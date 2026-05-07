from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


CHART_COLORS = {
    "primary": "#0891b2",
    "secondary": "#0f766e",
    "accent": "#d97706",
    "rose": "#e11d48",
    "slate": "#334155",
}


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        xaxis_visible=False,
        yaxis_visible=False,
        annotations=[
            {
                "text": "No data available",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": CHART_COLORS["slate"]},
            }
        ],
        margin=dict(l=10, r=10, t=50, b=10),
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return figure


def build_count_chart(
    dataframe: pd.DataFrame,
    column: str,
    title: str,
    color: str = CHART_COLORS["primary"],
) -> go.Figure:
    if dataframe.empty or column not in dataframe.columns:
        return _empty_figure(title)

    counts = (
        dataframe[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "blank")
        .value_counts(dropna=False)
        .rename_axis(column)
        .reset_index(name="count")
    )
    if counts.empty:
        return _empty_figure(title)

    figure = px.bar(
        counts,
        x=column,
        y="count",
        text="count",
        color_discrete_sequence=[color],
    )
    figure.update_layout(
        title=title,
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="Count",
    )
    figure.update_traces(marker_line_width=0, textposition="outside")
    return figure
