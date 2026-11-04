#!/usr/bin/env python3
"""Append-only proof ledger for the Bend law gate (bend_core/ + tools/bend_verify.sh).

Why this exists
---------------
Git versions the CLAIM and the PROOF text. A proof result is not a function of that
text alone: it also depends on the kernel (`lean --version`), the translator
(`bend version`), the import closure, the gate's own six checks and their pinned
lists, and the environment (WSL distro, cwd, PATH). "It was green on that commit"
is therefore not reproducible from the commit. This ledger records one JSONL line
per gate run with those inputs hashed and the judge named, so a later reader can
answer *when did this become green, with which kernel, over which files*.

Design rules
------------
* append-only: never rewrites or deletes a line
* classify, do not guess: a missing judge or a translation limit is
  `infrastructure`, never `red`
* bounded output: stdout/stderr tails are capped, never the whole log
* no dependency beyond the standard library

Usage
-----
    python tools/bend_proof_ledger.py                 # run the gate, append one record
    python tools/bend_proof_ledger.py --verify        # check recorded greens still match on-disk hashes
    python tools/bend_proof_ledger.py --self-test     # ledger fixtures (see below)

Exit codes: 0 green, 2 red, 4 infrastructure, 1 ledger/verify failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEDGER_DIR = REPO / ".bend-ledger"
LEDGER = LEDGER_DIR / "runs.jsonl"
GATE = REPO / "tools" / "bend_verify.sh"
WATCHED = ("bend_core/LAWS.bend", "bend_core/PROOF.bend", "bend_core/model.py", "bend_core/NEGATIVE_count_due_empty.bend", "bend_core/NEGATIVE_count_due_monotone.bend", "bend_core/NEGATIVE_count_due_one_word.bend", "bend_core/NEGATIVE_count_due_only.bend", "bend_core/NEGATIVE_display_clean_before_new_source.bend", "bend_core/NEGATIVE_epoch_monotonic.bend", "bend_core/NEGATIVE_live_flag.bend", "bend_core/NEGATIVE_live_flag_before.bend", "bend_core/NEGATIVE_no_cross_source_paint.bend", "bend_core/NEGATIVE_of_bool_agrees.bend", "bend_core/NEGATIVE_revealed_flag.bend", "bend_core/NEGATIVE_window_rows_capacity.bend", "bend_core/NEGATIVE_window_rows_live.bend", "bend_core/NEGATIVE_window_rows_min.bend", "tools/bend_verify.sh")
GATE_VERSION = "1"  # bump when a structural check is added/removed
TAIL = 4000  # bytes kept from each stream


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        return out.stdout.strip()
    except Exception:
        return ""


def _hash_files() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in WATCHED:
        path = REPO / rel
        rows.append({"path": rel, "sha256": _sha256(path) if path.is_file() else "MISSING"})
    return rows


JUDGE_BEND = re.compile(r"^== bend: (.+?)(?: ==)?$", re.M)
JUDGE_LEAN = re.compile(r"^== lean: (.+?)(?: ==)?$", re.M)
DISTRO = re.compile(r"^== bend laws gate \(distro: (\S+)\) ==", re.M)


def parse_gate_output(text: str) -> dict[str, Any]:
    """Turn the gate's own stdout into structured checks. Never infers a verdict."""
    checks: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("PASS: ", "FAIL: ", "SKIP: ")):
            kind, _, rest = line.partition(": ")
            checks.append({"result": kind.lower(), "what": rest})
    bend = JUDGE_BEND.search(text)
    lean = JUDGE_LEAN.search(text)
    distro = DISTRO.search(text)
    had_verdict = "ALL PROOFS CHECK" in text
    translated_limit = bool(re.search(r"translation|not supported|TT ", text, re.I))
    return {
        "judge": {"bend": bend.group(1).strip() if bend else None, "lean": lean.group(1).strip() if lean else None},
        "distro": distro.group(1) if distro else None,
        "checks": checks,
        "had_verdict": had_verdict,
        "translation_limit_seen": translated_limit,
    }


def classify(parsed: dict[str, Any], rc: int) -> str:
    """green | red | infrastructure — the only three outcomes this ledger records."""
    if parsed["judge"]["bend"] is None or parsed["judge"]["lean"] is None:
        return "infrastructure"
    if rc == 4:
        return "infrastructure"
    if not parsed["had_verdict"] and parsed["translation_limit_seen"]:
        return "infrastructure"
    if rc == 0 and parsed["had_verdict"] and all(c["result"] == "pass" for c in parsed["checks"]):
        return "green"
    return "red"


def run_gate() -> tuple[int, str]:
    start = time.time()
    proc = subprocess.run(
        ["bash", str(GATE)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "BEND_NO_TELEMETRY": "1"},
    creationflags=subprocess.CREATE_NO_WINDOW)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "") + f"\n[wall_s] {time.time() - start:.2f}"


def append(record: dict[str, Any]) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def record(no_run: bool = False) -> int:
    if no_run:
        return 1
    rc, text = run_gate()
    parsed = parse_gate_output(text)
    verdict = classify(parsed, rc)
    rows = _hash_files()
    laws = sorted(set(re.findall(r"^law\s+([A-Za-z0-9_.]+):", (REPO / "bend_core/LAWS.bend").read_text(encoding="utf-8"), re.M))) if (REPO / "bend_core/LAWS.bend").is_file() else []
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": verdict,
        "gate_rc": rc,
        "gate_version": GATE_VERSION,
        "judge": parsed["judge"],
        "distro": parsed["distro"],
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_git("status", "--porcelain")),
        },
        "files": rows,
        "laws": laws,
        "checks": parsed["checks"],
        "translation_limit_seen": parsed["translation_limit_seen"],
        "env": {"cwd": str(REPO)},
        "wall_s": float(re.search(r"\[wall_s\] ([\d.]+)", text).group(1)) if "[wall_s]" in text else None,
        "tail": text[-TAIL:],
    }
    append(entry)
    print(f"ledger: {verdict} rc={rc} judge={entry['judge']['bend']} laws={len(laws)} -> {LEDGER.relative_to(REPO)}")
    print("  " + "\n  ".join(f"{c['result']}: {c['what']}" for c in parsed["checks"][-6:]))
    return {"green": 0, "red": 2, "infrastructure": 4}[verdict]


def verify() -> int:
    """Every recorded green must still describe the files on disk, or be explainable."""
    if not LEDGER.is_file():
        print("ledger: no runs recorded")
        return 1
    now = {row["path"]: row["sha256"] for row in _hash_files()}
    bad = 0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            print("ledger: unparsable line skipped")
            bad += 1
            continue
        if entry.get("verdict") != "green":
            continue
        drift = [f["path"] for f in entry.get("files", []) if now.get(f["path"]) != f["sha256"]]
        if drift:
            print(f"ledger: green at {entry['ts']} ({entry['git']['commit'][:12]}) no longer matches on disk: {drift}")
            bad += 1
    print(f"ledger: verify {'ok' if bad == 0 else f'{bad} drift(s)'}")
    return 0 if bad == 0 else 1


def self_test() -> int:
    ok = True

    def check(name: str, got: Any, want: Any) -> None:
        nonlocal ok
        if got != want:
            ok = False
            print(f"FAIL {name}: got {got!r} want {want!r}")
        else:
            print(f"PASS {name}")

    green = "== bend: bend 2.0.39 ==\n== lean: Lean (version 4.34.0) ==\nALL PROOFS CHECK\nPASS: a\nPASS: b\n"
    check("green", classify(parse_gate_output(green), 0), "green")
    red = "== bend: bend 2.0.39 ==\n== lean: Lean (version 4.34.0) ==\nSOME PROOFS FAIL\nFAIL: a\n"
    check("red", classify(parse_gate_output(red), 2), "red")
    nojudge = "ALL PROOFS CHECK\nPASS: a\n"
    check("no judge -> infrastructure", classify(parse_gate_output(nojudge), 0), "infrastructure")
    limit = "== bend: bend 2.0.39 ==\n== lean: Lean (version 4.34.0) ==\nError: translation limit\n"
    check("translation limit -> infrastructure", classify(parse_gate_output(limit), 2), "infrastructure")
    check("rc4 -> infrastructure", classify(parse_gate_output(green), 4), "infrastructure")
    mixed = green.replace("PASS: b", "SKIP: b")
    check("a skipped check is not green", classify(parse_gate_output(mixed), 0), "red")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="check recorded greens against on-disk hashes")
    ap.add_argument("--self-test", action="store_true", help="ledger fixtures; no gate is run")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.verify:
        return verify()
    return record()


if __name__ == "__main__":
    sys.exit(main())
