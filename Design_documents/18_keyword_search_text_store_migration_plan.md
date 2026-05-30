# 18. Keyword Search Text-Store Migration Plan

## 0. Cel

A nagy ugyes irattarolo atalakitas kovetkezo kritikus pontja a kulcsszavas kereses.

Jelenleg a kulcsszavas kereses PostgreSQL full-text search-t hasznal kozvetlenul ezeken a teljes szovegmezokon:

```text
document_pages.extracted_text
document_chunks.chunk_text
```

Ez ellentmond a nagy ugyes celallapotnak, ahol:

```text
PostgreSQL = metadata, workflow, audit, source references, keresesi index reprezentacio
data-root text store = oldalak es chunkok teljes kinyert szovege
Qdrant = szemantikus vektorindex
```

Cel:

```text
a teljes page/chunk szoveg kivezetheto legyen PostgreSQL-bol ugy,
hogy a kulcsszavas es hybrid kereses tovabbra is gyors, szurheto,
audit-kompatibilis es text-store-backed quote-kepes maradjon.
```

## 1. Jelenlegi kodszintu allapot

Fo kod:

```text
app/services/search.py
```

Jelenlegi chunk kereses:

```text
to_tsvector('simple', DocumentChunkModel.chunk_text)
```

Jelenlegi page kereses:

```text
to_tsvector('simple', DocumentPageModel.extracted_text)
```

Jelenlegi quote gyartas:

```text
_make_quote(row.DocumentChunkModel.chunk_text, query)
_make_quote(row.DocumentPageModel.extracted_text, query)
```

Kapcsolodo hasznalat:

- `POST /api/v1/cases/{case_id}/search/keyword`
- `POST /api/v1/cases/{case_id}/search/hybrid`
- `search_findings` source selection
- source-cited smoke
- hybrid ranking keyword oldala

## 2. Mi mar kesz

Mar nem kozvetlen DB-szovegre tamaszkodik:

- `search_findings` SOURCE blokk epites,
- `search_findings` quote validacio,
- source-reference quote/span validacio,
- source-cited smoke LLM SOURCE text,
- embedding input,
- analysis run preview,
- review report source excerpt,
- research finding source excerpt.

Ezek text-store-first / DB fallback modban mukodnek.

Mar letezik:

- `document_text_layers`,
- `document_chunk_manifests`,
- `pages.jsonl`,
- `chunks.jsonl`,
- `read_page_text_from_store(...)`,
- `read_chunk_text_from_store(...)`.

## 3. Fo dontes

Ne fajlszintu linearis scannelest tegyunk a kulcsszavas kereses fo utvonalava.

Indok:

- 5000+ irat / ugy mellett a fajlszkenneles hamar draga lesz,
- a jelenlegi szurok (`document_ids`, taxonomy, page range) DB-ben jol ervenyesithetok,
- a hybrid kereses keyword resze gyors indexelt talalatokat igenyel,
- audit es analysis-run input metadata tovabbra is DB objektumokra hivatkozik.

Javasolt celmodell:

```text
document_search_entries
```

Ez nem tarolja a teljes eredeti szoveget, csak:

- source metadata,
- aktualis allapot,
- text hash / manifest kapcsolat,
- PostgreSQL `tsvector` keresesi reprezentacio.

A talalati quote es teljes excerpt mindig text-store-bol jon vissza.

## 4. Javasolt uj tabla

Munkanev:

```text
document_search_entries
```

Mezok:

```text
id uuid pk
case_id uuid not null
document_id uuid not null
source_type text not null               -- page | chunk
page_id uuid null
chunk_id uuid null
text_layer_id uuid null
chunk_manifest_id uuid null
page_start integer not null
page_end integer not null
chunk_index integer null
document_group_code text not null
document_type_code text not null
lifecycle_status text not null          -- denormalizalt gyors szureshez, vagy join DocumentModel-re
text_hash text not null
search_vector tsvector not null
is_current boolean not null default true
created_at timestamptz not null
updated_at timestamptz null
```

Constraint javaslat:

```text
source_type in ('page', 'chunk')
page_id is not null only when source_type='page'
chunk_id is not null only when source_type='chunk'
```

Index javaslat:

```text
GIN(search_vector)
btree(case_id, source_type, is_current)
btree(case_id, document_id, is_current)
btree(case_id, document_group_code, document_type_code, is_current)
btree(case_id, page_start, page_end)
unique(chunk_id) where source_type='chunk' and is_current=true
unique(page_id) where source_type='page' and is_current=true
```

Megjegyzes:

PostgreSQL `tsvector` tarolja a lexikai reprezentaciot, de nem a teljes visszaolvashato szoveget. Ez a celallapot szempontjabol elfogadhato metadata/index reteg.

## 5. Indexepitesi workflow

### 5.1 Page search entry

Amikor current page text layer letrejon vagy elfogadasra kerul:

1. `pages.jsonl` text-store-ba kerul.
2. `document_pages` metadata sorok megmaradnak atmenetileg.
3. Letrejonnek/frissulnek a page `document_search_entries` sorok.
4. A `search_vector` a text-store-bol olvasott page textbol keszul.
5. A teljes page szoveg nem kell kesobb DB-bol.

### 5.2 Chunk search entry

Amikor current chunk manifest letrejon:

1. `chunks.jsonl` text-store-ba kerul.
2. `document_chunks` metadata sorok megmaradnak atmenetileg.
3. Letrejonnek/frissulnek a chunk `document_search_entries` sorok.
4. A `search_vector` a text-store-bol olvasott chunk textbol keszul.
5. A keyword/hybrid source selection chunk search innen dolgozik.

## 6. Keresesi workflow celallapot

`keyword_search(...)` ne ezt tegye:

```text
to_tsvector('simple', DocumentChunkModel.chunk_text)
```

Hanem:

```text
DocumentSearchEntryModel.search_vector @@ to_tsquery(...)
```

Majd:

1. DB visszaadja a talalati source metadata-t: document, page/chunk id, score.
2. Ha `include_quotes=true`, a quote text-store-bol keszul:
   - chunk talalatnal `read_chunk_text_from_store(db, chunk)`,
   - page talalatnal `read_page_text_from_store(db, page)`.
3. A visszatero `KeywordSearchHit` API forma valtozatlan maradhat.

## 7. Hybrid keresesre gyakorolt hatas

Hybrid jelenleg:

```text
keyword_hits + semantic_hits -> hybrid rank
```

A semantic oldal mar Qdrant + metadata alapu.

A keyword oldal atall:

```text
document_search_entries.search_vector
```

Ezutan a hybrid ranking lenyegeben valtozatlan maradhat.

## 8. Mi marad DB-ben atmenetileg

Az elso implementacios lepesekben ne toroljuk:

```text
document_pages.extracted_text
document_chunks.chunk_text
```

Hanem:

1. bevezetjuk az uj search entry tablat,
2. uj import/chunk workflow-k irjak azt,
3. `keyword_search` atall az uj indexre,
4. tesztekkel igazoljuk az egyezo vagy jobb mukodest,
5. csak ezutan lehet nullable/deprecated iranyba vinni a teljes DB text mezoket.

## 9. Implementacios lepcso

### Lepes 1

Allapot: kesz.

Schema + model:

- `DocumentSearchEntryModel`,
- Alembic migracio,
- indexek.

### Lepes 2

Allapot: service skeleton kesz, workflow bekotes kesz.

Index writer service:

```text
app/services/lexical_index.py
```

Felelosseg:

- current page/chunk search entries letrehozasa,
- regi current entries deaktivalasa,
- `tsvector` feltoltes DB oldali `to_tsvector('simple', :text)` kifejezessel,
- text-store-bol olvasott text hasznalata.

### Lepes 3

Allapot: kesz.

Workflow bekotes:

- TXT import,
- clean native PDF text layer,
- clean/accepted OCR text layer,
- explicit chunk creation.

### Lepes 4

Allapot: kesz.

`keyword_search` atallitasa:

- source target `chunks/pages/all` tovabbra is mukodjon,
- filterek ugyanazok maradjanak,
- quote text-store-bol jojjon,
- API forma ne valtozzon.

### Lepes 5

Teszt lefedes:

- keyword talalat chunk entrybol,
- page talalat page entrybol,
- taxonomy/document/page-range filter,
- include_quotes text-store-bol,
- hybrid keyword oldal uj indexbol,
- DB text fallback csak atmeneti/regresszios modon.

### Lepes 6

Atmeneti kompatibilitas utan:

- uj dokumentumoknal DB text mezok minimalizalasa / nullable irany megtervezese,
- regi DB texttol valo fuggoseg tilasa teszttel,
- nagy ugyes import batch tervezese.

## 10. Nem cel most

Nem cel ebben a szeletben:

- sajat fajlalapu inverted index,
- SQLite FTS bevezetese,
- Qdrant lecserelese keyword indexre,
- DB text mezok azonnali torlese,
- frontend API szerzodes megvaltoztatasa.

## 11. Javasolt kovetkezo konkret feladat

Kovetkezo implementacios szelet:

```text
import/search live smoke friss TXT/PDF anyaggal, majd DB text mezok nullable/deprecated terv.
```

Az elso foundation mar kesz: `DocumentSearchEntryModel`, `0036_search_entries` migracio,
es `app/services/lexical_index.py` writer helper. A populacio is be van kotve a text-layer
es chunk-manifest workflow-kba, igy az uj `document_search_entries` reteg parhuzamosan
karbantartodik. Az aktiv `keyword_search` mar a `document_search_entries.search_vector`
mezot hasznalja, mikozben a quote/full excerpt text-store-backed olvasasbol keszul.
