# Receipt 2026-10-12 — continuation: doc pins become a gate, and two stale citations fixed

Owner instruction for this round, verbatim: *"continua, disco ta menos cheio."* The previous objective
(goal `goal-edd0a2ee…`) was already complete at exit 0; this round is follow-on work with NO launch,
per the standing stop order.

## What was stale, measured, and fixed

1. **`AGENTS.md` pinned the wrong `run.cmd --help` size.** The file said "(measured: 2272 B, rc 0, BOTH
   sides)" with no date. Re-measured 2026-10-12: **4872 B, 78 lines, 78 CRLF / 0 bare LF, rc 0,
   sha256 `3EB553400B3A5AAF9EDA65D5AE894DA0C7B4F35D99250F1BBADEF9197D6B1744`** (instrument: the wrapper
   itself, output to a file, then bytes/lines/CRLF/hash). The TEXT grew because flags were added --
   which is why the number must carry its date (the file own rules 1 and 2). The sentence asserts a
   COMPARISON (the pre-flight does not change the output); that claim is untouched, only the size is
   now dated and current.
2. **The shell own `stats()` docstring cited two stale lines.** `sotto_webview.py` said "`panel.js:1702-1710`
   reads `peak` and `blocks`; `panel.js:1738-1740` (the behind chip) reads `queue_drops` and `rate`".
   Measured today: the level consumer is `pushLevel(peak, blocks)` at **`panel.js:2564`** (`LEVEL.blocks`
   at `:2584`), the behind chip reads `queue_drops`/`rate` at **`:2688-2689`** and paints at **`:2700`**
   (declared `:2539`), and `:1738-1740` is `wireSurfaces()` -- not a chip at all. The docstring also said
   "the payload is exactly `{peak, blocks}`", which stopped being true when the shell began stamping
   `tag` on purpose (`:5941` worker tick, `:5927` meter path) -- an idle shell answers `{tag: stats}`,
   never `{}`. Both corrected in place, with the reason and the date. Shell after: **450292 B, 8845 CRLF,
   0 bare LF**, `py_compile` rc=0.

## The numbers are now a GATE, not prose

`_main/agents-md-pins-oracle.py` (NEW) re-measures both pins from the live bytes on every run:
`run.cmd --help` (bytes/lines/CRLF/bare-LF/rc/sha) and `_main/_audit-verify-all.cmd`
(bytes/CRLF/bare-LF/sha), then requires AGENTS.md to carry those exact tokens in a window around the
relevant sentence -- scanning EVERY occurrence of the battery name, because the first version anchored
on the owner-order mention at the top of the file and reported both tokens missing.

It immediately caught a stale pin **I had created myself in the same session**: editing the battery
(one `REM` line + the autostart step) took it from 32203 B to **32637 B, sha
`035CD13288966F5265CB0126F2544CE9D56099E1EA90466911D506E3BD9CA6AB`**, while the corrections table still
quoted the old size. AGENTS.md now carries the re-measurement and names the gate.

Both colours, measured:

```
py -3 _main/agents-md-pins-oracle.py             -> AGENTS-PINS PASS,  VERDICT: PASS, rc=0
py -3 _main/agents-md-pins-oracle.py --neg-arm   -> AGENTS-PINS CONTROL PASS, rc=0 (1 failure on the
                                                    mutated copy: the gate can say NO)
```

The control own first version was INVALID and said so: its mutation regex matched nothing (the shipped
sentence bolds from "the SIZE here was stale" onwards, so the bolded-digit pattern never matched) and it
printed `CONTROL FAIL -- the gate cannot say NO` instead of passing quietly. Fixed to mutate the real
text and to return rc=5 when the mutation anchor disappears.

## Battery

`_main/instruments-battery.mjs` now runs **77** entries (was 75): the new gate and its control. Measured
after the change: **77/77 rc=0, failed=0**. Its `launches=0` line was made precise: the one `run.cmd`
invocation in the list is the `--help` pre-flight, which argparse answers and exits -- measured after
four such invocations: **0 python processes left behind**. Nothing was launched; no window was opened.

## Disk (the owner mentioned it)

* My own footprint, measured and removed: 30 temp files in `I:\cc-tmp` (0.161 MB) and the 12 generated
  mutant copies in `_main/_redux-gate-mutants` (3.82 MB, rebuilt by every `--neg-arm` run). Kept: my
  `proc-check2.ps1`, and other lanes evidence (`wv-cleanup.txt`, `clean-dump.log`).
* **NOT touched, and reported instead:** `I:\cc-tmp` holds **21.7 GB** of `.sqlite` files dated
  2026-10-07 from another tool -- `runtime-state.sqlite` (3230 MB), `rs-liveness.sqlite` (3224 MB),
  `runtime-state-copy.sqlite` (3206 MB), six `scratch.sqlite` (297 MB each), `index-211200.sqlite`
  (143 MB), `snap2.sqlite` (125 MB). They are neither mine nor Sotto, so deleting them is the owner
  call, not mine.
* Free space right now: C: 27.3 GB, G: 9.6 GB, H: 35.6 GB, I: 96.4 GB.

## Honesty notes

Nothing in this round launched the app, the shell, the worker or `run.cmd` as an app. The only wrapper
invocation was `--help` (the documented safe pre-flight), and the process check after it is the evidence.
The shell edit is a COMMENT-only change, gated by `py_compile` plus the two oracles that read those
payload shapes (`_strip-surface-oracle.py` 109 arms rc=0, `rtf-cpu-attribution-oracle.py` rc=0, its arm 4
now reporting `shell claims panel.js:1738-1740=false`). Row #19 stays OPEN: naming its remaining cause
still needs a relaunch, which the owner order forbids.
