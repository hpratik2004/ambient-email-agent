from datetime import datetime
from langchain_core.tools import tool


@tool
def schedule_meeting(
    attendees: list[str],
    subject: str,
    duration_minutes: int,
    preferred_day: str,
    start_time: int,
) -> str:
    """Schedule a calendar meeting. preferred_day should be a date like 2026-09-20."""
    # Accept either a plain date or a full date-time, since models emit both.
    day = datetime.fromisoformat(preferred_day.split("T")[0])
    date_str = day.strftime("%A, %B %d, %Y")
    return (
        f"Meeting '{subject}' scheduled on {date_str} at {start_time}:00 "
        f"for {duration_minutes} minutes with {len(attendees)} attendees"
    )

@tool
def check_calendar_availability(day: str) -> str:
    """Check calendar availability for a given day."""
    return f"Available times on {day}: 9:00 AM, 2:00 PM, 4:00 PM"