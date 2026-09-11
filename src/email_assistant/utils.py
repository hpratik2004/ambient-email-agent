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