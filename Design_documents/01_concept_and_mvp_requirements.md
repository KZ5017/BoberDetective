# Lokális Nyomozati Iratintelligencia Rendszer
## Koncepció és MVP-követelmények

## 1. Projektcél

A projekt célja egy lokálisan futó, auditálható, ember által ellenőrzött nyomozati iratfeldolgozó és döntéstámogató rendszer megtervezése, amely nagy mennyiségű nyomozati, vizsgálati vagy igazságszolgáltatási dokumentumból strukturált, forráshivatkozott elemzéseket készít.

A rendszer elsődleges feladata nem az, hogy önálló nyomozati, jogi vagy személyi döntést hozzon, hanem az, hogy az iratanyag feldolgozását, áttekintését, keresését, összekapcsolását és ellenőrzését hatékonyabbá tegye.

A rendszer alapmondata:

> Lokálisan futó, auditálható nyomozati iratfeldolgozó és döntéstámogató rendszer, amely nagy mennyiségű dokumentumból strukturált, forráshivatkozott, ember által ellenőrizhető elemzéseket készít, de nem hoz önálló jogi, nyomozati vagy személyi döntést.

## 2. Alapelvek

### 2.1 Lokális működés

A rendszer érzékeny nyomozati, vizsgálati vagy igazságszolgáltatási adatokkal dolgozhat, ezért az elsődleges követelmény a lokális, offline vagy zárt hálózati környezetben történő működés.

A feldolgozott dokumentumok, indexek, embeddingek, lekérdezések, modellválaszok és naplók nem kerülhetnek külső szolgáltatóhoz vagy nyilvános felhőbe.

### 2.2 Emberi kontroll

A rendszer minden elemzése emberi ellenőrzésre szánt előzetes feldolgozásnak minősül. A rendszer nem helyettesíti a nyomozót, ügyészt, bírót, védőt, szakértőt vagy más eljárási szereplőt.

A rendszer által jelzett következtetések, ellentmondások, hiányok és kapcsolatok csak akkor használhatók fel érdemben, ha azokat ember ellenőrizte.

### 2.3 Forrásalapú működés

A rendszer egyik legfontosabb szabálya:

> Nincs forrás → nincs állítás.

Minden generált állításhoz, összefoglalóhoz, eseményhez, ellentmondáshoz és hiányjelzéshez kapcsolódnia kell konkrét forráshelynek.

Egy forráshivatkozás minimális elemei:

- dokumentumazonosító,
- dokumentumnév,
- oldalszám vagy szövegrész-azonosító,
- releváns idézett vagy kivonatolt szövegrész,
- feldolgozási időpont,
- confidence / bizonyossági érték,
- emberi ellenőrzés státusza.

### 2.4 Auditálhatóság

A rendszer minden fontos műveletét naplózni kell:

- dokumentum importálása,
- OCR / szövegkinyerés,
- dokumentumdarabolás,
- embedding generálás,
- indexelés,
- lekérdezés,
- retrieval találatok,
- modellnek átadott kontextus,
- modellválasz,
- emberi módosítás,
- exportálás.

A cél az, hogy utólag rekonstruálható legyen, hogy egy adott elemzés hogyan jött létre.

### 2.5 Nem döntéshozó rendszer

A rendszer nem hozhat önálló jogi, nyomozati vagy személyi döntést. A rendszer nem minősíthet személyeket, nem állapíthat meg bűnösséget, nem javasolhat automatikus eljárási kényszerintézkedést, és nem helyettesítheti a jogi vagy nyomozati mérlegelést.

## 3. Nem célok

Az első verzióban és általános tervezési alapelvként a rendszer nem végezheti az alábbiakat:

- automatikus gyanúsítás,
- személyek kockázati pontozása,
- prediktív nyomozás,
- profilalkotás önálló döntési céllal,
- arcfelismerés vagy biometrikus azonosítás,
- automatikus jogi minősítés,
- bűnösség vagy ártatlanság megállapítása,
- vallomások hitelességének végleges eldöntése,
- bírói, ügyészi, nyomozói vagy védői döntések helyettesítése,
- automatikus eljárási javaslat kiadása emberi kontroll nélkül.

A rendszer tehát nem azt mondja meg, hogy „ki követte el”, hanem azt, hogy „az iratok alapján milyen állítások, események, kapcsolatok, ellentmondások és hiányok azonosíthatók, és ezek hol találhatók a forrásanyagban”.

## 4. Elsődleges felhasználók

A rendszer lehetséges felhasználói:

- nyomozó,
- vizsgáló,
- ügyész,
- bíró,
- védő,
- igazságügyi szakértő,
- belső ellenőrzési vagy compliance munkatárs.

Az MVP-1 elsődleges célfelhasználója:

> Nyomozó / vizsgáló, aki nagy mennyiségű iratanyagot szeretne gyorsabban áttekinteni, rendszerezni és ellenőrizni.

## 5. Fő használati esetek

### 5.1 Iratanyag áttekintése

A felhasználó egy ügyhöz dokumentumokat importál. A rendszer feldolgozza azokat, majd létrehoz egy strukturált ügyáttekintést.

Kimenetek:

- dokumentumlista,
- dokumentumtípusok,
- fő szereplők,
- fő események,
- releváns dátumok,
- visszatérő helyszínek,
- elsődleges ügyösszefoglaló.

### 5.2 Szereplők azonosítása

A rendszer kigyűjti az iratokban előforduló személyeket, szervezeteket, cégeket, hatóságokat és egyéb releváns entitásokat.

Lehetséges mezők:

- név,
- szerep,
- előfordulások száma,
- kapcsolódó dokumentumok,
- kapcsolódó események,
- azonosítás bizonyossága,
- névegyezési / névvariációs problémák.

### 5.3 Idővonal készítése

A rendszer az iratokból dátumokat, időpontokat és eseményeket nyer ki, majd strukturált idővonalat készít.

Az idővonal minden eleme forráshivatkozott.

Példa:

| Időpont | Esemény | Forrás | Bizonyosság | Megjegyzés |
|---|---|---|---|---|
| 2024.03.12. 18:42 | Telefonhívás X és Y között | Híváslista, 14. oldal | magas | időbélyeg közvetlenül dokumentumból |
| 2024.03.12. kb. 19:00 | Tanú szerint X a helyszínen volt | Tanúvallomás, 3. oldal | közepes | vallomásból származó állítás |

### 5.4 Állításlista készítése

A rendszer kigyűjti az iratokban szereplő releváns állításokat.

Egy állítás rekordja tartalmazza:

- az állítás szövegét,
- ki állította,
- kire vagy mire vonatkozik,
- melyik dokumentumból származik,
- milyen időponthoz kapcsolódik,
- milyen eseményhez kapcsolódik,
- van-e más dokumentummal való kapcsolat vagy ellentmondás,
- bizonyossági szint.

### 5.5 Ellentmondások jelzése

A rendszer potenciális ellentmondásokat jelezhet, de nem döntheti el azok valódi jelentőségét.

Példa:

> Az egyik dokumentum szerint X személy 19:00 körül a helyszínen tartózkodott. Egy másik dokumentum szerint X személyhez köthető telefon 19:02-kor más településen jelent meg. A jelzés emberi ellenőrzést igényel.

Az ellentmondásjelzés nem bizonyíték és nem végleges következtetés, hanem vizsgálati figyelemfelhívás.

### 5.6 Hiányok jelzése

A rendszer azonosíthat olyan pontokat, ahol az iratok egy dokumentumra, mellékletre, bizonyítékra vagy vizsgálati lépésre hivatkoznak, de az adott elem nem található meg az importált anyagban.

Példa:

> A jegyzőkönyv kamerafelvételre hivatkozik, de az importált dokumentumok között nem található lefoglalási jegyzőkönyv, szakértői vizsgálat vagy képkocka-melléklet.

### 5.7 Bizonyítékmátrix készítése

A rendszer későbbi fázisban képes lehet bizonyítékmátrixot készíteni egy adott téma, esemény vagy jogszabályi tényállási elem köré.

Az MVP-1-ben ez még nem feltétlenül jogszabályi alapon működik, hanem inkább ügytémák szerint:

- adott eseményhez tartozó források,
- adott személyhez tartozó állítások,
- adott időszakhoz tartozó bizonyítékok,
- adott helyszínhez tartozó dokumentumok.

## 6. Bemeneti dokumentumtípusok

Az MVP-1 célzott bemeneti formátumai:

- PDF,
- szkennelt PDF,
- DOCX,
- TXT,
- HTML,
- e-mail export,
- egyszerű CSV / táblázatos adatok későbbi fázisban,
- chat export későbbi fázisban.

Az első prototípusban a legfontosabb dokumentumtípusok:

- jegyzőkönyvek,
- vallomások,
- határozatok,
- szakértői vélemények,
- lefoglalási jegyzőkönyvek,
- hivatalos levelezések,
- egyszerű mellékletek.

## 7. Dokumentumfeldolgozási követelmények

### 7.1 Import

A rendszernek ügyenként kell kezelnie a dokumentumokat. Egy ügy egy elkülönített munkaterület.

Minden importált fájlhoz rögzíteni kell:

- fájlnév,
- fájltípus,
- fájlméret,
- hash érték,
- importálás időpontja,
- importáló felhasználó,
- feldolgozási státusz.

### 7.2 OCR és szövegkinyerés

> **Aktualis megjegyzes, 2026-05-17:** a kovetelmeny tovabbra is ervenyes, de a megvalositott workflow explicit text-review pontot vezetett be. Native PDF parse vagy OCR utan oldalszintu text layer jon letre, majd csak felhasznaloi jovahagyas utan keszulnek chunkok. Reszletek: `Design_documents/06_document_processing_pipeline_v1.md`.

A rendszernek különbséget kell tennie:

- natív szöveget tartalmazó dokumentum,
- szkennelt dokumentum,
- vegyes dokumentum,
- hibásan olvasható dokumentum között.

OCR után meg kell őrizni:

- az eredeti fájlt,
- az OCR-rel kinyert szöveget,
- az oldalszintű szöveget,
- az OCR confidence értékeket, ha rendelkezésre állnak.

### 7.3 Darabolás / chunkolás

> **Aktualis megjegyzes, 2026-05-17:** a jelenlegi chunkolas page-local `char_window_v2`, paragraph/sentence/line/space/hard-limit hatarpreferenciakkal. A chunkok nem nyulnak at oldalhataron a forrashely-huseg miatt. Reszletek: `Design_documents/06_document_processing_pipeline_v1.md`.

A dokumentumokat olyan egységekre kell bontani, amelyek visszakereshetők és forráshivatkozhatók.

A chunkok minimális metaadatai:

- ügyazonosító,
- dokumentumazonosító,
- oldalszám,
- chunk sorszám,
- karakterpozíció vagy szövegrész-azonosító,
- chunk szövege,
- embedding azonosító,
- feldolgozási verzió.

## 8. Kimeneti elemzések

Az MVP-1 által előállított fő kimenetek:

1. dokumentumlista,
2. ügyösszefoglaló,
3. szereplőlista,
4. idővonal,
5. állításlista,
6. potenciális ellentmondáslista,
7. potenciális hiánylista,
8. forráshivatkozott keresési válaszok.

Minden kimenetnél kötelező:

- forráshivatkozás,
- bizonyossági szint,
- emberi ellenőrzés státusza,
- generálás időpontja,
- használt modell és feldolgozási verzió.

## 9. Technikai alapelvek

### 9.1 Lokális LLM

A rendszer lokálisan futó nyelvi modellt használ. A modell feladata nem az, hogy belső tudásból válaszoljon, hanem az, hogy a lokálisan visszakeresett dokumentumrészleteket strukturált elemzéssé alakítsa.

### 9.2 RAG-alapú működés

A rendszer retrieval-augmented generation elven működik:

1. dokumentumok feldolgozása,
2. indexelés,
3. releváns részletek visszakeresése,
4. modellnek csak a releváns kontextus átadása,
5. strukturált, forráshivatkozott válasz generálása.

### 9.3 Hybrid search

A későbbi pontos működéshez nem elég kizárólag vektoros keresés. Javasolt a hybrid search:

- kulcsszavas keresés,
- vektoros szemantikus keresés,
- metaadat-alapú szűrés,
- esetleges reranking.

### 9.4 Strukturált output

A modell válaszait lehetőleg strukturált formában kell kérni és tárolni:

- JSON,
- táblázatos forma,
- validálható séma,
- exportálható jelentés.

A strukturált output segíti az ellenőrzést, az auditálást és a későbbi UI-megjelenítést.

## 10. Biztonsági követelmények

A rendszernek az alábbi biztonsági alapelveket kell követnie:

- lokális adattárolás,
- ügyenként elkülönített adattér,
- hozzáférés-kezelés,
- felhasználói szerepkörök,
- naplózás,
- fájlintegritás hash alapján,
- eredeti dokumentumok változatlan megőrzése,
- exportok naplózása,
- modellválaszok verziózása,
- érzékeny adatok véletlen kiszivárgásának minimalizálása.

## 11. Auditálási követelmények

A rendszerben minden generált elemzésnek visszavezethetőnek kell lennie az alábbiakra:

- melyik dokumentumokból dolgozott,
- melyik chunkokat használta,
- milyen prompt vagy elemzési sablon alapján futott,
- milyen modellverzióval készült,
- mikor készült,
- ki indította,
- módosította-e ember,
- elfogadta-e ember,
- exportálták-e.

Az audit log célja nem csak technikai hibakeresés, hanem eljárási és szakmai visszaellenőrizhetőség.

## 12. Jogszabályi RAG modul helye

A magyar jogszabályi tudásbázis nem az MVP-1 legelső eleme, hanem az MVP-2 vagy MVP-3 egyik kiemelt modulja.

Indoklás:

Először stabilan meg kell oldani az iratok feldolgozását, kereshetőségét, forráshivatkozását és strukturált elemzését. Ha ez nem megbízható, akkor a jogszabályi réteg is bizonytalan alapra épülne.

A későbbi jogszabályi modul javasolt működése:

- magyar jogszabályi korpusz lokális indexelése,
- jogszabályi rendelkezések strukturált feldolgozása,
- joghelyek visszakeresése,
- jogszabályi tényállási elemek tárolása,
- bizonyítékok tényállási elemekhez rendelése,
- minden jogi állítás joghelyhez kötése.

Fontos:

A modell nem „fejből” ismeri a jogot, hanem lokálisan indexelt, ellenőrzött jogszabályi forrásokból dolgozik.

## 13. MVP-1 funkciólista

Az első MVP javasolt funkciói:

1. Ügy létrehozása.
2. Dokumentumok importálása.
3. Fájlintegritási hash generálása.
4. PDF / DOCX / TXT szövegkinyerés.
5. OCR szkennelt PDF-ekre.
6. Oldalszintű szövegtárolás.
7. Dokumentumdarabolás chunkokra.
8. Lokális keresőindex építése.
9. Személyek, dátumok, helyszínek előzetes felismerése.
10. Forráshivatkozott keresés.
11. Automatikus szereplőlista készítése.
12. Automatikus idővonaljavaslat készítése.
13. Állításlista készítése.
14. Potenciális ellentmondások jelzése.
15. Potenciális hiányok jelzése.
16. Ügyösszefoglaló készítése.
17. Minden elemzés auditnaplózása.
18. Emberi ellenőrzési státusz kezelése.
19. Exportálható jelentés készítése.

## 14. MVP-1-ből szándékosan kihagyott funkciók

Az első verzióból szándékosan kimarad:

- automatikus jogi minősítés,
- teljes magyar jogszabályi RAG,
- prediktív elemzés,
- személyi kockázati scoring,
- arcfelismerés,
- hangfelismerés,
- videóelemzés,
- automatikus eljárási javaslat,
- más rendszerekkel való éles integráció,
- felhőalapú feldolgozás.

## 15. Későbbi modulok

Lehetséges későbbi fejlesztési irányok:

### MVP-2: Jogszabályi RAG

- magyar jogszabályi korpusz indexelése,
- joghelyek visszakeresése,
- tényállási elemek kezelése,
- bizonyítékmátrix jogszabályi elemekhez.

### MVP-3: Fejlettebb bizonyítékmátrix

- eseményalapú bizonyítéki kapcsolatok,
- személyalapú bizonyítéki kapcsolatok,
- forráserősség jelölése,
- emberi validálás.

### MVP-4: Ügyösszehasonlítás

- hasonló mintázatok keresése ügyeken belül,
- csak anonimizált vagy megfelelően jogosított környezetben,
- prediktív policing nélkül.

### MVP-5: Speciális adatforrások

- chat exportok,
- e-mail postafiók exportok,
- híváslisták,
- cellainformációk,
- pénzügyi táblázatok,
- naplófájlok.

## 16. Tesztelési stratégia

A rendszert első körben nem valódi érzékeny adatokon, hanem szintetikus vagy anonimizált iratanyagon kell tesztelni.

Tesztelési célok:

- dokumentumfeldolgozás pontossága,
- OCR minősége,
- entitásfelismerés pontossága,
- idővonal helyessége,
- forráshivatkozások pontossága,
- hallucination arány,
- hamis ellentmondásjelzések aránya,
- kihagyott releváns elemek aránya,
- emberi ellenőrzési idő csökkenése.

## 17. Minőségi mérőszámok

Lehetséges mérőszámok:

- dokumentumfeldolgozási sikerarány,
- OCR confidence átlag,
- entity extraction precision / recall,
- timeline event precision / recall,
- citation accuracy,
- unsupported claim rate,
- hallucination rate,
- false contradiction rate,
- human review acceptance rate,
- feldolgozási idő dokumentumonként,
- emberi időmegtakarítás becslése.

Kiemelten fontos mérőszám:

> Unsupported claim rate: milyen gyakran állít a rendszer olyat, amelyhez nincs megfelelő forráshely.

Ennek az értéknek ideális esetben nullához kell közelítenie.

## 18. Javasolt első fejlesztési sorrend

1. Dokumentumimport és ügykezelés.
2. Szövegkinyerés és OCR.
3. Oldalszintű tárolás.
4. Chunkolás és metaadatolás.
5. Lokális keresőindex.
6. Forráshivatkozott keresés.
7. Lokális LLM integráció.
8. Strukturált válaszformátumok.
9. Szereplőlista.
10. Idővonal.
11. Állításlista.
12. Ellentmondásjelzés.
13. Hiányjelzés.
14. Audit log.
15. Exportálható jelentés.

## 19. Első technológiai döntési pontok

A következő tervezési fázisban az alábbi technológiákról kell dönteni:

- OCR motor,
- dokumentumparser,
- embedding modell,
- lokális LLM,
- vektoradatbázis,
- kulcsszavas keresőmotor,
- reranker,
- háttéradatbázis,
- backend nyelv és framework,
- frontend / UI,
- audit log formátuma,
- exportformátumok.

## 20. Összefoglalás

Az MVP-1 célja nem egy teljes jogi vagy nyomozati AI-rendszer létrehozása, hanem egy stabil, lokálisan futó, auditálható iratfeldolgozó mag kialakítása.

A rendszer első verziójának legfontosabb értéke:

- nagy iratmennyiség gyorsabb áttekintése,
- szereplők és események strukturálása,
- idővonal építése,
- állítások forráshoz kötése,
- ellentmondások és hiányok jelzése,
- emberi ellenőrzés támogatása.

A projekt hosszú távú célja egy olyan döntéstámogató rendszer kialakítása, amely a nyomozati és igazságszolgáltatási munkát hatékonyabbá, átláthatóbbá és ellenőrizhetőbbé teszi anélkül, hogy emberi döntéseket helyettesítene.
