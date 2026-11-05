# Recibo — prazo por passo e tecto da corrida (2026-11-05)

**Ordem do dono, verbatim:** *"por que é completamente BURRO voce levar mais que um minuto pra rodar
COISAS JA GARANTIDAS EM VARIOS LUGARES DA BATERIA"* e *"QUALQUER TESTE EXISTENTE OU QUE SERÁ
IMPLEMENTADO, DEVE SER IMPLEMENTADO DESSE JEITO PRA MENOR DESPERDÍCIO DE TEMPO E QUALIDADE MÁXIMA"*.

## 1. O que estava medido antes de existir mecanismo

Fonte: `_cache\battery-steps.json`, 320 passos registados, lido em 2026-11-05.

| corte | n | segundos | fatia |
|---|---|---|---|
| < 0,3 s | 56 | 12,1 | 0,2 % |
| 0,3–1 s | 110 | 61,2 | 1,1 % |
| 1–5 s | 88 | 204,5 | 3,5 % |
| 5–30 s | 46 | 535,5 | 9,2 % |
| >= 30 s | 20 | 4 987,9 | **86,0 %** |
| **total** | **320** | **5 801,2 s (96,7 min)** | |

O pior passo: `panel-hidden-at-startup-oracle` **3 781,6 s (63 min)** = **65 %** de tudo. Segundo:
`youtube-cdp-boot-oracle` **21,6 min** (medido na corrida de 13:20:48, morta por mim depois).
Os 254 passos abaixo de 5 s somam **277,8 s (4,8 %)** — o custo NÃO estava nas provas baratas.

Consequência medida da corrida morta: `_main\_audit-verify\_battery-summary.txt` continuou a ser o da
corrida anterior e foi lido como o veredicto de agora (dois `steps=` diferentes, um ficheiro).

## 2. Os dois mecanismos

### 2.1 `_main\step-deadline.py` — prazo por passo

- Ligado em `:step_run`: `python _main\step-deadline.py --seconds %SOTTO_STEP_DEADLINE_S% -- !S_CMD!`
  com piso de casa `SOTTO_STEP_DEADLINE_S=240` e `SOTTO_STEP_NAME=!S_NAME!`.
- No corte: **JOB OBJECT** com `KILL_ON_JOB_CLOSE`, `TerminateJobObject`, rc **124**, e a linha
  `STEP-DEADLINE exceeded step=<nome> seconds=<N> killed=<n> job=yes` no log do passo.
- O filho **herda o nosso stdout** — o log da bateria continua a ser a evidência.
- Preço medido: **95 ms por passo executado** (`python -c pass` 75 ms; pelo wrapper 170 ms), ~24 s
  numa corrida inteira.

**Selftest (5 arms, todos verdes):**
`A1` filho rápido rc=3 intacto · `A2` prazo de 1,5 s → rc=124, `ainda-vivos=0` · `A3` neto morto com o
pai (`neto_escreveu=false`) · `A4` rc=1 do filho a tempo não vira 124 · `A5` **um processo ALHEIO
sobrevive** ao corte.

**Um defeito meu, medido e corrigido:** a primeira versão matava por Caminhada de árvore
(`ppid→filhos` numa fotografia global). Medido: um corte de 2 s matou **dois `cargo.exe`** de outra
lane — um `conhost.exe` partilhado entrega como "filhos" processos que o instrumento nunca largou.
A cura é o job object; o braço `A5` é o que impede o regresso. E o `--neg-arm` (muta `job_terminate`
numa cópia) devolve **rc=1** com `A2` FAIL.

### 2.2 `_main\battery-budget-oracle.py` — tecto da corrida, como ratchet

- Baseline `_main\battery-budget-baseline.json`: `total_s=5801.2`, `steps=320`,
  `over_deadline=[panel-hidden-at-startup-oracle]`, `target_s=60`.
- Veredicto: total > baseline × **1,05** → RED; passo novo >= 240 s sem dívida declarada → RED;
  senão `RATCHET-OK` **com o gap impresso** — hoje
  `BATTERY-BUDGET VERDICT RATCHET-OK -- steps=320 total=5801.2s TARGET NOT MET (gap 5741.2s de 60s)`.
  Um `PASS` ao lado de 5 741 s de gap seria o verde que não mede nada, e por isso a palavra é
  `RATCHET-OK` e a distância é obrigatória.
- `--neg-arm` muta a **LEITURA** (infla o pior passo 10×) e exige o RED do **mesmo `judge`** —
  medido `caught`, rc=1.
- O par corre no **fim** da lista, imediatamente antes do sumário: o passo lê
  `_cache\battery-steps.json`, que a corrida escreve passo a passo; em qualquer outro sítio mediria
  "a corrida até aqui", isto é, um número menor do que o verdadeiro.

## 3. Onde a regra vive, para não morrer com a sessão

- `AGENTS.md` § **A LEI DOS TESTES** (ordem do dono, 2026-11-05): as seis propriedades, o mecanismo
  e o **DEVER DE TRANSPORTE** (toda mudança que altere como o trabalho se faz escreve a regra aqui,
  no mesmo commit).
- `docs/bateria-e-portoes.md` § **4-a**: a forma longa, com os números.
- Skills globais: `extreme-optimization-audit` **1.3.0** (três cópias byte-idênticas, 60 007 B,
  sha `4c46ccffda4f3956…`) com **L12-bis** (test economy), **L12-ter** (o dever de transporte) e os
  detectores **D45–D52**; `task-resolver` (três cópias) com `## Test economy and the carry-forward
  duty`.

## 4. Pins

`_main\_audit-verify-all.cmd` = **245095 B**, **3022 CRLF** / 0 bare LF,
sha256 `B788F58E3ED2C3C78DF6517D73244FC6FEEA5A48D65434EE139055C95DBC9677`
(`_main\agents-md-pins-oracle.py` PASS; `claims-date-oracle` PASS; `battery-wiring-oracle` PASS;
`battery-class-oracle` PASS).

## 5. O que este recibo NÃO prova

O `--selftest` e o `--neg-arm` provam o detector; a linha do `:step_run` foi provada sob `cmd` num
harness com a mesma forma (filho rápido rc=0 com o log dele; filho de 30 s → rc=124 + linha no log).
Uma corrida completa do `.cmd` com o wrapper é evidência de outra ordem e está registada no sumário
dela, não aqui.
