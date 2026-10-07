# -*- coding: utf-8 -*-
"""_import-io-probe.py -- lane 08: HOW MANY BYTES does each job actually read?

Uses GetProcessIoCounters on the retained process handle, so the counter is read AFTER
exit and cannot be missed by a poll race. The file is the lane's own synthetic video
(H:\\aireplay), so no owner video is opened. Run with pythonw.exe.
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_import-bench")
VID = os.path.join(OUT, "synth-180s-1080p30.mp4")
FF = shutil.which("ffmpeg")
NO_WINDOW = 0x08000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


def run_counted(args, label):
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
    rec = {"label": label, "seconds": round(dt, 3), "ok": bool(ok),
           "read_bytes": io.ReadTransferCount, "read_ops": io.ReadOperationCount,
           "write_bytes": io.WriteTransferCount}
    print(json.dumps(rec))
    return rec


def main():
    size = os.path.getsize(VID)
    res = {"file": VID, "file_bytes": size, "runs": []}
    cases = [
        (["-i", VID, "-f", "null", "NUL"], "full decode (video+audio)"),
        (["-i", VID, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", "NUL"], "audio only -> 16k wav"),
        (["-ss", "100", "-t", "30", "-i", VID, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", "NUL"],
         "audio chunk 100s+30s"),
        (["-ss", "170", "-i", VID, "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", "-y",
          os.path.join(OUT, "thumb_io.jpg")], "one thumbnail at t=170 (seek before -i)"),
    ]
    for extra, label in cases:
        res["runs"].append(run_counted([FF, "-nostdin", "-hide_banner", "-loglevel", "error"] + extra, label))
    res["read_ratio"] = {r["label"]: round(r["read_bytes"] / size, 4) for r in res["runs"] if r["ok"]}
    with open(os.path.join(OUT, "io.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res["read_ratio"], indent=2))


if __name__ == "__main__":
    main()
