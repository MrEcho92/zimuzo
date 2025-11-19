import httpx
from celery import shared_task

from app.core.security import sign_webhook_payload


@shared_task(bind=True, max_retries=8)
async def deliver_webhook_task(
    self, target_url: str, secret_token: str, payload: dict, event_id: str = None
) -> str:
    """
    Celery task: Deliver a webhook payload to the target URL with optional signing.
    Retries up to 8 times with exponential backoff.
    """
    try:
        signature = sign_webhook_payload(payload, secret_token) if secret_token else ""
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            r = client.post(target_url, json=payload, headers=headers)
            r.raise_for_status()
        return "delivered"
    except Exception as exc:
        backoff = 2**self.request.retries
        raise self.retry(exc=exc, countdown=backoff)
