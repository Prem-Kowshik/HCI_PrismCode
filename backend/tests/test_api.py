import os
import tempfile
import unittest

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_PATH"] = _tmp_db.name
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.database import init_db  # noqa: E402
from backend.app.main import app  # noqa: E402


class TestHCIVerifyAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(_tmp_db.name):
            os.remove(_tmp_db.name)

    def test_health_llm_test_and_frontend(self) -> None:
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

        llm_test = self.client.get("/api/llm/test")
        self.assertEqual(llm_test.status_code, 200)
        self.assertTrue(llm_test.json()["ok"])

        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("MakeAI-Verify", index.text)

    def test_core_study_warmup_edge_cases_debrief_and_systems(self) -> None:
        # Check core tasks are realistic (>= 25 lines each)
        core = self.client.get("/api/tasks/validated").json()
        self.assertEqual(len(core), 6)
        for t in core:
            self.assertGreaterEqual(len(t["code"].splitlines()), 25, t["id"])

        p_resp = self.client.post(
            "/api/participants",
            json={
                "consent_given": True,
                "programming_experience": "1-2 years",
                "cpp_familiarity": 3,
                "ai_tool_frequency": "Weekly",
            },
        )
        self.assertEqual(p_resp.status_code, 200)
        pid = p_resp.json()["participant_id"]

        plan = self.client.get(f"/api/study/{pid}/plan").json()
        self.assertIn("warmup_task", plan)
        self.assertEqual(len(plan["blocks"]), 3)

        first_block = plan["blocks"][0]
        first_task = first_block["tasks"][0]
        r_resp = self.client.post(
            "/api/responses",
            json={
                "participant_id": pid,
                "task_id": first_task["id"],
                "condition": first_block["condition"],
                "order_index": 0,
                "user_verdict": "incorrect",
                "suspected_error_line": 13,
                "suspected_error_description": "Unsigned underflow",
                "confidence": 4,
                "time_taken_ms": 22500,
                "checklist_checked": [0, 1],
                "edge_cases_checked": [0, 2],
                "expanded_hints_count": 1,
            },
        )
        self.assertEqual(r_resp.status_code, 200)
        self.assertEqual(r_resp.json()["task_set"], "core")

        rat_resp = self.client.post(
            "/api/ratings",
            json={
                "participant_id": pid,
                "condition": first_block["condition"],
                "task_set": "core",
                "mental_demand": 4,
                "effort": 4,
                "frustration": 2,
                "helpfulness": 6,
                "distraction": 2,
                "overall_usability": 6,
                "useful_features": "Clickable edge cases",
                "confusing_features": "",
                "comments": "",
            },
        )
        self.assertEqual(rat_resp.status_code, 200)

        debrief = self.client.get(f"/api/study/{pid}/debrief")
        self.assertEqual(debrief.status_code, 200)
        self.assertEqual(debrief.json()["total_tasks"], 1)

        csv_resp = self.client.get("/api/export/csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("edge_cases_checked_count", csv_resp.text)

    def test_custom_tasks_and_llm_endpoints(self) -> None:
        c_resp = self.client.post(
            "/api/tasks/custom",
            json={
                "title": "Custom Bounds Check",
                "difficulty": "Medium",
                "problem_statement": "Check index bounds",
                "code": "bool inBounds(int i, int n) {\n  return i >= 0 && i < n;\n}",
                "ground_truth_correct": True,
                "is_active": True,
            },
        )
        self.assertEqual(c_resp.status_code, 200)
        cid = c_resp.json()["id"]

        listed = self.client.get("/api/tasks/custom").json()
        self.assertTrue(any(t["id"] == cid for t in listed))

        solve_resp = self.client.post(
            "/api/llm/solve",
            json={
                "problem_statement": "Write a C++ function to reverse a string.",
                "language": "C++",
                "preferred_interface": "explanation",
            },
        )
        self.assertEqual(solve_resp.status_code, 200)
        self.assertIn("explanation_notes", solve_resp.json())


if __name__ == "__main__":
    unittest.main()
