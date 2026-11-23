#!/usr/bin/env python
# NO-BUG: conduz `_yt_clock_static` num shell falso; nao reproduz os oito minutos de imagem congelada no player do dono.
"""O RELOGIO PARADO E' PAUSA -- mesmo quando a bandeira `paused` diz que nao.

CASO MEDIDO (log do dono, 2026-11-09 21:29:57 -> 21:36, oito minutos): o ecra
ficou com `Reeling like a desperado`, `YOUTUBE_TICK_MS ... rows=2 why='painted'`
a repetir a MESMA linha, e NENHUMA linha de pausa/fim em toda a janela -- a foto
do DOM devolvia `paused=False` e `currentTime` nao avancava. Sem borda de pausa,
nada apagou os pixels: a legenda ficou congelada para sempre.

A CURA E' A MEDIDA: um video a andar nunca repete o `currentTime`. Se ele fica
imovel por `CLOCK_STATIC_PAUSE_S`, o player esta' parado, e o `_yt_pause_edge`
apaga os pixels pela MESMA via da pausa declarada.

AS ARMS (a funcao REAL, `ExternalCaptionWatcher._yt_clock_static`, conduzida com um shell
falso que so' tem o estado dela)

  A1  `t` avanca a cada leitura -> nao parado, held 0.
  A2  `t` imovel por 0,5 s (menos que o piso) -> nao parado.
  A3  `t` imovel por 2,5 s -> PARADO, com held >= 2,0 (o numero, nao um booleano).
  A4  `t` AUSENTE -> nao parado, e o estado de uma serie parada e' LIMPO: ausencia
      de medida nunca vira afirmacao de pausa.
  A5  `t` retoma depois de uma serie parada -> nao parado, held 0 (a borda de
      volta tem de poder disparar).
  A6  A FIACAO: `_yt_cdp_snapshot` chama `_yt_clock_static` e escreve o resultado
      em `yt_cdp_paused` ANTES de `_yt_pause_edge` -- lido por `ast`, no corpo da
      funcao real, e na ordem certa.

`--neg-arm` muta uma COPIA do modulo: o piso vai a 1e9 (M1), a guarda de `t`
ausente passa a devolver parado (M2) e a fiacao do OR e' arrancada (M3). Exige
A3, A4 e A6 vermelhas, e devolve 1 quando as apanha.
"""
import argparse
import ast
import io
import os
import re
import importlib.util
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


class FakeShell(object):
    """So' o estado que `_yt_clock_static` le' e escreve."""


def measure(shell, snap, now):
    return shell._yt_clock_static(snap, now=now)


def _wiring_ok(path):
    """A6: a chamada existe dentro de `_yt_cdp_snapshot`, antes do `_yt_pause_edge`."""
    src = io.open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'ExternalCaptionWatcher':
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == '_yt_cdp_snapshot':
                    body = fn
    if body is None:
        return False, 'sem _yt_cdp_snapshot'
    seg = ast.get_source_segment(src, body) or ''
    call = seg.find('_yt_clock_static(')
    pause = seg.find('_yt_pause_edge(')
    if call < 0:
        return False, 'a chamada a _yt_clock_static nao esta no corpo'
    if pause < 0:
        return False, 'sem _yt_pause_edge no corpo'
    if call > pause:
        return False, 'a chamada vem DEPOIS do _yt_pause_edge'
    if not re.search(r'yt_cdp_paused\s*=\s*True', seg):
        return False, 'o resultado nao chega a yt_cdp_paused'
    return True, 'ok'


def run(module, shell_path, label):
    ok = 0
    total = 0
    failed = []

    def arm(name, good, detail):
        nonlocal ok, total
        total += 1
        if good:
            ok += 1
        else:
            failed.append(name)
        print('  %-3s %-34s %s' % (name, 'PASS' if good else 'FAIL', detail))

    cls = module.ExternalCaptionWatcher
    FakeShell.CLOCK_STATIC_PAUSE_S = cls.CLOCK_STATIC_PAUSE_S
    t0 = 1000.0
    S = cls.CLOCK_STATIC_PAUSE_S

    # A1 -- relogio a andar
    sh = FakeShell()
    r1 = cls._yt_clock_static(sh, {'t': 10.0}, now=t0)
    r2 = cls._yt_clock_static(sh, {'t': 10.5}, now=t0 + 0.3)
    arm('A1', r1 == (False, 0.0) and r2 == (False, 0.0), 'movendo: %r %r' % (r1, r2))

    # A2 -- imovel abaixo do piso
    sh = FakeShell()
    cls._yt_clock_static(sh, {'t': 42.0}, now=t0)
    r = cls._yt_clock_static(sh, {'t': 42.0}, now=t0 + 0.5)
    arm('A2', r == (False, 0.5), 'imovel 0,5 s: %r' % (r,))

    # A3 -- imovel acima do piso: PARADO, com o numero
    sh = FakeShell()
    cls._yt_clock_static(sh, {'t': 42.0}, now=t0)
    r = cls._yt_clock_static(sh, {'t': 42.0}, now=t0 + 2.5)
    arm('A3', bool(r[0]) and r[1] >= S, 'imovel 2,5 s: %r (piso %.1f)' % (r, S))

    # A4 -- `t` ausente nao e' pausa, e limpa a serie
    sh = FakeShell()
    cls._yt_clock_static(sh, {'t': 42.0}, now=t0)
    cls._yt_clock_static(sh, {'t': 42.0}, now=t0 + 3.0)
    r = cls._yt_clock_static(sh, {'t': None}, now=t0 + 3.1)
    cleared = getattr(sh, '_yt_ct_val', 'x') is None
    arm('A4', r == (False, 0.0) and cleared, 't ausente: %r val=%r' % (r, sh._yt_ct_val))

    # A5 -- retoma
    sh = FakeShell()
    cls._yt_clock_static(sh, {'t': 7.0}, now=t0)
    cls._yt_clock_static(sh, {'t': 7.0}, now=t0 + 3.0)
    r = cls._yt_clock_static(sh, {'t': 7.25}, now=t0 + 3.2)
    arm('A5', r == (False, 0.0), 'retomou: %r' % (r,))

    # A6 -- fiacao
    good, detail = _wiring_ok(shell_path)
    arm('A6', good, detail)

    verdict = 'PASS' if not failed else 'FAIL (%s)' % ','.join(failed)
    print('%s VERDICT: %s -- %d/%d' % (label, verdict, ok, total))
    return 0 if not failed else 1


def _load(path):
    """The module at `path`, imported once under a name that follows the file.

    O DIRECTORIO DA APP VAI SEMPRE NO `sys.path`: o shell importa os irmaos por
    nome (`youtube_reveal`, `youtube_cdp_source`), e uma copia fora da arvore nao
    carrega sem eles.
    """
    app = os.path.dirname(os.path.abspath(SHELL))
    for d in (app, os.path.dirname(os.path.abspath(path))):
        if d not in sys.path:
            sys.path.insert(0, d)
    name = 'sotto_webview_ytclock'
    if os.path.abspath(path) != os.path.abspath(SHELL):
        name = 'sotto_webview_ytclock_' + os.path.basename(path).replace('.py', '')
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def neg_arm():
    tmp = tempfile.mkdtemp(prefix='yt-clock-static-')
    copy = os.path.join(tmp, 'sotto_webview.py')
    src = io.open(SHELL, encoding='utf-8').read()
    caught = 0
    want = []

    def mutant(label, text, needle, repl):
        nonlocal caught
        mutated = text.replace(needle, repl, 1)
        if mutated == text:
            print('  %s NOT-CAUGHT (mutacao nao aplicou)' % label)
            return
        path = os.path.join(tmp, 'mut_%s.py' % label)
        io.open(path, 'w', encoding='utf-8').write(mutated)
        rc = _run_mutant(path, label)
        if rc == 1:
            caught += 1

    def _run_mutant(path, label):
        mod = _load(path)
        print('--- mutante %s' % label)
        rc = run(mod, path, 'MUTANT %s' % label)
        return rc

    print('=== NEG-ARM ===')
    mutant('M1', src, 'CLOCK_STATIC_PAUSE_S = 2.0',
           'CLOCK_STATIC_PAUSE_S = 1000000000.0')
    mutant('M2', src,
           "        if t is None:\n            self._yt_ct_val = None\n            self._yt_ct_since = 0.0\n            self._yt_ct_verdict = (False, 0.0)",
           "        if t is None:\n            self._yt_ct_val = None\n            self._yt_ct_since = 0.0\n            self._yt_ct_verdict = (True, 99.0)")
    mutant('M3', src, '                    self.yt_cdp_paused = True\n',
           '                    pass\n')
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    if caught == 3:
        print('NEG-ARM: PASS -- %d/3 mutantes apanhados' % caught)
        return 1
    print('NEG-ARM: FAIL -- %d/3 mutantes apanhados' % caught)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--shell', default=SHELL)
    a = ap.parse_args(argv)
    if a.neg_arm:
        return neg_arm()
    mod = _load(a.shell)
    return run(mod, a.shell, 'YT-CLOCK-STATIC')


if __name__ == '__main__':
    sys.exit(main())
