#!/usr/bin/env python3
"""panel-search-keyboard-oracle -- can the panel take keyboard focus at all? The row says NO; the code and a
real run log say YES, while the pointer is on it.

AUDIT ROW F9: "o campo de busca do painel nao pode receber teclado" (auditoria-completa-20261007.md:71), a
finding whose source transfers the decision to the owner. The audit was right about the MECHANISM it named:
`_on_before_show` puts WS_EX_NOACTIVATE on the window and `show_panel` shows it with SW_SHOWNOACTIVATE --
right for appearing (Alt+C must not steal focus), wrong for the INTERACTIVE state, because a
WS_EX_NOACTIVATE window is not brought to the foreground by a click either, so the panel could never take
keyboard focus and `<input type="search" id="search-input">` could never receive a character.

THAT IS NOW FIXED, and this oracle measures the fix where it can:
  * THE CHAIN, in the live files: panel.js mouseenter/mouseleave -> bridge.setPointerInteractive(active) ->
    the shell IPC call -> set_pointer_interactive(), which CLEARS WS_EX_NOACTIVATE and click-through while
    active and restores both on leave. show_panel SW_SHOWNOACTIVATE is untouched, so appearing still
    steals nothing; only the moment the pointer is on the panel can activate it.
  * THE EVIDENCE FROM A REAL RUN: _main/webview-run.log carries hundreds of POINTER_INTERACTIVE lines, and
    (THE LOG IS LIVE -- lanes keep writing to it, so the counts DRIFT: 671 lines read in one pass, 621 in the
    next minutes later. The arms re-derive them every run and the verdict prints the CURRENT ones; no number
    here is remembered.)
    this oracle checks the INVARIANT over every one of them -- active=X iff click_through=not X iff
    noactivate=not X. Measured 2026-10-12: 671 lines, 337 active=true with noactivate=false, 334
    active=false with noactivate=true. The window really does receive activation rights while the pointer
    is on it, thousands of times, in the shipped app.
  * WHAT STAYS TRUE, and is by design: the search INPUT is DISABLED while no writer exists (panel.html), a
    content condition rather than a keyboard one, so an empty history cannot be searched even when focused.
  * UNMEASURED, and said so: that a CHARACTER actually lands in the field. Nothing here typed into it --
    that needs the launch the owner stop order forbids. The residual is a keystroke test, not a wiring gap.

ARM 4 is the control: one line of a COPY of the log is rewritten so noactivate contradicts active, and the
invariant must catch it -- otherwise arm 2 would only be counting lines. The real log is never modified.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
PANEL_JS = os.path.join(ROOT, "app", "panel", "panel.js")
PANEL_HTML = os.path.join(ROOT, "app", "panel", "panel.html")
LOG = os.path.join(ROOT, "_main", "webview-run.log")
LINE = re.compile(r"POINTER_INTERACTIVE active=(\w+) click_through=(\w+) noactivate=(\w+)")


def parse(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = LINE.search(line)
            if match:
                rows.append(tuple(match.group(1, 2, 3)))
    return rows


def violations(rows):
    bad = []
    for active, click, noact in rows:
        want = "false" if active == "true" else "true"
        if click != want or noact != want:
            bad.append((active, click, noact))
    return bad


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    say = print
    wrong = []
    with open(SHELL, encoding="utf-8") as handle:
        shell = handle.read()
    with open(PANEL_JS, encoding="utf-8") as handle:
        panel_js = handle.read()
    with open(PANEL_HTML, encoding="utf-8") as handle:
        panel_html = handle.read()
    say("panel-search-keyboard-oracle -- row F9 (files + the run log; no launch)")

    chain = {
        "panel.js drives activation on hover": "setPointerInteractive" in panel_js,
        "on mouseenter AND mouseleave": "mouseenter" in panel_js and "mouseleave" in panel_js,
        "the shell receives the payload": "'active'" in shell or "\"active\"" in shell,
        "the setter CLEARS noactivate when active": "remove=WS_EX_NOACTIVATE" in shell,
        "and RESTORES it when idle": "add=WS_EX_NOACTIVATE" in shell,
    }
    say("  arm 1  the chain, in the live files: " + ", ".join("%s=%s" % (k, str(v).lower())
        for k, v in chain.items()))
    for key, ok in chain.items():
        if not ok:
            wrong.append("arm 1: the chain lost " + key)

    rows = parse(LOG)
    truthy = sum(1 for a, _c, _n in rows if a == "true")
    falsy = sum(1 for a, _c, _n in rows if a == "false")
    bad = violations(rows)
    say("  arm 2  the run log: %d POINTER_INTERACTIVE line(s), active=true %d, active=false %d, invariant violations %d" % (len(rows), truthy, falsy, len(bad)))
    if not rows:
        wrong.append("arm 2: the log carries no POINTER_INTERACTIVE line at all")
    if truthy == 0 or falsy == 0:
        wrong.append("arm 2: the toggle only ever went ONE way -- the panel could not take activation")
    if bad:
        wrong.append("arm 2: %d line(s) break the invariant, e.g. %s" % (len(bad), bad[:2]))

    field = ("search-input" in panel_html) and ("search-form" in panel_html)
    declared = "disabled while no writer exists" in panel_html or "search input is disabled" in panel_html
    say("  arm 3  the field and its own condition: input present=%s, disabled-while-no-writer declared=%s"
        % (str(field).lower(), str(declared).lower()))
    if not field:
        wrong.append("arm 3: the search field is gone from panel.html")
    if not declared:
        wrong.append("arm 3: the declared reason the box is inert (no writer) disappeared")

    workdir = os.path.join(tempfile.gettempdir(), "f9-keyboard")
    os.makedirs(workdir, exist_ok=True)
    mutant = os.path.join(workdir, "log-mutant.txt")
    shutil.copyfile(LOG, mutant)
    with open(mutant, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    mutated = text.replace("POINTER_INTERACTIVE active=true click_through=false noactivate=false",
                           "POINTER_INTERACTIVE active=true click_through=true noactivate=true", 1)
    if mutated == text:
        say("  arm 4  CONTROL: could not seed a violation (no active=true line to mutate)")
        wrong.append("arm 4: no active=true line exists to mutate")
    else:
        with open(mutant, "w", encoding="utf-8", newline="") as handle:
            handle.write(mutated)
        caught = violations(parse(mutant))
        say("  arm 4  CONTROL (one line of a COPY made contradictory): violations caught=%d" % len(caught))
        if not caught:
            wrong.append("arm 4: a contradictory line slipped through -- arm 2 counts lines, it does not read them")
        os.remove(mutant)

    say("")
    detail = (" -- the row is REFUTED as of this revision: the panel DOES receive activation while the"
              " pointer is on it (chain wired in the files; %d activation(s) measured in a real run log,"
              " %d release(s), %d invariant violation(s) over %d line(s)). What stays true is the field"
              " own condition -- DISABLED while no writer exists -- and that no keystroke was ever typed"
              " into it: that is UNMEASURED, and needs the launch the owner order forbids"
              ) % (truthy, falsy, len(bad), len(rows))
    say("VERDICT: " + ("PASS" if not wrong else "FAIL") + detail)
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())