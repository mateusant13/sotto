#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: O BIT DE CLICK-THROUGH QUE O WINDOWS RECUSA -- capacidade/observabilidade copiada do Perssua (2026-11-04); nao corresponde a nenhum id de `_main/bug-ledger.json`.
"""O BIT DE CLICK-THROUGH QUE O WINDOWS RECUSA (2026-11-04).

O QUE FOI COPIADO. Dois projectos que resolvem o mesmo problema dizem a mesma
coisa: o Perssua 0.28.0 reaplica o pedido de mouse do renderer depois de uma
mudanca na janela nativa (`WindowMouseControl ... reapplied renderer
mouse-events request after native window change`, no log dele), e o
`Live-Subtitles` diz no codigo que no Windows o estilo pode nao valer ate' a
moldura ser recalculada (`overlay.py:247-252`).

O QUE O SOTTO FAZIA. `make_click_through` escrevia `WS_EX_TRANSPARENT` e
NINGUEM lia o bit de volta: uma recusa do Windows ficava em silencio, e o
sintoma seria o painel a comer cliques do dono. `apply_click_through` le', e
quando o bit nao pegou insiste uma vez com `SWP_FRAMECHANGED` -- que nao
remapeia a janela, portanto nao acrescenta um flash do primeiro frame.

O QUE ESTE ORACULO JULGA (a funcao REAL, com um `user32` de mentira que obedece
as regras do Windows):
  1. um `SetWindowLongW` que pega -> aplicado na primeira, e ZERO `SetWindowPos`;
  2. um Windows que so' honra o bit DEPOIS de `SWP_FRAMECHANGED` -> aplicado,
     com exactamente um `SetWindowPos` que leva `SWP_FRAMECHANGED`;
  3. um Windows que RECUSA o bit -> `False` e a linha `CLICK_THROUGH_NOT_APPLIED`;
  4. desligar (`enabled=False`) segue o mesmo caminho -- o bit e' removido de
     facto, nao so' pedido;
  5. a funcao NAO usa `ShowWindow`: remapear a janela e' o flash que o
     `panel-startup-flash-census` proibe.

`--neg-arm`: muta uma COPIA de `app/webview/sotto_webview.py` para o
`apply_click_through` antigo (escreve e devolve True sem ler) e exige as arms 2
e 3 a VERMELHO. rc=1 quando apanha (convencao da casa).
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
sys.path.insert(0, WEBVIEW)

GL_EXSTYLE = -20
TRANSPARENT = 0x00000020
FRAMECHANGED = 0x0020
NOMOVE, NOSIZE, NOZORDER, NOACTIVATE = 0x0002, 0x0001, 0x0004, 0x0010


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeWindow(object):
    """O Windows minimo: um estilo, uma politica e um contador de mapas."""

    def __init__(self, policy, start=0):
        self.style = start
        self.policy = policy            # 'immediate' | 'after-framechanged' | 'refuse'
        self.wanted = None
        self.frame_changes = 0
        self.shows = 0

    def GetWindowLongW(self, hwnd, index):
        if index != GL_EXSTYLE:
            raise AssertionError('indice inesperado %r' % (index,))
        return self.style

    def SetWindowLongW(self, hwnd, index, value):
        self.wanted = int(value)
        if self.policy == 'immediate':
            self.style = int(value)
        if self.policy == 'refuse':
            pass                     # o Windows ignora o pedido
        return int(value)

    def SetWindowPos(self, hwnd, after, x, y, cx, cy, flags):
        if flags & FRAMECHANGED:
            self.frame_changes += 1
            if self.policy == 'after-framechanged':
                self.style = int(self.wanted)
        return True

    def ShowWindow(self, hwnd, cmd):
        self.shows += 1
        return True


def run_arms(shell_path=None):
    mod = load_module(shell_path or SHELL, 'sotto_shell_ct')
    rows = []
    logs = []

    def fake(policy, start=0):
        win = FakeWindow(policy, start=start)
        mod.user32 = win
        return win

    # 1) pega na primeira
    win = fake('immediate', start=0)
    ok = mod.apply_click_through(1234, True, log=logs.append)
    rows.append(('applies-first-try', bool(ok) and win.frame_changes == 0
                 and bool(win.style & TRANSPARENT),
                 'ok=%s frame_changes=%d style=%#x' % (ok, win.frame_changes, win.style)))

    # 2) so' pega depois do FRAMECHANGED
    win = fake('after-framechanged', start=0)
    ok = mod.apply_click_through(1234, True, log=logs.append)
    rows.append(('framechanged-retry', bool(ok) and win.frame_changes == 1
                 and bool(win.style & TRANSPARENT),
                 'ok=%s frame_changes=%d style=%#x' % (ok, win.frame_changes, win.style)))

    # 3) recusa do Windows e' NOMEADA
    logs[:] = []
    win = fake('refuse', start=0)
    ok = mod.apply_click_through(1234, True, log=logs.append)
    named = any('CLICK_THROUGH_NOT_APPLIED' in x for x in logs)
    rows.append(('refusal-is-named', (not ok) and named,
                 'ok=%s logs=%s' % (ok, [x[:60] for x in logs])))

    # 4) desligar remove o bit de facto
    win = fake('after-framechanged', start=TRANSPARENT)
    ok = mod.apply_click_through(1234, False, log=logs.append)
    rows.append(('disable-removes-it', bool(ok) and not (win.style & TRANSPARENT),
                 'ok=%s style=%#x' % (ok, win.style)))

    # 5) nao remapeia a janela (o flash)
    win = fake('after-framechanged', start=0)
    mod.apply_click_through(1234, True, log=logs.append)
    rows.append(('never-remaps-the-window', win.shows == 0, 'ShowWindow=%d' % win.shows))

    return rows


def main(argv):
    if '--neg-arm' in argv:
        tmp = tempfile.mkdtemp(prefix='sotto-ct-mut-')
        try:
            raw = io.open(SHELL, encoding='utf-8').read()
            anchor = 'def apply_click_through(hwnd, enabled: bool, log=None) -> bool:'
            i = raw.index(anchor)
            j = raw.index('def ', raw.index('\n    return live == want', i))
            dead = (
                'def apply_click_through(hwnd, enabled: bool, log=None) -> bool:\n'
                '    make_click_through(hwnd, bool(enabled))\n'
                '    return True\n\n\n')
            mutated = raw[:i] + dead + raw[j:]
            if mutated == raw:
                print('NEG-ARM IMPOSSIVEL: a ancora do mutante nao esta no fonte')
                return 2
            path = os.path.join(tmp, 'sotto_webview_ct_mut.py')
            io.open(path, 'w', encoding='utf-8', newline='\n').write(mutated)
            rows = run_arms(shell_path=path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        red = {n for n, ok, _d in rows if not ok}
        want = {'framechanged-retry', 'refusal-is-named'}
        missed = want - red
        for name, ok, detail in rows:
            print('%-24s %s %s' % (name, 'PASS' if ok else 'RED', detail))
        print('')
        print('mutante escreve-e-nao-le APANHADO' if not missed
              else 'mutante PASSOU: %s' % ', '.join(sorted(missed)))
        print('NEG-ARM: %s (vermelhas: %s)'
              % ('PASS' if not missed else 'FAIL', ', '.join(sorted(red)) or 'nenhuma'))
        return 1

    rows = run_arms()
    for name, ok, detail in rows:
        print('%-24s %s %s' % (name, 'PASS' if ok else 'RED', detail))
    bad = [n for n, ok, _d in rows if not ok]
    print('')
    print('VERDICT: %s (%d/%d arms)'
          % ('RED' if bad else 'PASS', len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
