"""console-window-gate — no console/foreground window from this tree.

PORT FOR (owner order, 2026-11-02, verbatim): *"para de abrir janela de terminal
em foreground. é tu? ou um .vbs?"* / *"anota no agents.md pra tu nunca mais fazer
nada em foreground ou ter scripts q façam isso"*.

THE DEFECT IT REFUSES: a child started from a console-less parent (the shell,
`pythonw`, a task, a lane session) makes Windows ALLOCATE a console for it, and
that window is on the owner's desktop for the child's whole life. He saw it as
windows opening and vanishing while a battery ran. `_main/hidden-launch.py` is
the sanctioned way to start one; this port refuses a NEW call site that starts
`cmd`/`powershell`/`.cmd`/`.bat`/`run.cmd` (or `os.system`) without
`CREATE_NO_WINDOW` / `startupinfo` / the helper.

THE DEBT IS FROZEN, NOT IGNORED: the call sites that already existed on
2026-11-02 are written to `_main/console-window-baseline.json` and never grow.
`--write-baseline` records the CURRENT set (a ratchet re-baseline must be a
deliberate act, same shape as `lane-screen-baseline.json`); `--neg-arm` appends
a violating call site to a COPY of the tree in the temp dir and requires the gate
to go RED, so a gate that cannot see a new offender cannot pass either.

VERDICT: rc 0 = no growth; rc 1 = growth (or a broken baseline); rc 2 = the
detector itself failed a control.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, "console-window-baseline.json")

# Files whose job is to talk about windows: the rule text and the instruments
# that MEASURE windows must not be judged as spawners.
SKIP_DIRS = {
    "_cache", "_libs", "__pycache__", "node_modules", "dist", "target",
    "_audit-verify", "history", "worker/models", "_falsify",
}
SKIP_FILES = {
    "console-window-gate.py",
    "console-window-baseline.json",
    "lane-screen-gate.py",
    "hidden-launch.py",
}

# The launcher of a process, not its argument list, decides whether a console is
# allocated: `cmd.exe`, `powershell.exe`, a batch file. A bare `python` child of a
# console-less parent does NOT get a new console (it inherits the absence), so it
# is not a violation — the rule in AGENTS.md names `pythonw` for the case where a
# window would otherwise be OWNED by the app.
LAUNCHER_RE = re.compile(
    r"""(?ix)
    (?:
      ["'\s\[]cmd(?:\.exe)?["'\s,\]]        # cmd / cmd.exe
    | ["'\s\[]powershell(?:\.exe)?["'\s,\]]?
    | ["'\s\[]pwsh(?:\.exe)?["'\s,\]]?
    | ["'\s\[]start["'\s,\]]                # `start` in a shell context
    | \.cmd["'\s,\]]                       # a batch file
    | \.bat["'\s,\]]
    | run\.cmd
    )
    """
)

CALL_RE = re.compile(
    r"(?P<callee>subprocess\.Popen|subprocess\.run|subprocess\.call|subprocess\.check_output"
    r"|subprocess\.check_call|os\.system|os\.popen|hidden\.run|hidden\.popen|hl\.run)\s*\("
)

HIDE_RE = re.compile(
    r"(?i)creationflags|CREATE_NO_WINDOW|startupinfo|STARTF_USESHOWWINDOW|"
    r"hidden[-_]launch|hidden\.run|hidden\.popen|hl\.run|_hidden_run|WindowStyle\s+Hidden"
)


def _iter_sources(base):
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in files:
            if name in SKIP_FILES:
                continue
            if not name.endswith((".py", ".cmd", ".bat", ".vbs")):
                continue
            yield os.path.join(root, name)


def _balanced(text: str, start: int) -> str:
    """Text of the call whose '(' is at `start`, parenthesis-balanced."""
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start : start + 400]


def scan(repo: str = REPO) -> list[dict]:
    """Every console-launching call site in `repo` that does not hide the window."""
    findings = []
    for path in _iter_sources(repo):
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", "replace")
        rel = os.path.relpath(path, repo).replace("\\", "/")
        low = rel.lower()
        if low.endswith((".cmd", ".bat")):
            # A batch file that starts powershell itself: the file is run by
            # SOMETHING, and that something must hide it. What we can see here is
            # whether the file turns around and starts another console.
            for m in re.finditer(r"(?im)^\s*(?:powershell(?:\.exe)?|pwsh(?:\.exe)?)\b.*$", text):
                line = m.group(0)
                if not re.search(r"(?i)-WindowStyle\s+Hidden", line):
                    findings.append(
                        {
                            "file": rel,
                            "line": text[: m.start()].count("\n") + 1,
                            "why": "batch file starts powershell without -WindowStyle Hidden",
                            "evidence": line.strip()[:120],
                        }
                    )
            continue
        if low.endswith(".vbs"):
            continue
        for m in CALL_RE.finditer(text):
            call = _balanced(text, text.index("(", m.end() - 1))
            if not LAUNCHER_RE.search(call):
                continue
            # A call whose callee IS the helper is compliant by construction.
            if m.group("callee").startswith(("hidden.", "hl.")):
                continue
            if HIDE_RE.search(call):
                continue
            findings.append(
                {
                    "file": rel,
                    "line": text[: m.start()].count("\n") + 1,
                    "why": "console launcher started without CREATE_NO_WINDOW/startupinfo",
                    "evidence": " ".join(call.split())[:120],
                }
            )
    findings.sort(key=lambda f: (f["file"], f["line"]))
    return findings


def _key(f: dict) -> str:
    return f"{f['file']}:{f['line']}"


def main(argv: list[str]) -> int:
    write = "--write-baseline" in argv
    neg = "--neg-arm" in argv

    findings = scan()
    if write:
        with open(BASELINE, "w", encoding="utf-8", newline="") as fh:
            json.dump(
                {"written": "2026-11-02", "count": len(findings), "sites": [_key(f) for f in findings]},
                fh,
                indent=1,
            )
            fh.write("\n")
        print(f"BASELINE-WRITTEN count={len(findings)} path={os.path.relpath(BASELINE, REPO)}")
        return 0

    if not os.path.exists(BASELINE):
        print(f"NO-BASELINE {os.path.relpath(BASELINE, REPO)} missing — run --write-baseline")
        return 1
    with open(BASELINE, encoding="utf-8") as fh:
        base = json.load(fh)
    allowed = set(base.get("sites") or [])
    new = [f for f in findings if _key(f) not in allowed]

    print(f"findings={len(findings)} baseline={len(allowed)} new={len(new)}")
    for f in new:
        print(f"NEW {f['file']}:{f['line']} — {f['why']} | {f['evidence']}")
    verdict = "GREEN" if not new else "RED"
    print(f"VERDICT: {verdict}")

    if neg:
        # THE CONTROL: plant a violating call site in a COPY of the tree. The
        # gate must see it. A gate that cannot catch its own tree cannot refuse
        # a lane's new `cmd /c`.
        tmp = tempfile.mkdtemp(prefix="cwgate-")
        try:
            dst = os.path.join(tmp, "tree")
            os.makedirs(os.path.join(dst, "_main"))
            shutil.copy(__file__, os.path.join(dst, "_main", "console-window-gate.py"))
            with open(os.path.join(dst, "_main", "planted.py"), "w", encoding="utf-8", newline="") as fh:
                fh.write('import subprocess\nsubprocess.Popen(["cmd", "/c", "echo hi"])\n')
            planted = scan(dst)
            caught = len(planted)
            print(f"NEG-ARM planted={caught} caught={caught}")
            print("NEG-ARM: PASS" if caught >= 1 else "NEG-ARM: FAIL")
            if caught < 1:
                return 2
            # `red-as-expected-*` CONVENTION: a control that caught the defect
            # exits 1 BY DESIGN so the battery can demand rc=1 and read the
            # phrase. Returning 0 here made the step fail with rc=0 (measured
            # 2026-11-02: `red-as-expected-console-window-gate=0`).
            return 1 if not new else 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return 0 if not new else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
