import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
import importlib.util
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.schemas.document import DocumentPageRead
from app.services.ocr import ocr_pdf_document, render_pdf_pages_to_images
from app.services.pdf_parsers import NoExtractedTextError, PdfParsingError, parse_pdf
from app.services.documents import (
    InvalidTextEncodingError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    _build_text_chunks,
    _clean_original_filename,
    _decode_txt,
    _is_pdf_upload,
    parse_native_pdf_pages,
    _read_limited_upload,
    _validate_pdf_upload,
    _validate_txt_upload,
    _validate_current_document_processing,
    _pdf_parse_quality_issues,
    _ocr_quality_issues,
)
from app.services.ocr import OcrDocumentResult, OcrPageResult


def test_txt_import_rejects_non_txt_extension() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        _validate_txt_upload("payload.pdf", "text/plain")


def test_txt_import_rejects_unexpected_content_type() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        _validate_txt_upload("payload.txt", "text/html")


def test_pdf_import_accepts_pdf_extension_and_content_type() -> None:
    _validate_pdf_upload("payload.pdf", "application/pdf")


def test_pdf_import_rejects_unexpected_content_type() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        _validate_pdf_upload("payload.pdf", "text/plain")


def test_import_dispatch_detects_pdf_by_extension_or_content_type() -> None:
    assert _is_pdf_upload("payload.pdf", "application/octet-stream") is True
    assert _is_pdf_upload("payload.bin", "application/pdf") is True
    assert _is_pdf_upload("payload.txt", "text/plain") is False


def test_parse_native_pdf_pages_extracts_text_from_simple_pdf() -> None:
    pages = parse_native_pdf_pages(_simple_text_pdf("Forras szoveg PDF importhoz."))

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Forras szoveg" in pages[0].text


def test_pypdf_parser_profile_extracts_multiple_pages() -> None:
    result = parse_pdf(_text_pdf_pages(["Elso oldal forras.", "Masodik oldal forras."]), "pypdf")

    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Elso oldal" in result.pages[0].text
    assert "Masodik oldal" in result.pages[1].text


def test_pypdf_parser_profile_records_parser_metadata() -> None:
    result = parse_pdf(_simple_text_pdf("Forras szoveg PDF importhoz."), "pypdf")

    assert result.parser_name == "pypdf"
    assert result.parser_profile == "pypdf_native_v1"
    assert result.pages[0].page_number == 1


def test_docling_parser_profile_extracts_text_when_installed() -> None:
    if importlib.util.find_spec("docling") is None:
        pytest.skip("docling optional dependency is not installed")

    result = parse_pdf(_simple_text_pdf("Forras szoveg Docling parser teszthez."), "docling")

    assert result.parser_name == "docling"
    assert result.parser_profile == "docling_native_v1"
    assert "Forras szoveg" in result.pages[0].text


def test_pdf_parser_rejects_unknown_profile() -> None:
    with pytest.raises(PdfParsingError):
        parse_pdf(_simple_text_pdf("Forras szoveg PDF importhoz."), "unknown")


def test_pdf_parser_rejects_corrupt_pdf() -> None:
    with pytest.raises(PdfParsingError):
        parse_pdf(b"%PDF-1.4\nnot a complete pdf", "pypdf")


def test_pdf_parse_quality_flags_empty_pages() -> None:
    issues = _pdf_parse_quality_issues(
        [
            type("Page", (), {"page_number": 1, "text": "Forras szoveg."})(),
            type("Page", (), {"page_number": 2, "text": ""})(),
        ]
    )

    assert issues == [{"code": "empty_pages", "severity": "warning", "page_numbers": [2]}]


def test_ocr_quality_flags_empty_pages() -> None:
    result = type(
        "OcrResult",
        (),
        {
            "pages": [
                type("Page", (), {"page_number": 1, "text": "Forras szoveg."})(),
                type("Page", (), {"page_number": 2, "text": ""})(),
            ]
        },
    )()

    assert _ocr_quality_issues(result) == [
        {"code": "empty_ocr_pages", "severity": "warning", "page_numbers": [2]}
    ]


def test_ocr_quality_flags_low_confidence_pages() -> None:
    result = OcrDocumentResult(
        pages=[
            OcrPageResult(page_number=1, text="Jo OCR szoveg.", confidence=0.91, image_path=Path("/tmp/page-1.png")),
            OcrPageResult(page_number=2, text="Gyenge OCR szoveg.", confidence=0.42, image_path=Path("/tmp/page-2.png")),
        ],
        tool_name="tesseract",
        tool_version="5.3.4",
        language="hun+eng",
    )

    issues = _ocr_quality_issues(result)

    assert issues == [
        {
            "code": "low_ocr_confidence",
            "severity": "warning",
            "threshold": 0.5,
            "pages": [{"page_number": 2, "confidence": 0.42}],
        }
    ]


def test_document_page_schema_accepts_decimal_ocr_confidence() -> None:
    page = DocumentPageModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
        extracted_text="OCR szoveg.",
        text_source="ocr",
        ocr_used=True,
        ocr_confidence=Decimal("0.9432"),
        parser_name="tesseract",
        parser_version="5.3.4",
        version_no=1,
        is_current=True,
        text_char_count=10,
        created_at=datetime.now(UTC),
    )

    response = DocumentPageRead.model_validate(page)

    assert response.ocr_confidence == 0.9432


def test_native_pdf_parser_flags_image_only_pdf_as_no_text() -> None:
    with pytest.raises(NoExtractedTextError):
        parse_pdf(_image_only_pdf("Forras OCR TESZT 123"), "pypdf")


def test_pdf_pages_can_be_rendered_for_ocr(tmp_path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(_simple_text_pdf("Forras szoveg OCR renderhez."))

    image_paths = render_pdf_pages_to_images(pdf_path, tmp_path, run_id=uuid4())

    assert len(image_paths) == 1
    assert image_paths[0].is_file()
    assert image_paths[0].suffix == ".png"


def test_tesseract_ocr_reads_rendered_pdf_text(tmp_path) -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is not installed")

    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(_simple_text_pdf("Forras szoveg OCR teszthez."))
    result = ocr_pdf_document(
        pdf_path,
        tmp_path / "ocr",
        tesseract_cmd="tesseract",
        languages="hun+eng",
        run_id=uuid4(),
    )

    assert result.tool_name == "tesseract"
    assert result.pages[0].confidence is not None
    assert 0 <= result.pages[0].confidence <= 1
    assert result.pages[0].text
    assert "Forras" in result.pages[0].text or "OCR" in result.pages[0].text


def test_tesseract_ocr_reads_image_only_pdf_text(tmp_path) -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is not installed")

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(_image_only_pdf("Forras OCR TESZT 123"))
    result = ocr_pdf_document(
        pdf_path,
        tmp_path / "ocr",
        tesseract_cmd="tesseract",
        languages="hun+eng",
        run_id=uuid4(),
    )

    assert result.pages[0].text
    assert result.pages[0].confidence is not None
    assert 0 <= result.pages[0].confidence <= 1
    assert "Forras" in result.pages[0].text or "OCR" in result.pages[0].text


def test_txt_import_requires_utf8() -> None:
    with pytest.raises(InvalidTextEncodingError):
        _decode_txt(b"\xff\xfe\x00")


def test_txt_import_size_limit_is_enforced() -> None:
    upload = UploadFile(filename="payload.txt", file=BytesIO(b"abcdef"))

    with pytest.raises(UploadTooLargeError, match="5 B"):
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


def test_document_processing_validation_passes_for_current_page_and_chunk() -> None:
    case_id = uuid4()
    document_id = uuid4()
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename="irat.txt",
        stored_path="/tmp/irat.txt",
        mime_type="text/plain",
        file_extension="txt",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processing",
        page_count=1,
    )
    page = DocumentPageModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_number=1,
        extracted_text="Forras szoveg.",
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=13,
    )
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunk_text="Forras szoveg.",
        char_start=0,
        char_end=13,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )

    result = _validate_current_document_processing(document, [page], [chunk])

    assert result["run_status"] == "succeeded"
    assert result["validation_status"] == "passed"
    assert result["document_status"] == "processed"
    assert result["issues"] == []


def test_document_processing_validation_requires_current_pages() -> None:
    document = DocumentModel(
        id=uuid4(),
        case_id=uuid4(),
        original_filename="irat.txt",
        stored_path="/tmp/irat.txt",
        mime_type="text/plain",
        file_extension="txt",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processing",
    )

    result = _validate_current_document_processing(document, [], [])

    assert result["run_status"] == "failed"
    assert result["validation_status"] == "failed"
    assert result["document_status"] == "failed"
    assert result["issues"][0]["code"] == "no_current_pages"


def _simple_text_pdf(text: str) -> bytes:
    return _text_pdf_pages([text])


def _image_only_pdf(text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 72)
    except OSError:
        font = ImageFont.load_default()
    draw.text((120, 320), text, fill="black", font=font)

    output = BytesIO()
    image.save(output, format="PDF", resolution=150.0)
    return output.getvalue()


def _text_pdf_pages(page_texts: list[str]) -> bytes:
    kids = " ".join(f"{4 + index * 2} 0 R" for index in range(len(page_texts))).encode()
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_texts)).encode() + b" >> endobj\n",
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    for index, text in enumerate(page_texts):
        page_object_number = 4 + index * 2
        content_object_number = page_object_number + 1
        escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 24 Tf 72 720 Td ({escaped_text}) Tj ET".encode()
        objects.append(
            f"{page_object_number} 0 obj ".encode()
            + b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            + b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{content_object_number} 0 R >> endobj\n".encode()
        )
        objects.append(
            f"{content_object_number} 0 obj << /Length ".encode()
            + str(len(content)).encode()
            + b" >> stream\n"
            + content
            + b"\nendstream endobj\n"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)
