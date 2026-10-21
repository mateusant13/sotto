#!/usr/bin/env python
"""ORACLE: Alt+C IS THREE GESTURES AT HUMAN SPEED -- two clocks, and the undo.

OWNER, 2026-10-18, verbatim:
    "pra habilitar a legenda: primeiro alt c. pra ir pro priemiro painel:
     double alt c. caso double alt c, a legenda nao habilita"
    "triple alt c é pra mostrar o painel da direita"

    ONE press    -> the caption on/off
    TWO presses  -> the FIRST panel (the bottom strip)
    THREE        -> the RIGHT panel

WHY THIS FILE WAS REWRITTEN (2026-10-21). It used to model every press inside
ONE window (`HOTKEY_DOUBLE_MS = 250`) and fire every deferred handler only at the
END, after all presses. That coarse model could not see the defect the owner
reported, verbatim: *"alt c nao ta funcionando direito pra abrir o painel"*.
MEASURED on his own running app (real `WM_HOTKEY` posted to the shell's hotkey
thread, the technique `_main/_audit-hotkey-delivery.py` uses): two presses 400 ms
apart -> "caption on, caption off", NOTHING ELSE, because a HUMAN double press is
300-500 ms and the one clock was 250. The harness below is TIME-ACCURATE: it
advances a fake clock and fires each deferred handler at its OWN due time, in
order, BEFORE the next press -- which is what makes the human-speed arms mean
anything.

TWO CLOCKS, and the arms that pin them:
    HOTKEY_CAPTION_DEFER_MS (250)  how long a LONE press waits for the caption
    HOTKEY_GESTURE_MS       (700)  how long a press still belongs to the gesture
and the caption is UNDONE when the gesture grows to a panel, because the first
press of a human double can already have applied it.

THE SCENARIOS, and what each one is really asking:

    one               the caption flips and NO panel appears
    double_fast       (2 @ 120ms)  the strip, the caption NEVER moved
    double_human      (2 @ 400ms)  the strip, the caption NOT left on -- THE BUG
    double_wide       (2 @ 900ms)  two separate gestures -> two captions, no panel
    triple_fast       (3 @ 120ms)  the RIGHT panel, the strip NEVER appeared
    triple_human      (3 @ 400ms)  the RIGHT panel, no strip, caption not left on
    quad_fast         (4 @ 120ms)  right panel, then a NEW gesture -- a caption
    lone_then_double  (1, then a double 900ms later) the FIRST press's caption
                      SURVIVES the later, unrelated double (the id guard)

THE NEGATIVE ARM runs every scenario against deliberately broken COPIES of the
extracted source and compares the WHOLE OBSERVATION MAP (the call sequence AND
the final caption state), not just the scenario the mutant was written for. Two
of the mutants are invisible to a single-scenario comparison, which is why the
map is compared whole: `count >= 2` for the triple produces the same TRIPLE call
list as the control (the difference only shows in `double_*`), and dropping the
post-triple reset produces the same triple list too (the difference only shows in
`quad`).

NOTHING IS LAUNCHED. The four method bodies are EXTRACTED from the shipped file
with `ast` and exec'd against a fake clock and a fake `threading.Timer`. No
Win32, no window, no hotkey, no worker, nothing sleeps.
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
    print(f"  {'GREEN' if ok else 'RED  '} {name}"
          + (f"  {detail}" if detail else ""))
    return bool(ok)


SRC = SHELL.read_text(encoding="utf-8")
tree = ast.parse(SRC)
cls = next((n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SottoShell"), None)
if cls is None:
    print("VERDICT: FAIL -- SottoShell not found")
    sys.exit(EXIT_FAIL)


def _fn(name):
    return next((n for n in cls.body
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)


fn_press = _fn("hotkey_pressed")
fn_double = _fn("_hotkey_double")
fn_single = _fn("_hotkey_single")
fn_undo = _fn("_undo_gesture_caption")

print("ARM structure")
add(fn_press is not None, "hotkey_pressed exists")
add(fn_double is not None, "_hotkey_double exists (the double's own handler)")
add(fn_single is not None, "_hotkey_single still exists")
add(fn_undo is not None, "_undo_gesture_caption exists (the caption put-back)")


def _const(name):
    m = re.search(r"^%s\s*=\s*(\d+)" % name, SRC, re.M)
    return int(m.group(1)) if m else None


CAP = _const("HOTKEY_CAPTION_DEFER_MS")
GEST = _const("HOTKEY_GESTURE_MS")
add(CAP is not None and 100 <= CAP <= 400,
    "the caption deferral is short enough not to feel like lag",
    f"HOTKEY_CAPTION_DEFER_MS={CAP}")
add(GEST is not None and 300 <= GEST <= 1500,
    "the gesture window is wide enough for a human double press",
    f"HOTKEY_GESTURE_MS={GEST}")
add(GEST is not None and CAP is not None and GEST > CAP,
    "the gesture window is WIDER than the caption deferral -- the split that "
    "fixes the bug", f"gesture={GEST} caption={CAP}")

press_src = ast.get_source_segment(SRC, fn_press) or ""
double_src = ast.get_source_segment(SRC, fn_double) or ""
single_src = ast.get_source_segment(SRC, fn_single) or ""
undo_src = ast.get_source_segment(SRC, fn_undo) or ""

add("show_side" in press_src and "hotkey-triple" in press_src,
    "the triple names the RIGHT panel and says so in the log tag")
add("count >= 3" in press_src, "the third press is the branch that fires")
add("_hotkey_press_count" in press_src,
    "the press count is tracked on the shell")
add("HOTKEY_GESTURE_MS" in press_src,
    "the gesture test reads the GESTURE window (the human clock)")
add("HOTKEY_CAPTION_DEFER_MS" in press_src,
    "the caption's deferral is the OTHER clock")
add("_undo_gesture_caption" in press_src,
    "the gesture undoes the caption when it grows to a panel")
add("token !=" in double_src,
    "the deferred double checks the token at RUN time, like the single")
add("show_strip" in double_src, "the double lands on the FIRST panel")
add("_caption_gesture_id" in single_src,
    "the single records which gesture applied the caption")
add("_caption_gesture_id" in undo_src and "_hotkey_gesture_id" in undo_src,
    "the undo is guarded by the gesture id (an old gesture cannot undo a new one)")


# ── the fake world ────────────────────────────────────────────────────────────
SCENARIOS = [
    ("one", []),
    ("double_fast", [120]),
    ("double_human", [400]),
    ("double_wide", [900]),
    ("triple_fast", [120, 120]),
    ("triple_human", [400, 400]),
    ("quad_fast", [120, 120, 120]),
    ("lone_then_double", [900, 50]),
]


class FakeClock:
    """MILLISECONDS from a non-zero base, like `time.monotonic`.

    Not starting at 0.0 matters: the product keeps the last press in
    `self._last_hotkey_press` and decides with `if not (prev and ...)`. A clock
    that starts at 0.0 makes `prev` FALSY and the second press looks like a brand
    new gesture. A fake clock with the wrong base is worse than no fake clock.
    """

    def __init__(self):
        self.ms = 1000_000.0

    def monotonic(self):
        return self.ms / 1000.0


class FakeTimer:
    """A `threading.Timer` that is RECORDED, with its own DUE TIME.

    The product defers the caption and the first panel and decides at RUN time,
    so the oracle has to fire each handler at the moment the owner would see it
    -- and `due` is what lets it fire them in the right order relative to the
    presses.
    """

    def __init__(self, delay, fn, store, clock):
        self.delay = delay
        self.fn = fn
        self.daemon = False
        self.started = False
        self.due = clock.ms + delay * 1000.0
        store.append(self)

    def start(self):
        self.started = True

    def run(self):
        self.fn()


def _indent(src: str) -> str:
    return "\n".join(("    " + ln) if ln.strip() else ln
                     for ln in src.splitlines())


def build_ns(press_body, double_body, single_body, undo_body, clock, timers, log):
    """Exec the four method bodies into a namespace, exactly as shipped."""
    mod = ast.parse("class _M:\n" + _indent(press_body) + "\n"
                    + _indent(double_body) + "\n"
                    + _indent(single_body) + "\n"
                    + _indent(undo_body))

    class TF:
        def Timer(self, delay, fn):
            return FakeTimer(delay, fn, timers, clock)

    ns = {"time": clock, "log": log.append,
          "window_visible": lambda h: False,
          "HOTKEY_CAPTION_DEFER_MS": CAP, "HOTKEY_GESTURE_MS": GEST,
          "threading": TF()}
    exec(compile(ast.Module(body=mod.body[0].body, type_ignores=[]),
                 "<m>", "exec"), ns)
    return ns


def run_scenario(press_body, double_body, single_body, undo_body, gaps):
    """Press Alt+C (len(gaps)+1 times) with a clock, firing timers on time.

    Returns (calls, final_caption, log_lines). `calls` is the sequence the owner
    SAW: ('caption', bool) for a caption change, ('strip'|'side', reason) for a
    panel. The clock is advanced to each press, and every deferred handler whose
    due time has passed is fired FIRST, in due order -- so the measurement is the
    real ordering, not a pile of timers fired at the end.
    """
    clock = FakeClock()
    timers = []
    log = []
    ns = build_ns(press_body, double_body, single_body, undo_body,
                  clock, timers, log)

    class Sh:
        hwnd = 1
        visible = False

        def __init__(self):
            self.calls = []
            self._hotkey_single_token = 0
            self._hotkey_press_count = 0
            self._last_hotkey_press = 0.0
            self._hotkey_gesture_id = 0
            self._caption_wanted = False
            self._caption_gesture_id = None
            self._caption_restore = False

        hotkey_pressed = ns["hotkey_pressed"]
        _hotkey_double = ns["_hotkey_double"]
        _hotkey_single = ns["_hotkey_single"]
        _undo_gesture_caption = ns["_undo_gesture_caption"]

        def _set_live_enabled(self, payload):
            on = bool((payload or {}).get("on"))
            self._caption_wanted = on
            self.calls.append(("caption", on))
            return True

        def show_side(self, reason):
            self.calls.append(("side", reason))
            return True

        def show_strip(self, reason):
            self.calls.append(("strip", reason))
            return True

    sh = Sh()
    fired = set()

    def fire_due(target_ms):
        while True:
            due = [t for t in timers
                   if t.started and t not in fired and t.due <= target_ms]
            if not due:
                break
            nxt = min(due, key=lambda t: t.due)
            clock.ms = max(clock.ms, nxt.due)
            fired.add(nxt)
            nxt.run()

    base = clock.ms
    times = [0.0]
    for g in gaps:
        times.append(times[-1] + g)
    for tms in times:
        fire_due(base + tms)
        clock.ms = max(clock.ms, base + tms)
        sh.hotkey_pressed()
    fire_due(float("inf"))
    return sh.calls, sh._caption_wanted, log


def run_all(press_body, double_body, single_body, undo_body):
    out = {}
    for name, gaps in SCENARIOS:
        calls, final_caption, _log = run_scenario(
            press_body, double_body, single_body, undo_body, gaps)
        out[name] = (calls, final_caption)
    return out


def kinds(calls):
    return [c[0] for c in calls]


def panels(calls):
    return [c[0] for c in calls if c[0] in ("strip", "side")]


def arm_gestures(obs):
    """Every scenario the owner cares about, asserted against the map.

    The HUMAN arms carry caption entries on purpose: at 400 ms the caption's
    250 ms deferral has already fired, so the map shows the caption go on and be
    undone. What must hold is that it is NOT LEFT on and that no strip flashes.
    """
    fails = []
    one_calls, one_cap = obs["one"]
    if kinds(one_calls) != ["caption"] or one_cap is not True:
        fails.append("one press is the caption and nothing else: %r final=%r"
                     % (one_calls, one_cap))

    df_calls, df_cap = obs["double_fast"]
    if (panels(df_calls) != ["strip"] or "caption" in kinds(df_calls)
            or df_cap is not False):
        fails.append("two FAST presses are the FIRST panel and the caption never "
                     "moves: %r final=%r" % (df_calls, df_cap))

    dh_calls, dh_cap = obs["double_human"]
    if (panels(dh_calls) != ["strip"] or dh_cap is not False):
        fails.append("two HUMAN presses (400 ms) are the FIRST panel and the "
                     "caption is NOT left on: %r final=%r" % (dh_calls, dh_cap))

    dw_calls, dw_cap = obs["double_wide"]
    if (kinds(dw_calls) != ["caption", "caption"] or dw_cap is not False
            or panels(dw_calls) != []):
        fails.append("two presses 900 ms apart are TWO gestures -- two captions "
                     "and NO panel: %r final=%r" % (dw_calls, dw_cap))

    tf_calls, tf_cap = obs["triple_fast"]
    if (panels(tf_calls) != ["side"] or tf_cap is not False):
        fails.append("three FAST presses are the RIGHT panel, strip NEVER on the "
                     "way, caption never moved: %r final=%r"
                     % (tf_calls, tf_cap))

    th_calls, th_cap = obs["triple_human"]
    if (panels(th_calls) != ["side"] or th_cap is not False):
        fails.append("three HUMAN presses (400 ms) are the RIGHT panel, no strip "
                     "flash, caption not left on: %r final=%r"
                     % (th_calls, th_cap))

    q_calls, q_cap = obs["quad_fast"]
    if (panels(q_calls) != ["side"] or kinds(q_calls)[-1:] != ["caption"]
            or q_cap is not True):
        fails.append("four presses give the right panel then a NEW gesture (a "
                     "caption): %r final=%r" % (q_calls, q_cap))

    lt_calls, lt_cap = obs["lone_then_double"]
    if (panels(lt_calls) != ["strip"] or kinds(lt_calls)[0] != "caption"
            or lt_cap is not True):
        fails.append("a lone press's caption SURVIVES a later, unrelated double "
                     "(the undo is id-guarded): %r final=%r"
                     % (lt_calls, lt_cap))
    return fails


control = run_all(press_src, double_src, single_src, undo_src)

print("\nARM the gestures, executed from the file's own source (time-accurate)")
add(not arm_gestures(control), "the whole gesture map is the owner's contract",
    "" if not arm_gestures(control) else "; ".join(arm_gestures(control)))

print("\nARM the undo is LOUD and the log names the gesture")
_log_lines = run_scenario(press_src, double_src, single_src, undo_src, [400])[2]
add(any("HOTKEY_CAPTION_UNDONE" in ln for ln in _log_lines),
    "the human double logs HOTKEY_CAPTION_UNDONE",
    next((ln for ln in _log_lines if "HOTKEY_CAPTION_UNDONE" in ln), "NO LOG"))
_ff = run_scenario(press_src, double_src, single_src, undo_src, [120])[2]
add(not any("HOTKEY_CAPTION_UNDONE" in ln for ln in _ff),
    "the FAST double logs NO undo (the caption never moved)",
    "clean" if not any("HOTKEY_CAPTION_UNDONE" in ln for ln in _ff) else "undo logged")
add(any("HOTKEY_DOUBLE panel=strip" in ln for ln in _ff),
    "the double logs which panel it raised",
    next((ln for ln in _ff if "HOTKEY_DOUBLE panel" in ln), "NO LOG"))

print("\nNEGATIVE ARM -- every scenario, against deliberately broken copies")
MUTANTS = [
    ("M1 the triple threshold drops to two", press_src,
     "count >= 3", "count >= 2"),
    ("M2 the triple paints the strip", press_src,
     "return self.show_side('hotkey-triple')",
     "return self.show_strip('hotkey-triple')"),
    ("M3 the pending caption is not retired", press_src,
     "            self._hotkey_single_token = getattr(self, "
     "'_hotkey_single_token', 0) + 1",
     "            pass  # MUTANT M3"),
    ("M4 the double is immediate again", press_src,
     "if count == 1:\n            handler, defer_ms = self._hotkey_single, "
     "HOTKEY_CAPTION_DEFER_MS\n        else:\n            handler, defer_ms = "
     "self._hotkey_double, HOTKEY_GESTURE_MS",
     "if count == 1:\n            handler, defer_ms = self._hotkey_single, "
     "HOTKEY_CAPTION_DEFER_MS\n        else:\n            return "
     "self.show_strip('hotkey-double')"),
    ("M5 the gesture is never closed", press_src,
     "self._hotkey_press_count = 0\n            self._last_hotkey_press = 0.0\n"
     "            self._undo_gesture_caption()\n            return self.show_side",
     "return self.show_side"),
    ("M6 the window is per gesture, not per press", press_src,
     "if not (prev and (now - prev) * 1000.0 <= HOTKEY_GESTURE_MS):\n"
     "            prev, count = 0.0, 0\n"
     "            self._hotkey_gesture_id = getattr(self, "
     "'_hotkey_gesture_id', 0) + 1",
     "pass  # MUTANT M6"),
    ("M7 the gesture window is the caption deferral", press_src,
     "(now - prev) * 1000.0 <= HOTKEY_GESTURE_MS",
     "(now - prev) * 1000.0 <= HOTKEY_CAPTION_DEFER_MS"),
    ("M8 the caption is not undone", press_src,
     "            self._undo_gesture_caption()\n"
     "            self._hotkey_single_token",
     "            self._hotkey_single_token"),
    ("M9 the undo ignores the gesture id", undo_src,
     "if getattr(self, '_caption_gesture_id', None) != gid:\n            "
     "return False",
     "pass  # MUTANT M9"),
]
for label, base, old, new in MUTANTS:
    if old not in base:
        add(False, f"mutant {label!r} could not be built", f"anchor={old!r}")
        continue
    if base is undo_src:
        mutant = run_all(press_src, double_src, single_src,
                         base.replace(old, new, 1))
    else:
        mutant = run_all(base.replace(old, new, 1), double_src, single_src,
                         undo_src)
    diff = [name for name, _gaps in SCENARIOS if mutant[name] != control[name]]
    noticed = arm_gestures(mutant)
    add(bool(diff) and bool(noticed), f"mutant {label!r} is caught",
        ("differs in " + ", ".join(diff)) if diff
        else "NOTHING -- invisible")
    if not noticed and diff:
        add(False, f"mutant {label!r} changed behaviour and NO ARM NOTICED",
            "; ".join(f"{k}={mutant[k]!r}" for k in diff))


def _main():
    bad = [r for r in rows if not r[0]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} GREEN")
    if bad:
        print("VERDICT: FAIL")
        for _, n, d in bad:
            print(f"  - {n}" + (f"  {d}" if d else ""))
        return EXIT_FAIL
    print("VERDICT: PASS")
    return EXIT_PASS


sys.exit(_main())
