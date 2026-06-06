def calculate_score(answers, questions):
    total = len(questions)
    correct = 0
    details = []
    for question in questions:
        selected = answers.get(question["id"])
        is_correct = selected == question["correct_answer"]
        correct += int(is_correct)
        details.append(
            {
                "question_id": question["id"],
                "selected_answer": selected,
                "correct_answer": question["correct_answer"],
                "is_correct": is_correct,
                "skill": question["skill"],
                "level": question["level"],
                "explanation": question["explanation"],
            }
        )
    percent = round((correct / total) * 100, 1) if total else 0
    return {"score": correct, "total": total, "percent": percent, "details": details}


def estimate_cefr_level(percent):
    if percent <= 30:
        return "A1/A2"
    if percent <= 50:
        return "B1"
    if percent <= 70:
        return "B2"
    if percent <= 85:
        return "C1"
    return "C2"


def level_to_difficulty(level):
    return {"A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 5}.get(level, 3)
