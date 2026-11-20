"""Tiny JSON-only LLM helper for both features.

Provider: Gemini if GEMINI_API_KEY is set, else Claude if ANTHROPIC_API_KEY is set,
else None. Returns a parsed dict, or None on ANY failure. Callers always have a
deterministic fallback; the model never does arithmetic.

GEMINI_MODEL default checked against ai.google.dev/gemini-api/docs/models on 2026-11-20:
gemini-3.1-flash-lite is listed as stable. Override via GEMINI_MODEL / CLAUDE_MODEL secrets.
"""
import json
import os

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

# Demo-visible status only: provider, model, last error TYPE and a short message. Never the key.
_status = {"provider": None, "model": None, "ok": None, "error_type": None, "error_msg": None}


def provider():
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def available():
    return provider() is not None


def _extract_json(raw_text):
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def status():
    return dict(_status)


def summary():
    """One line for Demo controls: 'AI: <state>'."""
    p = provider()
    if p is None:
        return "no key"
    model = GEMINI_MODEL if p == "gemini" else CLAUDE_MODEL
    if _status["ok"] is True and _status["provider"] == p:
        return f"{p} OK ({model})"
    if _status["ok"] is False and _status["provider"] == p:
        return f"error {_status['error_type']}: {_status['error_msg']}"
    return f"{p} configured, untested"


def test_call():
    """Used by the 'Test AI' button: one tiny real call. Returns True/False, also updates status()."""
    return call_json('Reply with exactly this JSON: {"ok": true}', {"ping": "test"}, max_tokens=20) is not None


def call_json(system_prompt, payload, max_tokens=400, temperature=0.2):
    p = provider()
    if p is None:
        return None
    model = GEMINI_MODEL if p == "gemini" else CLAUDE_MODEL
    user = json.dumps(payload, ensure_ascii=False)
    try:
        if p == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt, temperature=temperature,
                    max_output_tokens=max_tokens, response_mime_type="application/json"),
            )
            out = _extract_json(resp.text)
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            resp = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=max_tokens, temperature=temperature,
                system=system_prompt, messages=[{"role": "user", "content": user}])
            out = _extract_json("".join(b.text for b in resp.content if getattr(b, "type", None) == "text"))
        _status.update(provider=p, model=model, ok=True, error_type=None, error_msg=None)
        return out
    except Exception as exc:
        _status.update(provider=p, model=model, ok=False,
                        error_type=type(exc).__name__, error_msg=str(exc)[:120])
        return None
