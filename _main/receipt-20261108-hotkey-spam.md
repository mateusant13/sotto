# RECEIPT — Alt+C spammado: rajada coalescida, uma transicao por drain (2026-11-08)

**Owner, verbatim:** *"apertar alt c super rapido deixa o app travando pra caralho. deixa
completamente fluido. é pra abrir os paineis e qualquer outra coisa super rapido com o alt c
sendo spammed. sem travar."*

**Defeito medido (evidencia ja recolhida, `_main/webview-run.log`):** rajada do dono
03:30:57.5Z..03:31:02.6Z — 107 presses na vida, 17 com gap < 300 ms, minimo 0 ms. Cada pressao
corria a transicao inteira (`HOTKEY_TOGGLE` -> `STRIP_RECT_WIDTH` -> `WINDOW_GEOMETRY` ->
`PANEL_SURFACE` -> `PAINT_ACK_ARM` -> `PANEL_CONTENT` -> `PAINT_ACK` -> `PANEL_SHOWN`),
416-700 ms de um `HOTKEY_TOGGLE` ao seguinte, em FIFO: 5 presses = ~3 s de resize + troca de
documento WebView2. `WARN UI_THREAD_STALL begin-invoke not run in 0.25s fn=guarded_show` existe
nesse log.

## Mudanca

1. `app/webview/hotkey_gesture.py` — **novo `advance(visible, surface, presses=1)`**, PURA (sem
   I/O, sem log, sem relogio). Caminha `next_surface` N vezes sobre o estado medido e devolve o
   fim. O `surface` sobrevive ao hide (contrato do `hide_panel`), por isso escondido volta sempre
   ao `strip`.
2. `app/webview/sotto_webview.py`:
   - `__init__` ganha `_panel_presses = 0` e `_panel_press_lock = threading.Lock()`.
   - `_hotkey_dispatch('panels')` SOMA o contador sob o lock e poe **um token por pressao** na
     fila, na ordem de chegada (um `live` entre dois Alt+C nao perde o lugar).
   - `_hotkey_worker_loop` continua FIFO (nao mudou).
   - `_hotkey_resolve`, no primeiro token `panels`, **DRENA** o contador (`n, self._panel_presses
     = self._panel_presses, 0`) e aplica **uma** transicao para `hotkey_numbers().advance(alive,
     shown, n)`. O estado de partida e' o medido (`window_visible(self.hwnd)` +
     `surface_applied`), nunca cache. Token com contador a zero e' no-op com
     `HOTKEY_COALESCED skipped=1 presses=0 reason=already-drained`.
   - Log por drain: `HOTKEY_COALESCED presses=N from=<visible|hidden>/<surface|-> to=<...>
     steps=N transitions=<0|1>`; o `HOTKEY_TOGGLE` existente continua a sair quando ha
     transicao.
   - Sem sleep/debounce: o dreno acontece no token, portanto uma pressao sozinha nao paga nada
     (medido: transicao comeca 6 ms depois do despacho).
3. `_main/hotkey-spam-oracle.py` — **novo oraculo** que extrai por AST os corpos REAIS de
   `_hotkey_dispatch`/`_hotkey_worker_loop`/`_hotkey_resolve` e os conduz com fila real, worker
   real e um show/hide falso que dorme 400 ms (modelo da transicao medida). `--neg-arm` muta uma
   COPIA para FIFO (um passo por token) e exige A1/A5 RED.
4. Harnesses de oraculos existentes que chamavam `_hotkey_resolve('panels')` DIRECTAMENTE foram
   migrados para somar o contador como o despacho real: `_main/altc-gesture-oracle.py` e
   `_main/hotkey-live-toggle-oracle.py`. Ambos continuam GREEN (97/97 e 38/38).

**Nao tocado:** `app/panel/**`, `caption_overlay.py`, battery `.cmd`, pin do `AGENTS.md`
(Main e' o dono do wiring da bateria/pin).

## Numeros medidos (oraculo, transicao falsa = 400 ms)

| cenario | ANTES (FIFO, neg-arm) | DEPOIS (coalescido) |
|---|---|---|
| 6 presses numa rajada (< 50 ms), worker ainda sem vez | drains=6, skipped=0, **window_transitions=6**, wall=**2461.5 ms** | drains=**1** (presses=6), skipped=**5**, window_transitions=**0** (6 passos ≡ estado inicial), wall=**82.1 ms** (burst 18.5 ms; o resto e' o worker/settle) |
| 5 presses em 320 ms (transicao ja' a decorrer) | drains=5, **5 transicoes**, wall=**2051.6 ms** | drains=1+4, **2 transicoes** (strip -> panel), wall=**850-852 ms** |
| 1 pressao sozinha | — | dispatch 6.08 ms, transicao comeca 6.16 ms, total 463 ms (sem debounce) |
| 3 presses escondido | 3 transicoes (show strip, show panel, hide) | **0 transicoes**, `transitions=0`, skipped=2; a pressao seguinte volta a andar (1 transicao) |
| `live` entre dois `panels` | ordem ok, mas 2 transicoes | ordem `panels-applied, live, panels-skipped`, drains=['2'], 1 transicao |

Nota de honestidade aritmetica: 6 presses ≡ 0 (mod 3) no ciclo de 3 casas, logo o estado final e'
o inicial e o coalescedor nao move a janela: "uma transicao pesada" aqui e' **um unico drain
coalescido** (um `HOTKEY_COALESCED ... transitions=1`), nao um map/unmap. O neg-arm FIFO e' o
controle: no mesmo instrumento ele faz 6 drains e 6 map/unmaps (2461.5 ms).

## Verificacao exercitada

- `python -c "...g.advance(False,'',1), g.advance(False,'',3), g.advance(True,'strip',2)"` ->
  `(True, 'strip') (False, 'panel') (False, 'panel')` (hidden+1->strip, hidden+3->hidden,
  strip-visible+2->hidden).
- `python _main/hotkey-spam-oracle.py` -> **GREEN arms=19 pass=19 fail=0 (rc=0)**.
- `python _main/hotkey-spam-oracle.py --neg-arm` -> **NEG-ARM PASS**: copia FIFO com
  arms=19 pass=7 fail=12, A1_red=True A5_red=True.
- `python _main/altc-gesture-oracle.py` -> **GREEN 97/97**.
- `python _main/hotkey-live-toggle-oracle.py` -> **GREEN 38/38**.

## Falsification artifacts que ficam RED por desenho

`_main/_falsify/hotkey-spam-driver/driver.py` e `_main/_falsify-altc-probe.py` julgam o contrato
ANTIGO ("N presses = N flips"). A decisao do Main substitui-o por coalescencia; nao os editei
(sao evidencia da decisao anterior). Se a bateria os correr, passam a RED de proposito e precisam
de substituicao/decisao do Main.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: AltCSpamCoalescer
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['AltCSpamCoalescer']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['AltCSpamCoalescer']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T06:43:26.379433+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['AltCSpamCoalescer']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['AltCSpamCoalescer']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — faltou-me um protocolo de MIGRACAO DE HARNESSES quando se muda um
  contrato interno (o `_hotkey_resolve` deixou de ser "um token = um passo"). Descobri-o a ler
  oraculos existentes; devia ter começado por inventariar QUEM chama o corpo extraido antes de o
  mudar. Faria diferente: `grep` dos callers de `_hotkey_resolve`/`_hotkey_dispatch` como
  primeiro passo.
- **verificacao adicional** — a mais barata que aumentaria a confianca: correr a bateria real
  contra o processo vivo com uma rajada sintetica de 6 `WM_HOTKEY` e medir `UI_THREAD_STALL` /
  press->`PANEL_SHOWN`. Custo: lançar o app na sessao do dono (proibido nesta lane) e ler o log
  vivo; nao corrido.
- **checkboxes novas** — (1) a CLI de aceitacao (`advance`) como comando unico; (2) o oraculo
  `--neg-arm` a exigir A1/A5 RED — ambos implementados; (3) faltaria um assert ESTRUTURAL de que
  `_hotkey_dispatch` nao chama `show_strip/show_side/hide_panel` nem `sleep`/`Timer`, e um mutante
  que inline o show no despacho tem de deixar A3 RED.
- **review por outro subagente** — `sim-com-escopo concurrency do contador e o portao
  (`BurstQueue`) do A1, para provar que o braco nao passa por construcao`.
- **gate-doubt**
  - `verde-de-verdade:` o A1 e' verde com a fila PORTICADA (`BurstQueue`), que fixa o
    escalonamento "rajada entregue, worker sem vez": o verde e' real para o CODIGO, mas nao mede
    o escalonador do Windows. O controle de vacuidade e' o `--neg-arm`, que no MESMO portao
    devolve 6 drains / 6 transicoes / 2461.5 ms e deixa A1/A5 RED. A3 e A6 correm com fila SEM
    portao (escalonamento natural) e continuam verdes. O `window_transitions=0` do A1 nao e'
    falha escondida: 6 ≡ 0 (mod 3), declarado no proprio oraculo e no relatorio.
  - `falta-no-gate:` o oraculo NAO exercita o UI thread nem o WebView2 reais; a transicao e'
    `time.sleep(0.4)`. Uma mudanca futura que volte a fazer trabalho de UI dentro do
    `_hotkey_dispatch` (ou que torne `show_strip` sincrono no fio do hotkey) nao seria vista:
    A3 mede so' o inicio da transicao falsa. Cenario concreto: alguem move `show_strip` para o
    despacho "para poupar a fila" — todos os bracos continuam verdes porque a transicao falsa
    ainda comeca depressa.
  - `gate-melhor:` braco estrutural no oraculo: `_code(_hotkey_dispatch)` sem chamadas a
    `show_strip|show_side|hide_panel|time.sleep` e sem `Timer`; entrada que tem de o deixar RED:
    mutante com `self.show_strip('x')` dentro de `_hotkey_dispatch` (comando:
    `python _main/hotkey-spam-oracle.py --neg-arm` estendido com esse mutante).
- **confianca** — `alta` no caminho de codigo e nos bracos do oraculo (neg-arm controla
  vacuidade); `media` no numero de transicoes de uma rajada REAL, porque depende do
  escalonamento entre o fio do hotkey e o worker (A6 mede 2 para 5 presses em 320 ms, mas uma
  rajada de 500 ms pode dar 3).
- **nao verificado** — (a) o app vivo / teclado real; (b) a reducao real de `UI_THREAD_STALL`
  medida no processo do dono; (c) a bateria completa; (d) os artefactos `_falsify` antigos
  (esperados RED por desenho, nao corridos).
