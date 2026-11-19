"""Galla: a phone-first app for kirana owners with two features.

  Gullak    -- auto-savings that follow daily UPI settlements (features/gullak)
  Grahak    -- Wapas Aao: bring back regular customers (features/wapas_aao)

Concept demo, mock data. Run: streamlit run app.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

try:  # Streamlit Cloud secrets -> env vars (never printed)
    for _k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "SARVAM_API_KEY", "GEMINI_MODEL", "CLAUDE_MODEL",
               "SARVAM_STT_MODEL", "SARVAM_TTS_MODEL"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

from features.common import ui_kit as K
from features.common.i18n import DAY_LONG, LANGS, MONTHS
from features.gullak import engine as G
from features.gullak import ui as gullak_ui
from features.wapas_aao import ui as wapas_ui

st.set_page_config(page_title="Galla", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

SHOP = "Gupta General Store"
TABS = [("aaj", "🏠", "tab_aaj"), (gullak_ui.NAV_KEY, "🪙", "tab_gullak"), (wapas_ui.NAV_KEY, "🔁", "tab_grahak")]
t = K.t

if "nav" not in st.session_state:
    st.session_state.nav = "aaj"
if "lang" not in st.session_state:
    st.session_state.lang = "hi"

# ---------------------------------------------------------------- phone shell
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"],
[data-testid="stToolbar"], footer, #MainMenu { display: none !important; }
.stApp { background: #F4F6FA; }
.block-container { max-width: 480px !important; padding: 0.6rem 1rem 7.5rem !important; }
/* keep button rows side by side on phones */
[class*="st-key-kx_"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.6rem !important; }
[class*="st-key-kx_"] [data-testid="stColumn"], [class*="st-key-kx_"] [data-testid="column"] { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
/* top bar */
.gl-top { display:flex; justify-content:space-between; align-items:center; padding: 6px 2px 10px; }
.gl-brand { font-size: 24px; font-weight: 800; color: #0B2447; letter-spacing: .2px; }
.gl-brand span { color: #00BAF2; }
.gl-shop { font-size: 12px; color: #5B6472; line-height: 1.3; margin-top: 2px; }
.st-key-kx_topbar { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #E4E7EC; }
.st-key-kx_topbar [data-testid="stHorizontalBlock"] { align-items: center; }
.st-key-kx_topbar [data-testid="stButtonGroup"] { justify-content: flex-end; display: flex; }
/* bottom tab bar */
.st-key-kx_tabbar { position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: min(480px, 100%);
  background: #fff; border-top: 1px solid #E4E7EC; padding: 6px 10px calc(8px + env(safe-area-inset-bottom)); z-index: 1000;
  box-shadow: 0 -4px 16px rgba(11,36,71,.06); }
.st-key-kx_tabbar .stButton button { min-height: 54px !important; border: 0 !important; background: transparent !important;
  color: #667085 !important; font-size: 15px !important; font-weight: 600 !important; border-radius: 12px !important; white-space: pre-line; line-height: 1.25; }
.st-key-kx_tabbar .stButton button[kind="primary"] { background: #E6F7FD !important; color: #0B2447 !important; }
</style>
""", unsafe_allow_html=True)
K.inject_css()


def top_bar():
    with st.container(key="kx_topbar"):
        c1, c2 = st.columns([3, 2])
        c1.markdown(f'<div class="gl-brand">Galla<span>.</span></div><div class="gl-shop">{SHOP} · {t("concept_demo")}</div>',
                    unsafe_allow_html=True)
        choice = c2.segmented_control("lang", list(LANGS), format_func=lambda c: {"hi": "हिं", "en": "EN"}[c],
                                      default=st.session_state.lang, key="lang_seg", label_visibility="collapsed")
        if choice and choice != st.session_state.lang:
            st.session_state.lang = choice
            st.rerun()


def tab_bar():
    with st.container(key="kx_tabbar"):
        cols = st.columns(len(TABS))
        for col, (key, icon, label_key) in zip(cols, TABS):
            if col.button(f"{icon}\n{t(label_key)}", key=f"tab_{key}", width="stretch",
                          type="primary" if st.session_state.nav == key else "secondary"):
                st.session_state.nav = key
                st.rerun()


def aaj_screen():
    state = gullak_ui.get_state()
    S, _ = gullak_ui._data()
    day = state.get("today", date.today().isoformat())
    d = date.fromisoformat(day)
    settlement = S.get(day)
    with st.container(key="kx_page_aaj"):
        lang = st.session_state.lang
        st.markdown(f'<div class="kx-title">{t("namaste")}</div>'
                    f'<div class="kx-sub">{DAY_LONG[lang][d.weekday()]}, {d.day} {MONTHS[lang][d.month - 1]}</div>',
                    unsafe_allow_html=True)
        if settlement is None:
            K.card(f'<div class="kx-mid">{t("r_no_data")}</div>', "grey")
        else:
            K.card(f'<div class="kx-kicker">{t("upi_today")}</div><div class="kx-big">₹{G.rs(settlement)}</div>'
                   f'<div class="kx-muted">{t("upi_today_sub")}</div>')
    gullak_ui.render_home_card()
    wapas_ui.render_home_card()
    K.foot(t("foot_app"))


# ---------------------------------------------------------------- route
top_bar()
nav = st.session_state.nav
if nav == gullak_ui.NAV_KEY:
    gullak_ui.render_page()
elif nav == wapas_ui.NAV_KEY:
    wapas_ui.render_page()
else:
    aaj_screen()
tab_bar()
