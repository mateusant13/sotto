#!/usr/bin/env python3
"""One gate for the revival contract: feature map, angle matrix, metric budgets.

Run from anywhere: `python scripts/revival_gate.py`.  Exit 0 is green; exit 2
names the FIRST problem.  No check here writes to the repository.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_GLOBAL_ROOT = ROOT
FEATURE_SYNC = Path(
    "C:/Users/Administrador/.agents/skills/project-revival/scripts/feature_map_sync.py"
)
ANGLES = ROOT / "harness" / "angles.tsv"  # resolved per run by _set_root()
BUDGETS = ROOT / "benchmarks" / "budgets.json"  # resolved per run by _set_root()
GOAL = ROOT / "revival" / "GOAL.json"  # resolved per run by _set_root()
COLUMNS = ("feature", "angle", "cmd", "expect", "neg", "note")
# sotto's matrix carries a 7th column, `pre`: the precondition a LIVE row
# needs before its command means anything (see AGENTS.md, "A LIVE row carries
# its environment in a `pre` column"). The first six are the fleet contract;
# an extra one is a DECLARED extension, never a silent one.
EXTRA_COLUMNS = ("pre",)
# sotto's matrix carries a 7th column, `pre`: the precondition a LIVE row needs
# before its command means anything (see AGENTS.md). The first six are the
# fleet contract; an extra one is a declared extension, never a silent one.
EXTRA_COLUMNS = ("pre",)
REQUIRED = ("feature", "angle", "cmd", "expect", "neg", "note")
# Two class families are in use: A<n> (product angles) and L<n> (the live
# angles a lane can reach). A new family is a deliberate edit here, not a
# silent string.
ANGLE_RE = re.compile(r"^[A-Z]\d+-[a-z0-9]+(?:-[a-z0-9]+)*$")
PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/.-])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:jsonl|json|tsv|py|md))(?::\d+)?"
)
# The neg-arm re-runs this gate as a child once per mutant. One child is a
# local file check, not a product workload: 30 s is a DECLARED ceiling that
# keeps the whole control far below the battery's 240 s step deadline. A hung
# child must fail the control, never pin the battery waiting on it.
NEG_ARM_CHILD_TIMEOUT_S = 30.0


def _fail(message: str) -> int:
    print("REVIVAL GATE FAIL: " + message)
    return 2


def _feature_gate() -> str | None:
    """Run feature_map_sync.py --gate in-process and return its first problem.

    Only its commit-subject decoration is skipped: `gate_check` decides from
    tracked file sets and curated fields, never from commit subjects, and the
    200-commit `git log` costs tens of seconds on this box's SMR volume.
    """
    if not FEATURE_SYNC.is_file():
        return f"missing feature sync script: {FEATURE_SYNC}"
    spec = importlib.util.spec_from_file_location("feature_map_sync_gate", FEATURE_SYNC)
    if spec is None or spec.loader is None:
        return f"cannot load {FEATURE_SYNC}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._commit_activity = lambda repo, max_commits=200: (module.Counter(), {})
    # Both helpers only decorate the generated docs. gate_check compares tracked
    # file sets and requires already-curated inputs/outputs, so neither hint is
    # part of its verdict; their git log and per-file stats cost tens of seconds
    # under the launcher's very-low IO priority on this SMR volume.
    module._detect_io_hints = lambda repo, files: ([], [])
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        rc = module.main(["--repo", str(ROOT), "--gate"])
    if rc != 0:
        return f"feature_map_sync.py --gate rc={rc}: {captured.getvalue().strip()[:400]}"
    try:
        verdict = json.loads(captured.getvalue())
    except json.JSONDecodeError as exc:
        return f"feature_map_sync.py --gate emitted non-JSON: {exc}"
    if verdict.get("verdict") != "PASS":
        return f"feature_map_sync.py --gate verdict={verdict.get('verdict')}"
    problems = verdict.get("problems") or []
    if problems:
        return "feature_map_sync.py --gate: " + str(problems[0])
    return None


def _set_root(root: Path) -> None:
    """Point every check at `root`. The population is an ARGUMENT, not the cwd.

    The negative arm needs the same code to judge a mutated copy; without this
    it could only mutate the real tree, which is the defect this file exists to
    refuse one level up.
    """
    global ROOT, ANGLES, BUDGETS, GOAL
    ROOT = root
    ANGLES = root / "harness" / "angles.tsv"
    BUDGETS = root / "benchmarks" / "budgets.json"
    GOAL = root / "revival" / "GOAL.json"


def _angles() -> tuple[str | None, int]:
    """Return (first problem, row count).

    Coverage is checked against the authoritative macro-feature list: every
    row names a real feature, every macro feature owns at least one row, and
    no (feature, angle) pair is repeated.  24 is the shipped floor, not a
    ceiling: adding angles must not vacuously pass by dropping features.
    """
    if not ANGLES.is_file():
        return f"missing {ANGLES.relative_to(ROOT).as_posix()}", 0
    # THE FLEET HAS TWO NAMES FOR THIS FILE: the skill scripts and the AGENTS.md
    # generator say harness/angles.tsv, the fleet census (f6-preflight.py:85)
    # asks for harness/angulos.tsv and prints FALTA when it is absent. A copy
    # would drift, so the second name is a HARD LINK and this check refuses the
    # moment the two stop being the same bytes.
    twin = ROOT / "harness" / "angulos.tsv"
    if not twin.is_file():
        return ("missing harness/angulos.tsv (the census name); create it as a hard link: "
                "os.link('harness/angles.tsv', 'harness/angulos.tsv')"), 0
    if twin.read_bytes() != ANGLES.read_bytes():
        return ("harness/angulos.tsv has DRIFTED from harness/angles.tsv -- re-create the "
                "hard link, never edit the twin"), 0
    features_path = ROOT / "features" / "features.json"
    try:
        features = json.loads(features_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"features/features.json is not usable for angle coverage: {exc}", 0
    macro = {
        str(item.get("id"))
        for item in (features.get("macro_features") or features.get("features") or [])
        if isinstance(item, dict) and item.get("id")
    }
    if not macro:
        return "features/features.json: no feature ids (macro_features or features)", 0
    # DIRECTORIES ARE NOT THE VOCABULARY OF THE ANGLE MATRIX. The rows speak
    # functional names; the map speaks directory names. harness/features-
    # functional.json is the DECLARED translation, and every macro feature it
    # leaves out must carry its reason -- a silent omission would make the
    # coverage check below a lie by construction.
    functional: dict[str, list[str]] = {}
    uncovered: dict[str, str] = {}
    registry = ROOT / "harness" / "features-functional.json"
    if registry.is_file():
        try:
            reg = json.loads(registry.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return f"harness/features-functional.json is not JSON: {exc}", 0
        for item in (reg.get("features") or []):
            if not isinstance(item, dict) or not item.get("id"):
                return "harness/features-functional.json: entry without id", 0
            owners = [str(o) for o in (item.get("owners") or [])]
            if not owners and item.get("scope") != "repo":
                return f"harness/features-functional.json: {item['id']} has no owners", 0
            stray = [o for o in owners if o not in macro]
            if stray:
                return (
                    f"harness/features-functional.json: {item['id']} names "
                    f"non-feature owner(s) {stray}", 0)
            functional[str(item["id"])] = owners
        raw_uncovered = reg.get("uncovered_macro") or {}
        if not isinstance(raw_uncovered, dict):
            return "harness/features-functional.json: uncovered_macro is not an object", 0
        uncovered = {str(k): str(v) for k, v in raw_uncovered.items()}
        for key, why in uncovered.items():
            if key not in macro:
                return (
                    f"harness/features-functional.json: uncovered_macro names "
                    f"unknown feature {key}", 0)
            if len(why.strip()) < 8:
                return f"harness/features-functional.json: uncovered_macro[{key}] has no reason", 0
    known = macro | set(functional)
    reached: set[str] = set()
    text = ANGLES.read_text(encoding="utf-8")
    angles: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    covered: set[str] = set()
    count = 0
    holes = 0
    header_seen = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        cells = [cell.strip() for cell in raw.split("\t")]
        if not header_seen:
            # The fleet template prefixes its header with `#`. This matrix does
            # not, so the first row is recognised by its own names -- a header
            # read as data would become an "unknown feature: feature" verdict.
            header_seen = True
            if [c.casefold() for c in cells[:len(COLUMNS)]] == list(COLUMNS):
                continue
        if len(cells) not in (len(COLUMNS), len(COLUMNS) + len(EXTRA_COLUMNS)):
            return (
                f"harness/angles.tsv:{lineno}: {len(cells)} columns, expected "
                f"{len(COLUMNS)} or {len(COLUMNS) + len(EXTRA_COLUMNS)}",
                count,
            )
        row = dict(zip(COLUMNS, cells))
        hole = row["note"].startswith("HOLE:")
        if hole:
            # A HOLE is a DECLARED absence: no command can fail because no
            # measurement exists, and the row says which population is missing.
            # Deleting it would hide the gap; leaving cmd empty without the
            # marker would let a typo pass as coverage. Same rule this gate's
            # GOAL receipt check already enforces one level up.
            if row["cmd"] or row["neg"]:
                return (
                    f"harness/angles.tsv:{lineno}: HOLE row carries a command; "
                    f"either the arm exists (drop the HOLE:) or it does not (drop the command)",
                    count,
                )
            if len(row["note"]) < 60:
                return f"harness/angles.tsv:{lineno}: HOLE row does not name what is missing", count
            holes += 1
        else:
            for field in REQUIRED:
                if not row[field]:
                    return f"harness/angles.tsv:{lineno}: empty {field}", count
        pair = (row["feature"], row["angle"])
        if pair in pairs:
            return (
                f"harness/angles.tsv:{lineno}: duplicate (feature,angle) "
                f"{pair[0]}/{pair[1]}",
                count,
            )
        pairs.add(pair)
        # An angle NAME is a CLASS in this matrix, not a key: the same
        # A2-known-answer is asked of several features, and the pair
        # (feature, angle) is what must be unique. The label still has to be
        # shaped like a class, so a typo cannot invent a third vocabulary.
        if not ANGLE_RE.match(row["angle"]):
            return (
                f"harness/angles.tsv:{lineno}: angle {row['angle']!r} is not "
                f"shaped like An-<slug>",
                count,
            )
        angles.add(row["angle"])
        if row["feature"] not in known:
            return (
                f"harness/angles.tsv:{lineno}: unknown feature {row['feature']} "
                f"(not a macro feature and not in harness/features-functional.json)",
                count)
        reached.add(row["feature"])
        if row["feature"] in macro:
            covered.add(row["feature"])
        else:
            covered.update(functional.get(row["feature"]) or [])
        if not hole and row["neg"] == row["expect"]:
            return f"harness/angles.tsv:{lineno}: neg equals expect (cannot fail)", count
        for path in PATH_RE.findall(row["cmd"] + " " + row["note"]):
            if not (ROOT / path).is_file():
                return f"harness/angles.tsv:{lineno}: named file missing: {path}", count
        count += 1
    absent = sorted(macro - covered - set(uncovered))
    if absent:
        return (
            "harness/angles.tsv: macro features without an angle row and without a "
            "declared reason (harness/features-functional.json uncovered_macro): "
            + ", ".join(absent),
            count,
        )
    orphan = sorted(set(functional) - reached)
    if orphan:
        return (
            "harness/angles.tsv: functional features with no angle row: "
            + ", ".join(orphan),
            count,
        )
    if count < 24:
        return f"harness/angles.tsv: {count} rows, expected at least 24", count
    print(f"ANGLES HOLES {holes} declared with a named missing population", flush=True)
    if not any(angle.startswith("A3") for angle in angles):
        return "harness/angles.tsv: missing A3 steady-state-decay angle", count
    return None, count


def _budgets() -> tuple[str | None, int]:
    """Return (first problem, metric count)."""
    if not BUDGETS.is_file():
        return "missing benchmarks/budgets.json", 0
    try:
        doc = json.loads(BUDGETS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"benchmarks/budgets.json is not JSON: {exc}", 0
    metrics = doc.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return "benchmarks/budgets.json: metrics missing or empty", 0
    for metric in metrics:
        if not str(metric.get("command") or "").strip():
            return f"benchmarks/budgets.json: metric {metric.get('id', '?')} has empty command", 0
    return None, len(metrics)


def _goal_receipts() -> tuple[str | None, int]:
    """Return (first problem, criteria count).

    A criterion with no receipt is a goal nobody can audit, and a receipt that
    names nothing verifiable is the same defect one level down.  Two exits are
    admissible: a receipt that names something this repository can be asked
    about (an existing file, or a command this box runs), and the literal
    `CANNOT-MEASURE` — which is only admissible when it also names the MISSING
    population, so "we did not measure it" cannot pass as "it is fine".
    """
    if not GOAL.is_file():
        return "missing revival/GOAL.json", 0
    try:
        doc = json.loads(GOAL.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"revival/GOAL.json is not JSON: {exc}", 0
    criteria = doc.get("acceptance")
    if not isinstance(criteria, list) or not criteria:
        return "revival/GOAL.json: acceptance missing or empty", 0
    placeholder = ("todo", "tbd", "placeholder", "skeleton", "xxx", "none recorded")
    for index, item in enumerate(criteria, 1):
        name = str(item.get("id") or f"#{index}")
        if not str(item.get("id") or "").strip():
            return f"revival/GOAL.json: criterion #{index} has no id", 0
        if not str(item.get("text") or "").strip():
            return f"revival/GOAL.json: {name} has no text", 0
        receipt = str(item.get("receipt") or "").strip()
        if not receipt:
            return f"revival/GOAL.json: {name} has no receipt", 0
        low = receipt.casefold()
        for word in placeholder:
            if word in low:
                return f"revival/GOAL.json: {name} receipt is a placeholder ({word})", 0
        if "cannot-measure" in low:
            if "missing population" not in low:
                return f"revival/GOAL.json: {name} says CANNOT-MEASURE without naming the missing population", 0
            continue
        paths = [path for path in PATH_RE.findall(receipt) if (ROOT / path).is_file()]
        has_command = "`python " in receipt
        if not paths and not has_command:
            return f"revival/GOAL.json: {name} receipt names nothing in this repo and no command", 0
    return None, len(criteria)


def _checks(only: str) -> int:
    if only in ("all", "feature"):
        problem = _feature_gate()
        if problem:
            return _fail(problem)
        print("FEATURE SYNC OK")
    if only in ("all", "angles"):
        problem, rows = _angles()
        if problem:
            return _fail(problem)
        print(f"ANGLES OK ({rows} rows, cmd/expect/neg present, files exist)")
    if only in ("all", "budgets"):
        problem, metrics = _budgets()
        if problem:
            return _fail(problem)
        print(f"BUDGETS OK ({metrics} metrics with commands)")
    if only in ("all", "goal"):
        problem, criteria = _goal_receipts()
        if problem:
            return _fail(problem)
        print(f"GOAL OK ({criteria} acceptance criteria carry a verifiable receipt)")
    print("REVIVAL GATE PASS")
    return 0


def _drift_twin(root: Path) -> None:
    """Replace the hard link with a DIFFERENT file: the census would then read
    the old matrix while every repo consumer reads the new one."""
    twin = root / "harness" / "angulos.tsv"
    twin.unlink()
    twin.write_bytes((root / "harness" / "angles.tsv").read_bytes() + b"codebase\tA99-extra\tpython x.py\trc=0\tpython x.py --neg-arm\t" + b"n" * 70 + b"\n")
    _drift_twin.keeps_link = True


MUTATIONS = (
    (
        "a-row-with-no-command-is-not-coverage",
        "empty cmd",
        lambda root: _append_row(root, "codebase\tA99-invented\t\t\t\t" + "n" * 70),
    ),
    (
        "an-undeclared-macro-feature-is-a-gap",
        "without a declared reason",
        lambda root: _drop_uncovered(root, "scripts"),
    ),
    (
        "a-hole-that-carries-a-command-is-not-a-hole",
        "HOLE row carries a command",
        lambda root: _give_hole_a_command(root),
    ),
    (
        "a-twin-that-drifted-is-not-the-same-matrix",
        "DRIFTED",
        _drift_twin,
    ),
)


def _read(root: Path, rel: str) -> tuple[Path, str]:
    path = root / rel
    return path, path.read_bytes().decode("utf-8")


def _append_row(root: Path, row: str) -> None:
    path, text = _read(root, "harness/angles.tsv")
    if not text.endswith("\n"):
        text += "\n"
    path.write_bytes((text + row + "\n").encode("utf-8"))


def _drop_uncovered(root: Path, key: str) -> None:
    path, text = _read(root, "harness/features-functional.json")
    doc = json.loads(text)
    doc.get("uncovered_macro", {}).pop(key, None)
    path.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def _give_hole_a_command(root: Path) -> None:
    path, text = _read(root, "harness/angles.tsv")
    lines = text.split("\n")
    for index, line in enumerate(lines):
        cells = line.split("\t")
        if len(cells) > 5 and cells[5].startswith("HOLE:"):
            cells[2] = "python _main/product-soak-oracle.py"
            lines[index] = "\t".join(cells)
            break
    else:
        raise SystemExit("NEG-ARM cannot build its mutant: no HOLE row in the matrix")
    path.write_bytes("\n".join(lines).encode("utf-8"))


def neg_arm() -> int:
    """Prove the gate can go RED, on a COPY, without touching the real tree.

    A control run on the unmutated copy must pass first: otherwise a temp tree
    that always fails would make every mutant look caught.
    """
    import shutil
    import subprocess
    import tempfile

    copies = ("harness/angles.tsv", "harness/features-functional.json",
              "features/features.json", "benchmarks/budgets.json",
              "revival/GOAL.json")

    def relink(root: Path) -> None:
        """Re-create the twin so a mutant is judged by ITS reason, not by a broken link."""
        twin = root / "harness" / "angulos.tsv"
        if twin.exists():
            twin.unlink()
        try:
            os.link(root / "harness" / "angles.tsv", twin)
        except OSError:
            twin.write_bytes((root / "harness" / "angles.tsv").read_bytes())

    def mirror(root: Path) -> None:
        """Copy the five judged inputs and TOUCH every path the matrix names.

        The mutant must fail for ITS reason: without the placeholders the
        existence check fires first and every mutation would look caught.
        """
        for rel in copies:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_GLOBAL_ROOT / rel, root / rel)
        relink(root)
        text = (root / "harness/angles.tsv").read_text(encoding="utf-8")
        for path in PATH_RE.findall(text):
            target = root / path
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"")

    with tempfile.TemporaryDirectory(prefix="revival-neg-") as tmp:
        root = Path(tmp)
        mirror(root)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")

        def run() -> tuple[int, str]:
            done = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--root", str(root),
                 "--only", "angles"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                timeout=NEG_ARM_CHILD_TIMEOUT_S)
            return done.returncode, (done.stdout or "") + (done.stderr or "")

        rc, out = run()
        if rc != 0:
            print("NEG-ARM CONTROL FAILED: the unmutated copy does not pass")
            print(out.strip()[:800])
            return 2
        print("NEG-ARM control: unmutated copy PASS (rc=0)")

        caught = 0
        for name, marker, mutate in MUTATIONS:
            shutil.rmtree(root)
            mirror(root)
            mutate(root)
            if not getattr(mutate, "keeps_link", False):
                relink(root)
            rc, out = run()
            hit = marker in out
            print(f"NEG-ARM {name}: rc={rc} marker={hit} "
                  f"{'CAUGHT' if rc == 2 and hit else 'MISSED'}")
            if rc == 2 and hit:
                caught += 1
            else:
                print(out.strip()[:600])
        total = len(MUTATIONS)
        print(f"NEG-ARM {caught}/{total} mutants caught")
        print("NEG-ARM: PASS" if caught == total else "NEG-ARM: FAIL")
        return 1 if caught == total else 2


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="one gate for the revival contract")
    ap.add_argument("--root", default=str(_GLOBAL_ROOT),
                    help="the population to judge (default: this repo)")
    ap.add_argument("--only", default="all",
                    choices=("all", "feature", "angles", "budgets", "goal"))
    ap.add_argument("--neg-arm", action="store_true",
                    help="prove the gate goes RED on a mutated copy; rc 1 = all mutants caught")
    args = ap.parse_args(argv)
    _set_root(Path(args.root).resolve())
    if args.neg_arm:
        return neg_arm()
    return _checks(args.only)


if __name__ == "__main__":
    raise SystemExit(main())
