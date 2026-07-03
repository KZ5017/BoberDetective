# 34. Kapcsolati terkep canvas objektumkijeloles es eltavolitas terv

## 1. Cel

A Kapcsolati terkep hasznalhatosagi hianya, hogy objektumokat konnyu feltenni a terkepre, de a mar kirajzolt objektumokat gyorsan levenni korulmenyes.

Korabbi UX:

- a user ranez a grafra;
- latja, hogy egy vagy tobb objektum nem kell;
- visszakeresi oket a Megjelenitendo objektum listaban;
- kiveszi a checkboxot;
- ujratolti a terkepet.

Ez 1-2 objektumnal elfogadhato, de 10+ objektumnal lassu es faraszto.

Cel:

- a canvas-on kattintassal lehessen egy vagy tobb szakmai objektum node-ot kijelolni;
- a kijelolt objektumok egy gombbal levehetok legyenek a terkep fokuszlistajarol;
- kontextus/provenance node-ok ne legyenek eltavolithatok ebbol a funkciobol;
- a megoldas ne toroljon szakmai adatot es ne bontsa meg a backend graph truth modellt;
- az inspector panelek mukodese maradjon egyertelmu.

## 2. Fogalmi szetvalasztas

Harom allapotot kulon kell kezelni.

### 2.1 Aktualisan vizsgalt csomopont

Ez a selectedRelationshipNodeId.

Szerepe:

- a Kijelolt csomopont tartalma panel ezt mutatja;
- a Kapcsolatok panel ennek a kapcsolatait mutatja;
- a Kapcsolodo objektumok panel ebbol indit kapcsolodo-objektum keresest.

Ez tovabbra is egyetlen csomopont.

### 2.2 Csoportos canvas kijeloles

Frontend-only allapot:

relationshipBulkSelectedNodeIds: string array

Szerepe:

- csak canvas-muveletekhez hasznaljuk;
- csak fokuszobjektum node-ok kerulhetnek bele;
- nem valtoztatja meg az inspector panelek tartalmat tobbes panelle;
- nem indit automatikusan backend lekerdezest;
- nem azonos a Megjelenitendo objektum lista checkbox allapotaval, de eltavolitas utan ahhoz szinkronizalodik.

### 2.3 Fokuszobjektumok

Ez a relationshipGraphFocusKeys es relationshipGraph.focus_objects vilaga.

Szerepe:

- ezek azok a szakmai objektumok, amelyek alapjan a backend grafot epit;
- ezek levetele valodi graf-fokusz valtozas;
- levetel utan uj backend graph load szukseges.

## 3. Node-tipusonkenti viselkedes

### 3.1 Eltavolithato node-ok

Csak azok a szakmai objektum node-ok eltavolithatok, amelyek az aktualis fokuszobjektum-listaban is szerepelnek.

Ide tartozhatnak:

- claim;
- event;
- entity;
- missing_item_candidate;
- contradiction_candidate.

Ha ilyen node kerul eltavolitasra:

- ki kell venni a fokuszobjektum-listabol;
- a grafot ujra kell tolteni a megmaradt fokuszobjektumokkal;
- ha nem marad fokuszobjektum, a terkep kiurul.

Ez nem adat- vagy objektumtorles, csak az aktualis terkep fokuszanak modositasa.

### 3.2 Nem eltavolithato node-ok

Ide tartoznak a kontextus/provenance node-ok:

- irat;
- oldal;
- szovegresz;
- forrashivatkozas.

Ezek nem onalloan kerulnek fel a terkepre, hanem a backend altal visszaadott graf kovetkezmenyei.

A live UX-proba alapjan ezek ideiglenes elrejtese vizualis katyvaszt okozott, ezert az elso stabil verzio tudatosan nem tamogatja a kontextus node-ok eltavolitasat vagy elrejteset.

Kovetkezmeny:

- normal modban kattinthatoak maradnak inspector celbol;
- csoportos kijeloles modban rajuk kattintva nem tortenik bulk-kijeloles;
- ha csak ilyen node van aktualisan kijelolve, az Eltavolitas gomb inaktiv.

## 4. UI viselkedes

A Kapcsolati terkep panel retegvalaszto soraban ket canvas-muveleti control szerepel:

- Csoportos kijeloles;
- Eltavolitas.

### 4.1 Csoportos kijeloles

Toggle jellegu gomb.

Inaktiv allapot:

- a canvas kattintas a jelenlegi modon mukodik;
- barmely node kattintasa beallitja a selectedRelationshipNodeId erteket;
- az inspector panelek frissulnek.

Aktiv allapot:

- csak eltavolithato fokuszobjektum node kattintasa adja hozza vagy veszi ki a node id-t a relationshipBulkSelectedNodeIds listabol;
- kontextus/provenance node kattintas nem kerul bulk-kijelolesbe;
- az utoljara kattintott eltavolithato node tovabbra is lehet selectedRelationshipNodeId, hogy az inspector panelek hasznalhatok maradjanak;
- edge kattintas tovabbra is a normal edge-inspector viselkedest koveti.

### 4.2 Eltavolitas

A gomb akkor aktiv, ha:

- csoportos kijelolesben legalabb egy eltavolithato fokuszobjektum node ki van jelolve; vagy
- normal modban az aktualis selectedRelationshipNodeId eltavolithato fokuszobjektum node.

Mukodes:

- ha van csoportos kijeloles, azon dolgozik;
- ha nincs csoportos kijeloles, az aktualis selectedRelationshipNodeId node-on dolgozik;
- csak fokuszobjektumokat vesz le a terkep fokuszlistajarol;
- nem torol adatot az adatbazisbol.

## 5. Eltavolitasi algoritmus

Input:

candidateNodeIds = relationshipBulkSelectedNodeIds vagy selectedRelationshipNodeId

Lepesek:

1. Kivalasztjuk a node-okat az aktualis lathato grafbol.
2. Csak azokat tartjuk meg, amelyek relationshipFocusFromGraphNode alapjan szakmai objektumok, es szerepelnek az aktualis fokuszlistaban.
3. A talalt object_type + object_id kulcsokat kivesszuk a fokuszlistabol.
4. Toroljuk a csoportos kijelolest.
5. Toroljuk az aktualisan kijelolt edge-et.
6. Ha az aktualisan vizsgalt node is lekerult, selectedRelationshipNodeId legyen null.
7. Ha maradt fokuszobjektum, ujra betoltjuk a grafot a megmaradt fokuszokkal.
8. Ha nem maradt fokuszobjektum, a terkep kiurul.
9. A UI visszajelzi, hany objektum kerult le a terkepbol.

## 6. Graf szures frontend oldalon

A frontend graf szures tovabbra is csak a retegkapcsolokbol dolgozik:

- Irat;
- Oldal;
- Szovegresz;
- Forrashivatkozas;
- Ellentmondasok.

Nincs hidden-node graf projection az elso stabil canvas-eltavolitas verziohoz.

Indok:

- a kontextusnode elrejtes vizualisan nem adott eleg tiszta eredmenyt;
- a provenance-lanc teljessege fontosabb, mint az egyedi kontextusnode levetel;
- objektum-level fokuszcsokkentes tisztabb UX es tisztabb kodmodell.

## 7. Inspector panelek viselkedese

Az inspector panelek nem valnak tobbes kijelolesu panelle.

Ezert:

- selectedRelationshipNodeId marad egyetlen node;
- relationshipBulkSelectedNodeIds csak canvas muveleti kijeloles;
- csoportos kijeloles modban az utoljara kattintott eltavolithato objektum lehet az inspector alapja;
- a Kapcsolodo objektumok panel tovabbra is csak az aktualisan vizsgalt szakmai node-bol indit keresest.

## 8. Vizualis jeloles

A bulk-selected objektum node kulon vizualis jelolest kap.

Szabaly:

- a normal inspector-selected node maradjon minimalis;
- a bulk-selected node kapjon finom, de lathato outline-t;
- az outline a meglevo aranybarna kijelolesi tokenbol dolgozik: color-warning-border;
- a bulk-selected node a meglevo aranybarna kijelolesi hatteret is megkapja: color-warning-bg; ez az aktualisan inspector-selected node-on is ervenyesul, ha kozben bulk-selected is.

CSS osztaly:

graph-flow-node-bulk-selected

## 9. Backend erintes

Ehhez a verziohoz nem szukseges backend modositas.

Indok:

- fokuszobjektum levetel a mar meglevo multi-focus graph POST ujrahivasaval megoldhato;
- nem keletkezik uj adat, audit esemeny vagy perzisztens layout;
- a muvelet nem szakmai objektumtorles, csak terkep-fokusz modositas.

## 10. Tudatosan nem resze ennek a verzionak

- kontextus/provenance node-ok elrejtese;
- edge-ek csoportos kijelolese;
- kijelolesi teglalap vagy drag select;
- billentyuparancsok;
- elrejtes perzisztalasa;
- layout mentese;
- audit esemeny a canvas muveletekrol;
- backend oldali hidden-node graph projection.

## 11. Implementacios allapot

Megvalositva:

- a Kapcsolati terkep canvas kapott csoportos kijeloles modot;
- a csoportos kijeloles frontend-only node-id listaban el;
- normal kattintas tovabbra is az egyetlen inspector-selected csomopontot kezeli;
- csoportos modban csak fokuszobjektum node kerulhet a bulk-kijelolesbe;
- az Eltavolitas gomb csak fokuszobjektum node eseten aktiv;
- az Eltavolitas gomb kiveszi az objektumot a fokuszlistabol es ujratolti a grafot;
- kontextus/provenance node elrejtes nincs a kodban;
- a bulk-kijeloles finom aranybarna outline jelolest es aranybarna hatteret kap, a selected + bulk-selected kombinalt allapotban is.

Ellenorzes:

- frontend build: npm --prefix frontend run build sikeres.

Hatokor:

- backend modositas nem tortent;
- adatbazis vagy API contract nem valtozott;
- a muvelet nem torol szakmai adatot, csak a terkep aktualis fokuszlistajat modositja.

## 12. Elfogadasi kriteriumok

A szelet kesznek tekintheto, ha:

- egyetlen fokuszobjektum node leveheto a canvasrol;
- csoportos kijeloles modban tobb fokuszobjektum node kijelolheto kattintassal;
- kontextus/provenance node-ok nem kerulnek bulk-kijelolesbe;
- kontextus/provenance node kijelolese mellett az Eltavolitas gomb inaktiv;
- fokuszobjektum levetele utan a graf ujratoltodik a megmaradt fokuszokkal;
- ha minden fokuszobjektum lekerul, a terkep kiurul;
- az inspector panelek tovabbra is egyetlen aktualis node vagy edge adatait mutatjak;
- a Kapcsolodo objektumok panel nem indul el tobbes kijelolesbol, csak az aktualisan vizsgalt szakmai node-bol.
