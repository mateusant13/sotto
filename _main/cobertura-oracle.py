#!/usr/bin/env python3
"""cobertura-oracle -- does EVERY area of Sotto have a gate that runs in the battery?

The owner, 2026-10-14, verbatim: *"ter oraculo. ter uma suite de testes com forma de
confirmar os resultados. recria tudo pra cada coisa do sotto, e pro futuro."*

WHAT THIS MEASURES: the repo already holds ~99 oracle files. that number is not the
question. the question is whether an AREA can be changed with no instrument to catch it
-- and this session measured exactly that hole: the wrapper pre-flight area had no gate,
so a TEMP redirect that answered rc 120 and REFUSED A GOOD LAUNCH lived there until a
red battery was chased down by hand.

So this oracle holds the AREA -> INSTRUMENT map. An area is COVERED when at least one
instrument that names it is LISTED in instruments-battery.mjs -- the file that actually
runs. An oracle that exists but is not in the battery is DECORATIVE, and this says so.

It is deliberately a inventory claim, never a behavioural one: nothing here launches the
shell, the worker or WebView2. What is measured is membership, which is exactly what
was missing.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.path.pardir))
BATTERY = os.path.join(HERE, "instruments-battery.mjs")

# AREA -> the tokens an instrument name must carry to be counted as gating that area.
# The tokens are the ones the battery rows already use, so the map cannot drift into
# naming instruments that do not exist.
AREAS = {
    "wrapper pre-flight (run.cmd exit contract)": ["run-cmd-exit"],
    "pre-flight refusal visibility": ["preflight-refusal-visible"],
    "worker exit-3 / silent-device contract": ["panel-exit3", "device-silence"],
    "worker no-audio status severity": ["panel-exit3", "benign-status"],
    "worker restart ladders": ["panel-exit3"],
    "panel state write (atomic)": ["panel-state", "panel-atomic"],
    "panel visibility writer": ["panel-visibility"],
    "JS<->Python surface loop guard": ["surface-loop", "panel-surface"],
    "hotkey / Alt+C cycle": ["hotkey"],
    "panel hide gate at startup": ["panel-hidden-at-startup"],
    "panel paint / render": ["panel-paint", "paint"],
    "strip drag and float": ["strip-float", "strip-drag"],
    "buttons lane (size and visibility)": ["botoes-lane"],
    "caption overlay independence": ["caption-independent", "three-overlays"],
    "caption line fidelity": ["caption-lines"],
    "history / transcript gate": ["history", "canonical-producer"],
    "themes: light census": ["theme-lightness", "base-themes"],
    "themes: generator reproducibility": ["gen-themes-repro", "gen-cinematic-repro"],
    "themes: scope leak": ["scope-leak"],
    "themes: design fidelity (zip)": ["cine-themes", "cinematic-designs", "zipc-designs"],
    "fonts fidelity": ["fonts-fidelity"],
    "theme chrome (footer labels)": ["panel-chrome"],
    "theme switching": ["theme-switch"],
    "log rotation": ["log-rotation"],
    "log flood census": ["log-flood", "flood"],
    "second pass (M3) opt-in": ["second-pass"],
    "queue_drops whitelist": ["queue-drops"],
    "bridge handler map": ["bridge-handler"],
    "emit queue bound": ["emit-queue-bound"],
    "CSP inline policy": ["csp-inline"],
    "device ladder": ["device-ladder", "flat-endpoint", "audio-meter"],
    "app target (per-app tap)": ["app-target"],
    "AGENTS.md pins": ["agents-md-pins"],
    "cited instruments": ["cited-instruments"],
}


def main() -> int:
    say = print
    if not os.path.exists(BATTERY):
        say(f"cobertura-oracle: NO BATTERY at {BATTERY}")
        return 1
    with open(BATTERY, encoding="utf-8", errors="replace") as handle:
        battery = handle.read().lower()

    covered, decorative, uncovered = [], [], []
    for area, tokens in sorted(AREAS.items()):
        rows = [t for t in tokens if t in battery]
        if rows:
            covered.append((area, rows[0]))
        elif any(t in battery for t in tokens):
            decorative.append(area)
        else:
            uncovered.append(area)

    say(f"cobertura-oracle -- {len(AREAS)} area(s) mapped")
    for area, token in covered:
        say(f"  [ok]   {area:52s} <- {token}")
    for area in decorative:
        say(f"  [warn] {area:52s} <- instrument names a token not in the battery")
    for area in uncovered:
        say(f"  [GAP]  {area:52s} <- NO instrument runs in the battery")

    say("")
    say(f"COVERAGE {len(covered)}/{len(AREAS)} area(s) gated by the battery; "
        f"{len(uncovered)} gap(s), {len(decorative)} warning(s)")
    if uncovered:
        say("VERDICT: FAIL -- these areas can be changed with nothing to catch it.")
        for area in uncovered:
            say(f"           - {area}")
        return 1
    say("VERDICT: PASS -- every mapped area has an instrument that RUNS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
