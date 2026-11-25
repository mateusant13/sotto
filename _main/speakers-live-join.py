#!/usr/bin/env python
"""speakers-live-join.py -- the JOIN nobody had run: a real call, both halves.

WHAT THIS INSTRUMENT CLOSES
---------------------------
Every piece of the per-voice chain was proven by a part, each with its own
instrument, and `worker/speaker_sidecar.py`'s own header says the missing half
is the join: *"THE JOIN between them -- a live call, this sidecar running, the
panel naming two or more people -- has NOT been run on this machine"*. On
2026-11-24 the join was not merely unproven, it was IMPOSSIBLE: the loader
refused every start because sherpa-onnx 1.13.4 has no strict GPU adapter, so
the sidecar exited 1 before capture. That is fixed by asking for the MEASURED
CPU provider by name (`DIARIZER_PROVIDER`), and this script is the run that
proves the two processes agree.

WHAT IT DOES, AND WHAT IT REFUSES TO DO
---------------------------------------
It starts `worker/speaker_sidecar.py` and `worker/sotto_worker.py --speakers`
in this order -- sidecar first, so the first caption already has a payload to
read -- with `CREATE_NO_WINDOW`, stdout captured to files, and a BOUNDED
lifetime. It reads:

  * the payload the sidecar actually published (`_main/diar-live.json`):
    real (not `fake`), fresh, and how many speakers;
  * the captions the worker actually printed, and how many of them carry a
    `voice:speaker-N` source;
  * the sidecar's placement line, which names the provider it runs on.

It does NOT open an output device, does NOT touch the owner's audio settings,
does NOT launch the panel, and does NOT navigate anything. It reads the render
mix the way the product does. Silence is not a failure: with nobody talking,
the honest answer is `CANNOT-MEASURE reason=silence`, never a green.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "app" / "webview"))

SIDECAR = ROOT / "worker" / "speaker_sidecar.py"
WORKER = ROOT / "worker" / "sotto_worker.py"
PAYLOAD = HERE / "diar-live.json"

#: The artifact identities this instrument owns. A lane is not allowed to kill
#: a process it did not start: the pids it spawns are the ONLY ones it stops,
#: and it verifies each one's cmdline still names its own script first.
SPAWNED = ("speaker_sidecar.py", "sotto_worker.py")


def _popen(argv, log_path):
    from no_console import popen_kwargs                       # noqa: PLC0415
    handle = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        argv, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=handle,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", **popen_kwargs())
    proc._sotto_log = handle
    return proc


def _stop(proc, wait_s=8.0):
    """Stop ONLY the process this instrument spawned, proven by cmdline."""
    if proc is None or proc.poll() is not None:
        return "already-exited"
    try:
        cmd = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-WindowStyle", "Hidden", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"ProcessId=%d\").CommandLine"
             % proc.pid],
            capture_output=True, text=True, timeout=10,
            **__import__("no_console").popen_kwargs()).stdout
    except Exception:  # noqa: BLE001 -- identity unknown => do not kill
        return "identity-unknown-not-stopped"
    if not any(name in (cmd or "") for name in SPAWNED):
        return "identity-mismatch-not-stopped"
    proc.kill()
    try:
        proc.wait(timeout=wait_s)
    except subprocess.TimeoutExpired:
        return "kill-timeout"
    return "stopped"


def _read_jsonl(path, kind):
    rows = []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and str(row.get("type") or "") == kind:
            rows.append(row)
    return rows


def _payload_state(now):
    try:
        raw = PAYLOAD.read_text(encoding="utf-8")
        stat = PAYLOAD.stat()
    except OSError as exc:
        return {"state": "absent", "why": type(exc).__name__}
    try:
        payload = json.loads(raw)
    except ValueError:
        return {"state": "torn", "bytes": stat.st_size}
    age = now - stat.st_mtime
    segs = payload.get("segments") if isinstance(payload, dict) else None
    return {
        "state": "present",
        "age_s": round(age, 2),
        "fresh": age <= 30.0,
        "fake": payload.get("fake") is True,
        "segments": len(segs) if isinstance(segs, list) else 0,
        "speakers": sorted({int(s.get("speaker", -1)) for s in (segs or [])
                            if isinstance(s, dict)}),
        "window_start_abs": payload.get("window_start_abs"),
        "speech_fraction": payload.get("speech_fraction"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=75.0,
                    help="bounded lifetime of the whole join")
    ap.add_argument("--worker-threads", type=int, default=4)
    ap.add_argument("--sidecar-threads", type=int, default=2)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(os.environ.get("TMPDIR") or "I:/cc-tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    side_log = out_dir / ("speakers-live-%s-sidecar.log" % stamp)
    work_log = out_dir / ("speakers-live-%s-worker.log" % stamp)
    out_json = Path(args.out) if args.out else out_dir / (
        "speakers-live-%s.json" % stamp)

    payload_before = _payload_state(time.time())
    started = time.time()
    sidecar = _popen([sys.executable, "-u", str(SIDECAR),
                      "--duration-s", str(int(args.seconds) + 10),
                      "--threads", str(args.sidecar_threads)], side_log)
    time.sleep(2.0)                      # let the tap open before the worker
    worker = _popen([sys.executable, "-u", str(WORKER), "--speakers",
                     "--threads", str(args.worker_threads)], work_log)
    try:
        deadline = started + args.seconds
        while time.time() < deadline and sidecar.poll() is None:
            time.sleep(1.0)
    finally:
        worker_state = _stop(worker)
        sidecar_state = _stop(sidecar)

    captions = _read_jsonl(work_log, "caption")
    # THE VERDICT READS THE PRODUCT'S OWN OUTPUT. The worker already decided
    # (its `source` ends in `/voice:speaker-N` when the bridge named the line),
    # so re-deciding here with a synthetic epoch -- `tap_ms - start` -- measures
    # the instrument's arithmetic, not the product: the tap happens AFTER the
    # line closed, and that shift alone can move the line out of its segment.
    # MEASURED 2026-11-25: a replay built that way said "0 of 49" on a log
    # where the worker had stamped 84 lines.
    attributed = [c for c in captions
                  if re.search(r"/voice:speaker-\d+\s*$",
                               str(c.get("source") or ""))]
    voices = sorted({re.search(r"(speaker-\d+)\s*$",
                               str(c.get("source") or "")).group(1)
                     for c in attributed})
    payload_after = _payload_state(time.time())

    side_text = side_log.read_text(encoding="utf-8", errors="replace") \
        if side_log.exists() else ""
    placement = [ln.strip() for ln in side_text.splitlines()
                 if "DIARIZER_PLACEMENT" in ln]
    side_fail = [ln.strip() for ln in side_text.splitlines()
                 if ln.startswith("sidecar:") and
                 ("unavailable" in ln or "missing" in ln)]

    facts = {
        "seconds": args.seconds,
        "wall_s": round(time.time() - started, 2),
        "sidecar_exit": sidecar_state,
        "worker_exit": worker_state,
        "placement": placement[-1] if placement else None,
        "sidecar_refusals": side_fail[-2:],
        "payload_before": payload_before,
        "payload_after": payload_after,
        "captions": len(captions),
        "attributed_captions": len(attributed),
        "voices_in_captions": voices,
        "logs": {"sidecar": str(side_log), "worker": str(work_log)},
    }
    verdict, reason = _verdict(facts)
    facts["verdict"] = verdict
    facts["reason"] = reason
    out_json.write_text(json.dumps(facts, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print("FACTS " + json.dumps(facts, ensure_ascii=False))
    print("%s speakers-live-join: %s" % (verdict, reason))
    print("report: %s" % out_json)
    return {"PASS": 0, "FAIL": 1, "CANNOT-MEASURE": 3}[verdict]


def _verdict(facts):
    pay = facts["payload_after"]
    if pay.get("state") != "present":
        return "CANNOT-MEASURE", (
            "no payload was published during %.0f s (%s); nobody spoke, the "
            "capture was silent, or the tap never opened -- the logs name "
            "which" % (facts["seconds"], pay.get("state")))
    if pay.get("fake"):
        return "FAIL", "the payload is a fixture (`fake: true`) -- the chain " \
                       "is reading a test, not audio"
    if not pay.get("fresh"):
        return "FAIL", "payload is %.1f s old (window is 30 s)" % pay.get("age_s", -1)
    if not pay.get("segments"):
        return "CANNOT-MEASURE", "a fresh payload with zero segments: it " \
                                "measured silence, it did not name voices"
    if not facts["captions"]:
        return "FAIL", "the sidecar published but the worker printed no caption"
    if not facts["attributed_captions"]:
        return "FAIL", ("the worker printed %d caption(s) and NONE carries a "
                        "voice source -- the bridge is not reading what the "
                        "sidecar writes" % facts["captions"])
    return "PASS", ("real payload (%d segments, speaker(s) %s) and %d/%d "
                    "captions attributed (%s)"
                    % (pay["segments"], pay["speakers"],
                       facts["attributed_captions"], facts["captions"],
                       ",".join(facts["voices_in_captions"]) or "-"))


if __name__ == "__main__":
    raise SystemExit(main())
