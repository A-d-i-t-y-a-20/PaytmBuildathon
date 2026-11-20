"""Galla: a phone-first app for kirana owners with two features, plus a Platform
Console for the platform's (Paytm's) merchant ops team.

  Gullak    -- auto-savings that follow daily UPI settlements (features/gullak)
  Grahak    -- Wapas Aao: bring back regular customers (features/wapas_aao)
  Console   -- pilot vs holdout, churn radar, value proof (features/platform)

Concept demo, mock data. Run: streamlit run app.py
"""
import hashlib
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

from features.common import assistant, ui_kit as K
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


def _assistant_facts():
    """This merchant's real current numbers, so Ask Galla can analyze actual session data
    instead of only describing the app in the abstract."""
    gstate = gullak_ui.get_state()
    facts = {
        "shop_name": shop_name(), "gullak_balance": int(gstate.get("balance", 0)),
        "gullak_goal": (gstate.get("goal") or {}).get("name"),
        "gullak_goal_target": (gstate.get("goal") or {}).get("target"),
        "gullak_mode": gstate.get("mode"),
    }
    try:
        pr = wapas_ui._proposal()
        facts["lapsed_customers"] = pr.get("lapsed")
    except Exception:
        pass
    return facts


@st.dialog("Galla")
def _ask_dialog():
    from features.common import voice
    with st.container(key="kx_ask_dialog"):
        answered = bool(st.session_state.get("ask_voice_answered"))
        st.markdown(K.wave(still=not answered and not voice.has_key()), unsafe_allow_html=True)
        status = t("ask_listening") if not answered else t("ask_dialog_sub")
        st.markdown(f'<div class="kx-mid" style="text-align:center">{status}</div>', unsafe_allow_html=True)

        # Voice is the primary, hands-free path (Alexa/Siri-style): once a recording is made,
        # it answers itself -- no further taps, voice in, voice out, no visible answer text --
        # in whichever language was spoken. The only taps are the browser's own mic
        # start/stop (required for microphone permission; nothing I can do in-app removes
        # that one browser-level click), never a separate "Ask" step.
        if voice.has_key():
            audio = st.audio_input(t("ask_mic_label"), key="ask_audio", label_visibility="collapsed")
            if audio is not None:
                h = hashlib.sha1(audio.getvalue()).hexdigest()
                if st.session_state.get("ask_audio_seen") != h:
                    st.session_state.ask_audio_seen = h
                    with st.spinner(t("ask_listening")):
                        res = voice.speech_to_text(audio.getvalue())
                    if res and res.get("transcript"):
                        lang_code = res.get("language_code") or "hi-IN"
                        answer = assistant.ask(res["transcript"], lang=lang_code, facts=_assistant_facts()) or t("ask_fallback")
                        assistant.log(res["transcript"], answer, lang_code, "voice", shop_name())
                        st.session_state.ask_voice_answered = True
                        K.speak(answer, lang_code=voice.normalize_lang(lang_code), autoplay=True, key="ask_voice_tts")
                        st.rerun()
                    else:
                        st.caption(t("voice_fail"))
        else:
            st.caption(t("ask_novoice"))

        # Typing stays available, tucked away: a deliberate visual action, so it still shows text.
        with st.expander(t("ask_type_instead")):
            text = st.text_input("ask", value="", placeholder=t("ask_placeholder"), key="ask_text", label_visibility="collapsed")
            if st.button(t("ask_btn"), type="primary", width="stretch", key="ask_go") and text.strip():
                answer = assistant.ask(text, lang=st.session_state.lang, facts=_assistant_facts()) or t("ask_fallback")
                assistant.log(text, answer, st.session_state.lang, "text", shop_name())
                st.session_state.ask_text_answer = answer
            if st.session_state.get("ask_text_answer"):
                K.ai_say(st.session_state.ask_text_answer)
                K.speak(st.session_state.ask_text_answer, key="ask_text_tts")

        if st.button(t("ask_close"), key="ask_close_btn", width="stretch"):
            for k in ("ask_text_answer", "ask_audio_seen", "ask_voice_answered"):
                st.session_state.pop(k, None)
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
        with st.container(key="kx_orb_home"):
            st.markdown(f'<div class="kx-orb-hint">{t("ask_orb_hint")}</div>', unsafe_allow_html=True)
            if st.button(t("ask_orb_label"), key="ask_orb_btn"):
                _ask_dialog()
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
