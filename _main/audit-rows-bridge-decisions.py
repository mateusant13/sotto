# =============================================================================
# audit-rows-bridge-decisions.py -- ONE instrument for EIGHT open register rows
# that all live in the SottoShell WorkerBridge decision table:
#
#   #11  the "no audio" falsifier rewrites a REAL worker error to busy
#   #12  an EMPTY caption counts as proof-of-life and lifts the death banner
#   #13  start() returns True with no worker at all
#   #15  _schedule_restart overwrites the timer without cancelling the old one
#   #38  a mid-run tag=tick can be read as the run's total (tag lands nowhere)
#   #41  a status line without a type key is dropped in silence
#   #42  stop() emits no final status on the Python side
#   #43  _spawn() runs on the restart thread WITHOUT the lock
#
# EVERY arm is measured on the LIVE bytes by IMPORTING the shell as a module and
# calling its own methods. Nothing is launched: no shell, no window, no tray, no
# hotkey, no worker, no device, no WebView2 (the owner order of 2026-10-11).
# The module import executes module-level code only.
#
# THE INSTRUMENT CAN SAY NO, PER ROW: for every arm there is a MUTANT of the
# shell -- the defect FIXED by ONE literal replacement -- written into a COPY
# under %TEMP%, and the arm must FLIP colour on that copy. An arm that returns
# the same answer against today's bytes and against the fixed mutant is RED: it
# is a printed label, not a detector.
#
# Usage:  py -3 _main/audit-rows-bridge-decisions.py [--neg-arm] [--verbose]
# =============================================================================
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')

VERBOSE = False


def say(message):
    print(message, flush=True)


def detail(message):
    if VERBOSE:
        say('    ' + message)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def load_shell(path, name):
    """Import the shell from a FILE -- no launch, no window, no worker."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def line_of(text, anchor):
    """1-based line number of the FIRST occurrence of an anchor, or 0.

    The anchor is written with \n; the shell is CRLF, so it is re-encoded to
    the file's OWN line ending before it is searched -- the same conversion the
    mutant writer does, which is what makes the number cited here the number the
    mutation actually lands on.
    """
    newline = '\r\n' if '\r\n' in text else '\n'
    index = text.find(anchor.replace('\n', newline))
    if index < 0:
        return 0
    return text.count('\n', 0, index) + 1


# ---------------------------------------------------------------------------
# mutants: one literal replacement each, CRLF preserved (the shell is CRLF)
# ---------------------------------------------------------------------------
MUTANTS = {
    # #11 -- THE MUTANT NOW GOES THE OTHER WAY (2026-10-11): the live falsifier only fires
    # while NO caption has arrived, so the mutant DROPS that guard and lets it rewrite a
    # REAL error again.
    'm11-guard-removed': (
        '        elif FALSE_AUDIO_ABSENT_RE.search(value) and self.captions == 0:',
        '        elif FALSE_AUDIO_ABSENT_RE.search(value):'),
    # #12 -- INVERTED: the live shell refuses '' and the mutant accepts it again.
    'm12-empty-caption-accepted': (
        "            text = message.get('text')\n"
        "            if not text:\n",
        "            text = message.get('text')\n"
        "            if text is None:\n"),
    # #13 -- INVERTED: the live start() reports the spawn; the mutant reports the REQUEST.
    'm13-start-reports-request': (
        "            return self._spawn() is not None\n",
        "            return True\n"),
    # #15 -- INVERTED: the live shell cancels the armed timer; the mutant overwrites it.
    'm15-timer-overwritten': (
        "        # CANCEL BEFORE OVERWRITING (row #15, 2026-10-11): overwriting the handle\n"
        "        # left the previous timer ARMED and unreachable, so two restarts could\n"
        "        # fire for one death -- and `_cancel_timers()` could no longer reach the\n"
        "        # first one at all.\n"
        "        if self._restart_timer is not None:\n"
        "            try:\n"
        "                self._restart_timer.cancel()\n"
        "            except Exception:  # noqa: BLE001\n"
        "                pass\n"
        "        self._restart_timer = timer\n",
        "        self._restart_timer = timer\n"),
    # #38 -- INVERTED: the live payload SAYS which source it came from; the mutant drops
    # the tag from the STATS branch, which is the one a tick and a total share.
    'm38-stats-tag-dropped': (
        "        payload['tag'] = (fields.get('tag') if isinstance(fields, dict) else None) or 'stats'\n",
        "        pass  # m38: the worker's own tag is NOT carried -- the defect\n"),
    # #40 -- INVERTED into the mutant it now has to be: the live shell lowercases the
    # type like the JS twin; the mutant compares it RAW again.
    'm40-case-normalisation-removed': (
        "        kind = str(message.get('type') or '').lower()\n",
        "        kind = message.get('type')\n"),
    # #41 -- the unknown-type line is swallowed instead of counted and logged.
    'm41-unknown-type-silent': (
        "        else:\n"
        "            self.malformed += 1\n"
        "            self.log(f'BRIDGE_UNKNOWN type={kind!r}')\n",
        "        else:\n"
        "            pass\n"),
    # #42 -- stop() says on the status channel that it stopped.
    # #42 -- INVERTED: the live stop TELLS the panel when there was nothing to stop.
    'm42-stop-silent': (
        "        self.log(f'BRIDGE_STOP reason={reason} pid=none')\n"
        "        self._bridge_status(\n"
        "            'Nothing to stop - no worker is running',\n"
        "            'busy',\n"
        "            {'title': 'No worker running',\n"
        "             'body': 'The stop request arrived when no transcription worker was '\n"
        "                     'running.'},\n"
        "            'idle')\n"
        "        return False\n",
        "        self.log(f'BRIDGE_STOP reason={reason} pid=none')\n"
        "        return False\n"),
    # #43 -- the restart thread takes the lock before it spawns.
    # #43 -- INVERTED: the live restart path holds the lock; the mutant drops it.
    'm43-restart-without-lock': (
        "        with self._lock:\n"
        "            if self.stopped or self.child is not None:\n"
        "                return\n"
        "            self.state = 'restarting'\n"
        "            self._spawn()\n",
        "        if self.stopped or self.child is not None:\n"
        "            return\n"
        "        self.state = 'restarting'\n"
        "        self._spawn()\n"),
}


def make_mutant(source, key, directory):
    old, new = MUTANTS[key]
    newline = '\r\n' if '\r\n' in source else '\n'
    old_n = old.replace('\n', newline)
    new_n = new.replace('\n', newline)
    count = source.count(old_n)
    if count != 1:
        say('SETUP ERROR: the ' + key + ' anchor appears ' + str(count)
            + ' time(s) in ' + SHELL + ' (wanted exactly 1) -- the mutation '
            'would not be the one this instrument documents')
        raise SystemExit(2)
    path = os.path.join(directory, 'sotto_webview_' + key + '.py')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(source.replace(old_n, new_n, 1))
    return path


# ---------------------------------------------------------------------------
# the harness: a bridge built in-process, with its log captured
# ---------------------------------------------------------------------------
class Recorder:
    def __init__(self, mod, worker_path):
        self.logs = []
        self.statuses = []
        self.captions = []
        self.bridge = mod.WorkerBridge(
            command=sys.executable,
            worker_path=worker_path,
            log=self.logs.append,
            on_caption=lambda text, meta: self.captions.append((text, meta)),
            on_status=lambda text, kind, info: self.statuses.append(
                (text, kind, dict(info or {}))),
            silence_ms=3600000,          # never fire the watchdog in-process
            backoff_base=600000,         # restart timers stay pending, not fired
            backoff_max=600000)

    def names(self):
        return [entry.split(' ', 1)[0] for entry in self.logs]

    def close(self):
        try:
            self.bridge.stop('audit')
        except Exception:
            pass


class FakeChild:
    pid = 424242


# ---------------------------------------------------------------------------
# arms -- each returns the measured values, including the row's own key
# ---------------------------------------------------------------------------
def arm_r11(mod):
    """#11: a REAL worker error whose detail says there is no audio."""
    rec = Recorder(mod, WORKER)
    # The line the worker itself writes (worker/sotto_worker.py:4361):
    #   emit(type="status", state="error", stage="selftest",
    #        detail=f"no audio at {audio}")
    line = json.dumps({'type': 'status', 'state': 'error', 'stage': 'selftest',
                       'detail': 'no audio at I:/cc-tmp/audit-row11.wav'})
    rec.bridge._consume(line)
    text, kind = rec.statuses[-1][0], rec.statuses[-1][1]
    # THE SECOND CASE (2026-10-11, row #11): once ONE caption has arrived, the SAME real
    # error must keep its own kind and text. The guard exists so the falsifier cannot hide a
    # genuine regression behind "capture not started" after the panel has seen audio.
    rec.bridge.captions = 1
    rec.bridge._consume(line)
    text_after, kind_after = rec.statuses[-1][0], rec.statuses[-1][1]
    rec.bridge.captions = 0
    rec.close()
    return {
        'worker_said': 'state=error stage=selftest detail="no audio at ..."',
        'kind_after_a_caption': kind_after,
        'text_after_a_caption': text_after[:70],
        'rewrites_after_caption': (kind_after == 'busy'
                                   and text_after == mod.CAPTURE_NOT_STARTED),
        'kind_emitted': kind,
        'text_emitted': text[:70],
        'rewritten': kind == 'busy' and text == mod.CAPTURE_NOT_STARTED,
    }


def arm_r12(mod):
    """#12: an EMPTY caption lifts a death the panel is showing."""
    rec = Recorder(mod, WORKER)
    rec.bridge.pending_error = {'state': 'silent-device', 'text': 'dead',
                                'body': ''}
    rec.bridge.last_error = dict(rec.bridge.pending_error)
    rec.bridge.captions = 0
    rec.bridge._consume(json.dumps({'type': 'caption', 'text': ''}))
    lifted = rec.bridge.pending_error is None
    result = {
        'caption_text': repr(rec.captions[-1][0] if rec.captions else None),
        'captions_counter': rec.bridge.captions,
        'malformed_counter': rec.bridge.malformed,
        'death_lifted': lifted,
        'lift_logged': 'BRIDGE_DEATH_LIFTED' in rec.names(),
    }
    rec.close()
    return result


def arm_r13(mod):
    """#13: start() with a worker path that does not exist."""
    absent = os.path.join(tempfile.gettempdir(),
                          'sotto-audit-row13-absent-worker-NEVER-CREATED.py')
    if os.path.exists(absent):
        os.remove(absent)
    rec = Recorder(mod, absent)
    started = rec.bridge.start('audit-row13')
    result = {
        'start_returned': bool(started),
        'child_is_none': rec.bridge.child is None,
        'spawns': rec.bridge.spawns,
        'state': rec.bridge.state,
        'status': (rec.statuses[-1][0][:60] if rec.statuses else None),
        'restart_scheduled': rec.bridge._restart_timer is not None,
    }
    result['returns_true_with_no_worker'] = (bool(started)
                                             and rec.bridge.child is None)
    rec.close()
    return result


def arm_r15(mod):
    """#15: two restarts scheduled -- is the first timer cancelled?"""
    rec = Recorder(mod, WORKER)
    rec.bridge._schedule_restart('first')
    first = rec.bridge._restart_timer
    time.sleep(0.05)
    rec.bridge._schedule_restart('second')
    second = rec.bridge._restart_timer
    result = {
        'first_is_second': first is second,
        'first_still_alive': bool(first is not None and first.is_alive()),
        'second_alive': bool(second is not None and second.is_alive()),
        'restart_log_lines': [n for n in rec.names() if n == 'BRIDGE_RESTART'],
    }
    result['timers_pending'] = sum(
        1 for t in (first, second) if t is not None and t.is_alive())
    result['overwrites_without_cancel'] = result['first_still_alive']
    rec.close()
    return result


def arm_r38(mod):
    """#38: does the payload the panel reads tell a tick from the final?"""
    rec = Recorder(mod, WORKER)
    child = FakeChild()
    tick = 'WORKER_STATS tag=tick blocks=42 peak=0.1000 nonzero_blocks=7\n'
    final = 'WORKER_STATS tag=final blocks=99 peak=0.4000 nonzero_blocks=9\n'
    rec.bridge._pump(iter([tick]), 'stderr', child)
    tick_payload = mod.SottoShell.stats(types.SimpleNamespace(bridge=rec.bridge,
                                                              last_meter=None))
    rec.bridge._pump(iter([final]), 'stderr', child)
    final_payload = mod.SottoShell.stats(types.SimpleNamespace(bridge=rec.bridge,
                                                               last_meter=None))
    # The OTHER source (2026-10-11, row #38): a fresh meter tick must say so too.
    rec.bridge.last_meter = {'at': time.monotonic(), 'peak': 0.5, 'blocks': 7}
    meter_payload = mod.SottoShell.stats(types.SimpleNamespace(
        bridge=rec.bridge, last_meter=rec.bridge.last_meter))
    rec.bridge.last_meter = None
    result = {
        'meter_payload_tag': meter_payload.get('tag'),
        'stored_tag': (rec.bridge.last_worker_stats or {}).get('tag'),
        'tick_payload': tick_payload,
        'final_payload': final_payload,
        'payload_has_tag': 'tag' in tick_payload,
        'payloads_differ': tick_payload != final_payload,
    }
    result['tick_indistinguishable_from_total'] = not result['payload_has_tag']
    rec.close()
    return result


#: The JS twin, read ONCE (this file has no `read()` helper). `worker-bridge.js` is the
#: Electron-era bridge the row #40 comparison is against: it lowercases `message.type`
#: before branching, and the SHELL did not.
JS_TWIN = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'app', '_legacy-electron', 'worker-bridge.js'),
               encoding='utf-8').read()


def arm_r40(mod):
    """#40: a MIS-CASED type is a caption to the JS twin and was a drop here."""
    rec = Recorder(mod, WORKER)
    before_captions, before_malformed = rec.bridge.captions, rec.bridge.malformed
    rec.bridge._consume(json.dumps({'type': 'Caption', 'text': 'mis-cased'}))
    rec.bridge._consume(json.dumps({'type': 'STATUS', 'state': 'capture-started'}))
    result = {
        'captions_added': rec.bridge.captions - before_captions,
        'malformed_added': rec.bridge.malformed - before_malformed,
        'caption_text': repr(rec.captions[-1][0] if rec.captions else None),
        'js_twin_rule_present': 'toLowerCase()' in JS_TWIN,
        'js_twin_separator_rule_present': 'replace(/[-_]' in JS_TWIN,
    }
    result['mis_cased_type_dropped'] = result['captions_added'] == 0
    rec.close()
    return result


def arm_r41(mod):
    """#41: a status line with no type key."""
    rec = Recorder(mod, WORKER)
    rec.bridge.malformed = 0
    rec.bridge._consume(json.dumps({'state': 'capture-started',
                                    'device': 'X'}))
    logged = 'BRIDGE_UNKNOWN' in rec.names()
    result = {
        'malformed': rec.bridge.malformed,
        'statuses': len(rec.statuses),
        'logged_unknown': logged,
        'log_lines': [entry[:60] for entry in rec.logs],
    }
    # The row has TWO halves and they are not the same claim:
    #   dropped    -- the line paints nothing (TRUE today and in any fix)
    #   in_silence -- nothing counts it and nothing logs it (the DEFECT)
    result['dropped'] = not rec.statuses
    result['in_silence'] = (rec.bridge.malformed == 0 and not logged)
    rec.close()
    return result


def arm_r42(mod):
    """#42: does stop() say anything on the status channel?"""
    rec = Recorder(mod, WORKER)
    before = len(rec.statuses)
    returned = rec.bridge.stop('audit-row42')
    result = {
        'stop_returned': returned,
        'statuses_emitted_by_stop': len(rec.statuses) - before,
        'stop_log_lines': [entry[:50] for entry in rec.logs
                           if 'BRIDGE_STOP' in entry],
    }
    result['no_final_status'] = result['statuses_emitted_by_stop'] == 0
    return result


def arm_r43(mod):
    """#43: is the lock held when _spawn() runs from each entry point?"""
    rec = Recorder(mod, WORKER)
    seen = {}

    def probe(*_a, **_k):
        seen['calls'] = seen.get('calls', 0) + 1
        seen['locked'] = rec.bridge._lock.locked()
        got_it = rec.bridge._lock.acquire(blocking=False)
        seen['acquirable'] = got_it
        if got_it:
            rec.bridge._lock.release()

    rec.bridge._spawn = probe
    rec.bridge._restart()                       # the restart thread's path
    restart_locked = seen.get('locked')
    seen.clear()
    rec.bridge.start('audit-row43')             # the caller's path
    start_locked = seen.get('locked')
    result = {
        'restart_path_locked': restart_locked,
        'start_path_locked': start_locked,
    }
    result['restart_spawns_without_lock'] = (restart_locked is False
                                             and start_locked is True)
    rec.close()
    return result


ARMS = ('r11', 'r12', 'r13', 'r15', 'r38', 'r40', 'r41', 'r42', 'r43')
MEASURE = {'r11': arm_r11, 'r12': arm_r12, 'r13': arm_r13, 'r15': arm_r15,
           'r38': arm_r38, 'r40': arm_r40, 'r41': arm_r41, 'r42': arm_r42,
           'r43': arm_r43}
MUTANT_OF = {'r11': 'm11-guard-removed', 'r12': 'm12-empty-caption-accepted',
             'r13': 'm13-start-reports-request',
             'r15': 'm15-timer-overwritten',
             'r38': 'm38-stats-tag-dropped', 'r40': 'm40-case-normalisation-removed',
             'r41': 'm41-unknown-type-silent',
             'r42': 'm42-stop-silent', 'r43': 'm43-restart-without-lock'}
#: What each arm must READ on the LIVE bytes, and on its OWN mutant. SEVEN of the eight
#: flipped on 2026-10-11, the day the rows were paid: the live shell now carries every fix
#: this instrument exists to measure, and each mutant reproduces the defect it names. r41
#: is the one that was already refuted on the live bytes (the shell COUNTS and LOGS the
#: typeless line, and the mutant is what the row describes: silence).
EXPECT = {
    'r11': {'live': False, 'mutant': True},
    'r12': {'live': False, 'mutant': True},
    'r13': {'live': False, 'mutant': True},
    'r15': {'live': False, 'mutant': True},
    'r38': {'live': False, 'mutant': True},
    'r41': {'live': False, 'mutant': True},
    'r40': {'live': False, 'mutant': True},
    'r42': {'live': False, 'mutant': True},
    'r43': {'live': False, 'mutant': True},
}
#: The key each arm READS to decide "the defect is present today".
#: r11 reads the SECOND case (after a caption), which is the claim the row makes now:
#: the falsifier may still fire while NO caption has ever arrived, by design.
DEFECT_KEY = {'r11': 'rewrites_after_caption', 'r12': 'death_lifted',
              'r40': 'mis_cased_type_dropped',
              'r13': 'returns_true_with_no_worker',
              'r15': 'overwrites_without_cancel',
              'r38': 'tick_indistinguishable_from_total',
              'r41': 'in_silence', 'r42': 'no_final_status',
              'r43': 'restart_spawns_without_lock'}
ROW_OF = {
    'r11': 'audit #11 (shell-bridge.md F2): the no-audio falsifier rewrites a '
           'REAL worker error to CAPTURE_NOT_STARTED/busy',
    'r12': 'audit #12 (shell-bridge.md F3): an EMPTY caption counts as '
           'proof-of-life and clears the death banner',
    'r13': 'audit #13 (shell-bridge.md F4): start() returns true with no '
           'worker at all',
    'r15': 'audit #15 (shell-bridge.md F6): _schedule_restart overwrites the '
           'timer without cancelling the previous one',
    'r38': 'audit #38 (audio-path.md F5): a mid-run tick can be read as the '
           'run total (tag=tick vs tag=final)',
    'r40': 'audit #40: the SHELL compares `type` RAW where the JS twin normalises it '
           '(worker-bridge.js:691), so one mis-cased line is a caption to one arm and a '
           'drop to the other',
    'r41': 'audit #41 (shell-bridge.md F8): a status line without a type key '
           'is dropped in silence',
    'r42': 'audit #42 (shell-bridge.md F9): stop() emits no final status on '
           'the Python side',
    'r43': 'audit #43 (shell-bridge.md F10): _spawn() runs on the restart '
           'thread WITHOUT the lock',
}


def run_all(mod):
    results = {}
    for name in ARMS:
        try:
            results[name] = MEASURE[name](mod)
        except Exception as exc:  # noqa: BLE001
            results[name] = {'ERROR': type(exc).__name__ + ': ' + str(exc)}
    return results


def report(label, results, expected):
    say('')
    say('== ' + label)
    matched = True
    for name in ARMS:
        got = results[name]
        key = DEFECT_KEY[name]
        value = got.get(key)
        defect = value if isinstance(value, bool) else None
        ok = (defect is expected[name])
        matched = matched and ok
        wanted = 'DEFECT-PRESENT' if expected[name] else 'DEFECT-REFUTED'
        seen = 'DEFECT-PRESENT' if defect else 'DEFECT-REFUTED'
        say('  ARM ' + name + '  ' + seen.ljust(15) + ' want=' + wanted.ljust(15)
            + ('OK' if ok else 'WRONG COLOUR') + '  ' + ROW_OF[name])
        say('      measured: ' + json.dumps(got, default=str))
    return matched


def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(
        description='Eight open audit rows in the WorkerBridge decision table, '
                    'measured in-process against the live shell bytes '
                    '(launches nothing).')
    parser.add_argument('--shell', default=SHELL)
    parser.add_argument('--neg-arm', action='store_true',
                        help='run only the mutant half (the instrument must '
                             'flip on every copy)')
    parser.add_argument('--verbose', action='store_true')
    parsed = parser.parse_args(argv)
    VERBOSE = parsed.verbose
    shell_path = os.path.abspath(parsed.shell)

    say('audit-rows-bridge-decisions -- eight open rows, one instrument')
    say('shell      : ' + shell_path)
    say('bytes      : ' + str(os.path.getsize(shell_path)))
    say('sha256     : ' + sha256_file(shell_path))
    say('launches   : NOTHING (no shell, no window, no tray, no hotkey, '
        'no worker, no device)')

    with open(shell_path, encoding='utf-8', newline='') as handle:
        source = handle.read()
    say('')
    say('anchors (1-based line of the FIRST occurrence, live bytes):')
    for key in ARMS:
        anchor = MUTANTS[MUTANT_OF[key]][0]
        say('  ' + key + ': ' + MUTANT_OF[key].ljust(30) + ' anchor line '
            + str(line_of(source, anchor)) + '  '
            + repr(anchor.split('\n')[0].strip()[:60]))

    directory = tempfile.mkdtemp(prefix='sotto-audit-bridge-')
    say('')
    say('mutants    : ' + directory)
    mutant_paths = {}
    for key in ARMS:
        path = make_mutant(source, MUTANT_OF[key], directory)
        mutant_paths[key] = path
        say('  ' + os.path.basename(path).ljust(46) + ' '
            + str(os.path.getsize(path)) + ' B  sha256 '
            + sha256_file(path)[:16])

    verdicts = []
    live_present = []
    live_measured = False
    if not parsed.neg_arm:
        live = load_shell(shell_path, 'audit_bridge_live')
        results = run_all(live)
        live_measured = True
        # RECORDED, not asserted: the closing line used to say "7 defects present, 1
        # refuted" as a FIXED string, and that sentence went stale the day the seven
        # rows were paid (2026-10-11). A PASS line must derive from the run it closes.
        live_present = [name for name in ARMS
                        if results[name].get(DEFECT_KEY[name]) is True]
        expected = {name: EXPECT[name]['live'] for name in ARMS}
        ok = report('LIVE shell -- every arm must read what the ARM declares',
                    results, expected)
        verdicts.append(('live', ok))

    for key in ARMS:
        module = load_shell(mutant_paths[key], 'audit_bridge_' + key)
        results = run_all(module)
        expected = {name: (EXPECT[name]['mutant'] if name == key
                           else EXPECT[name]['live']) for name in ARMS}
        ok = report('MUTANT ' + MUTANT_OF[key] + ' -- arm ' + key
                    + ' alone must FLIP', results, expected)
        verdicts.append((key, ok))

    say('')
    failed = [label for label, ok in verdicts if not ok]
    if failed:
        say('VERDICT: FAIL  (' + str(len(verdicts) - len(failed)) + '/'
            + str(len(verdicts)) + ' labels matched; wrong: ' + str(failed)
            + ')')
        return 1
    if not live_measured:
        live_text = 'live NOT probed in this mode (--neg-arm), so no live set is claimed'
    elif live_present:
        live_text = (str(len(live_present)) + ' of ' + str(len(ARMS))
                     + ' defects still present on the live shell ('
                     + ', '.join(live_present) + ')')
    else:
        live_text = ('0 of ' + str(len(ARMS)) + ' defects present on the live shell -- every'
                     ' one refuted by the bytes')
    say('VERDICT: PASS  live: ' + live_text + '; ' + str(len(ARMS)) + '/' + str(len(ARMS))
        + ' mutants flipped exactly their own arm')
    return 0


if __name__ == '__main__':
    sys.exit(main())
