import uuid

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    created_at: str

    class Config:
        orm_mode = True


class APIKeyResponse(BaseModel):
    key_id: uuid.UUID
    username: str
    is_active: bool
    created_at: str
    last_used: str | None

    class Config:
        orm_mode = True
