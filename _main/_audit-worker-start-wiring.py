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
import subprocess
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

    # ── 4. A RECUSA MUDA: `bridge` ja' armado nao pode passar em silencio ────
    #       nem ser reportada como `started` (medido 2026-11-05: o log do dono
    #       teve `WORKER_AUTOSTART=started reason=default` DUAS vezes no mesmo
    #       arranque, a segunda sem arrancar nada).
    bridge_refusal = re.search(
        r'if self\.bridge is not None:\s*\n\s*(?:#[^\n]*\n\s*)*'
        r'log\(f?[\'"]WORKER_AUTOSTART=declined reason=\{reason\}', text)
    say(f'the already-running refusal SPEAKS: {bool(bridge_refusal)}')
    if not bridge_refusal:
        say('FAIL: a `bridge` that already exists returns False with no log — the'
            ' reader cannot tell an already-running worker from a silent failure')
        failures.append('silent-already-running')
    if 'cause=already-running' not in text:
        say('FAIL: the already-running refusal does not name its cause')
        failures.append('already-running-cause')
    false_started = "WORKER_AUTOSTART=started reason=default by=startup-show" in src
    say(f'the false `started ... by=startup-show` line is GONE: {not false_started}')
    if false_started:
        say('FAIL: a branch that starts nothing logs `started` — two workers in'
            ' one boot as far as the log is concerned')
        failures.append('false-started')
    routed = re.search(r'if getattr\(self, \'bridge\', None\) is not None:\s*\n'
                       r'\s*(?:#[^\n]*\n\s*)*self\.start_worker\(worker_reason\)', src)
    say(f'the startup-show branch routes through start_worker: {bool(routed)}')
    if not routed:
        say('FAIL: the startup-show branch does not use the ONE refusal path')
        failures.append('startup-show-route')

    say('')
    if failures:
        say('WIRING-VERDICT: RED — ' + ', '.join(failures))
        return 1
    say('WIRING-VERDICT: GREEN — the reason the rule returns is the reason that'
        ' decides, and a decline both refuses and says so')
    return 0


MUTANTS = (
    # (rotulo, ancora, substituicao) -- cada um tem de derrubar o portao.
    ('sem a recusa muda',
     "            log(f'WORKER_AUTOSTART=declined reason={reason} '\n"
     "                'by=start_worker cause=already-running')\n",
     "            pass\n"),
    ('a linha falsa de volta',
     "                    self.start_worker(worker_reason)\n",
     "                    log('WORKER_AUTOSTART=started reason=default by=startup-show')\n"),
    ('sem o motivo da recusa',
     "'by=start_worker cause=already-running')",
     "'by=start_worker')"),
    ('a guarda do reason depois do spawn',
     "if reason not in self.START_REASONS:",
     "if False:"),
)


def neg_arm() -> int:
    """Quatro mutacoes numa COPIA; cada uma tem de fazer o portao dar rc=1.

    O portao e' uma assercao de TEXTO, e o repo ja' pagou duas vezes por isso
    (mutacoes ancoradas em texto que a cura substituiu, a verde por nao se
    aplicarem). Um mutante que nao se aplica e' `IMPOSSIVEL`, nunca `PASS`.
    """
    import tempfile

    src = open(SHELL, encoding='utf-8').read()
    caught = 0
    for label, anchor, repl in MUTANTS:
        if anchor not in src:
            print(f'NEG-ARM: IMPOSSIVEL mutar {label} (a ancora mudou)')
            continue
        tmp = tempfile.mkdtemp(prefix='wsw-neg-')
        path = os.path.join(tmp, 'sotto_webview.py')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(anchor, repl, 1))
        rc = subprocess.run([sys.executable, os.path.abspath(__file__), '--shell', path],
                            capture_output=True, text=True).returncode
        hit = rc == 1
        caught += 1 if hit else 0
        print(f"[{'CAUGHT' if hit else 'NOT-CAUGHT'}] mutante: {label} (rc={rc})")
    total = len(MUTANTS)
    print(f"NEG-ARM: {'PASS' if caught == total else 'FAIL'} -- "
          f"{caught}/{total} mutante(s) recusado(s)")
    return 1 if caught == total else 0


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv else main())
