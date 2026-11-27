# Recibo 2026-11-26 — a régua por passo vira híbrida (CPU onde há par) e o piso do RATIO vem de uma medição

## 1. O que a corrida #12 (20:44, 1 867,94 s) mediu

`BATTERY-VERDICT: RED - 3 step(s) failed` → `load-shedding=1 battery-budget=1 benchmark-gate=1`.

- `benchmark-gate` foi **cascata**: `e2e.battery_budget_gate_ms: command exited 1` — o comando do
  budget é o próprio oráculo, e ele estava vermelho. Nenhum defeito independente.
- `battery-budget`: `RED regua=PAREDE (sem cpu_s dos dois lados: baseline=0, corrida=203)`. A corrida
  #12 já tinha `cpu_s` em 203 passos; o baseline antigo não tinha nenhum, e a régua caía inteira para a
  parede — que dentro de `--cpu 40 --io very-low` mede o duty cycle da jaula.
- `load-shedding`: `arms=257 pass=255 fail=2`, e **solto dá 257/257 em 2,3 s**. Os dois arms vermelhos
  eram `loads=1` e `out=0` — `_settle()` junta o lote **em curso** e devolve `True` na hora quando o
  lote ainda **não começou** (`maybe_kick()` é assíncrono). O arm lia um instantâneo do escalonador,
  não o contrato.

## 2. As três correções

**(a) `load-shedding-oracle.py` ARM 10 — espera limitada PELO CONTRATO.**
`_settle` + re-`maybe_kick` num laço com prazo declarado (`JOIN_CAP_S = 15,0 s`), saindo quando
`eng2.loads >= 2` e `blocks_out >= blocks_in`; estourar o prazo **continua a reprovar** pelo que o
contrato não fez (prazo não vira isenção). Duas corridas soltas: 257/257 cada. EOL CRLF preservado
(3 117 CRLF / 0 LF nu).

**(b) `battery-budget-oracle.py` — régua híbrida por passo.**
Cada passo é julgado por **CPU quando há número dos dois lados**, por **parede no resto**, e a linha diz
quantos ficaram em cada régua com o token `regua=CPU` / `regua=PAREDE` (as arms C1–C4 leem esse token;
um `regua=CPU` num caso sem par seria o porteiro a dizer que mediu o que não mediu). O total julga a
**interseção do CPU** quando existe e publica a parede da corrida como contexto. Removido o laço de
parede duplicado que a primeira versão deixava correr depois (as razões saíam duas vezes).

Rebaseline com a razão gravada (`notes.rebase`, que antes só entrava com mudança de política):

```
python _main/battery-budget-oracle.py --baseline --policy cap40 \
  --accept-growth "incomplete-word,input-path,load-shedding,panel-themes,red-as-expected-boot-profile,red-as-expected-live-ack,red-as-expected-measurement-flags,red-as-expected-panel-header-oracle,red-as-expected-panel-history-clip,red-as-expected-panel-themes,red-as-expected-seam-coverage,seam-coverage,red-as-expected-history-write,red-as-expected-load-shedding,red-as-expected-nemotron-weights" \
  --rebase-policy "regua por passo passa a CPU onde ha' par nos dois lados ..."
```

Depois: `BATTERY-BUDGET VERDICT RATCHET-OK -- steps=588 total=2700.3s`, **41 ARM ok, 0 falhas**,
`total_cpu_s 399.26` sobre 214 passos com par.

## 3. `paint-cost-oracle.py` — o piso do RATIO, medido

|corrida|hit p95|miss p50|RATIO|
|---|---|---|---|
|solta, cache a servir|0,110 ms|8,36 ms|**76,1×** (re-medido hoje: 52,4 / 78,5 / 79,3×)|
|jaula `--cpu 40` (corrida #11)|15,164 ms|—|**14,1×**|
|mutante `lookup-off` (constrói e nunca serve)|8,44 ms|6,42 ms|**0,76×**|

`HIT_RATIO_MIN = 20.0 → 8.0`: acima do mutante com folga de 10×, abaixo da corrida capada com folga de
1,75×. O limite absoluto de 2,0 ms continua julgado **só quando a corrida não está capada**.

**O buraco que isto fechou**: o mutante `lookup-off` era apanhado apenas pelo limite **absoluto**, e numa
corrida capada esse limite responde `CANNOT-MEASURE` — ou seja, sob a jaula um cache que nunca serve
passava. O braço negativo agora mede o **RATIO do próprio mutante** (`own_ratio`): `miss_p50 / hit_p95`
do mesmo módulo mutado, invariante ao tecto de CPU. `python _main/paint-cost-oracle.py --neg-arm` →
`RATIO proprio=0.76x < 8.0x`, `NEG-ARM: PASS`, rc 1 (mutante apanhado = rc 1, convenção da casa).

## 4. Estado

- Positivo: `PAINT-COST PASS` rc 0, `A2 PASS ... RATIO miss/hit=52.4x (portao >=8x)`.
- `battery-budget`: `RATCHET-OK` rc 0, 41 arms.
- `load-shedding`: 257/257 solto (o vermelho só aparecia na jaula; a corrida #13 é quem o prova lá).
- Corrida #13 lançada sobre estas três mudanças; nada pesado corre ao lado dela.
