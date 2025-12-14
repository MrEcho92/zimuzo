import hashlib
import hmac
import json


def sign_webhook_payload(payload: dict, secret: str) -> str:
    """Generate HMAC SHA256 signature for the given payload using the secret."""
    if not secret:
        return ""
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
