"""Sotto dev lab -- real video, real audio, real worker, ZERO owner exposure.

Owner order (2026-11-15): run https://youtu.be/<id> in a browser with real audio
to process, but never on his screen, never taking focus, never audible; make it
easy (`sotto dev`), repeatable, stepped, cached so nothing cold-repeats.

THE THREE CONSTRAINTS ARE MEASURED, NOT DECLARED (2026-11-15, this box):

| primitive | measurement |
|---|---|
| headless Chrome (`--headless=new`) | foreground HWND unchanged before/after; no window class painted |
| plain playback of the video | `CABLE Input` device peak **0.724559** -> AUDIBLE, refused |
| element hijacked into WebAudio, graph terminated at gain 0 | page RMS **0.2873**, all 4 active endpoints **0.000000** -> SILENT |

Why the hijack is the ONLY safe route: `createMediaElementSource` redirects the
element's decoded audio into the graph and stops it reaching any render
endpoint, while the graph still decodes real audio at real speed. VoiceMeeter
forwards `CABLE Input` to hardware on this box, so "mute the tab" or "use a
virtual cable" are both audible routes. Muting the element (`v.muted=true`)
kills the analyser data too -- measured RMS 0 -- so it cannot be used either.

INSTRUMENT LESSONS BAKED IN (each paid for once):
* pycaw's `AudioDevice` has no `Activate` here, and `d.state != 1` compared an
  Enum to an int: the whole population was skipped and the verdict printed
  "SILENT" over an empty dict. Identity comes from pycaw (by device id), the
  METER from the repo's proven raw `audio-escopo-probe.py::meter_peak`.
* pycaw registers STA at import and the raw probe wants MTA; pycaw imports FIRST.
* Endpoints are keyed by ID: the raw `friendly()` returns None for every
  device here, so name-keying collapsed 4 endpoints into one and lost a live
  0.487 peak.
* A verdict over zero measured endpoints is CANNOT-MEASURE, never SILENT.

USAGE
    python _main/devlab/lab.py selftest
    python _main/devlab/lab.py harvest --video rS4VMlwf2qM --windows 60:20
    python _main/devlab/lab.py feed --video rS4VMlwf2qM --window 60:20
    python _main/devlab/lab.py score --video rS4VMlwf2qM --window 60:20
    python _main/devlab/lab.py strips --video rS4VMlwf2qM --window 60:20
    python _main/devlab/lab.py status

NOTHING here opens a device, registers a hotkey, or shows a window.
"""
from __future__ import annotations

import argparse

# The audio meter probes every endpoint through pycaw and each dead property
# raises a COMError that pycaw turns into a UserWarning: measured, 8 warning
# blocks for 4 endpoints, printed BEFORE any result and looking like a failure.
# They are READ-only probes of endpoints this lab never writes to.
import warnings as _warnings
_warnings.simplefilter("ignore")
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(HERE, "cache")
CACHE_INDEX = os.path.join(CACHE, "index.json")
AUDIBILITY_THRESHOLD = 0.001        # peak below this is silence on this box
SR = 16000                          # the worker's TARGET_SR

BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

#: bump when the capture JS changes: it is part of the cache key, so a fixed
#: extractor never serves PCM produced by the broken one.
CAPTURE_PROTOCOL = 3

PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
CREATE_NO_WINDOW = 0x08000000


def _no_window_kwargs():
    """The pair that hides a console child, in ONE place.

    `CREATE_NO_WINDOW` alone is the defect class `AGENTS.md` names: a console-less
    host (pythonw, the shell) can still be asked for a window through STARTUPINFO,
    and an app that ignores the flag honours `STARTF_USESHOWWINDOW`/`wShowWindow=0`.
    `_main/console-window-audit.py` calls a lone `creationflags` a `WEAK-FLAG` and
    the frozen baseline is empty, so every new site fails the gate. Mirrors
    `_main/hidden-launch._startupinfo`, duplicated rather than imported because
    this file's whole point is to run from `Sotto.cmd dev` with no `_main` on path.
    """
    kw = {"creationflags": CREATE_NO_WINDOW}
    if os.name == "nt":
        kw["startupinfo"] = subprocess.STARTUPINFO(
            dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)
    return kw


# ── audibility gate ─────────────────────────────────────────────────────────
class EndpointMeter:
    """Read-only peak meter over ACTIVE render endpoints (id-keyed).

    NEVER writes: no SetMute, no SetVolume, no SetDefault. The owner's audio is
    his; this only reads `GetPeakValue`.
    """

    def __init__(self):
        from pycaw.pycaw import AudioUtilities, AudioDeviceState
        import importlib.util
        sys.path.insert(0, os.path.join(ROOT, "worker"))
        self.AudioUtilities = AudioUtilities
        self.Active = AudioDeviceState.Active
        probe = os.path.join(ROOT, "_main", "audio-escopo-probe.py")
        spec = importlib.util.spec_from_file_location("aep", probe)
        self.aep = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(self.aep)   # wants MTA; STA already set -> ignored
        except OSError as exc:
            print("  meter-init: %s (meter is apartment agnostic)" % exc)
        self.names = self._catalog()

    def _catalog(self):
        return {self._norm(d.id): d.FriendlyName
                for d in self.AudioUtilities.GetAllDevices()
                if d.state == self.Active}

    @staticmethod
    def _norm(did):
        return (did or "").strip("{}").strip().lower()

    def endpoints(self):
        c = self.aep.ctypes
        enum = self.aep._enumerator()
        coll = c.c_void_p()
        hr = self.aep._vtbl(enum, 3, self.aep.HRESULT, self.aep.wintypes.DWORD,
                            self.aep.wintypes.DWORD, c.POINTER(c.c_void_p))(
            enum, self.aep.E_RENDER, self.aep.DEVICE_STATE_ACTIVE, c.byref(coll))
        if hr != 0:
            raise SystemExit("EnumAudioEndpoints hr=%s" % self.aep.W._fmt(hr))
        n = self.aep.wintypes.UINT(0)
        self.aep._vtbl(coll, 3, self.aep.HRESULT, c.POINTER(self.aep.wintypes.UINT))(
            coll, c.byref(n))
        out = []
        for i in range(n.value):
            d = c.c_void_p()
            self.aep._vtbl(coll, 4, self.aep.HRESULT, self.aep.wintypes.UINT,
                           c.POINTER(c.c_void_p))(coll, i, c.byref(d))
            out.append({"id": self._norm(self.aep.dev_id(d)), "_dev": d})
        return out

    def sample(self, eps, seconds=0.5):
        res, fails = {}, 0
        for e in eps:
            v = self.aep.meter_peak(e["_dev"], seconds=seconds)
            if v is None:
                fails += 1
                continue
            res[self.names.get(e["id"], "dev:" + e["id"][:24])] = round(v, 6)
        return res, fails

    def verdict(self, peaks):
        """(audible_names, reason). Zero measured endpoints is CANNOT-MEASURE."""
        if not peaks:
            return [], "CANNOT-MEASURE"
        hot = {k: v for k, v in peaks.items() if v > AUDIBILITY_THRESHOLD}
        return sorted(hot), ("AUDIBLE" if hot else "SILENT")


# ── cache ───────────────────────────────────────────────────────────────────
def cache_key(*parts):
    h = hashlib.sha256()
    h.update(("|".join(str(p) for p in parts) + "|proto=%d|sr=%d"
              % (CAPTURE_PROTOCOL, SR)).encode("utf-8"))
    return h.hexdigest()[:24]


def load_index():
    try:
        with open(CACHE_INDEX, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_index(idx):
    os.makedirs(CACHE, exist_ok=True)
    tmp = CACHE_INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, CACHE_INDEX)


# ── harvest: real audio out of a real (headless) browser ────────────────────
CAPTURE_JS = r"""
(() => {
  const v = document.querySelector('video');
  if (!v) return {ok: false, why: 'no-video'};
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  let src;
  try { src = ctx.createMediaElementSource(v); }
  catch (e) { return {ok: false, why: 'me-source: ' + e.message}; }
  // The graph ENDS at a gain of 0: the element's audio is diverted into the
  // graph (so it never reaches a render endpoint) and the graph itself emits
  // nothing. Both halves are what make this inaudible.
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  const sink = ctx.createGain();
  sink.gain.value = 0;
  window.__pcm = []; window.__cap = false;
  proc.onaudioprocess = function (ev) {
    if (!window.__cap) return;
    const ch = ev.inputBuffer.getChannelData(0);
    let s = 0;
    for (let i = 0; i < ch.length; i++) s += ch[i] * ch[i];
    window.__rms = Math.sqrt(s / ch.length);
    window.__pcm.push(new Float32Array(ch));
    window.__n = (window.__n || 0) + ch.length;
    window.__sr = ctx.sampleRate;
    window.__rmsmax = Math.max(window.__rmsmax || 0, window.__rms);
  };
  src.connect(proc); proc.connect(sink); sink.connect(ctx.destination);
  window.__ctx = ctx; window.__proc = proc;
  window.__reset = function (t) {
    window.__pcm = []; window.__n = 0; window.__cap = false;
    window.__rmsmax = 0;
    if (typeof t === 'number') { v.currentTime = t; }
    v.play().catch(function () {});
    return v.currentTime;
  };
  window.__start = function () { window.__cap = true; return ctx.state; };
  window.__stop = function () {
    window.__cap = false;
    return {frames: window.__n || 0, sr: window.__sr || ctx.sampleRate,
            rms: window.__rmsmax || 0, t: v.currentTime,
            ready: v.readyState, paused: v.paused};
  };
  window.__drain = function () {
    // base64 of float32, chunk by chunk, so nothing is lost to JSON precision
    const out = [];
    for (const f of window.__pcm) {
      const b = new Uint8Array(f.buffer.slice(0));
      let s = '';
      for (let i = 0; i < b.length; i += 8192) {
        s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
      }
      out.push(btoa(s));
    }
    window.__pcm = [];
    return out;
  };
  return {ok: true, sr: ctx.sampleRate};
})()
"""


def cdp_connect(port, timeout=30):
    import urllib.request
    import websocket
    tabs = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port,
                                        timeout=5) as r:
                tabs = json.loads(r.read().decode())
            if tabs:
                break
        except Exception:
            time.sleep(0.25)
    if not tabs:
        raise SystemExit("CDP never came up on :%d" % port)
    tgt = [t for t in tabs if t.get("type") == "page"][0]
    w = websocket.create_connection(tgt["webSocketDebuggerUrl"], timeout=30)
    mid = [0]

    def send(method, params=None):
        mid[0] += 1
        w.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        while True:
            msg = json.loads(w.recv())
            if msg.get("id") == mid[0]:
                return msg

    def ev(expr, await_promise=False):
        r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                     "awaitPromise": await_promise})
        res = r.get("result", {})
        if res.get("exceptionDetails"):
            raise RuntimeError(str(res["exceptionDetails"])[:400])
        return res.get("result", {}).get("value")

    return w, send, ev


def foreground():
    """Foreground window (hwnd, pid, title) -- the focus witness."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = u.GetForegroundWindow()
    pid = wintypes.DWORD(0)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    n = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    return {"hwnd": int(hwnd), "pid": int(pid.value), "title": buf.value}


def harvest_window(video, start, seconds, port):
    """Capture `seconds` of REAL decoded audio starting at `start`, silently."""
    exe = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not exe:
        raise SystemExit("no browser")
    meter = EndpointMeter()
    eps = meter.endpoints()
    base, bfail = meter.sample(eps, 1.0)
    fg_before = foreground()
    print("  population: devices=%d measured=%d meter_fail=%d"
          % (len(eps), len(base), bfail))
    print("  baseline peaks:", json.dumps(base, sort_keys=True))

    prof = tempfile.mkdtemp(prefix="sottolab-", dir=tempfile.gettempdir())
    args = [exe, "--remote-debugging-port=%d" % port, "--headless=new",
            "--disable-gpu", "--autoplay-policy=no-user-gesture-required",
            "--no-first-run", "--no-default-browser-check",
            "--user-data-dir=" + prof]
    proc = subprocess.Popen(args + ["about:blank"])
    worst, hot_all = {}, {}
    try:
        w, send, ev = cdp_connect(port)
        send("Page.enable")
        send("Runtime.enable")
        send("Page.navigate", {"url": "https://www.youtube.com/watch?v=%s" % video})
        # Wait for a DECODABLE stream, never merely for a <video> tag. Measured
        # failure when only the tag was awaited: `ready:0 paused:true t:0`,
        # 1 052 672 frames of pure silence. readyState>=2 is HAVE_CURRENT_DATA.
        probe = ("(function(){var v=document.querySelector('video');"
                 "if(!v)return null;return {rs:v.readyState,dur:v.duration,"
                 "paused:v.paused,t:v.currentTime,src:!!v.currentSrc};})()")
        ready = 0
        for _ in range(120):
            time.sleep(0.5)
            st = ev(probe)
            if st:
                ready = st.get("rs") or 0
                if ready >= 2 and (st.get("dur") or 0) > 1:
                    print("  media ready: rs=%d dur=%.1f paused=%s"
                          % (ready, st.get("dur") or 0, st.get("paused")))
                    break
        else:
            raise SystemExit("media never became decodable (readyState=%d)" % ready)
        init = ev(CAPTURE_JS)
        print("  capture init:", json.dumps(init))
        if not init or not init.get("ok"):
            raise SystemExit("capture init failed: %r" % (init,))
        t_real = ev("window.__reset(%r)" % float(start))
        # The playhead must MOVE before the window counts: a seek that never
        # lands yields silence, not data.
        moved = False
        for _ in range(60):
            time.sleep(0.5)
            t_now = ev("document.querySelector('video').currentTime")
            if isinstance(t_now, (int, float)) and t_now > float(start) + 0.05:
                print("  playhead moved to %.2fs" % t_now)
                moved = True
                break
        if not moved:
            print("  last currentTime=%r (start=%r)" % (t_now, start))
            raise SystemExit("playhead never advanced past %.1fs" % start)
        print("  ctx state at start:", ev("window.__start()"))
        ev("(function(){ if(window.__ctx.state!=='running') window.__ctx.resume(); return window.__ctx.state; })()")
        # sample the meter WHILE audio plays -- this is the audibility evidence
        t_end = time.time() + seconds + 1.0
        while time.time() < t_end:
            snap, _f = meter.sample(eps, 0.3)
            for k, v in snap.items():
                worst[k] = max(worst.get(k, 0.0), v)
        stopped = ev("window.__stop()")
        print("  stop:", json.dumps(stopped))
        # drain PCM in chunks
        chunks = []
        while True:
            part = ev("window.__drain()")
            if not part:
                break
            chunks.extend(part)
            if ev("(window.__pcm && window.__pcm.length) || 0") == 0:
                break
        import base64
        import numpy as np
        raw = b"".join(base64.b64decode(c) for c in chunks)
        pcm = np.frombuffer(raw, dtype=np.float32).copy()
        sr = int(stopped.get("sr") or init.get("sr") or 48000)
        hot, verdict = meter.verdict(worst)
        fg_after = foreground()
        print("  max peaks while playing:", json.dumps(worst, sort_keys=True))
        print("  AUDIBILITY: %s %s" % (verdict, hot or ""))
        print("  focus before=%d after=%d unchanged=%s"
              % (fg_before["hwnd"], fg_after["hwnd"],
                 fg_before["hwnd"] == fg_after["hwnd"]))
        w.close()
        if verdict != "SILENT":
            raise SystemExit("REFUSED: audio reached %r (%s)" % (hot, verdict))
        if pcm.size < sr * 0.5:
            raise SystemExit("captured only %d samples (sr=%d)" % (pcm.size, sr))
        # A SILENT capture is a DEFECT, never a dataset: the graph gained 0 has
        # to still carry the element's decoded audio. Measured failure modes:
        # `--mute-audio` (rms 0.000) and an element that never reached
        # HAVE_FUTURE_DATA both land here instead of poisoning the cache.
        import numpy as _np
        peak = float(_np.abs(pcm).max()) if pcm.size else 0.0
        rms = float(_np.sqrt((pcm.astype(_np.float64) ** 2).mean())) if pcm.size else 0.0
        print("  signal: peak=%.4f rms=%.4f page_rms=%.4f" % (peak, rms, stopped.get("rms") or 0.0))
        if peak < 0.01 or rms < 0.001:
            raise SystemExit("REFUSED: capture is SILENCE (peak=%.5f rms=%.5f) -- "
                             "nothing written" % (peak, rms))
        return {"pcm": pcm, "sr": sr, "verdict": verdict, "peaks": worst,
                "peak": peak, "rms": rms,
                "focus_unchanged": fg_before["hwnd"] == fg_after["hwnd"],
                "video_time": t_real}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)


def write_wav16(path, pcm, sr):
    """float32 mono @sr -> 16 kHz mono WAV the worker's FileTap reads."""
    import numpy as np
    import soundfile as sf
    if sr != SR:
        # polyphase resample; linear is not good enough for ASR scoring
        from math import gcd
        g = gcd(int(sr), SR)
        up, down = SR // g, int(sr) // g
        n_out = int(round(len(pcm) * up / down))
        idx = np.arange(n_out) * (down / up)
        i0 = np.floor(idx).astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        i1 = np.clip(i0 + 1, 0, len(pcm) - 1)
        i0 = np.clip(i0, 0, len(pcm) - 1)
        pcm = (pcm[i0] * (1 - frac) + pcm[i1] * frac).astype(np.float32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, pcm, SR, subtype="FLOAT")
    return len(pcm) / float(SR)


# ── ground truth: the video's own captions ──────────────────────────────────
def fetch_truth(video, out_path, langs=("en", "en-orig")):
    if os.path.exists(out_path):
        return out_path
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    for lang in langs:
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download",
               "--write-auto-subs", "--write-subs", "--sub-langs", lang,
               "--sub-format", "json3", "-o", out_path + ".%(ext)s",
               "https://youtu.be/%s" % video]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=300, **_no_window_kwargs())
        cand = out_path + ".%s.json3" % lang
        if os.path.exists(cand):
            os.replace(cand, out_path)
            print("  truth: %s from lang=%s" % (out_path, lang))
            return out_path
        print("  truth: lang=%s rc=%d %s" % (lang, r.returncode,
                                            (r.stderr or "")[-160:].replace("\n", " ")))
    raise SystemExit("no caption track fetched")


def truth_slice(truth_path, start, seconds):
    """Text the video's own captions carry in [start, start+seconds)."""
    with open(truth_path, encoding="utf-8") as fh:
        data = json.load(fh)
    # STRICT INTERIOR, by event MIDPOINT. Measured: including events that
    # merely OVERLAP the window put "bully the little guy ... except for the
    # person he was" (spoken BEFORE the window) into the reference and inflated
    # WER from a coverage problem into a 0.779 score that measured the slicer.
    words, kept, dropped = [], 0, 0
    for ev in data.get("events", []):
        t = ev.get("tStartMs", 0) / 1000.0
        d = (ev.get("dDurationMs") or 0) / 1000.0
        mid = t + d / 2.0
        if not (start <= mid < start + seconds):
            dropped += 1
            continue
        kept += 1
        for seg in (ev.get("segs") or []):
            txt = (seg.get("utf8") or "").strip()
            if txt and txt != "\n":
                words.append(txt)
    return " ".join(words).strip(), kept, dropped


# ── worker run over cached audio ────────────────────────────────────────────
def _private_mb(pid):
    """PRIVATE COMMIT of one pid, in MiB (the watcher's own unit).

    psutil is not a dependency of this repo, so the counter comes from the
    kernel through ctypes. PrivatePageCount is the pagefile-backed reservation
    the governor caps; WorkingSetSize is what is actually resident, and the two
    differ by an order of magnitude on a parked process.
    """
    import ctypes
    from ctypes import wintypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not h:
        raise OSError(ctypes.get_last_error())
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]
        c = PMC(); c.cb = ctypes.sizeof(PMC)
        if not k32.K32GetProcessMemoryInfo(h, ctypes.byref(c), ctypes.sizeof(PMC)):
            raise OSError(ctypes.get_last_error())
        return c.PrivateUsage // (1024 * 1024)
    finally:
        k32.CloseHandle(h)


#: The lab feeds a FINITE window. The worker's FileTap LOOPS the file by design
#: (its job is to keep a live stream alive), and measured on 2026-11-15 that
#: loop replays the window while the model is still loading, so a generous
#: `--max-seconds` behaved worse than a tight one: the HYP text repeated whole
#: phrases ("... the person he was bullying this time ..." twice) and coverage
#: swings tracked the replay, not the model. `SOTTO_FILE_TAP_ONCE=1` makes the
#: pump END its stream at EOF, which is the honest shape for a cached window.
LAB_ENV_BASE = {"SOTTO_FILE_TAP_ONCE": "1"}

# Declared wall margin over a run's own `--max-seconds`: the tail after the last
# audio chunk is the line flush + the second pass, both bounded by the worker's
# own statistics, not by the audio length. Anything past this is PARKED, and a
# parked worker holds a BLAS arena on the pagefile for nothing.
WATCH_WALL_MARGIN_S = 90.0


def run_worker_once(wav, tag, max_seconds, extra_env=None, extra_args=None):
    """The REAL live loop, fed from a file: no device, no window, no hotkey."""
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, "%s.stdout.jsonl" % tag)
    err = os.path.join(CACHE, "%s.stderr.log" % tag)
    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = wav
    env.update(LAB_ENV_BASE)
    # Per-chunk decode trace: the only way to tell "the model heard nothing"
    # from "the pipeline dropped it". Measured need 2026-11-15 -- 35 chunks
    # counted, captions stopped at chunk 15, and nothing in the receipt said
    # which chunk produced which text.
    env["SOTTO_CHUNK_TRACE"] = os.path.join(CACHE, "%s.chunks.jsonl" % tag)
    env.pop("SOTTO_AUDIO_FILE", None)
    env.pop("SOTTO_REDUX_WAV_DIR", None)
    for k, v in (extra_env or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    # DECLARED THREAD CEILING, pinned at LAUNCH (watcher DM
    # dm-a0062c2653c775458667, 2026-11-15): one of these workers was measured
    # parked with private=1.81 GiB against rss=0.09 GiB -- 20.1x its resident
    # set -- because a BLAS/ORT arena is sized per CPU thread and this box
    # reports 20. A launch that never declares the count pays that arena on
    # every run and parks it on the pagefile. The env is set BEFORE the
    # interpreter starts, so the arena is never created at the default size.
    # `--threads` is the worker's own knob (current_threads() reads it), so the
    # two halves cannot disagree.
    env.setdefault("OMP_NUM_THREADS", "2")
    env["OMP_NUM_THREADS"] = "2"
    env["OPENBLAS_NUM_THREADS"] = "2"
    env["MKL_NUM_THREADS"] = "2"
    env["NUMEXPR_NUM_THREADS"] = "2"
    env["VECLIB_MAXIMUM_THREADS"] = "2"
    env["OMP_WAIT_POLICY"] = "PASSIVE"
    cmd = [os.path.join(ROOT, "worker", "sotto_worker.py"),
           "--max-seconds", str(max_seconds), "--stats-interval", "4",
           "--threads", "2"]
    cmd += (extra_args or [])
    exe = PYTHONW if os.path.exists(PYTHONW) else sys.executable
    t0 = time.time()
    with open(out, "w", encoding="utf-8") as fo, open(err, "w", encoding="utf-8") as fe:
        p = subprocess.Popen([exe] + cmd, cwd=ROOT, env=env, stdout=fo, stderr=fe,
                             creationflags=CREATE_NO_WINDOW,
                             startupinfo=subprocess.STARTUPINFO(
                                 dwFlags=subprocess.STARTF_USESHOWWINDOW,
                                 wShowWindow=0))
        # THE CEILING IS MEASURED, not declared and forgotten: the watcher DM
        # of 2026-11-15 accused this exact launch (private=1.81 GiB, rss=0.09
        # GiB, 20.1x). Sampling the child's private commit while it runs is the
        # only way the receipt can answer "declared ceiling vs what was taken".
        # THE DEADLINE IS DECLARED OR THE PROCESS PARKS ON ITS COMMIT. Measured
        # defect 2026-11-15 (watcher DM dm-a0062c2653c775458667): a devlab
        # worker launched with `--max-seconds 26` was still alive at 186.6 s
        # holding private=1.81 GiB against rss=0.09 GiB, so it was PARKED, not
        # working, and the pagefile paid for it. The old loop had no wall
        # deadline at all -- `p.poll()` never raises TimeoutExpired, so the
        # `except` that was supposed to kill it was dead code. The ceiling is
        # the run's own budget plus a declared margin for the tail after the
        # last chunk (flush + second pass), and an overrun is NAMED in the
        # receipt instead of being silently tolerated.
        deadline_s = float(max_seconds) + WATCH_WALL_MARGIN_S
        peak_priv = 0
        killed_at = None
        while True:
            rc = p.poll()
            if rc is not None:
                break
            elapsed = time.time() - t0
            if elapsed > deadline_s:
                killed_at = round(elapsed, 1)
                p.kill()
                try:
                    p.wait(timeout=20)
                except Exception:
                    pass
                break
            try:
                peak_priv = max(peak_priv, _private_mb(p.pid))
            except Exception:
                pass
            time.sleep(0.5)
    # A process we had to kill is not a measurement: its transcript is short by
    # however much it failed to drain, and the caller must say so out loud.
    if killed_at is not None:
        print("WORKER CEILING HIT tag=%s wall=%.1fs deadline=%.0fs -- the "
              "process was KILLED holding private=%.0fMiB; its transcript is "
              "partial by construction" % (tag, killed_at, deadline_s, peak_priv))
    return {"tag": tag, "rc": p.returncode, "wall_s": round(time.time() - t0, 1),
            "out": out, "err": err, "peak_priv_mb": peak_priv,
            "killed_at_s": killed_at, "deadline_s": deadline_s}


def load_estimate(tag_hint="model-load"):
    """How long the model takes to load, from the LAST run that measured it.

    MEASURED DEFECT this fixes (2026-11-15): `--max-seconds` counts from
    PROCESS START, and `capture-started` only happens AFTER `model-loaded`.
    A run measured `load_s=24.59` and was launched with `--max-seconds 26`, so
    ~1.4 s of a 20 s window was ever drained and coverage swung 0.34 / 0.58 /
    0.68 / 0.71 across IDENTICAL runs -- the lab was measuring its own budget,
    not the model. The estimate is read from a previous run's own
    `model-loaded.load_s`, so it is content-free and never guessed when a
    measurement exists.
    """
    best = None
    try:
        names = [n for n in os.listdir(CACHE) if n.endswith(".stdout.jsonl")]
    except OSError:
        names = []
    for n in names:
        try:
            with open(os.path.join(CACHE, n), encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    if '"model-loaded"' not in raw:
                        continue
                    try:
                        o = json.loads(raw)
                    except Exception:
                        continue
                    ls = o.get("load_s")
                    if isinstance(ls, (int, float)) and ls > 0:
                        best = max(best or 0.0, float(ls))
        except OSError:
            continue
    return best


def run_budget(dur_s, load_s=None):
    """Seconds to give a run so the WHOLE window is drained, and no more.

    budget = load + window + drain, where drain is the engine's own tail.
    A too-small budget silently truncates the window; a too-large one makes the
    looping FileTap replay audio and duplicate lines. Both were measured.
    """
    if load_s is None:
        load_s = load_estimate()
    if load_s is None:
        load_s = 45.0  # declared fallback, printed as DECLARED when used
    return int(round(load_s + dur_s + 12))


def transcript_of(result):
    """The closed lines the run produced, in order (the panel's own route)."""
    lines = []
    path = result["out"] if os.path.exists(result["out"]) else result["err"]
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if obj.get("type") not in ("caption", "final", "transcript"):
                continue
            # ONLY the closed lines: measured on a real feed, 23 `final:false`
            # partials against 3 finals, and every partial is a PREFIX of the
            # next one -- counting them as separate lines inflates the
            # transcript and corrupts WER. `final` absent is treated as final
            # for the batch producers, which never emit partials.
            if obj.get("final") is False:
                continue
            txt = (obj.get("text") or "").strip()
            if txt:
                lines.append({"text": txt, "start": obj.get("start"),
                              "end": obj.get("end"),
                              "producer": obj.get("producer"),
                              "route": obj.get("route")})
    return lines


def wer(ref, hyp):
    """Word error rate + the substitution/deletion counts behind it."""
    import re
    norm = lambda s: re.sub(r"[^a-z0-9' ]+", " ", (s or "").lower()).split()
    r, h = norm(ref), norm(hyp)
    if not r:
        return None, {"ref": 0, "hyp": len(h)}
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1] / float(len(r)), {"ref": len(r), "hyp": len(h), "errors": prev[-1]}


# ── commands ────────────────────────────────────────────────────────────────
def parse_windows(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        a, b = part.split(":")
        out.append((float(a), float(b)))
    return out


def cmd_harvest(a):
    idx = load_index()
    rows = []
    for start, seconds in parse_windows(a.windows):
        key = cache_key("harvest", a.video, start, seconds)
        wav = os.path.join(CACHE, "audio", "%s.wav" % key)
        meta = os.path.join(CACHE, "audio", "%s.json" % key)
        if os.path.exists(wav) and os.path.exists(meta) and not a.force:
            with open(meta, encoding="utf-8") as fh:
                m = json.load(fh)
            print("CACHE HIT %s video=%s window=%s:%s" % (key, a.video, start, seconds))
            rows.append(m)
            continue
        print("MISS %s video=%s window=%s:%s" % (key, a.video, start, seconds))
        got = harvest_window(a.video, start, seconds, a.port)
        dur = write_wav16(wav, got["pcm"], got["sr"])
        m = {"key": key, "video": a.video, "start": start, "seconds": seconds,
             "wav": wav, "dur_s": round(dur, 3), "src_sr": got["sr"],
             "audibility": got["verdict"], "peaks": got["peaks"],
             "focus_unchanged": got["focus_unchanged"],
             "page_rms": got["rms"], "peak": round(got.get("peak", 0), 5),
             "rms": round(got.get("rms", 0), 5), "samples": int(got["pcm"].size)}
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=2)
            fh.write("\n")
        idx[key] = m
        rows.append(m)
        print("  wrote %s (%.2fs audio, %d samples)" % (wav, dur, m["samples"]))
    save_index(idx)
    for m in rows:
        print("AUDIO %s %s:%ss dur=%.2fs audibility=%s"
              % (m["key"], m["video"], m["seconds"], m["dur_s"], m["audibility"]))
    return 0


def cmd_feed(a):
    idx = load_index()
    key = _window_key(a.video, a.window[0], a.window[1])
    if key not in idx:
        raise SystemExit("no cached audio for %s -- run harvest first" % key)
    m = idx[key]
    tag = "feed-%s" % key
    print("feed %s  wav=%s  max_seconds=%.1f" % (key, m["wav"], m["dur_s"]))
    _load = load_estimate()
    _budget = run_budget(m["dur_s"], _load)
    print("BUDGET window=%.1fs load=%s budget=%ds "
          "(max-seconds counts from process start; capture starts after the load)"
          % (m["dur_s"],
             ("%.1fs" % _load) if _load is not None else "DECLARED 45.0s",
             _budget))
    res = run_worker_once(m["wav"], tag, _budget,
                          extra_env={"SOTTO_LANG": a.lang} if a.lang else None)
    lines = transcript_of(res)
    print("rc=%s wall=%.1fs lines=%d" % (res["rc"], res["wall_s"], len(lines)))
    print("logs: %s / %s" % (res["out"], res["err"]))
    for ln in lines[:a.show]:
        print("  [%s-%s] %s" % (ln.get("start"), ln.get("end"), ln["text"]))
    return 0 if lines else 1


def cmd_score(a):
    idx = load_index()
    key = _window_key(a.video, a.window[0], a.window[1])
    if key not in idx:
        raise SystemExit("no cached audio for %s -- run harvest first" % key)
    m = idx[key]
    truth_path = os.path.join(CACHE, "truth", "%s.json3" % a.video)
    fetch_truth(a.video, truth_path)
    ref, kept, dropped = truth_slice(truth_path, m["start"], m["seconds"])
    tag = "feed-%s" % key
    _load = load_estimate()
    _budget = run_budget(m["dur_s"], _load)
    print("BUDGET window=%.1fs load=%s budget=%ds "
          "(max-seconds counts from process start; capture starts after the load)"
          % (m["dur_s"],
             ("%.1fs" % _load) if _load is not None else "DECLARED 45.0s",
             _budget))
    # THE GATE IS EXPLICIT ON THE SCORE PATH. MEASURED DEFECT 2026-11-15: this
    # call passed only `SOTTO_LANG`, so the worker fell back to its live-branch
    # default (`gate=on`) and the "gate off" comparison was never taken -- the
    # log said `gate=on source=live-default` while the command line said nothing
    # about the gate. A control that cannot be selected is not a control.
    _env = {}
    if a.lang:
        _env["SOTTO_LANG"] = a.lang
    # NO SOTTO_GATE UNLESS ASKED. The worker's own default is the thing under
    # test after 2026-11-15 (it is OFF now), and an env var set by the harness
    # would hide the default it is supposed to exercise. `--gate` is the only
    # thing that forces it on; "unset" is the product's answer.
    if a.gate:
        _env["SOTTO_GATE"] = "1"
    print("GATE gate=%s (%s)" % ("on" if a.gate else "product default",
                                 "forced" if a.gate else "no SOTTO_GATE set"))
    res = run_worker_once(m["wav"], tag, _budget, extra_env=_env)
    lines = transcript_of(res)
    hyp = " ".join(l["text"] for l in lines)
    rate, detail = wer(ref, hyp)
    print("REF: %s" % (ref[:300] or "(empty)"))
    print("HYP: %s" % (hyp[:300] or "(empty)"))
    hyp_words = len(hyp.split())
    coverage = (hyp_words / float(detail["ref"])) if detail.get("ref") else 0.0
    print("SCORE population: finals=%d ref_events=%d dropped=%d "
          "ref_words=%d hyp_words=%d coverage=%.2f"
          % (len(lines), kept, dropped, detail.get("ref", 0), hyp_words, coverage))
    print("SCORE cost: wall=%ss peak_private=%dMiB threads=2"
          " (the watcher DM dm-a0062c2653c775458667 accused this launch at"
          " private=1.81GiB; the ceiling is declared at launch)"
          % (res["wall_s"], res.get("peak_priv_mb", 0)))
    print("SCORE %s window=%s:%s wer=%s detail=%s"
          % ("PASS" if rate is not None else "CANNOT-MEASURE",
             m["start"], m["seconds"],
             ("%.3f" % rate) if rate is not None else "n/a",
             json.dumps(detail)))
    return 0 if rate is not None else 3


STRIPS = {
    "live-only":      {},
    "batch-on":       {"SOTTO_REDUX_WHEN_HIDDEN": "1"},
    "no-denoise":     {"SOTTO_GATE": "0"},
    "single-thread":  {"SOTTO_WORKER_THREADS": "1"},
}


def cmd_strips(a):
    idx = load_index()
    key = _window_key(a.video, a.window[0], a.window[1])
    if key not in idx:
        raise SystemExit("no cached audio for %s -- run harvest first" % key)
    m = idx[key]
    truth_path = os.path.join(CACHE, "truth", "%s.json3" % a.video)
    fetch_truth(a.video, truth_path)
    ref, _k, _d = truth_slice(truth_path, m["start"], m["seconds"])
    rows = []
    for name, env in STRIPS.items():
        tag = "strip-%s-%s" % (name, key)
        res = run_worker_once(m["wav"], tag, run_budget(m["dur_s"]), extra_env=env)
        lines = transcript_of(res)
        hyp = " ".join(l["text"] for l in lines)
        rate, detail = wer(ref, hyp)
        rows.append({"strip": name, "rc": res["rc"], "wall_s": res["wall_s"],
                     "lines": len(lines),
                     "wer": None if rate is None else round(rate, 4),
                     "detail": detail})
        print("  %-14s rc=%s wall=%5.1fs peak_priv=%dMiB lines=%-3d wer=%s"
              % (name, res["rc"], res["wall_s"], res.get("peak_priv_mb", 0),
                 len(lines), ("%.4f" % rate) if rate is not None else "n/a"))
    out = os.path.join(CACHE, "strips-%s.json" % key)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"key": key, "video": a.video, "window": list(a.window),
                   "ref_words": len(ref.split()), "rows": rows}, fh, indent=2)
        fh.write("\n")
    print("STRIPS wrote %s" % out)
    return 0


def cmd_status(a):
    idx = load_index()
    print("cache: %s entries=%d" % (CACHE, len(idx)))
    for k, m in sorted(idx.items(), key=lambda kv: kv[1].get("video", "")):
        print("  %s %s %s:%ss dur=%.2fs aud=%s focus_ok=%s"
              % (k, m.get("video"), m.get("start"), m.get("seconds"),
                 m.get("dur_s", 0), m.get("audibility"), m.get("focus_unchanged")))
    return 0


def cmd_selftest(a):
    """Judge the JUDGE: the gate must refuse a known-audible route."""
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        print("  %-34s %s %s" % (name, "PASS" if ok else "FAIL", detail))

    meter = EndpointMeter()
    eps = meter.endpoints()
    peaks, fails = meter.sample(eps, 0.5)
    check("population non-empty", len(eps) > 0, "devices=%d" % len(eps))
    check("meter reads every endpoint", fails == 0 and len(peaks) == len(eps),
          "measured=%d fail=%d" % (len(peaks), fails))
    hot, verdict = meter.verdict(peaks)
    check("verdict is a word", verdict in ("SILENT", "AUDIBLE", "CANNOT-MEASURE"), verdict)
    # the negative arm: a synthetic peak MUST be named audible
    hot2, v2 = meter.verdict({"(planted)": 0.9})
    check("neg-arm: planted peak -> AUDIBLE", v2 == "AUDIBLE" and hot2 == ["(planted)"], v2)
    hot3, v3 = meter.verdict({})
    check("neg-arm: zero endpoints -> CANNOT-MEASURE", v3 == "CANNOT-MEASURE", v3)
    hot4, v4 = meter.verdict({"(quiet)": 0.0000001})
    check("quiet endpoint -> SILENT", v4 == "SILENT", v4)
    check("threshold is the measured floor", AUDIBILITY_THRESHOLD == 0.001,
          str(AUDIBILITY_THRESHOLD))
    # capture protocol must actually hijack the element and end at gain 0
    check("capture ends at gain 0", "sink.gain.value = 0" in CAPTURE_JS)
    check("capture diverts element audio", "createMediaElementSource" in CAPTURE_JS)
    check("capture never connects src to destination",
          "src.connect(sink)" not in CAPTURE_JS and "src.connect(ctx.destination)" not in CAPTURE_JS)
    ok = all(c[1] for c in checks)
    print("LAB SELFTEST: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                        sum(1 for c in checks if c[1]), len(checks)))
    return 0 if ok else 1






# ── deterministic source + window (the audio path) ──────────────────────────
# WHY the audio does NOT come from the browser (measured 2026-11-15, four arms):
# headless Chrome plays and buffers, but a seek PAST the buffered range parks at
# `readyState=1 networkState=2` and never fetches again -- A/B/D (baseline,
# with anti-throttling flags, and with a wait-then-play) all stayed
# `RECOVERED=False` for 10 s, while the headed-offscreen arm recovered. Headed
# steals focus, which is forbidden. So the audio comes from the video's OWN
# stream: one download per video, then any window is cut locally with ffmpeg.
# Deterministic, repeatable, cacheable -- and it touches no renderer at all.

def source_file(video, force=False):
    """The video's full audio track, downloaded once and cached by video id."""
    d = os.path.join(CACHE, "source")
    os.makedirs(d, exist_ok=True)
    final = os.path.join(d, "%s.m4a" % video)
    marker = os.path.join(d, "%s.json" % video)
    # CACHE ON WHAT THE MARKER RECORDS. Measured defect: the hit test required
    # `<id>.m4a` while yt-dlp produced `<id>.webm`, so the 53.5 MB download was
    # paid on EVERY run and the "MISS source" line was the only symptom. The
    # recorded path is the only honest key -- the container is chosen by the
    # format, never by this file.
    if os.path.exists(marker) and not force:
        with open(marker, encoding="utf-8") as fh:
            m = json.load(fh)
        if m.get("path") and os.path.exists(m["path"]):
            print("CACHE HIT source %s (%.1f MB, %.1f s)"
                  % (video, os.path.getsize(m["path"]) / 1e6, m.get("dur_s") or 0))
            return m["path"], m
    print("MISS source %s: downloading the audio track once" % video)
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "-f", "bestaudio",
           "-o", final.replace(".m4a", ".%(ext)s"), "https://youtu.be/%s" % video]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                       **_no_window_kwargs())
    got = None
    for name in os.listdir(d):
        if name.startswith(video + ".") and not name.endswith(".json"):
            got = os.path.join(d, name)
            break
    if not got:
        raise SystemExit("download failed rc=%d %s" % (r.returncode, (r.stderr or "")[-300:]))
    info = probe_audio(got)
    m = {"video": video, "path": got, "bytes": os.path.getsize(got),
         "dur_s": info.get("dur_s"), "sr": info.get("sr"), "ch": info.get("ch")}
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2)
        fh.write("\n")
    print("  wrote %s (%.1f MB, %.1f s @ %s Hz)"
          % (got, m["bytes"] / 1e6, m["dur_s"] or 0, m["sr"]))
    return got, m


def probe_audio(path):
    try:
        import soundfile as sf
        i = sf.info(path)
        return {"dur_s": round(i.duration, 3), "sr": i.samplerate, "ch": i.channels}
    except Exception:
        pass
    ff = shutil.which("ffprobe") or "ffprobe"
    r = subprocess.run([ff, "-v", "error", "-show_entries",
                        "format=duration:stream=sample_rate,channels", "-of", "json", path],
                       capture_output=True, text=True, **_no_window_kwargs())
    try:
        d = json.loads(r.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        return {"dur_s": round(float(d.get("format", {}).get("duration") or 0), 3),
                "sr": int(st.get("sample_rate") or 0), "ch": int(st.get("channels") or 0)}
    except Exception:
        return {}


def extract_window(src, start, seconds, out_wav):
    """Cut [start, start+seconds) from the cached source to 16 kHz mono WAV."""
    ff = shutil.which("ffmpeg") or "ffmpeg"
    os.makedirs(os.path.dirname(out_wav), exist_ok=True)
    cmd = [ff, "-y", "-v", "error", "-ss", "%.3f" % start, "-t", "%.3f" % seconds,
           "-i", src, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", out_wav]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       **_no_window_kwargs())
    if r.returncode != 0 or not os.path.exists(out_wav):
        raise SystemExit("ffmpeg failed rc=%d %s" % (r.returncode, (r.stderr or "")[-300:]))
    info = probe_audio(out_wav)
    return info


def _window_key(video, start, seconds):
    return cache_key("window", video, "%.3f" % start, "%.3f" % seconds)


# ── S2: the caption arm ─────────────────────────────────────────────────────
# WHY THIS DRIVES A FIXTURE AND NOT YOUTUBE (measured 2026-11-15, five arms):
#
# Real headless YouTube REFUSES to serve captions to this lab. Measured on
# `rS4VMlwf2qM`: `ytInitialPlayerResponse.captions` lists 124 tracks and
# `#movie_player.getOption('captions','track')` returns `languageCode='en'`
# with **`is_servable: false`**; `loadModule('captions')`, `setOption(...)` and
# `setOption('captions','reload',true)` all return success and the container
# stays empty for 16 s of playback; the CC button reports `aria-pressed=true`
# while `.ytp-caption-window-container` holds **0** `.caption-visual-line`;
# and fetching the track's own `baseUrl + '&fmt=json3'` from inside the page
# returns `status=200` with a **0-byte** body. A desktop UA string changed
# nothing (`why=no-window` throughout). This is a platform fact about the
# headless player, not a lab defect.
#
# What the lab CAN prove, and what actually matters for Sotto, is the part that
# is ours: the extractor JS, `parse_snapshot`, `pick_target`, the pause/clock
# rules and the "subtitles off is not no-captions" distinction. Those run
# against a player DOM the lab controls, in a real Chrome, with the REAL code
# from `app/webview/youtube_cdp_source.py` -- no reimplementation, so the arm
# cannot pass while the shipped extractor rots.
CAPTION_FIXTURE = r"""<!doctype html><html><head><meta charset="utf-8"><style>
  body { margin:0; background:#000; font:18px sans-serif; }
  .caption-window { position:absolute; left:40px; top:120px; width:240px; }
  .caption-visual-line { display:block; height:26px; color:#fff; }
  .ytp-caption-segment { display:inline-block; height:20px; }
  .ytp-chrome-bottom { position:absolute; left:0; top:300px; }
  button.cc { width:60px; height:30px; }
</style></head><body>
<video id="v" width="320" height="180"></video>
<div class="ytp-caption-window-container">
  <div class="caption-window"></div>
</div>
<div class="ytp-chrome-bottom"><button class="cc">CC</button></div>
<script>
// A PLAYER, NOT A PICTURE (2026-11-15). The first version of this fixture let
// the lab push lines by hand, which measured the extractor against a script
// nobody ships. Here the cues are the page's own data, the clock decides which
// one is on screen, and captions are toggled by the SAME two doors a person
// uses: the `c` key on the page and the CC button's own handler. The lab only
// turns the clock -- it never writes a caption line.
window.__cues = [
  {s: 0.0, e: 5.0, lines: ['the opening line']},
  {s: 5.0, e: 11.0, lines: ['the second sentence']},
  {s: 11.0, e: 18.0, lines: ['first of two', '>> second with marker']},
  {s: 18.0, e: 30.0, lines: ['the closing line']}
];
window.__t = 0.0;
window.__paused = false;
window.__rate = 1.0;
window.__ended = false;
window.__cc = false;
var v = document.getElementById('v');
Object.defineProperty(v, 'currentTime', {get: function () { return window.__t; },
                                         set: function (x) { window.__t = x; render(); }});
Object.defineProperty(v, 'readyState', {get: function () { return 4; }});
Object.defineProperty(v, 'paused', {get: function () { return window.__paused; }});
Object.defineProperty(v, 'ended', {get: function () { return window.__ended; }});
Object.defineProperty(v, 'duration', {get: function () { return 3380.0; }});
Object.defineProperty(v, 'playbackRate', {get: function () { return window.__rate; }});

function win() { return document.querySelector('.caption-window'); }
function paint(lines) {
  var w = win();
  w.innerHTML = '';
  for (const text of lines || []) {
    var line = document.createElement('div');
    line.className = 'caption-visual-line';
    var seg = document.createElement('span');
    seg.className = 'ytp-caption-segment';
    seg.textContent = text;
    line.appendChild(seg);
    w.appendChild(line);
  }
  return w.children.length;
}
// WHICH CUE IS ON SCREEN IS A FUNCTION OF THE CLOCK -- the same rule the real
// player follows, so a seek changes the caption without any lab help.
function render() {
  if (!window.__cc) return paint([]);
  var t = window.__t;
  for (const c of window.__cues) {
    if (t >= c.s && t < c.e) return paint(c.lines);
  }
  return paint([]);
}
window.__toggleCC = function () { window.__cc = !window.__cc; render(); return window.__cc; };
window.__seek = function (t) { window.__t = t; render(); return window.__t; };
window.__setLines = function (arr) { window.__cc = false; return paint(arr); };

// DOOR 1: the `c` key. The page listens; a synthetically dispatched key event
// from CDP is what reaches this handler, and it reaches it only if the handler
// is wired -- which is the thing being measured.
window.addEventListener('keydown', function (ev) {
  if (ev.key === 'c' || ev.key === 'C') { ev.preventDefault(); window.__toggleCC(); }
});
// DOOR 2: the button's own click handler.
document.querySelector('button.cc').addEventListener('click', function () {
  window.__toggleCC();
});
</script></body></html>
"""


#: The keys are the states the arm walks, not a syntax to remember.
S2_STEPS = ("paint", "advance", "pause", "off", "segments", "chrome-window")


def caption_fixture_page(video):
    """Serve the fixture at a `/watch?v=<id>` URL on loopback.

    `list_targets` filters tabs on `_WATCH` ('/watch') -- the shipped rule, and
    the one that decides which tabs Sotto may read. A fixture on `about:blank`
    or a `data:` URL would be invisible to the REAL target picker, so the arm
    would exercise a decision the app never takes. A loopback server costs one
    thread and makes the picker see exactly what it sees on YouTube.
    """
    import http.server
    import threading

    body = CAPTION_FIXTURE.replace("PLACEHOLDER", "the opening line").encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                    # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a):                          # silence
            return

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, name="lab-fixture", daemon=True).start()
    return srv, "http://127.0.0.1:%d/watch?v=%s" % (srv.server_address[1], video)


#: THE MUTANTS THE NEGATIVE ARM PLANTS, each aimed at the check that must catch
#: it. A control that only proves "the arm runs" is a control that cannot fail;
#: every edit here is applied to a COPY of the shipped module, and the arm has
#: to go RED on exactly the check named beside it -- measured, not asserted.
CAPTION_MUTANTS = (
    # (label, needle, replacement, the check it must break)
    ("chrome-window filter removed",
     'if line.get("chrome"):\n            continue',
     'if False:\n            continue',
     "chrome-window: control window dropped from rows"),
    ("speaker marker no longer stripped",
     'text = strip_speaker_markers(line.get("text"))',
     'text = (line.get("text") or "")',
     "seek: speaker marker >> stripped"),
    ("empty box still called painted",
     'if why == "painted" and not rows:',
     'if False:',
     "chrome-window: an empty box is not called painted"),
)


def mutant_source(path, needle, replacement):
    """The shipped module with ONE edit, or None when the needle is absent.

    `None` is not a pass: a mutant whose anchor disappeared proves nothing, and
    the arm says so instead of reporting a control it never planted.
    """
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if needle not in src:
        return None
    return src.replace(needle, replacement, 1)


def run_captions(video, port, steps=S2_STEPS, source=None):
    """S2 -- exercise the REAL extractor + parser over a controlled player.

    `source` overrides the module path so the negative arm can drive a MUTATED
    copy through the same checks; the shipped path is the default.
    """
    import importlib.util
    path = source or os.path.join(ROOT, "app", "webview", "youtube_cdp_source.py")
    spec = importlib.util.spec_from_file_location("ycs", path)
    ycs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ycs)

    exe = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not exe:
        raise SystemExit("no browser")
    srv, watch_url = caption_fixture_page(video)
    prof = tempfile.mkdtemp(prefix="sottocap-", dir=tempfile.gettempdir())
    fg0 = foreground()
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        print("  %-40s %s %s" % (name, "PASS" if ok else "FAIL", detail))

    proc = subprocess.Popen([exe, "--remote-debugging-port=%d" % port,
                             "--headless=new", "--disable-gpu", "--mute-audio",
                             "--no-first-run", "--no-default-browser-check",
                             "--user-data-dir=" + prof, watch_url])
    try:
        w, send, ev = cdp_connect(port)
        send("Page.enable")
        send("Runtime.enable")
        time.sleep(0.6)

        def snap():
            return ycs.parse_snapshot(ev(ycs.EXTRACT_JS))

        def press_c():
            """The `c` key, through the input pipeline, not through a property."""
            for kind in ("keyDown", "keyUp"):
                send("Input.dispatchKeyEvent", {"type": kind, "key": "c", "code": "KeyC",
                                                "windowsVirtualKeyCode": 67, "text": "c"})
            time.sleep(0.05)

        def click_cc():
            """The CC button's own handler, through a real mouse event."""
            box = ev("""(function(){var b=document.querySelector('button.cc').getBoundingClientRect();
                          return {x: b.left + b.width/2, y: b.top + b.height/2};})()""")
            for kind in ("mousePressed", "mouseReleased"):
                send("Input.dispatchMouseEvent", {"type": kind, "x": box["x"], "y": box["y"],
                                                  "button": "left", "clickCount": 1})
            time.sleep(0.05)

        # ── never-on: subtitles that were never enabled must not invent text ─
        s0 = snap()
        check("never-on: zero rows before anyone enables subtitles",
              s0 and s0["rows"] == [], "rows=%r" % (s0 and s0["rows"],))
        check("never-on: why is no-painted-caption", s0 and s0["why"] == "no-painted-caption",
              s0 and s0["why"])

        # ── door 1: the `c` key ────────────────────────────────────────────
        press_c()
        s = snap()
        check("key c: the page's cc toggles and a line appears",
              s and s["rows"] == ["the opening line"], "rows=%r why=%r" % (s and s["rows"], s and s["why"]))
        check("paint: segments carry geometry",
              s and s["items"] and s["items"][0]["right"] > s["items"][0]["left"],
              "items=%d" % len(s["items"] if s else ()))
        check("paint: why says painted", s and s["why"] == "painted", s and s["why"])

        # ── seek: the caption is a function of the player's clock ──────────
        ev("window.__seek(6.0)")
        s1 = snap()
        check("seek: the new cue replaces the old one",
              s1 and s1["rows"] == ["the second sentence"], "rows=%r" % (s1 and s1["rows"],))
        check("seek: t carries the new position", s1 and abs((s1["t"] or 0) - 6.0) < 1e-6,
              "t=%r" % (s1 and s1["t"]))
        ev("window.__seek(12.0)")
        s2 = snap()
        check("seek: two lines kept", s2 and len(s2["rows"]) == 2, "rows=%r" % (s2 and s2["rows"],))
        check("seek: speaker marker >> stripped",
              s2 and all(">>" not in r for r in s2["rows"]), "rows=%r" % (s2 and s2["rows"],))

        # ── off: the S2 LAW -- off is not a stale line, and not "no window" ─
        press_c()
        s3 = snap()
        check("key c again: rows cleared", s3 and s3["rows"] == [], "rows=%r" % (s3 and s3["rows"],))
        check("off: why is no-painted-caption, not painted",
              s3 and s3["why"] == "no-painted-caption", s3 and s3["why"])
        check("off: segs empty too", s3 and s3["segs"] == [], "segs=%d" % len(s3["segs"] if s3 else ()))
        ev("window.__seek(20.0)")
        s3b = snap()
        check("off: seeking with subtitles off brings back no line",
              s3b and s3b["rows"] == [], "rows=%r" % (s3b and s3b["rows"],))

        # ── door 2: the CC button ──────────────────────────────────────────
        click_cc()
        s4 = snap()
        check("button cc: the button's own handler turns subtitles back on",
              s4 and s4["rows"] == ["the closing line"], "rows=%r" % (s4 and s4["rows"],))

        # ── pause: the flag is the player's, and None is never a pause ─────
        ev("window.__paused = true")
        sp = snap()
        check("pause: paused flag surfaces", sp and sp["paused"] is True, "paused=%r" % (sp and sp["paused"]))
        check("pause: player_stopped agrees", ycs.player_stopped(sp) is True)
        ev("window.__paused = false")
        check("pause: cleared flag is not a pause", ycs.player_stopped(snap()) is False)

        # ── chrome-window: the player's own notice is not speech ───────────
        ev("""(function(){
          var win=document.querySelector('.caption-window');
          win.innerHTML='';
          var line=document.createElement('div');
          line.className='caption-visual-line';
          var seg=document.createElement('span');
          seg.className='ytp-caption-segment';
          seg.textContent='English';
          line.appendChild(seg);
          var btn=document.createElement('button');   // the player's control
          line.appendChild(btn);
          win.appendChild(line);
          return 1;})()""")
        s5 = snap()
        check("chrome-window: control window dropped from rows", s5 and s5["rows"] == [],
              "rows=%r why=%r" % (s5 and s5["rows"], s5 and s5["why"]))
        check("chrome-window: an empty box is not called painted",
              s5 and s5["why"] == "no-painted-caption",
              "why=%r rows=%r" % (s5 and s5["why"], s5 and s5["rows"]))

        # ── the REAL target picker accepts the fixture tab ─────────────────
        tabs, others = ycs.list_targets(port, timeout=3.0)
        check("targets: the shipped picker sees the tab", len(tabs) >= 1,
              "watch_tabs=%d others=%d" % (len(tabs), others))
        pick, why = ycs.pick_target(tabs, video, "")
        check("targets: pick_target names it", pick is not None, "why=%s" % why)

        # ── the silence/focus guard: a headless run never takes the desktop
        fg1 = foreground()
        check("focus unchanged", fg0["hwnd"] == fg1["hwnd"],
              "before=%d after=%d" % (fg0["hwnd"], fg1["hwnd"]))
        w.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass

    ok = all(c[1] for c in checks)
    print("S2 CAPTIONS: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                       sum(1 for c in checks if c[1]), len(checks)))
    return ok, checks


def cmd_captions(a):
    """S2 -- the caption arm, one command."""
    ok, _checks = run_captions(a.video, a.port)
    return 0 if ok else 1


def cmd_captions_neg(a):
    """The control: a mutated extractor must turn the NAMED check red.

    An arm whose mutants all pass is an arm that cannot fail, so each mutant is
    paired with the one check it has to break. A mutant whose anchor vanished is
    reported `ANCHOR-GONE`, never counted as caught -- a control that was never
    planted proves nothing.
    """
    shipped = os.path.join(ROOT, "app", "webview", "youtube_cdp_source.py")
    caught = 0
    total = 0
    for label, needle, replacement, check_name in CAPTION_MUTANTS:
        total += 1
        mutated = mutant_source(shipped, needle, replacement)
        if mutated is None:
            print("  %-34s ANCHOR-GONE -- the mutant was never planted" % label)
            continue
        # Beside the shipped module: `_load_sibling` resolves siblings BY
        # DIRECTORY, so a copy in the temp root imports a `youtube_window`
        # that is not there and the arm dies before it measures anything.
        tmp = os.path.join(os.path.dirname(shipped), "_ycs_mutant_%d.py" % (total,))
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutated)
        try:
            ok, checks = run_captions(a.video, a.port + total, source=tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        row = next((c for c in checks if c[0] == check_name), None)
        if row is None:
            print("  %-34s CHECK-MISSING %r" % (label, check_name))
        elif row[1] is False:
            caught += 1
            print("  %-34s CAUGHT by %r" % (label, check_name))
        else:
            print("  %-34s NOT-CAUGHT -- %r still passed" % (label, check_name))
    print("S2 NEG-ARM: %s -- %d/%d mutants caught"
          % ("PASS" if caught == total else "FAIL", caught, total))
    return 1 if caught == total else 0


def cmd_window(a):
    """Cut (or hit) a cached 16 kHz WAV window from the video's audio track."""
    src, sm = source_file(a.video)
    idx = load_index()
    ok = 0
    for start, seconds in parse_windows(a.windows):
        key = _window_key(a.video, start, seconds)
        wav = os.path.join(CACHE, "audio", "%s.wav" % key)
        meta = os.path.join(CACHE, "audio", "%s.json" % key)
        if os.path.exists(wav) and os.path.exists(meta) and not a.force:
            with open(meta, encoding="utf-8") as fh:
                m = json.load(fh)
            print("CACHE HIT %s %s %.1f:%ss dur=%.2fs"
                  % (key, a.video, start, seconds, m.get("dur_s") or 0))
            rows.append(m) if False else None
            ok += 1
            continue
        print("MISS %s %s %.1f:%ss" % (key, a.video, start, seconds))
        info = extract_window(src, start, seconds, wav)
        import soundfile as sf
        import numpy as np
        pcm, sr = sf.read(wav, dtype="float32")
        peak = float(np.abs(pcm).max()) if pcm.size else 0.0
        rms = float(np.sqrt((pcm.astype(np.float64) ** 2).mean())) if pcm.size else 0.0
        m = {"key": key, "video": a.video, "start": start, "seconds": seconds,
             "wav": wav, "dur_s": round(info.get("dur_s") or 0, 3), "src_sr": info.get("sr"),
             "peak": round(peak, 5), "rms": round(rms, 5),
             "samples": int(pcm.size), "source": src,
             "audibility": "NO-RENDERER (audio cut from the file, nothing plays)"}
        if peak < 0.01:
            raise SystemExit("REFUSED: window is silence (peak=%.5f)" % peak)
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=2)
            fh.write("\n")
        idx[key] = m
        print("  wrote %s dur=%.2fs peak=%.3f rms=%.4f"
              % (wav, m["dur_s"], peak, rms))
        ok += 1
    save_index(idx)
    return 0 if ok else 1

def _cli():
    """CLI table. Defined AFTER every `cmd_*` so a new command cannot be wired
    before it exists -- measured: `set_defaults(fn=cmd_window)` raised
    NameError because `main()` was defined above the block that adds it."""
    ap = argparse.ArgumentParser(prog="lab", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="capture real audio from a headless browser")
    h.add_argument("--video", required=True)
    h.add_argument("--windows", default="60:20", help="start:seconds[,start:seconds]")
    h.add_argument("--port", type=int, default=9450)
    h.add_argument("--force", action="store_true")
    h.set_defaults(fn=cmd_harvest)

    w = sub.add_parser("window", help="cut cached 16 kHz windows from the audio track")
    w.add_argument("--video", required=True)
    w.add_argument("--windows", default="60:20", help="start:seconds[,start:seconds]")
    w.add_argument("--force", action="store_true")
    w.set_defaults(fn=cmd_window)

    f = sub.add_parser("feed", help="run the real worker over cached audio")
    f.add_argument("--video", required=True)
    f.add_argument("--window", default="60:20", type=float, nargs=2)
    f.add_argument("--lang", default=None)
    f.add_argument("--show", type=int, default=12)
    f.set_defaults(fn=cmd_feed)

    s_ = sub.add_parser("score", help="WER against the video's own captions")
    s_.add_argument("--video", required=True)
    s_.add_argument("--window", default="60:20", type=float, nargs=2)
    s_.add_argument("--lang", default=None)
    s_.add_argument("--gate", action="store_true",
                    help="run the speech/music gate (default OFF for quality runs)")
    s_.set_defaults(fn=cmd_score)

    st = sub.add_parser("strips", help="pipeline ablations over the same audio")
    st.add_argument("--video", required=True)
    st.add_argument("--window", default="60:20", type=float, nargs=2)
    st.set_defaults(fn=cmd_strips)

    c = sub.add_parser("captions",
                       help="S2: drive the REAL extractor over a controlled player")
    c.add_argument("--video", default="rS4VMlwf2qM",
                   help="the id the fixture tab declares (pick_target needs one)")
    c.add_argument("--port", type=int, default=9450)
    c.set_defaults(fn=cmd_captions)

    cn = sub.add_parser("captions-neg",
                        help="S2 control: each mutant must break its named check")
    cn.add_argument("--video", default="rS4VMlwf2qM")
    cn.add_argument("--port", type=int, default=9460)
    cn.set_defaults(fn=cmd_captions_neg)

    sub.add_parser("status", help="what is cached").set_defaults(fn=cmd_status)
    sub.add_parser("selftest", help="judge the audibility gate").set_defaults(fn=cmd_selftest)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(_cli())
