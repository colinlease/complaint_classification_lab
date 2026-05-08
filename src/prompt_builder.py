from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.config import ALLOWED_ENUMS, ASSIGNMENT_CONTEXT, CLASSIFICATION_FIELDS


def build_system_instructions() -> str:
    allowed_values = "\n".join(
        f"- {field}: {', '.join(values)}" for field, values in ALLOWED_ENUMS.items()
    )
    required_fields = "\n".join(f"- {field}" for field in CLASSIFICATION_FIELDS)

    return f"""{ASSIGNMENT_CONTEXT}

Non-negotiable requirements:
1. Return only valid JSON.
2. The JSON must match the provided schema exactly.
3. Return one item per complaint and preserve complaint_id exactly.
4. Use the allowed values below for enumerated fields:
{allowed_values}
5. Required output fields for every item:
{required_fields}
6. If the complaint is ambiguous, still classify it with the best available judgment and use low confidence when appropriate.
7. Keep rationale concise, grounded in evidence, and suitable for classroom review."""


def build_user_prompt(
    complaints: pd.DataFrame,
    taxonomy_text: str,
    student_prompt: str,
) -> str:
    complaint_records: list[dict[str, Any]] = complaints.to_dict(orient="records")
    complaint_json = json.dumps(complaint_records, indent=2, ensure_ascii=True)

    return f"""Assignment taxonomy:
{taxonomy_text}

Student-written classification guidance:
{student_prompt.strip() or "No extra student guidance provided."}

Input complaint batch:
{complaint_json}

Return only a JSON object with a single top-level key called "items".
Each object in "items" must represent exactly one complaint from the input batch."""
