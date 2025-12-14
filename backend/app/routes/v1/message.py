import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.auth import get_current_user
from app.core.events import store_event_and_queue_webhooks
from app.core.models import (
    EventType,
    Inbox,
    Message,
    MessageDirection,
    MessageStatus,
    Thread,
)
from app.core.schemas import MessageCreate, MessageResponse
from app.database.db import get_db
from app.workers.tasks_email import send_email_task

router = APIRouter(prefix="/messages", tags=["messages"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> MessageResponse:
    """Send a new message

    Agent calls endpoint to send an email.
    1. Validate Inbox.
    2. Save Message (queued).
    3. Enqueue Celery Task.

    """
    try:
        project_id = current_user_info.get("project_id")
        inbox_result = await db.execute(
            select(Inbox).filter(
                Inbox.id == payload.inbox_id, Inbox.project_id == project_id
            )
        )
        inbox = inbox_result.scalar_one_or_none()
        if not inbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inbox {payload.inbox_id} not found",
            )
        if payload.thread_id:
            thread_result = await db.execute(
                select(Thread).filter(
                    Thread.id == payload.thread_id, Thread.inbox_id == inbox.id
                )
            )
            thread = thread_result.scalar_one_or_none()
            if not thread:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Thread {payload.thread_id} not found in Inbox {payload.inbox_id}",
                )
        else:
            thread = Thread(
                inbox_id=inbox.id,
                subject=payload.subject,
                created_at=datetime.now(timezone.utc),
            )
            db.add(thread)
            await db.flush()
        message = Message(
            inbox_id=inbox.id,
            thread_id=thread.id,
            from_address=inbox.address,
            to_address=payload.to_address,
            subject=payload.subject,
            body_text=payload.body_text,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.QUEUED,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(message)
        thread.last_message_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(message)

        # Emit queued event
        await store_event_and_queue_webhooks(
            db=db,
            inbox_id=inbox.id,
            message_id=message.id,
            event_type=EventType.MESSAGE_QUEUED,
            payload={
                "message_id": str(message.id),
                "status": MessageStatus.QUEUED,
                "from": message.from_address,
                "to": message.to_address,
                "subject": message.subject,
            },
        )

        # Enqueue Celery task
        send_email_task.delay(message_id=str(message.id))

        return MessageResponse.model_validate(message)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error sending message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{message_id}", response_model=MessageResponse, status_code=status.HTTP_200_OK
)
async def get_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> MessageResponse:
    """Retrieve a specific message by ID"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Message).filter(
                Message.id == message_id,
                Message.inbox.has(project_id=project_id),
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found",
            )
        return MessageResponse.model_validate(message)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error retrieving message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
