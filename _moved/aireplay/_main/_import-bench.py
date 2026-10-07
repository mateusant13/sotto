# -*- coding: utf-8 -*-
"""_import-bench.py -- lane 08 (import library). MEASUREMENT ONLY.

What it does NOT do: it does not scan, index, or open ANY of the owner's video files.
The one file it reads outside H:\\aireplay is a HuggingFace model blob on the HDD --
non-personal, read-only, opened with FILE_FLAG_NO_BUFFERING so the number is the device.

Produces _main/_import-bench/summary.json + summary.txt.
Every ffmpeg is spawned with CREATE_NO_WINDOW; this script must be launched with pythonw.exe.
"""
import ctypes
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_import-bench")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "run.log"), "w", encoding="utf-8", buffering=1)
FF = shutil.which("ffmpeg")
FP = shutil.which("ffprobe")
NO_WINDOW = 0x08000000
NUL = "NUL"
R = {}

# HDD (Seagate ST4000DM004, I:) -- non-personal model blob, 4 220 320 824 B
HDD = r"I:\codeintel\hf-cache\hub\models--Qwen--Qwen3-ASR-1.7B\blobs\a4cd1f1a04d90b757dc7f7dd26254e69a013b19e80efe590a83c6a3bde8608d6"
VID = os.path.join(OUT, "synth-180s-1080p30.mp4")


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n")
    print(s)


def run(args, timeout=600):
    t0 = time.perf_counter()
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=NO_WINDOW, timeout=timeout)
    return time.perf_counter() - t0, p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def stat(xs):
    xs = sorted(xs)
    if not xs:
        return None
    return {"n": len(xs), "min": round(xs[0], 4), "median": round(statistics.median(xs), 4),
            "mean": round(sum(xs) / len(xs), 4), "max": round(xs[-1], 4)}


# ---------------------------------------------------------------- raw device reads
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
FILE_FLAG_RANDOM_ACCESS = 0x10000000
MEM_COMMIT_RESERVE = 0x3000
PAGE_READWRITE = 0x04
INVALID = ctypes.c_void_p(-1).value

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                 ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]


def dev_open(path, flags):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, flags, None)
    if h == INVALID:
        raise OSError("CreateFileW failed %d for %s" % (ctypes.get_last_error(), path))
    return h


def buf(size):
    p = k32.VirtualAlloc(None, size, MEM_COMMIT_RESERVE, PAGE_READWRITE)
    if not p:
        raise MemoryError("VirtualAlloc")
    return p


def read_at(h, ptr, off, size):
    k32.SetFilePointerEx(h, off, None, 0)
    n = wintypes.DWORD(0)
    if not k32.ReadFile(h, ctypes.c_void_p(ptr), size, ctypes.byref(n), None):
        raise OSError("ReadFile %d" % ctypes.get_last_error())
    return n.value


def seq_read(path, tag, total_mb=512, chunk_mb=8, offset_mb=256, flags=FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN):
    h = dev_open(path, flags)
    size = chunk_mb << 20
    p = buf(size)
    total = total_mb << 20
    off = offset_mb << 20
    t0 = time.perf_counter()
    done = 0
    while done < total:
        done += read_at(h, p, off + done, size)
    dt = time.perf_counter() - t0
    k32.CloseHandle(h)
    mb = done / 1048576.0
    log("[seq] %s: %.1f MiB in %.3fs = %.1f MB/s" % (tag, mb, dt, mb / dt))
    return {"tag": tag, "bytes": done, "seconds": round(dt, 3), "MB_per_s": round(mb / dt, 1),
            "flags": hex(flags), "start_offset": off}


def rand_read(path, tag, n=200, block=4096, span_mb=2048, seed=7):
    rnd = random.Random(seed)
    h = dev_open(path, FILE_FLAG_NO_BUFFERING | FILE_FLAG_RANDOM_ACCESS)
    p = buf(block)
    offs = [rnd.randrange(0, span_mb << 20, 4096) for _ in range(n)]
    lats = []
    t0 = time.perf_counter()
    for o in offs:
        a = time.perf_counter()
        read_at(h, p, o, block)
        lats.append((time.perf_counter() - a) * 1000.0)
    dt = time.perf_counter() - t0
    k32.CloseHandle(h)
    mb = n * block / 1048576.0
    log("[rand1] %s: %d x 4 KiB in %.3fs = %.2f MB/s, median lat %.2f ms" % (tag, n, dt, mb / dt, statistics.median(lats)))
    return {"tag": tag, "reads": n, "seconds": round(dt, 3), "MB_per_s": round(mb / dt, 2),
            "latency_ms_median": round(statistics.median(lats), 2),
            "latency_ms_p95": round(sorted(lats)[int(0.95 * n) - 1], 2)}


def rand_read_mt(path, tag, threads=8, per=25, block=4096, span_mb=2048, seed=11):
    rnd = random.Random(seed)
    plan = [[rnd.randrange(0, span_mb << 20, 4096) for _ in range(per)] for _ in range(threads)]
    results = []
    start = threading.Event()

    def work(offs):
        h = dev_open(path, FILE_FLAG_NO_BUFFERING | FILE_FLAG_RANDOM_ACCESS)
        p = buf(block)
        start.wait()
        lats = []
        for o in offs:
            a = time.perf_counter()
            read_at(h, p, o, block)
            lats.append((time.perf_counter() - a) * 1000.0)
        k32.CloseHandle(h)
        results.append(lats)

    ts = [threading.Thread(target=work, args=(pl,)) for pl in plan]
    for t in ts:
        t.start()
    t0 = time.perf_counter()
    start.set()
    for t in ts:
        t.join()
    dt = time.perf_counter() - t0
    n = threads * per
    mb = n * block / 1048576.0
    allm = [x for r in results for x in r]
    log("[randN] %s: %d x 4 KiB on %d threads in %.3fs = %.2f MB/s, median lat %.2f ms" %
        (tag, n, threads, dt, mb / dt, statistics.median(allm)))
    return {"tag": tag, "reads": n, "threads": threads, "seconds": round(dt, 3),
            "MB_per_s": round(mb / dt, 2), "latency_ms_median": round(statistics.median(allm), 2)}


def bench_device(path, tag):
    r = {}
    r["seq_512m"] = seq_read(path, tag + " seq")
    r["rand_4k_1thr"] = rand_read(path, tag + " rand")
    r["rand_4k_8thr"] = rand_read_mt(path, tag + " rand8")
    return r


# ---------------------------------------------------------------- media measurements
def make_synth():
    cmd = [FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
           "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
           "-t", "180",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
           "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
           "-c:a", "aac", "-b:a", "128k", "-shortest", VID]
    dt, rc, o, e = run(cmd, timeout=900)
    sz = os.path.getsize(VID)
    log("[synth] %.1fs rc=%d %d B = %.1f MB" % (dt, rc, sz, sz / 1048576.0))
    return {"encode_s": round(dt, 3), "rc": rc, "bytes": sz, "stderr": e[-400:]}


def media():
    r = {"synth": make_synth()}
    mbits = os.path.getsize(VID) * 8 / 180 / 1e6
    r["synth_mbps"] = round(mbits, 2)

    # 1. header/metadata probe (stage D0)
    ts = []
    for _ in range(5):
        dt, rc, o, e = run([FP, "-v", "error", "-print_format", "json",
                            "-show_entries", "format=duration,size,bit_rate:stream=codec_name,width,height,r_frame_rate",
                            VID], timeout=60)
        ts.append(dt)
    r["probe_header"] = stat(ts)
    r["probe_header_json"] = o[:400]

    # 2. full decode, video+audio
    ts = []
    for _ in range(3):
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", VID, "-f", "null", NUL], timeout=900)
        ts.append(dt)
    r["full_decode"] = stat(ts)
    r["full_decode_fps"] = round(180 * 30 / statistics.median(ts), 1)
    r["full_decode_rtf"] = round(180 / statistics.median(ts), 1)

    # 3. audio demux + 16 kHz mono WAV (what ASR actually eats)
    ts = []
    for _ in range(3):
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", VID,
                            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", NUL], timeout=900)
        ts.append(dt)
    r["audio_to_wav16k"] = stat(ts)
    r["audio_to_wav16k_rtf"] = round(180 / statistics.median(ts), 1)

    # 4. one 30 s audio chunk (the unit of work a crash must not lose)
    ts = []
    for _ in range(5):
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", "100", "-t", "30", "-i", VID,
                            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", NUL], timeout=300)
        ts.append(dt)
    r["audio_chunk_30s"] = stat(ts)

    # 5. thumbnail: input-side seek (correct) vs output-side seek (the trap)
    good, bad, sizes = [], [], []
    for t in [5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 105, 115, 125, 135, 145, 155, 165, 175]:
        jpg = os.path.join(OUT, "thumb.jpg")
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", VID,
                            "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", "-y", jpg], timeout=300)
        good.append(dt)
        sizes.append(os.path.getsize(jpg))
    r["thumb_seek_before_i"] = stat(good)
    r["thumb_jpeg_bytes"] = stat(sizes)
    for _ in range(3):
        jpg = os.path.join(OUT, "thumb_bad.jpg")
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", VID, "-ss", "170",
                            "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", "-y", jpg], timeout=600)
        bad.append(dt)
    r["thumb_seek_after_i_t170"] = stat(bad)

    # 6. 1 fps gallery (what a naive "index every second" costs)
    frames = os.path.join(OUT, "fps1_%04d.jpg")
    dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", VID,
                        "-vf", "fps=1,scale=320:-2", "-q:v", "4", "-y", frames], timeout=900)
    made = [f for f in os.listdir(OUT) if f.startswith("fps1_")]
    tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in made)
    r["gallery_1fps"] = {"seconds": round(dt, 3), "frames": len(made), "total_bytes": tot,
                         "bytes_per_frame": int(tot / max(1, len(made))),
                         "per_video_5min_MB": round(tot / 180 * 300 / 1048576.0, 1)}
    log("[1fps] %d frames in %.1fs, %.1f MB total" % (len(made), dt, tot / 1048576.0))
    for f in made:
        os.remove(os.path.join(OUT, f))

    # 7. input seek only, no decode: does the container seek cost anything?
    ts = []
    for t in [30, 90, 150]:
        dt, rc, o, e = run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", VID,
                            "-vn", "-f", "null", NUL], timeout=300)
        ts.append(dt)
    r["audio_seek_only"] = stat(ts)
    return r


def main():
    t_start = time.time()
    R["host"] = {"ffmpeg": FF, "ffprobe": FP, "python": sys.version.split()[0], "cwd": os.getcwd()}
    if not (FF and FP):
        log("FATAL: ffmpeg/ffprobe not found")
        return
    R["hdd_I"] = {"path": HDD, "bytes": os.path.getsize(HDD)}
    R["hdd_I"].update(bench_device(HDD, "I: HDD ST4000DM004"))
    R["media"] = media()
    # NVMe control: same measurement on H: using the file we just wrote
    R["nvme_H"] = seq_read(VID, "H: NVMe (synthetic, 256 MiB no-buffering)",
                           total_mb=min(256, max(1, os.path.getsize(VID) >> 20) - 8))
    R["wall_seconds"] = round(time.time() - t_start, 1)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2)
    log("DONE in %.1fs" % R["wall_seconds"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa
        import traceback
        log("EXCEPTION: " + repr(exc))
        log(traceback.format_exc())
        with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
            json.dump({"error": repr(exc), "partial": R}, f, indent=2)
        raise
