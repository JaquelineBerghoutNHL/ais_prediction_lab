import streamlit as st
import hmac
import os

def controleer_login():
    if st.session_state.get("ingelogd", False):
        return

    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        </style>
    """, unsafe_allow_html=True)

    wachtwoord = st.text_input("Wachtwoord", type="password")

    if st.button("Inloggen"):
        verwacht = os.getenv("APP_PASSWORD")

        if not verwacht:
            st.error("APP_PASSWORD is niet ingesteld.")
        elif hmac.compare_digest(wachtwoord, verwacht):
            st.session_state["ingelogd"] = True
            st.rerun()
        else:
            st.error("Verkeerd wachtwoord")

    st.stop()