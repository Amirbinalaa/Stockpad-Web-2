# 📋 StockPad Webhook Security & Performance Audit Report

This report presents a comprehensive backend and system integration audit of the **StockPad Warehouse Management (WM) / Production Engineer Portal** ecosystem, focusing on establishing a secure, asynchronous (Zero-Delay) webhook pipeline to send real-time material request updates.

---

## 1. Tech Stack & Current Workflow Detected

A full scan of the codebase reveals the following architectural footprint:

### ⚙️ Backend Framework & Dependencies
* **Framework:** **Django 6.0.3** integrated with **Django REST Framework (DRF) 3.16.1**.
* **Python Runtime:** Python 3.13 (indicated by `NIXPACKS_PYTHON_VERSION` in [BackEnd/.env](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/.env)).
* **WSGI/ASGI Entry Points:** The project supports standard synchronous WSGI (`wms.wsgi.application`) and asynchronous ASGI (`wms.asgi.application`) gateways, defined in [wms/wsgi.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/wsgi.py) and [wms/asgi.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/asgi.py).

### 🗄️ Database Integration
* **Database Engine:** **PostgreSQL** hosted via **Supabase** (as identified by the `DATABASE_URL` pooler endpoint in [BackEnd/.env](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/.env#L5)).
* **ORM Connection:** Handled dynamically via `django-environ` using `env.db("DATABASE_URL")` within [wms/settings/settings.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/settings/settings.py#L97).

### 🛠️ Material Request Creation & Review Workflow
* **Database Model:** `MaterialRequest` in [inventory/models.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/models.py#L110) (table mapping: `inventory_materialrequest`).
* **API Entry Endpoint (Site B to Site A):** [MaterialRequestCreateView](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L281) handles incoming creations. It authenticates calls using the custom permission class [HasSiteBAPIKey](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L140) by verifying the `X-Site-B-API-Key` header.
* **Review/Approval Endpoint (Site A Manager):** [MaterialRequestReviewView](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L194) accepts `PATCH` updates from authorized warehouse managers, modifying the request status (`pending` ➡️ `approved` / `denied`) inside a database transaction block.

### ⏳ Background Task Execution Infrastructure
* **Current Status:** **Completely Missing**.
* **Findings:** While `REDIS_URL` is declared in [BackEnd/.env](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/.env#L6), the codebase **does not use Redis** or import any task queue libraries (like Celery or Django-Q) in [requirements.txt](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/requirements.txt).
* **Delivery Method:** Webhook POST calls are executed **synchronously** within the Django view request-response lifecycle using the `requests` library.

---

## 2. The Zero-Delay Webhook Audit (The Gap Analysis)

| Requirement | Implementation Status | Affected Files | Audit Findings & Vulnerabilities |
| :--- | :--- | :--- | :--- |
| **Asynchronous Execution (Zero-Delay)** | **Completely Missing** | [inventory/views.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L266-L271) | Outbound webhooks are triggered synchronously inside [MaterialRequestReviewView.update](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L266) and [MaterialRequestCreateView.perform_create](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L318). If the receiver (Site B) experiences latency, has cold starts, or is offline, it blocks the main Django thread for up to 5 seconds (the timeout limit), degrading portal response performance. |
| **HMAC SHA256 Signature Generation** | **Partially Implemented (Flawed)** | [inventory/views.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L150-L161) | The signing helper [_build_webhook_headers](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L150) uses `SITE_A_API_KEY` to sign payloads. However, `SITE_A_API_KEY` is **never loaded** in [settings.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/settings/settings.py). Consequently, `getattr(settings, "SITE_A_API_KEY", "")` defaults to an empty string (`""`), rendering the generated signature useless and highly vulnerable to spoofing. |
| **Timestamping & Replay Mitigation** | **Completely Missing** | [inventory/views.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L150) | The webhook header contains no timestamping key (`X-Webhook-Timestamp`). Attackers could intercept signed payloads and execute replay attacks against the receiver without needing to crack the signature. |
| **Failure & Retry Policy** | **Completely Missing** | [inventory/views.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L272-L273) | Requests are wrapped in a basic `try-except requests.RequestException: pass` block. If the receiving site is down, the notification is silently lost forever with no retry attempts, logging, or backoff logic. |
| **Environment Settings Configuration** | **Completely Missing** | [wms/settings/settings.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/settings/settings.py) | Custom settings variables like `WEBHOOK_SHARED_SECRET` or dedicated endpoint definitions are not defined in the settings module. |

---

## 3. The Missing Code Blocks (Production-Ready)

To remediate these gaps, we implement a robust cryptographic signer, an asynchronous background execution engine, and non-blocking view integration.

### Step 3.1: Settings Integration
Add configuration constants to [wms/settings/settings.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/wms/settings/settings.py) to securely retrieve environment variables:

```python
# wms/settings/settings.py

# Webhook Security Configuration
WEBHOOK_SHARED_SECRET = env("WEBHOOK_SHARED_SECRET", default="fallback-dev-secret-key-change-in-prod")
WEBHOOK_DEFAULT_TIMEOUT = env.int("WEBHOOK_DEFAULT_TIMEOUT", default=10)
```

---

### Step 3.2: The Signer Utility
Create a dedicated cryptographic helper in a new utility file, e.g., `BackEnd/inventory/webhooks.py`, to sign payloads with HMAC-SHA256 and append custom timestamp headers to prevent replay attacks.

```python
# inventory/webhooks.py
import hmac
import hashlib
import time
import json
from django.conf import settings

def sign_webhook_payload(payload_dict: dict) -> tuple[str, str]:
    """
    Computes an HMAC-SHA256 signature by concatenating a timestamp and JSON payload.
    Returns:
        tuple: (signature_hex, timestamp_string)
    """
    secret = getattr(settings, "WEBHOOK_SHARED_SECRET", "").encode("utf-8")
    timestamp = str(int(time.time()))  # Unix epoch timestamp
    
    # Serialize payload with sorted keys and minimal whitespace for standard serialization format
    serialized_payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
    
    # Concatenate timestamp and payload with a period delimiter to lock the hash parameters
    signing_message = f"{timestamp}.{serialized_payload}".encode("utf-8")
    
    signature = hmac.new(secret, signing_message, hashlib.sha256).hexdigest()
    return signature, timestamp
```

---

### Step 3.3: The Asynchronous Webhook Dispatcher
Since there is no external worker daemon (like Celery) configured, we will implement **two production-grade dispatcher architectures**:
* **Option A:** A thread pool execution approach using Python's built-in `ThreadPoolExecutor`. This works instantly with zero added server dependencies.
* **Option B:** A Celery-based worker task using the database/Redis cache queue configurations.

#### Option A: Thread Pool Executor (Zero-Dependency Async Dispatcher)
This approach handles non-blocking fire-and-forget dispatches on a dedicated worker pool with active exponential backoff retries.

```python
# inventory/webhooks.py (continued)
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Initialize thread pool for non-blocking HTTP dispatch
webhook_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="webhook_dispatcher")

def dispatch_webhook_async(url: str, payload: dict):
    """
    Submits a webhook POST task to the background thread pool immediately,
    releasing the HTTP view request cycle thread.
    """
    webhook_executor.submit(_send_webhook_sync, url, payload)

def _send_webhook_sync(url: str, payload: dict):
    """
    Worker task executing the synchronous post request with exponential backoff.
    """
    signature, timestamp = sign_webhook_payload(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
    }
    
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    timeout = getattr(settings, "WEBHOOK_DEFAULT_TIMEOUT", 10)
    
    # Exponential Backoff variables
    max_retries = 5
    initial_delay = 1.0  # 1 second initial delay
    backoff_factor = 2.0
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Dispatching Webhook to {url} [Attempt {attempt}/{max_retries}]")
            response = requests.post(
                url,
                data=serialized_payload,
                headers=headers,
                timeout=timeout
            )
            
            # Successful response check
            if 200 <= response.status_code < 300:
                logger.info(f"Webhook delivered successfully to {url} (HTTP {response.status_code})")
                return
                
            logger.warning(
                f"Recipient returned error status code {response.status_code}. "
                f"Retrying..."
            )
        except requests.RequestException as e:
            logger.error(f"Network error on attempt {attempt} to {url}: {str(e)}")
            
        # Calculate exponential sleep period before next execution run
        if attempt < max_retries:
            sleep_time = initial_delay * (backoff_factor ** (attempt - 1))
            time.sleep(sleep_time)
            
    logger.critical(f"Webhook delivery failed after {max_retries} retry attempts to {url}.")
```

#### Option B: Celery Task (If Celery is configured via `REDIS_URL`)
If you decide to configure Celery using the `REDIS_URL` in [BackEnd/.env](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/.env#L6), define this task instead:

```python
# inventory/tasks.py
from celery import shared_task
import requests
import json
import logging
from .webhooks import sign_webhook_payload

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    queue="webhooks"
)
def send_webhook_task(self, url: str, payload: dict):
    """
    Celery task representing Webhook client dispatch with automated retry capability.
    """
    signature, timestamp = sign_webhook_payload(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
    }
    
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    
    try:
        response = requests.post(url, data=serialized_payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook delivered to {url} (HTTP {response.status_code})")
    except requests.RequestException as exc:
        logger.warning(f"Failed webhook dispatch to {url}: {exc}. Retrying...")
        
        # Exponential backoff retry execution
        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)
```

---

### Step 3.4: View Integration

To integrate the new async dispatcher, modify [inventory/views.py](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py) by importing `dispatch_webhook_async` and replacing the blocking inline request blocks in the view logic.

#### Modifying [MaterialRequestReviewView](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L194) (Request Review Dispatch)

```python
# inventory/views.py
# (At the top of the file, import the async dispatcher helper)
from .webhooks import dispatch_webhook_async

# ... inside MaterialRequestReviewView class:
    def update(self, request, *args, **kwargs):
        # [Preserve all existing request review and transaction database logic]
        # ...
        
        # Replace lines 259–274 with:
        if instance.webhook_url and new_status in [MaterialRequest.STATUS_APPROVED, MaterialRequest.STATUS_DENIED]:
            payload = {
                "id": instance.id,
                "status": instance.status,
            }
            # Asynchronous delivery releases thread immediately
            dispatch_webhook_async(instance.webhook_url, payload)

        return Response(
            MaterialRequestSerializer(instance).data,
            status=status.HTTP_200_OK,
        )
```

#### Modifying [MaterialRequestCreateView](file:///c:/Users/user/Desktop/StockPad%28WM%29/BackEnd/inventory/views.py#L281) (Request Creation Immediate Sync)

```python
# ... inside MaterialRequestCreateView class:
    def perform_create(self, serializer):
        # [Preserve all user preferences matching logic]
        # ...
        
        # Save request instance
        instance = serializer.save()

        # Replace lines 311–325 with:
        if instance.webhook_url:
            payload = {
                "id": instance.id,
                "status": instance.status,
            }
            # Asynchronous execution for zero delay during creation
            dispatch_webhook_async(instance.webhook_url, payload)
```

---

## 4. Audit Summary & Recommendations

1. **Implement ThreadPoolExecutor Dispatch first:** Since there's no pre-configured Celery system running, **Option A** is the fastest path to achieve a zero-delay experience without adding database infrastructure complexity.
2. **Correct the Shared Key Configuration:** The current codebase is vulnerable due to referencing a non-existent settings property. We must load `WEBHOOK_SHARED_SECRET` in settings and update the signing utility to use it.
3. **Deploy the Replay Attack Prevention:** The signature must verify both payload data and timestamp headers to block third-party replay interceptions.
4. **Log Webhook Outcomes:** Implement structured logging to store delivery logs in case Website 1 / Website 2 integration issues occur during peak transaction runs.
