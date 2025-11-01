from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import generate_api_key, get_current_user, hash_api_key
from app.database.db import get_db
from app.models.models import APIKey, User
from app.schemas.schemas import APIKeyResponse, UserCreate, UserResponse

router = APIRouter()


@router.post("/admin/users/create", response_model=UserResponse)
async def create_user(
    user: UserCreate, db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Create a new user"""
    try:
        stmt = select(User).where(User.username == user.username)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
            )

        new_user = User(username=user.username, email=user.email)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at,
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/admin/users/{username}/keys/generate")
async def generate_key_for_user(
    username: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Generate an API key for a user"""
    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Generate key
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        api_key = APIKey(username=username, key_hash=key_hash)
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        # Only return the raw key once - user must save it
        return {
            "key_id": api_key.key_id,
            "api_key": raw_key,
            "username": username,
            "created_at": api_key.created_at,
            "note": "Save this API key securely. You won't be able to see it again.",
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/admin/users/{username}/keys")
async def list_keys_for_user(
    username: str, db: AsyncSession = Depends(get_db)
) -> list[APIKeyResponse]:
    """List all API keys for a user (shows api_id only, not the actual key)"""
    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        stmt = select(APIKey).where(APIKey.username == username)
        result = await db.execute(stmt)
        keys = result.scalars().all()
        return [APIKeyResponse.model_validate(k) for k in keys]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/admin/users/{username}/keys/{key_id}")
async def revoke_api_key(
    username: str, key_id: str, db: AsyncSession = Depends(get_db)
) -> Any:
    """Revoke an API key"""
    try:
        stmt = select(APIKey).where(
            APIKey.key_id == key_id, APIKey.username == username
        )
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )

        api_key.is_active = False
        await db.commit()
        return {"message": "API key revoked"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/admin/users/{username}")
async def delete_user(username: str, db: AsyncSession = Depends(get_db)) -> Any:
    """Delete a user and their API keys"""
    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Delete related API keys first
        api_keys_stmt = select(APIKey).where(APIKey.username == username)
        api_keys_result = await db.execute(api_keys_stmt)
        api_keys = api_keys_result.scalars().all()
        for api_key in api_keys:
            await db.delete(api_key)

        # Then delete the user
        await db.delete(user)
        await db.commit()
        return {"message": "User and associated API keys deleted"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/protected/profile")
async def get_user_profile(
    current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Get current user's profile"""
    user = select(User).where(User.username == current_user)
    result = await db.execute(user)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return {
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
