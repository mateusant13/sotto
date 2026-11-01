# RECIBO — a bateria que ficou em 0 B, e os portões que a voltaram a fazer medir (2026-10-30)

Lane desta sessão: `H:\sotto` (raiz git). Nenhuma janela foi aberta, nenhum dispositivo
de áudio foi tocado, nenhum commit foi feito. `TMPDIR=I:\cc-tmp`.

---

## 0. O incidente: `_main\_audit-verify-all.cmd` ficou com 0 bytes

**O que aconteceu.** Um script de reconstrução abriu o ficheiro com

```python
io.open(p, 'wb')
```

e levantou excepção **depois** do `open` e **antes** do `write`. O `'wb'` trunca no
`open`: o ficheiro ficou com **0 B** e a bateria passou a correr um `.cmd` vazio (exit 0,
zero passos, nenhum portão). Não havia cópia de segurança do conteúdo do dia.

**A recuperação, e porque é reconstrução e não restauro.** Duas fontes independentes:

| fonte | o que deu |
|---|---|
| `git show HEAD:_main/_audit-verify-all.cmd` | 115 passos declarados |
| `_cache/battery-steps.json` | **169** passos que JÁ CORRERAM, cada um com o `rc` medido |

`_main/_battery-restore-steps.py` comparou as duas listas e nomeou **28** passos que o
registo provava existirem e que o `HEAD` não declarava. Cada um foi reconstruído com o
**comando** provado pelo registo (nome, dependências, log, argumentos) — não com um
comando inventado.

**Estado medido depois do restauro:** **171 passos declarados / 169 no registo / 0 em falta.**

**A lição, escrita onde se lê:** um `open(p,'wb')` é um truncate. Um script que escreve
um ficheiro da casa escreve primeiro num temporário e faz `os.replace` no fim — ou nunca
abre em `'wb'` antes de ter o conteúdo novo inteiro em memória.

---

## 1. O defeito que o restauro criou, e o portão novo que o impede

Os 28 passos restaurados foram declarados `always`. **Dois deles largam a app**:
`shell-relaunch` e o seu braço negativo (`--neg-arm` repõe o direito culpado e exige o
`err=5` de volta, o que exige uma instância viva).

**MEDIDO:** o log da app tem dois `SHELL_STARTUP_STAGE` nos dois minutos em que a bateria
correu — `pid 8992` às 12:07:05 e `pid 33300` às 12:09:12 — um por cada passo. A regra
`SOTTO_NEVER_ON_OWNER_SCREEN` foi violada **duas vezes por um passo da bateria**.

**A correcção.** Os dois passos passaram a `heavy` (a classe que não corre sem
`SOTTO_BATTERY_HEAVY=1`), e um portão novo recusa a recaída:

`_main/battery-class-oracle.py` (6577 B, sha256 `C72AF5D1A7BC2670…`)

| arm | o que exige |
|---|---|
| 1 | nenhum passo `always` corre um LARGADOR (lista de módulos que sobem a app) |
| 2 | cada largador nomeado existe no repo |
| 3 | `shell-relaunch` e o seu negativo estão declarados `heavy` |

Veredicto: `BATTERY-CLASS VERDICT PASS -- arms=3 fail=0`, e o `--neg-arm`
(`heavy → always`) é **caught and named**: `NEG-ARM PASS -- RED as designed`, rc=1.

O parser mede três formas reais que a primeira versão não lia: `call :step always heavy
<passo>`, `py_compile` de um ficheiro (não é largada) e um largador citado só na lista de
dependências (não é execução).

---

## 2. Quatro oráculos de 2026-10-30 ligados, com o sinal certo

`stale-display`, `battery-class`, `live-queue` e `flat-endpoint` passaram a ter passo na
bateria. A primeira ligação expôs **a convenção de rc que eu não segui**: o `:expectred`
exige **rc=1**, e os meus braços negativos devolviam **0** (o valor "correu bem").

| oráculo | normal | negativo |
|---|---|---|
| `stale-display-oracle.py` | 0 PASS / 2 setup | **1** RED-as-designed / 2 setup |
| `live-queue-oracle.py` | 0 / 2 | **1** / 2 |
| `battery-class-oracle.py` | 0 / 2 | **1** / 2 |
| `flat-endpoint-oracle.py` | 0 / 2 | — (o controle está DENTRO: a cópia congelada tem de dar RED) |

O `flat-endpoint` não tem `--neg-arm` e por isso o par `red-as-expected-flat-endpoint`
foi **retirado** — um par que chamava um argumento inexistente seria um vermelho
decorativo.

**Segundo defeito medido, no `live-queue`:** a primeira versão do braço negativo
devolvia `1` também no run NORMAL, e o passo positivo registava `VERDICT PASS` com
`rc=1`. O `:step` leu-o como falha (1 passo vermelho na bateria) e a mensagem do oráculo
era verde. Agora o rc depende do modo: normal 0/2, negativo 1/2.

---

## 3. Pares aposentados que ficaram a acusar

| passo | porquê saiu |
|---|---|
| `search-twin-parity` + `red-as-expected-search-twin-parity` | o segundo motor (JS/Soundex) **não existe** na árvore; o par publicava `MISSING`/`rc=0` sobre um ficheiro que não tem o que o oráculo julga |
| `hotkey-cycle`, `hotkey-gesture`, `hotkey-triple` | mediam 1/2/3 pressões dentro de uma janela; o gesto de hoje (1 tap = painel de baixo, 2 taps = painel da direita, HOLD = live on/off) vive em `app/webview/hotkey_gesture.py` |

---

## 4. `state-page` corria antes do passo que a escreve

O par é `--write` e **depois** `--check`: o `--check` compara as células da página com o
registo VIVO, por isso um `--check` antes do `--write` reprova sempre. O `state-page-write`
estava no fim da `.cmd` e o `state-page` a `:530`. Movido: **write em `:530`, check em
`:534`**.

---

## 5. `word-split-oracle.py` — os registos de 2026-10-07 deixaram de ser portão

**O estado à entrada:** 4 arms vermelhos.

**A causa, medida e não suposta.** O oráculo comparava o replay puro com dois registos
reais de **2026-10-07**, e a **decode mudou**: a sonda `_main/word-split-trace.py`
re-corrida ao lado do ficheiro de 2026-10-07 mostra que os chunks **4, 5, 10, 11, 12 e 15**
já não dão o mesmo texto (`próx`+`ima` saíam partidos, hoje sai `próxima` inteiro; `Os`
passou a `os`; `segunda-feira.` passou a `segunda feira`). Comparar com aquele registo
media o **modelo de então**, não a correcção do join.

**O que foi feito (com a razão escrita dentro do ficheiro):**

1. `word-split-trace.py`: a sonda estava parada na assinatura antiga
   (`StreamAsr(providers=None)` → `TypeError: 'NoneType' object is not iterable`).
   Passou a pedir a lista a `choose_providers(...)`, i.e. a mesma que a app usa.
   Trace regravado do worker vivo (**26 chunks**, worker sha256 `76DC526C…`).
2. `_wordsplit-after.jsonl` regravado de um `--selftest` **real** (`rc=0`, 21 captions,
   `done.text` presente) — o registo passou a ser do código de hoje.
3. **arm 1** deixou de comparar com o registo de 2026-10-07 e afirma a forma do trace
   (uma passagem, 26 chunks, com `ids`/`raw`/`stripped`/`start`/`end`).
4. **arm 2** deriva a lista de palavras partidas **do trace de hoje** (para cada costura
   que o modelo marcou como meio-de-palavra) em vez de fixar `["próx ima", "preci m"]`,
   e verifica que o texto ENVIADO não as contém — lendo o **registo real**, não o replay,
   para o braço de controlo não herdar a mutação.
5. **arm 12** (`done.text`) deixou de exigir `gt == gt_before` (é uma afirmação sobre a
   decode de 2026-10-07); exige que os finais DESTE run estejam no `done.text` DESTE run,
   que os finais concatenados igualem o `done.text`, e que nenhuma palavra partida
   apareça dos dois lados.
6. `_revert_stable_rule` foi re-apontado: a regra da palavra provada mudou de forma
   (`stable_text(self.line())` → `proven_text(self._words)` devolve `(provado, cauda)`),
   e o mutante tem de reverter a chamada **que existe**.

**Veredicto:** `word-split-oracle: 12 PASS / 0 FAIL`, `VERDICT: PASS`; `--neg-arm`
→ **7 FIX arms RED as required, 0 stayed green, 0 controls broke** → `NEG-ARM PASS`, rc=1.

---

## 6. `open-close-stall` F4: o braço pinava um número que o dono tinha mudado

F4 exigia `WORKER_PRELOAD_DELAY_S > 0`. O dono, a 2026-10-30, pediu o contrário —
*"a porra da legenda ao vivo levou uns 20 segundos pra começar a mostrar. não era pra
essa merda estar carregada desde sempre e mostrar IMEDIATAMENTE?"* — e o valor passou a
**0.0**. O invariante que sobrevive aos dois dias: o preload é **deferido** (nunca corre
no chamador), tem escape `SOTTO_NO_PRELOAD`, o motivo `'preload'` é aceite, e a espera
pelo dono quieto continua escrita para quem passar um atraso
(`base <= 0.0 or idle >= WORKER_PRELOAD_IDLE_S`). F4 passou a medir isso.

`VERDICT: PASS` (5 factos) e `NEG-ARM 5 of 5 mutant(s) caught`.

---

## 7. `code-health`: o piso subiu onde o dono mandou crescer

Cinco métricas em dois ficheiros, todas de trabalho desta data (a regra da palavra
provada ao nível do token em `worker/sotto_worker.py`, e o atraso de preload em
`app/webview/sotto_webview.py`):

| ficheiro | bytes | linhas | max_func |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 798942 → 799682 | 15239 → 15257 | — |
| `worker/sotto_worker.py` | 398096 → 399036 | 7457 → 7479 | 2311 → 2333 |

O baseline foi elevado **exactamente** a estes números e `measured` passou a
`2026-10-30`. `CODE-HEALTH VERDICT PASS` (`piorem: 0 métrica(s)`), `--neg-arm`
`3 of 3 mutant(s) caught`.

---

## 8. `battery-wiring`: a dívida de `flat-endpoint-oracle.py` paga

O oráculo passou a estar ligado, por isso a sua entrada no baseline (que só pode
descrever dívida) tornou-se falsa: `baseline-orphans FAIL`. Entrada removida
(**113 → 112**), e o `battery-wiring` fecha `populacao=179 ligados=67 sem_passo=112
ceiling=124`, `PASS checks=7 fail=0`, `NEG-ARM PASS mutations=6`.

---

## 9. `altc-first-caption`: uma sessão de um build antigo não é medição de hoje

O passo publicava **19030 ms** contra um orçamento de 1500 ms, medido numa sessão de
**11:26** — e no disco já corria outro código. O log já trazia a identidade de cada build
(`SHELL_CODE_ID sha256=…`); o oráculo passou a lê-la:

* cada sessão fica com o `code` do seu arranque;
* o id do disco é calculado pelo próprio shell (`code_identity()`, a mesma fonte que
  `live-code-freshness-oracle.py` compara);
* uma sessão cujo build **não** é o do disco (ou que não declara build nenhum) **não dá
  veredicto**: `NO-MEASURE (rc=2)` e os dois ids nomeados.

Resultado de hoje: `MEDICAO AUSENTE: nenhuma sessao com pressao nasceu do build que
esta' no disco (disco sha256=00B9B7FEDB7C)` → rc=2. O passo passou a `heavy` com a
razão escrita na `.cmd`: **mede um gesto do dono**, e nenhum passo o pode produzir.
`--neg-arm`: `NEG-ARM PASS cases=7`.

A classe pesada ganhou o motivo `owner-hand` em `_main/battery-heavy-gate.py`
(`HEAVY_KINDS`), com a nota de que não é "sem classe": é uma classe própria porque
nenhuma bandeira de ambiente a produz.

---

## 10. As três leis novas do epoch/slot entraram no inventário do portão

`bend_core/LAWS.bend` passou a **14 leis** e `NEGATIVE_*.bend` a **14 controlos**
(`Cap.epoch_monotonic`, `Nat.no_cross_source_paint`,
`Cap.display_clean_before_new_source`). O portão fixa o inventário, por isso
`_main/bend-laws-gate.py` recebeu as três leis e os três controlos.

* `python _main/bend-laws-gate.py` → **gate green** (14 controlos, cada um com o
  `Location:` exacto, mais os dois tamper probes);
* `bend PROOF.bend --verdict` em WSL `ubuntu-bend` → `ALL PROOFS CHECK`, rc=0;
* `bend_core/model.py` → **1238** casos, GREEN; `--neg-arm` viola **7** leis, rc=1;
* `docs/bend/README.md`: `11 laws` / `11 controls` → **14** / **14** (re-medido 2026-10-30).

---

## 11. SELF-AUDIT

| # | pergunta | resposta medida |
|---|---|---|
| 1 | a app foi aberta visivelmente por esta lane? | **Não pelo meu trabalho directo.** E **sim** duas vezes por passos da bateria que a reconstrução declarou `always` — está no §1, com os dois pids e as horas, e o portão que impede a recaída |
| 2 | algum teste foi re-pinado sem prova? | Não. O que mudou: `code-health` baseline (§7, números exactos), `battery-wiring` baseline (§8, dívida paga), e três arms do `word-split` cuja fonte de comparação deixou de existir (§5, com a medição da decode) |
| 3 | algum instrumento foi desligado para ficar verde? | Só pares aposentados por ordem/dead code (§3), e um passo medido-passado a `heavy` com a razão escrita (§9) |
| 4 | o pin do `.cmd` foi re-medido? | Sim: **145028 B / 1894 CRLF / 0 bare LF**, sha256 `6D2F4EA847B4B26EBFFF9821F2C54C795A5063506A4060C3BA79A51423ACC221`; `agents-md-pins-oracle.py` → `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` |
| 5 | algum braço negativo foi exercitado? | Todos os tocados: `battery-class`, `stale-display`, `live-queue`, `word-split`, `open-close-stall`, `battery-wiring`, `code-health`, `battery-heavy-gate`, `bend-laws`, `altc-first-caption` |
| 6 | editei a `.cmd` enquanto ela corria? | **Sim, uma vez** (§12). Os dois passos que apareceram corrompidos nesse run (`live-queue`, `red-as-expected-border-radius-gate`) fecharam verdes no run seguinte |

---

## 12. O segundo erro meu, e como se viu

Editei `_main/_audit-verify-all.cmd` **enquanto a bateria a corria** (normalizei quatro
`LF` sozinhos para `CRLF`). O `cmd.exe` lê o ficheiro batch por deslocamento, e o run
publicou `live-queue=1` e `red-as-expected-border-radius-gate=<um caminho de ficheiro>`
— um rc que é um caminho é a assinatura de uma linha lida a meio. Os dois oráculos,
corridos à mão, estavam verdes.

**Regra:** uma `.cmd` que está a correr não se edita. Mede-se, espera-se o veredicto,
edita-se depois.

---

## 13. Veredicto final

```
steps    : 171   gate=100  control=8  skipped=9  expect-red=54  missing=0  cached=98
failed   : -none-
skipped  : mute-audio strip-stats-log-budget strip-surface-runtime strip-geometry-restore
           strip-stats-wave hotkey-delivery control-panel-exit3-neg-arm altc-first-caption
           red-as-expected-shell-relaunch shell-relaunch
BATTERY-VERDICT: GREEN WITH 9 SKIPPED - 9 step(s) did NOT verify this run and are NOT
counted as gates (all 9 are the HEAVY class)
exit-code: 0
```

**A serie, medida nesta sessao:** 19 falhas (bat4, 12:0x, com a `.cmd` reconstruida mas com os
passos novos declarados `always` e a `.cmd` desalinhada) -> 3 (bat5) -> 1 (bat6: o rc do
`live-queue`) -> 1 (bat7: `launch-as-token`, prazo de 8 s curto para esta maquina) -> **0 (bat8)**.

**Duas notas que ficam escritas:**

1. **Nao sao 171 portoes verdes: sao 171 passos, 9 deles sem verificar** — todos da classe
   `heavy`. (No run anterior eram 10: o `hotkey-delivery` correu neste.)
2. **`altc-first-caption` e' medivel hoje por uma so' pessoa:** o dono, a premir Alt+C numa sessao
   nascida do build que esta' no disco. O oraculo ja' recusa veredicto de qualquer outra coisa.

