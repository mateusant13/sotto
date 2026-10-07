# -*- coding: utf-8 -*-
"""_import-hdd2.py -- lane 08: repeat the HDD device numbers, because the first pass
overlapped a directory walk this lane had started on the same volume (contention).
Reads only a non-personal HuggingFace blob; no owner video is touched. pythonw.exe.
"""
import ctypes
import json
import os
import random
import statistics
import time
from ctypes import wintypes

OUT = r"H:\aireplay\_main\_import-bench"
HDD = r"I:\codeintel\hf-cache\hub\models--Qwen--Qwen3-ASR-1.7B\blobs\a4cd1f1a04d90b757dc7f7dd26254e69a013b19e80efe590a83c6a3bde8608d6"

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
NOBUF = 0x20000000
SEQ = 0x08000000
RAND = 0x10000000
INVALID = ctypes.c_void_p(-1).value
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                 ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
k32.VirtualAlloc.restype = ctypes.c_void_p


def open_raw(flags):
    h = k32.CreateFileW(HDD, GENERIC_READ, 1, None, OPEN_EXISTING, flags, None)
    if h == INVALID:
        raise OSError(ctypes.get_last_error())
    return h


def read_at(h, ptr, off, size):
    k32.SetFilePointerEx(h, off, None, 0)
    n = wintypes.DWORD(0)
    if not k32.ReadFile(h, ctypes.c_void_p(ptr), size, ctypes.byref(n), None):
        raise OSError(ctypes.get_last_error())
    return n.value


R = {"file": HDD, "bytes": os.path.getsize(HDD), "seq": [], "rand": []}

for chunk_mb, offset_mb, total_mb in [(8, 0, 512), (8, 1024, 512), (8, 2048, 512), (1, 3072, 256), (32, 512, 1024)]:
    h = open_raw(NOBUF | SEQ)
    size = chunk_mb << 20
    p = k32.VirtualAlloc(None, size, 0x3000, 4)
    off = offset_mb << 20
    total = total_mb << 20
    done = 0
    t0 = time.perf_counter()
    while done < total:
        done += read_at(h, p, off + done, size)
    dt = time.perf_counter() - t0
    k32.CloseHandle(h)
    mb = done / 1048576.0
    rec = {"chunk_mb": chunk_mb, "offset_mb": offset_mb, "mb": round(mb, 1),
           "seconds": round(dt, 3), "MB_per_s": round(mb / dt, 1)}
    print(json.dumps(rec))
    R["seq"].append(rec)

for label, span_mb, n in [("within 256 MiB", 256, 100), ("within 2 GiB", 2048, 100)]:
    rnd = random.Random(3)
    h = open_raw(NOBUF | RAND)
    p = k32.VirtualAlloc(None, 4096, 0x3000, 4)
    lats = []
    t0 = time.perf_counter()
    for _ in range(n):
        o = rnd.randrange(0, span_mb << 20, 4096)
        a = time.perf_counter()
        read_at(h, p, o, 4096)
        lats.append((time.perf_counter() - a) * 1000.0)
    dt = time.perf_counter() - t0
    k32.CloseHandle(h)
    rec = {"label": label, "reads": n, "seconds": round(dt, 3),
           "MB_per_s": round(n * 4096 / 1048576.0 / dt, 3),
           "lat_median_ms": round(statistics.median(lats), 2),
           "lat_p95_ms": round(sorted(lats)[int(0.95 * n) - 1], 2),
           "lat_min_ms": round(min(lats), 2)}
    print(json.dumps(rec))
    R["rand"].append(rec)

with open(os.path.join(OUT, "hdd2.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, indent=2)
print("HDD2-DONE")
