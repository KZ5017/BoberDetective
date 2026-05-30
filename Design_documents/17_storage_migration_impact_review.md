# 17. Storage Migration Impact Review

## 0. Aktualisitas

Letrehozva: 2026-05-29.

Implementacios allapot:

```text
TextStore / SourceTextResolver DB-backed elso szelet: kesz.
Text layer / chunk manifest DB szerzodes: kesz.
JSONL oldal/chunk text-store helper: kesz.
TXT import fizikai text-store iras: kesz.
PDF native parse, OCR es explicit chunk creation fizikai text-store iras: kesz, API-kompatibilitas megtartasaval.
Runtime olvasasi atvezetes: analysis preview, review report source excerpt, research finding excerpt, search_findings SOURCE blokk, search_findings quote validacio, source-reference quote/span validacio, source-cited smoke es embedding input text-store first / DB fallback modban kesz.
Szigoru DB-text kivezetes: kesz. Migration `0040_drop_db_text_cols` eltavolitja a `document_pages.extracted_text` es `document_chunks.chunk_text` oszlopokat, valamint a regi kozvetlen FTS indexeket.
```

Elso atvezetett olvasasi pontok:

- source reference quote validacio,
- `search_findings` SOURCE blokk epites,
- `search_findings` quote validacio,
- embedding input osszeallitas,
- analysis run chunk preview,
- review report source excerpt,
- research finding source excerpt,
- source-cited smoke helper.

Szandekosan meg nem atvezetett / kesobbi dontesi pontok:

- PostgreSQL keyword search FTS (`app/services/search.py`),
- chunk letrehozas jelenlegi page text bemenete (`app/services/documents.py`),
- tovabbi source-text runtime olvasas fizikai JSONL text store-ra kotese.

Uj metadata szerzodes:

- `document_text_layers`,
- `document_chunk_manifests`.

Ezek jelenleg elokeszito es import/chunking workflow-kban mar irt tablazatok. Celjuk, hogy az extracted page text es chunk text teljes tartalma adat-root JSONL allomanyokba kerulhessen, mikozben PostgreSQL-ben megmarad a text layer / chunk manifest azonositasa, hash-e, verzioja, aktualis allapota es provenance kapcsolata.

Ez a dokumentum a `Design_documents/16_large_case_document_storage_and_retrieval_plan.md` elso kodszintu hatasterkepe.

Cel:

```text
megmutatni, pontosan hol fugg a jelenlegi rendszer attol,
hogy az oldalak es chunkok teljes szovege PostgreSQL-ben van.
```

Ez meg nem implementacios patch. Ez a biztonsagos atvezetes elotti bontasi terkep.

## 1. Jelenlegi tarolasi modell

### 1.1 Dokumentum metadata

Kod:

- `app/models/document.py`
- `app/services/documents.py`

`documents` jelenleg jo alap metadata es lifecycle szinten:

- `stored_path`
- `sha256_hash`
- `mime_type`
- `file_extension`
- `file_size_bytes`
- `processing_status`
- `lifecycle_status`
- `page_count`
- `parser_name`
- `parser_version`

Ez a resz nagyreszt megtarthato.

### 1.2 Oldalszoveg

Kod:

- `DocumentPageModel.extracted_text`
- `app/services/documents.py::_persist_parsed_pages`
- `app/services/documents.py::_persist_ocr_pages`

Jelenleg minden importalt/native/OCR oldal teljes szovege DB-be kerul:

```text
document_pages.extracted_text
```

Fuggesek:

- dokumentum oldalak API,
- OCR ajanlas / minosegi statisztika reszben `text_char_count` alapjan,
- source reference validacio page quote eseten,
- review/report/source excerpt megjelenites,
- keyword keresés page target eseten,
- chunk letrehozas.

### 1.3 Chunk szoveg

Kod:

- `DocumentChunkModel.chunk_text`
- `app/services/documents.py::_create_chunks_from_pages`

Jelenleg minden chunk teljes szovege DB-be kerul:

```text
document_chunks.chunk_text
```

Fuggesek:

- keyword keresés chunk target eseten,
- semantic/hybrid indexeles embedding inputja,
- Qdrant talalat utan chunk visszaolvasas,
- `search_findings` prompt `SOURCE` blokkjai,
- source reference validacio chunk quote eseten,
- analysis run input/output preview,
- review report source excerpt,
- research finding source excerpt,
- manual source-bound object workflow.

## 2. Jelenlegi import pipeline

### 2.1 TXT import

Kod:

- `app/services/documents.py::import_txt_document`

Most:

```text
upload txt
  -> original file data root
  -> documents row
  -> document_pages.extracted_text
  -> document_chunks.chunk_text azonnal
  -> processing_status=processed
```

Nagyugyes cel:

```text
upload txt
  -> original file data root
  -> documents row
  -> document_text_layer row
  -> pages.jsonl
  -> document_chunk_manifest row
  -> chunks.jsonl
  -> minimal chunk metadata rows
```

TXT import elso atvezetese megtortent, mert egyszeru egyoldalas bemenet. A jelenlegi API-kompatibilitas miatt a DB-s page/chunk sorok meg megmaradnak, de importkor mar letrejon:

- `pages.jsonl`,
- `chunks.jsonl`,
- `document_text_layers`,
- `document_chunk_manifests`.

### 2.2 PDF native import

Kod:

- `app/services/documents.py::import_pdf_document`
- `app/services/documents.py::_persist_parsed_pages`

Most:

```text
upload pdf
  -> original file data root
  -> documents row
  -> parse_document run
  -> document_pages.extracted_text
  -> processing_status=text_review_required
  -> chunk nincs, amig user explicit nem keri
```

Nagyugyes cel:

```text
upload pdf
  -> original file data root
  -> documents row
  -> parse_document run
  -> document_text_layer row
  -> pages.jsonl
  -> minimal page metadata rows vagy page manifest
  -> processing_status=text_review_required
```

PDF-nel az elso atvezetesnel megmaradhat a jelenlegi review-before-chunk workflow.

Fontos minosegi kapu:

- Nativ PDF parse eredmenybol csak akkor perzisztalunk oldalszoveget/text layert, ha a parse minosegi hiba nelkul atment.
- `empty_pages`, `no_native_text` vagy mas parser-minosegi hiba eseten az eredeti PDF megmarad OCR bemenetkent, de nativ `document_pages`, `pages.jsonl`, chunk vagy indexelheto alapanyag nem jon letre.
- A dokumentum ilyenkor `review_required`, a run `quality_issues` es `next_action=run_ocr` jelzest kap.
- OCR teljes bukas eseten nem perzisztalunk oldalszoveget/text layert, az analysis run `next_action=discard_or_replace_document` jelzest ad.
- OCR reszsiker eseten sem jon letre automatikusan text layer; az analysis run `usable_page_numbers`, `failed_page_numbers` es `next_action=review_partial_ocr_before_text_layer` jelzest ad.
- OCR reszsiker eseten a backend nem aktualis jelolt `pages.jsonl` allomanyt ir az adat-root ala. Az explicit `ocr/accept-partial` endpoint a felhasznalo dontese utan a kivalasztott hasznalhato oldalakat aktualis OCR text-review layerre emeli.
- Felhasznalo altal elvetett reszeredmeny eseten a munkarendszerben nem orzunk tovabb feldolgozhatatlan iratot; azt vegleges elvetes/torles iranyba kell vinni.

### 2.3 OCR

Kod:

- `app/services/documents.py::ocr_document`
- `app/services/documents.py::_persist_ocr_pages`

Most:

```text
ocr_document
  -> elozo pages/chunks is_current=false
  -> uj document_pages.extracted_text
  -> nincs automatikus chunk
```

Nagyugyes cel:

```text
ocr_document
  -> uj document_text_layer
  -> uj pages.jsonl
  -> elozo text layer is_current=false
  -> elozo chunk manifest is_current=false
```

Az OCR atvezetes rizikosabb, mert verziozast es supersession logikat is erint.

## 3. Source reference hatas

Kod:

- `app/models/source_reference.py`
- `app/services/source_references.py`

Jelenlegi validacio:

```text
chunk_quote -> chunk.chunk_text
page_quote  -> page.extracted_text
```

Kulcspontok:

- `create_source_reference_for_run`
- `_resolve_quote_span`
- `_validate_existing_source_reference`

Nagyugyes cel:

```text
chunk_quote -> TextStore.read_chunk_text(chunk_id)
page_quote  -> TextStore.read_page_text(page_id vagy text_layer/page_number)
```

DB-ben maradhat:

- `quote_text`
- `quote_char_start`
- `quote_char_end`
- `page_number`
- `page_id`
- `chunk_id`

Hianyzik majd:

- `text_layer_id`
- `quote_hash`
- esetleg `chunk_external_id` vagy stabil manifest chunk id

Elso kompatibilis atvezetes:

```text
SourceTextResolver szolgaltatas
```

Interfesz:

```text
get_page_text(page) -> str
get_chunk_text(chunk) -> str
```

Elso implementacioban ez meg DB-bol olvashat, kesobb text store-bol. Igy a fuggosegek egy helyre terelhetok.

## 4. Kereses es retrieval hatas

### 4.1 Keyword search

Kod:

- `app/services/search.py`

Most PostgreSQL full-text search:

```text
to_tsvector('simple', DocumentChunkModel.chunk_text)
to_tsvector('simple', DocumentPageModel.extracted_text)
```

Ez a legnagyobb tervezesi torlespont.

Ha a teljes szoveg kikerul DB-bol, a jelenlegi DB FTS nem mukodik ugyanigy.

Lehetseges iranyok:

1. Minimal atmenet: chunk/page szoveg egy ideig DB-ben marad, de uj text store mar keszul.
2. Kulon search index tabla `chunk_search_text` roviditett vagy normalizalt text mezovel.
3. Qdrant payload + text store + sajat lexical scan kisebb source-scope-on.
4. PostgreSQL-ben csak `tsvector` vagy lexikai indexelt reprezentacio marad, teljes text nelkul.

Javaslat elso atvezeteshez:

```text
Ne a keyword keresest bontsuk el elsokent.
Elobb vezessuk be a TextStore absztrakciot es minimal manifest modelleket.
```

### 4.2 Semantic / hybrid index

Kod:

- `app/services/vector_index.py`

Most:

```text
_chunks_to_index -> DocumentChunkModel rows
embed_chunks_in_batches -> chunk.chunk_text
Qdrant payload -> chunk_id, document_id, page_start, page_end, is_current
```

Nagyugyes cel:

```text
_chunks_to_index -> minimal chunk metadata rows
TextStore.read_chunk_text(chunk) -> embedding input
Qdrant payload -> chunk metadata + text hash + optional preview
```

Ez viszonylag jol atvezetheto, ha a `DocumentChunkModel` megmarad metadata-only sorkent.

### 4.3 `search_findings`

Kod:

- `app/services/analysis_module_common.py`
- `app/services/analysis_module_findings.py`

Most:

```text
retrieval -> RetrievedChunk(chunk=DocumentChunkModel)
build_source_blocks -> text store first / DB fallback
validate_extracted_findings -> text store first / DB fallback
create source_reference -> chunk_id + quote_text
```

Nagyugyes cel:

```text
RetrievedChunk tartalmazzon chunk metadata + source text provider/resolved text
build_source_blocks text store-bol dolgozzon: kesz
quote validacio text store-bol dolgozzon: kesz
```

Elso biztonsagos refaktor:

```text
RetrievedChunk ne kozvetlenul a chunk.chunk_text-re tamaszkodjon.
Legyen helper: retrieved_chunk_text(retrieved).
```

## 5. Megjelenites es API hatas

### 5.1 Document pages/chunks API

Kod:

- `app/api/v1/documents.py`
- `app/schemas/document.py`

Most a valasz teljes szoveget ad:

```text
DocumentPageRead.extracted_text
DocumentChunkRead.chunk_text
```

Nagyugyes cel:

- lista endpoint metadata + preview,
- reszletes endpoint vagy explicit content endpoint teljes szovegre,
- lapozott/virtualizalt olvasas.

Kompatibilitasi opcio:

```text
Az elso atvezetesben az API tovabbra is visszaadhat teljes textet,
de mar TextStore-bol tolti vissza es nem DB mezobol.
```

### 5.2 Review report / source excerpt

Kod:

- `app/services/review_report.py`
- `app/api/v1/research_findings.py`

Most:

```text
chunk.chunk_text vagy page.extracted_text -> excerpt
```

Nagyugyes cel:

```text
SourceTextResolver -> excerpt
```

Ez jol izolalhato, mert a UI-nak nem kell tudnia, honnan jott a teljes forrasszoveg.

### 5.3 Analysis run detail

Kod:

- `app/services/analysis_runs.py`

Most:

```text
input/output chunk preview -> chunk.chunk_text
```

Nagyugyes cel:

```text
TextStore preview helper
```

## 6. Jelenlegi erosen erintett fajlok

Elsodleges:

- `app/models/document.py`
- `app/models/source_reference.py`
- `app/services/documents.py`
- `app/services/source_references.py`
- `app/services/search.py`
- `app/services/vector_index.py`
- `app/services/analysis_module_common.py`
- `app/services/analysis_module_findings.py`

Masodlagos:

- `app/services/review_report.py`
- `app/api/v1/research_findings.py`
- `app/services/analysis_runs.py`
- `app/api/v1/documents.py`
- `app/schemas/document.py`
- `app/schemas/source_reference.py`
- `app/schemas/search.py`

Teszt erintes:

- `tests/test_documents.py`
- `tests/test_source_references.py`
- `tests/test_vector_index.py`
- `tests/test_analysis_modules.py`
- `tests/test_review_report.py`

## 7. Javasolt elso technikai szelet

### 7.1 Ne torjuk meg egyszerre a DB mezoket

Elsokent ne toroljuk a `extracted_text` es `chunk_text` mezoket.

Helyette:

```text
vezessunk be TextStore absztrakciot,
majd atirjuk az olvasasi pontokat erre,
es csak utana mozgassuk ki fizikailag a teljes szoveget.
```

Indok:

- kisebb riziko,
- tesztek fokozatosan atirhatok,
- a frontend kozben nem omlik ossze,
- source reference validacio vegig mukodokepes marad.

### 7.2 Elso uj service: TextStore / SourceTextResolver

Javasolt fajl:

```text
app/services/text_store.py
```

Elso interfesz:

```text
read_page_text(page: DocumentPageModel) -> str
read_chunk_text(chunk: DocumentChunkModel) -> str
write_pages(...)
write_chunks(...)
```

Elso implementacio:

```text
DBBackedTextStore
```

Aktualis implementacio:

```text
SourceTextResolver:
  read_page_text(page)
  read_chunk_text(chunk)

JSONL helper:
  StoredPageText
  StoredChunkText
  write_pages_jsonl / read_pages_jsonl
  write_chunks_jsonl / read_chunks_jsonl
```

A JSONL helper stabil UTF-8 sorokat ir, rekord szintu `text_hash` erteket es allomany szintu `manifest_hash` erteket ad. Hibas JSONL rekordot `TextStoreError`-ral utasit el.

Masodik implementacio:

```text
JsonlTextStore
```

Ezzel a rendszer fuggesei atallnak egy kozos kapura.

### 7.3 Elso uj metadata modellek

Javasolt migracio:

```text
document_text_layers
document_chunk_manifests
```

Implementalva:

```text
0035_text_layer_manifests
```

Elso korben ezek be vannak vezetve ugy, hogy a regi page/chunk tablakat meg nem bontottuk szet.

### 7.4 Elso olvasasi refaktorok

Atirando helper-hasznalatra:

- `source_references.py` - kesz.
- `analysis_module_common.py::build_source_blocks` - kesz.
- `analysis_module_findings.py::validate_extracted_findings` - kesz.
- `vector_index.py::embed_chunks_in_batches` - kesz.
- `review_report.py` - kesz.
- `research_findings.py` - kesz.
- `analysis_runs.py` - kesz.
- explicit chunk creation: `_create_chunks_from_pages` mar text-store-first page olvasast hasznal - kesz.
- page/chunk detail API responses: `app/api/v1/documents.py` mar text-store-first textet ad vissza - kesz.

Aktualis allapot:

```text
Az aktiv service/API olvasasi utvonalakon nincs kozvetlen page.extracted_text /
chunk.chunk_text hasznalat. A teljes oldal/chunk szoveg a data-root text-store
JSONL allomanyaiban el, PostgreSQL-ben csak metadata, manifest, search-entry,
source-reference, workflow es audit/provenance adat marad.
```

### 7.5 Csak ezutan fizikai text store

Ha a fenti olvasasi pontok mar absztrakcion at mennek, akkor lehet:

- PDF native parse `pages.jsonl`,
- OCR `pages.jsonl`,
- explicit chunk creation `chunks.jsonl`,
- DB `extracted_text` / `chunk_text` fokozatos nullable/deprecated kezelese utan a szigoru kivezetes is kesz: `0040_drop_db_text_cols`.

## 8. Kockazatok

### 8.1 Keyword search ujratervezes

A PostgreSQL FTS kozvetlenul teljes text mezokre epul. Ez nem csak refaktor, hanem retrieval dontes.

Reszletes terv:

- `Design_documents/18_keyword_search_text_store_migration_plan.md`

A kijelolt irany:

- `document_search_entries` metadata + `tsvector` reteg,
- quote/full excerpt text-store-bol,
- jelenlegi API forma es filterek megtartasa.

Eredeti nyitott kerdesek, amelyekre a 18-as terv valaszt ad:

- marad-e DB-ben search-only tsvector,
- kerul-e kulon lightweight lexical index,
- Qdrant + metadata eleg-e,
- kell-e sajat inverted index.

### 8.2 API kompatibilitas

Frontend jelenleg teljes page/chunk textet var.

Atmeneti megoldas:

- ugyanaz az API forma,
- textet TextStore-bol tolti vissza,
- kesobb preview/content endpoint szetvalasztas.

### 8.3 Source reference stabilitas

Ez a rendszer szakmai gerince.

Nem szabad ugy atvezetni, hogy:

- quote offset elcsusszon,
- OCR/native text layer keveredjen,
- regi source reference ne legyen validalhato,
- source reference csak Qdrant talalatra epuljon.

### 8.4 Tesztadat nelkuli allapot

Most az adatbazis tiszta, ez jo az atalakitasra.

De a kovetkezo implementacios szeletnel kell:

- kis TXT fixture,
- kis PDF native fixture,
- OCR fixture,
- source reference validation fixture,
- indexing fixture.

## 9. Dontesi javaslat

Elso implementacios lepes:

```text
TextStore absztrakcio + DB-backed adapter + olvasasi pontok atvezetese.
```

Allapot: kesz.

Indok:

- a legkisebb biztonsagos kodlepes,
- azonnal csokkenti a szetszort `chunk.chunk_text` / `page.extracted_text` fuggosegeket,
- elokesziti a valodi text store-t,
- kozben a jelenlegi rendszer viselkedese nem valtozik.

Utana:

```text
document_text_layers + document_chunk_manifests schema: kesz
JSONL text store writer/reader: kesz
TXT import atvezetes: kesz
PDF import atvezetes
OCR atvezetes
chunk manifest atvezetes
runtime text olvasas atvezetes: kesz az aktiv service utvonalakon
indexing atvezetes: embedding input kesz
keyword search ujratervezes: kesz a `document_search_entries` reteggel
DB text oszlopok eltavolitasa: kesz, `0040_drop_db_text_cols`
```
