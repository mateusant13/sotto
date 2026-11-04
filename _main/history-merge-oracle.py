#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: o historico dobrava a frase porque tratava a linha como fluxo de eventos -- trabalho de CAPACIDADE pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""UMA LINHA E' UMA LINHA -- o historico nao acrescenta, reescreve.

ORDEM DO DONO (2026-11-04), verbatim: *"o historico da legenda e completamente
IMBECIL na logica. fica duplicando frase. fica dando append ou sei la. coisa
burra do cacete."*

MEDIDO na captura dele (painel, 10:01:44 -> 10:01:57): a MESMA linha gravada seis
vezes enquanto crescia --

    Because he's going for these uh these people you know those who's going for.
    ... you know those who's going for there.
    ... for there is.
    ... for there is.            <- identica a anterior
    Is a very.
    ... for there is.            <- a linha LONGA outra vez
    Is a very high chance.

O que este oraculo julga, sempre o CODIGO REAL (nunca uma copia da regra):

  1. `history_merge` -- as nove decisoes: texto igual (skip), a mesma linha a
     crescer (replace), a mesma linha CORRIGIDA para MENOR pelo mesmo `start=`
     do worker (replace), prefixo dentro da janela (replace), prefixo FORA da
     janela (append -- uma repeticao legitima continua a entrar), texto alheio
     (append), sem cauda (append), corpo vazio (skip).
  2. `_history_tail` -- le de um ficheiro gravado a hora e o `start=` da ULTIMA
     linha, que sao as duas testemunhas que `history_merge` usa.
  3. O CAMINHO INTEIRO `history_append` sobre um `HISTORY_ROOT` temporario:
     crescer, repetir, corrigir para menor e mudar de linha tem de deixar
     **duas** linhas no ficheiro, nao sete.

`--neg-arm`: muta uma COPIA de `app/webview/sotto_webview.py` de duas formas --
(1) `history_merge` devolve sempre `'append'` (o comportamento antigo, que e' o
defeito), (2) `history_merge` devolve sempre `'skip'` (o exagero oposto: uma
linha nova nunca entra) -- e exige as arms correspondentes a VERMELHO. Um portao
cujo mutante passa nao mede nada.
"""
import importlib.util
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
sys.path.insert(0, WEBVIEW)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def tail(body, time_s=3600, start=None):
    return {'body': body, 'time_s': time_s, 'start': start}


LONG = "Because he's going for these uh these people you know those who's going for."
GROWN = LONG[:-1] + " there."


def arms(shell):
    """(nome, obtido, esperado) -- a lista que o veredicto julga."""
    merge = shell.history_merge
    out = []
    out.append(('a1-igual-skip', merge(tail(LONG), LONG, now_s=3601), 'skip'))
    out.append(('a2-cresceu-replace',
                merge(tail(LONG, start=1.68), GROWN, now_s=3602, start=1.68),
                'replace'))
    # A CORRECCAO QUE ENCOLHE (medido 10:01:48: a linha LONGA depois de "Is a
    # very." e vice-versa). O texto novo e' mais CURTO e o `start=` e' o mesmo:
    # e' a mesma linha, e um append-only nao a consegue representar.
    out.append(('a3-encolheu-mesmo-start-replace',
                merge(tail(GROWN, start=1.68), LONG, now_s=3601, start=1.70),
                'replace'))
    out.append(('a4-prefixo-sem-start-dentro-da-janela',
                merge(tail(LONG, time_s=3600), GROWN, now_s=3601), 'replace'))
    out.append(('a5-prefixo-fora-da-janela-appende',
                merge(tail(LONG, time_s=3600), GROWN, now_s=3630), 'append'))
    out.append(('a6-texto-alheio-appende',
                merge(tail(LONG, time_s=3600), 'Is a very high chance.',
                      now_s=3601), 'append'))
    out.append(('a7-sem-cauda-appende',
                merge(None, LONG, now_s=3600), 'append'))
    out.append(('a8-corpo-vazio-skip',
                merge(tail(LONG), '   ', now_s=3601), 'skip'))
    # O MESMO `start` COM TEXTO ALHEIO NAO E' A MESMA LINHA (2026-11-04, medido
    # neste proprio caminho): engolir isto deixava o ficheiro com UMA linha onde
    # havia duas frases.
    out.append(('a10-mesmo-start-texto-alheio-appende',
                merge(tail(LONG, start=1.68), 'Is a very high chance.',
                      now_s=3601, start=1.68),
                'append'))
    out.append(('a9-start-diferente-longe-appende',
                merge(tail(LONG, time_s=3600, start=1.68),
                      LONG[:-1] + ' there is.', now_s=3640, start=40.10),
                'append'))
    return out


def tail_arms(shell):
    """`_history_tail` sobre um ficheiro GRAVADO, com a proveniencia real."""
    tmp = tempfile.mkdtemp(prefix='hist-tail-')
    path = os.path.join(tmp, '10.md')
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('- [10:01:44] Is a very.\n'
                 '- [10:01:47] Because he\'s going for these uh these people '
                 'you know those who\'s going for there. '
                 '<!-- route=final start=1.68 src=worker-stamped -->\n')
    got = shell.SottoShell._history_tail(path)
    out = [
        ('b1-cauda-le-o-texto',
         got and got.get('body'),
         "Because he's going for these uh these people you know those who's "
         "going for there."),
        ('b2-cauda-le-a-hora', got and got.get('time_s'), 10 * 3600 + 60 + 47),
        ('b3-cauda-le-o-start', got and got.get('start'), 1.68),
        ('b4-ficheiro-vazio-e-none',
         shell.SottoShell._history_tail(os.path.join(tmp, 'nope.md')), None),
    ]
    return out, tmp


def end_to_end(shell):
    """O caminho inteiro: `history_append` contra um `HISTORY_ROOT` temporario.

    Quatro escritas que sao UM enunciado (cresceu, repetiu, encolheu, cresceu) e
    uma linha nova: o ficheiro tem de ficar com DUAS linhas.
    """
    tmp = tempfile.mkdtemp(prefix='hist-e2e-')
    had = getattr(shell, 'HISTORY_ROOT', None)
    shell.HISTORY_ROOT = tmp
    logs = []
    shell_log, shell_warn = shell.log, shell.warn
    shell.log = lambda msg: logs.append(str(msg))
    shell.warn = shell.log
    path = None
    try:
        shim = shell.SottoShell.__new__(shell.SottoShell)
        opts = {'route': 'final', 'routeSource': 'worker-stamped', 'start': 1.68}
        e1 = shim.history_append(LONG, opts)
        e2 = shim.history_append(GROWN, opts)
        e3 = shim.history_append(GROWN, opts)                 # copia identica
        e4 = shim.history_append(LONG, dict(opts, start=1.70))  # encolheu
        e5 = shim.history_append('Is a very high chance.',
                                 dict(opts, start=9.20))
        path = (e1 or {}).get('path')
        rows = []
        if path and os.path.exists(path):
            with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
                rows = [r.rstrip('\r\n') for r in fh if r.strip()]
        bodies = []
        for r in rows:
            body = r.split('] ', 1)[-1]
            bodies.append(body.split(' <!--')[0].strip())
        out = [
            ('c1-uma-linha-por-enunciado', len(rows), 2),
            ('c2-a-linha-e-a-ultima-versao', bodies[:1], [LONG]),
            ('c3-a-linha-nova-entrou', bodies[1:], ['Is a very high chance.']),
            ('c4-acao-da-primeira-escrita',
             (e1 or {}).get('action'), 'append'),
            ('c5-acao-do-crescimento', (e2 or {}).get('action'), 'replace'),
            ('c6-acao-da-repeticao', (e3 or {}).get('action'), 'skip'),
            ('c7-acao-do-encolhimento', (e4 or {}).get('action'), 'replace'),
            ('c8-acao-da-linha-nova', (e5 or {}).get('action'), 'append'),
        ]
        return out, [m for m in logs if m.startswith('HISTORY_')], tmp
    finally:
        shell.log = shell_log
        shell.warn = shell_warn
        if had is not None:
            shell.HISTORY_ROOT = had


def judge(rows):
    bad = [r for r in rows if r[1] != r[2]]
    for name, got, want in rows:
        print(('ok  ' if got == want else 'RED ') + name
              + ('' if got == want else f'  got={got!r} want={want!r}'))
    return bad


MUTANTS = {
    'm1-sempre-appende': (
        "    if not last:\n        return 'append'",
        "    if True:\n        return 'append'"),
    'm2-sempre-skip': (
        "    if not last:\n        return 'append'",
        "    if True:\n        return 'skip'"),
}


def run_neg_arm():
    """Muta uma COPIA do shell e exige as arms correspondentes a VERMELHO."""
    caught = 0
    total = 0
    for name, (old, new) in MUTANTS.items():
        total += 1
        with io.open(SHELL, 'r', encoding='utf-8', errors='replace') as fh:
            src = fh.read()
        if old not in src:
            print(f'NEG-ARM IMPOSSIVEL {name}: o padrao nao esta no ficheiro')
            continue
        tmpdir = tempfile.mkdtemp(prefix='hist-mut-')
        copy = os.path.join(tmpdir, 'sotto_webview_mut.py')
        with io.open(copy, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new, 1))
        try:
            mod = load_module(copy, 'sotto_webview_mut_%d' % total)
        except Exception as exc:                      # noqa: BLE001
            print(f'NEG-ARM LOAD-FAILED {name}: {exc!r}')
            continue
        bad = judge(arms(mod))
        if bad:
            caught += 1
            print(f'ok  {name} -> RED: ' + ','.join(b[0] for b in bad))
        else:
            print(f'NOT-CAUGHT {name}: nenhum arm vermelho')
    print('NEG-ARM %s mutants %d/%d' % ('PASS' if caught == total else 'FAIL',
                                        caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return run_neg_arm()
    shell = load_module(SHELL, 'sotto_webview_histmerge')
    rows = list(arms(shell))
    tail_rows, _t1 = tail_arms(shell)
    rows.extend(tail_rows)
    e2e_rows, e2e_logs, _t2 = end_to_end(shell)
    rows.extend(e2e_rows)
    bad = judge(rows)
    print('HISTORY_E2E_LOG ' + ' | '.join(e2e_logs))
    print('VERDICT: %s arms %d/%d' % ('FAIL' if bad else 'PASS',
                                      len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
