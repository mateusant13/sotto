"""ARM oracle for F1 -- "the worker starts by DEFAULT" -- without a WebView2.

The audit (`docs/audit/auditoria-completa-20261007.md`, F1) measured that the
documented launch started NO worker: `run.cmd` passed no flag and `start_worker`
lived under `if self.args.with_worker:`. 32 shell starts in the owner's own
`_main/webview-run.log`, 10 with a worker, every one of them
`reason=with-worker`. The cure is a default plus a suppression rule, and a
default is exactly the kind of change that is asserted by prose and never
measured -- so this gate calls the REAL decision function, in the REAL shell
module, through the REAL argument parser.

`_worker_autostart_reason(args)` is the whole rule; `_on_loaded` passes the
result to `start_worker`, which prints
`WORKER_AUTOSTART=started|declined reason=<that string>`. So one assertion per
arm ("this flag list starts it / does not") covers the log line, because the log
line is that string.

Run: `python _main/_lane1-worker-default-arms.py`  -> exit 0 GREEN, 3 RED.
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def load_shell():
    """Import the shell by path, without starting anything.

    `sotto_webview.py` builds no window and no worker at import time, and its
    module level is where the parser and the constants live. sys.path gets the
    shell's own directory because it imports its siblings (`hot_reload`,
    `panel_state`).
    """
    sys.path.insert(0, os.path.dirname(SHELL))
    spec = importlib.util.spec_from_file_location('sotto_webview_under_test',
                                                  SHELL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: (label, argv, env, expected-reason, does-it-start)
ARMS = [
    # -- F1 itself: the documented double-click passes NOTHING. ---------------
    ('plain double-click (run.cmd, no flags)',
     [], {}, 'default', True),
    ('explains itself: --show only',
     ['--show'], {}, 'default', True),
    # -- the opt-outs -------------------------------------------------------
    ('--no-worker',
     ['--no-worker'], {}, 'no-worker', False),
    ('SOTTO_NO_WORKER=1',
     [], {'SOTTO_NO_WORKER': '1'}, 'env', False),
    # -- the measurement modes: the shell/panel, not transcription -----------
    ('--dump-dom', ['--dump-dom'], {}, 'measurement-flag(--dump-dom)', False),
    ('--selftest', ['--selftest'], {}, 'measurement-flag(--selftest)', False),
    ('--memory', ['--memory'], {}, 'measurement-flag(--memory)', False),
    ('--no-hotkey', ['--no-hotkey'], {}, 'measurement-flag(--no-hotkey)', False),
    ('--exit-after 8', ['--exit-after', '8'], {},
     'measurement-flag(--exit-after)', False),
    # A REAL probe argv, verbatim from the oracles: --exit-after must not be the
    # reason a lane that wanted the worker loses it.
    ('--no-hotkey --no-hot-reload --exit-after 30 (a probe argv)',
     ['--no-hotkey', '--no-hot-reload', '--exit-after', '30'], {},
     'measurement-flag(--no-hotkey)', False),
    # -- --with-worker is AUTHORITATIVE, in the exact argv the lanes pass -----
    ('--show --with-worker (app/webview/README.md)',
     ['--show', '--with-worker'], {}, 'with-worker', True),
    ('--with-worker + a measurement flag',
     ['--with-worker', '--dump-dom'], {}, 'with-worker', True),
    ('_main/_app-drive.py: --with-worker --probe-v2 6',
     ['--with-worker', '--probe-v2', '6'], {}, 'with-worker', True),
    ('--with-worker + --no-worker (the flag that forces wins)',
     ['--with-worker', '--no-worker'], {}, 'with-worker', True),
    ('run-cmd-exit-oracle arm: --log --no-hotkey --no-hot-reload --exit-after 6',
     ['--log', 'x.log', '--no-hotkey', '--no-hot-reload', '--exit-after', '6'],
     {}, 'measurement-flag(--no-hotkey)', False),
]


#: The reasons that START the worker. This is the mapping the arms assert
#: against, spelled out rather than inferred from one string: `with-worker` is a
#: FORCE and `default` is the absence of any instruction, and both start it.
STARTS = ('default', 'with-worker')


def main():
    shell = load_shell()
    failures = []
    for label, argv, env, expected, starts in ARMS:
        try:
            args = shell.parse_args(argv)
        except SystemExit as exc:
            failures.append(f'{label}: argparse REFUSED this list (rc={exc.code})')
            print(f'RED  {label}\n     argparse refused: rc={exc.code}')
            continue
        # A COPY of the environment, so this process' own env cannot decide an
        # arm: `env` alone is what the shell would read for `SOTTO_NO_WORKER`.
        got = shell.SottoShell._worker_autostart_reason(args, env=dict(env))
        ok = (got == expected) and ((got in STARTS) == starts)
        print(f'{"GREEN" if ok else "RED "} {label}\n'
              f'      reason={got}  starts_worker={got in STARTS}')
        if not ok:
            failures.append(
                f'{label}: got {got!r} (starts={got in STARTS}), '
                f'expected {expected!r} (starts={starts})')

    # The DEFAULT has to be reachable from the entry the owner actually runs,
    # so the claim is about the parser of the shell `run.cmd` calls, not about a
    # hand-built namespace.
    parser_ok = hasattr(shell, 'parse_args') and hasattr(
        shell.SottoShell, '_worker_autostart_reason')
    print(f'{"GREEN" if parser_ok else "RED "} the shell exposes both the '
          'parser and the rule (no hand-built namespace)')
    if not parser_ok:
        failures.append('the shell does not expose parse_args + the rule')

    # D3: the painted sentence must NAME THE FLAG, and no arm whose reason has a
    # worker may paint anything. A measurement-flag reason DOES paint: the parent
    # lane's refined requirement is that the status name the flag that suppressed
    # the worker, so the owner can undo it in one argument.
    print('\nD3 -- the honest sentence, per reason:')
    for reason, must_paint in (('no-worker', True), ('env', True),
                               ('measurement-flag(--dump-dom)', True),
                               ('measurement-flag(--exit-after)', True),
                               ('with-worker', False), ('default', False)):
        got = shell.SottoShell._worker_off_message(reason)
        paints = got is not None
        flag = (reason[len('measurement-flag('):-1] if reason.startswith(
            'measurement-flag(') else {'no-worker': '--no-worker',
                                       'env': 'SOTTO_NO_WORKER=1'}.get(reason))
        named = (not paints) or (flag is None) or (
            flag in got[0] and flag in got[1]['body'])
        ok = (paints == must_paint) and named
        print(f'{"GREEN" if ok else "RED "} reason={reason} paints={paints}'
              + (f' text={got[0]!r}' if got else ''))
        if not ok:
            failures.append(
                f'D3 {reason}: paints={paints} (expected {must_paint}), '
                f'names_the_flag={named}')

    if failures:
        print('\nRESULT: RED -- ' + str(len(failures)) + ' arm(s)')
        for line in failures:
            print('  ' + line)
        return 3
    print(f'\nRESULT: GREEN -- all {len(ARMS)} arm(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
