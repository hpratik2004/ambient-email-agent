import pytest
from dotenv import load_dotenv
from langsmith import testing as t
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from email_assistant.eval.email_dataset import (
    email_inputs,
    email_names,
    response_criteria_list,
)
from email_assistant.eval.prompts import RESPONSE_CRITERIA_SYSTEM_PROMPT
from email_assistant.email_assistant import email_assistant
from email_assistant.utils import format_messages_string

load_dotenv()


class CriteriaGrade(BaseModel):
    """Score the response against specific criteria."""

    justification: str = Field(
        description="The justification for the grade, including specific examples from the response."
    )
    grade: bool = Field(description="Does the response meet the provided criteria?")


criteria_eval_llm = init_chat_model("groq:openai/gpt-oss-120b", temperature=0.0)
criteria_eval_structured_llm = criteria_eval_llm.with_structured_output(
    CriteriaGrade, method="json_schema"
)


@pytest.mark.langsmith(output_keys=["criteria"])
@pytest.mark.parametrize(
    "email_input, email_name, criteria",
    [
        (email_inputs[i], email_names[i], response_criteria_list[i])
        for i in [0, 3, 4, 6]
    ],
)
def test_response_criteria(email_input, email_name, criteria):
    """Grade the assistant's full response against its success criteria."""
    result = email_assistant.invoke({"email_input": email_input})
    all_messages_str = format_messages_string(result["messages"])

    eval_result = criteria_eval_structured_llm.invoke(
        [
            {"role": "system", "content": RESPONSE_CRITERIA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"\n\nResponse criteria: {criteria} "
                f"\n\nAssistant's response: \n\n{all_messages_str}\n\n"
                "Evaluate whether the assistant's response meets the criteria "
                "and provide justification for your evaluation.",
            },
        ]
    )
    assert isinstance(eval_result, CriteriaGrade)

    t.log_outputs(
        {
            "justification": eval_result.justification,
            "response": all_messages_str,
        }
    )

    assert eval_result.grade