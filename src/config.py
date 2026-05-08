from __future__ import annotations

from dataclasses import dataclass
from typing import Any


APP_TITLE = "AI Complaint Classification Lab"
APP_ICON = "🧭"
DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_RETRIES = 2
DEFAULT_TEST_SAMPLE_SIZE = 5
DEFAULT_SEED = 42

REQUIRED_COMPLAINT_COLUMNS = [
    "complaint_id",
    "received_date",
    "channel",
    "product",
    "region",
    "customer_segment",
    "complaint_text",
    "visible_context",
]

REQUIRED_TAXONOMY_SHEETS = [
    "Categories",
    "Root_Causes",
    "Severity_Rules",
    "Escalation_Rules",
]

REQUIRED_TAXONOMY_COLUMNS = {
    "Categories": ["category", "definition", "examples", "non_examples"],
    "Root_Causes": ["root_cause", "definition", "examples", "non_examples"],
    "Severity_Rules": ["severity", "definition", "examples"],
    "Escalation_Rules": ["escalation_flag", "definition", "examples"],
}

CLASSIFICATION_FIELDS = [
    "complaint_id",
    "category",
    "root_cause",
    "severity",
    "escalation_flag",
    "confidence",
    "rationale",
]

ALLOWED_ENUMS = {
    "severity": ["low", "medium", "high"],
    "escalation_flag": ["yes", "no"],
    "confidence": ["low", "medium", "high"],
}

RESULT_METADATA_COLUMNS = [
    "processing_status",
    "error_message",
    "error_type",
    "batch_number",
    "api_attempts",
    "repair_used",
    "response_id",
    "model_name",
]

DEFAULT_STUDENT_PROMPT = """Classify each complaint carefully using the uploaded taxonomy.

Focus on:
- choosing the best-fitting category and root cause
- keeping rationales short and business-readable
- using low confidence when the evidence is weak or ambiguous
"""

ASSIGNMENT_CONTEXT = """You are classifying synthetic customer complaints for an MBA classroom lab.
The user is a student practicing taxonomy design and prompt design.
Follow the uploaded taxonomy strictly when possible.
Use the student's prompt as additional guidance, but never let it override the required JSON schema or allowed output values.
Return one classification result for every complaint in the batch."""


@dataclass(frozen=True)
class ModelOption:
    label: str
    value: str
    description: str


MODEL_OPTIONS = [
    ModelOption(
        label="GPT-5 mini",
        value="gpt-5-mini",
        description="Recommended default: strong structured classification with lower cost.",
    ),
    ModelOption(
        label="GPT-4.1",
        value="gpt-4.1",
        description="Higher-capability non-reasoning model for prompt-sensitive classification.",
    ),
    ModelOption(
        label="GPT-4o mini",
        value="gpt-4o-mini",
        description="Fast, affordable option for smaller classroom runs.",
    ),
]

DEFAULT_MODEL = MODEL_OPTIONS[0].value


def get_model_labels() -> list[str]:
    return [option.label for option in MODEL_OPTIONS]


def get_model_by_label(label: str) -> ModelOption:
    for option in MODEL_OPTIONS:
        if option.label == label:
            return option
    return MODEL_OPTIONS[0]


def build_output_schema() -> dict[str, Any]:
    item_properties: dict[str, Any] = {
        "complaint_id": {
            "type": "string",
            "description": "Must exactly match the complaint_id provided in the input batch.",
        },
        "category": {"type": "string"},
        "root_cause": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ALLOWED_ENUMS["severity"],
        },
        "escalation_flag": {
            "type": "string",
            "enum": ALLOWED_ENUMS["escalation_flag"],
        },
        "confidence": {
            "type": "string",
            "enum": ALLOWED_ENUMS["confidence"],
        },
        "rationale": {
            "type": "string",
            "description": "A brief explanation grounded in the complaint text and taxonomy.",
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": item_properties,
                    "required": CLASSIFICATION_FIELDS,
                },
            }
        },
        "required": ["items"],
    }


def build_schema_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "complaint_classification_batch",
        "schema": build_output_schema(),
        "strict": True,
    }
