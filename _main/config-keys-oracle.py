"""ORACLE for `worker/config.json`: every shipped leaf key has a READER, and the
fallback model agrees with the configured one.

Why this exists (ticket #614; `docs/audit/model-config.md` §6.1/§6.3): seven keys
in `worker/config.json` were read by NOBODY, and `DEFAULT_MODEL` named a different
export (…-int4) than the config did (…-int8), so deleting `model.dir` silently
substituted a smaller model. Neither defect could go RED anywhere: no gate checked
that a shipped key reaches a consumer, and no gate compared the two model names.
The audit's own SELF-AUDIT named this checkbox as the thing it could not land.

WHAT IT ASSERTS
  1. For every leaf key in config.json (keys starting with `_` are comments and are
     skipped), there is at least one ACCESS FORM in the worker code:
     `.get("<key>")` or `["<key>"]`. Zero hits, and the key is not on the
     allow-list below, is RED.
  2. `DEFAULT_MODEL` (the model used when neither `--model` nor `model.dir` names
     one) resolves to the SAME directory as `config.model.dir`. A mismatch is RED.

THE LIMIT OF CHECK 1, STATED: this is a STRING census, not a dataflow proof. A zero
hit means "no string match for this key in the worker sources" — which is exactly
the defect class that was shipped, but a key read through an indirect path (a
variable built from a string) would be reported RED even though it is read. That
failure direction is chosen on purpose: a false RED costs one grep, a false green
shipped seven dead keys.

`--selftest` plants one inert key and one model-name mismatch and requires the
oracle to go RED on both — the oracle must be shown able to fail.

Exit codes: 0 PASS, 1 RED, 2 setup error.
No window: pure file reads, nothing spawned.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER_DIR = os.path.join(REPO, "worker")
CONFIG = os.path.join(WORKER_DIR, "config.json")

# A key with no reader is RED unless it is named here. Keep this list SHORT and
# justified: it is the list of keys that are deliberately not read.
ALLOW_INERT = {}

# Directories under worker/ that are not the shipped code (mutant copies, probes).
SKIP_DIRS = {"runs", "_probe", "__pycache__"}


def leaf_keys(d, prefix=""):
    for k, v in d.items():
        if k.startswith("_"):
            continue
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from leaf_keys(v, path + ".")
        else:
            yield path, k


def worker_sources():
    out = []
    for root, dirs, files in os.walk(WORKER_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn.endswith(".py"):
                out.append(os.path.join(root, fn))
    return out


def access_forms(key):
    return (
        re.compile(r'\.get\(\s*["\']' + re.escape(key) + r'["\']'),
        re.compile(r'\[\s*["\']' + re.escape(key) + r'["\']\s*\]'),
    )


def consumers(key, sources):
    hits = []
    forms = access_forms(key)
    for path in sources:
        try:
            text = io.open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(f.search(line) for f in forms):
                hits.append((os.path.relpath(path, REPO), i, line.strip()))
    return hits


def default_model_name():
    """Import the worker's own constant (module import is side-effect free)."""
    sys.path.insert(0, WORKER_DIR)
    import sotto_worker as w  # noqa: E402
    return os.path.basename(os.path.normpath(w.DEFAULT_MODEL))


def check(cfg, default_name):
    findings = []
    sources = worker_sources()
    for path, key in leaf_keys(cfg):
        hits = consumers(key, sources)
        if not hits and key not in ALLOW_INERT:
            findings.append(
                f"INERT KEY: {path!r} (json key {key!r}) has 0 access forms "
                f'(.get("{key}") / ["{key}"]) in worker/**/*.py'
            )
        else:
            print(f"  key {path:28} -> {len(hits)} consumer(s)"
                  + (f"  first: {hits[0][0]}:{hits[0][1]}" if hits else "  (allow-listed)"))
    want = os.path.basename(os.path.normpath(cfg["model"]["dir"]))
    got = default_name
    if want != got:
        findings.append(
            f"DEFAULT_MODEL DISAGREES: code fallback {got!r} != config model.dir {want!r}"
        )
    else:
        print(f"  DEFAULT_MODEL agrees with config.model.dir: {got}")
    return findings


def selftest(cfg):
    ok = True
    print("== selftest 1: an inert key must be RED ==")
    bad = json.loads(json.dumps(cfg))
    bad.setdefault("output", {})["definitely_inert"] = 1
    f = check(bad, default_model_name())
    for x in f:
        print("  RED:", x)
    fired = any("definitely_inert" in x for x in f)
    print("  planted key reported RED:", fired, "->", "ok" if fired else "WRONG")
    ok = ok and fired

    print("== selftest 2: a DEFAULT_MODEL mismatch must be RED ==")
    f2 = check(cfg, "nemotron-3.5-asr-streaming-0.6b-int4")
    for x in f2:
        print("  RED:", x)
    fired2 = any("DISAGREES" in x for x in f2)
    print("  planted mismatch reported RED:", fired2, "->", "ok" if fired2 else "WRONG")
    ok = ok and fired2

    print("== selftest 3: the shipped config must be GREEN ==")
    f3 = check(cfg, default_model_name())
    green = not f3
    print("  shipped config GREEN:", green, "->", "ok" if green else "WRONG")
    ok = ok and green
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(CONFIG):
        print(f"setup error: no {CONFIG}")
        return 2
    cfg = json.load(io.open(CONFIG, encoding="utf-8"))
    if args.selftest:
        return selftest(cfg)

    print(f"# config-keys-oracle  {CONFIG}")
    findings = check(cfg, default_model_name())
    for x in findings:
        print("RED:", x)
    print("VERDICT:", "PASS" if not findings else "RED")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
