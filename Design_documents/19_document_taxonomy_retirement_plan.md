# 19. Document Taxonomy Retirement Plan

## 0. Mi valtozott

A strukturalt irattaxonomia eredetileg kisebb, kezzel gondozott ugyekhez es importkori besorolashoz hasznosnak tunt.

A nagy ugyes celallapot viszont mas:

```text
5000+ irat / ugy
gyors csoportos import
minel kevesebb importkori adminisztracio
forraskor szukites inkabb konkret iratlista, oldaltartomany, keresesi fokusz,
kesobb teljes iratfeldolgozasbol szarmazo ujrahasznosithato keresesi alapanyag
```

Ebben a modellben az importkori `Iratcsoport` / `Irattipus` valasztas rossz UX:

- lassitja a tomeges importot,
- olyan dontest ker a felhasznalotol, amit sokszor nem akar vagy nem tud meghozni,
- tul eros strukturat ken ra az iratgyujtemenyre,
- frontend oldalon a regi szemleletet kommunikalja.

Cel:

```text
a dokumentumtaxonomia teljes, tiszta, lepcsozetes kivezetese
ugy, hogy kozben ne torjuk el a jelenlegi import/kereses/indexeles workflow-t.
```

## 0.1 Aktualis allapot

Elso implementacios szelet kesz:

- frontend importbol kikerult az `Iratcsoport` / `Irattipus` valasztas,
- iratreszletekbol kikerult a `Besorolas modositasa` blokk,
- elemzesi forraskorbol kikerult az `Iratcsoport szuro` / `Irattipus szuro`,
- frontend API kliens mar nem hivja a `document-taxonomy` endpointot,
- frontend import mar nem kuld `document_group_code` / `document_type_code` mezoket,
- frontend import mar tobb fajlt is tud kijelolni, es ezeket sorban kuldi a jelenlegi egyfajlos backend endpointnak,
- case-scope analysis/index status mar csak konkret `document_ids` szukitest kuld.

Az eddigi implementacios szeletek utan a backend taxonomia endpointok,
request mezok, service szurok, DB/model mezok es search-entry denormalizalt
oszlopok is kikerultek az aktiv mukodesbol.

## 1. Jelenlegi erintett reteg

### 1.1 Frontend

Fajlok:

```text
frontend/src/App.tsx
frontend/src/api.ts
```

Kivezetes elotti elemek:

- import panel:
  - `Iratcsoport`
  - `Irattipus`
- iratreszletek panel:
  - `Besorolas modositasa`
- elemzesi panel:
  - `Iratcsoport szuro`
  - `Irattipus szuro`
- API kliens:
  - `getDocumentTaxonomy`
  - `updateDocumentTaxonomy`
  - `importDocument(..., documentGroupCode, documentTypeCode)`
  - analysis/index status filterekben `document_group_code`, `document_type_code`

### 1.2 Backend API

Fajlok:

```text
app/api/v1/document_taxonomy.py
app/api/v1/documents.py
app/api/v1/search.py
app/api/v1/router.py
```

Jelenlegi elemek:

- `GET /api/v1/document-taxonomy`
- `PATCH /api/v1/cases/{case_id}/documents/{document_id}/taxonomy`
- import form mezok:
  - `document_group_code`
  - `document_type_code`
- index/search query filterek:
  - `document_group_code`
  - `document_type_code`

### 1.3 Backend schema/service

Fajlok:

```text
app/core/document_taxonomy.py
app/schemas/document.py
app/schemas/search.py
app/schemas/analysis_modules.py
app/services/documents.py
app/services/analysis_module_common.py
app/services/analysis_module_findings.py
app/services/search.py
app/services/vector_index.py
app/services/lexical_index.py
```

Jelenlegi elemek:

- `DocumentImportMetadata.document_group_code`
- `DocumentImportMetadata.document_type_code`
- `DocumentTaxonomyUpdateRequest`
- `SearchFilters.document_group_code`
- `SearchFilters.document_type_code`
- `ChunkIndexRequest.document_group_code`
- `ChunkIndexRequest.document_type_code`
- `AnalysisModuleRunRequest.document_group_code`
- `AnalysisModuleRunRequest.document_type_code`
- taxonomia validacio importnal / search/index/analysis filtereknel
- document reclassification service: `update_document_taxonomy`

### 1.4 DB/model

Fajl:

```text
app/models/document.py
```

Jelenlegi mezok:

```text
documents.document_group_code
documents.document_type_code
document_search_entries.document_group_code
document_search_entries.document_type_code
```

Megjegyzes:

A `documents` tabla mezoi nem az elso UI-tisztitasi korben torlendok.
Ezek atmeneti kompatibilitasi mezok maradhatnak `uncategorized / uncategorized` ertekkel,
amig a backend/API takaritas es migracio biztonsagosan vegig nem er.

## 2. Kivezetesi alapelv

Nem eleg a frontend mezok elrejtese.

Helyes sorrend:

```text
1. Felhasznaloi workflow tisztitasa.
2. API bemenetek kompatibilis egyszerusitese.
3. Backend filterek kivezetese.
4. Search/index denormalizalt taxonomia mezok kivezetese.
5. DB oszlopok eltavolitasa vagy belso defaultkent valo veglegesitese.
6. Dokumentacio es tesztek takaritasa.
```

Az elso korben nem szabad egyszerre DB oszlopot torolni, mert:

- a jelenlegi dokumentumok es search-entry sorok erre epulnek,
- a modellekben es tesztekben sok helyen vannak kotelezo mezok,
- a `document_search_entries` friss bevezetett reteg meg stabilizalodik.

## 3. Celallapot

### 3.1 Frontend celallapot

Import panel:

- nincs `Iratcsoport`,
- nincs `Irattipus`,
- fajlvalasztas es import legyen gyors,
- kesobb csoportos fajlkijeloles kerulhet ide.

Iratreszletek:

- nincs `Besorolas modositasa`,
- nem jelenik meg hangsulyos irattaxonomia metadata,
- ha backend atmenetileg meg ad taxonomia labelt, azt nem kell felhasznaloi workflow-kent mutatni.

Elemzesi panel:

- nincs `Iratcsoport szuro`,
- nincs `Irattipus szuro`,
- marad:
  - teljes ugy,
  - kivalasztott irat,
  - konkret iratlista,
  - oldaltartomany csak kivalasztott iratnal,
  - fokuszszoveg,
  - retrieval strategy,
  - szovegresz plafon,
  - batch meret.

### 3.2 Backend celallapot

Import:

- API callernek nem kell `document_group_code` / `document_type_code`,
- backend atmenetileg automatikusan `uncategorized / uncategorized` erteket allit,
- kesobb a mezok teljesen eltavolithatok.

Search/index/analysis:

- taxonomia filter nincs,
- konkret `document_ids` maradhat,
- `document_id` selected-document source mode maradhat,
- oldaltartomany selected-document modban maradhat.

Document taxonomy endpoint:

- vegul torlendo:
  - router,
  - schemas,
  - core registry,
  - tests.

Document reclassification:

- vegul torlendo:
  - endpoint,
  - service,
  - frontend blokk,
  - audit event hasznalat.

### 3.3 DB celallapot

Lehetseges vegso opcio:

```text
documents.document_group_code eltorolve
documents.document_type_code eltorolve
document_search_entries.document_group_code eltorolve
document_search_entries.document_type_code eltorolve
```

Atmeneti opcio:

```text
mezok maradnak, de csak belso, fix uncategorized ertekek
frontend/API nem hasznalja oket
```

Javaslat:

- UI/API/service szinten elobb teljes kivezetes,
- DB oszlopok torlese csak utana, kulon migracioval,
- addig a mezok maradjanak default `uncategorized` erteken.

## 4. Implementacios lepcso

### Lepes 1: Frontend workflow tisztitas

Statusz: kesz.

Feladat:

- import panelbol kivenni:
  - `Iratcsoport`,
  - `Irattipus`,
  - taxonomia leiro hint.
- `importDocument` frontend wrapper ne kerjen taxonomia parametereket.
- `Besorolas modositasa` blokk eltavolitasa az iratreszletekbol.
- analysis source filter panelbol kivenni:
  - `Iratcsoport szuro`,
  - `Irattipus szuro`.
- a konkret iratlista-szuro maradhat.

Elvart eredmeny:

```text
felhasznaloi szinten eltunik az iratkategoria-kotelezettseg.
```

Meg nem torlendo:

- backend taxonomy endpoint,
- DB mezok,
- backend filter mezok.

Indok:

Eloszor a felhasznaloi workflow-t kell a celallapothoz igazitani ugy,
hogy a backend kompatibilitas meg megmarad.

### Lepes 2: Frontend API kliens takaritas

Statusz: reszben kesz.

Feladat:

- `getDocumentTaxonomy` hasznalat eltavolitasa, ha mar nincs olyan UI, ami igenyli. Kesz.
- `updateDocumentTaxonomy` eltavolitasa. Kesz.
- frontend state-ek torlese:
  - `documentTaxonomy`,
  - `documentGroupCode`,
  - `documentTypeCode`,
  - `taxonomyEditGroupCode`,
  - `taxonomyEditTypeCode`,
  - `taxonomyEditComment`,
  - analysis taxonomy filter state-ek. Kesz.
- label helper egyszerusitese:
  - `labelDocumentTaxonomy` eltavolitasa vagy nem hasznalata. Kesz.

Meg marad:

- `DocumentRead` API tipusban a backend altal meg kuldott taxonomia mezok,
- index/status API tipusban a backend kompatibilitasi filter mezok.

Elvart eredmeny:

```text
frontend kodban nem marad hasznalt taxonomia workflow.
```

### Lepes 3: Backend API kompatibilis egyszerusites

Feladat:

- `DocumentImportMetadata` taxonomia mezoi torolve.
- import service tovabbra is defaultoljon:
  - `uncategorized / uncategorized`.
- analysis/search/index request sémákból a taxonomia mezok torolve.

Ellenorzes:

- uj frontend nem kuldi,
- API-bemeneti szerzodes mar nem tartalmaz taxonomia mezoket.

### Lepes 4: Backend filterek kivezetese

Feladat:

- `SearchFilters`-bol torolni:
  - `document_group_code`,
  - `document_type_code`. Kesz.
- `ChunkIndexRequest`-bol torolni:
  - `document_group_code`,
  - `document_type_code`. Kesz.
- `AnalysisModuleRunRequest`-bol torolni:
  - `document_group_code`,
  - `document_type_code`. Kesz.
- kapcsolodo service szuroket torolni:
  - `app/services/search.py`,
  - `app/services/vector_index.py`,
  - `app/services/analysis_module_common.py`,
  - `app/services/analysis_module_findings.py`,
  - `app/api/v1/search.py`. Kesz.

Elvart eredmeny:

```text
forraskor szures csak konkret dokumentumlista / selected-document / oldalrange / fokusz alapon.
```

### Lepes 5: Taxonomy endpoint es reclassification workflow torlese

Feladat:

- torolni:
  - `app/api/v1/document_taxonomy.py`, Kesz.
  - router include, Kesz.
  - `app/core/document_taxonomy.py`, Kesz.
  - `app/schemas/document_taxonomy.py`, Kesz.
  - `DocumentTaxonomyUpdateRequest`, Kesz.
  - `update_document_taxonomy`, Kesz.
  - `PATCH /documents/{document_id}/taxonomy`. Kesz.
- torolni / atirni:
  - `tests/test_document_taxonomy.py`. Kesz.

Elvart eredmeny:

```text
nincs aktiv API vagy service dokumentum taxonomia kezelesre.
```

### Lepes 6: DB es search-entry mezok kivezetese

Csak akkor, ha az elso 5 lepes utan minden teszt zold.

Feladat:

- Alembic migracio:
  - `documents.document_group_code` torlese,
  - `documents.document_type_code` torlese,
  - `document_search_entries.document_group_code` torlese,
  - `document_search_entries.document_type_code` torlese,
  - taxonomia indexek torlese. Kesz: `0037_remove_doc_taxonomy`.
- model frissites. Kesz.
- `document_read_with_labels` label-logikajanak megszuntetese. Kesz.

Elvart eredmeny:

```text
taxonomia nemcsak UI-bol, hanem DB modellbol is eltunik.
```

### Lepes 7: Dokumentacio takaritas

Feladat:

- `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`
  legyen torteneti/retired dokumentumkent kezelve.
- `CURRENT_STATE.md`, `AI_NOTES.md`, `README.md`, `CHANGELOG.md` frissitese. Kesz az aktualis allapotra.
- regi irattaxonomia hivatkozasok eltavolitasa vagy historical note-ra szukitese.

## 5. Tesztelési terv

Minden lepesnel:

```bash
.venv/bin/pytest -q
cd frontend && npm run build
```

Kiemelt regressziok:

- TXT import taxonomia nelkul sikeres.
- PDF import taxonomia nelkul sikeres.
- OCR / chunk creation utan search-entry populacio megmarad.
- keyword search mukodik search-entry alapon.
- hybrid search keyword oldala mukodik.
- analysis selected-document mukodik.
- analysis whole-case konkret document_ids szurovel mukodik.
- taxonomy endpoint eltavolitasa utan frontend build nem hivatkozik ra.

## 6. Mi ne maradjon kódszemétként

Vegso takaritas utan ne maradjon aktiv kodban:

- `documentTaxonomy` frontend state,
- `getDocumentTaxonomy`,
- `updateDocumentTaxonomy`,
- `document-taxonomy` busy label,
- `Besorolas modositasa` blokk,
- importkori `documentGroupCode` / `documentTypeCode`,
- analysis taxonomy filter state-ek,
- `DocumentTaxonomyUpdateRequest`,
- `update_document_taxonomy`,
- `document_taxonomy.py` router,
- `app/core/document_taxonomy.py`,
- taxonomia filterek search/index/analysis requestekben,
- taxonomia denormalizalt mezok `document_search_entries` tablan,
- taxonomy-specifikus tesztek, kiveve torteneti migracios teszt ha indokolt.

## 7. Javasolt kovetkezo konkret lepes

Kovetkezo implementacios szelet:

```text
friss import/search smoke a taxonomy-mentes workflow-val:
TXT import,
PDF import,
chunk creation,
keyword search,
hybrid search,
search_findings.
```

Ez igazolja, hogy a taxonomy DB-s kivezetese utan az uj nagyugyes import es
keresesi irany stabil maradt.
