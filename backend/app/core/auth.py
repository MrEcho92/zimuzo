import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.contants import API_KEY_HEADER_NAME
from app.database.db import get_db
from app.models.models import APIKey, User

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME, description="API Key for authentication"
)


def hash_api_key(key: str):
    """Hash API key using SHA256"""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key():
    """Generate a random API key"""
    return "sk_" + secrets.token_urlsafe(32)


async def verify_api_key(api_key: str, db: Session) -> str:
    """Verify API key and return username"""
    key_hash = hash_api_key(api_key)

    api_key_record = (
        await db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active)
        .first()
    )

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    # Check if user is active
    user = await db.query(User).filter(User.username == api_key_record.username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    # Update last_used timestamp
    api_key_record.last_used = datetime.now(timezone.utc)
    await db.commit()

    return api_key_record.username


async def get_current_user(
    api_key: str = Depends(api_key_header), db: Session = Depends(get_db)
) -> str:
    """Verify API key and return current user"""
    return verify_api_key(api_key, db)
