# AI-asszisztens Chat Modul Terv

## 1. Cel

Az AI-asszisztens egy uj, kulonallo munkafelület legyen a rendszerben.

Feladata nem iratfeldolgozas, nem RAG, nem talalatkeszites es nem nyomozati objektumkezeles, hanem egy altalanos, lokalis LLM chatfelulet biztositasa a mar hasznalt LM Studio hattermodellhez.

Gyakorlati cel:

- klasszikus webes chat interface,
- uj beszelgetes inditasa,
- korabbi beszelgetesek mentese es visszanyitasa,
- altalanos kerdes-valasz hasznalat,
- kenyelmes, stilusos frontend megjelenites,
- teljesen lokalis mukodes.

Fontos tervezesi alapelv:

Az AI-asszisztens nem tudja es nem hasznalja automatikusan, hogy a BoberDetective rendszer resze. A modellnek nem kell rendszerkontextust, ugyirat-kontextust vagy forrashivatkozasi szabalyokat kapnia.

## 2. Tudatos nem-celok

Az elso verzio szandekosan nem tartalmazza az alabbiakat:

- automatikus hozzaferes ugyiratokhoz,
- automatikus RAG,
- dokumentum- vagy tudasbazis-retrieval,
- claim/event/entity/missing item/contradiction objektum letrehozasa,
- chatbol kozvetlen munkalista-elem gyartas,
- forrashivatkozas-kotelezettseg,
- source-bound prompt beagyazasa ebbe a modulba,
- ugyek kozotti memoria,
- rendszerwide szemelyes profilozas,
- audit/provenance graf bovites,
- chatvalaszok automatikus atemelese mas modulokba.

Ha a felhasznalo kezzel bemasol egy iratreszletet a chatbe, akkor az egyszeru chat inputkent kezelendo. A modell nem kap plusz tudast arrol, hogy az szoveg milyen dokumentumbol vagy ugybol szarmazik.

## 3. Viszony a rendszer tobbi reszehez

Az AI-asszisztens a tobbi munkafelület mellett jelenjen meg, de ne valtsa ki oket.

Javasolt modulnev a navigacioban:

- AI-asszisztens

A modul fuggetlen legyen az alabbiaktol:

- Ügy munkapad,
- Általános iratkérdező,
- Tudásbázis,
- Teljes iratfeldolgozás,
- Kapcsolati térkép,
- Audit napló.

Ez azt jelenti, hogy a chat modul:

- nem igenyel aktiv ugyet,
- nem szur ugyre,
- nem olvas dokumentumot,
- nem hasznal source reference adatot,
- nem hoz letre analysis_run objektumot,
- nem szennyezi az investigative audit/provenance modellt.

Kesobb, ha szukseg lesz ra, lehet kulon donteni arrol, hogy a chat muveletei kapjanak-e technikai audit bejegyzest. Az elso verzio celja inkabb a chat history es nem a nyomozati audit.

## 4. Reasoning es LM Studio hivas

A jelenlegi kod szerint a chat modell betoltese es a reasoning kapcsolo ket kulon szint.

A modell betoltese LM Studio native model-load endpointon tortenik. A konkret chat hivas LM Studio native chat endpointon tortenik.

A jelenlegi LMStudioNativeProvider.chat_completion a chat hivas payloadjaban kuldi a reasoning mezot, nem a modellbetoltesnel.

Aktualis mukodes:

- a backend auto-ensure logikaval betolti vagy ujrahasznalja a konfiguralt chat modellt,
- a chat keres a betoltott instance id-ra megy,
- Qwen-szeru modelleknel jelenleg reasoning: off kerul a request payloadba,
- nem Qwen-szeru modelleknel a reasoning mezot nem kuldjuk, mert peldaul Llama hibazhat tole.

Kovetkeztetes:

A reasoning a jelenlegi integracio alapjan request-szintu dontes. Emiatt az AI-asszisztensben kesobb akar beszelgetesenkent vagy uzenetenkent is allithato lehet.

Elso implementacios javaslat:

1. A backend LLM adapter maradjon kompatibilis a jelenlegi stabil mukodessel.
2. Az AI-asszisztens API keruljon ugy megtervezesre, hogy opcionlisan at tudjon adni reasoning modot.
3. A reasoning beallitas elso lepesben lehet normal vagy model default.
4. Normal modban marad a jelenlegi stabil mukodes, vagyis Qwen eseten reasoning off.
5. Model default modban Qwen eseten sem kuldunk reasoning off mezot, vagyis az LM Studio/model alapertelmezett viselkedese ervenyesul.
6. A model default opciot csak live teszt utan erdemes UI-ban kitenni, mert a pontos LM Studio elfogadott ertekek modell- es verziokent elterhetnek.

Fontos: az AI-asszisztens nem hasznaljon forrashu, JSON schema-s vagy objektumgyarto promptot. Ez sima chat completion hasznalat legyen.

## 5. Backend adatmodell

Javasolt tablak:

### assistant_chats

Cel: egy beszelgetes metaadatai.

Javasolt mezok:

- id,
- title,
- created_at,
- updated_at,
- archived_at vagy deleted_at,
- model_name,
- reasoning_mode,
- temperature,
- system_prompt_mode,
- metadata_json.

Megjegyzes:

system_prompt_mode elso korben lehet null vagy generic_empty. A lenyeg, hogy ne keruljon bele nyomozati kontextus vagy forrashivatkozott viselkedes.

### assistant_messages

Cel: a beszelgetes uzenetei sorrendben.

Javasolt mezok:

- id,
- chat_id,
- role,
- content,
- created_at,
- sequence_index,
- model_name,
- reasoning_mode,
- token_or_runtime_metadata_json,
- error_message.

Role ertekek:

- user,
- assistant,
- system csak akkor, ha kesobb technikailag szukseg lesz ra; elso korben kerulendo.

Az assistant uzenet csak sikeres LLM valasz utan jojjon letre. Ha a hivas hibazik, a user uzenet megmaradhat, es a hiba kulon error allapotkent jelenhet meg.

## 6. Backend API terv

Javasolt endpointok:

### Chat lista

GET /api/v1/assistant/chats

Visszaadja a nem archivalt/nem torolt beszelgetesek rovid listajat.

### Uj chat

POST /api/v1/assistant/chats

Letrehoz egy ures beszelgetest.

Aktualis dontes:

- a letrehozas nem fogad explicit cimet,
- a kezdeti cim `Uj beszelgetes`,
- az elso user uzenetbol a backend automatikusan rovid cimet kepez,
- kesobbi kezi atnevezes csak a PATCH endpointon tortenik.

### Chat reszletek

GET /api/v1/assistant/chats/{chat_id}

Visszaadja a chat metaadatokat es az uzeneteket idorendben.

### Uzenet kuldese

POST /api/v1/assistant/chats/{chat_id}/messages

Bemenet:

- user_message,
- optional temperature,
- optional reasoning_mode.

Folyamat:

1. user uzenet mentese,
2. elkuldendo kontextus osszeallitasa a chat elozo uzeneteibol,
3. LM Studio native chat hivas,
4. assistant uzenet mentese,
5. chat updated_at frissitese,
6. valasz visszaadasa.

### Chat atnevezes

PATCH /api/v1/assistant/chats/{chat_id}

Elso korben eleg a title modositasa.

### Chat torles

DELETE /api/v1/assistant/chats/{chat_id}

Aktualis dontes:

- elso korben soft delete,
- a beszelgetes nem jelenik meg az aktiv listaban,
- vegleges torles csak kesobbi, kulon UI/UX dontes utan kerulhet be.

## 7. Kontextuskezeles

A chat history mentesre kerul, de nem minden esetben kuldheto vissza teljes egeszeben a modellnek.

Elso verzios egyszeru strategia:

- minden uzenet tarolva marad,
- LLM hivasnal a legutobbi N uzenet kerul be,
- N vagy karakter/token kozelito budget konfigurálhato,
- ha tul hosszu a history, a regi uzenetek kimaradnak a requestbol, de a frontend historyban megmaradnak.

Kezdeti javasolt beallitas:

- karakteralapu konzervativ limit,
- vagy max 20-30 utolso uzenet,
- kesobb tokenbecsles vagy osszefoglalas, ha valoban kell.

Nem javasolt elso korben:

- automatikus memoria-osszefoglalo,
- tartos szemelyes profil,
- cross-chat memoria.

## 8. Frontend UX terv

Elfogadott elso baseline desktopon:

Ketsavos, de nem hagyomanyos panel-a-panelben elrendezes:

1. Bal oldali beszelgetes rail
   - Uj chat gomb,
   - frissites gomb,
   - mentett beszelgetesek kompakt listaja,
   - aktiv beszelgetes choice-button szeru kijelolese,
   - harompontos context menu atnevezes / torles muveletekkel.

2. Jobb oldali chat canvas
   - ures allapotban a composer es a Miben segithetek? inditas kozeprol indul,
   - aktiv beszelgetesnel az uzenetfolyam belso scrollteruletet kap,
   - a composer stabil also sorban marad, nem sticky/viewport-trukk,
   - a chat buborekok nem mozgatjak a teljes oldalt, csak a thread sajat scrollpoziciojat,
   - user uzenetek es assistant valaszok buborekformaban jelennek meg,
   - assistant valaszok biztonsagos Markdown rendererrel jelennek meg,
   - valaszgeneralas kozben typing indicator jelenik meg,
   - ujrageneralas kozben a regi utolso asszisztens-valasz eltunik, typing indicator jelenik meg, majd az uj valasz kerul a helyere.

Fontos UI dontes:

- a beszelgetes cimet nem kulon, allando felso input mezoben szerkesztjuk,
- letrehozaskor nincs explicit cimadas,
- a cim automatikusan az elso user uzenetbol kepzodik,
- kezi atnevezes a beszelgeteskartya context menujebol nyilo sajat tokenizalt dialogusbol erheto el.

Mobilon:

- chat lista es aktiv chat egymas ala torik,
- a chat canvas fix belso magassagot kap,
- a composer es az uzenetfolyam ugyanazt a stabil belso scroll-logikat koveti.

## 9. Frontend viselkedes

Elso baseline-ban kesz:

- uj chat letrehozasa,
- chat kivalasztasa,
- uzenet kuldese,
- assistant valasz megjelenitese,
- elkuldott user uzenet azonnali megjelenitese,
- assistant typing indicator,
- betoltesi allapot,
- hibaallapot,
- chat lista frissitese,
- chat torles soft delete modellel,
- aktiv beszelgetes torlese utan a felulet automatikusan betolti a legfrissebb megmaradt beszelgetest; ha nincs ilyen, tiszta ures kezdooldal jelenik meg,
- automatikus chat cim az elso uzenetbol,
- kezi atnevezes context menubol nyilo sajat dialogussal,
- Enter a beviteli mezon belul sortorest ad; kuldes csak a composer kuldes gombjaval tortenik,
- assistant valasz masolasa frontend-only modon,
- csak az utolso assistant valasz ujrageneralasa,
- ujrageneralasnal az utolso assistant valasz torlodik, majd az elozo user uzenetre kerul uj valasz,
- ujrageneralas kozben a frontend in-flight zarat es typing allapotot hasznal, hogy ne indulhasson tobb parhuzamos regenerate keres,
- Gondolkodo UI kapcsolo, amely uzenetkuldesenkent es ujrageneralasenkent normal vagy model_default reasoning modot kuld.

Tudatosan kihuzott irany:

- streaming valasz. Az LM Studio technikailag tamogat SSE streaminget, de ehhez kulon backend streaming endpoint, stream-fogyaszto frontend es reszleges uzenetmentes kellene. Jelenleg nem akarjuk ezt a komplexitast.

## 10. CSS token es dark mode kovetelmeny

Az AI-asszisztens UI kizarolag a mar kialakitott vizualis rendszerre epuljon.

Hasznalando iranyok:

- panel/surface tokenek,
- text role tokenek,
- border/radius/shadow tokenek,
- choice-button/nav-button tokenek,
- control height es spacing tokenek,
- popup/dropdown role tokenek,
- markdown answer megjelenites, ha chatvalasz Markdown jellegu.

Kerulendo:

- direkt komponensszintu szinkodok,
- panelenkenti dark-mode override,
- egyedi gombstilus,
- uj arnyek/border rendszer,
- raw HTML rendereles.

A mar elfogadott dark mode miatt az uj modulnak akkor kell jol mukodnie, ha a komponensek a role-tokenekbol kapjak a szineket.

## 11. Biztonsagi es megbizhatosagi szabalyok

Az AI-asszisztens altalanos chat, de a tartalma tovabbra is untrusted input/output.

Frontend:

- ne rendereljen raw HTML-t,
- Markdown rendereles eseten HTML tiltva legyen,
- hosszu kodblokkok, linkek, sorok ne fussanak ki panelbol.

Backend:

- parameterized ORM/SQL,
- nincs shell hivas,
- nincs fajlrendszer hozzaferes chat prompt alapjan,
- nincs automatikus dokumentumolvasas,
- LM Studio hivasnal store false maradjon,
- LLM hibakat felhasznalobarat magyar hibaallapotkent kell visszaadni.

## 12. Tesztelesi terv

Backend tesztek:

- chat letrehozas,
- chat lista,
- chat detail uzenetekkel,
- user uzenet mentese,
- assistant valasz mentese mock providerrel,
- LLM hiba eseten kezelheto error,
- chat rename,
- chat delete/archive,
- reasoning payload opcio unit teszt, ha az adapter bovul.

Frontend verifikacio:

- npm build,
- uj modul megjelenik a navigacioban,
- uj chat,
- uzenet kuldes,
- valasz megjelenites,
- ures allapot,
- hibaallapot,
- dark mode vizualis ellenorzes,
- mobil stack ellenorzes.

Live smoke:

1. LM Studio fut.
2. Backend/frontend fut.
3. AI-asszisztens modul megnyitasa.
4. Uj chat.
5. Egyszeru kerdes.
6. Valasz mentese historyba.
7. Oldal frissites utan a chat visszanyithato.
8. Uj chat indithato.
9. Korabbi chat torolheto/archivalhato.

## 13. Implementacios sorrend

Javasolt sorrend:

1. Backend schema/migration: assistant_chats es assistant_messages.
2. Backend model/schema/API: CRUD alapok, message send endpoint, mockolhato LLM provider-hivas.
3. LLM adapter finomitas: opcionalis reasoning request parameter elokeszitese, a jelenlegi stabil reasoning off viselkedes megtartasa alapertelmezettkent.
4. Backend tesztek: API es provider payload unit/regression tesztek.
5. Frontend modul: navigacios menupont, chat lista, aktiv chat panel, input/kuldes, history betoltes.
6. Frontend token audit: vilagos/sotet mod, mobile query, overflow es Markdown/kodblokk kezeles.
7. Live smoke: valos LM Studio hivas, reasoning default ellenorzes, history persistencia.

## 14. Jelenlegi implementacios allapot

2026-06-24 allapot:

- Backend adatmodell es migracio kesz: assistant_chats, assistant_messages, Alembic 0051_assistant_chats.
- Backend API kesz az elso baseline-hoz: chat lista, letrehozas, reszlet, atnevezes, soft delete, uzenet kuldese, utolso assistant valasz ujrageneralasa.
- A chat letrehozas backend contractja megtisztitva: nincs create-time title, csak alapcim, elso uzenetbol automatikus cim, es PATCH-alapu kesobbi atnevezes.
- LLM adapter kesz az elso verziohoz: az AI-asszisztens optionalis request-szintu reasoning_mode mezot tud hasznalni, mikozben a tobbi modul stabil Qwen reasoning: off alapviselkedese megmarad.
- Frontend baseline elfogadva: kulon AI-asszisztens modul a Tudásbázis es az Audit napló kozott, beszelgetes rail, context-menu atnevezes/torles, sajat tokenizalt atnevezo dialogus, megosztott tokenizalt torlesi megerosites, stabil belso chat canvas, belso uzenet-thread scroll, also soros composer, centered empty-state composer, Markdown valaszmegjelenites, typing indicator, valaszmasolas, csak-utolso-valasz ujrageneralas in-flight zarral, Gondolkodo reasoning toggle, gombos kuldes Enter-sortoressel, beviteli mezon kivuli kuldes/reasoning gombokkal, aktiv chat torlese utani automatikus kovetkezo-chat betoltes, token-alapu vilagos/sotet stilus, mobil torodes. A composer textarea belso input shellt hasznal, a fokusz allapot szinvaltassal jelzett, de meretugrast nem okoz, a tobbsoros szoveg csak valodi tulcsordulasnal kap scrollbart.
- Popup/dropdown vizualis szereptokenek bevezetve: searchable-select dropdownok es az asszisztens context menu ugyanarra a light/dark token retegre epulnek.
- Globalis scrollbar role tokenek bevezetve: a gorgetosav merete, thumb szine, trackje es belso paddingje CSS tokenekbol jon; az AI-asszisztens composer csak a sajat belso track margojat tartja lokalisan.
- Tudatosan nincs ugyirat-, dokumentum-, RAG-, objektum- vagy audit/provenance integracio.

Ellenorzes:

- .venv/bin/python -m pytest tests/test_assistant.py tests/test_llm.py -> 25 passed friss celzott AI-asszisztens/LLM slice
- npm --prefix frontend run build -> passed
- git diff --check -> passed

Kovetkezo logikus lepes: az AI-asszisztens jelenlegi baseline-ja elfogadott, tovabbi munka csak konkret live UX vagy mukodesi problema alapjan induljon. Streaming tovabbra sem cel.

## 15. Lezart es nyitott dontesek

Lezart elso-baseline dontesek:

1. A chat history elso korben soft delete modellt hasznal.
2. A Gondolkodo reasoning UI kesz; uzenetkuldesnel es ujrageneralasnal request-szinten kuld normal vagy model_default modot.
3. A chat cim automatikusan az elso user uzenetbol kepzodik, kezi modositas context-menu atnevezessel tortenik.
4. Streaming nincs az elso baseline-ban es tovabbra sem cel; stabil non-stream valasz a cel.
5. Kulon investigative audit esemeny nincs chat kuldeshez, mert ez nem nyomozati provenance workflow.
6. A kesobbi hasonlo megerosito vagy beirasos muveletekhez is a megosztott sajat tokenizalt app-dialog minta hasznalando; browser-native confirm / prompt nem legyen ujra bevezetve.
7. Valaszmasolas kesz frontend-only ikonnal az assistant buborek alatt.
8. Ujrageneralas kesz, de csak az utolso assistant valaszon; a regi assistant valasz torlodik, majd uj LLM-hivas keszul az elozo user uzenetbol.
9. Enter nem kuld uzenetet, hanem sortorest ad; kuldes csak a composer kuldes gombjaval tortenik.
10. Aktiv chat torlese utan a felulet automatikusan a legfrissebb megmaradt chatet tolti be.
11. A composer fokuszvisszajelzese meretstabil border-szinvaltassal tortenik; uj plusz outline vagy layout-ugras nem hasznalhato.
12. A scrollbark kinezetet globalis CSS tokenek adjak, nem komponensenkenti ad hoc szabalyok.

Nyitott ismert AI-asszisztens szal nincs; tovabbi munka konkret live UX vagy mukodesi problema alapjan induljon.

## 16. Elfogadasi kriterium

Az elso verzio akkor tekintheto kesznek, ha:

- az AI-asszisztens kulon modulban elerheto,
- aktiv ugy nelkul is hasznalhato,
- uj chat indithato,
- chat history mentodik,
- korabbi chat visszanyithato,
- a modell valaszt ad a jelenlegi LM Studio providerrel,
- a frontend nem hasznal egyedi, tokenen kivuli szinrendszert,
- dark mode kulon komponensszintu javitas nelkul vallalhato,
- nincs automatikus RAG/dokumentum/objektum integracio,
- a megvalositas nem zavarja a forrashivatkozott nyomozati workflow-kat.
