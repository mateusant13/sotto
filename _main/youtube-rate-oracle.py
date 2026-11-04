#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: A VELOCIDADE DO PLAYER NO RELOGIO DA LEGENDA -- capacidade/observabilidade pedida pelo dono (2026-11-04); nao corresponde a nenhum id de `_main/bug-ledger.json`.
"""A VELOCIDADE DO PLAYER NO RELOGIO DA LEGENDA (2026-11-04).

O DEFEITO MEDIDO. O relogio do YouTube avanca entre duas leituras do player como
`t + (agora - leitura)`, e essa formula e' 1x POR CONSTRUCAO: a 2x o video anda
dois segundos e o ecra revela um. O `playbackRate` chega no MESMO snapshot do
DOM que o `currentTime` (`app/webview/youtube_cdp_source.py`), logo a metade que
faltava custava um campo e uma multiplicacao.

E O SEGUNDO, do mesmo instrumento: o `YT_ANCHOR_MAX_S` existia para um video
PAUSADO nao revelar por inercia, mas congelava o ecra tambem quando a LEITURA e'
que falhava -- o dono descreveu exactamente isso (*"sotto was BEFORE with the
youtube, but then it stopped"*). Pausa declarada pelo player avanca zero e
MANTEM a linha; leitura atrasada avanca ate' `YT_ANCHOR_STALL_S` e diz no log
`YOUTUBE_LIVE_STALLED`.

O QUE ELE JULGA -- o codigo REAL, carregado por ficheiro:
  1. `youtube_cdp_source.parse_snapshot` entrega `rate` do payload.
  2. `caption_overlay._PlayerCue.clock` escala pelo `rate`.
  3. `_PlayerCue` sem `rate` (ou com um valor absurdo) e' 1x -- o comportamento
     de antes, nunca uma aceleracao inventada.
  4. `SottoShell.yt_live_frame` escala o `t` que entrega a `_yt_lines`.
  5. Pausa: o `t` nao avanca e a linha continua a existir.
  6. Leitura atrasada (sem pausa): a linha CONTINUA e o log diz que parou de ler.
  7. Atraso absurdo: `None` (o ecra nao inventa para sempre).

`--neg-arm`: muta uma COPIA de `app/webview/caption_overlay.py` e de
`app/webview/sotto_webview.py` (tira o `* self.rate` e o `* rate`) e exige as
arms de escala a VERMELHO. rc=1 quando apanha todos os mutantes (convencao da
casa: um negativo devolve 1 quando APANHA).
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
OVERLAY = os.path.join(WEBVIEW, 'caption_overlay.py')
CDP = os.path.join(WEBVIEW, 'youtube_cdp_source.py')
sys.path.insert(0, WEBVIEW)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ROWS = [
    {"text": "um dois tres quatro", "start": 10.0, "end": 14.0, "cap": None,
     "words": [{"text": "um", "t": 10.0}, {"text": "dois", "t": 10.5},
               {"text": "tres", "t": 11.0}, {"text": "quatro", "t": 11.5}]},
]


def arm_snapshot_carries_rate(cdp):
    snap = cdp.parse_snapshot(json.dumps({
        "videoId": "abc12345678", "t": 12.5, "paused": False, "rate": 2.0,
        "rows": [{"text": "uma linha", "items": [
            {"text": "uma", "left": 0, "top": 0, "right": 9, "bottom": 9}]}]}))
    ok = bool(snap) and abs(float(snap.get("rate") or 0.0) - 2.0) < 1e-6
    return ok, "rate=%r" % ((snap or {}).get("rate"),)


def arm_cue_clock_scales(overlay):
    t0 = 100.0
    cue = overlay._PlayerCue(ROWS, t0, at=0.0, rate=2.0)
    got = cue.clock(now=0.5)
    ok = abs(got - (t0 + 1.0)) < 0.02
    return ok, "clock=%.3f esperado=%.3f" % (got, t0 + 1.0)


def arm_cue_default_is_1x(overlay):
    t0 = 100.0
    got_absent = overlay._PlayerCue(ROWS, t0, at=0.0).clock(now=0.5)
    got_zero = overlay._PlayerCue(ROWS, t0, at=0.0, rate=0).clock(now=0.5)
    got_junk = overlay._PlayerCue(ROWS, t0, at=0.0, rate="x").clock(now=0.5)
    ok = (abs(got_absent - (t0 + 0.5)) < 0.02
          and abs(got_zero - (t0 + 0.5)) < 0.02
          and abs(got_junk - (t0 + 0.5)) < 0.02)
    return ok, "sem=%.3f rate=0=%.3f lixo=%.3f" % (got_absent, got_zero, got_junk)


class FakeShell(object):
    """A shell reduzida ao que `yt_live_frame` le': ancora, faixa, velocidade."""

    YT_ANCHOR_MAX_S = None

    def __init__(self, mod, t0, elapsed, rate=None, paused=False):
        self.YT_ANCHOR_MAX_S = mod.ExternalCaptionWatcher.YT_ANCHOR_MAX_S
        self._yt_anchor = (t0, time.monotonic() - elapsed)
        self._yt_track = {"cues": []}
        self.yt_cdp_rate = rate
        self.yt_cdp_paused = paused
        self.seen = []

    def _yt_lines(self, track, t):
        self.seen.append(t)
        return ["linha em %.3f" % t]


def arm_live_frame_scales(mod, lines, logs):
    sh = FakeShell(mod, 10.0, 0.5, rate=2.0)
    out = mod.ExternalCaptionWatcher.yt_live_frame(sh)
    got = sh.seen[-1] if sh.seen else None
    ok = (out is not None and got is not None and abs(got - 11.0) < 0.05)
    return ok, "t=%.3f esperado=11.0 out=%r" % (got or -1, (out or [None])[0])


def arm_paused_holds(mod):
    sh = FakeShell(mod, 10.0, 2.0, rate=1.0, paused=True)
    out = mod.ExternalCaptionWatcher.yt_live_frame(sh)
    got = sh.seen[-1] if sh.seen else None
    ok = (out is not None and got is not None and abs(got - 10.0) < 0.02)
    return ok, "t=%.3f (pausado, esperado 10.000) out=%r" % (got if got is not None else -1, bool(out))


def arm_stall_is_named(mod, logs):
    logs[:] = []
    sh = FakeShell(mod, 10.0, 5.0, rate=1.0)
    mod.ExternalCaptionWatcher.yt_live_frame(sh)
    said = any("YOUTUBE_LIVE_STALLED" in x for x in logs)
    return said, "YOUTUBE_LIVE_STALLED=%s" % said


def arm_stall_clamps_the_clock(mod):
    """O ancora velho NAO extrapola: o t entregue para no teto de 3 s."""
    sh = FakeShell(mod, 10.0, 40.0, rate=2.0)
    mod.ExternalCaptionWatcher.yt_live_frame(sh)
    got = sh.seen[-1] if sh.seen else None
    want = 10.0 + mod.ExternalCaptionWatcher.YT_ANCHOR_MAX_S * 2.0
    ok = got is not None and abs(got - want) < 0.02
    return ok, "t=%.3f esperado=%.3f" % (got if got is not None else -1, want)


def run_arms(shell_path=None, overlay_path=None, cdp_path=None):
    mod = load_module(shell_path or SHELL, "sotto_shell_rate")
    overlay = load_module(overlay_path or OVERLAY, "sotto_overlay_rate")
    cdp = load_module(cdp_path or CDP, "sotto_cdp_rate")
    lines, logs = [], []
    real_log = mod.log
    mod.log = lambda msg: logs.append(str(msg))
    rows = []
    try:
        for name, fn in (
            ("snapshot-carries-rate", lambda: arm_snapshot_carries_rate(cdp)),
            ("cue-clock-scales", lambda: arm_cue_clock_scales(overlay)),
            ("cue-default-is-1x", lambda: arm_cue_default_is_1x(overlay)),
            ("live-frame-scales", lambda: arm_live_frame_scales(mod, lines, logs)),
            ("paused-holds", lambda: arm_paused_holds(mod)),
            ("stall-is-named", lambda: arm_stall_is_named(mod, logs)),
            ("stall-clamps-the-clock", lambda: arm_stall_clamps_the_clock(mod)),
        ):
            try:
                ok, detail = fn()
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, "EXCECAO %r" % (exc,)
            rows.append((name, bool(ok), str(detail)[:170]))
    finally:
        mod.log = real_log
    return rows


def main(argv):
    neg = "--neg-arm" in argv
    if neg:
        tmp = tempfile.mkdtemp(prefix="sotto-rate-mut-")
        try:
            shell_raw = io.open(SHELL, encoding="utf-8").read()
            ovl_raw = io.open(OVERLAY, encoding="utf-8").read()
            mut_shell = shell_raw.replace("base_t + elapsed * rate",
                                          "base_t + elapsed", 1)
            mut_ovl = ovl_raw.replace("t = self.t + elapsed * self.rate",
                                      "t = self.t + elapsed", 1)
            if mut_shell == shell_raw or mut_ovl == ovl_raw:
                print("NEG-ARM IMPOSSIVEL: a ancora do mutante nao esta no fonte")
                return 2
            shell_p = os.path.join(tmp, "sotto_webview_mut.py")
            ovl_p = os.path.join(tmp, "caption_overlay_mut.py")
            io.open(shell_p, "w", encoding="utf-8", newline="\n").write(mut_shell)
            io.open(ovl_p, "w", encoding="utf-8", newline="\n").write(mut_ovl)
            rows = run_arms(shell_path=shell_p, overlay_path=ovl_p)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        red = {n for n, ok, _d in rows if not ok}
        want = {"cue-clock-scales", "live-frame-scales", "stall-clamps-the-clock"}
        missed = want - red
        for name, ok, detail in rows:
            print("%-24s %s %s" % (name, "PASS" if ok else "RED", detail))
        print("")
        print("mutante relogio sem velocidade APANHADO" if not missed
              else "mutante PASSOU: %s" % ", ".join(sorted(missed)))
        print("NEG-ARM: %s (vermelhas: %s)"
              % ("PASS" if not missed else "FAIL", ", ".join(sorted(red)) or "nenhuma"))
        return 1

    rows = run_arms()
    for name, ok, detail in rows:
        print("%-24s %s %s" % (name, "PASS" if ok else "RED", detail))
    bad = [n for n, ok, _d in rows if not ok]
    print("")
    print("VERDICT: %s (%d/%d arms)"
          % ("RED" if bad else "PASS", len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
