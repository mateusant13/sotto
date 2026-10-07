#!/usr/bin/env pythonw
"""asr02-census.py -- an independent 100 ms window census over a DRIVER-spawned ASR child.

The oracle censuses its own children; this censuses the same spawn discipline from the other
launcher (`asr02-run.py` style: pythonw parent, `python -m asr.transcribe` child with
CREATE_NO_WINDOW, stdout to a FILE). The house 60 s census cannot see a short window, so the
cadence here is 100 ms and the tracked set is seeded from the child's OWN pid.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"H:\aireplay")
SRC = ROOT / "src"
PY = r"C:\Program Files\Python311\python.exe"
CREATE_NO_WINDOW = 0x08000000
LOG = ROOT / "_main" / "logs" / "asr02-census.log"
OUT = ROOT / "_main" / "logs" / "asr02-census.json"
WAV = Path(r"H:\sotto\_main\_redux-long\plain-3600s.wav")


class Census(threading.Thread):
    def __init__(self, every: float = 0.1):
        super().__init__(daemon=True)
        self.every, self.pids, self.samples, self.hits = every, set(), 0, 0
        self.distinct: set[int] = set()
        self.rows: list[str] = []
        self._stop = threading.Event()

    def run(self) -> None:
        u = ctypes.windll.user32
        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        while not self._stop.is_set():
            self.samples += 1
            found = []

            def visit(hwnd, _l):
                pid = ctypes.c_ulong()
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in self.pids and u.IsWindowVisible(hwnd):
                    n = u.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    found.append((pid.value, hwnd, buf.value))
                return True

            u.EnumWindows(cb(visit), None)
            for pid, hwnd, title in found:
                self.hits += 1
                self.distinct.add(pid)
                self.rows.append(f"ALERTA-JANELA pid={pid} hwnd={hwnd} title={title!r}")
            self._stop.wait(self.every)

    def stop(self) -> None:
        self._stop.set()


def main() -> int:
    census = Census(0.1)
    census.start()
    log = ROOT / "_main" / "logs" / "asr02-census-child.out"
    t0 = time.perf_counter()
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [PY, "-m", "asr.transcribe", "--wav", str(WAV), "--offset-s", "900", "--max-s", "40",
             "--json", "--label", "census-child"],
            stdout=fh, stderr=subprocess.STDOUT, cwd=str(SRC), creationflags=CREATE_NO_WINDOW)
        census.pids.add(proc.pid)
        rc = proc.wait(timeout=600)
    wall = time.perf_counter() - t0
    census.stop()
    time.sleep(0.3)
    summary = {"rc": rc, "wall_s": round(wall, 1), "child_pid": proc.pid,
               "census": {"samples": census.samples, "every_ms": 100, "visible_hits": census.hits,
                          "distinct_pids": len(census.distinct), "rows": census.rows}}
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.write_text(
        f"census over driver-spawned child pid={proc.pid} rc={rc} wall={wall:.1f}s\n"
        f"samples={census.samples} every_ms=100 visible_hits={census.hits} "
        f"distinct_pids={len(census.distinct)}\n" + "\n".join(census.rows) + "\n"
        + f"CENSUS-VERDICT: {'CLEAN' if census.hits == 0 else 'ALERTA'}\n", encoding="utf-8")
    return 0 if census.hits == 0 and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
