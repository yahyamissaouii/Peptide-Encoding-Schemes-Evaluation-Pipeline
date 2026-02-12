"""Reusable Streamlit input widgets."""

import streamlit as st


def probability_input(
    label: str,
    default: float,
    help_text: str,
    key_prefix: str,
    min_value: float = 0.0,
    max_value: float = 50.0,
    step: float = 0.5,
) -> float:
    slider_key = f"{key_prefix}_slider"
    input_key = f"{key_prefix}_input"

    if slider_key not in st.session_state and input_key not in st.session_state:
        st.session_state[slider_key] = default
        st.session_state[input_key] = default
    elif slider_key in st.session_state and input_key not in st.session_state:
        st.session_state[input_key] = st.session_state[slider_key]
    elif input_key in st.session_state and slider_key not in st.session_state:
        st.session_state[slider_key] = st.session_state[input_key]

    def slider_changed() -> None:
        st.session_state[input_key] = st.session_state[slider_key]

    def input_changed() -> None:
        st.session_state[slider_key] = st.session_state[input_key]

    col1, col2 = st.columns([3, 1])
    with col1:
        st.slider(
            label,
            min_value=min_value,
            max_value=max_value,
            step=step,
            help=help_text,
            key=slider_key,
            on_change=slider_changed,
        )
    with col2:
        st.number_input(
            "Value (%)",
            min_value=min_value,
            max_value=max_value,
            step=step,
            key=input_key,
            on_change=input_changed,
            label_visibility="collapsed",
        )

    return float(st.session_state[slider_key]) / 100.0
