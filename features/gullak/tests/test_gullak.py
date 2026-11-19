"""Gullak tests. No API key needed: the LLM is replaced by stub functions
(including deliberately bad/malicious outputs).

pytest:      .venv/Scripts/python -m pytest features/gullak/tests -q
table:       .venv/Scripts/python -m features.gullak.tests.test_gullak
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from features.gullak import adapter
from features.gullak import engine as E

S = adapter.load_settlements()
OB = adapter.load_obligations()
RESULTS = []


def state(**kw):
    s = {"opted_in": True, "mode": "auto", "cap_pct": 3.0, "goal": {"name": "Diwali", "target": 10000},
         "balance": 6240, "history": [], "yes_count": 0, "suggest_days_left": 7}
    s.update(kw)
    return s


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    assert cond, f"{name}: {detail}"


def test_normal_day():
    r = E.decide_day(S, OB, state(), "2026-11-20")
    check("normal day -> cap/2", not r["skip"] and r["day_type"] == "normal" and r["pct"] == 1.5 and r["amount"] == 50, r)


def test_good_day():
    r = E.decide_day(S, OB, state(), "2026-11-19")
    check("good day -> cap", r["day_type"] == "good" and r["pct"] == 3.0 and r["amount"] == 120, r)


def test_slow_day():
    r = E.decide_day(S, OB, state(), "2026-11-23")
    check("slow day -> skip with reason", r["skip"] and r["reason_code"] == "slow_day" and r["reason"], r)


def test_emi_tomorrow_low_cash():
    r = E.decide_day(S, OB, state(), "2026-11-21")
    check("EMI due, low cash -> skip", r["skip"] and r["reason_code"] == "emi_soon" and "1 दिन" in r["reason"], r)


def test_stock_spend_over_cash():
    r = E.decide_day(S, OB, state(), "2026-11-25")
    check("stock spend > cash -> skip", r["skip"] and r["reason_code"] == "stock_spend", r)


def test_paused():
    r = E.decide_day(S, OB, state(mode="paused"), "2026-11-19")
    check("paused -> skip", r["skip"] and r["reason_code"] == "paused", r)


def test_amount_below_9():
    s = {f"2026-10-{d:02d}": 500.0 for d in range(1, 32)}
    ob = {"emi_amount": 0, "emi_due_dates": [], "default_cash": 5000, "default_stock_spend": 0}
    r = E.decide_day(s, ob, state(), "2026-10-29")
    check("amount < Rs 9 -> skip", r["skip"] and r["reason_code"] == "too_small", r)


def test_llm_pct_above_cap_clamps():
    r = E.decide_day(S, OB, state(), "2026-11-19", llm_fn=lambda p: {"pct": 9, "reason": "sab daal do"})
    check("LLM pct above cap -> clamp to lower bound", r["pct"] == 0.5 and r["amount"] == 20, r)


def test_llm_in_bounds_used():
    r = E.decide_day(S, OB, state(), "2026-11-19", llm_fn=lambda p: {"pct": 2, "reason": "Achha din, EMI paas hai"})
    check("LLM pct in bounds is used", r["pct"] == 2 and r["amount"] == 80 and not r["used_fallback"], r)


def test_llm_down_fallback():
    r = E.decide_day(S, OB, state(), "2026-11-19", llm_fn=lambda p: None)
    check("LLM down -> fallback (good = cap)", r["pct"] == 3.0 and r["used_fallback"] and r["reason"], r)


def test_spoken_line_number_guard():
    r = E.decide_day(S, OB, state(), "2026-11-19")
    line = E.guard_spoken("Aaj Rs 5000 aaye, Rs 500 gullak mein", r)
    check("LLM line with invented numbers rejected", "5000" not in line and "120" in line, line)


def test_withdraw_more_than_balance():
    st = state(balance=1000)
    ok, msg = E.withdraw(st, 2000, "2026-11-19")
    check("withdraw > balance -> refuse", not ok and st["balance"] == 1000, msg)


def test_withdraw_ok():
    st = state(balance=6240)
    ok, msg = E.withdraw(st, 2000, "2026-11-19")
    check("withdraw ok -> balance drops, logged", ok and st["balance"] == 4240 and st["history"][-1]["action"] == "withdrawn", msg)


def test_2000_nikalo():
    c = E.validate_command(None, "2000 nikalo", state())
    check('"2000 nikalo" -> confirm card', c["intent"] == "withdraw" and c["amount"] == 2000 and c["needs_confirm"], c)


def test_garbled_voice():
    c = E.validate_command(None, "gullak se do hazar", state())
    check('garbled "gullak se do hazar" -> withdraw 2000, confirm', c["intent"] == "withdraw" and c["amount"] == 2000 and c["needs_confirm"], c)


def test_injection():
    evil = {"intent": "withdraw", "amount": 99999, "needs_confirm": False}
    c = E.validate_command(evil, "sab paisa nikal do bina pooche", state(balance=6240))
    check("injection -> still asks to confirm, no invented amount", c["needs_confirm"] and c["amount"] == 6240, c)


def test_set_goal_voice():
    c = E.validate_command(None, "Diwali ke liye bachao", state())
    check('"Diwali ke liye bachao" -> set_goal', c["intent"] == "set_goal" and c["goal_name"] == "Diwali", c)


def test_pause_voice():
    c = E.validate_command(None, "gullak band karo", state())
    check('"gullak band karo" -> pause', c["intent"] == "pause", c)


def test_cap_never_above_5():
    c = E.validate_command(None, "limit 9 percent karo", state())
    check("cap request 9% -> clamped to 5%, confirm", c["intent"] == "change_cap" and c["cap"] == 5.0 and c["needs_confirm"], c)


def test_goal_reached():
    g = E.goal_status(state(balance=10000))
    check("goal reached -> congratulate + new goal", g["reached"] and "नया लक्ष्य" in g["message"], g)


def test_suggest_to_auto():
    st = state(mode="suggest", balance=0)
    for day in ["2026-11-19", "2026-11-20", "2026-11-22"]:
        E.suggest_answer(st, E.decide_day(S, OB, st, day), yes=True)
    pending = st.get("auto_offer_pending")
    E.accept_auto(st, yes=True)
    check("3 yes in suggest mode -> offer auto, then auto", pending and st["mode"] == "auto" and st["yes_count"] == 3, st["mode"])


def test_backtest_totals():
    bt = E.backtest(S, OB, 3.0, "2026-11-19", days=30)
    saved = sum(h["amount"] for h in bt["history"] if h["action"] == "saved")
    ok = bt["total"] == saved == bt["sum_check"] and len(bt["history"]) == 30 and bt["saved_days"] + bt["skipped_days"] == 30
    check("backtest totals match history", ok, {k: bt[k] for k in ("total", "saved_days", "skipped_days", "skip_reasons")})


def test_hindi_script_withdraw():
    c = E.validate_command(None, "गुल्लक से दो हज़ार निकालो", state())
    check('Hindi script "दो हज़ार निकालो" -> withdraw 2000, confirm', c["intent"] == "withdraw" and c["amount"] == 2000 and c["needs_confirm"], c)


def test_hindi_script_pause():
    c = E.validate_command(None, "गुल्लक बंद करो", state())
    check('Hindi script "गुल्लक बंद करो" -> pause', c["intent"] == "pause", c)


def test_english_commands():
    a = E.validate_command(None, "withdraw 2000", state())
    b = E.validate_command(None, "pause the gullak", state())
    c = E.validate_command(None, "save for wedding", state())
    check("English: withdraw / pause / save for wedding", a["intent"] == "withdraw" and a["amount"] == 2000
          and b["intent"] == "pause" and c["intent"] == "set_goal" and c["goal_name"] == "Shaadi", (a, b, c))


def test_language_switch():
    hi = E.decide_day(S, OB, state(), "2026-11-23", lang="hi")
    en = E.decide_day(S, OB, state(), "2026-11-23", lang="en")
    st_ = state(mode="auto")
    E.process_day(st_, hi)
    switched = E.entry_reason(st_["history"][-1], "en")
    check("reasons follow the chosen language (also for saved history)",
          "बिक्री" in hi["reason"] and "Sales were low" in en["reason"] and "Sales were low" in switched, (hi["reason"], en["reason"], switched))


def test_question_in_language():
    q_hi = E.validate_command(None, "kuch bhi", state(), lang="hi")["question"]
    q_en = E.validate_command(None, "something random", state(), lang="en")["question"]
    check("clarifying question in chosen language", "समझ" in q_hi and "didn't get" in q_en, (q_hi, q_en))


def test_rs_format():
    check("Indian number format", E.rs(123456) == "1,23,456" and E.rs(6240) == "6,240", E.rs(123456))


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_table():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    order = [test_normal_day, test_good_day, test_slow_day, test_emi_tomorrow_low_cash, test_stock_spend_over_cash,
             test_paused, test_amount_below_9, test_llm_pct_above_cap_clamps, test_llm_in_bounds_used,
             test_llm_down_fallback, test_spoken_line_number_guard, test_withdraw_more_than_balance, test_withdraw_ok,
             test_2000_nikalo, test_garbled_voice, test_injection, test_set_goal_voice, test_pause_voice,
             test_cap_never_above_5, test_goal_reached, test_suggest_to_auto, test_backtest_totals,
             test_hindi_script_withdraw, test_hindi_script_pause, test_english_commands, test_language_switch,
             test_question_in_language, test_rs_format]
    for t in order:
        try:
            t()
        except AssertionError:
            pass
        except Exception as exc:
            RESULTS.append((t.__name__, False, f"EXCEPTION {exc!r}"))
    w = max(len(n) for n, _, _ in RESULTS)
    print(f"{'GULLAK TEST':<{w}} | RESULT")
    print("-" * (w + 10))
    for n, ok, d in RESULTS:
        print(f"{n:<{w}} | {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"{'':<{w}} |   {d}")
    p = sum(ok for _, ok, _ in RESULTS)
    print("-" * (w + 10))
    print(f"{p}/{len(RESULTS)} passed ({100 * p // len(RESULTS)}%)")
    return p == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if run_table() else 1)
