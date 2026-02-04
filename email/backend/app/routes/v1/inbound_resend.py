import json
import logging
import os
from datetime import datetime, timezone

import resend
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.events import store_event_and_queue_webhooks
from app.core.models import (
    Attachment,
    EventType,
    Inbox,
    Message,
    MessageDirection,
    MessageStatus,
    Thread,
)
from app.database.db import get_db
from app.services.email_parser import EmailParser

router = APIRouter(prefix="/webhooks/resend", tags=["inbound"])

RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET")
RESEND_API_BASE = "https://api.resend.com"
resend.api_key = os.getenv("RESEND_API_KEY")

logger = logging.getLogger(__name__)

parser = EmailParser()


@router.post("/email-received", status_code=status.HTTP_200_OK)
async def handle_resend_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle inbound email webhook from Resend.
    - Verify webhook signature.
    - Parse email content.
    - Store Message and Attachments.
    - Emit internal event and queue user webhooks."""
    try:
        body_bytes = await request.body()
        headers = {k.lower(): v for k, v in request.headers.items()}

        if not RESEND_WEBHOOK_SECRET:
            logger.error("Webhook secret not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook secret not configured",
            )

        try:
            wh = Webhook(RESEND_WEBHOOK_SECRET)
            msg = wh.verify(body_bytes, headers)
            event = msg
        except WebhookVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature",
            )

        event_type_raw = (event or {}).get("type")
        event_type = (
            EventType.MESSAGE_RECEIVED
            if event_type_raw in ["email.received", "email.delivered", "email.sent"]
            else EventType.MESSAGE_UKNOWN
        )
        data = (event or {}).get("data") or {}

        resource_id = data.get("email_id") or data.get("id") or None
        if not resource_id:
            logger.error("Resource ID not found in event data")
            await store_event_and_queue_webhooks(
                db, None, None, EventType.MESSAGE_UKNOWN, {"event": event}
            )
            return Response(status_code=status.HTTP_200_OK)

        # Full email content
        received = resend.Emails.Receiving.get(email_id=resource_id)

        subject = received.get("subject") or ""
        text_body = received.get("text") or ""
        html_body = received.get("html") or ""
        headers = received.get("headers") or {}
        attachments = received.get("attachments") or []
        message_id = received.get("message_id") or ""
        from_address = received.get("from") or ""

        to_list = received.get("to") or []
        if len(to_list) != 1:
            logger.error("Multiple recipients not supported in this webhook handler")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple recipients not supported in this webhook handler",
            )

        inbox = None
        if to_list:
            to_email = to_list[0]
            result = await db.execute(select(Inbox).filter(Inbox.address == to_email))
            inbox = result.scalar_one_or_none()

        if not inbox:
            logger.error(f"Inbox not found for recipient: {to_list}")
            await store_event_and_queue_webhooks(
                db,
                None,
                None,
                EventType.MESSAGE_UKNOWN,
                {"resource_id": resource_id, "to": to_list},
            )
            return Response(status_code=status.HTTP_200_OK)

        reply_to = received.get("reply_to") or headers.get("reply_to") or []
        thread = None
        if reply_to:
            thread_result = await db.execute(
                select(Thread).filter(
                    Thread.inbox_id == inbox.id, Thread.subject == subject
                )
            )
            thread = thread_result.scalar_one_or_none()

        if not thread:
            thread = Thread(inbox_id=inbox.id, subject=subject)
            db.add(thread)
            await db.commit()
            await db.refresh(thread)
        else:
            thread.last_message_at = datetime.now(timezone.utc)
            await db.commit()

        message = Message(
            inbox_id=inbox.id,
            thread_id=thread.id,
            direction=MessageDirection.INBOUND,
            from_address=from_address,
            to_address=to_email,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
            message_id=message_id,
            status=MessageStatus.DELIVERED,
            provider_message_id=resource_id,
            delivered_at=datetime.now(timezone.utc),
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Store attachments
        for att in attachments:
            a = Attachment(
                message_id=message.id,
                file_name=att.get("filename") or att.get("name"),
                content_type=att.get("content_type") or att.get("mime_type"),
                storage_url=att.get("url") or att.get("download_url") or att.get("id"),
                size_bytes=att.get("size"),
            )
            db.add(a)
        await db.commit()

        # Parse content for OTPs, links, etc. and store parsed metadata
        parsed_data = {}
        try:
            parsed_data = await parser.parse(text=text_body, html=html_body)
        except Exception as e:
            logger.error(f"Parse error: {e}")
        message.parsed_metadata = json.dumps(parsed_data)
        await db.commit()

        # Emit internal event and queue user webhooks
        logger.info(f"Processing message: {message.id}")
        await store_event_and_queue_webhooks(
            db=db,
            inbox_id=inbox.id,
            message_id=message.id,
            event_type=event_type,
            payload={
                "message_id": str(message.id),
                "resource_id": resource_id,
                "sender": from_address,
                "subject": subject,
                # The "Gold" for the agent
                "extracted_data": {
                    "otp": parsed_data.otp_codes[0].code
                    if parsed_data.otp_codes
                    else None,
                    "verify_url": parsed_data.links[0].url
                    if parsed_data.links
                    else None,
                },
                "body_snippet": text_body[:200],
            },
        )
        return Response(status_code=status.HTTP_200_OK)

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Error processing inbound email webhook: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
