"""WORKER 1 -- revive the interrupted lane "Wire audio into the engine".

Evidence that this lane died: local_runtime_sessions, workspace I:\\!aicompanion,
status='interrupted', updated_at 2026-10-06 01:24:21, child of root
mvs_58d4329e89f340809745f74278e78a2c.

Its residue is on disk, UNCOMMITTED, on branch wip/recover-2026-10-05:
  A apps/vod-cutter-pro/engine/audioBridge.ts
  A apps/vod-cutter-pro/__tests__/audioBridge-wiring.test.ts
  M apps/vod-cutter-pro/engine/Engine.ts
  M apps/vod-cutter-pro/engine/EngineClient.ts
  M apps/vod-cutter-pro/App.tsx

This worker answers ONE question with static evidence, and writes ONE receipt.
It runs NO build, NO npm, NO test runner -- law 8: the owner's machine outranks
our throughput, and a monorepo typecheck is not cheap.

FORBIDDEN (hard): git add -A, git checkout, git reset, any write outside the
single receipt path below.

Exit codes are contracts: 0 = verdict produced, 2 = could not verify.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(r"I:\!aicompanion")
OUT = REPO / "receipts" / "receipt-aicomp-01-audio-bridge-lane.md"
FILES = [
    "apps/vod-cutter-pro/engine/audioBridge.ts",
    "apps/vod-cutter-pro/__tests__/audioBridge-wiring.test.ts",
    "apps/vod-cutter-pro/engine/Engine.ts",
    "apps/vod-cutter-pro/engine/EngineClient.ts",
    "apps/vod-cutter-pro/App.tsx",
]


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO), *args],
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    facts, missing = [], []
    for rel in FILES:
        p = REPO / rel
        if not p.exists():
            missing.append(rel)
            facts.append((rel, "MISSING", 0, "", ""))
            continue
        b = p.read_bytes()
        txt = b.decode("utf-8", "replace")
        facts.append((rel, "present", len(b),
                      hashlib.sha256(b).hexdigest()[:16], txt))

    # wiring: does audioBridge get imported by the three consumers?
    imports = {}
    for rel in FILES[2:]:
        txt = facts[[f[0] for f in facts].index(rel)][4]
        imports[rel] = ("audioBridge" in txt,
                        re.findall(r"import[^;]*audioBridge[^;]*;", txt)[:3])

    status = git("status", "--porcelain", "--", *FILES)
    staged_new = [l for l in status.splitlines()
                  if re.match(r"^A\s", l.strip()[:2])]

    # Is the new test file actually wired into any test config? (static only)
    test_files = list((REPO / "apps" / "vod-cutter-pro").rglob("*.test.ts*"))

    verdict = "INCOMPLETE" if missing else "PRESENT-BUT-UNVERIFIED"

    lines = [
        "# receipt-aicomp-01 -- the interrupted lane 'Wire audio into the engine'",
        "",
        "Revived by seat `aicompanion` (suborch). Death evidence: "
        "status='interrupted', updated_at=2026-10-06 01:24:21 (MEASURED, "
        "local_runtime_sessions).",
        "",
        "## Verdict",
        "",
        f"**{verdict}** -- the lane's residue is on disk and uncommitted.",
        "NOT verified by build: no `npm`/`tsc` was run, by design (law 8).",
        "A green here would mean 'the files exist', never 'the build passes'.",
        "",
        "## Files and their sha256 (first 16 hex)",
        "",
        "| file | state | bytes | sha256[:16] |",
        "|---|---|---:|---|",
    ]
    for rel, state, size, digest, _ in facts:
        lines.append(f"| `{rel}` | {state} | {size} | `{digest}` |")

    lines += ["", "## Wiring (static grep, not a build)", "",
              "| consumer | mentions audioBridge | import statement |",
              "|---|---|---|"]
    for rel, (hit, imps) in imports.items():
        shown = "; ".join(i.strip().replace("\n", " ") for i in imps) or "-"
        lines.append(f"| `{rel}` | {'YES' if hit else 'NO'} | `{shown}` |")

    lines += [
        "",
        "## Staged as new (A) by the dead lane",
        "",
        "```",
        staged_new or ["(none)"],
        "```",
        "",
        f"Test files present under apps/vod-cutter-pro: {len(test_files)}",
        "",
        "## UNKNOWN (named, not guessed)",
        "",
        "- Whether `npm run ci` passes. NOT RUN -- heavy, and law 8 forbids "
        "spending the owner's machine on it without his say-so.",
        "- Whether the new test is wired into a runner.",
        "- Whether the uncommitted diff is semantically correct.",
        "",
        "## Safety",
        "",
        "No `git add -A`, no `git checkout`, no `git reset`, no build, no write "
        "outside this receipt.",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"verdict={verdict} missing={len(missing)}")
    print(f"receipt={OUT}")
    print(f"bytes={OUT.stat().st_size}")
    return 0 if not missing else 0  # a missing file is a FINDING, not a tool failure


if __name__ == "__main__":
    sys.exit(main())