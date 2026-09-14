from datetime import datetime
from typing import Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
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
from email_assistant.schemas import State, StateInput, RouterSchema
from email_assistant.utils import parse_email, format_email_markdown, format_for_display

load_dotenv()

tools = get_tools()
tools_by_name = get_tools_by_name()

llm = init_chat_model("groq:openai/gpt-oss-120b", temperature=0.0)
llm_router = llm.with_structured_output(RouterSchema, method="json_schema")
llm_with_tools = llm.bind_tools(tools, tool_choice="auto")

# Tool calls that require human approval before they run.
HITL_TOOLS = ["write_email", "schedule_meeting", "Question"]

def llm_call(state: State) -> dict:
    """Decide which tool to call next, or finish."""
    system_prompt = AGENT_SYSTEM_PROMPT_HITL.format(
        tools_prompt=HITL_TOOLS_PROMPT,
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

def build_interrupt_request(tool_call: dict, email_markdown: str) -> HumanInterrupt:
    """Build the payload shown to the human for a tool call awaiting approval."""
    # Questions can only be answered or skipped; there is nothing to edit or accept.
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

def run_tool(tool_call: dict, args: dict | None = None) -> dict:
    """Execute a tool call and return the resulting tool message."""
    tool = tools_by_name[tool_call["name"]]
    observation = tool.invoke(args if args is not None else tool_call["args"])
    return {
        "role": "tool",
        "content": str(observation),
        "tool_call_id": tool_call["id"],
    }

def apply_edit(state: State, tool_call: dict, edited_args: dict) -> list:
    """Rewrite the tool call with the human's edits, then execute it.

    The tool call on the AI message is updated as well as the executed args.
    If only the execution used the new args, the message history would show
    the model proposing one thing and the tool doing another, which can
    confuse the agent on later turns.
    """
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

def interrupt_handler(state: State) -> Command[Literal["llm_call", "__end__"]]:
    """Pause for human review before running any sensitive tool call."""
    result = []
    goto = "llm_call"

    last_message = state["messages"][-1]
    assert isinstance(last_message, AIMessage)

    author, to, subject, email_thread = parse_email(state["email_input"])
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    for tool_call in last_message.tool_calls:
        # Tools without real-world side effects run without asking.
        if tool_call["name"] not in HITL_TOOLS:
            result.append(run_tool(tool_call)) # type: ignore
            continue

        request = build_interrupt_request(tool_call, email_markdown) # type: ignore
        response = interrupt([request])[0]
        response_type = response["type"]

        # The config says which actions are offered; reject anything else rather
        # than running a tool the human was never given the option to approve.
        allowed = {
            "accept": request["config"]["allow_accept"],
            "edit": request["config"]["allow_edit"],
            "response": request["config"]["allow_respond"],
            "ignore": request["config"]["allow_ignore"],
        }
        if not allowed.get(response_type):
            raise ValueError(
                f"Response type '{response_type}' is not allowed for "
                f"{tool_call['name']}."
            )

        if response_type == "accept":
            result.append(run_tool(tool_call)) # type: ignore

        elif response_type == "edit":
            result.extend(apply_edit(state, tool_call, response["args"]["args"])) # type: ignore

        elif response_type == "response":
            result.append(
                {
                    "role": "tool",
                    "content": f"User gave feedback on the proposed {tool_call['name']}. "
                    f"Use it for the next attempt. Feedback: {response['args']}",
                    "tool_call_id": tool_call["id"],
                }
            )

        elif response_type == "ignore":
            result.append(
                {
                    "role": "tool",
                    "content": f"User rejected the proposed {tool_call['name']}. "
                    "End the workflow without further action.",
                    "tool_call_id": tool_call["id"],
                }
            )
            goto = END

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
    state: State,
) -> Command[Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
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
        return Command(
            goto="triage_interrupt_handler",
            update={"classification_decision": classification},
        )

    if classification == "ignore":
        print("Classification: IGNORE - This email can be safely ignored")
        return Command(goto=END, update={"classification_decision": classification})  # type: ignore

    raise ValueError(f"Invalid classification: {classification}")

def triage_interrupt_handler(
    state: State,
) -> Command[Literal["response_agent", "__end__"]]:
    """Show a 'notify' email to the human and let them dismiss it or reply."""
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

    messages = [
        {"role": "user", "content": f"Email to notify user about: {email_markdown}"}
    ]

    if response["type"] == "response":
        messages.append(
            {
                "role": "user",
                "content": f"User wants to reply to this email. "
                f"Use this feedback to respond: {response['args']}",
            }
        )
        return Command(goto="response_agent", update={"messages": messages})

    if response["type"] == "ignore":
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