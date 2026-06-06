import hashlib
import hmac
import os

import streamlit as st

from . import db

try:
    from passlib.context import CryptContext
except ImportError:
    CryptContext = None


PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def hash_password(password, salt=None):
    if PWD_CONTEXT:
        return PWD_CONTEXT.hash(password)
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password, stored_hash):
    if PWD_CONTEXT and not stored_hash.startswith("pbkdf2_sha256$"):
        return PWD_CONTEXT.verify(password, stored_hash)
    try:
        algo, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, expected)


def register(email, password):
    if db.get_user_by_email(email):
        raise ValueError("Un compte existe déjà avec cet email.")
    return db.create_user(email, hash_password(password))


def login(email, password):
    user = db.get_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        st.session_state.user = user
        return user
    return None


def logout():
    st.session_state.pop("user", None)


def current_user():
    user = st.session_state.get("user")
    if user:
        fresh = db.get_user(user["id"])
        st.session_state.user = fresh
        return fresh
    return None
