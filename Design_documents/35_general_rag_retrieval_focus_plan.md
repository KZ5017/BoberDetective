# 35. Altalanos iratkerdezo: keresesi fokusz es kerdes szetvalasztasa

## Implementacios allapot

2026-07-05: az elso implementacios szelet elkeszult.

- `RagQueryRequest` opcionális `retrieval_query` mezot kapott.
- A backend RAG source selection az explicit `retrieval_query` mezot hasznalja, ha ki van toltve, kulonben visszaesik a `question` szovegre.
- Az LLM promptok tovabbra is a `question` mezot hasznaljak `QUERY`-kent.
- Az analysis run input es a retrieval metadata rogzitik az effective retrieval queryt es annak forrasat.
- A frontend `Altalanos iratkerdezo` feluleten megjelent a `Kereses fokusza (ajanlott)` mező, a `Kerdes` textarea pedig ket sorosra tomorodott.
- Celzott ellenorzes: `tests/test_rag.py` 26 passed, `npm --prefix frontend run build` passed, `git diff --check` passed.

## Cel

Az `Altalanos iratkerdezo` jelenleg ugyanazt a felhasznaloi szoveget hasznalja ket kulon feladatra:

- retrieval / forraskivalasztas: mely szovegreszek keruljenek a modell ele,
- valaszgeneralas: mit csinaljon a modell a mar kivalasztott szovegreszekkel.

Ez kis kerdeseknel elfogadhato, de hosszabb, instrukcios jellegu kerdeseknel zajt vihet a retrievalbe. Pelda:

```text
Kerlek reszletesen pontokba szedve ird le lepesrol lepesre hogyan jutott el a detektiv a megoldashoz.
```

Ez jo LLM-utasitas, de retrieval szempontbol a `kerlek`, `reszletesen`, `pontokba szedve`, `lepesrol lepesre` jellegu szavak nem feltetlenul segitik a legjobb chunkok kivalasztasat.

A cel egy opcionalis, felhasznalo altal megadhato `Kereses fokusza` mezo bevezetese az `Altalanos iratkerdezo` modulban. Ha ez ki van toltve, akkor csak a retrieval hasznalja. A valaszgeneralo prompt tovabbra is a `Kerdes` tartalmat kapja feladatkent.

## Elso implementacios scope

Csak az `Altalanos iratkerdezo / Kerdes az iratallomanyhoz` feluletet erinti.

Nem erinti ebben a szeletben:

- `Ugy munkapad / Kutatasi talalatok keresese`,
- `Tudasbazis / Kerdes a tudasbazishoz`,
- `AI-asszisztens`,
- `Teljes iratfeldolgozas / Szabad iratkerdes`,
- a chunkolo, indexelo vagy Qdrant storage reteget,
- a RAG valasz adatmodelljet mint tartos mentett valaszt.

Az `Ugy munkapad` kesobb kaphat hasonlo bontast, de csak akkor, ha az altalanos iratkerdezos kiserlet live teszten erteket mutat.

## Felhasznaloi modell

A felulet ket szoveges mezot mutasson:

1. `Kereses fokusza (ajanlott)`
   - opcionalis,
   - egy soros beviteli mezo,
   - a retrieval / forraskivalasztas szovege,
   - ha ures, a rendszer a jelenlegi mukodes szerint a `Kerdes` szoveget hasznalja retrievalre.

2. `Kerdes`
   - kotelezo,
   - rovidebb, kb. ket soros textarea,
   - a modellnek szolo valaszgeneralasi feladat,
   - tovabbra is ez jelenjen meg a valaszhoz kapcsolodo fo kerdeskent.

Pelda:

```text
Kereses fokusza:
detektiv Dupin bunteny nyomozas megoldas orangutan villamharito

Kerdes:
Kerlek reszletesen pontokba szedve ird le lepesrol lepesre hogyan jutott el a detektiv a megoldashoz.
```

Ebben az esetben a retrieval a fokusz szovegre fut, de az LLM a kerdes alapjan tudja, milyen szerkezetu es reszletessegu valaszt varunk.

## Backend contract

### Uj opcionalis request mezo

`RagQueryRequest` kapjon egy uj opcionalis mezot:

```text
retrieval_query: str | None
```

Javasolt szabalyok:

- `None` vagy csak whitespace eseten nincs kulon retrieval fokusz.
- Nem ures ertek eseten trimelt valtozat kerul hasznalatra.
- Javasolt maximum: 1000 karakter. Ez eleg egy tomor keresesi fokuszhoz, es nem keveri ossze a mezot a teljes kerdes / instrukcio szerepevel.
- A `question` tovabbra is kotelezo es a jelenlegi hosszkorlat szerint mukodik.

### Fallback szabaly

A retrieval szoveg meghatarozasa:

```text
retrieval_text = retrieval_query.trim() if retrieval_query is not blank else question
```

Ez biztositja a visszafele kompatibilitast:

- regi frontend / API kliens tovabbra is mukodik,
- ha a user nem akar kulon fokuszt megadni, semmi nem valtozik,
- csak explicit kitoltott fokusz valtoztatja meg a forraskivalasztast.

## Retrieval viselkedes

A valtoztatando pont az `app/services/rag.py` RAG source chunk szelekcios aga.

Jelenlegi logikai alak:

```text
_select_rag_source_chunks(... payload.question ...)
```

Uj logikai alak:

```text
retrieval_text = resolve_rag_retrieval_text(payload)
_select_rag_source_chunks(... retrieval_text ...)
```

A belso `AnalysisModuleRunRequest` vagy kozos retrieval helper tovabbra is kaphat `query` nevu mezot, de annak erteke a retrievalre szant szoveg legyen, nem feltetlenul a valaszkent megvalaszolando kerdes.

Fontos: ez nem uj retrieval algoritmus. A keyword / semantic / hybrid mukodes valtozatlan marad. Csak az alapul vett szoveg valaszthato szet.

## Prompt viselkedes

Az LLM promptban a `QUERY` tovabbra is a felhasznaloi `question` legyen.

Nem javasolt a `retrieval_query` kulon prompt-reszkent valo beadása az elso szeletben, mert az ujra osszekeverheti a ket szerepet:

- a retrieval fokusz a forrasok megtalalasara valo,
- a kerdes a valasz format, szempontjat es feladatat hatarozza meg.

Egy dokumentumos RAG:

```text
QUERY = question
SOURCE = selected chunks from retrieval_text
```

Tobbdokumentumos RAG:

```text
partial document answers: QUERY = question
final synthesis: QUERY = question
source selection before both: retrieval_text
```

## Provenance, audit es visszakereshetoseg

A futasnal visszakereshetoen rogziteni kell, hogy mi volt:

- a valaszgeneralo kerdes,
- a retrievalhez hasznalt szoveg,
- volt-e explicit kulon retrieval fokusz.

Javasolt rogzites:

- `analysis_run.input_parameters` tartalmazza:
  - `question`,
  - `retrieval_query` vagy `null`,
  - `effective_retrieval_query`,
  - `retrieval_query_source`: `explicit` vagy `question_fallback`.

A mentett `rag_answers` tablaba elso korben nem szukseges uj oszlop. A mentett valasz az analysis runon keresztul auditalhato. Ha kesobb a mentett valasz listaban is kulon meg akarjuk jeleniteni a keresesi fokuszt, akkor azt vagy a meglevo retrieval metadata JSON-bol, vagy egy kesobbi migracioval lehet finomitani.

## API valasz es frontend allapot

A `RagQueryResponse` retrieval metadata resze opcionalisan tartalmazhatja:

```text
retrieval_query
retrieval_query_source
```

Ez a frontendnek hasznos lehet:

- utolso iratkerdezo keresesi osszegzes,
- debug / live teszt visszajelzes,
- kesobbi mentett valasz reszletei.

Elso implementacios minimum:

- request fogadja a mezot,
- backend hasznalja retrievalre,
- analysis run inputban rogziti,
- frontend elkuldi.

Megjelenites opcionalis, de javasolt legalabb az aktualis futas osszegzeseben vagy reszleteiben lathatova tenni, ha a fokusz elter a kerdestol.

## Frontend implementacios terv

Erintett felulet: `Altalanos iratkerdezo`, `Kerdes az iratallomanyhoz` panel.

1. Allapot:
   - uj React state: `ragRetrievalQuery` vagy `ragSearchFocus`,
   - reset / case valtas / forrasvaltas eseten a jelenlegi form-reset logikaval osszhangban kezelendo.

2. UI:
   - a `Kerdes` textarea fole kerul egy uj input:
     - label: `Kereses fokusza (ajanlott)`,
     - egy soros,
     - placeholder lehet visszafogott, peldaul: `Kulcsszavak, nevek, temak a forrasok megtalalasahoz`.
   - a `Kerdes` textarea marad kotelezo, de vizualisan legyen tomorebb, kb. ket sor magas.
   - a `Kerdes inditasa` gomb tovabbra is csak a `Kerdes` kitolteset kovetelje meg.

3. Request payload:
   - `question`: a kotelezo kerdes,
   - `retrieval_query`: trimelt fokusz vagy `null` / omitted.

4. UI copy:
   - ne legyen tulmagyarazo zaj,
   - a label eleg legyen a szerep jelzesere,
   - ha kesobb kell, lehet tooltip vagy kompakt hint, de elso korben nem szukseges.

## Backend implementacios terv

1. Schema:
   - `app/schemas/rag.py` / `RagQueryRequest` bovites `retrieval_query` mezovel.
   - Whitespace normalizalas / validator, ha a projektben erre van kialakult pattern.

2. Service:
   - `app/services/rag.py` kapjon egy kicsi helper logikat:
     - `resolve_rag_retrieval_query(payload) -> (effective_text, source)`.
   - `_select_rag_source_chunks` a helper eredmenyet hasznalja.
   - `_generate_rag_answer` es prompt builder hivasok maradjanak `payload.question` alapon.

3. Analysis run input:
   - RAG run input parameters bovuljenek a retrieval fokusz mezokkel.
   - A selected source inputok tovabbra is a tenylegesen kivalasztott chunkokat rogzitsek.

4. Response metadata:
   - ha egyszeru, bovitheto a `retrieval_metadata` a `retrieval_query` / `retrieval_query_source` mezokkel.
   - Ha ez sok schema churnt okozna, elso szeletben eleg az analysis run input rogzites, de a UI visszajelzes miatt a metadata bovites javasolt.

## Tesztterv

Backend tesztek:

1. `POST /rag/query` kulon `retrieval_query` mezovel:
   - a retrieval helper az explicit fokuszt kapja,
   - az LLM promptban a `question` marad.

2. `POST /rag/query` ures / whitespace `retrieval_query` mezovel:
   - fallback a `question` szovegre.

3. Visszafele kompatibilitas:
   - `retrieval_query` nelkuli regi payload tovabbra is sikeres.

4. Analysis run rogzites:
   - `question`, `retrieval_query`, `effective_retrieval_query`, `retrieval_query_source` visszakeresheto.

5. Schema validacio:
   - tul hosszu retrieval fokusz elutasitasa,
   - ures `question` tovabbra is elutasitva.

Frontend ellenorzes:

- `npm --prefix frontend run build`.
- Kezi live teszt:
  - fokusz nelkul ugyanaz a viselkedes, mint eddig,
  - kulon fokusz mellett mas / jobb forrasvalasztas lathato a felhasznalt forrasokban,
  - a valasz szerkezete tovabbra is a `Kerdes` mezot koveti.

## Tudatos dontesek

- Nincs automatikus backend query-varians gyartas a felhasznalo helyett.
- Nincs automatikus fallback a `question`-re, ha az explicit `retrieval_query` nem talal jo forrast. Ha a user kulon fokuszt adott meg, azt tiszteletben tartjuk; ha rossz, a user finomitja.
- Nincs uj RAG valasz-adatbazis migration az elso szelethez.
- Nincs `search_findings` atalakitas az elso szeletben.
- Nincs promptba kevert kulon `RETRIEVAL_FOCUS` blokk az elso szeletben.

## Kockazatok

- A tul szuk fokusz keves vagy felrecsuszott forrast adhat.
- A felhasznalo eleinte nem biztos, hogy erzi a ket mezo kozti kulonbseget.
- Ha a fokusz tul hosszu vagy instrukcioszeru, ugyanaz a zaj visszakerulhet, csak masik mezon keresztul.

Ezeket UX oldalon finoman lehet kezelni, de nem erdemes tul sok segedszoveggel kezdeni.

## Varhato minosegi nyereseg

A varhato nyereseg foleg hybrid retrievalnel jelentkezhet:

- a keyword oldal tisztabb, celzottabb kifejezeseket kap,
- a semantic oldal kevesebb formai/instrukcios zajjal dolgozik,
- a modell tovabbra is reszletes, termeszetes kerdesre valaszolhat,
- a forraskivalasztas es a valaszformatum kevesbe huzza egymast rossz iranyba.

Ez nem helyettesiti a retrieval scoring tovabbi finomitasat, de alacsony kockazatu, felhasznalo altal kontrollalhato minosegi kapcsolo.

## Implementacios sorrend

1. Backend schema bovites `retrieval_query` mezovel.
2. Retrieval-text resolver bevezetese `app/services/rag.py` alatt.
3. Source selection atkotese az effective retrieval textre.
4. Prompt oldali ellenorzes: minden LLM valaszprompt tovabbra is `question` alapu maradjon.
5. Analysis run input / retrieval metadata rogzites.
6. Backend tesztek bovitese.
7. Frontend UI mezo bevezetese a `Kerdes` felett.
8. Frontend request payload bovites.
9. Frontend build.
10. Live teszt egy olyan kerdesen, ahol a hosszu instrukcio es a celzott fokusz varhatoan kulonbozo forrasvalasztast ad.

## Kesobbi kiterjesztesi pontok

Ha az elso szelet mukodik, ugyanez a minta kesobb megfontolhato:

- `Ugy munkapad / Kutatasi talalatok keresese` eseteben,
- mentett RAG valasz reszleteiben kulon `Kereses fokusza` kijelzessel,
- opcionalis tooltip / rovid pelda UI hinttel,
- esetleg API-szinten egyseges `retrieval_query` fogalommal mas RAG jellegu modulokban.

A `Tudasbazis` modulnal ezt nem kell automatikusan atvenni, mert ott a Markdown-aware retrieval es a kerdes jellege mas minosegi problemakat kezel.
