from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

import marko
from marko import block


PARSER_NAME = "markdown_marko_ast_parser"
PARSER_VERSION = "markdown_marko_ast_parser_v1"
CHUNKING_STRATEGY = "markdown_ast_sections_v1"

HARD_MAX_CHARS = 8000
FATAL_QUALITY_FLAGS = {"invalid_encoding", "empty_markdown", "no_text_content"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)\s*([A-Za-z0-9_+.#-]*)\s*$")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9_\-\u00C0-\u024F]+)")


@dataclass(frozen=True)
class MarkdownChunk:
    chunk_index: int
    text: str
    heading_path: str
    heading_level: int | None
    char_start: int
    char_end: int
    contains_code_block: bool = False
    code_languages: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    frontmatter_tags: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "heading_path": self.heading_path,
            "heading_level": self.heading_level,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "contains_code_block": self.contains_code_block,
            "code_languages": self.code_languages,
            "wikilinks": self.wikilinks,
            "tags": self.tags,
            "frontmatter_tags": self.frontmatter_tags,
            "quality_flags": self.quality_flags,
        }


@dataclass(frozen=True)
class ParsedMarkdownDocument:
    text: str
    frontmatter: dict[str, Any]
    frontmatter_raw: str
    chunks: list[MarkdownChunk]
    headings: list[dict[str, Any]]
    quality_flags: list[str]

    @property
    def has_fatal_error(self) -> bool:
        return any(flag in FATAL_QUALITY_FLAGS for flag in self.quality_flags)


@dataclass(frozen=True)
class _Section:
    text: str
    heading_path: str
    heading_level: int | None
    char_start: int
    char_end: int


@dataclass(frozen=True)
class _ChunkCandidate:
    text: str
    heading_path: str
    heading_level: int | None
    char_start: int
    char_end: int
    node_types: list[str]
    contains_code_block: bool
    code_languages: list[str]
    quality_flags: list[str]


def parse_markdown_bytes(data: bytes) -> ParsedMarkdownDocument:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ParsedMarkdownDocument(
            text="",
            frontmatter={},
            frontmatter_raw="",
            chunks=[],
            headings=[],
            quality_flags=["invalid_encoding"],
        )
    return parse_markdown_text(text)


def parse_markdown_text(text: str) -> ParsedMarkdownDocument:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    quality_flags: list[str] = []
    if not normalized.strip():
        return ParsedMarkdownDocument(
            text=normalized,
            frontmatter={},
            frontmatter_raw="",
            chunks=[],
            headings=[],
            quality_flags=["empty_markdown"],
        )

    frontmatter, frontmatter_raw, content_start = _extract_frontmatter(normalized, quality_flags)
    frontmatter_tags = _frontmatter_tags(frontmatter)
    sections, headings = _source_sections(normalized, content_start, quality_flags)
    candidates = _section_candidates(sections, quality_flags)
    chunks = _chunks_from_candidates(candidates, frontmatter_tags)

    if not chunks and "empty_markdown" not in quality_flags:
        quality_flags.append("no_text_content")

    return ParsedMarkdownDocument(
        text=normalized,
        frontmatter=frontmatter,
        frontmatter_raw=frontmatter_raw,
        chunks=chunks,
        headings=headings,
        quality_flags=_unique(quality_flags),
    )


def _extract_frontmatter(text: str, quality_flags: list[str]) -> tuple[dict[str, Any], str, int]:
    if not text.startswith("---\n"):
        return {}, "", 0
    end_marker = text.find("\n---", 4)
    if end_marker == -1:
        quality_flags.append("frontmatter_parse_failed")
        return {}, "", 0
    marker_end = text.find("\n", end_marker + 1)
    marker_end = len(text) if marker_end == -1 else marker_end + 1
    raw = text[4:end_marker]
    return _parse_simple_frontmatter(raw, quality_flags), raw, marker_end


def _parse_simple_frontmatter(raw: str, quality_flags: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    try:
        for line in raw.splitlines():
            if not line.strip():
                continue
            if line.startswith((" ", "\t")) and current_key and line.strip().startswith("- "):
                existing = result.setdefault(current_key, [])
                if isinstance(existing, list):
                    existing.append(_strip_quotes(line.strip()[2:].strip()))
                continue
            if ":" not in line:
                quality_flags.append("frontmatter_parse_failed")
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if not value:
                result[key] = []
            elif value.startswith("[") and value.endswith("]"):
                result[key] = [_strip_quotes(item.strip()) for item in value[1:-1].split(",") if item.strip()]
            else:
                result[key] = _strip_quotes(value)
    except Exception:
        quality_flags.append("frontmatter_parse_failed")
        return {}
    return result


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _frontmatter_tags(frontmatter: dict[str, Any]) -> list[str]:
    value = frontmatter.get("tags") or frontmatter.get("tag")
    if isinstance(value, list):
        return _unique(str(item).strip().lstrip("#") for item in value if str(item).strip())
    if isinstance(value, str):
        return _unique(item.strip().lstrip("#") for item in re.split(r"[, ]+", value) if item.strip())
    return []


def _source_sections(
    text: str,
    start_offset: int,
    quality_flags: list[str],
) -> tuple[list[_Section], list[dict[str, Any]]]:
    sections: list[_Section] = []
    headings: list[dict[str, Any]] = []
    heading_stack: list[tuple[int, str]] = []
    current_start: int | None = None
    current_heading_path = ""
    current_heading_level: int | None = None

    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(raw_line)
        offset = line_end
        if line_end <= start_offset:
            continue

        line = raw_line.rstrip("\n")
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if current_start is not None and line_start > current_start:
                _append_section(
                    sections,
                    _Section(
                        text=text[current_start:line_start].strip(),
                        heading_path=current_heading_path,
                        heading_level=current_heading_level,
                        char_start=current_start,
                        char_end=line_start,
                    ),
                )
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, title))
            current_heading_path = _heading_path(heading_stack)
            current_heading_level = level
            current_start = line_start
            headings.append(
                {
                    "level": level,
                    "title": title,
                    "heading_path": current_heading_path,
                    "char_start": line_start,
                }
            )
        elif current_start is None and line.strip():
            current_start = line_start
            current_heading_path = _heading_path(heading_stack)
            current_heading_level = heading_stack[-1][0] if heading_stack else None

    if current_start is not None and len(text) > current_start:
        _append_section(
            sections,
            _Section(
                text=text[current_start:].strip(),
                heading_path=current_heading_path,
                heading_level=current_heading_level,
                char_start=current_start,
                char_end=len(text),
            ),
        )
    if not headings and not sections and text[start_offset:].strip():
        quality_flags.append("ast_no_sections")
    return [section for section in sections if section.text.strip()], headings


def _append_section(sections: list[_Section], section: _Section) -> None:
    if not section.text.strip() or _is_heading_only_section(section.text):
        return
    sections.append(section)


def _is_heading_only_section(text: str) -> bool:
    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(non_empty_lines) == 1 and _HEADING_RE.match(non_empty_lines[0]) is not None


def _section_candidates(sections: list[_Section], quality_flags: list[str]) -> list[_ChunkCandidate]:
    candidates: list[_ChunkCandidate] = []
    for section in sections:
        node_types = _marko_node_types(section.text, quality_flags)
        code_languages = _code_languages(section.text)
        contains_code = "fenced_code" in node_types or "code_block" in node_types or bool(code_languages)
        section_flags: list[str] = []
        if len(section.text) <= HARD_MAX_CHARS:
            candidates.append(
                _ChunkCandidate(
                    text=section.text,
                    heading_path=section.heading_path,
                    heading_level=section.heading_level,
                    char_start=section.char_start,
                    char_end=section.char_end,
                    node_types=node_types,
                    contains_code_block=contains_code,
                    code_languages=code_languages,
                    quality_flags=section_flags,
                )
            )
            continue
        section_flags.append("oversized_ast_section")
        quality_flags.append("oversized_ast_section")
        candidates.extend(_split_oversized_section(section, node_types, contains_code, code_languages, section_flags))
    return candidates


def _split_oversized_section(
    section: _Section,
    node_types: list[str],
    contains_code: bool,
    code_languages: list[str],
    quality_flags: list[str],
) -> list[_ChunkCandidate]:
    candidates: list[_ChunkCandidate] = []
    cursor = 0
    text = section.text
    while cursor < len(text):
        end = min(cursor + HARD_MAX_CHARS, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n\n", cursor, end), text.rfind("\n", cursor, end))
            if split_at > cursor + 500:
                end = split_at
        part = text[cursor:end].strip()
        if part:
            candidates.append(
                _ChunkCandidate(
                    text=part,
                    heading_path=section.heading_path,
                    heading_level=section.heading_level,
                    char_start=section.char_start + cursor,
                    char_end=section.char_start + end if end < len(text) else section.char_end,
                    node_types=node_types,
                    contains_code_block=contains_code,
                    code_languages=code_languages,
                    quality_flags=quality_flags,
                )
            )
        cursor = max(end, cursor + 1)
    return candidates


def _chunks_from_candidates(candidates: list[_ChunkCandidate], frontmatter_tags: list[str]) -> list[MarkdownChunk]:
    return [
        MarkdownChunk(
            chunk_index=index,
            text=candidate.text,
            heading_path=candidate.heading_path,
            heading_level=candidate.heading_level,
            char_start=candidate.char_start,
            char_end=candidate.char_end,
            contains_code_block=candidate.contains_code_block,
            code_languages=candidate.code_languages,
            wikilinks=_extract_wikilinks(candidate.text),
            tags=_extract_tags(candidate.text),
            frontmatter_tags=frontmatter_tags,
            quality_flags=_candidate_quality_flags(candidate),
        )
        for index, candidate in enumerate(candidates)
    ]


def _candidate_quality_flags(candidate: _ChunkCandidate) -> list[str]:
    return _unique([*candidate.quality_flags, *[f"ast_node:{node_type}" for node_type in candidate.node_types]])


def _marko_node_types(markdown_text: str, quality_flags: list[str]) -> list[str]:
    try:
        document = marko.parse(markdown_text)
    except Exception:
        quality_flags.append("marko_parse_failed")
        return []
    return _unique(_node_type_name(node) for node in _walk_marko_nodes(document) if not isinstance(node, block.BlankLine))


def _walk_marko_nodes(node: Any):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, list):
        for child in children:
            yield from _walk_marko_nodes(child)


def _node_type_name(node: Any) -> str:
    if isinstance(node, block.Document):
        return "document"
    if isinstance(node, block.Heading):
        return "heading"
    if isinstance(node, block.Paragraph):
        return "paragraph"
    if isinstance(node, block.List):
        return "list"
    if isinstance(node, block.ListItem):
        return "list_item"
    if isinstance(node, block.FencedCode):
        return "fenced_code"
    if isinstance(node, block.CodeBlock):
        return "code_block"
    if isinstance(node, block.Quote):
        return "blockquote"
    if isinstance(node, block.ThematicBreak):
        return "thematic_break"
    if node.__class__.__name__.lower().endswith("table"):
        return "table"
    return node.__class__.__name__.lower()


def _code_languages(text: str) -> list[str]:
    languages: list[str] = []
    for line in text.splitlines():
        match = _FENCE_RE.match(line.strip())
        if match and match.group(2).strip():
            languages.append(match.group(2).strip())
    return _unique(languages)


def _heading_path(stack: list[tuple[int, str]]) -> str:
    return " > ".join(title for _, title in stack)


def _extract_wikilinks(text: str) -> list[str]:
    return _unique(match.group(1).strip() for match in _WIKILINK_RE.finditer(text) if match.group(1).strip())


def _extract_tags(text: str) -> list[str]:
    return _unique(match.group(1).strip() for match in _TAG_RE.finditer(text) if match.group(1).strip())


def _unique(values) -> list:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def has_fatal_quality_flags(flags: list[str]) -> bool:
    return any(flag in FATAL_QUALITY_FLAGS for flag in flags)
