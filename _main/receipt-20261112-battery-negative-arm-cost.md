# RECIBO — o braço negativo deixou de pagar o trabalho inteiro por mutante (2026-11-12)

Tudo o que segue foi medido nesta árvore, nesta sessão. Onde um número aparece, o comando ou o
instrumento que o produziu está ao lado. O defeito é o D-06 de `docs/spec/10-DEFECTS.md`.

## 1. O que estava errado, e como foi achado

A cauda da bateria já estava nomeada por número (D-06). O que faltava era a CAUSA, e a pergunta que a
acha é uma conta: um `--neg-arm` corre `N` mutantes, logo o custo legítimo é `N ×` **o braço que
aquele mutante derruba** — nunca `N ×` a bateria inteira.

```
        positivo   negativo   negativo/positivo
panel-themes            34.8 s     92.2 s     2,6x
panel-header-oracle      8.5 s     59.8 s     7,0x
gaming-hotkey            2.8 s     53.1 s    19,0x
youtube-cdp-source       6.2 s    110.2 s    17,8x
warm-engine             10.0 s     71.3 s     7,1x
```

`cProfile` sobre cada um nomeou o custo, e nos quatro primeiros não era o trabalho do braço.

## 2. As quatro curas, cada uma com o número ANTES e DEPOIS

| # | passo | defeito medido | cura | efeito |
|---|---|---|---|---|
| 1 | `red-as-expected-panel-themes` | `fs.cpSync` de `app/panel` (2 882 ficheiros / 35 MB) = **2 837 ms**, uma vez por mutante × 13 = **~37 s** de cópia pura | uma cópia base + restauro por BYTES dos 4 ficheiros mutados | **92,2 → 56,8 s** sozinho, **43,3 s** na corrida |
| 2 | `red-as-expected-panel-header-oracle` | 9 mutantes × 2 837 ms, mais uma cópia inteira no braço de CONTROLO | o mesmo restauro; o controlo mede a cópia que o `restore()` já repôs | **59,8 → 44,4 s** sozinho, **31,1 s** na corrida |
| 3 | `red-as-expected-gaming-hotkey` | `(a+)+$` com 26 `a` custa **3 773,5 ms** por chamada (2,3 ms com 16, 480,6 com 23): 8× o prazo de 0,45 s, × 5 mutantes | `HOLD_BACKTRACK_A = 20` = **36–46 ms** por chamada, 10–13× abaixo do prazo | **53,1 → 34,8 s** sozinho, **34,7 s** na corrida |
| 4 | `red-as-expected-youtube-cdp-source` | a cache de AST por CONTEÚDO entrou nesta árvore, mas o passo em `_cache/battery-steps.json` carregava o valor velho | rebase do ledger (nenhum código novo) | **110,2 → 12,9 s** sozinho, **12,1 s** na corrida |

Os quatro positivos da mesma corrida, para a razão ser legível: `panel-themes` 40,5 s (paga os 59
desenhos), `panel-header-oracle` 2,3 s, `gaming-hotkey` 3,9 s, `youtube-cdp-source` 5,7 s.

As três curas de código são do INSTRUMENTO, não do produto: nenhuma linha de `app/` ou `worker/` mudou.

**O restauro tem de se provar.** Três mutantes do `panel-themes` tocam o MESMO ficheiro
(`panel-unified.css`); um restauro que falhasse deixaria o mutante seguinte a medir o anterior e as
arms cairiam pelo mutante errado. O `restore()` relê os bytes depois de escrever e **levanta** se não
bater. O controlo do `panel-header` passou a usar o mesmo `restore()` e a função `copyDir` (a única
chamadora que restava) foi apagada.

## 3. O que os veredictos dizem (a cura não pode afrouxar o braço)

```
panel-themes            NEG-ARM: PASS -- 13/13 mutants caught
panel-header-oracle     NEG-ARM VERDICT PASS -- 9 mutant(s), 0 wrong
gaming-hotkey           NEG-ARM PASS -- RED as designed: as cinco regressoes derrubam o oraculo
youtube-cdp-source      NEG-ARM VERDICT: PASS (17/17)
```

## 4. O defeito de PORTÃO que a corrida revelou (e a sua cura)

`spec-coverage-oracle.py` contou **cinco** ficheiros `app/webview/_inputpath-neg-*.py` como produto e
publicou `ausentes=5 VERDICT: FAIL`. Não são produto: `input-path-oracle.py:477` escreve-os dentro da
árvore durante a corrida e `:487` apaga-os no fim (`MUTANT_PREFIX = "_inputpath-neg-"`,
`input-path-oracle.py:73`). A população daquele portão é lida do DISCO, por isso uma corrida
concorrente mudava a resposta.

Cura: `EPHEMERAL_PREFIXES = ("_inputpath-neg-",)` com a razão escrita ao lado. Provado nos dois
sentidos — com uma cópia plantada à mão (`app/webview/_inputpath-neg-race-probe.py`) o portão
continua `PASS`, e sem ela também; o `--neg-arm` continua a apanhar os dois mutantes e sai **rc=1**.

## 5. O número da bateria, medido numa corrida INTEIRA

O modo rápido não serve para isto: ele SALTA os passos mais lentos da corrida anterior, que são
exactamente os curados, e o número novo nunca apareceria. Corrida inteira, `rc=0`:

```
BATTERY-VERDICT: GREEN WITH 24 SKIPPED - 24 step(s) did NOT verify this run   (17 sao HEAVY)
failed   : -none-
```

E o portão do relógio, antes e depois:

```
antes:   RATCHET-OK -- steps=413 total=2293.3s   (baseline 2731.1s)
depois:  RATCHET-OK -- steps=452 total=1876.8s TARGET NOT MET (gap 1816.8s de 60s)
soma crua da cache: cap40 n=452 total=2363.2s
```

**−854,3 s, −31 %** contra o baseline anterior. A fatia dos `red-as-expected-*` caiu de **60,6 %**
para **53,5 %** do custo (198 passos, 1 263,3 s de 2 363,2 s).

O baseline foi rebasado no mesmo comando (`--rebase-policy` com a razão escrita), porque um ratchet
preso à régua de 2 731,1 s deixaria passar **45 %** de regressão antes de voltar a falar. Dois passos
"engordaram" na corrida e tiveram de ser nomeados em `--accept-growth`:
`caption-overlay-theme` 62,5 s e `stepcache-oracle` 67,4 s medem **5,2 s** e **12,0 s** em janela
calma — era contenda dos meus próprios probes em paralelo, e um rebaseline que absorvesse um aumento
em silêncio seria o ratchet a assinar o próprio aumento.

## 6. O que NÃO se corta, e por quê

`red-as-expected-warm-engine` (73,4 s / 6 mutantes = 1,2× o positivo), `red-as-expected-altc-gesture`
(56,6 s) e `red-as-expected-window-drag` (55,5 s) pagam um SUBPROCESSO real por mutante — é o
isolamento que o braço compra, e um cache partilhado entre mutantes mediria o mutante anterior.
`caption-overlay-theme` (62,5 s) e `headphone-cut` (60,7 s) renderizam os 59 desenhos e leem um
dispositivo de áudio. Cortá-los exige cortar a POPULAÇÃO do braço, que é uma decisão de cobertura e
não de relógio.

## 7. O QUE NÃO ESTÁ VERIFICADO

* Nada disto foi visto na tela do dono. A prova é de oráculo, de cache de bateria e de uma corrida
  completa; `verified` continua a exigir uma corrida real da app pela mão dele.
* Os 24 passos SKIPPED da corrida não são gates que passaram, e 17 deles são a classe HEAVY (abrem o
  ecrã dele, o dispositivo de áudio ou a GPU) que não corre sem `SOTTO_BATTERY_HEAVY=1`.
