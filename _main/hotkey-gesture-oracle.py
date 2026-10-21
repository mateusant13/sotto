#!/usr/bin/env python
"""ORACLE: Alt+C IS THE CAPTION, AND A DOUBLE DOES NOT ENABLE IT.

OWNER, 2026-10-18, verbatim:
    "pra habilitar a legenda: primeiro alt c. pra ir pro priemiro painel:
     double alt c. caso double alt c, a legenda nao habilita"

The contract has a physical cost that is stated rather than hidden: a caption
cannot appear faster than the window that proves the press was not part of a
double. So the single press is DEFERRED, and the question this oracle answers is
the one that decides whether that deferral is safe:

    when the timer finally fires, can it still tell that a second press came?

It can, because the double branch bumps a token and the deferred single checks
that token at RUN time rather than trying to cancel a Timer that may already be
inside `_set_live_enabled`. Cancelling the Timer would be the obvious design and
it is the wrong one.

The bodies are EXTRACTED FROM THE SHIPPED FILE with `ast` and exec'd, so this
measures the code that will run, not a transcription of it. No Win32, no window,
nothing launched on the owner's machine.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SHELL = Path(r"H:\sotto\app\webview\sotto_webview.py")
EXIT_PASS, EXIT_FAIL = 0, 1
rows: list[tuple[bool, str, str]] = []


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


SRC = SHELL.read_text(encoding="utf-8")
tree = ast.parse(SRC)

cls = next((n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SottoShell"), None)
if cls is None:
    print("VERDICT: FAIL -- SottoShell not found")
    sys.exit(EXIT_FAIL)

fn_single = next((n for n in cls.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_hotkey_single"), None)
fn_press = next((n for n in cls.body
                 if isinstance(n, ast.FunctionDef) and n.name == "hotkey_pressed"), None)

print("ARM structure")
add(fn_single is not None, "_hotkey_single exists")
add(fn_press is not None, "hotkey_pressed exists")

# RE-ANCHORED 2026-10-21: one constant became two. `HOTKEY_DOUBLE_MS` governed
# BOTH how long a lone press waits for the caption AND how long a press still
# counts as the same gesture -- and the SHORTER of the two broke the other: a
# human double press (300-500 ms, measured) fell OUTSIDE the 250 ms window, so
# the two presses were two gestures, the caption toggled on and off, and the
# panel never opened. The contract is now TWO numbers:
#     HOTKEY_CAPTION_DEFER_MS  the caption's wait (250 -- a lone press must not
#                              look slow, and a fast double must not flash it)
#     HOTKEY_GESTURE_MS        the gesture's window (700 -- a HUMAN number)
m = re.search(r"^HOTKEY_CAPTION_DEFER_MS\s*=\s*(\d+)", SRC, re.M)
WIN = int(m.group(1)) if m else None
add(WIN is not None and 100 <= WIN <= 400,
    "the caption's deferral is short enough not to feel like lag",
    f"HOTKEY_CAPTION_DEFER_MS={WIN}")
gm = re.search(r"^HOTKEY_GESTURE_MS\s*=\s*(\d+)", SRC, re.M)
GWIN = int(gm.group(1)) if gm else None
add(GWIN is not None and WIN is not None and GWIN >= WIN,
    "the gesture window is at least the caption's deferral",
    f"HOTKEY_GESTURE_MS={GWIN}")
add(GWIN is not None and GWIN >= 500,
    "the gesture window is wide enough for a HUMAN double press (300-500 ms)",
    f"HOTKEY_GESTURE_MS={GWIN}")

press_src = ast.get_source_segment(SRC, fn_press) or ""
add("_hotkey_single_token" in press_src and "+= 1" in press_src.replace(" ", " ").replace("+ 1", "+= 1"),
    "the double branch bumps the token",
    "")
add("HOTKEY_GESTURE_MS" in press_src, "the double test reads the gesture window")
add("_undo_gesture_caption" in press_src,
    "the double branch PUTS THE CAPTION BACK when the gesture is a panel")
add("threading.Timer" in press_src, "the single press is deferred by a timer")

single_src = ast.get_source_segment(SRC, fn_single) or ""
add("token !=" in single_src, "the deferred single checks the token at run time")

print("\nARM the deferred single, executed from the file's own source")

calls: list[dict] = []


class FakeShell:
    """Only what `_hotkey_single` touches. It calls nothing Win32."""

    def __init__(self, token, wanted, live_token):
        self._hotkey_single_token = live_token
        self._caption_wanted = wanted
        self._log = calls

    def _set_live_enabled(self, payload):
        calls.append(payload)
        self._caption_wanted = bool(payload.get('on'))
        return 'enabled'


ns = {"log": lambda *a, **k: None,
      "HOTKEY_CAPTION_DEFER_MS": WIN or 250,
      "HOTKEY_GESTURE_MS": GWIN or 700}
exec(compile(ast.Module(body=[fn_single], type_ignores=[]), "<single>", "exec"), ns)
hotkey_single = ns["_hotkey_single"]

# 1. A lone press: the token still matches, so the caption must flip.
calls.clear()
s = FakeShell(token=4, wanted=False, live_token=4)
hotkey_single(s, 4)
add(calls == [{"on": True}], "a lone press enables the caption", str(calls))

# 2. ... and from on, a lone press disables it.
calls.clear()
s = FakeShell(token=4, wanted=True, live_token=4)
hotkey_single(s, 4)
add(calls == [{"on": False}], "a lone press from on disables the caption", str(calls))

# 3. THE CLAUSE THAT MATTERS: a double arrived, so the token moved and the
#    deferred single must do NOTHING AT ALL. This is the owner's rule verbatim.
calls.clear()
s = FakeShell(token=4, wanted=False, live_token=5)
hotkey_single(s, 4)
add(calls == [], "a DOUBLE leaves the caption untouched", str(calls) or "no call")

# 4. A third press starts a new gesture: token 5 matches again, so it acts.
calls.clear()
s = FakeShell(token=5, wanted=False, live_token=5)
hotkey_single(s, 5)
add(calls == [{"on": True}], "a press after the double is a NEW gesture and acts",
    str(calls))

bad = [r for r in rows if not r[0]]
print(f"\n{len(rows) - len(bad)}/{len(rows)} GREEN")
if bad:
    print("VERDICT: FAIL")
    for _, n, d in bad:
        print(f"  - {n}" + (f"  {d}" if d else ""))
    sys.exit(EXIT_FAIL)
print("VERDICT: PASS")
sys.exit(EXIT_PASS)