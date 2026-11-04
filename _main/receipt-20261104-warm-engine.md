# Warm engine — what was implemented, what was measured, what was NOT

**Lane:** `WarmEngineImpl-2`, worktree `H:/sotto-wt/WarmEngineImpl-2` (branch `lane/warm-engine-impl-2`).
**Design of record:** `state/design/warm-worker-20261104.md` (read in full before writing code).
**Date:** 2026-11-04.

Every number below carries the command that produced it. Anything without a command is marked
`[INFERENCE]` and is not a result.

---

## 1. What was implemented

| file | what it is |
|---|---|
| `app/webview/warm_pipe.py` | the Win32 primitives both halves share: pipe/mutex **names** (`<prefix><session>.<model_key>`, model key = basename + first 12 hex of `genai_config.json`), `owner_sddl()` from the token's SID, `create_first_instance()` (`FILE_FLAG_FIRST_PIPE_INSTANCE`), `create_mutex()`, `open_client()`, `connect`/`disconnect`, `cancel_sync_io()`, and `PipeConn` (`send`, `readline(deadline)`, `recv`). No process is started, no device opened, no window touched. |
| `app/webview/warm_engine.py` | the engine process: `WorkerGraphLoader` (loads the nemotron graph OUTSIDE the shell), `WarmEngine` (the four twin locks, the pipe server, the line protocol, the load gate, the park/release timer), `AttachedSession` (decode loop, tap, replay), `Sender` (bounded queue: meters drop, captions drop first), `PcmRing` (8 s), `replay_is_history()` (the single definition of the 2 000 ms line). `--no-model` is the instrument switch: it skips the LOAD only. |
| `app/webview/sotto_webview.py` | `WarmPipeBridge(WorkerBridge)` assigned to `self.bridge` in `_try_warm_attach`, so every existing `self.bridge is not None` guard IS the twin-load gate; `_WarmChild` (pid-only proxy: `kill()` refuses — the shell does not own the engine); `_PipeLineStream` feeding the existing `WorkerBridge._pump`; `WARM_ATTACHED` / `WARM_ATTACH_FAILED` / `WARM_FALLBACK_COLD` log lines; replay lines stamped `src=warm-replay` and > 2 000 ms routed to history-only (`WARM_REPLAY_HISTORY_ONLY`). Cold ladder untouched: `WarmPipeBridge.attach()` returns `(None, reason)` and the caller falls through to today's code. |
| `_main/warm-engine/warm-engine-task.xml` + `warm-engine-run.cmd` | the Task Scheduler action: `IgnoreNew`, `Hidden`, `ExecutionTimeLimit PT0S`, `RestartOnFailure Count=2`, **no triggers** (R4), `pythonw` via a `.cmd` so the engine has no console. |
| `_main/warm-engine-oracle.py` | 22 arms + `--neg-arm` (6 mutants), headless, `CREATE_NO_WINDOW` on every spawn, per-arm 60 s deadline so a wedged arm dies instead of wedging the battery. |
| `_main/_audit-verify-all.cmd` | the pair `warm-engine` + `red-as-expected-warm-engine` (`call :step always` / `call :record` / `call :expectred`, phrase `NEG-ARM PASS`). |
| `AGENTS.md` | both pins re-measured: `run.cmd --help` = 8544 B / 131 lines / 131 CRLF (the two new flags print in the help) and the battery = 210969 B / 2626 CRLF / sha256 `8D03D133…E2CC`. |

**The gate (G1–G4).** `load_gate()` reads `LoadProbe.reread()` (measured commit + CPU) and the published
`shed` file, **takes the worse**, and returns `allowed` only for `measured and worst == "leve"`.
`unknown` is `allowed: False` with `why=no-measurement`. G2 refuses to open the tap under the same gate;
G3 re-reads the gate at attach time and answers `WARM_ATTACHED mode=shed` (the shell then takes the batch
path); G4 releases the weights after 120 s of `muito-alta`. There is no `force` parameter, no env var and
no flag: `arm 20 no-bypass` asserts their absence by name, and asserts the XML truths (`IgnoreNew`,
`PT0S`, no triggers, restart ≤ 2).

---

## 2. Acceptance rows

Commands are run from the worktree root with `TMPDIR=I:\cc-tmp`.

`python _main/warm-engine-oracle.py` → **rc 0**, `WARM-ENGINE VERDICT: PASS -- 22 arm(s), 0 red`,
`warm engine pid file: none`.
`python _main/warm-engine-oracle.py --neg-arm` → **rc 1** (by design), `NEG-ARM PASS -- 6/6 mutant(s)
caught`, each mutant caught by the arm that names it:

```
MUTANT M1-gate-bypass         CAUGHT by g1-unknown-defers, g1-engine-defer-log
MUTANT M2-unknown-allows      CAUGHT by g1-alta-refuses, g1-unknown-defers, g1-engine-defer-log
MUTANT M3-ring-oldest-first   CAUGHT by ring-newest-first
MUTANT M4-mutex-twin          CAUGHT by twin-mutex
MUTANT M5-replay-2000         CAUGHT by replay-boundary
MUTANT M6-detach-quits        CAUGHT by attach-handshake, stop-detaches-not-kills, attach-20
```

| # | row | measurement | result |
|---|---|---|---|
| A1 | shell-up → first caption, audio playing (≤ 3 000 ms) | `_main/time-to-first-caption-oracle.py` (needs a live app + audio) | **UNMEASURED** — see §3 |
| A2 | same, mode B (≤ 6 000 ms) | same | **UNMEASURED** — see §3 |
| A3 | cold floor (≤ 13 000 ms, no regression) | same | **UNMEASURED** — see §3 |
| A4 | attach handshake p50 ≤ 300 ms, p95 ≤ 500 ms, 0 timeouts / 20 | arm 21 `attach-20` (20 real pipe handshakes, one engine, one load) | **PASS** — `attach-20: p50=0.0 ms p95=16.0 ms max=16.0 ms n=20`, `0 timeouts`, `ONE load across 20 attaches` |
| A5 | zero cold loads once attach succeeded | arm 15 `single-loader` (shell path: `start_worker` with an engine present) | **PASS** — no cold `WorkerBridge` constructed, `_spawn` never ran |
| A6 | twin engine impossible | arms 13 `twin-pipe` (two processes, one pipe name, different mutexes) and 14 `twin-mutex` (pre-held mutex) | **PASS** — the twin exits rc 0 with `WARM_TWIN_EXIT rc=0 why=pipe-exists` / `why=mutex-exists`, the first still answers |
| A7 | no double load | arm 15 (second `start_worker` refuses on `self.bridge`), arm 21 (`ONE WARM_LOAD_BEGIN`) | **PASS** |
| A8 | the gate has a veto | arms 01–08 (`g1-alta-refuses`, `g1-unknown-defers`, `worst-of-two`, `g1-loads-on-leve`, `g1-engine-defer-log`, `g2-tap-refused`, `g3-attach-shed`, `g4-release`) | **PASS** — 0 loads at `alta`, `unknown` never loads, `WARM_ATTACHED mode=shed` on a rising level, `WARM_RELEASE` after 120 s of `muito-alta` |
| A9 | one WASAPI client, no rotation | `_main/tap-silent-desktop-oracle.py` + a live engine log | **UNMEASURED** — the tap is refused on this box by design (no device is opened by any arm) |
| A10 | no window, ever | `_main/console-window-audit.py`, `owner-screen-gate.py`, `lane-screen-gate.py` | **PARTIAL** — nothing in this lane launched a window (no `WebView2`, no `pythonw` spawn, every subprocess uses `CREATE_NO_WINDOW`); the screen gates themselves were **not** run here |
| A11 | no stray process after the shell dies; TTL releases the engine | arm 19 `pid-identity` (pid + start time written, file removed on exit), arm 22 `ttl-exit` (`WARM_EXIT why=idle-expired` past the TTL) | **PASS** for the engine half; the "kill the shell, census its children" half is **UNMEASURED** (needs a live shell) |
| A12 | a crash is not a loop | arm 20 `no-bypass` (XML: `RestartOnFailure` `<Count>2</Count>`, `MultipleInstancesPolicy IgnoreNew`, `ExecutionTimeLimit PT0S`, no triggers) | **PASS** as a property of the registered task XML; a real crash loop was **not** executed |
| A13 | residency ≤ 2 100 MB parked, ≤ 0.5 % CPU idle | per-pid RSS over a live engine | **UNMEASURED** — no live model was loaded in this lane (the arms use a 12.5 ms fake graph; that number says nothing about 1.9 GB) |
| A14 | the engine is not stale | arm 12 `stale-sha-refused`: attach with `expect_sha256=deadbeef` | **PASS** (engine side) — `WARM_HELLO_REFUSED why=stale-code`, engine quits, no session. The shell-side freshness oracle was not extended. |
| A15 | the channel does not stall the audio loop | arm 18 `sender-never-blocks`: 400 meters + 400 captions through a 50 ms `send`, queue capacity 16 | **PASS** — all 800 `put`s returned in < 2 s (no call blocks), `WARM_SEND_DROPPED` / `WARM_SEND_OVERFLOW` grew and `overflow` is set |
| A16 | replay never paints stale audio | arm 10 `replay-boundary` + the shell's `replay_is_history()` choke point | **PASS** as classification (2 000 ms is live, 2 001 ms is history-only, `None` is history); no line with `src=warm-replay` and `audio_ms > 2000` can be painted, but that paint counter was **not** observed live |

---

## 3. What stays UNMEASURED (and is not reported green)

1. **A1/A2/A3 — the 3 s first caption.** Needs a live shell with audio already playing and the engine
   registered. This lane may not launch the app on the owner's screen (`AGENTS.md`), so the three
   latency rows are untouched. The design's own floors (2 981 ms line-close, 4.5–6 s graph load) remain
   the only numbers.
2. **A9 — one WASAPI client.** No endpoint was opened by any arm (by acceptance). The tap path is
   implemented (`WarmTap`), and its refusal path is measured (arm 06), but its behaviour against a real
   device is not.
3. **A10 — window census.** Nothing here launched a window; the audit/watch/screen gates were not run.
4. **A11 (shell half) / A12 (real crash loop).** The process-level guarantees were measured through the
   engine and the XML; a live shell kill and a live crash loop were not.
5. **A13 — residency and idle CPU of the real graph.** Not measured; no model was loaded.
6. **Task registration.** `schtasks /create /xml _main/warm-engine/warm-engine-task.xml` was **not** run:
   registering a task on the owner's machine is outside this lane. The XML is the artefact; the engine is
   started by `schtasks /run \SottoWarmEngine` and by nothing else (R1, `--no-model` exists so the oracle
   never needs the task).
7. **The pipe across integrity levels (F11).** Not exercised; `owner_sddl()` pins the DACL to the token's
   SID, but an unelevated shell attaching to an elevated engine was not measured.

---

## 4. Defects the oracle found in MY OWN code (each now fixed and pinned by an arm)

These are the reason the arm table is worth more than the verdict:

1. **ctypes HANDLE truncation** (`warm_pipe`): with no `argtypes`/`restype`, a REFUSED
   `CreateNamedPipeW` came back as `-1`, which is not `INVALID_HANDLE_VALUE`
   (`0xFFFFFFFFFFFFFFFF`) and was read as a valid handle — two engines on ONE pipe name both logged
   `WARM_PIPE_READY`. Caught by arm 13. Fixed by `_declare()` with prototypes.
2. **`CloseHandle` on a pipe with a pending `ConnectNamedPipe` blocks** — the engine hung in shutdown and
   left its own pid file on disk. Caught by arm 19. Fixed by `cancel_sync_io()` + join before close.
3. **The last envelope was lost on quit** — a `WARM_HELLO_REFUSED` queued a microsecond before `quit` never
   reached the shell, which then logged `pipe-timeout` (a lie about the reason). Fixed by
   `Sender.flush()` before close.
4. **`self.tap.source` after a concurrent detach** — `AttributeError` inside `_open_tap` (M6 neg-arm).
   Fixed by holding the tap in a local.
5. **A wrong test read as a red product**: arm 07 read `[]` from a `FakeConn` the engine never had, and
   called it "the engine did not answer" while the engine had answered into `_conn`. Fixed with a fake
   client wired through `_raw_send`.

---

## 5. Battery

```
python _main/agents-md-pins-oracle.py   -> AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
python _main/battery-wiring-oracle.py   -> BATTERY-VERDICT battery-wiring PASS checks=7 fail=0
                                           (new-unwired PASS: nenhum oraculo novo sem passo)
```

The pair in `_main/_audit-verify-all.cmd` (lines 2226–2234) is `call :step always warm-engine` +
`call :record` and `call :step always red-as-expected-warm-engine … --neg-arm` + `call :expectred …
"NEG-ARM PASS"`. The battery itself was **not** run end-to-end here (it is the main seat's gate and it
runs every step); only the two oracles that police it were.

**Verdict of this lane:** the warm engine exists, the four twin locks and the four-point veto are
measured against mutants, and the shell's cold path is provably untouched when no engine answers (arm 16:
`WARM_FALLBACK_COLD reason=absent`, exactly one cold `WorkerBridge`, `_spawn` once). The three
**owner-facing latency rows (A1–A3) are still UNMEASURED** — they need a live run and this lane may not
put a window on the owner's screen.
