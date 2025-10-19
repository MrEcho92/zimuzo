from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import generate_api_key, get_current_user, hash_api_key
from app.database.db import get_db
from app.models.models import APIKey, User
from app.schemas.schemas import APIKeyResponse, UserCreate, UserResponse

router = APIRouter()


@router.post("/admin/users/create", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user
    :param user: UserCreate
    :param db: Database session
    :return: UserResponse
    """
    try:
        existing_user = await db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
            )

        new_user = User(username=user.username, email=user.email)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/admin/users/{username}/keys/generate")
async def generate_key_for_user(username: str, db: Session = Depends(get_db)) -> dict:
    """Generate an API key for a user
    :param username: str
    :param db: Database session
    :return: dict
    """
    try:
        user = await db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/admin/users/{username}/keys")
async def list_keys_for_user(username: str, db: Session = Depends(get_db)) -> list[APIKeyResponse]:
    """List all API keys for a user (shows api_id only, not the actual key)
    :param username: str
    :param db: Database session
    :return: list of dicts
    """
    try:
        user = await db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        keys = await db.query(APIKey).filter(APIKey.username == username).all()
        return [APIKeyResponse.model_validate(k) for k in keys]
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/admin/users/{username}/keys/{key_id}")
async def revoke_api_key(username: str, key_id: str, db: Session = Depends(get_db)) -> Any:
    """Revoke an API key
    :param username: str
    :param key_id: str
    :param db: Database session
    :return: dict
    """
    try:
        api_key = (
            await db.query(APIKey)
            .filter(APIKey.key_id == key_id, APIKey.username == username)
            .first()
        )

        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        api_key.is_active = False
        await db.commit()
        return {"message": "API key revoked"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/protected/profile")
async def get_user_profile(
    current_user: str = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Get current user's profile"""
    user = await db.query(User).filter(User.username == current_user).first()
    return {
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
