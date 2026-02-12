"""Thesis showcase app with dedicated landing and reader routes."""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st
import streamlit.components.v1 as components

from utils.thesis_content import load_thesis_content
from utils.thesis_outline import flatten_outline_entries, load_outline

APP_DIR = Path(__file__).resolve().parent
THESIS_PDF = APP_DIR / "Missaoui_Yahya_thesis_final.pdf"
SECTIONS_MAPPING = APP_DIR / "thesis_sections.json"
THESIS_STRUCTURE = APP_DIR / "thesis_structure.json"

LANDING_ROUTE = "/"
READER_ROUTE = "/app"
ENCODE_ROUTE = "/encode"


st.set_page_config(
    page_title="Thesis Showcase",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_global_styles() -> None:
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

html, body, [class*="st-"], .stMarkdown, .stCaption, .stTextInput > label, .stRadio > label {
  font-family: "Manrope", "Segoe UI", sans-serif;
}

h1, h2, h3, h4 {
  font-family: "Fraunces", Georgia, serif;
  color: var(--text-ink);
  letter-spacing: -0.02em;
}

/* Preserve Streamlit Material icons; otherwise icon names render as plain text. */
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

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(80rem 35rem at 5% -5%, #e9f7ef 0%, transparent 60%),
    radial-gradient(80rem 35rem at 95% -15%, #d6efe3 0%, transparent 55%),
    linear-gradient(180deg, #f7fbf8 0%, #e4f2eb 100%);
}

[data-testid="stMainBlockContainer"] {
  padding-top: var(--space-4);
  padding-bottom: var(--space-5);
}

a:focus-visible,
button:focus-visible,
[role="button"]:focus-visible,
input:focus-visible,
[tabindex]:focus-visible {
  outline: 3px solid var(--focus) !important;
  outline-offset: 2px !important;
}

a,
a:visited,
[data-testid="stMarkdownContainer"] a,
[data-testid="stMarkdownContainer"] a:visited {
  color: var(--primary);
  text-decoration-color: var(--primary);
}

a:hover,
a:active,
[data-testid="stMarkdownContainer"] a:hover,
[data-testid="stMarkdownContainer"] a:active {
  color: var(--primary-strong);
  text-decoration-color: var(--primary-strong);
}

/* Remove underlines from button-style links */
.hero-cta,
.hero-cta:visited,
.hero-cta:hover,
.hero-cta:active,
.section-link,
.section-link:visited,
.section-link:hover,
.section-link:active,
.reader-jump,
.reader-jump:visited,
.reader-jump:hover,
.reader-jump:active,
.scroll-indicator,
.scroll-indicator:visited,
.scroll-indicator:hover,
.scroll-indicator:active,
[data-testid="stLinkButton"] a,
[data-testid="stLinkButton"] a:visited,
[data-testid="stLinkButton"] a:hover,
[data-testid="stLinkButton"] a:active {
  text-decoration: none !important;
}

/* Keep URL text white when rendered inside green primary link-buttons. */
[data-testid="stLinkButton"] a[kind="primary"],
[data-testid="stLinkButton"] a[data-kind="primary"],
a.hero-cta-primary,
a.hero-cta-primary:visited {
  color: #ffffff !important;
}

.reader-body {
  max-width: 76ch;
  color: var(--text-ink);
  line-height: 1.72;
  font-size: 1.04rem;
}

.reader-body p {
  margin: 0 0 var(--space-2) 0;
}

.reader-meta {
  display: inline-block;
  margin-top: 0.35rem;
  margin-bottom: var(--space-2);
  padding: 0.38rem 0.75rem;
  border-radius: 999px;
  background: #d7efe6;
  border: 1px solid #c9e2d6;
  color: #0f3328;
  font-size: 0.82rem;
  font-weight: 600;
}

.side-muted {
  color: var(--text-subtle);
  font-size: 0.92rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _load_pdf_bytes(pdf_path: str) -> bytes:
    return Path(pdf_path).read_bytes()


@st.cache_data(show_spinner=False)
def _load_thesis_data(
    pdf_path: str, mapping_path: str, pdf_mtime: float, mapping_mtime: float
) -> dict:
    del pdf_mtime, mapping_mtime
    return load_thesis_content(pdf_path=Path(pdf_path), mapping_path=Path(mapping_path))


def _render_pdf_preview(pdf_bytes: bytes, height: int = 860) -> None:
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    components.html(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded}"
            width="100%"
            height="{height}"
            style="border:1px solid #c6d7cc; border-radius: 16px; box-shadow: 0 12px 26px rgba(28, 57, 45, 0.12);"
            type="application/pdf"
        ></iframe>
        """,
        height=height + 22,
        scrolling=True,
    )


def _parse_latex_content(text: str) -> str:
    """Parse LaTeX-style content and convert to styled HTML."""
    result = html.escape(text)

    # Handle \cite{key} or \cite{key1, key2} - make clickable citations
    def replace_cite(match: re.Match) -> str:
        keys = match.group(1)
        citations = [k.strip() for k in keys.split(",")]
        links = []
        for cite_key in citations:
            links.append(
                f'<a href="#bib-{cite_key}" class="citation" data-cite="{html.escape(cite_key)}">'
                f'{html.escape(cite_key)}</a>'
            )
        return '<span class="cite-group">[' + ", ".join(links) + ']</span>'

    result = re.sub(r"\\cite\{([^}]+)\}", replace_cite, result)

    # Handle \textit{text} - italic
    result = re.sub(r"\\textit\{([^}]+)\}", r'<em>\1</em>', result)

    # Handle \textbf{text} - bold
    result = re.sub(r"\\textbf\{([^}]+)\}", r'<strong>\1</strong>', result)

    # Handle \emph{text} - emphasis
    result = re.sub(r"\\emph\{([^}]+)\}", r'<em>\1</em>', result)

    # Handle \texttt{text} - monospace/code
    result = re.sub(r"\\texttt\{([^}]+)\}", r'<code class="latex-code">\1</code>', result)

    # Handle inline math $...$
    def replace_inline_math(match: re.Match) -> str:
        math_content = match.group(1)
        return f'<span class="math-inline">{math_content}</span>'

    result = re.sub(r"\$([^$]+)\$", replace_inline_math, result)

    # Handle display math \[...\] or $$...$$
    def replace_display_math(match: re.Match) -> str:
        math_content = match.group(1)
        return f'<div class="math-display">{math_content}</div>'

    result = re.sub(r"\\\[(.+?)\\\]", replace_display_math, result, flags=re.DOTALL)
    result = re.sub(r"\$\$(.+?)\$\$", replace_display_math, result, flags=re.DOTALL)

    # Handle \ref{label} - references
    result = re.sub(
        r"\\ref\{([^}]+)\}",
        r'<a href="#ref-\1" class="ref-link">[\1]</a>',
        result
    )

    # Handle \label{label}
    result = re.sub(
        r"\\label\{([^}]+)\}",
        r'<span id="ref-\1" class="ref-anchor"></span>',
        result
    )

    # Handle \url{...}
    result = re.sub(
        r"\\url\{([^}]+)\}",
        r'<a href="\1" class="url-link" target="_blank">\1</a>',
        result
    )

    # Handle \href{url}{text}
    result = re.sub(
        r"\\href\{([^}]+)\}\{([^}]+)\}",
        r'<a href="\1" class="url-link" target="_blank">\2</a>',
        result
    )

    # Handle \footnote{text}
    result = re.sub(
        r"\\footnote\{([^}]+)\}",
        r'<span class="footnote" title="\1"><sup>*</sup></span>',
        result
    )

    # Handle \includegraphics[options]{path}
    def replace_figure(match: re.Match) -> str:
        options = match.group(1) or ""
        img_path = match.group(2)
        # Extract width if specified
        width_match = re.search(r'width\s*=\s*([^,\]]+)', options)
        width_style = ""
        if width_match:
            width_val = width_match.group(1).strip()
            # Convert LaTeX widths to CSS
            if "\\textwidth" in width_val or "\\linewidth" in width_val:
                factor = re.search(r'([\d.]+)', width_val)
                if factor:
                    pct = float(factor.group(1)) * 100
                    width_style = f'style="max-width: {pct}%"'
                else:
                    width_style = 'style="max-width: 100%"'
            elif "cm" in width_val or "in" in width_val or "px" in width_val:
                width_style = f'style="max-width: {width_val}"'

        # Build figure HTML - path will be resolved by frontend
        return (
            f'<figure class="latex-figure">'
            f'<img src="/app/static/figures/{html.escape(img_path)}" '
            f'alt="{html.escape(img_path)}" class="latex-figure-img" {width_style} '
            f'onerror="this.parentElement.innerHTML=\'<div class=figure-placeholder>'
            f'Figure: {html.escape(img_path)}</div>\'">'
            f'</figure>'
        )

    result = re.sub(
        r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}",
        replace_figure,
        result
    )

    # Handle \begin{figure}...\end{figure} environment
    def replace_figure_env(match: re.Match) -> str:
        content = match.group(1)

        # Extract caption if present
        caption_match = re.search(r"\\caption\{([^}]+)\}", content)
        caption = caption_match.group(1) if caption_match else ""

        # Extract label if present
        label_match = re.search(r"\\label\{([^}]+)\}", content)
        label = label_match.group(1) if label_match else ""
        label_id = f'id="ref-{html.escape(label)}"' if label else ""

        # Find includegraphics
        img_match = re.search(r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}", content)
        if img_match:
            options = img_match.group(1) or ""
            img_path = img_match.group(2)

            width_style = 'style="max-width: 100%"'
            width_match = re.search(r'width\s*=\s*([^,\]]+)', options)
            if width_match:
                width_val = width_match.group(1).strip()
                if "\\textwidth" in width_val or "\\linewidth" in width_val:
                    factor = re.search(r'([\d.]+)', width_val)
                    if factor:
                        pct = float(factor.group(1)) * 100
                        width_style = f'style="max-width: {pct}%"'

            return (
                f'<figure class="latex-figure" {label_id}>'
                f'<img src="/app/static/figures/{html.escape(img_path)}" '
                f'alt="{html.escape(caption or img_path)}" class="latex-figure-img" {width_style} '
                f'onerror="this.parentElement.querySelector(\'.latex-figure-img\')?.remove(); '
                f'this.parentElement.insertAdjacentHTML(\'afterbegin\', '
                f'\'<div class=figure-placeholder>Figure: {html.escape(img_path)}</div>\')">'
                f'{f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""}'
                f'</figure>'
            )

        return f'<div class="figure-placeholder">[Figure environment]</div>'

    result = re.sub(
        r"\\begin\{figure\}.*?(?:\\centering)?(.+?)\\end\{figure\}",
        replace_figure_env,
        result,
        flags=re.DOTALL
    )

    # Handle common symbols
    result = result.replace("\\%", "%")
    result = result.replace("\\&", "&amp;")
    result = result.replace("\\$", "$")
    result = result.replace("\\#", "#")
    result = result.replace("\\textasciitilde", "~")
    result = result.replace("---", "—")  # em dash
    result = result.replace("--", "–")   # en dash
    result = result.replace("``", '"')
    result = result.replace("''", '"')
    result = result.replace("`", "'")

    # Handle \newline or \\
    result = re.sub(r"\\\\|\\newline", "<br>", result)

    return result


def _parse_bibtex(bibtex_content: str) -> list[dict]:
    """Parse BibTeX content and return list of bibliography entries."""
    entries = []

    # Match BibTeX entries: @type{key, ... }
    entry_pattern = re.compile(
        r'@(\w+)\s*\{\s*([^,]+)\s*,([^@]*?)(?=\n\s*@|\n\s*$|\Z)',
        re.DOTALL | re.MULTILINE
    )

    for match in entry_pattern.finditer(bibtex_content):
        entry_type = match.group(1).lower()
        cite_key = match.group(2).strip()
        fields_text = match.group(3)

        # Parse individual fields
        fields = {}
        # Match field = {value} or field = "value" or field = value
        field_pattern = re.compile(
            r'(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)"|(\d+))',
            re.DOTALL
        )

        for field_match in field_pattern.finditer(fields_text):
            field_name = field_match.group(1).lower()
            # Get value from whichever group matched
            field_value = (
                field_match.group(2) or
                field_match.group(3) or
                field_match.group(4) or
                ""
            )
            # Clean up whitespace
            field_value = re.sub(r'\s+', ' ', field_value).strip()
            fields[field_name] = field_value

        entries.append({
            'type': entry_type,
            'key': cite_key,
            'fields': fields
        })

    return entries


def _render_bibliography_html(bibtex_content: str) -> str:
    """Render BibTeX content as styled HTML bibliography."""
    entries = _parse_bibtex(bibtex_content)

    if not entries:
        return "<p>No bibliography entries found.</p>"

    html_parts = ['<div class="bibliography">']

    for entry in entries:
        key = entry['key']
        fields = entry['fields']
        entry_type = entry['type']

        # Extract common fields
        authors = fields.get('author', 'Unknown Author')
        title = fields.get('title', 'Untitled')
        year = fields.get('year', '')

        # Clean up title (remove extra braces)
        title = re.sub(r'\{|\}', '', title)

        # Format authors (convert "and" to ", ")
        authors = authors.replace(' and ', ', ')

        # Build citation details based on type
        details = []

        if entry_type == 'article':
            if fields.get('journal'):
                details.append(f'<span class="bib-venue">{html.escape(fields["journal"])}</span>')
            if fields.get('volume'):
                vol = fields['volume']
                if fields.get('number'):
                    vol += f'({fields["number"]})'
                details.append(f'<span class="bib-volume">{html.escape(vol)}</span>')
            if fields.get('pages'):
                details.append(f'<span class="bib-pages">pp. {html.escape(fields["pages"])}</span>')

        elif entry_type == 'inproceedings' or entry_type == 'conference':
            if fields.get('booktitle'):
                details.append(f'<span class="bib-venue">In: {html.escape(fields["booktitle"])}</span>')
            if fields.get('pages'):
                details.append(f'<span class="bib-pages">pp. {html.escape(fields["pages"])}</span>')

        elif entry_type == 'book':
            if fields.get('publisher'):
                details.append(f'<span class="bib-publisher">{html.escape(fields["publisher"])}</span>')

        elif entry_type == 'misc' or entry_type == 'online':
            if fields.get('howpublished'):
                details.append(f'<span class="bib-venue">{html.escape(fields["howpublished"])}</span>')
            if fields.get('note'):
                details.append(f'<span class="bib-note">{html.escape(fields["note"])}</span>')

        # Build URL link if available
        url_html = ''
        url = fields.get('url') or fields.get('doi')
        if url:
            if url and not url.startswith('http'):
                url = f'https://doi.org/{url}'
            url = url.strip()
            url_html = f'<a href="{html.escape(url)}" class="bib-link" target="_blank">View</a>'

        # Build the entry HTML
        details_html = ' · '.join(details) if details else ''

        html_parts.append(f'''
<div class="bib-entry" id="bib-{html.escape(key)}">
  <div class="bib-header">
    <span class="bib-key">{html.escape(key)}</span>
    {f'<span class="bib-year">{html.escape(year)}</span>' if year else ''}
  </div>
  <div class="bib-authors">{html.escape(authors)}</div>
  <div class="bib-title">{html.escape(title)}</div>
  {f'<div class="bib-details">{details_html}</div>' if details_html else ''}
  {f'<div class="bib-actions">{url_html}</div>' if url_html else ''}
</div>
''')

    html_parts.append('</div>')
    return ''.join(html_parts)


def _is_bibtex_content(text: str) -> bool:
    """Check if text appears to be BibTeX content."""
    return bool(re.search(r'@\w+\s*\{', text))


def _paragraphs_html(text: str, max_chars: int, max_paragraphs: int) -> str:
    compact = text.strip()
    if not compact or compact == "...":
        return "<p>Text extraction unavailable for this section.</p>"

    clipped = compact[:max_chars]
    if len(compact) > max_chars:
        clipped = clipped.rstrip() + "..."

    raw_parts = re.split(r"\n\s*\n", clipped)
    parts = [re.sub(r"\s+", " ", part).strip() for part in raw_parts if part.strip()]
    selected = parts[:max_paragraphs]
    return "".join(f"<p>{_parse_latex_content(part)}</p>" for part in selected)


def _content_or_placeholder(text: str, label: str) -> str:
    cleaned = text.strip()
    if cleaned and cleaned != "...":
        return cleaned
    return (
        f"{label} is structured and ready. Add full text in "
        f"`frontend/thesis_structure.json` to render detailed content."
    )


def _landing_markup(thesis_title: str, outline: dict, pdf_bytes: bytes) -> str:
    encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")

    # Build chapter sections with parallax scroll animations
    chapter_sections = []
    chapters = outline.get("chapters", [])

    for index, chapter in enumerate(chapters):
        chapter_text = _content_or_placeholder(chapter.get("content", ""), chapter["title"])
        paragraphs = _paragraphs_html(chapter_text, max_chars=1800, max_paragraphs=4)

        # Alternate layout direction
        layout_class = "parallax-section--right" if index % 2 == 1 else ""

        # Build section list for this chapter
        section_items = []
        for section in chapter.get("sections", []):
            section_items.append(
                f'<a class="chapter-section-link" href="{READER_ROUTE}?item={quote_plus(section["id"])}">'
                f'{html.escape(section["title"])}</a>'
            )

        sections_html = ""
        if section_items:
            sections_html = f'<div class="chapter-sections-list">{"".join(section_items)}</div>'

        chapter_num = f"{index + 1:02d}"

        chapter_sections.append(f'''
<section class="parallax-section {layout_class}" id="chapter-{chapter["id"]}">
  <div class="parallax-content">
    <span class="chapter-number">{chapter_num}</span>
    <h2 class="chapter-title">{html.escape(chapter["title"])}</h2>
    <div class="chapter-text">{paragraphs}</div>
    {sections_html}
    <a class="chapter-cta" href="{READER_ROUTE}?item={quote_plus(chapter["id"])}">
      Read Full Chapter
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5 12h14M12 5l7 7-7 7"/>
      </svg>
    </a>
  </div>
</section>
''')

    return f'''
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{
  display: none !important;
}}

[data-testid="stMainBlockContainer"] {{
  max-width: 100% !important;
  padding: 0 !important;
}}

/* Hero Section */
.hero-stage {{
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: transparent;
}}

.hero-shell {{
  position: relative;
  z-index: 1;
  width: min(100%, 900px);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 1.5rem;
}}

.hero-shell > * {{
  opacity: 0;
  transform: translateY(20px);
  animation: hero-rise 800ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}}

.hero-shell > *:nth-child(1) {{ animation-delay: 100ms; }}
.hero-shell > *:nth-child(2) {{ animation-delay: 200ms; }}
.hero-shell > *:nth-child(3) {{ animation-delay: 300ms; }}
.hero-shell > *:nth-child(4) {{ animation-delay: 400ms; }}
.hero-shell > *:nth-child(5) {{ animation-delay: 500ms; }}

.hero-title {{
  margin: 0;
  font-size: clamp(2.5rem, 6vw, 5rem);
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: var(--text-ink);
}}

.hero-subtitle {{
  margin: 0;
  max-width: 52ch;
  color: var(--text-subtle);
  font-size: clamp(1.05rem, 2vw, 1.25rem);
  line-height: 1.6;
}}

.hero-actions {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}}

.hero-cta {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 0.9rem 1.5rem;
  border-radius: 12px;
  border: 1px solid transparent;
  font-weight: 600;
  font-size: 1rem;
  transition: all 200ms ease;
}}

.hero-cta-primary {{
  background: var(--primary);
  color: #fff;
  box-shadow: 0 8px 24px rgba(27, 122, 95, 0.25);
}}

.hero-cta-primary:hover {{
  background: var(--primary-strong);
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(27, 122, 95, 0.3);
}}

.hero-cta-secondary {{
  background: rgba(27, 122, 95, 0.08);
  color: var(--primary-strong);
  border-color: rgba(27, 122, 95, 0.2);
}}

.hero-cta-secondary:hover {{
  background: rgba(27, 122, 95, 0.12);
  border-color: rgba(27, 122, 95, 0.3);
}}

.hero-cta-tertiary {{
  background: transparent;
  color: var(--text-subtle);
  border-color: var(--line);
}}

.hero-cta-tertiary:hover {{
  background: rgba(27, 122, 95, 0.05);
  color: var(--primary);
  border-color: var(--primary);
}}

/* Scroll Indicator */
.scroll-indicator {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-top: 2rem;
  color: var(--text-subtle);
}}

.scroll-indicator-text {{
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  opacity: 0.7;
}}

.scroll-indicator-arrow {{
  position: relative;
  width: 26px;
  height: 42px;
  border: 2px solid currentColor;
  border-radius: 13px;
  opacity: 0.5;
}}

.scroll-indicator-arrow::before {{
  content: "";
  position: absolute;
  top: 6px;
  left: 50%;
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 50%;
  transform: translateX(-50%);
  animation: scroll-dot 2s ease-in-out infinite;
}}

.scroll-indicator:hover {{
  color: var(--primary);
}}

.scroll-indicator:hover .scroll-indicator-arrow {{
  opacity: 1;
}}

/* Parallax Sections */
.parallax-section {{
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: clamp(3rem, 8vw, 6rem) clamp(1.5rem, 5vw, 4rem);
  position: relative;
}}

.parallax-section:nth-child(odd) {{
  background: transparent;
}}

.parallax-section:nth-child(even) {{
  background: linear-gradient(180deg, rgba(27, 122, 95, 0.02) 0%, rgba(27, 122, 95, 0.04) 100%);
}}

.parallax-content {{
  max-width: 720px;
  margin: 0 auto;
  opacity: 0;
  transform: translateY(60px);
  animation: parallax-reveal linear forwards;
  animation-timeline: view();
  animation-range: entry 0% cover 40%;
}}

.parallax-section--right .parallax-content {{
  margin-left: auto;
  margin-right: 10%;
  text-align: right;
}}

.parallax-section--right .chapter-sections-list {{
  justify-content: flex-end;
}}

.chapter-number {{
  display: inline-block;
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(4rem, 12vw, 8rem);
  font-weight: 700;
  line-height: 1;
  color: rgba(27, 122, 95, 0.08);
  letter-spacing: -0.04em;
  margin-bottom: -0.5rem;
}}

.chapter-title {{
  margin: 0 0 1.5rem 0;
  font-size: clamp(2rem, 5vw, 3.5rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--text-ink);
}}

.chapter-text {{
  font-size: clamp(1rem, 1.5vw, 1.15rem);
  line-height: 1.75;
  color: var(--text-ink);
  opacity: 0.85;
}}

.chapter-text p {{
  margin: 0 0 1rem 0;
}}

.chapter-text p:last-child {{
  margin-bottom: 0;
}}

.chapter-sections-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.5rem;
}}

.chapter-section-link {{
  display: inline-flex;
  padding: 0.4rem 0.85rem;
  background: rgba(27, 122, 95, 0.06);
  border: 1px solid rgba(27, 122, 95, 0.12);
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--primary);
  transition: all 180ms ease;
}}

.chapter-section-link:hover {{
  background: rgba(27, 122, 95, 0.12);
  border-color: rgba(27, 122, 95, 0.25);
  color: var(--primary-strong);
}}

.chapter-cta {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 2rem;
  padding: 0.75rem 1.25rem;
  background: var(--primary);
  color: #fff;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.95rem;
  transition: all 200ms ease;
}}

.chapter-cta:hover {{
  background: var(--primary-strong);
  transform: translateX(4px);
}}

.chapter-cta svg {{
  transition: transform 200ms ease;
}}

.chapter-cta:hover svg {{
  transform: translateX(3px);
}}

/* Footer CTA */
.footer-cta {{
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 4rem 2rem;
  background: linear-gradient(180deg, transparent 0%, rgba(27, 122, 95, 0.04) 100%);
}}

.footer-cta h2 {{
  margin: 0 0 1rem 0;
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  color: var(--text-ink);
}}

.footer-cta p {{
  margin: 0 0 2rem 0;
  color: var(--text-subtle);
  font-size: 1.1rem;
}}

.footer-actions {{
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: center;
}}

/* Animations */
@keyframes hero-rise {{
  to {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

@keyframes scroll-dot {{
  0%, 100% {{ top: 6px; opacity: 1; }}
  50% {{ top: 24px; opacity: 0.3; }}
}}

@keyframes parallax-reveal {{
  to {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

/* Fallback for browsers without scroll-driven animations */
@supports not (animation-timeline: view()) {{
  .parallax-content {{
    opacity: 1;
    transform: none;
  }}
}}

@media (prefers-reduced-motion: reduce) {{
  .hero-shell > *,
  .parallax-content {{
    animation: none;
    opacity: 1;
    transform: none;
  }}
  .scroll-indicator-arrow::before {{
    animation: none;
  }}
}}

@media (max-width: 768px) {{
  .hero-stage {{
    min-height: 100svh;
    padding: 1.5rem;
  }}

  .hero-actions {{
    width: 100%;
  }}

  .hero-cta {{
    width: 100%;
  }}

  .parallax-section {{
    min-height: auto;
    padding: 4rem 1.5rem;
  }}

  .parallax-section--right .parallax-content {{
    margin: 0 auto;
    text-align: left;
  }}

  .parallax-section--right .chapter-sections-list {{
    justify-content: flex-start;
  }}

  .chapter-number {{
    font-size: 4rem;
  }}
}}

/* LaTeX Content Styling for Landing Page */

/* Citations */
.cite-group {{
  font-size: 0.9em;
}}

.citation {{
  color: var(--primary) !important;
  background: rgba(27, 122, 95, 0.08);
  padding: 0.1em 0.35em;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.85em;
  transition: all 180ms ease;
  cursor: pointer;
}}

.citation:hover {{
  background: rgba(27, 122, 95, 0.15);
  color: var(--primary-strong) !important;
}}

/* Math styling */
.math-inline {{
  font-family: "Cambria Math", "STIX Two Math", Georgia, serif;
  font-style: italic;
  background: rgba(27, 122, 95, 0.04);
  padding: 0.1em 0.3em;
  border-radius: 3px;
}}

.math-display {{
  display: block;
  font-family: "Cambria Math", "STIX Two Math", Georgia, serif;
  font-style: italic;
  text-align: center;
  padding: 1rem;
  margin: 1rem 0;
  background: rgba(27, 122, 95, 0.03);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
}}

/* Code/monospace */
.latex-code {{
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 0.88em;
  background: rgba(27, 122, 95, 0.06);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  color: var(--primary-strong);
}}

/* URLs and references */
.url-link, .ref-link {{
  color: var(--primary) !important;
}}

.url-link:hover, .ref-link:hover {{
  text-decoration: underline !important;
}}

/* Footnotes */
.footnote {{
  cursor: help;
  color: var(--primary);
}}

.footnote sup {{
  font-size: 0.75em;
}}
</style>

<section class="hero-stage">
  <div class="hero-shell">
    <h1 class="hero-title">{html.escape(thesis_title)}</h1>
    <p class="hero-subtitle">A deep dive into peptide-based data encoding systems, error correction mechanisms, and practical evaluation frameworks.</p>
    <div class="hero-actions">
      <a class="hero-cta hero-cta-primary"
         href="data:application/pdf;base64,{encoded_pdf}"
         download="Missaoui_Yahya_thesis_final.pdf">
        Download Thesis
      </a>
      <a class="hero-cta hero-cta-secondary" href="{READER_ROUTE}">
        Full Reader
      </a>
    </div>
    <div class="hero-actions">
      <a class="hero-cta hero-cta-tertiary" href="{ENCODE_ROUTE}">
        Try Encoder
      </a>
    </div>
    <a class="scroll-indicator" href="#chapter-{chapters[0]["id"] if chapters else "intro"}">
      <span class="scroll-indicator-text">Scroll</span>
      <span class="scroll-indicator-arrow"></span>
    </a>
  </div>
</section>

{''.join(chapter_sections)}

<section class="footer-cta">
  <h2>Ready to explore more?</h2>
  <p>Download the full thesis or try the interactive encoder.</p>
  <div class="footer-actions">
    <a class="hero-cta hero-cta-primary"
       href="data:application/pdf;base64,{encoded_pdf}"
       download="Missaoui_Yahya_thesis_final.pdf">
      Download PDF
    </a>
    <a class="hero-cta hero-cta-secondary" href="{ENCODE_ROUTE}">
      Open Encoder
    </a>
  </div>
</section>
'''


def _render_landing() -> None:
    st.markdown(
        """
<style>
html {
  scroll-behavior: smooth;
}
</style>
""",
        unsafe_allow_html=True,
    )

    if not THESIS_PDF.exists():
        st.error(
            "Missing thesis PDF at `frontend/Missaoui_Yahya_thesis_final.pdf`. "
            "Add the file to enable download and section rendering."
        )
        return

    mapping_mtime = SECTIONS_MAPPING.stat().st_mtime if SECTIONS_MAPPING.exists() else 0.0
    thesis_data = _load_thesis_data(
        pdf_path=str(THESIS_PDF),
        mapping_path=str(SECTIONS_MAPPING),
        pdf_mtime=THESIS_PDF.stat().st_mtime,
        mapping_mtime=mapping_mtime,
    )
    outline = load_outline(
        structure_path=THESIS_STRUCTURE,
        fallback_thesis_data=thesis_data,
        strict_json=True,
    )
    pdf_bytes = _load_pdf_bytes(str(THESIS_PDF))

    st.markdown(
        _landing_markup(
            thesis_title=outline.get("title", thesis_data.get("title", "Thesis")),
            outline=outline,
            pdf_bytes=pdf_bytes,
        ),
        unsafe_allow_html=True,
    )
    if not outline.get("chapters"):
        st.warning(
            "No chapters found in `frontend/thesis_structure.json`. "
            "Only JSON content is used now; PDF text fallback is disabled."
        )


def _reader_body_html(text: str, is_bibliography: bool = False) -> str:
    cleaned = text.strip()
    if not cleaned or cleaned == "...":
        return (
            "<p>Structured heading is available. Add full content in "
            "<code>frontend/thesis_structure.json</code> for this item.</p>"
        )

    # Check if this is BibTeX content
    if is_bibliography or _is_bibtex_content(cleaned):
        return _render_bibliography_html(cleaned)

    raw_parts = re.split(r"\n\s*\n", cleaned)
    parts = [re.sub(r"\s+", " ", part).strip() for part in raw_parts if part.strip()]
    return "".join(f"<p>{_parse_latex_content(part)}</p>" for part in parts)


def _reader_collapsible_outline_html(outline: dict, selected_path: str) -> str:
    chapter_blocks: list[str] = []

    for chapter in outline.get("chapters", []):
        chapter_title = chapter["title"]
        chapter_id = chapter.get("id", "")
        chapter_open = " open" if selected_path.startswith(chapter_title) else ""
        chapter_text = _content_or_placeholder(chapter.get("content", ""), chapter_title)

        # Check if this is the bibliography chapter
        is_bib_chapter = chapter_id == "bibliography" or chapter_title.lower() == "bibliography"

        section_blocks: list[str] = []
        for section in chapter.get("sections", []):
            section_title = section["title"]
            section_open = " open" if selected_path.startswith(f"{chapter_title} / {section_title}") else ""
            section_text = _content_or_placeholder(section.get("content", ""), section_title)

            subsection_blocks: list[str] = []
            for subsection in section.get("subsections", []):
                subsection_title = subsection["title"]
                subsection_text = _content_or_placeholder(subsection.get("content", ""), subsection_title)
                subsection_open = (
                    " open"
                    if selected_path
                    == f"{chapter_title} / {section_title} / {subsection_title}"
                    else ""
                )
                subsection_blocks.append(
                    f"""
<details class="outline-subsection"{subsection_open}>
  <summary>{html.escape(subsection_title)}</summary>
  <div class="outline-body">
    {_reader_body_html(subsection_text)}
  </div>
</details>
"""
                )

            section_blocks.append(
                f"""
<details class="outline-section"{section_open}>
  <summary>{html.escape(section_title)}</summary>
  <div class="outline-body">
    {_reader_body_html(section_text)}
    {''.join(subsection_blocks)}
  </div>
</details>
"""
            )

        chapter_blocks.append(
            f"""
<details class="outline-chapter"{chapter_open}>
  <summary>{html.escape(chapter_title)}</summary>
  <div class="outline-body">
    {_reader_body_html(chapter_text, is_bibliography=is_bib_chapter)}
    {''.join(section_blocks)}
  </div>
</details>
"""
        )

    return "".join(chapter_blocks)


def _render_reader() -> None:
    if not THESIS_PDF.exists():
        st.error("Missing thesis PDF at `frontend/Missaoui_Yahya_thesis_final.pdf`.")
        return

    mapping_mtime = SECTIONS_MAPPING.stat().st_mtime if SECTIONS_MAPPING.exists() else 0.0
    thesis_data = _load_thesis_data(
        pdf_path=str(THESIS_PDF),
        mapping_path=str(SECTIONS_MAPPING),
        pdf_mtime=THESIS_PDF.stat().st_mtime,
        mapping_mtime=mapping_mtime,
    )
    pdf_bytes = _load_pdf_bytes(str(THESIS_PDF))

    st.markdown(
        """
<style>
/* Sidebar styling */
[data-testid="stSidebar"] {
  background: transparent;
  border-right: 1px solid rgba(27, 122, 95, 0.1);
}

[data-testid="stSidebar"] > div:first-child {
  padding-top: 1.5rem;
}

[data-testid="stSidebar"] .stDownloadButton > button {
  background: var(--primary);
  color: #ffffff;
  border-color: var(--primary) !important;
  border-radius: 10px;
  font-weight: 600;
}

[data-testid="stSidebar"] .stDownloadButton > button:hover {
  background: var(--primary-strong);
  transform: translateY(-1px);
}

[data-testid="stSidebar"] .stButton > button {
  border-radius: 8px;
  font-weight: 500;
  transition: all 180ms ease;
}

[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(27, 122, 95, 0.08);
  border-color: var(--primary);
}

[data-testid="stSidebar"] .stProgress > div > div {
  background: var(--primary);
}

/* Main container */
[data-testid="stMainBlockContainer"] {
  max-width: 900px;
  padding-top: 1rem !important;
}

/* Page header */
.reader-header {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(27, 122, 95, 0.1);
}

.reader-header h1 {
  margin: 0 0 0.5rem 0;
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  line-height: 1.15;
}

.reader-header p {
  margin: 0;
  color: var(--text-subtle);
  font-size: 1rem;
}

/* Navigation pills */
.nav-pills {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
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

/* Section title with accent bar */
.section-label {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 2rem 0 1rem 0;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.section-label::before {
  content: "";
  width: 4px;
  height: 1em;
  background: var(--primary);
  border-radius: 2px;
}

/* Outline styling */
.outline-chapter,
.outline-section,
.outline-subsection {
  border: 1px solid rgba(27, 122, 95, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.75rem;
  transition: all 200ms ease;
}

.outline-chapter:hover,
.outline-section:hover,
.outline-subsection:hover {
  border-color: rgba(27, 122, 95, 0.25);
  background: rgba(255, 255, 255, 0.7);
}

.outline-chapter[open],
.outline-section[open],
.outline-subsection[open] {
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(27, 122, 95, 0.2);
}

.outline-section,
.outline-subsection {
  margin-top: 0.5rem;
}

.outline-chapter > summary,
.outline-section > summary,
.outline-subsection > summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text-ink);
  padding: 0.85rem 1rem;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.outline-chapter > summary::-webkit-details-marker,
.outline-section > summary::-webkit-details-marker,
.outline-subsection > summary::-webkit-details-marker {
  display: none;
}

.outline-chapter > summary::before,
.outline-section > summary::before,
.outline-subsection > summary::before {
  content: "";
  width: 0;
  height: 0;
  border-left: 5px solid var(--primary);
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  transition: transform 200ms ease;
}

.outline-chapter[open] > summary::before,
.outline-section[open] > summary::before,
.outline-subsection[open] > summary::before {
  transform: rotate(90deg);
}

.outline-body {
  padding: 0 1rem 1rem 1.5rem;
  color: var(--text-ink);
  line-height: 1.7;
  font-size: 0.98rem;
}

.outline-body p {
  margin: 0 0 0.75rem 0;
  opacity: 0.9;
}

/* PDF toggle section */
.pdf-section {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid rgba(27, 122, 95, 0.1);
}

/* Remove underlines */
a, a:visited, a:hover, a:active {
  text-decoration: none !important;
}

/* Dividers */
hr {
  border: none;
  border-top: 1px solid rgba(27, 122, 95, 0.1);
  margin: 2rem 0;
}

/* LaTeX Content Styling */

/* Citations */
.cite-group {
  font-size: 0.9em;
}

.citation {
  color: var(--primary) !important;
  background: rgba(27, 122, 95, 0.08);
  padding: 0.1em 0.35em;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.85em;
  transition: all 180ms ease;
  cursor: pointer;
}

.citation:hover {
  background: rgba(27, 122, 95, 0.15);
  color: var(--primary-strong) !important;
}

/* Math styling */
.math-inline {
  font-family: "Cambria Math", "STIX Two Math", "Latin Modern Math", Georgia, serif;
  font-style: italic;
  background: rgba(27, 122, 95, 0.04);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  white-space: nowrap;
}

.math-display {
  display: block;
  font-family: "Cambria Math", "STIX Two Math", "Latin Modern Math", Georgia, serif;
  font-style: italic;
  text-align: center;
  padding: 1.25rem 1rem;
  margin: 1rem 0;
  background: rgba(27, 122, 95, 0.03);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  overflow-x: auto;
}

/* Code/monospace */
.latex-code {
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", Consolas, monospace;
  font-size: 0.88em;
  background: rgba(27, 122, 95, 0.06);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  color: var(--primary-strong);
}

/* References */
.ref-link {
  color: var(--primary) !important;
  font-weight: 500;
}

.ref-link:hover {
  color: var(--primary-strong) !important;
  text-decoration: underline !important;
}

.ref-anchor {
  scroll-margin-top: 100px;
}

/* URLs */
.url-link {
  color: var(--primary) !important;
  word-break: break-all;
}

.url-link:hover {
  text-decoration: underline !important;
}

/* Footnotes */
.footnote {
  cursor: help;
  color: var(--primary);
}

.footnote sup {
  font-size: 0.75em;
  color: var(--primary);
}

/* Bibliography section styling */
.bib-entry {
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(27, 122, 95, 0.1);
  border-radius: 8px;
  scroll-margin-top: 100px;
  transition: all 200ms ease;
}

.bib-entry:target {
  background: rgba(27, 122, 95, 0.08);
  border-color: var(--primary);
}

.bib-entry:hover {
  border-color: rgba(27, 122, 95, 0.25);
}

.bib-key {
  display: inline-block;
  font-weight: 700;
  color: var(--primary);
  background: rgba(27, 122, 95, 0.1);
  padding: 0.15em 0.5em;
  border-radius: 4px;
  font-size: 0.85em;
  margin-right: 0.5rem;
}

.bib-authors {
  font-weight: 600;
  color: var(--text-ink);
}

.bib-title {
  font-style: italic;
  color: var(--text-ink);
  opacity: 0.9;
}

.bib-venue {
  color: var(--text-subtle);
  font-size: 0.92em;
}

.bib-year {
  display: inline-block;
  background: rgba(27, 122, 95, 0.08);
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-size: 0.85em;
  font-weight: 600;
  color: var(--text-subtle);
}

/* Bibliography container */
.bibliography {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.bib-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.bib-details {
  font-size: 0.9em;
  color: var(--text-subtle);
  margin-top: 0.25rem;
}

.bib-actions {
  margin-top: 0.5rem;
}

.bib-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3rem 0.7rem;
  background: var(--primary);
  color: #fff !important;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  transition: all 180ms ease;
}

.bib-link:hover {
  background: var(--primary-strong);
  transform: translateY(-1px);
}

/* Figure styling */
.latex-figure {
  margin: 1.5rem 0;
  text-align: center;
}

.latex-figure-img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.latex-figure figcaption {
  margin-top: 0.75rem;
  font-size: 0.9em;
  color: var(--text-subtle);
  font-style: italic;
}

.figure-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(27, 122, 95, 0.05);
  border: 2px dashed rgba(27, 122, 95, 0.2);
  border-radius: 8px;
  color: var(--text-subtle);
  font-style: italic;
}

/* Smooth scroll for citation links */
html {
  scroll-behavior: smooth;
}
</style>
""",
        unsafe_allow_html=True,
    )

    outline = load_outline(
        structure_path=THESIS_STRUCTURE,
        fallback_thesis_data=thesis_data,
        strict_json=True,
    )
    entries = flatten_outline_entries(outline)
    if not entries:
        st.warning("No outline entries are available.")
        return

    entry_by_id = {entry["id"]: entry for entry in entries}
    all_ids = [entry["id"] for entry in entries]

    query_item = st.query_params.get("item")
    if query_item in entry_by_id:
        st.session_state["reader_selected_item"] = query_item
    query_section = st.query_params.get("section")
    if query_section in entry_by_id:
        st.session_state["reader_selected_item"] = query_section

    with st.sidebar:
        st.markdown("## Reader")
        st.caption("Navigate and explore the thesis content.")

        if st.button(
            "Home",
            type="secondary",
            use_container_width=True,
        ):
            st.switch_page(landing_page)

        if st.button(
            "Encoder",
            type="secondary",
            use_container_width=True,
        ):
            st.switch_page(encode_page)

        st.markdown("---")

        search_query = st.text_input(
            "Search",
            value="",
            placeholder="Search chapters...",
            label_visibility="collapsed",
        )

        normalized_query = search_query.strip().lower()
        selected_entry = st.session_state.get("reader_selected_item")
        if not isinstance(selected_entry, str) or selected_entry not in entry_by_id:
            selected_entry = entries[0]["id"]

        if normalized_query:
            matches = [
                entry
                for entry in entries
                if normalized_query in entry["path"].lower()
                or normalized_query in entry.get("content", "").lower()
            ]
            if matches:
                selected_entry = matches[0]["id"]
                st.caption(f"{len(matches)} match(es)")
            else:
                st.caption("No matches")

        selected_entry = entry_by_id[selected_entry]
        st.session_state["reader_selected_item"] = selected_entry["id"]
        st.query_params["item"] = selected_entry["id"]

        st.markdown("---")

        st.caption("**Chapters**")
        for chapter in outline.get("chapters", []):
            is_selected = selected_entry["path"].startswith(chapter["title"])
            btn_type = "primary" if is_selected else "secondary"
            if st.button(
                chapter["title"],
                key=f"chapter_nav_{chapter['id']}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state["reader_selected_item"] = chapter["id"]
                st.query_params["item"] = chapter["id"]
                st.rerun()

        st.markdown("---")

        overall_index = all_ids.index(selected_entry["id"]) + 1
        st.progress(overall_index / len(all_ids))
        st.caption(f"{overall_index} / {len(all_ids)}")

        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=THESIS_PDF.name,
            mime="application/pdf",
            use_container_width=True,
        )

    # Page header
    st.markdown(
        f"""
<div class="reader-header">
  <h1>{html.escape(outline.get('title', thesis_data.get('title', 'Thesis')))}</h1>
  <p>Expand chapters to explore the full thesis content.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    # Navigation pills
    st.markdown(
        """
<div class="nav-pills">
  <a class="nav-pill" href="/" target="_self">Home</a>
  <a class="nav-pill" href="/encode" target="_self">Encoder</a>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-label">Thesis Outline</p>', unsafe_allow_html=True)

    st.markdown(
        _reader_collapsible_outline_html(outline=outline, selected_path=selected_entry["path"]),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pdf-section">', unsafe_allow_html=True)
    show_preview = st.toggle(
        "Show PDF preview",
        value=False,
        help="Load inline PDF viewer",
    )
    if show_preview:
        _render_pdf_preview(pdf_bytes=pdf_bytes, height=920)
    else:
        st.caption("Toggle to load the embedded PDF viewer.")
    st.markdown('</div>', unsafe_allow_html=True)


_render_global_styles()

landing_page = st.Page(
    page=_render_landing,
    title="Landing",
    icon=":material/home:",
    default=True,
)
reader_page = st.Page(
    page=_render_reader,
    title="Reader",
    icon=":material/menu_book:",
    url_path="app",
)
encode_page = st.Page(
    page="pages/01_Encode_Decode.py",
    title="Encode / Decode",
    icon=":material/biotech:",
    url_path="encode",
)

current_page = st.navigation(
    pages=[landing_page, reader_page, encode_page],
    position="hidden",
)
current_page.run()
