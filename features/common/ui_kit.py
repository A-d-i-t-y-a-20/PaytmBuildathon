"""Shared look for the Gullak and Wapas Aao features only.

All CSS is scoped to containers whose key starts with "kx_" (Streamlit adds the
class "st-key-<key>"). Design system: "Hyper-Saturated Fluid" -- one flat
Cyber Yellow shout colour, a deep onyx void, glass cards, pill buttons, Inter.
"""
import hashlib

import streamlit as st

from features.common.i18n import T, tts_lang

# ---------------------------------------------------------------- design tokens: "Hyper-Saturated Fluid"
SHOUT = "#FDE047"      # Cyber Yellow -- the one dominant colour, always flat
VOID = "#0A0A0A"       # Deep Onyx background
SURFACE = "#171717"    # Charcoal panels
DEEP = "#262626"       # UI elements inside the void
WHITE = "#FFFFFF"
GREEN, GREEN_BG = "#4ADE80", "rgba(74,222,128,.10)"     # saved
AMBER, AMBER_BG = "#FB923C", "rgba(251,146,60,.10)"     # skipped (orange, so it never reads as the shout yellow)
GREY, GREY_BG = "#A3A3A3", "rgba(255,255,255,.04)"      # paused
BLUE, BLUE_BG = "#60A5FA", "rgba(96,165,250,.10)"
NAVY = VOID
EASE = "cubic-bezier(0.22, 1, 0.36, 1)"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
[class*="st-key-kx_"], [class*="st-key-kx_"] * {{ font-family: 'Inter', 'Noto Sans Devanagari', 'Nirmala UI', system-ui, sans-serif; }}
[class*="st-key-kx_"] {{ font-size: 16px; color: {WHITE}; }}
[class*="st-key-kx_page"] {{ max-width: 560px; margin: 0 auto; }}
[class*="st-key-kx_"] p, [class*="st-key-kx_"] li, [class*="st-key-kx_"] label {{ font-size: 15px; line-height: 1.6; }}
[class*="st-key-kx_"] [data-testid="stCaptionContainer"] p {{ font-size: 13px; color: rgba(255,255,255,.5); }}

/* ---------- motion */
@keyframes kxUp {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes kxFloat {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-4px); }} }}
.kx-hero, .kx-card {{ animation: kxUp .55s {EASE} both; }}
.kx-float {{ animation: kxUp .55s {EASE} both, kxFloat 6s ease-in-out 1s infinite; }}

/* ---------- pill buttons (squish on press) */
[class*="st-key-kx_"] .stButton button {{
  min-height: 52px; border-radius: 999px !important; font-size: 15px; font-weight: 700; letter-spacing: .01em;
  background: rgba(255,255,255,.06) !important; color: {WHITE} !important; border: 1px solid rgba(255,255,255,.18) !important;
  transition: transform .25s {EASE}, box-shadow .25s {EASE}, background .2s; }}
[class*="st-key-kx_"] .stButton button:hover {{ transform: scale(1.03); box-shadow: 0 10px 30px rgba(0,0,0,.45); border-color: rgba(255,255,255,.35) !important; }}
[class*="st-key-kx_"] .stButton button:active {{ transform: scale(.95); }}
[class*="st-key-kx_"] .stButton button[kind="primary"] {{ background: {SHOUT} !important; color: {VOID} !important; border: 0 !important; }}
[class*="st-key-kx_"] .stButton button[kind="primary"] p {{ color: {VOID} !important; font-weight: 800; }}
[class*="st-key-kx_"] .stButton button:disabled {{ opacity: .35; transform: none; }}

/* ---------- liquid hero (flat shout colour, asymmetrical bottom) */
.kx-hero {{ background: {SHOUT}; color: {VOID}; margin: 0 -1rem 18px; padding: 26px 24px 46px;
  border-radius: 0 0 120px 40px; position: relative; overflow: hidden; }}
.kx-hero .kx-badge {{ background: {VOID}; color: {SHOUT}; }}
.kx-title {{ font-size: 46px; font-weight: 900; letter-spacing: -.035em; line-height: .98; color: {VOID}; margin: 12px 0 10px; }}
.kx-sub {{ font-size: 16px; font-weight: 500; opacity: .75; color: {VOID}; max-width: 92%; line-height: 1.45; }}
.kx-hero .kx-label {{ color: rgba(10,10,10,.6); }}
.kx-hero-num {{ font-size: 56px; font-weight: 900; letter-spacing: -.04em; line-height: 1; color: {VOID}; margin-top: 18px; }}
.kx-head {{ display:flex; align-items:center; gap:.6rem; }}
.kx-badge {{ display:inline-block; font-size:10px; font-weight:800; padding:5px 11px; border-radius:999px;
  letter-spacing:.16em; text-transform:uppercase; }}
.kx-label {{ font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.5); }}

/* ---------- glass cards */
.kx-card {{ border-radius: 32px; padding: 22px 22px; margin: 8px 0 14px; color: {WHITE};
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); box-shadow: 0 24px 60px rgba(0,0,0,.45); }}
.kx-green {{ background: {GREEN_BG}; border-color: rgba(74,222,128,.35); }}
.kx-amber {{ background: {AMBER_BG}; border-color: rgba(251,146,60,.35); }}
.kx-grey  {{ background: {GREY_BG}; border-color: rgba(255,255,255,.10); }}
/* the "ask" / primary cards become liquid shout blocks */
.kx-blue  {{ background: {SHOUT}; border: 0; color: {VOID}; border-radius: 32px 32px 96px 32px; box-shadow: 0 24px 60px rgba(253,224,71,.12); }}
.kx-blue .kx-big, .kx-blue .kx-mid, .kx-blue .kx-line, .kx-blue b {{ color: {VOID}; }}
.kx-blue .kx-kicker, .kx-blue .kx-muted {{ color: rgba(10,10,10,.62); }}

/* ---------- type scale */
.kx-kicker {{ font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.5); margin-bottom: 6px; }}
.kx-big {{ font-size: 40px; font-weight: 900; letter-spacing: -.035em; line-height: 1.05; color: {WHITE}; }}
.kx-mid {{ font-size: 24px; font-weight: 800; letter-spacing: -.02em; color: {WHITE}; line-height: 1.2; }}
.kx-line {{ font-size: 15px; color: rgba(255,255,255,.85); margin-top: 8px; line-height: 1.6; }}
.kx-muted {{ font-size: 13px; color: rgba(255,255,255,.55); margin-top: 6px; line-height: 1.6; }}
.kx-card b {{ color: inherit; }}

/* ---------- chips & bars */
.kx-chip {{ display:inline-block; font-size:12px; font-weight:800; padding:6px 13px; border-radius:999px; margin-top:12px; letter-spacing:.02em; }}
.kx-chip.green {{ background: rgba(74,222,128,.16); color: {GREEN}; }}
.kx-chip.amber {{ background: rgba(251,146,60,.16); color: {AMBER}; }}
.kx-chip.grey  {{ background: rgba(255,255,255,.08); color: {GREY}; }}
.kx-chip.blue  {{ background: {SHOUT}; color: {VOID}; }}
.kx-blue .kx-chip.blue {{ background: {VOID}; color: {SHOUT}; }}
.kx-bar {{ height:10px; background: rgba(255,255,255,.10); border-radius:99px; overflow:hidden; margin-top:12px; }}
.kx-bar > i {{ display:block; height:100%; border-radius:99px; background:{SHOUT}; }}
.kx-row {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; padding:11px 0;
  border-bottom:1px solid rgba(255,255,255,.08); font-size:15px; color: rgba(255,255,255,.75); }}
.kx-row:last-child {{ border-bottom:0; }}
.kx-row b {{ font-size:17px; color: {WHITE}; }}
.kx-steps {{ display:flex; gap:6px; margin:4px 0 16px; }}
.kx-steps i {{ flex:1; height:6px; border-radius:99px; background: rgba(255,255,255,.12); }}
.kx-steps i.on {{ background:{SHOUT}; }}
.kx-split {{ display:flex; height:14px; border-radius:99px; overflow:hidden; margin:12px 0 10px; gap:3px; }}
.kx-split > i {{ display:block; height:100%; border-radius:99px; }}
.kx-legend {{ font-size:13px; color: rgba(255,255,255,.7); line-height:1.9; }}
.kx-legend span {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; vertical-align:middle; }}

/* ---------- speech bubble, phone mock-ups, footer */
.kx-say {{ background: rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); color: {WHITE};
  border-radius: 24px 24px 24px 6px; padding: 14px 16px; font-size: 15px; line-height: 1.55;
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); animation: kxUp .55s {EASE} both; }}
.kx-say.me {{ background: {SHOUT}; color: {VOID}; border: 0; border-radius: 24px 24px 6px 24px; margin-left: auto; max-width: 85%; font-weight: 600; }}
.kx-phone {{ border:1px solid rgba(255,255,255,.2); border-radius:32px; padding:16px; background:#F5F5F5; color:{VOID};
  max-width:300px; margin:8px auto; box-shadow: 0 24px 60px rgba(0,0,0,.5); }}
.kx-phone .bar {{ font-size:11px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:{SHOUT}; background:{VOID};
  margin:-16px -16px 14px; padding:10px 14px; border-radius:31px 31px 0 0; }}
.kx-phone .bar.other {{ background:#3B0764; color:#fff; }}
.kx-phone .kx-chip.green {{ background: rgba(22,163,74,.12); color: #15803D; }}
.kx-phone .kx-chip.grey {{ background: rgba(0,0,0,.06); color: #525252; }}
.kx-strike {{ text-decoration: line-through; color:#A3A3A3; font-size:20px; margin-right:8px; }}
.kx-foot {{ font-size:10px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color: rgba(255,255,255,.35);
  text-align:center; margin:26px 0 8px; line-height:1.8; }}

/* ---------- Streamlit widgets inside our screens */
[class*="st-key-kx_"] [data-testid="stExpander"] details {{ border-radius: 28px; border: 1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.04); }}
[class*="st-key-kx_"] [data-testid="stExpander"] summary p {{ font-weight: 700; }}
[class*="st-key-kx_"] [data-baseweb="input"], [class*="st-key-kx_"] [data-baseweb="base-input"] {{ border-radius: 999px !important; }}
[class*="st-key-kx_"] [data-testid="stTabs"] [role="tab"] p {{ font-weight: 700; }}
[class*="st-key-kx_"] [data-testid="stButtonGroup"] button {{ border-radius: 999px !important; }}
</style>
"""


def lang():
    return st.session_state.get("lang", "hi")


def t(key, **kw):
    return T(lang(), key, **kw)


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title, subtitle, badge=None, extra_html=""):
    """Liquid hero: flat Cyber Yellow block with an asymmetrical bottom edge and a massive headline."""
    badge = badge or t("concept")
    st.markdown(
        f'<div class="kx-hero"><span class="kx-badge">{badge}</span>'
        f'<div class="kx-title">{title}</div><div class="kx-sub">{subtitle}</div>{extra_html}</div>',
        unsafe_allow_html=True)


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
