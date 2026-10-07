# Reinício a cada ~30 s: causa medida e cura

Alvo: `H:/sotto` (nada em `I:/!manager` foi tocado).
Data da medição: 2026-10-06, entre 13:44Z e 13:54Z (10:44–10:54 local, UTC-3).
Log do dono: `H:/sotto/_main/webview-run.log` (ainda a crescer durante a auditoria —
a app do dono corre em `pythonw.exe` pid **40784**, `--with-worker`).

---

## 0. O defeito, em uma linha

O worker **esta' a produzir**, e o shell mata-o na mesma por "não disse nada":

```
sotto: BRIDGE_DEATH_LIFTED reason=caption captions=29
sotto: BRIDGE_CAPTION_SENT delivered=true text="Olha o E que eu Simplesmente"
sotto: BRIDGE_SILENT ms=15000 pid=4312          <-- watchdog dispara
sotto: BRIDGE_RESTART reason=silent in_ms=30000 restart=17
sotto: BRIDGE_EXIT pid=4312 rc=1 spawns=9 captions=31 statuses=62 malformed=0
       stderr_tail=[… "WORKER_STATS tag=tick blocks=92 … nonzero_blocks=92
                        peak=0.383783 … gain_db=+7.6" …]
sotto: BRIDGE_DEATH rc=1 deaths=9 last="worker exit 1"
```

Note-se o que o **próprio shell registou no mesmo instante**: o `BRIDGE_EXIT`
carrega, no `stderr_tail`, o batimento do worker com `blocks=92`
`nonzero_blocks=92` `peak=0.383783`. O shell estava a receber a prova de
progresso **ao mesmo tempo** que declarava silêncio.

---

## 1. A CAUSA: quem decide, e que sinal esperava

Medido lendo o código, não adivinhado.

| | |
|---|---|
| **Quem decide** | `WorkerBridge._arm_silence()` — `app/webview/sotto_webview.py:3196`, arma `threading.Timer(self.silence_ms/1000, self._on_silence)` |
| **Onde dispara** | `_on_silence()` — `sotto_webview.py:3299` → `BRIDGE_SILENT ms=15000` em `:3339` → `_kill_and_restart('silent')` em `:3344` |
| **Que sinal re-arma o timer** | `sotto_webview.py:3075` — `self._arm_silence()`, executado **só para linhas de STDOUT** |
| **O que o STDOUT leva** | JSONL de `caption` / `status` — eventos **esparsos**, dependentes de haver fala |
| **O que fica de fora** | o ramo `if name == 'stderr':` (`sotto_webview.py:3057`) faz `continue` (`:3074`) **antes** do re-arm |
| **O sinal periódico que existe** | `WORKER_STATS tag=tick … blocks=<N>` em **STDERR**, a cada `--stats-interval` = **10 s** (`worker/sotto_worker.py:1798-1803`; emitido em `:2424`/`:2542`) |
| **Janela do watchdog** | `silence_ms` = **15000 ms** (`sotto_webview.py`, default do construtor) |

**A janela `in_ms=30000` do log NÃO é o watchdog.** É o *backoff* do reinício:
`_schedule_restart` faz `delay = min(backoff_max, backoff_base * 2**restarts)`
(`sotto_webview.py:3401`), ou seja `30000` é o teto depois de `restarts>=5`.
A janela real do silêncio **era `15000`** (passou a `30000` com a cura — §3).

**A contradição estrutural:** o único sinal **periódico** que o worker publica
(o batimento de 10 s) viaja no stream que o watchdog **ignora**. O watchdog
estava armado contra *legendas*, contra um worker cujo sinal de vida é um
*batimento de áudio* — e uma pausa de fala de 15 s (normal numa conversa)
mata-o.

**E o `rc=1` não é uma avaria do worker — é o próprio shell a matá-lo.**
`_kill_and_restart` chama `child.terminate()`; no Windows isso é
`TerminateProcess(handle, 1)`:

```
Popen.terminate() -> returncode = 1
```

Logo `BRIDGE_DEATH rc=1 last="worker exit 1"` é o shell a reportar a sua própria
morte como se fosse do worker. É daqui que sai o `namedState="exit"` /
`panel.status.kind="error"` que o dono vê.

---

## 2. Os comandos, com rc e saída

### 2.1 Censo do campo (o "ANTES", na janela declarada)

```
py -3 _main/restart-30s-oracle.py --field _main/webview-run.log
```

```json
{
  "window": { "from": "10:45:40", "to": "10:49:46", "seconds": 246,
              "declared_as": "last 5 HISTORY_APPEND commit stamps" },
  "commit_gaps_s": [62, 56, 71, 57],
  "restart_silent": 4, "restart_exit": 4,
  "restarts_per_min": 1.95, "silent_per_min": 0.98,
  "spawns_in_window": 4, "captions_in_window": 11,
  "whole_file_restart_silent": 38, "whole_file_spawned": 63
}
```

rc do comando completo (campo + braços): **0**.

> **A janela anda.** A app do dono continuava em ciclo enquanto isto era medido,
> por isso a "última de 5 commits" desloca-se a cada corrida. Re-corrido ~7 min
> depois, a mesma medição deu janela `10:49:46 → 10:56:13` (387 s) e
> **1,86 reinícios/min** (`silent` 0,93/min) — a mesma ordem de grandeza, com o
> ficheiro já em 41 `reason=silent` e 65 `BRIDGE_SPAWNED`. O número estável é
> **≈1,9 reinícios/min**; a janela exacta é função do instante da medição.

### 2.2 O batimento chega mesmo enquanto o shell declara silêncio

```
grep -c "BRIDGE_EXIT.*WORKER_STATS tag=tick" _main/webview-run.log   -> 16
grep -c "BRIDGE_EXIT"                        _main/webview-run.log   -> 53
grep -c "BRIDGE_DEATH rc="                   _main/webview-run.log   -> 52
grep -c "BRIDGE_DEATH_LIFTED"                _main/webview-run.log   -> 13
```

**16 de 53** linhas de `BRIDGE_EXIT` trazem um `WORKER_STATS tag=tick` na cauda
de stderr que o shell guarda (só 3 linhas). Ou seja: em pelo menos 30% das
mortes o shell estava a **receber o batimento do worker que tinha acabado de
matar por não dizer nada** — e essa proporção é um *piso*, limitado pela cauda
de 3 linhas.

---

## 3. A cura

`app/webview/sotto_webview.py` (sha256 `a10d77e9ddfb964699d07a029a4e55d3c69f6471bd40aa776bed7891c1732762`):

1. **`_note_progress(stats)`** (`:3221`): um `WORKER_STATS` em stderr conta como
   **PROGRESSO** e re-arma o watchdog — **se e só se** o contador `blocks=`
   **avançar**. Um worker encravado que reimprime a última linha não compra
   perdão eterno: `blocks <= self._progress_blocks` → não re-arma.
2. **`_pump`** (`:3073`): o ramo de stderr passa a chamar `_note_progress`.
   É a linha que cura — antes havia ali um `continue` que saltava o re-arm.
3. **`_progress_blocks`** (`:2839` init, `:2964` reset por filho): o contador de
   `blocks=` reinicia em 0 a cada spawn, logo o valor do processo morto tem de
   ser limpo, senão todo batimento do filho novo parece repetição.
4. **Janela: 15000 → 30000 ms** (`WORKER_SILENCE_MS`, `:238`; usado como default
   em `:2776`), com `WORKER_STATS_INTERVAL_S = 10.0` (`:225`) ao lado.
   Justificação medida: o batimento é 10 s; uma janela de 15 s deixa 5 s de
   margem, e o worker faz inferência **na mesma thread** que bate o tick
   (`infer_wall_s=1.78` no log), pelo que um tick atrasado é esperado. 3×
   o batimento mantém a deteção de um worker realmente encravado em 30 s.
   **Isto não é afrouxar o watchdog: é mudar o que ele mede** — de "nenhuma
   legenda em 15 s" para "nenhum progresso em 30 s", onde progresso = legenda
   nova OU bloco de áudio novo OU status novo.

O código que **não** mudou: `_on_silence` na rota `no_audio`/benigna
(`BRIDGE_SILENT_BENIGN`) e o `panel.html/css/js` (congelados pela lane
`PainelTextoSemVisao` — não tocados).

---

## 4. Par de controlos (o mesmo instrumento, o mesmo cenário)

Ficheiros: `_main/restart-30s-oracle.py` (sha256 `8aa8f0ec…`) e o fixture
`_main/_restart-30s-fake-worker.py` (sha256 `a44b02b1…`). O fixture reproduz a
**forma medida**: aquecimento em stdout, **uma** legenda, e depois nada em
stdout enquanto o batimento corre em stderr com `blocks` a avançar.

O braço RED é uma **cópia da shell de hoje** com **exatamente uma linha**
revertida (`self._note_progress(parsed)` → `pass`); o oráculo recusa correr
(rc=2) se o padrão não for encontrado ou se a cópia diferir por mais do que
essa linha.

```
py -3 _main/restart-30s-oracle.py
```

```
GREEN heartbeat: spawns=1 respawns=0 silent_kills=0 reason_silent=0 progress_blocks=380 captions=1
RED heartbeat (pre-fix copy): spawns=7 respawns=6 silent_kills=3 reason_silent=3 progress_blocks=None captions=7
ANOMALY wedge: spawns=5 respawns=4 silent_kills=3 reason_silent=3 progress_blocks=20 captions=5
static: worker --stats-interval default=10.0s shell WORKER_STATS_INTERVAL_S=10.0s shell WORKER_SILENCE_MS=30000ms

VERDICT: GREEN -- heartbeat counts as progress (0 restarts); the pre-fix copy
still loops; a wedged worker is still restarted.
```

rc = **0**.

| braço | shell | fixture | respawns | `BRIDGE_SILENT` | `reason=silent` |
|---|---|---|---|---|---|
| GREEN heartbeat | com a cura | batimento | **0** | 0 | 0 |
| RED heartbeat | pré-cura (1 linha) | batimento | **6** | 3 | 3 |
| ANOMALY wedge | com a cura | bate 1× e emudece | **4** | 3 | 3 |

Os braços GREEN e RED correm o **mesmo** instrumento, o **mesmo** fixture e o
**mesmo** cenário; divergem **só** na linha que cura. O terceiro braço é o
controlo-anti-vacuidade: um worker que *realmente* para continua a ser
reiniciado — a cura não desligou o watchdog.

Protocolo de janela comprimida: `SILENCE_MS=600`, batimento a `150 ms`
(4× margem, contra 3× no campo). O que está sob teste é a **razão**, não o
número absoluto.

> **Leitura dos números.** Os contadores de respawn/kill *variam entre corridas*
> com o escalonamento da máquina (corridas observadas: `respawns` 3–6 no RED,
> `sample(s)` de morte 14–17); o que é **determinístico** é o `rc`, o VERDICT, e
> a divergência `0` no GREEN contra `≥1` no RED. Nenhuma asserção depende de um
> valor exacto — todas comparam com 0 ou com "≥1".

### 4.1 O gate consegue ficar RED?

```
py -3 _main/restart-30s-oracle.py --selftest     ->  rc = 0
```

```
selftest: …\_restart-30s-prefix-mutant.py (line 3073: self._note_progress(parsed) -> pass)
  selftest FAIL (expected) GREEN heartbeat: the shell RESTARTED a worker whose heartbeat was advancing (3x)
  selftest FAIL (expected) GREEN heartbeat: BRIDGE_SILENT fired on a working worker
  selftest FAIL (expected) GREEN heartbeat: BRIDGE_RESTART reason=silent on a working worker
  selftest FAIL (expected) GREEN heartbeat: the heartbeat never reached the watchdog (progress_blocks=None)
  selftest FAIL (expected) GREEN heartbeat: the panel showed a DEATH for 14 sample(s) while the worker was working
  selftest FAIL (expected) GREEN heartbeat: an ERROR status was painted while the worker was working
selftest: rc=0 -- the GREEN checks went RED on the pre-fix copy (6 failure(s))
```

### 4.2 Não parti nada: regressão do oráculo anterior

```
py -3 _main/tap-restart-loop-oracle.py     ->   VERDICT: PASS (0 failing check(s))
py -3 -m py_compile app/webview/sotto_webview.py _main/restart-30s-oracle.py _main/_restart-30s-fake-worker.py  ->  rc=0
```

---

## 5. `panel-state.json` depois da cura (a aceitação)

O `namedState` é decidido por `SottoShell._named_panel_state(worker, panel_status)`
(`sotto_webview.py:1976`). O oráculo **não reimplementa** essa precedência:
chama a função da shell e alimenta-a com o `bridge.snapshot()` real de cada
braço, amostrado a cada 50 ms durante o braço inteiro — e guarda o **pior**
estado observado, porque o painel mostra a morte desde o `BRIDGE_EXIT` até a
primeira legenda a levantá-la.

```
panel-state GREEN heartbeat: namedState(live)='receiving' namedState(no footer)='capture-started'
                             pendingError=None
panel-state RED heartbeat (pre-fix copy): namedState(live)='receiving' namedState(no footer)='exit'
                             pendingError='exit'
```

- Com a cura, `namedState` = **`receiving`** (≠ `exit`) e `pendingError` = **None**
  enquanto as legendas chegam → **aceitação cumprida**.
- Sem a cura, a mesma função devolve **`exit`** — o `namedState` que o dono viu
  no `_main/panel-state.json` (`"namedState": "exit"`, `status.kind: "error"`,
  `"Worker stopped (exit 1) - worker exit 1"`).

**Limitação declarada:** este `namedState` é composto pela função shipped a
partir do estado real da bridge, **não** lido de um `panel-state.json` escrito
pela app com janela WebView2. A app do dono (pid 40784) continuava a correr o
código **antigo** (carregado no arranque) e está em ciclo enquanto isto foi
medido; eu **não** a matei nem relancei (relançar abre janela no desktop dele).
O `panel-state.json` real pós-cura sai no próximo arranque da app.

---

## 6. Quanto custa o modelo a recarregar (o que o dono paga em CPU)

Medido, com o **mesmo interpretador** que a app usa
(`C:\Program Files\Python311\python.EXE`, o que aparece em `BRIDGE_SPAWNED`):

```
"C:\Program Files\Python311\python.EXE" worker/sotto_worker.py --max-seconds 5
```

```json
{"type":"status","state":"model-loaded","model":"nemotron-3.5-asr-streaming-0.6b-int8",
 "providers":["CUDAExecutionProvider","CPUExecutionProvider"],
 "load_s":4.6,"rss_mb":1674.8,"peak_rss_mb":1693.4,...}
```

…e a última linha `WORKER_STATS tag=final … rss_mb=2429.5`.

- **`load_s = 4.6 s`** por arranque — só a carga do modelo.
- **`rss_mb = 2429.5`** (2,4 GB) por worker, confirmado no worker **do dono**
  (`WORKER_STATS … rss_mb=2415.9` no log).
- Taxa do loop: **1,95 reinícios/min** (janela declarada) × 4,6 s ≈ **9 s de
  cada 60 s** gastos a recarregar o modelo — **~15% do tempo em carga**, e,
  pior, o contexto de hipótese do ASR morre com o processo a cada ciclo.

> Nota de armadilha medida: correr o worker com o interpretador errado
> (`py -3` do venv do manager) dá `ModuleNotFoundError: No module named
> 'onnxruntime'` e `rc=1` em 0,2 s. É o mesmo modo de falha já registado em
> `_main/audio-escopo-restore-app.ps1`. A medição acima usou o interpretador
> correto.

---

## 7. Ficheiros

| ficheiro | estado |
|---|---|
| `app/webview/sotto_webview.py` | **alterado** (cura), sha256 `a10d77e9…` |
| `_main/restart-30s-oracle.py` | **novo** (oráculo + par de controlos + selftest + censo de campo), sha256 `8aa8f0ec…` |
| `_main/_restart-30s-fake-worker.py` | **novo** (fixture), sha256 `a44b02b1…` |
| `_main/_restart-30s-prefix-mutant.py` | gerado em cada corrida pelo oráculo (cópia pré-cura) |
| `_main/_probe/restart30s-final.json` / `.out` | recibo bruto da corrida final |
| `app/electron/panel.html` / `.css` / `.js` | **não tocados** |

Reverter a cura: `self._note_progress(parsed)` → `pass` na linha 3073 e repor
`silence_ms=15000`.

---

## 8. LIMITAÇÕES (explicitas)

- O par de controlos corre a **classe `WorkerBridge` real, importada do ficheiro
  shipped**, com um fixture que reproduz a forma medida — não uma janela
  WebView2 com microfone. Não houve corrida com GUI: abrir a app compete com a
  instância do dono e abre janela no desktop dele.
- O "DEPOIS" no relógio real é uma **projeção medida**: 0 reinícios enquanto o
  batimento avança (provado no oráculo a 4× o campo) e o batimento é 10 s < 30 s
  de janela. A confirmação no campo exige o próximo arranque da app do dono.
- `worker_stats_lines` no braço do oráculo é sempre 0 (o shell não loga as
  linhas de stderr cruas), pelo que essa métrica não é usada em nenhuma
  asserção.

---

## SELF-AUDIT

- **protocolos em falta** — senti falta de um protocolo que **amarra dois
  ficheiros por um número**: `--stats-interval` (worker) e `silence_ms` (shell)
  têm de estar em relação, e nada no repo o verificava. Foi por isso que o bug
  ficou invisível: a shell materializava uma política ("legenda é o único
  progresso") sobre um worker cuja cadência é outra. Acrescentei a asserção ao
  oráculo (`static_checks`), mas ela vive num oráculo, não numa convenção que
  outros respeitem. Faria diferente: um `WORKER_HEARTBEAT_CONTRACT` num sítio
  neutro, lido pelos dois.
- **verificação adicional** — a que teria aumentado a confiança era uma corrida
  **real** com o worker verdadeiro sob a `WorkerBridge` durante ≥ 2 ciclos (≥ 120 s).
  Não a corri: custa duas cargas de 2,4 GB, disputa o dispositivo de áudio com a
  app do dono (a correr) e o ponto de extensão (`worker_path=` no oráculo)
  existe, mas o resultado seria dominado pelo modelo carregado no processo, não
  pela policy. Custo estimado: ~120 s e ~2,4 GB de RSS.
- **checkboxes novas (mecânico)** — `py -3 _main/restart-30s-oracle.py --selftest`
  tem de dar rc=0 **antes** de qualquer alteração a `_pump`/`_arm_silence`/
  `_on_silence`: red-ifica a cura e prova que os checks verdes não são vacuosos.
  E, para a classe "watchdog sobre subprocesso": *o contador de progresso
  declarado pela política tem de ser comparado com o sinal periódico real do
  filho, lido do fonte do filho* — foi essa comparação que faltava.
- **review por outro subagente** — **sim-com-escopo**: o que eu gostava revisto
  por outro é exactamente o `static_checks` (a asserção `WORKER_SILENCE_MS >= 2×
  batimento` e a leitura do default de `--stats-interval` por regex do fonte do
  worker) — é a parte que pode ser verde-vacuosa se o regex deixar de casar e
  alguém a fizer "passar". O resto (oráculo + fixture + par de controlos) é
  auto-verificável por rc.
- **gate-doubt**:
  - verde-de-verdade: os verdes reais foram (a) `--selftest` rc=0 — **não é
    vacuoso, foi medido a ficar RED** (6 falhas esperadas contra a cópia pré-cura);
    (b) `tap-restart-loop-oracle.py` PASS — correu contra o ficheiro alterado, e
    é um instrumento **distinto** do meu; (c) `py_compile` rc=0. **O que podia
    ser vacuoso, e verifico agora:** o braço GREEN dá `progress_blocks=380`
    (não `None`) — se o fixture não tivesse emitido batimentos, o check
    "progress_blocks" teria rebentado; e o RED dá `progress_blocks=None`, o que
    prova que a variável é sensível à cura e não passada por construção.
  - falta-no-gate: o oráculo **não** verifica que a app real (WebView2 +
    dispositivo + modelo) deixa de reiniciar. Cenário que o atravessa: alguém
    sobe `--stats-interval` para 40 s no `run.cmd` sem tocar em `sotto_webview.py`
    — a asserção estática lê o *default do argparse*, não a linha de comandos
    usada no arranque, e continuaria verde enquanto a app voltava ao loop.
  - gate-melhor: um check que leia o `argv` real do worker do próprio log da
    app (`BRIDGE_SPAWNED argv=[…]`) e falhe se `--stats-interval` aparecer com
    valor > `WORKER_SILENCE_MS/2000`:
    `py -3 _main/restart-30s-oracle.py --field <log>` — input que tem de o deixar
    RED: um log com `BRIDGE_SPAWNED argv=[… "--stats-interval", "40" …]`.
    **Não implementado** (o custo é um parser de argv; nomeado, não feito).
- **confianca** — **alta** para a causa e para a cura na `WorkerBridge`
  (determinística, rc=0, RED reproduzido, selftest red-ifica os verdes, regressão
  do oráculo anterior PASS). **média** para o número de campo depois da cura: é
  projeção (0 reinícios com batimento < janela) e não uma corrida real da app.
  O que a muda: arrancar a app do dono com este código e ler
  `_main/panel-state.json` e `restart_silent` na mesma janela declarada.
- **nao verificado**
  - a app do dono a correr **com** esta cura (não relancei; pid 40784 corre o
    código antigo);
  - `panel-state.json` escrito por uma janela real pós-cura;
  - o braço Electron (`app/electron/worker-bridge.js`) — li que o seu watchdog é
    um *first-output ceiling* (`if (this.sawOutput || !this.child) return;`), logo
    **não** tem este defeito, mas não o medi;
  - o `run.cmd` **verificado agora** (`app/webview/run.cmd`, 8551 B, mtime
    2026-10-06 05:41): **não** passa `--stats-interval` nem escolhe o
    interpretador do worker — localiza `pythonw.exe` ao lado do `python` que
    `py -3` resolve (`run.cmd:51-72`) e recusa arrancar sem ele. Logo o worker
    corre com o default de 10 s, e a armadilha do interpretador errado
    (`onnxruntime`) é do *arranque*, não do ficheiro;
  - o efeito no `history`/`CAPTION_APPLIED` da continuidade do ASR (só observável
    numa corrida real).

---

## CACHE/PRICE

```
bash 'I:/!manager/scripts/cache-task-report.sh' Reinicio30sSotto
```

rc = **0**. Saída VERBATIM (linhas longas truncadas pelo próprio instrumento de captura,
marcadas com `…`):

```
## CACHE/PRICE
- task/agent: Reinicio30sSotto
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\Reinicio30sSotto.jsonl
- cache: read=10641420 write=0 hit=97.5606% (cache-read / input+cache-read); universe: 70 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\Reinicio30sSotto.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=62 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=5 input=$0.00000000 ou…
- when-failed: break_items=2; WHEN=2026-10-06T13:46:32.229000+00:00 | break_items=1; WHEN=2026-10-06T13:46:33.364000+00:00 | break_items=2; WHEN=2026-10-06T13:46:34.099000+00:00 | break_items=7; WHEN=2026-10-06T13:46:34.592000+00:00 | break_items=2; WHEN=2026-10-06T13:48:29.966000+00:00 | break_items=2; WHEN=2026-10-06T13:53:33.061000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 118784 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'Reinicio30sSotto']; window: 2026-10-06T13:46:32.229000+00:00..2026-10-06T13:53:33.061000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791294392229 | session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791294393364 | session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791294394099 | session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791294394592 | session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-flash model=deepseek-flash item_index=87; turn_id=1791294509966 | session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-…
- report generated_at: 2026-10-06T13:55:05.781767+00:00
- usage rows: 70
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 266074
- output tokens: 55658
- cache-read tokens: 10641420
- cache-write tokens: 0
- hit ratio: 97.5606% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=62 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=5 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; o…
- prefix breaks: 16 (state=RESOLVED-BREAKS-OMP; population: 6 of 118784 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'Reinicio30sSotto']; window: 2026-10-06T13:46:32.229000+00:00..2026-10-06T13:53:33.061000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T13:46:32.229000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791294392229
  - break_items=1; WHEN=2026-10-06T13:46:33.364000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791294393364
  - break_items=2; WHEN=2026-10-06T13:46:34.099000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791294394099
  - break_items=7; WHEN=2026-10-06T13:46:34.592000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791294394592
  - break_items=2; WHEN=2026-10-06T13:48:29.966000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-flash model=deepseek-flash item_index=87; turn_id=1791294509966
  - break_items=2; WHEN=2026-10-06T13:53:33.061000+00:00; WHERE session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1 provider=deepseek-flash model=deepseek-flash item_index=223; turn_id=1791294813061
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

- **cache:** read=10641420 write=0 hit=97,5606 % (universe: 70 usage rows do meu
  `Reinicio30sSotto.jsonl`; instrumento: `scripts/cache-task-report.sh`).
- **price:** $0,00000000 USD reportado; as taxas por modelo são UNKNOWN — não
  registadas nesta fonte (é o próprio instrumento que o diz).
- **when-failed:** 6 janelas de prefix-break entre 2026-10-06T13:46:32Z e
  13:53:33Z; a maior `break_items=7` às 13:46:34.592Z (≈ 1 s após o anterior).
- **where-failed:** todas em `session_id=01a11177-1ee4-742d-9eaa-e92da6c07fd1`,
  `item_index` 0/0/0/0/87/223 — três delas no *primeiro* item da chamada, que é
  onde a rota troca de provider (`cline-pass` → `space-bunny-free` →
  `ling-3.1-flash-free` → `deepseek-flash`).
- **source:** `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\Reinicio30sSotto.jsonl`.
- **when/where FALHOU (do instrumento):** o caminho `I:/manager/scripts/...` que
  o protocolo nomeia não resolve nesta caixa (`No such file or directory`, rc=127);
  o script existe em `I:/!manager/scripts/...`. Correu a partir daí, rc=0.
