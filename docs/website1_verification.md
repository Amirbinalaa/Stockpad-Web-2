# Website 1 (StockPad) Live Verification Checklist

Once Website 1's team shares the production credentials, perform the following steps to verify the end-to-end integration:

## 1. Credentials Configuration
- [ ] Configure environment variables in the host environment (or updated `.env` file):
  - `SITE_A_BASE_URL`: The production URL of Website 1 (e.g. `https://stockpad-backend-production.up.railway.app`)
  - `SITE_A_API_KEY`: The API key supplied by Website 1's team.
  - `SITE_A_WEBHOOK_SECRET`: The HMAC secret shared by Website 1 to verify incoming signatures.
  - `SITE_B_PUBLIC_WEBHOOK_URL`: The public-facing endpoint of this instance (e.g. `https://your-domain.com/api/webhooks/material-status/`). Note that localhost/127.0.0.1 cannot receive external webhooks from Website 1 unless exposed via ngrok or cloudflare tunnels.
- [ ] Confirm Django startup is successful and does not raise `ImproperlyConfigured`.

## 2. Materials Catalog Synchronization
- [ ] Run the catalog sync command:
  ```bash
  python manage.py sync_materials_from_site_a
  ```
- [ ] Verify command output indicates a non-zero count of materials synchronized (e.g., `Successfully synchronized N materials (Created: X, Updated: Y)`).
- [ ] Verify in Website 2's admin panel or interface that the materials have their `site_a_material_id` fields populated.

## 3. End-to-End Request Submission
- [ ] Log in as an engineer in Website 2's UI.
- [ ] Submit a new material request.
- [ ] Verify that:
  - The request is saved locally.
  - The request transitions status/sync fields: `sync_status` should become `'synced'`.
  - The `site_a_request_id` field in the database populates with a valid non-empty ID returned from Website 1's response.
- [ ] Verify that there is a log message like `Successfully synced request N to Website 1 (Site A ID: ...)` in the `api` logger.

## 4. Webhook Status Verification
- [ ] Ask the manager/admin to approve or reject the request on Website 1's dashboard.
- [ ] Monitor the incoming webhook logs in Website 2's server logs:
  - Confirm the incoming webhook payload signature `X-Site-A-Signature` is successfully validated.
  - Check that no 403 or 500 status codes are returned by `/api/webhooks/material-status/`.
  - Verify that the local request transitions to the correct status (e.g., `approved` or `rejected`) on Website 2.
  - Verify that a `RequestStatusHistory` record is created with `changed_by=None` and notes `'Status updated via Website 1 webhook.'`.

## 5. UI Sanity Check
- [ ] Log in as a manager on Website 2's dashboard.
- [ ] View the requests tab.
- [ ] Visually confirm that the Approve and Reject buttons are **completely absent** from the manager dashboard for any pending requests, and only the current synced status is visible.

---

## 6. Periodic Scheduling

### Recommended approach: system cron (no Celery required)

The project does not use Celery. Adding it solely for two periodic tasks would introduce a message broker dependency (Redis or RabbitMQ), worker processes, and beat-scheduler — a significant operational overhead increase for what are short, stateless, shell-safe management commands.

**Use cron instead.** It's zero-dependency, visible in the OS, and produces email alerts on non-zero exit codes out of the box.

#### Suggested crontab entries

Open the crontab with `crontab -e` on Linux/macOS, or add a Scheduled Task on Windows. Example entries:

```cron
# Sync materials catalog from Website 1 every 15 minutes
*/15 * * * * cd /path/to/Website2/backend && venv/bin/python manage.py sync_materials_from_site_a >> logs/sync_materials.log 2>&1

# Retry failed request syncs every 10 minutes
*/10 * * * * cd /path/to/Website2/backend && venv/bin/python manage.py retry_failed_syncs >> logs/retry_syncs.log 2>&1
```

> **Replace `/path/to/Website2/backend`** with the actual absolute path on the server.

#### Why these intervals?
- **15 min for catalog sync** — stock levels don't need sub-minute freshness; 15 min is a good balance between currency and API load.
- **10 min for retry** — failed submissions should be retried soon after connectivity recovers, but there's no benefit going faster than the root cause (Website 1 downtime) resolves.

#### Cron error surfacing
Both commands now exit non-zero on failure (`raise CommandError`). Cron by default emails the crontab owner when a job produces any output on stderr or exits non-zero. To make this explicit, ensure the server's MTA is configured, or redirect to a dedicated monitoring endpoint:

```cron
# Alternative: pipe failures to a Slack/webhook alert script
*/15 * * * * cd /path/to/Website2/backend && venv/bin/python manage.py sync_materials_from_site_a >> logs/sync_materials.log 2>&1 || curl -s -X POST "$SLACK_WEBHOOK_URL" -d '{"text":"sync_materials_from_site_a failed — check logs"}'
```

#### If Celery is added in the future
If the project later adopts Celery (e.g. for async email sending or other tasks), migrate these to `celery beat` periodic tasks in `CELERY_BEAT_SCHEDULE`. The tradeoff versus cron:

| | **cron** | **Celery beat** |
|---|---|---|
| Dependencies | None (OS-level) | Redis/RabbitMQ + worker + beat process |
| Monitoring | OS cron mail / exit codes | Flower, Sentry, etc. |
| Retry on worker crash | No (next schedule tick) | Yes (depending on `acks_late`) |
| Ease of setup | ✅ Trivial | ⚠️ Extra infra |
| Good for this project now | ✅ Yes | ❌ Over-engineered |

---

## 7. Concurrency Safety

`sync_materials_from_site_a` and `retry_failed_syncs` are safe to run concurrently. Here is why:

### They operate on completely disjoint rows

| Command | Rows touched |
|---|---|
| `sync_materials_from_site_a` | `Material` rows (via `update_or_create` on `site_a_material_id`) |
| `retry_failed_syncs` | `MaterialRequest` rows (only those with `sync_status='sync_failed'`) |

No row is written by both commands simultaneously.

### Neither holds a long-running transaction

- **`sync_materials_from_site_a`**: Each `update_or_create` call is a short, independent statement with no wrapping `transaction.atomic()` block. There is no lock held across the full loop.
- **`retry_failed_syncs`**: Each `req.save(update_fields=...)` is a short, independent `UPDATE`. No transaction spans the full retry loop.

### The only shared table risk is avoided by design

`retry_failed_syncs` filters `MaterialRequest` rows by `sync_status='sync_failed'`. The `SiteAWebhookView` (which writes `MaterialRequest` rows) uses `select_for_update()` inside `transaction.atomic()`, but only for the duration of a single webhook HTTP request — a few milliseconds. The retry command's individual `req.save()` calls do not conflict with this.

### Recommendation

No changes needed. If you later introduce a `sync_materials` task that also modifies `MaterialRequest` rows (e.g. auto-creating requests from low-stock alerts), revisit this analysis at that time.

