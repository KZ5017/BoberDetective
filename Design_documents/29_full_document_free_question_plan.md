# 29. Teljes iratfeldolgozas - szabad iratkerdes terv

## 0. Cel

Aktualis allapot: az elso backend/frontend implementacios szelet elkeszult.

Megvalosult:

- `full_document_answers` adatmodell es migracio (`0050_full_document_answers`),
- `full_document_answer` analysis-run output tipus,
- `free_document_question` profil a profil-listaban,
- profilfuggo futtatas a meglevo full-document run endpointon,
- valasz lista/reszlet/soft-delete API,
- frontend `Szabad iratkérdés` egysoros kerdesmezo,
- frontend `Iratválasz` panel biztonsagos Markdown renderelessel,
- mentett valasz lista/reszlet/torles UI,
- torles utani automatikus listafrissites es kovetkezo valasz kivalasztasa,
- korabbi valaszok kivalaszto gombjai a kozos, tokenizalt choice-button stilust hasznaljak,
- tolerans valasz-JSON mentes: ha az `answer_text` kinyerheto, a hibas opcionalis metadata, a belso escape-eletlen idezojel vagy a hianyzo vegso objektumzaras nem dobja el a teljes valaszt.

Nem megvalosult / kesobbi finomitas:

- tovabbi UX finomhangolas live tesztek alapjan, ha konkret problema jelenik meg,
- esetleges prompt tuning konkret hibas valaszok alapjan,
- archiv/restore workflow az iratvalaszokra.

Ez a dokumentum a `Teljes iratfeldolgozás` munkafelület tervezett masodik
profiliranyat rogziti.

Munkanev:

```text
Szabad iratkérdés
```

A cel egy olyan dokumentum- es oldaltartomany-kotott kerdes-valasz profil,
amely nem retrieval/chunk valogatasbol dolgozik, hanem a felhasznalo altal
kivalasztott aktiv irat megadott oldalait adja at az LLM-nek forraskent.

Ez nem ugyanaz, mint:

- a `Személykeresési fókuszok` profil,
- az `Általános iratkérdező`,
- a `Tudásbázis`,
- a `search_findings` kutatasi talalat workflow.

## 1. Alapelv

Az uj profil nem munkalista-elemeket gyart, hanem egy iratvalaszt.

Kulonbseg:

```text
Szemelyprofil:
irat + oldaltartomany -> szemely munkadarabok -> Elokeszitett munkalista

Szabad iratkerdes:
irat + oldaltartomany + kerdes -> szoveges valasz -> Iratvalasz
```

Ezert az uj profil nem kerulhet bele a `document_processing_items` tablaba.

Indok:

- a `document_processing_items` jelenlegi adatmodellje person-only
  munkalistara van szukitve,
- a szabad iratkerdes egyetlen valasz, nem sok elokeszitett kartyas
  munkadarab,
- a ket workflow UI/UX es validacios jelentese elter,
- nem akarunk ujra egy tul altalanos, nehezen ertelmezheto munkalista-tablaba
  visszacsuszni.

## 2. Javasolt adatmodell

Uj tabla:

```text
full_document_answers
```

Javasolt mezok:

```text
id
case_id
document_id
analysis_run_id
profile_key
question_text
answer_text
source_summary
page_start
page_end
source_page_count
source_character_count
model_name
prompt_template_name
prompt_template_version
answer_status
created_at
updated_at
```

### 2.1 `profile_key`

Elso ertek:

```text
free_document_question
```

UI cimke:

```text
Szabad iratkérdés
```

### 2.2 `answer_status`

Javasolt elso ertekek:

```text
active
deleted
```

Elso implementacios szeletben nem kell bonyolitani archiv/restore workflow-val.
Ha a kesobbi UI igenyli, felveheto:

```text
archived
```

### 2.3 `source_summary`

Rovid, backend- vagy LLM-altal adott forrasalap osszegzes.

Nem kotelezo szakmai bizonyitek, csak olvasasi segedlet:

```text
A válasz a kijelölt irat 5-9. oldalain szereplő tanúvallomás-részletekre épül.
```

Ha a modell erosen ingadozo vagy zavaro `source_summary` mezot ad, az elso
implementacioban elhagyhato vagy backend-altal determinisztikusan eloallithato:

```text
Forrás: <iratnév>, <page_start>-<page_end>. oldal
```

## 3. Analysis run kapcsolat

Run type marad:

```text
full_document_processing
```

Indok:

- ugyanazon munkafelület es forraskivalasztasi logika,
- a profil kulonbozteti meg a futas jellegét,
- az audit/analysis tortenet tovabbra is egy helyen kovetheto.

`analysis_runs.input_parameters`:

```json
{
  "document_id": "...",
  "profile_key": "free_document_question",
  "page_start": 5,
  "page_end": 9,
  "question_text": "..."
}
```

`analysis_run_inputs`:

- dokumentum input,
- oldalszintu inputok a kivalasztott oldaltartomany aktualis oldalaival,
- opcionalisan `input_kind=full_document_free_question_source`.

`analysis_run_outputs`:

- `output_type=full_document_answer`,
- `output_object_id=<full_document_answers.id>`.

Ehhez DB constraint bovites kell az analysis output tipusoknal.

## 4. API szerzodes

### 4.1 Profilok

A profil-lista bovul:

```json
{
  "key": "free_document_question",
  "label": "Szabad iratkérdés",
  "description": "Kérdés megválaszolása a kijelölt irat megadott oldalai alapján."
}
```

### 4.2 Futtatas

Lehetoseg A: a meglevo run endpoint bovul profilfuggo payload mezovel.

```http
POST /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/runs
```

Payload:

```json
{
  "profile_key": "free_document_question",
  "page_start": 5,
  "page_end": 9,
  "question_text": "Milyen módon jutott a detektív a megoldáshoz?"
}
```

Valasz:

```json
{
  "analysis_run_id": "...",
  "document_id": "...",
  "profile_key": "free_document_question",
  "answer": {
    "id": "...",
    "question_text": "...",
    "answer_text": "...",
    "source_summary": "...",
    "page_start": 5,
    "page_end": 9
  },
  "validation_status": "passed"
}
```

Lehetoseg B: kulon endpoint.

```http
POST /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/free-question
```

Elso implementacios javaslat:

```text
Lehetoseg A
```

Indok:

- a profilvalaszto es az oldaltartomany ugyanazt a munkafelületet hasznalja,
- a backend mar most profilkulcs alapjan futtat,
- kevesebb duplikalt API es frontend allapot.

### 4.3 Valaszok listazasa

```http
GET /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/answers
```

Query:

```text
profile_key=free_document_question
answer_status=active
search=...
```

### 4.4 Valasz reszlete

```http
GET /api/v1/cases/{case_id}/full-document-processing/answers/{answer_id}
```

### 4.5 Valasz torlese

Elso korben soft delete:

```http
DELETE /api/v1/cases/{case_id}/full-document-processing/answers/{answer_id}
```

Eredmeny:

```text
answer_status = deleted
```

## 5. Prompt es JSON szerzodes

### 5.1 System prompt

Elv:

- a system prompt tartalmazza a feladatot es szabalyokat,
- a user prompt csak dinamikus adatot tartalmaz:
  - dokumentum,
  - oldalak,
  - kerdes.

Javasolt szabalyok:

```text
Forráshű iratválaszoló komponens vagy.
A SOURCE az egyetlen igazságforrás.
A QUESTION a megválaszolandó kérdés.
Csak a SOURCE alapján válaszolj.
Ne használj külső tudást.
Ne pótolj hiányzó adatot.
Ha a SOURCE alapján nincs elég információ, ezt mondd ki.
Ne hozz létre kutatási találatot, claimet, eseményt vagy személy-munkalistát.
Csak érvényes JSON objektumot adj vissza.
```

### 5.2 Elvart JSON

Javasolt minimalis alak:

```json
{
  "insufficient_source": false,
  "source_summary": "...",
  "answer_text": "..."
}
```

Mezosorrend:

```text
insufficient_source
source_summary
answer_text
```

Indok:

- a rovid/egyszeru mezok elol vannak,
- a hosszu, Markdown-szeru `answer_text` a vegen van,
- ez csokkentheti annak eselyet, hogy a modell a rovid mezoket elhagyja.

### 5.3 JSON tolerancia

A `Tudásbázis` valaszokhoz hasonloan itt is varhato hosszu Markdown-szeru
szoveg, belso idezojelek, kodblokkok, felsorolasok.

Ezert:

- `answer_text` legyen kotelezo,
- `source_summary` lehessen opcionális / backend fallback,
- `insufficient_source` legyen boolean, de a parser koercialhatja a
  nyilvanvalo string/numeric boolean-szeru ertekeket,
- fallback parser csak erre a sémára keszuljon, es kezelje az escape-eletlen belso idezojeleket, valamint a hianyzo vegso objektumzarast,
- ez a tolerancia nem masolhato at source-validalt strukturalt objektumok
  letrehozasara.

## 6. Forraskezeles

Forras:

```text
kivalasztott aktiv irat + page_start/page_end
```

Nem hasznal:

- semantic/hybrid retrievalt,
- Qdrantot,
- chunk plafont,
- batch meretet,
- iratgyujtemenyt,
- ugy-szintu forraskort.

Az oldalak cimkezve mennek ki:

```text
page_5:
document_id: ...
page_number: 5
text:
...
```

Fontos:

- nagy oldaltartomanynal kontextusablak-tulcsordulas lehet,
- elso korben backend karakterlimit kell a kivalasztott oldalak osszhosszara,
- ha tul nagy a forraskor, a backend adjon ertelmes hibat:

```text
A kijelölt oldaltartomány túl hosszú egyetlen iratválaszhoz. Szűkítsd az oldaltartományt.
```

## 7. UI terv

### 7.1 Profilpanel

`Irat és feldolgozási profil`:

- `Feldolgozási profil`
  - `Személykeresési fókuszok`
  - `Szabad iratkérdés`
- `Oldaltól`
- `Oldalig`
- ha `Szabad iratkérdés` aktiv:
  - megjelenik egy teljes soros `Kérdés` beviteli mező,
  - `Feldolgozás indítása` helyett lehet ugyanaz a gomb vagy pontosabb cimke:
    `Kérdés megválaszolása`.

### 7.2 Eredmenypanel profilfuggo megjelenitese

Ha profil:

```text
person_search_seeds
```

akkor:

```text
Előkészített munkalista
```

Ha profil:

```text
free_document_question
```

akkor:

```text
Iratválasz
```

Az `Iratválasz` panel ne hasznalja a szemely-munkalista kartyakat.

Javasolt megjelenites:

- aktualis / legutobbi valasz nagy olvashato kartyan,
- kerdes,
- valasz Markdown-szeru biztonsagos renderelessel,
- korabbi valaszok teljes szelessegu choice-button jellegu gombokkal,
- ures allapotban kozos helykitolto blokk,
- forrasalap: iratnev + oldaltartomany,
- mentett korabbi valaszok listaja kesobb vagy ugyanazon panel masodik
  reszekent.

Elso implementacios szeletben elfogadhato:

- csak az aktualis valasz es egy egyszeru mentett valasz lista,
- vagy a valasz azonnali mentese `full_document_answers` tablaba es a lista
  automatikus frissitese.

## 8. Validacio

Backend validacio:

- case letezik,
- document a case-hez tartozik,
- document `active`,
- document rendelkezik aktualis oldalszoveggel,
- profile ismert,
- `free_document_question` profilnal `question_text` kotelezo es nem ures,
- `page_start/page_end` a dokumentumon belul van,
- `page_start <= page_end`,
- kivalasztott oldalak nem uresek,
- kivalasztott oldalak osszkaraktere nem lepi tul az elso implementacios
  biztonsagi limitet,
- LLM valaszbol `answer_text` kinyerheto.

Frontend validacio:

- `Szabad iratkérdés` profilnal a futtatas gomb inaktiv, amig nincs kerdes,
- page range hibas allapotnal futtatas inaktiv vagy backend hiba jelenik meg,
- profilvaltasnal a munkalista/iratvalasz panel ne mutasson masik profilhoz
  tartozo tartalmat.

## 9. Mi marad ki tudatosan elso korben

Nem elso kor:

- tobb irat egy valaszban,
- iratgyujtemeny alapu szabad kerdes,
- retrieval/hybrid/semantic forrasvalogatas,
- chunk-lista megjelenites,
- forrasmondatok automatikus kiemelese,
- review report objektum letrehozas,
- claim/event/entity automatikus letrehozas,
- valaszok kozti osszehasonlitas,
- export.

## 10. Implementacios sorrend

1. DB migracio:
   - `full_document_answers`,
   - analysis output type bovites `full_document_answer`.
2. Schema:
   - request bovites `question_text`,
   - response bovites `answer`,
   - answer read/list schema.
3. Service:
   - profil registry bovites,
   - `person_search_seeds` es `free_document_question` futas szetvalasztasa,
   - oldaltartomany text-store olvasas ujrahasznositasa,
   - full-document free-question prompt,
   - JSON parser/fallback,
   - answer persistence,
   - analysis run input/output rogzites.
4. API:
   - meglevo run endpoint profilfuggo valasza,
   - answer list/detail/delete endpointok.
5. Frontend:
   - profilvalasztas utan kerdesmezo,
   - profilfuggo eredmenypanel,
   - `Iratválasz` megjelenites biztonsagos Markdown renderelessel,
   - mentett valasz lista / torles.
6. Tesztek:
   - schema validacio,
   - prompt/user prompt tartalom,
   - tul nagy oldaltartomany hiba,
   - sikeres answer mentese,
   - frontend build.

## 11. Döntési összegzés

Elfogadott irany:

```text
Teljes iratfeldolgozás
  -> person_search_seeds: document_processing_items munkalista
  -> free_document_question: full_document_answers iratvalasz
```

Ez megtartja a jelenlegi személy-munkalista tisztaságát, miközben ad egy
kontrollált, oldaltartományhoz kötött, tartósan menthető szabad iratválasz
workflow-t.
