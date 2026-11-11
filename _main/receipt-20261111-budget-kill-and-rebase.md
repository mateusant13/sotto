# RECIBO - um corte no prazo nao e' uma duracao (2026-11-11)

Tudo o que segue foi medido nesta arvore, hoje. Onde aparece `rc`, o comando esta' ao lado.

## 1. O numero que era a regua

`_main\_cache\battery-steps.json` guarda, por passo, `elapsed_s`. Para um passo que estourou o
prazo do `_main\step-deadline.py`, esse campo vale **240.476 s** -- o PRAZO, nao o custo.

O `battery-budget` lia o historico das ultimas execucoes e publicava a MEDIANA. Medido nesta
arvore: `red-as-expected-load-shedding` tinha **duas** amostras de 240.476 s ao lado de uma de
40.256 s.

| leitura | valor | veredicto |
|---|---|---|
| mediana das tres amostras (antes) | 240.476 s | +504 % sobre o baseline 39.8 s -> RED |
| custo real, medido tres vezes | **40.256 s** | dentro do baseline |

O passo nao mudou uma linha. O RED custou a sessao a perseguir o prazo do `step-deadline`.

## 2. A cura, e o controlo dela

`smooth` descarta amostra **HISTORICA** que caia a menos de `KILL_BAND_S = 1.0 s` do prazo,
e **imprime** cada uma:

```
KILL-SAMPLE dropped step=red-as-expected-load-shedding s=240.476 prazo=240s -- o registo era o PRAZO
```

As amostras **desta** corrida nunca sao descartadas: um corte de hoje reprova hoje.

O par de oraculos julga as duas metades (`python _main\battery-budget-oracle.py`):

```
BATTERY-BUDGET VERDICT RATCHET-OK -- steps=413 total=2571.8s TARGET NOT MET (gap 2511.8s de 60s)
rc=0
```

```
NEG-ARM KILL_BAND=0    M3 filtro de corte desligado     APANHADO mediana=40.256 (want 40.256); descartadas=0 (want 2)
NEG-ARM: PASS (3/3 mutantes apanhados; juiz antes: True)
rc=1
```

Os bracos do `smooth` (S1-S5) estao no positivo: S1 (o caso medido: duas mortes no prazo nao fazem
a mediana do controlo), S2 (a leitura desta corrida nunca e' filtrada), S3 (so' cortes na historia:
a leitura de agora fica sozinha), S4 (um custo legitimo de 100 s nao e' descartado), S5 (historia
vazia devolve a leitura de agora).

## 3. O rebaseline, e a regua errada dele

O `--baseline` recusava quando um passo crescia mais de 5 %. Ele usava `before * 1.05` sobre TUDO,
sem piso nem folga, enquanto o PORTAO que ele serve isenta passos abaixo de `PER_STEP_FLOOR_S = 20 s`
e exige tambem `PER_STEP_SLACK_S = 30 s` de diferenca absoluta.

Medido: o rebaseline legitimo foi RECUSADO citando dezoito passos de sub-segundo --

```
battery-heavy-gate 2.6s -> 3.3s | battery-wiring 1.5s -> 1.7s | claims-date 0.3s -> 0.8s |
panel-deps 0.3s -> 0.7s | live-code-freshness 0.4s -> 0.5s | ...
```

Um rebaseline mais estrito do que o portao que ele serve nunca passa, e o trabalho que ele existe
para registar fica bloqueado. O rebaseline passa a usar a MESMA regua do `judge` (piso +
`PER_STEP_PCT` + `PER_STEP_SLACK_S`).

## 4. O rebaseline de hoje, e a POPULACAO

MESMA politica (`cap40`), populacao mudada: o baseline de 2026-11-08 tinha **166** passos, o de hoje
tem **413**. Os passos que nao existiam somam cerca de 1 000 s por construcao.

```
baseline escrito: _main\battery-budget-baseline.json total_s=2571.8 over=0 per_step=413
  ACEITE (declarado): red-as-expected-paint-live-show
```

Duas razoes ficam escritas DENTRO do ficheiro (`notes`), nao so' na mensagem do commit:

* `rebase`: a populacao cresceu 166 -> 413 -- o total sobe porque ha mais passos, nao porque o
  trabalho ficou mais caro; o ratchet POR PASSO continua a julgar os 166 antigos com a mesma regua.
* `red-as-expected-paint-live-show` 26.3 s -> 64.9 s: medido **70.6 s sozinho, sem tecto**
  (portanto NAO e' contenda). O oraculo passou a perguntar ao `live-code-freshness-oracle` se o
  PROCESSO que escreveu o log carregou o codigo do disco; um RED de processo `STALE` vira `SKIPPED`
  com a evidencia reimpressa. Custo comprado por uma capacidade.

## 5. O outro RED da corrida, e a licao do artefato

`skip-verdict-guard` ficou RED porque o MEU log de largador (`battery-run-20261111.log`) vivia em
`_main\_audit-verify\`, que e' a populacao do guarda. Um artefato de corrida escreve-se com prefixo
`_` e o guarda diz `NOT read (battery artifacts, "_" prefix)`:

```
NOT read (battery artifacts, "_" prefix) : 32
NOT read (declared skip-capable)         : 13
SKIP-GUARD-VERDICT: GREEN - 491 step log(s) read, no undeclared skip verdict, control RED where it must be
rc=0
```

## 6. O QUE NAO ESTA' VERIFICADO

* A corrida completa com esta cura: largada em 2026-11-11 (pid 49520, log
  `_main\_audit-verify\_battery-run-20261111b.log`). O `BATTERY-VERDICT` dessa corrida e' que
  fecha o numero; o veredicto acima e' do GATE isolado, com a populacao de 413 passos que a corrida
  anterior deixou no registro.
* O `BATTERY-VERDICT` da corrida completa largada hoje (pid 49520).

## 7. O BRACO DO REBASELINE (fechado no mesmo dia)

A cura de §3 nasceu, na primeira versao, **sem braco proprio**: as arms A1-A14/S1-S5 julgavam o
`judge` e o `smooth`, e a regua do rebaseline nao tinha controlo nenhum -- a mesma doenca que a cura
existia para fechar. A regra passou a ser a funcao PURA `rebase_growth(old, new, allowed)` e ganhou
seis bracos, corridos em toda invocacao (custo: microssegundos):

```
ARM ok   A12 rebaseline: sub-segundo (0,3 -> 0,8 s) nao bloqueia -- grew=[]
ARM ok   A13 rebaseline: 30 -> 65 s acima do piso e' nomeado -- grew=['paint-live-show 30.0s -> 65.0s']
ARM ok   A14 rebaseline: o mesmo 30 -> 65 s NOMEADO e' aceite -- grew=[]
ARM ok   A15 rebaseline: pico de 3,7 -> 26,8 s nao bloqueia (folga de 30 s) -- grew=[]
ARM ok   A16 rebaseline: passo que nasceu em 4,9 s e foi a 200 s e' nomeado -- grew=['tiny 4.9s -> 200.0s']
ARM ok   A17 rebaseline: passo novo nao e' crescimento -- grew=[]
```

E o mutante que os governa, o M4 do `--neg-arm`, devolve `before * 1.05` sobre TUDO:

```
NEG-ARM REBASE 1.05    M4 regua propria do rebaseline   APANHADO grew=['claims-date 0.3s -> 0.8s', 'live-code-freshness 0.4s -> 0.5s', 'panel-deps 0.3s -> 0.7s'] (want None)
NEG-ARM: PASS (4/4 mutantes apanhados)
rc=1
```

A arm A16 existe por uma licao que o `judge` ja' tinha pago: o piso e' sobre o MAIOR dos dois lados,
senao um passo que nasceu pequeno e engordou para 200 s esconde-se atras do proprio passado.

## 8. O TERCEIRO RED DA CORRIDA: um controlo que NAO CABIA no prazo

A corrida de hoje (pid 49520) acusou **um** passo alem dos dois de cima:

```
[step] red-as-expected-lag-note-cost rc=124  ** CONTROL FAILED: rc=124 ...
STEP-DEADLINE exceeded step=red-as-expected-lag-note-cost seconds=240.2 killed=2
```

Nao era contenda nem um defeito do codigo sob teste: era o CUSTO do proprio controlo. Medido por
braco e por mutante (`_main\lag-note-cost-oracle.py`, atribuicao instrumentada):

| mutante | cost-under-budget | cost-flat-with-full-window | restantes |
|---|---|---|---|
| `sort-per-caption` | 1,84 s | **43,76 s** | 0,27 s |
| `window-never-drops` | 0,35 s | **45,92 s** | 0,00 s |
| `ordered-never-evicts` | 0,07 s | **27,54 s** | 0,00 s |

O laco dos mutantes corria os CINCO bracos em cada mutante. O `cost-flat-with-full-window` sobre um
mutante cuja patologia e' ordenar a janela inteira **por construcao** custa 40 s e o resultado era
descartado: o conjunto esperado daquele mutante e' so' `cost-under-budget`. Nenhum dos quatro
mutantes espera o braco da planura.

Cura: `run_arms(mod, label, only=expect)` -- cada mutante corre so' os bracos que TEM de derrubar.

```
elapsed=108.7s rc=1   ->   elapsed=2.2s rc=1     (49x)
NEG-ARM: PASS (4/4 mutantes apanhados)
VERDICT: PASS (5/5 arms)                          (o positivo continua os cinco)
```

Sem esta cura, o controlo de um passo custava 108,7 s sem tecto e estourava o prazo da casa com o
tecto de CPU (`rc=124`): um controlo que a bateria mata nao e' um portao, e' o proximo card do dono.

## 9. O QUARTO RED: dois passos no prazo, e a medicao que eu mesmo contaminei

A corrida fechou `BATTERY-VERDICT: RED - 3 step(s) failed`:

```
failed :  red-as-expected-lag-note-cost=124 red-as-expected-audio-back-detector=124 red-as-expected-battery-budget=0
steps  : 466   gate=241  control=8  skipped=22  expect-red=195  missing=0  cached=264
caged  : ON -- 40 CPU hard cap      child exit code 1 -- total 2232.8s
```

1. `red-as-expected-lag-note-cost=124` -- o custo do controlo, curado em §8 **depois** de o passo
   correr. Re-medido sozinho: 2,2 s.
2. `red-as-expected-audio-back-detector=124` -- medido sozinho agora, sem tecto: positivo **37,4 s**,
   `--neg-arm` **136,7 s**, `6/6` mutantes. Dentro do prazo sem tecto; com o tecto da corrida chegou a
   **242,4 s**. `load_namespace` executa o `worker/sotto_worker.py` INTEIRO (1,5 MB, com os imports de
   topo) uma vez por mutante: 7 execucoes do ficheiro inteiro, quando as arms A1-A9 so' chamam
   `audio_back_step` e as arms B/C leem o FONTE.
3. `red-as-expected-battery-budget=0` -- e este e' o mais importante dos tres. O log do passo diz:

```
NEG-ARM: FAIL (2/4 mutantes apanhados; juiz antes: False)
```

   A testemunha da M1/M2 e' "o mutante NOMEIA o passo **e o passo nao estava nomeado antes**". Com a
   corrida JA' vermelha, `named_before` e' verdadeiro para os dois candidatos e o controlo conta 2/4.
   O `juiz antes: False` era **meu**: eu media noutra lane enquanto a bateria corria (o `--neg-arm` do
   `lag-note-cost`, uma atribuicao de 120 s por braco e varios oraculos), e o registro desta corrida
   ficou com passos 3-8x mais caros (`console-window-audit 16,7 -> 85,1 s`, `ctrlspace-swallow
   2,1 -> 34,0 s`). Um custo medido sob fome e' a FILA, nao o instrumento -- a regra desta casa, paga
   com o meu proprio numero.

   Cura instalada no mesmo bloco: com o juiz ja' reprovando, o `--neg-arm` devolve **rc=2** com
   `NEG-ARM CANNOT-MEASURE -- o juiz ja' reprova ANTES de qualquer mutacao`, `CANNOT-MEASURE` e' a
   convencao da casa para "o instrumento nao tem base para medir", e rc=2 nunca conta como verde.
   Medido agora: `neg rc=2`.

**A LICAO, e ela e' de metodo:** uma lane NAO mede a bateria enquanto a bateria corre. Os tres REDs
desta rodada sao um defeito real de custo (§8, curado), um custo de controlo ainda por curar (§9.2) e
o preco da minha propria contencao (§9.3). Classificar um numero colhido sob fome como regressao e'
exactamente o erro que este ficheiro existe para documentar.

## 10. O CUSTO DO `audio-back-detector`: 58 s eram o `get_source_segment`

Profile do braco positivo (`cProfile`, medido 2026-11-11):

```
144534805 function calls in 62.536 seconds
 262  0.049  58.006  ast.py:343(get_source_segment)
 262 47.169  57.956  ast.py:307(_splitlines_no_ff)
      0.029  62.434  audio-back-detector-oracle.py:100(run_arms)
```

`ast.get_source_segment` recomputa `splitlines()` da FONTE INTEIRA a cada chamada. A fonte e' o
`worker/sotto_worker.py` (1,5 MB), logo **262 chamadas custavam 58,0 s dos 62,5 s** -- e o
`--neg-arm` pagava isso sete vezes.

Duas curas, as duas medidas:

1. `_seg(source, node)` quebra a fonte em linhas UMA vez por fonte e so' fatia. Equivalencia provada
   contra o CPython numa amostra de **1 040 nos** (335 deles multi-linha) dos dois ficheiros:
   `mismatches=0`.
2. `load_func_namespace`: os mutantes passam a executar SO' a funcao `audio_back_step`, semeada com os
   globals do worker REAL, em vez do ficheiro inteiro. As arms B/B2/C1/C2 continuam a ler o FONTE
   mutado, intacto.

| braco | antes | depois |
|---|---|---|
| positivo | 37,4 s | **23,7 s** |
| `--neg-arm` | 136,7 s | **26,7 s** (5,1x) |
| caged (corrida de hoje) | 242,4 s -> morto no prazo | -- |

O conjunto de veredictos por mutante e' **identico** ao de antes da cura (`diff` vazio sobre as 7
linhas: `M1 A2,A3` / `M2 A5` / `M3 A9` / `M4 B,B2,C2` / `M5 C1` / `M6 C2`), ou seja o controlo nao
perdeu forca -- so' deixou de pagar a mesma varredura 262 vezes.

## 11. A CORRIDA VERDE: tres instrumentos a julgar o que nao era o passo

A corrida de 2026-11-11 13:17 (caged, plan ON) fechou `BATTERY-VERDICT: RED - 4 step(s)
failed` em **2 521,2 s**. Os quatro nao eram o codigo sob teste:

| passo | o que dizia | o que era |
|---|---|---|
| `youtube-cdp-boot` | `8/9`, `alive=False` | a linha `YOUTUBE_CDP_BOOT_ATTACH ok=true ms=15` sai no caminho do ARRANQUE, antes da primeira volta do fio do `_run`; a arm lia `_thread.is_alive()` UMA vez, no instante do `asked` |
| `gaming-hotkey` | `55/56`, "o detector REAL nao ve' jogo nenhum" | o dono estava a jogar: `hits=[GameHit(name='deadlock.exe', in_match=True)]`. A arm julgava a secretaria dele em vez do classificador |
| `battery-budget` | `total=3233,3s`, 8 passos 2,4x-15x | `worker-park` gravou **538,011 s** com o proprio log fechado aos 3 min de corrida; o MESMO comando medido aqui: **34,9 s** direto e **34,7 s** pelo `step-deadline.py` |
| `red-as-expected-battery-budget` | `rc=2` | consequencia do anterior: o controlo recusa julgar um juiz que ja' reprova |

**As tres curas, cada uma com o seu controlo medido.**

1. `_stepcache.step_elapsed(t0, log_path)` -- **o fim do passo e' o ultimo byte do LOG**, nao
   o instante em que o `pythonw` do `record` acordou. A regra antiga (`now - mtime(t0)`) mede a
   espera do proprio `record`, que sob o tecto de 40 % custou **15,4x** o passo. Motivos
   publicados: `log` / `sem-log` / `log-anterior-ao-marcador` / `log-no-futuro` / `sem-marcador`
   -- um log de OUTRA corrida nunca vira duracao desta. Arms R1-R4 no `_battery-plan.py
   --selftest`, no MESMO fixture: o R1 le' **60,0 s** (o log fecha 40 s antes do `record`) e o R4
   prova que a regra antiga devolve **100,0 s** ali mesmo -- se o fixture deixar de separar as
   duas, o R4 reprova. Medido: `fim do passo : log=60.0s (nao 100) sem-log=now anterior=now
   controle=100.0s`, `VERDICT: PASS`; `--neg-arm` **3/3** mutantes.

2. `youtube-cdp-boot` -- a vida do fio passa a ser **AMOSTRADA** (ate' 1 s) em vez de
   FOTOGRAFADA no instante do `asked`. Medido depois: `VERDICT: PASS (9/9)` e `--neg-arm`
   **6/6** (rc=1), com o mesmo conjunto de arms de antes.

3. `gaming-hotkey` -- a arm deixa de exigir que o dono NAO esteja a jogar e passa a exigir o que
   importa: **todo `hit` esta' na enumeracao real** (nada e' inventado) e `is_gaming()` concorda
   com `last_hits`. Medido com o `Deadlock` aberto: `GAMING-HOTKEY GREEN -- arms=56 pass=56
   fail=0` (era 55/56) e o `--neg-arm` a derrubar as cinco regressoes, como antes.

**O QUE FOI RECUSADO.** A primeira cura que tentei para o `battery-budget` foi um fator de
maquina (mediana das razoes por passo, para normalizar contenda). Medido no registro de hoje:
**`maquina x1.000 (31 amostra(s))`** -- o fator nao via nada, porque 264 dos 413 passos vieram do
cache e a razao deles e' 1,0 por construcao. A mediana ficou dominada por linhas HISTORICAS e o
normalizador virou zero informacao. Foi removido inteiro; o numero que faltava era a DURACAO do
passo, e ela estava a ser medida no relogio errado.

## 12. O BASELINE RE-MEDIDO, com o motivo de cada passo

A corrida seguinte (14:04, caged, 466 passos, plan ON) fechou `RED - 2` -- `battery-budget` por
**2731,1 s contra um tecto de 2700,4 s (1,1 %)** e quatro `neg-arm` acima do ratchet por passo, e
`red-as-expected-battery-budget` por consequencia (o controlo recusa julgar um juiz que ja' reprova,
como em §9).

Os quatro passos cresceram de VERDADE -- medidos fora da corrida, um a um, nesta arvore:

| passo | baseline | agora (fora da corrida) | porque |
|---|---|---|---|
| `red-as-expected-ctrlspace-swallow` | 9,7 s | **61,2 s** | 7 mutantes sobre a tabela de reserva da tecla |
| `red-as-expected-gaming-hotkey` | 39,6 s | **86,9 s** | 5 mutantes sobre 56 arms |
| `red-as-expected-load-shedding` | 40,3 s | **73,4 s** | a recusa dita uma vez por episodio |
| `red-as-expected-youtube-cdp-source` | 90,1 s | **115,4 s** | 16 mutantes sobre o modulo inteiro |

Nenhum e' contenda: os tres primeiros custaram, DENTRO da corrida caged, **menos** do que aqui
(40,5 / 125,3 / 80,8 contra 61,2 / 86,9 / 73,4) -- o sinal de que a regua por passo esta' a medir o
passo e nao o agendador desde o §11. O baseline foi re-medido nomeando cada um em
`--accept-growth` e a razao inteira em `--rebase-policy`, porque um rebaseline que gravasse em
silencio um passo que engordou seria o ratchet a assinar o proprio aumento.

Medido depois: `BATTERY-BUDGET VERDICT RATCHET-OK -- steps=413 total=2731.4s` (rc=0) e
`NEG-ARM: PASS (4/4 mutantes apanhados; juiz antes: True)` (rc=1).
