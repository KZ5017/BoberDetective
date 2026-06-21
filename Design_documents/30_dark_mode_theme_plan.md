# 30. Sotet mod es tematizalasi terv

## 0. Cel

Ez a dokumentum a jelenlegi, vilagos UI melle bevezetheto sotet mod tervezett megvalositasat rogziti.

A cel nem egy masodik, panelenkent kulon megfestett felulet, hanem egy professzionalis, CSS-token alapu tematizalasi retegre epulo megoldas.

Rovid cel:

```text
egy kapcsoloval valthato vilagos / sotet tema,
a jelenlegi vilagos UI megorzesevel,
a komponensek atirasa nelkul,
a meglevo CSS token rendszerre epitve.
```

## 1. Kiindulo allapot

A frontend jelenleg mar eros CSS token alapokon all.

Fo token csoportok:

- tipografia: `--font-size-*`, `--text-*`, `--font-weight-*`;
- spacing/layout: `--space-*`, `--layout-*`;
- feluletek es szinek: `--color-page`, `--color-surface`, `--color-border-*`, `--color-text-*`, `--color-primary-*`, `--color-warning-*`, `--color-error-*`, `--color-success-*`;
- gomb/valaszto stilus: `--choice-button-*`;
- grafikus kapcsolati terkep: `--graph-*`;
- arnyekok: `--shadow-*`;
- kontrolmeretek: `--control-min-height`, `--button-min-height`, `--chip-min-height`.

Ez kedvezo kiindulas, mert a sotet mod nagy resze tematokenek felulirasaval megoldhato.

## 2. Alapelv

Ne panelenkenti dark override-okkal epitsuk, hanem temavaltozokkal.

```css
:root {
  --color-page: ...;
  --color-surface: ...;
  --color-text: ...;
}

:root[data-theme="dark"] {
  --color-page: ...;
  --color-surface: ...;
  --color-text: ...;
}
```

A komponensek tovabbra is csak szerep-tokeneket hasznaljanak.

```css
.panel {
  background: var(--color-surface);
  color: var(--color-text);
}
```

Igy a vilagos tema marad az alap, a sotet tema egy masodik tokenkeszlet, es a komponens-CSS nem valik ket kulon vilagga.

## 3. Nem cel

Ebben a fejlesztesben nem cel:

- komponensek ujrarajzolasa,
- uj layout,
- panelenkenti egyedi sotet override,
- userenkenti backendben tarolt tema-preferencia,
- tobb paletta vagy teljes theme editor,
- sotet modhoz kulon mobil/1080p layout.

A tema tisztan frontend-preferencia legyen.

## 4. Megvalositasi fazisok

### 4.1 Token audit

Elso lepesben at kell nezni a `frontend/src/styles.css` fajlt es szet kell valasztani:

1. Valodi token definiciok.
2. Jogos, egyszeri specialis szinek.
3. Olyan direkt szinek, amelyeket token ala kell huzni.

Kiemelt teruletek:

- topbar,
- sidebar / surface navigation,
- panelek es belso panelek,
- ures allapot blokkok,
- searchable select,
- Markdown renderelt valaszok,
- code block / inline code,
- status/chip/badge elemek,
- danger/warning/success/info allapotok,
- `Kapcsolati térkép` node/edge/canvas elemei.

Elfogadasi feltetel:

```text
Az altalanos UI-szerepet betolto szinek tokenbol jojjenek.
Direkt szin csak indokolt, nagyon helyi specialis esetben maradjon.
```

### 4.2 Dark token layer

A kovetkezo lepes egy sotet tokenkeszlet letrehozasa.

```css
:root[data-theme="dark"] {
  --color-page: ...;
  --color-surface: ...;
  --color-surface-soft: ...;
  --color-surface-muted: ...;
  --color-border: ...;
  --color-text: ...;
  --color-text-muted: ...;
}
```

Javasolt palettaelv:

- ne legyen teljesen fekete hatter,
- inkabb hideg, szurkes-kekes munkafelület,
- oldalhatter legyen nagyon sotet, de nem fekete,
- panelek es belso panelek adjanak finom melysegi lepcsot,
- borderok legyenek lathatoak, de ne vilagitsanak,
- szoveg legyen kontrasztos, de ne tiszta feher mindenhol.

Pelda irany, nem vegleges szinpaletta:

```css
:root[data-theme="dark"] {
  --color-page: #101418;
  --color-surface: #171d22;
  --color-surface-soft: #1d252b;
  --color-surface-muted: #222b32;
  --color-border: #33404a;
  --color-border-soft: #2a353d;
  --color-text: #e6edf2;
  --color-text-soft: #c2ccd4;
  --color-text-muted: #9eacb6;
}
```

### 4.3 Allapotszinek sotet modban

Kulon figyelmet igenyelnek: primary/secondary/danger gombok, warning/success/error/info blokkok, selected/marked/delete allapotok.

Sotet modban az allapotszinek ne egyszeruen a vilagos tema inverzei legyenek. A danger legyen egyertelmu, de ne tul agressziv; a warning ne legyen vilagito sarga; a success ne legyen harsany zold.

### 4.4 Arnyekok es melyseg

Vilagos modban az arnyekok termeszetesek. Sotet modban az eros fekete arnyek sokszor nem latszik vagy koszos hatast ad, ezert a `--shadow-*` tokenek kulon felulirast kapjanak.

### 4.5 Markdown es code megjelenites

Kiemelt tesztterulet: `Általános iratkérdező`, `Tudásbázis`, `Teljes iratfeldolgozás / Iratválasz`, `Felhasznált Markdown források`.

Sotet modban ellenorizni kell a paragrafusokat, linkeket, inline code-ot, fenced code blockot, listakat, idezeteket, tablazatokat, hosszu parancsokat, pathokat es forrasidezeteket.

A code block kapjon sajat tokeneket, ha meg nincs eleg pontos szerep-token: `--color-code-bg`, `--color-code-border`, `--color-code-text`.

### 4.6 Kapcsolati terkep

A `Kapcsolati térkép` kulon validacios pont: canvas hatter, node hatter, object-type node szinezes, edge szinek, visual bridge edge, edge label hatter/szoveg, React Flow attribution, MiniMap, inspector panelek es inspector chip tokenek.

Elso sotet-mod korrekcio: a kijelolt graph node ne kapjon uj hatterszint, csak tokenizalt, erosebb bordert; az edge label es a MiniMap sajat `--graph-*` tokeneken keresztul kapjon vilagos/sotet temaerteket.

## 5. React oldali temaallapot

Javasolt mukodes:

- temaallapot: `light` / `dark`,
- tarolas: `localStorage`,
- alkalmazas: `document.documentElement.dataset.theme = "dark"`,
- alapertelmezett: ha van mentett user-preferencia, azt hasznaljuk; ha nincs, kezdetben maradhat `light`.

Elso implementacios dontes:

```text
Vilagos tema legyen az alapertelmezett.
A sotet mod csak explicit user kapcsolasra aktivalodjon.
```

## 6. Kapcsolo helye

A kapcsolo a topbar jobb oldali status-strip reszebe keruljon, ahol jelenleg ezek lathatok: `helyi`, `forrashivatkozott`, `emberi ellenorzes`.

Javasolt forma: kompakt, ikon alapu billenokapcsolo nap/hold ikonokkal, magyar `aria-label` szoveggel. Ne legyen hosszu szoveges gomb.

## 7. Implementacios sorrend

1. CSS szin-audit: direkt szinek listazasa, tokenizalando elemek azonositasa.
2. Hianyzo tokenek bevezetese: code/markdown, specialis sidebar/status, graph finomsagok.
3. Dark token blokk: `:root[data-theme="dark"]` es elsodleges surface/text/border/action tokenek.
4. React theme state: `light/dark` allapot, `localStorage`, `data-theme` beallitasa.
5. Topbar kapcsolo: ikon/billeno UI, magyar `aria-label`, mobilon is stabil tordeles.
6. Celzott vizualis korrekcio: Markdown/code, Kapcsolati terkep, dropdown/searchable-select, status/chip/warning/error, empty-state blokkok.
7. Live ellenorzes: desktop alap, 1080p, mobil media query.

## 8. Tesztelesi matrix

Minimum manualis vizualis ellenorzes:

- topbar es tema kapcsolo,
- oldalsav / munkafelület valaszto,
- `Irat rendező`, `Ügy munkapad`, `Áttekintési jelentés`, `Kutatási találatok`,
- `Találat részletei`, `Leválasztott forráshivatkozások`, `Elemzési előzmények`, `Elemzési futás részletei`,
- `Általános iratkérdező`, `Tudásbázis`, `Teljes iratfeldolgozás`, `Kapcsolati térkép`,
- ures allapot panelek, hiba/siker/figyelmeztetes allapotok, markdown valasz code blockkal, hosszu path/fajlnev, mobil nezet.

Automatikus minimum:

```bash
npm --prefix frontend run build
git diff --check
```

Ha csak CSS/React UI valtozik, backend teszt nem kotelezo.

## 9. Elfogadasi kriteriumok

Az elso sotet mod akkor tekintheto kesz baseline-nak, ha a vilagos tema nem romlik, a sotet mod kapcsoloval valthato, a valasztas frissites utan megmarad, nincs panelenkenti ad hoc sotet override-halmozas, a fo munkafeluletek es Markdown/code tartalmak olvashatoak, a kapcsolati terkep ertelmezheto, es mobilon nem esik szet a topbar/kapcsolo.

## 10. Kockazatok

### 10.1 Direkt szinek szivargasa

Ha sok direkt szin marad, sotet modban egyes elemek vilagos foltokkent megjelenhetnek. Kezeles: token audit, csak indokolt specialis szin maradjon direkt.

### 10.2 Markdown/code tul eros kontraszt

Security/technical jegyzeteknel a code block gyakori. Kezeles: kulon code tokenek es hosszu sorokra mobil overflow guard.

### 10.3 Graph olvashatosag

A kapcsolati terkep vonalai es node-jai sotet hatteren maskepp viselkednek. Kezeles: graph tokenek kulon dark override-ja, canvas es edge teszt valos adatokkal.

### 10.4 Allapotszinek tul harsany vagy tul halvany hatasa

Kezeles: dark warning/danger/success/info paletta kulon, ne automatikus invertalas legyen.

## 11. Dokumentacios kovetes

Megvalositas kozben frissitendo: `AI_NOTES.md`, `CURRENT_STATE.md`, `CHANGELOG.md`, valamint ez a dokumentum.

Javasolt allapotjeloles: `Tervezve`, `Folyamatban`, `Kesz`, `Elhalasztva`.

## 11.1 Implementacios allapot

Allapot: Kesz baseline.

Elkeszult:

- az elso token-audit / szinfegyelmezesi szelet,
- a komponens-szintu direkt hex/rgba szinek nagy resze vissza lett kotve letezo vagy uj CSS szerep-tokenekre,
- uj vilagos tema role tokenek kerultek be a shell/status, source/accent, highlight es link szerepekre,
- a frontend styles tokenretege megkapta az elso sotet tema palettat,
- a React frontend temaallapotot tart fenn light / dark ertekekkel,
- a valasztas localStorage-ba kerul,
- a topbar status-strip reszeben megjelent a sotet/vilagos mod kapcsolo,
- a live felhasznaloi atnezes utan feltart Kapcsolati terkep finomitasok bekerultek: kijelolt node border, edge label tokenek, MiniMap tokenek, felso objektumvalaszto sor maximalis magassaga, valamint a graf canvas/preview nagyobb munkaterulete.

A jelenlegi sotet mod elso elfogadott baseline-nak tekintheto. Nincs ismert, konkret elvarratlan szal ehhez a fejlesztesi szelethez.

## 12. Javasolt kovetkezo konkret lepes

Nincs kulon sotet-mod implementacios kovetkezo lepes. A tovabbi sotet tema munka live hasznalat soran felmerulo, konkret vizualis hibak vagy uj komponensek tokenizalasa alapjan tortenjen.

Figyelendo, de nem blokkoló teruletek kesobbi boviteseknel:

- uj Markdown/code megjelenitesi variansok,
- uj Kapcsolati terkep canvas/node/edge elemek,
- uj searchable-select/dropdown helyzetek,
- uj status/chip/warning/error allapotok,
- uj ures allapot blokkok,
- mobil topbar es tema kapcsolo, ha a topbar szerkezete kesobb valtozik.
