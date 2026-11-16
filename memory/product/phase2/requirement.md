# Phase 2 — AI drafts outbox + go-live readiness

Version: phase-2. Context: /app/memory/product/overview.md (F-14..F-16). Builds on Phase 1 as delivered: FastAPI + React + Mongo, operator cookie auth, /desk, Stripe sandbox test key, webhook at /api/webhooks/stripe (+ /api/stripe/webhook alias).

## Goal
Help the operator get the first real sale: Claude Sonnet 5.5 (Emergent Universal Key) writes outreach drafts and buyer delivery notes the operator edits and approves. Also make the app ready to flip to live Stripe without code changes.

## Functional requirements
Prospects & outreach
- REQ-46 [event] When the operator pastes prospects as "handle | reason" lines on /desk/drafts, the system shall save one prospect per valid line.
- REQ-47 [unwanted] If a line has no "|" or an empty handle, then the system shall skip it and show "N lines skipped".
- REQ-48 [event] When the operator clicks "Write outreach" on a prospect, the system shall create one draft from Claude Sonnet 5.5 that names the offer, the $1,090 price, 3 slots, and the store link.
- REQ-49 [always] Outreach drafts shall not promise income, guaranteed results, or invented testimonials.
- REQ-50 [unwanted] If the AI call fails, then the system shall show "Draft failed — try again" and keep no partial draft.
Delivery notes
- REQ-51 [event] When an order becomes paid, the system shall offer a "Write delivery note" action on that order in the desk.
- REQ-52 [event] When the operator clicks it, the system shall create a delivery-note draft that includes the buyer's certificate code and /p/<code> link.
Outbox
- REQ-53 [always] The outbox shall list drafts with kind (outreach/delivery), target, status (draft/approved/discarded) and created time.
- REQ-54 [event] When the operator edits a draft and saves, the system shall store the edited text.
- REQ-55 [event] When the operator clicks Approve, the system shall set status approved and show a Copy button.
- REQ-56 [event] When the operator clicks Discard, the system shall set status discarded.
- REQ-57 [always] The system shall never send, post or email any draft.
- REQ-58 [always] Draft actions shall never write to orders, ledger, ships or certificates.
- REQ-59 [unwanted] If unauthenticated, then all draft/prospect APIs shall return 401.
Go-live readiness
- REQ-60 [always] The system shall pick live vs test mode solely from the configured Stripe secret key prefix (sk_live_ / sk_test_).
- REQ-61 [state] While in live mode, /proof shall hide TEST certificates (interpreted).
- REQ-62 [always] The desk status panel shall show a "Go-live checklist": deployed public URL in use, live key set, live webhook secret set, last live webhook received.
- REQ-63 [event] When the operator clicks "Reset test data" on the desk, the system shall delete test-mode orders, ledger rows, certificates, inbox entries and reset test slot counters, leaving live data untouched.

## Quality requirements
```
Q-8  Tag: AI.Quality
     Scale: drafts with a false claim (income promise, fake testimonial, wrong price/slots)
     Meter: generate 5 outreach drafts, read them
     Must: 0   Plan: 0
Q-9  Tag: AI.Latency
     Scale: seconds from click to draft shown
     Meter: 3 trials
     Must: < 30   Plan: < 12
Q-10 Tag: Money.Isolation
     Scale: changes to ledger/orders/certs from any draft or reset-test action on live data
     Meter: snapshot counts before/after
     Must: 0   Plan: 0
```
