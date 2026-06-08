# 21. Markdown tudasbazis modul terv

## 1. Cel

Ez a dokumentum a kovetkezo nagyobb fejlesztesi szeletet rogziti:
egy kulon `Tudasbazis` modul bevezetese Markdown (`.md`) alapu,
strukturalt tudasanyag importalasara, indexelesere es kerdezesere.

A cel nem egy IT security, hacking, jogszabalyi vagy mas tartalomspecifikus
modul. A cel egy altalanos, lokalis, Markdown-alapu tudasbazis workflow.

Rovid celmondat:

```text
A felhasznalo nagy mennyisegu strukturalt Markdown tudasanyagot importalhat,
majd azt kulon Tudasbazis modulban, lokalis RAG modon kerdezheti.
```

## 2. Alapdontes

Az `.md` fajlok ne keruljenek ugyanabba a mentalis es feldolgozasi kalapba,
mint az ugyiratok.

Ugyirat:

- nyomozati/jogi/irati forras,
- bizonyitek vagy ugyanyag lehet,
- munkapad workflow-khoz kapcsolodik,
- `search_findings`, teljes iratfeldolgozas, attekintesi jelentes es
  forrasvalidalt objektumletrehozas hasznalja.

Markdown tudasbazis:

- strukturalt hattertudas vagy jegyzetanyag,
- nem bizonyitek es nem ugyirat,
- kulon modulban kerdezheto,
- nem kerulhet be veletlenul a nyomozati munkapad workflow-k forraskorebe,
- valaszado/tudasfeltaro RAG hasznalatra keszul.

## 3. Dokumentumjelleg

A megbeszelt logikai par:

```text
knowledge_base / markdown_note
```

Fontos pontositas:

- ez nem a korabban kivezetett altalanos irattaxonomia visszahozasa,
- nem cel ujra szabadon szerkesztheto iratcsoport/irattipus workflow-t epiteni,
- ez egy szuk, rendszer-altal ertett dokumentumjelleg vagy importprofil.

Implementacios nev kesobb valaszthato:

- `document_domain = knowledge_base`
- `document_kind = markdown_note`
- vagy mas szuk, enum-szeru mezo.

A lenyeg:

```text
knowledge_base / markdown_note = rendszer-szintu elkulonites,
nem felhasznaloi taxonomia.
```

## 4. Mi ez es mi nem

### Ez

- Markdown import,
- Markdown-szerkezetet figyelembe vevo szovegkinyeres,
- heading-alapu es code-block-safe chunkolas,
- kulon Tudasbazis munkafelület,
- lokalis RAG kerdezes csak tudasbazis dokumentumokon,
- nagy volumen tesztelesre alkalmas import es indexeles,
- tartalomfuggetlen hasznalat:
  - IT security jegyzet,
  - jogi jegyzet Markdownban,
  - muszaki dokumentacio,
  - kutatasi jegyzet,
  - belso ceges tudasanyag,
  - oktatasi anyag.

### Nem ez

- nem nyomozati iratimport,
- nem bizonyitekkezeles,
- nem `search_findings` munkalista-forras,
- nem teljes iratfeldolgozasi szemelykereso forras,
- nem jogi dontestamogato modul,
- nem automatikus exploit, tamadasi vagy muveleti vegrehajto eszkoz,
- nem tartalomspecifikus "hacking kereso".

## 5. Modulhatarok

### Tudasbazis modul

A `Tudasbazis` modul hasznalja:

- `knowledge_base / markdown_note` dokumentumokat,
- Markdown-aware chunkokat,
- tudasbazisra optimalizalt RAG promptot,
- mentheto valaszokat, ha ez a kesobbi UX-ben indokolt.

### Meglevo modulok

A kovetkezo modulok alapertelmezetten ne kinaljak fel a Markdown
tudasbazis dokumentumokat forraskent:

- `Ugy munkapad`,
- `Teljes iratfeldolgozas`,
- `Attekintesi jelentes`,
- `Kutatasi talalatok`,
- `Kezi ellentmondasjelolt`.

Indok:

```text
A meglevo workflow-k ugyiratokra, forrasvalidalt talalatokra es
emberi review-ra vannak optimalizalva. Markdown tudasanyagnal ez
rossz UX-et es felrevezeto eredmenyt adna.
```

### Altalanos iratkerdezo kapcsolata

Az `Altalanos iratkerdezo` mar mukodo lokalis RAG felulet. A `Tudasbazis`
modul ne olvadjon bele automatikusan ebbe, mert:

- mas a forraskor,
- mas az import,
- mas a dokumentumjelleg,
- mas a vart felhasznaloi mentalis modell.

A ketto technikailag hasznalhat kozos retrieval/LLM szolgaltatast, de a
frontend es forraskor-valasztas legyen kulon.

## 6. Elso implementacios szelet

Az elso szelet celja:

```text
.md fajlok importalasa, chunkolasa, indexelese es kerdezese kulon
Tudasbazis modulban, Obsidian-specifikus graf funkciok nelkul.
```

### 6.1 Backend

Elso backend feladatok:

1. `.md` fajltipus engedelyezese kontrollalt upload path-on.
2. Szuk dokumentumjelleg/importprofil bevezetese:
   - `knowledge_base`,
   - `markdown_note`.
3. Markdown parser szolgaltatas letrehozasa.
4. Markdown text-layer/chunk-manifest irasa a jelenlegi text-store elvhez
   igazodva.
5. Markdown chunkok indexelese a meglevo embedding/Qdrant alapon.
6. Tudasbazis RAG endpoint vagy a RAG service szuk, elkulonitett
   knowledge-base wrapperje.
7. Audit/provenance:
   - import,
   - chunkolas,
   - indexeles,
   - kerdezes,
   - valasz mentes, ha lesz ilyen az elso szeletben.

### 6.2 Frontend

Elso frontend feladatok:

1. Uj oldalsav/menu elem:

```text
Tudasbazis
```

2. Markdown import panel.
3. Importalt tudasbazis dokumentumok listaja.
4. Index allapot.
5. Kerdes beviteli panel.
6. Aktualis valasz panel.
7. Felhasznalt forrasok megjelenitese:
   - fajlnev,
   - heading path,
   - chunk/snippet,
   - code block jeloles, ha relevans.

## 7. Markdown feldolgozasi szabalyok

### 7.1 Megorzendo szerkezet

A parser tartsa meg vagy metaadatkent vigye tovabb:

- fajlnev,
- relatív fajlut,
- heading hierarchy,
- YAML frontmatter,
- fenced code blockok,
- code block nyelvjeloles,
- listak,
- tablak,
- Obsidian wikilinkek forrasszovege.

### 7.2 Chunkolasi elvek

Markdown chunkolasnal elso prioritas:

```text
ne vagjunk szet ertelmi szerkezetet.
```

Javasolt hatarok:

1. H1/H2/H3 heading szakaszok,
2. bekezdesek,
3. listablokkok,
4. tablak,
5. fenced code blockok.

Code block szabaly:

```text
Fenced code blockot ne vagjunk ket chunkba, ha ez esszeru merethataron
belul tarthato.
```

Ha egy code block tul nagy:

- kulon `oversized_code_block` jelzes,
- kontrollalt belso darabolas,
- metaadatban jelezni, hogy a kodblokk darabolt.

### 7.3 Heading path

Minden chunk kapjon emberileg ertelmezheto heading path-ot, peldaul:

```text
PrivEsc jegyzetek > Linux > SUID binarisok
```

Ez a RAG forrasmegjelenitesben sokkal hasznosabb, mint egy puszta
oldalszam, mert Markdownban nincs termeszetes page fogalom.

## 8. Obsidian specifikus elemek

Az elso szeletben az Obsidian-tamogatas csak kompatibilitas legyen,
nem teljes graf feldolgozas.

Elso szelet:

- `.md` fajlok importalhatok,
- wikilink forrasszoveg megmarad,
- frontmatter nem veszik el,
- mappautvonal megmarad,
- code blockok es headingek ertelmesen kezelodnek.

Kesobbi szelet:

- wikilink target feloldas,
- backlink nezet,
- tag alapu szures,
- frontmatter alapu szures,
- Obsidian mappaszerkezetbol gyujtemenyjavaslat,
- kapcsolati graf,
- attachment/image kezeles.

## 9. RAG viselkedes

Tudasbazis RAG alapelv:

```text
A valasz csak az importalt tudasbazis dokumentumokbol dolgozzon.
```

Prompt mentalitas:

- ne kezelje bizonyitekkent a jegyzetet,
- ne hozzon letre nyomozati allitast,
- ne gyartson review objektumot,
- ne hasznaljon kulso tudast,
- ha nincs elegendo forras, mondja ki,
- technikai/jogi/muszaki jellegu valasz eseten is a forrasjegyzet legyen az alap.

Forrasmegjelenites:

- fajlnev,
- heading path,
- relevans idezet/snippet,
- code block nyelv, ha van,
- chunk azonosito vagy source id belso audit celra.

## 10. Biztonsagi es UX megfontolasok

Markdown tudasbazis tartalmazhat muveleti jellegu technikai anyagot.
Ez nem baj, mert:

- lokalis rendszer,
- felhasznalo sajat anyagai,
- fejlesztesi/tesztelesi es tudasfeltaro cel,
- nincs kulso szolgaltatas,
- nincs autonom vegrehajtas.

Termeklogikai hatar:

```text
A Tudasbazis modul valaszolhat a sajat jegyzetanyag alapjan,
de nem futtat parancsot, nem hajt vegre muveletet, es nem tesz
autonom dontest.
```

Ez nem tartalmi cenzura, hanem rendszerhatar.

## 11. Adatmodell irany

Mivel a regi altalanos dokumentum-taxonomia ki lett vezetve, a
`knowledge_base / markdown_note` megoldast nem szabad annak egyszeru
visszahozasakent implementalni.

Javasolt irany:

- szuk, enum-szeru dokumentumjelleg,
- importprofilhoz kotott viselkedes,
- forraskor-kapuk a workflow-k elott,
- backend oldali ellenorzes, hogy mely modul milyen dokumentumjelleggel
  dolgozhat.

Lehetseges mezo vagy modell:

- `documents.document_domain`,
- `documents.document_kind`,
- kulon `knowledge_documents` tabla,
- vagy importprofil + dokumentum-meta kombinacio.

Ezt az implementacio elotti DB/API tervezesi korben kell veglegesiteni.

## 12. API irany

Elso API iranyok:

- Markdown import endpoint vagy import endpoint bovites szuk modban,
- tudasbazis dokumentum lista,
- tudasbazis dokumentum reszlet,
- tudasbazis index status,
- tudasbazis index job,
- tudasbazis kerdes endpoint,
- opcionális mentett tudasbazis valaszok.

Fontos:

```text
Ne engedjuk, hogy a meglevo ugyirat workflow-k veletlenul
knowledge_base dokumentumokat kapjanak forraskent.
```

## 13. DB/API contract v1

### 13.1 Dontes: globalis tudasbazis

A `Tudasbazis` modul elso celallapotban legyen ugytol fuggetlen, globalis
modul.

Indok:

- a Markdown tudasanyag nem ugyirat,
- nem kell ugyet letrehozni csak azert, hogy tudasanyagot lehessen importalni,
- a felhasznalo sajat jegyzetei, technikai dokumentacioi vagy jogi
  jegyzetanyagai tobb ugytol fuggetlenul is hasznosak lehetnek,
- tisztabb UX: tudasbazis import a `Tudasbazis` modulban tortenik, nem az
  `Irat rendezo` ugyirat-importjaban.

Kovetkezmeny:

```text
knowledge-base dokumentumoknak nincs case_id kovetelmenye.
```

### 13.2 Dontes: kulon adattér

Az elso implementacios irany kulon tudasbazis adattér:

```text
knowledge_documents
knowledge_document_chunks
knowledge_query_runs / knowledge_answers - pontos nev kesobb
```

Indok:

- a `documents` tabla jelenleg ugyirat-dokumentumokra epul,
- a meglevo ugyirat workflow-k `case_id` es source-reference logikaja nem
  illik termeszetesen a globalis tudasbazishoz,
- a kulon tabla fizikailag is megakadalyozza, hogy Markdown tudasanyag
  veletlenul bekeruljon a nyomozati workflow-kba,
- a backend kapuk egyszerubbek: az ugyirat modulok csak `documents`-bol,
  a tudasbazis modul csak `knowledge_documents`-bol dolgozik.

Ez tudatos valtas az elso gondolatkiserlethez kepest, amely a meglevo
`documents` tabla ujrahasznalasa fele hajlott. A globalis modul dontese miatt
a kulon tudasbazis adattér lett a tisztabb valtozat.

### 13.3 Kozos technikai gerinc

A kulon adattér nem jelenti azt, hogy mindent ujra kell irni.

Ujrahasznalando mintak:

- data-root fajltarolas,
- immutable original file tarolas,
- text-store / manifest szemlelet,
- chunk manifest,
- embedding provider,
- Qdrant indexeles,
- LM Studio/OpenAI-kompatibilis chat provider,
- analysis/provenance jellegu futasnyom,
- audit esemenyek.

Elv:

```text
kulon domain modell,
kozos technikai mechanika
```

### 13.4 Minimalis DB irany

Elso migracios jelolt:

```text
knowledge_documents
```

Javasolt mezok:

- `id`
- `original_filename`
- `relative_path`
- `content_hash`
- `file_size_bytes`
- `mime_type`
- `document_kind` = `markdown_note`
- `status` = `imported | processed | indexing | indexed | failed | archived`
- `original_file_path`
- `text_layer_manifest_path`
- `chunk_manifest_path`
- `frontmatter_json`
- `heading_summary_json`
- `created_at`
- `updated_at`
- `imported_by_user_id`

Elso chunk tabla vagy manifest-alapu chunk modell:

```text
knowledge_document_chunks
```

Javasolt mezok, ha DB tabla lesz:

- `id`
- `knowledge_document_id`
- `chunk_index`
- `heading_path`
- `text_store_path` vagy manifest offset,
- `char_start`
- `char_end`
- `contains_code_block`
- `code_language`
- `metadata_json`
- `created_at`

Ha a jelenlegi text-store iranyhoz jobban illeszkedik, a chunkok DB-ben csak
metadata/index bejegyzesek legyenek, a teljes szoveg tovabbra is a data-root
text-store-ban maradjon.

### 13.5 Qdrant/index irany

A tudasbazis dokumentumok ne keveredjenek az ugyirat chunk indexekkel.

Javasolt:

- kulon Qdrant collection prefix:

```text
boberdetective_knowledge_<embedding_model_slug>
```

- payload kulcsok:
  - `knowledge_document_id`,
  - `chunk_id`,
  - `heading_path`,
  - `relative_path`,
  - `content_hash`,
  - `document_kind = markdown_note`.

Indok:

- nincs veletlen keresztkereses ugyirat es tudasbazis kozott,
- a tudasbazis index torolheto/ujraepitheto az ugyirat indexek erintese nelkul,
- kesobb mas retrieval/rerank szabalyokat kaphat.

### 13.6 API contract v1

Javasolt prefix:

```text
/api/v1/knowledge
```

Elso endpointok:

```text
POST /api/v1/knowledge/documents
GET  /api/v1/knowledge/documents
GET  /api/v1/knowledge/documents/{knowledge_document_id}
DELETE /api/v1/knowledge/documents/{knowledge_document_id}

POST /api/v1/knowledge/index/jobs
GET  /api/v1/knowledge/index/status

POST /api/v1/knowledge/query
```

Kesobbi endpointok:

```text
POST /api/v1/knowledge/documents/bulk
POST /api/v1/knowledge/import-folder
GET  /api/v1/knowledge/answers
POST /api/v1/knowledge/answers
GET  /api/v1/knowledge/answers/{answer_id}
DELETE /api/v1/knowledge/answers/{answer_id}
```

### 13.7 Import endpoint

```text
POST /api/v1/knowledge/documents
```

Input:

- multipart upload,
- csak `.md` fajl,
- opcionális `relative_path`,
- opcionális `collection_name` vagy kesobbi tudasbazis-gyujtemeny.

Backend validacio:

- kiterjesztes `.md`,
- meretlimit,
- utvonal normalizalas,
- nincs path traversal,
- UTF-8 dekodolhatosag vagy kontrollalt hibajelzes,
- hash szamitas,
- duplikatumkezeles.

Output:

```json
{
  "id": "...",
  "original_filename": "example.md",
  "relative_path": "notes/example.md",
  "status": "processed",
  "chunk_count": 12,
  "frontmatter_detected": true
}
```

### 13.8 Index status/job

```text
POST /api/v1/knowledge/index/jobs
GET  /api/v1/knowledge/index/status
```

Az elso verzio indexelhet:

- minden aktiv knowledge documentet,
- vagy kesobb kivalasztott dokumentumokat/gyujtemenyt.

Statusz tartalom:

- embedding model,
- Qdrant collection,
- indexed chunk count,
- missing chunk count,
- latest job status,
- latest job progress.

### 13.9 Query endpoint

```text
POST /api/v1/knowledge/query
```

Input v1:

```json
{
  "question": "...",
  "retrieval_strategy": "hybrid",
  "max_chunks": 45,
  "answer_mode": "detailed"
}
```

Kesobbi input:

```json
{
  "question": "...",
  "source_scope": {
    "document_ids": ["..."],
    "folder_prefix": "notes/web/",
    "tags": ["..."]
  },
  "retrieval_strategy": "hybrid",
  "max_chunks": 45,
  "answer_mode": "detailed"
}
```

Output v1:

```json
{
  "answer_text": "...",
  "source_summary": "...",
  "used_sources": [
    {
      "knowledge_document_id": "...",
      "filename": "example.md",
      "relative_path": "notes/example.md",
      "heading_path": "Fo tema > Altema",
      "quote_text": "...",
      "contains_code_block": false
    }
  ],
  "retrieval_metadata": {
    "retrieval_strategy": "hybrid",
    "max_chunks": 45,
    "selected_chunk_count": 8,
    "embedding_model": "..."
  }
}
```

### 13.10 Workflow-gate szabalyok

Backend oldali kotelezo kapuk:

1. `search_findings` nem olvashat `knowledge_documents`-bol.
2. `full-document processing` nem olvashat `knowledge_documents`-bol.
3. `review report` objektumlista nem tartalmaz `knowledge_documents`
   eredetu objektumot.
4. `source_references` klasszikus ugyirat-forraskent nem hivatkozhat
   `knowledge_documents` rekordra.
5. `knowledge/query` nem olvashat `documents`-bol.
6. Qdrant collection/payload szinten is legyen elvalasztas.

Ezeket tesztekkel kell vedeni, mert ez a modulhatar lenyege.

### 13.11 Audit/provenance

A tudasbazis workflow is auditált legyen, de ne keveredjen az ugyirat
analysis modellel.

Audit esemeny jeloltek:

- `knowledge_document_imported`
- `knowledge_document_deleted`
- `knowledge_document_index_started`
- `knowledge_document_index_completed`
- `knowledge_query_run`
- `knowledge_answer_saved` - ha lesz mentett valasz

Nyitott implementacios kerdes:

- kulon `knowledge_query_runs` tabla,
- vagy `analysis_runs` bovites ugytol fuggetlen futastipussal.

Elso javaslat:

```text
kulon knowledge_query_runs, hogy ne kelljen case_id nelkuli analysis_run
viselkedest bevezetni.
```

### 13.12 Tesztkontraktus v1

Backend tesztek:

1. `.md` import letrehoz `knowledge_documents` rekordot.
2. `.txt`/`.pdf` feltoltes a knowledge import endpointon elutasitott.
3. Import nem igenyel `case_id`-t.
4. Ugyirat import endpoint nem hoz letre `knowledge_documents` rekordot.
5. Knowledge chunkolas megorzi a heading path-ot.
6. Knowledge index kulon Qdrant collection/payload iranyt hasznal.
7. `knowledge/query` csak knowledge chunkokbol valaszt forrast.
8. `search_findings` nem lat knowledge chunkot.
9. `full-document processing` nem lat knowledge dokumentumot.
10. Path traversal jellegu `relative_path` elutasitott vagy normalizalt.

## 14. Markdown parser/chunker contract v1

### 14.1 Alapelv

Markdownnal nem oldalakban, hanem szakaszokban kell gondolkodni.

Termeszetes forrashely:

```text
fajl > heading path > szovegresz
```

Ezert a `Tudasbazis` modul forrasmegjeleniteseben ne probaljunk
oldalszamot eroltetni. A felhasznalo szamara a fajlut + heading path adja
a legjobb tajekozodasi pontot.

### 14.2 Beolvasas es kodolas

Alapertelmezett kodolas:

```text
UTF-8
```

V1 viselkedes:

- ha a fajl nem dekodolhato UTF-8-kent, az import kontrollalt hibaval alljon
  meg,
- ne probaljunk csendben javitani vagy karaktereket eldobni,
- hibakod: `invalid_encoding`.

Indok:

```text
A forrashuseg fontosabb, mint az agressziv "megjavitas".
```

### 14.3 YAML frontmatter

Ha a Markdown fajl elejen YAML frontmatter talalhato:

```markdown
---
tags:
  - linux
  - web
---
```

akkor:

- kulon metadata mezokent taroljuk,
- `frontmatter_json` vagy ennek megfelelo manifest metadata reszbe kerul,
- a RAG bemeneti szovegbe ne keruljon automatikusan teljes egeszeben.

Indok:

- a frontmatter hasznos szuresre es rendszerezesre,
- de valaszalapkent gyakran zaj,
- kesobb explicit forraskor/tag szureshez jol hasznalhato.

Ha a frontmatter parse nem sikerul:

- ne legyen fatal hiba,
- quality flag: `frontmatter_parse_failed`,
- a nyers frontmatter szoveg megorizheto metadata/debug celra.

### 14.4 Heading path

A headingek a chunkolas es forrasmegjelenites elsodleges szerkezeti elemei.

Pelda:

```markdown
# Linux
## Privilege escalation
### SUID
```

Heading path:

```text
Linux > Privilege escalation > SUID
```

Minden chunk metadataja tartalmazza:

- `heading_path`,
- `heading_level`,
- opcionálisan `heading_ids` vagy heading indexek kesobbi navigaciohoz.

Ha egy fajl heading nelkuli:

- a `heading_path` lehet ures vagy `Dokumentum gyokere`,
- ez nem hiba.

### 14.5 Chunkolasi elvek

Elso chunkolasi prioritas:

```text
ne vagjunk szet ertelmi szerkezetet.
```

Javasolt hatarok:

1. H1/H2/H3 heading szakaszok,
2. bekezdesek,
3. listablokkok,
4. tablak,
5. fenced code blockok.

Meretirany v1:

```text
target: 2500-4000 karakter
hard max: 6000-8000 karakter
```

Viselkedes:

- ha egy heading alatti szakasz normal meretu, maradjon egy chunk,
- ha tul nagy, bekezdesek/listablokkok menten daraboljuk,
- ha nagyon kicsi, osszevonhato szomszedos szakasszal ugyanazon heading
  alatt vagy kozvetlen parent alatt,
- a chunkolas karakteralapu legyen, mert a jelenlegi text-store es chunk
  pipeline ezzel konnyebben illesztheto.

### 14.6 Fenced code block

Fenced code blockot alapbol ne vagjunk szet.

Pelda:

````markdown
```bash
whoami
id
```
````

V1 viselkedes:

- a code block egyben maradjon, ha esszeru merethataron belul van,
- a chunk metadata tartalmazza:
  - `contains_code_block = true`,
  - `code_languages = ["bash"]`,
- nagy code block kulon chunk lehet.

Ha egy code block extrem nagy:

- quality flag: `oversized_code_block`,
- csak ekkor darabolhato kontrollaltan,
- darabolas eseten metadata:
  - `split_code_block = true`.

### 14.7 Listak

Listakat ne vagjunk szet soronkent.

V1 viselkedes:

- egy osszetartozo lista blokk maradjon egy blokk,
- ha tul nagy, listaelemek menten darabolhato,
- nested lista forrasszovege maradjon karakterhű.

### 14.8 Tablak

Markdown tablat lehetoseg szerint egyben kell tartani.

Ha tul nagy:

- quality flag: `large_markdown_table`,
- v1-ben ne epitsunk kulon tablaparsert,
- a Markdown szoveg maradjon forrashu.

### 14.9 Inline code

Inline code maradjon valtozatlan szovegkent.

Pelda:

```markdown
Hasznald az `nmap -sV` parancsot.
```

Ne normalizaljuk, ne vegyuk ki, ne alakitsuk at.

### 14.10 Obsidian wikilink

Obsidian wikilinkek v1-ben maradjanak karakterhűen a szovegben.

Pelda:

```markdown
[[Linux PrivEsc]]
[[Linux PrivEsc|SUID technikak]]
```

V1 viselkedes:

- ne probaljuk feloldani,
- ne csereljuk link targetre,
- metadata szinten opcionalisan kigyujtheto:

```json
{
  "wikilinks": ["Linux PrivEsc"]
}
```

A teljes Obsidian graf/backlink feldolgozas kesobbi szelet.

### 14.11 Obsidian tagek

Inline tag:

```markdown
#linux #privsec
```

V1 viselkedes:

- maradjon a szovegben,
- metadata szinten kigyujtheto `tags` listaba,
- frontmatter tags kulon `frontmatter_tags` listaba kerulhet.

### 14.12 Kepek es attachmentek

V1-ben ne dolgozzuk fel az attachmenteket.

Pelda:

```markdown
![[image.png]]
![alt](image.png)
```

Viselkedes:

- maradjanak forrashu szovegkent,
- ne legyen OCR,
- ne legyen kepindex,
- attachment feldolgozas kesobbi kulon szelet.

### 14.13 Minimalis chunk metadata

Javasolt minimalis metadata:

```json
{
  "knowledge_document_id": "...",
  "chunk_index": 0,
  "heading_path": "Linux > Privilege escalation > SUID",
  "heading_level": 3,
  "char_start": 1200,
  "char_end": 3800,
  "contains_code_block": true,
  "code_languages": ["bash"],
  "wikilinks": ["Linux PrivEsc"],
  "tags": ["linux", "privsec"],
  "frontmatter_tags": ["web"],
  "quality_flags": []
}
```

Ezek kozul a kotelezo minimum:

- `knowledge_document_id`,
- `chunk_index`,
- `heading_path`,
- `char_start`,
- `char_end`,
- `quality_flags`.

A tobbi mezot akkor taroljuk, ha a parser biztosan ki tudja nyerni.

### 14.14 Source display

Forrasmegjelenites forma:

```text
notes/linux/privesc.md
Linux > Privilege escalation > SUID
```

Alatta:

- relevans excerpt,
- code block jeloles, ha a forrasresz kodot tartalmaz,
- belso chunk/source id csak technikai reszletekben.

Ez legyen a Markdown megfeleloje annak, amit ugyiratoknal dokumentum + oldal
+ szovegresz ad.

### 14.15 Quality flags es hibak

Fatal hibak:

- `invalid_encoding`,
- `empty_markdown`,
- `no_text_content`.

Warning jellegu quality flag:

- `frontmatter_parse_failed`,
- `oversized_code_block`,
- `large_markdown_table`.

V1 szabaly:

```text
Fatal hiba eseten ne keszuljon feldolgozhato knowledge document text layer.
Warning eseten keszulhet text layer, de a figyelmeztetes jelenjen meg az
import/feldolgozasi allapotban.
```

### 14.16 Parser implementacios irany

V1-ben ne vezessunk be teljes Markdown AST feldolgozast, ha nem muszaj.

Javasolt:

- determinisztikus, soralapu parser,
- felismeri:
  - frontmatter blokkot,
  - headingeket,
  - fenced code blockokat,
  - listablokkokat,
  - tablablokkokat,
  - bekezdeseket,
  - Obsidian wikilink/tag mintakat.

Indok:

- a cel nem HTML rendereles,
- a cel jo, forrashu chunkolas,
- a soralapu parser jobban kontrollalhato,
- kevesebb dependency es kevesebb meglepetes.

Kesobb, ha a live korpusz megmutatja, hogy kell, bevezetheto teljesebb
Markdown parser vagy AST-alapu feldolgozas.

## 15. Tesztelési terv

Elso tesztek:

1. `.md` upload sikeres.
2. Nem `.md` fajl nem kerulhet a Tudasbazis import path-ra.
3. Markdown headingekbol helyes heading path keszul.
4. Fenced code block nem szakad szet normal meretnel.
5. YAML frontmatter nem veszik el.
6. Wikilink forrasszoveg megmarad.
7. Markdown chunkok indexelhetok.
8. Tudasbazis RAG csak knowledge-base dokumentumokat hasznal.
9. Ugy munkapad nem kinalja fel knowledge-base dokumentumokat forraskent.
10. Nagyobb mappanyi `.md` importnal a rendszer nem omlik ossze es
    audit/progress allapotot ad.

## 16. Nyitott kerdesek

Implementacio elott tisztazando:

1. Legyen-e mappas upload / batch import az elso szeletben, vagy eloszor
   csak tobb fajlos `.md` upload?
2. Mentjuk-e a tudasbazis valaszokat ugyanugy, mint az altalanos RAG
   valaszokat?
3. A heading path kulon DB mezokent, chunk metadata-kent vagy manifest
   adatkent legyen tarolva?
4. Mekkora legyen a Markdown chunk merethatara code blockok mellett?
5. Kulon `knowledge_query_runs` tabla legyen, vagy az `analysis_runs`
   kapjon ugytol fuggetlen futastipust?
6. Mikor vezessuk be az Obsidian wikilink/backlink graf feldolgozast?

## 17. Backend implementation plan v1

Ez a resz a kodolas elotti elso konkret backend szeletet rogziti.

Cel:

```text
minimalis, tesztelheto backend alap a globalis Markdown Tudasbazishoz
```

Nem cel meg:

- teljes frontend,
- Obsidian graf,
- attachment feldolgozas,
- mappas import,
- mentett tudasbazis valaszok teljes workflow-ja.

### 17.1 Elso backend scope

Az elso implementacios scope:

1. kulon `knowledge_documents` adattér,
2. `.md` import endpoint,
3. determinisztikus Markdown parser/chunker,
4. text-store/chunk-manifest iras,
5. dokumentum lista/reszlet API,
6. minimalis backend tesztek.

Az indexeles es RAG endpoint a kovetkezo backend szelet lehet, ha az import
es chunkolas stabil.

Indok:

```text
Eloszor legyen megbizhato, forrashu Markdown -> chunk pipeline. Csak erre
erdemes retrievalt es LLM valaszadast epiteni.
```

### 17.2 Migracio

Elso migracio:

```text
0046_knowledge_documents
```

Javasolt tartalom:

- `knowledge_documents` tabla,
- szuk status enum/check constraint,
- content hash index,
- created/updated idopontok,
- importalo user nullable/optional kapcsolat, ha a jelenlegi auth modell ezt
  konnyen tamogatja,
- path mezok:
  - original file path,
  - text layer manifest path,
  - chunk manifest path.

Masodik migracio csak akkor kell az elso szeletben, ha a chunkokat DB tablaban
is akarjuk tartani:

```text
0047_knowledge_document_chunks
```

Elso javaslat:

```text
az elso szeletben a teljes chunk szoveg text-store/manifest alapu legyen,
DB-ben csak knowledge_documents meta; chunk tabla csak akkor keruljon be, ha
az index/query implementaciohoz tenyleg szukseges.
```

### 17.3 SQLAlchemy modellek

Javasolt fajl:

```text
app/models/knowledge.py
```

Elso modellek:

- `KnowledgeDocumentModel`
- kesobb `KnowledgeDocumentChunkModel`, ha DB chunk tabla kell
- kesobb `KnowledgeQueryRunModel`
- kesobb `KnowledgeAnswerModel`

Ne keverjuk a `DocumentModel` osztalyba, mert az ugyirat dokumentum.

### 17.4 Pydantic sémák

Javasolt fajl:

```text
app/schemas/knowledge.py
```

Elso sémák:

- `KnowledgeDocumentResponse`
- `KnowledgeDocumentListResponse`
- `KnowledgeDocumentImportResponse`
- `KnowledgeDocumentDetailResponse`
- `KnowledgeDocumentStatus`
- `KnowledgeChunkPreview`

Kesobbi sémák:

- `KnowledgeIndexStatusResponse`
- `KnowledgeQueryRequest`
- `KnowledgeQueryResponse`
- `KnowledgeUsedSource`
- `KnowledgeAnswerResponse`

### 17.5 Markdown parser service

Javasolt fajl:

```text
app/services/markdown_parser.py
```

Feladata:

- UTF-8 decode,
- frontmatter felismeres,
- heading stack epites,
- fenced code block felismeres,
- listablokk/tablabokk/bekezdes blokkositas,
- wikilink/tag kigyujtes,
- quality flag gyujtes,
- chunk jeloltek eloallitasa.

Javasolt belso DTO-k:

- `ParsedMarkdownDocument`
- `MarkdownBlock`
- `MarkdownChunkCandidate`

Fontos:

```text
Ez a service ne irjon adatbazist es ne hivjon LLM-et.
Csak determinisztikus parse/chunk logika.
```

### 17.6 Knowledge import service

Javasolt fajl:

```text
app/services/knowledge_import.py
```

Feladata:

- upload validacio,
- `.md` kiterjesztes ellenorzes,
- path traversal vedelem,
- hash szamitas,
- original fajl mentese data-root ala,
- markdown parser meghivasa,
- text-layer/chunk-manifest irasa,
- `knowledge_documents` rekord letrehozasa/frissitese,
- audit esemeny irasa.

Fontos:

```text
Az ugyirat import service-t ne bovitsuk tudasbazis logikaval. A mintakat
ujrahasznalhatjuk, de a domain service legyen kulon.
```

### 17.7 Text-store integracio

Az elso szelet hasznalja a meglevo data-root/text-store szemleletet, de kulon
utvonal alatt.

Javasolt irany:

```text
data_root/
  knowledge/
    documents/
      <knowledge_document_id>/
        original.md
        text_layer.json
        chunks.jsonl
```

Vagy a projektben mar letezo text-store path-konvenciokhoz igazodva ennek
megfelelo varians.

Elv:

- eredeti `.md` immutable,
- feldolgozott text layer kulon,
- chunk manifest kulon,
- DB-ben csak meta/path.

### 17.8 API router

Javasolt fajl:

```text
app/api/v1/knowledge.py
```

Router bekotes:

```text
app/api/v1/router.py
```

Elso endpointok:

```text
POST /api/v1/knowledge/documents
GET  /api/v1/knowledge/documents
GET  /api/v1/knowledge/documents/{knowledge_document_id}
DELETE /api/v1/knowledge/documents/{knowledge_document_id}
```

Elsore a `DELETE` lehet soft delete / archive, ha ez jobban illik a
rendszer audit szemleletehez.

### 17.9 Indexing service kovetkezo szelet

Javasolt kesobbi fajl:

```text
app/services/knowledge_indexing.py
```

Feladata:

- knowledge chunk manifest beolvasas,
- embedding generálas,
- kulon Qdrant collection hasznalat,
- index status/progress,
- reindexeles.

Ezt ne keverjuk az elso import/parser szeletbe, ha ettol az elso szelet
tul nagy lenne.

### 17.10 Knowledge RAG service kovetkezo szelet

Javasolt kesobbi fajl:

```text
app/services/knowledge_rag.py
```

Feladata:

- knowledge retrieval,
- prompt osszeallitas,
- source packet generalas heading path + excerpt alapon,
- LLM valasz parse,
- used sources visszaadas,
- opcionális answer save elokeszites.

Ez hasznalhat kozos RAG helper mintakat, de ne legyen ugyanaz az endpoint,
mint az `Altalanos iratkerdezo`.

### 17.11 Tesztfajlok

Javasolt elso tesztfajlok:

```text
tests/test_markdown_parser.py
tests/test_knowledge_import.py
```

Kesobbi tesztek:

```text
tests/test_knowledge_indexing.py
tests/test_knowledge_rag.py
tests/test_knowledge_workflow_gates.py
```

Elso tesztminimum:

1. valid `.md` parse,
2. frontmatter metadata,
3. heading path,
4. code block egyben marad,
5. wikilink/tag megorzodik,
6. invalid encoding hiba,
7. `.txt` knowledge import elutasitott,
8. import nem igenyel `case_id`,
9. `knowledge_documents` rekord letrejon,
10. chunk manifest letrejon.

### 17.12 Implementacios sorrend backend elso szelethez

1. Migracio: `knowledge_documents`.
2. SQLAlchemy model es Pydantic sémák.
3. Markdown parser service tiszta unit tesztekkel.
4. Knowledge import service data-root/text-store irassal.
5. API router es import/list/detail endpointok.
6. Import endpoint tesztek.
7. Workflow-gate smoke:
   - ugyirat endpointok nem latjak knowledge dokumentumokat,
   - knowledge endpointok nem igenyelnek ugyet.
8. Dokumentacio frissites es commit.

### 17.13 Elso szelet kesz definicio

Az elso backend szelet akkor tekintheto kesznek, ha:

- `.md` fajl importalhato a knowledge endpointon,
- nem `.md` fajl elutasitott,
- az eredeti Markdown fajl eltarolodik,
- parser/chunker letrehoz heading path-os chunk manifestet,
- a dokumentum listazhato es megnyithato API-bol,
- nincs `case_id` kovetelmeny,
- az ugyirat workflow-k nem erintettek,
- tesztek lefutnak.

## 18. Magas szintu implementacios roadmap

1. DB/API contract v1 veglegesitese a fenti kulon, globalis tudasbazis
   adattér alapjan.
2. Markdown parser/chunker contract v1 veglegesitese a fenti szabalyok
   alapjan.
3. Backend `.md` import es text-store/chunk-manifest iras.
4. Backend index status/job support knowledge-base dokumentumokra.
5. Backend tudasbazis RAG endpoint vagy wrapper.
6. Minimalis `Tudasbazis` frontend modul:
   - import,
   - lista,
   - indexeles,
   - kerdes,
   - valasz/forras megjelenites.
7. Nagyobb sajat Markdown korpusz live smoke.
8. UX es prompt finomitas a live tapasztalatok alapjan.
9. Obsidian-specifikus masodik szelet tervezese, ha az alap stabil.

## 19. Statusz

Allapot:

```text
tervezesi alap, DB/API contract v1 irany, Markdown parser/chunker contract v1 es backend implementation plan v1 letrehozva, implementacio meg nem indult
```

Kapcsolodo dokumentumok:

- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`
- `Design_documents/20_general_rag_question_answering_plan.md`
- `CURRENT_STATE.md`
- `AI_NOTES.md`
