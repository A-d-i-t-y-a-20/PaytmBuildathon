"""Tiny JSON-only LLM helper for both features.

Provider: Gemini if GEMINI_API_KEY is set, else Claude if ANTHROPIC_API_KEY is set,
else None. Returns a parsed dict, or None on ANY failure. Callers always have a
deterministic fallback; the model never does arithmetic.
"""
import json
import os

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")


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


def call_json(system_prompt, payload, max_tokens=400, temperature=0.2):
    p = provider()
    if p is None:
        return None
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
            return _extract_json(resp.text)
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt, messages=[{"role": "user", "content": user}])
        return _extract_json("".join(b.text for b in resp.content if getattr(b, "type", None) == "text"))
    except Exception:
        return None
