from typing import Dict, List
from langchain_core.tools import BaseTool

from email_assistant.tools.email_tools import write_email, Done
from email_assistant.tools.calendar_tools import (
    schedule_meeting,
    check_calendar_availability,
)

ALL_TOOLS = {
    "write_email": write_email,
    "schedule_meeting": schedule_meeting,
    "check_calendar_availability": check_calendar_availability,
    "Done": Done,
}


def get_tools() -> List[BaseTool]:
    """Return the list of tools available to the agent."""
    return list(ALL_TOOLS.values())


def get_tools_by_name() -> Dict[str, BaseTool]:
    """Return tools keyed by name, for looking up a tool when executing a call."""
    return dict(ALL_TOOLS)