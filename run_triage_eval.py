from dotenv import load_dotenv
from langsmith import Client

from email_assistant.email_assistant import email_assistant

load_dotenv()

client = Client()

dataset_name = "Email Triage Evaluation"


def target_email_assistant(inputs: dict) -> dict:
    """Run only the triage router on a dataset example."""
    response = email_assistant.nodes["triage_router"].invoke(
        {"email_input": inputs["email_input"]}
    )
    return {"classification_decision": response.update["classification_decision"]}


def classification_evaluator(outputs: dict, reference_outputs: dict) -> bool:
    """Check whether the agent's classification matches the expected one."""
    return (
        outputs["classification_decision"].lower()
        == reference_outputs["classification"].lower()
    )


results = client.evaluate( 
    target_email_assistant,
    data=dataset_name,
    evaluators=[classification_evaluator], # type: ignore
    experiment_prefix="Triage classification",
    max_concurrency=2,
)