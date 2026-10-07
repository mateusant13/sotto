# O painel como TEXTO — um dump que se lê com `read`, sem visão

Ordem do dono, verbatim (2026-10-06):
*"tu deve fazer uma versao do sotto ou painel que tu pode ver sem precisar da
visao"*.

Até hoje a única forma de saber o que o painel mostrava era capturar o ecrã — e
a captura precisa de visão e está limitada no tempo. Agora o painel tem um canal
de **LEITURA** em texto: um ficheiro JSON reescrito a cada 2 s **e sob pedido**,
com o que o painel mostra AGORA. O painel que o dono vê não mudou uma linha.

---

## 1. Onde o dump é escrito

```
H:\sotto\_main\panel-state.json
```

O caminho é derivado de `HERE` (`app/webview/`), portanto vale para qualquer
clone. É o mesmo `_main/` onde a app já escreve o seu próprio log
(`_main/webview-run.log`) e onde vivem as sondas.

O sentinela do **sob pedido** é irmão do dump:

```
H:\sotto\_main\panel-state.json.request
```

Quem escreve é a própria app (`app/webview/sotto_webview.py`), no fim do
carregamento do painel (`_on_loaded` → `start_panel_state()`), através de
`app/webview/panel_state.py`. Confirmação no log da app, verbatim:

```
sotto: PANEL_STATE_WRITER path=H:\sotto\_main\panel-state.json interval_s=2.0 request=H:\sotto\_main\panel-state.json.request
sotto: PANEL_STATE_WRITER_STOP reason=exit writes=26 errors=0
```

(`writes=26 errors=0` numa corrida de ~50 s a 2 s de cadência.)

## 2. O comando exacto que lê

```powershell
py -3 H:\sotto\app\webview\panel_state.py --read            # dump + IDADE
py -3 H:\sotto\app\webview\panel_state.py --read --json      # o JSON cru
py -3 H:\sotto\app\webview\panel_state.py --request          # dump AGORA
```

O ficheiro também se lê directamente com a ferramenta `read` — é JSON.

## 3. De onde vêm os dados (não há segundo caminho)

Cada campo é estado que a shell **já tinha**:

| campo no dump | origem |
|---|---|
| `panel.live.lines[]` (`provisional` / `latest`), `panel.status`, `panel.placeholder` | a caixa **live** do próprio painel, lida pelo `exec_js` que a shell já usa nas sondas — a mesma leitura que uma captura de ecrã faz, em texto. É o único sítio onde uma linha **provisória** (`.caption--provisional`) se distingue de uma **commitada** (`.caption--latest`) |
| `worker.state`, `captions`, `statuses`, `spawns`, `restarts`, `deaths`, `pendingError`, `noAudio` | o `WorkerBridge` da própria shell (`bridge.state` e os seus contadores) |
| `shell.captionLogCount` | o `caption_log` da shell — as linhas que o DOM acusou (`sotto:caption-applied`) |
| `worker.workerStats.*` (`peak`, `nonzero_blocks`, …) | a linha `WORKER_STATS` que o worker já imprime no **stderr** e que o bridge **já lia** para o `stderr_tail` (era descartada após 3 linhas). Guardada intacta |
| `worker.device.*` | o endpoint que o worker nomeia nas suas próprias mensagens `device` / `capture-started` / `device-rotated` |

Nada aqui arranca um processo, abre uma janela, ou toca num browser.

## 4. Actualidade: o dump diz o seu timestamp **e a idade**

O dump leva `writtenAt` (ISO com offset), `writtenAtEpoch`, `ageSeconds` e
`staleAfterSeconds`. **A idade autoritária é `now - writtenAtEpoch`, e é
calculada pelo LEITOR** — nunca congelada dentro do JSON: um produtor que morre
não consegue actualizar um número dentro do ficheiro que deixou de escrever, e
uma idade auto-declarada seria exactamente a mentira que este desenho existe para
remover. `ageSeconds` no JSON está definido como a idade **no momento da
escrita** (0.0).

Por isso a doca (o gancho à falha) é: **um dump de há 10 minutos diz que foi
escrito há 10 minutos** — `writtenAt` fica para trás e a idade recalculada cresce;
`freshness` passa a `STALE` acima de `staleAfterSeconds` (6.0 s = 3× a cadência).

### `sob pedido` — medido

```
$ py -3 app/webview/panel_state.py --request
PANEL_STATE_REQUESTED path=H:\sotto\_main\panel-state.json.request
the app writes the dump on its next tick (<= 2 s) and removes this file

SEQUENCE 44 -> 45 reason= request age_s=0.07
request-sentinel still present: False
```

---

## 5. A prova: áudio a tocar, legendas certas E estado nomeado

As duas leituras abaixo vêm **da app do dono a correr** (`producerPid=40784`,
`shell.log = H:\sotto\_main\webview-run.log`, `visible=false` — a app está
escondida à espera do Alt+C), com o Twitch a tocar. O mesmo texto aparece primeiro
**provisório** e ~45 s depois **commitado** — que é a distinção que só o dump em
texto faz.

### 5.1 O MESMO texto, primeiro PROVISÓRIO

`py -3 app/webview/panel_state.py --read`, verbatim:

```
=== Sotto panel state (text) ===
writtenAt        = 2026-10-06T10:37:31-03:00
writtenAtEpoch   = 1791293851.951
ageSeconds       = 0.192   (now - writtenAtEpoch)
staleAfterSeconds= 6.0
freshness        = FRESH
reason           = periodic sequence=14 producerPid=40784

namedState       = capture-started
panel.status     = 'capture-started' kind='busy'
placeholder      = title='Listening' hidden=True
live.count       = 1 (provisional=1) hint=''
  [PROVISIONAL] 'Top cer Acho en tia mo ·'

captions (worker)  = 2   statuses=8 spawns=1 restarts=0 deaths=0
captionLog (shell) = 0 visible=False
endpoint           = 'WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)' api=None from='capture-started' current=True
worker peak        = 0.317136 nonzero_blocks=93 blocks=93 (WORKER_STATS tag=tick childPid=41196 current=True)
noAudio            = False evidence=None
```

Os campos do próprio JSON nessa leitura (verbatim):

```json
  "sequence": 14,
  "writtenAt": "2026-10-06T10:37:31-03:00",
  "writtenAtEpoch": 1791293851.951,
  "ageSeconds": 0.0,
  "ageSecondsNote": "age at write; the authoritative age is now - writtenAtEpoch and is printed by `panel_state.py --read`",
  "staleAfterSeconds": 6.0,
  "producerPid": 40784
```

### 5.2 O MESMO texto, agora COMMITADO — e o estado nomeado a vermelho

O dump cru, completo, verbatim (`read H:/sotto/_main/panel-state.json`):

```json
{
  "namedState": "exit",
  "panel": {
    "live": {
      "count": 1,
      "hidden": false,
      "hint": "1 line",
      "lines": [
        {
          "latest": true,
          "provisional": false,
          "text": "Top cer Acho en tia mo."
        }
      ],
      "provisionalCount": 0
    },
    "placeholder": {
      "body": "lang_id      : 101 (auto) source=config:auto table=languages.json A restart is scheduled. Captions stay off until the worker reports a caption.",
      "hidden": true,
      "title": "Worker stopped"
    },
    "status": {
      "kind": "error",
      "text": "Worker stopped (exit 1) - worker exit 1"
    },
    "url": "file:///H:/sotto/app/electron/panel.html"
  },
  "shell": {
    "visible": false,
    "hotkey": "Alt+C",
    "rendererReady": true,
    "bridgeInstalled": true,
    "lastStatus": "Worker stopped (exit 1) - worker exit 1",
    "captionLogCount": 1,
    "reloadCount": 0,
    "workerPath": "H:\\sotto\\worker\\sotto_worker.py",
    "log": "H:\\sotto\\_main\\webview-run.log",
    "hotReload": true
  },
  "worker": {
    "state": "model-loading",
    "capturing": false,
    "childPid": 3292,
    "spawns": 3,
    "restarts": 4,
    "deaths": 2,
    "captions": 2,
    "statuses": 14,
    "malformed": 0,
    "lastExit": 1,
    "noAudio": false,
    "noAudioEvidence": null,
    "pendingError": {
      "state": "exit",
      "text": "worker exit 1",
      "body": ""
    },
    "lastError": null,
    "device": {
      "state": "capture-started",
      "device": "WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)",
      "api": null,
      "peak": null,
      "reason": null,
      "candidates": null,
      "childPid": 41196
    },
    "deviceCurrent": false,
    "workerStats": {
      "tag": "tick",
      "fields": {
        "blocks": "193",
        "block_samples": "926400",
        "nonzero_blocks": "193",
        "peak": "0.327062",
        "rms": "0.02217227",
        "gain_db": "+12.9",
        "gain_min_db": "+0.0",
        "gain_max_db": "+15.0",
        "peak_out": "0.561771",
        "gain_would_db": "+17.3",
        "gain_would_max_db": "+24.0",
        "held_blocks": "102",
        "speech_blocks": "102",
        "agc": "on",
        "resampled_samples": "308800",
        "chunks": "34",
        "captions": "2",
        "tokens": "13",
        "frames": "111",
        "blanks": "98",
        "blank_frac": "0.8829",
        "empty_chunks": "12",
        "vad_gated_chunks": "3",
        "music_gated_chunks": "17",
        "gate_kept": "17",
        "gate": "on",
        "queue_drops": "0",
        "reruns": "0",
        "rerun_wall_s": "0.00",
        "audio_s": "19.04",
        "infer_wall_s": "1.84",
        "rss_mb": "2417.7"
      },
      "line": "WORKER_STATS tag=tick blocks=193 block_samples=926400 nonzero_blocks=193 peak=0.327062 rms=0.02217227 gain_db=+12.9 gain_min_db=+0.0 gain_max_db=+15.0 peak_out=0.561771 gain_would_db=+17.3 gain_would_max_db=+24.0 held_blocks=102 speech_blocks=102 agc=on resampled_samples=308800 chunks=34 captions=2 tokens=13 frames=111 blanks=98 blank_frac=0.8829 empty_chunks=12 vad_gated_chunks=3 music_gated_chunks=17 gate_kept=17 gate=on queue_drops=0 reruns=0 rerun_wall_s=0.00 audio_s=19.04 infer_wall_s=1.84 rss_mb=2417.7",
      "childPid": 41196
    },
    "workerStatsCurrent": false,
    "stderrTail": [
      "lang_id      : 101 (auto) source=config:auto table=languages.json"
    ]
  },
  "schema": "sotto.panel-state/1",
  "reason": "periodic",
  "sequence": 36,
  "writtenAt": "2026-10-06T10:38:16-03:00",
  "writtenAtEpoch": 1791293896.525,
  "ageSeconds": 0.0,
  "ageSecondsNote": "age at write; the authoritative age is now - writtenAtEpoch and is printed by `panel_state.py --read`",
  "staleAfterSeconds": 6.0,
  "producerPid": 40784
}
```

E o leitor, segundos depois, com a idade recalculada (verbatim):

```
=== Sotto panel state (text) ===
writtenAt        = 2026-10-06T10:38:18-03:00
writtenAtEpoch   = 1791293898.558
ageSeconds       = 4.454   (now - writtenAtEpoch)
staleAfterSeconds= 6.0
freshness        = FRESH
reason           = periodic sequence=37 producerPid=40784

namedState       = exit
panel.status     = 'Worker stopped (exit 1) - worker exit 1' kind='error'
placeholder      = title='Worker stopped' hidden=True
live.count       = 1 (provisional=0) hint='1 line'
  [committed] 'Top cer Acho en tia mo.'

captions (worker)  = 2   statuses=14 spawns=3 restarts=6 deaths=3
captionLog (shell) = 1 visible=False
endpoint           = 'WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)' api=None from='capture-started' current=False
worker peak        = 0.327062 nonzero_blocks=193 blocks=193 (WORKER_STATS tag=tick childPid=41196 current=False)
noAudio            = False evidence=None
```

### O que isto prova

- **As legendas certas**: `'Top cer Acho en tia mo.'` — exactamente o texto que o
  painel mostra, primeiro `provisional=1` (a mesma leitura em que o
  `captionLogCount` ainda era 0) e, 45 s depois, `provisional=0` com
  `captionLogCount=1`, ou seja a linha **commitada**.
- **O estado nomeado**: `namedState = exit`,
  `panel.status = 'Worker stopped (exit 1) - worker exit 1' kind='error'` — o
  painel a nomear a morte do worker, em TEXTO, com o `kind` que decide a cor.
  Na leitura anterior o mesmo campo dizia `capture-started` / `busy`.
- **O endpoint tapado**: `WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)`.
- **`peak` / `nonzero_blocks` do worker**: `0.327062` / `193`, tirados da linha
  `WORKER_STATS` do próprio worker.
- **O dump diz o timestamp e a idade**: `writtenAt` no ficheiro,
  `ageSeconds` recalculado pelo leitor (`0.192` e `4.454` nas duas leituras),
  `freshness=FRESH` contra `staleAfterSeconds=6.0`.

### Honestidade sobre os números marcados `current=false`

`deviceCurrent` e `workerStatsCurrent` estão **`false`** nas duas leituras porque
a linha e o dispositivo foram publicados pelo worker `childPid=41196` e, no
momento da leitura, o filho já era outro (`3292`). Isto é deliberado: um número
de um processo morto é mostrado **marcado**, nunca apagado nem disfarçado de
actual. (`AGENTS.md` regista o mesmo defeito noutro sítio: uma leitura de um
produtor já substituído não pode passar por leitura fresca.)

---

## 6. O que ficou mudado

| ficheiro | mudança |
|---|---|
| `app/webview/panel_state.py` | **novo** — o produtor periódico + sob pedido, o leitor (`--read`) e o gatilho (`--request`) |
| `app/webview/sotto_webview.py` | constantes do caminho; `PANEL_STATE_PROBE` (leitura do DOM live); `parse_worker_stats`; `WorkerBridge.last_worker_stats` / `last_device_status` + `snapshot()`; `SottoShell.panel_state_snapshot()` / `_named_panel_state()` / `start_panel_state()`; arranque em `_on_loaded`; paragem em `request_exit` |
| `app/webview/README.md` | secção "The panel as TEXT" |

**Não tocado**: `app/electron/panel.html`, `panel.css`, `panel.js` — o painel que
o dono vê é carregado byte-a-byte de lá e não tem uma linha mudada.

## 7. Limites nomeados (não corrigidos)

- **Duas instâncias da app partilham UM caminho de dump.** A shell WebView2 não
  tem trava de instância única (ao contrário da Electron), e durante esta lane
  houve duas a correr: a do dono (`producerPid=40784`) e a minha de medição
  (`33272`). Cada escrita é atómica, por isso uma leitura devolve **a vista
  inteira de UMA** instância — nunca uma mistura —, mas qual delas escreveu por
  último só se sabe pelo `producerPid`. Registado como ticket.
- O dump lê o DOM pelo `exec_js` da shell. Com a janela fechada (que é o estado
  normal — Alt+C) o WebView2 mantém o DOM, e a leitura continua a funcionar
  (é o que as leituras acima mostram: `visible=false`).
- **Janela**: a app do Sotto já tem, medido e documentado em `AGENTS.md`, um flash
  de painel no arranque (pywebview transparente). A minha corrida de medição
  arrancou mais uma instância, e o censo às 13:35:22Z registou
  `JANELAS ... visiveis=16 ... reencontro=1` contra 15 antes. Não mexi em código
  de visibilidade, e `windows` declarou `NO WINDOW SHOWING SIGNAL FOUND` para o
  comando de arranque; mas o número subiu, e fica dito.

## 8. CACHE/PRICE

Ver o recibo do agente `PainelTextoSemVisao` (secção `## CACHE/PRICE`), gerado por
`bash I:/!manager/scripts/cache-task-report.sh PainelTextoSemVisao`.
