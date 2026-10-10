"""THE ENGINE PROCESS -- single supervisor, owner of the ring, parent of capture.

WHAT THIS IS
    One process that owns (a) the capture child, (b) the ASR side, (c) the ring
    of the last 100 events, and (d) the durable SQLite spine. The UI is a CHILD
    that attaches and detaches at any time: detaching never stops recording, and
    a reconnecting UI is made consistent by REPLAYING the retained ring from the
    event id it last saw.

WHAT THIS DELIBERATELY IS NOT
    * It is NOT the long-term Rust core. This Python Engine is the shippable
      supervisor for the P0 milestone; the divergences are listed in the receipt
      (accepted, not accidental).
    * It does NOT touch a capture device. The capture child is either the real
      C++ binary (src/capture/main.cpp's --cut-session mode) or, when that path
      is unavailable on this host, the documented stub (stub_capture.py). STUB
      arms are labelled STUB everywhere they surface.
    * It does NOT require WGC. Every arm here runs the capture child headless
      from a h264 source (real) or from a generated tone (stub) -- no screen
      capture, no window (docs/design-notes/03-engine-ipc.md 6).

EXIT CODES
    0  clean shutdown (keyboard interrupt, --seconds elapsed, or "bye")
    2  usage / configuration refused
    3  the capture side refused to arm: NO encoder (LAW 6). A dead hotkey that
       says why beats a live hotkey that does nothing.
    4  a second Engine instance refused: the ring lock is already held.
    5  fatal internal error.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import protocol
from protocol import make, parse_line, ProtocolError
from store import Spine
from capture_child import CaptureChild, CaptureChildError, CREATE_NO_WINDOW
from asr_worker import AsrWorker

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NVENC = 3
EXIT_SECOND = 4
EXIT_FATAL = 5

RING_CAPACITY = 100
ENGINE_VERSION = 1
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")

# How long the Engine will wait, AT SHUTDOWN ONLY, for an ASR result that is
# already in flight.  The clip is closed and committed by then, so a stalled ASR
# child cannot hold the Engine hostage; it is killed by its own timeout first.
ASR_EXIT_GRACE_S = 12.0

# How long the Engine waits for its UI socket to be BOUND (the bind happens on
# the server thread, so the listening port is not known when start() returns).
# Bounded on purpose: a UI door that never listens is a fatal Engine fault, not
# a reason to hold the recording hostage.
UI_BIND_WAIT_S = 5.0


class EngineFatal(Exception):
    def __init__(self, code, msg):
        super(EngineFatal, self).__init__(msg)
        self.code = code
        self.msg = msg


def now_ms():
    return int(time.time() * 1000)


def split_cmd_line(text):
    """Split a command line WITHOUT eating Windows backslashes.

    shlex.split(posix=True) treats backslash as an escape character, so the
    native path in a --asr-cmd / --capture-cmd string was handed to the child
    with every separator stripped -- MEASURED in the kept workdir of
    ARM-C/stall: the ASR child died rc=2 with
    "can't open file H:\\sotto-wtengproc_movedaireplaysrcenginestub_asr.py".
    posix=False keeps the backslashes and the quoting, so the quoting is
    stripped here, by hand, once.
    """
    parts = []
    try:
        raw = shlex.split(text, posix=False)
    except ValueError:
        raw = text.split()
    for p in raw:
        p = p.strip()
        if len(p) >= 2 and p[0] == p[-1] and p[0] in ("'", '"'):
            p = p[1:-1]
        if p:
            parts.append(p)
    return parts


def wav_frames(path):
    """Sample FRAMES in a PCM WAV file, read from the file itself.

    A clip whose bytes are already on disk is described by its own header, not
    by a promise: this is what the shutdown reconcile uses to fill the frames
    column for the clip the child closed at stdin EOF, where no request is
    ever answered any more.  Returns 0 for anything that is not a PCM WAV and
    never raises -- a file that cannot be read is a diagnostic, not a crash.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(256)
            size = os.path.getsize(path)
    except OSError:
        return 0
    if len(head) < 12 or head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
        return 0
    pos = 12
    channels = 1
    bits = 16
    data_bytes = None
    data_start = None
    while pos + 8 <= len(head):
        cid = head[pos:pos + 4]
        sz = int.from_bytes(head[pos + 4:pos + 8], "little")
        body = pos + 8
        if cid == b"fmt " and body + 16 <= len(head):
            channels = int.from_bytes(head[body + 2:body + 4], "little") or 1
            bits = int.from_bytes(head[body + 14:body + 16], "little") or 16
        elif cid == b"data":
            data_bytes = sz
            data_start = body
            break
        pos = body + sz + (sz & 1)
    if data_start is None or channels <= 0 or bits < 8:
        return 0
    if data_bytes is None or data_bytes < 0 or data_bytes > size - data_start:
        data_bytes = max(0, size - data_start)   # a streaming size field lies
    per_frame = channels * (bits // 8)
    if per_frame <= 0:
        return 0
    return data_bytes // per_frame


# --------------------------------------------------------------------------
# ring: the engine-owned, bounded, replay-by-since_id event log
# --------------------------------------------------------------------------
class Ring(object):
    def __init__(self, capacity=RING_CAPACITY):
        self.capacity = int(capacity)
        self.items = collections.deque(maxlen=self.capacity)
        self.dropped = 0
        self.next_id = 1
        self.lock = threading.Lock()

    def append(self, type_, payload):
        with self.lock:
            if len(self.items) == self.capacity:
                self.dropped += 1
            env = make(type_, payload, id_=self.next_id)
            self.next_id += 1
            self.items.append(env)
            return env

    def since(self, since_id):
        """Events with id > since_id plus the oldest id still retained."""
        with self.lock:
            evs = [dict(e) for e in self.items if e["id"] > since_id]
            oldest = self.items[0]["id"] if self.items else 0
            newest = self.items[-1]["id"] if self.items else 0
        return evs, oldest, newest

    def snapshot(self):
        with self.lock:
            return {
                "size": len(self.items),
                "capacity": self.capacity,
                "dropped": self.dropped,
                "oldest_id": self.items[0]["id"] if self.items else 0,
                "newest_id": self.items[-1]["id"] if self.items else 0,
                "next_id": self.next_id,
            }


# --------------------------------------------------------------------------
# UI side: a bounded, per-connection queue with its own writer thread
# --------------------------------------------------------------------------
class UiConnection(object):
    def __init__(self, sock, peer, ring):
        self.sock = sock
        self.peer = peer
        self.ring = ring
        # The peer address is NOT an identity: a UI that reconnects fast
        # enough gets its predecessor's ephemeral port back, and a hub keyed by
        # "ip:port" would then have add(new) OVERWRITE the live entry and
        # remove(old) EVICT the new connection -- the reconnect would be answered
        # with silence while a perfectly healthy Engine cut clips.  Measured
        # 2026-10-09 (ARM-B, repro5).  The serial is assigned by the hub, under
        # its own lock, in add().
        self.id = None
        self.attached = False
        self.since = 0
        self.alive = True
        self.sent = 0
        self.replayed = 0
        self.dropped = 0
        self.overflow = False
        self.connected_at = time.time()
        self.ready = threading.Event()
        self.q = collections.deque(maxlen=256)

    # (offers go through UiHub.offer, which counts the drop)


class UiHub(object):
    def __init__(self, diag):
        self.diag = diag
        self.lock = threading.Lock()
        self.conns = {}
        self.serial = 0

    def add(self, conn):
        with self.lock:
            self.serial += 1
            conn.id = "%s:%d#%d" % (conn.peer[0], conn.peer[1], self.serial)
            self.conns[conn.id] = conn

    def remove(self, conn):
        with self.lock:
            self.conns.pop(conn.id, None)

    def count(self, attached_only=False):
        with self.lock:
            if attached_only:
                return sum(1 for c in self.conns.values() if c.attached)
            return len(self.conns)

    def publish(self, env):
        self.publish_now(env)

    def publish_now(self, env):
        """Deliver to attached UIs WITHOUT ring retention.

        health is a pollable state (the status command and the status file carry it
        too); retaining it in the ring would EVICT clip_written events and make a
        reconnecting UI's replay worthless.  Only real history enters the ring.
        """
        with self.lock:
            conns = list(self.conns.values())
        for c in conns:
            if not c.attached:
                continue
            UiHub.offer(c, ("env", env))

    @staticmethod
    def offer(conn, item):
        """Push to a bounded per-UI queue.  A UI that cannot keep up LOSES EVENTS
        (counted, visible in health) -- it never applies backpressure to the ring."""
        if len(conn.q) >= conn.q.maxlen:
            conn.dropped += 1
            conn.overflow = True
            return False
        conn.q.append(item)
        return True

    def shutdown(self):
        with self.lock:
            conns = list(self.conns.values())
        for c in conns:
            c.alive = False
            try:
                c.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass


class UiServer(threading.Thread):
    def __init__(self, engine, host="127.0.0.1", port=0):
        super(UiServer, self).__init__(name="ui-server", daemon=True)
        self.engine = engine
        self.host = host
        self.port = port
        self.sock = None
        self._stop = threading.Event()
        self.error = ""

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
        except OSError as exc:
            self.error = "cannot bind %s:%s: %s" % (self.host, self.port, exc)
            return
        s.listen(8)
        self.port = s.getsockname()[1]
        self.sock = s
        s.settimeout(0.25)
        while not self._stop.is_set():
            try:
                client, peer = s.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            client.settimeout(None)
            try:
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            threading.Thread(target=self._serve, args=(client, peer), daemon=True).start()
        try:
            s.close()
        except Exception:
            pass

    def stop(self):
        self._stop.set()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _serve(self, client, peer):
        conn = UiConnection(client, peer, self.engine.ring)
        self.engine.hub.add(conn)
        writer = threading.Thread(target=self.engine.ui_writer, args=(conn,), daemon=True)
        writer.start()
        why = None
        try:
            f = client.makefile("r", encoding="utf-8", errors="replace")
            for line in f:
                if not conn.alive:
                    why = "conn-not-alive"
                    break
                line = line.rstrip("\r\n")
                if not line:
                    continue
                try:
                    env = parse_line(line, where="ui")
                    self.engine.ui_command(conn, env)
                except ProtocolError as exc:
                    # A malformed line is a DIAGNOSTIC on this Engine -- it is
                    # answered with an error event, never with a traceback, and
                    # the connection survives.
                    self.engine.diag("ui %s sent a malformed line: %s" % (conn.id, exc))
                    conn.q.append(("env", make("error", {"reply_to": None, "error": str(exc)})))
        except OSError as exc:
            why = "read-failed %s" % (exc,)
            self.engine.diag("ui %s read failed: %s" % (conn.id, exc))
        finally:
            # ARM-B instrument 2026-10-09: the reader thread is the only one that
            # can stop a connection being served, and it used to leave without a
            # word.  why=None means the client's socket reached EOF.
            self.engine.diag("ui %s READER-EXIT sent=%d q=%d attached=%s why=%s"
                             % (conn.id, conn.sent, len(conn.q), conn.attached,
                                why or "eof"))
            conn.alive = False
            self.engine.hub.remove(conn)
            try:
                client.close()
            except Exception:
                pass


# --------------------------------------------------------------------------
# the ring lock: one Engine, one owner of the endpoint and the ring file
# --------------------------------------------------------------------------
class RingLock(object):
    """Exclusive, self-cleaning lock file holding pid + boot time."""

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.payload = None

    @staticmethod
    def pid_alive(pid):
        """Is that pid a LIVE process?  On Windows the POSIX answer does harm.

        MEASURED 2026-10-09 on this host (CPython 3.11.8): os.kill(pid, 0) against
        a LIVE process TERMINATES it.  The victim was a 12 s sleep; it died after
        3 s with exit code 0 -- a CLEAN-looking exit -- and the call itself raised
        SystemError('<built-in function kill> returned a result with an exception
        set').  Two consequences, both measured in the gate: a liveness check that
        murders its subject (a second Engine KILLED the first instead of merely
        failing to refuse it), and an exception no except clause here caught, so
        the refusal crashed out as exit 5 instead of exit 4.

        Win32 answers the question without touching the process: OpenProcess with
        SYNCHRONIZE tells us it EXISTS, WaitForSingleObject(0) tells us it has NOT
        exited yet.  Any probe failure answers "alive" -- the ring is never STOLEN
        on a hunch, which is the law this class exists to hold.
        """
        if not pid or pid <= 0:
            return False
        if pid == os.getpid():
            return True
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            SYNCHRONIZE = 0x00100000
            WAIT_TIMEOUT = 0x00000102
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
            if not handle:
                return kernel32.GetLastError() == 5  # ERROR_ACCESS_DENIED: it exists
            try:
                return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True

    def acquire(self):
        payload = {
            "pid": os.getpid(),
            "boot_ts": time.time(),
            "argv": sys.argv,
            "workdir": os.getcwd(),
            "start_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        for attempt in (0, 1):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
                os.write(self.fd, json.dumps(payload, indent=1).encode("utf-8"))
                os.fsync(self.fd)
                self.payload = payload
                return True
            except FileExistsError:
                other = self._read()
                if self.pid_alive(other.get("pid")):
                    return False  # a LIVE Engine owns the ring: refuse, never steal
                # a DEAD pid left the file behind: crash recovery, done loudly
                sys.stderr.write(
                    "ENGINE-RINGLOCK-STALE pid=%s boot_ts=%s -- stealing (owner is dead)\n"
                    % (other.get("pid"), other.get("boot_ts")))
                sys.stderr.flush()
                try:
                    os.unlink(self.path)
                except OSError:
                    return False
            except OSError as exc:
                sys.stderr.write("ENGINE-RINGLOCK-ERROR path=%s err=%s\n" % (self.path, exc))
                sys.stderr.flush()
                return False
        return False

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.loads(fh.read() or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def release(self):
        if self.fd is None:
            return
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass
        self.fd = None


# --------------------------------------------------------------------------
# THE ENGINE
# --------------------------------------------------------------------------
class Engine(object):

    # -- construction / CLI ------------------------------------------------
    def __init__(self, argv=None):
        self.args = self.parse_args(argv)
        self.stop = threading.Event()
        self.stop_reason = "unknown"
        self.exit_code = EXIT_OK
        self.boot_ts = time.time()
        self.workdir = os.path.abspath(self.args.workdir)
        # --out / --spine resolve AGAINST --workdir, never against the cwd: an engine
        # launched from another directory must still keep its own ring and spine.
        self.clip_dir = self.args.out if os.path.isabs(self.args.out) \
            else os.path.join(self.workdir, self.args.out)
        # NOTHING is created on disk here: a capture side that refuses to arm must
        # leave no clip directory, no spine and no child behind (see _ensure_dirs).
        self.spine_path = self.args.spine if os.path.isabs(self.args.spine) \
            else os.path.join(self.workdir, self.args.spine)
        self.lock_path = os.path.join(self.workdir, self.args.lock_name)
        self.portfile = os.path.join(self.workdir, self.args.port_name)
        self.statusfile = os.path.join(self.workdir, self.args.status_name)
        self.ring = Ring(RING_CAPACITY)
        self.hub = UiHub(self.diag)
        self.lock = RingLock(self.lock_path)
        self.spine = None
        self.child = None
        self.asr = None
        self.asr_done = collections.deque()
        self.asr_done_lock = threading.Lock()
        self.ui = None
        self.next_cut_at = None
        self.next_health_at = 0.0
        self.next_status_at = 0.0
        self.clip_index = 0
        self.capture_kind = "exe"
        self.stats = {
            "cuts_requested": 0, "cuts_ok": 0, "cuts_refused": 0,
            "asr_dead": 0, "asr_failed": 0,
        }
        # clips named by the SHUTDOWN reconcile (not by a requested cut); the
        # two are kept apart because --cut-count counts what the user asked for.
        self.reconciled = 0

    @staticmethod
    def parse_args(argv):
        ap = argparse.ArgumentParser(
            prog="engine.py",
            description="THE ENGINE PROCESS: single supervisor, ring owner, capture parent. "
                        "stdout stays EMPTY by contract; every diagnostic goes to stderr.")
        ap.add_argument("--capture", choices=("exe", "stub"), default="exe",
                        help="which capture child to supervise (stub is labelled STUB in every arm)")
        ap.add_argument("--capture-exe", default=os.path.join(REPO_ROOT, "_main", "build", "aireplay-capture.exe"))
        ap.add_argument("--capture-cmd", default="",
                        help="full capture command line (overrides --capture/--capture-exe)")
        ap.add_argument("--feed", default="", help="h264 source for the real capture child")
        ap.add_argument("--cut-size", default="", help="WxH passed to the real capture child")
        ap.add_argument("--out", default="clips", help="clip directory (relative to --workdir)")
        ap.add_argument("--fps", type=int, default=30)
        ap.add_argument("--seconds", type=float, default=0.0, help="self-close after N seconds (0 = forever)")
        ap.add_argument("--cut-every", type=float, default=0.0,
                        help="fire one cut every N seconds (the 'hotkey' arm without a keyboard)")
        ap.add_argument("--cut-count", type=int, default=0,
                        help="stop after N cuts (0 = unlimited)")
        ap.add_argument("--asr", choices=("on", "off"), default="off",
                        help="run the ASR side as a supervised child")
        ap.add_argument("--asr-cmd", default="",
                        help="ASR subcommand override, e.g. 'stub_asr_stall.py' (gate only)")
        ap.add_argument("--asr-timeout", type=float, default=900.0)
        ap.add_argument("--asr-queue", type=int, default=8)
        ap.add_argument("--ui", choices=("on", "off"), default="on")
        ap.add_argument("--port", type=int, default=0, help="0 = ephemeral, recorded in the portfile")
        ap.add_argument("--workdir", default=".")
        ap.add_argument("--spine", default="engine-spine.db")
        ap.add_argument("--lock-name", default="engine-ring.lock")
        ap.add_argument("--port-name", default="engine-port.json")
        ap.add_argument("--status-name", default="engine-status.json")
        ap.add_argument("--selftest", action="store_true",
                        help="run ONLY the LAW 6 pre-flight against the capture child and exit")
        ap.add_argument("--inject-fault", default="none",
                        choices=("none", "no-nvenc", "tuning-undefined", "skip-map"),
                        help="forwarded to the capture child's --selftest (gate pre-flight)")
        ap.add_argument("--quiet", action="store_true", help="suppress periodic health events")
        return ap.parse_args(argv)

    def _ensure_dirs(self):
        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(self.clip_dir, exist_ok=True)

    # -- diagnostics -------------------------------------------------------
    def diag(self, msg):
        # ARM-B instrument 2026-10-09: a diag write is an ordinary OS write, so a
        # pipe nobody reads freezes the WHOLE Engine -- that is the shape of the
        # 7-second ARM-B stall.  A write that costs seconds is named here, on
        # stderr, with the bytes that were stuck.
        _line = "[engine %s] %s\n" % (time.strftime("%H:%M:%S"), msg)
        _t0 = time.time()
        sys.stderr.write(_line)
        sys.stderr.flush()
        _dt = time.time() - _t0
        if _dt >= 1.0:
            sys.stderr.write("[engine %s] STDERR-BLOCKED %.3fs stalled %d bytes: %s\n"
                             % (time.strftime("%H:%M:%S"), _dt, len(_line), msg[:160]))
            sys.stderr.flush()

    def _silence_stdout(self):
        """stdout is EMPTY by contract: writing to it is a bug, made loud."""

        class _Guard(object):
            def write(self, s):
                raise AssertionError("engine stdout is EMPTY by contract; refused %r" % (s[:120],))

            def flush(self):
                pass

            def fileno(self):
                raise AssertionError("engine stdout has no fileno by contract")

        sys.stdout = _Guard()

    # -- lifecycle ---------------------------------------------------------
    def run(self):
        self._silence_stdout()
        try:
            return self._run()
        except EngineFatal as exc:
            self.diag("FATAL(%d): %s" % (exc.code, exc.msg))
            self.exit_code = exc.code
            return exc.code
        except KeyboardInterrupt:
            self.diag("shutdown: SIGINT")
            return EXIT_OK
        except Exception:
            self.diag("FATAL(5): unhandled internal error\n" + traceback.format_exc())
            return EXIT_FATAL
        finally:
            self._cleanup()
            self._write_status(final=True)

    def _run(self):
        if self.args.selftest:
            # A pre-flight in ITS OWN process: the refusal code IS the exit code
            # and the status file must say so.  Measured defect (ARM-D): this
            # branch returned the code without setting self.exit_code, so the
            # finally in run() persisted exit_code 0 + stop_reason "unknown" for
            # a run whose process really exited 3 and whose stderr really carried
            # CAPTURE-PREFLIGHT-REFUSED rc=3 -- the word and the code disagreed in
            # one run.  Created directories are still only the status file.
            code = self._preflight()
            self.exit_code = code
            self.stop_reason = "preflight-refused"
            os.makedirs(self.workdir, exist_ok=True)  # for the status file ONLY
            self._write_status(final=True)
            return code
        self._install_signals()
        self.diag("BOOT pid=%d python=%s workdir=%s ring=%d" %
                  (os.getpid(), sys.version.split()[0], self.workdir, self.ring.capacity))

        # (1) LAW 6 pre-flight -- BEFORE the Engine owns the ring, opens the spine
        #     or spawns a capture child.  A capture side that cannot arm must exit 3
        #     without having created anything, and its words (the encoder status)
        #     must reach the operator verbatim.
        code = self._preflight(exit_on_refusal=False)
        if code != EXIT_OK:
            self.exit_code = code
            self.diag("shutdown: pre-flight refused, the Engine never owned a ring")
            os.makedirs(self.workdir, exist_ok=True)  # for the status file ONLY
            self._write_status(final=True)
            return code
        self._ensure_dirs()

        # (2) the ring lock: one Engine, one owner
        if not self.lock.acquire():
            self.diag("REFUSED: another Engine owns the ring lock %s -- refusing to start a "
                      "second owner of the capture endpoint / ring file (exit 4)" % self.lock_path)
            sys.stderr.write("ENGINE-SECOND-INSTANCE path=%s\n" % self.lock_path)
            sys.stderr.flush()
            return EXIT_SECOND
        self.diag("ring lock acquired: %s" % self.lock_path)

        # (3) the spine
        self.spine = Spine(self.spine_path)
        self.diag("spine open: %s" % self.spine_path)

        # (4) the capture child -- the Engine's own child, or nothing is
        self.child = self._spawn_capture()
        if self.child is None:
            raise EngineFatal(EXIT_FATAL, "capture child would not start")
        self.diag("capture child pid=%d argv=%s" % (self.child.pid, " ".join(self.child.argv)))
        try:
            reply = self.child.ping(timeout=20.0)
            self.diag("capture handshake ok=%s reply=%s" % (reply.get("ok"), json.dumps(reply)[:160]))
        except CaptureChildError as exc:
            raise EngineFatal(EXIT_FATAL, "capture handshake failed: %s" % (exc,))

        # (5) the ASR side, behind a bounded queue
        if self.args.asr == "on":
            self.asr = AsrWorker(
                self._asr_argv(), cwd=SRC_DIR,
                on_result=self._asr_enqueue_result,
                queue_size=self.args.asr_queue, timeout=self.args.asr_timeout,
                diag=self.diag)
            self.asr.start()
            self.diag("asr side started: %s" % " ".join(self.asr.argv))

        # (6) the UI child door
        if self.args.ui == "on":
            self.ui = UiServer(self, "127.0.0.1", self.args.port)
            self.ui.start()
            # The socket is bound on the server THREAD, so the port this Engine
            # asked for (0 = ephemeral, the default) is NOT the port that is
            # listening.  Writing the portfile before the bind was measured
            # twice: it carried "port": 0, the UI child dialled 127.0.0.1:0 and
            # died with WinError 10049, and the Engine looked alive with no UI
            # attached -- the exact symptom ARM-B exists to detect.  Wait,
            # bounded, for the bind; the portfile names the LISTENING port.
            ui_deadline = time.time() + UI_BIND_WAIT_S
            while (self.ui.sock is None and not self.ui.error
                   and time.time() < ui_deadline):
                time.sleep(0.005)
            if self.ui.error or self.ui.sock is None:
                raise EngineFatal(EXIT_FATAL, "ui server: %s" % (self.ui.error or "bind timed out"))
            self._write_portfile()
            self.diag("ui door listening on 127.0.0.1:%d (portfile=%s)" % (self.ui.port, self.portfile))
        else:
            self.diag("ui door disabled (--ui off): recording continues unattended")

        self.emit("capture_started", {
            "capture": self.capture_kind,
            "clip_dir": self.clip_dir,
            "child_pid": self.child.pid,
            "fps": self.args.fps,
            "stub": self.capture_kind == "stub",
            "ring": self.ring.snapshot(),
        })
        if self.args.cut_every > 0:
            self.next_cut_at = time.time() + self.args.cut_every

        deadline = time.time() + self.args.seconds if self.args.seconds > 0 else None
        while not self.stop.is_set():
            now = time.time()
            if deadline is not None and now >= deadline:
                self.stop_reason = "seconds-elapsed"
                self.stop.set()
                break
            if not self.child.alive and not self.stop.is_set():
                self.diag("capture child died (rc=%r) -- the Engine cannot own a ring without a "
                          "capture side, but it does NOT wait for the ASR side" % (self.child.exit_code,))
                self.emit("error", {"where": "capture_child", "alive": False,
                                    "exit_code": self.child.proc.poll()})
                self.stop_reason = "capture-child-died"
                self.stop.set()
                break
            if self.next_cut_at is not None and now >= self.next_cut_at:
                self.next_cut_at = now + self.args.cut_every
                self.cut("hotkey")
            if now >= self.next_health_at:
                self.next_health_at = now + 1.0
                if not self.args.quiet:
                    self.hub.publish_now(make("health", self.health_payload()))
            if now >= self.next_status_at:
                self.next_status_at = now + 0.5
                self._write_status()
            self._drain_asr()
            time.sleep(0.02)
        self.diag("main loop stopped: %s" % self.stop_reason)
        # any ASR result already in flight is applied BEFORE the Engine exits, but
        # never for longer than ASR_EXIT_GRACE_S: a stalled ASR child must not hold
        # the Engine's shutdown hostage (capture is already closed at this point).
        self._drain_asr()
        if self.asr is not None:
            for _ in range(int(ASR_EXIT_GRACE_S * 10)):
                if not self.asr.has_pending():
                    break
                time.sleep(0.1)
                self._drain_asr()
        self._drain_asr()
        return EXIT_OK

    def _install_signals(self):
        for sig in ("SIGINT", "SIGTERM", "SIGBREAK"):
            s = getattr(signal, sig, None)
            if s is None:
                continue
            try:
                signal.signal(s, self._on_signal)
            except (ValueError, OSError):
                pass

    def _on_signal(self, signum, frame):
        if not self.stop.is_set():
            self.stop_reason = "signal-%d" % signum
        self.stop.set()


    # -- capture side ------------------------------------------------------
    def _capture_argv(self):
        if self.args.capture_cmd.strip():
            self.capture_kind = "custom"
            return split_cmd_line(self.args.capture_cmd)
        if self.args.capture == "stub":
            self.capture_kind = "stub"
            return [sys.executable, os.path.join(_HERE, "stub_capture.py"),
                    "--session", "--out", self.clip_dir, "--fps", str(self.args.fps)]
        self.capture_kind = "exe"
        argv = [os.path.abspath(self.args.capture_exe), "--cut-session"]
        if self.args.feed:
            argv += ["--cut-from-h264", os.path.abspath(self.args.feed)]
        argv += ["--cut-dir", self.clip_dir, "--cut-fps", str(self.args.fps)]
        if self.args.cut_size:
            argv += ["--cut-size", self.args.cut_size]
        return argv

    def _spawn_capture(self):
        argv = self._capture_argv()
        return CaptureChild(argv, workdir=None, diag=self.diag,
                            tag="capture" if self.capture_kind != "stub" else "capture-STUB").start()

    def _clip_ext(self):
        return ".wav" if self.capture_kind == "stub" else ".mp4"

    def _predicted_clip_path(self):
        return os.path.join(self.clip_dir, "cut-%04d%s" % (self.clip_index, self._clip_ext()))

    # -- LAW 6 pre-flight --------------------------------------------------
    def _preflight(self, exit_on_refusal=True):
        """Ask the capture child to arm BEFORE the Engine owns anything.

        LAW 6 (nose/#8889000A class): the capture side must REFUSE loudly with a
        dead encoder rather than run a hotkey that does nothing. The Engine maps
        the child's own verdict onto its own exit codes and prints the child's
        words verbatim -- the message names the encoder status.
        """
        exe = os.path.abspath(self.args.capture_exe)
        argv = [exe, "--selftest"]
        if self.args.capture == "stub":
            argv = [sys.executable, os.path.join(_HERE, "stub_capture.py"), "--selftest",
                    "--session", "--out", os.path.join(self.workdir, "clips"),
                    "--fps", str(self.args.fps)]
            exe = argv[1]
        if self.args.inject_fault != "none":
            argv += ["--inject-fault", self.args.inject_fault]
        self.diag("pre-flight (LAW 6): %s" % " ".join(argv))
        t0 = time.time()
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = CREATE_NO_WINDOW
        try:
            proc = subprocess.run(argv, input="", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=300, cwd=REPO_ROOT, **kw)
        except subprocess.TimeoutExpired:
            raise EngineFatal(EXIT_FATAL, "pre-flight timed out after 300s: %s" % " ".join(argv))
        except OSError as exc:
            raise EngineFatal(EXIT_USAGE, "pre-flight cannot run %s: %s" % (exe, exc))
        rc = proc.returncode
        decision = ""
        for line in (proc.stdout or "").splitlines():
            if "DECISION" in line:
                decision = line.strip()
                break
        self.diag("pre-flight rc=%d decision=%r wall=%.1fs" % (rc, decision, time.time() - t0))
        if rc == 0:
            return EXIT_OK
        # ---- a refusal: the child's own words, verbatim, on stderr ----
        sys.stderr.write("CAPTURE-PREFLIGHT-REFUSED rc=%d argv=%s\n" % (rc, " ".join(argv)))
        sys.stderr.write((proc.stdout or "").strip() + "\n")
        sys.stderr.write((proc.stderr or "").strip() + "\n")
        sys.stderr.flush()
        if rc == 3:
            return EXIT_NVENC
        if rc == 2:
            return EXIT_USAGE
        sys.stderr.write("ENGINE-PREFLIGHT-UNEXPECTED rc=%d -> treated as fatal internal\n" % rc)
        sys.stderr.flush()
        return EXIT_FATAL

    # -- the cut path ------------------------------------------------------
    def cut(self, reason="hotkey"):
        self.stats["cuts_requested"] += 1
        clip_id = "cut-%06d" % self.clip_index
        pred_path = self._predicted_clip_path()
        started_ms = now_ms()
        try:
            self.spine.anchor(clip_id, pred_path, started_ms,
                               modes="engine-%s" % reason, frames=0)
        except Exception as exc:
            self.stats["cuts_refused"] += 1
            self.diag("cut %s: cannot anchor: %r" % (clip_id, exc))
            self.emit("error", {"where": "spine_anchor", "clip_id": clip_id, "error": repr(exc)})
            return None
        _t0 = time.time()
        try:
            reply = self.child.cut(timeout=120.0)
        except CaptureChildError as exc:
            self.diag("cut %s: child.cut raised after %.3fs" % (clip_id, time.time() - _t0))
            self.spine.mark_failed(clip_id, "refused")
            self.stats["cuts_refused"] += 1
            self.diag("cut %s REFUSED: %s" % (clip_id, exc))
            self.emit("error", {"where": "cut", "clip_id": clip_id, "error": str(exc)})
            return None
        if time.time() - _t0 >= 1.0:
            self.diag("cut %s: child.cut took %.3fs" % (clip_id, time.time() - _t0))
        closed = reply.get("closed_clip")
        cid = "cut-%06d" % closed if isinstance(closed, int) else clip_id
        path = reply.get("path") or pred_path
        frames = int(reply.get("closed_frames") or 0)
        size = int(reply.get("closed_bytes") or 0)
        duration_ms = int(round(frames * 1000.0 / max(1, self.args.fps)))
        try:
            row = self.spine.commit_clip(cid, size_bytes=size, frames=frames,
                                          duration_ms=duration_ms, path=path)
        except Exception as exc:
            self.spine.mark_failed(cid, "commit-failed")
            self.stats["cuts_refused"] += 1
            self.diag("cut %s: commit failed: %r" % (cid, exc))
            self.emit("error", {"where": "spine_commit", "clip_id": cid, "error": repr(exc)})
            return None
        self.stats["cuts_ok"] += 1
        self.clip_index = (closed + 1) if isinstance(closed, int) else (self.clip_index + 1)
        payload = {
            "clip_id": cid, "path": path, "content_key": row["content_key"],
            "size_bytes": int(row["size_bytes"]), "frames": int(row["frames"]),
            "duration_ms": int(row["duration_ms"]), "reason": reason,
            "duration_source": "frames*fps (child carries no ms field)",
            "t_ms": now_ms() - started_ms,
        }
        self.emit("clip_written", payload)
        self.diag("clip %s written: %s key=%s bytes=%d frames=%d"
                  % (cid, os.path.basename(path), row["content_key"][:12], payload["size_bytes"], frames))
        if self.asr is not None:
            offered = self.asr.submit(cid, path)
            if not offered:
                self.spine.set_asr_state(cid, "dropped")
                self.diag("clip %s: ASR queue FULL -- job dropped (capture never waited)" % cid)
        if self.args.cut_count > 0 and self.stats["cuts_ok"] >= self.args.cut_count:
            self.stop_reason = "cut-count-reached"
            self.stop.set()
        if self.args.cut_every > 0 and self.next_cut_at is None:
            self.next_cut_at = time.time() + self.args.cut_every
        return payload

    # -- events ------------------------------------------------------------
    def emit(self, type_, payload):
        env = self.ring.append(type_, payload)
        self.hub.publish_now(env)
        return env

    # -- ASR side ----------------------------------------------------------
    def _asr_argv(self):
        if self.args.asr_cmd.strip():
            parts = split_cmd_line(self.args.asr_cmd)
            if parts and parts[0].endswith(".py"):
                return [sys.executable, os.path.abspath(parts[0])] + parts[1:]
            return parts
        return [sys.executable, "-m", "asr.transcribe"]

    def _asr_enqueue_result(self, res):
        with self.asr_done_lock:
            self.asr_done.append(res)

    def _drain_asr(self):
        while True:
            with self.asr_done_lock:
                if not self.asr_done:
                    return
                res = self.asr_done.popleft()
            self._apply_asr_result(res)

    def _apply_asr_result(self, res):
        d = res.as_dict()
        if res.state == "ok":
            self.spine.set_asr_state(res.clip_id, "ok")
            if res.segments:
                rows = [{"seg_index": int(s.get("i", i)), "t0": float(s.get("start", 0.0)),
                         "t1": float(s.get("end", 0.0)), "text": str(s.get("text", "")),
                         "infer_s": res.infer_s}
                        for i, s in enumerate(res.segments)]
                d["speech_rows"] = self.spine.add_speech(res.clip_id, rows)
            if res.text:
                # asr_partial is the LIVE caption event; this Engine's ASR side is
                # an offline child per clip, so the partial arrives at clip close.
                self.emit("asr_partial", {"clip_id": res.clip_id, "text": res.text,
                                          "segments": len(res.segments), "final": True,
                                          "note": "offline ASR per clip: emitted at clip close"})
            self.emit("asr_final", d)
            self.emit("index_updated", {"clip_id": res.clip_id,
                                        "speech_segments": len(res.segments)})
            self.diag("asr %s ok: %d segments %d chars (infer %.2fs)"
                      % (res.clip_id, len(res.segments), len(res.text), res.infer_s or -1))
        else:
            # a stalled or dead ASR side is reported and RECORDED, never fatal
            self.spine.set_asr_state(res.clip_id, res.state)
            d["error"] = res.error
            if res.state == "dead":
                self.stats["asr_dead"] += 1
            else:
                self.stats["asr_failed"] += 1
            self.emit("asr_final", d)
            self.diag("asr %s %s: %s" % (res.clip_id, res.state, res.error))

    # -- UI side: writer thread and command handler ------------------------
    def ui_writer(self, conn):
        # ARM-B instrument 2026-10-09: this thread is the ONLY one that touches
        # the socket on this side, and when it died it said nothing -- the
        # reconnecting UI got a handshake and then total silence while a healthy
        # Engine cut 137 more clips.  It now speaks every 2 s while idle, names a
        # send that blocks, and names its own death.
        _idle_diag = 0.0
        while conn.alive:
            try:
                item = conn.q.popleft()
            except IndexError:
                _now = time.time()
                if _now - _idle_diag >= 2.0:
                    _idle_diag = _now
                    self.diag("ui %s WRITER-IDLE sent=%d q=%d alive=%s attached=%s"
                              % (conn.id, conn.sent, len(conn.q), conn.alive, conn.attached))
                time.sleep(0.004)
                continue
            kind = item[0]
            env = None
            if kind == "env":
                env = item[1]
            elif kind == "hello":
                env = make("hello", item[1])
            elif kind == "replay":
                env = make("replay", item[1])
                conn.replayed = len(item[1].get("events", []))
                conn.since = item[1].get("to", conn.since)
            elif kind == "ready":
                conn.ready.set()
                continue
            _data = protocol.encode(env).encode("utf-8")
            _t0 = time.time()
            try:
                conn.sock.sendall(_data)
                conn.sent += 1
            except OSError as exc:
                self.diag("ui %s WRITER-DEAD send failed after %.3fs: %s"
                          % (conn.id, time.time() - _t0, exc))
                conn.alive = False
                self.hub.remove(conn)
                return
            _dt = time.time() - _t0
            if _dt >= 1.0:
                self.diag("ui %s WRITER-SLOW send blocked %.3fs bytes=%d"
                          % (conn.id, _dt, len(_data)))

    def ui_command(self, conn, env):
        t = env.get("type")
        mid = env.get("id")
        p = env.get("payload") or {}
        if t == "attach":
            since = p.get("since", 0)
            if isinstance(since, bool) or not isinstance(since, int) or since < 0:
                since = 0
            conn.since = since
            snap = self.ring.snapshot()
            conn.q.append(("hello", {
                "engine_version": ENGINE_VERSION, "pid": os.getpid(),
                "ring": snap, "since": since,
                "capture": self.capture_kind,
            }))
            evs, oldest, newest = self.ring.since(since)
            conn.q.append(("replay", {
                "events": evs, "from": since, "to": newest,
                "oldest_retained": oldest,
                "truncated": bool(since > 0 and since < oldest),
                "replayed": len(evs),
            }))
            UiHub.offer(conn, ("env", make("health", {
                "ui_ready": True, "since": since, "replayed": len(evs),
                "truncated": bool(since > 0 and since < oldest),
                "oldest_retained": oldest, "to": newest,
            })))
            conn.attached = True
            self.diag("ui %s ATTACH since=%d replay=%d truncated=%s"
                      % (conn.id, since, len(evs), since > 0 and since < oldest))
        elif t == "detach":
            conn.attached = False
            conn.q.append(("env", make("detach", {"reply_to": mid})))
            self.diag("ui %s DETACH -- recording continues" % conn.id)
        elif t == "cut":
            payload = self.cut("ui")
            conn.q.append(("env", make("cut_ack", {"reply_to": mid, "ok": payload is not None,
                                                   "clip": payload})))
        elif t == "status":
            conn.q.append(("env", make("status", {"reply_to": mid, "health": self.health_payload()})))
        elif t == "search":
            q = str(p.get("query") or "").strip()
            try:
                hits = self.spine.search(q, limit=50) if (q and self.spine) else []
            except Exception as exc:
                hits = []
                self.diag("search failed: %r" % (exc,))
            conn.q.append(("env", make("search", {"reply_to": mid, "query": q, "hits": hits})))
        elif t == "bye":
            conn.q.append(("env", make("bye", {"reply_to": mid})))
            conn.alive = False
        else:
            conn.q.append(("env", make("error", {"reply_to": mid,
                                                 "error": "unknown command %r" % (t,)})))

    def health_payload(self):
        return {
            "pid": os.getpid(),
            "uptime_s": round(time.time() - self.boot_ts, 1),
            "capture": self.capture_kind,
            "ring": self.ring.snapshot(),
            "cuts": dict(self.stats),
            "reconciled": int(self.reconciled),
            "clips": self.spine.counts() if self.spine else {},
            "asr": self.asr.snapshot() if self.asr else None,
            "child": {
                "alive": bool(self.child and self.child.alive),
                "pid": self.child.pid if self.child else None,
                "diag_lines": self.child.diag_lines if self.child else 0,
                "exit_code": self.child.exit_code if self.child else None,
            },
            "ui": {"connected": self.hub.count(), "attached": self.hub.count(True)},
            "stop_reason": self.stop_reason if self.stop.is_set() else None,
        }

    # -- files the outside world reads -------------------------------------
    def _atomic_write_json(self, path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _write_portfile(self):
        self._atomic_write_json(self.portfile, {
            "protocol_version": ENGINE_VERSION,
            "host": "127.0.0.1", "port": self.ui.port if self.ui else None,
            "pid": os.getpid(), "boot_ts": self.boot_ts,
            "capture": self.capture_kind,
            "workdir": self.workdir, "clip_dir": self.clip_dir,
            "spine": self.spine_path,
            "transport": "localhost TCP JSONL (production target: a named pipe; "
                         "accepted divergence, see receipt)",
        })

    def _write_status(self, final=False):
        out = {
            "pid": os.getpid(), "boot_ts": self.boot_ts,
            "now": time.time(), "final": bool(final),
            "stop_reason": self.stop_reason,
            "exit_code": None if self.exit_code is None else int(self.exit_code),
            "capture": self.capture_kind,
            "ring": self.ring.snapshot(),
            "health": self.health_payload(),
            "spine": self.spine_path,
            "portfile": self.portfile,
            "lock": self.lock_path,
            "stdout_bytes": 0,
        }
        try:
            self._atomic_write_json(self.statusfile, out)
        except Exception as exc:
            self.diag("cannot write status file: %r" % (exc,))

    # -- shutdown ----------------------------------------------------------
    def _shutdown_capture(self):
        if self.child is None:
            return
        if self.child.proc is not None:
            self.diag("capture child shutdown: stdin EOF -> finalise -> wait")
            rc = self.child.close(grace=8.0)
            self.diag("capture child exited rc=%r" % (rc,))
        self._drain_final_clips()

    def _drain_final_clips(self):
        """Name every clip the capture child closed that no cut consumed.

        TWO mechanisms, measured 2026-10-09, and the second one is the one
        that carries the weight:

        (1) _finalise_child_replies -- a child that ANSWERS stdin EOF with a
            cut-shaped reply.  Kept because a capture child may; MEASURED on
            both children that exist today and neither does: the real child
            writes its finalise fields into a LOG line and nothing on the
            reply channel (src/capture/main.cpp:1294-1299), and
            stub_capture.py:234 matches that behaviour byte for byte.  So the
            drain is defensive only -- it is not what closes the gap.

        (2) _reconcile_clip_dir -- the CLIP DIRECTORY against the spine.  That
            is the measured answer: on ARM-G green the session ended with 305
            clip files on disk against 304 spine rows (ARM-B: 208/207), the
            last clip of a graceful stop present on disk with no content_key
            and nothing downstream able to find it.  The file was written, so
            the spine must describe it; a spine that does not describe every
            clip on disk is not a spine.

        Both run while the spine, the ring, the hub and the ASR side are still
        alive -- _cleanup tears those down after this call, never before.
        """
        try:
            self._finalise_child_replies()
        except Exception as exc:
            self.diag("finalise drain failed (non-fatal): %r" % (exc,))
        self._reconcile_clip_dir()

    def _reconcile_clip_dir(self):
        """Every clip FILE on disk gets a spine row, or the session is a lie.

        Lists the clip directory, skips every file the spine already names by
        path, and commits the rest from the FILE: content_key is the sha256 of
        the bytes on disk (content_key_of), frames come from the WAV header
        (wav_frames), duration is frames*fps.  The row is anchored, committed,
        published to any attached UI as a clip_written with reason=reconcile,
        and offered to ASR -- the same three steps a requested cut takes.

        This is NOT a cut and never touches cuts_ok: --cut-count counts the
        cuts the USER asked for, and ARM-A keeps asserting cuts_ok == 4 while
        the same session leaves 5 clip files on disk (4 requested cuts plus
        the clip the child closed at stdin EOF).  The counter that reports
        reconciles is self.reconciled, in the health payload under its own
        name, so a reconcile can never be mistaken for a hotkey act.

        Not an ARM-F path: a TerminateProcess kill runs no cleanup at all, so
        a killed engine still leaves at most one cutting row with no key.
        """
        if self.spine is None:
            return
        try:
            names = sorted(os.listdir(self.clip_dir))
        except OSError:
            return   # an engine whose capture side refused to arm has no clips
        known = set()
        try:
            for row in (self.spine.clips() or []):
                try:
                    p = row["path"]
                except Exception:
                    p = None
                if p:
                    known.add(os.path.abspath(p))
        except Exception as exc:
            self.diag("reconcile cannot read the spine: %r" % (exc,))
            return
        fps = float(self.args.fps or 0) or 1.0
        for name in names:
            path = os.path.join(self.clip_dir, name)
            try:
                if not os.path.isfile(path):
                    continue
                if os.path.abspath(path) in known:
                    continue   # already described: the common case
            except OSError:
                continue
            cid = os.path.splitext(name)[0]
            try:
                frames = wav_frames(path)
                size = os.path.getsize(path)
                duration = int(round(float(frames) * 1000.0 / fps)) if frames else 0
                self.spine.anchor(cid, path, now_ms(), modes="engine-reconcile",
                                  frames=frames or 0)
                row = self.spine.commit_clip(cid, size_bytes=size, frames=frames or 0,
                                             duration_ms=duration, path=path)
                self.reconciled += 1
                try:
                    self.clip_index = max(self.clip_index, int(cid.split("-")[-1]) + 1)
                except ValueError:
                    pass
                payload = {
                    "clip_id": cid, "path": path, "content_key": row["content_key"],
                    "size_bytes": int(row["size_bytes"]), "frames": int(row["frames"]),
                    "duration_ms": int(row["duration_ms"]), "reason": "reconcile",
                    "duration_source": "frames*fps (child carries no ms field)",
                    "t_ms": 0,
                }
                self.emit("clip_written", payload)
                self.diag("clip %s RECONCILED at shutdown: %s key=%s bytes=%d frames=%d"
                          % (cid, name, row["content_key"][:12], payload["size_bytes"],
                             payload["frames"]))
                if self.asr is not None:
                    if not self.asr.submit(cid, path):
                        self.spine.set_asr_state(cid, "dropped")
            except Exception as exc:
                # A reconcile must never turn a clean stop into a crash, and it
                # must never be silent: an unnamed clip is reported, not hidden.
                self.diag("reconcile FAILED for %s: %r" % (path, exc))

    def _finalise_child_replies(self):
        """Commit every clip the child closed that no requested cut consumed.

        Today that is exactly one: the clip left open at shutdown, and only
        for a child that answers stdin EOF at all -- measured on both children
        that exist today, NEITHER does, so in practice _reconcile_clip_dir is
        what names it.  It is
        anchored, committed with the sha256 of the FILE as content_key,
        published to any attached UI and offered to ASR -- in that order,
        because all of those have to still be alive for it to matter.
        """
        if self.child is None:
            return 0
        try:
            q = self.child.replies
        except Exception:
            return 0
        done = 0
        while True:
            try:
                reply = q.get_nowait()
            except Exception:
                break
            if not isinstance(reply, dict):
                continue
            if self._finalise_child_reply(reply) is not None:
                done += 1
        return done

    def _finalise_child_reply(self, reply):
        """Anchor+commit ONE child reply that no requested cut waited for."""
        closed = reply.get("closed_clip")
        if not isinstance(closed, int):
            return None
        cid = "cut-%06d" % closed
        path = reply.get("path")
        frames = int(reply.get("closed_frames") or 0)
        size = int(reply.get("closed_bytes") or 0)
        duration_ms = int(round(frames * 1000.0 / max(1, self.args.fps)))
        if not path or not os.path.exists(path):
            self.diag("final clip %s: child reports %r closed but it is not on disk"
                      % (cid, path))
            return None
        if self.spine is None:
            return None
        try:
            self.spine.anchor(cid, path, now_ms(), modes="engine-finalise",
                              frames=frames)
            row = self.spine.commit_clip(cid, size_bytes=size, frames=frames,
                                          duration_ms=duration_ms, path=path)
        except Exception as exc:
            self.diag("final clip %s: cannot commit: %r" % (cid, exc))
            return None
        self.stats["cuts_ok"] += 1
        self.clip_index = closed + 1
        payload = {
            "clip_id": cid, "path": path, "content_key": row["content_key"],
            "size_bytes": int(row["size_bytes"]), "frames": int(row["frames"]),
            "duration_ms": int(row["duration_ms"]), "reason": "finalise",
            "duration_source": "frames*fps (child carries no ms field)",
            "t_ms": 0,
        }
        self.emit("clip_written", payload)
        self.diag("clip %s FINALISED at shutdown: %s key=%s bytes=%d frames=%d"
                  % (cid, os.path.basename(path), row["content_key"][:12],
                     payload["size_bytes"], frames))
        if self.asr is not None:
            offered = self.asr.submit(cid, path)
            if not offered:
                self.diag("final clip %s: ASR queue full -- not offered" % cid)
        return row

    def _cleanup(self):
        if getattr(self, "stop", None) is not None:
            self.stop.set()
        # The capture child is stopped FIRST.  It finalises the clip that is
        # still open when its stdin reaches EOF, and that reply has to be
        # committed to the spine and published to whatever UI is still
        # attached -- measured 2026-10-09 in ARM-G green (see
        # _finalise_child_replies): before this order, a graceful stop left an
        # orphan clip on disk with no row and no content_key.
        try:
            self._shutdown_capture()
        except Exception as exc:
            sys.stderr.write("ENGINE-CLEANUP-ERROR capture: %r\n" % (exc,))
        if getattr(self, "ui", None):
            try:
                self.hub.shutdown()
                self.ui.stop()
            except Exception:
                pass
        if getattr(self, "asr", None):
            try:
                self.asr.stop(join_timeout=2.0)
            except Exception:
                pass
        if getattr(self, "spine", None):
            try:
                self.spine.close()
            except Exception:
                pass
            self.spine = None  # a closed spine answers no question
        try:
            if os.path.exists(self.portfile):
                os.unlink(self.portfile)
        except OSError:
            pass
        self.lock.release()
        sys.stderr.flush()


def main(argv=None):
    eng = Engine(argv)
    return eng.run()


if __name__ == "__main__":
    raise SystemExit(main())
