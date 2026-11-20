# MakeAI-Verify: Making AI-Generated Code Easier to Verify

An interactive full-stack HCI research prototype comparing three interface designs for verifying AI-generated C/C++ code:

1. **Standard Interface**: Problem statement and AI-generated C++ code only.
2. **Explanation-Based Interface**: Line-anchored notes describing purpose, logic, and key assumptions.
3. **Verification-Guided Interface**: Lightweight verification support (visible assumptions, suggested edge cases, attention line highlights, interactive checklist, and optional expandable hints) without spoiling the correctness verdict.

## Project Structure

```
hci_verify_project/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI routes, Latin-square assignment, analytics, CSV export
│   │   ├── database.py      # SQLite schema & connection helper
│   │   ├── llm_service.py   # Gemini / OpenAI-compatible LLM calling + mock fallback
│   │   ├── schemas.py       # Pydantic request models
│   │   └── tasks_seed.py    # 6 validated C++ verification tasks with ground truth
│   └── tests/
│       └── test_api.py      # End-to-end API test suite
├── frontend/
│   ├── index.html           # Participant study flow & Researcher/LLM dashboard
│   ├── styles.css           # Clean responsive UI styles
│   └── app.js               # Timer, line-click selector, telemetry, analytics & LLM preview
├── requirements.txt
└── .env.example
```

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure LLM Calling (Optional)**:
   Copy `.env.example` to `.env` and set either:
   - `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...`, or
   - `LLM_PROVIDER=openai` and `OPENAI_API_KEY=...`
   *(If no key is set, the app automatically runs in `mock` heuristic mode so you can demo and test immediately.)*

3. **Run the server**:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   Open `http://localhost:8000` in your browser.

4. **Run automated tests**:
   ```bash
   python3 -m unittest backend/tests/test_api.py -v
   ```
