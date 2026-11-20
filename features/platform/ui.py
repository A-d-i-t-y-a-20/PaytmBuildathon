"""Platform Console UI (Streamlit). What a platform's (Paytm's) merchant ops team
sees: pilot vs holdout, a churn radar, safe-credit-timing flags, a value-proof line
per merchant, an outcome-fee calculator, and an "ask your merchants" box.

Every merchant here is mock data (features/platform/generate_data.py); every figure
is labelled "mock pilot". Reuses features/common/ui_kit.py for all styling -- no new
design system -- and features/gullak + features/wapas_aao engines for all maths.
"""
import streamlit as st

from features.common import ui_kit as K
from features.gullak.engine import rs
from features.platform import engine as PE
from features.platform import generate_data as GD

NAV_KEY = "platform"

SCREENS = [
    ("overview", "Pilot overview"),
    ("churn", "Churn radar"),
    ("credit", "Safe credit timing"),
    ("value", "Value proof"),
    ("fee", "Outcome fee calculator"),
    ("ask", "Ask your merchants"),
]


def _ensure_data():
    if "pf_rows" not in st.session_state:
        merchants = GD.generate_merchants()
        pilot, holdout = GD.pilot_holdout_split(merchants)
        st.session_state.pf_pilot_rows = [PE.merchant_row(m) for m in pilot]
        st.session_state.pf_holdout_rows = [PE.merchant_row(m) for m in holdout]
    return st.session_state.pf_pilot_rows, st.session_state.pf_holdout_rows


def _kpi_tile(label, value, sub=""):
    K.card(f'<div class="kx-kicker">{label}</div><div class="kx-mid">{value}</div>'
           + (f'<div class="kx-muted">{sub}</div>' if sub else ""))


def _open_merchant_app_view(m):
    st.session_state.platform_merchant = m
    for k in ("gk_state", "gk_rec_cache", "gk_view", "gk_onb", "gk_flash", "gk_reply",
              "gk_settlements", "gk_obligations", "gk_data_merchant_id"):
        st.session_state.pop(k, None)
    st.session_state.console_view = "merchant"
    st.session_state.nav = "aaj"
    st.toast(f"Opening {m['name']}'s app view (concept)")
    st.rerun()


# ---------------------------------------------------------------- screens
def _overview(pilot_rows, holdout_rows):
    s = PE.pilot_summary(pilot_rows, holdout_rows)
    K.card('<div class="kx-kicker">Mock pilot · 250 merchants vs 250 holdout</div>'
           '<div class="kx-line">Every number on this screen is from the mock population, '
           'generated the same way as the rest of this demo\'s data.</div>', "blue")
    rows = [
        ("Weekly active merchants", "weekly_active_pct", "pct"),
        ("Gullak opt-in rate", "gullak_optin_pct", "pct"),
        ("Avg gullak balance", "avg_gullak_balance", "rs"),
        ("Avg buffer days", "avg_buffer_days", "days"),
        ("Win-back profit / merchant", "avg_winback_profit", "rs"),
        ("Soundbox churn rate (score >= 70)", "churn_rate_pct", "pct"),
    ]

    def fmt(v, unit):
        if unit == "rs":
            return f"₹{rs(v)}"
        if unit == "pct":
            return f"{v}%"
        return f"{v} days"

    def fmt_diff(v, unit):
        sign = "+" if v >= 0 else ""
        return f"{sign}{fmt(v, unit)}"

    table = [{"Metric": label, "Pilot (mock)": fmt(s["pilot"][key], unit), "Holdout (mock)": fmt(s["holdout"][key], unit),
              "Difference vs holdout": fmt_diff(s["diff"][key], unit)} for label, key, unit in rows]
    st.dataframe(table, hide_index=True, width="stretch")


def _churn(pilot_rows):
    K.card('<div class="kx-kicker">Churn radar · mock pilot</div>'
           '<div class="kx-line">Code rules flag risk: falling UPI days, falling sales, no approvals in 14 days. '
           'Gemini only writes the one-line reason and suggested action; the score and amount are code.</div>', "amber")
    radar = PE.churn_radar(pilot_rows, top_n=25)
    if not radar:
        st.caption("No merchants currently flagged at risk in this mock pilot.")
        return
    from features.common import llm
    selected = st.session_state.setdefault("pf_churn_selected", set())
    for r in radar[:15]:
        m, c = r["merchant"], r["churn"]
        reason = None
        if llm.available():
            out = llm.call_json(
                "You write ONE short line (<=16 words) explaining why a shop may stop using a payments "
                "subscription, in Hinglish, from the given risk flags and score. Reply as JSON {\"reason\": \"...\"}. "
                "Never invent numbers not given to you.",
                {"flags": c["flags"], "score": c["score"], "suggested_save_pct": c["suggested_save_pct"]}, max_tokens=60)
            if isinstance(out, dict) and out.get("reason"):
                reason = out["reason"]
        reason = reason or ("Risk: " + ", ".join(c["flags"]).replace("_", " ") if c["flags"] else "Elevated risk")
        c1, c2 = st.columns([5, 1])
        with c1:
            K.card(f'<div class="kx-line"><b>{m["name"]}</b> · {m["town"]} · risk {c["score"]}/100</div>'
                   f'<div class="kx-muted">{reason}</div>'
                   f'<div class="kx-muted">Suggested save: {c["suggested_save_pct"]:g}% (₹{rs(c["suggested_save_amount"])})</div>')
        with c2:
            checked = c2.checkbox("Select", key=f"pf_cr_{m['id']}", value=m["id"] in selected, label_visibility="collapsed")
            if checked:
                selected.add(m["id"])
            else:
                selected.discard(m["id"])
    if st.button(f"Approve bulk save action for {len(selected)} selected (mock)", width="stretch", disabled=not selected):
        st.success(f"Mock: queued a save-amount nudge for {len(selected)} merchants. No real action taken.")


def _credit(pilot_rows):
    K.card('<div class="kx-kicker">Safe credit timing · Concept, lending partner decides</div>'
           '<div class="kx-line">Code computes the daily instalment of a mock existing offer as a % of the '
           'merchant\'s slow-day sales. No rates, eligibility or approval claims are made here.</div>', "blue")
    cash_short = [r for r in pilot_rows if r["gullak"]["opted_in"] and r["gullak"]["buffer_days"] < 2]
    if not cash_short:
        st.caption("No merchants currently show a cash-short signal in this mock pilot.")
        return
    table = []
    for r in cash_short[:40]:
        m = r["merchant"]
        ins = PE.instalment_safety(m)
        table.append({
            "Merchant": m["name"], "Town": m["town"], "Buffer days": r["gullak"]["buffer_days"],
            "Offer (mock)": f"₹{rs(ins['offer_amount'])}", "Daily instalment": f"₹{rs(ins['daily_instalment'])}",
            "% of slow-day sales": f"{ins['pct_of_slow_day']}%",
            "Tag": "Safe" if ins["safe"] else f"Too heavy -> suggest ₹{rs(ins['suggested_amount'])}",
        })
    st.dataframe(table, hide_index=True, width="stretch")


def _value(pilot_rows):
    K.card('<div class="kx-kicker">Value proof · mock pilot</div>'
           '<div class="kx-line">Per merchant: "Galla helped you gain about this much this month (estimated)".</div>', "green")
    total = sum(r["value"] for r in pilot_rows if r["value"] > 0)
    _kpi_tile("Platform total (merchants with positive gain, mock)", f"₹{rs(total)}")
    top = sorted(pilot_rows, key=lambda r: r["value"], reverse=True)[:10]
    names = {r["merchant"]["name"]: r for r in top}
    pick = st.selectbox("Merchant", list(names), key="pf_value_pick", label_visibility="collapsed")
    if pick:
        r = names[pick]
        line = f"Galla ne is mahine aapko karib Rs {int(r['value'])} ka fayda dilaya (estimate)."
        st.markdown(f'<div class="kx-say">{line}</div>', unsafe_allow_html=True)
        if st.button("Play value line (Sarvam TTS)", key="pf_value_play"):
            if not K.speak(line, key="pf_value_tts", autoplay=True):
                st.caption("Voice abhi band hai, code se jawab de rahe hain (no Sarvam key / call failed).")
    table = [{"Merchant": r["merchant"]["name"], "Town": r["merchant"]["town"],
              "Estimated gain this month": f"₹{rs(r['value'])}"} for r in top]
    st.dataframe(table, hide_index=True, width="stretch")


def _fee(pilot_rows):
    K.card('<div class="kx-kicker">Outcome fee calculator</div>'
           '<div class="kx-line">Platform extra revenue vs holdout x fee %, counted only for merchants '
           'whose own net gain is positive -- this is how Galla AI gets paid.</div>', "blue")
    fee_pct = st.slider("Fee %", min_value=1.0, max_value=25.0, value=PE.DEFAULT_FEE_PCT, step=0.5, key="pf_fee_pct")
    fee = PE.outcome_fee(pilot_rows, fee_pct)
    c1, c2, c3 = st.columns(3)
    with c1:
        _kpi_tile("Merchants paying (positive gain)", f"{fee['eligible_merchants']} / {fee['total_merchants']}")
    with c2:
        _kpi_tile("Total merchant gain counted", f"₹{rs(fee['total_positive_value'])}")
    with c3:
        _kpi_tile(f"Platform revenue at {fee_pct:g}%", f"₹{rs(fee['platform_revenue'])}")


_EXAMPLE_QUESTIONS = ["How many pilot merchants are at risk of churn?", "What's the average gullak balance?",
                      "How many merchants gained money this month?"]


def _ask(pilot_rows, holdout_rows):
    K.card('<div class="kx-kicker">Ask your merchants</div>'
           '<div class="kx-line">Code filters the mock data; Gemini answers in up to 3 lines using only the '
           'filtered numbers (checked -- no invented figures reach the screen).</div>', "blue")
    pick = st.pills("examples", _EXAMPLE_QUESTIONS, key="pf_ask_examples", label_visibility="collapsed")
    q = st.text_input("Question", value=pick or "", key=f"pf_ask_q_{pick}", label_visibility="collapsed",
                      placeholder="e.g. How many pilot merchants are at risk of churn?")
    if st.button("Ask", type="primary", width="stretch", key="pf_ask_go") and q.strip():
        s = PE.pilot_summary(pilot_rows, holdout_rows)
        at_risk = len(PE.churn_radar(pilot_rows, top_n=10_000))
        gained = sum(1 for r in pilot_rows if r["value"] > 0)
        facts = {"pilot_merchants": s["pilot"]["n"], "holdout_merchants": s["holdout"]["n"],
                 "weekly_active_pct_pilot": s["pilot"]["weekly_active_pct"], "gullak_optin_pct": s["pilot"]["gullak_optin_pct"],
                 "avg_gullak_balance": s["pilot"]["avg_gullak_balance"], "avg_buffer_days": s["pilot"]["avg_buffer_days"],
                 "avg_winback_profit": s["pilot"]["avg_winback_profit"], "merchants_at_risk": at_risk,
                 "merchants_gained_money": gained}
        from features.common import llm
        answer = None
        if llm.available():
            out = llm.call_json(
                "Answer the ops question in at most 3 short lines, using ONLY the numbers given in `facts` "
                "(never invent a number). Reply as JSON {\"answer\": \"...\"}.",
                {"question": q, "facts": facts}, max_tokens=150)
            if isinstance(out, dict) and out.get("answer") and PE.numbers_ok(out["answer"], facts):
                answer = out["answer"]
        if not answer:
            answer = (f"Mock pilot: {facts['pilot_merchants']} merchants, {facts['merchants_at_risk']} flagged at "
                      f"churn risk, {facts['merchants_gained_money']} gained money this month. Avg gullak balance "
                      f"₹{rs(facts['avg_gullak_balance'])}, {facts['gullak_optin_pct']}% opted in.")
        st.session_state.pf_ask_answer = answer
    if st.session_state.get("pf_ask_answer"):
        st.markdown(f'<div class="kx-say">{st.session_state.pf_ask_answer}</div>', unsafe_allow_html=True)


def _merchant_directory(pilot_rows, holdout_rows):
    with st.expander("Open any merchant's app view"):
        all_rows = pilot_rows + holdout_rows
        names = {f"{r['merchant']['name']} ({r['merchant']['town']}, {r['merchant']['group']})": r["merchant"]
                 for r in all_rows}
        pick = st.selectbox("Merchant", list(names), key="pf_dir_pick")
        if st.button("Open app view", key="pf_dir_open", width="stretch"):
            _open_merchant_app_view(names[pick])


# ---------------------------------------------------------------- page
def render_page():
    K.inject_css()
    pilot_rows, holdout_rows = _ensure_data()
    with st.container(key="kx_console"):
        K.header("Platform Console", "Concept -- what Paytm's merchant ops team would see. Mock pilot data.")
        screen = st.radio("screen", [s[1] for s in SCREENS], key="pf_screen", horizontal=True, label_visibility="collapsed")
        key = {label: k for k, label in SCREENS}[screen]
        if key == "overview":
            _overview(pilot_rows, holdout_rows)
        elif key == "churn":
            _churn(pilot_rows)
        elif key == "credit":
            _credit(pilot_rows)
        elif key == "value":
            _value(pilot_rows)
        elif key == "fee":
            _fee(pilot_rows)
        else:
            _ask(pilot_rows, holdout_rows)
        _merchant_directory(pilot_rows, holdout_rows)
        K.foot("Concept · mock pilot data · no real merchants, payments or messages")
