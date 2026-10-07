#!/usr/bin/env python3
"""THE DELIVERY GATE — does a caption actually LAND in the panel's DOM?

THE P0. `sotto_webview.py` logs `BRIDGE_CAPTION_SENT delivered=true`
(`sotto_webview.py:5810`) the moment it hands a caption to `exec_js`. That line
is NOT proof of delivery: `evaluate_js` reports the CALL, not the page's own
execution, and the same file records the incident that made this lane necessary
-- on 2026-10-07 the shell logged thousands of `delivered=true` lines while the
panel sat on "Starting the worker" with `#caption-list` still `display:none`
(`sotto_webview.py:2385-2393`).

A page-side COUNTER IS ALSO NOT PROOF, and this gate deliberately does not
settle for one: `window.__sotto_emit.counts[kind]` is incremented at
`sotto_webview.py:2219`, one line BEFORE the subscriber dispatch at `:2220`. A
panel whose scripts threw at init -- the case that kills every subscription --
would still increment that counter.

SO THE MEASUREMENT IS THE DOM. `PANEL_STATE_PROBE` (`sotto_webview.py:2597`)
reads `#caption-list` back out of the page. A caption in THAT list was ingested
by `panel.js:668`'s `bridge.onCaption` handler, formatted by `engine.ingest`,
and committed by `addCaption` (`panel.js:684-689`) -- which is what un-hides the
list. There is no shorter route from a worker's stdout line to that list.

ARMS
  real     REAL ASR. `_cap2panel-realworker.py` runs the REAL worker over
           `worker/assets/sample1.flac` (13.44 s, Dickens). A caption in the
           DOM here is a real model's real output on a real panel.
  silent   THE ARM THAT MUST GO RED. Same shell, same panel, same JSONL
           channel, same wait; the worker prints a `status` and never emits a
           caption. If this arm shows a caption too, the gate is measuring
           nothing and reports RED.

    python _main/_cap2panel-probe.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
#: The REAL product -- shell, panel and worker all come from `H:\sotto`. This
#: worktree carries the HARNESS only; it has no weights and is not the subject.
PRODUCT = r'H:\sotto'
SHELL = os.path.join(PRODUCT, 'app', 'webview', 'sotto_webview.py')
PANEL_STATE = os.path.join(PRODUCT, '_main', 'panel-state.json')
REQUEST = PANEL_STATE + '.request'
REPORT = os.path.join(HERE, '_cap2panel-probe.json')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
STAMP = f'{os.getpid()}-{int(time.time())}'
CREATE_NO_WINDOW = 0x08000000

#: How long each arm is given. The real worker loads ~2.4 GB of weights and
#: transcribed 13.44 s of audio in 15.8 s on this box (measured, 1 run), so the
#: caption is expected well inside this window; the negative arm gets the SAME
#: window, which is the point -- an arm that is merely longer cannot be the
#: reason the real arm passed.
WINDOW_S = float(os.environ.get('CAP2PANEL_WINDOW_S', '70'))


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError as exc:
        # LOUD: an unreadable log would silently turn every log-based check
        # into a vacuous pass, so the reason travels into the report.
        return f'__READ_LOG_FAILED__ {path}: {exc!r}'


def read_json(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        # LOUD, same reason: a dump this gate cannot read is NOT "no captions".
        return {'__READ_DUMP_FAILED__': f'{path}: {exc!r}'}


def dump_lines(text, needle):
    return [ln.strip() for ln in text.splitlines() if needle in ln]


def run_arm(tag, worker, window_s):
    """Launch the panel on `worker`, wait, then ask the panel to dump its DOM."""
    log_path = os.path.join(HERE, f'_cap2panel-{tag}-{STAMP}.log')
    # A stale dump from an earlier launch would be read as this arm's result.
    # Recorded rather than swallowed: if the removal fails, this arm's reading
    # may not be its own, and the report has to say so.
    stale_remove_errors = []
    for path in (PANEL_STATE, REQUEST):
        if not os.path.exists(path):
            continue  # nothing to remove: the normal case, not a failure
        try:
            os.remove(path)
        except OSError as exc:
            stale_remove_errors.append(f'{os.path.basename(path)}: {exc!r}')

    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--log', log_path, '--with-worker', '--worker', worker,
           '--exit-after', str(int(window_s) + 15)]
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Give the caption time to land and the panel time to commit the line.
    deadline = started + window_s
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.5)

    # ON-DEMAND DUMP: drop the sentinel and wait for a FRESH write, so the
    # reading is of THIS arm's DOM rather than of a boot-time snapshot.
    snapshot, waited, request_error = None, 0.0, None
    try:
        with open(REQUEST, 'w', encoding='utf-8') as fh:
            fh.write('probe')
        wait_until = time.time() + 15.0
        while time.time() < wait_until:
            waited = round(time.time() - started, 2)
            snapshot = read_json(PANEL_STATE)
            if isinstance(snapshot, dict) and (snapshot.get('live') or {}).get('lines'):
                break
            time.sleep(0.5)
    except OSError as exc:
        # LOUD and consequential: without the sentinel there is no fresh DOM
        # read at all, so this arm has NO measurement and must not pass.
        request_error = repr(exc)

    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    text = read_log(log_path)
    live = (snapshot or {}).get('live') or {}
    return {
        'tag': tag,
        'worker': worker,
        'rc': proc.returncode,
        'wall_s': round(time.time() - started, 2),
        'snapshot_age_s': waited,
        'stale_remove_errors': stale_remove_errors,
        'request_error': request_error,
        'dump_read_error': snapshot.get('__READ_DUMP_FAILED__')
        if isinstance(snapshot, dict) else None,
        'dom_lines': live.get('lines'),
        'dom_count': live.get('count'),
        'caption_list_hidden': live.get('listHidden'),
        'placeholder_hidden': live.get('placeholderHidden'),
        'shell_sent': dump_lines(text, 'BRIDGE_CAPTION_SENT'),
        'sent_count': len(dump_lines(text, 'BRIDGE_CAPTION_SENT')),
        'autostart': dump_lines(text, 'WORKER_AUTOSTART'),
        'page_errors': dump_lines(text, 'PAGE_ERROR'),
        'log': log_path,
    }


def texts(arm):
    out = []
    for row in (arm.get('dom_lines') or []):
        out.append(row.get('text') if isinstance(row, dict) else str(row))
    return [t for t in out if t]


def main():
    real = run_arm('real', os.path.join(HERE, '_cap2panel-realworker.py'), WINDOW_S)
    silent = run_arm('silent', os.path.join(HERE, '_cap2panel-silentworker.py'),
                     WINDOW_S)

    real_texts = texts(real)
    silent_texts = texts(silent)
    # The real worker transcribes sample1.flac; the words below are IN that
    # recording's transcript, so finding one is a match against real ASR output
    # and not against a string this harness wrote.
    DICKEYNS = ('country roads', 'damp audiences', 'drafty schoolrooms',
                'fortnight', 'worship')

    def instrumented(arm):
        return (not arm['stale_remove_errors'] and arm['request_error'] is None
                and arm['dump_read_error'] is None)

    checks = [
        ('real: the instrument itself was sound (no stale/dump/request failure)',
         instrumented(real)),
        ('real: the shell started the REAL worker (reason=with-worker)',
         any('reason=with-worker' in ln for ln in real['autostart'])),
        ('real: the shell reached on_worker_caption (BRIDGE_CAPTION_SENT)',
         real['sent_count'] >= 1),
        ('real: a caption line is in the panel DOM (#caption-list)',
         len(real_texts) >= 1),
        ('real: the DOM text is real ASR output from sample1.flac',
         any(any(w in t.lower() for w in DICKEYNS) for t in real_texts)),
        ('real: the caption list is NOT hidden any more (addCaption un-hid it)',
         real.get('caption_list_hidden') is False),
        ('real: no page error', not real['page_errors']),
        # ── THE ARM THAT MUST GO RED ──────────────────────────────────────
        ('silent: the instrument itself was sound',
         instrumented(silent)),
        ('silent: the shell started the negative worker too',
         any('reason=with-worker' in ln for ln in silent['autostart'])),
        ('silent: no caption reached the DOM (the check CAN say no)',
         len(silent_texts) == 0),
        ('silent: no BRIDGE_CAPTION_SENT either',
         silent['sent_count'] == 0),
        ('silent: the caption list is still hidden',
         silent.get('caption_list_hidden') is not False),
    ]

    report = {
        'stamp': STAMP,
        'window_s': WINDOW_S,
        'population': ('caption lines observed in ONE panel launch per arm, '
                       'window = %.0f s after launch' % WINDOW_S),
        'real': real, 'silent': silent,
        'checks': [{'what': w, 'ok': bool(o)} for w, o in checks],
    }
    report['failed'] = [w for w, o in checks if not o]
    report['verdict'] = 'GREEN' if not report['failed'] else 'RED'

    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print('verdict=%s' % report['verdict'])
    print('real   : rc=%s sent=%s dom_count=%s wall=%ss'
          % (real['rc'], real['sent_count'], real['dom_count'], real['wall_s']))
    print('  dom  : %r' % (real_texts[:3],))
    print('silent : rc=%s sent=%s dom_count=%s wall=%ss'
          % (silent['rc'], silent['sent_count'], silent['dom_count'],
             silent['wall_s']))
    print('  dom  : %r' % (silent_texts[:3],))
    for row in report['checks']:
        print('  [%s] %s' % ('ok' if row['ok'] else 'XX', row['what']))
    for row in report['failed']:
        print('FAILED: %s' % row)
    print('report: %s' % REPORT)
    return 0 if report['verdict'] == 'GREEN' else 3


if __name__ == '__main__':
    sys.exit(main())