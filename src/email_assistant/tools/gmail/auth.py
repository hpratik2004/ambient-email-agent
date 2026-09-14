"""Load stored Google credentials, refreshing them when they expire."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SECRETS_DIR = Path(__file__).parent / ".secrets"
TOKEN_FILE = SECRETS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials() -> Credentials:
    """Return valid credentials, refreshing the access token if needed."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"No token found at {TOKEN_FILE}. Run setup_auth.py first."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return creds


def get_gmail_service():
    """Return an authorized Gmail API client."""
    return build("gmail", "v1", credentials=get_credentials())


def get_calendar_service():
    """Return an authorized Calendar API client."""
    return build("calendar", "v3", credentials=get_credentials())