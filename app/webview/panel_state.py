"""Sotto — the panel as TEXT: a dump you read from a file, with no eyes.

WHY THIS EXISTS
    Until now the only way to know what the panel shows was a screen capture,
    and a capture needs vision and is limited in time. This module writes the
    panel's state to one JSON file every `interval_s` AND on request, so the
    state is readable with `read` at any moment, from disk, by anyone.

    `H:/sotto/_main/panel-state.json`.

WHERE THE DATA COMES FROM (there is no second path)
    Every field is state the app ALREADY holds, read where it already lands:

      * `WorkerBridge.state` — the bridge's own state machine — and its own
        counters (`captions`, `statuses`, `spawns`, `restarts`, `deaths`,
        `malformed`), plus `pending_error` / `no_audio_evidence`;
      * the shell's `caption_log` — the committed lines the DOM acked back;
      * the panel's OWN live box, read over the shell's existing `exec_js`
        seam: the same read a screenshot makes, in text. That is where the
        PROVISIONAL line (`.caption--provisional`) and the committed ones
        (`.caption--latest`) are told apart;
      * the worker's `WORKER_STATS` line, which the bridge ALREADY reads off
        the worker's stderr for its stderr tail — kept whole here, so `peak`
        and `nonzero_blocks` are readable instead of being thrown away;
      * the named endpoint, from the worker's own `device` / `device-rotated`
        / `capture-started` status messages.

    Nothing here spawns a process, opens a window, or touches a browser.

FRESHNESS, AND WHY THE AGE IS NOT SELF-REPORTED
    A dump ten minutes old is worse than none, because it LOOKS current. So
    the producer stamps `writtenAt` (ISO, with the machine's offset) and
    `writtenAtEpoch`, carries `staleAfterSeconds`, and rewrites the file on
    every tick. The authoritative AGE is `now - writtenAtEpoch` and is computed
    by the READER — never frozen into the JSON, because a producer that died
    cannot update a number inside the file it stopped writing, and a
    self-reported age would then be exactly the lie this design exists to
    remove. `ageSeconds` in the JSON is therefore defined as the age AT WRITE
    (0.0), and `panel_state.py --read` prints the real one.

READ IT
    python app/webview/panel_state.py --read                 # human report
    python app/webview/panel_state.py --read --json          # the raw dump
    python app/webview/panel_state.py --request              # dump now
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime

#: Bumped when a field is renamed or removed, so a reader can refuse a shape it
#: does not know instead of reading a wrong number.
SCHEMA = 'sotto.panel-state/1'
DEFAULT_INTERVAL_S = 2.0


def now_iso() -> str:
    """Local wall clock with its UTC offset — the same shape `medido_em` uses."""
    return datetime.now().astimezone().isoformat(timespec='seconds')


def write_atomic(path: str, payload: dict) -> None:
    """Write to a sibling temp file, fsync, then rename.

    A reader must never see a half-written dump: `os.replace` is atomic on
    Windows for a same-directory rename, so the file is either the previous
    dump or the new one, whole.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class PanelStateWriter:
    """Periodic + on-request writer of the panel dump.

    `snapshot(reason)` is the caller's function and returns the dict of state.
    The writer owns only the cadence, the freshness stamps and the atomicity.
    """

    def __init__(self, path, snapshot, log=lambda _m: None,
                 interval_s=DEFAULT_INTERVAL_S, request_path=None):
        self.path = path
        self.request_path = request_path
        self.snapshot = snapshot
        self.log = log
        self.interval_s = max(0.2, float(interval_s))
        self.sequence = 0
        self.writes = 0
        self.errors = 0
        self.last_write_epoch = None
        self._stop = threading.Event()
        self._thread = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> bool:
        if self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._loop,
                                        name='sotto-panel-state', daemon=True)
        self._thread.start()
        self.log(f'PANEL_STATE_WRITER path={self.path} '
                 f'interval_s={self.interval_s} '
                 f'request={self.request_path}')
        self.write('boot')
        return True

    def stop(self, reason='stop') -> None:
        self._stop.set()
        self.log(f'PANEL_STATE_WRITER_STOP reason={reason} '
                 f'writes={self.writes} errors={self.errors}')

    # -- the loop ----------------------------------------------------------
    def _pending_request(self) -> bool:
        """True once, per `panel-state.request` file dropped by a caller.

        The sentinel IS the on-demand path: an agent or a human writes the file
        (`write`/`touch`) and the next tick dumps immediately instead of waiting
        out the cadence. It is removed before the dump so a request cannot fire
        twice.
        """
        if not self.request_path:
            return False
        try:
            os.remove(self.request_path)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            self.log(f'PANEL_STATE_REQUEST_UNREADABLE '
                     f'path={self.request_path} error={exc!r}')
            return False

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.write('request' if self._pending_request() else 'periodic')

    # -- one dump ----------------------------------------------------------
    def write(self, reason='periodic') -> bool:
        try:
            payload = dict(self.snapshot(reason) or {})
        except Exception as exc:  # a bad snapshot must not kill the writer
            self.errors += 1
            self.log(f'PANEL_STATE_SNAPSHOT_FAILED reason={reason} error={exc!r}')
            return False
        generated = time.time()
        self.sequence += 1
        payload['schema'] = SCHEMA
        payload['reason'] = reason
        payload['sequence'] = self.sequence
        payload['writtenAt'] = now_iso()
        payload['writtenAtEpoch'] = round(generated, 3)
        payload['ageSeconds'] = 0.0
        payload['ageSecondsNote'] = (
            'age at write; the authoritative age is now - writtenAtEpoch and '
            'is printed by `panel_state.py --read`')
        payload['staleAfterSeconds'] = round(max(self.interval_s * 3.0, 5.0), 2)
        payload['producerPid'] = os.getpid()
        try:
            write_atomic(self.path, payload)
        except Exception as exc:
            self.errors += 1
            self.log(f'PANEL_STATE_WRITE_FAILED path={self.path} error={exc!r}')
            return False
        self.writes += 1
        self.last_write_epoch = generated
        return True


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def read_state(path: str) -> dict:
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def age_seconds(payload: dict, now=None):
    """`now - writtenAtEpoch`, or None when the dump carries no epoch."""
    epoch = payload.get('writtenAtEpoch')
    if epoch is None:
        return None
    return round((time.time() if now is None else now) - float(epoch), 3)


def freshness(payload: dict, now=None) -> str:
    age = age_seconds(payload, now)
    limit = payload.get('staleAfterSeconds')
    if age is None or limit is None:
        return 'UNKNOWN'
    return 'FRESH' if age <= float(limit) else 'STALE'


def format_report(payload: dict, now=None) -> str:
    """The two facts the dump must say, plus the panel state, in text.

    `writtenAt` is the dump's own timestamp; `ageSeconds` is its age, computed
    HERE, at read time, which is the only place it can be true.
    """
    out = []
    probe = payload.get('panel') or {}
    live = probe.get('live') or {}
    status = probe.get('status') or {}
    shell = payload.get('shell') or {}
    worker = payload.get('worker') or {}

    out.append('=== Sotto panel state (text) ===')
    out.append(f"writtenAt        = {payload.get('writtenAt')}")
    out.append(f"writtenAtEpoch   = {payload.get('writtenAtEpoch')}")
    out.append(f"ageSeconds       = {age_seconds(payload, now)}"
               f"   (now - writtenAtEpoch)")
    out.append(f"staleAfterSeconds= {payload.get('staleAfterSeconds')}")
    out.append(f"freshness        = {freshness(payload, now)}")
    out.append(f"reason           = {payload.get('reason')} "
               f"sequence={payload.get('sequence')} "
               f"producerPid={payload.get('producerPid')}")
    out.append('')
    out.append(f"namedState       = {payload.get('namedState')}")
    out.append(f"panel.status     = {status.get('text')!r} kind={status.get('kind')!r}")
    out.append(f"placeholder      = title={probe.get('placeholder', {}).get('title')!r} "
               f"hidden={probe.get('placeholder', {}).get('hidden')}")
    out.append(f"live.count       = {live.get('count')} "
               f"(provisional={live.get('provisionalCount')}) "
               f"hint={live.get('hint')!r}")
    for line in (live.get('lines') or []):
        mark = 'PROVISIONAL' if line.get('provisional') else 'committed'
        out.append(f"  [{mark}] {line.get('text')!r}")
    out.append('')
    out.append(f"captions (worker)  = {worker.get('captions')}   "
               f"statuses={worker.get('statuses')} "
               f"spawns={worker.get('spawns')} restarts={worker.get('restarts')} "
               f"deaths={worker.get('deaths')}")
    out.append(f"captionLog (shell) = {shell.get('captionLogCount')} "
               f"visible={shell.get('visible')}")
    device = worker.get('device') or {}
    out.append(f"endpoint           = {device.get('device')!r} "
               f"api={device.get('api')!r} from={device.get('state')!r} "
               f"current={worker.get('deviceCurrent')}")
    stats = worker.get('workerStats') or {}
    fields = stats.get('fields') or {}
    out.append(f"worker peak        = {fields.get('peak')} "
               f"nonzero_blocks={fields.get('nonzero_blocks')} "
               f"blocks={fields.get('blocks')} "
               f"(WORKER_STATS tag={stats.get('tag')} "
               f"childPid={stats.get('childPid')} "
               f"current={worker.get('workerStatsCurrent')})")
    out.append(f"noAudio            = {worker.get('noAudio')} "
               f"evidence={worker.get('noAudioEvidence')!r}")
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, os.pardir, os.pardir,
                                         '_main', 'panel-state.json'))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='panel-state',
        description='Read the Sotto panel as text, from the dump the app '
                    'writes, with no screenshot and no browser.')
    parser.add_argument('--path', default=_default_path(),
                        help='the dump to read (default: _main/panel-state.json)')
    parser.add_argument('--read', action='store_true',
                        help='print the dump and its AGE (the default action)')
    parser.add_argument('--json', action='store_true',
                        help='with --read, print the raw JSON instead of the report')
    parser.add_argument('--request', action='store_true',
                        help='drop the on-demand sentinel so the app dumps NOW')
    parser.add_argument('--request-path', default=None,
                        help='the sentinel path (default: <dump>.request)')
    args = parser.parse_args(argv)

    if args.request:
        request_path = args.request_path or (args.path + '.request')
        os.makedirs(os.path.dirname(os.path.abspath(request_path)), exist_ok=True)
        with open(request_path, 'w', encoding='utf-8') as handle:
            handle.write(f'requested {now_iso()}\n')
        print(f'PANEL_STATE_REQUESTED path={request_path}')
        print('the app writes the dump on its next tick (<= 2 s) and removes '
              'this file')
        return 0

    if not os.path.exists(args.path):
        print(f'PANEL_STATE_MISSING path={args.path}')
        print('the app has not written a dump yet, or it is writing elsewhere')
        return 3
    payload = read_state(args.path)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(format_report(payload))
    return 0


if __name__ == '__main__':
    sys.exit(main())
