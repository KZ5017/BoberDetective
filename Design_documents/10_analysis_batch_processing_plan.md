# 10. Analysis Batch Processing Plan

## 1. Cel

A kovetkezo fejlesztes celja, hogy az elemzesi modulok ne csak fokuszalt query alapjan valasszanak ki nehany chunkot, hanem kesobb teljes dokumentumon vagy teljes ugyon is tudjanak dolgozni, batchekre bontva.

Az elso implementacios cel:

```text
extract_claims batch-kepes futtatasa tobb dokumentumchunkon
```

Ez azert jo elso modul, mert az allitasok kesobbi elemzesek alapjai, kulonosen az ellentmondasjeloltek keresesehez.

## 1.1 Implementacios allapot

Elso backend szelet elkeszult:

- `AnalysisModuleRunRequest` bovult `source_mode`, `document_id`, `max_chunks`, es `batch_size` mezokkel.
- A `focused_query` mod visszafele kompatibilis alapertelmezett maradt.
- Letrejott a kozos forraschunk-valasztas `focused_query`, `document`, es `case` modokra.
- Letrejott a determinisztikus chunk batch-eles es batch metaadat mentese az analysis run inputokhoz.
- Az `extract_claims` tobb batchen fut, egy parent analysis run alatt.
- Az `extract_events` tobb batchen fut, egy parent analysis run alatt.
- Az `extract_entities` tobb batchen fut, egy parent analysis run alatt.
- A `summarize_case` tobb batchen fut, egy parent analysis run alatt, batchenkent legfeljebb 3 summary itemmel.
- A `detect_missing_items` tobb batchen fut, egy parent analysis run alatt.
- Az `extract_claims` in-run exact dedupot hasznal ugyanazon chunk, quote es claim szoveg szerint.
- Az `extract_events` in-run exact dedupot hasznal ugyanazon chunk, quote es event title szerint.
- Az `extract_entities` in-run exact dedupot hasznal ugyanazon chunk, quote, canonical name es surface text szerint.
- A `summarize_case` in-run exact dedupot hasznal ugyanazon chunk, quote, title es body text szerint.
- A `detect_missing_items` in-run exact dedupot hasznal ugyanazon chunk, quote, referenced item text es description szerint.

Kovetkezo validacios lepes:

- valos dokumentumos live smoke az extract_claims -> contradiction candidate utvonalra,
- frontend review report ellenorzes valosabb adatokon,
- batch meretek es max chunk guardrail finomhangolasa a nyers chunk moduloknal.

Live smoke allapot:

- `document` source mode 5 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `case` source mode 6 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- Az analysis run inputokban latszik a `batch_index`, `batch_count`, `chunk_labels`, `source_label`, es `retrieval_score`.
- `extract_events` `document` source mode 5 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `extract_events` `case` source mode 4 chunkot valasztott ki, 2 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `extract_entities` `document` source mode 5 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `extract_entities` `case` source mode 4 chunkot valasztott ki, 2 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `summarize_case` `document` source mode 5 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `summarize_case` `case` source mode 4 chunkot valasztott ki, 2 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `detect_missing_items` `document` source mode 5 chunkot valasztott ki, 3 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `detect_missing_items` `case` source mode 4 chunkot valasztott ki, 2 batchben futott `batch_size=2` mellett, es `validation_status=passed` eredmennyel zart.
- `detect_contradiction_candidates` ures/precondition smoke: 0 source-valid claim eseten `HTTP 200`, `validation_status=warning`, 0 jelolt, es `input_kind=claim_selection` metadata kerult az analysis run inputok koze.
- `detect_contradiction_candidates` claim-gazdag pair-selection smoke: fokuszalt query 8 claimet kert le, 6 claimet talalt fokusz szerint, 8 backend-altal kivalasztott part adott a promptba, majd 2 source-cited `time_conflict` jeloltet adott vissza.
- `detect_contradiction_candidates` quality smoke: time-conflict jeloltek determinisztikus, konzervativ cimmel/leirassal, claim-parhoz kotott szoveggel es `medium` severity mellett mentodtek.
- Frontend build passed after claim-pair UI support: analysis run details show claim-selection metrics and selected pairs, contradiction summaries show claim-pair based execution, and review report items mark candidates as review-only.
- `claim_review_scope` bekerult az ellentmondas modulba: az alapertelmezett `reviewable` kor kizarta az elutasitott claim-eket, de engedi a `new`, `needs_review`, `verified`, es `corrected` source-valid claim-eket. A frontendben ez `Allitaskor` mezokent valaszthato.
- Az ellentmondas modul explicit kvalifikacios kaput kapott: mentett jelolthez `is_contradiction_candidate=true` es konkret `conflict_basis` kell; a csak kontextualisan osszefuggo, de nem utkozo parok unsupported itemkent maradnak.

## 2. Jelenlegi allapot

A jelenlegi elemzesi modell:

```text
query + module + limit
-> keyword chunk retrieval
-> legfeljebb limit chunk
-> egy LLM hivas
-> forrasidezet-validalas
-> objektumok mentese
```

Fontos korlatok:

- `query` jelenleg kotelezo.
- `limit` jelenleg 1-20 kozott lehet.
- A chunk alapu modulok egyszerre legfeljebb `limit` chunkot tesznek a promptba.
- A modulok promptjai jellemzoen legfeljebb 5 kimenetet kernek.
- Nincs meg batch runner.
- Nincs meg teljes dokumentum / teljes ugy mod.
- Az `detect_contradiction_candidates` kulon eset: az nem nyers chunkokon, hanem korabbi source-cited claim objektumokon dolgozik.
- Ha kettonel kevesebb source-valid claim erheto el, az ellentmondas modulnak figyelmeztetessel kell zarnia, LLM-hivas nelkul.
- A modul backend oldalon determinisztikus claim parokat valaszt, `pair_limit` korlattal, opcionalis ertelmes fokuszszuressel, es az LLM valaszban csak a kivalasztott parokra hivatkozo jelolteket fogadja el.
- Mentes elott a jelolteket minosegi szures is vedi: ugyanazon claim-par/type duplikatumai kiesnek, a legtobb modellbol jovo `high` severity `medium` szintre korlatozodik, a cim/leiras pedig konzervativ, claim-parhoz kotott backend-szoveg lesz.

## 3. Fo tervezesi dontes

Ne legyen ket kulon feldolgozasi vilag.

Ne ez legyen:

```text
A) regi query alapu elemzes
B) uj teljes dokumentumos elemzes
```

Hanem legyen egy kozos pipeline:

```text
source selector
-> chunk batcher
-> module batch runner
-> LLM JSON parse
-> source quote validation
-> persistence
-> review/audit/run outputs
```

A fokuszalt query alapu elemzes ennek csak egy source selection modja legyen.

## 4. Source selection modok

Tervezett modok:

### 4.1 `focused_query`

A jelenlegi mukodes folytatasa.

Input:

- `query`
- `limit`

Mukodes:

- keyword search chunkokra,
- magyar query variansok,
- fallback case chunks, ha nincs talalat.

### 4.2 `document`

Egy konkret dokumentum osszes aktualis chunkja.

Input:

- `document_id`
- opcionails `query` kesobb csak szuro/fokusz szerepben
- `max_chunks`

Mukodes:

- `document_chunks.is_current = true`
- `document_id` szerint szurve
- `chunk_index` sorrendben

### 4.3 `case`

Az ugy osszes aktualis chunkja.

Input:

- `case_id`
- opcionails `query` kesobb csak szuro/fokusz szerepben
- `max_chunks`

Mukodes:

- `document_chunks.is_current = true`
- dokumentum import ideje + chunk index sorrend

## 5. Batch logika

Az elso verzio legyen konzervativ:

```text
default_batch_size = 5 chunk
default_max_chunks = 50 chunk
```

Azert nem nagyobb, mert:

- a lokalis LLM context limit veges,
- a promptban teljes chunk szovegek mennek,
- a quote-validalasnak karakterpontosnak kell maradnia,
- a hosszu futasoknal kesobb kulon progress/status kellhet.

A batcher determinisztikusan dolgozzon:

```text
selected chunks -> [batch_1, batch_2, ...]
```

Minden batch kapjon stabil metaadatot:

- `batch_index`
- `batch_count`
- `chunk_ids`
- `chunk_labels`

## 6. Analysis run es audit dontes

Elso implementaciohoz nem szukseges uj adatbazis tabla vagy migracio.

Indok:

- `analysis_runs.input_parameters` JSONB-ben el tudja tarolni:
  - `source_mode`
  - `document_id`
  - `query`
  - `max_chunks`
  - `batch_size`
  - `batch_count`
- `analysis_run_inputs.payload_json` el tudja tarolni chunk inputnal:
  - `source_label`
  - `batch_index`
  - `retrieval_score`
- `analysis_run_outputs` mar tud `claim` es `source_reference` outputot tarolni.
- `finish_analysis_run.output_summary` tarolhatja:
  - `batch_count`
  - `processed_batch_count`
  - `failed_batch_count`
  - `created_claim_count`
  - `duplicate_skipped_count`
  - `historical_duplicate_skipped_count`
  - `unsupported_count`

Megvalositott kiegeszites:

- A batch-futason beluli deduplikacio mellett a modulok torteneti deduplikaciot is vegeznek a perzisztalas elott.
- Azonos ugy + azonos objektumtipus + azonos normalizalt tartalom eseten a rendszer kihagyja a mar rogzitett claim/event/entity/summary/missing item/contradiction objektum ujra letrehozasat.
- Ez nem valtja ki az emberi review dontest, csak megakadalyozza, hogy ismetelt futtatasok ugyanazt a review objektumot sokszorozzak.
- Entitasoknal az exact/normalizalt egyezes automatikusan a meglevo entitashoz kapcsol uj mention/source elofordulast.
- Nem egyertelmu entitas-azonossag eseten a rendszer ne talalgasson: a felhasznalo explicit `Osszevonas` review muvelettel donthet.
- Esemenyeknel az explicit `Osszevonas` review muvelet a forraslinkeket a cel esemenyhez kapcsolja, a forras esemenyt `corrected` allapotba teszi, es audit es review bejegyzeseket rogzit.
- Hianyzo irat jelolteknel az explicit `Osszevonas` review muvelet a forraslinkeket a cel jelolthoz kapcsolja, a forras jeloltet `corrected` allapotba teszi, es audit es review bejegyzeseket rogzit.
- Entitas, esemeny es hianyzo irat jelolt eseteben a hibasan csatolt forras explicit `Levalasztas` review muvelettel eltavolithato az objektumrol; ez nem torli az eredeti iratot vagy source reference-t, csak az objektum-forras kapcsolatot, es audit/review bejegyzest hagy maga utan.
- A levalasztott forraslinkek `detached_source_items` rekordkent parkolnak tovabbi emberi dontesre: megorzodik a source reference, a levalasztas pillanataban latott objektum-snapshot, a megjegyzes es a kezelesi allapot.
- A parkolt forras kesobb visszacsatolhato azonos objektumtipusu celhoz vagy irrelevansnak jelolheto. Ha a felhasznalo mar a forras reszleteinel tudja a helyes celobjektumot, ugyanaz a koncepcio direkt `Athelyezes` muvelettel is elerheto, kulon kezi parkolasi kor nelkul.
- Kezi rogzitessel is letrehozhato forrashoz kotott claim/entity/event/missing item candidate: a felhasznalo dokumentumchunkbol jelol ki idezetet, a frontend readonly forras-elonezetet mutat, a backend pedig source reference validacioval es `manual_entry` analysis run provenance-szal rogzit.
- Ugyanez a kezi rogzitessel letrehozott objektum workflow levalasztott forrasbol is indithato; ilyenkor a meglevo source reference marad az alap, es a parkolt forras a letrehozott objektumra mutato kezelt celadatot kap.

Kesobbi migracio akkor kellhet, ha:

- kulon child run / batch run tortenet kell,
- progress UI kell batchenkent,
- batch retry kell,
- reszleges futas folytatasa kell.

## 7. Elso modul: `extract_claims`

### 7.1 Javasolt elso backend API bovites

A jelenlegi endpoint megtarthato:

```text
POST /api/v1/cases/{case_id}/analysis/modules/{module_key}
```

A request schema bovulhet visszafele kompatibilisen:

```json
{
  "query": "opcionalis fokusz",
  "limit": 5,
  "source_mode": "focused_query",
  "document_id": null,
  "max_chunks": 50,
  "batch_size": 5
}
```

Kompatibilitas:

- Ha `source_mode` nincs megadva, legyen `focused_query`.
- `focused_query` modban a `query` tovabbra is legyen kotelezo az elso lepesben.
- `document` es `case` modban a `query` lehessen ures vagy `null`.
- A frontend atalakitas kesobb kovesse ezt.

### 7.2 Modulon beluli flow

```text
start parent analysis_run
-> select source chunks
-> add chunk inputs batch metadata-val
-> split into batches
-> foreach batch:
     build SOURCE block csak a batch chunkjaibol
     LLM hivas
     JSON parse
     quote validation
     exact dedup
     source_reference + claim persistence
     add outputs
-> finish parent analysis_run
```

### 7.3 Dedup elso verzio

Minimalis exact dedup:

```text
dedup_key = (chunk_id, normalized_quote_text, normalized_claim_text)
```

Normalizalas csak technikai whitespace/casefold lehet.

Ne legyen szemantikus dedup az elso korben, mert az LLM vagy embedding alapu hasonlosag uj kockazatot vinne be.

## 8. Hibakezeles

Elso verzios javaslat:

- Ha nincs kivalasztott chunk: run `failed`.
- Ha egy batch LLM valasza invalid JSON: batch issue bekerul `output_summary.batch_errors` ala.
- Ha legalabb egy batch sikeres es van valid kimenet: parent run `succeeded`, `validation_status=warning`, ha volt batch hiba.
- Ha minden batch hibas: parent run `failed`.
- Ha nincs valid kimenet, de a batch futasok technikailag sikeresek: parent run `succeeded`, `validation_status=warning`.

Minden AI output tovabbra is csak valid forrasidezet mellett mentheto.

## 9. Biztonsagi es szakmai korlatok

Maradnak a kotelezo szabalyok:

- A modell nem forrasigazsag.
- No source -> no claim.
- Csak eredeti dokumentum / page / chunk / source reference lehet forras.
- LLM JSON untrusted input.
- Quote text karakterpontosan validalando chunk ellen.
- Nem lehet autonom jogi/nyomozati dontes, bunosseg, felelosseg vagy kockazati pontszam.
- Nem vezetunk be cloud dependencyt.

## 10. Fajlszintu implementacios terv

Elso implementacios lepesek:

1. `app/schemas/analysis_modules.py`
   - `AnalysisModuleRunRequest` bovites:
     - `query: str | None`
     - `source_mode`
     - `document_id`
     - `max_chunks`
     - `batch_size`

2. `app/services/analysis_module_common.py`
   - source selection tipusok/helper:
     - `select_analysis_chunks(...)`
     - `select_focused_query_chunks(...)`
     - `select_document_chunks(...)`
     - `select_case_chunks(...)`
   - batch helper:
     - `chunk_batches(...)`
   - input recording helper batch metadata-val.

3. `app/services/analysis_module_claims.py`
   - `extract_claims` atallitasa batch runnerre.
   - Regi focused query mod megorzese kompatibilisen.
   - Exact dedup.
   - Batch summary az analysis run output summaryben.

4. `tests/test_analysis_modules.py`
   - source selection helper unit tesztek.
   - batch splitter tesztek.
   - dedup teszt.
   - request schema kompatibilitasi teszt.

5. Integracios teszt kesobb
   - teljes dokumentum tobb chunkkal,
   - fake/mock LLM valasz batchenkent,
   - tobb claim mentese,
   - analysis run inputs/outputs ellenorzese.

## 11. Frontend terv kesobbre

Csak azutan, hogy a backend bizonyitott.

Javasolt UI fogalmak:

- `Forraskor`
  - Fokuszalt kereses
  - Kivalasztott dokumentum
  - Teljes ugy
- `Fokusz / keresokifejezes`
  - csak fokuszalt modban kotelezo
  - document/case modban opcionails
- `Max. forrasresz`
  - a mostani limit pontosabb neve
- `Batch meret`
  - kezdetben rejtett vagy advanced

## 12. Kovetkezo konkret lepes

Kovetkezo konkret lepes: valos dokumentumos live smoke az extract_claims -> contradiction candidate utvonalra.

```text
document/case-scope extract_claims
detect_contradiction_candidates
frontend review report ellenorzes
selected pair metadata visszakovetes
```

Ezutan lehet valos dokumentumon ujra live-smoke-olni a teljes extract_claims -> contradiction candidate utvonalat.
