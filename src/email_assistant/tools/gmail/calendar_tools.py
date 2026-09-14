"""Calendar tools backed by a real Google Calendar."""

from datetime import datetime, timedelta

from langchain_core.tools import tool

from email_assistant.tools.gmail.auth import get_calendar_service


@tool
def schedule_meeting(
    attendees: list[str],
    subject: str,
    duration_minutes: int,
    preferred_day: str,
    start_time: float,
) -> str:
    """Schedule a calendar meeting. preferred_day is a date like 2026-09-20, start_time is an hour like 14 or 16.5 for 4:30pm."""
    service = get_calendar_service()

    day = datetime.fromisoformat(preferred_day.split("T")[0])
    hour = int(start_time)
    minute = int(round((start_time - hour) * 60))
    start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end = start + timedelta(minutes=duration_minutes)

    event = {
        "summary": subject,
        "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Berlin"},
        "attendees": [{"email": a} for a in attendees],
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    date_str = start.strftime("%A, %B %d, %Y at %H:%M")
    return f"Meeting '{subject}' scheduled for {date_str} ({duration_minutes} minutes). Link: {created.get('htmlLink')}"


@tool
def check_calendar_availability(day: str) -> str:
    """Check calendar availability for a given day."""
    service = get_calendar_service()

    date = datetime.fromisoformat(day.split("T")[0])
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    if not events:
        return f"No events on {date.strftime('%A, %B %d')}. The whole day is free."

    busy = []
    for event in events:
        event_start = event["start"].get("dateTime", event["start"].get("date"))
        busy.append(f"{event_start}: {event.get('summary', 'Busy')}")

    return f"Existing events on {date.strftime('%A, %B %d')}:\n" + "\n".join(busy)