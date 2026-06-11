# 22. Markdown AST alapu chunking terv

## 1. Cel

Ez a dokumentum a `Tudasbazis` modul Markdown parser hardening szeletet
rogziti. A szelet vegrehajtott allapota:

```text
Az aktiv Markdown import parser Marko/AST alapu.
Parser: markdown_marko_ast_parser_v1
Chunking: markdown_ast_sections_v1
```

A cel nem a teljes `Tudasbazis` modul ujrairasa volt. A cel az volt, hogy a
Markdown fajlokbol jobb minosegu, logikailag osszetartozobb chunkok
keszuljenek, mert ez kozvetlenul javithatja a retrieval es a RAG valaszok
minoseget.

## 2. Kiindulo allapot

Korabban a Markdown feldolgozas sajat, determinisztikus, soralapu parserrel
tortent:

```text
parser: markdown_line_parser_v1
chunking_strategy: markdown_heading_blocks_v1
```

A mostani parser felismeri:

- UTF-8 tartalmat,
- egyszeru frontmattert,
- headingeket,
- bekezdeseket,
- listanak latszo sorokat,
- tablanak latszo sorokat,
- fenced code blockokat,
- wikilink-szeru hivatkozasokat,
- inline tageket.

A mostani chunking elsodleges logikaja:

- heading path valtasnal uj chunk indul,
- blokkokat gyujt kb. 4000 karakteres celmeretig,
- 8000 karakteres hard maximumot hasznal,
- fenced code blockot igyekszik egyben tartani.

Ez jo elso alap volt, de nem teljes Markdown szerkezeti ertelmezes.

## 3. Mi a problema, amit javitani akarunk?

Markdown jegyzetekben a tartalom gyakran nem egyszeru bekezdesfolyam.

Tipikus szerkezetek:

- heading alatti teljes szakasz,
- nested listak,
- listaelemhez tartozo code block,
- magyarazat + parancs + kovetkezmeny egy logikai egysegben,
- tablak,
- blockquote-ok,
- hosszabb technikai lepeslistak,
- frontmatterrel es tagekkel jelolt jegyzetek.

Soralapu chunkolasnal elofordulhat, hogy:

- a code block levallik a magyarazo szovegrol,
- egy lista rossz ponton szakad,
- egy heading szakasz tul mechanikusan darabolodik,
- nested szerkezetek lapos szovegge valnak,
- a retrieval olyan chunkot talal meg, amelybol hianyzik a logikai kontextus.

Az AST-alapu megkozelites celja ezek csokkentese.

## 4. Alapdontes

Eredeti bevezetesi dontes: ne csereljuk le vakon a korabbi parser utat.

Elso korben epult melle egy masodik parser/chunking motor:

```text
markdown_line_parser_v1
markdown_marko_ast_parser_v1
```

Es egy uj chunking strategiat:

```text
markdown_ast_sections_v1
```

Az elfogadas utan a Marko/AST parser lett az egyetlen aktiv parser
implementacio az `app/services/markdown_parser.py` modulban. Az import,
text-store, chunk-manifest, indexeles, query es UI tovabbra is a meglevo belso
adatformatummal dolgozik.

Tehat az uj AST parser kimenete is ugyanabba a belso modellbe forduljon:

```text
ParsedMarkdownDocument
MarkdownChunk
KnowledgeStoredChunk
```

Ez csokkenti a blast radius-t: a valtozas elsosorban a Markdown feldolgozo
reteget erinti.

## 5. Javasolt konyvtar: Marko

Elso jelolt:

```text
Marko
```

Indok:

- Python alapu,
- Markdown parserkent es strukturalt dokumentumfakent hasznalhato,
- kozelebb all a backend jelenlegi technologiai stackjehez, mint egy Node
  alapu remark/unified pipeline,
- kiserleti adapterrel kontrollaltan bevezethetonek tunik.

Fontos:

```text
Marko bevezetese elott spike szukseges. A dontes akkor vegleges, ha a
sajat mintafajlokon tenylegesen jobb chunkokat ad, elfogadhato sebesseggel.
```

Alternativak kesobbi osszehasonlitasra:

- `markdown-it-py`,
- `mistune`,
- Node oldalon `remark/unified`, ha egyszer nagyon eros okunk lenne ra.

## 6. AST-alapu chunking alapelvek

Az uj chunking ne karakterablakbol induljon, hanem Markdown szerkezeti
egysegekbol.

Prioritas:

1. logikai Markdown egyseg,
2. heading path,
3. egyben tartando belso szerkezet,
4. merethatar,
5. kontrollalt fallback darabolas.

### 6.1 Heading szakasz

Egy heading alatti tartalom termeszetes forrasegyseg.

Pelda:

```markdown
## SUID

Magyarazat.

```bash
find / -perm -4000 -type f 2>/dev/null
```

Kovetkeztetes.
```

Idealizalt chunk:

```text
heading_path: Linux > SUID
node_type: heading_section
text: a magyarazat, a code block es a kovetkeztetes egyutt
```

### 6.2 Code block

Fenced code blockot nem szabad elszakitani a kozvetlenul hozza tartozo
magyarazattol, ha ez meretben esszeru.

Elso szabaly:

```text
bevezeto bekezdes + code block + kozvetlen kovetkezmeny maradjon egy chunkban,
ha a merethatar engedi
```

Tul nagy code block eseten:

- maradjon kulon strukturalt chunk,
- kapjon `oversized_code_block` quality flaget,
- darabolas csak kontrollalt fallbackkent tortenjen.

### 6.3 Listak es nested listak

Lista alapbol egyben maradjon.

Ha egy lista tul nagy:

- eloszor listaelemenkent daraboljunk,
- nested listaelemet ne szakitsunk szet, ha nem muszaj,
- listaelemhez tartozo code block maradjon a listaelemmel.

### 6.4 Tablak

Tabla alapbol egyben maradjon.

Ha tul nagy:

- kapjon `oversized_table` quality flaget,
- csak kontrollalt fallback darabolja.

### 6.5 Blockquote

Blockquote alapbol egyben maradjon.

Ha tul nagy:

- blockquote belso bekezdeshatarain lehet darabolni.

## 7. Chunk metadata bovites

A jelenlegi metadata megtartando:

- `chunk_index`,
- `heading_path`,
- `heading_level`,
- `char_start`,
- `char_end`,
- `contains_code_block`,
- `code_languages`,
- `wikilinks`,
- `tags`,
- `frontmatter_tags`,
- `quality_flags`.

Javasolt uj metadata mezok:

```text
chunk_node_type
node_types
contains_table
contains_list
contains_blockquote
ast_strategy
```

Pelda:

```json
{
  "chunk_node_type": "heading_section",
  "node_types": ["paragraph", "list", "code_block"],
  "contains_table": false,
  "contains_list": true,
  "contains_blockquote": false,
  "ast_strategy": "markdown_ast_sections_v1"
}
```

Az uj mezok elso korben manifest/Qdrant payload szinten elegendok lehetnek.
DB migracio csak akkor kell, ha valamit relaciosan is szurni akarunk.

## 8. Offset es forrashuseg

Nyitott technikai kockazat:

```text
Marko mennyire ad megbizhato forraspozicio / karakter-offset informaciot?
```

A jelenlegi rendszer chunkonkent tarol `char_start` / `char_end` ertekeket.
Ezeket az AST adapternek is elo kell allitania.

Elfogadhato megoldasok sorrendben:

1. Marko altal adott source position hasznalata, ha eleg pontos.
2. AST node szovegenek visszakeresese az eredeti normalizalt Markdownban.
3. Fallback: becsult offset + quality flag, ha pontos offset nem allithato elo.

Fontos:

```text
Az LLM-nek adott SOURCE szovegnek tovabbra is a tenyleges forrasszovegbol kell
szarmaznia. Az AST parser nem fogalmazhatja at a dokumentumot.
```

## 9. Kep- es attachment-hivatkozasok

Markdown fajlok gyakran tartalmaznak kep- vagy attachment-hivatkozasokat.

V1 dontes:

```text
Nem importalunk kepet vagy attachmentet.
```

Az `.md` fajlban szereplo hivatkozas forrasszovegkent megmaradhat, peldaul:

```markdown
![[image.png]]
![abra](attachments/image.png)
```

De:

- a kepfajl nem kerul importalasra,
- nincs OCR,
- nincs multimodal feldolgozas,
- a RAG csak a Markdown szoveggel dolgozik.

Ez tudatos hatar, nem hiba.

## 10. Bevezetesi terv

### 10.1 Spike

Cel:

```text
Bizonyitsuk vagy cafoljuk, hogy Marko AST alapu feldolgozas jobb chunkokat ad
a sajat Markdown korpuszon.
```

Feladatok:

1. Marko dependency ideiglenes/tervezett felvetele.
2. Kiserleti AST parse script vagy szolgaltatas.
3. 5-10 sajat Markdown minta feldolgozasa.
4. Osszehasonlito kimenet:
   - regi chunk szam,
   - uj chunk szam,
   - heading path,
   - chunk meretek,
   - code block egyben maradt-e,
   - nested listak hogyan viselkedtek,
   - par konkret chunk szovege.

Sikerfeltetel:

- az AST chunkok lathatoan jobban tartjak egyben a logikai egysegeket,
- nincs elfogadhatatlan lassulas,
- nincs forrasszoveg-vesztes,
- a kimenet beillesztheto a jelenlegi `KnowledgeStoredChunk` modellbe.

### 10.2 Adapter implementacio

Feladatok:

1. Uj parser adapter letrehozasa.
2. AST node-ok bejarasa heading contexttel.
3. AST node-okbol strukturalt chunk jeloltek epultetese.
4. Chunk jeloltek meret szerinti finomitasa.
5. Kimenet forditasa `MarkdownChunk` objektumokra.
6. Parser/chunking strategia nevek frissitese.

### 10.3 Bekotes importba

Elso opcio:

```text
Az uj parser legyen az alapertelmezett tudásbázis import parser.
```

Mivel jelenleg nincs megtartando tudásbázis dokumentum, nem kell regi
knowledge chunk kompatibilitassal szamolni.

Masodik, biztonsagosabb opcio:

```text
Konfiguracio kapcsolja, hogy line parser vagy Marko parser fusson.
```

Javaslat:

```text
Eredeti javaslatkent felmerult konfiguracios kapcsolo. A live teszt es a
tiszta kodbazis igenye alapjan vegul nem maradt ket parser: Marko/AST lett az
egyetlen aktiv import parser.
```

### 10.4 Indexeles es query

Az indexeles es query lenyegeben maradhat.

Ellenorizendo:

- Qdrant payload kapja meg az uj metadata mezoket, ha hasznosak,
- `heading_path` tovabbra is jol megjelenik,
- `quote_preview` es forraskartyak olvashatok maradnak,
- code blockos chunkok nem okoznak tul hosszu SOURCE blokkokat.

### 10.5 Tesztek

Minimum tesztek:

1. Frontmatter megmarad.
2. Heading path helyes.
3. Bevezeto bekezdes + code block + kovetkezmeny egy chunkban marad.
4. Nested lista nem esik szet feleslegesen.
5. Tabla egyben marad normal meretnel.
6. Blockquote egyben marad normal meretnel.
7. Tul nagy code block quality flaget kap.
8. Kep-hivatkozas szovegkent megmarad, de nincs attachment import.
9. Fatal encoding/empty file viselkedes nem romlik.
10. Import -> chunks.jsonl -> index -> query smoke tovabbra is mukodik.

## 11. Nem cel ebben a szeletben

Nem cel:

- Obsidian vault integracio,
- backlink/graf epites,
- attachment import,
- kep OCR vagy multimodal elemzes,
- alkalmazas-specifikus wikilink feloldas,
- jogszabalyi specializacio,
- ugyirat workflow-kba knowledge anyag beengedese.

## 12. Elfogadasi kriterium

A szelet akkor tekintheto kesznek, ha:

- van mukodo Marko/AST parser adapter,
- az uj parser a tudásbázis import utvonalon hasznalhato,
- az uj chunking strukturatudatos es tesztekkel fedett,
- az importalt chunk manifestek tartalmazzak a megorzendo metadata mezoket,
- a knowledge indexeles es query tovabbra is mukodik,
- nagyobb sajat Markdown korpuszon live smoke lefut,
- a felhasznalo altal ellenorzott valaszok es forraskartyak live hasznalatban
  jonak bizonyulnak.

## 13. Lezart dontes es aktualis allapot

A Marko/AST parser spike elfogadott v1 baseline lett.

Aktualis implementacio:

- `marko` dependency deklaralva a projektben,
- `app/services/markdown_parser.py` tartalmazza az aktiv AST parser
  implementaciot,
- parser: `markdown_marko_ast_parser_v1`,
- chunking strategy: `markdown_ast_sections_v1`,
- az AST parser ugyanabba a belso `ParsedMarkdownDocument` /
  `MarkdownChunk` modellbe fordit,
- a `Tudasbazis` importutvonal ezt hasznalja uj importokhoz,
- a regi soralapu parser implementacio, a kulon kiserleti AST modul es az
  old-vs-AST compare script el lett tavolitva.

Live elfogadas:

```text
121 Markdown dokumentum
2708 szovegresz
index kesz: 2708/2708
felhasznaloi live teszt alapjan jo minosegu RAG valaszok
```

Nyitott elv:

```text
Ne tuningoljuk tovabb altalanosan. Kovetkezo parser modositas csak konkret,
visszakeresheto rossz chunkolas vagy rossz forrasvalasz-pelda alapjan tortenjen.
```

## 14. Kovetkezo konkret lepes

Ebben a szeletben nincs tovabbi kotelezo parser munka. A Marko/AST parser
aktiv baseline.

A kovetkezo kozvetlen Tudasbazis-minosegi lepes ne a parser ujabb altalanos
tuningja legyen, hanem a retrieval reteg javitasa, mert a RAG valasz minoseget
elsosorban az hatarozza meg, hogy milyen chunkok kerulnek az LLM ele.

Javasolt kovetkezo szelet:

1. Pontosan dokumentalni es tesztekkel korulvenni, hogy a `semantic` es
   `hybrid` Tudasbazis retrieval jelenleg milyen sorrendben es milyen score
   alapjan valaszt chunkokat.
2. Markdown-aware hybrid scoring:
   - heading path egyezes vagy reszegyezes,
   - fenced code block jelenlet,
   - code language egyezes,
   - technikai token overlap,
   - pontos kifejezes egyezes,
   - keyword/semantic score kombinacio.
3. Query variansok:
   - a felhasznaloi kerdes termeszetes nyelvu alakja maradjon elso query,
   - determinisztikus technikai/kulcsszo jellegu variansok bovitsék a
     candidate setet,
   - a vegso kimenet deduplikalt legyen.
4. Kontextusbovites:
   - egy jo talalat melle opcionálisan beemelheto az elozo/kovetkezo chunk,
     ha ugyanabban a dokumentumban es ugyanazon vagy kompatibilis heading alatt
     van,
   - kulonosen hasznos magyarazat + kodblokk + kovetkezmeny jellegu
     jegyzeteknel.
5. Vegso sorrend:
   - a retrieval tovabbra is relevancia szerint valasszon,
   - az LLM-nek adott SOURCE blokkok viszont maradjanak dokumentum /
     heading / chunk sorrendben, hogy a modell osszefuggo kontextust lasson.
6. Reranking csak akkor keruljon be, ha a fenti determinisztikus jelek
   kevesnek bizonyulnak.

Nem cel:

- keyword mode tulbonyolitasa,
- LLM-alapu reranker elso korben,
- ujabb parsercsere,
- Obsidian- vagy alkalmazasspecifikus szemantika.
