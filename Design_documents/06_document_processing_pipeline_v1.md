# Lokális Nyomozati Iratintelligencia Rendszer
## Dokumentumfeldolgozó pipeline v1

## 1. Cél

Ez a dokumentum az MVP-1 dokumentumfeldolgozó pipeline tervét írja le.

A pipeline feladata:

- eredeti dokumentumok biztonságos importálása,
- SHA-256 hash készítése,
- immutable eredeti fájl megőrzése,
- dokumentumtípus és feldolgozási stratégia meghatározása,
- parsing és OCR futtatása,
- oldalszintű szöveg létrehozása,
- chunkok létrehozása verziózottan,
- embedding és keresőindex előkészítése,
- forráshivatkozások alapjának megteremtése,
- minden lépés auditálása.

Alapelv:

> Ha a pipeline nem tud megbízható page/chunk/source alapot létrehozni, későbbi AI-állítás sem tekinthető használhatónak.

## 2. Pipeline szerepe az architektúrában

> **Aktualis megjegyzes, 2026-05-17:** a megvalositott PDF pipeline tudatosan ketlepcsos lett. Native parse vagy OCR utan current page text reteg keletkezik `text_review_required` allapotban, es csak felhasznaloi jovahagyas utan keszulnek current chunkok. Ez csokkenti az OCR/native duplikacio es a rossz text layerbol indulo elemzes kockazatat. A friss operationalis allapotot `CURRENT_STATE.md`, az API iranyt pedig `Design_documents/05_api_design_v1.md` jelzi.

Magas szintű folyamat:

```text
File upload / import
  ↓
Immutable original storage
  ↓
SHA-256 hash + document record
  ↓
File inspection
  ↓
Parsing strategy selection
  ↓
Native text extraction
  ↓
OCR if needed
  ↓
Page-level text records
  ↓
Chunking
  ↓
Embedding + index metadata
  ↓
Keyword/vector search availability
  ↓
Source references and analysis inputs
```

A pipeline nem készít önálló nyomozati vagy jogi megállapításokat. Csak megbízható, auditálható dokumentumalapot épít a későbbi elemzésekhez.

## 3. Bemenetek és kimenetek

## 3.1 Támogatott MVP bemenetek

Első körben:

- PDF,
- szkennelt PDF,
- DOCX,
- TXT,
- HTML,
- egyszerű e-mail export.

Későbbre hagyva:

- XLSX / CSV mélyebb táblázatos feldolgozás,
- PST / MBOX,
- chat exportok,
- képfájl-kötegek,
- híváslista- és cellaadat-specifikus parser.

## 3.2 Pipeline fő kimenetei

Adatbázisban:

- `documents`,
- `analysis_runs`,
- `analysis_run_inputs`,
- `analysis_run_outputs`,
- `document_pages`,
- `document_chunks`,
- `source_references` későbbi keresési/elemzési lépésekhez,
- `audit_events`.

Fájlrendszeren:

- immutable original file,
- opcionális derived text snapshotok,
- audit JSONL bejegyzések,
- későbbi exportok.

Qdrantban:

- chunk embedding vektorok,
- chunkhoz kötött payload metadata.

## 4. Storage elrendezés

Fejlesztési alapértelmezés:

```text
~/boberdetective-data/
  ├─ cases/
  │   └─ <case_id>/
  │       ├─ originals/
  │       │   └─ <document_id>/
  │       ├─ derived/
  │       │   └─ <document_id>/
  │       ├─ audit/
  │       └─ exports/
  ├─ postgres/
  └─ qdrant/
```

Importkor az eredeti fájl a rendszer storage alá kerül. Az adatbázis nem bináris dokumentumtár, hanem metaadatot, hash-t és útvonalat tárol.

## 5. Analysis run modell

Minden nagyobb pipeline lépés `analysis_runs` rekordhoz kötődjön.

Javasolt `run_type` értékek:

- `import_document`,
- `inspect_document`,
- `parse_document`,
- `ocr_document`,
- `extract_pages`,
- `chunk_document`,
- `embed_chunks`,
- `index_chunks`,
- `validate_document_processing`.

Állapotok:

- `queued`,
- `running`,
- `succeeded`,
- `failed`,
- `cancelled`.

Minden run mentse:

- indító felhasználó,
- provider/tool neve,
- tool verzió,
- input dokumentum/page/chunk id-k,
- futási paraméterek,
- validation státusz,
- hibaüzenet,
- kezdés és befejezés ideje.

## 6. Lépésenkénti terv

## 6.1 Import

### Cél

A felhasználó által feltöltött dokumentum ügyhöz rendelése és biztonságos eltárolása.

### Műveletek

1. Jogosultság ellenőrzése.
2. Case státusz ellenőrzése.
3. Fájl alapellenőrzése:
   - üres-e,
   - fájlméret elfogadható-e,
   - kiterjesztés és MIME típus értelmezhető-e.
4. Ideiglenes import helyre mentés.
5. SHA-256 hash számítása.
6. Duplikátum ellenőrzése `(case_id, sha256_hash)` alapján.
7. Végleges immutable storage útvonal kialakítása.
8. `documents` rekord létrehozása.
9. `audit_events` és JSONL audit bejegyzés írása.

### Fontos szabályok

- Az eredeti fájl tartalma import után nem módosítható.
- A hash a véglegesen eltárolt eredeti fájlról készüljön.
- Duplikátum esetén az API adjon kontrollált választ, ne írja felül a meglévő dokumentumot.

## 6.2 Dokumentum inspection

### Cél

Feldolgozási stratégia meghatározása.

### Vizsgált adatok

- MIME típus,
- kiterjesztés,
- fájlméret,
- oldalszám, ha gyorsan megállapítható,
- titkosított vagy sérült-e,
- natív szöveg valószínűsíthető-e,
- OCR szükséges-e.

### Kimenet

Frissülhet:

- `documents.page_count`,
- `documents.mime_type`,
- `documents.file_extension`,
- `documents.is_encrypted`,
- `documents.processing_status`,
- `documents.parser_name`,
- `documents.parser_version`.

## 6.3 Parsing

> **Aktualis megjegyzes, 2026-05-17:** a jelenlegi default PDF parser profil `docling_then_pypdf`: Docling az elsodleges, lokalis `pypdf` fallbackkel. Explicit `BOBERDETECTIVE_PDF_PARSER=docling` smoke sikeres volt. A parser kimenete tovabbra sem forrasigazsag onmagaban; page/chunk/source validacio es emberi review szukseges.

### Cél

Natív szöveget tartalmazó dokumentumokból oldalszintű szöveg kinyerése.

### Elsődleges parser

```text
Docling
```

### Bemenet

- `document_id`,
- immutable original path,
- parser profile,
- language hint.

### Kimenet

Oldalanként:

- `page_number`,
- `extracted_text`,
- `text_source = native` vagy `mixed`,
- parser metadata,
- `text_char_count`,
- `version_no = 1`,
- `is_current = true`.

### Minőségellenőrzés

Oldalanként jelölni kell:

- üres vagy közel üres oldal,
- nagyon rövid szöveg,
- gyanús karakterarány,
- parser hiba,
- OCR-re javasolt oldal.

## 6.4 OCR

> **Aktualis megjegyzes, 2026-05-17:** az OCR explicit felhasznaloi muvelet PDF dokumentumokra, backend OCR-ajanlas metadata alapjan (`hidden`, `recommended`, `optional`). OCR utan current page reteg frissul, de chunkolas kulon lepes marad. Optional OCR szoveges PDF-en zajt/duplikaciot okozhat, ezert UI-ban OCR ellenorzeskent kell kezelni.

### Cél

Szkennelt vagy gyenge natív szövegű dokumentumokból oldalszintű szöveg előállítása.

### OCR motor

```text
Tesseract OCR magyar nyelvi támogatással
```

### Mikor fusson OCR?

OCR fusson, ha:

- nincs natív szöveg,
- oldalanként túl kevés a natív szöveg,
- a parser szövege zajos,
- a dokumentum inspection szkennelt PDF-et jelez,
- a felhasználó explicit kéri az OCR újrafuttatását.

### Kimenet

Oldalanként:

- `text_source = ocr` vagy `mixed`,
- `ocr_used = true`,
- `ocr_confidence`, ha elérhető,
- parser/OCR tool verzió,
- verziózott `document_pages` rekord.

### Újrafuttatás

OCR újrafuttatáskor:

- új `analysis_runs` rekord keletkezik,
- új `document_pages` verziók keletkeznek,
- korábbi aktuális rekordok `is_current = false` állapotba kerülnek,
- `superseded_by_id` az új rekordra mutat.

## 6.5 Page validation

### Cél

Annak eldöntése, hogy a page text elég jó-e chunkoláshoz és későbbi forráshivatkozáshoz.

### Ellenőrzések

- oldalanként van-e rekord,
- oldalszámok folytonosak-e,
- `text_char_count` helyes-e,
- OCR confidence elfogadható-e,
- nincs-e túl sok üres oldal,
- parser/OCR hibák száma elfogadható-e.

### Kimenet

Dokumentum feldolgozási státusz:

- `processed`,
- `review_required`,
- `failed`.

Alacsony minőségű oldal esetén a dokumentum maradhat feldolgozott, de `review_required` jelölést kapjon.

## 6.6 Chunking

> **Aktualis megjegyzes, 2026-05-17:** a jelenlegi chunking strategia page-local `char_window_v2`: nem lep at feldolgozott oldalhataron, es paragraph breaket preferal sentence-end, line break, space, majd hard karakterlimit elott. A dokumentumszintu, oldalakon ativelo chunkolas tudatosan nincs bevezetve, mert a forrashely-huseg fontosabb.

### Cél

Oldalszintű szövegből kereshető, embeddingelhető, forráshivatkozható egységek létrehozása.

### MVP stratégia

```text
chunk_size: 800-1200 token körül
overlap: 100-200 token körül
határ: lehetőleg bekezdés vagy mondathatár
```

### Kimenet

`document_chunks` rekordok:

- `case_id`,
- `document_id`,
- `page_start`,
- `page_end`,
- `chunk_index`,
- `chunk_text`,
- `char_start`,
- `char_end`,
- `token_count`,
- `chunking_strategy`,
- `chunker_version`,
- `chunk_run_id`,
- `version_no`,
- `is_current`.

### Fontos szabály

A chunknak mindig visszavezethetőnek kell lennie:

- konkrét dokumentumra,
- oldaltartományra,
- feldolgozási runra,
- chunker verzióra.

## 6.7 Embedding

> **Aktualis megjegyzes, 2026-05-27:** a chunk indexing mar hatterjobkent is elerheto, LM Studio/OpenAI-compatible embeddinggel es Qdrant model-specifikus collectionokkel. A jelenlegi default embedding modell `text-embedding-bge-m3`; index batching default `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE=8`. A friss operationalis reszleteket `CURRENT_STATE.md` es `AI_NOTES.md` tartalmazza.

### Cél

Aktuális chunkok szemantikus kereshetővé tétele.

### Provider stratégia

Az embedding provider külön konfigurálható legyen. Ne legyen automatikusan azonos a generatív LLM-mel.

Lehetséges MVP opciók:

- LM Studio embedding endpoint, ha stabil és megfelelő,
- külön lokális embedding provider,
- később Ollama vagy llama.cpp kompatibilis megoldás.

### Kimenet

`document_chunks` mezők frissülnek:

- `embedding_provider`,
- `embedding_model`,
- `embedding_vector_id`.

Qdrant payload minimálisan:

- `case_id`,
- `document_id`,
- `chunk_id`,
- `page_start`,
- `page_end`,
- `chunk_index`,
- `chunker_version`,
- `version_no`,
- `is_current`.

## 6.8 Keyword index

### Cél

Pontos keresések támogatása nevek, dátumok, ügyszámok, rendszámok, telefonszámok és idézetrészletek alapján.

MVP-ben PostgreSQL full-text search elegendő lehet:

- `document_pages.extracted_text`,
- `document_chunks.chunk_text`.

Magyar nyelvnél mérni kell, hogy a `simple` konfiguráció elég-e, vagy később külön magyar FTS/OpenSearch irány kell.

## 6.9 Processing validation

### Cél

Dokumentumszintű feldolgozási eredmény validálása.

### Ellenőrzések

- létezik `documents` rekord,
- létezik legalább egy aktuális `document_pages` rekord,
- oldalszámok konzisztensek,
- létezik legalább egy aktuális `document_chunks` rekord, ha van kinyert szöveg,
- chunkok oldaltartománya érvényes,
- embedding státusz megfelel a választott feldolgozási profilnak,
- minden pipeline lépéshez van audit esemény.

### Kimenet

`documents.processing_status`:

- `processed`,
- `review_required`,
- `failed`.

## 7. Source reference kapcsolódás

A pipeline önmagában nem köteles minden page/chunkhoz `source_references` rekordot létrehozni.

Javasolt szabály:

- keresési találatból,
- AI analysis inputból,
- emberi kijelölésből,
- exportált idézetből

keletkezzen konkrét `source_references` rekord.

A source reference mindig konkrét:

- dokumentumra,
- oldalra vagy chunkra,
- idézetre,
- karakterpozícióra, ha elérhető,
- létrehozó runra vagy felhasználóra

mutasson.

## 8. Állapotmodell

## 8.1 Document processing status

Javasolt értékek:

- `pending`,
- `processing`,
- `processed`,
- `failed`,
- `review_required`.

## 8.2 Page quality státusz alkalmazásszinten

Nem feltétlenül kell külön DB mező az első körben, de a validation outputban érdemes számolni:

- `ok`,
- `empty`,
- `low_text`,
- `low_ocr_confidence`,
- `parser_warning`,
- `manual_review_needed`.

Ez mehet `analysis_runs.input_parameters` / output summary vagy audit payload mezőbe az első MVP-ben.

## 8.3 Újrafeldolgozás

Újrafeldolgozás oka lehet:

- jobb OCR beállítás,
- új parser verzió,
- új chunking stratégia,
- manuális page text javítás,
- embedding modell csere.

Alapelv:

- eredeti fájl nem változik,
- page/chunk új verziót kap,
- régi analysis runok régi konkrét rekordokra mutatnak,
- aktuális keresés csak `is_current = true` rekordokon fusson,
- auditból látszódjon, mi váltott mit.

## 9. Hibakezelés

## 9.1 Tipikus hibák

- unsupported file type,
- encrypted document,
- corrupted file,
- parser failed,
- OCR failed,
- no text extracted,
- chunking failed,
- embedding provider unavailable,
- Qdrant indexing failed,
- storage write failed.

## 9.2 Hiba esetén mentendő

`analysis_runs`:

- `status = failed`,
- `error_message`,
- tool/provider metadata,
- input dokumentum/chunk id-k.

`audit_events`:

- `event_type`,
- `success = false`,
- `input_summary`,
- `error_message`,
- related document/page/chunk id.

`documents`:

- `processing_status = failed` vagy `review_required`.

## 10. Idempotencia és újraindíthatóság

Az import kivételével a pipeline lépések legyenek újraindíthatók.

Javaslat:

- import hash alapján detektálja a duplikátumot,
- parsing/OCR/chunking új runként fusson,
- embedding újrafuttatáskor új vector id-k keletkezhetnek,
- Qdrant index frissítése legyen összevethető a DB aktuális chunkjaival.

Minden újrafuttatás legyen explicit felhasználói vagy rendszeresemény, auditált okkal.

## 11. Audit események

Javasolt eseménytípusok:

- `document_import_started`,
- `document_imported`,
- `document_duplicate_detected`,
- `document_inspection_started`,
- `document_inspection_completed`,
- `document_parsing_started`,
- `document_parsing_completed`,
- `document_ocr_started`,
- `document_ocr_completed`,
- `document_page_validation_completed`,
- `document_chunking_started`,
- `document_chunking_completed`,
- `document_embedding_started`,
- `document_embedding_completed`,
- `document_indexing_started`,
- `document_indexing_completed`,
- `document_processing_failed`,
- `document_processing_completed`,
- `document_processing_review_required`.

## 12. API kapcsolódás

A pipeline-t az API v1 főként ezekkel az endpointokkal indítja és figyeli:

```text
POST /api/v1/cases/{case_id}/documents
POST /api/v1/cases/{case_id}/documents/{document_id}/process
GET  /api/v1/cases/{case_id}/analysis-runs/{analysis_run_id}
GET  /api/v1/cases/{case_id}/documents/{document_id}/pages
GET  /api/v1/cases/{case_id}/documents/{document_id}/chunks
POST /api/v1/cases/{case_id}/search/hybrid
```

Hosszabb feldolgozásnál az API aszinkron `analysis_run_id` választ adjon.

## 13. Első implementációs sorrend pipeline szinten

Javasolt sorrend:

1. Storage path és case directory konvenció.
2. Document import + SHA-256 + `documents` rekord.
3. `analysis_runs` és explicit audit service minimális használata.
4. TXT és egyszerű natív szövegű PDF parsing.
5. Page-level text írás verziózással.
6. Egyszerű chunking aktuális page textből.
7. PostgreSQL full-text keresés chunkokon.
8. Qdrant embedding/index integráció.
9. OCR szkennelt PDF-ekre.
10. Processing validation és `review_required` státusz.
11. Újrafeldolgozás verziózási szabályai.

## 14. Tesztelési terv

MVP pipeline tesztanyagok:

- rövid TXT,
- natív szöveges PDF,
- szkennelt PDF magyar szöveggel,
- vegyes PDF,
- DOCX,
- üres vagy sérült dokumentum,
- duplikált dokumentum,
- nagyon rossz OCR-minőségű dokumentum.

Mérendő:

- hash stabilitás,
- page count helyesség,
- extracted text karakterarány,
- OCR confidence,
- chunk oldaltartomány pontossága,
- source quote visszakereshetőség,
- újrafeldolgozás verziókonzisztenciája,
- audit teljessége.

## 15. Tudatosan későbbre hagyva

Nem MVP-1 pipeline cél:

- automatikus jogi minősítés,
- jogszabályi RAG feldolgozás,
- híváslista/cellaadat-specifikus normalizáló pipeline,
- e-mail thread rekonstrukció,
- chat export speciális feldolgozás,
- képfelismerés vagy arcfelismerés,
- hang vagy videó feldolgozás.

## 16. Rövid összegzés

A dokumentumfeldolgozó pipeline a rendszer forráshű alaprétege.

Az MVP-ben a legfontosabb cél nem az, hogy minden dokumentumtípust tökéletesen kezeljen, hanem hogy:

1. az eredeti fájl változatlan maradjon,
2. minden kinyert oldal és chunk verziózott legyen,
3. minden feldolgozási lépés `analysis_runs` és audit esemény mögé kerüljön,
4. a későbbi AI-outputok konkrét page/chunk/source rekordokra tudjanak hivatkozni,
5. hibás vagy gyenge minőségű feldolgozás ne váljon észrevétlenül "megbízható" elemzési alappá.
