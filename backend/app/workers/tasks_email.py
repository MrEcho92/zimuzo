import logging
import os
from datetime import datetime, timezone

import resend
from resend.exceptions import ResendError

from app.core.events import store_event_and_queue_webhooks_sync
from app.core.models import EventType, Inbox, Message, MessageStatus
from app.database.db import get_sync_session
from app.workers.celery_app import celery_app

resend.api_key = os.getenv("RESEND_API_KEY")

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=5)
def send_email_task(self, message_id: str) -> str:
    """
    Celery task: Send outbound email via Resend

    Flow:
    1. Fetch message from database
    2. Update status to 'sending'
    3. Call Resend API
    4. Update status based on result (sent/failed)
    5. Store event and queue webhook delivery
    """
    db = get_sync_session()
    msg = None
    inbox = None
    try:
        msg = db.query(Message).filter(Message.id == message_id).first()
        if not msg:
            logger.error(f"Message {message_id} not found")
            return f"Message {message_id} not found"

        inbox = db.query(Inbox).filter(Inbox.id == msg.inbox_id).first()
        if not inbox:
            logger.error(f"Inbox {msg.inbox_id} not found")
            return f"Inbox {msg.inbox_id} not found"

        msg.status = MessageStatus.SENDING
        db.commit()
        logger.info(f"Sending message {msg.id} via Resend")
        params: resend.Emails.SendParams = {
            "from": msg.from_address,
            "to": [msg.to_address],
            "subject": msg.subject,
            # prefer html if available - here we only have body_text
            "html": f"<pre>{msg.body_text}</pre>",
            "text": msg.body_text,
        }
        response = resend.Emails.send(params)

        logger.info(f"Email sent via Resend: {response}")

        msg.status = MessageStatus.SENT
        msg.provider_message_id = getattr(response, "id", None) or response.get("id")
        msg.sent_at = datetime.now(timezone.utc)
        db.commit()

        store_event_and_queue_webhooks_sync(
            db=db,
            inbox_id=inbox.id,
            message_id=msg.id,
            event_type=EventType.MESSAGE_SENT,
            payload={
                "message_id": str(msg.id),
                "resend_id": msg.provider_message_id,
            },
        )

        return f"Message {msg.id} sent successfully"
    except ResendError as exc:
        countdown = 2**self.request.retries if hasattr(self.request, "retries") else 5
        logger.warning(
            "ResendError for message %s: %s. Retrying in %ss",
            message_id,
            str(exc),
            countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error(
            "Error sending message %s: %s", message_id, str(exc), exc_info=True
        )
        if msg:
            msg.status = MessageStatus.FAILED
            db.commit()

        if inbox and msg:
            store_event_and_queue_webhooks_sync(
                db=db,
                inbox_id=inbox.id,
                message_id=msg.id,
                event_type=EventType.MESSAGE_FAILED,
                payload={"message_id": str(msg.id), "error": str(exc)},
            )

        raise
    finally:
        db.close()
