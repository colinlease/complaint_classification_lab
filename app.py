from __future__ import annotations

import hashlib
import os
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.charts import build_count_chart
from src.classifier import ClassificationRunResult, classify_complaints
from src.config import (
    APP_ICON,
    APP_TITLE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MODEL,
    DEFAULT_STUDENT_PROMPT,
    DEFAULT_TEST_SAMPLE_SIZE,
    DEFAULT_MAX_RETRIES,
    MODEL_OPTIONS,
)
from src.data_loader import (
    DataLoadResult,
    DataValidationError,
    get_recommended_sheet,
    inspect_excel_sheets,
    load_complaints_dataset,
)
from src.llm_client import ComplaintLLMClient, LLMClientError
from src.styles import apply_styles
from src.taxonomy_loader import TaxonomyLoadResult, TaxonomyValidationError, load_taxonomy_workbook
from src.ui_components import (
    dataframe_to_excel_bytes,
    render_friendly_exception,
    render_metric_cards,
    render_section_intro,
    render_status_badges,
)


load_dotenv()

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)


def file_signature(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.md5(file_bytes).hexdigest()
    return f"{file_name}:{digest}"


def input_signature(
    dataset_signature: str,
    taxonomy_signature: str,
    dataset_result: DataLoadResult | None,
    taxonomy_result: TaxonomyLoadResult | None,
    student_prompt: str,
    model_name: str,
) -> str:
    raw = "|".join(
        [
            dataset_signature,
            taxonomy_signature,
            dataset_result.file_name if dataset_result else "",
            dataset_result.selected_sheet or "" if dataset_result else "",
            taxonomy_result.file_name if taxonomy_result else "",
            student_prompt.strip(),
            model_name,
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def ensure_session_defaults() -> None:
    defaults = {
        "dataset_result": None,
        "dataset_signature": "",
        "dataset_sheet_choice": None,
        "taxonomy_result": None,
        "taxonomy_signature": "",
        "student_prompt": DEFAULT_STUDENT_PROMPT,
        "test_run_result": None,
        "full_run_result": None,
        "test_run_signature": "",
        "full_run_signature": "",
        "selected_model": DEFAULT_MODEL,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_run_outputs() -> None:
    st.session_state["test_run_result"] = None
    st.session_state["full_run_result"] = None
    st.session_state["test_run_signature"] = ""
    st.session_state["full_run_signature"] = ""


def render_run_summary(run_result: ClassificationRunResult) -> None:
    summary = run_result.summary
    render_metric_cards(
        [
            ("Rows", str(summary["total_rows"])),
            ("Completed", str(summary["completed_rows"])),
            ("Partial", str(summary["partial_rows"])),
            ("Failed", str(summary["failed_rows"])),
            ("Parse Errors", str(summary["parse_error_rows"])),
            ("Retries", str(summary["retry_attempts"])),
        ]
    )

    if run_result.warnings:
        st.warning(f"{len(run_result.warnings)} warning(s) were recorded during processing.")

    if run_result.technical_log:
        with st.expander("Technical details"):
            st.text("\n".join(run_result.technical_log))


def render_results_dashboard(results_df: pd.DataFrame) -> None:
    st.dataframe(results_df, use_container_width=True, hide_index=True)

    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        st.plotly_chart(
            build_count_chart(results_df, "category", "Category Counts"),
            use_container_width=True,
        )
        st.plotly_chart(
            build_count_chart(results_df, "severity", "Severity Distribution", color="#d97706"),
            use_container_width=True,
        )
        st.plotly_chart(
            build_count_chart(
                results_df,
                "emerging_issue_relevance",
                "Emerging Issue Relevance",
                color="#0f766e",
            ),
            use_container_width=True,
        )
    with chart_col_2:
        st.plotly_chart(
            build_count_chart(results_df, "root_cause", "Root Cause Counts", color="#0f766e"),
            use_container_width=True,
        )
        st.plotly_chart(
            build_count_chart(results_df, "confidence", "Confidence Distribution", color="#e11d48"),
            use_container_width=True,
        )
        st.plotly_chart(
            build_count_chart(results_df, "escalation_flag", "Escalation Flags", color="#334155"),
            use_container_width=True,
        )

    st.markdown("### Focus Cases")
    focus_col_1, focus_col_2, focus_col_3 = st.columns(3)
    with focus_col_1:
        st.markdown("**Low-confidence cases**")
        st.dataframe(
            results_df[results_df["confidence"] == "low"],
            use_container_width=True,
            hide_index=True,
        )
    with focus_col_2:
        st.markdown("**High-severity cases**")
        st.dataframe(
            results_df[results_df["severity"] == "high"],
            use_container_width=True,
            hide_index=True,
        )
    with focus_col_3:
        st.markdown("**Escalation-flagged cases**")
        st.dataframe(
            results_df[results_df["escalation_flag"] == "yes"],
            use_container_width=True,
            hide_index=True,
        )


def main() -> None:
    ensure_session_defaults()
    apply_styles()

    st.markdown(
        f"""
        <div style="color: var(--text); font-family: inherit; font-size: 2.4rem; font-weight: 600; letter-spacing: 0; line-height: 1.05; margin: 0 0 0.35rem 0;">
            {APP_TITLE}
        </div>
        <div class="page-caption">
            A guided classroom app for taxonomy design, prompt refinement, structured AI classification, and business interpretation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## Run Setup")
        typed_api_key = st.text_input(
            "OpenAI API key",
            type="password",
            help="Paste a personal OpenAI API key or rely on OPENAI_API_KEY from a local .env file.",
        ).strip()
        env_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        resolved_api_key = typed_api_key or env_api_key

        if env_api_key and not typed_api_key:
            st.caption("Using `OPENAI_API_KEY` from the local `.env` file.")

        model_label_map = {option.label: option.value for option in MODEL_OPTIONS}
        model_labels = list(model_label_map.keys())
        default_index = next(
            (
                index
                for index, option in enumerate(MODEL_OPTIONS)
                if option.value == st.session_state["selected_model"]
            ),
            0,
        )
        selected_label = st.selectbox("OpenAI model", options=model_labels, index=default_index)
        st.session_state["selected_model"] = model_label_map[selected_label]
        selected_model = st.session_state["selected_model"]

        selected_option = next(option for option in MODEL_OPTIONS if option.value == selected_model)
        st.caption(selected_option.description)

        if st.button("Test API connection", use_container_width=True):
            if not resolved_api_key:
                st.error("Add an OpenAI API key first.")
            else:
                try:
                    client = ComplaintLLMClient(api_key=resolved_api_key, model=selected_model)
                    response_text = client.test_connection()
                    st.success(f"API connection succeeded. Response: {response_text}")
                except LLMClientError as exc:
                    st.error(str(exc))

    dataset_result: DataLoadResult | None = st.session_state["dataset_result"]
    taxonomy_result: TaxonomyLoadResult | None = st.session_state["taxonomy_result"]
    student_prompt = st.session_state.get("student_prompt", DEFAULT_STUDENT_PROMPT)
    current_signature = input_signature(
        st.session_state["dataset_signature"],
        st.session_state["taxonomy_signature"],
        dataset_result,
        taxonomy_result,
        student_prompt,
        selected_model,
    )

    tabs = st.tabs(["Start", "Data", "Taxonomy", "Prompt", "Test Run", "Full Run", "Results"])

    with tabs[0]:
        render_section_intro(
            "Classroom Workflow",
            "Upload complaint data and taxonomy files, refine the classification prompt, test on a small sample, then run the full dataset and export the results.",
        )
        render_status_badges(
            [
                ("API key ready" if resolved_api_key else "API key missing", "success" if resolved_api_key else "warning"),
                ("Data ready" if dataset_result else "Data missing", "success" if dataset_result else "warning"),
                ("Taxonomy ready" if taxonomy_result else "Taxonomy missing", "success" if taxonomy_result else "warning"),
                ("Prompt ready" if student_prompt.strip() else "Prompt missing", "success" if student_prompt.strip() else "warning"),
            ]
        )
        render_metric_cards(
            [
                ("Models", str(len(MODEL_OPTIONS))),
                ("Batch Size", str(DEFAULT_BATCH_SIZE)),
                ("Test Sample", str(DEFAULT_TEST_SAMPLE_SIZE)),
                ("Full Results", "Ready" if st.session_state["full_run_result"] else "Pending"),
                ("Downloads", "Enabled" if st.session_state["full_run_result"] else "Later"),
            ]
        )

        st.markdown(
            """
            1. Upload the complaint dataset provided by your instructor. 
            2. Upload your completed taxonomy workbook with all required sheets.
            3. Include your classification prompt.
            4. Run the 5-record test sample to debug your prompt and taxonomy.
            5. Run the full dataset and export the classified output.
            """
        )

    with tabs[1]:
        render_section_intro(
            "Complaint Dataset",
            "Upload a CSV or Excel file. If the Excel workbook has multiple sheets, the app will recommend the first sheet that contains all required columns.",
        )

        dataset_file = st.file_uploader(
            "Upload complaint dataset",
            type=["csv", "xlsx", "xlsm", "xls"],
            key="dataset_file_uploader",
        )

        if dataset_file is not None:
            file_bytes = dataset_file.getvalue()
            signature = file_signature(dataset_file.name, file_bytes)
            if signature != st.session_state["dataset_signature"]:
                st.session_state["dataset_signature"] = signature
                st.session_state["dataset_result"] = None
                st.session_state["dataset_sheet_choice"] = None
                clear_run_outputs()

            selected_sheet = None
            if dataset_file.name.lower().endswith((".xlsx", ".xlsm", ".xls")):
                try:
                    inspections = inspect_excel_sheets(file_bytes)
                    sheet_names = [inspection.sheet_name for inspection in inspections]
                    recommended_sheet = get_recommended_sheet(inspections)
                    default_sheet = st.session_state["dataset_sheet_choice"] or recommended_sheet
                    default_index = sheet_names.index(default_sheet) if default_sheet in sheet_names else 0
                    selected_sheet = st.selectbox(
                        "Select complaint sheet",
                        options=sheet_names,
                        index=default_index,
                        help="The app recommends the first sheet with all required columns.",
                    )
                    st.session_state["dataset_sheet_choice"] = selected_sheet
                    inspection_rows = [
                        {
                            "sheet_name": inspection.sheet_name,
                            "valid": "yes" if inspection.valid else "no",
                            "missing_columns": ", ".join(inspection.missing_columns),
                        }
                        for inspection in inspections
                    ]
                    with st.expander("Sheet scan details"):
                        st.dataframe(pd.DataFrame(inspection_rows), use_container_width=True, hide_index=True)
                except DataValidationError as exc:
                    render_friendly_exception(str(exc), technical_details=repr(exc))

            try:
                dataset_result = load_complaints_dataset(
                    file_bytes=file_bytes,
                    file_name=dataset_file.name,
                    selected_sheet=selected_sheet,
                )
                st.session_state["dataset_result"] = dataset_result
                st.success(
                    f"Loaded {len(dataset_result.dataframe)} complaint rows from {dataset_result.file_name}."
                )
                st.dataframe(dataset_result.dataframe.head(20), use_container_width=True, hide_index=True)
            except DataValidationError as exc:
                st.session_state["dataset_result"] = None
                render_friendly_exception(str(exc), technical_details=repr(exc))

        else:
            st.info("Upload a complaint dataset to continue.")

    with tabs[2]:
        render_section_intro(
            "Taxonomy Workbook",
            "Upload the taxonomy Excel workbook with the required sheets. The app will validate the workbook structure and build the taxonomy text used inside the backend prompt.",
        )

        taxonomy_file = st.file_uploader(
            "Upload taxonomy workbook",
            type=["xlsx", "xlsm", "xls"],
            key="taxonomy_file_uploader",
        )

        if taxonomy_file is not None:
            file_bytes = taxonomy_file.getvalue()
            signature = file_signature(taxonomy_file.name, file_bytes)
            if signature != st.session_state["taxonomy_signature"]:
                st.session_state["taxonomy_signature"] = signature
                st.session_state["taxonomy_result"] = None
                clear_run_outputs()

            try:
                taxonomy_result = load_taxonomy_workbook(
                    file_bytes=file_bytes,
                    file_name=taxonomy_file.name,
                )
                st.session_state["taxonomy_result"] = taxonomy_result
                st.success("Taxonomy workbook validated successfully.")

                if taxonomy_result.warnings:
                    for warning in taxonomy_result.warnings:
                        st.warning(warning)

                for sheet_name, sheet_frame in taxonomy_result.sheet_frames.items():
                    with st.expander(f"{sheet_name} preview"):
                        st.dataframe(sheet_frame.head(20), use_container_width=True, hide_index=True)

                with st.expander("Parsed taxonomy preview"):
                    st.text(taxonomy_result.preview_text)
            except TaxonomyValidationError as exc:
                st.session_state["taxonomy_result"] = None
                render_friendly_exception(str(exc), technical_details=repr(exc))
        else:
            st.info("Upload a taxonomy workbook to continue.")

    with tabs[3]:
        render_section_intro(
            "Classification Prompt",
            "Enter your prompt here.",
        )

        updated_prompt = st.text_area(
            "Student classification prompt",
            value=st.session_state["student_prompt"],
            height=280,
            help="This prompt can influence classification logic, but it cannot change the output schema.",
        )
        if updated_prompt != st.session_state["student_prompt"]:
            st.session_state["student_prompt"] = updated_prompt
            student_prompt = updated_prompt
            clear_run_outputs()

        st.info(
            "Guardrail: the app always requires valid JSON with the fixed output fields. Students can improve reasoning, not break the schema."
        )

        if st.session_state["taxonomy_result"] is not None:
            with st.expander("Taxonomy text that will be injected into the backend prompt"):
                st.text(st.session_state["taxonomy_result"].preview_text)

    with tabs[4]:
        render_section_intro(
            "Test Run",
            "Run the classifier on a random sample of 5 complaints. Use this to debug prompt wording before spending tokens on the full dataset.",
        )

        prerequisites_ready = all(
            [
                resolved_api_key,
                st.session_state["dataset_result"] is not None,
                st.session_state["taxonomy_result"] is not None,
                st.session_state["student_prompt"].strip(),
            ]
        )
        if not prerequisites_ready:
            st.warning("Complete the API key, dataset, taxonomy, and prompt steps before running the test sample.")
        else:
            if st.button("Run test sample", use_container_width=True):
                sample_df = (
                    st.session_state["dataset_result"]
                    .dataframe.sample(
                        n=min(DEFAULT_TEST_SAMPLE_SIZE, len(st.session_state["dataset_result"].dataframe)),
                    )
                    .sort_values("source_row_number")
                    .reset_index(drop=True)
                )

                progress_placeholder = st.empty()
                progress_bar = st.progress(0)

                def update_progress(payload: dict[str, Any]) -> None:
                    fraction = payload["batch_number"] / max(payload["total_batches"], 1)
                    progress_bar.progress(min(fraction, 1.0))
                    progress_placeholder.info(
                        f"Processed batch {payload['batch_number']} of {payload['total_batches']} | "
                        f"rows completed: {payload['completed_rows']} | "
                        f"failed: {payload['failed_rows']} | partial: {payload['partial_rows']}"
                    )

                run_result = classify_complaints(
                    dataframe=sample_df,
                    taxonomy_text=st.session_state["taxonomy_result"].parsed_text,
                    student_prompt=st.session_state["student_prompt"],
                    api_key=resolved_api_key,
                    model_name=selected_model,
                    batch_size=DEFAULT_BATCH_SIZE,
                    max_retries=DEFAULT_MAX_RETRIES,
                    progress_callback=update_progress,
                )
                st.session_state["test_run_result"] = run_result
                st.session_state["test_run_signature"] = current_signature

        if st.session_state["test_run_result"] is not None:
            if st.session_state["test_run_signature"] != current_signature:
                st.warning("These test results were produced with an older combination of files, prompt, or model.")
            render_run_summary(st.session_state["test_run_result"])
            st.dataframe(
                st.session_state["test_run_result"].results,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[5]:
        render_section_intro(
            "Full Run",
            "Run the classifier on the full uploaded dataset. The app will process complaints in backend-controlled batches, continue past failures where possible, and retain partial results.",
        )

        prerequisites_ready = all(
            [
                resolved_api_key,
                st.session_state["dataset_result"] is not None,
                st.session_state["taxonomy_result"] is not None,
                st.session_state["student_prompt"].strip(),
            ]
        )
        if not prerequisites_ready:
            st.warning("Complete the API key, dataset, taxonomy, and prompt steps before running the full dataset.")
        else:
            st.caption(
                f"This run will process {len(st.session_state['dataset_result'].dataframe)} complaints in batches of {DEFAULT_BATCH_SIZE}."
            )
            if st.button("Run full classification", use_container_width=True):
                progress_placeholder = st.empty()
                progress_bar = st.progress(0)

                def update_progress(payload: dict[str, Any]) -> None:
                    fraction = payload["batch_number"] / max(payload["total_batches"], 1)
                    progress_bar.progress(min(fraction, 1.0))
                    progress_placeholder.info(
                        f"Processed batch {payload['batch_number']} of {payload['total_batches']} | "
                        f"rows completed: {payload['completed_rows']} | "
                        f"failed: {payload['failed_rows']} | partial: {payload['partial_rows']}"
                    )

                run_result = classify_complaints(
                    dataframe=st.session_state["dataset_result"].dataframe,
                    taxonomy_text=st.session_state["taxonomy_result"].parsed_text,
                    student_prompt=st.session_state["student_prompt"],
                    api_key=resolved_api_key,
                    model_name=selected_model,
                    batch_size=DEFAULT_BATCH_SIZE,
                    max_retries=DEFAULT_MAX_RETRIES,
                    progress_callback=update_progress,
                )
                st.session_state["full_run_result"] = run_result
                st.session_state["full_run_signature"] = current_signature

        if st.session_state["full_run_result"] is not None:
            if st.session_state["full_run_signature"] != current_signature:
                st.warning("These full-run results were produced with an older combination of files, prompt, or model.")
            render_run_summary(st.session_state["full_run_result"])

    with tabs[6]:
        render_section_intro(
            "Results and Export",
            "Review classified output, inspect summary distributions, and download the final file for submission.",
        )

        run_result = st.session_state["full_run_result"] or st.session_state["test_run_result"]
        if run_result is None:
            st.info("Run a test sample or the full dataset to see results here.")
        else:
            if (
                (st.session_state["full_run_result"] and st.session_state["full_run_signature"] != current_signature)
                or (
                    st.session_state["full_run_result"] is None
                    and st.session_state["test_run_signature"] != current_signature
                )
            ):
                st.warning("The displayed results are stale relative to the current inputs.")

            results_df = run_result.results.copy()
            render_results_dashboard(results_df)

            csv_bytes = results_df.to_csv(index=False).encode("utf-8")
            excel_bytes = dataframe_to_excel_bytes(results_df)
            download_col_1, download_col_2 = st.columns(2)
            with download_col_1:
                st.download_button(
                    "Download CSV",
                    data=csv_bytes,
                    file_name="classified_complaints.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with download_col_2:
                st.download_button(
                    "Download Excel",
                    data=excel_bytes,
                    file_name="classified_complaints.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
