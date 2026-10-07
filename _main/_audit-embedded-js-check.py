#!/usr/bin/env python3
"""Extract every JavaScript blob embedded in the shell and hand it to `node --check`.

WHY THIS EXISTS: `python -m py_compile` proves the PYTHON parses, and says nothing
about the JavaScript inside the probe strings. An edit that breaks a probe's JS —
a missing brace, a renamed field read by a later arm — compiles clean and fails
only when a WebView2 exists to run it, which this session cannot produce. So the
strings are written out as files and parsed by node.

It also prints the field set of each probe, so an arm that reads a field no other
arm provides is visible as text instead of as a probe timeout.

    python _main/_audit-embedded-js-check.py [--out DIR]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL_DIR = os.path.join(ROOT, 'app', 'webview')
OUT = os.path.join(HERE, '_audit-verify', 'js')

PROBES = ('PANEL_V2_INJECT', 'PANEL_V2_READ_LIVE', 'PANEL_V2_READ_SEARCH',
          'PANEL_STATE_PROBE', 'DUMP_DOM_PROBE', 'BRIDGE_PROBE', 'BOOTSTRAP_JS')


def main() -> int:
    out_dir = OUT
    if '--out' in sys.argv:
        out_dir = sys.argv[sys.argv.index('--out') + 1]
    os.makedirs(out_dir, exist_ok=True)
    sys.path.insert(0, SHELL_DIR)

    import sotto_webview as shell  # noqa: PLC0415 -- by path, like the shell itself

    failures = []
    for name in PROBES:
        blob = getattr(shell, name, None)
        if blob is None:
            print(f'MISSING {name} (not defined in the shell)')
            failures.append(name)
            continue
        path = os.path.join(out_dir, name + '.js')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(blob)
        # `node --check` writes its complaint to stderr. It is REDIRECTED TO A
        # FILE, never captured through a pipe: this sandbox denies CreatePipe
        # (`PermissionError: [WinError 5]` on `subprocess.run(capture_output=True)`),
        # which is the same boundary that makes `run.cmd`'s `for /f` unusable here.
        err_path = path + '.err'
        with open(err_path, 'wb') as err_file:
            res = subprocess.run(['node', '--check', path],
                                 stdout=subprocess.DEVNULL, stderr=err_file)
        status = 'syntax OK' if res.returncode == 0 else 'SYNTAX ERROR'
        if res.returncode != 0:
            failures.append(name)
        # The fields the blob RETURNS, as text: enough to notice an arm reading a
        # field nobody provides (the F6 defect class, in probe form).
        fields = sorted(set(re.findall(r'^\s{4,6}([A-Za-z_][A-Za-z0-9_]*)\s*[:(]',
                                       blob, re.M)))
        print(f'{name:22s} {len(blob):6d} B  {status}')
        print(f'{"":22s} fields: {", ".join(fields) if fields else "(none found)"}')
        if res.returncode != 0:
            with open(err_path, encoding='utf-8', errors='replace') as fh:
                print(f'{"":22s} ' + ' | '.join(fh.read().splitlines()[:3]))

    print('')
    if failures:
        print('JS-CHECK: RED -- ' + ', '.join(failures))
        return 1
    print(f'JS-CHECK: GREEN -- {len(PROBES)} embedded blob(s) parse under node, '
          f'written to {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
