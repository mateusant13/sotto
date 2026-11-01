#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: prova do proprio portao task-resolver (positivo, negativo atribuivel, fail-safe); nasce com o portao que testa
"""test_task_resolver_gate.py -- o portao do mandato task-resolver sabe dizer NAO, e diz ONDE.

Tres coisas que um portao tem de provar sobre si mesmo, e um teste cada:

  1. PASS no repo real            -- senao o verde nao existe
  2. NEG-ARM PASS por mutante     -- e o check NOMEADO tem de estar entre os que recusaram;
                                    um mutante que cai por outro braco nao prova este braco
  3. NO-VERDICT (rc=2) numa raiz sem a skill -- um instrumento que nao pode julgar nao da
                                    verde nem vermelho (`task-resolver`, vocabulario)

    python scripts\\test_task_resolver_gate.py          # unittest, rc=0 quando os 3 provam
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE_PATH = os.path.join(HERE, "task-resolver-gate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("task_resolver_gate_under_test", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = _load_gate()


def _run(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = GATE.main(argv)
    return rc, buffer.getvalue()


class TaskResolverGateTest(unittest.TestCase):
    def test_gate_passes_on_repo_root(self):
        rc, out = _run(["--root", ROOT])
        self.assertEqual(rc, 0, "o portao tem de passar no repo real:\n%s" % out)
        self.assertIn("BATTERY-VERDICT task-resolver-gate PASS", out)
        self.assertIn("checks=%d fail=0" % len(GATE.CHECKS), out)

    def test_every_mutation_is_attributable_to_its_named_check(self):
        for name, _mutator, expected in GATE.MUTATIONS:
            with self.subTest(mutation=name):
                rc, out = _run(["--root", ROOT, "--mutation", name])
                self.assertEqual(rc, 1, "mutacao %s devia sair rc=1 POR DESENHO:\n%s" % (name, out))
                self.assertIn("NEG-ARM PASS", out)
                self.assertIn("[esperado: %s]" % expected, out)
                self.assertIn("MUTATION %-24s NEG-ARM PASS" % name, out)

    def test_missing_skill_is_no_verdict_not_green(self):
        tmp = tempfile.mkdtemp(prefix="trg-nov-", dir=os.environ.get("TMPDIR") or None)
        try:
            for rel in GATE.COPY_FILES:
                if rel == GATE.SKILL_REL:
                    continue
                target = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(target) or tmp, exist_ok=True)
                shutil.copyfile(os.path.join(ROOT, rel), target)
            rc, out = _run(["--root", tmp])
            self.assertEqual(rc, 2, "raiz sem a skill tem de ser NO-VERDICT:\n%s" % out)
            self.assertIn("NO-VERDICT", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_pinned_digest_matches_the_skill_actually_read(self):
        """O pin nao e decoracao: e o mesmo sha256 que o TODO desta lane declara."""
        self.assertEqual(len(GATE.PINNED_SHA256), 64)
        self.assertEqual(GATE.PINNED_SHA256, GATE.PINNED_SHA256.lower())
        body = open(os.path.join(ROOT, GATE.SKILL_REL), "rb").read()
        import hashlib
        self.assertEqual(hashlib.sha256(body).hexdigest(), GATE.PINNED_SHA256)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=2).result.wasSuccessful() else 1)
