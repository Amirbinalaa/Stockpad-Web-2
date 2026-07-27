# StockPad — Site B (Production Engineer Portal) Hardening Checklist

**Scope:** This document is scoped entirely to the Site B repo. Tasks assume Django REST Framework + PostgreSQL, hosted on Railway/Vercel. Work through phases in order — each phase builds on the last.

**How to use this:** Hand one phase at a time to an agent/dev session. Don't bundle phases.

**Convention:** Tasks marked with ⚠️ **CROSS-SITE CHANGE** affect the contract with Site A. Whenever the agent completes one of these, it must explicitly state what needs to change on Site A — exact field names, formats, endpoints, and env vars — so nothing has to be guessed or reverse-engineered later.

---

## 📋 Resolved Site A Contract Details (read this first)

Site A's hardening (Phases 1–5) is **complete and verified**. The items below were previously open cross-site questions — they are now resolved. Use these exact values when implementing the matching Site B tasks; do not guess or invent alternatives.

| Contract item | Resolved value / behavior | Relevant Site B phase |
|---|---|---|
| **Health-check endpoint Site A calls** | Site A will send `GET` to Site B's health endpoint before pushing a webhook. Site B must expose `GET /api/v1/health/` (or set `SITE_B_HEALTH_CHECK_URL` on Site A to override). Must include header `X-Site-B-API-Key: <key>` support (Site A sends it). Expected healthy response: `HTTP 200` with JSON body `{"status": "healthy"}` (or `"ok"`). If unreachable/timeout, Site A aborts that webhook delivery attempt rather than retrying blindly. | Phase 2 |
| **Webhook `event_id` field** | Site A now includes `"event_id": "<uuid4-string>"` in **both** Creation Sync and Review Decision webhook payloads. A new `event_id` is generated per dispatch attempt by Site A, but stays **stable across Celery retries of the same delivery**. Site B must store seen `event_id`s and skip re-processing if a duplicate arrives (return `HTTP 200` without reapplying the status change). | Phase 3 |
| **Outbound `idempotency_key` field (Site B → Site A)** | Site A's `POST /api/inventory/requests/create/` now optionally accepts `"idempotency_key": "<uuid4-string>"` in the request body. **Site B must generate this UUID once per logical request** (before the first submission attempt) and send the **same value on every retry** of that request — never regenerate it per retry. If Site A sees a duplicate `idempotency_key`, it returns the existing request record instead of creating a new one (`HTTP 200`, not an error). Currently optional on Site A's side, but Site B should always send it. | Phase 3 |
| **Site A's dead-letter behavior (for parity reference)** | Site A logs permanently-failed outbound webhooks (after 3 retries) into a `WebhookDeliveryLog` model — `webhook_url`, `payload`, `event_id`, `error_message`, `attempt_count`, `created_at`. Site B's own dead-letter log for failed *outbound request submissions* (Phase 3) should follow the same shape/spirit for consistency, though it's a separate table on Site B's own DB. | Phase 3 |
| **Site A's caching pattern (for reference, not required to match)** | Site A uses **versioned cache keys** (e.g. `catalog_payload_v{version}_{email}`) with a version counter incremented via Django signals on any underlying data change, rather than explicit `cache.delete()` calls. This avoids race conditions on invalidation. Not a contract requirement for Site B, but worth reusing this pattern for Site B's own AI-insights/catalog caching in Phase 4 since it's already proven out. | Phase 4 (optional pattern reference) |
| **`SITE_B_API_KEY` rotation (Site B is the sender)** | Site A will accept **both** the old and new key simultaneously during a transition window via `SITE_B_API_KEY_NEW` on Site A's side. Site B's job: simply update its own `SITE_B_API_KEY` env var to the new value and redeploy — **only after** Site A confirms it has set `SITE_B_API_KEY_NEW` (Site A will announce this). Do not rotate unilaterally. | Phase 5 |
| **`SITE_A_API_KEY` (HMAC) rotation (Site B is the verifier)** | Site B must be able to **verify incoming webhook signatures against two secrets simultaneously** during rotation: (1) add the new HMAC secret as a secondary accepted value *before* Site A starts signing with it, (2) keep both accepted while Site A transitions, (3) remove the old secret only after Site A confirms it has fully cut over. The exact env var name for this on Site B is up to Site B's own implementation — just ensure the verification logic checks against a list/set of currently-valid secrets, not a single hardcoded one. | Phase 5 |
| **Retry-spike alerting pattern (for reference)** | Site A implemented a rolling 1-hour Redis counter (`cache.set(..., timeout=3600)`, refreshed on every retry) with a configurable threshold (`WEBHOOK_RETRY_SPIKE_THRESHOLD`, default 5) and a periodic Celery Beat sentinel task (every 15 min) as backup, logging `logger.critical("[WM ALERT] ...")`. Site B's Phase 5 alerting task can mirror this exact pattern for its own `retry_failed_syncs`/queue retries. | Phase 5 |

---

## Phase 1 — Quick Wins (low cost, low risk) #Done

Goal: immediate performance improvement with no architectural change.

- [x] **Add DB indexes** on:
  - Request status field (local mirror of pending/approved/rejected — used in the engineer's Requests page)
- [x] **Add pagination** to:
  - Requests page endpoint (engineer's own request history/tracking list)

**Done when:** The Requests page stays fast for an engineer with a long request history.

---

## Phase 2 — Decouple the Slow Part (medium cost, medium risk — isolate this phase) #Done

Goal: make outbound calls to Site A (and existing retry logic) non-blocking for the engineer's UI.

- [x] **Introduce a task queue** (Celery + Redis, or Django-RQ)
- [x] **Move request submission to Site A off the request/response cycle** — when an engineer submits a material request, Site B should save it locally and respond to the engineer immediately, then forward to Site A asynchronously
- [x] **Fold `retry_failed_syncs` into the queue** so retries are managed by the task queue's built-in retry/backoff instead of a separate scheduled command
- [x] **Add a lightweight health-check endpoint** (e.g. `GET /health/`) if one doesn't already exist, so Site A can verify Site B is reachable before pushing a webhook

> ⚠️ **CROSS-SITE CHANGE — RESOLVED, see table above.** Implement `GET /api/v1/health/` returning `HTTP 200` + `{"status": "healthy"}`. No further coordination needed — Site A already expects this exact shape.

**Done when:** Submitting a request feels instant to the engineer regardless of Site A's current latency or uptime, and failed sync attempts retry automatically via the queue.

**⚠️ Test thoroughly:** the full submit → local save → forward to Site A → webhook confirmation flow, including the case where Site A is temporarily unreachable.

---

## Phase 3 — Safe Retries (medium cost, low-medium risk) #Done

Goal: make sure retries can't create duplicate or conflicting data.

- [x] **Idempotency key on webhook handling** — when Site B receives Creation Sync or Review Decision webhooks from Site A, it should ignore a duplicate delivery (e.g. if Site A's queue retries a send) rather than double-applying a status update

> ⚠️ **CROSS-SITE CHANGE — RESOLVED, see table above.** Site A already sends `"event_id": "<uuid4>"` in both webhook events. Just implement dedup logic on Site B's side against this exact field name — no need to check with Site A further.

- [x] **Add an idempotency key to outbound request submissions** — when submitting (or retrying) a material request to Site A, send a stable client-generated key so Site A can detect duplicates from retries

> ⚠️ **CROSS-SITE CHANGE — RESOLVED, see table above.** Send `"idempotency_key": "<uuid4>"` in the request body — Site A already accepts and checks this exact field name (optional, but always send it). Generate once per logical request, reuse on every retry.

- [x] **Dead-letter log for failed request submissions** — persist a record when a request permanently fails to sync to Site A (exhausts retries), so it's visible instead of silently stuck in "pending" forever

**Done when:** A retried webhook from Site A can't corrupt a request's status, and an engineer (or admin) can actually see if a submission never made it to Site A.

---

## Phase 4 — Caching (medium cost, low risk) #

Goal: keep the engineer-facing AI features fast.

- [ ] **Cache AI insights/predictions** surfaced through the Inventory Assistant Chatbot and any predictive warnings (high-demand materials, days-to-depletion), refreshed on a schedule rather than computed per query
- [ ] **Ensure the local catalog cache** (from `sync_materials_from_site_a`) is read efficiently by the dashboard rather than re-querying more than needed

**Done when:** The chatbot and dashboard stay responsive even as the local material catalog and request history grow.

---

## Phase 5 — Operational Hygiene (low-medium cost, low risk, flexible timing) #Done

Goal: visibility into failures instead of silent degradation.

- [x] **Alerting when `retry_failed_syncs` (or its Phase-2 queue equivalent) fires repeatedly** — a spike here usually means Site A is unreachable or rejecting requests, and it's worth knowing before an engineer notices their request is stuck
- [x] **API key / HMAC secret rotation plan** *(joint task with Site A — see Site A checklist)* — document and test a rotation procedure for the `X-Site-B-API-Key` and shared HMAC signing secret that doesn't require simultaneous downtime on both sites

> ⚠️ **CROSS-SITE CHANGE — RESOLVED, see table above.** Site A has already built dual-key acceptance on its side (`SITE_B_API_KEY_NEW`, `SITE_A_API_KEY_NEW`) and written a full runbook (`SECRET_ROTATION_RUNBOOK.md`). Site B's remaining work: (1) support verifying against two HMAC secrets simultaneously, (2) follow the step order in the table above — do not rotate until Site A signals it's ready at each step.

**Done when:** You'd find out about a broken sync to Site A quickly, instead of an engineer reporting "my request has been pending for three days."

---

## Cross-Site Dependency Notes
- Phase 2 and 3 here are independent of Site A's equivalent work — no shared code, just a shared *contract* (the webhook payload format and HMAC signature must stay compatible with what Site A sends).
- Phase 5's key rotation task requires coordinating a deploy with Site A — don't rotate unilaterally.
