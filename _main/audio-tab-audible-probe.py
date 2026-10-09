#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio-tab-audible-probe.py -- le, NA MESMA AMOSTRA, (a) o meter WASAPI da sessao do
navegador e (b) a tira de abas por UIA, para testar se o UIA consegue dizer QUAL aba soa.

Motivo: a hipotese "GetDisplayName traz o titulo da aba" foi REFUTADA. Esta sonda mede
a alternativa, com as duas leituras simultaneas -- sem isso nao se pode correlacionar.

Por amostra (JSONL):
  ts, chrome_peak (max por sessao cujo exe e o do navegador), endpoint meters,
  e por janela: lista de abas {name, is_selected, ind_rect, ind_w, ind_h}

Escreve so em _main\\. Nao cria janelas. Nao abre dispositivo de captura.
"""
import argparse
import ctypes
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_libs"))

import comtypes  # noqa: E402
import uiautomation as auto  # noqa: E402


def load_probe_module():
    path = os.path.join(HERE, "audio-source-probe.py")
    spec = importlib.util.spec_from_file_location("audio_source_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def safe(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception as exc:
        return "<err:%s>" % type(exc).__name__


def rect_of(ctrl):
    try:
        r = ctrl.BoundingRectangle
        return [int(r.left), int(r.top), int(r.right), int(r.bottom),
                int(r.right - r.left), int(r.bottom - r.top)]
    except Exception as exc:
        return "<err:%s>" % type(exc).__name__


def collect_tabs(ctrl, out, depth=0, maxdepth=14):
    if depth > maxdepth or len(out) > 400:
        return
    try:
        children = ctrl.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            ct = ch.ControlTypeName
        except Exception:
            ct = None
        if ct == "TabItemControl":
            row = {"name": safe(ch, "Name"), "is_selected": None, "ind": None}
            try:
                row["is_selected"] = bool(ch.GetSelectionItemPattern().IsSelected)
            except Exception:
                pass
            try:
                for k in ch.GetChildren():
                    if safe(k, "ClassName") == "AlertIndicatorButton":
                        row["ind"] = rect_of(k)
                        break
            except Exception as exc:
                row["ind"] = "<err:%s>" % type(exc).__name__
            out.append(row)
        collect_tabs(ch, out, depth + 1, maxdepth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=120.0)
    ap.add_argument("--every", type=float, default=3.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--browser-exe", default="chrome.exe")
    ap.add_argument("--class-name", default="Chrome_WidgetWin_1")
    ap.add_argument("--max-windows", type=int, default=4)
    args = ap.parse_args()

    probe_mod = load_probe_module()
    pargs = argparse.Namespace(
        all_endpoints=True, floor=0.001, win=1.0, meter_iid=None,
        watch_file=None, no_endpoint_meter=False, list_endpoints=False,
        once=False, secs=0.0, hz=1.0, out=None, txt=None,
        neg_arm_iid=False, neg_arm_floor=False,
    )

    comtypes.CoInitialize()
    auto.SetGlobalSearchTimeout(2.0)
    t0 = time.time()
    c0 = time.process_time()
    fout = open(args.out, "w", encoding="utf-8") if args.out else None
    try:
        p = probe_mod.Probe(pargs)
        p.refresh_endpoints()
        root = auto.GetRootControl()
        n = 0
        while (time.time() - t0) < args.secs:
            t = time.time()
            rec = p.sample(n)
            chrome_peak = 0.0
            chrome_sessions = []
            ep_meters = {}
            for ep in rec["endpoints"]:
                if isinstance(ep["endpoint_meter_peak"], float):
                    ep_meters[ep["name"]] = ep["endpoint_meter_peak"]
                for s in ep["sessions"]:
                    if s.get("exe_name") == args.browser_exe and s.get("peak"):
                        chrome_peak = max(chrome_peak, s["peak"])
                        chrome_sessions.append(
                            {"pid": s.get("pid"), "peak": s.get("peak"),
                             "display_name": s.get("display_name"),
                             "state": s.get("state"), "endpoint": ep["name"]}
                        )
            windows = []
            for child in root.GetChildren():
                try:
                    if child.ClassName != args.class_name:
                        continue
                except Exception:
                    continue
                tabs = []
                collect_tabs(child, tabs)
                windows.append(
                    {"title": safe(child, "Name"), "pid": safe(child, "ProcessId"),
                     "n_tabs": len(tabs), "tabs": tabs}
                )
                if len(windows) >= args.max_windows:
                    break
            out = {
                "seq": n,
                "ts": rec["ts"],
                "ts_unix": rec["ts_unix"],
                "browser_peak": round(chrome_peak, 6),
                "browser_sessions": chrome_sessions,
                "endpoint_meters": ep_meters,
                "windows": windows,
            }
            if fout:
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                fout.flush()
            n += 1
            dt = args.every - (time.time() - t)
            if dt > 0:
                time.sleep(dt)
        summary = {
            "kind": "audible-probe-summary", "samples": n,
            "wall_secs": round(time.time() - t0, 3),
            "cpu_secs": round(time.process_time() - c0, 3),
            "cpu_percent_of_one_core": round(
                100.0 * (time.process_time() - c0) / max(1e-6, time.time() - t0), 2),
            "threads": 1,
        }
        if fout:
            fout.write(json.dumps(summary) + "\n")
            fout.close()
        if sys.stdout is not None:
            print(json.dumps(summary), flush=True)
        return 0
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
