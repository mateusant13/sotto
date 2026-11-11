#!/usr/bin/env python
# NO-BUG: mede a placa contra a tinta branca do bitmap que embarca; nao redesenha a legenda nem decide a largura que o dono quer.
"""ORACLE: a PLACA da legenda nativa abraca a linha -- e a opacidade e' da PLACA.

O dono, 2026-11-09, verbatim: *"the background in the subtitles is too wide.
should be more concise and less bloaty."*

O QUE ELE VE NA TELA E' A JANELA NATIVA (`caption_overlay` -> `overlay_paint`),
um bitmap GDI+ composto por `UpdateLayeredWindow`; o `caption.html` do painel nao
chega ao ecra. Logo a medida tem de ser feita no BITMAP que embarca:

  * a PLACA e' o proprio bitmap (o `_paint_bitmap` enche o rect 0..width x
    0..height), por isso "placa vs texto" mede-se contra a tinta BRANCA que o
    GDI+ pintou -- `LockBits` do mesmo raster que vai para o ecra;
  * a TINTA e' lida como pixel premultiplicado (`R >= 200`), e a placa como
    `A > 0`; a caixa de texto e' o bounding box dos dois.

MEDIDO com este oraculo (escala 1.0, Arial 38, contorno 5, placa preta 200):

  cue      modo    placa      tinta      folga L/R/T/B
  1 linha  normal  249 x 71   179 x 27   35/35/20/24
  1 linha  tight   205 x 60   179 x 27   13/13/14/19
  2 linhas normal  310 x 122  239 x 85   35/36/20/17
  2 linhas tight   266 x 111  239 x 86   14/13/14/11
  vazio    normal  240 x 71   (nada)     240 px de nada  <-- o slab de hoje
  vazio    tight   1 x 1      (nada)     0

AS ARMS (todas executadas; um braco que nao pode ficar RED nao e' evidencia):

  A1 aperto        -- `tight` e' mais estreita E mais baixa que `normal` nas duas
                      cues com texto (>= 10 px de largura, >= 5 px de altura).
  A2 vazio         -- cue sem texto em `tight` = 1x1; em `normal` >= 240 px de
                      largura (o tecto antigo, medido 240 x 71).
  A3 tinta intacta -- a caixa de TINTA (largura e altura) e' IDENTICA nos dois
                      modos: encolheu a placa, nunca o glifo. (Foi esta arm que
                      apanhou o `rect` do `AddString` 0,4 px mais estreito que a
                      medida: 155 px de tinta contra 179 -- o ultimo glifo cai.)
  A4 folga medida  -- em `tight` a folga lateral fica entre 4 px e 0,45 em; em
                      `normal` >= 25 px. E' a definicao de "hug" que o dono pediu.
  A5 opacidade     -- placa 200 @ opacity 1.0 -> 200 de alfa; @ 0.4 -> 80; a
                      TINTA continua a 255 e a caixa de tinta nao se move. A
                      opacidade e' da placa; a legenda nao desbota.
  A6 padrao ausente-- `_layout`/`_premultiplied_bitmap` sem os kwargs == os
                      numeros de `normal`/1.0 (o caminho de pintura), e o
                      `_caption_style` do overlay num objecto SEM os atributos
                      devolve o que EMBARCA (`tight`, lido de
                      `caption_settings`); com os atributos postos, honra-os e
                      prende `0.1 -> 0.30`.
  A7 settings      -- `caption_settings`: ausente / corrompido / tipo errado caem
                      no default e nunca levantam; `0.1 -> 0.30`, `5 -> 1.0`,
                      `plate='banana' -> tight`; a escrita e' atomica (sem
                      `.tmp`) e NAO apaga o `target_lang` dele.

O NEGATIVO (--neg-arm) MUTA UMA COPIA, nunca o fonte: cada mutante tem de deixar
RED a arm que ele nomeia. rc=1 = todos apanhados (o negativo passou); rc=0 = algum
mutante INERTE.

NADA AQUI ABRE JANELA: o bitmap e' montado fora do ecra, e nenhum endpoint de
audio e' tocado.

Uso:
  python _main/caption-plate-oracle.py
  python _main/caption-plate-oracle.py --neg-arm
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import importlib.util
import inspect
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')
sys.path.insert(0, WEBVIEW)

import overlay_paint as op  # noqa: E402

#: O TEMA MEDIDO: a face do player (Arial 38 / contorno 5) e a placa do desenho
#: (preto a 200) -- e' o caso do dono: legenda sobre video, com fundo.
THEME = dict(op._THEME_DEFAULT)
THEME.update({'plate': (0, 0, 0, 200), 'plateRadius': 10.0,
              'strokeColor': (0, 0, 0, 255)})
PLATE_ALPHA = 200
CUES = (('1-line', 'ola mundo'),
        ('2-line', 'primeira linha\nsegunda linha'),
        ('empty', ''))
TIGHT_MAX_EM = 0.45      # a folga lateral de `tight`, em em do tamanho vivo
NORMAL_MIN_GAP = 25      # a folga de `normal` que `tight` tem de bater
WIDTH_SAVED = 10         # px poupados a' largura, no minimo
HEIGHT_SAVED = 5

rows: list[tuple[bool, str, str]] = []
_CACHE: dict[tuple, dict] = {}


def add(ok: bool, name: str, detail: str = '') -> bool:
    rows.append((bool(ok), name, detail))
    print('  %s %s%s' % ('GREEN' if ok else 'RED  ', name,
                         ('  ' + detail) if detail else ''))
    return bool(ok)


# ── a medida, no raster que embarca ──────────────────────────────────────────
def measure(text: str, mode: str, opacity: float = 1.0,
            overlay=op) -> dict:
    """A caixa da placa e a caixa da TINTA, do bitmap pintado. Sem janela."""
    key = (text, mode, float(opacity),
           getattr(overlay, '__name__', 'unknown'))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    cur, prev, width, height, _scrolled = overlay._layout(
        text, '', 1.0, 1920, THEME, plate_mode=mode)
    overlay._paint_cache_clear()
    bmp = overlay._premultiplied_bitmap(cur, prev, width, height, 1.0, THEME,
                                        None, 0.0, plate_mode=mode,
                                        opacity=opacity)
    try:
        from System.Drawing import Rectangle
        from System.Drawing.Imaging import ImageLockMode, PixelFormat
        data = bmp.LockBits(Rectangle(0, 0, width, height),
                            ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb)
        try:
            stride = abs(int(data.Stride))
            raw = ctypes.string_at(int(data.Scan0.ToInt64()), stride * height)
        finally:
            bmp.UnlockBits(data)
    finally:
        bmp.Dispose()
    plate = _bbox(raw, width, height, stride, lambda i: raw[i + 3] > 0)
    ink = _bbox(raw, width, height, stride,
                lambda i: raw[i + 3] > 0 and raw[i + 2] >= 200)
    out = {'w': width, 'h': height, 'raw': raw, 'stride': stride,
           'plate': plate, 'ink': ink, 'mode': mode, 'text': text}
    if plate and ink:
        pl, pt, pw, ph = plate
        il, it, iw, ih = ink
        out['gaps'] = (il - pl, (pl + pw) - (il + iw),
                       it - pt, (pt + ph) - (it + ih))
    _CACHE[key] = out
    return out


def _bbox(raw: bytes, width: int, height: int, stride: int, hit) -> tuple | None:
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for y in range(height):
        base = y * stride
        for x in range(width):
            if hit(base + x * 4):
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        return None
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def alpha_at(m: dict, x: int, y: int) -> int:
    return m['raw'][y * m['stride'] + x * 4 + 3]


def brightest(m: dict) -> tuple:
    """O pixel mais claro com alfa: a tinta (premultiplicada) da legenda."""
    best = (0, 0, 0)
    for y in range(m['h']):
        base = y * m['stride']
        for x in range(m['w']):
            i = base + x * 4
            if m['raw'][i + 3] == 255 and m['raw'][i + 2] >= best[0]:
                best = (m['raw'][i + 2], m['raw'][i + 1], m['raw'][i], 255)
    return best


def table() -> None:
    print('MEDIDO -- placa (bitmap inteiro) vs TINTA (branco pintado), escala 1.0')
    print('  %-8s %-7s %-12s %-11s %s'
          % ('cue', 'modo', 'placa', 'tinta', 'folga L/R/T/B'))
    for label, text in CUES:
        for mode in ('normal', 'tight'):
            m = measure(text, mode)
            placa = '%dx%d' % (m['w'], m['h'])
            ink = ('%dx%d' % (m['ink'][2], m['ink'][3])) if m['ink'] else '-'
            gaps = '/'.join(str(v) for v in m['gaps']) if m.get('gaps') else '-'
            print('  %-8s %-7s %-12s %-11s %s' % (label, mode, placa, ink, gaps))
    print('')


# ── as arms ──────────────────────────────────────────────────────────────────
def arm_a1(ctx) -> tuple:
    overlay = ctx['overlay']
    saved = []
    ok = True
    for label, text in CUES[:2]:
        n = measure(text, 'normal', overlay=overlay)
        t = measure(text, 'tight', overlay=overlay)
        dw, dh = n['w'] - t['w'], n['h'] - t['h']
        saved.append('%s %dx%d->%dx%d (-%d,-%d)' % (label, n['w'], n['h'],
                                                    t['w'], t['h'], dw, dh))
        ok = ok and dw >= WIDTH_SAVED and dh >= HEIGHT_SAVED
    return ok, ' '.join(saved)


def arm_a2(ctx) -> tuple:
    overlay = ctx['overlay']
    n = measure('', 'normal', overlay=overlay)
    t = measure('', 'tight', overlay=overlay)
    ok = n['w'] >= 240 and t['w'] <= 2 and t['h'] <= 2
    return ok, 'normal %dx%d  tight %dx%d' % (n['w'], n['h'], t['w'], t['h'])


def arm_a3(ctx) -> tuple:
    overlay = ctx['overlay']
    ok = True
    detail = []
    for label, text in CUES[:2]:
        n = measure(text, 'normal', overlay=overlay)
        t = measure(text, 'tight', overlay=overlay)
        same = bool(n['ink'] and t['ink']
                    and n['ink'][2] == t['ink'][2]
                    and abs(n['ink'][3] - t['ink'][3]) <= 1)
        detail.append('%s %s vs %s' % (label,
                                       n['ink'][2:] if n['ink'] else '-',
                                       t['ink'][2:] if t['ink'] else '-'))
        ok = ok and same
    return ok, ' '.join(detail)


def arm_a4(ctx) -> tuple:
    overlay = ctx['overlay']
    em = overlay._geom(1.0, THEME)['cur_px']
    limit = max(6.0, TIGHT_MAX_EM * em)
    ok = True
    detail = []
    for label, text in CUES[:2]:
        n = measure(text, 'normal', overlay=overlay)
        t = measure(text, 'tight', overlay=overlay)
        tl, tr = t['gaps'][0], t['gaps'][1]
        nl, nr = n['gaps'][0], n['gaps'][1]
        detail.append('%s tight %d/%d normal %d/%d' % (label, tl, tr, nl, nr))
        ok = ok and 4 <= tl <= limit and 4 <= tr <= limit
        ok = ok and nl >= NORMAL_MIN_GAP and nr >= NORMAL_MIN_GAP
    return ok, 'limite %.1f px '%(limit) + ' '.join(detail)


def arm_a5(ctx) -> tuple:
    overlay = ctx['overlay']
    full = measure('ola mundo', 'tight', 1.0, overlay=overlay)
    dim = measure('ola mundo', 'tight', 0.4, overlay=overlay)
    a_full = alpha_at(full, full['w'] // 2, 2)
    a_dim = alpha_at(dim, dim['w'] // 2, 2)
    ink_full = brightest(full)
    ink_dim = brightest(dim)
    ok = (abs(a_full - PLATE_ALPHA) <= 1
          and abs(a_dim - round(PLATE_ALPHA * 0.4)) <= 1
          and ink_full[3] == 255 and ink_dim[3] == 255
          and ink_full[:3] == ink_dim[:3])
    return ok, ('placa %d->%d  tinta %r->%r' %
                (a_full, a_dim, ink_full, ink_dim))


def arm_a6(ctx) -> tuple:
    """O default de quem NAO tem atributo e' o que EMBARCA.

    RE-PINADO EM 2026-11-09 junto com a cura: a placa apertada deixou de ser uma
    escolha para passar a ser o que a legenda e' quando o dono nunca abriu a
    caixa. Antes desta data a arm exigia `normal`/1.0 -- ou seja, exigia que a
    legenda continuasse a ser a coisa que ele pediu para emagrecer. O mutante M4
    passou a mutar no sentido INVERSO (tight -> normal) pela mesma razao.
    """
    overlay, caption = ctx['overlay'], ctx['caption']
    sig = inspect.signature(overlay._layout)
    bmp_sig = inspect.signature(overlay._premultiplied_bitmap)
    # A API de PINTURA mantem os proprios defaults (normal/1.0): quem decide o
    # que embarca e' o OVERLAY, nao a funcao de desenho -- e e' isso que a
    # segunda metade desta arm mede.
    defaults = (sig.parameters['plate_mode'].default,
                bmp_sig.parameters['plate_mode'].default,
                bmp_sig.parameters['opacity'].default)
    bare = overlay._layout('ola mundo', '', 1.0, 1920, THEME)
    explicit = overlay._layout('ola mundo', '', 1.0, 1920, THEME,
                               plate_mode='normal')

    class _Absent:
        pass
    style = caption.NativeCaptionOverlay._caption_style(_Absent())
    ok = (defaults == ('normal', 'normal', 1.0)
          and bare == explicit
          and style == {'plate_mode': 'tight', 'opacity': 1.0})
    return ok, 'defaults %r  style %r' % (defaults, style)


def arm_a7(ctx) -> tuple:
    import caption_settings as cs
    detail = []
    with tempfile.TemporaryDirectory(prefix='plate-settings-') as folder:
        dest = os.path.join(folder, 'caption-settings.json')
        old = os.environ.get('SOTTO_CAPTION_SETTINGS')
        os.environ['SOTTO_CAPTION_SETTINGS'] = dest
        try:
            base = cs.visual()
            detail.append('ausente %r' % (base,))
            with io.open(dest, 'w', encoding='utf-8') as fh:
                fh.write('{ not json')
            corrupt = cs.visual()
            detail.append('corrompido %r' % (corrupt,))
            cs.save({'target_lang': 'en', 'plate': 'banana', 'opacity': 0.1})
            clamped = cs.visual()
            detail.append('clamp %r' % (clamped,))
            applied = cs.set_visual(5.0, 'normal')
            detail.append('teto %r' % (applied,))
            kept = cs.load()
            tmp_left = os.path.exists(dest + '.tmp')
            ok_kept = kept.get('target_lang') == 'en'
            applied2 = cs.set_visual(opacity=0.55)
            kept2 = cs.load()
        finally:
            if old is None:
                os.environ.pop('SOTTO_CAPTION_SETTINGS', None)
            else:
                os.environ['SOTTO_CAPTION_SETTINGS'] = old
    ok = (base == {'opacity': 1.0, 'plate': 'tight'}
          and corrupt == {'opacity': 1.0, 'plate': 'tight'}
          and clamped == {'opacity': 0.3, 'plate': 'tight'}
          and applied == {'opacity': 1.0, 'plate': 'normal'}
          and ok_kept and not tmp_left
          and applied2 == {'opacity': 0.55, 'plate': 'normal'}
          and kept2.get('target_lang') == 'en')
    return ok, ' | '.join(detail) + ' | target_lang kept=%s tmp=%s' % (
        ok_kept, tmp_left)


def _source_path(rel: str) -> str:
    """O caminho UNICO de um fonte, para o leitor e para o plantador nao divergirem.

    Ha' duas maneiras de nomear o mesmo ficheiro neste oraculo: relativo ao
    `app/webview` (`sotto_webview.py`) e relativo a ele com `../` (`../panel/
    panel.html`). O `--neg-arm` plantava o texto mutado com uma chave e o `src`
    lia com outra -- os mutantes da pagina ficavam INERTES (medido: M5 e M6 a
    0/7 a 2026-11-09). Uma funcao so' e' a cura, nao duas contas iguais.
    """
    if os.path.isabs(rel):
        return os.path.normpath(rel)
    if rel.startswith('../'):
        return os.path.normpath(os.path.join(
            os.path.dirname(WEBVIEW), *rel[3:].split('/')))
    return os.path.normpath(os.path.join(WEBVIEW, *rel.split('/')))


def src(ctx, rel: str) -> str:
    """O fonte real, ou o MUTADO que o `--neg-arm` plantou para este ficheiro.

    Os mutantes de FIACAO (`panel.html`, `panel.js`, `sotto_webview.py`) nao sao
    modulos importaveis: a unica forma de os medir e' entregar o texto mutado ao
    mesmo leitor que le o texto de disco.
    """
    path = _source_path(rel)
    over = (ctx.get('sources') or {}).get(path)
    if over is not None:
        return over
    return io.open(path, encoding='utf-8', newline='').read()


def arm_a8(ctx) -> tuple:
    """A CADEIA: a caixa -> o shell -> o ficheiro -> a janela viva.

    O defeito que esta arm existe para impedir foi medido nesta casa tres vezes
    (a mesma classe: um instrumento sem chamador): a maquinaria de `tight` e de
    `opacity` existia e NADA a ligava -- `caption_settings` sem um unico
    importador no shell, `set_visual` sem chamadores e a caixa sem controlos. Um
    oraculo que so' prova a matematica da placa deixa este furo inteiro aberto.

    Quatro metades, todas lidas do FONTE REAL:

      a) o `NativeCaptionOverlay` REAL nasce com `_SHIPPED_VISUAL`: criado num
         ambiente sem ficheiro de configuracao, sai `tight`/1.0 -- a legenda do
         dono ja' nasce apertada, sem depender de um push da pagina;
      b) `set_visual` aplica e devolve o PRESO (0.1 -> 0.30, 'banana' -> 'tight');
      c) o `_caption_visual` do shell grava o ficheiro E aplica ao overlay vivo,
         e o log diz o numero aplicado, nao o pedido;
      d) a pagina: as duas linhas existem no `panel.html`, `panel.js` obtem os
         elementos e envia `setCaptionVisual`, e o mapa de mensagens do shell tem
         a entrada `caption-visual` (sem ela o `post` morre em BRIDGE_UNKNOWN_KIND).
    """
    caption = ctx['caption']
    panel_html = src(ctx, '../panel/panel.html')
    panel_js = src(ctx, '../panel/panel.js')
    shell_src = src(ctx, 'sotto_webview.py')

    # (b) o clamp e a aplicacao, num overlay de verdade (sem janela: hwnd=None).
    import caption_settings as cs
    detail = []
    with tempfile.TemporaryDirectory(prefix='plate-chain-') as folder:
        dest = os.path.join(folder, 'caption-settings.json')
        old = os.environ.get('SOTTO_CAPTION_SETTINGS')
        os.environ['SOTTO_CAPTION_SETTINGS'] = dest
        try:
            ov = caption.NativeCaptionOverlay(log=lambda msg: None)
            born_real = {'plate': getattr(ov, 'plate_mode', None),
                         'opacity': getattr(ov, 'opacity', None)}
            applied = ov.set_visual(opacity=0.1, plate='banana')
            applied2 = ov.set_visual(opacity=0.5)
            kept = ov.set_visual(plate='normal')
            # (c) o metodo do shell, extraido por AST e chamado com um overlay
            # falso: o ficheiro TEM de ficar gravado e o overlay TEM de receber.
            logs = []

            class _FakeOverlay:
                def __init__(self):
                    self.calls = []

                def set_visual(self, opacity=None, plate=None):
                    self.calls.append((plate, opacity))
                    return {'plate_mode': plate, 'opacity': opacity}

            fake = _FakeOverlay()
            holder = type('H', (), {'caption_overlay': fake})()
            fn = None
            for node in ast.parse(shell_src).body:
                if isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if (isinstance(sub, ast.FunctionDef)
                                and sub.name == '_caption_visual'):
                            fn = ast.get_source_segment(shell_src, sub)
            ns = {'log': logs.append, 'json': json}
            if fn:
                exec(fn, ns)  # noqa: S102 -- o fonte REAL, sem copia
                ns['_caption_visual'](holder, {'opacity': 5.0, 'plate': 'normal'})
            on_disk = cs.visual()
            shell_ok = bool(fn) and on_disk == {'opacity': 1.0, 'plate': 'normal'} \
                and fake.calls == [('normal', 1.0)] \
                and any('CAPTION_VISUAL' in ln for ln in logs)
            # (d) a pagina e o mapa de mensagens
            html_ok = ('id="caption-plate-select"' in panel_html
                       and 'id="caption-opacity-range"' in panel_html)
            # A CHAMADA, nao o identificador: o `typeof bridge.setCaptionVisual`
            # da linha de cima sobrevive a mutacao do CALL, e foi assim que o M6
            # ficou INERTE (medido: 6/7 a 2026-11-09). A arm exige a chamada que
            # leva os DOIS valores.
            js_ok = ('captionPlateSelect' in panel_js
                     and 'sendCaptionLook' in panel_js
                     and 'bridge.setCaptionVisual({ plate: plate, opacity: opacity })'
                     in panel_js)
            map_ok = "'caption-visual': ('host', '_caption_visual')" in shell_src
            bridge_ok = 'setCaptionVisual: function' in shell_src
        finally:
            if old is None:
                os.environ.pop('SOTTO_CAPTION_SETTINGS', None)
            else:
                os.environ['SOTTO_CAPTION_SETTINGS'] = old
    detail.extend(['applied %r' % (applied,), 'applied2 %r' % (applied2,),
                   'kept %r' % (kept,), 'nasceu com %r' % (born_real,),
                   'shell %r' % (fake.calls,), 'disco %r' % (on_disk,),
                   'html=%s js=%s mapa=%s bridge=%s'
                   % (html_ok, js_ok, map_ok, bridge_ok)])
    ok = (born_real == {'plate': 'tight', 'opacity': 1.0}
          and applied == {'plate_mode': 'tight', 'opacity': 0.3}
          and applied2 == {'plate_mode': 'tight', 'opacity': 0.5}
          and kept == {'plate_mode': 'normal', 'opacity': 0.5}
          and shell_ok and html_ok and js_ok and map_ok and bridge_ok)
    return ok, ' | '.join(detail)


def arm_a9(ctx) -> tuple:
    """A CAIXA QUE O OVERLAY MEDE E' A CAIXA QUE ELE PINTA -- e o estilo passa.

    MEDIDO 2026-11-10, chamando o `NativeCaptionOverlay` REAL: `_measure` faz
    `_layout(..., **self._caption_style())` e o estilo carrega `opacity`, que o
    `_layout` nao aceitava -- `TypeError: _layout() got an unexpected keyword
    argument 'opacity'` em TODA pintura. A1-A8 nao viam: medem o bitmap por
    argumentos explicitos, e A8 nunca chama `_measure` (sem janela nao ha'
    `_update`). Um instrumento que so' exercita a funcao de baixo nivel deixa o
    chamador quebrado, que e' exactamente a classe de defeito desta casa.

    Duas metades: (1) `_measure` do overlay REAL aceita o estilo inteiro e
    devolve a MESMA caixa que A1 mede no bitmap (>= 10 px de largura e >= 5 de
    altura a menos em `tight`); (2) o dict do `_caption_style` e' aceito pelas
    DUAS funcoes de pintura, com o alfa aplicado.
    """
    caption, overlay = ctx['caption'], ctx['overlay']
    ov = caption.NativeCaptionOverlay(log=lambda msg: None)
    detail = ['nasceu %r/%r' % (getattr(ov, 'plate_mode', None),
                                getattr(ov, 'opacity', None))]
    ov.set_visual(plate='normal')
    n = ov._measure('ola mundo', '')
    ov.set_visual(plate='tight')
    t = ov._measure('ola mundo', '')
    style = ov._caption_style()
    # O splat corre contra o modulo do ctx, que e' o MUTANTE quando o
    # `--neg-arm` plantou um: o overlay real chama o `_layout` importado no
    # namespace DELE, e uma copia mutada noutro modulo nao o alcanca.
    try:
        geometry = overlay._layout('ola mundo', '', 1.0, 1920, THEME, **style)
        overlay._premultiplied_bitmap(*geometry[:4], 1.0, THEME, None, 0.0,
                                      **style)
        style_ok = True
        err = ''
    except TypeError as exc:
        style_ok = False
        err = repr(exc)
    detail.extend(['normal %r tight %r' % (n, t), 'estilo %r' % (style,),
                   'splat=%s%s' % (style_ok, (' erro=' + err) if err else '')])
    ok = (style_ok
          and n[0] - t[0] >= WIDTH_SAVED
          and n[1] - t[1] >= HEIGHT_SAVED)
    return ok, ' | '.join(detail)


ARMS = {'A1': arm_a1, 'A2': arm_a2, 'A3': arm_a3, 'A4': arm_a4,
        'A5': arm_a5, 'A6': arm_a6, 'A7': arm_a7, 'A8': arm_a8,
        'A9': arm_a9}

#: Cada mutante muda UMA ancora (que tem de existir uma vez) numa COPIA do fonte.
MUTANTS = (
    {'name': 'M1 a placa ignora o modo tight',
     'file': 'overlay_paint.py',
     'anchor': "    tight = str(plate_mode or 'normal').lower() == 'tight'",
     'mutant': '    tight = False',
     'arms': ('A1', 'A2', 'A4')},
    {'name': 'M2 a opacidade nao escala o alfa',
     'file': 'overlay_paint.py',
     'anchor': '    if alpha < 1.0:',
     'mutant': '    if False:',
     'arms': ('A5',)},
    {'name': 'M3 a caixa corta a ultima letra',
     'file': 'overlay_paint.py',
     'anchor': "        width = min(int(widest + g['x_text'] + g['pad_r']) + 1, int(max_text))",
     'mutant': "        width = min(int(widest + g['x_text'] + g['pad_r']) - 8, int(max_text))",
     'arms': ('A3',)},
    {'name': 'M4 o overlay volta a nascer com a placa LARGA',
     'file': 'caption_overlay.py',
     'anchor': "                   or _SHIPPED_VISUAL.get('plate') or 'tight').lower()",
     'mutant': "                   or 'normal').lower()",
     'arms': ('A6',)},
    {'name': 'M5 a pagina perde o controlo do fundo',
     'file': '../panel/panel.html',
     'anchor': 'id="caption-plate-select"',
     'mutant': 'id="caption-plate-select-removido"',
     'arms': ('A8',)},
    {'name': 'M6 a pagina deixa de enviar a escolha',
     'file': '../panel/panel.js',
     'anchor': 'bridge.setCaptionVisual({ plate: plate, opacity: opacity });',
     'mutant': 'void 0;',
     'arms': ('A8',)},
    {'name': 'M8 o layout recusa o estilo inteiro (opacity)',
     'file': 'overlay_paint.py',
     'anchor': "            plate_mode='normal', opacity=1.0):",
     'mutant': "            plate_mode='normal'):",
     'arms': ('A9',)},
    {'name': 'M7 o shell perde a entrada do mapa',
     'file': 'sotto_webview.py',
     'anchor': "            'caption-visual': ('host', '_caption_visual'),",
     'mutant': "",
     'arms': ('A8',)},
)


def load_copy(rel: str, name: str, source: str, folder: str):
    dest = os.path.join(folder, os.path.basename(rel))
    with io.open(dest, 'w', encoding='utf-8', newline='') as fh:
        fh.write(source)
    spec = importlib.util.spec_from_file_location(name, dest)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def real_ctx() -> dict:
    import caption_overlay as caption
    import caption_settings as settings
    return {'overlay': op, 'caption': caption, 'settings': settings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--neg-arm', action='store_true',
                        help='muta COPIAS e exige as arms nomeadas RED (rc=1)')
    args = parser.parse_args(argv)
    ctx = real_ctx()

    if args.neg_arm:
        print('NEGATIVE ARM -- oito mutantes em COPIA; cada um nomeia a arm')
        caught = 0
        for mutant in MUTANTS:
            source = io.open(os.path.join(WEBVIEW, mutant['file']),
                             encoding='utf-8', newline='').read()
            if source.count(mutant['anchor']) != 1:
                add(False, mutant['name'] + ' NAO FOI CONSTRUIDO',
                    'a ancora ocorre %d vez(es)' % source.count(mutant['anchor']))
                continue
            mutated = source.replace(mutant['anchor'], mutant['mutant'], 1)
            if mutant['file'].endswith(('.html', '.js')) or \
                    mutant['file'] == 'sotto_webview.py':
                # Mutante de FIACAO: o texto mutado vai para o leitor do A8,
                # sob a MESMA chave que o `src` calcula (`_source_path`).
                sub = dict(ctx)
                sub['sources'] = {_source_path(mutant['file']): mutated}
                red = []
                for name in mutant['arms']:
                    ok, _detail = ARMS[name](sub)
                    if not ok:
                        red.append(name)
                hit = sorted(red) == sorted(mutant['arms'])
                caught += 1 if hit else 0
                add(hit, mutant['name'], 'RED em %s' % ', '.join(red)
                    if red else 'INERTE -- nenhuma arm nomeada caiu')
                continue
            with tempfile.TemporaryDirectory(prefix='plate-mut-') as folder:
                mod = load_copy(mutant['file'], 'mutant_' + mutant['name'][:2],
                                mutated, folder)
                sub = dict(ctx)
                sub['overlay' if mutant['file'] == 'overlay_paint.py'
                    else 'caption'] = mod
                red = []
                for name in mutant['arms']:
                    ok, _detail = ARMS[name](sub)
                    if not ok:
                        red.append(name)
            hit = sorted(red) == sorted(mutant['arms'])
            caught += 1 if hit else 0
            add(hit, mutant['name'], 'RED em %s' % ', '.join(red)
                if red else 'INERTE -- nenhuma arm nomeada caiu')
        print('')
        print('%d/%d mutantes apanhados' % (caught, len(MUTANTS)))
        print('VERDICT: %s' % ('NEG-ARM PASS (mutantes apanhados)'
                               if caught == len(MUTANTS)
                               else 'NEG-ARM FAIL (mutante inerte)'))
        return 1 if caught == len(MUTANTS) else 0

    table()
    for name in ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9'):
        ok, detail = ARMS[name](ctx)
        add(ok, name, detail)
    bad = [r for r in rows if not r[0]]
    print('')
    print('%d/%d GREEN' % (len(rows) - len(bad), len(rows)))
    if bad:
        print('VERDICT: FAIL')
        for _ok, name, detail in bad:
            print('  - %s  %s' % (name, detail))
        return 1
    print('VERDICT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
