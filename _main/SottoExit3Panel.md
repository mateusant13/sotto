# SottoExit3Panel — o painel RENDERIZAVA o codigo de saida? Nao: ele nunca o via.

**Lane:** `app/webview/` (a shell WebView2). **Data:** 2026-10-06.
**Brecha declarada pela propria lane anterior** (`_main/SottoDeviceResolution.md`,
verbatim): *"nao verificado: the WebView2 panel's RENDERED state on exit 3 --
read the code, did not run the shell."*
**Ficheiros tocados:** `app/webview/sotto_webview.py` (o meu ficheiro),
`AGENTS.md` (linhas de contrato), `_main/panel-exit3-oracle.py` + logs e o
`_main/_prefix-under-test.py` (o input RED), `agents/SottoExit3Panel.md`.
**Nao tocados:** `worker/*` (a lane anterior), `app/electron/*` (o braco de
referencia), `app/electron/panel.{html,js,css}` (outra lane).

---

## 1. O headline CONTRADIZ o brief, e e' maior que ele

O brief pedia: "se o painel engolir o codigo, corrige-o". Ele engolia — mas por
uma causa que nenhuma das duas lanes tinha visto, e o efeito e' maior do que o
exit 3:

> **`run.cmd --with-worker` (O APP) entrav(a) em deadlock no proprio lock no
> primeiro worker, e por isso o shell nunca leu UMA linha do stdout do worker.
> Como captions e statuses viajam no MESMO pump de stdout, o app nao conseguia
> mostrar UMA legenda.** Medido: `BRIDGE_EXIT … statuses=0` em **8 de 8** ciclos
> de worker, `WORKER_AUTOSTART` nunca impresso, `--dump-dom` nunca correu,
> `--exit-after` nunca armado (`_main/exit3-armB1.log`, 74 linhas).

A causa, no codigo:

```
start()            -> with self._lock:            # threading.Lock, NAO reentrante
                        self._bridge_status(...)
                        self._spawn()             # ... que termina com
                            self._arm_silence()   # -> with self._lock:  == DEADLOCK
```

`_spawn()` corre COM o lock tomado; `_arm_silence()` tomava o mesmo lock. O
thread do `start()` bloqueia-se contra si mesmo. Os threads `_pump` tambem
chamam `_arm_silence()`, portanto bloqueiam antes da primeira linha — excepto o
de **stderr**, que faz `continue` antes da chamada e por isso continuou a
funcionar. E' essa assimetria que faz o sintoma parecer impossivel: o stderr
chega (`SILENT-DEVICE … peak=0.000122 < floor=0.002` esta' no `stderr_tail`) e o
stdout nao chega a lado nenhum.

Corre(c)cao (a menor que fecha a classe): `_arm_silence()` **nao toma lock**. O
`_on_silence` ja' re-checa `self.stopped`, portanto a pior corrida com `stop()`
e' um timer que dispara e retorna.

## 2. A segunda metade: o classifier engolia o veredicto

Desfeito o deadlock, os statuses chegam — e ai' o swallow seguinte aparece, agora
no codigo que `_main/SottoDeviceResolution.md` leu e considerou seguro:

| o worker diz | a shell pintava | o braco de referencia ja' decidia |
|---|---|---|
| `state: silent-device` | `silent-device` **busy** | — (estado novo, 2026-10-06) |
| `state: device-exhausted` | `device-exhausted (all-flat)` **busy** | `kind: 'error'` (`worker-bridge.js:133`) |
| `state: done, verdict: all-candidate-taps-flat` | `done` **busy** | sem caso (o verdict e' novo) |

`FAILURE_WORDS_RE = error|fail|fatal|dead|stopped|crash|denied|missing` nao contem
nenhuma dessas palavras, e o veredicto viaja DENTRO do `done`. O shell admite a
omissao no proprio `_readable()` ("that table is a cosmetic dictionary in another
file and is NOT ported here"). O que se porta agora e' a DECISAO, nao a prosa.

## 3. Aceitacao — o RENDER, os dois bracos, colado

`py -3 _main/panel-exit3-oracle.py 30 22` (bracos reais, shell com
`CREATE_NO_WINDOW`, **`--no-hotkey`**). Saida: `ORACLE_RC=0`, `verdict: PASS`,
`failures: []`. Extracto de `_main/panel-exit3-oracle.log`:

```json
"armA_worker_alive": {
  "shell_rc": 0, "worker_exits": [1],
  "rendered": { "text": "Receiving captions", "error": false, "live": true,
                "className": "status status--live", "captions": 2,
                "placeholderTitle": "Warming up" },
  "status_applied": ["device","device","capture-started","capture-started",
                     "Receiving captions","Receiving captions"],
  "stderr_silent_lines": [] },

"armB_worker_exit3": {
  "shell_rc": 0, "worker_exits": [3, 1],
  "rendered": { "text": "Worker stopped (exit 3) - Worker finished on silent-device",
                "error": true, "live": false,
                "className": "status status--error",
                "placeholderTitle": "Worker stopped",
                "placeholderBody": "verdict=silent-device device=Mapeador de som da Microsoft - Input
                                     peak=0.000122 blocks=60 captions=0 tokens=0 chunks=10 rotations=0
                                     WORKER_STATS tag=final … SILENT-DEVICE Mapeador de som da Microsoft
                                     - Input [MME] peak=0.000122 < floor=0.002 over 60 blocks …"},
  "status_applied_tail": [
      "Silent audio device - Mapeador de som da Microsoft - Input [MME] peaked 0.000122 < floor 0.002",
      "Worker finished on silent-device",
      "Worker stopped (exit 3) - Worker finished on silent-device" ],
  "held_lines": ["BRIDGE_STATUS_HELD state=\"model-loading\" behind=\"done\"", …] }
```

- **Braco A (worker vivo, tom injetado no cabo):** o painel escreve
  `Receiving captions`, `status--live`, `captions=2`. Pela primeira vez o
  caminho worker→stdout→pump→painel produziu legendas. O `worker_exits=[1]` e' o
  `request_exit` do `--dump-dom` a terminar o worker, nao uma falha.
- **Braco B (worker forcado ao dispositivo mudo, exit 3):** o painel escreve
  `Worker stopped (exit 3) - Worker finished on silent-device`, com
  `status--error` e o corpo do placeholder a NOMEAR o dispositivo, o pico e o
  floor. O `--name` obrigatorio do brief ("assert on WHAT THE PANEL SHOWS") esta'
  satisfeito e o dispositivo aparece no corpo.
- **Braco negativo:** o proprio oraculo falha se os dois renders forem iguais
  (`A.text != B.text` e `A.error != B.error`), e ambos os `assert` passaram.
- **Retencao atraves do restart:** 7 linhas `BRIDGE_STATUS_HELD … behind="done"`
  provam que `model-loading`/`model-loaded`/`device`/`capture-started` do restart
  NAO apagaram a morte, como antes apagavam.

## 4. O gate tem as duas cores (nao passa por construcao)

`_main/panel-exit3-oracle.py --unit` alimenta o proprio `WorkerBridge` da shell
com as linhas reais do worker (sem placa de som, sem modelo, sem WebView2). O
input RED e' `_main/_prefix-under-test.py`, que preserva o classifier PRE-fix:

```
PANEL_ORACLE_SHELL=…/_prefix-under-test.py py -3 _main/panel-exit3-oracle.py --unit  -> rc=1
  ARM 0/silent-device: kind='busy' expected 'error' (text='silent-device')
  ARM 0/device-exhausted: kind='busy' expected 'error'
  ARM 0/done-failure: kind='busy' expected 'error' (text='done')
  ARM 0/restart: a warm-up status PAINTED OVER the death
  … 10 falhas ao todo
py -3 _main/panel-exit3-oracle.py --unit                                                -> rc=0
```

Os dois bracos do oracle NAO podem passar por acidente: o A exige
`error=false ∧ live=true ∧ captions>0`, o B exige `rc=3` no
`BRIDGE_EXIT` ∧ `error=true` ∧ a palavra de falha ∧ o nome do dispositivo.

## 5. Medicoes que CONTRADIZEM o brief / que eu proprio violei

1. **`statuses=0`, nao `statuses>0`** — o brief assumia que o painel recebia os
   statuses e os pintava mal. Nao recebia nenhum. (Secao 1.)
2. **O app nao mostrava legendas nenhumas** — consequencia do mesmo deadlock, e
   nenhuma lane tinha corrido o caminho real (a lane anterior mediu o stdout do
   worker directamente, com exit 0 e 17 captions; isso nunca passou pelo painel).
3. **`TypeError: 'NoneType' object is not subscriptable` no `stage=chunk` do
   worker** com audio de silencio digital (`_main/exit3-armB-worker.jsonl`,
   `--device "Mapeador de som da Microsoft - Input"`): o `run_chunk` estoura e o
   worker emite `state: error` e para o tap. **Nao e' meu ficheiro** e nao o
   corrigi: fica nomeado para a lane do worker (`worker/sotto_worker.py`, dono da
   lane `SottoDeviceResolution`).
4. **O verdict de topo do worker nao bate com o status barulhento** no mesmo run:
   o `done` diz `all-candidate-taps-flat` enquanto um `silent-device` foi emitido
   (a ramificacao `if outcome in ("all-flat","open-failed")` vence a
   `elif ran_but_silent`). O painel mostra os DOIS, portanto nao mente; o worker
   sim, por dentro. Tambem nomeado, nao corrigido (ficheiro alheio).
5. **VIOLACAO DA REGRA DA CASA, minha.** Dois runs meus subiram `python.exe`
   directamente do shell do harness. O censo de janelas nomeou-os:
   `ALERTA-JANELA ts=2026-10-06T06:42:22Z chave=24836:22814874 pid=24836
   nome=python` e `…06:50:22Z chave=18056:8789598 pid=18056 nome=python` —
   exactamente os `pid` da linha 1 dos meus logs. Correc(a)o aplicada: todos os
   runs passam pelo oracle, que usa `CREATE_NO_WINDOW`, e o proprio oracle corre
   sob `pythonw`. Alem disso o shell REGISTOU o Alt+C do dono nesses runs
   (2x `PANEL_SHOWN reason=hotkey` no `exit3-armB1.log`), o que e' um segundo
   dano: um probe que rouba a unica tecla do app responde-lhe com o SEU painel.
   Por isso `--no-hotkey` passou a existir, e os dois bracos usam-no.
6. **Nao atribuido:** `ALERTA-JANELA ts=2026-10-06T06:54:22Z chave=6724:29693352
   pid=6724 nome=pythonw` caiu DENTRO da janela de execucao do meu oracle (que e'
   pythonw e cujos shells-filhos sao pythonw). O censo regista pid/hwnd/nome e
   **nao** o titulo, o pid ja' nao existia para interrogar, e o `create_window`
   passa `hidden=True` (que o pywebview honra com `Show(); Hide()` — winforms.py
   :777-782). Se aquela janela era o painel, entao o APP mostra o painel no
   arranque, contra o "start hidden" do `run.cmd`. **Nao verificado, nao
   atribuido** — o check que fecha isto esta' na self-audit.

## 6. O que o shell ganhou, linha a linha

| mudanca | porque |
|---|---|
| `_arm_silence()` sem `self._lock` | o deadlock da seccao 1; `_spawn` corre com o lock tomado |
| `WORKER_ERROR_STATES` / `HEALTHY_DONE_VERDICTS` / `worker_status_kind` | porta a DECISAO do STATE_MAP do braco Electron, inclusive o verdict dentro do `done` |
| `worker_status_text` / `worker_status_body` | o painel passa a nomear a CAUSA do worker (dispositivo, api, pico, floor, detail) em vez de um token pelado |
| `pending_error` + `WORKER_WARMUP_STATES` (hold) | a morte sobrevive ao restart automatico ate' um CAPTION provar recuperacao |
| `last_error` + `BRIDGE_DEATH` + `stderr_tail` no corpo | a ultima linha de stderr do worker (`SILENT-DEVICE …`) chega ao painel, nao so' ao log |
| `_pump` loga `BRIDGE_PUMP_DIED` / `BRIDGE_PUMP_NULL` | um leitor que morre engolia tudo em silencio (`except Exception: pass`) |
| `--dump-dom-wait S` | medir DEPOIS de o worker ter corrido; sem isto o dump fotografia o arranque |
| `--no-hotkey` | medicao nao rouba o Alt+C do dono |
| `BRIDGE_PROBE` + `status.{text,className,error,live}`, `placeholder.{title,body,warming}`, `captions.{count,hidden}` | o dump passou a carregar o estado RENDERIZADO, nao so' geometria |

## SELF-AUDIT

- **protocolos em falta:** nenhuma lane tinha a regra que este caso exigia:
  *um agente que mede um app GUI tem de passar pelas flags que o tornam
  invisivel e nao-interactivo* (`--no-hotkey`, `CREATE_NO_WINDOW`). Tive de a
  descobrir pelo censo de janelas, com o meu pid la' dentro. Faria diferente:
  antes do primeiro run, ler as flags do shell e perguntar "esta invocacao
  consegue pôr uma janela no ecra do dono, ou roubar-lhe a tecla?".
  Falta tambem uma regra que o brief violou por omissao: *um brief que pede para
  "fixa no ficheiro X" deve primeiro deixar medir se X e' a causa* — aqui a causa
  estava um nivel abaixo (o lock), e teria sido errado corrigir so' o classifier.
- **verificacao adicional:** corri o oracle do CLI do braco A 2x (o run completo
  e o `--unit`) e o `--unit` 2x em cores opostas. Barato e foi o que permitiu
  distinguir "o classifier engole" de "nada chega ao classifier". O que FALTA e'
  caro: uma medicao da visibilidade real do painel no arranque (nomeada abaixo).
- **checkboxes novas (mecanicas):**
  1. `py -3 _main/panel-exit3-oracle.py --unit` tem de dar rc=0 e
     `PANEL_ORACLE_SHELL=…/_prefix-under-test.py` rc=1 — parea RED/GREEN na mesma
     corrida.
  2. `grep -c "statuses=0" <log do run real>` tem de ser 0 num run com
     `--with-worker`: `statuses=0` e' a assinatura de um pump morto, nao de um
     worker calado.
  3. `grep -c "PANEL_SHOWN reason=hotkey" <log>` tem de ser 0 num run de medicao.
  4. `grep "ALERTA-JANELA" I:/!manager/state/progress/window-census.log` depois do
     run: nenhum pid da linha 1 do log do run.
- **review por outro subagente:** **sim-com-escopo** — `_arm_silence`/`start`
  (a classe do deadlock, para alguem procurar o mesmo padrao noutros sitios) e a
  frase do `AGENTS.md`; **nao** para os numeros renderizados, que sao saida de
  ficheiro e re-correm com um comando.
- **gate-doubt:**
  - *verde-de-verdade:* o `verdict: PASS` do oracle e' real: os dois bracos
    executaram na MESMA invocacao, o A afirma factos positivos
    (`captions=2`, `status--live`) que um gate vazio nao fabrica, e o B afirma
    `rc=3` lido do `BRIDGE_EXIT` da propria shell. O verde que eu NAO confio e' o
    primeiro `RED_RC=1`: era um `SyntaxError` meu, nao uma falha do classifier —
    so' o notei porque imprimi o log em vez de ler o codigo de saida. Corrida:
    `_main/panel-exit3-arm0-RED.log` (o log mau) vs o re-run depois do `py_compile`.
  - *falta-no-gate:* o oracle NAO verifica se o painel mostra a morte DURANTE
    varios ciclos de restart com o dono a olhar (so' um dump por braco), e nao
    verifica a VISIBILIDADE da janela. Cenario que atravessa o buraco: alguem
    troca o `pending_error` por um timeout, e o painel volta a parecer sao
    enquanto o worker morre — o dump continuaria verde se cair no instante certo.
  - *gate-melhor:* uma assercao mecanica para a retencao — correr o braco B com
    `--dump-dom-wait` DEPOIS de um restart completo e exigir que o texto ainda
    contenha `silent-device`/`exit 3`; e logar
    `PANEL_VISIBILITY_AT_STARTUP visible=<bool> hwnd=…` (instrumento que falta) e
    deixar RED se `visible=true` com `--no-hotkey` e sem `--show`. Input que tem
    de deixar RED: o run de hoje sem `--no-hotkey`.
- **confianca:** **alta** no deadlock (8/8 ciclos, causa linha-a-linha, o fix
  faz os statuses aparecerem: `statuses=9` no braco B) e no render dos dois
  bracos (ficheiros colados). **media** numa coisa: a visibilidade do painel no
  arranque (item 6) — o censo apanhou um `pythonw` visivel dentro do meu run e eu
  nao o atribuí.
- **nao verificado:**
  1. a visibilidade do painel no arranque do APP (o `hwnd` do censo nao tem
     titulo e o processo ja' morreu);
  2. `run.cmd` como wrapper batch (corri o entrypoint python que ele chama, com o
     mesmo argv; nao corri o `.cmd` porque o `--dump-dom` dele usa `python.exe` no
     console do harness — o mesmo caminho que ja' me deu uma janela visivel);
  3. o comportamento com audio DE FACTO roteado por muito tempo: o braco A so'
     prova que legendas chegam com um tom injetado durante ~30 s;
  4. **`AGENTS.md` e o `docs/model-specs/README.md` estao DESACTUALIZADOS** face a
     `worker/config.json` de hoje: o doc diz `"lang_id": 0` (=en-US) e
     `"use_vad": false`, e o ficheiro diz `"lang_id": "auto"` e `"use_vad": true`
     (`_comment_lang_id` atribui a mudanca `'os' -> 'auto'` a lane
     `SottoLangDefault`, 2026-10-06). Os meus runs apanharam a edicao a meio: dois
     ciclos impressos com `lang_id : 0 (en-US) source=config:id` e, mais tarde,
     `lang_id : 12 (pt-BR) source=config:os-locale`. **Nao toquei nessas linhas**
     (nao sao a minha tabela nem o meu contrato) — fica nomeado para quem a
     mudou fechar o doc.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoExit3Panel
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoExit3Panel.jsonl
- cache: read=23336960 write=0 hit=98.8075% (cache-read / input+cache-read); universe: 114 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoExit3Panel.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=110 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 114 of 114 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T06:38:32.050000+00:00 | break_items=3; WHEN=2026-10-06T06:40:21.836000+00:00 | break_items=2; WHEN=2026-10-06T06:45:30.687000+00:00 | break_items=2; WHEN=2026-10-06T06:55:25.811000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 112372 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoExit3Panel']; window: 2026-10-06T06:38:32.050000+00:00..2026-10-06T06:55:25.811000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791268712050 | session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=85; turn_id=1791268821836 | session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=170; turn_id=1791269130687 | session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=349; turn_id=1791269725811 (state=RESOLVED-BREAKS-OMP; population: 4 of 112372 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoExit3Panel']; window: 2026-10-06T06:38:32.050000+00:00..2026-10-06T06:55:25.811000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T06:57:07.266254+00:00
- usage rows: 114
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 281650
- output tokens: 110833
- cache-read tokens: 23336960
- cache-write tokens: 0
- hit ratio: 98.8075% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=110 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 114 of 114 matched usage rows
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 4 of 112372 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoExit3Panel']; window: 2026-10-06T06:38:32.050000+00:00..2026-10-06T06:55:25.811000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T06:38:32.050000+00:00; WHERE session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791268712050
  - break_items=3; WHEN=2026-10-06T06:40:21.836000+00:00; WHERE session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=85; turn_id=1791268821836
  - break_items=2; WHEN=2026-10-06T06:45:30.687000+00:00; WHERE session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=170; turn_id=1791269130687
  - break_items=2; WHEN=2026-10-06T06:55:25.811000+00:00; WHERE session_id=01a10fef-296e-7392-9fa0-12e14e663af3 provider=deepseek-flash model=deepseek-flash item_index=349; turn_id=1791269725811
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## 7. As duas linhas que provam o deadlock desfeito

Em NENHUM log anterior deste repo aparece a linha que o `start_worker()` imprime
DEPOIS de `bridge.start()` retornar. No run pos-fix ela aparece, nos dois bracos:

```
_main/panel-exit3-armA.log:23  WORKER_AUTOSTART=started reason=with-worker
_main/panel-exit3-armB.log:23  WORKER_AUTOSTART=started reason=with-worker
```

E o gate que ja' existia continua verde com a sonda estendida, nos dois bracos:

```
BRIDGE_GATE=GREEN hasPanelElement=true url=file:///H:/sotto/app/electron/panel.html panelSaidBridgeMissing=false
SHELL_EXIT rc=0 reason=dump-dom
```

Braco A, `statuses=7 captions=2`, com o audio do worker realmente presente
(`WORKER_STATS … nonzero_blocks=200 peak=0.273407`). Braco B, `statuses=9`,
`rc=3`, `SILENT-DEVICE … peak=0.000122 < floor=0.002 over 60 blocks`.

