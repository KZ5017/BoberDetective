# 36. Ugy munkapad: keresesi fokusz es elemzesi fokusz szetvalasztasa

Status: Implementalva.

## Cel

Az `Ugy munkapad / Elemzes` panel `Kutatasi talalatok keresese` workflow-ja jelenleg egyetlen fokuszszoveget hasznal ket kulon celra:

- retrieval / forraskivalasztas: mely szovegreszek keruljenek a modell ele,
- LLM elemzesi feladat: a modell mit keressen, milyen kapcsolatot vagy szakmai tartalmat allapitson meg a kivalasztott forrasokban.

Ez gyakran eleg, de a gyakorlatban zajt vihet a forraskivalasztasba. Pelda:

```text
William Bird szabo tanuvallomasa
```

Retrieval szempontbol sok esetben a tomorebb kifejezes jobb:

```text
William Bird szabo
```

Az LLM-nek viszont mar hasznos lehet a pontosabb feladat:

```text
William Bird szabo tanuvallomasa
```

Ugyanez igaz akkor is, ha a felhasznalo valojaban entitaskent, szemelyes adatokkal, szereppel vagy egy konkret reszlettel kapcsolatban keres. A `tanuvallomas`, `szemelyes adatok`, `azonositas`, `reszlet` jellegu szavak az LLM feladataban ertelmesek lehetnek, de retrievalben fals pozitiv chunkokat hozhatnak be.

A cel a `search_findings` workflow-ban is ugyanannak a mintanak a bevezetese, amely az `Altalanos iratkerdezo` elso retrieval-fokusz szeleteben mar mukodik:

- `Kereses fokusza (ajanlott)` - a forraskivalasztas szovege,
- `Elemzesi fokusz` - az LLM-nek szolo szakmai feladat/fokusz.

## Scope

Ez a terv csak az `Ugy munkapad / Elemzes` panel aktiv `search_findings` workflow-jara vonatkozik.

Erinti:

- frontend `Elemzes` panel,
- `search_findings` request schema,
- `search_findings` source selection / retrieval query,
- analysis run input/provenance,
- latest research-finding run summary,
- prompt user data: `QUERY` tovabbra is az elemzesi fokusz legyen.

Nem erinti ebben a szeletben:

- `Altalanos iratkerdezo` mar implementalt `retrieval_query` mukodeset,
- `Tudasbazis` Markdown retrievalt,
- `AI-asszisztens`,
- `Teljes iratfeldolgozas`,
- `detect_contradiction_candidates` claim-par alapu workflow-t,
- review report / object conversion logikat,
- chunkolast, indexelest, Qdrant storage-t.

## Felhasznaloi modell

Az `Elemzes` panelen a jelenlegi `Fokusz` mezo helyett ket mezo legyen:

1. `Kereses fokusza (ajanlott)`
   - opcionalis,
   - egy soros input,
   - csak a keyword / semantic / hybrid retrieval kapja meg,
   - ha ures, a rendszer fallbackkent az `Elemzesi fokusz` szoveget hasznalja retrievalre.

2. `Elemzesi fokusz`
   - kotelezo,
   - ket soros textarea,
   - ezt kapja az LLM `QUERY`-kent,
   - ez hatarozza meg, hogy a modell mit keressen a mar kivalasztott forrasokban.

Felugro magyarázat az `(ajanlott)` elemre:

```text
Ide tomor temamegjeloles keruljon. A valasz formajat, reszletesseget es konkret feladatat tovabbra is az Elemzesi fokusz mezo hatarozza meg.
```

A szoveg ugyanazt a gondolatot viszi tovabb, mint az altalanos RAG kerdezoben, csak a modul nyelvere igazítva.

## Backend contract

### Javasolt mezok

A jelenlegi analysis module requestben a `query` mező maradjon meg, mert ez a `search_findings` LLM oldali `QUERY`/elemzesi fokusza.

Uj opcionális mező:

```text
retrieval_query: str | None
```

Jelentes:

- `query`: elemzesi fokusz, LLM `QUERY`,
- `retrieval_query`: keresesi fokusz, source/chunk retrieval query.

### Fallback szabaly

```text
effective_retrieval_query =
    retrieval_query.trim() if retrieval_query is not blank else query.trim()
```

Ez biztosítja:

- regi API kliensek tovabbra is mukodnek,
- a frontend akkor is mukodik, ha a user nem ad kulon keresesi fokuszt,
- csak explicit kitoltott `Kereses fokusza` valtoztatja meg a source selectiont.

### Validacio

Javasolt szabalyok:

- `query` tovabbra is kotelezo a `search_findings` modulnal.
- `retrieval_query` opcionális.
- `retrieval_query` whitespace trim utan ures -> `None`.
- Javasolt max hossz: 1000 karakter.
- A backend ne fogadja el ugy, hogy `query` ures, de `retrieval_query` ki van toltve. A keresesi fokusz nem helyettesiti az elemzesi fokuszt.

## Retrieval viselkedes

Jelenlegi logikai forma:

```text
retrieve_source_scope_chunks(payload.query)
```

Uj logikai forma:

```text
effective_retrieval_query = resolve_analysis_retrieval_query(payload)
retrieve_source_scope_chunks(effective_retrieval_query)
```

A retrieval algoritmus nem valtozik:

- keyword,
- semantic,
- hybrid,
- query variansok,
- dokumentum/page/chunk LLM input ordering,
- dokumentumonkenti batch izolacio,
- `max_chunks`,
- `batch_size`.

Csak az alapul vett keresesi szoveg valtozhat.

## Prompt viselkedes

A `search_findings` promptban a `QUERY` tovabbra is az `Elemzesi fokusz`, vagyis a request `query` mezo legyen.

Nem javasolt a `retrieval_query` kulon promptba keverese az elso szeletben, mert:

- a retrieval fokusz feladata a forrasok megtalalasa,
- az elemzesi fokusz feladata a modell szakmai dontesi kerete,
- ha mindketto bekerul a promptba, ujra osszekeveredhet a ket szerep.

Tehat:

```text
SOURCE = effective_retrieval_query alapjan kivalasztott chunkok
QUERY = query / Elemzesi fokusz
```

## Provenance es audit

Az analysis run inputban es/vagy input_parametersben rogziteni kell:

- `query`: elemzesi fokusz,
- `retrieval_query`: explicit keresesi fokusz vagy `null`,
- `effective_retrieval_query`: tenylegesen retrievalre hasznalt szoveg,
- `retrieval_query_source`: `explicit` vagy `query_fallback`.

A `query_text` analysis inputot nem szabad egyszeruen atirni ugy, hogy elveszitsuk az LLM feladatot. Javasolt:

- vagy a `query_text` payload tartalmazza mindket erteket,
- vagy kulon `retrieval_query_text` input_type kerul bevezetesre.

Elso szeletben egyszerubb es kompatibilisebb:

```json
{
  "query": "<elemzesi fokusz>",
  "retrieval_query": "<explicit vagy null>",
  "effective_retrieval_query": "<tenyleges retrieval szoveg>",
  "retrieval_query_source": "explicit | query_fallback"
}
```

## Latest run summary

A `GET /api/v1/cases/{case_id}/research-findings/latest-run-summary` valaszaban opcionálisan megjelenhet:

```text
retrieval_query
retrieval_query_source
```

Frontend oldalon a top latest-run kartyan csak akkor erdemes kiirni a keresesi fokuszt, ha:

- explicit volt,
- es elter az elemzesi fokusztol.

Pelda chip:

```text
Kereses: William Bird szabo
```

## Frontend implementacios terv

Erintett felulet:

- `Ugy munkapad`,
- `Elemzes` panel,
- `Kutatasi talalatok keresese` modul.

Javasolt UI:

1. A jelenlegi `Fokusz` label helyett:
   - felul: `Kereses fokusza (ajanlott)` egysoros input,
   - alatta: `Elemzesi fokusz` ket soros textarea.

2. Az `(ajanlott)` ugyanugy kattinthato legyen, mint az altalanos RAG kerdezoben:
   - ne nezzen ki gombnak/linknek,
   - hoverre kez kurzor,
   - `app-dialog` alert nyiljon.

3. A futtatasi gomb tovabbra is csak az `Elemzesi fokusz` kitolteset kovetelje meg.

4. A frontend payload:

```text
query = elemzesi fokusz
retrieval_query = keresesi fokusz vagy null
```

5. A `Fokuszba teszem` handoffok:
   - jelenlegi celjuk az elemzesi feladat/fokusz kitoltese,
   - ezert elso korben az `Elemzesi fokusz` mezobe toltsenek,
   - a `Kereses fokusza` maradjon ures, hogy a fallback a regi mukodest adja.

Ez fontos, mert a handoffoknal a rendszer jelenleg teljes szakmai fokuszt ad at, nem kulon retrieval kulcsszavakat.

## Backend implementacios terv

1. `AnalysisModuleRunRequest` bovites:
   - opcionális `retrieval_query`.

2. Normalizalas:
   - whitespace trim,
   - ures -> `None`.

3. Helper:

```text
resolve_analysis_retrieval_query(payload) -> (effective_text, source, explicit_text)
```

4. `search_findings` source selection:
   - retrieval query = helper effective text,
   - LLM query = payload.query.

5. Analysis run input/provenance:
   - `query_text` payload bovuljon mindket mezovel.

6. Latest research summary:
   - input/output metadata alapjan exposeolja az explicit keresesi fokuszt.

7. API/frontend type bovites.

## Tesztterv

Backend:

1. `search_findings` explicit `retrieval_query` mellett:
   - retrieval helper ezt kapja,
   - LLM prompt `QUERY` resze tovabbra is `query`.

2. `retrieval_query` nelkul:
   - fallback a `query` mezore,
   - regi tesztek tovabbra is atmennek.

3. Whitespace `retrieval_query`:
   - `None`-ra normalizalodik.

4. Tul hosszu `retrieval_query`:
   - validacios hiba.

5. Analysis run input:
   - `query`,
   - `retrieval_query`,
   - `effective_retrieval_query`,
   - `retrieval_query_source`.

Frontend:

- `npm --prefix frontend run build`.
- Kezi live teszt:
  - `Kereses fokusza`: `William Bird szabo`,
  - `Elemzesi fokusz`: `William Bird szabo tanuvallomasa`,
  - ellenorizni, hogy a forrasok jobban William Bird kore rendezodnek,
  - az LLM talalatok tovabbra is az elemzesi fokusz szerint keszulnek.

## Tudatos dontesek

- Nem vezetunk be automatikus query-okoskodast.
- Nem toltjuk ki automatikusan a keresesi fokuszt az elemzesi fokuszbol a frontend state-ben; a fallback backend oldalon tortenik.
- Nem keverjuk a `retrieval_query` szoveget az LLM promptba.
- Nem erintjuk a `detect_contradiction_candidates` modult.
- A handoffok elso korben az `Elemzesi fokusz` mezot toltik, nem a `Kereses fokusza` mezot.

## Varhato haszon

A varhato minosegi javulas foleg akkor latszik majd, amikor az elemzesi fokuszban vannak olyan szavak, amelyek:

- a modellnek hasznosak,
- retrievalben viszont tul altalanosak vagy tul sok fals pozitivot hoznak.

Tipikus peldak:

- `tanuvallomas`,
- `szemelyes adatok`,
- `szemelyazonossag`,
- `reszlet`,
- `korulmenyek`,
- `kapcsolat`,
- `szerep`.

Ezeket az `Elemzesi fokusz` tovabbra is tartalmazhatja, mikozben a `Kereses fokusza` tomor, nev/tema/entitas-kozelibb maradhat.

## Kesobbi kiterjesztes

Ha ez a szelet live teszten bevalik:

- a latest-run summaryben erosebben megjelenhet a ket fokusz kulonbsege,
- a `Fokuszba teszem` handoff kesobb kaphat opcionális keresesi fokusz javaslatot,
- a felhasznalo altal mentett workflow presetek kesobb kulon tarolhatjak a keresesi es elemzesi fokuszt.

Ezek nem az elso implementacios szelet reszei.
