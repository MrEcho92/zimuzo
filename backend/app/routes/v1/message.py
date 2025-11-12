from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.auth import get_current_user
from app.database.db import get_db
from app.core.models import Inbox, Message, MessageDirection, MessageStatus, Thread
from app.schemas.schemas import MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> MessageResponse:
    """Send a new message"""
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

        # TODO: Integrate with actual email sending service here
        # Future: queue async mail send via Celery or AWS SES here
        return MessageResponse.model_validate(message)
    except SQLAlchemyError as e:
        await db.rollback()
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
