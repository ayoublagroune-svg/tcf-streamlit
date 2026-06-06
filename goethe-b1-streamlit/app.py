import csv
import hashlib
import html
import io
import json
import os
import random
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


APP_TITLE = "Goethe-Zertifikat B1 Trainer"
QUESTIONS_PATH = Path(__file__).with_name("questions.json")
AI_ENABLED = False
AI_DEFAULT_MODEL = "gpt-4.1-mini"
AI_MAX_CALLS_PER_SESSION = 10
AI_INPUT_CHAR_LIMIT = 6000
AI_OUTPUT_TOKEN_LIMIT = 1600


def _md5_compat(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return hashlib.md5(*args, **kwargs)


pdfdoc.md5 = _md5_compat

MODULE_META = {
    "lesen": {
        "label": "Lesen",
        "short": "Lesen",
        "duration": 65 * 60,
        "expected": 30,
        "kind": "mcq",
        "parts": 5,
    },
    "hoeren": {
        "label": "Hören",
        "short": "Hören",
        "duration": 40 * 60,
        "expected": 30,
        "kind": "mcq",
        "parts": 4,
    },
    "schreiben": {
        "label": "Schreiben",
        "short": "Schreiben",
        "duration": 60 * 60,
        "expected": 3,
        "kind": "writing",
        "parts": 3,
    },
    "sprechen": {
        "label": "Sprechen",
        "short": "Sprechen",
        "duration": 15 * 60,
        "expected": 3,
        "kind": "speaking",
        "parts": 3,
    },
}

EXAM_ORDER = list(MODULE_META)


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    return text[:limit] + "\n\n[Text gekürzt, um API-Kosten zu begrenzen.]"


def ai_cache_key(prompt, max_tokens):
    raw = f"{ai_model()}::{max_tokens}::{truncate_for_ai(prompt)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def call_ai(prompt, max_tokens=AI_OUTPUT_TOKEN_LIMIT):
    if not ai_is_enabled():
        return "KI-Modus ist deaktiviert. Aktivieren Sie ihn in der Seitenleiste."
    if not ai_is_configured():
        return "Keine OpenAI-API-Key konfiguriert. Die App funktioniert weiter ohne KI."
    if OpenAI is None:
        return "OpenAI SDK fehlt. Bitte installieren Sie die Abhängigkeiten aus requirements.txt."

    cache_key = ai_cache_key(prompt, max_tokens)
    if cache_key in st.session_state.ai_cache:
        return st.session_state.ai_cache[cache_key]
    if st.session_state.ai_call_count >= AI_MAX_CALLS_PER_SESSION:
        return f"Limit erreicht: maximal {AI_MAX_CALLS_PER_SESSION} KI-Aufrufe pro Session."

    client = OpenAI(api_key=openai_api_key())
    try:
        response = client.responses.create(
            model=ai_model(),
            input=[{"role": "user", "content": truncate_for_ai(prompt)}],
            max_output_tokens=max_tokens,
        )
    except Exception as exc:
        if "insufficient_quota" in str(exc):
            return "OpenAI-Quota unzureichend. Bitte Credits oder Billing im OpenAI-Konto aktivieren."
        return f"OpenAI-Fehler: {exc}"

    st.session_state.ai_call_count += 1
    if getattr(response, "status", None) == "incomplete":
        return "KI-Antwort unvollständig. Bitte erneut versuchen."
    output = response.output_text or "Keine KI-Antwort erhalten."
    st.session_state.ai_cache[cache_key] = output
    return output


def load_questions():
    with QUESTIONS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def init_state():
    defaults = {
        "page": "home",
        "answers": {},
        "writing_answers": {},
        "speaking_notes": {},
        "active_modules": EXAM_ORDER.copy(),
        "module_index": 0,
        "module_started_at": None,
        "attempt_started_at": None,
        "attempt_question_ids": [],
        "writing_task_ids": [],
        "speaking_task_ids": [],
        "history": [],
        "result_saved": False,
        "error_counts": {},
        "errors_saved": False,
        "ai_outputs": {},
        "ai_cache": {},
        "ai_call_count": 0,
        "ai_enabled": env_bool("AI_ENABLED", AI_ENABLED),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def set_page(page):
    st.session_state.page = page


def questions_by_module(questions, module):
    return [q for q in questions if q["module"] == module and q["type"] == "mcq"]


def tasks_by_module(questions, module):
    return [q for q in questions if q["module"] == module and q["type"] in {"writing", "speaking"}]


def interleave_by_part_and_theme(items):
    groups = defaultdict(list)
    for item in items:
        groups[(item.get("part"), item.get("theme"))].append(item)
    for group in groups.values():
        random.shuffle(group)
    keys = list(groups)
    random.shuffle(keys)
    ordered = []
    while keys:
        next_keys = []
        for key in keys:
            if groups[key]:
                ordered.append(groups[key].pop())
            if groups[key]:
                next_keys.append(key)
        keys = next_keys
    return ordered


def signature_for_question(question):
    raw = f"{question.get('module')}::{question.get('part')}::{question.get('theme')}::{question.get('question')}::{question.get('text')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def select_attempt_question_ids(all_questions, modules):
    selected = []
    for module in modules:
        meta = MODULE_META[module]
        if meta["kind"] != "mcq":
            continue
        pool = questions_by_module(all_questions, module)
        target = min(meta["expected"], len(pool))
        candidates = random.sample(pool, len(pool))
        selected_items = []
        seen_signatures = set()
        for item in candidates:
            signature = signature_for_question(item)
            if signature in seen_signatures:
                continue
            selected_items.append(item)
            seen_signatures.add(signature)
            if len(selected_items) >= target:
                break
        if len(selected_items) < target:
            selected_ids = {item["id"] for item in selected_items}
            selected_items.extend(item for item in candidates if item["id"] not in selected_ids)
            selected_items = selected_items[:target]
        selected.extend(item["id"] for item in interleave_by_part_and_theme(selected_items))
    return selected


def select_task_ids(all_questions, module):
    tasks = tasks_by_module(all_questions, module)
    by_part = defaultdict(list)
    for task in tasks:
        by_part[task["part"]].append(task)
    selected = []
    for part in sorted(by_part):
        selected.append(random.choice(by_part[part])["id"])
    return selected


def current_attempt_questions(all_questions):
    ids = st.session_state.get("attempt_question_ids", [])
    if not ids:
        ids = select_attempt_question_ids(all_questions, st.session_state.active_modules)
        st.session_state.attempt_question_ids = ids
    by_id = {item["id"]: item for item in all_questions}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def current_tasks(all_questions, module):
    state_key = "writing_task_ids" if module == "schreiben" else "speaking_task_ids"
    ids = st.session_state.get(state_key, [])
    if not ids:
        ids = select_task_ids(all_questions, module)
        st.session_state[state_key] = ids
    by_id = {item["id"]: item for item in all_questions}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def reset_attempt(modules, all_questions):
    st.session_state.answers = {}
    st.session_state.writing_answers = {}
    st.session_state.speaking_notes = {}
    st.session_state.active_modules = modules
    st.session_state.attempt_question_ids = select_attempt_question_ids(all_questions, modules)
    st.session_state.writing_task_ids = select_task_ids(all_questions, "schreiben") if "schreiben" in modules else []
    st.session_state.speaking_task_ids = select_task_ids(all_questions, "sprechen") if "sprechen" in modules else []
    st.session_state.module_index = 0
    st.session_state.module_started_at = time.time()
    st.session_state.attempt_started_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.result_saved = False
    st.session_state.errors_saved = False
    set_page("test")


def format_seconds(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def estimate_result(percent):
    if percent >= 80:
        return "sehr gut"
    if percent >= 70:
        return "gut"
    if percent >= 60:
        return "bestanden"
    return "noch nicht bestanden"


def score_attempt(questions):
    scored = []
    for q in questions:
        user_answer = st.session_state.answers.get(q["id"])
        correct = user_answer == q["answer"]
        scored.append({**q, "user_answer": user_answer, "correct": correct})

    total = len(scored)
    correct_count = sum(item["correct"] for item in scored)
    percent = round(correct_count / total * 100, 1) if total else 0
    by_module = []
    for module, meta in MODULE_META.items():
        module_items = [item for item in scored if item["module"] == module]
        if not module_items:
            continue
        ok = sum(item["correct"] for item in module_items)
        pct = round(ok / len(module_items) * 100, 1)
        by_module.append(
            {
                "module": module,
                "Modul": meta["short"],
                "richtige Antworten": ok,
                "Items": len(module_items),
                "Score": pct,
                "Ergebnis": estimate_result(pct),
            }
        )
    weak_themes = Counter(item["theme"] for item in scored if not item["correct"])
    return {
        "items": scored,
        "total": total,
        "correct": correct_count,
        "incorrect": total - correct_count,
        "percent": percent,
        "result": estimate_result(percent),
        "by_module": by_module,
        "weak_themes": weak_themes,
    }


def build_report_payload(questions):
    score = score_attempt(questions)
    return {
        "date": datetime.now().isoformat(timespec="seconds"),
        "score": score["percent"],
        "ergebnis": score["result"],
        "richtige_antworten": score["correct"],
        "falsche_antworten": score["incorrect"],
        "details_module": score["by_module"],
        "themen_wiederholen": score["weak_themes"].most_common(),
        "antworten": [
            {
                "id": item["id"],
                "module": item["module"],
                "part": item["part"],
                "theme": item["theme"],
                "question": item["question"],
                "user_answer": item["user_answer"],
                "answer": item["answer"],
                "correct": item["correct"],
                "explanation": item["explanation"],
                "strategy": item["strategy"],
            }
            for item in score["items"]
        ],
        "schreiben": st.session_state.writing_answers,
        "sprechen": st.session_state.speaking_notes,
    }


def csv_bytes(payload):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "module", "part", "theme", "question", "user_answer", "answer", "correct", "explanation", "strategy"],
    )
    writer.writeheader()
    writer.writerows(payload["antworten"])
    return output.getvalue().encode("utf-8")


def pdf_bytes(payload):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(APP_TITLE, styles["Title"]),
        Paragraph(f"Datum: {payload['date']}", styles["Normal"]),
        Paragraph(f"Score: {payload['score']} % - Ergebnis: {payload['ergebnis']}", styles["Heading2"]),
        Paragraph("Dieser Score ist eine Trainingsschätzung und ersetzt keine offizielle Goethe-Bewertung.", styles["Italic"]),
        Spacer(1, 12),
        Paragraph("Module", styles["Heading2"]),
    ]
    rows = [["Modul", "Score", "Ergebnis"]]
    rows += [[row["Modul"], f"{row['Score']} %", row["Ergebnis"]] for row in payload["details_module"]]
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [table, Spacer(1, 12), Paragraph("Korrektur", styles["Heading2"])]
    for item in payload["antworten"]:
        result = "Richtig" if item["correct"] else "Falsch"
        story.append(Paragraph(f"{item['id']} - {item['module']} - {result}", styles["Heading3"]))
        story.append(Paragraph(f"Aufgabe: {item['question']}", styles["Normal"]))
        story.append(Paragraph(f"Ihre Antwort: {item['user_answer'] or 'Keine'} | Lösung: {item['answer']}", styles["Normal"]))
        story.append(Paragraph(f"Erklärung: {item['explanation']}", styles["Normal"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    return buffer.getvalue()


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


def render_ai_controls():
    with st.sidebar:
        st.subheader("KI-Modus")
        st.session_state.ai_enabled = st.checkbox(
            "KI aktivieren",
            value=st.session_state.get("ai_enabled", AI_ENABLED),
            help="Standardmäßig aus. KI wird nur über explizite Buttons aufgerufen.",
        )
        if ai_is_enabled() and ai_is_configured():
            remaining = max(0, AI_MAX_CALLS_PER_SESSION - st.session_state.ai_call_count)
            st.caption(f"Modell: {ai_model()} - {remaining} Aufruf(e) übrig.")
        elif ai_is_enabled():
            st.caption("KI aktiv, aber kein API-Key konfiguriert.")
        else:
            st.caption("KI aus. Die lokale Aufgabenbank funktioniert ohne Kosten.")


def render_home(questions):
    st.title(APP_TITLE)
    st.markdown('<span class="badge">Goethe-Zertifikat B1</span>', unsafe_allow_html=True)
    st.write("Trainieren Sie mit prüfungsnahen Aufgaben für Lesen, Hören, Schreiben und Sprechen.")

    counts = Counter(item["module"] for item in questions)
    cols = st.columns(4)
    for col, module in zip(cols, EXAM_ORDER):
        with col:
            st.metric(MODULE_META[module]["label"], counts[module], f"{MODULE_META[module]['parts']} Teil(e)")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Komplette Prüfung starten", type="primary", use_container_width=True):
            reset_attempt(EXAM_ORDER.copy(), questions)
            st.rerun()
        if st.button("Meine Ergebnisse", use_container_width=True):
            set_page("results")
            st.rerun()
    with c2:
        if st.button("Nach Modul trainieren", use_container_width=True):
            set_page("training")
            st.rerun()
        if st.button("Prüfungsformat", use_container_width=True):
            set_page("about")
            st.rerun()


def render_training(questions):
    st.title("Nach Modul trainieren")
    labels = {meta["label"]: key for key, meta in MODULE_META.items()}
    choice = st.selectbox("Modul", list(labels))
    if st.button("Training starten", type="primary"):
        reset_attempt([labels[choice]], questions)
        st.rerun()
    if st.button("Zurück"):
        set_page("home")
        st.rerun()


def render_timer(module_key):
    meta = MODULE_META[module_key]
    if st.session_state.module_started_at is None:
        st.session_state.module_started_at = time.time()
    elapsed = time.time() - st.session_state.module_started_at
    remaining = meta["duration"] - elapsed
    progress = min(1.0, max(0.0, elapsed / meta["duration"]))
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("Restzeit", format_seconds(remaining))
    with c2:
        st.progress(progress, text=f"{meta['label']} - {round(progress * 100)} % der Zeit")
    return remaining <= 0


def advance_module():
    if st.session_state.module_index + 1 >= len(st.session_state.active_modules):
        set_page("correction")
        return
    st.session_state.module_index += 1
    st.session_state.module_started_at = time.time()


def render_audio(question):
    text = html.escape(json.dumps(question["text"], ensure_ascii=False), quote=True)
    element_id = f"audio_{question['id']}"
    components.html(
        f"""
        <div id="{element_id}" style="display:flex;gap:10px;align-items:center;margin:8px 0 14px 0;">
          <button type="button" style="background:#2563eb;color:white;border:0;border-radius:6px;padding:10px 14px;font-weight:700;cursor:pointer;"
            onclick="window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance({text}); u.lang='de-DE'; u.rate=0.9; window.speechSynthesis.speak(u);">
            Audio hören
          </button>
          <button type="button" style="background:#e2e8f0;color:#0f172a;border:0;border-radius:6px;padding:10px 14px;font-weight:700;cursor:pointer;"
            onclick="window.speechSynthesis.cancel();">Stop</button>
          <span style="color:#475569;font-size:14px;">Browser-Sprachausgabe für Training.</span>
        </div>
        """,
        height=62,
    )


def render_mcq_module(module_key, questions, expired):
    module_questions = questions_by_module(questions, module_key)
    for index, q in enumerate(module_questions, start=1):
        with st.container(border=True):
            st.subheader(f"Aufgabe {index}")
            st.caption(f"Teil {q['part']} | Thema: {q['theme'].replace('_', ' ')}")
            st.write(q["instruction"])
            if module_key == "hoeren":
                render_audio(q)
                st.caption("Die Transkription sehen Sie erst in der Korrektur.")
            else:
                st.write(q["text"])
            st.write(q["question"])
            options = [f"{key}. {value}" for key, value in q["choices"].items()]
            current = st.session_state.answers.get(q["id"])
            index_value = list(q["choices"]).index(current) if current in q["choices"] else None
            selected = st.radio(
                "Ihre Antwort",
                options,
                index=index_value,
                key=f"answer_{q['id']}",
                disabled=expired,
            )
            if selected and not expired:
                st.session_state.answers[q["id"]] = selected.split(".", 1)[0]


def writing_feedback_prompt(task, answer):
    return f"""
Du bist Prüfer für Goethe-Zertifikat B1 Schreiben. Antworte auf Deutsch, klar und knapp.
Bewerte nicht offiziell, sondern gib Training-Feedback.

Aufgabe:
{task['prompt']}

Antwort:
{answer}

Gib:
1. geschätztes Niveau,
2. Erfüllung der Inhaltspunkte,
3. wichtigste Fehler,
4. verbesserte Version,
5. drei konkrete Tipps.
Maximal 350 Wörter.
"""


def render_writing_module(tasks, expired):
    st.info("Goethe B1 Schreiben: Aufgabe 1 E-Mail, Aufgabe 2 Forumsbeitrag, Aufgabe 3 formelle Nachricht.")
    for task in tasks:
        with st.container(border=True):
            st.subheader(f"Aufgabe {task['part']}: {task['title']}")
            st.write(task["prompt"])
            st.caption(task["expected"])
            value = st.text_area(
                "Ihre Antwort",
                value=st.session_state.writing_answers.get(task["id"], ""),
                key=f"writing_{task['id']}",
                height=190,
                disabled=expired,
            )
            if not expired:
                st.session_state.writing_answers[task["id"]] = value
            st.metric("Wörter", len(value.split()))
            ai_key = f"writing_feedback_{task['id']}"
            if st.button("Mit KI korrigieren", key=f"ai_{task['id']}", disabled=not value.strip()):
                with st.spinner("KI-Korrektur läuft..."):
                    st.session_state.ai_outputs[ai_key] = call_ai(writing_feedback_prompt(task, value))
            if ai_key in st.session_state.ai_outputs:
                st.markdown(st.session_state.ai_outputs[ai_key])


def render_speaking_module(tasks, expired):
    st.info("Goethe B1 Sprechen: gemeinsam planen, Thema präsentieren, Rückfragen/Feedback.")
    for task in tasks:
        with st.container(border=True):
            st.subheader(f"Teil {task['part']}: {task['title']}")
            st.write(task["prompt"])
            notes = st.text_area(
                "Notizen zur Vorbereitung",
                value=st.session_state.speaking_notes.get(task["id"], ""),
                key=f"speaking_{task['id']}",
                height=150,
                disabled=expired,
            )
            if not expired:
                st.session_state.speaking_notes[task["id"]] = notes


def render_test(all_questions):
    module_key = st.session_state.active_modules[st.session_state.module_index]
    meta = MODULE_META[module_key]
    st.title(meta["label"])
    st.caption(f"Modul {st.session_state.module_index + 1} / {len(st.session_state.active_modules)}")
    expired = render_timer(module_key)
    if expired:
        st.warning("Zeit abgelaufen: Antworten sind gesperrt.")

    if meta["kind"] == "mcq":
        render_mcq_module(module_key, current_attempt_questions(all_questions), expired)
    elif meta["kind"] == "writing":
        render_writing_module(current_tasks(all_questions, "schreiben"), expired)
    else:
        render_speaking_module(current_tasks(all_questions, "sprechen"), expired)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Startseite"):
            set_page("home")
            st.rerun()
    with c2:
        label = "Beenden und korrigieren" if st.session_state.module_index + 1 >= len(st.session_state.active_modules) else "Nächstes Modul"
        if st.button(label, type="primary", use_container_width=True):
            advance_module()
            st.rerun()


def render_dashboard(score):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Score", f"{score['percent']} %")
    with c2:
        st.metric("Ergebnis", score["result"])
    with c3:
        st.metric("Richtig", score["correct"])
    with c4:
        st.metric("Falsch", score["incorrect"])

    st.caption("Goethe B1 ist modular. In der echten Prüfung wird jedes Modul separat bewertet; diese App ist ein Training.")
    df = pd.DataFrame(score["by_module"])
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            radar = go.Figure(data=go.Scatterpolar(r=df["Score"], theta=df["Modul"], fill="toself", name="Score"))
            radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
            st.plotly_chart(radar, use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(df, x="Modul", y="Score", color="Ergebnis", range_y=[0, 100]), use_container_width=True)
    if score["weak_themes"]:
        theme_df = pd.DataFrame(score["weak_themes"].most_common(), columns=["Thema", "Fehler"])
        st.plotly_chart(px.bar(theme_df, x="Thema", y="Fehler", title="Fehler nach Thema"), use_container_width=True)


def save_history_once(payload):
    if st.session_state.result_saved:
        return
    st.session_state.history.append({"date": payload["date"], "score": payload["score"], "ergebnis": payload["ergebnis"], "details": payload["details_module"]})
    st.session_state.result_saved = True


def save_error_counts_once(score):
    if st.session_state.errors_saved:
        return
    counts = Counter(st.session_state.error_counts)
    counts.update(item["theme"] for item in score["items"] if not item["correct"])
    st.session_state.error_counts = dict(counts)
    st.session_state.errors_saved = True


def render_correction(questions):
    st.title("Korrektur")
    score = score_attempt(questions)
    payload = build_report_payload(questions)
    save_history_once(payload)
    save_error_counts_once(score)
    render_dashboard(score)

    if score["weak_themes"]:
        st.subheader("Wiederholen")
        for index, (theme, count) in enumerate(score["weak_themes"].most_common(6), start=1):
            st.write(f"{index}. {theme.replace('_', ' ')} ({count} Fehler)")

    st.subheader("Details")
    for index, item in enumerate(score["items"], start=1):
        status = "Richtig" if item["correct"] else "Falsch"
        with st.expander(f"Aufgabe {index} - {status} - {item['theme'].replace('_', ' ')}", expanded=not item["correct"]):
            if item["module"] == "hoeren":
                st.write(f"**Transkription:** {item['text']}")
            else:
                st.write(f"**Text:** {item['text']}")
            st.write(f"**Frage:** {item['question']}")
            for key, value in item["choices"].items():
                st.write(f"{key}. {value}")
            st.write(f"**Ihre Antwort:** {item['user_answer'] or 'Keine Antwort'}")
            st.write(f"**Lösung:** {item['answer']} - {item['choices'][item['answer']]}")
            st.write(f"**Erklärung:** {item['explanation']}")
            st.write(f"**Strategie:** {item['strategy']}")

    st.subheader("Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("PDF", pdf_bytes(payload), "goethe_b1_report.pdf", "application/pdf", use_container_width=True)
    with c2:
        st.download_button("CSV", csv_bytes(payload), "goethe_b1_report.csv", "text/csv", use_container_width=True)
    with c3:
        st.download_button("JSON", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "goethe_b1_report.json", "application/json", use_container_width=True)

    if st.button("Zurück zur Startseite"):
        set_page("home")
        st.rerun()


def render_results():
    st.title("Meine Ergebnisse")
    if not st.session_state.history:
        st.info("Noch keine abgeschlossene Prüfung.")
    else:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df[["date", "score", "ergebnis"]], use_container_width=True)
        st.plotly_chart(px.line(df, x="date", y="score", markers=True, title="Fortschritt"), use_container_width=True)
    if st.button("Zurück"):
        set_page("home")
        st.rerun()


def render_about():
    st.title("Prüfungsformat Goethe B1")
    st.write("Diese App orientiert sich am offiziellen Aufbau des Goethe-Zertifikats B1, verwendet aber eigene Trainingsaufgaben.")
    st.write("- Lesen: 5 Teile, 65 Minuten, ungefähr 30 Items")
    st.write("- Hören: 4 Teile, 40 Minuten, ungefähr 30 Items")
    st.write("- Schreiben: 3 Aufgaben, 60 Minuten")
    st.write("- Sprechen: 3 Aufgaben, circa 15 Minuten plus Vorbereitung")
    st.caption("Offizielle Muster und Übungsmaterialien finden Sie beim Goethe-Institut. Diese App ersetzt keine offizielle Prüfung.")
    if st.button("Zurück"):
        set_page("home")
        st.rerun()


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="B1", layout="wide")
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
        render_test(questions)
    elif page == "correction":
        render_correction(current_attempt_questions(questions))
    elif page == "results":
        render_results()
    elif page == "about":
        render_about()


if __name__ == "__main__":
    main()
