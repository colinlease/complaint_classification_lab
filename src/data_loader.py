from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from src.config import REQUIRED_COMPLAINT_COLUMNS


class DataValidationError(Exception):
    """Friendly validation error for complaint data uploads."""


@dataclass
class SheetInspection:
    sheet_name: str
    columns: list[str]
    missing_columns: list[str]
    valid: bool


@dataclass
class DataLoadResult:
    dataframe: pd.DataFrame
    file_name: str
    file_type: str
    selected_sheet: str | None
    recommended_sheet: str | None
    sheet_inspections: list[SheetInspection]


def normalize_column_name(column: Any) -> str:
    return str(column).strip().lower()


def normalize_dataframe_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    renamed = dataframe.copy()
    renamed.columns = [normalize_column_name(col) for col in renamed.columns]
    return renamed


def _finalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    finalized = dataframe.copy()
    finalized = finalized.fillna("")
    for column in finalized.columns:
        finalized[column] = finalized[column].astype(str).str.strip()
    return finalized


def _validate_required_columns(dataframe: pd.DataFrame) -> list[str]:
    normalized_columns = set(normalize_dataframe_columns(dataframe).columns)
    return [column for column in REQUIRED_COMPLAINT_COLUMNS if column not in normalized_columns]


def inspect_excel_sheets(file_bytes: bytes) -> list[SheetInspection]:
    try:
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise DataValidationError(
            "The uploaded complaint file could not be opened as an Excel workbook."
        ) from exc

    inspections: list[SheetInspection] = []
    for sheet_name in excel_file.sheet_names:
        try:
            preview = pd.read_excel(
                BytesIO(file_bytes),
                sheet_name=sheet_name,
                dtype=str,
                nrows=0,
            )
        except Exception:
            preview = pd.DataFrame()
        normalized_columns = [normalize_column_name(col) for col in preview.columns]
        missing = [col for col in REQUIRED_COMPLAINT_COLUMNS if col not in normalized_columns]
        inspections.append(
            SheetInspection(
                sheet_name=sheet_name,
                columns=normalized_columns,
                missing_columns=missing,
                valid=not missing,
            )
        )
    return inspections


def get_recommended_sheet(inspections: list[SheetInspection]) -> str | None:
    for inspection in inspections:
        if inspection.valid:
            return inspection.sheet_name
    if inspections:
        return inspections[0].sheet_name
    return None


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise DataValidationError(
            "The uploaded CSV could not be read. Please confirm the file is a valid CSV."
        ) from exc


def _read_excel(file_bytes: bytes, sheet_name: str | None) -> pd.DataFrame:
    try:
        return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, dtype=str)
    except Exception as exc:
        label = f"sheet '{sheet_name}'" if sheet_name else "the workbook"
        raise DataValidationError(
            f"The uploaded Excel file could not be read from {label}. Please check the file format."
        ) from exc


def load_complaints_dataset(
    file_bytes: bytes,
    file_name: str,
    selected_sheet: str | None = None,
) -> DataLoadResult:
    lower_name = file_name.lower()
    sheet_inspections: list[SheetInspection] = []
    recommended_sheet: str | None = None

    if lower_name.endswith(".csv"):
        raw_dataframe = _read_csv(file_bytes)
        file_type = "csv"
    elif lower_name.endswith((".xlsx", ".xlsm", ".xls")):
        sheet_inspections = inspect_excel_sheets(file_bytes)
        recommended_sheet = get_recommended_sheet(sheet_inspections)
        sheet_to_read = selected_sheet or recommended_sheet
        raw_dataframe = _read_excel(file_bytes, sheet_to_read)
        file_type = "excel"
        selected_sheet = sheet_to_read
    else:
        raise DataValidationError(
            "Unsupported complaint data file type. Please upload a CSV or Excel file."
        )

    if raw_dataframe.empty:
        raise DataValidationError(
            "The uploaded complaint dataset is empty. Please upload a file with complaint records."
        )

    normalized = normalize_dataframe_columns(raw_dataframe)
    missing_columns = _validate_required_columns(normalized)
    if missing_columns:
        missing_list = ", ".join(missing_columns)
        raise DataValidationError(
            f"The complaint dataset is missing required columns: {missing_list}."
        )

    finalized = _finalize_dataframe(normalized)
    finalized = finalized[REQUIRED_COMPLAINT_COLUMNS].copy()
    finalized.insert(0, "source_row_number", range(1, len(finalized) + 1))

    return DataLoadResult(
        dataframe=finalized,
        file_name=file_name,
        file_type=file_type,
        selected_sheet=selected_sheet,
        recommended_sheet=recommended_sheet,
        sheet_inspections=sheet_inspections,
    )
