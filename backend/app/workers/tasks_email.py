import os
from datetime import datetime, timezone

import resend
from celery import shared_task
from resend.exceptions import ResendError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import store_event_and_queue_webhooks
from app.core.models import EventType, Inbox, Message, MessageStatus
from app.database.db import AsyncSessionLocal

resend.api_key = os.getenv("RESEND_API_KEY")


@shared_task(bind=True, max_retries=5, default_retry_delay=5)
async def send_email_task(self, message_id: str) -> str:
    """
    Celery task: Send outbound email via Resend

    Flow:
    1. Fetch message from database
    2. Update status to 'sending'
    3. Call Resend API
    4. Update status based on result (sent/failed)
    5. Store event and queue webhook delivery
    """
    db: AsyncSession = AsyncSessionLocal()
    try:
        message_result = await db.execute(
            select(Message).filter(
                Message.id == message_id,
            )
        )
        message = message_result.scalar_one_or_none()
        if not message:
            return f"Message {message_id} not found"

        inbox_result = await db.execute(
            select(Inbox).filter(
                Inbox.id == message.inbox_id,
            )
        )
        inbox = inbox_result.scalar_one_or_none()
        if not inbox:
            return f"Inbox {message.inbox_id} not found"

        message.status = MessageStatus.SENDING
        await db.commit()

        params: resend.Emails.SendParams = {
            "from": message.from_address,
            "to": [message.to_address],
            "subject": message.subject,
            # prefer html if available - here we only have body_text
            "html": f"<pre>{message.body_text}</pre>",
        }
        response = resend.Emails.send(params)
        message.status = MessageStatus.SENT
        message.provider_message_id = getattr(response, "id", None) or response.get(
            "id"
        )
        message.sent_at = datetime.now(timezone.utc)
        await db.commit()

        store_event_and_queue_webhooks(
            db=db,
            inbox_id=inbox.id,
            message_id=message.id,
            event_type=EventType.MESSAGE_SENT.value,
            payload={
                "message_id": str(message.id),
                "resend_id": getattr(response, "id", None) or response.get("id"),
            },
        )

        return f"Message {message_id} sent successfully"

    except ResendError as exc:
        # Retry with exponential backoff
        try:
            countdown = 2**self.request.retries
        except Exception:
            countdown = 5
        self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        message.status = MessageStatus.FAILED
        await db.commit()
        store_event_and_queue_webhooks(
            db=db,
            inbox_id=inbox.id,
            message_id=message.id,
            event_type=EventType.MESSAGE_FAILED.value,
            payload={"message_id": str(message.id), "error": str(exc)},
        )
        raise exc
    finally:
        db.close()
