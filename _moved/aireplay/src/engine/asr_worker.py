"""The Engine's ASR side: a BOUNDED worker that never applies backpressure.

CAPTURE NEVER WAITS FOR AI. That law is enforced here structurally, not by
politeness: the job queue is bounded, and when it is full the job is DROPPED --
counted, and reported in every health event -- instead of blocking the caller.
The Engine's ring keeps writing while the ASR side stalls or dies; the proof is
one of the gate's arms (ARM-C: a stalled child must not stop a single frame).

Each job is a FRESH subprocess of the ASR side's own CLI
(python -m asr.transcribe), which is that side's contract: one JSON object per
line on stdout, diagnostics on stderr, exit 0 ok / 2 bad input. The worker runs
it in EVENT mode (no --json) on purpose: the per-segment rows the spine wants
(speech_segment.t0/t1/text) are only printed as {"type":"segment",...} events,
and --json suppresses them (measured: src/asr/transcribe.py prints
type=segment/level/done lines; --json prints exactly one line, the done object).
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time

CREATE_NO_WINDOW = 0x08000000


class AsrJob(object):
    __slots__ = ("clip_id", "path", "submitted_at")

    def __init__(self, clip_id, path):
        self.clip_id = clip_id
        self.path = path
        self.submitted_at = time.time()


class AsrResult(object):
    __slots__ = ("clip_id", "path", "state", "text", "segments", "metrics", "error",
                 "rc", "infer_s", "submit_s", "started_at", "ended_at")

    def __init__(self, job):
        self.clip_id = job.clip_id
        self.path = job.path
        self.state = "dropped"
        self.text = ""
        self.segments = []
        self.metrics = {}
        self.error = ""
        self.rc = None
        self.infer_s = None
        self.submit_s = time.time() - job.submitted_at
        self.started_at = None
        self.ended_at = None

    def as_dict(self):
        return {
            "clip_id": self.clip_id,
            "path": self.path,
            "state": self.state,
            "n_segments": len(self.segments),
            "chars": len(self.text),
            "error": self.error,
            "rc": self.rc,
            "infer_s": self.infer_s,
            "submit_s": round(self.submit_s, 3),
        }


def parse_asr_stream(text):
    """Split the ASR child's stdout into (segments, done, noise_count).

    The channel is MIXED by nature (10 Hz level events when --level is on), so
    an unparseable line is counted, never fatal.
    """
    segments = []
    done = None
    noise = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            noise += 1
            continue
        if not isinstance(obj, dict):
            noise += 1
            continue
        t = obj.get("type")
        if t == "segment":
            segments.append(obj)
        elif t == "done":
            done = obj
        else:
            noise += 1
    return segments, done, noise


class AsrWorker(threading.Thread):
    """One-at-a-time ASR side with a bounded queue and drop-with-counter."""

    def __init__(self, argv, cwd=None, on_result=None, queue_size=32, timeout=900.0, diag=None):
        super(AsrWorker, self).__init__(name="asr-worker", daemon=True)
        self.argv = [str(a) for a in argv]
        self.cwd = cwd
        self.on_result = on_result or (lambda res: None)
        self.timeout = float(timeout)
        self.diag = diag
        self._q = queue.Queue(maxsize=max(1, int(queue_size)))
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.stats = {
            "submitted": 0, "dropped": 0, "done": 0, "failed": 0, "dead": 0,
            "segments": 0, "infer_s_max": 0.0, "wait_s_max": 0.0,
        }

    # -- public ------------------------------------------------------------
    def submit(self, clip_id, path):
        """Offer a job. NEVER blocks, NEVER raises. False == dropped."""
        with self._lock:
            stats = self.stats
            stats["submitted"] += 1
        job = AsrJob(clip_id, path)
        try:
            self._q.put_nowait(job)
            return True
        except queue.Full:
            with self._lock:
                stats["dropped"] += 1
            return False

    def has_pending(self):
        """True while a job is queued, or a child is still running.

        Used at Engine shutdown: the Engine applies whatever already landed and
        then LEAVES -- a stalled ASR child never holds the shutdown hostage.
        """
        if self._q.qsize() > 0:
            return True
        with self._lock:
            st = self.stats
        settled = st.get("done", 0) + st.get("failed", 0) + st.get("dead", 0)
        return st.get("submitted", 0) > settled

    def snapshot(self):
        with self._lock:
            d = dict(self.stats)
        d["queued"] = self._q.qsize()
        d["infer_s_max"] = round(d["infer_s_max"], 3)
        d["wait_s_max"] = round(d["wait_s_max"], 3)
        return d

    def stop(self, join_timeout=5.0):
        self._stop.set()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=join_timeout)

    # -- worker ------------------------------------------------------------
    def run(self):
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            res = self._run_job(job)
            with self._lock:
                st = self.stats
                if res.state == "ok":
                    st["done"] += 1
                    st["segments"] += len(res.segments)
                    if res.infer_s:
                        st["infer_s_max"] = max(st["infer_s_max"], res.infer_s)
                elif res.state == "dead":
                    st["dead"] += 1
                else:
                    st["failed"] += 1
                st["wait_s_max"] = max(st["wait_s_max"], res.submit_s)
            try:
                self.on_result(res)
            except Exception as exc:  # a bad callback must not kill the worker
                self._d("asr result callback failed: %r" % (exc,))

    def _run_job(self, job):
        res = AsrResult(job)
        res.started_at = time.time()
        if not os.path.isfile(job.path):
            res.state = "failed"
            res.error = "clip file vanished before ASR ran"
            return res
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(
                self.argv + [job.path],
                cwd=self.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                **kw,
            )
        except OSError as exc:
            res.state = "dead"
            res.error = "cannot spawn ASR child: %s" % (exc,)
            res.ended_at = time.time()
            return res
        try:
            out, err = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                out, err = proc.communicate(timeout=10.0)
            except Exception:
                out, err = "", ""
            res.state = "dead"
            res.error = "ASR child stalled past %.0fs -- killed (capture must not have waited)" % self.timeout
            res.rc = proc.returncode
            res.ended_at = time.time()
            self._d("asr %s: %s" % (job.clip_id, res.error))
            return res
        res.ended_at = time.time()
        res.rc = proc.returncode
        segments, done, noise = parse_asr_stream(out)
        if proc.returncode != 0 or done is None:
            res.state = "failed" if proc.returncode == 2 else "dead"
            tail = (err or "").strip().splitlines()[-1:] if err else []
            res.error = "asr rc=%s %s" % (proc.returncode, tail[0] if tail else "(no diagnostic)")
            return res
        res.state = "ok"
        res.segments = segments
        res.text = str(done.get("text") or "")
        res.metrics = {
            "n_segments": done.get("n_segments"),
            "audio_s": done.get("audio_s"),
            "rtfx_infer": done.get("rtfx_infer"),
            "model_load_s": done.get("load_s"),
            "rss_after_load_mb": done.get("rss_after_load_mb"),
        }
        res.infer_s = done.get("infer_s")
        return res

    def _d(self, msg):
        if self.diag:
            self.diag("[asr] " + msg)
