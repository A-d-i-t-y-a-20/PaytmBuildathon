"""Shared look for the Gullak and Wapas Aao features only.

All CSS is scoped to containers whose key starts with "kx_" (Streamlit adds the
class "st-key-<key>"). Design system: dark forest-green/teal gradient, glass
cards with a soft glow border, pill buttons with a teal gradient fill, a bold
condensed display font for headlines, Inter for body text.
"""
import hashlib

import streamlit as st

from features.common.i18n import T, tts_lang

# ---------------------------------------------------------------- design tokens
SHOUT = "#22D3A8"      # Teal-green -- the one accent colour (gradient to SHOUT_2)
SHOUT_2 = "#15B37F"
VOID = "#0A1F16"       # Deep forest green -- the page background (flat fallback)
SURFACE = "rgba(255,255,255,.05)"   # glass card fill
DEEP = "#13301F"       # UI elements inside cards
INK = "#FFFFFF"        # primary text colour
GREEN, GREEN_BG = "#4ADE80", "rgba(74,222,128,.12)"     # saved
AMBER, AMBER_BG = "#FBBF24", "rgba(251,191,36,.12)"     # skipped (amber, so it never reads as the shout teal)
GREY, GREY_BG = "#9CA3AF", "rgba(255,255,255,.06)"      # paused
BLUE, BLUE_BG = "#38BDF8", "rgba(56,189,248,.12)"       # matches the AI-avatar accent
GRAD = f"linear-gradient(135deg, {SHOUT}, {SHOUT_2})"
EASE = "cubic-bezier(0.22, 1, 0.36, 1)"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Anton&display=swap');
[class*="st-key-kx_"], [class*="st-key-kx_"] * {{ font-family: 'Inter', 'Noto Sans Devanagari', 'Nirmala UI', system-ui, sans-serif; }}
[class*="st-key-kx_"] {{ font-size: 16px; color: {INK}; }}
[class*="st-key-kx_page"] {{ max-width: 560px; margin: 0 auto; }}
[class*="st-key-kx_console"] {{ max-width: 1100px; margin: 0 auto; }}
[class*="st-key-kx_"] p, [class*="st-key-kx_"] li, [class*="st-key-kx_"] label {{ font-size: 15px; line-height: 1.6; }}
[class*="st-key-kx_"] [data-testid="stCaptionContainer"] p {{ font-size: 13px; color: rgba(255,255,255,.55); }}

/* ---------- motion */
@keyframes kxUp {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes kxFloat {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-4px); }} }}
.kx-hero, .kx-card {{ animation: kxUp .55s {EASE} both; }}
.kx-float {{ animation: kxUp .55s {EASE} both, kxFloat 6s ease-in-out 1s infinite; }}

/* ---------- pill buttons (glass outline by default, teal gradient for primary) */
[class*="st-key-kx_"] .stButton button {{
  min-height: 52px; border-radius: 999px !important; font-size: 15px; font-weight: 700; letter-spacing: .01em;
  background: rgba(255,255,255,.05) !important; color: {INK} !important; border: 1px solid rgba(255,255,255,.14) !important;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  transition: transform .2s {EASE}, box-shadow .2s {EASE}, background .2s, border-color .2s; }}
[class*="st-key-kx_"] .stButton button:hover {{ transform: scale(1.02); box-shadow: 0 8px 24px rgba(34,211,168,.18); border-color: {SHOUT} !important; }}
[class*="st-key-kx_"] .stButton button:active {{ transform: scale(.96); }}
[class*="st-key-kx_"] .stButton button[kind="primary"] {{ background: {GRAD} !important; color: #06150E !important; border: 0 !important; }}
[class*="st-key-kx_"] .stButton button[kind="primary"] p {{ color: #06150E !important; font-weight: 800; }}
[class*="st-key-kx_"] .stButton button:disabled {{ opacity: .35; transform: none; }}

/* ---------- hero: headline sits directly on the gradient page bg, no card box */
.kx-hero {{ margin: 6px 0 18px; padding: 0; }}
.kx-hero .kx-badge {{ background: rgba(255,255,255,.08); color: {SHOUT}; border: 1px solid rgba(34,211,168,.3); }}
.kx-title {{ font-family: 'Anton', 'Inter', 'Noto Sans Devanagari', sans-serif; font-size: 44px; font-weight: 400;
  letter-spacing: -.01em; line-height: .98; color: {INK}; margin: 14px 0 10px; text-transform: uppercase; }}
.kx-sub {{ font-size: 16px; font-weight: 500; color: rgba(255,255,255,.65); max-width: 92%; line-height: 1.45; }}
.kx-hero .kx-label {{ color: rgba(255,255,255,.55); }}
.kx-hero-num {{ font-size: 52px; font-weight: 900; letter-spacing: -.03em; line-height: 1; color: {SHOUT}; margin-top: 16px;
  text-shadow: 0 0 28px rgba(34,211,168,.45); }}
.kx-head {{ display:flex; align-items:center; gap:.6rem; }}
.kx-badge {{ display:inline-block; font-size:10px; font-weight:800; padding:5px 11px; border-radius:999px;
  letter-spacing:.16em; text-transform:uppercase; }}
.kx-label {{ font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.5); }}

/* ---------- glass cards: dark translucent fill, soft glow border, blur, glossy top sheen */
.kx-card {{ position: relative; overflow: hidden; border-radius: 28px; padding: 22px 22px; margin: 8px 0 14px; color: {INK};
  background: {SURFACE}; border: 1px solid rgba(255,255,255,.08);
  backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px); box-shadow: 0 16px 40px rgba(0,0,0,.35); }}
.kx-card::before {{ content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: linear-gradient(180deg, rgba(255,255,255,.07), transparent 45%); }}
.kx-card > * {{ position: relative; }}

/* ---------- AI reply avatar: a small gradient circle beside an assistant chat bubble */
.kx-sticker {{ display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px;
  border-radius: 50%; background: linear-gradient(135deg, #38BDF8, #FFFFFF); flex-shrink: 0;
  box-shadow: 0 4px 14px rgba(56,189,248,.45), inset 0 1px 0 rgba(255,255,255,.5); }}
.kx-green {{ background: {GREEN_BG}; border-color: rgba(74,222,128,.3); }}
.kx-amber {{ background: {AMBER_BG}; border-color: rgba(251,191,36,.3); }}
.kx-grey  {{ background: {GREY_BG}; border-color: rgba(255,255,255,.08); }}
/* the "ask" / primary cards stay dark glass with a glowing teal border -- solid teal fill is
   reserved for buttons and the user's own chat bubble, matching the reference's balance */
.kx-blue  {{ background: rgba(34,211,168,.08); border: 1px solid rgba(34,211,168,.35); color: {INK};
  box-shadow: 0 16px 36px rgba(34,211,168,.1); }}
.kx-blue .kx-big, .kx-blue .kx-mid, .kx-blue .kx-line, .kx-blue b {{ color: {INK}; }}
.kx-blue .kx-kicker, .kx-blue .kx-muted {{ color: {SHOUT}; }}

/* ---------- type scale */
.kx-kicker {{ font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: rgba(255,255,255,.5); margin-bottom: 6px; }}
.kx-big {{ font-size: 40px; font-weight: 900; letter-spacing: -.035em; line-height: 1.05; color: {INK}; }}
.kx-mid {{ font-size: 24px; font-weight: 800; letter-spacing: -.02em; color: {INK}; line-height: 1.2; }}
.kx-line {{ font-size: 15px; color: rgba(255,255,255,.85); margin-top: 8px; line-height: 1.6; }}
.kx-muted {{ font-size: 13px; color: rgba(255,255,255,.55); margin-top: 6px; line-height: 1.6; }}
.kx-card b {{ color: inherit; }}

/* ---------- chips & bars */
.kx-chip {{ display:inline-block; font-size:12px; font-weight:800; padding:6px 13px; border-radius:999px; margin-top:12px; letter-spacing:.02em; }}
.kx-chip.green {{ background: rgba(74,222,128,.16); color: {GREEN}; }}
.kx-chip.amber {{ background: rgba(251,191,36,.16); color: {AMBER}; }}
.kx-chip.grey  {{ background: rgba(255,255,255,.08); color: {GREY}; }}
.kx-chip.blue  {{ background: {GRAD}; color: #06150E; }}
.kx-bar {{ height:10px; background: rgba(255,255,255,.08); border-radius:99px; overflow:hidden; margin-top:12px; }}
.kx-bar > i {{ display:block; height:100%; border-radius:99px; background:{GRAD}; }}
.kx-row {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; padding:11px 0;
  border-bottom:1px solid rgba(255,255,255,.08); font-size:15px; color: rgba(255,255,255,.75); }}
.kx-row:last-child {{ border-bottom:0; }}
.kx-row b {{ font-size:17px; color: {INK}; }}
.kx-steps {{ display:flex; gap:6px; margin:4px 0 16px; }}
.kx-steps i {{ flex:1; height:6px; border-radius:99px; background: rgba(255,255,255,.1); }}
.kx-steps i.on {{ background:{GRAD}; }}
.kx-split {{ display:flex; height:14px; border-radius:99px; overflow:hidden; margin:12px 0 10px; gap:3px; }}
.kx-split > i {{ display:block; height:100%; border-radius:99px; }}
.kx-legend {{ font-size:13px; color: rgba(255,255,255,.7); line-height:1.9; }}
.kx-legend span {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; vertical-align:middle; }}

/* ---------- speech bubble, phone mock-ups, footer */
.kx-say {{ background: {SURFACE}; border:1px solid rgba(255,255,255,.1); color: {INK};
  border-radius: 24px 24px 24px 6px; padding: 14px 16px; font-size: 15px; line-height: 1.55;
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); animation: kxUp .55s {EASE} both; }}
.kx-say.me {{ background: {GRAD}; color: #06150E; border: 0; border-radius: 24px 24px 6px 24px; margin-left: auto; max-width: 85%; font-weight: 600; }}
.kx-phone {{ border:1px solid rgba(255,255,255,.14); border-radius:32px; padding:16px; background:#0F2A1E; color:{INK};
  max-width:300px; margin:8px auto; box-shadow: 0 24px 60px rgba(0,0,0,.5); }}
.kx-phone .bar {{ font-size:11px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:#06150E; background:{GRAD};
  margin:-16px -16px 14px; padding:10px 14px; border-radius:31px 31px 0 0; }}
.kx-phone .bar.other {{ background:#3B0764; color:#fff; }}
.kx-phone .kx-chip.green {{ background: rgba(74,222,128,.16); color: #4ADE80; }}
.kx-phone .kx-chip.grey {{ background: rgba(255,255,255,.08); color: #9CA3AF; }}
.kx-strike {{ text-decoration: line-through; color:rgba(255,255,255,.4); font-size:20px; margin-right:8px; }}
.kx-foot {{ font-size:10px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color: rgba(255,255,255,.35);
  text-align:center; margin:26px 0 8px; line-height:1.8; }}

/* ---------- Streamlit widgets inside our screens */
[class*="st-key-kx_"] [data-testid="stExpander"] details {{ border-radius: 24px; border: 1px solid rgba(255,255,255,.1);
  background: {SURFACE}; backdrop-filter: blur(18px); }}
[class*="st-key-kx_"] [data-testid="stExpander"] summary p {{ font-weight: 700; }}
/* the Material Symbols ligature font can fail to load (blocked/offline); hide the literal
   "keyboard_arrow_right" text and draw a plain triangle instead so it never shows as text */
[class*="st-key-kx_"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
  font-size: 0 !important; display: inline-flex; align-items: center; justify-content: center;
  width: 14px; transition: transform .2s {EASE}; }}
[class*="st-key-kx_"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"]::after {{
  content: "▸"; font-size: 13px; color: {SHOUT}; }}
[class*="st-key-kx_"] [data-testid="stExpander"] details[open] summary [data-testid="stIconMaterial"] {{
  transform: rotate(90deg); }}
[class*="st-key-kx_"] [data-baseweb="input"], [class*="st-key-kx_"] [data-baseweb="base-input"] {{
  border-radius: 999px !important; border-color: rgba(255,255,255,.14) !important; background: rgba(255,255,255,.05) !important; }}
[class*="st-key-kx_"] [data-testid="stTabs"] [role="tab"] p {{ font-weight: 700; }}
[class*="st-key-kx_"] [data-testid="stButtonGroup"] button {{ border-radius: 999px !important; }}
[class*="st-key-kx_console"] [data-testid="stDataFrame"] {{ border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(255,255,255,.1); }}
</style>
"""

DEFAULT_SHOP = "Gupta General Store"


def shop_name():
    """The merchant app's shop name always comes from the selected merchant -- the hand-authored
    demo merchant by default, or whichever mock merchant the Platform Console opened."""
    pm = st.session_state.get("platform_merchant")
    return pm["name"] if pm else DEFAULT_SHOP


def lang():
    return st.session_state.get("lang", "hi")


def t(key, **kw):
    return T(lang(), key, **kw)


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def avatar():
    """The small gradient avatar shown beside an AI/assistant reply bubble."""
    return '<span class="kx-sticker" style="margin-top:2px"></span>'


def ai_say(text):
    """An assistant reply bubble with its gradient avatar beside it, like a chat message."""
    st.markdown(f'<div style="display:flex;gap:10px;align-items:flex-start;margin:6px 0">{avatar()}'
                f'<div class="kx-say" style="flex:1;min-width:0">{text}</div></div>', unsafe_allow_html=True)


def header(title, subtitle, badge=None, extra_html=""):
    """Headline sits directly on the gradient page background -- no card box -- with a bold
    condensed display font, matching a 'Hi Josh!' style app greeting."""
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
