# 24. Markdown section-aware retrieval packing terv

## 1. Cel

Ez a dokumentum a `Tudasbazis` retrieval kovetkezo minosegi szintjet
rogziti.

A jelenlegi allapot:

- Marko/AST alapu Markdown chunking aktiv,
- semantic/hybrid retrieval mukodik,
- Markdown-aware hybrid scoring elso valtozata mukodik,
- context-neighbor expansion mukodik,
- query-varians / query-expansion tudatosan kivezetve.

A kovetkezo cel nem az, hogy a backend uj kerdeseket talaljon ki a user
kerdesebol, hanem az, hogy a mar megtalalt Markdown szerkezeti jeleket jobban
kihasznalja.

Rovid celmondat:

```text
A Tudasbazis ne csak top chunkokat valasszon, hanem dokumentum- es
section-szintu relevans kontextuscsomagokat allitson ossze.
```

## 2. Kiindulo problema

Markdown jegyzeteknel gyakori, hogy egy talalat nem onmagaban hasznos.

Pelda:

```text
QUERY:
mit tudsz a kubernetes pentesting-rol?

Talalat:
1. Mi az a Kubernetes?
6. Mi az a kubectl?
3. Alapfogalmak > Cluster
```

Ezek jo kapuk a temahoz, de ha a chunk csak headinget vagy rovid bevezetest
tartalmaz, akkor az LLM nem kapja meg az alatta levo erdemi anyagot.

Ez azt eredmenyezi, hogy:

- a retrieval latszolag jo talalatokat mutat,
- a forraskartyak megsem tartalmazzak a lenyeget,
- a modell hianyos kontextusbol valaszol,
- a `detailed` valasz sem tud igazan reszletes lenni.

## 3. Alapelv

A Markdown heading nem csak szoveg, hanem strukturajel.

Ezert a headinget ket celra kell hasznalni:

1. Score jel:
   - a heading egyezese novelheti a chunk relevanciajat.
2. Expansion boundary:
   - a heading kijelolheti, milyen tovabbi chunkok tartoznak ugyanahhoz a
     logikai szakaszhoz.

Dontes:

```text
A retrieval seed chunkokat talal, a section-aware packing pedig ezekbol
dokumentumon es szekcion beluli kontextuscsomagokat epit.
```

## 4. Nem cel

Ebben a szeletben nem cel:

- backend oldali query-varians vagy query-expansion,
- LLM-alapu query rewriting,
- LLM-alapu reranking elso korben,
- keyword mode tulbonyolitasa,
- Obsidian-specifikus wikilink/backlink/graf feldolgozas,
- teljes dokumentum vakon beadagolasa,
- a `max_chunks` plafon megkerulese.

## 5. Fogalmak

### 5.1 Seed chunk

Olyan chunk, amelyet az alap retrieval megtalalt.

Forrasai:

- semantic hit,
- hybrid hit,
- keyword hit hybrid komponenskent.

### 5.2 Heading seed

Olyan seed chunk, amelynel a heading/path kulonosen eros jel.

Pelda jelek:

- a query fo fogalma szerepel a headingben,
- a dokumentum path/filename es a heading egyutt eros temajel,
- a chunk rovid, heading-szeru, de magas score-t kapott.

### 5.3 Section candidate

Olyan chunk, amely nem feltetlenul volt kozvetlen retrieval talalat, de egy
eros seed chunkhoz tartozik strukturailag.

Pelda:

- ugyanazon heading alatt kovetkezo chunk,
- kozvetlen al-heading alatt levo chunk,
- rovid heading chunk alatt levo magyarazat vagy kodblokk.

### 5.4 Document candidate

Egy dokumentumhoz tartozo seed es section candidate chunkok osszessége,
osszesitett dokumentum score-ral.

## 6. Javasolt algoritmus

### 6.1 Elso fazis: seed retrieval

Maradjon a mostani semantic/hybrid retrieval alap:

1. keyword/semantic/hybrid candidate-ek letrejonnek,
2. Markdown-aware scoring lefut,
3. top seed lista kialakul.

Fontos:

```text
A seed retrieval tovabbra is relevancia szerint valaszt.
```

### 6.2 Masodik fazis: section expansion

Minden seed chunkra vizsgaljuk:

- heading path,
- heading level,
- chunk hossza,
- seed score,
- expansion priority,
- dokumentum path/filename temajelleg,
- kozeli chunkok heading kompatibilitasa.

Bovites tortenhet:

- azonos heading path alatt,
- kozvetlen al-heading alatt,
- rovid heading-szeru seed utan kovetkezo tobb chunkra,
- magas priority nem-heading seed utan kovetkezo tobb kompatibilis chunkra.

Nem bovitheto:

- masik dokumentumba,
- teljesen mas heading agra,
- tul tavoli chunkokra kontroll nelkul,
- `max_chunks` plafonon tul.

### 6.2a Expansion priority es forward context

A nyers retrieval score onmagaban nem eleg jo dontesi alap arra, hogy egy seed
mennyi kontextust erdemel. Elofordulhat, hogy a semantic score alacsony, de a
heading/path/filename alapjan emberi szemmel nyilvanvalo, hogy a chunk egy
fontos temakaput jelent.

Ezert a bovitesi jog alapja kulon `expansion_priority` legyen:

```text
expansion_priority =
  retrieval_score
  + heading relevance
  + path/filename topic bonus
  + technical/code bonus
```

Javasolt elso lepcsozes:

```text
expansion_priority >= 0.80:
  seed + kovetkezo 8-10 kompatibilis chunk

expansion_priority >= 0.60:
  seed + kovetkezo 4-6 kompatibilis chunk

alatta:
  csak seed, vagy csak a mar kozvetlenul megtalalt candidate
```

A bovites alapiranya Markdown jegyzeteknel forward legyen, mert a hasznos
magyarazat, pelda es kodblokk gyakran a megtalalt bevezeto/heading utan jon.
Elozo chunkot csak kesobbi kulon dontessel erdemes visszahozni, ha konkret live
pelda indokolja.

Fontos fekek:

- csak ugyanazon dokumentumon belul,
- csak azonos vagy kompatibilis heading agon,
- kemeny `max_chunks` plafonon belul,
- globalis expansion budgettel, hogy sok kozepes seed ne tolja tele a SOURCE-ot
  zajos kornyezettel.

### 6.3 Harmadik fazis: szarmaztatott score

A section candidate score-ja szarmazzon a seed score-bol.

Javasolt komponensek:

- seed score,
- tavolsag a seed chunktol,
- heading kompatibilitas,
- heading level,
- chunk hossza/tartalmassaga,
- code block jelenlet technikai query mellett.

Pelda gondolat:

```text
section_candidate_score =
  seed_score
  * heading_compatibility_factor
  * distance_decay
  + local_content_bonus
```

Nem cel, hogy ez matematikailag tokeletes legyen. Cel, hogy:

- determinisztikus legyen,
- tesztelheto legyen,
- ne jutalmazza tul a hosszu dokumentumokat,
- ne toljon be vakon sok kornyezeti chunkot.

### 6.4 Negyedik fazis: dokumentum score

A dokumentumok sorrendjet ne a dokumentum hossza dontse el.

Ezert a document score ne egyszeru osszeg legyen minden chunkra.

Javasolt:

- csak a top N seed/section score szamitson,
- legyen capelve,
- kapjon plusz jelet, ha tobb eros seed ugyanabbol a dokumentumbol jon,
- kapjon plusz jelet, ha a path/filename/heading temailag eros,
- ne kapjon aranytalan elonyt csak azert, mert sok chunkja van.

Pelda:

```text
document_score =
  sum(top 3 seed scores)
  + capped section coverage bonus
  + path/heading topic bonus
```

### 6.5 Otodik fazis: packing

A vegso SOURCE lista osszeallitasa:

1. dokumentumok rendezese `document_score` szerint csokkenoen,
2. dokumentumon belul candidate chunkok rendezese termeszetes `chunk_index`
   szerint,
3. deduplikalas,
4. `max_chunks` kemeny plafon alkalmazasa.

Fontos:

```text
A dokumentumok kozotti sorrend lehet score alapu, de dokumentumon belul a
chunkok termeszetes sorrendben maradjanak.
```

Ez tartja meg a kontextust.

## 7. Pelda

Tegyük fel:

```text
max_chunks = 30

Y dokumentum: 7 relevans/expanded candidate
Z dokumentum: 13 relevans/expanded candidate
X dokumentum: 15 relevans/expanded candidate

document_score sorrend:
Y > Z > X
```

Vegso SOURCE:

```text
Y osszes 7 candidate chunkja chunk sorrendben
Z osszes 13 candidate chunkja chunk sorrendben
X candidate chunkjaibol az elso 10 chunk sorrendben
```

Nem azt jelenti, hogy X dokumentum elso 10 chunkja kerul be, hanem azt, hogy
X kivalasztott candidate chunkjai kozul az elso 10 termeszetes sorrendben.

## 8. Score es heading level

A heading level ertekes jel lehet.

Altalanos irany:

- magasabb szintu heading / rovidebb heading path erosebb temakaput jelenthet,
- alacsonyabb szintu heading pontosabb resztemat jelenthet,
- heading path query overlap eros relevanciajel,
- heading seed alatt levo chunkok bovitesi jogot kaphatnak.

Vigyazat:

```text
Heading level onmagaban ne legyen eleg. Mindig legyen mellette query/path/text
vagy retrieval score jel.
```

## 9. API/UI hatas

Elso korben nem kell uj user-facing kapcsolo.

Lehetseges kesobbi debug/UI jelzes:

- `retrieval_match_type = section_context`,
- `retrieval_match_type = section_seed`,
- dokumentumon beluli source grouping,
- forraskartyakon:
  - `Hybrid`,
  - `Szemantikus`,
  - `Környezeti szövegrész`,
  - `Szekciókörnyezet`.

Elso implementacios javaslat:

```text
Ne a UI-t bonyolitsuk eloszor. Eloszor a backend source selection legyen
tesztelt es stabil.
```

## 10. Tesztterv

Minimum tesztek:

1. Heading seed alatt levo azonos section chunk bekerul.
2. Inkompatibilis heading ag nem kerul be.
3. Document score nem jutalmazza tul a hosszu dokumentumot.
4. Dokumentumok sorrendje document score szerint alakul.
5. Dokumentumon belul chunk_index sorrend marad.
6. `max_chunks` kemeny plafon marad.
7. Deduplikacio mukodik, ha ugyanaz a chunk seed es section candidate is.
8. Keyword mode nem valtozik varatlanul.
9. A mostani context-neighbor tesztek vagy megmaradnak kompatibilisen, vagy
   tudatosan atvezetjuk oket section-aware tesztekbe.

## 11. Implementacios javaslat

Ez mar nagyobb, mint egy egyszeru helper.

Javasolt modul:

```text
app/services/knowledge_retrieval.py
```

Ide kerulhet:

- chunk score komponensek,
- heading compatibility,
- section expansion,
- document score,
- packing,
- deduplikalas,
- final ordering.

`knowledge_query.py` maradjon orchestration:

- dokumentumok betoltese,
- retrieval meghivasa,
- LLM prompt epites,
- valasz parsing,
- response osszerakas.

## 12. Implementacios sorrend

Javasolt sorrend:

1. Tesztbaseline a mostani context-neighbor viselkedesre. `ELKESZULT`
2. Helper/model objektumok bevezetese viselkedesvaltozas nelkul. `ELKESZULT`
3. Heading compatibility es heading-level scoring kiszervezese. `ELSO SZELET ELKESZULT`
4. Section expansion bevezetese csak semantic/hybrid modra. `ELSO SZELET ELKESZULT`
5. Document scoring es packing bevezetese. `ELSO SZELET ELKESZULT`
6. Live teszt nagyobb Markdown tudásbázison.
7. Csak ezutan dontsunk deterministic rerankingrol.

## 12a. Implementalt v1 reszletek

Az elso implementalt backend szelet:

- `app/services/knowledge_retrieval.py` tartalmazza a retrieval helper reteget,
- `score_heading_relevance` es `heading_level_bonus` kezeli a heading seed
  pontozas elso determinisztikus jeleit,
- semantic/hybrid context expansion eloszor section contextet probal
  heading-relevans seedek alatt,
- ha nincs section context, a forward `context_neighbor` fallback megmarad
  nem-heading, de eleg eros seedekre,
- a bovitesi jogot `expansion_priority` adja, nem pusztan a nyers retrieval
  score:
  - retrieval score,
  - heading relevance,
  - path/filename topic bonus,
  - technical/code bonus,
- magas priority seed legfeljebb 10 kovetkezo kompatibilis chunkot hozhat,
- kozepes priority seed legfeljebb 6 kovetkezo kompatibilis chunkot hozhat,
- alacsony priority seed nem kap automatikus forward contextet,
- `score_document_candidates` capelt dokumentum score-t szamol:
  - top 3 candidate score osszege,
  - kis, maximalizalt coverage bonus,
  - nem egyszeru teljes dokumentumosszpontszam,
- `pack_retrieved_chunks_by_document`:
  - deduplikal document/chunk szerint,
  - a magasabb score-u duplikatumot tartja meg,
  - dokumentumokat document score szerint rendezi,
  - dokumentumon belul `chunk_index` sorrendet tart,
  - kemenyen betartja a `max_chunks` plafont,
  - ujracimkezi a SOURCE label-eket.

Ezzel a Tudásbázis SOURCE lista mar nem pusztan globalis top chunk lista,
hanem dokumentumszintu kontextuscsomag, amely a dokumentumon beluli olvasasi
sorrendet megorzi. A célzott Kubernetes/kubectl cheatsheet jellegu esetekben
az alacsonyabb nyers semantic score-u, de heading/path alapjan erosen relevans
kapu chunkok is eleg kontextust kaphatnak maguk utan.

## 13. Nyitott kerdesek

1. Mi legyen a section expansion maximalis tavolsaga?
   - Elso gondolat: ne fix ±N legyen, hanem heading boundary-ig, de capelve.
2. Hany seed chunk szamitson egy dokumentum score-jaba?
   - Elso gondolat: top 3-5.
3. Milyen match type legyen a sectionbol behuzott chunkokon?
   - Elso gondolat: `section_context`.
4. A jelenlegi `context_neighbor` megmaradjon-e kulon egyszeru fallbackkent?
   - Elso gondolat: a section-aware packing kivalthatja, de atmenetileg
     maradhat kompatibilitasi reteggel.
5. Kell-e UI-n dokumentumcsoportositas a forraskartyakhoz?
   - Elso gondolat: kesobb hasznos lehet, de nem elso backend kor.

## 14. Elfogadasi kriterium

A szelet akkor tekintheto kesznek, ha:

- semantic/hybrid Tudásbázis retrieval nem csak top chunk listat ad, hanem
  dokumentum/section-aware forrascsomagot,
- heading seedek alatt a relevans tartalom nagyobb esellyel bekerul,
- masik dokumentum vagy idegen heading ag nem keveredik be kontroll nelkul,
- `max_chunks` tovabbra is kemeny korlat,
- dokumentumon belul a SOURCE sorrend termeszetes marad,
- a Kubernetes-szeru heading-heavy live tesztben a forraskartyak nem csak
  cimeket, hanem alatta levo erdemi tartalmat is adnak,
- a relevans unit tesztek zolden futnak.
