# 37. Kutatasi talalat forrasanak meglevo talalathoz csatolasa

Status: Implementalva.

## Implementacios allapot

A szelet elkeszult:

- backend schema es endpoint: `POST /api/v1/cases/{case_id}/research-findings/{finding_id}/attach-source`,
- service: `attach_research_finding_source_to_existing_object(...)`,
- frontend API helper: `attachResearchFindingSource(...)`,
- `Kutatasi talalatok` kartyakon `Meglevo talalathoz csatolas` blokk,
- a blokk belso elrendezese a kezi `Uj talalat forrashivatkozasbol -> Meglevo talalathoz csatolas` mintat hasznalja,
- sikeres csatolas utan a finding `converted` allapotba kerul es eltunik az aktiv munkalistabol.

Friss celzott ellenorzesek:

```text
.venv/bin/python -m pytest tests/test_research_findings.py -q -> 17 passed
.venv/bin/python -m pytest tests/test_research_findings.py tests/test_manual_entries.py -q -> 22 passed
npm --prefix frontend run build -> passed
git diff --check -> passed
```

## Cel

A `Kutatasi talalatok` panel jelenleg ket fo munkautat ad:

- a talalatjeloltbol uj strukturalt objektum keszul,
- a talalatjelolt felrekerul vagy torlesre jelolheto.

Gyakorlati hasznalat kozben viszont gyakori, hogy egy keresesi futas ugyanahhoz a szakmai objektumhoz tobb ertekes, kulon forrashivatkozast ad. Pelda:

```text
Egy szemelyrol vagy entitasrol 5 relevans kutatasi talalatjelolt erkezik.
Az elso talalatbol letrejon az entitas.
A tovabbi 4 talalat forrasa ugyanahhoz az entitashoz tartozna.
```

A jelenlegi kerulo workflow:

1. minden talalatbol kulon objektum letrehozasa,
2. objektumok osszevonasa vagy forrasok levalasztasa,
3. forrasok visszacsatolasa,
4. maradek csonka elemek torlese.

Ez mukodik, de feleslegesen hosszu es zajos.

Az uj cel:

```text
Kutatasi talalat forrasa -> meglevo strukturalt objektumhoz csatolas -> kutatasi talalat feldolgozottkent eltunik az aktiv munkalistabol.
```

## Alapelv

A `research_finding` tovabbra sem vegleges szakmai objektum.

A szakmai objektumok tovabbra is:

- `claim`,
- `entity`,
- `event`,
- `missing_item_candidate`.

Az uj muvelet nem hoz letre uj szakmai objektumot, es nem irja at automatikusan a celobjektum szoveges tartalmat. Csak a kutatasi talalat mar letezo, validalt forrashivatkozasat kapcsolja a kivalasztott celobjektumhoz.

Kotelezo alapelv:

```text
No source -> no claim.
```

Ebben a workflow-ban a forras mar letezik: a `research_finding.source_reference_id`.

## Fontos fogalmi pontositas

### Kutatasi talalat forrasa

Itt a forras technikailag a konkret `source_reference` rekord:

- dokumentum,
- oldal,
- szovegresz,
- idezett szoveg,
- karakterpozicio, ha van,
- citation label,
- source kind.

Ez kapcsolhato a celobjektumhoz.

### A forrason kivuli resz

A kutatasi talalat LLM-altal eloallitott munkalista-metaadatai:

- `title`,
- `finding_text`,
- `relevance_reason`,
- `suggested_type`,
- `suggested_type_reason`.

Ezek nem masolodnak automatikusan a celobjektumba.

Indok:

- ne modositsunk csendben mar letezo szakmai objektumot,
- ne engedjuk, hogy egy talalatjelolt szovege automatikusan atirja az ember altal mar elfogadott vagy szerkesztett objektumot,
- a talalatjelolt metaadata megmaradhat audit/provenance celra.

Felhasznaloi szinten a talalat eltunik az aktiv listabol.
Adatmodell szinten a talalat rekordja megmarad feldolgozott allapotban.

## Jelenlegi alapok

Mar letezik:

- `research_findings.conversion_status`,
- `research_findings.target_object_type`,
- `research_findings.target_object_id`,
- `convert_research_finding_to_manual_object(...)`,
- `create_manual_object_from_source_reference(...)`,
- `attach_manual_source_to_existing_object(...)`,
- belso `_attach_source_reference_to_existing_object(...)` helper,
- review/audit event forrascsatolasra.

A kutatasi talalat lista mar most is kizarja a `converted` elemeket:

```text
conversion_status != "converted"
```

Ezert az uj muvelet utan az elem termeszetesen eltunik az aktiv munkalistabol.

## Tervezett backend contract

### Uj endpoint

Javasolt kulon endpoint, nem a jelenlegi `convert` tulterhelese:

```text
POST /api/v1/cases/{case_id}/research-findings/{finding_id}/attach-source
```

Payload:

```json
{
  "target_object_type": "entity",
  "target_object_id": "uuid"
}
```

Response:

```json
{
  "analysis_run_id": "uuid",
  "source_reference": { "...": "..." },
  "target_object_type": "entity",
  "target_object_id": "uuid",
  "skipped_duplicate_source": false,
  "target_reactivated": false,
  "finding": { "...": "ResearchFindingRead" }
}
```

A response szandekosan hasonlit a `ManualSourceAttachmentResponse` es `ResearchFindingConvertResponse` alakjara.

### Uj schema

Javasolt:

```text
ResearchFindingAttachSourceRequest
ResearchFindingAttachSourceResponse
```

A request csak celobjektumot ker:

- `target_object_type`,
- `target_object_id`.

Nem ker uj cimet/leirast, mert nem uj objektum keszul.

## Backend service terv

Javasolt uj service fuggveny:

```text
attach_research_finding_source_to_existing_object(
    db,
    case_id,
    finding_id,
    payload,
)
```

Lepesek:

1. `research_finding` betoltese `case_id` + `finding_id` alapjan.
2. Ha `conversion_status == "converted"`, hibaval alljon meg.
3. `source_reference` betoltese a `finding.source_reference_id` alapjan.
4. Ellenorzes: a forras ugyanahhoz az ugyhoz tartozik.
5. Ellenorzes: a forras dokumentuma aktiv, ugyanugy mint a konverzios uton.
6. Ellenorzes: elso implementacios szeletben csak `source_validation_status == "source_valid"` talalat csatolhato.
7. Manual/provenance run inditasa `manual_entry` tipussal.
8. A forrashivatkozas celobjektumhoz kapcsolasa a mar letezo objektumtipus-specifikus logikaval.
9. `research_finding` frissitese:
   - `conversion_status = "converted"`,
   - `target_object_type = payload.target_object_type`,
   - `target_object_id = payload.target_object_id`,
   - `updated_at = now`.
10. Analysis run output:
   - `source_reference`,
   - target object,
   - `research_finding`.
11. Audit event:
   - `research_finding_source_attached` vagy hasonlo nev,
   - input: finding id, source reference id, target object,
   - output: converted allapot, duplikacio jelzes, reaktivacio jelzes.
12. Commit es frissitett finding visszaadasa.

## Duplikacio kezelese

Fontos dontes:

Nem akarunk okos/fuzzy duplikacio-automatikat.

Csak ezt kell vedeni:

```text
azonos target object + azonos source_reference_id
```

Ha ugyanez a konkret `source_reference_id` mar rajta van ugyanazon a celobjektumon:

- ne jojjon letre uj kapcsolat,
- a muvelet jelezze `skipped_duplicate_source = true`,
- a `research_finding` ennek ellenere feldolgozottkent `converted` allapotba kerulhet, mert a user dontese teljesult: ez a talalat ehhez az objektumhoz tartozik.

Amit tudatosan nem csinalunk:

- nem hasonlitunk szovegeket fuzzy modon,
- nem tiltunk csak azert, mert ugyanaz a dokumentum / oldal / chunk,
- nem tekintunk ket kicsit eltero idezetet automatikusan azonosnak,
- nem dontjuk el backendbol, hogy ket hasonlo forras szakmailag redundans-e.

Indok:

Egy forrashivatkozason belul vagy ugyanazon chunkon belul tobb, szakmailag kulon ertekes idezet is lehet. A minimalis duplikacio-vedelem csak az egzakt kapcsolati duplikatumot elozi meg.

## Celobjektum tipusok

Tamogatott tipusok:

```text
claim
entity
event
missing_item_candidate
```

Nem tamogatott elso korben:

- contradiction candidate,
- document,
- research finding mint cel,
- full-document answer,
- knowledge-base document.

Indok:

Az uj workflow a forrassal alatamasztott strukturalt objektumokhoz valo forrascsatolasrol szol.

## Frontend UX terv

Erintett panel:

```text
Ugy munkapad -> Kutatasi talalatok
```

Minden aktiv, nem `converted` kutatasi talalat kartyajan legyen egy uj lenyithato resz:

```text
Meglevo talalathoz csatolas
```

Javasolt tartalom:

- cel tipus valaszto,
- keresheto celobjektum valaszto,
- `Forrashivatkozas csatolasa` gomb.

A celobjektum valaszto hasznalja ugyanazt a szemleletet, mint a kezi forrascsatolas:

- `claim` -> allitasok,
- `entity` -> entitasok,
- `event` -> esemenyek,
- `missing_item_candidate` -> hianyzo iratjeloltek.

### Alapertelmezett cel tipus

Javasolt:

- ha `suggested_type` megfeleltetheto manual objektumtipusnak, az legyen az alapertelmezett,
- `document_reference` es `other` eseten biztonsagos fallback: `claim` vagy explicit valaszto, a felhasznalo dontese szerint.

### Sikeres csatolas utan

Frontend frissitendo:

- kutatasi talalat lista,
- attekintesi jelentés,
- claims/entities/events/missing item candidate listak,
- analysis run history,
- esetleg selected report item a celobjektumra allithato.

Felhasznaloi visszajelzes:

```text
Forrashivatkozas meglevo talalathoz csatolva.
```

Ha egzakt duplikatum volt:

```text
A forrashivatkozas mar szerepelt a celon, ezert nem duplikaltuk.
```

## UI allapotok

Letiltott / nem elerheto:

- `source_validation_status != source_valid`,
- `conversion_status == converted`,
- nincs celobjektum kivalasztva,
- busy allapot.

Uzenet invalid source eseten:

```text
Csak ervenyes forrashivatkozasu kutatasi talalat csatolhato meglevo talalathoz.
```

## Audit es provenance

Az uj muveletnek ket reteget kell rogzitenie:

1. A celobjektum forrascsatolasi tortenetet.
2. A kutatasi talalat feldolgozottsagat.

Javasolt audit event:

```text
research_finding_source_attached
```

Input summary:

- `research_finding_id`,
- `source_reference_id`,
- `target_object_type`,
- `target_object_id`.

Output summary:

- `conversion_status`,
- `skipped_duplicate_source`,
- `target_reactivated`.

A mar letezo `manual_source_attached` event megtarthato, ha a belso helper hasznalja. Az uj kutatasi talalat specifikus event azert hasznos, mert megmutatja, hogy a forras nem sima kezi kijelolesbol, hanem LLM-altal javasolt kutatasi munkalista-elembol erkezett.

## Tesztterv

Backend unit/service tesztek:

- sikeres csatolas `source_valid` kutatasi talalatbol meglevo claimhez,
- sikeres csatolas entitashoz,
- `conversion_status` converted lesz,
- `target_object_type` / `target_object_id` kitoltodik,
- a finding eltunik a `list_research_findings` aktiv listabol,
- mar converted finding ujracsatolasa hibazik,
- masik ugyhoz tartozo target hibazik,
- invalid source finding csatolasa hibazik,
- azonos `source_reference_id` + target eseten nincs duplikalt source link,
- egzakt duplikatum eseten a finding megis converted allapotba kerul,
- audit/provenance summary tartalmazza a finding/source/target adatokat.

Frontend build/regresszio:

- `npm --prefix frontend run build`,
- uj API helper tipuskontroll,
- kartyankenti UI allapotok,
- sikeres csatolas utani refresh.

## Implementacios sorrend

1. Backend schema:
   - request/response tipusok.
2. Backend service:
   - `attach_research_finding_source_to_existing_object`.
3. Backend API:
   - `POST /research-findings/{finding_id}/attach-source`.
4. Backend tesztek.
5. Frontend API helper.
6. Frontend state:
   - kartyankenti cel tipus,
   - kartyankenti cel objektum id.
7. Frontend UI:
   - `Meglevo talalathoz csatolas` blokk.
8. Frontend refresh es notice.
9. Build/test.
10. Dokumentacio/CHANGELOG allapotfrissites.

## Nem cel ebben a szeletben

- Talalatjelolt szoveges tartalmanak automatikus beolvasztasa a celobjektumba.
- Fuzzy forrasduplikacio felismeres.
- Celobjektum tartalmanak automatikus modositasa.
- Contradiction candidate celkent hasznalata.
- Bulk csatolas tobb kutatasi talalatbol egyszerre.
- Kutatasi talalat fizikai torlese sikeres csatolas utan.

## Nyitva hagyott kesobbi lehetosegek

- Bulk attach: tobb kutatasi talalat kijelolese es egy celobjektumhoz csatolasa.
- Celobjektum szoveges frissitesi javaslat, kulon emberi jovahagyassal.
- Duplikatum-gyanus, de nem egzakt forrasok jelzese csak figyelmezteteskent.
- Konverzios tortenet megjelenitese a kutatasi talalat reszleteiben vagy audit panelen.

## Elfogadott dontesek

- A kutatasi talalat nem torlodik fizikailag sikeres csatolas utan.
- Sikeres csatolas utan `conversion_status = converted`.
- A `target_object_type` / `target_object_id` a celobjektumra mutat.
- A talalat LLM-metaadata nem irja at a celobjektumot.
- Csak az egzakt `source_reference_id` + celobjektum duplikaciot vedjuk.
- A felhasznaloi modell szerint a talalat eltunik az aktiv listabol, de audit/provenance celra megmarad.
