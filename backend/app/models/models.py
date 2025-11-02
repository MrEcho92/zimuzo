import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.db import Base


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, enum.Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class User(Base):
    """Represents a user"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # One-to-one relationship with Project
    project = relationship(
        "Project", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class APIKey(Base):
    """Represents an API key associated with a user"""

    __tablename__ = "api_keys"

    key_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    username = Column(String, index=True)
    key_hash = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used = Column(DateTime, nullable=True)


class Project(Base):
    "Represents an organisation"

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="projects")
    inboxes = relationship(
        "Inbox", back_populates="project", cascade="all, delete-orphan"
    )


class Inbox(Base):
    """Represents a unique agent-owned mailbox"""

    __tablename__ = "inboxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), unique=True, nullable=False)
    custom_domain = Column(String(255), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project", back_populates="inboxes")
    threads = relationship(
        "Thread", back_populates="inbox", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="inbox", cascade="all, delete-orphan"
    )
    drafts = relationship("Draft", back_populates="inbox", cascade="all, delete-orphan")


class Thread(Base):
    """Represents a logical conversation container inside an inbox"""

    __tablename__ = "threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    subject = Column(String(255))
    last_message_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    inbox = relationship("Inbox", back_populates="threads")
    messages = relationship(
        "Message", back_populates="thread", cascade="all, delete-orphan"
    )


class Message(Base):
    """Represents individual inbound/outbound emails inside a thread"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    direction = Column(Enum(MessageDirection), nullable=False)
    from_address = Column(String(255))
    to_address = Column(String(255))
    subject = Column(String(255))
    body_text = Column(Text)
    body_html = Column(Text)
    message_id = Column(String(255))  # Original Message-ID header
    in_reply_to = Column(String(255))  # In-Reply-To header
    sent_at = Column(DateTime)
    status = Column(Enum(MessageStatus), default=MessageStatus.RECEIVED)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    thread = relationship("Thread", back_populates="messages")
    inbox = relationship("Inbox", back_populates="messages")
    attachments = relationship(
        "Attachment", back_populates="message", cascade="all, delete-orphan"
    )


class Draft(Base):
    """Represents unsent or in-progress outbound messages"""

    __tablename__ = "drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=True)
    to_address = Column(String(255))
    subject = Column(String(255))
    body_text = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    inbox = relationship("Inbox", back_populates="drafts")
    thread = relationship("Thread", back_populates="drafts")


message_tags = Table(
    "message_tags",
    Base.metadata,
    Column(
        "message_id", UUID(as_uuid=True), ForeignKey("messages.id"), primary_key=True
    ),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    """Represents user or system-generated tags"""

    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20))
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", secondary=message_tags, back_populates="tags")


class Attachment(Base):
    """Represents binary files (images, PDFs, etc.) linked to messages"""

    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    content_type = Column(String(100))
    storage_url = Column(Text, nullable=False)
    size_bytes = Column(Integer)
    checksum = Column(String(64))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("Message", back_populates="attachments")
