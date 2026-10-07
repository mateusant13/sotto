# Review — the Sotto code that landed 2026-10-07 (the M1–M3 re-land, the History source cut, the `src=` gate, the derived `routeSource`)

**Lane:** `SottoReview` · **data:** 2026-10-07 · **repo:** `H:/sotto` (árvore partilhada;
`# shared-tree-reason: DO NOT request a worktree. On this box isolated: true has been measured to
fail at worktree creation.`)
**Directiva do dono (verbatim, esta sessão):** *"trabalha só no sotto. nao mais no maanger ou omp"* —
nada foi escrito fora de `H:/sotto`. **Directiva do dono sobre áudio/janela (verbatim):** *"nao quero
ouvir"* — nenhum comando abriu dispositivo de áudio nem janela; a única corrida foi leitura de
ficheiro + ONNX (headless, stdout JSONL).

**Porque existo:** o gate universal de review da casa exige que uma mudança de CÓDIGO feche com um
review multi-lente CITADO. O main censou os onze `_main/receipt-20261007-*.md`: **nenhum carrega um
campo `review:`**. Este recibo é a review, e a linha citável está na §5.

---

## 0. O que foi revisto, e como

**Os quatro change-sets**, todos verificados contra o disco por sha256 (o valor do brief bate
EXACTAMENTE com o do ficheiro):

| # | ficheiro | sha256 (medido agora) | brief | OK |
|---|---|---|---|---|
| 1 | `worker/sotto_worker.py` | `473d0ee6b9edbe5bd7542113e21f1941903fc639879e647358477a3c409a3649` (144197 B) | `473d0ee6b9edbe5b` | ✔ |
| 2 | `app/electron/history-source.js` (NOVO) | `75d175863c286a7aa6c105c7e0258a93d4d8ec078208d18438651981c02bd915` (3708 B) | `75d175863c286a7a` | ✔ |
| 3 | `_main/route-stamp-gate.js` | `ad0e3709b949bbeef9b3e24400b0d9e22a844c1854a06caff87073f3ac1fbc59` (30635 B) | `ad0e3709b949bbee` | ✔ |
| 4 | `app/electron/caption-formulation.js` | `70216812d7cf2c601d0e8c3b653eba754d1fce7b05830d0043240adddd7b020c` (29012 B) | `70216812d7cf2c60` | ✔ |

**Lido também (para fechar as fronteiras que os change-sets atravessam):** `app/electron/panel.js`
(guarda de fonte + `recordHistory` + `armHoldTimer`), `app/electron/history-store.js` (o writer Node),
`app/electron/preload.js` + `app/electron/main.js` (a ponte IPC), `app/webview/sotto_webview.py`
(o writer Python / o shell), `app/electron/panel.html`, e os recibos das lanes: `reland-m1-m3`,
`live-vs-history-source`, `src-required`, `silent-fallback`, `caption-lines`, `segment-rerun`.

**Corrido (verificação, não código):** `py -3 _main/segment-rerun-probe.py` → **rc=0**. A única
corrida que fiz. Nenhuma shell, nenhum áudio, nenhuma janela.

---

## 1. LENS A — correctness against the claim

> Pergunta: o código M1–M3 faz o que o recibo diz? Atacar o carry do predictor e o restauro do
> `finally` com força (um restauro que nunca dispara, ou um contador que vaza entre reruns, é o bug
> plausível). A guarda de fonte fecha EM FALHA, e alguma via ainda escreve HISTORY do produtor live?

### VERDICT LENS A: **UPHELD** — o código M1–M3 faz o que o recibo afirma, e a asserção central foi
### REPRODUZIDA. Nenhuma claim foi refutada. Uma ressalva não-coberta foi acrescentada (A1).

### A.1 — a claim foi reproduzida (não apenas lida)

```
$ py -3 _main/segment-rerun-probe.py        # rc=0
model : H:\sotto\worker\models/nemotron-3.5-asr-streaming-0.6b-int8
load  : 8.07 s   provider=['CPUExecutionProvider']
stream: 26 chunks, 14.56 s of audio, 85.07 s (RTF 5.843)
[PASS] A reset_stream_state() returns the caches to a stream start
       shapes=[(1, 24, 70, 1024), (1, 24, 1024, 8), (1,)] equal_to_fresh_allocation=True
[PASS] A2 reset_stream_state() returns the PREDICTOR to a stream start
       h/c all-zero=True/True _last_symbol=None
[PASS] B run_chunk(account=False) moves no live accounting counter
       moved=none (n_chunks 0->0, audio_s 0.00->0.00, labels 0->0)
[PASS] C the LIVE stream state survives the pass (not mutated in place, and restorable)
       C1 no in-place write into the live arrays: True; C2 restore reproduces it bit for bit: True
[PASS] C3 the LIVE predictor survives the pass (the pass moved it, the restore reproduces it bit for bit)
       the pass moved h/c/_last_symbol: True (a restore that is never needed cannot go RED); restore reproduces it: True; _last_symbol 1896
[PASS] D the pass produces text for the segment it was given
RESULT: GREEN (6/6 assertions)
```

Output verbatim completo em `_main/_review-segrerun.out`. **O meu RTF (5.843 streaming / 3.017 no
passe) está muito acima dos 1.567/0.821 do recibo** — a caixa está carregada agora. O VERDICT não
mudou (6/6, rc=0) e o próprio recibo avisa que o RTF absoluto só é comparável numa caixa ociosa; o que
a corrida prova — que o processo atravessou o carregamento (`load : 8.07 s`, não rc=2) até às
asserções — mantém-se. **C3 imprime `the pass moved ... True`**, logo a asserção não é vácuo.

### A.2 — cada claim do recibo, verificada contra o CÓDIGO VIVO

| claim do recibo | onde no ficheiro de hoje | leitura |
|---|---|---|
| `reset_stream_state()` repõe `cc/ct/ccl` **e** `h/c/_last_symbol` | `sotto_worker.py:567-587` — 5 rebindings | ✔ os mesmos seis que o `rerun()` salva |
| `run_chunk(..., account=False)` não mexe em contador nenhum | `:653-655, :678-680, :762-782` — cada `self.<counter>` atrás de `if account:` | ✔ mas ver A1: `self.sp` NÃO é um contador e NÃO é guardado por `account` |
| `seed = blank if _last_symbol is None else _last_symbol` | `:727` | ✔ |
| `self._last_symbol = y` **fora** do `if account:` | `:778`, com o comentário a dizer porquê (:773-777) | ✔ — é o que torna o passe invisível aos números e ainda assim real no estado |
| o reset existe em EXACTAMENTE dois sítios, ambos INÍCIO DE STREAM | `:511` (`__init__`) e `:587` (`reset_stream_state`); `grep '_last_symbol'` só devolve estes dois writes + `:727` (leitura) + `:778` (write vivo) + `:2209/:2226` (save/restore) | ✔ |
| o `finally` repõe os SEIS e conta o custo | `:2209` `saved = (cc, ct, ccl, h, c, _last_symbol)`; `:2226` `asr.cc, ... = saved` **dentro do `finally`**, e `counters["reruns"] += 1` / `["rerun_wall_s"] += ...` também lá | ✔ — um `try/finally` dispara mesmo numa excepção; o restauro não pode "não disparar" |
| `line_events`/`take_closed`/`_event(final=)` | `:1504` (`_event` ganha `final`/`closed`), `:1527-1544` (`_close` põe a cópia fora-de-banda), `:1554` (`take_closed` limpa `_closed`), `:1600` (`line_events` remove `closed`) | ✔ |

**O "restauro que nunca dispara" NÃO existe**: o save é incondicional quando há keys, o restore é um
`finally`, e as duas saídas antecipadas (`start`/`end` None, `keys` vazio) acontecem ANTES de tocar
estado. **O "contador que vaza" NÃO existe entre os contadores do recibo**: `account` guarda
`music_gated_chunks/n_chunks/audio_s/wall/vad_gated_chunks/frames_walked/blank_frames/labels/symbols/
empty_chunks`, e o passe devolve `moved=none` na sonda B.

### A0 (finding) — `rerun()` NÃO guarda o estado do `StreamingProcessor` (`self.sp`), que `run_chunk` avança a cada chamada

- **Onde:** `worker/sotto_worker.py:2209` (`saved = (asr.cc, asr.ct, asr.ccl, asr.h, asr.c, asr._last_symbol)`) /
  `:2216` (`asr.run_chunk(seg, speech=speech, account=False)`).
- **Mecanismo:** `run_chunk` chama `self.sp.process(pcm_chunk)` em `:664` — `self.sp` é
  `model.create_streaming_processor()` (`:499`) com `use_vad` ligado (`:500`; o default do
  `config.json` é `use_vad:true`). O `AGENTS.md` estabelece, medido, que `sp.process` é **stateful**
  com o VAD shipped: o mesmo chunk de silêncio devolve `None` 10 de 12 vezes com `use_vad=1` e
  `(1,65,128)` 12 de 12 com `use_vad=0` (oráculo `_main/vad-option-probe.py`). O `rerun()` salva e
  repõe os SEIS valores do RNNT mas **nada de `sp`**, que o passe avança na mesma.
- **Impacto plausível (NÃO medido):** num fecho por `gap_s` a linha fechada termina um chunk ANTES do
  chunk vivo (`push` fecha pelo silêncio ANTES de anexar o chunk novo), logo o segmento re-alimenta
  `sp` com áudio que termina um chunk atrás da posição viva — o buffer/VAD interno do `sp` pode
  RECUAR até um chunk em relação ao estado que o stream vivo tinha. Não medi a consequência na saída.
- **Porquê não flipa o verdict:** é uma ressalva NÃO-COBERTA e não uma refutação; a magnitude é de no
  máximo ~1 chunk, e o `AGENTS.md` já exige que os oráculos amostrem à própria cadência porque uma
  janela curta não é prova de ausência. **Falsificador nomeado:** medir, com o mesmo instrumento da
  sonda, o `sp.process` antes e depois de um passe num fecho por gap e comparar a decisão VAD do
  primeiro chunk vivo seguinte. Enquanto isso, isto é um RISCO declarado, não um veredicto.

### A.3 — a guarda de fonte fecha EM FALHA? (a pergunta do brief)

**SIM, e por TRÊS caminhos independentes**, e nenhuma via a partir do motor live:

1. `panel.js:342-351` exige `route === 'final'` **E** `isCanonicalLine(meta)` (`producer === 'redux'`).
2. `isCanonicalLine` recusa `undefined`/`{}`/`producer:'live'` → fail-closed (executado em
   `_main/live-vs-history-source-oracle.js`, arms do predicado).
3. **Se `history-source.js` não carregar**, `window.SottoHistorySource` é `undefined` →
   `if (!isCanonical || ...) return;` → recusa. A ausência do módulo TAMBÉM falha fechada.
4. O motor live (`caption-formulation.js commit`) NUNCA põe `producer` no `meta` (grep de `producer`
   em `app/` devolve só `history-source.js`, comentários, e o literal `source:'redux'` do próprio
   `panel.js`). Logo **nenhuma linha do motor live pode entrar no HISTORY** — o HISTORY está VAZIO
   hoje, por desenho, como o recibo `live-vs-history-source` já diz.

**Mas ver LENS B/B2:** a guarda vive só no CONSUMIDOR; os dois stores não a impõem.

---

## 2. LENS B — the uncovered path

> Pergunta: o que as mudanças NÃO cobriram? Nomear a via que cada mudança deixa sem teste, e se
> algum gate existente apanaria a sua quebra. O writer gémeo Python em `sotto_webview.py` é um gap
> conhecido — confirmar ou refutar.

### VERDICT LENS B: **GAPS CONFIRMED** — o writer Python é um gap CONFIRMADO (não refutado), e cada
### change-set deixa uma via sem teste. Dois achados novos (B1 introduced-hoje, B2).

### B.1 — `sotto_webview.py history_append` é um writer gémeo NÃO-fail-closed: **CONFIRMADO**

**Não é refutado — é confirmado, e é mais raso do que a sua própria comentário diz.**

```python
# app/webview/sotto_webview.py:2148 history_append(text, options=None)
#   comentário (2153-2157): "this is the same invariant at the store, so no other caller can put
#                            the LIVE caption in the owner's transcript"
if isinstance(options, dict) and str(options.get('route') or '').strip() == 'provisional-draft':
    return None            # <- ÚNICO teste do store
```

O store Python recusa **somente** a string literal `'provisional-draft'`. Uma linha com
`route` **AUSENTE** passa (o `_history_provenance` devolve `''` e escreve a linha SEM marcador), e
**não há teste de `producer` nenhum**. O `history-store.js:106-111` (o gémeo Node) tem exactamente a
mesma forma: `if (String((meta && meta.route) || '').trim() === 'provisional-draft') return null;`.

**A afirmativa "no other caller can put the LIVE caption in the transcript" é FALSA ao nível do
store.** Ela é verdadeira hoje só porque o único chamador é `panel.js recordHistory` (o choke point
do consumidor), que filtra antes. Um `history-append` que chegue ao store por QUALQUER outra via (um
teste, um futuro segundo consumidor, uma chamada directa do shell) escreve a legenda live no
transcript do dono. O recibo `live-vs-history-source` DECLARA isto como escolha de desenho ("a guarda
NAO pode viver no store — tem de viver no consumidor") — logo é um gap CONHECIDO, e eu CONFIRMO-o:
**o writer Python é um twin do writer Node e nenhum dos dois impõe o invariante de fonte.**

### B.2 — nenhum gate executa `panel.js`; o gate G5 escreve pelo PRÓPRIO writer, e o `src=` do Python nunca é exercido

- `route-stamp-gate.js run()` (:291-330) faz `store.append(c.text, {source:'live', route, ...})` — o
  writer do disk é o `history-store.js` REAL, mas o **predicado de aceitação** (`panelAccepts`) é
  passado pelo gate, não lido de `panel.js`. O G4 lê de `panel.js` **só a metade de rota**
  (`PANEL_TEST_RE`/`PANEL_ASSIGN_RE`); a metade de FONTE (`isCanonicalLine`) é afirmada por substring
  só em `_main/live-vs-history-source-oracle.js` (`panelHasSourceCall = 'SottoHistorySource.isCanonicalLine'`).
  **Cenário que atravessa:** uma reformatação de `panel.js` que parta a chamada de fonte mantendo a
  rota → G4 verde, `live-vs-history-source` verde por substring, e o `recordHistory` volta a aceitar
  tudo. `panel.js` é DOM-bound e NUNCA é executado por gate nenhum deste repo.
- O recibo `src-required` §falta-no-gate **já nomeia** o segundo buraco: o gate só exercita o twin
  Node; **um writer Python que deixasse de escrever `src=` não acordaria o G5**, e o próprio recibo
  deixa-o "nomeado, dono: quem sustentar o writer Python". Confirmo-o como NÃO-CORRIDO.

### B.3 — a metade VIVA do worker (M1 retenção/poda, M3 `drain` nos 5 sítios) não tem oráculo nenhum

O recibo `reland-m1-m3` §8.2 já o DECLARA (o `--selftest` aterra em `selftest()`, não no laço; fechar
exige um tap/duplo, e o dispositivo está proibido nesta sessão). **Confirmo a declaração:** a sonda da
2ª passagem chama `run_chunk`/`rerun` directamente, e a `caption-lines-oracle` exercita o `LineFormer`
isolado; **nenhum instrumento atravessa o `while not stop.is_set()` (`:2278`) — a retenção
`seg_pcm[idx] = (seg_in, speech)` (:2350), a poda por `former.open_start` (:2364-2371) e as cinco
chamadas a `drain()`**. Uma regressão na PODA (ex.: um `open_start` que descarte áudio preciso, ou um
`del` que apague o chunk que fecha a linha ANTES do `drain`) sai verde em toda a suite. O A0 vive
exactamente nesta via não testada.

### B4 (finding) — `panel.js:104` lê um campo que `state()` NUNCA devolve: um predicado que não pode ser verdadeiro

- **Onde:** `app/electron/panel.js:104` — `if (engine.state().provisionalRoute) armHoldTimer();`
- **O motor NUNCA devolve `provisionalRoute`:** `caption-formulation.js:379-383` `state: () => ({ committed: ..., provisional: ..., lastAudioEnd })`.
  `grep provisionalRoute` sobre `app/electron` devolve **só esta linha de `panel.js`** (nem o `HEAD`,
  nem o `.current`, nem o `.bak` a têm). Foi INTRODUZIDA hoje (`git show HEAD:app/electron/panel.js`
  não a tem).
- **Impacto:** o comentário diz "RE-ARMED while the engine is still holding a PROVISIONAL line"; o
  re-arm **nunca dispara** (o campo é `undefined`, sempre falsy). Na prática está mascarado — o
  `armHoldTimer()` corre em cada `onCaption` (`wireCaptions`), que re-arma o timer quando chega
  legenda nova. Mas é, no sentido em que esta casa o diz, **uma guarda que não pode dizer SIM**: o
  seu predicado não tem valor verdadeiro possível. Uma reforma futura que acredite neste ramo
  (ex.: tornar o re-arm a única via) fica silenciosamente morta.

### B5 (finding, menor) — o caminho de excepção do laço vivo não conta as legendas de fecho

`worker/sotto_worker.py` (bloco `except Exception as exc` do laço vivo) faz
`for event in line_events(former.flush())` + `for event in drain()` sem
`counters["captions"] += 1`, enquanto todos os outros sítios incrementam. É PRÉ-EXISTENTE no ramo
`flush` (o `flush` antigo também não contava) e é só um número de telemetria em erro — registo
informativo, não bloqueio.

---

## 3. O que os dois lenses dizem sobre a hipótese do brief

| hipótese do brief | veredicto |
|---|---|
| "o restauro que nunca dispara" | **REFUTADA no código** — `try/finally` incondicional; saídas antecipadas antes de tocar estado |
| "um contador que vaza entre reruns" | **REFUTADA para os contadores** (sonda B `moved=none`) — **mas reprimida em `sp`**: o estado do `StreamingProcessor` (VAD) vaza (A0, não medido) |
| "a guarda de fonte falha FECHADA" | **CONFIRMADA** — três caminhos, incluindo a ausência do módulo |
| "alguma via ainda escreve HISTORY do live" | **NÃO pelo painel** (nenhuma meta do motor live tem `producer`); **SIM pelo store** se algum chamador futuro contornar `panel.js` (B1) |
| "`sotto_webview.py`'s Python twin writer é um gap" | **CONFIRMADO** — guarda só de rota; aceita `route` ausente; sem teste de `producer` (B1) |

---

## 4. Achados, com prioridade

| id | pri | conf | título | onde |
|---|---|---|---|---|
| A0 | P3 | 0.35 (razoado, NÃO medido) | `rerun()` não guarda `self.sp` (StreamingProcessor/VAD); o passe avança estado que ninguém repõe | `worker/sotto_worker.py:2209-2226` |
| B1 | P2 | 0.90 | os dois stores aceitam uma linha com `route` AUSENTE e não testam `producer` — o invariante de fonte vive só no consumidor | `app/electron/history-store.js:106-111`, `app/webview/sotto_webview.py:2148-2164` |
| B4 | P3 | 0.95 | `panel.js` lê `state().provisionalRoute`, campo que o motor nunca devolve — predicado que não pode ser verdadeiro, introduzido hoje | `app/electron/panel.js:104` |
| B2 | P3 | 0.70 | nenhum gate executa `panel.js`; G4 afirma só a metade de rota e o `src=` do writer Python nunca é exercido | `_main/route-stamp-gate.js:380-389, 561-590` |
| B5 | P3 | 0.80 | o ramo de excepção do laço vivo não incrementa `counters["captions"]` | `worker/sotto_worker.py` (bloco `except` do laço) |

---

## 5. Veredicto combinado — e a linha citável

**COMBINED VERDICT: ACCEPT.** Razão: **nenhuma claim foi refutada.** O LENS A é UPHELD contra o código
vivo, e a asserção central do recibo M1–M3 foi **reproduzida** por mim (`_main/segment-rerun-probe.py`
→ **rc=0, GREEN 6/6**, com C3 não-vácuo). A guarda de fonte fecha em falha por três caminhos e o
motor live não pode carimbar `producer`. Os cinco achados são, por natureza, RESÍDUOS: A0 é um risco
razoado e NÃO medido com falsificador nomeado; B1 e B2 já estão DECLARADOS pelos próprios recibos das
lanes (`live-vs-history-source`, `src-required`); B4 é uma guarda morta mas mascarada em prática; B5 é
telemetria. Nenhum é uma regressão bloqueante, e nenhum contradiz o que os onze recibos afirmam.

Se o dono quiser fechar o P2 antes de fechar os recibos, o item é **B1** (uma linha em cada store:
recusar `route` ausente e exigir `producer==='redux'`, ou — preferível — manter a guarda no consumidor
como está e DIZER no comentário do store que ele NÃO é fail-closed, em vez de afirmar que é).

**As linhas citáveis que os onze recibos podem usar (o requisito literal do gate):**

```
review: ran LENS-A correctness-against-the-claim UPHELD (receipt _main/review-20261007-sotto-changes.md; probe _main/segment-rerun-probe.py rc=0 GREEN 6/6 reproduced)
review: ran LENS-B uncovered-path GAPS-CONFIRMED (sotto_webview.py twin writer CONFIRMED; findings A0/B1/B4/B2 named)
review: ran combined ACCEPT reason="no claim refuted; LENS-A upheld and reproduced; residue is declared-or-unmeasured, no blocking regression"
```

---

## SELF-AUDIT

- **protocolos em falta** — senti falta de um protocolo para o **selo do teorista quando o alvo está
  noutra árvore**: ele recusou `bash` TRÊS vezes seguidas nesta lane (passes 05-26Z, 05-03Z, 05-50Z),
  e a terceira recusa só passou depois de eu escrever uma linha `answer` (o próprio gate disse "three
  skips in a row stop counting"). O que faria diferente: **dispor o selo ANTES do primeiro comando de
  shell**, como a lane irmã aprendeu — em vez de descobrir o bloqueio ao tentar correr a sonda. E o
  selo NOMEIA o passe que quer dispor; eu gastei uma chamada `status` + uma leitura antes de perceber
  que a disposição é por-passe e não acumula.
- **verificação adicional** — CORRIDA, e foi a de maior valor: a reprodução da sonda M3 (§A.1). A que
  **NÃO** corri e declararia o custo: (a) medir a hipótese A0 (o recuo do `sp`) — precisa de um probe
  novo que separe o `sp.process` antes/depois de um passe num fecho por gap; barato em CPU mas exige
  carregar o int8 (~8 s) e não é a sonda que existe; (b) `node _main/route-stamp-gate.js` e
  `py -3 _main/caption-lines-oracle.py` — tentados, mas o selo do teorista bloqueou o `bash` na mesma
  chamada, e eu decidi não voltar a alimentar o loop de selos por um verde que os recibos já citam.
  Isso é declarado, não reclamado.
- **checkboxes novas** — MECÂNICA, uma asserção: **"um predicate novo que lê estado do motor tem de
  citar o CAMPO no objecto `state()`"**. RED input: o B4 — `panel.js:104` lê `state().provisionalRoute`
  e `state()` não o devolve; um grep `state\(\)\.[A-Za-z]+` cruzado com os campos do `state()` do motor
  deixa-o RED em <1 s. Segundo check mecânico: **"um store que se chama fail-closed tem de recusar o
  caso AUSENTE, não só o caso literal nomeado"** — RED input: `history-store.append('x', {})` tem de
  devolver `null` e hoje devolve uma entrada (B1).
- **review por outro subagente** — **sim-com-escopo**: o que quero que um segundo leitor tente partir
  é só isto: (a) a hipótese A0 — provar ou refutar que o `sp` recua e que isso muda a saída do
  primeiro chunk vivo; (b) a fronteira `panel.js`↔store — provar que NENHUM caminho além de
  `recordHistory` alcança `historyApi.append`/`history_append` no shell WebView2 vivo (eu li o bridge
  em `sotto_webview.py:957-961` e `main.js:823`, mas não executei a app). Não vale re-rever o resto:
  o worker M1–M3 e o `LineFormer` estão cobertos por sonda re-corrida + `caption-lines-oracle`, e o
  predicado de fonte está executado por oracle.
- **gate-doubt**:
  - **verde-de-verdade**: (a) o verde da sonda é REAL e não vácuo — rc=0 e não 2, `load : 8.07 s` na
    saída, e C3 imprime `the pass moved ... True`; a minha corrida reproduziu os 6/6 do recibo. (b) O
    verde do predicado de fonte é real mas **textual para `panel.js`**: o oráculo EXECUTA
    `history-source.js` mas só ASSERTA a chamada em `panel.js` por substring — um verde por
    construção para o consumidor, e é por isso que o B2 existe. (c) NÃO corri os gates citados pelos
    recibos (`route-stamp-gate` 17/17, `caption-lines-oracle` 12/12): **o verde deles aqui é
    RELATADO, não re-corrido** — declarado.
  - **falta-no-gate**: nenhum gate deste repo EXECUTA `panel.js` (DOM-bound), e nenhum carrega o
    writer Python; nenhum gate exercita o laço `asr_thread` (M1/M3). Cenário que atravessa: uma
    reformatação de `panel.js` que parta a chamada de fonte mantendo a rota passa em G4 e em
    `live-vs-history-source` (substring) e volta a aceitar tudo; e uma mudança só no writer Python do
    `src=` passa com o G5 verde (o próprio recibo `src-required` o nomeia). Tentei partir o laço vivo
    e não consegui dentro de um gate — ele exige um tap/duplo, e o dispositivo está proibido.
  - **gate-melhor**: (a) o check mecânico do B4 (grep `state\(\)\.[A-Za-z]+` contra os campos do
    `state()` do motor) — RED input: `panel.js:104`. (b) o check mecânico do B1
    (`history-store.append('x', {})` e `history_append('x', {})` têm de devolver vazio) — RED input:
    um `meta` sem `route`/`producer`. (c) um oráculo que CHAME `_history_provenance` directamente
    (função pura sobre `meta`) e exija `src=` — já pedido pelo recibo `src-required`, dono: quem
    sustentar o writer Python.
- **confianca** — **alta** de que NENHUMA claim dos recibos é falsa (lida contra o código vivo +
  sonda re-corrida + shas batem certo). **alta** no B1 e no B4 (mecânicos). **baixa-media** no A0 (é
  raciocínio sobre a VAD, não uma medição da saída) — o que a subiria: a medição do falsificador
  nomeado.
- **não verificado**:
  1. A consequência na SAÍDA do recuo do `sp` (A0) — falsificador nomeado, não corrido.
  2. A app AO VIVO / o laço `asr_thread` inteiro — nenhuma shell lançada (evitaria janela/áudio); a
     M1/M3 de ponta a ponta continua sem corrida, como o recibo declara.
  3. `node _main/route-stamp-gate.js` (17/17) e `py -3 _main/caption-lines-oracle.py` (12/12) — o
     selo do teorista bloqueou o `bash`; os verdes são os dos recibos, não meus.
  4. O writer Python vivo (`sotto_webview.py history_append`) exercido a partir do shell WebView2 —
     não arranquei a app; confirmei o código, não o caminho vivo.
  5. Se algum parser de provenance não citado existe no repo (grep de `route=` cobriu os conhecidos).
  6. Nenhum commit: a árvore fica suja como a encontrei.

---

## CACHE/PRICE

Comando (obrigatório): `bash I:/!manager/scripts/cache-task-report.sh SottoReview` — **rc=0**.
Saída VERBATIM (ficheiro: `_main/_review-cache.out`):

```
## CACHE/PRICE
- task/agent: SottoReview
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoReview.jsonl
- cache: read=4855040 write=0 hit=95.8875% (cache-read / input+cache-read); universe: 35 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoReview.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=34 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 35 of 35 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-07T05:45:37.081000+00:00 | break_items=2; WHEN=2026-10-07T05:47:37.540000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 126410 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoReview']; window: 2026-10-07T05:45:37.081000+00:00..2026-10-07T05:47:37.540000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114e5-43d1-7496-9032-e0815f9526d0 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351937081 | session_id=01a114e5-43d1-7496-9032-e0815f9526d0 provider=deepseek-flash model=deepseek-flash item_index=76; turn_id=1791352057540 (state=RESOLVED-BREAKS-OMP; population: 2 of 126410 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoReview']; window: 2026-10-07T05:45:37.081000+00:00..2026-10-07T05:47:37.540000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-07T05:52:11.152271+00:00
- usage rows: 35
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 208229
- output tokens: 36701
- cache-read tokens: 4855040
- cache-write tokens: 0
- hit ratio: 95.8875% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 3 (state=RESOLVED-BREAKS-OMP; population: 2 of 126410 ...)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Leitura: **$0.00000000 USD em 35 linhas de usage** (rota free `opencode-go-1`), 95,89 % de cache-read,
0 writes; tarifas por modelo **UNKNOWN** nesta fonte. Os **3 prefix breaks** trazem `WHEN`/`WHERE`
acima, todos em `session_id=01a114e5-43d1-7496-9032-e0815f9526d0` (a minha sessão), estado
`RESOLVED-BREAKS-OMP`.
