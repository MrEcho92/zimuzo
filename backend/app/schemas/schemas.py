import uuid
from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    key_id: uuid.UUID
    username: str
    is_active: bool
    created_at: datetime
    last_used: datetime | None

    class Config:
        from_attributes = True
