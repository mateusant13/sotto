# Recibo — lane `audio-source-metadata` (METADE: **a FONTE DO SOM**)

Data: 2026-10-07 (horário local −03:00). Máquina: a do dono, `H:\sotto`.
Âmbito: **só** a fonte do som. A app em foco e a fila de foco são de outra lane e **não** foram tocadas.
Tudo o que escrevi está em `H:\sotto\_main\`. Não toquei em `worker/`, `app/panel/`, `app/webview/`.

---

## 0. Veredictos (o que fica decidido)

| # | afirmação | estado |
|---|---|---|
| V1 | Enumerar as sessões de áudio do WASAPI dá, por sessão: `pid`, `exe`, `display_name`, `icon_path`, `is_system_sounds`, `identifier`, `instance_identifier`, estado, volume, mute **e um meter por sessão** | **PROVADO** (21/21 sessões com meter legível, 25 740 leituras, 0 indisponíveis) |
| V2 | Dá para saber **qual está a soar mais alto**, não só quais existem | **PROVADO** (meter por sessão via `IAudioSessionControl2::QueryInterface(IAudioMeterInformation)`) |
| V3 | **HIPÓTESE CENTRAL REFUTADA**: o Chromium **não** põe o título da aba no `GetDisplayName()` da sessão de áudio | **REFUTADA por medição** — `display_name` = `''` (string vazia) em **1200** leituras da sessão do Chrome, **141** delas com o Chrome comprovadamente a soar |
| V4 | O PID da sessão **não** é o da aba: é o processo utilitário de áudio do Chromium | **CONFIRMADO** — pid 14412 = `--type=utility --utility-sub-type=audio.mojom.AudioService` |
| V5 | O título da **aba que fez o som** sai daí? | **NÃO CONSEGUI** — nem pelo WASAPI (V3) nem por UI Automation (ver §3) |
| V6 | ShareX faz proveniência por app/aba? | **NÃO.** Escolhe um **dispositivo DirectShow** e passa-o ao `ffmpeg.exe` como `-i audio=<nome>` (§7) |
| V7 | Existe algum caminho do sistema para "que aba fez o som"? | **NÃO.** O único caminho verdadeiro é uma **extensão de navegador** (§5.1, contrato `sotto.browser-tab/1`) |
| V8 | Enumerar só a endpoint por omissão serve? | **NÃO — dá a app ERRADA.** O som transcrito ia para `CABLE Input`, não para a endpoint por omissão (`VoiceMeeter Input`) (§2.1, §5.2) |

---

## 0.1 Correcções deste próprio recibo (o que estava errado e foi corrigido)

1. **Afirmei um controlo vermelho que não tinha corrido.** A primeira versão dizia que o `--neg-arm-iid` fazia
   falhar todas as leituras de meter. Ao correr, deu `meter_reads_ok=21` — porque o IID configurável só era usado
   no meter do **endpoint**, não no da sessão. **Corrigi o probe** (o QI por sessão passa a usar o IID
   configurado) e voltei a correr: agora `ok=0 / unavailable=21`. O texto do §2.2 é o resultado **medido**.
2. **Placeholders inventados na tabela de sha256** das fontes upstream: substituídos pelos valores reais de
   `Get-FileHash` (§8).
3. **Um braço do `--selftest` estava mal escrito** e deu `RED 9/10`; corrigido para exercitar a partição real →
   `GREEN 10/10`. Registado em §2.6.
4. O `audio-source-probe.py` mudou depois de eu o ter hasheado pela primeira vez; o sha256 do §8 é o final.

---

## 1. Instrumento

**Via canónica** (a mesma do misturador de volume do Windows), toda por COM/WASAPI **sem abrir stream de captura**:

```
IMMDeviceEnumerator → EnumAudioEndpoints(eRender, ACTIVE) e GetDefaultAudioEndpoint(eRender, eMultimedia)
  → IMMDevice::Activate(IID_IAudioSessionManager2) → QueryInterface(IAudioSessionManager2)
    → GetSessionEnumerator() → IAudioSessionControl (GetSession(i))
      → QueryInterface(IAudioSessionControl2)  → GetProcessId / GetDisplayName / GetIconPath /
                                                 GetSessionIdentifier / GetSessionInstanceIdentifier /
                                                 IsSystemSoundsSession / GetState
      → QueryInterface(IAudioMeterInformation) → GetPeakValue()          [o meter POR SESSÃO]
      → QueryInterface(ISimpleAudioVolume)     → GetMasterVolume / GetMute
  → IMMDevice::Activate(IID_IAudioMeterInformation) → GetPeakValue()      [meter do ENDPOINT = controlo]
```

- `IAudioMeterInformation` **não existe no pycaw**; defini-o à mão (IID `{C02216F6-8C67-4B5B-9D00-D008E73E0064}`, 4 métodos na ordem da MSDN) em `audio-source-probe.py`.
- **Não abri nenhum dispositivo para captura e não reproduzi áudio.** `Activate` do endpoint e `Activate`/`QueryInterface` do meter não criam stream — por isso coexistem com o loopback do worker (pid 29008). O worker continuou a transcrever durante todas as medições.
- Caminho do executável por PID: `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `QueryFullProcessImageNameW` (API nativa). **Zero** `Win32_Process` em ciclo. Fiz **uma** consulta `Get-CimInstance Win32_Process` em toda a lane, para ler a linha de comandos de dois PIDs (§2.4).
- Dependências instaladas **só** em `_main\_libs` (`pip install --target`): `comtypes 1.4.17`, `pycaw 20260927`, `uiautomation 2.0.29`, `psutil 7.2.2`. Nada foi instalado no site-packages do sistema.
- Lançamento sempre escondido: `pythonw.exe` (probes de UIA) ou `python.exe` com `Start-Process -WindowStyle Hidden` (probes do meter, para recolher stdout). Nenhuma janela visível (§8).

### Ficheiros-probe
| ficheiro | o que é |
|---|---|
| `_main\audio-source-probe.py` | o probe principal: sessões + meters + escolha da fonte. É o entregável nº1 |
| `_main\audio-tab-title-probe.py` | UIA na tira de abas do Chrome (títulos, seleção, indicador de áudio) |
| `_main\audio-tab-audible-probe.py` | **simultâneo**: meter WASAPI + UIA na mesma amostra (para correlacionar) |
| `_main\as-*.py` | analisadores dos JSONL (censo de display_name, correlação, indicador) |

**Como se corre o probe principal:**
```
py -3 _main\audio-source-probe.py --selftest                      # gate da logica, sem audio (GREEN 10/10)
py -3 _main\audio-source-probe.py --list-endpoints                 # endpoints de render activas
py -3 _main\audio-source-probe.py --once --all-endpoints           # uma amostra, todas as endpoints
py -3 _main\audio-source-probe.py --secs 60 --hz 4 --all-endpoints --out x.jsonl --txt x.txt
py -3 _main\audio-source-probe.py --once --all-endpoints --neg-arm-iid     # controlo (vermelho)
py -3 _main\audio-source-probe.py --once --all-endpoints --neg-arm-floor   # controlo do chao (fraco: precisa de audio)
```
Cada linha de `--txt` é: `[ts] SOURCE pid=… exe=… peak_win=… peak=… name=… | pid=… exe=… peak=… win=… dn=… sys=… st=…`
(uma entrada por sessão com meter). O JSONL tem a amostra completa (§5).

---

## 2. Medições reais desta máquina

### 2.1 Topologia (verbatim, `--list-endpoints` / amostra `--all-endpoints`)

6 endpoints de render **activos**, com a endpoint por omissão a ser:

```
endpoint default=True  name='VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'  id={0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}
endpoint default=False name='Speakers (NVIDIA Broadcast)'
endpoint default=False name='CABLE Input (VB-Audio Virtual Cable)'
endpoint default=False name='Fones de ouvido (soundcore Space Q45)'
endpoint default=False name='AG251F1WG2 (NVIDIA High Definition Audio)'
endpoint default=False name='Alto-falantes (HyperX Quadcast)'
```

Isto confirma o AGENTS.md (a por omissão é o VoiceMeeter Input) **e acrescenta o facto que interessa a esta lane**:
o som que o worker transcreve **não** passa pela endpoint por omissão — passa pelo **`CABLE Input`** (§2.2).
Ou seja: **enumerar só a endpoint por omissão teria dado a resposta errada.** É por isso que o probe varre todas as endpoints activas.

Sessões observadas (21 numa amostra típica), por exe: `NVIDIA Broadcast.exe`, `python.exe` (×3, o worker 29008),
`chrome.exe` (pid 14412), `steam.exe` (×4), `chatterino.exe`, `Discord.exe` (×2), `nvcontainer.exe`,
e a sessão especial de **System Sounds** (pid 0, `is_system_sounds=True`, presente em cada endpoint).

### 2.2 Controlo positivo do instrumento (a prova de que o meter não é um zero decorativo)

Janela **11:48:32 → 11:49:13**, 155 amostras a 4 Hz, enquanto o worker do dono **transcrevia** (o log da app cresceu **7062 B** nessa janela):

| medido | valor |
|---|---|
| meter do endpoint `CABLE Input (VB-Audio Virtual Cable)` | **0.126788** (máx. da janela) |
| meter da sessão `chrome.exe` no `CABLE Input` | **0.149162** (máx. da janela) — **a mais alta** |
| meter da sessão `python.exe` (o loopback do worker) | 0.126788 |
| meter de todos os outros endpoints | 0.000000 |

**As duas cores do mesmo gate (ambas CORRIDAS, não afirmadas):**
- **verde**: com áudio a tocar, o meter sai de zero e o `chrome.exe` é a fonte mais alta (números da tabela acima).
- **vermelho (controlo, medido)**: `--neg-arm-iid` (IID do meter corrompido, `{00000000-…-FF}`) → **`meter_reads_ok=0`, `meter_reads_unavailable=21`**, todas as sessões com `peak=null`, erro `TypeError: must be a ctypes type` (21×). Ou seja: o número **deixa de existir** quando o IID deixa de resolver — a leitura passa mesmo por uma resolução de interface, não é uma constante. (Modo de falha exacto: o comtypes recusa um GUID não registado antes de chegar ao `E_NOINTERFACE` do COM. É um controlo mais fraco do que "o COM recusou o IID", e fica dito assim.)
- **vermelho (controlo do chão, medido em separado)**: o `--neg-arm-floor` ao vivo (chão 1.1) devolveu `source=null` — mas nesse instante **não havia áudio nenhum**, logo o braço é **inconclusivo** (não distingue "o chão cortou" de "não havia nada"). O controlo válido do chão é o do `--selftest` (§2.6), que é determinístico e não precisa de áudio.

### 2.3 HIPÓTESE CENTRAL — **REFUTADA**, com verbatim

A pergunta era: *o Chromium põe o título da aba no `GetDisplayName()` da sessão?*

**Não.** Verbatim, sessão do Chrome **a soar** (`peak=0.102777`, `state=Active`, `volume=0.85`, `muted=False`), endpoint `CABLE Input (VB-Audio Virtual Cable)`, 2026-10-07T11:48:54.418−0300:

```
pid            = 14412
display_name   = ''                       <-- STRING VAZIA
icon_path      = ''
identifier     = '{0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}|\Device\HarddiskVolume17\Program Files\Google\Chrome\Application\chrome.exe%b{00000000-0000-0000-0000-000000000000}'
instance_id    = '{0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}|\Device\HarddiskVolume17\Program Files\Google\Chrome\Application\chrome.exe%b{00000000-0000-0000-0000-000000000000}|1%b14412'
state/peak/vol = Active 0.102777 0.85 False
```

**Censo (instrumento: `as-displayname-census.py`, sobre 5 ficheiros JSONL, 1227 amostras, 25 740 leituras de meter):**

| exe | leituras com `display_name` vazio | com `display_name` preenchido |
|---|---|---|
| `chrome.exe` | **1200** | **0** |
| `python.exe` (worker) | 4908 | 0 |
| `steam.exe` | 6135 | 0 |
| `Discord.exe` | 2454 | 0 |
| `chatterino.exe` | 1227 | 0 |
| `NVIDIA Broadcast.exe` | 1227 | 0 |
| `nvcontainer.exe` | 1227 | 0 |
| `<pid 0>` (System Sounds) | 0 | **7362** |

E, dentro das leituras do Chrome, **141 têm `peak > 0.001`** (a soar) — em **todas as 141** o `display_name` foi `''`.

O **único** `display_name` não vazio visto nesta máquina em 25 740 leituras é o da sessão de sons do sistema:
`'@%SystemRoot%\System32\AudioSrv.Dll,-202'`.

**Porque é que o misturador mostra "YouTube — Google Chrome" então?** Porque esse nome **não é** o `GetDisplayName()`: é o *fallback* do próprio Sndvol. Documentação da Microsoft, verbatim
([`IAudioSessionControl::SetDisplayName`](https://learn.microsoft.com/en-us/previous-versions/ms678794(v=vs.85))):

> "If the client does not call **SetDisplayName** to assign a display name to the session, the Sndvol program uses a default, automatically generated name to label the session. **The default name incorporates information such as the window title or version resource of the audio application.**"

Ou seja: o `GetDisplayName()` devolve **só o que a app escreveu**, e o Chrome não escreve nada. O misturador
inventa o rótulo a partir do **título da JANELA** — que, num navegador, é o da **aba SELECCIONADA**, não o da
aba que soa. Corroboração no código do Chromium: o único consumidor de `IAudioSessionControl` no
`media/audio/win/` é um **ouvinte** que ignora o nome —
`chromium/media/audio/win/audio_session_event_listener_win.cc:28`, `AudioSessionEventListener::OnDisplayNameChanged(...) { return S_OK; }`.

### 2.4 O PID da sessão **não** mapeia para a aba — confirmado

Uma consulta `Get-CimInstance Win32_Process` (não em ciclo) sobre os dois PIDs:

```
PID 1628 : "C:\Program Files\Google\Chrome\Application\chrome.exe" --single-argument http://127.0.0.1:3080/?token=...
PID 14412: "C:\Program Files\Google\Chrome\Application\chrome.exe" --type=utility --utility-sub-type=audio.mojom.AudioService --service-sandbox-type=audio ...
```

A sessão de áudio é do **pid 14412** (`audio.mojom.AudioService`); a **janela** do Chrome é do **pid 1628**.
Nota adicional que fecha a porta: o Chrome mistura **todas as abas de um perfil** nesse **único** processo de
áudio — há **uma** sessão para o browser inteiro. Logo a granularidade "por aba" **não existe** na camada
WASAPI, por construção; não é só um problema de não haver nome.

### 2.5 O título da aba por UI Automation — medido, e **não serve**

`_main\audio-tab-title-probe.py` (uiautomation sobre `Chrome_WidgetWin_1`). Isto **funciona** para listar abas:

- 2 janelas do Chrome do pid 1628: uma com **7** abas, outra com **23** abas; 1 janela do Discord com 0.
- `TabItemControl.Name` = título da aba (verbatim, exemplos): `'Uso elevado da memória em level down trolling - YouTube: 997 MB'`, `'FELIPE MOURA BRASIL ANALISA a ENTREVISTA de LULA para O FLOW: PIOROU A SITUAÇÃO? - YouTube'`, `'127.0.0.1 - Erro de rede'`, `'Nova guia'`, `'ChatGPT'`.
- `SelectionItemPattern.IsSelected` funciona (exactamente 1 aba seleccionada por janela).
- **`HelpText` = `''` em todas; `ItemStatus` não existe** (AttributeError) — não há propriedade de "está a soar".

Encontrei um indicador com nome prometedor — um filho `AlertIndicatorButton` chamado **`'Desativar som da guia'`**
(*mute tab*) — mas ele **não discrimina**:

| instrumento | resultado |
|---|---|
| presença do botão | presente em **todas** as abas do browser, incluindo `'Nova guia'` e `'127.0.0.1 - Erro de rede'` (onde áudio é impossível) |
| **geometria** do botão (`BoundingRectangle`) | 16×16 em 4 abas, `(0,0,0,0)` nas outras |
| **controlo decisivo** (`audio-tab-audible-probe.py`, meter + UIA **na mesma amostra**, 50 amostras a 3 s) | em **49 de 50** amostras **todos os meters de endpoint valiam exactamente 0.000000** — e as **mesmas 4 abas** continuavam com o indicador 16×16. Na única amostra com som (`browser_peak=0.024811`, endpoint `0.021089`) o conjunto era **o mesmo 4**. |

Conclusão: **o indicador do UIA não acompanha o som** (marca 4 abas de mídia mesmo com o browser em silêncio
medido). E `IsOffscreen` é `False` em todas, logo também não serve. **Não consegui o título da aba que fez o
som** — nem pelo WASAPI, nem pelo UIA. Não vou inventar um número.

### 2.6 Gate da lógica de escolha — `--selftest` (não precisa de áudio)

`py -3 _main\audio-source-probe.py --selftest` → **`SELFTEST-VERDICT: GREEN (10/10 PASS)`, rc=0**.
Testa a função `pick_source()` com candidatos sintéticos (é o que decide "qual soa mais alto"):

| braço | resultado |
|---|---|
| maior `peak_max_win` ganha | PASS (`src=game.exe`) |
| `margin_ratio` = 0.50/0.20 = 2.5 | PASS |
| 2.5 ≥ 1.5 → não ambíguo | PASS |
| `runner_up` é o segundo | PASS (`discord.exe`, 0.2) |
| empate apertado (0.50 vs 0.45) → **ambíguo** | PASS (`margin=1.111`) |
| chão 1.1 corta tudo → `None` | PASS |
| sons de sistema **não** são a fonte na partição de apps | PASS (`src=discord.exe`) |
| mas **são** a fonte no pool total | PASS |
| pool vazio → `None` | PASS |
| exactamente no chão (0.001 com chão 0.001) → passa | PASS |

**A primeira corrida deste gate deu `RED (9/10)`** — o braço dos sons de sistema estava mal escrito (testava
`pick_source`, que **não** faz a partição; a partição é do chamador). Corrigi o braço para exercitar a partição
real e voltou GREEN. Fica registado porque um gate que nunca ficou vermelho não é um gate.

---

## 3. O que NÃO consegui, e porquê (técnico)

1. **Título da aba que fez o som.** Três razões, todas medidas:
   (a) `GetDisplayName()` devolve `''` — o Chromium não o define (1200/1200 leituras; e o código do Chromium mostra o ouvinte a ignorar `OnDisplayNameChanged`).
   (b) O PID da sessão é o **processo utilitário de áudio** (14412), não a aba nem a janela (1628) — e **um** processo de áudio serve **todas** as abas do perfil, logo a mistura é irreversível nesta camada.
   (c) A alternativa UIA **lista** as abas e diz qual está selecionada, mas **não** diz qual soa: o único indicador candidato está aceso em 4 abas mesmo com o browser em silêncio (49/50 amostras com meter 0).
2. **Atribuição por janela em vez de por processo** — não testei `GetWindowThreadProcessId` ascendente para achar a janela "dona" da sessão, porque o processo de áudio do Chromium **não tem janela**; para apps de janela única isto funcionaria (fica por medir, §9).
3. **Distinguir "aba audível" de "aba com sessão de mídia"** — não consegui; o indicador do UIA parece marcar a segunda.
4. **Um intervalo de 150 s (11:43:35→11:46:05) e outro de 130 s (≈11:51→11:53) deram 0.000000 em todas as leituras.** Não posso afirmar que o dono estava em silêncio nesses intervalos: o meu único instrumento independente para "está a tocar" era o crescimento do log da app, e **esse proxy está contaminado** — no tail do log contei **155 `HOT_RELOAD_EVENT` + 38 `RECEIVER_READY` + 830 `BRIDGE_CAPTION_SENT`** em 2000 linhas, ou seja o painel recarrega e **reproduz o histórico**, o que faz o log crescer sem áudio novo. Registado como **não resolvido**, não como silêncio provado. O que **está** provado é o controlo positivo (§2.2): quando há som, o meter mexe.

---

## 4. Gates — as duas cores, em um comando cada

| gate | verde (resultado) | vermelho (controlo que TEM de ficar vermelho) |
|---|---|---|
| o meter por sessão existe e lê | 25 740 leituras, **0** indisponíveis; 21/21 sessões com `peak` | `--neg-arm-iid` **medido**: `meter_reads_ok=0`, `unavailable=21`, todas `peak=null` |
| a lógica "qual soa mais alto" está certa | `--selftest` **GREEN 10/10**, rc=0 | a 1ª corrida do selftest deu **RED 9/10** (braço mal escrito) — corrigido e re-corrido; o gate já mostrou as duas cores |
| o chão de amplitude corta | com som, `source` = o Chrome (§2.2) | `--selftest`: chão 1.1 → `None` PASS. O `--neg-arm-floor` **ao vivo** é **inconclusivo** (não havia áudio) e não é usado como prova |
| o meter acompanha o som | §2.2: endpoint 0.1268 / chrome 0.1492 com o worker a transcrever | §2.5: 49/50 amostras com **todos** os meters de endpoint = 0.000000 (ausência real, o instrumento continua a ler) |
| `display_name` do Chrome | — | **o resultado é o vermelho**: `''` em 1200 leituras (a hipótese morre aqui) |
| ShareX faz proveniência por app | — | grep de termos de sessão nos ficheiros do ShareX = **0**; controlo do mesmo grep (`dshow|AudioSource`) = **25** |
| ausência de janela visível | **SKIP não é um passe**: o censo da casa amostra 1×/60 s e **não pode** provar ausência de janela curta (AGENTS.md). Instrumento próprio: `Select-String ALERTA-JANELA` sobre 139 logs de `_main` com mtime < 2 h → **0 ocorrências**; e todos os lançamentos foram `pythonw.exe` ou `-WindowStyle Hidden` | — |

---

## 5. Contrato de dados proposto — `sotto.audio-source/1`

Uma linha JSONL por amostra. Unidades: **`peak` é amplitude linear em [0,1]** (1.0 = escala cheia);
para dBFS: `20*log10(peak)`. O chão por omissão `0.001` = **−60 dBFS**.

```jsonc
{
  "schema": "sotto.audio-source/1",
  "ts": "2026-10-07T11:48:54.418-0300",   // string, hora local, ms
  "ts_unix": 1791384534.418,              // float, segundos epoch
  "seq": 1234,                            // int, contador da sessão de captura
  "floor": 0.001,                         // float, amplitude linear; declarado
  "win_secs": 1.0,                        // float, janela do pico deslizante

  // A FONTE ESCOLHIDA. null = nada acima do chão.
  "source": {
    "rank": 1,                            // int, 1 = a mais alta
    "pid": 14412,                         // int
    "exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "exe_name": "chrome.exe",             // string
    "display_name": "",                   // string, GetDisplayName() VERBATIM (vazio no Chrome)
    "icon_path": "",                      // string, GetIconPath() verbatim
    "session_identifier": "{0.0.0.00000000}.{2f1295af-...}|\\Device\\...\\chrome.exe%b{00000000-...}",
    "session_instance_identifier": "...|1%b14412",   // chave estável da instância da sessão
    "is_system_sounds": false,            // bool
    "state": "Active",                    // "Active" | "Inactive" | "Expired"
    "muted": false,                       // bool
    "volume": 0.85,                       // float 0..1, volume DA SESSÃO (o slider do misturador)
    "peak": 0.102777,                     // float, amplitude linear INSTANTÂNEA
    "peak_max_win": 0.149162,             // float, máximo na janela `win_secs` (é o critério de escolha)
    "endpoint_id": "{0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}",
    "endpoint_name": "CABLE Input (VB-Audio Virtual Cable)"
  },

  "source_including_system_sounds": { /* mesma forma, ou null */ },

  // COMO se representa "há várias a soar": a lista COMPLETA, ordenada. Nunca colapsar.
  "sources": [ /* objetos como `source`, com rank 1..N, TODAS as que passam o chão */ ],
  "n_sessions_total": 21,                 // int, sessões vistas com meter
  "n_sources_above_floor": 1,             // int, quantas passam o chão
  "margin_ratio": 3.42,                   // float|null, peak_max_win(1)/peak_max_win(2)
  "ambiguous": false,                     // bool, true se margin_ratio < 1.5 (declarado)
  "runner_up": { "pid": 29008, "exe_name": "python.exe", "peak_max_win": 0.0436 },

  "reason": "max-peak_max_win-above-floor",  // ou "all-sessions-below-floor"

  // ---- navegador: o título da ABA. Honesto sobre o que não se sabe.
  // O unico caminho VERDADEIRO e a extensao de navegador (schema sotto.browser-tab/1, §5.1).
  "browser_tab": {
    "available": false,                   // bool
    "tab_id": null,                       // int|null, id da aba DENTRO do browser (so a extensao o da)
    "title": null,                        // string|null
    "url": null,                          // string|null
    "audible": null,                      // bool|null, a aba esta a produzir som AGORA
    "method": null,                       // "extension" | "wasapi-display-name" | "uia-audible-indicator" | "uia-selected-tab" | null
    "confidence": "none",                 // "high" | "medium" | "low" | "none"
    "note": "chromium nao define GetDisplayName (1200/1200 leituras vazias); o PID da sessao e o processo utilitario de audio e serve TODAS as abas do perfil. Nenhuma via sem extensao da a aba audivel."
  }
}
```

**Decisões de representação (as que importam ao consumidor):**

1. **"A fonte" quando há várias**: `source` = a de maior `peak_max_win` (não o `peak` instantâneo — o instantâneo
   pisca e faz a fonte saltar entre apps a cada 250 ms). A lista `sources` inteira vai sempre; `margin_ratio` e
   `ambiguous` dizem se a escolha é firme. Se `ambiguous=true`, a pesquisa deve guardar **todas** as fontes acima
   do chão, não só a primeira.
2. **Sons do sistema** (pid 0) ficam fora de `source` (não são uma "app") mas aparecem em
   `source_including_system_sounds` e na lista — senão perde-se a informação de que o que soou foi um *ding* do Windows.
3. **Chave estável**: usar `session_instance_identifier` (não o `pid`, que se recicla; não o `identifier`, que
   junta todas as instâncias do mesmo exe).
4. **`display_name` vai verbatim, mesmo vazio.** Vazio é um resultado, não um erro — e é o que o Chrome devolve.
5. **`peak` por sessão é medida directa, não estimativa.** Não derivar de volume × nada.

---

## 5.1 O ÚNICO caminho verdadeiro para "que aba fez o som": **uma extensão de navegador**

**Recomendação (decorre da medição, não é opinião).** Provei nesta máquina que a granularidade **por aba não
existe** em nenhuma via do sistema:

| via | porque não dá a aba que soa |
|---|---|
| `IAudioSessionControl2` (WASAPI) | uma sessão **por perfil/processo de áudio**, não por aba; `display_name` = `''` (1200/1200 leituras); o pid é o `audio.mojom.AudioService` |
| indicador de áudio do UIA | aceso em **4 abas** com o browser em silêncio medido (49/50 amostras com todos os meters = 0.000000) |
| título da janela (o que o Sndvol usa) | é a aba **SELECCIONADA**, não a que soa |
| DevTools / `chrome://media-internals` | exigiria relançar o Chrome do dono com `--remote-debugging-port` — inaceitável |

Logo: **a atribuição por aba exige um componente DENTRO do navegador** — uma extensão que sabe, por aba,
`{tabId, title, url, audible}` e o reporta ao Sotto. **Uma extensão é pequena; a mentira é permanente.**

### Contrato proposto — `sotto.browser-tab/1`

A extensão publica em `http://127.0.0.1:<porta>/tabs` (ou um `POST` para o Sotto), **só em loopback**, com um
token efémero. Uma linha/objeto por aba, `audible` a ser o campo que interessa:

```jsonc
{
  "schema": "sotto.browser-tab/1",
  "ts": "2026-10-07T11:48:54.418-0300",   // string, hora local, ms — a extensão carimba
  "browser": "chrome",                     // "chrome" | "edge" | "firefox" | ...
  "profile": "Default",                    // string, o perfil (um perfil = uma sessão WASAPI)
  "window_id": 3,                          // int|null, janela do browser
  "tabs": [
    {
      "tab_id": 210,                       // int, id da aba DENTRO do browser (chave estável)
      "title": "level down trolling - YouTube",  // string
      "url": "https://www.youtube.com/watch?v=...", // string
      "audible": true,                     // bool — A ABA ESTA A PRODUZIR SOM AGORA
      "muted": false,                      // bool
      "active": true,                      // bool, aba seleccionada na sua janela
      "audible_since": 1791384534.1        // float|null, epoch em que ficou audivel
    }
  ]
}
```

**Como se casa com o lado WASAPI (é isto que dá o produto):**
1. `sotto.audio-source/1` diz **que o `chrome.exe` está a soar** e com que `peak` (medido, fiável).
2. `sotto.browser-tab/1` diz **QUAIS as abas com `audible=true`** dentro desse browser.
3. Se **exactamente uma** estiver `audible=true` → essa é a aba, `confidence="high"`.
4. Se **várias** → o sistema **não consegue** dizer qual delas contribui mais (a mistura já aconteceu dentro do
   processo de áudio): gravar **todas** com `confidence="low"` e **não** escolher uma. É o mesmo princípio do
   `ambiguous`/`margin_ratio` do lado das apps.
5. Se a extensão não estiver instalada → `browser_tab.available=false`, `title=null`. **Não preencher com o título da janela.**

### A REGRA (para o código e para o AGENTS.md)

> **O título da janela do navegador NUNCA pode ser apresentado como "a aba que fez o som".**
> É a aba **seleccionada**. Quando o dono ouve uma aba de **fundo** (o caso exacto do pedido dele: *"se eu ouvi
> algum amigo meu falando algo engraçado pelo discord, enquanto eu estava jogando"*), o título da janela aponta
> para a aba errada **com toda a confiança**. Preferir `null` a um palpite que mente.

---

## 5.2 Linha proposta para o `AGENTS.md`

O texto abaixo é a regra de produto que a medição impõe. **Proposta** — não editei o `AGENTS.md` (não é meu
ficheiro nesta lane):

> - **O SOM QUE O WORKER TRANSCREVE NÃO PASSA PELA ENDPOINT POR OMISSÃO — ENUMERAR SÓ A POR OMISSÃO DÁ A
>   RESPOSTA ERRADA.** Medido 2026-10-07 (lane `audio-source-metadata`): a endpoint de render por omissão desta
>   caixa é `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`, mas o Chrome que o worker estava a transcrever
>   renderizava para **`CABLE Input (VB-Audio Virtual Cable)`** — e essa é uma de **seis** endpoints de render
>   activas. O meter do `CABLE Input` leu **0.126788** e a sessão `chrome.exe` **0.149162** enquanto o worker
>   transcrevia, com **todas as outras endpoints a 0.000000**. Qualquer código que pergunte "que app está a soar"
>   tem de varrer **todas** as endpoints de render activas (`EnumAudioEndpoints(eRender, ACTIVE)`), não só
>   `GetDefaultAudioEndpoint`: senão nomeia a app errada com toda a confiança, exactamente no cenário do dono
>   (VoiceMeeter a encaminhar para um cabo virtual).

*(Recibo: `_main/receipt-audio-source-metadata.md`; probe: `_main/audio-source-probe.py --all-endpoints`.)*

---

## 6. Cadência e custo medidos

| instrumento | cadência medida | amostras | CPU (1 núcleo) | RSS | threads |
|---|---|---|---|---|---|
| `audio-source-probe.py` (6 endpoints, 21 sessões, meters) | 4 Hz | **573** em 150.158 s | **2.11 %** (3.172 s CPU) | 54.8 MB | **1** |
| idem | 4 Hz | **497** em 130.077 s | **2.03 %** (2.641 s CPU) | 51.7 MB | **1** |
| idem | 4 Hz | 155 em 40.155 s | 1.98 % | 37.5 MB | 1 |
| `audio-tab-title-probe.py` (UIA, 2 janelas / 30 abas) | por invocação | 1 | **0.281 s CPU / 1.30 s wall** (~22 % de 1 núcleo se corresse a 1 Hz) | 45.5 MB | 1 |
| `audio-tab-audible-probe.py` (meter + UIA juntos) | 3 s | 50 em 150 s | ver `as-audible.jsonl` (`audible-probe-summary`) | — | 1 |

**Recomendação de cadência:**
- **Meter das sessões a 1–2 Hz em regime normal** (≈1 % de 1 núcleo): a *identidade* da fonte muda devagar
  (abrir/fechar uma app), e a 2 Hz ainda se apanha uma troca de faixa. **4 Hz** só com o painel aberto ou perto
  de um corte de clipe — é o que já custa 2 % e 55 MB.
- **Nunca chamar o UIA por omissão.** Só quando `source.exe_name` é um navegador **e** o meter está acima do
  chão; e a **≤0.2 Hz**, com cache do título entre chamadas (0.28 s CPU por dump é ~25× o custo do meter).
- **Uma thread chega** (medido: `threads: 1`). O orçamento de ≤2 threads foi respeitado com folga.

---

## 7. ShareX — a resposta, com ficheiro e linha

ShareX **é** open source (GPL-3.0, `github.com/ShareX/ShareX`). Fui ao código. **Não faz proveniência de áudio
por app nem por aba: escolhe um DISPOSITIVO.** O caminho do áudio dele é DirectShow → `ffmpeg.exe`.

Evidência, verbatim, com ficheiro e linha (cópias locais em `_main\src\`, sha256 em §8):

1. `ShareX.ScreenCaptureLib/ScreenRecording/FFmpegCaptureDevice.cs:43` — o vocabulário de "fonte de áudio" que o ShareX tem é um nome de dispositivo dshow:
   ```csharp
   public static FFmpegCaptureDevice VirtualAudioCapturer { get; } = new FFmpegCaptureDevice("virtual-audio-capturer", "dshow (virtual-audio-capturer)");
   ```
   (e `:41` `None`, `:42` `ScreenCaptureRecorder`; `Value` é uma `string`.)
2. `.../FFmpegOptions.cs:37` — a escolha de áudio é uma **string**, não uma sessão:
   ```csharp
   public string AudioSource { get; set; } = FFmpegCaptureDevice.None.Value;
   ```
3. `.../ScreenRecordingOptions.cs:105` (idem `:128` e `:195`) — é interpolada num argumento dshow do ffmpeg:
   ```csharp
   AppendInputDevice(args, "dshow", true);
   args.Append($"-i audio={Helpers.EscapeCLIText(FFmpeg.AudioSource)} ");
   ```
   Ou seja: **um dispositivo de captura DirectShow, não uma aplicação.** Nada aqui distingue o Chrome do Discord.
4. `Directory.Packages.props` (manifesto central de dependências, 26 linhas) — **não há NAudio, CSCore nem
   qualquer biblioteca de WASAPI/sessões**. As únicas dependências de mídia são `Vortice.Direct2D1`,
   `Vortice.Direct3D11`, `Vortice.MediaFoundation` e `SkiaSharp` (vídeo/ecrã, ver `HDRScreenCapture.cs`).
5. **Instrumento da ausência, com controlo:** o mesmo grep sobre os ficheiros do ShareX descarregados:
   `IAudioSessionManager2|IAudioMeterInformation|IAudioSessionControl|IAudioSessionEnumerator|MMDeviceEnumerator|NAudio|WasapiLoopbackCapture|SetDisplayName|GetDisplayName|AudioSession`
   → **0 matches**; e o **controlo** do mesmo grep (`dshow|AudioSource`) → **25 matches**. Um grep que devolve zero
   num ficheiro que não contém nada é inútil; este devolve zero no que interessa e 25 no que tem de aparecer.

**Conclusão sobre o ShareX:** ler mais dele **não** ensina nada sobre atribuir áudio a uma app ou a uma aba. Ele
resolve um problema diferente (levar *algum* áudio para o ffmpeg) e a granularidade dele é **pior** do que a
nossa: um dispositivo. O que ele confirma, isso sim, é que o caminho "virtual-audio-capturer" é o padrão da
indústria para *capturar* o mix — exactamente o que o worker do dono já faz com o loopback WASAPI. **Não vale a
pena ler mais do que a nossa própria medição.**

---

## 8. Ficheiros que criei (sha256 + tamanho)

Instrumento e código:
| ficheiro | bytes | sha256 |
|---|---|---|
| `_main\audio-source-probe.py` | 24089 | `2F930BFE36D68E30C550C88D337181C931555FAB6B4C3A9500A904847D5945A2` |
| `_main\audio-tab-title-probe.py` | 6405 | `EED33019446A30E3950193D5356009E3A1EF1B358ECDC8712165186FFFFA3E4F` |
| `_main\audio-tab-audible-probe.py` | 6260 | `B646598BDF4033CEDADAAE5BC80C700F0DF84AD76E64F6C4271B9397CFF2C305` |
| `_main\as-analyze.py` | 1877 | `986C030EADF967E019768EC80BF02E502DDA3A4B8C5BA55EF1142F1EA39C5972` |
| `_main\as-indicator-analyze.py` | 1480 | `ABBD6C4C763DB8EBE9EF6A2E3668671D3A78C7EA5E2C1BE08E568FD3435B4D68` |
| `_main\as-displayname-census.py` | 2485 | `A1811118F14377D73D816785D048648444BA852B01DD7957664DD1E9EF4CB354` |
| `_main\as-audible-analyze.py` | 1800 | `F50A32A044168FA8264F99C7015673BFAACD1CEBA34641954F82D17B0A238322` |

> O `audio-source-probe.py` foi **alterado depois** da primeira versão deste recibo (acrescentei o `--selftest`,
> a função `pick_source()` extraída e o controlo do IID por sessão). O sha256 acima é o da revisão **final**,
> 24089 B. A revisão anterior era 21048 B / `D1373D0E…`; qualquer citação dela está obsoleta.

Dados (JSONL por amostra + log humano):
| ficheiro | bytes | sha256 |
|---|---|---|
| `_main\as-once.jsonl` | 18906 | `DFEBA3C0B7CFC1F506E6941589DADBEFD9C524716182C5B2D9C5407329BF9AA0` |
| `_main\as-once.txt` | 2212 | `5814571A043DA616766899FB73B15FA26C39A646B1379D816D017E6D50E3BB0A` |
| `_main\as-control.jsonl` | 3017157 | `42712FC8954A415ED4183F21E281DAF7D373EBAFAD5F04DC2CA759AF1BDD61B4` |
| `_main\as-control.txt` | 289636 | `7C5DC3756A6AB06FB79E76EB590C242F8DE48416626328981455952D84E8C4E2` |
| `_main\as-run1.jsonl` | 10757437 | `10EDB73432736402922ED819A45AEB9DAE7988002E9B41093D03631DD701D69D` |
| `_main\as-run1.txt` | 1058219 | `069A52CFB94EF9DAC1820A0DCF0FFE2E7F9A8F51B9C18881A3CA22BC5823E261` |
| `_main\as-corr.jsonl` | 9225944 | `C5DB9D62445661194598A5585ECD96EA178D38E94A6027E4D032BEB5C85BDD48` |
| `_main\as-corr.txt` | 916272 | `A3746075D9D274793DF6761ACAAD062623CADD9CB47F3A5D907227FA95B1F8FA` |
| `_main\as-now.jsonl` | 18904 | `AAF1526FDA27B20621823AB424B83ED5DFD7AF52DC0114736F7CE6FF62E0A36D` |
| `_main\as-now.txt` | 2210 | `96B2AC159008E15DD40783D75E8F058EBC8964298EE7FBA52222CF68798CF711` |
| `_main\as-now2.jsonl` | 18906 | `A1DF01EB97C3BCC97BDCE388FBF02E984D11BCEDF1D4CE678C39BEF12D9946BD` |
| `_main\as-tabs.json` | 12492 | `65C75CCA5DE02ECBC3F5FC09E54823FF8F51551AD038C2769A5E9DB4DE5D1F78` |
| `_main\as-tabs-deep.json` | 37295 | `2BAA7AA3A5C55B6204DEE0E6161A5C26AAA634B1F12F4CDDA49883EF7BA88C59` |
| `_main\as-tabs-deep2.json` | 43977 | `058631F413EC8A90C2352899095BE037D82D992807DFF2713A77C24F4774B07B` |
| `_main\as-audible.jsonl` | 213639 | `6C95BEBF3A15265DE78534E499F4E683DF27A50034724EB8CAF42CA9EEABDE08` |
| `_main\as-selftest.txt` | 854 | `02C252415CEC5AA1F1934C0AB68C7A8BE7CD6D215DC0150E9F2CCC9A14E9C1CB` |
| `_main\as-neg-iid.jsonl` | 15489 | `8E20B356840090F860308518AD4218FF11EFB738A119C044CF5F0ACF4E4808C2` |
| `_main\as-neg-iid.txt` | 481 | `F6FD1FEDF64E25A2C87EF1677D8DF1DCB41C95529B31B65F897A4FD3AFD3703D` |
| `_main\as-neg-floor.jsonl` | 18936 | `A2F45DFD3B32AFF9768B5A42FFC71FCDA4249A60515A9B90BA15BC3558F07F8F` |
| `_main\as-neg-floor.txt` | 2208 | `1AF475B54298D4746A80B9F834A88B19C09EB4366BDD68F54F50B658C35A24FE` |

Análises:
| ficheiro | bytes | sha256 |
|---|---|---|
| `_main\as-analysis.txt` | 16238 | `C1BBFC1F34DDDF53CAEE56011AFEB71F2DD7A7ADCCF5C9217094A59485AD9EAD` |
| `_main\as-indicator.txt` | 5847 | `CB6EF9356AC40366BEE163697E7448F9A5E037562718B19BCC369EEA6588918D` |
| `_main\as-displayname-census.txt` | 899 | `959DAACBE4F997546A3294E5424FFF1F4C3BE28F7A6C806D4E55AD0921B37114` |
| `_main\as-audible-analysis.txt` | 13807 | `C04DB5E2297B1700ABDB73DACDD97F329B0A9A2F38B9FFD8A61AA7F13AE2B4A1` |

Fontes upstream descarregadas (para as citações com linha):
| ficheiro | bytes | sha256 |
|---|---|---|
| `_main\src\sharex-FFmpegCaptureDevice.cs` | 2104 | `054D459982A1BAC0DD7B7A1A8AC2E5F2B140A2C565CAD83B479123AE3D6AD5A2` |
| `_main\src\sharex-FFmpegOptions.cs` | 6635 | `64ABE7635623B93FDEA1591D62E90EE009CCCE480AD08803929998E2F47BB316` |
| `_main\src\sharex-ScreenRecordingOptions.cs` | 17799 | `9A28638F22A6F5FD43B299232EF90465A20FCE75E01588A35071623257DB7F25` |
| `_main\src\sharex-ScreenRecorder.cs` | 9681 | `34A6BD57C7470A221B061896450B5D1E174E49E154071BD50AA10AE329695B3B` |
| `_main\src\sharex-Directory.Packages.props` | 1530 | `BBCFC1394AF4247EC009ACFCF8FEB69E2204FC46CB3205792C74FEA88AF17484` |
| `_main\src\chromium-audio_session_event_listener_win.cc` | 1703 | `059E646DCE40D57667949F557550BEA9B419409896E97D8BAD114D801C3E326C` |

> **Nota de honestidade:** os sha256 desta tabela foram calculados com `Get-FileHash` **depois** de escrever o
> recibo. A primeira versão deste bloco trazia placeholders inventados; foram substituídos pelos valores reais
> acima. Os ficheiros são cópias de `raw.githubusercontent.com` (ShareX branch `develop`, Chromium `main`),
> descarregadas em 2026-10-07 — as citações com número de linha referem-se a **estas** cópias.

### Custo próprio da lane
- 1 thread em todos os probes; nunca mais de 1 probe de cada vez.
- Pico de CPU do meter: **2.11 %** de 1 núcleo. Pico do UIA: 0.281 s CPU por dump.
- Nenhum processo do dono foi tocado; **nada foi morto**. O worker (29008) e o shell (28428) continuaram a correr e a transcrever durante todas as medições.
- Janelas visíveis: **0** `ALERTA-JANELA` em 139 logs recentes de `_main`; lançamentos por `pythonw.exe` ou `-WindowStyle Hidden`.

---

## 9. O que ficou por medir

1. **Título da aba que soa** — não obtido (§3). Um caminho que **não** testei e que poderia valer: ler
   `chrome://media-internals` / o protocolo DevTools (`--remote-debugging-port`, **não** está ligado nesta
   máquina) — daria a aba audível, mas exige relançar o Chrome do dono, o que **não** é aceitável nesta lane.
2. **Atribuição por janela para apps de janela única** (jogos, Discord, media players): subir do PID da sessão
   para a janela de topo e ler o título. Não medido; para o Chrome **não serve** (o processo de áudio não tem janela).
3. **Se o indicador UIA do Chrome muda com o *mute*** — não testei (mudar o mute seria mexer na app do dono).
4. **Sessões expiradas** (`state="Expired"`): apareceram 0 nesta máquina; o tratamento está no código mas não foi exercitado.
5. **A extensão de navegador** proposta em §5.1: contrato desenhado, **nada implementado nem medido** — não escrevi
   código de extensão nesta lane (e não é `_main\`).

### 9.1 LACUNA DECLARADA (a) — duas fontes reais ao mesmo tempo: **NUNCA EXERCITADO**

O caso "duas apps a soar em simultâneo" **nunca aconteceu** durante as minhas medições: nunca observei mais de
**1** sessão com `peak > 0.001` em nenhuma amostra. Consequência, dita sem maquilhagem:

- a lógica de desempate (`peak_max_win` → `peak`), o `margin_ratio` e o `ambiguous` (limiar 1.5) estão
  **testados apenas em sintético**, no `--selftest` (GREEN 10/10), com candidatos que **eu inventei**;
- **não** há uma única medição real com duas fontes acima do chão. O limiar 1.5 é uma **escolha de desenho, não
  um resultado**: não sei qual é o `margin_ratio` típico entre um jogo e o Discord na voz, nem se 1.5 é apertado
  ou folgado demais;
- o caminho `source_including_system_sounds` (um *ding* do Windows por cima de música) também nunca foi visto ao vivo.

Falsificador barato para quem pegar nisto: pôr um vídeo a tocar **e** falar no Discord ao mesmo tempo, e correr
`py -3 _main\audio-source-probe.py --secs 30 --hz 4 --all-endpoints` — espera-se `n_sources_above_floor >= 2`.

### 9.2 LACUNA DECLARADA (b) — os 150 s + 130 s a `0.000000`: **NÃO RESOLVIDO**

Fica **não resolvido**, e o proxy que usei está **declaradamente contaminado**:

- medi **573 amostras em 150 s** e **497 em 130 s** com **todas** as leituras a zero;
- **não** posso afirmar que era silêncio, porque o meu único instrumento independente para "está a tocar" era o
  **crescimento do log da app** — e esse log é escrito também por **hot reloads do painel**, que **reproduzem o
  histórico** (`155 HOT_RELOAD_EVENT` + `38 RECEIVER_READY` + `830 BRIDGE_CAPTION_SENT` em 2000 linhas). Um log
  que cresce **não** prova áudio novo;
- o log da app **não tem timestamp por linha**, logo não consigo reconstruir *quando* cresceu.

**O que fica provado, e é o que conta:** o **controlo positivo** — quando há som, o meter mexe (endpoint
`0.126788` / `chrome.exe` `0.149162`, §2.2). A ausência nos outros intervalos **não** está provada; a **presença**
está. Não maquilho isto para "silêncio".
