# Receipt — 2026-10-11 — the Redux arm gate: the runner FILE is not the ENGINE

Lane: two defects fixed in `H:\sotto`, with an oracle that can say NO. Every anchor below was
re-measured in this session on the bytes named; the hints in the brief were treated as hints.
**Nothing was launched** — no `sotto_webview.py`, no `run.cmd`, no worker, no GUI/WebView2 probe,
no `_main\_audit-verify-all.cmd`. The owner's stop order (*"para de abrir o sotto, ta travando meu pc
quando ele abre"*) is in force and was obeyed. The only child process this lane spawned is `node`
(`--check`, and the oracle's in-process store driver), always with
`CREATE_NO_WINDOW = 0x08000000`.

---

## 1. THE QUESTIONS

**A.** `worker/sotto_worker.py`, class `ReduxHiddenSwitch` (the `--redux-when-hidden` switch,
DEFAULT OFF) armed itself on ONE fact:

```python
self.runner_available = os.path.exists(self.runner)
self.armed = bool(self.enabled and self.runner_available)
```

The runner FILE is not the ENGINE. `_run_runner` invokes the runner as
`[sys.executable, self.runner, "--wav", wav_path, "--json"]` — **no `--model-dir`** — so the runner
resolves its OWN checkpoint (`worker/redux_batch.py:38-39`:
`HERE = Path(__file__).resolve().parent`, `DEFAULT_MODEL_DIR = HERE / "models" / "parakeet-redux-ternary"`)
and `load_runtime` raises `SystemExit` on the first missing manifest
(`config.json` `:112`, `model.safetensors` `:114`, `ternary.json` `:116`).

Measured today on this box: `worker/models/` holds **ONE** directory
(`nemotron-3.5-asr-streaming-0.6b-int8`) and `worker/models/parakeet-redux-ternary` is **ABSENT**.
With the flag ON and the gate armed on the file alone, the switch cuts the streaming decode while the
panel is hidden (`asr_thread` skips streaming in batch mode) and every batch pass then dies inside
`load_runtime`: **no transcriber at all, silently**. The only guard was the flag's default being OFF.

Question A: *can the gate refuse to arm when the checkpoint the runner will LOAD is not on disk, say
so ONCE and LOUDLY naming the missing path — and still behave byte-for-byte as before when the
checkpoint IS there?*

**B.** `app/panel/history-store.js`'s `ROUTE_SOURCES` (the allow-list that gates the `src=` marker
in `provenance()`) omitted `'worker-stamped-producer'` — a token
`app/panel/caption-formulation.js routeSourceFor()` declares at `:501`. A line carrying it was
written with **no `src=` marker at all**.

Question B: *does the allow-list carry every token the panel's own formulation code can declare?*

---

## 2. THE EDITS (the only two source files touched)

### 2.1 `worker/sotto_worker.py` — five hunks

**(i) constants, after `REDUX_RUNNER_DEFAULT` (`:3047`)** — new `:3048-3059`:

```python
#: The checkpoint that runner LOADS when it is invoked with no `--model-dir`,
#: RELATIVE to the runner's own directory — `redux_batch.py` resolves it exactly
#: this way (`HERE = Path(__file__).resolve().parent`, then
#: `DEFAULT_MODEL_DIR = HERE / "models" / "parakeet-redux-ternary"`). `_run_runner`
#: passes no `--model-dir`, so this is the directory every batch pass will open.
#: Keep it in step with `redux_batch.py`: the gate below must refuse to arm on a
#: checkpoint the runner cannot LOAD.
REDUX_CHECKPOINT_RELPATH = os.path.join("models", "parakeet-redux-ternary")
#: The manifests `redux_batch.load_runtime` demands, in ITS order: the first one
#: missing is the `SystemExit` that kills the pass. The DIRECTORY existing is not
#: the test — a directory without these loads nothing.
REDUX_CHECKPOINT_FILES = ("config.json", "model.safetensors", "ternary.json")
```

**(ii) two module-level helpers, before the class (`:3172-3187`)**:

```python
def redux_checkpoint_dir(runner):
    """The checkpoint the batch runner opens when it is given no `--model-dir`.

    Resolved the way `redux_batch.py` resolves its own default — relative to the
    runner's directory (`HERE = Path(__file__).resolve().parent`) — because
    `_run_runner` passes the runner no `--model-dir` and the runner therefore
    loads exactly this path, whatever directory the worker was started from.
    """
    return os.path.join(os.path.dirname(os.path.realpath(runner)),
                        REDUX_CHECKPOINT_RELPATH)


def redux_checkpoint_missing(model_dir):
    """The manifests NOT on disk under `model_dir`; `[]` when it can load."""
    return [name for name in REDUX_CHECKPOINT_FILES
            if not os.path.isfile(os.path.join(model_dir, name))]
```

**(iii) the class docstring's gate-2 paragraph** now names the runner FILE *and* the checkpoint
it will LOAD (the HARD RULE reason is stated where the gate is documented).

**(iv) `__init__` gained the testability hook** `model_dir=None` (`:3236`) — production passes
nothing and the derivation runs (proved by check W15).

**(v) THE GATE (`:3248-3265`)** — BEFORE:

```python
        self.runner_available = os.path.exists(self.runner)
        self.armed = bool(self.enabled and self.runner_available)
```

AFTER:

```python
        # ── gate 2, decided ONCE, at construction, and stated in the log ─────
        # TWO facts, not one: the runner FILE and the checkpoint it will LOAD.
        # `_run_runner` invokes the runner with no `--model-dir`, so the runner
        # resolves its own `models/parakeet-redux-ternary` — and with that
        # directory absent (measured on this box 2026-10-11: `worker/models/`
        # holds only the nemotron export) every batch dies in
        # `redux_batch.load_runtime`'s SystemExit. Armed on the file alone, the
        # switch would cut the streaming decode in the asr thread (`if mode ==
        # "batch": ... continue`) and leave the owner with NO transcriber at all,
        # silently. So the checkpoint is part of the gate, and the refusal names
        # the path that is missing.
        self.runner_available = os.path.exists(self.runner)
        self.model_dir = os.path.abspath(
            model_dir if model_dir else redux_checkpoint_dir(self.runner))
        self.model_missing = redux_checkpoint_missing(self.model_dir)
        self.model_available = not self.model_missing
        self.armed = bool(
            self.enabled and self.runner_available and self.model_available)
```

`self.runner_available = os.path.exists(self.runner)` is kept **verbatim** — the old fact is still
reported, it is just no longer sufficient.

**(vi) `boot_line` (`:3297-3316`)** — the old `else:` (runner-missing) became
`elif not self.runner_available:` with its message **byte-identical**, and a NEW `else:` branch
states the distinct reason and the missing path:

```python
        else:
            # The runner IS on disk and the checkpoint it will LOAD is not: the
            # distinct reason (and the path) is the whole point of this branch —
            # a bare `armed=false` would leave the next reader hunting for why.
            self.log(
                f"REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing "
                f"runner={self.runner} model_dir={self.model_dir} "
                f"missing={','.join(self.model_missing)} — the batch engine cannot "
                f"LOAD this checkpoint (`redux_batch.load_runtime` exits on the "
                f"first missing manifest), so the streaming capture is NOT cut "
                f"while the panel is hidden (today it is the only transcriber)")
```

**NOT changed:** `REDUX_WHEN_HIDDEN_DEFAULT` stays `False`; `REDUX_PRODUCER` stays the literal
`"redux"`; the armed boot line is untouched (proved by W6); `tick`/`maybe_kick`/`flush_pending`
are untouched; the call site (`:5025-5044`) passes no `model_dir`.

### 2.2 `app/panel/history-store.js` — one line + its comment

BEFORE (`:60` region, no comment):

```js
const ROUTE_SOURCES = ['worker-stamped', 'panel-deadline', 'fallback'];
```

AFTER (`:44-60`), the new comment states why the token is there and why the defect was latent:

```js
 * `'worker-stamped-producer'` is the SAME route decided by a DIFFERENT fact:
 * `caption-formulation.js routeSourceFor` returns it for a line that DECLARES
 * a producer while no worker `final` vote decided the route. It was declared
 * there (`:501`) and missing here until 2026-10-11, so such a line would have
 * been written with no `src=` marker at all — the provenance thinner than the
 * decision that produced it. (`panel.js recordHistory`'s `route !== 'final'`
 * guard is what kept it latent: a producer-stamped line with no worker vote is
 * usually not a `final` route.)
 */
const ROUTE_SOURCES = ['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback'];
```

The declared set is now exactly the four tokens `routeSourceFor` can return
(`'worker-stamped'` `:492`, `'worker-stamped-producer'` `:501`, `'fallback'` / `'panel-deadline'` `:502`).

---

## 3. FILES TOUCHED (bytes + sha256 + mtime, measured after the last edit)

| file | bytes | CRLF / bare LF | sha256 | mtime (UTC) |
|---|---|---|---|---|
| `worker/sotto_worker.py` (edited) | 295867 | 5693 / 0 | `2C0AF4FB8B22D3D15BE9AEAD051CDDC45AC062C0CE73EB260D6F893F3A106CC4` | 2026-10-11T22:24:41Z |
| `app/panel/history-store.js` (edited) | 9766 | 0 / 256 | `0A81FD98378911FC416DD9335EE5557008B0C628B36FC010D333CC41D47E76DC` | 2026-10-11T22:25:13Z |
| `_main/redux-arm-weights-oracle.py` (new) | 27218 | 0 / 601 | `DA0F5FFCDCD74E7E81E4620C0D0FBA399A3CE2114F211CE1C4DCD02609FD694D` | 2026-10-11T22:36:30Z |
| `_main/receipt-20261011-redux-arm-weights.md` (new) | 32688 | 0 / 490 | `4FF44D388389D00156364049732B23690CF01F9D880C1D883E6C9EE6E2870BD8` | 2026-10-11T22:39:31Z |

Unchanged, read-only subjects of the oracle: `worker/redux_batch.py` 8559 B /
`C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989` / 2026-10-07T07:39:45Z;
`app/panel/caption-formulation.js` 40333 B /
`6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072` / 2026-10-11T21:25:47Z.

`git status --porcelain` for the two edited files, after all work:
` M worker/sotto_worker.py` and ` M app/panel/history-store.js`; the oracle is `?? _main/redux-arm-weights-oracle.py`.
**No git write command was run by this lane** (no `add`, no `commit`) — the Lead commits.

---

## 4. THE INSTRUMENT: `_main/redux-arm-weights-oracle.py`

In process. It imports the REAL `worker/sotto_worker.py` by path (`importlib`, with
`sys.dont_write_bytecode = True`), imports the REAL `worker/redux_batch.py` by path, reads the REAL
`app/panel/history-store.js` and `app/panel/caption-formulation.js` bytes, and spawns ONLY `node`
invisibly for the store side. It never launches the app, the shell or the worker.

* **ARM G, GREEN colour (W5-W8):** a `%TEMP%` runner with the checkpoint it derives arms the switch
  (no `model_dir` passed — the derivation itself is exercised), the armed boot line keeps its shape,
  and the mode machine still goes `stream → batch → stream`.
* **ARM G, RED colour (W9-W13):** the REAL runner with the REAL (absent) checkpoint refuses —
  `armed=False`, `reason=checkpoint-missing`, `model_dir=H:\sotto\worker\models\parakeet-redux-ternary`,
  `missing=config.json,model.safetensors,ternary.json` — one line, and the switch stays inert
  (10 ticks + `maybe_kick` add no line, `mode` stays `stream`).
* **ARM J (J1-J5):** every token `routeSourceFor` declares is appended through the store's OWN
  `append()` (with `SOTTO_HISTORY_ROOT` in `%TEMP%`) and must carry its exact `src=` marker; an
  unknown token is still written WITHOUT `src=`; a `provisional-draft` is still refused.
* **`--neg-arm`:** four mutants of the REAL bytes, built in memory and written to `%TEMP%`. Each
  mutant's RED set must equal its expected set EXACTLY (extra RED = FAIL, missing RED = FAIL), and a
  comment-only control must move nothing. A mutant whose anchor is not found is a **SETUP ERROR
  (rc=2)**, never a silent pass.
* Exit codes: **0 PASS, 1 FAIL, 2 SETUP ERROR**.

### 4.1 Instrument note (honest, and it is why W3 exists)

The first pass of this oracle went **RED on `W3`**: the extraction over `load_runtime`'s body also
matched the signature default `device: str = "cpu"`, so it read four names
(`['cpu', 'config.json', 'model.safetensors', 'ternary.json']`). The extraction was narrowed to the
manifest predicate itself — `(model_dir / "NAME")` — which is the thing the loader actually tests.
This is recorded because it is the difference between "the code is wrong" and "the instrument was
too broad", and only the second was true.

---

## 5. THE COMMANDS, AND THEIR RAW OUTPUT

### 5.1 `py -3 _main/redux-arm-weights-oracle.py` → `VERDICT: PASS`, rc=0

Full output, verbatim (42 lines; saved at `I:\cc-tmp\redux-arm-green.txt`):

```text
SOTTO redux-arm-weights-oracle -- in process; the app, the shell and the worker are NEVER launched
PIN worker/sotto_worker.py bytes=295867 sha256=2C0AF4FB8B22D3D15BE9AEAD051CDDC45AC062C0CE73EB260D6F893F3A106CC4 mtime=2026-10-11T22:24:41Z
PIN worker/redux_batch.py bytes=8559 sha256=C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989 mtime=2026-10-07T07:39:45Z
PIN app/panel/history-store.js bytes=9766 sha256=0A81FD98378911FC416DD9335EE5557008B0C628B36FC010D333CC41D47E76DC mtime=2026-10-11T22:25:13Z
PIN app/panel/caption-formulation.js bytes=40333 sha256=6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072 mtime=2026-10-11T21:25:47Z
node=C:\Program Files\nodejs\node.EXE
REAL_DISK worker/models dirs=['nemotron-3.5-asr-streaming-0.6b-int8']
REAL_DISK checkpoint H:\sotto\worker\models\parakeet-redux-ternary exists=False
TEMP_ROOT I:\cc-tmp\redux-arm-weights-w5it3yk0
== ARM G: the REAL bytes, as shipped ==
  GREEN G:W1-checkpoint-constants -- REDUX_CHECKPOINT_RELPATH='models\\parakeet-redux-ternary' REDUX_CHECKPOINT_FILES=('config.json', 'model.safetensors', 'ternary.json')
  GREEN G:W2-runner-own-default-agrees -- worker derives H:\sotto\worker\models\parakeet-redux-ternary | redux_batch.DEFAULT_MODEL_DIR H:\sotto\worker\models\parakeet-redux-ternary
  GREEN G:W3-manifest-order-matches-load_runtime -- load_runtime tests for ['config.json', 'model.safetensors', 'ternary.json'] in that order; the gate demands ['config.json', 'model.safetensors', 'ternary.json']
  GREEN G:W4-flag-default-and-producer-literal -- REDUX_WHEN_HIDDEN_DEFAULT=False REDUX_PRODUCER='redux'
  GREEN G:W5-arms-when-the-checkpoint-is-there -- armed=True model_dir=I:\cc-tmp\redux-arm-weights-w5it3yk0\green-derived\models\parakeet-redux-ternary missing=[]
  EVIDENCE G:armed-line=REDUX_SWITCH armed=true by=--redux-when-hidden hidden_after_s=20.0 batch_interval_s=15.0 max_audio_s=120.0 min_free_mb=4600.0 runner=I:\cc-tmp\redux-arm-weights-w5it3yk0\green-derived\redux_batch.py visibility=<oracle-fake-visibility>
  GREEN G:W6-armed-line-shape-unchanged -- REDUX_SWITCH armed=true by=--redux-when-hidden hidden_after_s=20.0 batch_interval_s=15.0 max_audio_s=120.0 min_free_mb=4600.0 runner=I:\cc-tmp\redux-arm-weights-w5it3yk0\green-derived\redux_batch.py visibility=<oracle-fake-visibility>
  GREEN G:W7-explicit-model-dir-wins-over-the-derivation -- armed=True model_dir=I:\cc-tmp\redux-arm-weights-w5it3yk0\explicit-ckpt
  GREEN G:W8-mode-machine-still-switches -- tick sequence=('stream', 'batch', 'stream') switches=2
  GREEN G:W9-real-disk-refuses -- armed=False model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=['config.json', 'model.safetensors', 'ternary.json']
  EVIDENCE G:refusal-line=REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=H:\sotto\worker\redux_batch.py model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=config.json,model.safetensors,ternary.json — the batch engine cannot LOAD this checkpoint (`redux_batch.load_runtime` exits on the first missing manifest), so the streaming capture is NOT cut while the panel is hidden (today it is the only transcriber)
  GREEN G:W10-refusal-names-reason-and-path -- REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=H:\sotto\worker\redux_batch.py model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=config.json,model.safetensors,ternary.json — the batch engine cannot LOAD this checkpoint (`redux_batch.load_runtime` exits on the first missing manifest), so the streaming capture is NOT cut while the panel is hidden (today it is the only transcriber)
  GREEN G:W11-refusal-is-one-line-and-inert -- lines_after_boot=1 lines_after_10_ticks=1 maybe_kick=False mode=stream
  GREEN G:W12-partial-checkpoint-names-what-is-missing -- missing=['model.safetensors', 'ternary.json'] line=REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=I:\cc-tmp\redux-arm-weights-w5it3yk0\partial\redux_batch.py model_dir=I:\cc-tmp\redux-arm-weights-w5it3yk0\partial\models\parakeet-redux-ternary missing=model.safetensors,ternary.json — the batch engine cannot LOAD this checkpoint (`redux_batch.load_runtime` exits on the first missing manifest), so the streaming capture is NOT cut while the panel is hidden (today it is the only transcriber)
  GREEN G:W13-runner-missing-reason-still-distinct -- REDUX_SWITCH_REFUSED armed=false reason=runner-missing runner=I:\cc-tmp\redux-arm-weights-w5it3yk0\not-here\redux_batch.py — the batch engine is not on disk, so the streaming capture is NOT cut while the panel is hidden (today it is the only transcriber)
  GREEN G:W14-flag-off-is-still-gate-1 -- armed=False log_lines=0
  GREEN G:W15-call-site-uses-the-derivation -- call sites=1 runner=args.redux_batch=True model_dir-in-call=False
  EVIDENCE G:declared-sources=['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback']
  EVIDENCE G:allow-list=['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback']
  GREEN G:J1-allow-list-covers-every-declared-token -- missing=[]
  GREEN G:J2-allow-list-has-no-extras -- allow-list=['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback'] declared=['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback']
  EVIDENCE G:history-root=I:\cc-tmp\redux-arm-weights-w5it3yk0\store-G\history-root
  EVIDENCE G:written: - [19:36:36] oracle line 1 <!-- route=final start=1.50 src=worker-stamped reason=oracle -->
  EVIDENCE G:written: - [19:36:36] oracle line 2 <!-- route=final start=1.50 src=worker-stamped-producer reason=oracle -->
  EVIDENCE G:written: - [19:36:36] oracle line 3 <!-- route=final start=1.50 src=panel-deadline reason=oracle -->
  EVIDENCE G:written: - [19:36:36] oracle line 4 <!-- route=final start=1.50 src=fallback reason=oracle -->
  EVIDENCE G:written: - [19:36:36] oracle unknown token <!-- route=final start=2.50 reason=oracle -->
  GREEN G:J3-every-token-writes-its-src-marker -- tokens_without_their_exact_marker=[] rows=[('worker-stamped', True), ('worker-stamped-producer', True), ('panel-deadline', True), ('fallback', True)]
  GREEN G:J4-unknown-token-is-still-refused -- unknown_written=True
  GREEN G:J5-provisional-draft-is-still-refused -- append(provisional-draft) -> null
GREEN ARM SUMMARY: 20/20 checks green; red=[]
VERDICT: PASS
```

**The two colours, side by side, in one run:**
* GREEN (checkpoint present, `:3248-3265`): `armed=True`, `missing=[]`, boot line
  `REDUX_SWITCH armed=true by=--redux-when-hidden …`, mode machine `('stream','batch','stream')`.
* RED (real disk today): `armed=False`, `missing=['config.json','model.safetensors','ternary.json']`,
  boot line `REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing … model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=config.json,model.safetensors,ternary.json …`.
* The J side: `allow-list` == `declared-sources` == the four tokens, and the
  `worker-stamped-producer` line carries its marker
  (`<!-- route=final start=1.50 src=worker-stamped-producer reason=oracle -->`) — the SAME `src=` shape
  as the other three.

### 5.2 `py -3 _main/redux-arm-weights-oracle.py --neg-arm` → `VERDICT: PASS`, rc=0

Raw verdict block (full log, 171 lines, at `I:\cc-tmp\redux-arm-neg.txt`):

```text
GREEN ARM SUMMARY: 20/20 checks green; red=[]
== NEG ARM: mutants of the real bytes (in memory, written to %TEMP%) ==
-- MUTANT M1-gate-reverted-to-the-runner-file
  MUTANT VERDICT M1-gate-reverted-to-the-runner-file: expect_red=['M1:W10-refusal-names-reason-and-path', 'M1:W12-partial-checkpoint-names-what-is-missing', 'M1:W9-real-disk-refuses'] observed_red=['M1:W10-refusal-names-reason-and-path', 'M1:W12-partial-checkpoint-names-what-is-missing', 'M1:W9-real-disk-refuses'] missing=[] extra=[] -> OK
-- MUTANT M2-refusal-loses-the-missing-path
  MUTANT VERDICT M2-refusal-loses-the-missing-path: expect_red=['M2:W10-refusal-names-reason-and-path', 'M2:W12-partial-checkpoint-names-what-is-missing'] observed_red=['M2:W10-refusal-names-reason-and-path', 'M2:W12-partial-checkpoint-names-what-is-missing'] missing=[] extra=[] -> OK
-- MUTANT M3-store-allow-list-reverted
  MUTANT VERDICT M3-store-allow-list-reverted: expect_red=['M3:J1-allow-list-covers-every-declared-token', 'M3:J2-allow-list-has-no-extras', 'M3:J3-every-token-writes-its-src-marker'] observed_red=['M3:J1-allow-list-covers-every-declared-token', 'M3:J2-allow-list-has-no-extras', 'M3:J3-every-token-writes-its-src-marker'] missing=[] extra=[] -> OK
-- MUTANT M4-control-comment-only-must-move-nothing
  MUTANT VERDICT M4-control-comment-only-must-move-nothing: expect_red=[] observed_red=[] missing=[] extra=[] -> OK
VERDICT: PASS
```

What each mutant did, from the observed RED lines (verbatim):

```text
  RED   M1:W9-real-disk-refuses -- armed=True model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=['config.json', 'model.safetensors', 'ternary.json']
  RED   M1:W10-refusal-names-reason-and-path -- REDUX_SWITCH armed=true by=--redux-when-hidden hidden_after_s=20.0 batch_interval_s=15.0 max_audio_s=120.0 min_free_mb=4600.0 runner=H:\sotto\worker\redux_batch.py visibility=<oracle-fake-visibility>
  RED   M1:W12-partial-checkpoint-names-what-is-missing -- missing=['model.safetensors', 'ternary.json'] line=REDUX_SWITCH armed=true by=--redux-when-hidden …
  RED   M2:W10-refusal-names-reason-and-path -- REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=H:\sotto\worker\redux_batch.py missing=config.json,model.safetensors,ternary.json — …
  RED   M2:W12-partial-checkpoint-names-what-is-missing -- missing=['model.safetensors', 'ternary.json'] line=REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=…\partial\redux_batch.py missing=model.safetensors,ternary.json — …
  RED   M3:J1-allow-list-covers-every-declared-token -- missing=['worker-stamped-producer']
  RED   M3:J2-allow-list-has-no-extras -- allow-list=['worker-stamped', 'panel-deadline', 'fallback'] declared=['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback']
  RED   M3:J3-every-token-writes-its-src-marker -- tokens_without_their_exact_marker=['worker-stamped-producer'] rows=[('worker-stamped', True), ('worker-stamped-producer', True), ('panel-deadline', True), ('fallback', True)]
```

* **M1** (`self.armed = bool(self.enabled and self.runner_available)` restored) → the switch arms on
  the file alone again, exactly the defect: W9/W10/W12 go RED.
* **M2** (`model_dir={self.model_dir} ` dropped from the refusal f-string) → the refusal no longer
  names the missing path: W10/W12 go RED. **The oracle notices a refusal that is quiet about WHERE.**
* **M3** (`ROUTE_SOURCES` reverted to three tokens) → J1/J2/J3 go RED: the token is missing, and the
  line is written with no marker (J3's `rows` show the line WAS written — the check catches the
  missing marker, not a missing line).
* **M4** (comment-only mutant in BOTH files) → **no RED anywhere**: the instrument does not redden on
  any diff.

---

## 6. NO-REGRESSION BATTERY (all in process)

```text
=== py_compile ===
PY_COMPILE_RC=0
=== node --check history-store.js ===
NODE_CHECK_RC=0
=== in-process import ===
IMPORT_OK True
REDUX_CHECKPOINT_RELPATH 'models\\parakeet-redux-ternary'
REDUX_CHECKPOINT_FILES ('config.json', 'model.safetensors', 'ternary.json')
REDUX_WHEN_HIDDEN_DEFAULT False
REDUX_PRODUCER 'redux'
CHECKPOINT_DIR H:\sotto\worker\models\parakeet-redux-ternary
MISSING ['config.json', 'model.safetensors', 'ternary.json']
ARMED False MODEL_DIR H:\sotto\worker\models\parakeet-redux-ternary MODEL_MISSING ['config.json', 'model.safetensors', 'ternary.json']
LOG REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=H:/sotto/worker/redux_batch.py model_dir=H:\sotto\worker\models\parakeet-redux-ternary missing=config.json,model.safetensors,ternary.json — the batch engine cannot LOAD this checkpoint …
TICK stream
MAYBE_KICK False
IMPORT_RC=0
```

(`python -m py_compile` and `node --check` are parses; the import is `sys.path` = `H:/sotto/worker`,
`sys.dont_write_bytecode = True`. The em dash renders as `?` on a cp1252 console — the file bytes are
UTF-8 and the oracle, which reconfigures its streams, prints it correctly.)

### 6.1 `_main/per-app-source-plumbing-oracle.py` → **`VERDICT: PASS`, rc=0** (30/30)

```text
worker: H:\sotto\worker\sotto_worker.py
worker: 295867 B sha256=2C0AF4FB8B22D3D15BE9AEAD051CDDC45AC062C0CE73EB260D6F893F3A106CC4
  PASS CHK-1 imports without NameError  loaded sotto_worker.py
  … (CHK-2 … CHK-9, 30 PASS lines) …
VERDICT: PASS
```

Full text: `I:\cc-tmp\redux-arm-plumbing.txt`. **GREEN — the worker still imports and the per-app
plumbing is untouched.**

### 6.2 `_main/canonical-producer-oracle.py` → **`43/45 checks green`, `VERDICT: FAIL`, rc=1**

**THIS ORACLE WAS NOT EDITED** (the brief forbids adjusting it to fit) and the failure is reported,
not smoothed over. Both RED checks are the two defects **written down as expected state**; each one
now measures the FIXED bytes:

```text
FAIL [B] the switch ARMS on the RUNNER FILE even when no checkpoint exists  -- runner_available=True armed=False -- gate 2 checks the .py, not the weights
FAIL [C] FINDING (latent): the store's src= allow-list omits 'worker-stamped-producer'  -- history-store.js ROUTE_SOURCES does not list the value caption-formulation.js:501 returns for a producer-stamped line with NO final flag, so such a line would be written with NO src= marker; LATENT today because panel.js:1330 stops a non-final route before the store is reached

SUMMARY: 43/45 checks green; failed=['the switch ARMS on the RUNNER FILE even when no checkpoint exists', "FINDING (latent): the store's src= allow-list omits 'worker-stamped-producer'"]
VERDICT: FAIL
```

The source of each, read on the live bytes:

```python
# _main/canonical-producer-oracle.py:463-464  -- asserts the DEFECT
check("B", "the switch ARMS on the RUNNER FILE even when no checkpoint exists",
      armed_switch.armed is True,
      ...
      + " -- gate 2 checks the .py, not the weights")

# _main/canonical-producer-oracle.py:551-552  -- asserts the ABSENCE
check("C", "FINDING (latent): the store's src= allow-list omits 'worker-stamped-producer'",
      "'worker-stamped-producer'" not in store_text,
      ...)
```

* `:463` asserts `armed is True` for the real runner with the checkpoint absent. The brief's fix A is
  precisely "do not arm in that case", so this check **cannot** stay green under any implementation of
  fix A. Its own message ("gate 2 checks the .py, not the weights") is now a false statement about the
  bytes.
* `:551` asserts the token is ABSENT. Fix B adds it, so this check **cannot** stay green under any
  implementation of fix B.
* Everything else in that oracle is green, including all anchor re-measurements on the live bytes
  (`REDUX_PRODUCER` is re-found at `:3069`, the stamp at `:3567`) and the whole end-to-end ARM B/ARM C
  chain, whose own `ok [C] END-TO-END: the REAL gate ACCEPTS the line the REAL worker stamped` still
  holds.

**This is a contradiction inside the brief, not a regression:** the brief requires both fixes AND
requires this oracle to stay green, while that oracle pins both defects as expected state. The
resolution belongs to the Lead: either the two checks are re-baselined to the post-fix expectations
(one line each) or the oracle is retired for those two arms. **This lane did not touch it.**

The same oracle's printed ANSWER prose is stale in the same two places (it is prose, not a check):
*"the switch's own gate sotto_worker.py:3259 checks the RUNNER FILE, not the weights"* — it now
checks both, and `:3259` is still `self.runner_available = os.path.exists(self.runner)`, kept
verbatim.

---

## 7. NEW PINS

| pin | value |
|---|---|
| `worker/sotto_worker.py` | 295867 B, 5693 CRLF / 0 bare LF, `2C0AF4FB8B22D3D15BE9AEAD051CDDC45AC062C0CE73EB260D6F893F3A106CC4`, 2026-10-11T22:24:41Z |
| `app/panel/history-store.js` | 9766 B, 0 CRLF / 256 bare LF, `0A81FD98378911FC416DD9335EE5557008B0C628B36FC010D333CC41D47E76DC`, 2026-10-11T22:25:13Z |
| `_main/redux-arm-weights-oracle.py` | 27218 B, 0 CRLF / 601 bare LF, `DA0F5FFCDCD74E7E81E4620C0D0FBA399A3CE2114F211CE1C4DCD02609FD694D`, 2026-10-11T22:36:30Z |
| gate, after fix | `self.armed = bool(self.enabled and self.runner_available and self.model_available)` — `sotto_worker.py:3264-3265` |
| refusal line, checkpoint case | `sotto_worker.py:3310-3316` (`reason=checkpoint-missing`) |
| allow-list | `history-store.js:60` |
| `_main/receipt-20261011-redux-arm-weights.md` (this file) | 32688 B, 0 CRLF / 490 bare LF, `4FF44D388389D00156364049732B23690CF01F9D880C1D883E6C9EE6E2870BD8`, 2026-10-11T22:39:31Z |

**Self-pin note, stated plainly:** the row above for THIS file is the revision measured immediately
before this note was appended. A file cannot contain the hash of itself plus this note, so the final
post-note measurement (bytes / sha256 / mtime) is reported to the Lead in this lane's hand-off message
rather than written here — writing it here would only move the target again. Every OTHER pin in this
receipt is the post-edit measurement of a file that is not this one.

Pre-fix pins for the record: `worker/sotto_worker.py` was 291873 B / `EFDFB098…`;
`app/panel/history-store.js` was 9150 B / `F13A843C…`.

---

## 8. NOT MEASURED (and why)

1. **Anything that needs the app running.** No live WebView2/panel run, no worker launch, no audio
   capture — the owner's stop order. So: what the panel PAINTS, whether the refusal line reaches
   `_main\webview-run.log` on a real start, and whether a real `--redux-when-hidden` run behaves as
   the in-process switch does are all **UNMEASURED**.
2. **The runner's real weight load was never executed.** The checkpoint is absent, and running the
   runner would be a launch. W2/W3 compare the worker's constants against `redux_batch.py`'s OWN
   source (its `DEFAULT_MODEL_DIR` and the `(model_dir / "NAME")` predicates); they do not load
   weights.
3. **`flush_pending` / `_run_runner` were never executed** — deliberately. A batch pass spawns
   `sys.executable <runner>`; that is forbidden here. The claim is limited to `armed`, `mode`,
   `maybe_kick` (which returns `False` before `flush_pending` unless `mode == "batch"`) and the static
   guard `if not self.armed: return False` (`sotto_worker.py:3438-3439`). **The switch's refusal to
   CUT streaming was therefore never observed on a live asr thread** — it is asserted from the gate
   value plus that guard.
4. **Whether a real `producer`-stamped line reaches the canonical gate.** Unchanged from the earlier
   receipt: `history-store.js` is the LEGACY arm's writer; `panel.html` does not load it. The live
   WebView2 app writes through the PYTHON twin.
5. **`app/webview/sotto_webview.py:169` `HISTORY_ROUTE_SOURCES = ('worker-stamped', 'panel-deadline',
   'fallback')` still omits `'worker-stamped-producer'`** — the SAME defect in the writer the shipped
   app actually uses, and **OUT OF THIS LANE'S EDIT SCOPE**. Reported as an OPEN finding; not fixed,
   not measured end-to-end. `app/panel/_strip-logmutant-repro_sotto_webview.py:169` carries the same
   tuple.
6. **No RSS/CPU/timing of anything** was measured; `min_free_mb` (4600.0) appears in the log lines
   only because it is the switch's default, not because memory was measured.
7. **The two RED checks in `canonical-producer-oracle.py` were not re-baselined** and no other oracle
   was run beyond the two the brief named.

---

## 9. VERDICT

* Defect A: **FIXED**, both colours proved in process. Green colour: the switch still arms and still
  switches `stream → batch → stream` when the checkpoint the runner will load IS on disk. Red colour
  (real disk today): it refuses to arm, ONCE, with `reason=checkpoint-missing`, the directory
  `H:\sotto\worker\models\parakeet-redux-ternary` and all three missing manifests named, and it
  stays inert. The flag default and the producer literal are unchanged.
* Defect B: **FIXED**. `ROUTE_SOURCES` == the four tokens `routeSourceFor` can return; the
  `worker-stamped-producer` line now carries the same `src=` marker as the others.
* The instrument **can say NO**: 4 mutants, each RED set exactly as predicted (M1 → W9/W10/W12,
  M2 → W10/W12, M3 → J1/J2/J3) and a comment-only control that moves nothing. `VERDICT: PASS`, rc=0,
  with rc=2 reserved for an unbuildable arm.
* No regression in `per-app-source-plumbing-oracle.py` (PASS, rc=0).
  `canonical-producer-oracle.py` is 43/45 with the 2 RED checks that pin the two defects as expected
  state — **reported to the Lead, not adjusted, not a regression.**
