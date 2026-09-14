"""Tools that act on a real Gmail account."""

import base64
from email.message import EmailMessage

from langchain_core.tools import tool

from email_assistant.tools.gmail.auth import get_gmail_service


@tool
def write_email(to: str, subject: str, content: str) -> str:
    """Write and send an email."""
    service = get_gmail_service()

    message = EmailMessage()
    message.set_content(content)
    message["To"] = to
    message["Subject"] = subject

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": encoded}).execute()

    return f"Email sent to {to} with subject '{subject}' (message id: {sent['id']})"