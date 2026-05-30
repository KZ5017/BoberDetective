# 16. Large Case Document Storage and Retrieval Plan

## 0. Aktualisitas

Letrehozva: 2026-05-29.

Ez a dokumentum a full-document backend implementacio elotti ujratervezesi kapu.

Implementacios allapot: a fo storage/retrieval kapu elso szigoru kore kesz.
Az oldalak es szovegreszek teljes szovege mar nem PostgreSQL oszlopokban el,
hanem data-root text-store manifestekben (`pages.jsonl`, `chunks.jsonl`).
PostgreSQL metadata/workflow/audit/search-entry/source-reference szerepben marad,
a kulcsszavas kereses `document_search_entries.search_vector` mezon keresztul
mukodik, a Qdrant pedig tovabbra is model-specifikus retrieval index. A
taxonomia workflow ki lett vezetve az aktiv import/kereses utvonalbol, es a
teljes ugy torlese mar case-szintu DB/file/Qdrant takaritast vegez ugy, hogy
az audit esemenyek megmaradnak.

Az eddigi rendszer jol mukodik kis es kozepes tesztugyekkel, de a celzott valos terheles mas:

```text
egy ugyben akar 5000+ irat,
az iratok tobbsege rovidebb, jellemzoen 30-50 oldal,
az elemzesi cel nem egy-egy oriasi irat kezi lapozasa,
hanem nagy irathalmaz gyors, forrashu, ember altal iranyitott kutatasa.
```

Ezert a `Design_documents/15_full_document_processing_plan.md` backend implementacioja elott meg kell hatarozni, hogyan tarolunk, indexelunk es keresunk nagy iratmennyiseg mellett.

Kapcsolodo dokumentumok:

- `Design_documents/06_document_processing_pipeline_v1.md`
- `Design_documents/10_analysis_batch_processing_plan.md`
- `Design_documents/12_source_bound_findings_model_plan.md`
- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/15_full_document_processing_plan.md`
- `Design_documents/17_storage_migration_impact_review.md`

## 1. Problema

A jelenlegi implementacio a dokumentumok oldalszoveget es chunk szoveget teljes tartalommal PostgreSQL-ben tarolja:

- `document_pages.extracted_text`
- `document_chunks.chunk_text`
- `source_references.quote_text`

Ez fejlesztesi es audit szempontbol tiszta, de nagy ugyeknel rossz iranyba skalaozodik:

- tobb ezer iratnal a DB gyorsan szovegtarolo rendszerrre valik,
- import es ujraimport utan nagy mennyisegu page/chunk rekord keletkezik,
- a page/chunk lista UI-ban es API-ban is nehezen kezelheto,
- Qdrant mellett ugyanaz a nyers szoveg nagyreszt duplikaltan is el,
- az egy-iratos oldalintervallum szures kevesbe hasznos, ha sok ezer rovidebb irat van,
- az iratkategoria-rendszer nagy tomegu "csak kereshessek benne" importnal folosleges adminisztracios terhet okozhat.

Fontos megallapitas:

```text
Nem az a cel, hogy tobb adatot tegyunk DB-be.
Az a cel, hogy csak azt tegyuk DB-be, ami tranzakcios, kapcsolati, audit vagy workflow okbol tenyleg oda valo.
```

## 2. Cel

Olyan nagyugyes dokumentum-alapot kell tervezni, amely:

- 5000+ irat / ugy volumennel is ertelmezheto,
- nem tarolja foloslegesen a teljes oldalszovegeket es chunkokat PostgreSQL-ben,
- megtartja a `No source -> no claim` elvet,
- megorzi az eredeti dokumentumok valtozatlan forraserteket,
- gyors importot es batch importot tamogat,
- tamogatja a PDF es TXT alapot, de bovitheto MD/DOCX iranyba,
- jol illeszkedik Qdrant-alapu szemantikus/hybrid retrievalhez,
- nem teszi szuksegtelenne az emberi kontrollt,
- kesobb is kompatibilis marad audit naploval, forrashivatkozasokkal es grafnezet lehetosegevel.

## 3. Nem cel

Nem cel:

- cloud szolgaltatas bevezetese,
- eredeti iratok felulirasa,
- chat-first rendszerre valtani,
- automatikus jogi/nyomozati donteseket hozni,
- minden importalt iratot azonnal LLM-mel elemeztetni,
- minden ideiglenes keresesi vagy chunkolasi adatot vegleg DB-ben orizni,
- a `search_findings` es structured review workflow kidobasa.

## 4. Alapelv: harom tarolasi reteg

### 4.1 Eredeti irattar

Az eredeti feltoltott fajl valtozatlanul marad a data root alatt.

Javasolt irany:

```text
data_root/
  cases/
    {case_id}/
      documents/
        {document_id}/
          original/
            original.pdf
          extracted/
            text_layers/
            chunks/
            manifests/
```

Az eredeti fajl:

- nem modosul,
- sha256 hash alapjan ellenorizheto,
- csak dokumentum eletciklus muvelettel torolheto, ha meg nem lett forrasanyag.

### 4.2 Tranzakcios adatbazis

PostgreSQL-ben maradjon:

- ugy,
- dokumentum metadata,
- import/proceszalas allapot,
- fajl hash,
- fajltipus,
- text layer metadata,
- chunk/index manifest metadata,
- source reference-ek,
- analysis runok,
- human review,
- audit eventek,
- strukturalt objektumok.

PostgreSQL-ben ne legyen alapertelmezetten teljes nyers oldalszoveg es teljes chunk szoveg nagy ugyes modban.

### 4.3 Kulso szoveg- es indexreteg

A kinyert szoveg es chunkok fajlalapu, append-baratos, manifestelt formaban tarolodjanak a data root alatt.

Javasolt fajlok:

```text
pages.jsonl
chunks.jsonl
chunk_manifest.json
text_layer_manifest.json
```

Pelda `chunks.jsonl` sor:

```json
{"chunk_id":"...","document_id":"...","page_start":7,"page_end":7,"char_start":912,"char_end":1510,"text":"...","text_hash":"..."}
```

A DB csak a manifestet es az azonosithato hivatkozasi pontokat tarolja. A teljes szoveg betoltese akkor tortenik, amikor:

- indexelunk,
- retrieval talalatot allitunk ossze,
- forrashivatkozast validalunk,
- UI-ban forrasreszletet jelenitunk meg.

## 5. Importmodell

### 5.1 Fajltipus registry

Ne legyen hardkodolva szetszorva, hogy milyen fajl importalhato.

Javasolt backend registry:

```text
DocumentParserRegistry
  pdf -> PdfParser
  txt -> TxtParser
```

Kesobbi bovites:

```text
md -> MarkdownParser
docx -> DocxParser
```

A registry adja meg:

- engedelyezett kiterjesztesek,
- MIME tipusu varakozas,
- parser neve,
- kell-e OCR opcio,
- keletkezhet-e tobb text layer,
- milyen minosegi figyelmeztetesek lehetnek.

### 5.2 Batch import

A jelenlegi egyfajlos import mellett kell batch import:

- tobb PDF/TXT kijelolese,
- egy import batch id,
- fajlonkenti statusz,
- reszleges siker megengedett,
- hibak fajlonkent latszanak,
- import batch audit esemeny.

Javasolt fogalmak:

```text
import_batches
import_batch_items
```

Elso implementacio lehet analysis-run alapu is, de nagy ugyeknel kulon batch kovetes tisztabb.

### 5.3 Import utani allapot

Javasolt egyszerusitett workflow:

```text
uploaded
  -> text_extracted
  -> indexed
  -> active
```

Vagy a jelenlegi statuszokhoz illesztve:

```text
review_required / text_review_required / processed
```

PDF minosegi kapu:

- A nativ PDF parser eredmenye csak akkor hozhat letre tartos text layert, `pages.jsonl`-t, `document_pages` rekordot vagy kesobbi chunk/index alapot, ha a parser eredmenye minosegi hiba nelkul atment.
- Ha a parser nem nyer ki szoveget, vagy csak reszleges/gyenge eredmenyt ad, az eredeti PDF megmarad OCR bemenetkent, de nativ text layer nem jon letre.
- Ilyenkor a dokumentum `review_required` allapotba kerul, az analysis run `quality_issues` listat es `next_action=run_ocr` jelzest ad.
- OCR utan ugyanez az elv ervenyes: tiszta OCR eredmenybol text layer keszulhet; teljesen hasznalhatatlan OCR eseten nem jon letre text layer, az analysis run `next_action=discard_or_replace_document` jelzest ad.
- Reszleges OCR eredmenybol sem lesz automatikusan text layer; az analysis run `usable_page_numbers`, `failed_page_numbers` es `next_action=review_partial_ocr_before_text_layer` jelzest ad. A sikeres reszek feldolgozasa kulon, tudatos felhasznaloi elfogadasi workflow legyen.
- Backend oldalon az elso elfogadasi workflow letezik: a reszleges OCR nem aktualis jelolt `pages.jsonl` allomanyt ir, majd `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr/accept-partial` explicit dontessel tudja a kivalasztott hasznalhato oldalakat aktualis OCR text-review layerre emelni.
- Felhasznalo altal elvetett reszeredmeny eseten az iratot vegleges elvetes/torles iranyba kell vinni.

De nagy ugyes mukodesnel a legfontosabb kulonvalasztas:

```text
eredeti fajl megvan
szoveg kinyerve
chunk manifest kesz
embedding index kesz
forraskent aktiv
```

Ezek ne feltetlenul egyetlen statusz mezoben keveredjenek.

## 6. Dokumentumkategoria ujragondolasa

A jelenlegi taxonomy hasznos volt kisebb, kezzel gondozott irathalmaznal.

5000+ iratos ugyeknel mas a prioritas:

- gyors import,
- kereshetoseg,
- forrasmegtalalas,
- kesobbi emberi rendezhetoseg.

Javaslat:

```text
A dokumentum taxonomy ne legyen kotelezo importkori kerdes.
```

Lehetseges iranyok:

1. Teljesen opcionális dokumentumcimkezes.
2. Automatikus `uncategorized` minden batch importnal.
3. Kesobbi tomeges cimkezes vagy mentett dokumentumhalmazok.

Fontos:

```text
Ne legyen olyan UX, amely tobb ezer irat importjat adminisztracios besorolas miatt lassitja.
```

## 7. Retrieval modell nagy ugyekhez

### 7.1 A jelenlegi oldalintervallum-szures korlata

Az oldalintervallum-szures jo, ha:

- egy irat nagyon hosszu,
- a felhasznalo tudja, kb. hol van a relevans resz.

5000 rovid iratnal a fontosabb szurok:

- dokumentumhalmaz,
- fajlnev / dokumentumcim,
- import batch,
- datum,
- fajltipus,
- aktiv / archiv / kizart,
- full-text kulcsszo,
- szemantikus talalat,
- mentett talalati munkalista.

### 7.2 Retrieval pipeline

Javasolt nagyugyes pipeline:

```text
focus/query
  -> lexical prefilter / metadata filter
  -> vector search Qdrantban
  -> hybrid ranker
  -> top N chunk/source candidates
  -> LLM csak a szukitett forrasokon
  -> research_finding worklist
```

Az LLM nem keresomotor. A keresomotor dolga, hogy jo forrasjelolteket adjon neki.

### 7.3 Indexelendo egyseg

Chunk tovabbra is kell, de ne DB-kozpontu modon.

Javasolt chunk rekord a Qdrant payloadban:

```json
{
  "case_id": "...",
  "document_id": "...",
  "chunk_id": "...",
  "page_start": 7,
  "page_end": 7,
  "text_hash": "...",
  "document_title": "...",
  "lifecycle_status": "active",
  "parser_profile": "docling_then_pypdf",
  "text_layer_id": "..."
}
```

A chunk teljes szovege lehet:

- Qdrant payloadban, ha meret es teljesitmeny elfogadhato,
- vagy csak text_hash / chunk_id payloadban, a szoveg pedig `chunks.jsonl`-bol toltodik vissza.

Elso nagyugyes irany:

```text
Qdrant payloadban elegendo preview + azonosito + source metadata.
Teljes chunk text a data root chunk store-bol legyen visszaolvasva.
```

## 8. Source reference modell

A source reference tovabbra is DB-ben marad, mert ez mar audit es szakmai hivatkozasi pont.

Source reference tarolhat:

- `document_id`,
- `text_layer_id`,
- `chunk_id`,
- `page_start`,
- `page_end`,
- `quote_char_start`,
- `quote_char_end`,
- `quote_text`,
- `quote_hash`.

Kerdes:

```text
quote_text maradjon-e teljes szoveggel DB-ben?
```

Javaslat:

- rovid quote text maradhat DB-ben, mert ez a konkret forrashivatkozas ellenorzesi lenyege,
- teljes page/chunk text ne legyen DB-ben,
- quote hash es offset kotelezo legyen,
- quote validacio mindig vissza tudja olvasni a kulso text layerbol.

## 9. DB modell irany

### 9.1 Dokumentum metadata

`documents` marad kozponti tabla, de bovitendo / tisztitando:

```text
id
case_id
original_filename
stored_path
sha256
mime_type
file_extension
file_size_bytes
lifecycle_status
import_batch_id
current_text_layer_id
current_chunk_manifest_id
current_index_status
created_at
updated_at
```

### 9.2 Text layer

Uj vagy tisztabb fogalom:

```text
document_text_layers
```

Mezok:

```text
id
document_id
source_kind native_text | ocr | manual
parser_profile
language
page_count
char_count
storage_uri
manifest_hash
is_current
created_by_run_id
created_at
```

### 9.3 Chunk manifest

Uj fogalom:

```text
document_chunk_manifests
```

Mezok:

```text
id
document_id
text_layer_id
chunking_strategy
chunk_count
storage_uri
manifest_hash
is_current
created_by_run_id
created_at
```

### 9.4 Chunk sorok DB-ben?

Ket lehetseges irany:

1. Minimal DB chunk metadata tabla.
2. Nincs DB chunk tabla nagyugyes modban, csak manifest + Qdrant payload + source reference.

Javaslat elso atalakitasra:

```text
Tartsunk minimal chunk metadata tablat, de ne taroljuk benne a teljes chunk_text-et.
```

Indok:

- konnyebb atmenet a jelenlegi kodbol,
- analysis run input/output kapcsolatok egyszerubbek,
- forras-hivatkozasi integracio kevesbe borul.

Minimal mezok:

```text
id
document_id
text_layer_id
chunk_manifest_id
chunk_id
page_start
page_end
char_start
char_end
text_hash
embedding_model
embedding_vector_id
is_current
```

## 10. UI kovetkezmenyek

### 10.1 Import felulet

Uj import felulet nagy ugyekhez:

- tobb fajl kijelolese,
- fajltipus szures,
- import batch statusz,
- fajlonkenti siker/hiba,
- opcionális OCR kesobb,
- nem kotelezo taxonomy valasztas.

### 10.2 Dokumentumlista

5000+ iratnal a jelenlegi kartya/lista onmagaban nem eleg.

Kell:

- keresheto dokumentumlista,
- lapozas vagy virtualizalt lista,
- statusz filterek,
- fajltipus filter,
- import batch filter,
- indexeltsagi statusz,
- tomeges muveletek.

### 10.3 Forraskivalasztas

Az elemzesi panel ne tobb ezer checkboxot mutasson.

Helyette:

- dokumentumkereso,
- mentett dokumentumhalmaz,
- import batch,
- fajltipus/statusz filter,
- explicit top-N retrieval.

## 11. Kapcsolat a teljes iratfeldolgozassal

A `15_full_document_processing_plan.md` tovabbra is ervenyes szakmai irany:

```text
teljes irat -> elokeszito munkadarabok -> emberi dontes
```

De a backend implementacio csak akkor induljon, ha a jelen dokumentum szerinti storage/retrieval alap el van dontve.

Kulonosen:

- teljes iratfeldolgozo ne feltetelezze, hogy minden oldal teljes szovege DB-ben van,
- oldalblokkokat a text layer store-bol kell tudnia olvasni,
- forrasidezet validacio text layer + offset + hash alapon tortenjen,
- output munkadarabok source evidence-e kompatibilis legyen source_reference letrehozassal.

## 12. Kapcsolat a graf-kompatibilitassal

A nagyugyes storage terv ne zavarja a kesobbi grafnezetet.

Graf szempontbol a lenyeg nem az, hogy DB-ben legyen minden szoveg, hanem hogy a kapcsolatok explicitek legyenek:

```text
document
  -> text_layer
  -> chunk_manifest
  -> source_reference
  -> research_finding
  -> structured_object
  -> human_review
  -> audit_event
```

Ez kesobb grafban megjelenitheto akkor is, ha a teljes nyers szoveg fajlalapu text store-ban van.

## 13. Migracios / atalakitas irany

Mivel a tesztadatbazis ki lett uritve, most lehetoseg van tisztabb iranyvaltasra.

Javasolt sorrend:

1. Dontes a text layer / chunk manifest minimal adatmodellrol.
2. Parser registry bevezetese.
3. Batch import backend szerzodes megtervezese.
4. Jelenlegi import pipeline atvezetese text layer store-ra.
5. Jelenlegi `document_pages.extracted_text` es `document_chunks.chunk_text` szerepenek csokkentese vagy kivezetese.
6. Qdrant indexeles atallitasa chunk store-bol olvasott szovegre.
7. Source reference validacio atallitasa text layer store + offset/hash alapra.
8. Frontend import/dokumentumlista attervezese nagy ugyekhez.
9. Csak ezutan induljon a `full_document_processing` backend elso szelete.

## 14. Elso implementacios scope javaslat

Elso kodolasi lepes ne a teljes rendszer csereje legyen.

Kodszintu hatasterkep:

```text
Design_documents/17_storage_migration_impact_review.md
```

Ebben az elso javasolt biztonsagos technikai szelet:

```text
TextStore absztrakcio + DB-backed adapter + olvasasi pontok atvezetese.
```

Allapot:

```text
kesz: TextStore / SourceTextResolver DB-backed adapter es olvasasi pontok elso atvezetese
kesz: document_text_layers / document_chunk_manifests migracio
kesz: pages.jsonl / chunks.jsonl helper szerzodes
kesz: TXT import fizikai text-store-ra kotese, API-kompatibilitas megtartasaval
kesz: PDF native parse, OCR es explicit chunk creation text-store manifest irasa, API-kompatibilitas megtartasaval
kesz: source-text olvasas tobb runtime ponton text-store first / DB fallback modban: analysis preview, review/source excerpt, search_findings SOURCE es quote validacio, source-reference quote/span validacio, smoke helper, embedding input
kesz: PostgreSQL keyword/FTS fuggoseg kivezetesi terve a 18-as dokumentumban
kesz: elso keyword-search foundation: document_search_entries schema/model es lexical_index service skeleton
kesz: lexical_index populacio bekotese a text-layer/chunk-manifest workflow-kba
kesz: keyword_search atkapcsolasa document_search_entries.search_vector hasznalatara, text-store-backed quote-tal
kovetkezo: import/search live smoke, majd DB text mezok nullable/deprecated terve
```

Javasolt elso scope:

```text
Design spike + minimal storage slice
```

Tartalma:

- `document_text_layers` es `document_chunk_manifests` tervezese/migracioja,
- fajlalapu `pages.jsonl` / `chunks.jsonl` writer-reader helper,
- TXT import atvezetese erre az uj tarolasi modra,
- PDF native text import atvezetese erre az uj tarolasi modra,
- jelenlegi API kompatibilitasi retege, hogy a frontend meg tudja jeleniteni az oldal/chunk tartalmat,
- tesztek arra, hogy a teljes szoveg nem DB-ben, hanem text store-ban van,
- source reference quote validacio text store-bol.

Masodik scope:

- Qdrant indexing a chunk store-bol,
- index statusz chunk manifesthez kotve,
- retrieval talalatok teljes szoveg visszaolvasasa chunk store-bol.

Harmadik scope:

- batch import,
- nagy dokumentumlista UI,
- full-document processing backend.

## 15. Nyitott dontesek

Implementacio elott tisztazando:

- DB-ben maradjon-e minimal chunk metadata tabla, vagy csak manifest legyen? Elso implementacios dontes: marad metadata tabla, teljes szoveg nelkul.
- `document_pages` megmaradjon-e metadata-only tablakent? Elso implementacios dontes: megmarad metadata/source-location szerepben.
- Qdrant payload tartalmazzon-e teljes chunk textet, vagy csak preview-t? Elso implementacios dontes: nem tartalmaz teljes chunk textet; a visszaolvasas text-store-bol tortenik.
- A text store legyen JSONL, SQLite, Parquet, vagy sajat file manifest? Elso implementacios dontes: JSONL manifest.
- Batch importnal legyen-e kulon `import_batches` tabla, vagy analysis run eleg?
- Taxonomy maradjon-e opcionális metadata, vagy legyen teljesen elrejtve nagyugyes importnal? Elso implementacios dontes: aktiv workflow-bol ki lett vezetve.
- Hogyan nezzen ki a tomeges irat torles/archivalas/kizaras UX? Meg nyitott nagyobb UX kerdes; teljes ugy torlese mar letezik kulon veszelyes muveletkent.

## 16. Dontesi osszegzes

Elfogadando uj irany:

```text
PostgreSQL = kapcsolatok, workflow, audit, metadata, source references.
Data root text store = oldalak, chunkok, teljes kinyert szoveg.
Qdrant = embedding index es retrieval payload.
LLM = csak szukitett, forrashu jelolteken dolgozik.
```

Ez a modell jobban illik a valos celhoz:

```text
nem nehany oriasi irat,
hanem sok ezer rovidebb irat,
amelyekben gyorsan, forrashuen es ember altal iranyitva kell kutatni.
```
