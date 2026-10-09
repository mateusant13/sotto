#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wake-tick-gate.py -- A GATE THAT CAN SAY NO.

WHAT THIS IS. `cron-wake-gate.ps1` is the oracle for the 4:40 wake loop: it reads
`state/progress/heartbeat.json`, keeps the last tick it SAW, and asks "is the
number going up?". This file is the same question asked by the same rule, with
no dependency on the live surface, so it can be pointed at a frozen COPY and be
made to fail on purpose. A gate that has only ever returned green has never been
tested; that is the whole reason this file exists separately from the one that
runs on the schedule.

THE BAR. `cadence x tolerance`, default 280 s x 3 = 840 s.

  A NOTE THAT IS A CORRECTION, NOT A PARAPHRASE. The brief for this file said
  "threshold x 3 (the gate's own bar)". The live gate's own bar is x2, not x3.
  `cron-wake-gate.ps1:169` declares `[int]$Tolerance = 2`, and its own header
  (`:102-126`) records the history: x3 was the ORIGINAL borrowed convention,
  x1 was tried and MEASURED to be a mistake (326 of 331 samples exceeded it and
  the gate killed a healthy loop), and x2 = 560 s is the number that survived,
  because it sits above the MEASURED healthy maximum (~302 s). So x3 = 840 s is
  the brief's number and it is not the production number. It is kept as the
  default because it is what was asked for, and it is exposed as --tolerance so
  that x2 (the production bar) can be run against the same evidence. Being LESS
  sensitive than production is stated here rather than discovered later.

  The rule the header buys, which is the part that outlives the number: a
  threshold on a periodic producer must be derived from the MEASURED period,
  never from the period the config DECLARES.

WHAT MAKES IT RED. Two independent ages, either of which past the bar is a
failure. Taking the OR of two measurements, not the max of them, because they
fail for different reasons:

  A. `unchanged_for` -- now minus the last time THIS GATE saw the tick move.
     This is the gate's own memory, and it is the measurement that survives a
     touched-but-not-written file.
  B. `artifact_age`  -- now minus the heartbeat's own mtime / `at`.
     This is the one that works on a FIRST run, when there is no memory yet.
     Without it a gate with no baseline is silent forever, which is the exact
     shape of the blind spot this file exists to close.

EXIT CODES (house law, same as cron-wake-gate.ps1: rc carries a VERDICT, never
a cause):
  0  the tick is advancing, or is inside the bar and therefore not yet a verdict
  3  STALLED -- the tick has not advanced within the bar
  4  COULD NOT TELL -- heartbeat or state unreadable. Fail-closed, and the
     artefact that could not be read is named. rc 4 exists so "I could not tell"
     is never printed as either "the loop is fine" or "the loop is gone".

uso:
  python wake-tick-gate.py                                   # the live surface
  python wake-tick-gate.py --heartbeat FROZEN --state S      # RED proof
  python wake-tick-gate.py --tolerance 2                     # the production bar
  python wake-tick-gate.py --selftest                        # both, on fixtures
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# The loop's OWN declared cadence. This is what the bar is derived FROM, and
# per the rule above it is the DECLARED number -- the measured floor is
# `state/progress/cron-wake-floor.json` and it is not read here on purpose, so
# that this file stays pointable at a copy with no other live surface attached.
DEFAULT_CADENCE_S = 280
DEFAULT_TOLERANCE_X = 3

LIVE_HEARTBEAT = r"I:\!manager\state\progress\heartbeat.json"
LIVE_STATE = r"I:\!manager\state\progress\cron-wake-gate-tickdelta.json"

RC_OK, RC_STALLED, RC_CANNOT_TELL = 0, 3, 4


def _say(line: str) -> None:
    stamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{stamp} {line}", flush=True)


def _parse_iso(txt) -> float | None:
    if not txt or not isinstance(txt, str):
        return None
    try:
        return _dt.datetime.fromisoformat(txt).timestamp()
    except (ValueError, TypeError):
        return None


def read_heartbeat(path: Path):
    """(tick, artifact_mtime_epoch), or a string naming why it could not be read."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"heartbeat unreadable: {exc}"
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        return f"heartbeat is not valid JSON ({exc}); a truncated write is exactly this"
    if not isinstance(payload, dict):
        return "heartbeat is not a JSON object"
    tick = payload.get("tick")
    # bool is an int subclass; a `true` where a count belongs is a bug, not a tick.
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        return f"heartbeat has no usable `tick` (got {tick!r})"
    # mtime FIRST, `at` second: mtime is what the filesystem says happened, and
    # `at` is a self-report the producer could have written and then not been
    # able to act on. Prefer the witness over the claim.
    try:
        mtime = path.stat().st_mtime
    except OSError:
        at = _parse_iso(payload.get("at"))
        if at is None:
            return "heartbeat has neither a usable mtime nor a parseable `at`"
        return tick, at
    return tick, mtime


def read_state(path: Path):
    """The last tick this gate SAW, or None when there is no usable memory.

    A malformed state file is None, not an exception: the gate falls back to
    the artifact age rather than dying. That is the same shape as the blind
    spot this file closes, so it must not open a second one here.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    tick = payload.get("last_tick")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        return None
    advanced = _parse_iso(payload.get("last_advance_utc"))
    if advanced is None:
        return None
    return {"last_tick": tick, "last_advance_utc": advanced}


def write_state(path: Path, tick: int, advanced_epoch: float, verdict: str) -> None:
    """Atomic, so a reader never sees a half-written file.

    THIS IS THE ONE-LINE DEFECT THIS FILE EXISTS BECAUSE OF.
    `cron-wake-gate.ps1:386` writes its state with a format string whose
    `episode` value AND closing quote are both missing, so the healthy-advance
    path emits `...,"episode":}` -- not valid JSON. The next firing cannot parse
    it, has no baseline, re-seeds, and writes it again broken. Measured on the
    live surface: the state file is 98 B and ends mid-token, and the gate log
    alternates `TICK ok tick=X (+N)` with `TICK ok seeded (no baseline yet)` on
    every single firing. See TICK-DELTA.md.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "last_tick": tick,
            "last_advance_utc": _dt.datetime.fromtimestamp(
                advanced_epoch, _dt.timezone.utc
            ).isoformat(timespec="seconds"),
            "verdict": verdict,
        }
    )
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        # The write did NOT land. Report it loudly on stderr and remove the
        # partial temp; re-raise, because a state file that was not written is
        # not a green -- it is a gate that has lost its memory.
        print(f"wake-tick-gate: FAILED to write state {path}", file=sys.stderr)
        if tmp.exists():
            os.unlink(tmp)
        raise
    # Success path: os.replace MOVED tmp onto path, so tmp no longer exists and
    # there is nothing to clean up and nothing to swallow.


def check(heartbeat: Path, state_path: Path, cadence_s: int, tolerance_x: int) -> int:
    bar = cadence_s * tolerance_x
    read = read_heartbeat(heartbeat)
    if isinstance(read, str):
        _say(f"GATE CANNOT-TELL rc=4 {read}")
        return RC_CANNOT_TELL
    tick, artifact_epoch = read
    artifact_age = max(0.0, time.time() - artifact_epoch)

    _say(
        f"START tick={tick} cadence={cadence_s}s tolerance=x{tolerance_x} "
        f"bar={bar}s artifact_age={int(artifact_age)}s"
    )

    last = read_state(state_path)

    if last is None:
        # No memory. The artifact age is the only witness there is, and it is
        # enough to go red: silence past the bar is silence past the bar.
        if artifact_age > bar:
            _say(
                f"STALLED rc=3 tick={tick} no_baseline=True artifact_age="
                f"{int(artifact_age)}s > bar={bar}s verdict=RED"
            )
            write_state(state_path, tick, artifact_epoch, "stalled")
            return RC_STALLED
        write_state(state_path, tick, time.time(), "seeded")
        _say(f"TICK ok seeded tick={tick} (no baseline yet; nothing to compare)")
        return RC_OK

    unchanged_for = max(0.0, time.time() - last["last_advance_utc"])

    if tick > last["last_tick"]:
        delta = tick - last["last_tick"]
        write_state(state_path, tick, time.time(), "advanced")
        _say(
            f"TICK ok tick={tick} (+{delta}) unchanged_for={int(unchanged_for)}s "
            f"bar={bar}s verdict=GREEN"
        )
        return RC_OK

    if tick < last["last_tick"]:
        write_state(state_path, tick, time.time(), "restarted")
        _say(
            f"TICK ok tick={tick} (was {last['last_tick']}: loop REPLACED, counter "
            f"restarted -- movement, not a stall) verdict=GREEN"
        )
        return RC_OK

    # Equal ticks. Two independent ages, OR-ed: either one past the bar is RED.
    if unchanged_for > bar or artifact_age > bar:
        _say(
            f"STALLED rc=3 tick={tick} unchanged_for={int(unchanged_for)}s "
            f"artifact_age={int(artifact_age)}s bar={bar}s verdict=RED"
        )
        write_state(state_path, tick, last["last_advance_utc"], "stalled")
        return RC_STALLED

    _say(
        f"TICK ok tick={tick} unchanged but only {int(unchanged_for)}s stalled "
        f"(bar {bar}s) verdict=GREEN"
    )
    return RC_OK


def selftest(cadence_s: int, tolerance_x: int) -> int:
    """Both colours, on fixtures built HERE -- never on the owner's live surface."""
    import shutil

    root = Path(tempfile.mkdtemp(prefix="wake-tick-gate-selftest-"))
    rc_total = 0
    try:
        bar = cadence_s * tolerance_x

        # --- RED: a heartbeat frozen far past the bar, and no baseline ---
        frozen = root / "frozen-heartbeat.json"
        frozen.write_text(
            json.dumps({"at": "2026-10-07T03:07:02+00:00", "tick": 10151}),
            encoding="utf-8",
        )
        # Backdate the mtime by 2 bar-lengths so the age, not the `at` claim, is
        # what the gate reads. A green here would be a gate trusting a claim.
        past = time.time() - 2 * bar
        os.utime(frozen, (past, past))
        rc = check(frozen, root / "red-state.json", cadence_s, tolerance_x)
        print(f"--- SELFTEST frozen:      rc={rc} (want 3)", flush=True)
        if rc != RC_STALLED:
            print("--- SELFTEST FAILED: a frozen heartbeat did not go RED", flush=True)
            rc_total = 1

        # --- GREEN: the same shape, but written NOW ---
        live = root / "live-heartbeat.json"
        live.write_text(
            json.dumps({"at": "2026-10-07T22:22:18+00:00", "tick": 10226}),
            encoding="utf-8",
        )
        rc = check(live, root / "green-state.json", cadence_s, tolerance_x)
        print(f"--- SELFTEST fresh-seed:  rc={rc} (want 0)", flush=True)
        if rc != RC_OK:
            print("--- SELFTEST FAILED: a fresh heartbeat went RED", flush=True)
            rc_total = 1

        # --- GREEN: and now the MEMORY advances, which is the real green ---
        time.sleep(1.05)
        live.write_text(
            json.dumps({"at": "2026-10-07T22:27:18+00:00", "tick": 10238}),
            encoding="utf-8",
        )
        rc = check(live, root / "green-state.json", cadence_s, tolerance_x)
        print(f"--- SELFTEST advanced:    rc={rc} (want 0)", flush=True)
        if rc != RC_OK:
            print("--- SELFTEST FAILED: an advancing tick went RED", flush=True)
            rc_total = 1

        print(f"--- SELFTEST {'PASS' if rc_total == 0 else 'FAIL'}", flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return rc_total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="wake tick delta gate")
    ap.add_argument("--heartbeat", default=LIVE_HEARTBEAT)
    ap.add_argument(
        "--state",
        default=LIVE_STATE,
        help="this gate's OWN memory file; separate from cron-wake-gate.json "
        "so the two gates cannot corrupt each other's baseline",
    )
    ap.add_argument("--cadence", type=int, default=DEFAULT_CADENCE_S)
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE_X)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(args.cadence, args.tolerance)
    return check(Path(args.heartbeat), Path(args.state), args.cadence, args.tolerance)


if __name__ == "__main__":
    sys.exit(main())