# RECIBO — a rodada dos INSTRUMENTOS (2026-11-12)

Duas curas, as duas nascidas de veredictos MEDIDOS na corrida inteira
(`_main/_audit-verify/full-run-20261112b.log`, 492 passos, `BATTERY-VERDICT: RED - 34 step(s) failed`).
Nenhum numero abaixo foi copiado de log velho: cada linha traz o comando que a produziu.

## 1. `launch-as-token` — o instrumento que MORRIA quando nao havia fonte `high`

**O que aconteceu.** O passo estava declarado `:record` (espera `rc=0`). Medido:

```
$ python _main/launch-as-token.py --selftest
SELFTEST SKIP -- nenhum processo fonte abrivel nesta sessao (nao e' um passe)
rc=1
```

O texto do proprio instrumento diz "nao e' um passe" e o codigo devolvia 1 — e a bateria lia
`rc=1` num passo registado como `:record`, o que conta como FALHA da corrida. A causa e' honesta:
o `--selftest` precisa de um processo `high` nesta sessao para EMPRESTAR o token, e num momento em
que nenhum `explorer.exe`/`shell` `high` estava abrivel nao ha o que medir. Quando ha' fonte, o
mesmo comando verifica de facto:

```
$ python _main/launch-as-token.py --selftest
SELFTEST PASS -- fonte pid=13636 (HIGH), filho pid=49560 executou, integridade=S-1-16-12288 (HIGH)
```

**A cura (duas metades, e a segunda e' a que impede o verde falso).**
- o ramo sem fonte imprime `VERDICT: SKIPPED reason=no-high-source` junto do texto antigo e sai
  `rc=0` — um skip honesto, nunca um passe;
- o passo passa a `:step` + `:skipped` (a forma que `shell-thread-budget` ja' usava): com
  `SELFTEST PASS` no log e' um GATE; com `VERDICT: SKIPPED` e' contado em `skipped=`, NAMED no
  sumario. O par e' obrigatorio porque `battery-record-pairing` recusa um `:skipped` sem o `:step`
  do mesmo nome (medido: `R3-registo-orfao launch-as-token linha 3392`).

**Verificado.** `python _main/battery-record-pairing-oracle.py` →
`passos: 497 | nomes com registo: 497 | achados: 0`, `VERDICT: PASS`.
`python _main/battery-class-oracle.py` → `BATTERY-CLASS VERDICT PASS -- arms=3 fail=0`.

## 2. `panel-hidden-at-startup-oracle` — 242,77 s contra um tecto de 240 s

**O que aconteceu.** Na mesma corrida, o passo mais caro foi

```
panel-hidden-at-startup-oracle                 242.77 s
```

e o `per-step` do sumario registou `panel-hidden-at-startup-oracle=124` — o `rc=124` do
`_main/step-deadline.py`, ou seja o JOB do passo foi cortado pelo tecto da casa
(`SOTTO_STEP_DEADLINE_S=240`). O passo nao estava preso: ele paga QUATRO processos filhos (um por
mutante, cada um num interpretador proprio — a decisao esta' escrita no ficheiro e e' correta: um
mutante que suja o estado do pai mediria o pai). Sob contenda, o mesmo passo ja' mediu **55,7 s**
sozinho e **219,1 s** dentro de uma corrida carregada: a variancia e' de 4x, e um numero UNICO por
corrida nao separa "passo preso" de "passo caro".

**A cura — o tecto POR PASSO, e nao um numero maior para toda a corrida.**
`_main/step-deadline.py` ganhou `resolve_seconds()`: a variavel `SOTTO_STEP_OVERRIDE_S` vence o
`--seconds` da corrida, e a resolucao vive no UNICO sitio que corta (`run_with_deadline`), nao no
`main` — o `--selftest` chama `run_with_deadline` directamente, logo um override aplicado no `main`
seria um no-op silencioso. A linha do passo declara o proprio tecto e limpa a variavel no fim:

```
set "SOTTO_STEP_OVERRIDE_S=420"
  call :step panel-hidden-at-startup-oracle 0 ... python _main\panel-hidden-at-startup-oracle.py
  call :record panel-hidden-at-startup-oracle !STEP_RC!
set "SOTTO_STEP_OVERRIDE_S="
```

420 s = 1,7x o valor medido DENTRO da corrida (242,77 s) e e' o dobro do pior valor legitimo
anterior (219,1 s). O tecto da propria corrida continua a ser 240 s para todos os outros ~490 passos.

**O braco que prova que a variavel nao e' decorativa.** O `--selftest` do `step-deadline` passou de
6 para 7 arms; a A7 poe `SOTTO_STEP_OVERRIDE_S=1.5` e pede `--seconds 120` a um filho que dorme 30 s:

```
A7 override de 1,5 s contra --seconds 120: rc=124 killed=2 -> PASS
STEP-DEADLINE SELFTEST: PASS (7 arms)   (rc=0)
```

A primeira versao desta arm dava `rc=0 killed=0 -> FAIL` — e o FAIL era do INSTRUMENTO, nao da cura:
a leitura do override estava no `main` e a arm chama `run_with_deadline` directamente. E' o mesmo
defeito que a casa ja' pagou no `cost-watchdog` ("um instrumento que devolve o valor por omissao e'
indistinguivel de nao houve nada").

**Extremo a extremo, pela linha que a bateria executa:**

```
$ SOTTO_STEP_OVERRIDE_S=2  python _main/step-deadline.py --seconds 240 -- python -c "time.sleep(6)"
STEP-DEADLINE exceeded step=<unnamed> seconds=2.2 killed=2:2416,50368 job=yes     (rc=124)

$ SOTTO_STEP_OVERRIDE_S=30 python _main/step-deadline.py --seconds 1   -- python -c "time.sleep(4)"
                                                                                 (rc=0)
```

O negativo do proprio wrapper: `python _main/step-deadline.py --neg-arm` → `NEG-ARM: PASS (o mutante
sem kill foi APANHADO)`.

## 3. `panel-hidden-at-startup-oracle` — o corte passa a NOMEAR quem estava vivo

**O que faltava.** Dois `rc=124` no mesmo dia, e o log do passo dizia `Timeout` e mais nada: nem o
pid, nem o processo filho que estava a importar, nem quanto tinha andado. Um corte sem pid e' um
numero de relogio.

**A cura, duas metades.**
- `run_mutant_isolated` passou de `subprocess.run` para `Popen` + `communicate(timeout=...)`: sem o
  pid nao ha' o que atribuir.
- no `TimeoutExpired`, `freeze_capture(pid, mutante)` escreve
  `_main/_cache/panel-hidden-freeze-<ts>-pid<N>.txt` com a arvore VIVA (pid, ppid, nome, status,
  `cpu_s`, hora de criacao e cmdline), mata a arvore e o log do passo leva
  `FREEZE-CAPTURE path=...`.

**Provado contra um filho REAL** (nao contra um mock): um `python -c "time.sleep(20)"` largado pelo
proprio oraculo, e o ficheiro nomeia-o —

```
FREEZE-CAPTURE pid=57384 at=20261112-042310 mutant=mutante-falso
pid=57384 ppid=58572 name=python.exe status=running cpu_s=0.06 born=04:23:09 cmd=... -c import time; time.sleep(20)
```

**O braco, e o seu proprio controlo.** `arm_freeze_capture(capture=None)` corre em TODA invocacao do
oraculo (custa ~1 s) e aceita a funcao de captura injectada exactamente para poder ser julgada:

```
$ arm_freeze_capture()                  -> fail=0   (detail pid=19428 nomeado=True linhas=3)
$ arm_freeze_capture(capture=mutante)   -> fail=1   (detail pid=18788 nomeado=False linhas=1)
```

O mutante escreve SO' o cabecalho — o defeito que um capture decorativo teria — e o braco cai.
A primeira versao do controlo NAO o apanhou (`mutante fail=0`): eu trocava a funcao no `__dict__` do
modulo e a funcao original continuava a resolver o `freeze_capture` do `__globals__` dela. A cure foi
tornar a funcao um PARAMETRO; o mesmo erro de "o controlo mede o nome, nao o caminho" que o
`process-target-oracle` ja' custou.

## 4. O que NAO esta' verificado

- `panel-hidden-at-startup-oracle` **nao** foi cronometrado sob o tecto novo nesta sessao: a corrida
  que o prova e' a seguinte a este recibo. O que esta' medido e' o valor velho (242,77 s) e o tecto.
- O override e' um tecto, nao uma reducao de custo. O custo real do passo continua a ser 4 processos
  filhos; a reducao (correr os mutantes em paralelo) fica por medir e nao foi feita.
- Nada disto toca a app que o dono corre: sao instrumentos de bateria.
