#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
"""NAMED-PANEL-STATE ORACLE -- does the panel's own name tell the truth?

THE DEFECT (measured live 2026-10-12 16:47, read-only, nothing launched):
`_main/panel-state.json` carried `namedState="no-audio"` in the SAME write as
`panel.live.count=201` and `panel.status={"kind":"live","text":""}` -- the
panel was demonstrably receiving captions and its own name said no-audio.

THE MECHANISM, in the shell's own reader: `panel.js:2896-2903` blanks
`#status-text` for every state that is not an error (the owner ruled
2026-10-08, verbatim: "tira o 'receiving captions'. deixa so um icone
dinamico"), so the live state is an ICON and the element's text is ''.
`panel_state_snapshot` reads only `.text` and `_named_panel_state` tests
`panel_status == 'Receiving captions'` FIRST -- a comparison that is DEAD on
the live path. The precedence therefore falls through to the worker's
`noAudio` latch, which a caption never clears, and the name lies.

ARMS (all in process, over `panel_state`-shaped payloads):
  1  THE LIVE PATH: text='' kind='live' noAudio=True   -> 'receiving'  (the bug)
  2  the sentence, for a panel that still paints it       -> 'receiving'
  3  a death, held until a caption proves recovery        -> the death state
  4  a quiet worker, panel idle                          -> 'no-audio'
  5  no bridge at all                                    -> 'no-worker'
  6  an idle worker, nothing latched                      -> 'idle'
  7  the worker's own error vocabulary                    -> that state
  8  NEGATIVE control: the OLD predicate (text only) must FAIL arm 1.

Launches nothing. Receipt: _main/receipt-20261012-leak-loop-hunt.md
"""
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), "app", "webview", "sotto_webview.py")
NEG = "--neg-arm" in sys.argv
BROKEN = []


def check(name, got, want):
    ok = got == want
    print("  [%s] %-46s got=%-16s want=%s" % ("PASS" if ok else "FAIL", name, got, want))
    if not ok:
        BROKEN.append(name)
    return ok


def main():
    sys.path.insert(0, os.path.dirname(SHELL))
    import importlib.util
    spec = importlib.util.spec_from_file_location("_shell_under_test", SHELL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    print("shell: %d bytes" % os.path.getsize(SHELL))

    fn = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and hasattr(obj, "_named_panel_state"):
            fn = getattr(obj, "_named_panel_state")
            print("predicate: %s._named_panel_state" % attr)
            break
    if fn is None:
        print("RED -- _named_panel_state not found")
        return 1

    ARITY = len(inspect.signature(fn).parameters)

    def named(worker, text, kind=None):
        if NEG or ARITY < 3:
            # THE OLD PREDICATE, restored: the text test alone. This is the arm
            # that must go RED, so the oracle can say NO. (On the shipped file the
            # signature is still (worker, panel_status), so the kind is dropped
            # here too -- which IS the defect, measured rather than assumed.)
            return fn(worker, text)
        return fn(worker, text, kind)

    live = {"state": "no-audio", "noAudio": True,
            "noAudioEvidence": "device-rotated reason=flat peak=0.0 floor=0.002",
            "pendingError": None}
    dead = {"state": "no-audio", "noAudio": True,
            "pendingError": {"state": "silent-device",
                             "text": "Worker finished on silent-device"}}
    quiet = {"state": "no-audio", "noAudio": True, "pendingError": None}
    idle = {"state": "", "noAudio": False, "pendingError": None}
    erring = {"state": "silent-device", "noAudio": False, "pendingError": None}

    print("\n-- ARM 1-7: the truth table -----------------------------------")
    check("1 LIVE text='' kind='live' noAudio=True",
          named(live, "", "live"), "receiving")
    check("2 the sentence, if a panel still paints it",
          named(live, "Receiving captions", "live"), "receiving")
    check("3 a death held until a caption proves recovery",
          named(dead, "", None), "silent-device")
    check("4 a quiet worker, panel idle",
          named(quiet, "", None), "no-audio")
    check("5 no bridge at all",
          named(None, "", None), "no-worker")
    check("6 an idle worker, nothing latched",
          named(idle, "", None), "idle")
    check("7 the worker's own error vocabulary",
          named(erring, "", None), "silent-device")

    print("\n-- ARM 8: the LIVE path is the one that must move ------------")
    old = fn(live, "")
    new = named(live, "", "live")
    check("old predicate says no-audio on the live path", old, "no-audio")
    check("new predicate says receiving on the live path", new, "receiving")

    print("\n-- VERDICT ----------------------------------------------------")
    if NEG:
        print("  NEG-ARM: the restored old predicate must be RED on arm 1.")
        print("  failures: %d (must be > 0)" % len(BROKEN))
        return 0 if BROKEN else 1
    print("  failures: %d" % len(BROKEN))
    if BROKEN:
        print("  RED -- " + "; ".join(BROKEN[:4]))
        return 1
    print("  PASS -- the panel's own live icon outranks the worker's no-audio latch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
