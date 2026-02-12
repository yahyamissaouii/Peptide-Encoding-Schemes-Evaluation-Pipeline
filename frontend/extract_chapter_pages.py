#!/usr/bin/env python3
"""Extract first page of each chapter from thesis PDF as images for landing page backgrounds."""

from __future__ import annotations

import json
import re
from pathlib import Path

# PyMuPDF
import fitz

FRONTEND_DIR = Path(__file__).resolve().parent
PDF_PATH = FRONTEND_DIR / "Missaoui_Yahya_thesis_final.pdf"
STRUCTURE_PATH = FRONTEND_DIR / "thesis_structure.json"
OUTPUT_DIR = FRONTEND_DIR / "chapter_pages"


def _sanitize_json(raw_text: str) -> str:
    """Sanitize JSON with invalid escape sequences."""
    result: list[str] = []
    in_string = False
    i = 0

    while i < len(raw_text):
        ch = raw_text[i]

        if not in_string:
            result.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        if ch == '"':
            result.append(ch)
            in_string = False
            i += 1
            continue

        if ch == "\r":
            i += 1
            continue

        if ch == "\n":
            result.append("\\n")
            i += 1
            continue

        if ch == "\\":
            if i + 1 < len(raw_text):
                nxt = raw_text[i + 1]
                if nxt in {'"', "\\", "/", "n", "r", "t", "b", "f"}:
                    result.append("\\")
                    result.append(nxt)
                    i += 2
                    continue
                if nxt == "u" and i + 5 < len(raw_text):
                    unicode_seq = raw_text[i + 2 : i + 6]
                    if all(c in "0123456789abcdefABCDEF" for c in unicode_seq):
                        result.append("\\")
                        result.append("u")
                        result.extend(list(unicode_seq))
                        i += 6
                        continue
            result.append("\\\\")
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def extract_chapter_pages() -> None:
    """Extract first page of each chapter as PNG images."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load thesis structure to get chapter start pages
    raw_text = STRUCTURE_PATH.read_text(encoding="utf-8")
    sanitized = _sanitize_json(raw_text)
    structure = json.loads(sanitized)

    chapters = structure.get("chapters", [])

    # Open PDF
    doc = fitz.open(PDF_PATH)

    for chapter in chapters:
        chapter_id = chapter.get("id", "unknown")
        start_page = chapter.get("start_page")

        if start_page is None:
            print(f"Skipping chapter '{chapter_id}': no start_page defined")
            continue

        # PDF pages are 0-indexed, thesis pages are 1-indexed
        page_index = start_page - 1

        if page_index < 0 or page_index >= len(doc):
            print(f"Skipping chapter '{chapter_id}': page {start_page} out of range")
            continue

        page = doc.load_page(page_index)

        # Render at higher resolution for quality (2x scale)
        matrix = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        output_path = OUTPUT_DIR / f"{chapter_id}.png"
        pix.save(str(output_path))
        print(f"Extracted page {start_page} for chapter '{chapter_id}' -> {output_path.name}")

    doc.close()
    print(f"\nDone! Extracted {len(chapters)} chapter pages to {OUTPUT_DIR}")


if __name__ == "__main__":
    extract_chapter_pages()
