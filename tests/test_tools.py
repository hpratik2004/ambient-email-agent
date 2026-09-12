import pytest
from dotenv import load_dotenv
from langsmith import testing as t

from email_assistant.eval.email_dataset import email_inputs, expected_tool_calls
from email_assistant.email_assistant import email_assistant
from email_assistant.utils import extract_tool_calls, format_messages_string

load_dotenv()


@pytest.mark.langsmith
@pytest.mark.parametrize(
    "email_input, expected_calls",
    [
        (email_inputs[0], expected_tool_calls[0]),
        (email_inputs[3], expected_tool_calls[3]),
        (email_inputs[6], expected_tool_calls[6]),
    ],
)
def test_email_dataset_tool_calls(email_input, expected_calls):
    """Check that the assistant makes all the tool calls we expect for an email.

    This confirms every expected tool was called. It does not check call order
    or how many times each tool was invoked.
    """
    result = email_assistant.invoke({"email_input": email_input})

    extracted_tool_calls = extract_tool_calls(result["messages"])

    missing_calls = [
        call for call in expected_calls if call.lower() not in extracted_tool_calls
    ]

    t.log_outputs(
        {
            "missing_calls": missing_calls,
            "extracted_tool_calls": extracted_tool_calls,
            "response": format_messages_string(result["messages"]),
        }
    )

    assert len(missing_calls) == 0