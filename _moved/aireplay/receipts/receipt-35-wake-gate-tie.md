# receipt-35 — o gate do wake tied nas DUAS colunas, e a "latência 42 min" era artefato

**Data:** 2026-10-07 · **Lane:** 16 (re-dispatch) · **Artefato:** `_main/_lane16-wake-gate.ps1`
**Alvo:** `H:\sotto\_moved\aireplay` · **Store:** `C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite`
(`mode=ro`, sempre) · **Log:** `_main/heartbeat.log`

---

## 0. O resumo que importa

O briefing desta lane chegou com um achado forte e **ele estava errado**:

> *"delivery→delivery GAP: 49 of 120 under 180 s — looks healthy.
> send→delivery LATENCY: median **2537 s (42 min)**, **0 of 121 under 180 s** — the owner's actual
> metric, and it is terrible."*

Essa média de 42 min **não é uma latência de wake**. É um **artefato de pareamento por índice**.
Medi, reproduzi e retraction abaixo. O requisito do dono (a latência) está **saudável**;
o que estava doente era o **método de medição**.

Isto não é um detalhe. É literalmente a doença que o briefing pedia para eu aplicar a mim mesmo:
*"a gate that measures the wrong column is worse than no gate, because it converts a regression
into a pass."* Um número inventado de regressão, num log real, com POP e janela certain —
é o mesmo erro com o sinal trocado. **A mesma defesa serve para os dois.**

---

## 1. Os TRÊS defeitos nomeados no briefing

Os três já estavam corrigidos na **working tree não commitada** quando recebi a lane
(`git diff --stat` = 573 inserções / 98 remoções sobre HEAD). Verifiquei cada um no código
antes de aceitar:

| # | Defeito | Onde | Estado encontrado | Verificação |
|---|---|---|---|---|
| 1 | `-match '0'` é regex de substring | `D2-control-expiry-clears-the-wedge` | **JÁ CORRIGIDO** → `-eq '0,0,0,0,0'` | vetor de 5 rcs, igualdade total |
| 2 | população truncada (`limit 20`) antes do teste | `A1-queue-linked-delivery-proven` | **JÁ CORRIGIDO** → sem `LIMIT`, igualdade sobre população inteira | `arm_a_proven_delivery_pop` = 80, `counter_examples` = 0 |
| 3 | `B4-control-table-not-empty` não pode falhar | `B4` | **JÁ CORRIGIDO** → `B4-control-cron-regime-is-two-sided` (banda de flapping é vermelha) | 1442 linhas, mais novo 2114 min ⇒ DEAD |

**Não "consertei" o que já estava certo.** O briefing mandava explicitamente isso.

---

## 2. O quarto defeito — o que eu adicionei (ARM L)

**POPULACIONAL na execução do gate (H:\...\_lane16-gate.out.txt, 2026-10-07 22:00:28):
153 `WAKE sending` · 125 `WAKE delivered` · drift = 28 slots**
**JANELA: log inteiro `2026-10-07 11:26:32 -> 2026-10-07 22:00:13`.**
O log é append-only e a task continua disparando a cada 180 s, então estes números
crescem a cada execução; o gate imprime a POPULAÇÃO e a JANELA na cara de cada braço.
(A medição que reproduz o número do briefing, feita antes, sobre a janela
`12:22:04 -> 21:22:02`, deu 146/122/drift 24 — ver §2.1.)

### 2.1 Reprodução do artefato

Cinco regras de pareamento, e qual reproduz o número do briefing
(`_main/_lane16-latency-pairings.out.txt`):

| Regra | POP | min | median | max |
|---|---|---|---|---|
| **P1 índice `send[i]→delivery[i]`** | 122 | **979 s** | **2549 s** | **6019 s** |
| P2 índice, 121 do fim | 122 | −4592 s | −2637 s | 585 s |
| P3 soma acumulada dos gaps | 122 | 0 s | 14636 s | 30631 s |
| **P4 identidade (o honesto)** | 121 | **27 s** | **87 s** | 585 s |
| P5 delivery − primeiro send | 122 | 2066 s | 16702 s | 32697 s |

Briefing: `POP=121, min 979 s, median 2537 s, max 6019 s`.
**P1 bate `min` e `max` dígito a dígito.** Não é semelhança: é o mesmo cálculo.
Com 146 envios e 122 entregas, o índice **anda 24 casas**, e o que ele mede é a
**profundidade da fila**, não a espera de um wake. Por isso ele "dá 42 min".

**Confirmado dentro do gate, numa janela posterior e maior:** o braço `L3` imprime
`drift 28` e a mediana do índice pareado contra a mediana por identidade
(`2567 s` vs `90 s`, diferença `2477 s`). O artefato **cresce com a fila**, que é
a assinatura de uma medição de backlog.

### 2.2 O número honesto

Pareamento **por identidade**: cada envio casa com a **primeira entrega em ou depois dele**;
um envio cujo sucessor dispara antes é **UNFULFILLED** (não entregue), **não lento**.

> **send → delivery = POP 125 · min 27 s · mediana 90 s (1,5 min) · p90 233 s · max 585 s · 103 de 125 abaixo de 180 s (83%)**
> (na execução do gate, janela `11:26:32 -> 22:00:13`; a medição anterior sobre
> `12:22:04 -> 21:22:02` deu POP 121 · mediana 87 s · 101/121)

**RETRACTADO:** *"a latência do dono piorou uma ordem de grandeza"*. **FALSO.**
E o inverso também vale, e é por isso que a coluna errada é perigosa nos dois sentidos:
o gap (mediana 192 s, 50/124 abaixo de 180 s) é **saudável** — eu usaria esse número
sozinho para dizer "tudo bem", e isso também seria mentira.

### 2.3 Os braços

| Braço | O que afirma | POP | Veredito |
|---|---|---|---|
| **`L1-REQUIREMENT-send-to-delivery-latency`** | **O REQUISITO.** mediana **e** p90 | 125 | PASS |
| `L2-supporting-delivery-to-delivery-gap` | métrica de apoio — **o nome do braço diz que não é o requisito** | 124 | PASS |
| `L3-control-pairing-is-load-bearing` | CONTROLE: identidade (90 s) ≠ índice (2567 s) | 125 | PASS |
| `L4-control-no-latency-regression-from-the-gap` | CONTROLE: **afirma a retraction como VERDADEIRA** | 125 | PASS |

**L1 segura mediana *e* p90.** Um gate só de mediana é satisfazível por uma população em que
metade das esperas não tem teto — que é como uma regressão de latência sobrevive.

**Orçamentos derivados, não inventados:** a task dispara a cada 180 s
(`TASK-FIRE` POP=160, mediana 180 s, máx 186 s, 159/159 dentro de 180±6 s), então
`LatencyMaxMinutes=2` ≈ 3,4 ciclos. Expostos como parâmetros
(`-LatencyMaxMinutes`, `-LatencyP90MaxMinutes`, `-GapMaxMinutes`) para quem roda dizer o
regime que está medindo, em vez de herdar literais enterrados num braço.

---

## 3. Achado colateral: o "gap de 12 min" do C1 também era artefato

`C1-task-fires-in-window` reportava `max inter-fire gap = 12 min` e ficava **VERMELHO**
em execuções anteriores. Medindo a cadência real da task:

> **`TASK-FIRE` POP=160 · mediana 180 s · máx 186 s · 159/159 gaps dentro de 180±6 s — a task está impecável.**

O "gap" do C1 nascia do **regex**, não da task: o padrão de C1 **não casa** as linhas
`WAKE QUEUE FAILED` (26 no log inteiro: 19 `exec-child-inflight` + 7 `plan-busy`). Uma
passagem em que o dono **não recebeu nada** é invisível para ele, e vira "silêncio" —
exatamente o tipo de verde-por-omissão que este gate existe para matar. **Não alterei
o predicado de C1**: a correção honesta exige um vocabulário novo, e o transporte de
wake está sendo trocado por outra lane agora; mexer aqui seria uma corrida. Fica como
**dívida aberta**, medida e com POP. Na execução de 22:00 C1 passou por sorte de janela,
e isso **não** fecha a dívida — um braço que passa ou falha conforme a fase do ciclo de
outra lane não é um braço.

---

## 4. `wake-fix.py` e o bug do `like '%* * * *'`

O briefing mandava confirmar, não assumir. **Li os dois lados: o CÓDIGO ESTÁ CORRETO.**
`wake-fix.py` **não usa `LIKE`** — conta os campos:

- `cron_fields()` (`wake-fix.py:112-126`) devolve `expression.split()`, e o consumidor exige
  `len(...) == 5` (`wake-fix.py:249`).
- O docstring de `cron_fields` **documenta os dois padrões errados**
  (`'%* * * * *%'` e `'%* * * *'`) e por que os dois dão 0 linhas.

**Mudei zero linhas de `wake-fix.py`.** O artefato stale era o **receipt**, não o código.
Corrigir código correto seria fabricar um diff para parecer ocupado.

**Nota lateral:** `wake-fix.py:60` ainda descreve o mint antigo
(`f"msg-user-v1-wake{uuid4().hex[:32]}"`), mas a função real (`mint_user_message_id`,
linhas 97-109) usa `secrets.token_urlsafe(32)` — o docstring é stale, **o código não**.
Isso é o que faz `B5` aparecer vermelho no relatório (o `source_has_wake_mint` procura o
padrão antigo). **Fora do meu escopo**: `wake-fix.py` não é meu arquivo, e "consertar" B5
sem essa decisão seria apagar um vermelho verdadeiro.

---

## 5. BOTH COLOURS

Comando (sem pipe em comando nativo; exit code lido de `$LASTEXITCODE`):

```
pwsh -NoProfile -File _main\_lane16-wake-gate.ps1            → rc live
pwsh -NoProfile -File _main\_lane16-wake-gate.ps1 -NegArm   → rc negarm
```

O `-NegArm` gera uma **CÓPIA** com apenas as correções revertidas (cada revert é conferido:
padrão ausente ⇒ o neg-arm **erra em vez de certificar nada**), e alimenta as **duas** com as
**mesmas** medições doctoradas:

- `A1`: 1 contra-exemplo numa população api-linked de 80
- `D2`: vetor `'2,2,2,2,0'` — 4 de 5 injeções ainda recusando
- `B4`: idade 30 min, dentro da banda de flapping
- `L1/L4`: latência mediana forçada a **42 min** — o número exato do briefing — **com o
  gap de entrega→entrada deixado saudável**

O quarto doctor é o achado do briefing virado em máquina: o gate corrigido lê a latência e
**fica vermelho**; a cópia revertida lê o gap e **fica verde** sobre os mesmos dados.

`NEG1` fixo vai vermelho · `NEG2` revertido não vê · `NEG3` verde no store real.
Resultado e códigos de saída: ver `_main/_lane16-gate-*.out.txt` e o relatório final.

---

## 6. POPULAÇÃO honesta: braços que continuam vermelhos

Este gate **não fecha verde hoje**, e isso é o resultado correto:

- **`B5-minted-userMessageId-shape`** — `source_has_wake_mint = False`, porque o mint real já
  migrou para `token_urlsafe(32)` e o braço procura o literal antigo. A store tem
  **2 linhas** com o prefixo `msg-user-v1-wake` (len 48) contra **5578** com len 55 — são as
  duas linhas históricas, de antes do fix. O brazo pede evidência que **a store não tem**
  para o código atual.
- **`C1-task-fires-in-window`** — a cadência real da task é impecável (§3); o vermelho é do
  regex, não do sistema.

**Não os apaguei para fabricar um verde.** Um gate que só fecha quando a reality combina com
ele é um gate que mente quando ela não combina — que é o defeito inteiro.

---

## 7. Limites desta lane

- Só toquei `_main/_lane16-wake-gate.ps1` e este receipt.
- **Não** toquei `_main/heartbeat.ps1` (outra lane, meio de transporte em troca),
  `src/**`, `receipts/receipt-21*`, `receipts/receipt-23*`, `receipts/receipt-14*`,
  `_main/DEBT-LEDGER.md`.
- Probe lançado com `CreateNoWindow`/`Hidden`; braço `E1` censo o próprio pid tree.
- Sem console visível; `py` sempre com redirecionamento para arquivo antes do exit code.

## 8. Reproduzir

```
py -3 _main\_lane16-latency-pairings.py    # as 5 regras de pareamento; qual reproduz 2537 s
py -3 _main\_lane16-latency-measure.py     # a latência por identidade + o gap
py -3 _main\_lane16-outcome-census.py      # a perda de entrega e o vocabulário que C1 ignora
pwsh -NoProfile -File _main\_lane16-wake-gate.ps1
pwsh -NoProfile -File _main\_lane16-wake-gate.ps1 -NegArm
```