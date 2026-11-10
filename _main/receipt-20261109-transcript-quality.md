# RECEIPT — transcript quality: census, refuted causes, one cheap landed fix

**Lane:** TranscriptQuality · **Date:** 2026-11-09 · **Repo:** `H:/sotto`
**Scope:** census `history/2026-11-09/*.md` (read-only); change `worker/**` only after a cause
was measured; this receipt. **Not touched:** `app/webview/sotto_webview.py`, `app/panel/**`,
`history/**`, `AGENTS.md`, `_main/*-oracle.py`, the owner's app or audio endpoints.
**State of the deliverable:** `LIVE` for the worker predicate and its two call sites (exercised
with fake engines, real function); `DARK` for the owner's history (no app launch, no live audio);
`UNWIRED` for the shell-side partial-admission finding (Main owns the shell).

## 0. Result in one line

The cheapest *proven* worker-side class is the batch engine's non-lexical filler: **93 of 680
history lines (13.7 %) are `Mmm`/`Mmm Mmm.` and every one is `producer=redux`**. A whole-caption
predicate now drops exactly those lines in the in-process parakeet pass (`run_engine_pass`) and
logs `noise_lines=`. It costs **~2.4 µs per non-empty caption** (≤1.6 µs of CPU per audio second
at one call per 3 s window) and does not touch decode. The ternary runner path is not wired in
this change (see §4).

The **dominant 15:00+ class is not this one**: 112 of the 293 lines in `15.md`/`17.md`/`18.md`
(38.2 %) end without terminal punctuation, and 76 of those are **live `reason=stable` partials**
that the panel admitted to history. That is a shell/panel admission defect, named in §2.5 for
Main; landing a worker change for it would trade live-caption behaviour for transcript
cosmetics, so it was not landed here.

## 1. CENSUS — measured, not impressions

Method: one Python pass over all 680 lines, parsing the `- [hh:mm:ss] text <!-- meta -->`
format; `producer=redux` from the meta, everything else `live`; classes are exact predicates
listed below. Script is inline in the command log; counts were re-run twice after the fix and
are identical.

| class | predicate | lines | % of 680 | producer |
|---|---|---:|---:|---|
| no terminal punctuation | text does not end in `. ! ? …` (quotes/brackets allowed) | **113** | 16.6 % | live 76 / redux 37 |
| …and ends on a function word ("dangling") | last token in a 60-word function list | **12** | 1.8 % | live 8 / redux 4 |
| adjacent duplicate token | same normalised token twice in a row | **67** | 9.9 % | redux 58 / live 9 |
| repeated 2–3 word n-gram | `A B A B` or `A B C A B C` | **34** | 5.0 % | redux 33 / live 1 |
| split word | one of 17 hand-verified pairs (`Su per`, `Ho pe`, …) | **15** | 2.2 % | live 14 / redux 1 |
| **`Mmm`-only noise** | **every token matches `m+`/`hm+`/`mhm+` + punctuation** | **93** | **13.7 %** | **redux 93** |
| other single-word line | one token, not `Mmm`-only | 33 | 4.9 % | redux 27 / live 6 |
| Cyrillic script | any U+0400–U+04FF | **10** | 1.5 % | redux 10 |
| lowercase standalone `i` | `\bi\b` | 7 | 1.0 % | live 6 / redux 1 |
| lowercase line start | first char lowercase | 0 | 0 % | — |
| exact repeated sentence | identical normalised line | **0** | 0 % | — |

Normalised duplicate lines exist (10 distinct strings, 96 extra occurrences) but they are the
filler runs plus `one`/`oh`: the largest is `mmm` ×56. There is **no repeated sentence** in the
corpus, so the "repeated sentences" class is not a defect here; the repeated *n-grams* are the
same filler.

Per file (`lines` / `redux` / `live` / no-terminal / `Mmm` / split / Cyrillic):

| file | lines | redux | live | no-term | Mmm | split | Cyrillic |
|---|---:|---:|---:|---:|---:|---:|---:|
| 05.md | 137 | 76 | 61 | 0 | 7 | 5 | 0 |
| 06.md | 114 | 112 | 2 | 1 | 29 | 1 | 1 |
| 07.md | 64 | 41 | 23 | 0 | 8 | 2 | 2 |
| 11.md | 4 | 4 | 0 | 0 | 4 | 0 | 0 |
| 13.md | 19 | 19 | 0 | 0 | 3 | 1 | 1 |
| 14.md | 49 | 49 | 0 | 0 | 25 | 0 | 0 |
| 15.md | 101 | 100 | 1 | 3 | 8 | 0 | 0 |
| 17.md | 63 | 26 | 37 | 45 | 1 | 4 | 1 |
| 18.md | 129 | 91 | 38 | 64 | 8 | 2 | 5 |

**The 15:00+ slice** (`15.md`+`17.md`+`18.md`, 293 lines): 112 no-terminal (38.2 %), 17 `Mmm`
(5.8 %), 17 split-word occurrences? — split lines in the slice are 6 (`17.md` 4, `18.md` 2), and
the slice is 76 live / 217 redux. The no-terminal class is the one the owner reads as
"truncated"; it is not the class this fix removes.

### Five real examples per class (`file:line`)

**Truncation / no terminal punctuation**
- `06.md:81` — But you would need a big battery, sensors,
- `15.md:21` — Okay,
- `15.md:72` — Hello, hello, hello, hello, hello, hello. God,
- `15.md:95` — We fighting roof yeah we're up souls that's what I'm worried about, though like the
- `17.md:37` — But I

**Duplicated / overlapping words**
- `05.md:15` — Still super super niche and it wasn't really a tapped market, yet quote.
- `05.md:19` — And i i was really disappointed to find out that that moment has already.
- `05.md:25` — There's plenty of room to to prompt some presets the ought to respond to some.
- `05.md:26` — Shit which is you know just kind of lazy in my opinion i i even look at like big.
- `05.md:39` — It as soon as we, notice that channel was around around for uh I want to sit like a.

**Split words**
- `05.md:2` — Su per critical of it, but uh when I saw this screenshots it was pretty dam.
- `05.md:24` — Ho pe that they're made with you know some handmade presets, but I know that.
- `05.md:44` — Visi bility to those really passion creators just like when the the six hero update.
- `05.md:45` — Dr opped or the old god's new blood update dropped and we had like a huge influx of.
- `17.md:9` — Ti po não pode cancelar é só quando bate alguma coisa

**Wrong language / script inside the stream**
- `06.md:98` — Да, шабуницу да им же...
- `07.md:10` — А ну киса!
- `07.md:21` — Вот едно!
- `13.md:11` — И начина чуда. Că ște că cię dizântoni o căsare.
- `18.md:79` — Я тебе исключение.

**Single-word noise**
- `05.md:58` — Mmm.
- `05.md:65` — Mmm.
- `05.md:70` — Mmm.
- `06.md:12` — Mmm Mmm Mmm Mmm Mmm.
- `14.md:5` — Mmm Mmm Mmm Mmm Mmm.

**Repeated n-gram (no repeated sentence exists)**
- `05.md:32` — That did a good jo, but I was I was disappointed to fid out that they were using this.
- `05.md:136` — Mmm Mmm Mmm Mmm Mmm Mmm.
- `06.md:12` — Mmm Mmm Mmm Mmm Mmm.
- `06.md:15` — Mmm Mmm Mmm Mmm.
- `06.md:16` — Mmm Mmm Mmm Mmm Mmm.

**Missing capitalisation**
- `05.md:16` — Unquote you know a marketplace, but i think right now it has become a full on.
- `05.md:19` — And i i was really disappointed to find out that that moment has already.
- `05.md:21` — Find other channels and see like where this is happening i know there's a couple comic.
- `05.md:26` — Shit which is you know just kind of lazy in my opinion i i even look at like big.
- `05.md:41` — I i just hate to see this game being used as like a content farm uh when there's so.

## 2. CANDIDATES — each with the observation that would refute it, and the probe

### 2.1 Language / language-id hint

**Refuted as the cause of the measured classes on the one clip with a reference.**
Command (child processes through `_main/hidden-launch.py`; no device opened):
`py -3` driver calling `worker/sotto_worker.py --selftest --audio _main/fixtures/stack-compare/ptbr-radio-14s.wav --lang-id {auto,12,0}`.

| arm | rc | captions | hypothesis (verbatim) | edits vs provisional reference |
|---|---:|---:|---|---:|
| `auto` (101) | 0 | 2 | `Rádio anunciou que a ponte sobre o vai ser interditada na próxima segunda-feira. Os moradores precim de um caminho alternativo para chegar ao trabalho` | 4 / 26 tokens |
| `12` (pt-BR) | 0 | 2 | same normalised tokens; second line has no final period | 4 / 26 |
| `0` (en-US) | 3 | 0 | `''` — `quality: REFUSED (0 token(s) over 14.56 s, floor 4.0)`, 0 tokens, blank_frac 1.0 | — |

`auto` and `12` **tie**; `0` refuses. The reference's own JSON says 25 words and warns the WER is
for engine comparison, not an absolute claim; the edit count is reported only to show the tie.
The 10 Cyrillic lines are all batch lines in media/game tabs; the history carries no per-line
language label, and no audio was retained, so this corpus **cannot** say whether the audio
contained Russian speech or the decoder invented it. What it can say: hardcoding `12` is not a
measured improvement over `auto` on the owner's own pt-BR clip; `12` on English was not measured
here, so it cannot be called a general improvement either.

### 2.2 Chunk / VAD boundaries cutting words

**Refuted for the batch lines; unresolved for 14 live split words.**
- `start` deltas for consecutive `redux` lines in the same file are dominated by **exactly 3.00 s**
  (`05.md` 64/76, `06.md` 63/112, `14.md` 17/49, `15.md` 39/100, `18.md` 30/91). That is
  `engine_policy.REDUX_ENGINE_WINDOW_S = 3.0`, not the 560 ms live chunk. No 0.56 s mode appears.
- Live history lines are *committed lines*, not chunks: successive live `start` values are
  10–270 s apart (`17.md`, `18.md`), so their starts cannot expose the 560 ms seam.
- Split-word position: **14 of 15 split words are the first word of a line**; the 15th is inside
  one line. The previous line usually does **not** end with the first half (e.g. `05.md:1` ends
  `not super.`, `05.md:2` begins `Su per critical…`), so a naive seam-join of adjacent history
  lines cannot recover them.
- Synthetic replay against the real `LineFormer`: `push("Su", continues=False)` then
  `push("per", continues=True)` at the normal cap gives `line() == "Super"` and one event
  `Super`; only `continues=False` gives `"Su per"`. The shipped marked-continuation join works.
  The corpus has no token ids/audio, so it cannot distinguish "the model emitted two word
  starts" from a path that forced `continues=False`.
- **Latent code defect found by that replay (reported, not landed):** in `LineFormer.push`, after
  a `_close(carry=True)` at the 90-char cap the code sets `cont = False` unconditionally, even
  when `continues=True`. A word spanning the cap therefore becomes `"Su per"`; with `cont`
  preserved it would be `"Super"`. This is a real invariant break, but it was not proven to be
  the producer of the 14 corpus lines, so the one-line change is left for a lane with the token
  trace. Falsifier for that lane: capture the `chunk_continues` values around one split line and
  show the carry path is not involved.

### 2.3 Decode policy (`max_symbols_per_step`, blank, emit)

**Refuted as a cause of these classes; the config and the model's own spec agree.**
Command: `python _main/model-spec-oracle.py` → **VERDICT: PASS**, rc 0:

```
model dir      : models/nemotron-3.5-asr-ptbr-onnx-int4
blank_id       : 13087 (spec says 13087)
chunk_samples  : 8960 (spec says 8960)
max_symbols    : 10
left_context   : 56
config lang_id : auto (resolves to 101 (auto, source=auto))
config use_vad : True (model ships silero_vad tuned thr=0.3 silence=3360ms)
```

The worker reads `blank_id`, `chunk_samples`, `max_symbols_per_step` from the model's
`genai_config.json`; no new decode convention was introduced. Changing any of these would be an
invented convention, and none of the measured classes is explained by a mismatch (there is none).

### 2.4 Seam / duplicate rules

**Partly refuted; the safe subset is the filler rule.**
- Adjacent duplicate tokens: 67 lines, but **58 are batch** and include legitimate speech
  (`Still super super niche`, `room to to prompt`, Portuguese `no no`); a general single-word
  dedupe would rewrite real speech. `dedup_seam_repeat` already collapses 2+ word repeats on the
  live path; the only non-noise live multi-word repeat is `05.md:32` (`I was I was`), which the
  current partial path still shows (another reason the stable path, not the close path, is the
  live text's source). No safe, cheap, general rule was found.
- The 33 batch multi-word repeats are all `Mmm` runs. The landed whole-caption filter removes
  them without touching a real repeated word.

### 2.5 The actual 15:00+ finding (shell, not worker)

All 162 live lines in the corpus carry `route=final src=worker-stamped reason=stable`. A
`stable` commit is the panel's own close of a partial, not the worker's `final:true` line (see
`app/panel/caption-formulation.js` `PANEL_CLOSED_REASON` and the `routeFor` doc). The live
partial has no terminal punctuation by construction (it is mid-line), so admitting it to history
is exactly the "truncated sentence" the owner reads:

- 17.md: 45/63 lines no terminal; 18.md: 64/129; 15.md: 3/101.
- 76 of the 113 no-terminal lines are live; all 162 live lines are `reason=stable`.
- 17/18 examples: `17.md:37` `But I`, `17.md:48` ends `do`, `18.md:6` `Ou não sai ela canceu
  não vi enfim`, `18.md:120` ends `a`, `18.md:129` ends `noi`.

**Recommended cheapest shell fix (Main):** do not let `reason=stable` commits reach the history
feed; wait for the worker's `final:true`/closed line. The worker already emits that out of band
(`take_closed`); the panel's route fallback is converting a partial into a final. This is a
one-line predicate in the shell, zero decode cost, and it addresses 76 of the 113 no-terminal
lines. It is outside this lane's write scope.

#### 2.5-C CORRECTION (medida 2026-11-10, por quem foi ler os flags) — o mecanismo acima está ERRADO

A atribuição desta secção não se sustenta no que a própria linha escreve. Medido agora:

* `route=final src=worker-stamped` é **exatamente o contrário** de "fechamento do PAINEL": em
  `app/panel/caption-formulation.js`, `routeSourceFor()` devolve `'panel-deadline'` para um
  fechamento do painel e `'fallback'` para o default silencioso; `'worker-stamped'` só sai quando
  `bufferFinal || bufferSawFinal`, ou seja **quando o WORKER votou**. E `routeFor()` só devolve
  `final` quando `bufferFinal` (o `meta.final === true` do worker) — com `reason=stable` e sem
  voto do worker a rota seria `provisional-draft`, que as duas lojas RECUSAM.
* Logo: aquelas 162 linhas não são parciais admitidas pela shell; são linhas que o **worker**
  fechou (`worker/sotto_worker.py:5341`, `self._event(text, final=True, closed=True,
  stable=True)`) e que o painel commitou no instante do `stable` (`ingest`, `if (meta.stable ===
  true) commit('stable')`). O `reason=stable` é o NOME do gatilho, não a rota.
* A "frase truncada" também não é um corte de meio de linha do painel: medido em `17.md`, as
  **37** linhas `reason=stable` — **0** terminam com marca de pontuação — e **0** têm a linha
  seguinte começando em minúscula (nenhuma é continuação de uma linha partida). O corte é a pausa
  de fala, que é onde o worker fecha a linha.
* A ausência da marca tem causa nomeada e é um DECISÃO medida, não um defeito de admissão:
  `worker/punctuation_model.py` só pontua `supported_lang(tag)` (`en*`), e o docstring do módulo
  registra por que o multilang foi recusado (`oliverguhr/...-multilang-large`, ~2,4 GB, arrasta
  `torch` num worker de 1,9 GB com `I:` a 4,8 % livre). O áudio deste worker é pt-BR: a pontuação
  de MODELO fica `active=false` e o `log_line()` diz isso com a língua ao lado.

**Consequência para quem for agir:** "não deixar `reason=stable` chegar ao histórico" não é uma
cura, é uma regressão — tiraria do histórico as linhas que o worker FECHOU e que hoje são a única
coisa boa dele. Continuam abertas duas classes medidas e pequenas: (a) `Mmm` — curada nesta lane;
(b) a marca de pontuação em pt-BR, que exige prosódia/pausa (`punctuation_prosody.py`) ou um
modelo com português, e **não** um filtro de rota.

## 3. THE LANDED FIX — whole-caption noise filter

### 3.1 What changed

| file | change |
|---|---|
| `worker/caption_noise.py` | **new file** — `is_noise_caption(text)`, `admit_batch_caption(sw, text)` (counts on the switch), `--selftest` (7 arms, negative arm) |
| `worker/engine_policy.py` | one import; `run_engine_pass` calls `admit_batch_caption`; `noise_lines=` in `REDUX_ENGINE_DONE` |

Files: `worker/caption_noise.py` 7 387 B / 193 lines, sha256
`fae70fdd21c30299285a01a308811e566fbb12832f3fbe8785b5057612239ebb`;
`worker/engine_policy.py` 23 294 B / 522 lines, sha256
`4c9aab4d37559384eece9c08c807e27becbac5b3a1031a5e37f90b25612151ca` (the structural
ratchet now measures it **LESS**: 23 499 → 23 294 B, same 522 lines, max function 96 → 92).
`worker/engine_switch.py` is unchanged (89 038 B / 1 670 lines). All three are **LF only**
(0 CRLF).

The filter lives in the **in-process parakeet pass** (`run_engine_pass`), which produced the
3 s-window corpus. The ternary runner path (`ReduxHiddenSwitch._run_runner`) is *not* wired in
this change; its output was not in the measured corpus, and keeping `engine_switch.py` at its
baseline is part of not growing a ratcheted file.

The predicate is deliberately narrow: the whole caption must consist of `m`/`hm`/`mhm` tokens
(with terminal punctuation). `Mmm, mas eu vou.`, `Uh, we take everything…`, `Oh.`, `Sim`,
`Cabeça!` are **not** matched. That last point is a measured constraint: 33 other single-word
lines exist and are kept; the corpus's `Mmm` class is 93 lines and all redux.

### 3.2 Effect on the corpus (measured)

```
python - <<'PY'
import glob, re, sys
sys.path.insert(0, 'worker')
from caption_noise import is_noise_caption
lines = [m for f in glob.glob('history/2026-11-09/*.md')
         for m in re.findall(r'^- \[[^]]+\] (.*?) <!--', open(f, encoding='utf-8').read(), re.M)]
noise = [x for x in lines if is_noise_caption(x)]
print('CORPUS lines=%d noise=%d kept=%d' % (len(lines), len(noise), len(lines) - len(noise)))
print('noise examples', noise[:5])
print('false positives among single-word lines:',
      [x for x in lines if len(x.split()) == 1 and is_noise_caption(x)
       and x.strip('.').lower() not in ('m', 'mm', 'mmm', 'mmmm', 'mmmmm')])
PY
CORPUS lines=680 noise=93 kept=587
noise examples ['Mmm.', 'Mmm.', 'Mmm.', 'Mmm.', 'Mmm.']
false positives among single-word lines: []
```

Re-run against the extracted module (the counts are unchanged; the predicate is the same).

- Whole corpus: 680 → 587 (−93, 13.7 %).
- 15:00+ slice: 293 → 276 (−17, 5.8 %).
- `14.md`: 49 → 24 (−25, 51.0 %).

This is a *history cleanliness* improvement, not a word-error-rate improvement: the filler lines
carry no word. It does not change any line that has a real word.

### 3.3 Cost (same instrument, before/after)

`timeit` on the shipped predicate (100 000 repeats per string):

| input | ns/call | µs/call |
|---|---:|---:|
| `Mmm Mmm Mmm Mmm Mmm.` (noise) | 2 415 | 2.42 |
| a real 90-char corpus line | 1 702 | 1.70 |
| 90-word synthetic line (worst case) | 4 663 | 4.66 |

One call per non-empty 3 s window ⇒ **≤1.6 µs of CPU per audio second** (worst case).

Call-site benchmark inside the real `run_engine_pass` after the extraction, **200 repetitions ×
200 windows / 600 s** of fake all-`Mmm` audio:

```
filter_on  0.0002514 s/pass
filter_off 0.0005692 s/pass
delta      -1.59 µs/window  (-0.53 µs/audio second)
```

Filter-on is *faster* on this fixture because an all-noise window no longer allocates the caption
dict (the 200 skipped `put`s cost more than the predicate and counter). On a mixed stream the
predicate is paid only on non-empty windows and is bounded by the microbenchmark above; it never
runs the decoder.

The batch engine's documented cost is **0.745 s compute for 14.6 s of audio** (~51 ms per audio
second, `worker/audio_queue_consumer.py` measurement cited by `REDUX_ENGINE_WINDOW_S`). The
filter is therefore ~0.001–0.003 % of the decode cost. No model load, no extra decode, no new
thread.

### 3.4 Oracle / regression arm — two colours

The worker's module-level oracle family is the `--selftest` convention (`worker/denoise.py`,
`worker/speaker_sidecar.py` and `worker/unified_asr.py` already have one). The new arm is in the
module it guards:

```
python worker/caption_noise.py --selftest
PASS noise-only captions are noise -- []
PASS captions with a real word are not noise -- []
PASS noise windows publish zero captions -- []
PASS all-noise pass logs noise_lines=2 -- ["REDUX_ENGINE_DONE … lines=0 noise_lines=2 …"]
PASS all-noise pass reports redux-batch-empty -- [...]
PASS a real word survives beside a noise window -- [{"type": "caption", "text": "hello world", ...}]
PASS negative arm re-breaks it (both noise windows publish) -- ["Mmm.", "Mmm Mmm."]
{"ok": true, "cases": 7, "caught": 7, "neg_arm": "PASS"}
NEG-ARM: PASS
RC=0
```

The first two arms are the predicate in both colours; arms 3–5 exercise the **real**
`run_engine_pass` with a fake engine; arm 6 is the control (a real word beside a noise window);
arm 7 empties `_NOISE_WORD` and requires **both** noise windows to publish, so the rule — not the
harness — is what removed them.

Regression checks:

```
python -m py_compile worker/caption_noise.py worker/engine_policy.py worker/engine_switch.py  # rc 0
python _main/code-health-oracle.py   # caption_noise NEW (<120 KB); engine_policy LESS (-205 B, max_func 92); engine_switch SAME
python _main/engine-serialization-oracle.py                            # 19/19 arms green, VERDICT PASS, rc 0
python _main/word-split-oracle.py                                     # 12/12 arms, VERDICT PASS, rc 0
```

The code-health gate's **overall** verdict is FAIL because of pre-existing RED files outside this
lane (all in `app/panel/**` and `app/webview/**`); the three files in this lane are green and the
only new file is 7 387 B, far below the 120 KB new-file limit.

The word-split oracle's worker sha256 is `76DC...`; this lane did not modify
`worker/sotto_worker.py`, and the oracle passes unchanged. It is quoted only to show the
split-word join behaviour the §2.2 replay relies on.

## 4. What was NOT proven / not verified

1. **No live audio, no app launch, no history write.** The owner's app and endpoints were not
   touched; the worker predicate was exercised with fake engines. `DARK` for the real path.
2. **The filter's cost is not a real-parakeet measurement.** The decode cost is cited from the
   module's own measured figures; the filter delta is measured with a fake engine. The filter
   does not alter `transcribe()`, so the decode cost is unchanged by construction, but that is
   an argument, not a run of the real engine with/without the filter.
3. **The split-word cause is unresolved.** 14 live splits remain; the corpus has no token ids or
   audio for them. The synthetic replay proves a marked continuation would glue, not that these
   were unmarked. The latent cap-carry `cont=False` bug is reported, not landed.
4. **Language is only tested on one pt-BR clip.** No English arm was run; `auto` and `12` tie on
   the pt-BR fixture, and `0` refuses. The 10 Cyrillic lines cannot be attributed without audio.
5. **No shell change.** The stable-partial admission finding is for Main; this lane did not edit
   `app/panel/**` or `sotto_webview.py`.
6. **Only the in-process parakeet ingress is filtered.** `run_engine_pass` is the path that
   produced the measured 3 s-window corpus. The ternary runner path (`ReduxHiddenSwitch._run_runner`)
   and a direct `redux_batch.py` invocation still emit raw `Mmm`; their output was not in the
   measured corpus, and extending the filter there needs its own wiring arm.
7. **The structural gate is red overall, not because of this lane.** After extraction,
   `_main/code-health-oracle.py` reports `caption_noise.py` NEW (7 387 B), `engine_policy.py` LESS
   (−205 B, max function 96 → 92) and `engine_switch.py` SAME; every remaining RED is in
   `app/panel/**` or `app/webview/**`, which this lane must not edit.

## 5. Cheapest next actions, in measured order

1. **Shell:** refuse `reason=stable` in the history feed; take only the worker's closed
   `final:true` line. Measured target: 76 of 113 no-terminal lines; zero decode cost.
2. **Split words:** capture the token trace around one live split (`chunk_continues` values and
   whether `_close(carry=True)` ran); if the cap carry is involved, the one-line `cont` fix in
   `LineFormer.push`, with the synthetic replay as its negative arm. Do not add a dictionary.
3. **Batch punctuation:** if the owner still reads batch lines as truncated, the fix belongs in
   the line-closing policy (90-char cap and sentence punctuation), not in the decoder. This
   needs a paired latency/line-length measurement before landing; not attempted here.

## CACHE/PRICE
- task/agent: TranscriptQuality
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['TranscriptQuality']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['TranscriptQuality']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-10T00:59:15.594489+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['TranscriptQuality']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['TranscriptQuality']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## SELF-AUDIT

- **protocolos em falta** — I did not run the owner's live app or audio path (hard rule, correct), and I
  did not add the new `--selftest` to `_main/_audit-verify-all.cmd` (the battery is explicitly
  forbidden, and Main owns integration). I also did not edit the existing `_main` oracle family
  because the write scope allowed only `worker/**` plus this receipt; I would ask Main to wire
  `python worker/caption_noise.py --selftest` as a battery step.
- **verificacao adicional** — a real parakeet decode on the 14.56 s fixture with the filter on/off
  would turn the fake-engine cost into a live one (cost: ~10 s load + ~3 s decode, plus a
  second run); a token trace around one live split line would decide the cap-carry defect. Both
  are cheap in principle, but the former needs the real model and the latter needs audio the
  corpus does not contain.
- **checkboxes novas** — mechanical, not "be careful": (1) a census command that parses
  `history/*.md` and asserts the noise count and the no-terminal count are both printed, so a
  future claim cannot be made without the numbers; (2) the landed wiring arm: empty `_NOISE_WORD`
  and require both noise windows to publish, so removing the `admit_batch_caption` call turns the
  positive arms RED; (3) a two-colour predicate fixture that always includes `Mmm, mas eu vou.`
  as a must-keep line.
- **review por outro subagente** — `sim-com-escopo` — the shell-side stable admission (§2.5) and
  the latent cap-carry line (§2.2) should be reviewed by Main/the panel owner, because both are
  outside this lane's write scope and both can change the transcript more than the landed filter.
- **gate-doubt**
  - `verde-de-verdade:` `python worker/caption_noise.py --selftest` is a real green: 7 arms, run
    after the extraction. Arms 3–5 call the real `run_engine_pass`; arm 7 empties the
    `_NOISE_WORD` used by `admit_batch_caption` and requires both noise windows to publish. If
    the call is removed, the positive arms go RED, so this is a wiring arm, not only a predicate
    test. `_main/engine-serialization-oracle.py` (19/19) does not exercise batch caption text;
    its green is not evidence for this fix.
  - `falta-no-gate:` no gate asserts the **ternary runner** (`_run_runner`) or a direct
    `redux_batch.py` run is noise-free; only `run_engine_pass` is wired. A future change that
    routes a batch through `_run_runner` can publish `Mmm` again while this selftest stays green.
  - `gate-melhor:` a fake-runner arm that feeds `["Mmm.", "hello"]` through
    `ReduxHiddenSwitch._run_runner` and asserts only `hello` publishes; it is RED on today's
    unfiltered runner path, which is exactly the gap. Land it with the runner wiring, not now.
- **confianca** — `alta` for the census counts and the predicate's corpus effect (recomputed
  twice); `media` for the history outcome (no live run); `baixa` for the split-word cause (no
  token trace/audio).
- **nao verificado** — no app launch, no live audio, no end-to-end history write, no real-parakeet
  filter timing, no English language arm, no token trace for the 14 live split words, no shell
  change, no fake-runner arm. The ternary `_run_runner` path and a direct `redux_batch.py` run
  still emit raw `Mmm`; only `run_engine_pass` was measured and wired.
