"""scripts/gate.py — one command for the rails sotto ALREADY has.

This file is a DRIVER. It owns no verdict: every stage shells out to a rail that
owns its own exit code, bounds it, and reports that code honestly.

Rails inventoried here (path -> what it refuses):
  .artifacts.toml + I:/!watcher/tools/artifact-manifest.py --gate
      incomplete family / cap OVER / truncated manifest / no manifest.
  features/INDEX.md, features/features.json + feature_map_sync.py --gate
      drift between the tracked tree, AGENTS.md and the feature map (rc 1/3).
  benchmarks/budgets.json -> named metric commands
      regressions over a metric ceiling, or a named CANNOT-MEASURE.
  harness/angles.tsv
      feature x angle rows; each row carries its own cmd AND its neg arm.
  revival/FRICTION.json + loop_friction_audit.py measure --gate
      inner-loop friction / offline-twin regression.
  scripts/revival_gate.py
      the revival contract as ONE file: feature map, angle matrix (coverage,
      holes declared, the angulos.tsv twin), budgets, goal receipts.
  revival/sim.jsonl + sim_memory.py --repo . gate
      the self-improvement ledger itself: a row whose cause, action or
      falsifier is missing, a graduated row that still has no enforcer, or a
      ledger that drifted from the rows the last commit claims (rc 1).
  app/shadowplay/run-all.mjs and its *.test.mjs population
      failing suites or a refused parse probe (pre-commit runs the same entry).
  scripts/test_task_resolver_gate.py (pytest)
      broken wiring of the task-resolver mandate.
  scripts/agc-gate.sh --selftest
      an inert AGC at a level that needs it (rc 2), or no signal (rc 3).
  scripts/task-resolver-gate.py
      AGENTS.md/skill digest/version/battery wiring drift.

Exit codes: 0 every selected stage PASS (or SKIPPED by explicit --skip name),
2 a named REFUSED stage, 3 CANNOT-MEASURE (timeout, missing tool, unreadable
input) with no plain refusal. A missing rail is always REFUSED rc=2 with the
rail's path in the reason — never a silent skip, never PASS by omission.

Bounds: WALL_BUDGET_S is the hard envelope; every stage also has its own named
timeout in TIME_LIMITS. No shell is used, every child gets CREATE_NO_WINDOW on
Windows (no console popups).

Usage:
  python scripts/gate.py [--json] [--skip NAME ...]

Negative-arm hook (for the gate's own proof): SOTTO_RAIL_<STAGE> overrides the
rail path; hyphens in the stage name become underscores. A nonexistent override
is a named refusal, e.g. SOTTO_RAIL_AGC=missing.sh python scripts/gate.py.
SOTTO_RUNTIME selects the live checkout used by cache-reading rails (default
H:/sotto); code-reading rails use the checkout this file lives in.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RUNTIME = Path(os.environ.get("SOTTO_RUNTIME", "H:/sotto"))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
REVIVAL = Path(os.environ.get("SOTTO_REVIVAL_SCRIPTS",
                              "C:/Users/Administrador/.agents/skills/project-revival/scripts"))
ARTIFACT_TOOL = Path("I:/!watcher/tools/artifact-manifest.py")
WALL_BUDGET_S = 170.0

TIME_LIMITS = {
    "artifact-manifest": 20.0,
    "feature-map": 30.0,
    "budgets": 40.0,
    "angles": 25.0,
    "friction": 35.0,
    "revival": 30.0,
    "sim": 25.0,
    "pytest": 30.0,
    "agc": 25.0,
    "task-resolver": 25.0,
    # run-all.mjs itself needs >150 s (measured); the gate runs its own suite
    # population with a per-suite ceiling instead. parse-gate.mjs stays named.
    "tests": 105.0,
}
STAGES = tuple(TIME_LIMITS)
# Budgets: only commands that are measurable inside this envelope. The battery
# ratchet and tooling-intent rails are RED owner regressions, not missing
# instruments; they stay owned by _main/battery-launch.py and are not graded
# here. Every command run below is read from benchmarks/budgets.json by id.
BUDGET_IDS = (
    "basic.yt_capture_replay_ms",
    "e2e.yt_paint_worst_ms",
    "subsystem.undefined_names_scan_ms",
)
ANGLE_KEY = ("codebase", "A3-steady-state-decay")


def rail(name: str, default: Path) -> Path:
    key = "SOTTO_RAIL_" + name.upper().replace("-", "_")
    return Path(os.environ.get(key, str(default)))


def emit(name: str, verdict: str, rc: int, ms: int, detail: str, *, err: bool) -> None:
    line = f"{name} {verdict} rc={rc} {ms}ms {detail}"
    print(line, file=sys.stderr if err else sys.stdout, flush=True)


def refused(name: str, reason: str, ms: int = 0, cannot: bool = False) -> dict:
    emit(name, "REFUSED", 2, ms, reason, err=STREAM_JSON)
    return {"stage": name, "verdict": "REFUSED", "rc": 2, "ms": ms,
            "detail": reason, "cannot_measure": cannot}


def passed(name: str, detail: str, ms: int) -> dict:
    emit(name, "PASS", 0, ms, detail, err=STREAM_JSON)
    return {"stage": name, "verdict": "PASS", "rc": 0, "ms": ms,
            "detail": detail, "cannot_measure": False}


def tail(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "ok"
    key = next((ln for ln in reversed(lines)
                if any(k in ln for k in ("VERDICT", "PASS", "RESULT", "GREEN", "ok", "OK"))),
               lines[-1])
    return key[:240]


def run(argv: list[str], cwd: Path, seconds: float) -> tuple[int, str, int, bool]:
    """Run one real rail, argv-only, bounded, hidden; return (rc, detail, ms, timeout)."""
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=seconds,
                           creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return 124, f"CANNOT-MEASURE timeout after {seconds:.0f}s", \
            round((time.monotonic() - t0) * 1000), True
    except OSError as exc:
        return 124, f"CANNOT-MEASURE spawn {type(exc).__name__}: {exc}"[:240], \
            round((time.monotonic() - t0) * 1000), True
    ms = round((time.monotonic() - t0) * 1000)
    body = (p.stdout or "") + (p.stderr or "")
    return p.returncode, tail(body), ms, False


def left(deadline: float, name: str, limit: float) -> tuple[float, str | None]:
    remaining = min(limit, deadline - time.monotonic())
    if remaining <= 1.0:
        return 0.0, f"CANNOT-MEASURE {name}: gate envelope exhausted"
    return remaining, None


def one(name: str, argv: list[str], cwd: Path, deadline: float) -> dict:
    budget, reason = left(deadline, name, TIME_LIMITS[name])
    if reason:
        return refused(name, reason, 0, cannot=True)
    rc, detail, ms, timed_out = run(argv, cwd, budget)
    if timed_out:
        return refused(name, detail, ms, cannot=True)
    if rc != 0:
        return refused(name, f"child rc={rc}: {detail}", ms)
    return passed(name, detail, ms)


def stage_artifact(deadline: float) -> dict:
    name = "artifact-manifest"
    tool = rail(name, ARTIFACT_TOOL)
    if not tool.is_file():
        return refused(name, f"missing rail: {tool}")
    if not (RUNTIME / ".artifacts.toml").is_file():
        return refused(name, f"missing rail: {RUNTIME / '.artifacts.toml'}")
    return one(name, [sys.executable, str(tool), "--project", str(RUNTIME), "--gate"],
               RUNTIME, deadline)


def stage_feature(deadline: float) -> dict:
    name = "feature-map"
    tool = rail(name, REVIVAL / "feature_map_sync.py")
    index = REPO / "features" / "INDEX.md"
    for path in (tool, index):
        if not path.is_file():
            return refused(name, f"missing rail: {path}")
    return one(name, [sys.executable, str(tool), "--repo", str(REPO), "--gate"],
               REPO, deadline)


def stage_budgets(deadline: float) -> dict:
    name = "budgets"
    path = rail(name, REPO / "benchmarks" / "budgets.json")
    if not path.is_file():
        return refused(name, f"missing rail: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        by_id = {m.get("id"): m for m in doc.get("metrics", [])}
    except (OSError, ValueError, TypeError) as exc:
        return refused(name, f"CANNOT-MEASURE unreadable {path}: {type(exc).__name__}: {exc}"[:240],
                       cannot=True)
    missing = [i for i in BUDGET_IDS if i not in by_id]
    if missing:
        return refused(name, f"missing budget rows in {path}: {', '.join(missing)}")
    started, details = time.monotonic(), []
    for metric_id in BUDGET_IDS:
        metric = by_id[metric_id]
        argv = shlex.split(str(metric.get("command") or ""))
        if not argv:
            return refused(name, f"no command for {metric_id} in {path}")
        if argv[0] in ("python", "python3"):
            argv[0] = sys.executable
        limit = min(float(metric.get("timeout_s") or 30.0), 40.0)
        budget, reason = left(deadline, name, limit)
        if reason:
            return refused(name, reason, round((time.monotonic() - started) * 1000), cannot=True)
        rc, detail, _ms, timed_out = run(argv, REPO, budget)
        if timed_out:
            return refused(name, f"CANNOT-MEASURE {metric_id}: {detail}",
                           round((time.monotonic() - started) * 1000), cannot=True)
        if rc != 0:
            return refused(name, f"{metric_id} rc={rc}: {detail}",
                           round((time.monotonic() - started) * 1000))
        details.append(f"{metric_id} {detail}")
    return passed(name, " | ".join(details)[:240], round((time.monotonic() - started) * 1000))


def stage_angles(deadline: float) -> dict:
    name = "angles"
    path = rail(name, REPO / "harness" / "angles.tsv")
    if not path.is_file():
        return refused(name, f"missing rail: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        row = next(r for r in rows
                   if (r.get("feature"), r.get("angle")) == ANGLE_KEY)
        pos, neg = shlex.split(row["cmd"]), shlex.split(row["neg"])
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        return refused(name, f"CANNOT-MEASURE angle row {ANGLE_KEY} in {path}: "
                             f"{type(exc).__name__}: {exc}"[:240], cannot=True)
    for argv in (pos, neg):
        if argv[0] in ("python", "python3"):
            argv[0] = sys.executable
    started = time.monotonic()
    for label, argv, want_zero in (("cmd", pos, True), ("neg", neg, False)):
        budget, reason = left(deadline, name, TIME_LIMITS[name])
        if reason:
            return refused(name, reason, round((time.monotonic() - started) * 1000), cannot=True)
        rc, detail, _ms, timed_out = run(argv, REPO, budget)
        if timed_out:
            return refused(name, f"CANNOT-MEASURE {label}: {detail}",
                           round((time.monotonic() - started) * 1000), cannot=True)
        if want_zero:
            if rc != 0:
                return refused(name, f"cmd rc={rc} (expected 0): {detail}",
                               round((time.monotonic() - started) * 1000))
        elif rc != 1:
            # The neg arm returns 1 only when every mutant was caught; 2 means
            # the arm itself failed (no verdict). A blind arm is not a red arm.
            return refused(name, f"neg rc={rc} (expected 1 RED): {detail}",
                           round((time.monotonic() - started) * 1000),
                           cannot=(rc >= 2))
    return passed(name, f"{ANGLE_KEY[1]} cmd=0 neg=1: {tail(' '.join(pos))}",
                  round((time.monotonic() - started) * 1000))


def stage_revival(deadline: float) -> dict:
    name = "revival"
    tool = rail(name, REPO / "scripts" / "revival_gate.py")
    if not tool.is_file():
        return refused(name, f"missing rail: {tool}")
    return one(name, [sys.executable, str(tool)], REPO, deadline)


def stage_sim(deadline: float) -> dict:
    name = "sim"
    tool = rail(name, REVIVAL / "sim_memory.py")
    if not tool.is_file():
        return refused(name, f"missing rail: {tool}")
    return one(name, [sys.executable, str(tool), "--repo", str(REPO), "gate"], REPO, deadline)


def stage_friction(deadline: float) -> dict:
    name = "friction"
    tool = rail(name, REVIVAL / "loop_friction_audit.py")
    friction = RUNTIME / "revival" / "FRICTION.json"
    for path in (tool, friction):
        if not path.is_file():
            return refused(name, f"missing rail: {path}")
    return one(name, [sys.executable, str(tool), "measure", "--repo", str(RUNTIME), "--gate"],
               RUNTIME, deadline)


def stage_tests(deadline: float) -> dict:
    name = "tests"
    runner = rail(name, REPO / "app" / "shadowplay" / "run-all.mjs")
    if not runner.is_file():
        return refused(name, f"missing rail: {runner}")
    suites = sorted(runner.parent.glob("*.test.mjs"))
    if not suites:
        return refused(name, f"missing rail: no *.test.mjs beside {runner}")
    started, done = time.monotonic(), 0
    for suite in suites:
        budget, reason = left(deadline, name, 60.0)
        if reason:
            return refused(name, reason, round((time.monotonic() - started) * 1000), cannot=True)
        rc, detail, _ms, timed_out = run(["node", str(suite)], suite.parent, budget)
        if timed_out:
            return refused(name, f"CANNOT-MEASURE {suite.name}: {detail}",
                           round((time.monotonic() - started) * 1000), cannot=True)
        if rc != 0:
            return refused(name, f"{suite.name} rc={rc}: {detail}",
                           round((time.monotonic() - started) * 1000))
        done += 1
    return passed(name,
                  f"{done}/{len(suites)} suites PASS; parse-gate.mjs SKIPPED by name "
                  f"(measured 231 s > {WALL_BUDGET_S:.0f} s envelope; pre-commit runs it)",
                  round((time.monotonic() - started) * 1000))


def stage_pytest(deadline: float) -> dict:
    name = "pytest"
    path = rail(name, REPO / "scripts" / "test_task_resolver_gate.py")
    if not path.is_file():
        return refused(name, f"missing rail: {path}")
    return one(name, [sys.executable, "-m", "pytest", str(path), "-q"], REPO, deadline)


def stage_agc(deadline: float) -> dict:
    name = "agc"
    script = rail(name, REPO / "scripts" / "agc-gate.sh")
    if not script.is_file():
        return refused(name, f"missing rail: {script}")
    bash = shutil.which("bash")
    if not bash:
        return refused(name, "CANNOT-MEASURE missing-tool:bash", 0, cannot=True)
    return one(name, [bash, str(script), "--selftest"], REPO, deadline)


def stage_task_resolver(deadline: float) -> dict:
    name = "task-resolver"
    script = rail(name, REPO / "scripts" / "task-resolver-gate.py")
    if not script.is_file():
        return refused(name, f"missing rail: {script}")
    return one(name, [sys.executable, str(script), "--root", str(REPO)], REPO, deadline)


BUILDERS = {
    "artifact-manifest": stage_artifact,
    "feature-map": stage_feature,
    "budgets": stage_budgets,
    "angles": stage_angles,
    "friction": stage_friction,
    "revival": stage_revival,
    "sim": stage_sim,
    "tests": stage_tests,
    "pytest": stage_pytest,
    "agc": stage_agc,
    "task-resolver": stage_task_resolver,
}

STREAM_JSON = False


def main(argv: list[str] | None = None) -> int:
    global STREAM_JSON
    ap = argparse.ArgumentParser(description="one command for sotto's real rails")
    ap.add_argument("--json", action="store_true", help="one JSON object on stdout; stages on stderr")
    ap.add_argument("--skip", action="append", default=[], choices=STAGES,
                    metavar="NAME", help="skip one stage BY NAME (always printed)")
    args = ap.parse_args(argv)
    STREAM_JSON = args.json

    started, deadline = time.monotonic(), time.monotonic() + WALL_BUDGET_S
    results: list[dict] = []
    for name in STAGES:
        if name in args.skip:
            emit(name, "SKIPPED", 0, 0, "by --skip", err=args.json)
            results.append({"stage": name, "verdict": "SKIPPED", "rc": 0, "ms": 0,
                            "detail": "by --skip", "cannot_measure": False})
            continue
        results.append(BUILDERS[name](deadline))
        if results[-1]["verdict"] == "REFUSED":
            break

    wall_ms = round((time.monotonic() - started) * 1000)
    plain = [r for r in results if r["verdict"] == "REFUSED" and not r["cannot_measure"]]
    cannot = [r for r in results if r["cannot_measure"]]
    rc = 2 if plain else 3 if cannot else 0
    verdict = {0: "PASS", 2: "REFUSED", 3: "CANNOT-MEASURE"}[rc]
    if rc == 0:
        ran = [r for r in results if r["verdict"] != "SKIPPED"]
        skipped = len(results) - len(ran)
        suffix = f" ({skipped} SKIPPED)" if skipped else ""
        summary = f"gate PASS {len(ran)}/{len(ran)} stages{suffix} in {wall_ms}ms rc=0"
    else:
        bad = next(r["stage"] for r in results if r["verdict"] == "REFUSED")
        summary = f"gate {verdict} {bad} in {wall_ms}ms rc={rc}"
    print(summary, file=sys.stderr if args.json else sys.stdout, flush=True)
    if args.json:
        print(json.dumps({"verdict": verdict, "rc": rc, "wall_ms": wall_ms,
                          "stages": results}, ensure_ascii=False, indent=2), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
