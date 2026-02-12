"""Load and normalize hierarchical thesis outline metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _safe_int(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _is_placeholder(content: str) -> bool:
    return content in {"", "..."}


def _resolve_content(title: str, content: str) -> str:
    del title
    if not _is_placeholder(content):
        return content
    return ""


def _build_fallback_outline(title: str, fallback_sections: list[dict[str, Any]]) -> dict[str, Any]:
    chapters: list[dict[str, Any]] = []
    for index, section in enumerate(fallback_sections, start=1):
        section_id = _safe_text(section.get("id")) or f"chapter_{index}"
        chapters.append(
            {
                "id": section_id,
                "title": _safe_text(section.get("title")) or f"Chapter {index}",
                "start_page": _safe_int(section.get("start_page")),
                "end_page": _safe_int(section.get("end_page")),
                "content": "",
                "landingpg_content": "",
                "sections": [],
            }
        )
    return {"title": title or "Thesis", "chapters": chapters}


def _sanitize_json_like(raw_text: str) -> str:
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
                if nxt in {'"', "\\", "/"}:
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


def _load_outline_json(raw_text: str) -> dict[str, Any] | None:
    try:
        loaded = json.loads(raw_text)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    sanitized = _sanitize_json_like(raw_text)
    try:
        loaded = json.loads(sanitized)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        return None

    return None


def _normalize_subsection(
    subsection: dict[str, Any],
    index: int,
    chapter_content: str,
    section_content: str,
) -> dict[str, Any]:
    subsection_title = _safe_text(subsection.get("title")) or f"Subsection {index}"
    subsection_id = _safe_text(subsection.get("id")) or f"subsection_{index}"
    subsection_content = _resolve_content(
        title=subsection_title,
        content=_safe_text(subsection.get("content")),
    )
    if _is_placeholder(subsection_content):
        subsection_content = section_content or chapter_content

    return {
        "id": subsection_id,
        "title": subsection_title,
        "content": subsection_content,
    }


def _normalize_section(
    section: dict[str, Any],
    index: int,
    chapter_content: str,
    chapter_start_page: int | None,
    chapter_end_page: int | None,
) -> dict[str, Any]:
    section_title = _safe_text(section.get("title")) or f"Section {index}"
    section_id = _safe_text(section.get("id")) or f"section_{index}"
    section_content = _resolve_content(
        title=section_title,
        content=_safe_text(section.get("content")),
    )
    if _is_placeholder(section_content):
        section_content = chapter_content

    raw_subsections = section.get("subsections", [])
    subsections: list[dict[str, Any]] = []
    if isinstance(raw_subsections, list):
        for subsection_index, subsection in enumerate(raw_subsections, start=1):
            if not isinstance(subsection, dict):
                continue
            subsections.append(
                _normalize_subsection(
                    subsection=subsection,
                    index=subsection_index,
                    chapter_content=chapter_content,
                    section_content=section_content,
                )
            )

    return {
        "id": section_id,
        "title": section_title,
        "start_page": chapter_start_page,
        "end_page": chapter_end_page,
        "content": section_content,
        "subsections": subsections,
    }


def _normalize_chapter(
    chapter: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    chapter_title = _safe_text(chapter.get("title")) or f"Chapter {index}"
    chapter_id = _safe_text(chapter.get("id")) or f"chapter_{index}"
    chapter_start_page = _safe_int(chapter.get("start_page"))
    chapter_end_page = _safe_int(chapter.get("end_page"))
    chapter_content = _resolve_content(
        title=chapter_title,
        content=_safe_text(chapter.get("content")),
    )
    chapter_landingpg_content = _resolve_content(
        title=chapter_title,
        content=_safe_text(chapter.get("landingpg_content")),
    )
    if _is_placeholder(chapter_landingpg_content):
        chapter_landingpg_content = chapter_content

    raw_sections = chapter.get("sections", [])
    sections: list[dict[str, Any]] = []
    if isinstance(raw_sections, list):
        for section_index, section in enumerate(raw_sections, start=1):
            if not isinstance(section, dict):
                continue
            sections.append(
                _normalize_section(
                    section=section,
                    index=section_index,
                    chapter_content=chapter_content,
                    chapter_start_page=chapter_start_page,
                    chapter_end_page=chapter_end_page,
                )
            )

    return {
        "id": chapter_id,
        "title": chapter_title,
        "start_page": chapter_start_page,
        "end_page": chapter_end_page,
        "content": chapter_content,
        "landingpg_content": chapter_landingpg_content,
        "sections": sections,
    }


def load_outline(
    structure_path: Path,
    fallback_thesis_data: dict[str, Any],
    strict_json: bool = False,
) -> dict[str, Any]:
    fallback_sections = fallback_thesis_data.get("sections", [])
    fallback_title = _safe_text(fallback_thesis_data.get("title", "")) or "Thesis"

    if strict_json and not structure_path.exists():
        return {"title": fallback_title, "chapters": []}

    if not structure_path.exists():
        return _build_fallback_outline(title=fallback_title, fallback_sections=fallback_sections)

    try:
        raw_text = structure_path.read_text(encoding="utf-8")
    except OSError:
        if strict_json:
            return {"title": fallback_title, "chapters": []}
        return _build_fallback_outline(title=fallback_title, fallback_sections=fallback_sections)

    raw_outline = _load_outline_json(raw_text)
    if raw_outline is None:
        if strict_json:
            return {"title": fallback_title, "chapters": []}
        return _build_fallback_outline(title=fallback_title, fallback_sections=fallback_sections)

    outline_title = _safe_text(raw_outline.get("title")) or fallback_title
    raw_chapters = raw_outline.get("chapters", [])
    if not isinstance(raw_chapters, list) or not raw_chapters:
        if strict_json:
            return {"title": outline_title, "chapters": []}
        return _build_fallback_outline(title=outline_title, fallback_sections=fallback_sections)

    chapters: list[dict[str, Any]] = []
    for chapter_index, chapter in enumerate(raw_chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        chapters.append(
            _normalize_chapter(
                chapter=chapter,
                index=chapter_index,
            )
        )

    if not chapters:
        if strict_json:
            return {"title": outline_title, "chapters": []}
        return _build_fallback_outline(title=outline_title, fallback_sections=fallback_sections)

    return {"title": outline_title, "chapters": chapters}


def flatten_outline_entries(outline: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    chapters = outline.get("chapters", [])
    for chapter in chapters:
        chapter_title = chapter["title"]
        entries.append(
            {
                "id": chapter["id"],
                "title": chapter_title,
                "level": 0,
                "path": chapter_title,
                "content": chapter.get("content", ""),
                "start_page": chapter.get("start_page"),
                "end_page": chapter.get("end_page"),
            }
        )

        for section in chapter.get("sections", []):
            section_title = section["title"]
            entries.append(
                {
                    "id": section["id"],
                    "title": section_title,
                    "level": 1,
                    "path": f"{chapter_title} / {section_title}",
                    "content": section.get("content", ""),
                    "start_page": section.get("start_page"),
                    "end_page": section.get("end_page"),
                }
            )

            for subsection in section.get("subsections", []):
                subsection_title = subsection["title"]
                entries.append(
                    {
                        "id": subsection["id"],
                        "title": subsection_title,
                        "level": 2,
                        "path": f"{chapter_title} / {section_title} / {subsection_title}",
                        "content": subsection.get("content", ""),
                        "start_page": section.get("start_page"),
                        "end_page": section.get("end_page"),
                    }
                )

    return entries


def chapter_tree_markdown(chapter: dict[str, Any], base_route: str) -> str:
    lines = [f"- [{chapter['title']}]({base_route}?item={quote_plus(chapter['id'])})"]

    for section in chapter.get("sections", []):
        lines.append(f"  - [{section['title']}]({base_route}?item={quote_plus(section['id'])})")
        for subsection in section.get("subsections", []):
            lines.append(
                f"    - [{subsection['title']}]({base_route}?item={quote_plus(subsection['id'])})"
            )

    return "\n".join(lines)
