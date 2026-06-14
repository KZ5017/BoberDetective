# 28. Kapcsolati terkep vizszintes layout terv

## Cel

Ez a dokumentum a `Kapcsolati terkep` jelenlegi technikailag kesz
multi-focus baseline-jara epul.

A cel nem uj backend kapcsolatmodell, nem uj igazsagreteg es nem grafadatbazis.

A cel:

```text
A jelenlegi node/edge projection vizualisan ertelmezhetobb, determinisztikus,
vizszintes retegekbe rendezett megjelenitese.
```

Kiindulo problema:

- a React Flow / XYFlow canvas mar mukodik;
- a node-ok es edge-ek kattinthatok, szurhetok, inspectalhatok;
- tobb fokuszobjektum is megjelenitheto;
- viszont a jelenlegi rajzolas vizualisan meg konnyen "szetszort halonak"
  tunhet;
- a vonalak keresztezodhetnek, es a usernek fejben kell osszeraknia, hogy mi
  forras, mi objektum, mi kapcsolat es mi provenance.

## Alapelv

A graf megjelenitese kovesse a rendszer szakmai logikajat:

```text
Irat -> Oldal -> Szovegresz -> Forrashivatkozas -> Strukturalt objektum -> Kapcsolodo objektum
```

Ez a rendszer lenyegevel osszhangban van:

- az eredeti dokumentum es szovegresz a bizonyiteki alap;
- a forrashivatkozas konkret idezet/szovegkapcsolat;
- a strukturalt objektum ember altal ellenorizheto munkadarab;
- a kapcsolodo objektumok es ellentmondasjeloltek az objektumok kozotti
  osszefuggeseket mutatjak.

Fontos backend dontes:

- a dokumentum/page/chunk/source_reference sorrend ne frontend-only trukk legyen;
- a backend graph projection adja vissza a source-location lancot;
- a frontend layout ezt a backend projectiont rendezze vizszintes retegekbe.

## Nem-cel

Ebben a vizualis erositesi korben tovabbra sem cel:

- uj node vagy edge letrehozasa backend oldalon;
- AI altal generalt kapcsolat;
- force-layout alapu, veletlenszeru hatasu halozat;
- szerkesztheto graf;
- layout mentes;
- teljes ugy graf;
- edge-szurok;
- audit vagy human review node-ok bevezetese.

Ezek kesobbi bovitesi pontok lehetnek, de a kovetkezo lepesben a mar letezo
adatokat kell jobban elrendezni.

## Layout dontes

Az elso vizualis erositesi irany:

```text
Vizszintes, determinisztikus reteges layout.
```

Javasolt alapretegek balrol jobbra:

```text
[Irat]
        ->
[Oldal]
        ->
[Szovegresz]
        ->
[Forrashivatkozas]
        ->
[Fokuszobjektum(ok)]
        ->
[Kapcsolodo objektumok / ellentmondasok]
```

Az objektumkozpontu terkep tudatosan nem tartalmaz kulon `Elemzesi eredet`
reteget. Az analysis run es kutatasi talalat eletut/provenance informacio
tovabbra is fontos, de azt az elemzesi/audit feluletek vagy egy kesobbi,
kulon eletut/provenance terkep kezelje, ne ez a kapcsolati nezeti terkep.

## Retegek javasolt szerepe

### 1. Forrasoldali reteg

Ide kerulhet:

- `document`
- `page`
- `chunk`

Feladata:

- megmutatni, melyik iratbol, oldalrol, szovegreszbol ered a kapcsolat;
- halvanyabb, bizonyiteki/context jellegu vizualis szerepet kapni;
- nem dominálni a fokuszobjektumhoz kepest.

Elrendezesi otlet:

- azonos dokumentumhoz tartozo oldalak/chunkok egymas utan, hierarchikus
  olvasasi sorrendben;
- ha csak chunk lathato alapertelmezetten, akkor a dokumentum/page reteg a
  jelenlegi layer toggle szerint opcionalis maradhat;
- kesobb lehet vizualis csoportositas dokumentum szerint, de elso korben nem
  kotelezo.

Aktualis cel:

```text
document -> page -> chunk -> source_reference
```

Fallback:

- page nelkul: `document -> chunk -> source_reference`;
- chunk nelkul: `document -> page -> source_reference`;
- csak dokumentummal: `document -> source_reference`.

### 2. Forrashivatkozas reteg

Ide kerul:

- `source_reference`

Feladata:

- atmeneti hidat kepezni a forrasoldali szovegresz es a strukturalt objektum
  kozott;
- lathatova tenni, hogy az objektum nem kozvetlenul "a dokumentumbol" lebeg
  elo, hanem konkret valid forrashivatkozason at.

Elrendezesi otlet:

- a hozza tartozo chunk es objektum koze keruljon;
- ha tobb objektum osztozik egy forrashivatkozason, a source_reference node
  legyen kozos koztes pont;
- tobb kozos forras eseten ezek rendezodjenek egymas ala.

### 3. Fokuszobjektum reteg

Ide kerulnek:

- a kijelolt fokuszobjektumok:
  - `claim`
  - `event`
  - `entity`
  - `missing_item_candidate`
  - `contradiction_candidate`

Feladata:

- a terkep vizualis kozepe;
- a user altal valasztott vizsgalati pontok kiemelese;
- tobb fokuszobjektum eseten stabil, egymas alatti vagy enyhen csoportositott
  megjelenites.

Elrendezesi otlet:

- a fokuszobjektumok legyenek kozepre zarva;
- erossebb keret/suly, de ne harsany szin;
- ha egy fokuszobjektum source_reference-en keresztul kapcsolodik a forrashoz,
  a vonal balrol jobbra haladjon;
- ha tobb fokuszobjektum ugyanazon forrashoz kapcsolodik, a kozos forras legyen
  bal oldalon kozosan lathato, ne duplikalva.

### 4. Kapcsolodo objektum / ellentmondas reteg

Ide kerulhet:

- nem fokusz `claim`
- nem fokusz `event`
- nem fokusz `entity`
- nem fokusz `missing_item_candidate`
- nem fokusz `contradiction_candidate`

Feladata:

- megmutatni, milyen mas strukturalt objektumok kapcsolodnak a fokuszhoz;
- lathatova tenni a kozos forrasbol, ellentmondasjeloltbol vagy egyeb
  levezetheto relaciobol fakado kapcsolatokat.

Elrendezesi otlet:

- a fokuszobjektumok jobb oldalara keruljenek;
- kevesbe dominans vizualis sulyt kapjanak, mint a fokusz;
- ellentmondasjeloltek kaphatnak finoman figyelmezteto stilust;
- ha a node retegkapcsoloval ki van kapcsolva, az edge is tunjon el, ha egyik
  vegpontja nem lathato.

### 5. Provenance / elemzesi eredet reteg

Ide kerulhet:

- `research_finding`
- `analysis_run`

Feladata:

- audit/provenance kontextus adasa;
- megmutatni, hogy egy objektum kutatasi talalatbol vagy elemzesi futasbol
  szarmazik.

Elrendezesi otlet:

- ne keveredjen a fo forras -> objektum -> kapcsolat tengelybe;
- inkabb felso vagy also sav;
- opcionális layer toggle maradjon;
- vizualisan legyen kisebb, technikai/provenance jellegu.

## Node tipusu vizualis szerepek

Elso vizualis erositesnel a node-ok ne csak pozicioban, hanem szerepben is
kulonbozzenek.

Javaslat:

- fokuszobjektum:
  - legerosebb keret;
  - kozepes/nagyobb node;
  - stabil kiemeles;
- kapcsolodo objektum:
  - hasonlo forma, de gyengebb vizualis suly;
- source_reference:
  - hid/kapocs jellegu node;
  - kompaktabb meret;
- chunk:
  - forrasoldali szoveghely;
  - halvanyabb, de olvashato;
- document/page:
  - kontextus node;
  - kevesbe dominans;
- contradiction_candidate:
  - objektumszeru stilus;
  - az objektum retegtol jobbra jelenik meg, mert ket allitasbol/objektumbol
    epulo ellenorzesi jelolt;
- analysis_run/research_finding:
  - technikai/provenance stilus.

Fontos:

- ne vezessunk be teljesen uj, egyedi szinrendszert;
- a meglévo CSS tokenrendszerbol induljunk ki;
- a szin csak masodlagos jel legyen, a pozicio es forma legyen az elso.

## Edge elrendezesi alapelvek

A cel a keresztezodesek csokkentese.

Elso korben eleg:

- balrol jobbra halado edge-irany;
- azonos retegek kozotti edge-ek kerulese, ahol lehet;
- node-ok retegen beluli rendezese kapcsolati kozeliseg szerint;
- kozos source_reference vagy chunk node-ok kozos koztes pontkent hasznalata;
- csak olyan edge jelenjen meg, amelynek mindket vegpontja lathato.

Nem cel elso korben:

- automatikus edge bundling;
- virtualis osszevont edge-ek;
- dinamikus legrövidebb utvonal kirajzolasa;
- interaktiv edge-szurok.

### Vizualis athidalo edge-ek

Egy celzott kivetel megengedett: ha a user kikapcsolja a
`Forráshivatkozás` reteget, de bekapcsolva hagyja az `Irat`, `Oldal` vagy
`Szövegrész` reteget, akkor a frontend rajzolhat csak vizualis athidalo edge-et.

Pelda:

```text
Irat / oldal -> Objektum
```

vagy:

```text
Szovegresz -> Objektum
```

Ez akkor hasznos, ha a user az irat vagy szovegresz es az objektum kapcsolatara
kivancsi, de a konkret `source_reference` node zajos lenne.

Fontos szabalyok:

- ez csak frontend renderelesi segedvonal;
- nem backend edge;
- nem kerul adatbazisba;
- nem jelent uj szakmai allitast;
- `metadata.visual_only = true` jelleggel legyen megkulonboztetve;
- label nelkuli, halvanyabb/szaggatott vonal legyen;
- ne legyen osszekeverheto a valodi backend projection edge-ekkel.

## Retegeken beluli rendezesi javaslat

A determinisztikus layout miatt ugyanaz a graf hasonlo rajzot adjon.

Retegeken beluli sort javaslat:

1. fokuszobjektumok:
   - kijeloles sorrendje;
   - majd objektumtipus;
   - majd title/label;

2. source_reference node-ok:
   - a kapcsolodo fokuszobjektum sorrendje;
   - majd dokumentum;
   - majd oldal/chunk;

3. document/page/chunk:
   - dokumentumnev;
   - oldal;
   - chunk index;

4. kapcsolodo objektumok:
   - kapcsolodo fokuszobjektum sorrendje;
   - kapcsolat tipusa;
   - objektumtipus;
   - title/label;

5. Eletut/provenance node-ok:
   - ebben az objektumkozpontu terkepben nem jelennek meg;
   - ha kesobb szukseg lesz rajuk, kulon lifecycle/provenance terkepben kell
     rendezni oket.

## Multi-focus viselkedes

Tobb fokuszobjektum eseten a layout ne robbanjon szet.

Elso szabaly:

```text
Minden fokuszobjektum a kozepso retegben marad.
```

Kozos forrasok:

- ha tobb fokuszobjektum ugyanazon source_reference/chunk/document alapu,
  a kozos node egyszer jelenjen meg;
- ez a kozos node bal oldalon helyezkedjen el;
- a tobb fokuszobjektumhoz meno vonalak onnan induljanak.

Kozos kapcsolodo objektumok:

- ha egy kapcsolodo objektum tobb fokuszhoz is kotodik, egyszer jelenjen meg;
- jobb oldalon, a kapcsolodo retegben;
- tobb edge mutathat ra.

Limit:

- a 20 fokuszobjektumos limit maradjon;
- ha a graf tul suru, elso korben a layer toggle es node/edge cap legyen a
  vedekezes, ne uj backend logika.

## React Flow / XYFlow megvalositasi irany

A jelenlegi React Flow canvas megtarthato.

Elso implementacios cel:

- sajat determinisztikus layout fuggveny a frontendben;
- node type -> layer mapping;
- layer index -> x koordinata;
- retegen beluli sorrend -> y koordinata;
- stabil node meretek / min width / max width;
- canvas `fitView` maradhat.

Javasolt frontend helper:

```text
layoutRelationshipGraphHorizontally(graph, visibleLayerState)
```

Feladata:

- a mar szurt, lathato node/edge listat kapja;
- retegbe sorolja a node-okat;
- stabil poziciot ad nekik;
- visszaadja a React Flow node listat poziciokkal.

Elso korben nem kell kulon layout library.

Indok:

- a domain layout egyszeru es determinisztikus;
- nem kell force simulation;
- kevesebb kulso fuggoseg;
- jobban illeszkedik az audit/workbench szemlelethez.

Kesobb, ha szukseges:

- Dagre / ElkJS tipusu automatikus layer layout megfontolhato;
- de csak akkor, ha a sajat egyszeru retegezett layout mar nem eleg.

## Elfogadasi kriteriumok

Az elso vizszintes layout akkor tekintheto sikeresnek, ha:

- a forrasoldali node-ok bal oldalon vannak;
- a fokuszobjektumok kozepen vannak;
- a kapcsolodo objektumok jobb oldalon vannak;
- nincs kulon provenance sav, hogy a fo olvasasi irany tiszta maradjon;
- ugyanaz a graf ujratoltes utan stabilan hasonlo elrendezest kap;
- a vonalkeresztezodesek erezhetoen csokkennek;
- a node-ok szovege nem fut ki a dobozokbol;
- a layer toggles tovabbra is mukodnek;
- node/edge kattintas tovabbra is frissiti az inspektor paneleket;
- a multi-focus eset nem esik szet vizualisan 2-5 fokuszobjektumnal;
- nagyobb, 10-20 fokuszobjektumos grafnal legalabb nem torik a UI, meg ha
  vizualisan mar zsufolt is lehet.

## Javasolt implementacios sorrend

1. Frontend layout helper megirasa:
   - node type -> layer;
   - stabil layer order;
   - x/y koordinatak.

2. Node vizualis szerepek finomitasa:
   - fokusz;
   - forras;
   - source_reference;
   - kapcsolodo objektum;
   - provenance.

3. Edge stilus finomitasa:
   - balrol jobbra irany;
   - edge tipus szerint visszafogott stilus;
   - ne harsany, de lathato kapcsolat.

4. Layer toggle kompatibilitas ellenorzese:
   - csak lathato node-ok kozotti edge-ek;
   - default mag tovabbra is ertelmes.

5. Live UI teszt:
   - 1 fokuszobjektum;
   - 2-5 fokuszobjektum;
   - kozos forrassal rendelkezo objektumok;
   - contradiction candidate.

6. Dokumentacios frissites a tapasztalatok alapjan.

## Kovetkezo kozvetlen lepes

A kovetkezo fejlesztesi lepes lehet:

```text
Kapcsolati terkep frontend determinisztikus vizszintes layout helper
bevezetese a jelenlegi multi-focus graph adatokra.
```

Ezt backend schema modositas nelkul erdemes elkezdeni.

## Implementacios allapot

### 2026-06-13 - elso frontend layout helper

Elkeszult az elso frontend-only vizszintes layout helper a meglévő
`RelationshipFlowCanvas` komponensben.

Megvalosult:

- multi-focus kompatibilis fokuszfelismeres `focus_node_ids` alapjan;
- node type -> layout layer mapping:
  - `document` / `page` / `chunk` -> source layer;
  - `source_reference` -> source reference layer;
  - fokuszobjektumok -> focus layer;
  - minden mas strukturalt objektum -> related layer;
- balrol jobbra stabil, szellos x poziciok:
  - dokumentum: `0`;
  - oldal: `340`;
  - szovegresz: `680`;
  - forrashivatkozas: `1040`;
  - objektum: `1440`;
  - ellentmondasjelolt: `1840`;
  - provenance kulon also savban az objektum reteggel egy x-pozicion;
- retegen beluli determinisztikus rendezes:
  - fokusz sorrend;
  - dokumentum/page/chunk metaadat, ha elerheto;
  - kapcsolati fok;
  - tipus;
  - label;
  - id;
- React Flow node-ok balrol jobbra iranyitott source/target poziciot kapnak;
- CSS oldalon a node-ok alap border/effect kezelese szandekosan egységes
  maradt. A jelenlegi elfogadott vizualis kulonbseg csak az objektum jellegu
  node-ok finom hatterszinezese kategoriankent (`claim`, `event`, `entity`,
  `missing_item_candidate`, `contradiction_candidate`). A kijelolt/fokusz node
  allapot nem ad extra hatteret, keretet vagy arnyekot; a kattintas csak az
  inspektor panelek tartalmat valtoztatja.
- a valo source-chain edge-ek solid vonalak;
- ha a `Forráshivatkozás` reteg ki van kapcsolva, de az irat/oldal vagy
  szovegresz reteg lathato, a frontend label nelkuli, szaggatott
  `VISUAL_SOURCE_BRIDGE` edge-et rajzol a forrasoldali node es a fokuszobjektum
  koze. Ez csak vizualis athidalas, nem backend kapcsolat.
- `VISUAL_SOURCE_BRIDGE` edge nem rajzolodik ki, ha ugyanazon ket lathato node
  kozott mar van valo edge, akar ellenkezo iranyban is.

Nem valtozott:

- backend graph schema;
- backend edge/node projection;
- layer toggle logika;
- node/edge kattintas es inspektor panelek;
- multi-focus POST API.

Verifikacio:

- `npm --prefix frontend run build` sikeres.

### Inspector es node-stilus finomitas

A live UI csiszolas soran a `Kapcsolati térkép` inspektor panelei read-only
reszletnezeti szerepet kaptak:

- a `Kijelölt csomópont tartalma` es `Kapcsolatok` kartyai nem kapnak
  selected/focus hatter-, border- vagy arnyekeffektet;
- a kartyak es a kapszulak graph-inspector CSS tokeneken keresztul kovetik a
  globalis compact card/chip vizualis nyelvet;
- a canvas node-oknal kikerultek a nem hasznalt layer/focus classok;
- megmaradtak az objektumtipus classok, mert ezek adjak a celzott, kategoriankenti
  objektum-hatterszint;
- a graph node-ok selected/focus allapota nem modositja a node doboz kinezetet.

### Backend projection tisztitas allapota

A frontend helper utan kiderult, hogy a source-location node-ok backend oldalon
meg csillagszeruen kapcsolodtak a `source_reference` node-hoz.

Ez a cleanup implementalva lett. A backend graph projection jelenlegi celzott
forrashely-lanca:

```text
document -> page -> chunk -> source_reference -> object
```

Ez backend projection szinten tortenik, nem frontend-only vizualis trukkel.
A frontend ezutan a backend altal adott, szakmailag tiszta lancot rendezi el.

Fallbackok:

- page nelkul: `document -> chunk -> source_reference -> object`;
- chunk nelkul: `document -> page -> source_reference -> object`;
- csak dokumentummal: `document -> source_reference -> object`.

Az `Elemzési eredet` node-ok kivezetese megtortent ebbol az objektumkozpontu
terkepbol. Ha kesobb szukseg lesz rajuk, azt kulon eletut/provenance terkepben
kell ujratervezni.
