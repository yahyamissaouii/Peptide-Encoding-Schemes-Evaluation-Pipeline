"""Session state helpers for Streamlit pages."""

import streamlit as st


def init_session_state() -> None:
    if "current_result" not in st.session_state:
        st.session_state.current_result = None
