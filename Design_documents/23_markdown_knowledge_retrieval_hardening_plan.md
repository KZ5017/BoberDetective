# 23. Markdown tudasbazis retrieval hardening terv

## 1. Cel

Ez a dokumentum a `Tudasbazis` modul kovetkezo minosegi fejlesztesi
szeletet rogziti.

A Marko/AST alapu Markdown parser mar aktiv baseline. A kovetkezo cel nem a
parser altalanos tovabbtuningolasa, hanem annak javitasa, hogy semantic es
hybrid forraskereses eseten pontosan milyen chunkok kerulnek az LLM ele.

Rovid celmondat:

```text
A Tudasbazis RAG valaszminoseget a semantic/hybrid forraskivalasztas
Markdown-aware javitasaval noveljuk.
```

## 2. Mi a problema?

A RAG valasz minoseget elsosorban nem az hatarozza meg, hogy a modell
elvileg mire kepes, hanem hogy milyen forrasreszeket kap meg.

Ha a retrieval jo:

- a modell pontosabb valaszt ad,
- kevesebb hianyzo reszlet lesz,
- kevesebb irrelevans osszefugges jelenik meg,
- a forraskartyak emberileg is hasznosabbak.

Ha a retrieval rossz:

- a modell jo stilusban fog rossz vagy hianyos kontextusbol dolgozni,
- a felhasznalo nem azt latja, amit valojaban keresett,
- a `detailed` valasz sem lesz erdemben reszletesebb.

## 3. Kiindulo implementacio

Aktiv kodut:

```text
app/services/knowledge_query.py
```

Fontosabb fogalmak:

- `KnowledgeRetrievedChunk`
- `_keyword_knowledge_search`
- `_semantic_knowledge_search`
- `_merge_hybrid_hits`
- `_order_retrieved_chunks_for_llm`
- `_build_knowledge_source_blocks`
- `_build_used_sources`

### 3.1 Keyword mode

A keyword mode egyszeru, determinisztikus baseline:

- a query terms lista alapjan keres a chunk szovegeben,
- exact query match plusz pontot kap,
- talalatok score szerint csokkeno sorrendben jonnek,
- dontetlenben dokumentumnev/path es chunk index rendez.

Dontes:

```text
Keyword mode maradjon egyszeru baseline. Ezt ne bonyolitsuk tul ebben a
szeletben.
```

### 3.2 Semantic mode

A semantic mode jelenleg:

1. ellenorzi, hogy a kijelolt knowledge dokumentumok indexelve vannak-e,
2. a teljes felhasznaloi query-re embeddinget ker,
3. Qdrant knowledge indexben keres,
4. Qdrant score szerinti talalatokat ad vissza,
5. a talalatokbol `KnowledgeRetrievedChunk` lista keszul.

Ez jo alap, de:

- csak a nyers kerdes embeddingelt alakjat hasznalja,
- nem hasznal explicit Markdown strukturajelet,
- nem tudja, hogy heading/code/lista/tablas tartalom kulonosen fontos lehet.

### 3.3 Hybrid mode

A hybrid mode jelenleg:

1. lefuttat keyword keresest,
2. lefuttat semantic keresest,
3. azonos chunkokat deduplikal,
4. keyword score-t normalizal,
5. semantic score-t normalizal,
6. ha ugyanaz a chunk keyword es semantic talalat is, overlap bonuszt kap,
7. a vegso talalatlista score szerint rendezodik.

Ez jo elso forma, de Markdown tudasbazisnal meg nem eleg tudatos.

## 4. Alapelv

Retrieval javitasnal ket kulon dontest kell szetvalasztani:

1. **Mely chunkok legyenek kivalasztva?**
   - Ez relevancia/pontozas/reranking kerdes.

2. **Milyen sorrendben kapja meg oket az LLM?**
   - Ez kontextus-olvashatosagi kerdes.

Dontes:

```text
A retrieval valasszon relevancia szerint, de az LLM-nek adott SOURCE blokkok
maradjanak dokumentum / heading / chunk sorrendben.
```

Ez csokkenti annak eselyet, hogy ket egymas utan kovetkezo, osszetartozo
szovegresz szetszakadjon a promptban.

## 5. Nem cel

Ebben a szeletben nem cel:

- uj Markdown parser,
- Obsidian-specifikus wikilink/backlink/graf logika,
- attachment vagy kepfeldolgozas,
- keyword mode tulbonyolitasa,
- backend oldali query-varians vagy query-expansion a felhasznaloi kerdesbol,
- LLM-alapu reranker elso korben,
- kulso szolgaltatas vagy cloud dependency,
- a Tudásbázis osszekeverese ugyirat workflow-kkal.

## 6. Fejlesztesi sorrend

### 6.1 Elso lepes: jelenlegi retrieval audit es tesztbaseline

Eloszor pontosan korul kell venni a jelenlegi viselkedest.

Feladatok:

1. Unit tesztek a jelenlegi keyword / semantic / hybrid orderingra.
2. Tesztek arra, hogy hybrid mode hogyan kezeli:
   - csak keyword talalat,
   - csak semantic talalat,
   - keyword + semantic overlap talalat,
   - azonos score eseten stabil rendezest.
3. Teszt arra, hogy `_order_retrieved_chunks_for_llm` dokumentum / path /
   chunk sorrendbe rendezi az LLM bemenetet.
4. Debug/helper kimenet lehetosege fejlesztoi szinten:
   - chunk id,
   - document path,
   - heading path,
   - keyword score,
   - semantic score,
   - final score,
   - match type.

Elfogadas:

```text
Mielott scoringot modositunk, legyen teszttel rogzitve, mit csinal most.
```

Aktualis allapot:

```text
ELKESZULT.
```

Lefedett baseline esetek:

- semantic Qdrant hit -> `KnowledgeRetrievedChunk` lekepezes,
- jelenlegi hybrid keyword/semantic/overlap score viselkedes,
- stabil hybrid tie ordering dokumentum path es chunk index alapjan,
- LLM bemenet dokumentum/path/chunk sorrendje.

Kovetkezo lepes:

```text
Markdown-aware hybrid scoring bevezetese.
```

### 6.2 Masodik lepes: Markdown-aware hybrid scoring

A hybrid scoring hasznaljon olyan jeleket is, amelyek a Markdown tudasanyag
szerkezetebol jonnek.

Javasolt pontozasi komponensek:

#### Query/text jelek

- exact phrase evidence a chunk textben,
- query term overlap a chunk textben,
- technikai token overlap,
- code-szeru tokenek megjelenese:
  - `cmd`,
  - `net use`,
  - `bitsadmin`,
  - `certutil`,
  - `smb`,
  - parancsnevek,
  - fajlkiterjesztesek,
  - kapcsolok / flag-ek.

#### Markdown metadata jelek

- query term overlap a `heading_path` mezoben,
- exact phrase vagy reszegyezes headingben,
- `contains_code_block`,
- `code_languages`,
- lista/table/block metadata, ha mar elerheto vagy kesobb konnyen elerheto.

#### Retrieval jelek

- keyword score,
- semantic score,
- keyword + semantic overlap bonusz,
- exact phrase bonusz,
- heading match bonusz,
- code block bonusz csak akkor, ha a query technikai/parancs jellegu.

Fontos korlat:

```text
A code block jelenlete onmagaban ne toljon mindent el. Csak akkor kapjon
jelentos bonuszt, ha a query vagy a heading/code language is technikai
egyezest mutat.
```

Aktualis allapot:

```text
ELSO VALTOZAT ELKESZULT.
```

Implementalt jelek:

- exact query egyezes a chunk szovegeben,
- exact query egyezes a heading path-ban,
- query term overlap a heading path-ban,
- technikai token overlap a chunk szovegeben,
- technikai token overlap a heading path-ban,
- code language egyezes,
- code block bonusz csak akkor, ha van technikai query/text/heading/language
  egyezes.

Fontos:

```text
Keyword mode nem valtozott. Semantic mode onallo Qdrant talalatkivalasztasa
nem valtozott. A plusz pontozas csak a hybrid merge vegen ervenyesul.
```

Allapot:

```text
Elkeszult. A kovetkezo lepes mar a kornyezeti chunk bovites.
```

### 6.3 Harmadik lepes: opcionális szomszedos chunk bevonas

Markdown jegyzeteknel gyakori, hogy:

- egy chunk tartalmazza a parancsot,
- az elozo chunk tartalmazza a bevezetest,
- a kovetkezo chunk tartalmazza a kovetkeztetest.

Javaslat:

Ha egy chunk eros talalat, opcionálisan kerulhessen melle:

- az elozo chunk ugyanabbol a dokumentumbol,
- a kovetkezo chunk ugyanabbol a dokumentumbol,
- csak ha heading path azonos vagy kompatibilis,
- csak ha a `max_chunks` keretbe belefer,
- csak alacsonyabb vagy jelolt `match_type` ertekkel, peldaul:

```text
context_neighbor
```

Implementalt v1 viselkedes:

- csak `semantic` es `hybrid` keresésnel aktiv,
- `keyword` mod egyszeru baseline marad,
- a `max_chunks` tovabbra is kemeny plafon,
- a plafon kisebb, backend altal kontrollalt resze lehet kornyezeti chunk,
- csak kozvetlen elozo/kovetkezo chunk kerulhet be,
- csak ugyanabbol a dokumentumbol,
- csak azonos vagy kompatibilis heading path mellett,
- a kornyezeti chunk `retrieval_match_type=context_neighbor` jelolest kap,
- a vegso LLM bemenet tovabbra is dokumentum / path / chunk sorrendben stabil.

Korlatozas:

```text
Szomszedos chunk bevonas soha ne huzzon be masik dokumentumot.
```

Dontes:

```text
A kornyezeti chunkok kulon `context_neighbor` match type-pal latszanak.
```

### 6.4 Negyedik lepes: deterministic reranking

Reranking csak akkor kell, ha a fenti jelek utan is tul zajos a candidate set.

Elso korben ne LLM reranker legyen.

Javasolt deterministic reranker:

- bemenet: keyword/semantic/hybrid talalatokbol es opcionális kornyezeti
  chunkokbol osszeallitott deduplikalt candidate set,
- kimenet: max_chunks darab chunk,
- score komponensek:
  - semantic score,
  - keyword score,
  - heading score,
  - exact phrase score,
  - code/token score,
  - overlap score,
  - context-neighbor penalty vagy cap.

Minden komponens legyen tesztelheto.

## 7. Adatmodell/API hatas

Elso korben nem szukseges DB migracio.

Lehetseges API/schema bovites kesobb:

- `retrieval_match_type = context_neighbor`,
- `retrieval_metadata` bovites fejlesztoi/debug celra,
- source cardon kiegészito jelzes:
  - `Szemantikus`,
  - `Hybrid`,
  - `Kulcsszavas`,
  - `Környezeti szövegrész`.

Javaslat:

```text
Elso implementacios korben a belso pontozas javuljon, UI/debug bovites csak
akkor kelljen, ha a felhasznalo szamara ertelmezheto plusz informaciot ad.
```

## 8. Tesztterv

Minimum tesztek:

1. Hybrid score overlap bonusz megmarad.
2. Heading path egyezes bonuszt ad.
3. Code block bonusz csak technikai query mellett eros.
4. Exact phrase egyezes elorebb sorol.
5. Szomszedos chunk bevonas csak ugyanabban a dokumentumban tortenik.
6. Szomszedos chunk bevonas nem lepi tul a `max_chunks` limitet.
7. LLM bemenet sorrendje dokumentum / heading / chunk szerint stabil.
8. Keyword mode viselkedese nem valtozik varatlanul.
9. Empty/no-index source viselkedes nem romlik.

Javasolt tesztfajl:

```text
tests/test_knowledge_query.py
```

Ha a scoring logika nagyobb lesz, erdemes lehet kiszervezni:

```text
app/services/knowledge_retrieval.py
tests/test_knowledge_retrieval.py
```

## 9. Implementacios javaslat

### 9.1 Kodszetvalasztas

Ha a retrieval logika tovabb no, ne hagyjuk tul nagyra noni a
`knowledge_query.py` fajlt.

Javasolt uj modul:

```text
app/services/knowledge_retrieval.py
```

Ide kerulhet:

- query term extraction,
- score komponensek,
- hybrid merge,
- context neighbor expansion,
- final candidate sorting.

`knowledge_query.py` maradhat a magas szintu query orchestration:

- dokumentumok kivalasztasa,
- retrieval meghivasa,
- LLM prompt epites,
- valasz parser,
- response osszerakas.

### 9.2 Lepesenkenti merge

Ne egy nagy atiras legyen.

Javasolt sorrend commitokon belul is:

1. Baseline tesztek a jelenlegi viselkedesre.
2. Kiszervezes vagy belso helper tisztitas viselkedesvaltozas nelkul.
3. Markdown-aware scoring.
4. Context neighbor expansion.
5. Csak ha kell: deterministic reranker.

## 10. Elfogadasi kriterium

A szelet akkor tekintheto kesznek, ha:

- a jelenlegi semantic/hybrid retrieval viselkedes tesztekkel fedett,
- hybrid scoring hasznal Markdown-aware jeleket,
- opcionális context neighbor expansion nem kever dokumentumokat,
- LLM bemenet sorrendje tovabbra is dokumentum / heading / chunk szerint stabil,
- a `Tudásbázis` live valaszok legalabb nem romlanak, es konkret tesztkerdeseken
  jobb forraskartyakat adnak,
- frontend build es backend tesztek zolden futnak.

## 11. Dontesek es nyitott kerdesek

Eldontve:

1. Nem kell user-facing kapcsolo a context neighbor expansionre.
   - Backend kontrollalt minosegi reteg.
2. A context neighbor forrasok kulon `context_neighbor` match type-pal
   latszanak.
3. A kornyezeti chunkok a `max_chunks` plafonon belul maradnak.
   - V1-ben a plafon kb. 25%-a lehet kornyezeti chunk.
   - Kis plafonnal nincs kornyezeti bovites.

Nyitott:

1. Hasznaljunk-e deterministic rerankinget?
   - Elso javaslat: csak akkor, ha a live tesztek szerint a mostani scoring +
     context-neighbor bovites meg mindig tul zajos forraskartyakat ad.
2. Hasznaljunk-e LLM-et query rewritingra vagy rerankingre?
   - Elso javaslat: nem, csak kesobb, ha determinisztikus jelek kevesek.

## 12. Kovetkezo konkret lepes

Allapot:

```text
Ez a hardening szelet elso kore implementalva van.
```

Megvalosult:

- baseline retrieval tesztek,
- Markdown-aware hybrid scoring,
- context-neighbor expansion,
- heading relevance scoring,
- section expansion v1,
- dokumentumszintu source packing v1.

A kovetkezo konkret lepes:

```text
Live validacio nagyobb Markdown tudásbázison, majd konkret rossz talalati
peldak alapjan score/packing finomhangolas.
```

Indok:

- a section-aware packing backend alapja mar elkeszult,
- a kovetkezo donteseket mar nem elmeleti tervbol, hanem live talalati
  mintakbol erdemes meghozni,
- deterministic reranking csak akkor indokolt, ha a source packing utan is
  tul zajos marad a forrasvalasztas.

Deterministic reranking csak kesobbi opcio, ha a section-aware packing utan is
tul zajos marad a forrasvalasztas.

## 13. Kivezetett otlet: query variansok

Felmerult, hogy a backend a felhasznaloi kerdesbol tobb keresesi valtozatot
kepezzen, peldaul technikai kulcsszavakat vagy domain-szotar alapjan bovitett
queryket.

Dontes:

```text
Ezt a Tudasbazis retrieval hardening v1-ben nem vezetjuk be.
```

Indok:

- magyar nyelvu kerdeseknel konnyen kaotikus vagy tul szeles candidate setet
  okozhat,
- a backend ne okoskodja tul a felhasznaloi kerdes szandekat,
- plusz szamitas es plusz zaj lehet, mikozben a nyereseg bizonytalan,
- a jelenlegi iranyban a felhasznaloi query marad a keresesi alap, es a
  minoseget a Markdown-aware scoring, majd a kornyezeti chunk bevonas javitja.
