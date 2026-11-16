# Shipready — PRD (Phase 1)

## Original problem statement
Build Phase 1 of "Shipready" (FastAPI + React + MongoDB) per /app/memory/product/overview.md, phase1/requirement.md, phase1/journeys.md: F-1..F-13 (no AI drafts). Top priority: working public Stripe webhook POST /api/webhooks/stripe. Integer-cent money module; no oversell; append-only ledger (unique op_key); webhook inbox (unique event_id, rollback on failure); namespace/mode/amount/currency validation; unresolved events → 200; stable refund idempotency; auto sweep; HMAC cookie operator auth; desk status panel; dark minimal design.

## Architecture
- backend: money.py (constants), config.py (env), db.py (Mongo + Pydantic BaseDocument models + indexes), slots.py (atomic per-mode slot ops, idempotent via ship.slot_ops), ledger.py (event → ledger effects), auth.py (HMAC cookie), server.py (routes, webhook, sweep loop, seed)
- Stripe: platform claimable sandbox (test). Endpoint we_1UcTMJAKc8hoKIW1SqpsFsGs → /api/webhooks/stripe (9 events). Platform endpoint /api/stripe/webhook also accepted (shared inbox dedupe).
- No Mongo replica set → no transactions; compensating logic (op_key/event_id uniqueness, per-order applied_ops, slot_pending repair in sweep).
- frontend: pages Landing, Store, Access, Desk (Metrics, StatusPanel, OrdersTable, RefundDialog), Proof, Certificate, NotFound.
- scripts/stripe_sim.py: signed-event simulator + real PaymentIntent/dispute helpers.

## Implemented (2026-11-16)
- F-1..F-13 all done; real Stripe test delivery verified (payment_intent.succeeded, refund.created/updated, checkout.session.expired)
- Testing iteration_1: backend 11/11, frontend all journeys pass; minor fixes applied (refund cap includes disputes, actual fee retry in sweep, refund dialog live remaining, sim timeout)

## Backlog
- P1: Phase 2 — AI drafts outbox (F-14..F-16, Claude Sonnet 5.5)
- P2: live-mode switch (claim sandbox), dispute fee accounting, multi-worker lock (currently in-process asyncio.Lock)

## Phase 2 (2026-11-16)
- Drafts outbox (/desk/drafts): prospects paste, outreach + delivery-note drafts via Claude claude-sonnet-5-5 (Emergent LLM key), server-side honesty checks (price/slots/link required, forbidden promise words), edit/approve/copy/discard; never sends. 503 "Draft failed — try again" on failure.
- Go-live: mode from key prefix only, /proof hides TEST certs in live mode, Go-live checklist, Reset test data (test-mode only).
- Add-on: webhook accepts sandbox/preview/account secrets, records matched label; status panel lists secrets + last verified delivery; Stripe account id shown.
- iteration_2: Phase 2 21/21, Phase 1 regression 11/11. Test data reset → 3 of 3 open.
