# Documentation against the running code — Sotto

**Axis:** every numeric or behavioural claim in `H:/sotto/AGENTS.md` and `H:/sotto/docs/**` that can
be checked against the code, checked. Every claim below carries the doc `file:line` (quoted) and the
code `file:line` **or** the command + its output.

**Date:** 2026-10-06 (~08:2x local). **Mode:** READ-ONLY. I wrote exactly one file — this one.
The app is running (pid 30848); I did not launch, kill, restart or attach to it. No window was
opened by me on purpose (see SELF-AUDIT, "nao verificado"/side-effect note).

**Which side is right, in one line per finding.** Where the doc and the code disagree I say so and
name the winner. Where a doc is *self-contradicting*, I name the section that is right and the
section that is stale.

---

## 0. Summary

| # | doc claim (file:line) | code / instrument | verdict |
|---|---|---|---|
| F1 | `docs/README.md:8` "No application code has been written" | ~5.5k lines of app+worker code | **code wins** |
| F2 | `docs/README.md`, `docs/roadmap.md`, `README.md` describe a Tauri/Rust/CPAL/`transcribe.cpp`/Parakeet/SQLite stack as THE stack; `README.md:64` "Status: Planning." | the shipped app is Python + pywebview (WebView2); ASR is ONNX Runtime | **code/AGENTS win** |
| F3 | `AGENTS.md:169` "(arm P 0 of 41 samples …)" — panel not visible at startup | `AGENTS.md:215` same file says the panel IS visible 50 ms–7 s; the flash census says so too | **census wins; AGENTS contradicts itself** |
| F4 | `AGENTS.md:89` "fp16 1230 MB" | measured 1 307 568 147 B = 1247 MiB | **disk wins; 1230 stale** |
| F5 | `AGENTS.md:119` cites `worker-bridge.js:133` as "STATE_MAP" | `STATE_MAP` is declared at `:114`; `:133` is one entry inside it | code wins (citation nit) |
| F6 | `docs/oss-approaches-20261006.md:214` ranks "flip use_vad" #1 | §10 (`:444`–`:475`) RETRACTS it: "NO-OP on the bundled sample" | **§10 wins; §5 left standing** |
| F7 | `docs/live-captions-20261006.md:214` "keep Electron for now … WebView2 saves ~214 MB" | later same day: WebView2 IS the app and costs **+33% MORE** | **later measurement wins** |
| F8 | `docs/full-audit-transcription-20261006.md:310,326` describes the "1200 ms rule" join | `caption-formulation.js:72` `SENTENCE_GAP_S = 8` on the AUDIO timeline; the 1200 ms wall rule is gone | **code wins** |
| F9 | `docs/webview-shell-20261006.md:90` "fields compared: 14 | MISMATCHES: 0" | I reproduced **MISMATCHES: 0**, but **64** fields by the doc's own described method | claim holds; the count "14" is unexplained |
| F10 | `AGENTS.md:25` cites `worker/runs/exit3-armB-worker.jsonl` | that file is not there; it lives at `_main/exit3-armB-worker.jsonl` | code wins (wrong path cited) |

Claims that **held** (verified, not stale) are listed in §12.

---

## 1. F1 — `docs/README.md:8` says the repo is empty of code

**DOC** `docs/README.md:8-9`:

> Planning only. No application code has been written. What is here:

**CODE** — measured:

```
$ wc -l worker/sotto_worker.py app/webview/sotto_webview.py app/electron/worker-bridge.js \
        app/webview/run.cmd app/electron/panel.js
  1699 worker/sotto_worker.py
  2506 app/webview/sotto_webview.py
   768 app/electron/worker-bridge.js
   111 app/webview/run.cmd
   278 app/electron/panel.js
```

`worker/sotto_worker.py` is a 1699-line capture → chunk → encode → RNNT decode worker, and
`app/webview/sotto_webview.py` is a 2506-line WebView2 shell that `app/webview/run.cmd` launches as
**the app** (`AGENTS.md:97`). The sentence was true on the day it was written (2026-10-05, mtime
21:39) and is false now — it was never updated.

**Verdict: the code is right; the doc line is stale.** This is the most consequential stale claim in
`docs/`, because a reader trusts this file first.

---

## 2. F2 — three documents still describe the abandoned Tauri/Rust stack as the product

**DOCS**

- `docs/README.md:22-27`: "`nvidia/nemotron-3.5-asr-streaming-0.6b` … along with `transcribe.cpp`
  as the C++ runtime that loads both without a resident Python."
- `docs/roadmap.md:53-64`: "**M0 — Foundation.** Tauri 2 + Rust + Svelte." … "**M1 — Loopback
  capture.** WASAPI render-endpoint capture through CPAL" … "**M2 — First transcription.** Parakeet
  Redux through `transcribe.cpp`".
- `README.md:50-58`: "**Shell** — Tauri 2, Rust, Svelte 5 + TypeScript. No Electron." … "**Search**
  — SQLite + FTS5 + sqlite-vec".
- `README.md:64`: "Planning. See `docs/roadmap.md`."

**CODE** — the app the owner runs is Python:

```
$ ls -la app/src-tauri/Cargo.toml app/webview/sotto_webview.py app/webview/run.cmd
2026-10-05 21:45:13  app/src-tauri/Cargo.toml
2026-10-06 05:24:57  app/webview/sotto_webview.py
2026-10-06 04:53:05  app/webview/run.cmd
```

A Tauri skeleton **does** exist (`app/src-tauri/{Cargo.toml,build.rs,src/*.rs}`,
`app/dist/assets/index-*.js`), but it has not been touched since 2026-10-05 21:45 and `cargo` hangs
on this host — measured and recorded in `docs/live-captions-20261006.md:208-213` ("`cargo` sat 12+ min
on 'Updating crates.io index' with CPU frozen at 0.203125"; `app/cargo-fetch.log`,
`app/cargo-build.err.log` are 30-byte failures). The shipped pipeline is:

- capture + decode: `worker/sotto_worker.py` (ONNX Runtime, `onnxruntime-genai`),
- shell: `app/webview/sotto_webview.py` (pywebview + WebView2),
- launcher: `app/webview/run.cmd`.

`AGENTS.md:95-96` already records the owner's ruling — "**WebView2 is the app.**" — so `AGENTS.md`
and the stack docs disagree with each other, and `AGENTS.md` is the one that tracks the code.

**Verdict: AGENTS.md/the code are right; `README.md`, `docs/README.md`, `docs/roadmap.md` describe a
plan that was abandoned on 2026-10-05.** These three are dated "Written 2026-10-05" / "Planning" and
were never updated. Nothing in them is a lie about the past; every one of them is now wrong about
the present.

---

## 3. F3 — AGENTS.md contradicts itself about the panel at startup (the known "0 of 41")

**DOC (first bullet)** `AGENTS.md:152-170`, ending at `:168-170`:

> Gate, both colours in ONE run: `pythonw.exe _main/panel-startup-visibility-oracle.py` → `VERDICT
> PASS` (arm P **0 of 41** samples, arm B — cure removed — on screen, arm S — `--show` — still
> visible).

**DOC (later bullet, same file)** `AGENTS.md:215-218`:

> - **THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s, AND `run.cmd` IS NOT THE CAUSE** …

**INSTRUMENT** — the sibling census states outright that it contradicts the first bullet.
`_main/panel-startup-flash-census.py:1-9`:

> """CENSUS: BOUND the intermittent panel flash at shell startup.
>
> Sibling lane `SottoErrorRecovery` caught a SUB-SAMPLE panel flash with its own census,
> **contradicting `AGENTS.md`'s "arm P 0 of 41"**:
>
>     CENSUS-PID visible pid=36332 hwnd=6955742 title='Sotto' sample=4   (200 ms, 1/163)
>     CENSUS-PID visible pid=32508 hwnd=82451080 title='Sotto' sample=168 (100 ms, 1/302)
>     …
> 3 of 5 censuses caught it, each for ONE sample."

**The "0 of 41" line is real** — it is in the log the oracle wrote:

```
$ grep 'CENSUS-PID arm=P' _main/panel-startup-visibility.log
CENSUS-PID arm=P samples=41 pid=15720 name=pythonw.exe main_hwnd=0 visible_samples_over_tree=0 pids_in_tree=[896, 5580, 7228, 15720, 33892, 35244, 35352]
```

So the oracle's own arm P recorded `visible_samples_over_tree=0` over 41 samples. The defect is not
that the line is fabricated — it is that **41 samples at the oracle's cadence is not enough to prove
absence**, and the finer census (25 ms, ≥20 launches) then caught the flash. `AGENTS.md` already
knows this: the very next bullet (`:171-177`) says "a missing `ALERTA-JANELA` is NOT proof that no
window appeared … a window that lives less than that can pass it unseen", and `:245-246` says
'"0 visible in N samples" is not absence'. The file asserts the clean result at `:169` and, two
bullets later, asserts the rule that invalidates it.

**Verdict: the flash census and `AGENTS.md:215` are right — the panel DOES appear at startup for
~50 ms to ~7 s. `AGENTS.md:169`'s "0 of 41" is a sampling artifact presented as a pass, and it
contradicts `AGENTS.md`'s own later measurement.**

---

## 4. F4 — `AGENTS.md:89` fp16 weight figure does not match the disk

**DOC** `AGENTS.md:89`:

> Model weights on disk: **int4 756 MB / int8 1020 MB / fp16 1230 MB**;

**CODE/DISK** — measured:

```
$ python -c "import os
for m in ['int4','int8','fp16']:
  d='worker/models/nemotron-3.5-asr-streaming-0.6b-'+m
  t=sum(os.path.getsize(os.path.join(dp,f)) for dp,_,fs in os.walk(d) for f in fs)
  print(m, t, 'bytes =', round(t/1024/1024,1),'MiB')"
int4 792603807 bytes = 755.9 MiB
int8 1070567736 bytes = 1020.9 MiB
fp16 1307568147 bytes = 1246.9 MiB
```

- int4 756 / int8 1020 — the doc numbers match MiB to the decimal (the doc labels MiB as "MB").
- **fp16: the disk says 1246.9 MiB / 1307.6 MB; the doc says 1230.** No reading of the fp16
  directory (whole dir 1247 MiB; `.onnx.data` sidecars only 1285.3 MB) yields 1230. There is also
  **no fp16 RAM probe** in `_main/` — only `precision-ram-probe-int4.log` and `-int8.log` exist — so
  the 1230 figure has no receipt on disk today.

**Verdict: the disk is right; `AGENTS.md:89`'s fp16 number is stale or mis-transcribed.** int4/int8
on the same line are exact.

---

## 5. F5 — `AGENTS.md:119` cites `worker-bridge.js:133` as "STATE_MAP"

**DOC** `AGENTS.md:118-119`:

> That is the decision `app/electron/worker-bridge.js`'s STATE_MAP already carried
> (worker-bridge.js:133) …

**CODE** `app/electron/worker-bridge.js:114` is the declaration; `:133` is one entry:

```
114:const STATE_MAP = {
133:  device_exhausted: { kind: 'error', status: 'No audio tap carried signal - every candidate device was silent', title: 'No working audio tap' },
```

**Verdict: the citation is loose, not wrong.** Line 133 is the *error* entry for a silent device,
which is exactly the decision the sentence is about; `STATE_MAP` itself starts at 114. The semantic
claim (a silent device is painted as an error) is correct.

---

## 6. F6 — the `use_vad` "rank-1" claim is retracted in the same file

**DOC (ranking)** `docs/oss-approaches-20261006.md:214`:

> 1. **A3 — flip `use_vad` to true** (`worker/config.json:17`). **LANDED 2026-10-06 — and measured to
>    [not confirm the rank-1 premise]**

**DOC (retraction)** `docs/oss-approaches-20261006.md:444-475`:

> ## 10. RETRACTION — rank-1 ("flip `use_vad` to true") is WITHDRAWN as stated
> §5 ranked **A3 … first**, on the premise that it is *"one boolean"* …
> **Verdict: §5's rank-1 recommendation is WITHDRAWN as stated.**

The measurement agrees with the retraction: `docs/model-specs/README.md:161-167` ("Flipping the
boolean alone changed **nothing measurable on `worker/assets/sample1.flac`** — identical 16 captions,
94 tokens, 262 frames") and `AGENTS.md:22` ("On the bundled sample the transcript is
**byte-identical** with the flag on and off … that clip has no 3.36 s stretch of silence").
`worker/config.json` ships `"use_vad": true` but the flag is gate-only.

**Verdict: §10 and the measurements are right; §5's ranking survives earlier in the same file.** A
reader who stops at the ranked list (line 214) gets the pre-measurement claim. The file is
self-correcting, but the correction is 230 lines below the claim, with no pointer at §5.

---

## 7. F7 — `live-captions` leaves a superseded shell decision standing, with a number that flipped sign

**DOC** `docs/live-captions-20261006.md:214-216` (timestamped 04:56Z):

> DECISION: **keep Electron for now.** A WebView2 port saves ~214 MB of a ~2.4 GB process (the engine
> is 9% of the footprint — the model is 89%) …

**LATER SAME DAY** `docs/webview-shell-20261006.md:154-155`:

> **So: 416.3 MB against 312.2 MB — the WebView2 shell costs about 33% MORE memory, not less.**

and `AGENTS.md:97-99`: "**The app is `app/webview/run.cmd`.** Electron is the EARLIER shell, not a
fallback; do not offer it as one. The +33% memory verdict was measured and the owner ruled on it."

**Verdict: the later measurement + the owner's ruling are right.** Two problems in
`live-captions-20261006.md` are left uncorrected: (a) the decision "keep Electron for now" was
reversed hours later and never struck; (b) "a WebView2 port **saves ~214 MB**" is the opposite sign
of the later measured "**costs 33% more**". A reader skimming §04:56Z gets both the wrong decision
and the wrong direction of the memory trade.

---

## 8. F8 — `full-audit` describes a join rule the code no longer has

**DOC** `docs/full-audit-transcription-20261006.md:310` and `:326`:

> Gaps of 0.56 s and 1.12 s are under the 1200 ms rule and **did** join …
> | display join | consequence | `panel.js:57` 1200 ms rule; joined `"cre s partici"` correctly …

**CODE** — the 1200 ms **wall-clock** rule was replaced by an AUDIO-timeline gap;
`app/electron/caption-formulation.js:68-75`:

```
 * This is the boundary the old 1200 ms WALL-CLOCK rule could never see: at
const SENTENCE_GAP_S = 8;
const SENTENCE_MAX_CHARS = 90;
```

and `app/electron/panel.js:59-61` explains why the old rule was inert:

> Why the old join was inert, measured: `PHRASE_GAP_MS` was 1200 ms of WALL clock, but the worker
> emits one fragment per ~560 ms of AUDIO and the panel received them faster than that, so the gap
> rule never fired and every fragment became its own line.

`PHRASE_GAP_MS` is now referenced **only in that comment** — `grep -n PHRASE_GAP_MS app/electron/*.js`
returns panel.js:59 alone; there is no live constant.

**Verdict: the code (`SENTENCE_GAP_S = 8` on the audio timeline) is right.** `full-audit`'s
"display join" row describes a mechanism that no longer exists; it was diagnosed and replaced the
same day (`docs/caption-formulation-20261006.md:34-53`).

---

## 9. F9 — `webview-shell`'s "14 fields, 0 mismatches": 0 mismatches reproduced, "14" not

**DOC** `docs/webview-shell-20261006.md:85-90`:

> **Mechanical diff — 14 fields, 0 mismatches:**
> ```
> … (compare viewport/zoom/body/sheets + every element's rect/color/display/position/visibility/opacity)
> fields compared: 14 | MISMATCHES: 0
> ```

**REPRODUCED** — I parsed the doc's own two logs with the doc's own described method
(`_main/electron-dump-fresh.log`, `_main/webview-dump.stdout.txt`; each carries one `DOMDUMP` line):

```
$ python …  (viewport/zoom/body/sheets + every element's 6 display fields)
electron keys ['body','els','sheets','viewport','zoom']   els=10
webview  keys ['body','els','sheets','viewport','zoom']   els=10
fields compared: 64 MISMATCHES: 0
```

**Verdict: the substantive claim is right — the two shells render identically (0 mismatches, same
10 elements, same viewport/zoom/body).** But the count "14" does not fall out of the method the doc
itself names: that method yields 64 fields on today's logs. The "14" is unexplained and not
reproducible; it is also repeated in `AGENTS.md:94` ("14 DOM fields compared, 0 mismatches").

---

## 10. F10 — `AGENTS.md:25` cites an artefact at the wrong path

**DOC** `AGENTS.md:25`:

> … (measured: `worker/runs/exit3-armB-worker.jsonl`).

**CODE/FS**:

```
$ python -c "import glob; print(glob.glob('worker/runs/exit3*'), glob.glob('**/exit3-armB*', recursive=True))"
[] ['_main\\exit3-armB-worker.jsonl', '_main\\exit3-armB-worker.jsonl.err', '_main\\exit3-armB1.log', …]

$ grep -o 'all-candidate-taps-flat\|silent-device\|all-flat' _main/exit3-armB-worker.jsonl | sort | uniq -c
      1 all-candidate-taps-flat
      4 all-flat
      2 silent-device
```

The receipt exists and its content matches the claim (a `done` verdict `all-candidate-taps-flat`
beside 2 `silent-device` statuses — the exact divergence the bullet describes), but it lives under
`_main/`, not `worker/runs/`. Every other receipt `AGENTS.md` cites is under `_main/`, which makes
this one path a typo.

**Verdict: code/FS right; the path in the citation is wrong (the file is real, one directory over).**

---

## 11. Claims I could not verify, and why

- **Memory numbers that require launching the app** — `docs/webview-shell-20261006.md:141-156`
  (416.3 MB vs 312.2 MB) and `docs/live-captions-20261006.md:205` (ASR worker `peak_rss_mb`
  2141.7 MB), plus the gpu-route RSS tables. Verifying these means running the shell / worker; the
  brief forbids launching the app or a browser, and the app is already running (pid 30848). I did
  **not** run them. The webview-shell numbers do have a receipt description (a
  `--show --memory --memory-wait 7` run) but no log I could find on disk to re-read.
- **The oracles' own `VERDICT PASS`** — `py -3 _main/panel-startup-visibility-oracle.py`,
  `_main/panel-exit3-oracle.py --unit --neg-arm`, `_main/run-cmd-exit-oracle.py` all **execute the
  real entry point / spawn processes / open a WebView2 form** (the first's docstring: "it runs the
  REAL entry point that `app/webview/run.cmd` launches"). Running them would put a window on the
  owner's desk — exactly what the brief forbids. I verified them **by reading the instruments and
  the logs they already wrote** (`_main/panel-startup-visibility.log` line 11 is the "0 of 41"
  receipt); I did not re-run them, so their green is **not** re-confirmed by me.
- **`run.cmd --help` is "byte-identical … 2272 B"** (`AGENTS.md:187-188`) — would require executing
  the wrapper / a console interpreter; not run.
- **The routing numbers** (`AGENTS.md:37-49`: peak 0.4999, 0.00003, 0.000122). `_main/inject-all-probe.py`
  and `_main/listen-probe.py` exist but the **`.log` files the doc implies do not**; the only 0.000122
  I found on disk is inside `_main/_ppv-fullrun.log` (a different probe). The device *indices*
  (MME #2 / DirectSound #15 / WASAPI #32) I **did** verify — see §12.
- **The house window census "every 60 s"** (`AGENTS.md:171`) — that governor lives under
  `I:/!manager/scripts/window-census.ps1`, outside this repo.
- **`docs/stack-verification.md`** (628 lines) is a set of 2026-10-05 URL fetches with quoted
  primary-source text. I read its headers and structure but did not re-fetch the URLs; its internal
  consistency and the licence quotes are not checkable against this repo's code at all.

---

## 12. Claims that HELD (verified, not stale)

These are not findings; they are listed so the audit is auditable in both directions.

| claim | evidence |
|---|---|
| `AGENTS.md:11` normative `blank_id 13087 / max_symbols_per_step 10 / chunk_samples 8960` | `worker/models/…-int8/genai_config.json` declares exactly these; the doc's own oracle runs clean: `py -3 -c "…"` → `dir …-int8`, `blank_id 13087 chunk 8960 maxsym 10`, `lang_id auto use_vad True`, **rc=0**. |
| `AGENTS.md:34` "MME #2, DirectSound #15, WASAPI #32" | `_main/device-names.log`: `id=2 … api=MME … 'CABLE Output (VB-Audio Virtual '`, `id=15 … api=Windows DirectSound … 'CABLE Output (VB-Audio Virtual Cable)'`, `id=32 … api=Windows WASAPI`. Exact. |
| `AGENTS.md:22` use_vad LIVE, gates, exit 1 unhandled | `worker/config.json` `"use_vad": true`; `genai_config.json` `vad {threshold 0.3, silence_duration_ms 3360, prefix_padding_ms 560}`. |
| `AGENTS.md:24` silent-device → **exit 3** | `worker/sotto_worker.py:1606` `verdict = "silent-device"`, `:1630-1631` `state="silent-device", verdict="silent-device"`, `:1692` `return 3 if ran_but_silent else 0`. |
| `AGENTS.md:25` verdict order (`ran_but_silent` FIRST) | `worker/sotto_worker.py:1602-1612` tests `if ran_but_silent:` before `elif outcome in ("all-flat","open-failed")`. |
| `AGENTS.md:89` int4 756 / int8 1020 + RSS 924 / 1192 | `_main/precision-ram-probe-int4.log`: `total=755.91 MB … FINAL RSS=923.6`; `-int8.log`: `total=1020.30 MB … FINAL RSS=1191.9`. |
| `AGENTS.md:118-119` STATE_MAP paints `silent-device`/`device-exhausted` as errors | `app/electron/worker-bridge.js:133` `device_exhausted: {kind:'error',…}`; `:114` declares the map. |
| `AGENTS.md:141` line citations | `app/webview/sotto_webview.py:144-155` is the positive `if verdict not in HEALTHY_DONE_VERDICTS` branch; `:168-179` is the no-verdict footer sentence. Both exact. |
| `AGENTS.md:115-118` panel text names the device | `sotto_webview.py:176-180` renders `device` … (footer carries the device); silent-device footer confirmed in `_main/_ppv-fullrun.log` ("Silent audio device - Mapeador … [MME] peaked 0.000122 < floor 0.002"). |
| `docs/model-specs/README.md` "copied verbatim into `original/`" | sha256 match: `original/{int4,int8}/genai_config.json`, `original/int8/README.md`, `original/fp16/{config,languages}.json` are byte-identical to the files in `worker/models/`. |
| `docs/audio-ladder.md` §3 ladder order (c→a→b→tail), floors, rung names | `worker/sotto_worker.py:635-740` `device_candidates()`: rung C first (`if wanted: offer(d,"c","explicit override")`), then `offer(spec,"a",…)`, then `"b"` by `heuristic_loopback_score`, then the tail; `TAP_PEAK_FLOOR = 0.002` at `:152`; `LOOPBACK_NAME_PATTERNS` at `:102-115` matches the doc's list verbatim. |
| `docs/audio-ladder.md` §2 "exact 3:1 block average at 48 kHz → 16 kHz" | `worker/sotto_worker.py:759-772` `resample_to_16k`: `k = src // TARGET_SR; … reshape(-1,k).mean(axis=1)`. |
| `docs/audio-ladder.md` §4 capability-probe output | `_main/capability-probe.log` reproduces the quoted 203 packets / 97056 samples / peak=0.350000 / `VERDICT: YES …` lines. |
| `docs/webview-shell-20261006.md` §2 identity | see F9 — 0 mismatches reproduced. |

---

## 13. SELF-AUDIT

- **protocolos em falta** — Two. (1) I ran `grep`, `wc`, `python` etc. as shell children of the
  harness without an explicit `CREATE_NO_WINDOW` on each; the hook's own census then reported
  `ALERTA-JANELA ts=2026-10-06T08:28:22Z … nome=cmd` at 08:28:22Z — plausibly my tool shell's
  `cmd.exe`. I never launched the *app* and never called `start`/`Start-Process`, so the flash the
  census caught is a `cmd` console, not a Sotto window — but the brief said "prefer not launching
  anything", and a stricter reading would have routed every command through a hidden-spawn shim
  (like the house's `scripts/run-hidden-task.vbs`). What I would do differently: pass every probe
  through an existing `CREATE_NO_WINDOW` wrapper rather than the bare shell. (2) I should have read
  `_main/SottoStartupVisibility.md` and `_main/panel-exit3-armE-receipt.md` **before** re-deriving
  the "0 of 41" contradiction from `panel-startup-flash-census.py` — they already named it
  (`_main/panel-exit3-armE-receipt.md:140`).

- **verificacao adicional** — a cheap one, not run: re-run the webview-shell DOM diff **with the
  doc's own counting code** rather than my re-implementation, to decide whether "14" or "64" is the
  intended field count (the doc does not paste that code). Cost: ~0 (the two logs are on disk); not
  run because the doc gives no script to run, and inventing one is what produced the "14 vs 64"
  ambiguity I am reporting. A second, more expensive one: launch the shell once with
  `--show --memory --memory-wait 7` under `CREATE_NO_WINDOW` to re-measure 416.3 MB / 312.2 MB —
  **cost: it opens a window**, so it is out of scope for a read-only audit.

- **checkboxes novas** — one mechanical step for this class: **every `file:line` citation in a doc
  must resolve on disk before the doc is committed** — a one-liner that pulls all `path:line`
  strings out of a `.md`, stats each path, and reprints the cited line to confirm it says what the
  doc claims. RED input: `AGENTS.md:25`'s `worker/runs/exit3-armB-worker.jsonl` (does not exist; the
  file is at `_main/`), and `AGENTS.md:119`'s `worker-bridge.js:133` (resolves to an entry, not the
  declaration) — both would be caught. This is the same shape as the house's "verify cited paths
  before the task" rule and it is not yet applied to docs.

- **review por outro subagente** — **sim-com-escopo**: a reviewer should (a) independently re-parse
  `_main/electron-dump-fresh.log` + `_main/webview-dump.stdout.txt` to settle the "14 vs 64" field
  count, and (b) confirm my reading that `docs/README.md` + `docs/roadmap.md` + `README.md` are
  *stale-by-supersession* rather than describing a still-live parallel workstream (I judged
  abandoned from the frozen mtime + the measured cargo hang, not from an owner statement).

- **gate-doubt:**
  - **verde-de-verdade:** The one green I actually produced is the model-specs ORACLE, and it is a
    real green: `py -3 -c "…"` exits **0** with `blank_id 13087 chunk 8960 maxsym 10 lang_id auto
    use_vad True`. It could **not** pass vacuously: it reads `worker/config.json`'s `model.dir`,
    then opens `worker/<dir>/genai_config.json` and asserts two constants — a wrong `dir` or a wrong
    constant both exit 1. The greens I did **not** produce (the three oracle `VERDICT PASS` lines)
    are exactly the ones at risk: they are quoted in `AGENTS.md` from runs I cannot re-run without
    opening a window, and the "0 of 41" case proves that green **can** be vacuous on this surface.
  - **falta-no-gate:** the "0 of 41" oracle verifies the panel is not visible **at its own
    cadence**, and the census proves that cadence misses a <100 ms flash. A future change (e.g.
    removing the posted `_reassert_hidden` half) would cross this gate green and still flash the
    panel: `AGENTS.md:215-246` documents precisely that happening after the cure was considered
    green.
  - **gate-melhor:** a mechanical check that closes it: assert the oracle's PID-tree census samples
    at the **flash-census cadence**. Command: `py -3 _main/panel-startup-flash-census.py --arms real
    --n 20 --ms 25` with a pass condition of `owner_samples == 0` across all 20 launches. Input that
    **must** make it RED: today's tree (F3 — the real arm catches 1-sample flashes), which is why
    the honest pass bar is 0-of-N at 25 ms, not 0-of-41 at ~200 ms.

- **confianca** — **alta** for §1–§10 (each is a doc line vs a code line/file, both quoted, and the
  numeric ones re-measured). **media** for §11's unverified set (memory figures and oracle greens
  are not re-run) and for the "abandoned stack" judgement in F2 (inferred from mtime + measured
  cargo hang, not from an owner statement). What would raise it: one hidden-spawn run of
  `--show --memory --memory-wait 7` for the memory pair, and one run of the flash census for F3's
  current state.

- **nao verificado** — (1) memory/RSS figures in `webview-shell`, `live-captions`, `gpu-route`,
  `int8-route`, `accuracy-int4-vs-fp16`, `worker-single-instance` (need a launch); (2) the three
  oracles' live `VERDICT PASS`; (3) `run.cmd --help` byte count; (4) `stack-verification.md`'s URL
  quotes (not re-fetched); (5) the router peaks 0.4999 / 0.00003 (their `.log`s are absent);
  (6) the `I:/!manager` window-census cadence; (7) whether `app/src-tauri/` is truly dead vs merely
  paused (no owner statement found — only mtime + the measured `cargo` hang).

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh AuditDocVsCode` — VERBATIM (rc=0; full output at
`artifact://1719`):

- cache: read=7288192 write=0 hit=97.4390% (cache-read / input+cache-read); universe: 58 usage rows
  from `…\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditDocVsCode.jsonl`;
  instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing;
  exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: break_items=1 WHEN=2026-10-06T08:24:34.915000+00:00 | break_items=1
  08:24:36.967000+00:00 | break_items=1 08:24:38.449000+00:00 | break_items=3 08:24:39.606000+00:00
  | break_items=2 08:26:29.825000+00:00 (state=RESOLVED-BREAKS-OMP; 5 of 113513 OMP
  prefix-ledger rows attributable to keys `['01a10f72-c0a0-7284-9445-0cecfd6636ce',
  'AuditDocVsCode']`)
- where-failed: session_id=01a11050-0fed-77af-8c7d-efb85d8edcda provider=deepseek-flash
  item_index=100; turn_id=1791275189825 (and 4 sibling rows, all `item_index=0`, listed in the
  receipt above)
- source: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditDocVsCode.jsonl`

Additional lines from the same run: **usage rows 58**, models/routes
`cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free,
opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free`; input 191556 / output 41117 /
cache-read 7288192 / cache-write 0; **prefix breaks: 8**; `verdict: UNKNOWN — no task-level
acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision`.
