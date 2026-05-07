from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
import streamlit as st


def render_section_intro(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-panel">
            <div class="panel-title">{title}</div>
            <div class="panel-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: list[tuple[str, str]]) -> None:
    if not metrics:
        return

    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics):
        with column:
            st.markdown(
                f"""
                <div class="m-card">
                    <div class="m-val">{escape(str(value))}</div>
                    <div class="m-label">{escape(str(label))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_status_badges(items: list[tuple[str, str]]) -> None:
    badges = []
    for label, status in items:
        badges.append(f'<span class="badge {status}">{label}</span>')
    st.markdown(f'<div class="status-row">{"".join(badges)}</div>', unsafe_allow_html=True)


def render_friendly_exception(message: str, technical_details: str | None = None) -> None:
    st.error(message)
    if technical_details:
        with st.expander("Technical details"):
            st.code(technical_details)


def dataframe_to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="classified_results")
    buffer.seek(0)
    return buffer.getvalue()
