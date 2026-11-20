"""Ask Galla assistant tests. No API key needed (and must not need one to pass)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from features.common import assistant


def test_ask_returns_none_without_a_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert assistant.ask("Gullak kya hai?", lang="hi") is None
