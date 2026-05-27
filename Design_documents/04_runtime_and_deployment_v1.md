# Lokális Nyomozati Iratintelligencia Rendszer
## Runtime és deployment v1

## 1. Cél

Ez a dokumentum azt rögzíti, hogy a készülő rendszer fejlesztési, MVP és későbbi üzemi környezetben hol és hogyan fusson.

A fő cél:

- a Windows 11 host maradjon kényelmes munkaállomás,
- a rendszer alkalmazás- és adatfeldolgozó része Linux-környezetben fusson,
- az LLM inference használhassa a már működő natív Windowsos LM Studio környezetet,
- a teljes rendszer továbbra is lokális, auditálható és cloud-független maradjon.

## 2. Ajánlott fejlesztési topológia

Fejlesztéshez és MVP-prototípushoz az ajánlott topológia:

```text
Windows 11 host
  ├─ VS Code / Codex / browser
  ├─ LM Studio
  │   ├─ loaded local model
  │   ├─ local OpenAI-compatible API server
  │   └─ native Windows hardware acceleration
  │
  └─ WSL2 Ubuntu
      ├─ FastAPI backend
      ├─ worker pipeline
      ├─ PostgreSQL
      ├─ Qdrant
      ├─ Docling / OCR / HuSpaCy / regex processing
      ├─ frontend development server
      ├─ original document storage
      ├─ derived text and index metadata
      ├─ audit JSONL logs
      └─ exports
```

Ebben a modellben a Windows 11 nem a teljes rendszer natív futtatókörnyezete, hanem host és munkaállomás. A rendszer fő szolgáltatásai WSL2 Ubuntu alatt futnak.

## 3. Fejlesztési környezet szerepei

## 3.1 Windows 11 host

Feladata:

- VS Code és Codex futtatása,
- böngészős UI használata,
- LM Studio natív futtatása,
- lokális modell betöltése és kiszolgálása,
- opcionális GPU/hardveres gyorsítás biztosítása.

Nem javasolt feladata:

- PostgreSQL natív Windows service-ként futtatása,
- Qdrant natív Windows service-ként futtatása,
- OCR/NLP pipeline natív Windows alatti elsődleges futtatása,
- case storage szétszórása Windows könyvtárakba.

## 3.2 WSL2 Ubuntu

Feladata:

- backend futtatása,
- worker folyamatok futtatása,
- PostgreSQL és Qdrant futtatása,
- dokumentumfeldolgozás,
- OCR,
- NLP,
- indexelés,
- audit log írás,
- export generálás,
- fejlesztői Linux-környezet biztosítása.

Javasolt, hogy az implementációs repo és a runtime adatok WSL fájlrendszeren legyenek, ne `/mnt/c/...` alatt.

Példa:

```text
~/projects/BoberDetective
~/boberdetective-data
```

## 4. LLMProvider strategy

## 4.1 Development default LLM provider

Development default LLM provider:

```text
LM Studio running natively on the Windows 11 host,
exposed through its local OpenAI-compatible API.
```

Provider abstraction:

```text
The backend uses an LLMProvider interface so LM Studio can later be replaced
by Ollama, llama.cpp, or another local runtime without changing the analysis modules.
```

## 4.2 Miért LM Studio az MVP fejlesztési default?

Az LM Studio választása fejlesztési defaultként indokolt, ha:

- már telepítve van a Windows 11 hoston,
- stabilan fut,
- jól használja a helyi hardvert,
- lokális API szerverként elérhető,
- OpenAI-kompatibilis endpointokat biztosít,
- támogatja a strukturált JSON output munkafolyamatot,
- embedding endpoint vagy külön embedding provider illeszthető mellé.

Ez nem jelenti azt, hogy a rendszer LM Studio-függő lesz. Az LM Studio csak az elsődleges fejlesztési provider.

## 4.3 LLMProvider interfész elvárt képességei

Az alkalmazás elemzési moduljai csak az `LLMProvider` absztrakción keresztül hívhatnak modellt.

Javasolt provider műveletek:

```text
LLMProvider.generate(prompt, context, schema)
LLMProvider.embed(texts)
LLMProvider.healthcheck()
LLMProvider.model_info()
```

Később bővíthető:

```text
LLMProvider.list_models()
LLMProvider.validate_structured_output(response, schema)
LLMProvider.count_tokens(text)
```

## 4.4 OpenAI-kompatibilis provider adapter

Mivel LM Studio OpenAI-kompatibilis lokális API-t biztosít, érdemes általános `OpenAICompatibleProvider` adaptert tervezni.

Ez használható lehet:

- LM Studio,
- llama.cpp OpenAI-compatible server,
- Ollama OpenAI-compatible endpoint, ha az adott verzióban megfelelő,
- egyéb lokális OpenAI-compatible runtime.

Konfigurációs példa:

```text
LLM_PROVIDER=lm_studio
LLM_BASE_URL=http://<windows-host>:1234/v1
LLM_API_KEY=lm-studio
LLM_CHAT_MODEL=<local-model-id>
LLM_EMBEDDING_MODEL=<local-embedding-model-id>
```

Az API kulcs ebben a fejlesztési modellben technikai kompatibilitási érték lehet, de a konfigurációban akkor is kezeljük explicit módon.

## 4.4a LM Studio native API adapter megjegyzések

> **Aktualis megjegyzes, 2026-05-27:** az implementacio mar kulon chat- es embedding-modell betoltesi utat hasznal LM Studio native API-n. A jelenlegi helyi profil: chat `context_length=61440`, `eval_batch_size=4096`, `flash_attention=true`, `offload_kv_cache_to_gpu=true`; embedding default `text-embedding-bge-m3`, `context_length=4096`. Az LM Studio jelenleg nem fogadja el embedding modellre az `eval_batch_size`, `flash_attention` es `offload_kv_cache_to_gpu` mezoket, ezert azokat embedding loadnal nem kuldjuk. A friss session allapotot mindig a `CURRENT_STATE.md` es `AI_NOTES.md` tartalmazza.

2026-05-12 update:

Az LM Studio native API-ja a jelenlegi helyi környezetben hasznosabb a Qwen reasoning modellekhez, mint az OpenAI-compatible `/v1/chat/completions` útvonal, mert a native endpoint támogatja a reasoning explicit kikapcsolását.

Endpoint:

```text
POST /api/v1/chat
```

Fontos request mezők:

```json
{
  "model": "qwen/qwen3.5-9b",
  "input": [
    {
      "type": "message",
      "content": "..."
    }
  ],
  "system_prompt": "...",
  "reasoning": "off",
  "temperature": 0.1,
  "max_output_tokens": 1600,
  "store": false
}
```

Gyakorlati megjegyzések:

- `reasoning: "off"` csak reasoning-et támogató modelleknél küldhető. Llama 3.1 8B esetén hiba, ezért modellfüggő kapcsoló kell.
- Az LM Studio native API a dokumentáció szerint `max_output_tokens` mezőt használ. A korábban próbált `maxTokens` és `max_tokens` kulcs hibás.
- `store: false` ajánlott érzékeny iratoknál, hogy a chat ne kerüljön LM Studio chat history-ba.
- `system_prompt` tisztább, mint a system/user üzenetek kézi összefűzése.
- A helyi tesztben az `input` elem `{"type": "text", "content": "..."}` alakot is elfogadott, de a dokumentált alak `{"type": "message", "content": "..."}`. Következő optimalizálásnál érdemes a dokumentált formára átállni és visszatesztelni.

Load endpoint későbbi optimalizáláshoz:

```text
POST /api/v1/models/load
```

Hasznos load paraméterek:

- `context_length`
- `eval_batch_size`
- `flash_attention`
- `offload_kv_cache_to_gpu`
- `echo_load_config`

Ezeket nem kell az első source-cited analysis smoke-ba belekeverni. Előbb legyen stabil, auditált elemzési útvonal, utána jöhet VRAM/sebesség tuning.

## 4.5 WSL-ből Windows LM Studio elérése

Ha LM Studio Windows hoston fut, a WSL backendnek HTTP-n kell elérnie.

Lehetséges megoldások:

1. Windows host IP használata WSL felől.
2. Docker/Compose esetén `host.docker.internal` jellegű elérés.
3. LM Studio server olyan interfészen hallgat, amely WSL-ből elérhető.

Biztonsági alapelv:

- az LM Studio API ne legyen nyitva feleslegesen a teljes LAN felé,
- ha nem csak localhoston hallgat, Windows firewall szabállyal korlátozni kell,
- az API elérését auditált backend konfiguráción keresztül kezeljük.

## 4.6 Mit kell auditálni LLM hívásnál?

Minden LLM-alapú analysis run esetén tárolni kell:

- `provider_type`, például `lm_studio`,
- provider base URL vagy konfigurációs azonosító,
- model name / model identifier,
- model version vagy model file identifier, ha elérhető,
- context length,
- temperature,
- top_p és egyéb generation settings,
- seed, ha támogatott és használt,
- prompt template neve és verziója,
- output schema neve és verziója,
- input chunkok listája,
- validációs státusz,
- hibaüzenet, ha volt.

Ezzel az LM Studio használata ugyanúgy auditálható marad, mint bármely más provider.

## 5. Szolgáltatási modell MVP-ben

MVP fejlesztéshez ajánlott induló modell:

```text
WSL2 Ubuntu
  ├─ PostgreSQL
  ├─ Qdrant
  ├─ FastAPI backend
  ├─ worker process
  ├─ frontend dev server
  └─ document storage

Windows 11
  └─ LM Studio local server
```

Gyakorlati fokozatok:

1. PostgreSQL és Qdrant konténerben.
2. Backend eleinte WSL Python virtualenvben.
3. Worker eleinte WSL Python virtualenvben.
4. Frontend eleinte WSL/Node dev serverrel.
5. Később backend, worker és frontend is konténerbe tehető.

## 6. Adattárolási javaslat

Az ügyadatok ne szétszórt Windows elérési utakon éljenek. A rendszer importkor másolja be az eredeti fájlokat saját case storage alá.

Fejlesztési példa:

```text
~/boberdetective-data/
  ├─ cases/
  │   └─ <case_id>/
  │       ├─ originals/
  │       ├─ derived/
  │       ├─ audit/
  │       └─ exports/
  ├─ postgres/
  └─ qdrant/
```

Üzemi Linux példa:

```text
/var/local/boberdetective/
  ├─ cases/
  ├─ postgres/
  ├─ qdrant/
  └─ backups/
```

Alapelv:

- eredeti dokumentum immutable módon bekerül a rendszer storage alá,
- hash az eltárolt eredeti fájlról készül,
- adatbázis metaadatot és útvonalat tárol,
- OCR/page/chunk/index/export származtatott adatként kezelendő,
- audit JSONL külön append-only jellegű fájlban is megmarad.

## 7. Hálózat és biztonság

Fejlesztésben minden szolgáltatás lehetőleg csak lokálisan legyen elérhető.

Javasolt alapelv:

```text
Backend API: localhost / WSL-local
Frontend: localhost
PostgreSQL: internal / localhost
Qdrant: internal / localhost
LM Studio: Windows host local API, WSL felől korlátozottan elérhető
```

Később controlled deployment esetén:

- zárt belső hálózat,
- explicit firewall szabályok,
- külső modell API tiltása alapértelmezetten,
- export naplózás,
- backup titkosított helyre,
- admin override-ok auditálása.

## 8. MVP és későbbi üzemi irány

Javasolt fokozatok:

```text
1. Fejlesztés:
   Windows 11 + WSL2 Ubuntu + LM Studio on Windows

2. MVP / belső pilot:
   erősebb Windows 11 workstation + WSL2 + Docker Compose + LM Studio

3. Komolyabb üzemi használat:
   dedikált natív Linux workstation vagy server,
   lokális vagy zárt hálózati inference runtime-mal
```

WSL2 fejlesztésre és pilotra praktikus. Komolyabb, érzékeny ügyanyaggal dolgozó üzemi környezetben hosszabb távon dedikált Linux gép vagy szerver tisztább.

## 9. Nyitott technikai ellenőrzések

Az implementáció előtt vagy elején röviden validálni kell:

1. WSL backend eléri-e stabilan a Windows hoston futó LM Studio API-t.
2. LM Studio JSON schema / structured output elég megbízható-e a kiválasztott modellnél.
3. Embeddinget LM Studio adja-e, vagy külön embedding provider kell.
4. A kiválasztott modell magyar nyelven elég jó-e claim, event és contradiction candidate feladatokra.
5. A provider válaszából kinyerhető-e elég modellmetaadat az audit loghoz.
6. Timeout, retry és hibakezelés hogyan működik hosszabb elemzési futásoknál.

## 10. Rövid döntés

Az MVP fejlesztési célkörnyezete:

```text
Windows 11 host munkaállomásként,
WSL2 Ubuntu alkalmazásruntime-ként,
LM Studio natív Windowsos default LLM providerként,
LLMProvider absztrakcióval a későbbi cserélhetőséghez.
```

Ez a felállás megtartja a lokális, auditálható működést, miközben kihasználja a jelenlegi gépen már jól működő LM Studio környezetet.
