import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.auth import get_current_user
from app.core.models import Inbox, Message, Tag, Thread
from app.core.schemas import MessageTagAssign, TagCreate, TagResponse
from app.database.db import get_db

router = APIRouter(prefix="/tags", tags=["tags"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> TagResponse:
    """Create a new tag"""
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

        # Check for duplicate tag name in this inbox
        result = await db.execute(
            select(Tag).filter(
                Tag.inbox_id == payload.inbox_id, Tag.name == payload.name
            )
        )
        existing_tag = result.scalar_one_or_none()
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag '{payload.name}' already exists in this inbox",
            )
        tag = Tag(
            name=payload.name,
            color=payload.color,
            inbox_id=payload.inbox_id,
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return TagResponse.model_validate(tag)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error creating tag: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/messages/{message_id}/assign", response_model=dict, status_code=status.HTTP_200_OK
)
async def assign_tag_to_message(
    message_id: UUID,
    tag_data: MessageTagAssign,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Assign a tag to a message"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Message)
            .options(selectinload(Message.tags))
            .filter(
                Message.id == message_id,
                Message.thread.has(Thread.inbox.has(project_id=project_id)),
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found",
            )

        # Verify tag exists and belongs to the same inbox as the message
        result = await db.execute(
            select(Tag)
            .join(Inbox)
            .join(Thread)
            .filter(
                Tag.id == tag_data.tag_id,
                Thread.id == message.thread_id,
                Tag.inbox_id == Thread.inbox_id,
                Inbox.project_id == project_id,
            )
        )
        tag = result.scalar_one_or_none()
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_data.tag_id} not found or doesn't belong to this inbox",
            )

        if tag in message.tags:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag '{tag.name}' is already assigned to this message",
            )

        # Assign tag
        message.tags.append(tag)
        await db.commit()

        await db.refresh(message, ["tags"])
        return {
            "message": "Tag assigned successfully",
            "message_id": str(message_id),
            "tag_id": str(tag_data.tag_id),
            "tag_name": tag.name,
        }
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error assigning tag to message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/", response_model=list[TagResponse], status_code=status.HTTP_200_OK)
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user_info: dict = Depends(get_current_user),
) -> list[TagResponse]:
    """List tags across all inboxes in the user's project"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(select(Tag).filter(Inbox.project_id == project_id))
        tags = result.scalars().all()
        return [TagResponse.model_validate(tag) for tag in tags]
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error listing tags: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/inbox/{inbox_id}",
    response_model=list[TagResponse],
    status_code=status.HTTP_200_OK,
)
async def get_inbox_tags(
    inbox_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    """Get all tags for an inbox"""
    try:
        project_id = current_user_info.get("project_id")

        result = await db.execute(
            select(Tag)
            .filter(Tag.inbox_id == inbox_id, Tag.inbox.has(project_id=project_id))
            .order_by(Tag.name)
        )
        tags = result.scalars().all()

        return [TagResponse.model_validate(tag) for tag in tags]

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error retrieving inbox tags: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/messages/{message_id}/tags",
    response_model=list[TagResponse],
    status_code=status.HTTP_200_OK,
)
async def get_message_tags(
    message_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    """Get all tags assigned to a message"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Message)
            .options(selectinload(Message.tags))
            .filter(
                Message.id == message_id,
                Message.thread.has(Thread.inbox.has(project_id=project_id)),
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found",
            )

        return [TagResponse.model_validate(tag) for tag in message.tags]

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error retrieving message tags: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/messages/{message_id}/unassign/{tag_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unassign_tag_from_message(
    message_id: UUID,
    tag_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a tag from a message"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Message)
            .options(selectinload(Message.tags))
            .filter(
                Message.id == message_id,
                Message.thread.has(Thread.inbox.has(project_id=project_id)),
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found",
            )

        # Find the tag in message's tags
        tag_to_remove = None
        for tag in message.tags:
            if tag.id == tag_id:
                tag_to_remove = tag
                break

        if not tag_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} is not assigned to this message",
            )

        # Remove tag
        message.tags.remove(tag_to_remove)
        await db.commit()

        await db.refresh(message, ["tags"])
        return None
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error unassigning tag from message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a tag"""
    try:
        project_id = current_user_info.get("project_id")

        result = await db.execute(
            select(Tag).filter(Tag.id == tag_id, Tag.inbox.has(project_id=project_id))
        )
        tag = result.scalar_one_or_none()
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Tag {tag_id} not found"
            )

        await db.delete(tag)
        await db.commit()

        return None
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error deleting tag: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
