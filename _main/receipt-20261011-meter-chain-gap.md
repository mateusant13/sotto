# The wave has no producer: the worker never emits what the shell and the panel are built to receive (2026-10-11)

Found by the dead-control sweep as finding A ("inert meter code"), re-measured by me, and it is
bigger than an inert flag: **it is the owner-reported wave defect, still live.** The chain is built
at both ends and broken in the middle.

## The three links, measured on the live bytes (nothing launched)

**Panel — BUILT.** `app/panel/panel.js:2560 pushLevel(peak, blocks)`, a ring buffer at `:607-612`,
bars written at `:2607` from `LEVEL.hist`; `wireLevel()` at `:2619` subscribes and calls
`pushLevel(fields.peak, fields.blocks)` at **`:2633`**. Its own comment at `:2611-2614` says the
shell "exposes neither `onStats` nor `getStats`, so this returns immediately and the bars stay at
the floor. The day it lands, the wave fills by itself." — **that comment is STALE**: the shell
exposes BOTH.

**Shell — BUILT, and it names the owner's complaint.** `app/webview/sotto_webview.py:2593
`onStats: function (cb) { return subscribe('stats', cb); }`, `:2633 getStats: function () {`, the
meter branch at **`:7467 elif kind == 'meter':`**, `METER_FRESH_S = 2.0` at `:664`, and the docstring
at `:657-663`: *"`worker/sotto_worker.py:3591` emits `{\"type\":\"meter\",\"peak\":…,\"blocks\":…}`
once per meter window (10 Hz by default) … A wave drawn from a running maximum is a staircase that
only rises and then flattens — that IS the defect the owner reported (\"as ondas que crescem e
diminuem nao ta funcionando\"). So a fresh meter sample WINS over the stats line."*

**Worker — NOT BUILT, and its own comment lies about it.** Case-insensitive census of
`(?i)meter` over `worker/sotto_worker.py` (295 867 B at the time of the sweep): **20 hits, every one
a class, a flag, or a comment.** `METER_HZ = 10.0` (`:1338`), `class AudioMeter:` (`:1341`),
`def __init__(self, hz=METER_HZ, now=0.0)` (`:1349`), `--meter-hz` with `default=METER_HZ`
(`:3985-3987`). There is **no instantiation of `AudioMeter` anywhere, no read of `args.meter_hz`,
no read of `SOTTO_METER_HZ` (mentioned at `:3979`, never read), and no `type="meter"` emission**.
And the comment at `:3982` claims *"not one branch of `on_block`'s meter block is taken"* —
**`on_block` has no meter block.** A comment describing code that does not exist is worse than no
comment: it is what made two earlier readers believe the wave was wired.

## Consequence

The only thing that can feed `pushLevel` today is the `WORKER_STATS` line on stderr
(`--stats-interval`, default 10 s), which carries the **running maximum of the whole run** — and
the shell's own docstring says a wave drawn from a running maximum is the defect the owner reported.
So the owner's complaint is HALF cured: the receiving logic exists, the producer does not. The panel
degrades honestly (bars at `LEVEL_FLOOR`, `body[data-level="none"]`) rather than faking a wave — the
fake wave was deleted on purpose (`panel.js:588-590`).

## Decision (owner: "toma todas as decisoes voce mesmo") — WIRE IT

The fix is one-sided: make the worker emit what both other links already parse. Deferred until
`worker/sotto_worker.py` is free — another lane is editing that exact file right now (295 867 B,
mtime 2026-10-11T22:24:41Z). Acceptance criteria for the wiring lane:

1. `AudioMeter` instantiated on the live path, `--meter-hz` / `SOTTO_METER_HZ` actually READ.
2. `{"type":"meter","peak":<window peak>,"blocks":<blocks>}` emitted on stdout once per meter
   window, shape matching what the shell's `:7467` branch consumes.
3. `--meter-hz 0` stays byte-identical: no read, no line, no branch taken (the property the
   worker's own comment already promises).
4. The cadence off-by-one the sweep measured is fixed: 100 blocks of 100 ms must produce 100
   events, and a 99 ms pace must not beat at ~6 Hz (`_main/audio-meter-oracle.py`, currently
   rc=1 with exactly those 2 arms RED).
5. No per-sample log line on the worker side; the shell already budgets its own log at 30 s
   (`METER_LOG_INTERVAL_S`) and the DATA is deliberately not throttled.
6. An in-process oracle with a `--neg-arm` that can say NO (instantiation removed -> RED).

## NOT MEASURED

- Nothing launched (owner stop order): no meter event has been observed travelling the real bridge.
- Whether the shell's `METER_FRESH_S = 2.0` preference behaves correctly against a real 10 Hz
  stream is a property of code I read, not of a run.
- The `panel.js:2611-2614` stale comment is real but harmless (the early return never fires); it is
  named here rather than fixed to avoid touching a file two other lanes are reasoning about.
