# 03 — CAPTURE: de onde vem o áudio

Este ficheiro responde só a isto: **que samples entram no Sotto, por que porta, e o que acontece
quando não entram**. Todo o `[CODE]` foi lido nesta campanha (2026-11-11) e traz `ficheiro:linha`; o
`[MEASURED]` vindo de um recibo é **histórico** (diz a data e o ficheiro, não foi re-medido aqui —
ver `## Lacunas`).

## 1. A decisão de topo: três braços de captura

`main()` escolhe o braço **antes** de tocar num dispositivo — `[CODE]`
`sotto_worker.py:7244,7279,7289,7291`:

| condição | braço | consequência | evidência |
|---|---|---|---|
| `--selftest` ou `--audio`/`SOTTO_AUDIO_FILE` | `selftest()` | nenhum dispositivo aberto | `[CODE]` `sotto_worker.py:7244` |
| `SOTTO_FILE_TAP=<path>` | `FileTap` | `device_candidates()` **nunca** corre | `[CODE]` `sotto_worker.py:7279,7289` |
| resto | escada de dispositivos | `device_candidates(audio_cfg, wanted, target_pid=...)` | `[CODE]` `sotto_worker.py:7291` |

O braço é publicado antes de abrir o tap, com `device`, `max_input_channels`, `candidates`,
`wanted`, `tap_window_s` e `tap_peak_floor` — `[CODE]` `sotto_worker.py:7322`; lista vazia sai com
`state=error stage=device detail="no input device available"` — `[CODE]` `sotto_worker.py:7318`.

### 1.1 `SOTTO_CAPTURE_MODE`: escrito pela shell, lido por ninguém

A shell exporta-a em todos os arranques a partir de `self.capture_mode`, cujo valor por omissão é a
string `'callback'` — `[CODE]` `sotto_webview.py:23419,1350`; o comentário ao lado diz porquê: a API
de leitura bloqueante do PortAudio não funciona nesta máquina — `[CODE]`
`sotto_webview.py:1347-1350`. `[MEASURED]` 2026-11-11,
`grep -c SOTTO_CAPTURE_MODE worker/sotto_worker.py worker/redux_live.py worker/wasapi_loopback.py` →
`1`, `0`, `0`; o único acerto é o comentário de `sotto_worker.py:8182`. O `--capture` da shell existe
no parser (`sotto_webview.py:25533`) mas **não** viaja em ARGV —
`worker_argv_tail` só emite `--speakers` e `--threads` — `[CODE]` `sotto_webview.py:23021-23044`; e
o worker não declara esse flag (tem `--device`, `--target-pid`, `--target-name`, `--meter-hz` e mais
nenhum nome da família) — `[CODE]` `sotto_worker.py:6574-6620`.

`[INFERENCE]` O "modo de captura" é hoje um rótulo de log (`SOTTO_CAPTURE_MODE=callback` em
`BRIDGE_SPAWNED`, `sotto_webview.py:23582`): a forma decide-a quem entrega blocos, o tap por
*callback*; `SOTTO_CAPTURE_MODE=blocking` não muda nada **e não dá erro** — a parte perigosa.

### 1.2 O tap por processo (`ProcessLoopbackTap`)

O contrato de leitura é copiado campo a campo do `WasapiLoopbackTap`, para a escada, o `tap_ledger`,
o `close_tap()` e o veredicto de mudez não precisarem de um ramo novo — `[CODE]`
`sotto_worker.py:3972-3995`.

| facto | valor | evidência |
|---|---|---|
| dispositivo virtual | `VAD\Process_Loopback` | `[CODE]` `sotto_worker.py:3416` |
| formato DECLARADO e `GetMixFormat` | 48 000 Hz, 2 canais, 32 bits; `GetMixFormat` dá `E_NOTIMPL` e cada braço guarda o HRESULT | `[CODE]` `sotto_worker.py:3426-3428,3823-3880` |
| timeout da activação | 10,0 s | `[CODE]` `sotto_worker.py:3422` |
| pid `absent` / `denied` | `absent` recusado antes de abrir; `denied` (protegido) **não** | `[CODE]` `sotto_worker.py:4130-4140,3924-3945` |

**A LEI DO FIO ÚNICO.** COM + open + pump + teardown correm no mesmo fio, `plp-owner` — `[CODE]`
`sotto_worker.py:4080,4093,4109` — porque aberto num fio e lido de outro o pump entregou 71 blocos em
3 s e **parou** quando o fio de abertura morreu — `[CODE]` `sotto_worker.py:4070-4079`. O open é
**síncrono**: `_start` espera `PLP_ACTIVATE_TIMEOUT_S + 5.0` e relança o erro, senão um open que falha
em silêncio viraria "dispositivo mudo" — `[CODE]` `sotto_worker.py:4083-4090`. O pump declara o
formato que o cliente **aceitou** (lido da struct vencedora, não do rótulo) — `[CODE]`
`sotto_worker.py:3791-3820` — e sonda a cada `block_ms/20` — `[CODE]` `sotto_worker.py:4200-4235`.
Pacotes `AUDCLNT_BUFFERFLAGS_SILENT` acumulam-se como **zeros** (a cadência sobrevive e o silêncio é
reportado como silêncio); posições descontínuas contam-se em `position_gap_packets` e
`discontinuity_packets` — `[CODE]` `sotto_worker.py:4250-4285`. `stop()` faz `join(timeout=2.0)` e
depois toma o lock do callback, com `_stop` re-testado **dentro** do lock — daí "nenhum `on_block`
depois de `stop()`" ser uma propriedade do objecto — `[CODE]` `sotto_worker.py:4169-4184`.

### 1.3 O caminho loopback de endpoint

`WasapiLoopbackTap` é o tap da rung (a) e **carrega o `endpoint_id`**, porque abrir "o default" quando
a escada escolheu outro substituiria em silêncio exactamente o endpoint cuja mudez é o defeito —
`[CODE]` `wasapi_loopback.py:1049,1227-1245`. Não negocia formato: inicializa com o *mix format*,
pedindo `HNS_100MS` e caindo para `0` — `[CODE]` `wasapi_loopback.py:1288-1305`; o comentário mede o
preço — 1056 frames (22 ms) com duração zero contra 4800 frames (100 ms), e 200 wakeups/s custavam
6,0 % de um núcleo — `[CODE]` `wasapi_loopback.py:1272-1287`. `AUDCLNT_E_DEVICE_IN_USE` =
`0x8889000A` — `[CODE]` `sotto_worker.py:8340-8342`.

### 1.4 O tap de ficheiro (`SOTTO_FILE_TAP`)

`FileTap` não abre dispositivo: lê o ficheiro (float32 mono a `TARGET_SR`), faz *loop*, e chama
`on_block` uma vez por `block_ms` num relógio de parede — `[CODE]` `sotto_worker.py:4498-4535`.
Candidato com `rung: "file"` e nome `file:<basename>` — `[CODE]` `sotto_worker.py:4562-4580`.
**Desligado** por omissão — `[CODE]` `sotto_worker.py:4510-4515`.

## 2. A escada de dispositivos

`device_candidates()` devolve uma lista ordenada e deduplicada — `[CODE]` `sotto_worker.py:2613`.

| rung | o que oferece | porquê | evidência |
|---|---|---|---|
| `c` | o nome explícito (`--device`/`SOTTO_AUDIO_DEVICE`), por substring | decisão do dono; nunca substituída em silêncio | `[CODE]` `sotto_worker.py:2692` |
| `p` | o pid alvo (tap por processo) | um loopback de endpoint daria a mistura inteira | `[CODE]` `sotto_worker.py:2706` |
| `a` | loopback de **todos** os endpoints de render activos, quem toca primeiro | sem driver, sem cabo virtual | `[CODE]` `sotto_worker.py:2709` |
| `b` | nomes que *parecem* saída do PC + nomes configurados | heurística, nunca lista literal | `[CODE]` `sotto_worker.py:2764,180-208` |
| `tail` | entrada restante que não seja microfone | uma rotação tem sempre para onde ir | `[CODE]` `sotto_worker.py:2823` |

Duas exclusões explícitas: os **pseudo-dispositivos** Sound Mapper / Primary Sound Capture Driver,
que abrem e entregam silêncio digital (medido `peak=9.2e-05`, `nonzero_blocks=0`) — `[CODE]`
`sotto_worker.py:220-241` — e qualquer endpoint que **denuncie** Bluetooth, porque abrir o microfone
de um auscultador sem fios força o Windows de A2DP para HFP e cala a música dele — `[CODE]`
`sotto_worker.py:250-273,2805-2822`. A deduplicação é por endpoint físico (nome até ao primeiro `(`)
e, num candidato WASAPI, pelo `endpoint_id` — `[CODE]` `sotto_worker.py:2652-2680`.

### 2.1 A primeira escolha: `CAPTURE_FIRST_PICK` + `probe_ms`

Antes do primeiro tap, `main()` pergunta ao medidor vivo **quem renderiza agora** e move esse
candidato para o slot 0 — `[CODE]` `sotto_worker.py:7304-7311`; a rung `c` fica de fora (`if not
wanted`), para um dispositivo nomeado não ser re-ordenado pelas costas do dono — `[CODE]`
`sotto_worker.py:7305-7307`. A linha publica escolha, escolha estática, movimento, `probe_ms`,
número de candidatos e piso — `[CODE]` `sotto_worker.py:7311-7316`; a função é
`signal_ranked_next()`, que devolve a ordem antiga quando o medidor dá `{}`, porque "sem leitura"
nunca é "sem sinal" — `[CODE]` `sotto_worker.py:2538-2560`.

`[MEASURED]` histórico, 2026-11-04, `_main/receipt-20261104-first-capture-fast.md` §1: **735 ms**
(primeira leitura) e **750 ms** (cache quente) para **6 endpoints**, contra os **3,8 s** da variante
antiga (`loopback_device_specs()`, um `IAudioClient` por endpoint); o comando está transcrito lá.

### 2.2 O journal de endpoints

`%LOCALAPPDATA%\Sotto\endpoint-signal.json`, desligável por `SOTTO_ENDPOINT_JOURNAL` com
`off`/`0`/`none` — `[CODE]` `wasapi_loopback.py:540,596-614`; escrito no `close()` do tap com os
números do próprio tap, e nunca levanta — `[CODE]` `wasapi_loopback.py:1501,1530-1550`.

| campo | regra | evidência |
|---|---|---|
| `verdict` | `signal` se `peak > 0.002`; `flat` se ouviu o mínimo e tudo foi silêncio; `no-data` se a janela foi curta | `[CODE]` `wasapi_loopback.py:670-698,545` |
| validade / tecto | 1 800 s; 64 linhas, as mais recentes | `[CODE]` `wasapi_loopback.py:555,560` |
| `no-data` não apaga | um tap que não ouviu não apaga um que ouviu | `[CODE]` `wasapi_loopback.py:712-720` |

A ordem final tem quatro degraus — `[CODE]` `wasapi_loopback.py:759-810`: (1) o medidor VIVO diz que
renderiza agora; (2) um tap mediu `signal` aqui recentemente; (3) desconhecido — e aqui o *tie-break*
histórico (default primeiro) fica intacto; (4) um tap **provou** `flat`, o mais velho primeiro.
`[INFERENCE]` O degrau 3 garante que uma máquina sem journal ordena como antes; o degrau 1 garante
que nenhum journal esconde um endpoint que está a tocar neste instante.

### 2.3 `LADDER_TRY`: uma linha por candidato, com milissegundos

Amontada por função **pura**, `ladder_try_line()` — `[CODE]` `sotto_worker.py:2588-2610`:

```
LADDER_TRY attempt=%d/%d device=%r api=%r ms=%d retries=%d result=%s
```

`result ∈ opened | refused | stopped` — `[CODE]` `sotto_worker.py:2605-2610`; o carimbo `_t_try` é
tirado **antes** do laço de retry, para não somar três esperas de 1,5 s — `[CODE]`
`sotto_worker.py:8457-8460,8551-8556`. `[MEASURED]` histórico, 2026-11-10,
`_main/receipt-20261110-boot-attribution.md` §2:
`LADDER_TRY attempt=2/9 device='VoiceMeeter Input' api='wasapi' ms=1743 retries=1 result=opened`;
`[MEASURED]` histórico, 2026-11-11, `_main/receipt-20261111-live-start-latency.md` §8 (pid 49180):
`attempt=1/11 ... ms=16 result=opened` às 17:34:42.832 e `attempt=2/11 ... ms=46 result=opened` às
17:35:27.496 — abrir é barato; os 43,6 s entre os dois foram a **guarda** à espera.

### 2.4 Recusa, espera e desistência

| classe | o que acontece | evidência |
|---|---|---|
| `DEVICE_IN_USE` (`0x8889000A`) | **não** roda: espera 1,5 s e repete, até 3 tentativas (o ocupante é normalmente o worker anterior); qualquer outro erro roda já | `[CODE]` `sotto_worker.py:8530-8540` |
| abertura que **bloqueia** | abandonada ao fim de 4,0 s; o fio abandonado fecha o próprio tap quando voltar | `[CODE]` `sotto_worker.py:4370-4425,603` |
| recusa / escada gasta | `status device-open-refused` (neutro: a escada a funcionar não é falha); ao esgotar, `audio-endpoint-unavailable reason=ladder-exhausted`, `denials` fora do corpo | `[CODE]` `sotto_worker.py:8515-8528,8588-8608` |
| rotação | `status device-rotated`, espera `min(8 s, 2^(n-1))` | `[CODE]` `sotto_worker.py:8612-8622` |

O tecto de rotações sem sinal é **8** e é condicional: só dispara numa corrida sem legenda e sem
pico acima do piso — `[CODE]` `sotto_worker.py:575,9012`. A razão está medida: 2 188 rotações
`reason=flat` em dez minutos, cada uma um `Initialize` num endpoint novo — `[CODE]`
`sotto_worker.py:560-575`.

## 3. O alvo por NOME

`resolve_audio_target()` resolve o alvo **antes** de carregar 1,8 GB de pesos e recusa com `exit 2`
em vez de cair para a mistura — `[CODE]` `sotto_worker.py:6503-6520`. Duas fontes, nesta ordem —
`[CODE]` `sotto_worker.py:6527-6560`:

| prioridade | fonte | recusa |
|---|---|---|
| 1 | `--target-pid`, senão `SOTTO_TARGET_PID` | não inteiro / não positivo / pid `absent` → `stage=target-pid` |
| 2 | `--target-name`, senão `SOTTO_TARGET_NAME`, senão `audio.target_name` | nenhum processo com o nome → `stage=target-name` |

O nome resolve para a **raiz da árvore** em `worker/process_target.py`: `normalise()` baixa a
minúsculas e exige `.exe` (`:54`), `match()` compara igualdade de basename e nunca substring (`:62`),
e `pick_root()` escolhe o processo cujo pai não tem o mesmo nome, desempatando pelo **maior pid** (o
mais recente) — `[CODE]` `process_target.py:83-99`.

O rebind vive num sítio só: `live_target(where)` — `[CODE]` `sotto_worker.py:7020-7046`. Pid vivo é
o pid; morto, resolve-se de novo; sem nenhum processo com o nome devolve o anterior **e diz isso**
(`TARGET_NAME_MISSING`), porque trocar em silêncio para a mistura transcreveria a máquina inteira —
`[CODE]` `sotto_worker.py:7043-7046`. É chamado no censo do parque (`'park'`,
`sotto_worker.py:8365-8375`) e na re-enumeração da escada (`'ladder'`). Quando a escada passa do tap
do processo para um endpoint, a perda é gritada uma vez: `PER-APP SEPARATION LOST` e
`device-rotated reason=per-app-tap-lost` — `[CODE]` `sotto_worker.py:8441-8446`.

Na APP o caminho é outro: `--app-target PID|IMAGE` é resolvido pela **shell** para o pid da raiz
(`sotto_webview.py:17792`) e viaja como `SOTTO_TARGET_PID` — `[CODE]`
`sotto_webview.py:23440,17788-17812`; `[MEASURED]` 2026-11-11, `grep -n "target_name\|target-name"
app/webview/sotto_webview.py` → **zero** linhas.

`[INFERENCE]` Com o nome resolvido pela shell o pid fica **pinado** na env do filho (reinício com o
mesmo `SOTTO_TARGET_PID`; um pid morto é recusado em `stage=target-pid`) e o rebind só existe quando
o **worker** é dono do nome. O `worker/config.json` de fábrica **não** tem `audio.target_name` —
`[MEASURED]` 2026-11-11, chaves de `audio` via `json.load`: `device`, `preferred_devices`, `_comment`.

## 4. Silêncio: cinco perguntas diferentes

| pergunta | tag | limiar | evidência |
|---|---|---|---|
| o candidato entregou **algum** bloco? | `TAP_DEAD_FAST` → `TAP_DEAD_ENDPOINT` / `TAP_QUIET_DESKTOP` | 2,0 s, e o medidor diz "morto" ou "desktop calado" | `[CODE]` `sotto_worker.py:409,412,436,8850-8880` |
| a janela fechou sem legenda? | `device-rotated reason=flat` | 6,0 s | `[CODE]` `sotto_worker.py:370,2425` |
| o desktop está calado? | `tap-silent-desktop` / `tap-own-endpoint-loud` | espera em vez de rodar | `[CODE]` `sotto_worker.py:2320,2526` |
| o cliente morreu? | `TAP_STALLED` | 8,0 s sem blocos; `pump_exited` é a única prova afirmativa | `[CODE]` `sotto_worker.py:510,605,8769` |
| o endpoint não renderiza? | `TAP_IDLE` | 300 s com o pump vivo, re-arma **uma** vez | `[CODE]` `sotto_worker.py:590,8758` |

`silent_desktop_hold()` impede rodar num desktop parado: `live={}` devolve `None` e a escada segue;
todos abaixo do piso devolve a janela **seguinte**, dobrada — `[CODE]`
`sotto_worker.py:2320-2380`. E o endpoint **desta** tap manda: se `own_peak > tap_floor` a tap fica
aberta mesmo que outro endpoint toque, porque blocos a contar num endpoint que renderiza são buffer a
encher, não dispositivo morto — `[CODE]` `sotto_worker.py:2330-2350`. A espera está limitada por
`FLAT_EVIDENCE_S = 4.0` — `[CODE]` `wasapi_loopback.py:588`, aplicado por `_flat_evidence_s()` —
`[CODE]` `sotto_worker.py:2291-2318`; a justificação usa três números: 4 s = 40 blocos > os 20 blocos
de evidência, a leitura do medidor custa 0,755 s para 6 endpoints (2026-11-11), e 4 s >
`TAP_FIRST_BLOCK_MAX_S` (2,0 s) para o caminho do candidato morto decidir primeiro — `[CODE]`
`wasapi_loopback.py:566-587`. `[INFERENCE]` O comentário de `silent_desktop_hold` descreve a série
6→12→24→48→60 e o arranque que custou **43,6 s** (recibo 2026-11-11, §8, código **anterior** a este
tecto); com 4,0 s a espera fica em ≤ 4,0 s.

### 4.1 "O áudio voltou e nada acontece"

Máquina pura, duas linhas — `[CODE]` `sotto_worker.py:528-560`:

```
CAPTURE_SIGNAL_BACK gap_s=%d blocks=%d captions=%d
NO_CAPTION_AFTER_AUDIO_BACK grace_s=%d blocks_delta=%d captions=%d
```

A lacuna usa **o mesmo** limiar do `TAP_STALLED` (`gap_s >= TAP_STALL_S`), para não haver um segundo
número para a mesma pergunta — `[CODE]` `sotto_worker.py:531-545`. Se as legendas avançarem dentro da
graça de **25 s**, o estado morre em silêncio — `[CODE]` `sotto_worker.py:552-560`. A tag vem
**primeiro** na linha porque `ENGINE_VISIBLE_TAGS` casa por `startswith` — `[CODE]`
`sotto_worker.py:8710-8720`.

### 4.2 Do lado da SHELL: `WORKER_ALIVE`, `BRIDGE_SILENT`, e a graça

O worker publica `WORKER_ALIVE seq=... phase=... age_ms=...` a cada **8 s** e **cala-se** quando o
`seq` não avança: o batimento é prova de progresso, não um relógio — `[CODE]`
`sotto_worker.py:1388-1425`; `WORKER_ALIVE_ARMED` distingue "não chegou batimento" de "nunca foi
armado" — `[CODE]` `sotto_worker.py:1425`. A shell só conta `WORKER_STATS` quando `blocks` avança e
aceita `WORKER_ALIVE` como progresso — `[CODE]` `sotto_webview.py:1554-1560,24157-24190`.

| janela | valor | evidência |
|---|---|---|
| silêncio com o modelo carregado | 30 000 ms | `[CODE]` `sotto_webview.py:1457` |
| silêncio durante a carga | 180 000 ms, tecto duro 900 000 ms | `[CODE]` `sotto_webview.py:1465,1662` |
| graça antes de matar | 10 % da janela, piso 50 ms | `[CODE]` `sotto_webview.py:1483-1493` |

A sequência está no log: `BRIDGE_SILENT_LOADING` enquanto `model-loaded` não chegou — `[CODE]`
`sotto_webview.py:24334`; `BRIDGE_SILENT_WAIT` no primeiro disparo, a perguntar se há progresso em
voo — `[CODE]` `sotto_webview.py:24381`; `BRIDGE_SILENT_GRACE` se o progresso andou depois do prazo
— `[CODE]` `sotto_webview.py:24370`; e só então `BRIDGE_SILENT` + `_kill_and_restart` — `[CODE]`
`sotto_webview.py:24392-24397`.

Se o worker já declarou que não há nada a transcrever, a shell **não mata**: escreve
`BRIDGE_SILENT_BENIGN` e re-arma o vigia — `[CODE]` `sotto_webview.py:24253-24280`; a evidência
aceite é estreita — `device-rotated reason=flat`, `tap-silent-desktop`, um estado de
`WORKER_NO_AUDIO_STATES`, ou um `done` com veredicto dessa lista — `[CODE]`
`sotto_webview.py:24194-24250`. O preço de uma morte: **250 ms** e **2** trocas grátis com som noutro
endpoint, 15 000–300 000 ms sem som, piso de 20 000 ms numa saída limpa; e ao fim de **3** mortes por
silêncio a shell **para** e pede Alt+C — `[CODE]` `sotto_webview.py:1519-1545,1502,23069`.

## 5. AGC, tecto de pico e costura de chunks

| constante | valor | o que faz | evidência |
|---|---|---|---|
| `AGC_TARGET_DBFS` | `-20.0` | alvo de RMS à entrada do modelo | `[CODE]` `sotto_worker.py:2875` |
| `AGC_MAX_GAIN_DB` / `AGC_MIN_GAIN_DB` | `24.0` / `-6.0` | 16× para cima, 2× para baixo | `[CODE]` `sotto_worker.py:2876-2877` |
| `AGC_FLOOR_DBFS` | `-60.0` | a este nível ou abaixo **segura**, não amplifica | `[CODE]` `sotto_worker.py:2878` |
| `AGC_ATTACK` / `AGC_RELEASE` / `AGC_SUBBLOCK` | `0.50` / `0.10` / `1600` | desce depressa, sobe devagar; 100 ms a 16 kHz é a unidade | `[CODE]` `sotto_worker.py:2879-2881` |
| `AGC_CEILING` | `0.98` | tecto do sinal que o modelo recebe | `[CODE]` `sotto_worker.py:2894` |

A **ordem** é decisão: a decisão de fala corre primeiro, sobre o chunk **pré-ganho**, e o ganho só se
aplica ao que a decisão guardou — `[CODE]` `sotto_worker.py:2896-2910`; com `speech=False`,
`process()` devolve o bloco à unidade e regista o ganho que *teria* aplicado (`would_*`) — `[CODE]`
`sotto_worker.py:2985-3005`. O tecto é aplicado **antes** de multiplicar: `g = min(g, AGC_CEILING /
pk_in)`, e `self.gain_db` **não** se move com isso (o limite de hoje não pode amortecer a libertação
de amanhã) — `[CODE]` `sotto_worker.py:3025-3045`; `limited_blocks` conta quando cedeu, e o
`np.clip(-1, 1)` fica só como rede de segurança. `SOTTO_AGC=0` desliga o estágio — `[CODE]`
`sotto_worker.py:7405`.

Costura: repetição **imediata** de 2 a 6 palavras é o modelo a re-decodificar o rabo do chunk
anterior, e uma palavra sozinha repetida é fala e não se toca — `[CODE]`
`sotto_worker.py:5108-5148`. `dedup_seam_repeat()` normaliza caixa e pontuação nas bordas, colapsa o
segmento mais comprido primeiro e repete até 4 passagens, porque o artefacto cresce (`A`, `A+B`,
`A+B+C`) — `[CODE]` `sotto_worker.py:5149-5198`; `SEAM_REPEAT_MIN_WORDS = 2` e
`SEAM_REPEAT_MAX_WORDS = 6` — `[CODE]` `sotto_worker.py:5114-5115`.

## 6. O que a SHELL vê disto

**`meter` — a onda.** O worker emite `type="meter"` com exactamente `{"peak", "blocks"}`, onde
`peak` é o pico **daquela janela** — `[CODE]` `sotto_worker.py:7546-7600,3149-3180` — a
`METER_HZ = 10.0` — `[CODE]` `sotto_worker.py:3082` — e a janela fecha no **primeiro** de "tempo
suficiente" e "blocos suficientes" — `[CODE]` `sotto_worker.py:3168-3180`. A shell valida os dois
campos e guarda `last_meter` — `[CODE]` `sotto_webview.py:23797-23845`; o **dado** não é limitado, o
**log** é (`BRIDGE_METER` no máximo a cada 30 s) — `[CODE]` `sotto_webview.py:3200,23828-23836`.
`stats()` prefere um `meter` com menos de `METER_FRESH_S = 2.0` s e nesse caso **não mistura** com a
linha `WORKER_STATS` — `[CODE]` `sotto_webview.py:3195,20230-20290`; o payload leva `tag='meter'`,
`peak`, `blocks` e `paused`, e o painel consome-o em `pushLevel(fields.peak, fields.blocks)` —
`[CODE]` `app/panel/panel.js:4464,4349` — o comentário do worker cita `panel.js:1709`, mas em `HEAD` a
chamada está em `:4464` — `[MEASURED]` 2026-11-11, `grep -n pushLevel app/panel/panel.js`: `1000,4339,4349,4409,4464`.

**`status` — a frase, o corpo, a cor.** `worker_status_kind()` devolve `error | no-audio | busy`, e o
teste de no-audio vem **primeiro** porque esses estados são subconjunto dos de erro — `[CODE]`
`sotto_webview.py:2050-2090`. As listas são fechadas: `WORKER_ERROR_STATES` (`:1371`),
`WORKER_NO_AUDIO_STATES` (`:1411`), `WORKER_WARMUP_STATES` (`:1383`) e `WORKER_CAPTURING_STATES =
{capture-started}` (`:1390`) — `[CODE]` `sotto_webview.py:1371-1416`. O **corpo** enviado ao painel é
uma lista fixa, por esta ordem — `[CODE]` `sotto_webview.py:1729-1731`:

```
stage, detail, verdict, device, api, peak, peak_floor, blocks, window_s,
captions, tokens, chunks, rotations, reason, rate
```

`detail` passa por `human_audio_error()` antes de ser pintado, para um HRESULT conhecido virar frase
com acção em vez de hexadecimal — `[CODE]` `sotto_webview.py:2235-2258`. O rodapé tem regras
próprias: `silent-device` vira `Silent audio device - <device> [<api>] peaked <peak> < floor
<floor>`; `device-exhausted` vira `Audio tap carried no signal - every candidate device was flat`; e
`audio-endpoint-unavailable` vira `No audio endpoint was free - Sotto keeps looking` — `[CODE]`
`sotto_webview.py:2160-2210`.

**O que NÃO chega ao painel.** `candidates`, `denials`, `from`/`to`, `reopened`, `stalled_s`,
`attempt`/`of` e `why` não estão em `STATUS_BODY_FIELDS`, logo não entram no corpo — `[CODE]`
`sotto_webview.py:1729-1731`; `denials` é mantido fora de propósito porque contém o HRESULT cru que
o dono mandou tirar da tela — `[CODE]` `sotto_worker.py:8598-8606`. O `peak`/`peak_floor`/`blocks` de
um `device-rotated` também não são corpo: a shell usa-os como evidência de no-audio e escreve-os no
**log** (`BRIDGE_STATUS_NOAUDIO`) — `[CODE]` `sotto_webview.py:24220-24235,24070-24080`.

## 7. O gate de fala/música (`SOTTO_GATE`)

**`HEAD`: OFF nos dois braços.** Sem a variável, `gate_enabled = False` e o estado publicado diz
`source=default-off`; um valor explícito (`SOTTO_GATE=1`, e `0`/`off`/`false`/`no` no sentido inverso)
vence nos dois e muda para `source=env` - `[CODE]` `sotto_worker.py:7240-7260`.

O juiz é `SpeechMusicGate.is_speech(chunk)`, numpy puro, por chunk de 560 ms, com três constantes
(`sotto_worker.py:3216-3218`): `GATE_DB_RANGE_MIN = 18.0` dB de vão entre o máximo e o mínimo do RMS
das sub-tramas de 320 amostras, `GATE_RMS_FLOOR = 0.004` abaixo do qual é silêncio e não fala, e
`GATE_HOLD_CHUNKS = 3` de histerese depois de fala. Um chunk com `nsub < 2` é **mantido**: reter
áudio por falta de evidência é a substituição silenciosa que a escada de dispositivos existe para
remover (`sotto_worker.py:3265-3272`). O `18.0` está no vão medido entre o pior não-fala (15.6) e o
pior p10 de fala (20.2) sobre seis fixtures (`sotto_worker.py:3200-3207`).

A ordem é o motivo de o gate existir: a decisão corre no chunk **pré-ganho** e o `AutoGain` recebe-a
em `process(block, speech=...)`, onde `speech=False` segura o ganho e regista o `would_*` do que teria
aplicado (`sotto_worker.py:2896-2910,8088`). Chunk barrado não chega ao encoder e conta em
`music_gated_chunks` (`sotto_worker.py:2064-2075`).

**Por que está OFF (medido 2026-11-15).** Ligado, recusou fala de broadcast: em 20 s de
`rS4VMlwf2qM` o traço por chunk deu `speech=False` em todos a partir de 8,4 s, sobre áudio cujo RMS
sobe de 0,24 para 0,32-0,50 - o gate não vê silêncio, vê um vão dinâmico estreito. A/B no mesmo
áudio, um processo por braço: cobertura 0,80 → 0,25, WER 0,458 → 0,780. **O oráculo não pegou**: as
quatro fixtures de fala são gravações de estúdio limpas (`kept_frac=1.0`) e o único negativo é um
drone de amplitude constante. Recibo em `_main/receipt-20261115-speech-gate-broadcast.md`;
`SOTTO_GATE=1` reproduz o defeito e `=0` é byte-idêntico ao default (`sotto_worker.py:3237-3249`).

## 8. 2026-11-25 — micro em todos os rungs, captura partilhada, denoise ligado

`LoopbackTap()` é a porta única dos rungs que abrem dispositivo, e todos passam pelo mesmo `mic_tap.open_stream(make_primary, on_block)`: P/`ProcessLoopbackTap` em `[CODE] worker/sotto_worker.py:4950-4968`, A/`WasapiLoopbackTap` em `[CODE] worker/sotto_worker.py:4972-4996`, B/C/`_PortAudioTap` em `[CODE] worker/sotto_worker.py:4997-5004`. Cada rung imprime `MIC_CAPTURE`; o rung `SOTTO_FILE_TAP` não abre dispositivo e fica fora. O micro é o default de CAPTURA do Windows, com filtro de não-microfones, ganho constante, `MIC_BACKLOG_S = 10.0` e queda contada `[CODE] worker/mic_tap.py:35,40,46-52`. Sem micro, o loopback volta byte-idêntico.

O worker não abre o seu tap duas vezes: publica o bloco misturado no limite do ASR `[CODE] worker/sotto_worker.py:8609-8610` e o sidecar liga-se a esse publicador antes de enumerar endpoints `[CODE] worker/speaker_sidecar.py:1811-1844`. Um cliente só, fila `QUEUE_BLOCKS` com `CAPTURE_SHARE_DROP dropped=N`, `SOTTO_CAPTURE_SHARE=0` para desligar, fallback nomeado. `[MEASURED]` 2026-11-25: `python _main/capture-share-oracle.py` → `CAPTURE SHARE VERDICT: PASS (8/8 arms)`, braço `f` com `worker_taps=1 worker_mics=1 sidecar_taps=0`, braço `g` (um estranho calado não despe o leitor) e `--neg-arm` → `NEG ARM VERDICT: PASS (8/8 mutants caught, 0 decorative)`.

O denoise deixou de ser inerte: `use_denoise` (TOP-LEVEL, `false` por omissão em `[CODE] worker/config.json:29`) aplica-se num único ponto em `StreamAsr.run_chunk`, depois do gate fala/música e antes da janela mel/VAD `[CODE] worker/sotto_worker.py:2574-2585`. `[MEASURED]` 2026-11-25: `python _main/config-truth-oracle.py` → `VERDICT: PASS`, com `false` byte-idêntico ao módulo desligado e `true` a alterar o PCM (`max|delta|=0.079018` em 8 960 amostras).

---

## Lacunas

- `[UNKNOWN]` **Nenhum número aqui foi medido no código de `HEAD`**: os `[MEASURED]` vêm de recibos
  datados. Fechar exige `live-code-freshness-oracle.py --strict` → `FRESH`, que não lancei.
- `[UNKNOWN]` O custo de `live_endpoint_order()` nesta máquina **hoje**: exige medidor com áudio a
  tocar; o recibo de 2026-11-04 (735/750 ms, 6 endpoints) não foi repetido. Fechar exige correr o
  medidor (leitura pura, `--status-all`) numa sessão com audio a tocar e citar os ms e o nº de endpoints.
- `[UNKNOWN]` Se o tecto de 4,0 s de `FLAT_EVIDENCE_S` já correu numa sessão real: o recibo de
  2026-11-11 mede 43,6 s (código anterior). Fechar exige `device-rotated reason=flat` a ≤ 4,0 s.
- `[UNKNOWN]` O que `_flat_evidence_s()` faz quando o import de `wasapi_loopback` falha (devolve
  `inf`, a política antiga inteira) — lido no código, não exercitado. Fechar exige uma corrida com
  `wasapi_loopback` removível do `sys.path` (ou um `ImportError` injectado na mesma sonda), a exigir
  `flat_evidence` = `inf` e a política de dedobragem por relógio intacta.
- `[UNKNOWN]` Quantos `meter` chegam ao painel por segundo em produção (10 Hz nominais): exige contar
  eventos num log vivo, e o log só tem uma linha por 30 s. Fechar exige um contador do emissor no
  log (uma linha por minuto com o total acumulado), não uma amostra.
- `[UNKNOWN]` Se `SOTTO_CAPTURE_MODE` é lido por consumidor **fora** deste repositório; dentro da
  árvore não tem leitor e fora dela não medi. Fechar exige um censo dos lançadores desta máquina
  (autostart, `.cmd`, tarefa agendada) que leia o ambiente de cada processo e nomeie quem o define.
- `[UNKNOWN]` O comportamento real de um endpoint Bluetooth recusado pela rung `tail`: o código
  exclui-o por nome/driver (`sotto_worker.py:260-273,2805-2822`), mas não abri hardware. Fechar exige
  um par de auscultadores BT pareado nesta máquina e a linha `LADDER_TRY result=refused` com o driver.
- `[UNKNOWN]` Se o `ProcessLoopbackTap` foi exercido com alvo **elevado** (`denied`): o código
  permite-o (`sotto_worker.py:3924-3945`) e a activação a partir de um worker `BELOW_NORMAL` contra
  um processo protegido não foi medida. Fechar exige abrir o tap sobre um alvo `high` (o Explorer
  desta máquina serve) e a linha `PLP_OPEN hr=` com o motivo da recusa, sem tocar em áudio do dono.
