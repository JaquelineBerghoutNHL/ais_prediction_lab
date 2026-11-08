import streamlit as st
import hmac

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
        if hmac.compare_digest(wachtwoord, st.secrets["APP_PASSWORD"]):
            st.session_state["ingelogd"] = True
            st.rerun()
        else:
            st.error("Verkeerd wachtwoord")

    st.stop()