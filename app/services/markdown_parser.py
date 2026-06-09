from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


PARSER_NAME = "markdown_line_parser"
PARSER_VERSION = "markdown_line_parser_v1"
CHUNKING_STRATEGY = "markdown_heading_blocks_v1"

TARGET_CHARS = 4000
HARD_MAX_CHARS = 8000
OVERSIZED_CODE_BLOCK_CHARS = 8000

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


@dataclass
class _Block:
    text: str
    heading_path: str
    heading_level: int | None
    char_start: int
    char_end: int
    block_type: str
    contains_code_block: bool = False
    code_languages: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class _OpenBlock:
    lines: list[str]
    heading_path: str
    heading_level: int | None
    char_start: int
    block_type: str


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
    blocks, headings = _build_blocks(normalized, content_start, quality_flags)
    chunks = _chunks_from_blocks(blocks, frontmatter_tags)

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
    if marker_end == -1:
        marker_end = len(text)
    else:
        marker_end += 1
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
                result[key] = [
                    _strip_quotes(item.strip())
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
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


def _build_blocks(text: str, start_offset: int, quality_flags: list[str]) -> tuple[list[_Block], list[dict[str, Any]]]:
    blocks: list[_Block] = []
    headings: list[dict[str, Any]] = []
    heading_stack: list[tuple[int, str]] = []
    current: _OpenBlock | None = None
    in_code = False
    code_fence = ""
    code_language = ""

    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(raw_line)
        offset = line_end
        if line_end <= start_offset:
            continue

        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if in_code:
            assert current is not None
            current.lines.append(raw_line)
            if stripped.startswith(code_fence):
                block = _close_block(current, line_end)
                block.contains_code_block = True
                block.code_languages = [code_language] if code_language else []
                if len(block.text) > OVERSIZED_CODE_BLOCK_CHARS:
                    block.quality_flags.append("oversized_code_block")
                    quality_flags.append("oversized_code_block")
                blocks.append(block)
                current = None
                in_code = False
                code_fence = ""
                code_language = ""
            continue

        fence_match = _FENCE_RE.match(stripped)
        if fence_match:
            if current is not None:
                blocks.append(_close_block(current, line_start))
            code_fence = fence_match.group(1)
            code_language = fence_match.group(2).strip()
            current = _OpenBlock(
                lines=[raw_line],
                heading_path=_heading_path(heading_stack),
                heading_level=heading_stack[-1][0] if heading_stack else None,
                char_start=line_start,
                block_type="code",
            )
            in_code = True
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if current is not None:
                blocks.append(_close_block(current, line_start))
                current = None
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, title))
            headings.append(
                {
                    "level": level,
                    "title": title,
                    "heading_path": _heading_path(heading_stack),
                    "char_start": line_start,
                }
            )
            continue

        if not stripped:
            if current is not None:
                blocks.append(_close_block(current, line_start))
                current = None
            continue

        block_type = _block_type(line)
        if current is None:
            current = _OpenBlock(
                lines=[raw_line],
                heading_path=_heading_path(heading_stack),
                heading_level=heading_stack[-1][0] if heading_stack else None,
                char_start=line_start,
                block_type=block_type,
            )
        elif current.block_type == block_type:
            current.lines.append(raw_line)
        else:
            blocks.append(_close_block(current, line_start))
            current = _OpenBlock(
                lines=[raw_line],
                heading_path=_heading_path(heading_stack),
                heading_level=heading_stack[-1][0] if heading_stack else None,
                char_start=line_start,
                block_type=block_type,
            )

    if current is not None:
        block = _close_block(current, len(text))
        if in_code:
            block.contains_code_block = True
            block.code_languages = [code_language] if code_language else []
            block.quality_flags.append("unclosed_code_block")
            quality_flags.append("unclosed_code_block")
        blocks.append(block)
    return blocks, headings


def _block_type(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+[.)]\s+", stripped):
        return "list"
    if stripped.startswith("|") and stripped.endswith("|"):
        return "table"
    return "paragraph"


def _close_block(block: _OpenBlock, char_end: int) -> _Block:
    text = "".join(block.lines).strip()
    return _Block(
        text=text,
        heading_path=block.heading_path,
        heading_level=block.heading_level,
        char_start=block.char_start,
        char_end=char_end,
        block_type=block.block_type,
    )


def _chunks_from_blocks(blocks: list[_Block], frontmatter_tags: list[str]) -> list[MarkdownChunk]:
    chunks: list[MarkdownChunk] = []
    current: list[_Block] = []

    def flush() -> None:
        if not current:
            return
        chunks.extend(_split_chunk_blocks(current, len(chunks), frontmatter_tags))
        current.clear()

    for block in blocks:
        if not block.text.strip():
            continue
        if len(block.text) > HARD_MAX_CHARS or block.contains_code_block:
            flush()
            chunks.extend(_split_chunk_blocks([block], len(chunks), frontmatter_tags))
            continue
        current_len = sum(len(item.text) + 2 for item in current)
        if current and (current_len + len(block.text) > TARGET_CHARS or block.heading_path != current[-1].heading_path):
            flush()
        current.append(block)
    flush()
    return [
        MarkdownChunk(
            chunk_index=index,
            text=chunk.text,
            heading_path=chunk.heading_path,
            heading_level=chunk.heading_level,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            contains_code_block=chunk.contains_code_block,
            code_languages=chunk.code_languages,
            wikilinks=chunk.wikilinks,
            tags=chunk.tags,
            frontmatter_tags=chunk.frontmatter_tags,
            quality_flags=chunk.quality_flags,
        )
        for index, chunk in enumerate(chunks)
    ]


def _split_chunk_blocks(blocks: list[_Block], start_index: int, frontmatter_tags: list[str]) -> list[MarkdownChunk]:
    del start_index
    text = "\n\n".join(block.text for block in blocks).strip()
    first = blocks[0]
    last = blocks[-1]
    contains_code = any(block.contains_code_block for block in blocks)
    quality_flags = _unique(flag for block in blocks for flag in block.quality_flags)
    code_languages = _unique(lang for block in blocks for lang in block.code_languages if lang)
    if contains_code or len(text) <= HARD_MAX_CHARS:
        return [
            MarkdownChunk(
                chunk_index=0,
                text=text,
                heading_path=first.heading_path,
                heading_level=first.heading_level,
                char_start=first.char_start,
                char_end=last.char_end,
                contains_code_block=contains_code,
                code_languages=code_languages,
                wikilinks=_extract_wikilinks(text),
                tags=_extract_tags(text),
                frontmatter_tags=frontmatter_tags,
                quality_flags=quality_flags,
            )
        ]
    return _split_large_text_block(first, last, text, frontmatter_tags, quality_flags)


def _split_large_text_block(
    first: _Block,
    last: _Block,
    text: str,
    frontmatter_tags: list[str],
    quality_flags: list[str],
) -> list[MarkdownChunk]:
    chunks: list[MarkdownChunk] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + HARD_MAX_CHARS, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n\n", cursor, end), text.rfind("\n", cursor, end))
            if split_at > cursor + 500:
                end = split_at
        part = text[cursor:end].strip()
        if part:
            chunks.append(
                MarkdownChunk(
                    chunk_index=0,
                    text=part,
                    heading_path=first.heading_path,
                    heading_level=first.heading_level,
                    char_start=first.char_start + cursor,
                    char_end=first.char_start + end if end < len(text) else last.char_end,
                    wikilinks=_extract_wikilinks(part),
                    tags=_extract_tags(part),
                    frontmatter_tags=frontmatter_tags,
                    quality_flags=quality_flags,
                )
            )
        cursor = max(end, cursor + 1)
    return chunks


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
