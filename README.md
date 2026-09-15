# Ambient Email Agent

An agent that triages incoming email, drafts replies, schedules meetings, pauses for human approval before doing anything with real consequences, and turns each correction into a preference that shapes the next email.

Built with LangGraph and LangChain. Runs against real Gmail and Google Calendar.

## Why "ambient"

Most AI assistants only act when prompted in a chat window. This one runs in the background: it reacts to incoming email on its own, handles what it can, and surfaces to a human only when it needs approval or clarification.

That shift creates the problems this project is actually about. If an agent acts without being asked, you need to decide what it may do unsupervised, how you would know if it started doing the wrong thing, and what happens to the corrections you give it.

## Architecture

One graph, two components with deliberately different designs.

**A triage router** runs on every incoming email and classifies it as `respond`, `notify`, or `ignore`. This is a fixed workflow node rather than an agent: the decision has three enumerable outcomes, so it needs one structured model call, not a reasoning loop. Emails classified `ignore` end immediately, and `notify` emails are surfaced to the human without invoking the agent. The expensive path never runs for newsletters.

**A response agent** runs only for emails that need a reply. Here an agent loop is the right fit, because the work genuinely varies: some emails need only a draft, others need a calendar check, then a booking, then a confirmation. The sequence cannot be known until the email is read.

The two never call each other. They communicate only through shared graph state, which is what lets the agent be composed as a reusable subgraph.

```
                    ┌─────────────────┐
   incoming mail →  │  triage_router  │
                    └────────┬────────┘
                   ignore /  │  \ respond
                      ↓      ↓      ↓
                    end   notify   response_agent
                          handler   ↓        ↑
                             ↓      │        │
                            end   interrupt ─┘
                                  (human approval)
```

## Human oversight

Only actions with real-world consequences are gated: sending an email, scheduling a meeting, and asking the user a question. A read-only calendar lookup is not, because requiring approval for harmless queries trains people to click Accept without reading.

Each gated action offers up to four responses:

| Response | Effect |
|---|---|
| `accept` | Runs the tool call as proposed |
| `edit` | Rewrites the arguments, then runs it |
| `response` | Does not run it; feedback goes back to the agent, which tries again |
| `ignore` | Does not run it; the workflow ends |

The interrupt payload declares which of these are permitted, and a server-side check rejects anything else. Approvals can be given through LangGraph Studio, through the SDK, or through [Agent Inbox](https://dev.agentinbox.ai), which the interrupt schema is compatible with.

## Learning from feedback

Three preference profiles are stored across threads: triage, response, and calendar. What a piece of feedback teaches depends on both the tool and the response:

* Editing or pushing back on a **draft** teaches response preferences
* Editing or pushing back on a **meeting** teaches calendar preferences
* **Accepting** teaches nothing, since there is no signal in it
* **Rejecting outright** teaches the triage step that emails like this should not have reached the agent at all

That last one closes the loop: feedback given at the action stage changes how the next email is classified.

## Evaluation

Three kinds of check, matched to three kinds of output:

| What | Method | Why |
|---|---|---|
| Triage decision | Exact string comparison | A discrete label with three possible values |
| Tool calls made | Set comparison | The expected calls are known in advance |
| Reply quality | LLM as judge, against written criteria | Unstructured text with no single correct answer |

Reaching for an LLM judge when a string comparison would do is expensive and unreliable, so it is used only where nothing cheaper works.

```bash
# tool-call unit tests
uv run pytest tests/test_tools.py --langsmith-output

# response quality, LLM as judge
uv run pytest tests/test_response.py --langsmith-output

# triage classification against a LangSmith dataset
uv run create_dataset.py
uv run run_triage_eval.py
```

## Setup

```bash
uv venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

uv pip install -e .
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=ambient-email-agent
```

## Running it

```bash
langgraph dev
```

This starts the local server and opens LangGraph Studio. Four graphs are registered, which also shows how the system was built up:

| Graph | What it adds |
|---|---|
| `email_assistant` | Triage router plus response agent, mock tools |
| `email_assistant_hitl` | Human approval gates on sensitive actions |
| `email_assistant_hitl_memory` | Preferences learned from feedback |
| `email_assistant_hitl_memory_gmail` | The same, against real Gmail and Calendar |

Submit an email to any of them (set **As Node** to `__start__`):

```json
{
  "author": "Alice Smith <alice.smith@company.com>",
  "to": "Pk <pk@company.com>",
  "subject": "Quick question about API documentation",
  "email_thread": "Hi Pk, I noticed the endpoint for user permissions isn't documented. Could you clarify?"
}
```

### Connecting a real inbox

The Gmail graph needs a Google Cloud project with the Gmail and Calendar APIs enabled and an OAuth desktop client. Put the downloaded credentials at `src/email_assistant/tools/gmail/.secrets/secrets.json`, then:

```bash
uv run src/email_assistant/tools/gmail/setup_auth.py
```

This writes a token next to the credentials. Neither file is tracked by git.

Note that the scopes requested (`gmail.modify`, `calendar`) allow sending mail and writing to your calendar. Use an account you are comfortable with.

## Project structure

```
ambient-email-agent/
├── src/email_assistant/
│   ├── tools/
│   │   ├── email_tools.py                    # write_email, Done, Question
│   │   ├── calendar_tools.py                 # mock scheduling and availability
│   │   ├── registry.py                       # tool lookup, by list and by name
│   │   └── gmail/                            # real Gmail and Calendar tools
│   │       ├── auth.py                       # credential loading and refresh
│   │       ├── gmail_tools.py
│   │       ├── calendar_tools.py
│   │       ├── ingest.py                     # fetch and parse real messages
│   │       ├── registry.py
│   │       └── setup_auth.py                 # one-time OAuth flow
│   ├── eval/
│   │   ├── email_dataset.py                  # test emails, expected outcomes, criteria
│   │   └── prompts.py                        # LLM-as-judge grading prompt
│   ├── email_assistant.py                    # triage router plus response agent
│   ├── email_assistant_hitl.py               # adds approval gates
│   ├── email_assistant_hitl_memory.py        # adds learned preferences
│   ├── email_assistant_hitl_memory_gmail.py  # same, with real Gmail tools
│   ├── memory.py                             # cross-thread preference store
│   ├── schemas.py                            # router output schema, graph state
│   ├── prompts.py                            # system prompts and triage rules
│   ├── utils.py                              # parsing and display formatting
│   └── langgraph_101.py                      # LangGraph fundamentals exploration
├── tests/
│   ├── test_tools.py                         # tool-call unit tests
│   └── test_response.py                      # response quality, LLM as judge
├── langgraph.json                            # graph registration
├── pyproject.toml
└── .env                                      # not tracked
```

## Tech stack

Python · LangGraph · LangChain · LangSmith (tracing and evaluation) · Groq (`openai/gpt-oss-120b`) · Gmail and Calendar APIs · uv

The model is accessed through LangChain's standard interface, so switching provider is a one-line change. This mattered in practice: the project moved across three providers during development because of rate limits, account-level restrictions and a model deprecation.

## Known limitations

These are documented rather than hidden, because most of them are more interesting than the parts that work.

* **LLM-as-judge evaluation is not reproducible.** The same suite scored 75% and 100% on identical code. A suite whose noise is larger than the effect you want to measure cannot act as a regression gate. The judge is also the same model it grades, which is the setup most prone to inconsistency.
* **A sent reply disclosed calendar contents** to an external recipient. The availability tool returns event titles, so the detail was in context and nothing stopped the agent repeating it. The fix is a narrower tool returning free/busy windows only, not a prompt instruction.
* **Free-text memory has no schema.** Preferences are prose rewritten in place by a model, with no retention policy and no way for the user to inspect or correct them. It has recorded observations about tool APIs as though they were user preferences.
* **The agent does not reliably call the completion tool.** Termination depends on a fallback branch that treats "no tool call" as done.
* **Markdown leaks into plain-text email**, and HTML-only messages arrive with an empty body because ingestion has no HTML-to-text step.
* **OAuth scopes are broader than the task needs**, and run traces containing email bodies are sent to a US-region LangSmith project.
* **Not deployed.** No durable persistence, no trigger, no always-on hosting, and no enforced monitoring thresholds. The project structure is deployment-ready; the infrastructure is not built.

## Notes on design decisions

A few choices that were deliberate rather than incidental:

**Tool parameters are loosely typed and parsed inside the tool.** Strict schemas failed repeatedly against reasonable model output: a date parameter typed as `datetime` rejected a plain date, and an integer hour rejected `16.5` for half past four. A strict schema looks safer but shifts the burden onto the model producing an exact format every time.

**Prompts do not describe output format when a schema already does.** The memory updater began emitting its profile wrapped in XML tags copied from its own prompt examples, and then abandoned structured output entirely when the instruction was made stricter. Removing all format language from the prompt fixed it.

**The interrupt config is enforced, not just declared.** Each interrupt states which responses are permitted; a server-side check rejects the rest. Without it, resuming a question with `accept` executed a tool with no implementation and handed the agent its own question back as the result.