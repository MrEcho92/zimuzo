from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    project_name: str

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    key_id: UUID
    username: str
    is_active: bool
    created_at: datetime
    last_used: datetime | None

    class Config:
        from_attributes = True


class InboxCreate(BaseModel):
    name: str
    custom_domain: Optional[str] = None


class InboxResponse(BaseModel):
    id: UUID
    name: str
    address: str
    custom_domain: Optional[str] = None
    created_at: datetime


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class MessageCreate(BaseModel):
    inbox_id: UUID
    thread_id: Optional[UUID] = None
    to_address: EmailStr
    subject: str
    body_text: str


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    inbox_id: UUID
    from_address: str
    to_address: str
    subject: str
    body_text: Optional[str]
    direction: MessageDirection
    status: MessageStatus
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class ThreadBase(BaseModel):
    subject: Optional[str] = None
    inbox_id: UUID


class ThreadResponse(ThreadBase):
    id: UUID
    last_message_at: Optional[datetime]
    created_at: datetime
    messages: Optional[List[MessageResponse]] = []

    class Config:
        from_attributes = True


class DraftCreate(BaseModel):
    inbox_id: UUID
    thread_id: Optional[UUID] = None
    to_address: EmailStr
    subject: str
    body_text: str


class DraftUpdate(BaseModel):
    to_address: Optional[EmailStr] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None


class DraftResponse(BaseModel):
    id: UUID
    inbox_id: UUID
    thread_id: Optional[UUID] = None
    to_address: str
    subject: str
    body_text: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#888888", pattern="^#[0-9A-Fa-f]{6}$")


class TagCreate(TagBase):
    inbox_id: UUID


class TagResponse(TagBase):
    id: UUID
    inbox_id: UUID
    name: str
    color: str
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageTagAssign(BaseModel):
    tag_id: UUID


class AttachmentCreate(BaseModel):
    message_id: UUID
    file_name: str
    file_url: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None


class AttachmentResponse(BaseModel):
    id: UUID
    message_id: UUID
    file_name: str
    file_url: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True
