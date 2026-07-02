# 32. Kapcsolati terkep - iratalapu kapcsolodo objektumok terve

## 2026-07-02 implementacios allapot

Ez a szelet elso korben megvalosult.

Megvalosult elemek:

- a regi checkbox/layer alapu `Kapcsolodo objektumok` reteg kikerult a frontend layer toggle-ok kozul;
- a normal backend graph projection mar nem gyujt automatikus shared-source szomszedokat;
- az `include_shared_sources`, a backend node/edge csonkolasi request mezok es a `SHARES_SOURCE_WITH` normal graf edge kikerult az aktiv szerzodesbol;
- bekerult a `POST /api/v1/cases/{case_id}/graph/related-by-documents` endpoint;
- a frontend top sor negy paneles lett, elfogadott sorrendben: `Megjelenitendo objektum`, `Kapcsolodo objektumok`, `Kijelolt csomopont tartalma`, `Kapcsolatok`;
- a kapcsolodo objektum keresese csak strukturalt objektum node kijelolese utan indithato;
- a kapcsolodo panel elsodleges gombja `Kereses`, mellette `Lathatok kijelolese` segiti a lathato talalatok gyors kijeloleset;
- a talalatok kartyalistaban jelennek meg, es csak kijeloles utan kerulnek fel a terkepre;
- a kapcsolodo objektum kartyak es a fo objektumvalaszto kartyai az objektumtipus szerinti graf-szint hasznaljak hatterszinkent, igy a korabbi `tipus | kozos irat: n` meta sor nem jelenik meg kulon szovegkent;
- a meglévő 50 fokuszobjektumos cap tovabbra is ervenyes;
- celzott backend teszt bizonyitja, hogy a kapcsolat most kozos irat alapjan mukodik, nem kozos source_reference alapjan.

Friss verifikacio:

- `.venv/bin/python -m pytest tests/test_relationship_graph.py -q` -> 9 passed;
- `.venv/bin/python -m pytest -q` -> 409 passed, 1 Docling deprecation warning;
- `npm --prefix frontend run build` -> passed;
- `git diff --check` -> passed.


## Cel

Ez a dokumentum a Kapcsolati terkep kovetkezo fejlesztesi szeletet rogziti.

A cel nem uj igazsagreteg es nem automatikus AI-kapcsolatgyartas, hanem egy
celzott, user altal inditott feltaro muvelet:

Milyen tovabbi source-valid objektumok szerepelnek azokban az iratokban, amelyekben a terkepen kijelolt objektum is szerepel?

A funkcio a meglévő, audit-kovetheto, source-bound objektumokra epul.

## Kiindulo problema

A jelenlegi Kapcsolodo objektumok reteg checkboxos megoldasa tul szuk es nem eleg
hasznos.

Jelenlegi mukodes nagy vonalban:

- a frontend layer toggle lokalisan megjelenit vagy elrejt mar betoltott nem
  fokusz objektum node-okat;
- nem indit uj backend lekerdezest;
- nem boviti a grafot;
- a backend shared-source jelleggel olyan objektumokat tudott hozzatenni,
  amelyek ugyanarra a konkret source_reference rekordra epultek.

Ez a gyakorlatban ritkan ad hasznos talalatot, mert a jelenlegi workflow-ban egy
forrashivatkozas jellemzoen egy konkret objektum alapja. Nyomozati/emberi
szemmel sokkal hasznosabb kapcsolat, ha azt vizsgaljuk, hogy a kijelolt objektum
mely iratokban szerepel, es ezekben az iratokban milyen tovabbi objektumok
fordulnak elo.

## Kivezetesi dontes: regi checkboxos kapcsolodo objektum reteg

A jelenlegi Kapcsolodo objektumok checkboxos/layeres megoldast teljesen ki kell
vezetni frontend es backend oldalrol is.

Kivezetendo frontend elemek:

- related_objects layer key/state;
- Kapcsolodo objektumok checkbox a retegkapcsolok kozul;
- layer filter ag, amely nem fokusz objektum node-okat csak lathatova tesz;
- minden olyan label vagy empty-state, amely a regi layeres megoldasra utal.

Kivezetendo backend elemek:

- automatikus shared-source neighbor gyujtes a normal graph projectionben;
- include_shared_sources request/schema/API mezo, ha mar nincs aktiv szerepe;
- SHARES_SOURCE_WITH edge normal objektumkozpontu terkepen;
- a shared-source szomszedokat eloallito service ag, ha csak ezt a regi UI
  retegkapcsolot szolgalta ki.

Fontos: ha kesobb kulon provenance vagy audit grafban szukseg lesz pontos
shared-source kapcsolatokra, azt uj, tudatos terv alapjan kell visszahozni. A
mostani objektumkozpontu Kapcsolati terkepben ez nem maradjon felig elo legacy
kod.

## Uj fogalom: kijelolt objektum

Ebben a funkcioban a kijelolt objektum nem a Megjelenitendo objektum panel
checkboxos kijeloleset jelenti.

A kijelolt objektum jelentese:

- a React Flow terkepen egerrel rakattintott aktualis node;
- csak strukturalt objektum node lehet;
- egy idoben pontosan egy node a muvelet celpontja.

Tamogatott node tipusok elso korben:

- claim;
- event;
- entity;
- missing_item_candidate;
- contradiction_candidate csak akkor, ha az iratkapcsolat a bemeneti objektumok
  alapjan egyertelmuen es zaj nelkul levezetheto.

Nem tamogatott node tipusok:

- document;
- page;
- chunk;
- source_reference.

Ezzel a UI-ban ket fogalom tisztan szetvalik:

- Megjelenitendo objektumok: mit akar a user feltenni a terkepre;
- Kijelolt csomopont: melyik mar lathato node-bol akar tovabb indulni.

## UI layout

A funkcio kapjon kulon panelt, ne keruljon bele a Megjelenitendo objektum
panelbe.

Javasolt felso sor:

Megjelenitendo objektum | Kijelolt csomopont tartalma | Kapcsolatok | Kapcsolodo objektumok

Indok:

- a Megjelenitendo objektum panel szerepe mar tiszta: objektumvalasztas es
  terkepre helyezes;
- a Kapcsolodo objektumok keresese masodik lepes: egy mar lathato, kattintassal
  kivalasztott objektumbol indulo feltaras;
- kulon panelben nem keveredik a kezdeti kivalasztas es a tovabbkereses
  fogalma.

Panel allapotok:

- nincs kijelolt node: helykitolto, peldaul Válassz egy objektumot a térképen;
- nem tamogatott node van kijelolve: disabled allapot, peldaul Ehhez a
  csomóponthoz nem kereshetők kapcsolódó objektumok;
- tamogatott strukturalt objektum van kijelolve: aktiv gomb es talalati lista.

Javasolt gomb:

Kapcsolodo objektumok keresese

## UX dontes: talalati lista, nem automatikus grafra dobas

Az uj backend lekerdezes eredmenye ne automatikusan keruljon a grafra.

Elsokoros felhasznaloi folyamat:

1. User rakattint egy objektum node-ra a terkepen.
2. A Kapcsolodo objektumok panel aktivva valik.
3. User megnyomja a Kapcsolodo objektumok keresese gombot.
4. Backend visszaadja az azonos iratokban szereplo tovabbi objektumokat.
5. A panel kartyalistaban mutatja a talalatokat.
6. User checkboxokkal kijelol nehany talalatot.
7. Kijeloltek terkepre helyezese hozzaadja oket a jelenlegi fokuszobjektum
   halmazhoz.
8. A graf frissul az uj fokuszhalmazzal.

Mi ne tortenjen:

- egy gombnyomasra ne keruljon fel automatikusan minden talalt objektum;
- ne lehessen kontroll nelkul 50+ objektumot rarakni a terkepre;
- a kapcsolodo objektum talalati lista ne irja felul a normal objektumvalasztot.

## Backend API terv

Javasolt endpoint:

POST /api/v1/cases/{case_id}/graph/related-by-documents

Javasolt request mezok:

- object_type: claim/event/entity/missing_item_candidate/contradiction_candidate;
- object_id: UUID;
- max_results: opcionális, kezdetben 100-as javasolt felső korlát.

Javasolt response mezok:

- case_id;
- source_object: object_type, object_id, title;
- documents: a kiindulo objektumhoz tartozo erintett iratok;
- objects: a talalt kapcsolodo objektumok listaja title, body_excerpt, review_status, source_validation_status, shared_document_count es shared_documents mezokkel.

Backend levezetes:

1. validalja a source objektum tipus/id erteket;
2. case-bound modon betolti az objektumot;
3. ellenorzi, hogy az objektum source-valid;
4. az objektum forrashivatkozasai vagy mentionjei alapjan meghatarozza az
   erintett dokumentumokat;
5. megkeresi azokat a mas source-valid strukturalt objektumokat, amelyeknek van
   forrasa vagy mentionje ezekben a dokumentumokban;
6. kizarja a kiindulo objektumot;
7. deduplikal object_type + object_id alapjan;
8. visszaadja a talalatokat tomor kartyazashoz eleg metaadattal.

Tamogatott objektumforrasok:

- claim: claim source linkek -> source_reference -> document;
- event: event source linkek -> source_reference -> document;
- missing_item_candidate: missing-item source linkek -> source_reference -> document;
- entity: entity mention/source kapcsolat -> source_reference vagy document;
- contradiction_candidate: elso korben csak akkor, ha a bemeneti claim/event
  parokon keresztul egyertelmuen levezetheto az irathalmaz; ha ez tul zajos,
  visszaadhato unsupported/ures allapot.

## Frontend integracio

Javasolt state-ek:

- relationshipRelatedCandidates;
- selectedRelationshipRelatedKeys;
- relationshipRelatedLoading;
- relationshipRelatedError;
- relationshipRelatedSourceNodeId.

Viselkedes:

- node kattintas torolje vagy ervenytelenitse a korabbi kapcsolodo talalati
  listat, ha masik node-ra valtunk;
- a keresogomb csak akkor aktiv, ha a kijelolt node tamogatott strukturalt
  objektum;
- a talalati kartya hasonlitson a normal objektumkartyakra:
  - checkbox;
  - cim;
  - rovid leiras/reszlet;
  - kozos irat: n chip;
- a mar terkepen levo vagy fokuszban levo objektumokat ne lehessen ujra
  hozzaadni;
- ha az 50-es focus cap elerne a hatart, a tovabbi hozzaadas legyen tiltott
  vagy adjon magyar visszajelzest.

## Elfogadasi kep

A szelet akkor tekintheto kesznek, ha:

- a regi Kapcsolodo objektumok checkbox mar nem lathato;
- a backend normal graph projection nem ad automatikus shared-source kapcsolodo
  objektumokat;
- a Kapcsolodo objektumok kulon panel csak graph-node kijeloles utan aktiv;
- a gomb backend lekerdezest indit;
- a visszakapott objektumok listaban jelennek meg, nem automatikusan a grafon;
- kijelolt talalatok feltehetok a terkepre az 50 fokuszobjektumos cap
  betartasaval;
- a Megjelenitendo objektum, Kijelolt csomopont tartalma, Kapcsolatok es React
  Flow canvas mukodese nem romlik.

## Implementacios sorrend

1. Backend cleanup:
   - shared-source neighbor projection eltavolitasa;
   - include_shared_sources kivezetese;
   - SHARES_SOURCE_WITH normal graph projectionbol valo eltavolitasa.
2. Frontend cleanup:
   - related_objects layer es checkbox kivezetese;
   - layer filter es label tisztitasa.
3. Backend related-by-documents endpoint:
   - schema;
   - service;
   - API endpoint;
   - celzott tesztek claim/event/entity/missing-item es unsupported esetekre.
4. Frontend Kapcsolodo objektumok panel:
   - kulon panel a felso graph sorban;
   - node-selection alapu aktiv/disabled allapot;
   - keresogomb;
   - talalati kartyak;
   - kijeloltek terkepre helyezese.
5. Verifikacio:
   - tests/test_relationship_graph.py celzott bovites;
   - npm --prefix frontend run build;
   - git diff --check.
