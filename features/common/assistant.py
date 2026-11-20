"""A general-purpose "ask anything about Galla" help assistant -- voice or text.

This is a Siri-style help agent, not a command executor: it only answers questions
about what the app is and how it works, grounded in this merchant's real current
numbers (passed in as `facts`). Every money action (withdraw, pause, change
goal/limit, run an offer) stays in its own dedicated, confirmed flow in the Gullak
and Wapas Aao tabs -- this assistant explicitly refuses to perform those and points
the merchant to the right button instead, so it can never bypass that confirmation.
Returns None on any failure/no key/invented numbers; the caller always shows a
graceful fallback. Every turn is logged to a local SQLite database (see log()).
"""
import os
import re
import sqlite3
from datetime import datetime, timezone

from features.common import llm

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "assistant_log.db")

# Sarvam's detected STT language code -> the language name Gemini should reply in.
LANGUAGE_NAMES = {
    "hi": "Hindi in Devanagari script", "en": "English", "bn": "Bengali", "gu": "Gujarati",
    "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi", "pa": "Punjabi", "ta": "Tamil",
    "te": "Telugu", "od": "Odia",
}

SYSTEM = """You are "Ask Galla", a voice help assistant inside the Galla app -- a concept demo
fintech app for Indian kirana (small shop) owners, with three parts:
- Gullak tab: auto-savings that take a small share of each day's UPI settlement, skip bad
  days (slow sales, EMI due, stock purchase coming, a bad week), with pause/withdraw/change
  goal/change limit buttons.
- Grahak tab (Wapas Aao): finds regular customers who stopped coming, suggests a priced
  offer, reaches only customers who agreed, shows the result as profit after the offer's cost.
- Platform Console (desktop/ops view): pilot vs holdout merchants, a churn radar, safe
  credit timing, a value-proof line per merchant, and an outcome-fee calculator.

You are given `facts`: this merchant's real current numbers from this session (balance,
goal, mode, today's settlement, lapsed customers). Use ONLY the numbers in `facts` when
answering a question about this merchant's own data -- never invent a number that isn't
there. For a general "how does X work" question, answer from the app description above
without needing facts. Answer in at most 3 short sentences, in {language}. This is a
concept demo with mock data -- never claim real money, loans or payments actually move.
You cannot perform any action yourself (withdraw, pause, change a setting, run an offer);
if asked to do one, say which tab and button does that instead of doing it. If the
question has nothing to do with this app, say you can only help with questions about
Galla. Reply as JSON exactly like {{"answer": "..."}}.
"""


def _lang_name(lang):
    """Accepts either our app's 'hi'/'en' or a Sarvam STT code like 'hi-IN'/'ta-IN'."""
    short = (lang or "hi")[:2].lower()
    return LANGUAGE_NAMES.get(short, "Hindi in Devanagari script")


def _numbers_ok(text, facts):
    """Every number in the answer must come from the given facts (same guard pattern as
    features/wapas_aao/ai.py and features/platform/engine.py)."""
    allowed = set()
    for v in (facts or {}).values():
        allowed |= {int(n) for n in re.findall(r"\d+", str(v))}
    used = {int(n) for n in re.findall(r"\d+", (text or "").replace(",", ""))}
    return used <= allowed


def ask(question, lang="hi", facts=None):
    """One Q&A turn. Returns the answer string, or None if the AI is unavailable, fails,
    or invents a number not present in `facts`."""
    payload = {"question": question, "facts": facts or {}}
    out = llm.call_json(SYSTEM.format(language=_lang_name(lang)), payload, max_tokens=200)
    if not isinstance(out, dict) or not out.get("answer"):
        return None
    answer = str(out["answer"]).strip()
    if not answer or not _numbers_ok(answer, facts):
        return None
    return answer


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, shop TEXT, mode TEXT,
        language TEXT, question TEXT, answer TEXT)""")
    return conn


def log(question, answer, language, mode, shop):
    """Persist one Q&A turn to the local SQLite database (features/common/data/assistant_log.db,
    gitignored -- never committed). Never raises: a logging failure must not break the answer."""
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO conversations (ts, shop, mode, language, question, answer) VALUES (?,?,?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), shop, mode, language, question, answer))
    except Exception:
        pass


def recent(limit=20):
    """Most recent conversation turns, newest first. Used by a demo/ops log viewer."""
    try:
        with _connect() as conn:
            cols = ("ts", "shop", "mode", "language", "question", "answer")
            rows = conn.execute(f"SELECT {', '.join(cols)} FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(zip(cols, r)) for r in rows.fetchall()]
    except Exception:
        return []
