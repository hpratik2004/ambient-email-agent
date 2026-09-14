"""Cross-thread memory: preferences that persist between email threads."""

from langgraph.store.base import BaseStore
from dotenv import load_dotenv

load_dotenv()

# Namespaces for each kind of preference we remember.
TRIAGE_NS = ("email_assistant", "triage_preferences")
RESPONSE_NS = ("email_assistant", "response_preferences")
CAL_NS = ("email_assistant", "cal_preferences")

MEMORY_KEY = "user_preferences"


def get_memory(store: BaseStore, namespace: tuple, default_content: str) -> str:
    """Read a preference profile, seeding it with the default on first use."""
    existing = store.get(namespace, MEMORY_KEY)
    if existing is not None:
        return existing.value # type: ignore

    store.put(namespace, MEMORY_KEY, default_content) # type: ignore
    return default_content

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from email_assistant.prompts import (
    MEMORY_UPDATE_INSTRUCTIONS,
    MEMORY_UPDATE_REINFORCEMENT,
)


class UserPreferences(BaseModel):
    """An updated preference profile, with the reasoning behind the change."""

    chain_of_thought: str = Field(
        description="Reasoning about which preferences need to be added or updated."
    )
    user_preferences: str = Field(description="The updated preference profile.")


_memory_llm = init_chat_model(
    "groq:openai/gpt-oss-120b", temperature=0.0
).with_structured_output(UserPreferences, method="json_schema")


def update_memory(store: BaseStore, namespace: tuple, feedback: str) -> None:
    """Revise a preference profile in light of new feedback from the user."""
    current = store.get(namespace, MEMORY_KEY)
    current_profile = current.value if current else ""

    result = _memory_llm.invoke(
        [
            {
                "role": "system",
                "content": MEMORY_UPDATE_INSTRUCTIONS.format(
                    current_profile=current_profile, namespace=namespace[1]
                ),
            },
            {"role": "user", "content": f"{feedback}\n\n{MEMORY_UPDATE_REINFORCEMENT}"},
        ]
    )
    assert isinstance(result, UserPreferences)
    store.put(namespace, MEMORY_KEY, result.user_preferences.strip())  # type: ignore