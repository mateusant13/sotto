# Receipt — 2026-11-23 — the 18 red steps of the Wave D2 battery

Battery run of 2026-11-23 09:37 (`bg_19`): `battery rc=1 agrees=True verdict=RED - 18 step(s) failed`,
`steps=548 gate=281 control=8 skipped=25 expect-red=234 missing=0 cached=117 failed=18`, wall 4265.64 s.

The 18 rows, and what each one actually was. Nine were **instruments** that had rotted (a stale
anchor, a judge pointing the wrong way, an rc that never propagated, a deadline that was not the
measurement); one was a **product** defect (autostart identity); three were **contention** (a
browser fixture timing out beside four heavy jobs); one was a **cost** that had to be paid down
before any ceiling could judge it.

Everything below was executed on this box with `H:\Python311\python.exe`, in `H:\sotto`.

## 1. Instruments that had rotted

| step | what the arm was | what it is now |
|---|---|---|
| `exception-hygiene` | baseline had `worker/sotto_worker.py` = 8, tree measures 5 — growth ratchet read as debt | baseline 8→5; `EXCEPTION-HYGIENE VERDICT PASS -- a divida de except Exception: pass nao cresce (medida: 33)` |
| `task-resolver-gate` | pin still named an older skill version/sha | pin 1.4.2 / `20031262c1039feba0dff8c1c8a375912d7d9b6ea8695e167db007dde2afcf9a`; `BATTERY-VERDICT task-resolver-gate PASS checks=6 fail=0` |
| `red-as-expected-task-resolver-gate` | rc=2 (setup) instead of the control's 1 | `NEG-ARM PASS mutations=6 named-arm-fail=0`, rc=1 |
| `claims-date` | six numeric claims in `AGENTS.md` carried no date | `BATTERY-VERDICT claims-date PASS checks=4 fail=0` |
| `red-as-expected-claims-date` | rc=2 | `NEG-ARM PASS mutations=6 named-arm-fail=0`, rc=1 |
| `red-as-expected-live-ack` | two anchors had moved (`cold-worker-arming-removed`, `route-refused-tag-unpublished`) and the arm still read the old text | anchors re-measured against the shipping shell; `NEG-ARM: PASS (14/14)`, 84.9 s |
| `red-as-expected-loading-placeholder` | mutant changed two variables at once, so the arm's meaning was gone | one-variable mutant (`GUARD` → `GUARD_MUTANT`); `NEG-ARM guard-removed PASS pushes=2, antes do mutante=1`; `VERDICT: PASS (4/4 arms)` |
| `red-as-expected-yt-clock-static` | M2 planted its mutation against text the file no longer contains | anchor rebuilt from `chr(92)`/`chr(34)`; `NEG-ARM: PASS -- 3/3 mutantes apanhados`, `YT-CLOCK-STATIC VERDICT: PASS -- 6/6` |
| `batch-executor-ceiling` | population sampled too few completions, and the ceiling arm was two-sided against a one-sided budget | population `2*MAX+1`, waits for 3 finished children (60 s); one-sided arm; `VERDICT: PASS (19/19)`, 14.51 s |
| `panel-commit-stable` | the control's population was a literal, so a legal page could not pass it | `ceiling_floor(pop) = max(20, int(0.03 * lines))` used by both the BEFORE check and the control: POS `VERDICT: PASS` (7.90 s), NEG `VERDICT: RED BY DESIGN` rc=1 |
| `red-as-expected-panel-commit-stable` | rc=0 — the ceiling mode still counted as the clock | rc=1 with `NEG-ARM: PASS -- stable commit removed; the ceiling mode came back at 32 lines (floor=20, 43.2 % of them, queue p50=1500 ms)` |
| `panel-search-keyboard` | arm needed a keyboard it does not own on a box with the owner's window | synthetic seed + a `SKIPPED` arm with its reason; row declared `:skipped` |
| `red-as-expected-panel-search-keyboard` | rc=0 against the same missing surface | reads the declared skip and its reason; rc=1 |

## 2. The product defect: `autostart-status` rc=4

`autostart_status()` (`app/webview/sotto_webview.py:11209`) compared the registry value to
`autostart_command()` **as strings**. `C:\Program Files\Python311` is a **junction to `H:\Python311`**
— `os.path.realpath` of both is `H:\Python311\pythonw.exe`, sha256 of both is `e65ecc6b135f8c22` — so a
correct registry entry was reported as "on, but pointing somewhere else".

Identity, not spelling: `_autostart_tokens()` splits the command into quoted tokens and
`autostart_same_checkout(value)` compares token 0 with `os.path.samefile` (normcase fallback) and the
script plus args by normcase. Measured: `matches this checkout: True  via=samefile (expected:
"H:\Python311\pythonw.exe" ...)`, `AUTOSTART_CHECK state=on-this-checkout`,
`AUTOSTART_CHECK_OK on, and it points at THIS checkout`. **The owner's registry was not touched** —
a gate is not a licence to rewrite the thing it inspects.

## 3. The cost that had to be paid before a ceiling could judge it: `state-page`

`red-as-expected-state-page` measured 72.6 s in the battery (baseline 34.7 s) and 136 s in one
contended sample. Two honest optimizations, both measured:

1. **The sandbox root was chosen by existence, not by cost.** `TMPDIR` was read as a rule, and
   `I:\cc-tmp` sits on a volume with 18 GiB free where a 64 KiB write has been measured at
   0–1595 ms. `_tmp_base()` now probes candidates with a 64 KiB write (best of 2) and prints its
   choice: `STATE-PAGE TMPROOT chosen=H:\cc-tmp write_ms=0.11 candidates=H:\cc-tmp=0.11, I:\cc-tmp=0.20`.
   `H:\cc-tmp` is a shared root outside the repo: this receipt's lane created only that directory and
   removes only exact paths it made.
2. **The content cache was thrown away 5 480 times.** `load_engine()` re-`exec_module`'d
   `_stepcache` for every `build_rows`/`verdict_for` call, so each of the 548 rows × 10 renders got a
   fresh empty `_HASH_CACHE` and re-hashed 830 MB of dependencies — the profile showed
   `BufferedReader.read` 27.3 s in 36 888 calls and `_hashlib.HASH.update` 7.7 s in 127 528 calls.
   One module per process, keyed by absolute `(root, dep_root)`, gives one cache:
   `STATE-PAGE WALL 81.1 s → 32.5 s` (baseline 34.7 s), `NEG-ARM PASS mutations=8 named-arm-fail=0`.
   Positive unchanged: `--write` rc=0, `--check` rc=0, `BATTERY-VERDICT state-page PASS checks=7 fail=0`.

No rebaseline was needed: the step is now under the baseline it already had.

## 4. Contention, not defects: the devlab browser drills

`red-as-expected-panel-themes` failed at 43.3 s with a navigation `TimeoutError` while four heavy
jobs ran beside it. Solo, the same command measures **258.78 s** and prints
`NEG-ARM: PASS -- 13/13 mutants caught` — the arm works; the run was starved. The step now declares
`SOTTO_STEP_OVERRIDE_S=420` (the house floor is 240 s, and the population is 13 mutants × 11 arms ×
59 themes = what it exists to prove) and clears it after the `:expectred`; the `REM` that said "seven
mutants" now names all thirteen. Pin re-measured: `_main\_audit-verify-all.cmd` = **415967 B**,
**4754 CRLF** / 0 bare LF, sha256 `A8D2E5AD721586A3020767FE827E311F8AB5F04DAC62C456AED5FD78647FC16B`
(`AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`).

`devlab-captions` and `devlab-chaos` failed with `fixture never became ready`. Solo, both pass:

- `python _main\devlab\lab.py captions` → `S2 CAPTIONS: PASS (23/23)`, rc=0 — including the two arms
  the battery log showed red (`chrome-window: control window dropped from rows`,
  `chrome-window: an empty box is not called painted`), which now read
  `why='no-painted-caption'`;
- `python _main\devlab\lab.py captions-neg` → `S2 NEG-ARM: PASS -- 3/3 mutants caught`, rc=1;
- `python _main\devlab\lab.py chaos` → `S5 CHAOS: PASS (24/24)`, rc=0;
- `python _main\devlab\lab.py chaos-neg` → `S5 NEG-ARM: PASS -- 4/4 mutants caught`, rc=1. Each
  mutant is caught by the row that names it, and the totals are the arithmetic of that (`23/24` three
  times, `22/24` for the mutant that removes the notice-window row as well as its own). Measured
  **after** the readiness budget below — the same command before it ended in
  `fixture never became ready`.

The readiness gate also got the fix its failure asked for. It waited a bare **10 s** for the
fixture's own API; measured cold, the port answers at 0.54 s and `typeof window.__seek ===
'function'` is true at **4.23 s** — 2.4× of headroom against the 2.7× contention measured on this
same box, which is exactly how a merely-late page was reported as a broken one
(`chaos-neg`, mutant 2 of 3, after mutant 1 had already been caught). One declared budget,
`FIXTURE_READY_S = 30.0`, is now used by both drills, and the timeout prints the page's own account
(`href`, `readyState`, `typeof __seek`/`__setCues`, title, page errors) instead of a sentence that
reads the same for a slow disk and a dead page.


## 4-bis. The second battery run (11:18) left four, and three of them were the same volume

`battery rc=1 agrees=True verdict=RED - 4 step(s) failed`, wall 2 845.67 s
(`failed: red-as-expected-panel-themes=1 red-as-expected-devlab-chaos=1
red-as-expected-nemotron-weights=124 battery-budget=1`).

One root cause explains three of the four, and it is the house's own law read the wrong way round:
**the temp root was chosen by existence.** Measured on this box, `stat()` costs

| volume | `stat()` | read 4 KiB |
|---|---|---|
| `H:\cc-tmp` | **0.016 ms** | 0.037 ms |
| `G:\watcher-state\cache\tmp` (the cage's cache) | 0.047 ms | 0.069 ms |
| `I:\cc-tmp` | **8.022 ms** | 0.068 ms |

and a Chromium profile makes thousands of `stat` calls while it starts, so the volume is worth
500× per call. `os.tmpdir()` answers `I:\cc-tmp` from a shell and `G:\watcher-state\cache\tmp`
under the cage, and both drills just used it.

- **`_main/fixture-temp.mjs`** (new) probes the candidates with the operations a profile performs,
  prints them and sets `TMPDIR`/`TMP`/`TEMP` to the cheapest. Measured after wiring:
  `HISTORY-CLIP TMPROOT chosen=H:\cc-tmp per-op-ms=0.025 candidates=G:\watcher-state\cache\tmp=0.063, G:\Temp=0.071, H:\cc-tmp=0.025`;
  `panel-history-clip --neg-arm` **17.9 s → 9.1 s** (baseline 9.0 s), `NEG-ARM: PASS -- identity caught
  (1 face(s), the positive measures 28); 6/6 retention mutant(s) caught`.
- **`lab.py`** gains `_fixture_root()` with the same probe
  (`FIXTURE TMPROOT chosen=H:\cc-tmp per-op-ms=0.031 candidates=G:\watcher-state\cache\tmp=0.100, H:\cc-tmp=0.031`),
  and `captions` measures **2.64 s** with `S2 CAPTIONS: PASS (23/23)` where the same drill took
  ~11-13 s on the slow root.
- **A tab is not always the page we launched.** `chaos-neg`'s `about:blank` failure is now named and
  fixed: after `cdp_connect`, if the attached target does not carry the fixture's nonce, the drill
  issues `Page.navigate` to it. Measured: `S5 NEG-ARM: PASS -- 4/4 mutants caught`, 58.7 s.
- **`fetch-nemotron.py --neg-arm` builds 793 MB of sparse stand-ins** (the verifier only size-checks
  them, so that allocation is the arm's whole cost). It now picks the root by measuring a 64 MiB
  `truncate` (`NEG-ARM stand-ins root=H:\cc-tmp probe_ms=93.4`), prints one line per stand-in with
  `flush=True` so a cut names the phase instead of leaving an empty log, and the arm measures
  **3.6 s → 1.69 s** solo. The battery cut it at 243.7 s — a 3-second step starved, not slowed; the
  override was **not** raised to hide that, the evidence was made visible instead.
- **`panel-themes --neg-arm`: 258.8 s → 111.8 s, 13/13 still caught** with the measured root
  (`THEMES TMPROOT chosen=H:\cc-tmp per-op-ms=0.032`). The 420 s `SOTTO_STEP_OVERRIDE_S` added one
  message ago was therefore **removed**: the arm is inside the 240 s house floor once the volume is
  right, and a ceiling that exists to hide a defect is the defect. Pin re-measured to 415941 B /
  4753 CRLF / `675B37F3…`. The positive arm measures 50.1 s, `VERDICT: PASS -- themes=59 arms=19
  failed_arms=0 fatal_page_errors=0`.
- **The probe is best-of-two**, because a single sample chose the slower volume once
  (0.032 ms vs 0.103 ms for the same root on consecutive runs): measured after the change,
  `PROBE TMPROOT chosen=H:\cc-tmp per-op-ms=0.022 candidates=G:\watcher-state\cache\tmp=0.063, G:\Temp=0.059, H:\cc-tmp=0.022`.
- **`page.goto` defaults were library defaults.** Both browser drills now carry a declared
  `NAV_TIMEOUT_MS = 120000` (the arm costs ~20 s per mutant solo, so 120 s is 6× the observed cost and
  still bounded), and `panel-themes` prints `THEMES mutant i/13 <name>` before each measurement and
  `THEMES mutant <name> CRASHED before it could be judged: ...` on an exception, so a timeout names
  the mutant instead of dying inside Playwright.

## 4-ter. Run 4: three reds, two of them INSTRUMENT rules that outlived their file

`battery rc=1 agrees=True verdict=RED - 3 step(s) failed` (`clr-warm=1 battery-plan=1
red-as-expected-battery-plan=0`), 1 084.72 s, `steps=548 ... cached=306`.

- **`clr-warm` A3 measured `warm_ms=8740.7 budget_ms=4000`** — and the same oracle measured
  **727.9 / 960.0 / 1189.6 ms** three times in a row on a quiet box, `VERDICT: PASS (5/5)`. That is
  the house rule over again: *a process that was not scheduled measures the queue*. The arm now
  prints three numbers instead of one — `warm_ms`, `cpu_ms` (the process's own CPU during the call)
  and `sched_ms` (mean overshoot of five 20 ms sleeps taken immediately after, i.e. how late this
  process is being served) — and judges on them:
  `cpu_ms` over budget is **always** a failure (our function grew); `warm_ms` over budget on a
  *responsive* machine is a failure (our path is waiting on disk); `warm_ms` over budget on a
  *late* machine is `NOT-JUDGED under contention` with the three numbers printed. New arm
  **A6** judges the judge on a four-case matrix, and new mutant **M5** (a `judge_warm` that accepts
  everything) has to make it red. Measured: `PASS A3 ... warm_ms=376.7 cpu_ms=375.0 sched_ms=0.3`,
  `VERDICT: PASS (6/6)`, `NEG-ARM: PASS -- 5/5`.
- **`battery-plan` self-check `defer>=1` was an invariant of a file that no longer exists.** The
  DEFER rule answers a step whose dependency is the live record at the moment it runs; after the
  subject-dep change no step declares that dependency, so `defer=0` was the *correct* plan and the
  check demanded the impossible. The check is now **`defer == deps-do-estado`** (the plan defers
  exactly the steps that declare the state file and invents none) and a **fixture** declares one
  step with the dependency and one without — because with zero declared, the mutant that disables
  DEFER became invisible (`NOT-CAUGHT defer-apagado: o selftest da copia PASSOU`). Measured:
  `fixture DEFER   : defer=1 deps-do-estado=1 com-dep=DEFER sem-dep=MISS`;
  `plano real ... defer=0 deps-do-estado=0`; `VERDICT: PASS`; `NEG-ARM: PASS -- 3 mutantes, 3 apanhados`.
- **`red-as-expected-battery-plan=0`** was a consequence of the same: the negative arm printed
  `NEG-ARM: FAIL -- 2/3` because its own mutant was no longer observable. A control whose mutation
  cannot be seen is the same defect as a green nobody measured.

## 5. Standing green gates re-run after the edits

- `python _main\code-health-oracle.py` → `piorem: 0 metrica(s)`, `CODE-HEALTH VERDICT PASS`. The
  identity fix adds two functions, so `sotto_webview.py` grew 1 531 B / 64 lines / 2 defs: absorbed
  with `--update --allow-dirty`, which printed the entry it fixed
  (`AVISO  --allow-dirty: fixado a partir do working tree: app/webview/sotto_webview.py`) instead of
  pinning a state nobody can reproduce.
- `python _main\sotto-state-page.py --write` rc=0 then `--check` rc=0.
- `python _main\agents-md-pins-oracle.py` → `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.

## 6. What is still open

- `speaker-watch-oracle` rc=2 — `REFUSED before audio/model load: pass --allow-heavy only inside the
  performance-gate + Watcher lease`. The gate is **AMBER** (`commit-pct=81.8`, `heavy_allowed=False`,
  `amber_light_ttl_max=300.0s`), so the heavy lease is refused by design; the step is blocked, not
  green.
- The full battery re-run below is what turns these 18 into a number.

## 6. What the Codex lane left unfinished (owner order, 2026-11-23)

The Codex sessions for this workspace stop on **2026-11-21 12:49Z** mid-repair. Its own TODO
(`.agent-work/TODO-parakeet-nemotron-speaker-accuracy-20261117.md`) and the last turns name three
code-level items; all three are now closed here, each with a model-free control.

1. **Cold-path `UnboundLocalError` in `_main/kestrel-ultra-stream-runner.py`.** `run()` aggregated
   the cold branch with `model_ready_s`, `gpu` and `process_info`, assigned only inside the resume
   branch (`git show HEAD:…` shows the assignment at the resume branch and the use 23 lines below,
   outside it) — a run with nothing cached died before writing its report. Fixed by
   `_engine_report_inputs(result)`, which refuses a result missing rows, a model-ready receipt, a
   `cuda:0` device or a process receipt. `--selftest` now asserts both the four values and five
   incomplete shapes; `KESTREL_ULTRA_STREAM_SELFTEST PASS`.
2. **Model identity reused without proof of unchanged bytes.** The fingerprint already carries the
   NTFS `usn` (advances on every write) plus size/mtime/ctime/file_id; the uncovered case was a
   volume where `_file_usn()` returns `None`. Reuse now requires `usn` on **every** file, otherwise
   the cached receipt is ignored and the identity is re-hashed (`identity_basis=rehash`). Selftest:
   with `usn` the hash function is not called on the second pass; without it both files are re-hashed.
3. **A3 review gap in `_main/bench/separate.py`.** `--score` bounded the *requested span* but
   `read_wav()` loaded the whole file before the RSS monitor existed, so the allocation never
   appeared in the measurement. `read_wav_span()` now seeks and reads the window and prints
   `SPAN READ start_s=.. span_s=.. frames=.. alloc_mb=.. file_mb=..`; `--auto-spans` (which needs the
   whole series) refuses above `MAX_FULL_READ_MB = 512` by name — measured on a 629 MB file:
   `--auto-spans reads the whole file (629 MB) and the float32 copy would exceed the 512 MB read
   ceiling; use --start/--span-s`. `--score-selftest` gained `span_read=PASS` (window equals the
   slice of the full read; allocation is the window's bytes; a start at/after the end or negative
   is refused).

Both selftests had **no battery step**: they now do (`kestrel-ultra-stream`, `certas-score-selftest`,
`always`, 2.6 s and 1.9 s, no model, no GPU). What stays blocked is unchanged and honest: the V26
production replay (CUDA device census sees CPU only) and A10 word boosting need a GPU experiment
under a GREEN heavy lease, and the natural multi-speaker reference transcripts do not exist locally.


## 7. The observer's own rows, the single entry point, and the tool that judged a directory

Three defects, all measured in run 7 (`_battery-run-20261123-142233.log`), all repaired with a
control that can fail.

### 7.1 A row cannot be judged by the run that writes it (`CARRIED`)

`no-invented-green` reported the observer's own three rows as unsupported green:

    no-invented-green FAIL  2 verde(s) sem sustentacao: state-page(PASS: log alterado),
                            red-as-expected-state-page(EXPECTED-RED: deps mudaram)

The mechanism: `state-page-write` renders `docs/state-generated.md` at T from the previous run's
`_cache/battery-steps.json`; the shell then **truncates** `state-page.log` / `state-page-neg.log`
before the check process starts, so the `log_sha256` recorded at T can never match at T+2 s, and
`docs/state-generated.md` (a dep of both rows) has an mtime newer than either record. The page was
therefore `NO-VERDICT` every run, which makes D2's `NO-VERDICT=0` unreachable by construction.

The fix is a verdict, not an exemption: `SELF_STEPS` render as `CARRIED` with the note "auto-julgamento
impossivel na mesma corrida … julgada na corrida seguinte". `verdict_for` is untouched, and every row
that is not one of the observer's own is judged with the same log/dep/token evidence. Measured:
`--write` → `passos=550 PASS=259 EXPECTED-RED=217 FAIL=1 STALE=4 NO-VERDICT=0 NOT RUN=66 CARRIED=3`;
`--check` → `CHECK verdict-vocabulary FAIL vocabulario fora da lista: state-page-write='CARRIED',
state-page='CARRIED', red-as-expected-state-page='CARRIED'` — i.e. the vocabulary check caught the new
word, and `"CARRIED"` entered `VERDICTS`. Re-measured: `BATTERY-VERDICT state-page PASS checks=7 fail=0`
with `no-invented-green PASS 0 verde(s) sem sustentacao (CARRIED=3: linhas do proprio observador,
julgadas na corrida seguinte)`.

### 7.2 A second battery run is a defect of the entry point (`BATTERY-BUSY`, rc=4)

Two overlapping runs make the first one's verdicts unreadable (measured, twice: run 5 `rc=0
agrees=False` and run 6 `red-as-expected-nemotron-preload=1` because `:hastext` read a log the peer
was truncating). The lock lives in `_main/battery-run.py` — the documented single entry point — as
`O_CREAT|O_EXCL` plus a holder line `pid create_time`:

    BATTERY-BUSY pid=… -- outra corrida e' dona de _main/_audit-verify; esta e' recusada
    (uma segunda corrida trunca os logs de passo e o sumario da primeira)      rc=4, launches=0

`BUSY_RC = 4` is a code no step returns by accident. A holder whose pid no longer exists is taken
over by name: `BATTERY-LOCK stale pid=999999 -- o dono do cadeado ja' nao existe; a toma-lo`.
Measured: `--selftest` rc=0 (`L1` acquire, `L2` second run REFUSED, `L3` dead-pid takeover,
`L4` release unlinks, plus `C1–C4` for the rc/verdict judge), repeatable, no leftover lock.

**The control names the branch it exercises.** The first patch was refused before touching the real
file, for two reasons, both measured on a copy: the block inserted *before* `ok = True` raised
`UnboundLocalError: cannot access local variable 'ok'`, and `L2` "passed" through the wrong branch
because on Windows `os.unlink` of a lock file whose holder has the handle open raises — so
`acquire_lock` returned `None` for the wrong reason. `L3` therefore closes the handle, which is the
only state where a dead-pid takeover is provable here, and the mutant (a dead pid reported as alive)
is caught by `L3`: `--neg-arm` rc=1, `BATTERY-RUN NEG-ARM: PASS -- a mutacao do cadeado foi apanhada`.

### 7.3 The step named three files and the truth was a directory

`tooling-intent` declares `_main\tooling-intent-oracle.py;…baseline.json;…bug-ledger.json`, but the
oracle's population is every `*oracle*.py`, `*-gate.py`, `*-guard.py`, `*_gate*.py`, `*_guard*.py` in
`_main` — **325 files**, measured. Run 7: `declaradas: 170 | baseline (sem declaracao): 144 |
vermelhas: 11`, `TOOLING-INTENT VERDICT FAIL` rc=2. Eleven enforcement files written after the
baseline snapshot declared no intent, and a cached HIT would have re-printed a verdict over a file
set it never read — the `panel-deps` class, paid again.

Both halves are fixed. The eleven files state the measured defect or the owner order they serve
(`# NO-BUG: …`, in the first 60 lines, at the start of the line, naming what it blocks and saying the
ledger carries no id for it — inventing a `BLOCKS:` id would be the false intention the oracle calls
red, and `_main/bug-ledger.json` has exactly four ids). Measured: `declaradas: 181 | vermelhas: 0 |
TOOLING-INTENT VERDICT PASS` rc=0, `--neg-arm` rc=1 with `NEG-ARM PASS 4 of 4`. The step takes
`""` deps, so `_stepcache` answers `MISS reason=no-deps` and the step always runs; measured cost of
one run **1,51 s**.

### 7.4 Two instrument lessons paid in this session

**`kill -0 <pid>` from MSYS bash does not see Windows pids.** Two of my own "the run is GONE"
readings were false: `kill -0 37592` answered non-zero for a live `python.exe` whose age was 3 280 s,
because bash resolves its *own* pid namespace. The reader that works is
`psutil.Process(pid)` — the same identity check the repo already uses for tree attribution.

**A background job of this harness is killed once it has run 300 s in total.** A battery launcher
started as a plain background job is therefore reaped mid-run and leaves the previous
`_battery-summary.txt` on disk, which then reads as a verdict for a run that never finished (this is
also why run 7's `failed:` line was the 14:19 one). Long waiters are started with no deadline
(`timeout: 0`) and poll `psutil`, not `kill`.

## 8. Run 7, run 8, run 9: what the ratchet refused, and the three instruments that were paying it

### 8.1 The verdicts

| run | started | wall | steps | failed |
|---|---|---|---|---|
| 7 | 14:46 | 5 020.5 s | 550 | `tooling-intent=2` (stale: the step ran at 14:46:45, the fix landed after) and `battery-budget=1` (named `input-path 29.8 -> 61.2 s`) |
| 8 | — | 2 339 s | 550 | `nemotron-preload=1` (a false `MISSING`) and `battery-budget=1` |
| 9 | 16:41 | 1 683.8 s | 550 | `battery-budget=1` only |

Run 9 is the first run whose only red is the ratchet itself, and the ratchet was right about
something that had to be *measured*, not argued: ten steps carried per-step times 2-5x their
2026-11-12 baseline, and every one of them was measured while my own probes ran beside the tail of
the run. The rebaseline **refused** them by name, which is the ratchet doing its job.

### 8.2 A rebaseline that measured nothing was erasing the ratchet (measured, fixed)

`battery-budget-oracle.py --baseline` without `--policy cap40` reads
`_cache/battery-steps.json`, `measure()` drops every row because they were all measured under
`cap40`, and the tool wrote `per_step={}`, `steps=0`, `total_s=0.0` **with rc 0** — the ceiling
gone, silence. It happened in this session and the backup
(`_main/_cache/triage/baseline-before.json`) is what undid it.

The judge path already refused a missing `--policy` ("CANNOT-MEASURE ... o baseline foi medido sob
'cap40'"), so the hole was exactly one branch: `--baseline` never asked. Now it does:
`rebaseline_population(measured, baseline_policy)` is a pure guard and `--baseline` returns 1 with

```
baseline RECUSADO -- 0 passo(s) medido(s); 526 linha(s) de outra politica foram descartadas.
Falta `--policy cap40` para casar a populacao que este cache mede; um baseline vazio apagaria a regua.
```

Two arms keep it alive: `A18` (0 measured rows must refuse) and `A19` (526 rows must write) —
a guard that refuses always is the same green that never fails, only inverted. Measured:
`ARM ok A18 ... recusa='baseline RECUSADO ...'`, `ARM ok A19 ... recusa=None`.

### 8.3 `red-as-expected-nemotron-weights`: 24 730 ms -> 296 ms

`_standin_root()` probes candidates by truncating 64 MiB; the negative arm then built **658 MB of
sparse stand-ins** (16 files) for a check that only ever calls `os.path.getsize` (`verify()` tests
sizes first, lines 74-86) — the stand-ins are load-bearing, the *bytes* never were. Now a file over
1 MiB is `os.link(src, dst)` with an `OSError` fallback to the truncate. Measured:
`9 961 / 24 730 ms -> 296 ms`, `probe_ms` 4 393 -> 79.3, `NEG-ARM: PASS`, rc=1 preserved, and the
hardlink is *more* faithful than a sparse file pretending to be a graph.

### 8.4 `nemotron-preload`: a false `MISSING` costs a whole run

The child-exit arm waited a single window and printed nothing when it lost the race. It now waits in
two windows (5.0 s then 10.0 s) and prints `NEG-CHILD alive after %.1fs (window %.1fs)
poll=%r stdin_closed=%s`; a lost thread prints `NEG-THREAD %s still alive after 5.0s`. The battery
line was then reproduced twice outside a run (`bat1 rc=0 ms=15 214`, `bat2 rc=0 ms=15 860`,
`VERDICT: PASS`) — the run-8 red was contention, not a defect, and the instrument now says so with
evidence instead of a bare `MISSING`.

### 8.5 `console-window-audit`: 34.1 / 50.0 / 67.1 s -> 0.98-1.28 s (content-keyed)

The same command, back to back, with no code change: **34 105 ms then 49 975 ms** (46 % spread) —
the box, not the census. The profiler then named the work:

| ncalls | cumulative | what |
|---|---|---|
| 7 501 847 | 68.6 s | `ast.walk` — `_scope_map` re-walked every function's whole subtree (O(n^2)) |
| 413 | 26.7 s | `ast.get_source_segment` — `_splitlines_no_ff` re-splits the file per call |
| 2 553 117 | 45.4 s | `ast.walk` again — `_resolve_name` re-walked a function body per name |
| 1 021 | 20.0 s | `compile` — every file parsed on every run |

Three fixes, each keeping the judged answer byte-identical (`counts` and all 26 `sites` compared
before/after: **same**, `unparsed []`, `VERDICT PASS -- 0 sitio(s)`):
`_scope_map` became one iterative pass; `_resolve_name` memoises `(id(fn), name)` per file; and the
rows are cached per file under its **sha256**, so a byte change re-parses that file and only it.

Measured: cold 67 123 ms (1 375 re-parsed), then **981 / 956 / 1 284 / 1 069 ms** with
`cache: 1375 reaproveitado(s), 0 re-parseado(s)`; a touched file shows `1 re-parseado`. `--neg-arm`
stays 5/5 (`C1(os.system)=True C2(bit sozinho RED)=True C2(baseline perdoa)=True C3(o par
passa)=True C4(detached do JS nao esconde)=True`, rc=1) and does not touch the cache. The cache
lives in the ignored `_cache/` (`git check-ignore` says so), never in the repo.

### 8.6 `red-as-expected-paint-live-show`: 59.0 s -> 2.22 s (the same stdlib trap)

The profiler found the *same* `_splitlines_no_ff`, this time in
`_main/content-gate-answer-probe.py`: **66 calls, 158.6 s cumulative**, 1.95 s each on the 1 MB shell
source, plus 56 `ast.parse`/`compile` calls (57.8 s) because three separate extractors each re-parsed
the same text. One identity-keyed single-slot cache now holds the line table and the tree; the
segment is computed from it with the same offsets. Measured: `59 000 ms -> 2 220 ms`,
`NEG-ARM cases=19 caught=19`, `NEG-ARM PASS`, rc=1 — every arm still demands its own mutant.

### 8.7 `input-path`: the wall was blocked, not throttled (no rebaseline)

Caged, the step measured **64 677 ms of wall for 22.8 s of CPU** and the wrapper printed
`not-scheduled 0.0s` — the child was scheduled, so the difference is waiting, not a CPU cap. Two
honest optimizations were applied (mutants moved out of `app\webview` into
`_main\_cache\input-path-mutants`, and `sys.modules` dropped per mutant) and **both were refuted as
the cause**: 64.7 / 63.8 / 55.6 s, and `gc.disable()` made it worse (95.3 s). A phase profiler then
measured the same arms at 1.00 / 1.09 / 1.87 / 2.32 / 3.45 / 2.54 / 3.34 / 4.65 / 5.81 / 3.53 /
3.36 s — the same work growing with the box's mood, and the whole oracle 37.6 / 55.6 / 63.8 / 95.3 s
on identical code inside 40 minutes. The step's own 29.8 s baseline was a warm-best-case sample.
No rebaseline was taken from a contended sample; run 10 measures it in the quiet.

### 8.8 The rule this session paid for twice

**A battery run and a probe do not share the box.** Ten "regressions" in run 8 were my own probes'
cost appearing in per-step times. The ratchet refused them (good), the rebaseline would have signed
them (bad), and the only honest instrument is the one that runs alone: run 9 and run 10 were started
with nothing else alive, `timeout: 0`, and `psutil` as the reader.

### 8.9 The page said FAIL=1 while the run said rc=0 -- and the cache was why

Run 10 came back `BATTERY-VERDICT: GREEN ... failed: -none-`, and the state page -- the Wave D2
artifact the owner reads -- still carried `tooling-intent | FAIL | 2`. Both were "right" about their
own source, and one of the sources was hours old.

The chain, measured: `_main/_stepcache.py:record()` **refused to write a row for a step whose deps
are empty** (`no-deps: refusing to record a step with no deps`). A step declared `"--deps ''"`
(the four whose population is a *directory*, not a set of files) therefore never refreshed its row,
so the page kept publishing run 7's `rc=2` while every later run executed the step and printed
`rc=0`. The cache refusing to *hit* is correct; refusing to *record a measurement* is not -- the row
is what the page publishes, and the two questions are different.

Fixed in three places, each with a control:

1. **`record()`** now writes the row for a no-deps step with `fingerprint: null` and returns
   `(True, "no-deps: measured, never a cache hit")`. `check()` refuses a no-deps step *before* it
   ever reads a row, so a measurement cannot become a hit.
2. **The CLI accepted no such call.** `--deps` was `nargs="+"`, and `cmd.exe` expands `""` to
   nothing, so every `--deps ""` invocation died in argparse (`unrecognized arguments`,
   **rc=2**) with the message going to `>nul`. `nargs="*"` is the shape that matches the
   declaration. (Measured along the way: MSYS bash *also* drops empty arguments to a native Windows
   exe, so `--deps ""` cannot be tested from this shell at all -- the argv has to be built in
   Python.)
3. **Arm (q)** of `_stepcache-oracle.py` demands BOTH halves in one arm -- the row is written
   (`RECORDED`, `row rc=0`, `log_sha256` present) AND `check` still says `no-deps` with
   `hit=False` -- and a seventh mutant restores the old early `return`, which the arm catches
   alone. Measured: `VERDICT: PASS arms 17/17 mutants 7/7`, `NEG-ARM` green on all seven.

Five steps were then re-measured through the real instruments and recorded through the same CLI the
battery uses (`--policy cap40`, marker file, `:step`'s own command):
`tooling-intent` 0.4 s rc=0, `spec-citations` 1.2 s rc=0, `red-as-expected-spec-citations` 20.9 s
rc=1, `spec-coverage` 0.9 s rc=0, `red-as-expected-spec-coverage` 0.2 s rc=1. The three rows that
went STALE when `_main/_stepcache.py` changed (`stepcache-oracle`, `battery-plan`,
`red-as-expected-battery-plan`) were re-measured the same way: 7.9 s / 6.0 s / 22.0 s.

**Page after: `passos=550 PASS=294 EXPECTED-RED=233 FAIL=0 STALE=0 NO-VERDICT=0 NOT RUN=20
CARRIED=3`, `state-page PASS checks=7 fail=0`.** Budget after the five new rows:
`steps=530 total=2227.7s`, `RATCHET-OK`.

The lesson is the one this session keeps paying for: **a status that was never re-measured is a
status that describes an older tree** -- and a cache that refuses to record makes that permanent
instead of momentary.

## §9. The pre-commit gate was grading the owner's screen, not the product (2026-11-23, 21:2x)

The commit that closes this session was refused by the repository's own pre-commit gate:

```
compose-probe.mjs  FAILED  exit 1: deliver() -> THREW Error: instant replay refused:
  G:\watcher-state\cache\tmp\shadowplay-e2e-D6SF3N\0000.mp4 holds 27 contiguous distinct
  frames but covers 240 frame slots; the clock is there and the content is not
GATE 8 passed / 1 refused, exit 1
```

That sentence is the delivery gate **working**. `app/shadowplay/index.js:84-104` states the
contract in its own header -- *"A still desktop can hold run=24 at any duration and be refused,
which is the gate working, not a defect to route around"* -- because a replay clip whose content
cannot cover its own clock is not a replay. Nothing on the desktop moved during a 2 772 s caged
battery run, so every 8 s `gdigrab desktop` capture was content-short, and the probe published
`exit 1`: it graded **the screen**, not the product. A green tree could not commit.

Two measurements, same probe, same box, 122 s apart:

|source|frames captured|capture bytes|longest distinct run vs slots|delivery|probe rc|
|---|---|---|---|---|---|
|`desktop` (gdigrab)|190 (`capture()`)|69 447 B|**27 / 240** -> refused|refused|1|
|`testsrc2` (lavfi)|240|2 061 469 B|240 / 240|`action=instant-replay`, `0000.mp4` landed|0|
|`testsrc2` repeat|240|2 061 469 B|240 / 240|landed, `CLIP_FILES_ON_DISK=1`|0|

The repair is the source, not the verdict: `app/shadowplay/compose-probe.mjs` now asks for
`testsrc2`, which `NvencEncoder.captureAndEncode` already routes through the SAME `-f lavfi`
branch into the SAME NVENC, the SAME ring, the SAME IDR cut and the SAME delivery gate. The
artifact is real (2 061 469 B, 240 frames, `firstIdr=0`); only its *content* is guaranteed to move.
Three further facts, each in the file:

- **The desktop path stays measured where it belongs**, by `still-screen-probe.mjs`, which took the
  still/moving arm pair and PASSED in the same gate run.
- **`gdigrab desktop` is a hazard in a pre-commit gate**, measured in `nvenc.js:67-73`: at 60 fps it
  locks the Windows compositor, and a live 30 fps capture there already cost one
  `UI_WATCHDOG_EXIT code=9` on this box. A gate that runs on every commit must not grab the owner's
  screen to test a remux.
- **The refusal is still named, and the classifier is a control that can fail.** The probe carries a
  three-message arm (`CLASSIFY_ARMS=3/3`): the content-short sentence -> `still-desktop`, the
  `could not measure delivery` and `could not be counted` messages -> `unexplained`. `rc 0` requires
  BOTH the landed clip and 3/3, so a `testsrc2` clip refused content-short is a defect here -- the
  source moves by construction -- and a regex that stopped matching turns the probe red. It prints
  `SOURCE=testsrc2`, `DELIVER_REFUSAL_CLASS=none`, `PRODUCT_LANDS_A_NONEMPTY_CLIP=YES`.

Cost: compose-probe **24.55 s -> 3.35 s**, and the whole `run-all` gate stops spending 100 s
waiting on a desktop encode.

The lesson, and it is the same one as §8.9 with the sign flipped: **an instrument that reads the
world outside the product reports the world**. A green tree failed a gate because the screen was
still.
