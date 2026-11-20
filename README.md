# MakeAI-Verify: Making AI-Generated Code Easier to Verify

An interactive full-stack HCI research prototype comparing three interface designs for verifying AI-generated C/C++ code:

1. **Standard Interface**: Problem statement and syntax-highlighted C++ code only.
2. **Explanation-Based Interface**: Line-anchored notes describing purpose, logic, and key assumptions.
3. **Verification-Guided Interface**: Lightweight verification support (visible assumptions, suggested edge cases, attention line highlights, interactive checklist, and optional expandable hints) without spoiling the correctness verdict.

Also includes:
- **AI Code Playground**: General-use mode where users enter any coding problem, pick their preferred interface, and get an AI-generated solution + aids.
- **Systems & 100+ Line Challenge**: Optional counterbalanced Part 2 with systems-level C++ tasks (Ring Buffer, Packet Parser, and a 108-line Slab Allocator).
- **Researcher Dashboard**: Live descriptive stats for Core Study and Systems Challenge, plus one-click CSV export (`/api/export/csv`).

## Local Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure LLM Calling (Optional)**:
   Copy `.env.example` to `.env` and set either:
   - `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...`, or
   - `LLM_PROVIDER=openai` and `OPENAI_API_KEY=...`
   *(If no key is set, the app runs in `mock` heuristic mode out-of-the-box.)*

3. **Run locally**:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   Open `http://localhost:8000`.

4. **Run automated tests**:
   ```bash
   python3 -m unittest backend/tests/test_api.py -v
   ```

## Online Deployment (Phase 3)

### Option A: Render.com (Recommended — includes persistent disk)
1. Push this repository to GitHub.
2. On Render, click **New → Blueprint** and select this repo (`render.yaml` is already configured).
3. Add your `GEMINI_API_KEY` (or `OPENAI_API_KEY`) and set `LLM_PROVIDER=gemini` in the Render Environment tab.
4. `render.yaml` mounts a persistent disk at `/data` so `study_data.db` is preserved across redeploys.

### Option B: Docker / Railway / Fly.io
```bash
docker build -t makeai-verify .
docker run -p 8000:8000 -v $(pwd)/data:/data -e LLM_PROVIDER=mock makeai-verify
```
