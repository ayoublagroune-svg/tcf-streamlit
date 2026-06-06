import streamlit as st

from modules import db, ui


st.set_page_config(page_title="TCF Coach IA", page_icon="TCF", layout="wide")


def main():
    db.init_db()
    ui.inject_style()
    page = ui.render_sidebar()
    st.title("TCF Coach IA")
    ui.render_page(page)


if __name__ == "__main__":
    main()
