from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.config import ALLOWED_ENUMS, CLASSIFICATION_FIELDS


class ParsedResponseError(Exception):
    """Raised when an LLM response cannot be parsed into structured JSON."""


@dataclass
class ParsedBatchResult:
    rows: list[dict[str, Any]]
    warnings: list[str]


def _strip_code_fences(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_balanced_json(text: str, opening: str, closing: str) -> str | None:
    start = text.find(opening)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json_payload(raw_text: str) -> Any:
    text = _strip_code_fences(raw_text)
    candidates = [text]

    object_candidate = _extract_balanced_json(text, "{", "}")
    if object_candidate and object_candidate not in candidates:
        candidates.append(object_candidate)

    array_candidate = _extract_balanced_json(text, "[", "]")
    if array_candidate and array_candidate not in candidates:
        candidates.append(array_candidate)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ParsedResponseError("The model response was not valid JSON.")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_enum(field_name: str, value: Any) -> tuple[str, str | None]:
    normalized = _normalize_text(value).lower()
    if normalized in ALLOWED_ENUMS[field_name]:
        return normalized, None
    return "", f"Invalid value for {field_name}: {value}"


def validate_and_align_results(payload: Any, expected_ids: list[str]) -> ParsedBatchResult:
    if isinstance(payload, dict):
        items = payload.get("items")
    elif isinstance(payload, list):
        items = payload
    else:
        raise ParsedResponseError("The model response did not contain a valid items list.")

    if not isinstance(items, list):
        raise ParsedResponseError("The model response did not contain a valid items list.")

    expected_set = {str(value) for value in expected_ids}
    parsed_by_id: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            warnings.append("One returned item was ignored because it was not an object.")
            continue

        complaint_id = _normalize_text(item.get("complaint_id"))
        if not complaint_id:
            warnings.append("One returned item was ignored because complaint_id was blank.")
            continue
        if complaint_id not in expected_set:
            warnings.append(f"Ignored unexpected complaint_id returned by the model: {complaint_id}.")
            continue
        if complaint_id in parsed_by_id:
            warnings.append(f"Duplicate result returned for complaint_id {complaint_id}; kept the first one.")
            continue

        row_errors: list[str] = []
        normalized: dict[str, Any] = {"complaint_id": complaint_id}

        for field in ["category", "subcategory", "root_cause", "rationale"]:
            value = _normalize_text(item.get(field))
            normalized[field] = value
            if not value:
                row_errors.append(f"Missing value for {field}.")

        for field in ["emerging_issue_relevance", "severity", "escalation_flag", "confidence"]:
            normalized_value, error = _normalize_enum(field, item.get(field))
            normalized[field] = normalized_value
            if error:
                row_errors.append(error)

        normalized["processing_status"] = "success" if not row_errors else "partial_error"
        normalized["error_message"] = " ".join(row_errors)
        normalized["error_type"] = "" if not row_errors else "validation_error"
        parsed_by_id[complaint_id] = normalized

    rows: list[dict[str, Any]] = []
    for expected_id in expected_ids:
        if expected_id in parsed_by_id:
            rows.append(parsed_by_id[expected_id])
            continue

        rows.append(
            {
                "complaint_id": expected_id,
                "category": "",
                "subcategory": "",
                "root_cause": "",
                "emerging_issue_relevance": "",
                "severity": "",
                "escalation_flag": "",
                "confidence": "",
                "rationale": "",
                "processing_status": "parse_error",
                "error_message": "No valid classification result was returned for this complaint.",
                "error_type": "missing_result",
            }
        )

    for row in rows:
        for field in CLASSIFICATION_FIELDS:
            row.setdefault(field, "")

    return ParsedBatchResult(rows=rows, warnings=warnings)
