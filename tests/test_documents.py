import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile

from app.services.documents import (
    InvalidTextEncodingError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    _build_text_chunks,
    _clean_original_filename,
    _decode_txt,
    _read_limited_upload,
    _validate_txt_upload,
)


def test_txt_import_rejects_non_txt_extension() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        _validate_txt_upload("payload.pdf", "text/plain")


def test_txt_import_rejects_unexpected_content_type() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        _validate_txt_upload("payload.txt", "text/html")


def test_txt_import_requires_utf8() -> None:
    with pytest.raises(InvalidTextEncodingError):
        _decode_txt(b"\xff\xfe\x00")


def test_txt_import_size_limit_is_enforced() -> None:
    upload = UploadFile(filename="payload.txt", file=BytesIO(b"abcdef"))

    with pytest.raises(UploadTooLargeError):
        asyncio.run(_read_limited_upload(upload, max_upload_bytes=5))


def test_txt_import_filename_is_metadata_only_basename() -> None:
    assert _clean_original_filename("../../evidence.txt") == "evidence.txt"


def test_text_chunker_preserves_offsets() -> None:
    text = "First paragraph.\n\nSecond paragraph is longer.\nThird line."

    chunks = _build_text_chunks(text, max_chars=30)

    assert len(chunks) == 2
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text
        assert chunk.text == chunk.text.strip()


def test_text_chunker_skips_whitespace_only_text() -> None:
    assert _build_text_chunks(" \n\n\t ", max_chars=10) == []


def test_text_chunker_rejects_invalid_size() -> None:
    with pytest.raises(ValueError):
        _build_text_chunks("text", max_chars=0)
