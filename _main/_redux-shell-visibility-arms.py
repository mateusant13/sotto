#!/usr/bin/env python3
"""Sotto — the SHELL'S OWN show/hide publishes the visibility file (executed).

WHY NOT JUST ASSERT THE SOURCE. `_main/redux-flag-gate.py` proves the calls are
wired by reading the file; a source assertion cannot tell whether the VALUE the
call publishes is the measured one, and "we called publish" is precisely the
stale-intention class this repo has already been bitten by
(`PANEL_VISIBILITY_CACHE_STALE`, and a panel on screen while
`PANEL_VISIBILITY_AT_STARTUP` said `visible=false`).

So this arm EXECUTES the real `SottoShell.show_panel` / `hide_panel` /
`observe_panel_visible` with the Win32 boundary replaced by a scripted
`window_visible`, and reads the file they wrote:

  hide        `hide_panel('hotkey')`            -> file says visible=false,
              reason=hotkey, and the log carries
              `PANEL_VISIBILITY_MODE visible=false reason=hotkey`
  show        `show_panel('hotkey')`            -> visible=true, reason=hotkey
  show-fails  the window REFUSES to map (the scripted `window_visible` stays
              False) -> the file must STILL say visible=false. A shell that
              published the INTENTION here would send the worker back to
              streaming for a panel nobody can see.
  cadence     `PANEL_VISIBILITY_INTERVAL_S` is shortened and the cadence writer
              is left to run: it must refresh the dump WITHOUT inventing a
              transition, which is what keeps `writtenAtEpoch` fresh for a reader
              that refuses stale answers — and is the only thing that records a
              visibility change nobody announced.
  stale-refused  the file the shell wrote is then aged past `staleAfterSeconds`
              and the WORKER's own reader is asked for its verdict: it must
              answer visible=true. The two halves are put side by side here
              because "the producer stamps an age" and "the consumer refuses a
              stale age" are different claims, and only the pair is worth
              anything.

NOTHING here opens a window, registers a hotkey or opens an audio device: no
WebView2 object is created, no `create_window` is called, and the Win32 calls are
replaced before any of them can run.

    python _main/_redux-shell-visibility-arms.py     # or pythonw.exe

Exit 0 when every arm holds, 1 otherwise, 2 on a setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL_DIR = os.path.join(ROOT, "app", "webview")
WORKER_DIR = os.path.join(ROOT, "worker")
TMP = os.path.join(HERE, "_redux-shell-visibility.json")
LOG = os.path.join(HERE, "_redux-shell-visibility.log")

sys.path.insert(0, SHELL_DIR)
sys.path.insert(0, WORKER_DIR)

lines: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(msg, flush=True)


class Args:
    """The minimum `SottoShell.__init__` reads. NOT a parser and not a stub of
    one: the shell only ever reads these attributes, and inventing a full
    Namespace would let this arm pass while `main()`'s real flags drifted."""

    show = False
    hotkey = 'alt+c'
    python = sys.executable
    worker = os.path.join(WORKER_DIR, "sotto_worker.py")
    device = None
    capture = None
    ready_file = None
    log = None
    no_worker = True
    with_worker = False
    dump_dom = False
    selftest = False
    memory = False
    no_hotkey = True
    exit_after = 0.0
    probe_v2 = False
    verbose = False


def main() -> int:
    ap = argparse.ArgumentParser(prog="redux-shell-visibility-arms")
    ap.add_argument("--keep", action="store_true", help="keep the dump written")
    args = ap.parse_args()

    import sotto_webview as shell

    problems: list[str] = []
    logs: list[str] = []

    # ── the Win32 boundary, replaced before it can be reached ────────────────
    # A scripted window: `VISIBLE = False` means the window refuses to map.
    window = {"visible": False, "shows": 0, "hides": 0}
    shell.window_visible = lambda hwnd: bool(window["visible"])
    shell.set_topmost = lambda hwnd: None
    shell.hide_window = lambda hwnd: window.__setitem__("visible", False)

    def fake_show(hwnd):
        # `SW_SHOWNOACTIVATE` succeeded or not is a fact about the WINDOW, and
        # the scripted window is the only thing that decides it here.
        window["shows"] += 1
        if not window.get("refuse_show", False):
            window["visible"] = True
    shell.show_without_activating = fake_show
    # The real `log` goes to the shell's log file; this arm wants it in memory.
    shell.log = lambda msg: logs.append(msg)
    shell.warn = lambda msg: logs.append('WARN ' + msg)

    if os.path.exists(TMP):
        os.remove(TMP)
    shell.PANEL_VISIBILITY_PATH = TMP
    shell.PANEL_VISIBILITY_INTERVAL_S = 0.4

    obj = shell.SottoShell(Args())
    # `hwnd` is a fake: nothing in these code paths dereferences it, because the
    # three Win32 functions above are the only ones that would.
    obj.hwnd = 0x1234
    obj.visible = False

    started = obj.start_panel_visibility()
    say(f"ARM boot      start_panel_visibility() -> {started}, "
        f"path={os.path.relpath(TMP, ROOT)}")

    def read_dump():
        with open(TMP, encoding="utf-8") as fh:
            return json.load(fh)

    def mode_lines():
        return [ln for ln in logs if ln.startswith("PANEL_VISIBILITY_MODE")]

    boot = read_dump()
    say(f"ARM boot      dump visible={boot.get('visible')} reason={boot.get('reason')} "
        f"schema={boot.get('schema')} pid={boot.get('pid')} since_ms={boot.get('since_ms')}")
    if boot.get("visible") is not False:
        problems.append("boot: the file does not start hidden")
    for key in ("visible", "since_ms", "pid", "writtenAtEpoch"):
        if key not in boot:
            problems.append(f"boot: the frozen shape is missing {key!r}")
    if boot.get("schema") != shell.PANEL_VISIBILITY_SCHEMA:
        problems.append(f"boot: schema={boot.get('schema')!r}")

    # ── show: the owner pressed Alt+C on a hidden panel ─────────────────────
    # The arms run in the order the owner's OWN sequence runs, and that order is
    # load-bearing: the writer publishes a TRANSITION, so a `hide_panel` on a file
    # that already says hidden is correctly a no-op and proves nothing. (The first
    # version of this arm made exactly that mistake, and its RED was a real
    # finding about the arm, not about the shell.)
    obj.show_panel('hotkey')
    time.sleep(0.05)
    after_show = read_dump()
    say(f"ARM show      dump visible={after_show.get('visible')} "
        f"reason={after_show.get('reason')}")
    say(f"ARM show      log: {mode_lines()[-1] if mode_lines() else 'NONE'}")
    if after_show.get("visible") is not True:
        problems.append("show: the dump does not say visible=true")
    if after_show.get("reason") != "hotkey":
        problems.append(f"show: reason={after_show.get('reason')!r} (expected 'hotkey')")
    if not any("PANEL_VISIBILITY_MODE visible=true reason=hotkey" in ln for ln in logs):
        problems.append("show: no `PANEL_VISIBILITY_MODE visible=true reason=hotkey` line")

    # ── hide: he pressed Alt+C again ────────────────────────────────────────
    obj.hide_panel('hotkey')
    time.sleep(0.05)
    after_hide = read_dump()
    say(f"ARM hide      dump visible={after_hide.get('visible')} "
        f"reason={after_hide.get('reason')} age_ms={after_hide.get('age_ms')}")
    say(f"ARM hide      log: {mode_lines()[-1] if mode_lines() else 'NONE'}")
    if after_hide.get("visible") is not False:
        problems.append("hide: the dump still says visible=true")
    if after_hide.get("reason") != "hotkey":
        problems.append(f"hide: reason={after_hide.get('reason')!r} (expected 'hotkey')")
    if not any("PANEL_VISIBILITY_MODE visible=false reason=hotkey" in ln for ln in logs):
        problems.append("hide: no `PANEL_VISIBILITY_MODE visible=false reason=hotkey` line")
    if after_hide.get("since_ms") == after_show.get("since_ms"):
        problems.append("hide: since_ms did not move on the transition")

    # ── show-fails: the window REFUSES to map ──────────────────────────────
    # The honest-measurement arm. `show_without_activating` returns, the window
    # does not become visible, and the file must keep saying false — that is what
    # keeps the worker on the batch path for a panel nobody can see.
    window["refuse_show"] = True
    window["visible"] = False
    obj.visible = False
    obj.show_panel('hotkey')
    time.sleep(0.05)
    after_refused = read_dump()
    say(f"ARM show-fail dump visible={after_refused.get('visible')} "
        f"(the window refused to map)")
    if after_refused.get("visible") is not False:
        problems.append("show-fail: the shell published the INTENTION, not the window")
    window["refuse_show"] = False

    # ── cadence: a refresh that must NOT invent a transition ───────────────
    transitions_before = read_dump().get("transitions")
    stamp_before = read_dump().get("writtenAtEpoch")
    time.sleep(1.2)
    cadence_dump = read_dump()
    say(f"ARM cadence   writtenAtEpoch {stamp_before} -> {cadence_dump.get('writtenAtEpoch')} "
        f"transitions {transitions_before} -> {cadence_dump.get('transitions')}")
    if not (cadence_dump.get("writtenAtEpoch", 0) > stamp_before):
        problems.append("cadence: the dump was not refreshed")
    if cadence_dump.get("transitions") != transitions_before:
        problems.append("cadence: a refresh INVENTED a transition")

    # ── the same file, an unannounced change: the cadence must catch it ────
    # This is pywebview's own navigation-time `Show`, `_reassert_hidden`, or a hot
    # reload: the window moved and NOBODY called show/hide. If the cadence did not
    # re-read the window, the file would diverge from the screen silently.
    window["visible"] = True
    obj.visible = False          # the shell's cache does NOT know
    time.sleep(1.2)
    caught = read_dump()
    say(f"ARM unannounced window mapped with no show() call -> "
        f"dump visible={caught.get('visible')} reason={caught.get('reason')} "
        f"transitions={caught.get('transitions')}")
    if caught.get("visible") is not True:
        problems.append("unannounced: the cadence did not catch a window that mapped "
                        "without a show/hide call")
    if caught.get("reason") != "poll":
        problems.append(f"unannounced: reason={caught.get('reason')!r} (expected 'poll', "
                        f"which is what says the FILE is the only record of it)")

    # ── the CONSUMER refuses a stale answer ────────────────────────────────
    obj.panel_visibility.stop('probe')
    stale = dict(caught)
    stale["visible"] = False
    stale["writtenAtEpoch"] = round(time.time() - 60.0, 3)
    stale["staleAfterSeconds"] = 5.0
    with open(TMP, "w", encoding="utf-8") as fh:
        json.dump(stale, fh)
    import sotto_worker as worker

    reader = worker.PanelVisibilityReader(TMP)
    visible, why, age = reader.read()
    say(f"ARM stale     worker.PanelVisibilityReader on a 60 s old dump -> "
        f"visible={visible} why={why} age={age}")
    if visible is not True:
        problems.append("stale: a stale dump did not read as VISIBLE (the worker would "
                        "have obeyed a dead shell)")
    if not str(why).startswith("stale"):
        problems.append(f"stale: why={why!r} (expected a stale(...) reason)")

    # ...and the FRESH dump the shell wrote must read as the truth.
    fresh = dict(caught)
    fresh["writtenAtEpoch"] = round(time.time(), 3)
    fresh["visible"] = False
    with open(TMP, "w", encoding="utf-8") as fh:
        json.dump(fresh, fh)
    visible2, why2, _ = reader.read()
    say(f"ARM fresh     the same file, fresh -> visible={visible2} why={why2}")
    if visible2 is not False or why2 != "fresh":
        problems.append(f"fresh: a fresh hidden dump read as visible={visible2} why={why2}")

    if not args.keep and os.path.exists(TMP):
        os.remove(TMP)

    say("")
    if problems:
        for p in problems:
            say(f"!! {p}")
        say(f"SHELL-VISIBILITY-VERDICT: RED — {len(problems)} arm(s) moved")
        return 1
    say("SHELL-VISIBILITY-VERDICT: GREEN — the shell's own show_panel/hide_panel publish "
        "the MEASURED window state (a show that fails keeps saying hidden), the cadence "
        "refreshes without inventing transitions and catches a window nobody announced, "
        "and the worker's reader refuses a stale dump while believing a fresh one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
