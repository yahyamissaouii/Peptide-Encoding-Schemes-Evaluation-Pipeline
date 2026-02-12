import streamlit as st

from state import init_session_state

st.set_page_config(
    page_title="About | Peptide Encoding",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

st.title("About")

st.markdown(
    """
This web application is part of a **Bachelor thesis** on peptide-based data storage encoding schemes.
"""
)

st.markdown("---")
st.markdown("*Built with Streamlit | Copyright 2025 Goethe University Frankfurt*")
