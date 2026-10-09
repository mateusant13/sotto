#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
focus-timeline-probe.py -- LANE: app em foco + fila de foco (metade A).

Instrumento de MEDICAO da linha do tempo de foco do Windows, por EVENTO (nao por
amostragem), com a fila de foco (as N janelas seguintes na ordem Z) capturada em
cada transicao.

NAO abre dispositivo de audio. NAO mata nada. NAO cria janela nenhuma
(o processo nao tem HWND: corre com pythonw.exe).

Vias medidas
------------
* Evento:   SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
            0, cb, 0, 0, WINEVENT_OUTOFCONTEXT) + message loop na thread que
            instalou o hook. A latencia e medida DIRETAMENTE contra o campo
            `dwmsEventTime` que o proprio WinEventProc entrega:
                latencia_ms = GetTickCount64() - dwmsEventTime
* Amostra:  uma thread a `--poll-ms` a ler GetForegroundWindow(). Serve de
            (a) verdade-terreno para a latencia do hook e
            (b) CONTROLADO: re-amostrada offline a 1000 ms no oracle, mostra
            quantas transicoes um amostrador ingenuo PERDE.
* Fila:     GetWindow(hwnd, GW_HWNDNEXT) a partir do foco, com filtro de
            top-level + visivel + nao-cloaked (DwmGetWindowAttribute,
            DWMWA_CLOAKED) + sem WS_EX_TOOLWINDOW + fora dos pids do Sotto.
            Cada evento grava TAMBEM a contagem crua e as janelas que o filtro
            rejeitou, portanto as DUAS CORES do gate saem na mesma corrida.

Uso
---
  pythonw.exe _main\\focus-timeline-probe.py --mode live --secs 300 \\
      --jsonl _main\\focus-timeline-live.jsonl \\
      --summary _main\\focus-timeline-live-summary.json --label live

  pythonw.exe _main\\focus-timeline-probe.py --mode poll-only --poll-ms 1000 ...
  pythonw.exe _main\\focus-timeline-probe.py --mode live --no-ghost-filter ...

Contrato de cada evento (uma linha JSONL)
-----------------------------------------
  {t, t_mono_ms, source, reason, latency_ms, event_time_ms, stale,
   focus:{hwnd,pid,exe,title,class}, prev:{...}|null, focus_changed,
   queue:[{z,hwnd,pid,exe,title,class}], queue_depth,
   raw_walked, filtered_n, ghost_rejected_n, ghost_in_top_slots,
   ghosts:[{hwnd,pid,exe,title,class,why}], handle_ms}
"""

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
GW_HWNDNEXT = 2
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WM_QUIT = 0x0012
WM_GETTEXT = 0x000D
SMTO_BLOCK = 0x0001
SMTO_ABORTIFHUNG = 0x0002

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetTopWindow.restype = wintypes.HWND
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD,
)
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [
    wintypes.UINT, wintypes.UINT, wintypes.HMODULE, WINEVENTPROC,
    wintypes.DWORD, wintypes.DWORD, wintypes.UINT,
]
user32.UnhookWinEvent.restype = wintypes.BOOL
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]

dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
]

kernel32.GetTickCount64.restype = ctypes.c_ulonglong
kernel32.GetTickCount64.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


def filetime_to_100ns(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def self_cpu_100ns():
    c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    h = kernel32.GetCurrentProcess()
    if not kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                    ctypes.byref(k), ctypes.byref(u)):
        return None
    return filetime_to_100ns(k) + filetime_to_100ns(u)


kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
]


# --------------------------------------------------------------------------
# Identidade de janela / processo
# --------------------------------------------------------------------------

class Describer:
    """Descreve janelas; cacheia exe por pid (OpenProcess nao e barato)."""

    def __init__(self, exclude_pids):
        self.exe_cache = {}
        self.exclude_pids = set(int(p) for p in exclude_pids)
        self.self_pid = os.getpid()
        self.exclude_pids.add(self.self_pid)
        self.n_openprocess = 0
        self.n_dwm = 0

    def exe_of(self, pid):
        if pid in self.exe_cache:
            return self.exe_cache[pid]
        path = None
        if pid:
            self.n_openprocess += 1
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(1024)
                    if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                        path = buf.value
                finally:
                    kernel32.CloseHandle(h)
        self.exe_cache[pid] = path
        return path

    def title_of(self, hwnd):
        buf = ctypes.create_unicode_buffer(1024)
        n = user32.GetWindowTextW(hwnd, buf, 1024)
        return buf.value, int(n)

    def class_of(self, hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, buf, 512)
        return buf.value

    def cloaked(self, hwnd):
        v = wintypes.DWORD(0)
        self.n_dwm += 1
        rc = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), 4)
        if rc != 0:
            return None, rc
        return int(v.value), rc

    def pid_of(self, hwnd):
        pid = wintypes.DWORD(0)
        tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value), int(tid)

    def title_crosscheck(self, hwnd):
        """Duas vias independentes para o MESMO titulo:
        GetWindowTextW (le a caption interna; para janelas de OUTRO processo
        nao envia WM_GETTEXT) vs SendMessageTimeoutW(WM_GETTEXT)."""
        gwt, gwt_len = self.title_of(hwnd)
        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.c_size_t(0)
        rc = user32.SendMessageTimeoutW(
            hwnd, WM_GETTEXT, 1024, ctypes.addressof(buf),
            SMTO_ABORTIFHUNG | SMTO_BLOCK, 50, ctypes.byref(res))
        return {
            "gwt": gwt, "gwt_len": gwt_len,
            "wm_gettext": buf.value, "wm_len": int(res.value),
            "wm_rc": int(rc),
            "agree": bool(gwt == buf.value),
        }

    def describe(self, hwnd):
        hwnd = int(hwnd)
        pid, tid = self.pid_of(hwnd)
        title, tlen = self.title_of(hwnd)
        return {
            "hwnd": "0x%08X" % (hwnd & 0xFFFFFFFFFFFFFFFF),
            "pid": pid,
            "tid": tid,
            "exe": self.exe_of(pid),
            "title": title,
            "title_len": tlen,
            "class": self.class_of(hwnd),
        }

    # -- gate do filtro ---------------------------------------------------
    def verdict(self, hwnd, root_of_fg):
        """(aceite?, razao). A razao e o nome do filtro que o rejeitou."""
        hwnd = int(hwnd)
        if not hwnd:
            return False, "null"
        pid, _ = self.pid_of(hwnd)
        if pid in self.exclude_pids:
            return False, "own-pid"
        root = int(user32.GetAncestor(hwnd, GA_ROOT) or 0)
        if root != hwnd:
            return False, "not-toplevel"
        if not user32.IsWindowVisible(hwnd):
            return False, "invisible"
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        if ex & WS_EX_TOOLWINDOW:
            return False, "toolwindow"
        ck, _rc = self.cloaked(hwnd)
        if ck:
            return False, "cloaked(%d)" % ck
        return True, "ok"


def walk_queue(desc, fg_hwnd, depth, ghost_filter_on, max_walk, ghost_sample):
    """Percorre a ordem Z a partir do foco.

    Devolve (queue, raw_walked, filtered_n, ghost_in_top_slots, ghosts).
    `queue` e o que o filtro ACEITA (ou o cru, se ghost_filter_on=False).
    `ghost_in_top_slots` conta quantas das `depth` primeiras posicoes CRUAS
    seriam rejeitadas pelo filtro -- e a medida da poluicao.
    """
    queue = []
    raw = []
    ghosts = []
    reasons_all = {}
    hwnd = int(fg_hwnd or 0)
    walked = 0
    while hwnd and walked < max_walk:
        hwnd = int(user32.GetWindow(hwnd, GW_HWNDNEXT) or 0)
        if not hwnd:
            break
        walked += 1
        ok, why = desc.verdict(hwnd, fg_hwnd)
        reasons_all[why] = reasons_all.get(why, 0) + 1
        if len(raw) < depth:
            raw.append((hwnd, ok, why))
        if ok:
            if len(queue) < depth:
                queue.append((hwnd, len(queue) + 1))
        elif len(ghosts) < ghost_sample:
            d = desc.describe(hwnd)
            d["why"] = why
            ghosts.append(d)
        if len(queue) >= depth and len(raw) >= depth:
            break
    ghost_in_top = sum(1 for (_h, ok, _w) in raw if not ok)
    if not ghost_filter_on:
        # COR DA CORRECAO DESLIGADA: a fila passa a ser o cru.
        queue = [(h, i + 1) for i, (h, _ok, _w) in enumerate(raw)]
    out = []
    for h, z in queue:
        d = desc.describe(h)
        d["z"] = z
        # anotacao INDEPENDENTE de cada entrada emitida: mesmo com o filtro
        # ligado, o veredicto e recalculado aqui -- a fila nao se auto-certifica
        ok2, why2 = desc.verdict(h, fg_hwnd)
        d["passes_filter"] = bool(ok2)
        d["ghost_why"] = None if ok2 else why2
        out.append(d)
    return out, walked, len(queue), ghost_in_top, ghosts, reasons_all


# --------------------------------------------------------------------------
# Deteccao da app do dono (uma unica vez, no arranque -- nunca em ciclo)
# --------------------------------------------------------------------------

def detect_sotto_pids():
    """Pids cuja command line e sotto_webview.py / sotto_worker.py.

    Uma passagem psutil no arranque. NAO e um ciclo e NAO usa
    Get-CimInstance Win32_Process (regra da casa).
    """
    found = {}
    try:
        import psutil
    except Exception as exc:                                  # pragma: no cover
        return found, "psutil-unavailable: %s" % exc
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = p.info.get("cmdline") or []
        except Exception:
            cl = []
        blob = " ".join(cl).lower()
        if "sotto_webview.py" in blob or "sotto_worker.py" in blob:
            found[int(p.info["pid"])] = {
                "name": p.info.get("name"),
                "which": "sotto_webview.py" if "sotto_webview.py" in blob else "sotto_worker.py",
            }
    return found, "psutil-ok"


def detect_sotto_windows(desc, sotto_pids):
    """Janelas do Sotto por DUAS regras independentes, para poder dize-lo."""
    hits = []
    first = int(user32.GetTopWindow(None) or 0)
    h = first
    seen = 0
    while h and seen < 4000:
        seen += 1
        d = desc.describe(h)
        rule = None
        if d["pid"] in sotto_pids:
            rule = "pid-in-sotto-cmdline"
        elif d["title"] == "Sotto" and d["class"].startswith("WindowsForms10.Window.8.app"):
            rule = "title+class(panel-form)"
        if rule:
            d["rule"] = rule
            d["visible"] = bool(user32.IsWindowVisible(h))
            hits.append(d)
        h = int(user32.GetWindow(h, GW_HWNDNEXT) or 0)
    return hits, seen


# --------------------------------------------------------------------------
# Probe
# --------------------------------------------------------------------------

class Probe:
    def __init__(self, args):
        self.args = args
        self.sotto_pids = {}
        self.sotto_rule_src = ""
        self.desc = None
        self.stop = threading.Event()
        self.t_main = 0
        self.hook = None
        self.cb = None
        self._wlock = threading.Lock()
        self.fh = None
        self.n_hook = 0
        self.n_poll = 0
        self.lat = []
        self.lat_hi = []
        self.handle_ms = []
        self.errors = []
        self.t0 = None
        self.cpu0 = None
        self.last_fg = 0
        self.last_desc = None
        self.last_poll_fg = 0
        self.last_poll_desc = None
        self.threads_with_poller = None
        self.sotto_windows = []
        self.z_census = 0
        self.threads_at_start = None
        self.threads_before_poller = None
        self.reasons_total = {}

    # -- escrita ----------------------------------------------------------
    def emit(self, rec):
        line = json.dumps(rec, ensure_ascii=False)
        with self._wlock:
            self.fh.write(line + "\n")
            self.fh.flush()

    def base(self, source, reason):
        return {
            "t": round(time.time(), 4),
            "t_mono_ms": int(kernel32.GetTickCount64()),
            "source": source,
            "reason": reason,
            "label": self.args.label,
            "arm": self.args.arm,
        }

    # -- captura de uma transicao ----------------------------------------
    def snapshot(self, source, reason, hwnd_hint=None, event_time_ms=None, prev=None):
        t_start = int(kernel32.GetTickCount64())
        perf0 = time.perf_counter()
        fg = int(hwnd_hint or 0) or int(user32.GetForegroundWindow() or 0)
        rec = self.base(source, reason)
        if event_time_ms is not None:
            rec["event_time_ms"] = int(event_time_ms)
            # GetTickCount64 tem resolucao de 1 ms e dwmsEventTime tambem, logo
            # o valor inteiro e um PISO. O limite superior e o piso + 1 ms.
            rec["latency_ms"] = t_start - int(event_time_ms)
            rec["latency_hi_ms"] = rec["latency_ms"] + 1
            self.lat.append(rec["latency_ms"])
            self.lat_hi.append(rec["latency_hi_ms"])
        if source == "hook":
            now_fg = int(user32.GetForegroundWindow() or 0)
            rec["stale"] = bool(now_fg != fg)
            rec["fg_at_handle"] = "0x%08X" % (now_fg & 0xFFFFFFFFFFFFFFFF)
        focus = self.desc.describe(fg) if fg else None
        rec["focus"] = focus
        if focus and self.args.title_crosscheck:
            rec["title_crosscheck"] = self.desc.title_crosscheck(fg)
        rec["prev"] = prev
        rec["focus_changed"] = bool(prev is None or (focus and prev.get("hwnd") != focus["hwnd"]))
        q, walked, fn, ghost_top, ghosts, reasons_all = walk_queue(
            self.desc, fg, self.args.queue_depth, not self.args.no_ghost_filter,
            self.args.max_walk, self.args.ghost_sample,
        )
        rec["queue"] = q
        rec["queue_depth"] = len(q)
        rec["raw_walked"] = walked
        rec["filtered_n"] = fn
        rec["ghost_in_top_slots"] = ghost_top
        rec["ghost_rejected_n"] = len(ghosts)
        rec["ghosts"] = ghosts
        rec["ghost_reasons_all"] = reasons_all
        for k, v in reasons_all.items():
            self.reasons_total[k] = self.reasons_total.get(k, 0) + v
        rec["ghost_filter"] = not self.args.no_ghost_filter
        rec["handle_ms"] = round((time.perf_counter() - perf0) * 1000.0, 3)
        self.handle_ms.append(rec["handle_ms"])
        return rec

    # -- callback do hook -------------------------------------------------
    def _on_event(self, hook, event, hwnd, id_object, id_child, tid, event_time_ms):
        if self.stop.is_set():
            return
        try:
            rec = self.snapshot("hook", "foreground-event",
                                hwnd_hint=int(hwnd or 0),
                                event_time_ms=int(event_time_ms),
                                prev=self.last_desc)
            rec["id_object"] = int(id_object)
            rec["id_child"] = int(id_child)
            rec["event"] = int(event)
            self.n_hook += 1
            self.emit(rec)
            if rec.get("focus"):
                self.last_desc = rec["focus"]
                self.last_fg = int(hwnd or 0)
        except Exception as exc:                              # pragma: no cover
            self.errors.append("hook-cb: %r" % (exc,))

    # -- thread de amostragem --------------------------------------------
    def poll_loop(self, stopper):
        # A poller tem o SEU PROPRIO ultimo-foco. Se partilhasse `last_fg` com o
        # hook, o hook consumia a mudanca primeiro e a poller nunca a via --
        # medido: 38 eventos de hook contra 9 transicoes da poller na MESMA
        # janela, com a poller a reportar menos mudancas do que o hook. As duas
        # vias tem de ser independentes para a comparacao valer.
        nxt = time.perf_counter()
        while not self.stop.is_set():
            if self.threads_with_poller is None:
                self.threads_with_poller = self._nthreads()
            try:
                fg = int(user32.GetForegroundWindow() or 0)
                if fg != self.last_poll_fg:
                    rec = self.snapshot("poll", "poll-detect", hwnd_hint=fg,
                                        prev=self.last_poll_desc)
                    self.n_poll += 1
                    self.emit(rec)
                    self.last_poll_fg = fg
                    if rec.get("focus"):
                        self.last_poll_desc = rec["focus"]
            except Exception as exc:                          # pragma: no cover
                self.errors.append("poll: %r" % (exc,))
            nxt += self.args.poll_ms / 1000.0
            d = nxt - time.perf_counter()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.perf_counter()
            if stopper and time.time() - self.t0 >= self.args.secs:
                break
        if stopper:
            self.finish_and_quit()

    @staticmethod
    def _nthreads():
        try:
            import psutil
            return psutil.Process(os.getpid()).num_threads()
        except Exception:
            return None

    # -- fim --------------------------------------------------------------
    def finish_and_quit(self):
        if self.stop.is_set():
            return
        self.stop.set()
        try:
            rec = self.snapshot("probe", "arm-stop", prev=self.last_desc)
            self.emit(rec)
        except Exception as exc:                              # pragma: no cover
            self.errors.append("stop-snapshot: %r" % (exc,))
        try:
            user32.PostThreadMessageW(self.t_main, WM_QUIT, 0, 0)
        except Exception as exc:                              # pragma: no cover
            self.errors.append("post-quit: %r" % (exc,))

    def run(self):
        a = self.args
        os.makedirs(os.path.dirname(os.path.abspath(a.jsonl)), exist_ok=True)
        self.fh = open(a.jsonl, "w", encoding="utf-8", newline="\n")
        self.sotto_pids, self.sotto_rule_src = detect_sotto_pids()
        self.desc = Describer(self.sotto_pids.keys())
        self.t_main = int(kernel32.GetCurrentThreadId())
        # cria a fila de mensagens da thread principal ANTES de a poller poder
        # fazer PostThreadMessageW para ela
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        self.t0 = time.time()
        self.cpu0 = self_cpu_100ns()
        wall0 = time.perf_counter()

        self.sotto_windows, self.z_census = detect_sotto_windows(self.desc, self.sotto_pids)
        try:
            import psutil as _ps
            self.threads_at_start = sorted(t.id for t in _ps.Process(os.getpid()).threads())
        except Exception:
            self.threads_at_start = None
        start = self.base("probe", "arm-start")
        start["mode"] = a.mode
        start["secs"] = a.secs
        start["poll_ms"] = a.poll_ms
        start["queue_depth"] = a.queue_depth
        start["ghost_filter"] = not a.no_ghost_filter
        start["max_walk"] = a.max_walk
        start["self_pid"] = os.getpid()
        start["sotto_pids"] = self.sotto_pids
        start["sotto_pid_source"] = self.sotto_rule_src
        start["sotto_windows"] = self.sotto_windows
        start["z_census_windows"] = self.z_census
        start["note"] = a.note
        fg0 = int(user32.GetForegroundWindow() or 0)
        self.last_fg = fg0
        self.last_poll_fg = fg0
        start["focus"] = self.desc.describe(fg0) if fg0 else None
        self.last_desc = start["focus"]
        q, walked, fn, gt, gh, ra = walk_queue(self.desc, fg0, a.queue_depth,
                                               not a.no_ghost_filter, a.max_walk,
                                               a.ghost_sample)
        start["queue"] = q
        start["queue_depth"] = len(q)
        start["raw_walked"] = walked
        start["filtered_n"] = fn
        start["ghost_in_top_slots"] = gt
        start["ghosts"] = gh
        start["ghost_reasons_all"] = ra
        for k, v in ra.items():
            self.reasons_total[k] = self.reasons_total.get(k, 0) + v
        start["threads_before_poller"] = self._nthreads()
        self.threads_before_poller = start["threads_before_poller"]
        self.emit(start)

        hook_ok = False
        if a.mode == "live":
            self.cb = WINEVENTPROC(self._on_event)
            flags = WINEVENT_OUTOFCONTEXT
            if a.skip_own_process:
                flags |= WINEVENT_SKIPOWNPROCESS
            self.hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None,
                self.cb, 0, 0, flags,
            )
            hook_ok = bool(self.hook)
            if not hook_ok:
                self.errors.append("SetWinEventHook failed err=%d" % ctypes.get_last_error())

        if a.mode == "live":
            th = threading.Thread(target=self.poll_loop, args=(True,),
                                  name="focus-poll", daemon=True)
            th.start()
            while True:
                r = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
                if r == 0:
                    break
                if r == -1:
                    self.errors.append("GetMessageW err=%d" % ctypes.get_last_error())
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            th.join(timeout=5.0)
        else:
            # poll-only: 1 thread. A thread principal e o amostrador.
            while time.time() - self.t0 < a.secs and not self.stop.is_set():
                fg = int(user32.GetForegroundWindow() or 0)
                if fg != self.last_fg:
                    rec = self.snapshot("poll", "poll-detect", hwnd_hint=fg,
                                        prev=self.last_desc)
                    self.n_poll += 1
                    self.emit(rec)
                    self.last_fg = fg
                    if rec.get("focus"):
                        self.last_desc = rec["focus"]
                time.sleep(a.poll_ms / 1000.0)
            self.stop.set()
            rec = self.snapshot("probe", "arm-stop", prev=self.last_desc)
            self.emit(rec)

        wall = time.perf_counter() - wall0
        cpu1 = self_cpu_100ns()
        cpu_pct = None
        if self.cpu0 is not None and cpu1 is not None and wall > 0:
            cpu_pct = round(((cpu1 - self.cpu0) / 1e7) / wall * 100.0, 3)
        try:
            import psutil
            me = psutil.Process(os.getpid())
            rss = me.memory_info().rss / (1024.0 * 1024.0)
            peak = getattr(me.memory_info(), "peak_wset", None)
            peak_mb = (peak / (1024.0 * 1024.0)) if peak else None
            nthreads = me.num_threads()
            thread_ids = sorted(t.id for t in me.threads())
        except Exception:
            rss = peak_mb = nthreads = thread_ids = None
        if self.hook:
            user32.UnhookWinEvent(self.hook)

        def stats(v):
            if not v:
                return None
            s = sorted(v)
            return {
                "n": len(s), "min": s[0], "p50": s[len(s) // 2],
                "p95": s[min(len(s) - 1, int(len(s) * 0.95))], "max": s[-1],
                "mean": round(sum(s) / len(s), 3),
            }

        summary = {
            "label": a.label, "arm": a.arm, "mode": a.mode,
            "secs_declared": a.secs, "wall_s": round(wall, 3),
            "poll_ms": a.poll_ms, "queue_depth": a.queue_depth,
            "ghost_filter": not a.no_ghost_filter,
            "hook_installed": bool(self.hook), "hook_ok": hook_ok,
            "hook_flags": (WINEVENT_OUTOFCONTEXT | (WINEVENT_SKIPOWNPROCESS if a.skip_own_process else 0)),
            "hook_events": self.n_hook, "poll_events": self.n_poll,
            "events_total": self.n_hook + self.n_poll,
            "latency_ms": stats(self.lat),
            "latency_hi_ms": stats(self.lat_hi),
            "latency_zero_frac": (None if not self.lat else
                                  round(sum(1 for v in self.lat if v == 0) / len(self.lat), 4)),
            "handle_ms": stats(self.handle_ms),
            "cpu_pct_of_one_core": cpu_pct,
            "wall_cpu_100ns": (None if self.cpu0 is None or cpu1 is None else cpu1 - self.cpu0),
            "rss_mb": None if rss is None else round(rss, 2),
            "peak_wset_mb": None if peak_mb is None else round(peak_mb, 2),
            "threads": nthreads,
            "thread_ids": thread_ids,
            "threads_at_start": self.threads_at_start,
            "threads_before_poller": self.threads_before_poller,
            "threads_with_poller": self.threads_with_poller,
            "threads_added_by_lane": (None if (self.threads_with_poller is None
                                               or self.threads_before_poller is None)
                                      else self.threads_with_poller - self.threads_before_poller),
            "self_pid": os.getpid(),
            "sotto_pids": self.sotto_pids,
            "sotto_pid_source": self.sotto_rule_src,
            "sotto_windows": self.sotto_windows,
            "z_census_windows": self.z_census,
            "exe_cache_entries": len(self.desc.exe_cache),
            "ghost_reasons_total": self.reasons_total,
            "openprocess_calls": self.desc.n_openprocess,
            "dwm_calls": self.desc.n_dwm,
            "errors": self.errors,
            "jsonl": os.path.abspath(a.jsonl),
        }
        with open(a.summary, "w", encoding="utf-8", newline="\n") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        self.fh.close()
        return summary


def main(argv=None):
    p = argparse.ArgumentParser(description="Focus timeline probe (events + Z-order queue)")
    p.add_argument("--mode", choices=["live", "poll-only"], default="live")
    p.add_argument("--secs", type=float, default=120.0)
    p.add_argument("--poll-ms", type=float, default=15.0)
    p.add_argument("--queue-depth", type=int, default=5)
    p.add_argument("--max-walk", type=int, default=400)
    p.add_argument("--ghost-sample", type=int, default=8)
    p.add_argument("--no-ghost-filter", action="store_true",
                   help="COR DA CORRECCAO DESLIGADA: a fila passa a ser o cru")
    p.add_argument("--skip-own-process", action="store_true", default=False)
    p.add_argument("--title-crosscheck", action="store_true", default=False,
                   help="GetWindowTextW vs SendMessageTimeoutW(WM_GETTEXT) no foco")
    p.add_argument("--jsonl", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--label", default="run")
    p.add_argument("--arm", default="A")
    p.add_argument("--note", default="")
    a = p.parse_args(argv)
    pr = Probe(a)
    s = pr.run()
    print(json.dumps({k: s[k] for k in (
        "label", "mode", "wall_s", "hook_ok", "hook_events", "poll_events",
        "latency_ms", "cpu_pct_of_one_core", "rss_mb", "threads", "errors")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
