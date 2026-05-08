from __future__ import annotations

import streamlit as st


THEME = {
    "bg": "#f8fafc",
    "card": "#ffffff",
    "card_hover": "#f1f5f9",
    "surface": "#eef2f7",
    "border": "rgba(15,23,42,0.08)",
    "border_glow": "rgba(8,145,178,0.20)",
    "primary": "#0891b2",
    "emerald": "#059669",
    "amber": "#d97706",
    "rose": "#e11d48",
    "text": "#0f172a",
    "slate": "#475569",
    "muted": "#64748b",
    "input_bg": "#ffffff",
    "sidebar_bg": "linear-gradient(180deg, #f1f5f9 0%, #e2e8f0 100%)",
}


def apply_styles() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@700;800&family=JetBrains+Mono:wght@500;700&display=swap');

        :root {{
            --bg: {THEME["bg"]};
            --card: {THEME["card"]};
            --card-hover: {THEME["card_hover"]};
            --surface: {THEME["surface"]};
            --border: {THEME["border"]};
            --border-glow: {THEME["border_glow"]};
            --primary: {THEME["primary"]};
            --emerald: {THEME["emerald"]};
            --amber: {THEME["amber"]};
            --rose: {THEME["rose"]};
            --text: {THEME["text"]};
            --slate: {THEME["slate"]};
            --muted: {THEME["muted"]};
            --input-bg: {THEME["input_bg"]};
            --font-body: 'DM Sans', sans-serif;
            --font-display: 'Playfair Display', serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container {{
            background: var(--bg) !important;
            color: var(--text) !important;
            font-family: var(--font-body) !important;
        }}

        #MainMenu, footer {{ visibility: hidden; }}
        header[data-testid="stHeader"] {{ background: transparent !important; }}
        .block-container {{
            padding-top: 1.35rem !important;
            padding-bottom: 2rem !important;
            max-width: 1450px !important;
        }}

        section[data-testid="stSidebar"] {{
            background: {THEME["sidebar_bg"]} !important;
            border-right: 1px solid var(--border) !important;
        }}

        .app-panel {{
            background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 100%);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.25rem 1.25rem 1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 12px 34px rgba(15,23,42,0.04);
        }}

        .panel-title {{
            color: var(--text);
            font-family: var(--font-display);
            font-size: 1.45rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
        }}

        .panel-subtitle {{
            color: var(--slate);
            font-size: 0.98rem;
            line-height: 1.6;
        }}

        .page-caption {{
            color: var(--slate);
            font-size: 1rem;
            line-height: 1.6;
            margin: 0 0 1.1rem 0;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 1.25rem;
        }}

        @media (max-width: 980px) {{
            .metric-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}

        .m-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.1rem 0.95rem;
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 22px rgba(15,23,42,0.03);
        }}

        .m-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), #7dd3fc);
        }}

        .m-val {{
            color: var(--text);
            font-family: var(--font-mono);
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .m-label {{
            color: var(--slate);
            font-size: 0.72rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-top: 0.45rem;
            font-weight: 700;
        }}

        .status-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 0 0 1rem 0;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid var(--border);
            padding: 0.45rem 0.75rem;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text);
            background: var(--surface);
        }}

        .badge.success {{ background: rgba(5,150,105,0.10); }}
        .badge.warning {{ background: rgba(217,119,6,0.10); }}
        .badge.error {{ background: rgba(225,29,72,0.10); }}
        .badge.info {{ background: rgba(8,145,178,0.08); }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            background: var(--surface);
            border-radius: 15px;
            padding: 5px;
            border: 1px solid var(--border);
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: 11px !important;
            padding: 10px 18px !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            color: var(--slate) !important;
        }}

        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background: var(--card) !important;
            color: var(--primary) !important;
            box-shadow: 0 8px 20px rgba(8,145,178,0.10);
        }}

        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {{
            display: none !important;
        }}

        .stButton > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="stFormSubmitButton"] > button {{
            border-radius: 12px !important;
            border: 1px solid var(--border) !important;
            background: var(--card) !important;
            color: var(--text) !important;
            font-weight: 700 !important;
            min-height: 2.75rem !important;
            box-shadow: 0 8px 18px rgba(15,23,42,0.03);
        }}

        .stButton > button:hover,
        [data-testid="stDownloadButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {{
            border-color: var(--border-glow) !important;
            transform: translateY(-1px);
        }}

        .stTextInput input,
        .stTextArea textarea,
        div[data-baseweb="select"] > div {{
            background: var(--input-bg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            color: var(--text) !important;
        }}

        .stExpander {{
            border-radius: 16px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
