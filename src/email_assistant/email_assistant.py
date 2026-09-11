from datetime import datetime
from typing import Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from email_assistant.tools import get_tools, get_tools_by_name
from email_assistant.prompts import (
    TOOLS_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    TRIAGE_USER_PROMPT,
    AGENT_SYSTEM_PROMPT,
    DEFAULT_BACKGROUND,
    DEFAULT_TRIAGE_INSTRUCTIONS,
    DEFAULT_RESPONSE_PREFERENCES,
    DEFAULT_CAL_PREFERENCES,
)
from email_assistant.schemas import State, StateInput, RouterSchema
from email_assistant.utils import parse_email, format_email_markdown

load_dotenv()

tools = get_tools()
tools_by_name = get_tools_by_name()

llm = init_chat_model("groq:openai/gpt-oss-120b", temperature=0.0)
llm_router = llm.with_structured_output(RouterSchema, method="json_schema")
llm_with_tools = llm.bind_tools(tools, tool_choice="auto")


def llm_call(state: State) -> dict:
    """Decide which tool to call next, or finish."""
    system_prompt = AGENT_SYSTEM_PROMPT.format(
        tools_prompt=TOOLS_PROMPT,
        background=DEFAULT_BACKGROUND,
        response_preferences=DEFAULT_RESPONSE_PREFERENCES,
        cal_preferences=DEFAULT_CAL_PREFERENCES,
        today=datetime.now().strftime("%Y-%m-%d"),
    )
    return {
        "messages": [
            llm_with_tools.invoke(
                [{"role": "system", "content": system_prompt}] + state["messages"]
            )
        ]
    }


def tool_node(state: State) -> dict:
    """Execute whatever tool calls the model just made."""
    result = []
    last_message = state["messages"][-1]
    assert isinstance(last_message, AIMessage)
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(
            {
                "role": "tool",
                "content": str(observation),
                "tool_call_id": tool_call["id"],
            }
        )
    return {"messages": result}


def should_continue(state: State) -> Literal["environment", "__end__"]:
    """Keep looping until the Done tool is called."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return END  # type: ignore
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "Done":
            return END  # type: ignore
    return "environment"


agent_builder = StateGraph(State)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("environment", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {"environment": "environment", END: END},
)
agent_builder.add_edge("environment", "llm_call")

agent = agent_builder.compile()

def triage_router(state: State) -> Command[Literal["response_agent", "__end__"]]:
    """Decide whether to respond to, notify about, or ignore an incoming email."""
    author, to, subject, email_thread = parse_email(state["email_input"])

    system_prompt = TRIAGE_SYSTEM_PROMPT.format(
        background=DEFAULT_BACKGROUND,
        triage_instructions=DEFAULT_TRIAGE_INSTRUCTIONS,
    )
    user_prompt = TRIAGE_USER_PROMPT.format(
        author=author, to=to, subject=subject, email_thread=email_thread
    )

    result = llm_router.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    assert isinstance(result, RouterSchema)

    classification = result.classification

    if classification == "respond":
        print("Classification: RESPOND - This email requires a response")
        email_markdown = format_email_markdown(subject, author, to, email_thread)
        return Command(
            goto="response_agent",
            update={
                "classification_decision": classification,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Respond to the email: {email_markdown}",
                    }
                ],
            },
        )

    if classification == "notify":
        print("Classification: NOTIFY - This email contains important information")
        return Command(goto=END, update={"classification_decision": classification}) # type: ignore

    if classification == "ignore":
        print("Classification: IGNORE - This email can be safely ignored")
        return Command(goto=END, update={"classification_decision": classification}) # type: ignore

    raise ValueError(f"Invalid classification: {classification}")


overall_workflow = (
    StateGraph(State, input_schema=StateInput)
    .add_node(triage_router)
    .add_node("response_agent", agent)
    .add_edge(START, "triage_router")
)

email_assistant = overall_workflow.compile()