# Lokális Nyomozati Iratintelligencia Rendszer
## Adatbázis-séma v1

## 1. Cél

Ez a dokumentum a PostgreSQL-alapú MVP-1 adatbázis-sémát írja le egy lokálisan futó, auditálható, forráshivatkozott nyomozati iratintelligencia rendszerhez.

A séma elsődleges céljai:

- eredeti dokumentumok változatlan megőrzése,
- oldalszintű és chunk-szintű visszakereshetőség,
- minden AI-objektum forrásalapú és futásalapú visszavezethetősége,
- emberi review és audit teljes naplózhatósága,
- exportálható, ellenőrizhető kimenetek támogatása,
- későbbi jogszabályi RAG modul előkészítése anélkül, hogy azt most implementálnánk.

## 2. Rövid összefoglaló a jelenlegi architektúráról

A projekt egy fully local, offline-képes case analysis workbench.

Az igazságforrások:

- az eredeti dokumentumok,
- az oldalszintű kinyert szöveg,
- a konkrét source reference rekordok,
- az audit log,
- az emberi review döntések.

Az LLM nem igazságforrás, hanem strukturáló komponens. Emiatt a séma központi tervezési elve:

> Minden AI által létrehozott eseménynek, állításnak, entitásnak, ellentmondásjelöltnek, hiányjelöltnek és összefoglalóelemnek visszamutathatónak kell lennie:
>
> 1. legalább egy konkrét forráshelyre,
> 2. az azt létrehozó analysis run rekordra.

Az architektúra logikája:

1. ügy létrehozása,
2. dokumentum import,
3. hash és immutable tárolás,
4. parsing / OCR,
5. page text tárolás,
6. chunkolás,
7. indexelés,
8. keresés / retrieval,
9. strukturált AI-elemzés,
10. human review,
11. export.

## 3. Tervezési alapelvek

### 3.1 PostgreSQL irány

Az MVP relációs adattárolója PostgreSQL.

Indokok:

- erős tranzakciókezelés,
- jó JSONB támogatás,
- full-text search lehetőség,
- audit és riport lekérdezésekhez jól használható,
- lokálisan egyszerűen futtatható.

### 3.2 Eredeti dokumentumok kezelése

Az eredeti fájl nem írható felül és nem módosítható. A `documents` tábla az eredeti fájl metaadatait tartja nyilván, minden származtatott adat külön táblába kerül.

Alapelv:

- az eredeti fájl metaadata immutable,
- a parsing/OCR/chunking eredmények külön rekordok,
- újrafeldolgozás új analysis runnal és új származtatott rekordokkal történik.

### 3.3 AI és emberi output szétválasztása

Az AI által létrehozott rekordoknál:

- `created_by_analysis_run_id` kötelező,
- `review_status` kötelező,
- a source reference kapcsolatok kötelezők üzleti szabályként.

Az emberi beavatkozások nem írják felül nyomtalanul az AI-outputot, hanem review és audit rekordokban is megjelennek.

### 3.4 Forráshivatkozás mint elsődleges objektum

A forráshivatkozás nem egyszerű szövegmező, hanem önálló rekord. Így:

- több output hivatkozhat ugyanarra a forráshelyre,
- a quote validálható,
- az UI-ban az "ugrás a forrásra" stabilan megvalósítható,
- később evidence matrix is könnyebben építhető.

### 3.5 Auditálhatóság

Két audit réteg javasolt:

1. `audit_events` PostgreSQL táblában lekérdezhető eseményekhez,
2. append-only JSONL napló fájlrendszerben immutable jellegű visszaellenőrzéshez.

Ez a dokumentum az adatbázisoldali réteget részletezi.

## 4. Fő entitáskapcsolatok

```text
users
  └─< case_users >─ cases
                     ├─< documents
                     │    ├─< document_pages
                     │    └─< document_chunks
                     ├─< entities
                     │    └─< entity_mentions
                     ├─< events
                     ├─< claims
                     ├─< contradiction_candidates
                     ├─< missing_item_candidates
                     ├─< analysis_runs
                     │    ├─< analysis_run_inputs
                     │    └─< analysis_run_outputs
                     ├─< source_references
                     ├─< human_reviews
                     ├─< exports
                     └─< audit_events
```

## 5. Javasolt közös technikai konvenciók

### 5.1 Kulcsok

- Elsődleges kulcs: `uuid`
- Külső kulcsok: `uuid`
- Időbélyegek: `timestamptz`

### 5.2 Névkonvenció

- táblanevek többes számban, snake_case-ben,
- elsődleges kulcs neve minden táblában `id`,
- idegen kulcsok `<entity>_id` formában.

### 5.3 Státusz- és típusmezők

MVP-ben `text` + `CHECK` ajánlott.

Praktikus javaslat:

- első migrációkhoz `text` + `CHECK`,
- későbbi stabilizálás után opcionálisan `ENUM`.

Indok: a review státuszok, claim típusok, event típusok, run típusok és forrásvalidációs státuszok még várhatóan finomodnak az MVP során.

### 5.4 Soft delete

MVP-ben ne legyen általános soft delete. Inkább:

- `status`,
- `archived_at`,
- `closed_at`

mezők használata javasolt.

Bizonyítéki és audit célú rekordok ne tűnjenek el nyomtalanul.

## 6. Fő táblák

## 6.1 `users`

### Cél

Felhasználók, akik importálnak, elemzést futtatnak, review-znek, exportálnak vagy adminisztrálnak.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| username | text | igen | egyedi bejelentkezési név |
| display_name | text | igen | megjelenített név |
| role | text | igen | `admin`, `analyst`, `reviewer`, `viewer` |
| is_active | boolean | igen | aktív státusz |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | utolsó módosítás |

### Kulcsok és indexek

- PK: `id`
- UNIQUE: `username`
- INDEX: `role`

### Fontos constraint

- `role` ellenőrzött értékkészletből jön

### Audit / traceability megjegyzés

A legtöbb fontos rekord kapcsolódik egy felhasználóhoz:

- importáló,
- analysis run indító,
- review végző,
- export indító.

## 6.2 `cases`

### Cél

Ügyek elkülönített munkaterületként való kezelése.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_reference | text | nem | külső vagy belső ügyszám |
| case_name | text | igen | ügy neve |
| description | text | nem | rövid leírás |
| status | text | igen | `open`, `closed`, `archived` |
| created_by_user_id | uuid | igen | FK `users.id` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | utolsó módosítás |
| closed_at | timestamptz | nem | lezárás időpontja |
| archived_at | timestamptz | nem | archiválás időpontja |

### Kulcsok és indexek

- PK: `id`
- FK: `created_by_user_id -> users.id`
- UNIQUE: `(case_reference)` opcionális, ha a szervezet megköveteli
- INDEX: `status`
- INDEX: `created_at`

### Audit / traceability megjegyzés

Minden forrás- és AI-objektum case-bound legyen. Ez egyszerűsíti:

- hozzáféréskezelést,
- auditot,
- exportot,
- későbbi case-level archiválást.

## 6.3 `case_users`

### Cél

Felhasználók és ügyek közötti jogosultsági kapcsolat.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| user_id | uuid | igen | FK `users.id` |
| case_role | text | igen | pl. `owner`, `analyst`, `reviewer`, `viewer` |
| granted_by_user_id | uuid | igen | FK `users.id` |
| granted_at | timestamptz | igen | jogosultságadás |

### Kulcsok és indexek

- PK: `id`
- UNIQUE: `(case_id, user_id)`
- INDEX: `user_id`

### Audit / traceability megjegyzés

Segíti annak rekonstruálását, hogy egy adott időszakban ki férhetett hozzá egy ügyhöz.

## 6.4 `documents`

### Cél

Az eredeti importált dokumentumok immutable metaadatai.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| original_filename | text | igen | eredeti fájlnév |
| stored_path | text | igen | lokális tárolási útvonal |
| mime_type | text | igen | MIME típus |
| file_extension | text | nem | pl. `pdf`, `docx`, `txt` |
| file_size_bytes | bigint | igen | fájlméret |
| sha256_hash | char(64) | igen | eredeti fájl hash |
| import_batch_id | uuid | nem | opcionális csoportos import azonosító |
| document_type | text | nem | pl. vallomás, jegyzőkönyv, szakvélemény |
| language_code | text | nem | pl. `hu` |
| is_encrypted | boolean | igen | titkosított dokumentum jelölése |
| imported_by_user_id | uuid | igen | FK `users.id` |
| imported_at | timestamptz | igen | import időpontja |
| processing_status | text | igen | `pending`, `processing`, `processed`, `failed`, `review_required` |
| page_count | integer | nem | oldalszám, ha ismert |
| parser_name | text | nem | elsődleges parser neve |
| parser_version | text | nem | elsődleges parser verzió |
| notes | text | nem | technikai vagy emberi megjegyzés |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `imported_by_user_id -> users.id`
- UNIQUE: `(case_id, sha256_hash)`
- INDEX: `(case_id, imported_at)`
- INDEX: `processing_status`
- INDEX: `document_type`

### Fontos constraint

- `sha256_hash` fix 64 hex karakter
- `file_size_bytes > 0`
- `page_count IS NULL OR page_count >= 0`

### Audit / traceability megjegyzés

Ez a tábla az eredeti fájl "evidence root" metaadata. Az üzleti szabály szerint ezek a mezők import után nem módosíthatók, kivéve korlátozott admin metaadatok, mint a `notes`.

## 6.5 `document_pages`

### Cél

Oldalszintű szöveg és OCR/parsing eredmények tárolása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| document_id | uuid | igen | FK `documents.id` |
| page_number | integer | igen | 1-alapú oldalszám |
| extracted_text | text | igen | oldal teljes kinyert szövege |
| text_source | text | igen | `native`, `ocr`, `mixed`, `manual` |
| ocr_used | boolean | igen | OCR történt-e |
| ocr_confidence | numeric(5,4) | nem | 0.0000-1.0000 |
| parser_name | text | nem | feldolgozó neve |
| parser_version | text | nem | feldolgozó verzió |
| extraction_run_id | uuid | nem | FK `analysis_runs.id` |
| version_no | integer | igen | oldal-szöveg verziószáma az adott dokumentumoldalon belül |
| is_current | boolean | igen | ez-e az aktuális oldal-szöveg verzió |
| superseded_by_id | uuid | nem | FK `document_pages.id`, ha újabb verzió váltotta |
| text_char_count | integer | igen | karakterdarabszám |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `document_id -> documents.id`
- FK: `extraction_run_id -> analysis_runs.id`
- FK: `superseded_by_id -> document_pages.id`
- UNIQUE: `(document_id, page_number, version_no)`
- INDEX: `(case_id, document_id)`
- INDEX: `page_number`
- INDEX: `(document_id, page_number, is_current)`
- GIN/FTS index: `to_tsvector('simple', extracted_text)`

### Fontos constraint

- `page_number >= 1`
- `version_no >= 1`
- `text_char_count >= 0`
- `ocr_confidence BETWEEN 0 AND 1` ha nem null
- üzleti szabály: dokumentumoldalanként pontosan egy `is_current = true` rekord legyen

### Audit / traceability megjegyzés

Ez a forráshűség egyik legfontosabb táblája. A source reference rekordoknak tudniuk kell oldalra mutatni még akkor is, ha a chunk több oldalon átível.

Újrafeldolgozáskor nem csendes felülírás történik, hanem új verzió keletkezik. Ez fontos jobb OCR-beállítás, parser verzióváltás vagy manuálisan javított oldalszöveg esetén.

## 6.6 `document_chunks`

### Cél

Chunkolt, kereshető, embeddingelhető és hivatkozható szövegegységek tárolása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| document_id | uuid | igen | FK `documents.id` |
| page_start | integer | igen | első érintett oldal |
| page_end | integer | igen | utolsó érintett oldal |
| chunk_index | integer | igen | dokumentumon belüli sorrend |
| chunk_text | text | igen | chunk szövege |
| char_start | integer | nem | dokumentumszintű vagy oldalszintű kezdet |
| char_end | integer | nem | dokumentumszintű vagy oldalszintű vég |
| token_count | integer | nem | becsült vagy számolt tokenmennyiség |
| chunking_strategy | text | igen | pl. `paragraph_window_v1` |
| chunker_version | text | igen | chunker verzió |
| embedding_provider | text | nem | embedding komponens neve |
| embedding_model | text | nem | embedding modell |
| embedding_vector_id | text | nem | Qdrant / pgvector oldali azonosító |
| chunk_run_id | uuid | nem | FK `analysis_runs.id` |
| version_no | integer | igen | chunk verziószáma az adott dokumentum/chunk indexen belül |
| is_current | boolean | igen | ez-e az aktuális chunk verzió |
| superseded_by_id | uuid | nem | FK `document_chunks.id`, ha újabb verzió váltotta |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `document_id -> documents.id`
- FK: `chunk_run_id -> analysis_runs.id`
- FK: `superseded_by_id -> document_chunks.id`
- UNIQUE: `(document_id, chunk_index, chunker_version, version_no)`
- INDEX: `(case_id, document_id)`
- INDEX: `(document_id, page_start, page_end)`
- INDEX: `(document_id, chunk_index, is_current)`
- INDEX: `embedding_vector_id`
- GIN/FTS index: `to_tsvector('simple', chunk_text)`

### Fontos constraint

- `page_start >= 1`
- `page_end >= page_start`
- `chunk_index >= 0`
- `version_no >= 1`
- `token_count IS NULL OR token_count >= 0`
- `char_end IS NULL OR char_start IS NULL OR char_end >= char_start`
- üzleti szabály: dokumentum/chunk indexenként pontosan egy `is_current = true` rekord legyen

### Audit / traceability megjegyzés

Az AI-elemzések elsődleges kontextus-egysége. Minden analysis run inputnak konkrét chunk rekordokra kell mutatnia.

Új chunking stratégia vagy embedding modell bevezetésekor új chunk verziók keletkeznek. A régi analysis runok továbbra is a korábban használt konkrét chunk rekordokra mutatnak.

## 6.7 `analysis_runs`

### Cél

Bármely feldolgozási vagy AI-elemzési futás teljes auditálható naplózása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| run_type | text | igen | pl. `parse_document`, `ocr_document`, `chunk_document`, `extract_entities`, `extract_events`, `extract_claims`, `detect_contradictions`, `detect_missing_items`, `summarize_case`, `answer_with_citations`, `export_bundle` |
| status | text | igen | `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| started_by_user_id | uuid | igen | FK `users.id` |
| started_at | timestamptz | igen | start |
| finished_at | timestamptz | nem | finish |
| provider_type | text | nem | pl. `docling`, `tesseract`, `huspacy`, `ollama`, `llama_cpp`, `system` |
| model_name | text | nem | modell neve |
| model_version | text | nem | modell vagy komponens verzió |
| prompt_template_name | text | nem | prompt sablon neve |
| prompt_template_version | text | nem | prompt verzió |
| input_parameters | jsonb | nem | futási paraméterek |
| raw_prompt_text | text | nem | audit célú prompt mentés, ha releváns |
| output_schema_name | text | nem | elvárt JSON séma neve |
| output_schema_version | text | nem | séma verzió |
| retrieval_strategy | text | nem | pl. `hybrid_v1` |
| validation_status | text | nem | `not_applicable`, `passed`, `failed`, `warning` |
| error_message | text | nem | hibaüzenet |
| created_at | timestamptz | igen | rekord létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `started_by_user_id -> users.id`
- INDEX: `(case_id, run_type, started_at DESC)`
- INDEX: `status`
- INDEX: `(provider_type, model_name, model_version)`

### Fontos constraint

- `finished_at IS NULL OR finished_at >= started_at`

### Audit / traceability megjegyzés

Ez a séma központi provenance táblája. Minden AI-generált rekordnál kötelező a `created_by_analysis_run_id` referencia.

## 6.8 `analysis_run_inputs`

### Cél

Az analysis run tényleges bemeneteinek explicit tárolása.

### Miért külön tábla?

Mert nem elég csak a run paramétereit menteni. Utólag bizonyíthatónak kell lennie, hogy pontosan mely dokumentumokat, oldalakat vagy chunkokat használta a futás.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| input_type | text | igen | `document`, `page`, `chunk`, `entity`, `claim`, `event`, `query_text`, `filter` |
| document_id | uuid | nem | FK `documents.id` |
| page_id | uuid | nem | FK `document_pages.id` |
| chunk_id | uuid | nem | FK `document_chunks.id` |
| related_object_type | text | nem | opcionális más objektumokhoz |
| related_object_id | uuid | nem | opcionális más objektumokhoz |
| sequence_no | integer | igen | bemeneti sorrend |
| payload_json | jsonb | nem | query vagy paraméter snapshot |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `analysis_run_id -> analysis_runs.id`
- INDEX: `analysis_run_id`
- INDEX: `document_id`
- INDEX: `page_id`
- INDEX: `chunk_id`
- INDEX: `(related_object_type, related_object_id)`

### Fontos constraint

- `sequence_no >= 0`
- legalább egy input-hordozó mező legyen kitöltve:
  - `document_id`, vagy
  - `page_id`, vagy
  - `chunk_id`, vagy
  - `payload_json`, vagy
  - `related_object_type + related_object_id`

### Audit / traceability megjegyzés

Ez teszi reprodukálhatóvá a runokat. Különösen fontos retrieval-alapú LLM-futásoknál.

## 6.9 `analysis_run_outputs`

### Cél

Az analysis run által létrehozott objektumok explicit regisztrációja.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| output_type | text | igen | `entity`, `mention`, `event`, `claim`, `contradiction_candidate`, `missing_item_candidate`, `export`, `summary_item` |
| output_object_id | uuid | igen | létrehozott rekord id-ja |
| output_position | integer | nem | sorrend a kimenetben |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `analysis_run_id -> analysis_runs.id`
- INDEX: `(output_type, output_object_id)`
- INDEX: `analysis_run_id`

### Audit / traceability megjegyzés

Ezzel könnyű visszakérdezni, hogy egy run pontosan milyen objektumokat eredményezett.

## 6.10 `source_references`

### Cél

Konkrét, újrafelhasználható forráshivatkozási rekordok tárolása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| document_id | uuid | igen | FK `documents.id` |
| page_id | uuid | nem | FK `document_pages.id` |
| chunk_id | uuid | nem | FK `document_chunks.id` |
| page_number | integer | nem | denormalizált gyors eléréshez |
| quote_text | text | igen | releváns idézet / kivonat |
| quote_char_start | integer | nem | quote kezdete a chunkban vagy oldalon |
| quote_char_end | integer | nem | quote vége a chunkban vagy oldalon |
| citation_label | text | nem | UI-barát rövid címke |
| confidence | numeric(5,4) | nem | 0-1 |
| source_kind | text | igen | `page_quote`, `chunk_quote`, `document_metadata`, `manual_note` |
| extraction_run_id | uuid | nem | FK `analysis_runs.id` |
| created_by_user_id | uuid | nem | manuális létrehozó |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `document_id -> documents.id`
- FK: `page_id -> document_pages.id`
- FK: `chunk_id -> document_chunks.id`
- FK: `extraction_run_id -> analysis_runs.id`
- FK: `created_by_user_id -> users.id`
- INDEX: `(case_id, document_id, page_number)`
- INDEX: `chunk_id`
- INDEX: `extraction_run_id`

### Fontos constraint

- `page_number IS NULL OR page_number >= 1`
- `confidence IS NULL OR confidence BETWEEN 0 AND 1`
- `quote_char_end IS NULL OR quote_char_start IS NULL OR quote_char_end >= quote_char_start`
- üzleti szabály: `page_id` vagy `chunk_id` közül legalább az egyik kötelező, kivéve `source_kind = document_metadata` esetén

### Audit / traceability megjegyzés

Minden source-cited AI output ezekre a rekordokra hivatkozzon közvetlenül vagy kapcsolótáblán keresztül.

## 6.11 `entities`

### Cél

Normalizált entitások tárolása ügyön belül.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| entity_type | text | igen | `person`, `organization`, `location`, `phone`, `email`, `license_plate`, `case_reference`, `money_amount`, `document_reference`, `other` |
| canonical_name | text | igen | kanonikus megjelenítés |
| normalized_value | text | nem | normalizált forma |
| description | text | nem | rövid leírás |
| confidence | numeric(5,4) | nem | AI confidence |
| created_by_analysis_run_id | uuid | nem | FK `analysis_runs.id` |
| created_by_user_id | uuid | nem | manuális létrehozó |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- FK: `created_by_user_id -> users.id`
- INDEX: `(case_id, entity_type)`
- INDEX: `review_status`
- INDEX: `canonical_name`
- INDEX: `normalized_value`

### Fontos constraint

- AI-eredetű entitásnál `created_by_analysis_run_id` kötelező
- manuális entitásnál `created_by_user_id` kötelező

### Audit / traceability megjegyzés

Entitás önmagában nem elég: a bizonyító erejű visszakereshetőség az `entity_mentions` táblából jön.

## 6.12 `entity_mentions`

### Cél

Entitások konkrét előfordulásainak tárolása oldalon/chunkban.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| entity_id | uuid | igen | FK `entities.id` |
| document_id | uuid | igen | FK `documents.id` |
| page_id | uuid | nem | FK `document_pages.id` |
| chunk_id | uuid | nem | FK `document_chunks.id` |
| page_number | integer | nem | denormalizált |
| surface_text | text | igen | konkrét előforduló alak |
| char_start | integer | nem | pozíció |
| char_end | integer | nem | pozíció |
| source_reference_id | uuid | nem | FK `source_references.id` |
| confidence | numeric(5,4) | nem | 0-1 |
| created_by_analysis_run_id | uuid | nem | FK `analysis_runs.id` |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `entity_id -> entities.id`
- FK: `document_id -> documents.id`
- FK: `page_id -> document_pages.id`
- FK: `chunk_id -> document_chunks.id`
- FK: `source_reference_id -> source_references.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `entity_id`
- INDEX: `(document_id, page_number)`
- INDEX: `chunk_id`

### Audit / traceability megjegyzés

Az entitás-állítások forráshű alapja a mention, nem az összevont entity rekord.

## 6.13 `events`

### Cél

Forráshivatkozott eseményjelöltek és idővonal-elemek tárolása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| event_type | text | igen | pl. `call`, `meeting`, `statement`, `transfer`, `search`, `seizure`, `other` |
| event_title | text | igen | rövid cím |
| event_description | text | nem | részletes leírás |
| event_time_raw | text | nem | eredeti időmegfogalmazás |
| event_time_start | timestamptz | nem | normalizált kezdő idő |
| event_time_end | timestamptz | nem | normalizált záró idő |
| time_precision | text | nem | `exact`, `minute`, `hour`, `day`, `month`, `unknown` |
| location_entity_id | uuid | nem | FK `entities.id` |
| confidence | numeric(5,4) | nem | 0-1 |
| created_by_analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| source_validation_status | text | igen | `pending_source_validation`, `source_valid`, `source_invalid` |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `location_entity_id -> entities.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `(case_id, event_time_start)`
- INDEX: `event_type`
- INDEX: `source_validation_status`
- INDEX: `review_status`

### Audit / traceability megjegyzés

Az esemény forrásait nem egyetlen oszlop, hanem kapcsolt source reference rekordok hordozzák. A `source_validation_status` jelzi, hogy a kapcsolt források létezését, ügyhöz tartozását és idézetszintű ellenőrzését a validációs pipeline már elvégezte-e.

## 6.14 `event_sources`

### Cél

Események és source reference rekordok N:N kapcsolata.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| event_id | uuid | igen | FK `events.id` |
| source_reference_id | uuid | igen | FK `source_references.id` |
| relevance_rank | integer | nem | elsődleges / másodlagos sorrend |
| support_type | text | igen | `direct`, `indirect`, `contextual` |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- UNIQUE: `(event_id, source_reference_id)`
- INDEX: `event_id`
- INDEX: `source_reference_id`

### Audit / traceability megjegyzés

Ez biztosítja a többforrásos timeline-elemek korrekt modellezését.

## 6.15 `claims`

### Cél

Strukturált állítások tárolása forráshivatkozással és review státusszal.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| claim_type | text | igen | `witness_statement`, `document_fact`, `expert_opinion`, `administrative_fact`, `inference_candidate`, `unknown` |
| claim_text | text | igen | állítás szövege |
| speaker_entity_id | uuid | nem | FK `entities.id` |
| subject_entity_id | uuid | nem | FK `entities.id` |
| related_event_id | uuid | nem | FK `events.id` |
| claim_time_raw | text | nem | eredeti időhivatkozás |
| claim_time_normalized | timestamptz | nem | normalizált idő |
| confidence | numeric(5,4) | nem | 0-1 |
| created_by_analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| source_validation_status | text | igen | `pending_source_validation`, `source_valid`, `source_invalid` |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `speaker_entity_id -> entities.id`
- FK: `subject_entity_id -> entities.id`
- FK: `related_event_id -> events.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `(case_id, claim_type)`
- INDEX: `related_event_id`
- INDEX: `source_validation_status`
- INDEX: `review_status`
- GIN/FTS index: `to_tsvector('simple', claim_text)`

### Audit / traceability megjegyzés

Minden claimhez legalább egy source reference kapcsolódjon üzleti szabályként. A `source_validation_status` addig maradjon `pending_source_validation`, amíg a quote és a kapcsolt source reference ellenőrzése le nem futott.

## 6.16 `claim_sources`

### Cél

Állítások és forrásrekordok N:N kapcsolata.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| claim_id | uuid | igen | FK `claims.id` |
| source_reference_id | uuid | igen | FK `source_references.id` |
| relevance_rank | integer | nem | elsődleges / további forrás |
| support_type | text | igen | `direct`, `indirect`, `contextual` |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- UNIQUE: `(claim_id, source_reference_id)`
- INDEX: `claim_id`
- INDEX: `source_reference_id`

### Audit / traceability megjegyzés

Ez implementálja a "No source -> no claim" szabály adatmodell-oldali magját.

## 6.17 `contradiction_candidates`

### Cél

Potenciális ellentmondásjelöltek tárolása, nem végleges következtetésként.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| contradiction_type | text | igen | pl. `time_conflict`, `location_conflict`, `identity_conflict`, `document_mismatch`, `other` |
| title | text | igen | rövid cím |
| description | text | igen | ember által olvasható leírás |
| claim_id_a | uuid | nem | FK `claims.id` |
| claim_id_b | uuid | nem | FK `claims.id` |
| event_id_a | uuid | nem | FK `events.id` |
| event_id_b | uuid | nem | FK `events.id` |
| confidence | numeric(5,4) | nem | 0-1 |
| severity_hint | text | nem | `low`, `medium`, `high` |
| created_by_analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| source_validation_status | text | igen | `pending_source_validation`, `source_valid`, `source_invalid` |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `claim_id_a -> claims.id`
- FK: `claim_id_b -> claims.id`
- FK: `event_id_a -> events.id`
- FK: `event_id_b -> events.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `(case_id, contradiction_type)`
- INDEX: `source_validation_status`
- INDEX: `review_status`

### Fontos constraint

- legalább egy összevetési pár legyen megadva:
  - `claim_id_a + claim_id_b`, vagy
  - `event_id_a + event_id_b`

### Audit / traceability megjegyzés

A jelölt forrásait külön kapcsolótábla tartja, mert gyakran több claim és több idézet együtt adja a konfliktust. A `source_validation_status` nem azt jelenti, hogy az ellentmondás igazolt, csak azt, hogy a hivatkozott források technikailag ellenőrizhetők és visszakereshetők.

## 6.18 `contradiction_candidate_sources`

### Cél

Ellentmondásjelöltek és forráshivatkozások kapcsolata.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| contradiction_candidate_id | uuid | igen | FK `contradiction_candidates.id` |
| source_reference_id | uuid | igen | FK `source_references.id` |
| side_label | text | nem | pl. `a`, `b`, `context` |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- UNIQUE: `(contradiction_candidate_id, source_reference_id, side_label)`
- INDEX: `contradiction_candidate_id`
- INDEX: `source_reference_id`

### Audit / traceability megjegyzés

Lehetővé teszi a UI-ban a két oldal egymás mellé helyezését konkrét idézetekkel.

## 6.19 `missing_item_candidates`

### Cél

Azon hivatkozott, de hiányzó elemek jelöltjeinek tárolása, amelyek emberi ellenőrzést igényelnek.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| missing_item_type | text | igen | pl. `attachment`, `video`, `expert_report`, `protocol`, `image`, `document_reference`, `other` |
| referenced_item_text | text | igen | mire történt hivatkozás |
| description | text | igen | miért tűnik hiányzónak |
| expected_document_type | text | nem | várt dokumentumtípus |
| confidence | numeric(5,4) | nem | 0-1 |
| created_by_analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| source_validation_status | text | igen | `pending_source_validation`, `source_valid`, `source_invalid` |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `(case_id, missing_item_type)`
- INDEX: `source_validation_status`
- INDEX: `review_status`

### Audit / traceability megjegyzés

Ezek is csak forrásokkal együtt értelmezhetők, különösen azért, hogy látszódjon, mely szövegrész utal a hiányzó elemre. A `source_validation_status` csak a forráshivatkozás ellenőrzöttségét jelzi, nem a hiány tényleges bizonyítottságát.

## 6.20 `missing_item_candidate_sources`

### Cél

Hiányjelöltek és forrásrekordok kapcsolata.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| missing_item_candidate_id | uuid | igen | FK `missing_item_candidates.id` |
| source_reference_id | uuid | igen | FK `source_references.id` |
| relevance_rank | integer | nem | sorrend |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- UNIQUE: `(missing_item_candidate_id, source_reference_id)`
- INDEX: `missing_item_candidate_id`
- INDEX: `source_reference_id`

## 6.21 `human_reviews`

### Cél

Minden emberi elfogadás, elutasítás, javítás, megjegyzés és státuszváltás naplózása.

### Megjegyzés

Ez szándékosan append-only jellegű eseménytábla, nem csak "aktuális review állapot" tároló.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| object_type | text | igen | `entity`, `event`, `claim`, `contradiction_candidate`, `missing_item_candidate`, `source_reference`, `export` |
| object_id | uuid | igen | review-zott objektum |
| action_type | text | igen | `mark_needs_review`, `verify`, `reject`, `correct`, `comment`, `attach_source`, `detach_source` |
| previous_review_status | text | nem | korábbi státusz |
| new_review_status | text | nem | új státusz |
| review_comment | text | nem | emberi megjegyzés |
| correction_patch_json | jsonb | nem | strukturált módosítás |
| performed_by_user_id | uuid | igen | FK `users.id` |
| performed_at | timestamptz | igen | időpont |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `performed_by_user_id -> users.id`
- INDEX: `(object_type, object_id, performed_at DESC)`
- INDEX: `performed_by_user_id`
- INDEX: `action_type`

### Audit / traceability megjegyzés

Ez az egyik kulcstábla annak megértésére, hogy egy AI-javaslatból hogyan lett ember által elfogadott vagy javított output.

## 6.22 `exports`

### Cél

Exportfutások és exportált csomagok nyilvántartása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| export_type | text | igen | `markdown`, `html`, `json`, később `pdf`, `docx` |
| export_scope | text | igen | `case_summary`, `claims`, `timeline`, `contradictions`, `missing_items`, `custom_bundle` |
| file_path | text | igen | lokális export útvonal |
| sha256_hash | char(64) | nem | exportfájl hash |
| generated_by_analysis_run_id | uuid | nem | FK `analysis_runs.id` |
| exported_by_user_id | uuid | igen | FK `users.id` |
| review_filter | text | nem | pl. `verified_only` |
| export_parameters | jsonb | nem | formátum és szűrés |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `generated_by_analysis_run_id -> analysis_runs.id`
- FK: `exported_by_user_id -> users.id`
- INDEX: `(case_id, created_at DESC)`
- INDEX: `export_type`
- INDEX: `export_scope`

### Audit / traceability megjegyzés

Exportnál vissza kell tudni nézni:

- ki exportált,
- mikor,
- milyen szűrővel,
- mely objektumokat.

## 6.23 `export_items`

### Cél

Megmondja, hogy egy export pontosan mely objektumokat tartalmazta.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| export_id | uuid | igen | FK `exports.id` |
| object_type | text | igen | `entity`, `event`, `claim`, `contradiction_candidate`, `missing_item_candidate`, `summary_item` |
| object_id | uuid | igen | exportált objektum |
| source_reference_id | uuid | nem | opcionális elsődleges forrás |
| display_order | integer | nem | sorrend |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `export_id -> exports.id`
- FK: `source_reference_id -> source_references.id`
- INDEX: `export_id`
- INDEX: `(object_type, object_id)`

### Audit / traceability megjegyzés

Ez teszi export szinten is rekonstruálhatóvá, hogy mi került ki a rendszerből.

## 6.24 `audit_events`

### Cél

Lekérdezhető rendszer-audit események tárolása.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | nem | FK `cases.id` |
| user_id | uuid | nem | FK `users.id` |
| analysis_run_id | uuid | nem | FK `analysis_runs.id` |
| event_type | text | igen | pl. `case_created`, `document_imported`, `hash_computed`, `ocr_completed`, `chunking_completed`, `retrieval_executed`, `llm_called`, `review_recorded`, `export_created` |
| event_timestamp | timestamptz | igen | esemény ideje |
| related_object_type | text | nem | objektumtípus |
| related_object_id | uuid | nem | objektum azonosító |
| related_document_id | uuid | nem | FK `documents.id` |
| related_page_id | uuid | nem | FK `document_pages.id` |
| related_chunk_id | uuid | nem | FK `document_chunks.id` |
| success | boolean | igen | sikeresség |
| input_summary | jsonb | nem | tömör bemeneti összefoglaló |
| output_summary | jsonb | nem | tömör kimeneti összefoglaló |
| error_message | text | nem | hibaüzenet |
| created_at | timestamptz | igen | rekord létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `user_id -> users.id`
- FK: `analysis_run_id -> analysis_runs.id`
- FK: `related_document_id -> documents.id`
- FK: `related_page_id -> document_pages.id`
- FK: `related_chunk_id -> document_chunks.id`
- INDEX: `(case_id, event_timestamp DESC)`
- INDEX: `event_type`
- INDEX: `analysis_run_id`
- INDEX: `(related_object_type, related_object_id)`

### Audit / traceability megjegyzés

Az `analysis_runs` a futások strukturált naplója, az `audit_events` pedig az összes jelentős üzleti és technikai esemény univerzális eseménytára.

## 7. Ügyösszefoglaló elemek

## 7.1 `summary_items`

### Cél

Review-zható, forráshivatkozott ügyösszefoglaló-elemek tárolása.

### Döntés

MVP-1-ben az ügyösszefoglaló ne csak exportált szöveg legyen, hanem első osztályú AI-output objektum. Így minden összefoglalóelem külön ellenőrizhető, javítható, forráshoz köthető és exportálható.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| case_id | uuid | igen | FK `cases.id` |
| summary_type | text | igen | `case_overview`, `document_summary`, `timeline_summary`, `entity_summary`, `caution_note`, `other` |
| title | text | igen | rövid cím |
| body_text | text | igen | összefoglalóelem szövege |
| confidence | numeric(5,4) | nem | 0-1 |
| created_by_analysis_run_id | uuid | igen | FK `analysis_runs.id` |
| source_validation_status | text | igen | `pending_source_validation`, `source_valid`, `source_invalid` |
| review_status | text | igen | `new`, `needs_review`, `verified`, `rejected`, `corrected` |
| created_at | timestamptz | igen | létrehozás |
| updated_at | timestamptz | igen | módosítás |

### Kulcsok és indexek

- PK: `id`
- FK: `case_id -> cases.id`
- FK: `created_by_analysis_run_id -> analysis_runs.id`
- INDEX: `(case_id, summary_type)`
- INDEX: `source_validation_status`
- INDEX: `review_status`

### Audit / traceability megjegyzés

Az ügyösszefoglaló is AI-output. Ugyanazok a source validation és human review szabályok vonatkozzanak rá, mint a claim, event, contradiction és missing item objektumokra.

## 7.2 `summary_item_sources`

### Cél

Ügyösszefoglaló-elemek és source reference rekordok N:N kapcsolata.

### Oszlopok

| Oszlop | Típus | Kötelező | Leírás |
|---|---|---:|---|
| id | uuid | igen | PK |
| summary_item_id | uuid | igen | FK `summary_items.id` |
| source_reference_id | uuid | igen | FK `source_references.id` |
| relevance_rank | integer | nem | elsődleges / további forrás |
| support_type | text | igen | `direct`, `indirect`, `contextual` |
| created_at | timestamptz | igen | létrehozás |

### Kulcsok és indexek

- PK: `id`
- FK: `summary_item_id -> summary_items.id`
- FK: `source_reference_id -> source_references.id`
- UNIQUE: `(summary_item_id, source_reference_id)`
- INDEX: `summary_item_id`
- INDEX: `source_reference_id`

### Audit / traceability megjegyzés

Ez biztosítja, hogy az összefoglaló minden külön állítása visszavezethető legyen konkrét dokumentumoldalra vagy chunkra.

## 8. Fő üzleti szabályok

## 8.1 Kötelező provenance szabályok

1. Minden AI által létrehozott `entity`, `event`, `claim`, `contradiction_candidate`, `missing_item_candidate`, `summary_item` rekordhoz tartozzon `created_by_analysis_run_id`.
2. Minden `claim` rekordhoz tartozzon legalább egy `claim_sources` kapcsolat.
3. Minden `event` rekordhoz tartozzon legalább egy `event_sources` kapcsolat.
4. Minden `contradiction_candidate` rekordhoz tartozzon legalább két forráshivatkozás vagy két forrásozott claim/event kapcsolat.
5. Minden `missing_item_candidate` rekordhoz tartozzon legalább egy forráshivatkozás.
6. Minden `summary_item` rekordhoz tartozzon legalább egy `summary_item_sources` kapcsolat.
7. Az AI-output objektumok `source_validation_status` mezője export előtt legyen `source_valid`.

## 8.2 Immutable source szabályok

1. A `documents` tábla eredeti fájlra vonatkozó mezői import után nem módosíthatók üzleti szabályként.
2. A `sha256_hash` az eredeti fájl identitásának része.
3. A `document_pages` és `document_chunks` rekordok újrafeldolgozáskor új verzióként keletkezzenek, ne csendes felülírással.

## 8.3 Human review szabályok

1. A review státusz ne csak az objektumtáblákban legyen jelen, hanem minden review esemény kerüljön be a `human_reviews` táblába.
2. Export alapértelmezetten csak `verified` és `source_valid` objektumokból történjen.
3. Ettől eltérő admin override csak explicit paraméterrel és audit eseménnyel történhet.

## 8.4 Query/audit reprodukció

LLM-futásoknál minimálisan mentendő:

- input chunk lista,
- prompt template név és verzió,
- modell neve és verziója,
- output séma és verzió,
- validáció státusza.

## 9. Indexelési javaslatok

## 9.1 Kötelező indexek

- minden FK mezőn B-tree index,
- `documents(case_id, imported_at)`,
- `document_pages(document_id, page_number)`,
- `document_chunks(document_id, chunk_index)`,
- `analysis_runs(case_id, run_type, started_at)`,
- `audit_events(case_id, event_timestamp)`.

## 9.2 Full-text keresés

MVP-ben elegendő lehet PostgreSQL FTS az alábbiakon:

- `document_pages.extracted_text`
- `document_chunks.chunk_text`
- `claims.claim_text`

Magyar nyelv esetén később érdemes mérni:

- `simple` dictionary,
- egyedi magyar konfiguráció,
- vagy külső kereső bevezetése szükséges-e.

## 9.3 JSONB indexek

Ha a `analysis_runs.input_parameters`, `exports.export_parameters` vagy `audit_events.input_summary` mezők gyakran szűrtek, érdemes célzott GIN indexeket adni.

## 10. Particionálási és méretezési megjegyzések

MVP-ben nem kötelező particionálás.

Ha az adatmennyiség gyorsan nő, elsőként ezeknél érdemes megfontolni:

- `audit_events` időalapú particionálása,
- `analysis_runs` case vagy idő szerinti particionálása,
- nagyon nagy ügyeknél `document_pages` és `document_chunks` case szerinti szegmentálása.

## 11. Mi maradjon az adatbázison kívül

Az alábbiakat ne a PostgreSQL tárolja elsődleges bináris formában az MVP-ben:

- eredeti dokumentum bináris tartalma,
- OCR-képek,
- exportált fájlok,
- append-only JSONL auditfájlok,
- Qdrant vektorindex.

Az adatbázis ezekhez stabil metaadat- és hash-hivatkozást tartson fenn.

## 12. Javasolt minimális implementációs sorrend

1. `users`
2. `cases`
3. `case_users`
4. `documents`
5. `document_pages`
6. `document_chunks`
7. `analysis_runs`
8. `analysis_run_inputs`
9. `analysis_run_outputs`
10. `source_references`
11. `entities`
12. `entity_mentions`
13. `events`
14. `event_sources`
15. `claims`
16. `claim_sources`
17. `contradiction_candidates`
18. `contradiction_candidate_sources`
19. `missing_item_candidates`
20. `missing_item_candidate_sources`
21. `summary_items`
22. `summary_item_sources`
23. `human_reviews`
24. `exports`
25. `export_items`
26. `audit_events`

## 13. Rövid összegzés

Ez a séma tudatosan három dolog köré épül:

1. immutable source layer,
2. explicit provenance layer,
3. human-reviewed analysis layer.

Az MVP-1 szempontjából a legfontosabb adatmodellezési döntés az, hogy:

- az eredeti dokumentum,
- az oldalszintű szöveg,
- a chunk,
- a source reference,
- az analysis run,
- a human review

mind külön első osztályú entitás.

Ettől lesz a rendszer:

- auditálható,
- reprodukálható,
- forráshű,
- később bővíthető jogszabályi RAG, evidence matrix és fejlettebb review workflow irányába.
