# StockPad — Project State Handoff (for new agent session)

**Purpose:** This document lets a new agent session pick up work immediately without needing re-explanation of the project or prior work. Read this fully before doing anything.

---

## 1. What StockPad Is

A two-site warehouse management system:
- **Site A (Warehouse Manager Portal)** — the authority/ledger. Managers approve requests, own inventory truth.
- **Site B (Production Engineer Portal)** — engineers browse catalog (scoped to their connected manager) and submit material requests. Site B never mutates inventory directly; it only requests and displays.

Both are separate repos: Django REST Framework + PostgreSQL backends, vanilla HTML/CSS/JS frontends, hosted on Railway.

---

## 2. Site A Status — ✅ FULLY COMPLETE (all 5 hardening phases done, tested, and deployed live)

Site A went through a 5-phase "hardening" process (performance/reliability improvements — **no new features, no UI changes**). All phases are implemented, tested (48/48 automated tests passing), and **live on Railway** with a working Celery worker + Redis.

| Phase | What it did | Status |
|---|---|---|
| 1 | DB indexes, pagination, rate limiting | ✅ Done, deployed |
| 2 | Async Celery webhook delivery (was blocking approve/reject before) | ✅ Done, deployed, worker verified running |
| 3 | Idempotency keys (`idempotency_key` on requests) + `event_id` on webhooks + dead-letter logging | ✅ Done, deployed |
| 4 | Redis caching for AI insights + catalog, with versioned cache keys per-engineer (`catalog_payload_v{version}_{email}`) to avoid stale/leaked data | ✅ Done, deployed |
| 5 | Webhook retry-spike alerting + zero-downtime API key/HMAC rotation runbook (`docs/SECRET_ROTATION_RUNBOOK.md`) | ✅ Done, deployed |

**Two extra bugs found and fixed along the way (not originally planned, but important context):**
1. A frontend bug: Phase 1's pagination changed the Requests API response shape from a plain array to `{count, next, previous, results}`. This broke `api-service.js`/`script.js`, which expected a plain array — fixed with a safe fallback, working counters (3 parallel status-count requests with a 30s cache + invalidation on approve/deny), and added pagination UI.
2. A pre-existing (unrelated to hardening) bug: profile/material images were 404ing because `settings.py` used the deprecated `DEFAULT_FILE_STORAGE` instead of Django 4.2+'s `STORAGES` dict — meaning uploads silently fell back to Railway's ephemeral local filesystem instead of Cloudinary. Fixed by adding the proper `STORAGES` dict. Two old broken image records (`User id=2`, `Material id=3`) are unrecoverable and those users need to re-upload manually.

**Railway infra for Site A now includes:** `web` service, `worker` service (Celery, `--concurrency=2` — do NOT leave default concurrency, it caused OOM crash loops), and a `Redis` service. All Online.

---

## 3. Site B Status — 🟡 NOT STARTED (checklist ready, zero code changes made yet)

**Nothing has been implemented on Site B yet.** No push has been made. This is the next work to do.

The full phased checklist for Site B is attached separately: **`SiteB_PE_Hardening_Checklist.md`**. It already contains a section called **"📋 Resolved Site A Contract Details"** at the top — this has all the exact field names, endpoint specs, and formats already finalized from Site A's implementation, so Site B's agent does NOT need to guess or ask Site A anything. Use those exact values.

Key resolved contract items Site B will need to implement across its phases:
- A health-check endpoint (`GET /api/v1/health/` returning `{"status": "healthy"}`) — Site A will ping this before sending webhooks.
- Accept `event_id` field in incoming webhooks for deduplication.
- Send `idempotency_key` field on outbound request submissions.
- Support dual-key HMAC verification during future key rotation (not urgent, just needs to be built to support it later).

---

## 4. How This Project Has Been Managed (please follow the same process)

This has been a deliberate, phase-by-phase hardening process — **not feature development**. The working method that's been used successfully so far:

1. **One phase at a time**, never bundle phases in a single agent session.
2. **Verify, don't just trust "done."** Every phase has been followed by direct verification questions before accepting changes (e.g., confirming test counts didn't silently drop, confirming security-sensitive logic like cache isolation actually has a dedicated test, confirming a fix didn't just patch around a bug via mocking).
3. **Cross-site changes are flagged explicitly.** Any task that touches the Site A ↔ Site B contract is marked and must be reported back with exact technical details (field names, formats, endpoints) before being considered done.
4. **Cost-conscious model tier selection:** Low-risk mechanical tasks (logging, simple config) can use a lighter model tier. Anything touching security, data isolation, or shared contracts should use a stronger tier — this has been the practice throughout Site A's work and should continue for Site B.

---

## 5. Immediate Next Step

Start Site B's **Phase 1** (DB indexes + pagination — low risk, low cost) using the attached `SiteB_PE_Hardening_Checklist.md`. Use the same prompt style as before: scope strictly to one phase, don't touch anything else, run tests, report results, update the checklist file itself.

If quota runs out again mid-phase, update this handoff document (or ask the agent to produce a similar summary of exactly what was done and what's left) before switching accounts again.
