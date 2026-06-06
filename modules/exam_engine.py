import time

from . import questions as question_bank
from . import scoring


def start_exam(short=True, include_premium=True):
    selected = question_bank.sample_exam_questions(short=short, include_premium=include_premium)
    duration = sum(q.get("estimated_time_seconds", 75) for q in selected)
    return {
        "questions": selected,
        "answers": {},
        "started_at": time.time(),
        "duration_seconds": max(duration, 10 * 60),
        "finished": False,
    }


def get_next_question(exam_state):
    answered = set(exam_state.get("answers", {}))
    for question in exam_state.get("questions", []):
        if question["id"] not in answered:
            return question
    return None


def submit_answer(exam_state, question_id, answer):
    exam_state.setdefault("answers", {})[question_id] = answer
    return exam_state


def calculate_score(exam_state):
    return scoring.calculate_score(exam_state.get("answers", {}), exam_state.get("questions", []))


def estimate_cefr_level(percent):
    return scoring.estimate_cefr_level(percent)


def generate_exam_report(exam_state):
    result = calculate_score(exam_state)
    result["estimated_level"] = estimate_cefr_level(result["percent"])
    result["disclaimer"] = "Estimation non officielle, basée sur un barème MVP de préparation."
    return result
