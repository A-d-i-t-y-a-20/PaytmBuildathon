"""Galla Gullak UI (Streamlit). Concept demo with mock data -- no real money moves.

Entry points used by app.py:
  render_page()       -> the "Gullak" sidebar page
  render_home_card()  -> small card on the Home dashboard
"""
import copy
from datetime import date, timedelta

import streamlit as st

from features.common import ui_kit as K
from features.gullak import adapter, ai
from features.gullak import engine as E

NAV_KEY = "gullak"
DAY_NAMES = ["Som", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Ravi"]


# ---------------------------------------------------------------- state
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
    """Decision for a day, computed once per (day, cap, mode) so reruns don't re-call the LLM."""
    S, OB = _data()
    cache = st.session_state.setdefault("gk_rec_cache", {})
    key = (day, state.get("cap_pct"), state.get("mode"))
    if key not in cache:
        llm_fn = ai.smart_amount if ai.available() else None
        cache[key] = E.decide_day(S, OB, state, day, llm_fn=llm_fn)
    return cache[key]


def _entry(state, day):
    for h in reversed(state.get("history", [])):
        if h["date"] == day and h["action"] in ("saved", "skipped", "declined"):
            return h
    return None


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


# ---------------------------------------------------------------- shared public helpers
def summary_line(day=None):
    state = st.session_state.get("gk_state") or adapter.load_seed_state()
    return E.summary_line(state, day or state.get("today", date.today().isoformat()))


def balance():
    state = st.session_state.get("gk_state") or adapter.load_seed_state()
    return int(state.get("balance", 0))


# ---------------------------------------------------------------- onboarding
def _onboarding(state):
    step = st.session_state.get("gk_onb", 1)
    K.steps(step, 3)
    if step == 1:
        K.card('<div class="kx-mid">Roz ki bikri se thoda-thoda bachao.</div>'
               '<div class="kx-line">Kharab din pe apne aap ruk jayega.</div>'
               '<div class="kx-muted">Woh chhote paise jo roz galle se kho jaate hain, gullak mein jama honge.</div>', "blue")
        if st.button("Shuru karein", type="primary", width="stretch", key="gk_onb1"):
            st.session_state.gk_onb = 2
            st.rerun()
    elif step == 2:
        st.markdown('<div class="kx-mid">Kis cheez ke liye bachana hai?</div>', unsafe_allow_html=True)
        goal = st.pills("Goal", E.GOALS, default=state["goal"]["name"] if state["goal"]["name"] in E.GOALS else "Diwali",
                        key="gk_goal_pick", label_visibility="collapsed")
        st.markdown('<div class="kx-line">Kitna jama karna hai?</div>', unsafe_allow_html=True)
        targets = {"₹5,000": 5000, "₹10,000": 10000, "₹25,000": 25000}
        tgt = st.pills("Target", list(targets), default="₹10,000", key="gk_tgt_pick", label_visibility="collapsed")
        if st.button("Aage", type="primary", width="stretch", key="gk_onb2"):
            state["goal"] = {"name": goal or "Bas bachat", "target": targets.get(tgt or "₹10,000", 10000)}
            st.session_state.gk_onb = 3
            st.rerun()
    else:
        st.markdown('<div class="kx-mid">Roz ki bikri ka kitna hissa?</div>', unsafe_allow_html=True)
        caps = {"1%": 1.0, "2%": 2.0, "3%": 3.0}
        cap_lbl = st.pills("Limit", list(caps), default="3%", key="gk_cap_pick", label_visibility="collapsed")
        cap = caps.get(cap_lbl or "3%", 3.0)
        K.card(f'<div class="kx-line">₹4,000 ki bikri pe <b>₹{E.rs(4000 * cap / 100)}</b> tak gullak mein.</div>'
               '<div class="kx-muted">Normal din pe aadha. Kharab din pe kuch nahi.</div>')
        st.markdown('<div class="kx-muted">✔ Kabhi bhi rok sakte ho, kabhi bhi nikaal sakte ho.<br>'
                    '✔ Pehle 7 din har shaam aapse poochenge.<br>✔ Concept demo, partner ke through. Koi asli paisa nahi katega.</div>'
                    '<div style="height:14px"></div>',
                    unsafe_allow_html=True)
        if st.button("Haan, shuru karo", type="primary", width="stretch", key="gk_onb3"):
            state.update(opted_in=True, mode="suggest", cap_pct=cap, yes_count=0, suggest_days_left=E.SUGGEST_DAYS)
            st.session_state.gk_onb = 1
            st.toast("Gullak shuru ho gaya")
            st.rerun()


# ---------------------------------------------------------------- today card
def _today_card(state):
    day = _today(state)
    rec = _rec(state, day)
    entry = _entry(state, day)
    s = rec["settlement"] or 0
    dname = DAY_NAMES[date.fromisoformat(day).weekday()]

    if state.get("auto_offer_pending"):
        K.card('<div class="kx-kicker">3 din aapne haan kaha</div>'
               '<div class="kx-mid">Ab se apne aap daal doon?</div>'
               '<div class="kx-line">Kharab din pe nahi daalunga. Har baar batata rahunga.</div>', "blue")
        c1, c2 = st.columns(2)
        if c1.button("Haan, apne aap", type="primary", width="stretch", key="gk_auto_yes"):
            E.accept_auto(state, True)
            st.toast("Ab se apne aap. Rokna ho to ek tap.")
            st.rerun()
        if c2.button("Nahi, poochte raho", width="stretch", key="gk_auto_no"):
            E.accept_auto(state, False)
            st.rerun()
        return

    if rec["reason_code"] == "no_data":
        K.card('<div class="kx-mid">Aaj ka data abhi nahi aaya</div><div class="kx-muted">Settlement aate hi bataenge.</div>', "grey")
        return

    if state.get("mode") == "paused":
        K.card(f'<div class="kx-kicker">{dname} · aaj aaye ₹{E.rs(s)}</div><div class="kx-mid">Gullak ruka hua hai</div>'
               f'<div class="kx-line">Poore ₹{E.rs(s)} aapke paas.</div><span class="kx-chip grey">⏸ Ruka hua</span>', "grey")
        return

    if entry and entry["action"] == "saved":
        K.card(f'<div class="kx-kicker">{dname} · aaj aaye ₹{E.rs(s)}</div>'
               f'<div class="kx-big">₹{E.rs(s - entry["amount"])} aapke paas</div>'
               f'<div class="kx-line">₹{E.rs(entry["amount"])} gullak mein daale.</div>'
               f'<div class="kx-muted">{entry["reason"]}</div><span class="kx-chip green">✓ Aaj ₹{E.rs(entry["amount"])} daale</span>', "green")
        _speak_once(rec["spoken_line"])
        return

    if entry and entry["action"] in ("skipped", "declined"):
        why = entry["reason"]
        K.card(f'<div class="kx-kicker">{dname} · aaj aaye ₹{E.rs(s)}</div>'
               f'<div class="kx-big">₹{E.rs(s)} aapke paas</div>'
               f'<div class="kx-line">Aaj gullak mein kuch nahi daala.</div>'
               f'<span class="kx-chip amber">● {why}</span>', "amber")
        return

    # suggest mode, a normal/good day: evening confirm card
    K.card(f'<div class="kx-kicker">{dname} shaam · aaj aaye ₹{E.rs(s)}</div>'
           f'<div class="kx-big">₹{E.rs(rec["amount"])} gullak mein daalein?</div>'
           f'<div class="kx-muted">{rec["reason"]}</div>'
           f'<div class="kx-line">Aapke paas <b>₹{E.rs(s - rec["amount"])}</b> rahenge.</div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button("Haan", type="primary", width="stretch", key="gk_yes"):
        E.suggest_answer(state, rec, yes=True)
        st.session_state.gk_speak = rec["spoken_line"]
        st.rerun()
    if c2.button("Aaj nahi", width="stretch", key="gk_no"):
        E.suggest_answer(state, rec, yes=False)
        st.rerun()


def _speak_once(line):
    if st.session_state.get("gk_speak") == line:
        if not K.speak(line, autoplay=True, key="gk_tts"):
            pass
        st.session_state.gk_speak = None


# ---------------------------------------------------------------- balance + strip
def _balance_block(state):
    bal = int(state.get("balance", 0))
    g = E.goal_status(state)
    days = E.buffer_days(bal, _avg(state))
    if g["reached"]:
        K.card(f'<div class="kx-mid">🎉 {g["message"]}</div>', "green")
        if st.button("Naya goal chuno", type="primary", width="stretch", key="gk_newgoal"):
            _go("goal")
        return
    K.card(f'<div class="kx-kicker">🪙 Gullak mein jama</div><div class="kx-big">₹{E.rs(bal)}</div>'
           f'<div class="kx-line">{_sahara(days)}</div>'
           f'<div class="kx-muted" style="margin-top:12px">{state["goal"]["name"]} · {int(g["progress"] * 100)}% · '
           f'lakshya ₹{E.rs(state["goal"]["target"])}</div>{K.bar(g["progress"])}')


def _sahara(days):
    return f"{days:g} din ka sahara" if days >= 0.5 else "Sahara ban raha hai"


def _strip(state):
    end = date.fromisoformat(_today(state))
    days = [(end - timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    icon = {"saved": "🟢", "skipped": "🟠", "declined": "⚪"}
    labels = {}
    for d in days:
        e = _entry(state, d)
        name = DAY_NAMES[date.fromisoformat(d).weekday()]
        mark = icon.get(e["action"], "◽") if e else "◽"
        if e and e.get("reason") == E.REASONS["paused"]:
            mark = "⏸"
        if e:
            text = (f"₹{E.rs(e['amount'])} daale · {e['reason']}" if e["action"] == "saved"
                    else f"Nahi daala · {e['reason']}")
        else:
            text = "Gullak shuru nahi hua tha"
        labels[f"{mark} {name}"] = text
    st.markdown('<div class="kx-kicker" style="margin-top:6px">Pichhle 7 din · din dabao, wajah dekho</div>', unsafe_allow_html=True)
    pick = st.segmented_control("Din chuno", list(labels), default=None, key="gk_strip_pick", label_visibility="collapsed")
    if pick:
        st.caption(f"{pick.split(' ', 1)[1]}: {labels[pick]}")


def _backtest_box(state):
    S, OB = _data()
    bt = E.backtest(S, OB, state.get("cap_pct", 3.0), _today(state), days=30)
    slow = bt["skip_reasons"].get("slow_day", 0)
    other = bt["skipped_days"] - slow
    extra = f", {other} din EMI ya maal ke liye" if other else ""
    K.card(f'<div class="kx-kicker">Pichhle 30 din</div>'
           f'<div class="kx-line">Agar 30 din pehle shuru karte, aaj gullak mein <b>₹{E.rs(bt["total"])}</b> hota.</div>'
           f'<div class="kx-muted">{bt["skipped_days"]} din chhod diye: {slow} din bikri kam thi{extra}.</div>', "")


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
        K.card(f'<div class="kx-mid">Is hafte bikri {drop}% kam hai.</div>'
               f'<div class="kx-line">Loan lene se pehle: gullak mein <b>₹{E.rs(bal)}</b> hai.</div>', "amber")
        return st.button("Gullak dekho", key=button_key, width="stretch")
    return False


# ---------------------------------------------------------------- flows
def _withdraw(state):
    bal = int(state.get("balance", 0))
    st.markdown('<div class="kx-mid">Kitne nikaalne hain?</div>', unsafe_allow_html=True)
    st.caption(f"Gullak mein ₹{E.rs(bal)} hai")
    opts = {"₹500": 500, "₹1,000": 1000, "₹2,000": 2000, "Sab": bal}
    pick = st.pills("Rakam", list(opts), key="gk_wd_pick", label_visibility="collapsed")
    amt = st.number_input("Ya rakam likho (₹)", min_value=0, max_value=max(bal, 0), step=100,
                          value=int(opts[pick]) if pick else 0, key=f"gk_wd_num_{pick}")
    c1, c2 = st.columns(2)
    if c1.button("Aage", type="primary", width="stretch", key="gk_wd_next", disabled=amt <= 0):
        st.session_state.gk_wd_amount = int(amt)
        _go("withdraw_confirm")
    if c2.button("Wapas", width="stretch", key="gk_wd_back"):
        _go("main")


def _withdraw_confirm(state):
    amt = int(st.session_state.get("gk_wd_amount", 0))
    bal = int(state.get("balance", 0))
    if amt > bal:
        K.card(f'<div class="kx-mid">Gullak mein sirf ₹{E.rs(bal)} hai.</div><div class="kx-line">Itna nahi nikaal sakte.</div>', "amber")
        if st.button("Rakam badlo", type="primary", width="stretch", key="gk_wdc_fix"):
            _go("withdraw")
        return
    K.card(f'<div class="kx-big">₹{E.rs(amt)} nikaalein?</div>'
           f'<div class="kx-line">Gullak mein ₹{E.rs(bal - amt)} bachenge.</div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button("Haan, nikalo", type="primary", width="stretch", key="gk_wdc_yes"):
        ok, msg = E.withdraw(state, amt, _today(state))
        st.session_state.gk_flash = ("green" if ok else "amber", msg)
        _go("main")
    if c2.button("Nahi", width="stretch", key="gk_wdc_no"):
        _go("main")


def _goal(state):
    st.markdown('<div class="kx-mid">Naya goal</div>', unsafe_allow_html=True)
    goal = st.pills("Goal", E.GOALS, default=None, key="gk_goal2", label_visibility="collapsed")
    targets = {"₹5,000": 5000, "₹10,000": 10000, "₹25,000": 25000}
    tgt = st.pills("Target", list(targets), default=None, key="gk_tgt2", label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("Pakka karo", type="primary", width="stretch", key="gk_goal_ok", disabled=not (goal and tgt)):
        state["goal"] = {"name": goal, "target": targets[tgt]}
        st.session_state.gk_flash = ("green", f"Naya goal: {goal}, ₹{E.rs(targets[tgt])}")
        _go("main")
    if c2.button("Wapas", width="stretch", key="gk_goal_back"):
        _go("main")


def _cap(state):
    st.markdown('<div class="kx-mid">Roz ki limit</div>', unsafe_allow_html=True)
    st.caption("Kabhi 5% se zyada nahi.")
    caps = {"1%": 1.0, "2%": 2.0, "3%": 3.0, "4%": 4.0, "5%": 5.0}
    cur = f"{int(state.get('cap_pct', 3))}%"
    pick = st.pills("Limit", list(caps), default=cur if cur in caps else "3%", key="gk_cap2", label_visibility="collapsed")
    cap = caps.get(pick or cur, 3.0)
    st.markdown(f'<div class="kx-line">₹4,000 ki bikri pe zyada se zyada ₹{E.rs(4000 * cap / 100)}.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Pakka karo", type="primary", width="stretch", key="gk_cap_ok"):
        state["cap_pct"] = E.clamp_cap(cap)
        st.session_state.gk_flash = ("green", f"Limit ab {int(state['cap_pct'])}%")
        _go("main")
    if c2.button("Wapas", width="stretch", key="gk_cap_back"):
        _go("main")


def _cmd_confirm(state):
    c = st.session_state.get("gk_cmd") or {}
    if c.get("intent") == "set_goal":
        name = c.get("goal_name") or "Bas bachat"
        target = c.get("amount") or state["goal"]["target"]
        K.card(f'<div class="kx-mid">Goal "{name}" rakhein?</div><div class="kx-line">Lakshya ₹{E.rs(target)}</div>', "blue")
        if st.button("Haan", type="primary", width="stretch", key="gk_cc_goal"):
            state["goal"] = {"name": name, "target": int(target)}
            st.session_state.gk_flash = ("green", f"Goal: {name}")
            _go("main")
    elif c.get("intent") == "change_cap":
        K.card(f'<div class="kx-mid">Limit {int(c["cap"])}% karein?</div>'
               f'<div class="kx-line">₹4,000 ki bikri pe zyada se zyada ₹{E.rs(40 * c["cap"])}.</div>', "blue")
        if st.button("Haan", type="primary", width="stretch", key="gk_cc_cap"):
            state["cap_pct"] = c["cap"]
            st.session_state.gk_flash = ("green", f"Limit ab {int(c['cap'])}%")
            _go("main")
    if st.button("Nahi", width="stretch", key="gk_cc_no"):
        _go("main")


def _voice(state):
    st.markdown('<div class="kx-kicker" style="margin-top:8px">🎤 Bol kar ya likh kar batao</div>', unsafe_allow_html=True)
    heard = K.listen("Mic dabao aur bolo", key="gk_mic")
    text = st.text_input("Likho", value=heard or "", placeholder='Jaise: "2000 nikalo" ya "gullak band karo"',
                         key=f"gk_cmd_text_{bool(heard)}", label_visibility="collapsed")
    if st.button("Bhejo", width="stretch", key="gk_cmd_go") and text.strip():
        llm_out = ai.read_command(text, state.get("balance", 0)) if ai.available() else None
        c = E.validate_command(llm_out, text, state)
        reply = _do_command(state, c)
        st.session_state.gk_reply = reply
        st.rerun()
    if st.session_state.get("gk_reply"):
        st.markdown(f'<div class="kx-say">{st.session_state.gk_reply.replace("Rs ", "₹")}</div>', unsafe_allow_html=True)
        K.speak(st.session_state.gk_reply, key="gk_reply_tts")


def _do_command(state, c):
    i = c["intent"]
    if i == "withdraw":
        if not c.get("amount"):
            return c.get("question") or "Kitne paise nikaalne hain?"
        st.session_state.gk_wd_amount = int(c["amount"])
        st.session_state.gk_view = "withdraw_confirm"
        return f"₹{E.rs(c['amount'])} nikaalne hain? Neeche pakka kijiye."
    if i == "pause":
        E.set_mode(state, "paused")
        return "Gullak rok diya. Chalu karna ho to bolo 'chalu karo'."
    if i == "resume":
        E.resume(state)
        return "Gullak phir chalu."
    if i in ("set_goal", "change_cap"):
        if i == "change_cap" and c.get("cap") is None:
            return c.get("question")
        st.session_state.gk_cmd = c
        st.session_state.gk_view = "cmd_confirm"
        return "Neeche pakka kijiye."
    if i == "status":
        return f"Gullak mein ₹{E.rs(state.get('balance', 0))} jama. {E.goal_status(state)['message']}."
    return c.get("question") or "Samajh nahi aaya."


# ---------------------------------------------------------------- demo controls
def _demo_controls(state):
    with st.expander("Demo controls"):
        S, OB = _data()
        last = max(S)
        c1, c2 = st.columns(2)
        today = _today(state)
        can_next = today < last and (_entry(state, today) is not None or not state.get("opted_in"))
        if c1.button("Agla din ➜", width="stretch", key="gk_next", disabled=not can_next):
            state["today"] = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
            st.rerun()
        if c2.button("3 mahine purana user", width="stretch", key="gk_preset"):
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
        st.session_state.gk_demo_badweek = c3.toggle("Kharab hafta", value=st.session_state.get("gk_demo_badweek", False),
                                                     key="gk_bw_toggle")
        if c4.button("Reset", width="stretch", key="gk_reset"):
            for k in ("gk_state", "gk_view", "gk_rec_cache", "gk_onb", "gk_reply", "gk_flash"):
                st.session_state.pop(k, None)
            st.rerun()
        st.caption(f"Demo din: {today} · mode: {state.get('mode')} · AI: {'Gemini' if ai.available() else 'fallback'}")


# ---------------------------------------------------------------- page
def render_page():
    K.inject_css()
    state = get_state()
    with st.container(key="kx_page_gullak"):
        K.header("Galla Gullak", "Roz ki bikri se thoda-thoda bachat. Kharab din pe apne aap ruk jaata hai.")
        if not state.get("opted_in"):
            _onboarding(state)
            _demo_controls(state)
            K.foot("Concept · partner ke through · mock data · koi asli paisa nahi")
            return

        _settle_today(state)
        flash = st.session_state.pop("gk_flash", None)
        if flash:
            K.card(f'<div class="kx-line">{flash[1].replace("Rs ", "₹")}</div>', flash[0])

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
            if c1.button("💸 Paise nikalo", width="stretch", key="gk_a_wd", disabled=state.get("balance", 0) <= 0):
                _go("withdraw")
            paused = state.get("mode") == "paused"
            if c2.button("▶ Chalu karo" if paused else "⏸ Rok do", width="stretch", key="gk_a_pause"):
                E.resume(state) if paused else E.set_mode(state, "paused")
                st.session_state.gk_rec_cache = {}
                st.rerun()
            c3, c4 = st.columns(2)
            if c3.button("🎯 Goal badlo", width="stretch", key="gk_a_goal"):
                _go("goal")
            if c4.button("⚙ Limit badlo", width="stretch", key="gk_a_cap"):
                _go("cap")
            _backtest_box(state)
            _voice(state)
            with st.expander("Poora hisaab (log)"):
                rows = [{"Din": h["date"], "Kya hua": {"saved": "Daala", "skipped": "Chhoda", "declined": "Mana kiya",
                                                       "withdrawn": "Nikaala"}[h["action"]],
                         "₹": E.rs(h["amount"]), "Kyun": h["reason"]} for h in reversed(state.get("history", []))]
                st.dataframe(rows, hide_index=True, width="stretch") if rows else st.caption("Abhi kuch nahi.")
        _demo_controls(state)
        K.foot("Concept · partner ke through (jaise Paytm Gold) · mock data · koi asli paisa nahi katega · "
               "koi rate, return ya guarantee nahi")


def render_home_card():
    """Small card for the Home dashboard."""
    K.inject_css()
    state = get_state()
    with st.container(key="kx_card_gullak"):
        if not state.get("opted_in"):
            K.card('<div class="kx-kicker">🪙 Galla Gullak · Concept</div>'
                   '<div class="kx-mid">Roz ki bikri se thoda bachao</div>'
                   '<div class="kx-muted">Kharab din pe apne aap ruk jayega.</div>', "blue")
            if st.button("Shuru karein", key="gk_home_start", width="stretch"):
                st.session_state.nav = NAV_KEY
                st.rerun()
            return
        _settle_today(state)
        bal = int(state.get("balance", 0))
        g = E.goal_status(state)
        e = _entry(state, _today(state))
        if state.get("mode") == "paused":
            chip = '<span class="kx-chip grey">⏸ Ruka hua</span>'
        elif e and e["action"] == "saved":
            chip = f'<span class="kx-chip green">✓ Aaj ₹{E.rs(e["amount"])} daale</span>'
        elif e:
            chip = f'<span class="kx-chip amber">● Aaj nahi, {e["reason"].split(",")[0].lower()}</span>'
        else:
            chip = '<span class="kx-chip blue">Aaj ka sawaal baaki</span>'
        K.card(f'<div class="kx-kicker">🪙 Galla Gullak · Concept</div><div class="kx-big">₹{E.rs(bal)} jama</div>'
               f'<div class="kx-line">{_sahara(E.buffer_days(bal, _avg(state)))}</div>'
               f'<div class="kx-muted">{state["goal"]["name"]} {int(g["progress"] * 100)}%</div>{K.bar(g["progress"])}{chip}')
        if _bad_week_card(state, "gk_bw_btn_home"):
            st.session_state.nav = NAV_KEY
            st.rerun()
        if st.button("Gullak kholo", key="gk_home_open", width="stretch"):
            st.session_state.nav = NAV_KEY
            st.rerun()
