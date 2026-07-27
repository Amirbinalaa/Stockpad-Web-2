import hashlib
import hmac

from django.conf import settings


def get_webhook_hmac_secrets():
    """Currently valid HMAC secrets for inbound Site A webhooks (primary + optional rotation secret)."""
    secrets = []
    primary = getattr(settings, "WEBHOOK_SHARED_SECRET", None) or getattr(
        settings, "SITE_A_WEBHOOK_SECRET", None
    )
    if primary:
        secrets.append(primary)

    secondary = getattr(settings, "WEBHOOK_SHARED_SECRET_NEW", None) or getattr(
        settings, "SITE_A_WEBHOOK_SECRET_NEW", None
    )
    if secondary and secondary not in secrets:
        secrets.append(secondary)

    return secrets


def verify_webhook_hmac_signature(received_sig: str, timestamp: str, raw_body_str: str) -> bool:
    """
    Verify X-Webhook-Signature against any currently valid shared secret.
    Site A signs: HMAC-SHA256(secret, f"{timestamp}.{raw_json_body}")
    """
    if not received_sig:
        return False

    signing_message = f"{timestamp}.{raw_body_str}".encode("utf-8")
    for secret in get_webhook_hmac_secrets():
        if not secret:
            continue
        expected_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(received_sig, expected_sig):
            return True
    return False
