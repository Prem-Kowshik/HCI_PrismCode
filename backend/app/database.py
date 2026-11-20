import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "study_data.db"),
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                consent_given INTEGER NOT NULL,
                programming_experience TEXT NOT NULL,
                cpp_familiarity INTEGER NOT NULL,
                ai_tool_frequency TEXT NOT NULL,
                condition_order TEXT NOT NULL,
                task_assignment TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                condition TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                user_verdict TEXT NOT NULL,
                suspected_error_line INTEGER,
                suspected_error_description TEXT,
                confidence INTEGER NOT NULL,
                time_taken_ms INTEGER NOT NULL,
                checklist_checked TEXT NOT NULL DEFAULT '[]',
                edge_cases_checked TEXT NOT NULL DEFAULT '[]',
                expanded_hints_count INTEGER NOT NULL DEFAULT 0,
                ground_truth_correct INTEGER NOT NULL,
                is_accurate INTEGER NOT NULL,
                error_detected INTEGER NOT NULL,
                false_rejection INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants(id)
            );

            CREATE TABLE IF NOT EXISTS condition_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                condition TEXT NOT NULL,
                task_set TEXT NOT NULL DEFAULT 'core',
                mental_demand INTEGER NOT NULL,
                effort INTEGER NOT NULL,
                frustration INTEGER NOT NULL,
                helpfulness INTEGER NOT NULL,
                distraction INTEGER NOT NULL,
                overall_usability INTEGER NOT NULL,
                useful_features TEXT,
                confusing_features TEXT,
                comments TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants(id)
            );

            CREATE TABLE IF NOT EXISTS generated_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                difficulty TEXT NOT NULL DEFAULT 'Medium',
                problem_statement TEXT NOT NULL,
                code TEXT NOT NULL,
                ground_truth_correct INTEGER,
                ground_truth_error_line INTEGER,
                ground_truth_error_description TEXT,
                explanation_notes TEXT NOT NULL,
                verification_guided TEXT NOT NULL,
                llm_provider TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        # Safe migrations for existing DBs
        tr_cols = [r["name"] for r in conn.execute("PRAGMA table_info(task_responses)").fetchall()]
        if "edge_cases_checked" not in tr_cols:
            conn.execute(
                "ALTER TABLE task_responses ADD COLUMN edge_cases_checked TEXT NOT NULL DEFAULT '[]'"
            )

        cr_cols = [r["name"] for r in conn.execute("PRAGMA table_info(condition_ratings)").fetchall()]
        if "task_set" not in cr_cols:
            conn.execute(
                "ALTER TABLE condition_ratings ADD COLUMN task_set TEXT NOT NULL DEFAULT 'core'"
            )

        gt_cols = [r["name"] for r in conn.execute("PRAGMA table_info(generated_tasks)").fetchall()]
        if "difficulty" not in gt_cols:
            conn.execute(
                "ALTER TABLE generated_tasks ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'Medium'"
            )
        if "is_active" not in gt_cols:
            conn.execute(
                "ALTER TABLE generated_tasks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0"
            )
