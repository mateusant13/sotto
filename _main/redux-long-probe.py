#!/usr/bin/env python3
"""_main/redux-long-probe.py - long-audio + device instrument for worker/redux_batch.py.

Two questions this probe answers, both with measurements rather than assertions:

  1. LONG AUDIO. ``worker/redux_batch.py`` (Parakeet Redux ternary through Photon/kestrel) was
     only ever given 8.5 s and 15 s. Here it gets 30 s .. 600 s, built out of the three WAVs that
     exist on this box. The probe measures wall time, audio-seconds per compute-second, PEAK RSS
     sampled from OUTSIDE the child, and whether the text covers the whole file (the corpus is
     built so the file ALWAYS ends on the pt-BR clip's last sentence, which makes a dropped tail
     unambiguous).

  2. THE DEVICE. ``--device cuda`` was never tried. Same instrument, plus VRAM sampling with
     ``nvidia-smi``.

Usage
-----
    python _main/redux-long-probe.py build
    python _main/redux-long-probe.py run --cases all --device cpu
    python _main/redux-long-probe.py run --cases plain-120s --device cuda
    python _main/redux-long-probe.py report

Artifacts (all under ``_main/_redux-long/``): the WAV corpus, ``layout-<case>.json`` sidecars
(so a segment boundary can be checked against a known splice point), ``logs/`` with the child's
raw stdout/stderr, and ``results-<device>.json`` (appended, one record per run).

It never opens an audio device (WAV files only), never spawns a visible window
(``CREATE_NO_WINDOW``) and never touches the owner's app. It reads ``worker/redux_batch.py``,
it does not modify it.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import statistics
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import psutil

R = Path(__file__).resolve().parent.parent          # H:\sotto
RUNNER = R / "worker" / "redux_batch.py"
OUT = R / "_main" / "_redux-long"
LOGS = OUT / "logs"
RATE = 16000

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

SOURCES = {
    "pt": R / "_main" / "pt-br-sample.wav",
    "en": R / "_main" / "en-us-sample.wav",
    "agc": R / "_main" / "agc_drone_floor.wav",
}
# The corpus cycles through these, and ALWAYS ends on a whole "pt" piece: its last sentence is
# the tail sentinel, so a truncated run is visible in the text itself.
CYCLE = ("pt", "en", "agc")
SENTINEL = "pt"

PT_TAIL = "Os moradores precisam de um caminho alternativo para chegar ao trabalho."
EN_HEAD = "The radio announced that the bridge over the river will be closed next Monday."

# (case, target_seconds, gap_seconds). Sources are used directly as their own cases.
LONG_CASES = (
    ("plain-30s", 30.0, 0.0),
    ("plain-60s", 60.0, 0.0),
    ("plain-120s", 120.0, 0.0),
    ("plain-300s", 300.0, 0.0),
    ("plain-600s", 600.0, 0.0),
    ("plain-1800s", 1800.0, 0.0),
    ("plain-3600s", 3600.0, 0.0),
    ("gap-120s", 120.0, 1.0),
    ("gap-300s", 300.0, 1.0),
    ("gap-600s", 600.0, 1.0),
)
SRC_CASES = (("src-en-8s", "en"), ("src-pt-15s", "pt"), ("src-agc-20s", "agc"))
CASE_NAMES = tuple(c for c, _, _ in LONG_CASES) + tuple(c for c, _ in SRC_CASES)


# --------------------------------------------------------------------------- WAV I/O

def read_wav(path: Path) -> np.ndarray:
    """Read any mono/stereo 16-bit WAV and return 16 kHz mono int16.

    The three sources on this box are 22050 / 22050 / 48000 Hz (measured), i.e. none of them is
    the 16 kHz the model wants. ``kestrel_native`` has its own ``resample_audio_mono`` and would
    resample anyway; doing it here makes the corpus genuinely "16 kHz mono WAV" as asked, and
    makes the piece layout exact. ``resample_poly`` (scipy, polyphase) is used, not linear
    interpolation.
    """
    from math import gcd
    from scipy.signal import resample_poly

    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"{path}: {sw * 8}-bit samples, this probe only builds 16-bit WAVs")
    a = np.frombuffer(raw, dtype="<i2")
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1).round().astype("<i2")
    if sr != RATE:
        g = gcd(RATE, sr)
        a = resample_poly(a.astype(np.float64), RATE // g, sr // g)
        a = np.clip(np.round(a), -32768, 32767).astype("<i2")
    return np.ascontiguousarray(a)


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.astype("<i2").tobytes())


def ref_texts() -> dict:
    """The two reference transcripts, if the earlier lane left them on disk."""
    out = {}
    for key, name in (("pt", "redux-ptbr.txt"), ("en", "redux-en.txt")):
        p = R / "_main" / name
        if not p.is_file():
            continue
        raw = p.read_bytes()
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            lines = raw.decode("cp1252").splitlines()
        keep = [ln.strip() for ln in lines if ln.strip() and not ln.lower().startswith("model loaded")]
        if keep:
            out[key] = keep[-1]
    return out


# --------------------------------------------------------------------------- corpus

def build_corpus() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    src = {k: read_wav(p) for k, p in SOURCES.items()}
    ref = ref_texts()
    for k, a in src.items():
        with wave.open(str(SOURCES[k]), "rb") as w:
            orig = f"{w.getframerate()} Hz/{w.getnchannels()}ch"
        print(f"source {k}: {SOURCES[k].name} {orig} -> 16 kHz mono {len(a) / RATE:.3f}s  "
              f"{len(a)} samples")

    report = {"sources": {k: {"path": str(SOURCES[k]), "seconds_16k": round(len(a) / RATE, 3)}
                          for k, a in src.items()}, "cases": {}}

    # 1. the three sources as their own cases (the small end of the RSS curve)
    for case, key in SRC_CASES:
        a = src[key]
        write_wav(OUT / f"{case}.wav", a)
        report["cases"][case] = {
            "seconds": round(len(a) / RATE, 3), "gap": 0.0, "pieces": [],
            "note": "raw source file, copied",
        }

    # 2. the long cases
    for case, target, gap in LONG_CASES:
        samples, layout, expect = assemble(src, target, gap)
        write_wav(OUT / f"{case}.wav", samples)
        side = {"seconds": round(len(samples) / RATE, 3), "gap": gap,
                "pieces": layout, "expected_chars": expect, "ref_texts": ref}
        (OUT / f"layout-{case}.json").write_text(json.dumps(side, indent=1), encoding="utf-8")
        report["cases"][case] = {k: side[k] for k in ("seconds", "gap", "expected_chars")}
        print(f"built {case}.wav  {side['seconds']}s  gap={gap}s  "
              f"pieces={len(layout)}  expected_chars~{expect}")
    (OUT / "corpus.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


def assemble(src: dict, target: float, gap: float):
    """Concatenate whole/partial source pieces up to ``target`` seconds.

    The fill runs through CYCLE and is cut at exactly the remaining budget (so a partial piece,
    and a partial sentence in the transcript, is expected at the fill boundary). A WHOLE
    ``pt`` piece is always appended last, after a gap if gaps are on, so the file's final words
    are the pt-BR clip's final sentence whatever the fill did.
    """
    g = int(round(gap * RATE))
    total = int(round(target * RATE))
    sent = src[SENTINEL]
    budget = total - len(sent) - (g if gap else 0)
    if budget <= 0:
        raise SystemExit(f"target {target}s is too short for the sentinel piece")

    parts, layout, expect = [], [], 0
    pos = 0
    i = 0
    while budget > 0:
        key = CYCLE[i % len(CYCLE)]
        i += 1
        if pos > 0 and g:
            gn = min(g, budget)
            parts.append(np.zeros(gn, dtype="<i2"))
            pos += gn
            budget -= gn
            if budget <= 0:
                break
        a = src[key]
        take = min(len(a), budget)
        parts.append(a[:take])
        layout.append({"src": key, "start": round(pos / RATE, 3), "dur": round(take / RATE, 3),
                       "whole": take == len(a)})
        pos += take
        budget -= take
    # expected character estimate: proportional to the fraction of each piece that survived
    expect = 0
    for p in layout:
        if p["src"] == "pt":
            expect += 155 * (p["dur"] / (len(src["pt"]) / RATE))
        elif p["src"] == "en":
            expect += 130 * (p["dur"] / (len(src["en"]) / RATE))
    expect += 155  # the sentinel pt piece, whole
    if g:
        parts.append(np.zeros(g, dtype="<i2"))
        pos += g
    layout.append({"src": SENTINEL, "start": round(pos / RATE, 3),
                   "dur": round(len(sent) / RATE, 3), "whole": True, "sentinel": True})
    parts.append(sent)
    out = np.concatenate(parts) if parts else np.zeros(0, dtype="<i2")
    return out, layout, int(round(expect))


# --------------------------------------------------------------------------- windows / VRAM

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def visible_windows(pids: set) -> list:
    """Top-level windows that are WS_VISIBLE and belong to ``pids`` (alpha is NOT checked)."""
    hits = []

    def cb(hwnd, _lparam):
        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.IsWindowVisible(hwnd):
            n = _user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, title, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, cls, 256)
            hits.append({"pid": pid.value, "hwnd": int(hwnd), "title": title.value,
                         "class": cls.value})
        return True

    _user32.EnumWindows(_WNDENUMPROC(cb), 0)
    return hits


def vram() -> tuple:
    """(used MiB, total MiB) from nvidia-smi, or (None, None) if it is not there."""
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if p.returncode != 0 or not p.stdout.strip():
        return None, None
    used, _, total = p.stdout.strip().splitlines()[0].partition(",")
    try:
        return int(used.strip()), int(total.strip())
    except ValueError:
        return None, None


def gpu_procs() -> set:
    """PIDs nvidia-smi reports as holding a compute context."""
    return set(gpu_proc_mem())


def gpu_proc_mem() -> dict:
    """{pid: MiB} for every process nvidia-smi sees holding a compute context.

    This is the attribution instrument: ``memory.used`` is the WHOLE GPU and moves with whatever
    else the owner's desktop is doing (measured range on this box: 2.7 GiB .. 15.5 GiB of 15.9 GiB
    while these runs were going on), so a before/after delta only bounds the child's own VRAM.
    ``--query-compute-apps`` names the child's own allocation.
    """
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for ln in p.stdout.splitlines():
        pid, _, mib = ln.strip().partition(",")
        try:
            out[int(pid.strip())] = int(mib.strip())
        except ValueError:
            continue
    return out


# --------------------------------------------------------------------------- one run

def run_case(case: str, device: str, timestamps: str, cadence: float, vram_every: int,
             gpu_watch: bool = False, max_wall: float | None = None) -> dict:
    wav = OUT / f"{case}.wav"
    if not wav.is_file():
        raise SystemExit(f"no corpus file {wav}; run `build` first")

    with wave.open(str(wav), "rb") as w:
        audio_s = w.getnframes() / w.getframerate()

    stem = f"{case}.{device}.{timestamps}"
    fo = open(LOGS / f"{stem}.stdout.txt", "wb")
    fe = open(LOGS / f"{stem}.stderr.txt", "wb")

    cmd = [sys.executable, str(RUNNER), "--wav", str(wav), "--json",
           "--device", device, "--timestamps", timestamps]
    timeout = 300.0 + 1.0 * audio_s
    if max_wall is not None:
        timeout = float(max_wall)
    vram_before, vram_total = vram()
    gpu_before = gpu_procs()

    rec = {
        "case": case, "device": device, "timestamps": timestamps, "wav": str(wav),
        "audio_seconds": round(audio_s, 3), "command": subprocess.list2cmdline(cmd),
        "cwd": str(R), "cadence_s": cadence, "timeout_s": round(timeout, 1),
        "vram_before_mib": vram_before, "vram_total_mib": vram_total,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(cmd, cwd=str(R), stdout=fo, stderr=fe,
                                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS)
    except OSError as exc:
        fo.close()
        fe.close()
        rec.update({"rc": None, "error": f"spawn failed: {exc!r}"})
        return rec

    ps = psutil.Process(proc.pid)

    # The child's OWN dedicated VRAM, sampled by a PowerShell helper reading the
    # \GPU Process Memory(pid_<child>_*)\Dedicated Usage perf counter -- the only instrument on this
    # WDDM box that attributes VRAM to a pid (`nvidia-smi --query-compute-apps` prints [N/A]).
    watcher = None
    watch_out = LOGS / f"{stem}.gpuwatch.txt"
    if gpu_watch:
        try:
            watch_out.unlink()
        except OSError:
            pass
        helper = OUT / "_gpu-watch.ps1"
        watcher = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper),
             "-TargetPid", str(proc.pid), "-Seconds", str(int(timeout)), "-Out", str(watch_out)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW)
    peak_rss = 0
    peak_wset = 0
    rss_samples = []
    vram_samples = []
    cpu_samples = []
    window_hits = []
    gpu_during = set()
    child_vram = []
    child_on_gpu = False
    i = 0
    hung = False
    rc = None
    try:
        while True:
            rc = proc.poll()
            try:
                mi = ps.memory_info()
                rss = mi.rss
                peak_rss = max(peak_rss, rss)
                rss_samples.append(round(rss / 2**20, 1))
                peak_wset = max(peak_wset, getattr(mi, "peak_wset", 0) or 0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if i % 4 == 0:
                cpu_samples.append(psutil.cpu_percent(interval=None))
            if vram_every and i % vram_every == 0:
                u, _t = vram()
                if u is not None:
                    vram_samples.append(u)
                if i % (vram_every * 4) == 0:
                    here = gpu_proc_mem()
                    gpu_during |= set(here)
                    if proc.pid in here:
                        child_on_gpu = True
                        child_vram.append(here[proc.pid])
            hits = visible_windows({proc.pid})
            if hits:
                window_hits.extend(hits)
            if rc is not None:
                break
            if time.perf_counter() - t0 > timeout:
                hung = True
                proc.kill()
                rc = proc.wait()
                break
            time.sleep(cadence)
            i += 1
    finally:
        wall = time.perf_counter() - t0
        fo.close()
        fe.close()

    vram_after, _ = vram()
    if watcher is not None:
        try:
            watcher.kill()
        except OSError:
            pass
        watcher.wait(timeout=20)
    stdout = (LOGS / f"{stem}.stdout.txt").read_bytes().decode("utf-8", "replace")
    stderr = (LOGS / f"{stem}.stderr.txt").read_bytes().decode("utf-8", "replace")

    captions, result = [], None
    for ln in stdout.splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "caption":
            captions.append(obj)
        elif obj.get("type") == "result":
            result = obj

    text = (result or {}).get("text") or "".join(c.get("text", "") for c in captions)
    tail_ok = PT_TAIL in text
    last_end = max([float(c.get("end") or 0.0) for c in captions], default=None)

    boundaries = []
    layout_path = OUT / f"layout-{case}.json"
    if layout_path.is_file():
        layout = json.loads(layout_path.read_text(encoding="utf-8"))["pieces"]
        starts = [p["start"] for p in layout[1:]]
        for s in starts:
            near = min((abs(float(c.get("start") or 0.0) - s) for c in captions), default=None)
            boundaries.append({"expected": s, "nearest_segment_start": None if near is None else round(near, 3),
                               "hit": bool(near is not None and near <= 0.75)})

    compute = (result or {}).get("compute_seconds")
    watched_vram = None
    if watch_out.is_file():
        head = watch_out.read_text(encoding="ascii", errors="replace").splitlines()
        for ln in head:
            if ln.startswith("max_mib="):
                try:
                    watched_vram = float(ln.split("=", 1)[1])
                except ValueError:
                    pass
                break
        if watched_vram is None:  # the helper was killed before its final line: use the running max
            best = 0.0
            for ln in head[1:]:
                parts = ln.split(",")
                if len(parts) == 3:
                    try:
                        best = max(best, float(parts[2]))
                    except ValueError:
                        pass
            watched_vram = best or None
        watch_rows = len(head) - 1
    else:
        watch_rows = 0
    rec["gpu_watch_rows"] = watch_rows
    rec.update({
        "rc": rc, "wall_seconds": round(wall, 3), "hung": hung,
        "peak_rss_mib": round(peak_rss / 2**20, 1),
        "peak_rss_gib": round(peak_rss / 2**30, 3),
        "peak_wset_mib_reported_by_os": round(peak_wset / 2**20, 1),
        "rss_samples_mib": rss_samples,
        "vram_peak_mib": max(vram_samples) if vram_samples else None,
        "vram_after_mib": vram_after,
        "vram_samples_mib": vram_samples,
        "gpu_procs_before": sorted(gpu_before),
        "gpu_procs_during": sorted(gpu_during),
        "child_held_gpu_context": child_on_gpu,
        "child_vram_samples_mib": child_vram,
        "child_vram_peak_mib": max(child_vram) if child_vram else None,
        "child_vram_from_perfcounter_mib": watched_vram,
        "cpu_percent_samples": cpu_samples,
        "cpu_percent_median": round(statistics.median(cpu_samples), 1) if cpu_samples else None,
        "cpu_percent_max": max(cpu_samples) if cpu_samples else None,
        "visible_window_samples": len(window_hits),
        "windows": window_hits[:5],
        "load_stderr": [ln for ln in stderr.splitlines() if "loaded in" in ln or "weight form" in ln],
        "timing_stderr": [ln for ln in stderr.splitlines() if "of audio in" in ln],
        "stderr_tail": stderr.splitlines()[-12:],
        "n_captions": len(captions),
        "text_chars": len(text),
        "duration_reported": (result or {}).get("duration"),
        "compute_seconds": compute,
        "x_real_inference": (result or {}).get("real_time_factor"),
        "x_real_inference_measured": round(audio_s / compute, 2) if compute else None,
        "x_real_wall": round(audio_s / wall, 2) if wall else None,
        "tail_sentinel_present": tail_ok,
        "tail_sentinel_at_end": bool(text.strip().endswith(PT_TAIL)) if tail_ok else False,
        "sentinel_count": text.count(PT_TAIL),
        "english_head_count": text.count(EN_HEAD),
        "last_caption_end": last_end,
        "coverage": round(last_end / audio_s, 3) if (last_end and audio_s) else None,
        "boundaries": boundaries,
        "boundary_hits": sum(1 for b in boundaries if b["hit"]),
        "boundary_total": len(boundaries),
        "segments": captions,
    })
    return rec


# --------------------------------------------------------------------------- report

def load_results(device: str) -> list:
    p = OUT / f"results-{device}.json"
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_results(device: str, recs: list) -> None:
    p = OUT / f"results-{device}.json"
    p.write_text(json.dumps(recs, indent=1), encoding="utf-8")


def print_table(recs: list, title: str) -> None:
    print(f"\n=== {title} ===")
    hdr = (f"{'case':<12}{'audio_s':>9}{'wall_s':>9}{'xreal_w':>9}{'xreal_inf':>10}"
           f"{'peakRSS_GB':>12}{'peakVRAM_MB':>12}{'rc':>4}{'seg':>5}{'chars':>7}"
           f"{'cov':>7}{'bnd':>8}{'tail':>6}{'hang':>6}{'cpu%':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in recs:
        bnd = (f"{r.get('boundary_hits')}/{r.get('boundary_total')}"
               if r.get("boundary_total") else "-")
        print(f"{r['case']:<12}{r['audio_seconds']:>9.2f}{r.get('wall_seconds', 0):>9.2f}"
              f"{r.get('x_real_wall') or 0:>9.2f}{r.get('x_real_inference_measured') or 0:>10.2f}"
              f"{r.get('peak_rss_gib') or 0:>12.3f}{r.get('vram_peak_mib') or 0:>12}"
              f"{r.get('rc')!s:>4}{r.get('n_captions', 0):>5}{r.get('text_chars', 0):>7}"
              f"{r.get('coverage') or 0:>7.2f}{bnd:>8}"
              f"{'yes' if r.get('tail_sentinel_present') else 'NO':>6}"
              f"{'HUNG' if r.get('hung') else '':>6}{r.get('cpu_percent_median') or 0:>7.1f}")


# --------------------------------------------------------------------------- main

def print_detail(recs: list, title: str) -> None:
    print(f"\n=== {title} -- per-run detail ===")
    for r in recs:
        rs = r.get("rss_samples_mib") or []
        print(f"\n-- {r['case']}  (device={r.get('device')}, started {r.get('started')})")
        print(f"   audio={r['audio_seconds']}s  wall={r.get('wall_seconds')}s  "
              f"compute={r.get('compute_seconds')}s  xreal_inference={r.get('x_real_inference_measured')}  "
              f"xreal_wall_incl_load={r.get('x_real_wall')}")
        print(f"   peak RSS (my 0.25 s poll) = {r.get('peak_rss_gib')} GiB "
              f"({r.get('peak_rss_mib')} MiB); OS peak_wset = {r.get('peak_wset_mib_reported_by_os')} MiB; "
              f"{len(rs)} samples, first={rs[0] if rs else None} last={rs[-1] if rs else None}")
        print(f"   cpu% median={r.get('cpu_percent_median')} max={r.get('cpu_percent_max')}   "
              f"VRAM before={r.get('vram_before_mib')} peak={r.get('vram_peak_mib')} "
              f"after={r.get('vram_after_mib')} of {r.get('vram_total_mib')} MiB   "
              f"child_held_gpu_context={r.get('child_held_gpu_context')}  "
              f"child's OWN VRAM peak={r.get('child_vram_peak_mib')} MiB "
              f"({len(r.get('child_vram_samples_mib') or [])} samples)")
        print(f"   visible windows for the child pid: {r.get('visible_window_samples')} sample(s) "
              f"of {len(rs)} at 0.25 s {r.get('windows')}")
        print(f"   rc={r.get('rc')} hung={r.get('hung')}  load: {r.get('load_stderr')}")
        print(f"   timing: {r.get('timing_stderr')}")
        print(f"   captions={r.get('n_captions')} chars={r.get('text_chars')} "
              f"duration_reported={r.get('duration_reported')} "
              f"last_caption_end={r.get('last_caption_end')} coverage={r.get('coverage')}")
        print(f"   tail sentinel present={r.get('tail_sentinel_present')} "
              f"at_end={r.get('tail_sentinel_at_end')} count={r.get('sentinel_count')}   "
              f"english head count={r.get('english_head_count')}")
        if r.get("boundary_total"):
            print(f"   splice points landing on a segment start (<=0.75 s): "
                  f"{r.get('boundary_hits')}/{r.get('boundary_total')}")
            for b in r["boundaries"]:
                print(f"      expected {b['expected']:>9.3f}  nearest segment start "
                      f"{b['nearest_segment_start']}  hit={b['hit']}")
        segs = r.get("segments") or []
        if segs:
            print(f"   first caption: {json.dumps(segs[0], ensure_ascii=False)[:220]}")
            print(f"   last  caption: {json.dumps(segs[-1], ensure_ascii=False)[:220]}")
        if r.get("stderr_tail"):
            for ln in r["stderr_tail"]:
                print(f"   stderr| {ln}")


def parity(cases: list, timestamps: str) -> int:
    """Byte-compare the CPU and CUDA caption streams for the same WAV.

    ``result`` lines are excluded on purpose: they carry ``compute_seconds``,
    ``real_time_factor``, ``wav`` and ``model_dir``, i.e. the run, not the transcript. What must
    match is the caption stream and the decoded ``text``.
    """
    bad = 0
    for case in cases:
        a = LOGS / f"{case}.cpu.{timestamps}.stdout.txt"
        b = LOGS / f"{case}.cuda.{timestamps}.stdout.txt"
        if not (a.is_file() and b.is_file()):
            print(f"{case}: MISSING log pair")
            bad += 1
            continue

        def split(p):
            caps, text = [], None
            for ln in p.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln.startswith("{"):
                    continue
                obj = json.loads(ln)
                if obj.get("type") == "caption":
                    caps.append(json.dumps(obj, ensure_ascii=False, sort_keys=True))
                elif obj.get("type") == "result":
                    text = obj.get("text")
            return caps, text

        ca, ta = split(a)
        cb, tb = split(b)
        same_caps = ca == cb
        same_text = ta == tb
        if same_caps and same_text:
            print(f"{case}: IDENTICAL  captions={len(ca)}  text_chars={len(ta or '')}")
        else:
            bad += 1
            print(f"{case}: DIFFERS  captions cpu={len(ca)} cuda={len(cb)}  "
                  f"text_equal={same_text}")
            if not same_text:
                print(f"   cpu : {ta}")
                print(f"   cuda: {tb}")
            for i, (x, y) in enumerate(zip(ca, cb)):
                if x != y:
                    print(f"   caption[{i}]\n      cpu : {x}\n      cuda: {y}")
    print(f"PARITY: {'PASS' if bad == 0 else f'FAIL on {bad} case(s)'}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="redux-long-probe", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="build the long WAV corpus in _main/_redux-long/")

    r = sub.add_parser("run", help="run the batch runner on corpus cases and measure")
    r.add_argument("--cases", default="all",
                   help="comma list of case names, or 'all', or 'long' (default all)")
    r.add_argument("--device", default="cpu", choices=("cpu", "cuda", "mps"))
    r.add_argument("--timestamps", default="segment")
    r.add_argument("--cadence", type=float, default=0.25, help="RSS/window sample period in s")
    r.add_argument("--vram-every", type=int, default=4, help="sample nvidia-smi every Nth tick")
    r.add_argument("--keep", action="store_true", help="keep earlier records of the same case")
    r.add_argument("--gpu-watch", action="store_true",
                   help="also sample the child's OWN dedicated VRAM with _gpu-watch.ps1")
    r.add_argument("--max-wall", type=float, default=None,
                   help="hard wall-clock cap in seconds, overriding 300 + audio_seconds. A run that "
                        "hits it is reported hung=True; hour-length CUDA runs stall, and this bounds "
                        "the cost of proving that.")

    rp = sub.add_parser("report", help="print the measured tables from disk")
    rp.add_argument("--device", default=None)
    rp.add_argument("--detail", action="store_true", help="also print the per-run detail block")

    pp = sub.add_parser("parity", help="compare the CPU and CUDA caption streams, case by case")
    pp.add_argument("--cases", default="all")
    pp.add_argument("--timestamps", default="segment")

    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    if args.cmd == "build":
        build_corpus()
        return 0

    if args.cmd == "report":
        devices = [args.device] if args.device else ["cpu", "cuda"]
        for d in devices:
            recs = load_results(d)
            if recs:
                print_table(recs, f"device={d}")
                if args.detail:
                    print_detail(recs, f"device={d}")
        return 0

    if args.cmd == "parity":
        cases = (list(CASE_NAMES) if args.cases == "all"
                 else [c.strip() for c in args.cases.split(",") if c.strip()])
        return parity(cases, args.timestamps)

    if args.cases == "all":
        cases = list(CASE_NAMES)
    elif args.cases == "long":
        cases = [c for c, _, _ in LONG_CASES]
    else:
        cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    unknown = [c for c in cases if c not in CASE_NAMES]
    if unknown:
        raise SystemExit(f"unknown case(s): {unknown}; known: {list(CASE_NAMES)}")

    recs = load_results(args.device) if args.keep else []
    new = []
    for case in cases:
        print(f"[{time.strftime('%H:%M:%S')}] running {case} on {args.device} ...", flush=True)
        rec = run_case(case, args.device, args.timestamps, args.cadence, args.vram_every,
                       gpu_watch=args.gpu_watch, max_wall=args.max_wall)
        new.append(rec)
        recs = recs + [rec]
        save_results(args.device, recs)
        print(f"    rc={rec.get('rc')} wall={rec.get('wall_seconds')}s "
              f"peakRSS={rec.get('peak_rss_gib')}GiB xreal_inf={rec.get('x_real_inference_measured')} "
              f"segs={rec.get('n_captions')} tail={rec.get('tail_sentinel_present')} "
              f"cov={rec.get('coverage')} hang={rec.get('hung')}", flush=True)
        if rec.get("stderr_tail"):
            for ln in rec["stderr_tail"][-4:]:
                print(f"    stderr| {ln}", flush=True)
    print_table(new, f"device={args.device} (this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
