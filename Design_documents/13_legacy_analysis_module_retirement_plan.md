# 13. Legacy Analysis Module Retirement Plan

## 0. Aktualisitas

Frissitve: 2026-05-22.

Ez a dokumentum mar a munkalista-alapu kutatasi talalat modellt koveti. A `research_finding` nem reviewolhato/exportalhato szakmai objektum, hanem atmeneti keresesi munkadarab. A review reportba es a tovabbi szakmai workflow-kba csak az atalakitas utan letrejovo strukturalt objektum kerul.

Aktualis kivezetesi allapot:

```text
aktiv backend dispatch: search_findings, detect_contradiction_candidates
eltavolitott raw modulok: extract_claims, extract_events, extract_entities, summarize_case, detect_missing_items
frontend modulvalaszto: csak kutatasi talalatok es ellentmondasjeloltek
regi module_key viselkedes: Unsupported analysis module
```

2026-05-22-re a korabbi nyers chunk-alapu modulok aktiv kodutjai, frontend opcioi, response schema mezoi, modul-specifikus service fajljai es prompt/validacios tesztjei el lettek tavolitva. A torteneti adatbazis run type engedelyezes es a torteneti changelog/design megjegyzesek megmaradhatnak, de nem jelentenek aktiv workflow-t.

Aktualis UI-sorrend:

```text
Kutatási találatok -> Áttekintési jelentés -> Találat részletei
```

Aktualis munkalista-muveletek:

```text
felretetel
vissza az aktiv listaba
torlesre jeloles
csoportos torles
strukturalt objektumma alakitas
```

Nem cel: kutatasi talalat review status, human review bejegyzes vagy export sor.

## 1. Cel

Ez a dokumentum azt rogziti, hogyan kell tisztan kivezetni a jelenlegi nyers chunk-alapu automatikus elemzesi modulokat, hogy az uj `research_finding` / kutatasi talalat munkalista-modellre valo atallas utan ne maradjanak felig hasznalt legacy kodutak.

Kiemelt cel:

```text
nincs "legacykent maradhat" szemlelet,
nincs felig elhalt endpoint,
nincs UI-ban ottfelejtett modulvalaszto,
nincs jovobeli fejlesztest zavaro nem hasznalt kodtoredek.
```

## 2. Kivezetes oka

A tesztek alapjan a jelenlegi modell tul koran objektumtipust kenyszerit az LLM-re.

Peldak:

- `extract_events` esemenyt probal gyartani akkor is, ha a relevans forrashely inkabb altalanos talalat,
- `extract_claims` sokszor tul szuk vagy tul tag allitasokat hoz,
- `extract_entities` kockazatosan keverheti a valodi entitast es a queryhez lazabban kapcsolodo szereploket,
- `detect_missing_items` nyers szovegreszekbol probal hianyra kovetkeztetni, ami fogalmilag hibas,
- `summarize_case` egymastol tavoli retrieval-talalatokbol probal osszefoglalot kesziteni, ami nem ugyosszefoglalo, hanem keresesi talalatok narrativ osszefuzese.

Az uj irany:

```text
query -> forraskereses -> kutatasi talalat munkalista -> emberi dontes -> strukturalt objektum
```

## 3. Kivezetendo automatikus modulok

Az alabbi nyers chunk-alapu automatikus modulokat ki kell vezetni a fo workflow-bol es a kodbol:

```text
extract_claims
extract_events
extract_entities
detect_missing_items
summarize_case
```

Kivezetes utan ezekhez ne maradjon aktiv:

- frontend modulvalaszto opcio,
- backend analysis module endpoint route-ag,
- service entrypoint,
- prompt,
- JSON repair helper, ha csak az adott modul hasznalta,
- modul-specifikus teszt,
- dokumentacio, amely aktiv funkciokent irja le oket.

## 4. Kulon kezelt modul: detect_contradiction_candidates

A `detect_contradiction_candidates` nem ugyanaz a kategoria, mert nem nyers chunkokbol dolgozik, hanem forrassal mar rendelkezo claim-parokon.

Ezt nem kell az elso korben kidobni.

Viszont at kell gondolni az uj modellben:

- csak ember altal letrehozott vagy jovahagyott claim-ekkel dolgozzon,
- ne legyen nyers findingokra kotve automatikusan,
- maradjon downstream, strukturalt objektumokon dolgozo workflow.

Tehat allapota:

```text
megtartando, de kesobb ujraillesztendo.
```

Nem szabad osszekeverni a nyers chunk-alapu automatikus kinyerokkel.

## 5. Megtartando workflow-k

Az alabbiak nem legacy automatikus modulok, hanem emberi kontrollos forraskotott muveletek. Ezeket meg kell tartani, es az uj finding-modellhez kell illeszteni:

```text
manual claim creation from selected chunk text
manual entity creation from selected chunk text
manual event creation from selected chunk text
manual missing item candidate creation from selected chunk text, ha kesobb megmarad ilyen objektum
manual object creation from detached source
source detach
source reattach
direct source move
entity merge
event merge
missing item candidate merge
manual contradiction candidate creation from claim pair
review actions
export, ha az uj report modellhez igazitjuk
```

Ezek erteke:

- forrasalapuak,
- ember inditja oket,
- audit es review folyamatba kothetok,
- nem kenyszeritik az LLM-et nyers szovegbol rossz kategoriaba.

## 6. Adatbazis-tablak elvi sorsa

Nem minden tabla torlendo.

### 6.1 Megtartando strukturalt objektumtablak

Ezekre tovabbra is szukseg van, mert a felhasznalo vagy kesobbi konverzio hozhat letre ilyen objektumokat:

```text
claims
claim_sources
events
event_sources
entities
entity_mentions
contradiction_candidates
contradiction_candidate_sources
source_references
analysis_runs
analysis_run_inputs
analysis_run_outputs
audit_events
```

### 6.2 Uj tablak

Bevezetendo:

```text
research_findings
```

A pontos schema a `12_source_bound_findings_model_plan.md` alapjan keszuljon.

Aktualis elso lepcso:

- `research_findings` tabla kozvetlen `target_object_type` / `target_object_id` mezokkel,
- nincs kulon `research_finding_conversions` tabla,
- nincs `review_status` mező a research finding modellen,
- a kesobbi grafirany miatt a kozvetlen celmezos kapcsolat kesobb kapcsolattablava bovitheto.

### 6.3 Kerdeses tablak

`summary_items` es `missing_item_candidates` sorsa kulon dontest igenyel.

Jelenlegi irany:

- `summary_items`: a nyers retrieval-alapu summary workflow-bol kivezetendo; kesobb mas, dokumentum/ugy-szintu osszefoglalo modellben lehet ujragondolni.
- `missing_item_candidates`: nyers chunk-alapu detekciokent kivezetendo; kesobb dokumentumtaxonomia, hivatkozas-osszevetes es iratleltar alapu workflow-ban lehet ujragondolni.

Elso implementacios korben ne toroljuk automatikusan a tablat, amig nincs migracios dontes, de uj automatikus letrehozas ne maradjon aktiv.

Fontos:

```text
az adatmodell megtartasa nem jelent aktiv legacy workflow-t.
```

## 7. API kivezetesi terv

### 7.1 Eltavolitando vagy atiro backend route-ok

A jelenlegi altalanos analysis module endpointban meg kell szuntetni az alabbi module_key-ek fogadasat:

```text
extract_claims
extract_events
extract_entities
detect_missing_items
summarize_case
```

Helyettuk uj modul:

```text
search_findings
```

vagy:

```text
extract_findings
```

Vegleges nev kesobb dontendo, de legyen egyetlen altalanos kutatasi modul, ne tobb automatikus objektumkategoria.

### 7.2 Uj endpoint-csoport

Javasolt uj API-k:

```text
POST /api/v1/cases/{case_id}/analysis/modules/search_findings
GET  /api/v1/cases/{case_id}/research-findings
GET  /api/v1/cases/{case_id}/research-findings/{finding_id}
POST /api/v1/cases/{case_id}/research-findings/{finding_id}/convert
POST /api/v1/cases/{case_id}/research-findings/{finding_id}/set-aside
POST /api/v1/cases/{case_id}/research-findings/{finding_id}/restore
DELETE /api/v1/cases/{case_id}/research-findings/{finding_id}
POST /api/v1/cases/{case_id}/research-findings/bulk-delete
```

A `review` endpoint tudatosan nem resze ennek a retegnek. A kutatasi talalat munkalista-elem; a review az atalakitas utan letrejott strukturalt objektumon tortenik.

### 7.3 Tiltasi szabaly

Ne maradjon csendes alias.

Ha regi modulnevet kuld valaki, az uj rendszerben legyen egyertelmu hiba:

```text
unsupported module
```

Ne legyen automatikus atiranyitas, mert az elfedne a regi workflow jelenletet.

## 8. Frontend kivezetesi terv

Eltavolitando:

- modul dropdown jelenlegi opcioi:
  - allitasok kinyerese,
  - esemenyek kinyerese,
  - entitasok kinyerese,
  - hianyzo iratok keresese,
  - osszefoglalo,
- modul-specifikus parameterek, amelyek csak ezekhez kellenek,
- modul-specifikus output panelek, ha csak a regi automatikus outputot mutatjak.

Uj UI irany:

```text
Kutatási keresés
```

Mezok:

- forraskor,
- dokumentum/taxonomia/oldal szurok,
- keresesi mod,
- szovegresz plafon,
- batch meret,
- fokuszszoveg,
- futtatas.

Kimenet:

```text
Kutatási találatok
```

Talalatonkent:

- cim,
- rovid magyarazat,
- tipusjavaslat,
- relevancia indoklas,
- source reference,
- felretetel / visszaallitas,
- torlesre jeloles / csoportos torles,
- strukturalt objektumma alakitas.

Panelhely:

```text
jobb oldali munkaterulet teteje, az Attekintesi jelentes folott
```

## 9. Service kod kivezetesi terv

Eltavolitando vagy atdolgozando service fajlok:

```text
app/services/analysis_module_claims.py
app/services/analysis_module_events.py
app/services/analysis_module_entities.py
app/services/analysis_module_missing_items.py
app/services/analysis_module_summaries.py
```

Uj service:

```text
app/services/analysis_module_findings.py
```

Megmarado kozos helper-ek, ha tenyleg hasznaltak:

```text
app/services/analysis_module_common.py
```

De ezt is tisztitani kell:

- csak a retrieval,
- batch,
- JSON parse/repair,
- source block epites,
- analysis run input helper maradjon,
- regi modulokra szabott fallback mar ne maradjon benne.

## 10. Tesztek kivezetesi terve

Eltavolitando vagy atirando tesztek:

- regi module_key-ek inditasat ellenorzo tesztek,
- regi promptszovegekre epitett tesztek,
- regi output schema tesztek,
- summary/missing item nyers chunk workflow tesztek.

Uj tesztek:

- finding prompt epites,
- finding JSON parse/repair,
- quote validation,
- source_label validation,
- suggested_type allowlist,
- unsupported findings kezelese,
- analysis run provenance,
- source reference letrehozas,
- finding felretetel / visszaallitas,
- egyedi es csoportos finding torles,
- finding -> claim conversion,
- finding -> event conversion,
- finding -> entity conversion,
- konvertalt finding eltunese az aktiv munkalistabol,
- `other` finding munkalista-szintu kezelese,
- regi module_key 422/400 hibaval elutasitasa.

## 11. Implementacios sorrend

### 11.1 Tervezes

1. `12_source_bound_findings_model_plan.md` veglegesitese.
2. Jelen kivezetesi terv veglegesitese.
3. Erintett dokumentumokban jelzes, hogy a regi modulalapu nyers kinyeres kivezetes alatt all.

### 11.2 Kod-elokeszites

1. Pontos route- es service-inventory keszitese.
2. Pontos frontend komponens-inventory keszitese.
3. Teszt-inventory keszitese.

### 11.3 Uj modell minimalis bevezetese

1. `research_findings` schema/migracio.
2. Finding service.
3. Finding analysis endpoint.
4. Finding list/detail/worklist API.
5. Minimal frontend panel.

### 11.4 Regi modulok levagasa

Csak akkor, amikor az uj minimal finding workflow mukodik:

1. Regi module_key-ek eltavolitasa az endpointbol.
2. Regi frontend modulopciok torlese.
3. Regi service fajlok torlese vagy tartalmuk teljes kivaltasa.
4. Regi tesztek torlese/atirasa.
5. Dokumentacio frissitese.

### 11.5 Strukturalt konverzio

1. Finding -> claim.
2. Finding -> event.
3. Finding -> entity.
4. Finding felretetel, visszaallitas es csoportos torles.

## 12. Atmeneti adatkezeles

A fejlesztoi adatbazisban mar letezhetnek regi automatikus claim/event/entity/summary/missing item objektumok.

Elv:

- nem torlunk torteneti adatot automatikusan,
- de nem hagyunk aktiv kodutat, amely uj regi-tipusu automatikus objektumot hoz letre,
- a UI jelezheti, ha egy objektum regi automatikus analysis runbol szarmazik,
- kesobb lehet kulon migracios/takaritasi dontes.

Ha tiszta fejlesztoi baseline kell, azt kulon, explicit adatbazis-reset vagy migracios dontessel kell kezelni.

## 13. Dokumentacios kivezetes

Frissitendo dokumentumok:

```text
README.md
AI_NOTES.md
CURRENT_STATE.md
CHANGELOG.md
Design_documents/05_api_design_v1.md
Design_documents/07_prompt_and_json_schema_collection_v1.md
Design_documents/08_mvp_backlog_and_implementation_sequence.md
Design_documents/10_analysis_batch_processing_plan.md
```

Nem kell mindent azonnal atirni, de minden regi modulalapu leirasnal legyen egyertelmu hivatkozas:

```text
Ez a nyers modulalapu kinyeresi modell kivezetes alatt all.
Az uj celmodell: Design_documents/12_source_bound_findings_model_plan.md
Kivezetesi terv: Design_documents/13_legacy_analysis_module_retirement_plan.md
```

## 14. Sikerfeltetelek

A kivezetes akkor tekintheto tisztanak, ha:

- a frontendbol nem indithato regi automatikus nyers modulextract,
- a backend nem fogad regi module_key-t,
- nincs nem hasznalt service kod a regi automatikus modulokhoz,
- a tesztek nem tartanak eletben regi workflow-t,
- az uj finding workflow forraskotott munkalista, amelybol audit es review alapu strukturalt objektum hozhato letre,
- a strukturalt objektumok letrehozasa emberi donteshez vagy finding-konverziohoz kotott.

## 15. Code Inventory - torteneti kivezetesi terkep

Ez a fejezet a 2026-05-20 koruli kodallapot alapjan rogziti, hol eltek a kivezetendo nyers automatikus modulok. 2026-05-22 utan ez torteneti bontasi terkep, nem aktualis aktiv kod-inventory.

### 15.1 Backend facade es module dispatch

Fo kapcsolo:

```text
app/services/analysis_modules.py
```

Jelenleg itt vannak importalva es dispatch-elve:

```text
run_extract_claims
run_extract_events
run_extract_entities
run_summarize_case
run_detect_missing_items
```

Itt elnek a regi module_key-ek:

```text
extract_claims
extract_events
extract_entities
summarize_case
detect_missing_items
```

Kivezetesi feladat:

- ezek a module_key-ek ne maradjanak aktiv dispatch agkent,
- helyettuk egy uj finding-alapu module_key legyen,
- regi module_key-re ne legyen alias vagy kompatibilitasi fallback.

### 15.2 Backend modulservice fajlok

Kivezetendo automatikus modulservice-ek:

```text
app/services/analysis_module_claims.py
app/services/analysis_module_events.py
app/services/analysis_module_entities.py
app/services/analysis_module_summaries.py
app/services/analysis_module_missing_items.py
```

Ezek tartalmazzak:

- modul promptokat,
- JSON repair / parse logikat,
- LLM hivasokat,
- quote validaciot,
- source reference letrehozast,
- strukturalt objektum automatikus letrehozast,
- analysis run input/output rogzitest.

Kivezetesi szabaly:

- a promptok es automatikus strukturalt objektum-persistalas torlendo vagy uj finding service-be atdolgozando,
- a hasznos altalanos reszek csak akkor maradjanak, ha tenylegesen az uj finding workflow hasznalja oket.

### 15.3 Megtartando kozos backend helper

Valoszinuleg megtartando, de tisztitando:

```text
app/services/analysis_module_common.py
```

Megtarthato reszek:

- `RetrievedChunk`,
- source chunk selection,
- retrieval query variants,
- batch split,
- batch metadata,
- source block epites,
- JSON object parse helper,
- analysis run input helper.

Tisztitando reszek:

- regi raw module szemantikahoz kotott elnevezesek,
- fallback vagy dokumentum-sorrend logika, ha mar nem hasznalt,
- olyan helper, amely csak kivezetett modul miatt maradna.

### 15.4 API route kapcsolodas

Fo analysis module API:

```text
app/api/v1/analysis_modules.py
```

Ez hivja a service facade-ot a `module_key` alapjan.

Kivezetesi feladat:

- a regi module_key-eket ne fogadja el,
- uj finding endpoint vagy uj `search_findings` module_key bevezetese,
- regi module_key-re egyertelmu hiba.

### 15.5 Schemakkal kapcsolatos erintett fajlok

Erintett:

```text
app/schemas/analysis_modules.py
```

Jelenleg tartalmazza:

- `AnalysisModuleRunRequest`,
- modul-specifikus response elemek:
  - `AnalysisModuleClaim`,
  - `AnalysisModuleEvent`,
  - `AnalysisModuleEntity`,
  - `AnalysisModuleSummaryItem`,
  - `AnalysisModuleMissingItemCandidate`,
- `AnalysisModuleRunResponse` tobb listaval.

Kivezetesi feladat:

- uj finding response schema,
- regi modulresponse-listak eltavolitasa az analysis module valaszbol, ha mar nincs aktiv regi modul,
- contradiction response kulon dontes alapjan maradhat vagy kulon schema agra kerulhet.

### 15.6 Strukturalt objektum service-ek

Megtartando, mert ezek emberi konverziobol vagy kezi workflow-bol tovabbra is kellenek:

```text
app/services/claims.py
app/services/events.py
app/services/entities.py
app/services/contradictions.py
```

Feltetelesen megtartando / kesobb ujragondolando:

```text
app/services/missing_items.py
app/services/summary_items.py
```

Indok:

- a missing item es summary objektumok nyers automatikus modulbol kivezetendok,
- de a mar letezo API/review/export/model reteg eltavolitasa kulon migracios dontes,
- elso korben az automatikus letrehozas megszuntetese a cel, nem a teljes adattortenet torlese.

### 15.7 Review report es export kapcsolodas

Erintett:

```text
app/services/review_report.py
app/services/exports.py
app/models/export.py
```

Jelenleg a review/export reteg kezeli:

```text
claim
event
entity
summary_item
missing_item_candidate
contradiction_candidate
```

Kivezetesi feladat:

- az uj `research_finding` ne jelenjen meg reviewolhato/exportalhato talalatkent,
- a review report es export a konverzio utan letrejott strukturalt objektumokat kezelje,
- summary/missing item megjelenites sorsarol kulon dontes kell,
- regi automatikus modulbol szarmazo objektumokat tortenetileg lehet mutatni, de uj automatikus letrehozas ne maradjon.

### 15.8 Analysis run output osszegzes

Erintett:

```text
app/services/analysis_runs.py
```

Jelenleg output summary-t ad:

```text
claim
event
entity
summary_item
missing_item_candidate
contradiction_candidate
source_reference
chunk
```

Kivezetesi feladat:

- `research_finding` output summary bevezetese,
- regi summary/missing item output summary sorsa a modelldontessel egyutt kezelendo,
- analysis history tovabbra is tudja megjeleniteni a regi futasokat, ha torteneti adat marad.

### 15.9 Frontend fo kapcsolodasok

Fo fajl:

```text
frontend/src/App.tsx
```

Jelenlegi kapcsolodasok:

- `modules` lista tartalmazza:
  - `extract_claims`,
  - `extract_events`,
  - `extract_entities`,
  - `summarize_case`,
  - `detect_missing_items`,
- `labelModule` magyar neveket ad ezekhez,
- `moduleKey` state a regi modulvalasztot hajtja,
- `isRawChunkModule` logika ezekre epul,
- `runAnalysis(selectedCaseId, moduleKey, payload)` hivja a regi endpointot,
- analysis output count a regi response listakbol szamol:
  - `claims`,
  - `events`,
  - `entities`,
  - `summary_items`,
  - `missing_item_candidates`.

Kivezetesi feladat:

- modul dropdown helyett `Kutatási keresés` workflow,
- finding output lista,
- finding munkalista panel,
- finding felretetel / visszaallitas / torles / konverzio muveletek,
- regi modulopciok teljes eltavolitasa.

### 15.10 Frontend API reteg

Erintett:

```text
frontend/src/api.ts
```

Jelenleg:

- `runAnalysis(caseId, moduleKey, payload)` altalanos regi module_key endpointot hiv,
- `AnalysisResponse` tartalmazza a regi output listakat,
- review endpoint allowlist kezeli `summary_item` es `missing_item_candidate` tipust is.

Kivezetesi feladat:

- uj finding API tipusok,
- uj `runFindingSearch` vagy hasonlo kliensfuggveny,
- regi modulresponse mezok eltavolitasa, ha mar nincs aktiv regi modul,
- summary/missing item review endpoint sorsa kulon dontes.

### 15.11 Teszt inventory

Fo erintett fajl:

```text
tests/test_analysis_modules.py
```

Jelenlegi regi modul tesztek:

- prompt builder tesztek:
  - claim,
  - event,
  - entity,
  - summary,
  - missing item,
- source selection es batching tesztek,
- summary item validacio,
- missing item candidate validacio,
- contradiction claim-pair tesztek.

Kivezetesi feladat:

- source selection / batching kozos tesztek megtarthatok es findingra atirhatok,
- regi prompt builder tesztek torlendok vagy finding prompt teszte valnak,
- summary/missing item automatikus validacio tesztek torlendok, ha nincs automatikus modul,
- contradiction tesztek maradnak, mert downstream claim-pair workflow.

Kulon tesztfajlok, amelyek nem feltetlenul torlendok:

```text
tests/test_summary_items.py
tests/test_missing_items.py
tests/test_review_report.py
tests/test_exports.py
tests/test_manual_entries.py
```

Ezek strukturalt objektum/review/export/manual reteghez tartoznak, nem csak automatikus modulokhoz. Sorsuk kulon dontendo.

### 15.12 Modellek es adatbazis check constraint erintes

Erintett:

```text
app/models/analysis.py
app/models/review.py
app/models/export.py
```

Jelenleg check constraint szinten is szerepelhetnek regi run/output/object tipusok.

Kivezetesi feladat:

- uj `research_finding` output/object tipus hozzaadasa migracioval,
- regi analysis run type-ok torlese csak akkor, ha a torteneti adatok kezelese eldontott,
- ha regi run type-ok torteneti okbol maradnak, ne legyen aktiv endpoint, amely uj ilyen runt hoz letre.

### 15.13 Javasolt elso implementacios szelet

Kovetkezo kis szelet:

```text
Research finding schema + migration + minimal service skeleton
```

Tartalma:

- `research_findings` tabla,
- source reference kapcsolat,
- conversion/worklist status mezok,
- opcionlis `target_object_type` / `target_object_id` vagy kesobbi kapcsolattablara bovitheto konverzios kapcsolat,
- schema osztalyok,
- minimal list/detail API,
- teszt quote/source kotelezosegre.

Meg nem tartalmazza:

- regi modulok torleset,
- teljes frontend atalakitasat,
- finding LLM promptot,
- konverziot claim/event/entity objektumma.

Indok:

Elobb legyen stabil uj celobjektum, utana lehet biztonsagosan levagni a regi automatikus modulokat.

Graf-kompatibilitasi megjegyzes:

Az elso szelet ne vezessen be graf-adatbazist, de a `research_findings` modell ne zarja ki a kesobbi kapcsolatgrafot. A finding es a belole letrejovo strukturalt objektum kapcsolatat meg kell tudni orizni, mert kesobb ebbol epulhet:

```text
source_reference -> research_finding -> claim/event/entity/other
```

Ha az elso implementacio kozvetlen celmezokkel indul, azt ugy kell megtervezni, hogy kesobb `research_finding_links` jellegu kapcsolattablava bovitheto legyen adattisztitas nelkul.
