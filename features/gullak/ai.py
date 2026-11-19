"""LLM calls for Gullak. Every function degrades to None / code fallback."""
import os

from features.common import llm

PROMPT_VERSION = "gullak_v1"
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", f"{PROMPT_VERSION}.md")


def _prompt():
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def smart_amount(payload):
    """llm_fn for engine.decide_day: returns {pct, reason} or None."""
    return llm.call_json(_prompt(), payload, max_tokens=200)


def read_command(text, balance):
    return llm.call_json(_prompt(), {"task": "command", "text": text, "balance": int(balance)}, max_tokens=200)


def available():
    return llm.available()
