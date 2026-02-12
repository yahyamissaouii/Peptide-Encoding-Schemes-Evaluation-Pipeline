"""Utilities for extracting thesis title and section content from PDF."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_SECTION_TITLES = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Methodology",
    "Results",
    "Discussion",
    "Conclusion and Outlook",
    "Bibliography",
]


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or "section"


def _normalize(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def _run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def _extract_pdf_pages(pdf_path: Path) -> list[str]:
    output = _run_command(["pdftotext", "-layout", str(pdf_path), "-"])
    if not output:
        return []

    pages = [page.strip("\n") for page in output.split("\f")]
    while pages and not pages[-1].strip():
        pages.pop()
    return pages


def _extract_title_from_metadata(pdf_path: Path) -> str:
    info_text = _run_command(["pdfinfo", str(pdf_path)])
    if not info_text:
        return ""

    for line in info_text.splitlines():
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            if title:
                return title
    return ""


def _extract_title_from_first_page(first_page: str) -> str:
    blocked_patterns = re.compile(
        r"(bachelor thesis|student id|submitted|examiner|department|goethe university|"
        r"february|^\s*by\s*$|s\d+@)",
        re.IGNORECASE,
    )
    lines = []
    for raw_line in first_page.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line.lower() == "by" and lines:
            break
        if blocked_patterns.search(line):
            continue
        if len(line) < 5:
            continue
        lines.append(line)
        if len(lines) == 3:
            break

    return " ".join(lines).strip()


def _extract_toc_titles(pages: list[str]) -> list[str]:
    joined = "\n".join(pages[: min(len(pages), 16)])
    if "Contents" not in joined:
        return []

    titles: list[str] = []
    seen: set[str] = set()

    chapter_pattern = re.compile(
        r"^\s*\d+\s+([A-Za-z][A-Za-z0-9 ,:&\-/\u2013\u2014]+?)\s+\d+\s*$"
    )
    bibliography_pattern = re.compile(r"^\s*(Bibliography)\s+\d+\s*$", re.IGNORECASE)

    for raw_line in joined.splitlines():
        line = raw_line.rstrip()
        chapter_match = chapter_pattern.match(line)
        bibliography_match = bibliography_pattern.match(line)

        if chapter_match:
            title = chapter_match.group(1).strip()
        elif bibliography_match:
            title = bibliography_match.group(1).strip()
        else:
            continue

        normalized = _normalize(title)
        if normalized and normalized not in seen:
            seen.add(normalized)
            titles.append(title)

    return titles


def _parse_int(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _load_section_mapping(mapping_path: Path) -> list[dict[str, Any]]:
    if not mapping_path.exists():
        return []

    try:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(payload, dict):
        entries = payload.get("sections", [])
    else:
        entries = payload

    if not isinstance(entries, list):
        return []

    sections: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        title = str(entry.get("title", "")).strip()
        if not title:
            continue

        aliases_raw = entry.get("aliases", [])
        aliases = [str(alias).strip() for alias in aliases_raw if str(alias).strip()]

        sections.append(
            {
                "title": title,
                "aliases": aliases,
                "start_page": _parse_int(entry.get("start_page")),
                "end_page": _parse_int(entry.get("end_page")),
            }
        )

    return sections


def _merge_section_seeds(
    toc_titles: list[str], mapping_sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    mapping_by_title = {_normalize(item["title"]): item for item in mapping_sections}
    seen: set[str] = set()

    ordered_titles = ["Abstract", *toc_titles]
    if len(ordered_titles) == 1:
        ordered_titles = DEFAULT_SECTION_TITLES.copy()

    for title in ordered_titles:
        normalized = _normalize(title)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        mapped = mapping_by_title.get(normalized)
        if mapped:
            merged.append(mapped)
        else:
            merged.append(
                {
                    "title": title,
                    "aliases": [],
                    "start_page": None,
                    "end_page": None,
                }
            )

    for mapped in mapping_sections:
        normalized = _normalize(mapped["title"])
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(mapped)

    return merged


def _find_section_start_page(
    pages: list[str], title: str, aliases: list[str] | None = None
) -> int | None:
    candidates = [title, *(aliases or [])]
    normalized_candidates = [_normalize(candidate) for candidate in candidates if candidate]
    normalized_candidates = [candidate for candidate in normalized_candidates if candidate]
    if not normalized_candidates:
        return None

    for page_number, page_text in enumerate(pages, start=1):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        if not lines:
            continue

        header_preview = " ".join(lines[:4])
        if "contents" in _normalize(header_preview):
            continue

        for line in lines[:80]:
            if len(line) > 120:
                continue
            if re.search(r"\.{3,}", line):
                continue
            if re.search(r"\s+\d+\s*$", line) and len(line.split()) > 2:
                continue

            normalized_line = _normalize(line)
            if not normalized_line or len(normalized_line.split()) > 14:
                continue

            for candidate in normalized_candidates:
                if (
                    normalized_line == candidate
                    or normalized_line.endswith(f" {candidate}")
                    or normalized_line.startswith(f"{candidate} ")
                ):
                    return page_number
    return None


def _clean_section_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        compact = line.strip()
        if not compact:
            cleaned_lines.append("")
            continue

        if re.fullmatch(r"[ivxlcdm]+", compact.lower()):
            continue
        if re.fullmatch(r"\d+", compact):
            continue
        if compact.lower() == "contents":
            continue

        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
    return cleaned_text


def _section_excerpt(text: str, max_chars: int = 520) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def _build_sections(
    pages: list[str], seeds: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    page_count = len(pages)
    discovered: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for seed in seeds:
        title = str(seed.get("title", "")).strip()
        normalized = _normalize(title)
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)

        aliases = seed.get("aliases", [])
        start_page = _parse_int(seed.get("start_page"))
        end_page = _parse_int(seed.get("end_page"))

        if start_page is None:
            start_page = _find_section_start_page(pages, title=title, aliases=aliases)

        if start_page is None or start_page > page_count:
            continue

        discovered.append(
            {
                "title": title,
                "start_page": start_page,
                "end_page": end_page,
                "aliases": aliases,
            }
        )

    discovered.sort(key=lambda item: item["start_page"])
    sections: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for index, section in enumerate(discovered):
        title = section["title"]
        start_page = section["start_page"]
        explicit_end = _parse_int(section.get("end_page"))
        next_start = (
            discovered[index + 1]["start_page"] if index + 1 < len(discovered) else page_count + 1
        )

        if explicit_end is not None:
            end_page = min(explicit_end, next_start - 1)
        else:
            end_page = next_start - 1

        end_page = max(start_page, min(end_page, page_count))
        raw_text = "\n\n".join(pages[start_page - 1 : end_page]).strip()
        text = _clean_section_text(raw_text)

        section_id = _slugify(title)
        if section_id in used_ids:
            section_id = f"{section_id}-{index + 1}"
        used_ids.add(section_id)

        sections.append(
            {
                "id": section_id,
                "title": title,
                "start_page": start_page,
                "end_page": end_page,
                "text": text,
                "excerpt": _section_excerpt(text) if text else "",
            }
        )

    return sections


def load_thesis_content(pdf_path: Path, mapping_path: Path) -> dict[str, Any]:
    pages = _extract_pdf_pages(pdf_path)
    if not pages:
        return {
            "title": "Thesis",
            "page_count": 0,
            "sections": [],
            "text_extracted": False,
        }

    title = _extract_title_from_metadata(pdf_path)
    if not title:
        title = _extract_title_from_first_page(pages[0]) or "Thesis"

    mapping_sections = _load_section_mapping(mapping_path)
    toc_titles = _extract_toc_titles(pages)
    section_seeds = _merge_section_seeds(toc_titles=toc_titles, mapping_sections=mapping_sections)
    sections = _build_sections(pages=pages, seeds=section_seeds)

    if not sections:
        fallback_text = _clean_section_text("\n\n".join(pages))
        sections = [
            {
                "id": "thesis",
                "title": "Thesis",
                "start_page": 1,
                "end_page": len(pages),
                "text": fallback_text,
                "excerpt": _section_excerpt(fallback_text) if fallback_text else "",
            }
        ]

    return {
        "title": title,
        "page_count": len(pages),
        "sections": sections,
        "text_extracted": any(section["text"] for section in sections),
    }
