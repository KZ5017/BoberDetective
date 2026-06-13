# 26. Attekintesi jelentes statusztisztitas terv

## Cel

Az `Attekintesi jelentes` szuroi es kartyacimkei ne mutassanak egymasnak
ellentmondo allapotokat.

Allapot:

```text
Megvalositva.
```

Implementacios baseline:

- `0048_review_status_cleanup` migracio,
- aktiv backend/frontend `new` statusz kivezetes,
- `corrected` magyar UI cimke: `Korrekcióval kizárt`,
- merge / vegso forraslevalasztas / vegso forrasathelyezes utan arva
  objektumok korrekcioval kizart + forrasinvalid szemantikaja,
- torlesi/destruktiv UI gombok egységes danger + kukaikon megjelenitese.

Kulonosen ezt a helyzetet kell megszuntetni:

```text
Ellenorzesi allapot: Javítva
Forrashivatkozas allapota: Forrashivatkozas ervenyes
Valojaban: nincs sajat ervenyes forrashivatkozas a kartyahoz
```

## Donto gondolat

Ket kulon allapottengely van:

```text
review_status
source_validation_status
```

Ezek kulon dolgot mondanak:

- `review_status`: mi tortent az objektummal workflow/emberi dontes szinten,
- `source_validation_status`: van-e ervenyes forrashivatkozasa.

Ha egy objektum osszevonas vagy forraslevalasztas utan forras nelkul marad,
akkor mindket allitas igaz ra:

```text
review_status = corrected
source_validation_status = source_invalid
```

Frontend magyar cimke:

```text
corrected -> Korrekcióval kizárt
source_invalid -> Nincs érvényes forráshivatkozás
```

## `new` statusz kivezetese

A `new` review statusz jelenleg nem latszik aktiv letrehozasi workflow-ban
hasznalt allapotnak. A rendszer jellemzoen `needs_review` allapotban hozza
letre a strukturalt objektumokat.

Dontes:

- `new` ne maradjon csak felig eltuntetve.
- Ki kell vezetni backend es frontend szinten is.
- Meglevo `new` rekordokat migracioval `needs_review` allapotra kell hozni.

Erintett helyek:

- adatbazis constraint-ek,
- SQLAlchemy model constraint-ek,
- review report allowed filter statuszok,
- review report counts,
- frontend szuro lista es label,
- tesztek.

## `corrected` uj user-facing jelentese

A `corrected` eddigi magyar cimkeje:

```text
Javítva
```

Felrevezeto, mert azt sugallja, hogy az objektum tartalma lett kijavitva.
A valos workflow jelentese inkabb:

```text
Korrekcióval kizárt
```

Ez azt jelenti, hogy az objektum mar nem aktiv szakmai talalat, mert egy
korrekcios muvelet - peldaul osszevonas vagy forrasalap megszunese - kivette
az aktiv ervenyes halmazbol.

## Osszevonas szabaly

Ha egy objektumot egy masikba osszevonunk:

```text
source object review_status = corrected
source object source_validation_status = source_invalid
```

A celobjektum nem valtozik `corrected` allapotra.

Ez alkalmazando:

- claim,
- event,
- missing_item_candidate,
- ahol relevans, entity merge source oldali allapotara is.

## Forraslevalasztas szabaly

Ha egy objektumrol forrashivatkozast valasztunk le:

1. Ha marad legalabb egy ervenyes forrashivatkozasa:
   - `review_status` marad,
   - `source_validation_status = source_valid`.

2. Ha nem marad ervenyes forrashivatkozasa:
   - `review_status = corrected`,
   - `source_validation_status = source_invalid`.

Entity esetben a review report forrasallapot jelenleg mention/source linkekbol
szamolodik. Ha az entitynek nincs valid mention/source linkje, akkor a report
`source_invalid`-kent jelenitse meg; a review statusz forrasvesztes eseten
ugyanugy `corrected` iranyba viheto.

## `pending_source_validation`

A `pending_source_validation` marad backendben es frontendben is.

Indok:

- jelenleg ritkan vagy egyaltalan nem aktiv,
- de ertelmes atmeneti statusz lehet kesobbi aszinkron vagy emberi
  forrasvalidacios workflow-hoz,
- ha backendben tamogatott, akkor UI-ban is latszodhat.

## Elvart UI eredmeny

Az `Attekintesi jelentes` szurok:

Ellenorzesi allapot:

- Osszes
- Ellenorzesre var
- Ellenorizve
- Elutasitva
- Korrekcioval kizart

Forrashivatkozas allapota:

- Osszes
- Forrashivatkozas ervenyes
- Nincs ervenyes forrashivatkozas
- Forrashivatkozas ellenorzesre var

Tilos allapotkombinacio normal mukodesben:

```text
Korrekcioval kizart + Forrashivatkozas ervenyes + nincs forras
```

## Implementacios lepesek

1. Migracio: **kesz**
   - `new` -> `needs_review`,
   - review status check constraint-ek frissitese.
2. Model/schema/report frissites: **kesz**
   - `new` allowed status eltavolitasa,
   - count mezokbol `new` eltavolitasa.
3. Merge workflow-k: **kesz**
   - source oldal `corrected` + `source_invalid`.
4. Forraslevalasztas workflow-k: **kesz**
   - ha nem marad valid source, `corrected` + `source_invalid`.
5. Frontend: **kesz**
   - `new` eltavolitasa,
   - `corrected` cimke atnevezese `Korrekcióval kizárt`-ra.
6. Tesztek: **kesz**
   - review report counts/filter,
   - merge source-invalid allapot,
   - detach utani arva objektum allapot.
