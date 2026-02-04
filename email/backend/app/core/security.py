import hashlib
import hmac
import json


def sign_webhook_payload(payload: dict, secret: str) -> str:
    """Generate HMAC SHA256 signature for the given payload using the secret."""
    if not secret:
        return ""
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_webhook(payload: str, signature: str, secret: str) -> bool:
    """Verify the HMAC SHA256 signature of the given payload using the secret."""
    if not secret:
        return False
    expected_signature = sign_webhook_payload(json.loads(payload), secret)

    return hmac.compare_digest(expected_signature, signature)
