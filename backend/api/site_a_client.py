import logging

import requests
from django.conf import settings

logger = logging.getLogger('api')


class SiteAError(Exception):
    pass


def _wm_headers() -> dict:
    """Standard outbound headers for all WM API requests."""
    return {"X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY}


def fetch_materials_catalog():
    """GET the WM Website's live material catalog (no engineer filter).

    Returns a list of dicts: [{"id", "name", "quantity", "unit"}, ...]
    """
    resp = requests.get(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/materials/catalog/",
        headers=_wm_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _normalize_wm_catalog_item(item: dict) -> dict:
    """Normalize flat WM catalog item fields for PE frontend and chatbot."""
    qty = item.get("quantity_available")
    if qty is None:
        qty = item.get("quantity", 0)
    cat_name = item.get("category_name")
    if not cat_name:
        cat = item.get("category")
        if isinstance(cat, dict):
            cat_name = cat.get("name", "")
        elif isinstance(cat, str):
            cat_name = cat
        else:
            cat_name = ""
    stock_status = item.get("stock_status") or item.get("status") or ""
    return {
        **item,
        "quantity": item.get("quantity") if item.get("quantity") is not None else qty,
        "quantity_available": qty,
        "category_name": cat_name,
        "stock_status": stock_status,
    }


def _normalize_wm_catalog(items: list) -> list:
    return [_normalize_wm_catalog_item(i) for i in items if isinstance(i, dict)]


def fetch_wm_catalog_for_engineer(engineer_email: str) -> list:
    """GET the WM Website's engineer-scoped material catalog.

    Calls GET /api/inventory/engineer-catalog/?email=<user_email> so the WM
    server returns only materials belonging to the Warehouse Manager who has
    whitelisted this engineer.

    Args:
        engineer_email: The PE engineer's email address (from request.user.email).

    Returns:
        list of normalized material dicts with flat quantity, stock_status,
        and category_name fields.

    Raises:
        SiteAError: if the WM site returns a non-2xx response.
        requests.exceptions.RequestException: on network-level failures.
    """
    engineer_email = engineer_email.lower().strip()
    resp = requests.get(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/engineer-catalog/",
        params={"email": engineer_email},
        headers=_wm_headers(),
        timeout=10,
    )
    if not resp.ok:
        raise SiteAError(
            f"WM catalog HTTP {resp.status_code} for {engineer_email}: {resp.text[:500]}"
        )
    data = resp.json()
    if isinstance(data, list):
        items = data
    else:
        items = data.get("results", data.get("materials", []))
    return _normalize_wm_catalog(items)


_WM_STATUS_ENDPOINTS = (
    "/api/inventory/connections/check/",
    "/api/inventory/engineers/status/",
)


def check_engineer_status_on_wm(engineer_email: str) -> dict:
    """Check whether an engineer is whitelisted / active on the WM site.

    Probes WM connection status via GET .../?email=<user_email> and normalises
    the response to {"connected": bool, "manager_name": str | None}.

    Uses response.json().get("connected") is True as the authoritative signal.
    As a final fallback, attempts a catalog fetch: if materials are returned,
    the engineer is considered connected.

    Args:
        engineer_email: The PE engineer's email address.

    Returns:
        dict with keys "connected" (bool) and "manager_name" (str or None).
        Never raises — failures are silently mapped to {"connected": False, ...}.
    """
    engineer_email = engineer_email.lower().strip()
    headers = _wm_headers()
    for path in _WM_STATUS_ENDPOINTS:
        try:
            resp = requests.get(
                f"{settings.WM_WEBSITE_BASE_URL}{path}",
                params={"email": engineer_email},
                headers=headers,
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                is_connected = data.get("connected") is True
                manager = (
                    data.get("manager_name")
                    or data.get("manager")
                    or data.get("warehouse_manager")
                    or None
                )
                return {"connected": is_connected, "manager_name": manager}
            if resp.status_code in (404, 403):
                return {"connected": False, "manager_name": None}
        except requests.exceptions.RequestException:
            continue

    # Catalog fallback: if the WM site returns materials, engineer is connected.
    try:
        items = fetch_wm_catalog_for_engineer(engineer_email)
        if items:
            return {"connected": True, "manager_name": None}
    except Exception:
        pass

    return {"connected": False, "manager_name": None}


_WM_REQUEST_ENDPOINT = "/api/inventory/requests/create/"


def _log_wm_request_sync_error(status_code, response_body: str) -> None:
    msg = f"[WM Request Sync Error]: status {status_code} response {response_body[:1000]}"
    print(msg)
    logger.error(msg)


def resolve_wm_material_id(material, engineer_email: str):
    """Resolve the WM material PK for outbound request sync.

    Uses Material.site_a_material_id when set; otherwise looks up the engineer's
    WM catalog by material name and unit.
    """
    if material.site_a_material_id:
        return material.site_a_material_id

    engineer_email = (engineer_email or "").lower().strip()
    if not engineer_email:
        return None

    try:
        catalog = fetch_wm_catalog_for_engineer(engineer_email)
    except Exception as exc:
        logger.warning(
            "WM catalog lookup failed while resolving material_id for '%s': %s",
            material.name,
            exc,
        )
        return None

    name_key = (material.name or "").strip().lower()
    unit_key = (material.unit or "").strip().lower()

    for item in catalog:
        item_name = (item.get("name") or "").strip().lower()
        item_unit = (item.get("unit") or "").strip().lower()
        if item_name == name_key and (not unit_key or item_unit == unit_key):
            wm_id = item.get("id") or item.get("site_a_material_id")
            if wm_id is not None:
                return int(wm_id)

    for item in catalog:
        if (item.get("name") or "").strip().lower() == name_key:
            wm_id = item.get("id") or item.get("site_a_material_id")
            if wm_id is not None:
                return int(wm_id)

    return None


def resolve_wm_requester_id(engineer_email: str):
    """Resolve the WM engineer PK (requester_id) for outbound request sync."""
    engineer_email = (engineer_email or "").lower().strip()
    if not engineer_email:
        return None

    headers = _wm_headers()
    for path in _WM_STATUS_ENDPOINTS:
        try:
            resp = requests.get(
                f"{settings.WM_WEBSITE_BASE_URL}{path}",
                params={"email": engineer_email},
                headers=headers,
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                requester_id = data.get("engineer_id") or data.get("requester_id")
                if requester_id is not None:
                    return int(requester_id)
        except requests.exceptions.RequestException:
            continue
    return None


def submit_request_to_site_a(
    *,
    material_id,
    quantity,
    requester_email,
    justification="",
    webhook_url=None,
):
    """POST a new material request to the WM Website (inventory_materialrequest).

    WM requires ``material`` (WM material PK) and ``requester_id`` (WM engineer PK).
    The engineer PK is resolved from the connections/status endpoint using email.

    Args:
        material_id:     The WM Website's own material PK (Material.site_a_material_id).
        quantity:        Integer/Decimal quantity being requested.
        requester_email: Email of the PE engineer who raised the request.
        justification:   Free-text reason for the request (maps to WM ``reason``).
        webhook_url:     Full public URL of our receiver webhook endpoint.

    Returns:
        dict — WM JSON response including the created request "id".

    Raises:
        SiteAError: on non-2xx HTTP responses from WM or missing requester_id.
        requests.exceptions.RequestException: on network failures.
    """
    requester_email = (requester_email or "").lower().strip()
    reason = justification or ""
    requester_id = resolve_wm_requester_id(requester_email)
    if requester_id is None:
        msg = f"Could not resolve WM requester_id for engineer {requester_email}"
        _log_wm_request_sync_error("missing_requester_id", msg)
        raise SiteAError(msg)

    payload = {
        "material": material_id,
        "requester_id": requester_id,
        "quantity": quantity,
        "reason": reason,
        "requester_email": requester_email,
        "webhook_url": webhook_url or settings.SITE_B_PUBLIC_WEBHOOK_URL,
    }
    url = f"{settings.WM_WEBSITE_BASE_URL}{_WM_REQUEST_ENDPOINT}"
    headers = _wm_headers()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.ok:
            return resp.json()
        _log_wm_request_sync_error(resp.status_code, resp.text)
        raise SiteAError(
            f"WM request HTTP {resp.status_code} at {_WM_REQUEST_ENDPOINT}: {resp.text[:500]}"
        )
    except requests.exceptions.RequestException as exc:
        _log_wm_request_sync_error("network", str(exc))
        raise
