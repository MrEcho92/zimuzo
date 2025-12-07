import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.auth import get_current_user
from app.core.models import Thread
from app.core.schemas import ThreadResponse
from app.database.db import get_db

router = APIRouter(prefix="/threads", tags=["threads"])

logger = logging.getLogger(__name__)


@router.get("/", response_model=list[ThreadResponse], status_code=status.HTTP_200_OK)
async def list_threads(
    inbox_id: UUID = Query(...),
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadResponse]:
    """Retrieve all threads for a specific inbox"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Thread)
            .options(
                selectinload(Thread.messages),
                selectinload(Thread.drafts),
                selectinload(Thread.inbox),
            )
            .filter(
                Thread.inbox_id == inbox_id, Thread.inbox.has(project_id=project_id)
            )
        )
        threads = result.scalars().all()
        return [ThreadResponse.model_validate(thread) for thread in threads]
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error retrieving threads: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{thread_id}", response_model=ThreadResponse, status_code=status.HTTP_200_OK
)
async def get_thread(
    thread_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Retrieve a specific thread by ID"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Thread)
            .options(
                selectinload(Thread.messages),
                selectinload(Thread.drafts),
                selectinload(Thread.inbox),
            )
            .filter(Thread.id == thread_id, Thread.inbox.has(project_id=project_id))
        )
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found",
            )
        return ThreadResponse.model_validate(thread)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error retrieving thread: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
