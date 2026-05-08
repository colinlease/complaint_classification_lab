from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

import pandas as pd

from src.config import (
    CLASSIFICATION_FIELDS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_RETRIES,
    REQUIRED_COMPLAINT_COLUMNS,
    RESULT_METADATA_COLUMNS,
)
from src.llm_client import ComplaintLLMClient, LLMClientError
from src.parser import ParsedResponseError, extract_json_payload, validate_and_align_results
from src.prompt_builder import build_system_instructions, build_user_prompt


ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class ClassificationRunResult:
    results: pd.DataFrame
    summary: dict[str, Any]
    warnings: list[str]
    technical_log: list[str]


def chunk_dataframe(dataframe: pd.DataFrame, batch_size: int) -> list[pd.DataFrame]:
    return [
        dataframe.iloc[index : index + batch_size].copy()
        for index in range(0, len(dataframe), batch_size)
    ]


def _build_failed_rows(
    batch_df: pd.DataFrame,
    error_message: str,
    error_type: str,
    processing_status: str,
    batch_number: int,
    api_attempts: int,
    repair_used: bool,
    response_id: str,
    model_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, source_row in batch_df.iterrows():
        row = source_row.to_dict()
        row.update({field: "" for field in CLASSIFICATION_FIELDS if field != "complaint_id"})
        row.update(
            {
                "processing_status": processing_status,
                "error_message": error_message,
                "error_type": error_type,
                "batch_number": batch_number,
                "api_attempts": api_attempts,
                "repair_used": repair_used,
                "response_id": response_id,
                "model_name": model_name,
            }
        )
        rows.append(row)
    return rows


def classify_complaints(
    dataframe: pd.DataFrame,
    taxonomy_text: str,
    student_prompt: str,
    api_key: str,
    model_name: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    progress_callback: ProgressCallback | None = None,
) -> ClassificationRunResult:
    client = ComplaintLLMClient(api_key=api_key, model=model_name)
    instructions = build_system_instructions()

    all_rows: list[dict[str, Any]] = []
    technical_log: list[str] = []
    warnings: list[str] = []
    batches = chunk_dataframe(dataframe, batch_size=batch_size)

    total_rows = len(dataframe)
    failed_rows = 0
    partial_rows = 0
    parse_error_rows = 0
    repaired_batches = 0
    total_attempts = 0
    retry_attempts = 0

    for batch_index, batch_df in enumerate(batches, start=1):
        user_prompt = build_user_prompt(
            complaints=batch_df[REQUIRED_COMPLAINT_COLUMNS],
            taxonomy_text=taxonomy_text,
            student_prompt=student_prompt,
        )
        expected_ids = batch_df["complaint_id"].astype(str).tolist()

        try:
            call_result = client.classify_batch(
                instructions=instructions,
                user_input=user_prompt,
                max_retries=max_retries,
            )
            total_attempts += call_result.attempts_used
            retry_attempts += max(call_result.attempts_used - 1, 0)
            raw_payload = extract_json_payload(call_result.raw_text)
        except ParsedResponseError:
            technical_log.append(
                f"Batch {batch_index}: initial JSON parse failed; attempting repair."
            )
            try:
                repair_result = client.repair_json(
                    malformed_response=call_result.raw_text,
                    max_retries=1,
                )
                total_attempts += repair_result.attempts_used
                retry_attempts += max(repair_result.attempts_used - 1, 0)
                repaired_batches += 1
                raw_payload = extract_json_payload(repair_result.raw_text)
                call_result = repair_result
            except LLMClientError as exc:
                total_attempts += exc.attempts_used
                retry_attempts += max(exc.attempts_used - 1, 0)
                failed_rows += len(batch_df)
                parse_error_rows += len(batch_df)
                technical_log.append(f"Batch {batch_index}: repair API failure. {exc}")
                all_rows.extend(
                    _build_failed_rows(
                        batch_df=batch_df,
                        error_message="This batch could not be repaired into valid structured output.",
                        error_type="parse_error",
                        processing_status="parse_error",
                        batch_number=batch_index,
                        api_attempts=call_result.attempts_used + exc.attempts_used,
                        repair_used=True,
                        response_id="",
                        model_name=model_name,
                    )
                )
                if progress_callback:
                    progress_callback(
                        {
                            "batch_number": batch_index,
                            "total_batches": len(batches),
                            "completed_rows": len(all_rows),
                            "failed_rows": failed_rows,
                            "partial_rows": partial_rows,
                        }
                    )
                continue
            except Exception as exc:
                failed_rows += len(batch_df)
                parse_error_rows += len(batch_df)
                technical_log.append(f"Batch {batch_index}: repair failed. {exc}")
                all_rows.extend(
                    _build_failed_rows(
                        batch_df=batch_df,
                        error_message="This batch could not be parsed into valid structured output.",
                        error_type="parse_error",
                        processing_status="parse_error",
                        batch_number=batch_index,
                        api_attempts=call_result.attempts_used,
                        repair_used=True,
                        response_id="",
                        model_name=model_name,
                    )
                )
                if progress_callback:
                    progress_callback(
                        {
                            "batch_number": batch_index,
                            "total_batches": len(batches),
                            "completed_rows": len(all_rows),
                            "failed_rows": failed_rows,
                            "partial_rows": partial_rows,
                        }
                    )
                continue
        except LLMClientError as exc:
            total_attempts += exc.attempts_used
            retry_attempts += max(exc.attempts_used - 1, 0)
            failed_rows += len(batch_df)
            technical_log.append(f"Batch {batch_index}: API failure. {exc}")
            all_rows.extend(
                _build_failed_rows(
                    batch_df=batch_df,
                    error_message=str(exc),
                    error_type="api_error",
                    processing_status="failed",
                    batch_number=batch_index,
                    api_attempts=exc.attempts_used,
                    repair_used=False,
                    response_id="",
                    model_name=model_name,
                )
            )
            if progress_callback:
                progress_callback(
                    {
                        "batch_number": batch_index,
                        "total_batches": len(batches),
                        "completed_rows": len(all_rows),
                        "failed_rows": failed_rows,
                        "partial_rows": partial_rows,
                    }
                )
            continue

        try:
            parsed_result = validate_and_align_results(raw_payload, expected_ids=expected_ids)
            warnings.extend(parsed_result.warnings)
            technical_log.extend([f"Batch {batch_index}: {warning}" for warning in parsed_result.warnings])

            aligned_by_id = {row["complaint_id"]: row for row in parsed_result.rows}
            for _, source_row in batch_df.iterrows():
                source_dict = source_row.to_dict()
                complaint_id = str(source_dict["complaint_id"])
                parsed_row = aligned_by_id[complaint_id]
                merged_row = source_dict.copy()
                for field in CLASSIFICATION_FIELDS:
                    if field == "complaint_id":
                        continue
                    merged_row[field] = parsed_row.get(field, "")
                merged_row["processing_status"] = parsed_row["processing_status"]
                merged_row["error_message"] = parsed_row["error_message"]
                merged_row["error_type"] = parsed_row["error_type"]
                merged_row["batch_number"] = batch_index
                merged_row["api_attempts"] = call_result.attempts_used
                merged_row["repair_used"] = call_result.repair_used
                merged_row["response_id"] = call_result.response_id
                merged_row["model_name"] = model_name
                all_rows.append(merged_row)

                if merged_row["processing_status"] == "partial_error":
                    partial_rows += 1
                elif merged_row["processing_status"] in {"parse_error", "failed"}:
                    failed_rows += 1
                    if merged_row["processing_status"] == "parse_error":
                        parse_error_rows += 1

        except Exception as exc:
            failed_rows += len(batch_df)
            technical_log.append(f"Batch {batch_index}: validation failure. {exc}")
            all_rows.extend(
                _build_failed_rows(
                    batch_df=batch_df,
                    error_message="The model response could not be validated against the required schema.",
                    error_type="validation_error",
                    processing_status="failed",
                    batch_number=batch_index,
                    api_attempts=call_result.attempts_used,
                    repair_used=call_result.repair_used,
                    response_id=call_result.response_id,
                    model_name=model_name,
                )
            )

        if progress_callback:
            progress_callback(
                {
                    "batch_number": batch_index,
                    "total_batches": len(batches),
                    "completed_rows": len(all_rows),
                    "failed_rows": failed_rows,
                    "partial_rows": partial_rows,
                }
            )

    results_df = pd.DataFrame(all_rows)
    ordered_columns = (
        ["source_row_number"]
        + REQUIRED_COMPLAINT_COLUMNS
        + [field for field in CLASSIFICATION_FIELDS if field != "complaint_id"]
        + RESULT_METADATA_COLUMNS
    )
    existing_columns = [column for column in ordered_columns if column in results_df.columns]
    results_df = results_df[existing_columns].copy()

    summary = {
        "total_rows": total_rows,
        "completed_rows": int((results_df["processing_status"] == "success").sum())
        if not results_df.empty
        else 0,
        "partial_rows": partial_rows,
        "failed_rows": failed_rows,
        "parse_error_rows": parse_error_rows,
        "repaired_batches": repaired_batches,
        "total_batches": len(batches),
        "total_attempts": total_attempts,
        "retry_attempts": retry_attempts,
    }

    return ClassificationRunResult(
        results=results_df,
        summary=summary,
        warnings=warnings,
        technical_log=technical_log,
    )
