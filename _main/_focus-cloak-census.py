#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/focus-cloak-census.py -- censo de UMA passagem a TODAS as janelas
top-level, com o veredicto de cada filtro do gate da fila.

Serve de CONTROLADO POSITIVO para o sub-filtro DWMWA_CLOAKED: se a corrida ao
vivo nao apanhou nenhuma janela cloaked, este censo diz se isso e porque nao
existem (SKIP honesto) ou porque o instrumento esta cego.

Nao cria janela nenhuma. Nao mata nada.

  pythonw.exe _main\\_focus-cloak-census.py --out _main\\focus-cloak-census.json
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GW_HWNDNEXT = 2
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32.GetTopWindow.restype = wintypes.HWND
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def exe_of(pid, cache):
    if pid in cache:
        return cache[pid]
    p = None
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                p = buf.value
        finally:
            kernel32.CloseHandle(h)
    cache[pid] = p
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cache = {}
    rows = []
    h = int(user32.GetTopWindow(None) or 0)
    n = 0
    while h and n < 6000:
        n += 1
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        pid = int(pid.value)
        tb = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(h, tb, 512)
        cb = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cb, 256)
        ck = wintypes.DWORD(0)
        rc = dwmapi.DwmGetWindowAttribute(h, DWMWA_CLOAKED, ctypes.byref(ck), 4)
        cloaked = int(ck.value) if rc == 0 else None
        ex = user32.GetWindowLongW(h, GWL_EXSTYLE) & 0xFFFFFFFF
        root = int(user32.GetAncestor(h, GA_ROOT) or 0)
        vis = bool(user32.IsWindowVisible(h))
        why = []
        if root != h:
            why.append("not-toplevel")
        if not vis:
            why.append("invisible")
        if ex & WS_EX_TOOLWINDOW:
            why.append("toolwindow")
        if cloaked:
            why.append("cloaked(%d)" % cloaked)
        rows.append({
            "z": len(rows) + 1,
            "hwnd": "0x%08X" % (h & 0xFFFFFFFFFFFFFFFF), "pid": pid,
            "exe": exe_of(pid, cache), "title": tb.value, "class": cb.value,
            "visible": vis, "cloaked": cloaked, "cloaked_rc": rc,
            "toolwindow": bool(ex & WS_EX_TOOLWINDOW),
            "top_level": root == h, "rejected_by": why,
            "passes_filter": not why,
        })
        h = int(user32.GetWindow(h, GW_HWNDNEXT) or 0)

    cloaked_rows = [r for r in rows if r["cloaked"]]
    out = {
        "t": round(time.time(), 3),
        "top_level_windows_walked": len(rows),
        "visible": sum(1 for r in rows if r["visible"]),
        "passes_filter": sum(1 for r in rows if r["passes_filter"]),
        "invisible": sum(1 for r in rows if not r["visible"]),
        "toolwindow": sum(1 for r in rows if r["toolwindow"]),
        "cloaked_any": len(cloaked_rows),
        "cloaked_values": {},
        "cloaked_z_positions": sorted(r["z"] for r in cloaked_rows),
        "cloaked_min_z": (min(r["z"] for r in cloaked_rows) if cloaked_rows else None),
        "cloaked_examples": cloaked_rows[:10],
        "dwm_rc_nonzero": sum(1 for r in rows if r["cloaked_rc"] != 0),
    }
    for r in cloaked_rows:
        k = str(r["cloaked"])
        out["cloaked_values"][k] = out["cloaked_values"].get(k, 0) + 1
    out["verdict"] = {
        "cloak_filter_exercised_on_this_box": len(cloaked_rows) > 0,
        "note": ("SKIP honesto: nenhuma janela cloaked existe agora, logo o sub-filtro "
                 "DWMWA_CLOAKED nao foi exercitado") if not cloaked_rows else
                ("o sub-filtro DWMWA_CLOAKED tem controlado positivo: %d janela(s) cloaked"
                 % len(cloaked_rows)),
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
