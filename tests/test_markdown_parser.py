from app.services.markdown_parser import parse_markdown_bytes, parse_markdown_text


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


def test_parse_markdown_keeps_fenced_code_block_together() -> None:
    parsed = parse_markdown_text(
        """# Commands

Intro paragraph.

```bash
whoami
id
uname -a
```

Closing paragraph.
"""
    )

    code_chunks = [chunk for chunk in parsed.chunks if chunk.contains_code_block]
    assert len(code_chunks) == 1
    assert code_chunks[0].code_languages == ["bash"]
    assert "whoami\nid\nuname -a" in code_chunks[0].text


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
