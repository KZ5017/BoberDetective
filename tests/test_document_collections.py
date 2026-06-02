from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.api.v1.document_collections as document_collections_api
from app.schemas.document_collection import (
    DocumentCollectionCreate,
    DocumentCollectionScopeResolveRequest,
)
from app.services.document_collections import (
    CollectionCounts,
    DocumentCollectionNameConflictError,
    MembershipChangeResult,
    ScopeResolution,
    _unique_uuids,
)


def test_document_collection_scope_requires_collection_ids() -> None:
    with pytest.raises(ValidationError):
        DocumentCollectionScopeResolveRequest(source_mode="collections")


def test_document_collection_scope_accepts_document_scope() -> None:
    document_id = uuid4()

    payload = DocumentCollectionScopeResolveRequest(source_mode="documents", document_ids=[document_id])

    assert payload.source_mode == "documents"
    assert payload.document_ids == [document_id]


def test_unique_uuids_preserves_first_seen_order() -> None:
    first = uuid4()
    second = uuid4()

    assert _unique_uuids([first, second, first]) == [first, second]


def test_membership_change_result_counts_skipped_reasons() -> None:
    result = MembershipChangeResult(
        collection_id=uuid4(),
        requested_count=3,
        added_count=1,
        skipped_reasons=["missing", "other_case"],
    )

    assert result.skipped_count == 2


def test_scope_resolution_exposes_preview_limit() -> None:
    document_ids = [uuid4() for _ in range(55)]
    resolution = ScopeResolution(
        source_mode="collections",
        requested_document_ids=[],
        requested_collection_ids=[uuid4()],
        resolved_document_ids=document_ids,
        inactive_document_count=2,
        duplicate_membership_count=4,
        warnings=[],
    )

    assert resolution.active_document_count == 55
    assert resolution.resolved_document_count == 55
    assert resolution.document_ids_preview == document_ids[:50]


def test_document_collection_api_list_includes_counts(monkeypatch) -> None:
    collection_id = uuid4()
    case_id = uuid4()
    user_id = uuid4()
    collection = SimpleNamespace(
        id=collection_id,
        case_id=case_id,
        name="Joganyag",
        description=None,
        color="#336699",
        sort_order=3,
        created_by_user_id=user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    monkeypatch.setattr(document_collections_api, "list_document_collections", lambda db, case_id: [collection])
    monkeypatch.setattr(
        document_collections_api,
        "get_collection_counts",
        lambda db, collection_id: CollectionCounts(total_document_count=7, active_document_count=5),
    )

    response = document_collections_api.get_document_collections(case_id, db=object())

    assert response.data[0].name == "Joganyag"
    assert response.data[0].document_count == 7
    assert response.data[0].active_document_count == 5


def test_document_collection_api_maps_name_conflict(monkeypatch) -> None:
    def _raise_conflict(db, case_id, payload):
        raise DocumentCollectionNameConflictError("name conflict")

    monkeypatch.setattr(document_collections_api, "create_document_collection", _raise_conflict)

    with pytest.raises(HTTPException) as exc:
        document_collections_api.post_document_collection(uuid4(), DocumentCollectionCreate(name="Dupla"), db=object())

    assert exc.value.status_code == 409
