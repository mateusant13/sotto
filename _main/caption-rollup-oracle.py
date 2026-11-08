#!/usr/bin/env python3
"""O ROLL-UP da legenda, medido em PIXEL: a linha velha SOBE, a caixa nao muda.

O oraculo do `caption_overlay` para a ordem do dono de 2026-11-08, verbatim:
*"quero a animacao de quando comeca uma linha nova e a outra linha vai pra cima"*.
ELE NAO ABRE JANELA: monta o bitmap pelo mesmo `_layout`/`_premultiplied_bitmap`
que o overlay usa, logo o que ele aprova e' o pixel que o dono veria.


Nao abre janela nenhuma: monta o bitmap pelo MESMO `_layout`/`_premultiplied_bitmap`
que o overlay usa. A pergunta do dono (2026-11-08): *"quero a animacao de quando
comeca uma linha nova e a outra linha vai pra cima"*.

A PROVA E' IGUALDADE DE BITMAP, nao contagem de tinta:
  A1 antes da linha nova, o desenho e' IDENTICO a renderizar `[linha1, linha2]`
     parado;
  A2 a meio da transicao o deslocamento esta' estritamente entre 0 e 1 e o
     desenho NAO e' igual nem ao de antes nem ao de depois -- e' um quadro
     intermediario de verdade (a linha 1 meio fora pelo topo, a nova meio dentro);
  A3 terminado o *exit*, o desenho e' IDENTICO a renderizar `[linha2, linha3]`
     parado -- a linha 1 saiu, e as duas que ficam estao' exactamente onde
     estariam sem animacao nenhuma;
  A4 a ALTURA do bitmap e' a mesma nos tres instantes.
  NEG (`--neg-arm`): desliga `roll_progress` e exige que A2 caia -- o quadro do
  meio fica com a linha 1 INTEIRA no topo, que e' exactamente o defeito que o
  dono descreveu (a linha velha nao sobe).

AS ARMS B* CORREM O `_display` REAL DO OVERLAY, com um `LiveRows` real por tras
(caminho do ASR): A2 sozinho julga a aritmetica, e aritmetica verde com o overlay
a descartar a linha que sai e' o defeito que existia (o `_display` filtrava
`m["exiting"]` e forçava `_roll = 0`). B1 = tres linhas desenhadas, B2 = o
deslocamento esta' estritamente entre 0 e 1 nesse mesmo chamado, B3 = a linha do
TOPO e' a que esta' a sair, B4 = sem linha a sair o deslocamento e' zero.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "webview"))

import youtube_reveal  # noqa: E402

import caption_overlay  # noqa: E402  (o `_display` REAL, sem abrir janela)


LINE1 = "line one is here"
LINE2 = "the second line"
LINE3 = "and the new third"


def _rows():
    return [
        {"text": LINE1, "start": 0.0, "end": 2.0, "words": [], "cap": None},
        {"text": LINE2, "start": 1.0, "end": 2.6, "words": [], "cap": None},
        {"text": LINE3, "start": 2.0, "end": 4.0, "words": [], "cap": None},
    ]


def _bits(bmp, height):
    from System.Drawing.Imaging import ImageLockMode, PixelFormat
    from System.Drawing import Rectangle
    import ctypes

    data = bmp.LockBits(Rectangle(0, 0, bmp.Width, height), ImageLockMode.ReadOnly,
                        PixelFormat.Format32bppPArgb)
    try:
        stride = abs(int(data.Stride))
        return ctypes.string_at(int(data.Scan0.ToInt64()), stride * height)
    finally:
        bmp.UnlockBits(data)


def _render(lines, roll, png=None):
    """O bitmap de `lines` com `roll` de deslocamento, pelo caminho REAL."""
    import overlay_paint

    text = "\n".join(lines)
    cur, prev, width, height, _s = overlay_paint._layout(
        text, "", 1.0, 1920, None, rows=2)
    bmp = overlay_paint._premultiplied_bitmap(cur, prev, width, height, 1.0, None,
                                              [255] * len(cur), roll=roll)
    raw = _bits(bmp, height)
    if png:
        try:
            from System.Drawing.Imaging import ImageFormat
            Path(png).parent.mkdir(parents=True, exist_ok=True)
            bmp.Save(png, ImageFormat.Png)
        except Exception:
            pass
    return hashlib.sha256(raw).hexdigest()[:16], height, raw


def _top_ink(raw, width, height):
    """Tinta do primeiro terco de altura (a banda onde a linha 1 vive)."""
    stride = len(raw) // height
    third = height // 3
    total = 0
    for y in range(third):
        base = y * stride
        for x in range(3, stride, 4):
            total += raw[base + x]
    return total


def _live_display(now):
    """O `_display` REAL sobre um `LiveRows` real -- o caminho do ASR inteiro.

    Devolve `(texto, alfas, roll)` do MESMO chamado que o overlay faz no timer.
    """
    live = youtube_reveal.LiveRows(wrap=lambda text: [text])
    live.push(LINE1, now - 2.40)
    live.push(LINE2, now - 1.20)
    live.push(LINE3, now - 0.20)
    obj = object.__new__(caption_overlay.NativeCaptionOverlay)
    obj._cue = None
    obj._live = live
    obj._row_alphas = None
    obj._roll = 0.0
    text, alphas = obj._display()
    return text, alphas, obj._roll


def _live_settled(now):
    """Duas linhas, nenhuma a sair: o deslocamento tem de ser ZERO."""
    live = youtube_reveal.LiveRows(wrap=lambda text: [text])
    live.push(LINE1, now - 1.20)
    live.push(LINE2, now - 0.20)
    obj = object.__new__(caption_overlay.NativeCaptionOverlay)
    obj._cue = None
    obj._live = live
    obj._row_alphas = None
    obj._roll = 0.0
    text, alphas = obj._display()
    return text, alphas, obj._roll


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="caption-rollup-probe")
    parser.add_argument("--neg-arm", action="store_true",
                        help="desliga o deslocamento e exige que A2 caia")
    parser.add_argument("--png", default="", help="prefixo de PNGs (debug visual)")
    args = parser.parse_args(argv)

    if args.neg_arm:
        youtube_reveal.roll_progress = lambda *a, **k: 0.0

    ref12, _, _ = _render([LINE1, LINE2], 0.0)
    ref23, _, _ = _render([LINE2, LINE3], 0.0)

    moments = (("antes", 1.95), ("meio", 2.20), ("depois", 2.60))
    seen = {}
    for label, t in moments:
        marks = youtube_reveal.frame(_rows(), t, 2, youtube_reveal.ROLLUP_ROWS,
                                     youtube_reveal.EXIT_S)
        roll = 0.0
        if len(marks) > 2 and marks[0].get("displaced_at") is not None:
            roll = youtube_reveal.roll_progress(t - float(marks[0]["displaced_at"]),
                                                youtube_reveal.EXIT_S)
        lines = [m["text"] for m in marks]
        digest, height, raw = _render(
            lines, roll, (args.png + "-%s.png" % label) if args.png else None)
        stride = len(raw) // height
        seen[label] = {"digest": digest, "height": height, "roll": roll,
                       "lines": len(lines), "top": _top_ink(raw, stride, height)}
        print("%-7s t=%.2f roll=%.3f linhas=%d altura=%d digest=%s topo=%d"
              % (label, t, roll, len(lines), height, digest, seen[label]["top"]),
              flush=True)

    a1 = seen["antes"]["digest"] == ref12
    a2 = (0.0 < seen["meio"]["roll"] < 1.0
          and seen["meio"]["digest"] not in (ref12, ref23))
    a3 = seen["depois"]["digest"] == ref23
    a4 = len({v["height"] for v in seen.values()}) == 1
    # ── B: o `_display` REAL, no caminho do ASR ──────────────────────────────
    import time as _time
    now = _time.monotonic()
    text, alphas, live_roll = _live_display(now)
    rolled = str(text or "").rstrip("\n").split("\n")
    text2, _alphas2, settled_roll = _live_settled(now)
    # A ultima linha esta' a MEIO de ser revelada (0,2 s depois de comecar, e o
    # motor revela palavra a palavra): o que a arm exige e' que ela EXISTA como
    # terceira linha, comecada, e que a que esta' a sair seja a de cima.
    b1 = (len(rolled) == 3 and rolled[0] == LINE1
          and rolled[1] == LINE2 and rolled[2].startswith("and the new"))
    b2 = 0.0 < live_roll < 1.0
    b3 = bool(alphas) and len(alphas) == len(rolled) and all(a == 255 for a in alphas)
    b4 = settled_roll == 0.0 and len(str(text2 or "").rstrip("\n").split("\n")) == 2
    print("live   linhas=%d roll=%.3f alfas=%s | parado linhas=%d roll=%.3f"
          % (len(rolled), live_roll, alphas,
             len(str(text2 or "").rstrip("\n").split("\n")), settled_roll), flush=True)

    checks = (("A1 antes == [linha1,linha2] parado", a1),
              ("A2 meio e' quadro intermediario", a2),
              ("A3 depois == [linha2,linha3] parado", a3),
              ("A4 altura da caixa constante", a4),
              ("B1 _display desenha as TRES linhas", b1),
              ("B2 _display desloca a que sai", b2),
              ("B3 alfa 255 nas tres (sem dissolve)", b3),
              ("B4 sem linha a sair, roll == 0", b4))
    for name, ok in checks:
        print("%-38s -> %s" % (name, "PASS" if ok else "FAIL"))
    if args.neg_arm:
        caught = (not a2) and (not b2)
        print("NEG-ARM: %s (A2 caiu=%s, B2 caiu=%s com o deslocamento desligado)"
              % ("PASS" if caught else "FAIL", not a2, not b2))
        return 1 if caught else 0
    ok = all(value for _name, value in checks)
    print("VERDICT: %s (%d/%d)" % ("PASS" if ok else "FAIL",
                                   sum(1 for _n, v in checks if v), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
