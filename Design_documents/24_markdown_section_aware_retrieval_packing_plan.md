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

## 12b. Live tesztbol feltart heading-meta gap

Egy OWASP Top 10 cheat-sheet live teszt feltart egy fontos hianyzo esetet.

QUERY:

```text
OWASP Top 10 - Cheat Sheet (2021)
```

A dokumentumban a lenyegi fo heading:

```text
## OWASP Top 10 - Cheat Sheet (2021)
```

A Marko/AST parser ezt helyesen felismeri es a `text_layer.json` `headings`
listajaba teszi, valamint a kovetkezo A01-A10 chunkok `heading_path`
ertekebe beemeli. Viszont a fo heading nem jelenik meg onallo chunk `text`
ertekkent.

A retrieval ezert a bevezeto chunkot talalta meg, mert abban szovegkent
szerepelt az `OWASP Top 10 (2021)` es a `cheat-sheet`. Ez a chunk azonban
`heading_path=""` erteku, ezert a jelenlegi expansion szabaly nem lep at a
kovetkezo fo heading ala.

Kovetkezmeny:

- a valodi A01-A10 tartalom letezik chunkokban,
- a fo heading metaadatkent letezik,
- a SOURCE listaba megis csak a bevezeto chunk kerulhet be,
- az LLM nem kapja meg a temahoz tartozo teljes cheat-sheet kontextust.

Ez legalabb harom kulon, de osszefuggo resproblema:

1. **Meta-heading nem teljes erteku retrieval anchor.**
   - A fo heading csak `heading_path`/`headings` adatban latszik, de nem
     viselkedik onallo seedkent.

2. **A keyword/hybrid scoring nem hasznalja eleg erosen a `heading_path`
   mezot.**
   - Az A01-A10 chunkok relevansak, mert a `heading_path` tartalmazza a
     keresett fo cimet, akkor is, ha a chunk sajat `text` mezoben mar csak
     az A01/A02... tartalom van.

3. **Pre-heading seed nem tud atlepni a kovetkezo relevans heading ala.**
   - Ha egy magas score-u bevezeto chunk kozvetlenul egy query-matching
     heading elott all, akkor a kovetkezo heading alatti szekciot is
     expansion candidate-kent kell kezelni.

## 12c. V2 javitasi terv: heading anchor es pre-heading bridge

Cel:

```text
Ha a query egy Markdown fo headingre vagy section cimre illeszkedik, akkor a
retrieval ne csak a cimet/bevezetot talalja meg, hanem a heading ala tartozo
erdemleges chunkokat is atadja az LLM-nek.
```

### 12c.1 Heading path scoring erosites

A keyword es hybrid jeloltek pontozasa hasznalja teljes erteku forraskent:

- `chunk.text`,
- `chunk.heading_path`,
- `document.relative_path`,
- `document.original_filename`.

Elvaras:

- exact query vagy jelentos query-term overlap a `heading_path` mezoben
  adjon eros, de bounded bonuszt,
- ha a query egy heading-path prefixre illeszkedik, az alatta levo chunkok
  legyenek jo seed/section candidate-ek,
- a heading score tovabbra se legyen eleg onmagaban teljesen idegen
  dokumentumok beemelesere.

### 12c.2 Meta-heading anchor kepzese

Nem kell feltetlenul uj adatbazis- vagy fajlformatum.

Elso implementacios irany:

- a meglévő `KnowledgeStoredChunk.heading_path` adatokbol derivaltan kezeljuk
  a fo heading egyezest,
- ha tobb chunk `heading_path` erteke ugyanazzal a query-matching headinggel
  indul, ezek egy logikai section candidate csoportot alkotnak,
- nem kell onallo synthetic chunkot letrehozni az LLM SOURCE listaba, ha a
  source blokkban a chunk `heading_path` is megjelenik.

Kesobbi opcionális irany:

- synthetic `heading_anchor` candidate belso retrieval objektumkent, amely
  nem mentodik kulon chunkkent, csak arra szolgal, hogy a heading alatti
  chunkokat osszefogja.

### 12c.3 Pre-heading bridge

Ha egy seed chunk:

- magas `expansion_priority` erteku,
- `heading_path` ures vagy nem egyezo,
- es kozvetlenul utana query-matching heading path alatti chunkok kovetkeznek,

akkor a kovetkezo heading ala tartozo chunkok bovitesi candidate-ek legyenek.

Ez kifejezetten az olyan dokumentumokra fontos, ahol:

- van egy rovid bevezeto,
- utana jon a valodi `##` fo cim,
- majd alatta sok `###` reszszakasz.

Fekek:

- csak ugyanazon dokumentumon belul,
- csak kozvetlenul kovetkezo heading agra,
- csak akkor, ha a kovetkezo heading path maga is egyezik a queryvel,
- `max_chunks` tovabbra is kemeny plafon,
- dokumentumon belul `chunk_index` sorrend marad.

### 12c.4 SOURCE blokk heading kontextus

A promptba adott SOURCE blokkban a chunk szovege mellett jelenjen meg a
Markdown heading path is, amikor van ilyen.

Pelda:

```text
source_3
Dokumentum: ...
Heading: OWASP Top 10 - Cheat Sheet (2021) > A01: Broken Access Control
Szoveg:
...
```

Ez nem valtoztatja meg a source-id/used-source objektumokat, csak az LLM
szamara teszi lathatova azt a kontextust, amely jelenleg csak backend
metaadatkent el.

### 12c.5 Tesztesetek

Minimum uj tesztek:

1. Fo heading csak `heading_path` metaadatban szerepel, de query egyezik vele:
   az alatta levo A01/A02... chunkok bekerulnek.
2. Magas score-u bevezeto chunk kozvetlenul query-matching heading elott all:
   a kovetkezo heading ala hidal a bovites.
3. Ures headingu bevezeto ne hidaljon at idegen vagy nem egyezo heading ala.
4. A SOURCE blokk tartalmazza a `heading_path` mezot, ha van.
5. `max_chunks` plafon tovabbra is ervenyes.
6. Dokumentumon belul a vegso SOURCE sorrend tovabbra is `chunk_index`
   szerinti.

### 12c.6 Implementacios sorrend

Javasolt sorrend:

1. Tesztben reprodukalni az OWASP Top 10 esetet kis synthetic chunk listaval.
   `ELKESZULT`
2. Heading-path scoring/selection erosites a meglévő retrieval helperben.
   `ELKESZULT`
3. Pre-heading bridge helper bevezetese az expansion fazisba.
   `ELKESZULT`
4. SOURCE blokk heading megjelenites a prompt-epitesnel.
   `MAR MEGLEVŐ, TESZTTEL ROGZITVE`
5. Celzott knowledge query teszt futtatas.
   `ELKESZULT`
6. Live OWASP teszt ujrafuttatasa.
   `KOVETKEZO USER-SIDE LIVE TESZT`

### 12c.7 Implementalt v2 reszletek

Az elso v2 javitas a meglévő section-aware retrieval retegre epul, nem csereli
le azt.

Implementalt valtozasok:

- `keyword_knowledge_search` most a chunk szovege mellett a `heading_path`,
  `relative_path` es `original_filename` mezoket is figyelembe veszi.
- Exact query egyezes es query-term overlap a `heading_path` mezoben eros,
  de bounded relevanciajelet ad.
- Magas priority, ures `heading_path`-u seed chunk eseteben az expansion
  megprobal atlepni a kozvetlenul kovetkezo query-matching heading agra.
- A pre-heading bridge csak ugyanazon dokumentumon belul mukodik, csak
  kovetkezo chunkokra, es csak addig, amig a kovetkezo chunkok headingje
  tovabbra is illeszkedik a queryre.
- A bridge-bol szarmazo chunkok `retrieval_match_type=heading_bridge`
  jelolest kapnak.
- A SOURCE blokkban a `heading_path` mező lathatosagat teszt rogzitette, hogy
  az LLM ne veszitse el a Markdown strukturakontextust.

Verifikacio:

```text
.venv/bin/python -m pytest tests/test_knowledge_api.py tests/test_knowledge_query.py -q
49 passed
```

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
