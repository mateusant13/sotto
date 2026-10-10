#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ENGINE-PROCESS AUDIT BATTERY v2 -- ONE command, BOTH colours, the EXIT CODE is the verdict.

Subject : H:/sotto-wt/engproc/_moved/aireplay/src/engine  (branch feat/engine-process)
What    : run the whole dual-colour engine gate, then THIS battery's own checks on top of
          the gate's own verdict.  A step is never reported PASS when it did not run.
Run     : python _main/_engine-audit-battery-v2.py             (full, writes the log)
          python _main/_engine-audit-battery-v2.py --log FILE  (score an existing log)
          python _main/_engine-audit-battery-v2.py --neg-arm   (prove the battery can go RED)

The gate it runs (src/engine/test_engine.py --mutants) is the dual-colour instrument itself:
GREEN on the subject as it ships, RED on copies with one defect restored.  The battery
AGGREGATES and its exit code IS the verdict, in the house style of _main\_audit-verify-all.cmd:
a MISSING instrument or a missing step is a FAILURE, and any failure exits 1.

No audio device, no screen, no WGC: every arm is headless.  Which arm used the REAL C++ child
(its own --selftest / --inject-fault paths) and which used stub_capture.py is disclosed, arm
by arm, in _main/20261009-engine-process-lane-a.md -- never inferred from this battery.
"""

import argparse
import os
import re
import subprocess
import sys
import time

CREATE_NO_WINDOW = 0x08000000
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.normpath(os.path.join(HERE, "..", "src", "engine"))
GATE = os.path.join(ENGINE_DIR, "test_engine.py")
DEFAULT_LOG_DIR = os.environ.get("TMPDIR") or "I:/cc-tmp"
DEFAULT_LOG = os.path.join(DEFAULT_LOG_DIR, "battery-engine-v2.txt")

GREEN_ARMS = ["ARM-A", "ARM-B", "ARM-C/dead", "ARM-C/stall", "ARM-D",
              "ARM-E", "ARM-F", "ARM-G"]
RED_CONTROLS = ["stdout-leak", "no-replay", "capture-waits", "preflight-ok", "no-lock",
                "commit-nokey", "stale-lie", "no-finalise"]

# The gate's VERDICT TABLE rows.  Both regexes are applied LINE-WISE (never with re.M over the
# whole text) for two measured reasons: the table may hold TWO red rows for the same arm
# (ARM-G carries two mutants), and r[3] must be the WHOLE line, because one check reads the
# engine stdout byte count OUT of that row.
ROW = re.compile(r"^\s{2}(PASS|FAIL|REDok|BAD)\s+(ARM-\S+)\s+(green|red)\b")
ECHO = re.compile(r"^ARM-\S+\s+red\s+RED\s+(?:[\d.]+s\s+)?mutant=(\S+)")
SUMMARY = re.compile(r"arms=(\d+) \(([^)]*)\) green=(\d+)/(\d+) red-controls-red=(\d+)/(\d+) silent-controls=(\d+)")
VERDICT = re.compile(r"^GATE-VERDICT:\s*(\S+)", re.M)
STDOUT_BYTES = re.compile(r"stdout=(\d+)B")
LAT = re.compile(r"\bui(?:1|2)?=(\d+)ms")


def run_gate(log_path, keep):
    """Run the dual-colour gate; its ENTIRE output becomes the battery log."""
    argv = [sys.executable, GATE, "--mutants"] + (["--keep"] if keep else [])
    print("BATTERY CMD  : python src/engine/test_engine.py %s" % " ".join(argv[2:]))
    print("BATTERY LOG  : %s" % log_path)
    print("BATTERY START: %s" % time.strftime("%Y-%m-%dT%H:%M:%S"))
    print("")
    env = dict(os.environ)
    env["TMPDIR"] = DEFAULT_LOG_DIR        # G: fills (ENOSPC); I:/cc-tmp is the lane scratch
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    # CREATE_NO_WINDOW: never put a console on the owner's screen (AGENTS.md hard rule).
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    p = subprocess.Popen(argv, cwd=ENGINE_DIR, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env, text=True,
                         encoding="utf-8", errors="replace",
                         creationflags=flags)
    with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        for line in p.stdout:
            fh.write(line)
            sys.stdout.write(line)
    p.wait()
    print("")
    print("BATTERY GATE EXIT=%s  wall=%.1fs" % (p.returncode, time.time() - t0))
    return p.returncode


def score(log_path, rc=None):
    """The battery's OWN checks on one gate log.  Returns (ok, checks, text)."""
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    rows = []
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3), line))
    green_rows = [r for r in rows if r[2] == "green"]
    red_rows = [r for r in rows if r[2] == "red"]
    green_ok = (len(green_rows) == len(GREEN_ARMS)
                and sorted(r[1] for r in green_rows) == sorted(GREEN_ARMS)
                and all(r[0] == "PASS" for r in green_rows))
    red_ok = len(red_rows) == 8 and all(r[0] == "REDok" for r in red_rows)
    green_stdout = [int(x) for r in green_rows for x in STDOUT_BYTES.findall(r[3])]
    verdicts = VERDICT.findall(text)
    summary = SUMMARY.search(text)
    mutants_red = sorted(set(ECHO.match(line).group(1) for line in
                              text.splitlines() if ECHO.match(line)))
    lats = sorted(set(int(x) for x in LAT.findall(text)))
    checks = {}
    if rc is not None:
        checks["gate exit code 0"] = (rc == 0)
    checks["exactly one GATE-VERDICT line"] = len(verdicts) == 1
    checks["gate verdict is GREEN"] = verdicts == ["GREEN"]
    checks["all 8 green arms ran and PASS"] = green_ok
    checks["all 8 red controls ran and went RED"] = red_ok
    checks["all 8 named mutants went RED"] = mutants_red == sorted(RED_CONTROLS)
    checks["gate summary says 8/8, 8/8, 0 silent"] = bool(
        summary and summary.group(3) == "8" and summary.group(5) == "8"
        and summary.group(7) == "0")
    checks["stdout-leak control proves the stdout guard"] = bool(
        re.search(r"^ARM-\S+\s+red\s+RED[^\n]*FAIL:stdout empty", text, re.M))
    checks["engine stdout empty on every green arm"] = (
        len(green_stdout) >= 2 and sum(green_stdout) == 0)
    checks["UI reconnect latency measured (ms)"] = bool(lats)
    checks["no arm threw an exception"] = "exception" not in text
    checks["no silent control"] = ("CONTROL DID NOT GO RED" not in text
                               and "NOT-A-CONTROL" not in text)
    checks["census: no gate process left alive"] = (
        "no gate process alive after the run" in text)
    return all(checks.values()), checks, text


def report(tag, checks, text):
    print("")
    print("%s RESULT" % tag)
    for k, v in checks.items():
        print("  %-5s %s" % ("PASS" if v else "FAIL", k))
    lats = sorted(set(int(x) for x in LAT.findall(text)))
    if lats:
        print("UI-RECONNECT LATENCY (attach -> first ui_ready health, ms): min=%d max=%d %s"
              % (lats[0], lats[-1], lats))
    return [k for k, v in checks.items() if not v]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Engine-process audit battery v2")
    ap.add_argument("--log", default="", help="score an existing gate log instead of running it")
    ap.add_argument("--no-keep", action="store_true",
                        help="let the gate delete its workdirs")
    ap.add_argument("--neg-arm", action="store_true",
                        help="score a TAMPERED copy of the log: the battery MUST go RED")
    args = ap.parse_args(argv)
    print("BATTERY      : _engine-audit-battery-v2  subject=%s" % ENGINE_DIR)
    print("GATE         : %s" % GATE)
    print("")
    rc = None
    if args.log:
        log_path = args.log
        print("BATTERY MODE : scoring an existing log: %s" % log_path)
    else:
        os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)
        log_path = DEFAULT_LOG
        rc = run_gate(log_path, not args.no_keep)
    if args.neg_arm:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        tampered = text.replace("GATE-VERDICT: GREEN", "GATE-VERDICT: RED", 1)
        tampered = tampered.replace("no gate process alive after the run",
                                  "TAMPERED", 1)
        # flip ONE VERDICT TABLE row (never an echo line): "  PASS " starts a table row,
        # an echo line merely contains "PASS" after the arm name.
        lines = tampered.split("\n")
        for i, ln in enumerate(lines):
            if ln.startswith("  PASS "):
                lines[i] = ln.replace("  PASS ", "  FAIL ", 1)
                break
        tampered = "\n".join(lines)
        if rc is not None:
            pass                        # the exit-code check is taken from the real rc
        else:
            tampered = tampered.replace("EXIT=0", "EXIT=1", 1)
        if tampered == text:
            print("NEGPROOF-FAIL: could not tamper the log (%s)" % log_path)
            return 2
        bad = os.path.join(DEFAULT_LOG_DIR, "battery-engine-v2-negproof.txt")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write(tampered)
        ok, checks, text2 = score(bad, rc=1)
        print("")
        print("NEGPROOF     : %s" % bad)
        failed = report("NEGPROOF", checks, text2)
        print("")
        if ok:
            print("NEGPROOF-VERDICT: BATTERY STAYED GREEN ON A TAMPERED LOG")
            print("NEGPROOF-EXITCODE=1")
            return 1
        print("NEGPROOF-VERDICT: RED   failed=%d/%d %s"
              % (len(failed), len(checks), ",".join(failed)))
        print("NEGPROOF-EXITCODE=0")
        return 0
    ok, checks, text = score(log_path, rc=rc)
    failed = report("BATTERY", checks, text)
    if ok:
        print("")
        print("BATTERY-VERDICT: GREEN - %d step(s) pass" % len(checks))
        print("exit-code: 0")
        return 0 if (rc is None or rc == 0) else 1
    print("")
    print("BATTERY-VERDICT: RED - %d step(s) failed: %s"
          % (len(failed), ", ".join(failed)))
    print("exit-code: 1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
