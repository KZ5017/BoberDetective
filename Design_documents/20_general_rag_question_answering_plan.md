# 20. Altalanos lokalis RAG kerdezo terv

## 1. Cel

Ez a dokumentum a kovetkezo nagyobb tervezesi es implementacios szeletet rogziti:
egy altalanos, lokalis, kijelolt iratanyagra korlatozott RAG kerdezo feluletet.

A cel nem a jelenlegi `search_findings` vagy `Teljes iratfeldolgozas` workflow kivaltasa.
Azok tovabbra is celzott, forrasvalidalt, munkalista-alapu nyomozati/iratfeldolgozasi eszkozok.

Az uj szelet celja:

```text
A felhasznalo termeszetes nyelven kerdezhet a kijelolt iratanyagrol, a rendszer pedig csak az adott lokalis korpusz alapjan valaszol.
```

## 2. Mi ez es mi nem

### Ez

- altalanos kerdes-valasz felulet,
- lokalis RAG workflow,
- kijelolt ugy / dokumentumhalmaz / kesobbi jogszabalyi korpusz szerinti valaszadas,
- valasz generalasa a visszakeresett forrasreszek alapjan,
- belso audit: milyen forrasreszekbol dolgozott a valasz,
- opcionalis forrasmegjelenites a felhasznalonak.

### Nem ez

- nem strukturalt talalatjelolt-generalo,
- nem `research_finding` munkalista,
- nem automatikus jogi dontes,
- nem bunosseg, felelosseg, kockazat vagy jogi minosites megallapitas,
- nem forras nelkuli chatbot,
- nem a modell belso tudasara epulo valaszado.

## 3. Kulonbseg a jelenlegi workflow-khoz kepest

`search_findings`:

- forrasreszekbol strukturalt kutatasi talalatokat hoz letre,
- quote-validaciot es source-reference-et hasznal,
- munkalistaba ment,
- talalatbol emberi dontessel strukturalt objektum keszulhet.

`Teljes iratfeldolgozas`:

- egy kijelolt dokumentum oldaltartomanyabol elokeszito szemely-keresesi munkalista-elemeket hoz letre,
- forrasbizonyitekot backend validacioval epit,
- fokuszokat ad at a munkapad kereseseihez.

Altalanos RAG kerdezo:

- egy kerdesre ad osszefoglalo valaszt,
- nem hoz letre automatikusan `research_finding` vagy review objektumot,
- a felhasznalo elso korben nem talalatlistat kezel, hanem valaszt kap,
- a rendszer a hatterben megorzi a felhasznalt forrasreszeket audit es ellenorzes celjabol.

## 4. Alapelv

Az altalanos RAG kerdezo sem lehet szabad chatbot.

Kotelezo alapelv:

```text
Nincs forras -> nincs valasz.
```

Pontosabban:

- ha nincs elegendo relevans forras, a rendszer ezt mondja ki,
- a modell nem hasznalhat kulso tudast,
- a modell nem potolhat hianyzo adatot,
- a valasz mindig a kijelolt korpuszra vonatkozik,
- a hasznalt forrasreszeket backend oldalon meg kell orizni.

## 5. Javasolt felulet

Az altalanos RAG kerdezo sajat munkafeluleten jelenjen meg, ne a mar
meglevo `Ugy munkapad`, `Teljes iratfeldolgozas` vagy `Irat rendezo` panelekbe
beagyazva.

```text
Altalanos iratkerdezo
```

Indok:

- hosszabb, egybefuggo valaszokra szamitunk,
- a valasz olvashatosaga nagy, nyugodt feluletet igenyel,
- a modul mentalisan mas, mint a munkalista-alapu kutatasi talalat workflow,
- a mostani oldalsavos munkafelulet alkalmas uj modul felvetelere anelkul,
  hogy a tobbi munkafeluletet szetfeszitene.

Elhelyezes a munkafeluletek kozott:

```text
Ügy munkapad | Teljes iratfeldolgozás | Általános iratkérdező | Audit napló
```

Elso feluleti elemek:

- nagy kerdes beviteli mezo,
- forraskor valasztasa:
  - teljes ugy,
  - egy dokumentum,
  - egy iratgyujtemeny,
  - kesobb tobb dokumentum vagy tobb iratgyujtemeny,
  - kesobbi kulon korpuszok, peldaul jogszabalyi korpusz,
- retrieval strategia:
  - keyword,
  - semantic,
  - hybrid,
- valasz reszletessege:
  - rovid,
  - reszletes,
- opcionális kapcsolo:
  - forrasok megjelenitese.

Elsodleges UX-elv:

- a felhasznalo kerdez,
- a rendszer egy dedikalt valaszpanelben megjeleniti az aktualis valaszt,
- a kovetkezo kerdes alapertelmezetten felulirja az elozo ideiglenes valaszt,
- a valasz csak explicit `Valasz mentese` felhasznaloi muvelettel valik
  tartos `rag_answers` rekordda.

Ez megelozi az adatbazis-szemetelest, mikozben a hasznos valaszok kulon
megorizhetok es kesobb visszakereshetok.

### 5.1 Aktualis implementalt allapot, 2026-06-07

Az elso altalanos iratkerdezo szelet mar nem csak terv, hanem aktiv
backend/frontend workflow.

Implementalt elemek:

- kulon `Általános iratkérdező` munkafelület,
- migracio `0044_rag_answers` a mentett valaszokhoz,
- migracio `0045_limit_rag_answer_modes`, amely az aktiv valaszmodokat `short` es `detailed` ertekekre szukiti,
- `rag_query` analysis run tipus,
- `RagAnswerModel`,
- `app/schemas/rag.py`,
- `app/services/rag.py`,
- `app/api/v1/rag.py`,
- router regisztracio,
- frontend kerdes/futtatas/mentes/listazas/reszlet/torles workflow,
- `tests/test_rag.py`.

Aktiv API-k:

```text
POST   /api/v1/cases/{case_id}/rag/query
POST   /api/v1/cases/{case_id}/rag/runs/{analysis_run_id}/save-answer
GET    /api/v1/cases/{case_id}/rag/answers
GET    /api/v1/cases/{case_id}/rag/answers/{answer_id}
DELETE /api/v1/cases/{case_id}/rag/answers/{answer_id}
```

Aktualis valaszmodok:

```text
short
detailed
```

A `source_focused` es `strict_source` kiserleti valaszmodok ki lettek vezetve,
mert elo teszteken a jelenlegi lokalis modellnel nem javitottak a valasz
forrashuseget, hanem egyes esetekben magabiztosabb teves szerep- vagy
elkovetoi allitasokat eredmenyeztek.

Aktualis alapertelmezesek:

```text
retrieval_strategy = hybrid
max_chunks default = 45
max_chunks hard cap = 90
```

Tobbdokumentumos RAG valaszgeneraltas:

1. a retrieval tovabbra is relevancia szerint valasztja ki a chunkokat,
2. a kivalasztott chunkok dokumentum/page/chunk sorrendbe rendezodnek,
3. a chunkok dokumentumonkent csoportosulnak,
4. minden hozzajarulo dokumentumhoz kulon reszvalasz keszul,
5. a vegso valasz ezekbol a dokumentumszintu reszvalaszokbol keszul.

Egyetlen dokumentum eseten a rendszer egy kozvetlen LLM valaszt ker, nincs
felesleges reszvalasz-szintezes.

A frontend a `retrieval_metadata.document_answer_count` alapjan jelzi, hany
dokumentumszintu reszvalaszbol keszult a vegso valasz.

JSON parser megjegyzes:

- az altalanos RAG valasz parser tovabbra is minimalis JSON objektumot var,
- a lokalis modell gyakori JSON-hibai miatt van celzott fallback helyreallitas,
- ez nem jelent forrasvalidacio-megkerulest: a backend altal hasznalt forraslista
  es analysis run inputok tovabbra is a visszakeresett chunkokbol jonnek.

## 6. Elso kisebb lepes: iratgyujtemeny es forraskor-kijeloles

Mielott az altalanos RAG kerdezo konkret valaszado pipeline-ja elkeszulne, eloszor a forraskor kijelolesehez kell egy rugalmas, felhasznalobarat rendezo reteg.

Jelenlegi kiindulopont:

- az ugy egy nagy iratgyujtobe varja az importalt iratokat,
- a korabbi kotott dokumentumkategoria/taxonomia irany ki lett vezetve,
- nem akarunk kotelezo adminisztraciot vagy szakmai besorolasi terhet adni a felhasznalonak,
- 5000+ iratnal megis kell valamilyen szabad rendezes es forraskor-kijeloles.

### 6.1 Fogalom

Javasolt fogalom:

```text
Iratgyujtemeny
```

Alternativ UI-nevek kesobb:

- Forrasmappa,
- Iratmappa,
- Gyujtemeny,
- Forraskosar.

Ebben a tervben az `iratgyujtemeny` kifejezest hasznaljuk.

### 6.2 Mit jelent az iratgyujtemeny

Az iratgyujtemeny:

- felhasznalo altal szabadon letrehozhato rendezo reteg,
- mappaszeru UI-elmenyt ad,
- segiti a vizualis attekintest,
- segiti a forraskor gyors kijeloleset,
- nem szakmai dokumentumtaxonomia,
- nem irattipus,
- nem jogi vagy nyomozati besorolas,
- nem modosítja az iratbol keszulo objektumok validacios vagy merge logikajat.

### 6.3 Many-to-many modell

Fontos dontes:

```text
Egy irat tobb iratgyujtemenyben is szerepelhet.
```

Ez nem jelent iratduplikalast.
Az eredeti dokumentum tovabbra is egyetlen dokumentumrekord es egyetlen fizikai irat.
Az iratgyujtemeny csak tagsagi kapcsolatot tart fenn.

Indok:

- ugyanaz az irat tobb munkaszempontbol is relevans lehet,
- peldaul `Autok`, `Helyszinek`, `Elso korben fontos`, `RAG tesztkorpusz`,
- a felhasznalo nem kenyszerul egyetlen "helyes" mappa kivalasztasara,
- a forraskor-kepzes kesobb rugalmasabb lesz.

### 6.4 Forraskor feloldasa

Az iratgyujtemeny nem forras maga.

A valodi forras tovabbra is:

```text
document -> page -> chunk -> source_reference
```

Az iratgyujtemeny csak source-selection layer.

Ha a felhasznalo egy vagy tobb iratgyujtemenyt jelol ki, a backend ezt mindig egyedi aktiv dokumentumhalmazza oldja fel:

```text
selected_collection_ids -> document_ids DISTINCT -> active documents only
```

Pelda:

```text
Autok: A, B, C
Fontos: B, C, D

Tenyeges forraskor:
A, B, C, D
```

Nem:

```text
A, B, B, C, C, D
```

### 6.5 Tobbszoros gyujtemeny-kijeloles

Tobb iratgyujtemeny egyideju kijeloleset engedni kell.

Ez a felhasznalonak rugalmas:

- "Autok" + "Elso korben fontos",
- "Kihallgatasok" + "2024",
- "RAG tesztkorpusz" + "Helyszinek".

A backend oldalon a deduplikacio miatt nem keletkezhet:

- duplikalt chunk retrieval,
- tobbszoros LLM kontextus ugyanarra az iratra,
- mestersegesen felfujt talalati lista.

### 6.6 UI visszajelzes

Tobb gyujtemeny kijelolesenel erdemes mutatni:

```text
3 iratgyujtemeny kivalasztva
127 egyedi aktiv irat a forraskorben
```

Kesobbi, nem elso koros kiegeszites:

```text
9 irat tobb kivalasztott gyujtemenyben is szerepel
```

### 6.7 Korlatozasok

Elso javasolt rendszerkorlat:

- legfeljebb 500 iratgyujtemeny / ugy,
- tagsagok szama gyakorlatilag a dokumentumszamhoz igazodik,
- az iratgyujtemeny-nevek ugyon belul legyenek egyediek vagy UI-szinten figyelmeztetettek.

A "korlatlan" felhasznaloi erzet megmaradhat, de a backendnek legyen vedokorlat.

### 6.8 Nem oroklodik at objektumokra

Az iratgyujtemeny tagsag nem oroklodik:

- kutatasi talalatokra,
- szemely munkalista-elemekre,
- claim/entity/event/missing item objektumokra,
- ellentmondasjeloltekre,
- review statuszra,
- source validation statuszra.

Egy `Autok` iratgyujtemenybol szarmazo objektum kesobb szabadon osszevonhato egy `Helyszinek` gyujtemenybol szarmazo objektummal, ha a forrasok es az emberi dontes ezt tamasztjak ala.

### 6.9 Javasolt elso adatmodell-vazlat

Elso gondolati modell:

```text
document_collections
- id
- case_id
- name
- description
- color
- sort_order
- created_by
- created_at
- updated_at

document_collection_memberships
- collection_id
- document_id
- added_by
- added_at
```

Ezt a kovetkezo konkret tervezesi korben kell reszletesen kidolgozni:

- torlesi szabalyok,
- audit esemenyek,
- API-k,
- frontend dokumentumlista integracio,
- tomeges hozzaadas/eltavolitas,
- import utani alapallapot,
- collection-scope index readiness.

### 6.10 Konkret elso lepcsos terv

Ez a fejezet mar a megvalositas elotti konkret terv.
Celja, hogy az altalanos RAG kerdezo elott legyen egy stabil, szabad forraskor-kijelolesi reteg.

Az elso lepcso neve:

```text
Iratgyujtemenyek
```

Felhasznaloi cel:

- 5000+ iratot is lehessen emberi modon csoportositani,
- a csoportositas ne legyen kotelezo,
- a csoportositas ne legyen szakmai/taxonomiai besorolas,
- a gyujtemenyek kesobb kozvetlen forraskorkent hasznalhatok legyenek RAG kerdeshez, keresesi talalatokhoz, index readiness ellenorzeshez es mas source-selection workflow-khoz.

### 6.11 Adatmodell reszletek

#### `document_collections`

Javasolt oszlopok:

```text
id uuid primary key
case_id uuid not null references cases(id)
name text not null
description text null
color text null
sort_order integer not null default 0
created_by_user_id uuid not null references users(id)
created_at timestamptz not null
updated_at timestamptz not null
```

Constraintok:

- `name` ne legyen ures vagy csak whitespace,
- `name` max hossza: 120 karakter,
- `description` max hossza: 1000 karakter,
- `color` opcionális, elso korben csak egyszeru hex forma: `#RRGGBB`,
- `sort_order >= 0`,
- ugyon belul egyedi normalizalt nev javasolt.

Az egyedi nevnel ket lehetoseg van:

1. DB-szintu egyedi `case_id + lower(name)`.
2. Service-szintu ellenorzes, hogy kesobb konnyebb legyen lokalizalt/normalizalt nevlogikat cserelni.

Elso korben a DB-szintu vedelmet tartom jobbnak, mert egyszerubb es stabilabb.

#### `document_collection_memberships`

Javasolt oszlopok:

```text
collection_id uuid not null references document_collections(id)
document_id uuid not null references documents(id)
added_by_user_id uuid not null references users(id)
added_at timestamptz not null
primary key (collection_id, document_id)
```

Constraintok es indexek:

- `collection_id, document_id` primer kulcs, igy ugyanaz az irat nem szerepelhet ketszer ugyanabban a gyujtemenyben,
- index `document_id` szerint, hogy egy dokumentum gyujtemenyei gyorsan lekerhetok legyenek,
- a service ellenorizze, hogy a dokumentum ugyanahhoz az ugyhoz tartozik, mint a gyujtemeny.

Torlesi szabaly:

- gyujtemeny torlesekor a membership sorok torlodhetnek cascade-del,
- dokumentum teljes fizikai torlese csak korai discard esetben letezik; ilyenkor a membership sorok torlodhetnek cascade-del,
- dokumentum `excluded` vagy `archived` allapotba helyezese nem torli a membershipet.

### 6.12 Rendszerkorlatok

Elso vedokorlatok:

```text
max 500 document_collections / case
max 5000 document_ids egy bulk membership muveletben
max 5000 resolved active documents egy collection-scope forraskorben elso korben
```

A harmadik limit nem feltetlen vegleges technikai plafon, hanem elso biztonsagi korlat.
Ha a felhasznalo 5000 folotti forraskort valaszt, a UI jelezze, hogy a muvelethez szukebb gyujtemeny vagy konkret dokumentumkijeloles ajanlott.

### 6.13 Service-szabalyok

Backend service reteg javasolt neve:

```text
app/services/document_collections.py
```

Alapmuveletek:

- gyujtemeny letrehozasa,
- gyujtemeny atnevezese/leiras/szin/sorrend modositasa,
- gyujtemeny torlese,
- dokumentumok hozzaadasa gyujtemenyhez,
- dokumentumok eltavolitasa gyujtemenybol,
- dokumentum gyujtemenyeinek listazasa,
- gyujtemenyek listazasa darabszamokkal,
- gyujtemeny forraskor feloldasa deduplikalt aktiv dokumentumhalmazza.

Fontos service invariant:

```text
collection scope mindig dokumentumhalmazza oldodik fel, es csak utana megy tovabb retrieval/index/analysis iranyba.
```

Ez megakadalyozza, hogy a gyujtemeny mint "forras" osszekeveredjen a tenyleges forrasreferencia-modellel.

### 6.14 Forraskor-feloldo helper

Kesobb tobb workflow is hasznalni fogja:

- altalanos RAG kerdezo,
- `search_findings`,
- index readiness,
- background indexing,
- esetleg teljes iratfeldolgozas kesobbi tobbdokumentumos valtozata.

Ezert legyen kozponti helper:

```text
resolve_document_scope(
  case_id,
  source_mode,
  document_ids=None,
  collection_ids=None
) -> ResolvedDocumentScope
```

Javasolt visszateres:

```text
ResolvedDocumentScope
- source_mode
- requested_document_ids
- requested_collection_ids
- resolved_document_ids
- active_document_count
- inactive_document_count
- duplicate_membership_count
- warnings
```

Elso source mode-ok:

```text
case
documents
collections
```

Kesobb:

```text
corpus
```

Szabalyok:

- `case`: minden aktiv dokumentum,
- `documents`: a megadott dokumentumok kozul csak az aktivak,
- `collections`: a megadott gyujtemenyek dokumentumai, deduplikalva, csak aktivak,
- ha nincs aktiv dokumentum, a workflow ne induljon el,
- a valasztott collection id-ket es a feloldott dokumentum id-ket audit/provenance celra el kell menteni.

### 6.15 API terv

Javasolt API-k:

```text
GET    /api/v1/cases/{case_id}/document-collections
POST   /api/v1/cases/{case_id}/document-collections
PATCH  /api/v1/cases/{case_id}/document-collections/{collection_id}
DELETE /api/v1/cases/{case_id}/document-collections/{collection_id}

GET    /api/v1/cases/{case_id}/document-collections/{collection_id}/documents
POST   /api/v1/cases/{case_id}/document-collections/{collection_id}/documents
DELETE /api/v1/cases/{case_id}/document-collections/{collection_id}/documents

POST   /api/v1/cases/{case_id}/document-collections/resolve-scope
```

`POST .../{collection_id}/documents` payload:

```json
{
  "document_ids": ["..."]
}
```

`DELETE .../{collection_id}/documents` payload:

```json
{
  "document_ids": ["..."]
}
```

`resolve-scope` payload:

```json
{
  "source_mode": "collections",
  "collection_ids": ["..."]
}
```

`resolve-scope` valasz:

```json
{
  "source_mode": "collections",
  "requested_collection_ids": ["..."],
  "resolved_document_count": 127,
  "inactive_document_count": 3,
  "duplicate_membership_count": 9,
  "document_ids": ["..."],
  "warnings": []
}
```

Megjegyzes:

- a `document_ids` lista nagy lehet; frontend elso korben eleg lehet a count + preview,
- analysis API-khoz nem feltetlen kell a teljes listat visszaadni, de provenance szempontbol a backendnek tarolnia kell a feloldott halmazt.

### 6.16 Audit esemenyek

Javasolt audit event tipusok:

```text
document_collection_created
document_collection_updated
document_collection_deleted
document_collection_documents_added
document_collection_documents_removed
document_collection_scope_resolved
```

Audit metadata tartalmazza:

- `case_id`,
- `collection_id`,
- erintett dokumentumok szama,
- bulk muveletnel max elso nehany dokumentum id preview,
- feloldott forraskor darabszamai,
- user id.

Nem kell minden egyes membership sorrol kulon audit event, mert 5000 iratnal ez zajos lenne.
Bulk muveletrol egy osszesitett audit event eleg.

### 6.17 Frontend terv

Első UI hely:

```text
Dokumentumlista / iratok panel
```

Nem az `Általános iratkérdező` belsejebe zarjuk, mert az iratgyujtemeny kesobb mas workflow-khoz is hasznos.

Javasolt elemek:

- bal oldali vagy felso szuro:
  - `Minden aktív irat`,
  - `Gyűjtemények`,
  - `Nincs gyűjteményben`,
- gyujtemenylista:
  - nev,
  - darabszam,
  - szin jelolo,
  - szerkesztes,
  - torles,
- dokumentumkartyakon vagy tablan:
  - gyujtemeny cimkek,
  - `Gyűjteményhez adás`,
  - `Eltávolítás gyűjteményből`,
- tomeges muveletek:
  - kijelolt dokumentumok hozzaadasa gyujtemenyhez,
  - kijelolt dokumentumok eltavolitasa gyujtemenybol,
  - uj gyujtemeny letrehozasa kijeloltekbol.

Elso minimal UI slice:

1. gyujtemenylista,
2. uj gyujtemeny letrehozasa,
3. dokumentumok kijelolese,
4. kijeloltek hozzaadasa gyujtemenyhez,
5. gyujtemeny szerinti dokumentumszures.

Későbbi UI:

- drag/drop mappaszeru rendezes,
- szinek,
- sorrend modositas,
- "tobb gyujtemenyben szereplo iratok" nezet,
- gyujtemenyek keresese.

### 6.18 Index readiness collection scope mellett

Az iratgyujtemeny nem hoz letre kulon indexet.

Az index tovabbra is dokumentum/chunk szinten mukodik.

Collection scope readiness:

1. collection_ids -> resolved active document_ids,
2. a meglévő chunk index status logika lefut ezen a dokumentumhalmazon,
3. a UI ezt mutatja:

```text
2 gyűjtemény kiválasztva
127 egyedi aktív irat
12 840 szövegrész
12 110 indexelve
730 hiányzik
```

Ez megelozi, hogy az altalanos RAG kerdezo semantic/hybrid modban felkeszuletlen forraskorrel induljon.

### 6.19 Import utani alapallapot

Az importalt iratok alapbol ne keruljenek kotelezo gyujtemenybe.

Alapnezet:

```text
Minden aktív irat
```

Opcionális kesobbi segednezet:

```text
Nincs gyűjteményben
```

Ez segit rendet rakni, de nem kotelezi a felhasznalot adminisztraciora.

### 6.20 Implementacios sorrend ehhez a lepcsohoz

Javasolt szeletek:

1. DB migration es SQLAlchemy modellek.
2. Pydantic schemak.
3. Service reteg:
   - CRUD,
   - membership bulk add/remove,
   - scope resolver.
4. API router.
5. Audit eventek.
6. Backend tesztek:
   - many-to-many tagsag,
   - duplikalt add idempotens vagy tiszta hiba,
   - mas ugy dokumentuma nem adhato hozza,
   - torles membership cleanup,
   - collection scope deduplikacio,
   - inactive dokumentum kiszurese.
7. Frontend minimal UI:
   - gyujtemenylista,
   - letrehozas/szerkesztes/torles,
   - dokumentumok kijelolese es bulk add/remove,
   - gyujtemeny szerinti szures.
8. Index readiness endpointok es analysis source-scope integracio bovites.
   - **Implementalva, 2026-06-02:** `search_findings` mar tud `source_mode=collection` + `collection_id` forraskorrel futni; a backend a gyujtemenyt deduplikalt aktiv dokumentumhalmazza oldja fel.
   - **Implementalva, 2026-06-02:** chunk index status es background indexing is elfogad `collection_id` scope-ot, es ugyanazt az aktiv dokumentumhalmazt hasznalja.
   - **Implementalva, 2026-06-02:** a frontend `Elemzes` panelen az `Iratgyűjtemény` forraskor keresheto valasztoval elerheto.
9. Altalanos RAG kerdezo tervezes folytatasa mar erre a forraskor-retegre epulve.

### 6.21 Kifejezetten nem elso lepcso

Nem elso lepcso:

- jogszabalyi korpusz import,
- kulon korpusz adattar,
- drag/drop fa-struktura,
- nested mappak,
- automatikus LLM-alapu iratgyujtemeny-javaslat,
- gyujtemeny tagsag oroklitese review objektumokra,
- gyujtemenyekbol automatikus szakmai kovetkeztetes.

### 6.22 Iratgyujtemeny backend/API/frontend contract v1

Ez a contract az elso implementalhato iratgyujtemeny-szelet szerzodese.
Celja, hogy a kovetkezo munka mar ne otleteles, hanem kontrollalt backend/frontend implementacio legyen.

Implementacios allapot:

- backend DB/API/service/schema slice elkeszult migracioval `0043_document_collections`,
- endpointok es scope-resolve contract bekerult az aktiv API-ba,
- celzott backend tesztek lefutottak,
- frontend v1 szelet elkeszult az `Ügy munkapad` iratlistaja mellett: gyujtemeny letrehozas/torles, forraskor elonezet, fuggetlen celgyujtemeny-valaszto az `Iratok` panelen, egyedi kijeloles, osszes lathato kijelolese, kijeloles torlese es kijeloltek bulk hozzaadasa.

#### 6.22.1 DB contract

Uj migracio:

```text
0043_document_collections
```

Uj tablak:

```text
document_collections
document_collection_memberships
```

`document_collections`:

```text
id uuid primary key
case_id uuid not null references cases(id) on delete cascade
name text not null
description text null
color text null
sort_order integer not null default 0
created_by_user_id uuid not null references users(id)
created_at timestamptz not null
updated_at timestamptz not null
```

DB constraintok:

```text
ck_document_collections_name_not_blank
ck_document_collections_name_length
ck_document_collections_description_length
ck_document_collections_color_hex
ck_document_collections_sort_order_non_negative
uq_document_collections_case_name_lower
```

Megjegyzes:

- PostgreSQL-ben az egyedi kisbetus nevhez expression unique index javasolt: `case_id, lower(name)`.
- Ha ez Alembic/SQLAlchemy oldalon kenyelmetlen, akkor `normalized_name text not null` oszlop is elfogadhato. Elso implementacional a tisztabb DB-vedelem a fontos, nem a szepsegverseny.

`document_collection_memberships`:

```text
collection_id uuid not null references document_collections(id) on delete cascade
document_id uuid not null references documents(id) on delete cascade
added_by_user_id uuid not null references users(id)
added_at timestamptz not null
primary key (collection_id, document_id)
```

Indexek:

```text
ix_document_collection_memberships_document_id
ix_document_collection_memberships_collection_id
```

Service invariant:

```text
A membership csak akkor hozhato letre, ha a document.case_id == collection.case_id.
```

Ezt DB foreign key onmagaban nem garantalja, ezert service- es teszt-szabaly.

#### 6.22.2 Pydantic schema contract

Javasolt schema-k:

```text
DocumentCollectionCreate
- name: str, max 120
- description: str | None, max 1000
- color: str | None

DocumentCollectionUpdate
- name: str | None
- description: str | None
- color: str | None
- sort_order: int | None

DocumentCollectionRead
- id
- case_id
- name
- description
- color
- sort_order
- document_count
- active_document_count
- created_by_user_id
- created_at
- updated_at

DocumentCollectionList
- data: list[DocumentCollectionRead]

DocumentCollectionMembershipChangeRequest
- document_ids: list[UUID]

DocumentCollectionMembershipChangeResponse
- collection_id
- requested_count
- added_count / removed_count
- already_present_count / not_present_count
- skipped_count
- skipped_reasons
- active_document_count
- total_document_count

DocumentCollectionScopeResolveRequest
- source_mode: Literal["case", "documents", "collections"]
- document_ids: list[UUID] = []
- collection_ids: list[UUID] = []

DocumentCollectionScopeResolveResponse
- source_mode
- requested_document_ids
- requested_collection_ids
- resolved_document_count
- active_document_count
- inactive_document_count
- duplicate_membership_count
- document_ids_preview
- warnings
```

Elso korben a `resolve-scope` valasz ne kuldje vissza kotelezoen mind az 5000 dokumentum id-t a frontendnek.
Legyen eleg:

- darabszam,
- legfeljebb 50 id preview,
- warning lista.

Analysis/backend provenance oldalon viszont a teljes feloldott dokumentumhalmazt a futas input metadatajaban tarolni kell, ha egy workflow ezzel indul.

#### 6.22.3 Service contract

Javasolt file:

```text
app/services/document_collections.py
```

Javasolt exceptionok:

```text
DocumentCollectionError
CaseNotFoundError
DocumentCollectionNotFoundError
DocumentCollectionNameConflictError
DocumentCollectionLimitError
DocumentCollectionMembershipError
DocumentCollectionScopeError
```

Service fuggvenyek:

```text
list_document_collections(db, case_id)
create_document_collection(db, case_id, payload)
update_document_collection(db, case_id, collection_id, payload)
delete_document_collection(db, case_id, collection_id)
list_collection_documents(db, case_id, collection_id)
add_documents_to_collection(db, case_id, collection_id, document_ids)
remove_documents_from_collection(db, case_id, collection_id, document_ids)
list_document_collections_for_document(db, case_id, document_id)
resolve_document_scope(db, case_id, source_mode, document_ids=None, collection_ids=None)
```

Viselkedesi dontesek:

- duplikalt add legyen idempotens: ne hiba, hanem `already_present_count`,
- nem letezo dokumentum vagy mas ugy dokumentuma legyen `skipped` reszletes okkal bulk muveletben,
- ha minden kert dokumentum ervenytelen, a valasz legyen 400,
- remove nem letezo tagsagnal legyen idempotens: `not_present_count`,
- gyujtemeny torlese torli a membership sorokat, de nem torol dokumentumot,
- `excluded` / `archived` dokumentum membershipje megmarad,
- scope resolve csak aktiv dokumentumokat ad vissza,
- scope resolve jelzi, hany inaktiv dokumentum maradt ki,
- collection nev utkozes 409,
- 500 gyujtemeny / ugy limit elerese 400 vagy 409; elso korben 400 eleg.

Bulk membership muveletnel javasolt hard limit:

```text
1 <= len(document_ids) <= 5000
```

#### 6.22.4 API contract

Router:

```text
app/api/v1/document_collections.py
```

Endpointok:

```text
GET    /api/v1/cases/{case_id}/document-collections
POST   /api/v1/cases/{case_id}/document-collections
PATCH  /api/v1/cases/{case_id}/document-collections/{collection_id}
DELETE /api/v1/cases/{case_id}/document-collections/{collection_id}

GET    /api/v1/cases/{case_id}/document-collections/{collection_id}/documents
POST   /api/v1/cases/{case_id}/document-collections/{collection_id}/documents
DELETE /api/v1/cases/{case_id}/document-collections/{collection_id}/documents

GET    /api/v1/cases/{case_id}/documents/{document_id}/collections
POST   /api/v1/cases/{case_id}/document-collections/resolve-scope
```

HTTP status szabalyok:

```text
201 collection letrehozasnal
200 update/list/membership/resolve valaszoknal
204 collection torlesnel
400 validacios/limit/scope hiba
404 case/collection/document not found egyedi muveleteknel
409 nevutkozes
422 Pydantic schema hiba
```

Bulk add/remove esetben nem kell 404-et dobni minden rossz dokumentum miatt.
Ott a response tartalmazza a skipped elemeket.
Ha a `collection_id` vagy `case_id` rossz, az tovabbra is 404.

#### 6.22.5 API response reszletek

`DocumentCollectionRead` peldaval:

```json
{
  "id": "...",
  "case_id": "...",
  "name": "Autok",
  "description": "Autokkal kapcsolatos iratok",
  "color": "#2f80ed",
  "sort_order": 0,
  "document_count": 42,
  "active_document_count": 39,
  "created_by_user_id": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

Membership change response:

```json
{
  "collection_id": "...",
  "requested_count": 4,
  "added_count": 2,
  "already_present_count": 1,
  "skipped_count": 1,
  "skipped_reasons": [
    {"document_id": "...", "reason": "document_not_in_case"}
  ],
  "total_document_count": 12,
  "active_document_count": 10
}
```

Scope resolve response:

```json
{
  "source_mode": "collections",
  "requested_document_ids": [],
  "requested_collection_ids": ["..."],
  "resolved_document_count": 127,
  "active_document_count": 127,
  "inactive_document_count": 3,
  "duplicate_membership_count": 9,
  "document_ids_preview": ["..."],
  "warnings": [
    "3 inaktiv irat kimaradt a forráskörből."
  ]
}
```

#### 6.22.6 Audit contract

Audit eventek:

```text
document_collection_created
document_collection_updated
document_collection_deleted
document_collection_documents_added
document_collection_documents_removed
document_collection_scope_resolved
```

Metadata minimum:

```json
{
  "collection_id": "...",
  "collection_name": "...",
  "requested_count": 100,
  "changed_count": 94,
  "skipped_count": 6,
  "document_ids_preview": ["..."]
}
```

Scope resolve audit csak akkor kotelezo, ha a scope resolve egy kesobbi analysis/RAG/index workflow reszekent fut.
Onallo UI preview `resolve-scope` hivasnal elso korben eleg lehet nem auditolni, hogy ne legyen zajos.

#### 6.22.7 Frontend contract v1

Elso UI integracios pont:

```text
Dokumentumlista panel
```

Elso minimal hasznalhato UX:

1. Gyujtemenylista megjelenitese darabszammal.
2. Uj gyujtemeny letrehozasa.
3. Gyujtemeny atnevezese / leiras / szin modositasa.
4. Gyujtemeny torlese megerosites utan.
5. Dokumentumlista checkbox kijelolessel.
6. Kijelolt dokumentumok hozzaadasa gyujtemenyhez.
7. Kijelolt dokumentumok eltavolitasa gyujtemenybol.
8. Szures egy gyujtemeny dokumentumaira.
9. `Nincs gyűjteményben` nezet.

UI szovegek magyarul:

```text
Iratgyűjtemények
Új gyűjtemény
Gyűjteményhez adás
Eltávolítás gyűjteményből
Nincs gyűjteményben
Minden aktív irat
127 egyedi aktív irat
```

Design elv:

- ne legyen kotelezo a gyujtemenyhasznalat,
- ne legyen landing/marketing jellegu felulet,
- legyen gyors tomeges dokumentumkezeles,
- nagy iratszamnal legyen scan-elheto, suru, munkapad jellegu UI.

#### 6.22.8 Teszt contract

Backend tesztek:

```text
create collection
reject blank name
reject duplicate collection name in same case
allow same collection name in another case
update collection metadata
delete collection removes memberships, not documents
bulk add documents
bulk add duplicate is idempotent
bulk add skips document from another case
bulk remove existing and missing memberships
document lifecycle excluded membership remains
resolve case scope active documents only
resolve documents scope deduplicated active documents only
resolve collections scope deduplicated active documents only
resolve collections reports inactive and duplicate counts
```

Frontend smoke:

```text
create collection
select documents
add selected documents to collection
filter document list by collection
remove selected document from collection
delete collection
verify documents remain
```

#### 6.22.9 Elso implementacios slice javaslat

Az elso implementacios slice legyen backend-first:

1. Migration + modellek.
2. Schemak.
3. Service.
4. API.
5. Backend tesztek.

Csak ezutan jojjon a minimal frontend.

Indok:

- a forraskor-feloldas rendszer-szintu alap,
- az altalanos RAG kerdezo es kesobbi workflow-k erre fognak epulni,
- jobb elobb stabil contractot es teszteket kapni, mint UI-val megelozni a backend szabalyokat.

## 7. Backend pipeline vazlat

Elso tervezett pipeline:

1. Felhasznaloi kerdes fogadasa.
2. Forraskor feloldasa konkret aktiv dokumentumokra / korpuszra.
3. Retrieval:
   - keyword,
   - semantic,
   - hybrid,
   - kesobb rerank.
4. Top forrasreszek osszegyujtese.
5. Opcionális forras-csoportositas vagy kontextus-tomorites.
6. LLM valaszgeneralas.
7. Valasz validalasa:
   - csak JSON vagy strukturalt valaszformatum,
   - nincs forrason kivuli allitas,
   - nincs tiltott jogi/nyomozati dontes.
8. Analysis run mentese:
   - kerdes,
   - retrieval parameterek,
   - hasznalt forrasreszek,
   - modell,
   - prompt verzio,
   - valasz.

## 8. Valasz es forrasok

Felhasznaloi oldalrol az elso verzio lehet egyszeru:

- valasz szovege,
- opcionalis forrasok lenyithato listaja.

Backend oldalon viszont mindig kell:

- hasznalt chunkok listaja,
- retrieval score-ok,
- dokumentum/page/chunk metadata,
- prompt/model metadata,
- analysis run provenance.

Ez kulonosen fontos akkor, ha a felhasznalo nem ker explicit forraslistat, mert hibakereseshez es auditnal akkor is vissza kell kovetni, mibol szuletett a valasz.

## 9. Jogszabalyi korpusz mint kiemelt use case

A teljes magyar jogszabalyi kornyezet egy kesobbi specialis korpusz lehet az altalanos RAG kerdezo alatt.

Ehhez nem eleg a sima dokumentumimport.
Kulon tervezni kell:

- jogszabaly azonosito,
- cim,
- paragrafus,
- bekezdes,
- pont/alpont,
- hatalyossagi datum,
- konszolidalt szoveg verzioja,
- importforras,
- modositasok es idobeli ervenyesseg.

Jogszabalyi valaszadasnal kulon szabaly:

```text
A valasz hatalyossagi allapot nelkul nem tekintheto teljesnek.
```

Ezert a jogszabalyi RAG ne legyen az elso implementacios szelet, hanem az altalanos RAG kerdezo tervezesen belul kulon specializalt corpus-profil.

## 10. Elso tervezesi kerdesek

Mielott implementalni kezdjuk, atfogo terv kell az alabbiakrol:

1. Milyen objektum legyen a RAG valasz?
   - csak `analysis_run` output,
   - kulon `rag_answers` tabla,
   - vagy exportalhato, de nem review-objektum?
2. Hogyan valasszon a felhasznalo forraskort?
3. Kell-e kulon korpusz fogalom az ugyektol fuggetlen tudastarhoz?
4. Mennyi forrast kapjon a modell egy valaszhoz?
5. Kell-e rerank vagy eleg az aktualis hybrid retrieval?
6. Hogyan jelezzuk, ha nincs eleg forras?
7. Megjelenjenek-e a forrasok alapbol, vagy csak lenyithato modon?
8. Milyen prompt-strategia kell a valaszado modulhoz?
9. Hogyan merjuk a valasz minoseget lokalis modellekkel?

### 10.1 Elso dontesi allapot

Az elso atbeszeles alapjan az alabbi iranyt tekintjuk munkahipotézisnek.

#### RAG valasz adatmodell

Legyen kulon `rag_answers` tabla, de csak az explicit mentett valaszoknak.

Kulon kell kezelni:

- ideiglenes RAG valasz: lefut, megjelenik, de alapbol nem lesz tartos
  uzleti objektum,
- mentett RAG valasz: a felhasznalo `Valasz mentese` muvelete utan kerul
  `rag_answers` tablaba.

Minden RAG futas kapjon `analysis_run` provenance nyomot, de ez nem azonos a
mentett valasszal.

Javasolt `rag_answers` mezok:

- `id`,
- `case_id`,
- `analysis_run_id`,
- `question`,
- `answer_text`,
- `answer_mode`,
- `source_scope_json`,
- `used_sources_json`,
- `retrieval_metadata_json`,
- `model_name`,
- `title` opcionálisan,
- `created_at`.

A `rag_answers` nem review objektum, nem `research_finding`, nem claim, es nem
automatikusan ellenorizheto ugyteny. Mentett iratkerdezo-valasz.

#### Forraskor valasztas

Elso implementacios korben tamogatando:

- teljes ugy,
- egy dokumentum,
- egy iratgyujtemeny.

Kesobbi bovites:

- tobb dokumentum,
- tobb iratgyujtemeny.

A tobb iratgyujtemeny deduplikalt dokumentumhalmazza oldodjon fel; ugyanaz az
irat nem jelenhet meg tobbszor a modell bemeneteben.

#### Valasz szerkezete es modja

A valasz reszletessege legyen felhasznalo altal valaszthato.

Aktiv modok:

- `Rovid valasz`,
- `Reszletes valasz`.

Korabbi otlet volt kulon forraskozpontu es szigoru forrasalapu mod, de a live
modelltesztek alapjan ezek a jelenlegi lokalis modellel nem lettek stabilabbak,
ezert az aktiv termekdontes szerint nem kerulnek a valaszthato modok koze.

A valasz minden modban tartalmazzon:

- valaszszoveget,
- backend altal ismert felhasznalt forrasok listajat,
- elegtelen forrashelyzet jelzeset, ha a retrieval nem adott jo alapot.

Nem javasolt szazalekos bizonyossagi pontszam, mert hamis precizitas erzetet
keltheti. Inkabb szoveges allapot kell: peldaul `nincs eleg forras`,
`gyenge forrasalap`, `tobb forras is alatamasztja`.

#### Kapcsolodas a meglevo rendszerhez

Az altalanos iratkerdezo ne valtsa ki es ne kerulje meg a szigoru workflow-kat:

- `search_findings`,
- teljes iratfeldolgozas szemelykeresesi munkalistaja,
- research finding konverzio,
- forrasvalidacio,
- ellentmondasjelolt workflow.

Az iratkerdezo alapveto szerepe:

```text
szabad kerdezes a kijelolt iratanyaghoz, objektumgyartas nelkul
```

Később lehet `Valaszbol kutatasi talalat inditasa` vagy hasonlo muvelet, de ez
nem az elso implementacios szelet resze.

#### Backend contract irany

Javasolt kulon API-felulet, nem a meglevo analysis endpoint tovabbterhelese:

```text
POST /api/v1/cases/{case_id}/rag/query
POST /api/v1/cases/{case_id}/rag/runs/{run_id}/save-answer
GET  /api/v1/cases/{case_id}/rag/answers
GET  /api/v1/cases/{case_id}/rag/answers/{answer_id}
DELETE /api/v1/cases/{case_id}/rag/answers/{answer_id}
```

Az elso endpoint ideiglenes valaszt ad vissza es `analysis_run` nyomot rogzit.
A mentett valasz csak a masodik muvelet utan jon letre.

### 10.2 Backend/API contract v1

Ez a contract az elso implementalhato `Altalanos iratkerdezo` backend szelet
szerzodese. Celja, hogy a kesobbi kodolas soran ne mosodjon ossze:

- az ideiglenes RAG valasz,
- a provenance celra rogzitett `analysis_run`,
- es a felhasznalo altal explicit mentett `rag_answers` rekord.

#### 10.2.1 Fogalmak es enumok

Javasolt `analysis_run.run_type`:

```text
rag_query
```

Javasolt RAG source mode ertekek:

```text
case
document
collection
```

Elso korben ezek legyenek egyes szamu source scope-ok. A tobb dokumentum vagy
tobb gyujtemeny kesobbi bovites legyen:

```text
documents
collections
```

Javasolt valaszmodok:

```text
short
detailed
```

UI megfeleltetes:

- `short` -> `Rovid valasz`,
- `detailed` -> `Reszletes valasz`.

Megjegyzes: a korabban tervezett `source_focused` es `strict_source`
modokat a live modelltesztek alapjan kivezettuk, mert a lokalis modell a
szigorubbnak szant instrukciok mellett nagyobb magabiztossaggal egeszitett ki
nem alatamasztott szerepeket es esemenylancokat. A rendszer jelenleg tudatosan
kevesebbet vallal: ket stabilabb valaszmodot tart meg.

Javasolt retrieval strategia ertekek:

```text
keyword
semantic
hybrid
```

Alapertelmezett:

```text
hybrid
```

#### 10.2.1a Aktualis valaszgeneralasi pipeline

Az aktiv implementacio ket alapelvet kovet:

- a retrieval relevancia alapjan valasztja ki a felhasznalando chunkokat,
- az LLM bemenetet viszont dokumentumlogikai sorrendben kell felepiteni.

Egy dokumentum eseten a RAG valasz egy kozvetlen LLM-hivasbol keszul, a
kivalasztott chunkok dokumentum/page/chunk sorrendjeben.

Tobb dokumentum eseten a valaszgeneralas ketlepcsos:

1. dokumentumonkenti reszvalasz keszul csak az adott dokumentum chunkjaibol,
2. vegso szintezis keszul a dokumentumonkenti reszvalaszokbol.

Ez lassabb lehet, mert N dokumentum eseten N+1 LLM-hivas tortenhet, de
csokkenti annak kockazatat, hogy kulonbozo iratok egymastol fuggetlen
szovegreszei egyetlen kevert promptban hamis esemenylancca alljanak ossze.
Az API `retrieval_metadata.document_answer_count` mezoben jelzi, hany
dokumentum-reszvalaszbol keszult a vegso valasz.

#### 10.2.2 Ideiglenes kerdezes endpoint

```text
POST /api/v1/cases/{case_id}/rag/query
```

Cel:

- kerdes fogadasa,
- forraskor feloldasa,
- retrieval futtatasa,
- LLM valasz generalasa,
- `analysis_run` provenance mentese,
- ideiglenes valasz visszaadasa.

Fontos:

```text
Ez az endpoint nem hoz letre rag_answers rekordot.
```

Javasolt request:

```json
{
  "question": "...",
  "source_mode": "collection",
  "document_id": null,
  "collection_id": "...",
  "answer_mode": "detailed",
  "retrieval_strategy": "hybrid",
  "max_chunks": 30,
  "include_sources": true
}
```

Mezok:

- `question`: kotelezo, nem ures, erdemi kerdes vagy utasitas,
- `source_mode`: kotelezo, `case | document | collection`,
- `document_id`: csak `source_mode=document` eseten kotelezo,
- `collection_id`: csak `source_mode=collection` eseten kotelezo,
- `answer_mode`: opcionális, default `detailed`,
- `retrieval_strategy`: opcionális, default `hybrid`,
- `max_chunks`: opcionális, backend validalt felso korlattal,
- `include_sources`: UI-megjeleniteshez hasznos jelzes; a backend akkor is
  tarolja a felhasznalt forrasokat, ha a UI alapbol nem mutatja oket.

Javasolt response:

```json
{
  "run_id": "...",
  "answer": {
    "answer_text": "...",
    "source_summary": "...",
    "insufficient_source": false,
    "answer_mode": "detailed"
  },
  "source_scope": {
    "source_mode": "collection",
    "case_id": "...",
    "document_id": null,
    "collection_id": "...",
    "resolved_document_count": 12,
    "resolved_chunk_count": 84
  },
  "used_sources": [
    {
      "document_id": "...",
      "document_filename": "...",
      "page_number": 4,
      "chunk_id": "...",
      "chunk_index": 8,
      "quote_preview": "...",
      "retrieval_score": 0.82,
      "retrieval_match_type": "hybrid"
    }
  ],
  "retrieval_metadata": {
    "retrieval_strategy": "hybrid",
    "max_chunks": 30,
    "selected_chunk_count": 8,
    "embedding_model": "...",
    "collection_name": "..."
  },
  "can_save": true
}
```

Megjegyzesek:

- `used_sources` backend altal osszeallitott lista, nem LLM output,
- `quote_preview` nem feltetlenul source-reference quote, hanem a retrieval
  alapjat ado szovegresz roviditett/olvashato elonezete,
- elso korben nem kell karakterpontos quote-validacio ugy, mint
  `research_finding` eseten,
- a valasz forraskotott, de nem allitja magarol, hogy formalizalt bizonyitek.

#### 10.2.3 Mentett valasz letrehozasa

```text
POST /api/v1/cases/{case_id}/rag/runs/{run_id}/save-answer
```

Cel:

- egy korabbi `rag_query` analysis run ideiglenes valaszabol tartos
  `rag_answers` rekord letrehozasa.

Javasolt request:

```json
{
  "title": "Rovid sajat cim",
  "note": "Opcionális felhasznaloi megjegyzes"
}
```

Javasolt response:

```json
{
  "answer_id": "...",
  "run_id": "...",
  "saved": true
}
```

Validacio:

- a `run_id` a megadott ugyhoz tartozzon,
- a run type `rag_query` legyen,
- a run sikeres vagy reszlegesen hasznalhato allapotban legyen,
- ugyanarra a runra elso korben vagy csak egy mentett valasz legyen
  engedelyezett, vagy a backend idempotensen adja vissza a mar letezot.

Javaslat:

```text
Egy rag_query run -> legfeljebb egy rag_answer.
```

Ez egyszerubb UX-et ad, es megelozi, hogy ugyanaz a valasz tobbszor mentodjon.

#### 10.2.4 Mentett valaszok listazasa

```text
GET /api/v1/cases/{case_id}/rag/answers
```

Javasolt query parameterek kesobb:

- `q`,
- `source_mode`,
- `created_from`,
- `created_to`.

Elso korben eleg lehet egyszeru idorendi lista.

Javasolt listaelem:

```json
{
  "id": "...",
  "title": "...",
  "question": "...",
  "answer_mode": "detailed",
  "source_mode": "collection",
  "source_label": "Gyujtemeny neve",
  "created_at": "...",
  "used_source_count": 8
}
```

#### 10.2.5 Mentett valasz reszletei

```text
GET /api/v1/cases/{case_id}/rag/answers/{answer_id}
```

Javasolt response:

```json
{
  "id": "...",
  "case_id": "...",
  "analysis_run_id": "...",
  "title": "...",
  "question": "...",
  "answer_text": "...",
  "answer_mode": "detailed",
  "source_scope": {},
  "used_sources": [],
  "retrieval_metadata": {},
  "model_name": "...",
  "created_at": "..."
}
```

#### 10.2.6 Mentett valasz torlese

```text
DELETE /api/v1/cases/{case_id}/rag/answers/{answer_id}
```

Elso korben soft delete nem feltetlenul szukseges, de audit esemeny igen.

Javasolt audit event:

```text
rag_answer_deleted
```

#### 10.2.7 `rag_answers` tabla v1

Javasolt tabla:

```text
rag_answers
```

Javasolt oszlopok:

```text
id uuid primary key
case_id uuid not null references cases(id)
analysis_run_id uuid not null references analysis_runs(id)
title text null
question text not null
answer_text text not null
answer_mode text not null
source_scope_json jsonb not null
used_sources_json jsonb not null
retrieval_metadata_json jsonb not null
model_name text null
created_at timestamptz not null
created_by_user_id uuid null
```

Javasolt constraint:

```text
unique (analysis_run_id)
```

Indok: ugyanazt az ideiglenes RAG futast ne lehessen tobbszor menteni.

Kesobbi opcionális mezok:

- `note`,
- `updated_at`,
- `deleted_at`,
- `tags_json`.

#### 10.2.8 Analysis run input/output szerkezet

`analysis_runs.input_parameters` tartalmazza:

```json
{
  "question": "...",
  "source_mode": "collection",
  "document_id": null,
  "collection_id": "...",
  "answer_mode": "detailed",
  "retrieval_strategy": "hybrid",
  "max_chunks": 30,
  "resolved_document_ids": ["..."]
}
```

`analysis_runs.output_summary_json` tartalmazza:

```json
{
  "answer_text": "...",
  "source_summary": "...",
  "insufficient_source": false,
  "used_source_count": 8,
  "saved_answer_id": null
}
```

Ha kesobb a valaszt mentik, a save endpoint frissitheti:

```json
{
  "saved_answer_id": "..."
}
```

#### 10.2.9 Validacios alapelvek

- ures vagy tul rovid `question` ne induljon,
- nem letezo dokumentum vagy gyujtemeny 404,
- mas ugyhoz tartozo dokumentum/gyujtemeny 404,
- inaktiv dokumentumok ne keruljenek uj RAG retrieval bemenetbe,
- semantic/hybrid mod csak akkor induljon, ha a valasztott forraskor indexelt,
- ha nincs talalat vagy nincs eleg forras, az endpoint sikeres lehet, de
  `insufficient_source=true` valasszal terjen vissza,
- LLM hibanal a run `failed` legyen, es ne lehessen mentett valaszt letrehozni.

#### 10.2.10 Minimal elso backend szelet

Az elso implementacios szelet tartalmazza:

1. `rag_answers` migration/model/schema.
2. `rag_query` analysis run type.
3. `POST /rag/query` endpoint retrieval nelkuli vagy egyszeru retrieval
   stubbal csak contract smoke-ra, ha szukseges.
4. Valodi retrieval bekotese a mar letezo source-scope resolverrel.
5. LLM valasz generalasa minimal JSON outputtal.
6. `save-answer` endpoint.
7. Mentett valasz lista/reszlet API.
8. Backend tesztek:
   - source scope validacio,
   - successful query creates analysis_run but no rag_answer,
   - save creates one rag_answer,
   - duplicate save idempotens vagy tiltott,
   - inactive/wrong-case sources rejected,
   - insufficient source answer is not treated as failure.

#### Retrieval es prompt irany

Elso korben:

- default retrieval: hybrid,
- nincs kulon bonyolult rerank,
- a forraskor a mar letezo case/document/collection resolverre epuljon,
- a modell csak a backend altal beadott forrasreszekbol dolgozhat,
- a modellnek adott forrasokat a backend tarolja az analysis run input/output
  metadata reszekent,
- a forraslistat ne az LLM talalja ki, hanem a backend kapcsolja a valaszhoz.

Prompt oldalon a cel nem munkalista JSON, hanem forrashu valasz. Megis erdemes
minimalis JSON valaszt kerni, hogy a backend stabilan tudja megjeleniteni:

```json
{
  "answer_text": "...",
  "source_summary": "...",
  "insufficient_source": false
}
```

A konkret forrasok listaja backend oldali adat legyen, mert a backend tudja,
mely dokumentum/chunk reszeket kuldte a modellnek.

### 10.3 Retrieval es prompt contract v1

Ez a szakasz azt rogziti, hogyan lesz egy felhasznaloi kerdesbol:

```text
source scope -> retrieval candidate set -> LLM source packet -> strukturalt RAG valasz
```

Az elso cel nem maximalisan okos RAG pipeline, hanem stabil, forrashu es
auditálhato valaszado workflow.

#### 10.3.1 Source scope feloldas

A `rag/query` endpoint elso lepesben forraskort old fel.

Tamogatott elso source mode-ok:

- `case`: minden aktiv, elemzesre kesz dokumentum az ugyben,
- `document`: egy aktiv, elemzesre kesz dokumentum,
- `collection`: egy iratgyujtemeny deduplikalt aktiv dokumentumhalmaza.

Feloldas utan a backend tarolja:

- kert source mode,
- kert `document_id` vagy `collection_id`,
- feloldott aktiv dokumentum id-k,
- kihagyott inaktiv dokumentumok szama, ha relevans,
- deduplikalt dokumentumszam,
- index-ready allapot semantic/hybrid modhoz.

Fontos:

```text
A gyujtemeny nem forras, csak source-selection layer.
```

A valodi forras tovabbra is:

```text
document -> page -> chunk
```

#### 10.3.2 Retrieval strategia

Elso implementacios alap:

```text
hybrid
```

Indok:

- mar letezik keyword/semantic/hybrid retrieval alap,
- a hybrid jobban toleralja a pontos neves/azonositos kerdeseket es a
  szemantikusabb kerdeseket is,
- nem kell rogton uj rerank reteget epiteni.

Tamogatott modok:

- `keyword`: ha nincs vagy nem kell embedding index,
- `semantic`: ha a forraskor teljesen indexelt,
- `hybrid`: default, ha a forraskor teljesen indexelt.

Semantic/hybrid feltetel:

```text
semantic vagy hybrid mod csak akkor indulhat, ha a valasztott forraskor a
konfiguralt embedding modellel index-ready.
```

Ha nem indexelt:

- UI oldalon blokkolhato,
- backend oldalon 409 vagy validacios hiba,
- vagy kesobb ajanlott `indexeles inditasa` workflow.

Elso korben ne legyen automatikus indexeles a kerdezes kozben.

#### 10.3.3 Kivalasztott forrasok mennyisege

Javasolt elso backend default:

```text
max_chunks = 45
```

Javasolt backend cap:

```text
max_chunks <= 90
```

Indok:

- a jelenlegi lokalis chat modell hosszu kontextust kezel, de a valaszminoseg
  romolhat, ha tul sok zajos chunk kerul be,
- az altalanos iratkerdezo nem batch-es munkalista-gyarto, hanem egyetlen
  valaszhoz gyujt forrasokat,
- a UI kesobb adhat `Forrasreszlet plafon` jellegu beallitast, de elso korben
  eleg lehet egy halado beallitas vagy fix default.

Javasolt chunk rendezesi elv:

1. hybrid vegso pontszam,
2. pontos kifejezes/nev egyezes bonusz, ha van,
3. dokumentumon beluli sorrend csak azonos pontszam kornyeken.

#### 10.3.4 LLM source packet

Az LLM ne kapjon nyers belso objektumokat vagy adatbazis ID-ket, csak
olvashato, cimezett forrasblokkokat.

Javasolt prompt SOURCE forma:

```text
SOURCE:
[source_1]
document: RejtoJ_a_boszorkanymester.pdf
page: 9
chunk: 17
text:
...

[source_2]
document: ...
page: ...
chunk: ...
text:
...
```

A `source_1`, `source_2` csak LLM-bemeneti cimke.

Backend oldali mapping:

```text
source_1 -> document_id/page_id/chunk_id/retrieval metadata
```

Az LLM valaszban nem kell forrasazonositokat kotelezoen visszakerdezni. A
forraslista backend oldalon mar ismert.

#### 10.3.5 System prompt v1

Javasolt magyar system prompt:

```text
Forrashu iratkerdezo komponens vagy.
A SOURCE az egyetlen igazsagforras.
A QUERY a felhasznalo kerdese vagy utasitasa.
Csak a SOURCE alapjan valaszolhatsz.
Ne hasznalj kulso tudast, ne potolj hianyzo adatot, ne feltetelezz.
Ha a SOURCE nem ad eleg alapot a valaszhoz, mondd ki roviden.
Ne allapits meg bunosseget, felelosseget, jogi minositest vagy szemelyes hibaztatast.
Csak ervenyes JSON objektumot adj vissza.
Ne irj magyarazatot, markdown blokkot vagy JSON-on kivuli szoveget.
```

#### 10.3.6 User prompt v1

Javasolt user prompt szerkezet:

```text
QUERY:
{question}

ANSWER_MODE:
{answer_mode}

SOURCE:
{source_blocks}

FELADAT:
Valaszolj a QUERY-re kizarolag a SOURCE alapjan.
Ha nincs eleg forras, ne talalj ki valaszt.
A valasz legyen magyar nyelvu.
A valaszmodot vedd figyelembe:
- short: rovid, lenyegre toro valasz
- detailed: reszletesebb, de tovabbra is forrashu valasz
```

#### 10.3.7 LLM JSON output v1

Minimalis, stabil valaszforma:

```json
{
  "answer_text": "...",
  "source_summary": "...",
  "insufficient_source": false
}
```

Mezok:

- `answer_text`: a felhasznalonak megjelenitendo valasz,
- `source_summary`: rovid magyar osszefoglalo arrol, milyen forrasalapbol
  szuletett a valasz,
- `insufficient_source`: `true`, ha a SOURCE alapjan nincs eleg biztos valasz.

Javasolt kesobbi bovites, nem elso kor:

```json
{
  "answer_text": "...",
  "source_summary": "...",
  "insufficient_source": false,
  "follow_up_questions": ["..."],
  "limitations": ["..."]
}
```

Elso korben a `follow_up_questions` es `limitations` ne legyen kotelezo, mert
feleslegesen noveli a modell JSON-hibazas es valaszszemeteles eselyet.

#### 10.3.8 `insufficient_source` gyakorlati jelentese

`insufficient_source=true`, ha:

- nincs retrieval talalat,
- a talalatok csak tematikusan lazán kapcsolodnak,
- a forrasok nem tartalmazzak a kerdes megvalaszolasahoz szukseges lenyeget,
- a valasz csak kulso tudassal vagy kovetkeztetessel lenne megadhato.

Ilyenkor az `answer_text` ne legyen ures. Mondjon valami ilyesmit:

```text
A kijelolt forrasok alapjan erre nem talalhato elegendo valasz.
```

Es ha lehet, tegye hozza roviden, mit talalt:

```text
A forrasok csak ... temat erintik, de ... kerdesre nem adnak kozvetlen alapot.
```

Backend oldali szabaly:

- `insufficient_source=true` nem backend hiba,
- az analysis run lehet `succeeded` vagy `completed_with_warning`,
- ilyen valaszt elso korben lehet menteni, mert a "nincs eleg forras" is
  hasznos kutatasi eredmeny lehet.

#### 10.3.9 Forrasmegjelenites

A UI forrasmegjelenitese backend `used_sources` listabol dolgozzon.

Elso megjelenites:

- dokumentumnev,
- oldalszam,
- szovegresz sorszama,
- rovid elonezet,
- lenyithato teljes chunk text.

Nem kell elso korben:

- karakterpontos quote span,
- source-reference objektum,
- claim/finding konverzio,
- kulon forrasvalidacios workflow.

Indok:

Az altalanos iratkerdezo nem munkalista-objektumot gyart, hanem valaszt ad. A
forrasok ellenorizhetoseget meg kell adni, de nem kell ugyanazt a szigoru
forrasvalidacios feluletet raeroltetni, mint a `research_finding` workflow-ra.

#### 10.3.10 Rerank es tomorites

Elso korben:

```text
nincs kulon rerank es nincs elozetes LLM-tomorites
```

Indok:

- a rendszerben mar van mukodo hybrid retrieval,
- a lokalis LLM plusz rerank/tomorites lepesek lassithatjak a kerdezot,
- eloszor a vegpont, adatmodell, menthetoseg es UX stabilitasa a fontos.

Kesobbi bovites:

- lightweight rerank pontos nevek/azonositok alapjan,
- dokumentumon beluli szomszedos chunkok osszefuzese, ha ugyanabbol a
  kontextusbol jonnek,
- LLM elotti extractive context compression,
- jogszabalyi korpusznal kulon hatalyossagi/szakasz-szintu retrieval.

#### 10.3.11 Minimal tesztelheto retrieval/prompt slice

Elso backend tesztek:

1. `case` scope keyword query visszaad source packetet.
2. `document` scope csak a kijelolt dokumentumbol valaszt forrast.
3. `collection` scope deduplikalt aktiv dokumentumokbol valaszt forrast.
4. semantic/hybrid nem indul index-ready nelkul.
5. LLM JSON parse hiba failed run.
6. `insufficient_source=true` sikeres, mentheto valasz.
7. `used_sources` backend mapping nem az LLM valaszbol szarmazik.

### 10.4 Minimal backend implementacios checklist v1

Ez a lista mar a konkret elso backend szeletet bontja fajlokra es lepesekre.
Celja, hogy a kovetkezo implementacios kor kontrollalt legyen, es ne keverje
ossze az altalanos RAG kerdezot a meglevo `search_findings` workflow-val.

> **Implementacios allapot, 2026-06-07:** az elso backend/frontend foundation
> szelet elkeszult: `0044_rag_answers`, `0045_limit_rag_answer_modes`,
> `RagAnswerModel`, `app/schemas/rag.py`, `app/services/rag.py`,
> `app/api/v1/rag.py`, router regisztracio, kulon frontend munkafelület es
> `tests/test_rag.py`. A jelenlegi `/rag/query` feloldja a
> case/document/collection forraskort, ujrahasznalja a meglevo chunk retrieval
> reteget, analysis-run inputkent rogziti a kivalasztott chunkokat,
> backend-owned `used_sources` listat ad vissza, cimkezett source packetet kuld
> az LM Studio chat modellnek, es a minimalis RAG JSON valaszt
> (`answer_text`, `source_summary`, `insufficient_source`) validalja. A
> tobbdokumentumos generaltas dokumentumonkenti reszvalasz + vegso szintezis
> szerkezetet hasznal.

#### 10.4.1 Migracio

Uj Alembic migracio:

```text
0044_rag_answers
0045_limit_rag_answer_modes
```

Tartalma:

- `rag_answers` tabla letrehozasa,
- `analysis_run_id` egyedi constraint,
- index `case_id`,
- index `analysis_run_id`,
- opcionális index `created_at`.

Javasolt constraint-ek:

- `question` ne legyen ures,
- `answer_text` ne legyen ures,
- `answer_mode` csak `short | detailed`,
- `source_scope_json`, `used_sources_json`, `retrieval_metadata_json` legyen
  not null.

Ha a jelenlegi migration-konvencio nem szereti a JSONB constraintet, eleg a
not null es service-szintu validacio.

#### 10.4.2 SQLAlchemy model

Uj fajl:

```text
app/models/rag_answer.py
```

Model:

```text
RagAnswerModel
```

Kapcsolatok:

- `case`,
- `analysis_run`,
- opcionálisan `created_by_user`.

Frissitendo:

```text
app/models/__init__.py
```

#### 10.4.3 Pydantic schemak

Uj fajl:

```text
app/schemas/rag.py
```

Javasolt request schemak:

- `RagQueryRequest`,
- `RagSaveAnswerRequest`.

Javasolt response schemak:

- `RagUsedSource`,
- `RagSourceScopeSummary`,
- `RagRetrievalMetadata`,
- `RagAnswerPayload`,
- `RagQueryResponse`,
- `RagSavedAnswerListItem`,
- `RagSavedAnswerDetail`,
- `RagSaveAnswerResponse`.

Javasolt enumok:

- `RagSourceMode`,
- `RagAnswerMode`,
- `RagRetrievalStrategy`.

Fontos:

```text
Az enum/internal ertekek lehetnek angolok, de a frontend lathato szovege magyar legyen.
```

#### 10.4.4 Service reteg

Uj fajl:

```text
app/services/rag.py
```

Javasolt fuggvenyek:

```text
run_rag_query(db, case_id, request) -> RagQueryResponse
save_rag_answer(db, case_id, run_id, request) -> RagSaveAnswerResponse
list_rag_answers(db, case_id) -> list[RagSavedAnswerListItem]
get_rag_answer(db, case_id, answer_id) -> RagSavedAnswerDetail
delete_rag_answer(db, case_id, answer_id) -> None
```

Belső helper fuggvenyek:

```text
resolve_rag_source_scope(...)
select_rag_source_chunks(...)
build_rag_source_packet(...)
call_rag_llm(...)
parse_rag_llm_response(...)
build_used_sources(...)
```

Ujrafelhasznalando meglevo reteg:

- `app/services/analysis_runs.py`,
- `app/services/document_collections.py` source-scope resolver,
- keyword/semantic/hybrid retrieval helper a `search_findings` workflow-bol,
- `app/services/llm.py`,
- `app/services/text_store.py`.

Service-szintu dontes:

- `run_rag_query` mindig indit `analysis_run` rekordot,
- sikeres vagy insufficient-source valasz nem hoz letre `rag_answers` rekordot,
- `save_rag_answer` csak korabbi `rag_query` runbol menthet,
- duplicate save elso korben legyen idempotens: ha mar van mentett valasz az
  adott runhoz, adja vissza a letezot.

#### 10.4.5 API router

Uj fajl:

```text
app/api/v1/rag.py
```

Endpointok:

```text
POST   /cases/{case_id}/rag/query
POST   /cases/{case_id}/rag/runs/{run_id}/save-answer
GET    /cases/{case_id}/rag/answers
GET    /cases/{case_id}/rag/answers/{answer_id}
DELETE /cases/{case_id}/rag/answers/{answer_id}
```

Frissitendo:

```text
app/api/v1/router.py
```

Elso korben nem kell:

- update saved answer,
- tageles,
- export,
- valaszbol finding/claim inditasa.

#### 10.4.6 Analysis run integracio

Javasolt `analysis_runs` ertekek:

```text
run_type = "rag_query"
model_name = aktualis chat modell
status = succeeded | failed
validation_status = passed | warning | failed
```

`input_parameters` tartalmazza:

- question,
- source mode,
- requested document/collection id,
- answer mode,
- retrieval strategy,
- max chunks,
- resolved document ids.

Run inputok:

- `query_text` vagy `rag_question`,
- `chunk` inputok a felhasznalt chunkokra.

Run output:

- elso korben eleg lehet output summary JSON,
- kesobb lehet `rag_answer` output csak mentett valasz eseten.

#### 10.4.7 Audit eventek

Javasolt audit eventek:

```text
rag_query_run
rag_answer_saved
rag_answer_deleted
```

Elso korben a `rag_query_run` lehet implicit az analysis runbol, de a mentett
es torolt valaszrol legyen audit esemeny.

Audit payload ne tartalmazzon teljes valaszszoveget, csak azonositokat es
rovid metadata-t:

- `case_id`,
- `analysis_run_id`,
- `answer_id`,
- `source_mode`,
- `used_source_count`.

#### 10.4.8 Tesztek

Uj fajl:

```text
tests/test_rag.py
```

Elso backend tesztek:

1. `POST /rag/query` ervenytelen ures kerdest elutasit.
2. `POST /rag/query` wrong-case document/collection eseten 404.
3. `POST /rag/query` sikeres futasnal letrehoz `analysis_run` rekordot.
4. Sikeres query nem hoz letre `rag_answers` rekordot.
5. `insufficient_source=true` valasz nem failure es mentheto.
6. `save-answer` letrehozza a `rag_answers` rekordot.
7. `save-answer` ugyanarra a runra idempotensen a meglevo valaszt adja vissza.
8. Nem `rag_query` run nem mentheto RAG valaszkent.
9. Failed run nem mentheto RAG valaszkent.
10. List/detail/delete endpointok csak sajat ugy valaszait kezelik.
11. `used_sources` a backend source mappingbol jon, nem az LLM JSON-bol.
12. semantic/hybrid index-ready hiany validacios hibat ad.

Ha az elso implementacios korben a teljes LLM hivas mockolva van, az elfogadhato.
A cel az adatmodell, API contract es provenance stabilizalasa.

#### 10.4.9 Nem cel az elso backend szeletben

- frontend modul,
- streaming valasz,
- tobb gyujtemeny egyszerre,
- rerank,
- context compression,
- jogszabalyi corpus,
- valaszbol automatikus research finding / claim / event,
- karakterpontos source-reference quote validacio,
- saved answer szerkesztes vagy tageles.

#### 10.4.10 Elso implementacios sorrend

Javasolt sorrend:

1. migration + model + schema,
2. router skeleton + service skeleton,
3. `save/list/detail/delete` a megadott/fake output nelkul meg nem hasznalhato
   query runokra,
4. `run_rag_query` analysis-run scaffold mockolt LLM outputtal,
5. source-scope resolver bekotese,
6. retrieval helper bekotese,
7. LLM prompt/parser bekotese,
8. teljes backend tesztcsomag,
9. csak ezutan minimal frontend modul.

## 11. Javasolt implementacios sorrend

Elso nagy szelet ne implementacioval, hanem tervezessel induljon:

1. Iratgyujtemeny / forraskor-kijeloles konkret terve.
   - **Implementalva, 2026-06-02 utan:** az elso backend/frontend
     iratgyujtemeny-szelet kesz, es az analysis/indexing workflow mar tud
     collection scope-pal dolgozni.
2. Atfogo termek- es UX-terv az altalanos RAG kerdezohoz.
   - **Aktualis dontes:** kulon oldalsavos modul legyen, nagy valaszpanellel
     es explicit `Valasz mentese` muvelettel.
3. Backend contract terv:
   - API,
   - request/response schema,
   - analysis run provenance,
   - source input/output model.
4. Retrieval terv:
   - source scope,
   - max context,
   - batch/rerank/tomorites.
5. Prompt es JSON schema terv.
6. Minimal backend slice:
   - kerdes,
   - retrieval,
   - LLM valasz,
   - analysis run mentese.
7. Minimal frontend slice:
   - kerdes mezo,
   - forraskor,
   - valasz,
   - lenyithato forrasok.
8. Jogszabalyi korpusz specializalt terv csak ezutan.

## 12. Nyitott dontes

Az altalanos RAG kerdezo bevezetese utan is meg kell tartani a szigoru, forrasvalidalt munkapad workflow-kat.

Nyitott kerdes:

```text
A RAG valaszbol kesobb lehessen-e egy gombbal kutatasi talalatot, allitast vagy mas strukturalt objektumot kezdeni?
```

Ez hasznos lehet, de nem az elso szelet resze.

## 13. Kesobbi specializalt jogszabalyi kereso

Az altalanos iratkerdezo technikailag alkalmas lehet jogszabalyi szovegek
alap RAG-kerdezesere, de egy komoly jogszabalyi kereso ne legyen egyszeruen
ugyanennek a modulnak egy feliratozott valtozata.

Ha a rendszer kesobb valodi joganyag-korpusszal dolgozik, kulon modult vagy
legalabb kulon specializalt munkamodot erdemes tervezni.

Indok:

- jogszabalyhely-modell kellhet: jogszabaly, cim, fejezet, paragrafus,
  bekezdes, pont, alpont,
- hatalyossagi datum szerinti kereses es valaszadas kellhet,
- norma, kivetel, atmeneti rendelkezes es modositas elkulonitese kellhet,
- a forrasok nem egyszeru dokumentumchunkok, hanem jogszabalyhelyek,
- a valaszban a jogszabalyhelyek elsorangu objektumok legyenek, ne csak
  altalanos forrasidezetek.

Elso dontes:

```text
Az altalanos iratkerdezo marad szabad kerdes-valasz felulet ugyiratokhoz es
iratgyujtemenyekhez. A komoly jogszabalyi kereso kesobbi, kulon tervezesi
szelet legyen.
```
