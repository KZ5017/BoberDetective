# 14. Work Surface UI Architecture Plan

## 0. Aktualisitas

Frissitve: 2026-06-03.

Ez a dokumentum a kovetkezo frontend iranyt rogziti: a jelenlegi, vizualisan stabil ketoszlopos munkapad ne tovabb zsufolodjon, hanem keruljon egy tobb munkafeluletet kezelo alkalmazasvaz ala.

Aktualis dontes:

```text
nem ujabb panelek a jelenlegi oldalra,
hanem kozos AppShell + kulon munkafeluletek.
```

Aktualis implementacios allapot:

```text
shell/surface-navigation szelet: kesz, bal oldali sidebar aktiv
Ügy munkapad: mukodo, elemzes/kutatasi talalat/review munkafelületre szukitve
Teljes iratfeldolgozás: backend-kapcsolt, person-profile munkafelület
Audit napló: placeholder
Iratgyujtemeny/source-scope layer: mukodo backend/frontend, search_findings es index scope integracioval
```

2026-06-03 allapot:

```text
Irat rendező: alapertelmezett munkafelület, iratimport + iratlista bal oldalon, iratgyujtemenyek jobb oldalon
Ügy munkapad: Szemantikus index állapot + Utolsó kutatási keresés felso statuszsorban
Ügy munkapad fo arany: Elemzes 0.8fr, Kutatási találatok 1.2fr
Sidebar: keskenyebb, modellek egymas alatt, modellkartyan belul bal oldalt statusz, jobb oldalt gombok
Vizualis nyelv: halkabb betusulyok, laposabb gombok, szolidabb chipek
CSS alap: typography/surface/spacing tokenek + role primitive-ek aktivak
```

2026-06-02 dontes:

```text
a felso munkafelület-valtot fokozatosan bal oldali oldalsavra csereljuk,
az iratimport/iratmuveletek/iratgyujtemeny/iratreszletek onallo Irat rendezo munkafelületre kerulnek,
a munkafelületek alapertelmezett elrendezese egy fo tartalmi oszlop legyen,
ketpaneles elrendezes csak indokolt, modulon beluli reszletnezeteknel maradjon.
```

A kovetkezo nagyobb termekiranyt az altalanos lokalis RAG kerdezo adja (`Design_documents/20_general_rag_question_answering_plan.md`), de elotte a munkafelületek szetvalasztasa es az `Irat rendezo` felület letisztitasa szukseges, hogy a forraskor-kezelés ne terhelje tovabb az `Ügy munkapad` elemzesi feluletet.

A jelenlegi munkapad ertekes es mukodik, de mar tul sok feladatkort hordoz egyszerre. Nem cel az ujratervezese nullarol. Cel, hogy a mukodo funkciokat szemantikailag tisztabb munkafelületekre rendezzuk:

- irat rendezo munkafelület,
- ugy munkapad / kutatasi munkafelület,
- teljes iratfeldolgozo munkafelület,
- altalanos iratkerdezo / lokalis RAG munkafelület,
- teljes audit naplo munkafelület,
- kesobbi riport / graf / forrasmunka feluletek.

## 1. Problema

A jelenlegi frontend egyetlen nagy munkafeluleten jeleniti meg a legtobb funkciot:

- ugyvalasztas es ugyletrehozas,
- iratlista,
- iratimport,
- iratreszletek,
- modellallapot,
- indexallapot,
- elemzes,
- elemzesi elozmenyek,
- kutatasi talalatok,
- attekintesi jelentes,
- talalat reszletei,
- kezi ellentmondasjelolt,
- levalasztott forrasok,
- export.

Ez a jelenlegi workflow-hoz meg kezelheto, de uj nagyobb munkafolyamatoknal nem tarthato:

- teljes iratfeldolgozas,
- teljes audit naplo,
- kesobbi graf vagy kapcsolati nezet,
- specializalt riport/ellenorzesi feluletek.

Ha mindez ugyanabba az oldalba kerulne, a stabil UI ujra zsufoltta valna, es a panelek kozti logikai hatar elmosodna.

## 2. Cel

Olyan UI-hierarchia kell, amely:

- megtartja a jelenlegi vizualis stilust,
- megtartja a jelenlegi munkapad ergonomiajat,
- tobb nagy munkafelületet tud kezelni,
- nem valasztja szet adat-szigetekre a rendszert,
- kozos ugykontextust ad minden munkafelületnek,
- kesobb is bovitheto marad anelkul, hogy az `App.tsx` ujra egyetlen oriasi munkalappa valna.

Rovid celmondat:

```text
egy kozos alkalmazasvaz, tobb szemantikailag kulon munkafelulettel, kozos adatterrel.
```

## 3. Alapelv

A munkafelület nem onallo mini-alkalmazas.

Minden munkafelület ugyanazon ugyon, ugyanazon dokumentumokon, ugyanazon forras- es audit-adatokon dolgozik. A kulonbseg nem adat-sziget, hanem feladatszervezes.

Pelda:

- a teljes iratfeldolgozo felület kinyerhet szemely/entity/search-focus jellegu munkadarabokat,
- ezek kesobb atadhatok a kutatasi talalat keresesenek,
- vagy strukturalt entitassa / allitassa / esemenye alakithatok,
- es kesobb grafiranyban is hasznalhatok.

Ezert a UI szemantikailag tagolt, de adatfolyam szempontbol osszekotott.

## 4. Javasolt hierarchia

### 4.1 Rendszerszintu AppShell

Mindig latszo, minden munkafelületet korbeolelo vaz.

Feladata:

- alkalmazasidentitas,
- aktiv ugy rovid megjelenitese,
- globalis muveleti allapot,
- globalis hiba / siker uzenetek,
- modellallapot rovid jelzese,
- munkafelület valtas.

Nem feladata:

- minden irat reszleteinek mutatasa,
- minden elemzesi futas listazasa,
- minden review objektum kezelese.

### 4.2 Ugykontextus

Az ugyvalasztas es ugyletrehozas rendszerszintu kepesseg, nem egy adott munkafelület sajatja.

Javasolt kozos elemek:

- aktiv ugy valaszto,
- ugy neve / hivatkozasa,
- ugyadatok frissitese,
- uj ugy letrehozasa,
- rovid statusz.

A jelenlegi `case-strip` jo alap, de kesobb erdemes kompaktabb `CaseContextBar` komponensse alakitani.

### 4.3 Modulrail / munkafelület-valto

A jelenlegi felso munkafelület-valto helyere fokozatosan bal oldali, tartos navigacios sav keruljon.

Indok:

- a munkafelületek szama no,
- az aktiv felület neve ne foglaljon el egy teljes vizszintes sort,
- az egypaneles munkafelületek mellett a bal oldali sav kevesbe zavarja a tartalmi teret,
- a klasszikus oldalsav mentalis modellje jobban illik a tobb munkamodhoz.

Desktopon:

- bal oldali sav,
- ikon + rovid cim,
- aktiv munkafelület egyertelmu jelolese,
- ne vegyen el teljes oszlopnyi helyet,
- maradjon eleg hely az egypaneles fo munkaternek.

Kisebb nezetben:

- ideiglenesen megmaradhat a felso munkafelület-valto,
- vagy kompakt lenyilo / segmented control.

Elsodleges munkafelület-jeloltek:

```text
Irat rendező
Ügy munkapad
Teljes iratfeldolgozás
Általános iratkérdező
Audit napló
```

Az elso implementacios korben eleg lehet:

```text
Irat rendező
Ügy munkapad
Teljes iratfeldolgozás
Audit napló
```

Az `Általános iratkérdező` eleinte lehet terv/placeholder jellegu, de a navigacios modell mar keszuljon ra.

### 4.4 WorkSurface

Az AppShell alatt mindig egy aktiv munkafelület renderelodik.

Javasolt fogalom:

```text
WorkSurface = egy nagy feladatkorhoz tartozo panelrendszer
```

Peldak:

- `DocumentOrganizerSurface`
- `CaseWorkbenchSurface`
- `FullDocumentProcessingSurface`
- `GeneralRagQuestionSurface`
- `AuditLogSurface`

## 5. Elso munkafeluletek

### 5.1 Irat rendező

Ez legyen az elso uj, tenylegesen letisztitott munkafelület.

Celja:

- az iratok feltoltese,
- az iratok attekintese,
- az iratok technikai allapotanak kezelese,
- az iratgyujtemenyek kezelese,
- a forraskorok elokeszitese az elemzesi munkakhoz.

Ide tartozzon:

- iratimport,
- iratlista,
- iratreszletek,
- OCR / OCR-ellenorzes inditasa,
- szovegreteg es szovegresz-letrehozas,
- dokumentum eletciklus muveletek,
- iratgyujtemeny letrehozasa es szerkesztese,
- irat gyujtemenyhez adasa egyenkent vagy csoportosan,
- irat gyujtemenybol kivetele egyenkent vagy csoportosan,
- forraskor elonezet,
- iratgyujtemeny-tagsagbol adodo duplikatumok felhasznaloi szintu jelzese.

Fontos tervezesi elv:

```text
az iratgyujtemeny nem uj dokumentumtipus es nem elemzesi attribútum,
hanem rugalmas rendezesi es forraskor-kijelolesi reteg.
```

Egy irat tobb iratgyujtemenyben is szerepelhet. A gyujtemenyek kijelolese
forraskorkent deduplikalt dokumentumhalmazt adjon az elemzesi/indexelesi
folyamatoknak, ne tobbszorozze meg ugyanazt az iratot.

Az `Irat rendező` ne legyen elemzesi felület. Mutathat technikai
allapotot es indexelhetosegi jelzest, de ne itt fusson a kutatasi talalat
kinyeres, a teljes iratfeldolgozas vagy az ellentmondas-elemzes.

### 5.2 Ügy munkapad

Ez legyen az elemzesi es kutatasi munkafelület.

Tartalma:

- elemzes inditasa,
- elemzesi elozmenyek,
- indexallapot es forraskorhoz kotodo elemzesi keszenlet,
- kutatasi talalatok,
- attekintesi jelentes,
- talalat reszletei,
- kezi ellentmondasjelolt,
- levalasztott forrasok,
- export panelek.

Az `Ügy munkapad` ne legyen az iratok altalanos rendezo felulete. Iratokat
es forraskorokat valaszthat elemzesi bemenetkent, de az iratok napi
rendezese az `Irat rendező` feladata.

Kesobbi finomitas:

- export panelek kulon `Export / riport` surface ala mehetnek,
- levalasztott forrasok kulon forrasmunka felület jelolt lehet,
- az elemzesi panel egypaneles, letisztitott elrendezest kaphat.

### 5.3 Teljes iratfeldolgozás

Kovetkezo nagy munkafelület.

Cel:

- mar feltoltott iratokon dolgozni,
- nem uj import-rendszer,
- nem a jelenlegi chunk alapu kutatasi talalat workflow kivaltasa,
- hanem teljes, osszefuggo irat alapjan eloallitani ujrahasznosithato munkadarabokat.

Elso celterulet:

- szemelyek / entitasok kinyerese teljes iratbol,
- rovid forrashu leiras,
- alternativ nevformak,
- keresesi fokuszjavaslatok,
- kesobbi atadas a kutatasi talalat workflow-nak.

Fontos:

```text
a teljes iratfeldolgozo nem torheti meg a No source -> no claim elvet.
```

Ha teljes iratbol keszul munkadarab, annak is visszakovethetonek kell lennie:

- melyik iratbol,
- melyik feldolgozasi futasbol,
- milyen prompt/profil alapjan,
- milyen forrasreszletek alapjan.

### 5.4 Audit napló

Kulon munkafelület kell, mert nem azonos az `Elemzési előzmények` panellel.

`Elemzési előzmények` jelenleg `analysis_runs` alapu.

Az `Audit napló` celja:

- `audit_events` megjelenitese,
- dokumentum atminosites,
- eletciklus valtozas,
- teljes ugy torlese utan is megmarado torteneti audit esemenyek, peldaul `case_deleted`,
- forrasmozgatasi / torlesi / kezi muveleti esemenyek,
- kesobbi felhasznaloi / idobeli / objektum szerinti szures.

Friss implementacios alap: az `audit_events.case_id` es `audit_events.analysis_run_id`
mar nem kemeny FK, hanem torteneti UUID metadata. Ez lehetove teszi, hogy egy
ugy teljes munkatartalma torolheto legyen, mikozben az audit esemenyek
megmaradnak a kesobbi `Audit napló` felulet szamara.

Ez ne keruljon ra a jelenlegi munkapadra egy ujabb nagy panelkent.

### 5.5 Általános iratkérdező

Kesobbi, onallo munkafelület.

Celja:

- szabadabb, kerdes-valasz jellegu helyi RAG hasznalat,
- kizarolag kijelolt forraskor alapjan,
- forrasokon alapulo osszefoglalo valasz,
- nem talalatjelolt-workflow es nem strukturalt objektumgyartas.

Ez a felület csak akkor induljon, ha az iratgyujtemeny/source-scope reteg
mar stabil, mert a valaszadas minosege es biztonsaga a jol kijelolt
forraskortol fugg.

## 6. Mi legyen globalis?

Minden munkafeluleten latszodjon:

- aktiv ugy,
- ugyvaltas,
- globalis muveleti allapot,
- hiba/siker uzenet,
- munkafelület navigacio,
- rovid modell/index statusz,
- bal oldali munkafelület-navigacio desktopon.

Ne legyen minden munkafeluleten nagyban lathato:

- teljes iratlista,
- iratimport,
- iratgyujtemeny-kezelés,
- irat reszletek,
- teljes elemzesi elozmenylista,
- teljes attekintesi jelentes,
- export elozmenyek,
- kezi ellentmondasjelolt.

Ezek munkafelület-specifikus elemek.

## 7. Allapotkezelesi irany

Az elso implementacioban nem kell teljes state management refaktor.

Elso korben elfogadhato:

- az `App.tsx` megtartja a kozos state nagy reszet,
- bevezetunk egy `activeSurface` state-et,
- a dokumentum/iratgyujtemeny markup bekerul egy `DocumentOrganizerSurface` jellegu blokkba vagy kesobb komponensbe,
- az elemzesi markup bekerul egy `CaseWorkbenchSurface` jellegu blokkba vagy kesobb komponensbe,
- a mar mukodo feluletek eloszor logikailag valjanak szet, komponensbontas csak utana melyuljon.

Kesobbi refaktor:

- `components/AppShell.tsx`,
- `components/CaseContextBar.tsx`,
- `components/ModuleRail.tsx`,
- `surfaces/DocumentOrganizerSurface.tsx`,
- `surfaces/CaseWorkbenchSurface.tsx`,
- `surfaces/FullDocumentProcessingSurface.tsx`,
- `surfaces/GeneralRagQuestionSurface.tsx`,
- `surfaces/AuditLogSurface.tsx`.

Fontos: a komponensbontas ne elozze meg tul agressziven a mukodo UI megerteset. Elobb a vaz, aztan a bontas.

## 8. Responsive elv

Desktop / 1080p:

- keskeny bal modulrail,
- felso topbar,
- ugykontextus kompakt sor,
- aktiv munkafelület a fennmarado terben.

Nagyobb felbontas:

- ugyanaz a vaz,
- nagyobb panelmagassagok,
- kenyelmesebb oszloparanyok.

Kisebb kepernyo:

- modulrail helyett felso munkafelület-valto,
- munkafeluleten belul egyoszlopos panelrendezes,
- a globalis allapot ne tolja le tul melyre a munkafelületet.

## 9. Elso implementacios szelet

Minimalis, alacsony kockazatu sorrend:

1. `document_organizer` munkafelület felvetele a surface definicio listaba.
2. Munkafelület definicio lista:
   - `document_organizer`,
   - `case_workbench`,
   - `full_document_processing`,
   - `audit_log`.
3. A felso munkafelület-valto desktopon bal oldali oldalsavra cserelese.
4. Topbar / CaseContextBar / modellstatusz / muveleti allapot megtartasa a munkafelületek folott.
5. Iratimport, iratlista, iratreszlet, OCR/chunk muveletek es iratgyujtemeny panelek atmozgatasa az `Irat rendező` ala.
6. Az `Ügy munkapad` megtartasa elemzesi, kutatasi talalat, attekintesi, forrasmunka es export feluletkent.
7. `Teljes iratfeldolgozás` es `Audit napló` feluletek mostani mukodesenek megtartasa, csak a navigaciohoz igazitva.

Ebben a szeletben nem kell uj backend endpoint.

## 10. Kesobbi implementacios szeletek

### 10.0 CSS token es role baseline

2026-06-03-ra a frontend vizualis rendszere mar nem csak egyedi
selector-ertekekbol all. A `frontend/src/styles.css` elejen letrejott egy
kozponti tokenretegre epulo baseline.

Token-csaladok:

- `--font-size-*` es `--font-weight-*`: alap meret- es sulyertekek.
- `--text-*`: szemantikus tipografia szerepek, peldaul panelcim, kartyacim,
  label, guide szoveg, meta szoveg es kod/id szoveg.
- `--space-*` es `--layout-*`: oldal, panel, kartya, compact kartya, toolbar,
  form, chip, gomb es input tavolsagok.
- `--color-*`: page/surface/border/text/primary/danger/warning/info/selected/
  success/error/export allapotszinek.
- `--radius-*`, `--shadow-*`, `--control-min-height`, `--button-min-height`,
  `--chip-min-height`: formai es kontrollmeret alapok.

CSS role primitive-ek:

```text
work card:
  .full-document-item, .research-finding-card, .report-item

inner panel:
  .collection-summary, .collection-content-panel, .document-collection-bulk-bar,
  .source-filter-panel, .manual-source-panel, .model-status-panel,
  .model-status-card, .analysis-readable-card, .object-facts div,
  .text-sample, .research-run-summary

compact surface:
  .compact-item, .pair-item, .source-quote-item, .finding-conversion-panel

chip:
  .status-strip span, .metrics span, .tags span, .status-pill, .source-meta span
```

Fontos munkaszabaly:

```text
uj UI finomitasnal eloszor tokent vagy role-valtozot allits,
es csak akkor adj hozza egyedi selector-erteket,
ha a komponens tenyleg egyedi viselkedest igenyel.
```

Ez kulonosen fontos a kovetkezo Full HD / 1080p hangolasnal. A Full HD media
query szandekosan ures, hogy a kovetkezo kor tiszta baseline-rol induljon. Ne
valjon ujra sok komponensspecifikus javitofolt gyujtemenyeve. Elso korben
ezekhez nyuljon:

- `--text-*`
- `--layout-*`
- `--control-min-height`
- `--button-min-height`
- `--chip-min-height`
- role-szintu lokalis valtozok, peldaul `--work-card-*`, `--inner-panel-*`,
  `--compact-surface-*`, `--chip-*`

Live UX ellenorzes:

```text
a felhasznalo vegigkattintotta a feluletet a token/role refaktor utan,
es a jelenlegi latvanyt elfogadta jo baseline-nak.
```

### 10.0.1 Ügy munkapad panelrendezesi baseline

2026-06-05-re az `Ügy munkapad` mar nem csak ket altalanos oszlopbol all,
hanem funkcio szerint rendezett sorokbol.

Felso statuszsor:

- `Szemantikus index állapot`
- `Utolsó kutatási keresés`

Fo elemzesi/kutatasi sor:

- bal oldalon egymas alatt:
  - `Elemzés`
  - `Kézi ellentmondásjelölt`
- jobb oldalon:
  - `Kutatási találatok`

A jobb oldali `Kutatási találatok` panel a bal oldali ket panel egyuttes
magassagahoz igazodik, es belso scrollt hasznal. Nem tolhatja tovabb az egesz
oldal magassagat csak azert, mert sok talalati kartya van benne.

Kozepso/tovabbi teljes szelessegu sorok:

- `Áttekintési jelentés`
- `Találat részletei`
- `Leválasztott forráshivatkozások`
- `Elemzési futás részletei`

Elozmeny/export sor:

- bal oldalon: `Elemzési előzmények`
- jobb oldalon egymas alatt:
  - `Export előzmények`
  - `Export`

Ez a sor 1:1 szelessegben osztozik, es az `Elemzési előzmények` belso scrollt
hasznal, hogy ne fusson tul a jobb oldali export stack magassagan.

Az `Elemzési futás részletei` panel celja nem a nyers technikai payload
megjelenitese, hanem emberileg olvashato folyamatnezete:

- bal oldalon: a feldolgozasba kuldott forras vagy forrasok,
- jobb oldalon: az adott forrasbol letrejott talalat/objektum/forrashivatkozas,
- `manual_entry` futasnal: a kezzel kivalasztott forras es az abbol letrehozott
  vagy ahhoz kapcsolt objektum,
- torolt vagy mar nem elerheto kimenetnel: rovid magyar uzenet arrol, hogy az
  eredmeny mar nem all rendelkezesre.

Backend tamogatas:

- `AnalysisRunRead.display_label` jeleniti meg az elozmenykartyan a kereses
  fokuszat vagy a kezi rogzitessel letrehozott objektum cimet.
- `AnalysisRunOutputSummary` forrashivatkozas mezoi adjak a dokumentum/oldal/
  szovegresz/idezet adatokat, hogy a frontend ne technikai ID-kbol epitkezzen.
- Az analysis input source summary teljes szovegreszt ad vissza a reszletnezeti
  emberi ellenorzeshez; ez itt tudatosan nem rovid preview.

### 10.1 AppShell komponensbontas

Miutan a surface-valtas mukodik:

- `AppShell`,
- `Topbar`,
- `CaseContextBar`,
- `SurfaceSidebar`.

### 10.2 DocumentOrganizerSurface kiemelese

Az elso atmozgatas utan az iratos JSX szakasz sajat komponensbe kerulhet.

Ez tartalmazza:

- import,
- dokumentum lista,
- dokumentum reszletek,
- iratgyujtemenyek,
- csoportos gyujtemenyhez adas/kivetel.

### 10.3 CaseWorkbenchSurface tisztitasa

A jelenlegi nagy JSX szakasz fokozatosan kikerulhet sajat komponensbe.

Ez nagy munka, ezert csak akkor erdemes, ha az AppShell vaz mar stabil.

### 10.4 FullDocumentProcessingSurface

Elso tenyleges uj munkafelület.

Kezdeti UI:

- aktiv irat valaszto,
- teljes iratfeldolgozasi profil valaszto,
- prompt/profil leiras,
- futtatas,
- eredmeny munkalista,
- keresesi fokuszba kuldes / kutatasi talalat workflow-hoz atadas.

### 10.5 GeneralRagQuestionSurface

Az iratgyujtemeny/source-scope reteg stabilizalasa utan induljon.

Kezdeti UI:

- forraskor valaszto,
- szabad kerdes mezo,
- valasz forrasalapu osszefoglaloval,
- felhasznalt forrasok listaja,
- audit-tracked futasi elozmeny.

### 10.6 AuditLogSurface

Backend/API es UI egyutt:

- `audit_events` lista,
- szures ugy, objektum, esemenytipus, idoszak szerint,
- reszletezo panel,
- kapcsolodas dokumentumhoz / objektumhoz / futashoz.

## 11. Nem cel most

Nem cel az elso UI-vaz szeletben:

- teljes `App.tsx` szetbontasa,
- uj audit backend,
- uj iratgyujtemeny backend,
- altalanos RAG backend,
- graf UI,
- uj design system bevezetese,
- minden munkafelület vegleges vizualis ujratervezese,
- minden ketpaneles belso nezet azonnali megszuntetese.

## 12. Dontesi osszegzes

Elfogadott irany:

```text
AppShell + CaseContext + LeftSidebar + WorkSurface
```

Elso ujrarendezendo felület:

```text
Irat rendező = iratimport, iratlista, iratreszletek, iratgyujtemenyek, forraskor elokeszites
```

Elemzesi felület:

```text
Ügy munkapad = kutatasi talalatok, attekintesi jelentes, elemzes, forrasmunka
```

Mar letezo / kovetkezo feluletek:

```text
Teljes iratfeldolgozás
Audit napló
Általános iratkérdező
```

A cel nem az, hogy a rendszer tobb kulonallo modulra essen szet, hanem hogy a felhasznalo kulon munkafolyamatokat kapjon ugyanazon kozos ugy- es forrasadatok folott.
