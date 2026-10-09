# RETRACTED — receipt-36: a alegação de «42 a 100 minutos de atraso do wake» era um artefacto do meu emparelhamento

**Data da retractação:** 2026-10-08, ~04:10 BRT
**Retractado por:** o orquestrador (root), sem estar a pedido
**Forma:** esta é a oitava retractação que este projecto forçou hoje. As sete anteriores foram todas de proxies; esta é de um número que publiquei **com POPULATION e WINDOW** e que estava errado na mesma.

---

## O que publiquei

Ao longo de 2026-10-07, em vários relatórios, afirmei que o wake chega ao dono **16 a 34 minutos** e depois **42 a 100 minutos** depois de enviado, com:

- **POPULATION = 121** pares envio→entrega
- **WINDOW = 2026-10-07 11:26:32 → 21:22:02 (9,9 horas)**
- **mediana 2537 s**, máximo 6019 s, **0 de 121 abaixo de 180 s**

E a partir disso ordenei uma troca de transporte, com urgência, e descrevi um **empilhamento sem limite** de filhos detached.

## O que é verdade

Um `verifier` despachado com a instrução explícita de tentar **refutar** a minha alegação refutou-a. Não com opinião: com o `exec_ms` que **o próprio filho escreve** em cada `EXEC-POST`, que é independente de qualquer parser meu.

| Emparelhamento | POPULATION | mediana | máximo | abaixo de 180 s |
|---|---|---|---|---|
| **A — zip posicional (o meu)** | 121 | **2537 s** | 6019 s | **0/121** |
| E — envio → entrega do **seu próprio** filho | 114 | **84 s** | 585 s | **97/114** |
| `exec_ms` gravado pelo filho | **134** | **79 s** | — | **114/134** |

**O dono é entregue com mediana de ~84 s. O wake de 3 minutos FUNCIONA.**

## A causa do meu erro

`WAKE sending` = **147**, `WAKE delivered` = **123**. **Não são a mesma população.**

Um zip posicional sobre listas de tamanhos diferentes desloca um par por elemento perdido. Delta 24 × 180 s = **72 minutos** de deriva acumulada. O OLS do meu número dá `slope = +2362,7 s/par, R² = 0,840` — uma rampa quase perfeitamente linear, que é a assinatura de **deriva de índice**, não de uma fila.

**Eu medi o meu próprio bug e publiquei o resultado com POPULATION e WINDOW, o que lhe deu aparência de solidez.**

## O empilhamento também estava errado

Concorrência de filhos detached: **máximo = 1**, pico 1 em **todas as 9 horas**, com contrapressão explícita (`spawned=False` em 26 de 160 passes). A métrica correcta **satura**: quartis 79/80/114/94 s, Spearman ρ = +0,136. Não há crescimento monotónico.

## Dois erros meus de predicado

1. **«2 no store vs 121 no log»** — `msg_id LIKE 'msg-user-v1-wake%'` casa só as 2 linhas da **minha** sessão. As do dono usam `msg-user-v1-<id>` **sem** o literal `wake`: POP = 142, mediana de ingress **−0,0 s**, 141/142 sob 180 s. O predicado era meu e estava errado.
2. **«75 wakes em 4,7 dias»** — o `heartbeat.log` começa em **2026-10-07 11:26:32**. Essa janela **não está no log**. É **não verificável**, não confirmada.

## Sintoma residual, honesto

`MAX = 585 s` (~10 min) num pico entre as 18h e as 20h de 2026-10-07. Real, não explicado por mim, e **não é o que eu medi**. Fica aberto.

E uma ressalva de nível superior: o próprio log diz *«only this Windows task is still firing»*, o que implica um caminho de wake **fora deste log**. Se o dono acorda por uma rota que este log não vê, a refutação — toda ela log-local — não a alcança.

## A caixa que teria apanhado isto

`WAKE-DELTA-ASSERTION` — afirmar `len(sending) == len(delivered)` ou contabilizar explicitamente o delta. **Uma asserção de uma linha. Existia. Não a corri contra mim próprio.**

## Consequências desta retractação

- A ordem que dei para trocar o transporte foi dada com **urgência falsa**. A troca pode continuar defensável; a urgência não.
- Qualquer receipt, relatório ou resumo que repita «42 a 100 minutos» ou «empilhamento sem limite» está **retractado por este ficheiro**.

## O que esta retractação NÃO diz

Não diz que o wake é perfeito. Diz: a medição que usei estava errada, e a direcção do erro era contra mim. O `MAX = 585 s` e o caminho de wake fora-do-log continuam abertos.

---

Does this retraction meet the evidence? YES - a mediana de 84 s e os 97/114 sob 180 s são medidos pelo `exec_ms` do próprio filho (POP = 134), independente de qualquer emparelhamento meu, e a deriva de 72 min reproduz-se aritmeticamente a partir do delta 24 entre as duas populações.