#!/usr/bin/env python3
"""agents-md-pins-oracle -- re-measure, live, every size/sha that AGENTS.md pins, and fail when the doc drifts.

WHY THIS EXISTS (2026-10-12). AGENTS.md rule 2 demands that every cited size or sha names its
revision, because a false line in that file is read by every agent. Two failures in one day:
  * the `run.cmd --help` size was stale (2272 B from 2026-10-06 against 4872 B live), corrected
    by the Lead the same day;
  * and the Lead then made a NEW stale pin by editing `_main/_audit-verify-all.cmd` (32203 B ->
    32637 B) while AGENTS.md's corrections table still quoted the old size.
A doc that cannot be checked rots, so the numbers are now a GATE instead of prose. This oracle is
doc-drift detection ONLY: it launches nothing (the `run.cmd --help` path is the wrapper's
safe-uses pre-flight -- argparse prints usage and exits, no window, no app), it never writes to
AGENTS.md, and every number it compares is measured in this run.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
AGENTS = os.path.join(ROOT, "AGENTS.md")
WRAPPER = os.path.join(ROOT, "app", "webview", "run.cmd")
BATTERY = os.path.join(ROOT, "_main", "_audit-verify-all.cmd")

failures = []


def say(text):
    print("sotto: " + text)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def measure_doc(path):
    return read_bytes(path)


def measure_help():
    """run.cmd --help to a file: the one invocation the docs already call safe (pre-flight only)."""
    handle, path = tempfile.mkstemp(suffix=".txt", prefix="agents-pin-help-")
    os.close(handle)
    try:
        with open(path, "wb") as out:
            proc = subprocess.run(["cmd", "/c", WRAPPER + " --help"], stdout=out,
                                  stderr=subprocess.STDOUT, cwd=ROOT, timeout=180)
        body = read_bytes(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return {
        "bytes": len(body),
        "lines": body.count(b"\r\n"),
        "crlf": body.count(b"\r\n"),
        "barelf": len(re.findall(rb"(?<!\r)\n", body)),
        "rc": proc.returncode,
        "sha256": hashlib.sha256(body).hexdigest().upper(),
    }


def measure_battery():
    body = read_bytes(BATTERY)
    return {
        "bytes": len(body),
        "crlf": body.count(b"\r\n"),
        "barelf": len(re.findall(rb"(?<!\r)\n", body)),
        "sha256": hashlib.sha256(body).hexdigest().upper(),
    }


def window(text, anchor, span=420):
    """The text around an anchor, so a token is checked where it BELONGS, not anywhere in the file."""
    at = text.find(anchor)
    if at < 0:
        return None
    return text[max(0, at - span):at + span]


def check(where, tokens):
    if where is None:
        failures.append("the anchor sentence is GONE from AGENTS.md -- the pin cannot be checked")
        return
    for token in tokens:
        ok = token in where
        say("    %-46s %s" % (token, str(ok).lower()))
        if not ok:
            failures.append("AGENTS.md does not carry %r at its anchor" % (token,))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true",
                        help="control: check a COPY with one pinned digit moved -- must go RED")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    text = measure_doc(AGENTS).decode("utf-8", errors="replace")
    help_facts = measure_help()
    battery_facts = measure_battery()
    say("measured run.cmd --help: %(bytes)d B, %(lines)d lines, %(crlf)d CRLF / %(barelf)d bare LF, rc=%(rc)d" % help_facts)
    say("  sha256=%(sha256)s" % help_facts)
    say("measured _main/_audit-verify-all.cmd: %(bytes)d B, %(crlf)d CRLF / %(barelf)d bare LF" % battery_facts)
    say("  sha256=%(sha256)s" % battery_facts)
    if args.neg_arm:
        # The control must MUTATE the doc, and it must say so when it cannot: the first version of
        # this arm matched `is **(\d+) B`, but the shipped sentence bolds from "the SIZE here was
        # stale" onwards, so the regex matched NOTHING and the control reported "0 failure(s) ...
        # cannot say NO" instead of quietly passing. An unmutable control is an INVALID control.
        pattern = r"(re-measured 2026-10-12 the output is )(\d+) B"
        matches = len(re.findall(pattern, text))
        moved = re.sub(pattern, lambda m: m.group(1) + str(int(m.group(2)) + 1) + " B", text, count=1)
        say("  --neg-arm: anchor matches=%d changed=%s (0 and the control is INVALID)"
            % (matches, str(moved != text).lower()))
        if matches == 0 or moved == text:
            print("AGENTS-PINS CONTROL INVALID -- the mutation anchor is gone from the doc")
            return 5
        text = moved
    say("PIN 1 -- the run.cmd --help sentence:")
    anchor = window(text, "re-measured 2026-10-12 the output is")
    check(anchor, ["%d B" % help_facts["bytes"], "%d lines" % help_facts["lines"],
                   "%d CRLF" % help_facts["crlf"], "%d bare LF" % help_facts["barelf"],
                   "rc %d" % help_facts["rc"], help_facts["sha256"]])
    say("PIN 2 -- the _audit-verify-all.cmd corrections row:")
    # The FIRST occurrence of a filename is not the row that pins it: this file names the battery in
    # the owner-order section too, and my first version anchored there and reported both tokens as
    # missing. Scan EVERY occurrence and accept the tokens in ANY scoped window; a name that pins its
    # own numbers anywhere in the file is what rule 2 asks for.
    hits = []
    at = text.find("_audit-verify-all.cmd")
    while at >= 0:
        hits.append(text[max(0, at - 700):at + 700])
        at = text.find("_audit-verify-all.cmd", at + 1)
    say("    occurrences of the name: %d" % len(hits))
    for token in ("%d B" % battery_facts["bytes"], "%d CRLF" % battery_facts["crlf"]):
        ok = any(token in hit for hit in hits)
        say("    %-46s %s" % (token, str(ok).lower()))
        if not ok:
            failures.append("AGENTS.md does not carry %r in any window around the battery name" % (token,))
    if args.neg_arm:
        say("CONTROL: %d failure(s) on the mutated copy (must be > 0)" % len(failures))
        print("AGENTS-PINS CONTROL " + ("PASS" if failures else "FAIL -- the gate cannot say NO"))
        return 0 if failures else 4
    for row in failures:
        say("FAIL " + row)
    verdict = "PASS" if not failures else "FAIL"
    print("AGENTS-PINS %s -- %d pin(s) checked live, %d failure(s)" % (verdict, 2, len(failures)))
    print("VERDICT: " + verdict)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())