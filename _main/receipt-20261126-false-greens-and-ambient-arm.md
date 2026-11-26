# Recibo — 2026-11-26: dois verdes falsos, uma arm ambiente, e o orçamento que media o caso

Tudo o que está aqui foi medido nesta máquina, nesta sessão. Cada linha nomeia o comando e o
número. O que **não** foi medido está dito como tal.

## 1. Dois passos da bateria que não podiam ficar vermelhos

O mecanismo, lido e não suposto: `_main/_audit-verify-all.cmd:4860-4874` corre cada passo por
`_main/step-deadline.py` e guarda `STEP_RC=!ERRORLEVEL!`; `:record` (`.cmd:4908-4922`) trata
`rc=0` como verde **sem ler o log**. Logo o rc do instrumento É o portão.

|ficheiro|antes|depois|
|---|---|---|
|`_main/_review-f1f3.py:244-247`|imprimia `PART A/B GREEN\|RED`, escrevia o log e caía no fim → **rc 0 sempre**|`sys.exit(0 if (a_ok and b_ok) else 1)`|
|`_main/_review-tapstop.py:90-111`|imprimia `VERDICT: UPHELD\|INCONSISTENT\|REFUTED\|held` e caía no fim → **rc 0 sempre**|`raise SystemExit(0 if not after else 1)`|

Duas direcções, medidas:

- f1f3 **vermelho**: com a expectativa antiga (`--probe-v2 3` exigia `starts=True`) deu
  `PART A (F1 rule): RED`, rc 1. A expectativa estava errada — `--probe-v2` está em
  `MEASUREMENT_FLAGS` desde 2026-11-12 (`app/webview/sotto_webview.py:13854`, portão
  `_main/measurement-flags-oracle.py`), e a docstring de `_worker_autostart_reason` diz que
  medição não arranca worker. Corrigida a expectativa → `PART A/B: GREEN`, rc 0.
- tapstop **verde**: `VERDICT: UPHELD`, rc 0.
- O braço vermelho do rc novo, portanto, é o próprio histórico: antes do `sys.exit` o mesmo
  RED saía 0.

## 2. `app-target-oracle`: a arm que media a máquina

`arm b` enumera processos REAIS (`EnumProcesses` + árvore de pais). Na corrida caged #9, com a
minha própria sessão a correr, `python.exe` aparece legitimamente como raiz de árvore e a arm b
ficou vermelha por oito linhas `candidate ... is a tree ROOT` — e como o meio dos mutantes exige
"exatamente UMA arm vermelha", o `M3 run.cmd default back` foi **acusado de sobreviver sem ter
sobrevivido**: `NEG-ARM FAIL: os mutantes sobreviveram (['M3 run.cmd default back'])`.

Cura: `ENV_SENSITIVE = frozenset({'b'})`. A arm continua a correr e a imprimir
(`<-- ENV-SENSITIVE, not counted`); não vota no veredicto dos mutantes.

Medido: standalone `NEG-ARM PASS: 4 de 4 mutante(s) apanhado(s) pela SUA arm`, rc 1, 9,6 s.

## 3. `nemotron-preload-oracle`: "child startup" media o caso inteiro

`startup_s = now - case_spawn_s` era calculado depois do preload, da activação e do dreno, então
o orçamento `min(60, max(15, 4*startup))` escalava com o tempo do CASO, não do filho. Medido
agora, com o primeiro `capture-started` por nome (`status_times`):

    NEG-CHILD eof budget=15.0s (child startup measured 0.38s)
    NEG-CHILD eof budget=15.0s (child startup measured 0.50s)
    NEG-ARM: PASS -- 17/17 focused lifecycle mutations caught     rc 1   78 s

Fora da jaula 76,5 s; **caged 82 s** (`launched pid cpu 49.75s`).

O `rc=124` da corrida #9 **não** era deste instrumento: 82 s medidos contra um prazo de 240 s. A
#9 corria em paralelo com três scouts e um reclaim de 9,81 GB — a contenção era minha. A regra que
fica: nada de trabalho pesado concorrente com a bateria.

## 4. `dm-triage-oracle` era `new-unwired`

`battery-wiring` recusou-o (`new-unwired`, sem passo e sem licença no baseline) — um instrumento
que nunca corre não é instrumento. Par novo na bateria, guardado por `if exist`:

    dm-triage                 positivo  4,0 s
    red-as-expected-dm-triage  negativo  1,0 s   NEG-ARM: PASS -- 3 caught, 0 missed of 3

## 5. Seis passos da `project-revival` na bateria

`feature-map-gate`, `benchmark-gate`, `friction-gate` e o `--selftest` de cada um. O selftest É o
braço vermelho: prova lá dentro que um repo regredido devolve rc != 0. Custo medido fora da jaula:
1,8 s / 2,6 s / 6,4 s. Cada par sob `if exist` — máquina sem a skill publica `:record ... MISSING`.

## 6. Pin e portões

|o quê|antes|depois|
|---|---|---|
|`_main/_audit-verify-all.cmd`|448 809 B / 5 115 CRLF|**452 321 B / 5 155 CRLF** / 0 bare LF|
|sha256|`EF7ED87D…C473E`|`DA5EF87783A4D05A0E7142E2A8929BBF10345FEE1B2D71255C838740737A6266`|
|`call :step` / `call :expectred`|604 / 440|612 / 442|

`python _main/agents-md-pins-oracle.py` → `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.
`python _main/battery-launch.py --verify` → `VERIFY: PASS` (pins, wiring, pairing, class,
undefined-names).

## 7. O que NÃO foi medido

- A corrida completa #9 foi morta pelo **meu** cap de cliente (3500 s) aos 530/602 passos: um
  aborto não é veredicto e não se cita como verde.
- `red-as-expected-app-target` e `red-as-expected-nemotron-preload` não foram ainda vistos verdes
  **dentro** de uma corrida completa; a #10 corre para isso.
- O processo do dono (`pythonw.exe(53752)` shell, `python.exe(73436)` sidecar) é anterior a todas
  as correcções desta sessão: `fixed, NOT verified` até ele reiniciar.
