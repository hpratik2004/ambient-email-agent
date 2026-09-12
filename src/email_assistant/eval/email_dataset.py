"""Test cases for evaluating the email assistant."""

# --- Email inputs ---

email_input_1 = {
    "author": "Alice Smith <alice.smith@company.com>",
    "to": "Pk <pk@company.com>",
    "subject": "Quick question about API documentation",
    "email_thread": """Hi Pk,

I was reviewing the API documentation for the new authentication service and noticed a few endpoints seem to be missing from the specs. Could you help clarify if this was intentional or if we should update the docs?

Specifically, I'm looking at:
- /auth/refresh
- /auth/validate

Thanks!
Alice""",
}

email_input_2 = {
    "author": "Marketing Team <marketing@company.com>",
    "to": "Pk <pk@company.com>",
    "subject": "New Company Newsletter Available",
    "email_thread": """Hello Pk,

The latest edition of our company newsletter is now available on the intranet. This month features articles on our Q2 results and upcoming team building activities.

Best regards,
Marketing Team""",
}

email_input_3 = {
    "author": "System Admin <sysadmin@company.com>",
    "to": "Pk <pk@company.com>",
    "subject": "Scheduled maintenance - database downtime",
    "email_thread": """Hi Pk,

This is a reminder that we'll be performing scheduled maintenance on the production database tonight from 2AM to 4AM. During this time, all database services will be unavailable.

Please plan your work accordingly.

Thanks,
System Admin Team""",
}

email_input_4 = {
    "author": "Project Manager <pm@client.com>",
    "to": "Pk <pk@company.com>",
    "subject": "Integration planning - let's schedule a call",
    "email_thread": """Pk,

I'd like to schedule a call to discuss the integration plan before we commit to a timeline.

Are you available sometime next week? Tuesday or Thursday afternoon would work best for me, for about 45 minutes.

Regards,
Project Manager""",
}

email_input_5 = {
    "author": "Conference Organizer <events@techconf.com>",
    "to": "Pk <pk@company.com>",
    "subject": "Invitation to speak at TechConf 2026",
    "email_thread": """Hi Pk,

We're reaching out to invite you to TechConf 2026, happening June 15-17.

The conference features workshops on AI and ML, and great networking opportunities. Early bird registration is available until April 30th. We can also arrange group discounts if other team members want to join.

Would you be interested in attending?

Best regards,
Conference Team""",
}

email_input_6 = {
    "author": "GitHub <notifications@github.com>",
    "to": "Pk <pk@company.com>",
    "subject": "[repo] New comment on pull request #42",
    "email_thread": """A new comment was added to pull request #42.

View it on GitHub or unsubscribe from these notifications.""",
}

email_input_7 = {
    "author": "Sarah Chen <sarah.chen@company.com>",
    "to": "Pk <pk@company.com>",
    "subject": "Can you review the deployment doc before Friday?",
    "email_thread": """Hi Pk,

I've drafted the deployment runbook and would appreciate your review before we finalize it on Friday.

I've shared the draft in the team folder. Let me know if you spot anything missing.

Thanks,
Sarah""",
}

email_input_8 = {
    "author": "Premium Deals <offers@dealsite.com>",
    "to": "Pk <pk@company.com>",
    "subject": "LAST CHANCE: 80% off developer tools!",
    "email_thread": """Don't miss our BIGGEST SALE of the year! Get 80% off premium developer tools.

Limited time only. Click here to claim your discount now!""",
}

# --- Ground truth triage classifications ---

triage_output_1 = "respond"
triage_output_2 = "ignore"
triage_output_3 = "notify"
triage_output_4 = "respond"
triage_output_5 = "respond"
triage_output_6 = "notify"
triage_output_7 = "respond"
triage_output_8 = "ignore"

# --- Expected tool calls (empty for emails that need no response) ---

expected_tool_calls = [
    ["write_email"],
    [],
    [],
    ["check_calendar_availability", "schedule_meeting", "write_email"],
    ["write_email"],
    [],
    ["write_email"],
    [],
]

# --- Success criteria for responses (used by the LLM judge) ---

response_criteria_1 = """
- Send an email with the write_email tool acknowledging the question about the missing endpoints
- Indicate whether the assistant will investigate or who will be asked
- Give a rough timeline for follow-up
"""

response_criteria_2 = ""

response_criteria_3 = ""

response_criteria_4 = """
- Check calendar availability with the check_calendar_availability tool
- Schedule a meeting with the schedule_meeting tool
- Send a confirmation email with the write_email tool
- Reference the meeting duration and purpose in the response
"""

response_criteria_5 = """
- Send an email with the write_email tool
- Acknowledge the early bird registration deadline
- Ask for more detail about the workshops
- Ask about the group discount
"""

response_criteria_6 = ""

response_criteria_7 = """
- Send an email with the write_email tool
- Acknowledge the existing draft that was shared
- Explicitly reference the Friday deadline
- Commit to reviewing before that deadline
"""

response_criteria_8 = ""

# --- Collected lists ---

email_inputs = [
    email_input_1, email_input_2, email_input_3, email_input_4,
    email_input_5, email_input_6, email_input_7, email_input_8,
]

email_names = [
    "email_input_1", "email_input_2", "email_input_3", "email_input_4",
    "email_input_5", "email_input_6", "email_input_7", "email_input_8",
]

triage_outputs_list = [
    triage_output_1, triage_output_2, triage_output_3, triage_output_4,
    triage_output_5, triage_output_6, triage_output_7, triage_output_8,
]

response_criteria_list = [
    response_criteria_1, response_criteria_2, response_criteria_3, response_criteria_4,
    response_criteria_5, response_criteria_6, response_criteria_7, response_criteria_8,
]

# --- Dataset format for LangSmith ---

examples_triage = [
    {"inputs": {"email_input": email_inputs[i]}, "outputs": {"classification": triage_outputs_list[i]}}
    for i in range(len(email_inputs))
]