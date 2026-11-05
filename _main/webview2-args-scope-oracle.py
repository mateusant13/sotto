# NO-BUG: O PORTO DE DEPURACAO DO WEBVIEW2 PERTENCE A ESTE PROCESSO, NAO A CAIXA.
"""O PORTO DE DEPURACAO DO WEBVIEW2 PERTENCE A ESTE PROCESSO, NAO A CAIXA.

O DEFEITO QUE ESTE ORACULO RECUSA (medido 2026-11-04). O ambiente desta sessao
tem `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333`: um
valor que QUALQUER processo herdou passa a abrir um porto de depuracao em todas
as janelas WebView2 que a app criar. Duas consequencias, e a segunda e' a grave:

  1. uma app de terceiros com o mesmo loader (Stremio e' WebView2) fica com um
     porto de depuracao aberto se for largada por um processo contaminado;
  2. o MESMO binario comporta-se diferente consoante quem o largou -- a sessao
     do dono nao tem o valor, a de uma lane tem. Uma medicao verde numa lane
     deixa de dizer nada sobre o que ele ve.

O PRODUTO NAO PRECISA DO PORTO: a fonte de legenda do YouTube le o browser do
DONO em 9222 (`youtube_cdp_source.DEFAULT_PORT`), nunca o WebView2 desta app.
Portanto o valor herdado e' REMOVIDO por omissao e so' um pedido explicito
(`--cdp-port N` / `SOTTO_CDP_PORT=N`) o pos.

ARMS
  1  heredado, sem pedido             -> 'cleared', value None, dropped gravado
  2  nada heredado, sem pedido        -> 'none'
  3  heredado + --cdp-port 9400       -> 'set' e o valor e' UM argumento: 9400
  4  heredado 9333 + pedido 9400      -> 'set' 9400 (o pedido ganha)
  5  porto fora de 1..65535           -> recusa (ValueError)
  6  apply('cleared') num mapping     -> a chave DESAPARECE do mapping
  7  apply('set') num mapping         -> a chave fica com o valor pedido
  8  apply('none') num mapping        -> o mapping nao e' tocado
  9  A FUNCAO REAL DA SHELL, ambiente envenenado, sem bandeira -> a chave sai
     do `os.environ` do processo e a decisao diz 'cleared'
 10  A FUNCAO REAL DA SHELL com `--cdp-port 9400` -> a chave fica com 9400
 11  A FUNCAO REAL DA SHELL com `SOTTO_CDP_PORT=9401` -> a chave fica com 9401
 12  A FUNCAO REAL DA SHELL sem nada -> nenhuma chave e nenhum porto

O NEGATIVO (`--neg-arm`) muta COPAS e exige que os arms 1/6, 2/8 e 9 fiquem
vermelhos: um oraculo que nao apanha o mutante nao e' oraculo.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
MODULE = os.path.join(WEBVIEW, 'webview2_args.py')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _judge(module_path=MODULE, shell_path=SHELL):
    """Corre os 12 arms contra os ficheiros dados. Devolve [(id, ok, detail)]."""
    out = []

    mod = _load('_wv2_args_under_test', module_path)
    KEY = mod.INHERIT_VAR

    # ---- 1-5: a decisao pura ------------------------------------------------
    d = mod.plan('--remote-debugging-port=9333', None)
    ok = d['action'] == 'cleared' and d['value'] is None and d['dropped'] == \
        '--remote-debugging-port=9333'
    out.append((1, ok, 'plan(herdado, sem pedido) -> %r' % (d,)))

    d = mod.plan(None, None)
    out.append((2, d['action'] == 'none' and d['value'] is None and not d['dropped'],
                'plan(nada, sem pedido) -> %r' % (d,)))

    d = mod.plan('--remote-debugging-port=9333', '9400')
    ok = (d['action'] == 'set'
          and d['value'] == '--remote-debugging-port=9400'
          and d['dropped'] == '--remote-debugging-port=9333')
    out.append((3, ok, 'plan(herdado, 9400) -> %r' % (d,)))

    d = mod.plan('--another-flag', 9400)
    out.append((4, d['action'] == 'set' and d['value'] == '--remote-debugging-port=9400',
                'plan(outro valor, 9400) -> %r' % (d,)))

    try:
        mod.plan(None, 70000)
        out.append((5, False, 'plan(porto=70000) NAO recusou'))
    except ValueError as exc:
        out.append((5, True, 'plan(porto=70000) recusou: %s' % (exc,)))

    # ---- 6-8: a mutacao do mapping -----------------------------------------
    env = {KEY: '--remote-debugging-port=9333'}
    got = mod.apply(mod.plan(env[KEY], None), env)
    out.append((6, KEY not in env and got['present'] is False,
                'apply(cleared) -> env=%r got=%r' % (env, got)))

    env = {KEY: '--remote-debugging-port=9333'}
    got = mod.apply(mod.plan(env[KEY], 9400), env)
    out.append((7, env.get(KEY) == '--remote-debugging-port=9400' and got['present'],
                'apply(set) -> env=%r' % (env,)))

    env = {}
    got = mod.apply(mod.plan(None, None), env)
    out.append((8, env == {} and got['action'] == 'none' and got['present'] is False,
                'apply(none) -> env=%r' % (env,)))

    # ---- 9-12: a FUNCAO REAL da shell, no ambiente do PROCESSO -------------
    # A shell importa os seus irmaos (`hot_reload`, `theme_knobs`, ...) por
    # nome simples, porque em producao e' o proprio `app/webview` que esta' no
    # `sys.path` quando o `run.cmd` a larga. O oraculo reproduz essa condicao.
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    shell = _load('_sotto_shell_under_test_' + str(os.getpid()), shell_path)
    shout = io.StringIO()
    real_stdout, real_environ = sys.stdout, os.environ
    saved = {k: real_environ.get(k) for k in
             (KEY, 'SOTTO_CDP_PORT', 'WEBVIEW2_DEFAULT_BACKGROUND_COLOR',
              'COREWEBVIEW2_FORCED_HOSTING_MODE')}
    try:
        def _arm(n, argv, expect_action, expect_value, pre):
            for k in (KEY, 'SOTTO_CDP_PORT'):
                real_environ.pop(k, None)
            for k, v in pre.items():
                real_environ[k] = v
            sys.stdout = io.StringIO()
            try:
                res = shell.apply_webview2_environment(argv)
            finally:
                sys.stdout = real_stdout
            ba = res.get('browser_args') or {}
            got = real_environ.get(KEY)
            ok = (ba.get('action') == expect_action and got == expect_value
                  and ba.get('present') == (KEY in real_environ))
            out.append((n, ok, 'apply_webview2_environment(%r) pre=%r -> '
                               'action=%r env=%r dropped=%r'
                        % (argv, pre, ba.get('action'), got, ba.get('dropped'))))

        _arm(9, [], 'cleared', None, {KEY: '--remote-debugging-port=9333'})
        _arm(10, ['--cdp-port', '9400'], 'set', '--remote-debugging-port=9400', {})
        _arm(11, [], 'set', '--remote-debugging-port=9401', {'SOTTO_CDP_PORT': '9401'})
        _arm(12, ['--cdp-port=9402'], 'set', '--remote-debugging-port=9402', {})
    finally:
        sys.stdout = real_stdout
        for k, v in saved.items():
            real_environ.pop(k, None)
            if v is not None:
                real_environ[k] = v
    return out


def _run(module_path=MODULE, shell_path=SHELL, verbose=True):
    try:
        arms = _judge(module_path, shell_path)
    except Exception as exc:  # noqa: BLE001 - um oraculo que rebenta e' RED
        if verbose:
            print('RED  a execucao rebentou: %r' % (exc,))
        return False
    total = len(arms)
    good = sum(1 for _n, ok, _d in arms if ok)
    for n, ok, detail in arms:
        if verbose:
            print('  %s  a%-2d %s' % ('ok  ' if ok else 'RED ', n, detail))
    if verbose:
        print('VERDICT: %s  %d/%d arms' % ('PASS' if good == total else 'FAIL',
                                           good, total))
    return good == total


def _mutate(src, dst, old, new, label):
    """Muta uma COPIA. As ancoras sao escritas com `\n` e os ficheiros do repo
    sao CRLF: comparar o texto cru faria o mutante dizer "ancora ausente" em vez
    de medir, por isso a comparacao e' feita em LF e o CRLF da origem e'
    reposto na escrita."""
    raw = io.open(src, encoding='utf-8', newline='').read()
    crlf = '\r\n' in raw
    body = raw.replace('\r\n', '\n')
    if old not in body:
        raise SystemExit('MUTANTE IMPOSSIVEL (%s): ancora ausente em %s' % (label, src))
    out = body.replace(old, new, 1)
    if crlf:
        out = out.replace('\n', '\r\n')
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def negative_arm():
    """Muta COPAS e exige os arms certos vermelhos."""
    tmp = tempfile.mkdtemp(prefix='wv2args-', dir=os.environ.get('TMPDIR') or None)
    cases = []
    try:
        # M1: o plan deixa de limpar -- arms 1 e 6 caem.
        m1 = os.path.join(tmp, 'webview2_args_firstcome.py')
        _mutate(MODULE, m1,
                "    if inherited:\n        return {'action': 'cleared', 'value': None, 'dropped': dropped}",
                "    if inherited:\n        return {'action': 'set', 'value': inherited, 'dropped': ''}",
                'M1 first-come')
        cases.append(('M1 o plano volta a aceitar o valor herdado', m1, SHELL, (1, 6)))

        # M2: o apply nega-se a remover -- arm 6 cai, e o 9 tambem.
        m2 = os.path.join(tmp, 'webview2_args_nopop.py')
        _mutate(MODULE, m2,
                "        env.pop(INHERIT_VAR, None)",
                "        pass  # M2",
                'M2 no-pop')
        # O arm 9 carrega o modulo REAL por nome (a shell importa-o do seu
        # `sys.path`), logo o mutante do modulo NAO o alcanca: so' o arm 6 mede
        # esta mutacao. (Escrever 9 aqui daria um NOT-CAUGHT que acusaria o
        # oraculo por uma expectativa errada dele.)
        cases.append(('M2 o apply deixa a chave no ambiente', m2, SHELL, (6,)))

        # M3: a shell deixa de chamar a decisao -- arms 9/10/12 caem.
        m3 = os.path.join(tmp, 'sotto_webview_nocall.py')
        _mutate(SHELL, m3,
                "    import webview2_args\n",
                "    import types as _t\n"
                "    webview2_args = _t.SimpleNamespace(\n"
                "        INHERIT_VAR='WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS',\n"
                "        plan=lambda v, p: {},\n"
                "        apply=lambda d: {'action': 'none', 'present': True,\n"
                "                         'value': os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'),\n"
                "                         'dropped': ''})\n",
                'M3 no-call')
        cases.append(('M3 a shell nao escopa o ambiente', MODULE, m3, (9, 10, 12)))

        fails = 0
        for label, mp, sp, want_red in cases:
            arms = _judge(mp, sp)
            reds = {n for n, ok, _d in arms if not ok}
            caught = all(n in reds for n in want_red)
            print('  %s  %s -- esperados vermelhos %s, vermelhos %s'
                  % ('CAUGHT' if caught else 'NOT-CAUGHT', label,
                     list(want_red), sorted(reds)))
            if not caught:
                fails += 1
        print('NEG-ARM %s cases=%d caught=%d' % ('PASS' if fails == 0 else 'FAIL',
                                                 len(cases), len(cases) - fails))
        return fails == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta copas e exige os arms certos vermelhos')
    ap.add_argument('--module', default=MODULE)
    ap.add_argument('--shell', default=SHELL)
    a = ap.parse_args(argv)
    if a.neg_arm:
        # A CONVENCAO DA CASA: o braco negativo devolve 1 quando APANHA os
        # mutantes (o passo declara-se `:expectred`), e 0 quando NAO os apanha --
        # ao contrario de um passo normal. Trocar os dois faz o mutante passar
        # como um oraculo verde, que e' o defeito que a bateria de 2026-11-03
        # apanhou em cinco `--neg-arm` deste repo.
        return 1 if negative_arm() else 0
    return 0 if _run(a.module, a.shell) else 1


if __name__ == '__main__':
    sys.exit(main())
