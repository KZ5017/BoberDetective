# Lokális Nyomozati Iratintelligencia Rendszer
## Prompt és JSON schema collection v1

## 1. Cél

Ez a dokumentum az MVP-1 elemzési modulok prompt- és JSON-kimeneti szerződéseit írja le.

A cél nem végleges promptszövegek irodalmi kidolgozása, hanem implementálható, validálható keretek rögzítése:

- milyen bemenetet kap az LLM,
- milyen JSON objektumot adhat vissza,
- milyen mezők kötelezők,
- hogyan kell forrást hivatkozni,
- milyen outputot kell elutasítani,
- hogyan kapcsolódik minden elem `analysis_runs`, `source_references`, `source_validation_status` és human review mezőkhöz.

Alapelv:

> No source -> no claim.

## 2. Általános prompt szabályok

Minden MVP LLM promptban szerepeljen:

1. A modell nem igazságforrás.
2. Csak a megadott context chunkokból dolgozhat.
3. Nem használhat külső tudást.
4. Nem tehet forrás nélküli állítást.
5. Nem dönthet bűnösségről, jogi minősítésről, kockázatról vagy személyi felelősségről.
6. Ha nincs elegendő forrás, üres listát vagy `insufficient_source` jelzést kell visszaadnia.
7. Minden output idézetének szó szerint vagy ellenőrizhetően szerepelnie kell valamelyik input chunkban.
8. Csak a kért JSON formátumot adhatja vissza, magyarázó szöveg nélkül.

> **Aktuális implementációs megjegyzés, 2026-05-26:** az aktív `search_findings` workflow-nál a tényleges LLM-instrukciós nyelv angol, mert a helyi Qwen modell ezzel stabilabban követi a precíz feladatkorlátokat. Ez nem változtatja meg a felhasználói vagy forrásnyelvet: a SOURCE chunkok magyar szövegek, a felhasználó felé megjelenő `title`, `finding_text`, `suggested_type_reason`, `relevance_reason` és `unsupported_reason` mezők magyarul készülnek, a `quote_text` pedig karakterpontosan a magyar forrásból másolandó, fordítás és javítás nélkül. A jelenlegi prompt tartalmaz egy általánosított direkt fókuszszabályt is: ha a QUERY konkrét fókuszelemet nevez meg vagy ír le, és a SOURCE ugyanazt az elemet tényszerű állítással, szereppel, attribútummal, cselekménnyel, hellyel, idővel, összeggel, kapcsolattal, állapottal, hivatkozással vagy megfigyeléssel együtt közvetlenül tartalmazza, azt közvetlen információnak kell tekinteni. A példálózó fókuszelemek: személy, szervezet, hely, telefonszám, email cím, rendszám, pénzösszeg, ügyszám, irathivatkozás és melléklet.

## 3. Közös input contract

> **Aktualis megjegyzes, 2026-05-17:** a kozos elv maradt, de a tenyleges analysis run inputok batchelt forraschunk metadata-t is tartalmaznak (`batch_index`, `batch_count`, `chunk_labels`, `retrieval_match_type`, `retrieval_score`). A raw-chunk modulok kotelezo fokuszszoveg alapjan valasztanak forrast keyword/semantic/hybrid retrievallel. Az ellentmondas modul ettol elteroen source-valid claim-parokon dolgozik. Reszletek: `Design_documents/10_analysis_batch_processing_plan.md`.

Minden analysis modul közös bemeneti alakja:

```json
{
  "case_id": "uuid",
  "analysis_run_id": "uuid",
  "task": "extract_claims",
  "language": "hu",
  "instructions": {
    "no_source_no_claim": true,
    "use_only_context": true,
    "output_language": "hu"
  },
  "chunks": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "document_name": "string",
      "page_start": 1,
      "page_end": 1,
      "chunk_index": 0,
      "text": "string"
    }
  ]
}
```

## 4. Közös source object

Minden output item legalább egy source objektumot tartalmazzon.

```json
{
  "document_id": "uuid",
  "document_name": "string",
  "page_number": 1,
  "chunk_id": "uuid",
  "quote": "string",
  "char_start": null,
  "char_end": null,
  "support_type": "direct"
}
```

Megkötések:

- `document_id` kötelező.
- `chunk_id` kötelező, ha chunkból dolgozott a modul.
- `quote` nem lehet üres.
- `quote` legyen rövid, de elég konkrét az ellenőrzéshez.
- `support_type` értékei: `direct`, `indirect`, `contextual`.

## 5. Közös confidence és review mezők

LLM outputban confidence szöveges érték legyen:

```text
low
medium
high
```

Adatbázisba íráskor ez leképezhető numerikus tartományra, ha szükséges:

- `low`: kb. 0.30
- `medium`: kb. 0.60
- `high`: kb. 0.85

Minden AI-output kezdeti review státusza:

```text
new
```

Minden AI-output kezdeti source validation státusza:

```text
pending_source_validation
```

## 6. Közös validációs szabályok

Az LLM output csak akkor menthető strukturált objektumként, ha:

1. JSON parse-olható.
2. Megfelel az adott modul sémájának.
3. Minden itemhez tartozik legalább egy source.
4. Minden source létező input chunkra mutat.
5. A `quote` megtalálható az input chunk szövegében, vagy validálható page text alapján.
6. A típusmezők ellenőrzött értékkészletből jönnek.
7. Nem tartalmaz tiltott döntést vagy vádat.

Ha bármelyik szabály sérül:

- az outputot ne írjuk végleges objektumtáblába,
- az `analysis_runs.validation_status` legyen `failed` vagy `warning`,
- audit esemény készüljön.

## 7. Modul: `extract_entities`

## 7.1 Cél

Entitásjelöltek és konkrét mentionök kinyerése dokumentumrészletekből.

## 7.2 Prompt feladat

A modell azonosítson személyeket, szervezeteket, helyszíneket és strukturált azonosítókat, de ne vonjon le következtetést személyek szerepéről, felelősségéről vagy bűnösségéről.

## 7.3 Output schema

```json
{
  "entities": [
    {
      "entity_type": "person",
      "canonical_name": "string",
      "normalized_value": null,
      "description": null,
      "confidence": "medium",
      "mentions": [
        {
          "surface_text": "string",
          "source": {
            "document_id": "uuid",
            "document_name": "string",
            "page_number": 1,
            "chunk_id": "uuid",
            "quote": "string",
            "char_start": null,
            "char_end": null,
            "support_type": "direct"
          }
        }
      ]
    }
  ]
}
```

## 7.4 Értékkészletek

`entity_type`:

- `person`
- `organization`
- `location`
- `phone`
- `email`
- `license_plate`
- `case_reference`
- `money_amount`
- `document_reference`
- `other`

## 7.5 Validáció

- Legalább egy mention kell minden entityhez.
- A mention source quote kötelező.
- A modell nem adhat `suspect`, `guilty`, `risk` vagy hasonló minősítő szerepet.

## 8. Modul: `extract_events`

## 8.1 Cél

Forráshivatkozott eseményjelöltek kinyerése idővonalhoz.

## 8.2 Prompt feladat

A modell azonosítson eseményszerű állításokat, dátumokat, időpontokat és helyszíneket. Csak jelölt eseményt adjon vissza, ne végleges ténymegállapítást.

## 8.3 Output schema

```json
{
  "events": [
    {
      "event_type": "statement",
      "event_title": "string",
      "event_description": "string",
      "event_time_raw": "string",
      "event_time_start": null,
      "event_time_end": null,
      "time_precision": "unknown",
      "location_text": null,
      "related_entities": [],
      "confidence": "medium",
      "sources": [
        {
          "document_id": "uuid",
          "document_name": "string",
          "page_number": 1,
          "chunk_id": "uuid",
          "quote": "string",
          "char_start": null,
          "char_end": null,
          "support_type": "direct"
        }
      ]
    }
  ]
}
```

## 8.4 Értékkészletek

`event_type`:

- `call`
- `meeting`
- `statement`
- `transfer`
- `search`
- `seizure`
- `document_created`
- `document_received`
- `other`

`time_precision`:

- `exact`
- `minute`
- `hour`
- `day`
- `month`
- `unknown`

## 8.5 Validáció

- Minden eseményhez legalább egy source kell.
- `event_time_start` és `event_time_end` csak ISO-8601 kompatibilis string vagy null lehet.
- Ha az időpont csak szövegként szerepel, `event_time_raw` legyen kitöltve.
- A modell ne állítsa, hogy az esemény biztosan megtörtént, ha a forrás csak állítja vagy hivatkozza.

## 9. Modul: `extract_claims`

## 9.1 Cél

Dokumentumokban szereplő releváns állítások strukturált kinyerése.

## 9.2 Prompt feladat

A modell különítse el, hogy ki vagy mely dokumentum mit állít. Ne döntse el az állítás igazságát.

## 9.3 Output schema

```json
{
  "claims": [
    {
      "claim_type": "witness_statement",
      "claim_text": "string",
      "speaker_text": null,
      "subject_text": null,
      "related_time_raw": null,
      "related_event_hint": null,
      "confidence": "medium",
      "sources": [
        {
          "document_id": "uuid",
          "document_name": "string",
          "page_number": 1,
          "chunk_id": "uuid",
          "quote": "string",
          "char_start": null,
          "char_end": null,
          "support_type": "direct"
        }
      ]
    }
  ]
}
```

## 9.4 Értékkészletek

`claim_type`:

- `witness_statement`
- `document_fact`
- `expert_opinion`
- `administrative_fact`
- `inference_candidate`
- `unknown`

## 9.5 Validáció

- Minden claimhez legalább egy source kell.
- `claim_text` nem lehet erősebb állítás, mint amit a quote alátámaszt.
- `inference_candidate` használata csak óvatosan megengedett, és kötelezően `needs_review` jellegű UI-kezelést igényel.

## 10. Modul: `detect_contradiction_candidates`

## 10.1 Cél

Potenciális ellentmondásjelöltek azonosítása már kinyert claim/event objektumok vagy visszakeresett chunkok alapján.

## 10.2 Prompt feladat

A modell csak jelölt ellentmondást adhat vissza. Nem döntheti el, hogy az ellentmondás valódi, lényeges vagy jogilag releváns.

## 10.3 Input kiegészítés

Ez a modul kaphat előzetes claim/event objektumokat is:

```json
{
  "claims": [],
  "events": [],
  "chunks": []
}
```

## 10.4 Output schema

```json
{
  "contradiction_candidates": [
    {
      "contradiction_type": "time_conflict",
      "title": "string",
      "description": "string",
      "claim_refs": [],
      "event_refs": [],
      "severity_hint": "medium",
      "confidence": "low",
      "sources": [
        {
          "side_label": "a",
          "document_id": "uuid",
          "document_name": "string",
          "page_number": 1,
          "chunk_id": "uuid",
          "quote": "string",
          "char_start": null,
          "char_end": null,
          "support_type": "direct"
        }
      ]
    }
  ]
}
```

## 10.5 Értékkészletek

`contradiction_type`:

- `time_conflict`
- `location_conflict`
- `identity_conflict`
- `document_mismatch`
- `amount_conflict`
- `other`

`severity_hint`:

- `low`
- `medium`
- `high`

## 10.6 Validáció

- Legalább két source szükséges, vagy két már forrásozott claim/event referencia.
- `severity_hint` nem jelent jogi vagy személyi kockázati pontozást.
- A leírásban kötelező legyen óvatos nyelvezet: potenciális, jelölt, ellenőrzést igényel.

## 11. Modul: `detect_missing_items`

## 11.1 Cél

Olyan hivatkozott dokumentumok, mellékletek, bizonyítékok vagy vizsgálati lépések jelzése, amelyekre az iratanyag utal, de a betöltött dokumentumkészletben nem láthatók.

## 11.2 Prompt feladat

A modell csak hiányjelöltet adhat vissza. Nem állíthatja véglegesen, hogy az elem valóban hiányzik.

## 11.3 Output schema

```json
{
  "missing_item_candidates": [
    {
      "missing_item_type": "attachment",
      "referenced_item_text": "string",
      "description": "string",
      "expected_document_type": null,
      "confidence": "medium",
      "sources": [
        {
          "document_id": "uuid",
          "document_name": "string",
          "page_number": 1,
          "chunk_id": "uuid",
          "quote": "string",
          "char_start": null,
          "char_end": null,
          "support_type": "direct"
        }
      ]
    }
  ]
}
```

## 11.4 Értékkészletek

`missing_item_type`:

- `attachment`
- `video`
- `expert_report`
- `protocol`
- `image`
- `document_reference`
- `other`

## 11.5 Validáció

- Legalább egy source kötelező.
- A description ne állítsa, hogy a dokumentum biztosan nem létezik, csak azt, hogy az importált anyagban nem azonosított.

## 12. Modul: `summarize_case`

## 12.1 Cél

Forráshivatkozott, review-zható `summary_items` létrehozása, nem egyetlen szabad szövegű összefoglaló.

## 12.2 Prompt feladat

A modell rövid összefoglaló-elemeket készítsen kizárólag a megadott context alapján. Minden elem külön forrásozott legyen.

## 12.3 Output schema

```json
{
  "summary_items": [
    {
      "summary_type": "case_overview",
      "title": "string",
      "body_text": "string",
      "confidence": "medium",
      "sources": [
        {
          "document_id": "uuid",
          "document_name": "string",
          "page_number": 1,
          "chunk_id": "uuid",
          "quote": "string",
          "char_start": null,
          "char_end": null,
          "support_type": "direct"
        }
      ]
    }
  ]
}
```

## 12.4 Értékkészletek

`summary_type`:

- `case_overview`
- `document_summary`
- `timeline_summary`
- `entity_summary`
- `caution_note`
- `other`

## 12.5 Validáció

- Minden summary itemhez legalább egy source kell.
- `body_text` ne tartalmazzon forrásban nem szereplő következtetést.
- `caution_note` csak ellenőrizendő szakmai figyelemfelhívás lehet, nem risk scoring.

## 13. Modul: `answer_with_citations`

## 13.1 Cél

Felhasználói kérdésre forráshivatkozott válasz készítése kizárólag retrieval context alapján.

## 13.2 Prompt feladat

A modell válaszoljon röviden és forrásokkal. Ha a context nem elég, ezt mondja ki strukturáltan.

## 13.3 Output schema

```json
{
  "answer": {
    "answer_text": "string",
    "answer_status": "answered",
    "confidence": "medium",
    "sources": [
      {
        "document_id": "uuid",
        "document_name": "string",
        "page_number": 1,
        "chunk_id": "uuid",
        "quote": "string",
        "char_start": null,
        "char_end": null,
        "support_type": "direct"
      }
    ]
  }
}
```

## 13.4 Értékkészletek

`answer_status`:

- `answered`
- `partial`
- `insufficient_source`

## 13.5 Validáció

- `answered` és `partial` esetén legalább egy source kötelező.
- `insufficient_source` esetén az answer_text mondja ki, hogy a megadott forrásanyag alapján nem válaszolható meg.
- A modell nem pótolhatja a hiányzó választ saját tudásból.

## 14. Prompt template verziózás

Minden prompt template kapjon nevet és verziót:

- `extract_entities_v1`
- `extract_events_v1`
- `extract_claims_v1`
- `detect_contradiction_candidates_v1`
- `detect_missing_items_v1`
- `summarize_case_v1`
- `answer_with_citations_v1`

Az `analysis_runs` tárolja:

- `prompt_template_name`,
- `prompt_template_version`,
- `output_schema_name`,
- `output_schema_version`,
- `raw_prompt_text`, ha releváns és biztonságosan tárolható.

## 15. Implementációs megjegyzés

Későbbi kódban minden modulhoz külön fájl vagy objektum tartozzon:

- prompt builder,
- input schema,
- output schema,
- parser,
- validator,
- mapper DB objektumokra.

Javasolt későbbi struktúra:

```text
app/services/analysis/modules/
  extract_entities.py
  extract_events.py
  extract_claims.py
  detect_contradictions.py
  detect_missing_items.py
  summarize_case.py
  answer_with_citations.py
```

Prompt template-ek és JSON sémák lehetnek külön konfigurációs fájlokban:

```text
app/analysis_templates/
  prompts/
  schemas/
```

## 16. Első implementációs sorrend

Javasolt sorrend:

1. Közös source object séma.
2. Közös output validátor.
3. `answer_with_citations`, mert ez teszteli leggyorsabban a retrieval + source idézet működését.
4. `extract_claims`.
5. `extract_entities`.
6. `extract_events`.

## 17. Implementációs státusz

Aktuális backend állapot:

- Az első smoke jellegű `answer_with_citations` útvonal működik a `POST /api/v1/cases/{case_id}/analysis/source-cited-smoke` endpointon.
- Elindult a generalizált analysis module API: `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}`.
- Az első támogatott modulok: `extract_claims`, `extract_events`.
- Az `extract_claims` modul keyword chunk retrievalt használ, analysis run inputként rögzíti a queryt és a chunkokat, LM Studio native hívást végez, majd minden visszaadott idézetet a megjelölt chunk szövege ellen validál.
- Csak validált idézettel rendelkező claim kerül `source_references`, `claims` és `claim_sources` táblába.
- Az `extract_events` modul ugyanezt a validációs mintát használja, majd valid forrás esetén `events` és `event_sources` rekordokat hoz létre.
- Nem támogatott modul kulcs esetén a backend elutasítja a futtatást.
7. `summarize_case`.
8. `detect_missing_items`.
9. `detect_contradiction_candidates`.

## 17. Rövid összegzés

Az MVP prompt- és JSON schema réteg célja, hogy a modell ne szabad szövegű szakértőként, hanem szigorúan korlátozott strukturáló komponensként működjön.

A siker feltételei:

1. minden output forrásozott,
2. minden source quote validálható,
3. minden output analysis runhoz kötött,
4. minden output emberi review-ra vár,
5. a modell soha nem hoz jogi, nyomozati vagy személyi döntést.
