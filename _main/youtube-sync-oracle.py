"""O PORTAO DA SINCRONIA -- a legenda do YouTube e 1:1 em texto, linhas e timing.

O DONO, 2026-10-22, verbatim:
    *"nao para ate tu arrumar isso. … se eu ver uma porra de uma legenda
    renderizando na minha tela que e diferente da que ta do youtube atual, fora de
    sync, nao 1:1…"*

O QUE ESTE FICHEIRO JULGA, e por que cada braco existe:

  ARM 1  A JANELA. Com o payload real (`_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`),
         em cada instante amostrado, `youtube_window.live_lines` devolve exactamente
         as linhas que o payload diz que estao vivas -- e devolve DUAS em 94 % do
         video. Uma linha so e o defeito que ele fotografou.
  ARM 2  O FANTASMA. `youtube_captions._rendered` recusa um elemento fora do ecra ou
         com rectangulo vazio. Medido 2026-10-22: 400 amostras do browser com a
         legenda VAZIA e a app a contar 8 palavras pintadas (a linha de antes, que
         ficou na arvore de acessibilidade depois de deixar de ser desenhada). Sem
         esta recusa a app mostra essa linha no segundo errado, para sempre.
  ARM 3  O CAMINHO VIVO CHAMA AS DUAS. As duas verdades acima nao servem de nada se o
         shell continuar a devolver `[text]` (um cue). O braco le `sotto_webview.py`
         por AST/texto e exige a chamada a `_yt_lines` nos DOIS sitios que devolvem
         legenda do YouTube.
  ARM 4  O HISTORICO NAO REPETE. `youtube_window.window_key` muda 19 vezes em 339
         amostras -- se mudasse em cada poll, cada poll era uma linha nova no
         historico (a mesma frase seis vezes).

BRAcO NEGATIVO (`--neg-arm`): janela forcada a UMA linha e `_rendered` forcado a
dizer sempre que sim. ARM 1, ARM 2 e ARM 4 teem de ficar VERMELHOS e o processo sai 1
POR DESENHO.

NAO LANCA NADA -- le ficheiros e corre python puro.

    python _main\\youtube-sync-oracle.py
    python _main\\youtube-sync-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")
STEP = 0.1


def rows_of(doc):
    out = []
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict) or ev.get("aAppend"):
            continue
        text = "".join((s.get("utf8") or "") for s in (ev.get("segs") or []) if isinstance(s, dict))
        if not text.strip():
            continue
        start = float(ev.get("tStartMs") or 0) / 1000.0
        out.append({"start": start,
                    "end": start + float(ev.get("dDurationMs") or 0) / 1000.0,
                    "text": text})
    return out


class FakeRect(object):
    def __init__(self, w, h):
        self.left, self.top, self.right, self.bottom = 10, 10, 10 + w, 10 + h


class FakeElement(object):
    """Um elemento de automacao falso: so o que `_rendered` le.

    `explode=True` simula um elemento cujo peer de automacao morreu -- a leitura do
    `Current*` levanta. O filtro tem de responder "nao desenhado", nao propagar.
    """

    def __init__(self, offscreen=False, w=300, h=40, explode=False):
        self._offscreen = offscreen
        self._rect = FakeRect(w, h)
        self._explode = explode

    @property
    def CurrentIsOffscreen(self):
        if self._explode:
            raise RuntimeError("no automation peer")
        return self._offscreen

    @property
    def CurrentBoundingRectangle(self):
        if self._explode:
            raise RuntimeError("no automation peer")
        return self._rect


def main(argv=None):
    ap = argparse.ArgumentParser(description="1:1 da legenda do YouTube: janela, fantasma, chamadas")
    ap.add_argument("--neg-arm", action="store_true", help="muta a janela e o filtro (tem de dar vermelho)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import youtube_captions as yc
    import youtube_window as yw

    capacity = 1 if args.neg_arm else 2
    rendered = (lambda el: True) if args.neg_arm else yc._rendered

    doc = json.loads(io.open(FIXTURE, encoding="utf-8").read())
    rows = rows_of(doc)
    cues = yc.parse_json3(io.open(FIXTURE, encoding="utf-8").read())
    end = max(r["end"] for r in rows)

    fails = []
    checks = 0

    def check(name, ok, detail=""):
        nonlocal checks
        checks += 1
        print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
        if not ok:
            fails.append(name)
        return ok

    print("youtube-sync-oracle%s" % (" -- NEG-ARM" if args.neg_arm else ""))
    print("  fixture: %s (%d linhas)" % (os.path.basename(FIXTURE), len(rows)))
    print("")

    # ---------------- ARM 1 ----------------
    print("ARM 1  a janela e a do payload, em cada instante")
    bad = []
    two = 0
    n = 0
    t = 0.0
    while t < end:
        want = [r["text"] for r in rows if r["start"] <= t < r["end"]][-capacity:]
        got = yw.live_lines(cues, t, capacity)
        if len(want) >= 2:
            two += 1
        n += 1
        if want != got:
            bad.append((round(t, 2), want, got))
        t += STEP
    check("1.1 %d instantes concordam" % n, not bad,
          "" if not bad else "primeiro divergente t=%.2f want=%r got=%r" % (bad[0][0], bad[0][1], bad[0][2]))
    check("1.2 ha instantes com DUAS linhas (o ecra do YouTube)", two > 0,
          "%d de %d (%.0f%%)" % (two, n, 100.0 * two / n))
    print("")

    # ---------------- ARM 2 ----------------
    print("ARM 2  um elemento que nao esta a ser desenhado nao conta palavras")
    check("2.1 um elemento DESENHADO passa", rendered(FakeElement()) is True,
          "offscreen=False rect=300x40")
    check("2.2 OFFSCREEN e recusado", rendered(FakeElement(offscreen=True)) is False,
          "offscreen=True")
    check("2.3 rectangulo VAZIO e recusado", rendered(FakeElement(w=0, h=0)) is False,
          "rect=0x0")
    check("2.4 sem peer de automacao e recusado (nao rebenta)",
          rendered(FakeElement(explode=True)) is False, "CurrentIsOffscreen levanta")
    print("")

    # ---------------- ARM 3 ----------------
    print("ARM 3  o caminho vivo devolve a JANELA, nos dois sitios")
    src = io.open(SHELL, encoding="utf-8", newline="").read()
    check("3.1 existe o helper _yt_lines", "def _yt_lines(self, track, t)" in src)
    check("3.2 o helper usa a JANELA do youtube_window, com a revelacao do YouTube",
          "youtube_window.revealed_lines(cues, t, 2)" in src)
    single = src.count("[('external:youtube:track', [text])]")
    check("3.3 nenhum sitio devolve um cue so", single == 0,
          "%d sitio(s) ainda com [text]" % single)
    #: TRES sitios desde 2026-10-23, e DOIS deles desde 2026-10-29. O numero
    #: antigo era PIN 3: `painted` (alinhamento por texto), `painted-other-track:clock`
    #: e o `has-cue` -- os dois ultimos escolhem a cue pelo RELOGIO e por isso
    #: passam pela janela de duas linhas de `_yt_lines`. A revelacao palavra-a-
    #: palavra de 2026-10-29 trocou o ramo `painted` por
    #: `youtube_reveal.window_by_paint`, que e' a MESMA janela de duas linhas
    #: com a linha viva cortada no que o player ja pintou -- ou seja o invariante
    #: que este braco guarda ("nenhum sitio devolve um cue so") continua a valer,
    #: mas o NOME da funcao mudou, e um pin no numero 3 media o nome e nao o
    #: invariante. ATUALIZADO, nao re-fixado: o braco passa a exigir as DUAS
    #: chamadas a `_yt_lines` E a `window_by_paint`, e continua a exigir zero
    #: sitios com `[text]` sozinho (3.3).
    # 3.4 RE-ANCORADO A 2026-10-30, com a razao escrita: a contagem era `== 2` e
    # mede **3** hoje. Os dois sitios originais continuam la' (o `painted` e o
    # `external:youtube:track`), e o terceiro e' `_yt_anchor_estimate`, que monta as
    # linhas pelo relogio estimado quando o UIA para de responder -- um caminho que
    # existe para nao inventar revelacao nenhuma. O que este braco guarda agora e' a
    # PROPRIEDADE (todo o sitio do relogio pede as linhas a `_yt_lines`, nada as
    # constroi a mao), e o numero fica publicado como INFORMACAO.
    _sites = src.count("self._yt_lines(track,")
    check("3.4 todo o sitio do relogio usa _yt_lines (>=2, hoje 3)",
          _sites >= 2 and "lines = self._yt_lines(track," in src,
          "count=%d" % _sites)
    check("3.5 o sitio pintado usa a janela revelada pela PINTURA",
          "youtube_reveal.window_by_paint(" in src,
          "window_by_paint ausente: o ramo `painted` voltou a um relogio estimado")
    print("")

    # ---------------- ARM 4 ----------------
    print("ARM 4  a chave so muda quando a janela muda")
    keys = []
    t = 0.0
    while t < end:
        keys.append(yw.window_key(yw.live_lines(cues, t, capacity)))
        t += STEP
    check("4.1 a janela muda 19 vezes, nao uma por poll",
          len(set(keys)) < len(keys) / 2,
          "distinct=%d de %d amostras" % (len(set(keys)), len(keys)))
    print("")

    verdict = "PASS" if not fails else "FAIL"
    print("BATTERY-VERDICT youtube-sync-oracle %s  checks=%d fail=%d" % (verdict, checks, len(fails)))
    for name in fails:
        print("  RED: %s" % name)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
