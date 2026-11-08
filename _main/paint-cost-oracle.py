#!/usr/bin/env python3
"""O CUSTO DA PINTURA DA LEGENDA, e a igualdade de pixel que o cache nao pode quebrar.

A ORDEM (watcher, 2026-11-08, DM de stutter): o processo acusado e' a app viva do
dono (`pythonw.exe` 42572) e o maior consumidor nomeado da shell e' a pintura da
legenda. Medido antes desta cura, neste caixa:

  `python -m watcher profile 42572` -> `cpu=33.5%` de um nucleo, 53 fios;
  `THREAD_CPU` (instrumento da app, janelas de 30 s) -> `top=sotto-caption-paint:10%`;
  uma pintura de uma legenda de 2 linhas -> 11,6 ms de p95 / 6,7 de p50
  (`GraphicsPath.AddString` + `DrawPath` + `FillPath`, POR LINHA, POR QUADRO).

O defeito nao e' o GDI+ ser lento: e' ele ser chamado quando NADA mudou de glifo.
`_premultiplied_bitmap` reconstruia o caminho do texto em todos os quadros, e a
unica coisa que muda entre dois quadros de uma legenda parada e' o alfa do
`UpdateLayeredWindow`. A cura (em `app/webview/overlay_paint.py`) guarda o RASTER
composto com uma chave que e' tudo o que move um pixel dele.

AS ARMS, todas medidas nesta corrida:

  A1 IGUALDADE DE PIXEL. >= 12 bases x alfa 0..255 (mais vetores de alfa
     misturados) comparadas BYTE A BYTE contra a implementacao ANTERIOR, que este
     oraculo carrega de `git show HEAD:app/webview/overlay_paint.py` para um
     modulo temporario. As bases cobrem os dois temas, as duas escalas, uma linha,
     duas linhas, o deslocamento de roll-up, a linha anterior, a placa ligada e
     desligada, a caixa estreita (borda direita) e a linha longa que quebra.
  A2 CUSTO. Cache-hit <= 2,0 ms de p95 em >= 200 iteracoes quentes (p50/p95/max
     impressos). O custo do MISS e' impresso e NAO e' portao: o miss e' o codigo
     de sempre.
  A2b LIMITE DO CACHE. LRU <= 8 entradas, e hits/misses/evictions/entries
     observaveis -- um cache sem contadores e' um cache que ninguem audita.
  A3 DELTA DE CPU [INFERENCE] -- aritmetica de A2 x taxa de quadro, derivada do
     ORCAMENTO (`CAPTION_FRAME_BUDGET` em `caption_overlay.py`), nunca de uma
     corrida da app: o pid do dono corre o codigo ANTERIOR e segura o mutex de
     instancia unica. O orcamento e' o que LIMITA o nucleo (40% por construcao);
     o cache e' o que compra TAXA (240 Hz exige <= 1,67 ms de pintura).
     O invariante "o periodo do quadro vem do custo da pintura" tem DONO noutro
     portao (`_main/caption-tick-thread-oracle.py`, arm A7) -- um invariante, um
     dono. Este oraculo nao o repete.
  NEG (`--neg-arm`). Dois mutantes em COPIA: (1) o cache e' construido e nunca
     consultado -- a igualdade de pixel continua verde e o CUSTO tem de cair;
     (2) um campo que move glifos/geometria (`roll`) sai da chave -- o custo
     continua verde e a IGUALDADE tem de cair. Um oraculo que nao cai com o
     defeito de volta nao mede nada.

NADA AQUI ABRE JANELA: o bitmap e' montado pelo `_layout`/`_premultiplied_bitmap`
que o overlay usa, e a tela do dono nao e' tocada.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "app" / "webview"
PAINT = WEB / "overlay_paint.py"
sys.path.insert(0, str(WEB))

import overlay_paint as op  # noqa: E402

#: O tecto declarado do passo. Medido 2026-11-08 nesta caixa: 7,1 ms de p50 numa
#: caixa de 576x156 (escala 1.0) e 11,6 ms de p95 na caixa real de 1040x240.
HIT_P95_MAX_MS = 2.0
FULL_SWEEP_BASES = 12
STRIDE = 15          # 18 valores de alfa nas bases fora da varredura cheia
MIXED_ALPHAS = ((0, 255, 128), (128, 255, 0), (255, 0, 255))


# ── os temas ─────────────────────────────────────────────────────────────────
# T0 = o overlay do YouTube, sem placa, centrado (o default historico).
T0 = None
# T1 = um tema de painel COM placa, regua e LED (o caminho do `brand-bridge`).
T1 = {
    'panelLivePx': 14.0, 'panelPrevPx': 10.5, 'panelPad': [6, 8, 6, 8],
    'panelRuleW': 1.5, 'fontFamily': 'Arial',
    'rowBg': '#101418', 'rowBgAlpha': 0.72, 'rowRadius': 12,
    'ruleColor': '#ff3b3b', 'ledVisible': True, 'ledColor': '#22ff88',
    'liveColor': '#f2f5f8', 'prevColor': '#b9c2cc',
    'align': 'left', 'liveLeading': 1.30, 'prevLeading': 1.25,
}
# T2 = o MESMO tema sem placa: e' a base que separa "placa ligada" de "desligada"
# sem mudar mais nada (regua e LED continuam, logo a chave tem de carregar os tres).
T2 = {k: v for k, v in T1.items() if k not in ('rowBg', 'rowBgAlpha', 'rowRadius')}

LONG = ("e a legenda ta do tamanho da tela, e pra tu verificar online como quebrar "
        "de um jeito bom, ou como o youtube faz")
TWO = "first line of the caption\nsecond line of it"


def _bases():
    """As bases: (rotulo, tema, escala, texto, anterior, largura, rows, roll)."""
    shapes = [
        ('one', 'just one line here', '', 1920, None, 0.0),
        ('two', TWO, 'an older line', 1920, 2, 0.0),
        ('roll45', TWO, 'an older line', 1920, 2, 0.45),
        ('prev', 'a live line', 'the previous caption that has faded', 1920, 2, 0.0),
        ('noprev', 'a live line with no previous row', '', 1920, 2, 0.0),
        ('long', LONG, '', 1920, None, 0.0),
        ('narrow', 'edge pinned line', '', 620, None, 0.0),
        ('three', 'one\nand a new third line\nwith a window', 'older still', 1920, 2, 0.30),
    ]
    out = []
    for tema_nome, tema in (('t0', T0), ('t1', T1), ('t2', T2)):
        for escala in (1.0, 2.0):
            for nome, texto, prev, work, rows, roll in shapes:
                out.append({
                    'label': '%s/s%.1f/%s' % (tema_nome, escala, nome),
                    'theme': tema, 'scale': escala, 'text': texto,
                    'prev': prev, 'work': work, 'rows': rows, 'roll': roll,
                })
    return out


# ── carregar modulos PELO CAMINHO ────────────────────────────────────────────
def _load_source(text, name):
    tmpdir = Path(tempfile.mkdtemp(prefix='paint-cost-'))
    path = tmpdir / (name + '.py')
    io.open(path, 'w', encoding='utf-8', newline='\n').write(text)
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_head():
    """A implementacao ANTERIOR, do MESMO commit -- nao de uma copia a mao."""
    out = subprocess.run(
        ['git', '-C', str(REPO), 'show', 'HEAD:app/webview/overlay_paint.py'],
        capture_output=True)
    if out.returncode != 0:
        raise SystemExit('paint-cost: HEAD ilegivel: %s'
                         % (out.stderr or b'').decode('utf-8', 'replace')[-400:])
    return _load_source(out.stdout.decode('utf-8'), 'overlay_paint_head')


# ── o bitmap como bytes ──────────────────────────────────────────────────────
def _bits(bmp, width, height):
    from System.Drawing import Rectangle
    from System.Drawing.Imaging import ImageLockMode, PixelFormat
    import ctypes

    data = bmp.LockBits(Rectangle(0, 0, width, height), ImageLockMode.ReadOnly,
                        PixelFormat.Format32bppPArgb)
    try:
        stride = abs(int(data.Stride))
        return (width, height, hashlib.sha256(
            ctypes.string_at(int(data.Scan0.ToInt64()), stride * height)
        ).hexdigest()[:16], stride * height)
    finally:
        bmp.UnlockBits(data)


def _alphas(n, k):
    return None if k is None else [int(k)] * n


def _render(mod, base, k=None):
    """O bitmap de uma base pelo caminho REAL do modulo dado."""
    cur, prev, w, h, _scrolled = mod._layout(
        base['text'], base['prev'], base['scale'], base['work'],
        base['theme'], rows=base['rows'])
    bmp = mod._premultiplied_bitmap(cur, prev, w, h, base['scale'],
                                    base['theme'], _alphas(len(cur), k),
                                    roll=base['roll'])
    try:
        return _bits(bmp, w, h)
    finally:
        try:
            bmp.Dispose()
        except Exception:
            pass


# ── A1: igualdade de pixel ───────────────────────────────────────────────────
def _arm_a1(new_mod, head_mod, bases, full_count, quiet=False):
    """Compara BYTE A BYTE contra a implementacao anterior."""
    bases = list(bases)
    full = set(range(min(full_count, len(bases))))
    compared = 0
    red = []
    for index, base in enumerate(bases):
        ks = range(0, 256) if index in full else range(0, 256, STRIDE)
        if 255 not in ks:
            ks = list(ks) + [255]
        for k in ks:
            want = _render(head_mod, base, k)
            got = _render(new_mod, base, k)
            compared += 1
            if want != got:
                red.append('%s k=%d head=%r novo=%r' % (base['label'], k,
                                                        want, got))
                break
        for vec in MIXED_ALPHAS:
            cur, _p, _w, _h, _s = new_mod._layout(
                base['text'], base['prev'], base['scale'], base['work'],
                base['theme'], rows=base['rows'])
            for k in (0, 128, 255):
                alphas = [(k if i % 2 == 0 else vec[i % 3]) for i in range(len(cur))]
                want = _digest(_paint(head_mod, base, alphas), head_mod, base)
                got = _digest(_paint(new_mod, base, alphas), new_mod, base)
                compared += 1
                if want != got:
                    red.append('%s misto=%r head=%r novo=%r'
                               % (base['label'], alphas, want, got))
                    break
        if not quiet:
            print('  A1 %-22s alfas=%s %s'
                  % (base['label'],
                     ('0..255' if index in full else 'passo %d' % STRIDE),
                     'RED' if red and red[-1].startswith(base['label']) else 'ok'),
                  flush=True)
    return not red, compared, red[:4]


def _digest(bmp, mod, base):
    """Bytes do bitmap e fecha-o (o `_layout` e' o do modulo dono do bitmap)."""
    _c, _p, w, h, _s = mod._layout(base['text'], base['prev'], base['scale'],
                                   base['work'], base['theme'],
                                   rows=base['rows'])
    try:
        return _bits(bmp, w, h)
    finally:
        try:
            bmp.Dispose()
        except Exception:
            pass


def _paint(mod, base, alphas):
    cur, prev, w, h, _s = mod._layout(base['text'], base['prev'], base['scale'],
                                      base['work'], base['theme'],
                                      rows=base['rows'])
    return mod._premultiplied_bitmap(cur, prev, w, h, base['scale'], base['theme'],
                                     alphas, roll=base['roll'])


# ── A2 + A2b: custo e limite do cache ────────────────────────────────────────
def _cost_base():
    return {'label': 'custo', 'theme': T1, 'scale': 2.0, 'text': TWO,
            'prev': 'the previous caption that has faded', 'work': 1920,
            'rows': 2, 'roll': 0.0}


def _time_calls(fn, n):
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        bmp = fn()
        out.append((time.perf_counter() - t0) * 1000.0)
        try:
            bmp.Dispose()
        except Exception:
            pass
    out.sort()

    def pick(q):
        return out[min(len(out) - 1, int(q * len(out)))]
    return out, statistics.median(out), pick(0.95), out[-1]


def _arm_a2(new_mod, head_mod, n=200):
    base = _cost_base()
    cur, prev, w, h, _s = new_mod._layout(base['text'], base['prev'],
                                          base['scale'], base['work'],
                                          base['theme'], rows=base['rows'])

    def once(mod):
        return lambda: mod._premultiplied_bitmap(
            cur, prev, w, h, base['scale'], base['theme'], [255] * len(cur),
            roll=base['roll'])

    before = _time_calls(once(head_mod), 30)
    before_stats = head_mod.__dict__.get('_paint_cache_stats')

    def miss_once():
        new_mod._paint_cache_clear()       # o miss E' o caminho de sempre
        return once(new_mod)()

    miss = _time_calls(miss_once, 12)
    new_mod._paint_cache_clear()
    _time_calls(once(new_mod), 1)
    hits, hit_p50, hit_p95, hit_max = _time_calls(once(new_mod), n)
    stats = new_mod._paint_cache_stats()
    facts = ('caixa=%dx%d hit_ms p50=%.3f p95=%.3f max=%.3f (%d iteracoes) | '
             'miss_ms p50=%.2f p95=%.2f (nao e portao) | HEAD_ms p50=%.2f | '
             'stats=%r'
             % (w, h, hit_p50, hit_p95, hit_max, n,
                statistics.median(miss[0]), miss[2],
                statistics.median(before[0]), stats))
    problems = []
    if hit_p95 > HIT_P95_MAX_MS:
        problems.append('hit p95=%.3f ms > %.1f ms' % (hit_p95, HIT_P95_MAX_MS))
    if stats['hits'] < n:
        problems.append('hits=%d < %d iteracoes: nem todas bateram no cache'
                        % (stats['hits'], n))
    if before_stats is not None:
        problems.append('a implementacao ANTERIOR ja tinha cache: nao e a baseline')
    return (not problems, facts if not problems else ' | '.join(problems),
            {'hit_p50': hit_p50, 'hit_p95': hit_p95, 'hit_max': hit_max,
             'miss_p50': statistics.median(miss[0]),
             'head_p50': statistics.median(before[0]), 'w': w, 'h': h})


def _ten_keys(bases):
    """10 chaves DISTINTAS da mesma forma (o texto muda, a geometria nao)."""
    base = bases[0]
    out = []
    for index in range(10):
        variant = dict(base)
        variant['text'] = '%s %d' % (base['text'], index)
        out.append(variant)
    return out


def _arm_a2b(new_mod, bases):
    """LRU <= 8 e contadores observaveis."""
    new_mod._paint_cache_clear()
    facts = []
    problems = []
    keys = _ten_keys(bases)
    for base in keys:
        _render(new_mod, base, 255)
    stats = new_mod._paint_cache_stats()
    facts.append('apos 10 chaves: %r' % stats)
    if stats['entries'] > stats['max'] or stats['max'] > 8:
        problems.append('entradas=%d max=%d > 8' % (stats['entries'], stats['max']))
    if stats['evictions'] < 2:
        problems.append('evictions=%d < 2 apos 10 chaves' % stats['evictions'])
    if stats['misses'] < 10:
        problems.append('misses=%d < 10 chaves novas' % stats['misses'])
    # Um hit tem de ser CONTADO e o raster tem de ser o mesmo.
    base = keys[9]
    before = _render(new_mod, base, 255)
    after = _render(new_mod, base, 255)
    stats = new_mod._paint_cache_stats()
    facts.append('hit repetido: hits=%d mesmo_raster=%s'
                 % (stats['hits'], before == after))
    if stats['hits'] < 1:
        problems.append('hits=0 no segundo pedido da MESMA base')
    if before != after:
        problems.append('hit devolveu raster diferente')
    # O hit tem de ser o raster do MISS (e nao do HEAD): a copia e' fiel.
    clean = _load_source(io.open(str(PAINT), encoding='utf-8').read(),
                         'overlay_paint_fresh')
    if _render(clean, base, 255) != after:
        problems.append('o raster servido pelo cache difere de um miss limpo')
    # Alfa parcial NAO pode usar o cache (nao ha' decomposicao exacta).
    new_mod._paint_cache_clear()
    cur, _p, w, h, _s = new_mod._layout(base['text'], base['prev'], base['scale'],
                                        base['work'], base['theme'],
                                        rows=base['rows'])
    new_mod._premultiplied_bitmap(cur, _p, w, h, base['scale'], base['theme'],
                                  [128] * len(cur), roll=base['roll'])
    stats = new_mod._paint_cache_stats()
    facts.append('alfa 128: %r' % stats)
    if stats['entries'] != 0 or stats['hits'] != 0:
        problems.append('o cache guardou/serviu um raster com alfa parcial')
    return not problems, ' '.join(facts) if not problems else ' | '.join(problems)


def _arm_a3(cost, budget=0.40):
    """[INFERENCE] -- aritmetica de A2 x taxa de quadro, nao uma corrida da app.

    O ORCAMENTO E' O QUE LIMITA O NUCLEO; O CACHE E' O QUE COMPRA TAXA. Com
    `CAPTION_FRAME_BUDGET` o periodo e' `custo / 0.40`, logo a CPU do fio e' 40%
    POR CONSTRUCAO e deixa de ser funcao do custo da pintura -- o custo passa a
    comprar QUADROS. Nada disto e' medido na app do dono: o pid dele corre o
    codigo ANTERIOR e segura o mutex de instancia unica. [INFERENCE]
    """
    saved_ms = max(0.0, cost['miss_p50'] - cost['hit_p50'])
    lines = []
    before_hz = budget / max(1e-6, cost['miss_p50'] / 1000.0)
    after_hz = budget / max(1e-6, cost['hit_p50'] / 1000.0)
    lines.append('orcamento %.0f%%: antes %.2f ms -> %.0f Hz; depois %.2f ms -> '
                 '%.0f Hz (tecto do relogio 240 Hz)'
                 % (budget * 100.0, cost['miss_p50'], before_hz,
                    cost['hit_p50'], after_hz))
    lines.append('guardado por pintura: %.2f ms; %.2fx menos'
                 % (saved_ms, cost['miss_p50'] / max(1e-6, cost['hit_p50'])))
    # O NUMERO QUE O INSTRUMENTO NOMEOU: 10% de um nucleo = 0,1 s/s. Nas MESMAS
    # pinturas por segundo que aquilo implicava, o custo novo da' quanto?
    paints_per_s = 0.10 / max(1e-6, cost['miss_p50'] / 1000.0)
    lines.append('mesmas %.1f pinturas/s (o que 10%% de um nucleo pagava): '
                 '%.1f%% -> %.2f%% de um nucleo'
                 % (paints_per_s, paints_per_s * cost['miss_p50'] / 10.0,
                    paints_per_s * cost['hit_p50'] / 10.0))
    period_ms = cost['hit_p50'] / budget
    lines.append("o tecto do relogio so' e' alcancavel com pintura <= %.2f ms; "
                 "o hit medido da' periodo de %.1f ms (%.0f Hz)"
                 % (1000.0 * budget / 240.0, period_ms, 1000.0 / period_ms))
    return '[INFERENCE] ' + '; '.join(lines)


# ── NEG: mutantes em COPIA ───────────────────────────────────────────────────
MUT1 = ("    if key is not None:\n"
        "        hit = _paint_cache_get(key)\n"
        "        if hit is not None:\n"
        "            return hit\n",
        "    if key is not None:\n"
        "        hit = _paint_cache_get(key)\n"
        "        if hit is not None:\n"
        "            hit.Dispose()      # MUTANTE: constroi e nunca serve\n")
MUT2 = ("_freeze(geo), float(roll))",
        "_freeze(geo), 0.0)      # MUTANTE: `roll` fora da chave")


def _mutate(text, mutation, label):
    old, new = mutation
    if text.count(old) != 1:
        raise SystemExit('paint-cost: MUTANTE %s nao aplicou (%d ocorrencias) -- '
                         'o mutante tem de doer, nao falhar em silencio'
                         % (label, text.count(old)))
    return text.replace(old, new, 1)


def _neg_arm(head_mod, bases, cost_runs=40):
    src = io.open(str(PAINT), encoding='utf-8').read()
    qbase = [b for b in bases if b['label'] in
             ('t0/s1.0/one', 't0/s1.0/two', 't0/s1.0/roll45',
              't0/s1.0/prev', 't1/s2.0/two', 't1/s2.0/roll45')]
    print('NEG: %d bases reduzidas, alfas 0/128/255' % len(qbase), flush=True)

    def pixel_red(mod):
        red = []
        for base in qbase:
            for k in (0, 128, 255):
                if _render(head_mod, base, k) != _render(mod, base, k):
                    red.append('%s k=%d' % (base['label'], k))
        return red

    def cost_ms(mod):
        base = _cost_base()
        cur, prev, w, h, _s = mod._layout(base['text'], base['prev'],
                                          base['scale'], base['work'],
                                          base['theme'], rows=base['rows'])
        mod._paint_cache_clear()
        fn = lambda: mod._premultiplied_bitmap(  # noqa: E731
            cur, prev, w, h, base['scale'], base['theme'], [255] * len(cur),
            roll=base['roll'])
        _time_calls(fn, 1)
        _r, p50, p95, _mx = _time_calls(fn, cost_runs)
        return p50, p95

    caught = {}
    mod1 = _load_source(_mutate(src, MUT1, 'lookup-off'), 'overlay_paint_mut1')
    red1 = pixel_red(mod1)
    p50, p95 = cost_ms(mod1)
    caught['lookup-off'] = (p95 > HIT_P95_MAX_MS,
                            'pixel_red=%d hit_ms p50=%.2f p95=%.2f (portao %.1f)'
                            % (len(red1), p50, p95, HIT_P95_MAX_MS))
    print('  MUTANTE lookup-off: %s' % caught['lookup-off'][1], flush=True)

    mod2 = _load_source(_mutate(src, MUT2, 'roll-off-key'), 'overlay_paint_mut2')
    red2 = pixel_red(mod2)
    p502, p952 = cost_ms(mod2)
    caught['roll-off-key'] = (bool(red2),
                              'pixel_red=%d (%s) hit_p95=%.2f ms'
                              % (len(red2), ', '.join(red2[:3]) or 'nenhum', p952))
    print('  MUTANTE roll-off-key: %s' % caught['roll-off-key'][1], flush=True)

    ok = all(v[0] for v in caught.values())
    print('NEG-ARM: %s' % ('PASS' if ok else 'FAIL'), flush=True)
    return ok


# ── main ─────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='paint-cost-oracle')
    parser.add_argument('--neg-arm', action='store_true',
                        help='muta a cura numa COPIA e exige o vermelho')
    parser.add_argument('--bases', type=int, default=0,
                        help='limita o numero de bases (debug)')
    args = parser.parse_args(argv)

    head_mod = _load_head()
    bases = _bases()
    if args.bases:
        bases = bases[:args.bases]
    print('paint-cost: %d bases, %d com varredura cheia 0..255'
          % (len(bases), min(FULL_SWEEP_BASES, len(bases))), flush=True)

    if args.neg_arm:
        return 1 if _neg_arm(head_mod, bases) else 0

    arms = []
    ok, compared, red = _arm_a1(op, head_mod, bases, FULL_SWEEP_BASES)
    print('A1 %s -- %d comparacoes byte a byte contra HEAD%s'
          % ('PASS' if ok else 'RED', compared,
             '' if ok else ': ' + ' | '.join(red)), flush=True)
    arms.append(('A1 igualdade de pixel vs HEAD', ok))

    ok, facts, cost = _arm_a2(op, head_mod)
    print('A2 %s -- %s' % ('PASS' if ok else 'RED', facts), flush=True)
    arms.append(('A2 custo do hit <= %.1f ms p95' % HIT_P95_MAX_MS, ok))

    ok, facts = _arm_a2b(op, bases)
    print('A2b %s -- %s' % ('PASS' if ok else 'RED', facts), flush=True)
    arms.append(('A2b LRU <= 8 com contadores', ok))

    print('A3 %s' % _arm_a3(cost), flush=True)

    bad = [name for name, good in arms if not good]
    print('')
    for name, good in arms:
        print('  %-34s %s' % (name, 'PASS' if good else 'RED'))
    print('PAINT-COST %s' % ('PASS' if not bad else 'FAIL ' + ' '.join(bad)),
          flush=True)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
