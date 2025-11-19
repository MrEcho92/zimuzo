from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.auth import get_current_user
from app.contants import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE
from app.core.models import Attachment, Message, Thread
from app.core.schemas import AttachmentResponse
from app.database.db import get_db
from app.services.message_storage import storage_service

router = APIRouter(prefix="/attachments", tags=["attachments"])


# TODO: Integrate object storage (AWS S3, GCS, or Supabase Storage) for attachments.
@router.post(
    "/", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED
)
async def upload_attachment(
    message_id: UUID,
    file: UploadFile = File(...),
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Upload an attachment to a message"""
    try:
        project_id = current_user_info.get("project_id")

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
            )

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{file.content_type}' not allowed",
            )

        result = await db.execute(
            select(Message).filter(
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

        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({MAX_FILE_SIZE} bytes)",
            )

        attachment_id = uuid4()

        # TODO: Change to use Amazon S3, Google Cloud Storage, etc
        storage_url, size_bytes, checksum = await storage_service.save_file(
            file, message_id, attachment_id
        )

        # Create attachment record
        attachment = Attachment(
            id=attachment_id,
            message_id=message_id,
            file_name=file.filename,
            content_type=file.content_type,
            storage_url=storage_url,
            size_bytes=size_bytes,
            checksum=checksum,
        )

        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)

        return AttachmentResponse.model_validate(attachment)
    except SQLAlchemyError as e:
        await db.rollback()
        # Clean up file if database operation fails
        if "storage_url" in locals():
            storage_service.delete_file(storage_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}",
        )


@router.get(
    "/message/{message_id}",
    response_model=list[AttachmentResponse],
    status_code=status.HTTP_200_OK,
)
async def list_attachments_for_message(
    message_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AttachmentResponse]:
    """List all attachments for a message"""
    try:
        project_id = current_user_info.get("project_id")

        result = await db.execute(
            select(Message)
            .options(selectinload(Message.attachments))
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

        return [
            AttachmentResponse.model_validate(attachment)
            for attachment in message.attachments
        ]
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: UUID,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an attachment"""
    try:
        project_id = current_user_info.get("project_id")

        result = await db.execute(
            select(Attachment).filter(
                Attachment.id == attachment_id,
                Attachment.message.has(
                    Message.thread.has(Thread.inbox.has(project_id=project_id))
                ),
            )
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found",
            )

        storage_service.delete_file(attachment.storage_url)

        # Delete database record
        await db.delete(attachment)
        await db.commit()

        return None

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
