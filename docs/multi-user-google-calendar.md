# Multi-user Google Calendar

Each Telegram user can have a separate Google account token and calendar id.

Authorize Google Calendar for a specific Telegram user id:

```bash
python google_calendar_setup.py --user-id 123456789
```

The token is saved locally to:

```text
data/google_tokens/123456789.json
```

Useful Telegram commands:

```text
/calendar_auth
/calendar_set primary
/calendar_set your_calendar_id@group.calendar.google.com
```

`GOOGLE_CALENDAR_ID` in `.env` remains the default fallback. Per-user values set
with `/calendar_set` override it only for that Telegram user.
