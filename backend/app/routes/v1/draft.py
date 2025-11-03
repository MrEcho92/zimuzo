from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database.db import get_db
from app.schemas.schemas import DraftCreate, DraftUpdate

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_draft(
    draft: DraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
):
    """Create a new draft"""
    try:
        pass
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{draft_id}", status_code=status.HTTP_200_OK)
async def get_draft(draft_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve a specific draft by ID"""
    try:
        pass
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{draft_id}", status_code=status.HTTP_200_OK)
async def update_draft(
    draft_id: UUID,
    draft: DraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
):
    """Update an existing draft"""
    try:
        pass
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
):
    """Delete a draft"""
    try:
        pass
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
