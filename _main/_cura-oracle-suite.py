"""Run the SOTTO ORACLE SUITE over `_main/` and land one receipt.

WHY THIS EXISTS: the repo's oracles were each written by a different lane and
each has its own exit code convention (documented in its own docstring: 0 PASS,
1 FAIL, 2 setup error). Before this file there was no single command that ran
them together and no receipt of the run, so "the suite is still green" was an
assertion nobody could point at.

It runs each oracle SERIALLY, in its own process, with a per-oracle timeout, and
records rc + the last lines of its output. Serial is not a convenience: two
concurrent CUDA processes in this tree die at ~62 s with rc=255 and no traceback
(`docs/audit/sotto-vs-referencia.md` §7).

`rc==2` is reported as UNRUNNABLE, never as a pass: several oracles need a live
loopback endpoint, the overlay, or a device this box may not have, and a setup
error is not the same claim as a green.

Usage:
  python _main/_cura-oracle-suite.py [--only NAME,...] [--out receipts.json]
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
PY = sys.executable or "python"

# name, argv, timeout_s
ORACLES = [
    ("segment-rerun-probe", ["_main/segment-rerun-probe.py"], 420),
    ("model-spec-oracle", ["_main/model-spec-oracle.py"], 120),
    ("config-keys-oracle", ["_main/config-keys-oracle.py"], 300),
    ("lang-id-oracle", ["_main/lang-id-oracle.py"], 300),
    ("caption-lines-oracle", ["_main/caption-lines-oracle.py"], 300),
    ("speech-gate-oracle", ["_main/speech-gate-oracle.py"], 420),
    ("delivery-rate-oracle-wav",
     ["_main/delivery-rate-oracle.py", "--wav", "worker/assets/sample1.flac"], 420),
    ("flat-endpoint-oracle", ["_main/flat-endpoint-oracle.py"], 180),
    ("wasapi-com-init-oracle", ["_main/wasapi-com-init-oracle.py"], 180),
    ("_ordem-cura-oracle", ["_main/_ordem-cura-oracle.py"], 180),
    ("panel-hidden-at-startup-oracle",
     ["_main/panel-hidden-at-startup-oracle.py", "--repeats", "2"], 420),
    ("restart-30s-oracle", ["_main/restart-30s-oracle.py"], 300),
    ("panel-exit3-oracle", ["_main/panel-exit3-oracle.py"], 300),
    ("run-cmd-exit-oracle", ["_main/run-cmd-exit-oracle.py"], 300),
    # ── the NODE probes ──────────────────────────────────────────────────────
    # A gate nobody runs is this house's most-repeated defect: the three `.js`
    # probes below were each RED-able and each invoked by NOBODY (`grep -rn`
    # found only their own strings). The suite runs `[PY] + argv` (see the
    # subprocess.run below) and maps rc 0/1/2 to GREEN/RED/UNRUNNABLE, so each
    # node probe is invoked THROUGH the interpreter, which propagates node's
    # exit code. `cwd=` is the repo root the suite already runs every oracle in.
    ("route-stamp-gate",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/route-stamp-gate.js'],cwd=r'H:/sotto'))"],
     120),
    ("historico-vs-redux-probe",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/historico-vs-redux-probe.js'],cwd=r'H:/sotto'))"],
     120),
    ("panel-live-vs-history-probe",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/panel-live-vs-history-probe.js'],cwd=r'H:/sotto'))"],
     120),
    # The silent-fallback probe (owner order 2026-10-07): the `src=` field that
    # names WHICH branch decided the route, so a line the else-half manufactured
    # reads `route=final src=fallback` and cannot be mistaken for a worker vote.
    # RED input is its own `--emit-mutant` copy (the derivation forced to a
    # constant), the same mutation `route-stamp-gate`'s G5 arm is proven on.
    ("silent-fallback-probe",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/silent-fallback-probe.js'],cwd=r'H:/sotto'))"],
     120),
]

VERDICT = {0: "GREEN", 1: "RED", 2: "UNRUNNABLE"}


def main():
    # A child's output is decoded with errors="replace", which yields U+FFFD. On a
    # cp1252 console print() then raises UnicodeEncodeError and ABORTS THE WHOLE
    # SUITE mid-run -- every oracle after the first one with a bad byte never ran.
    # Measured 2026-10-07: the run died on the first tail line carrying \ufffd,
    # after 4 oracles of the list. errors="replace" here cannot raise, so the
    # suite always reaches its own SUITE line and its receipt.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=os.path.join(HERE, "_cura-oracle-suite.json"))
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    rows = []
    for name, argv, timeout in ORACLES:
        if only and name not in only:
            continue
        t0 = time.time()
        try:
            p = subprocess.run([PY] + argv, cwd=REPO, capture_output=True,
                               timeout=timeout)
            rc, out, err = p.returncode, p.stdout, p.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            rc, out, err, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
        wall = round(time.time() - t0, 1)
        text = (out or b"").decode("utf-8", "replace") + (err or b"").decode("utf-8", "replace")
        tail = [ln for ln in text.strip().splitlines() if ln.strip()][-6:]
        verdict = "TIMEOUT" if timed_out else VERDICT.get(rc, f"rc={rc}")
        rows.append({"oracle": name, "argv": argv, "rc": rc, "verdict": verdict,
                     "wall_s": wall, "tail": tail})
        print(f"[{verdict:>10}] {name:<32} rc={rc} wall={wall}s")
        for ln in tail:
            print(f"             | {ln}")

    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("SUITE: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    json.dump({"repo": REPO, "rows": rows, "counts": counts},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"receipt: {args.out}")
    # rc: 0 only when NOTHING is red and nothing timed out. UNRUNNABLE is
    # reported, not excused, but it is not a failure of the code under test.
    bad = [r for r in rows if r["verdict"] in ("RED", "TIMEOUT")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
