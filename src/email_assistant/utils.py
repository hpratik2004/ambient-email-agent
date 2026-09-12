def parse_email(email_input: dict) -> tuple[str, str, str, str]:
    """Pull the author, recipient, subject, and body out of an email dict."""
    return (
        email_input["author"],
        email_input["to"],
        email_input["subject"],
        email_input["email_thread"],
    )


def format_email_markdown(subject: str, author: str, to: str, email_thread: str) -> str:
    """Format an email as markdown for display to the model or a human reviewer."""
    return f"""

**Subject**: {subject}
**From**: {author}
**To**: {to}

{email_thread}

---
"""

from typing import Any, List


def extract_tool_calls(messages: List[Any]) -> List[str]:
    """Return the lowercased names of every tool called across a list of messages."""
    tool_call_names = []
    for message in messages:
        if isinstance(message, dict) and message.get("tool_calls"):
            tool_call_names.extend(call["name"].lower() for call in message["tool_calls"])
        elif hasattr(message, "tool_calls") and message.tool_calls: # type: ignore
            tool_call_names.extend(call["name"].lower() for call in message.tool_calls)
    return tool_call_names


def format_messages_string(messages: List[Any]) -> str:
    """Flatten a list of messages into one string, for passing to an LLM judge."""
    return "\n".join(message.pretty_repr() for message in messages)