import json
import os
from typing import Any, Dict

import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# TODO: review code and adapt accordingly and add other llm options
async def parse_email_content(text_body: str, system_prompt: str) -> Dict[str, Any]:
    """Parse email content with Claude API to extract OTP, links, etc."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""
                            Parse this email and extract key information in JSON format:
                            - otp_codes: list of any OTP/verification codes
                            - verification_links: list of verification URLs
                            - important_info: any other important information
                            - sender_intent: what the sender wants

                            Email content:
                            {text_body}

                            Return only valid JSON.
                            """,
                        }
                    ],
                },
            )

            if response.status_code == 200:
                result = response.json()
                content = result["content"][0]["text"]

                # Try to extract JSON from response
                try:
                    return json.loads(content)
                except Exception as e:
                    print(f"Raw content: {e}")
                    # If not valid JSON, return raw content
                    return {"raw_parsed": content}
            else:
                return {"error": "Failed to parse"}

        except Exception as e:
            print(f"Error parsing with AI: {e}")
            return {"error": str(e)}
