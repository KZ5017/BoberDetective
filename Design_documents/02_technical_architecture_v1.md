# Lokális Nyomozati Iratintelligencia Rendszer
## Technikai architektúra v1

## 1. Architektúra célja

A technikai architektúra célja egy lokálisan futó, auditálható, forráshivatkozott nyomozati iratfeldolgozó rendszer megtervezése, amely nagy mennyiségű dokumentumból strukturált elemzéseket készít.

A rendszer nem önálló döntéshozó rendszer, hanem iratfeldolgozó, kereső, rendszerező és döntéstámogató eszköz.

Az architektúra elsődleges céljai:

- lokális működés,
- érzékeny adatok védelme,
- dokumentumok pontos feldolgozása,
- forráshivatkozott keresés,
- strukturált elemzések készítése,
- minden generált állítás visszavezethetősége,
- emberi ellenőrzés támogatása,
- auditálhatóság,
- későbbi jogszabályi RAG modul előkészítése.

## 2. Fő rendszerelv

A rendszer egyik alapelve:

> A modell nem igazságforrás, hanem feldolgozó komponens.

Az igazságforrások:

- az eredeti dokumentumok,
- a dokumentumokból kinyert oldalszintű szövegek,
- a forráshivatkozások,
- az audit log,
- az emberi ellenőrzések,
- későbbi fázisban az ellenőrzött jogszabályi korpusz.

A rendszer nem engedi, hogy a nyelvi modell forrás nélküli állításokat tegyen. Minden elemzésnek visszakereshető dokumentumrészletekre kell épülnie.

## 3. Magas szintű adatfolyam

> **Aktualis megjegyzes, 2026-05-17:** az adatfolyam celmodell maradt, de a megvalositott pipeline-ban a PDF import/OCR utan explicit `text_review_required` reteg van: elobb current oldalak keletkeznek, majd a felhasznalo kulon hoz letre chunkokat. A retrieval oldalon a raw-chunk elemzesek mar kotelezo fokuszszoveggel, `case` vagy `document` forraskorrel, `max_chunks` plafonnal, opcionális dokumentum-oldaltartomannyal es keyword/semantic/hybrid moddal dolgoznak. Reszletek: `Design_documents/06_document_processing_pipeline_v1.md` es `Design_documents/10_analysis_batch_processing_plan.md`.

```text
Ügy / iratanyag
  ↓
Dokumentumimport
  ↓
Fájlhash + eredeti fájl megőrzése
  ↓
Dokumentum parsing / OCR
  ↓
Oldalszintű szöveg
  ↓
Chunkolás + metaadatolás
  ↓
Hybrid index
  ├─ kulcsszavas keresés
  └─ szemantikus keresés
  ↓
Reranking / relevancia-rendezés
  ↓
Lokális LLM
  ↓
Strukturált output
  ├─ szereplőlista
  ├─ idővonal
  ├─ állításlista
  ├─ ellentmondásjelöltek
  ├─ hiányjelöltek
  └─ ügyösszefoglaló
  ↓
Forráshivatkozás + audit log + emberi validálás
```

## 4. Fő komponensek

> **Aktualis megjegyzes, 2026-05-17:** a nagy iratmennyisegu ugyek kezelesere kulon dokumentumtaxonomia es strukturalt forrasszuresi terv keszult. Az irattipusokat nem szabad a regi szabad szoveges `document_type` modellre tovabb epiteni; lasd `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`.

A rendszer fő komponensei:

1. Ügykezelő modul
2. Dokumentumimport modul
3. Fájlintegritási modul
4. Dokumentumparser / OCR pipeline
5. Oldalszintű szövegtároló
6. Chunkoló modul
7. Metaadat- és entitáskinyerő modul
8. Kulcsszavas kereső
9. Vektoros kereső
10. Hybrid retrieval réteg
11. Reranker réteg
12. Lokális LLM réteg
13. Strukturált elemzési modulok
14. Forráshivatkozási modul
15. Emberi review workflow
16. Audit log modul
17. Export modul
18. Felhasználói felület

## 5. Ügykezelő modul

Az ügykezelő modul biztosítja, hogy minden adat egy konkrét ügyhöz kapcsolódjon.

Egy ügy önálló munkaterület:

- saját dokumentumokkal,
- saját indexszel,
- saját elemzésekkel,
- saját audit loggal,
- saját jogosultságokkal.

Fő funkciók:

- ügy létrehozása,
- ügy metaadatainak kezelése,
- ügy lezárása / archiválása,
- ügyhöz tartozó dokumentumok listázása,
- ügyhöz tartozó elemzések listázása,
- ügyhöz tartozó exportok kezelése.

MVP-ben minimális ügyadatok:

```text
case_id
case_name
case_reference
created_at
created_by
status
notes
```

## 6. Dokumentumimport modul

A dokumentumimport modul feladata az iratok biztonságos betöltése és nyilvántartásba vétele.

Támogatott MVP formátumok:

- PDF,
- szkennelt PDF,
- DOCX,
- TXT,
- HTML,
- egyszerű e-mail export.

Későbbi formátumok:

- CSV,
- XLSX,
- chat export,
- PST / MBOX,
- képfájlok,
- strukturált hatósági exportok.

Importáláskor rögzítendő:

```text
document_id
case_id
original_filename
stored_filename
mime_type
file_size
sha256
imported_at
imported_by
processing_status
parser_profile
```

Az eredeti fájl változatlan formában megőrzendő.

## 7. Fájlintegritási modul

Minden importált dokumentumhoz kriptográfiai hash értéket kell generálni, javasoltan SHA-256-tal.

Célok:

- eredeti fájl integritásának ellenőrzése,
- duplikált fájlok felismerése,
- későbbi auditálás támogatása,
- bizonyítéki lánc támogatása.

Alapelv:

> Az eredeti dokumentum nem módosítható. Minden feldolgozott forma külön származtatott adatként kezelendő.

## 8. Dokumentumparser / OCR pipeline

A dokumentumfeldolgozó pipeline célja, hogy minden dokumentumból oldalszintű, visszakereshető és hivatkozható szöveget hozzon létre.

### 8.1 Parsing stratégia

A rendszer különbséget tesz:

- natív szöveget tartalmazó PDF,
- szkennelt PDF,
- vegyes PDF,
- DOCX,
- TXT,
- HTML,
- rossz minőségű vagy hibás dokumentum között.

### 8.2 Javasolt komponensek

Elsődleges dokumentumfeldolgozó:

```text
Docling
```

Fallback OCR:

```text
Tesseract OCR magyar nyelvi támogatással
```

MVP-ben javasolt feldolgozási logika:

```text
1. Fájl típusának felismerése
2. Natív szöveg kinyerésének megkísérlése
3. Oldalszintű szöveg ellenőrzése
4. Ha nincs vagy gyenge a szöveg: OCR futtatása
5. OCR eredmény oldalszintű tárolása
6. Parser/OCR confidence értékek mentése, ha elérhetők
7. Hibák és figyelmeztetések naplózása
```

### 8.3 Oldalszintű szövegtárolás

Minden dokumentum minden oldalához külön rekord tartozik.

Minimális mezők:

```text
page_id
document_id
page_number
text
ocr_used
ocr_confidence
parser_name
parser_version
created_at
```

Az oldalszintű tárolás azért fontos, mert a későbbi forráshivatkozásoknál az oldalszám alapvető követelmény.

## 9. Chunkolási stratégia

A chunkolás célja, hogy a dokumentumszöveget olyan kisebb egységekre bontsa, amelyek kereshetők, embeddingelhetők és forráshivatkozhatók.

### 9.1 Chunkolási alapelvek

A chunk ne legyen túl kicsi, mert elveszhet a kontextus.

A chunk ne legyen túl nagy, mert romlik a retrieval pontossága és a modell kontextuskezelése.

MVP javaslat:

```text
chunk_size: 800–1200 token körül
overlap: 100–200 token körül
határ: lehetőleg bekezdés vagy mondathatár
```

### 9.2 Chunk metaadatok

Minden chunkhoz rögzíteni kell:

```text
chunk_id
case_id
document_id
page_start
page_end
chunk_index
text
char_start
char_end
token_count
embedding_id
parser_version
chunker_version
created_at
```

### 9.3 Oldalhatár kezelése

Ha egy chunk több oldalon átível, azt külön jelölni kell:

```text
page_start
page_end
```

Forráshivatkozásnál a rendszernek képesnek kell lennie pontosítani, hogy a releváns idézet melyik oldalon található.

## 10. Metaadat- és entitáskinyerő modul

A rendszernek ki kell nyernie az iratanyagból a fontos entitásokat és azonosítókat.

### 10.1 Kinyerendő entitások

MVP-ben:

- személyek,
- szervezetek,
- helyszínek,
- dátumok,
- időpontok,
- ügyiratszámok,
- telefonszámok,
- e-mail címek,
- rendszámok,
- pénzösszegek,
- dokumentumhivatkozások.

Később:

- bankszámlaszámok,
- IMEI / IMSI,
- IP-címek,
- cellainformációk,
- szerződésszámok,
- ingatlan-azonosítók,
- cégjegyzékszámok,
- adószámok.

### 10.2 Javasolt módszer

A rendszer hibrid entitáskinyerést használjon:

```text
Regex szabályok
+ magyar NLP / NER
+ LLM-alapú normalizálás és validálás
```

Regex alkalmas:

- telefonszám,
- e-mail,
- dátum,
- ügyiratszám,
- rendszám,
- pénzösszeg,
- IP-cím,
- adószám jellegű minták felismerésére.

Magyar NLP alkalmas:

- személynevek,
- szervezetek,
- helyszínek,
- mondathatárok,
- nyelvi szerkezetek felismerésére.

LLM alkalmas:

- névvariációk összevonására,
- szerepkörök becslésére,
- bizonytalan entitások jelölésére,
- entitáskapcsolatok strukturálására.

### 10.3 Javasolt komponens

Magyar NLP réteghez javasolt:

```text
HuSpaCy
```

A HuSpaCy nem helyettesíti az LLM-et, hanem előfeldolgozó és strukturáló rétegként működik.

## 11. Keresési architektúra

A rendszernek nem szabad kizárólag szemantikus vektoros keresésre épülnie.

Nyomozati iratokban sokszor pontos keresésre van szükség:

- név,
- dátum,
- rendszám,
- telefonszám,
- ügyiratszám,
- helyszín,
- dokumentumszám,
- azonosító.

Ezért a rendszer hybrid search architektúrát használ.

## 12. Kulcsszavas kereső

A kulcsszavas kereső célja pontos szövegegyezések, részleges egyezések és strukturált minták megtalálása.

Lehetséges MVP-megoldások:

```text
PostgreSQL full-text search
vagy
OpenSearch későbbi fázisban
```

MVP-ben a PostgreSQL full-text search elegendő lehet, ha az adatmennyiség mérsékelt.

Nagyobb skálán OpenSearch javasolt.

## 13. Vektoros kereső

A vektoros kereső célja szemantikusan hasonló szövegrészek megtalálása.

Javasolt MVP-megoldás:

```text
Qdrant
```

Alternatív MVP-megoldás:

```text
PostgreSQL + pgvector
```

A Qdrant előnye:

- dedikált vektoros keresőmotor,
- jó RAG-integráció,
- tiszta API,
- lokálisan futtatható,
- később skálázható.

A pgvector előnye:

- egyszerűbb deployment,
- kevesebb komponens,
- PostgreSQL-ben marad minden.

Javaslat:

```text
MVP-1: PostgreSQL + Qdrant
Egyszerűsített PoC: PostgreSQL + pgvector
```

## 14. Hybrid retrieval réteg

A hybrid retrieval réteg összevonja:

- kulcsszavas találatokat,
- vektoros találatokat,
- metaadat-szűréseket,
- jogosultsági szűréseket,
- reranker eredményeket.

Példa folyamat:

```text
Felhasználói kérdés vagy elemzési feladat
  ↓
Query normalizálás
  ↓
Kulcsszavas keresés
  ↓
Vektoros keresés
  ↓
Találatok összevonása
  ↓
Duplikátumok eltávolítása
  ↓
Reranking
  ↓
Top N releváns chunk kiválasztása
  ↓
LLM kontextus összeállítása
```

A retrieval outputját minden esetben menteni kell az audit logba.

## 15. Reranker réteg

A reranker célja, hogy a keresési találatokat újrarendezze relevancia szerint.

MVP-ben a reranker opcionális, de erősen javasolt későbbi fázisban.

Reranker nélkül a rendszer is működhet, de több irreleváns chunk kerülhet a modell elé.

MVP-stratégia:

```text
MVP-1A: reranker nélkül
MVP-1B: lokális reranker bevezetése
```

## 16. Lokális LLM réteg

A lokális LLM réteg feladata nem az, hogy saját tudásból válaszoljon, hanem hogy a visszakeresett dokumentumrészletekből strukturált elemzéseket készítsen.

### 16.1 LLM feladatok

A generatív modell fő feladatai:

- ügyösszefoglaló készítése,
- állítások strukturálása,
- események kinyerése,
- idővonal-elemek megfogalmazása,
- potenciális ellentmondások jelzése,
- potenciális hiányok jelzése,
- válaszadás forráshivatkozott kérdésekre,
- entitások normalizálása.

### 16.2 LLM provider absztrakció

A rendszer ne legyen egy konkrét LLM futtatókörnyezethez kötve.

Javasolt interfész:

```text
LLMProvider.generate(prompt, context, schema)
LLMProvider.embed(texts)
LLMProvider.healthcheck()
LLMProvider.model_info()
```

Fejlesztési környezetben:

```text
LM Studio running natively on the Windows 11 host,
exposed through its local OpenAI-compatible API
```

Az MVP fejlesztési alapértelmezett LLM providere LM Studio legyen, ha a lokális szerver stabilan elérhető a WSL/Linux backend felől.

Indok:

- a jelenlegi Win11 hoston már telepítve van és jól fut,
- natívan használhatja a Windows oldali hardveres gyorsítást,
- OpenAI-kompatibilis endpointokon keresztül hívható,
- támogatja a programozott lokális inference-t,
- illeszthető az `LLMProvider` absztrakció mögé.

Provider absztrakció:

```text
Backend analysis modules
  ↓
LLMProvider interface
  ↓
LM Studio / Ollama / llama.cpp / other local runtime
```

A backend elemzési moduljai ne függjenek közvetlenül LM Studio-specifikus API-tól. A cél az, hogy az LM Studio később cserélhető legyen Ollamára, llama.cpp / llama-serverre vagy más lokális runtime-ra az elemzési modulok módosítása nélkül.

Kontrolláltabb deploymentnél:

```text
llama.cpp / llama-server
```

Későbbi alternatívák:

- Ollama,
- vLLM,
- LM Studio lokális server,
- saját inference service,
- GPU-s lokális deployment.

### 16.3 Modellválasztási elvek

A modellválasztásnál nem csak a nyers teljesítményt kell nézni.

Fontos szempontok:

- magyar nyelvi teljesítmény,
- hosszabb kontextus kezelése,
- JSON-követés képessége,
- hallucination kontrollálhatóság,
- lokális futtathatóság,
- kvantált verziók elérhetősége,
- sebesség középkategóriás gépen,
- licence,
- reproducibilitás.

## 17. Embedding modell

Az embedding modell feladata a chunkok szemantikus vektorrá alakítása.

Követelmények:

- magyar nyelv támogatása,
- többnyelvű vagy magyarra jól működő embedding,
- lokális futtathatóság,
- stabil dimenziószám,
- jó retrieval teljesítmény,
- batch feldolgozás támogatása.

Az embedding modell külön komponens legyen, ne legyen összekeverve a generatív LLM-mel.

## 18. Strukturált elemzési modulok

A rendszer nem szabad formájú chatbotként működik, hanem előre definiált elemzési modulokkal.

MVP elemzési modulok:

```text
extract_entities
extract_events
extract_claims
build_timeline
detect_contradiction_candidates
detect_missing_items
summarize_case
answer_with_citations
```

Minden modulhoz tartozik:

- prompt template,
- bemeneti séma,
- kimeneti JSON séma,
- validátor,
- confidence mezők,
- source reference mezők,
- audit log bejegyzés.

## 19. Példa: állításkinyerő modul

### 19.1 Modulnév

```text
extract_claims
```

### 19.2 Cél

A dokumentumrészletekből releváns állítások kinyerése és strukturált formában tárolása.

### 19.3 Bemenet

```json
{
  "case_id": "...",
  "chunks": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "document_name": "...",
      "page_start": 3,
      "page_end": 3,
      "text": "..."
    }
  ]
}
```

### 19.4 Kimenet

```json
{
  "claims": [
    {
      "claim_text": "...",
      "claim_type": "witness_statement | document_fact | expert_opinion | administrative_fact | unknown",
      "source": {
        "document_id": "...",
        "document_name": "...",
        "page": 3,
        "chunk_id": "...",
        "quote": "..."
      },
      "related_entities": ["..."],
      "related_time": "...",
      "confidence": "low | medium | high",
      "requires_human_review": true
    }
  ]
}
```

### 19.5 Validáció

A modul kimenete csak akkor fogadható el, ha:

- minden állításhoz van forrás,
- minden forrás létező chunkra mutat,
- a quote megtalálható a forráschunkban vagy annak oldalszintű szövegében,
- a confidence érték megadott értékkészletből származik,
- a JSON séma valid.

## 20. Forráshivatkozási modul

A forráshivatkozási modul biztosítja, hogy minden elemzés visszavezethető legyen a dokumentum konkrét részére.

Forráshivatkozás mezői:

```text
source_reference_id
case_id
document_id
document_name
page_number
chunk_id
quote
char_start
char_end
created_at
```

Alapelv:

> A rendszer UI-jában minden állítás mellett legyen „Ugrás a forrásra” funkció.

## 21. Emberi review workflow

Minden AI által létrehozott elemzés ellenőrzési státusszal rendelkezik.

Javasolt státuszok:

```text
new
needs_review
verified
rejected
corrected
exported
```

Az emberi ellenőrzés során a felhasználó:

- elfogadhat egy állítást,
- elutasíthatja,
- javíthatja,
- megjegyzést fűzhet hozzá,
- további forrásokat kapcsolhat hozzá,
- törölheti az elemzésből.

Minden emberi módosítás auditált.

## 22. Audit log architektúra

Az audit log célja, hogy minden fontos művelet utólag rekonstruálható legyen.

### 22.1 Auditálandó események

- ügy létrehozása,
- dokumentum importálása,
- hash generálása,
- OCR/parsing futtatása,
- chunkolás,
- embedding generálás,
- keresés,
- retrieval találatok,
- LLM prompt összeállítása,
- LLM válasz,
- strukturált output validáció,
- emberi review,
- exportálás,
- törlés / archiválás.

### 22.2 Audit log javasolt tárolása

Két réteg javasolt:

```text
1. PostgreSQL audit_events tábla lekérdezhető eseményekhez
2. Append-only JSONL log fájl immutable jellegű naplózáshoz
```

Minden audit esemény tartalmazza:

```text
event_id
case_id
user_id
event_type
timestamp
input_summary
output_summary
related_document_ids
related_chunk_ids
model_name
model_version
prompt_template_version
success
error_message
```

## 23. Adatmodell v1

### 23.1 Fő entitások

```text
Case
Document
Page
Chunk
Entity
Mention
Event
Claim
ContradictionCandidate
MissingItemCandidate
SourceReference
AnalysisRun
AuditEvent
HumanReview
Export
```

### 23.2 Case

```text
id
name
reference
description
status
created_at
created_by
updated_at
```

### 23.3 Document

```text
id
case_id
original_filename
stored_path
mime_type
file_size
sha256
page_count
imported_at
imported_by
processing_status
parser_name
parser_version
```

### 23.4 Page

```text
id
document_id
page_number
text
ocr_used
ocr_confidence
created_at
```

### 23.5 Chunk

```text
id
case_id
document_id
page_start
page_end
chunk_index
text
char_start
char_end
token_count
embedding_id
created_at
```

### 23.6 Entity

```text
id
case_id
entity_type
canonical_name
normalized_value
confidence
created_at
review_status
```

### 23.7 Mention

```text
id
entity_id
case_id
document_id
chunk_id
page_number
surface_text
char_start
char_end
confidence
```

### 23.8 Event

```text
id
case_id
event_time
normalized_time
event_text
event_type
source_reference_id
confidence
review_status
```

### 23.9 Claim

```text
id
case_id
claim_text
claim_type
source_reference_id
related_event_id
confidence
review_status
created_by_analysis_run
```

### 23.10 ContradictionCandidate

```text
id
case_id
description
claim_id_a
claim_id_b
source_reference_id_a
source_reference_id_b
contradiction_type
confidence
review_status
```

### 23.11 MissingItemCandidate

```text
id
case_id
description
referenced_item
source_reference_id
missing_item_type
confidence
review_status
```

### 23.12 AnalysisRun

```text
id
case_id
analysis_type
started_at
finished_at
started_by
model_name
model_version
prompt_template_version
input_chunk_ids
output_object_ids
status
error_message
```

### 23.13 HumanReview

```text
id
case_id
object_type
object_id
review_status
reviewed_by
reviewed_at
comment
previous_value
new_value
```

## 24. Backend architektúra

Javasolt backend:

```text
Python + FastAPI
```

Indoklás:

- erős AI/NLP/OCR ökoszisztéma,
- gyors prototípusfejlesztés,
- könnyű integráció Doclinggal, Tesseracttal, Qdranttal, Ollamával,
- jó REST API támogatás,
- később könnyen konténerizálható.

Fő backend modulok:

```text
app/api
app/core
app/models
app/services/document_processing
app/services/ocr
app/services/chunking
app/services/search
app/services/llm
app/services/analysis
app/services/audit
app/services/export
```

## 25. Frontend architektúra

Javasolt frontend:

```text
React alapú webes UI
```

Fő felületek:

- ügylista,
- ügy részletező nézet,
- dokumentumlista,
- dokumentummegjelenítő,
- keresőfelület,
- szereplőlista,
- idővonal,
- állításlista,
- ellentmondásjelöltek,
- hiányjelöltek,
- audit log,
- export nézet.

A UI fő elve:

> Minden AI által generált elem mellett legyen forráslink és review státusz.

A rendszer ne chatbotként induljon, hanem case analysis workbenchként.

## 26. Export modul

Az export modul célja ember által ellenőrzött elemzések kinyerése.

MVP export formátumok:

- Markdown,
- HTML,
- JSON.

Később:

- PDF,
- DOCX,
- CSV,
- evidencematrix export.

Exportáláskor naplózni kell:

- ki exportált,
- mikor,
- melyik ügyből,
- mely elemzéseket,
- milyen formátumban.

## 27. Jogosultságkezelés

MVP-ben egyszerű szerepkörök elegendők:

```text
admin
analyst
reviewer
viewer
```

Szerepkörök:

### admin

- rendszerbeállítások,
- felhasználókezelés,
- minden ügy elérése.

### analyst

- dokumentumimport,
- elemzések indítása,
- keresés,
- javaslatok létrehozása.

### reviewer

- AI outputok ellenőrzése,
- elfogadás,
- javítás,
- elutasítás.

### viewer

- olvasási hozzáférés,
- export csak külön jogosultsággal.

## 28. Biztonsági architektúra

Alapelvek:

- minden adat lokális,
- ügyek elkülönítése,
- hozzáférés-szabályozás,
- eredeti fájlok változatlan megőrzése,
- minden export naplózása,
- minden AI output verziózása,
- minden prompt és retrieval találat auditálása,
- konfigurálható modellhasználat,
- külső hálózati kapcsolat tiltása vagy szigorú kontrollja.

Deployment környezetnél javasolt:

```text
offline gép
vagy
zárt belső hálózat
vagy
konténerizált lokális deployment
```

## 29. Javasolt technológiai stack v1

### Backend

```text
Python + FastAPI
```

### Relációs adatbázis

```text
PostgreSQL
```

### Vektoros keresés

```text
Qdrant
```

Alternatíva egyszerűsített PoC-hoz:

```text
PostgreSQL + pgvector
```

### Dokumentumfeldolgozás

```text
Docling
```

### OCR

```text
Tesseract OCR + hun nyelvi csomag
```

### Magyar NLP

```text
HuSpaCy + regex szabályok
```

### Lokális LLM fejlesztéshez

```text
LM Studio on the Windows 11 host,
called from the WSL/Linux backend through the local OpenAI-compatible API
```

Alternatív fejlesztési provider:

```text
Ollama
```

### Kontrollált lokális inference később

```text
llama.cpp / llama-server
```

### Frontend

```text
React
```

### Audit log

```text
PostgreSQL audit_events tábla
+ append-only JSONL log
```

### Export

```text
Markdown / HTML / JSON MVP-ben
PDF / DOCX később
```

## 30. MVP fejlesztési sorrend

### Fázis 1: Dokumentumfeldolgozó mag

Cél:

- ügy létrehozása,
- dokumentumimport,
- hash generálás,
- szövegkinyerés,
- OCR,
- oldalszintű tárolás.

Kimenet:

- importált dokumentumok,
- oldalszintű szövegek,
- feldolgozási státuszok.

### Fázis 2: Chunkolás és indexelés

Cél:

- chunkok létrehozása,
- chunk metaadatok tárolása,
- embedding generálás,
- Qdrant index építése,
- kulcsszavas index építése.

Kimenet:

- kereshető dokumentumkorpusz.

### Fázis 3: Forráshivatkozott keresés

Cél:

- kulcsszavas keresés,
- szemantikus keresés,
- hybrid találati lista,
- forrásoldal és idézet megjelenítése.

Kimenet:

- ellenőrizhető keresőfelület.

### Fázis 4: Lokális LLM integráció

Cél:

- LLM provider interfész,
- LM Studio integráció OpenAI-kompatibilis lokális API-n keresztül,
- Ollama alternatív providerként,
- strukturált prompt template-ek,
- JSON output validáció,
- analysis_run naplózás.

Kimenet:

- forrásalapú strukturált válaszok.

### Fázis 5: Szereplőlista és entitások

Cél:

- regex alapú entitáskinyerés,
- HuSpaCy integráció,
- LLM-alapú normalizálás,
- szereplőlista UI.

Kimenet:

- forráshivatkozott szereplőlista.

### Fázis 6: Idővonal

Cél:

- dátumok és események kinyerése,
- események normalizálása,
- idővonal UI,
- forráslink minden eseményhez.

Kimenet:

- ellenőrizhető idővonaljavaslat.

### Fázis 7: Állításlista

Cél:

- claim extraction,
- forráshivatkozás,
- claim típusok,
- review workflow.

Kimenet:

- strukturált állításlista.

### Fázis 8: Ellentmondás- és hiányjelöltek

Cél:

- potenciális ellentmondások azonosítása,
- hiányzó hivatkozott elemek jelzése,
- emberi ellenőrzési státusz.

Kimenet:

- review-képes figyelemfelhívó listák.

### Fázis 9: Export és audit

Cél:

- audit log teljessé tétele,
- exportálható jelentés,
- export auditálása.

Kimenet:

- ember által ellenőrzött jelentéscsomag.

## 31. Első működő célállapot

Az első valóban értékes célállapot:

> A felhasználó betölt 20–50 dokumentumot egy ügyhöz. A rendszer lokálisan feldolgozza azokat, létrehoz egy kereshető indexet, majd forráshivatkozott szereplőlistát, idővonaljavaslatot és állításlistát készít. Minden generált elem mellett látható az eredeti dokumentum, oldalszám, idézet, bizonyossági szint és emberi review státusz.

Ez már egy használható MVP, még jogszabályi RAG nélkül is.

## 32. Tudatosan későbbre hagyott elemek

Az első architektúrában előkészítjük, de nem építjük meg teljesen:

- magyar jogszabályi RAG,
- tényállási elemek szerinti bizonyítékmátrix,
- többügyes összehasonlítás,
- híváslista/cellaadat-specifikus elemzés,
- e-mail postafiókok mély feldolgozása,
- chat exportok speciális elemzése,
- grafos kapcsolatelemzés,
- teljes jogosultsági enterprise modell,
- külső rendszerintegrációk.

## 33. Későbbi jogszabályi RAG előkészítése

> **Aktuális megjegyzés, 2026-06-02:** a jogszabályi RAG továbbra sem azonnali implementációs feladat, de a következő nagyobb tervezési irány már egy általános lokális RAG kérdező réteg. Ebben a jogszabályi corpus később specializált adat- és retrieval-profillal jelenhet meg. Részletek: `Design_documents/20_general_rag_question_answering_plan.md`.

Bár a jogszabályi RAG nem MVP-1 funkció, az architektúrát úgy kell kialakítani, hogy később hozzáadható legyen.

Ehhez már MVP-ben szükséges:

- elkülönített corpus fogalma,
- forráshivatkozott retrieval,
- chunk metaadatok,
- verziózott indexek,
- modellválaszok auditálása,
- JSON-sémás outputok,
- jogszabályi hivatkozások kezelésére alkalmas adatmodell-bővítési pont.

Későbbi jogszabályi corpus entitások:

```text
LegalDocument
LegalSection
LegalProvision
LegalElement
LegalCitation
```

## 34. Fejlesztési prioritás

A legfontosabb prioritási sorrend:

```text
1. Forráshűség
2. Auditálhatóság
3. Lokális működés
4. Kereshetőség
5. Strukturált output
6. Emberi review
7. Modellminőség
8. Kényelmes UI
9. Jogszabályi modul
10. Fejlett elemzések
```

A modellminőség fontos, de nem előzheti meg a forráshűséget és az auditálhatóságot.

## 35. Legfontosabb kockázatok

### 35.1 Hallucináció

Kockázat:

A modell forrás nélküli vagy pontatlan állítást generál.

Kontroll:

- kötelező forráshivatkozás,
- quote-validáció,
- JSON séma,
- unsupported claim ellenőrzés,
- emberi review.

### 35.2 Hibás OCR

Kockázat:

A rendszer rosszul olvassa be a dokumentumot, emiatt hibás elemzés készül.

Kontroll:

- OCR confidence tárolás,
- alacsony minőségű oldalak jelölése,
- eredeti oldal megtekintése,
- emberi ellenőrzés.

### 35.3 Rossz retrieval

Kockázat:

A modell nem a releváns dokumentumrészleteket kapja meg.

Kontroll:

- hybrid search,
- reranking,
- találatok naplózása,
- retrieval evaluation.

### 35.4 Forráshivatkozási hiba

Kockázat:

Az elemzés rossz dokumentumra vagy oldalra hivatkozik.

Kontroll:

- source reference validáció,
- quote ellenőrzése a chunkban,
- oldalszintű tárolás,
- UI-ból visszakattintható forrás.

### 35.5 Túlzott bizalom a rendszerben

Kockázat:

A felhasználó kész tényként kezeli az AI által generált elemzést.

Kontroll:

- minden outputon review státusz,
- figyelmeztető jelölések,
- export csak ellenőrzött elemekből,
- rendszerleírásban rögzített nem döntéshozó szerep.

## 36. Következő dokumentumjavaslatok

A technikai architektúra után a következő dokumentumok javasoltak:

1. Adatbázis-séma v1
2. API-terv v1
3. Dokumentumfeldolgozó pipeline részletes terve
4. Prompt- és JSON-séma gyűjtemény
5. MVP fejlesztési backlog
6. Tesztelési és validációs terv
7. Lokális modellválasztási benchmark terv
8. Jogszabályi RAG modul koncepciója

## 37. Összegzés

A javasolt architektúra egy lokális, moduláris, auditálható nyomozati iratfeldolgozó rendszer alapját adja.

A rendszer nem chatbotként, hanem case analysis workbenchként működik.

Elsőként az iratok pontos feldolgozására, kereshetőségére, forráshivatkozására és emberi ellenőrzésére koncentrál.

A lokális LLM fontos komponens, de nem a rendszer központi igazságforrása. A központi igazságforrás az eredeti dokumentum, a forráshely, az audit log és az emberi validálás.

A v1 architektúra legfontosabb célja, hogy stabil alapot adjon a későbbi jogszabályi RAG, bizonyítékmátrix és fejlettebb nyomozati elemző modulok számára.
