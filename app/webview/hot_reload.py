"""Hot reload for the WebView2 shell: edit a source file, see it in the app.

THE PORT, NOT A SECOND IMPLEMENTATION
-------------------------------------
`app/_legacy-electron/hot-reload.js` already owns this idea for the Electron arm, and
this module is its counterpart, not a rival. `hot-reload.js` is a Node/CommonJS
module: it cannot be `require`d from a Python process, so it is not portable
and could not be reused even in principle. What IS portable — and what is
reproduced here verbatim — is its contract:

  * watch DIRECTORIES, not files (an editor save is a write-temp-then-rename,
    and a handle on the FILE dies at that rename: the classic "hot reload
    works twice then stops");
  * debounce the burst (`DEBOUNCE_MS = 250` ms of quiet, per kind, not per
    event, so one save yields exactly ONE call per kind);
  * decide WHEN, never WHAT — this module hands the caller the settled list of
    files; `sotto_webview.py` owns what a reload means (CoreWebView2.Reload)
    and what a worker change means (restart the bridge);
  * a callback that throws is a bug report, never the death of the app.

The engine-specific parts are necessarily different: `fs.watch` here is
`ReadDirectoryChangesW`, and Electron's `webContents.reloadIgnoringCache()` is
WebView2's `CoreWebView2` navigation.

`watchdog` is NOT installed on this box (measured: `ModuleNotFoundError: No
module named 'watchdog'`), and adding a dependency for one file watch would be
a worse trade than the ~60 lines of Win32 this needs.

RUN IT STANDALONE — `python hot_reload.py --selftest`
Exercises the watcher, the debounce and the flush against real files in a temp
directory, with no WebView2 and no window. It is the RED-capable half of the
gate: it fails when a burst produces more than one call, when a single write
produces none, or when the watcher dies at a rename-over (the bug this design
exists to prevent).
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import sys
import tempfile
import threading
import time

#: Quiet period that must pass after the LAST event of a burst. Same constant,
#: same reason, as hot-reload.js:DEBOUNCE_MS.
DEBOUNCE_MS = 250

#: The renderer assets that reload in place. Same set as hot-reload.js.
PANEL_ASSETS = frozenset(('panel.html', 'panel.css', 'panel.js'))

# --- Win32, read from the DLL, never assumed ------------------------------
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

FILE_LIST_DIRECTORY = 0x0001
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OVERLAPPED = 0x40000000
FILE_NOTIFY_CHANGE_NAME = 0x00000001 | 0x00000002      # file + dir rename
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_CREATION = 0x00000040
FILE_NOTIFY_CHANGE_ALL = (FILE_NOTIFY_CHANGE_NAME
                          | FILE_NOTIFY_CHANGE_ATTRIBUTES
                          | FILE_NOTIFY_CHANGE_SIZE
                          | FILE_NOTIFY_CHANGE_LAST_WRITE
                          | FILE_NOTIFY_CHANGE_CREATION)
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
ERROR_OPERATION_ABORTED = 995
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF
BUFFER_BYTES = 64 * 1024
#: GetOverlappedResult reports ERROR_IO_INPROGRESS while a read is outstanding.
ERROR_IO_INPROGRESS = 997
#: How long `_drain` waits for a cancelled read to retire before giving up.
DRAIN_TIMEOUT_S = 2.0


#: Sleep tick between completion polls. Small enough that a save is seen
#: promptly, large enough not to spin the core.
POLL_MS = 100

kernel32.CreateFileW.restype = wt.HANDLE
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID,
                                  wt.DWORD, wt.DWORD, wt.HANDLE]
kernel32.ReadDirectoryChangesW.restype = wt.BOOL
kernel32.ReadDirectoryChangesW.argtypes = [
    wt.HANDLE, wt.LPVOID, wt.DWORD, wt.BOOL, wt.DWORD, wt.LPVOID, wt.LPVOID]
kernel32.GetOverlappedResult.restype = wt.BOOL
kernel32.GetOverlappedResult.argtypes = [wt.HANDLE, wt.LPVOID, wt.LPDWORD,
                                         wt.BOOL]
kernel32.CancelIoEx.restype = wt.BOOL
kernel32.CancelIoEx.argtypes = [wt.HANDLE, wt.LPVOID]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.WaitForSingleObject.restype = wt.DWORD
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.ResetEvent.restype = wt.BOOL
kernel32.ResetEvent.argtypes = [wt.HANDLE]


class FILE_NOTIFY_INFORMATION(ctypes.Structure):
    """One record of a ReadDirectoryChangesW notification.

    The header is three DWORDs; the name follows at byte offset 12, and its
    length is in BYTES (not characters) and not NUL-terminated. Records are
    chained by NextEntryOffset; 0 ends the buffer.
    """
    _fields_ = [('NextEntryOffset', ctypes.c_uint32),
                ('Action', ctypes.c_uint32),
                ('FileNameLength', ctypes.c_uint32)]


class OVERLAPPED(ctypes.Structure):
    """`ctypes.wintypes` has no OVERLAPPED on this Python — measured:
    `AttributeError: module 'ctypes.wintypes' has no attribute 'OVERLAPPED'` —
    and the overlapped read needs a real one: `hEvent` is the handle that
    `CancelIoEx` and `WaitForSingleObject` are addressed by, so a placeholder
    would make stop() silently do nothing.
    """
    _fields_ = [('Internal', ctypes.c_size_t),
                ('InternalHigh', ctypes.c_size_t),
                ('Offset', ctypes.c_uint32),
                ('OffsetHigh', ctypes.c_uint32),
                ('hEvent', wt.HANDLE)]


kernel32.CreateEventW.restype = wt.HANDLE
kernel32.CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]


def parse_names(buf, nbytes):
    """[(action, filename)] out of one notification buffer.

    Parsed by the documented offsets rather than by `struct` layout, because
    the buffer is a chain of variable-length records and the declared structure
    has no room for the name it describes.
    """
    out = []
    if not nbytes:
        return out
    base = ctypes.cast(buf, ctypes.c_void_p).value
    offset = 0
    while offset + 12 <= nbytes:
        head = FILE_NOTIFY_INFORMATION.from_buffer_copy(
            ctypes.string_at(base + offset, 12))
        action = int(head.Action)
        nchars = int(head.FileNameLength) // 2
        name_at = offset + 12
        if name_at + nchars * 2 > nbytes:
            break  # truncated tail: a partial record is not a name
        name = ctypes.string_at(base + name_at, nchars * 2).decode(
            'utf-16-le', errors='replace')
        if name:
            out.append((action, name))
        nxt = int(head.NextEntryOffset)
        if nxt == 0:
            break
        offset += nxt
    return out


class DirWatcher(threading.Thread):
    """One blocking ReadDirectoryChangesW loop on one directory."""

    def __init__(self, directory, on_event, on_error=None):
        super().__init__(daemon=True, name='sotto-watch-' +
                         os.path.basename(directory))
        self.directory = directory
        self.on_event = on_event
        self._handle = None
        self._event = None
        # The OVERLAPPED struct and the notification buffer are OWNED BY THE
        # WATCHER, not by one loop iteration. An overlapped read points the
        # kernel at both of them for as long as the I/O is pending, so letting
        # Python free either one at the end of an iteration hands the kernel a
        # pointer into released heap. Measured on this box: the process then
        # dies later, far from the cause, with
        #   `Windows fatal exception: access violation` inside
        #   `shutil.py:584 _rmtree_isdir` — an unrelated-looking stack that is
        #   actually this corruption (reproduced 2/2 with rmtree, 0/2 without:
        #   `_main/_probe/hr5.out`, `_main/_probe/hr6.out`).
        self._overlapped = OVERLAPPED()
        self._buf = ctypes.create_string_buffer(BUFFER_BYTES)
        self._stopping = threading.Event()
        self._pending = False      # a read is issued and not yet drained

    # `_armed` is set HERE, not inferred from the return of Thread.start():
    # that returns None on success (measured), so `if not started:` calls every
    # successful watcher a failure and reports watchers=0 for a shell that had
    # two live watchers.
    _armed = False

    def start(self):
        """Arm the directory, then run. True only when the handle is live; a
        directory that cannot be watched is a log line, not a crash."""
        self._arm()
        if not self._armed:
            return False
        super().start()
        return True

    def _arm(self):
        self._event = kernel32.CreateEventW(None, True, False, None)
        if not self._event:
            self.on_error('EVENT_FAILED', ctypes.get_last_error())
            self._armed = False
            return
        handle = kernel32.CreateFileW(
            self.directory, FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED, None)
        if not handle or handle == INVALID_HANDLE_VALUE:
            self.on_error('OPEN_FAILED', ctypes.get_last_error())
            self._armed = False
            kernel32.CloseHandle(self._event)
            self._event = None
            return
        self._handle = handle
        self._armed = True

    def stop(self, reason='stop'):
        self._stopping.set()
        # CancelIoEx only REQUESTS cancellation. The kernel keeps pointers into
        # `_overlapped` and `_buf` until the operation actually completes with
        # ERROR_OPERATION_ABORTED, so the read is also drained here; see
        # `_drain` for what happens when that is skipped.
        if self._handle:
            kernel32.CancelIoEx(self._handle, self._event)
            self._drain()

    def _drain(self):
        """Wait, bounded, until the pending overlapped read has retired."""
        if not self._pending:
            return True
        transferred = ctypes.c_ulong(0)
        deadline = time.monotonic() + DRAIN_TIMEOUT_S
        while time.monotonic() < deadline:
            if kernel32.GetOverlappedResult(
                    self._handle, ctypes.byref(self._overlapped),
                    ctypes.byref(transferred), False):
                # Retired — with or without data; either way the kernel is done
                # writing into our buffer.
                self._pending = False
                return True
            if ctypes.get_last_error() != ERROR_IO_INPROGRESS:
                # It stopped being "in progress" for another reason; treat it
                # as retired rather than spin to the deadline.
                self._pending = False
                return True
            time.sleep(0.01)
        self._pending = False
        return False

    def run(self):
        """Arm, wait, read, repeat.

        COMPLETION IS POLLED, NOT WAITED ON. Measured on this box
        (`_main/_probe/rdc.out`): `ReadDirectoryChangesW` completes and
        `GetOverlappedResult` returns the bytes within ~0.1-0.3 s of the write,
        but the OVERLAPPED event is NEVER signalled —
        `WaitForSingleObject(event, 5000)` returns 258 (`WAIT_TIMEOUT`) with
        the data already sitting in the buffer. A loop that waits on that event
        therefore blocks forever, never reports an error, and hot reload simply
        never fires — which is exactly what the first version of this file did
        (`ARM burst writes=8 flushes=0 expect=1`, rc=3).

        So completion is `GetOverlappedResult(..., bWait=FALSE)` polled on a
        short `WaitForSingleObject(event, POLL_MS)` tick. The tick is a sleep,
        not a completion signal; the poll is the truth. `_probe/rdc2.out`
        measures three consecutive rounds completing this way.

        The loop uses the watcher's OWN `_overlapped` and `_buf`, never a
        per-iteration local — see `__init__` for why that is a correctness
        requirement rather than a style choice.
        """
        while not self._stopping.is_set():
            kernel32.ResetEvent(self._event)
            self._overlapped.hEvent = self._event
            ok = kernel32.ReadDirectoryChangesW(
                self._handle, self._buf, BUFFER_BYTES, False,
                FILE_NOTIFY_CHANGE_ALL, None,
                ctypes.byref(self._overlapped))
            if not ok:
                code = ctypes.get_last_error()
                self._pending = False
                if code != ERROR_OPERATION_ABORTED and not self._stopping.is_set():
                    self.on_error('READ_FAILED', code)
                break
            self._pending = True
            transferred = ctypes.c_ulong(0)
            completed = False
            while not self._stopping.is_set():
                # The poll IS the completion test. GetOverlappedResult returns
                # TRUE with a non-zero byte count exactly when the buffer
                # holds a full notification record chain.
                if kernel32.GetOverlappedResult(
                        self._handle, ctypes.byref(self._overlapped),
                        ctypes.byref(transferred), False) and transferred.value:
                    completed = True
                    break
                if ctypes.get_last_error() == ERROR_OPERATION_ABORTED \
                        and self._stopping.is_set():
                    break
                # A short sleep. It is a TICK, not a signal: see the docstring.
                kernel32.WaitForSingleObject(self._event, POLL_MS)
            if not completed:
                self._drain()
                break
            self._pending = False
            try:
                for action, name in parse_names(self._buf, transferred.value):
                    self.on_event(action, name)
            except Exception as exc:  # a parse bug must not kill the watcher
                self.on_error('PARSE_FAILED', repr(exc))

    def close(self):
        """Release the handles — only safe once `_drain` has settled the I/O."""
        if not self._stopping.is_set():
            self.stop('close')
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._event:
            kernel32.CloseHandle(self._event)
            self._event = None


class HotReload:
    """Arm the panel and worker directories; call back once per settled burst."""

    def __init__(self, log=None, on_panel_assets_changed=None,
                 on_worker_changed=None, debounce_ms=DEBOUNCE_MS,
                 panel_dir=None, worker_dir=None):
        self.log = log or (lambda line: None)
        self.on_panel_assets_changed = on_panel_assets_changed or (
            lambda files: False)
        self.on_worker_changed = on_worker_changed or (lambda files: False)
        self.debounce_ms = (debounce_ms if isinstance(debounce_ms, (int, float))
                            and debounce_ms >= 0 else DEBOUNCE_MS)
        self.panel_dir = panel_dir or os.path.dirname(os.path.abspath(__file__))
        self.worker_dir = worker_dir or os.path.normpath(
            os.path.join(self.panel_dir, os.pardir, os.pardir, 'worker'))

        self._watchers = []
        self._lock = threading.Lock()
        self._pending = {'panel': set(), 'worker': set()}
        self._events = 0
        self._timer = None
        self._stopped = False
        self.flushes = []          # (kind, files, events) — the receipt

    # -- the watcher's callback ------------------------------------------
    def _on_fs_event(self, kind, action, name):
        if self._stopped:
            return
        base = os.path.basename(name)
        if kind == 'panel':
            accept = base in PANEL_ASSETS
        else:
            accept = base.endswith('.py') and not base.startswith('.')
        if not accept:
            return
        with self._lock:
            self._pending[kind].add(base)
            self._events += 1
            events = self._events
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(self.debounce_ms / 1000.0, self._flush)
            timer.daemon = True
            self._timer = timer
        self.log(f'HOT_RELOAD_EVENT kind={kind} file={base} action={action} '
                 f'events={events} debounce_ms={self.debounce_ms}')
        timer.start()

    def _error(self, kind, error):
        self.log(f'HOT_RELOAD_WATCH_ERROR dir_kind={kind} error={error}')

    # -- the flush ---------------------------------------------------------
    def _flush(self):
        with self._lock:
            panel = sorted(self._pending['panel'])
            worker = sorted(self._pending['worker'])
            events = self._events
            self._pending = {'panel': set(), 'worker': set()}
            self._events = 0
            self._timer = None
        if self._stopped:
            return
        if not panel and not worker:
            return
        for kind, files, callback in (
                ('panel', panel, self.on_panel_assets_changed),
                ('worker', worker, self.on_worker_changed)):
            if not files:
                continue
            self.log(f'HOT_RELOAD_FLUSH kind={kind} '
                     f'files={json.dumps(files)} events={events} '
                     f'debounce_ms={self.debounce_ms}')
            self.flushes.append((kind, list(files), events))
            try:
                callback(files)
            except Exception as exc:
                self.log(f'HOT_RELOAD_{kind.upper()}_THREW '
                         f'files={json.dumps(files)} error={exc!r}')

    # -- lifecycle ---------------------------------------------------------
    def _arm_dir(self, directory, kind):
        watcher = DirWatcher(
            directory,
            lambda action, name: self._on_fs_event(kind, action, name),
            on_error=lambda err, code: self._error(
                f'{kind}:{directory}:{err}', code))
        if not watcher.start():
            watcher.close()
            self.log(f'HOT_RELOAD_WATCH_FAILED kind={kind} '
                     f'dir={json.dumps(directory)}')
            return False
        self._watchers.append(watcher)
        self.log(f'HOT_RELOAD_WATCH kind={kind} '
                 f'dir={json.dumps(directory)} debounce_ms={self.debounce_ms}')
        return True

    def start(self):
        if self._stopped:
            return False
        armed = 0
        if os.path.isdir(self.panel_dir):
            armed += 1 if self._arm_dir(self.panel_dir, 'panel') else 0
        else:
            self.log(f'HOT_RELOAD_WATCH_FAILED kind=panel '
                     f'dir={json.dumps(self.panel_dir)} reason=missing')
        if os.path.isdir(self.worker_dir):
            armed += 1 if self._arm_dir(self.worker_dir, 'worker') else 0
        else:
            self.log(f'HOT_RELOAD_WATCH_FAILED kind=worker '
                     f'dir={json.dumps(self.worker_dir)} reason=missing')
        self.log(f'HOT_RELOAD_ENABLED watchers={len(self._watchers)} '
                 f'debounce_ms={self.debounce_ms}')
        return armed == 2

    def stop(self, reason='stop'):
        if self._stopped:
            return False
        self._stopped = True
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            dropped = self._events
            self._pending = {'panel': set(), 'worker': set()}
            self._events = 0
        for watcher in self._watchers:
            watcher.stop(reason)
        for watcher in self._watchers:
            watcher.join(3)
            watcher.close()
        self._watchers = []
        self.log(f'HOT_RELOAD_STOPPED reason={reason} watchers=0 '
                 f'droppedUnsettledEvents={dropped}')
        return True


# ===========================================================================
# selftest — the RED-capable half, runnable with no WebView2 and no window
# ===========================================================================


def selftest() -> int:
    """Drive real files through a real watcher and assert the contract.

    Four arms, each able to print RED:
      1. burst      8 rapid writes to panel.css  -> EXACTLY ONE flush
      2. single     one write                    -> EXACTLY ONE flush
      3. rename     write-temp + rename over     -> EXACTLY ONE flush, and the
                    watcher is STILL ALIVE afterwards (the file-watch bug)
      4. rename x3  three rename-overs in a row  -> still alive, still flushing
    Plus: a worker .py write produces a `worker` flush, and a non-asset write
    produces NONE.
    """
    root = tempfile.mkdtemp(prefix='sotto-hotreload-')
    panel_dir = os.path.join(root, 'panel')
    worker_dir = os.path.join(root, 'worker')
    os.makedirs(panel_dir)
    os.makedirs(worker_dir)
    css = os.path.join(panel_dir, 'panel.css')
    worker_py = os.path.join(worker_dir, 'sotto_worker.py')
    with open(css, 'w', encoding='utf-8') as fh:
        fh.write('/* seed */\n')
    with open(worker_py, 'w', encoding='utf-8') as fh:
        fh.write('# seed\n')

    lines = []

    def log(line):
        lines.append(line)
        print(f'selftest: {line}', flush=True)

    hr = HotReload(log=log, on_panel_assets_changed=lambda f: True,
                   on_worker_changed=lambda f: True,
                   debounce_ms=250, panel_dir=panel_dir, worker_dir=worker_dir)
    rc = 0
    if not hr.start():
        log('VERDICT arm=start watchers=2 got=0-1')
        return 3

    def flushes(kind):
        return [f for f in hr.flushes if f[0] == kind]

    def settle(seconds=1.5):
        time.sleep(seconds)

    # arm 1 — a burst is ONE call, not eight
    hr.flushes.clear()
    for i in range(8):
        with open(css, 'a', encoding='utf-8') as fh:
            fh.write(f'/* burst {i} */\n')
        time.sleep(0.03)
    settle()
    got = len(flushes('panel'))
    log(f'ARM burst writes=8 flushes={got} expect=1')
    if got != 1:
        rc = 3

    # arm 2 — a single write is still one call
    hr.flushes.clear()
    with open(css, 'a', encoding='utf-8') as fh:
        fh.write('/* single */\n')
    settle()
    got = len(flushes('panel'))
    log(f'ARM single writes=1 flushes={got} expect=1')
    if got != 1:
        rc = 3

    # arm 3 — write-temp + rename over, the case a FILE watch dies on
    hr.flushes.clear()
    for i in range(3):
        tmp = os.path.join(panel_dir, 'panel.css.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(f'/* renamed {i} */\n')
        os.replace(tmp, css)
        time.sleep(0.05)
    settle()
    got = len(flushes('panel'))
    log(f'ARM rename renames=3 flushes={got} expect=1 alive_after_rename='
        f'{str(hr._watchers and hr._watchers[0].is_alive()).lower()}')
    if got != 1:
        rc = 3

    # arm 4 — the watcher survives the whole sequence, and still fires
    hr.flushes.clear()
    with open(css, 'a', encoding='utf-8') as fh:
        fh.write('/* after rename */\n')
    settle()
    got = len(flushes('panel'))
    log(f'ARM alive_after flushes={got} expect=1')
    if got != 1:
        rc = 3

    # arm 5 — the worker directory drives its own kind
    hr.flushes.clear()
    with open(worker_py, 'a', encoding='utf-8') as fh:
        fh.write('# touched\n')
    settle()
    got = len(flushes('worker'))
    log(f'ARM worker flushes={got} expect=1')
    if got != 1:
        rc = 3

    # arm 6 — a file that is not an asset produces NOTHING
    hr.flushes.clear()
    with open(os.path.join(panel_dir, 'notes.txt'), 'w',
              encoding='utf-8') as fh:
        fh.write('not an asset\n')
    settle(0.8)
    got = len(hr.flushes)
    log(f'ARM non_asset flushes={got} expect=0')
    if got != 0:
        rc = 3

    hr.stop('selftest-done')
    shutil.rmtree(root, ignore_errors=True)
    log(f'SELFTEST rc={rc}')
    return rc


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='sotto-hot-reload',
        description='Directory watcher + debounce for the Sotto WebView2 shell.')
    parser.add_argument('--selftest', action='store_true',
                        help='drive real files through the watcher and assert '
                             'the burst/single/rename/alive contract')
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    parser.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())