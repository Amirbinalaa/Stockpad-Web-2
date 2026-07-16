<<<<<<< HEAD
# StockPad — Engineer App (Website 2)

A Django REST Framework backend + vanilla-JS frontend for Wheeler & Senior's internal material request workflow. Engineers submit material requests through this app; approvals are handled by [StockPad (Website 1)](https://stockpad-backend-production.up.railway.app) and pushed back here via signed webhooks.

---

## Architecture Overview

```
Engineer (browser)
      │  submit request
      ▼
 Website 2 (this repo)          Website 1 (StockPad — external)
 ┌─────────────────────┐        ┌──────────────────────────────┐
 │  Django REST API    │──────► │  POST /api/requests/         │
 │  PostgreSQL DB      │◄──────  │  Webhook → signed callback   │
 │  Vanilla JS UI      │        │  Manager approves/rejects    │
 └─────────────────────┘        └──────────────────────────────┘
```

- **Engineers** submit requests in Website 2's UI.  
- **Website 2** saves the request locally and forwards it to Website 1 via its REST API.  
- **Website 1** is the sole authority on approval/rejection and notifies Website 2 via a signed HMAC-SHA256 webhook.  
- Local approve/reject buttons are intentionally removed — all status changes come from Website 1.

---

## Project Structure

```
Website 2/
├── backend/                  Django project root
│   ├── api/                  Main app (models, views, serializers, tests)
│   │   ├── management/
│   │   │   └── commands/
│   │   │       ├── sync_materials_from_site_a.py   # pull catalog & stock from Website 1
│   │   │       └── retry_failed_syncs.py           # retry failed request submissions
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── site_a_client.py  # outbound HTTP client for Website 1
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── stockpad_backend/     Django settings, URLs, WSGI/ASGI
│   ├── manage.py
│   └── _env                  ← env variable template (copy → .env, fill in values)
├── frontend/                 Vanilla JS single-page app
│   ├── index.html
│   ├── script.js
│   └── style.css
└── docs/
    └── website1_verification.md   # live-key integration checklist & cron setup
```

---

## Prerequisites

- Python 3.8+
- PostgreSQL 13+
- A running instance of [Website 1 (StockPad)](https://stockpad-backend-production.up.railway.app) with API credentials

---

## Local Development Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd "Website 2"
```

### 2. Create and activate a virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> If `requirements.txt` is missing, generate it from the current environment:
> ```bash
> pip freeze > requirements.txt
> ```

### 4. Configure environment variables

Copy the template and fill in your values:

```bash
cp _env .env
```

Edit `.env`:

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DB_PASSWORD=your-postgres-password

# Email
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Gemini AI
GEMINI_API_KEY=your-gemini-key

# Website 1 integration
SITE_A_BASE_URL=https://stockpad-backend-production.up.railway.app
SITE_A_API_KEY=supplied-by-website-1-team
SITE_A_WEBHOOK_SECRET=supplied-by-website-1-team
SITE_B_PUBLIC_WEBHOOK_URL=https://your-domain.com/api/webhooks/material-status/
```

> ⚠️ **Never commit `.env` or `_env` with real values.** Both are gitignored.

### 5. Create the PostgreSQL database

```sql
CREATE DATABASE stockpad_db;
```

### 6. Apply migrations

```bash
python manage.py migrate
```

### 7. Seed initial data (optional)

```bash
python manage.py seed
```

### 8. Run the development server

```bash
python manage.py runserver
```

Open `frontend/index.html` in a browser (or serve it with a static file server).

---

## Website 1 Integration

### Sync materials catalog from Website 1

Pull the latest materials and stock levels into the local database:

```bash
python manage.py sync_materials_from_site_a

# With a minimum expected count guard (aborts if response has < 10 items):
python manage.py sync_materials_from_site_a --min-expected 10
```

The command will:
- Exit non-zero (surfacing to cron/monitoring) on any network or format error
- Abort and leave local data untouched if the response drops by >50% vs. the previous sync (suspicious empty/bad response guard)
- Print a detailed summary: `Synchronized N materials (Created: X, Updated: Y)`

### Retry failed request syncs

```bash
python manage.py retry_failed_syncs
```

Re-submits any `MaterialRequest` records with `sync_status='sync_failed'` to Website 1. Exits non-zero if all retries fail.

### Scheduling (cron — recommended)

Add to your crontab (`crontab -e`):

```cron
# Sync catalog every 15 minutes
*/15 * * * * cd /path/to/backend && venv/bin/python manage.py sync_materials_from_site_a >> logs/sync_materials.log 2>&1

# Retry failed syncs every 10 minutes
*/10 * * * * cd /path/to/backend && venv/bin/python manage.py retry_failed_syncs >> logs/retry_syncs.log 2>&1
```

See [docs/website1_verification.md](docs/website1_verification.md) for full scheduling details, Celery migration guidance, and the live-key verification checklist.

### Inbound webhooks

Website 1 calls `POST /api/webhooks/material-status/` to push approval/rejection decisions. The endpoint verifies the `X-Site-A-Signature` header using HMAC-SHA256 with `SITE_A_WEBHOOK_SECRET`.

> For local testing, expose the dev server using [ngrok](https://ngrok.com/) or [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) and set `SITE_B_PUBLIC_WEBHOOK_URL` accordingly.

---

## Running Tests

```bash
cd backend
python manage.py test api
```

All 7 integration tests cover: webhook HMAC verification, duplicate delivery idempotency, offline fallback to `sync_failed`, and client payload structure.

---

## Production Checklist

Before deploying, ensure:

- [ ] `DJANGO_DEBUG=False` in the environment
- [ ] `DJANGO_SECRET_KEY` is a long random string (never the dev default)
- [ ] `DB_PASSWORD` is set (Django will refuse to start if missing in production)
- [ ] `SITE_A_API_KEY`, `SITE_A_WEBHOOK_SECRET`, `SITE_B_PUBLIC_WEBHOOK_URL` are all set (Django will refuse to start if any are missing in production)
- [ ] Cron jobs are configured for `sync_materials_from_site_a` and `retry_failed_syncs`
- [ ] The webhook URL is publicly reachable by Website 1
- [ ] Run through the manual checklist in [docs/website1_verification.md](docs/website1_verification.md)

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/token/` | Obtain JWT token pair |
| `POST` | `/api/token/refresh/` | Refresh JWT |
| `GET` | `/api/materials/` | List materials (synced from Website 1) |
| `POST` | `/api/requests/` | Submit a new material request |
| `GET` | `/api/requests/` | List requests for current user |
| `POST` | `/api/webhooks/material-status/` | Inbound signed webhook from Website 1 |
| `POST` | `/api/chatbot/` | Gemini AI chatbot |

---

## License

Internal capstone project — Wheeler & Senior.
=======
# Stockpad-Web-2
>>>>>>> 4a5d5576a17db4f9b39e6fdb46abe110092e81f3
