from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.models.document import (
    DocumentChunkManifestModel,
    DocumentChunkModel,
    DocumentModel,
    DocumentPageModel,
    DocumentSearchEntryModel,
    DocumentTextLayerModel,
)
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store, sha256_text


def refresh_page_search_entries(
    db: Session,
    document: DocumentModel,
    text_layer: DocumentTextLayerModel,
    pages: Iterable[DocumentPageModel],
) -> list[DocumentSearchEntryModel]:
    """Refresh page-level lexical entries without changing search behavior yet."""

    _deactivate_current_entries(db, document.id, source_type="page")
    entries: list[DocumentSearchEntryModel] = []
    for page in pages:
        text = read_page_text_from_store(db, page)
        entry = build_page_search_entry(document, text_layer, page, text)
        db.add(entry)
        entries.append(entry)
    return entries


def refresh_chunk_search_entries(
    db: Session,
    document: DocumentModel,
    chunk_manifest: DocumentChunkManifestModel,
    chunks: Iterable[DocumentChunkModel],
) -> list[DocumentSearchEntryModel]:
    """Refresh chunk-level lexical entries without changing search behavior yet."""

    _deactivate_current_entries(db, document.id, source_type="chunk")
    entries: list[DocumentSearchEntryModel] = []
    for chunk in chunks:
        text = read_chunk_text_from_store(db, chunk)
        entry = build_chunk_search_entry(document, chunk_manifest, chunk, text)
        db.add(entry)
        entries.append(entry)
    return entries


def deactivate_document_search_entries(db: Session, document_id, *, source_type: str | None = None) -> None:
    _deactivate_current_entries(db, document_id, source_type=source_type)


def build_page_search_entry(
    document: DocumentModel,
    text_layer: DocumentTextLayerModel,
    page: DocumentPageModel,
    source_text: str,
) -> DocumentSearchEntryModel:
    return DocumentSearchEntryModel(
        case_id=document.case_id,
        document_id=document.id,
        source_type="page",
        page_id=page.id,
        chunk_id=None,
        text_layer_id=text_layer.id,
        chunk_manifest_id=None,
        page_start=page.page_number,
        page_end=page.page_number,
        chunk_index=None,
        lifecycle_status=document.lifecycle_status,
        text_hash=sha256_text(source_text),
        search_vector=func.to_tsvector("simple", source_text),
        is_current=True,
    )


def build_chunk_search_entry(
    document: DocumentModel,
    chunk_manifest: DocumentChunkManifestModel,
    chunk: DocumentChunkModel,
    source_text: str,
) -> DocumentSearchEntryModel:
    return DocumentSearchEntryModel(
        case_id=document.case_id,
        document_id=document.id,
        source_type="chunk",
        page_id=None,
        chunk_id=chunk.id,
        text_layer_id=chunk_manifest.text_layer_id,
        chunk_manifest_id=chunk_manifest.id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        chunk_index=chunk.chunk_index,
        lifecycle_status=document.lifecycle_status,
        text_hash=sha256_text(source_text),
        search_vector=func.to_tsvector("simple", source_text),
        is_current=True,
    )


def _deactivate_current_entries(db: Session, document_id, *, source_type: str | None = None) -> None:
    stmt = (
        update(DocumentSearchEntryModel)
        .where(
            DocumentSearchEntryModel.document_id == document_id,
            DocumentSearchEntryModel.is_current.is_(True),
        )
        .values(is_current=False, updated_at=datetime.now(UTC))
    )
    if source_type is not None:
        stmt = stmt.where(DocumentSearchEntryModel.source_type == source_type)
    try:
        db.execute(stmt)
    except AttributeError:
        return
