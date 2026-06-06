import csv
import html
import hashlib
import io
import json
import os
import random
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfdoc
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


APP_TITLE = "TCF Trainer - Objectif B2, C1 et plus"
QUESTIONS_PATH = Path("questions.json")
AI_ENABLED = False
AI_DEFAULT_MODEL = "gpt-5-mini"
AI_MAX_CALLS_PER_SESSION = 10
AI_INPUT_CHAR_LIMIT = 6000
AI_OUTPUT_TOKEN_LIMIT = 700
AI_RETEST_TOKEN_LIMIT = 900
REQUIRED_AI_QUESTION_FIELDS = {
    "id",
    "section",
    "theme",
    "niveau",
    "consigne",
    "texte",
    "choix",
    "bonne_reponse",
    "explication",
    "rappel_regle",
    "astuce_tcf",
}
PARASITE_PREFIX_RE = re.compile(
    r"^\s*(?:sujet\s+(?:compréhension|comprehension|expression\s+écrite|expression\s+ecrite)|"
    r"compréhension\s+orale|comprehension\s+orale|nouveau\s+document|document\s+d'entraînement|"
    r"item\s+grammatical\s+d'entraînement|nouvelle\s+question\s+de\s+grammaire|question)\s*[:.]\s*",
    re.IGNORECASE,
)


def _md5_compat(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return hashlib.md5(*args, **kwargs)


pdfdoc.md5 = _md5_compat

SECTION_META = {
    "comprehension_orale": {
        "label": "Compréhension orale",
        "short": "Oral",
        "duration": 25 * 60,
        "expected": 29,
        "kind": "mcq",
    },
    "structures_langue": {
        "label": "Structures de la langue",
        "short": "Structures",
        "duration": 15 * 60,
        "expected": 18,
        "kind": "mcq",
    },
    "comprehension_ecrite": {
        "label": "Compréhension écrite",
        "short": "Écrit",
        "duration": 45 * 60,
        "expected": 29,
        "kind": "mcq",
    },
    "expression_ecrite": {
        "label": "Expression écrite",
        "short": "Expression écrite",
        "duration": 60 * 60,
        "expected": 3,
        "kind": "writing",
    },
    "expression_orale": {
        "label": "Expression orale",
        "short": "Expression orale",
        "duration": 12 * 60,
        "expected": 3,
        "kind": "speaking",
    },
}

EXAM_ORDER = list(SECTION_META)

WRITING_TASKS = [
    {
        "id": "EE_001",
        "title": "Tâche 1 - Répondre à un message",
        "prompt": "Votre ami vous invite à passer le week-end chez lui. Répondez pour accepter, remercier et poser deux questions pratiques.",
        "recommended": "60 à 120 mots",
    },
    {
        "id": "EE_002",
        "title": "Tâche 2 - Raconter une expérience",
        "prompt": "Racontez une expérience où vous avez dû vous adapter à une nouvelle situation.",
        "recommended": "120 à 150 mots",
    },
    {
        "id": "EE_003",
        "title": "Tâche 3 - Exprimer une opinion argumentée",
        "prompt": "Selon vous, faut-il rendre les transports publics gratuits dans les grandes villes ? Donnez votre opinion avec des arguments et des exemples.",
        "recommended": "180 à 220 mots",
    },
]

SPEAKING_TASKS = [
    {
        "id": "EO_001",
        "title": "Tâche 1 - Parler de soi",
        "prompt": "Présentez-vous, parlez de vos études ou de votre travail, puis expliquez pourquoi vous apprenez le français.",
    },
    {
        "id": "EO_002",
        "title": "Tâche 2 - Obtenir des informations",
        "prompt": "Vous voulez vous inscrire à une activité culturelle. Préparez les questions à poser sur les horaires, les tarifs et les conditions d'inscription.",
    },
    {
        "id": "EO_003",
        "title": "Tâche 3 - Donner son opinion",
        "prompt": "Pensez-vous que le télétravail améliore la qualité de vie ? Préparez une réponse organisée avec exemples.",
    },
]


def load_questions():
    with QUESTIONS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def init_state():
    defaults = {
        "page": "home",
        "answers": {},
        "writing_answers": {},
        "speaking_notes": {},
        "active_sections": EXAM_ORDER.copy(),
        "section_index": 0,
        "section_started_at": None,
        "attempt_started_at": None,
        "attempt_question_ids": [],
        "history": [],
        "result_saved": False,
        "errors_saved": False,
        "error_counts": {},
        "ai_outputs": {},
        "ai_generated_questions": {},
        "ai_cache": {},
        "ai_call_count": 0,
        "ai_enabled": env_bool("AI_ENABLED", AI_ENABLED),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def set_page(page):
    st.session_state.page = page


def root_question_id(question_id):
    return question_id.split("_V", 1)[0]


def select_attempt_question_ids(all_questions, sections):
    selected = []
    for section in sections:
        meta = SECTION_META[section]
        if meta["kind"] != "mcq":
            continue
        pool = questions_by_section(all_questions, section)
        grouped = defaultdict(list)
        for question in pool:
            grouped[root_question_id(question["id"])].append(question)
        roots = list(grouped)
        target = min(meta["expected"], len(roots))
        for root in random.sample(roots, target):
            selected.append(random.choice(grouped[root])["id"])
    return selected


def current_attempt_questions(all_questions):
    ids = st.session_state.get("attempt_question_ids", [])
    if not ids:
        ids = select_attempt_question_ids(all_questions, st.session_state.active_sections)
        st.session_state.attempt_question_ids = ids
    by_id = {question["id"]: question for question in all_questions}
    return [by_id[question_id] for question_id in ids if question_id in by_id]


def reset_attempt(sections, all_questions):
    st.session_state.answers = {}
    st.session_state.writing_answers = {}
    st.session_state.speaking_notes = {}
    st.session_state.active_sections = sections
    st.session_state.attempt_question_ids = select_attempt_question_ids(all_questions, sections)
    st.session_state.section_index = 0
    st.session_state.section_started_at = time.time()
    st.session_state.attempt_started_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.result_saved = False
    st.session_state.errors_saved = False
    set_page("test")


def questions_by_section(questions, section):
    return [q for q in questions if q["section"] == section]


def estimate_level(percent):
    if percent <= 20:
        return "inférieur A1"
    if percent <= 35:
        return "A1"
    if percent <= 50:
        return "A2"
    if percent <= 65:
        return "B1"
    if percent <= 80:
        return "B2"
    if percent <= 92:
        return "C1"
    return "C2"


def format_seconds(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def clean_question_text(text):
    """Supprime seulement les titres parasites placés au tout début du texte."""
    if not isinstance(text, str):
        return text
    return PARASITE_PREFIX_RE.sub("", text, count=1).strip()


def reading_document_text(question):
    """Présente les items de compréhension écrite comme de vrais courts documents TCF."""
    text = clean_question_text(question.get("texte", ""))
    if question.get("section") != "comprehension_ecrite" or len(text) >= 260:
        return text

    theme = question.get("theme", "")
    if "email" in theme or "message" in theme:
        return (
            "Message reçu\n\n"
            f"{text}\n\n"
            "Le destinataire doit comprendre l'information principale, la date ou l'action attendue avant de répondre."
        )
    if "courrier" in theme or "administr" in theme:
        return (
            "Extrait d'un courrier administratif\n\n"
            f"{text}\n\n"
            "Le document précise la situation du dossier et indique, si nécessaire, la démarche à effectuer."
        )
    if "annonce" in theme:
        return (
            "Annonce pratique\n\n"
            f"{text}\n\n"
            "Les informations importantes concernent les conditions, le moment, le lieu ou le service proposé."
        )
    if "reglement" in theme or "instruction" in theme:
        return (
            "Consigne ou règlement\n\n"
            f"{text}\n\n"
            "Le lecteur doit repérer ce qui est obligatoire, interdit, conseillé ou soumis à une condition."
        )
    if "opinion" in theme or "article" in theme:
        return (
            "Extrait d'article\n\n"
            f"{text}\n\n"
            "Le passage présente une idée principale et une nuance. Il faut distinguer l'opinion générale des détails."
        )
    return (
        "Document\n\n"
        f"{text}\n\n"
        "Lisez attentivement le document et repérez l'information qui répond exactement à la question."
    )


def question_text_for_display(question):
    if question.get("section") == "comprehension_ecrite":
        return reading_document_text(question)
    return clean_question_text(question.get("texte", ""))


CLEAN_TEXT_EXAMPLES = {
    "Sujet compréhension : Lisez le texte...": "Lisez le texte...",
    "Le télétravail en France": "Le télétravail en France",
    "Nouveau document : Lisez le texte...": "Lisez le texte...",
}
for _source_text, _expected_text in CLEAN_TEXT_EXAMPLES.items():
    assert clean_question_text(_source_text) == _expected_text


def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def openai_api_key():
    return get_secret("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")


def ai_model():
    return get_secret("OPENAI_MODEL") or os.environ.get("OPENAI_MODEL", AI_DEFAULT_MODEL)


def ai_is_enabled():
    return bool(st.session_state.get("ai_enabled", AI_ENABLED))


def ai_is_configured():
    return bool(openai_api_key())


def truncate_for_ai(text, limit=AI_INPUT_CHAR_LIMIT):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[Texte tronqué pour limiter le coût de l'appel IA.]"


def ai_cache_key(prompt, max_tokens):
    raw = f"{ai_model()}::{max_tokens}::{truncate_for_ai(prompt)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def call_ai(prompt, max_tokens=AI_OUTPUT_TOKEN_LIMIT):
    """Appel IA volontaire, plafonné et caché pour limiter les coûts personnels."""
    # Garde-fou coût : aucun appel API si le Mode IA n'a pas été activé explicitement.
    if not ai_is_enabled():
        return "Mode IA désactivé : activez-le dans la barre latérale pour lancer cet appel."
    if not ai_is_configured():
        return "IA non configurée : ajoutez OPENAI_API_KEY dans les secrets Streamlit ou les variables d'environnement."
    if OpenAI is None:
        return "SDK OpenAI non installé : lancez pip install -r requirements.txt puis redémarrez l'application."

    cache_key = ai_cache_key(prompt, max_tokens)
    if cache_key in st.session_state.ai_cache:
        return st.session_state.ai_cache[cache_key]

    # Garde-fou coût : limite par session et cache avant tout nouvel appel réseau.
    if st.session_state.ai_call_count >= AI_MAX_CALLS_PER_SESSION:
        return f"Limite atteinte : {AI_MAX_CALLS_PER_SESSION} appels IA maximum par session."

    client = OpenAI(api_key=openai_api_key())
    try:
        response = client.responses.create(
            model=ai_model(),
            input=[
                {
                    "role": "user",
                    "content": truncate_for_ai(prompt),
                }
            ],
            max_output_tokens=max_tokens,
        )
    except Exception as exc:
        if "insufficient_quota" in str(exc):
            return (
                "Quota OpenAI insuffisant : ajoutez des crédits ou activez la facturation dans votre compte "
                "OpenAI API, puis réessayez. Aucun autre appel IA n'a été lancé."
            )
        return f"Erreur OpenAI : {exc}"

    st.session_state.ai_call_count += 1
    output = response.output_text or "Aucune réponse IA reçue."
    st.session_state.ai_cache[cache_key] = output
    return output


def render_ai_status():
    if not ai_is_enabled():
        st.caption("Mode IA désactivé. Les questions fixes de questions.json restent disponibles sans coût.")
    elif ai_is_configured():
        remaining = max(0, AI_MAX_CALLS_PER_SESSION - st.session_state.ai_call_count)
        st.caption(f"Mode IA activé - modèle {ai_model()} - {remaining} appel(s) restant(s) dans cette session.")
    else:
        st.caption("Mode IA activé mais aucune clé API n'est configurée. Le mode gratuit fonctionne toujours.")


def render_ai_controls():
    with st.sidebar:
        st.subheader("Mode IA")
        st.session_state.ai_enabled = st.checkbox(
            "Activer le Mode IA",
            value=st.session_state.get("ai_enabled", AI_ENABLED),
            help="Désactivé par défaut pour éviter tout coût. Les appels IA ne partent que via les boutons dédiés.",
        )
        render_ai_status()
        if st.session_state.ai_cache:
            st.caption(f"{len(st.session_state.ai_cache)} réponse(s) IA en cache session.")


def extract_json_array(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\[[\s\S]*\]", text)
    return match.group(0) if match else text


def validate_ai_questions(raw_text):
    try:
        questions = json.loads(extract_json_array(raw_text))
    except json.JSONDecodeError as exc:
        return [], f"JSON IA invalide : {exc}"
    if not isinstance(questions, list):
        return [], "JSON IA invalide : la réponse doit être une liste."

    validated = []
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            return [], f"Question IA {index} invalide : objet attendu."
        missing = REQUIRED_AI_QUESTION_FIELDS - set(question)
        if missing:
            return [], f"Question IA {index} invalide : champ(s) manquant(s) {', '.join(sorted(missing))}."
        if question["bonne_reponse"] not in {"A", "B", "C", "D"}:
            return [], f"Question IA {index} invalide : bonne_reponse doit être A, B, C ou D."
        choix = question.get("choix")
        if not isinstance(choix, dict) or set(choix) != {"A", "B", "C", "D"}:
            return [], f"Question IA {index} invalide : choix doit contenir A, B, C et D."
        validated.append(question)
    return validated, None


def writing_feedback_prompt(task, answer):
    return f"""
Tu es correcteur TCF pour l'expression écrite. Réponds en français, de façon concise et pédagogique.

Consigne :
{task['prompt']}

Longueur recommandée :
{task['recommended']}

Réponse du candidat :
{answer}

Donne :
1. niveau estimé : B1, B2 ou C1,
2. les points forts,
3. les erreurs principales avec corrections,
4. une version améliorée naturelle,
5. trois conseils concrets pour viser B2/C1.
Ne donne pas de note officielle TCF.
"""


def retest_questions_prompt(item, count=3):
    source = {
        "section": item["section"],
        "theme": item["theme"],
        "niveau": "B2/C1",
        "consigne": clean_question_text(item["consigne"]),
        "texte": question_text_for_display(item),
        "choix": item["choix"],
        "bonne_reponse": item["bonne_reponse"],
        "reponse_utilisateur": item["user_answer"],
        "explication": clean_question_text(item["explication"]),
        "rappel_regle": clean_question_text(item["rappel_regle"]),
        "astuce_tcf": clean_question_text(item["astuce_tcf"]),
    }
    return f"""
Génère exactement {count} questions TCF similaires pour retester ce type d'erreur.
Niveau visé : B2/C1.

Question source :
{json.dumps(source, ensure_ascii=False)}

Réponds uniquement avec un JSON strict, sans texte avant ni après.
Format obligatoire :
[
  {{
    "id": "AI_RETEST_001",
    "section": "{item['section']}",
    "theme": "{item['theme']}",
    "niveau": "B2/C1",
    "consigne": "...",
    "texte": "...",
    "choix": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "bonne_reponse": "A",
    "explication": "...",
    "rappel_regle": "...",
    "astuce_tcf": "..."
  }}
]
"""


def revision_plan_prompt(score, payload):
    writing_word_counts = {task_id: len(answer.split()) for task_id, answer in payload["expression_ecrite"].items()}
    return f"""
Prépare un plan de révision TCF sur 7 jours pour un candidat visant B2, C1 et plus.

Score global : {score['percent']} %
Niveau estimé : {score['level']}
Scores par compétence :
{json.dumps(score['by_section'], ensure_ascii=False)}

Thèmes à revoir :
{json.dumps(score['weak_themes'].most_common(8), ensure_ascii=False)}

Mots écrits par tâche d'expression écrite :
{json.dumps(writing_word_counts, ensure_ascii=False)}

Donne un plan pratique jour par jour, avec durée, objectifs, exercices et priorité.
"""


def score_attempt(questions):
    scored = []
    for q in questions:
        user_answer = st.session_state.answers.get(q["id"])
        correct = user_answer == q["bonne_reponse"]
        scored.append({**q, "user_answer": user_answer, "correct": correct})

    total = len(scored)
    correct_count = sum(item["correct"] for item in scored)
    percent = round(correct_count / total * 100, 1) if total else 0

    by_section = []
    for section, meta in SECTION_META.items():
        section_items = [item for item in scored if item["section"] == section]
        if not section_items:
            continue
        ok = sum(item["correct"] for item in section_items)
        pct = round(ok / len(section_items) * 100, 1)
        by_section.append(
            {
                "section": section,
                "compétence": meta["short"],
                "bonnes réponses": ok,
                "questions": len(section_items),
                "score": pct,
                "niveau estimé": estimate_level(pct),
            }
        )

    weak_themes = Counter(item["theme"] for item in scored if not item["correct"])
    return {
        "items": scored,
        "total": total,
        "correct": correct_count,
        "incorrect": total - correct_count,
        "percent": percent,
        "level": estimate_level(percent),
        "by_section": by_section,
        "weak_themes": weak_themes,
    }


def build_report_payload(questions):
    score = score_attempt(questions)
    return {
        "date": datetime.now().isoformat(timespec="seconds"),
        "score": score["percent"],
        "niveau_estime": score["level"],
        "bonnes_reponses": score["correct"],
        "mauvaises_reponses": score["incorrect"],
        "details_competences": score["by_section"],
        "themes_a_revoir": score["weak_themes"].most_common(),
        "reponses": [
            {
                "id": item["id"],
                "section": item["section"],
                "theme": item["theme"],
                "consigne": clean_question_text(item["consigne"]),
                "question": question_text_for_display(item),
                "reponse_utilisateur": item["user_answer"],
                "bonne_reponse": item["bonne_reponse"],
                "correct": item["correct"],
                "explication": clean_question_text(item["explication"]),
                "rappel_regle": clean_question_text(item["rappel_regle"]),
                "astuce_tcf": clean_question_text(item["astuce_tcf"]),
            }
            for item in score["items"]
        ],
        "expression_ecrite": st.session_state.writing_answers,
        "expression_orale": st.session_state.speaking_notes,
    }


def save_error_counts_once(score):
    if st.session_state.errors_saved:
        return
    counts = Counter(st.session_state.error_counts)
    counts.update(item["theme"] for item in score["items"] if not item["correct"])
    st.session_state.error_counts = dict(counts)
    st.session_state.errors_saved = True


def render_generated_questions(questions, key_prefix):
    for index, question in enumerate(questions, start=1):
        with st.container(border=True):
            st.write(f"**Question IA {index} - {question['theme'].replace('_', ' ')}**")
            st.write(clean_question_text(question["consigne"]))
            st.write(question_text_for_display(question))
            selected = st.radio(
                "Votre réponse",
                [f"{key}. {clean_question_text(value)}" for key, value in question["choix"].items()],
                key=f"{key_prefix}_{index}",
                index=None,
            )
            if selected:
                answer = selected.split(".", 1)[0]
                if answer == question["bonne_reponse"]:
                    st.success(f"Correct. {clean_question_text(question['explication'])}")
                else:
                    st.error(f"Réponse attendue : {question['bonne_reponse']}. {clean_question_text(question['explication'])}")
                st.caption(clean_question_text(question["rappel_regle"]))
                st.caption(clean_question_text(question["astuce_tcf"]))


def generate_retest_for_item(item, output_key, count=3):
    raw = call_ai(retest_questions_prompt(item, count=count), max_tokens=AI_RETEST_TOKEN_LIMIT)
    if raw.startswith(("Mode IA", "IA non configurée", "SDK OpenAI", "Limite atteinte", "Erreur OpenAI")):
        st.session_state.ai_outputs[output_key] = raw
        st.session_state.ai_generated_questions.pop(output_key, None)
        return
    questions, error = validate_ai_questions(raw)
    if error:
        st.session_state.ai_outputs[output_key] = error
        st.session_state.ai_generated_questions.pop(output_key, None)
        return
    st.session_state.ai_generated_questions[output_key] = questions[:4]
    st.session_state.ai_outputs[output_key] = None


def render_frequent_errors(score):
    counts = Counter(st.session_state.error_counts)
    if not counts:
        return

    st.subheader("Mes erreurs fréquentes")
    error_df = pd.DataFrame(counts.most_common(), columns=["thème", "erreurs"])
    st.dataframe(error_df, use_container_width=True, hide_index=True)

    incorrect_items = [item for item in score["items"] if not item["correct"]]
    if not incorrect_items:
        return
    themes = [theme for theme, _ in counts.most_common()]
    selected_theme = st.selectbox("Retest ciblé", themes)
    item = next((candidate for candidate in incorrect_items if candidate["theme"] == selected_theme), incorrect_items[0])
    output_key = f"frequent_retest_{selected_theme}"
    if st.button("Générer 3 questions similaires", key=f"frequent_{selected_theme}"):
        with st.spinner("Génération du retest ciblé..."):
            generate_retest_for_item(item, output_key)
    if st.session_state.ai_outputs.get(output_key):
        st.error(st.session_state.ai_outputs[output_key])
    if output_key in st.session_state.ai_generated_questions:
        render_generated_questions(st.session_state.ai_generated_questions[output_key], output_key)


def csv_bytes(payload):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "section",
            "theme",
            "consigne",
            "question",
            "reponse_utilisateur",
            "bonne_reponse",
            "correct",
            "explication",
            "rappel_regle",
            "astuce_tcf",
        ],
    )
    writer.writeheader()
    writer.writerows(payload["reponses"])
    return output.getvalue().encode("utf-8")


def pdf_bytes(payload):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(APP_TITLE, styles["Title"]),
        Paragraph(f"Date : {payload['date']}", styles["Normal"]),
        Paragraph(f"Score : {payload['score']} % - Niveau estimé : {payload['niveau_estime']}", styles["Heading2"]),
        Paragraph("Ce score est une estimation d'entraînement. Le TCF officiel utilise un barème différent.", styles["Italic"]),
        Spacer(1, 12),
        Paragraph("Compétences", styles["Heading2"]),
    ]
    table_rows = [["Compétence", "Score", "Niveau"]]
    table_rows += [[row["compétence"], f"{row['score']} %", row["niveau estimé"]] for row in payload["details_competences"]]
    table = Table(table_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [table, Spacer(1, 12), Paragraph("Questions et corrections", styles["Heading2"])]
    for item in payload["reponses"]:
        result = "Correct" if item["correct"] else "Incorrect"
        story.append(Paragraph(f"{item['id']} - {item['section']} - {result}", styles["Heading3"]))
        story.append(Paragraph(f"Question : {item.get('question', '')}", styles["Normal"]))
        story.append(Paragraph(f"Votre réponse : {item['reponse_utilisateur'] or 'Aucune'} | Bonne réponse : {item['bonne_reponse']}", styles["Normal"]))
        story.append(Paragraph(f"Explication : {item['explication']}", styles["Normal"]))
        story.append(Paragraph(f"Rappel : {item['rappel_regle']}", styles["Normal"]))
        story.append(Paragraph(f"Astuce TCF : {item['astuce_tcf']}", styles["Normal"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    return buffer.getvalue()


def metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)


def render_header():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 16px;
        }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-weight: 700;
            font-size: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_home(questions):
    st.title(APP_TITLE)
    st.markdown('<span class="badge">Objectif B2, C1 et plus</span>', unsafe_allow_html=True)
    st.write("Entraînez-vous avec un examen blanc complet, des corrections détaillées et un tableau de bord de progression vers les niveaux avancés.")

    cols = st.columns(3)
    with cols[0]:
        metric_card("Banque QCM", len(questions), "L'examen tire 76 questions au hasard dans cette banque.")
    with cols[1]:
        metric_card("Durée estimée", "2 h 37")
    with cols[2]:
        metric_card("Niveau visé", "B2/C1+")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Passer un examen complet", use_container_width=True, type="primary"):
            reset_attempt(EXAM_ORDER.copy(), questions)
            st.rerun()
        if st.button("Consulter mes résultats", use_container_width=True):
            set_page("results")
            st.rerun()
    with c2:
        if st.button("S'entraîner par compétence", use_container_width=True):
            set_page("training")
            st.rerun()
        if st.button("À propos du TCF", use_container_width=True):
            set_page("about")
            st.rerun()


def render_training(questions):
    st.title("S'entraîner par compétence")
    labels = {meta["label"]: key for key, meta in SECTION_META.items()}
    choice = st.selectbox("Compétence", list(labels))
    if st.button("Commencer l'entraînement", type="primary"):
        reset_attempt([labels[choice]], questions)
        st.rerun()
    if st.button("Retour à l'accueil"):
        set_page("home")
        st.rerun()


def render_timer(section_key):
    meta = SECTION_META[section_key]
    if st.session_state.section_started_at is None:
        st.session_state.section_started_at = time.time()
    elapsed = time.time() - st.session_state.section_started_at
    remaining = meta["duration"] - elapsed
    progress = min(1.0, max(0.0, elapsed / meta["duration"]))
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("Temps restant", format_seconds(remaining))
    with c2:
        st.progress(progress, text=f"{meta['label']} - {round(progress * 100)} % du temps écoulé")
    return remaining <= 0


def advance_section():
    if st.session_state.section_index + 1 >= len(st.session_state.active_sections):
        set_page("correction")
        return
    st.session_state.section_index += 1
    st.session_state.section_started_at = time.time()


def render_oral_audio(question):
    audio_text = html.escape(json.dumps(clean_question_text(question["texte"]), ensure_ascii=False), quote=True)
    element_id = f"audio_{question['id']}"
    components.html(
        f"""
        <div id="{element_id}" style="display:flex;gap:10px;align-items:center;margin:8px 0 14px 0;">
          <button
            type="button"
            style="background:#2563eb;color:white;border:0;border-radius:6px;padding:10px 14px;font-weight:700;cursor:pointer;"
            onclick="
              window.speechSynthesis.cancel();
              const utterance = new SpeechSynthesisUtterance({audio_text});
              utterance.lang = 'fr-FR';
              utterance.rate = 0.92;
              window.speechSynthesis.speak(utterance);
            "
          >Écouter l'audio</button>
          <button
            type="button"
            style="background:#e2e8f0;color:#0f172a;border:0;border-radius:6px;padding:10px 14px;font-weight:700;cursor:pointer;"
            onclick="window.speechSynthesis.cancel();"
          >Stop</button>
          <span style="color:#475569;font-size:14px;">Lecture audio générée par le navigateur.</span>
        </div>
        """,
        height=62,
    )


def render_mcq_section(section_key, questions, expired):
    disabled = expired
    for index, q in enumerate(questions_by_section(questions, section_key), start=1):
        with st.container(border=True):
            st.subheader(f"Question {index}")
            st.caption(f"Thème : {q['theme'].replace('_', ' ')} | Niveau : {q['niveau']}")
            st.write(clean_question_text(q["consigne"]))
            if section_key == "comprehension_orale":
                if q.get("audio_file"):
                    st.audio(q["audio_file"])
                else:
                    render_oral_audio(q)
                st.caption("La transcription sera affichée dans la correction.")
            else:
                st.write(question_text_for_display(q))
            options = [f"{key}. {clean_question_text(value)}" for key, value in q["choix"].items()]
            current = st.session_state.answers.get(q["id"])
            index_value = list(q["choix"]).index(current) if current in q["choix"] else None
            selected = st.radio(
                "Votre réponse",
                options,
                index=index_value,
                key=f"answer_{q['id']}",
                disabled=disabled,
                horizontal=False,
            )
            if selected and not disabled:
                st.session_state.answers[q["id"]] = selected.split(".", 1)[0]


def render_writing_section(expired):
    st.info("Auto-évaluation : clarté de la réponse, respect de la consigne, organisation, richesse du vocabulaire, correction grammaticale.")
    render_ai_status()
    for task in WRITING_TASKS:
        with st.container(border=True):
            st.subheader(task["title"])
            st.write(clean_question_text(task["prompt"]))
            st.caption(f"Longueur recommandée : {task['recommended']}")
            value = st.text_area(
                "Votre réponse",
                value=st.session_state.writing_answers.get(task["id"], ""),
                key=f"writing_{task['id']}",
                height=180,
                disabled=expired,
            )
            if not expired:
                st.session_state.writing_answers[task["id"]] = value
            st.metric("Mots", len(value.split()))
            st.checkbox("J'ai répondu à toutes les parties de la consigne", key=f"self_{task['id']}_1", disabled=expired)
            st.checkbox("J'ai utilisé des connecteurs logiques", key=f"self_{task['id']}_2", disabled=expired)
            st.checkbox("J'ai relu les accords et les temps", key=f"self_{task['id']}_3", disabled=expired)
            ai_key = f"writing_feedback_{task['id']}"
            if st.button("Corriger cette réponse avec l'IA", key=f"ai_{task['id']}", disabled=not value.strip()):
                with st.spinner("Correction IA en cours..."):
                    st.session_state.ai_outputs[ai_key] = call_ai(writing_feedback_prompt(task, value))
            if ai_key in st.session_state.ai_outputs:
                st.markdown(st.session_state.ai_outputs[ai_key])


def render_speaking_section(expired):
    st.info("Préparation écrite uniquement pour cette version. Une zone d'enregistrement audio pourra être ajoutée plus tard.")
    for task in SPEAKING_TASKS:
        with st.container(border=True):
            st.subheader(task["title"])
            st.write(clean_question_text(task["prompt"]))
            notes = st.text_area(
                "Notes de préparation",
                value=st.session_state.speaking_notes.get(task["id"], ""),
                key=f"speaking_{task['id']}",
                height=150,
                disabled=expired,
            )
            if not expired:
                st.session_state.speaking_notes[task["id"]] = notes


def render_test(questions):
    section_key = st.session_state.active_sections[st.session_state.section_index]
    meta = SECTION_META[section_key]
    st.title(meta["label"])
    st.caption(f"Section {st.session_state.section_index + 1} / {len(st.session_state.active_sections)}")
    expired = render_timer(section_key)
    if expired:
        st.warning("Temps écoulé : les réponses de cette section sont bloquées.")

    if meta["kind"] == "mcq":
        render_mcq_section(section_key, questions, expired)
    elif meta["kind"] == "writing":
        render_writing_section(expired)
    else:
        render_speaking_section(expired)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Accueil"):
            set_page("home")
            st.rerun()
    with c2:
        label = "Terminer et corriger" if st.session_state.section_index + 1 >= len(st.session_state.active_sections) else "Section suivante"
        if st.button(label, type="primary", use_container_width=True):
            advance_section()
            st.rerun()


def render_dashboard(score):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Score global", f"{score['percent']} %")
    with c2:
        st.metric("Niveau estimé", score["level"])
    with c3:
        st.metric("Bonnes réponses", score["correct"])
    with c4:
        st.metric("Mauvaises réponses", score["incorrect"])

    st.caption("Ce score est une estimation d'entraînement. Le TCF officiel utilise un barème différent.")
    section_df = pd.DataFrame(score["by_section"])
    if not section_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            radar = go.Figure(
                data=go.Scatterpolar(
                    r=section_df["score"],
                    theta=section_df["compétence"],
                    fill="toself",
                    name="Score",
                )
            )
            radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
            st.plotly_chart(radar, use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(section_df, x="compétence", y="score", color="niveau estimé", range_y=[0, 100]), use_container_width=True)

    if score["weak_themes"]:
        theme_df = pd.DataFrame(score["weak_themes"].most_common(), columns=["thème", "erreurs"])
        st.plotly_chart(px.bar(theme_df, x="thème", y="erreurs", title="Répartition des erreurs par thème"), use_container_width=True)


def save_history_once(payload):
    if st.session_state.result_saved:
        return
    st.session_state.history.append(
        {
            "date": payload["date"],
            "score": payload["score"],
            "niveau": payload["niveau_estime"],
            "details": payload["details_competences"],
        }
    )
    st.session_state.result_saved = True


def render_correction(questions):
    st.title("Correction pédagogique")
    score = score_attempt(questions)
    payload = build_report_payload(questions)
    save_history_once(payload)
    save_error_counts_once(score)
    render_dashboard(score)

    if score["weak_themes"]:
        st.subheader("À revoir en priorité")
        for index, (theme, count) in enumerate(score["weak_themes"].most_common(5), start=1):
            st.write(f"{index}. {theme.replace('_', ' ')} ({count} erreur(s))")

    render_frequent_errors(score)

    st.subheader("Plan IA optionnel")
    render_ai_status()
    if st.button("Créer un plan de révision avec l'IA", use_container_width=True):
        with st.spinner("Création du plan..."):
            st.session_state.ai_outputs["revision_plan"] = call_ai(revision_plan_prompt(score, payload))
    if "revision_plan" in st.session_state.ai_outputs:
        with st.expander("Plan de révision IA", expanded=True):
            st.markdown(st.session_state.ai_outputs["revision_plan"])

    st.subheader("Détail des réponses")
    for idx, item in enumerate(score["items"], start=1):
        status = "✓ Correct" if item["correct"] else "✗ Incorrect"
        with st.expander(f"Question {idx} - {status} - {item['theme'].replace('_', ' ')}", expanded=not item["correct"]):
            st.write(f"**Consigne :** {clean_question_text(item['consigne'])}")
            label = "Transcription audio" if item["section"] == "comprehension_orale" else "Question"
            st.write(f"**{label} :** {question_text_for_display(item)}")
            st.write("**Choix proposés :**")
            for choice_key, choice_text in item["choix"].items():
                st.write(f"{choice_key}. {clean_question_text(choice_text)}")
            st.write(f"**Votre réponse :** {item['user_answer'] or 'Aucune réponse'}")
            st.write(f"**Bonne réponse :** {item['bonne_reponse']} - {clean_question_text(item['choix'][item['bonne_reponse']])}")
            st.write(f"**Explication :** {clean_question_text(item['explication'])}")
            if not item["correct"]:
                st.write(f"**Pourquoi c'est incorrect :** la réponse attendue correspond à l'indice principal de la question et à la règle testée.")
                output_key = f"retest_{item['id']}"
                if st.button("Générer 3 questions similaires", key=f"retest_button_{item['id']}"):
                    with st.spinner("Génération du retest..."):
                        generate_retest_for_item(item, output_key)
                if st.session_state.ai_outputs.get(output_key):
                    st.error(st.session_state.ai_outputs[output_key])
                if output_key in st.session_state.ai_generated_questions:
                    render_generated_questions(st.session_state.ai_generated_questions[output_key], output_key)
            st.write(f"**Rappel :** {clean_question_text(item['rappel_regle'])}")
            st.write(f"**Conseil pratique :** notez ce thème dans votre carnet d'erreurs et refaites trois phrases similaires.")
            st.write(f"**Astuce TCF :** {clean_question_text(item['astuce_tcf'])}")

    st.subheader("Export")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Télécharger PDF", pdf_bytes(payload), "rapport_tcf.pdf", "application/pdf", use_container_width=True)
    with col2:
        st.download_button("Télécharger CSV", csv_bytes(payload), "rapport_tcf.csv", "text/csv", use_container_width=True)
    with col3:
        st.download_button(
            "Télécharger JSON",
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "rapport_tcf.json",
            "application/json",
            use_container_width=True,
        )

    if st.button("Retour à l'accueil"):
        set_page("home")
        st.rerun()


def render_results():
    st.title("Historique de mes examens")
    if not st.session_state.history:
        st.info("Aucun examen terminé pour le moment.")
    else:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df[["date", "score", "niveau"]], use_container_width=True)
        st.plotly_chart(px.line(df, x="date", y="score", markers=True, title="Progression dans le temps"), use_container_width=True)
        st.plotly_chart(px.bar(df, x="date", y="score", color="niveau", title="Évolution du niveau"), use_container_width=True)
    if st.button("Retour à l'accueil"):
        set_page("home")
        st.rerun()


def render_about(questions):
    counts = defaultdict(int)
    for q in questions:
        counts[q["section"]] += 1
    st.title("À propos du TCF")
    st.write("Le TCF Tout Public évalue la compréhension orale, la maîtrise des structures de la langue, la compréhension écrite et, selon l'inscription, les expressions écrite et orale.")
    st.write("Cette application est un outil d'entraînement pédagogique pour viser B2, C1 et progresser vers des usages avancés.")
    st.subheader("Format inclus")
    for section, meta in SECTION_META.items():
        total = counts.get(section, meta["expected"])
        st.write(f"- {meta['label']} : {total} question(s) ou tâche(s), durée {meta['duration'] // 60} min")
    st.caption("Les scores affichés sont des estimations d'entraînement et ne remplacent pas le barème officiel.")
    if st.button("Retour à l'accueil"):
        set_page("home")
        st.rerun()


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="TCF", layout="wide")
    init_state()
    render_header()
    render_ai_controls()
    questions = load_questions()

    page = st.session_state.page
    if page == "home":
        render_home(questions)
    elif page == "training":
        render_training(questions)
    elif page == "test":
        render_test(current_attempt_questions(questions))
    elif page == "correction":
        render_correction(current_attempt_questions(questions))
    elif page == "results":
        render_results()
    elif page == "about":
        render_about(questions)


if __name__ == "__main__":
    main()
