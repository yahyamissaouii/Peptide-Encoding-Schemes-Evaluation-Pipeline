import streamlit as st

from state import init_session_state
from utils.shared_styles import (
    render_page_styles,
    render_nav_pills,
    render_page_header,
    render_page_footer,
)

st.set_page_config(
    page_title="About | Peptide Encoding",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

# Render consistent styles and navigation
render_page_styles()
render_page_header(
    "About",
    "Information about this project and the research behind peptide-based data storage.",
)
render_nav_pills("about")

st.markdown(
    """
This web application is part of a **Bachelor thesis** on peptide-based data storage encoding schemes.

### Project Overview

Peptide-based data storage represents a novel approach to archival data storage, leveraging the stability and
density of biological molecules. This application provides tools for:

- **Encoding & Decoding**: Transform digital data into peptide sequences and back
- **Error Simulation**: Model real-world errors that occur during peptide synthesis and sequencing
- **Visualization**: Step-by-step visualization of error models affecting peptide sequences

### Research Context

This project explores various encoding schemes and error correction codes to maximize data recovery
rates in the presence of typical biological errors such as:

- Residue deletions
- Residue substitutions (mutations)
- Residue insertions
- Local sequence shuffling

### Technologies

- **Python** for the core encoding/decoding pipeline
- **Streamlit** for the interactive web interface
- **Reed-Solomon** error correction codes
- **Huffman** and **Yin-Yang** encoding schemes
"""
)

render_page_footer()
