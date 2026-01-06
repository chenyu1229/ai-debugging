# AI CI Triage (Complete Sample Project)

This is a **complete, runnable** mini-project that demonstrates an **AI-powered CI failure triage & decision system**:
- Runs pytest tests
- Collects raw failure output
- Produces **structured JSON decisions** (Retry / Block / Ticket)
- Saves **history** into SQLite
- Offers a **web dashboard** (FastAPI) to view runs and decisions
- Optional: uses an LLM (OpenAI) as the reasoning engine if `OPENAI_API_KEY` is set

> If you don't set `OPENAI_API_KEY`, it still works using deterministic rules.

---

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

---

## 2) Run the web dashboard

```bash
uvicorn server.main:app --reload
```

Open:
- http://127.0.0.1:8000

---

## 3) Trigger a test run + triage

From the UI:
- Click **Run tests now**

Or from CLI:

```bash
python -m triage.run_and_triage
```

---

## 4) Optional: enable LLM triage

Set your API key:

```bash
export OPENAI_API_KEY="YOUR_KEY"
```

The system will try LLM triage first, and fall back to rules if parsing fails.

---

## 5) Project structure

```
ai-ci-triage/
  app_under_test/          # intentionally buggy code + tests
  server/                  # FastAPI dashboard
  triage/                  # runner + collector + decision engine
  data/triage.db           # SQLite history (auto-created)
```

---

## 6) What makes this different from copy/pasting into ChatGPT?

- **Automation**: runs automatically (UI button / CLI / CI)
- **Structured output**: produces JSON decisions a pipeline can consume
- **Memory**: stores history, enabling flaky detection & trend analysis
- **Replaceable AI component**: rules vs LLM can be swapped and compared


## Flaky detection (v1)

The system stores per-run test lists and failed tests, then marks a test **flaky** if, within the last 30 runs, it has **both passes and failures** and appears in at least 3 runs. Visit `/flaky` in the dashboard.
