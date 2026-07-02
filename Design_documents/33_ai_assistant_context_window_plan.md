# AI-asszisztens Kontextusablak Kezelesi Terv

## 1. Cel

Az AI-asszisztens jelenlegi chatfelulete stabil elso baseline, de a hosszu beszelgetesek kontextusablak-kezelese legyen tudatosabb es lathatobb.

A cel:

- a modell mindig a legutobbi felhasznaloi uzenetre valaszoljon,
- a korabbi uzeneteket csak beszelgetesi kontextuskent hasznalja,
- ne tortenjen lathatatlan, csendes regi-uzenet levagas,
- a felhasznalo ertheto jelzest kapjon, ha a beszelgetes mar tul nagy ehhez a chathez,
- a frontend es a backend ugyanazt a vedelmi logikat kovesse.

Ez a terv az AI-asszisztens modulra vonatkozik. Nem erinti a RAG, Tudásbázis, Ügy munkapad vagy teljes iratfeldolgozasi promptokat.

## 2. Tudatos nem-celok

Ez a szelet nem vezet be:

- streaming valaszmegjelenitest,
- automatikus beszelgetes-osszefoglalast,
- cross-chat memoriat,
- szemelyes profilt,
- RAG-ot vagy ugyirat-hozzaferest az AI-asszisztenshez,
- source-bound vagy nyomozati rendszerpromptot,
- automatikus objektumletrehozast,
- tobb agas regenerate/verziozasi modellt.

A modul tovabbra is altalanos, lokalis LLM chatfelulet marad.

## 3. Jelenlegi allapot

A jelenlegi backend mukodes lenyege:

- az `assistant_chats` es `assistant_messages` minden beszelgetest es uzenetet tarol,
- az LLM hivas elott a backend a chat uzeneteibol epit kontextust,
- a jelenlegi kontextusvalaszto karakteralapu budgetet hasznal,
- ha a history tul hosszu, a regi uzenetek csendben kimaradhatnak az LLM requestbol,
- az AI-asszisztens jelenleg nem hasznal kulon system promptot,
- az assistant valasz generalasnal nincs kemeny kimeneti tokenlimit kenyszeritve,
- a reasoning mod uzenetenkent/regeneralasonkent kuldheto.

Ez technikailag mukodik, de hosszu chatnel felhasznaloi szempontbol felrevezeto lehet, mert a UI-ban latszo regi kontextus nem feltetlenul kerul be a modellhez.

## 4. Uj dontesek

### 4.1 Minimalis altalanos system prompt

Az AI-asszisztens kapjon egy minimalis, nem nyomozati, nem forrasalapu system promptot:

```text
Valaszolj a legutobbi felhasznaloi uzenetre. A korabbi uzeneteket csak beszelgetesi kontextuskent hasznald.
```

Ez a prompt szandekosan nem tartalmaz:

- BoberDetective rendszerkontextust,
- ugyirat- vagy forrashivatkozasi szabalyokat,
- jogi/nyomozati szerepmeghatarozast,
- JSON vagy strukturalt output elvarast.

Celja csak az, hogy a modell beszelgetesi helyzetben is az aktualis utolso user uzenetet tekintse feladatnak.

### 4.2 Konzervativ karakterbudget

A hasznalt fejlesztoi modell jelenlegi tervezett kontextusablaka nagy, de a vedelmi limitet szandekosan alulbecsult karakterbudgettel kell megfogni.

Tervezett kezdeti ertek:

```text
ASSISTANT_CONTEXT_CHARACTER_BUDGET = 120000
```

Ez nagyjabol a 53000 tokenes celterulet konzervativ karakteres kozelitese. A minimalis system promptot nem kell kulon beleszamolni ebbe a budgetbe, mert az alulbecsles eleve biztonsagi tartalekot hagy.

### 4.3 Csendes truncation helyett explicit blokk

Az AI-asszisztens normal uzenetkuldesenel a backend ne vagja le csendben a regi uzeneteket.

Uj szabaly:

- ha a teljes aktiv chat tartalma + az uj user uzenet belefer a budgetbe, a teljes chatkontextus kuldheto a modellnek,
- ha nem fer bele, a kuldes legyen blokkolva,
- a felhasznalo kapjon ertheto jelzest, hogy uj chatet kell nyitnia vagy roviditenie kell.

A teljes history tovabbra is megmarad az adatbazisban es a UI-ban. A blokk csak az uj LLM hivasra vonatkozik.

### 4.4 Prompt-hossz es chat-hossz kulon kezelese

Ket helyzetet kell kulon kezelni:

1. Az aktualis beirt uzenet onmagaban tul hosszu. Az elso implementalt ertek megegyezik a teljes chat budgettel: 120000 karakter.
2. Az aktualis uzenet onmagaban elfogadhato, de a teljes beszelgetessel egyutt mar tullepi a chat budgetet.

Az elso esetben eleg inline UI jelzes es a kuldes gomb tiltasa.

A masodik esetben a megosztott `app-dialog` stilusu felugro jelzes javasolt, mert ez mar chat-szintu allapot, nem csak inputvalidacio.

Javasolt magyar szovegek:

```text
Az uzenet tul hosszu ehhez a chathez. Roviditsd, vagy indits uj beszelgetest.
```

```text
A beszelgetes elerte a kontextuskeretet
Ez az uzenet mar nem kuldheto el biztonsagosan ebben a beszelgetesben. Nyiss uj chatet a folytatashoz, hogy a modell ne veszitsen el korabbi kontextust lathatatlanul.
```

## 5. Backend terv

### 5.1 Kontextusmeres

Legyen egy kozponti helper az AI-asszisztens szolgaltatasban, amely:

- osszeszamolja az aktiv chat uzeneteinek `content` hosszat,
- hozzaadja az uj user uzenet hosszat,
- osszeveti az `ASSISTANT_CONTEXT_CHARACTER_BUDGET` ertekkel,
- egyertelmu hibaval megallitja a requestet, ha tul nagy.

Az ellenorzes ne a frontend bizalmara epitsen; a backend legyen az authoritative guard.

### 5.2 LLM message lista

Ha a budget rendben van, az LLM fele kuldott uzenetlista:

1. minimalis system prompt,
2. teljes chat history idorendben,
3. az aktualis user uzenet, ha meg nem szerepel a historyban a konkret hivas epitesi pontjan.

Az implementacional figyelni kell arra, hogy a jelenlegi kuldesi folyamat mar elmenti a user uzenetet a valaszgeneralas elott. Emiatt a helper ne duplazza az aktualis user uzenetet.

### 5.3 Regeneralas

Az utolso asszisztens-valasz ujrageneralasa ugyanazt a budget ellenorzest hasznalja.

Mivel a jelenlegi dontes szerint csak a legutolso asszisztens-valasz regeneralhato, nincs szukseg tobb agas beszelgetesmodellre. A legutolso assistant uzenet torlese utan a fennmarado chat history alapjan kell ujra LLM hivasra menni.

### 5.4 API hiba

Ha a budget tulcsordul, a backend adjon tiszta, UI altal megjelenitheto hibakodot/uzenetet.

Javasolt belso hibakod:

```text
assistant_context_limit_exceeded
```

HTTP szinten a 400-as validacios hiba eleg.

## 6. Frontend terv

### 6.1 Inline input vedelmi jelzes

A composer oldalon legyen kliensoldali becsles:

- ha a draft onmagaban tul hosszu, a kuldes gomb legyen tiltva,
- a felhasznalo kapjon rovid inline magyar jelzest.

Ez UX kenyelmi reteg, nem biztonsagi reteg.

### 6.2 Chat-szintu blokk dialog

Ha a chat + draft becsult hossza tullepi a budgetet:

- a kuldes ne induljon el,
- jelenjen meg tokenizalt `app-dialog`,
- a dialog magyarul mondja el, hogy a beszelgetes elerte a kontextuskeretet,
- elso korben csak bezaras gomb kell.

Kesobbi kenyelmi bovites lehet:

- `Uj chat nyitasa ezzel az uzenettel`

Ez most tudatosan nem resze az elso implementacionak.

### 6.3 Backend hiba megjelenitese

Ha a frontend becsles ellenere a backend dobja vissza a requestet:

- ugyanazt a dialog-szeru UX-et kell megjeleniteni,
- ne maradjon typing indicator vagy felig elkuldott UI allapot.

## 7. Tesztelesi terv

Backend:

- tul hosszu teljes chat + uj uzenet eseten a kuldes 400-at ad,
- budgeten beluli chat teljes historyval megy tovabb,
- a minimalis system prompt bekerul az LLM hivasba,
- regeneralas is ugyanazt a budget guardot hasznalja,
- nincs csendes regi-uzenet truncation a normal AI-asszisztens chatben.

Frontend:

- tul hosszu draft letiltja a kuldes gombot,
- tul hosszu chat + draft dialogot mutat,
- backend `assistant_context_limit_exceeded` hiba dialogban jelenik meg,
- normal kuldes, masolas, regeneralas es reasoning toggle nem regresszal.

Minimum verifikacio:

```bash
.venv/bin/python -m pytest tests/test_assistant.py tests/test_llm.py -q
npm --prefix frontend run build
git diff --check
```

## 8. Implementacios sorrend

1. Backend konstans es context-budget helper bevezetese.
2. Minimalis system prompt bekotese az AI-asszisztens LLM hivasba.
3. Csendes truncation megszuntetese normal kuldesnel es regeneralasnal.
4. Backend validacios hiba es tesztek.
5. Frontend karakterbudget becsles es inline draft validacio.
6. Frontend app-dialog chat-limit jelzes.
7. Build es celzott tesztek.

## 9. Kesobbi opcionalis iranyok

Ezek nem elvarrasai az elso implementacios szeletnek:

- uj chat nyitasa a jelenlegi drafttal,
- tokenizalo-alapu pontosabb meres,
- automatikus beszelgetes-osszefoglalas,
- felhasznalo altal lathato context usage indikator,
- model/profil fuggo budget konfiguracio a UI-ban.

## 10. Implementacios allapot

2026-07-02 allapot: az elso szelet implementalva.

- Backend: `ASSISTANT_CONTEXT_CHARACTER_BUDGET = 120000`, `AssistantMessageSendRequest.content` max 120000 karakter, minimalis altalanos system prompt, teljes-history LLM message lista, explicit `assistant_context_limit_exceeded` validacios hiba, normal kuldes es utolso-valasz regeneralas budget guard.
- Frontend: tul hosszu draft inline composer warninggal es tiltott kuldes gombbal all meg; a warning sajat composer grid sorban jelenik meg, ezert nem tolja el a beviteli mezot, kuldes gombot vagy Gondolkodo gombot; tul nagy chat + draft vagy backend context-limit hiba a megosztott `app-dialog` jelzest hasznalja.
- A csendes regi-uzenet truncation az AI-asszisztens normal chat hivasabol kikerult.

Friss ellenorzes:

```bash
.venv/bin/python -m pytest tests/test_assistant.py tests/test_llm.py -q  # 28 passed
npm --prefix frontend run build
```
