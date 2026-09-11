"""Shared design system for the Streamlit UI.

Both app.py and pages/1_Evaluation.py import from here so the two pages look
like one product instead of two independently-styled scripts. Colors are
literal hex values (not Streamlit's undocumented theme CSS vars) so the look
is identical regardless of the viewer's OS/browser theme setting.
"""

import streamlit as st

PRIMARY = "#6C5CE7"
PRIMARY_DARK = "#4F3DC4"
ACCENT = "#00C2B8"
BG_SOFT = "#F5F5FC"
CARD = "#FFFFFF"
BORDER = "#E7E7F4"
TEXT = "#1C1B29"
MUTED = "#6B7089"
SUCCESS = "#16A34A"
SUCCESS_BG = "#E9F9EF"
WARNING = "#B45309"
WARNING_BG = "#FEF3E2"
DANGER = "#DC2626"
DANGER_BG = "#FDECEC"
INFO = "#2563EB"
INFO_BG = "#EAF1FF"

_BADGE_STYLES = {
    "success": (SUCCESS, SUCCESS_BG),
    "warning": (WARNING, WARNING_BG),
    "danger": (DANGER, DANGER_BG),
    "info": (INFO, INFO_BG),
    "neutral": (MUTED, BG_SOFT),
}


def inject_base_css() -> None:
    st.markdown(
        f"""
        <style>
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        header[data-testid="stHeader"] {{ background: transparent; }}

        .stApp {{ background: {BG_SOFT}; }}
        [data-testid="stMainBlockContainer"] {{ padding-top: 1.5rem; max-width: 1100px; }}
        [data-testid="stSidebarContent"] {{ background: {CARD}; border-right: 1px solid {BORDER}; }}

        html, body, [class*="css"] {{ color: {TEXT}; }}
        h1, h2, h3, h4 {{ color: {TEXT}; font-weight: 800; letter-spacing: -0.01em; }}
        p, li, span, label {{ color: {TEXT}; }}
        .stCaption, [data-testid="stCaptionContainer"], small {{ color: {MUTED} !important; }}

        /* ---- Hero banner ---- */
        .rag-hero {{
            background: linear-gradient(120deg, {PRIMARY} 0%, {PRIMARY_DARK} 55%, {ACCENT} 130%);
            border-radius: 20px;
            padding: 1.6rem 1.9rem;
            margin-bottom: 1.4rem;
            box-shadow: 0 10px 30px -12px rgba(79, 61, 196, 0.55);
        }}
        .rag-hero .rag-hero-title {{
            color: #FFFFFF;
            font-size: 1.55rem;
            font-weight: 800;
            margin: 0 0 0.15rem 0;
            letter-spacing: -0.01em;
        }}
        .rag-hero .rag-hero-sub {{
            color: rgba(255,255,255,0.88);
            font-size: 0.92rem;
            margin: 0;
        }}

        /* ---- Generic surface card ---- */
        .rag-card {{
            background: {CARD};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 1.1rem 1.25rem;
            box-shadow: 0 1px 2px rgba(28, 27, 41, 0.04);
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            border-radius: 16px !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 16px !important;
        }}

        /* ---- Section headers ---- */
        .rag-section-title {{
            font-weight: 700;
            font-size: 0.95rem;
            color: {TEXT};
            margin: 0 0 0.6rem 0;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}

        /* ---- Stat pill row ---- */
        .rag-stat {{
            background: {BG_SOFT};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 0.65rem 0.85rem;
            height: 100%;
        }}
        .rag-stat .rag-stat-label {{
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: {MUTED};
            margin-bottom: 0.15rem;
        }}
        .rag-stat .rag-stat-value {{
            font-size: 1.25rem;
            font-weight: 800;
            color: {TEXT};
            line-height: 1.2;
        }}

        /* ---- Badge pill ---- */
        .rag-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.18rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
        }}

        /* ---- Buttons ---- */
        .stButton > button {{
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid {BORDER};
            transition: transform 0.05s ease-in-out;
        }}
        .stButton > button:hover {{ border-color: {PRIMARY}; color: {PRIMARY}; }}
        .stButton > button:active {{ transform: scale(0.98); }}
        .stButton > button[kind="primary"] {{
            background: linear-gradient(120deg, {PRIMARY}, {PRIMARY_DARK});
            border: none;
            color: #fff;
        }}
        .stButton > button[kind="primary"]:hover {{ opacity: 0.92; color: #fff; }}
        div[data-testid="stFormSubmitButton"] > button {{
            background: linear-gradient(120deg, {PRIMARY}, {PRIMARY_DARK});
            border: none;
            color: #fff;
            border-radius: 10px;
            font-weight: 600;
        }}

        /* ---- File uploader ---- */
        div[data-testid="stFileUploader"] {{
            border: 1.5px dashed {PRIMARY};
            border-radius: 16px;
            background: {INFO_BG};
            padding: 0.5rem;
        }}
        div[data-testid="stFileUploader"] section {{ background: transparent; }}

        /* ---- Tabs ---- */
        div[data-testid="stTabs"] button[data-baseweb="tab"] {{
            border-radius: 8px 8px 0 0;
            font-weight: 600;
            color: {MUTED};
        }}
        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: {PRIMARY};
        }}
        div[data-testid="stTabs"] div[data-baseweb="tab-highlight"] {{
            background-color: {PRIMARY};
            height: 3px;
        }}

        /* ---- Chat messages ---- */
        div[data-testid="stChatMessage"] {{
            border-radius: 16px;
            background: {CARD};
            border: 1px solid {BORDER};
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 1px 3px rgba(28, 27, 41, 0.05);
        }}
        div[data-testid="stChatMessage"]:has(img[data-testid="stChatMessageAvatarUser"]) {{
            background: {INFO_BG};
            border-color: #D6E4FF;
        }}
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {{
            background: {INFO_BG};
            border-color: #D6E4FF;
        }}

        /* ---- Chat input ---- */
        div[data-testid="stChatInput"] textarea {{
            border-radius: 12px;
        }}

        /* ---- Metrics (native st.metric, kept as fallback in a few spots) ---- */
        div[data-testid="stMetricValue"] {{ font-size: 1.3rem; font-weight: 800; color: {TEXT}; }}
        div[data-testid="stMetricLabel"] {{ color: {MUTED}; }}

        /* ---- Dataframes ---- */
        div[data-testid="stDataFrame"] {{
            border: 1px solid {BORDER};
            border-radius: 12px;
            overflow: hidden;
        }}

        hr {{ border-color: {BORDER}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="rag-hero">
            <p class="rag-hero-title">{icon} {title}</p>
            <p class="rag-hero-sub">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(icon: str, text: str) -> None:
    st.markdown(f'<div class="rag-section-title">{icon} {text}</div>', unsafe_allow_html=True)


def stat(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="rag-stat">
            <div class="rag-stat-label">{label}</div>
            <div class="rag-stat-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "neutral") -> str:
    color, bg = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    return f'<span class="rag-badge" style="color:{color};background:{bg};">{text}</span>'
