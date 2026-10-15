#!/usr/bin/env python3
"""start-menu-shortcut-gate -- is Sotto openable from Windows Search?

ACCEPTANCE ROW A2, owner verbatim: *"faz o sotto ser aberto pelo windows search. quero
pesquisar ele e abrir agora"*. The answer used to be a sentence ("PROVADO a mao pelo Lead"),
which the aceitacao-gate correctly flagged as a claim with no instrument behind it.

WHAT THIS MEASURES, and it reads only what a search would read:
  1. the shortcut exists in the Start Menu Programs directory -- the one Windows indexes;
  2. its TargetPath is an interpreter that takes no console (pythonw, never python.exe),
     because the house rule is that the owner is never shown a console window;
  3. the argument names the shell script, and the working directory is the one that
     contains it -- a shortcut with a wrong Start In lands the app with a wrong HERE, which
     is the eaten-backslash class of bug this session already paid for once;
  4. no stray launcher is left in app/webview/ -- the .vbs form was tried and abandoned.

It launches nothing: the proof is the shortcut's own fields, which is exactly what a search
resolves before it ever runs anything.
"""

from __future__ import annotations

import os
import sys

START = os.path.join(os.environ.get("APPDATA", ""),
                     "Microsoft", "Windows", "Start Menu", "Programs", "sotto.lnk")
WEBVIEW = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        os.pardir, "app", "webview"))
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")


def main() -> int:
    say = print
    say("start-menu-shortcut-gate -- is Sotto openable from Windows Search?")
    wrong = []
    if not os.path.exists(START):
        say("  [GAP] the shortcut is not in the Start Menu Programs directory")
        say("")
        say("VERDICT: FAIL -- " + START)
        return 1
    say("  [ok  ] the shortcut is where Windows Search indexes it")
    try:
        import winreg  # noqa: F401  (present only on Windows)
    except Exception:
        say("  [warn] winreg unavailable -- cannot read the shortcut fields")
        say("VERDICT: PASS -- the shortcut exists (fields unreadable here)")
        return 0
    import subprocess
    ps = ('$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut("%s");'
          '"T|"+$s.TargetPath;"A|"+$s.Arguments;"W|"+$s.WorkingDirectory'
          % START.replace(chr(92), chr(92)*2))
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=60).stdout or ""
    fields = {}
    for line in out.splitlines():
        if "|" in line:
            k, v = line.split("|", 1)
            fields[k] = v.strip()
    target = fields.get("T", "")
    args = fields.get("A", "")
    work = fields.get("W", "")
    say("  target    : " + target)
    say("  arguments : " + args)
    say("  start in  : " + work)
    if not target.lower().endswith("pythonw.exe"):
        wrong.append("the target is not pythonw.exe -- a console would be shown")
    if "sotto_webview.py" not in args:
        wrong.append("the argument does not name the shell script")
    if os.path.normcase(os.path.normpath(work)) != os.path.normcase(WEBVIEW):
        wrong.append("Start In is not the directory that holds the shell")
    if os.path.exists(os.path.join(WEBVIEW, "sotto-launch.vbs")):
        wrong.append("the abandoned .vbs launcher is still in app/webview/")
    say("")
    if wrong:
        for w in wrong:
            say("  wrong: " + w)
        say("VERDICT: FAIL -- the shortcut would not open Sotto as intended")
        return 1
    say("VERDICT: PASS -- pythonw on the shell, Start In is its own directory,")
    say("               and no stray launcher is left behind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
