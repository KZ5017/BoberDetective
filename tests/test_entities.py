from uuid import uuid4

import pytest

from app.models.document import DocumentModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.source_reference import SourceReferenceModel
from app.services.entities import (
    EntityNotFoundError,
    EntityValidationError,
    _find_existing_entity,
    _review_status_for_action,
    create_entity_with_mention,
    detach_entity_mention,
    merge_entity,
    move_entity_mention,
)


class _FakeDb:
    def get(self, model, key):
        return None


class _FakeScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self._rows


class _FakeQueryDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, statement):
        return _FakeScalarRows(self._rows)


def test_create_entity_requires_canonical_name() -> None:
    with pytest.raises(EntityValidationError):
        create_entity_with_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_type="person",
            canonical_name=" ",
            normalized_value=None,
            description=None,
            surface_text="Kovacs Anna",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_entity_requires_analysis_run() -> None:
    with pytest.raises(EntityValidationError):
        create_entity_with_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_type="person",
            canonical_name="Kovacs Anna",
            normalized_value=None,
            description=None,
            surface_text="Kovacs Anna",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_merge_entity_rejects_same_source_and_target() -> None:
    entity_id = uuid4()
    with pytest.raises(EntityValidationError):
        merge_entity(
            _FakeDb(),
            case_id=uuid4(),
            source_entity_id=entity_id,
            target_entity_id=entity_id,
        )


def test_merge_entity_rejects_corrected_target() -> None:
    case_id = uuid4()
    source = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    target = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="corrected",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    with pytest.raises(EntityValidationError, match="Corrected entities cannot be merge targets"):
        merge_entity(
            _Db(),
            case_id=case_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
        )


def test_merge_entity_rejects_source_without_mentions(monkeypatch) -> None:
    case_id = uuid4()
    source = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    target = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    monkeypatch.setattr("app.services.entities.list_entity_mentions", lambda db, entity_id: [])

    with pytest.raises(EntityValidationError, match="Entities without sources cannot be merged"):
        merge_entity(
            _Db(),
            case_id=case_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
        )


def test_detach_entity_mention_requires_existing_entity() -> None:
    with pytest.raises(EntityNotFoundError):
        detach_entity_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_id=uuid4(),
            mention_id=uuid4(),
        )


def test_move_entity_mention_reactivates_corrected_target(monkeypatch) -> None:
    case_id = uuid4()
    source = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    target = EntityModel(
        id=uuid4(),
        case_id=case_id,
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        created_by_analysis_run_id=uuid4(),
        review_status="corrected",
    )
    mention = EntityMentionModel(
        id=uuid4(),
        case_id=case_id,
        entity_id=source.id,
        document_id=uuid4(),
        surface_text="Dupin",
        source_reference_id=uuid4(),
        created_by_analysis_run_id=uuid4(),
    )
    document = DocumentModel(
        id=mention.document_id,
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path="/tmp/irat.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        lifecycle_status="active",
    )
    source_reference = SourceReferenceModel(
        id=mention.source_reference_id,
        case_id=case_id,
        document_id=document.id,
        quote_text="Dupin",
    )

    class _Db:
        def __init__(self):
            self.added = []

        def get(self, model, key):
            return {source.id: source, target.id: target, mention.id: mention, source_reference.id: source_reference, document.id: document}.get(key)

        def add(self, item):
            self.added.append(item)

        def flush(self):
            pass

        def commit(self):
            pass

        def refresh(self, item):
            pass

    class _AuditWriter:
        def __init__(self, *args, **kwargs):
            pass

        def write(self, event):
            return None

    db = _Db()
    monkeypatch.setattr("app.services.entities.get_or_create_dev_user", lambda db: type("User", (), {"id": uuid4()})())
    monkeypatch.setattr("app.services.entities.DatabaseAuditWriter", _AuditWriter)
    monkeypatch.setattr("app.services.entities.JsonlAuditWriter", _AuditWriter)
    monkeypatch.setattr("app.services.entities.list_entity_mentions", lambda db, entity_id: [])

    move_entity_mention(
        db,
        case_id=case_id,
        source_entity_id=source.id,
        mention_id=mention.id,
        target_entity_id=target.id,
    )

    assert mention.entity_id == target.id
    assert target.review_status == "needs_review"
    target_reviews = [item for item in db.added if getattr(item, "object_id", None) == target.id]
    assert target_reviews[-1].previous_review_status == "corrected"
    assert target_reviews[-1].new_review_status == "needs_review"
    assert target_reviews[-1].correction_patch_json["reactivated_corrected_target"] is True


def test_find_existing_entity_matches_same_canonical_name() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )

    existing = _find_existing_entity(
        _FakeQueryDb([entity]),
        entity.case_id,
        "person",
        " dupin ",
        None,
    )

    assert existing == entity


def test_find_existing_person_entity_does_not_guess_longer_name_alias() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )

    existing = _find_existing_entity(
        _FakeQueryDb([entity]),
        entity.case_id,
        "person",
        "Dupin",
        None,
    )

    assert existing is None


def test_entity_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_entity_review_status_rejects_unknown_action() -> None:
    with pytest.raises(EntityValidationError):
        _review_status_for_action("publish", "needs_review")
