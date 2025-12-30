import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


class LinkType(str, Enum):
    VERIFICATION = "verification"
    RESET_PASSWORD = "reset_password"
    CONFIRMATION = "confirmation"
    UNSUBSCRIBE = "unsubscribe"
    MAGIC_LINK = "magic_link"
    GENERIC = "generic"


@dataclass
class OTPCode:
    """Extracted OTP code with metadata
    code: str - The OTP code itself
    confidence: float - Confidence score (0.0 to 1.0)
    context: str - Surrounding text for context
    position: int - Character position in the text
    method: str - Method used for extraction ("regex" or "llm")
    """

    code: str
    confidence: float
    context: str
    position: int
    method: str


@dataclass
class ConfirmationLink:
    """Extracted confirmation/verification link

    url: str - The URL of the link
    link_type: LinkType - Type of link (verification, reset password, etc.)
    confidence: float - Confidence score (0.0 to 1.0)
    text: str - Link text/anchor text
    context: str - Surrounding text
    method: str - Method used for extraction ("regex" or "llm")
    """

    url: str
    link_type: LinkType
    confidence: float
    text: str
    context: str
    method: str


@dataclass
class ParseResult:
    """Complete parsing result"""

    otp_codes: list[OTPCode]
    links: list[ConfirmationLink]
    sender_intent: Optional[str] = None
    requires_action: bool = False
    summary: Optional[str] = None
    metadata: Dict[str, Any] = None


class EmailParser:
    """
    Email content parser with regex + LLM fallback

    Strategy:
    1. Try regex patterns first (fast, reliable for common formats)
    2. If regex finds nothing or low confidence, use LLM
    3. Combine results with deduplication
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmailParser, cls).__new__(cls)
        return cls._instance

    def __init__(self, anthropic_api_key: str = None):
        self.anthropic_api_key = anthropic_api_key or ANTHROPIC_API_KEY

        # OTP Regex Patterns (ordered by specificity)
        self.otp_patterns = [
            # Explicit OTP mentions with various formats
            (r"(?:otp|code|verification code|passcode|pin)[\s:]+([0-9]{4,8})", 0.95),
            (r"your (?:otp|code|verification code) is[\s:]+([0-9]{4,8})", 0.95),
            (r"([0-9]{6})\s+is your (?:otp|code|verification code)", 0.95),
            # Common formats with context
            (r"(?:use|enter|type)[\s]+(?:code|otp)?[\s:]+([0-9]{4,8})", 0.90),
            (r"([0-9]{6})\s+to (?:verify|confirm|complete)", 0.90),
            # Standalone codes with high probability context
            (
                r"(?:^|\n|\s)([0-9]{6})(?:\n|$|\s)(?=.*(?:verify|login|security|authentication))",
                0.85,
            ),
            (r"<strong[^>]*>([0-9]{4,8})</strong>", 0.85),  # HTML bold codes
            (r"<b>([0-9]{4,8})</b>", 0.85),
            # Generic 6-digit codes (lower confidence)
            (r"\b([0-9]{6})\b", 0.60),
            # 4-digit codes (lower confidence, many false positives)
            (r"\b([0-9]{4})\b", 0.40),
        ]

        # Link patterns for verification/confirmation
        self.link_patterns = [
            # Verification links
            (r"https?://[^\s]+/verify[^\s]*", LinkType.VERIFICATION, 0.95),
            (r"https?://[^\s]+/confirm[^\s]*", LinkType.CONFIRMATION, 0.95),
            (r"https?://[^\s]+/activate[^\s]*", LinkType.VERIFICATION, 0.95),
            (r"https?://[^\s]+/validation[^\s]*", LinkType.VERIFICATION, 0.90),
            # Password reset
            (r"https?://[^\s]+/reset[^\s]*", LinkType.RESET_PASSWORD, 0.95),
            (r"https?://[^\s]+/password[^\s]*", LinkType.RESET_PASSWORD, 0.85),
            # Magic links / one-time access
            (r"https?://[^\s]+/auth[^\s]*token[^\s]*", LinkType.MAGIC_LINK, 0.90),
            (r"https?://[^\s]+/magic[^\s]*", LinkType.MAGIC_LINK, 0.90),
            # Unsubscribe
            (r"https?://[^\s]+/unsubscribe[^\s]*", LinkType.UNSUBSCRIBE, 0.95),
            # Generic HTTPS links (low confidence)
            (r'https?://[^\s<>"]+', LinkType.GENERIC, 0.50),
        ]

    def extract_otps_regex(self, text: str) -> list[OTPCode]:
        """Extract OTP codes using regex patterns"""
        otps = []
        seen_codes = set()

        for pattern, base_confidence in self.otp_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                code = match.group(1) if match.groups() else match.group(0)

                # Skip if already found
                if code in seen_codes:
                    continue

                # Get context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                # Adjust confidence based on context
                confidence = self._adjust_otp_confidence(code, context, base_confidence)

                # Only include if confidence is reasonable
                if confidence >= 0.5:
                    otps.append(
                        OTPCode(
                            code=code,
                            confidence=confidence,
                            context=context,
                            position=match.start(),
                            method="regex",
                        )
                    )
                    seen_codes.add(code)

        # Sort by confidence
        otps.sort(key=lambda x: x.confidence, reverse=True)

        return otps

    def _adjust_otp_confidence(
        self, code: str, context: str, base_confidence: float
    ) -> float:
        """Adjust OTP confidence based on context and code characteristics"""
        confidence = base_confidence
        context_lower = context.lower()

        # Boost confidence for strong indicators
        strong_indicators = [
            "verification",
            "verify",
            "otp",
            "one-time",
            "passcode",
            "authentication",
            "two-factor",
            "2fa",
            "security code",
            "confirmation code",
        ]
        if any(indicator in context_lower for indicator in strong_indicators):
            confidence = min(1.0, confidence + 0.1)

        # Reduce confidence for weak indicators
        weak_indicators = ["invoice", "order", "reference", "tracking"]
        if any(indicator in context_lower for indicator in weak_indicators):
            confidence *= 0.7

        # Boost 6-digit codes (most common OTP length)
        if len(code) == 6:
            confidence = min(1.0, confidence + 0.05)

        # Reduce confidence for 4-digit codes (many false positives)
        if len(code) == 4:
            confidence *= 0.6

        # Reduce confidence for codes with repeated digits
        if len(set(code)) <= 2:  # e.g., "1111", "1212"
            confidence *= 0.5

        return confidence

    def extract_links_regex(self, text: str) -> list[ConfirmationLink]:
        """Extract confirmation/verification links using regex"""
        links = []
        seen_urls = set()

        for pattern, link_type, base_confidence in self.link_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                url = match.group(0)

                # Clean up URL (remove trailing punctuation)
                url = re.sub(r"[.,;!?)\]}>]+$", "", url)

                # Skip if already found
                if url in seen_urls:
                    continue

                # Get context
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end].strip()

                # Try to find link text (for HTML)
                link_text = self._extract_link_text(text, match.start(), url)

                # Adjust confidence based on context
                confidence = self._adjust_link_confidence(
                    url, link_text, context, base_confidence, link_type
                )

                if confidence >= 0.5:
                    links.append(
                        ConfirmationLink(
                            url=url,
                            link_type=link_type,
                            confidence=confidence,
                            text=link_text,
                            context=context,
                            method="regex",
                        )
                    )
                    seen_urls.add(url)

        # Sort by confidence
        links.sort(key=lambda x: x.confidence, reverse=True)

        return links

    def _extract_link_text(self, text: str, position: int, url: str) -> str:
        """Extract anchor text for a link"""
        # Look for <a> tag pattern
        pattern = rf'<a[^>]*href=["\']?{re.escape(url)}["\']?[^>]*>(.*?)</a>'
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

        if match:
            return match.group(1).strip()

        # Look for nearby text (simple heuristic)
        start = max(0, position - 30)
        end = position
        nearby_text = text[start:end].strip()

        # Common link text patterns
        link_text_patterns = [
            r"(verify|confirm|click here|activate|reset)",
            r"(complete|continue|get started)",
        ]

        for pattern in link_text_patterns:
            match = re.search(pattern, nearby_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def _adjust_link_confidence(
        self,
        url: str,
        link_text: str,
        context: str,
        base_confidence: float,
        link_type: LinkType,
    ) -> float:
        """Adjust link confidence based on context, link text, and URL"""
        confidence = base_confidence
        context_lower = context.lower()
        url_lower = url.lower()
        link_text_lower = link_text.lower() if link_text else ""

        # Boost for strong action words in context
        action_words = [
            "click",
            "verify",
            "confirm",
            "activate",
            "complete",
            "continue",
            "get started",
            "sign in",
        ]
        if any(word in context_lower for word in action_words):
            confidence = min(1.0, confidence + 0.1)

        # Boost for action words in link text (strong signal)
        if link_text_lower and any(word in link_text_lower for word in action_words):
            confidence = min(1.0, confidence + 0.15)

        # Boost for descriptive link text matching link type
        if link_text_lower:
            if link_type == LinkType.VERIFICATION and any(
                word in link_text_lower for word in ["verify", "confirm", "activate"]
            ):
                confidence = min(1.0, confidence + 0.1)
            elif link_type == LinkType.RESET_PASSWORD and any(
                word in link_text_lower for word in ["reset", "password", "forgot"]
            ):
                confidence = min(1.0, confidence + 0.1)
            elif link_type == LinkType.MAGIC_LINK and any(
                word in link_text_lower for word in ["sign in", "login", "access"]
            ):
                confidence = min(1.0, confidence + 0.1)

        # Reduce confidence for generic link text
        generic_link_text = ["click here", "here", "link", "this link"]
        if link_text_lower and link_text_lower in generic_link_text:
            confidence *= 0.9

        # Boost for matching link type in URL path
        if link_type != LinkType.GENERIC:
            if link_type.value in url_lower:
                confidence = min(1.0, confidence + 0.05)

        # Reduce for generic links without clear purpose
        if link_type == LinkType.GENERIC:
            has_action_context = any(word in context_lower for word in action_words)
            has_action_text = link_text_lower and any(
                word in link_text_lower for word in action_words
            )
            if not has_action_context and not has_action_text:
                confidence *= 0.5

        # Boost for HTTPS
        if url.startswith("https://"):
            confidence = min(1.0, confidence + 0.05)

        return confidence

    async def extract_otps_llm(self, text: str) -> list[OTPCode]:
        """Extract OTP codes using LLM (fallback)"""
        if not self.anthropic_api_key:
            return []

        # Sanitize input: limit length to prevent abuse
        MAX_TEXT_LENGTH = 10000  # ~2500 words
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "\n[... truncated for safety]"

        # Remove any potential prompt injection attempts
        text = (
            text.replace("</user>", "")
            .replace("<assistant>", "")
            .replace("Human:", "")
            .replace("Assistant:", "")
        )

        # Use XML tags to clearly separate instructions from user data
        prompt = f"""Extract all OTP codes, verification codes, or passcodes from the email content below.

            Instructions:
            - Return ONLY a JSON array, nothing else
            - Each object should have: code (numeric string), confidence (0.0-1.0), context (max 50 chars)
            - Only include actual verification codes, NOT order numbers, invoice numbers, tracking numbers, or dates
            - If no codes found, return empty array: []

            Example output format:
            [{"code": "123456", "confidence": 0.95, "context": "Your verification code is 123456"}]

            <email_content>
            {text}
            </email_content>

            JSON array:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "temperature": 0,  # Deterministic output
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["content"][0]["text"]

                    # Remove markdown code blocks if present
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    # Validate it's actually JSON array
                    if not content.startswith("["):
                        print(f"LLM returned non-array response: {content[:100]}")
                        return []

                    codes_data = json.loads(content)

                    # Validate response structure
                    if not isinstance(codes_data, list):
                        print(f"LLM response not a list: {type(codes_data)}")
                        return []

                    # Limit number of codes to prevent abuse
                    MAX_CODES = 10
                    codes_data = codes_data[:MAX_CODES]

                    validated_codes = []
                    for item in codes_data:
                        # Validate each code object
                        if not isinstance(item, dict):
                            continue

                        code = str(item.get("code", ""))

                        # Validate code format: only digits, reasonable length
                        if not code.isdigit() or len(code) < 4 or len(code) > 8:
                            continue

                        confidence = float(item.get("confidence", 0.8))
                        # Clamp confidence to valid range
                        confidence = max(0.0, min(1.0, confidence))

                        context = str(item.get("context", ""))[
                            :100
                        ]  # Limit context length

                        validated_codes.append(
                            OTPCode(
                                code=code,
                                confidence=confidence,
                                context=context,
                                position=-1,
                                method="llm",
                            )
                        )

                    return validated_codes

        except json.JSONDecodeError as e:
            print(f"LLM OTP extraction - JSON parse error: {e}")
        except Exception as e:
            print(f"LLM OTP extraction error: {e}")

        return []

    async def extract_links_llm(self, text: str) -> list[ConfirmationLink]:
        """Extract links using LLM (fallback)"""
        if not self.anthropic_api_key:
            return []

        # Sanitize input: limit length to prevent abuse
        MAX_TEXT_LENGTH = 10000
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "\n[... truncated for safety]"

        # Remove potential prompt injection
        text = (
            text.replace("</user>", "")
            .replace("<assistant>", "")
            .replace("Human:", "")
            .replace("Assistant:", "")
        )

        # Use XML tags to separate instructions from user data
        prompt = f"""Extract all verification, confirmation, or action links from the email content below.

            Instructions:
            - Return ONLY a JSON array, nothing else
            - Each object should have: url, link_type, confidence (0.0-1.0), text, context (max 100 chars)
            - link_type must be one of: verification, confirmation, reset_password, magic_link, unsubscribe, generic
            - Focus on actionable links that require user interaction
            - Skip footer links, social media links, privacy policy links unless specifically for verification
            - If no links found, return empty array: []

            Example output format:
            [{"url": "https://example.com/verify/abc", "link_type": "verification", "confidence": 0.95, "text": "Verify email", "context": "Click to verify"}]

            <email_content>
            {text}
            </email_content>

            JSON array:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "temperature": 0,  # Deterministic output
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["content"][0]["text"]

                    # Parse JSON response with safety checks
                    import json

                    # Remove markdown code blocks if present
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    # Validate it's actually JSON array
                    if not content.startswith("["):
                        print(f"LLM returned non-array response: {content[:100]}")
                        return []

                    links_data = json.loads(content)

                    # Validate response structure
                    if not isinstance(links_data, list):
                        print(f"LLM response not a list: {type(links_data)}")
                        return []

                    # Limit number of links to prevent abuse
                    MAX_LINKS = 20
                    links_data = links_data[:MAX_LINKS]

                    validated_links = []
                    for item in links_data:
                        # Validate each link object
                        if not isinstance(item, dict):
                            continue

                        url = str(item.get("url", ""))

                        # Validate URL format and protocol
                        if not url.startswith(("http://", "https://")):
                            continue

                        # Limit URL length to prevent abuse
                        if len(url) > 2000:
                            continue

                        # Validate link_type is one of allowed values
                        link_type_str = item.get("link_type", "generic")
                        try:
                            link_type = LinkType(link_type_str)
                        except ValueError:
                            link_type = LinkType.GENERIC

                        confidence = float(item.get("confidence", 0.8))
                        # Clamp confidence to valid range
                        confidence = max(0.0, min(1.0, confidence))

                        text = str(item.get("text", ""))[:200]  # Limit text length
                        context = str(item.get("context", ""))[
                            :200
                        ]  # Limit context length

                        validated_links.append(
                            ConfirmationLink(
                                url=url,
                                link_type=link_type,
                                confidence=confidence,
                                text=text,
                                context=context,
                                method="llm",
                            )
                        )

                    return validated_links

        except json.JSONDecodeError as e:
            print(f"LLM link extraction - JSON parse error: {e}")
        except Exception as e:
            print(f"LLM link extraction error: {e}")

        return []

    async def parse(
        self, text: str, html: str = None, use_llm_fallback: bool = True
    ) -> ParseResult:
        """
        Parse email content with regex + LLM fallback

        Args:
            text: Plain text email content
            html: Optional HTML content
            use_llm_fallback: Whether to use LLM if regex finds nothing

        Returns:
            ParseResult with extracted OTPs and links
        """
        # Combine text and html for better parsing
        combined_text = text
        if html:
            clean_html = re.sub(r"<[^>]+>", " ", html)
            combined_text = f"{text}\n\n{clean_html}"

        # 1. Try regex first (fast)
        regex_otps = self.extract_otps_regex(combined_text)
        regex_links = self.extract_links_regex(combined_text)

        # 2. Decide if LLM fallback is needed
        needs_llm = use_llm_fallback and (
            len(regex_otps) == 0
            or (regex_otps and max(otp.confidence for otp in regex_otps) < 0.7)
            or len(regex_links) == 0
        )

        llm_otps = []
        llm_links = []

        if needs_llm:
            llm_otps = await self.extract_otps_llm(combined_text)
            llm_links = await self.extract_links_llm(combined_text)

        # 3. Combine and deduplicate results
        all_otps = self._merge_otps(regex_otps, llm_otps)
        all_links = self._merge_links(regex_links, llm_links)

        # 4. Determine sender intent and action required
        sender_intent = self._determine_intent(combined_text, all_otps, all_links)
        requires_action = len(all_otps) > 0 or any(
            link.link_type != LinkType.UNSUBSCRIBE for link in all_links
        )

        # 5. Generate summary
        summary = self._generate_summary(all_otps, all_links, sender_intent)

        return ParseResult(
            otp_codes=all_otps,
            links=all_links,
            sender_intent=sender_intent,
            requires_action=requires_action,
            summary=summary,
            metadata={
                "regex_otp_count": len(regex_otps),
                "regex_link_count": len(regex_links),
                "llm_otp_count": len(llm_otps),
                "llm_link_count": len(llm_links),
                "used_llm": needs_llm,
            },
        )

    def _merge_otps(
        self, regex_otps: list[OTPCode], llm_otps: list[OTPCode]
    ) -> list[OTPCode]:
        """Merge and deduplicate OTP codes"""
        seen = {}

        # Add regex results first
        for otp in regex_otps:
            seen[otp.code] = otp

        for otp in llm_otps:
            if otp.code not in seen or otp.confidence > seen[otp.code].confidence:
                seen[otp.code] = otp

        # Sort by confidence
        result = list(seen.values())
        result.sort(key=lambda x: x.confidence, reverse=True)

        return result

    def _merge_links(
        self, regex_links: list[ConfirmationLink], llm_links: list[ConfirmationLink]
    ) -> list[ConfirmationLink]:
        """Merge and deduplicate links"""
        seen = {}

        # Add regex results first
        for link in regex_links:
            seen[link.url] = link

        # Add LLM results if not found or higher confidence
        for link in llm_links:
            if link.url not in seen or link.confidence > seen[link.url].confidence:
                seen[link.url] = link

        # Sort by confidence
        result = list(seen.values())
        result.sort(key=lambda x: x.confidence, reverse=True)

        return result

    def _determine_intent(
        self, text: str, otps: list[OTPCode], links: list[ConfirmationLink]
    ) -> str:
        """Determine sender's intent"""
        text_lower = text.lower()

        if otps:
            if "login" in text_lower or "sign in" in text_lower:
                return "authentication"
            if "verify" in text_lower or "confirm" in text_lower:
                return "verification"
            if "reset" in text_lower or "password" in text_lower:
                return "password_reset"
            return "authentication"

        if links:
            primary_link = links[0]
            if primary_link.link_type == LinkType.VERIFICATION:
                return "verification"
            if primary_link.link_type == LinkType.RESET_PASSWORD:
                return "password_reset"
            if primary_link.link_type == LinkType.CONFIRMATION:
                return "confirmation"
            if primary_link.link_type == LinkType.MAGIC_LINK:
                return "magic_link_auth"

        return "unknown"

    def _generate_summary(
        self, otps: list[OTPCode], links: list[ConfirmationLink], intent: str
    ) -> str:
        """Generate human-readable summary"""
        parts = []

        if otps:
            codes_str = ", ".join(otp.code for otp in otps[:3])
            parts.append(f"Found {len(otps)} OTP code(s): {codes_str}")

        if links:
            action_links = [
                link for link in links if link.link_type != LinkType.UNSUBSCRIBE
            ]
            if action_links:
                parts.append(f"Found {len(action_links)} action link(s)")

        if intent and intent != "unknown":
            parts.append(f"Intent: {intent.replace('_', ' ')}")

        return ". ".join(parts) if parts else "No actionable items found"
