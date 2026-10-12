#!/usr/bin/env python3
"""autostart-status-check -- the battery step for autostart, with the exit code READ AS A STATUS.

WHY THIS FILE EXISTS (measured 2026-10-12, the first product-battery run of this session): the step called
`python app/webview/sotto_webview.py --autostart-status` directly and recorded its rc as a plain gate, so it
demanded rc=0. But `autostart_status()` (sotto_webview.py:2435-2452) returns **1 when there is no Run value**
-- the exit code IS the answer: 0 = on and matching this checkout, 1 = off, 2 = the registry read failed,
3 = on but pointing at ANOTHER checkout. On a healthy machine with autostart off, the battery therefore
painted a red step and exited 1. The fix belongs here, in the SEMANTICS of the step -- never in the
registry: installing autostart to turn a gate green would change the owner machine without being asked.

WHAT IT DOES, and the trade it makes explicit:
  1. it reads HKCU Run Sotto itself, using the key and value names PARSED FROM THE SHELL SOURCE so they
     cannot drift, and classifies the state: off / on-this-checkout / on-another-checkout / unreadable;
  2. it ALSO runs the shell own `--autostart-status` (launch-free in effect: the flag prints four lines and
     exits; measured 2026-10-12 that it leaves no process and no WebView2 tree behind) and requires the
     CODE it returns to agree with the state read here -- so the step still exercises the shipped
     implementation instead of bypassing it;
  3. it exits 0 for the two VALID states, 2 when the registry cannot be read, 3 when autostart points at
     another checkout, and 4 when the shell own answer disagrees with this reading. A disagreement is the
     interesting case and it is LOUD.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
PY = sys.executable


def shell_constants():
    with open(SHELL, encoding="utf-8", errors="replace") as handle:
        src = handle.read()
    # Quote-free on purpose: the first version embedded quote characters inside a double-quoted
    # Python string and did not compile, so this parses the value between the delimiters instead.
    name = re.search(r"AUTOSTART_VALUE_NAME\s*=\s*.(.*?).$", src, re.MULTILINE)
    key = re.search(r"AUTOSTART_RUN_KEY\s*=\s*.(.*?).$", src, re.MULTILINE)
    if not name or not key:
        print("sotto: AUTOSTART_CHECK_FAILED could not parse the shell constants")
        sys.exit(2)
    return name.group(1), key.group(1)


def read_state(name, keypath):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, keypath, 0, winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return "off", None
    except OSError as exc:
        print("sotto: AUTOSTART_CHECK_FAILED registry read: %r" % (exc,))
        return "unreadable", None
    expected = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
    same = os.path.normcase(expected) in os.path.normcase(value or "")
    return ("on-this-checkout" if same else "on-another-checkout"), value


def shell_answer():
    proc = subprocess.run([PY, os.path.join(ROOT, "app", "webview", "sotto_webview.py"), "--autostart-status"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    name, keypath = shell_constants()
    state, value = read_state(name, keypath)
    code, output = shell_answer()
    print("sotto: AUTOSTART_CHECK state=%s value=%r" % (state, value))
    print("sotto:   the shell own answer: rc=%d (0=on+matching, 1=off, 2=unreadable, 3=elsewhere)" % code)
    for line in output.splitlines():
        print("sotto:   | " + line)
    expected_code = {"off": 1, "on-this-checkout": 0, "on-another-checkout": 3, "unreadable": 2}[state]
    if code != expected_code:
        print("sotto: AUTOSTART_CHECK_DISAGREES read=%s (expects rc=%d) shell_said=%d"
              % (state, expected_code, code))
        return 4
    if state == "off":
        print("sotto: AUTOSTART_CHECK_OK off is a VALID state -- the step must not paint it red")
        return 0
    if state == "on-this-checkout":
        print("sotto: AUTOSTART_CHECK_OK on, and it points at THIS checkout")
        return 0
    if state == "on-another-checkout":
        print("sotto: AUTOSTART_CHECK_BAD autostart points at another checkout: " + str(value))
        return 3
    print("sotto: AUTOSTART_CHECK_BAD the registry could not be read")
    return 2


if __name__ == "__main__":
    sys.exit(main())