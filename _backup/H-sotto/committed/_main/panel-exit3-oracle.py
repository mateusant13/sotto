"""ORACLE for the gap the worker lane declared: does the PANEL show a dead worker?

Lane `SottoDeviceResolution` landed `silent-device` + exit 3 in
`worker/sotto_worker.py` and said of the WebView2 panel, verbatim:

    "nao verificado: the WebView2 panel's RENDERED state on exit 3 -- read the
     code, did not run the shell."

Reading the code says the panel swallows it: `WorkerBridge._consume` classified
every worker state with an English-prose word list (`error|fail|fatal|dead|
stopped|crash|denied|missing`) that contains none of this worker's failure
states, so `silent-device` was painted with the same NEUTRAL styling as warm-up.
This oracle MEASURES the panel instead of reading it. Two arms, one command:

  ARM A  worker ALIVE (a real tone is routed into the cable):
         the panel must render a live caption state.
  ARM B  worker forced onto a permanently silent device, so it exits 3:
         the panel must render an ERROR state that NAMES the device.

The two arms must NOT render the same thing. Each arm reads the panel through
the shell's own DOM probe (`--dump-dom` + BRIDGE_PROBE), which now carries
`status.text`, `status.error`, `status.live` and the placeholder block, plus the
ordered `STATUS_APPLIED` lines the page posts back after writing each status
into `#status-text` ÔÇö i.e. the panel's own receipt of what it displayed.

Both shells run with CREATE_NO_WINDOW (AGENTS.md: the owner has been shown a
stray console twice) and the tone feed runs inside this process, so no window
is ever created. Usage:  py -3 _main/panel-exit3-oracle.py [arm-a-wait] [arm-b-wait]
        py -3 _main/panel-exit3-oracle.py --unit      # ARM 0 only, no audio needed

The RED input for ARM 0 is `_main/_prefix-under-test.py` ÔÇö the shell's classifier
BEFORE this lane's fix, kept so the gate can be shown to fail:

    PANEL_ORACLE_SHELL=H:/sotto/_main/_prefix-under-test.py py -3 _main/panel-exit3-oracle.py --unit   # rc=1
    py -3 _main/panel-exit3-oracle.py --unit                                                           # rc=0

ARM D is the join this file was extended for, and it is the one neither sibling
lane owned. `_main/panel-exit3-oracle.py` (lane SottoExit3Panel) asserted the
shell paints a DEAD worker and fed it a `silent-device` STATUS;
`_main/verdict-order-oracle.py` (lane SottoVerdictShadow) asserted the WORKER's
`done.verdict` matches its exit code. Neither fed the worker's real `done` line
to the shell and asked what the PANEL painted. ARM D does exactly that, on four
inputs: the real exit-3 `done` (verdict `silent-device`), a `done` whose verdict
the shell was never taught, a `done` carrying NO verdict at all (the
discriminating one), and the positive control (`captions-emitted`). It asserts
kind, the footer text and the placeholder body, because the bare word "done"
painted as a healthy finish was the defect.

The negative arm is built FROM TODAY'S shell, never from a kept copy:

    py -3 _main/panel-exit3-oracle.py --unit --neg-arm   # rc=0 only if the reverted COPY goes RED on D3

ARM E is the OTHER HALF of the hold, and it is the hole this file was extended
for a second time. Lane SottoExit3Panel taught the shell to HOLD a death across
the automatic restart until a caption proves recovery (`_wait` arms
`pending_error`, `_consume` swallows warm-up statuses while it is set, a caption
clears it). Every arm above checks the HOLD; none ever fed a caption AFTER an
error and asked whether the PANEL came back to life, so a fix that held the death
FOREVER would keep them all green. ARM E runs the real exit-3 sequence, then a
REAL caption on the same bridge, and asserts the painted state returns to LIVE
('Receiving captions', error=false, placeholder gone). Its negative arm removes
the CLEAR block from a COPY of today's shell and requires ARM E to go RED on the
unlifted hold:

    py -3 _main/panel-exit3-oracle.py --unit --neg-arm   # also proves the clear-removed mutant goes RED
    py -3 _main/panel-exit3-oracle.py --arm-e-real       # the two painted states, real WebView2 DOM

"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.environ.get('PANEL_ORACLE_SHELL') or os.path.join(
    ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
LOGS = HERE

CREATE_NO_WINDOW = 0x08000000
SILENT_DEVICE = 'Mapeador de som da Microsoft - Input'
CABLE_OUT = 'CABLE Output (VB-Audio Virtual Cable)'
#: The worker's own failure vocabulary, as a NEGATIVE arm must NOT match it.
FAILURE_TEXT_RE = ('silent', 'stopped', 'error', 'flat', 'exhausted', 'exit')
NEUTRAL_TEXT_RE = ('loading', 'model load', 'starting', 'capture not started')

#: The REAL `done` line an exit-3 run writes (worker/sotto_worker.py, the `emit(
#: type="status", state="done", verdict=verdict, ...)` call at the end of
#: `main()`), carrying the fields the panel's placeholder body prints. This is
#: the line the two sibling lanes each half-owned and neither fed to the shell:
#: `panel-exit3-oracle.py` fed the shell a `silent-device` STATUS, and
#: `verdict-order-oracle.py` checked the WORKER's `done.verdict` against the exit
#: code. The join -- that the shell PAINTS that verdict -- is this arm.
REAL_DONE_SILENT_DEVICE = {
    'type': 'status', 'state': 'done', 'verdict': 'silent-device',
    'blocks': 34, 'block_samples': 54400, 'nonzero_blocks': 3,
    'peak': 0.000122, 'chunks': 6, 'captions': 0, 'tokens': 1, 'rotations': 0,
    'device': SILENT_DEVICE, 'device_outcome': 'all-flat',
}
#: A verdict NOBODY taught this shell. The discriminating input: a `done` that
#: says done does not get to be healthy on the strength of the word.
UNKNOWN_VERDICT = 'a-verdict-this-shell-never-learned'
#: The only verdict the panel is allowed to paint as a NORMAL finish.
HEALTHY_VERDICT = 'captions-emitted'

#: The negative arm is built from TODAY's shell by reverting exactly the line
#: this lane changed, so it can never go stale the way a kept copy can.
MUTANT = os.path.join(HERE, '_panel-verdict-benign-mutant.py')
MUTANT_FIXED = '        if verdict not in HEALTHY_DONE_VERDICTS:\n'
MUTANT_BENIGN = '        if verdict and verdict not in HEALTHY_DONE_VERDICTS:\n'

#: ARM E's caption: a REAL caption line -- the ONLY thing allowed to lift a held
#: death (`sotto_webview.py`, the `_consume` caption branch, `pending_error`).
#: The old oracle fed a caption only in ARM 0's quick restart check and looked at
#: `pending_error` alone: it never asserted that the PANEL came back to life.
CAPTION_TEXT = 'ola mundo'
#: panel.js:188-189 -- the text the PAGE paints after it commits a caption. The
#: live state is painted by the page, not the shell: the shell only FORWARDS the
#: caption, so a stub that returns this is modelling panel.js, not inventing it.
LIVE_STATUS_TEXT = 'Receiving captions'
#: ARM E's negative arm: the CLEAR path removed from a COPY of TODAY's shell.
MUTANT_E = os.path.join(HERE, '_panel-clear-lifted-mutant.py')
MUTANT_E_FIXED = (
    '            if self.pending_error is not None:\n'
    "                self.log(f'BRIDGE_DEATH_LIFTED reason=caption "
    "captions={self.captions}')\n"
    '                self.pending_error = None\n')
#: The fake worker the REAL-shell ARM E drives: it writes only the line shapes
#: worker/sotto_worker.py writes, so the shell's own `_consume` handles it
#: unchanged. Mode is chosen by SOTTO_ARME_MODE (`hold` | `recover`).
FAKE_WORKER = os.path.join(HERE, '_armE-fake-worker.py')
FAKE_WORKER_RUNS = os.path.join(HERE, '_armE-worker-runs.txt')


def _load_sibling_probe(name: str, path: str):
    """Import a probe by path, so its module-level code runs but its main() does not."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_shell(out_path: str, args: list[str], feed_stop=None, env=None) -> int:
    """Spawn the REAL shell hidden, capture its stdout, and return its exit code."""
    out = open(out_path, 'wb')
    proc = subprocess.Popen(
        [sys.executable, SHELL, *args],
        stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        cwd=os.path.dirname(SHELL),
        env=env,
    )
    rc = proc.wait(timeout=400)
    out.close()
    if feed_stop is not None:
        feed_stop.set()
    return rc


def lines(path: str) -> list[str]:
    with open(path, encoding='utf-8', errors='replace') as f:
        return [ln.rstrip('\n') for ln in f]


def one(log: list[str], needle: str) -> str | None:
    for ln in log:
        if needle in ln:
            return ln
    return None


def last_json(log: list[str], prefix: str) -> dict | None:
    got = None
    for ln in log:
        i = ln.find(prefix)
        if i < 0:
            continue
        try:
            got = json.loads(ln[i + len(prefix):])
        except ValueError:
            pass
    return got


def applied_texts(log: list[str]) -> list[str]:
    """Every text the PAGE posted back after writing it into #status-text."""
    out = []
    for ln in log:
        i = ln.find('STATUS_APPLIED text=')
        if i < 0:
            continue
        try:
            out.append(json.loads(ln[i + len('STATUS_APPLIED text='):]))
        except ValueError:
            out.append(ln[i:])
    return out


def worker_exits(log: list[str]) -> list[int]:
    out = []
    for ln in log:
        i = ln.find('BRIDGE_EXIT ')
        if i < 0:
            continue
        for tok in ln[i:].split():
            if tok.startswith('rc='):
                try:
                    out.append(int(tok[3:]))
                except ValueError:
                    pass
    return out


def rendered(log: list[str]) -> dict:
    """The panel's own DOM state, as the last BRIDGEPROBE of the run."""
    probe = last_json(log, 'BRIDGEPROBE ') or {}
    status = probe.get('status') or {}
    return {
        'text': status.get('text', probe.get('statusText', '')),
        'error': bool(status.get('error')),
        'live': bool(status.get('live')),
        'className': status.get('className'),
        'placeholderTitle': (probe.get('placeholder') or {}).get('title', ''),
        'placeholderBody': (probe.get('placeholder') or {}).get('body', ''),
        'placeholderHidden': (probe.get('placeholder') or {}).get('hidden'),
        'warming': bool((probe.get('placeholder') or {}).get('warming')),
        'captions': (probe.get('captions') or {}).get('count'),
    }


def _load_shell_module():
    """Import the shell as a module, so ARM 0 drives the REAL WorkerBridge."""
    sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
    spec = importlib.util.spec_from_file_location('sotto_webview_under_test', SHELL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arm0_classifier(report: dict) -> list[str]:
    """Feed the shell's OWN WorkerBridge the lines this worker really writes.

    No device, no model, no WebView2 ÔÇö so this half still runs on a box with no
    audio routed, which is the state this whole lane was written in. The only
    stand-in is the process handle, needed to reach `_wait` without spawning.
    """
    mod = _load_shell_module()
    failures: list[str] = []
    log_lines: list[str] = []
    painted: list[tuple] = []

    class _Child:
        pid = 4242

        def wait(self):
            return 3

    def new_bridge():
        b = mod.WorkerBridge(
            command=sys.executable, worker_path=WORKER, log=log_lines.append,
            on_status=lambda t, k, i: painted.append((t, k, dict(i))),
            on_caption=lambda t, m: painted.append(('caption:' + t, 'live', dict(m))),
            backoff_base=600000, backoff_max=600000)
        b.child = _Child()      # stand-in handle: `_wait` needs one, not a spawn
        return b

    cases = [
        ('silent-device',
         {'type': 'status', 'state': 'silent-device', 'verdict': 'silent-device',
          'device': SILENT_DEVICE, 'api': 'MME', 'peak': 0.000122, 'peak_floor': 0.002,
          'blocks': 34, 'detail': 'delivered 34 blocks but never reached peak 0.002'},
         'error', SILENT_DEVICE),
        ('device-exhausted',
         {'type': 'status', 'state': 'device-exhausted', 'reason': 'all-flat'},
         'error', None),
        ('done-failure',
         {'type': 'status', 'state': 'done', 'verdict': 'all-candidate-taps-flat',
          'blocks': 34, 'peak': 0.000122, 'captions': 0}, 'error', None),
        ('done-healthy',
         {'type': 'status', 'state': 'done', 'verdict': 'captions-emitted', 'captions': 5},
         'busy', None),
        ('device-rotated',
         {'type': 'status', 'state': 'device-rotated', 'reason': 'flat'},
         'busy', None),
        ('error-chunk',
         {'type': 'status', 'state': 'error', 'stage': 'chunk',
          'detail': "TypeError: 'NoneType' object is not subscriptable"},
         'error', None),
    ]
    seen = []
    for name, message, want_kind, want_in_text in cases:
        painted.clear()
        new_bridge()._consume(json.dumps(message))
        text, kind, info = painted[-1] if painted else (None, None, {})
        seen.append({'case': name, 'kind': kind, 'text': text})
        if kind != want_kind:
            failures.append(f'ARM 0/{name}: kind={kind!r} expected {want_kind!r} '
                            f'(text={text!r})')
        if want_in_text and want_in_text not in str(text):
            failures.append(f'ARM 0/{name}: the panel text does not name it: {text!r}')
        if want_kind == 'error' and not (info or {}).get('body'):
            failures.append(f'ARM 0/{name}: an error with an EMPTY placeholder body '
                            f'({info!r})')

    # A death must survive the restart's warm-up, and a caption must lift it.
    b = new_bridge()
    b._consume(json.dumps({'type': 'status', 'state': 'silent-device',
                           'device': SILENT_DEVICE, 'api': 'MME'}))
    b._wait()                      # rc=3 from the stand-in handle
    death_text = painted[-1][0]
    b.stop('arm0')                 # cancel the restart timer: no real spawn here
    painted.clear()
    b._consume(json.dumps({'type': 'status', 'state': 'model-loading'}))
    seen.append({'case': 'restart-warmup-held', 'kind': painted[-1][1] if painted else None,
                 'text': death_text})
    if painted and painted[-1][0] != death_text:
        failures.append('ARM 0/restart: a warm-up status PAINTED OVER the death: '
                        f'{death_text!r} -> {painted[-1][0]!r}')
    if not any('BRIDGE_STATUS_HELD' in ln for ln in log_lines):
        failures.append('ARM 0/restart: the warm-up was not held (no BRIDGE_STATUS_HELD)')
    b._consume(json.dumps({'type': 'caption', 'text': 'ola'}))
    if b.pending_error is not None:
        failures.append('ARM 0/recover: a caption did not lift the pending death')

    report['arm0_classifier'] = {'cases': seen, 'log_tail': log_lines[-6:]}
    return failures


def arm0_done_verdict(report: dict) -> list[str]:
    """THE JOIN the two sibling lanes each named and neither owned.

    `panel-exit3-oracle.py` asserted the shell paints a DEAD worker; it fed the
    shell a `silent-device` STATUS, never the `done` line that follows it.
    `verdict-order-oracle.py` asserted `done.verdict == "silent-device"` iff
    exit 3 inside the WORKER, and stopped at the worker's word. Its own receipt
    says so, verbatim: `falta_no_gate: The oracle checks the WORKER's word vs
    code, not that the panel/shell renders it`. So this arm feeds the shell the
    worker's REAL `done` line and asserts the PAINTED state, on the same
    channel the page is painted through: `WorkerBridge._consume` ->
    `worker_status_kind` -> `_status` -> `on_status(text, kind, info)`, which is
    exactly what `apply_panel_state` pushes into #status-text and toggles
    `status--error` with.

    Four inputs, and the third is the discriminating one:

      D1  the real exit-3 `done` (verdict `silent-device`)  -> PAINTED error
      D2  a `done` whose verdict is a word nobody taught   -> PAINTED error
      D3  a `done` carrying NO verdict at all              -> PAINTED error
          (D3 is the defect this arm was written to find: the mapping read
           `if verdict and verdict not in HEALTHY_DONE_VERDICTS`, so a missing
           verdict skipped the test, missed the prose list -- which does not
           contain the word `done` -- and a bare "done" was painted as a
           healthy finish.)
      D4  the POSITIVE control, verdict `captions-emitted`  -> PAINTED busy
          (without this, an arm that painted EVERYTHING red would also pass)
    """
    mod = _load_shell_module()
    failures: list[str] = []
    painted: list[tuple] = []

    class _Child:
        pid = 4243

        def wait(self):
            return 0

    def new_bridge():
        b = mod.WorkerBridge(
            command=sys.executable, worker_path=WORKER, log=lambda _ln: None,
            on_status=lambda t, k, i: painted.append((t, k, dict(i or {}))),
            on_caption=lambda t, m: painted.append((t, 'live', dict(m))),
            backoff_base=600000, backoff_max=600000)
        b.child = _Child()      # stand-in handle: `_consume` never needs a spawn
        return b

    # name, message, want_kind, word that must reach the footer, word that must
    # reach the placeholder body ('' = do not care beyond non-empty)
    cases = [
        ('done-silent-device-exit3', REAL_DONE_SILENT_DEVICE, 'error',
         'silent-device', SILENT_DEVICE.split(' - ')[0]),
        ('done-unknown-verdict',
         {'type': 'status', 'state': 'done', 'verdict': UNKNOWN_VERDICT,
          'captions': 0, 'blocks': 34, 'peak': 0.000122}, 'error',
         UNKNOWN_VERDICT, ''),
        ('done-no-verdict',
         {'type': 'status', 'state': 'done', 'captions': 0, 'blocks': 12,
          'peak': 0.000122, 'device': SILENT_DEVICE}, 'error', '', ''),
        ('done-healthy-control',
         {'type': 'status', 'state': 'done', 'verdict': HEALTHY_VERDICT,
          'captions': 5}, 'busy', '', ''),
    ]
    seen = []
    for name, message, want_kind, want_footer, want_body in cases:
        painted.clear()
        new_bridge()._consume(json.dumps(message))
        got = painted[-1] if painted else (None, None, {})
        text, kind, info = got
        footer = str(text or '')
        body = str((info or {}).get('body') or '')
        seen.append({'case': name, 'kind': kind, 'footer': footer,
                     'placeholder_title': (info or {}).get('title'),
                     'placeholder_body': body})
        if kind != want_kind:
            failures.append(f'ARM D/{name}: kind={kind!r} expected {want_kind!r} '
                            f'(footer={footer!r})')
        if want_kind == 'error':
            # The two lies this arm exists to kill: the bare state token in the
            # footer, and an error painted with the panel's WARM-UP placeholder.
            if not footer.strip() or footer.strip().lower() == 'done':
                failures.append(f'ARM D/{name}: the footer is a bare/neutral '
                                f'token, not a failure: {footer!r}')
            if not body:
                failures.append(f'ARM D/{name}: an error with an EMPTY '
                                f'placeholder body ({info!r})')
            if not (info or {}).get('title'):
                failures.append(f'ARM D/{name}: an error with no placeholder '
                                f'title ({info!r})')
        else:
            if 'error' in footer.lower():
                failures.append(f'ARM D/{name}: the positive control was painted '
                                f'as a failure: {footer!r}')
            if footer.strip().lower() != 'done':
                failures.append(f'ARM D/{name}: the healthy control must still '
                                f'render the NEUTRAL `done` footer, not '
                                f'{footer!r} (without this the arm would pass by '
                                f'painting everything red)')
        if want_footer and want_footer not in footer:
            failures.append(f'ARM D/{name}: the verdict word never reached the '
                            f'footer: {want_footer!r} not in {footer!r}')
        if want_body and want_body not in body:
            failures.append(f'ARM D/{name}: {want_body!r} never reached the '
                            f'placeholder body: {body!r}')

    # The real run writes TWO lines in this order: the loud `silent-device`
    # status, then the `done`. Fed in sequence through ONE bridge, the death
    # must survive to the second line -- the panel must still be showing an
    # error naming the device once the `done` has been consumed.
    painted.clear()
    b = new_bridge()
    b._consume(json.dumps({
        'type': 'status', 'state': 'silent-device', 'verdict': 'silent-device',
        'device': SILENT_DEVICE, 'api': 'MME', 'peak': 0.000122,
        'peak_floor': 0.002, 'blocks': 34,
        'detail': f'{SILENT_DEVICE} [MME] opened and delivered 34 blocks but '
                  'never reached peak 0.002'}))
    b._consume(json.dumps(REAL_DONE_SILENT_DEVICE))
    text, kind, info = painted[-1] if painted else (None, None, {})
    seen.append({'case': 'real-sequence-silent-device-then-done', 'kind': kind,
                 'footer': str(text or ''),
                 'placeholder_body': str((info or {}).get('body') or '')})
    if kind != 'error':
        failures.append('ARM D/real-sequence: the `done` after a silent-device '
                        f'status repainted a NON-error state: {kind!r} {text!r}')
    if 'silent-device' not in str(text or '') + str((info or {}).get('body') or ''):
        failures.append('ARM D/real-sequence: the verdict never reached the '
                        'footer or the placeholder after the real two-line '
                        f'sequence: {text!r} / {(info or {}).get("body")!r}')

    report['arm0_done_verdict'] = {'cases': seen}

    # WHY THE ORDER IS ASSERTED AND NOT TRUSTED. This arm reads the kind off
    # `on_status`, and the panel's DOM class is set by `apply_panel_state` in TWO
    # steps: `send_status(text)` first -- which is where panel.js's OWN prose
    # regex (/stopped|error|dead|no audio|no working/i, panel.js:213) sets
    # `status--error` -- and then an `exec_js` that re-toggles it from OUR kind.
    # Swap those two statements and the page's regex becomes the FINAL painter:
    # an error whose footer carries none of the page's words (the no-verdict
    # footer is exactly one) is then painted NEUTRAL in the DOM while this arm
    # still reads `error`. That is a hole in this gate, so the order is checked.
    try:
        with open(SHELL, encoding='utf-8') as f:
            src = f.read()
        body = src[src.index('def apply_panel_state'):]
        body = body[:body.index('\n    def ', 1)]
        i_send = body.index('self.send_status(')
        i_kind = body.index('status--error')
        if i_send > i_kind:
            failures.append('ARM D/paint-order: `apply_panel_state` toggles '
                            'status--error BEFORE it sends the text, so the '
                            "page's own prose regex decides the final class and "
                            'this arm can be green while the panel paints '
                            'NEUTRAL (app/webview/sotto_webview.py)')
    except ValueError as exc:
        failures.append(f'ARM D/paint-order: could not read the paint order out '
                        f'of {SHELL}: {exc!r}')
    return failures


def arm0_recovery(report: dict) -> list[str]:
    """ARM E -- the SECOND HALF of the hold: does a REAL caption bring the panel
    back to LIFE?

    Lane SottoExit3Panel taught the shell to HOLD a worker's death across the
    automatic restart until a caption proves recovery: `_wait` arms
    `pending_error` on a non-zero exit, `_consume` swallows the restart's warm-up
    statuses while it is set, and a caption clears it. Every oracle since checks
    the HOLD; ARM 0's restart case even ends by asserting `pending_error is None`
    after a caption -- ONE boolean on the BRIDGE, never the PAINTED state. So a
    fix that held the death FOREVER would keep every arm green, because none of
    them ever asked what the PANEL shows once a caption arrives. This arm does.

    It drives the shell's OWN WorkerBridge (no device, no model, no WebView2 --
    the same driver ARM 0 and ARM D use), runs the REAL exit-3 sequence (the
    loud `silent-device` status, then the worker's own `done`, then the non-zero
    exit), and then feeds a REAL caption on the SAME bridge. It asserts the
    painted state returns to LIVE:

      E1  the death is on screen and HELD (an error footer naming the device)
      E2  a restart warm-up (`model-loading`) is SWALLOWED, not painted over it
      E3  the caption is DELIVERED to the page handler (the shell forwards it)
      E4  the caption LIFTS the hold (`pending_error` is None;
          `BRIDGE_DEATH_LIFTED` is logged)
      E5  the panel is LIVE: footer 'Receiving captions' (panel.js:189),
          error=false, placeholder GONE (panel.js:156)
      E6  a warm-up AFTER the caption is PAINTED again, not held

    E5 is asserted as the CONTRACT the fix promises -- "the death stays on screen
    until a caption proves recovery" -- so a caption that did NOT lift the hold
    leaves the panel in the DEATH state, and E5 is where that shows. The page's
    own `addCaption` paints 'Receiving captions' on ANY caption (panel.js:189 is
    unconditional), so on the REAL shell a broken lift surfaces as E4/E6 (the
    hold sticks and swallows later warm-ups) rather than as a literal red footer;
    both are asserted here, and `arm_e_real_shell` measures which one the REAL
    DOM reports. That asymmetry is the per-lane caveat, not a hole.
    """
    mod = _load_shell_module()
    failures: list[str] = []
    log_lines: list[str] = []
    painted: list[dict] = []

    class _Child:
        pid = 4244

        def wait(self):
            return 3

    def status_stub(text, kind, info):
        info = info or {}
        painted.append({'what': 'status', 'footer': str(text), 'kind': kind,
                        'title': info.get('title'), 'body': info.get('body')})

    def caption_stub(text, meta):
        # panel.js:188-189 -- a committed caption hides the placeholder and
        # paints the footer live. This is the PAGE, and the shell FORWARDS the
        # caption to it, so the stub models panel.js instead of inventing it.
        painted.append({'what': 'caption', 'footer': LIVE_STATUS_TEXT,
                        'kind': 'live', 'text': str(text),
                        'title': '', 'body': ''})

    bridge = mod.WorkerBridge(
        command=sys.executable, worker_path=WORKER, log=log_lines.append,
        on_status=status_stub, on_caption=caption_stub,
        backoff_base=600000, backoff_max=600000)
    bridge.child = _Child()

    # -- the REAL exit-3 sequence, exactly as ARM D feeds it, then the exit that
    #    arms the hold (the `done` line alone does NOT: only `_wait` sets it).
    bridge._consume(json.dumps({
        'type': 'status', 'state': 'silent-device', 'verdict': 'silent-device',
        'device': SILENT_DEVICE, 'api': 'MME', 'peak': 0.000122,
        'peak_floor': 0.002, 'blocks': 34,
        'detail': f'{SILENT_DEVICE} [MME] opened and delivered 34 blocks but '
                  'never reached peak 0.002'}))
    bridge._consume(json.dumps(REAL_DONE_SILENT_DEVICE))
    bridge._wait()                 # rc=3 from the stand-in handle: arms the hold
    bridge.stop('arm-e')           # cancel the restart timer: no real spawn here

    err = painted[-1] if painted else {}
    error_state = {'footer': err.get('footer', ''),
                   'error': err.get('kind') == 'error',
                   'holding': bridge.pending_error is not None}
    if not error_state['error']:
        failures.append(f'ARM E/E1: no error was painted before the caption: {err!r}')
    if not error_state['holding']:
        failures.append('ARM E/E1: the exit-3 death did not arm the hold '
                        '(pending_error is None), so there is nothing to lift')

    # -- E2: the restart's warm-up must be HELD, not painted over the death.
    n_before = len(painted)
    bridge._consume(json.dumps({'type': 'status', 'state': 'model-loading'}))
    held = len(painted) == n_before
    if not held:
        failures.append('ARM E/E2: a restart warm-up PAINTED OVER the death '
                        f'({painted[-1]!r}) -- the hold is not holding')
    if not any('BRIDGE_STATUS_HELD' in ln for ln in log_lines):
        failures.append('ARM E/E2: the warm-up was not held (no BRIDGE_STATUS_HELD)')

    # -- E3/E4/E5: a REAL caption on the SAME bridge.
    painted.clear()
    bridge._consume(json.dumps({'type': 'caption', 'text': CAPTION_TEXT,
                                'start': 0.0, 'end': 1.5}))
    cap = painted[-1] if painted else {}
    lifted = bridge.pending_error is None
    delivered = bool(painted) and cap.get('what') == 'caption'
    if not delivered:
        failures.append('ARM E/E3: the caption never reached the page handler '
                        f'({cap!r}) -- the panel can never come back to life')
    if not lifted:
        failures.append('ARM E/E4: the caption did NOT lift the held death '
                        '(pending_error is still set)')
    if not any('BRIDGE_DEATH_LIFTED' in ln for ln in log_lines):
        failures.append('ARM E/E4: no BRIDGE_DEATH_LIFTED line -- the clear path '
                        'never ran')

    # E5: the painted state, composed as the CONTRACT says it must be -- the
    # death stays on screen until the caption lifts it. A caption that did not
    # lift leaves the panel in the DEATH state, which is the RED this arm exists
    # to catch.
    live_state = {
        'footer': LIVE_STATUS_TEXT if lifted else error_state['footer'],
        'error': not lifted,
        'placeholderHidden': lifted,
        'delivered': delivered,
    }
    if live_state['error']:
        failures.append('ARM E/E5: the panel did NOT return to live after the '
                        f"caption -- it stayed in ERROR showing "
                        f"{error_state['footer']!r}")
    if live_state['footer'] != LIVE_STATUS_TEXT:
        failures.append('ARM E/E5: the panel is not showing the live footer '
                        f'{LIVE_STATUS_TEXT!r}: {live_state["footer"]!r}')
    if not live_state['placeholderHidden']:
        failures.append('ARM E/E5: the placeholder is still up after the caption '
                        '(panel.js:156 hides it on the first committed line)')

    # -- E6: with the hold lifted, the NEXT warm-up must PAINT again -- this is
    #    the real observable difference a sticky hold leaves on the panel.
    n_after = len(painted)
    bridge._consume(json.dumps({'type': 'status', 'state': 'capture-started'}))
    repainted = len(painted) > n_after
    if not repainted:
        failures.append('ARM E/E6: a warm-up AFTER the caption was still HELD -- '
                        'the clear did not take, the hold is sticky')

    report['arm_e_recovery'] = {
        'error_state': error_state,
        'held_once': held,
        'caption_delivered': delivered,
        'lifted': lifted,
        'live_state': live_state,
        'warmup_after_caption_painted': repainted,
        'log_tail': log_lines[-5:],
    }
    return failures


def build_neg_mutant() -> tuple[bool, str, dict]:
    """A COPY of TODAY's shell with exactly this lane's mapping reverted.

    Built by rewriting the one line, never by keeping a second copy of a 2400
    line file: a kept copy goes stale the first time anyone touches the shell,
    and a stale negative arm reports on code nobody is running.
    """
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    n = src.count(MUTANT_FIXED)
    if n != 1:
        return False, (f'the line this lane changed appears {n} times in {SHELL} '
                       f'(expected exactly 1)'), {}
    out = src.replace(MUTANT_FIXED, MUTANT_BENIGN)
    if out == src:
        return False, 'the mutant is byte-identical to the source', {}
    with open(MUTANT, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    import hashlib
    digest = lambda b: hashlib.sha256(b).hexdigest()[:16]
    info = {'mutant': MUTANT, 'src_sha16': digest(src.encode('utf-8')),
            'mutant_sha16': digest(out.encode('utf-8'))}
    if info['src_sha16'] == info['mutant_sha16']:
        return False, 'the mutation did not move the artefact hash', info
    return True, '', info


def neg_arm(report: dict) -> list[str]:
    """Run the unit arms against the reverted COPY and require them to go RED.

    The gate PASSES only when the mutant is red AND red for the RIGHT reason:
    D3 (the absent verdict) fails, while D1/D2/D4 still pass. A mutant that
    broke everything, or that stayed green, is not this lane's negative arm.
    """
    failures: list[str] = []
    ok, reason, info = build_neg_mutant()
    report['neg_arm'] = dict(info)
    if not ok:
        return [f'NEGATIVE ARM: cannot build the mutant: {reason}']
    env = dict(os.environ)
    env['PANEL_ORACLE_SHELL'] = MUTANT
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--unit'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=os.path.dirname(os.path.abspath(__file__)),
        creationflags=CREATE_NO_WINDOW, timeout=300)
    text = proc.stdout.decode('utf-8', 'replace')
    report['neg_arm']['child_rc'] = proc.returncode
    try:
        child = json.loads(text)
    except ValueError:
        return [f'NEGATIVE ARM: the mutant run printed no JSON verdict '
                f'(rc={proc.returncode}): {text[-400:]!r}']
    child_failures = list(child.get('failures') or [])
    report['neg_arm']['child_failures'] = child_failures
    if proc.returncode == 0:
        failures.append('NEGATIVE ARM: the reverted shell stayed GREEN ÔÇö the '
                        'arm cannot fail, so it proves nothing')
    if not any('done-no-verdict' in f for f in child_failures):
        failures.append('NEGATIVE ARM: the mutant went red for the WRONG '
                        f'reason ÔÇö no `done-no-verdict` failure: {child_failures}')
    for name in ('done-silent-device-exit3', 'done-unknown-verdict',
                 'done-healthy-control'):
        if any(name in f for f in child_failures):
            failures.append(f'NEGATIVE ARM: the mutant also broke {name!r}, '
                            'which this revert must NOT touch')
    return failures


def build_neg_mutant_e() -> tuple[bool, str, dict]:
    """A COPY of TODAY's shell with the CLEAR path REMOVED.

    The CLEAR block is matched by TEXT and COUNTED, so a shell that has drifted
    away from this shape makes the arm REFUSE rather than mutate the wrong
    thing; the no-op and the stale-copy failure modes are refused by the hash
    moving. Built from today's shell, never from a kept copy: a kept copy goes
    stale the first time anyone touches the shell.
    """
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    n = src.count(MUTANT_E_FIXED)
    if n != 1:
        return False, (f'the CLEAR block appears {n} times in {SHELL} '
                       f'(expected exactly 1)'), {}
    out = src.replace(MUTANT_E_FIXED, '')
    if out == src:
        return False, 'the mutant is byte-identical to the source', {}
    with open(MUTANT_E, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    import hashlib
    digest = lambda b: hashlib.sha256(b).hexdigest()[:16]
    info = {'mutant': MUTANT_E, 'src_sha16': digest(src.encode('utf-8')),
            'mutant_sha16': digest(out.encode('utf-8'))}
    if info['src_sha16'] == info['mutant_sha16']:
        return False, 'the mutation did not move the artefact hash', info
    return True, '', info


def neg_arm_e(report: dict) -> list[str]:
    """Run the unit arms against the CLEAR-removed COPY and require ARM E RED.

    PASS only when the mutant is red AND red for the RIGHT reason: an `ARM E`
    failure naming the unlifted hold. ARM D must stay GREEN -- the clear path
    has nothing to do with the verdict mapping -- and the mutant must not break
    a verdict case, which a mutant that broke everything would.
    """
    failures: list[str] = []
    ok, reason, info = build_neg_mutant_e()
    report['neg_arm_e'] = dict(info)
    if not ok:
        return [f'NEGATIVE ARM E: cannot build the mutant: {reason}']
    env = dict(os.environ)
    env['PANEL_ORACLE_SHELL'] = MUTANT_E
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--unit'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=os.path.dirname(os.path.abspath(__file__)),
        creationflags=CREATE_NO_WINDOW, timeout=300)
    text = proc.stdout.decode('utf-8', 'replace')
    report['neg_arm_e']['child_rc'] = proc.returncode
    try:
        child = json.loads(text)
    except ValueError:
        return [f'NEGATIVE ARM E: the mutant run printed no JSON verdict '
                f'(rc={proc.returncode}): {text[-400:]!r}']
    child_failures = list(child.get('failures') or [])
    report['neg_arm_e']['child_failures'] = child_failures
    if proc.returncode == 0:
        failures.append('NEGATIVE ARM E: the clear-removed shell stayed GREEN -- '
                        'ARM E cannot fail, so it proves nothing')
    if not any('ARM E' in f for f in child_failures):
        failures.append('NEGATIVE ARM E: the mutant went red without a single '
                        f'ARM E failure: {child_failures}')
    for name in ('done-silent-device-exit3', 'done-unknown-verdict',
                 'done-no-verdict', 'done-healthy-control'):
        if any(name in f for f in child_failures):
            failures.append(f'NEGATIVE ARM E: the clear-removed mutant also '
                            f'broke {name!r}, which it must NOT touch')
    return failures


def _reset_fake_worker_runs():
    try:
        os.remove(FAKE_WORKER_RUNS)
    except OSError:
        pass


def arm_e_real_shell(report: dict) -> list[str]:
    """ARM E on the REAL shell: BOTH painted states, measured in the DOM.

    One fake worker (`_armE-fake-worker.py`), two modes, two real WebView2 runs.
    The fake worker writes only the line shapes worker/sotto_worker.py writes, so
    the shell's own `_consume` handles it unchanged: run 1 always dies of a
    `silent-device` (a loud status, the worker's own `done`, then exit 3), and in
    `recover` mode run 2 comes back, emits `model-loading` (held), and then ONE
    real caption, and goes quiet so the page's hold timer (COMMIT_MAX_HOLD_MS,
    1500 ms) commits it.

      mode=hold     every run exits 3 and no caption is ever emitted -> the DOM
                    must show the HELD ERROR and name the device
      mode=recover  run 1 exits 3, run 2 emits a caption             -> the DOM
                    must show 'Receiving captions', error=false, placeholder gone

    Both shells are spawned CREATE_NO_WINDOW and with --no-hotkey (AGENTS.md), so
    the owner is neither shown a window nor robbed of Alt+C. `--arm-e-real` runs
    only this arm.
    """
    failures: list[str] = []
    report['arm_e_real_shell'] = {}

    def one(mode, wait):
        _reset_fake_worker_runs()
        log_path = os.path.join(LOGS, f'panel-exit3-armE-{mode}.log')
        env = dict(os.environ)
        env['SOTTO_ARME_MODE'] = mode
        rc = run_shell(log_path, [
            '--with-worker', '--worker', FAKE_WORKER, '--no-hot-reload',
            '--no-hotkey', '--python', sys.executable, '--dump-dom',
            '--dump-dom-wait', str(wait), '--log', log_path + '.mirror',
        ], env=env)
        log = lines(log_path)
        return {'shell_rc': rc, 'rendered': rendered(log),
                'worker_exits': worker_exits(log),
                'death_lines': [ln for ln in log if 'BRIDGE_DEATH ' in ln][-2:],
                'lifted_lines': [ln for ln in log if 'BRIDGE_DEATH_LIFTED' in ln],
                'held_lines': [ln for ln in log if 'BRIDGE_STATUS_HELD' in ln][-2:],
                'status_applied_tail': applied_texts(log)[-6:]}

    hold = one('hold', 12.0)
    report['arm_e_real_shell']['hold'] = hold
    hr = hold['rendered']
    if not hr['error']:
        failures.append(f'ARM E-real/hold: the DOM is NOT in error: {hr!r}')
    errlow = (str(hr['text']) + ' ' + str(hr['placeholderBody'])).lower()
    if 'silent' not in errlow:
        failures.append('ARM E-real/hold: the error does not name the silent '
                        f'device: {hr!r}')
    if hr.get('placeholderHidden'):
        failures.append('ARM E-real/hold: the placeholder is hidden in an error '
                        'with zero captions, so the owner sees no headline')
    if 3 not in hold['worker_exits']:
        failures.append(f"ARM E-real/hold: no worker exit 3 ({hold['worker_exits']})")

    time.sleep(3.0)   # let the first WebView2 process fully exit between runs

    live = one('recover', 13.0)
    report['arm_e_real_shell']['recover'] = live
    lr = live['rendered']
    if lr['error']:
        failures.append(f'ARM E-real/recover: the panel stayed in ERROR after a '
                        f'caption: {lr!r}')
    if not lr['live']:
        failures.append(f'ARM E-real/recover: the panel is not LIVE (status--live '
                        f'not set): {lr!r}')
    if str(lr['text']).strip() != LIVE_STATUS_TEXT:
        failures.append('ARM E-real/recover: the footer is not '
                        f'{LIVE_STATUS_TEXT!r}: {lr["text"]!r}')
    if not lr.get('placeholderHidden'):
        failures.append('ARM E-real/recover: the placeholder is still up after a '
                        f'committed caption: {lr!r}')
    if not (lr.get('captions') or 0) > 0:
        failures.append(f'ARM E-real/recover: no caption line was rendered: {lr!r}')
    if not live['lifted_lines']:
        failures.append('ARM E-real/recover: no BRIDGE_DEATH_LIFTED in the shell '
                        'log -- the clear path never ran on the real shell')
    return failures


def main() -> int:
    unit_only = '--unit' in sys.argv
    real_e_only = '--arm-e-real' in sys.argv
    rest = [a for a in sys.argv[1:] if not a.startswith('--')]
    a_wait = float(rest[0]) if len(rest) > 0 else 40.0
    b_wait = float(rest[1]) if len(rest) > 1 else 26.0
    failures: list[str] = []
    report: dict = {}

    # ÔöÇÔöÇ ARM E, REAL SHELL ONLY: `--arm-e-real` runs just this arm, so the two
    #    painted states can be reproduced without the audio-dependent A/B.
    if real_e_only:
        failures += arm_e_real_shell(report)
        report['verdict'] = 'PASS' if not failures else 'FAIL'
        report['failures'] = failures
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    # ÔöÇÔöÇ ARM 0: the CLASSIFIER, fed the worker's own lines. No device, no model,
    #    no shell; this is the half that must go RED on any future change that
    #    reintroduces the swallow, and it stays runnable when no audio is routed.
    failures += arm0_classifier(report)

    # ÔöÇÔöÇ ARM D: the JOIN the two sibling lanes named and neither owned -- the
    #    worker's REAL `done` line through the shell's mapper, asserted at the
    #    paint (kind + footer text + placeholder), including the case where the
    #    verdict is one the shell was never taught.
    failures += arm0_done_verdict(report)

    # ÔöÇÔöÇ ARM E: the SECOND HALF of the hold -- a REAL caption after the exit-3
    #    death must bring the panel back to LIVE, not leave it held forever.
    failures += arm0_recovery(report)

    # ÔöÇÔöÇ NEGATIVE ARMS: revert this lane's mapping, and separately REMOVE the
    #    CLEAR path, in a COPY of today's shell, and require the gate to go RED
    #    on exactly the discriminating input each time.
    if '--neg-arm' in sys.argv:
        failures += neg_arm(report)
        failures += neg_arm_e(report)

    if unit_only:
        report['verdict'] = 'PASS' if not failures else 'FAIL'
        report['failures'] = failures
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    feed = _load_sibling_probe('device_silence_oracle',
                               os.path.join(HERE, 'device-silence-oracle.py'))

    # ÔöÇÔöÇ ARM A: worker ALIVE - a real tone is routed into the cable ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    stop = threading.Event()
    threading.Thread(target=feed.feed_cable, args=(stop,), daemon=True).start()
    time.sleep(1.0)
    a_log_path = os.path.join(LOGS, 'panel-exit3-armA.log')
    a_rc = run_shell(a_log_path, [
        '--with-worker', '--device', CABLE_OUT, '--no-hot-reload', '--no-hotkey',
        '--python', sys.executable, '--dump-dom',
        '--dump-dom-wait', str(a_wait), '--log', a_log_path + '.mirror',
    ], feed_stop=stop)
    a_log = lines(a_log_path)
    a = rendered(a_log)
    report['armA_worker_alive'] = {
        'shell_rc': a_rc, 'worker_exits': worker_exits(a_log), 'rendered': a,
        'status_applied': applied_texts(a_log)[-6:],
        'stderr_silent_lines': [ln for ln in a_log if 'SILENT-DEVICE' in ln],
    }

    # The two int8 loads back to back kill the second process on this box
    # (measured by the device lane), so the arms are separated in wall time.
    time.sleep(15.0)

    # ÔöÇÔöÇ ARM B: worker forced onto a permanently silent device -> exit 3 ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    b_log_path = os.path.join(LOGS, 'panel-exit3-armB.log')
    b_rc = run_shell(b_log_path, [
        '--with-worker', '--device', SILENT_DEVICE, '--no-hot-reload', '--no-hotkey',
        '--python', sys.executable, '--dump-dom',
        '--dump-dom-wait', str(b_wait), '--log', b_log_path + '.mirror',
    ])
    b_log = lines(b_log_path)
    b = rendered(b_log)
    b_exits = worker_exits(b_log)
    b_applied = applied_texts(b_log)
    report['armB_worker_exit3'] = {
        'shell_rc': b_rc, 'worker_exits': b_exits, 'rendered': b,
        'status_applied_tail': b_applied[-6:],
        'death_lines': [ln for ln in b_log if 'BRIDGE_DEATH ' in ln],
        'held_lines': [ln for ln in b_log if 'BRIDGE_STATUS_HELD' in ln],
        'stderr_silent_lines': [ln for ln in b_log if 'SILENT-DEVICE' in ln],
    }

    # ÔöÇÔöÇ the assertions. ARM B's rc=3 is the worker's OWN exit, read from the
    #    shell's BRIDGE_EXIT line; the shell's own rc is 0 because --dump-dom
    #    ends it by request.
    if 3 not in b_exits:
        failures.append(f'ARM B: no worker exit 3 in the log (saw {b_exits})')
    if not b['error']:
        failures.append(f"ARM B: panel rendered a NON-error state: {b['text']!r}")
    low = str(b['text']).lower()
    if not any(w in low for w in FAILURE_TEXT_RE) and not any(
            w in str(b['placeholderTitle']).lower() for w in FAILURE_TEXT_RE):
        failures.append(f'ARM B: no failure word in what the panel shows: '
                        f"text={b['text']!r} title={b['placeholderTitle']!r}")
    if SILENT_DEVICE.split(' - ')[0] not in str(b['text']) + str(b['placeholderBody']):
        failures.append('ARM B: the panel does not NAME the silent device: '
                        f"text={b['text']!r} body={b['placeholderBody']!r}")
    # THE JOIN, on the real DOM: the `done` line's OWN verdict is what has to
    # have travelled. The worker writes `verdict=silent-device` on both the loud
    # status and the `done`, so this asserts the VERDICT WORD reached the panel
    # -- the word `verdict-order-oracle.py` proves the worker emits, and that no
    # oracle until now proved the shell paints.
    if 'silent-device' not in (str(b['text']) + str(b['placeholderBody'])).lower():
        failures.append('ARM B: the `silent-device` VERDICT never reached the '
                        f"panel: text={b['text']!r} body={b['placeholderBody']!r}")

    if a['error']:
        failures.append(f"ARM A: a live run rendered an ERROR state: {a['text']!r}")
    if not ((a['captions'] or 0) > 0 or a['live']):
        failures.append(f"ARM A: no live caption state (captions={a['captions']}, "
                        f"live={a['live']}, text={a['text']!r})")

    # ÔöÇÔöÇ the NEGATIVE arm: the two renders must NOT be the same
    if str(a['text']).strip().lower() == str(b['text']).strip().lower():
        failures.append('NEGATIVE ARM: the silent-device run renders the SAME '
                        f"status as the healthy run ({a['text']!r})")
    if a['error'] == b['error']:
        failures.append('NEGATIVE ARM: error styling is identical on both arms '
                        '(error=%r)' % (a['error'],))

    # ÔöÇÔöÇ ARM E on the REAL shell: the two painted states measured in the DOM.
    #    A fake worker reproduces the exit-3 death and then, in `recover` mode,
    #    a real caption -- so BOTH the error and the live DOM are pasted from a
    #    real WebView2 run, not from the unit driver.
    failures += arm_e_real_shell(report)

    report['verdict'] = 'PASS' if not failures else 'FAIL'
    report['failures'] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
