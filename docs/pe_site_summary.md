# Production Engineer Portal (PE Site / Site B) — Summary

## 📌 Executive Overview

The **Production Engineer Portal (Site B / PE Site)** is the client-facing platform designed specifically for production engineers to browse stock, query AI insights, and submit raw material requests.

The StockPad ecosystem is structured as two interconnected platforms:
1. **Warehouse Manager Portal (Site A):** Central authority for stock levels, manager approvals, reporting, and webhook signing.
2. **Production Engineer Portal (Site B — *This Repository*):** Frontend & client backend allowing engineers to initiate material requests and track their status in real-time.

---

## 🛠️ Architectural Role & Dual-Site Workflow

```
       Production Engineer (Browser)
                     │
         Submits Material Request
                     ▼
  ┌─────────────────────────────────────┐
  │ Production Engineer Portal (Site B) │  <-- (This Repository)
  │   - Django REST Framework           │
  │   - PostgreSQL Database             │
  │   - Vanilla HTML / CSS / JS SPA     │
  └──────────────────┬──────────────────┘
                     │  1. Forward Request via REST API
                     │     Header: X-Site-B-API-Key
                     ▼
  ┌─────────────────────────────────────┐
  │  Warehouse Manager Portal (Site A)  │  <-- (External Authority)
  │   - Manages Inventory & Stock Logs  │
  │   - Approves / Rejects Requests     │
  └──────────────────┬──────────────────┘
                     │  2. Webhook Callback (Signed)
                     │     Header: X-Site-A-Signature (HMAC-SHA256)
                     ▼
  ┌─────────────────────────────────────┐
  │  Site B Updates Request Status      │
  │  (Pending ➔ Approved / Rejected)   │
  └─────────────────────────────────────┘
```

* **Request Delegation:** Site B saves request entries locally and forwards them to Site A via REST API calls using `X-Site-B-API-Key`.
* **Single Authority:** Site B does **not** allow local approval/rejection. All request approvals are controlled by Site A.
* **Callback Webhooks:** Site A pushes status updates back to Site B using HMAC-SHA256 cryptographic signatures (`X-Site-A-Signature`).

---

## 🚀 Key Features of the PE Portal (Site B)

### 1. Catalog & Inventory Synchronization
* Browses live material availability synced from Site A.
* Runs automated management commands (`sync_materials_from_site_a`) to pull catalog updates and current stock levels.

### 2. Request & Tracking Engine
* Form interface for engineers to request raw materials with required quantity and project details.
* Automatic retry mechanism (`retry_failed_syncs`) to re-attempt request submissions to Site A if network issues occur.
* Live status updates (`Pending`, `Approved`, `Rejected`) synced via webhooks.

### 3. AI Insights & Decision Chatbot
* Dedicated query bot for engineers to ask questions regarding material specs, stock recommendations, and logistics.
* Predictive warnings for high-demand materials and estimated days-to-depletion.

### 4. Security & Isolation
* **Authentication:** JWT (JSON Web Tokens) with auto-refresh mechanism & Google OAuth integration.
* **HMAC Verification:** Ensures callback webhooks originate strictly from Site A.
* **Email Fallback Routing:** Automatically routes unmapped engineer requests to admin accounts to prevent request drops.

---

## 💻 Tech Stack (Site B)
* **Backend:** Python / Django REST Framework + PostgreSQL (Hosted on Railway/Vercel)
* **Frontend:** Vanilla HTML5 / CSS3 / JavaScript (Single-Page Application)
* **Communication Protocol:** REST API + HMAC-SHA256 Signed Webhooks
