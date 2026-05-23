import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GOOGLE_TOKENS_DIR = DATA_DIR / "google_tokens"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def token_path_for_user(user_id: int | None) -> Path:
    if user_id is None:
        return TOKEN_PATH
    return GOOGLE_TOKENS_DIR / f"{user_id}.json"


def get_service(user_id: int | None = None):
    load_dotenv()
    creds = None
    token_path = token_path_for_user(user_id)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("Saved Google token is expired or revoked. Re-authorizing...")
                token_path.unlink(missing_ok=True)
                creds = None

        if not creds or not creds.valid:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH}. Download OAuth Desktop credentials "
                    "from Google Cloud Console and save them as credentials.json."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def create_test_event(service):
    load_dotenv()
    timezone = os.getenv("TIMEZONE", "Europe/Moscow")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    zone = ZoneInfo(timezone)
    start = datetime.now(zone) + timedelta(minutes=10)
    end = start + timedelta(minutes=15)

    event = {
        "summary": "Тест локального Telegram-агента",
        "description": "Это тестовое событие можно удалить.",
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
    }

    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    print("Created test event:")
    print(created.get("htmlLink", created.get("id", "ok")))


def main():
    parser = argparse.ArgumentParser(description="Authorize and test Google Calendar integration.")
    parser.add_argument(
        "--create-test",
        action="store_true",
        help="Create a short test event 10 minutes from now.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Telegram user id. Saves OAuth token to data/google_tokens/<user-id>.json.",
    )
    args = parser.parse_args()

    service = get_service(args.user_id)
    token_path = token_path_for_user(args.user_id)
    print(f"Google Calendar OAuth is ready. Token saved to {token_path}")

    if args.create_test:
        create_test_event(service)


if __name__ == "__main__":
    main()
