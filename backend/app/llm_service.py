"""
LLM Calling Service for generating non-spoiling Explanation-Based and Verification-Guided
verification aids, generating new C/C++ study tasks, and solving user-provided problems.

Supports:
- Google Gemini API (LLM_PROVIDER=gemini, GEMINI_API_KEY via x-goog-api-key header)
- OpenAI-compatible API (LLM_PROVIDER=openai, OPENAI_API_KEY, OPENAI_BASE_URL)
- Deterministic local fallback (LLM_PROVIDER=mock, or when no API key is configured)
"""

import json
import os
import re
import time
from typing import Any, Dict
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


ANALYZE_SYSTEM_PROMPT = """You are an HCI research assistant building verification interfaces for AI-generated C++ code.
Given a programming problem and a C++ code snippet, generate TWO sets of verification aids in strict JSON:
1. "explanation_notes": 2 to 4 short line-anchored notes describing purpose, logic, and key assumptions.
2. "verification_guided":
   - "assumptions": 2 short bullet strings stating implicit or explicit assumptions in the code.
   - "suggested_edge_cases": 3 concise input test cases the user should mentally trace (do NOT state whether the code fails them).
   - "attention_lines": list of 1-based integer line numbers that deserve closer inspection.
   - "checklist": 3 short, actionable verification questions/steps.
   - "expandable_hints": 1 to 2 objects with {"line": int, "label": str, "detail": str}.

CRITICAL HCI RULE: Never reveal whether the code is correct or buggy, and never give away the bug directly. Support human inspection without spoiling the verdict.

Return ONLY valid JSON matching this schema:
{
  "explanation_notes": [{"line": 1, "title": "...", "text": "..."}],
  "verification_guided": {
    "assumptions": ["..."],
    "suggested_edge_cases": ["..."],
    "attention_lines": [1, 2],
    "checklist": ["..."],
    "expandable_hints": [{"line": 1, "label": "...", "detail": "..."}]
  }
}"""

GENERATE_TASK_SYSTEM_PROMPT = """You are an HCI study designer creating realistic C++ programming verification tasks (30 to 55 lines).
Create a realistic, non-trivial C++ function or small class for the requested topic and difficulty.
If should_contain_bug is true, introduce ONE subtle, realistic logical or edge-case bug (e.g., stale state, off-by-one boundary, missing post-loop flush, integer overflow, or tie-breaking flaw) while keeping the code clean and convincing.
If should_contain_bug is false, write a completely correct C++ solution.

Also generate non-spoiling "explanation_notes" and "verification_guided" aids (following the strict rule: NEVER reveal whether the code is correct or buggy in the aids).

Return ONLY valid JSON:
{
  "title": "...",
  "problem_statement": "...",
  "code": "...",
  "ground_truth_correct": true,
  "ground_truth_error_line": null,
  "ground_truth_error_description": null,
  "explanation_notes": [{"line": 1, "title": "...", "text": "..."}],
  "verification_guided": {
    "assumptions": ["..."],
    "suggested_edge_cases": ["..."],
    "attention_lines": [1],
    "checklist": ["..."],
    "expandable_hints": [{"line": 1, "label": "...", "detail": "..."}]
  }
}"""

SOLVE_PROBLEM_SYSTEM_PROMPT = """You are an AI coding assistant inside a verification-aware IDE.
Given a user's programming problem, write a clean, idiomatic C/C++ solution AND generate both:
1. "explanation_notes": 2 to 4 short line-anchored notes describing purpose, logic, and key assumptions.
2. "verification_guided":
   - "assumptions": 2 short bullet strings stating implicit or explicit assumptions.
   - "suggested_edge_cases": 3 concise input test cases the user should verify.
   - "attention_lines": list of 1-based integer line numbers that deserve closer inspection.
   - "checklist": 3 short, actionable verification steps.
   - "expandable_hints": 1 to 2 objects with {"line": int, "label": str, "detail": str}.

Return ONLY valid JSON:
{
  "title": "...",
  "code": "...",
  "explanation_notes": [{"line": 1, "title": "...", "text": "..."}],
  "verification_guided": {
    "assumptions": ["..."],
    "suggested_edge_cases": ["..."],
    "attention_lines": [1],
    "checklist": ["..."],
    "expandable_hints": [{"line": 1, "label": "...", "detail": "..."}]
  }
}"""


def get_llm_status() -> Dict[str, Any]:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not provider:
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            provider = "gemini"
        elif openai_key and openai_key != "your_openai_api_key_here":
            provider = "openai"
        else:
            provider = "mock"

    model = "mock-heuristic-v1"
    configured = True
    if provider == "gemini":
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        configured = bool(gemini_key and gemini_key != "your_gemini_api_key_here")
    elif provider == "openai":
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        configured = bool(openai_key and openai_key != "your_openai_api_key_here")

    return {
        "provider": provider if configured else "mock",
        "configured_provider": provider,
        "model": model if configured else "mock-heuristic-v1",
        "live_llm_enabled": configured and provider in ("gemini", "openai"),
    }


def _extract_json(raw_text: str) -> Dict[str, Any]:
    cleaned = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    return json.loads(cleaned)


async def _call_gemini(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    api_key = os.environ["GEMINI_API_KEY"].strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini API HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response structure: {json.dumps(data)[:300]}") from exc
    return _extract_json(text)


async def _call_openai(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    api_key = os.environ["OPENAI_API_KEY"].strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI API HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

    text = data["choices"][0]["message"]["content"]
    return _extract_json(text)


def _heuristic_analyze_code(problem_statement: str, code: str) -> Dict[str, Any]:
    lines = code.splitlines()
    attention_lines = []
    notes = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if any(kw in stripped for kw in ("for ", "while ", "if ", "return ", "/", "=")):
            if len(attention_lines) < 4 and idx > 1:
                attention_lines.append(idx)
        if idx == 2 and stripped:
            notes.append({
                "line": idx,
                "title": "Initial State",
                "text": f"Sets up initial state or guard condition: `{stripped[:60]}`.",
            })
        elif ("for " in stripped or "while " in stripped) and len(notes) < 3:
            notes.append({
                "line": idx,
                "title": "Loop Control",
                "text": "Iterates over the input range; check boundary conditions and termination.",
            })
        elif stripped.startswith("return ") and len(notes) < 4:
            notes.append({
                "line": idx,
                "title": "Return Expression",
                "text": f"Produces the final function output via `{stripped[:60]}`.",
            })

    if not notes:
        notes.append({
            "line": 1,
            "title": "Function Signature",
            "text": "Defines input types and return type for the requested problem.",
        })
    if not attention_lines:
        attention_lines = [min(2, len(lines))]

    return {
        "explanation_notes": notes,
        "verification_guided": {
            "assumptions": [
                "Assumes input values fit within standard C++ integer/container bounds.",
                "Assumes caller respects any preconditions in the problem statement.",
            ],
            "suggested_edge_cases": [
                "Empty or minimum-size input (e.g., size 0 or 1)",
                "Boundary values (zero, negative, or maximum limits)",
                "Duplicate or consecutive identical elements",
            ],
            "attention_lines": attention_lines,
            "checklist": [
                "Check variable initialization and state resets.",
                "Verify loop bounds (`<` vs `<=`) and post-loop cleanup.",
                "Check arithmetic types for integer division or overflow.",
            ],
            "expandable_hints": [
                {
                    "line": attention_lines[0],
                    "label": "Trace boundary behavior",
                    "detail": "Walk through the highlighted line using an empty, single-element, or boundary input.",
                }
            ],
        },
    }


def _heuristic_generate_task(topic: str, difficulty: str, should_contain_bug: bool) -> Dict[str, Any]:
    if should_contain_bug:
        code = (
            "int countAboveThreshold(const std::vector<int>& nums, int threshold) {\n"
            "    int count = 0;\n"
            "    for (size_t i = 1; i < nums.size(); i++) {\n"
            "        if (nums[i] > threshold) {\n"
            "            count++;\n"
            "        }\n"
            "    }\n"
            "    return count;\n"
            "}"
        )
        return {
            "title": f"{topic} — Threshold Counter ({difficulty})",
            "problem_statement": (
                "Write a C++ function `int countAboveThreshold(const std::vector<int>& nums, int threshold)` "
                "that returns how many elements in `nums` are strictly greater than `threshold`."
            ),
            "code": code,
            "ground_truth_correct": False,
            "ground_truth_error_line": 3,
            "ground_truth_error_description": "Loop starts at `i = 1` instead of `i = 0`, skipping `nums[0]`.",
            **_heuristic_analyze_code("Count elements above threshold", code),
        }
    code = (
        "int countAboveThreshold(const std::vector<int>& nums, int threshold) {\n"
        "    int count = 0;\n"
        "    for (size_t i = 0; i < nums.size(); i++) {\n"
        "        if (nums[i] > threshold) {\n"
        "            count++;\n"
        "        }\n"
        "    }\n"
        "    return count;\n"
        "}"
    )
    return {
        "title": f"{topic} — Threshold Counter ({difficulty})",
        "problem_statement": (
            "Write a C++ function `int countAboveThreshold(const std::vector<int>& nums, int threshold)` "
            "that returns how many elements in `nums` are strictly greater than `threshold`."
        ),
        "code": code,
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        **_heuristic_analyze_code("Count elements above threshold", code),
    }


def _heuristic_solve_problem(problem_statement: str, language: str) -> Dict[str, Any]:
    lower = problem_statement.lower()
    if "reverse" in lower or "string" in lower:
        title = "Reverse String Helper"
        code = (
            "std::string reverseString(std::string s) {\n"
            "    int left = 0;\n"
            "    int right = static_cast<int>(s.size()) - 1;\n"
            "    while (left < right) {\n"
            "        std::swap(s[left], s[right]);\n"
            "        left++;\n"
            "        right--;\n"
            "    }\n"
            "    return s;\n"
            "}"
        )
    elif "factorial" in lower:
        title = "Iterative Factorial"
        code = (
            "long long factorial(int n) {\n"
            "    if (n < 0) return -1;\n"
            "    long long result = 1;\n"
            "    for (int i = 2; i <= n; i++) {\n"
            "        result *= i;\n"
            "    }\n"
            "    return result;\n"
            "}"
        )
    else:
        title = f"AI-Generated {language} Solution"
        code = (
            "// Mock fallback solution (set GEMINI_API_KEY or OPENAI_API_KEY in .env for live generation)\n"
            "int solveVectorSum(const std::vector<int>& nums) {\n"
            "    int total = 0;\n"
            "    for (int val : nums) {\n"
            "        total += val;\n"
            "    }\n"
            "    return total;\n"
            "}"
        )

    return {
        "title": title,
        "problem_statement": problem_statement,
        "code": code,
        **_heuristic_analyze_code(problem_statement, code),
    }


async def test_llm_connection() -> Dict[str, Any]:
    status = get_llm_status()
    provider = status["provider"]
    t0 = time.perf_counter()
    if provider == "mock":
        return {
            "ok": True,
            "provider": "mock",
            "model": status["model"],
            "latency_ms": 1,
            "message": "Running in local mock fallback mode (no live API key configured).",
        }

    test_prompt = 'Return JSON: {"ok": true, "ping": "pong"}'
    try:
        if provider == "gemini":
            res = await _call_gemini("Respond with valid JSON only.", test_prompt)
        else:
            res = await _call_openai("Respond with valid JSON only.", test_prompt)
        latency = round((time.perf_counter() - t0) * 1000)
        return {
            "ok": True,
            "provider": provider,
            "model": status["model"],
            "latency_ms": latency,
            "message": f"Connected to {provider} ({status['model']}) in {latency}ms. Response: {res}",
        }
    except Exception as exc:
        latency = round((time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "provider": provider,
            "model": status["model"],
            "latency_ms": latency,
            "message": str(exc),
        }


async def analyze_code_with_llm(problem_statement: str, code: str) -> Dict[str, Any]:
    status = get_llm_status()
    provider = status["provider"]
    user_prompt = f"Problem Statement:\n{problem_statement}\n\nC++ Code:\n```cpp\n{code}\n```"

    if provider == "gemini":
        result = await _call_gemini(ANALYZE_SYSTEM_PROMPT, user_prompt)
    elif provider == "openai":
        result = await _call_openai(ANALYZE_SYSTEM_PROMPT, user_prompt)
    else:
        result = _heuristic_analyze_code(problem_statement, code)

    result["llm_provider_used"] = provider
    return result


async def generate_task_with_llm(topic: str, difficulty: str, should_contain_bug: bool) -> Dict[str, Any]:
    status = get_llm_status()
    provider = status["provider"]
    user_prompt = (
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}\n"
        f"should_contain_bug: {str(should_contain_bug).lower()}"
    )

    if provider == "gemini":
        result = await _call_gemini(GENERATE_TASK_SYSTEM_PROMPT, user_prompt)
    elif provider == "openai":
        result = await _call_openai(GENERATE_TASK_SYSTEM_PROMPT, user_prompt)
    else:
        result = _heuristic_generate_task(topic, difficulty, should_contain_bug)

    result["llm_provider_used"] = provider
    return result


async def solve_problem_with_llm(problem_statement: str, language: str = "C++") -> Dict[str, Any]:
    status = get_llm_status()
    provider = status["provider"]
    user_prompt = f"Language: {language}\nProblem Statement:\n{problem_statement}"

    if provider == "gemini":
        result = await _call_gemini(SOLVE_PROBLEM_SYSTEM_PROMPT, user_prompt)
        result["problem_statement"] = problem_statement
    elif provider == "openai":
        result = await _call_openai(SOLVE_PROBLEM_SYSTEM_PROMPT, user_prompt)
        result["problem_statement"] = problem_statement
    else:
        result = _heuristic_solve_problem(problem_statement, language)

    result["llm_provider_used"] = provider
    return result
