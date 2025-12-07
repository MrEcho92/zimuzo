import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.auth import get_current_user
from app.core.models import Inbox, Webhook
from app.core.schemas import WebhookCreate, WebhookResponse
from app.database.db import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    payload: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info=Depends(get_current_user),
) -> WebhookResponse:
    """Create a new webhook for a specific inbox"""
    try:
        project_id = current_user_info.get("project_id")
        inbox = await db.execute(
            select(Inbox).filter(
                Inbox.id == payload.inbox_id, Inbox.project_id == project_id
            )
        )
        inbox = inbox.scalar_one_or_none()
        if not inbox:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Inbox {payload.inbox_id} not found or access denied",
            )

        webhook = Webhook(
            inbox_id=payload.inbox_id,
            target_url=payload.target_url,
            secret_token=payload.secret_token if payload.secret_token else None,
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        return webhook
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error creating webhook: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[WebhookResponse])
async def list_webhooks(
    inbox_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_info=Depends(get_current_user),
) -> list[WebhookResponse]:
    """List all webhooks for a specific inbox"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Webhook)
            .join(Inbox)
            .filter(
                Webhook.inbox_id == inbox_id,
                Inbox.project_id == project_id,
            )
        )
        webhooks = result.scalars().all()
        return webhooks
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error listing webhooks: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
