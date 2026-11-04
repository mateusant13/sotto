#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: a legenda do YouTube REPETE o que ja' passou quando a aba esta' em
# segundo plano. MEDIDO 2026-11-04 na Chrome do dono (CDP 9222, video
# r-AsGBMDI6c): 745 amostras a ~50 ms com `visibilityState=hidden`,
# `video.currentTime` 788,34 -> 828,30, e UMA unica pintura no ecra inteiro
# (`>> I am kind of impressed.` / `Are you E6 before the the rank up?` -- cues de
# t~502..507 da faixa `en-orig`, ou seja ~286 s atras do relogio do video).
"""YOUTUBE-HIDDEN-CLOCK -- a pintura congelada nao manda no ecra.

O DEFEITO, medido e nao hipotetico: com a aba do YouTube em segundo plano o
Chrome deixa de REPINTAR a caixa de legenda, enquanto `video.currentTime`
continua a andar. O caminho CDP (`_main/youtube-cdp-source-oracle.py`) le' o DOM
do player, logo serve a MESMA linha de ha' minutos -- as palavras do dono:
*"a legenda nao ta sincronizada direito ... parece que repete a legenda de
instantes atras"*.

A CURA (2026-11-04): `youtube_monotonic.PaintStall`. A pintura so' perde a
autoridade para a FAIXA quando a MEDIDA da' dois lados:
  1. a pintura esta' PARADA -- mesma assinatura, `video.currentTime` andou mais
     de `STALE_S` desde a primeira vez que ela aparece;
  2. a FAIXA diz outra coisa -- o cue que cobre `currentTime` nao e' o cue que a
     pintura alinha. Um cue LONGO (8 s) e' o mesmo cue e nao e' congelamento.
Quando a pintura volta (uma linha distinta), ela recupera a autoridade no mesmo
tick, com o relogio a andar ou nao.

O QUE ESTE ORACULO FAZ:
  * ARMS A1..A4 -- os quatro casos da ordem, com os DETECTORES DE PRODUCAO
    (`PaintStall.observe`, `youtube_captions.cue_at/align_painted`).
  * ARM A5 -- REPLAY da janela congelada REAL (o fixture), amostra a amostra.
  * ARM A6 -- LIGACAO no shell, por AST: o caminho CDP pergunta ao detector e o
    detector passa por `_yt_decide` (o chao monotono).
  * ARM A7 -- CONTROLE: a MESMA faixa com a pintura a acompanhar o tempo nao
    pode produzir um unico `stale` (um detector que diz sempre "congelou"
    passaria A5 e e' um detector morto).
  * `--neg-arm` -- tres mutantes FOCAIS do proprio modulo: sem detector,
    congelado para sempre, faixa sempre a' frente. Cada um tem de derrubar o
    arm que o nomeia. rc=1 = apanhados (PASS); rc=3 = instrumento cego.

Exit: 0 = medido e verde; 1 = RED; 2 = falta o que medir; 3 = neg-arm cego.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEBVIEW = os.path.join(REPO, "app", "webview")
MONO = os.path.join(WEBVIEW, "youtube_monotonic.py")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
FIXTURE = os.path.join(HERE, "fixtures", "yt-paint-freeze-20261104.json")

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

#: As cues dos arms sinteticos. As duas primeiras sao o texto REAL que estava
#: congelado na janela capturada; a terceira dura 8 s de proposito -- e' o caso
#: que a histerese protege (cue longo nao e' congelamento).
CUES = [
    {"start": 10.0, "end": 14.0, "text": "I am kind of impressed."},
    {"start": 14.0, "end": 18.0, "text": "Are you E6 before the the rank up?"},
    {"start": 18.0, "end": 26.0, "text": "A long cue that lasts eight seconds flat."},
    {"start": 26.0, "end": 30.0, "text": "Then this sword is useless."},
    {"start": 40.0, "end": 44.0, "text": "Something much later in the video."},
]

FROZEN_ROWS = [">> I am kind of impressed.", "Are you E6 before the the rank up?"]
LONG_ROWS = ["A long cue that lasts eight seconds flat."]


def _load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Tripwire(list):
    """Uma sequencia de cues que GRITA se alguem a consultar.

    Existe porque "a pintura fresca manda e o relogio nao e' consultado" nao se
    prove com `stale == False`: um detector que lesse a faixa e devolvesse False
    passaria. Aqui, LER a faixa e' a falha.
    """

    def __iter__(self):
        raise AssertionError("a faixa foi consultada numa pintura fresca")

    def __len__(self):
        raise AssertionError("a faixa foi consultada numa pintura fresca")


# --------------------------------------------------------------------------
# A1..A4 -- os quatro casos da ordem
# --------------------------------------------------------------------------
def arm_cases(mono):
    out = []

    # A1 -- pintura congelada + relogio a andar + a FAIXA noutro cue: a faixa
    # ganha e o motivo e' `stale`.
    st = mono.PaintStall()
    v0 = st.observe(FROZEN_ROWS, 12.0, 0.0, CUES)
    v1 = st.observe(FROZEN_ROWS, 20.0, 8.0, CUES)
    cue_at = float((v1.get("cue") or {}).get("start", -1))
    out.append(("A1-frozen-clock-track-wins",
                v1.get("stale") is True and v1.get("served") == "track"
                and v1.get("why") == "stale" and cue_at == 18.0
                and float(((v1.get("painted_cue") or {}).get("start")) or -1) == 14.0,
                "primeiro=%s segundo=%s cue=%s (a faixa em t=20 e' 18.0, a "
                "pintura alinha em 14.0)" % (v0.get("why"), v1.get("why"), cue_at)))

    # A2 -- pintura congelada + relogio a andar + a MESMA cue: nada muda. Um
    # cue de 8 s nao e' um congelamento.
    st = mono.PaintStall()
    st.observe(LONG_ROWS, 19.0, 0.0, CUES)
    v = st.observe(LONG_ROWS, 25.5, 6.5, CUES)
    out.append(("A2-long-cue-is-not-stall",
                v.get("stale") is False and v.get("why") == "same-cue"
                and v.get("served") == "paint",
                "why=%s stale=%r (cue 18.0..26.0 com o relogio em 25.5)"
                % (v.get("why"), v.get("stale"))))

    # A3 -- pintura FRESCA: ela ganha e a faixa NAO e' consultada.
    st = mono.PaintStall()
    trip = Tripwire()
    try:
        v0 = st.observe(FROZEN_ROWS, 12.0, 0.0, trip)
        v1 = st.observe(LONG_ROWS, 13.0, 1.0, trip)
        consulted = False
    except AssertionError as exc:
        v0 = v1 = {}
        consulted = str(exc)
    out.append(("A3-fresh-paint-wins-no-clock",
                not consulted and v1.get("stale") is False
                and v1.get("why") == "paint-changed"
                and v1.get("served") == "paint",
                "faixa consultada=%r why=%s served=%s"
                % (consulted, (v1 or {}).get("why"), (v1 or {}).get("served"))))

    # A4 -- depois de 30 s de congelamento, a pintura volta numa linha
    # DISTINTA: ela recupera a autoridade no mesmo tick e continua a te-la.
    st = mono.PaintStall()
    st.observe(FROZEN_ROWS, 12.0, 0.0, CUES)
    v_stale = st.observe(FROZEN_ROWS, 42.0, 30.0, CUES)
    v_back = st.observe(LONG_ROWS, 43.0, 31.0, CUES)
    v_next = st.observe(LONG_ROWS, 43.1, 31.1, CUES)
    out.append(("A4-paint-regains-after-30s",
                v_stale.get("stale") is True
                and v_back.get("stale") is False
                and v_back.get("why") == "paint-changed"
                and v_next.get("stale") is False
                and v_next.get("served") == "paint",
                "congelada=%s voltou=%s seguinte=%s"
                % (v_stale.get("why"), v_back.get("why"), v_next.get("why"))))
    return out


# --------------------------------------------------------------------------
# A5 -- REPLAY da janela congelada REAL
# --------------------------------------------------------------------------
def arm_fixture(mono):
    with io.open(FIXTURE, encoding="utf-8") as fh:
        data = json.load(fh)
    samples = data.get("samples") or []
    cues = ((data.get("track") or {}).get("cues") or [])
    if not samples or not cues:
        return [("A5-fixture", False,
                 "fixture sem amostras (%d) ou sem faixa (%d)"
                 % (len(samples), len(cues)))]
    st = mono.PaintStall()
    keys = set()
    stale_at = None
    stale = 0
    paint_changed = 0
    cue_ok = 0
    for i, s in enumerate(samples):
        rows = s.get("rows") or []
        keys.add(mono.paint_signature(rows))
        v = st.observe(rows, s.get("t"), s.get("wall"), cues)
        if v.get("why") == "paint-changed":
            paint_changed += 1
        if v.get("stale"):
            stale += 1
            if stale_at is None:
                stale_at = i
            if v.get("cue") is not None and float(v["cue"]["start"]) != float(
                    ((v.get("painted_cue") or {}).get("start")) or -1):
                cue_ok += 1
    ts = [s.get("t") for s in samples if isinstance(s.get("t"), (int, float))]
    span = (ts[-1] - ts[0]) if len(ts) > 1 else 0.0
    ok = (len(keys) == 1 and stale > 0 and paint_changed == 0
          and stale_at is not None and stale_at > 0 and cue_ok > 0)
    return [("A5-real-frozen-window",
             ok,
             "%d amostras, relogio +%.1f s, %d pintura(s) distinta(s), "
             "primeiro stale na amostra %s, %d amostras stale, %d com a cue da "
             "FAIXA (nao a pintada), %d pintura(s) nova(s)"
             % (len(samples), span, len(keys), stale_at, stale, cue_ok,
                paint_changed))]


# --------------------------------------------------------------------------
# A8/A9 -- O METODO VIVO do shell, sobre a mesma janela real
# --------------------------------------------------------------------------
class _FakeThread:
    """O `youtube_track_thread` como o shell o ve': `current` e `request`."""

    def __init__(self, track):
        self.track = track
        self.asked = []

    def current(self, video_id):
        return self.track

    def request(self, video_id, painted=None):
        self.asked.append((video_id, len(painted or [])))
        return self.track


def _stub_watcher(sw, track):
    import types
    obj = types.SimpleNamespace()
    obj.shell = types.SimpleNamespace(youtube_track_thread=_FakeThread(track))
    obj.yt_serve_floor = None
    obj.yt_reason = ''
    obj.yt_cue = ''
    obj.yt_stale_logged = None
    obj._yt_anchor = None
    obj._yt_track = None
    obj._yt_diag = {}
    for name in ('_yt_decide', '_yt_advance', '_yt_forget', '_yt_lines',
                 '_yt_paint_stall'):
        setattr(obj, name, getattr(sw.ExternalCaptionWatcher, name).__get__(obj))
    return obj


def arm_real_method():
    try:
        import sotto_webview as sw
    except Exception as exc:              # noqa: BLE001
        return [("A8-real-method", False, "import do shell falhou: %r" % (exc,))]
    with io.open(FIXTURE, encoding="utf-8") as fh:
        data = json.load(fh)
    samples = data.get("samples") or []
    cues = ((data.get("track") or {}).get("cues") or ())
    if not samples or not cues:
        return [("A8-real-method", False, "fixture sem amostras/faixa")]
    try:
        import youtube_captions
    except Exception as exc:              # noqa: BLE001
        return [("A8-real-method", False, "sem youtube_captions: %r" % (exc,))]
    track = {"state": "has-track", "lang": "en-orig", "cues": cues}
    obj = _stub_watcher(sw, track)
    first = None
    first_done = False
    stale = 0
    gaps = 0
    served_seq = []
    reason_ok = 0
    cue_ok = 0
    for s in samples:
        rows = s.get("rows") or []
        snap = {"t": s.get("t"), "stamp": s.get("wall"), "rows": rows}
        reply = obj._yt_paint_stall(snap, rows, "r-AsGBMDI6c")
        if not first_done:
            first_done = True
            first = reply
        if reply is None:
            continue
        if not reply[0]:
            gaps += 1
            continue
        stale += 1
        served_seq.append(obj.yt_serve_floor)
        if obj.yt_reason == "painted-stale:clock":
            reason_ok += 1
        cue = youtube_captions.cue_at(cues, obj.yt_serve_floor)
        if cue is not None and str(cue.get("text") or "").strip() == obj.yt_cue:
            cue_ok += 1
    mono_ok = all(b is not None and a is not None and b >= a - 0.001
                  for a, b in zip(served_seq, served_seq[1:])) if served_seq else False
    out = [("A8-real-method-serves-track",
            first is None and stale > 0 and reason_ok == stale
            and cue_ok == stale and mono_ok,
            "primeiro tick=%r, %d tick(s) servidos pela FAIXA, %d com "
            "`painted-stale:clock`, %d com o texto do cue do instante, %d "
            "lacuna(s) da faixa servidas como nada, chao "
            "monotono=%s" % ("paint" if first is None else "track", stale,
                             reason_ok, cue_ok, gaps, mono_ok))]
    # A9 -- sem a faixa (a testemunha nao esta'): pede-se UMA vez por
    # assinatura, nunca uma vez por tick (745 ticks nesta janela).
    obj2 = _stub_watcher(sw, None)
    for s in samples:
        rows = s.get("rows") or []
        obj2._yt_paint_stall({"t": s.get("t"), "stamp": s.get("wall"),
                              "rows": rows}, rows, "r-AsGBMDI6c")
    asks = obj2.shell.youtube_track_thread.asked
    out.append(("A9-asks-track-once-per-paint",
                len(asks) == 1,
                "%d pedido(s) da faixa (a testemunha) em %d tick(s) com a "
                "mesma pintura: %r" % (len(asks), len(samples), asks[:3])))
    return out


# --------------------------------------------------------------------------
# A7 -- CONTROLE: a mesma faixa, a pintura a acompanhar o relogio
# --------------------------------------------------------------------------
def arm_control(mono):
    with io.open(FIXTURE, encoding="utf-8") as fh:
        data = json.load(fh)
    cues = ((data.get("track") or {}).get("cues") or [])
    try:
        import youtube_captions
    except Exception as exc:              # noqa: BLE001
        return [("A7-control-paint-follows", False, "sem youtube_captions: %r" % (exc,))]
    st = mono.PaintStall()
    stale = 0
    n = 0
    t = 780.0
    while t < 840.0:
        cue = youtube_captions.cue_at(cues, t)
        if cue is not None:
            n += 1
            v = st.observe([str(cue.get("text") or "")], t, t, cues)
            if v.get("stale"):
                stale += 1
        t += 0.25
    return [("A7-control-paint-follows", stale == 0 and n > 100,
             "%d tick(s) com a pintura a acompanhar a faixa: %d stale "
             "(um detector que diga sempre 'congelou' morre aqui)"
             % (n, stale))]


# --------------------------------------------------------------------------
# A6 -- a LIGACAO no shell, por AST
# --------------------------------------------------------------------------
def _func_calls(tree, name):
    """[(lineno, nome_dotted)] das chamadas DENTRO da funcao `name`."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != name:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                parts = []
                cur = sub.func
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                out.append((getattr(sub, "lineno", 0), ".".join(reversed(parts)),
                            node.name))
    return out


def arm_wiring(path):
    with io.open(path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    fast = _func_calls(tree, "_yt_cdp_fast_lines")
    stall = _func_calls(tree, "_yt_paint_stall")
    fast_names = [n for _ln, n, _f in fast]
    stall_names = [n for _ln, n, _f in stall]
    out = []
    out.append(("A6-cdp-path-asks-detector",
                "self._yt_paint_stall" in fast_names,
                "chamadas em `_yt_cdp_fast_lines`: %r" % (fast_names,)))
    out.append(("A6-detector-uses-paintstall",
                any(n.endswith(".PaintStall") for n in stall_names),
                "chamadas em `_yt_paint_stall`: %r" % (stall_names,)))
    out.append(("A6-detector-serves-through-floor",
                "self._yt_decide" in stall_names,
                "o instante servido passa por `_yt_decide`: %s"
                % ("sim" if "self._yt_decide" in stall_names else "NAO")))
    out.append(("A6-log-line-written",
                "YOUTUBE_PAINT_STALE t=" in src
                and "painted_age_s=" in src,
                "a linha `YOUTUBE_PAINT_STALE t=.. painted_age_s=..` existe "
                "no shell: %s" % ("sim" if "YOUTUBE_PAINT_STALE t=" in src else "NAO")))
    return out


# --------------------------------------------------------------------------
# OS MUTANTES do braco negativo -- o PROPRIO modulo, com uma regra arrancada
# --------------------------------------------------------------------------
MUTANTS = [
    ("sem-detector", "A1-frozen-clock-track-wins", [
        ("        if age <= self.stale_s:\n",
         "        if age <= self.stale_s or True:\n")]),
    ("congelado-para-sempre", "A4-paint-regains-after-30s", [
        ("            self.asked = None\n            self.stale = False\n",
         "            self.asked = None\n")]),
    ("faixa-sempre-a-frente", "A3-fresh-paint-wins-no-clock", [
        ("            return self.verdict(False, 'paint-changed' if not first\n",
         "            return self.verdict(True, 'paint-changed' if not first\n")]),
]


def run_arms(mod):
    arms = arm_cases(mod) + arm_fixture(mod) + arm_control(mod)
    return dict((name, (ok, detail)) for name, ok, detail in arms)


def neg_arm():
    with io.open(MONO, encoding="utf-8") as fh:
        src = fh.read()
    tmpd = tempfile.mkdtemp(prefix="ythidden-",
                            dir=os.environ.get("TMPDIR") or None)
    blind = []
    try:
        for label, target, patches in MUTANTS:
            mut = src
            applied = 0
            for old, new in patches:
                if old not in mut:
                    blind.append("%s: patch nao aplica (o codigo mudou)" % label)
                    continue
                mut = mut.replace(old, new, 1)
                applied += 1
            mpath = os.path.join(
                tmpd, "ytmono_mut_%s.py" % label.replace("-", "_"))
            with io.open(mpath, "w", encoding="utf-8") as fh:
                fh.write(mut)
            mod = _load_module(mpath, "ytmono_mut_" + label.replace("-", "_"))
            arms = run_arms(mod)
            ok, detail = arms.get(target, (None, "arm ausente"))
            print("%-4s mutant=%-24s arm=%-30s %s"
                  % ("RED" if not ok else "GREEN", label, target, detail))
            if ok:
                blind.append("%s: o arm %s continuou GREEN -- o mutante passou"
                             % (label, target))
        if blind:
            print("NEG-ARM FAIL -- o instrumento esta' CEGO em %d caso(s):"
                  % len(blind))
            for line in blind:
                print("  - %s" % line)
            return 3
        print("NEG-ARM PASS -- RED as designed: 3 de 3 mutantes apanhados "
              "(sem detector, congelado para sempre, faixa sempre a' frente)")
        return 1
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def main(argv=None):
    global FIXTURE
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--neg-arm", action="store_true",
                    help="prova que o instrumento APANHA: cada mutante do "
                         "proprio detector tem de derrubar o arm que o nomeia. "
                         "rc=1 = apanhados; rc=3 = cego.")
    ap.add_argument("--fixture", default=FIXTURE)
    args = ap.parse_args(argv)

    FIXTURE = args.fixture
    for path in (MONO, SHELL, FIXTURE):
        if not os.path.exists(path):
            print("YOUTUBE-HIDDEN-CLOCK NO-VERDICT -- falta %s" % path)
            return 2

    if args.neg_arm:
        return neg_arm()

    mono = _load_module(MONO, "youtube_monotonic_live")
    results = arm_cases(mono) + arm_fixture(mono) + arm_wiring(SHELL) \
        + arm_real_method() + arm_control(mono)

    failed = 0
    for name, ok, detail in results:
        print("%-4s %-34s %s" % ("PASS" if ok else "FAIL", name, detail))
        if not ok:
            failed += 1
    total = len(results)
    if failed:
        print("YOUTUBE-HIDDEN-CLOCK VERDICT RED -- %d PASS / %d FAIL"
              % (total - failed, failed))
        return 1
    print("YOUTUBE-HIDDEN-CLOCK VERDICT GREEN -- %d PASS / 0 FAIL "
          "(STALE_S=%.2f s; a faixa e a segunda testemunha, nunca um "
          "temporizador)" % (total, mono.STALE_S))
    return 0


if __name__ == "__main__":
    sys.exit(main())
