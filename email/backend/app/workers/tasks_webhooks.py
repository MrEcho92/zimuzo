import logging

import httpx

from app.core.security import sign_webhook_payload
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=8, default_retry_delay=2)
def deliver_webhook_task(
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
        with httpx.Client(timeout=10) as client:
            r = client.post(target_url, json=payload, headers=headers)
            r.raise_for_status()

        logger.info(
            f"Webhook delivered successfully to {target_url} "
            f"(event_id: {event_id}, status: {r.status_code})"
        )

        return "delivered"

    except httpx.HTTPStatusError as exc:
        backoff = 2**self.request.retries if hasattr(self.request, "retries") else 2
        logger.warning(
            f"Webhook delivery failed to {target_url} "
            f"(event_id: {event_id}, status: {exc.response.status_code}, "
            f"attempt: {self.request.retries + 1}/{self.max_retries}). "
            f"Retrying in {backoff}s"
        )
        raise self.retry(exc=exc, countdown=backoff)

    except httpx.RequestError as exc:
        backoff = 2**self.request.retries if hasattr(self.request, "retries") else 2
        logger.warning(
            f"Webhook delivery request error to {target_url} "
            f"(event_id: {event_id}, error: {str(exc)}, "
            f"attempt: {self.request.retries + 1}/{self.max_retries}). "
            f"Retrying in {backoff}s"
        )
        raise self.retry(exc=exc, countdown=backoff)
    except Exception as exc:
        backoff = 2**self.request.retries if hasattr(self.request, "retries") else 2
        logger.error(
            f"Unexpected error delivering webhook to {target_url} "
            f"(event_id: {event_id}): {str(exc)}"
        )
        raise self.retry(exc=exc, countdown=backoff)
