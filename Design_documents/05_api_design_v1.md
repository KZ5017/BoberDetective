# Lokális Nyomozati Iratintelligencia Rendszer
## API design v1

## 1. Cél

Ez a dokumentum az MVP-1 backend API tervét írja le.

Az API célja nem egy chatbot kiszolgálása, hanem egy case analysis workbench működtetése:

- ügyek kezelése,
- dokumentumok importálása és feldolgozása,
- oldalak és chunkok keresése,
- forráshivatkozott elemzések indítása,
- AI-outputok validálása és emberi review-ja,
- auditálható exportok létrehozása.

Az API minden tervezési döntésénél érvényes alapelv:

> No source -> no claim.

## 2. API alapelvek

## 2.1 Lokális és zárt működés

Az MVP API lokális FastAPI backendként fusson WSL2 Ubuntu alatt.

Az API ne tartalmazzon felhőszolgáltatás-függőséget. Az LLM hívások kizárólag az `LLMProvider` absztrakción keresztül történjenek, fejlesztésben LM Studio OpenAI-kompatibilis lokális API-val.

## 2.2 Forráshivatkozás központi szerepe

AI-outputot létrehozó vagy módosító API műveleteknél kötelező legyen:

- `analysis_run_id`,
- legalább egy source kapcsolat az output típusának megfelelő kapcsolótáblán keresztül,
- `source_validation_status`,
- `review_status`.

Az API ne adjon vissza forrás nélküli állítást végleges vagy exportálható objektumként.

## 2.3 Emberi review külön művelet

Az AI-output létrehozása és az emberi elfogadás külön API művelet legyen.

Az AI csak javaslatot hoz létre. Az emberi döntés:

- `human_reviews` rekordot hoz létre,
- frissíti az érintett objektum aktuális `review_status` mezőjét,
- audit eseményt ír.

## 2.4 Explicit audit

Minden fontos API művelet írjon explicit audit eseményt:

- ügy létrehozása,
- dokumentum import,
- parsing/OCR/chunking indítása,
- keresés,
- retrieval,
- LLM analysis run,
- source validation,
- review,
- export.

Az MVP-ben ne legyen trigger-alapú audit az első körben.

## 3. Verziózás és alapútvonal

Javasolt API prefix:

```text
/api/v1
```

Példa:

```text
GET /api/v1/cases
POST /api/v1/cases/{case_id}/documents
POST /api/v1/cases/{case_id}/analysis/extract-claims
```

## 4. Közös válasz- és hibaforma

## 4.1 Sikeres objektumválasz

```json
{
  "data": {},
  "meta": {
    "request_id": "...",
    "generated_at": "2026-05-10T12:00:00Z"
  }
}
```

## 4.2 Lista válasz

```json
{
  "data": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 123
  },
  "meta": {
    "request_id": "..."
  }
}
```

## 4.3 Hiba válasz

```json
{
  "error": {
    "code": "source_validation_failed",
    "message": "The claim cannot be exported because at least one source reference is invalid.",
    "details": {}
  },
  "meta": {
    "request_id": "..."
  }
}
```

## 4.4 Fontos hibakódok

- `not_found`
- `permission_denied`
- `validation_error`
- `case_closed`
- `document_processing_failed`
- `analysis_run_failed`
- `source_required`
- `source_validation_failed`
- `review_required`
- `export_gate_failed`
- `provider_unavailable`

## 5. Auth és jogosultság MVP-ben

MVP-ben egyszerű felhasználó- és szerepkörkezelés elég:

- globális szerep: `users.role`,
- ügyön belüli szerep: `case_users.case_role`.

Javasolt szerepek:

- `admin`,
- `analyst`,
- `reviewer`,
- `viewer`.

Jogosultsági alapelv:

- `viewer`: olvasás, keresés,
- `analyst`: dokumentumimport, elemzések indítása,
- `reviewer`: AI-output review, javítás, elfogadás, elutasítás,
- `admin`: felhasználók, ügyhozzáférés, override műveletek.

Az API design most nem ír elő konkrét auth technológiát. Fejlesztési MVP-ben session vagy egyszerű lokális token is elég lehet, de minden auditált művelethez konkrét `user_id` kell.

## 6. Fő erőforráscsoportok

## 6.1 Cases

### Endpoints

```text
GET    /api/v1/cases
POST   /api/v1/cases
GET    /api/v1/cases/{case_id}
PATCH  /api/v1/cases/{case_id}
POST   /api/v1/cases/{case_id}/close
POST   /api/v1/cases/{case_id}/archive
```

### Megjegyzés

Minden case-bound lekérdezésnél case-level jogosultsági ellenőrzés kell.

## 6.2 Case users

### Endpoints

```text
GET    /api/v1/cases/{case_id}/users
POST   /api/v1/cases/{case_id}/users
PATCH  /api/v1/cases/{case_id}/users/{user_id}
DELETE /api/v1/cases/{case_id}/users/{user_id}
```

### Megjegyzés

A jogosultságváltozások audit eseményt írnak.

## 6.3 Documents

> **Aktualis megjegyzes, 2026-05-17:** a dokumentum API eredeti tervehez kepest a PDF feldolgozas explicit text-review/chunkolas workflow-ra valtott. Import/OCR utan current oldalak jonnek letre, de chunkok csak kulon `POST /api/v1/cases/{case_id}/documents/{document_id}/chunks` hivassal keszulnek. Az import oldalon a szabad szoveges `document_type` kivezetesre kerult; helyette strukturalt `document_group_code` / `document_type_code` mezok vannak. Reszletek: `Design_documents/06_document_processing_pipeline_v1.md` es `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`.

### Endpoints

```text
GET    /api/v1/cases/{case_id}/documents
POST   /api/v1/cases/{case_id}/documents
GET    /api/v1/cases/{case_id}/documents/{document_id}
GET    /api/v1/cases/{case_id}/documents/{document_id}/pages
GET    /api/v1/cases/{case_id}/documents/{document_id}/pages/{page_number}
GET    /api/v1/cases/{case_id}/documents/{document_id}/chunks
POST   /api/v1/cases/{case_id}/documents/{document_id}/process
```

### Import request

`POST /documents` multipart form:

```text
file
document_group_code
document_type_code
language_code
notes
```

### Import response

```json
{
  "data": {
    "document_id": "...",
    "case_id": "...",
    "original_filename": "vallomas.pdf",
    "sha256_hash": "...",
    "processing_status": "pending"
  }
}
```

### Processing request

```json
{
  "steps": ["parse", "ocr_if_needed", "chunk", "embed"],
  "parser_profile": "docling_default_v1",
  "chunking_strategy": "paragraph_window_v1"
}
```

### Megjegyzés

A feldolgozás indítása `analysis_runs` rekordot hoz létre. A page és chunk rekordok verziózottak; újrafeldolgozás nem írhatja felül nyomtalanul a korábbi szöveget.

## 6.4 Search és retrieval

### Endpoints

```text
POST /api/v1/cases/{case_id}/search/keyword
POST /api/v1/cases/{case_id}/search/vector
POST /api/v1/cases/{case_id}/search/hybrid
```

### Hybrid search request

> **Aktualis megjegyzes, 2026-05-17:** a `document_type` filter kivezetesre kerult. A jelenlegi irany a strukturalt dokumentumcsoport/tipus/dokumentumlista alapu szures. Oldaltartomany csak pontosan egy kivalasztott dokumentumnal ertelmezheto. Reszletek: `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`.

```json
{
  "query": "2024. március 12 telefonhívás",
  "filters": {
    "document_ids": [],
    "document_group_code": null,
    "document_type_code": null,
    "page_start": null,
    "page_end": null
  },
  "limit": 20,
  "include_quotes": true
}
```

### Hybrid search response

```json
{
  "data": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "document_name": "hivaslista.pdf",
      "page_start": 14,
      "page_end": 14,
      "quote": "...",
      "score": 0.91,
      "match_type": "keyword_and_vector"
    }
  ]
}
```

### Megjegyzés

Retrieval eredményt LLM analysis run esetén menteni kell `analysis_run_inputs` vagy audit payload formában.

## 6.5 Source references

### Endpoints

```text
GET  /api/v1/cases/{case_id}/source-references/{source_reference_id}
POST /api/v1/cases/{case_id}/source-references/validate
```

### Validation request

```json
{
  "source_reference_ids": ["..."]
}
```

### Validation szabályok

Az API validálja:

- a source reference létezik,
- ugyanahhoz az ügyhöz tartozik,
- dokumentumra mutat,
- `page_id` vagy `chunk_id` van, kivéve `document_metadata` esetén,
- a `quote_text` megtalálható a page vagy chunk szövegében, ha idézetalapú source.

## 6.6 Analysis runs

### Endpoints

```text
GET  /api/v1/cases/{case_id}/analysis-runs
GET  /api/v1/cases/{case_id}/analysis-runs/{analysis_run_id}
POST /api/v1/cases/{case_id}/analysis-runs/{analysis_run_id}/cancel
```

### Analysis run response

```json
{
  "data": {
    "id": "...",
    "case_id": "...",
    "run_type": "extract_claims",
    "status": "succeeded",
    "provider_type": "lm_studio",
    "model_name": "...",
    "prompt_template_version": "claims_v1",
    "validation_status": "passed",
    "started_at": "...",
    "finished_at": "..."
  }
}
```

## 6.7 Structured analysis

### Endpoints

```text
POST /api/v1/cases/{case_id}/analysis/extract-entities
POST /api/v1/cases/{case_id}/analysis/extract-events
POST /api/v1/cases/{case_id}/analysis/extract-claims
POST /api/v1/cases/{case_id}/analysis/detect-contradictions
POST /api/v1/cases/{case_id}/analysis/detect-missing-items
POST /api/v1/cases/{case_id}/analysis/summarize-case
POST /api/v1/cases/{case_id}/analysis/answer-with-citations
```

### Common analysis request

> **Aktualis megjegyzes, 2026-05-17:** ez az eredeti altalanos contract. A raw-chunk modulok jelenlegi request modellje mar `source_mode = case | document`, kotelezo fokuszszoveg, `max_chunks` es `batch_size` mezokkel dolgozik; a regi `limit` es `focused_query` forraskor megszunt. Az ellentmondas modul kulon `contradiction_candidate_limit` mezot hasznal es claim-parokon dolgozik, nem nyers chunkokon. Reszletek: `Design_documents/10_analysis_batch_processing_plan.md`.

```json
{
  "scope": {
    "document_ids": [],
    "chunk_ids": [],
    "query": null
  },
  "retrieval": {
    "strategy": "hybrid_v1",
    "limit": 30
  },
  "model": {
    "provider": "lm_studio",
    "model_id": null,
    "temperature": 0.1
  }
}
```

### Common analysis response

```json
{
  "data": {
    "analysis_run_id": "...",
    "status": "queued"
  }
}
```

### Megjegyzés

Az analysis endpointok lehetnek aszinkronok. Az első válasz csak a futást regisztrálja. A létrejött objektumokat később az adott objektumtípus endpointjai adják vissza.

## 6.8 Entities és mentions

### Endpoints

```text
GET /api/v1/cases/{case_id}/entities
GET /api/v1/cases/{case_id}/entities/{entity_id}
GET /api/v1/cases/{case_id}/entities/{entity_id}/mentions
```

### Megjegyzés

Az entity forrásalapja a mention. Az API ne jelenítse meg úgy az entity rekordot, mintha egyetlen forrás önmagában igazolná az összevont kanonikus entitást.

## 6.9 Events

### Endpoints

```text
GET /api/v1/cases/{case_id}/events
GET /api/v1/cases/{case_id}/events/{event_id}
GET /api/v1/cases/{case_id}/timeline
```

### Lista filterek

- `review_status`
- `source_validation_status`
- `event_type`
- `time_from`
- `time_to`
- `entity_id`

## 6.10 Claims

### Endpoints

```text
GET /api/v1/cases/{case_id}/claims
GET /api/v1/cases/{case_id}/claims/{claim_id}
```

### Lista filterek

- `review_status`
- `source_validation_status`
- `claim_type`
- `speaker_entity_id`
- `subject_entity_id`
- `related_event_id`

## 6.11 Contradiction candidates

### Endpoints

```text
GET /api/v1/cases/{case_id}/contradiction-candidates
GET /api/v1/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}
```

### Megjegyzés

Az API mindenütt jelölje, hogy ezek figyelemfelhívó jelöltek, nem végleges megállapítások.

## 6.12 Missing item candidates

### Endpoints

```text
GET /api/v1/cases/{case_id}/missing-item-candidates
GET /api/v1/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}
```

### Megjegyzés

Ezek sem bizonyított hiányok, hanem ellenőrizendő jelöltek.

## 6.13 Summary items

### Endpoints

```text
GET /api/v1/cases/{case_id}/summary-items
GET /api/v1/cases/{case_id}/summary-items/{summary_item_id}
```

### Megjegyzés

Az ügyösszefoglaló több review-zható, forráshivatkozott elemből álljon, ne egyetlen nem strukturált szövegből.

## 6.14 Human review

### Endpoints

```text
POST /api/v1/cases/{case_id}/reviews
GET  /api/v1/cases/{case_id}/reviews
GET  /api/v1/cases/{case_id}/reviews/{review_id}
```

### Review request

```json
{
  "object_type": "claim",
  "object_id": "...",
  "action_type": "verify",
  "new_review_status": "verified",
  "review_comment": "Forrás ellenőrizve.",
  "correction_patch_json": null
}
```

### Megjegyzés

Review csak támogatott objektumtípusra történhet:

- `entity`,
- `event`,
- `claim`,
- `contradiction_candidate`,
- `missing_item_candidate`,
- `summary_item`,
- `source_reference`,
- `export`.

## 6.15 Exports

### Endpoints

```text
GET  /api/v1/cases/{case_id}/exports
POST /api/v1/cases/{case_id}/exports
GET  /api/v1/cases/{case_id}/exports/{export_id}
GET  /api/v1/cases/{case_id}/exports/{export_id}/download
```

### Export request

```json
{
  "export_type": "markdown",
  "export_scope": "custom_bundle",
  "review_filter": "verified_only",
  "require_source_valid": true,
  "object_selection": [
    {
      "object_type": "summary_item",
      "object_id": "..."
    }
  ]
}
```

### Export gate

Alapértelmezés:

- csak `review_status = verified`,
- csak `source_validation_status = source_valid`,
- minden exportált objektum kerüljön az `export_items` táblába,
- minden export auditált.

Admin override lehetséges később, de csak explicit paraméterrel és audit eseménnyel.

## 6.16 Audit

### Endpoints

```text
GET /api/v1/cases/{case_id}/audit-events
GET /api/v1/audit-events
```

### Filterek

- `case_id`,
- `user_id`,
- `analysis_run_id`,
- `event_type`,
- `related_object_type`,
- `related_object_id`,
- `time_from`,
- `time_to`,
- `success`.

### Megjegyzés

A globális audit endpoint admin szerepkörhöz kötött legyen. Case-szintű auditot csak az ügyhöz jogosult felhasználó láthasson.

## 6.17 Provider health

### Endpoints

```text
GET /api/v1/system/health
GET /api/v1/system/providers/llm
GET /api/v1/system/providers/embedding
```

### LLM provider response

```json
{
  "data": {
    "provider": "lm_studio",
    "base_url_configured": true,
    "reachable": true,
    "model": "...",
    "supports_embeddings": false
  }
}
```

### Megjegyzés

Ezek az endpointok nem adhatnak vissza érzékeny titkokat vagy teljes API kulcsokat.

## 7. Aszinkron feldolgozás

Dokumentumfeldolgozás és LLM elemzés aszinkron legyen.

Javasolt állapotok:

```text
queued
running
succeeded
failed
cancelled
```

Az indító endpointok `analysis_run_id`-t adnak vissza. A frontend pollinggal vagy később WebSocket/SSE kapcsolattal követheti az állapotot.

MVP-ben polling elég:

```text
GET /api/v1/cases/{case_id}/analysis-runs/{analysis_run_id}
```

## 8. Source validation pipeline

Minden AI-output létrehozása után fusson source validation.

Validálandó:

1. Van-e kötelező source kapcsolat.
2. A source reference létezik-e.
3. A source reference azonos case-hez tartozik-e.
4. A source reference dokumentuma létezik-e.
5. Idézetalapú source esetén a quote megtalálható-e a page vagy chunk szövegében.
6. A kapcsolt output `created_by_analysis_run_id` mezője létezik-e.

Eredmény:

- `pending_source_validation`,
- `source_valid`,
- `source_invalid`.

## 9. API és adatmodell kapcsolat

Az API ne rejtse el a provenance mezőket a szakmai felhasználói felületek elől.

Listákban röviden, részletes nézetben teljesen jelenjen meg:

- `created_by_analysis_run_id`,
- `source_validation_status`,
- `review_status`,
- kapcsolt source reference-ek,
- confidence,
- audit és review előzmények.

## 10. Első implementációs sorrend API szinten

Javasolt sorrend:

1. Health és provider config ellenőrző endpointok.
2. Users/cases/case_users minimális API.
3. Document import és document list API.
4. Document processing indítása és analysis run státusz API.
5. Page/chunk olvasó API.
6. Keyword/hybrid search API.
7. Source reference és source validation API.
8. Claims/events/entities read API.
9. Analysis indító endpointok.
10. Human review API.
11. Summary item API.
12. Export API.
13. Audit event API.

## 11. Tudatosan későbbre hagyva

MVP API v1-ben nem szükséges:

- teljes enterprise permission modell,
- külső rendszerintegráció,
- jogszabályi RAG endpointok,
- graph analytics API,
- chat-first API,
- real-time collaboration,
- automatikus jogi minősítési endpoint.

## 12. Rövid összegzés

Az API v1 fő feladata, hogy a dokumentumfeldolgozó és elemző magot auditálható, forráshivatkozott, ember által review-zható műveletekké szervezze.

A legfontosabb API-szintű kapuk:

1. AI-output nem exportálható forrás nélkül.
2. AI-output nem exportálható emberi review nélkül.
3. Minden elemzési futás `analysis_runs` rekordhoz kötött.
4. Minden fontos művelet audit eseményt ír.
5. Az LLM provider cserélhető marad az `LLMProvider` absztrakció mögött.
