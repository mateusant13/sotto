# Receipt — THE DEAD-CONTROL SWEEP (`_main/`, 2026-10-11)

**Owner order in force, verbatim:** *"para de abrir o sotto, ta travando meu pc quando ele abre."*
Nothing was launched: no `app/webview/sotto_webview.py`, no `run.cmd`, no worker, no WebView2/electron
probe, no `_main\_audit-verify-all.cmd`. No process was killed. Every run below is an IN-PROCESS run of an
instrument (`node` / `pythonw.exe`) that does not open the app.

**Law applied:** *a check that cannot say NO (or cannot say YES) must be repaired or named as an OPEN gap.*

**How every number here was measured.** Bytes and sha256 were recomputed in this pass with `node`
(`fs.readFileSync` + `crypto.createHash("sha256")`) over the bytes on disk — no pin was inherited from
`AGENTS.md`. Exit codes and verdict lines were captured from foreground runs launched as
`Start-Process -FilePath pythonw.exe|node -NoNewWindow -Wait -PassThru -RedirectStandardOutput …`
(`pythonw` so no console can appear); the raw stdout/stderr of every run is on disk in
`G:\Temp\dc-sweep\<name>.out` / `.err`. `rc` is `$p.ExitCode`.

---

## 1. The two instruments the Lead repaired — VERIFIED, both colours, re-run in this pass

| instrument | bytes | sha256 (12) | colour | rc | measured verdict line |
|---|---|---|---|---|---|
| `_main/redux-live-contract-oracle.js` | 18 524 | `016C45B73795` | shipped | 0 | `CONTROL-VERDICT PASS armB(wrong start)-RED=true armC(shared start)-RED=true armD(per source)-GREEN=true` / `VERDICT PASS - 8/8 shipped-contract arm(s) held` |
| ″ | | | `--neg-arm` | 0 | `D1/legacy-keying-went-RED: 3 commit(s) over 3 source(s) at start=0.0 -> 1 row(s), replaced=2` / `armD(legacy keying)-RED=true` / `VERDICT PASS - 8/8` |
| `_main/_panel2-repeat-probe.js` | 18 231 | `ECA792B1CD04` | shipped | 0 | `RESULT: GREEN — 4/4 arm(s)` |
| ″ | | | `--revert` | 0 | `CONTROL: arms failed = 4 of 4 — want > 0` / `control copy removed: true` / `CONTROL PASS — the identity rule is what removes the repetition` / `RESULT: GREEN — control behaved as required` |

Both are LIVE: the flag changes what is measured, and the arm that must notice goes RED.
(The `--neg-arm` colour of the oracle skips the LIVE arms on purpose: 94 lines vs 106, and the final
line drops `live=GREEN(9/9)` — it does not re-assert a measurement it did not take.)

## 2. Repairs made in this pass (2 files, both under `_main/`)

### 2.1 `_main/audio-meter-oracle.py` — the whole oracle was DEAD (crash in BOTH colours)

* before: **16 744 B**, sha256 `0F1D6E9ED64F4F56758DE86DE22D1C1F0AF86B3EA7DB483D654F5A20D68867F2`
* after: **18 330 B**, sha256 `72942D49D7F241377915389BE1A2AD7C3272E8F110FD8CBD98EE5EACD011644A`

Measured before the repair, both colours, rc=1, no verdict line at all:

```
File "H:\sotto\_main\audio-meter-oracle.py", line 118, in stream
    m = W.AudioMeter(hz, now=0.0, block_s=block_s)
TypeError: AudioMeter.__init__() got an unexpected keyword argument 'block_s'
```

The shipped class is `worker/sotto_worker.py:1341` `class AudioMeter` with
`def __init__(self, hz=METER_HZ, now=0.0)` (`:1349`) — **no `block_s`, no `blocks_per_window`**. The
oracle was written against the block-count-window version this file does not have. Repairs, smallest first:

1. `stream()` now drives the shipped signature: `m = W.AudioMeter(hz, now=0.0)`.
2. `--neg-cadence` **refuses loudly** instead of being an inert mutant. The old mutant called the
   original `__init__` and then set `self.blocks_per_window = 0`, an attribute **nothing in the worker
   reads** — a mutant that cannot move one arm, and with the cadence arms already RED it would have
   printed `VERDICT: PASS` by inheriting a red base. It now checks
   `inspect.signature(W.AudioMeter.__init__)` and returns **rc=2** with
   `SETUP ERROR: --neg-cadence CANNOT BE BUILT — the SHIPPED AudioMeter has no block-count rule to remove
   (AudioMeter.__init__(self, hz=10.0, now=0.0)) …`.

Measured after the repair (four colours, foreground):

| colour | rc | measured verdict |
|---|---|---|
| shipped | **1** | `audio-meter-oracle: 9 PASS / 2 FAIL (11 arms)` → `VERDICT: FAIL` — the two FAILs are the cadence arms, with numbers: `100 blocks of 100 ms produce 100 events` got `(99, 9.9)`; `a tap paced at 99 ms still yields one point per block` got `(49, 4.95)` — i.e. **9.9 Hz and 4.95 Hz, the "6 Hz beat" the oracle's own docstring describes** |
| `--neg-arm` | **0** | `NEG (window): 3 arm(s) of this claim went RED as required, 0 stayed green (must be 0), 0 control arm(s) broke (must be 0)` / `VERDICT: PASS` — the flag is now REAL (before: crash) |
| `--neg-cadence` | **2** | `SETUP ERROR: … CANNOT BE BUILT …` (the mutant is unbuildable; named, not faked) |
| `--neg-default` | **0** | `NEG (default): 2 arm(s) of this claim went RED as required, 0 stayed green, 0 control arm(s) broke` / `VERDICT: PASS` |

Cost/shape arms measured in the same run: event = **47.0 B** → 470 B/s at 10 Hz; `emit()` 2.05 µs,
`format+write+flush` 3.34 µs, `AudioMeter.tick` 0.06 µs → all < 0.1 % of one core at 10 Hz.

### 2.2 `_main/_design-lane/theme-assert-lib.js` — the theme gate could never say YES

* before: **4 154 B**, sha256 `C7703B5383F3D4C1034F44822977AE6998B89C848F6B05B61743CA7EF11EA768`
* after: **5 110 B**, sha256 `EE495AEB0335F7AE729881A2436D0A0B44C094F84283B1A7EAD86F982FB0BFD2`

Measured before, `node _main/_design-lane/assert-themes.js` → rc=1,
`VERDICT FAIL — 5 file(s) violated the contract`, with **13 / 13 / 8 / 10 / 29** "unscoped selector(s):
`0% | 49% | 50%`". Those are **`@keyframes` STEPS**, not selectors: the walker pushed every prelude that
did not start with `@`, so `0%`, `49%`, `50%`, `from`/`to` inside `keyframes` were counted, found
unscoped, and turned every animated theme file RED. The instrument's own docstring claims it checks
"EVERY selector" — a keyframe step is not one. The repair tracks the `keyframes` block and skips its
steps (the at-rule's depth is popped on `}`); `node --check` passes.

Measured after: unscoped per file drops **13→4, 13→4, 8→4, 10→4, 29→4**, and the four that remain are
IDENTICAL in all five files and are REAL:

```
theme-N.css:576  :root[data-theme='theme-N'] .panel__header,  .panel__header *,  .status,  .status *,
theme-N.css:577  :root[data-theme='theme-N'] .chrome,  .chrome * {
```

Only the first member of each comma group carries the scope prefix, so `.panel__header *`, `.status`,
`.status *` and `.chrome *` leak into all five themes at once. The gate is now RED for a **true**
positive instead of mostly noise — see OPEN gap **B**.

## 3. Every candidate EXERCISED in this pass

`sha256` column = first 12 hex chars, upper case, measured on the bytes on disk. "can say NO before/after"
is about the CONTROL, not about the shipped verdict.

| instrument | bytes | sha256(12) | flag | could it say NO **before**? | evidence (rc / measured line) | can it say NO **after**? |
|---|---|---|---|---|---|---|
| `_main/audio-meter-oracle.py` | 18 330 | `72942D49D7F2` | `--neg-arm`, `--neg-cadence`, `--neg-default` | **NO — crashed**, rc=1 both colours | `TypeError … 'block_s'` (see §2.1) | **YES** — neg-arm 3 window arms RED, rc=0 `VERDICT: PASS`; cadence flag now refuses rc=2 |
| `_main/_design-lane/theme-assert-lib.js` | 5 110 | `EE495AEB0335` | shared lib of `assert-themes.js`/`assert-themes-neg.js` | **NO (could not say YES)** — 5/5 files RED | rc=1 `VERDICT FAIL — 5 file(s)…` (13/13/8/10/29 keyframe artifacts) | **YES** — residual 4 REAL unscoped selectors per file; mutants still RED for their own reason |
| `_main/redux-live-contract-oracle.js` | 18 524 | `016C45B73795` | `--neg-arm` | yes (Lead-repaired) | rc=0 `VERDICT PASS - 8/8`; `--neg-arm` rc=0 `armD(legacy keying)-RED=true` | VERIFIED unchanged |
| `_main/_panel2-repeat-probe.js` | 18 231 | `ECA792B1CD04` | `--revert` | yes (Lead-repaired) | rc=0 `4/4 arm(s)`; `--revert` rc=0 `CONTROL PASS` | VERIFIED unchanged |
| `_main/history-gallery-oracle.js` | 10 855 | `8DE0CEDE7EDF` | `--neg-arm` | yes | rc=0 `RESULT: GREEN — 6/6 arm(s)`; `--neg-arm` rc=0 `NEG-ARM: red=["a stamp is built in LOCAL time (the UTC-parsing trap)"]`, `NEG-ARM-VERDICT: PASS` | YES (live) |
| `_main/theme-tune-oracle.js` | 13 752 | `46F67752A501` | `--neg-arm` | yes | rc=0 `ARMS: 64 PASS: 64 FAIL: 0 VERDICT: PASS`; `--neg-arm` rc=0 `ARMS: 66 PASS: 66 FAIL: 0` (adds "the gate REJECTS a declared-but-unread token" / "ACCEPTS a consumed token") | YES (live) |
| `_main/historico-vs-redux-probe.js` | 10 901 | `0D83768A3432` | `--gate-off` | yes | rc=0 `RESULT: GREEN — the transcript carries only the worker-closed line`; `--gate-off` **rc=1** `RESULT: RED — 2 violation(s)` | YES (live; the control colour is rc=1) |
| `_main/panel-live-vs-history-probe.js` | 11 593 | `5E81512F088A` | `--gate-off` | not exercised in the neg colour | rc=0 `RESULT: GREEN — 9/9 arm(s)` | UNMEASURED (neg colour not run) |
| `_main/history-producer-gate.js` | 34 252 | `7DBD42EC7A93` | `--control-stamp-nvidia` | yes | rc=0 `PRODUCER-VERDICT: producer-wired-through`; control rc=0 `verdict real = RED` / `CONTROL PASS` / `RESULT: RED` | YES (live) |
| `_main/route-stamp-gate.js` | 30 620 | `36BEDAD31E13` | `--emit-mutant`, `--emit-panel-mutant` | yes | rc=0 `GATE: PASS — 17/17 arm(s) (live GREEN, and every arm RED on its own mutation)` | YES (live) |
| `_main/panel-row-identity-oracle.js` | 32 509 | `4FEE0E456503` | `--neg-arm` | yes | rc=0 `AS-SHIPPED COLOURS: CHK-A=GREEN … CHK-F=GREEN  VERDICT: PASS`; `--neg-arm` rc=0 `CHK-E=RED`, others GREEN, `VERDICT: PASS` | YES (live) |
| `_main/_panel2-dom-probe.js` | 53 979 | `3A48718C79FA` | — | n/a (no flag) | rc=0 `RESULT: GREEN — 82/82 arm(s)` | n/a |
| `_main/app-target-oracle.py` | 26 957 | `F7B3E9C65965` | `--neg-arm` | yes | rc=0 `VERDICT: PASS live=GREEN(9/9) M1 env line removed=RED-as-expected M2 tree-root rule removed=RED-as-expected`; `--neg-arm` rc=0, 94 lines vs 106 (live arms skipped) and the verdict line drops `live=GREEN(9/9)` — honest | YES (live) |
| `_main/emit-queue-bound-oracle.py` | 7 443 | `485549586646` | `--neg-arm` | yes | rc=0 `VERDICT: PASS`; `--neg-arm` rc=0 `mutant: …_emit-neg-shell.py (430833 B, guard replaced by pass)` / `NEG-ARM: RED as expected`; mutant self-deletes (measured: no leftover in `app/webview/`) | YES (live) |
| `_main/per-app-source-plumbing-oracle.py` | 12 997 | `72B46E413AF3` | `--neg-arm` | yes | rc=0 `VERDICT: PASS`; `--neg-arm` rc=0 `NEG-ARM: PASS -- both mutants RED` (incl. the `ctypes` NameError reproduction) | YES (live) |
| `_main/word-split-oracle.py` | 16 018 | `5C8695C39F1A` | `--neg-arm` | yes | rc=0 `12 PASS / 0 FAIL (12 arms) VERDICT: PASS`; `--neg-arm` rc=0 `NEG-ARM: 7 FIX arm(s) went RED as required, 0 stayed green, 0 control arm(s) broke` | YES (live) |
| `_main/redux-flag-gate.py` | 23 337 | `FCF83A05ED2A` | `--neg-arm` | yes | rc=0 `GATE-VERDICT: GREEN — all 13 claims hold as shipped`; `--neg-arm` rc=0 `NEG-VERDICT: GREEN — all 12 mutants moved exactly their own claim` | YES (live) |
| `_main/wasapi-com-init-oracle.py` | 12 967 | `81872CEE56F1` | `--neg-arm` | yes | rc=0 `LIVE: PASS` `NEGARM: PASS (pre-fix copy RED on 3 arm(s))` `VERDICT PASS`; `--neg-arm` rc=0 same | YES (live) |
| `_main/caption-lines-oracle.py` | 11 248 | `BF5C48B68919` | (control arm: "must differ") | yes | rc=0 `12 PASS / 0 FAIL (12 arms)` | YES |
| `_main/skin-strip-gate.py` | 4 642 | `4EA146CE4B77` | `--neg` | yes | rc=0 `VERDICT: GREEN - the strip keeps its slab and its captions with a skin recorded`; `--neg` rc=0 `OFFENDERS=3` `RED AS EXPECTED=True -> the strip would be white again` | YES (live) |
| `_main/render-protection-gate.py` | 6 300 | `2F35A583E366` | `--neg` | yes | rc=0 `LAYERS=2/2` `VERDICT: GREEN - two independent background layers…`; `--neg` rc=0 `LAYERS=1/2` `RED AS EXPECTED=True -> body is a hole again` | YES (live) |
| `_main/verdict-gate.py` | 27 898 | `0C144A42B22C` | `--control-unguard-captions-zero` | yes | rc=0 `RESULT (worker/sotto_worker.py (as shipped)): GREEN - 14/14 arm(s)`; control rc=0 `CONTROL PASS - arm (b) fails on the copy exactly as it should` | YES (live) |
| `_main/config-keys-oracle.py` | 6 334 | `73F7F0F11022` | — | n/a | rc=0 `VERDICT: PASS` | n/a |
| `_main/audio-source-probe.py` | 24 089 | `2F930BFE36D6` | `--neg-arm-iid`, `--neg-arm-floor` | **static only** | `--selftest` rc=0 `SELFTEST-VERDICT: GREEN  (10/10 PASS)`; the two flags ARE read (`:549` sets `args.meter_iid`, `:551` sets `args.floor`) — parsed-and-used, **not inert** | flags live by static read; neg colour NOT exercised (drives a device probe) |
| `_main/join-harness.js` | 10 472 | `3B4C96CE7F45` | — | **YES — it says NO today** | rc=1 `REAL JOIN-HARNESS: 6 FAILED  impl=H:\sotto\app\panel\caption-formulation.js` | see OPEN gap **C** |
| `_main/_design-lane/assert-themes-neg.js` | 3 967 | `3B3323E48D1A` | (is the negative control) | **YES — 5/5 mutants RED naming their own file+reason** | rc=1: `unscoped-selector`, `foreign-theme-scope`, `at-import`, `remote-url`, `undeclared-token` all `ok`; `pristine-copy want=GREEN got=RED  VERDICT FAIL` | see OPEN gap **B/D** |

---

## 4. UNRUN-BY-ORDER — instruments that LAUNCH the app/worker/electron (never executed here)

The owner's order forbids opening the app. Each row below was classified by reading the launch site in
the file (line measured in this pass). None of these was run; each is an **OPEN gap**, not a pass.

| instrument | bytes | sha256(12) | measured launch evidence |
|---|---|---|---|
| `_main/_cap2panel-probe.py` | 10 997 | — | `subprocess.Popen(cmd, cwd=os.path.dirname(SHELL), …)` :106; SHELL = the shell |
| `_main/_panel-chrome-arm.py` | 40 078 | `3D9D9EB7BE2E` | `subprocess.run(cmd, capture_output=True, …)` :264 (drives the panel) |
| `_main/_panel-geometry-arm.py` | 30 981 | `3CF74A639933` | `subprocess.Popen(cmd, stdout=…DEVNULL, stderr=errlog)` :259 |
| `_main/_theme-probe-arm.py` | 30 488 | `2F0564E03841` | `subprocess.run(cmd, capture_output=True, timeout=180)` :196 |
| `_main/_strip-reload-probe.py` | 42 823 | — | drives the LIVE worker ("held every edit to `worker/sotto_worker.py` waiting for `is_capturing()`") :6 |
| `_main/_strip-surface-oracle.py` | 37 185 | `B6AEB57A04CB` | writes `app/webview/_strip-mutant_sotto_webview.py` (outside `_main/`) |
| `_main/delivery-rate-oracle.py` | 20 080 | `FF97EB48DD46` | `subprocess.Popen(` :131; subject = the live worker :1 |
| `_main/device-silence-oracle.py` | 8 555 | — | `subprocess.Popen(` :66; `WORKER = …/worker/sotto_worker.py` :36 |
| `_main/denoise-file-ab.py` | 21 080 | `08C12C4ECDB9` | `subprocess.Popen(` :113; runs the worker `--selftest` :27 |
| `_main/e2e-redux-shell-arm.py` | 13 320 | `5E981228B087` | `subprocess.run(` :110; "the REAL app (`run.cmd`)" :1 |
| `_main/no-audio-latch-oracle.py` | 14 351 | `330583932E4B` | `ROOT,'app','webview','sotto_webview.py'` :57 (needs the shell) |
| `_main/panel-exit3-oracle.py` | 53 743 | `6491B1A1092B` | `subprocess.Popen(` :166; `--arm-e-real` pastes the REAL WebView2 DOM |
| `_main/panel-hidden-at-startup-oracle.py` | 40 301 | — | `DEFAULT_SHELL = …/sotto_webview.py` :87 |
| `_main/panel-paint-probe.py` | 11 284 | `7B23E4D63DBD` | `subprocess.Popen(args, …)` :188; `SHELL = …/sotto_webview.py` :37 |
| `_main/redux-live-window-census.py` | 11 204 | `3CE1C931515A` | `subprocess.run(["pwsh","-NoProfile","-Command",script])` :121 (script body not inspected) |
| `_main/revive-pipeline-oracle.py` | 27 354 | `422F8FA21536` | `subprocess.Popen(` :161; shell ref :55 |
| `_main/run-cmd-exit-oracle.py` | 53 411 | `E86EAA9A7AC8` | launches `app/webview/run.cmd` (docstring :1, `subprocess.run` :264) |
| `_main/verdict-order-oracle.py` | 14 011 | — | `subprocess.Popen(` :151; subject = `worker/sotto_worker.py` :1 |
| `_main/audio_battery.ps1` | 15 137 | — | `$psi.UseShellExecute` :132; `-Worker …sotto_worker.py` :23 |
| `_main/_skin-lane/oracle.js` | 18 145 | `BB97E0EF3C84` | `H:/sotto/app/node_modules/electron/dist/electron.exe _main/_skin-lane/oracle…` :3 |
| `_main/_restart-30s-prefix-mutant.py` | 330 301 | `5660A8F03F47` | `subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)` :4119; worker ref :66 |
| `_main/_tap-restart-prefix-mutant.py` | 406 226 | `A35C361E293D` | a mutant COPY of the shell (spawns it) |
| `_main/make-no-icon-negarm.py` | 2 524 | `B5EEC356E1AB` | `Writes app/webview/_negarm_sotto_webview.py` :10 — writes OUTSIDE `_main/` |
| `_main/_audit-verify-all.cmd` | 32 203 | `EBF715E9E4CF` | launches the shell dozens of times (named in the owner's order) |

---

## 5. Remaining candidates present in `_main/` and NOT exercised in this pass

Measured in the census (bytes + sha256 recomputed); `word-only` = the file contains the vocabulary
("control", "must go RED") without a flag that changes what is measured. **None of these is a pass.**

| file | bytes | sha256(12) | why not exercised |
|---|---|---|---|
| `_main/alt-c-e2e-probe.py` | 11 990 | `058525FD46B6` | word-only; refs the shell |
| `_main/audio-tab-audible-probe.py` | 6 260 | `B646598BDF40` | word-only |
| `_main/benign-status-arm-oracle.py` | 5 429 | `C7C6A6AB5AF8` | word-only; refs the worker |
| `_main/canonical-producer-oracle.py` | 37 969 | `3EE12D05CCF3` | `subprocess.run(` :161 NOT inspected; ARM B imports the real worker in-process :18 |
| `_main/control/caption-formulation-pre.js` | 4 210 | `719A68F7B9FC` | word-only fixture |
| `_main/crash_probe.ps1` | 16 938 | `FF368D63C4B4` | spawns; not inspected |
| `_main/denoise-frozen/off/denoise.py` | 27 001 | `38CDE013B0FE` | frozen copy (identical bytes to the "on" copy) |
| `_main/denoise-frozen/on/denoise.py` | 27 001 | `38CDE013B0FE` | frozen copy |
| `_main/dispatch-guard/scripts/check-dispatch-role.mjs` | 28 441 | `4CBED65B9F1A` | `--mutant`; not run |
| `_main/dispatch-guard/scripts/selftest-dispatch-role.mjs` | 16 005 | `992CABF25025` | spawns node children only (safe) — not run |
| `_main/dispatch-guard/selftest-declarative.mjs` | 16 001 | `225B25C3ACA4` | spawns node children only (safe) — not run |
| `_main/dr-ring-probe.py` | 2 546 | `0E2475345A33` | `--mutant`; not run |
| `_main/e2e_probe.ps1` | 10 814 | `359ACE51B82F` | spawns; not inspected |
| `_main/live-seam-probe.py` | 3 539 | `4B81499760C9` | `--neg-arm`; no spawn found, not run (time) |
| `_main/panel-state-guard-gate.js` | 13 007 | `101737AC730D` | word-only |
| `_main/process-loopback-probe.py` | 74 889 | `CA97269BA28F` | spawns + opens a device |
| `_main/quarantine-index-collision-20260707/selftest.py` | 42 745 | `E2F5B91A96FB` | spawns (python children); not run |
| `_main/redux-gemm8-probe.py` | 19 168 | `968B2ACFF98F` | `--neg-arm`; heavy model load |
| `_main/restart-30s-oracle.py` | 23 630 | `8AA8F0EC8C3E` | word-only; refs the worker |
| `_main/speech-gate-oracle.py` | 4 469 | `0CC16D7F29F5` | word-only |
| `_main/tap-restart-loop-oracle.py` | 16 786 | `63BD0E8AAF72` | word-only; refs the worker |
| `_main/tap-stall-watchdog-oracle.py` | 12 733 | `E16D0EE634E6` | word-only; refs the worker |
| `_main/thresh/denoise.py` | 27 615 | `3AA1BB64463D` | word-only |
| `_main/_audit-worker-start-wiring.py` | 5 961 | `135D6245EB51` | word-only; refs the worker |
| `_main/_diar-cuda-cache-probe.ps1` | 4 277 | `B50D545887D5` | word-only |
| `_main/_diar-gpu-watch.ps1` | 4 118 | `2F9A8AC9B644` | word-only; spawns |
| `_main/_diar-provider-probe.py` | 6 157 | `311CE8174B88` | word-only |
| `_main/_focus-window-census.py` | 4 905 | `F74EA507740C` | `--control-pid`; not run |
| `_main/_skip-verdict-guard.py` | 7 631 | `2655BE17999B` | `--control-only`; not run |
| `_main/_theme-probe.js` | 27 530 | `553F880444EA` | word-only; refs the shell |
| `_main/_tmp-panel-noreveal/history-gallery.js` | 7 638 | `6D31DF82926A` | `--neg-arm` in a scratch copy; not run |

The census population was `_main/**/*.{js,mjs,cjs,py,ps1,cmd,bat,html}` (skipping `node_modules`, `.git`,
`__pycache__`, model/venv/log dirs) = **73 files** matching the control vocabulary, of which **24 were
exercised or repaired** (§3) and **24 are UNRUN-BY-ORDER** (§4); the 31 above are the remainder. Logs,
`.json`, `.png` and `.wav` files are not instruments and were not counted.

---

## 6. OPEN gaps (named, not faked)

**A. The panel's WAVE has no producer in the shipped worker — and `--meter-hz` is INERT.**
Measured in this pass on `worker/sotto_worker.py` (**291 873 B** — re-measured; the sha256 prefix
`EFDFB098…` is the pin `AGENTS.md` carries for this revision, and the line numbers below are the
ones I read on it, treated as HINTS per that file's own rule 2): `class AudioMeter` at `:1341` with
`def __init__(self, hz=METER_HZ, now=0.0)` at `:1349`; the class is **never instantiated** anywhere
in `worker/` or `app/`; `def on_block` (`:4527`) has **no meter branch** and never emits
`type="meter"`; the only `meter` string in the file is a comment at `:1322`; and `--meter-hz` is
declared at `:3922-3927` (`default=METER_HZ`) with **`args.meter_hz` read nowhere** (`grep
args\.meter` = 0 matches). Consequence: the panel's `pushLevel(fields.peak, fields.blocks)`
(`panel.js:1709`) can never receive a datum, and the argparse comment promising "not one branch of
`on_block`'s meter block is taken" names a block that does not exist. The repaired oracle measures the
class itself and goes RED on cadence (9.9 Hz for 100 ms blocks; 4.95 Hz at 99 ms pacing). **The repair
belongs to `worker/**`, which this lane may not touch → OPEN.** Not measured (order): what the real
app paints.

**B. `app/panel/themes/theme-{1..5}.css` violate their own contract — 4 unscoped selectors each + 2 dead tokens.**
Measured: `:576-577` of each file carries a comma list where only the first member of each group is
scoped (`.panel__header *`, `.status`, `.status *`, `.chrome *` unscoped) → the same 4 rules exist
in all five themes and the last stylesheet loaded wins. And `theme-3.css:607`
`font-family: var(--font-serif)` consumes a token declared **nowhere under `app/`** (measured: 0
declarations of `--font-serif` or `--w-op` in every `.css`/`.html`/`.js` under `app/`) with
**no fallback** → the declaration is invalid at computed-value time; `:656`/`:665`
`opacity: var(--w-op, 1)` degrades to 1. **Out of repair scope (`app/**`) → OPEN.**

**C. `_main/join-harness.js` says NO against the shipped `app/panel/caption-formulation.js` — and it is right to.**
Measured rc=1: `REAL JOIN-HARNESS: 6 FAILED  impl=H:\sotto\app\panel\caption-formulation.js`. The six
failing arms read the PROVISIONAL path and receive word OBJECTS where the harness expects a joined string —
`arm3` got `[{"w":"this","a":0,"b":0.56}]` want `"this is"`; `arm7` got
`[{"w":"going","a":0,"b":0.56},{"w":"along","a":0.56,"b":1.12}]` want `"going along slush"`. The
COMMITTED-path arms in the same run all PASS (arm5, arm6, arm8, arm9, arm10, including `the committed
line has no garbage` = `"Going along slushy country."`). So this is an API-shape drift on the
provisional path — **whether the stale expectation is the harness's or the module's was NOT determined
here.** The instrument CAN say NO (rc=1, named arms) → it is not a dead control. **OPEN.**

**D. `_main/_design-lane/assert-themes-neg.js` is a LIVE control whose baseline is RED.**
5/5 mutants go RED naming their own file and reason; the `pristine-copy` arm is RED because the shipped
themes really do violate the contract (gap B). A control whose baseline is red cannot separate "the mutant
moved it" from "it was already red" — the harness says so itself (`NEG-ARM VERDICT FAIL — 1 arm(s) did
not behave`). **Do not "fix" this by making the pristine arm accept RED; the fix is gap B.**

**E. `_main/audio-source-probe.py` neg colours not exercised.** `--neg-arm-iid` (`:549`) and
`--neg-arm-floor` (`:551`) are parsed-and-USED (they set `args.meter_iid` / `args.floor`) — NOT
inert by static read — but the flags drive a device probe and their RED/GREEN colours were not measured here.

**F. `_main/redux-live-window-census.py`** runs a `pwsh -Command` script built in-file (`:121`) whose
body was not inspected; it is classified UNRUN for that reason, not because a launch was proven.

---

## 7. What this pass does NOT prove

* Nothing here proves what the real WebView2 panel paints, nor that any live caption reaches it — the
  owner's order suspends every shell measurement. Every "GREEN" above is a claim about bytes and logic.
* The 31 candidates in §5 were measured for size/hash and vocabulary only; their controls were NOT
  exercised. They are OPEN, not passing.
* The two repaired instruments are repaired **as instruments**: `audio-meter-oracle` now reports a true
  NO about the shipped worker (gap A) and `theme-assert-lib` now reports a true NO about the shipped
  themes (gap B). Neither repair changes any file outside `_main/`, and neither was used to make a
  verdict pass.

**Files touched by this lane (2, both under `_main/`):**

| file | bytes before → after | sha256 before → after |
|---|---|---|
| `_main/audio-meter-oracle.py` | 16 744 → **18 330** | `0F1D6E9E…67F2` → `72942D49…644A` |
| `_main/_design-lane/theme-assert-lib.js` | 4 154 → **5 110** | `C7703B53…A768` → `EE495AEB…BFD2` |

**Deliverable:** this file, `_main/receipt-20261011-dead-controls.md`, the only file CREATED by this lane.
No `.cmd` was edited, no `app/**` or `worker/**` file was edited, no git write command was run,
nothing was launched, no process was killed.




