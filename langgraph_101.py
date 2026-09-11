from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
load_dotenv()

from langchain.chat_models import init_chat_model

#llm = init_chat_model("google_genai:gemini-3.6-flash", temperature=0)
llm = init_chat_model("groq:openai/gpt-oss-120b", temperature=0)

#result = llm.invoke("What is an agent?")
#print(result.text)

from langchain.tools import tool

@tool
def write_email(to: str, subject: str, content: str) -> str:
    """Write and send an email."""
    return f"Email sent to {to} with subject '{subject}' and content: {content}"

#print(type(write_email))
#print(write_email.args)
#print(write_email.description)

model_with_tools = llm.bind_tools([write_email], tool_choice="auto")

#output = model_with_tools.invoke("Draft a response to my boss (boss@company.ai) about tomorrow's meeting")
#print(type(output))
#print(output)

args = {
    'to': 'boss@company.ai',
    'subject': "Re: Tomorrow's Meeting - Confirmation",
    'content': "Hi,\n\nI'm writing to confirm our meeting scheduled for tomorrow. I have reviewed the agenda and prepared the necessary materials for our discussion.\n\nPlease let me know if there are any specific topics or updates you would like me to focus on.\n\nBest regards,"
}
result = write_email.invoke(args)
print(result)

from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class StateSchema(TypedDict):
    request: str
    email: str

def write_email_node(state: StateSchema) -> dict:
    output = model_with_tools.invoke(f"Use the write_email tool to complete this task: {state['request']}")
    args = output.tool_calls[0]['args']
    email = write_email.invoke(args)
    return {"email": email}

workflow = StateGraph(StateSchema)
workflow.add_node("write_email_node", write_email_node)
workflow.add_edge(START, "write_email_node")
workflow.add_edge("write_email_node", END)

app = workflow.compile()

result = app.invoke({"request": "Draft a response to my boss (boss@company.ai) about tomorrow's meeting"}) # type: ignore
print(result)

from typing import Literal
from langgraph.graph import MessagesState
from langchain_core.messages import SystemMessage

def call_llm(state: MessagesState) -> dict:
    """Run LLM"""
    messages = [SystemMessage(content="Use the write_email tool to complete the user's request.")] + state["messages"]
    output = model_with_tools.invoke(messages)
    return {"messages": [output]}

from langchain_core.messages import AIMessage

def run_tool(state: MessagesState) -> dict:
    """Performs the tool call"""
    result = []
    last_message = state["messages"][-1]
    assert isinstance(last_message, AIMessage)
    for tool_call in last_message.tool_calls:
        observation = write_email.invoke(tool_call["args"])
        result.append({"role": "tool", "content": observation, "tool_call_id": tool_call["id"]})
    return {"messages": result}

def should_continue(state: MessagesState) -> Literal["run_tool", "__end__"]:
    """Route to tool handler, or end if no tool call"""
    messages = state["messages"]
    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "run_tool"
    return END  # type: ignore

workflow = StateGraph(MessagesState)
workflow.add_node("call_llm", call_llm)
workflow.add_node("run_tool", run_tool)
workflow.add_edge(START, "call_llm")
workflow.add_conditional_edges("call_llm", should_continue, {"run_tool": "run_tool", END: END})
workflow.add_edge("run_tool", END)

app = workflow.compile()

result = app.invoke({"messages": [{"role": "user", "content": "Draft a response to my boss (boss@company.ai) confirming that I want to attend tomorrow's meeting!"}]}) # type: ignore
for m in result["messages"]:
    m.pretty_print()

from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=[write_email],
    system_prompt="Respond to the user's request using the tools provided."
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Draft a response to my boss (boss@company.ai) confirming that I want to attend tomorrow's meeting!"}]}
)

for m in result["messages"]:
    m.pretty_print()

from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model=llm,
    tools=[write_email],
    system_prompt="Respond to the user's request using the tools provided.",
    checkpointer=InMemorySaver()
)

config = {"configurable": {"thread_id": "1"}}
result = agent.invoke({"messages": [{"role": "user", "content": "What are some good practices for writing emails?"}]}, config) # type: ignore

state = agent.get_state(config) # type: ignore
for message in state.values['messages']:
    message.pretty_print()

from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver

class State(TypedDict):
    input: str
    user_feedback: str

def step_1(state):
    print("---Step 1---")

def human_feedback(state):
    print("---human_feedback---")
    feedback = interrupt("Please provide feedback:")
    return {"user_feedback": feedback}

def step_3(state):
    print("---Step 3---")

builder = StateGraph(State)
builder.add_node("step_1", step_1)
builder.add_node("human_feedback", human_feedback)
builder.add_node("step_3", step_3)
builder.add_edge(START, "step_1")
builder.add_edge("step_1", "human_feedback")
builder.add_edge("human_feedback", "step_3")
builder.add_edge("step_3", END)

memory = InMemorySaver()
graph = builder.compile(checkpointer=memory)

initial_input = {"input": "hello world"}
thread = {"configurable": {"thread_id": "1"}}

for event in graph.stream(initial_input, thread, stream_mode="updates"): # type: ignore
    print(event)
    print("\n")

for event in graph.stream(
    Command(resume="go to step 3!"),
    thread, # type: ignore
    stream_mode="updates",
):
    print(event)
    print("\n")