# NO-BUG: A LEGENDA E' A DO YOUTUBE -- oraculo do ESTILO e da ausencia de animacao. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A LEGENDA E' A DO YOUTUBE -- oraculo do ESTILO e da ausencia de animacao.

AS DUAS ORDENS DO DONO, verbatim:

  2026-11-03, sobre uma captura com placa cinzenta e fundo: *"ESSE ESTILO DE
  LEGENDA E' DO YOUTUBE. NAO SOTTO."*
  2026-11-03, sobre a mesma captura: *"e ta com animacao fade in que eu JA MANDEI
  VOCE TIRAR"*.

O QUE ELE VE NA TELA E' A JANELA NATIVA (`caption_overlay`), NAO O `caption.html`:
corrigir CSS no painel nao chega ao ecra. Por isso este oraculo julga o ESTILO
nativo, sem abrir janela nenhuma -- a metade pura (`overlay_paint`) desenha o
bitmap num `Bitmap` de memoria e o oraculo le' os PIXEIS.

AS ARMS:

  1. `theme-is-youtube` -- o tema por omissao e' Arial, branco, contorno preto
     solido, sem placa, centrado, sem farol, peso 400.
  2. `no-second-ink`      -- `prevColor == liveColor`: o YouTube nao tem uma
     segunda cor para a linha antiga.
  3. `no-fade`            -- `FADE_ON` e' False e `_fade_alpha()` devolve 255.
  4. `no-plate-pixels`    -- no bitmap RENDERIZADO (o que vai para a tela) nenhum
     pixel de fundo existe: o canto e' transparente e nao ha' pixel colorido.
  5. `theme-not-branded`  -- a shell NAO deixa o design do painel vestir a
     legenda.
  6. `asr-does-not-override` -- o caminho do ASR nao empurra texto enquanto o
     player fornece linhas (o defeito medido 00:01:41-00:01:46).

USO:
    python _main/caption-style-oracle.py
    python _main/caption-style-oracle.py --neg-arm   # muta uma COPIA e exige RED
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
sys.path.insert(0, WEBVIEW)

SAMPLE = ['maior pra ficar por último, entendeu?', 'Então eles estão acabando,']
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')


def read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def render_pixels(rows=None):
    """(largura, altura, [(r,g,b,a)] dos pixeis do bitmap) -- pelo caminho real."""
    import clr
    clr.AddReference('System.Drawing')
    from System.Drawing import Rectangle
    from System.Drawing.Imaging import ImageLockMode, PixelFormat
    import overlay_paint

    theme = overlay_paint._normalise_theme(overlay_paint._THEME_DEFAULT)
    text = '\n'.join(rows or SAMPLE)
    lines, prev, width, height, _scrolled = overlay_paint._layout(
        text, '', 1.0, 1920, theme)
    bmp = overlay_paint._premultiplied_bitmap(lines, prev, width, height, 1.0,
                                              theme, None)
    data = bmp.LockBits(Rectangle(0, 0, width, height), ImageLockMode.ReadOnly,
                        PixelFormat.Format32bppPArgb)
    stride = abs(int(data.Stride))
    buf = (ctypes_bytes * (stride * height))()
    import ctypes
    ctypes.memmove(buf, ctypes.c_void_p(int(data.Scan0.ToInt64())),
                   stride * height)
    bmp.UnlockBits(data)
    bmp.Dispose()
    out = []
    for y in range(0, height, 2):
        row = y * stride
        for x in range(0, width, 2):
            b, g, r, a = buf[row + x * 4:row + x * 4 + 4]
            out.append((r, g, b, a))
    return width, height, out


import ctypes  # noqa: E402  (antes do primeiro render)
ctypes_bytes = ctypes.c_ubyte


def render_probe_alpha(width, height):
    """O alfa de um pixel no MEIO da borda de cima do bitmap branco."""
    import clr
    clr.AddReference('System.Drawing')
    import overlay_paint
    theme = overlay_paint._normalise_theme(overlay_paint._THEME_DEFAULT)
    text = '\n'.join(SAMPLE)
    lines, prev, w, h, _ = overlay_paint._layout(text, '', 1.0, 1920, theme)
    bmp = overlay_paint._premultiplied_bitmap(lines, prev, w, h, 1.0, theme, None)
    try:
        return (bmp.GetPixel(w // 2, 1).ToArgb() >> 24) & 0xFF
    finally:
        bmp.Dispose()


def arms():
    import overlay_paint
    import caption_overlay

    theme = overlay_paint._normalise_theme(overlay_paint._THEME_DEFAULT)
    out = []

    want = {
        'fontFamily': 'Arial',
        'livePx': 38.0,
        'liveWeight': 400,
        'plate': None,
        'align': 'center',
        'led': None,
        'liveColor': (255, 255, 255, 255),
        'strokeColor': (0, 0, 0, 255),
    }
    wrong = {k: (theme.get(k), v) for k, v in want.items() if theme.get(k) != v}
    out.append(('theme-is-youtube', not wrong, 'errado=%r' % (wrong,)))

    same_ink = (theme.get('prevColor') == theme.get('liveColor')
                and theme.get('prevPx') == theme.get('livePx'))
    out.append(('no-second-ink', same_ink,
                'prev=%r live=%r' % (theme.get('prevColor'), theme.get('liveColor'))))

    class _Stub:
        FADE_ON = caption_overlay.NativeCaptionOverlay.FADE_ON
        _fade_t0 = 0.0

    alpha = caption_overlay.NativeCaptionOverlay._fade_alpha(_Stub())
    no_fade = (caption_overlay.NativeCaptionOverlay.FADE_ON is False
               and alpha == 255)
    out.append(('no-fade', no_fade,
                'FADE_ON=%r alpha=%r' % (_Stub.FADE_ON, alpha)))

    width, height, px = render_pixels()
    # A PLACA COM CANTOS REDONDOS NAO TOCA O CANTO (medido: o canto e'
    # transparente mesmo com placa). O ponto que a denuncia e' o MEIO da borda
    # de cima, a 1 px da aresta -- ali a placa esta' sempre, com ou sem raio.
    corner = [p for p in px[:6]]
    opaque = [p for p in px if p[3] > 200]
    tinted = [p for p in opaque
              if max(p[:3]) - min(p[:3]) > 24 and sum(p[:3]) > 90]
    top_alpha = render_probe_alpha(width, height)
    plate_free = (top_alpha == 0 and not tinted
                  and len(opaque) < len(px) // 3)
    out.append(('no-plate-pixels', plate_free,
                'borda_superior=%d opacos=%d/%d coloridos=%d'
                % (top_alpha, len(opaque), len(px), len(tinted))))

    shell = read(SHELL)
    branded = ('set_theme(self._brand_tokens_last)' in shell
               or 'set_theme(theme)' in shell)
    forced = shell.count('set_theme(overlay_paint._THEME_DEFAULT)') + \
        shell.count('set_theme(_op._THEME_DEFAULT)')
    out.append(('theme-not-branded', forced >= 2 and not branded,
                'forced=%d branded=%s' % (forced, branded)))

    gated = ('_yt_owner_until' in shell
             and 'CAPTION_OVERLAY_DROP reason=external-captions' in shell)
    out.append(('asr-does-not-override', gated, 'gated=%s' % gated))

    # DOIS LADOS NO MESMO ARM (2026-11-04): o dono viu
    # `CAPTION_OVERLAY_PUSH visible=true` e NAO VIU a legenda. `visible` e' o que
    # NOS dissemos ao `ShowWindow`; a pergunta dele e' se a janela esta' DENTRO
    # de um monitor. O arm executa `_screen_proof` em DUAS janelas que nunca sao
    # mostradas (uma dentro do ecra, uma fora): se a funcao respondesse sempre
    # `True`, o caso de fora a derrubava -- o controle negativo vive aqui, nao
    # num ficheiro mutado.
    import ctypes as _ct
    _u = _ct.windll.user32
    inside = _u.CreateWindowExW(0, 'STATIC', None, 0x80000000, 200, 200, 400, 90,
                                0, 0, 0, 0)
    outside = _u.CreateWindowExW(0, 'STATIC', None, 0x80000000, -4000, -4000,
                                 400, 90, 0, 0, 0, 0)
    try:
        ov = caption_overlay.NativeCaptionOverlay.__new__(
            caption_overlay.NativeCaptionOverlay)
        ov.hwnd = inside
        ov.log = lambda m: None
        a_in = ov._screen_proof()
        ov2 = caption_overlay.NativeCaptionOverlay.__new__(
            caption_overlay.NativeCaptionOverlay)
        ov2.hwnd = outside
        ov2.log = lambda m: None
        a_out = ov2._screen_proof()
    finally:
        _u.DestroyWindow(inside)
        _u.DestroyWindow(outside)
    geom_ok = (a_in[0] is True and a_out[0] is False
               and isinstance(a_in[1], tuple) and a_in[1][2] == 400)
    out.append(('geometry-diz-onde-esta', geom_ok,
                'dentro=%r fora=%r' % (a_in, a_out)))
    wired = ('CAPTION_OVERLAY_GEOMETRY shown=true' in read(
        os.path.join(WEBVIEW, 'caption_overlay.py')))
    out.append(('geometry-publicada-no-show', wired, 'wired=%s' % wired))
    return out


def neg_arm():
    """Uma COPIA mutada tem de derrubar as arms certas."""
    import overlay_paint
    src = read(os.path.join(WEBVIEW, 'overlay_paint.py'))
    tmp = tempfile.mkdtemp(prefix='sotto-style-neg-')
    path = os.path.join(tmp, 'overlay_paint.py')
    cases = [
        ('plate-back', "'plate': None,", "'plate': (0, 0, 0, 255),", 'no-plate-pixels'),
        ('align-left', "'align': 'center',", "'align': 'left',", 'theme-is-youtube'),
        ('bold', "'liveWeight': 400,", "'liveWeight': 700,", 'theme-is-youtube'),
        ('second-ink', "'prevColor': (255, 255, 255, 255),",
         "'prevColor': (255, 255, 255, 90),", 'no-second-ink'),
    ]
    ok = 0
    for name, old, new, arm in cases:
        assert old in src, name
        io.open(path, 'w', encoding='utf-8', newline='').write(
            src.replace(old, new, 1))
        code = ("import sys; sys.path.insert(0, %r)\n"
                "import _main_style_neg as m\n" % tmp)
        # executa o modulo mutado num namespace proprio e julga a MESMA regra
        import importlib.util
        spec = importlib.util.spec_from_file_location('neg_%s' % name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['neg_%s' % name] = mod
        spec.loader.exec_module(mod)
        t = mod._normalise_theme(mod._THEME_DEFAULT)
        if arm == 'theme-is-youtube':
            caught = not (t['fontFamily'] == 'Arial' and t['plate'] is None
                          and t['align'] == 'center' and t['liveWeight'] == 400)
        elif arm == 'no-second-ink':
            caught = not t['prevColor'] == t['liveColor']
        else:
            # PLACA: julga-se no BITMAP, nao no dicionario. Um tema com placa
            # que nao chegasse a pintar pixeis de fundo nao seria o defeito que
            # o dono fotografou.
            lines, prev, w, h, _ = mod._layout('\n'.join(SAMPLE), '', 1.0,
                                               1920, t)
            bmp = mod._premultiplied_bitmap(lines, prev, w, h, 1.0, t, None)
            import clr as _clr
            _clr.AddReference('System.Drawing')
            from System.Drawing import Rectangle as _R
            from System.Drawing.Imaging import ImageLockMode as _IL, PixelFormat as _PF
            d = bmp.LockBits(_R(0, 0, w, h), _IL.ReadOnly, _PF.Format32bppPArgb)
            stride = abs(int(d.Stride))
            raw = (ctypes.c_ubyte * (stride * h))()
            ctypes.memmove(raw, ctypes.c_void_p(int(d.Scan0.ToInt64())),
                           stride * h)
            bmp.UnlockBits(d)
            bmp.Dispose()
            opaque = 0
            tinted = 0
            corner_a = raw[(1 * stride) + (w // 2) * 4 + 3]
            for y in range(0, h, 2):
                for x in range(0, w, 2):
                    off = y * stride + x * 4
                    b, g, r, a = raw[off:off + 4]
                    if a > 200:
                        opaque += 1
                        if max(r, g, b) - min(r, g, b) > 24 and r + g + b > 90:
                            tinted += 1
            # UMA PLACA E' UM CANTO OPACO. O filtro cromatico sozinho nao a ve:
            # uma placa preta tem `max-min == 0` -- foi medido, o mutante passou
            # com o filtro de cor e o canto e' o que a denuncia.
            caught = corner_a > 200 or tinted > 0
        print('NEG-ARM %-14s %s  arm=%s' % (name, 'PASS' if caught else 'FAIL', arm))
        ok += 1 if caught else 0
        try:
            os.remove(path)
        except OSError:
            pass
    # O FADE: uma COPIA do `caption_overlay` com `FADE_ON = True` tem de
    # devolver um alfa abaixo de 255 -- senao o botao nao governa nada e a arm
    # 3 estaria a julgar um comentario.
    cap = read(os.path.join(WEBVIEW, 'caption_overlay.py'))
    cap_path = os.path.join(tmp, 'caption_overlay.py')
    io.open(cap_path, 'w', encoding='utf-8', newline='').write(
        cap.replace('    FADE_ON = False', '    FADE_ON = True', 1))
    import importlib.util as _iu
    spec = _iu.spec_from_file_location('cap_neg', cap_path)
    mod2 = _iu.module_from_spec(spec)
    sys.modules['cap_neg'] = mod2
    spec.loader.exec_module(mod2)

    class _S2:
        FADE_ON = mod2.NativeCaptionOverlay.FADE_ON
        _fade_t0 = __import__('time').monotonic()

    alpha2 = mod2.NativeCaptionOverlay._fade_alpha(_S2())
    caught = alpha2 != 255
    print('NEG-ARM %-14s %s  arm=no-fade alpha=%r'
          % ('fade-back', 'PASS' if caught else 'FAIL', alpha2))
    ok += 1 if caught else 0
    total = len(cases) + 1
    try:
        os.remove(cap_path)
    except OSError:
        pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    print('NEG-ARM VERDICT: %s (%d/%d)' % ('PASS' if ok == total else 'FAIL',
                                           ok, total))
    # A CONVENCAO DA BATERIA (2026-11-03): um `red-as-expected` declara rc=1.
    # "Apanhei todos os mutantes" E' o resultado VERMELHO que o `:expectred`
    # exige, senao o passo passa como se fosse um oraculo normal e o mutante
    # nunca e' recusado. rc=0 quando um mutante escapa (o passo fica vermelho
    # de verdade, e com a frase FAIL no log).
    return 1 if ok == total else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    bad = 0
    results = arms()
    for name, ok, note in results:
        print('%-24s %s  %s' % (name, 'GREEN' if ok else 'RED', note))
        if not ok:
            bad += 1
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if bad == 0 else 'FAIL',
                                        len(results) - bad, len(results)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
