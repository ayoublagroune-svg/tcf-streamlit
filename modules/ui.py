import json
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from . import ai_tools, auth, db, exam_engine, paywall, questions, scoring


SKILL_LABELS = {
    "comprehension_ecrite": "Compréhension écrite",
    "comprehension_orale": "Compréhension orale",
    "structure_langue": "Structure de la langue",
    "expression_ecrite": "Expression écrite",
}


def inject_style():
    st.markdown(
        """
        <style>
        .main .block-container {max-width: 1120px; padding-top: 2rem;}
        .metric-row [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            padding: 14px 16px;
        }
        .hero {
            padding: 2.2rem 0 1rem;
            border-bottom: 1px solid #eceef4;
            margin-bottom: 1.2rem;
        }
        .hero h1 {font-size: 2.6rem; line-height: 1.08; margin-bottom: .45rem;}
        .muted {color: #5e6678;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    user = auth.current_user()
    st.sidebar.title("TCF Coach IA")
    if user:
        badge = "Premium" if paywall.is_premium(user) else "Gratuit"
        st.sidebar.caption(f"{user['email']} · {badge}")
    else:
        st.sidebar.caption("Non connecté")
    pages = ["Accueil", "Dashboard", "Entraînement", "Examen blanc", "Expression écrite", "Premium", "Connexion / Déconnexion"]
    st.session_state.setdefault("page", "Accueil")
    hinted_page = st.session_state.pop("nav_hint", None)
    if hinted_page in pages:
        st.session_state.page = hinted_page
    page = st.sidebar.radio(
        "Menu",
        pages,
        index=pages.index(st.session_state.page) if st.session_state.page in pages else 0,
        key="page",
        label_visibility="collapsed",
    )
    stats = questions.get_question_stats()
    st.sidebar.divider()
    st.sidebar.caption(f"{stats['total']} questions originales locales")
    st.sidebar.caption("IA: disponible" if ai_tools.detect_ai_available() else "IA: non configurée")
    return page


def render_landing_page():
    st.markdown(
        """
        <div class="hero">
          <h1>Prépare ton TCF avec un coach IA personnalisé</h1>
          <p class="muted">Entraîne-toi avec des examens blancs proches du vrai TCF, analyse tes erreurs et progresse vers B2/C1.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Commencer gratuitement", type="primary", use_container_width=True):
            st.session_state.nav_hint = "Entraînement"
            st.rerun()
    with c2:
        if st.button("Passer Premium", use_container_width=True):
            st.session_state.nav_hint = "Premium"
            st.rerun()

    st.subheader("Un entraînement pensé comme un vrai parcours TCF")
    cols = st.columns(3)
    items = [
        ("Examen blanc réaliste", "Temps limité, score final et estimation CECRL."),
        ("Questions niveau TCF", "Formats originaux inspirés des compétences attendues."),
        ("Correction pédagogique", "Explication claire après chaque réponse en entraînement."),
        ("Analyse des points faibles", "Compétences, niveaux et erreurs fréquentes suivis."),
        ("Coach IA", "Correction écrite disponible si une clé IA est configurée."),
        ("Suivi de progression", "Historique SQLite persistant par utilisateur."),
    ]
    for index, (title, body) in enumerate(items):
        with cols[index % 3]:
            st.markdown(f"**{title}**")
            st.caption(body)

    st.info("Application indépendante, non affiliée à France Éducation international. Les niveaux affichés sont des estimations non officielles.")


def render_auth_page():
    user = auth.current_user()
    if user:
        st.subheader("Compte")
        st.write(f"Connecté avec **{user['email']}**.")
        if st.button("Déconnexion"):
            auth.logout()
            st.rerun()
        return

    tab_login, tab_register = st.tabs(["Connexion", "Inscription"])
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", type="primary")
        if submitted:
            user = auth.login(email, password)
            if user:
                st.success("Connexion réussie.")
                st.rerun()
            else:
                st.error("Email ou mot de passe incorrect.")

    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Mot de passe", type="password", key="register_password")
            submitted = st.form_submit_button("Créer mon compte", type="primary")
        if submitted:
            if len(password) < 8:
                st.error("Choisis un mot de passe d'au moins 8 caractères.")
            else:
                try:
                    user = auth.register(email, password)
                    st.session_state.user = user
                    st.success("Compte créé.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def require_user():
    user = auth.current_user()
    if not user:
        st.warning("Connecte-toi pour enregistrer ta progression et appliquer les limites gratuites.")
        render_auth_page()
        return None
    return user


def render_dashboard():
    user = require_user()
    if not user:
        return
    stats = db.get_user_dashboard_stats(user["id"])
    st.subheader("Dashboard utilisateur")
    st.markdown('<div class="metric-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Score moyen", f"{stats['average_score']}%")
    c2.metric("Niveau estimé CECRL", stats["estimated_level"])
    c3.metric("Examens sauvegardés", len(stats["history"]))
    st.markdown("</div>", unsafe_allow_html=True)

    if stats["by_skill"]:
        chart_rows = [
            {"Compétence": SKILL_LABELS.get(skill, skill), "Réussite": round(values["correct"] / values["total"] * 100, 1)}
            for skill, values in stats["by_skill"].items()
            if values["total"]
        ]
        st.plotly_chart(px.bar(pd.DataFrame(chart_rows), x="Compétence", y="Réussite", range_y=[0, 100]), use_container_width=True)

    st.write("**Derniers examens**")
    if stats["history"]:
        st.dataframe(
            pd.DataFrame(stats["history"])[["created_at", "mode", "section", "score", "total", "estimated_level"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Aucun examen sauvegardé pour le moment.")

    st.write("**Erreurs fréquentes**")
    if stats["frequent_errors"]:
        for name, count in stats["frequent_errors"]:
            st.write(f"- {name.replace('_', ' ')}: {count} erreur(s)")
    else:
        st.caption("Pas encore assez de données.")

    st.write("**Recommandations**")
    for item in ai_tools.generate_revision_plan(stats):
        st.write(f"- {item}")


def _question_answer(question, key):
    st.markdown(f"**{SKILL_LABELS.get(question['skill'], question['skill'])} · {question['level']} · {question['type']}**")
    if question["context"]:
        st.info(question["context"])
    st.write(question["prompt"])
    selected = st.radio("Réponse", question["choices"], key=key, label_visibility="collapsed")
    return selected[0] if selected else None


def render_training_page():
    user = require_user()
    if not user:
        return
    st.subheader("Mode entraînement")
    c1, c2 = st.columns(2)
    skill = c1.selectbox("Compétence", ["comprehension_ecrite", "comprehension_orale", "structure_langue"], format_func=lambda x: SKILL_LABELS[x])
    level = c2.selectbox("Niveau", ["A2", "B1", "B2", "C1"])
    pool = questions.filter_questions(skill=skill, level=level, premium_only=paywall.is_premium(user))
    if not pool:
        st.warning("Aucune question disponible pour ce filtre. Essaie un autre niveau.")
        return
    if not paywall.is_premium(user):
        pool = [q for q in pool if q["level"] not in ("C1",)]
    question = pool[st.session_state.get("training_index", 0) % len(pool)]
    selected = _question_answer(question, f"training_{question['id']}")
    if st.button("Valider la réponse", type="primary"):
        allowed, message = paywall.can_answer_question(user)
        if not allowed:
            st.error(message)
            paywall.show_upgrade_message()
            return
        is_correct = selected == question["correct_answer"]
        db.save_question_attempt(user["id"], question["id"], selected, question["correct_answer"], is_correct, question["skill"], question["level"])
        db.increment_usage(user["id"], questions=1)
        st.success("Bonne réponse." if is_correct else f"Réponse correcte: {question['correct_answer']}")
        st.write(question["explanation"])
    if st.button("Question suivante"):
        st.session_state.training_index = st.session_state.get("training_index", 0) + 1
        st.rerun()


def render_exam_page():
    user = require_user()
    if not user:
        return
    st.subheader("Examen blanc TCF")
    st.caption("Correction masquée jusqu'à la fin. Estimation CECRL non officielle.")
    if "exam" not in st.session_state:
        allowed, message = paywall.can_take_mock_exam(user)
        if not allowed:
            st.error(message)
            paywall.show_upgrade_message()
            return
        if st.button("Démarrer un examen blanc court", type="primary"):
            st.session_state.exam = exam_engine.start_exam(short=True, include_premium=paywall.is_premium(user))
            db.increment_usage(user["id"], mock_exams=1)
            st.rerun()
        return

    exam = st.session_state.exam
    elapsed = int(time.time() - exam["started_at"])
    remaining = max(exam["duration_seconds"] - elapsed, 0)
    st.progress(1 - remaining / exam["duration_seconds"])
    st.caption(f"Temps restant: {remaining // 60:02d}:{remaining % 60:02d}")

    if remaining == 0:
        exam["finished"] = True

    if not exam.get("finished"):
        current = exam_engine.get_next_question(exam)
        if current:
            selected = _question_answer(current, f"exam_{current['id']}")
            if st.button("Enregistrer et continuer", type="primary"):
                exam_engine.submit_answer(exam, current["id"], selected)
                st.rerun()
        answered = len(exam.get("answers", {}))
        total = len(exam.get("questions", []))
        st.caption(f"{answered}/{total} réponses enregistrées")
        if answered == total or st.button("Terminer l'examen"):
            exam["finished"] = True
            st.rerun()
        return

    report = exam_engine.generate_exam_report(exam)
    st.metric("Score final", f"{report['score']}/{report['total']}", f"{report['percent']}%")
    st.metric("Niveau estimé", report["estimated_level"])
    st.caption(report["disclaimer"])
    if not exam.get("saved"):
        db.save_test_session(user["id"], "examen_blanc", "global", report["score"], report["total"], report["estimated_level"], report)
        for detail in report["details"]:
            db.save_question_attempt(
                user["id"],
                detail["question_id"],
                detail["selected_answer"],
                detail["correct_answer"],
                detail["is_correct"],
                detail["skill"],
                detail["level"],
            )
        exam["saved"] = True
    with st.expander("Analyse détaillée"):
        for detail in report["details"]:
            status = "correct" if detail["is_correct"] else "à revoir"
            st.write(f"**{detail['question_id']}** · {status} · réponse: {detail['selected_answer']} / {detail['correct_answer']}")
            st.caption(detail["explanation"])
    if st.button("Nouvel examen"):
        st.session_state.pop("exam", None)
        st.rerun()


def render_writing_page():
    user = require_user()
    if not user:
        return
    st.subheader("Expression écrite")
    level = st.selectbox("Niveau cible", ["A2", "B1", "B2", "C1"], index=2)
    prompt = questions.writing_prompts(level)[0]
    st.info(prompt["prompt"])
    text = st.text_area("Production", height=260)
    if st.button("Demander une correction IA", type="primary"):
        allowed, message = paywall.can_use_writing_correction(user)
        if not allowed:
            st.error(message)
            paywall.show_upgrade_message()
            return
        result = ai_tools.correct_writing(prompt["prompt"], text)
        db.increment_usage(user["id"], writing_corrections=1)
        db.save_writing_submission(user["id"], prompt["prompt"], text, result["feedback"], result["estimated_level"])
        if result["available"]:
            st.success("Correction générée.")
        else:
            st.warning(result["feedback"])
        st.write(result["feedback"])


def render_pricing_page():
    user = auth.current_user()
    st.subheader("Premium")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Gratuit**")
        st.write("- 20 questions par jour")
        st.write("- 1 examen blanc court par jour")
        st.write("- 1 correction écrite IA par jour")
    with c2:
        st.write("**Premium**")
        st.write("- Examens blancs illimités")
        st.write("- Historique complet")
        st.write("- Correction IA complète")
        st.write("- Plans de révision personnalisés")
        st.write("- Questions avancées B2/C1")
    if st.button("Passer Premium", type="primary"):
        _session, message = paywall.create_checkout_session(user)
        st.info(message)


def render_page(page):
    if page == "Accueil":
        render_landing_page()
    elif page == "Dashboard":
        render_dashboard()
    elif page == "Entraînement":
        render_training_page()
    elif page == "Examen blanc":
        render_exam_page()
    elif page == "Expression écrite":
        render_writing_page()
    elif page == "Premium":
        render_pricing_page()
    else:
        render_auth_page()
