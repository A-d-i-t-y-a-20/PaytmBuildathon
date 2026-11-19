# Galla

A phone-first app for kirana owners with exactly two features. Concept demo, mock data: no real money or messages move.

| Tab | Feature | What it does |
|---|---|---|
| Aaj | Home | Today's UPI money plus one card per feature |
| Gullak | Galla Gullak | A small share of each day's UPI settlement goes to a savings pot. The amount follows sales and skips bad days (slow sales, EMI due with low cash, stock purchase coming). First 7 days it asks every evening; auto only after he agrees. |
| Grahak | Wapas Aao | Finds regular customers who stopped coming, suggests a priced offer, reaches only customers who agreed, and shows the result as profit after the offer's cost. |

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Optional secrets (env vars or `.streamlit/secrets.toml`): `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) for the AI, `SARVAM_API_KEY` for voice. Without them the app uses code fallbacks and typed input.

## Tests
```
python -m pytest features -q                  # 47 tests, no API key needed
python -m features.gullak.tests.test_gullak   # printed pass/fail table
python -m features.wapas_aao.tests.test_wapas
```

## Layout
- `app.py` - phone shell: top bar, Aaj screen, bottom tabs
- `features/gullak/` - engine (all rules and maths), adapter, UI, prompt, mock data, tests
- `features/wapas_aao/` - engine, UI, prompt, mock data, tests
- `features/common/` - LLM JSON helper, Sarvam voice, shared styles (`ui_kit.py`, the one file to restyle)
