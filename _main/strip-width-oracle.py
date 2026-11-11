#!/usr/bin/env python3
# NO-BUG: recusa a largura auto-medida e fixa a strip em 380; nao restaura o desenho antigo do painel nem julga a estetica dele.
"""THE BOTTOM STRIP IS 380 WIDE, AND THE MEASUREMENT CANNOT WIDEN IT.

Owner, verbatim (2026-11-08T06:30:55Z, `_main/owner-prompts-20261108-40h.md` W6):
*"por que a porra do painel de baixo do sotto ta gigante? restaura como era
antes"*.

MEDIDO na instancia VIVA dele, no log dela:

    `webview-run.log:388721`  03:30:29.147  STRIP_WIDTH from=None to=1040 source=content
    `webview-run.log:388799`  03:30:31.517  WINDOW_GEOMETRY reason=surface-strip window=1040x40@(440,948)
    `webview-run.log:284356`  2026-11-07 10:22:40  window=380x40@(770,948)   <- "como era antes"

660 px wider, 2,74x the area, and the *cause* is a self-referential measurement:
`body[data-surface="strip"] .panel` is `inset:0`, so `strip_width_from_dom()`
read the window's own width, `geometry_for` wrote it into the saved rect, and
the loop had no content in it at all. Two cuts, both measured here:

1. `STRIP_WIDTH = 380` -- the default dock, and `dock_strip` on this machine's
   1920x1032 work area must land EXACTLY on his remembered rect
   (`380x40@(770,948)`), which is what arm A2 measures rather than asserts.
2. `content_width_is_self_measure()` -- the read is REFUSED, by name, when the
   "content" equals the window.

The oracle drives the REAL functions of the module the app runs. `--neg-arm`
removes the guard in a COPY and requires this oracle to fall.

Exit: 0 all arms pass, 1 an arm failed, 2 the negative arm could not be built.
"""
import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORK = {'x': 0, 'y': 0, 'width': 1920, 'height': 1032}   # the owner's work area


def load(path=None):
    sys.path.insert(0, os.path.dirname(SHELL))
    name = 'sotto_webview'
    if path is not None:
        sys.path.insert(0, os.path.dirname(path))
        name = 'sotto_webview_stripmut'
    return __import__(name)


class FakeShell(object):
    """Only what `strip_width_from_dom`/`refresh_strip_width` reach for.

    `window_width_dip` is the ONE window query, split out for exactly this: an
    oracle that has to open a window to test a number can only open the owner's.
    """

    def __init__(self, reading, window_width):
        self.reading = reading
        self.window_width = window_width
        self.hwnd = 1          # truthy: the real method would ask the OS
        self.strip_width_dom = None

    def exec_js(self, _script):
        return self.reading

    def window_width_dip(self):
        return self.window_width


def run(module, label):
    ok = 0
    total = 0
    lines = []

    def arm(name, real, want):
        nonlocal ok, total
        total += 1
        good = real == want
        ok += 1 if good else 0
        lines.append('[%s] %s' % ('PASS' if good else 'FAIL', name))
        lines.append('       real = %r' % (real,))
        lines.append('       want = %r' % (want,))

    def shell(reading='1040', window_width=1040):
        # Bound to the REAL methods: an unbound class call would make the method
        # reach for `self.strip_width_from_dom()` and fail on the fake, which
        # tests the harness instead of the product.
        s = FakeShell(reading, window_width)
        s.strip_width_from_dom = lambda: module.SottoShell.strip_width_from_dom(s)
        s.refresh_strip_width = (lambda reason='oracle':
                                 module.SottoShell.refresh_strip_width(s, reason))
        s.strip_width_live = lambda: module.SottoShell.strip_width_live(s)
        return s

    # A1 the declaration, and it is the one the owner calls "como era antes"
    arm('A1 STRIP_WIDTH e 380 (o pin do rect que ele lembra)', module.STRIP_WIDTH, 380)
    arm('A1b o piso nao nasceu acima do valor (320 <= 380 <= 1040)',
        [module.STRIP_WIDTH_MIN <= module.STRIP_WIDTH <= module.STRIP_WIDTH_MAX,
         module.STRIP_WIDTH_MIN, module.STRIP_WIDTH_MAX], [True, 320, 1040])

    # A2 the dock on HIS work area lands on HIS remembered rect. Pure function.
    rect = module.dock_strip(dict(WORK), height=40)
    arm('A2 dock 1920x1032 @40 -> 380x40 @ (770,948), o rect de 10:22 de ontem',
        [rect['width'], rect['height'], rect['x'], rect['y']],
        [380, 40, 770, 948])

    # A3 the predicate itself, both directions and the "could not ask" case
    p = module.content_width_is_self_measure
    arm('A3a 1040 lido numa janela de 1040 E a janela a medir-se',
        [p(1040, 1040), p(1039, 1040)], [True, True])
    arm('A3b 380 lido numa janela de 1040 e CONTEUDO a serio, e passa',
        [p(380, 1040), p(380.4, 1040)], [False, False])
    arm('A3c largura da janela desconhecida NAO e recusa (nao perguntei != igual)',
        [p(1040, None), p(1040, 0), p('x', 1040)], [False, False, False])

    # A4 the REAL read: refused when it is the window, honoured when it is not
    s = shell('1040', 1040)
    arm('A4a strip_width_from_dom recusa o 1040 que e a propria janela',
        s.strip_width_from_dom(), None)
    s = shell('380', 1040)
    arm('A4b strip_width_from_dom aceita um 380 que e MENOR que a janela',
        s.strip_width_from_dom(), 380.0)

    # A5 and the cache: the refusal must not poison strip_width_dom, which is
    #    what geometry_for adopts into the saved rect.
    s = shell('1040', 1040)
    moved = s.refresh_strip_width(reason='oracle')
    arm('A5a refresh recusa: nao move, e o cache fica em None (nada a adotar)',
        [moved, s.strip_width_dom], [False, None])
    s = shell('380', 1040)
    moved = s.refresh_strip_width(reason='oracle')
    arm('A5b refresh aceita 380: move e guarda 380',
        [moved, s.strip_width_dom], [True, 380])

    # A6 the adoption site must therefore never see a width to adopt on a strip
    #    that fills its window -- `strip_width_live()` stays None.
    s = shell('1040', 1040)
    s.refresh_strip_width(reason='oracle')
    arm('A6 strip_width_live devolve None depois da recusa (a declaracao governa)',
        s.strip_width_live(), None)

    print('\n'.join(lines))
    print('%s: %d/%d' % (label, ok, total))
    return ok, total


def neg_arm():
    src = io.open(SHELL, encoding='utf-8').read()
    line = '        if content_width_is_self_measure(value, win_w):'
    changed = src.replace(line, '        if False:  # MUTANTE: a guarda arrancada')
    if changed == src:
        print('NEG-ARM IMPOSSIVEL -- a guarda nao foi encontrada; o oraculo esta velho')
        return 2
    tmpdir = os.path.join(os.environ.get('TMPDIR') or 'I:\\cc-tmp', 'sotto-strip-arm')
    os.makedirs(tmpdir, exist_ok=True)
    mutant = os.path.join(tmpdir, 'sotto_webview_stripmut.py')
    io.open(mutant, 'w', encoding='utf-8', newline='').write(changed)
    module = load(mutant)
    ok, total = run(module, 'MUTANT')
    # A4a, A5a and A6 are the three that carry the guard; the rest must stand.
    print('NEG-ARM: %s -- %d/%d arms ainda passam' % ('PASS' if ok <= total - 3 else 'FAIL', ok, total))
    # A CASA CONVENTION: the control exits 1 when it CAUGHT the mutant, so
    # `:expectred` reads it as red-as-expected. A control that returns 0 when it
    # catches one is a step waiting for 0 and a mutant never refused.
    return 1 if ok <= total - 3 else 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    ok, total = run(load(), 'STRIP-WIDTH')
    print('VERDICT: %s -- %d/%d arm(s)' % ('PASS' if ok == total else 'FAIL', ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
