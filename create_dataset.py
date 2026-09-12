from dotenv import load_dotenv
from langsmith import Client

from email_assistant.eval.email_dataset import examples_triage

load_dotenv()

client = Client()

dataset_name = "Email Triage Evaluation"

if not client.has_dataset(dataset_name=dataset_name):
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Emails and their expected triage decisions.",
    )
    client.create_examples(dataset_id=dataset.id, examples=examples_triage)
    print(f"Created dataset '{dataset_name}' with {len(examples_triage)} examples.")
else:
    print(f"Dataset '{dataset_name}' already exists.")