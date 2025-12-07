from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.core.models import MessageDirection, MessageStatus


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

    model_config = ConfigDict(from_attributes=True)


class APIKeyResponse(BaseModel):
    key_id: UUID
    username: str
    is_active: bool
    created_at: datetime
    last_used: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InboxCreate(BaseModel):
    name: str
    custom_domain: Optional[str] = None


class InboxResponse(BaseModel):
    id: UUID
    name: str
    address: str
    custom_domain: Optional[str] = None
    created_at: datetime


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

    provider_message_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ThreadBase(BaseModel):
    subject: Optional[str] = None
    inbox_id: UUID


class ThreadResponse(ThreadBase):
    id: UUID
    last_message_at: Optional[datetime]
    created_at: datetime
    messages: Optional[List[MessageResponse]] = []

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class MessageTagAssign(BaseModel):
    tag_id: UUID


class AttachmentResponse(BaseModel):
    id: UUID
    message_id: UUID
    file_name: str
    content_type: Optional[str]
    storage_url: str
    size_bytes: Optional[int]
    checksum: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookCreate(BaseModel):
    inbox_id: UUID
    target_url: HttpUrl
    secret_token: str | None = None


class WebhookResponse(WebhookCreate):
    id: UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
