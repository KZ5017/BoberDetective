# 15. Full Document Processing Plan

## 0. Aktualisitas

Frissitve: 2026-05-28.

Ez a dokumentum a `Teljes iratfeldolgozás` munkafelület backend-szerzodeset es elso implementacios iranyat rogziti.

Kapcsolodo dokumentumok:

- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/12_source_bound_findings_model_plan.md`
- `Design_documents/13_legacy_analysis_module_retirement_plan.md`

Aktualis UI allapot:

```text
AppShell / munkafelület-valto kesz
Ügy munkapad = jelenlegi munkapad
Teljes iratfeldolgozás = frontend-only elso szelet
Audit napló = placeholder
```

A `Teljes iratfeldolgozás` feluleten mar van:

- aktiv irat kereses/valasztas,
- feldolgozasi profil valasztas,
- kivalasztott irat osszefoglalo,
- kimeneti struktura helye.

Most a backend szerzodest kell megtervezni.

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
- emlitesi formak gyujtese,
- rovid forrashu leiras,
- kapcsolodo szerep vagy viszony csak akkor, ha forras tamasztja ala,
- ajanlott keresesi fokuszok keszitese.

Peldak kimeneti mezokre:

```text
display_label
mentioned_forms
short_description
source_supported_details
relationships
recommended_search_focus
alternative_search_focuses
quote_refs
confidence_note
```

### 4.2 `entity_search_seeds`

UI:

```text
Entitások és keresési fókuszok
```

Feladat:

- szervezetek,
- helyek,
- ugyhivatkozasok,
- irathivatkozasok,
- mellekletek,
- egyeb konkret azonosithato objektumok kinyerese.

Nem cel minden fonev vagy altalanos fogalom kinyerese.

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
entity_search_seeds
```

### 5.2 `item_kind`

Nem vegleges strukturalt objektumtipus, hanem munkadarab-jelleg:

```text
person
organization
location
document_reference
case_reference
attachment
other
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
- opcionálisan oldal inputok, ha a teljes irat tul nagy es oldalcsoportokra kell bontani.

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
  "profile_key": "person_search_seeds"
}
```

Valasz:

```json
{
  "analysis_run_id": "...",
  "status": "succeeded",
  "items_created": 12
}
```

Elso korben szinkron futas is elfogadhato kisebb iratokhoz, de a teljes irat jellege miatt jobb a hatterjob-szeru modell:

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
- karakterpontos magyar idezet,
- nincs kulso tudas,
- nincs kovetkeztetett jogi/nyomozati minosites.

Elso `person_search_seeds` task lenyege:

```text
Extract persons mentioned in the Hungarian document text.
For each person, return a concise Hungarian, source-faithful description.
Include only details directly supported by quoted text.
Return recommended Hungarian search focus strings that can later be used in the research-finding workflow.
Do not turn persons into claims, suspects, perpetrators, witnesses, or procedural roles unless the source directly says so.
```

Elvart JSON:

```json
{
  "items": [
    {
      "item_kind": "person",
      "display_label": "...",
      "mentioned_forms": ["..."],
      "short_description": "...",
      "source_supported_details": ["..."],
      "relationships": [
        {
          "relation_label": "...",
          "target_label": "...",
          "quote_text": "..."
        }
      ],
      "recommended_search_focus": "...",
      "alternative_search_focuses": ["..."],
      "source_evidence": [
        {
          "quote_text": "...",
          "source_label": "page_7"
        }
      ],
      "confidence_note": "..."
    }
  ],
  "unsupported_items": ["..."]
}
```

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

- a modell `source_evidence.source_label` mezoben oldal labelt ad vissza,
- `quote_text` karakterpontosan szerepeljen az adott oldal szovegeben,
- backend validalja, hogy a quote megtalalhato az adott oldalon,
- backend szamitja az offsetet.

Ez egyszerubb es forrashubb, mint azonnal teljes dokumentum offsetet kovetelni.

## 10. Validacio

Backend validacio:

- irat a megadott ugyhoz tartozik,
- irat `active`,
- iratnak vannak aktualis oldalai,
- profil ismert,
- modell JSON ervenyes,
- `source_evidence` nem ures,
- minden `quote_text` megtalalhato a megjelolt oldalon,
- nincs kulso forras,
- output meret korlatozott.

Nem kell tul agressziv deduplikacio elso korben. A teljes iratfeldolgozo munkalista emberi elokeszito felulet lesz, nem vegleges szakmai rekord.

## 11. UI integracio

Elso backend integracio utan a `Teljes iratfeldolgozás` feluleten:

- feldolgozas inditasa gomb aktiv lesz,
- mutatja az utolso futast,
- listazza a munkadarabokat,
- munkadarab kartyan:
  - cim,
  - rovid leiras,
  - ajanlott keresesi fokusz,
  - forrasidezetek,
  - gomb: `Fókusz átvitele kutatási keresésbe`,
  - gomb: `Félreteszem`,
  - gomb: `Törlés`.

Kesobb:

- `Entitássá alakítás`,
- `Kutatási találatok keresése ezzel a fókusszal`,
- tobb munkadarab csoportos kezelese.

## 12. Elso implementacios sorrend

Javasolt sorrend:

1. Backend schema/migration `document_processing_items`.
2. Run type bovites: `full_document_processing`.
3. Profil registry backend oldalon.
4. Service: oldalak osszeallitasa `PAGE page_n` blokkokba.
5. Prompt + JSON parser + source quote validation.
6. API: run inditas, item lista, item statusz modositas.
7. Frontend: futtatas gomb bekotese, lista megjelenitese.
8. Frontend: ajanlott fokusz atvitele az `Ügy munkapad` elemzesi fokusz mezobe.

## 13. Nyitott dontesek

Ezeket implementacio elott vagy kozben kell tisztazni:

- szinkron vagy hatterjob legyen-e az elso futtatas,
- egy teljes irat belefer-e stabilan a chat modell aktualis context ablakaba,
- hosszu iratoknal oldalblokkokra bontunk-e,
- kell-e kulon munkadarab export,
- mikor es hogyan legyen munkadarabbol valodi `entity`.

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
