import io

from PIL import Image
import streamlit as st

from state import init_session_state
from ui.inputs import probability_input
from utils.backend_interface import (
    decode_image_payload,
    decode_image_payload_with_shape,
    encode_data,
    get_amino_acid_alphabet,
    get_encoders,
    get_ecc_profiles,
    get_profile_description,
    prepare_image_payload,
)

init_session_state()

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Manrope:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');

:root {
  --text-ink: #0f3328;
  --text-subtle: #1b7a5f;
  --primary: #1b7a5f;
  --primary-strong: #0f3328;
  --surface: #f7fbf8;
  --surface-soft: #e4f2eb;
  --line: #c9e2d6;
}

html, body, [class*="st-"], .stMarkdown, .stText, .stCaption {
  font-family: "Manrope", "Segoe UI", sans-serif !important;
}

h1, h2, h3, h4 {
  font-family: "Fraunces", Georgia, serif !important;
  color: var(--text-ink);
  letter-spacing: -0.02em;
}

/* Fix sidebar collapse button icon */
.material-icons,
.material-symbols-rounded,
.material-symbols-outlined,
[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"] span,
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapseButton"] button span,
[data-testid="stSidebarCollapsedControl"] span,
[data-testid="stSidebarCollapsedControl"] button span,
[data-testid="collapsedControl"] span,
[data-testid="collapsedControl"] button span,
button[kind="header"] span,
button[kind="headerNoPadding"] span {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
  font-weight: normal !important;
  font-style: normal !important;
  letter-spacing: normal !important;
  text-transform: none !important;
  line-height: 1 !important;
  -webkit-font-smoothing: antialiased;
  font-size: 24px !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] > div:first-child {
  padding-top: 2rem;
}

[data-testid="stSidebar"] {
  background: transparent;
  border-right: 1px solid rgba(27, 122, 95, 0.1);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color: var(--text-ink);
}

[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stRadio label {
  color: var(--text-ink) !important;
  font-weight: 600;
}

/* Main container */
[data-testid="stMainBlockContainer"] {
  max-width: 1000px;
  padding-top: 1rem !important;
}

/* Page header */
.page-header {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(27, 122, 95, 0.1);
}

.page-header h1 {
  margin: 0 0 0.5rem 0;
  font-size: clamp(2rem, 4vw, 2.8rem);
  line-height: 1.1;
}

.page-header p {
  margin: 0;
  color: var(--text-subtle);
  font-size: 1.05rem;
  max-width: 60ch;
}

/* Navigation */
.nav-pills {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.nav-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text-ink);
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 180ms ease;
}

.nav-pill:hover {
  background: rgba(27, 122, 95, 0.05);
  border-color: var(--primary);
  color: var(--primary);
}

/* Section styling */
.section-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 2rem 0 1rem 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-ink);
  letter-spacing: -0.01em;
}

.section-title::before {
  content: "";
  width: 4px;
  height: 1.2em;
  background: var(--primary);
  border-radius: 2px;
}

/* Input cards */
.input-card {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(27, 122, 95, 0.1);
  border-radius: 16px;
  padding: 1.5rem;
  margin-bottom: 1rem;
}

/* Metrics styling */
[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(27, 122, 95, 0.1);
  border-radius: 12px;
  padding: 1rem;
}

[data-testid="stMetric"] label {
  color: var(--text-subtle) !important;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.5rem;
}

/* Buttons */
.stButton > button {
  border-radius: 10px;
  border: 1px solid var(--primary) !important;
  font-weight: 600;
  transition: all 200ms ease;
}

.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(27, 122, 95, 0.2);
}

.stButton > button[kind="primary"] {
  background: var(--primary);
  color: white;
}

.stButton > button[kind="primary"]:hover {
  background: var(--primary-strong);
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  background: rgba(27, 122, 95, 0.05);
  border-radius: 12px;
  padding: 4px;
}

.stTabs [data-baseweb="tab"] {
  border-radius: 8px;
  padding: 0.6rem 1.2rem;
  font-weight: 600;
  color: var(--text-subtle);
}

.stTabs [aria-selected="true"] {
  background: white !important;
  color: var(--primary) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* Code blocks */
.stCodeBlock {
  border-radius: 10px;
  border: 1px solid rgba(27, 122, 95, 0.1);
}

/* Success/Error messages */
.stSuccess, .stError, .stInfo, .stWarning {
  border-radius: 10px;
  border: none;
}

.stSuccess {
  background: rgba(27, 122, 95, 0.1);
  color: var(--primary-strong);
}

/* Dividers */
hr {
  border: none;
  border-top: 1px solid rgba(27, 122, 95, 0.1);
  margin: 2rem 0;
}

/* Remove underlines from links */
a, a:visited, a:hover, a:active {
  text-decoration: none !important;
}

/* Expander styling */
.streamlit-expanderHeader {
  font-weight: 600;
  color: var(--text-ink);
}

/* File uploader */
[data-testid="stFileUploader"] {
  border: 2px dashed rgba(27, 122, 95, 0.2);
  border-radius: 12px;
  padding: 1rem;
  transition: all 200ms ease;
}

[data-testid="stFileUploader"]:hover {
  border-color: var(--primary);
  background: rgba(27, 122, 95, 0.02);
}

/* Results section */
.results-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.results-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  background: rgba(27, 122, 95, 0.1);
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--primary);
}

.results-badge--success {
  background: rgba(27, 122, 95, 0.15);
  color: var(--primary-strong);
}

.results-badge--error {
  background: rgba(220, 53, 69, 0.1);
  color: #dc3545;
}
</style>
""",
    unsafe_allow_html=True,
)

# Page header
st.markdown(
    """
<div class="page-header">
  <h1>Encode & Decode</h1>
  <p>Transform data into peptide sequences with configurable encoding, error correction, and error simulation.</p>
</div>
""",
    unsafe_allow_html=True,
)

# Navigation pills
st.markdown(
    """
<div class="nav-pills">
  <a class="nav-pill" href="/" target="_self">Home</a>
  <a class="nav-pill" href="/app" target="_self">Reader</a>
</div>
""",
    unsafe_allow_html=True,
)


def render_data_preview(title: str, data: bytes | None, preview_len: int) -> None:
    st.markdown(f"**{title}**")
    if not data:
        st.caption("No data available")
        return

    preview = data[:preview_len]
    st.code(preview.decode("utf-8", errors="replace"), language=None)

    shown = min(len(data), preview_len)
    if len(data) > preview_len:
        st.caption(f"Showing {shown} of {len(data)} bytes")
    else:
        st.caption(f"{shown} bytes")


# Sidebar configuration
with st.sidebar:
    st.markdown("## Configuration")
    st.caption("Adjust encoding parameters and error simulation settings.")

    st.markdown('<p class="section-title">Peptide Alphabet</p>', unsafe_allow_html=True)
    amino_acids = get_amino_acid_alphabet()
    st.code(" ".join(amino_acids), language=None)
    st.caption("8-letter alphabet (3 bits/amino acid)")

    st.markdown("---")

    st.markdown('<p class="section-title">Peptide Length</p>', unsafe_allow_html=True)
    peptide_length = st.slider(
        "Amino acids per peptide",
        min_value=6,
        max_value=30,
        value=18,
        step=1,
        help="Number of amino acids per peptide sequence",
        label_visibility="collapsed",
    )
    st.caption(f"{peptide_length} amino acids per sequence")

    st.markdown("---")

    st.markdown('<p class="section-title">Encoding Scheme</p>', unsafe_allow_html=True)
    encoder_options = get_encoders()
    encoder_labels = {
        "huffman": "Huffman",
        "yin_yang": "Yin-Yang",
        "fountain": "Fountain",
    }
    encoder = st.selectbox(
        "Encoder",
        options=encoder_options,
        index=0,
        help="Encoding scheme used to compress and map data",
        format_func=lambda value: encoder_labels.get(value, value),
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown('<p class="section-title">Error Correction</p>', unsafe_allow_html=True)
    ecc_profiles = get_ecc_profiles(encoder)
    ecc_profile = st.selectbox(
        "ECC Profile",
        options=ecc_profiles,
        index=0,
        help="Error correction code profile",
        label_visibility="collapsed",
    )
    st.info(get_profile_description(ecc_profile))

    st.markdown("---")

    st.markdown('<p class="section-title">Error Simulation</p>', unsafe_allow_html=True)

    error_model_choice = st.radio(
        "Error Model",
        options=["Uniform (basic)", "Scored (Pepsysco)"],
        index=0,
        help=(
            "Uniform: use fixed probabilities for all peptides. "
            "Scored: derive probabilities from per-peptide scores."
        ),
        label_visibility="collapsed",
    )

    error_model = "scored" if error_model_choice.startswith("Scored") else "basic"
    score_column = None
    loss_prob = 0.0
    mutation_prob = 0.0
    insertion_prob = 0.0
    shuffle_prob = 0.0

    if error_model == "basic":
        loss_prob = probability_input(
            "Peptide Loss (%)",
            default=0.0,
            help_text="Probability of entire peptide loss",
            key_prefix="loss_prob",
        )

        mutation_prob = probability_input(
            "Amino Acid Mutation (%)",
            default=0.0,
            help_text="Probability of amino acid substitution",
            key_prefix="mutation_prob",
        )

        insertion_prob = probability_input(
            "Amino Acid Insertion (%)",
            default=0.0,
            help_text="Probability of amino acid insertion",
            key_prefix="insertion_prob",
        )

        shuffle_prob = probability_input(
            "Amino Acid Shuffling (%)",
            default=0.0,
            help_text="Probability of amino acid order shuffling",
            key_prefix="shuffle_prob",
        )
    else:
        st.caption(
            "Scored mode fetches peptide scores from IEDB Pepsysco and derives "
            "error rates automatically."
        )
        score_column_input = st.text_input(
            "Score Column (optional)",
            value="",
            help="Leave empty to auto-detect a numeric score column in [0, 1].",
        )
        score_column = score_column_input.strip() or None

    shuffle_passes = st.number_input(
        "Shuffle Passes",
        min_value=1,
        max_value=10,
        value=1,
        help="Number of shuffle iterations",
    )

tab_encode, tab_results = st.tabs(["Encode", "Results"])

with tab_encode:
    st.markdown('<p class="section-title">Data Input</p>', unsafe_allow_html=True)

    input_method = st.radio(
        "Select Input Method:",
        options=["Text Input", "Image Upload"],
        horizontal=True,
        label_visibility="collapsed",
    )

    input_data = None
    input_metadata = {
        "input_method": input_method,
        "input_is_image": False,
        "input_filename": None,
        "input_image_format": None,
        "display_image_bytes": None,
        "payload_mode": None,
        "payload_width": None,
        "payload_height": None,
        "payload_channels": None,
    }

    if input_method == "Text Input":
        col1, col2 = st.columns([2, 1])
        with col1:
            text_input = st.text_area(
                "Enter text to encode:",
                height=200,
                placeholder="Type or paste your text here...",
                help="Enter any text data you want to encode into peptide sequences",
                label_visibility="collapsed",
            )

            if text_input:
                input_data = text_input.encode("utf-8")
                st.caption(f"{len(input_data)} bytes")

        with col2:
            if text_input:
                st.markdown("**Preview**")
                st.code(text_input[:200] + ("..." if len(text_input) > 200 else ""), language=None)

    else:
        uploaded_file = st.file_uploader(
            "Upload an image:",
            type=["png", "jpg", "jpeg", "bmp"],
            help="Upload an image file to encode into peptide sequences",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            uploaded_bytes = uploaded_file.read()
            col1, col2 = st.columns([1, 1])

            with col1:
                image = Image.open(io.BytesIO(uploaded_bytes))
                st.image(image, caption="Uploaded Image", use_container_width=True)

            with col2:
                image_format = image.format or "PNG"
                payload_info = prepare_image_payload(uploaded_bytes)
                input_data = payload_info["payload"]

                input_metadata.update(
                    {
                        "input_is_image": True,
                        "input_filename": uploaded_file.name,
                        "input_image_format": image_format,
                        "display_image_bytes": uploaded_bytes,
                        "payload_mode": "raw_pixels_with_header",
                        "payload_width": payload_info["width"],
                        "payload_height": payload_info["height"],
                        "payload_channels": payload_info["channels"],
                    }
                )

                st.markdown("**Image Details**")
                st.caption(f"Format: {image_format}")
                st.caption(f"Dimensions: {image.size[0]} x {image.size[1]}")
                st.caption(f"Mode: {image.mode}")
                st.caption(f"File size: {len(uploaded_bytes)} bytes")
                st.caption(f"Payload: {len(input_data)} bytes")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        encode_button = st.button(
            "Run Pipeline",
            type="primary",
            use_container_width=True,
            disabled=(input_data is None),
            help="Run the encoding pipeline with current configuration",
        )

    if encode_button and input_data is not None:
        with st.spinner("Processing..."):
            try:
                result = encode_data(
                    data=input_data,
                    peptide_length=peptide_length,
                    encoder=encoder,
                    ecc_profile=ecc_profile,
                    error_model=error_model,
                    score_column=score_column,
                    score_label=(
                        input_metadata.get("input_filename")
                        or ("text_input.txt" if input_method == "Text Input" else "uploaded_input.bin")
                    ),
                    loss_prob=loss_prob,
                    mutation_prob=mutation_prob,
                    insertion_prob=insertion_prob,
                    shuffle_prob=shuffle_prob,
                    shuffle_passes=shuffle_passes,
                )

                result["input_metadata"] = input_metadata
                result["run_config"] = {
                    "encoder": encoder,
                    "ecc_profile": ecc_profile,
                    "peptide_length": peptide_length,
                    "error_model": error_model,
                    "score_column": score_column,
                    "loss_prob": loss_prob,
                    "mutation_prob": mutation_prob,
                    "insertion_prob": insertion_prob,
                    "shuffle_prob": shuffle_prob,
                    "shuffle_passes": int(shuffle_passes),
                }
                st.session_state.current_result = result
                st.success("Complete! Switch to the Results tab to view output.")

            except Exception as exc:
                st.error(f"Error: {str(exc)}")
                st.exception(exc)

with tab_results:
    if st.session_state.current_result is not None:
        result = st.session_state.current_result
        encoded_peptides = result.get("encoded_peptides") or []
        run_cfg = result.get("run_config", {})

        # Status badge
        if result["success"]:
            st.markdown(
                '<span class="results-badge results-badge--success">Recovery Successful</span>',
                unsafe_allow_html=True,
            )
            st.caption("Original data was perfectly recovered despite simulated errors.")
        else:
            st.markdown(
                '<span class="results-badge results-badge--error">Recovery Failed</span>',
                unsafe_allow_html=True,
            )
            error_msg = (
                f"Bit Error Rate: {result['bit_error_rate']:.2f}% "
                f"({result['bit_errors']} errors / {result['total_bits']} bits)"
            )
            if "error" in result:
                error_msg += f" | {result['error']}"
            st.caption(error_msg)

        st.markdown("---")

        # Config summary
        st.caption(
            f"**Config:** {encoder_labels.get(run_cfg.get('encoder'), run_cfg.get('encoder', '-'))} encoder "
            f"| {run_cfg.get('ecc_profile', '-')} ECC "
            f"| {run_cfg.get('error_model', '-')} errors"
        )

        st.markdown('<p class="section-title">Metrics</p>', unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Original",
                value=f"{result['original_size']} B",
            )

        with col2:
            st.metric(
                label="Recovered",
                value=f"{result['recovered_size']} B",
                delta=f"{result['recovered_size'] - result['original_size']} B",
            )

        with col3:
            st.metric(
                label="Time",
                value=f"{result['encoding_time']:.2f}s",
            )

        with col4:
            st.metric(
                label="BER",
                value=f"{result['bit_error_rate']:.2f}%",
            )

        st.markdown("---")

        # Peptides preview
        if encoded_peptides:
            st.markdown('<p class="section-title">Peptide Sequences</p>', unsafe_allow_html=True)
            preview_count = st.slider(
                "Preview count",
                min_value=1,
                max_value=min(200, len(encoded_peptides)),
                value=min(20, len(encoded_peptides)),
                label_visibility="collapsed",
            )
            st.code("\n".join(encoded_peptides[:preview_count]), language=None)
            st.caption(f"{preview_count} of {len(encoded_peptides)} peptides")

        st.markdown("---")

        # Data comparison
        st.markdown('<p class="section-title">Data Comparison</p>', unsafe_allow_html=True)

        input_meta = result.get("input_metadata", {})
        is_image = bool(input_meta.get("input_is_image"))
        max_preview = max(
            result.get("original_size", 0),
            result.get("recovered_size", 0),
            1,
        )

        if is_image:
            col1, col2 = st.columns(2)
            original_size = None
            preview_mode = None

            with col1:
                st.markdown("**Original**")
                try:
                    original_image_bytes = input_meta.get("display_image_bytes") or result["original_data"]
                    original_image = Image.open(io.BytesIO(original_image_bytes))
                    original_size = original_image.size
                    preview_mode = (
                        original_image.mode
                        if original_image.mode in ("RGB", "L")
                        else "RGB"
                    )
                    st.image(
                        original_image,
                        caption=input_meta.get("input_filename") or "Original",
                        use_container_width=True,
                    )
                except Exception:
                    st.caption("Could not render original image.")

            with col2:
                st.markdown("**Recovered**")
                if result.get("recovered_data"):
                    payload_preview = decode_image_payload(result["recovered_data"])
                    if payload_preview is None and input_meta.get("payload_mode") == "raw_pixels_with_header":
                        payload_preview = decode_image_payload_with_shape(
                            result["recovered_data"],
                            width=int(input_meta.get("payload_width") or 0),
                            height=int(input_meta.get("payload_height") or 0),
                            channels=int(input_meta.get("payload_channels") or 0),
                        )
                    if payload_preview is not None:
                        st.image(
                            payload_preview,
                            caption="Recovered",
                            use_container_width=True,
                        )
                    else:
                        try:
                            recovered_image = Image.open(io.BytesIO(result["recovered_data"]))
                            preview_image = recovered_image
                            caption = "Recovered"
                            if original_size and recovered_image.size != original_size:
                                preview_image = recovered_image.resize(
                                    original_size,
                                    resample=Image.Resampling.NEAREST,
                                )
                                caption = f"Recovered (scaled)"
                            st.image(
                                preview_image,
                                caption=caption,
                                use_container_width=True,
                            )
                        except Exception:
                            raw_preview = None
                            if original_size and preview_mode:
                                recovered_bytes = result["recovered_data"]
                                bytes_per_pixel = 3 if preview_mode == "RGB" else 1
                                expected_len = original_size[0] * original_size[1] * bytes_per_pixel
                                if len(recovered_bytes) < expected_len:
                                    recovered_bytes = recovered_bytes + b"\x00" * (expected_len - len(recovered_bytes))
                                elif len(recovered_bytes) > expected_len:
                                    recovered_bytes = recovered_bytes[:expected_len]
                                try:
                                    raw_preview = Image.frombytes(
                                        preview_mode,
                                        original_size,
                                        recovered_bytes,
                                    )
                                except Exception:
                                    raw_preview = None
                            if raw_preview is not None:
                                st.image(
                                    raw_preview,
                                    caption="Recovered (raw)",
                                    use_container_width=True,
                                )
                            else:
                                st.caption("Recovered data is not a valid image.")
                else:
                    st.caption("No data recovered")

            st.markdown("---")

        # Raw data preview
        default_preview = min(500, max_preview)
        step = 100 if max_preview >= 100 else 1

        preview_len = st.slider(
            "Preview bytes",
            min_value=1,
            max_value=max_preview,
            value=default_preview,
            step=step,
            label_visibility="collapsed",
        )

        col1, col2 = st.columns(2)

        with col1:
            render_data_preview("Original", result.get("original_data"), preview_len)

        with col2:
            render_data_preview("Recovered", result.get("recovered_data"), preview_len)

    else:
        st.markdown(
            """
<div style="text-align: center; padding: 4rem 2rem; color: var(--text-subtle);">
  <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No results yet</p>
  <p style="font-size: 0.9rem; opacity: 0.7;">Run the pipeline from the Encode tab to see results here.</p>
</div>
""",
            unsafe_allow_html=True,
        )
