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

import app.api.v1.documents as documents_api
from app.models.document import (
    DocumentChunkManifestModel,
    DocumentChunkModel,
    DocumentModel,
    DocumentPageModel,
    DocumentSearchEntryModel,
    DocumentTextLayerModel,
)
from pydantic import ValidationError

from app.schemas.document import DocumentPartialOcrAcceptRequest
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
    _ocr_recommendation_from_stats,
    parse_native_pdf_pages,
    _read_limited_upload,
    _validate_pdf_upload,
    _validate_txt_upload,
    _validate_current_document_processing,
    _pdf_parse_quality_issues,
    _ocr_quality_decision,
    _ocr_quality_issues,
    _create_chunks_from_pages,
    _persist_text_store_manifests,
    _write_ocr_candidate_pages,
)
import app.services.documents as documents_service
from app.services.storage import StoragePaths
from app.services.text_store import read_chunk_text, read_chunks_jsonl, read_page_text, read_pages_jsonl, sha256_file
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


def test_ocr_quality_decision_fails_when_no_text_was_extracted() -> None:
    result = OcrDocumentResult(
        pages=[
            OcrPageResult(page_number=1, text="", confidence=None, image_path=Path("/tmp/page-1.png")),
            OcrPageResult(page_number=2, text="   ", confidence=None, image_path=Path("/tmp/page-2.png")),
        ],
        tool_name="tesseract",
        tool_version="5.3.4",
        language="hun+eng",
    )

    decision = _ocr_quality_decision(result, _ocr_quality_issues(result))

    assert decision == {
        "decision": "failed",
        "usable_page_numbers": [],
        "failed_page_numbers": [1, 2],
        "next_action": "discard_or_replace_document",
    }


def test_ocr_quality_decision_marks_partial_text_for_review() -> None:
    result = OcrDocumentResult(
        pages=[
            OcrPageResult(page_number=1, text="Hasznalhato OCR szoveg.", confidence=0.91, image_path=Path("/tmp/page-1.png")),
            OcrPageResult(page_number=2, text="", confidence=None, image_path=Path("/tmp/page-2.png")),
        ],
        tool_name="tesseract",
        tool_version="5.3.4",
        language="hun+eng",
    )

    decision = _ocr_quality_decision(result, _ocr_quality_issues(result))

    assert decision == {
        "decision": "partial",
        "usable_page_numbers": [1],
        "failed_page_numbers": [2],
        "next_action": "review_partial_ocr_before_text_layer",
    }


def test_ocr_quality_decision_passes_clean_text() -> None:
    result = OcrDocumentResult(
        pages=[
            OcrPageResult(page_number=1, text="Hasznalhato OCR szoveg.", confidence=0.91, image_path=Path("/tmp/page-1.png")),
        ],
        tool_name="tesseract",
        tool_version="5.3.4",
        language="hun+eng",
    )

    decision = _ocr_quality_decision(result, _ocr_quality_issues(result))

    assert decision["decision"] == "passed"
    assert decision["next_action"] == "review_text_layer_then_create_chunks"


def test_ocr_candidate_pages_are_staged_without_creating_text_layer(tmp_path) -> None:
    case_id = uuid4()
    document = DocumentModel(
        id=uuid4(),
        case_id=case_id,
        original_filename="scan.pdf",
        stored_path=str(tmp_path / "scan.pdf"),
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="review_required",
    )
    ocr_run_id = uuid4()
    result = OcrDocumentResult(
        pages=[
            OcrPageResult(page_number=1, text="Hasznalhato OCR szoveg.", confidence=0.91, image_path=Path("/tmp/page-1.png")),
            OcrPageResult(page_number=2, text="", confidence=None, image_path=Path("/tmp/page-2.png")),
        ],
        tool_name="tesseract",
        tool_version="5.3.4",
        language="hun+eng",
    )

    storage_uri = _write_ocr_candidate_pages(StoragePaths(tmp_path), case_id, document, ocr_run_id, result)

    staged_pages = read_pages_jsonl(tmp_path / storage_uri)
    assert [page.page_number for page in staged_pages] == [1, 2]
    assert staged_pages[0].text == "Hasznalhato OCR szoveg."
    assert staged_pages[0].ocr_confidence == 0.91
    assert staged_pages[1].text == ""


def test_partial_ocr_accept_request_normalizes_page_numbers() -> None:
    payload = DocumentPartialOcrAcceptRequest(ocr_run_id=uuid4(), page_numbers=[3, 1])

    assert payload.page_numbers == [1, 3]


def test_partial_ocr_accept_request_rejects_duplicate_page_numbers() -> None:
    with pytest.raises(ValidationError):
        DocumentPartialOcrAcceptRequest(ocr_run_id=uuid4(), page_numbers=[1, 1])


def test_document_page_api_read_accepts_decimal_ocr_confidence(monkeypatch) -> None:
    page = DocumentPageModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
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

    monkeypatch.setattr(documents_api, "read_page_text_from_store", lambda db_arg, page_arg: "OCR szoveg.")

    response = documents_api._page_read(object(), page)

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


def test_text_chunker_prefers_paragraph_break_before_sentence_break() -> None:
    paragraph = " ".join(["Elso bekezdes eleg hosszu"] * 9) + "."
    second = "Masodik mondat mar a kovetkezo reszben folytatodik."
    text = f"{paragraph}\n\n{second}"

    chunks = _build_text_chunks(text, max_chars=260)

    assert [chunk.text for chunk in chunks] == [
        paragraph,
        second,
    ]


def test_text_chunker_prefers_sentence_break_before_line_break() -> None:
    first_sentence = " ".join(["Az elso mondat termeszetes hatara itt veget er"] * 5) + "."
    rest = "Ez a masodik sorban folytatodik\nes meg mindig ugyanaz a gondolat."
    text = f"{first_sentence} {rest}"

    chunks = _build_text_chunks(text, max_chars=260)

    assert chunks[0].text == first_sentence
    assert chunks[1].text == rest


def test_text_chunker_skips_whitespace_only_text() -> None:
    assert _build_text_chunks(" \n\n\t ", max_chars=10) == []


def test_text_chunker_rejects_invalid_size() -> None:
    with pytest.raises(ValueError):
        _build_text_chunks("text", max_chars=0)


def test_ocr_recommendation_is_recommended_when_no_text_exists() -> None:
    page = DocumentPageModel(
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=0,
    )

    recommendation = _ocr_recommendation_from_stats("processed", 1, [page], [])

    assert recommendation.action == "recommended"
    assert recommendation.reason_code == "no_text"


def test_ocr_recommendation_hides_when_text_layer_awaits_chunking() -> None:
    page = DocumentPageModel(
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=500,
    )

    recommendation = _ocr_recommendation_from_stats("text_review_required", 1, [page], [])

    assert recommendation.action == "hidden"
    assert recommendation.reason_code == "text_layer_awaits_chunking"


def test_ocr_recommendation_is_optional_for_empty_pages_with_native_text() -> None:
    document_id = uuid4()
    pages = [
        DocumentPageModel(
                case_id=uuid4(),
                document_id=document_id,
                page_number=1,
                text_source="native",
            ocr_used=False,
            version_no=1,
            is_current=True,
            text_char_count=500,
        ),
        DocumentPageModel(
                case_id=uuid4(),
                document_id=document_id,
                page_number=2,
                text_source="native",
            ocr_used=False,
            version_no=1,
            is_current=True,
            text_char_count=0,
        ),
    ]
    chunks = [
        DocumentChunkModel(
            case_id=uuid4(),
            document_id=document_id,
            page_start=1,
            page_end=1,
            chunk_index=0,
            chunking_strategy="char_window_v2",
            chunker_version="2",
            version_no=1,
            is_current=True,
        )
    ]

    recommendation = _ocr_recommendation_from_stats("processed", 2, pages, chunks)

    assert recommendation.action == "optional"
    assert recommendation.reason_code == "empty_pages_with_text"


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


def test_text_store_manifest_persistence_writes_jsonl_and_models(tmp_path) -> None:
    case_id = uuid4()
    document_id = uuid4()
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename="irat.txt",
        stored_path=str(tmp_path / "cases" / str(case_id) / "originals" / str(document_id) / "original.txt"),
        mime_type="text/plain",
        file_extension="txt",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        page_count=1,
    )
    page = DocumentPageModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=len("Forras szoveg."),
    )
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_start=1,
        page_end=1,
        chunk_index=0,
        char_start=0,
        char_end=13,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
    )
    db = _FakeManifestDb()
    storage = StoragePaths(tmp_path)

    text_layer, chunk_manifest = _persist_text_store_manifests(
        db,
        storage,
        case_id,
        document,
        [page],
        [chunk],
        {page.id: "Forras szoveg."},
        {chunk.id: "Forras szoveg."},
        source_kind="native_text",
        parser_name="txt_import",
        parser_version="1",
        language_code="hu",
        created_by_run_id=None,
    )

    assert text_layer in db.added
    assert chunk_manifest in db.added
    search_entries = [item for item in db.added if isinstance(item, DocumentSearchEntryModel)]
    assert [entry.source_type for entry in search_entries] == ["page", "chunk"]
    assert text_layer.page_count == 1
    assert text_layer.char_count == len("Forras szoveg.")
    assert chunk_manifest.chunk_count == 1
    assert chunk_manifest.text_layer_id == text_layer.id
    pages_path = tmp_path / text_layer.storage_uri
    chunks_path = tmp_path / chunk_manifest.storage_uri
    assert text_layer.manifest_hash == sha256_file(pages_path)
    assert chunk_manifest.manifest_hash == sha256_file(chunks_path)
    assert read_pages_jsonl(pages_path)[0].page_id == str(page.id)
    assert read_chunks_jsonl(chunks_path)[0].chunk_id == str(chunk.id)


def test_create_chunks_from_pages_reads_page_text_through_text_store(monkeypatch) -> None:
    case_id = uuid4()
    document = DocumentModel(
        id=uuid4(),
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path="/tmp/irat.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="text_review_required",
        page_count=1,
    )
    page = DocumentPageModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document.id,
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=36,
    )
    db = _FakeChunkCreationDb()

    monkeypatch.setattr(documents_service, "_list_current_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(documents_service, "_next_chunk_version", lambda *args, **kwargs: 1)
    monkeypatch.setattr(documents_service, "add_analysis_run_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        documents_service,
        "read_page_text_from_store",
        lambda db_arg, page_arg: "Text-store page text is the chunk source.",
    )

    chunk_count, chunk_texts = _create_chunks_from_pages(db, case_id, document, [page], uuid4())

    chunks = [item for item in db.added if isinstance(item, DocumentChunkModel)]
    assert chunk_count == 1
    assert chunk_texts[chunks[0].id] == "Text-store page text is the chunk source."


def test_document_page_api_read_uses_text_store(monkeypatch) -> None:
    page = DocumentPageModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=22,
        created_at=datetime.now(UTC),
    )

    monkeypatch.setattr(
        documents_api,
        "read_page_text_from_store",
        lambda db_arg, page_arg: "Text-store page text.",
    )

    response = documents_api._page_read(object(), page)

    assert response.extracted_text == "Text-store page text."


def test_document_chunk_api_read_uses_text_store(monkeypatch) -> None:
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
        created_at=datetime.now(UTC),
    )

    monkeypatch.setattr(
        documents_api,
        "read_chunk_text_from_store",
        lambda db_arg, chunk_arg: "Text-store chunk text.",
    )

    response = documents_api._chunk_read(object(), chunk)

    assert response.chunk_text == "Text-store chunk text."


def test_text_store_fallback_returns_empty_string_without_db_text_columns() -> None:
    page = DocumentPageModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=0,
        created_at=datetime.now(UTC),
    )
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
        created_at=datetime.now(UTC),
    )

    assert read_page_text(page) == ""
    assert read_chunk_text(chunk) == ""


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


class _FakeManifestDb:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, item) -> None:
        if isinstance(item, (DocumentTextLayerModel, DocumentChunkManifestModel, DocumentSearchEntryModel)):
            self.added.append(item)

    def flush(self) -> None:
        self.flush_count += 1


class _FakeChunkCreationDb:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        self.flush_count += 1


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
