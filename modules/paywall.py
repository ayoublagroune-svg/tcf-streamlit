import os

import streamlit as st

from . import db


FREE_DAILY_QUESTIONS = 20
FREE_WRITING_CORRECTIONS = 1
FREE_MOCK_EXAMS = 1


def is_premium(user):
    return bool(user and user.get("is_premium"))


def can_answer_question(user):
    if is_premium(user):
        return True, ""
    usage = db.get_usage_today(user["id"]) if user else {"questions_answered": 0}
    if usage["questions_answered"] < FREE_DAILY_QUESTIONS:
        return True, ""
    return False, "Limite gratuite atteinte: 20 questions par jour."


def can_use_writing_correction(user):
    if is_premium(user):
        return True, ""
    usage = db.get_usage_today(user["id"]) if user else {"writing_corrections_used": 0}
    if usage["writing_corrections_used"] < FREE_WRITING_CORRECTIONS:
        return True, ""
    return False, "Limite gratuite atteinte: 1 correction écrite IA par jour."


def can_take_mock_exam(user):
    if is_premium(user):
        return True, ""
    usage = db.get_usage_today(user["id"]) if user else {"mock_exams_used": 0}
    if usage["mock_exams_used"] < FREE_MOCK_EXAMS:
        return True, ""
    return False, "Limite gratuite atteinte: 1 examen blanc court par jour."


def show_upgrade_message():
    st.info("Passe Premium pour débloquer les examens illimités, l'historique complet et les questions B2/C1 avancées.")


def create_checkout_session(user):
    if not os.getenv("STRIPE_SECRET_KEY") or not os.getenv("STRIPE_PRICE_ID"):
        return None, "Paiement bientôt disponible."
    return None, "Stripe est configuré côté variables, mais le checkout complet sera branché à la prochaine itération."
