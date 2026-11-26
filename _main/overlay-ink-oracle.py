# NO-BUG: Oracle: a legenda NATIVA tem de PINTAR TINTA do texto servido -- e nao so'
#        uma placa vazia com o texto certo no log. O bitmap e' lido fora do ecra, do
#        caminho REAL de desenho (GDI+), sem janela e sem tocar no ecra do dono.
#        Capacidade pedida pelo dono (A3, metade dos PIXEIS); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: the pixels, read off-screen from the real drawing path.

THE HOLE THIS CLOSES. Every caption gate up to now agreed on the TEXT -- what the
shell decided to paint, what the log records, what the history keeps. None of them
looked at the raster. A theme that paints the plate but drops the glyph, a wrap
that measures one face and draws another, or a paint cache that hands back another
line's raster would keep every one of those gates green while the owner sees an
empty box.

HOW IT READS PIXELS WITHOUT A WINDOW. `overlay_paint._layout` decides the box and
`overlay_paint._premultiplied_bitmap` draws it -- the same two functions
`caption_overlay` calls, through GDI+. The Bitmap object is inspected pixel by
pixel and disposed; no `CreateWindowExW`, no layered window, nothing on his
screen. With no plate in the theme, every pixel with alpha is GLYPH ink, which is
what makes the counts below mean something.

ARMS
  a INK-PRESENT     -- the owner's own line ("Still can't really pinpoint") lays
                       down ink above a floor;
  b INK-FOLLOWS-TEXT-- "I" vs "MMMMMMMM" widens the ink box, so the renderer is
                       drawing the text it was given;
  c TEXTS-DIFFER    -- two different sentences of the same length produce
                       different rasters (a stale raster served for the wrong
                       line is the failure this catches);
  d EMPTY-NO-INK    -- an empty caption lays down no ink at all;
  e CACHE-STABLE    -- A, then B, then A again: the third raster equals the
                       first and differs from the second, so the cache keys on
                       the text.

Usage:
  py -3 _main/overlay-ink-oracle.py            # rc 0 = every arm holds
  py -3 _main/overlay-ink-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
PAINT = os.path.join(WEBVIEW, 'overlay_paint.py')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

SCALE = 2.0
WORK_WIDTH = 1920
INK_FLOOR = 100          # PIXEIS AMOSTRADOS (passo 2) para uma frase real a 2x
OWNER_LINE = "Still can't really pinpoint"


def load_from_path(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_from_source(source, name):
    folder = tempfile.mkdtemp(prefix='overlay-ink-')
    path = os.path.join(folder, name + '.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(source)
    try:
        return load_from_path(path, name)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
        try:
            os.rmdir(folder)
        except OSError:
            pass


def ink(paint, text, dispose=True):
    """(pixeis de tinta, largura da tinta, digest do raster)."""
    bmp, width, height = _render_plain(paint, text)
    try:
        # UM RASTER COM OUTRA MEDIDA E' UM DEFEITO, NAO UM CRASH (2026-11-26):
        # com a chave do cache a ignorar o texto, `_premultiplied_bitmap` devolve
        # o raster de OUTRA linha e o `GetPixel` sai fora da caixa (medido:
        # `ArgumentOutOfRangeException` no braco negativo). A arm tem de ver o
        # tamanho errado e chama-lo pelo nome.
        if int(bmp.Width) != int(width) or int(bmp.Height) != int(height):
            return -1, -1, 'SIZE-MISMATCH-%dx%d-want-%dx%d' % (
                int(bmp.Width), int(bmp.Height), int(width), int(height))
        count = 0
        min_x, max_x = None, None
        digest = hashlib.sha256()
        # UM PASSO DE 2 PIXEIS: `GetPixel` custa ~0,2 ms e a caixa tem 1 000 x 300
        # (medido: 50 s de oraculo por causa do duplo laco). O passo nao muda
        # NENHUMA arm -- a contagem desce 4x e o piso desce com ela -- e o digest
        # continua a apanhar a mesma diferenca de texto. A contagem e' por isso
        # "pixeis amostrados", e a nota diz isso.
        step = 2
        for y in range(0, height, step):
            for x in range(0, width, step):
                px = bmp.GetPixel(x, y)
                digest.update(bytes((px.A, px.R & 0xF8, px.G & 0xF8, px.B & 0xF8)))
                if px.A <= 0:
                    continue
                count += 1
                min_x = x if min_x is None else min(min_x, x)
                max_x = x if max_x is None else max(max_x, x)
        span = 0 if min_x is None else max_x - min_x + 1
        return count, span, digest.hexdigest()
    finally:
        if dispose:
            bmp.Dispose()


def _render_plain(paint, text):
    theme = dict(paint._THEME_DEFAULT)
    for key in ('plate', 'background'):
        theme.pop(key, None)
    lines, prev, width, height, _scrolled = paint._layout(
        text, '', SCALE, WORK_WIDTH, theme, plate_mode='tight')
    bmp = paint._premultiplied_bitmap(lines, prev, int(width), int(height),
                                      SCALE, theme)
    return bmp, int(width), int(height)


def arms(paint):
    results = []

    count, span, digest = ink(paint, OWNER_LINE)
    results.append(('a INK-PRESENT', count >= INK_FLOOR,
                    'ink_px=%d span=%dpx floor=%d' % (count, span, INK_FLOOR)))

    thin, thin_span, _ = ink(paint, 'I')
    wide, wide_span, _ = ink(paint, 'MMMMMMMM')
    results.append(('b INK-FOLLOWS-TEXT',
                    bool(wide > thin and wide_span > thin_span * 2),
                    'I: px=%d span=%d | MMMMMMMM: px=%d span=%d'
                    % (thin, thin_span, wide, wide_span)))

    left, _, left_digest = ink(paint, 'the line the player served')
    right, _, right_digest = ink(paint, 'a totally other caption!')
    # AS DUAS METADES CONTAM: dois rasters VAZIOS tambem "diferem" se a medida
    # errada mudar o nome do veredicto -- por isso a tinta das duas entra na arm.
    painted = left >= INK_FLOOR and right >= INK_FLOOR
    results.append(('c TEXTS-DIFFER', bool(painted and left_digest != right_digest),
                    'ink %d/%d digests %s vs %s'
                    % (left, right, str(left_digest)[:12], str(right_digest)[:12])))

    blank, blank_span, _ = ink(paint, '')
    results.append(('d EMPTY-NO-INK', bool(blank == 0 and blank_span == 0),
                    'ink_px=%d span=%d' % (blank, blank_span)))

    first, _, first_digest = ink(paint, 'first served line here')
    mid, _, mid_digest = ink(paint, 'second served line here')
    again, _, again_digest = ink(paint, 'first served line here')
    # A TINTA DE CADA UM E' PARTE DO VEREDICTO: um cache que devolve o raster de
    # OUTRA linha da' digests que "diferem" e nomeia a medida errada -- sem esta
    # metade a arm passava com os tres rasters errados.
    painted = min(first, mid, again) >= INK_FLOOR
    results.append(('e CACHE-STABLE',
                    bool(painted and first_digest == again_digest
                         and first_digest != mid_digest),
                    'ink %d/%d/%d A==A2 %s A!=B %s'
                    % (first, mid, again, first_digest == again_digest,
                       first_digest != mid_digest)))
    return results


MUTATIONS = (
    # OS ANCORAS SAO A LINHA VIVA (2026-11-26): a primeira versao mutava a linha
    # de `cur_lines` que o caminho SEM `\n` nem chega a usar -- `_cw.wrap_tail`
    # escreve por cima dela --, e os tres mutantes "sobreviveram" a um portao que
    # estava certo. Um mutante que nao mexe no que corre e' decorativo.
    ('blank-glyphs',
     "cur_lines, scrolled = _cw.wrap_tail(text or '', cur_w, budget)",
     "cur_lines, scrolled = [''], ''", 'a INK-PRESENT'),
    ('text-ignored',
     "cur_lines, scrolled = _cw.wrap_tail(text or '', cur_w, budget)",
     "cur_lines, scrolled = _cw.wrap_tail('MMMM', cur_w, budget)",
     'b INK-FOLLOWS-TEXT'),
    ('cache-ignores-text',
     "def _paint_key(geo, cur_lines, prev_line, width, height, alphas, roll):",
     "def _paint_key(geo, cur_lines, prev_line, width, height, alphas, roll):\n    return 0",
     'e CACHE-STABLE'),
)


def neg_arm():
    with open(PAINT, encoding='utf-8') as fh:
        source = fh.read()
    caught = weak = 0
    for label, old, new, owner in MUTATIONS:
        if source.count(old) != 1:
            print('  RED   mutant %-18s ancora nao encontrada (%d) -- decorativo'
                  % (label, source.count(old)))
            weak += 1
            continue
        module = load_from_source(source.replace(old, new, 1),
                                  'overlay_paint_mut_' + label.replace('-', '_'))
        got = {name: ok for name, ok, _detail in arms(module)}
        if not got.get(owner):
            print('  GREEN mutant %-18s caught by: %s' % (label, owner))
            caught += 1
        else:
            print('  RED   mutant %-18s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    total = len(MUTATIONS)
    ok = caught == total and weak == 0
    print('NEG-ARM VERDICT: %s (%d/%d mutants caught, %d decorative)'
          % ('PASS' if ok else 'FAIL', caught, total, weak))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()
    paint = load_from_path(PAINT, 'overlay_paint_ink_probe')
    failed = 0
    for name, ok, detail in arms(paint):
        print('  %-18s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        failed += 0 if ok else 1
    print('OVERLAY-INK VERDICT: %s (%d failure(s))'
          % ('PASS' if not failed else 'FAIL', failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
