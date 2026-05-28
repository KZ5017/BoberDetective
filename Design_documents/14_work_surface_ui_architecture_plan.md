# 14. Work Surface UI Architecture Plan

## 0. Aktualisitas

Frissitve: 2026-05-28.

Ez a dokumentum a kovetkezo frontend iranyt rogziti: a jelenlegi, vizualisan stabil ketoszlopos munkapad ne tovabb zsufolodjon, hanem keruljon egy tobb munkafeluletet kezelo alkalmazasvaz ala.

Aktualis dontes:

```text
nem ujabb panelek a jelenlegi oldalra,
hanem kozos AppShell + kulon munkafeluletek.
```

Aktualis implementacios allapot:

```text
elso shell/surface-navigation szelet: kesz
Ügy munkapad: a korabbi munkapad rendezett tovabbvitele
Teljes iratfeldolgozás: elso frontend-only irat/profil/kimenet vaz kesz
Audit napló: placeholder
```

A kovetkezo implementacios iranyt a `Design_documents/15_full_document_processing_plan.md` tartalmazza.

A jelenlegi munkapad ertekes es mukodik. Nem cel az ujratervezese nullarol. Cel, hogy ez legyen az elso munkafelulet, es kesobb melle epulhessen:

- teljes iratfeldolgozo munkafelület,
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

A jelenlegi oldal melle egy keskeny, tartos navigacios sav kerulhet.

Desktopon:

- bal oldali keskeny sav,
- ikon + rovid cim vagy tooltip,
- aktiv munkafelület egyertelmu jelolese,
- 56-72 px koruli szelesseg,
- ne vegyen el teljes oszlopnyi helyet.

Kisebb nezetben:

- felso munkafelület-valto,
- vagy kompakt lenyilo / segmented control.

Elsodleges munkafelület-jeloltek:

```text
Ügy munkapad
Teljes iratfeldolgozás
Audit napló
Export / riport
```

Az elso implementacios korben eleg lehet:

```text
Ügy munkapad
Teljes iratfeldolgozás
Audit napló
```

Az utobbi ketto eleinte lehet placeholder jellegu, de a navigacios modell mar letisztul.

### 4.4 WorkSurface

Az AppShell alatt mindig egy aktiv munkafelület renderelodik.

Javasolt fogalom:

```text
WorkSurface = egy nagy feladatkorhoz tartozo panelrendszer
```

Peldak:

- `CaseWorkbenchSurface`
- `FullDocumentProcessingSurface`
- `AuditLogSurface`
- `ExportSurface`

## 5. Elso munkafeluletek

### 5.1 Ügy munkapad

Ez a mostani felület tovabborokitese.

Tartalma:

- iratok,
- iratreszletek,
- iratimport,
- modell/index statusz,
- elemzes,
- elemzesi elozmenyek,
- kutatasi talalatok,
- attekintesi jelentes,
- talalat reszletei,
- kezi ellentmondasjelolt,
- levalasztott forrasok,
- export panelek.

Elso korben nem kell belole minden panelt kivagni. A cel csak az, hogy a jelenlegi tartalom bekeruljon egy nevesitett munkafelület ala.

Kesobbi finomitas:

- export panelek kulon `Export / riport` surface ala mehetnek,
- modellallapot egy resze globalis AppShell statuszba mehet,
- levalasztott forrasok kulon forrasmunka felület jelolt lehet.

### 5.2 Teljes iratfeldolgozás

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

### 5.3 Audit napló

Kulon munkafelület kell, mert nem azonos az `Elemzési előzmények` panellel.

`Elemzési előzmények` jelenleg `analysis_runs` alapu.

Az `Audit napló` celja:

- `audit_events` megjelenitese,
- dokumentum atminosites,
- eletciklus valtozas,
- forrasmozgatasi / torlesi / kezi muveleti esemenyek,
- kesobbi felhasznaloi / idobeli / objektum szerinti szures.

Ez ne keruljon ra a jelenlegi munkapadra egy ujabb nagy panelkent.

## 6. Mi legyen globalis?

Minden munkafeluleten latszodjon:

- aktiv ugy,
- ugyvaltas,
- globalis muveleti allapot,
- hiba/siker uzenet,
- munkafelület navigacio,
- rovid modell/index statusz.

Ne legyen minden munkafeluleten nagyban lathato:

- teljes iratlista,
- teljes elemzesi elozmenylista,
- teljes attekintesi jelentes,
- export elozmenyek,
- kezi ellentmondasjelolt,
- irat reszletek.

Ezek munkafelület-specifikus elemek.

## 7. Allapotkezelesi irany

Az elso implementacioban nem kell teljes state management refaktor.

Elso korben elfogadhato:

- az `App.tsx` megtartja a kozos state nagy reszet,
- bevezetunk egy `activeSurface` state-et,
- a jelenlegi markup bekerul egy `renderCaseWorkbenchSurface()` jellegu blokkba vagy kesobb komponensbe,
- uj placeholder surface-ek keszulnek.

Kesobbi refaktor:

- `components/AppShell.tsx`,
- `components/CaseContextBar.tsx`,
- `components/ModuleRail.tsx`,
- `surfaces/CaseWorkbenchSurface.tsx`,
- `surfaces/FullDocumentProcessingSurface.tsx`,
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

1. `activeSurface` state bevezetese.
2. Munkafelület definicio lista:
   - `case_workbench`,
   - `full_document_processing`,
   - `audit_log`.
3. Topbar / CaseContextBar megtartasa.
4. Modulrail vagy kompakt surface-nav letrehozasa.
5. A jelenlegi teljes munkapad bekerul az `Ügy munkapad` surface ala.
6. `Teljes iratfeldolgozás` placeholder:
   - cel rovid megnevezese,
   - aktiv ugy es iratok elerhetosegenek jelzese,
   - kesobbi megvalositando funkciok rovid, nem marketing jellegu listaja.
7. `Audit napló` placeholder:
   - kulonbozzon az elemzesi elozmenyektol,
   - jelezze, hogy `audit_events` alapu munkafelület lesz.

Ebben a szeletben nem kell uj backend endpoint.

## 10. Kesobbi implementacios szeletek

### 10.1 AppShell komponensbontas

Miutan a surface-valtas mukodik:

- `AppShell`,
- `Topbar`,
- `CaseContextBar`,
- `SurfaceNav`.

### 10.2 CaseWorkbenchSurface kiemelese

A jelenlegi nagy JSX szakasz fokozatosan kikerulhet sajat komponensbe.

Ez nagy munka, ezert csak akkor erdemes, ha az AppShell vaz mar stabil.

### 10.3 FullDocumentProcessingSurface

Elso tenyleges uj munkafelület.

Kezdeti UI:

- aktiv irat valaszto,
- teljes iratfeldolgozasi profil valaszto,
- prompt/profil leiras,
- futtatas,
- eredmeny munkalista,
- keresesi fokuszba kuldes / kutatasi talalat workflow-hoz atadas.

### 10.4 AuditLogSurface

Backend/API es UI egyutt:

- `audit_events` lista,
- szures ugy, objektum, esemenytipus, idoszak szerint,
- reszletezo panel,
- kapcsolodas dokumentumhoz / objektumhoz / futashoz.

## 11. Nem cel most

Nem cel az elso UI-vaz szeletben:

- teljes `App.tsx` szetbontasa,
- uj audit backend,
- teljes iratfeldolgozo backend,
- graf UI,
- uj design system bevezetese,
- a jelenlegi munkapad vizualis ujratervezese.

## 12. Dontesi osszegzes

Elfogadott irany:

```text
AppShell + CaseContext + SurfaceNav + WorkSurface
```

Elso felület:

```text
Ügy munkapad = jelenlegi munkapad rendezett tovabbvitele
```

Kovetkezo felület:

```text
Teljes iratfeldolgozás
```

Utana:

```text
Audit napló
```

A cel nem az, hogy a rendszer tobb kulonallo modulra essen szet, hanem hogy a felhasznalo kulon munkafolyamatokat kapjon ugyanazon kozos ugy- es forrasadatok folott.
