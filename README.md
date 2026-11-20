# Galla

A phone-first app for kirana owners with two merchant features, plus a Platform Console
for the platform's (Paytm's) merchant ops team. Concept demo, mock data: no real money
or messages move. Design: "Cool Cat's" -- warm cream background, one flat deep-navy
shout colour, outlined cards, pill buttons.

Language: Hindi (Devanagari) or English, switch in the top bar. Voice commands work in Hindi script, Hinglish or English.
Switch between the merchant app and the Platform Console with the 📱/🖥 control next to the language toggle.

| Tab | Feature | What it does |
|---|---|---|
| Aaj | Home | Today's UPI money plus one card per feature |
| Gullak | Galla Gullak | A small share of each day's UPI settlement goes to a savings pot. The amount follows sales and skips bad days (slow sales, EMI due with low cash, stock purchase coming, a bad week). First 7 days it asks every evening; auto only after he agrees. |
| Grahak | Wapas Aao | Finds regular customers who stopped coming, suggests a priced offer, reaches only customers who agreed, and shows the result as profit after the offer's cost. |
| 🖥 Platform Console | Pilot vs holdout | 500 mock merchants (250 pilot / 250 holdout): pilot overview, churn radar, safe credit timing, value proof, an outcome-fee calculator, and an "ask your merchants" box. Opens any mock merchant's app view -- the shop name and Gullak data switch to that merchant. |

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Optional secrets (env vars or `.streamlit/secrets.toml`): `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) for the AI, `SARVAM_API_KEY` for voice. Without them the app uses code fallbacks and typed input.

## Tests
```
python -m pytest features -q                  # 70 tests, no API key needed
python -m features.gullak.tests.test_gullak   # printed pass/fail table
python -m features.wapas_aao.tests.test_wapas
python -m features.platform.tests.test_platform
```

## Layout
- `app.py` - phone shell: top bar (merchant/platform switch, language), Aaj screen, bottom tabs
- `features/gullak/` - engine (all rules and maths), adapter, UI, prompt, mock data, tests
- `features/wapas_aao/` - engine, UI, prompt, mock data, tests
- `features/platform/` - 500-merchant mock generator, engine (reuses gullak/wapas_aao engines), console UI, tests
- `features/common/` - LLM JSON helper, Sarvam voice, shared styles (`ui_kit.py`, the one file to restyle)
