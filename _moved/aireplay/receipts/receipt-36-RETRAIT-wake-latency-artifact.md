# RETRACTED — receipt-36: a alegacao de "42 a 100 minutos de atraso do wake" era um ARTEFACTO DO MEU EMPARELHAMENTO

**Data da retractacao:** 2026-10-08, ~04:10 BRT
**Retractado por:** o orquestrador (root), sem estar a pedido
**Forma:** esta e a NONTA retractacao que este projecto forced hoje. As sete anteriores foram todas de proxies; esta e de um numero que publiquei com POPULATION e WINDOW e que estava errado na mesma.

---

## O que publiquei

Ao longo de 2026-10-07, em varios relatorios, afirmei que o wake chega ao dono **16 a 34 minutos** e depois **42 a 100 minutos** depois de enviado, com:

- **POPULATION = 121** pares envio->entrega
- **WINDOW = 2026-10-07 11:26:32 -> 21:22:02 (9,9 horas)**
- **mediana 2537 s**, max 6019 s, **0 de 121 abaixo de 180 s**

E a partir disso ordenei uma troca de transporte, com urgencia, e descrevi um **empilhamento sem limite** de filhos detached.

## O que e verdade

Um `verifier` despachado com a instrucao explicita de tentar REFUTAR a minha alegacao refutou-a. Nao com opiniao: com o `exec_ms` que **o proprio filho escreve** em cada `EXEC-POST`, que e independente de qualquer parser meu.

| Emparelhamento | POP | mediana | max | <180 s |
|---|---|---|---|---|
| **A - zip posicional (o MEU)** | 121 | **2537 s** | 6019 s | **0/121** |
| E - envio -> entrega do SEU PROPRIO filho | 114 | **84 s** | 585 s | **97/114** |
| `exec_ms` gravado pelo filho | **134** | **79 s** | - | **114/134** |

**O dono e entregue com mediana de ~84 s. O wake de 3 minutos FUNCIONA.**

## A causa do meu erro

`WAKE sending` = **147**, `WAKE delivered` = **123**. **Nao sao a mesma populacao.**

Um zip posicional sobre listas de tamanhos diferentes desloca um par por elemento perdido. Delta 24 x 180 s = **72 minutos** de deriva acumulada. O OLS do meu numero da `slope = +2362,7 s/par, R^2 = 0,840` - uma rampa quase perfeitamente linear, que e a assinatura de **deriva de indice**, nao de uma fila.

**Eu medi o meu proprio bug e publiquei o resultado com POPULATION e WINDOW, o que lhe deu aparencia de solidez.**

## O empilhamento tambem estava errado

Concorrencia de filhos detached: **maximo = 1**, pico 1 em **todas as 9 horas**, com contrapressao explicita (`spawned=False` em 26 de 160 passes). A metrica correcta **satura**: quartis 79/80/114/94 s, Spearman rho = +0,136. Nao ha crescimento monotónico.

## Dois erros meus de predicado,同样 meus

1. **"2 no store vs 121 no log"** — `msg_id LIKE 'msg-user-v1-wake%'` casa so as 2 linhas da **minha** sessao. As do dono usam `msg-user-v1-<id>` **sem** o literal `wake`: POP = 142, mediana de ingress **-0,0 s**, 141/142 sob 180 s. O predicado era meu e estava errado.
2. **"75 wakes em 4,7 dias"** — o `heartbeat.log` comeca em **2026-10-07 11:26:32**. Essa janela **nao esta no log**. E **NAO VERIFICAVEL**, nao confirmada.

## Sintoma residual, HONESTO

`MAX = 585 s` (~10 min) num pico entre as 18h e as 20h de 2026-10-07. Real, nao explicado por mim, e **nao e o que eu medi**. Fica aberto.

E uma ressalva de nivel superior: o proprio log diz *"only this Windows task is still firing"*, o que implica um caminho de wake **fora deste log**. Se o dono acorda por uma rota que este log nao ve, a refutacao — toda ela log-local — nao a alcanca.

## A caixa que teria apanhado isto

`WAKE-DELTA-ASSERTION` — afirmar `len(sending) == len(delivered)` ou contabilizar explicitamente o delta. **Uma assercao de uma linha. Existia. Nao a corri contra mim proprio.**

## Consequencias desta retractacao

- A ordem que dei para trocar o transporte foi dada com **urgencia falsa**. A troca pode continuar defensavel; a urgencia nao.
- Qualquer receipt, relatorio ou resumo que repita "42 a 100 minutos" ou "empilhamento sem limite" esta **retractado por este ficheiro**.

## O que esta retractacao NAO diz

Nao diz que o wake e perfeito. Diz: a medicao que usei estava errada, e a direccao do erro era contra mim. O `MAX = 585 s` e o caminho de wake fora-do-log continuam abertos.

---

Does this retraction meet the evidence? YES - a mediana de 84 s e os 97/114 sob 180 s sao medidos pelo `exec_ms` do proprio filho (POP = 134),独立 de qualquer emparelhamento meu, e a deriva de 72 min reproduz-se aritmeticamente a partir do delta 24 entre as duas populacoes.
