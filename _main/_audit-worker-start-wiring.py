#!/usr/bin/env python3
"""Does the F1 RULE actually reach the machine? (the wiring, not the rule)

WHY THIS EXISTS — measured 2026-10-07. `SottoShell._worker_autostart_reason` is a
clean, factored, well-documented rule with FIVE reasons; lane 1's probe asserts all
15 of its arms and the adversary lane swept 22 more. Both passed. And both were
blind, because `start_worker(reason)` did not look at `reason` at all: the value
was computed and DISCARDED, so every launch — `--dump-dom` included — spawned a
~2 GB worker while the D3 path told the panel that no worker was running.

That is the defect class this whole round is about: an instrument that tests the
MODEL and certifies the MACHINE. So this gate asks the wiring question in both
directions, and it is deliberately a SOURCE assertion rather than an execution:
running the real `start_worker('default')` would spawn the worker and open an audio
device, which no gate in this repo may do.

    python _main/_audit-worker-start-wiring.py

Exit 0 when the rule is binding, 1 when a decline reason would still spawn, 2 on a
setup error.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
# `--shell <path>` exists so the NEGATIVE CONTROL can run against a mutated COPY
# instead of the live file: a gate whose control requires editing the shipped
# source is a gate nobody runs. Same reason the repo's other gates take variants.
if '--shell' in sys.argv:
    SHELL = sys.argv[sys.argv.index('--shell') + 1]
LOG = os.path.join(HERE, '_audit-verify', 'worker-start-wiring.log')

failures: list[str] = []
lines: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(msg, flush=True)


def main() -> int:
    try:
        with open(SHELL, encoding='utf-8') as fh:
            src = fh.read()
    except OSError as exc:
        say(f'SETUP ERROR: cannot read {SHELL}: {exc!r}')
        return 2

    # ── 1. the allow-list exists and is a literal tuple ─────────────────────
    allow = re.search(r'START_REASONS\s*=\s*\(([^)]*)\)', src)
    if not allow:
        say('FAIL: no `START_REASONS` tuple in the shell — the decline reasons have'
            ' nothing to be tested against')
        failures.append('allow-list')
        reasons: list[str] = []
    else:
        reasons = re.findall(r"'([^']+)'", allow.group(1))
        say(f'allow-list (may SPAWN): {reasons}')
        for must in ('default', 'with-worker', 'hot-reload'):
            if must not in reasons:
                say(f'FAIL: {must!r} is not allowed to spawn — the app could never'
                    f' start a worker for that reason')
                failures.append(f'allow-list:{must}')

    # ── 2. `start_worker` actually consults it, BEFORE anything else ─────────
    body = re.search(r'\n    def start_worker\(self, reason\):\n(.*?)\n    def ',
                     src, re.S)
    if not body:
        say('SETUP ERROR: `def start_worker(self, reason):` not found (renamed?)')
        return 2
    text = body.group(1)
    guard = re.search(r'if reason not in self\.START_REASONS:', text)
    say(f'`start_worker` consults START_REASONS: {bool(guard)}')
    if not guard:
        say('FAIL: start_worker would spawn for EVERY reason string — the rule is'
            ' computed and discarded (the exact 2026-10-07 defect)')
        failures.append('guard')
    else:
        # the guard must come before the bridge/spawn work, or a decline could
        # still reach `WorkerBridge(...)`/`.start()` on some path
        spawn_at = text.find('WorkerBridge(')
        guard_at = guard.start()
        ordered = 0 <= guard_at < spawn_at
        say(f'the guard precedes the spawn ({spawn_at if spawn_at >= 0 else "n/a"}'
            f'): {ordered}')
        if not ordered:
            say('FAIL: the reason test comes AFTER the spawn — a decline would still'
                ' construct and start a bridge')
            failures.append('order')
        declined_log = 'WORKER_AUTOSTART=declined' in text
        say(f'the decline is LOGGED in the same shape as a start: {declined_log}')
        if not declined_log:
            say('FAIL: a declined start would be silent — the log is the only'
                ' receipt a measurement run leaves')
            failures.append('decline-log')

    # ── 3. the call site passes the RULE's value, not a literal ─────────────
    call = re.search(r'self\.start_worker\((\w+)\)', src)
    if not call:
        say('SETUP ERROR: no `self.start_worker(<arg>)` call site found')
        return 2
    arg = call.group(1)
    say(f'call site passes: {arg}')
    if arg == 'worker_reason':
        rule = re.search(r'(\w+)\s*=\s*self\._worker_autostart_reason\(', src)
        say(f'the argument IS the rule\'s output ({rule.group(1) if rule else "?"})')
    elif not re.match(r"'", arg):
        say(f'note: the only call site passes {arg!r}; expected `worker_reason`')
        failures.append('call-site')
    hot = re.search(r"self\.start_worker\('hot-reload'\)", src)
    say(f'the hot-reload restart has its own call site: {bool(hot)}')
    if not hot:
        say('note: no `start_worker(\'hot-reload\')` — if the reload path was'
            ' renamed, re-check that it is in the allow-list')

    say('')
    if failures:
        say('WIRING-VERDICT: RED — ' + ', '.join(failures))
        return 1
    say('WIRING-VERDICT: GREEN — the reason the rule returns is the reason that'
        ' decides, and a decline both refuses and says so')
    return 0


if __name__ == '__main__':
    sys.exit(main())
