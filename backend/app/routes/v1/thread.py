from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.models import Thread
from app.schemas.schemas import ThreadResponse

router = APIRouter(prefix="/threads", tags=["threads"])


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
            select(Thread).filter(
                Thread.inbox_id == inbox_id, Thread.inbox.has(project_id=project_id)
            )
        )
        threads = result.scalars().all()
        return [ThreadResponse.model_validate(thread) for thread in threads]
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{thread_id}", response_model=ThreadResponse, status_code=status.HTTP_200_OK)
async def get_thread(
    thread_id: str,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Retrieve a specific thread by ID"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Thread).filter(Thread.id == thread_id, Thread.inbox.has(project_id=project_id))
        )
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Thread {thread_id} not found"
            )
        return ThreadResponse.model_validate(thread)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
