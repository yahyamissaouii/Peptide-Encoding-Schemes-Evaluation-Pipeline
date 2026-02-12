"""Shared styles and navigation components for consistent page design."""

from __future__ import annotations

import streamlit as st

# Route constants
ROUTES = {
    "home": "/",
    "reader": "/app",
    "encoder": "/encode",
    "visualizer": "/error-visualizer",
    "about": "/about",
}

# Navigation labels
NAV_LABELS = {
    "home": "Home",
    "reader": "Reader",
    "encoder": "Encode & Decode",
    "visualizer": "Visualizer",
    "about": "About",
}


def render_page_styles() -> None:
    """Render consistent page styles across all pages."""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Manrope:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');

:root {
  --space-1: 0.5rem;
  --space-2: 1rem;
  --space-3: 1.5rem;
  --space-4: 2rem;
  --space-5: 3rem;
  --text-ink: #0f3328;
  --text-subtle: #1b7a5f;
  --surface: #f7fbf8;
  --surface-soft: #e4f2eb;
  --card: #ffffffda;
  --line: #c9e2d6;
  --primary: #1b7a5f;
  --primary-strong: #0f3328;
  --secondary: #d7efe6;
  --secondary-strong: #1b7a5f;
  --focus: #0f3328;
}

html, body, [class*="st-"], .stMarkdown, .stText, .stCaption {
  font-family: "Manrope", "Segoe UI", sans-serif !important;
}

h1, h2, h3, h4 {
  font-family: "Fraunces", Georgia, serif !important;
  color: var(--text-ink);
  letter-spacing: -0.02em;
}

/* Fix Material icons */
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

/* App background */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(80rem 35rem at 5% -5%, #e9f7ef 0%, transparent 60%),
    radial-gradient(80rem 35rem at 95% -15%, #d6efe3 0%, transparent 55%),
    linear-gradient(180deg, #f7fbf8 0%, #e4f2eb 100%);
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
  max-width: 1100px;
  padding-top: 1rem !important;
}

/* Page header */
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid rgba(27, 122, 95, 0.1);
}

.page-header h1 {
  margin: 0 0 0.5rem 0;
  font-size: clamp(1.9rem, 4vw, 2.7rem);
  line-height: 1.1;
}

.page-header p {
  margin: 0;
  color: var(--text-subtle);
  font-size: 1.05rem;
  max-width: 65ch;
}

/* Navigation pills */
.nav-pills {
  display: flex;
  flex-wrap: wrap;
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
  color: var(--text-ink) !important;
  text-decoration: none !important;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 180ms ease;
}

.nav-pill:hover {
  background: rgba(27, 122, 95, 0.05);
  border-color: var(--primary);
  color: var(--primary) !important;
}

.nav-pill.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white !important;
}

/* Section title */
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

/* Results badges */
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

/* Footer */
.page-footer {
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(27, 122, 95, 0.1);
  text-align: center;
  color: var(--text-subtle);
  font-size: 0.9rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_nav_pills(current_page: str) -> None:
    """Render navigation pills with the current page highlighted.

    Args:
        current_page: Key from NAV_LABELS to mark as active (e.g., "encoder", "reader")
    """
    pills = []
    for key in ["home", "reader", "encoder", "visualizer"]:
        active_class = " active" if key == current_page else ""
        pills.append(
            f'<a class="nav-pill{active_class}" href="{ROUTES[key]}" target="_self">{NAV_LABELS[key]}</a>'
        )

    st.markdown(
        f'<div class="nav-pills">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


def render_page_header(title: str, description: str) -> None:
    """Render a consistent page header.

    Args:
        title: Page title
        description: Page description
    """
    st.markdown(
        f"""
<div class="page-header">
  <h1>{title}</h1>
  <p>{description}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_page_footer() -> None:
    """Render a consistent page footer."""
    st.markdown(
        """
<div class="page-footer">
  Built with Streamlit | Goethe University Frankfurt | 2025
</div>
""",
        unsafe_allow_html=True,
    )
