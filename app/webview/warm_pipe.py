"""WARM PIPE -- the Win32 primitives the warm engine and the shell share.

WHY THIS FILE EXISTS. The warm engine (``app/webview/warm_engine.py``) is a
process the SHELL DID NOT SPAWN: it is created by Task Scheduler, it outlives
the shell, and the shell may only *attach* to it. The design
(``state/design/warm-worker-20261104.md``, INV-1/INV-2) makes "at most one
loader" a property of two kernel objects -- a named pipe created with
``FILE_FLAG_FIRST_PIPE_INSTANCE`` and a named mutex held for the process
lifetime -- so the two halves of the app must agree, byte for byte, on the
names and on the error codes. They therefore share ONE implementation, this
file, instead of each carrying its own copy of the Win32 dance.

NOTHING HERE STARTS A PROCESS, OPENS A DEVICE, OR TOUCHES A WINDOW. It creates
kernel objects, opens handles, reads and writes bytes. That is what makes the
oracle able to drive it headless.

ERROR CODES ARE THE CONTRACT. ``FILE_FLAG_FIRST_PIPE_INSTANCE`` reports a
second instance as ``ERROR_ACCESS_DENIED`` (5), not as "already exists"; a
mutex that already exists is a SUCCESSFUL ``CreateMutexW`` with
``ERROR_ALREADY_EXISTS`` (183). Both are named here so neither file has to
remember the asymmetry.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import time

# ── constants ────────────────────────────────────────────────────────────────
SCHEMA = "sotto.warm/1"

DEFAULT_PIPE_PREFIX = r"\\.\pipe\sotto-warm-"
DEFAULT_MUTEX_PREFIX = r"Local\SottoWarmEngine."

PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

ERROR_FILE_NOT_FOUND = 2
ERROR_ACCESS_DENIED = 5
ERROR_BROKEN_PIPE = 109
ERROR_ALREADY_EXISTS = 183
ERROR_PIPE_BUSY = 231
ERROR_PIPE_CONNECTED = 535
ERROR_SEM_TIMEOUT = 121
ERROR_NO_DATA = 232

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_k32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None


def _declare():
    """PROTOTYPES -- without them ctypes answers WRONG, not slowly.

    Measured by oracle arm 13 (2026-11-04): with no ``restype`` a HANDLE is a
    C ``int``, so a REFUSED ``CreateNamedPipeW`` came back as ``-1`` -- which is
    not ``INVALID_HANDLE_VALUE`` (``0xFFFFFFFFFFFFFFFF``) and was therefore read
    as a VALID handle. Two engines on one pipe name both logged
    ``WARM_PIPE_READY``: the kernel's ``FILE_FLAG_FIRST_PIPE_INSTANCE`` was
    working the whole time, this module was misreading its answer.
    """
    if _k32 is None:
        return
    h, d, lp = wt.HANDLE, wt.DWORD, wt.LPVOID
    _k32.CreateNamedPipeW.argtypes = [wt.LPCWSTR, d, d, d, d, d, d, lp]
    _k32.CreateNamedPipeW.restype = h
    _k32.ConnectNamedPipe.argtypes = [h, lp]
    _k32.ConnectNamedPipe.restype = wt.BOOL
    _k32.DisconnectNamedPipe.argtypes = [h]
    _k32.DisconnectNamedPipe.restype = wt.BOOL
    _k32.WaitNamedPipeW.argtypes = [wt.LPCWSTR, d]
    _k32.WaitNamedPipeW.restype = wt.BOOL
    _k32.CreateFileW.argtypes = [wt.LPCWSTR, d, d, lp, d, d, h]
    _k32.CreateFileW.restype = h
    _k32.CloseHandle.argtypes = [h]
    _k32.CloseHandle.restype = wt.BOOL
    _k32.WriteFile.argtypes = [h, lp, d, ctypes.POINTER(d), lp]
    _k32.WriteFile.restype = wt.BOOL
    _k32.ReadFile.argtypes = [h, lp, d, ctypes.POINTER(d), lp]
    _k32.ReadFile.restype = wt.BOOL
    _k32.PeekNamedPipe.argtypes = [h, lp, d, ctypes.POINTER(d),
                                   ctypes.POINTER(d), ctypes.POINTER(d)]
    _k32.PeekNamedPipe.restype = wt.BOOL
    _k32.CreateMutexW.argtypes = [lp, wt.BOOL, wt.LPCWSTR]
    _k32.CreateMutexW.restype = h
    _k32.ProcessIdToSessionId.argtypes = [d, ctypes.POINTER(d)]
    _k32.ProcessIdToSessionId.restype = wt.BOOL
    _k32.OpenThread.argtypes = [d, wt.BOOL, d]
    _k32.OpenThread.restype = h
    _k32.CancelSynchronousIo.argtypes = [h]
    _k32.CancelSynchronousIo.restype = wt.BOOL


_declare()

#: The shared size of both directions. The protocol is JSONL; a caption line is
#: well under 4 KB and 64 KB is the default the Windows samples use.
PIPE_BUFFER = 65536


# ── naming ───────────────────────────────────────────────────────────────────
def model_key(model_dir):
    """The weights identity that travels in the pipe and mutex names.

    BASENAME + the first 12 hex of ``genai_config.json``: the basename names the
    export ("nemotron-3.5-asr-ptbr-onnx-int4") and the digest makes a re-export
    under the SAME directory name a different engine, which is the case the
    design's freshness rule (F1) cares about.
    """
    base = os.path.basename(os.path.normpath(model_dir or "")) or "model"
    digest = ""
    cfg = os.path.join(model_dir, "genai_config.json") if model_dir else ""
    try:
        with open(cfg, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()[:12]
    except OSError:
        digest = "noconfig"
    return "%s-%s" % (base, digest)


def session_id():
    """The console/session the pipe belongs to. Two RDP sessions are two engines.

    ``ProcessIdToSessionId`` is the API the design names ("two sessions (RDP) is
    correct there", F10). Falls back to the ``SESSIONNAME`` env on a box where
    the call is unavailable, and to ``0`` as the last resort -- and the fallback
    is a *name*, never a permission.
    """
    if os.name == "nt":
        try:
            sid = wt.DWORD(0)
            if _k32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid)):
                return int(sid.value)
        except Exception:  # noqa: BLE001 -- a fallback name, not a decision
            pass
    return os.environ.get("SESSIONNAME") or "0"


def pipe_name(key, session=None, prefix=DEFAULT_PIPE_PREFIX):
    return "%s%s-%s" % (prefix, session if session is not None else session_id(), key)


def mutex_name(key, session=None, prefix=DEFAULT_MUTEX_PREFIX):
    return "%s%s.%s" % (prefix, session if session is not None else session_id(), key)


# ── security ─────────────────────────────────────────────────────────────────
def owner_sddl():
    """A DACL that grants THIS user (and SYSTEM) the pipe, pinned rather than inherited.

    INV-2's price: the engine outlives the shell, so the default DACL of the
    creating token is not a policy -- it is whatever the launcher had. The SDDL
    is measured from the token (owner SID) and granted GENERIC_ALL to that SID
    plus LocalSystem. If the SID cannot be read the function returns ``None`` and
    ``create_first_instance`` falls back to the inherited DACL: a pipe that
    cannot be created is worse than a pipe with the default DACL, and the
    degradation is reported by the caller.
    """
    if os.name != "nt":
        return None
    try:
        import win32security  # pywin32 is present on this box
        import win32api

        sid = win32security.GetTokenInformation(
            win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32security.TOKEN_QUERY),
            win32security.TokenUser)[0]
        text = win32security.ConvertSidToStringSid(sid)
        return "D:P(A;;GA;;;%s)(A;;GA;;;SY)" % text
    except Exception:  # noqa: BLE001 -- no pywin32 / no windowstation: inherit
        return None


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("nLength", wt.DWORD),
                ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", wt.BOOL)]


def _security_attributes(sddl):
    """-> (SECURITY_ATTRIBUTES, descriptor) or (None, None).

    The descriptor is returned so the CALLER keeps it alive while
    ``CreateNamedPipeW`` reads it; a Python object collected here would leave the
    API reading freed memory.
    """
    if not sddl or os.name != "nt":
        return None, None
    try:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        desc = ctypes.c_void_p()
        ok = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            ctypes.c_wchar_p(sddl), ctypes.c_ulong(1), ctypes.byref(desc), None)
        if not ok:
            return None, None
        attrs = _SecurityAttributes()
        attrs.nLength = ctypes.sizeof(_SecurityAttributes)
        attrs.lpSecurityDescriptor = desc
        attrs.bInheritHandle = False
        return attrs, desc
    except Exception:  # noqa: BLE001
        return None, None


# ── server ───────────────────────────────────────────────────────────────────
def create_first_instance(name, sddl=None, instances=1):
    """The SINGLE-instance server end.

    Returns ``(handle, reason)``: ``reason`` is ``"ok"`` or one of
    ``"twin"`` (``ERROR_ACCESS_DENIED`` == an instance already exists),
    ``"unavailable"`` (not Windows / no kernel32), ``"error:<n>"``.

    ``FILE_FLAG_FIRST_PIPE_INSTANCE`` is the first of the four twin locks and it
    is the one with a kernel guarantee: the second creator cannot get a handle,
    it does not race, and the design makes that loser EXIT instead of retrying.
    """
    if os.name != "nt" or _k32 is None:
        return None, "unavailable"
    attrs, desc = _security_attributes(sddl)
    mode = (PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE)
    pipe_mode = PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS
    handle = _k32.CreateNamedPipeW(
        ctypes.c_wchar_p(name),
        wt.DWORD(mode),
        wt.DWORD(pipe_mode),
        wt.DWORD(max(1, int(instances))),
        wt.DWORD(PIPE_BUFFER),
        wt.DWORD(PIPE_BUFFER),
        wt.DWORD(0),
        ctypes.byref(attrs) if attrs is not None else None,
    )
    err = ctypes.get_last_error()
    # `desc` (the security descriptor) must outlive the call above; it does, by
    # this local reference, until the function returns.
    _ = desc
    if handle and handle != INVALID_HANDLE_VALUE:
        return handle, "ok"
    if err in (ERROR_ACCESS_DENIED, ERROR_PIPE_BUSY):
        # MEASURED (oracle arm 13, 2026-11-04): the refusal of a second
        # first-instance creator is ERROR_PIPE_BUSY (231) while the first
        # instance waits for a client, and ERROR_ACCESS_DENIED (5) once a client
        # is attached. Both mean "an instance exists"; neither means "retry".
        return None, "twin"
    return None, "error:%d" % err


def connect(handle):
    """Wait for the client. -> True if a client is connected."""
    if handle is None:
        return False
    ok = _k32.ConnectNamedPipe(handle, None)
    if ok:
        return True
    err = ctypes.get_last_error()
    return err in (ERROR_PIPE_CONNECTED, ERROR_ALREADY_EXISTS)


def disconnect(handle):
    if handle is None:
        return
    try:
        _k32.DisconnectNamedPipe(handle)
    except Exception:  # noqa: BLE001
        pass


# ── client ───────────────────────────────────────────────────────────────────
def wait_pipe(name, timeout_ms):
    if os.name != "nt" or _k32 is None:
        return False
    return bool(_k32.WaitNamedPipeW(ctypes.c_wchar_p(name), wt.DWORD(int(timeout_ms))))


def open_client(name, timeout_ms=500):
    """CreateFile on the server pipe, bounded. -> (handle, reason).

    ``ERROR_FILE_NOT_FOUND`` = absent (no engine); ``ERROR_PIPE_BUSY`` = an
    engine owns the pipe but is not accepting yet; both are *facts*, not errors,
    and the caller's fallback is the untouched cold path.
    """
    if os.name != "nt" or _k32 is None:
        return None, "unavailable"
    deadline = time.monotonic() + max(0, timeout_ms) / 1000.0
    if not wait_pipe(name, timeout_ms):
        err = ctypes.get_last_error()
        if err == ERROR_FILE_NOT_FOUND:
            return None, "absent"
        if err == ERROR_SEM_TIMEOUT:
            return None, "busy"
    while True:
        handle = _k32.CreateFileW(
            ctypes.c_wchar_p(name),
            wt.DWORD(GENERIC_READ | GENERIC_WRITE),
            wt.DWORD(0),
            None,
            wt.DWORD(OPEN_EXISTING),
            wt.DWORD(0),
            None,
        )
        if handle and handle != INVALID_HANDLE_VALUE:
            return handle, "ok"
        err = ctypes.get_last_error()
        if err in (ERROR_PIPE_BUSY, ERROR_FILE_NOT_FOUND) and time.monotonic() < deadline:
            wait_pipe(name, 50)
            continue
        if err == ERROR_FILE_NOT_FOUND:
            return None, "absent"
        if err == ERROR_PIPE_BUSY:
            return None, "busy"
        if err == ERROR_ACCESS_DENIED:
            return None, "access-denied"
        return None, "error:%d" % err


def cancel_sync_io(thread_id):
    """Abort the synchronous I/O a thread is blocked in (the accept loop's
    ``ConnectNamedPipe``).

    Measured by oracle arm 19: ``CloseHandle`` on a pipe whose OTHER thread is
    inside ``ConnectNamedPipe`` BLOCKS -- the kernel waits for the pending
    operation -- so the engine hung in shutdown with its own pid file still on
    disk. Cancelling the wait first is what makes shutdown bounded.
    """
    if os.name != "nt" or _k32 is None or not thread_id:
        return False
    #: THREAD_TERMINATE is the access CancelSynchronousIo documents.
    handle = _k32.OpenThread(wt.DWORD(0x0001), False, wt.DWORD(int(thread_id)))
    if not handle:
        return False
    try:
        return bool(_k32.CancelSynchronousIo(handle))
    finally:
        _k32.CloseHandle(handle)


def close_handle(handle):
    if handle is None:
        return
    try:
        _k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        pass


# ── byte transport ───────────────────────────────────────────────────────────
class PipeConn:
    """One connected end: ``send(bytes)``, ``recv(max)``, ``readline(deadline)``.

    Reads are driven by ``PeekNamedPipe`` + ``ReadFile`` rather than by a Python
    file object, because BOTH ends need a DEADLINE (the shell's attach is 500 ms)
    and a blocking ``readline`` cannot carry one.
    """

    def __init__(self, handle):
        self.handle = handle
        self._buf = b""
        self.closed = False

    def send(self, data):
        if self.closed or self.handle is None:
            raise OSError(ERROR_BROKEN_PIPE, "pipe closed")
        written = wt.DWORD(0)
        payload = data if isinstance(data, (bytes, bytearray)) else data.encode("utf-8")
        ok = _k32.WriteFile(self.handle, ctypes.cast(ctypes.c_char_p(payload),
                                                     ctypes.c_void_p),
                            wt.DWORD(len(payload)), ctypes.byref(written), None)
        if not ok:
            err = ctypes.get_last_error()
            self.closed = True
            raise OSError(err, "WriteFile failed")
        return int(written.value)

    def send_line(self, text):
        return self.send((text.rstrip("\n") + "\n").encode("utf-8"))

    def _peek(self):
        if self.handle is None or self.closed:
            return 0
        avail = wt.DWORD(0)
        ok = _k32.PeekNamedPipe(self.handle, None, wt.DWORD(0), None,
                                ctypes.byref(avail), None)
        if not ok:
            self.closed = True
            return 0
        return int(avail.value)

    def recv(self, max_bytes=65536, timeout_s=None):
        """One ReadFile. Returns b'' on EOF; raises TimeoutError on the deadline."""
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while True:
            if self._peek() > 0:
                chunk = ctypes.create_string_buffer(max_bytes)
                got = wt.DWORD(0)
                ok = _k32.ReadFile(self.handle, ctypes.cast(chunk, ctypes.c_void_p),
                                   wt.DWORD(max_bytes), ctypes.byref(got), None)
                if not ok:
                    err = ctypes.get_last_error()
                    if err in (ERROR_BROKEN_PIPE, ERROR_NO_DATA):
                        self.closed = True
                        return b""
                    raise OSError(err, "ReadFile failed")
                if got.value == 0:
                    self.closed = True
                    return b""
                return chunk.raw[: int(got.value)]
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("pipe read deadline")
            if self.closed:
                return b""
            time.sleep(0.005)

    def readline(self, timeout_s=None):
        """A whole line (without CRLF), or ``None`` on deadline/EOF.

        The buffer is kept on the object so a byte that straddled a ReadFile is
        not lost; the protocol is line-oriented and a lost half-line would be a
        lost caption.
        """
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line, self._buf = self._buf[:nl], self._buf[nl + 1:]
                return line.rstrip(b"\r").decode("utf-8", "replace")
            if self.closed:
                return None
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining == 0:
                return None
            try:
                chunk = self.recv(timeout_s=remaining if remaining is not None else 0.1)
            except TimeoutError:
                return None
            if chunk == b"":
                return None
            self._buf += chunk

    def close(self):
        self.closed = True
        close_handle(self.handle)
        self.handle = None


# ── mutex ────────────────────────────────────────────────────────────────────
def create_mutex(name):
    """-> (handle, created). ``created=False`` means another process holds it."""
    if os.name != "nt" or _k32 is None:
        return None, True
    handle = _k32.CreateMutexW(None, wt.BOOL(False), ctypes.c_wchar_p(name))
    err = ctypes.get_last_error()
    if not handle:
        return None, False
    if err == ERROR_ALREADY_EXISTS:
        # Our handle is still a valid open handle to the EXISTING mutex; close it
        # and say "not ours". Holding it here would keep the object alive past
        # the twin's exit.
        close_handle(handle)
        return None, False
    return handle, True


def mutex_exists(name):
    """A 0-ms acquire probe: *"an engine exists"* vs *"an engine exists and is wedged"*.

    ``CreateMutexW`` either creates (no engine) or opens the existing object. On
    Windows a mutex is released by the kernel when its owner dies, so "exists"
    is a fact about a LIVE process, not about a file that may be stale.
    """
    if os.name != "nt" or _k32 is None:
        return False
    handle = _k32.CreateMutexW(None, wt.BOOL(False), ctypes.c_wchar_p(name))
    err = ctypes.get_last_error()
    if not handle:
        return False
    exists = err == ERROR_ALREADY_EXISTS
    close_handle(handle)
    return exists


def release_mutex(handle):
    close_handle(handle)
