from datetime import datetime, timedelta
from email_assistant.tools.gmail.auth import get_calendar_service
from langchain_core.tools import tool


@tool
def schedule_meeting(
    attendees: list[str],
    subject: str,
    duration_minutes: int,
    preferred_day: str,
    start_time: float,
) -> str:
    """Schedule a calendar meeting. preferred_day is a date like 2026-09-20, start_time is an hour like 14 or 16.5 for 4:30pm."""
    day = datetime.fromisoformat(preferred_day.split("T")[0])
    hour = int(start_time)
    minute = int(round((start_time - hour) * 60))
    start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    date_str = start.strftime("%A, %B %d, %Y at %H:%M")
    return (
        f"Meeting '{subject}' scheduled on {date_str} "
        f"for {duration_minutes} minutes with {len(attendees)} attendees"
    )

@tool
def check_calendar_availability(day: str) -> str:
    """Check calendar availability for a given day."""
    return f"Available times on {day}: 9:00 AM, 2:00 PM, 4:00 PM"