from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.document_processing import DocumentProcessingItemModel
from app.schemas.full_document_processing import DocumentProcessingItemRead
from app.services.full_document_processing import (
    FullDocumentProcessingValidationError,
    FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT,
    PROFILES,
    build_full_document_processing_user_prompt,
    validate_full_document_processing_payload,
    list_profiles,
    update_document_processing_item_status,
)


class _FakeDb:
    def __init__(self, item=None):
        self.item = item

    def get(self, model, key):
        if model is DocumentProcessingItemModel and self.item is not None and self.item.id == key:
            return self.item
        return None

    def add(self, item):
        pass

    def commit(self):
        pass

    def refresh(self, item):
        pass


def test_full_document_processing_profiles_are_hungarian_and_stable() -> None:
    profiles = list_profiles()

    assert [profile.key for profile in profiles] == ["person_search_seeds"]
    assert profiles[0].label == "Személykeresési fókuszok"
    assert "person" in profiles[0].item_kinds


def test_full_document_processing_prompts_keep_rules_in_system_and_data_in_user_prompt() -> None:
    document = type("Document", (), {"original_filename": "irat.pdf"})()
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Kovács Ágnes, eladólány az Általános Áruházban.",
        }
    ]

    user_prompt = build_full_document_processing_user_prompt(profile=PROFILES[0], document=document, page_sources=page_sources)

    assert "Forráshű teljes iratfeldolgozó komponens vagy." in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "Alapelvek:" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "Feladat:" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "Mezőszabályok:" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "JSON szabályok:" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "Add vissza JSON formában a SOURCE-ban szereplő személyeket." in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "short_description" not in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "A recommended_search_focus rövid keresési kifejezés legyen" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "display_label + 1-4 forrásbeli szó" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "őrizd meg a SOURCE szerinti írásmódot" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "ne cseréld át másik idézőjelre" in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "A source_label megadása minden items elemben kötelező." in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert '"recommended_search_focus":"..."' in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "unsupported_items" not in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert '{"items":[]}' in FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT
    assert "DOCUMENT:\nirat.pdf" in user_prompt
    assert "PROFILE:\nperson_search_seeds" in user_prompt
    assert "SOURCE:\npage_1:" in user_prompt
    assert "Kovács Ágnes" in user_prompt
    assert "TASK:" not in user_prompt
    assert "JSON forma:" not in user_prompt
    assert "Mezőszabályok:" not in user_prompt
    assert "Add vissza JSON formában" not in user_prompt


def test_document_processing_item_schema_accepts_graph_ready_fields() -> None:
    item = DocumentProcessingItemModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        analysis_run_id=uuid4(),
        profile_key="person_search_seeds",
        item_kind="person",
        display_label="Pauline Dubourg",
        short_description="Mosónő, aki az áldozatoknak mosott.",
        mentioned_forms_json=["Pauline Dubourg"],
        source_supported_details_json=[{"detail": "mosónő"}],
        relationships_json=[{"target": "Madame L'Espanaye", "relation": "mosott rá"}],
        recommended_search_focus="Pauline Dubourg mosónő",
        alternative_search_focuses_json=["Pauline Dubourg tanúvallomása"],
        source_evidence_json=[{"document_id": str(uuid4()), "page": 7}],
        work_status="active",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    read = DocumentProcessingItemRead.model_validate(item)

    assert read.display_label == "Pauline Dubourg"
    assert read.item_kind == "person"
    assert read.recommended_search_focus == "Pauline Dubourg mosónő"
    assert read.source_supported_details_json[0]["detail"] == "mosónő"


def test_update_document_processing_item_status_rejects_converted_target() -> None:
    item = DocumentProcessingItemModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        analysis_run_id=uuid4(),
        profile_key="person_search_seeds",
        item_kind="person",
        display_label="Pauline Dubourg",
        work_status="converted",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(FullDocumentProcessingValidationError):
        update_document_processing_item_status(_FakeDb(item), case_id=item.case_id, item_id=item.id, work_status="deleted")


def test_update_document_processing_item_status_accepts_set_aside() -> None:
    item = DocumentProcessingItemModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        analysis_run_id=uuid4(),
        profile_key="person_search_seeds",
        item_kind="person",
        display_label="Pauline Dubourg",
        work_status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    updated = update_document_processing_item_status(_FakeDb(item), case_id=item.case_id, item_id=item.id, work_status="set_aside")

    assert updated.work_status == "set_aside"


def test_validate_full_document_processing_payload_keeps_source_exact_items() -> None:
    page_id = uuid4()
    document_id = uuid4()
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Pauline Dubourg",
                "short_description": "Pauline Dubourg mosónő, aki három éve ismeri az áldozatokat.",
                "recommended_search_focus": "Pauline Dubourg mosónő áldozatok",
                "mentioned_forms": ["Pauline Dubourg"],
                "source_supported_details": [{"detail": "mosónő", "source_label": "page_7"}],
                "relationships": [],
                "alternative_search_focuses": ["Pauline Dubourg tanúvallomása"],
                "source_evidence": [
                    {
                        "source_label": "page_7",
                        "quote_text": "Pauline Dubourg, mosónő, kijelenti, hogy három éve ismeri mind a két áldozatot.",
                    }
                ],
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_7",
            "document_id": document_id,
            "page_id": page_id,
            "page_number": 7,
            "text": "Pauline Dubourg, mosónő, kijelenti, hogy három éve ismeri mind a két áldozatot. Ennyi ideje mos rájuk.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["display_label"] == "Pauline Dubourg"
    assert valid_items[0]["recommended_search_focus"] == "Pauline Dubourg mosónő áldozatok"
    assert valid_items[0]["source_evidence"][0]["quote_char_start"] == 0
    assert valid_items[0]["source_evidence"][0]["page_id"] == str(page_id)


def test_validate_full_document_processing_payload_falls_back_to_label_when_focus_is_missing() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Kovács Ágnes",
                "source_label": "page_1",
            }
        ],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Kovács Ágnes, eladólány az Általános Áruházban.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["recommended_search_focus"] == "Kovács Ágnes"


def test_validate_full_document_processing_payload_repairs_wrong_source_label_when_label_exists_elsewhere() -> None:
    page_id = uuid4()
    document_id = uuid4()
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Anna nővér",
                "short_description": "Anna nővér hatalmában tartja dr. Torbágyot.",
                "source_label": "page_1",
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": document_id,
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Címlap.",
        },
        {
            "source_label": "page_2",
            "document_id": document_id,
            "page_id": page_id,
            "page_number": 2,
            "text": "Anna nővér, aki hatalmában tartja dr. Torbágyot.",
        },
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["source_evidence"][0]["source_label"] == "page_2"
    assert valid_items[0]["source_evidence"][0]["page_id"] == str(page_id)
    assert valid_items[0]["source_evidence"][0]["quote_text"] == "Anna nővér"


def test_validate_full_document_processing_payload_rejects_non_source_quote() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Kitalált személy",
                "source_evidence": [{"source_label": "page_1", "quote_text": "Ez nincs a forrásban."}],
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Valódi forrásszöveg.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert len(valid_items) == 1
    assert valid_items[0]["display_label"] == "Kitalált személy"
    assert valid_items[0]["source_evidence"] == []
    assert valid_items[0]["source_supported_details"][-1]["validation_status"] == "unconfirmed"
    assert valid_items[0]["source_supported_details"][-1]["llm_source_label"] == "page_1"
    assert "a név nem található" in unsupported[0]


def test_validate_full_document_processing_payload_accepts_ocr_spacing_variant() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Dr. Bloch alorvos",
                "source_evidence": [{"source_label": "page_1", "quote_text": "Dr. Bloch al orvos"}],
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Dr. Bloch alorvos megjelent.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["source_evidence"][0]["quote_text"] == "Dr. Bloch alorvos"


def test_validate_full_document_processing_payload_builds_source_quote_from_label_spacing_variant() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Pistabá",
                "short_description": "Helyi szereplő.",
                "source_label": "page_1",
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Pista bá megérkezett a helyszínre.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["source_evidence"][0]["quote_text"] == "Pista bá"


def test_validate_full_document_processing_payload_rejects_parenthetical_alias_label() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Zlinek Zsófia (Pipi nővér)",
                "short_description": "Nővér.",
                "source_label": "page_1",
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Zlinek Zsófia , akit itt Pipi nővérnek neveznek.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert len(valid_items) == 1
    assert valid_items[0]["display_label"] == "Zlinek Zsófia (Pipi nővér)"
    assert valid_items[0]["source_evidence"] == []
    assert valid_items[0]["recommended_search_focus"] == "Zlinek Zsófia (Pipi nővér)"
    assert valid_items[0]["source_supported_details"][-1]["validation_status"] == "unconfirmed"
    assert valid_items[0]["source_supported_details"][-1]["llm_source_label"] == "page_1"
    assert "a név nem található" in unsupported[0]


def test_validate_full_document_processing_payload_builds_source_quote_from_reversed_descriptor_name() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Vén Márton",
                "short_description": "Szanitéc.",
                "source_label": "page_7",
            }
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_7",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 7,
            "text": "Márton, a vén szanitéc, jól elrendezte az óndobozát.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert unsupported == []
    assert valid_items[0]["source_evidence"][0]["quote_text"] == "Márton"


def test_validate_full_document_processing_payload_keeps_repeated_exact_labels() -> None:
    payload = {
        "items": [
            {
                "item_kind": "person",
                "display_label": "Kovács Ágnes",
                "source_label": "page_1",
            },
            {
                "item_kind": "person",
                "display_label": "Kovács Ágnes",
                "source_label": "page_2",
            },
        ],
        "unsupported_items": [],
    }
    page_sources = [
        {
            "source_label": "page_1",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 1,
            "text": "Kovács Ágnes eladólány.",
        },
        {
            "source_label": "page_2",
            "document_id": uuid4(),
            "page_id": uuid4(),
            "page_number": 2,
            "text": "Kovács Ágnes rosszul lett.",
        }
    ]

    valid_items, unsupported = validate_full_document_processing_payload(payload, PROFILES[0], page_sources)

    assert len(valid_items) == 2
    assert unsupported == []
