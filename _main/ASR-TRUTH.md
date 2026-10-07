# ASR-TRUTH — does the product transcribe Portuguese?

Lane `lane/asrq2` · worktree `H:\sotto-wt\asrq2` · 2026-10-07.
Command 2 as briefed (`worktree add H:\sotto-wt\asr`) failed **rc=128** `'H:/sotto-wt/asr' already exists` —
that path is held by another lane's worktree (`chore/asr-truth-1`). Not destroyed; the same branch
`lane/asrq2` was checked out at `H:\sotto-wt\asrq2` instead. `H:\sotto` was never written (reads only).

## A. Architecture — forced or auto? (the decisive question)

**The worker does NOT force a single language. The default is the model's own AUTO slot.**

Flag — `worker/sotto_worker.py:2924-2931`, and there is **no `--lang` and no `--language`** flag
(`add_argument` scan returns nothing for either; only `--lang-id` exists):

```python
2924	    ap.add_argument(
2925	        "--lang-id",
2926	        default=None,
2927	        help="language prompt for the model: an id (12), a tag (pt-BR), 'auto' (101; the "
2928	        "shipped config default), or 'os' = the host's user locale (falls back to auto). "
```

Precedence and default — `sotto_worker.py:3128-3132` and `3152-3159`. Absent → `"auto"`, NOT the host locale:

```python
3129	    # Precedence: --lang-id > SOTTO_LANG_ID > config.json > 'auto'.
3132	    # THE DEFAULT IS `auto`, NOT `os` (F13).
3152	    if args.lang_id is not None:
3153	        lang_requested, lang_from = args.lang_id, "cli"
3154	    elif os.environ.get(_lp.ENV_VAR):
3155	        lang_requested, lang_from = os.environ[_lp.ENV_VAR], "env"
3156	    elif "lang_id" in (cfg.get("model") or {}):
3157	        lang_requested, lang_from = cfg["model"]["lang_id"], "config"
3158	    else:
3159	        lang_requested, lang_from = "auto", "default"
```

It is fed to the encoder, not to a post-hoc filter — `sotto_worker.py:535` builds the tensor and
`:796` sends it into the ONNX encoder's own `lang_id` input:

```python
535	        self.lid = np.array([self.lang_id], np.int64)
796	                "lang_id": self.lid,
```

The encoder is REQUIRED to declare that input (`:541-545`, raises `LangIdError`) — so `lang_id` is
part of the model's forward pass, and an undeclared value is refused (exit 2), never clamped.
Shipped `worker/config.json` → `"lang_id": "auto"`.

**Architecture: multi-prompt multilingual model, auto-detect by default, language selectable per-run
via `--lang-id` / `SOTTO_LANG_ID`.** One prompt may be forced, but nothing forces one.

## B. Model POPULATION

`H:\sotto\worker\models` — **POPULATION = 9 directories** (top-level files each):

| dir | files | MB |
|---|---|---|
| nemotron-3.5-asr-streaming-0.6b-fp16 | 9 | 1247.0 |
| nemotron-3.5-asr-streaming-0.6b-fp32 | 15 | 2478.8 |
| nemotron-3.5-asr-streaming-0.6b-int4 | 13 | 756.6 |
| nemotron-3.5-asr-streaming-0.6b-int8 | 14 | 1021.0 |
| parakeet-redux-onnx-int4 | 12 | 415.9 |
| parakeet-redux-reference | 3 | 0.1 |
| parakeet-redux-ternary | 6 | 170.7 |
| qwen3-0.6b-arm-int4 | 10 | 472.2 |
| qwen3.5-0.8b-ortgenai-cpu | 14 | 719.7 |

Shipped model (`config.json:model.dir`) = `nemotron-3.5-asr-streaming-0.6b-int8`.

**Multilingual — PROVEN, not inferred from size.** Two independent sources:

1. Model card `models/nemotron-3.5-asr-streaming-0.6b-int8/README.md` front matter:
   `language: [multilingual, ru, en, de, fr, es, zh, ja, ko, ar, hi, pt, it, nl, pl, tr, uk, vi, th]`
   — `pt` is declared. Upstream is *NVIDIA Nemotron-3.5-ASR-Streaming-**Multilingual**-0.6b*.
2. Language table `models/nemotron-3.5-asr-streaming-0.6b-fp16/languages.json` — 128 prompt slots:
   `"pt-BR": 12`, `"pt-PT": 13`, `"pt": 13`, `"auto": 101`, `"autoSlot": 101`.

(The int8 dir ships no `languages.json`; the resolver reads the fp16 one — confirmed at runtime by the
boot event below, which names that exact path as `table`.)

## C. Test — Portuguese audio, shipped default, no flags

Portuguese audio **already existed**, so nothing had to be generated or downloaded:
`H:\sotto\_main\pt-br-sample.wav` (661,544 B, 14.56 s @ 16 kHz mono).

```
python H:\sotto\worker\sotto_worker.py --selftest --audio H:\sotto\_main\pt-br-sample.wav
```
rc read from `$LASTEXITCODE` after redirect to file (never piped).

**rc = 0.** tokens 70, audio 14.560 s, load 4.175 s, infer 3.289 s, RTF 0.226, peak RSS 2415.0 MB,
providers `['CUDAExecutionProvider','CPUExecutionProvider']`, `empty_chunks=6`.

Resolved prompt, from the run's own boot event — `lang_id 101 (auto)`, `source config:auto`:

```json
{"type":"status","state":"boot","stage":"lang","lang_id":101,"lang":"auto","requested":"auto",
 "source":"config:auto","table":"...fp16\\languages.json","note":"the model's own auto slot, asked for explicitly"}
```

**POPULATION = 22 captions.** These are one growing line (`output.partial=true`), so they are prefixes,
not 22 independent utterances. The final closed line — which is the whole transcript:

> "rádio anunciou que a ponte sobre o vai ser interditada na próxima segunda-feira.  Os moradores
> precim de um caminho alternativo para chegar ao trabalho"

**Per-caption language check: 22/22 Portuguese.** Every prefix is Portuguese — *anunciou, ponte,
interditada, próxima, segunda-feira, moradores, caminho alternativo, chegar ao trabalho.* Portuguese
morphology and function words throughout. **Zero English tokens.** Auto-detect chose Portuguese for
Portuguese speech with no flag supplied.

Accuracy notes, honest: the model drops the word after *sobre* ("a ponte sobre o vai" — missing *rio*)
and mishears *precisam* as *precim*. Language ID is **correct**; word accuracy on this clip is
imperfect. That is a WER defect, not a language-support defect, and the two must not be conflated.

## D. Verdict on the doc claim

The refuting lane reported "the sample transcribes ENGLISH, rc=0, 120 tokens" as disproof of a
Portuguese claim. That inference does not hold:

- `_main/ASR-QUALITY.md` is titled **"ASR Quality - bundled English sample"** and its own §A declares
  `window=1 clip` on `sample1.flac`. **It makes no Portuguese claim to refute.** An English clip
  producing English is the doc working as written.
- English output is *not* evidence against Portuguese support. That inference requires the doc to
  promise Portuguese on English audio, which it does not.
- Directly measured on Portuguese audio with the shipped default: **rc=0, 22/22 captions Portuguese.**

The claim as stated ("the product does not do what its own docs claim for its primary market") is
**FALSE**. The docs do not claim Portuguese-on-English, and Portuguese-on-Portuguese is verified.
Two real defects are confirmed and belong in the record, but neither falsifies a Portuguese claim:
pt WER imperfection (§C) and `fp16` being the only dir shipping `languages.json` while being itself
unrunnable (`ASR-QUALITY.md` §D).

Scope limit stated plainly: POPULATION = 22 captions from **1 clip on 1 machine, 1 window (14.56 s)**.
This proves Portuguese is supported. It does **not** establish quality across accents, dialects,
channels or noise.

ASR CLAIM: FALSE - the docs claim no Portuguese-on-English behaviour (ASR-QUALITY.md is explicitly "bundled English sample"), and Portuguese was measured working: rc=0, 22/22 captions Portuguese on pt-br-sample.wav with the shipped lang_id:auto.