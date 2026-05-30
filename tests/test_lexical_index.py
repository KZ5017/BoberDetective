from uuid import uuid4

from sqlalchemy.sql.functions import Function

from app.models.document import (
    DocumentChunkManifestModel,
    DocumentChunkModel,
    DocumentModel,
    DocumentPageModel,
    DocumentTextLayerModel,
)
from app.services.lexical_index import build_chunk_search_entry, build_page_search_entry
from app.services.text_store import sha256_text


def test_build_page_search_entry_stores_metadata_and_search_vector_expression() -> None:
    case_id = uuid4()
    document = _document(case_id)
    page = DocumentPageModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document.id,
        page_number=7,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=11,
    )
    text_layer = DocumentTextLayerModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document.id,
        source_kind="native_text",
        page_count=1,
        char_count=21,
        storage_uri="cases/case/doc/pages.jsonl",
        manifest_hash="a" * 64,
    )

    entry = build_page_search_entry(document, text_layer, page, "Keresheto oldal szoveg.")

    assert entry.source_type == "page"
    assert entry.page_id == page.id
    assert entry.chunk_id is None
    assert entry.page_start == 7
    assert entry.page_end == 7
    assert entry.lifecycle_status == "active"
    assert entry.text_hash == sha256_text("Keresheto oldal szoveg.")
    assert isinstance(entry.search_vector, Function)


def test_build_chunk_search_entry_stores_metadata_and_search_vector_expression() -> None:
    case_id = uuid4()
    document = _document(case_id)
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document.id,
        page_start=2,
        page_end=3,
        chunk_index=4,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
    )
    chunk_manifest = DocumentChunkManifestModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document.id,
        text_layer_id=uuid4(),
        chunking_strategy="char_window_v2",
        chunker_version="2",
        chunk_count=1,
        storage_uri="cases/case/doc/chunks.jsonl",
        manifest_hash="b" * 64,
    )

    entry = build_chunk_search_entry(document, chunk_manifest, chunk, "Keresheto chunk szoveg.")

    assert entry.source_type == "chunk"
    assert entry.page_id is None
    assert entry.chunk_id == chunk.id
    assert entry.text_layer_id == chunk_manifest.text_layer_id
    assert entry.chunk_manifest_id == chunk_manifest.id
    assert entry.page_start == 2
    assert entry.page_end == 3
    assert entry.chunk_index == 4
    assert entry.text_hash == sha256_text("Keresheto chunk szoveg.")
    assert isinstance(entry.search_vector, Function)


def _document(case_id):
    return DocumentModel(
        id=uuid4(),
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path="cases/case/originals/irat.pdf",
        mime_type="application/pdf",
        file_size_bytes=123,
        sha256_hash="c" * 64,
        imported_by_user_id=uuid4(),
        lifecycle_status="active",
        processing_status="processed",
    )
