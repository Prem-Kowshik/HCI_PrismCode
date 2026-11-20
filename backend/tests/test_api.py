import os
import tempfile
import unittest

# Point database to an isolated temp file before importing app
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

    def test_health_and_frontend_served(self) -> None:
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("MakeAI-Verify", index.text)
        self.assertIn("AI Code Playground", index.text)

    def test_full_participant_study_flow_and_export(self) -> None:
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
        self.assertEqual(len(p_resp.json()["condition_order"]), 3)

        plan_resp = self.client.get(f"/api/study/{pid}/plan")
        self.assertEqual(plan_resp.status_code, 200)
        blocks = plan_resp.json()["blocks"]
        self.assertEqual(len(blocks), 3)

        first_block = blocks[0]
        first_task = first_block["tasks"][0]
        r_resp = self.client.post(
            "/api/responses",
            json={
                "participant_id": pid,
                "task_id": first_task["id"],
                "condition": first_block["condition"],
                "order_index": 0,
                "user_verdict": "incorrect",
                "suspected_error_line": 2,
                "suspected_error_description": "Fails on negative inputs",
                "confidence": 4,
                "time_taken_ms": 14500,
                "checklist_checked": [0, 1],
                "expanded_hints_count": 1,
            },
        )
        self.assertEqual(r_resp.status_code, 200)

        rat_resp = self.client.post(
            "/api/ratings",
            json={
                "participant_id": pid,
                "condition": first_block["condition"],
                "mental_demand": 3,
                "effort": 3,
                "frustration": 2,
                "helpfulness": 6,
                "distraction": 2,
                "overall_usability": 6,
                "useful_features": "Edge cases",
                "confusing_features": "",
                "comments": "Clean UI",
            },
        )
        self.assertEqual(rat_resp.status_code, 200)

        summary = self.client.get("/api/analytics/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertGreaterEqual(summary.json()["total_participants"], 1)

        csv_resp = self.client.get("/api/export/csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn(pid, csv_resp.text)

    def test_llm_analyze_generate_and_solve_mock(self) -> None:
        analyze_resp = self.client.post(
            "/api/llm/analyze-code",
            json={
                "title": "Sum Positive",
                "problem_statement": "Sum positive ints",
                "code": "int sumPos(vector<int> a) {\n  int s = 0;\n  for (int x : a) if (x > 0) s += x;\n  return s;\n}",
            },
        )
        self.assertEqual(analyze_resp.status_code, 200)
        self.assertIn("explanation_notes", analyze_resp.json())

        gen_resp = self.client.post(
            "/api/llm/generate-task",
            json={"topic": "Array Threshold", "difficulty": "Easy", "should_contain_bug": True},
        )
        self.assertEqual(gen_resp.status_code, 200)
        self.assertFalse(gen_resp.json()["ground_truth_correct"])

        solve_resp = self.client.post(
            "/api/llm/solve",
            json={
                "problem_statement": "Write a C++ function to reverse a string.",
                "language": "C++",
                "preferred_interface": "verification_guided",
            },
        )
        self.assertEqual(solve_resp.status_code, 200)
        solve_data = solve_resp.json()
        self.assertIn("code", solve_data)
        self.assertEqual(solve_data["preferred_interface"], "verification_guided")
        self.assertIn("verification_guided", solve_data)


if __name__ == "__main__":
    unittest.main()
