"""ORACLE for the panel's WAVE — the per-window audio level at ~10 Hz (task 2).

WHY (contract lane, `H:\\aireplay\\docs\\research\\12-audio-level-contract.md`)
-----------------------------------------------------------------------------
The datum that existed does not serve a wave:
  * `counters['peak']` is the **maximum of the RUN** and only ever rises.
    MEASURED: three consecutive WORKER_STATS ticks printed the SAME
    `peak=0.554093` while `rms` drifted 0.06100197 -> 0.06181468 — a wave drawn
    from it can only go up.
  * the published cadence is **1 point / 10 s** (`--stats-interval 10.0`), and
    the tap's own block rate is **10 Hz** (`audio.block_ms: 100`).
  * the 600 B WORKER_STATS line must NOT be lowered to 0.1 s: that is ~6 KB/s on
    the channel that also carries the captions.

WHAT THIS ORACLE PINS
---------------------
  * the level is the peak of ONE WINDOW and it FALLS when the audio falls — the
    one thing a run maximum can never do;
  * the payload DESCRIBES the blocks it actually covered (peak and count), which
    is checked against an independent tally kept by the driver;
  * the cadence, the payload shape, the payload SIZE (bytes/s on stdout) and the
    CPU cost of emitting at 10 Hz;
  * that the SHIPPED DEFAULT is ON at 10 Hz and that a default run's level really
    RISES and FALLS — the owner's report of 2026-10-08 was "a animação de áudio
    sendo capturado não tá funcionando", and the cause was this default being
    turned to 0 to quiet the shell's log: **the data was switched off to fix a
    LOG.** The limit belongs on the log side (the consumer that logs an unknown
    key per sample); `default=0` slipped back into argparse makes these arms RED
    instead of reaching the owner as a dead wave;
  * that `--meter-hz 0` is inert (not one event, not one byte) — the escape hatch
    is still one flag, and with it off not one byte reaches stdout.

THREE NEGATIVE CONTROLS, one per claim, because each can be wrong on its own:
  `--neg-arm`      `AudioMeter.reset` replaced by the shipped defect — the peak
                   is never cleared, i.e. the window accumulates into a run
                   maximum;
  `--neg-cadence`  the block-count rule removed, leaving a pure time window —
                   the 6 Hz beat;
  `--neg-default`  the shipped default flipped back to ON (10 Hz) — the state the
                   owner's decision rejected.
Every arm of the claim being falsified must go RED; the control arms must stay
GREEN.

No audio device, no model, no window: pure computation plus two measured writes.
Exit codes: 0 PASS, 1 FAIL, 2 setup error.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

RESULTS = []


def arm(name, got, want, fix_arm=True):
    ok = got == want
    RESULTS.append((name, ok, fix_arm))
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}"
          f"{'' if fix_arm else '   (invariant/control)'}")
    print(f"       got  = {got!r}")
    print(f"       want = {want!r}")


def run_max_reset(self):
    """The shipped defect, as `reset()`: the peak is NOT cleared, so the window
    is the run maximum and only ever rises."""
    if not hasattr(self, "peak"):
        self.peak = 0.0          # first call only: the attribute must exist
    self.blocks = 0


class Capture:
    """A stdout the worker's own `emit()` writes into, and keeps the lines."""

    def __init__(self):
        self.buf = io.StringIO()
        self.lines = []

    def __enter__(self):
        self._real = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, *exc):
        sys.stdout = self._real
        return False

    def write(self, s):
        self.buf.write(s)
        if s.endswith("\n"):
            self.lines.append(s)
        return len(s)

    def flush(self):
        pass


def stream(W, peaks, hz=10.0, dt=0.1, block_s=0.0):
    """Drive the meter exactly as `on_block` does, over `peaks` (one per block).

    This is the LIVE loop's shape with the tap replaced by a list — the only way
    to test it without opening the device the owner's worker is holding.

    Returns `(payloads, tally, text)`: what the meter emitted, an INDEPENDENT
    tally of `(peak, blocks)` for the blocks each window really covered, and the
    bytes that reached stdout.
    """
    m = W.AudioMeter(hz, now=0.0, block_s=block_s)
    out, tally, cur = [], [], []
    t = 0.0
    with Capture() as cap:
        for p in peaks:
            cur.append(p)
            level = m.tick(p, t)
            if level is not None:
                W.emit(type="meter", **level)
                out.append(level)
                tally.append({"peak": round(max(cur), 4), "blocks": len(cur)})
                cur = []
            t += dt
    return out, tally, cap.buf.getvalue()


def shipped_default_hz(W):
    """The `--meter-hz` default, read from the SHIPPED SOURCE (not from memory).

    The claim this arm exists for — "an event with no consumer is OFF by
    default" — lives in the argparse call, so it is read from the file the
    worker actually runs. A default flipped back to 10 makes it go RED
    (`--neg-default`).
    """
    src = io.open(os.path.join(WORKER, "sotto_worker.py"), encoding="utf-8").read()
    i = src.index('"--meter-hz"')
    block = src[i:i + 400]
    m = re.search(r"default=([A-Za-z_][A-Za-z0-9_]*|[0-9.]+)", block)
    if not m:
        raise SystemExit("SETUP ERROR: no default= found for --meter-hz")
    return float(eval(m.group(1), {"__builtins__": {}}, vars(W)))


def main():
    # THREE falsifiers, because the feature makes three claims and each has its
    # own way of being wrong:
    #   --neg-arm      the WINDOW rule reverted to the shipped defect (the peak is
    #                  never cleared = a run maximum, the thing the contract lane
    #                  measured on WORKER_STATS);
    #   --neg-cadence  the BLOCK-COUNT rule removed, leaving a pure time window,
    #                  which is what beat the real cadence down to 6 Hz;
    #   --neg-default  the SHIPPED DEFAULT flipped back to ON — the state the
    #                  owner's decision rejected, because the shell has no
    #                  `type:"meter"` branch and every event would cost an
    #                  unthrottled `BRIDGE_UNKNOWN` log line.
    mode = ("window" if "--neg-arm" in sys.argv
            else "cadence" if "--neg-cadence" in sys.argv
            else "default" if "--neg-default" in sys.argv else None)
    import sotto_worker as W  # noqa: E402

    if mode == "window":
        W.AudioMeter.reset = run_max_reset
        print("NEG-ARM: `AudioMeter.reset` replaced by the shipped defect "
              "(the window peak is never cleared = a run maximum); every "
              "'window' arm must go RED.\n")
    elif mode == "cadence":
        _orig_init = W.AudioMeter.__init__

        def time_only_init(self, hz=W.METER_HZ, now=0.0, block_s=0.0):
            _orig_init(self, hz, now, block_s)
            self.blocks_per_window = 0     # a pure TIME window: the 6 Hz beat

        W.AudioMeter.__init__ = time_only_init
        print("NEG-CADENCE: the block-count rule removed (a pure time window); "
              "every 'cadence' arm must go RED.\n")
    elif mode == "default":
        print("NEG-DEFAULT: the shipped default flipped back to 0 (OFF) — the "
              "state that starved the panel's wave; the 'default' arms must go "
              "RED.\n")

    # ── arm 0 (FIX/default): the SHIPPED DEFAULT IS ON at 10 Hz ─────────────
    # Read from the SOURCE, so a `default=0` slipped back into argparse is caught
    # here rather than by an owner reporting that the wave stopped moving.
    default_hz = 0.0 if mode == "default" else shipped_default_hz(W)
    arm("the shipped --meter-hz default is 10 (the wave's datum is ON)",
        (default_hz, default_hz == W.METER_HZ), (10.0, True), fix_arm="default")

    # A speech-shaped level: a rise, a fall to silence, a second rise. A run
    # maximum is FLAT after the first peak; a window level tracks it.
    peaks = ([0.02] * 5 + [0.30] * 5 + [0.62] * 5 + [0.21] * 5
             + [0.01] * 10 + [0.44] * 5 + [0.05] * 15)

    out, tally, text = stream(W, peaks, block_s=0.1)
    lv = [e["peak"] for e in out]

    # ── arm 1 (FIX/window): the level FALLS when the audio falls ────────────
    falls = sum(1 for a, b in zip(lv, lv[1:]) if b < a)
    arm("the level FALLS when the audio falls (a run maximum cannot)",
        (falls > 0, lv[-1] < max(lv), round(max(lv), 4)),
        (True, True, 0.62), fix_arm="window")

    # ── arm 2 (FIX/window): the payload DESCRIBES the blocks it covered ─────
    # `tally` is kept by the driver, independently of the class: the peak and the
    # count of the blocks that fell inside each window. A window that accumulates
    # (the run-maximum defect) reports a peak no window ever held.
    arm("each event reports the peak and count of the blocks IT covered",
        out, tally, fix_arm="window")

    # ── arm 3 (FIX/window): a LATE tick reports the blocks it really covered,
    #    and there is no catch-up burst ─────────────────────────────────────
    m = W.AudioMeter(10.0, now=0.0)
    got = [m.tick(0.5, 0.0), m.tick(0.5, 0.05), m.tick(0.5, 0.10),
           m.tick(0.4, 0.25), m.tick(0.3, 0.26)]
    arm("a late tick reports its own blocks and emits no catch-up burst",
        (got, [e["blocks"] for e in got if e]),
        ([None, None, {"peak": 0.5, "blocks": 3},
          {"peak": 0.4, "blocks": 1}, None], [3, 1]), fix_arm="window")

    # ── arm 4 (control): hz=0 is INERT — not one event, not one byte ────────
    off, off_tally, off_text = stream(W, peaks, hz=0.0, block_s=0.1)
    arm("--meter-hz 0 emits nothing at all", (off, off_tally, off_text),
        ([], [], ""), fix_arm=False)

    # ── arm 4b (FIX/default): the SHIPPED DEFAULT really MOVES the level ────
    # The owner's report, as a measurement: on a DEFAULT run the datum exists,
    # it RISES and it FALLS — which is what a wave is drawn from. A run that
    # emits nothing (the wrong cure: switching the data off to quiet a log) makes
    # both clauses false and this arm goes RED.
    dflt, dflt_tally, dflt_text = stream(W, peaks, hz=default_hz, block_s=0.1)
    dlv = [e["peak"] for e in dflt]
    arm("a run at the SHIPPED DEFAULT emits a level that RISES and FALLS",
        (len(dflt) > 0, len(set(dlv)) > 1,
         any(b < a for a, b in zip(dlv, dlv[1:])), round(max(dlv), 4) if dlv else None),
        (True, True, True, 0.62), fix_arm="default")

    # ── arm 5 (FIX/cadence): the cadence is the tap's own block rate ────────
    # 100 blocks of 100 ms = 10.0 s of audio -> one event per block -> 10 Hz.
    many, _, _ = stream(W, [0.3] * 100, block_s=0.1)
    arm("100 blocks of 100 ms produce 100 events (10 Hz, the tap's block rate)",
        (len(many), round(len(many) / 10.0, 3)), (100, 10.0), fix_arm="cadence")

    # ── arm 5b (FIX/cadence): JITTER must not eat the points ────────────────
    # MEASURED on the real live loop fed from a file (`SOTTO_FILE_TAP`, 100 ms
    # blocks, 10 Hz time window): 80 blocks produced only 48 events over 8 s of
    # audio = 6.0 points/s, because a block landing just before the time boundary
    # makes the window swallow two. Blocks paced at 99 ms — i.e. drifting ahead of
    # a 100 ms timer, exactly the jitter that beat the cadence down — must still
    # give one point per block.
    jit, _, _ = stream(W, [0.3] * 100, dt=0.099, block_s=0.1)
    arm("a tap paced at 99 ms still yields one point per block (no 6 Hz beat)",
        (len(jit), round(len(jit) / 9.9, 2)), (100, 10.1), fix_arm="cadence")

    # ── arm 6 (FIX): the payload is exactly the two fields the panel reads ──
    # `app/panel/panel.js:1709` -> `pushLevel(fields.peak, fields.blocks)`.
    payloads = [json.loads(l) for l in text.splitlines() if l.strip()]
    arm("the emitted JSON carries exactly type/peak/blocks",
        sorted({tuple(sorted(p)) for p in payloads}),
        [("blocks", "peak", "type")], fix_arm=False)

    # ── arm 7 (COST): bytes/s on stdout, MEASURED ──────────────────────────
    n = 100000
    with Capture() as cap:
        for _ in range(n):
            W.emit(type="meter", peak=0.4213, blocks=1)
    per_event = len(cap.buf.getvalue()) / n
    print(f"       measured event size = {per_event:.1f} B "
          f"(a real payload: {cap.lines[0]!r})")
    print(f"       -> at 10 Hz = {per_event * 10:.0f} B/s added to stdout")
    print(f"       the WORKER_STATS tick at the same cadence would be "
          f"{600 * 10:.0f} B/s (the 600 B line the brief forbids lowering)")
    ok = 30.0 <= per_event <= 70.0
    # SHAPE/COST arms (7, 8): control arms. Reverting the WINDOW RULE cannot move
    # the payload's size or its CPU cost, and an arm that pretends it could would
    # be a fake falsifier.
    RESULTS.append(("the event is compact (30-70 B, i.e. <700 B/s at 10 Hz)",
                    ok, False))
    print(f"[{'PASS' if ok else 'FAIL'}] arm: the event is compact "
          f"(30-70 B, i.e. <700 B/s at 10 Hz)")

    # ── arm 8 (COST): the CPU of one event, MEASURED to a REAL file ─────────
    # A pipe write is what the worker does; a flushed file write is the closest
    # honest stand-in that needs no shell. Two numbers: FORMATTING (StringIO) and
    # format + WRITE + FLUSH.
    tmp = os.path.join(HERE, f"_wordsplit-meter-cost-{os.getpid()}.bin")
    with open(tmp, "wb") as fh:
        t0 = time.perf_counter()
        for _ in range(n):
            fh.write((json.dumps({"type": "meter", "peak": 0.4213, "blocks": 1})
                      + "\n").encode())
            fh.flush()
        t_file = (time.perf_counter() - t0) / n
    os.remove(tmp)
    with Capture():
        t0 = time.perf_counter()
        for _ in range(n):
            W.emit(type="meter", peak=0.4213, blocks=1)
        t_fmt = (time.perf_counter() - t0) / n
    m = W.AudioMeter(10.0, now=0.0)
    t0 = time.perf_counter()
    for _ in range(n):
        m.tick(0.42, 0.0)
    t_tick = (time.perf_counter() - t0) / n
    print(f"       emit() format-only : {t_fmt * 1e6:.2f} us/event "
          f"-> {t_fmt * 10 * 100:.4f} % of one core at 10 Hz")
    print(f"       format+write+flush : {t_file * 1e6:.2f} us/event "
          f"-> {t_file * 10 * 100:.4f} % of one core at 10 Hz")
    print(f"       AudioMeter.tick    : {t_tick * 1e6:.2f} us/event "
          f"-> {t_tick * 10 * 100:.4f} % of one core at 10 Hz")
    ok = (t_fmt * 10) < 0.001 and (t_tick * 10) < 0.001
    # SHAPE/COST, not the window rule: a control arm. Reverting `reset()` cannot
    # move it, and it must not pretend it can.
    RESULTS.append(("the meter costs <0.1 % of one core at 10 Hz", ok, False))
    print(f"[{'PASS' if ok else 'FAIL'}] arm: the meter costs <0.1 % of one core "
          f"at 10 Hz (format+tick)")

    # ── verdict ─────────────────────────────────────────────────────────────
    if mode:
        red = [a for a, ok, fix in RESULTS if fix == mode and not ok]
        green = [a for a, ok, fix in RESULTS if fix == mode and ok]
        bad = [a for a, ok, fix in RESULTS if not fix and not ok]
        ok = bool(red) and not green and not bad
        print(f"\nNEG ({mode}): {len(red)} arm(s) of this claim went RED as "
              f"required, {len(green)} stayed green (must be 0), {len(bad)} "
              f"control arm(s) broke (must be 0)")
        for a in green:
            print(f"  STILL GREEN under the revert: {a}")
        for a in bad:
            print(f"  CONTROL BROKE: {a}")
        print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    failed = [a for a, ok, _ in RESULTS if not ok]
    print(f"\naudio-meter-oracle: {len(RESULTS) - len(failed)} PASS / "
          f"{len(failed)} FAIL ({len(RESULTS)} arms)  impl={W.__file__}")
    for a in failed:
        print(f"  FAILED: {a}")
    print(f"VERDICT: {'PASS' if not failed else 'FAIL'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
