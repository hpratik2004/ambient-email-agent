from datetime import datetime
from typing import Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.store.base import BaseStore
from langgraph.types import Command, interrupt
from typing import Literal, Mapping
from langgraph.prebuilt.interrupt import (
    ActionRequest,
    HumanInterrupt,
    HumanInterruptConfig,
)

from email_assistant.tools import get_tools, get_tools_by_name
from email_assistant.prompts import (
    HITL_TOOLS_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    TRIAGE_USER_PROMPT,
    AGENT_SYSTEM_PROMPT_HITL,
    DEFAULT_BACKGROUND,
    DEFAULT_TRIAGE_INSTRUCTIONS,
    DEFAULT_RESPONSE_PREFERENCES,
    DEFAULT_CAL_PREFERENCES,
)
from email_assistant.memory import (
    get_memory,
    update_memory,
    TRIAGE_NS,
    RESPONSE_NS,
    CAL_NS,
)
from email_assistant.schemas import State, StateInput, RouterSchema
from email_assistant.utils import parse_email, format_email_markdown, format_for_display

load_dotenv()

tools = get_tools()
tools_by_name = get_tools_by_name()

llm = init_chat_model("groq:openai/gpt-oss-120b", temperature=0.0)
llm_router = llm.with_structured_output(RouterSchema, method="json_schema")
llm_with_tools = llm.bind_tools(tools, tool_choice="auto")

HITL_TOOLS = ["write_email", "schedule_meeting", "Question"]

# Which preference profile each tool's feedback should update.
TOOL_MEMORY_NS = {
    "write_email": RESPONSE_NS,
    "schedule_meeting": CAL_NS,
}


def llm_call(state: State, store: BaseStore) -> dict:
    """Decide which tool to call next, using the user's learned preferences."""
    cal_preferences = get_memory(store, CAL_NS, DEFAULT_CAL_PREFERENCES)
    response_preferences = get_memory(store, RESPONSE_NS, DEFAULT_RESPONSE_PREFERENCES)

    system_prompt = AGENT_SYSTEM_PROMPT_HITL.format(
        tools_prompt=HITL_TOOLS_PROMPT,
        background=DEFAULT_BACKGROUND,
        response_preferences=response_preferences,
        cal_preferences=cal_preferences,
        today=datetime.now().strftime("%Y-%m-%d"),
    )
    return {
        "messages": [
            llm_with_tools.invoke(
                [{"role": "system", "content": system_prompt}] + state["messages"]
            )
        ]
    }


def build_interrupt_request(tool_call: Mapping, email_markdown: str) -> HumanInterrupt:
    """Build the payload shown to the human for a tool call awaiting approval."""
    if tool_call["name"] == "Question":
        config = HumanInterruptConfig(
            allow_ignore=True,
            allow_respond=True,
            allow_edit=False,
            allow_accept=False,
        )
    else:
        config = HumanInterruptConfig(
            allow_ignore=True,
            allow_respond=True,
            allow_edit=True,
            allow_accept=True,
        )

    return HumanInterrupt(
        action_request=ActionRequest(
            action=tool_call["name"],
            args=tool_call["args"],
        ),
        config=config,
        description=email_markdown + format_for_display(tool_call),
    )


def run_tool(tool_call: Mapping, args: dict | None = None) -> dict:
    """Execute a tool call and return the resulting tool message."""
    tool = tools_by_name[tool_call["name"]]
    observation = tool.invoke(args if args is not None else tool_call["args"])
    return {
        "role": "tool",
        "content": str(observation),
        "tool_call_id": tool_call["id"],
    }


def apply_edit(state: State, tool_call: Mapping, edited_args: dict) -> list:
    """Rewrite the tool call with the human's edits, then execute it."""
    ai_message = state["messages"][-1]
    assert isinstance(ai_message, AIMessage)

    updated_tool_calls = [
        tc for tc in ai_message.tool_calls if tc["id"] != tool_call["id"]
    ] + [
        {
            "type": "tool_call",
            "name": tool_call["name"],
            "args": edited_args,
            "id": tool_call["id"],
        }
    ]

    return [
        ai_message.model_copy(update={"tool_calls": updated_tool_calls}),
        run_tool(tool_call, edited_args),
    ]


def interrupt_handler(
    state: State, store: BaseStore
) -> Command[Literal["llm_call", "__end__"]]:
    """Pause for human review, and learn from whatever feedback is given."""
    result = []
    goto = "llm_call"

    last_message = state["messages"][-1]
    assert isinstance(last_message, AIMessage)

    author, to, subject, email_thread = parse_email(state["email_input"])
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    for tool_call in last_message.tool_calls:
        if tool_call["name"] not in HITL_TOOLS:
            result.append(run_tool(tool_call))
            continue

        request = build_interrupt_request(tool_call, email_markdown)
        response = interrupt([request])[0]
        response_type = response["type"]

        allowed = {
            "accept": request["config"]["allow_accept"],
            "edit": request["config"]["allow_edit"],
            "response": request["config"]["allow_respond"],
            "ignore": request["config"]["allow_ignore"],
        }
        if not allowed.get(response_type):
            raise ValueError(f"Response type '{response_type}' is not allowed for {tool_call['name']}.")

        tool_name = tool_call["name"]
        memory_ns = TOOL_MEMORY_NS.get(tool_name)

        if response_type == "accept":
            result.append(run_tool(tool_call))

        elif response_type == "edit":
            edited_args = response["args"]["args"]
            result.extend(apply_edit(state, tool_call, edited_args))
            if memory_ns:
                update_memory(store, memory_ns, f"The assistant proposed this {tool_name} call: {tool_call['args']}. The user edited it to: {edited_args}. Infer what this implies about their preferences.")

        elif response_type == "response":
            feedback = response["args"]
            result.append({"role": "tool", "content": f"User gave feedback on the proposed {tool_name}. Use it for the next attempt. Feedback: {feedback}", "tool_call_id": tool_call["id"]})
            if memory_ns:
                update_memory(store, memory_ns, f"The assistant proposed this {tool_name} call: {tool_call['args']}. The user asked for changes: {feedback}. Infer what this implies about their preferences.")

        elif response_type == "ignore":
            result.append({"role": "tool", "content": f"User rejected the proposed {tool_name}. End the workflow without further action.", "tool_call_id": tool_call["id"]})
            goto = END
            update_memory(store, TRIAGE_NS, f"The assistant classified this email as needing a response and proposed a {tool_name}, but the user rejected it outright. The email was: {email_markdown} Update the triage preferences so emails like this are not classified as respond.")

        else:
            raise ValueError(f"Unexpected response type: {response_type}")

    return Command(goto=goto, update={"messages": result})  # type: ignore


def should_continue(state: State) -> Literal["interrupt_handler", "__end__"]:
    """Route to the interrupt handler, or end when the agent is finished."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return END  # type: ignore
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "Done":
            return END  # type: ignore
    return "interrupt_handler"


agent_builder = StateGraph(State)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("interrupt_handler", interrupt_handler)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {"interrupt_handler": "interrupt_handler", END: END},
)

response_agent = agent_builder.compile()


def triage_router(
    state: State, store: BaseStore
) -> Command[Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
    """Classify the email, using triage rules learned from past feedback."""
    author, to, subject, email_thread = parse_email(state["email_input"])

    triage_instructions = get_memory(store, TRIAGE_NS, DEFAULT_TRIAGE_INSTRUCTIONS)

    system_prompt = TRIAGE_SYSTEM_PROMPT.format(
        background=DEFAULT_BACKGROUND,
        triage_instructions=triage_instructions,
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
                "messages": [{"role": "user", "content": f"Respond to the email: {email_markdown}"}],
            },
        )

    if classification == "notify":
        print("Classification: NOTIFY - This email contains important information")
        return Command(goto="triage_interrupt_handler", update={"classification_decision": classification})

    if classification == "ignore":
        print("Classification: IGNORE - This email can be safely ignored")
        return Command(goto=END, update={"classification_decision": classification})  # type: ignore

    raise ValueError(f"Invalid classification: {classification}")


def triage_interrupt_handler(
    state: State, store: BaseStore
) -> Command[Literal["response_agent", "__end__"]]:
    """Show a 'notify' email to the human, and learn from what they do with it."""
    author, to, subject, email_thread = parse_email(state["email_input"])
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    request = HumanInterrupt(
        action_request=ActionRequest(
            action=f"Email Assistant: {state['classification_decision']}",
            args={},
        ),
        config=HumanInterruptConfig(
            allow_ignore=True,
            allow_respond=True,
            allow_edit=False,
            allow_accept=False,
        ),
        description=email_markdown,
    )

    response = interrupt([request])[0]

    messages = [{"role": "user", "content": f"Email to notify user about: {email_markdown}"}]

    if response["type"] == "response":
        messages.append({"role": "user", "content": f"User wants to reply to this email. Use this feedback to respond: {response['args']}"})
        update_memory(store, TRIAGE_NS, f"The assistant classified this email as 'notify', but the user chose to reply to it instead. The email was: {email_markdown} Update the triage preferences so emails like this are classified as respond.")
        return Command(goto="response_agent", update={"messages": messages})

    if response["type"] == "ignore":
        update_memory(store, TRIAGE_NS, f"The assistant classified this email as 'notify', but the user dismissed it without acting. The email was: {email_markdown} Update the triage preferences so emails like this are classified as ignore.")
        return Command(goto=END, update={"messages": messages})  # type: ignore

    raise ValueError(f"Unexpected response type: {response['type']}")


overall_workflow = (
    StateGraph(State, input_schema=StateInput)
    .add_node(triage_router)
    .add_node(triage_interrupt_handler)
    .add_node("response_agent", response_agent)
    .add_edge(START, "triage_router")
)

email_assistant = overall_workflow.compile()