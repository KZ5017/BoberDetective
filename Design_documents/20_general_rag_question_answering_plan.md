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

Uj munkafeluleten vagy kesobb kulon modulban:

```text
Altalanos iratkerdezo
```

Elhelyezes a munkafeluletek kozott:

```text
Ügy munkapad | Teljes iratfeldolgozás | Általános iratkérdező | Audit napló
```

Elso feluleti elemek:

- nagy kerdes beviteli mezo,
- forraskor valasztasa:
  - teljes ugy,
  - kijelolt dokumentumok,
  - kesobbi kulon korpuszok, peldaul jogszabalyi korpusz,
- retrieval strategia:
  - keyword,
  - semantic,
  - hybrid,
- valasz reszletessege:
  - rovid,
  - normal,
  - reszletes,
- opcionális kapcsolo:
  - forrasok megjelenitese.

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

## 11. Javasolt implementacios sorrend

Elso nagy szelet ne implementacioval, hanem tervezessel induljon:

1. Iratgyujtemeny / forraskor-kijeloles konkret terve.
2. Atfogo termek- es UX-terv az altalanos RAG kerdezohoz.
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
