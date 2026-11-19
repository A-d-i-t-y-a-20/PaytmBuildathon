"""LLM calls for Wapas Aao. Every function returns None on failure; callers fall back to code text."""
import os
import re

from features.common import llm
from features.common.i18n import llm_language

PROMPT_VERSION = "wapas_v2"
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", f"{PROMPT_VERSION}.md")


def _prompt():
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def available():
    return llm.available()


def understand(text, lang="hi"):
    return llm.call_json(_prompt(), {"task": "understand", "text": text, "language": llm_language(lang)}, max_tokens=200)


def phrase(facts, lang="hi"):
    return llm.call_json(_prompt(), {"task": "phrase", "facts": facts, "language": llm_language(lang)}, max_tokens=250)


def numbers_ok(text, facts):
    """Every number in model text must exist in the facts."""
    allowed = set()
    for v in facts.values():
        allowed |= {int(n) for n in re.findall(r"\d+", str(v))}
    used = {int(n) for n in re.findall(r"\d+", (text or "").replace(",", ""))}
    return used <= allowed
