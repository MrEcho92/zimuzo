import os
from datetime import datetime, timezone

import requests
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

router = APIRouter(prefix="/webhooks/resend", tags=["inbound"])

RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_API_BASE = "https://api.resend.com"


@router.post("/email-received", status_code=status.HTTP_200_OK)
async def handle_resend_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        # Read raw body
        body_bytes = await request.body()
        headers = {k.lower(): v for k, v in request.headers.items()}

        # Verify signature using svix
        if not RESEND_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook secret not configured",
            )

        try:
            wh = Webhook(RESEND_WEBHOOK_SECRET)
            # wh.verify expects bytes and headers dict with svix headers
            msg = wh.verify(body_bytes, headers)
            # `msg` is the parsed JSON payload (verified)
            event = msg  # typically dict
        except WebhookVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature",
            )

        # event will usually contain a reference to the received email (resource id)
        # Example shapes vary: check for common keys
        # try: data.id, or event['data']['id'], or event['id']
        resource_id = None
        if isinstance(event, dict):
            data = event.get("data") or {}
            resource_id = data.get("id") or data.get("received_email_id")
            if not resource_id:
                resource_id = event.get("id") or event.get("resource")

        if not resource_id:
            # Can't find resource id — store event and return
            # (some webhooks include full payload but Resend typically uses resource id)
            store_event_and_queue_webhooks(
                db, None, None, "resend.webhook.unknown", event
            )
            return Response(status_code=status.HTTP_200_OK)

        # Fetch full email content from Resend Received Emails API
        url = f"{RESEND_API_BASE}/received_emails/{resource_id}"
        resp = requests.get(url, auth=("api", RESEND_API_KEY))
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch received email from Resend",
            )

        received = resp.json()
        # Received structure expected to include:
        # from, to, subject, text, html, headers, attachments (if any)
        # adapt to actual fields
        # mail_from = None
        # mail_to = None
        subject = received.get("subject") or ""
        text_body = received.get("text") or ""
        html_body = received.get("html") or ""
        headers = received.get("headers") or {}
        attachments = received.get("attachments") or []

        # Determine intended inbox by to-address (match one of your inbox addresses)
        # example: received['to'] might be list of {address: 'qa-agent@agentmailx.dev'}
        to_list = received.get("to") or received.get("recipients") or []
        inbox = None
        for r in to_list:
            addr = None
            if isinstance(r, dict):
                addr = r.get("email") or r.get("address") or r.get("to")
            else:
                addr = r
            if not addr:
                continue
            inbox = await db.execute(select(Inbox).filter(Inbox.address == addr))
            inbox = inbox.scalar_one_or_none()
            if inbox:
                break
        if not inbox:
            # Unknown recipient: store as orphan event
            store_event_and_queue_webhooks(
                db,
                None,
                None,
                "message.received.unmapped",
                {"resource_id": resource_id, "to": to_list},
            )
            return Response(status_code=status.HTTP_200_OK)

        # Find or create thread by In-Reply-To or subject heuristics
        in_reply_to = received.get("in_reply_to") or headers.get("in-reply-to")
        thread = None
        if in_reply_to:
            thread_result = await db.execute(
                select(Thread).filter(
                    Thread.inbox_id == inbox.id, Thread.subject == subject
                )
            )
            thread = thread_result.scalar_one_or_none()
        if not thread:
            # create new thread
            thread = Thread(inbox_id=inbox.id, subject=subject)
            db.add(thread)
            await db.commit()
            await db.refresh(thread)
        else:
            thread.last_message_at = datetime.now(timezone.utc)
            await db.commit()

        # Create Message record
        message = Message(
            thread_id=thread.id,
            inbox_id=inbox.id,
            direction=MessageDirection.INBOUND,
            from_address=(
                (received.get("from") or {}).get("email")
                if isinstance(received.get("from"), dict)
                else received.get("from")
            ),
            to_address=",".join(
                [r.get("email") if isinstance(r, dict) else r for r in to_list]
            ),
            subject=subject,
            body_text=text_body,
            body_html=html_body,
            status=MessageStatus.DELIVERED,
            provider_message_id=resource_id,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Store attachments metadata (if any)
        for att in attachments:
            # attachments fields may include id, url, filename, content_type, size_bytes
            a = Attachment(
                message_id=message.id,
                file_name=att.get("filename") or att.get("name"),
                content_type=att.get("content_type") or att.get("mime_type"),
                storage_url=att.get("url") or att.get("download_url") or att.get("id"),
                size_bytes=att.get("size"),
            )
            db.add(a)
        await db.commit()

        # TODO: Optionally perform parsing: OTP extraction / link detection here (call your parser)
        # e.g. otp = extract_otp(text_body) ; store metadata / labels

        # Emit internal event and queue user webhooks
        store_event_and_queue_webhooks(
            db=db,
            inbox_id=inbox.id,
            message_id=message.id,
            event_type=EventType.MESSAGE_RECEIVED.value,
            payload={
                "message_id": str(message.id),
                "resource_id": resource_id,
                # "sender": from_email,
                # "subject": subject,
                # "extracted_data": extracted_data,  # The "Gold" for the agent
                # "body_snippet": text_body[:200],
            },
        )
        return Response(status_code=status.HTTP_200_OK)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
