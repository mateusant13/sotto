#!/usr/bin/env python
"""PERF LOG: what does Sotto COST the owner's machine, and when does it hiccup?

THE OWNER, verbatim (2026-10-22):

    "faz uma ferramenta de loggar a performance que o sotto causa. depois, abre o
     sotto. veja se tu logga coisas como meu sistema travando ou dando stutter.
     usar isso pra melhorar o sotto. vamos usar tools corretas e robustas. pode
     usar algum pacote ja existente e etc."

WHY THIS FILE EXISTS. Until now the numbers about Sotto's cost were SINGLE
MEASUREMENTS taken by hand, in prose, in a receipt: "53-127 ms of stutter per
process start", "63.6 s later the box was saturated (VRAM 100 %, 38
msedgewebview2.exe)", "1 245 MB resident". Each one is a fact, and none of them
is a TIME SERIES: they cannot say WHICH moment the owner felt, WHAT was running
then, or whether the next launch was better or worse. This is the instrument that
answers those three.

THE FOUR MEASUREMENTS, and why each one is the right tool:

  1. TIMER SLIP (the stutter itself). A thread asks to sleep 25 ms and measures
     how late it wakes. On a quiet box the slip is 0-3 ms; when the machine
     stutters it jumps to tens or hundreds of milliseconds. This is the closest
     in-process proxy for "the owner's foreground froze", it costs nothing, and
     it is the SAME quantity the old hand measurements were reporting.
  2. CPU broken down by kind, from `psutil.cpu_times_percent` -- including
     `interrupt` and `dpc`. DPC (Deferred Procedure Call) time is the classic
     Windows stutter source: it runs at a priority above every thread, so a DPC
     storm is felt as a freeze and does not appear in any process's CPU.
  3. DISK, from `psutil.disk_io_counters`: MB/s and **% of the interval the disk
     was busy**. This machine's disks are 0.4-20 % free, and the AGENTS'
     measurement is that a process start is a disk read.
  4. THE PROCESS FAMILY, from `psutil`: every descendant of the Sotto shell
     (`sotto_webview.py`), attributed BY THE PROCESS TREE, not by name. An
     `msedgewebview2.exe` that belongs to ANOTHER app is counted separately and
     is never blamed on Sotto. Each member's CPU% and RSS is sampled, and each
     NEW pid is logged with the moment it appeared -- so the 38 WebView2
     processes are not a claim in a comment, they are a timestamped list.

WHY psutil AND NOT `Get-Process`/`Get-Counter` SHELLED OUT. Measured 2026-10-22:
starting ANY process on this box costs 53-127 ms. A logger that spawns a
PowerShell every second to ask for a counter IS the stutter it is trying to
measure. psutil is already installed (5.9.8), it is a single process, and its
calls are C syscalls. The heavier, ETW-based tools (`wpr.exe`, present in
`C:\\WINDOWS\\system32`) are the right tool for a DEEP hunt -- a full trace with
stack walking -- and the wrong tool for a 2-minute attribution run, because the
trace itself writes gigabytes to disks that are 0.4 % free.

THE INSTRUMENT'S OWN COST IS DECLARED, NOT HIDDEN: the report prints the p50 of
the slip (robust to the single sample the sampler can disturb), and the sampler
runs at 1 Hz against a 40 Hz probe.

    python _main\\sotto-perf-log.py --launch --seconds 150
    python _main\\sotto-perf-log.py --report _main\\perf\\sotto-perf-<ts>.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime

try:
    import psutil
except ImportError:  # pragma: no cover - the whole tool is psutil
    print("sotto-perf-log: psutil is not installed. `pip install psutil`.")
    sys.exit(3)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_CMD = os.path.join(ROOT, "app", "webview", "run.cmd")
CREATE_NO_WINDOW = 0x08000000

#: The shell's own source file name. The family is built from the process whose
#: command line carries this, and from its descendants.
SHELL_MARKER = "sotto_webview.py"
WORKER_MARKER = "sotto_worker.py"


# ---------------------------------------------------------------------------
# the sink: one JSON object per line, flushed as we go so a killed run still has
# everything up to the kill.
# ---------------------------------------------------------------------------

class Sink:
    """A line-per-record sink, buffered by 64 KB.

    NOT line-buffered: MEASURED 2026-10-22, a flush per record cost the probe
    3.5 ms per 25 ms sample (525 ms of bookkeeping in a 6 s run), which is 14 %
    duty on the very thread whose wake-up lateness is the measurement. 64 KB
    still reaches the disk about once a second at this rate, and the worst a
    hard kill can lose is that buffer.
    """

    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8", buffering=65536)
        self.path = path
        self.written = 0

    def write(self, **rec):
        rec.setdefault("t", round(time.time(), 3))
        self.fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.written += 1

    def close(self):
        try:
            self.fh.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 1. THE STUTTER PROBE
# ---------------------------------------------------------------------------

class SlipProbe(threading.Thread):
    """Sleep 25 ms, forty times a second, and report how late we woke up.

    KEPT FOR THE IN-PROCESS CASE (`--solo-thread`), because the two are not the
    same measurement and the difference is the point: see `_probe_process`.
    """

    PERIOD_S = 0.025

    def __init__(self, sink, stop):
        super().__init__(name="slip-probe", daemon=True)
        #: set by `run()`; a measured run sets this so the launch is stamped on
        #: the same clock as the slips.
        self.sink = sink
        self.stop = stop
        self.self_us = 0.0  # how long the probe's own bookkeeping took

    def run(self):
        mono = time.perf_counter
        while not self.stop.is_set():
            t0 = mono()
            self.stop.wait(self.PERIOD_S)
            t1 = mono()
            now = time.time()
            self.sink.write(k="stall", at=round(now, 3),
                            slip_ms=round((t1 - t0 - self.PERIOD_S) * 1000.0, 2))
            self.self_us += (mono() - t1) * 1e6


#: HOW LATE A 25 ms SLEEP WAKES UP, MEASURED FROM A PROCESS OF ITS OWN.
#:
#: WHY ITS OWN PROCESS AND NOT A THREAD. MEASURED 2026-10-22, first version of
#: this tool: the probe shared a process with the sampler, and the sampler walks
#: the process table (722 live processes, asking each for its command line) every
#: fifth second. The report showed slips of 1134 ms, 912 ms and 25 slips over
#: 250 ms -- WHILE the box had 40-53 % of its CPU idle, 17 GB of RAM free, `dpc`
#: under 1 % and the disk at 0 % I/O. An idle machine does not delay a timer by a
#: second; a thread waiting to re-acquire the GIL that another thread is holding
#: for a second does exactly that. So the number was the INSTRUMENT, not the
#: owner's machine. The probe now runs in its own process, where nothing else can
#: hold anything, and the sampler's cost is confined to the sampler.
PROBE_CHILD = r'''
import json, os, sys, time
stall_path, stop_path, period = sys.argv[1], sys.argv[2], float(sys.argv[3])
mono = time.perf_counter
own_us = 0.0
n = 0
with open(stall_path, "w", encoding="utf-8", buffering=65536) as fh:
    while not os.path.exists(stop_path):
        t0 = mono()
        time.sleep(period)
        t1 = mono()
        fh.write(json.dumps({"k": "stall", "at": round(time.time(), 3),
                             "slip_ms": round((t1 - t0 - period) * 1000.0, 2)},
                            separators=(",", ":")) + "\n")
        own_us += (mono() - t1) * 1e6
        n += 1
    fh.flush()
print("PROBE-DONE samples=%d own_ms=%.1f" % (n, own_us / 1000.0))
'''


# ---------------------------------------------------------------------------
# 4. THE PROCESS FAMILY
# ---------------------------------------------------------------------------

def find_shell_pids():
    """Every process whose command line carries the shell's source name."""
    out = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if any(SHELL_MARKER in str(part) for part in cmd):
                out.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return out


def classify(proc):
    """-> ('shell'|'worker'|'webview'|'other') from the process's own command line."""
    try:
        cmd = " ".join(proc.cmdline() or [])
        name = (proc.name() or "").lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "gone"
    if WORKER_MARKER in cmd:
        return "worker"
    if SHELL_MARKER in cmd:
        return "shell"
    if name.startswith("msedgewebview2"):
        return "webview"
    if name in ("conhost.exe",):
        return "conhost"
    return "other"


def family(shell_pids):
    """The shell's descendants, by the PROCESS TREE. -> {pid: role}.

    THE TREE MATTERS. `msedgewebview2.exe` is also used by other applications on
    this box, and naming a process by its file name is how a measurement blames
    the wrong program. Only descendants of a live shell are attributed to Sotto.
    """
    members = {}
    for pid in shell_pids:
        try:
            root = psutil.Process(pid)
        except psutil.NoSuchProcess:
            continue
        members[pid] = classify(root)
        try:
            for child in root.children(recursive=True):
                members[child.pid] = classify(child)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return members


def count_foreign_webviews(shell_pids):
    """How many `msedgewebview2.exe` on this box are NOT Sotto's.

    Counted so the report can say what it did NOT blame on Sotto: this box runs
    other embedded-WebView2 applications, and a count of "38 webview processes"
    that silently includes them is how a measurement accuses the wrong program.
    """
    ours = set()
    for pid in shell_pids:
        try:
            ours.add(pid)
            ours.update(c.pid for c in psutil.Process(pid).children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    foreign = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (proc.info.get("name") or "").lower().startswith("msedgewebview2") \
                    and proc.info["pid"] not in ours:
                foreign += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return foreign


# ---------------------------------------------------------------------------
# GPU MEMORY -- the measurement that was MISSING, and the whole reason for it
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS. The first version of this tool measured CPU, disk, RAM and
# timer slip -- and it reported that the owner's machine was not stuttering
# while Sotto ran. The owner answered, verbatim, 2026-10-22 03:43:
#
#     "e o stutter acontece sim. foi so eu botar audio no pc."
#
# He was right and the instrument was measuring the wrong population: with the
# capture device flat, the worker parks and does nothing, so the run that
# "proved" Sotto was innocent was taken in the one state where Sotto is idle.
# The moment audio arrives the worker runs CUDA inference -- and VRAM is what
# decides whether that is felt. Measured then, with the worker started on a FILE
# (`--audio`, which renders nothing to any speaker):
#
#     adapter total  13 304 MiB -> 14 911 MiB peak -> 13 653 MiB after exit
#     the worker      0 MiB -> 1 478 MiB peak -> 0 MiB after exit
#
# and the 13.3 GB that was ALREADY used was not Sotto's at all: 7 474 MiB to a
# `services.archive_transcribe` process and 2 926 MiB to a `codeintel.daemon`
# process, neither of which exists under `H:\sotto`. A GPU at 13/16 GB leaves
# almost nothing for the compositor, and THAT is what a stutter feels like.
#
# HOW IT IS READ: performance counters by PDH (`win32pdh`, already installed
# with pywin32), NOT by shelling out to `nvidia-smi`. Starting a process on this
# box costs 53-127 ms, and an instrument that spawns one every sample is the
# stutter it is trying to measure. `\GPU Process Memory(*)\Dedicated Usage` is
# per-pid dedicated VRAM -- the same number Task Manager shows.
GPU_COUNTER = r"\GPU Process Memory(*)\Dedicated Usage"
GPU_ADAPTER_COUNTER = r"\GPU Adapter Memory(*)\Dedicated Usage"

#: PDH_FMT_LARGE -- 64-bit integers, i.e. bytes for a memory counter.
_PDH_FMT_LARGE = 0x00000400
_PDH_MORE_DATA = 0x800007D2


class GpuMemory:
    """Dedicated VRAM, read straight from PDH through `ctypes`.

    WHY NOT `win32pdh`: MEASURED 2026-10-22 -- the pywin32 build on this box
    exposes neither `GetFormattedCounterArray(counter, fmt)` as a list of
    (name, value) pairs NOR `GetFormattedCounterValue(counter, fmt, instance)`;
    the first returns a bare list of instance NAMES and the second takes two
    arguments. Rather than guess at a wrapper, this talks to `pdh.dll` itself,
    which is stdlib territory (`ctypes`) and has no subprocess at all.

    TWO COUNTERS, and they answer different questions:
      * `GPU Adapter Memory(*)\\Dedicated Usage` -- what the CARD is using. This
        is the number `nvidia-smi --query-gpu=memory.used` reports, and it is the
        one that decides whether the card is full. Verified equal to within 1 %
        (measured 3 051 MiB here vs 3 032 MiB from nvidia-smi).
      * `GPU Process Memory(*)\\Dedicated Usage` -- the same memory attributed to
        a PID, which is what says WHOSE it is.
    """

    def __init__(self):
        self.ok = False
        self.why = ""
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:  # pragma: no cover
            self.why = "ctypes unavailable"
            return
        self.ctypes = ctypes
        pdh = ctypes.WinDLL("pdh")

        class _U(ctypes.Union):
            _fields_ = [("longValue", ctypes.c_long),
                        ("doubleValue", ctypes.c_double),
                        ("largeValue", ctypes.c_longlong),
                        ("AnsiStringValue", ctypes.c_char_p),
                        ("WideStringValue", ctypes.c_wchar_p)]

        class _V(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD), ("u", _U)]

        class _Item(ctypes.Structure):
            _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _V)]

        self._Item = _Item
        pdh.PdhOpenQueryW.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t,
                                      ctypes.POINTER(wintypes.HANDLE)]
        pdh.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, ctypes.c_wchar_p,
                                              ctypes.c_size_t,
                                              ctypes.POINTER(wintypes.HANDLE)]
        pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
        pdh.PdhGetFormattedCounterArrayW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        pdh.PdhGetFormattedCounterArrayW.restype = wintypes.DWORD
        pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]
        self.pdh = pdh
        self.wintypes = wintypes

        try:
            self._q = wintypes.HANDLE()
            self._q_proc = wintypes.HANDLE()
            self._q_adapter = wintypes.HANDLE()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._q)) != 0:
                raise OSError("PdhOpenQueryW failed")
            self._c_proc = wintypes.HANDLE()
            self._c_adapter = wintypes.HANDLE()
            rc1 = pdh.PdhAddEnglishCounterW(self._q, GPU_COUNTER, 0,
                                            ctypes.byref(self._c_proc))
            rc2 = pdh.PdhAddEnglishCounterW(self._q, GPU_ADAPTER_COUNTER, 0,
                                            ctypes.byref(self._c_adapter))
            if rc1 or rc2:
                raise OSError(f"AddCounter rc={rc1},{rc2}")
            # a rate/instantaneous counter needs one priming collect
            pdh.PdhCollectQueryData(self._q)
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            self.why = repr(exc)

    def _array(self, counter):
        """-> [(instance_name, bytes)] for one counter, or [] on any failure."""
        ctypes, wintypes = self.ctypes, self.wintypes
        size = wintypes.DWORD(0)
        count = wintypes.DWORD(0)
        rc = self.pdh.PdhGetFormattedCounterArrayW(
            counter, _PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), None)
        if rc not in (0, _PDH_MORE_DATA) or not size.value:
            return []
        buf = ctypes.create_string_buffer(size.value)
        rc = self.pdh.PdhGetFormattedCounterArrayW(
            counter, _PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), buf)
        if rc != 0:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(self._Item))
        return [(items[i].szName, items[i].FmtValue.u.largeValue)
                for i in range(count.value)]

    def read(self):
        """-> {'adapter_mb': float, 'by_pid': {pid: MiB}} or `None`."""
        if not self.ok:
            return None
        try:
            self.pdh.PdhCollectQueryData(self._q)
        except Exception:  # noqa: BLE001
            return None
        mb = 1024.0 * 1024.0
        adapter = max((v for _, v in self._array(self._c_adapter)), default=0)
        by_pid = {}
        for name, value in self._array(self._c_proc):
            if not name.startswith("pid_"):
                continue
            try:
                pid = int(name.split("_")[1])
            except (IndexError, ValueError):
                continue
            # a pid can have one instance per LUID (adapter); they ADD UP
            by_pid[pid] = by_pid.get(pid, 0.0) + value / mb
        return {"adapter_mb": adapter / mb, "by_pid": by_pid}

    def close(self):
        if self.ok:
            try:
                self.pdh.PdhCloseQuery(self._q)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# 2 + 3. THE SYSTEM SAMPLE
# ---------------------------------------------------------------------------

class Sampler(threading.Thread):
    """1 Hz: CPU by kind, disk, memory, and the Sotto family's own cost.

    TWO CADENCES, and the reason is measured. The cheap part (cpu_times_percent,
    disk_io_counters, this process's own family tree) runs every second. The
    EXPENSIVE part -- asking every process on the box for its command line, to
    find the shell, and counting the other applications' WebView2s -- runs every
    `SLOW_EVERY_S`, because MEASURED 2026-10-22 with 722 live processes it turned
    a 1 Hz sampler into a 2 Hz one. A logger that cannot keep its own cadence is
    reporting its own hiccups as the owner's.
    """

    SLOW_EVERY_S = 5.0
    #: VRAM is read on the slow cadence too: the counter walks every GPU process
    #: on the box, and there are ~40 of them.
    GPU_EVERY_S = 5.0

    def __init__(self, sink, stop, events):
        super().__init__(name="sampler", daemon=True)
        self.sink = sink
        self.stop = stop
        self.events = events          # the shared event list (for the report)
        self.seen_pids = {}           # pid -> role, so a new pid is an EVENT
        self.foreign_webview = 0
        self._shell_pids = []
        self._next_slow = 0.0
        self._next_gpu = 0.0
        self.gpu = GpuMemory()
        self.vram_seen = []           # every VRAM sample taken, for the report
        self.vram_foreign_top = {}    # pid -> peak MiB, for everything NOT ours

    def run(self):
        prev_disk = psutil.disk_io_counters()
        prev_wall = time.perf_counter()
        prev_own = {}                 # pid -> (cpu_seconds, rss_mb, role)
        # the first cpu_times_percent call primes the deltas
        psutil.cpu_times_percent(interval=None)
        while not self.stop.wait(1.0):
            now_wall = time.perf_counter()
            dt = max(now_wall - prev_wall, 1e-6)
            cpu = psutil.cpu_times_percent(interval=None)
            disk = psutil.disk_io_counters()
            vm = psutil.virtual_memory()

            read_mb = (disk.read_bytes - prev_disk.read_bytes) / dt / 1e6
            write_mb = (disk.write_bytes - prev_disk.write_bytes) / dt / 1e6
            #: `busy_time` does NOT exist on this Windows psutil (MEASURED
            #: 2026-10-22: the report printed `None` for every sample). What
            #: Windows does give is the time spent in reads and writes, so the
            #: honest metric is the share of the interval the disk was doing I/O
            #: -- named `disk_io_pct` so nobody reads it as a queue length.
            io_pct = None
            r0 = getattr(prev_disk, "read_time", None)
            w0 = getattr(prev_disk, "write_time", None)
            r1 = getattr(disk, "read_time", None)
            w1 = getattr(disk, "write_time", None)
            if None not in (r0, w0, r1, w1):
                io_pct = 100.0 * max((r1 - r0) + (w1 - w0), 0.0) / (dt * 1000.0)
            #: `interrupt` and `dpc` exist on Windows only; on a POSIX box the
            #: fields are absent and the report says so rather than pretending 0.
            int_pct = getattr(cpu, "interrupt", None)
            dpc_pct = getattr(cpu, "dpc", None)

            self.sink.write(
                k="sys", t=round(time.time(), 3),
                cpu=round(cpu.user + cpu.system, 1), cpu_user=round(cpu.user, 1),
                cpu_sys=round(cpu.system, 1), idle=round(cpu.idle, 1),
                interrupt=(None if int_pct is None else round(int_pct, 1)),
                dpc=(None if dpc_pct is None else round(dpc_pct, 1)),
                ram_avail_mb=round(vm.available / 1e6),
                disk_read_mb_s=round(read_mb, 2), disk_write_mb_s=round(write_mb, 2),
                disk_io_pct=(None if io_pct is None else round(io_pct, 1)),
            )

            if now_wall >= self._next_slow:
                self._next_slow = now_wall + self.SLOW_EVERY_S
                self._shell_pids = find_shell_pids()
                self.foreign_webview = count_foreign_webviews(self._shell_pids)
            members = family(self._shell_pids)

            # ---- VRAM. The measurement whose absence made this tool lie. ----
            if now_wall >= self._next_gpu:
                self._next_gpu = now_wall + self.GPU_EVERY_S
                vram = self.gpu.read()
                if vram is not None:
                    by_pid = vram["by_pid"]
                    total = vram["adapter_mb"]
                    ours = sum(mb for pid, mb in by_pid.items() if pid in members)
                    self.vram_seen.append({"t": round(time.time(), 3),
                                           "total_mb": round(total),
                                           "ours_mb": round(ours), "n": len(by_pid)})
                    for pid, mb in by_pid.items():
                        if pid not in members:
                            self.vram_foreign_top[pid] = max(
                                self.vram_foreign_top.get(pid, 0.0), mb)
                    others = sorted(((pid, mb) for pid, mb in by_pid.items()
                                     if pid not in members), key=lambda kv: -kv[1])[:8]
                    self.sink.write(k="vram", t=round(time.time(), 3),
                                    total_mb=round(total), ours_mb=round(ours),
                                    our_pids={str(pid): round(by_pid[pid])
                                              for pid in members if pid in by_pid},
                                    top_other=[{"pid": pid, "mb": round(mb)}
                                               for pid, mb in others])
            roles = {0: "shell", 1: "worker", 2: "webview", 3: "conhost", 4: "other"}
            by_role = {}
            own_total = 0.0
            rss_total = 0.0
            for pid, role in members.items():
                try:
                    p = psutil.Process(pid)
                    ct = p.cpu_times()
                    cpu_s = ct.user + ct.system
                    rss = p.memory_info().rss / 1e6
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                pct = None
                if pid in prev_own:
                    pct = round(100.0 * max(cpu_s - prev_own[pid][0], 0.0) / dt, 1)
                prev_own[pid] = (cpu_s, rss, role)
                own_total += cpu_s
                rss_total += rss
                slot = by_role.setdefault(role, {"n": 0, "cpu_s": 0.0, "rss_mb": 0.0,
                                                 "cpu_pct": 0.0})
                slot["n"] += 1
                slot["cpu_s"] += cpu_s
                slot["rss_mb"] += rss
                if pct is not None:
                    slot["cpu_pct"] += pct
                if pid not in self.seen_pids:
                    self.seen_pids[pid] = role
                    self.events.append({"t": round(time.time(), 3), "what": "pid-appeared",
                                        "role": role, "pid": pid})
                    self.sink.write(k="event", what="pid-appeared", role=role, pid=pid)

            if members:
                self.sink.write(k="family", t=round(time.time(), 3),
                                n=len(members), ours_cpu_s=round(own_total, 1),
                                rss_mb=round(rss_total), foreign_webview=self.foreign_webview,
                                roles={r: {"n": v["n"], "cpu_pct": round(v["cpu_pct"], 1),
                                           "rss_mb": round(v["rss_mb"])}
                                       for r, v in sorted(by_role.items())})
            prev_disk, prev_wall = disk, now_wall


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def launch_app(env_extra=None):
    """Start the app the way the owner does: through its own documented entry."""
    env = dict(os.environ)
    env.setdefault("SOTTO_REDUX_LIVE", "1")
    if env_extra:
        env.update(env_extra)
    return subprocess.Popen(
        ["cmd", "/c", RUN_CMD], cwd=os.path.join(ROOT, "app", "webview"),
        env=env, creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def run(args) -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or os.path.join(ROOT, "_main", "perf", f"sotto-perf-{stamp}.jsonl")
    stall_path = out + ".stalls"
    stop_path = out + ".stop"
    for path in (stop_path, stall_path):
        if os.path.exists(path):
            os.remove(path)
    sink = Sink(out)
    stop = threading.Event()
    events = []
    probe_period = 1.0 / args.probe_hz
    sink.write(k="meta", what="start", ts=stamp, root=ROOT,
               cpus=psutil.cpu_count(logical=True),
               phys_cpus=psutil.cpu_count(logical=False),
               ram_total_mb=round(psutil.virtual_memory().total / 1e6),
               probe_hz=args.probe_hz, probe_in=("thread" if args.in_process_probe
                                                 else "own-process"),
               sampler=("off (--solo)" if args.solo else "on"),
               launch=str(args.launch), seconds=args.seconds,
               baseline_s=args.baseline)
    print(f"sotto-perf-log: writing {out}")
    print(f"  probe: {'THREAD (shares the GIL)' if args.in_process_probe else 'OWN PROCESS'}"
          f" @ {args.probe_hz:g} Hz; sampler {'OFF' if args.solo else '1 Hz'}")
    print(f"  baseline {args.baseline:.0f}s, then {'LAUNCH' if args.launch else 'no launch'}, "
          f"total {args.seconds:.0f}s")

    # THE PROBE, IN ITS OWN PROCESS. See PROBE_CHILD.
    child = None
    thread_probe = None
    if args.in_process_probe:
        thread_probe = SlipProbe(sink, stop)
        thread_probe.PERIOD_S = probe_period
        thread_probe.start()
    else:
        child = subprocess.Popen(
            [sys.executable, "-c", PROBE_CHILD, stall_path, stop_path, str(probe_period)],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    sampler = None if args.solo else Sampler(sink, stop, events)
    if sampler:
        sampler.start()

    t_start = time.time()
    launched_at = None
    if args.launch:
        time.sleep(args.baseline)
        sink.write(k="event", what="launch-started", cmd=RUN_CMD)
        print("  >> launching the app now (through run.cmd, hidden)")
        launched_at = time.time()
        proc = launch_app()
        # wait for the shell process to exist, and say HOW LONG it took
        shell_t = None
        while time.time() - launched_at < 60 and not stop.is_set():
            if find_shell_pids():
                shell_t = time.time() - launched_at
                break
            time.sleep(0.05)
        sink.write(k="event", what="shell-appeared",
                   after_s=(None if shell_t is None else round(shell_t, 2)),
                   launcher_pid=proc.pid)
        print("  >> shell-appeared after %s s" % ("-" if shell_t is None else f"{shell_t:.2f}"))

    remaining = args.seconds - (time.time() - t_start)
    while remaining > 0:
        time.sleep(min(1.0, remaining))
        remaining = args.seconds - (time.time() - t_start)

    stop.set()
    open(stop_path, "w").close()
    probe_note = ""
    if thread_probe is not None:
        thread_probe.join(timeout=5)
        probe_note = "in-process probe bookkeeping: %.1f ms" % (thread_probe.self_us / 1000.0)
    if child is not None:
        try:
            o, e = child.communicate(timeout=15)
            probe_note = (o or e or "").strip().splitlines()[-1] if (o or e) else ""
        except subprocess.TimeoutExpired:
            child.kill()
            probe_note = "probe child had to be killed"
    if sampler:
        sampler.join(timeout=5)
    sink.write(k="meta", what="stop", seconds=round(time.time() - t_start, 1),
               lines=sink.written, probe_note=probe_note)
    sink.close()
    print(f"  done: {sink.written} records, {round(time.time() - t_start, 1)} s; {probe_note}")
    return report(out, launched_at)


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def _proc_label(pid):
    """-> (name, first 70 chars of command line) for a pid, or ('?', '').

    Read at REPORT time, not at sample time: the holder of 7 GB of VRAM may have
    exited between the sample and the reading of it, and a name looked up then is
    worth more than a pid nobody can trace.
    """
    try:
        p = psutil.Process(pid)
        return (p.name() or "?")[:22], " ".join(p.cmdline() or [])[:70]
    except Exception:  # noqa: BLE001
        return "?", ""


def _pct(values, p):
    if not values:
        return None
    values = sorted(values)
    k = min(len(values) - 1, max(0, int(round((p / 100.0) * (len(values) - 1)))))
    return values[k]


def report(path, launched_at=None) -> int:
    stalls, sysrows, fams, evs, vrams, meta = [], [], [], [], [], {}
    # The slips live in a SIDECAR file when the probe ran in its own process
    # (see PROBE_CHILD); older single-file logs keep them inline.
    paths = [path]
    if os.path.exists(path + ".stalls"):
        paths = [path, path + ".stalls"]
    for one in paths:
        with open(one, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                k = rec.get("k")
                if k == "stall":
                    stalls.append(rec)
                elif k == "sys":
                    sysrows.append(rec)
                elif k == "family":
                    fams.append(rec)
                elif k == "vram":
                    vrams.append(rec)
                elif k == "event":
                    evs.append(rec)
                elif k == "meta":
                    meta.update(rec)

    if launched_at is None:
        for e in evs:
            if e.get("what") == "launch-started":
                launched_at = e.get("t")
    if launched_at is None:
        # a meta record carries the wall clock of the start; derive if needed
        launched_at = (stalls[0]["at"] if stalls else time.time())

    print()
    print("=" * 78)
    print("SOTTO PERF REPORT -- %s" % os.path.basename(path))
    print("=" * 78)
    printed = meta.get("lines")
    print("  records      : %s (%s sys samples, %s family samples, %s slips)"
          % (printed, len(sysrows), len(fams), len(stalls)))
    if sysrows:
        print("  machine      : %s logical cpus, %s MB RAM total"
              % (meta.get("cpus"), meta.get("ram_total_mb")))

    # ---- 1. the stutter ----
    slips = [s["slip_ms"] for s in stalls]
    if slips:
        over50 = [s for s in slips if s > 50]
        over100 = [s for s in slips if s > 100]
        over250 = [s for s in slips if s > 250]
        print()
        print("1. TIMER SLIP -- how late a 25 ms sleep woke up (the felt stutter)")
        print("     p50 %.1f ms   p90 %.1f   p99 %.1f   MAX %.1f"
              % (_pct(slips, 50), _pct(slips, 90), _pct(slips, 99), max(slips)))
        print("     slips > 50 ms : %d   > 100 ms : %d   > 250 ms : %d"
              % (len(over50), len(over100), len(over250)))
        print("     probe: %s @ %s Hz -- %s"
              % (meta.get("probe_in", "?"), meta.get("probe_hz", "?"),
                 meta.get("probe_note") or "no bookkeeping reported"))

    # ---- 4. the family ----
    print()
    if not fams:
        print("4. THE SOTTO FAMILY -- NONE FOUND. No process carried "
              "`%s`, so the app was not running during this log." % SHELL_MARKER)
    else:
        peak_n = max(f["n"] for f in fams)
        peak_rss = max(f["rss_mb"] for f in fams)
        last = fams[-1]
        peak_roles = {}
        for f in fams:
            for role, slot in f["roles"].items():
                cur = peak_roles.setdefault(role, {"n": 0, "cpu_pct": 0.0, "rss_mb": 0})
                cur["n"] = max(cur["n"], slot["n"])
                cur["cpu_pct"] = max(cur["cpu_pct"], slot["cpu_pct"])
                cur["rss_mb"] = max(cur["rss_mb"], slot["rss_mb"])
        print("4. THE SOTTO FAMILY -- attributed BY THE PROCESS TREE")
        print("     peak processes : %d      peak RSS : %s MB" % (peak_n, peak_rss))
        print("     CPU used (process time, whole run): %.1f s (shell+worker+its webviews)"
              % last["ours_cpu_s"])
        for role, slot in sorted(peak_roles.items(), key=lambda kv: -kv[1]["rss_mb"]):
            print("       %-8s peak n=%-3d  %5.1f %% cpu    %6d MB rss"
                  % (role, slot["n"], slot["cpu_pct"], slot["rss_mb"]))
        if last.get("foreign_webview"):
            print("     NOT BLAMED ON SOTTO: %d other msedgewebview2.exe on the box "
                  "(another app's)" % last["foreign_webview"])
        born = [e for e in evs if e.get("what") == "pid-appeared"]
        by_role = {}
        for e in born:
            by_role[e["role"]] = by_role.get(e["role"], 0) + 1
        print("     processes STARTED during the log: %d  %s"
              % (len(born), ", ".join("%s x%d" % (r, n) for r, n in sorted(by_role.items()))))
        for e in evs:
            if e.get("what") == "shell-appeared":
                print("     shell-appeared %s s after launch" % e.get("after_s"))

    # ---- 5. VRAM: who owns the graphics memory, and how much of it is ours ----
    print()
    if not vrams:
        print("5. VRAM -- not sampled (pywin32/PDH counter unavailable, or --solo).")
    else:
        peak_total = max(v["total_mb"] for v in vrams)
        peak_ours = max(v["ours_mb"] for v in vrams)
        print("5. VRAM -- dedicated graphics memory, attributed by PID (PDH)")
        print("     peak in use : %d MiB   (the Sotto family's peak share: %d MiB)"
              % (peak_total, peak_ours))
        if peak_ours == 0:
            print("     THE SOTTO FAMILY HOLDS NO VRAM in this log. Whatever is filling "
                  "the card is another program -- measured below, by name.")
        # the family's own pids, at their peak in this log
        tops = {}
        for rec in vrams:
            for pid, mb in (rec.get("our_pids") or {}).items():
                tops[int(pid)] = max(tops.get(int(pid), 0), mb)
        for pid, mb in sorted(tops.items(), key=lambda kv: -kv[1])[:8]:
            print("       ours  pid=%-7d %-22s %6d MiB  %s"
                  % (pid, _proc_label(pid)[0], mb, _proc_label(pid)[1]))
        # everything else: the worst seen for each pid during the log
        foreign = {}
        for rec in vrams:
            for item in (rec.get("top_other") or []):
                pid = int(item.get("pid"))
                foreign[pid] = max(foreign.get(pid, 0), item.get("mb") or 0)
        for pid, mb in sorted(foreign.items(), key=lambda kv: -kv[1])[:8]:
            print("       OTHER pid=%-7d %-22s %6d MiB  %s"
                  % (pid, _proc_label(pid)[0], mb, _proc_label(pid)[1]))

    # ---- 2 + 3. what the machine was doing when it stuttered ----
    if slips and sysrows:
        worst = sorted(stalls, key=lambda s: -s["slip_ms"])[:12]
        print()
        print("2+3. WHAT WAS RUNNING WHEN IT STUTTERED (the 12 worst slips)")
        print("     %-9s %8s %6s %5s %5s %8s %9s %s"
              % ("clock", "slip_ms", "cpu%", "int", "dpc", "disk_io", "ram_avail", "family"))
        for s in worst:
            near = min(sysrows, key=lambda r: abs(r["t"] - s["at"]))
            fam = min(fams, key=lambda r: abs(r["t"] - s["at"])) if fams else None
            who = "-"
            if fam:
                who = "n=%d rss=%dMB" % (fam["n"], fam["rss_mb"])
            print("     %-9s %8.1f %6s %5s %5s %8s %9s %s"
                  % (time.strftime("%H:%M:%S", time.localtime(s["at"])), s["slip_ms"],
                     near.get("cpu"), near.get("interrupt", "-"), near.get("dpc", "-"),
                     near.get("disk_io_pct", "-"),
                     str(near.get("ram_avail_mb")) + "MB", who))

    # ---- the before/after: what the LAUNCH itself cost ----
    if slips and meta.get("launch") in (True, "True"):
        before = [s["slip_ms"] for s in stalls if s["at"] < launched_at]
        during = [s["slip_ms"] for s in stalls
                  if launched_at <= s["at"] < launched_at + 60]
        after = [s["slip_ms"] for s in stalls if s["at"] >= launched_at + 60]
        print()
        print("THE LAUNCH, BEFORE AND AFTER (launch at %s)"
              % time.strftime("%H:%M:%S", time.localtime(launched_at)))
        for label, series in (("before launch", before),
                              ("first 60 s after", during),
                              ("after that", after)):
            if not series:
                continue
            print("     %-18s n=%-6d p50 %6.1f ms  p90 %6.1f  p99 %6.1f  max %6.1f"
                  % (label, len(series), _pct(series, 50), _pct(series, 90),
                     _pct(series, 99), max(series)))

    # ---- the verdict: name what coincided ----
    print()
    if not slips:
        print("VERDICT: no slip samples -- the probe did not run.")
        return 1
    top = max(slips)
    print("VERDICT:")
    if not fams:
        print("  The app never ran during this log (`%s` never appeared), so this "
              "run measures the MACHINE, not Sotto." % SHELL_MARKER)
    else:
        fam_at_worst = None
        for s in sorted(stalls, key=lambda s: -s["slip_ms"])[:1]:
            fam_at_worst = min(fams, key=lambda r: abs(r["t"] - s["at"])) if fams else None
        print("  worst slip %.1f ms; the Sotto family was at %s"
              % (top, ("n=%d, rss=%d MB"
                       % (fam_at_worst["n"], fam_at_worst["rss_mb"]))
                 if fam_at_worst else "unknown"))
        durs = [r for r in sysrows if r.get("disk_busy_pct") is not None]
        if durs:
            print("  disk busy: p50 %.1f %%  max %.1f %%"
                  % (_pct([r["disk_busy_pct"] for r in durs], 50),
                     max(r["disk_busy_pct"] for r in durs)))
        print("  READ THIS AS CORRELATION, NOT CAUSE: the file has every sample; "
              "the pairs above are the moments to look at.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=150.0,
                    help="total capture time (default 150)")
    ap.add_argument("--baseline", type=float, default=8.0,
                    help="seconds of baseline BEFORE the launch (default 8)")
    ap.add_argument("--out", default=None, help="jsonl sink")
    ap.add_argument("--solo", action="store_true",
                    help="NO sampler thread: the probe alone, to separate the "
                         "MACHINE's stutter from the instrument's own cost")
    ap.add_argument("--probe-hz", type=float, default=40.0,
                    help="slip-probe rate (default 40)")
    ap.add_argument("--in-process-probe", action="store_true",
                    help="run the probe as a THREAD of this process (the first, "
                         "WRONG design: it shares the GIL with the sampler)")
    ap.add_argument("--launch", action="store_true",
                    help="start the app through app/webview/run.cmd after the baseline")
    ap.add_argument("--report", default=None,
                    help="analyse an existing .jsonl instead of capturing")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.report:
        return report(args.report)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
