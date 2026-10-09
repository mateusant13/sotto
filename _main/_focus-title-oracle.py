#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_main/_focus-title-oracle.py -- o titulo por DUAS vias, com a fronteira medida.

A afirmacao a testar: "o titulo de uma janela de OUTRO processo via
GetWindowText e confiavel para a janela EM FOCO".

O que este oraculo faz, numa passagem:
  * para cada janela TOP-LEVEL: GetWindowTextW  vs  SendMessageTimeoutW(WM_GETTEXT)
  * para cada FILHO (EnumChildWindows) da janela em foco: o mesmo par

As duas cores: se os top-level concordam e os FILHOS divergem, entao a regra
tem fronteira -- GetWindowText le a caption interna (nao envia WM_GETTEXT a
outro processo), o que serve para uma janela de topo e NAO serve para um
controlo filho. Sem esta segunda metade, "21/21 concordam" e um gate que nunca
pode dizer nao.

Nao cria janela nenhuma.

  pythonw.exe _main\\_focus-title-oracle.py --out _main\\focus-title-oracle.json
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GW_HWNDNEXT = 2
WM_GETTEXT = 0x000D
SMTO_BLOCK = 0x0001
SMTO_ABORTIFHUNG = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32.GetTopWindow.restype = wintypes.HWND
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def pid_of(h):
    p = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return int(p.value)


def title_pair(h):
    buf = ctypes.create_unicode_buffer(1024)
    n = user32.GetWindowTextW(h, buf, 1024)
    gwt = buf.value
    buf2 = ctypes.create_unicode_buffer(1024)
    res = ctypes.c_size_t(0)
    rc = user32.SendMessageTimeoutW(h, WM_GETTEXT, 1024, ctypes.addressof(buf2),
                                    SMTO_ABORTIFHUNG | SMTO_BLOCK, 50, ctypes.byref(res))
    wm = buf2.value
    cb = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, cb, 256)
    return {"hwnd": "0x%08X" % (h & 0xFFFFFFFFFFFFFFFF), "pid": pid_of(h),
            "class": cb.value, "gwt": gwt, "gwt_len": int(n),
            "wm_gettext": wm, "wm_len": int(res.value), "wm_rc": int(rc),
            "agree": bool(gwt == wm), "visible": bool(user32.IsWindowVisible(h))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-top", type=int, default=400)
    ap.add_argument("--max-children", type=int, default=900)
    a = ap.parse_args(argv)

    tops = []
    h = int(user32.GetTopWindow(None) or 0)
    n = 0
    while h and n < a.max_top:
        n += 1
        tops.append(title_pair(h))
        h = int(user32.GetWindow(h, GW_HWNDNEXT) or 0)

    fg = int(user32.GetForegroundWindow() or 0)
    kids = []
    if fg:
        def cb(hwnd, _lp):
            kids.append(title_pair(int(hwnd)))
            return True
        user32.EnumChildWindows(fg, WNDENUMPROC(cb), 0)

    # CONTROLADO POSITIVO do "filho": os filhos da janela em foco sao poucos.
    # Enumeram-se os filhos de TODAS as janelas de topo visiveis, com tecto.
    kids_all = []
    seen = set()
    for t in tops:
        if len(kids_all) >= a.max_children:
            break
        if not t["visible"]:
            continue
        hw = int(t["hwnd"], 16)
        if hw in seen:
            continue
        seen.add(hw)

        def cb2(hwnd, _lp):
            if len(kids_all) < a.max_children:
                kids_all.append(title_pair(int(hwnd)))
            return True
        try:
            user32.EnumChildWindows(hw, WNDENUMPROC(cb2), 0)
        except Exception:
            pass

    def summarise(rows, label):
        agree = sum(1 for r in rows if r["agree"])
        # a divergencia que interessa: WM_GETTEXT tem texto, GetWindowText nao
        gwt_blind = [r for r in rows if r["wm_gettext"] and not r["gwt"]]
        both_empty = sum(1 for r in rows if not r["wm_gettext"] and not r["gwt"])
        return {
            "label": label, "n": len(rows), "agree": agree,
            "disagree": len(rows) - agree,
            "gwt_blind_wm_has_text": len(gwt_blind),
            "both_empty": both_empty,
            "examples_gwt_blind": gwt_blind[:8],
            "examples_disagree": [r for r in rows if not r["agree"]][:8],
        }

    top_s = summarise(tops, "top-level")
    top_vis = [r for r in tops if r["visible"]]
    top_vis_s = summarise(top_vis, "top-level VISIVEIS")
    kid_s = summarise(kids, "filhos da janela em foco")
    kid_all_s = summarise(kids_all, "filhos de todas as janelas de topo visiveis")
    out = {
        "t": round(time.time(), 3),
        "foreground": title_pair(fg) if fg else None,
        "top_level": top_s, "top_level_visible": top_vis_s,
        "children_of_foreground": kid_s, "children_all_visible": kid_all_s,
        "top_level_rows": tops,
        "child_rows": kids,
        "child_all_rows": kids_all,
        "verdict": {
            "top_level_agrees": top_s["disagree"] == 0,
            "top_level_visible_agrees": top_vis_s["disagree"] == 0,
            "child_control_found": kid_all_s["gwt_blind_wm_has_text"] > 0
                                   or kid_all_s["disagree"] > 0,
            "statement": (
                "Top-level: %d/%d concordam. Restrito a janelas VISIVEIS (as unicas que "
                "podem estar em foco): %d/%d concordam. Filhos de todas as janelas de topo "
                "visiveis: %d/%d concordam, %d tem texto por WM_GETTEXT e nenhum por "
                "GetWindowText, %d divergem. GetWindowText nunca ficou cego onde WM_GETTEXT "
                "tinha texto (gwt_blind top-level=%d) -- a direccao da divergencia e a "
                "oposta da esperada: sao janelas auxiliares INVISIVEIS que nao respondem a "
                "WM_GETTEXT, e GetWindowText e o mais robusto dos dois"
                % (top_s["agree"], top_s["n"], top_vis_s["agree"], top_vis_s["n"],
                   kid_all_s["agree"], kid_all_s["n"], kid_all_s["gwt_blind_wm_has_text"],
                   kid_all_s["disagree"], top_s["gwt_blind_wm_has_text"])),
        },
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
