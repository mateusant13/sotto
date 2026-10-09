#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio-tab-title-probe.py -- ALTERNATIVA medida para "o titulo da ABA que fez o som".

Contexto: a hipotese de que o Chromium poe o titulo da aba no GetDisplayName() da
sessao WASAPI foi REFUTADA por medicao (devolve string vazia; ver receipt).
Esta sonda mede a via alternativa: UI Automation na tira de abas do Chrome.

O que reporta, por janela do Chrome:
  - titulo da janela (o que o Sndvol usa como fallback, segundo a MSDN)
  - TODAS as abas: Name (titulo), AutomationId, HelpText, ItemStatus, IsSelected
  - e o que o UIA expoe sobre "esta aba esta a soar" (HelpText/ItemStatus/etc.)

NAO cria janelas. NAO abre dispositivo de audio. Escreve so em _main\\.
"""
import argparse
import ctypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_libs"))

import comtypes  # noqa: E402
import uiautomation as auto  # noqa: E402


def say(msg):
    if sys.stdout is not None:
        try:
            print(msg, flush=True)
        except Exception:
            pass


def safe(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception as exc:
        return "<err:%s>" % type(exc).__name__


def prop(c, name):
    try:
        p = getattr(c, "Get" + name + "Property")()
        return p
    except Exception as exc:
        return "<err:%s>" % type(exc).__name__


def is_selected(c):
    try:
        return bool(c.GetSelectionItemPattern().IsSelected)
    except Exception:
        return None


def _legacy_state(c):
    try:
        return c.GetLegacyIAccessiblePattern().State
    except Exception as exc:
        return "<err:%s>" % type(exc).__name__


def deep_info(ch):
    """Tudo o que o UIA expoe sobre esta aba: padroes suportados, filhos e o
    LegacyIAccessible (onde um indicador de 'a soar' apareceria, se existisse)."""
    info = {}
    try:
        info["supported_patterns"] = [
            str(x) for x in ch.GetSupportedPatterns()
        ]
    except Exception as exc:
        info["supported_patterns"] = "<err:%s>" % type(exc).__name__
    try:
        info["children"] = [
            {
                "name": safe(c, "Name"),
                "control_type": safe(c, "ControlTypeName"),
                "class_name": safe(c, "ClassName"),
                "automation_id": safe(c, "AutomationId"),
                "is_offscreen": safe(c, "IsOffscreen"),
                "bounding_rect": str(safe(c, "BoundingRectangle")),
                "legacy_state": _legacy_state(c),
            }
            for c in ch.GetChildren()
        ]
    except Exception as exc:
        info["children"] = "<err:%s>" % type(exc).__name__
    try:
        leg = ch.GetLegacyIAccessiblePattern()
        info["legacy"] = {
            "name": leg.Name,
            "description": leg.Description,
            "state": leg.State,
            "role": leg.Role,
        }
    except Exception as exc:
        info["legacy"] = "<err:%s>" % type(exc).__name__
    return info


def walk_tabs(ctrl, out, depth=0, maxdepth=14, deep=False):
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
            row = {
                "name": safe(ch, "Name"),
                "automation_id": safe(ch, "AutomationId"),
                "class_name": safe(ch, "ClassName"),
                "help_text": safe(ch, "HelpText"),
                "item_status": prop(ch, "ItemStatus"),
                "is_selected": is_selected(ch),
                "bounding_rect": str(safe(ch, "BoundingRectangle")),
                "full_description": prop(ch, "FullDescription"),
            }
            if deep:
                row["deep"] = deep_info(ch)
            out.append(row)
        walk_tabs(ch, out, depth + 1, maxdepth, deep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--class-name", default="Chrome_WidgetWin_1")
    ap.add_argument("--max-windows", type=int, default=8)
    ap.add_argument("--deep", action="store_true",
                    help="por aba: padroes suportados, filhos e LegacyIAccessible")
    args = ap.parse_args()

    t0 = time.time()
    c0 = time.process_time()
    comtypes.CoInitialize()
    auto.SetGlobalSearchTimeout(2.0)
    try:
        root = auto.GetRootControl()
        report = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "window_class": args.class_name,
            "windows": [],
        }
        # janelas de topo com a classe pedida
        found = []
        for child in root.GetChildren():
            try:
                if child.ClassName == args.class_name:
                    found.append(child)
            except Exception:
                continue
            if len(found) >= args.max_windows:
                break
        report["n_windows"] = len(found)
        for w in found:
            tabs = []
            walk_tabs(w, tabs, deep=args.deep)
            report["windows"].append(
                {
                    "window_title": safe(w, "Name"),
                    "automation_id": safe(w, "AutomationId"),
                    "pid": safe(w, "ProcessId"),
                    "n_tabs": len(tabs),
                    "tabs": tabs,
                }
            )
        # controlo: qualquer outra janela de topo com abas (prova que o
        # instrumento nao esta a devolver vazio por nao encontrar nada)
        report["top_level_classes"] = sorted(
            {safe(c, "ClassName") for c in root.GetChildren()}
        )
        report["wall_secs"] = round(time.time() - t0, 3)
        report["cpu_secs"] = round(time.process_time() - c0, 3)
        try:
            import psutil

            report["rss_mb"] = round(psutil.Process().memory_info().rss / 1048576, 1)
        except Exception:
            report["rss_mb"] = None

        txt = json.dumps(report, ensure_ascii=False, indent=2)
        say(txt)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(txt + "\n")
        return 0
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
