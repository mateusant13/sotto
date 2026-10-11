"""ARM: the benign silence heartbeat tells the TRUTH and ages its evidence.

MEASURED DEFECT this arm pins (2026-10-11): _on_silence re-publishes the stored
no-audio evidence every silence window (2 818 BRIDGE_SILENT_BENIGN lines in one
live log), and the panel body it sent said the worker "measured every tap it
opened below the peak floor" while the evidence printed beside it read
peak=0.925995 floor=0.002 -- ABOVE the floor. The shell own docstring already
says reason=flat means "nothing transcribable in this window", not "below the
floor". Two cures, both pinned here: the body says what flat means, and the
replay carries evidence_age_s / evidenceAgeS so a stale replay is visible as one.

THREE ARMS, one of them a negative control:
  A  evidence measured 42.5 s ago -> log and state carry ~42.5, body honest
  B  evidence NEVER measured (age 0.0) -> no age is invented, body says no evidence
  C  evidence measured 1.0 s ago -> ~1.0, which proves the number is DERIVED
     from the stamp and not a constant that happens to match arm A

Run: py -3 _main/benign-status-arm-oracle.py
Exit: 0 GREEN, 1 RED (a claim above is false), 2 the arm could not run.
"""
import os
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBVIEW = os.path.join(ROOT, "app", "webview")
sys.path.insert(0, WEBVIEW)

import sotto_webview as shell  # noqa: E402

EVIDENCE = "device-rotated reason=flat peak=0.925995 floor=0.002"
OLD_LIE = "measured every tap it opened below the"


def _bridge(age_s):
    log = []
    status = {}
    br = shell.WorkerBridge(
        command=[sys.executable, "-c", "pass"],
        worker_path=os.path.join(ROOT, "worker", "sotto_worker.py"),
        device=None, capture_mode="loopback", log=log.append,
        on_caption=None, on_status=None, on_stats=None, on_meter=None,
        silence_ms=30000, backoff_base=2.0, backoff_max=30.0)
    br.child = types.SimpleNamespace(pid=4242)
    br.stopped = False
    br.pending_error = None
    br.restarts = 0
    br.no_audio = True
    br.no_audio_evidence = EVIDENCE if age_s is not None else None
    br.no_audio_evidence_at = 0.0 if age_s is None else time.monotonic() - age_s
    br._arm_silence = lambda: None
    br._bridge_status = lambda text, kind, info, state: status.update(
        {"text": text, "kind": kind, "info": info, "state": state})
    br._on_silence()
    line = [x for x in log if x.startswith("BRIDGE_SILENT_BENIGN")]
    return (line[-1] if line else ""), status


def _age_in(line):
    m = re.search(r"evidence_age_s=([0-9.]+|None)", line)
    return m.group(1) if m else "MISSING"


def main():
    failures = []
    facts = {}

    def want(label, got, ok, expected):
        facts[label] = got
        if not ok:
            failures.append("%s: got %r, expected %s" % (label, got, expected))

    try:
        line, st = _bridge(42.5)
    except Exception as exc:
        print("ARM COULD NOT RUN: %r" % (exc,))
        return 2
    info = st.get("info") or {}
    body = str(info.get("body") or "")
    age = _age_in(line)
    want("A.log.age", age, age != "MISSING" and 42.0 <= float(age) <= 43.0, "~42.5")
    want("A.state.age", info.get("evidenceAgeS"),
         isinstance(info.get("evidenceAgeS"), float)
         and 42.0 <= info.get("evidenceAgeS") <= 43.0, "~42.5 (a number)")
    want("A.state.evidence", info.get("evidence"), info.get("evidence") == EVIDENCE,
         EVIDENCE)
    want("A.state", st.get("state"), st.get("state") == shell.NO_AUDIO_STATE,
         shell.NO_AUDIO_STATE)
    want("A.body.names_flat", "reason=flat means" in body, "reason=flat means" in body,
         "True (the body says what flat means)")
    want("A.body.negates_floor_lie", "NOT \"below the peak floor\"" in body,
         "NOT \"below the peak floor\"" in body, "True")
    want("A.body.old_lie_absent", OLD_LIE in body, OLD_LIE not in body, "False")
    want("A.body.carries_age", "measured 42" in body, "measured 42" in body, "True")

    try:
        line_b, st_b = _bridge(None)
    except Exception as exc:
        print("ARM B COULD NOT RUN: %r" % (exc,))
        return 2
    info_b = st_b.get("info") or {}
    body_b = str(info_b.get("body") or "")
    want("B.log.age", _age_in(line_b), _age_in(line_b) == "None", "None")
    want("B.state.age", info_b.get("evidenceAgeS"),
         info_b.get("evidenceAgeS") is None, "None (never measured)")
    want("B.body.no_invented_age", "measured" in body_b, "measured" not in body_b,
         "False (no age is invented)")
    want("B.body.says_no_evidence", "no evidence" in body_b, "no evidence" in body_b,
         "True")

    try:
        line_c, st_c = _bridge(1.0)
    except Exception as exc:
        print("ARM C COULD NOT RUN: %r" % (exc,))
        return 2
    age_c = _age_in(line_c)
    want("C.log.age", age_c, age_c != "MISSING" and 0.5 <= float(age_c) <= 2.0, "~1.0")
    want("C.age.is.derived", (age, age_c), age != age_c,
         "two different inputs give two different ages")

    print("BENIGN-STATUS-ARM facts:")
    for k in sorted(facts):
        print("  %-28s %r" % (k, facts[k]))
    if failures:
        print("BENIGN-STATUS-ARM VERDICT: RED")
        for f in failures:
            print("  FAIL " + f)
        return 1
    print("BENIGN-STATUS-ARM VERDICT: GREEN -- 3 arm(s), %d check(s)" % len(facts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
