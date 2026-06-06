import json
import sqlite3
from datetime import date, datetime
from pathlib import Path


DB_PATH = Path("data/tcf_coach.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_premium INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                mode TEXT NOT NULL,
                section TEXT,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                estimated_level TEXT NOT NULL,
                details_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS question_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id TEXT NOT NULL,
                selected_answer TEXT,
                correct_answer TEXT,
                is_correct INTEGER NOT NULL,
                skill TEXT,
                level TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS writing_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prompt TEXT NOT NULL,
                text TEXT NOT NULL,
                ai_feedback TEXT,
                estimated_level TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS usage_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                usage_date TEXT NOT NULL,
                questions_answered INTEGER NOT NULL DEFAULT 0,
                writing_corrections_used INTEGER NOT NULL DEFAULT 0,
                mock_exams_used INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, usage_date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def _now():
    return datetime.utcnow().isoformat(timespec="seconds")


def _row_to_dict(row):
    return dict(row) if row else None


def create_user(email, password_hash):
    email = email.strip().lower()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at, is_premium) VALUES (?, ?, ?, 0)",
            (email, password_hash, _now()),
        )
        return get_user(cur.lastrowid)


def authenticate_user(email, password_hash):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password_hash = ?",
            (email.strip().lower(), password_hash),
        ).fetchone()
    return _row_to_dict(row)


def get_user(user_id):
    if not user_id:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def get_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    return _row_to_dict(row)


def save_test_session(user_id, mode, section, score, total, estimated_level, details):
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO test_sessions
            (user_id, mode, section, score, total, estimated_level, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, mode, section, score, total, estimated_level, json.dumps(details, ensure_ascii=False), _now()),
        )
        return cur.lastrowid


def save_question_attempt(user_id, question_id, selected_answer, correct_answer, is_correct, skill, level):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO question_attempts
            (user_id, question_id, selected_answer, correct_answer, is_correct, skill, level, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, question_id, selected_answer, correct_answer, int(is_correct), skill, level, _now()),
        )


def save_writing_submission(user_id, prompt, text, ai_feedback, estimated_level):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO writing_submissions
            (user_id, prompt, text, ai_feedback, estimated_level, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, prompt, text, ai_feedback, estimated_level, _now()),
        )


def get_user_history(user_id, limit=20):
    if not user_id:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM test_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _ensure_usage_row(conn, user_id):
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO usage_limits
        (user_id, usage_date, questions_answered, writing_corrections_used, mock_exams_used)
        VALUES (?, ?, 0, 0, 0)
        """,
        (user_id, today),
    )
    return today


def get_usage_today(user_id):
    if not user_id:
        return {"questions_answered": 0, "writing_corrections_used": 0, "mock_exams_used": 0}
    with get_connection() as conn:
        today = _ensure_usage_row(conn, user_id)
        row = conn.execute(
            "SELECT * FROM usage_limits WHERE user_id = ? AND usage_date = ?",
            (user_id, today),
        ).fetchone()
    return dict(row)


def increment_usage(user_id, questions=0, writing_corrections=0, mock_exams=0):
    if not user_id:
        return
    with get_connection() as conn:
        today = _ensure_usage_row(conn, user_id)
        conn.execute(
            """
            UPDATE usage_limits
            SET questions_answered = questions_answered + ?,
                writing_corrections_used = writing_corrections_used + ?,
                mock_exams_used = mock_exams_used + ?
            WHERE user_id = ? AND usage_date = ?
            """,
            (questions, writing_corrections, mock_exams, user_id, today),
        )


def get_user_dashboard_stats(user_id):
    if not user_id:
        return {
            "average_score": 0,
            "estimated_level": "A1",
            "history": [],
            "by_skill": {},
            "frequent_errors": [],
            "recommendations": ["Connecte-toi pour enregistrer ta progression."],
        }

    history = get_user_history(user_id, limit=10)
    with get_connection() as conn:
        attempts = conn.execute(
            "SELECT * FROM question_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT 500",
            (user_id,),
        ).fetchall()

    scores = [(item["score"] / item["total"]) * 100 for item in history if item["total"]]
    average = round(sum(scores) / len(scores), 1) if scores else 0
    estimated = history[0]["estimated_level"] if history else "A1"

    by_skill = {}
    errors = {}
    for row in attempts:
        skill = row["skill"] or "general"
        by_skill.setdefault(skill, {"correct": 0, "total": 0})
        by_skill[skill]["total"] += 1
        by_skill[skill]["correct"] += int(row["is_correct"])
        if not row["is_correct"]:
            key = f"{skill} - {row['level']}"
            errors[key] = errors.get(key, 0) + 1

    recommendations = []
    for skill, values in by_skill.items():
        rate = values["correct"] / values["total"] if values["total"] else 0
        if rate < 0.65:
            recommendations.append(f"Renforcer {skill.replace('_', ' ')} avec des questions ciblées.")
    if not recommendations:
        recommendations.append("Faire un examen blanc complet pour consolider l'estimation CECRL.")

    return {
        "average_score": average,
        "estimated_level": estimated,
        "history": history,
        "by_skill": by_skill,
        "frequent_errors": sorted(errors.items(), key=lambda item: item[1], reverse=True)[:5],
        "recommendations": recommendations,
    }
