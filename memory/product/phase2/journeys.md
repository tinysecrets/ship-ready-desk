# Phase 2 journeys (Phase 1 journeys remain valid)

- JRN-27 — steps: log in, open drafts, paste "alice | replied twice\nbob | runs an agency\nbadline". expected: 2 prospects listed; "1 lines skipped".
- JRN-28 — steps: click Write outreach on alice. expected: within 30s a draft appears mentioning $1,090, 3 slots and the /s/shipready-sprint link; no income guarantee.
- JRN-29 — steps: edit the draft text, save, reload. expected: edited text persists.
- JRN-30 — steps: approve a draft. expected: status approved; Copy button visible; nothing is sent anywhere.
- JRN-31 — steps: discard a draft. expected: status discarded.
- JRN-32 — steps: on a paid order click Write delivery note. expected: draft includes that order's SR- code and /p/<code> link.
- JRN-33 — steps: snapshot ledger/orders/certs counts, run draft actions. expected: counts unchanged.
- JRN-34 — steps: call draft/prospect APIs without cookie. expected: 401.
- JRN-35 — steps: open desk status panel. expected: Go-live checklist with 4 items showing current state (test key → "live key set: no").
- JRN-36 — steps: click Reset test data, confirm. expected: test closes 0, contribution $0.00, store "3 of 3 open", /proof empty-state; live data untouched.
- JRN-37 — steps: AI unavailable (simulated failure). expected: "Draft failed — try again"; no empty draft saved.
