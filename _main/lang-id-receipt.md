# SottoLangId — receipt: the language prompt was en-US (0) against a pt-BR owner's audio

Repo `H:/sotto`. Lane SottoLangId. 2026-10-06.

## WHAT THE DEFECT WAS

`worker/config.json` had `"lang_id": 0`, which the model's OWN `languages.json` defines as
`en-US`, while the owner's audio is Brazilian Portuguese (`pt-BR` = 12). Two halves, and the
second was the one nobody had noticed:

1. The value was wrong for the owner (`0` instead of `12`/`13`/`101`).
2. **The value never reached the model at all.** `main()` had

   ```python
   ap.add_argument("--lang-id", type=int, default=0)          # worker/sotto_worker.py:960 (before)
   ...
   lang_id = args.lang_id if args.lang_id is not None else cfg["model"]["lang_id"]   # :1023
   ```

   `default=0` is never `None`, so the `else` branch was unreachable on every run: the config
   key was documented in `worker/README.md` AND `docs/model-specs/README.md`, shipped in the
   config, and inert. `--lang-id` DID reach the model (flag -> `args.lang_id` -> `StreamAsr(lang_id=)` ->
   `self.lid` -> fed as the encoder's `lang_id` input). The config value was dropped.

## WHAT CHANGED

| file | change |
|---|---|
| `worker/lang_prompt.py` | NEW. Resolves the prompt from the model's own `languages.json`; `--lang-id` > `SOTTO_LANG_ID` > config > shipped default; refuses an undeclared id |
| `worker/sotto_worker.py` | `--lang-id` default `None` (was `0`) and now accepts a tag as well as an id; resolution runs BEFORE the model load; `StreamAsr` validates and reads back the encoder's declared `lang_id` input; the resolved value is named on stdout (`state=boot, stage=lang`) and on stderr |
| `worker/config.json` | `"lang_id": "os"` (was `0`), plus a `_comment_lang_id` naming the accepted values |
| `AGENTS.md`, `docs/model-specs/README.md` (§3, §6.2, §7), `worker/README.md` (§Config) | deviation row/§ marked RESOLVED; the contract documents the new setting |
| `_main/lang-id-oracle.py` | NEW, re-runnable oracle (rc 0 = OK) over the table, the ids, the default, the refusal, and the encoder read-back |
| `_main/lang-id-runs.py` | NEW, the arm harness (7 arms, one process each, launched hidden) |
| `_main/make-tts-samples.ps1` | NEW, builds a known-language pt-BR/en-US pair with the SAPI voices this box has |

### The default, and why

`"os"` — the host's USER locale (`GetUserDefaultLocaleName`; measured `pt-BR` on this box),
mapped through the model's own table, falling back to the model's `auto` slot (101) when the
locale names no slot. Not a hardcoded `pt-BR`.

Reasons: (a) the app ships to any user, and the owner's machine is one user among them —
the OS locale is the only per-user signal available without a UI; (b) it is FIXED for the
whole stream, where `auto` is not — this repo's own `docs/oss-approaches-20261006.md` A6
records that auto-detection "switches language mid-stream on accented audio" and "tends to
bias towards English", which is exactly the owner's streaming case; (c) `auto` is one config
value away for anyone who wants it. The honest cost of this choice is measured below (arm B).

## PROOF THAT THE VALUE REACHES THE MODEL

Read-back, from the constructed session (`_main/lang-id-oracle.log`):

```
enc inputs  : ['audio_signal', 'length', 'cache_last_channel', 'cache_last_time', 'cache_last_channel_len', 'lang_id']
lang_input  : lang_id
lid fed     : [12] int64
  encoder lang_id=0    -> shape (1, 7, 1024) mean|out|=0.032538
  encoder lang_id=12   -> shape (1, 7, 1024) mean|out|=0.038830
  encoder lang_id=999  -> shape (1, 7, 1024) mean|out|=0.383555
  max|enc(lang_id=0) - enc(lang_id=12)| = 0.534810  (0 would mean the input is ignored)
```

Same audio, same caches, only `lang_id` differing: the encoder output MOVES (0.534810), so
the input is consumed, not ignored. The resolved id is logged on every run:

```
{"type": "status", "state": "boot", "stage": "lang", "lang_id": 12, "lang": "pt-BR",
 "requested": "os", "source": "config:os-locale",
 "table": "H:\\sotto\\worker\\models\\nemotron-3.5-asr-streaming-0.6b-fp16\\languages.json",
 "note": "host locale 'pt-BR'"}
```

## THE ARMS (one process each, launched hidden with CREATE_NO_WINDOW alone)

`py -3 _main/lang-id-runs.py` -> `_main/lang-id-arm-*.jsonl/.err`

| arm | args | rc | resolved | source | `model-loaded.lang_id` | tokens | text |
|---|---|---|---|---|---|---|---|
| A-lang0 | `--lang-id 0` | 0 | 0 en-US | cli:id | 0 | 94 | `'Going along  slushy Country roads  speaking damp  in dr drafty school  day For a fortnight He'll have  an appearance At some Sunday morning and  he can come to  immediate'` |
| **B-default** | (none) | 0 | **12 pt-BR** | **config:os-locale** | **12** | 10 | `'Going along Day'` |
| C-config13 | `--config <lang_id:13>` | 0 | 13 pt-PT | config:id | 13 | 22 | `"Going along Country roads Day He'll have"` |
| D-env13 | `SOTTO_LANG_ID=13` | 0 | 13 pt-PT | env:id | 13 | 22 | `"Going along Country roads Day He'll have"` |
| E-neg999 | `--lang-id 999` | **2** | — | — | — | — | refused in **0.1 s**, no model load |
| F-pt-0 | pt-BR audio, `--lang-id 0` | 0 | 0 en-US | cli:id | 0 | 5 | `'O radio'` |
| G-pt-12 | pt-BR audio, `--lang-id 12` | 0 | 12 pt-BR | cli:id | 12 | 18 | `'O rádio Segunda feira Os moradores'` |

Arm B is the fix, end to end: with NO flag, the shipped config resolves through the host
locale to 12 and the session reports `lang_id=12`. Arms C and D are the clean proof that each
new rung reaches the model (a value that is neither the default nor the host locale, visible
in `model-loaded.lang_id` read back off the session). Arm A is the old behaviour.

### The two required transcripts, verbatim

Arm A — as it was (`--lang-id 0`), `_main/lang-id-arm-A-lang0.err`:

```
lang_id      : 0 (en-US) source=cli:id table=languages.json
--- selftest ---
audio        : H:\sotto\worker\assets\sample1.flac
audio_s      : 13.440
load_s       : 4.114
infer_wall_s : 3.916
rtf          : 0.291
tokens       : 94
blank_frac   : 0.6412 (frames=262 empty_chunks=8 vad_gated_chunks=0)
peak_rss_mb  : 2406.2
providers    : ['CUDAExecutionProvider', 'CPUExecutionProvider']
RECOGNISED   : "Going along  slushy Country roads  speaking damp  in dr drafty school  day For a fortnight He'll have  an appearance At some Sunday morning and  he can come to  immediate"
--- end selftest ---
```

Arm B — the shipped default now (`--selftest`, no flag), `_main/lang-id-arm-B-default.err`:

```
lang_id      : 12 (pt-BR) source=config:os-locale table=languages.json
--- selftest ---
audio        : H:\sotto\worker\assets\sample1.flac
audio_s      : 13.440
load_s       : 7.455
infer_wall_s : 4.452
rtf          : 0.331
tokens       : 10
blank_frac   : 0.9438 (frames=178 empty_chunks=22 vad_gated_chunks=0)
peak_rss_mb  : 2405.8
providers    : ['CUDAExecutionProvider', 'CPUExecutionProvider']
RECOGNISED   : 'Going along Day'
--- end selftest ---
```

**Arm B is a REGRESSION on English audio and must be stated as one.** `sample1.flac` is
English read speech; feeding it `pt-BR` drops 94 tokens to 10. The `"os"` default is
per-user, not per-utterance: it assumes the OS locale matches the language of the audio. A
pt-BR-locale user watching English content must set `lang_id` explicitly (or `"auto"`).
I do not claim otherwise.

## NEGATIVE ARM

`--lang-id 999` -> rc **2** in **0.1 s**, before `_add_cuda_dll_dirs()` and before any
session is built. stdout (`_main/lang-id-arm-E-neg999.jsonl`):

```
{"type": "status", "state": "boot", "stage": "start", "pid": 2560, "argv": ["--selftest", "--lang-id", "999"], "mode": "file"}
{"type": "status", "state": "error", "stage": "lang-id", "detail": "lang_id '999' is NOT declared by this model (an integer outside the declared slot set). H:\\sotto\\worker\\models\\nemotron-3.5-asr-streaming-0.6b-fp16\\languages.json declares 84 prompt slots (ids 0..104 named, plus autoSlot 101; e.g. 0=en-US, 12=pt-BR, 13=pt/pt-PT, 101=auto). Refused rather than clamped: an undeclared id is an undefined embedding row, and silently falling back would put the wrong language in front of the model with no trace in the run. Fix the value (an id, a language tag like 'pt-BR', 'auto', or 'os') or list the slots with: py -3 worker/lang_prompt.py --list", "requested": "999", "source": "cli"}
```

The oracle also refuses `-1`, `300`, `128`, `107`, `"klingon"`, `"zz-ZZ"` (all 7 checked, all
`LangIdError`). **Why the refusal is load-bearing, measured:** onnxruntime itself ACCEPTED
`lang_id=999` on the encoder and returned numbers (`mean|out|=0.383555`, ~12x the valid arms).
The graph does not police the slot. Nothing but this resolver stands between a typo and a
silently wrong prompt.

## CAN I SHOW A QUALITY DIFFERENCE? — YES, ON SYNTHETIC AUDIO ONLY

Arms F and G use `_main/pt-br-sample.wav`, a sentence spoken by `Microsoft Maria Desktop`
(pt-BR) via SAPI, generated on this box because no Portuguese audio exists in the repo:

* `--lang-id 0` (en-US prompt): **5 tokens**, `'O radio'`
* `--lang-id 12` (pt-BR prompt): **18 tokens**, `'O rádio Segunda feira Os moradores'`

The words recovered at 12 (`rádio`, `Segunda feira`, `moradores`) are content words that are
actually in the spoken sentence; at 0 almost nothing survives. **Limits, stated plainly:**
this is TTS synthetic speech, not the owner's audio; neither arm transcribes the sentence
fully; the numbers are token counts, not WER. I claim a real direction, not a measured
quality gain on the owner's own recordings. Arm C is the mirror check: `pt-PT` on the ENGLISH
sample gives 22 tokens vs 94 at en-US — a wrong prompt degrades in both directions.

## SELF-AUDIT

- **protocolos em falta:** the repo already had `_main/model-spec-oracle.py` as the canonical
  `config.json`-vs-spec oracle, and I wrote a SECOND oracle before checking it. The protocol I
  should have followed: read the existing oracle as the contract and extend it. What I would do
  differently: add the prompt check to `model-spec-oracle.py` first, and only split if the merged
  one became too slow. I kept them split (the old one loads no model, ~ms; mine loads ~1.2 GB)
  because an oracle that takes 5 s stops being run — but that is a decision that should have been
  visible from the start, not discovered afterwards.
- **verificacao adicional:** the en-US-audio-with-pt-BR-prompt arm (C) — it is the only arm that
  measures the REGRESSION the new default can cause, and it is what makes the honest cost claim
  possible. Cost: 10 s.
- **checkboxes novas (mecanicas):** (a) `py -3 worker/lang_prompt.py --list` exits 0 whenever the
  table or the resolver is touched; (b) an assertion pair in the oracle — `resolve(999)` must RAISE
  **and** `enc(lang_id=0) != enc(lang_id=12)` must hold on the same instrument (a refusal proves
  nothing if the accepted id is also ignored); (c) `git diff worker/config.json` must show the key
  the code actually reads — today's bug was a config key that was read by nothing and no gate
  looked at the file at all.
- **review por outro subagente:** sim-com-escopo — `worker/lang_prompt.py` plus the resolution block
  in `worker/sotto_worker.py` (the only part with decision logic). The rest is wiring whose
  behaviour is verified by execution above.
- **gate-doubt:**
  - **verde-de-verdade:** `py -3 _main/lang-id-oracle.py` -> rc 0. Real, not vacuous: it prints the
    `[RED]` rows it is able to emit, and its verdict depends on real ORT work (1.2 GB encoder, 3
    runs with different `lang_id`, max-abs-diff 0.534810). It cannot pass by construction — if the
    resolver returned a constant, checks 2, 3 and 5 would go RED. The 7-arm table likewise fails if
    any rung is dropped. The WEAKEST green is the F/G pair (5 vs 18 tokens on synthetic audio) and
    it is labelled as weak rather than dressed up.
  - **falta-no-gate:** the oracle does NOT verify that the config KEY the code reads is the key that
    exists — it inspects the argparse default by text, so a rename of `model.lang_id` in
    `worker/config.json` would silently fall back to `"os"` and the oracle would stay GREEN. A
    future change that renames the key (or moves the prompt under `model.speech.lang_id`) crosses
    this hole. I tried to break the config->model pair by another route and could not: arms C and B
    both bind the config value to `loaded.lang_id`.
  - **gate-melhor:** one comparison, per arm, between the `boot/stage=lang` line and the
    `model-loaded` line of the SAME run — if `source` starts with `config` and `loaded.lang_id !=
    lang_id`, RED. Input that must leave it RED: `--config` a file with `"lang_id": 12` and a worker
    that ignores the config (the pre-fix code) -> `lang_id=12` on the boot line, `loaded.lang_id=0`.
- **confianca:** alta no mecanismo (resolved, refused, delivered — all three measured). Media no
  default `"os"`: it is the best per-user signal available without a UI, but it assumes OS locale
  == audio language, and arm B prices that assumption.
- **nao verificado:** (1) no real owner audio — the quality evidence is SAPI TTS; (2) the app shell
  (`app/webview/run.cmd`) was not run with the new default, only the worker in `--selftest`; (3)
  `use_vad` was flipped to `true` by the sibling lane SottoVadOn in `worker/config.json` DURING this
  work, and my arms inherit that value — VAD was not isolated from `lang_id`; (4) no WER was
  measured, only token counts and the text itself.

## GATE-CHANGE REQUEST

`gate-change-request: n/a — no gate was found to be wrong. The hole named under gate-doubt
(falta-no-gate) is a gap in MY new oracle, not in an existing gate, and the fix for it is
stated there as `gate-melhor`; there is no patch to merge into a gate this lane does not own.`

## MEASUREMENT THAT CONTRADICTS THE BRIEF / PRIOR NOTES

1. The brief said "nobody owns" `lang_id`. Beyond the wrong value, the config key was **dead
   code** — the CLI default shadowed it on every run. That second half is the reason a fix that
   only changed the number would have changed nothing.
2. `docs/oss-approaches-20261006.md` A6 said `config.json:16` was "**already fixed**, i.e. Sotto is
   already right here — leave as is". That is WRONG: `0` is `en-US` and the owner's audio is
   Portuguese. Its underlying argument (auto-detection switches language mid-stream) is real and is
   why the shipped default is the OS locale rather than `auto` — the reasoning was kept, the
   conclusion discarded. A6 is now contradicted by a measured arm (F vs G).
3. Reverse-engineering note, recorded because it was measured: the window census logged
   `ALERTA-JANELA ... pid=24836 nome=python` at 06:42:22Z while I was running `py -3`; the command
   line was `python.exe sotto_webview.py --with-worker ... --log H:/sotto/_main/exit3-armB1.log` —
   the sibling lane SottoExit3Panel, NOT this lane. My own runs launch through `CREATE_NO_WINDOW`
   alone and the census stayed at 13 visible windows with no further ALERTA. I could not message
   that peer: `write agent://SottoExit3Panel` was refused by the owner-screen guard as a path
   (`I:\!manager\agent:\SottoExit3Panel`, parent does not exist).

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoLangId
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLangId.jsonl
- cache: read=8000324 write=0 hit=96.9640% (cache-read / input+cache-read); universe: 63 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLangId.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=49 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=14 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 63 of 63 matched usage rows
- when-failed: break_items=36; WHEN=2026-10-06T06:39:50.329000+00:00 | break_items=2; WHEN=2026-10-06T06:40:16.325000+00:00 | break_items=1; WHEN=2026-10-06T06:46:16.198000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 112257 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLangId']; window: 2026-10-06T06:39:50.329000+00:00..2026-10-06T06:46:16.198000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fef-210c-736d-b990-520372592a27 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791268790329 | session_id=01a10fef-210c-736d-b990-520372592a27 provider=deepseek-flash model=deepseek-flash item_index=82; turn_id=1791268816325 | session_id=01a10fef-210c-736d-b990-520372592a27 provider=deepseek-flash model=deepseek-flash item_index=207; turn_id=1791269176198 (state=RESOLVED-BREAKS-OMP; population: 3 of 112257 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLangId']; window: 2026-10-06T06:39:50.329000+00:00..2026-10-06T06:46:16.198000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T06:48:53.591916+00:00
- usage rows: 63
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 250492
- output tokens: 61122
- cache-read tokens: 8000324
- cache-write tokens: 0
- hit ratio: 96.9640% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 39 (state=RESOLVED-BREAKS-OMP; population: 3 of 112257 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLangId']; window: 2026-10-06T06:39:50.329000+00:00..2026-10-06T06:46:16.198000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
