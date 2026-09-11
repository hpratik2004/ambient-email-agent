from typing import Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import MessagesState


class RouterSchema(BaseModel):
    """Analyze the unread email and route it according to its content."""

    reasoning: str = Field(
        description="Step-by-step reasoning behind the classification."
    )
    classification: Literal["ignore", "respond", "notify"] = Field(
        description="The classification of an email: 'ignore' for irrelevant emails, "
        "'notify' for important information that doesn't need a response, "
        "'respond' for emails that need a reply",
    )


class StateInput(TypedDict):
    """What the graph accepts as input: a single incoming email."""

    email_input: dict


class State(MessagesState):
    """Full graph state: messages, the original email, and the triage decision."""

    email_input: dict
    classification_decision: Literal["ignore", "respond", "notify"]