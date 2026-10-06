# Attribute the ~2 GB: WEIGHTS or PROVIDER? Same int4 encoder, one session per provider.
# RSS via psutil when present, else GetProcessMemoryInfo with the HANDLE restype FIXED
# (without restype the 64-bit pseudo-handle truncates and every reading is 0.0 -- measured).
import os, gc, time, io, sys

OUT = r"H:\sotto\_main\provider-cost-probe.log"
log = io.open(OUT, "w", encoding="utf-8")
def p(*a):
    log.write(" ".join(str(x) for x in a)+"\n"); log.flush()

def read_rss():
    try:
        import psutil
        pr = psutil.Process()
        return pr.memory_info().rss/1048576.0, 0.0
    except Exception:
        import ctypes, ctypes.wintypes as w
        k32 = ctypes.windll.kernel32; k32.GetCurrentProcess.restype = w.HANDLE
        class PMC(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        h = k32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
        if not ok: raise RuntimeError("GetProcessMemoryInfo failed")
        return pmc.WorkingSetSize/1048576.0, pmc.PeakWorkingSetSize/1048576.0

try:
    import psutil; src = "psutil"
except Exception:
    src = "GetProcessMemoryInfo(restype-fixed)"
p("instrument:", src)

import onnxruntime as ort
p("onnxruntime", ort.__version__, "| providers:", ort.get_available_providers())
enc = r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int4\encoder.onnx"
p("encoder on disk MB:", round(os.path.getsize(enc)/1048576, 3))

base, _ = read_rss()
p(f"RSS at import (before ANY session): {base:.1f} MB")
for want in (["CPUExecutionProvider"], ["CUDAExecutionProvider", "CPUExecutionProvider"]):
    gc.collect(); time.sleep(1.5)
    before, _ = read_rss()
    t0 = time.time()
    try:
        s = ort.InferenceSession(enc, ort.SessionOptions(), providers=want)
        dt = time.time()-t0
        gc.collect(); time.sleep(0.5)
        now, peak = read_rss()
        p(f"provider={want[0]:<22} load_s={dt:6.2f}  rss={now:7.1f}  delta={now-before:+8.1f}  "
          f"peak={peak:7.1f}  actual={s.get_providers()}")
        del s
    except Exception as e:
        p(f"provider={want[0]:<22} FAILED: {type(e).__name__}: {str(e)[:160]}")
    gc.collect(); time.sleep(2.0)
p("DONE")
log.close()
