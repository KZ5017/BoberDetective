# 15. Full Document Processing Plan

## 0. Aktualisitas

Frissitve: 2026-05-30.

Ez a dokumentum a `Teljes iratfeldolgozás` munkafelület backend-szerzodeset, aktualis implementalt allapotat es kovetkezo iranyait rogziti.

Kapcsolodo dokumentumok:

- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`
- `Design_documents/12_source_bound_findings_model_plan.md`
- `Design_documents/13_legacy_analysis_module_retirement_plan.md`
- `Design_documents/29_full_document_free_question_plan.md`

Aktualis UI allapot:

```text
AppShell / munkafelület-valto kesz
Ügy munkapad = jelenlegi munkapad
Teljes iratfeldolgozás = backendhez kotott munkafelület
Audit napló = placeholder
```

A `Teljes iratfeldolgozás` feluleten mar van:

- aktiv irat kereses/valasztas,
- feldolgozasi profil valasztas,
- kivalasztott irat osszefoglalo,
- oldaltol/oldalig tartomanyvalasztas,
- futtatas inditasa,
- utolso futas validacios osszegzese,
- aktiv es felretett munkalista nezet,
- munkadarab felretetele es visszaallitasa,
- nev alapu munkalista szures,
- egyedi es osszes lathato torlesre jeloles,
- csoportos soft delete,
- egy soros forrasbizonyitek megjelenitese,
- `Egyedi` / `Többször előforduló` jeloles,
- ajanlott fokusz atadasa az `Ügy munkapad` `search_findings` workflow-jaba.

A nagyugyes tarolasi/retrieval kapu elso kritikus szeletei mar megvalosultak: a teljes page/chunk szoveg a data-root text store-bol olvashato, es a regi DB text oszlopok ki vannak vezetve. A teljes iratfeldolgozas jelenlegi szelete erre a text-store alapra epul.

## 1. Cel

A teljes iratfeldolgozas celja nem ugyanaz, mint a `search_findings` workflow celja.

`search_findings`:

```text
QUERY -> relevans szovegreszek -> kutatasi talalat munkalista
```

`Teljes iratfeldolgozás`:

```text
teljes irat -> ujrahasznosithato keresesi / entitas / szemely munkadarabok
```

Az elso cel:

- teljes, osszefuggo iratbol szemelyek es entitasok kinyerese,
- rovid, forrashu leiras keszitese,
- nevvaltozatok / emlitesi formak gyujtese,
- keresesi fokuszjavaslatok generalasa,
- kesobbi atadas a kutatasi talalat workflow-nak.

## 2. Nem cel

Nem cel:

- automatikusan strukturalt `claim`, `event`, `entity` objektumokat letrehozni,
- automatikusan review report elemeket letrehozni,
- a `search_findings` workflow kivaltasa,
- forras nelkuli szemely- vagy entitasadatok mentese,
- teljes dokumentum osszefoglalot gyartani altalanos celra,
- jogi vagy nyomozati kovetkeztetest levonni.

Kotelezo elv:

```text
No source -> no claim.
```

Ez itt is ervenyes, de a kimenet elso korben nem claim, hanem feldolgozasi munkadarab.

## 3. Uj munkadarab fogalom

Javasolt technikai nev:

```text
document_processing_item
```

Magyar UI nev:

```text
Iratfeldolgozási munkadarab
```

Ez nem azonos:

- `research_finding`,
- `claim`,
- `event`,
- `entity`,
- `missing_item_candidate`,
- `audit_event`.

Indok:

A `research_finding` egy query-alapu talalat. A teljes iratfeldolgozas viszont query nelkul vagy profil-alapu instrukcioval dolgozik, es keresesi alapanyagot keszit. Ha ezt kozvetlenul `research_finding`-kent mentenenk, osszemosnank a ket workflow jelentest.

Javasolt workflow:

```text
teljes iratfeldolgozas -> document_processing_item -> emberi dontes -> keresesi fokusz / kutatasi talalat / strukturalt objektum
```

## 4. Elso profilok

### 4.1 `person_search_seeds`

UI:

```text
Személyek és keresési fókuszok
```

Feladat:

- szemelyek kinyerese,
- rovid, hasznalhato keresesi fokusz keszitese,
- forrasoldal megadasa, ahol a modell szerint a nevalak szerepel.

Aktualis implementacios szabaly:

- az LLM csak `display_label`, `recommended_search_focus` es `source_label` mezoket ad vissza,
- a prompt nem ker `short_description`, `unsupported_items`, idezetet, emlitesi formakat vagy kapcsolatokat,
- a `recommended_search_focus` rovid keresesi kifejezes: `display_label` + 1-4 forrasbeli megkulonbozteto szo, nem mondat es nem osszefoglalo,
- a backend validalja, hogy a nev megtalalhato-e a megadott vagy kivalasztott forrasoldalakon,
- ha a nev nem talalhato, az elem nem torlodik: ugyanabba a munkalistaba kerul, ures `source_evidence_json` ertekkel es `Nem megerősített` frontend jelzessel.
- ha az LLM rossz `source_label` erteket ad, a backend eloszor a megadott oldalon keres, majd a teljes kivalasztott oldaltartomanyon belul megkeresi a validalt nevalakot es a tenyleges talalati oldalt menti.

Peldak kimeneti mezokre:

```text
display_label
recommended_search_focus
source_label
```

### 4.2 Nem-szemely profilok allapota

Az eredetileg tervezett `entity_search_seeds` profil ki lett vezetve az aktiv backendbol es frontendbol.

Indok:

- a jelenlegi kompakt prompt szemelyekre lett stabilizalva,
- szervezetek, helyek, idopontok, hivatkozasok es mellekletek kinyerese mas, gondosabb profiltervezest igenyel,
- felkesz, pontatlan profil ne maradjon valaszthato vagy kodszemetkent az aktiv workflow-ban.

Ha kesobb nem-szemely teljesirat-profil kell, azt uj tervezesi korben kell visszahozni, kulon prompttal es validacios szerzodessel.

### 4.3 `free_document_question`

Uj profil elso implementacios szelete:

```text
Szabad iratkérdés
```

Ez nem `document_processing_item` munkalistat gyart, hanem a kivalasztott
irat/oldaltartomany es felhasznaloi kerdes alapjan egy tartos iratvalaszt.

Reszletes terv:

```text
Design_documents/29_full_document_free_question_plan.md
```

Fontos dontes:

- a szemelyprofil marad person-only munkalista,
- a szabad iratkerdes kulon `full_document_answers` adatmodellre epul,
- a ket eredmeny UI-ban is profilfuggoen jelenik meg:
  - `Előkészített munkalista`,
  - `Iratválasz`.

Elso szelet allapota:

- backend modell/migracio/API kesz,
- full-document run endpoint profilfuggoen kezeli,
- frontend kerdesmezo es `Iratválasz` panel kesz,
- tovabbi UX/prompt finomitas csak konkret live hiba vagy minosegi problema alapjan tortenjen.

## 5. Javasolt adatmodell

Elso migracios szint:

```text
document_processing_items
```

Mezok:

```text
id
case_id
document_id
analysis_run_id
profile_key
item_kind
display_label
short_description
mentioned_forms_json
source_supported_details_json
relationships_json
recommended_search_focus
alternative_search_focuses_json
source_evidence_json
work_status
target_object_type
target_object_id
created_at
updated_at
```

### 5.1 `profile_key`

Engedelyezett ertekek elso korben:

```text
person_search_seeds
```

### 5.2 `item_kind`

Nem vegleges strukturalt objektumtipus, hanem munkadarab-jelleg:

```text
person
```

Ez kesobb grafnezethez is hasznos lehet, de nem jelent automatikus `entity` rekordot.

### 5.3 `source_evidence_json`

Kotelezo, legalabb egy elem.

Javasolt alak:

```json
[
  {
    "page_id": "...",
    "page_number": 7,
    "quote_text": "Pauline Dubourg, mosónő...",
    "quote_char_start": 912,
    "quote_char_end": 1040
  }
]
```

Elso korben a teljes iratfeldolgozas oldal-szintu vagy oldal+karakter offset bizonyitekot hasznalhat. Kesobb ezekbol letrehozhato konkret `source_reference`.

### 5.4 `work_status`

Javasolt ertekek:

```text
active
set_aside
converted
deleted
```

A `deleted` csak soft státusz vagy valodi torles lehet. Elso korben egyszerubb:

- aktiv lista,
- felretetel,
- torles.

Ha munkadarabbol strukturalt objektum keszul, `converted` statuszba kerul.

## 6. Analysis run kapcsolat

Uj run type javaslat:

```text
full_document_processing
```

Az `analysis_runs` rogzitse:

- `case_id`,
- `run_type=full_document_processing`,
- `input_parameters`:
  - `document_id`,
  - `profile_key`,
  - prompt verzio,
  - modell,
  - teljes oldalszam / karakter mennyiseg,
- statusz,
- validation statusz.

`analysis_run_inputs`:

- legalabb dokumentum input,
- oldal inputok a kivalasztott oldaltartomany aktualis, nem ures oldalaihoz. **A run-start szeletben egy futtatas egy LLM-keres: a kivalasztott oldaltartomany egyszerre megy ki.**

`analysis_run_outputs`:

- letrejott `document_processing_item` rekordok.

## 7. API szerzodes

### 7.1 Profilok listazasa

```http
GET /api/v1/full-document-processing/profiles
```

Valasz:

```json
{
  "data": [
    {
      "key": "person_search_seeds",
      "label": "Személyek és keresési fókuszok",
      "description": "Teljes iratból személyeket és keresési fókuszokat készít elő."
    }
  ]
}
```

Elso korben ez lehet frontend-konstans is, de backendrol listazva tisztabb lesz a kesobbi profilbovites.

### 7.2 Futtatas inditasa

```http
POST /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/runs
```

Payload:

```json
{
  "profile_key": "person_search_seeds",
  "page_start": 1,
  "page_end": 12
}
```

Valasz:

```json
{
  "analysis_run_id": "...",
  "document_id": "...",
  "profile_key": "person_search_seeds",
  "created_item_count": 12,
  "unsupported_count": 1,
  "validation_status": "warning",
  "items": [],
  "unsupported_items": []
}
```

Elso implementalt szeletben a futas szinkron. A service a kivalasztott oldaltartomany aktualis oldalait egyetlen LLM-keresben kuldi ki. Az aktualis prompt nem ker karakterpontos idezetet az LLM-tol: a modell `display_label`, `recommended_search_focus` es `source_label` mezot ad, a backend pedig a megadott vagy kivalasztott oldalakon megkeresi a `display_label` forrasbeli alakjat, es ebbol epiti a mentett `source_evidence` mezot. Ha a nevalak nem validalhato, az elem nem veszik el, hanem nem megerositett munkalista-elemkent marad kezelheto.

Aktualis JSON feldolgozasi megjegyzes, 2026-06-07:

- az LLM valasz eloszor a kozos JSON parseren megy at,
- ha ez elhasal belso, nem escape-elt dupla idezojel miatt, a teljes iratfeldolgozas sajat, sémaspecifikus fallback parsert hasznal,
- ez a fallback csak az aktualis minimalis items alakot probalja visszanyerni: `item_kind`, `display_label`, `recommended_search_focus`, `source_label`,
- a recovered elemek nem kerulik meg a forrasvalidaciot; ugyanugy lefut rajtuk a page/source-label korrekcio, display-label keresese es nem megerositett munkalista-logika.

Pelda kezelt hibatipus:

```json
{"items":[{"item_kind":"person","display_label":"Mademoiselle Camilla L"Espanaye","recommended_search_focus":"Mademoiselle Camilla L"Espanaye áldozat","source_label":"page_6"}]}
```

Ez JSON-kent hibas, de a mezosorrendhez kotott fallback vissza tudja nyerni a jeloltet, majd a backend validacio donti el, hogy a forrasban igazolhato-e.

Kesobbi nagyobb iratokhoz jobb lehet a hatterjob-szeru modell:

```text
POST -> run id
GET run detail/status -> progress/output
GET items -> munkalista
```

### 7.3 Munkadarabok listazasa

```http
GET /api/v1/cases/{case_id}/documents/{document_id}/full-document-processing/items
```

Opcionalis query:

```text
profile_key
work_status
item_kind
search
```

### 7.4 Munkadarab felretetele / visszaallitasa / torlese

```http
PATCH /api/v1/cases/{case_id}/full-document-processing/items/{item_id}
```

Payload:

```json
{
  "work_status": "set_aside"
}
```

Torlesnel elso korben lehet valodi torles, mert ez munkalista jellegu elokeszito adat. Ha mar konvertalt, ne legyen torolheto vakon.

Aktualis implementacio:

- az egyedi `PATCH` kezeli az `active`, `set_aside`, `deleted` statuszvaltast,
- a frontend nem torol azonnal kartyarol, hanem elobb torlesre jelol,
- a tenyleges csoportos soft delete a munkalista toolbarbol indul.

```http
POST /api/v1/cases/{case_id}/full-document-processing/items/bulk-delete
```

Payload:

```json
{
  "item_ids": ["..."]
}
```

Valasz:

```json
{
  "deleted_count": 3
}
```

### 7.5 Keresesi fokusz atadasa

Ez elso korben lehet frontend muvelet:

```text
recommended_search_focus -> Elemzés panel fókusz mező
```

Kesobb backend alapu muvelet is lehet:

```http
POST /api/v1/cases/{case_id}/full-document-processing/items/{item_id}/create-research-finding-search
```

De ez nem elso implementacios cel.

## 8. Prompt szerkezet

A teljes iratfeldolgozas promptja ne legyen azonos a `search_findings` prompttal.

Rendszerszintu cel:

- angol instrukcio,
- magyar forrasszoveg,
- magyar kimeneti felhasznaloi mezok,
- nincs kulso tudas,
- nincs kovetkeztetett jogi/nyomozati minosites.

Aktualis rendszerprompt:

```text
You are a source-faithful investigative document processing component.
You work with Hungarian source documents.
The source document is the only source of truth.
Do not use outside knowledge.
Do not infer guilt, responsibility, legal qualification, risk, or personal blame.
Return only a valid JSON object.
```

Aktualis user task lenyege:

```text
Add vissza JSON formában a szereplőket.
A display_label értéke kizárólag és pontosan a forrásban szereplő névalak legyen.
A recommended_search_focus rövid keresési kifejezés legyen: display_label + 1-4 forrásbeli szó.
A recommended_search_focus nem mondat, nem összefoglaló, nem idézet és nem felsorolás.
Minden szereplőhöz add meg annak a SOURCE-ban szereplő page_ címkének a source_label értékét, ahol a display_label névalak szerepel.
```

Elvart JSON:

```json
{
  "items": [
    {
      "item_kind": "person",
      "display_label": "...",
      "recommended_search_focus": "...",
      "source_label": "page_..."
    }
  ]
}
```

Az LLM altal adott minimalis forma utan a backend tolti ki a belso munkadarab-mezoket es a forrasbizonyitekot. Ez szandekosan kevesebb munka az LLM-nek, mert a korabbi reszletes schema, `short_description`, `unsupported_items` es quote-generaltatas hajlamos volt lassu, ismetlo vagy ervenytelen JSON kimenetet okozni.

## 9. Source handling

A teljes iratfeldolgozasnal kulon problema, hogy a bemenet nem egy chunk batch, hanem oldalak osszefuggo szovege.

Elso biztonsagos megoldas:

- oldalakat cimkezve kuldunk:

```text
PAGE page_1:
...

PAGE page_2:
...
```

- az aktualis implementacio szerint a modell `display_label`, `recommended_search_focus` es `source_label` mezot ad vissza,
- a backend a megadott oldalon megkeresi a `display_label` forrasbeli alakjat,
- backend szamitja az idezetet es az offsetet.

Ez egyszerubb es forrashubb, mint azonnal teljes dokumentum offsetet kovetelni.

## 10. Validacio

Backend validacio:

- irat a megadott ugyhoz tartozik,
- irat `active`,
- iratnak vannak aktualis oldalai,
- profil ismert,
- modell JSON ervenyes,
- `source_label` ismert oldalra mutat, vagy a backend a kivalasztott oldaltartomanyban meg tudja talalni a `display_label` alakot masik oldalon,
- a `display_label` megtalalhato a megjelolt vagy kivalasztott oldalon; az aktualis implementacio OCR-spacing tolerans egyezest is elfogad, peldaul `Pistaba` / `Pista ba` jellegu eltereseknel, de a mentett bizonyitek az eredeti forrasszoveg pontos substringje es karakterpozicioja,
- ha a `display_label` sehol nem talalhato a kivalasztott oldaltartomanyban, az elem nem megy veszendobe: ures `source_evidence_json` es validacios metadata mellett `Nem megerősített` munkalista-elemkent jelenik meg,
- nincs kulso forras,
- azonos `display_label` tobb elofordulasa nem torlodik automatikusan; a lista olvasasi valasza `occurrence_status` mezovel jelzi, hogy `unique` vagy `repeated`,
- nincs onkenyes `max_items` plafon: ha egy iratban sok forrassal igazolhato munkadarab van, nem dobjuk el oket csak elemszam miatt.

Nem kell tul agressziv deduplikacio elso korben. A teljes iratfeldolgozo munkalista emberi elokeszito felulet lesz, nem vegleges szakmai rekord.

## 11. UI integracio

Aktualis `Teljes iratfeldolgozás` feluleten:

- feldolgozas inditasa gomb aktiv,
- mutatja az utolso futast,
- listazza az aktiv vagy felretett munkadarabokat,
- a panel tetejen egy kozos toolbar van:
  - `Munkalista frissítése`,
  - nev alapu `Keresés a találatokban` mezo,
  - `Aktív`,
  - `Félretett`,
  - `Összes törlésre jelölése`,
  - `Jelöltek törlése (...)`,
- munkadarab kartyan:
  - cim,
  - ajanlott keresesi fokusz,
  - egy soros forrasbizonyitek,
  - `Egyedi` vagy `Többször előforduló` cimke,
  - `Nem megerősített` cimke es validacios uzenet, ha a nevalakot a backend nem talalta meg a kivalasztott forrasoldalakon,
  - gomb: `Fókusz átvitele kutatási keresésbe`,
  - gomb: `Félreteszem`,
  - felretett nezetben gomb: `Vissza az aktív listába`,
  - gomb: `Törlésre jelölés`.

Kesobb:

- `Entitássá alakítás`,
- `Kutatási találatok keresése ezzel a fókusszal`,
- tobb munkadarab csoportos kezelese.

## 12. Elso implementacios sorrend

Javasolt sorrend:

1. Backend schema/migration `document_processing_items`. **Kesz: `0039_doc_proc_items`.**
2. Run type bovites: `full_document_processing`. **Kesz.**
3. Profil registry backend oldalon. **Elso szelet kesz.**
4. Service: oldalak osszeallitasa `PAGE page_n` blokkokba. **Elso run-start szelet kesz.**
5. Prompt + JSON parser + backend source-evidence construction. **Aktualis szelet kesz: az LLM minimalis `display_label` / `recommended_search_focus` / `source_label` JSON-t ad, a backend a display_label alapjan epiti a forrasbizonyitekot vagy nem megerositett munkalista-elemet.**
6. API: run inditas, item lista, item statusz modositas, csoportos soft delete. **Elso teljes backend szelet kesz.**
7. Frontend: futtatas gomb bekotese, lista megjelenitese. **Elso szelet kesz: profilok, oldaltartomany, futtatas, aktiv/felretett munkalista, forrasbizonyitek, felretetel/visszaallitas, torlesre jeloles, osszes lathato torlesre jelolese, csoportos torles, nev alapu munkalista kereses, fokusz atadas.**
8. Frontend: ajanlott fokusz atvitele az `Ügy munkapad` elemzesi fokusz mezobe. **Elso szelet kesz.**

## 13. Nyitott dontesek

Ezek mar eldolt vagy implementalt pontok:

- az elso futtatas szinkron,
- a felhasznalo valasztott oldaltartomanyt ad meg,
- egy futtatas egy LLM-keres a kivalasztott oldaltartomanyra,
- nincs `max_items` alapu eredmenyeldobas,
- a munkalista torlese soft statuszvaltas.

Nyitott dontesek:

- kell-e kulon munkadarab export,
- mikor es hogyan legyen munkadarabbol valodi `entity`,
- a kovetkezo handoff lepest `research_finding` letrehozasa, strukturalt objektum letrehozasa vagy csak elore kitoltott `search_findings` futtatas jelentse-e,
- kell-e kesobb aszinkron/hatterjob modell nagyon hosszu futasokhoz.

## 14. Dontesi osszegzes

Elfogadando alapmodell:

```text
full_document_processing run
  -> document_processing_items
  -> emberi dontes
  -> keresesi fokusz / kutatasi talalat / strukturalt objektum
```

Ez tisztan elvalasztja:

- a query-alapu `research_finding` munkalistat,
- a teljes iratbol keszulo elokeszito munkadarabokat,
- a vegleges strukturalt objektumokat.

Igy a rendszer bovul, de nem mossa ossze a kulonbozo szakmai jelentesszinteket.
