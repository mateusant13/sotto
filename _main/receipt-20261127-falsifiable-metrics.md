# Recibo — as métricas voltaram a saber ficar vermelhas (2026-11-27)

**Defeito medido:** `benchmark_history.py run --gate --verify-red` passou a responder
`CANNOT-FALSIFY (parse_mode='wall_ms' has no deterministic perturbed answer)` para **as cinco** métricas de
tempo, no mesmo dia em que a mesma corrida imprimiu `5/5 PASS` executando o `red_arm_cmd`. O rail
`metric_budgets` do `revival_verify` não passa `--verify-red`, logo o verde do rail escondia o buraco: um
red arm declarado e nunca verificado.

## A cura, e ela é do instrumento

`_perturbed_answer` (I:/!watcher/scripts/benchmark_history.py) constrói agora uma resposta má para cada
modo de leitura, e a resposta má é julgada **pelo mesmo** `_extract_value`/`_meets_ceiling` da leitura real:

|modo|perturbação|porquê|
|---|---|---|
|`wall_ms`|devolve `ceiling*2` como tempo medido|o tempo não vem de um texto; vem do argumento de fallback|
|`json_key`|`{chave: ceiling*2}` (ou `1` quando a ceiling é 0)|`ceiling*2` de 0 é 0, e 0 passava a própria ceiling|
|`regex`|um candidato construído do PRÓPRIO padrão e re-parseado por ele|um candidato que o padrão não casa é recusado, nunca inventa um PASS|

Um caso que o tecto não consegue violar continua a responder `FALSE-GREEN` em vez de passar.

## As duas metades medidas

- `--verify-red` sobre as 6 métricas do repo: **`rc=0`, `failures []`, `red_arms_verified 6/6`** —
  `battery 40000>20000`, `feature_map 30000>15000`, `tooling 60000>30000`, `yt_capture 16000>8000`,
  `yt_paint 33.334>16.667` (regex), `undefined_names 1>0`.
- `--selftest`: **5 → 9 arms**, `{"selftest": "PASS", "arms": 9}`.

## O segundo defeito que a sonda encontrou

O `--selftest` do instrumento canónico estava **vermelho** antes de eu lhe tocar: a fixture do `wall_ms`
declarava `min_delta: 60000`, logo respondia `CANNOT-MEASURE` em toda a corrida e depois `NO-REFERENCE` (um
piso de ruído ≥ a própria referência não decide). A fixture passou a julgar com `compare: "ceiling"` e sem
piso, porque o arm existe para provar **parsing e tecto**, não um delta contra o arranque de um processo.

## O que isto não resolve

- `e2e.yt_paint_worst_ms` mede 12,1 ms contra um tecto de 16,667 ms; a folga é do produto, não do gate.
- O `--verify-red` do rail continua a não ser chamado pelo `revival_verify`: quem quiser a prova corre o
  comando acima. Um passo de bateria com este par é a próxima melhoria do rail, não deste recibo.
