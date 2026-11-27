"""capture_share.py -- the WORKER's mixed capture, shared with ONE local reader.

The worker already owns the only capture that may open a device: `mic_tap` mixes
the owner's microphone into the loopback and hands the result to the ASR at
16 kHz mono float32. The sidecar used to open a SECOND loopback and a SECOND
microphone for the same call, which doubled the device cost, could pick a
different endpoint, and mixed the owner's mic twice. This module publishes the
worker's already-mixed block on a loopback-only TCP socket so the sidecar can
consume it with NO device of its own.

CONTRACT
--------
* one client slot. A second client is answered BUSY and closed.
* a BOUNDED queue (QUEUE_BLOCKS blocks). A full queue drops the newest block
  and counts it: `CAPTURE_SHARE_DROP dropped=<n>`. The ASR thread never waits
  for a socket, a consumer or a lock held by the sender.
* `Publisher.publish()` is inert while no client is connected: one bool read
  and an immediate return, so the common (alone) case costs no copy at all.
* the sidecar connects within 2 s or falls back to its own tap, printing
  `CAPTURE_SHARE fallback reason=<...>`; a connected reader prints
  `CAPTURE_SHARE client=connected from=worker`.
* wire format: `uint32 little-endian byte count` + exactly that many bytes of
  native float32 PCM. No format, rate or endpoint negotiation is attempted:
  the bytes are the bytes the ASR was handed, in order.

Nothing here imports numpy or opens an audio device. The reader converts the
payload to a float32 array where it is consumed, on the reader's own thread.
"""
from __future__ import annotations

import os
import queue
import socket
import struct
import threading
import time

HOST = "127.0.0.1"
DEFAULT_PORT = 47913
PORT_ENV = "SOTTO_CAPTURE_SHARE_PORT"
ENABLE_ENV = "SOTTO_CAPTURE_SHARE"

HELLO = b"SOTTO-CAPTURE-1\n"
OK = b"OK\n"
BUSY = b"BUSY\n"
MAX_FRAME = 4 * 1024 * 1024
QUEUE_BLOCKS = 32
TIMEOUT_S = 2.0
#: The HELLO wait, shorter than the send timeout on purpose: the accept loop is
#: serial, so a stranger that connects and says nothing must not be able to
#: delay the legitimate client past its own 2 s connect deadline (which would
#: push the sidecar onto a duplicate tap without anyone failing).
HANDSHAKE_S = 0.5
RATE = 16000


def port_from_env(env=None):
    """The configured port; an invalid value never changes the product's port."""
    env = os.environ if env is None else env
    raw = str(env.get(PORT_ENV, DEFAULT_PORT) or DEFAULT_PORT).strip()
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


def share_disabled(env=None):
    """SOTTO_CAPTURE_SHARE=0 is the explicit off switch for the client."""
    env = os.environ if env is None else env
    return str(env.get(ENABLE_ENV, "1") or "1").strip().lower() in (
        "0", "off", "false", "no")


def _recv_exact(sock, count):
    """Exactly `count` bytes, or None on EOF. Caller owns the socket timeout."""
    parts = []
    left = count
    while left > 0:
        part = sock.recv(left)
        if not part:
            return None
        parts.append(part)
        left -= len(part)
    return b"".join(parts)


def _recv_line(sock, limit=32):
    data = b""
    while len(data) < limit and not data.endswith(b"\n"):
        ch = sock.recv(1)
        if not ch:
            break
        data += ch
    return data


def _raw(block):
    if isinstance(block, (bytes, bytearray, memoryview)):
        return bytes(block)
    return block.tobytes()


class Publisher:
    """Loopback listener with one client slot and a bounded, droppable queue."""

    def __init__(self, port=None, log=print, max_blocks=QUEUE_BLOCKS):
        self.port = port_from_env() if port is None else int(port)
        self.log = log
        self._queue = queue.Queue(maxsize=max(1, int(max_blocks)))
        self._lock = threading.Lock()
        self._connected = False
        self._drops = 0
        self._stop = threading.Event()
        self._server = None
        self._conn = None
        self._accept_thread = None
        self._sender_thread = None

    @property
    def connected(self):
        return bool(self._connected)

    @property
    def drops(self):
        return int(self._drops)

    @property
    def queued(self):
        return self._queue.qsize()

    def start(self):
        if self._server is not None:
            return self
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, self.port))
        sock.listen(4)
        sock.settimeout(0.2)
        self._server = sock
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="capture-share-accept", daemon=True)
        self._accept_thread.start()
        return self

    def stop(self):
        self._stop.set()
        conn = self._conn
        if conn is not None:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        for thread in (self._sender_thread, self._accept_thread):
            if (thread is not None and thread is not threading.current_thread()
                    and thread.ident is not None):
                thread.join(timeout=1.0)
        self._connected = False

    def _drain(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _disconnect(self, reason):
        with self._lock:
            was_connected = self._connected
            self._connected = False
        if was_connected and not self._stop.is_set():
            self.log("CAPTURE_SHARE client=disconnected reason=%s" % reason)
        self._drain()

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            handed_off = False
            try:
                conn.settimeout(HANDSHAKE_S)
                if _recv_exact(conn, len(HELLO)) != HELLO:
                    conn.sendall(b"NOHELLO\n")
                    continue
                with self._lock:
                    busy = self._connected
                    if not busy:
                        self._connected = True
                if busy:
                    conn.sendall(BUSY)
                    continue
                conn.sendall(OK)
                # The send path owns its own budget: HANDSHAKE_S is only the
                # HELLO wait, and a slow-but-alive client must not be dropped
                # because it was measured with the handshake clock.
                conn.settimeout(TIMEOUT_S)
                # Audio queued for a previous client belongs to that client's
                # session, not to the one that just connected.
                self._drain()
                self._conn = conn
                self._sender_thread = threading.Thread(
                    target=self._send_loop, args=(conn,),
                    name="capture-share-send", daemon=True)
                self._sender_thread.start()
                handed_off = True
            except (OSError, socket.timeout):
                # A STRANGER'S FAILED HANDSHAKE MUST NOT EJECT THE CLIENT THAT
                # HOLDS THE SLOT (reviewer finding, 2026-11-25). The first
                # version disconnected the slot on ANY handshake failure, so a
                # local process that connected and stayed silent forced the
                # sidecar back onto its own duplicate loopback+mic -- the exact
                # invariant this transport exists to hold. The slot is only
                # ours to release when the sender thread for THIS connection
                # dies; a newcomer that never got `handed_off` is just closed.
                if not handed_off:
                    try:
                        conn.sendall(BUSY)
                    except OSError:
                        pass
            finally:
                if not handed_off:
                    try:
                        conn.close()
                    except OSError:
                        pass

    def _send_loop(self, conn):
        """Socket I/O lives HERE, never in the ASR thread that calls publish."""
        try:
            while not self._stop.is_set() and self._connected:
                try:
                    payload = self._queue.get(timeout=0.2)
                except queue.Empty:
                    # No audio to send is the normal case between blocks, but
                    # it must not hide a client that went away: without this
                    # peek the one slot stays occupied until the worker exits.
                    try:
                        if conn.recv(1, socket.MSG_PEEK) == b"":
                            self._disconnect("client-closed")
                            return
                    except socket.timeout:
                        pass
                    except OSError as exc:
                        self._disconnect("client-closed: %s" % type(exc).__name__)
                        return
                    continue
                try:
                    conn.sendall(struct.pack("<I", len(payload)) + payload)
                except (OSError, socket.timeout) as exc:
                    self._disconnect("send failed: %s" % type(exc).__name__)
                    return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def publish(self, block):
        """Enqueue one 16 kHz mono float32 block without ever blocking.

        Returns True when the block was queued. With no client this is a single
        boolean test: no copy, no queue touch, no allocation on the live path.
        """
        if not self._connected:
            return False
        try:
            payload = _raw(block)
        except Exception:                                       # noqa: BLE001
            return False
        if not payload or len(payload) > MAX_FRAME:
            return False
        try:
            self._queue.put_nowait(payload)
            return True
        except queue.Full:
            with self._lock:
                self._drops += 1
                count = self._drops
            self.log("CAPTURE_SHARE_DROP dropped=%d" % count)
            return False


class Client:
    """The sidecar's reader. Feeds the same `sink` a local tap would feed."""

    def __init__(self, sock, log=print, timeout=TIMEOUT_S):
        self.sock = sock
        self.log = log
        self.rate = RATE
        self.alive = True
        self.failure_reason = None
        self._sink = None
        self._on_failure = None
        self._stop = threading.Event()
        self._thread = None
        self.stream = _ClientStream(self)

    def set_sink(self, sink):
        self._sink = sink

    def set_failure_callback(self, callback):
        self._on_failure = callback

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._read_loop, name="capture-share-client", daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if (self._thread is not None
                and self._thread is not threading.current_thread()
                and self._thread.ident is not None):
            self._thread.join(timeout=2.0)
        try:
            self.sock.close()
        except OSError:
            pass

    def _fail(self, reason):
        if not self.alive:
            return
        self.alive = False
        self.failure_reason = reason
        self.log("CAPTURE_SHARE fallback reason=%s" % reason)
        callback = self._on_failure
        if callback is not None:
            try:
                callback(reason)
            except Exception as exc:                            # noqa: BLE001
                self.log("CAPTURE_SHARE fallback tap failed (%s): %s"
                         % (type(exc).__name__, exc))

    def _read_loop(self):
        try:
            while not self._stop.is_set() and self.alive:
                head = _recv_exact(self.sock, 4)
                if head is None:
                    # END-OF-FILE IS ALSO WHAT AN ORDERLY `stop()` LOOKS LIKE.
                    # MEASURED 2026-11-25 (oracle arm f, 4 runs of 8): `stop()`
                    # shuts the socket down before the reader sees the flag, so
                    # the EOF branch called `_fail("publisher-closed")` and the
                    # sidecar opened a DUPLICATE local loopback tap while it was
                    # shutting down -- the second device pair this transport
                    # exists to prevent, on every clean stop. Only a stop we did
                    # not ask for is a failure.
                    if not self._stop.is_set():
                        self._fail("publisher-closed")
                    return
                size = struct.unpack("<I", head)[0]
                if not 0 < size <= MAX_FRAME:
                    self._fail("bad-frame")
                    return
                payload = _recv_exact(self.sock, size)
                if payload is None:
                    if not self._stop.is_set():
                        self._fail("publisher-closed")
                    return
                import numpy as np                              # noqa: PLC0415
                block = np.frombuffer(payload, dtype="<f4")
                sink = self._sink
                if sink is not None:
                    sink(block)
        except (OSError, ValueError, Exception) as exc:        # noqa: BLE001
            if not self._stop.is_set():
                self._fail("read failed: %s" % type(exc).__name__)


class _ClientStream:
    """The tap-shaped handle the sidecar's existing start/stop loop expects."""

    def __init__(self, client):
        self.client = client

    def start(self):
        return self.client.start()

    def stop(self):
        return self.client.stop()


def connect_client(port=None, timeout=TIMEOUT_S, log=print, env=None):
    """Connect within `timeout`, or return None having printed the reason.

    Never raises. Every refusal path is bounded by the same deadline, so the
    sidecar's own tap is open well inside the 2 s budget.
    """
    if share_disabled(env):
        log("CAPTURE_SHARE fallback reason=disabled")
        return None
    chosen_port = port_from_env(env) if port is None else int(port)
    deadline = time.monotonic() + float(timeout)
    def left():
        return max(0.01, deadline - time.monotonic())
    try:
        sock = socket.create_connection((HOST, chosen_port), timeout=left())
    except OSError as exc:
        log("CAPTURE_SHARE fallback reason=no-publisher (%s)" % type(exc).__name__)
        return None
    try:
        sock.settimeout(left())
        sock.sendall(HELLO)
        reply = _recv_line(sock)
        if reply != OK:
            if reply == BUSY:
                reason = "busy"
            elif not reply:
                reason = "handshake-timeout"
            else:
                reason = "bad-handshake"
            log("CAPTURE_SHARE fallback reason=%s" % reason)
            sock.close()
            return None
        sock.settimeout(None)
    except (OSError, socket.timeout):
        log("CAPTURE_SHARE fallback reason=handshake-timeout")
        try:
            sock.close()
        except OSError:
            pass
        return None
    log("CAPTURE_SHARE client=connected from=worker")
    return Client(sock, log=log, timeout=timeout)


__all__ = [
    "HOST", "DEFAULT_PORT", "PORT_ENV", "ENABLE_ENV", "RATE", "QUEUE_BLOCKS",
    "Publisher", "Client", "connect_client", "port_from_env", "share_disabled",
]
