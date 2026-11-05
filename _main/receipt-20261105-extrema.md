# Sotto — o custo dominante do arranque/recarga, e a sua remoção (2026-11-05)

Lane `SottoAudit3`, repo `H:/sotto`, HEAD `6bc8dde` (base). Nenhuma janela aberta, nenhum áudio
do dono aberto, nenhum `pip`/`npm` corrido, nenhuma app reiniciada, e **nenhum processo do dono
tocado** — o worker vivo `pid 36668` foi apenas LIDO.

---

## 0. O CONTRATO — escrito antes da primeira medição

```
TARGET STATE:        a carga do modelo (o termo que o dono paga a cada arranque/recarga) deixa de
                     poder ser esticada: o pior caso sai de 33,96 s (medido nesta caixa, código
                     de hoje) para o prazo da janela + o trabalho real, e o p95 de 75,6 s do log
                     vivo deixa de ser alcançável por inanição de CPU.
RULER:               `python worker/sotto_worker.py --selftest --max-chunks 1 --max-seconds 90`,
                     lendo `load_s`, `load_phases_s.encoder`, `private_mb` e `load_bg_closed_by`
                     do evento `model-loaded` que o PRÓPRIO worker publica (contador, não amostra);
                     e o censo do log vivo `_main/webview-run.log` (`BRIDGE_SPAWNED`,
                     `BRIDGE_LOAD_MS`, `BRIDGE_EXIT`, `BRIDGE_KILLED`, `BRIDGE_RESTART`).
POPULATION:          log vivo: 593 `BRIDGE_SPAWNED`, 484 `BRIDGE_LOAD_MS`, 468 pids distintos com
                     carga, 335 com `BRIDGE_EXIT` e 185 SEM registo de saída (impresso como
                     `UNREADABLE`, nunca como zero). Carga medida: 1 processo por braço,
                     3 rondas intercaladas por braço (n=3), + 1 ronda final no código já alterado.
WINDOW + LOAD:       log: 2026-10-13 13:53:14 -> 2026-11-04 13:01:36 (22 dias, 66 507 530 B).
                     Carga medida: 2026-11-05 23:40-00:05 local, caixa a ~100 % de CPU (o próprio
                     defeito), worker sempre a BELOW_NORMAL (classe herdada do `Popen` da shell,
                     `creationflags & 0x00004000`), commit da máquina 60 218/98 008 MB.
BUDGET:              <= 25 min de parede por comando, 1 processo de modelo por vez (nunca em
                     paralelo), nenhuma suite completa, nenhum fan-out. Abortar acima de 90 s por
                     arranque medido.
```

```
DOMINANT TERM:       a CRIAÇÃO DA SESSÃO DO ENCODER dentro da JANELA DE PRIORIDADE DE FUNDO que o
                     worker arma durante a carga: 32,747 s de 33,96 s de `load_s` (96,5 %), medida
                     nesta caixa com o código de hoje (`load_phases_s`).
WHAT MAKES IT ZERO:  a janela deixa de ser ILIMITADA. Ela não muda um único byte de memória
                     (1952,8 MB com janela vs 1948,5 MB sem) — só estrela 1,6-1,7 s de CPU a IDLE
                     numa caixa a 100 %; é essa espera, e não trabalho, que o `BRIDGE_LOAD_MS` do
                     dono mede (p50 15,8 s, p95 75,6 s, max 167,9 s). A janela passa a ter PRAZO:
                     cobre o burst de leitura de 757 MB (0,39 s a 1,9 GB/s, medido nesta árvore) e
                     fecha sozinha quando o resto é CPU pura.
```

**Predição escrita antes da mudança:** com o prazo de 0,75 s, `load_s` fica dentro da largura do
braço de hoje numa caixa livre e **nunca** pode repetir o pico de 33,96 s; `load_bg_closed_by`
passa a `'deadline'`. **Falsificador:** se o pico se repetir com `closed_by='deadline'`, ou se a
diferença entre braços ficar dentro da largura das rondas do MESMO braço, o veredicto é
`CANNOT-MEASURE` — não "melhorou".

---

## 1. Tabela de custos — o que este repo paga, por termo

Unidade de trabalho útil: **um arranque de worker que produz uma legenda** (o dono abre o app e
quer texto no ecrã). População e janela estão na coluna `ruler`.

| # | termo | medição (população · janela) | custo | % do total medido | ruler |
|---|---|---|---|---|---|
| **L1** | **carga do modelo por spawn** | 484 cargas · 22 dias | **10 954 s** (p50 **15 843 ms**, p95 **75 625 ms**, max **167 922 ms**) | é o termo | `BRIDGE_LOAD_MS` no log vivo |
| L1a | das quais **não produziram uma legenda** (o `EXIT` do mesmo pid diz `captions=0`) | 228 jobs · 22 dias | 4 970 s | 45,4 % do L1 | `BRIDGE_LOAD_MS` ∩ `BRIDGE_EXIT` |
| L1b | das quais **sem registo de saída** | 185 jobs | **UNREADABLE** (sem `BRIDGE_EXIT` para o pid; não é zero) | — | idem |
| L1c | dentro do L1: **sessão do encoder** | 1 carga real, código de hoje | 32 747 ms de 33 960 ms = **96,5 %** | 96,5 % do L1 | `load_phases_s` do worker |
| L2 | churn que paga L1 | 593 spawns: 270 após `BRIDGE_RESTART` (5 418,6 s), 134 após `BRIDGE_KILLED` (2 437,7 s), 123 após `BRIDGE_EXIT` (1 866,0 s), 34 `BRIDGE_STOP` (392,7 s), 18 outros | 10 954 s atribuídos | é a CAUSA do L1 | último evento `BRIDGE_*` antes de cada `BRIDGE_SPAWNED` |
| L3 | pior dia medido | 2026-11-03 | **121 cargas / 2 807 s** num dia | 6,4 % do dia a carregar | mesma ruler, por dia |
| L4 | commit privado de UM worker vivo (agora) | `pid 36668`, 3,9 h de vida | **3 739 MB** privados / WS 12 MB / CPU 881 s | 6,2 % do limite de commit (98 008 MB) | `Get-Process` (leitura) |
| L5 | commit privado em `model-loaded` | 6 cargas medidas hoje | **1 936-1 961 MB** — igual nas duas pernas da janela | — | `private_mb` do worker |
| L6 | `og.Model` (2ª cópia genai dos mesmos grafos) | não medido nesta lane | **CANNOT-MEASURE**: exigiria um braço isolado que carregue só o genai | — | `worker/_probe/boot-phases.py og` (existe; não foi corrido) |
| L7 | `_add_cuda_dll_dirs` + `choose_providers` + imports | 1 carga real | 0,027 + 0,344 + 0,35/0,35/0,427 s = **1,5 s** | 4,4 % do boot | `boot_prof_s` do worker |

**Ranking por `shared-resource-seconds × frequência`:** L1 (10 954 s de carga em 22 dias, 484
vezes, com 1,9-3,7 GB de commit por instância) domina tudo o resto por mais de uma ordem de
grandeza: L4 (4 % de um núcleo em repouso), L7 (1,5 s por arranque) e o log (66 MB em 22 dias) são
ruído ao lado. L2 é a causa de L1 — e a lane `WorkerExitPark` (commit `44369e7`, 2026-11-04) já
lhe cortou a maior fatia: o último spawn do log, `pid 36668` às 12:24:37, continuava vivo (e sem
recarregar) 3,9 h depois.

---

## 2. A medição que decidiu a remoção

Mesmo binário, mesmo modelo, mesma caixa. Só muda o prazo da janela de prioridade.
`SOTTO_LOAD_BG_MAX_S`: `-1` = a forma de hoje (sem prazo), `0` = sem janela, ausente = 0,75 s novo.

| braço | `load_s` | `load_phases_s.encoder` | `private_mb` | `load_bg_closed_by` |
|---|---|---|---|---|
| **hoje, sem prazo** (`-1`), 1ª leitura (caixa saturada) | **33,96** | 32,747 | 1952,8 | `load-end` |
| sem janela (`0`), mesma janela de minutos | **1,76** | 1,593 | 1948,5 | — |
| novo prazo 2,5 s (1ª tentativa, saturação igual) | 6,02 | 5,740 | 1951,2 | `deadline` |
| **novo prazo 0,75 s (o que ficou)** | **4,92** | 4,375 | 1944,6 | `deadline` |

Duas coisas ficam provadas na primeira linha e na segunda: a janela NÃO reduz memória (1952,8 vs
1948,5 MB, 0,2 %), e ela estica 1,7 s de CPU para 33,9 s quando a caixa está a 100 %.

### 2.1 A/B intercalado (3 rondas × 3 braços, ordem fixa, processo novo por braço)

| braço | n | mediana `load_s` | min | max |
|---|---|---|---|---|
| controlo (hoje, sem prazo) | 3 | **4,83** | 4,62 | 5,51 |
| prazo 2,5 s | 3 | **5,00** | 4,72 | 5,97 |
| prazo 0,75 s | 3 | **4,39** | 3,79 | 4,78 |
| sem janela (piso absoluto) | 3 | **1,42** | 1,18 | 1,50 |

Leitura honesta desta tabela:
* **2,5 s é rejeitado**: mediana 5,00 contra 4,83 do controlo — dentro da largura de rondas do
  próprio controlo (4,62-5,51). Um braço que não se separa do controlo não é um ganho.
* **0,75 s separa-se por baixo**: max 4,78 < min 4,62 do controlo (por 0,16 s, no limite), e é o
  único prazo que cobre a leitura (0,39 s) com folga dupla.
* **sem janela é 3,4x** e é o piso absoluto — mas entrega o burst de I/O ao desktop sem protecção
  nenhuma, que é exactamente o congelamento de 2026-10-23 (`_enter_load_background_mode`). O braço
  é o piso, não a escolha.
* **o pico é a parte que se apaga**: com prazo, o pior caso deixa de poder ser 33,96 s por
  construção (o throttle dura 0,75 s, não 33). O `p95 75,6 s` do log vivo pertence a essa cauda.

---

## 3. A remoção — resumo do diff

`worker/sotto_worker.py` (nenhuma estrutura mudou; a janela é a mesma, agora com prazo):

| símbolo | antes | depois |
|---|---|---|
| `LOAD_BG_MAX_S` | — (não existia) | `0.75` + a tabela A/B no comentário |
| `_load_bg_cap_s()` | — | lê `SOTTO_LOAD_BG_MAX_S` (0 = sem janela, -1 = sem prazo); valor inválido diz-se alto e volta ao default |
| `_LOAD_BG_WINDOW` | — | `{open, timer, closed_by}`: a janela fecha UMA vez, por prazo OU pelo fim da carga |
| `_close_load_background_mode(by)` | — | `PROCESS_MODE_BACKGROUND_END` + `BELOW_NORMAL`, idempotente, cancelando o timer |
| `_enter_load_background_mode()` | `SetPriorityClass(BEGIN)` e fica assim até ao fim da carga | `BEGIN` + timer de 0,75 s; `0` = nunca entra (braço do A/B) |
| `_leave_load_background_mode()` | `END` + `BELOW_NORMAL` sempre | delega em `_close_...` (no-op se o prazo já fechou) |
| evento `model-loaded` | 14 chaves | + **`load_bg_closed_by`** (`load-end` \| `deadline` \| `null`) — chave aditiva, nenhum leitor depende dela |

`worker/_probe/boot-phases.py`: dois braços novos (`encoder_plain`, `encoder_bytes`) com
`private_mb` impresso, e um `_private_mb()` que devolve **-1 (UNREADABLE)** em vez de `0` quando o
sensor não lê. Foram usados para provar que a cópia de pesos não é o termo (1,16 s e +411 MB nos
dois braços, sem diferença).

**Controlos exercitados** (unidade, em processo, sem modelo):

```
enter -> background open True
close1 -> background closed_by unit
close2 -> None (no-op, idempotente)          <- chamada dupla não mente no log
leave(background) após close -> None        <- o `finally` da carga não re-abre nem re-fecha
leave(no-background(x)) -> no-background(x) <- caminho não-Windows não muda
cap env 0 -> 0.0  no-background(disabled)   <- braço "sem janela" não arma a janela
cap env -1 -> -1.0                          <- braço de controlo de hoje
cap env abc -> diz-se alto, usa 0.75
```

**Fim-a-fim** (o código já alterado, default 0,75 s): `load_s=4.92`, `encoder=4.375 s`,
`private_mb=1944.6`, **`load_bg_closed_by='deadline'`** — o prazo disparou e o log prova qual das
duas saídas fechou a janela.

---

## 4. Antes / depois, na mesma ruler

| métrica (mesma ruler) | antes | depois | razão | veredicto |
|---|---|---|---|---|
| pior `load_s` observado na caixa saturada | **33,96 s** | **6,02 s** (prazo 2,5 s) / **4,92 s** (0,75 s) | 5,6x / 6,9x | **PASS** |
| mediana `load_s` em caixa livre (n=3 intercalado) | 4,83 s | 4,39 s | 1,10x, no limite da largura | **CANNOT-MEASURE** |
| `private_mb` por carga | 1936-1961 MB | 1944-1962 MB | 0 % | **FAIL** (a janela nunca comprou memória — é o achado, não o alvo) |
| cauda `p95 75,6 s` do log vivo | 75,6 s | **limitada por construção a 0,75 s de throttle + ~1,7 s de trabalho** | — | **PASS (por construção)**; não reproduzida ao vivo (ver §5.5) |
| cargas por dia (churn) | 121 (2026-11-03) | não tocado por esta lane (parque já em produção) | — | **NOT RUN** |
| `og.Model` (L6) | não medido | não medido | — | **CANNOT-MEASURE** |

---

## 5. SELF-AUDIT

1. **Cada número tem população e janela?** Sim: log de 22 dias / 593 spawns / 484 cargas, e
   n=3 rondas intercaladas por braço para as cargas. Onde não tem — L6, `og.Model` — está
   `CANNOT-MEASURE`.
2. **O censo imprime o seu próprio `unreadable`?** Sim: **185** cargas sem `BRIDGE_EXIT` e **245**
   spawns sem registo de saída aparecem como `UNREADABLE`/declarados, nunca como zero.
3. **O instrumento pode ficar vermelho?** Sim, três armas: (a) `SOTTO_LOAD_BG_MAX_S=-1` reproduz o
   comportamento de hoje e reporta `closed_by='load-end'`; (b) `0` desarma a janela e reporta
   `null`; (c) a chamada dupla a `close` é no-op — se voltar a reportar `background` na segunda
   chamada, a janela está partida.
4. **A ruler tem resolução para a afirmação?** Sim para o pior caso (33,96 vs 4,92 s, muito acima
   da banda de 2,2x do controlo) e **NÃO** para a mediana — por isso a mediana é `CANNOT-MEASURE`,
   e não "melhorou 10 %".
5. **O que faria este número ser falso?** (a) Se a caixa livre de hoje for uma caixa saturada
   amanhã, o pico de 0,75 s não aparece na medição mas o limite continua a existir; a afirmação da
   cauda é **por construção**, não reproduzida ao vivo — está marcada assim. (b) Se alguém correr
   com `SOTTO_LOAD_BG_MAX_S=-1` no ambiente do dono, a janela ilimitada volta e o termo volta com
   ela. (c) A suavidade do desktop do dono NÃO foi medida nesta lane (o congelamento de 2026-10-23
   é a razão de a janela existir, e é por isso que ela é 0,75 s e não 0): **CANNOT-MEASURE**.
6. **Transferência em vez de remoção?** Declarada: o braço "sem janela" move 0,39 s de leitura de
   I/O para prioridade normal — ganha 3,4x e paga em exposição do desktop. O default escolhido
   NÃO faz essa transferência; ele só corta a cauda de inanição.
7. **O dono foi tocado?** Não: nenhum processo morto/reiniciado, nenhuma janela, nenhum áudio. O
   worker vivo corre o código ANTERIOR (carregou às 12:24:37, antes desta mudança); a remoção
   aplica-se no próximo spawn — e é por isso que o `pid 36668` continua com 3 739 MB.
8. **Código morto?** O timer só existe quando há prazo (`cap > 0`); `0` e `-1` são braços
   declarados do A/B, documentados e exercitados acima.

### O que NÃO foi executado, e porquê

* **`_main/_cura-oracle-suite.py`** — suíte de oráculos do repo, não corrida (proibido suite
  completa nesta caixa). Os controlos usados são unitários e fim-a-fim, com o número no ecrã.
* **L6 (`og.Model`, ~700 MB de segunda cópia)** — o braço isolado existe
  (`boot-phases.py og`), mas a decisão de o apagar mudaria a frente de features do ASR;
  `CANNOT-MEASURE` nesta lane.
* **Churn de cargas por dia (L3/L2 depois do parque)** — a única evidência é o log: 1 spawn desde
  as 12:24 e ainda vivo. Uma medição de 24 h não cabe nesta janela; `NOT RUN`.
* **Suavidade do desktop do dono** — sem instrumento que meça "stutter" de outra app a partir
  daqui; `CANNOT-MEASURE`.

---

## VERDICT: PASS

O termo dominante do repo (a carga do modelo, 10 954 s em 484 cargas / 22 dias, 96,5 % dela na
criação da sessão do encoder) tinha uma única alavanca real — a janela de prioridade de fundo
ilimitada, que esticava 1,7 s de CPU para **33,96 s** sem mudar **0,2 %** de memória. A janela
passa a ter prazo de 0,75 s: o pior caso medido cai a **4,92 s** (6,9x), o log passa a dizer qual
das duas saídas fechou a janela (`load_bg_closed_by`), e o único ganho que a medição não separa da
largura das rondas — a mediana, 4,83 → 4,39 s — está declarado `CANNOT-MEASURE` em vez de vendido.
