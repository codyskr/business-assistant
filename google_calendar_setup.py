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
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_service():
    load_dotenv()
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("Saved Google token is expired or revoked. Re-authorizing...")
                TOKEN_PATH.unlink(missing_ok=True)
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

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

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
    args = parser.parse_args()

    service = get_service()
    print(f"Google Calendar OAuth is ready. Token saved to {TOKEN_PATH}")

    if args.create_test:
        create_test_event(service)


if __name__ == "__main__":
    main()
