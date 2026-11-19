"""Galla Gullak engine: all rules and arithmetic, in plain Python.

The LLM is only allowed to (a) pick a pct INSIDE bounds computed here, (b) write
short Hinglish text, (c) read voice commands. Every number shown to the merchant
comes from this module. Mock data only -- no real money moves.
"""
import re
from datetime import date, timedelta

from features.common.i18n import T, goal_label, llm_language

MIN_PCT = 0.5
MAX_CAP = 5.0
DEFAULT_CAP = 3.0
MIN_AMOUNT = 9
SUGGEST_DAYS = 7
YES_FOR_AUTO = 3

GOALS = ["Diwali", "Shaadi", "Emergency", "Dukaan", "Bas bachat"]

# Where the gullak money goes (all through Paytm partners; concept, no rates or returns shown)
INSTRUMENTS = ("gold", "silver", "fd", "fund")
DEFAULT_ALLOCATION = {"gold": 100}


# ---------------------------------------------------------------- allocation
def normalize_allocation(choice):
    """List of instruments -> equal % split summing to 100. Empty/invalid -> all gold."""
    picks = [i for i in INSTRUMENTS if i in (choice or [])]
    if not picks:
        return dict(DEFAULT_ALLOCATION)
    base, extra = divmod(100, len(picks))
    return {k: base + (1 if n < extra else 0) for n, k in enumerate(picks)}


def split_amount(amount, allocation):
    """Split whole rupees by allocation %, largest remainder so parts always sum to amount."""
    alloc = allocation or DEFAULT_ALLOCATION
    total = sum(alloc.values()) or 1
    raw = {k: amount * v / total for k, v in alloc.items()}
    parts = {k: int(x) for k, x in raw.items()}
    left = int(amount) - sum(parts.values())
    for k in sorted(raw, key=lambda k: raw[k] - parts[k], reverse=True)[:left]:
        parts[k] += 1
    return parts

REASON_CODES = ("paused", "no_data", "slow_day", "emi_soon", "stock_spend", "too_small")


def reason_text(code, lang="hi", **kw):
    return T(lang, f"r_{code}", **kw)


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
def evaluate(inp, cap_pct, paused=False, lang="hi"):
    """Skip checks + pct bounds. Returns a dict; no LLM involved."""
    cap = clamp_cap(cap_pct)
    s, usual = inp.get("settlement"), inp.get("usual")
    ev = {"skip": False, "reason_code": None, "reason_kw": {}, "reason": "", "day_type": None,
          "ratio": None, "bounds": None, "cap": cap}

    def skip(code, **kw):
        ev.update(skip=True, reason_code=code, reason_kw=kw, reason=reason_text(code, lang, **kw))
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


def decide_day(settlements, obligations, state, day, llm_fn=None, lang="hi"):
    """Full daily decision. llm_fn(payload) -> dict|None picks pct within bounds."""
    inp = day_inputs(settlements, obligations, day)
    ev = evaluate(inp, state.get("cap_pct", DEFAULT_CAP), paused=state.get("mode") == "paused", lang=lang)
    rec = {"date": inp["date"], "settlement": inp["settlement"], "usual": inp["usual"],
           "day_type": ev["day_type"], "ratio": ev["ratio"], "bounds": ev["bounds"],
           "pct": 0.0, "amount": 0, "skip": ev["skip"], "reason_code": ev["reason_code"],
           "reason_kw": ev["reason_kw"], "reason": ev["reason"], "llm_reason": None, "llm_lang": None,
           "used_fallback": True, "spoken_line": "", "lang": lang}
    if ev["skip"]:
        rec["spoken_line"] = spoken_template(rec, lang)
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
            "language": llm_language(lang),
        })
        if isinstance(out, dict) and "pct" in out:
            pct, in_bounds = validate_pct(out.get("pct"), ev["bounds"])
            used_fb = False
            if in_bounds and out.get("reason"):
                reason = _short(out["reason"], 12)
    amount = compute_amount(inp["settlement"], pct)
    if amount == 0:
        rec.update(skip=True, reason_code="too_small", reason=reason_text("too_small", lang), pct=pct)
        rec["spoken_line"] = spoken_template(rec, lang)
        return rec
    code = "good_day" if ev["day_type"] == "good" else "normal_day"
    rec.update(pct=pct, amount=amount, reason_code=code, reason=reason or reason_text(code, lang),
               llm_reason=reason, llm_lang=lang if reason else None, used_fallback=used_fb)
    rec["spoken_line"] = spoken_template(rec, lang)
    return rec


def spoken_template(rec, lang="hi"):
    s = rec.get("settlement") or 0
    if rec.get("skip"):
        if rec.get("reason_code") == "no_data":
            return reason_text("no_data", lang)
        why = reason_text(rec["reason_code"], lang, **(rec.get("reason_kw") or {}))
        return T(lang, "sp_skip", why=why, s=rs(s))
    return T(lang, "sp_saved", s=rs(s), a=rs(rec["amount"]), k=rs(s - rec["amount"]))


def entry_reason(entry, lang="hi"):
    """Reason for a history entry in the current language (LLM text only if written in that language)."""
    if entry.get("llm_reason") and entry.get("llm_lang") == lang:
        return entry["llm_reason"]
    code = entry.get("reason_code")
    if code:
        return reason_text(code, lang, **(entry.get("reason_kw") or {}))
    return entry.get("reason", "")


def guard_spoken(line, rec, extra_allowed=(), lang="hi"):
    """Use the LLM line only if every number in it came from code."""
    if not line:
        return spoken_template(rec, lang)
    s = int(rec.get("settlement") or 0)
    allowed = {s, int(rec.get("amount", 0)), s - int(rec.get("amount", 0)), *[int(x) for x in extra_allowed]}
    if numbers_in(line) - allowed:
        return spoken_template(rec, lang)
    return _short(line, 20)


# ---------------------------------------------------------------- state changes
def _log(state, rec, action, amount=None, reason_code=None):
    state.setdefault("history", []).append({
        "date": rec["date"], "settlement": rec.get("settlement"), "pct": rec.get("pct", 0),
        "amount": rec.get("amount", 0) if amount is None else amount, "action": action,
        "reason_code": reason_code or rec.get("reason_code"),
        "reason_kw": {} if reason_code else (rec.get("reason_kw") or {}),
        "llm_reason": None if reason_code else rec.get("llm_reason"),
        "llm_lang": None if reason_code else rec.get("llm_lang"),
        "reason": rec.get("reason", ""),
    })


def has_entry(state, day):
    return any(h["date"] == day and h["action"] in ("saved", "skipped", "declined") for h in state.get("history", []))


def apply_save(state, rec):
    state["balance"] = state.get("balance", 0) + rec["amount"]
    _log(state, rec, "saved")
    state["history"][-1]["split"] = split_amount(rec["amount"], state.get("allocation"))


def apply_skip(state, rec):
    _log(state, rec, "skipped", amount=0)


def apply_decline(state, rec):
    _log(state, rec, "declined", amount=0, reason_code="declined")


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


def withdraw(state, amount, day, lang="hi"):
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return False, T(lang, "wd_bad_amount")
    bal = int(state.get("balance", 0))
    if amount <= 0:
        return False, T(lang, "wd_min")
    if amount > bal:
        return False, T(lang, "wd_too_much", a=rs(bal))
    held = holdings(state)
    state["balance"] = bal - amount
    state.setdefault("history", []).append({"date": _d(day).isoformat(), "settlement": None, "pct": 0,
                                            "amount": amount, "action": "withdrawn", "reason_code": "withdrawn",
                                            "reason_kw": {}, "reason": "",
                                            "split": split_amount(amount, {k: v for k, v in held.items() if v > 0})})
    return True, T(lang, "wd_done", a=rs(amount), left=rs(state["balance"]))


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
def holdings(state):
    """Rupees per instrument, from history. Entries without a split (older/mock) count as gold.
    Any opening balance not explained by history is shown as gold too."""
    out = {k: 0 for k in INSTRUMENTS}
    for h in state.get("history", []):
        split = h.get("split") or {"gold": h.get("amount", 0)}
        sign = 1 if h["action"] == "saved" else -1 if h["action"] == "withdrawn" else 0
        for k, v in split.items():
            out[k] = out.get(k, 0) + sign * v
    gap = int(state.get("balance", 0)) - sum(out.values())
    if gap > 0:
        out["gold"] += gap
    return out


def analytics(state, today, days=30):
    """Numbers for the savings analytics card. All code, no LLM."""
    end = _d(today)
    start = end - timedelta(days=days - 1)
    hist = [h for h in state.get("history", []) if start <= _d(h["date"]) <= end]
    saved = [h for h in hist if h["action"] == "saved"]
    skipped = [h for h in hist if h["action"] in ("skipped", "declined")]
    withdrawn = sum(h["amount"] for h in hist if h["action"] == "withdrawn")
    period_saved = sum(h["amount"] for h in saved)
    # balance at the start of the window = current balance minus net change inside it
    bal_start = int(state.get("balance", 0)) - period_saved + withdrawn
    series, running = [], bal_start
    by_day = {}
    for h in hist:
        by_day.setdefault(h["date"], 0)
        by_day[h["date"]] += h["amount"] if h["action"] == "saved" else -h["amount"] if h["action"] == "withdrawn" else 0
    for k in range(days):
        d = (start + timedelta(days=k)).isoformat()
        running += by_day.get(d, 0)
        series.append({"date": d, "balance": running})
    best = max(saved, key=lambda h: h["amount"]) if saved else None
    held = holdings(state)
    total_held = sum(v for v in held.values() if v > 0) or 1
    return {
        "balance": int(state.get("balance", 0)), "period_saved": period_saved, "withdrawn": withdrawn,
        "days_saved": len(saved), "days_skipped": len(skipped),
        "avg_per_saved_day": round(period_saved / len(saved)) if saved else 0,
        "best_day": {"date": best["date"], "amount": best["amount"]} if best else None,
        "series": series, "holdings": held,
        "shares": {k: round(100 * max(v, 0) / total_held) for k, v in held.items()},
        "goal_pct": int(goal_progress(state) * 100),
    }


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


def goal_status(state, lang="hi"):
    g = state.get("goal") or {}
    name = goal_label(lang, g.get("name", "Bas bachat"))
    p = goal_progress(state)
    if p >= 1.0:
        return {"reached": True, "progress": 1.0,
                "message": T(lang, "goal_reached", goal=name, a=rs(state.get("balance", 0)))}
    return {"reached": False, "progress": p, "message": T(lang, "goal_progress", goal=name, pct=int(p * 100))}


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


def summary_line(state, day, lang="hi"):
    """One line for a closing briefing."""
    if not state or not state.get("opted_in"):
        return ""
    key = _d(day).isoformat()
    todays = [h for h in state.get("history", []) if h["date"] == key and h["action"] in ("saved", "skipped", "declined")]
    goal = goal_label(lang, (state.get("goal") or {}).get("name", "Bas bachat"))
    pct = int(goal_status(state, lang)["progress"] * 100)
    if todays and todays[-1]["action"] == "saved":
        return T(lang, "sum_saved", a=rs(todays[-1]["amount"]), goal=goal, pct=pct)
    if todays and todays[-1]["action"] == "skipped":
        return T(lang, "sum_skipped", why=entry_reason(todays[-1], lang), goal=goal, pct=pct)
    return T(lang, "sum_balance", a=rs(state.get("balance", 0)), goal=goal, pct=pct)


# ---------------------------------------------------------------- voice / text commands
_NUM_WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
              "saat": 7, "aath": 8, "nau": 9, "das": 10, "bees": 20, "pachaas": 50, "pachas": 50,
              "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "fifty": 50,
              "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8,
              "नौ": 9, "दस": 10, "बीस": 20, "पचास": 50}
_HALF = {"dedh": 1.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5, "डेढ़": 1.5, "ढाई": 2.5}
_MULT = {"sau": 100, "so": 100, "hazar": 1000, "hazaar": 1000, "hajar": 1000, "hazzar": 1000, "hajaar": 1000,
         "thousand": 1000, "hundred": 100, "सौ": 100, "हज़ार": 1000, "हजार": 1000}
_ALL = {"sab", "saara", "sara", "poora", "pura", "saare", "sare", "all", "everything", "सब", "सारा", "सारे", "पूरा"}
_GOAL_WORDS = {"diwali": "Diwali", "shaadi": "Shaadi", "shadi": "Shaadi", "wedding": "Shaadi", "emergency": "Emergency",
               "dukaan": "Dukaan", "dukan": "Dukaan", "saaman": "Dukaan", "saman": "Dukaan", "stock": "Dukaan",
               "दिवाली": "Diwali", "शादी": "Shaadi", "इमरजेंसी": "Emergency", "दुकान": "Dukaan", "सामान": "Dukaan"}
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _words(t):
    return re.findall(r"[a-zऀ-ॿ]+", t)


def parse_amount(text):
    """Digits ('2000', '2,000', '2k', '२०००') or words ('do hazar', 'दो हज़ार', 'two thousand').
    Returns int, 'all', or None."""
    t = (text or "").lower().translate(_DEV_DIGITS)
    m = re.search(r"(\d[\d,]*)\s*(k|hazar|hazaar|thousand|हज़ार|हजार)?", t)
    if m and "%" not in t[m.end():m.end() + 2] and not re.match(r"\s*(percent|pratishat|प्रतिशत)", t[m.end():]):
        n = int(m.group(1).replace(",", ""))
        return n * 1000 if m.group(2) else n
    words = _words(t)
    for i, w in enumerate(words):
        if w in _MULT:
            prev = words[i - 1] if i > 0 else ""
            base = _NUM_WORDS.get(prev) or _HALF.get(prev) or 1
            return int(base * _MULT[w])
    if any(w in _ALL for w in words):
        return "all"
    return None


_WITHDRAW = r"nikal|nikaal|withdraw|take out|wapas chahiye|de do|निकाल|निकालो|निकालना"
_CAP = r"limit|cap|pratishat|percent|%|लिमिट|प्रतिशत"
_SAVE_FOR = r"bacha|goal|lakshya|liye|save for|saving for|बचा|लक्ष्य|लिए"
_PAUSE = r"band|rok|ruk|pause|stop|बंद|रोक|रुक"
_RESUME = r"chalu|shuru|resume|start|phir se|चालू|शुरू|फिर से"
_STATUS = r"kitna|kitne|balance|status|jama|haal|how much|कितना|कितने|बैलेंस|जमा"


def parse_command(text):
    """Deterministic command parser (Hinglish, Hindi script, English). Used when the LLM is
    down and to cross-check it. Money commands always need confirmation."""
    t = (text or "").lower().strip().translate(_DEV_DIGITS)
    words = set(_words(t))
    amount = parse_amount(t)
    out = {"intent": "none", "amount": 0, "goal_name": None, "cap": None, "needs_confirm": False, "question": None}

    from_gullak = ("gullak" in t or "गुल्लक" in t) and re.search(r"\bse\b|से|from", t)
    if re.search(_WITHDRAW, t) or (amount and from_gullak):
        out.update(intent="withdraw", amount=amount or 0, needs_confirm=True)
        if not amount:
            out["question"] = "q_how_much"
        return out
    if re.search(_CAP, t):
        m = re.search(r"(\d+(?:\.\d+)?)", t)
        out.update(intent="change_cap", cap=float(m.group(1)) if m else None, needs_confirm=True)
        if out["cap"] is None:
            out["question"] = "q_cap"
        return out
    if words & set(_GOAL_WORDS) and re.search(_SAVE_FOR, t):
        name = next(_GOAL_WORDS[w] for w in _GOAL_WORDS if w in words)
        out.update(intent="set_goal", goal_name=name, amount=amount if isinstance(amount, int) else 0, needs_confirm=True)
        return out
    if re.search(_PAUSE, t):
        out["intent"] = "pause"
        return out
    if re.search(_RESUME, t):
        out["intent"] = "resume"
        return out
    if re.search(_STATUS, t):
        out["intent"] = "status"
        return out
    return out


INTENTS = {"set_goal", "pause", "resume", "withdraw", "change_cap", "status", "none"}


def validate_command(llm_out, text, state, lang="hi"):
    """Merge an LLM reading with the deterministic parse. Code wins on numbers;
    every money action needs confirmation no matter what the text or model says.
    `question` in the result is ready-to-show text in `lang`."""
    base = parse_command(text)
    llm_question = None
    if isinstance(llm_out, dict) and llm_out.get("intent") in INTENTS:
        intent = llm_out["intent"]
        if base["intent"] != "none" and base["intent"] != intent:
            intent = base["intent"]  # deterministic keywords win on disagreement
        base["intent"] = intent
        if intent == "set_goal" and not base.get("goal_name"):
            name = str(llm_out.get("goal_name") or "").strip().title()
            base["goal_name"] = name if name in GOALS else None
        if not base.get("amount") and llm_out.get("amount"):
            try:
                a = int(float(llm_out["amount"]))
                if a in numbers_in((text or "").translate(_DEV_DIGITS)):
                    base["amount"] = a
            except (TypeError, ValueError):
                pass
        if llm_out.get("question") and base["intent"] == "none":
            llm_question = _short(llm_out["question"], 12)
    if base["intent"] == "withdraw":
        if base["amount"] == "all":
            base["amount"] = int(state.get("balance", 0))
        base["needs_confirm"] = True
        base["question"] = None if base["amount"] else "q_how_much"
    if base["intent"] == "change_cap":
        base["needs_confirm"] = True
        if base.get("cap") is not None:
            base["cap"] = clamp_cap(base["cap"])
    if base["intent"] == "set_goal":
        base["needs_confirm"] = True
    if base["intent"] == "none" and not base.get("question"):
        base["question"] = "q_unknown"
    if base.get("question") in ("q_how_much", "q_cap", "q_unknown"):
        base["question"] = llm_question or T(lang, base["question"])
    return base
