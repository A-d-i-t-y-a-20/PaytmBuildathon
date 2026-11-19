"""Galla Gullak UI (Streamlit). Concept demo with mock data -- no real money moves.

Entry points used by app.py:
  render_page()       -> the "Gullak" tab
  render_home_card()  -> card on the "Aaj" home screen
All text comes from features/common/i18n.py (Hindi / English).
"""
import copy
from datetime import date, timedelta

import streamlit as st

from features.common import ui_kit as K
from features.common.i18n import DAY_SHORT, GOAL_LABELS, goal_label
from features.gullak import adapter, ai
from features.gullak import engine as E

NAV_KEY = "gullak"
t = K.t


# ---------------------------------------------------------------- state
def _lang():
    return K.lang()


def _data():
    if "gk_settlements" not in st.session_state:
        st.session_state.gk_settlements = adapter.load_settlements()
        st.session_state.gk_obligations = adapter.load_obligations()
    return st.session_state.gk_settlements, st.session_state.gk_obligations


def get_state():
    if "gk_state" not in st.session_state:
        st.session_state.gk_state = copy.deepcopy(adapter.load_seed_state())
        st.session_state.gk_view = "main"
    return st.session_state.gk_state


def _go(view):
    st.session_state.gk_view = view
    st.rerun()


def _today(state):
    return state.get("today", "2026-11-19")


def _rec(state, day):
    """Decision for a day, computed once per (day, cap, mode, language) so reruns don't re-call the LLM."""
    S, OB = _data()
    cache = st.session_state.setdefault("gk_rec_cache", {})
    key = (day, state.get("cap_pct"), state.get("mode"), _lang())
    if key not in cache:
        llm_fn = ai.smart_amount if ai.available() else None
        cache[key] = E.decide_day(S, OB, state, day, llm_fn=llm_fn, lang=_lang())
    return cache[key]


def _entry(state, day):
    for h in reversed(state.get("history", [])):
        if h["date"] == day and h["action"] in ("saved", "skipped", "declined"):
            return h
    return None


def _why(entry):
    return E.entry_reason(entry, _lang())


def _settle_today(state):
    """Auto/paused mode and skip days are recorded without asking."""
    day = _today(state)
    if not state.get("opted_in") or _entry(state, day):
        return
    rec = _rec(state, day)
    if rec["skip"] or state.get("mode") == "auto":
        E.process_day(state, rec)
        if not rec["skip"]:
            st.session_state.gk_speak = rec["spoken_line"]


def _avg(state):
    S, _ = _data()
    return E.avg_daily(S, _today(state))


def _day_name(day):
    return DAY_SHORT[_lang()][date.fromisoformat(day).weekday()]


def _goal_name(state):
    return goal_label(_lang(), (state.get("goal") or {}).get("name", "Bas bachat"))


def _goal_options():
    return {GOAL_LABELS[g][_lang()]: g for g in E.GOALS}


# ---------------------------------------------------------------- shared public helpers
def summary_line(day=None):
    state = st.session_state.get("gk_state") or adapter.load_seed_state()
    return E.summary_line(state, day or state.get("today", date.today().isoformat()), lang=_lang())


def balance():
    state = st.session_state.get("gk_state") or adapter.load_seed_state()
    return int(state.get("balance", 0))


# ---------------------------------------------------------------- onboarding
TARGETS = {"₹5,000": 5000, "₹10,000": 10000, "₹25,000": 25000}


def _onboarding(state):
    step = st.session_state.get("gk_onb", 1)
    K.steps(step, 3)
    if step == 1:
        K.card(f'<div class="kx-mid">{t("onb1_title")}</div><div class="kx-line">{t("onb1_line")}</div>'
               f'<div class="kx-muted">{t("onb1_muted")}</div>', "blue")
        if st.button(t("btn_start"), type="primary", width="stretch", key="gk_onb1"):
            st.session_state.gk_onb = 2
            st.rerun()
    elif step == 2:
        st.markdown(f'<div class="kx-mid">{t("onb2_q")}</div>', unsafe_allow_html=True)
        opts = _goal_options()
        goal = st.pills("goal", list(opts), default=list(opts)[0], key=f"gk_goal_pick_{_lang()}", label_visibility="collapsed")
        st.markdown(f'<div class="kx-line">{t("onb2_amt")}</div>', unsafe_allow_html=True)
        tgt = st.pills("target", list(TARGETS), default="₹10,000", key="gk_tgt_pick", label_visibility="collapsed")
        if st.button(t("btn_next"), type="primary", width="stretch", key="gk_onb2"):
            state["goal"] = {"name": opts.get(goal, "Bas bachat"), "target": TARGETS.get(tgt or "₹10,000", 10000)}
            st.session_state.gk_onb = 3
            st.rerun()
    else:
        st.markdown(f'<div class="kx-mid">{t("onb3_q")}</div>', unsafe_allow_html=True)
        caps = {"1%": 1.0, "2%": 2.0, "3%": 3.0}
        cap_lbl = st.pills("limit", list(caps), default="3%", key="gk_cap_pick", label_visibility="collapsed")
        cap = caps.get(cap_lbl or "3%", 3.0)
        K.card(f'<div class="kx-line">{t("onb3_example", amt=E.rs(4000 * cap / 100))}</div>'
               f'<div class="kx-muted">{t("onb3_example2")}</div>')
        st.markdown(f'<div class="kx-muted">{t("onb3_points")}</div><div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button(t("btn_agree"), type="primary", width="stretch", key="gk_onb3"):
            state.update(opted_in=True, mode="suggest", cap_pct=cap, yes_count=0, suggest_days_left=E.SUGGEST_DAYS)
            st.session_state.gk_onb = 1
            st.toast(t("toast_started"))
            st.rerun()


# ---------------------------------------------------------------- today card
def _today_card(state):
    day = _today(state)
    rec = _rec(state, day)
    entry = _entry(state, day)
    s = rec["settlement"] or 0
    dname = _day_name(day)

    if state.get("auto_offer_pending"):
        K.card(f'<div class="kx-kicker">{t("auto_kicker")}</div><div class="kx-mid">{t("auto_q")}</div>'
               f'<div class="kx-line">{t("auto_line")}</div>', "blue")
        c1, c2 = st.columns(2)
        if c1.button(t("btn_auto_yes"), type="primary", width="stretch", key="gk_auto_yes"):
            E.accept_auto(state, True)
            st.toast(t("toast_auto"))
            st.rerun()
        if c2.button(t("btn_auto_no"), width="stretch", key="gk_auto_no"):
            E.accept_auto(state, False)
            st.rerun()
        return

    if rec["reason_code"] == "no_data":
        K.card(f'<div class="kx-mid">{t("r_no_data")}</div><div class="kx-muted">{t("no_data_sub")}</div>', "grey")
        return

    if state.get("mode") == "paused":
        K.card(f'<div class="kx-kicker">{t("kicker_today", day=dname, amt=E.rs(s))}</div><div class="kx-mid">{t("r_paused")}</div>'
               f'<div class="kx-line">{t("all_yours", amt=E.rs(s))}</div><span class="kx-chip grey">{t("chip_paused")}</span>', "grey")
        return

    if entry and entry["action"] == "saved":
        amt = entry["amount"]
        K.card(f'<div class="kx-kicker">{t("kicker_today", day=dname, amt=E.rs(s))}</div>'
               f'<div class="kx-big">{t("keep_big", amt=E.rs(s - amt))}</div>'
               f'<div class="kx-line">{t("saved_line", amt=E.rs(amt))}</div>'
               f'<div class="kx-muted">{_why(entry)}</div><span class="kx-chip green">{t("chip_saved", amt=E.rs(amt))}</span>', "green")
        _speak_once(rec["spoken_line"])
        return

    if entry and entry["action"] in ("skipped", "declined"):
        K.card(f'<div class="kx-kicker">{t("kicker_today", day=dname, amt=E.rs(s))}</div>'
               f'<div class="kx-big">{t("keep_big", amt=E.rs(s))}</div>'
               f'<div class="kx-line">{t("skipped_line")}</div>'
               f'<span class="kx-chip amber">● {_why(entry)}</span>', "amber")
        return

    # suggest mode, a normal/good day: evening confirm card
    K.card(f'<div class="kx-kicker">{t("kicker_evening", day=dname, amt=E.rs(s))}</div>'
           f'<div class="kx-big">{t("ask_big", amt=E.rs(rec["amount"]))}</div>'
           f'<div class="kx-muted">{rec["reason"]}</div>'
           f'<div class="kx-line">{t("ask_keep", amt=E.rs(s - rec["amount"]))}</div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_yes"), type="primary", width="stretch", key="gk_yes"):
        E.suggest_answer(state, rec, yes=True)
        st.session_state.gk_speak = rec["spoken_line"]
        st.rerun()
    if c2.button(t("btn_not_today"), width="stretch", key="gk_no"):
        E.suggest_answer(state, rec, yes=False)
        st.rerun()


def _speak_once(line):
    if st.session_state.get("gk_speak") == line:
        K.speak(line, autoplay=True, key="gk_tts")
        st.session_state.gk_speak = None


# ---------------------------------------------------------------- balance + strip
def _sahara(days):
    return t("sahara_days", d=f"{days:g}") if days >= 0.5 else t("sahara_building")


def _balance_block(state):
    bal = int(state.get("balance", 0))
    g = E.goal_status(state, _lang())
    if g["reached"]:
        K.card(f'<div class="kx-mid">🎉 {g["message"]}</div>', "green")
        if st.button(t("btn_new_goal"), type="primary", width="stretch", key="gk_newgoal"):
            _go("goal")
        return
    K.card(f'<div class="kx-kicker">{t("bal_kicker")}</div><div class="kx-big">₹{E.rs(bal)}</div>'
           f'<div class="kx-line">{_sahara(E.buffer_days(bal, _avg(state)))}</div>'
           f'<div class="kx-muted" style="margin-top:12px">'
           f'{t("goal_line", goal=_goal_name(state), pct=int(g["progress"] * 100), target=E.rs(state["goal"]["target"]))}</div>'
           f'{K.bar(g["progress"])}')


def _strip(state):
    end = date.fromisoformat(_today(state))
    days = [(end - timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    icon = {"saved": "🟢", "skipped": "🟠", "declined": "⚪"}
    labels = {}
    for d in days:
        e = _entry(state, d)
        mark = icon.get(e["action"], "◽") if e else "◽"
        if e and e.get("reason_code") == "paused":
            mark = "⏸"
        if e:
            text = (t("strip_saved", amt=E.rs(e["amount"]), why=_why(e)) if e["action"] == "saved"
                    else t("strip_not", why=_why(e)))
        else:
            text = t("strip_none")
        labels[f"{mark} {_day_name(d)}"] = text
    st.markdown(f'<div class="kx-kicker" style="margin-top:6px">{t("strip_title")}</div>', unsafe_allow_html=True)
    pick = st.segmented_control("days", list(labels), default=None, key=f"gk_strip_pick_{_lang()}", label_visibility="collapsed")
    if pick:
        st.caption(f"{pick.split(' ', 1)[1]}: {labels[pick]}")


def _backtest_box(state):
    S, OB = _data()
    bt = E.backtest(S, OB, state.get("cap_pct", 3.0), _today(state), days=30)
    slow = bt["skip_reasons"].get("slow_day", 0)
    other = bt["skipped_days"] - slow
    extra = t("bt_extra", n=other) if other else ""
    K.card(f'<div class="kx-kicker">{t("bt_kicker")}</div><div class="kx-line">{t("bt_line", amt=E.rs(bt["total"]))}</div>'
           f'<div class="kx-muted">{t("bt_skip", n=bt["skipped_days"], slow=slow, extra=extra)}</div>')


# ---------------------------------------------------------------- nudges
def _bad_week_drop(state):
    S, _ = _data()
    if st.session_state.get("gk_demo_badweek"):
        return 25
    return E.week_drop(S, _today(state))


def _bad_week_card(state, button_key):
    drop = _bad_week_drop(state)
    bal = int(state.get("balance", 0))
    if drop >= 20 and bal > 0 and state.get("opted_in"):
        K.card(f'<div class="kx-mid">{t("bw_title", pct=drop)}</div><div class="kx-line">{t("bw_line", amt=E.rs(bal))}</div>', "amber")
        return st.button(t("btn_see_gullak"), key=button_key, width="stretch")
    return False


# ---------------------------------------------------------------- flows
def _withdraw(state):
    bal = int(state.get("balance", 0))
    st.markdown(f'<div class="kx-mid">{t("wd_q")}</div>', unsafe_allow_html=True)
    st.caption(t("wd_have", amt=E.rs(bal)))
    opts = {"₹500": 500, "₹1,000": 1000, "₹2,000": 2000, t("wd_all"): bal}
    pick = st.pills("amount", list(opts), key=f"gk_wd_pick_{_lang()}", label_visibility="collapsed")
    amt = st.number_input(t("wd_type"), min_value=0, max_value=max(bal, 0), step=100,
                          value=min(int(opts[pick]), bal) if pick else 0, key=f"gk_wd_num_{pick}")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_next"), type="primary", width="stretch", key="gk_wd_next", disabled=amt <= 0):
        st.session_state.gk_wd_amount = int(amt)
        _go("withdraw_confirm")
    if c2.button(t("btn_back"), width="stretch", key="gk_wd_back"):
        _go("main")


def _withdraw_confirm(state):
    amt = int(st.session_state.get("gk_wd_amount", 0))
    bal = int(state.get("balance", 0))
    if amt > bal:
        K.card(f'<div class="kx-mid">{t("wd_too_much", a=E.rs(bal))}</div>', "amber")
        if st.button(t("btn_change_amt"), type="primary", width="stretch", key="gk_wdc_fix"):
            _go("withdraw")
        return
    K.card(f'<div class="kx-big">{t("wd_confirm", amt=E.rs(amt))}</div><div class="kx-line">{t("wd_left", amt=E.rs(bal - amt))}</div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_wd_yes"), type="primary", width="stretch", key="gk_wdc_yes"):
        ok, msg = E.withdraw(state, amt, _today(state), lang=_lang())
        st.session_state.gk_flash = ("green" if ok else "amber", msg)
        _go("main")
    if c2.button(t("btn_no"), width="stretch", key="gk_wdc_no"):
        _go("main")


def _goal(state):
    st.markdown(f'<div class="kx-mid">{t("goal_new_title")}</div>', unsafe_allow_html=True)
    opts = _goal_options()
    goal = st.pills("goal", list(opts), default=None, key=f"gk_goal2_{_lang()}", label_visibility="collapsed")
    tgt = st.pills("target", list(TARGETS), default=None, key="gk_tgt2", label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button(t("btn_confirm"), type="primary", width="stretch", key="gk_goal_ok", disabled=not (goal and tgt)):
        state["goal"] = {"name": opts[goal], "target": TARGETS[tgt]}
        st.session_state.gk_flash = ("green", t("flash_goal", goal=goal, amt=E.rs(TARGETS[tgt])))
        _go("main")
    if c2.button(t("btn_back"), width="stretch", key="gk_goal_back"):
        _go("main")


def _cap(state):
    st.markdown(f'<div class="kx-mid">{t("cap_title")}</div>', unsafe_allow_html=True)
    st.caption(t("cap_never"))
    caps = {"1%": 1.0, "2%": 2.0, "3%": 3.0, "4%": 4.0, "5%": 5.0}
    cur = f"{int(state.get('cap_pct', 3))}%"
    pick = st.pills("limit", list(caps), default=cur if cur in caps else "3%", key="gk_cap2", label_visibility="collapsed")
    cap = caps.get(pick or cur, 3.0)
    st.markdown(f'<div class="kx-line">{t("cap_example", amt=E.rs(4000 * cap / 100))}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button(t("btn_confirm"), type="primary", width="stretch", key="gk_cap_ok"):
        state["cap_pct"] = E.clamp_cap(cap)
        st.session_state.gk_flash = ("green", t("flash_cap", pct=int(state["cap_pct"])))
        _go("main")
    if c2.button(t("btn_back"), width="stretch", key="gk_cap_back"):
        _go("main")


def _cmd_confirm(state):
    c = st.session_state.get("gk_cmd") or {}
    if c.get("intent") == "set_goal":
        name = c.get("goal_name") or "Bas bachat"
        target = c.get("amount") or state["goal"]["target"]
        K.card(f'<div class="kx-mid">{t("cc_goal", goal=goal_label(_lang(), name))}</div>'
               f'<div class="kx-line">{t("cc_target", amt=E.rs(target))}</div>', "blue")
        if st.button(t("btn_yes"), type="primary", width="stretch", key="gk_cc_goal"):
            state["goal"] = {"name": name, "target": int(target)}
            st.session_state.gk_flash = ("green", t("flash_goal", goal=goal_label(_lang(), name), amt=E.rs(target)))
            _go("main")
    elif c.get("intent") == "change_cap":
        K.card(f'<div class="kx-mid">{t("cc_cap", pct=int(c["cap"]))}</div>'
               f'<div class="kx-line">{t("cap_example", amt=E.rs(40 * c["cap"]))}</div>', "blue")
        if st.button(t("btn_yes"), type="primary", width="stretch", key="gk_cc_cap"):
            state["cap_pct"] = c["cap"]
            st.session_state.gk_flash = ("green", t("flash_cap", pct=int(c["cap"])))
            _go("main")
    if st.button(t("btn_no"), width="stretch", key="gk_cc_no"):
        _go("main")


def _voice(state):
    st.markdown(f'<div class="kx-kicker" style="margin-top:8px">{t("voice_title")}</div>', unsafe_allow_html=True)
    heard = K.listen(t("mic_label"), key="gk_mic")
    text = st.text_input("command", value=heard or "", placeholder=t("voice_ph"),
                         key=f"gk_cmd_text_{bool(heard)}", label_visibility="collapsed")
    if st.button(t("btn_send"), width="stretch", key="gk_cmd_go") and text.strip():
        llm_out = ai.read_command(text, state.get("balance", 0), _lang()) if ai.available() else None
        c = E.validate_command(llm_out, text, state, lang=_lang())
        st.session_state.gk_reply = _do_command(state, c)
        st.rerun()
    if st.session_state.get("gk_reply"):
        st.markdown(f'<div class="kx-say">{st.session_state.gk_reply}</div>', unsafe_allow_html=True)
        K.speak(st.session_state.gk_reply, key="gk_reply_tts")


def _do_command(state, c):
    i = c["intent"]
    if i == "withdraw":
        if not c.get("amount"):
            return c.get("question") or t("q_how_much")
        st.session_state.gk_wd_amount = int(c["amount"])
        st.session_state.gk_view = "withdraw_confirm"
        return t("r_withdraw_q", amt=E.rs(c["amount"]))
    if i == "pause":
        E.set_mode(state, "paused")
        return t("r_paused_now")
    if i == "resume":
        E.resume(state)
        return t("r_resumed")
    if i in ("set_goal", "change_cap"):
        if i == "change_cap" and c.get("cap") is None:
            return c.get("question")
        st.session_state.gk_cmd = c
        st.session_state.gk_view = "cmd_confirm"
        return t("r_confirm_below")
    if i == "status":
        return t("r_status", amt=E.rs(state.get("balance", 0)), goal=E.goal_status(state, _lang())["message"])
    return c.get("question") or t("q_unknown")


# ---------------------------------------------------------------- demo controls
def _demo_controls(state):
    with st.expander(t("demo")):
        S, OB = _data()
        last = max(S)
        c1, c2 = st.columns(2)
        today = _today(state)
        can_next = today < last and (_entry(state, today) is not None or not state.get("opted_in"))
        if c1.button(t("demo_next"), width="stretch", key="gk_next", disabled=not can_next):
            state["today"] = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
            st.rerun()
        if c2.button(t("demo_preset"), width="stretch", key="gk_preset"):
            bt = E.backtest(S, OB, 3.0, "2026-11-19", days=30)
            opening = 4487  # mock: saved in earlier months
            st.session_state.gk_state = {
                "mock": True, "opted_in": True, "mode": "auto", "cap_pct": 3.0,
                "goal": {"name": "Diwali", "target": 10000}, "balance": opening + bt["total"],
                "yes_count": 3, "auto_offer_done": True, "suggest_days_left": 0, "today": "2026-11-19",
                "history": bt["history"],
            }
            st.session_state.gk_rec_cache = {}
            st.rerun()
        c3, c4 = st.columns(2)
        st.session_state.gk_demo_badweek = c3.toggle(t("demo_badweek"), value=st.session_state.get("gk_demo_badweek", False),
                                                     key="gk_bw_toggle")
        if c4.button(t("demo_reset"), width="stretch", key="gk_reset"):
            for k in ("gk_state", "gk_view", "gk_rec_cache", "gk_onb", "gk_reply", "gk_flash"):
                st.session_state.pop(k, None)
            st.rerun()
        st.caption(f"{today} · {state.get('mode')} · AI: {'on' if ai.available() else 'fallback'}")


# ---------------------------------------------------------------- page
def render_page():
    K.inject_css()
    state = get_state()
    with st.container(key="kx_page_gullak"):
        K.header(t("gk_title"), t("gk_sub"))
        if not state.get("opted_in"):
            _onboarding(state)
            _demo_controls(state)
            K.foot(t("foot_gullak"))
            return

        _settle_today(state)
        flash = st.session_state.pop("gk_flash", None)
        if flash:
            K.card(f'<div class="kx-line">{flash[1]}</div>', flash[0])

        view = st.session_state.get("gk_view", "main")
        if view == "withdraw":
            _withdraw(state)
        elif view == "withdraw_confirm":
            _withdraw_confirm(state)
        elif view == "goal":
            _goal(state)
        elif view == "cap":
            _cap(state)
        elif view == "cmd_confirm":
            _cmd_confirm(state)
        else:
            _today_card(state)
            _bad_week_card(state, "gk_bw_btn_page")
            _balance_block(state)
            _strip(state)
            st.write("")
            c1, c2 = st.columns(2)
            if c1.button(t("btn_withdraw"), width="stretch", key="gk_a_wd", disabled=state.get("balance", 0) <= 0):
                _go("withdraw")
            paused = state.get("mode") == "paused"
            if c2.button(t("btn_resume") if paused else t("btn_pause"), width="stretch", key="gk_a_pause"):
                E.resume(state) if paused else E.set_mode(state, "paused")
                st.session_state.gk_rec_cache = {}
                st.rerun()
            c3, c4 = st.columns(2)
            if c3.button(t("btn_goal"), width="stretch", key="gk_a_goal"):
                _go("goal")
            if c4.button(t("btn_cap"), width="stretch", key="gk_a_cap"):
                _go("cap")
            _backtest_box(state)
            _voice(state)
            with st.expander(t("log_title")):
                acts = {"saved": t("act_saved"), "skipped": t("act_skipped"), "declined": t("act_declined"),
                        "withdrawn": t("act_withdrawn")}
                rows = [{t("col_date"): h["date"], t("col_what"): acts[h["action"]], "₹": E.rs(h["amount"]),
                         t("col_why"): _why(h)} for h in reversed(state.get("history", []))]
                st.dataframe(rows, hide_index=True, width="stretch") if rows else st.caption(t("log_empty"))
        _demo_controls(state)
        K.foot(t("foot_gullak"))


def render_home_card():
    """Card for the Aaj (home) screen."""
    K.inject_css()
    state = get_state()
    with st.container(key="kx_card_gullak"):
        if not state.get("opted_in"):
            K.card(f'<div class="kx-kicker">{t("hc_gk_kicker")}</div><div class="kx-mid">{t("hc_gk_title")}</div>'
                   f'<div class="kx-muted">{t("onb1_line")}</div>', "blue")
            if st.button(t("btn_start"), key="gk_home_start", width="stretch"):
                st.session_state.nav = NAV_KEY
                st.rerun()
            return
        _settle_today(state)
        bal = int(state.get("balance", 0))
        g = E.goal_status(state, _lang())
        e = _entry(state, _today(state))
        if state.get("mode") == "paused":
            chip = f'<span class="kx-chip grey">{t("chip_paused")}</span>'
        elif e and e["action"] == "saved":
            chip = f'<span class="kx-chip green">{t("chip_saved", amt=E.rs(e["amount"]))}</span>'
        elif e:
            chip = f'<span class="kx-chip amber">{t("chip_not_today", why=_why(e))}</span>'
        else:
            chip = f'<span class="kx-chip blue">{t("chip_pending")}</span>'
        K.card(f'<div class="kx-kicker">{t("hc_gk_kicker")}</div><div class="kx-big">{t("hc_gk_saved", amt=E.rs(bal))}</div>'
               f'<div class="kx-line">{_sahara(E.buffer_days(bal, _avg(state)))}</div>'
               f'<div class="kx-muted">{_goal_name(state)} {int(g["progress"] * 100)}%</div>{K.bar(g["progress"])}{chip}')
        if _bad_week_card(state, "gk_bw_btn_home"):
            st.session_state.nav = NAV_KEY
            st.rerun()
        if st.button(t("btn_open_gullak"), key="gk_home_open", width="stretch"):
            st.session_state.nav = NAV_KEY
            st.rerun()
