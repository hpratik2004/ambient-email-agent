"""Fetch recent emails from Gmail and shape them for the assistant."""

import base64
from typing import List

from email_assistant.tools.gmail.auth import get_gmail_service


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """Pull the plain text body out of a Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        return _decode_part(payload)

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            return _decode_part(part)
        nested = _extract_body(part)
        if nested:
            return nested

    return ""


def fetch_emails(max_results: int = 5, query: str = "is:unread") -> List[dict]:
    """Return recent emails in the shape the assistant expects."""
    service = get_gmail_service()

    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    emails = []
    for item in listing.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )

        headers = {h["name"].lower(): h["value"] for h in message["payload"]["headers"]}

        emails.append(
            {
                "author": headers.get("from", ""),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", "(no subject)"),
                "email_thread": _extract_body(message["payload"]).strip(),
            }
        )

    return emails