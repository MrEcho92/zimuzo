import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contants import API_KEY_HEADER_NAME
from app.core.models import APIKey, User
from app.database.db import get_db

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME, description="API Key for authentication"
)


def hash_api_key(key: str):
    """Hash API key using SHA256"""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key():
    """Generate a random API key"""
    return "sk_" + secrets.token_urlsafe(32)


async def verify_api_key(api_key: str, db: AsyncSession) -> str:
    """Verify API key"""
    key_hash = hash_api_key(api_key)

    api_key_record = (
        await db.execute(
            select(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active)
        )
    ).scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    # Check if user is active
    user = await db.execute(
        select(User)
        .options(selectinload(User.projects))
        .filter(User.username == api_key_record.username)
    )
    user = user.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    # Update last_used timestamp
    api_key_record.last_used = datetime.now(timezone.utc)
    db.add(api_key_record)
    await db.commit()

    return {
        "username": api_key_record.username,
        "project_id": user.projects.id,
    }


async def get_current_user(
    api_key: str = Depends(api_key_header), db: AsyncSession = Depends(get_db)
) -> str:
    """Verify API key and return current user"""
    return await verify_api_key(api_key, db)
