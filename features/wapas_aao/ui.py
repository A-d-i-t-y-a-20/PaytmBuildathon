"""Wapas Aao UI (Streamlit). Concept demo with mock data.

Merchant journey: ask -> one finding -> priced offer -> approve -> live -> result (profit after cost).
The merchant never sees customer names, numbers or ids -- only counts and rupees.
"""
import streamlit as st

from features.common import ui_kit as K
from features.gullak.engine import rs
from features.wapas_aao import ai
from features.wapas_aao import engine as E

NAV_KEY = "wapas_aao"
EXAMPLES = ["Dopahar mein dukaan khali rehti hai", "Purane grahak nahi aa rahe"]


def _data():
    if "wa_payments" not in st.session_state:
        st.session_state.wa_payments = E.load_payments()
        st.session_state.wa_consent = E.load_consent()
        st.session_state.wa_outcome = E.load_outcome()
    return st.session_state.wa_payments, st.session_state.wa_consent, st.session_state.wa_outcome


def _proposal(offer_id=None):
    P, C, _ = _data()
    oid = offer_id or st.session_state.get("wa_offer_id", E.DEFAULT_OFFER)
    key = ("wa_prop", oid)
    if st.session_state.get("wa_prop_key") != key:
        st.session_state.wa_prop = E.build_proposal(P, C, offer_id=oid)
        st.session_state.wa_prop_key = key
    return st.session_state.wa_prop


def _stage(s):
    st.session_state.wa_stage = s
    st.rerun()


def _window(q):
    def h(x):
        return f"{x - 12 if x > 12 else x}"
    return f"{h(q['start'])}–{h(q['end'])} baje"


def _offer_hi(o):
    if o["kind"] == "flat":
        return f"₹{rs(o['min_bill'])}+ ke bill par ₹{o['value']} chhoot"
    if o["kind"] == "free_item":
        return f"₹{rs(o['min_bill'])}+ ke bill par biscuit packet free"
    return f"Har 5vi visit par ₹{o['value']} wapas (₹{o['min_bill']}+ bill)"


# ---------------------------------------------------------------- stages
def _ask():
    K.card('<div class="kx-mid">Dukaan mein kya pareshani hai?</div>'
           '<div class="kx-muted">Bolo ya likho. Jaise: "Dopahar mein dukaan khali rehti hai"</div>', "blue")
    heard = K.listen("Mic dabao aur bolo", key="wa_mic")
    pick = st.pills("Udaharan", EXAMPLES, key="wa_example", label_visibility="collapsed")
    text = st.text_input("Likho", value=heard or pick or "", key=f"wa_text_{heard}_{pick}", label_visibility="collapsed",
                         placeholder="Apni baat likho")
    if st.button("Munim se poocho", type="primary", width="stretch", key="wa_ask_go", disabled=not text.strip()):
        llm_out = ai.understand(text) if ai.available() else None
        v = E.validate_ask(llm_out, text)
        if v.get("offer_id"):
            st.session_state.wa_offer_id = v["offer_id"]
        if v["intent"] == "win_back":
            st.session_state.wa_said = text
            _stage("finding")
        elif v["intent"] == "refuse_contact":
            st.session_state.wa_note = ("Hum kisi grahak ka naam ya number nahi dikhate, aur sirf unhi tak pahunchte hain "
                                        "jo raazi hain. Unke liye offer banayein?")
        elif v["intent"] == "result" and st.session_state.get("wa_running"):
            _stage("result")
        else:
            st.session_state.wa_note = v.get("question") or "Thoda aur batao?"
        st.rerun()
    if st.session_state.get("wa_note"):
        st.markdown(f'<div class="kx-say">{st.session_state.wa_note}</div>', unsafe_allow_html=True)


def _finding():
    pr = _proposal()
    q = pr["quiet"]
    facts = {"drop_pct": q["drop_pct"], "window": _window(q), "lapsed": pr["lapsed"]}
    default = (f"Dopahar {_window(q)} aapki bikri baaki din se {q['drop_pct']}% kam hai.",
               f"{pr['lapsed']} pakke grahak 3 hafte se nahi aaye.")
    lines = st.session_state.get("wa_finding")
    if lines is None:
        lines = default
        if ai.available():
            out = ai.phrase({**facts, "offer": _offer_hi(pr["offer"])})
            if out and out.get("finding_line") and ai.numbers_ok(out["finding_line"], facts):
                lines = (out["finding_line"], "")
        st.session_state.wa_finding = lines
    if st.session_state.get("wa_said"):
        st.markdown(f'<div class="kx-say" style="border-radius:16px 16px 4px 16px;background:#0B2447;color:#fff;margin-left:auto;'
                    f'max-width:85%">🎤 {st.session_state.wa_said}</div>', unsafe_allow_html=True)
    K.card(f'<div class="kx-mid">{lines[0]}</div>'
           + (f'<div class="kx-line">{lines[1]}</div>' if lines[1] else "")
           + '<div class="kx-line" style="margin-top:12px"><b>Unhe dopahar mein wapas bulayein?</b></div>', "blue")
    c1, c2 = st.columns(2)
    if c1.button("Haan, kuch sujhao", type="primary", width="stretch", key="wa_find_yes"):
        _stage("proposal")
    if c2.button("Abhi nahi", width="stretch", key="wa_find_no"):
        _stage("ask")


def _split_bar(r):
    tot = r["rewards"] + r["paytm"] + r["unreachable"] or 1
    w = lambda n: 100 * n / tot  # noqa: E731
    return (f'<div class="kx-split"><i style="width:{w(r["rewards"])}%;background:{K.GREEN}"></i>'
            f'<i style="width:{w(r["paytm"])}%;background:{K.BLUE}"></i>'
            f'<i style="width:{w(r["unreachable"])}%;background:#D0D5DD"></i></div>'
            f'<div class="kx-legend"><span style="background:{K.GREEN}"></span>{r["rewards"]} rewards member '
            f'&nbsp; <span style="background:{K.BLUE}"></span>{r["paytm"]} Paytm app offer wale<br>'
            f'<span style="background:#D0D5DD"></span>{r["unreachable"]} se sampark nahi (unhone haan nahi kaha)</div>')


def _proposal_view():
    pr = _proposal()
    o, r, c, q = pr["offer"], pr["reach"], pr["cost"], pr["quiet"]
    end = f"{int(pr['end_date'][8:])} Dec"
    K.card(f'<div class="kx-kicker">Munim ka sujhaav</div><div class="kx-mid">{_offer_hi(o)}</div>'
           f'<div class="kx-line">Dopahar {_window(q)} · {pr["days"]} din ({end} tak)</div>', "blue")
    K.card(f'<div class="kx-kicker">Kitne grahakon tak pahunchega</div>'
           f'<div class="kx-mid">{r["reachable"]} mein se {pr["lapsed"]}</div>{_split_bar(r)}')
    ok = "✓ Chhoot aapke munafe ke aadhe se kam" if c["ok"] else "Offer mehenga tha, min bill badhaya"
    K.card(f'<div class="kx-row"><span>Chhoot bill ka</span><b>{c["cost_pct"]:g}%</b></div>'
           f'<div class="kx-row"><span>Aapka munafa (andaaza)</span><b>~{c["margin_pct"]}%</b></div>'
           f'<div class="kx-row"><span>Zyada se zyada kharcha</span><b>₹{rs(pr["budget"])}</b></div>'
           f'<span class="kx-chip green">{ok}</span>')
    with st.expander("Doosra offer dekho"):
        labels = {oid: _offer_hi(off) for oid, off in E.OFFER_LIBRARY.items()}
        choice = st.radio("Offer", list(labels), format_func=lambda k: labels[k], index=list(labels).index(o["id"]),
                          key="wa_offer_radio", label_visibility="collapsed")
        if choice != o["id"]:
            st.session_state.wa_offer_id = choice
            st.rerun()
    st.markdown(f'<div class="kx-muted">🔒 Aapko grahakon ke naam ya number nahi dikhenge, sirf ginti aur rupaye.<br>'
                f'📏 Sahi hisaab ke liye {pr["holdout_n"]} grahakon ko offer nahi bhejenge, unse tulna karenge.</div>',
                unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("Haan, chalao", type="primary", width="stretch", key="wa_run"):
        st.session_state.wa_running = True
        _stage("running")
    if c2.button("Wapas", width="stretch", key="wa_prop_back"):
        _stage("finding")
    st.caption("Billing: Soundbox plan mein shaamil (concept). Koi per-payment fee nahi.")


def _phones(pr):
    o = pr["offer"]
    t1, t2 = st.tabs(["Grahak: Paytm app", "Grahak: doosra UPI app"])
    with t1:
        if o["kind"] == "flat":
            res = E.apply_offer(420, o, consented=True)
            body = (f'<div style="font-size:14px;color:#5B6472">Gupta General Store ✓</div>'
                    f'<div style="font-size:30px;font-weight:800;margin:8px 0"><span class="kx-strike">₹{res["bill"]}</span>₹{res["pay"]}</div>'
                    f'<div class="kx-chip green" style="margin:0">✓ Wapas Aao offer laga: −₹{res["discount"]}</div>'
                    f'<div style="font-size:13px;color:#5B6472;margin-top:8px">Dukaan ne chhoot di. Seedha kam paisa, koi cashback nahi.</div>')
        else:
            body = f'<div style="font-size:16px">{_offer_hi(o)}</div><div style="font-size:13px;color:#5B6472">Counter par milega.</div>'
        st.markdown(f'<div class="kx-phone"><div class="bar">Paytm · Scan & Pay</div>{body}</div>', unsafe_allow_html=True)
        st.caption("Sirf unhe dikhta hai jinhone Paytm app mein shop offers chalu kiye. Hafte mein max 1 notification. Payment screen par koi consent pop-up nahi.")
    with t2:
        sp = E.stamp_progress(4)
        st.markdown('<div class="kx-phone"><div class="bar other">Koi bhi UPI app</div>'
                    '<div style="font-size:24px;font-weight:800">₹268 bheje gaye ✓</div>'
                    '<div class="kx-chip grey" style="margin:6px 0 0">Is screen par koi badlav nahi</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kx-say">🔊 Soundbox: "₹268 prapt hue. Rewards: {sp["of"]} mein se {sp["stamps"]} visit poori. '
                    f'Agli baar ₹30 wapas."</div>', unsafe_allow_html=True)
        st.caption("Grahak counter ke alag 'Rewards join' QR se ek baar judta hai. 5vi visit par ₹30 refund unke apne app mein "
                   "(Paytm legal ki manzoori baaki; tab tak dukaandaar bill se ₹30 kam karta hai). 'Chhodo' dabate hi data mit jaata hai.")


def _running():
    pr = _proposal()
    _, _, out = _data()
    K.card(f'<div class="kx-kicker">Offer chalu · {_offer_hi(pr["offer"])}</div>'
           f'<div class="kx-mid">Aaj {out["day1_redemptions"]} grahakon ko chhoot mili</div>'
           f'<div class="kx-row"><span>Kharcha</span><b>₹{out["day1_redemptions"] * pr["offer"]["value"]} / ₹{rs(pr["budget"])}</b></div>'
           f'<div class="kx-row"><span>Naye rewards member</span><b>{out["new_rewards_members_day1"]}</b></div>', "green")
    line = E.soundbox_line(E.apply_offer(420, pr["offer"], consented=True))
    st.markdown(f'<div class="kx-say">🔊 Soundbox: "{line.replace("Rs ", "₹")}"</div>', unsafe_allow_html=True)
    K.speak(line, key="wa_sb")
    st.write("")
    if st.button("14 din baad nateeja dekho (demo)", type="primary", width="stretch", key="wa_to_result"):
        _stage("result")
    if st.button("Offer roko", width="stretch", key="wa_stop"):
        st.session_state.wa_running = False
        _stage("ask")
    st.markdown('<div class="kx-kicker" style="margin-top:14px">Grahak ko kya dikhta hai</div>', unsafe_allow_html=True)
    _phones(pr)


def _result():
    pr = _proposal()
    _, _, out = _data()
    r = E.compute_result(out, pr)
    tone = "green" if r["net"] > 0 else "amber"
    K.card(f'<div class="kx-kicker">{pr["days"]} din ka nateeja</div>'
           f'<div class="kx-big">{"+" if r["net"] >= 0 else "−"}₹{rs(abs(r["net"]))}</div>'
           f'<div class="kx-line">Offer ke kharche ke baad extra munafa</div>'
           f'<div class="kx-muted">Jinhe offer nahi mila, unse tulna karke</div>', tone)
    K.card(f'<div class="kx-row"><span>Wapas aaye pakke grahak</span><b>{r["returned"]}</b></div>'
           f'<div class="kx-row"><span>Extra bikri</span><b>₹{rs(r["extra_sales"])}</b></div>'
           f'<div class="kx-row"><span>Us par munafa (~{r["margin_pct"]}%)</span><b>₹{rs(r["extra_profit"])}</b></div>'
           f'<div class="kx-row"><span>Offer kharcha ({r["redemptions"]} × ₹{pr["offer"]["value"]})</span><b>−₹{rs(r["offer_cost"])}</b></div>')
    if r["next_tip"]:
        K.card(f'<div class="kx-kicker">Agla sujhaav</div><div class="kx-line">{r["next_tip"]}. Agli baar sirf in dino chalayein?</div>', "blue")
    st.caption("Chhoti ginti hai, isliye yeh andaaza hai. Asli naap kai dukaanon ko mila kar hoga.")
    if st.button("Phir se chalao", type="primary", width="stretch", key="wa_again"):
        _stage("proposal")
    if st.button("Naya sawaal", width="stretch", key="wa_new"):
        for k in ("wa_finding", "wa_said", "wa_note", "wa_running"):
            st.session_state.pop(k, None)
        _stage("ask")


def _trust_panel():
    with st.expander("Bharosa aur niyam (compliance)"):
        st.markdown(
            "- **Sirf raazi grahak:** Paytm app mein offers chalu kiye ho, ya counter par Rewards join kiya ho. Baaki ko kuch nahi bhejte.\n"
            "- **Consent alag se:** settings ya Rewards QR par. Payment screen par kabhi nahi.\n"
            "- **Dukaandaar ko sirf ginti:** koi naam, number ya UPI ID nahi.\n"
            "- **Chhoot seedhi bill par:** grahak kam deta hai. Koi cashback ya wallet nahi.\n"
            "- **Koi SMS/WhatsApp blast nahi.**\n"
            "- **Asli taareekh:** har offer ki pakki aakhri tareekh; jhoothi jaldi nahi.\n"
            "- **Chhodo = data mitao:** grahak ek tap mein bahar, data delete.\n"
            "- **Kharcha seema:** chhoot munafe ke aadhe se kam, budget poora hote hi offer band.\n"
            "- **Loan offers is flow mein nahi.**\n"
            "- **Legal check baaki:** rewards ke liye refund ka istemaal (RBI PA niyam 2025), aur billing ka tareeka.")


# ---------------------------------------------------------------- page
def render_page():
    K.inject_css()
    _data()
    with st.container(key="kx_page_wapas"):
        K.header("Wapas Aao", "Purane pakke grahak wapas bulao. Sirf unhe jo raazi hain.")
        stage = st.session_state.get("wa_stage", "ask")
        {"ask": _ask, "finding": _finding, "proposal": _proposal_view, "running": _running, "result": _result}[stage]()
        _trust_panel()
        if stage != "ask" and st.button("Shuru se", key="wa_restart"):
            for k in ("wa_stage", "wa_finding", "wa_said", "wa_note", "wa_running", "wa_offer_id"):
                st.session_state.pop(k, None)
            st.rerun()
        K.foot(f"Concept · mock data · AI: {'Gemini' if ai.available() else 'fallback'} · koi asli payment ya message nahi")


def render_home_card():
    K.inject_css()
    _data()
    pr = _proposal()
    with st.container(key="kx_card_wapas"):
        if st.session_state.get("wa_running"):
            K.card(f'<div class="kx-kicker">🔁 Wapas Aao · Concept</div><div class="kx-mid">Offer chalu</div>'
                   f'<div class="kx-line">{_offer_hi(pr["offer"])}</div>', "green")
            label = "Nateeja dekho"
        else:
            K.card(f'<div class="kx-kicker">🔁 Wapas Aao · Concept</div>'
                   f'<div class="kx-mid">{pr["lapsed"]} pakke grahak 3 hafte se nahi aaye</div>'
                   f'<div class="kx-muted">Dopahar {_window(pr["quiet"])} dukaan khali rehti hai.</div>', "blue")
            label = "Wapas bulao"
        if st.button(label, key="wa_home_open", width="stretch"):
            st.session_state.nav = NAV_KEY
            st.session_state.wa_stage = "result" if st.session_state.get("wa_running") else "finding"
            st.rerun()
