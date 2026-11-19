"""Galla Gullak engine: all rules and arithmetic, in plain Python.

The LLM is only allowed to (a) pick a pct INSIDE bounds computed here, (b) write
short Hinglish text, (c) read voice commands. Every number shown to the merchant
comes from this module. Mock data only -- no real money moves.
"""
import re
from datetime import date, timedelta

MIN_PCT = 0.5
MAX_CAP = 5.0
DEFAULT_CAP = 3.0
MIN_AMOUNT = 9
SUGGEST_DAYS = 7
YES_FOR_AUTO = 3

GOALS = ["Diwali", "Shaadi", "Emergency", "Dukaan", "Bas bachat"]

REASONS = {
    "paused": "Gullak ruka hua hai",
    "no_data": "Aaj ka data abhi nahi aaya",
    "slow_day": "Aaj bikri kam thi, paisa aapke paas rakha",
    "emi_soon": "EMI {n} din mein hai, paisa haath mein rakha",
    "stock_spend": "Maal kharidna hai, paisa haath mein rakha",
    "too_small": "Rakam Rs 9 se kam thi",
}


# ---------------------------------------------------------------- helpers
def _d(day):
    return day if isinstance(day, date) else date.fromisoformat(day)


def rs(n):
    """Indian digit grouping: 123456 -> '1,23,456'."""
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return ("-" if n < 0 else "") + s


def clamp_cap(cap_pct):
    try:
        cap = float(cap_pct)
    except (TypeError, ValueError):
        cap = DEFAULT_CAP
    return max(1.0, min(MAX_CAP, cap))


# ---------------------------------------------------------------- inputs
def usual_for(settlements, day):
    """Average settlement for the same weekday over the previous 4 weeks."""
    d = _d(day)
    prev = [settlements.get((d - timedelta(weeks=k)).isoformat()) for k in range(1, 5)]
    prev = [p for p in prev if p is not None]
    return sum(prev) / len(prev) if prev else None


def day_inputs(settlements, obligations, day):
    d = _d(day)
    key = d.isoformat()
    due_in = None
    for due in obligations.get("emi_due_dates", []):
        delta = (_d(due) - d).days
        if delta >= 0 and (due_in is None or delta < due_in):
            due_in = delta
    return {
        "date": key,
        "settlement": settlements.get(key),
        "usual": usual_for(settlements, d),
        "emi_amount": obligations.get("emi_amount", 0),
        "emi_due_in_days": due_in,
        "cash": obligations.get("cash_by_date", {}).get(key, obligations.get("default_cash", 0)),
        "stock_spend_3d": obligations.get("stock_spend_by_date", {}).get(key, obligations.get("default_stock_spend", 0)),
    }


# ---------------------------------------------------------------- rules
def evaluate(inp, cap_pct, paused=False):
    """Skip checks + pct bounds. Returns a dict; no LLM involved."""
    cap = clamp_cap(cap_pct)
    s, usual = inp.get("settlement"), inp.get("usual")
    ev = {"skip": False, "reason_code": None, "reason": "", "day_type": None,
          "ratio": None, "bounds": None, "cap": cap}

    def skip(code, **kw):
        ev.update(skip=True, reason_code=code, reason=REASONS[code].format(**kw))
        return ev

    if paused:
        return skip("paused")
    if s is None or s <= 0:
        return skip("no_data")
    ratio = (s / usual) if usual else 1.0
    ev["ratio"] = round(ratio, 2)
    if usual and s < 0.5 * usual:
        ev["day_type"] = "slow"
        return skip("slow_day")
    due = inp.get("emi_due_in_days")
    emi = inp.get("emi_amount") or 0
    if due is not None and due <= 2 and emi > 0 and inp.get("cash", 0) < emi * 1.2:
        return skip("emi_soon", n=due)
    if inp.get("stock_spend_3d", 0) > inp.get("cash", 0):
        return skip("stock_spend")
    good = ratio > 1.2
    ev["day_type"] = "good" if good else "normal"
    hi = cap if good else max(MIN_PCT, cap / 2)
    ev["bounds"] = (MIN_PCT, round(hi, 2))
    return ev


def fallback_pct(ev):
    return ev["bounds"][1]


def validate_pct(pct, bounds):
    """LLM pct must be inside bounds; anything else clamps to the LOWER bound."""
    lo, hi = bounds
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return lo, False
    if lo <= p <= hi:
        return round(p, 2), True
    return lo, False


def compute_amount(settlement, pct):
    amt = int(round(settlement * pct / 100.0))
    return amt if amt >= MIN_AMOUNT else 0


def _short(text, max_words):
    words = str(text or "").split()
    return " ".join(words[:max_words])


def numbers_in(text):
    return {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text or "") if n.replace(",", "").isdigit()}


def decide_day(settlements, obligations, state, day, llm_fn=None):
    """Full daily decision. llm_fn(payload) -> dict|None picks pct within bounds."""
    inp = day_inputs(settlements, obligations, day)
    ev = evaluate(inp, state.get("cap_pct", DEFAULT_CAP), paused=state.get("mode") == "paused")
    rec = {"date": inp["date"], "settlement": inp["settlement"], "usual": inp["usual"],
           "day_type": ev["day_type"], "ratio": ev["ratio"], "bounds": ev["bounds"],
           "pct": 0.0, "amount": 0, "skip": ev["skip"], "reason_code": ev["reason_code"],
           "reason": ev["reason"], "used_fallback": True, "spoken_line": ""}
    if ev["skip"]:
        rec["spoken_line"] = spoken_template(rec)
        return rec

    pct, reason, used_fb = fallback_pct(ev), None, True
    if llm_fn is not None:
        out = llm_fn({
            "task": "smart_amount",
            "today_settlement": inp["settlement"], "usual_settlement": round(inp["usual"] or 0),
            "day_type": ev["day_type"], "emi_due_in_days": inp["emi_due_in_days"],
            "emi_amount": inp["emi_amount"], "cash_in_hand": inp["cash"],
            "stock_spend_next_3_days": inp["stock_spend_3d"],
            "pct_bounds": {"min": ev["bounds"][0], "max": ev["bounds"][1]},
        })
        if isinstance(out, dict) and "pct" in out:
            pct, in_bounds = validate_pct(out.get("pct"), ev["bounds"])
            used_fb = False
            if in_bounds and out.get("reason"):
                reason = _short(out["reason"], 12)
    amount = compute_amount(inp["settlement"], pct)
    if amount == 0:
        rec.update(skip=True, reason_code="too_small", reason=REASONS["too_small"], pct=pct)
        rec["spoken_line"] = spoken_template(rec)
        return rec
    if reason is None:
        reason = "Aaj achha din tha, thoda zyada bachaya" if ev["day_type"] == "good" else "Aam din, thoda sa bachaya"
    rec.update(pct=pct, amount=amount, reason=reason, used_fallback=used_fb)
    rec["spoken_line"] = spoken_template(rec)
    return rec


def spoken_template(rec):
    s = rec.get("settlement") or 0
    if rec.get("skip"):
        if rec.get("reason_code") == "no_data":
            return "Aaj ka data abhi nahi aaya."
        return f"Aaj gullak mein kuch nahi daala. {rec['reason']}. Poore Rs {rs(s)} aapke paas."
    return f"Aaj Rs {rs(s)} aaye. Rs {rs(rec['amount'])} gullak mein, aapke paas Rs {rs(s - rec['amount'])}."


def guard_spoken(line, rec, extra_allowed=()):
    """Use the LLM line only if every number in it came from code."""
    if not line:
        return spoken_template(rec)
    s = int(rec.get("settlement") or 0)
    allowed = {s, int(rec.get("amount", 0)), s - int(rec.get("amount", 0)), *[int(x) for x in extra_allowed]}
    if numbers_in(line) - allowed:
        return spoken_template(rec)
    return _short(line, 20)


# ---------------------------------------------------------------- state changes
def _log(state, rec, action, amount=None, reason=None):
    state.setdefault("history", []).append({
        "date": rec["date"], "settlement": rec.get("settlement"), "pct": rec.get("pct", 0),
        "amount": rec.get("amount", 0) if amount is None else amount, "action": action,
        "reason": rec.get("reason", "") if reason is None else reason,
    })


def has_entry(state, day):
    return any(h["date"] == day and h["action"] in ("saved", "skipped", "declined") for h in state.get("history", []))


def apply_save(state, rec):
    state["balance"] = state.get("balance", 0) + rec["amount"]
    _log(state, rec, "saved")


def apply_skip(state, rec):
    _log(state, rec, "skipped", amount=0)


def apply_decline(state, rec):
    _log(state, rec, "declined", amount=0, reason="Aapne mana kiya")


def suggest_answer(state, rec, yes):
    """Evening confirm card answer (suggest mode)."""
    if yes:
        apply_save(state, rec)
        state["yes_count"] = state.get("yes_count", 0) + 1
    else:
        apply_decline(state, rec)
    state["suggest_days_left"] = max(0, state.get("suggest_days_left", SUGGEST_DAYS) - 1)
    if state.get("yes_count", 0) >= YES_FOR_AUTO and state.get("mode") == "suggest" and not state.get("auto_offer_done"):
        state["auto_offer_pending"] = True
    return state


def accept_auto(state, yes):
    state["auto_offer_pending"] = False
    state["auto_offer_done"] = True
    if yes:
        state["mode"] = "auto"
    return state


def process_day(state, rec):
    """Auto / paused mode, or a skip day in suggest mode: record without asking."""
    if rec["skip"]:
        apply_skip(state, rec)
        if state.get("mode") == "suggest":
            state["suggest_days_left"] = max(0, state.get("suggest_days_left", SUGGEST_DAYS) - 1)
    elif state.get("mode") == "auto":
        apply_save(state, rec)
    return state


def withdraw(state, amount, day):
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return False, "Rakam samajh nahi aayi."
    bal = int(state.get("balance", 0))
    if amount <= 0:
        return False, "Rakam Rs 1 se zyada honi chahiye."
    if amount > bal:
        return False, f"Gullak mein sirf Rs {rs(bal)} hai. Itna nahi nikaal sakte."
    state["balance"] = bal - amount
    state.setdefault("history", []).append({"date": _d(day).isoformat(), "settlement": None, "pct": 0,
                                            "amount": amount, "action": "withdrawn", "reason": "Aapne nikaala"})
    return True, f"Rs {rs(amount)} aapke account mein (demo). Gullak mein Rs {rs(state['balance'])} bache."


def set_mode(state, mode):
    if mode in ("suggest", "auto", "paused"):
        if mode == "paused" and state.get("mode") != "paused":
            state["mode_before_pause"] = state.get("mode", "suggest")
        state["mode"] = mode
    return state


def resume(state):
    state["mode"] = state.pop("mode_before_pause", "auto") or "auto"
    if state["mode"] == "paused":
        state["mode"] = "auto"
    return state


# ---------------------------------------------------------------- summaries
def avg_daily(settlements, day, days=30):
    d = _d(day)
    vals = [settlements[(d - timedelta(days=k)).isoformat()] for k in range(1, days + 1)
            if (d - timedelta(days=k)).isoformat() in settlements]
    return sum(vals) / len(vals) if vals else 0


def buffer_days(balance, avg):
    return round(balance / avg, 1) if avg else 0.0


def goal_progress(state):
    target = (state.get("goal") or {}).get("target") or 0
    return min(1.0, state.get("balance", 0) / target) if target else 0.0


def goal_status(state):
    g = state.get("goal") or {}
    p = goal_progress(state)
    if p >= 1.0:
        return {"reached": True, "progress": 1.0,
                "message": f"Badhai ho! {g.get('name', 'Goal')} ka lakshya poora. Rs {rs(state.get('balance', 0))} jama. Naya goal chunein?"}
    return {"reached": False, "progress": p, "message": f"{g.get('name', 'Goal')} {int(p * 100)}%"}


def week_drop(settlements, day):
    """% drop of the last 7 days vs their usual (positive = down)."""
    d = _d(day)
    got = usual = 0.0
    for k in range(0, 7):
        dd = d - timedelta(days=k)
        s, u = settlements.get(dd.isoformat()), usual_for(settlements, dd)
        if s is not None and u:
            got += s
            usual += u
    return round(100 * (1 - got / usual)) if usual else 0


def backtest(settlements, obligations, cap_pct, today, days=30):
    """Run the same rules (code fallback pct, auto mode) over the last N days before today."""
    end = _d(today)
    state = {"mode": "auto", "cap_pct": cap_pct, "balance": 0, "history": []}
    reasons = {}
    for k in range(days, 0, -1):
        day = (end - timedelta(days=k)).isoformat()
        rec = decide_day(settlements, obligations, state, day, llm_fn=None)
        if rec["skip"]:
            apply_skip(state, rec)
            reasons[rec["reason_code"]] = reasons.get(rec["reason_code"], 0) + 1
        else:
            apply_save(state, rec)
    saved = [h for h in state["history"] if h["action"] == "saved"]
    return {"total": state["balance"], "days": days, "saved_days": len(saved),
            "skipped_days": days - len(saved), "skip_reasons": reasons, "history": state["history"],
            "sum_check": sum(h["amount"] for h in saved)}


def summary_line(state, day):
    """One line for a closing briefing."""
    if not state or not state.get("opted_in"):
        return ""
    key = _d(day).isoformat()
    todays = [h for h in state.get("history", []) if h["date"] == key and h["action"] in ("saved", "skipped", "declined")]
    g = goal_status(state)
    goal_part = f"{(state.get('goal') or {}).get('name', 'Goal')} goal {int(g['progress'] * 100)}%."
    if todays and todays[-1]["action"] == "saved":
        return f"Aaj Rs {rs(todays[-1]['amount'])} gullak mein gaye. {goal_part}"
    if todays and todays[-1]["action"] == "skipped":
        return f"Aaj gullak nahi bhara ({todays[-1]['reason'].lower()}). {goal_part}"
    return f"Gullak mein Rs {rs(state.get('balance', 0))} jama. {goal_part}"


# ---------------------------------------------------------------- voice / text commands
_NUM_WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
              "saat": 7, "aath": 8, "nau": 9, "das": 10, "bees": 20, "pachaas": 50, "pachas": 50}
_HALF = {"dedh": 1.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5}
_MULT = {"sau": 100, "so": 100, "hazar": 1000, "hazaar": 1000, "hajar": 1000, "hazzar": 1000, "hajaar": 1000,
         "thousand": 1000, "hundred": 100}
_ALL = {"sab", "saara", "sara", "poora", "pura", "saare", "sare", "all"}
_GOAL_WORDS = {"diwali": "Diwali", "shaadi": "Shaadi", "shadi": "Shaadi", "emergency": "Emergency",
               "dukaan": "Dukaan", "dukan": "Dukaan", "saaman": "Dukaan", "saman": "Dukaan"}


def parse_amount(text):
    """Digits ('2000', '2,000', '2k') or Hindi words ('do hazar', 'paanch sau', 'dhai hazar').
    Returns int, 'all', or None."""
    t = (text or "").lower()
    m = re.search(r"(\d[\d,]*)\s*(k|hazar|hazaar|thousand)?\b", t)
    if m:
        n = int(m.group(1).replace(",", ""))
        if m.group(2):
            n *= 1000
        if "%" not in t[m.end():m.end() + 2]:
            return n
    words = re.findall(r"[a-z]+", t)
    for i, w in enumerate(words):
        if w in _MULT:
            prev = words[i - 1] if i > 0 else ""
            base = _NUM_WORDS.get(prev) or _HALF.get(prev) or 1
            return int(base * _MULT[w])
    if any(w in _ALL for w in words):
        return "all"
    return None


def parse_command(text):
    """Deterministic Hinglish command parser (used when the LLM is down, and to
    cross-check the LLM). Money commands always need confirmation."""
    t = (text or "").lower().strip()
    words = set(re.findall(r"[a-z]+", t))
    amount = parse_amount(t)
    out = {"intent": "none", "amount": 0, "goal_name": None, "cap": None, "needs_confirm": False, "question": None}

    if re.search(r"nikal|nikaal|withdraw|wapas chahiye|de do", t) or (amount and re.search(r"\bse\b", t) and "gullak" in t):
        out.update(intent="withdraw", amount=amount or 0, needs_confirm=True)
        if not amount:
            out["question"] = "Kitne paise nikaalne hain?"
        return out
    if re.search(r"limit|cap|pratishat|percent|%", t):
        m = re.search(r"(\d+(?:\.\d+)?)\s*(%|percent|pratishat)?", t)
        out.update(intent="change_cap", cap=float(m.group(1)) if m else None, needs_confirm=True)
        if out["cap"] is None:
            out["question"] = "Kitna pratishat rakhein? 1, 2 ya 3?"
        return out
    if words & set(_GOAL_WORDS) and re.search(r"bacha|goal|lakshya|liye", t):
        name = next(_GOAL_WORDS[w] for w in _GOAL_WORDS if w in words)
        out.update(intent="set_goal", goal_name=name, amount=amount if isinstance(amount, int) else 0, needs_confirm=True)
        return out
    if re.search(r"band|rok|ruk|pause|stop", t):
        out["intent"] = "pause"
        return out
    if re.search(r"chalu|shuru|resume|start|phir se", t):
        out["intent"] = "resume"
        return out
    if re.search(r"kitna|kitne|balance|status|jama|haal", t):
        out["intent"] = "status"
        return out
    return out


INTENTS = {"set_goal", "pause", "resume", "withdraw", "change_cap", "status", "none"}


def validate_command(llm_out, text, state):
    """Merge an LLM reading with the deterministic parse. Code wins on numbers;
    every money action needs confirmation no matter what the text or model says."""
    base = parse_command(text)
    if isinstance(llm_out, dict) and llm_out.get("intent") in INTENTS:
        intent = llm_out["intent"]
        if base["intent"] != "none" and base["intent"] != intent:
            intent = base["intent"]  # deterministic keywords win on disagreement
        base["intent"] = intent
        if intent == "set_goal" and not base.get("goal_name"):
            name = str(llm_out.get("goal_name") or "").strip().title()
            base["goal_name"] = name if name in GOALS else None
        # an LLM amount is only accepted if that number literally appears in the user's text
        if not base.get("amount") and llm_out.get("amount"):
            try:
                a = int(float(llm_out["amount"]))
                if a in numbers_in(text):
                    base["amount"] = a
            except (TypeError, ValueError):
                pass
        if llm_out.get("question") and base["intent"] == "none":
            base["question"] = _short(llm_out["question"], 12)
    if base["intent"] == "withdraw":
        if base["amount"] == "all":
            base["amount"] = int(state.get("balance", 0))
        base["needs_confirm"] = True
        if not base["amount"]:
            base["question"] = "Kitne paise nikaalne hain?"
    if base["intent"] == "change_cap":
        base["needs_confirm"] = True
        if base.get("cap") is not None:
            base["cap"] = clamp_cap(base["cap"])
    if base["intent"] == "set_goal":
        base["needs_confirm"] = True
    if base["intent"] == "none" and not base.get("question"):
        base["question"] = "Samajh nahi aaya. Gullak band karna hai, paise nikaalne hain, ya balance dekhna hai?"
    return base
