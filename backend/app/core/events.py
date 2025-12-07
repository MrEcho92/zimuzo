import logging
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Event, Webhook
from app.workers.tasks_webhooks import deliver_webhook_task

logger = logging.getLogger(__name__)


async def store_event_and_queue_webhooks(
    db: AsyncSession,
    inbox_id: UUID,
    message_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
):
    """
    Store an event in the database and queue webhook deliveries
    for all active webhooks associated with the given inbox.
    """
    try:
        event = Event(
            event_type=event_type,
            inbox_id=inbox_id,
            message_id=message_id,
            payload=payload,
        )
        db.add(event)
        await db.commit()

        hooks = await db.execute(
            select(Webhook).filter(Webhook.inbox_id == inbox_id, Webhook.is_active)
        )
        hooks = hooks.scalars().all()
        for wh in hooks:
            # queue background delivery with Celery
            deliver_webhook_task.delay(
                wh.target_url, wh.secret_token or "", payload, str(event.id)
            )

    except Exception as exc:
        logger.error(f"Error storing event and queueing webhooks: {exc}")
        await db.rollback()
        raise exc
    finally:
        await db.close()
