"""The Engine's supervisor for the capture child.

THE ENGINE IS THE ONLY PARENT of the capture process. This module owns the
spawn, the two pipes, and the rule that decides what every line of the child's
stdout MEANS:

  * a line that parses as a JSON object is a PROTOCOL reply (ping/cut) -- it
    never leaves this process through stderr, and it is never treated as text;
  * every other line is the child's DIAGNOSTIC and is forwarded to the ENGINE's
    stderr behind a "[capture]" tag.

That rule is not a preference. The real child (src/capture/main.cpp's
log_line) writes its "=== CUT SESSION ===" headers and its DECISION lines to
STDOUT, not stderr (measured while gating LAW 6: those lines arrive on the
captured stdout), so the Engine cannot assume a clean JSON channel from the
capture side. Meanwhile the ENGINE's own stdout stays EMPTY by contract -- that
channel belongs to the UI (docs/design-notes/03-engine-ipc.md), which is why
diagnostics can only travel on stderr.

The child is always spawned with CREATE_NO_WINDOW: the owner's screen must
never gain a console window because the Engine started (house rule).
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time

CREATE_NO_WINDOW = 0x08000000  # Win32: no console window for the child.


class CaptureChildError(RuntimeError):
    """The capture side could not answer, or answered "refused"."""


def classify(line):
    """Decide what ONE line of the child's stdout means.

    Returns ("reply", dict) for a JSON-object line and ("diag", str) for
    everything else (including a JSON array or scalar -- the capture protocol
    only ever answers with objects).
    """
    s = line.strip()
    if not s:
        return ("diag", "")
    try:
        obj = json.loads(s)
    except Exception:
        return ("diag", s)
    if not isinstance(obj, dict):
        return ("diag", s)
    return ("reply", obj)


class CaptureChild(object):
    """One capture child, supervised: pipes, replies, diagnostics, shutdown."""

    def __init__(self, argv, workdir=None, diag=None, tag="capture"):
        self.argv = [str(a) for a in argv]
        self.workdir = workdir
        self.diag = diag
        self.tag = tag
        self.proc = None
        self.replies = queue.Queue()
        self.diag_lines = 0
        self.last_diag = ""
        self.first_line_at = None
        self.exit_code = None
        self._io_lock = threading.Lock()
        self._reader = None
        self._stdin_closed = False

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = CREATE_NO_WINDOW
        try:
            self.proc = subprocess.Popen(
                self.argv,
                cwd=self.workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,  # inherit: the child's stderr IS the engine's stderr
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
                **kw,
            )
        except OSError as exc:
            raise CaptureChildError("cannot spawn capture child %r: %s" % (self.argv[0], exc))
        self._reader = threading.Thread(target=self._pump, name="cap-pump", daemon=True)
        self._reader.start()
        return self

    def _emit_diag(self, line):
        self.diag_lines += 1
        self.last_diag = line
        if self.diag:
            self.diag("[%s] %s" % (self.tag, line))

    def _pump(self):
        """Reader thread: every stdout line is a reply or a diagnostic."""
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                break
            if self.first_line_at is None:
                self.first_line_at = time.time()
            kind, val = classify(line)
            if kind == "reply":
                # Protocol travels inside this process only. It must never be
                # echoed to stderr -- that would put protocol on a channel the
                # contract reserves for diagnostics.
                self.replies.put(val)
            else:
                self._emit_diag(val)
        try:
            self.proc.stdout.close()
        except Exception:
            pass

    # -- state -------------------------------------------------------------
    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    @property
    def pid(self):
        return None if self.proc is None else self.proc.pid

    # -- command side ------------------------------------------------------
    def _send(self, obj):
        if self._stdin_closed:
            raise CaptureChildError("capture child stdin is closed")
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        with self._io_lock:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()

    def next_reply(self, timeout=None):
        try:
            return self.replies.get(timeout=timeout)
        except queue.Empty:
            return None

    def request(self, cmd, timeout=30.0, **payload):
        """Send {"cmd": ...} and return the child's next reply object.

        ping/cut are the only traffic on that channel, so the next JSON object
        IS the answer; a reply carrying ok=false is raised as an error with the
        child's own words (both the real child and the stub use that shape).
        """
        if not self.alive:
            raise CaptureChildError("capture child is not running (rc=%r)" % (self.exit_code,))
        self._send(dict(cmd=cmd, **payload))
        deadline = time.monotonic() + max(0.05, timeout)
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise CaptureChildError("capture child did not answer %r within %.1fs" % (cmd, timeout))
            reply = self.next_reply(left)
            if reply is None:
                raise CaptureChildError("capture child closed stdout while awaiting %r" % (cmd,))
            if reply.get("ok") is False:
                raise CaptureChildError("capture child refused %r: %s" % (cmd, reply.get("error")))
            return reply

    def ping(self, timeout=10.0):
        return self.request("ping", timeout=timeout)

    def cut(self, timeout=90.0):
        return self.request("cut", timeout=timeout)

    def counts(self):
        return {"diag_lines": self.diag_lines, "replies": self.replies.qsize()}

    # -- shutdown ----------------------------------------------------------
    def close_stdin(self):
        """EOF on the child's stdin: it finalises the open clip and exits."""
        if self._stdin_closed:
            return
        self._stdin_closed = True
        try:
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.stdin.close()
        except Exception:
            pass

    def wait(self, timeout=15.0):
        try:
            self.exit_code = self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        return self.exit_code

    def kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.kill()
            except Exception:
                pass

    def close(self, grace=8.0):
        """Graceful shutdown: stdin EOF, wait, then kill. Never leave a child."""
        self.close_stdin()
        rc = self.wait(grace)
        if rc is None:
            self._emit_diag("child ignored stdin EOF after %.1fs -- TerminateProcess" % grace)
            self.kill()
            rc = self.wait(5.0)
        if self._reader:
            self._reader.join(timeout=3.0)
        self.exit_code = rc
        return rc
