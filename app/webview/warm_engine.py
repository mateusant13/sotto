"""WARM ENGINE -- the graph that is already loaded when the shell asks for it.

THE QUESTION THIS FILE ANSWERS. The owner's first caption of the day was
measured at **65 037 ms** (``_main/webview-run.log``, ``_main/time-to-first-
caption-oracle.py``) and the isolated cold boot at **9 014 ms** even with the
desktop hold removed (``_main/receipt-20261104-boot-fast.md``). Both numbers
have the same shape: the shell cannot caption until a process it spawned has
read 1.9 GB of weights. The design contract
(``state/design/warm-worker-20261104.md``) replaces that with a process the
shell does not own, already holding the graph, that the shell can only
*attach* to. This file is that process.

WHAT IT IS, PRECISELY.

  * a Task-Scheduler-created process (R1: it is never a ``Popen`` of the
    shell, so ``BRIDGE.stop`` has no PID to kill and the measured
    ``KILL_ON_JOB_CLOSE`` job-object cure is not weakened);
  * the owner of ONE named pipe created with ``FILE_FLAG_FIRST_PIPE_INSTANCE``
    and ONE mutex held for the process lifetime, plus ``_main/warm-engine.pid``
    carrying ``pid + start time`` (the four twin locks, A6);
  * a holder of ``StreamAsr`` -- the graph AND the front end, the definition of
    ``loaded`` the design fixes in §4 -- loaded through the worker's OWN
    construction path so there is exactly one loader in the tree;
  * a speaker of the worker's EXACT line protocol: one JSON object per line,
    flushed, with the same ``caption`` / ``status`` / ``stats`` / ``meter``
    kinds the shell already parses.

WHAT IT IS NOT. It does not paint, it has no window, it writes no history (the
shell is the only writer, INV-6), and it never decodes while unattached (R7).
Its state is a log and a file.

THE VETO. G1..G4 (design §5) are the four points where it reads the SAME two
sources the worker reads -- ``LoadProbe.reread()`` and the shell's published
``shed`` -- takes the WORSE, and refuses. ``unknown`` is not permission to
preload: ``level_for_load(None)`` is ``leve`` ("a failed measurement never
disables an engine"), which is correct for a LIVE engine and wrong for a 1.9 GB
preload, so G1 additionally requires a real measurement. There is deliberately
no environment variable, CLI flag or task argument that skips them (R6).

Run: ``python -u app/webview/warm_engine.py`` (the task launches it with
``pythonw``; the ``-u`` is for the manual/CLI runs). ``--no-model`` is an
INSTRUMENT switch that refuses to build weights -- it cannot make anything
load that the gate would refuse, which is the direction R6 is about.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
MAIN = os.path.join(ROOT, "_main")

import warm_pipe  # noqa: E402  -- same directory, imported by path

# ── the contract's constants, all named here so the oracle can pin them ──────
SCHEMA = warm_pipe.SCHEMA

#: Park TTL. The SAME value and the SAME meaning as the worker's
#: ``IDLE_HOLD_MAX_S = 600.0``: a held process that nobody attached to is a
#: 1.9 GB leak with a timer, and ten minutes is the worker's own answer.
WARM_PARK_TTL_S = 600.0
#: How long ``muito-alta`` must persist before the weights go (G4).
WARM_RELEASE_S = 120.0
#: A deferred load retries on this cadence; the gate, not the clock, decides.
WARM_LOAD_RETRY_S = 30.0
#: Replayed audio older than this is HISTORY ONLY, never painted (INV-5/R11).
WARM_BACKLOG_LIVE_MS = 2000
#: The RAM ring of raw PCM held while the tap is open (mode C). 8 s at 16 kHz
#: mono float32 = 512 000 B, measured arithmetic from the design §4.
WARM_RING_S = 8.0
TARGET_SR = 16000
#: Bounded writer queue. Meter and stats are dropped first, captions never are
#: dropped silently (they switch the stream to history-only and say so).
WARM_SEND_QUEUE = 512

PID_FILE = os.path.join(MAIN, "warm-engine.pid")
LOG_FILE = os.path.join(MAIN, "warm-engine.log")
VISIBILITY_FILE = os.path.join(MAIN, "panel-visibility.json")

#: The published ``shed`` is trusted only while it is this young. The worker's
#: own reader carries the same window (``staleAfterSeconds: 9.0`` in the file).
SHED_STALE_S = 9.0


# ── identity ─────────────────────────────────────────────────────────────────
def sha256_file(path):
    import hashlib

    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def worker_path(root=ROOT):
    return os.path.join(root, "worker", "sotto_worker.py")


def plugin_sha256(root=ROOT):
    """The digest the shell compares against the file on disk (F1).

    A warm engine is BY CONSTRUCTION older than the code, so freshness has to be
    a field and not an assumption. ``UNKNOWN`` is not ``FRESH``: an unreadable
    file returns ``""`` and the shell refuses it.
    """
    return sha256_file(worker_path(root))


def model_dir_from(root=ROOT, given=None):
    if given:
        return given
    try:
        cfg = json.load(open(os.path.join(root, "worker", "config.json"),
                             encoding="utf-8"))
        value = (cfg.get("model") or {}).get("dir")
        if value:
            return value if os.path.isabs(value) else os.path.join(root, "worker", value)
    except (OSError, ValueError):
        pass
    return os.path.join(root, "worker", "models", "nemotron-3.5-asr-ptbr-onnx-int4")


def pid_alive(pid):
    try:
        import psutil

        return bool(pid) and psutil.pid_exists(int(pid))
    except Exception:  # noqa: BLE001
        try:
            os.kill(int(pid), 0)
            return True
        except Exception:  # noqa: BLE001
            return False


def process_start_time(pid=None):
    """The start time that makes a PID an ARTEFACT (AGENTS rule: pid + start time)."""
    try:
        import psutil

        return "%0.3f" % psutil.Process(int(pid or os.getpid())).create_time()
    except Exception:  # noqa: BLE001
        return ""


def read_pid_file(path=PID_FILE):
    try:
        with open(path, encoding="utf-8") as handle:
            parts = handle.readline().rstrip("\n").split("\t")
    except OSError:
        return None
    if len(parts) < 2:
        return None
    try:
        pid = int(parts[0])
    except ValueError:
        return None
    return {"pid": pid, "started": parts[1], "session": parts[2] if len(parts) > 2 else "",
            "model_key": parts[3] if len(parts) > 3 else "",
            "plugin_sha256": parts[4] if len(parts) > 4 else "",
            "started_at": parts[5] if len(parts) > 5 else ""}


# ── the gate: measured load + published shed, take the worse ─────────────────
def _levels():
    import load_shedding as module

    return module


def read_published_shed(path=VISIBILITY_FILE, now=None, stale_s=SHED_STALE_S):
    """The shell's published level, and whether it is still a measurement.

    Absent, unreadable or stale is ``shed=None`` -- which is NOT a level. The
    caller then decides on the measured half alone; inventing ``leve`` from a
    missing file would be exactly the "unknown is permission" mistake G1 exists
    to refuse.
    """
    out = {"shed": None, "fresh": False, "age_s": None, "written_at": None}
    try:
        payload = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return out
    level = payload.get("shed")
    if level not in ("leve", "alta", "muito-alta"):
        return out
    out["shed"] = level
    out["written_at"] = payload.get("writtenAt")
    stamp = payload.get("writtenAtEpoch") or payload.get("writtenAt")
    age = None
    if isinstance(stamp, (int, float)):
        age = max(0.0, (time.time() if now is None else now) - float(stamp))
    elif isinstance(payload.get("age_s"), (int, float)):
        age = max(0.0, float(payload["age_s"]))
    if age is None:
        # No clock in the file -- the shell's writer carries `writtenAt` as ISO.
        # Without an age the level cannot be called fresh, and a level that
        # cannot be dated is not allowed to PRELOAD anything.
        out["fresh"] = False
        return out
    out["age_s"] = age
    limit = payload.get("staleAfterSeconds")
    out["fresh"] = age <= (float(limit) if isinstance(limit, (int, float)) else stale_s)
    return out


def worst_level(*levels):
    known = [lvl for lvl in levels if lvl in ("leve", "alta", "muito-alta")]
    if not known:
        return None
    order = ("leve", "alta", "muito-alta")
    return max(known, key=order.index)


def load_gate(probe=None, visibility_path=VISIBILITY_FILE, now=None):
    """G1..G4's single question: may the engine take a step that costs the box?

    Returns ``{level, allowed, measured, commit_pct, cpu_pct, shed, shed_fresh,
    why}``. ``allowed`` is the permission for a PRELOAD and it requires BOTH
    halves: a real measurement (``commit_pct is not None``) and a worst level of
    ``leve``. ``unknown`` therefore refuses, which is the deliberate inversion of
    ``level_for_load(None)`` documented in the design §5.
    """
    module = _levels()
    probe = probe or module.LoadProbe()
    commit, cpu, _fresh = probe.reread()
    level = module.level_for_load(commit, cpu)
    published = read_published_shed(visibility_path, now=now)
    worst = worst_level(level, published["shed"] if published["fresh"] else None)
    measured = commit is not None or cpu is not None
    if commit is None and cpu is None:
        why = "no-measurement"
    elif worst in module.PARK_LEVELS:
        why = "shed-%s" % worst
    elif not measured:
        why = "no-measurement"
    else:
        why = "calm"
    return {
        "level": worst or level,
        "allowed": bool(measured and worst == "leve"),
        "measured": bool(measured),
        "commit_pct": commit,
        "cpu_pct": cpu,
        "shed": published["shed"],
        "shed_fresh": published["fresh"],
        "shed_age_s": published["age_s"],
        "why": why,
    }


def replay_is_history(audio_ms, limit_ms=WARM_BACKLOG_LIVE_MS):
    """THE ONE definition of "too old to paint" (INV-5/R11).

    The shell calls THIS, not its own comparison: two definitions of the replay
    window would be two truths, and the one that drifts is always the one that
    paints. `>` and not `>=`: a line at exactly the budget is still inside it
    (the same boundary style as `CAPTION_PAINT_LAG ... over=true`).
    """
    try:
        return int(audio_ms) > int(limit_ms)
    except (TypeError, ValueError):
        return True


# ── the ring ─────────────────────────────────────────────────────────────────
class PcmRing:
    """8 s of raw PCM, newest-first on read -- mode C's answer to "audio existed".

    A caption is a fact about audio, so the only honest way to produce one
    before the shell is up is to hold the audio that was already playing. The
    read order is NEWEST FIRST by design (§4): if a full ring is replayed, the
    line the owner is waiting for is the recent one, not the beginning of the
    window.
    """

    def __init__(self, seconds=WARM_RING_S, rate=TARGET_SR):
        import numpy as np

        self.np = np
        self.rate = int(rate)
        self.size = max(1, int(round(float(seconds) * self.rate)))
        self._buf = np.zeros(self.size, dtype="float32")
        self._start = 0          # index of the OLDEST sample
        self.count = 0           # valid samples, <= size

    def push(self, samples):
        np = self.np
        data = np.asarray(samples, dtype="float32").reshape(-1)
        if data.size == 0:
            return
        if data.size >= self.size:
            data = data[-self.size:]
            self._buf[:] = data
            self._start = 0
            self.count = self.size
            return
        end = (self._start + self.count) % self.size
        first = min(data.size, self.size - end)
        self._buf[end:end + first] = data[:first]
        if first < data.size:
            self._buf[:data.size - first] = data[first:]
        self.count = min(self.size, self.count + data.size)
        if self.count == self.size:
            self._start = (self._start + data.size) % self.size

    def tail(self, seconds=None):
        """The valid samples, OLDEST FIRST (the ring's physical order fixed)."""
        if self.count == 0:
            return self._buf[:0]
        if self.count < self.size:
            return self._buf[:self.count].copy()
        return self.np.concatenate((self._buf[self._start:], self._buf[:self._start]))

    def newest_first_chunks(self, chunk):
        """[(audio_ms, samples)] newest chunk first, each exactly ``chunk`` long."""
        data = self.tail()
        chunk = int(chunk)
        if chunk <= 0 or data.size < chunk:
            return []
        out = []
        end = data.size
        while end - chunk >= 0:
            age_ms = int(round((data.size - end) * 1000.0 / self.rate))
            out.append((age_ms, data[end - chunk:end].copy()))
            end -= chunk
        return out


# ── the loaders ──────────────────────────────────────────────────────────────
def import_worker(root=ROOT):
    """Import ``worker/sotto_worker.py`` by PATH, without entering its sys.path.

    The warm engine must run the SAME construction the worker runs. Copying a
    loader would create a second definition of "loaded", and the design's §4
    definition is what makes attach→caption cost 0.3 s instead of 5 s.
    """
    import importlib.util

    path = worker_path(root)
    spec = importlib.util.spec_from_file_location("sotto_worker_warm_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkerGraphLoader:
    """Graph + front end, built through the worker's own path (the real load)."""

    def __init__(self, root=ROOT, model_dir=None):
        self.root = root
        self.model_dir = model_dir or model_dir_from(root)

    def load(self):
        t0 = time.time()
        worker = import_worker(self.root)
        worker._add_cuda_dll_dirs()
        providers, _available, note, _probe = worker.choose_providers(None, self.model_dir)
        asr = worker.StreamAsr(self.model_dir, providers=providers, use_vad=True,
                               lang_id=None, on_sessions_ready=None)
        asr.load_s = time.time() - t0
        asr.provider_note = note
        # "loaded" is graph AND front end (design §4): an engine that stopped
        # after the sessions would pay the 1.7-3.4 s genai build at attach,
        # which is the trap that definition closes.
        asr.start_frontend()
        asr._join_frontend()
        return asr, (time.time() - t0) * 1000.0

    def unload(self, _asr=None):
        return None


class FakeGraph:
    """The INSTRUMENT graph -- no weights, no device, no window.

    It exists so the oracle can drive the state machine, the gate and the pipe
    without loading 1.9 GB in a battery step. It is reachable ONLY by the
    explicit ``--no-model`` switch; there is no env and no flag that makes the
    GATE allow a real load.
    """

    name = "warm-fake"
    chunk = 8960
    chunk_continues = False
    gate = None
    load_s = 0.0

    def run_chunk(self, _pcm, speech=None, account=True):
        return "", 0

    def reset_stream_state(self):
        return None

    def reset_frontend(self):
        return None

    def start_frontend(self):
        return None

    def _join_frontend(self):
        return None


class FakeLoader:
    def __init__(self, delay_s=0.0):
        self.delay_s = float(delay_s)

    def load(self):
        t0 = time.time()
        if self.delay_s:
            time.sleep(self.delay_s)
        return FakeGraph(), (time.time() - t0) * 1000.0

    def unload(self, _asr=None):
        return None


# ── the tap (mode C, OPT-IN) ─────────────────────────────────────────────────
class WarmTap:
    """One WASAPI loopback client that feeds the ring, and nothing else.

    It runs the worker's OWN ladder function (``_open_tap_bounded``) so the
    measured cures travel with it: the bounded open (a blocking driver cannot
    hold the ladder), the silent-desktop hold, and the client identity. While
    unattached it opens ONCE per TTL window -- a rotation nobody listens to is
    pure hitch (design §4, A9).
    """

    def __init__(self, asr_chunk=8960, on_block=None, device=None, target_pid=None,
                 worker=None, log=None):
        self.chunk = asr_chunk
        self.on_block = on_block or (lambda _pcm: None)
        self.device = device
        self.target_pid = target_pid
        self.worker = worker
        self.log = log or (lambda _m: None)
        self.tap = None
        self.source = None

    def open(self):
        worker = self.worker or import_worker(ROOT)
        try:
            candidates = worker.device_candidates(None, self.device, self.target_pid)
        except Exception as exc:  # noqa: BLE001 -- no audio stack is a fact, not a crash
            self.log("WARM_TAP_FAILED why=candidates error=%r" % (exc,))
            return False
        if not candidates:
            self.log("WARM_TAP_FAILED why=no-candidates")
            return False
        tap, error = worker._open_tap_bounded(candidates[0], self._on_pcm)
        if tap is None:
            self.log("WARM_TAP_FAILED why=open error=%r" % (error,))
            return False
        self.tap = tap
        self.source = getattr(tap, "source", None)
        self.log("WARM_TAP_OPEN mode=warm-tap while_unattached=true source=%s"
                 % self.source)
        self.log("WARM_CAPTURE_STARTED device=%s source=%s"
                 % (getattr(tap, "name", None) or "auto", self.source))
        return True

    def _on_pcm(self, indata, frames=None, time_info=None, status=None):
        try:
            import numpy as np

            block = np.asarray(indata, dtype="float32").reshape(-1).copy()
        except Exception:  # noqa: BLE001
            return
        try:
            rate = int(getattr(getattr(self.tap, "stream", None), "samplerate", TARGET_SR))
        except Exception:  # noqa: BLE001
            rate = TARGET_SR
        try:
            if rate != TARGET_SR:
                worker = self.worker or import_worker(ROOT)
                block = worker.resample_to_16k(block, rate)
        except Exception:  # noqa: BLE001
            return
        self.on_block(block)

    def close(self):
        tap, self.tap = self.tap, None
        if tap is None:
            return
        try:
            tap.stream.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            tap.stream.close()
        except Exception:  # noqa: BLE001
            pass
        self.log("WARM_TAP_CLOSED source=%s" % self.source)


# ── the attached session: replay newest-first, then live ─────────────────────
class AttachedSession:
    """One attach = one stream. Replay first, then the tap's audio, in order.

    The decode thread is the ONLY consumer of the ring and the queue, so there
    is one order and one writer. It emits the worker's line kinds through
    ``engine.emit_worker``.
    """

    def __init__(self, engine, asr, live=True, device=None, target_pid=None,
                 replay=True):
        self.engine = engine
        self.asr = asr
        self.live = bool(live)
        self.device = device
        self.target_pid = target_pid
        self.replay = bool(replay)
        self.worker = None
        self.former = None
        self.tap = None
        self.queue = None
        self.stop = threading.Event()
        self.thread = None
        self.threads = []
        self.chunks = 0
        self.replayed = 0
        self.blocked_dropped = 0
        self.last_caption_at = 0.0
        self.started_at = 0.0

    # -- lifecycle ----------------------------------------------------------
    def start(self):
        import queue

        self.queue = queue.Queue(maxsize=256)
        self.started_at = time.monotonic()
        worker = import_worker(self.engine.root)
        self.worker = worker
        self.asr.reset_stream_state()
        self.asr.reset_frontend()
        self.former = worker.LineFormer(min_chars=1, emit_partial=True)
        self.thread = threading.Thread(target=self._decode_loop,
                                       name="warm-decode", daemon=True)
        self.thread.start()
        if self.live:
            # THE TAP OPENS OFF THE ATTACH PATH: a bounded open can take ~1.8 s
            # on this box (measured in the smoke run), and the design's attach
            # deadline is 500 ms. Reply first, tap after -- the handshake is not
            # an audio operation.
            threading.Thread(target=self._open_tap, name="warm-attach-tap",
                             daemon=True).start()
        return True

    def _open_tap(self):
        if not self.engine.allow_model:
            # INSTRUMENT (`--no-model`): there is no real graph to feed, so
            # opening an endpoint would be a device touch with no consumer --
            # and the oracle's acceptance forbids touching audio at all.
            self.engine.log("WARM_TAP_SKIPPED why=no-model")
            return False
        gate = self.engine.gate()
        if not gate["allowed"]:
            # G2: `alta`/`muito-alta` means the live engine must not even HOLD a
            # tap (the owner's "desliga nemotron, so parakeet").
            self.engine.log("WARM_TAP_REFUSED why=g2 level=%s commit=%s cpu=%s"
                            % (gate["level"], gate["commit_pct"], gate["cpu_pct"]))
            self.engine.emit_status(state="warm-tap-refused", level=gate["level"],
                                    shed=gate["shed"])
            return False
        tap = WarmTap(self.asr.chunk, self._on_block, self.device,
                      self.target_pid, worker=self.worker,
                      log=self.engine.log)
        self.tap = tap
        if not tap.open():
            if self.tap is tap:
                self.tap = None
            return False
        # THE LOCAL, NOT `self.tap`: a detach can clear the attribute between
        # `open()` and this line (measured in the M6 neg-arm run: AttributeError
        # on None.source), and a log line must not be the thing that crashes an
        # engine whose tap is healthy.
        self.engine.emit_status(state="warm-tap", source=tap.source)
        return True

    def _on_block(self, block):
        if self.stop.is_set() or self.queue is None:
            return
        try:
            self.queue.put_nowait(block)
        except Exception:  # noqa: BLE001 -- a full queue is dropped audio, counted
            self.blocked_dropped += 1

    # -- decode -------------------------------------------------------------
    def _emit_events(self, events, audio_ms=None):
        for event in line_events(self.worker, events):
            meta = dict(event)
            if audio_ms is not None:
                meta["src"] = "warm-replay"
                meta["audio_ms"] = int(audio_ms)
                meta["tap_ms"] = int(time.time() * 1000.0 - int(audio_ms))
            else:
                meta["src"] = "warm-engine"
            self.engine.emit_worker({"type": "caption", "text": meta.pop("text", ""),
                                     **meta})
            self.last_caption_at = time.monotonic()

    def _decode_one(self, seg, start, end, audio_ms=None):
        try:
            speech = True if getattr(self.asr, "gate", None) is None \
                else self.asr.gate.is_speech(seg)
            text, _n = self.asr.run_chunk(seg, speech=speech)
        except Exception as exc:  # noqa: BLE001 -- a dead decode says so, then detaches
            self.engine.emit_status(state="error", stage="chunk", detail=repr(exc))
            self.stop.set()
            return
        wall = time.time()
        self._emit_events(self.former.push(text, start, end,
                                           continues=getattr(self.asr, "chunk_continues", False),
                                           wall=wall), audio_ms=audio_ms)
        if not (text or "").strip():
            self._emit_events(self.former.publish_on_silence(end), audio_ms=audio_ms)
        self.chunks += 1

    def _decode_loop(self):
        # REPLAY FIRST (mode C): the ring is audio that existed before the shell.
        if self.replay:
            for audio_ms, seg in self.engine.ring.newest_first_chunks(self.asr.chunk):
                if self.stop.is_set():
                    break
                start = round((self.replayed + 1) * self.asr.chunk / float(TARGET_SR), 2)
                self._decode_one(seg, start, start, audio_ms=audio_ms)
                self.replayed += 1
            if self.replayed:
                self.engine.log("WARM_BACKLOG_DECODED n=%d newest_first=true" % self.replayed)
                self.engine.emit_status(state="warm-replay-done", n=self.replayed)
        buf = None
        np = None
        try:
            import numpy as np  # noqa: F811 -- local, for the live half only
            buf = np.zeros(0, dtype="float32")
        except Exception:  # noqa: BLE001
            buf = None
        while not self.stop.is_set():
            if self.queue is None:
                break
            try:
                block = self.queue.get(timeout=0.25)
            except Exception:  # noqa: BLE001 -- empty
                continue
            if buf is None:
                continue
            buf = np.concatenate([buf, block])
            while len(buf) >= self.asr.chunk:
                seg = buf[: self.asr.chunk]
                buf = buf[self.asr.chunk:]
                start = round((self.chunks + self.replayed) * self.asr.chunk
                              / float(TARGET_SR), 2)
                self._decode_one(seg, start, start + round(self.asr.chunk / float(TARGET_SR), 2))
        # A tail is not dropped: the held line closes here, once.
        try:
            if self.former is not None:
                self._emit_events(self.former.flush())
        except Exception:  # noqa: BLE001
            pass

    def detach(self, why="peer-eof"):
        self.stop.set()
        if self.tap is not None:
            self.tap.close()
            self.tap = None
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        try:
            self.queue = None
        except Exception:  # noqa: BLE001
            pass
        return why


def line_events(worker, events):
    fn = getattr(worker, "line_events", None)
    if fn is not None:
        return fn(events)
    out = []
    for ev in events or ():
        e = dict(ev)
        e.pop("closed", None)
        e["final"] = bool(e.get("final"))
        out.append(e)
    return out


# ── the writer: never blocks the audio or the decode thread ──────────────────
class Sender:
    """Bounded queue drained by one writer thread (design §3).

    The shell can stop reading at any instant (a crash, a busy page, a second
    shell). With an engine that outlives the shell this is ROUTINE, so the write
    must never be allowed to stall capture: meter/stats drop first and are
    counted, captions drop only when the deque is full and the stream is then
    declared ``history-only``.
    """

    def __init__(self, send_fn, log, capacity=WARM_SEND_QUEUE):
        self.send_fn = send_fn
        self.log = log
        self.capacity = int(capacity)
        self.queue = collections.deque()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.dropped = collections.Counter()
        self.overflow = False
        self.thread = threading.Thread(target=self._run, name="warm-send", daemon=True)
        self.thread.start()

    def put(self, text, kind="line"):
        with self.lock:
            if len(self.queue) >= self.capacity:
                if kind in ("meter", "stats"):
                    self.dropped[kind] += 1
                    return False
                if kind == "caption":
                    if not self.overflow:
                        self.overflow = True
                        self.log("WARM_SEND_OVERFLOW class=caption "
                                 "dropped=%d" % sum(self.dropped.values()))
                    self.dropped["caption"] += 1
                    return False
                # envelope/status: the oldest non-caption goes, the envelope stays
                self.queue.popleft()
                self.dropped["older"] += 1
            self.queue.append(text)
            return True

    def _run(self):
        while not self.stop.is_set():
            with self.lock:
                text = self.queue.popleft() if self.queue else None
                dropped = sum(self.dropped.values())
                self.dropped.clear()
            if dropped:
                self.log("WARM_SEND_DROPPED class=meter n=%d" % dropped)
            if text is None:
                self.stop.wait(0.05)
                continue
            try:
                self.send_fn(text)
            except Exception as exc:  # noqa: BLE001 -- a dead peer is not a crash
                self.log("WARM_SEND_FAILED error=%r" % (exc,))
                self.stop.wait(0.2)

    def flush(self, timeout=1.0):
        """Drain the queue into the pipe BEFORE the pipe is closed.

        Measured by the oracle (arm 15/17): a refusal envelope queued a
        microsecond before `quit` was lost, so the shell read "pipe-timeout"
        for what was in fact `WARM_HELLO_REFUSED why=model-mismatch` -- the
        engine exited, the client saw a closed pipe, and the REASON existed
        only in a log nobody was reading. A last word must be synchronous
        enough to survive the close.
        """
        end = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() < end:
            with self.lock:
                if not self.queue:
                    return True
            self.stop.wait(0.01)
        with self.lock:
            return not self.queue

    def close(self, drain=1.0):
        try:
            self.flush(drain)
        except Exception:  # noqa: BLE001 -- a dead peer must not block a close
            pass
        self.stop.set()
        try:
            self.thread.join(timeout=0.5)
        except Exception:  # noqa: BLE001
            pass


# ── the engine ───────────────────────────────────────────────────────────────
class WarmEngine:
    """The process. Owns the locks, the pipe, the graph, the ring and the gate."""

    def __init__(self, session=None, model_dir=None, root=ROOT, loader=None,
                 log_path=None, pid_path=None, pipe=None, mutex=None,
                 park_ttl_s=WARM_PARK_TTL_S, release_s=WARM_RELEASE_S,
                 sample_interval_s=None, tap_opt_in=False, visibility_path=VISIBILITY_FILE,
                 gate_fn=None, clock=None, model_key_value=None):
        self.root = root
        self.model_dir = model_dir or model_dir_from(root, model_dir)
        self.key = model_key_value or warm_pipe.model_key(self.model_dir)
        self.session = session if session is not None else warm_pipe.session_id()
        self.pipe_name = pipe or warm_pipe.pipe_name(self.key, self.session)
        self.mutex_name = mutex or warm_pipe.mutex_name(self.key, self.session)
        self.pid_path = pid_path or PID_FILE
        self.log_path = log_path or LOG_FILE
        self.park_ttl_s = float(park_ttl_s)
        self.release_s = float(release_s)
        self.tap_opt_in = bool(tap_opt_in)
        self.visibility_path = visibility_path
        self.clock = clock or time.monotonic
        self._gate_fn = gate_fn
        self.loader = loader or WorkerGraphLoader(root, self.model_dir)
        self.allow_model = not isinstance(loader, FakeLoader)

        self.asr = None
        self.load_ms = 0.0
        self.loaded_at = None
        self.state = "starting"
        self.quit = False
        self.mode = "parked-closed"
        self.started_at = time.time()
        self._next_load_at = 0.0
        self._very_high_since = None
        self._last_detach_at = self.clock()
        self._client = None
        self._conn = None
        self._conn_lock = threading.Lock()
        self._load_thread = None
        self._accept_thread = None
        self._pipe_handle = None
        self._mutex_handle = None
        self._sender = None
        self.session_obj = None
        self.ring = PcmRing()
        self._tap = None
        self.log_lock = threading.Lock()
        self._samples = 0
        self._pipelines = 0
        self._shutdown_lock = threading.Lock()
        self._shutdown_done = False

    # -- logging ------------------------------------------------------------
    def log(self, message):
        line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
        with self.log_lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        if os.environ.get("WARM_ENGINE_ECHO") == "1":
            try:
                sys.stderr.write(line + "\n")
            except Exception:  # noqa: BLE001
                pass

    # -- gate ---------------------------------------------------------------
    def gate(self):
        if self._gate_fn is not None:
            return self._gate_fn()
        self._samples += 1
        return load_gate(visibility_path=self.visibility_path)

    # -- ownership ----------------------------------------------------------
    def acquire(self):
        """The four twin locks, in the only order that has no race.

        Mutex first (kernel-released on death, so "exists" means a LIVE engine),
        then the pipe. A loser of EITHER exits 0 -- it must not linger, retry or
        start a load: a twin that loads is the double load INV-1 forbids.
        """
        self._mutex_handle, created = warm_pipe.create_mutex(self.mutex_name)
        if not created:
            self.log("WARM_TWIN_EXIT rc=0 why=mutex-exists name=%s"
                     % self.mutex_name)
            return False
        handle, reason = warm_pipe.create_first_instance(self.pipe_name,
                                                         warm_pipe.owner_sddl())
        if handle is None:
            self.log("WARM_TWIN_EXIT rc=0 why=%s name=%s"
                     % ("pipe-exists" if reason == "twin" else reason,
                        self.pipe_name))
            warm_pipe.release_mutex(self._mutex_handle)
            self._mutex_handle = None
            return False
        self._pipe_handle = handle
        return True

    def write_pid(self):
        line = "\t".join([
            str(os.getpid()), process_start_time(), str(self.session), self.key,
            plugin_sha256(self.root),
            time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        ])
        try:
            os.makedirs(os.path.dirname(self.pid_path), exist_ok=True)
            with open(self.pid_path, "w", encoding="utf-8", newline="") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            self.log("WARM_PID_WRITE_FAILED path=%s error=%r" % (self.pid_path, exc))

    def clear_pid(self):
        try:
            current = read_pid_file(self.pid_path)
            if current is not None and current["pid"] == os.getpid():
                os.remove(self.pid_path)
        except OSError:
            pass

    # -- wire ---------------------------------------------------------------
    def _raw_send(self, text):
        with self._conn_lock:
            conn = self._conn
        if conn is None:
            return
        conn.send_line(text)

    def emit_envelope(self, tag, **fields):
        payload = json.dumps(fields, ensure_ascii=False, sort_keys=True)
        self._send_text("%s %s" % (tag, payload), "status")

    def emit_worker(self, payload):
        kind = str(payload.get("type") or "status")
        text = json.dumps(payload, ensure_ascii=False)
        self._send_text(text, "caption" if kind == "caption" else kind)

    def emit_status(self, **payload):
        payload.setdefault("type", "status")
        self.emit_worker(payload)

    def _send_text(self, text, kind):
        if self._sender is None:
            return
        self._sender.put(text, kind)

    def hello(self):
        return {
            "schema": SCHEMA,
            "pid": os.getpid(),
            "started_at": self.started_at,
            "session": self.session,
            "model_key": self.key,
            "plugin_sha256": plugin_sha256(self.root),
            "loaded": self.asr is not None,
            "mode": self.mode,
            "load_ms": round(self.load_ms, 1),
            "resident_mb": self.resident_mb(),
            "pipe": self.pipe_name,
        }

    def resident_mb(self):
        try:
            import psutil

            return round(psutil.Process().memory_info().rss / (1024.0 * 1024.0), 1)
        except Exception:  # noqa: BLE001
            return None

    # -- pipe server --------------------------------------------------------
    def run(self):
        if not self.acquire():
            return 0
        try:
            self.write_pid()
            self.log("WARM_ENGINE_START pid=%d started_at=%s model=%s "
                     "plugin_sha=%s session=%s pipe=%s"
                     % (os.getpid(), time.strftime("%Y-%m-%dT%H:%M:%S"),
                        self.key, plugin_sha256(self.root), self.session,
                        self.pipe_name))
            self.log("WARM_PIPE_READY name=%s instances=1" % self.pipe_name)
            self._sender = Sender(self._raw_send, self.log)
            self.state = "unloaded"
            self._next_load_at = self.clock()
            self._accept_thread = threading.Thread(target=self._accept_loop,
                                                   name="warm-accept", daemon=True)
            self._accept_thread.start()
            while not self.quit:
                self.tick()
                time.sleep(0.1)
        finally:
            self.shutdown()
        return 0

    def _accept_loop(self):
        while not self.quit:
            handle = self._pipe_handle
            if handle is None:
                return
            if not warm_pipe.connect(handle):
                time.sleep(0.05)
                continue
            conn = warm_pipe.PipeConn(handle)
            with self._conn_lock:
                self._conn = conn
            self.log("WARM_CLIENT_ACCEPTED pid=%d" % os.getpid())
            try:
                conn.send_line("WARM_HELLO " + json.dumps(self.hello(),
                                                          ensure_ascii=False,
                                                          sort_keys=True))
                self._command_loop(conn)
            except Exception as exc:  # noqa: BLE001 -- a peer that vanished
                self.log("WARM_CLIENT_DIED error=%r" % (exc,))
            finally:
                self._on_client_lost(conn)

    def _command_loop(self, conn):
        while not self.quit:
            line = conn.readline(timeout_s=0.2)
            if line is None:
                if conn.closed:
                    return
                continue
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except ValueError:
                self.log("WARM_COMMAND_MALFORMED line=%s" % json.dumps(line[:120]))
                continue
            if self.on_command(message, conn) is False:
                return

    def _on_client_lost(self, conn):
        with self._conn_lock:
            if self._conn is conn:
                self._conn = None
        # THE SERVER HANDLE IS NOT THE CLIENT'S TO CLOSE. `PipeConn.close()`
        # closes the handle it wraps; here that handle is the server end, and a
        # closed server end cannot `ConnectNamedPipe` again -- the engine would
        # become attachable exactly once. Mark the connection dead and let the
        # accept loop disconnect the instance instead.
        conn.closed = True
        if self.quit:
            warm_pipe.disconnect(self._pipe_handle)
            return
        if self.session_obj is not None:
            why = self.session_obj.detach("peer-eof")
            self.session_obj = None
            self.mode = "parked-tap" if self._tap is not None else "parked-closed"
            self.state = self.mode
            self._last_detach_at = self.clock()
            self.log("WARM_DETACHED why=%s" % why)
            self.emit_envelope("WARM_DETACHED", why=why)
        warm_pipe.disconnect(self._pipe_handle)

    # -- commands -----------------------------------------------------------
    def on_command(self, message, conn):
        op = str(message.get("op") or "")
        if op == "quit":
            self.log("WARM_EXIT why=%s" % (message.get("why") or "quit"))
            self.quit = True
            return False
        if op == "attach":
            self.attach(message, conn)
            return True
        if op == "detach":
            why = str(message.get("why") or "shell-closing")
            if self.session_obj is not None:
                self.session_obj.detach(why)
                self.session_obj = None
            self.mode = "parked-tap" if self._tap is not None else "parked-closed"
            self.state = self.mode
            self._last_detach_at = self.clock()
            self.log("WARM_DETACHED why=%s" % why)
            self.emit_envelope("WARM_DETACHED", why=why)
            return True
        if op == "park":
            self.release(str(message.get("why") or "park"))
            return True
        if op == "release":
            self.release(str(message.get("why") or "release"))
            return True
        self.log("WARM_COMMAND_UNKNOWN op=%s" % json.dumps(op))
        return True

    def attach(self, message, conn):
        t0 = self.clock()
        expect_sha = message.get("expect_sha256")
        expect_key = message.get("model_key")
        if expect_sha and expect_sha != plugin_sha256(self.root):
            self.log("WARM_HELLO_REFUSED why=stale-code disk_sha=%s engine_sha=%s"
                     % (expect_sha, plugin_sha256(self.root)))
            self.emit_envelope("WARM_HELLO_REFUSED", why="stale-code")
            self.quit = True
            return
        if expect_key and expect_key != self.key:
            self.log("WARM_HELLO_REFUSED why=model-mismatch disk=%s engine=%s"
                     % (expect_key, self.key))
            self.emit_envelope("WARM_HELLO_REFUSED", why="model-mismatch")
            self.quit = True
            return
        if self.asr is None:
            # A load that was deferred is not permission to attach to nothing.
            self.emit_envelope("WARM_ATTACH_FAILED", why="not-loaded",
                               state=self.state)
            self.log("WARM_ATTACH_FAILED why=not-loaded state=%s" % self.state)
            return
        gate = self.gate()
        if gate["level"] in ("alta", "muito-alta"):
            # G3: the level rose between load and attach. A warm graph is not an
            # argument to override the shed -- the shell takes the batch path.
            self.log("WARM_ATTACH_SHED level=%s commit=%s cpu=%s"
                     % (gate["level"], gate["commit_pct"], gate["cpu_pct"]))
            self.mode = "attached-shed"
            self.emit_envelope("WARM_ATTACHED", ms=round((self.clock() - t0) * 1000.0, 1),
                               mode="shed", level=gate["level"], replay=0)
            self.emit_envelope("WARM_ATTACH_SHED", level=gate["level"],
                               commit=gate["commit_pct"], cpu=gate["cpu_pct"])
            return
        if self.session_obj is not None:
            # A new attach on the same pipe is a RE-attach (the shell's revive
            # path stops and starts again). The old stream is ended FIRST, so
            # there is one decoder and one order -- never two sessions painting.
            self.session_obj.detach("reattach")
            self.session_obj = None
        live = bool(message.get("live", True))
        session = AttachedSession(self, self.asr, live=live,
                                  device=message.get("device"),
                                  target_pid=message.get("target_pid"),
                                  replay=bool(message.get("replay", True)))
        session.start()
        self.session_obj = session
        self.state = "attached"
        self.mode = "attached"
        reply_mode = "warm-tap" if live else "warm-idle"
        self.emit_envelope("WARM_ATTACHED",
                           ms=round((self.clock() - t0) * 1000.0, 1),
                           mode=reply_mode, replay=session.replayed, pid=os.getpid(),
                           load_ms=round(self.load_ms, 1))
        self.log("WARM_ATTACHED ms=%.1f mode=%s"
                 % ((self.clock() - t0) * 1000.0, reply_mode))

    # -- ticks --------------------------------------------------------------
    def tick(self):
        now = self.clock()
        if self.state == "unloaded" and now >= self._next_load_at:
            self._try_load(now)
        if self.asr is not None and self.session_obj is None:
            gate = self.gate()
            if gate["level"] == "muito-alta":
                if self._very_high_since is None:
                    self._very_high_since = now
                elif (now - self._very_high_since) >= self.release_s:
                    self.release("shed", gate=gate)
            else:
                self._very_high_since = None
        # TTL only applies to a process nobody attached to. An attached engine
        # is in use; its life is the shell's life.
        if (self.session_obj is None and self.asr is not None
                and (now - self._last_detach_at) >= self.park_ttl_s):
            self.log("WARM_EXIT why=idle-expired held_s=%.1f"
                     % (now - self._last_detach_at))
            self.quit = True

    def _try_load(self, now):
        gate = self.gate()
        if not gate["allowed"]:
            # THE INVERSION: `unknown` (no measurement) is NOT permission for a
            # 1.9 GB preload. Defer, say why with the numbers, retry on cadence.
            self._next_load_at = now + WARM_LOAD_RETRY_S
            if getattr(self, "_last_defer", None) != gate["why"]:
                self._last_defer = gate["why"]
                self.log("WARM_LOAD_DEFERRED why=%s commit=%s cpu=%s shed=%s"
                         % (gate["why"], gate["commit_pct"], gate["cpu_pct"],
                            gate["shed"]))
                self.emit_envelope("WARM_LOAD_DEFERRED", why=gate["why"],
                                   commit=gate["commit_pct"], cpu=gate["cpu_pct"],
                                   shed=gate["shed"])
            return
        self.state = "loading"
        self.log("WARM_LOAD_BEGIN commit=%s cpu=%s level=%s shed=%s"
                 % (gate["commit_pct"], gate["cpu_pct"], gate["level"], gate["shed"]))
        self.emit_envelope("WARM_LOAD_BEGIN", commit=gate["commit_pct"],
                           cpu=gate["cpu_pct"], level=gate["level"], shed=gate["shed"])
        self._load_thread = threading.Thread(target=self._load_worker,
                                             name="warm-load", daemon=True)
        self._load_thread.start()

    def _load_worker(self):
        t0 = self.clock()
        try:
            asr, ms = self.loader.load()
        except Exception as exc:  # noqa: BLE001 -- say the cause, do not die silently
            self.state = "unloaded"
            self._next_load_at = self.clock() + WARM_LOAD_RETRY_S
            self.log("WARM_LOAD_FAILED error=%r" % (exc,))
            self.emit_envelope("WARM_LOAD_FAILED", error=repr(exc))
            return
        self.asr = asr
        self.load_ms = float(ms)
        self.loaded_at = self.clock()
        self.state = "parked-closed"
        self.mode = "parked-closed"
        self.log("WARM_LOAD_MS ms=%.1f resident_mb=%s"
                 % (self.load_ms, self.resident_mb()))
        self.emit_envelope("WARM_LOAD_MS", ms=round(self.load_ms, 1),
                           resident_mb=self.resident_mb())
        if self.tap_opt_in and self.session_obj is None:
            self.open_parked_tap()

    def open_parked_tap(self):
        gate = self.gate()
        if gate["level"] in ("alta", "muito-alta"):
            self.log("WARM_TAP_REFUSED why=g2 level=%s" % gate["level"])
            return False
        self._tap = WarmTap(getattr(self.asr, "chunk", 8960), self._ring_block,
                            log=self.log)
        if not self._tap.open():
            self._tap = None
            return False
        self.mode = "parked-tap"
        self.state = "parked-tap"
        return True

    def _ring_block(self, block):
        self.ring.push(block)

    def release(self, why, gate=None):
        if self.asr is None:
            return False
        ms_resident = 0.0
        if self.loaded_at is not None:
            ms_resident = (self.clock() - self.loaded_at) * 1000.0
        if self.session_obj is not None:
            self.session_obj.detach("release")
            self.session_obj = None
        if self._tap is not None:
            self._tap.close()
            self._tap = None
        try:
            self.loader.unload(self.asr)
        except Exception:  # noqa: BLE001
            pass
        self.asr = None
        self.loaded_at = None
        self.state = "unloaded"
        self.mode = "unloaded"
        self._very_high_since = None
        self._next_load_at = self.clock() + WARM_LOAD_RETRY_S
        self.log("WARM_RELEASE ms_resident=%.0f why=%s level=%s"
                 % (ms_resident, why, (gate or {}).get("level")))
        self.emit_envelope("WARM_RELEASE", why=why,
                           ms_resident=round(ms_resident, 0),
                           level=(gate or {}).get("level"))
        return True

    def shutdown(self):
        # TWICE IS ALLOWED, AND MUST NOT BLOCK (oracle arm 19: the run loop and
        # the test both called it, both entered `DisconnectNamedPipe`, and the
        # pair deadlocked for the full 60 s arm deadline). `DisconnectNamedPipe`
        # waits for the peer's pending ReadFile; a dying engine does not owe the
        # peer a disconnect -- closing the handle completes those reads with
        # ERROR_BROKEN_PIPE, which is the truth.
        with self._shutdown_lock:
            if self._shutdown_done:
                return
            self._shutdown_done = True
        self.quit = True
        if self.session_obj is not None:
            self.session_obj.detach("engine-exit")
            self.session_obj = None
        if self._tap is not None:
            self._tap.close()
            self._tap = None
        if self.asr is not None:
            try:
                self.loader.unload(self.asr)
            except Exception:  # noqa: BLE001
                pass
            self.asr = None
        if self._sender is not None:
            self._sender.close()
        with self._conn_lock:
            conn = self._conn
            self._conn = None
        if conn is not None:
            conn.closed = True
        # THE ACCEPT THREAD FIRST. `CloseHandle` waits for a pending
        # `ConnectNamedPipe` on the same handle, and with no client that wait is
        # forever (oracle arm 19: the pid file outlived the engine). Cancel the
        # wait, then join, then close.
        accept = self._accept_thread
        if accept is not None and accept.is_alive() and \
                accept is not threading.current_thread():
            warm_pipe.cancel_sync_io(accept.native_id)
            accept.join(timeout=2.0)
        warm_pipe.close_handle(self._pipe_handle)
        self._pipe_handle = None
        warm_pipe.release_mutex(self._mutex_handle)
        self._mutex_handle = None
        self.clear_pid()
        self.log("WARM_ENGINE_EXIT rc=0 pid=%d" % os.getpid())


# ── the stop path: pipe first, identity kill second ─────────────────────────
def stop_engine(pipe=None, mutex=None, pid_path=PID_FILE, root=ROOT,
                wait_s=1.0):
    """``--warm-engine-stop``: ask it to quit, then kill by pid + start time.

    A wedged engine cannot answer the pipe; the design's F2 says kill by
    IDENTITY (pid + start time), never by a name filter -- filtering ``sotto``
    has already killed two processes that were not ours.
    """
    key = warm_pipe.model_key(model_dir_from(root))
    name = pipe or warm_pipe.pipe_name(key)
    handle, reason = warm_pipe.open_client(name, 300)
    if handle is not None:
        conn = warm_pipe.PipeConn(handle)
        try:
            conn.send_line(json.dumps({"op": "quit", "why": "cli-stop"}))
            deadline = time.time() + wait_s
            while time.time() < deadline:
                if conn.readline(timeout_s=0.1) is None and conn.closed:
                    break
        except Exception:  # noqa: BLE001
            pass
        conn.close()
    identity = read_pid_file(pid_path)
    if identity is None:
        return 0, "no-engine"
    pid = identity["pid"]
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if not pid_alive(pid):
            return 0, "stopped pid=%d" % pid
        time.sleep(0.1)
    # The identity check is the terminator's licence: a PID that was reused by
    # another process has a DIFFERENT start time and must not be killed.
    actual = process_start_time(pid)
    if identity.get("started") and actual and identity["started"] != actual:
        return 1, "pid-reused pid=%d expected_start=%s actual=%s" % (
            pid, identity["started"], actual)
    try:
        import psutil

        psutil.Process(pid).kill()
    except Exception as exc:  # noqa: BLE001
        return 1, "kill-failed pid=%d error=%r" % (pid, exc)
    for _ in range(50):
        if not pid_alive(pid):
            break
        time.sleep(0.1)
    return (0 if not pid_alive(pid) else 1), "killed pid=%d" % pid


# ── CLI ──────────────────────────────────────────────────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(description="Sotto warm engine")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--session", default=None)
    parser.add_argument("--pipe", default=None)
    parser.add_argument("--mutex", default=None)
    parser.add_argument("--pid-file", default=PID_FILE)
    parser.add_argument("--log-file", default=LOG_FILE)
    parser.add_argument("--park-ttl", type=float, default=WARM_PARK_TTL_S)
    parser.add_argument("--release-s", type=float, default=WARM_RELEASE_S)
    parser.add_argument("--visibility", default=VISIBILITY_FILE)
    parser.add_argument("--tap", action="store_true",
                        help="mode C: hold one WASAPI client while parked "
                             "(owner opt-in; default is mode B)")
    parser.add_argument("--no-model", action="store_true",
                        help="INSTRUMENT ONLY: run the state machine with a fake "
                             "graph (no weights). It cannot make anything load "
                             "that the gate refuses.")
    parser.add_argument("--stop", action="store_true",
                        help="ask the running engine to quit (then kill by pid+start time)")
    parser.add_argument("--log-age", action="store_true",
                        help="print the age of the pid file and exit")
    args = parser.parse_args(argv)

    if args.stop:
        rc, detail = stop_engine(args.pipe, args.mutex, args.pid_file, args.root)
        print("WARM_ENGINE_STOP rc=%d %s" % (rc, detail))
        return rc
    if args.log_age:
        identity = read_pid_file(args.pid_file)
        if identity is None:
            print("WARM_ENGINE pid=none")
            return 0
        alive = pid_alive(identity["pid"])
        print("WARM_ENGINE pid=%d alive=%s started=%s model=%s"
              % (identity["pid"], str(alive).lower(), identity["started"],
                 identity["model_key"]))
        return 0 if alive else 3

    loader = FakeLoader() if args.no_model else None
    engine = WarmEngine(session=args.session, model_dir=args.model_dir,
                        root=args.root, loader=loader,
                        log_path=args.log_file, pid_path=args.pid_file,
                        pipe=args.pipe, mutex=args.mutex,
                        park_ttl_s=args.park_ttl, release_s=args.release_s,
                        tap_opt_in=args.tap, visibility_path=args.visibility)
    return engine.run()


if __name__ == "__main__":
    sys.exit(main())
