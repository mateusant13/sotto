#!/usr/bin/env python
"""_speaker-chain-live.py -- THE JOIN, TWO PROCESSES, WITH A REAL AUDIO DEVICE.

This is the instrument, not a gate. Gates in this repo are fast and
deterministic; this one opens a real WASAPI loopback on a real render endpoint
and starts a real second process, so it is measured rather than asserted and
then written down by hand.

THE CHAIN IT CLOSES, and the reason it exists as its own file:

    render endpoint -> real tap -> ring buffer -> offset -> atomic publish
                    -> payload file -> bridge -> LineFormer -> caption event

Everything except the MODEL is exercised for real here. The diarizer is
`FakeDiarizer`, so the run costs a few seconds of CPU and no 277 MB -- which is
the whole reason it could be run at all while the owner is on a call.

THE BUG THIS INSTRUMENT WAS BUILT TO CATCH, and which no oracle could catch.

The worker stamps a caption's `start` as seconds since ITS OWN capture began:
`sotto_worker.py:5736` computes `(idx - 1) * asr.chunk / TARGET_SR`, where `idx`
is the worker's own chunk counter. The sidecar is a different process and
publishes on the wall clock. Two unrelated zeros.

Every oracle so far drove both sides from one fake clock, so the arithmetic was
consistent in the test and meaningless in production. In production it would
have produced NO error and NO log line -- it would simply have attributed every
line to whichever stranger spoke at that stream position in the sidecar's
window. A plausible, wrong, fully-painted name.

So this instrument runs the SAME captions TWICE through the REAL `LineFormer`:
once with `stream_epoch` set, once with it `None`, and reports both. The gap
between those two numbers is what the epoch buys, measured rather than argued.

    python _main\_speaker-chain-live.py --duration-s 10
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time

REPO = r"H:\sotto"
sys.path.insert(0, os.path.join(REPO, "worker"))

PLUMBING = os.path.join(REPO, "_main", "speaker-plumbing-oracle.py")
SIDECAR = os.path.join(REPO, "worker", "speaker_sidecar.py")

DEVICE = "device:CABLE Output (VB-Audio Virtual Cable)"

#: One caption every 400 ms for the whole run: short enough that some windows
#: certainly land inside the sidecar's window, long enough that most do not.
STEP_S = 0.4
LINE_S = 0.35


def extract_lineformer():
    """The SAME extractor the plumbing gate uses -- not a second copy.

    `runpy.run_path` executes the oracle's module body; its `main()` is behind
    `if __name__ == "__main__"`, so nothing runs and the tested extractor comes
    back. Two copies of this function would drift, and the drift would show up
    as a disagreement between this instrument and the gate that is supposed to
    describe the same code.
    """
    ns = runpy.run_path(PLUMBING)
    worker_src = open(os.path.join(REPO, "worker", "sotto_worker.py"),
                      encoding="utf-8").read()
    return ns["extract_lineformer"](worker_src)


def scenarios(duration_s, epoch):
    """Captions on the WORKER's clock: stream seconds, not wall clock."""
    out = []
    t = 0.0
    n = 0
    while t < duration_s:
        n += 1
        out.append(("linha %d do worker" % n, round(t, 2), round(t + LINE_S, 2),
                    n % 3 != 0))
        t += STEP_S
    return out


def run_sidecar(out_path, duration_s, device=None):
    cmd = [sys.executable, SIDECAR, "--capture-selftest",
           "--out", out_path, "--duration-s", str(duration_s)]
    if device:
        cmd += ["--device", device]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    return proc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--duration-s", type=float, default=10.0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="speaker-chain-")
    payload_path = args.out or os.path.join(tmp, "diar-live.json")
    report_path = args.report or os.path.join(tmp, "chain.json")

    LineFormer = extract_lineformer()

    print("THE JOIN: two processes, one real audio device, no model")
    print("  worker source : %s" % os.path.join(REPO, "worker",
                                                "sotto_worker.py"))
    print("  sidecar       : %s" % SIDECAR)
    print("  payload       : %s" % payload_path)
    print("  duration      : %.0f s" % args.duration_s)

    # ── the worker's zero, taken the way the live arm takes it ──────────────
    epoch = time.time()
    proc = run_sidecar(payload_path, args.duration_s, args.device)

    import speaker_bridge                                            # noqa: PLC0415

    cache = speaker_bridge.PayloadCache(payload_path)

    # ── TWO formers, ONE timeline, driven in REAL TIME ─────────────────────
    # The first version of this instrument pushed every caption instantly,
    # before the sidecar had published anything, and measured "0 of 31 named".
    # That was the INSTRUMENT lying: the captions' stream times ran 0..10 s
    # while the only payload that existed was written after they were all
    # generated. A real worker emits a caption as the audio arrives, so this
    # walks the clock in real time and offers the same caption to both formers
    # on the same beat.
    #
    # BOTH formers are driven on the SAME timeline on purpose. Running the
    # "without epoch" arm afterwards, as a second pass, would compare two
    # different moments against two different payloads and could not attribute
    # a single difference to the epoch.
    former_with = LineFormer(min_chars=3, emit_partial=True, source=DEVICE)
    former_without = LineFormer(min_chars=3, emit_partial=True, source=DEVICE)
    former_with.set_speaker_provider(cache)
    former_without.set_speaker_provider(cache)
    former_with.stream_epoch = epoch
    # `former_without.stream_epoch` stays None -- that is the arm.

    events_with, events_without = [], []
    beats = 0
    t = 0.0
    n = 0
    started = time.time()
    while time.time() - started < args.duration_s - 0.2:
        text = "linha %d do worker" % (n + 1)
        cont = (n % 3) != 2
        events_with.extend(former_with.push(text, round(t, 2),
                                            round(t + LINE_S, 2), cont))
        events_without.extend(former_without.push(text, round(t, 2),
                                                  round(t + LINE_S, 2), cont))
        n += 1
        beats += 1
        t += STEP_S
        time.sleep(STEP_S)
    events_with.extend(former_with.flush())
    events_with.extend(former_with.take_closed())
    events_without.extend(former_without.flush())
    events_without.extend(former_without.take_closed())

    try:
        sidecar_out = proc.communicate(timeout=args.duration_s + 25)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        sidecar_out = proc.communicate()[0]

    named_with = [e for e in events_with if e.get("speaker")]
    named_without = [e for e in events_without if e.get("speaker")]
    sources = sorted({e.get("source") for e in named_with})

    report = {
        "epoch": epoch,
        "duration_s": args.duration_s,
        "beats": beats,
        "events": len(events_with),
        "named_with_epoch": len(named_with),
        "named_without_epoch": len(named_without),
        "sources_with_epoch": sources,
        "speakers_with_epoch": sorted({e.get("speaker") for e in named_with}),
        "speakers_without_epoch": sorted({e.get("speaker")
                                          for e in named_without}),
        "payload_exists": os.path.isfile(payload_path),
        "sidecar_output": sidecar_out.splitlines()[-14:],
    }
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("\n--- sidecar stdout (tail) ---")
    for line in sidecar_out.splitlines()[-14:]:
        print("  " + line)

    print("\n--- the join ---")
    ok = True

    def chk(cond, name, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %s %s%s" % ("GREEN" if cond else "RED  ", name,
                             ("  " + detail) if detail else ""))

    chk(len(events_with) > 0, "the worker produced caption events",
        "%d events" % len(events_with))
    chk(report["payload_exists"], "the sidecar published a payload the worker "
                                  "could read")
    chk(len(named_with) > 0, "WITH the epoch, lines are attributed",
        "%d of %d named" % (len(named_with), len(events_with)))
    chk(len(sources) >= 1, "and each voice gets its own source",
        repr(sources))
    chk(all(("voice:speaker-" in s) for s in sources),
        "the source names the voice")
    print()
    print("  named WITH epoch    : %d   voices=%s"
          % (len(named_with), report["speakers_with_epoch"]))
    print("  named WITHOUT epoch : %d   voices=%s"
          % (len(named_without), report["speakers_without_epoch"]))
    if len(named_without) != len(named_with) or \
            report["speakers_without_epoch"] != report["speakers_with_epoch"]:
        print("  -> the epoch CHANGES the answer, so it is load-bearing")
    else:
        print("  -> the two agree here; that is not proof the epoch is "
              "unnecessary, only that this window was not decisive")

    print("\nREPORT: %s" % report_path)
    print("VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())