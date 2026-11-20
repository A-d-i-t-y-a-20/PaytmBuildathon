"""Wapas Aao UI (Streamlit). Concept demo with mock data.

Merchant journey: ask -> one finding -> priced offer -> approve -> live -> result (profit after cost).
The merchant never sees customer names, numbers or ids -- only counts and rupees.
All text comes from features/common/i18n.py (Hindi / English).
"""
import streamlit as st

from features.common import ui_kit as K
from features.common.i18n import MONTHS
from features.gullak.engine import rs
from features.wapas_aao import ai
from features.wapas_aao import engine as E

NAV_KEY = "wapas_aao"
t = K.t


def _lang():
    return K.lang()


def _data():
    if "wa_payments" not in st.session_state:
        st.session_state.wa_payments = E.load_payments()
        st.session_state.wa_consent = E.load_consent()
        st.session_state.wa_outcome = E.load_outcome()
    return st.session_state.wa_payments, st.session_state.wa_consent, st.session_state.wa_outcome


def _proposal():
    P, C, _ = _data()
    custom = st.session_state.get("wa_custom")
    oid = st.session_state.get("wa_offer_id", E.DEFAULT_OFFER)
    window = st.session_state.get("wa_window", "quiet")
    days = st.session_state.get("wa_days", E.CAMPAIGN_DAYS)
    budget = st.session_state.get("wa_budget", E.DEFAULT_BUDGET)
    key = (repr(sorted(custom.items())) if custom else oid, window, days, budget)
    if st.session_state.get("wa_prop_key") != key:
        st.session_state.wa_prop = E.build_proposal(P, C, offer_id=oid, offer=custom, window=window, days=days, budget=budget)
        st.session_state.wa_prop_key = key
    return st.session_state.wa_prop


def _stage(s):
    st.session_state.wa_stage = s
    st.rerun()


def _window(q):
    if q.get("key") == "allday":
        return t("window_allday")

    def h(x):
        return x - 12 if x > 12 else x
    return t("window", a=h(q["start"]), b=h(q["end"]))


def _offer_text(o):
    key = {"flat": "offer_flat", "percent": "offer_percent", "free_item": "offer_free", "stamp": "offer_stamp"}[o["kind"]]
    return t(key, v=o["value"], min=rs(o["min_bill"]))


def _end_label(iso):
    return f"{int(iso[8:])} {MONTHS[_lang()][int(iso[5:7]) - 1]}"


# ---------------------------------------------------------------- stages
def _ask():
    K.card(f'<div class="kx-mid">{t("ask_title")}</div><div class="kx-muted">{t("ask_sub")}</div>', "blue")
    heard = K.listen(t("mic_label"), key="wa_mic")
    examples = [t("ex1"), t("ex2")]
    pick = st.pills("examples", examples, key=f"wa_example_{_lang()}", label_visibility="collapsed")
    text = st.text_input("text", value=heard or pick or "", key=f"wa_text_{heard}_{pick}", label_visibility="collapsed",
                         placeholder=t("ph_text"))
    if st.button(t("btn_ask"), type="primary", width="stretch", key="wa_ask_go", disabled=not text.strip()):
        llm_out = ai.understand(text, _lang()) if ai.available() else None
        v = E.validate_ask(llm_out, text)
        if v.get("offer_id"):
            st.session_state.wa_offer_id = v["offer_id"]
            st.session_state.wa_llm_pick = v["offer_id"]
        st.session_state.wa_note = None
        if v["intent"] == "win_back":
            st.session_state.wa_said = text
            _stage("finding")
        elif v["intent"] == "refuse_contact":
            st.session_state.wa_note = "note_refuse"
        elif v["intent"] == "result" and st.session_state.get("wa_running"):
            _stage("result")
        else:
            st.session_state.wa_note = "note_q"
        st.rerun()
    if st.session_state.get("wa_note"):
        K.ai_say(t(st.session_state.wa_note))


def _finding():
    pr = _proposal()
    q = pr["quiet"]
    line1 = t("find1", w=_window(q), pct=q["drop_pct"])
    line2 = t("find2", n=pr["lapsed"])
    if ai.available():
        cache = st.session_state.setdefault("wa_finding_cache", {})
        if _lang() not in cache:
            facts = {"drop_pct": q["drop_pct"], "window": _window(q), "lapsed": pr["lapsed"]}
            out = ai.phrase({**facts, "offer": _offer_text(pr["offer"])}, _lang())
            cache[_lang()] = out["finding_line"] if out and out.get("finding_line") and ai.numbers_ok(out["finding_line"], facts) else None
        if cache[_lang()]:
            line1, line2 = cache[_lang()], ""
    if st.session_state.get("wa_said"):
        st.markdown(f'<div class="kx-say" style="border-radius:16px 16px 4px 16px;background:{K.SHOUT};color:#fff;margin-left:auto;'
                    f'max-width:85%">🎤 {st.session_state.wa_said}</div>', unsafe_allow_html=True)
    K.card(f'<div class="kx-mid">{line1}</div>' + (f'<div class="kx-line">{line2}</div>' if line2 else "")
           + f'<div class="kx-line" style="margin-top:12px"><b>{t("find_q")}</b></div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_suggest"), type="primary", width="stretch", key="wa_find_yes"):
        _stage("proposal")
    if c2.button(t("btn_not_now"), width="stretch", key="wa_find_no"):
        _stage("ask")


def _split_bar(r):
    tot = r["rewards"] + r["paytm"] + r["unreachable"] or 1
    w = lambda n: 100 * n / tot  # noqa: E731
    return (f'<div class="kx-split"><i style="width:{w(r["rewards"])}%;background:{K.GREEN}"></i>'
            f'<i style="width:{w(r["paytm"])}%;background:{K.BLUE}"></i>'
            f'<i style="width:{w(r["unreachable"])}%;background:#D0D5DD"></i></div>'
            f'<div class="kx-legend"><span style="background:{K.GREEN}"></span>{t("leg_rewards", n=r["rewards"])}<br>'
            f'<span style="background:{K.BLUE}"></span>{t("leg_paytm", n=r["paytm"])}<br>'
            f'<span style="background:#D0D5DD"></span>{t("leg_none", n=r["unreachable"])}</div>')


def _pct(x):
    return format(x, "g")


def _ai_picks(current):
    recs = E.rank_with_llm(E.recommend_offers(), st.session_state.get("wa_llm_pick"))
    for n, r in enumerate(recs):
        o = r["offer"]
        top = f'<span class="kx-chip blue" style="margin:0 0 6px">{t("ai_top")}</span><br>' if n == 0 else ""
        K.card(f'{top}<div class="kx-line" style="margin-top:0"><b>{_offer_text(o)}</b></div>'
               f'<div class="kx-muted">{t("ai_why_" + r["why"])} · {t("ai_cost", pct=_pct(r["cost_pct"]))}</div>')
        chosen = current.get("id") == o["id"] and not st.session_state.get("wa_custom")
        if st.button(t("in_use") if chosen else t("btn_use"), key=f"wa_use_{o['id']}", width="stretch", disabled=chosen):
            st.session_state.wa_offer_id = o["id"]
            st.session_state.wa_custom = None
            st.rerun()


CUSTOM_KINDS = ["flat", "percent", "free_item", "stamp"]


def _custom_builder(pr):
    kind = st.pills(t("cu_type"), CUSTOM_KINDS, default="flat", key=f"wa_cu_kind_{_lang()}",
                    format_func=lambda k: t({"flat": "cu_flat", "percent": "cu_percent", "free_item": "cu_free",
                                             "stamp": "cu_stamp"}[k])) or "flat"
    labels = {"flat": "cu_value_rs", "percent": "cu_value_pct", "free_item": "cu_value_item", "stamp": "cu_value_stamp"}
    defaults = {"flat": (20, 400), "percent": (5, 300), "free_item": (8, 250), "stamp": (30, 200)}
    c1, c2 = st.columns(2)
    value = c1.number_input(t(labels[kind]), min_value=1, max_value=100 if kind == "percent" else 2000,
                            value=defaults[kind][0], step=1 if kind == "percent" else 5, key=f"wa_cu_val_{kind}")
    min_bill = c2.number_input(t("cu_min"), min_value=50, max_value=20000, value=st.session_state.get(f"wa_cu_min_{kind}_v", defaults[kind][1]),
                               step=50, key=f"wa_cu_min_{kind}")
    windows = {"quiet": t("cu_quiet"), "evening": t("cu_evening"), "allday": t("cu_allday")}
    window = st.pills(t("cu_when"), list(windows), default=st.session_state.get("wa_window", "quiet"),
                      format_func=lambda k: windows[k], key=f"wa_cu_win_{_lang()}") or "quiet"
    days = st.pills(t("cu_days"), [7, 14, 30], default=st.session_state.get("wa_days", 14), key="wa_cu_days") or 14
    budgets = {300: "₹300", 600: "₹600", 1000: "₹1,000"}
    budget = st.pills(t("cu_budget"), list(budgets), default=st.session_state.get("wa_budget", 600),
                      format_func=lambda b: budgets[b], key="wa_cu_budget") or 600
    offer = E.make_custom_offer(kind, value, min_bill)
    chk = E.cost_check(offer)
    if chk["ok"]:
        st.markdown(f'<span class="kx-chip green">{t("cu_ok", pct=_pct(chk["cost_pct"]))}</span>', unsafe_allow_html=True)
    else:
        K.card(f'<div class="kx-line">{t("cu_bad", pct=_pct(chk["cost_pct"]), m=chk["margin_pct"])}</div>', "amber")
        fixed = E.reprice(offer)
        fix_label = (t("cu_fix", min=rs(fixed["min_bill"])) if kind != "percent"
                     else t("offer_percent", v=fixed["value"], min=rs(fixed["min_bill"])))
        if st.button(fix_label, key=f"wa_cu_fix_{kind}", width="stretch"):
            if kind == "percent":
                st.session_state[f"wa_cu_val_{kind}"] = fixed["value"]
            else:
                st.session_state[f"wa_cu_min_{kind}_v"] = fixed["min_bill"]
                st.session_state.pop(f"wa_cu_min_{kind}", None)
            st.rerun()
    if st.button(t("btn_use_custom"), type="secondary", width="stretch", key="wa_cu_use", disabled=not chk["ok"]):
        st.session_state.wa_custom = offer
        st.session_state.wa_window, st.session_state.wa_days, st.session_state.wa_budget = window, days, budget
        st.rerun()


def _proposal_view():
    pr = _proposal()
    o, r, c, q = pr["offer"], pr["reach"], pr["cost"], pr["quiet"]
    K.card(f'<div class="kx-kicker">{t("prop_kicker")}</div><div class="kx-mid">{_offer_text(o)}</div>'
           f'<div class="kx-line">{t("prop_when", w=_window(pr["window"]), d=pr["days"], end=_end_label(pr["end_date"]))}</div>', "blue")
    K.card(f'<div class="kx-kicker">{t("reach_kicker")}</div>'
           f'<div class="kx-mid">{t("reach_big", r=r["reachable"], total=pr["lapsed"])}</div>{_split_bar(r)}')
    K.card(f'<div class="kx-row"><span>{t("cost_share")}</span><b>{c["cost_pct"]:g}%</b></div>'
           f'<div class="kx-row"><span>{t("cost_margin")}</span><b>~{c["margin_pct"]}%</b></div>'
           f'<div class="kx-row"><span>{t("cost_max")}</span><b>₹{rs(pr["budget"])}</b></div>'
           f'<span class="kx-chip green">{t("cost_ok") if not o.get("repriced_from") else t("cost_repriced")}</span>')
    tab_ai, tab_custom = st.tabs([t("pick_tab_ai"), t("pick_tab_custom")])
    with tab_ai:
        _ai_picks(o)
    with tab_custom:
        _custom_builder(pr)
    st.markdown(f'<div class="kx-muted">{t("privacy_line")}<br>{t("holdout_line", n=pr["holdout_n"])}</div>',
                unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_run"), type="primary", width="stretch", key="wa_run"):
        st.session_state.wa_running = True
        _stage("running")
    if c2.button(t("btn_back"), width="stretch", key="wa_prop_back"):
        _stage("finding")
    st.caption(t("billing"))


def _customer_view(pr):
    """What the customer sees -- collapsed by default; it explains reach to the shopkeeper/judges."""
    o = pr["offer"]
    with st.expander(t("cv_title")):
        t1, t2 = st.tabs([t("cv_tab1"), t("cv_tab2")])
        with t1:
            if o["kind"] == "flat":
                res = E.apply_offer(420, o, consented=True)
                body = (f'<div style="font-size:14px;color:#5B6472">{K.shop_name()} ✓</div>'
                        f'<div style="font-size:30px;font-weight:800;margin:8px 0"><span class="kx-strike">₹{res["bill"]}</span>₹{res["pay"]}</div>'
                        f'<div class="kx-chip green" style="margin:0">{t("cv_applied", d=res["discount"])}</div>'
                        f'<div style="font-size:13px;color:#5B6472;margin-top:8px">{t("cv_note1")}</div>')
            else:
                body = f'<div style="font-size:16px">{_offer_text(o)}</div><div style="font-size:13px;color:#5B6472">{t("cv_counter")}</div>'
            st.markdown(f'<div class="kx-phone"><div class="bar">{t("cv_bar1")}</div>{body}</div>', unsafe_allow_html=True)
            st.caption(t("cv_cap1"))
        with t2:
            st.markdown(f'<div class="kx-phone"><div class="bar other">{t("cv_bar2")}</div>'
                        f'<div style="font-size:24px;font-weight:800">{t("cv_paid")}</div>'
                        f'<div class="kx-chip grey" style="margin:6px 0 0">{t("cv_nochange")}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kx-say">{t("soundbox")} {t("cv_sb2", n=E.stamp_progress(4)["stamps"])}</div>',
                        unsafe_allow_html=True)
            st.caption(t("cv_cap2"))


def _soundbox_text(res):
    if res.get("applied"):
        return t("sb_offer", p=int(res["pay"]), d=int(res["discount"]), b=int(res["bill"]))
    return t("sb_plain", p=int(res["pay"]))


def _running():
    pr = _proposal()
    _, _, out = _data()
    K.card(f'<div class="kx-kicker">{t("run_kicker", offer=_offer_text(pr["offer"]))}</div>'
           f'<div class="kx-mid">{t("run_title", n=out["day1_redemptions"])}</div>'
           f'<div class="kx-row"><span>{t("spent")}</span><b>₹{out["day1_redemptions"] * pr["offer"]["value"]} / ₹{rs(pr["budget"])}</b></div>'
           f'<div class="kx-row"><span>{t("new_members")}</span><b>{out["new_rewards_members_day1"]}</b></div>', "green")
    line = _soundbox_text(E.apply_offer(420, pr["offer"], consented=True))
    st.markdown(f'<div class="kx-say">{t("soundbox")} "{line}"</div>', unsafe_allow_html=True)
    K.speak(line, key="wa_sb")
    st.write("")
    if st.button(t("btn_result"), type="primary", width="stretch", key="wa_to_result"):
        _stage("result")
    if st.button(t("btn_stop"), width="stretch", key="wa_stop"):
        st.session_state.wa_running = False
        _stage("ask")
    _customer_view(pr)


def _result():
    pr = _proposal()
    _, _, out = _data()
    r = E.compute_result(out, pr)
    tone = "green" if r["net"] > 0 else "amber"
    K.card(f'<div class="kx-kicker">{t("res_kicker", d=pr["days"])}</div>'
           f'<div class="kx-big">{"+" if r["net"] >= 0 else "−"}₹{rs(abs(r["net"]))}</div>'
           f'<div class="kx-line">{t("res_line")}</div><div class="kx-muted">{t("res_muted")}</div>', tone)
    K.card(f'<div class="kx-row"><span>{t("res_back")}</span><b>{r["returned"]}</b></div>'
           f'<div class="kx-row"><span>{t("res_sales")}</span><b>₹{rs(r["extra_sales"])}</b></div>'
           f'<div class="kx-row"><span>{t("res_profit", m=r["margin_pct"])}</span><b>₹{rs(r["extra_profit"])}</b></div>'
           f'<div class="kx-row"><span>{t("res_cost", n=r["redemptions"], v=pr["offer"]["value"])}</span><b>−₹{rs(r["offer_cost"])}</b></div>')
    K.card(f'<div class="kx-kicker">{t("res_next")}</div><div class="kx-line">{t("res_tip")}</div>', "blue")
    st.caption(t("res_small"))
    if st.button(t("btn_again"), type="primary", width="stretch", key="wa_again"):
        _stage("proposal")
    if st.button(t("btn_new_q"), width="stretch", key="wa_new"):
        for k in ("wa_finding_cache", "wa_said", "wa_note", "wa_running"):
            st.session_state.pop(k, None)
        _stage("ask")


def _trust_panel():
    with st.expander(t("trust_title")):
        st.markdown(t("trust_body"))


# ---------------------------------------------------------------- page
def render_page():
    K.inject_css()
    _data()
    with st.container(key="kx_page_wapas"):
        if st.button("← " + t("tab_aaj"), key="wa_back_aaj"):
            st.session_state.nav = "aaj"
            st.rerun()
        K.header(t("wa_title"), t("wa_sub"), icon="return")
        stage = st.session_state.get("wa_stage", "ask")
        {"ask": _ask, "finding": _finding, "proposal": _proposal_view, "running": _running, "result": _result}[stage]()
        _trust_panel()
        if stage != "ask" and st.button(t("btn_restart"), key="wa_restart"):
            for k in ("wa_stage", "wa_finding_cache", "wa_said", "wa_note", "wa_running", "wa_offer_id", "wa_custom",
                      "wa_window", "wa_days", "wa_budget", "wa_llm_pick"):
                st.session_state.pop(k, None)
            st.rerun()
        K.foot(t("foot_wapas"))


def render_home_card():
    K.inject_css()
    _data()
    pr = _proposal()
    with st.container(key="kx_card_wapas"):
        kicker = f'<div class="kx-sticker-row">{K.sticker("return")}<div class="kx-kicker" style="margin:0">{t("hc_wa_kicker")}</div></div>'
        if st.session_state.get("wa_running"):
            K.card(f'{kicker}<div class="kx-mid">{t("hc_wa_running")}</div>'
                   f'<div class="kx-line">{_offer_text(pr["offer"])}</div>', "green")
            label = t("btn_see_result")
        else:
            K.card(f'{kicker}<div class="kx-mid">{t("hc_wa_title", n=pr["lapsed"])}</div>'
                   f'<div class="kx-muted">{t("hc_wa_sub", w=_window(pr["quiet"]))}</div>', "blue")
            label = t("btn_invite_back")
        if st.button(label, key="wa_home_open", width="stretch"):
            st.session_state.nav = NAV_KEY
            st.session_state.wa_stage = "result" if st.session_state.get("wa_running") else "finding"
            st.rerun()
