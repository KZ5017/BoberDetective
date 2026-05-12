# Lokális Nyomozati Iratintelligencia Rendszer
## Környezetellenőrzés és biztonságos fejlesztési baseline

## 1. Ellenőrzés dátuma

```text
2026-05-11
```

## 2. Ellenőrzött munkakönyvtár

```text
/home/bober/projects/Codex_BoberDetective
```

## 3. WSL környezet

Eredmény:

- OS: Ubuntu 24.04.4 LTS
- Kernel: WSL2 Linux 6.6.114.1-microsoft-standard-WSL2
- User: `bober`
- Home: `/home/bober`
- Shell: `/bin/bash`
- CPU: 16 logical CPU
- RAM: kb. 15 GiB
- Root filesystem: kb. 1007 GiB, bőven van szabad hely

Értékelés:

```text
OK az MVP fejlesztéshez.
```

## 4. Projekt- és adatútvonalak

Projekt:

```text
/home/bober/projects/Codex_BoberDetective
```

Adatútvonal:

```text
/home/bober/boberdetective-data
```

Eredmény:

- projektkönyvtár írható,
- data path létezik,
- data path olvasható és írható.

Megjegyzés:

A data path jelenleg üres, ez jó kiinduló állapot az első import/storage tesztekhez.

## 5. Repository állapot

Eredmény:

```text
Git repository initialized on branch main.
```

Megjegyzés:

A repository már `main` ágon követi az `origin/main` távoli ágat. A `.gitignore` kizárja a `.venv`, cache, `__pycache__` és `*.egg-info` generált fájlokat.

Talált extra Windows metadata fájlok:

```text
Design_documents/01_concept_and_mvp_requirements.md:Zone.Identifier
Design_documents/02_technical_architecture_v1.md:Zone.Identifier
```

Ezek Windowsból származó Zone.Identifier mellékfolyam-fájlok WSL alatt. Nem kritikusak, de később érdemes dönteni, hogy töröljük-e őket.

## 6. Elérhető fejlesztői eszközök

Elérhető:

- Python: 3.12.3
- pip: 24.0
- Git: 2.43.0
- Node: 18.19.1
- npm: 9.2.0
- curl: 8.5.0
- GNU Make: 4.3
- Docker CLI: 29.4.3
- Docker Compose: v5.1.3
- PostgreSQL CLI: 16.13
- `pg_isready`: 16.13
- Tesseract OCR: 5.3.4
- ShellCheck

Fontos szolgáltatásállapot:

- Docker daemon socket elérhető a `bober` user számára.
- A `bober` user a `docker` csoport tagja.
- `docker ps` hiba nélkül lefut.
- Docker Compose development runtime létrejött.
- PostgreSQL konténer fut és healthy:
  `boberdetective-postgres`, `postgres:16`, `127.0.0.1:5432`.
- PostgreSQL kliens kapcsolat sikeres:
  database `boberdetective`, user `boberdetective`.
- Qdrant konténer fut:
  `boberdetective-qdrant`, `qdrant/qdrant:v1.15.5`, `127.0.0.1:6333`.
- Qdrant HTTP endpoint válaszol.
- Tesseract nyelvek: `eng`, `hun`, `osd`.

Értékelés:

Az első backend scaffold Python/FastAPI irányban elindítható. PostgreSQL és Qdrant konténeres fejlesztői runtime már működik.

## 7. Python projektállapot

Létrejött:

- `.venv`,
- `pyproject.toml`,
- `.env.example`,
- minimális FastAPI alkalmazáskód,
- health endpoint,
- config loader,
- JSONL audit writer váz,
- secure storage path resolver,
- tesztstruktúra.

Telepített Python csomagok a `.venv` alatt:

- `fastapi`,
- `uvicorn`,
- `pytest`,
- `httpx`,
- `sqlalchemy`,
- `psycopg`,
- `alembic`,
- tranzitív runtime függőségek.

Értékelés:

Az első scaffold elkészült. A health endpoint működik, a storage path traversal teszt sikeres, és az első DB migration foundation alkalmazva van.

## 8. LM Studio elérés WSL felől

Tesztelt endpointok:

```text
http://127.0.0.1:1234/v1/models
http://172.27.48.1:1234/v1/models
```

Eredmény:

- `127.0.0.1:1234`: elérhető
- WSL gateway `172.27.48.1:1234`: timeout

Elérhető modellek az ellenőrzéskor:

- `qwen/qwen3.5-9b`
- `meta-llama-3.1-8b-instruct`
- `text-embedding-nomic-embed-text-v1.5`

Értékelés:

LM Studio jelenleg elérhető WSL felől a localhost címen. A backend `LLMProvider` absztrakciója létrejött, és a model-list smoke endpoint sikeresen ellenőrzi a lokális provider elérhetőségét.

Ellenőrzött backend smoke:

- Endpoint: `GET /api/v1/system/llm/smoke`
- Provider: `lm_studio`
- Base URL: `http://127.0.0.1:1234/v1`
- Configured chat model: `meta-llama-3.1-8b-instruct`, available
- Configured embedding model: `text-embedding-nomic-embed-text-v1.5`, available

Későbbi teendő:

- Chat completion endpoint tényleges válaszformátumának ellenőrzése.
- Embedding endpoint tényleges válaszformátumának ellenőrzése.

## 9. Első implementációt blokkoló hiányok

Jelenleg nem blokkolja az első backend/import alapokat:

- Docker daemon access működik a `bober` userrel.
- PostgreSQL fut Docker Compose-on keresztül.
- Qdrant fut Docker Compose-on keresztül.
- Tesseract `hun` nyelvi adat elérhető.

Később külön ellenőrizendő:

- Docling és HuSpaCy integráció tényleges telepítése/tesztje.
- LM Studio chat és embedding endpointok válaszformátuma.
- Vektoros indexelés első Qdrant smoke tesztje.

## 10. Biztonságos fejlesztési baseline

A saját kódot secure-by-default szemlélettel kell írni.

## 10.1 SQL injection védelem

Szabályok:

- Ne legyen user inputból összefűzött SQL.
- ORM vagy paraméterezett query használata kötelező.
- Dinamikus filtereknél allowlist alapú mezőválasztás kell.
- Raw SQL csak indokolt esetben, paraméterezve és teszttel.

## 10.2 XSS védelem

Szabályok:

- Frontendben user/document/LLM eredetű szöveg nem kerülhet raw HTML-ként renderelésre.
- Markdown exportnál escape/sanitize szabály kell.
- HTML exportnál explicit HTML escaping kell.
- LLM output nem tekinthető biztonságos HTML-nek.

## 10.3 SSTI védelem

Szabályok:

- Template-be user input csak adatként kerülhet, template forrásként nem.
- Export template-ek csak repo által kontrollált fájlok lehetnek.
- LLM output nem válhat template kóddá.

## 10.4 Command injection védelem

Szabályok:

- Alkalmazáskódból shell-hívást kerülni kell.
- Ha külső tool kell, `subprocess` list argumentumokkal, shell nélkül.
- User input soha nem kerülhet parancssorba escape nélküli stringként.
- Fájlútvonalakat canonicalizálni kell.

## 10.5 Path traversal védelem

Szabályok:

- Minden fájlelérés data rooton belül maradjon.
- User által adott fájlnév nem használható közvetlen tárolási útvonalként.
- Storage path generálása UUID/document id alapján történjen.
- `..`, abszolút path és symlink követés ellen védekezni kell.

## 10.6 File upload védelem

Szabályok:

- Fájlméret limit kell.
- MIME/kiterjesztés ellenőrzés kell, de egyik sem önmagában megbízható.
- Eredeti fájl immutable storage alá kerül.
- Importált fájl nem futtatható kódként.
- Parser/OCR hibák kontrollált hibává alakuljanak, ne stack trace szivárgássá.

## 10.7 LLM output trust boundary

Szabályok:

- LLM output nem trusted.
- JSON schema validáció kötelező.
- Source quote validáció kötelező.
- LLM output nem írhat felül eredeti forrást.
- LLM output nem kerülhet közvetlenül SQL-be, shellbe, HTML-be vagy template-be.

## 10.8 Audit és sensitive data

Szabályok:

- Audit legyen elég részletes a rekonstruálhatósághoz.
- Secret, API key, teljes környezeti változólista nem kerülhet auditba.
- Prompt/context tárolásnál később külön dönteni kell, mennyi érzékeny szöveg kerüljön tartós auditba.
- Export minden esetben auditált legyen.

## 10.9 Dependency kezelés

A függőségek számából eredő kitettség elfogadott gyakorlati kockázat, de:

- dependency verziókat rögzíteni kell,
- ne legyen indokolatlan dependency,
- fejlesztési és runtime dependency legyen elkülönítve,
- később bevezethető `pip-audit` vagy hasonló ellenőrzés.

## 11. Javasolt következő lépés

Következő gyakorlati lépés:

```text
Első implementációs sprint folytatása.
```

Elkészült az első sprintből:

- Python/FastAPI scaffold,
- `.env.example`,
- alap health endpoint,
- biztonságos config loader,
- audit service váz,
- storage path resolver path traversal védelemmel,
- SQLAlchemy/psycopg DB layer,
- Alembic migration foundation,
- users/cases/case_users/audit_events táblák,
- case create/list API,
- DB + JSONL audit case creation esetén,
- document/page/chunk SQLAlchemy modellek,
- `0002_documents_pages_chunks` Alembic migráció,
- documents/document_pages/document_chunks táblák constraint-ekkel és FTS indexekkel,
- immutable TXT import API,
- document list és document page list API,
- document chunks list API,
- TXT import DB + JSONL audittal,
- TXT import közbeni determinisztikus `char_window_v1` chunkolás,
- TXT import méretlimit, content-type/kiterjesztés és UTF-8 validáció,
- keyword search API PostgreSQL full-text search alapon,
- keyword search page/chunk source azonosítókkal és plain-text quote-tal,
- source-reference tábla és API quote validációval,
- source-reference DB + JSONL audit,
- LLMProvider absztrakció LM Studio/OpenAI-kompatibilis model-list smoke-kal,
- analysis run provenance táblák és lifecycle audit,
- synthetic LLM benchmark script modell-összehasonlításhoz,
- minimális pytest ellenőrzés.

Teszt eredmény:

```text
29 passed
```

Következő implementációs scope:

1. Source-cited analysis modulok bővítése az elkészült `extract_claims` és `extract_events` modulokon túl.
2. Export format expansion.

LLM benchmark megjegyzés:

- OpenAI-compatible `/v1/chat/completions` módban a `qwen/qwen3.5-9b` reasoning token viselkedés miatt nem adott használható final `content` mezőt.
- LM Studio native `/api/v1/chat` módban, `reasoning: "off"` paraméterrel a végső mérésben a `qwen/qwen3.5-9b` `12/12` benchmark pontot ért el 18.3s alatt.
- Ugyanebben a benchmarkban a `meta-llama-3.1-8b-instruct` `10/12` pontot ért el 6.2s alatt.
- Következtetés: Qwen a jobb első minőségi jelölt source-cited analysis smoke-hoz, ha native API + reasoning off útvonalon hívjuk; Llama gyors kontroll/fallback modell.
- LM Studio native API-n a helyes tokenlimit mező `max_output_tokens`; `maxTokens` hibás.
- Érzékeny iratoknál `store: false` ajánlott.
- A `system_prompt` mező használata tisztább, mint a system/user szöveg kézi összefűzése.
- `reasoning: "off"` csak reasoning-et támogató modelleknél küldhető; Llama esetén hibát ad.
- First source-cited analysis smoke endpoint elkészült: keyword retrieval -> analysis_run inputs -> Qwen native reasoning-off -> quote validation -> source_reference -> analysis_run output.
- Claim persistence foundation elkészült: `claims` és `claim_sources` táblák, claim list/detail API, source-cited smoke claim mentéssel.
- Élő smoke eredmény: `analysis 200`, `validation_status=passed`, claim persisted, 1 source, `source_validation_status=source_valid`.
- Claim review workflow foundation elkészült: `human_reviews` append-only tábla, claim review API, verify/reject/mark_needs_review/comment akciók.
- Élő review smoke eredmény: claim `verified`, review history count 1, `claim_review_recorded` audit esemény.
- Generalizált analysis module endpoint elkészült: `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}`.
- Első támogatott modul: `extract_claims`, keyword chunk retrieval -> LM Studio native -> idézet-validáció -> source_reference -> claim persistence -> analysis_run outputs.
- Második támogatott modul: `extract_events`, keyword chunk retrieval -> LM Studio native -> idézet-validáció -> source_reference -> event persistence -> analysis_run outputs.
- Keyword search prefix `to_tsquery` használatra váltott sanitizált query termekkel, hogy magyar toldalékos egyszerű esetekben kevésbé legyen törékeny.
- Case review report endpoint elkészült: `GET /api/v1/cases/{case_id}/review-report`, claim/event/source/review overview olvasási réteggel.
- Élő review report smoke eredmény: `report 200`, 3 total item, 3 `needs_review`, minden itemhez 1 source.
- JSON review report export foundation elkészült: `exports` és `export_items` táblák, export create/list/detail/download endpointok.
- Export fájlok a case export könyvtár alá kerülnek, SHA256 hash-sel és `export_created` audit eseménnyel.
- Élő export smoke eredmény: `export 201`, 3 export item, JSON download `200`.
- Export review workflow foundation elkészült: `POST /api/v1/cases/{case_id}/exports/{export_id}/reviews`.
- Export review append-only `human_reviews` rekordokat és `export_review_recorded` audit eseményt ír.
- Élő export review smoke eredmény: `review 200`, 1 review, `verified`.
- HTML review report export foundation elkészült ugyanazon export API-n keresztül, `export_type=html` paraméterrel.
- HTML export minden item/source/review szöveget escape-el, XSS regressziós teszttel.
- Élő HTML export smoke eredmény: `export 201`, 3 export item, `.html` fájl, download `200`, `text/html`.
- Event review workflow foundation elkészült: `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`.
- Event review `events.review_status` mezőt frissít, append-only `human_reviews` rekordot és `event_review_recorded` audit eseményt ír.
- Élő event review smoke eredmény: `review 200`, event `verified`, review history count 1.
- Shared review service helper elkészült: claim/event/export review mapping, review history listázás, append-only review rekord és audit írás közös helperből történik.
- Entity persistence foundation elkészült: `entities` és `entity_mentions` táblák.
- `extract_entities` analysis module elkészült source reference + mention alapon.
- Élő `extract_entities` smoke eredmény: `analysis 200`, 2 person entity, 2 mention, source reference kapcsolattal.
- Entity review workflow foundation elkészült: `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`.
- Entity review `entities.review_status` mezőt frissít, append-only `human_reviews` rekordot és `entity_review_recorded` audit eseményt ír.
- Élő entity review smoke eredmény: `review 200`, entity `verified`, review history count 1.
- Entity elemek bekerültek a case review reportba és a JSON/HTML review report exportokba is, mention/source_reference kapcsolaton keresztül.
- Élő entity report/export smoke eredmény: `report 200`, 2 entity item source-szal; HTML export `201`, 2 entity export item.
- Richer review report filtering elkészült: `object_type`, `review_status`, és `source_validation_status` query filterek a review report endpointon.
- JSON/HTML review report exportoknál `report_filters` payload mezővel ugyanaz a szűrés rögzíthető az export paraméterei és metadata tartalma között.
- Élő filtered report/export smoke eredmény: entity-only, `needs_review`, `source_valid` report `200`, JSON export `201`, 2 entity export item.
- Source/reference detail expansion elkészült a review report source objektumokban: dokumentum fájlnév/SHA256, quote offsetek, chunk/page metaadatok és kontrollált hosszúságú forrásszöveg excerpt.
- JSON/HTML exportok ugyanezeket a source detail mezőket viszik tovább; a HTML export továbbra is escape-el minden document/LLM/user eredetű szöveget.
- Analysis module service cleanup elkészült: a közös retrieval/JSON segédek külön fájlba kerültek, a claim/event/entity/summary modulok pedig saját service fájlokat kaptak. Az `analysis_modules.py` vékony public façade maradt.
- Summary item foundation elkészült: `summary_items` és `summary_item_sources` táblák, list/create/detail/review API, append-only `summary_item` review workflow, és review report inclusion.
- `summarize_case` analysis module foundation elkészült: keyword chunk retrieval -> LM Studio native -> quote validation -> source_reference -> summary_item persistence.
- Analysis module retrieval fallback elkészült: az eredeti query mellett normalizált lényegi kifejezéscsoportot és egyedi normalizált magyar kulcsszavakat is próbál.
- Élő `summarize_case` smoke eredmény: a korábban elbukó bő/ékezetes query a fallback után `analysis 200`, `validation_status=passed`, 3 summary item, mind `needs_review` és `source_valid`; review report `object_type=summary_item` 3 elemet adott vissza.
- Contradiction candidate foundation elkészült: `contradiction_candidates` és `contradiction_candidate_sources` táblák, list/create/detail/review API, append-only `contradiction_candidate` review workflow, és review report inclusion.
- `detect_contradiction_candidates` analysis module foundation elkészült: source-cited claim inputs -> LM Studio native -> claim label validation -> contradiction_candidate persistence.
- Élő `detect_contradiction_candidates` smoke eredmény: két eltérő telefonhívás-időpontot tartalmazó TXT mintából `extract_claims` 2 claimet hozott létre, contradiction detection `analysis 200`, `validation_status=passed`, 1 `time_conflict` candidate, 2 source reference, review report inclusion.
- Missing item candidate foundation elkészült: `missing_item_candidates` és `missing_item_candidate_sources` táblák, list/create/detail/review API, append-only `missing_item_candidate` review workflow, és review report inclusion.
- `detect_missing_items` analysis module foundation elkészült: keyword chunk retrieval -> LM Studio native -> quote validation -> source_reference -> missing_item_candidate persistence.
- Élő `detect_missing_items` smoke eredmény: hivatkozott mellékletet/fotódokumentációt tartalmazó TXT mintából `analysis 200`, `validation_status=passed`, 2 `attachment` candidate, review report inclusion.
- Missing item candidate export smoke eredmény: JSON és HTML review report export `object_type=missing_item_candidate`, `needs_review`, `require_source_valid=true` beállításokkal 1-1 export itemet hozott létre, és a letöltések tartalmazták a `missing_item_candidate` elemet.
- Analysis retrieval fallback finomítás elkészült: rövid magyar tárgyragos alakok, például `mellekletet` és `kamerafelvetelt`, vissza tudnak esni `melleklet` és `kamerafelvetel` kulcsszavakra.
- Élő rövid-query smoke eredmény: a korábban elbukó `Keress hivatkozott mellekletet.` lekérdezés `analysis 200`, `validation_status=passed`, 1 source-cited `attachment` candidate.
- Minimal React/Vite frontend scaffold elkészült `frontend/` alatt. A dev szerver `/api` proxyval kapcsolódik a lokális backendhez, backend CORS lazítás nélkül.
- Frontend review actions elkészültek allowlistelt objektumtípus -> review endpoint térképpel.
- Frontend build ellenőrzés: `npm run build` sikeres.

Adatbázis és Docker döntés:

Docker telepítve van és a `bober` user hozzáfér. PostgreSQL és Qdrant Docker Compose-on keresztül fut. Az alkalmazott migrációs állapot: `0012_missing_item_candidates`.

## 12. WSL stabilitási megjegyzés

A Docker Compose első indítása után több `wsl.exe` folyamat beragadt, és a WSL átmenetileg nem válaszolt még egyszerű parancsra sem.

Megoldás:

- Windows oldalról a beragadt `wsl.exe` folyamatok kényszerített leállítása megtörtént.
- Ezután WSL újra válaszolt.
- A tesztek újra lefutottak.
- PostgreSQL és Qdrant konténerek továbbra is elérhetők.

Ellenőrzött állapot:

```text
pytest: 96 passed
postgres: healthy, select 1 OK
qdrant: HTTP endpoint OK
lm_studio: model-list smoke OK
```
