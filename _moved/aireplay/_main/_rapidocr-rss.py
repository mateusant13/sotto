import os, sys, time, json
def rss_mb():
    try:
        import ctypes, ctypes.wintypes
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        p = PMC(); p.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(p), p.cb)
        return round(p.WorkingSetSize/1048576, 1), round(p.PeakWorkingSetSize/1048576, 1)
    except Exception as e:
        return None, str(e)
out = {"rss_after_python_mb": rss_mb()}
import numpy as np
from PIL import Image
out["rss_after_numpy_pil_mb"] = rss_mb()
from rapidocr import RapidOCR
out["rss_after_import_mb"] = rss_mb()
e = RapidOCR()
out["rss_after_engine_init_mb"] = rss_mb()
arr = np.array(Image.open(r"F:\aireplay\_main\ocr-frames\00-clean_hud.png").convert("RGB")) if False else np.array(Image.open(r"H:\aireplay\_main\ocr-frames\00-clean_hud.png").convert("RGB"))
t=time.perf_counter(); r=e(arr); out["first_infer_s"]=round(time.perf_counter()-t,3)
out["rss_after_infer_mb"] = rss_mb()
print(json.dumps(out, indent=1))
