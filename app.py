"""Galla: a phone-first app for kirana owners with two features, plus a Platform
Console for the platform's (Paytm's) merchant ops team.

  Gullak    -- auto-savings that follow daily UPI settlements (features/gullak)
  Grahak    -- Wapas Aao: bring back regular customers (features/wapas_aao)
  Console   -- pilot vs holdout, churn radar, value proof (features/platform)

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
from features.platform import ui as platform_ui
from features.wapas_aao import ui as wapas_ui

st.set_page_config(page_title="Galla", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

TABS = [("aaj", "🏠", "tab_aaj"), (gullak_ui.NAV_KEY, "🪙", "tab_gullak"), (wapas_ui.NAV_KEY, "🔁", "tab_grahak")]
t = K.t
shop_name = K.shop_name


if "nav" not in st.session_state:
    st.session_state.nav = "aaj"
if "lang" not in st.session_state:
    st.session_state.lang = "hi"
if "console_view" not in st.session_state:
    st.session_state.console_view = "merchant"

# ---------------------------------------------------------------- phone shell
_console = st.session_state.console_view == "platform"
st.markdown(f"""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"],
[data-testid="stToolbar"], footer, #MainMenu {{ display: none !important; }}
.stApp {{ background: radial-gradient(circle at 15% -10%, #1C4A33 0%, #0F2E1F 45%, #061309 100%) fixed; }}
.block-container {{ max-width: {"1200px" if _console else "480px"} !important; padding: 0.6rem 1rem 8rem !important; }}
[class*="st-key-kx_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 0.6rem !important; }}
[class*="st-key-kx_"] [data-testid="stColumn"], [class*="st-key-kx_"] [data-testid="column"] {{ min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }}
.gl-brand {{ font-family: 'Anton', 'Inter', sans-serif; font-size: 26px; font-weight: 400; color: {K.INK};
  letter-spacing: -.01em; text-transform: uppercase; }}
.gl-brand span {{ color: {K.SHOUT}; }}
.gl-shop {{ font-size: 10px; color: rgba(255,255,255,.5); letter-spacing: .14em; text-transform: uppercase; margin-top: 2px; }}
.st-key-kx_topbar {{ margin-bottom: 10px; }}
.st-key-kx_topbar [data-testid="stHorizontalBlock"] {{ align-items: center; }}
.st-key-kx_topbar [data-testid="stButtonGroup"] {{ justify-content: flex-end; display: flex; }}
.st-key-kx_tabbar {{ position: fixed; bottom: 14px; left: 50%; transform: translateX(-50%); width: min(452px, calc(100% - 28px));
  background: rgba(15,42,30,.85); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,.1); border-radius: 999px; padding: 6px; z-index: 1000; box-shadow: 0 16px 40px rgba(0,0,0,.4); }}
.st-key-kx_tabbar .stButton button {{ min-height: 52px !important; border: 0 !important; background: transparent !important;
  color: rgba(255,255,255,.55) !important; border-radius: 999px !important; padding: 4px 2px !important; white-space: pre-line; line-height: 1.2; }}
.st-key-kx_tabbar .stButton button p {{ font-size: 13px !important; font-weight: 700 !important; overflow: visible !important; text-overflow: clip !important; }}
.st-key-kx_tabbar .stButton button[kind="primary"] {{ background: linear-gradient(135deg, {K.SHOUT}, {K.SHOUT_2}) !important; }}
.st-key-kx_tabbar .stButton button[kind="primary"] p {{ color: #06150E !important; }}
</style>
""", unsafe_allow_html=True)
K.inject_css()


def top_bar():
    with st.container(key="kx_topbar"):
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.markdown(f'<div class="gl-brand">Galla<span>.</span></div><div class="gl-shop">{shop_name()} · {t("concept_demo")}</div>',
                    unsafe_allow_html=True)
        views = ["merchant", "platform"]
        # keying on the current value means an external change (e.g. the console opening a
        # merchant's app view) always wins -- the widget can never hold a stale selection
        view = c2.segmented_control("view", views, format_func=lambda v: "📱" if v == "merchant" else "🖥",
                                    default=st.session_state.console_view, key=f"view_seg_{st.session_state.console_view}",
                                    label_visibility="collapsed")
        if view and view != st.session_state.console_view:
            st.session_state.console_view = view
            st.rerun()
        choice = c3.segmented_control("lang", list(LANGS), format_func=lambda c: {"hi": "हिं", "en": "EN"}[c],
                                      default=st.session_state.lang, key="lang_seg", label_visibility="collapsed")
        if choice and choice != st.session_state.lang:
            st.session_state.lang = choice
            st.rerun()
        if st.session_state.get("platform_merchant") and st.session_state.console_view == "merchant":
            if st.button("← Back to default merchant", key="back_to_default", width="stretch"):
                for k in ("platform_merchant", "gk_state", "gk_rec_cache", "gk_view", "gk_onb", "gk_flash", "gk_reply",
                          "gk_settlements", "gk_obligations", "gk_data_merchant_id"):
                    st.session_state.pop(k, None)
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
        num = f'<div class="kx-label" style="margin-top:22px">{t("upi_today")}</div><div class="kx-hero-num">₹{G.rs(settlement)}</div>' if settlement is not None else ""
        K.header(t("namaste"), f'{DAY_LONG[lang][d.weekday()]}, {d.day} {MONTHS[lang][d.month - 1]}', extra_html=num)
    gullak_ui.render_home_card()
    wapas_ui.render_home_card()
    K.foot(t("foot_app"))


# ---------------------------------------------------------------- route
top_bar()
if st.session_state.console_view == "platform":
    platform_ui.render_page()
else:
    nav = st.session_state.nav
    if nav == gullak_ui.NAV_KEY:
        gullak_ui.render_page()
    elif nav == wapas_ui.NAV_KEY:
        wapas_ui.render_page()
    else:
        aaj_screen()
    tab_bar()
