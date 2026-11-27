#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/test_gate.py -- the unified driver's verdicts are testable.

The driver owns no rail verdict, but it does own the summary line and the
negative-arm contract. Three ways it can lie, one test each:

  1. a CANNOT-MEASURE gate printed as REFUSED;
  2. an explicit --skip counted as a PASS in the stage ratio;
  3. a neg arm whose rc=2 (no verdict) accepted as a RED.

    python -3 scripts/test_gate.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
GATE_PATH = os.path.join(HERE, "gate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("gate_under_test", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = _load_gate()


def _fast(name):
    def build(_deadline):
        return GATE.passed(name, "ok", 1)
    return build


def _fast_builders():
    return {n: _fast(n) for n in GATE.STAGES}


def _run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = GATE.main(argv)
    return rc, out.getvalue()


class GateSummaryTest(unittest.TestCase):
    def test_cannot_measure_summary_is_not_printed_as_refused(self):
        builders = _fast_builders()
        builders["agc"] = (lambda _deadline: GATE.refused(
            "agc", "CANNOT-MEASURE missing-tool:bash", 0, cannot=True))
        with patch.dict(GATE.BUILDERS, builders):
            rc, out = _run([])
        self.assertEqual(rc, 3)
        summary = out.strip().splitlines()[-1]
        self.assertTrue(summary.startswith("gate CANNOT-MEASURE agc "), summary)
        self.assertNotIn("gate REFUSED", summary)

    def test_skipped_stages_are_not_counted_as_passes(self):
        with patch.dict(GATE.BUILDERS, _fast_builders()):
            rc, out = _run(["--skip", "budgets", "--skip", "tests"])
        self.assertEqual(rc, 0)
        summary = out.strip().splitlines()[-1]
        ran = len(GATE.STAGES) - 2
        self.assertIn(f"gate PASS {ran}/{ran} stages (2 SKIPPED)", summary)
        self.assertNotIn(f"{len(GATE.STAGES)}/{len(GATE.STAGES)}", summary)

    def test_angles_neg_arm_without_verdict_is_not_a_red(self):
        calls = []

        def fake_run(argv, cwd, seconds):
            calls.append(argv)
            if len(calls) == 1:
                return 0, "FIXTURE VERDICT: PASS", 10, False
            return 2, "NEG-ARM VERDICT: FAIL (2/7 mutants caught)", 10, False

        with patch.object(GATE, "run", side_effect=fake_run):
            result = GATE.stage_angles(GATE.time.monotonic() + 100)
        self.assertEqual(result["verdict"], "REFUSED")
        self.assertTrue(result["cannot_measure"])
        self.assertIn("neg rc=2", result["detail"])


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=2).result.wasSuccessful() else 1)
