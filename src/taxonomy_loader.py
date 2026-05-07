from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pandas as pd

from src.config import REQUIRED_TAXONOMY_COLUMNS, REQUIRED_TAXONOMY_SHEETS


class TaxonomyValidationError(Exception):
    """Friendly validation error for taxonomy workbook uploads."""


@dataclass
class TaxonomyLoadResult:
    sheet_frames: dict[str, pd.DataFrame]
    parsed_text: str
    preview_text: str
    warnings: list[str]
    file_name: str


def _normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    normalized = normalized.fillna("")
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str).str.strip()
    return normalized


def _format_row(label: str, values: dict[str, str]) -> str:
    lines = [f"- {label}: {values.get(label.lower(), '')}"]
    for key, value in values.items():
        if key == label.lower():
            continue
        lines.append(f"  {key.replace('_', ' ').title()}: {value or 'n/a'}")
    return "\n".join(lines)


def _build_parsed_taxonomy_text(sheet_frames: dict[str, pd.DataFrame]) -> str:
    sections: list[str] = []

    categories = sheet_frames["Categories"]
    category_lines = ["[Categories]"]
    for _, row in categories.iterrows():
        category_lines.append(
            _format_row(
                "Category",
                {
                    "category": row.get("category", ""),
                    "definition": row.get("definition", ""),
                    "examples": row.get("examples", ""),
                    "non_examples": row.get("non_examples", ""),
                },
            )
        )
    sections.append("\n".join(category_lines))

    root_causes = sheet_frames["Root_Causes"]
    root_lines = ["[Root Causes]"]
    for _, row in root_causes.iterrows():
        root_lines.append(
            _format_row(
                "Root_Cause",
                {
                    "root_cause": row.get("root_cause", ""),
                    "definition": row.get("definition", ""),
                    "examples": row.get("examples", ""),
                    "non_examples": row.get("non_examples", ""),
                },
            )
        )
    sections.append("\n".join(root_lines))

    severity_rules = sheet_frames["Severity_Rules"]
    severity_lines = ["[Severity Rules]"]
    for _, row in severity_rules.iterrows():
        severity_lines.append(
            _format_row(
                "Severity",
                {
                    "severity": row.get("severity", ""),
                    "definition": row.get("definition", ""),
                    "examples": row.get("examples", ""),
                },
            )
        )
    sections.append("\n".join(severity_lines))

    escalation_rules = sheet_frames["Escalation_Rules"]
    escalation_lines = ["[Escalation Rules]"]
    for _, row in escalation_rules.iterrows():
        escalation_lines.append(
            _format_row(
                "Escalation_Flag",
                {
                    "escalation_flag": row.get("escalation_flag", ""),
                    "definition": row.get("definition", ""),
                    "examples": row.get("examples", ""),
                },
            )
        )
    sections.append("\n".join(escalation_lines))

    prompt_instructions = sheet_frames["Prompt_Instructions"]
    instruction_lines = ["[Prompt Instructions]"]
    for _, row in prompt_instructions.iterrows():
        instruction_lines.append(
            _format_row(
                "Instruction_Type",
                {
                    "instruction_type": row.get("instruction_type", ""),
                    "instruction": row.get("instruction", ""),
                },
            )
        )
    sections.append("\n".join(instruction_lines))

    return "\n\n".join(sections)


def load_taxonomy_workbook(file_bytes: bytes, file_name: str) -> TaxonomyLoadResult:
    if not file_name.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise TaxonomyValidationError(
            "Unsupported taxonomy file type. Please upload an Excel workbook."
        )

    try:
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
    except Exception as exc:
        raise TaxonomyValidationError(
            "The taxonomy workbook could not be opened. Please check the Excel file."
        ) from exc

    available_sheets = set(excel_file.sheet_names)
    missing_sheets = [sheet for sheet in REQUIRED_TAXONOMY_SHEETS if sheet not in available_sheets]
    if missing_sheets:
        missing_list = ", ".join(missing_sheets)
        raise TaxonomyValidationError(
            f"The taxonomy workbook is missing required sheets: {missing_list}."
        )

    sheet_frames: dict[str, pd.DataFrame] = {}
    column_errors: list[str] = []
    warnings: list[str] = []

    for sheet_name in REQUIRED_TAXONOMY_SHEETS:
        raw_frame = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, dtype=str)
        if raw_frame.empty:
            warnings.append(
                f"The sheet '{sheet_name}' is present but empty. Classification quality may be poor."
            )
        normalized = _normalize_columns(raw_frame)
        required_columns = REQUIRED_TAXONOMY_COLUMNS[sheet_name]
        missing_columns = [column for column in required_columns if column not in normalized.columns]
        if missing_columns:
            missing_list = ", ".join(missing_columns)
            column_errors.append(f"{sheet_name}: {missing_list}")
            continue
        sheet_frames[sheet_name] = normalized[required_columns].copy()

    if column_errors:
        joined = "; ".join(column_errors)
        raise TaxonomyValidationError(
            f"The taxonomy workbook has missing required columns in these sheets: {joined}."
        )

    parsed_text = _build_parsed_taxonomy_text(sheet_frames)
    preview_text = parsed_text[:8000]

    return TaxonomyLoadResult(
        sheet_frames=sheet_frames,
        parsed_text=parsed_text,
        preview_text=preview_text,
        warnings=warnings,
        file_name=file_name,
    )
