"""hidden-launch — the ONE way this tree starts a child process.

WHY THIS FILE EXISTS (owner order, 2026-11-02, verbatim): *"para de abrir janela
de terminal em foreground. é tu? ou um .vbs?"* and then *"anota no agents.md pra
tu nunca mais fazer nada em foreground ou ter scripts q façam isso"*.

MEASURED, that day: the pop-ups on his desktop were `cmd /c
"_main\\_audit-verify-all.cmd"` and `powershell -NoProfile -Command ...` started
by a lane session. A process started from a console-less parent makes Windows
ALLOCATE a console for the child, and that new console window is visible for as
long as the child lives — a battery step, a probe, a relaunch: he sees it. There
is no "mostly hidden": either the child gets `CREATE_NO_WINDOW` (0x08000000) or
STARTF_USESHOWWINDOW+SW_HIDE, or the window is HIS and the lane is a nuisance.

WHAT IT DOES NOT DO: it does not swallow the child's output. `capture=True`
returns (rc, stdout_text, stderr_text); the default inherits DEVNULL like the
existing launchers, because a probe that reads a pipe has already proven it cares
about the bytes and would have used `subprocess` itself.

CONTRACT for every caller in this tree: `cmd`, `powershell`, `.cmd`, `.bat`,
`run.cmd` and `python` children go through here. `_main/console-window-gate.py`
is the port that refuses a new `Popen`/`run` of those without the flag.
"""

from __future__ import annotations

import os
import subprocess
import sys

# CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP. The group matters for the same
# reason keepalive.py uses it: a Ctrl-C aimed at a console must not take the
# whole tree with it, and there is no console here for the child to inherit.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008

# STARTF_USESHOWWINDOW + SW_HIDE: the belt to CREATE_NO_WINDOW's braces. A
# console-less host (pythonw, the shell, a task) can still be asked for a window
# through STARTUPINFO, and a child that ignores CREATE_NO_WINDOW (some installers,
# `.vbs` via wscript) honours this one.
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0


def _startupinfo() -> "subprocess.STARTUPINFO | None":
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return si


def popen(argv, **kwargs):
    """Popen with the window suppressed. Extra kwargs pass straight through."""
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    si = _startupinfo()
    if si is not None and "startupinfo" not in kwargs:
        kwargs["startupinfo"] = si
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    # SEM `creationflags=` AQUI: ja' vem em `kwargs` (ver o comentario em `run`).
    return subprocess.Popen(argv, **kwargs)


def run(argv, cwd=None, env=None, capture=False, timeout=None, text=True):
    """Run a child HIDDEN and return (rc, out, err).

    `capture=False` gives the child DEVNULL for both pipes and returns
    (rc, '', ''). `capture=True` uses PIPE for both and decodes with `text`.
    It never raises on a non-zero rc: the CALLER decides what rc means, which is
    the rule this tree already applies to every oracle.
    """
    kw = {
        "cwd": cwd,
        "env": env,
        "creationflags": CREATE_NO_WINDOW,
        "stdin": subprocess.DEVNULL,
    }
    si = _startupinfo()
    if si is not None:
        kw["startupinfo"] = si
    if capture:
        kw.update(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            encoding=None if not text else "utf-8",
            errors=None if not text else "replace",
        )
    else:
        kw.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # `creationflags` JA' ESTA' em `kw`: passar de novo levanta
        # `TypeError: got multiple values for keyword argument` e o chamador morre
        # antes de arrancar o filho. MEDIDO 2026-11-04 (`run(['cmd','/c',...])`
        # a partir de uma lane: a bateria inteira nunca correu e o `cmd` que eu
        # via era o do erro). O portao `console-window-gate.py` so' confere a
        # PRESENCA da bandeira, por isso nao apanhou isto.
        proc = subprocess.Popen(argv, **kw)
    except FileNotFoundError as exc:
        return (127, "", str(exc))
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return (124, out or "", err or "")
    return (proc.returncode, out or "", err or "")


def powershell(script: str, capture=True, timeout=None):
    """`powershell -WindowStyle Hidden -NonInteractive` — the only powershell
    this tree may start. `-NoProfile` stays because a profile can print."""
    return run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            script,
        ],
        capture=capture,
        timeout=timeout,
    )


def _selftest() -> int:
    """Prove the mechanism on THIS box: no window, and output still arrives."""
    import json

    checks = []

    # 1. a console-less child reports its own console: `GetConsoleWindow()`
    #    through python itself, so the answer comes from the CHILD.
    rc, out, err = run(
        [sys.executable, "-c", "print('CTX', __import__('ctypes').windll.kernel32.GetConsoleWindow())"],
        capture=True,
        timeout=120,
    )
    hwnd = out.strip().split("CTX ")[-1] if "CTX " in out else "?"
    checks.append(("python child has no console window", rc == 0 and hwnd == "0", out.strip()))

    # 2. stderr still arrives (a hidden child is not a silent one).
    rc, out, err = run(
        [sys.executable, "-c", "import sys; sys.stderr.write('ERR-OK\\n'); sys.exit(3)"],
        capture=True,
        timeout=120,
    )
    checks.append(("stderr captured and rc honoured", rc == 3 and "ERR-OK" in err, f"rc={rc} err={err.strip()!r}"))

    # 3. powershell runs hidden and prints (its own console handle must be 0).
    rc, out, err = powershell(
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; 40+2; 'PSOK'", capture=True, timeout=180
    )
    checks.append(("powershell hidden answers", rc == 0 and "PSOK" in out, out.strip()[:60]))

    ok = all(c[1] for c in checks)
    for name, good, ev in checks:
        print(("PASS " if good else "FAIL ") + name + " — " + str(ev))
    print(json.dumps({"ok": ok, "cases": len(checks), "caught": sum(1 for c in checks if c[1])}))
    print("NEG-ARM: PASS" if ok else "NEG-ARM: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
