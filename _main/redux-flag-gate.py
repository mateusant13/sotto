#!/usr/bin/env python3
"""Sotto — THE STACK LAW'S WIRING GATE: is `--redux-when-hidden` OFF, and is the
switch actually WIRED, or merely present?

WHY THIS EXISTS. The two halves of this lane are a flag and a file, and both of
them have a failure mode this repo has already paid for once: a value that is
COMPUTED and then DISCARDED. `_main/_audit-worker-start-wiring.py` was written
after `_worker_autostart_reason` returned a clean five-word rule that
`start_worker` never read — 15 green arms on the RULE, and the machine did
something else entirely. So this gate asks the wiring question in BOTH directions
and it is deliberately a SOURCE assertion, not an execution: running the real
switch would spawn the batch runner and drive a mode change, and a gate in this
repo may not open an audio device or a process to make its point.

WHAT IT ASSERTS (each a named arm, so a failure names the claim):
  flag-exists      `--redux-when-hidden` is parsed, is `store_true`, and its
                   default IS the `False` constant — the brief's DEFAULT OFF.
  flag-guarded     the switch is CONSTRUCTED only under `if args.redux_when_hidden:`
                   — a switch built unconditionally would run with the flag off.
  switch-wired     the live loop CONSULTS it (`switch.tick()`) and CONSUMES the
                   answer: the batch mode must SKIP the streaming decode, which
                   is the whole point of the light path.
  stamp            the batch lines carry the literal `'redux'` in `producer` —
                   the ONE field `app/panel/history-source.js:51,61-63`
                   accepts, and which no producer in this tree wrote before.
  hard-rule        a missing runner REFUSES the switch (`armed` needs BOTH the
                   flag and the runner) and says so in `REDUX_SWITCH_REFUSED`.
  fail-safe        the visibility reader falls back to `visible=True` (KEEP
                   STREAMING) on a missing / unreadable / unknown-shape / stale
                   dump. The reader must never manufacture "hidden".
  payload-guarded  the `redux*` fields are added to `done` and to WORKER_STATS
                   ONLY when the switch exists, which is what makes "flag off =
                   byte-identical to today" a checkable claim.
  shell-loop       the shell's writer runs on a CADENCE (a thread, an interval)
                   and not only on transitions, so a map nobody announced is
                   still recorded.

BOTH COLOURS IN ONE COMMAND. The shipped files must come out GREEN, and SEVEN
mutated COPIES — one per claim, each reverting exactly that claim — must each go
RED on that claim and ONLY that claim, which is what makes it a control:
`python _main/redux-flag-gate.py --neg-arm`.
Nothing is written next to the shipped sources: the mutants live in
`_main/_redux-gate-mutants/`.

    python _main/redux-flag-gate.py              # shipped files, expect GREEN
    python _main/redux-flag-gate.py --neg-arm    # + 7 mutants, expect each RED
    python _main/redux-flag-gate.py --worker P --shell P   # a specific pair

Exit 0 when every claim holds in the shipped pair AND every mutant moves exactly
its own claim; 1 otherwise; 2 on a setup error.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WORKER_DEFAULT = os.path.join(ROOT, "worker", "sotto_worker.py")
SHELL_DEFAULT = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
MUTANT_DIR = os.path.join(HERE, "_redux-gate-mutants")
LOG = os.path.join(HERE, "_redux-gate.log")

lines: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# the claims — each returns (ok, detail)
# ---------------------------------------------------------------------------

def check_worker(src: str):
    """-> (claims: dict[str,bool], notes: list[str])"""
    claims: dict[str, bool] = {}
    notes: list[str] = []

    # ── flag-exists ────────────────────────────────────────────────────────
    const = re.search(r'REDUX_WHEN_HIDDEN_DEFAULT\s*=\s*(True|False)', src)
    const_false = bool(const) and const.group(1) == "False"
    parser = re.search(
        r'"--redux-when-hidden",\s*\n\s*action="store_true",\s*\n'
        r'\s*default=REDUX_WHEN_HIDDEN_DEFAULT', src)
    claims["flag-exists"] = bool(parser) and const_false
    notes.append(
        f'flag-exists: store_true+default=REDUX_WHEN_HIDDEN_DEFAULT={bool(parser)} '
        f'REDUX_WHEN_HIDDEN_DEFAULT=False={const_false}')

    # ── flag-guarded ───────────────────────────────────────────────────────
    guarded = re.search(r'if redux_optin:\s*\n\s*switch = ReduxHiddenSwitch\(',
                        src)
    unconditional = "switch = ReduxHiddenSwitch(" in src and not guarded
    claims["flag-guarded"] = bool(guarded) and not unconditional
    notes.append(f'flag-guarded: construction under `if redux_optin:`'
                 f'={bool(guarded)}')

    # ── env-optin ──────────────────────────────────────────────────────────
    # The shell spawns this worker and has no general "extra worker flags"
    # channel, so a flag with no environment counterpart would be unreachable in
    # the shipped app — a switch nobody can turn on. The env var must be read,
    # compared to '1', and it must OR with the flag rather than replace it.
    env_read = re.search(
        r'str\(os\.environ\.get\("SOTTO_REDUX_WHEN_HIDDEN"\)\s*or\s*""\)'
        r'\.strip\(\)\s*==\s*"1"', src)
    orred = re.search(r'redux_optin = bool\(args\.redux_when_hidden\) or \(', src)
    claims["env-optin"] = bool(env_read) and bool(orred)
    notes.append(f'env-optin: reads SOTTO_REDUX_WHEN_HIDDEN==1={bool(env_read)} '
                 f'ORs with the flag={bool(orred)}')

    # ── switch-wired ───────────────────────────────────────────────────────
    # Both halves: the answer is READ (`switch.tick()`) and it is CONSUMED — the
    # `continue` that skips the streaming chunking is the consumption.
    tick = re.search(r'if switch is not None:\s*\n\s*wanted = switch\.tick\(\)', src)
    consumes = re.search(
        r'if mode == "batch":\s*\n(?:\s*#[^\n]*\n)*\s*switch\.add_audio\(block\)\s*\n'
        r'\s*switch\.maybe_kick\(\)\s*\n\s*continue', src)
    in_loop = "switch.tick()" in src
    claims["switch-wired"] = bool(tick) and bool(consumes) and in_loop
    notes.append(f'switch-wired: tick()-guarded={bool(tick)} '
                 f'batch-continues-past-the-decode={bool(consumes)}')

    # ── stamp ──────────────────────────────────────────────────────────────
    prod_const = re.search(r'REDUX_PRODUCER\s*=\s*"redux"', src)
    stamped = re.search(r'"producer":\s*str\(payload\.get\("producer"\)\s*or\s*'
                        r'REDUX_PRODUCER\)', src)
    final_true = re.search(r'"final":\s*True,\s*\n\s*"producer":', src)
    claims["stamp"] = bool(prod_const) and bool(stamped) and bool(final_true)
    notes.append(f'stamp: REDUX_PRODUCER=="redux"={bool(prod_const)} '
                 f'caption carries producer={bool(stamped)} '
                 f'final:True beside it={bool(final_true)}')

    # ── hard-rule ──────────────────────────────────────────────────────────
    armed = re.search(
        r'self\.armed\s*=\s*bool\(self\.enabled and self\.runner_available\)', src)
    refused = "REDUX_SWITCH_REFUSED armed=false reason=runner-missing" in src
    claims["hard-rule"] = bool(armed) and refused
    notes.append(f'hard-rule: armed needs flag AND runner={bool(armed)} '
                 f'refusal is LOUD={refused}')

    # ── fail-safe ──────────────────────────────────────────────────────────
    # Every failure the reader can hit must return True (keep streaming), and the
    # FALLBACK ITSELF must return True — that second half is not decoration. The
    # first version of this claim only counted `return self._fallback(...)` sites
    # inside `read()`, so a mutant that made `_fallback` return False left the
    # claim GREEN: a presence test certifying a value it never read, which is the
    # exact defect class this gate exists to catch, caught here by the gate's own
    # negative arm.
    read_body = re.search(r'def read\(self\):(.*?)\n    def ', src, re.S)
    body = read_body.group(1) if read_body else ""
    fb_body = re.search(r'def _fallback\(self, why, age\):(.*?)(?=\n    def |\n\nclass )',
                        src, re.S)
    fb = fb_body.group(1) if fb_body else ""
    fallback_sites = len(re.findall(r'return self\._fallback\(', body))
    false_returns = len(re.findall(r'return False,', body + fb))
    fb_true = bool(re.search(r'return True, why, age', fb))
    claims["fail-safe"] = (fallback_sites >= 3 and false_returns == 0 and fb_true)
    notes.append(f'fail-safe: fallback-sites={fallback_sites} '
                 f'the fallback itself returns True={fb_true} '
                 f'`return False,`(must be 0)={false_returns}')

    # ── payload-guarded ────────────────────────────────────────────────────
    done_guard = re.search(r'if switch is not None:\s*\n\s*done_payload\.update\(',
                           src)
    stats_guard = re.search(r'if switch is not None:\s*\n\s*line \+= \(', src)
    carries_verdict = "reduxCaptions=counters[\"redux_captions\"]" in src
    claims["payload-guarded"] = bool(done_guard) and bool(stats_guard) and carries_verdict
    notes.append(f'payload-guarded: done guarded={bool(done_guard)} '
                 f'stats guarded={bool(stats_guard)} '
                 f'reduxCaptions published={carries_verdict}')

    # Two more facts that are cheap and are the difference between "the light
    # path ran" and "it ran and its lines were counted": the verdict function
    # must SUM both producers, or a hidden-from-start run is verdicted a failure
    # word and the panel paints it as an error.
    emitted = re.search(
        r'emitted = counters\.get\("captions", 0\) \+ counters\.get\("redux_captions", 0\)',
        src)
    verdict_uses = len(re.findall(r'\bemitted\b', src))
    claims["verdict-counts-batch"] = bool(emitted) and verdict_uses >= 4
    notes.append(f'verdict-counts-batch: sum present={bool(emitted)} '
                 f'`emitted` reads={verdict_uses} (>=4 expected)')

    # ── memory-gate ────────────────────────────────────────────────────────
    # The batch runner's own documented peak is ~3.9 GB and the streaming model
    # stays resident, so a pass that cannot fit must be DEFERRED (its audio stays
    # buffered) rather than attempted. Two halves, checked separately because they
    # are different promises: the floor is MEASURED, the INTERVAL path respects it,
    # the TAIL path (no next tick) does not, and the count is published so a
    # deferral is visible in `done` instead of inferred.
    sig = re.search(r'def flush_pending\(self, reason="flush",\s*\n?\s*'
                    r'respect_memory_floor=(True|False)\)', src)
    measures = "free = _free_memory_mb()" in src
    interval_respects = re.search(
        r'return self\.flush_pending\(reason, respect_memory_floor=True\)', src)
    deferred_log = "REDUX_BATCH_DEFERRED reason=low-memory" in src
    tail_attempts = "attempting=anyway" in src
    published = "reduxBatchDeferred=switch.deferred" in src
    claims["memory-gate"] = (
        bool(sig) and sig.group(1) == "False" and measures
        and bool(interval_respects) and deferred_log and tail_attempts and published)
    notes.append(
        f'memory-gate: floor measured={measures} '
        f'interval respects it={bool(interval_respects)} '
        f'tail attempts anyway={tail_attempts} '
        f'deferral is loud={deferred_log} published={published} '
        f'flush default(tail)={sig.group(1) if sig else "?"}')
    return claims, notes


def check_shell(src: str):
    claims: dict[str, bool] = {}
    notes: list[str] = []

    # ── shell-loop ─────────────────────────────────────────────────────────
    # The cadence is the half that records a visibility change NOBODY announced:
    # pywebview's own navigation-time `Show`, `_reassert_hidden`, a hot reload.
    cadence = re.search(r'while not self\._stop\.wait\(self\.interval_s\):\s*\n'
                        r'(?:\s*#[^\n]*\n)*\s*self\.write\(', src)
    thread = re.search(r'name=[\'"]sotto-panel-visibility[\'"]', src)
    claims["shell-loop"] = bool(cadence) and bool(thread)
    notes.append(f'shell-loop: cadence thread={bool(thread)} '
                 f'tick-writes={bool(cadence)}')

    # ── shell-transitions ─────────────────────────────────────────────────
    path = re.search(r"PANEL_VISIBILITY_PATH\s*=\s*os\.path\.join\(\s*\n?\s*"
                     r"REPO_ROOT,\s*'_main',\s*'panel-visibility\.json'\)", src)
    logline = re.search(r"f'PANEL_VISIBILITY_MODE '\s*\n\s*f'visible=", src)
    armed = ("self.start_panel_visibility()" in src)
    shows = len(re.findall(r'self\.publish_panel_visibility\(reason\)', src))
    reassert = "self.publish_panel_visibility('reassert-hidden')" in src
    claims["shell-transitions"] = (bool(path) and bool(logline) and armed
                                   and shows >= 2 and reassert)
    notes.append(f'shell-transitions: path=_main/panel-visibility.json={bool(path)} '
                 f'PANEL_VISIBILITY_MODE line={bool(logline)} '
                 f'start_panel_visibility() called={armed} '
                 f'show/hide publish sites={shows} reassert={reassert}')

    # ── shell-measured ────────────────────────────────────────────────────
    # `visible` must be the WINDOW, read at write time — never an intention.
    measured = re.search(r'def observe_panel_visible\(self\) -> bool:\s*\n'
                         r'(?:\s*""".*?"""\s*\n)?\s*hwnd = self\.hwnd\s*\n'
                         r'\s*return bool\(window_visible\(hwnd\)\) if hwnd else False',
                         src, re.S)
    claims["shell-measured"] = bool(measured)
    notes.append(f'shell-measured: observe uses window_visible(hwnd)={bool(measured)}')
    return claims, notes


# ---------------------------------------------------------------------------
# the mutants — one per claim, each reverting EXACTLY that claim
# ---------------------------------------------------------------------------

MUTANTS = [
    ("flag-exists", "worker",
     'REDUX_WHEN_HIDDEN_DEFAULT = False', 'REDUX_WHEN_HIDDEN_DEFAULT = True'),
    ("flag-guarded", "worker",
     'if redux_optin:\n        switch = ReduxHiddenSwitch(',
     'if True:\n        switch = ReduxHiddenSwitch('),
    ("env-optin", "worker",
     'str(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN") or "").strip() == "1")',
     'str(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN") or "").strip() == "0")'),
    ("memory-gate", "worker",
     'return self.flush_pending(reason, respect_memory_floor=True)',
     'return self.flush_pending(reason, respect_memory_floor=False)'),
    ("switch-wired", "worker",
     'switch.add_audio(block)\n                    switch.maybe_kick()\n'
     '                    continue',
     'switch.add_audio(block)\n                    switch.maybe_kick()\n'
     '                    pass'),
    ("stamp", "worker",
     'REDUX_PRODUCER = "redux"', 'REDUX_PRODUCER = "live"'),
    ("hard-rule", "worker",
     'self.armed = bool(self.enabled and self.runner_available)',
     'self.armed = True'),
    ("fail-safe", "worker",
     'def _fallback(self, why, age):\n        self.fallbacks += 1\n'
     '        self.last_reason = why\n        return True, why, age',
     'def _fallback(self, why, age):\n        self.fallbacks += 1\n'
     '        self.last_reason = why\n        return False, why, age'),
    ("payload-guarded", "worker",
     'if switch is not None:\n        done_payload.update(',
     'if True:\n        done_payload.update('),
    ("verdict-counts-batch", "worker",
     'emitted = counters.get("captions", 0) + counters.get("redux_captions", 0)',
     'emitted = counters.get("captions", 0)'),
    ("shell-loop", "shell",
     'while not self._stop.wait(self.interval_s):',
     'while False:'),
    ("shell-measured", "shell",
     'return bool(window_visible(hwnd)) if hwnd else False',
     'return False'),
]


def write_mutant(name: str, src: str, old: str, new: str, ext: str):
    if old not in src:
        return None, f"anchor NOT FOUND for mutant {name!r}"
    if src.count(old) != 1:
        return None, (f"anchor is not unique for mutant {name!r} "
                      f"({src.count(old)} occurrences)")
    path = os.path.join(MUTANT_DIR, f"{name}{ext}")
    os.makedirs(MUTANT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src.replace(old, new))
    return path, None


def evaluate(worker_path, shell_path, label):
    """-> (all_ok, failing_claims, notes)"""
    try:
        with open(worker_path, encoding="utf-8") as fh:
            wsrc = fh.read()
        with open(shell_path, encoding="utf-8") as fh:
            ssrc = fh.read()
    except OSError as exc:
        say(f"SETUP ERROR: cannot read {worker_path}/{shell_path}: {exc!r}")
        raise
    wclaims, wnotes = check_worker(wsrc)
    sclaims, snotes = check_shell(ssrc)
    claims = {**wclaims, **sclaims}
    notes = wnotes + snotes
    bad = sorted(k for k, v in claims.items() if not v)
    say(f"[{label}] claims: " + " ".join(
        f"{k}={'OK' if v else 'RED'}" for k, v in sorted(claims.items())))
    for note in notes:
        say(f"[{label}]   {note}")
    return (not bad), bad, claims


def main() -> int:
    ap = argparse.ArgumentParser(prog="redux-flag-gate")
    ap.add_argument("--worker", default=WORKER_DEFAULT)
    ap.add_argument("--shell", default=SHELL_DEFAULT)
    ap.add_argument("--neg-arm", action="store_true",
                    help="also build one mutated COPY per claim and require each "
                         "to go RED on its OWN claim and only that one")
    args = ap.parse_args()

    for path in (args.worker, args.shell):
        if not os.path.exists(path):
            say(f"SETUP ERROR: no such file: {path}")
            return 2

    say("=== REDUX FLAG GATE — is the switch OFF by default and WIRED? ===")
    ok, bad, shipped_claims = evaluate(args.worker, args.shell, "shipped")
    say(f"[shipped] VERDICT {'GREEN' if ok else 'RED'} "
        f"({len(shipped_claims) - len(bad)}/{len(shipped_claims)} claims hold)"
        + (f" — failing: {', '.join(bad)}" if bad else ""))
    if not ok:
        say("GATE-VERDICT: RED (as shipped) — the claims above are the wiring "
            "promises this lane makes; the shipped pair must hold ALL of them.")
        return 1

    if not args.neg_arm:
        say("")
        say(f"GATE-VERDICT: GREEN — all {len(shipped_claims)} claims hold as shipped. "
            f"Run with --neg-arm to prove each one can go RED.")
        return 0

    # ── the control: one mutant per claim ──────────────────────────────────
    say("")
    say("=== NEGATIVE ARM — one mutated COPY per claim ===")
    with open(args.worker, encoding="utf-8") as fh:
        wsrc = fh.read()
    with open(args.shell, encoding="utf-8") as fh:
        ssrc = fh.read()
    if os.path.isdir(MUTANT_DIR):
        shutil.rmtree(MUTANT_DIR)
    os.makedirs(MUTANT_DIR, exist_ok=True)

    moved: list[str] = []
    stayed: list[str] = []
    overmoved: list[str] = []
    setup: list[str] = []
    for name, target, old, new in MUTANTS:
        src = wsrc if target == "worker" else ssrc
        path, err = write_mutant(name, src, old, new, ".py")
        if err:
            setup.append(err)
            say(f"[mutant {name}] SETUP ERROR: {err}")
            continue
        # The mutant replaces ONLY its own file; the other half stays the
        # shipped one, so a RED on the claim it reverts cannot be blamed on a
        # second edit.
        mworker = path if target == "worker" else args.worker
        mshell = path if target == "shell" else args.shell
        mok, mbad, _ = evaluate(mworker, mshell, f"mutant {name}")
        if not mbad:
            stayed.append(name)
            say(f"[mutant {name}] DID NOT MOVE — the claim it reverts stayed green, "
                f"so that claim is not load-bearing")
        elif mbad != [name]:
            overmoved.append(name)
            say(f"[mutant {name}] moved MORE than its own claim: {mbad} — a mutant "
                f"that moves a second claim is not a control for the first")
        else:
            moved.append(name)
            say(f"[mutant {name}] RED on exactly {mbad!r} — RED-as-expected")

    say("")
    say(f"mutants built: {len(moved) + len(stayed) + len(overmoved)}/{len(MUTANTS)} "
        f"(each a COPY in {os.path.relpath(MUTANT_DIR, ROOT)})")
    if setup:
        for s in setup:
            say(f"  SETUP: {s}")
        say("GATE-VERDICT: RED — a mutant could not be built, so that claim is "
            "not controlled")
        return 1
    if stayed:
        for name in stayed:
            say(f"  NOT LOAD-BEARING: {name}")
        say("GATE-VERDICT: RED — claim(s) above did not go RED on their own mutant")
        return 1
    if overmoved:
        for name in overmoved:
            say(f"  NOT A CONTROL: {name}")
        say("GATE-VERDICT: RED — mutant(s) above moved a claim other than their own")
        return 1
    say(f"NEG-VERDICT: GREEN — all {len(moved)} mutants moved exactly their own "
        f"claim: {', '.join(moved)}")
    say("")
    say("GATE-VERDICT: GREEN — shipped pair holds every claim AND every claim is "
        "load-bearing (each of its mutants goes RED on that claim alone).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
