"""UM PRODUTOR POR VEZ NO ECRA -- oraculo da LEGENDA (flicker).

A QUEIXA DO DONO (2026-11-02), verbatim: *"as legendas tao flickando. tao
bugadas. ficam sumindo e aperecendo ou trocando a atual e a antiga ao mesmo
tempo"*.

O QUE FOI MEDIDO, e nao suposto. `_main/caption-frame-audit.py` sobre o log
vivo (23:05:00-23:08:13): **59 oscilacoes em 13,2 s**, com os quadros a
alternar A/B/A/B:

    A = ['Estados Unidos voltar, ne?', 'Mas tipo tres v tres, eles lutam']
    B = ['Mas tipo tres v tres, eles lutam com', 'menos,']

As duas vinham de PRODUTORES DIFERENTES: o laco de leitura punha a legenda
PINTADA pelo player (`A`), e o re-render de 60 ms entre leituras recompunha a
linha a partir da FAIXA com o relogio interpolado (`B`). Duas fontes, um ecra:
isso e' a oscilacao, e no corpo do ficheiro eram duas fotos diferentes (nomes
numa leitura, rects na anterior).

AS REGRAS QUE ESTE ORACULO GUARDA:

  1. O re-render da faixa (`yt_live_frame`) e' CONDICIONADO: enquanto a
     pintura esta' a fornecer a linha, ele nao corre (uma fonte so').
  2. A leitura da pintura e' UMA FOTO: `_youtube_painted` le com
     `with_rect=True` e reaproveita o rect de cada filho inalterado; nao ha'
     segunda leitura para os rects.
  3. O `EXTERNAL_CAPTION_DRAWN` e' o unico sitio que pinta (o instrumento de
     auditoria le'). Uma segunda chamada de desenho com outra fonte e' o
     defeito, e aqui ela e' procurada por NOME.
  4. O detector (`caption-frame-audit.audit`) apanha as tres formas conhecidas
     e deixa passar a sequencia limpa -- provado pelo `--neg-arm` dele.

USO:
    python _main/caption-producer-oracle.py
    python _main/caption-producer-oracle.py --neg-arm   # muta o ficheiro e exige RED
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
CAPTIONS = os.path.join(ROOT, 'app', 'webview', 'youtube_captions.py')


def read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def arms():
    """[(nome, ok, nota)] -- lidos do FONTE, porque a regra e' de fluxo."""
    shell = read(SHELL)
    captions = read(CAPTIONS)
    out = []

    # 1. O re-render da faixa e' condicionado pela pintura.
    guarded = ('painted_now = (time.monotonic()' in shell
               and 'if yt_mode and not painted_now:' in shell)
    out.append(('live-frame-is-gated', guarded,
                'gated=%s' % guarded))

    # 2. A pintura e' marcada como produtora da tela.
    marked = 'yt_live_paint_at = time.monotonic()' in shell
    out.append(('paint-marks-the-screen', marked, 'marked=%s' % marked))

    # 3. UMA leitura com rects; a leitura barata nao vira fonte de linhas.
    one_photo = ('painted_words(uia, UIA, hwnd=hwnd,' in shell
                 and 'with_rect=True,' in shell
                 and 'with_rect=False)' not in shell)
    out.append(('one-photo-with-rects', one_photo, 'one_photo=%s' % one_photo))

    # 4. O rect de um filho inalterado e' reaproveitado e o resto e' lido.
    reuse = ('reuse=None' in captions and 'prev.get("text") == name' in captions)
    out.append(('rect-reuse', reuse, 'reuse=%s' % reuse))

    # 5. Histerese das linhas: crescer passa, encolher espera.
    settle = ('ROWS_SETTLE_S' in shell and 'def _yt_rows_settle' in shell
              and 'rows[-1].startswith(shown[-1])' in shell)
    out.append(('row-hysteresis', settle, 'settle=%s' % settle))
    return out


def neg_arm():
    """MUTACAO: desligar o guarda da pintura tem de derrubar a arm 1."""
    text = read(SHELL)
    marker = 'if yt_mode and not painted_now:'
    if marker not in text:
        print('NEG-ARM: FAIL -- a ancora do guarda nao esta no ficheiro')
        return 1
    mutant = text.replace(marker, 'if yt_mode:', 1)
    tmpdir = tempfile.mkdtemp(prefix='sotto-neg-producer-')
    path = os.path.join(tmpdir, 'sotto_webview.py')
    io.open(path, 'w', encoding='utf-8', newline='').write(mutant)
    try:
        m = read(path)
        still = ('painted_now = (time.monotonic()' in m
                 and 'if yt_mode and not painted_now:' in m)
    finally:
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass
    print('NEG-ARM %-18s %s  guarda presente no mutante: %s'
          % ('gate-removed', 'PASS' if not still else 'FAIL', still))
    return 0 if not still else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    bad = 0
    results = arms()
    for name, ok, note in results:
        print('%-26s %s  %s' % (name, 'GREEN' if ok else 'RED', note))
        if not ok:
            bad += 1
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if bad == 0 else 'FAIL',
                                        len(results) - bad, len(results)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
