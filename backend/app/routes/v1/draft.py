from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.models import Draft, Inbox
from app.schemas.schemas import DraftCreate, DraftResponse, DraftUpdate

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("/", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: DraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> DraftResponse:
    """Create a new draft"""
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
        new_draft = Draft(**payload.dict())
        db.add(new_draft)
        await db.commit()
        await db.refresh(new_draft)
        return DraftResponse.model_validate(new_draft)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{draft_id}", status_code=status.HTTP_200_OK)
async def get_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> DraftResponse:
    """Retrieve a specific draft by ID"""
    try:
        project_id = current_user_info.get("project_id")
        draft_result = await db.execute(
            select(Draft).filter(
                Draft.id == draft_id, Draft.inbox.has(project_id=project_id)
            )
        )
        draft = draft_result.scalar_one_or_none()
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft {draft_id} not found",
            )
        return DraftResponse.model_validate(draft)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/{draft_id}", response_model=DraftResponse, status_code=status.HTTP_200_OK
)
async def update_draft(
    draft_id: UUID,
    payload: DraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> DraftResponse:
    """Update an existing draft"""
    try:
        project_id = current_user_info.get("project_id")
        draft_result = await db.execute(
            select(Draft).filter(
                Draft.id == draft_id, Draft.inbox.has(project_id=project_id)
            )
        )
        draft = draft_result.scalar_one_or_none()
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft {draft_id} not found",
            )
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(draft, key, value)
        await db.commit()
        await db.refresh(draft)
        return DraftResponse.model_validate(draft)
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
        project_id = current_user_info.get("project_id")
        draft_result = await db.execute(
            select(Draft).filter(
                Draft.id == draft_id, Draft.inbox.has(project_id=project_id)
            )
        )
        draft = draft_result.scalar_one_or_none()
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft {draft_id} not found",
            )
        await db.delete(draft)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
