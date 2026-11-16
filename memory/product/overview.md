# Requirements: Shipready

Rebuild of the user's pasted `build-shipready.sh` (Next.js + Postgres) on the platform stack: FastAPI + React + MongoDB. Same product rules, same money math. The pasted script is the reference spec; known bugs in it are fixed (see Edge Cases).

## Core Value
Sell exactly 3 slots of one offer at one price through Stripe Checkout, book every money event exactly once in an append-only ledger, and show the operator honest, ledger-derived contribution against a $1,000 target.

## Personas & Roles
- **Buyer (public, no login)**: views offer, takes a slot via Stripe Checkout, gets a verifiable certificate.
- **Public visitor**: views proof wall and any certificate page.
- **Operator (single)**: logs in with one shared operator secret (generated at setup, shown once in /app/memory/test_credentials.md). Sees desk, issues refunds, reviews/approves AI drafts.

## Features
| id | feature | persona | phase |
|---|---|---|---|
| F-1 | Single money-assumptions module (price 109000c, 3 slots, fee 2.9%+30c, compute 2000c, floor 100000c, usd) | all | 1 |
| F-2 | Landing page: headline, price, per-close contribution arithmetic, CTA | visitor | 1 |
| F-3 | Store page /s/shipready-sprint: open slots (mode-aware), Buy button, sold-out & payments-off states | buyer | 1 |
| F-4 | Checkout: idempotent (x-idem-key), atomic slot reservation, 45-min hold, Stripe Checkout session with namespace/orderId metadata on session AND payment_intent | buyer | 1 |
| F-5 | Stripe webhook: signature verified on raw body, event inbox dedupe, op_key-unique ledger effects in one atomic unit, validates namespace/mode/amount/currency | system | 1 |
| F-6 | Ledger booking: charge, refund (partial/full), dispute, dispute reversal (won), checkout expiry; slot counters; certificate issue/revoke | system | 1 |
| F-7 | Operator login (shared secret → HMAC-signed HttpOnly cookie, 8h) | operator | 1 |
| F-8 | Desk: contribution, closes booked, closes remaining to target, gross/refunds/disputes/fees(actual/est)/compute, orders list | operator | 1 |
| F-9 | Operator refund (full or partial) from desk, truly idempotent | operator | 1 |
| F-10 | Proof wall (/proof) listing certificates with LIVE/TEST/REVOKED | visitor | 1 |
| F-11 | Certificate page (/p/:code) Verified/REVOKED | visitor | 1 |
| F-12 | Sweep: expire stale holds (bounded) and release slots on their own ship; runs automatically | system | 1 |
| F-13 | Health + stripe status endpoints, doctor-style status panel on desk (webhook URL to paste into Stripe, last webhook received, mode) | operator | 1 |
| F-14 | AI draft writer (Claude Sonnet 5.5): outreach drafts from operator-entered prospect list | operator | 2 |
| F-15 | AI draft writer: delivery note draft per paid buyer | operator | 2 |
| F-16 | Drafts outbox: edit, approve, discard; nothing auto-sends; drafts never touch money | operator | 2 |

## Phases
- **Phase 1** — Store, checkout, webhook ledger, refunds/disputes, desk, proof, certificates, sweep, status. F-1..F-13. [requirement](phase1/requirement.md) · [journeys](phase1/journeys.md)
- **Phase 2** — AI drafts outbox. F-14..F-16.

## UI/UX Rules
- Dark, minimal, typographic look from the script: bg #0b0b0d, fg #e9e9ee, dim #8a8a94, line #23232a, signal #c6f24e. Big signal-coloured price numbers, tabular figures, monospace for codes.
- Every money figure labelled "estimated / ledger-derived, not bank settlement" where shown.
- No invented data: empty states say so ("No certificates yet. Nothing here is invented.").

## Integrations
- **Stripe** — environment test key in pod (never ask user for keys). Checkout Sessions + webhooks. User says their Stripe account is live; going live = user claims the account / later switches keys via secure flow. Webhook endpoint must be public HTTPS on the preview/deploy URL.
- **Claude Sonnet 5.5** via Emergent Universal Key (phase 2).
- No email sending, no auto-posting.

## Edge Cases
Bugs in the pasted script to fix, not replicate:
- `CLOSES_FOR_FLOOR` was imported but undefined → define it from the math (=1).
- Refund idempotency key included a timestamp → must be stable per (order, requested amount, client idem key).
- Sweep only released slots on one hard-coded ship → release on each order's own ship.
- Unknown/foreign payments returned 503 → Stripe retries and may disable endpoint; return 200 with "unresolved/foreign" recorded.
- Handle `checkout.session.async_payment_failed` as expire (release slot).
- Webhook secret: must be the one for this endpoint; status panel shows exact URL.
Math: contribution/close = 109000 − 3191 − 2000 = 103809 ($1,038.09); fully refunded = −5191 (−$51.91). 1 close clears $1,000.
- Test-mode purchases never consume live capacity and vice versa.
- Capacity can never exceed 3 per mode, even under concurrent checkouts.

## Seed Data
- One published ship: slug `shipready-sprint`, title "Shipready Sprint", 109000c, compute 2000c, 3 slots. Idempotent seed.
- Operator secret generated, stored in backend env, written to /app/memory/test_credentials.md.
- No fake orders, certificates or ledger rows.
