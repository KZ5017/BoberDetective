# 12. Source-Bound Findings Model Plan

## 0. Aktualisitas

Frissitve: 2026-05-23.

Ez a dokumentum mar a legujabb dontest rogziti: a `research_finding` nem vegleges review-objektum es nem perzisztens szakmai talalatlista, hanem atmeneti kutatasi munkalista-elem. Review, merge, forrasmozgatas es export szempontbol csak az az objektum szamit rendes strukturalt talalatnak, amelyet a felhasznalo a kutatasi talalatbol kezzel letrehozott.

Aktualis pontositas: a kutatasi talalatbol letrehozott strukturalt objektumoknal a kesobbi merge / forrasmozgatas / leválasztott forras visszacsatolas fo objektumtipushoz kotott, de altipushoz nem. Ez tudatos rugalmassag: az emberi konverzio soran elofordulhat teves altipusvalasztas, ezert egy `claim`, `event`, `entity` vagy `missing_item_candidate` a sajat fo tipuson belul szabadabban rendezheto, mikozben a fo tipusok kozotti atjaras tovabbra sem automatikus.

Aktualis fo workflow:

```text
forraskereses -> kutatasi talalat munkalista -> emberi dontes -> strukturalt objektum vagy meglevo strukturalt objektumhoz csatolt forras
```

Ha a kutatasi talalatbol uj strukturalt objektum keszul, vagy a kutatasi talalat forrashivatkozasa meglevo strukturalt objektumhoz kerul, a kutatasi talalat tobbe nem jelenik meg az aktiv munkalistaban. A celobjektum hordozza tovabb a forrashivatkozast es a szakmai feldolgozas szempontjabol relevans allapotokat. A kutatasi talalat ilyenkor `converted` provenance rekordkent megmarad `target_object_type` / `target_object_id` kapcsolattal; a talalat LLM-metaadata nem irja at automatikusan a celobjektum szoveges tartalmat.

## 1. Cel

Ez a dokumentum az uj, forrashely-kozpontu kutatasi modellt rogziti.

A jelenlegi tapasztalatok alapjan a nyers szovegresz-alapu automatikus modulok tul koran kenyszeritik ra az LLM-re az objektumtipust:

- allitas,
- esemeny,
- entitas,
- hianyzo iratjelolt,
- osszefoglalo elem.

Ez kulonosen helyi, kisebb LLM modelleknel zajos es mesterseges talalatokat eredmenyezhet. A modell gyakran megprobal megfelelni a kivalasztott modulnak, akkor is, ha a talalt forrashely inkabb altalanosan relevans reszlet, nem pedig tiszta esemeny vagy allitas.

Az uj celmodell:

```text
elobb forrasalapu kutatasi talalat,
utana emberi dontes es strukturalt objektumma alakitas.
```

## 2. Alapelv

Az LLM tovabbra sem forrasigazsag.

Forrasigazsag:

- eredeti dokumentum,
- aktualis oldalszoveg,
- aktualis szovegresz,
- source reference,
- analysis run,
- audit es review dontes.

Kotelezo szabaly:

```text
No source -> no claim.
```

Az uj modell ezt nem gyengiti, hanem elorebb hozza a forrashoz kotottseget. Az LLM elso korben nem vegleges allitast vagy esemenyt hoz letre, hanem forrashoz kotott kutatasi munkalista-elemet. Ez az elem onmagaban nem resze a review reportnak, es nem tekintendo szakmailag ellenorzendo objektumnak.

## 3. Uj koztes objektum: Source-Bound Finding

Magyar UI nev:

```text
Kutatási találat
```

Javasolt technikai nev:

```text
research_finding
```

Ez az objektum nem azonos a jelenlegi `claim`, `event`, `entity`, `missing_item_candidate` vagy `summary_item` objektumokkal.

Feladata:

- megorizni, hogy egy adott QUERY alapjan mely forrashely tunt relevansnak,
- rogziteni a modell rovid, forrashu magyarazatat,
- nem kenyszeriteni az eredmenyt tul koran strukturalt objektumtipusba,
- lehetove tenni, hogy a felhasznalo dontse el, mi legyen belole,
- engedni, hogy a felhasznalo felretegye vagy torolje a nem hasznos keresesi eredmenyeket,
- kesobbi kapcsolatgraf-nezeti hasznalatot megalapozni anelkul, hogy most graf-adatbazist vezetnenk be.

## 4. Javasolt mezok

Elso adatmodell-szint:

```text
id
case_id
analysis_run_id
source_reference_id
title
finding_text
suggested_type
suggested_type_reason
relevance_reason
conversion_status
target_object_type
target_object_id
created_at
updated_at
```

### 4.1 `source_reference_id`

Kotelezo.

Minden talalatnak konkret forrasa van:

- dokumentum,
- oldal/szovegresz,
- pontos idezet,
- szovegkornyezet.

Forras nelkuli talalat nem mentheto.

### 4.2 `title`

Rovid, ember altal olvashato cim.

Nem lehet jogi minosites, nem lehet bunosseg- vagy felelosseg-megallapitas.

### 4.3 `finding_text`

Rovid leiras arrol, hogy a forrashely miert relevans a QUERY szempontjabol.

Ez nem vegleges, ellenorzott tenyallitas. UI-ban is jelolni kell:

```text
Kutatási találat
```

nem:

```text
Bizonyitott teny
```

### 4.4 `suggested_type`

Nem kotelezo, nem forrasigazsag, csak tipusjavaslat.

Javasolt ertekek:

```text
claim
event
entity
document_reference
other
```

Magyar UI:

```text
Allitasjelolt
Esemenyjelolt
Entitasjelolt
Iratutalas-jelolt
Egyeb relevans talalat
```

Fontos:

```text
other
```

nem hibaallapot. Ez a biztonsagos alapertelmezett kategoria, ha a talalat relevans, de nem sorolhato tisztan a strukturalt objektumok koze.

### 4.5 `suggested_type_reason`

Rovid indoklas, hogy a modell miert javasolta az adott tipust.

Ez segit a felhasznalonak, de nem dont helyette.

### 4.6 `relevance_reason`

Rovid, QUERY-hez kotott indoklas.

Ennek nem az a celja, hogy uj informaciot allitson, hanem hogy megmutassa:

```text
miert ez a forrashely kerult elo a fokuszszovegre.
```

### 4.7 `conversion_status`

Jelzi, hogy a kutatasi munkalista-elemmel mi tortent.

Aktualis ertekek:

```text
not_converted
converted
ignored
```

Jelentes:

- `not_converted`: aktiv munkalista-elem, atalakitando vagy torolheto,
- `ignored`: felretett munkalista-elem, kesobb visszahozhato,
- `converted`: strukturalt objektumma alakult, az aktiv munkalistaban mar nem jelenik meg.

Fontos: az `ignored` nem szakmai elutasitas es nem review dontes. Csak munkalista-szervezesi allapot.

Ha `converted`, akkor a kapcsolatot celmezo rogzitette:

```text
target_object_type
target_object_id
```

Elso verzios implementacioban ez kozvetlen celmezo. A modellt ugy kell kialakitani, hogy kesobb kapcsolattablava bovitheto legyen, mert egy talalat vagy forrashely tobb strukturalt objektumhoz is kapcsolodhat.

Pelda:

```text
egy forrasalapu talalat -> egy allitas
egy forrasalapu talalat -> egy esemeny
egy forrasalapu talalat -> egy entitas
```

Ez kesobbi grafnezeti szempontbol fontos.

### 4.8 Torles es megtartas

A kutatasi talalat munkalista-elem, ezert az atalakitott vagy meg nem alakitott munkalista-kezelese nem azonos a strukturalt objektumok audit/review logikajaval.

Szabalyok:

- `not_converted` es `ignored` talalat torolheto a munkalistabol,
- a torles nem review dontes es nem igenyel audit esemenyt,
- `converted` talalatot nem mutatunk az aktiv listaban,
- a konverzio utan letrejott strukturalt objektum a sajat forrashivatkozasaval es provenance-aval el tovabb,
- a konverzio tenye tovabbra is megorizheto a research finding sorban torteneti/graf-kompatibilitasi celra, de ez nem felhasznaloi munkalista-elem.

### 4.9 Kapcsolatgraf-kompatibilitas

Az uj modellnek mar az elso adatbazis-tervben tamogatnia kell, hogy kesobb kapcsolatgraf epulhessen belole.

Ez nem jelent graf-adatbazis bevezetest. A cel tovabbra is PostgreSQL-rel indul, relacios kapcsolatokkal.

Kesobbi graf csomopontok lehetnek:

```text
case
document
page
chunk
source_reference
research_finding
claim
event
entity
contradiction_candidate
```

Kesobbi graf elek lehetnek:

```text
document -> contains -> chunk
chunk -> supports -> source_reference
source_reference -> supports -> research_finding
research_finding -> suggests_type -> suggested_type
research_finding -> converted_to -> claim/event/entity
research_finding -> mentions -> entity
claim -> supported_by -> source_reference
event -> supported_by -> source_reference
entity -> mentioned_in -> source_reference
claim -> contradicts -> claim
```

Elso lepesben eleg, ha a `research_finding` stabilan kapcsolodik:

- ugyhoz,
- analysis runhoz,
- source reference-hez,
- opcionlis celobjektumhoz.

De a schema ne zarja ki, hogy kesobb tobb kapcsolatot is rogzitsunk.

Javasolt kesobbi bovites:

```text
research_finding_links
```

Mezok:

```text
id
case_id
source_finding_id
target_object_type
target_object_id
link_type
created_at
created_by_user_id
```

Pelda `link_type` ertekek:

```text
converted_to
mentions
supports
related_to
derived_from
contradicts
```

Fontos: ezt nem kell az elso minimalis implementacioban teljesen megvalositani, de a `research_findings` schema ne legyen olyan szuk, hogy kesobb csak rombolassal lehessen grafiranyba boviteni.

## 5. Uj keresesi workflow

### 5.1 Felhasznaloi mentalis modell

A fo kerdes:

```text
Mit keresel az iratokban?
```

Pelda fokuszok:

```text
amit a matrózról tudni lehet
matrózzal megtörtént események
az orangután bejutásával kapcsolatos részletek
hivatkozott mellékletek és csatolmányok
```

A felhasznalo nem modulbol indul, hanem kutatasi celbol.

### 5.2 Technikai forraskivalasztas

Megmaradhatnak a mar jol mukodo forrasszukito elemek:

- forraskor: teljes ugy vagy kivalasztott irat,
- dokumentumtaxonomia szurok,
- konkret iratok listaja,
- oldaltartomany egyetlen kivalasztott iratnal,
- keyword / semantic / hybrid retrieval,
- szovegresz plafon,
- batch meret.

Ezek tovabbra is forrashelyeket valasztanak ki. A kulonbseg az, hogy az LLM nem elore megadott objektumtipusra dolgozik, hanem altalanos forrasalapu talalatokat keszit.

### 5.3 LLM feladat

Az uj prompt celja:

```text
Keresd meg a QUERY szempontjabol relevans, forrassal alatamasztott talalatokat.
Ha a talalat inkabb allitas, esemeny, entitas vagy iratutalas, javasolj tipust.
Ha nem sorolhato biztosan egyikbe sem, hasznald az other tipust.
Ne eroltesd egyik kategoriat sem.
```

A modellnek minden talalatnal kotelezo:

- `quote_text`,
- `source_label`,
- `relevance_reason`.

Tipusjavaslat nem kotelezo ereju.

## 6. Kimeneti JSON vazlat

Elso verzios javaslat:

```json
{
  "findings": [
    {
      "source_label": "chunk_1",
      "quote_text": "...",
      "title": "...",
      "finding_text": "...",
      "suggested_type": "other",
      "suggested_type_reason": "...",
      "relevance_reason": "..."
    }
  ]
}
```

Validacio:

- `quote_text` karakterpontosan szerepeljen a hivatkozott SOURCE chunkban,
- `source_label` letezzen az adott batchben,
- az aktualis prompt azert keri a `source_label` mezot elso mezokent, mert a helyi modell igy kevesebbszer hagyja ki,
- `suggested_type` csak allowlistbol johet,
- forras nelkuli elem nem mentheto,
- JSON hibakat ugyanugy kezelni kell, mint a jelenlegi moduloknal.

## 7. Strukturalt objektumma alakitas

A `research_finding` onmagaban nem reviewolhato strukturalt objektum. Ez csak kutatasi munkalista-elem.

Felhasznaloi muveletek:

```text
Allitas letrehozasa ebbol
Esemeny letrehozasa ebbol
Entitas letrehozasa ebbol
Iratutalas-jelolt letrehozasa ebbol
Felretetel
Vissza az aktiv listaba
Torles
```

Az atalakitott objektum tovabbra is:

- source reference-hez kotott,
- analysis runhoz vagy manual/conversion runhoz kotott,
- audit es review folyamatban kovetheto.

Konverzio utan is meg kell orizni a kapcsolatot az eredeti `research_finding` es a letrejott strukturalt objektum kozott. Ez kesobb a grafnezeti megjelenites egyik alapja lesz:

```text
forrashely -> finding -> strukturalt objektum
```

Felhasznaloi szempontbol azonban a konvertalt kutatasi talalat mar nem munkalista-elem. A felhasznalo a letrejott strukturalt objektummal dolgozik tovabb.

Aktualis UI-hely:

```text
Kutatási találatok panel -> jobb oldali munkaterulet teteje
Áttekintési jelentés -> alatta, mar strukturalt objektumokkal
```

## 8. Meglevo kezi workflow-k helye

Meg kell tartani es az uj modellhez kell illeszteni:

- kijelolt szovegreszbol kezi objektum letrehozasa,
- levalasztott forrasbol kezi objektum letrehozasa,
- forras mozgatasa,
- forras levalasztasa,
- forras visszacsatolasa,
- merge workflow-k,
- kezi ellentmondasjelolt letezo claim-parbol.

Ezek az uj modellben is hasznosak, mert emberi kontrollos, forraskotott muveletek.

## 9. Nem cel az elso lepcsoben

Az elso finding-alapu keresesi modell ne probalja megoldani:

- automatikus ugyosszefoglalot,
- automatikus hianyzo irat-detekciot,
- automatikus ellentmondasdetekciot nyers chunkokbol,
- jogi minositest,
- bunosseg vagy felelosseg megallapitasat.

Ezek mas workflow-t igenyelnek.

## 10. Szakmai kovetkezmeny

Az uj modellben a rendszer fo mukodese:

```text
forrashelyeket keres,
forrasalapu talalatokat javasol,
emberi dontes utan strukturalt objektumot hoz letre.
```

Ez jobban illeszkedik:

- a helyi LLM korlataihoz,
- a magyar nyelvu forrasanyaghoz,
- a no source -> no claim szabalyhoz,
- a nagy iratmennyisegu ugyek valos kutatasi workflow-jahoz.

## 11. Kesobbi grafnezeti irany

A finding-alapu modell kesobb alkalmas lehet kapcsolatgraf vizualizalasara.

Nem cel most:

- graf-adatbazis bevezetese,
- teljes kapcsolati ontologia megtervezese,
- automatikus gyanusitotti vagy felelossegi graf epites,
- szemelyek kockazati vagy bunossegi rangsorolasa.

Cel most:

- minden relevans talalat legyen stabilan forrashoz kotve,
- a talalat es a belole letrejovo objektum kozotti technikai kapcsolat ne vesszen el, akkor sem, ha a talalat mar nem jelenik meg munkalista-elemkent,
- a kesobbi graf csomopontok es elek relaciosan visszafejthetok legyenek,
- az audit es review dontesek a grafnezeti kapcsolatoknal is figyelembe vehetok legyenek.

Ez lehetove teszi, hogy kesobb a frontend grafnezete ne nyers LLM-asszociaciokra epuljon, hanem auditalt, forraskotott, ember altal ellenorzott kapcsolatokra.
