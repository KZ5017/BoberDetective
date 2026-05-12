# Adatbázis-séma v1
## Megvalósítás előtti rövid terváttekintés

## 1. Cél

Ez a dokumentum a `03_database_schema_v1.md` megvalósítás előtti rövid review-ja.

A cél nem új séma készítése, hanem annak eldöntése, hogy az SQL DDL és az első migrációk előtt mit érdemes:

- egyszerűsíteni,
- kötelezővé tenni,
- későbbre halasztani,
- vagy tudatos kompromisszumként elfogadni.

## 2. Rövid értékelés

A v1 séma jó irányba épül: az eredeti dokumentum, az oldalszintű szöveg, a chunk, a source reference, az analysis run, a human review és az export külön első osztályú entitásként szerepel.

Ez jól illeszkedik a projekt fő szabályához:

> No source -> no claim.

A megvalósítás előtt a legfontosabb finomítás nem a táblák számának radikális csökkentése, hanem a provenance szabályok technikai kikényszeríthetőségének tisztázása.

## 3. Javasolt döntések SQL előtt

## 3.1 Maradjon a source reference mint külön tábla

### Döntés

Tartsuk meg a `source_references` táblát önálló, központi objektumként.

### Indok

Ez adja a rendszer legfontosabb auditálhatósági alapját:

- dokumentumra mutat,
- oldalra mutat,
- chunkra mutathat,
- idézetet tárol,
- pozícióadatokat tárolhat,
- több AI-output ugyanarra a forráshelyre hivatkozhat.

### Megerősítés

DDL-ben érdemes minimum kikényszeríteni:

- `document_id` kötelező,
- `quote_text` kötelező,
- `source_kind` ellenőrzött értékkészlet,
- `confidence` 0 és 1 között,
- `page_id` vagy `chunk_id` legalább egyikének meglétét, kivéve `document_metadata` típusnál.

## 3.2 Az AI-outputoknál a source kapcsolat legyen kötelező üzleti szabály

### Döntés

A következő objektumok ne legyenek véglegesíthetők forrás nélkül:

- `events`
- `claims`
- `contradiction_candidates`
- `missing_item_candidates`

### Indok

Ezt tiszta SQL FK-val nem mindig lehet egyszerűen kikényszeríteni, mert a forráskapcsolat külön kapcsolótáblában van. Ennek ellenére az alkalmazás- és validációs rétegben kötelező szabályként kell kezelni.

### Megerősítés

Javasolt bevezetni egy `validation_status` vagy `source_validation_status` mezőt az érintett output táblákon:

- `pending_source_validation`
- `source_valid`
- `source_invalid`

Ez praktikusabb, mint minden ellenőrzést triggerrel megoldani az első MVP-ben.

## 3.3 Az `analysis_runs` maradjon központi provenance tábla

### Döntés

Minden AI vagy feldolgozó pipeline eredetű rekordnál maradjon kötelező a `created_by_analysis_run_id`.

### Indok

Ez biztosítja, hogy egy objektum visszavezethető legyen:

- futástípusra,
- modellre vagy parserre,
- verzióra,
- prompt template-re,
- bemeneti chunkokra,
- validációs státuszra.

### Megerősítés

Az első migrációban ne csak AI-futásokra használjuk, hanem dokumentumfeldolgozó pipeline lépésekre is:

- parsing,
- OCR,
- chunking,
- embedding,
- entity extraction,
- claim extraction.

Így a feldolgozás teljes életútja egységesen auditálható.

## 3.4 Újrafeldolgozásnál legyen explicit verziózás

### Probléma

A jelenlegi séma jelzi, hogy újrafeldolgozáskor inkább új rekordok keletkezzenek, de a page/chunk aktuális verziójának kiválasztása még nincs teljesen tisztázva.

### Javaslat

Adjunk a `document_pages` és `document_chunks` táblákhoz verziókezelő mezőket:

- `version_no integer`
- `is_current boolean`
- `superseded_by_id uuid null`

### Indok

Ez segít, ha:

- OCR-t újrafuttatunk jobb beállításokkal,
- chunking stratégiát váltunk,
- parser verziót frissítünk,
- egy dokumentumot manuálisan javított szöveggel egészítünk ki.

### Döntési javaslat

MVP-ben vezessük be ezeket már az elején. Később fájdalmasabb lenne ráépíteni.

## 3.5 A polymorphic output mezők maradhatnak, de tudatos kompromisszumként

### Érintett táblák

- `analysis_run_outputs`
- `human_reviews`
- `export_items`
- `audit_events`

### Probléma

Az `object_type + object_id` mintázat rugalmas, de PostgreSQL nem tud rá hagyományos FK-integritást kikényszeríteni.

### Döntés

MVP-ben maradhat ez a minta, mert jelentősen egyszerűsíti az audit, review és export réteget.

### Megerősítés

Kell hozzá alkalmazásszintű validáció:

- az `object_type` csak ismert érték lehet,
- az `object_id` létezését mentéskor ellenőrizni kell,
- export előtt minden hivatkozott objektumot újra validálni kell.

### Későbbi alternatíva

Ha enterprise szintű integritás kell, később lehet külön kapcsolótáblákat létrehozni objektumtípusonként.

## 3.6 Entity esetén a source kapcsolatot mention szinten kezeljük

### Döntés

Az `entities` tábla maradjon normalizált név- és típusrekord. A forráshivatkozás elsődleges helye az `entity_mentions` legyen.

### Indok

Egy entitás kanonikus rekordja gyakran több előfordulásból áll össze. Nem szerencsés egyetlen forrást úgy feltüntetni, mintha az egész normalizált entitást önmagában igazolná.

### Megerősítés

Az entity akkor tekinthető forrással alátámasztottnak, ha van legalább egy hozzá tartozó `entity_mentions` rekord, amely:

- dokumentumra mutat,
- oldalra vagy chunkra mutat,
- opcionálisan `source_reference_id`-t is tartalmaz.

## 3.7 Summary itemről most döntsünk

### Probléma

A séma opcionálisan kezeli a `summary_items` táblát.

### Javasolt döntés

MVP-1-ben vezessük be a `summary_items` táblát, de egyszerű formában.

### Indok

Az ügyösszefoglaló is AI-output. Ha csak exportált szövegként kezeljük, gyengébb lesz:

- a source traceability,
- a human review,
- a javíthatóság,
- a részleges exportálhatóság.

### Minimális mezők

- `id`
- `case_id`
- `summary_type`
- `title`
- `body_text`
- `created_by_analysis_run_id`
- `review_status`
- `created_at`
- `updated_at`

Plusz:

- `summary_item_sources`

## 4. Javasolt egyszerűsítések

## 4.1 Ne legyen túl sok ENUM az első migrációban

### Javaslat

Az első implementációban használjunk `text` + `CHECK` constraint megoldást.

### Indok

Az MVP-ben még változhatnak:

- review státuszok,
- claim típusok,
- event típusok,
- document típusok,
- run típusok.

A PostgreSQL ENUM módosítása nehézkesebb, ezért korai fázisban a `CHECK` praktikusabb.

## 4.2 Ne implementáljunk trigger-alapú auditot az első körben

### Javaslat

Az első MVP-ben explicit alkalmazásszintű audit írás legyen:

- `audit_events` tábla,
- append-only JSONL log.

### Indok

A trigger-alapú audit hasznos lehet később, de az elején bonyolítja:

- migrációkat,
- tesztelést,
- hibakeresést,
- fejlesztési sebességet.

## 4.3 A jogosultsági modell maradjon egyszerű

### Javaslat

Maradjon:

- `users.role` globális szerepkör,
- `case_users.case_role` ügyön belüli szerepkör.

### Indok

Ez elég az MVP-hez, de később bővíthető részletes permission táblákkal.

## 5. Javasolt megerősítések

## 5.1 Kötelező `case_id` minden case-bound táblán

### Döntés

Tartsuk meg a denormalizált `case_id` mezőt azokban a táblákban is, ahol dokumentumon vagy chunkon keresztül levezethető lenne.

### Indok

Ez gyorsítja és egyszerűsíti:

- jogosultsági szűrést,
- exportot,
- audit lekérdezést,
- case archiválást,
- hibakeresést.

## 5.2 Forrásvalidáció legyen külön pipeline-lépés

### Javaslat

Minden AI-output után fusson source validation:

1. létezik-e a hivatkozott source reference,
2. a source reference azonos ügyhöz tartozik-e,
3. a quote megtalálható-e a chunkban vagy oldalszövegben,
4. a generated object rendelkezik-e kötelező source kapcsolattal.

### Indok

Ez közvetlen kontroll a hallucination és source mismatch kockázatra.

## 5.3 Export előtt legyen review és source gate

### Javaslat

Export alapértelmezett szabály:

- csak `verified` objektum,
- csak valid source kapcsolat,
- minden exportált objektum szerepeljen az `export_items` táblában.

### Indok

Ez megakadályozza, hogy félkész AI-javaslatok véletlenül hivatalosnak tűnő reportba kerüljenek.

## 6. Megvalósítás előtti döntési lista

SQL DDL előtt ezekről érdemes végleg dönteni:

1. Bevezetjük-e most a `summary_items` táblát? Javaslat: igen.
2. Bevezetjük-e most a `version_no`, `is_current`, `superseded_by_id` mezőket page/chunk szinten? Javaslat: igen.
3. Marad-e az `object_type + object_id` minta audit/review/export esetén? Javaslat: igen, alkalmazásszintű validációval.
4. `ENUM` vagy `text + CHECK` legyen az első migrációban? Javaslat: `text + CHECK`.
5. Legyen-e trigger-alapú audit az MVP-ben? Javaslat: nem, explicit audit service legyen.
6. Kötelező legyen-e export előtt a `verified` státusz? Javaslat: alapértelmezetten igen, admin override csak naplózással.

## 7. Javasolt frissítés a `03_database_schema_v1.md` dokumentumhoz

A fenti review alapján a fő séma dokumentumban érdemes módosítani vagy pontosítani:

1. `document_pages`: `version_no`, `is_current`, `superseded_by_id` hozzáadása.
2. `document_chunks`: `version_no`, `is_current`, `superseded_by_id` hozzáadása.
3. `summary_items` átemelése opcionálisból MVP-javasolt táblává.
4. `summary_item_sources` hozzáadása.
5. AI-output táblákhoz `source_validation_status` mező hozzáadása.
6. `source_references` constraint pontosítása: page/chunk kötelező, kivéve metadata source.
7. Export szabály pontosítása: default `verified_only`.

## 8. Rövid konklúzió

A séma megvalósításra alkalmas, de SQL előtt érdemes egy kisebb v1.1 pontosítást elvégezni.

A legnagyobb értéket három módosítás adná:

1. page/chunk verziózás,
2. summary itemek első osztályú kezelése,
3. explicit source validation státusz az AI-outputokon.

Ezek nem növelik túl a komplexitást, viszont sokkal erősebbé teszik az auditálhatóságot és a későbbi újrafeldolgozhatóságot.
