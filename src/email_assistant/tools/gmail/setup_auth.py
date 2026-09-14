"""One-time script to authorize access to Gmail and Calendar."""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SECRETS_DIR = Path(__file__).parent / ".secrets"
SECRETS_FILE = SECRETS_DIR / "secrets.json"
TOKEN_FILE = SECRETS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def main() -> None:
    if not SECRETS_FILE.exists():
        raise FileNotFoundError(f"No OAuth client file found at {SECRETS_FILE}")

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved credentials to {TOKEN_FILE}")


if __name__ == "__main__":
    main()