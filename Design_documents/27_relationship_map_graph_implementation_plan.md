# 27. Kapcsolati terkep implementacios terv

## Cel

Ez a dokumentum a `Design_documents/25_relationship_map_graph_view_plan.md`
vazlatos iranyabol indul ki, es konkret implementacios tervve bontja az elso
`Kapcsolati terkep` verziot.

Az elso verzio celja:

```text
Egyetlen source-valid strukturalt objektum kozvetlen kapcsolati terkepe.
```

Ez szandekosan kis scope:

- egy fokuszobjektum,
- read-only megjelenites,
- backend altal levezetett node/edge projection,
- React Flow / XYFlow frontend,
- nincs grafadatbazis,
- nincs LLM altal kitalalt kapcsolat.

## Alapelvek

```text
No source -> no claim.
```

A graf nem uj igazsagreteg.

A graf csak azt jeleniti meg, ami a jelenlegi relacios adatmodellbol,
forrashivatkozasokbol, analysis run provenance-bol, kutatasi talalat
konverziobol vagy ellentmondasjelolt kapcsolatokbol levezetheto.

Az elso verzio ne hozzon letre, ne modositson es ne toroljon szakmai objektumot.

## Scope dontesek

### Benne van az elso verzioban

- egyetlen fokuszobjektum megjelenitese,
- source-valid strukturalt objektumok fokuszkent,
- kozvetlen forras/provenance/kapcsolodo objektum node-ok,
- backend graph projection API,
- frontend `Kapcsolati terkep` modul,
- `Ugy munkapad` objektumreszletbol atvezeto gomb,
- 50 fokuszobjektumos vedokorlat, node/edge csonkolas nelkul,
- read-only graph.

### Nincs benne az elso verzioban

- tobb fokuszobjektum egyszerre,
- teljes ugy graf,
- automatikus kapcsolatjavaslat,
- LLM altal generalt edge,
- graph database,
- source-invalid fokuszobjektum,
- audit event / human review node-ok,
- timeline graf,
- szerkesztheto graf.

## Fokuszobjektum tipusok

Az elso verzioban fokuszobjektum lehet:

- `claim`
- `event`
- `entity`
- `missing_item_candidate`
- `contradiction_candidate`

Fokusz feltetel:

- az objektum a megadott ugyhoz tartozzon,
- az objektum legyen lekerdezheto a jelenlegi backend modellekbol,
- legyen source-valid.

Forrasvalidacios ertelmezes:

- `claim`, `event`, `missing_item_candidate`, `contradiction_candidate`:
  `source_validation_status = source_valid`;
- `entity`: legalabb egy valid mention/source-reference kapcsolat kell, ugyanazzal
  a szemantikaval, ahogy a review report mar szamolja az entity source statuszt.

Review statusz alapjan az elso verzio nem zar ki objektumot. A node-on viszont
jelezni kell:

- `needs_review`,
- `verified`,
- `rejected`,
- `corrected`.

## Kapcsolodo node tipusok

Az elso verzios backend projection ezekbol epitheti a grafot:

- `focus_object`
- `claim`
- `event`
- `entity`
- `missing_item_candidate`
- `contradiction_candidate`
- `research_finding`
- `source_reference`
- `document`
- `page`
- `chunk`
Az objektumkozpontu kapcsolati terkep nem jelenit meg `analysis_run` vagy
`research_finding` eredet node-okat. Ezek az informaciok tovabbra is a rendszer
provenance/audit retegenek reszei, de nem ennek a terkepnek a node-jai.

Nem fokusz node-kent megjelenhet:

- ugyanazon source_reference-re epulo mas strukturalt objektum,
- contradiction candidate parja, ha a fokusz egy claim vagy contradiction candidate.

## Edge tipusok

Elso verzios belso edge tipusok:

```text
HAS_SOURCE
DOCUMENT_HAS_PAGE
PAGE_HAS_CHUNK
DOCUMENT_HAS_CHUNK
SOURCE_FROM_CHUNK
SOURCE_FROM_PAGE
SOURCE_FROM_DOCUMENT
CONTRADICTS_CLAIM_A
CONTRADICTS_CLAIM_B
SHARES_SOURCE_WITH
```

### Edge jelentese

- `HAS_SOURCE`
  - strukturalt objektum -> source_reference
  - pelda: claim -> source_reference

- `DOCUMENT_HAS_PAGE`
  - document -> page
  - csak akkor, ha a source_reference konkret page node-ot is ismer

- `PAGE_HAS_CHUNK`
  - page -> chunk
  - csak akkor, ha a chunk az adott page-hez kotheto

- `DOCUMENT_HAS_CHUNK`
  - document -> chunk
  - fallback edge, ha page node nincs, de document es chunk van

- `SOURCE_FROM_CHUNK`
  - chunk -> source_reference
  - preferalt forrashely edge, ha chunk ismert

- `SOURCE_FROM_PAGE`
  - page -> source_reference
  - fallback edge, ha chunk nincs, de page ismert

- `SOURCE_FROM_DOCUMENT`
  - document -> source_reference
  - fallback edge, ha se chunk, se page nincs, de document ismert

- `CONTRADICTS_CLAIM_A`
  - claim A -> contradiction_candidate

- `CONTRADICTS_CLAIM_B`
  - claim B -> contradiction_candidate

- `SHARES_SOURCE_WITH`
  - fokuszobjektum -> mas strukturalt objektum
  - csak akkor, ha ugyanarra a source_reference-re epulnek
  - elso verzioban limit: legfeljebb 10 kapcsolodo objektum

### Source-location projection dontes

A source-location node-ok ne csillagszeru kapcsolatkent jelenjenek meg a
`source_reference` korul.

Korabbi, kevesbe olvashato backend projection:

```text
source_reference -> document
source_reference -> page
source_reference -> chunk
```

Uj celallapot:

```text
document -> page -> chunk -> source_reference -> structured_object
```

A backend tovabbra is tarolhatja es ismerheti a source_reference kozvetlen
`document_id`, `page_id`, `chunk_id` mezeit, de a graph projection celja nem a
nyers idegen kulcsok parhuzamos kirajzolasa, hanem a forrashely termeszetes
hierarchiajanak megjelenitese.

Indok:

- az irat tartalmazza az oldalt;
- az oldal tartalmazza vagy lokalizalja a szovegreszt;
- a forrashivatkozas a legkonkretabb ismert forrashelybol ered;
- a strukturalt objektum erre a forrashivatkozasra epul;
- emberi olvasasi iranyban ez tisztabb, mint a csillag alaku source-reference
  kozpontu helymeghatarozas.

Fallback szabalyok:

1. Ha document + page + chunk is ismert:

   ```text
   document -> page -> chunk -> source_reference -> object
   ```

2. Ha document + chunk ismert, de page nincs:

   ```text
   document -> chunk -> source_reference -> object
   ```

3. Ha document + page ismert, de chunk nincs:

   ```text
   document -> page -> source_reference -> object
   ```

4. Ha csak document ismert:

   ```text
   document -> source_reference -> object
   ```

Ez nem onkenyes uj kapcsolat: a dokumentum/page/chunk viszony a jelenlegi
source-reference es chunk/page metaadatokbol determinisztikusan levezetheto.
Ha egy kapcsolat nem tamaszthato ala ezekbol a mezokbol, a projection ne
talalja ki.

Implementacios allapot:

- kesz backend oldalon;
- a source-location projection mar nem source-reference kozpontu csillag;
- uj edge-tipusok:
  - `DOCUMENT_HAS_PAGE`
  - `PAGE_HAS_CHUNK`
  - `DOCUMENT_HAS_CHUNK`
  - `SOURCE_FROM_CHUNK`
  - `SOURCE_FROM_PAGE`
  - `SOURCE_FROM_DOCUMENT`
- a frontend kulon retegekkent kezeli az `Irat`, `Oldal`, `Szovegresz` es
  `Forrashivatkozas` node-okat;
- ha koztes source-location reteg rejtett, a frontend csak vizualis
  `VISUAL_SOURCE_BRIDGE` elet rajzol, nem backend truth edge-et;
- az `Elemzési eredet` node-ok ebbol az objektumkozpontu terkepbol ki vannak
  vezetve; analysis/audit provenance kulon feluleten vagy kesobbi
  eletut/provenance terkepen jelenhet meg.

## Adatforrasok a jelenlegi DB-bol

### Claim

Forrasok:

- `claims`
- `claim_sources`
- `source_references`
- `documents`
- `document_pages`
- `document_chunks`
- `analysis_runs`
- `research_findings`
- `contradiction_candidates`

Kapcsolatok:

- claim -> source_reference,
- document/page/chunk -> source_reference termeszetes source-location lanc,
- claim -> analysis_run, ha provenance mezobol levezetheto,
- research_finding -> claim, ha `target_object_type=claim`,
- claim -> contradiction_candidate, ha az allitas az ellentmondasjelolt A/B oldala.

### Event

Forrasok:

- `events`
- `event_sources`
- `source_references`
- `documents`
- `document_pages`
- `document_chunks`
- `analysis_runs`
- `research_findings`

Kapcsolatok:

- event -> source_reference,
- document/page/chunk -> source_reference termeszetes source-location lanc,
- research_finding -> event, ha `target_object_type=event`,
- event -> analysis_run, ha levezetheto.

### Entity

Forrasok:

- `entities`
- entity mention/source jellegu kapcsolatok,
- `source_references`, ha a mention/source link ezt tarolja,
- `documents`
- `document_pages`
- `document_chunks`
- `analysis_runs`
- `research_findings`

Kapcsolatok:

- entity -> source_reference vagy entity -> document/page/chunk mention,
- research_finding -> entity, ha `target_object_type=entity`,
- entity -> analysis_run, ha levezetheto.

Megjegyzes:

Az entity forrasvalidacio nem ugyanugy mezoszintu, mint claim/event/missing item
eseten. Az elso implementacio hasznalja ugyanazt a forrasvalidacios
segedszemantikat, amelyet a review report mar alkalmaz az entity source
statuszhoz.

### Missing item candidate

Forrasok:

- `missing_item_candidates`
- `missing_item_candidate_sources`
- `source_references`
- `documents`
- `document_pages`
- `document_chunks`
- `analysis_runs`
- `research_findings`

Kapcsolatok:

- missing_item_candidate -> source_reference,
- document/page/chunk -> source_reference termeszetes source-location lanc,
- research_finding -> missing_item_candidate,
- missing_item_candidate -> analysis_run, ha levezetheto.

### Contradiction candidate

Forrasok:

- `contradiction_candidates`
- claim-pair kapcsolatok,
- `claims`
- claim source-ok,
- `source_references`
- `analysis_runs`

Kapcsolatok:

- claim A -> contradiction_candidate,
- claim B -> contradiction_candidate,
- claim A/B -> sajat source_reference,
- contradiction_candidate -> analysis_run, ha levezetheto.

Megjelenitesi/projection dontes:

- ebben az objektumkozpontu kapcsolati terkepben a contradiction candidate nem
  kap sajat kozvetlen source-reference labat;
- a forrasut a bemeneti claim A/B objektumokon keresztul olvashato;
- ezzel elkeruljuk a duplazott forrasvonalakat, mert az ellentmondasjelolt
  szakmailag a ket bemeneti allitasbol epul fel;
- ha kesobb eletut/provenance terkep keszul, ott a contradiction candidate
  sajat forrasai vagy letrehozasi korulmenyei ujra megjelenithetok.

## Backend API terv

### Elso endpoint, kivezetve

```text
GET /api/v1/cases/{case_id}/graph/object/{object_type}/{object_id}
```

Ez volt az elso single-focus backend endpoint. A multi-focus atvezetes utan
kivezetesre kerult a publikus API-bol; a frontend mar nem hasznalja, es uj
funkcionalitast nem szabad erre epiteni.

A korabbi query parameterek:

- `include_shared_sources: bool = true`
- `max_nodes: int = 80`
- `max_edges: int = 120`

Elso implementacios maximumok:

- `max_nodes` backend cap: 120
- `max_edges` backend cap: 200
- `SHARES_SOURCE_WITH` kapcsolodo objektum cap: 10

### Kovetkezo nagyobb endpoint

```text
POST /api/v1/cases/{case_id}/graph/objects
```

Ez a kovetkezo nagyobb fejlesztesi szelet. Celja, hogy a jelenlegi
egyobjektumos graf helyett vagy mellett tobb source-valid fokuszobjektum
egyideju kapcsolati terkepe legyen lekerdezheto.

Tervezett request:

```json
{
  "focus_objects": [
    {"object_type": "claim", "object_id": "..."}
  ],
  "include_shared_sources": true,
  "max_nodes": 150,
  "max_edges": 250
}
```

Backend elvek:

- `focus_objects` elemszam: 1..50;
- minden fokuszobjektum legyen case-bound es source-valid;
- ugyanazok az objektumtipusok tamogatottak, mint az egyfokuszu endpointnal;
- a service hasznalja ujra a mar meglevo single-focus graph builder logikajat,
  vagy emelje ki kozos collectorba;
- node/edge deduplikacio stabil `id` alapjan tortenjen;
- a response maradjon kompatibilis a jelenlegi node/edge semaval, de bovulhet
  `focus_node_ids` / `focus_objects` mezokkel;
- a backend akkor is ervenyesitse az 50 fokuszobjektumos capet, ha a frontend
  kesobb mas UI-limittel dolgozik.

Frontend elvek:

- az objektumkartyak radio jeloles helyett checkboxos tobbes kijelolest kapnak;
- latszodjon a kijeloles szamlaloja, peldaul `3 kijelölve / 50` es kulon `Összes: n` chip;
- legyen `Kijelöltek térképre helyezése` akcio;
- a jelenlegi retegkapcsolok valtozatlanul mukodjenek a tobbfokuszu grafon is;
- a kesobbi `Összes látható kijelölése` csak akkor keruljon be, ha az 50-es limit
  es a vizualis attekinthetoseg live teszten stabilnak bizonyul.

### Single-focus endpoint allapota

A korabbi endpoint:

```text
GET /api/v1/cases/{case_id}/graph/object/{object_type}/{object_id}
```

mar nem aktiv publikus backend API. A kezi UUID inputot a frontend kivaltotta
source-valid objektumkartyas valasztoval, majd a frontend graph betoltes is at
lett vezetve a multi-focus POST endpointra.

Aktualis helyzet:

- publikus graph betoltes: `POST /api/v1/cases/{case_id}/graph/objects`;
- egyetlen objektumos handoff is egy elemu `focus_objects` listat kuld;
- a service szinten megmaradhat az egyfokuszu wrapper, de HTTP-n a regi
  UUID-os single-focus endpoint nem el.

Kivezetesi dontes teljesult:

- multi-focus POST endpoint elkeszult;
- frontend single-focus es multi-focus betoltes is a POST endpointot hasznalja;
- a regi GET endpoint es frontend helper ki lett vezetve.

## Backend response schema

Javasolt Pydantic sema:

```json
{
  "case_id": "...",
  "focus_node_id": "claim:<uuid>",
  "focus_object_type": "claim",
  "focus_object_id": "...",
  "nodes": [],
  "edges": [],
  "warnings": [],
  "limits": {
    "max_nodes": 80,
    "max_edges": 120,
    "node_count": 12,
    "edge_count": 15,
    "truncated": false
  }
}
```

Node shape:

```json
{
  "id": "claim:<uuid>",
  "type": "claim",
  "label": "...",
  "subtitle": "...",
  "status": {
    "review_status": "needs_review",
    "source_validation_status": "source_valid"
  },
  "metadata": {
    "document_filename": "...",
    "page_number": 1,
    "chunk_index": 0
  }
}
```

Edge shape:

```json
{
  "id": "claim:<uuid>--HAS_SOURCE--source_reference:<uuid>",
  "type": "HAS_SOURCE",
  "source": "claim:<uuid>",
  "target": "source_reference:<uuid>",
  "label": "forrása",
  "metadata": {}
}
```

Warning shape:

A jelenlegi baseline-ban nincs normal node/edge csonkolas es nincs `graph_truncated` warning. A `limits` mezok a visszaadott tenyleges node/edge darabszamot jelzik.

## Backend implementacios fajlok

Javasolt uj fajlok:

- `app/schemas/relationship_graph.py`
- `app/services/relationship_graph.py`
- `app/api/v1/relationship_graph.py`

Router bekotes:

- `app/api/v1/__init__.py` vagy a jelenlegi router registry mintaja szerint.

Teszt fajl:

- `tests/test_relationship_graph.py`

## Backend service felelossegek

`relationship_graph.py` service:

1. validalja az `object_type` erteket,
2. betolti a fokuszobjektumot case-bound modon,
3. ellenorzi a source-valid fokuszfeltetelt,
4. osszegyujti a kozvetlen source/kapcsolodo node-okat,
5. deduplikalja a node-okat es edge-eket stabil id alapjan,
6. ervenyesiti az 50 fokuszobjektumos vedokorlatot,
7. node/edge csonkolas nelkul visszaadja a projection response-t.

## Source-valid fokusz validacio

Ha a fokuszobjektum nem valaszthato:

```text
HTTP 400
```

Pelda magyar UI-ra mappelheto hiba:

```text
Ehhez az objektumhoz nincs érvényes forráshivatkozás, ezért első körben nem nyitható kapcsolati térkép.
```

Nem talalt vagy masik ugyhoz tartozo objektum:

```text
HTTP 404
```

## Frontend modul terv

Uj work surface:

```text
Kapcsolati térkép
```

Sidebar helye:

- `Ügy munkapad` utan vagy `Általános iratkérdező` elott javasolt,
- vegleges sorrend UI proba utan dontheto el.

Elso layout:

1. Bal/felso panel: `Megjelenítendő objektum`
   - objektumtipus szuro,
   - keresomező,
   - source-valid strukturalt objektum kartyak,
   - `Térkép megnyitása` gomb.

2. Fo panel: `Kapcsolati térkép`
   - React Flow canvas,
   - ures allapot,
   - loading/error allapot,
   - node reszlet oldalsav vagy alsopanel.

Elso verzio lehet egyszerubb:

- ha a user az `Ügy munkapad` objektumreszletebol erkezik, automatikusan
  betolti a fokuszobjektum grafjat;
- a dedikalt modul objektumvalaszto panelje elso korben minimalis lehet, de
  a szerkezet mar tamogassa a kesobbi keresos listat.

## Frontend adatforrasok

Objektumvalaszto jelenlegi adatforrasa:

- kulon, source-valid `review-report` lekerdezes, amely nem veszi at az `Áttekintési jelentés` panel aktualis szuroit;
- igy a `Megjelenítendő objektum` lista modulfüggetlen marad, mikozben ugyanazokat a source-valid objektumokat hasznalja.

Jelenlegi implementacio:

- ne vezessunk be kulon candidate endpointot azonnal,
- az `Ügy munkapad` objektumreszletbol indulo atadas legyen az elso biztos
  hasznalati ut,
- a `Kapcsolati térkép` modulon legyen ures/varakozo allapot es kesobb bovitheto
  objektumvalaszto.

Ha megis kell minimalis valaszto az elso korben, akkor hasznaljuk a review
report API-t source-valid filterrel, es csak a frontend szurje a tamogatott
objektumtipusokat.

## Aktualis frontend layout dontes

A live prototipus alapjan az elso mukodo elrendezes nem klasszikus bal panel +
jobb graf, hanem ket soros vizsgalati nezet.

1. Felso inspektor sor, fixen korlatozott magassaggal:

   - `Megjelenítendő objektum`
     - objektumtipus szuro,
     - keresomezo,
     - source-valid objektumkartyak,
     - egyfokuszu kivalasztas,
     - `Térkép megnyitása` gomb.
   - `Elemek`
     - a terkepen kijelolt node adatai,
     - indulaskor a fokusz node adatai,
     - ures/helykitolto allapot, ha nincs kijeloles.
   - `Kapcsolatok`
     - kijelolt edge adatai, ha edge-re kattint a user,
     - kijelolt node kozvetlen kapcsolatai, ha node van kijelolve,
     - ures/helykitolto allapot, ha nincs megjelenitheto kapcsolat.

2. Also teljes szelessegu graf sor:

   - `Kapcsolati térkép`
   - read-only React Flow / XYFlow canvas,
   - pan/zoom/fit controls,
   - node/edge kattintas az inspektor panelek frissitesere.

Elv:

- a graf a vizualis osszefuggest mutatja,
- a hosszu szakmai reszletek nem a graf node-okba kerulnek, hanem a felso
  `Elemek` es `Kapcsolatok` panelekbe,
- a felso sor belul scrollozhat, hogy ne nyomja le a terkepet,
- mobilon a harom felso panel egymas ala torik, es nem tartja a desktop fix
  magassagi kenyszert.

## Aktualis tartalmi UX: graf retegkapcsolok

A backend projection tobb reteget ad vissza, mint amennyire a napi vizualis
attekinteshez alapbol szukseg van. A frontend ezert retegkapcsolokkal szuri a
React Flow canvasra kuldott lathato grafot. A cel nem az adatok eldobasa, hanem
a lathato graf letisztitasa.

Alapertelmezett lathato mag:

- fokusz strukturalt objektum,
- `source_reference`,
- erintett `document` / `page` kontextus.

Ez valaszolja meg a legfontosabb vizsgalati kerdest:

```text
Mi ez az objektum, milyen forrasidezettel tamasztottuk ala, es melyik
irat/oldal kontextushoz tartozik?
```

Opcionális frontend rétegek checkboxokkal:

- `Irat`
  - `document`.
- `Oldal`
  - `page`.
- `Szövegrész`
  - `chunk`.
- `Forráshivatkozás`
  - `source_reference`.
- `Kapcsolódó objektumok`
  - nem fokusz `claim`, `event`, `entity`, `missing_item_candidate` node-ok,
  - `SHARES_SOURCE_WITH` jellegu kapcsolatok.
- `Ellentmondások`
  - `contradiction_candidate`,
  - `CONTRADICTS_CLAIM_A`,
  - `CONTRADICTS_CLAIM_B`.

Megvalositott implementacios elv:

- az API valtozatlanul a teljes `nodes` / `edges` valaszt adja;
- a frontend teljes valaszt kap, majd lokalisan szur a bekapcsolt retegek
  szerint;
- a `Megjelenítendő objektum` panel objektumtipus-szuroje alapbol `Összes`
  allapotbol indul;
- a React Flow canvas fele mar a lathato graf megy;
- edge csak akkor jelenik meg, ha mindket vegpontja lathato;
- az `Elemek` es `Kapcsolatok` inspektor is a lathato grafhoz igazodik, hogy ne
  lehessen olyan elemre mutatni, amely a canvasrol eppen el van rejtve.

Alapertelmezett checkbox allapot:

- `Irat`: bekapcsolva,
- `Oldal`: kikapcsolva,
- `Szövegrész`: kikapcsolva,
- `Forráshivatkozás`: bekapcsolva,
- `Kapcsolódó objektumok`: kikapcsolva,
- `Ellentmondások`: kikapcsolva.

Kesobbi bovites lehet a retegek megjegyzese felhasznaloi preferenciakent, de
az elso korben eleg az egyszeru lokalis frontend state.

## React Flow / XYFlow

Javasolt frontend dependency:

```text
@xyflow/react
```

Elso verzios kepessegek:

- node megjelenites tipus szerinti szinnel,
- edge label,
- zoom/pan,
- fit view,
- node click -> reszletek,
- adat/kapcsolat szempontbol read-only canvas,
- ideiglenes node-mozgatas egerrel.

Ne legyen elso korben:

- node szerkesztes,
- edge letrehozas,
- draggel letrehozott kapcsolat,
- mentett layout.

Megvalositott drag dontes:

- a node-ok ideiglenesen mozgathatok egerrel;
- a poziciok nincsenek mentve backendbe vagy local storage-ba;
- uj graph betoltesnel, retegszuresnel vagy frissitesnel az automatikus layout
  ujra ervenyesul;
- node/edge szerkesztes, uj kapcsolat rajzolasa es edge reconnect tovabbra is
  tiltott.

## Node vizualis szabalyok

Node tipusok szinei legyenek CSS tokenekre kotve, ne inline ad hoc szinek.

Javasolt tipusjelek:

- claim: allitas jellegu,
- event: esemeny jellegu,
- entity: entitas jellegu,
- missing_item_candidate: dokumentum/hiany jellegu,
- contradiction_candidate: figyelmezteto/konfliktus jellegu,
- source_reference: forras jellegu,
- document/page/chunk: forrashely jellegu,
- research_finding: munkadarab/provenance jellegu,
- analysis_run: technikai/provenance jellegu.

Statusz jelzes:

- review status chip,
- source status chip,
- focus node kiemeles.

## Magyar UI szovegek

Lathato cimek:

- `Kapcsolati térkép`
- `Megjelenítendő objektum`
- `Térkép megnyitása`
- `Kapcsolati térkép megnyitása`
- `Nincs megjelenített kapcsolati térkép`
- `Válassz egy érvényes forráshivatkozású objektumot.`
- `A kapcsolati térkép elemszám-limit miatt rövidítve lett.`

Edge magyar label javaslat:

- `HAS_SOURCE`: `forrása`
- `SOURCE_IN_DOCUMENT`: `iratban`
- `SOURCE_ON_PAGE`: `oldalon`
- `SOURCE_IN_CHUNK`: `szövegrészben`
- `CONTRADICTS_CLAIM_A`: `állítás A`
- `CONTRADICTS_CLAIM_B`: `állítás B`
- `SHARES_SOURCE_WITH`: `azonos forrás`

## Ugy munkapad integracio

Az `Áttekintési jelentés` / `Találat részletei` panelen, ha a kijelolt objektum
tamogatott es source-valid:

```text
Kapcsolati térkép megnyitása
```

Gomb viselkedes:

1. work surface valtasa `Kapcsolati térkép` modulra,
2. fokusz objektum tipus/id atadasa frontend state-ben,
3. modul tetejere scroll,
4. graph API hivas,
5. eredmeny megjelenites.

Ha nem source-valid:

- gomb ne jelenjen meg, vagy legyen disabled magyar tooltip/hinttel.

Elso korben javaslat:

- csak source-valid es tamogatott objektumoknal jelenjen meg.

## Tesztterv

Backend tesztek:

1. `claim` graph:
   - focus claim node,
   - source_reference node,
   - document/page/chunk node,
   - `HAS_SOURCE` edge.

2. `event` graph:
   - event source chain.

3. `missing_item_candidate` graph:
   - missing item source chain.

4. `entity` graph:
   - valid mention/source chain.

5. `contradiction_candidate` graph:
   - contradiction node,
   - claim A/B node,
   - claim source chains.

6. invalid focus:
   - source-invalid object -> 400.

7. case isolation:
   - masik ugy objektuma -> 404.

8. limit behavior:
   - 50 fokuszobjektum folott validation hiba;
   - node/edge csonkolas normal mukodesben nincs.

Frontend ellenorzes:

- `npm --prefix frontend run build`
- source-valid detail gomb megjelenik,
- source-invalid detail gomb nem jelenik meg,
- graph empty/loading/error state,
- React Flow canvas nem log ki desktopon es mobilon.

## Implementacios sorrend

### 1. Backend schema/service/API

- `app/schemas/relationship_graph.py`
- `app/services/relationship_graph.py`
- `app/api/v1/relationship_graph.py`
- router bekotes
- alap tesztek claim/event/missing/entity/contradiction fokuszra

### 2. Frontend API kliens es tipusok

- graph response tipusok `frontend/src/api.ts`-ben
- `fetchRelationshipGraph(...)` helper

### 3. Frontend work surface skeleton

- sidebar menu: `Kapcsolati térkép`
- surface header illeszkedjen a meglévő egységes modulfejléchez
- empty state
- graph loading/error state

### 4. React Flow megjelenites

- dependency felvetele,
- node/edge mapping backend response-bol,
- read-only canvas,
- fit view,
- node click detail.

### 5. Ugy munkapad handoff

- kesz: gomb a source-valid, tamogatott strukturalt objektum reszlet panelen,
- kesz: surface valtasa,
- kesz: fokusz objektum atadasa,
- kesz: modul tetejere scroll es graph betoltes.

### 6. UX finomitas

- kesz: node szinek/chipek CSS tokenekkel,
- kesz: edge label olvashatosag alapverzio,
- kesz: truncation warning,
- kesz: objektumkartyas valaszto a kezi UUID input helyett,
- kesz: frontend retegkapcsolok,
- kesz: alap mobil/overflow kezeles.

## Kovetkezo nagyobb szelet: tobbfokuszu graf

A kovetkezo fejlesztesi kor celja:

```text
Tobb source-valid objektum egyideju kijelolese es egy kozos kapcsolati terkepen
valo megjelenitese.
```

Ez a fejezet meg nem fajl-/endpoint-szintu implementacios terv, hanem a
kovetkezo nagyobb szelet reszletes termek- es mukodesi celrogzitese. A konkret
implementacios bontast kulon kovetkezo lepesben kell elkesziteni.

### Mi a problema, amit megold

Az egyfokuszu graf jol mutatja egy adott strukturalt objektum kozvetlen
forras/provenance kapcsolatait. A nyomozati gondolkodasban viszont gyakran nem
egyetlen objektum erdekes, hanem tobb egymas melle tett allitas, esemeny,
entitas vagy hianyjelolt kozti osszefugges.

Pelda felhasznaloi helyzetek:

- a user tobb tanubol szarmazo allitast akar egymas mellett latni;
- egy entitas, egy esemeny es egy allitas kozos forrasait akarja vizsgalni;
- latni akarja, hogy ket vagy tobb objektum ugyanahhoz az irathoz,
  szovegreszhez, elemzesi futashoz vagy kutatasi talalathoz kapcsolodik-e;
- ellenorizni akarja, hogy egy ellentmondasjelolt milyen allitasok es
  forrasok kozott all fenn.

A cel nem az, hogy a rendszer uj kapcsolatokat talaljon ki, hanem hogy a
felhasznalo altal kijelolt objektumok mar letezo, audit-kovetheto kapcsolatait
egy kozos vizualis terbe rendezze.

### Alap mukodesi elkepzeles

Felhasznaloi oldalrol:

1. A `Kapcsolati térkép` modulban a user objektumokat valaszt ki.
2. A valaszto tovabbra is csak az aktualis ugy source-valid, tamogatott
   strukturalt objektumait mutatja.
3. A radio/egyfokuszu valasztas helyett checkboxos tobbes kijeloles jelenik meg.
4. A user legfeljebb 50 fokuszobjektumot jelolhet ki.
5. A felulet mutatja a kijeloles szamat, peldaul:

   ```text
   3 kijelölve / 50
Összes: n
   ```

6. A `Kijelöltek térképre helyezése` akcio egy kozos kapcsolati terkepet ker.
7. A grafon minden kijelolt objektum fokusz node-kent jelenik meg.
8. A jelenlegi retegkapcsolok tovabbra is ugyanugy mukodnek:
   - alapertelmezett mag: fokusz objektumok + source reference + chunk,
   - opcionális: irat/oldal, elemzesi eredet, kapcsolodo objektumok,
     ellentmondasok.

### Kivalaszthato objektumok

Az elso multi-focus verzio ugyanazokat az objektumtipusokat tamogassa, mint a
single-focus baseline:

- `claim`
- `event`
- `entity`
- `missing_item_candidate`
- `contradiction_candidate`

Kivalasztasi feltetelek:

- az objektum az aktualis ugyhoz tartozik;
- az objektum source-valid;
- review statusz alapjan nincs kizaras;
- source-invalid / unconfirmed / nincs ervenyes forrashivatkozas allapotu
  objektum tovabbra sem lehet fokuszobjektum.

Az elutasitott, ellenorzesre varo, ellenorzott vagy korrekcioval kizart
objektumok megjelenhetnek, ha a forrashivatkozasuk ervenyes. Ezek statuszat a
node-on jelezni kell, de nem szabad emiatt kiszurni oket.

### Kategoria es kijeloles

Az objektumvalaszto elso multi-focus verzioja maradhat tipus-szuro alapu:

- a user valaszt egy objektumtipust;
- a lista az adott tipus source-valid objektumait mutatja;
- a user checkboxokkal kijelolhet tobb elemet.

Kovetkezo finomitas lehet:

- `Összes típus` nezete,
- tipusonkenti csoportositas,
- `Összes látható kijelölése`.

Ezek nem kotelezoek az elso multi-focus korben. A fontosabb elso cel az, hogy a
tobbes kijeloles es a kozos graf technikailag stabil legyen.

### Fokuszobjektum limit

Az elso limit:

```text
max 50 fokuszobjektum
```

Indok:

- egy graf nagyon gyorsan vizualis zajja valhat;
- a React Flow canvas is attekinthetobb, ha nem engedjuk kontroll nelkul
  elszabadulni;
- a backend projection is eroforras-igenyesebb, mert minden fokuszobjektum
  forras/provenance/kornyezeti kapcsolatait ossze kell gyujteni.

Az 50-es fokuszobjektum-limit frontend es backend oldalon is legyen ervenyesitve.

Kesobb live teszt alapjan:

- novelheto,
- csokkentheto,
- vagy bevezetheto kulon `halado/osszefoglalo` nezeti mod.

### Backend valasz tartalmi celja

A multi-focus valasz tovabbra is read-only graph projection.

A response tartalmazza:

- az ugy azonositojat;
- a fokusz node-ok listajat;
- a node-ok listajat;
- az edge-ek listajat;
- limiteket;
- figyelmezteteseket.

Fontos:

- ugyanaz a `source_reference`, `document`, `page`, `chunk`, `analysis_run` vagy
  `research_finding` csak egyszer jelenjen meg;
- ha tobb fokuszobjektum ugyanarra a source_reference-re mutat, ez pont legyen
  lathato a grafban, ne duplikalt forras-node-okban vesszen el;
- a deduplikacio stabil node id alapjan tortenjen;
- edge deduplikacio is legyen stabil, hogy ugyanaz a kapcsolat ne jelenjen meg
  tobbszor.

### Kapcsolati logika

Az elso multi-focus verzio ne vezessen be uj edge-tipusokat pusztan azert, mert
tobb fokusz van. A jelenlegi edge tipusok mar elegendoek az alap osszkephez:

- `HAS_SOURCE`
- `SOURCE_IN_DOCUMENT`
- `SOURCE_ON_PAGE`
- `SOURCE_IN_CHUNK`
- `CONTRADICTS_CLAIM_A`
- `CONTRADICTS_CLAIM_B`
- `SHARES_SOURCE_WITH`

A kozosseg lathatosagat elsosorban a megosztott node-ok adjak:

- kozos source_reference,
- kozos chunk,
- kozos document/page.

Csak akkor erdemes kesobb uj, virtualis edge-et bevezetni, ha live hasznalat
kozben kiderul, hogy a kozos node-ok vizualisan nem eleg beszedesek.

### Graf retegkapcsolok multi-focus alatt

A mar megvalositott retegkapcsolok megmaradnak.

Alapertelmezett lathato mag multi-focus esetben:

- minden fokuszobjektum,
- minden kozvetlen source_reference,
- minden erintett dokumentum/oldal kontextus.

Opcionális retegek:

- `Irat`
- `Oldal`
- `Szövegrész`
- `Forráshivatkozás`
- `Kapcsolódó objektumok`
- `Ellentmondások`

Elv:

- a retegkapcsolo ne toroljon adatot, csak a canvasra kuldott lathato grafot
  szurje;
- az inspektor panelek mindig a lathato grafhoz igazodjanak;
- ha egy edge egyik vegpontja reteg miatt rejtett, az edge se jelenjen meg.

### Ugy munkapad handoff viselkedes

A jelenlegi `Ügy munkapad` handoff egy objektumot ad at.

Multi-focus utan is maradhat ez a viselkedes:

- egy gombnyomas egyetlen objektumot nyit meg a `Kapcsolati térkép` modulban;
- technikailag viszont mar az uj multi-focus endpointot hivhatja egyetlen
  fokuszobjektummal;
- ezutan a user a modulon belul tovabbi objektumokat jelolhet ki es ujra
  generalhatja a kozos terkepet.

Ez tiszta atmenetet ad:

- a single-focus UX megmarad gyors belepesnek;
- a backend viszont egyseges multi-focus utra allhat at.

### Single-focus GET kivezetes celja

A jelenlegi:

```text
GET /api/v1/cases/{case_id}/graph/object/{object_type}/{object_id}
```

endpoint addig maradjon, amig:

- az uj multi-focus POST endpoint el nem keszul;
- a frontend objektumvalaszto es az `Ügy munkapad` handoff at nem all az uj
  endpointra;
- a tesztek nem fedik az egyfokuszu esetet az uj endpointon keresztul is.

Utana a regi GET endpoint:

- kivezetheto,
- routerbol torolheto,
- tesztekbol torolheto vagy atirhato,
- dokumentaciobol legacy megjegyzesre redukalhato.

### Nem-cel ebben a szeletben

Ebben a multi-focus celrogzitesben tovabbra sem cel:

- teljes ugy graf;
- graph database;
- AI altal generalt kapcsolat;
- automatikus kapcsolatjavaslat;
- forras-invalid fokuszobjektum;
- graf szerkesztes;
- layout mentes;
- edge szuro;
- audit node;
- human review node;
- shortest path / ket objektum kozti optimalis utvonal;
- teljes backend tesztmatrix minden edge/limit kombinaciora.

Ezek kozul nehany kesobb hasznos lehet, de most nem szabad veluk szetfesziteni a
scope-ot.

### Elfogadasi kep

Az elso multi-focus fejlesztes akkor tekintheto sikeresnek, ha:

- legalabb 2-3 source-valid objektum kijelolheto;
- a graf egy kozos canvasra rendezi oket;
- kozos source/chunk/document node-ok deduplikaltan jelennek meg;
- a lathato graf nem valik hasznalhatatlanul zsufoltta kis elemszamnal;
- a retegkapcsolok tovabbra is mukodnek;
- egyetlen objektumos handoff sem romlik el;
- source-invalid objektum tovabbra sem valaszthato fokusznak.

## Multi-focus konkret implementacios terv

Ez a fejezet az elozo celrogzitesbol indul ki, es azt bontja backend/frontend
megvalositasi lepesekre. A cel tovabbra is kis scope: tobb fokuszobjektum kozos
read-only grafja, nem teljes ugy graf es nem uj kapcsolatfeltalalo reteg.

### Aktualis implementacios allapot

Az elso backend szelet elkeszult:

- multi-focus request schema;
- response `focus_node_ids` / `focus_objects` mezok;
- kozos `build_relationship_graph_for_objects(...)` service ut;
- a regi `build_relationship_graph(...)` egy elemu wrapperkent az uj kozos
  service utat hasznalja;
- `POST /api/v1/cases/{case_id}/graph/objects` endpoint;
- celzott backend tesztek az egyfokuszu kompatibilitasra, kozos forras
  deduplikaciora, source-invalid tiltasra es a fokuszobjektum capre.

Az elso frontend atvezetes is elkeszult:

- frontend API helper es UI atvezetes az uj POST endpoint hasznalatara;
- checkboxos tobbes objektumkijeloles;
- `Kijelöltek térképre helyezése`;
- `Kijelölés törlése`;
- `Ügy munkapad` handoff atvezetese egy elemu multi-focus requestre;
- a regi frontend GET helper es backend GET endpoint kivezetese.

Kovetkezo implementacios lepes:

- live UI ellenorzes;
- ha stabil, a multi-focus UX finomhangolasa;
- kesobb csak konkret igeny alapjan `Összes típus` / `Összes látható kijelölése`
  vagy teljes ugy graf irany.

### 1. Backend schema bovites

Erintett fajl:

- `app/schemas/relationship_graph.py`

Uj request schema:

```python
class RelationshipGraphFocusObject(BaseModel):
    object_type: str
    object_id: UUID


class RelationshipGraphMultiFocusRequest(BaseModel):
    focus_objects: list[RelationshipGraphFocusObject] = Field(min_length=1, max_length=50)
    include_shared_sources: bool = True
    max_nodes: int | None = None
    max_edges: int | None = None
```

Response schema bovites:

- a jelenlegi `RelationshipGraph` maradjon a kozos response alapja;
- uj opcionális vagy kotelezo mezok kellenek a multi-focus valaszhoz:

```python
focus_node_ids: list[str]
focus_objects: list[RelationshipGraphFocusObject]
```

Atmeneti kompatibilitasi dontes:

- a jelenlegi `focus_node_id`, `focus_object_type`, `focus_object_id` mezok
  maradhatnak az egyfokuszu kompatibilitas miatt;
- multi-focus valaszban ezek az elso fokuszobjektumra mutathatnak;
- a frontend uj kodja viszont mar a `focus_node_ids` mezot hasznalja.

Kesobbi tisztitas:

- a service-level egyfokuszu wrapper megmaradhat teszt/kompatibilitasi
  segedutkent;
- a response schema kesobb egyszerusitheto, ha mar semmi nem igenyli a
  `focus_node_id`, `focus_object_type`, `focus_object_id` kompatibilitasi mezoket.

### 2. Backend service refaktor

Erintett fajl:

- `app/services/relationship_graph.py`

Cel:

- ne masoljuk le a single-focus logikat;
- a mostani `build_relationship_graph(...)` alatt/mellett jojjon letre egy
  kozos, fokuszobjektum-listat kezelni tudo grafepito ut.

Javasolt uj service entrypoint:

```python
def build_relationship_graph_for_objects(
    db: Session,
    *,
    case_id: UUID,
    focus_objects: list[RelationshipGraphFocusObject],
    include_shared_sources: bool = True,
    max_nodes: int = 150,
    max_edges: int = 250,
) -> RelationshipGraph:
    ...
```

Belso mukodes:

1. validalja, hogy 1..50 fokuszobjektum erkezett;
2. validalja minden `object_type` erteket a `SUPPORTED_FOCUS_OBJECT_TYPES`
   alapjan;
3. case-bound modon betolti az osszes fokuszobjektumot;
4. minden fokuszobjektumnal ellenorzi a source-valid feltetelt;
5. stabil sorrendben deduplikalja az esetleg duplan bekuldott fokuszokat:
   `object_type + object_id`;
6. egy kozos `_GraphBuilder` peldanyba epiti be minden fokusz objektum:
   - objektum node-jat `is_focus=true` metadata jelzessel,
   - source chainjeit,
   - contradiction agat,
   - shared-source szomszedait, ha be van kapcsolva;
7. a vegso, deduplikalt grafot adja vissza node/edge csonkolas nelkul; a meretvedo korlat a fokuszobjektum limit.

Refaktor irany:

- a jelenlegi `build_relationship_graph(...)` hivja az uj
  `build_relationship_graph_for_objects(...)` fuggvenyt egyetlen fokusz
  objektummal;
- igy az egyfokuszu es tobbfokuszu viselkedes kozos koduton marad;
- ez csokkenti annak kockazatat, hogy a ket endpoint kesobb elterjen egymastol.

### 3. Limit es warning viselkedes

Javasolt backend cap:

- `max_nodes` / `max_edges`: kompatibilitasi mezok, normal mukodesben nem csonkolnak;
- `focus_objects`: hard cap 50.

Warningok:

- tul sok fokuszobjektum:
  - request validation hiba, ne warning;
- node/edge vagas nincs normal mukodesben:
  - ne legyen `graph_truncated` warning;
- duplikalt fokuszobjektum:
  - ne legyen hiba; deduplikaljuk;
  - opcionálisan adhat `duplicate_focus_ignored` warningot, de elso korben nem
    szukseges, mert a frontend eleve meg tudja fogni.

Fontos:

- limit utan csak olyan edge maradjon, amelynek mindket vegpontja megmaradt;
- a fokusz node-ok lehetoseg szerint ne essenek ki a limit miatt;
- ha a limit miatt maradna ki fokusz node, az inkabb validacios vagy
  truncation-strategiai hiba legyen, ne csendes adatvesztes.

### 4. Backend API endpoint

Erintett fajl:

- `app/api/v1/relationship_graph.py`

Uj endpoint:

```text
POST /api/v1/cases/{case_id}/graph/objects
```

Body:

```json
{
  "focus_objects": [
    {"object_type": "claim", "object_id": "..."},
    {"object_type": "entity", "object_id": "..."}
  ],
  "include_shared_sources": true,
  "max_nodes": 150,
  "max_edges": 250
}
```

Hibakezeles:

- ismeretlen objektumtipus: `400`;
- source-invalid fokuszobjektum: `400`;
- mas ugyhoz tartozo vagy nem letezo objektum: `404`;
- tul sok fokuszobjektum: Pydantic/FastAPI validation `422` vagy explicit
  `400`; a Pydantic `max_length=50` es a service oldali azonos limit ervenyes.

Single-focus GET migracios dontes:

- teljesult: a frontend atvezetes utan a GET endpoint ki lett vezetve;
- uj kod ne hasznalja a regi `/graph/object/{object_type}/{object_id}` format.

### 5. Frontend API helper

Erintett fajl:

- `frontend/src/api.ts`

Uj tipusok/helper:

```ts
export type RelationshipGraphFocusObject = {
  object_type: string;
  object_id: string;
};

export type RelationshipGraphRequest = {
  focus_objects: RelationshipGraphFocusObject[];
  include_shared_sources?: boolean;
  max_nodes?: number;
  max_edges?: number;
};

export function getRelationshipGraphForObjects(
  caseId: string,
  payload: RelationshipGraphRequest
): Promise<RelationshipGraph> {
  ...
}
```

Atmenet:

- teljesult: az `App.tsx` az uj helperre allt at;
- a regi `getRelationshipGraph(...)` helper torolve lett a frontend API
  retegbol.

### 6. Frontend state modell

Erintett fajl:

- `frontend/src/App.tsx`

Jelenlegi single-focus state:

- `relationshipGraphObjectType`
- `relationshipGraphObjectId`
- `selectedRelationshipObjectCandidate`

Uj multi-focus state javaslat:

```ts
const [selectedRelationshipFocusObjects, setSelectedRelationshipFocusObjects] =
  useState<RelationshipGraphFocusObject[]>([]);
```

Vagy praktikusabb lookup forma:

```ts
const [selectedRelationshipFocusKeys, setSelectedRelationshipFocusKeys] =
  useState<Set<string>>(new Set());
```

Kulcs:

```ts
`${object_type}:${object_id}`
```

Javaslat:

- React state-ben tombot vagy rekordot hasznaljunk, ne mutalhato `Set`-et
  kozvetlenul;
- a kartyaknal a kulcsbol szamoljuk, hogy kijelolt-e;
- maximum 50 kijelolesnel a tovabbi checkboxok legyenek disabled, vagy kattintas
  adjon magyar figyelmeztetest.

### 7. Frontend objektumvalaszto UI

Megmarad:

- objektumtipus szuro;
- keresomezo;
- source-valid objektumkartyak;
- kompakt cim + szovegresz elonezet.

Valtozik:

- radio jellegu kivalasztas helyett checkbox;
- kartyak kijelolt allapotot kapnak;
- megjelenik a szamlalo:

```text
3 kijelölve / 50
Összes: n
```

Gombok:

- `Kijelöltek térképre helyezése`
  - akkor aktiv, ha legalabb 1 objektum ki van jelolve;
- opcionális `Kijelölés törlése`
  - hasznos, de nem kotelezo elso korben.

Elso korben ne legyen:

- `Összes látható kijelölése`,
- `Összes típus`,
- drag/drop kijeloles,
- csoportos automatikus kijeloles.

### 8. Ugy munkapad handoff atvezetese

Jelenlegi viselkedes:

- a reszletpanel egy objektumot ad at a `Kapcsolati térkép` modulnak.

Uj viselkedes:

- ugyanaz a gomb marad;
- a handoff egyetlen objektummal tolti fel a multi-focus kijelolest;
- meghivja az uj `POST /graph/objects` endpointot egyetlen elemu
  `focus_objects` listaval;
- a user ezutan a `Kapcsolati térkép` modulban tovabbi objektumokat jelolhet ki.

Ezzel:

- a gyors egyobjektumos nyitas UX-e megmarad;
- backend oldalon mar az uj, kozos multi-focus utat hasznaljuk.

### 9. Frontend graph rendering

Erintett fajlok:

- `frontend/src/App.tsx`
- `frontend/src/RelationshipFlowCanvas.tsx`
- `frontend/src/styles.css`

Elv:

- a React Flow komponensnek tovabbra is egy `RelationshipGraph` tipusu lathato
  graf menjen;
- a layer-filter helper maradjon egy helyen;
- a `focus_node_ids` alapjan minden fokusz node kapjon fokusz vizualis jelzest;
- ha a response csak regi `focus_node_id` mezot tartalmaz, fallbackkent azt is
  kezelje, amig az atmenet tart.

CSS:

- a fokusz node stilus ne csak egy node-ra legyen kitalalva;
- tobb fokusz node eseten mindegyik kapja meg a fokusz keretet/hatteret;
- ne vezessunk be uj ad hoc szineket, maradjon a graph token rendszer.

### 10. Tesztterv

Backend target:

- `tests/test_relationship_graph.py`

Uj tesztesetek:

1. multi-focus claim + event:
   - ket fokusz node,
   - mindketto source chainje megjelenik.

2. kozos source deduplikacio:
   - ket objektum ugyanarra a source_reference-re mutat,
   - egy source_reference node,
   - ket `HAS_SOURCE` edge.

3. source-invalid fokusz tiltasa:
   - a request egyik fokusza source-invalid,
   - endpoint hibaval ter vissza.

4. case isolation:
   - masik ugy objektuma a listaban,
   - endpoint hibaval ter vissza.

5. max 50 fokusz cap:
   - 51 elemnel validation hiba.

6. single-focus through POST:
   - egyetlen objektummal ugyanaz a minimalis graf epul, mint a korabbi
     single-focus elvarasok szerint.

Frontend verifikacio:

- `npm --prefix frontend run build`;
- live UI:
  - tobb objektum kijelolheto;
  - szamlalo frissul;
  - 50 folott nem enged tovabbi kijelolest;
  - `Kijelöltek térképre helyezése` betolti a grafot;
  - retegkapcsolok mukodnek;
  - `Ügy munkapad` handoff tovabbra is mukodik.

### 11. Implementacios sorrend

Javasolt sorrend:

1. Kesz: backend schema bovites:
   - focus object request schema,
   - multi-focus request schema,
   - response `focus_node_ids` / `focus_objects` bovites.

2. Kesz: backend service refaktor:
   - uj `build_relationship_graph_for_objects(...)`;
   - regi `build_relationship_graph(...)` vezessen at erre egy elemmel.

3. Kesz: backend POST endpoint:
   - `POST /cases/{case_id}/graph/objects`;
   - hibamappeles a korabbi single-focus endpoint viselkedesevel osszhangban.

4. Kesz: backend tesztek:
   - multi-focus happy path,
   - deduplikacio,
   - source-invalid,
   - case isolation,
   - 50-es cap.

5. Kesz: frontend API helper:
   - uj POST helper,
   - tipusok.

6. Kesz: frontend state/UI:
   - checkboxos objektumkartyak,
   - kijeloles szamlalo,
   - `Kijelöltek térképre helyezése`.

7. Kesz: handoff atvezetes:
   - `Ügy munkapad` gomb egy elemu multi-focus requestet hasznal.

8. Kesz: frontend rendering finomitas:
   - tobb fokusz node kiemelese,
   - layer filter ellenorzes.

9. Kesz: regi GET endpoint kivezetese:
   - minden frontend hivas az uj POST-on megy;
   - a GET endpoint es helper torolve lett.

### 12. Kockazatok es vedokorlatok

Kockazat: a graf tul zsufolt lesz.

- Vedokorlat: 50 fokuszobjektumos limit es layer toggles; node/edge csonkolas nem hasznalt normal mukodesben.

Kockazat: single-focus mukodes regresszal.

- Vedokorlat: a regi `build_relationship_graph(...)` az uj multi-focus service-t
  hivja egy elemmel; legyen single-focus-through-POST teszt.

Kockazat: frontend state tul bonyolult lesz.

- Vedokorlat: az objektumtipus szuro es a lathato elemek csoportos kijelolese/levetele mar tamogatott, de a kijeloles 50 fokuszobjektumnal megall.

Kockazat: GET endpoint kivezetese tul koran tortenik.

- Allapot: kezelt. A torles csak azutan tortent meg, hogy az App mar az uj POST
  helperre allt at, a frontend build sikeres volt, es a celzott backend graph
  tesztek zolden lefutottak.

Fix tervkent megtartott hianyok:

- teljes ugy graf meg nincs, es csak akkor kovetkezzen, ha a tobbfokuszu
  valtozat stabil es attekintheto;
- mobil finomhangolast kulon, elo nezetben erdemes vegignezni;
- live UI validacio utan lehet donteni, hogy kell-e tovabbi multi-focus UX
  finomitas, peldaul `Összes látható kijelölése`, magasabb fokuszlimit vagy
  tovabbi graf-szuro.

Jelenlegi baseline allapot:

- 2026-07-02 frissites: a `Kapcsolati térkép` objektumvalasztoja sajat, source-valid objektumlistat hasznal, fuggetlenul az `Áttekintési jelentés` panel aktualis szuroitol. A multi-focus limit 50 fokuszobjektum; a UI `x kijelölve / 50` es `Összes: n` chipeket mutat, 50 utan a tovabbi nem kijelolt checkboxok disabled allapotba kerulnek. A backend nem csonkol node/edge cap alapjan normal mukodesben; a graf `limits` mezoi a visszaadott tenyleges node/edge darabszamot jelzik.
- a multi-focus backend es frontend mukodes technikailag kesznek tekintheto;
- a publikus graph betoltes egysegesen a `POST /graph/objects` utvonalon megy;
- az egyobjektumos handoff is ugyanazt az utat hasznalja;
- a kovetkezo kozvetlen munka nem core funkciohiany potlasa, hanem a graf
  vizualis erositesenek es olvashatosaganak finomhangolasa.

Tudatosan kesobbre hagyott, de nyilvantartott elemek:

- teljes backend tesztmatrix nincs 100%-osan kibovitve minden tipusra es
  limit-esetre;
- edge szurok nincsenek;
- layout mentes nincs;
- audit node-ok es human review node-ok nincsenek.

Az elso multi-focus implementacio ne probaljon teljes ugy grafot vagy
automatikus kapcsolatjavaslatot adni. A cel tovabbra is read-only projection a
mar letezo, audit-kovetheto relacios/source-bound adatokbol.

## Bovithetosegi pontok

Kesobbi bovitesre hagyott tiszta helyek:

- objektumvalaszto sajat backend candidate API,
- audit/provenance reteg,
- human_review node-ok,
- source-invalid opcionalis megjelenites,
- edge tipus szurok,
- layout mentese,
- legrövidebb kapcsolat ket objektum kozott,
- teljes ugy graf osszefoglalo nezet.

## Lezart korabbi kerdesek

- A sidebar helye eldolt: a `Kapcsolati térkép` dedikalt work surface-kent
  elerheto.
- Az elso verzio nem csak `Ügy munkapad` handoffbol mukodik: van dedikalt,
  source-valid objektumkartyas valaszto is.
- A kezi UUID inputot a frontend kivaltotta; a backend single-focus endpointot a
  multi-focus POST endpoint atvette es a regi GET utvonal ki lett vezetve.

## Kovetkezo related-object terv

Az iratalapu kapcsolodo objektumok, a regi checkboxos Kapcsolodo objektumok reteg kivezetese, valamint az uj kulon paneles related-by-documents workflow reszletes terve es implementacios allapota kulon dokumentumban van rogzítve: Design_documents/32_relationship_map_related_objects_plan.md. A normal objektumkozpontu grafban a shared-source neighbor projection mar nem aktiv; a kapcsolodo objektumok kulon, user altal inditott backend lekerdezesbol kerulnek vissza. A kapcsolodo objektum panel elfogadott UI-ja a top sorban kozvetlenul a Megjelenitendo objektum panel utan kovetkezik, `Kereses` es `Lathatok kijelolese` muveletekkel, valamint objektumtipus szerinti kartyaszinezessel a kulon meta sor helyett.
