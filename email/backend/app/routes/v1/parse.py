import logging

from fastapi import APIRouter, HTTPException, status

from app.core.schemas import ParseEmailRequest, ParseEmailResponse
from app.services.email_parser import EmailParser

router = APIRouter(prefix="/parse", tags=["parser"])

logger = logging.getLogger(__name__)

parser = EmailParser()


@router.post("/parse", response_model=ParseEmailResponse)
async def parse_email_content(request: ParseEmailRequest):
    """
    Parse email content to extract OTP codes and confirmation links

    This endpoint uses regex patterns first for fast extraction,
    then falls back to LLM (Claude) for complex cases.

    Example:
    POST /parse
    {
        "text": "Your verification code is: 123456\\n\\nClick here: https://example.com/verify/abc",
        "html": "<p>Your code: <strong>123456</strong></p>",
        "use_llm_fallback": true
    }

    Returns:
    {
        "otp_codes": [
            {
                "code": "123456",
                "confidence": 0.95,
                "context": "Your verification code is: 123456",
                "method": "regex"
            }
        ],
        "links": [
            {
                "url": "https://example.com/verify/abc",
                "link_type": "verification",
                "confidence": 0.95,
                "text": "Click here",
                "method": "regex"
            }
        ],
        "sender_intent": "verification",
        "requires_action": true,
        "summary": "Found 1 OTP code(s): 123456. Found 1 action link(s). Intent: verification",
        "metadata": {
            "regex_otp_count": 1,
            "regex_link_count": 1,
            "used_llm": false
        }
    }
    """
    try:
        result = await parser.parse(
            text=request.text,
            html=request.html,
            use_llm_fallback=request.use_llm_fallback,
        )

        from dataclasses import asdict

        return ParseEmailResponse(
            otp_codes=[asdict(otp) for otp in result.otp_codes],
            links=[
                {**asdict(link), "link_type": link.link_type.value}
                for link in result.links
            ],
            sender_intent=result.sender_intent,
            requires_action=result.requires_action,
            summary=result.summary,
            metadata=result.metadata or {},
        )
    except Exception as e:
        logger.error("Error parsing email content: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse email content",
        )


@router.post("/parse/batch")
async def parse_emails_batch(emails: list[ParseEmailRequest]):
    """
    Parse multiple emails in batch

    Example:
    POST /parse/batch
    [
        {"text": "Your code is 123456"},
        {"text": "Verify here: https://example.com/verify"}
    ]

    Returns array of parse results
    """
    results = []
    for email in emails:
        try:
            result = await parser.parse(
                text=email.text,
                html=email.html,
                use_llm_fallback=email.use_llm_fallback,
            )
            from dataclasses import asdict

            results.append(
                ParseEmailResponse(
                    otp_codes=[asdict(otp) for otp in result.otp_codes],
                    links=[
                        {**asdict(link), "link_type": link.link_type.value}
                        for link in result.links
                    ],
                    sender_intent=result.sender_intent,
                    requires_action=result.requires_action,
                    summary=result.summary,
                    metadata=result.metadata or {},
                )
            )
        except Exception as e:
            logger.error("Error parsing email content in batch: %s", str(e))
            results.append(
                HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to parse email content",
                )
            )
    return results
