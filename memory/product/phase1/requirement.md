# Phase 1 — Store, checkout, ledger, desk, proof

Version: phase-1. Context: /app/memory/product/overview.md (features F-1..F-13, edge cases, seed).

## Goal
A buyer can pay for one of 3 slots via Stripe Checkout (test key), the webhook books it exactly once, a certificate appears on the proof wall, and the operator sees correct contribution and can refund.

## Functional requirements
Money module
- REQ-1 [always] The system shall derive every money figure from one constants module (price 109000, slots 3, fee 290 bps + 30, compute 2000, floor 100000, usd) in integer cents.
- REQ-2 [always] The system shall compute contribution per close as 103809 cents.
- REQ-3 [always] The system shall compute fully-refunded contribution as −5191 cents.

Landing & store
- REQ-4 [always] The landing page shall show "Three slots. One offer. One price.", the price "$1,090.00", and a "Take a slot" link to /s/shipready-sprint.
- REQ-5 [always] The store page shall show "N of 3 open" counted for the current Stripe mode only.
- REQ-6 [state] While open slots for the current mode are 0, the store page shall show "Sold out." with no buy button.
- REQ-7 [state] While no Stripe key is configured, the store page shall show "Payments not configured."
- REQ-8 [unwanted] If the slug is unknown or unpublished, then the system shall show a 404 page "Nothing at this address."

Checkout
- REQ-9 [event] When the buyer clicks "Take a slot", the system shall reserve one slot and redirect to a Stripe Checkout URL.
- REQ-10 [unwanted] If the request has no x-idem-key of 8+ chars, then the checkout API shall return 400.
- REQ-11 [event] When the same idem key is sent again, the checkout API shall return the same order and session without reserving another slot.
- REQ-12 [unwanted] If sold+reserved for the mode already equals 3, then the checkout API shall return 409 "sold out".
- REQ-13 [unwanted] If Stripe session creation fails, then the system shall release the reserved slot (interpreted).
- REQ-14 [always] The Checkout session shall carry namespace and orderId metadata on both the session and the payment_intent.
- REQ-15 [event] When the buyer returns with ?ok=1, the store page shall show a confirmation linking to their certificate once booked (interpreted).

Webhook
- REQ-16 [unwanted] If the Stripe signature is missing or invalid, then the webhook shall return 400.
- REQ-17 [event] When an event id was already processed, the webhook shall return 200 "replay" with no ledger change.
- REQ-18 [event] When checkout.session.completed (paid) or payment_intent.succeeded arrives for a known order, the system shall book exactly one charge ledger row keyed op_key "charge:<pi>".
- REQ-19 [unwanted] If amount, currency, mode or namespace mismatch the local order, then the webhook shall book nothing.
- REQ-20 [unwanted] If the event cannot be matched to a local order, then the webhook shall return 200 and record it as unresolved (interpreted).
- REQ-21 [event] When a charge is booked, the system shall issue one certificate code matching ^SR-[0-9A-HJKMNP-TV-Z]{12}$.
- REQ-22 [event] When checkout.session.expired or checkout.session.async_payment_failed arrives, the system shall mark the order expired.
- REQ-23 [event] When an order expires, the system shall release its reserved slot.
- REQ-24 [event] When a succeeded refund event arrives, the system shall book a refund row of −min(amount, remaining) keyed "refund:<refund_id>".
- REQ-25 [event] When refunds reach the full amount, the system shall return the slot to open capacity (interpreted: sold→released, not re-held).
- REQ-26 [event] When refunds reach the full amount, the system shall mark the certificate REVOKED.
- REQ-27 [event] When charge.dispute.created arrives, the system shall book a dispute debit capped at the unrefunded amount.
- REQ-28 [event] When charge.dispute.closed with status won arrives, the system shall book a reversal equal to the debit.
- REQ-29 [unwanted] If processing throws mid-event, then the system shall roll back the inbox claim so a retry re-processes.

Operator
- REQ-30 [event] When the operator submits the correct secret on /access, the system shall set an HttpOnly signed cookie valid 8 hours and open /desk.
- REQ-31 [unwanted] If the secret is wrong, then /access shall show "Wrong secret."
- REQ-32 [unwanted] If an unauthenticated user opens /desk or calls refund/orders APIs, then the system shall redirect to /access or return 401.
- REQ-33 [always] The desk shall show contribution, closes booked, closes remaining to $1,000, gross, refunds, disputes, fees actual/estimated and compute for the current mode.
- REQ-34 [always] The desk shall list orders with state, amount, refunded amount and certificate code.
- REQ-35 [event] When the operator refunds an order (full or partial amount), the system shall create one Stripe refund.
- REQ-36 [unwanted] If the same refund request is repeated, then the system shall not create a second Stripe refund.
- REQ-37 [unwanted] If the refund amount exceeds the remaining amount, then the system shall cap it at the remaining amount.
- REQ-38 [always] The desk shall show a status panel: mode, the exact public webhook URL to paste into Stripe, webhook secret set yes/no, last webhook received time.

Proof & certificates
- REQ-39 [always] /proof shall list certificates newest first with code, ship, verified amount and LIVE/TEST/REVOKED.
- REQ-40 [state] While no certificates exist, /proof shall show "No certificates yet. Nothing here is invented."
- REQ-41 [always] /p/:code shall show "Verified" or "REVOKED" with mode, verified contribution and issued time.
- REQ-42 [unwanted] If the code is unknown, then /p/:code shall show the 404 page.

Sweep & health
- REQ-43 [always] The system shall expire reserved orders past their 45-minute hold at least every 5 minutes, releasing slots on each order's own ship.
- REQ-44 [always] GET /api/health shall return {"ok":true}.
- REQ-45 [always] GET /api/openapi.json shall serve the API spec.

## Quality requirements
```
Q-1  Tag: Money.Exactness
     Scale: ledger effects per Stripe operation
     Meter: replay the same signed webhook 5x, count ledger rows
     Must: exactly 1   Plan: exactly 1
Q-2  Tag: Capacity.Oversell
     Scale: slots sold+reserved per mode
     Meter: 10 concurrent checkout requests with distinct idem keys
     Must: never > 3   Plan: never > 3, extras get 409
Q-3  Tag: Money.Arithmetic
     Scale: cents difference from expected desk figures
     Meter: book 1 charge then full refund via signed test webhooks
     Must: 0 (103809 then −5191)   Plan: 0
Q-4  Tag: Security.OperatorExposure
     Scale: protected endpoints reachable without cookie
     Meter: curl each operator endpoint unauthenticated
     Must: 0   Plan: 0
Q-5  Tag: Webhook.Reliability
     Scale: non-2xx responses to valid-signed unmatched events
     Meter: send signed event for unknown PI
     Must: 0   Plan: 0
Q-6  Tag: Perf.Checkout
     Scale: ms from click to Stripe redirect URL returned
     Meter: 5 trials
     Must: < 4000   Plan: < 1500
Q-7  Tag: UX.Mobile
     Scale: horizontal overflow on store/desk at 390px width
     Meter: browser screenshot
     Must: none   Plan: none
```
