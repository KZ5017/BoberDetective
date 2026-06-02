# Lokális Nyomozati Iratintelligencia Rendszer
## MVP backlog és implementációs sorrend

## 1. Cél

Ez a dokumentum hidat képez a design dokumentumok és a tényleges implementáció között.

A cél:

- kijelölni az első működő MVP-állapotot,
- fázisokra bontani a megvalósítást,
- rögzíteni a függőségeket,
- meghatározni a validációs kapukat,
- megakadályozni, hogy túl korán épüljön AI-réteg instabil forrás- és audit-alapra.

Alapelv:

> Előbb source/audit foundation, utána LLM analysis.

## 2. Első működő célállapot

> **Aktualis megjegyzes, 2026-06-02:** az MVP alapok es a szigoru forraskotott munkapad workflow-k mar eleg erosek ahhoz, hogy a kovetkezo nagyobb szeletet eloszor tervezesi szinten az altalanos lokalis RAG kerdezo iranyaba vigyuk. Ez nem valtja ki a `search_findings` es review/worklist folyamatokat, hanem egy szabadabb, kijelolt korpuszra korlatozott kerdes-valasz reteg lesz mellettuk. Uj terv: `Design_documents/20_general_rag_question_answering_plan.md`.

> **Aktualis megjegyzes, 2026-05-17:** az elso MVP celallapot nagy resze mar megvalosult es tovabb finomodott: React/Vite frontend, explicit PDF text-review/chunkolas, OCR, batch-kepes raw-chunk analysis modulok, semantic/hybrid retrieval es background indexing is van. A kovetkezo nagy alapozas a strukturalt irattaxonomia es forrasszures. Friss allapot: `CURRENT_STATE.md`; uj terv: `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`.

Az első valóban hasznos MVP célállapot:

```text
A felhasználó létrehoz egy ügyet, importál néhány TXT/PDF dokumentumot,
a rendszer lokálisan eltárolja az eredetiket, hash-t számol,
oldalszintű szöveget és chunkokat hoz létre,
kereshetővé teszi az anyagot,
majd forráshivatkozott kérdés-válasz és claim extraction futtatható.
Minden eredmény source quote-tal, analysis_run kapcsolattal,
source_validation_status mezővel és review_status mezővel rendelkezik.
```

Nem cél az első működő állapotban:

- teljes frontend,
- minden dokumentumtípus tökéletes kezelése,
- OCR tökéletesítése,
- contradiction detection,
- jogszabályi RAG,
- exportált hivatalos riport.

## 3. Implementációs alapelvek

1. Minden új modulhoz legyen minimális teszt vagy ellenőrző script.
2. Minden AI-output előtt legyen működő source reference és quote validation alap.
3. Minden hosszabb folyamat `analysis_runs` rekordhoz kötődjön.
4. Minden fontos művelet audit eseményt írjon.
5. Előbb a legegyszerűbb dokumentumtípusok: TXT és natív szöveges PDF.
6. OCR csak akkor jöjjön, ha az import + parsing + page/chunk alap már működik.
7. Frontend csak akkor jöjjön, ha backend API-n már van valós adatfolyam.

## 4. Fázis 0: Környezetellenőrzés

### Cél

Biztosítani, hogy a WSL2 fejlesztési környezet alkalmas az implementációra.

### Feladatok

- Ellenőrizni:
  - Python verzió,
  - Git,
  - Node/npm,
  - PostgreSQL elérhetőség vagy telepítési stratégia,
  - Docker/Compose elérhetőség, ha használjuk,
  - Tesseract és magyar nyelvi csomag,
  - LM Studio API WSL-ből elérhető-e.
- Létrehozni vagy dokumentálni:
  - `.env.example`,
  - data root: `~/boberdetective-data`,
  - fejlesztési portok.

### Definition of Done

- Van rövid környezetellenőrzési eredmény.
- Tudjuk, hogy PostgreSQL/Qdrant konténerrel vagy lokálisan indul.
- Tudjuk, hogy LM Studio elérhetősége működik-e WSL felől.

## 5. Fázis 1: Backend scaffold

### Cél

Minimális FastAPI backend alap létrehozása.

### Feladatok

- Projektstruktúra:
  - `app/api`,
  - `app/core`,
  - `app/db`,
  - `app/models`,
  - `app/schemas`,
  - `app/services`,
  - `tests`.
- Konfiguráció:
  - data root,
  - database URL,
  - Qdrant URL,
  - LLM provider config.
- Health endpoint:
  - backend alive,
  - config loaded,
  - provider placeholders.

### Definition of Done

- Backend indul WSL alatt.
- `GET /api/v1/system/health` működik.
- Van alap teszt vagy manuális ellenőrző parancs.

## 6. Fázis 2: Database baseline

### Cél

Az első SQL migrációk létrehozása a source/audit foundationhöz.

### Első táblák

1. `users`
2. `cases`
3. `case_users`
4. `documents`
5. `analysis_runs`
6. `analysis_run_inputs`
7. `analysis_run_outputs`
8. `audit_events`

### Következő táblák

1. `document_pages`
2. `document_chunks`
3. `source_references`

### Definition of Done

- Migrációk lefutnak üres DB-n.
- Alap seed/dev user létrehozható.
- FK-k és alap CHECK constraint-ek működnek.
- `text + CHECK` van, nem PostgreSQL ENUM.

## 7. Fázis 3: Audit service

### Cél

Explicit audit írás bevezetése.

### Feladatok

- `audit_events` író service.
- Append-only JSONL írás data root alatt.
- Request/user/case kontextus kezelése.
- Hiba esetén is auditálható esemény.

### Definition of Done

- Case creation auditált.
- Document import kísérlet auditált.
- Sikertelen művelet is auditált.
- JSONL és DB audit esemény összekapcsolható.

## 8. Fázis 4: Case és user minimum API

### Cél

Ügy létrehozás és jogosultsági alapok.

### Endpointok

- `GET /api/v1/cases`
- `POST /api/v1/cases`
- `GET /api/v1/cases/{case_id}`
- minimális dev user kezelés.

### Definition of Done

- Ügy létrehozható.
- Ügy listázható.
- Case-bound jogosultság alapja megvan.
- Minden művelet auditált.

## 9. Fázis 5: Document import + immutable storage

### Cél

Eredeti dokumentumok biztonságos importja.

### Feladatok

- Multipart upload endpoint.
- SHA-256 hash számítás.
- Storage útvonal:
  - `~/boberdetective-data/cases/<case_id>/originals/<document_id>/`.
- `documents` rekord létrehozása.
- Duplikátumkezelés `(case_id, sha256_hash)` alapján.

### Definition of Done

- TXT és PDF fájl importálható.
- Eredeti fájl változatlanul eltárolódik.
- Hash visszaellenőrizhető.
- Duplikátum nem írja felül a meglévő dokumentumot.
- Import auditált.

## 10. Fázis 6: Analysis run alap és document processing indítás

### Cél

Aszinkron vagy kezdetben szinkron feldolgozási runok egységes kezelése.

### Feladatok

- `analysis_runs` létrehozása document processinghez.
- `POST /documents/{document_id}/process`.
- Run státusz lekérdezése.
- `analysis_run_inputs` kitöltése dokumentum inputtal.

### Definition of Done

- Processing run indítható.
- Sikeres és sikertelen run státusz látszik.
- Audit események kapcsolódnak a runhoz.

## 11. Fázis 7: TXT és natív szöveg parsing

### Cél

Első oldal- és szövegkinyerési flow.

### Feladatok

- TXT parser.
- Egyszerű natív PDF parser bevezetése.
- `document_pages` írás:
  - `version_no = 1`,
  - `is_current = true`,
  - `text_source`,
  - parser metadata.
- Page validation alap.

### Definition of Done

- TXT dokumentumból page record készül.
- Natív PDF-ből page record készül, ha a parser támogatja.
- Üres vagy hibás dokumentum `review_required` vagy `failed` státuszt kap.
- Page rekordok runhoz és audithoz köthetők.

## 12. Fázis 8: Chunking

### Cél

Aktuális page textből kereshető chunkok létrehozása.

### Feladatok

- Egyszerű paragraph/window chunker.
- `document_chunks` írás:
  - page range,
  - chunk index,
  - token count becslés,
  - chunker version,
  - `version_no`,
  - `is_current`.
- Újrafuttatásnál régi chunkok superseded állapota.

### Definition of Done

- Legalább TXT dokumentum chunkolható.
- Chunkból vissza lehet mutatni dokumentumra és oldalra.
- Új chunk run nem törli nyomtalanul a régi chunkot.

## 13. Fázis 9: Keyword search

### Cél

Első forrásalapú keresés PostgreSQL-ből.

### Feladatok

- Chunk/page full-text vagy egyszerű LIKE/FTS keresés MVP-szinten.
- `POST /search/keyword`.
- Találatok:
  - document id,
  - page,
  - chunk id,
  - quote snippet.

### Definition of Done

- Importált dokumentumban kereshető szöveg.
- Találatból kézzel ellenőrizhető quote jön vissza.
- Keresés auditált.

## 14. Fázis 10: Source references és quote validation

### Cél

Forráshivatkozások létrehozása és ellenőrzése.

### Feladatok

- `source_references` tábla használata.
- Source reference létrehozás keresési találatból.
- Quote validation:
  - chunkban szerepel-e,
  - page textben szerepel-e,
  - case egyezés.

### Definition of Done

- Source reference létrehozható.
- Érvényes quote `source_valid`.
- Hibás quote `source_invalid`.
- Ez a réteg LLM nélkül is működik.

## 15. Fázis 11: Qdrant és embedding

### Cél

Szemantikus keresés alapja.

### Feladatok

- Qdrant dev setup.
- Embedding provider adapter.
- Chunk embedding generálás.
- `embedding_vector_id` mentése.
- `POST /search/vector` vagy hybrid alap.

### Definition of Done

- Legalább néhány chunk beindexelhető.
- Vektoros keresés chunk id-t ad vissza.
- Qdrant payload tartalmaz case/document/chunk metadata adatokat.

### Megjegyzés

Ha LM Studio embedding bizonytalan, külön embedding provider döntés kell. Ez ne blokkolja a keyword search + source validation alapot.

## 16. Fázis 12: LLMProvider alap

### Cél

Generatív LLM hívások izolálása provider absztrakció mögé.

### Feladatok

- `LLMProvider` interfész.
- `OpenAICompatibleProvider`.
- LM Studio config.
- Healthcheck.
- Model info.
- Timeout és hiba mapping.

### Definition of Done

- WSL backend tud healthchecket kérni LM Studio felé.
- Egy egyszerű structured JSON próbahívás lefut.
- Provider hiba nem omlasztja össze az API-t.

## 17. Fázis 13: Közös schema és source validator

### Cél

LLM outputok közös validációja.

### Feladatok

- Common source object validator.
- Quote validator.
- JSON schema validator.
- `source_validation_status` mapping.
- Sikertelen validáció auditálása.

### Definition of Done

- Forrás nélküli output elutasításra kerül.
- Nem létező chunkra mutató output elutasításra kerül.
- Hibás quote source invalid státuszt kap.

## 18. Fázis 14: Első LLM modul: `answer_with_citations`

### Cél

Retrieval + LLM + source validation első end-to-end próbája.

### Feladatok

- Prompt builder.
- JSON parser.
- Source validation.
- Response API.
- Analysis run input/output mentése.

### Definition of Done

- Felhasználói kérdésre csak context alapján válaszol.
- Válaszhoz source quote tartozik.
- Insufficient source esetén nem talál ki választ.
- Minden auditált.

## 19. Fázis 15: `extract_claims`

### Cél

Első strukturált AI-output objektumtábla feltöltése.

### Feladatok

- Claims schema.
- Prompt builder.
- Claim mapper DB-be.
- `claim_sources`.
- `source_validation_status`.
- `review_status = new`.

### Definition of Done

- Legalább egy claim létrejön forrásból.
- Source nélküli claim nem menthető.
- Claim listázható API-n.
- Human review még nem kötelező, de státusz látszik.

## 20. Fázis 16: Human review minimum

### Cél

AI-output emberi ellenőrzési státuszának kezelése.

### Feladatok

- `human_reviews` tábla használata.
- `POST /reviews`.
- Verify/reject/comment.
- Objektum `review_status` frissítése.

### Definition of Done

- Claim verified/rejected státuszba tehető.
- Review esemény append-only módon megmarad.
- Audit esemény készül.

## 21. Fázis 17: Export minimum

### Cél

Csak ellenőrzött, source-valid objektumok exportja.

### Feladatok

- Markdown export.
- `exports` és `export_items`.
- `verified_only` default.
- `require_source_valid = true`.
- Export hash.

### Definition of Done

- Verified + source_valid claim exportálható.
- Nem verified vagy source_invalid objektum default nem exportálható.
- Export auditált.

## 22. Fázis 18: További analysis modulok

Javasolt sorrend:

1. `extract_entities`
2. `extract_events`
3. `summarize_case`
4. `detect_missing_items`
5. `detect_contradiction_candidates`

Mindegyikre ugyanazok a kapuk:

- JSON schema valid,
- source required,
- quote validation,
- analysis_run provenance,
- review_status,
- audit.

## 23. Fázis 19: OCR bevezetése

### Cél

Szkennelt PDF-ek kezelése.

### Feladatok

- Tesseract integráció.
- Magyar language pack ellenőrzés.
- OCR confidence tárolás.
- OCR page verziózás.
- `review_required` alacsony confidence esetén.

### Definition of Done

- Egyszerű szkennelt PDF-ből page text készül.
- OCR eredmény verziózott.
- Alacsony minőség nem válik csendben megbízható alappá.

## 24. Fázis 20: Minimal frontend

### Cél

Case analysis workbench első UI-ja.

### Első nézetek

- case list,
- case detail,
- document list,
- document pages/chunks,
- search,
- claims list,
- claim detail source quote-tal,
- review action,
- export list.

### Nem cél

- landing page,
- chatbot-first UI,
- látványos, de workflow nélküli dashboard.

## 25. Validációs kapuk implementáció közben

## 25.1 Source gate

AI-output nem menthető source nélkül.

## 25.2 Quote gate

Quote-nak meg kell találnia a source chunkban vagy page textben.

## 25.3 Provenance gate

AI-output nem menthető `created_by_analysis_run_id` nélkül.

## 25.4 Review/export gate

Export default:

- `review_status = verified`,
- `source_validation_status = source_valid`.

## 25.5 Audit gate

Minden fontos művelethez legyen DB audit esemény. JSONL audit legyen bekötve legkésőbb az import és analysis run fázisban.

## 26. Tesztprioritások

Első tesztek:

- SHA-256 stabil hash.
- Duplikált dokumentum felismerés.
- Document path case alatt marad.
- Page versioning.
- Chunk versioning.
- Source quote validation.
- Source nélküli claim elutasítása.
- Export gate működése.

Későbbi tesztek:

- OCR confidence kezelés.
- Qdrant payload konzisztencia.
- LM Studio provider hiba kezelés.
- JSON schema invalid output kezelése.
- Human review audit.

## 27. Tudatosan későbbre hagyandó

Ne implementáljuk az első körökben:

- jogszabályi RAG,
- automatikus jogi minősítés,
- contradiction detection production flow,
- graph analytics,
- enterprise permission rendszer,
- multi-case összehasonlítás,
- e-mail/chat/cellaadat speciális pipeline,

Megjegyzes: a jogszabalyi RAG tovabbra is specializalt, kesobbi corpus-profil. Az altalanos lokalis RAG kerdezo megtervezese viszont most mar kovetkezo nagyobb irany, mert ugyanarra a stabil import/text-store/retrieval/LLM/audit alapra epul.
- PDF/DOCX export,
- biometria, hang, videó.

## 28. Első konkrét implementációs sprint javaslat

Az első kódolási sprint célja:

```text
FastAPI backend indul,
case létrehozható,
TXT dokumentum importálható,
hash és immutable storage működik,
audit event keletkezik,
document_pages létrejön,
document_chunks létrejön,
keyword search visszaad source quote-tal ellenőrizhető találatot.
```

Ez még LLM nélkül is értékes, mert bizonyítja a source/audit foundationt.

## 29. Rövid összegzés

Az MVP implementációt nem az LLM-mel kell kezdeni.

A helyes sorrend:

1. local runtime,
2. database and audit foundation,
3. immutable document import,
4. page/chunk source layer,
5. search and source validation,
6. LLMProvider,
7. first source-cited analysis,
8. human review,
9. export.

Ha ez a sorrend megmarad, a rendszer később is auditálható és bővíthető marad.
