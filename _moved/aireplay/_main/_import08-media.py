# -*- coding: utf-8 -*-
"""_import08-media.py -- lane 08 (import library): the per-stage costs the 1000-video
import design needs, and the READ AMPLIFICATION of each stage.

MEASUREMENT ONLY. What it does NOT do: it does not scan, index, move or open ANY of the
owner's video files, and it does not download anything. The single video it reads is the
lane's OWN synthetic clip (`_import-bench/synth-180s-1080p30.mp4`, 295 501 289 B, 180 s,
1080p30, x264 ultrafast crf26 + aac 128k), left on disk by `_import-bench.py`.
Every ffmpeg child is spawned with CREATE_NO_WINDOW and this script must be launched with
pythonw.exe. No audio device is opened (`-f null NUL` / `-f wav NUL`).

Read amplification comes from GetProcessIoCounters on the RETAINED process handle: the
counter is read after exit, so no poll can miss it.

Output: _main/_import-bench/media08.json + media08.log
"""
import ctypes
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_import-bench")
VID = os.path.join(OUT, "synth-180s-1080p30.mp4")
FF = shutil.which("ffmpeg")
FP = shutil.which("ffprobe")
NO_WINDOW = 0x08000000
NUL = "NUL"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
R = {}
LOG = open(os.path.join(OUT, "media08.log"), "w", encoding="utf-8", buffering=1)


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n")


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO_COUNTERS)]


def stat(xs):
    xs = sorted(xs)
    if not xs:
        return None
    return {"n": len(xs), "min": round(xs[0], 4), "median": round(statistics.median(xs), 4),
            "max": round(xs[-1], 4)}


def run_counted(args, label, size, reps=1):
    """Spawn, wait, then read GetProcessIoCounters -- read_bytes / size = amplification."""
    recs = []
    for _ in range(reps):
        t0 = time.perf_counter()
        p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=NO_WINDOW)
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, p.pid)
        p.wait()
        dt = time.perf_counter() - t0
        io = IO_COUNTERS()
        ok = k32.GetProcessIoCounters(wintypes.HANDLE(h), ctypes.byref(io)) if h else 0
        if h:
            k32.CloseHandle(wintypes.HANDLE(h))
        recs.append({"seconds": round(dt, 4), "rc": p.returncode, "ok": bool(ok),
                     "read_bytes": io.ReadTransferCount, "read_ops": io.ReadOperationCount,
                     "write_bytes": io.WriteTransferCount})
    secs = [r["seconds"] for r in recs]
    reads = [r["read_bytes"] for r in recs]
    out = {"label": label, "runs": recs, "seconds": stat(secs)}
    out["median_seconds"] = round(statistics.median(secs), 4)
    out["read_bytes_min"] = min(reads)
    out["read_bytes_median"] = int(statistics.median(reads))
    out["read_amplification_median"] = round(statistics.median(reads) / size, 4)
    out["read_RTF"] = round(180.0 / out["median_seconds"], 2)  # 180 s of video / seconds
    log("[%s] %.3fs median  read=%.1f MB (x%.3f of file)  RTF=%.1fx"
        % (label, out["median_seconds"], out["read_bytes_median"] / 2**20,
           out["read_amplification_median"], out["read_RTF"]))
    return out


def stage_metadata(size):
    ts = []
    for _ in range(7):
        t0 = time.perf_counter()
        subprocess.run([FP, "-v", "error", "-print_format", "json", "-show_entries",
                        "format=duration,size,bit_rate:stream=codec_name,width,height,r_frame_rate",
                        VID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=NO_WINDOW)
        ts.append(time.perf_counter() - t0)
    R["D0_ffprobe_header"] = {"seconds": stat(ts),
                              "per_1000_files_minutes": round(statistics.median(ts) * 1000 / 60, 2)}
    log("[D0 ffprobe header] %.4fs median -> 1000 files = %.2f min"
        % (statistics.median(ts), R["D0_ffprobe_header"]["per_1000_files_minutes"]))


def stage_media(size):
    base = [FF, "-nostdin", "-hide_banner", "-loglevel", "error"]
    R["D1_full_decode"] = run_counted(base + ["-i", VID, "-f", "null", NUL], "full decode v+a", size, 2)
    R["D1_audio_16k"] = run_counted(base + ["-i", VID, "-vn", "-ac", "1", "-ar", "16000",
                                            "-c:a", "pcm_s16le", "-f", "wav", NUL], "audio->16k wav", size, 3)
    R["D1_audio_chunk_30s"] = run_counted(base + ["-ss", "100", "-t", "30", "-i", VID, "-vn",
                                                  "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                                                  "-f", "wav", NUL], "audio chunk 30s", size, 3)
    # thumbnail: input-side seek (fast, keyframe) vs output-side seek (the trap)
    th = os.path.join(OUT, "thumb08.jpg")
    good, sizes = [], []
    for t in [5, 55, 175]:
        r = run_counted(base + ["-ss", str(t), "-i", VID, "-frames:v", "1", "-vf", "scale=320:-2",
                                "-q:v", "4", "-y", th], "thumb -ss %d before -i" % t, size, 1)
        r["jpeg_bytes"] = os.path.getsize(th)
        good.append(r)
        sizes.append(r["jpeg_bytes"])
    R["D1_thumb_seek_before"] = good
    R["D1_thumb_jpeg_bytes"] = {"median": int(statistics.median(sizes)), "all": sizes}
    R["D1_thumb_seek_after"] = run_counted(base + ["-i", VID, "-ss", "170", "-frames:v", "1",
                                                   "-vf", "scale=320:-2", "-q:v", "4", "-y", th],
                                           "thumb -ss 170 AFTER -i (trap)", size, 1)
    # 1 fps gallery: what writing frames to disk costs, and how many bytes
    frames = os.path.join(OUT, "fps08_%04d.jpg")
    for f in os.listdir(OUT):
        if f.startswith("fps08_"):
            os.remove(os.path.join(OUT, f))
    t0 = time.perf_counter()
    subprocess.run(base + ["-i", VID, "-vf", "fps=1,scale=320:-2", "-q:v", "4", "-y", frames],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    dt = time.perf_counter() - t0
    made = [f for f in os.listdir(OUT) if f.startswith("fps08_")]
    tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in made)
    R["D1_gallery_1fps"] = {"seconds": round(dt, 4), "frames": len(made), "total_bytes": tot,
                            "bytes_per_frame": int(tot / max(1, len(made))),
                            "frames_per_second_of_wall": round(len(made) / dt, 1),
                            "per_1000_videos_10min_MB": round(tot / 180 * 600 * 1000 / 2**20, 1)}
    log("[1fps gallery] %d frames in %.2fs, %d B total -> %.1f MB per 1000 x 10 min video"
        % (len(made), dt, tot, R["D1_gallery_1fps"]["per_1000_videos_10min_MB"]))
    for f in made:
        os.remove(os.path.join(OUT, f))


def stage_hash(size):
    out = {}
    t0 = time.perf_counter()
    h = hashlib.sha256()
    with open(VID, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    dt = time.perf_counter() - t0
    out["sha256_full"] = {"seconds": round(dt, 4), "MB_per_s": round(size / 2**20 / dt, 1),
                          "per_300GB_minutes": round(300 * 1024 / (size / 2**20 / dt) / 60, 1),
                          "hex_head": h.hexdigest()[:16]}
    t0 = time.perf_counter()
    h = hashlib.blake2b()
    with open(VID, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    dt = time.perf_counter() - t0
    out["blake2b_full"] = {"seconds": round(dt, 4), "MB_per_s": round(size / 2**20 / dt, 1),
                           "per_300GB_minutes": round(300 * 1024 / (size / 2**20 / dt) / 60, 1),
                           "hex_head": h.hexdigest()[:16]}
    # cheap identity: size + first/last MiB (reads 2 MiB, not the file)
    t0 = time.perf_counter()
    h = hashlib.blake2b()
    with open(VID, "rb") as f:
        h.update(f.read(1 << 20))
        f.seek(-(1 << 20), os.SEEK_END)
        h.update(f.read(1 << 20))
    dt = time.perf_counter() - t0
    out["headtail_1MiB"] = {"seconds": round(dt, 4), "bytes_read": 2 << 20,
                            "per_1000_files_seconds": round(dt * 1000, 2)}
    R["identity_hash"] = out
    for k, v in out.items():
        log("[hash %s] %s" % (k, json.dumps(v)))


def stage_file_id():
    """NTFS identity with NO READ: volume serial + 128-bit file id."""
    class FILE_ID_INFO(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong),
                    ("FileId", ctypes.c_ubyte * 16)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [("dwFileAttributes", wintypes.DWORD),
                    ("ftCreationTime", wintypes.FILETIME),
                    ("ftLastAccessTime", wintypes.FILETIME),
                    ("ftLastWriteTime", wintypes.FILETIME),
                    ("dwVolumeSerialNumber", wintypes.DWORD),
                    ("nFileSizeHigh", wintypes.DWORD),
                    ("nFileSizeLow", wintypes.DWORD),
                    ("nNumberOfLinks", wintypes.DWORD),
                    ("nFileIndexHigh", wintypes.DWORD),
                    ("nFileIndexLow", wintypes.DWORD)]

    GENERIC_READ = 0x80000000
    SHARE = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    INVALID = ctypes.c_void_p(-1).value
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    h = k32.CreateFileW(VID, GENERIC_READ, SHARE, None, OPEN_EXISTING, 0, None)
    if h == INVALID:
        R["identity_file_id"] = {"error": "CreateFileW %d" % ctypes.get_last_error()}
        return
    t0 = time.perf_counter()
    fi = FILE_ID_INFO()
    ok = k32.GetFileInformationByHandleEx(wintypes.HANDLE(h), 18, ctypes.byref(fi), ctypes.sizeof(fi))
    dt = time.perf_counter() - t0
    bh = BY_HANDLE_FILE_INFORMATION()
    ok2 = k32.GetFileInformationByHandle(wintypes.HANDLE(h), ctypes.byref(bh))
    k32.CloseHandle(wintypes.HANDLE(h))
    R["identity_file_id"] = {
        "FileIdInfo_ok": bool(ok), "seconds": round(dt, 6),
        "volume_serial": fi.VolumeSerialNumber,
        "file_id_128_hex": bytes(fi.FileId).hex(),
        "by_handle_ok": bool(ok2),
        "vol_serial_32": bh.dwVolumeSerialNumber,
        "file_index_64": (bh.nFileIndexHigh << 32) | bh.nFileIndexLow,
        "size_from_handle": (bh.nFileSizeHigh << 32) | bh.nFileSizeLow,
        "links": bh.nNumberOfLinks,
    }
    log("[identity] " + json.dumps(R["identity_file_id"]))


def main():
    if not (FF and FP and os.path.exists(VID)):
        log("FATAL: ffmpeg/ffprobe/synth missing")
        return 1
    size = os.path.getsize(VID)
    R["video"] = {"path": VID, "bytes": size, "seconds": 180, "mbps": round(size * 8 / 180 / 1e6, 2)}
    R["host_note"] = "other lanes were running 13 python/pythonw processes during this pass"
    stage_metadata(size)
    stage_media(size)
    stage_hash(size)
    stage_file_id()
    with open(os.path.join(OUT, "media08.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2)
    log("MEDIA08-DONE")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        log("EXCEPTION\n" + traceback.format_exc())
        with open(os.path.join(OUT, "media08.json"), "w", encoding="utf-8") as f:
            json.dump({"error": "see log", "partial": R}, f, indent=2)
        raise
