from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.models import Inbox
from app.schemas.schemas import InboxCreate, InboxResponse

router = APIRouter(prefix="/inboxes", tags=["inboxes"])


@router.post(
    "/create", response_model=InboxResponse, status_code=status.HTTP_201_CREATED
)
async def create_inbox(
    inbox: InboxCreate,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InboxResponse:
    """Create a new inbox"""
    try:
        domain = inbox.custom_domain or "zimuzo.dev"
        address = f"{inbox.name}@{domain}"
        project_id = current_user_info.get("project_id")
        existing_inbox = await db.execute(
            select(Inbox).filter(
                Inbox.address == address, Inbox.project_id == project_id
            )
        )
        if existing_inbox.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inbox with this address already exists",
            )
        new_inbox = Inbox(
            name=inbox.name,
            address=address,
            custom_domain=inbox.custom_domain,
            project_id=project_id,
        )
        db.add(new_inbox)
        await db.commit()
        await db.refresh(new_inbox)
        return InboxResponse(
            id=new_inbox.id,
            name=new_inbox.name,
            address=new_inbox.address,
            custom_domain=new_inbox.custom_domain,
            created_at=new_inbox.created_at,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/", response_model=list[InboxResponse], status_code=status.HTTP_200_OK)
async def list_inboxes(
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InboxResponse]:
    """Retrieve all inboxes"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Inbox).filter(Inbox.project_id == project_id, Inbox.active)
        )
        inboxes = result.scalars().all()
        return [
            InboxResponse(
                id=inbox.id,
                name=inbox.name,
                address=inbox.address,
                custom_domain=inbox.custom_domain,
                active=inbox.active,
                created_at=inbox.created_at,
            )
            for inbox in inboxes
        ]
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{inbox_id}", response_model=InboxResponse, status_code=status.HTTP_200_OK)
async def get_inbox(
    inbox_id: str,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InboxResponse:
    """Retrieve a specific inbox by ID"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Inbox).filter(
                Inbox.id == inbox_id, Inbox.project_id == project_id, Inbox.active
            )
        )
        inbox = result.scalar_one_or_none()
        if not inbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inbox {inbox_id} not found",
            )

        return InboxResponse(
            id=inbox.id,
            name=inbox.name,
            address=inbox.address,
            custom_domain=inbox.custom_domain,
            created_at=inbox.created_at,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{inbox_id}", status_code=status.HTTP_200_OK)
async def delete_inbox(
    inbox_id: str,
    current_user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a specific inbox by ID"""
    try:
        project_id = current_user_info.get("project_id")
        result = await db.execute(
            select(Inbox).filter(
                Inbox.id == inbox_id, Inbox.project_id == project_id, Inbox.active
            )
        )
        inbox = result.scalar_one_or_none()
        if not inbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inbox not found"
            )

        inbox.active = False
        await db.commit()
        return {"message": "Inbox deleted successfully"}
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
