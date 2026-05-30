# 11. Document Taxonomy and Source Filtering Plan

## Statusz

Torteneti terv.

A strukturalt irattaxonomia elso implementacios kore elkeszult, de a nagy ugyes
celallapot felulirta ezt az iranyt. Az aktiv kivezetesi terv:

```text
Design_documents/19_document_taxonomy_retirement_plan.md
```

A dokumentumot csak torteneti kontextuskent kezeld. Uj funkciot ne epits
importkori `document_group_code` / `document_type_code` dontesre.

## 1. Cel

Ez a terv azt rogziti, hogyan vezessunk be kotott iratcsoportokat es irattipusokat a korabbi szabad szoveges `document_type` mezo helyett, majd hogyan hasznaljuk ezt a strukturat az elemzesi forraskor szukitesere. A legacy `document_type` oszlop/API mezo az implementacioban mar kivezetesre kerult.

A cel nem jogi minosites automatizalasa, hanem munkaszervezesi es keresesi struktura:

- sok iratos ugyek kezelhetosege,
- kovetkezetes import,
  - auditalhato forrasszures,
- celzottabb keyword / semantic / hybrid retrieval,
- tovabbra is ervenyes `no source -> no claim` szabaly.

## 2. Hatter es jelenlegi korlat

Korabban az import soran az irattipus szabad szoveg volt:

```text
documents.document_type
```

Ezt a frontend import mezo is szabad szovegkent kezelte. Kis tesztugyeknel ez eleg lehetett, de tobb szaz iratnal nem alkalmas stabil workflow-ra:

- elgepelesek es szinonimak keletkeznek,
- nem lehet megbizhatoan szurni,
- az elemzesi forraskor nem szukitheto szakmailag ertelmes iratkategoriakra,
- kesobbi UI es API funkcionalitas rossz alapra epulne.

## 3. Fontos alapelvek

1. A taxonomia nem forrasigazsag.
   - Az irat besorolasa munkaszervezesi metadata.
   - A dokumentum tartalma, oldalszovege, source reference es review dontes marad a forrasigazsag.

2. A taxonomia legyen kotott, de bovitheto.
   - Stabil code-ok kellenek backend/API oldalon.
   - Magyar label-ek kellenek UI oldalon.
   - Uj csoport vagy tipus kesobb konnyen felveheto legyen.

3. Legyen biztonsagos atmeneti kategoria.
   - Meglevo es ideiglenesen feltoltott iratok ne kenyszeruljenek hibas besorolasba.
   - Ezert kotelezo elem:

```text
document_group_code = uncategorized
document_type_code  = uncategorized
```

UI label:

```text
Nem kategorizalt / Nem kategorizalt
```

4. A forraskor es a szurok maradjanak kulon fogalmak.
   - Forraskor lehet teljes ugy vagy strukturalt dokumentumhalmaz.
   - Iratcsoport, irattipus es iratlista szurok.
   - Oldaltartomany csak pontosan egy kivalasztott iratnal ertelmezheto.

## 4. Elso taxonomia v1

A kezdeti lista a nyomozati iratok gyakorlati funkcio szerinti csoportositasat koveti. Ez nem zart jogszabalyi lista, hanem a rendszer indulasi munkataxonomiaja.

### 4.1 Hatosagi dontesek es rendelkezesek

Code:

```text
authority_decisions
```

Tipusok:

```text
hatarozat
intezkedes
megkereses
```

### 4.2 Eljarasi cselekmenyek rogzitese

Code:

```text
procedural_records
```

Tipusok:

```text
jegyzokonyv
feljegyzes
kep_hangfelvetel_leirat
```

Megjegyzes:

Kesobb, ha hasznos, a `jegyzokonyv` alatti alcsoportok kulon tipusokka valhatnak, peldaul kihallgatasi jegyzokonyv, kutatasi jegyzokonyv, lefoglalasi jegyzokonyv, szemlejegyzokonyv.

### 4.3 Bizonyitekok es szakertoi anyagok

Code:

```text
evidence_expert_materials
```

Tipusok:

```text
szakertoi_velemeny
szaktanacsadoi_felvilagositas
kornyezettanulmany
bunugyi_technikai_jelentes
okirati_bizonyitek
```

### 4.4 Resztvevok altal benyujtott iratok

Code:

```text
participant_submissions
```

Tipusok:

```text
feljelentes
inditvany
eszrevetel
panasz
mento_korulmenyek_igazolasa
```

### 4.5 A nyomozas lezarasanak iratai

Code:

```text
closing_documents
```

Tipusok:

```text
iratismertetesi_jegyzokonyv
vademelesi_javaslat_nyomozast_lezaro_jelentes
```

### 4.6 Nem kategorizalt

Code:

```text
uncategorized
```

Tipus:

```text
uncategorized
```

Hasznalat:

- korabban feltoltott iratok migracioja,
- ideiglenes import,
- bizonytalan besorolas,
- olyan irat, amelyet kesobb kezzel kell besorolni.

## 5. Javasolt backend reprezentacio

Elso korben ne adatbazis-tablakent kezdjuk, hanem kozponti registrykent:

```text
app/core/document_taxonomy.py
```

Pelda struktura:

```python
DOCUMENT_TAXONOMY = [
    {
        "group_code": "authority_decisions",
        "group_label": "Hatosagi dontesek es rendelkezesek",
        "types": [
            {"type_code": "hatarozat", "type_label": "Hatarozat"},
            {"type_code": "intezkedes", "type_label": "Intezkedes"},
        ],
    },
]
```

Backend helper funkciok:

```text
list_document_taxonomy()
validate_document_taxonomy(group_code, type_code)
document_type_belongs_to_group(group_code, type_code)
default_uncategorized()
```

Kesobb, ha admin UI vagy ugyenkent testreszabott taxonomia kell, ez DB tablaba mozgathato.

## 6. Adatbazis terv

Javasolt uj mezok a `documents` tablan:

```text
document_group_code text not null default 'uncategorized'
document_type_code  text not null default 'uncategorized'
```

Korabbi atmeneti megfontolas volt, hogy a regi szabad szoveges `document_type` mezo legacy adatkent megmaradhat. Ezt a projekt vegul elvetette: minden dokumentum strukturalt taxonomia kodot kapott, majd a regi oszlop/API mezo kivezetesre kerult.

Indexek:

```text
documents(case_id, document_group_code)
documents(case_id, document_type_code)
documents(case_id, document_group_code, document_type_code)
```

Migracios szabaly:

```text
Minden meglevo dokumentum:
document_group_code = 'uncategorized'
document_type_code  = 'uncategorized'
```

Nem probaljuk automatikusan kitalalni a regi szabad szoveges `document_type` alapjan a strukturalt tipust. Az hibas besorolasokat okozhatna. A legacy adat nem marad aktiv szerzodesi elem; az iratok atminositese kesobb explicit, audit-trackelt felhasznaloi muvelet legyen.

## 7. API terv

### 7.1 Taxonomia lekerese

```text
GET /api/v1/document-taxonomy
```

Valasz:

```json
{
  "groups": [
    {
      "group_code": "procedural_records",
      "group_label": "Eljarasi cselekmenyek rogzitese",
      "types": [
        {
          "type_code": "jegyzokonyv",
          "type_label": "Jegyzokonyv"
        }
      ]
    }
  ]
}
```

### 7.2 Dokumentum import

Multipart mezok:

```text
document_group_code
document_type_code
language_code
notes
file
```

Szabaly:

- ha nincs megadva csoport/tipus: `uncategorized / uncategorized`,
- ha meg van adva: backend validalja,
- hibas parositas: `422`.

### 7.3 Dokumentum lista

`DocumentRead` bovul:

```text
document_group_code
document_group_label
document_type_code
document_type_label
```

Vagy minimalisabb elso korben:

```text
document_group_code
document_type_code
```

Label mapping tortenhet frontend oldalon a taxonomia endpoint alapjan.

## 8. Frontend import workflow

Jelenlegi szabad szoveges irattipus mezo helyett:

1. Iratcsoport dropdown.
2. Irattipus dropdown.
3. Irattipus csak a csoport valasztasa utan aktiv.
4. Alapertelmezett:

```text
Nem kategorizalt / Nem kategorizalt
```

Visible text magyar.

Ha kesobb kell, lehet "Besorolas kesobb" gyorsgomb, amely ugyanebbe az alapertelmezett parba teszi az iratot.

## 9. Elemzesi forrasszures terv

Ez a masodik nagy lepcso, az import oldali strukturalt metadata stabilizalasa utan.

### 9.1 Jelenlegi aktiv modell

Raw-chunk moduloknal jelenleg:

```text
source_mode = case | document
query       = kotelezo fokusz
retrieval_strategy = keyword | semantic | hybrid
max_chunks
batch_size
```

Selected-document scope eseten van oldaltartomany:

```text
page_start/page_end
```

Whole-case scope eseten nincs oldaltartomany.

### 9.2 Tervezett strukturalt source filter

Uj source selector mezok:

```text
document_group_code?
document_type_code?
document_ids?
page_start?
page_end?
```

Szabalyok:

- `document_group_code` opcionalis.
- `document_type_code` csak akkor ertelmezheto, ha csoport is van.
- `document_ids` tobbes kijeloles lehet.
- `page_start/page_end` csak akkor ertelmezheto, ha pontosan egy dokumentum van kivalasztva.
- Ha tobb dokumentum van kivalasztva, nincs oldaltartomany.
- Ha nincs dokumentum kivalasztva, de van csoport/tipus, akkor a scope az adott csoport/tipus osszes aktualis dokumentuma.

### 9.3 Retrieval kovetelmeny

Minden retrieval modnak ugyanazt a dokumentumhalmazt kell hasznalnia:

- keyword,
- semantic,
- hybrid.

Ez azt jelenti, hogy:

- PostgreSQL keyword keresest dokumentumhalmazra kell szurni,
- Qdrant semantic keresest payload filterrel dokumentumhalmazra kell szurni,
- hybrid keresest mindket oldalon ugyanazzal a dokumentumszurovel kell futtatni.

## 10. Implementacios lepcsok

> **Implementacios allapot, 2026-05-20:** az elso backend es frontend szelet elkeszult: `app/core/document_taxonomy.py`, `GET /api/v1/document-taxonomy`, `documents.document_group_code`, `documents.document_type_code`, `0018_document_taxonomy`, import-time validacio, default `uncategorized / uncategorized`, valamint frontend import/list/detail megjelenites fix iratcsoport es irattipus mezokkel. Az analysis source filter backend bovites is elkeszult: case-scope raw-chunk moduloknal `document_group_code`, `document_type_code` es `document_ids` szurok hasznalhatok, keyword/semantic/hybrid retrievalben egységesen. A frontend elemzesi panelen teljes ugy forraskorben megjelent az iratcsoport-, irattipus- es konkret iratlista-szuro. A regi szabad szoveges `documents.document_type` oszlop/API mezo `0019_drop_legacy_document_type` migracioval kivezetesre kerult, igy az uj iratbesorolas csak strukturalt taxonomia kodokon alapul. Az iratok utolagos atbesorolasa `PATCH /api/v1/cases/{case_id}/documents/{document_id}/taxonomy` endpointon es a frontend iratreszletek `Besorolas modositasa` blokkjaban elerheto; ez audit-trackelt, metadata-only muvelet, amely nem modosit oldalakat, szovegreszeket, forrashivatkozasokat, elemzesi futasokat vagy review objektumokat. A dokumentum eletciklus/parkolas elso teljes kore is elkeszult `0020_document_lifecycle_status` migracioval: `active`, `excluded`, `archived` allapotok, biztonsagos korai elvetes/torles, audit esemenyek, frontend allapotkezeles, es aktiv-dokumentum kapu az uj indexelesi, keresesi, elemzesi, forrashivatkozasi, manualis objektumletrehozasi, forrasmozgatasi/merge es ellentmondasjelolt-letrehozasi utvonalakon. Friss sorrend szerint a kovetkezo nagyobb tema elobb a tobb dedikalt munkafelulet UI/UX terve, majd a teljes iratfeldolgozo munkafelulet; a kulon, teljes erteku `Audit naplo` az `audit_events` esemenyekhez ezt koveto nagyobb munkatema.

### Lepcso 1: taxonomia registry es API

- `app/core/document_taxonomy.py`
- Pydantic response schema.
- `GET /api/v1/document-taxonomy`
- unit tesztek:
  - csoportok listazasa,
  - valid parositas,
  - hibas parositas.

### Lepcso 2: DB migracio es import validacio

- uj dokumentum mezok:
  - `document_group_code`,
  - `document_type_code`.
- meglevo iratok migracioja `uncategorized / uncategorized` ala.
- import API validacio.
- `DocumentRead` bovites.
- tesztek:
  - nincs megadva tipus -> uncategorized,
  - ervenyes csoport/tipus -> mentodik,
  - ervenytelen csoport/tipus -> 422.

### Lepcso 3: frontend import UI

- taxonomia betoltese,
- csoport dropdown,
- tipus dropdown,
- alapertelmezett `Nem kategorizalt / Nem kategorizalt`,
- dokumentumlista strukturalt label megjelenites.

### Lepcso 4: dokumentumlista es egyszeru szures

- dokumentumlista UI csoport/tipus szerinti szurese.
- Ez meg nem analysis source filter, csak kezelhetosegi javitas.

### Lepcso 5: analysis source filter backend

- source selector bovites:
  - csoport,
  - tipus,
  - tobb dokumentum id.
- keyword/semantic/hybrid azonos dokumentumszurovel.
- oldaltartomany csak pontosan egy dokumentumnal.
- audit metadata az analysis run input_parameters-ben.

### Lepcso 6: analysis source filter frontend

- Forraskor panel ujrarendezese:

```text
Forraskor:
  Teljes ugy
  Strukturalt iratszures

Strukturalt iratszures:
  Iratcsoport
  Irattipus
  Iratok checkbox listaja
  Oldaltartomany csak egy iratnal
```

Megjegyzes:

Nem biztos, hogy a `Teljes ugy` es a `Strukturalt iratszures` ilyen neven maradjon. A UX-et kulon erdemes kiprobalni.

Implementalt elso UI-szelet:

- teljes ugy forraskorben opcionalis `Iratcsoport szuro`,
- a csoporttol fuggo opcionalis `Irattipus szuro`,
- a szuroknek megfelelo konkret iratok checkboxos listaja,
- ha nincs konkret irat kijelolve, a backend a csoport/tipus osszes aktualis iratara szukit,
- kiválasztott irat forraskorben tovabbra is az oldaltartomany a pontos szukites eszkoze.

Implementalt indexelesi kiegeszites:

- a semantic/hybrid index-keszultseg ellenorzes ugyanazokat a strukturalt case-scope szuroket kapja, mint az elemzes,
- a hatter indexeles inditasa is tudja a `document_ids`, `document_group_code`, `document_type_code` mezoket,
- semantic/hybrid futtatas elotti backend ellenorzes a feloldott dokumentumhalmaz indexeltseget vizsgalja, nem vakon a teljes ugyet.

## 11. Biztonsagi es szakmai korlatok

- A taxonomia nem bizonyit tartalmat.
- A besorolas emberi vagy import metadata dontes.
- LLM nem valaszthat automatikusan irattipust forrasigazsagkent.
- Kesobb lehet AI-javaslat irattipusra, de csak javaslatkent, emberi elfogadassal es audit loggal.
- Minden analysis output tovabbra is source reference-hez es analysis runhoz kotott.
- Nem szabad szabad szoveges taxonomia mezoket kontroll nelkul visszahozni.

## 12. Nyitott kerdesek

1. Kell-e mar elso korben kezi atbesorolas UI meglevo dokumentumokra?
2. A `jegyzokonyv` legyen-e egy altalanos tipus, vagy bontsuk rogton kihallgatasi / kutatasi / lefoglalasi / szemle jegyzokonyvre?
3. Az `okirati_bizonyitek` tul tag-e, kell-e ala kesobb bankszamla, szerzodes, level, szamla stb. bontas?
4. A hianyzo iratjeloltek `expected_document_type` mezoje mikor kapcsolodjon a taxonomiahoz?
5. Szukseges-e ugyenkenti egyedi irattipus bovites, vagy eleg koddal bovitheto globalis taxonomia?

## 13. Aktualis allapot es kovetkezo kapcsolodo lepesek

Az eredeti elso implementacios cel teljesult:

```text
Lepcso 1 + Lepcso 2
```

Vagyis:

- taxonomia registry,
- taxonomia API,
- DB mezok,
- import validacio,
- meglevo iratok `uncategorized / uncategorized` migracioja.

Azota a frontend import UI, az analysis source filter, a legacy `document_type` kivezetese, az audit-trackelt irat atbesorolas, valamint a dokumentum eletciklus/parkolas elso teljes kore is elkeszult.

Kapcsolodo kesobbi nagyobb tema:

- dedikalt `Audit naplo` felulet az `audit_events` tablaban levo muveletekhez, beleertve a `document_reclassified`, dokumentum eletciklus, forrasmozgatasi, review, import/OCR/chunking, export es analysis-run audit esemenyeket.
- Friss sorrendi dontes: az audit naplo elott kovetkezzen egy UI/UX tervezesi kor tobb dedikalt munkafelulethez, majd egy teljes iratfeldolgozo munkafelulet a mar feltoltott iratokon vegzett, adat-atjarhato teljes dokumentumos feldolgozashoz.
