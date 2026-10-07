# Recibo — `_main/caption-lines-oracle.py` (RED na suite, 2026-10-07)

**Lane:** `SottoCaptionLines` · **Repo:** `H:/sotto` · **Data:** 2026-10-07
**Alvo:** `_main/caption-lines-oracle.py` — rc=1 na corrida da suite `_main/_cura-oracle-suite.py`
(`SUITE: GREEN=13, RED=3, rc=3=1`).
**Ambito:** so o Sotto (ordem do dono). Nao toquei `I:/!manager` nem hooks/extensoes omp.
**Janela/audio:** o oraculo e' "No window: pure file reads" — NAO abriu janela e NAO abriu
dispositivo de audio nenhum (nao ha' risco de ser audivel ao dono).

---

## 1. A corrida ALONE — output VERBATIM

```
$ py -3 _main/caption-lines-oracle.py
[PASS] arm: a >= SENTENCE_GAP_S silence splits the line
       real    = ['hello there', 'again']
       want    = ['hello there', 'again']
       control = ['hello', 'there', 'again']  (must differ: yes)
[PASS] arm: a 2.80s gap keeps ONE line
       real    = ['this is one sentence']
       want    = ['this is one sentence']
       control = ['this is', 'one sentence']  (must differ: yes)
[PASS] arm: terminal punctuation closes the line
       real    = ['the roads are closed.', 'we go home']
       want    = ['the roads are closed.', 'we go home']
       control = ['the roads', 'are closed.', 'we go home']  (must differ: yes)
[PASS] arm: the char cap splits instead of overflowing
       real    = (True, True)
       want    = (True, True)
       control = (True, False)  (must differ: yes)
[PASS] arm: min_chars floors the LINE, not the fragment
       real    = ['ok go']
       want    = ['ok go']
       control = []  (must differ: yes)
[PASS] arm: partial=true emits the growing line
       real    = ['going', 'going along', 'going along the road']
       want    = ['going', 'going along', 'going along the road']
       control = ['going', 'along', 'the road']  (must differ: yes)
[PASS] arm: partial=false emits only the closed line
       real    = ['going along the road']
       want    = ['going along the road']
       control = ['going', 'along', 'the road']  (must differ: yes)
[PASS] arm: start is the line's start, not the newest chunk's
       real    = [0.0, 0.0, 0.0]
       want    = [0.0, 0.0, 0.0]
       control = [0.0, 0.5, 1.0]  (must differ: yes)
[PASS] arm: flush does not re-send the text it already showed
       real    = (['held', 'held back'], 1)
       want    = (['held', 'held back'], 1)
       control = (['held', 'back'], 0)  (must differ: yes)
Traceback (most recent call last):
  File "H:\sotto\_main\caption-lines-oracle.py", line 252, in <module>
    sys.exit(main())
             ^^^^^^
  File "H:\sotto\_main\caption-lines-oracle.py", line 221, in main
    wire11 = W.line_events(f11.take_closed())
             ^^^^^^^^^^^^^
AttributeError: module 'sotto_worker' has no attribute 'line_events'
```

## 2. rc

```
===RC=1===
```

**Nao e' um FAIL limpo: e' um ABORTO.** O traceback mata `main()` na **arm 11**, ANTES da
**arm 10 (dados reais)** e ANTES do **arm de aceitacao** — nenhum dos dois chegou a correr.
Ou seja, o RED esconde o resto: sem a prova independente da §5, nao se saberia que a arm 10 passou.

## 3. `git diff` da sonda (esta' MODIFICADA — e' 1 dos 11 tracked modificados)

`git status --porcelain` → ` M _main/caption-lines-oracle.py` (tracked, modificado, nao committed).

```diff
diff --git a/_main/caption-lines-oracle.py b/_main/caption-lines-oracle.py
index 5cd01a4..9d44be0 100644
--- a/_main/caption-lines-oracle.py
+++ b/_main/caption-lines-oracle.py
@@ -31,6 +31,9 @@ ARMS
 10  REAL DATA — replaying the fragments the worker MEASURED on
     `_main/pt-br-sample.wav` (the BEFORE run) through the former reproduces the
     AFTER run caption for caption
+11  the CLOSE is published OUT OF BAND (`take_closed()`), once, and marked
+    `final` (M2/M3 of the live-vs-redux cure): the events `push`/`flush` return
+    are unchanged, and the line the transcript accepts comes from `take_closed()`
 
 Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window: pure file reads.
 """
@@ -202,6 +205,25 @@ def main():
         (captions(drive(_PassThrough, held, emit_partial=True)), 0),
         (["held", "held back"], 1))
 
+    # ── arm 11: the CLOSE is published OUT OF BAND, once, and marked (M2/M3) ─
+    # `push`/`flush` keep returning exactly the events they always did (arm 9),
+    # and the line that CLOSED is collected from `take_closed()`. That split is
+    # the cure: measured on this box, suppressing the close whenever the text
+    # matched what was already shown made a 14.5 s file-mode run emit 3
+    # provisional partials and ZERO finals — a transcript that never receives a
+    # single line. This arm pins BOTH halves: exactly one close, marked final,
+    # and nothing provisional marked final.
+    f11 = W.LineFormer(emit_partial=True)
+    shown11 = []
+    for text, s, e in held:
+        shown11 += f11.push(text, s, e)
+    shown11 += f11.flush()
+    wire11 = W.line_events(f11.take_closed())
+    arm("the close is published once, out of band, and marked final",
+        (captions(shown11), captions(wire11), [bool(x.get("final")) for x in wire11]),
+        (captions(drive(_PassThrough, held, emit_partial=True)), [], []),
+        (["held", "held back"], ["held back"], [True]))
+
     # ── arm 10: REAL DATA — the BEFORE fragments reproduce the AFTER run ────
     before, after = load(BEFORE), load(AFTER)
     real = captions(drive(W.LineFormer, before, emit_partial=True))
```

A modificacao acrescenta **so** a arm 11 (22 linhas, 0 remocoes). A arm 11 e' a unica causa
proxima do RED. **sha256 da sonda (input, NAO alterado por mim):**
`bf5c48b689190916b3e56f707fa20e16946819093dcb56e98449afd022b0b66d`

## 4. Cadeia de evidencia (porque e' que a arm 11 falha)

1. `W.line_events` e `LineFormer.take_closed()` **nao existem** em
   `H:/sotto/worker/sotto_worker.py`. Medido por `hasattr` no proprio modulo importado:
   `W.line_events present: False`; `LineFormer.take_closed present: False`;
   `LineFormer` tem `push/flush/reset/line`; o modulo NAO tem
   `rerun/reset_stream_state/finalise/drain`.
2. Nunca estiveram em git: `git log -S line_events -- worker/sotto_worker.py` = vazio;
   `git log -S take_closed` = vazio.
3. Nao estao em NENHUMA worktree: `H:/sotto-wt-FlatEndpoint`, `H:/sotto-wt-PanelGap`,
   `H:/sotto-wt-TapRestartLoop` — 0 ocorrencias.
4. Referenciados por **duas** sondas: esta (`caption-lines-oracle.py:221`) e
   `_main/segment-rerun-probe.py:166,170`.
5. A cura M1/M2/M3 que a arm 11 testa foi medida GREEN e **DE-LANDADA** — dito pela propria
   lane: `_main/fragmentacao-receipt.md` §8 e §6b ("ESTADO NO FIM (17:45Z) — a metade de renderer
   foi de-landada ... §1-§6 descrevem uma cura que EU medi GREEN as 13:40Z e que **ja' nao esta'
   no disco**") e `docs/audit/ao-vivo-vs-redux-CURA.md` §6b. Bilhete aberto: **P1
   `4fb5b25380cbc8269977e22e`**.
6. Prova datada de que a API EXISTIA antes da de-landagem: `_main/_cura-oracle-suite-nonapp.json`
   (Oct 6 11:30) traz `segment-rerun-probe` **rc=0, verdict GREEN, wall_s=122.5** — a mesma sonda
   que hoje chama `W.line_events`. Logo a API existia as 11:30Z e desapareceu ate' as 17:45Z.
7. A de-landagem **nao** foi por a M2 ser design morto: o renderer shipped AINDA a espera.
   `app/electron/caption-formulation.js:250-301` diz, verbatim, que "The worker stamps every
   caption event with `final`" e "once `worker/sotto_worker.py:_event` stamps the flag", com um
   FALLBACK documentado para a ausencia (`routeFor()` :296-301, `if (bufferFinal) return 'final';
   if (bufferSawFinal) return 'provisional-draft'; return <reason> ? 'provisional-draft':'final'`).
   O fallback e' o que fez a de-landagem "passar em silencio" (receipt §8: "o `transcript-append-oracle.js`
   continua GREEN porque NAO cobre a rota").

## 5. Prova independente da arm 10 + aceitacao (o traceback escondia-as)

Como a arm 11 aborta antes da arm 10, repeti a arm 10 a' parte (mesma logica: replay dos fragmentos
de `_main/_wav-before.jsonl` por `W.LineFormer(emit_partial=True)` contra `_main/_wav-after.jsonl`):

```
ARM 10 (real data) real==want : True
  n_before_frags = 3  n_after_caps = 3
  real = ['O rádio', 'O rádio Segunda-feira', 'O rádio Segunda-feira Os moradores']
  want = ['O rádio', 'O rádio Segunda-feira', 'O rádio Segunda-feira Os moradores']
ACCEPTANCE (>=3 words): True  longest = 5
```

⇒ A **camada de FORMULACAO de legendas esta' saudavel**. Arms 1-9 PASS, arm 10 PASS,
aceitacao PASS. O unico RED e' a arm 11.

## 6. VERDICT

**REAL — nao uma expectativa stale.** Mas com precisao sobre ONDE esta' o defeito:

- **NAO e' um defeito da camada de formulacao de linhas** (`LineFormer` acumula/fecha linhas
  corretamente: arms 1-9, 10 e aceitacao todos PASS).
- **E' um defeito REAL do WORKER**: `worker/sotto_worker.py` perdeu a metade-M2 da cura M1/M2/M3
  — nao publica o FECHO fora de banda (`take_closed()`), nao tem `line_events()`, e o seu
  `LineFormer._event()` **nao estampa o `final`** que `caption-formulation.js` explicitamente
  espera. A arm 11 desta sonda e' o **unico instrumento do repo** que continua a apanhar isto
  (o proprio receipt da lane o diz: "O unico instrumento que reparou foi o meu oraculo").
- A modificacao da sonda (arm 11) e' a causa PROXIMA do RED, mas **a arm 11 esta' CERTA**: o RED
  deve FICAR RED. **NAO apaguei a arm 11.** Apagar uma assercao verdadeira para a suite ficar verde
  e' exactamente o "modo-de-passar" que o dono reprovou. Tambem **nao toquei `worker/**`**: o
  re-land da M2/M3 e' de outra lane (o irmao `SottoSegmentRerun` cuja sonda partilha a mesma API
  ausente) e tem o P1 `4fb5b25380cbc8269977e22e` aberto; editar o mesmo simbolo agora colidiria.

**Fecho exigido (para a suite ficar verde de VERDADE):** re-landar a metade-M2 no worker
(`_event(text, final=False, closed=False)`, `_close()` a publicar fora de banda, `take_closed()`,
`line_events()`), OU retirar a arm 11 **com** o apontador do P1 — decisao que nao e' deste lane.
Ate' la', este RED e' o SINAL correto, nao ruido.

## 7. `sha256` do que mudei

**Nada.** Esta lane nao alterou nenhum ficheiro de codigo nem o oraculo. Este recibo e' o unico
artefacto novo. Hashes de INPUT (para provar que o probe/worker nao foram tocados por mim):

```
bf5c48b689190916b3e56f707fa20e16946819093dcb56e98449afd022b0b66d  _main/caption-lines-oracle.py
85923bc4aa06da0c6a65d08e404bbf1f442f15de8ae9802b398bdcc3b1481ca9  worker/sotto_worker.py
```

## 8. Coordenacao (nao executada)

Tentei avisar o irmao `SottoSegmentRerun` (a sonda dele, `_main/segment-rerun-probe.py`, chama a
MESMA `W.line_events` ausente — e' o mesmo root cause). O `write` para `agent://` foi RECUSADO por
este build: *"agent://SottoSegmentRerun is an internal address, not a file, and this build exposes
no delegation seam (ctx.executeTool is absent)"*. Fica para o Main relayar.

---

## SELF-AUDIT

- **protocolos em falta** — o gate do selo do teorista recusou o meu primeiro `bash` (a pass
  2026-10-07T04-24Z sem disposicao) e eu despachei-o com `theorist_seal(skip, ...)` antes de
  continuar; nao senti falta de outro protocolo que devesse ter seguido. O que faria diferente:
  ter lido o `git diff` do probe **e** o receipt da lane `SottoFragmentacao` **antes** de correr,
  porque o §8 do receipt ja' nomeia a de-landagem — encurtaria a investigacao em ~metade.
- **verificacao adicional** — corrida e barata, ja' feita: a §5 (arm 10 + aceitacao a' parte),
  que o traceback escondia. Teria aumentado ainda mais a confianca correr a arm 11 contra uma
  COPIA do worker com a M2 re-landada — custo alto (reescrever M1/M3) e colide com o irmao; nao
  feito e declarado.
- **checkboxes novas** — MECANICA: **um oraculo nao pode ABORTAR; uma arm que toca um simbolo
  ausente tem de virar FAIL LIMPO**. Comando: qualquer arm que chame `getattr(W, 'x')` sem
  guarda deveria falhar e deixar correr as restantes (`py -3 _main/caption-lines-oracle.py` tem de
  imprimir as 11 arms + aceitacao). O input que a deixa RED e' exactamente o de hoje: um simbolo
  removido do worker. Hoje, esse aborto escondeu a arm 10 e a aceitacao (só as recuperei a' parte).
- **review por outro subagente** — **sim-com-escopo**: review da leitura de que a arm 11 esta'
  CERTA e deve ficar RED (i.e., que a M2 e' design de registo e nao uma assercao stale) — o
  contra-argumento honesto e' "a M2/M3 foi SUPERADA pela cura no store (`historico-vs-redux`), logo
  a arm 11 devia sair". Nao vale a pena re-rever o resto (leitura de ficheiro + hashes).
- **gate-doubt**:
  - **verde-de-verdade**: o unico "verde" que afirmo e' a §5 (arm 10 + aceitacao), e corrigi-o
    num kernel Python a' parte, com os MESMOS ficheiros JSONL que o oraculo le
    (`_wav-before.jsonl` 23 linhas, `_wav-after.jsonl` 23 linhas, ambos de Oct 6) — nao e' vacuo
    (real==want sobre 3 caption reais, e a aceitacao da' 5 palavras). Os PASS das arms 1-9 sao os
    do run real, com controlo NEGATIVO (`control must differ: yes` em todas). O "RED" da suite foi
    reproduzido por mim a' parte (rc=1), nao aceito de ouvir dizer.
  - **falta-no-gate**: a suite `_cura-oracle-suite.py` mede `rc`, e um oraculo que MORRE a meio
    (traceback) reporta rc=1 igual ao de um FAIL limpo: **um aborto e um FAIL sao indistinguiveis
    no rc**. Cenario que atravessa isto: remover um simbolo do worker faz uma sonda abortar na 1a
    arm que o usa e a suite regista um RED que parece "1 arm falhou" quando na verdade 2 arms +
    a aceitacao nem correram (o de hoje). Alem disso, nada no repo exige que as sondas que citam
    `W.line_events`/`take_closed`/`rerun` estejam consistentes com `worker/sotto_worker.py` — foi
    por isso que a de-landagem passou em silencio em varios oraculos.
  - **gate-melhor** — (a) **cobertura-do-oraculo**: a suite deve distinguir "FAIL" de "ABORT"
    (ex.: exigir a linha final `caption-lines-oracle: N PASS / M FAIL (K arms)` e ficar RED-ABORT
    se ela faltar); input RED = a corrida de hoje (a linha final nunca e' impressa).
    (b) **simbolo-ausente e' RED, nao crash**: a suite deveria fazer um `grep`/`hasattr` dos
    simbolos que as sondas citam antes de as correr. Input RED = hoje (`line_events` ausente).
- **confianca** — **alta** no verdict (a ausencia da API e' medida por `hasattr`, `grep`,
  `git log -S` e em 4 worktrees; a de-landagem esta' documentada pela propria lane; a API existia
  as 11:30Z e nao as 17:45Z). **media** apenas no *porque* da de-landagem (o receipt diz que a
  lane `HistoricoVsRedux` superou PARTE do desenho — nao sei se a M2 do worker foi removida de
  proposito ou por acidente); o que a subiria: o diff/commit que removeu `take_closed`.
- **nao verificado** — (1) QUEM removeu a M2 do worker e SE foi intencional (nao ha' commit: a
  arvore so foi trackada em `5ffeefc` ja' sem a M2); (2) o estado do irmao `SottoSegmentRerun` e
  se esta' a re-landar a MESMA API (nao consegui messagea-lo); (3) o caminho Electron/WebView2 ao
  vivo — nao corrido (nao ha' risco de janela/audio aqui: o oraculo e' leitura de ficheiro).

---

## CACHE/PRICE

Comando (obrigatorio): `bash I:/!manager/scripts/cache-task-report.sh "<session jsonl>"` —
**rc=0**. Fonte: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoCaptionLines.jsonl`

```
## CACHE/PRICE
- task/agent: C:/Users/Administrador/.omp/agent/sessions/--I--!manager--/2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26/SottoCaptionLines.jsonl
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoCaptionLines.jsonl
- cache: read=1702400 write=0 hit=93.0587% (cache-read / input+cache-read); universe: 22 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoCaptionLines.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=19 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/deepseek-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-ca… (CORTADA pela tool)
- when-failed: break_items=100; WHEN=2026-10-06T09:25:46.179000+00:00 | break_items=100; WHEN=2026-10-06T09:25:47.669000+00:00 | break_items=100; WHEN=2026-10-06T09:25:48.916000+00:00 | break_items=74; WHEN=2026-10-06T09:26:06.259000+00:00 | break_items=177; WHEN=2026-10-06T09:26:42.525000+00:00 | break_items=1; WHEN=2026-10-06T09:26:43.530000+00:00 | break_items=1; WHEN=2026-10-06T09:41:09.837000+00:00 | break_items=483; WHEN=2026-10-06T09:55:07.887000+00:00 | break_items=483; WHEN=2026-10-06T09:55:08.063000+00:00 | break_items=40; WHEN=2026-10-06T09:58:23.736000+00:00 | break_items=1; WHEN=2026-10-06T12:17:30.932000+00:00 | break_items=1; WHEN=2026-10-06T13:00:18.694000+00:00 | break_items=1; WHEN=2026-10-06T13:01:28.721000+00:00 | break_items=1; WHEN=2…
- where-failed: session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278746179 | session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791278747669 | session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278748916 | session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=2; turn_id=1791278766259 | session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278802525 | session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-fla…
- report generated_at: 2026-10-07T04:56:48.546308+00:00
- usage rows: 22
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash, opencode-go-4/deepseek-flash
- input tokens: 126983
- output tokens: 33666
- cache-read tokens: 1702400
- cache-write tokens: 0
- hit ratio: 93.0587% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 12142 (state=RESOLVED-BREAKS-OMP; population: 101 of 125848 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', '.../SottoCaptionLines.jsonl', 'SottoCaptionLines']; window: 2026-10-06T09:25:46.179000+00:00..2026-10-07T04:55:58.319000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed: (lista longa — as primeiras linhas em `when-failed`/`where-failed` acima; as ultimas:
  break_items=215 WHEN=2026-10-07T04:50:27 provider=deepseek-flash item_index=0; break_items=1
  WHEN=2026-10-07T04:51:26 provider=deepseek-flash; break_items=2 WHEN=2026-10-07T04:55:58
  session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash item_index=419)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Full instrument output available as `artifact://7441` (the header is what is pasted above;
the WHEN/WHERE lists were truncated by the tool's own 768-char-per-line cap, marked `(CORTADA)`).
