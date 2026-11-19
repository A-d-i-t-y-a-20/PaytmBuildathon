"""Shared look for the Gullak and Wapas Aao features only.

All CSS is scoped to containers whose key starts with "kx_" (Streamlit adds the
class "st-key-<key>"), so the rest of the app is not restyled. One place to
change when the final visual design (Pinterest references) arrives.
"""
import hashlib

import streamlit as st

from features.common.i18n import T, tts_lang

GREEN, GREEN_BG = "#0E8A4F", "#E9F8EF"
AMBER, AMBER_BG = "#B45309", "#FFF4E2"
GREY, GREY_BG = "#5B6472", "#F1F3F6"
BLUE, BLUE_BG = "#0077C8", "#E8F5FD"
NAVY = "#0B2447"

CSS = f"""
<style>
[class*="st-key-kx_"] {{ font-size: 18px; }}
[class*="st-key-kx_page"] {{ max-width: 560px; margin: 0 auto; }}
[class*="st-key-kx_"] p, [class*="st-key-kx_"] li, [class*="st-key-kx_"] label {{ font-size: 18px; }}
[class*="st-key-kx_"] .stButton button {{ min-height: 52px; border-radius: 14px; font-size: 18px; font-weight: 600; }}
[class*="st-key-kx_"] [data-testid="stCaptionContainer"] p {{ font-size: 15px; }}
.kx-head {{ display:flex; align-items:center; gap:.6rem; margin:.2rem 0 .1rem; }}
.kx-title {{ font-size: 30px; font-weight: 800; color: {NAVY}; line-height:1.1; }}
.kx-sub {{ color:#5B6472; font-size:17px; margin-bottom:.8rem; }}
.kx-badge {{ background:#EEF0F4; color:#475467; font-size:12px; font-weight:700; padding:3px 9px; border-radius:999px; letter-spacing:.3px; }}
.kx-card {{ border-radius: 20px; padding: 18px 20px; margin: 6px 0 12px; border:1px solid #E7EAF0; background:#fff; }}
.kx-green {{ background:{GREEN_BG}; border-color:#BFE8CF; }}
.kx-amber {{ background:{AMBER_BG}; border-color:#F6D9A8; }}
.kx-grey  {{ background:{GREY_BG}; border-color:#E1E4EA; }}
.kx-blue  {{ background:{BLUE_BG}; border-color:#C3E4F8; }}
.kx-kicker {{ font-size:15px; font-weight:600; color:#5B6472; margin-bottom:2px; }}
.kx-big {{ font-size: 38px; font-weight: 800; color:{NAVY}; line-height:1.15; }}
.kx-mid {{ font-size: 24px; font-weight: 700; color:{NAVY}; line-height:1.25; }}
.kx-line {{ font-size: 18px; color:#1F2937; margin-top:6px; line-height:1.45; }}
.kx-muted {{ font-size: 15px; color:#5B6472; margin-top:6px; line-height:1.4; }}
.kx-chip {{ display:inline-block; font-size:15px; font-weight:700; padding:5px 12px; border-radius:999px; margin-top:8px; }}
.kx-chip.green {{ background:{GREEN_BG}; color:{GREEN}; }}
.kx-chip.amber {{ background:{AMBER_BG}; color:{AMBER}; }}
.kx-chip.grey  {{ background:{GREY_BG}; color:{GREY}; }}
.kx-chip.blue  {{ background:{BLUE_BG}; color:{BLUE}; }}
.kx-bar {{ height:12px; background:#E7EAF0; border-radius:99px; overflow:hidden; margin-top:10px; }}
.kx-bar > i {{ display:block; height:100%; border-radius:99px; background:{GREEN}; }}
.kx-row {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; padding:8px 0; border-bottom:1px solid #EEF0F4; font-size:17px; }}
.kx-row:last-child {{ border-bottom:0; }}
.kx-row b {{ font-size:18px; }}
.kx-steps {{ display:flex; gap:6px; margin:4px 0 14px; }}
.kx-steps i {{ flex:1; height:6px; border-radius:4px; background:#E1E4EA; }}
.kx-steps i.on {{ background:{BLUE}; }}
.kx-dots {{ display:flex; gap:8px; margin-top:8px; }}
.kx-dot {{ flex:1; text-align:center; font-size:13px; color:#5B6472; }}
.kx-dot b {{ display:block; width:30px; height:30px; margin:0 auto 4px; border-radius:50%; }}
.kx-split {{ display:flex; height:16px; border-radius:99px; overflow:hidden; margin:10px 0 8px; }}
.kx-split > i {{ display:block; height:100%; }}
.kx-legend {{ font-size:15px; color:#344054; line-height:1.7; }}
.kx-legend span {{ display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:6px; vertical-align:middle; }}
.kx-phone {{ border:8px solid #111; border-radius:28px; padding:14px; background:#F6F8FB; max-width:300px; margin:6px auto; }}
.kx-phone .bar {{ font-size:13px; font-weight:700; color:#fff; background:{NAVY}; margin:-14px -14px 12px; padding:8px 12px; border-radius:20px 20px 0 0; }}
.kx-phone .bar.other {{ background:#5F259F; }}
.kx-strike {{ text-decoration: line-through; color:#98A2B3; font-size:20px; margin-right:8px; }}
.kx-say {{ background:#fff; border:1px solid #E7EAF0; border-radius:16px 16px 16px 4px; padding:12px 14px; font-size:17px; line-height:1.45; }}
.kx-foot {{ font-size:13px; color:#98A2B3; text-align:center; margin:18px 0 6px; }}
</style>
"""


def lang():
    return st.session_state.get("lang", "hi")


def t(key, **kw):
    return T(lang(), key, **kw)


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title, subtitle, badge=None):
    badge = badge or t("concept")
    st.markdown(
        f'<div class="kx-head"><div class="kx-title">{title}</div><span class="kx-badge">{badge}</span></div>'
        f'<div class="kx-sub">{subtitle}</div>', unsafe_allow_html=True)


def card(inner_html, tone=""):
    st.markdown(f'<div class="kx-card {("kx-" + tone) if tone else ""}">{inner_html}</div>', unsafe_allow_html=True)


def steps(n, of):
    st.markdown('<div class="kx-steps">' + "".join(f'<i class="{"on" if i < n else ""}"></i>' for i in range(of)) + "</div>",
                unsafe_allow_html=True)


def bar(frac, color=GREEN):
    pct = max(0, min(100, int(round(100 * frac))))
    return f'<div class="kx-bar"><i style="width:{pct}%;background:{color}"></i></div>'


def foot(text):
    st.markdown(f'<div class="kx-foot">{text}</div>', unsafe_allow_html=True)


def speak(text, lang_code=None, autoplay=False, key="tts"):
    """Play text through Sarvam TTS (cached). Text is always shown separately by the caller."""
    from features.common import voice
    if not voice.has_key() or not text:
        return False
    lang_code = lang_code or tts_lang(lang())
    cache = st.session_state.setdefault("_kx_tts_cache", {})
    h = hashlib.sha1((lang_code + text).encode()).hexdigest()
    if h not in cache:
        cache[h] = voice.text_to_speech(text, lang_code)
    if cache[h]:
        st.audio(cache[h], format="audio/wav", autoplay=autoplay)
        return True
    return False


def listen(label, key):
    """Mic input via Sarvam STT. Returns transcript or None; caller always offers a text box too."""
    from features.common import voice
    if not voice.has_key():
        return None
    audio = st.audio_input(label, key=key)
    if audio is None:
        return None
    seen = st.session_state.setdefault("_kx_stt_seen", {})
    h = hashlib.sha1(audio.getvalue()).hexdigest()
    if h in seen:
        return seen[h]
    res = voice.speech_to_text(audio.getvalue())
    seen[h] = (res or {}).get("transcript") or None
    if not seen[h]:
        st.caption(t("voice_fail"))
    return seen[h]
