# A régua do custo por passo: CPU, porque a parede dentro da jaula mede a jaula

Date: 2026-11-26. Tree `H:/sotto`.

## O que a corrida #11 mediu, e por que a resposta não era "mais rápido"

Run #11 (`_main/_audit-verify/_battery-run-20261126-180900.log`, 1 988,7 s, `RED - 3`):

```
failed : paint-cost=1 battery-budget=1 benchmark-gate=1
RED total 2796.0s acima do tecto 2481.4s (baseline 2363.2s x 1.05)
RED passo(s) que engordaram alem do ratchet:
    red-as-expected-audio-back-detector 12.1s -> 47.0s
    red-as-expected-history-write       4.3s -> 36.0s
    red-as-expected-load-shedding      39.6s -> 77.1s
    red-as-expected-nemotron-weights    2.3s -> 67.4s
```

Duas causas distintas, ambas agora nomeadas com número:

**1. O tecto do total julgava populações diferentes.** O baseline de 2026-11-12 tem 452 passos; a
corrida tem 588. Somados os 452 passos COMUNS, a corrida medida deu **2 119,4 s contra 2 363,2 s do
baseline — 0,90×, mais RÁPIDA** — e os 136 passos novos somam 677,4 s. O RED era todo da população
nova. `_intersection_total` passa a julgar os passos que o baseline mediu e publica os novos
separado; a arm A12 prova que o tecto ainda dispara quando os passos comuns engordam 8 % cada.

**2. A parede dentro da jaula é o duty cycle da jaula, não o custo do passo.** Medido nesta máquina,
mesmo comando, mesmo trabalho:

| condição | parede |
|---|---|
| solto | 0,36 s |
| `watcher run --cpu 40 --` | 7,24 s |
| `watcher run --cpu 40 --io very-low --` | **62,12 s** |

170× com o mesmo CPU. Uma régua de parede sobre esse número mede o escalonador — a mesma lição do
`paint-cost` (15,164 ms caged vs 0,110 ms solto), agora por passo.

## A cura: o custo por passo passa a ser CPU, medida no único sítio que já corre o filho

- `_main/step-deadline.py` — `_CpuSampler` amostra a ÁRVORE do filho a 50 ms e guarda o máximo
  (`psutil`). `run_with_deadline(..., cpu_box=...)` devolve-o por um dicionário opcional, logo as nove
  arms do selftest continuam a receber o `(rc, killed)` de sempre.
- `_main/_stepcache.py` — a linha do passo ganha `cpu_s` quando há número. **`None` nunca é zero**:
  um zero constante seria o verde que não pode falhar (e foi: `os.times().children_user` devolve 0.0
  sempre nesta plataforma, e `resource` não existe no Windows).
- `_main/battery-budget-oracle.py` — `read_steps` lê `cpu_s`, `measure_cpu` soma-o por passo, e o
  `judge` usa a régua de **CPU** quando baseline e corrida a têm os dois (publicando quantos passos
  ficaram sem par), caindo para a **parede** com `regua=PAREDE` impresso quando não. O `--baseline`
  grava `total_cpu_s` e `per_step_cpu` ao lado dos campos de parede.

Conhecido-respondido do amostrador (o mesmo código em `benchmark_history._run`): ciclo de CPU de
8 M iterações = **344 ms de cpu_s para 390 ms de parede**; `time.sleep(1.0)` = **62 ms para 1 068 ms**;
gate real = **891 ms para 1 451 ms**. Um filho mais curto do que uma amostra devolve `None`.

## Verificação

`python _main/step-deadline.py --selftest` → `PASS (9 arms)` (o CPU não muda nenhuma das anteriores).
Cadeia ponta a ponta, um passo real gravado com `--record-*` num estado temporário:

```
elapsed_s 0.556  cpu_s 0.359  policy cap40
```

`python -m py_compile` nos três ficheiros. O resto é a corrida: #12 recolhe `cpu_s` para os passos que
executam, o baseline é re-medido com `--rebase-policy` a dizer a troca de unidade, e #13 julga.
