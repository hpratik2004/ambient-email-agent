from pydantic import BaseModel
from langchain_core.tools import tool


@tool
def write_email(to: str, subject: str, content: str) -> str:
    """Write and send an email."""
    return f"Email sent to {to} with subject '{subject}' and content: {content}"


@tool
class Done(BaseModel):
    """Email has been sent."""
    done: bool