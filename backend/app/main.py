import csv
import io
import json
import os
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .database import get_db, init_db
from .llm_service import (
    _heuristic_analyze_code,
    analyze_code_with_llm,
    generate_task_with_llm,
    get_llm_status,
    solve_problem_with_llm,
    test_llm_connection,
)
from .schemas import (
    AnalyzeCodeRequest,
    ConditionRatingCreate,
    CustomTaskCreate,
    GenerateTaskRequest,
    ParticipantCreate,
    SolveProblemRequest,
    TaskResponseCreate,
)
from .tasks_seed import SYSTEMS_COMPLEX_TASKS, VALIDATED_TASKS, WARMUP_TASK

CONDITIONS = ["standard", "explanation", "verification_guided"]
LATIN_SQUARE_ORDERS = [
    ["standard", "explanation", "verification_guided"],
    ["explanation", "verification_guided", "standard"],
    ["verification_guided", "standard", "explanation"],
]

ALL_SEEDED_TASKS = [WARMUP_TASK] + VALIDATED_TASKS + SYSTEMS_COMPLEX_TASKS
TASK_MAP = {t["id"]: t for t in ALL_SEEDED_TASKS}

app = FastAPI(
    title="MakeAI-Verify: HCI Code Verification Prototype",
    description="Interactive prototype and study platform for comparing Standard, Explanation-Based, and Verification-Guided AI code interfaces.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lookup_task(task_id: str) -> Dict[str, Any] | None:
    if task_id in TASK_MAP:
        return TASK_MAP[task_id]
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM generated_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "difficulty": row["difficulty"],
            "task_set": "custom",
            "problem_statement": row["problem_statement"],
            "code": row["code"],
            "ground_truth_correct": bool(row["ground_truth_correct"]) if row["ground_truth_correct"] is not None else True,
            "ground_truth_error_line": row["ground_truth_error_line"],
            "ground_truth_error_description": row["ground_truth_error_description"],
            "explanation_notes": json.loads(row["explanation_notes"]),
            "verification_guided": json.loads(row["verification_guided"]),
        }


def _sanitize_task_for_condition(task: Dict[str, Any], condition: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": task["id"],
        "title": task["title"],
        "difficulty": task["difficulty"],
        "task_set": task.get("task_set", "core"),
        "problem_statement": task["problem_statement"],
        "code": task["code"],
        "condition": condition,
    }
    if condition == "explanation":
        payload["explanation_notes"] = task["explanation_notes"]
    elif condition == "verification_guided":
        payload["verification_guided"] = task["verification_guided"]
    return payload


def _compute_condition_stats(responses: List[Dict[str, Any]], ratings: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_condition: Dict[str, Any] = {}
    for cond in CONDITIONS:
        c_resps = [r for r in responses if r["condition"] == cond]
        c_rats = [r for r in ratings if r["condition"] == cond]

        buggy_resps = [r for r in c_resps if r["ground_truth_correct"] == 0]
        correct_resps = [r for r in c_resps if r["ground_truth_correct"] == 1]

        acc = round(100 * sum(r["is_accurate"] for r in c_resps) / len(c_resps), 1) if c_resps else 0.0
        err_det = round(100 * sum(r["error_detected"] for r in buggy_resps) / len(buggy_resps), 1) if buggy_resps else 0.0
        false_rej = round(100 * sum(r["false_rejection"] for r in correct_resps) / len(correct_resps), 1) if correct_resps else 0.0
        avg_time_s = round(statistics.mean(r["time_taken_ms"] for r in c_resps) / 1000.0, 2) if c_resps else 0.0
        avg_conf = round(statistics.mean(r["confidence"] for r in c_resps), 2) if c_resps else 0.0

        if c_rats:
            avg_workload = round(
                statistics.mean((r["mental_demand"] + r["effort"] + r["frustration"]) / 3.0 for r in c_rats), 2
            )
            avg_usability = round(statistics.mean(r["overall_usability"] for r in c_rats), 2)
            avg_helpfulness = round(statistics.mean(r["helpfulness"] for r in c_rats), 2)
        else:
            avg_workload = avg_usability = avg_helpfulness = 0.0

        by_condition[cond] = {
            "n_responses": len(c_resps),
            "n_ratings": len(c_rats),
            "accuracy_pct": acc,
            "error_detection_pct": err_det,
            "false_rejection_pct": false_rej,
            "avg_time_sec": avg_time_s,
            "avg_confidence": avg_conf,
            "avg_workload": avg_workload,
            "avg_usability": avg_usability,
            "avg_helpfulness": avg_helpfulness,
        }
    return by_condition


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {"status": "ok", "llm": get_llm_status()}


@app.get("/api/llm/test")
async def llm_connection_test() -> Dict[str, Any]:
    return await test_llm_connection()


@app.get("/api/tasks/validated")
def list_validated_tasks() -> List[Dict[str, Any]]:
    return VALIDATED_TASKS


@app.get("/api/tasks/systems")
def list_systems_tasks(condition: str = "verification_guided") -> List[Dict[str, Any]]:
    if condition not in CONDITIONS:
        raise HTTPException(status_code=400, detail="Invalid condition")
    return [_sanitize_task_for_condition(t, condition) for t in SYSTEMS_COMPLEX_TASKS]


@app.get("/api/tasks/custom")
def list_custom_tasks() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM generated_tasks ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "difficulty": r["difficulty"],
            "problem_statement": r["problem_statement"],
            "code": r["code"],
            "ground_truth_correct": bool(r["ground_truth_correct"]) if r["ground_truth_correct"] is not None else True,
            "ground_truth_error_line": r["ground_truth_error_line"],
            "ground_truth_error_description": r["ground_truth_error_description"],
            "explanation_notes": json.loads(r["explanation_notes"]),
            "verification_guided": json.loads(r["verification_guided"]),
            "llm_provider": r["llm_provider"],
            "is_active": bool(r["is_active"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/api/tasks/custom")
def create_custom_task(body: CustomTaskCreate) -> Dict[str, Any]:
    task_id = f"cust_{uuid.uuid4().hex[:8]}"
    aids = _heuristic_analyze_code(body.problem_statement, body.code)
    exp_notes = body.explanation_notes if body.explanation_notes is not None else aids["explanation_notes"]
    vg_data = body.verification_guided if body.verification_guided is not None else aids["verification_guided"]

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO generated_tasks (
                id, title, difficulty, problem_statement, code,
                ground_truth_correct, ground_truth_error_line, ground_truth_error_description,
                explanation_notes, verification_guided, llm_provider, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                body.title,
                body.difficulty,
                body.problem_statement,
                body.code,
                1 if body.ground_truth_correct else 0,
                body.ground_truth_error_line,
                body.ground_truth_error_description,
                json.dumps(exp_notes),
                json.dumps(vg_data),
                "manual",
                1 if body.is_active else 0,
                _utc_now(),
            ),
        )
    return {"id": task_id, "status": "created", "is_active": body.is_active}


@app.patch("/api/tasks/custom/{task_id}/toggle")
def toggle_custom_task(task_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT is_active FROM generated_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Custom task not found")
        new_val = 0 if row["is_active"] else 1
        conn.execute(
            "UPDATE generated_tasks SET is_active = ? WHERE id = ?", (new_val, task_id)
        )
    return {"id": task_id, "is_active": bool(new_val)}


@app.delete("/api/tasks/custom/{task_id}")
def delete_custom_task(task_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM generated_tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Custom task not found")
    return {"id": task_id, "status": "deleted"}


@app.post("/api/participants")
def create_participant(body: ParticipantCreate) -> Dict[str, Any]:
    if not body.consent_given:
        raise HTTPException(status_code=400, detail="Informed consent is required to participate.")

    participant_id = f"P-{uuid.uuid4().hex[:8].upper()}"

    with get_db() as conn:
        count_row = conn.execute("SELECT COUNT(*) AS cnt FROM participants").fetchone()
        idx = count_row["cnt"] if count_row else 0
        condition_order = LATIN_SQUARE_ORDERS[idx % len(LATIN_SQUARE_ORDERS)]

        pair_groups = ["A", "B", "C"]
        rotated_groups = pair_groups[idx % 3 :] + pair_groups[: idx % 3]
        assignment = {}
        for cond, grp in zip(condition_order, rotated_groups):
            assignment[cond] = [t["id"] for t in VALIDATED_TASKS if t["pair_group"] == grp]

        conn.execute(
            """
            INSERT INTO participants (
                id, created_at, consent_given, programming_experience,
                cpp_familiarity, ai_tool_frequency, condition_order, task_assignment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                participant_id,
                _utc_now(),
                1 if body.consent_given else 0,
                body.programming_experience,
                body.cpp_familiarity,
                body.ai_tool_frequency,
                json.dumps(condition_order),
                json.dumps(assignment),
            ),
        )

    return {
        "participant_id": participant_id,
        "condition_order": condition_order,
        "task_assignment": assignment,
    }


@app.get("/api/study/{participant_id}/plan")
def get_study_plan(participant_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE id = ?", (participant_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Participant not found")

    condition_order = json.loads(row["condition_order"])
    assignment = json.loads(row["task_assignment"])

    blocks = []
    for cond in condition_order:
        tasks = [
            _sanitize_task_for_condition(TASK_MAP[tid], cond)
            for tid in assignment[cond]
            if tid in TASK_MAP
        ]
        blocks.append({"condition": cond, "tasks": tasks})

    return {
        "participant_id": participant_id,
        "warmup_task": _sanitize_task_for_condition(WARMUP_TASK, "verification_guided"),
        "condition_order": condition_order,
        "blocks": blocks,
    }


@app.get("/api/study/{participant_id}/systems-plan")
def get_systems_plan(participant_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE id = ?", (participant_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Participant not found")
        p_idx = conn.execute(
            "SELECT COUNT(*) AS cnt FROM participants WHERE created_at <= ?",
            (row["created_at"],),
        ).fetchone()["cnt"]

    condition_order = json.loads(row["condition_order"])
    offset = (p_idx - 1) % len(SYSTEMS_COMPLEX_TASKS)
    rotated_tasks = SYSTEMS_COMPLEX_TASKS[offset:] + SYSTEMS_COMPLEX_TASKS[:offset]

    blocks = [
        {"condition": cond, "tasks": [_sanitize_task_for_condition(task, cond)]}
        for cond, task in zip(condition_order, rotated_tasks)
    ]

    return {
        "participant_id": participant_id,
        "condition_order": condition_order,
        "blocks": blocks,
    }


@app.get("/api/study/{participant_id}/debrief")
def get_participant_debrief(participant_id: str) -> Dict[str, Any]:
    """Post-study debrief showing the participant's score and ground-truth bug explanations."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM task_responses WHERE participant_id = ? ORDER BY created_at ASC",
            (participant_id,),
        ).fetchall()

    items = []
    for r in rows:
        task = _lookup_task(r["task_id"])
        if not task:
            continue
        items.append(
            {
                "task_id": r["task_id"],
                "title": task["title"],
                "condition": r["condition"],
                "user_verdict": r["user_verdict"],
                "is_accurate": bool(r["is_accurate"]),
                "ground_truth_correct": bool(task["ground_truth_correct"]),
                "ground_truth_error_line": task.get("ground_truth_error_line"),
                "ground_truth_error_description": task.get("ground_truth_error_description"),
                "time_taken_sec": round(r["time_taken_ms"] / 1000.0, 1),
            }
        )

    total = len(items)
    correct_count = sum(1 for x in items if x["is_accurate"])
    return {
        "participant_id": participant_id,
        "total_tasks": total,
        "accurate_count": correct_count,
        "accuracy_pct": round(100 * correct_count / total, 1) if total else 0.0,
        "items": items,
    }


@app.post("/api/responses")
def submit_task_response(body: TaskResponseCreate) -> Dict[str, Any]:
    task = _lookup_task(body.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    gt_correct = bool(task["ground_truth_correct"])
    user_says_correct = body.user_verdict == "correct"

    is_accurate = 1 if (user_says_correct == gt_correct) else 0
    error_detected = 1 if (not gt_correct and not user_says_correct) else 0
    false_rejection = 1 if (gt_correct and not user_says_correct) else 0

    with get_db() as conn:
        p = conn.execute(
            "SELECT id FROM participants WHERE id = ?", (body.participant_id,)
        ).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Participant not found")

        conn.execute(
            """
            INSERT INTO task_responses (
                participant_id, task_id, condition, order_index, user_verdict,
                suspected_error_line, suspected_error_description, confidence,
                time_taken_ms, checklist_checked, edge_cases_checked, expanded_hints_count,
                ground_truth_correct, is_accurate, error_detected, false_rejection, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.participant_id,
                body.task_id,
                body.condition,
                body.order_index,
                body.user_verdict,
                body.suspected_error_line,
                body.suspected_error_description,
                body.confidence,
                body.time_taken_ms,
                json.dumps(body.checklist_checked),
                json.dumps(body.edge_cases_checked),
                body.expanded_hints_count,
                1 if gt_correct else 0,
                is_accurate,
                error_detected,
                false_rejection,
                _utc_now(),
            ),
        )

    return {
        "status": "recorded",
        "is_accurate": bool(is_accurate),
        "task_set": task.get("task_set", "core"),
    }


@app.post("/api/ratings")
def submit_condition_rating(body: ConditionRatingCreate) -> Dict[str, Any]:
    with get_db() as conn:
        p = conn.execute(
            "SELECT id FROM participants WHERE id = ?", (body.participant_id,)
        ).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Participant not found")

        conn.execute(
            """
            INSERT INTO condition_ratings (
                participant_id, condition, task_set, mental_demand, effort, frustration,
                helpfulness, distraction, overall_usability,
                useful_features, confusing_features, comments, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.participant_id,
                body.condition,
                body.task_set,
                body.mental_demand,
                body.effort,
                body.frustration,
                body.helpfulness,
                body.distraction,
                body.overall_usability,
                body.useful_features,
                body.confusing_features,
                body.comments,
                _utc_now(),
            ),
        )

    return {"status": "recorded"}


@app.get("/api/analytics/summary")
def get_analytics_summary() -> Dict[str, Any]:
    with get_db() as conn:
        p_count = conn.execute("SELECT COUNT(*) AS cnt FROM participants").fetchone()["cnt"]
        responses = [dict(r) for r in conn.execute("SELECT * FROM task_responses").fetchall()]
        ratings = [dict(r) for r in conn.execute("SELECT * FROM condition_ratings").fetchall()]

    core_ids = {t["id"] for t in VALIDATED_TASKS}
    core_responses = [r for r in responses if r["task_id"] in core_ids]
    sys_responses = [r for r in responses if r["task_id"] not in core_ids]

    core_ratings = [r for r in ratings if r.get("task_set", "core") == "core"]
    sys_ratings = [r for r in ratings if r.get("task_set") == "systems_challenge"]

    return {
        "total_participants": p_count,
        "total_responses": len(responses),
        "core_responses": len(core_responses),
        "systems_responses": len(sys_responses),
        "conditions": _compute_condition_stats(core_responses, core_ratings),
        "systems_conditions": _compute_condition_stats(sys_responses, sys_ratings),
        "qualitative_feedback": [
            {
                "participant_id": r["participant_id"],
                "condition": r["condition"],
                "task_set": r.get("task_set", "core"),
                "useful_features": r["useful_features"],
                "confusing_features": r["confusing_features"],
                "comments": r["comments"],
            }
            for r in ratings
            if r["useful_features"] or r["confusing_features"] or r["comments"]
        ],
    }


@app.get("/api/export/csv")
def export_csv() -> StreamingResponse:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                tr.participant_id,
                p.programming_experience,
                p.cpp_familiarity,
                p.ai_tool_frequency,
                tr.condition,
                tr.order_index,
                tr.task_id,
                tr.user_verdict,
                tr.suspected_error_line,
                tr.suspected_error_description,
                tr.confidence,
                tr.time_taken_ms,
                tr.checklist_checked,
                tr.edge_cases_checked,
                tr.expanded_hints_count,
                tr.ground_truth_correct,
                tr.is_accurate,
                tr.error_detected,
                tr.false_rejection,
                tr.created_at
            FROM task_responses tr
            JOIN participants p ON p.id = tr.participant_id
            ORDER BY tr.created_at ASC
            """
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        "participant_id",
        "programming_experience",
        "cpp_familiarity",
        "ai_tool_frequency",
        "condition",
        "order_index",
        "task_id",
        "task_set",
        "user_verdict",
        "suspected_error_line",
        "suspected_error_description",
        "confidence",
        "time_taken_ms",
        "checklist_checked_count",
        "edge_cases_checked_count",
        "expanded_hints_count",
        "ground_truth_correct",
        "is_accurate",
        "error_detected",
        "false_rejection",
        "created_at",
    ]
    writer.writerow(headers)
    for row in rows:
        t_meta = TASK_MAP.get(row["task_id"], {})
        task_set = t_meta.get("task_set", "core")
        chk_cnt = len(json.loads(row["checklist_checked"] or "[]"))
        ec_cnt = len(json.loads(row["edge_cases_checked"] or "[]"))
        writer.writerow(
            [
                task_set if h == "task_set"
                else chk_cnt if h == "checklist_checked_count"
                else ec_cnt if h == "edge_cases_checked_count"
                else row[h]
                for h in headers
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hci_study_responses.csv"},
    )


@app.post("/api/llm/analyze-code")
async def llm_analyze_code(body: AnalyzeCodeRequest) -> Dict[str, Any]:
    try:
        result = await analyze_code_with_llm(body.problem_statement, body.code)
        task_id = f"gen_{uuid.uuid4().hex[:8]}"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO generated_tasks (
                    id, title, difficulty, problem_statement, code, explanation_notes,
                    verification_guided, llm_provider, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    body.title,
                    "Medium",
                    body.problem_statement,
                    body.code,
                    json.dumps(result["explanation_notes"]),
                    json.dumps(result["verification_guided"]),
                    result["llm_provider_used"],
                    0,
                    _utc_now(),
                ),
            )
        result["id"] = task_id
        result["title"] = body.title
        result["problem_statement"] = body.problem_statement
        result["code"] = body.code
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {exc}") from exc


@app.post("/api/llm/generate-task")
async def llm_generate_task(body: GenerateTaskRequest) -> Dict[str, Any]:
    try:
        result = await generate_task_with_llm(
            body.topic, body.difficulty, body.should_contain_bug
        )
        task_id = f"gen_{uuid.uuid4().hex[:8]}"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO generated_tasks (
                    id, title, difficulty, problem_statement, code, ground_truth_correct,
                    ground_truth_error_line, ground_truth_error_description,
                    explanation_notes, verification_guided, llm_provider, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    result["title"],
                    body.difficulty,
                    result["problem_statement"],
                    result["code"],
                    1 if result.get("ground_truth_correct") else 0,
                    result.get("ground_truth_error_line"),
                    result.get("ground_truth_error_description"),
                    json.dumps(result["explanation_notes"]),
                    json.dumps(result["verification_guided"]),
                    result["llm_provider_used"],
                    1,
                    _utc_now(),
                ),
            )
        result["id"] = task_id
        result["difficulty"] = body.difficulty
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM task generation failed: {exc}") from exc


@app.post("/api/llm/solve")
async def llm_solve_problem(body: SolveProblemRequest) -> Dict[str, Any]:
    try:
        result = await solve_problem_with_llm(body.problem_statement, body.language)
        result["preferred_interface"] = body.preferred_interface
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM problem solving failed: {exc}") from exc


FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
