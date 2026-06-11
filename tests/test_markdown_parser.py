from app.services.markdown_parser import PARSER_VERSION, parse_markdown_bytes, parse_markdown_text


def test_parse_markdown_keeps_frontmatter_heading_path_and_metadata() -> None:
    parsed = parse_markdown_text(
        """---
tags:
  - web
  - linux
---
# Linux
## Privilege escalation
### SUID

Hasznald az `find / -perm -4000` parancsot.
Lasd meg: [[Linux PrivEsc|SUID technikak]] #privsec
"""
    )

    assert parsed.quality_flags == []
    assert parsed.frontmatter == {"tags": ["web", "linux"]}
    assert parsed.headings[-1]["heading_path"] == "Linux > Privilege escalation > SUID"
    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert chunk.heading_path == "Linux > Privilege escalation > SUID"
    assert chunk.frontmatter_tags == ["web", "linux"]
    assert chunk.wikilinks == ["Linux PrivEsc"]
    assert chunk.tags == ["privsec"]
    assert "`find / -perm -4000`" in chunk.text
    assert PARSER_VERSION == "markdown_marko_ast_parser_v1"


def test_parse_markdown_keeps_heading_section_with_code_context_together() -> None:
    parsed = parse_markdown_text(
        """# Commands
## Basic checks

Intro paragraph.

```bash
whoami
id
uname -a
```

Closing paragraph.
"""
    )

    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert chunk.heading_path == "Commands > Basic checks"
    assert chunk.contains_code_block is True
    assert chunk.code_languages == ["bash"]
    assert "Intro paragraph." in chunk.text
    assert "whoami\nid\nuname -a" in chunk.text
    assert "Closing paragraph." in chunk.text
    assert any(flag == "ast_node:fenced_code" for flag in chunk.quality_flags)


def test_parse_markdown_keeps_nested_list_in_one_section_chunk() -> None:
    parsed = parse_markdown_text(
        """# Web
## Checklist

- recon
  - subdomain enumeration
  - technology fingerprinting
- validation
  - verify source
"""
    )

    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert chunk.heading_path == "Web > Checklist"
    assert "- recon" in chunk.text
    assert "subdomain enumeration" in chunk.text
    assert any(flag == "ast_node:list" for flag in chunk.quality_flags)
    assert any(flag == "ast_node:list_item" for flag in chunk.quality_flags)


def test_parse_markdown_reports_invalid_encoding() -> None:
    parsed = parse_markdown_bytes(b"\xff\xfe\x00")

    assert parsed.quality_flags == ["invalid_encoding"]
    assert parsed.chunks == []
    assert parsed.has_fatal_error is True


def test_parse_markdown_reports_empty_document() -> None:
    parsed = parse_markdown_text("  \n\n")

    assert parsed.quality_flags == ["empty_markdown"]
    assert parsed.chunks == []
    assert parsed.has_fatal_error is True
