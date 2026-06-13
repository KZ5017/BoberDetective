# 25. Kapcsolati terkep / graph view laza terv

## Cel

A `Kapcsolati terkep` egy dedikalt vizualis modul legyen, amely a mar
letezo, forrasvalidalt nyomozati objektumok kapcsolatait emberi szemmel
attekintheto modon jeleniti meg.

Nem uj igazsagreteg, nem uj LLM workflow es nem graph database bevezetese az
elso cel, hanem a jelenlegi relacios/auditalt adatmodell grafprojekcioja.

Alapelv:

```text
No source -> no claim.
```

A graf csak olyan kapcsolatokat jelenitsen meg, amelyek a backendben mar
letezo, auditalthato, forrashoz kotott adatokbol levezethetok.

## Mihez hasonlit

A nyomozo/vizsgalo "cetlis fal" jellegu munkajat tamogatja:

- entitasok,
- allitasok,
- esemenyek,
- forrasok,
- ellentmondasjeloltek,
- eredet/provenance kapcsolatok

vizualis osszefuggeseinek megmutatasaval.

A szemlelet rokon a BloodHound-fele grafgondolkodassal, de itt nem tamadasi
utvonal a fo kerdes, hanem:

```text
Mi kapcsolodik ehhez az objektumhoz, es milyen forras/provenance alapjan?
```

## Elso verzio: objektum-kozpontu graf

Az elso verzio objektum-kozpontu legyen.

A user egy vagy tobb strukturalt objektumot valaszt ki, es a rendszer ezek
kozvetlen kapcsolatait jeleniti meg.

Fokuszobjektum lehet:

- `claim`
- `entity`
- `event`
- `missing_item_candidate`
- `contradiction_candidate`

Elso korben ne legyen fokuszobjektum:

- `research_finding`
- `source_reference`
- `document`
- `chunk`
- `source_invalid` objektum

Ezek viszont megjelenhetnek kapcsolodo node-kent, ha egy fokuszobjektum
provenance vagy forrasagahoz tartoznak.

## Forrasvalidacios szabaly

A Kapcsolati terkep fokuszobjektumai csak teljes erteku, ervenyes
forrashivatkozassal rendelkezo objektumok legyenek.

Indok:

- a graf vizualisan eros meggyozoerot ad,
- ezert nem szabad nem validalt forrasu objektumokat ugy megjeleniteni,
  mintha ugyanolyan bizonyito erejuek lennenek,
- a `Nincs ervenyes forrashivatkozas` allapot elso korben ne legyen
  valaszthato graf-fokusz.

Review/ellenorzesi allapot szerint viszont ne legyen szures:

- ellenorzesre var,
- ellenorzott,
- javitott,
- elutasitott

objektumok is megjelenhetnek, ha forrasvalidak.

Az allapotot a node-on vizualisan egyertelmuen jelezni kell, de nem szabad
miatta elrejteni az objektumot.

## Megjelenitesi elkepzeles

Dedikalt modul neve:

```text
Kapcsolati terkep
```

Javasolt modulfelepites:

1. **Megjelenitendo objektumok panel**
   - kereses,
   - objektumtipus szuro,
   - objektumkartyak checkboxokkal,
   - kijeloltek megjelenitese.

2. **Kapcsolati terkep panel**
   - teljes szelessegu vizualis ter,
   - React Flow / XYFlow alapu interaktiv graf,
   - zoom/pan,
   - node/edge szurok,
   - kivalsztott node reszletei.

Az `Ugy munkapad` strukturalt objektum reszleteibol legyen egy gomb:

```text
Kapcsolati terkep megnyitasa
```

Ez atvisz a `Kapcsolati terkep` modulra, es az adott strukturalt objektumot
fokuszba teszi.

Fontos: ez a gomb letrehozott strukturalt talalatokra vonatkozzon, nem
kutatasi talalatjeloltekre.

## Technikai irany

Elso korben ne vezessunk be kulon grafadatbazist.

Javasolt architektura:

```text
PostgreSQL relacios modell
    -> backend graph projection API
        -> React Flow frontend megjelenites
```

A backend graph projection API pelda iranya:

```text
GET /api/v1/cases/{case_id}/graph/object/{object_type}/{object_id}
```

Tobb objektumhoz kesobb:

```text
POST /api/v1/cases/{case_id}/graph/objects
```

A valasz lenyege:

```json
{
  "focus_node_ids": ["claim:..."],
  "nodes": [],
  "edges": []
}
```

A node-ok es edge-ek csak backend altal ismert, meglevo kapcsolatokbol
epuljenek.

## Tipikus node-ok

- document
- page/chunk
- source_reference
- research_finding
- claim
- entity
- event
- missing_item_candidate
- contradiction_candidate
- analysis_run
- human_review vagy audit/provenance jellegu osszefoglalo node kesobb

## Tipikus edge-ek

Pelda belso tipusok:

- `contains`
- `supports`
- `mentioned_in`
- `converted_from`
- `created_by_run`
- `contradiction_between`
- `same_source_as`
- `detached_from`

Frontend magyar label pelda:

- `tartalmazza`
- `alatamasztja`
- `emlitve itt`
- `ebbol jott letre`
- `elemzesi futas hozta letre`
- `ellentmondasjelolt`
- `azonos forrasbol`
- `levalasztva innen`

## Tobbezres/tobb objektumos mukodes

Elso verzio:

```text
A kijelolt objektumok es kozvetlen kapcsolataik jelennek meg.
```

Nem elso kor:

- legrovidebb kapcsolat ket objektum kozott,
- csak kozos forrasok,
- csak kozos entitasok,
- teljes ugy graf,
- automatikus kapcsolatjavaslatok,
- grafadatbazis.

## Nem-celok az elso verziohoz

- AI ne generaljon grafelt.
- Ne legyen graph database.
- Ne legyen teljes ugyet egyben kirajzolo nagyhalos nezet.
- Ne legyen source-invalid objektum fokusz.
- Ne legyen automatikus szakmai kovetkeztetes.
- Ne valtsa ki az `Attekintesi jelentes`, `Talalat reszletei` vagy audit
  workflow-kat.

## Kapcsolat a provenance grafhoz

A `Kapcsolati terkep` elso verzioja objektum-kozpontu:

```text
Mi kapcsolodik ehhez az objektumhoz?
```

A kesobbi provenance/audit graf mas kerdesre valaszolna:

```text
Honnan szarmazik ez az objektum, es milyen dontesi/feldolgozasi uton jott letre?
```

A ket irany rokon, de nem azonos. Elso lepesben az objektum-kozpontu graf a
gyakorlati, vizualis nyomozati attekintest celszerubb tamogatja.

## Jelenlegi dontes

Ez a dokumentum csak iranyrogzites. Implementacio nem indul automatikusan.

Ha kesobb elindul:

1. backend graph projection API terv,
2. minimalis node/edge schema,
3. React Flow prototipus,
4. Ugy munkapad objektumreszletbol atvezeto gomb,
5. fokozatos bovites konkret hasznalati tapasztalat alapjan.
