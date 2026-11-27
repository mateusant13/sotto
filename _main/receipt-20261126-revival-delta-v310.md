# Recibo 2026-11-26 — o DELTA v3.1.0 da `project-revival`, aplicado com números medidos

Pedido: a DM `w12:p1N` (v3.1.0 DELTA, `G:\Temp\revival-delta-v310.md`) manda aplicar **só o delta** —
não re-executar a v3.0.1. Seis itens, cada um com a sua prova.

## 1. `benchmark_history.py` v3.1.0 (best-of-3, piso de ruído 250 ms, `host_cpu_pct`)

- O script instalado **é** a v3.1.0: `--selftest` → `PASS (5 arms)`; aceita `--samples N`, grava
  `host_cpu_pct` por linha e aplica o piso de 250 ms.
- **O meu fork de `cpu_ms` foi engolido pelo update** (19:42) — a lição é a da casa: o script canónico da
  frota é o dono do instrumento. `benchmarks/budgets.json` foi reconciliado de volta para `wall_ms` +
  `"samples": 3`; a sonda de CPU que eu tinha escrito não virou um segundo dono, ficou no recibo
  `_main/receipt-20261126-scheduler-arms-and-cpu-metric.md` como evidência.
- `run --repo . --label probe-final --samples 3` → `passed true`, `failure_count 0`,
  `host_cpu_pct 57.1`, `e2e.battery_budget_gate_ms 134,31 ms` (amostras 134,31 / 135,82 / 141,66,
  tecto 20 000).

## 2. `slider_scorecard.py set-many` nos 8 sliders

`set-many --repo . --evidence "<medido>"` → `ok true`, 8 atualizados, **overall 73,4**.

|slider|baseline|agora|o número que o justifica|
|---|---|---|---|
|delivery_balance|62|72|`landing_ratio_check` HEALTHY, 0 doc-only, max_doc_streak 2, small_slices 90 %; ainda `product_ratio 32,5 %` e 203 `_main/*.py` sem referência|
|observability|78|84|`stall-heartbeat` + `stall-attr` (HOST / SHELL-ONLY / HOST-IDLE), `why=` e `regua=` em cada portão, `KILL-SAMPLE` nomeado, `caged: ON/OFF` no sumário|
|inner_loop_speed|55|78|`loop_friction_audit measure --gate` → `PASS []`; pior verificação **1,706 s** (browser_live_wait) contra barra de 15 s; censo do loop 0,119 s|
|architecture_coherence|70|45|Codeintel `balance_score 37`, `product_ratio_pct 32,5` — o mapa existe mas a dívida é real|
|metric_gate_coverage|35|72|5 tectos em `budgets.json` com blast-radius, `feature_map_sync --gate` no gate do projeto|
|harness_falsifiers|74|86|bateria: 610 passos, 316 gate, **258 expect-red**; arms por oráculo: battery-budget 41, load-shedding 257, yt-capture-replay 43 (+7 mutantes), paint-cost 2 mutantes|
|reversibility_safety|80|82|worktrees por lane, recibos em cada correção, 29 `PermissionError` honrados no reclaim, nada do dono tocado|
|autonomy_end_to_end|64|68|13 classes de teste correm sem o dono; o playback do YouTube é `CANNOT-MEASURE reason=youtube-login-required` — é um HOLE nomeado, não um verde|

## 3. `loop_friction_audit measure --gate`

`verdict PASS`, `failures []`, seis linhas `VERIFIED`: rust_compile_loop 0,124 s · youtube_live_dep
0,306 · browser_live_wait 1,706 · paid_or_live_api 0,104 · inner_test_loop 0,119 · owner_dependency
0,288. A `rust_compile_loop` **era** a fricção: o `verify_cmd` dela fazia `rglob('*')` sobre 8,87 GiB em
15,068 s contra o próprio alvo de 8,0 s; passou a um censo limitado de 3 fontes declaradas.

## 4. `sub_orchestrator.py` auto-adaptive

Presente e com `--max-parallel` adaptativo; nada a corrigir. Não foi usado para trabalho que uma lane
resolve sozinha (a lei do custo: fan-out não é ornamento).

## 5. `codeintel health` / `trace`

`health . --panorama --deadline 10` em 1,26 s; `trace run app/webview/youtube_clock.py` →
`live-trace verdict: green (exit 0)`, 1 de 1 frames do sujeito.

## 6. `ACC-01..ACC-05` e o DM final

Fechados em `revival/GOAL.json` com o recibo em cada linha; `MILESTONES.json` P0-10 `DONE`; o **único**
`REVIVAL-COMPLETE: sotto` foi para `w12:p1N` (a Gravador `w1D:p1` não é pane minha — conferido na
roster).

## O que este delta NÃO fez

- Não re-executou a v3.0.1 inteira: `revival_bootstrap --cold` não voltou a correr, `harness/angles.tsv`
  e os 610 passos da bateria não foram tocados.
- Não subiu nenhum tecto para o vermelho passar: o único rebaseline do dia está justificado em
  `notes.rebase` por uma mudança de **unidade** (parede → CPU, 0,36 s contra 62,12 s para o mesmo
  comando), e os 15 passos aceites por `--accept-growth` estão nomeados um a um.

## 7. `benchmark_history.py --selftest` media o escalonador (achado pela corrida #17)

`benchmark-selftest=1` na #17 com `AssertionError` na linha 493 do script **canónico**
(`C:\Users\Administrador\.agents\skills\project-revival\scripts\benchmark_history.py`) e
`PASS (5 arms)` solto na mesma árvore. A causa é o fixture do próprio `_selftest`: a métrica
`basic.fast_wall` (`samples: 2`, `python -c print('ok')`, `ceiling: 5000`) é comparada entre `baseline`
e `after` com tolerância de 25 % e piso de ruído de **250 ms**, e o mesmo spawn custa ~60 ms solto e
~1,5 s capado — o `after` "regredia" 20× sem nada ter degradado.

Correção primeiro no script canónico (não num fork): `wall_ms_noise_floor_ms` do fixture `250.0 →
60000.0`, com o porquê no ficheiro. Provado nas duas direções: solto `PASS (5 arms)` rc 0 (3,5–4,1 s);
dentro de `python -m watcher run --cpu 40 --io very-low` `PASS (5 arms)` rc 0 (total 6,7 s, wrapper cpu
0,30 s); `ops 80` continua a reprovar (rc 1) e `ops 30` a passar.

**A versão que fica é a do dono do script, e é melhor do que a minha** (medido 2026-11-26 22:14,
depois do DM): o watcher trocou o meu piso global por um piso **por métrica**
(`"min_delta": 60000.0` dentro de `basic.fast_wall`, com o comentário a citar
`dm-58532a83aadaca0abf6c`), que é mais estreito do que o meu -- só a métrica medida pelo relógio fica
isenta, o resto do fixture continua com o piso de 250 ms. O ficheiro canónico é dele; não mantenho
variante minha.

**Entrega ao dono do script**: `herdr agent list` mostrou que **`w12:p1N` já não existe** na roster (é
recusa, não tentativa — o `herdr-dm.py` devolveu `delivery: unsent`), pelo que o DM foi para o pane vivo
do watcher `w12:p1H`: `delivery: unproven` → `submitted: null` → `herdr agent send-keys w12:p1H Enter`
→ o pane passou a `Inspecting the repo copy of benchmark_history`. Registo:
`I:\!watcher\state\herdr-inbox\dm-58532a83aadaca0abf6c.md`.
