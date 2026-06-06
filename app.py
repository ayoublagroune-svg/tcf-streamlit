import csv
import hashlib
import io
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfdoc
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


APP_TITLE = "TCF Tout Public - Examen Blanc"
QUESTIONS_PATH = Path("questions.json")


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
        "history": [],
        "result_saved": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def set_page(page):
    st.session_state.page = page


def reset_attempt(sections):
    st.session_state.answers = {}
    st.session_state.writing_answers = {}
    st.session_state.speaking_notes = {}
    st.session_state.active_sections = sections
    st.session_state.section_index = 0
    st.session_state.section_started_at = time.time()
    st.session_state.attempt_started_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.result_saved = False
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
                "reponse_utilisateur": item["user_answer"],
                "bonne_reponse": item["bonne_reponse"],
                "correct": item["correct"],
                "explication": item["explication"],
                "rappel_regle": item["rappel_regle"],
                "astuce_tcf": item["astuce_tcf"],
            }
            for item in score["items"]
        ],
        "expression_ecrite": st.session_state.writing_answers,
        "expression_orale": st.session_state.speaking_notes,
    }


def csv_bytes(payload):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "section",
            "theme",
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
    st.markdown('<span class="badge">Objectif B2</span>', unsafe_allow_html=True)
    st.write("Entraînez-vous avec un examen blanc complet, des corrections détaillées et un tableau de bord de progression.")

    cols = st.columns(3)
    with cols[0]:
        metric_card("Questions QCM", len(questions))
    with cols[1]:
        metric_card("Durée estimée", "2 h 37")
    with cols[2]:
        metric_card("Niveau visé", "B2")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Passer un examen complet", use_container_width=True, type="primary"):
            reset_attempt(EXAM_ORDER.copy())
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


def render_training():
    st.title("S'entraîner par compétence")
    labels = {meta["label"]: key for key, meta in SECTION_META.items()}
    choice = st.selectbox("Compétence", list(labels))
    if st.button("Commencer l'entraînement", type="primary"):
        reset_attempt([labels[choice]])
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


def render_mcq_section(section_key, questions, expired):
    disabled = expired
    for index, q in enumerate(questions_by_section(questions, section_key), start=1):
        with st.container(border=True):
            st.subheader(f"Question {index}")
            st.caption(f"Thème : {q['theme'].replace('_', ' ')} | Niveau : {q['niveau']}")
            st.write(q["consigne"])
            if section_key == "comprehension_orale":
                st.info(f"Vous entendez : {q['texte']}")
                if q.get("audio_file"):
                    st.audio(q["audio_file"])
            else:
                st.write(q["texte"])
            options = [f"{key}. {value}" for key, value in q["choix"].items()]
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
    for task in WRITING_TASKS:
        with st.container(border=True):
            st.subheader(task["title"])
            st.write(task["prompt"])
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


def render_speaking_section(expired):
    st.info("Préparation écrite uniquement pour cette version. Une zone d'enregistrement audio pourra être ajoutée plus tard.")
    for task in SPEAKING_TASKS:
        with st.container(border=True):
            st.subheader(task["title"])
            st.write(task["prompt"])
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
    render_dashboard(score)

    if score["weak_themes"]:
        st.subheader("À revoir en priorité")
        for index, (theme, count) in enumerate(score["weak_themes"].most_common(5), start=1):
            st.write(f"{index}. {theme.replace('_', ' ')} ({count} erreur(s))")

    st.subheader("Détail des réponses")
    for idx, item in enumerate(score["items"], start=1):
        status = "✓ Correct" if item["correct"] else "✗ Incorrect"
        with st.expander(f"Question {idx} - {status} - {item['theme'].replace('_', ' ')}", expanded=not item["correct"]):
            st.write(f"**Votre réponse :** {item['user_answer'] or 'Aucune réponse'}")
            st.write(f"**Bonne réponse :** {item['bonne_reponse']} - {item['choix'][item['bonne_reponse']]}")
            st.write(f"**Explication :** {item['explication']}")
            if not item["correct"]:
                st.write(f"**Pourquoi c'est incorrect :** la réponse attendue correspond à l'indice principal de la question et à la règle testée.")
            st.write(f"**Rappel :** {item['rappel_regle']}")
            st.write(f"**Conseil pratique :** notez ce thème dans votre carnet d'erreurs et refaites trois phrases similaires.")
            st.write(f"**Astuce TCF :** {item['astuce_tcf']}")

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
    st.write("Cette application est un outil d'entraînement pédagogique pour consolider un niveau B1 et viser B2.")
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
    questions = load_questions()

    page = st.session_state.page
    if page == "home":
        render_home(questions)
    elif page == "training":
        render_training()
    elif page == "test":
        render_test(questions)
    elif page == "correction":
        render_correction(questions)
    elif page == "results":
        render_results()
    elif page == "about":
        render_about(questions)


if __name__ == "__main__":
    main()
