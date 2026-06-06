import json
import random
from collections import Counter
from pathlib import Path


QUESTIONS_PATH = Path("data/questions.json")
BLUEPRINT_PATH = Path("data/tcf_blueprint.json")
REQUIRED_FIELDS = {
    "id",
    "skill",
    "level",
    "difficulty_score",
    "type",
    "prompt",
    "context",
    "choices",
    "correct_answer",
    "explanation",
    "estimated_time_seconds",
    "tags",
}


def load_questions():
    with QUESTIONS_PATH.open(encoding="utf-8") as handle:
        questions = json.load(handle)
    valid = [question for question in questions if validate_question_schema(question)]
    return valid


def load_blueprint():
    with BLUEPRINT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_question_schema(question):
    if not REQUIRED_FIELDS.issubset(question):
        return False
    return isinstance(question["choices"], list) and len(question["choices"]) == 4


def filter_questions(skill=None, level=None, premium_only=False):
    questions = load_questions()
    if skill:
        questions = [q for q in questions if q["skill"] == skill]
    if level:
        questions = [q for q in questions if q["level"] == level]
    if not premium_only:
        questions = [q for q in questions if not q.get("premium_only")]
    return questions


def sample_exam_questions(blueprint=None, short=True, include_premium=True):
    questions = load_questions()
    if not include_premium:
        questions = [q for q in questions if not q.get("premium_only")]
    distribution = {
        "comprehension_orale": 8 if short else 20,
        "structure_langue": 6 if short else 15,
        "comprehension_ecrite": 8 if short else 20,
    }
    selected = []
    for skill, count in distribution.items():
        pool = [q for q in questions if q["skill"] == skill]
        random.shuffle(pool)
        selected.extend(pool[:count])
    selected.sort(key=lambda q: (q["skill"], q["difficulty_score"]))
    return selected


def get_question_stats():
    questions = load_questions()
    return {
        "total": len(questions),
        "by_skill": dict(Counter(q["skill"] for q in questions)),
        "by_level": dict(Counter(q["level"] for q in questions)),
    }


def writing_prompts(level=None):
    prompts = [
        {
            "id": "EE_A2_001",
            "level": "A2",
            "type": "message court",
            "prompt": "Tu écris à un ami pour proposer une sortie ce week-end. Donne le lieu, l'heure et une raison.",
        },
        {
            "id": "EE_B1_001",
            "level": "B1",
            "type": "récit d'expérience",
            "prompt": "Raconte une expérience où tu as découvert une nouvelle ville. Décris ce que tu as aimé et ce qui t'a surpris.",
        },
        {
            "id": "EE_B2_001",
            "level": "B2",
            "type": "email formel",
            "prompt": "Écris un email à une mairie pour demander plus d'espaces verts dans ton quartier. Explique la situation et propose deux solutions.",
        },
        {
            "id": "EE_C1_001",
            "level": "C1",
            "type": "argumentation",
            "prompt": "Selon toi, le télétravail transforme-t-il durablement la vie professionnelle ? Présente une opinion nuancée et argumentée.",
        },
    ]
    if level:
        return [prompt for prompt in prompts if prompt["level"] == level]
    return prompts
