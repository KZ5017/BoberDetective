from dataclasses import dataclass


UNCATEGORIZED_GROUP_CODE = "uncategorized"
UNCATEGORIZED_TYPE_CODE = "uncategorized"


@dataclass(frozen=True)
class DocumentTypeDefinition:
    code: str
    label: str
    description: str


@dataclass(frozen=True)
class DocumentGroupDefinition:
    code: str
    label: str
    description: str
    types: tuple[DocumentTypeDefinition, ...]


DOCUMENT_TAXONOMY: tuple[DocumentGroupDefinition, ...] = (
    DocumentGroupDefinition(
        code="authority_decisions",
        label="Hatósági döntések és rendelkezések",
        description="A nyomozó hatóság vagy ügyészség formális döntései, rendelkezései és hivatalos megkeresései.",
        types=(
            DocumentTypeDefinition("hatarozat", "Határozat", "Érdemi vagy eljárási hatósági döntés."),
            DocumentTypeDefinition("intezkedes", "Intézkedés", "Külön határozatot nem feltétlenül igénylő hatósági lépés."),
            DocumentTypeDefinition("megkereses", "Megkeresés", "Más hatósághoz vagy szervezethez intézett hivatalos adatkérés."),
        ),
    ),
    DocumentGroupDefinition(
        code="procedural_records",
        label="Eljárási cselekmények rögzítése",
        description="A nyomozási cselekményeket, kihallgatásokat, szemléket és kapcsolódó rögzítéseket dokumentáló iratok.",
        types=(
            DocumentTypeDefinition("jegyzokonyv", "Jegyzőkönyv", "Kihallgatásról, szemléről, kutatásról vagy más eljárási cselekményről készült jegyzőkönyv."),
            DocumentTypeDefinition("feljegyzes", "Feljegyzés", "Rövidebb hivatali rögzítés vagy eljárási megjegyzés."),
            DocumentTypeDefinition(
                "kep_hangfelvetel_leirat",
                "Kép- és hangfelvétel leirata",
                "Felvételhez kapcsolódó szöveges leirat vagy rögzítési dokumentum.",
            ),
        ),
    ),
    DocumentGroupDefinition(
        code="evidence_expert_materials",
        label="Bizonyítékok és szakértői anyagok",
        description="A tényállás tisztázására beszerzett szakmai vagy bizonyítási iratok.",
        types=(
            DocumentTypeDefinition("szakertoi_velemeny", "Szakértői vélemény", "Igazságügyi vagy más szakértő által készített vélemény."),
            DocumentTypeDefinition(
                "szaktanacsadoi_felvilagositas",
                "Szaktanácsadói felvilágosítás",
                "Szaktanácsadó írásos szakmai felvilágosítása.",
            ),
            DocumentTypeDefinition("kornyezettanulmany", "Környezettanulmány", "Életkörülményeket vagy személyi hátteret bemutató dokumentum."),
            DocumentTypeDefinition(
                "bunugyi_technikai_jelentes",
                "Bűnügyi technikai jelentés",
                "Nyomrögzítésről, mintavételről vagy technikai vizsgálatról készült jelentés.",
            ),
            DocumentTypeDefinition("okirati_bizonyitek", "Okirati bizonyíték", "Külső forrásból származó vagy ügyhöz kapcsolódó okirat."),
        ),
    ),
    DocumentGroupDefinition(
        code="participant_submissions",
        label="Résztvevők által benyújtott iratok",
        description="Sértett, bejelentő, gyanúsított, védő vagy más résztvevő által benyújtott iratok.",
        types=(
            DocumentTypeDefinition("feljelentes", "Feljelentés", "Eljárást megindító vagy kezdeményező bejelentés."),
            DocumentTypeDefinition("inditvany", "Indítvány", "Bizonyítási vagy más eljárási kérelem."),
            DocumentTypeDefinition("eszrevetel", "Észrevétel", "Eljárási cselekményre vagy bizonyítékra tett írásos reflexió."),
            DocumentTypeDefinition("panasz", "Panasz", "Határozat vagy intézkedés elleni jogorvoslati irat."),
            DocumentTypeDefinition(
                "mento_korulmenyek_igazolasa",
                "Mentő körülmények igazolása",
                "Védelem által benyújtott alibi, igazolás vagy más mentő dokumentum.",
            ),
        ),
    ),
    DocumentGroupDefinition(
        code="closing_documents",
        label="A nyomozás lezárásának iratai",
        description="A vizsgálati szakasz végéhez és az iratismertetéshez kapcsolódó záró dokumentumok.",
        types=(
            DocumentTypeDefinition(
                "iratismertetesi_jegyzokonyv",
                "Iratismertetési jegyzőkönyv",
                "Az iratok megismerését igazoló dokumentum.",
            ),
            DocumentTypeDefinition(
                "vademelesi_javaslat_nyomozast_lezaro_jelentes",
                "Vádemelési javaslat / nyomozást lezáró jelentés",
                "A bizonyítékokat összegző és az ügyészség felé továbbító záró jelentés.",
            ),
        ),
    ),
    DocumentGroupDefinition(
        code=UNCATEGORIZED_GROUP_CODE,
        label="Nem kategorizált",
        description="Átmeneti vagy meglévő iratok biztonságos alapbesorolása.",
        types=(
            DocumentTypeDefinition(
                UNCATEGORIZED_TYPE_CODE,
                "Nem kategorizált",
                "Nincs még szakmailag rögzített iratbesorolás.",
            ),
        ),
    ),
)


def list_document_taxonomy() -> tuple[DocumentGroupDefinition, ...]:
    return DOCUMENT_TAXONOMY


def default_document_taxonomy_codes() -> tuple[str, str]:
    return UNCATEGORIZED_GROUP_CODE, UNCATEGORIZED_TYPE_CODE


def find_document_group(group_code: str) -> DocumentGroupDefinition | None:
    return next((group for group in DOCUMENT_TAXONOMY if group.code == group_code), None)


def find_document_type(group_code: str, type_code: str) -> DocumentTypeDefinition | None:
    group = find_document_group(group_code)
    if group is None:
        return None
    return next((document_type for document_type in group.types if document_type.code == type_code), None)


def validate_document_taxonomy(group_code: str, type_code: str) -> None:
    if find_document_group(group_code) is None:
        raise ValueError(f"Unknown document group code: {group_code}")
    if find_document_type(group_code, type_code) is None:
        raise ValueError(f"Document type '{type_code}' does not belong to document group '{group_code}'")


def document_taxonomy_labels(group_code: str, type_code: str) -> tuple[str, str]:
    group = find_document_group(group_code)
    document_type = find_document_type(group_code, type_code)
    if group is None or document_type is None:
        return group_code, type_code
    return group.label, document_type.label
