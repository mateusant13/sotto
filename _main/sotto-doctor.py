#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: mede o produto contra o INTENCAO.md; nao corrige um defeito, da o veredicto
"""SOTTO-DOCTOR -- o veredicto de "o Sotto esta a funcionar como deve?".

Le `_main/webview-run.log`, isola a ULTIMA sessao da shell (do ultimo
`shell=webview2 ... pid=N` para a frente) e responde item a item ao
`INTENCAO.md`. Nao mede nada por si: julga o que a app escreveu.

Porque existe: em 2026-10-23 o dono perguntou "tu sabe como ele deve?". A
resposta honesta era "esta espalhado por 748 linhas". Um veredicto que ninguem
pode correr nao e um veredicto.

    python _main\\sotto-doctor.py            # ultima sessao
    python _main\\sotto-doctor.py --json
    python _main\\sotto-doctor.py --neg-arm  # 3 mutantes, rc=1 por desenho

Codigos: 0 = todos os itens observaveis PASS; 2 = algum FAIL; 3 = ha UNKNOWN
(nada falhou, mas falta prova -- UNKNOWN nao e PASS); 1 = --neg-arm.
"""
import argparse
import json
import os
import re
import sys

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   '_main', 'webview-run.log')

SESSION_RE = re.compile(r'shell=webview2 .* pid=(\d+)')


def last_session(lines):
    """As linhas da ultima instancia da shell, e o pid dela."""
    start, pid = 0, None
    for i, line in enumerate(lines):
        m = SESSION_RE.search(line)
        if m:
            start, pid = i, m.group(1)
    return lines[start:], pid


def judge(lines, pid):
    """[(id, estado, evidencia)] -- a unica logica deste ficheiro."""
    text = '\n'.join(lines)
    has = lambda pat: bool(re.search(pat, text))  # noqa: E731

    out = []
    # INT-1: a app abriu sa.
    fails = []
    if not has(r'SINGLE_INSTANCE .*already_running=false'):
        fails.append('sem SINGLE_INSTANCE=false')
    if not has(r'CAPTION_OVERLAY_CREATED'):
        fails.append('sem CAPTION_OVERLAY_CREATED')
    if has(r'TRAY_ICON_ADD ok=false'):
        fails.append('TRAY_ICON_ADD ok=false')
    if has(r'WEBVIEW2_INIT_FAILED'):
        fails.append('WEBVIEW2_INIT_FAILED')
    out.append(('INT-1 app abre sa', 'FAIL' if fails else 'PASS',
                ', '.join(fails) or 'mutex + overlay + tray + WebView2'))

    # INT-2: Alt+C mostra legenda.
    keyed = has(r'PANEL_SHOWN|HOTKEY_CAPTION_UNDONE|HOTKEY_DOUBLE|HOTKEY_TRIPLE')
    captioned = has(r'route=final|CAPTION_EMIT|caption\.emit|captions=[1-9]')
    if keyed and captioned:
        out.append(('INT-2 Alt+C -> legenda', 'PASS', 'tecla + legenda'))
    elif keyed:
        out.append(('INT-2 Alt+C -> legenda', 'FAIL',
                    'a tecla foi tratada mas nao saiu legenda'))
    elif not has(r'HOTKEY_REGISTERED .*isRegistered=true'):
        out.append(('INT-2 Alt+C -> legenda', 'FAIL', 'hotkey nao registado'))
    else:
        out.append(('INT-2 Alt+C -> legenda', 'UNKNOWN',
                    'hotkey registado, ninguem pressionou com o log a correr'))

    # INT-3: o worker carrega.
    spawned = has(r'BRIDGE_SPAWNED')
    loaded = has(r'BRIDGE_LOAD_MS')
    died = has(r'BRIDGE_DEATH|BRIDGE_EXIT')
    if spawned and loaded:
        out.append(('INT-3 worker carrega', 'PASS', 'BRIDGE_SPAWNED + BRIDGE_LOAD_MS'))
    elif spawned and died:
        m = re.search(r'BRIDGE_DEATH rc=(\d+) deaths=(\d+) kind=(\S+)', text)
        out.append(('INT-3 worker carrega', 'FAIL',
                    'morreu sem carregar: ' + (m.group(0) if m else 'BRIDGE_DEATH')))
    elif spawned:
        out.append(('INT-3 worker carrega', 'FAIL',
                    'BRIDGE_SPAWNED e NENHUM BRIDGE_LOAD_MS / BRIDGE_DEATH '
                    '(o worker nao disse onde parou)'))
    else:
        out.append(('INT-3 worker carrega', 'UNKNOWN', 'nenhum BRIDGE_SPAWNED'))

    # INT-7: o rato nao paga por um hook que nao serve.
    hook = has(r'OUTSIDE_CLICK_HOOK installed=true')
    shown = has(r'PANEL_SHOWN|PANEL_VISIBILITY_ON_SCREEN visible=true')
    if hook and not shown:
        out.append(('INT-7 hook so com painel', 'FAIL',
                    'hook instalado com o painel escondido'))
    elif has(r'OUTSIDE_CLICK_HOOK deferred'):
        out.append(('INT-7 hook so com painel', 'PASS',
                    'hook adiado com o painel escondido'))
    else:
        out.append(('INT-7 hook so com painel', 'UNKNOWN', 'sem linhas do hook'))
    return out


def render(rows, pid):
    print('SOTTO-DOCTOR  ultima sessao: pid=%s' % (pid or '?'))
    print('-' * 78)
    worst = 'PASS'
    for name, state, ev in rows:
        print('  %-26s %-7s %s' % (name, state, ev[:90]))
        if state == 'FAIL':
            worst = 'FAIL'
        elif state == 'UNKNOWN' and worst == 'PASS':
            worst = 'UNKNOWN'
    print('-' * 78)
    print('VERDICT: %s' % worst)
    return {'FAIL': 2, 'UNKNOWN': 3}.get(worst, 0)


def neg_arm():
    """Tres mutantes: cada um TEM de ser classificado como falha."""
    healthy = [
        'sotto: shell=webview2 pywebview=6.2.1 pid=1',
        'sotto: SINGLE_INSTANCE name=Local\\SottoShell already_running=false',
        'sotto: CAPTION_OVERLAY_CREATED hwnd=1 layered=true',
        'sotto: TRAY_ICON_ADD ok=true winerror=0',
        'sotto: HOTKEY_REGISTERED accelerator=Alt+C isRegistered=true',
        'sotto: BRIDGE_SPAWNED pid=2',
        'sotto: BRIDGE_LOAD_MS ms=16000 pid=2',
        'sotto: PANEL_SHOWN mode=strip',
        'sotto: caption route=final text="ola"',
        'sotto: OUTSIDE_CLICK_HOOK deferred reason=panel-hidden',
    ]
    zombie = [l for l in healthy if 'BRIDGE_LOAD_MS' not in l]
    webview = healthy + ['sotto: WEBVIEW2_INIT_FAILED error=0x80010108']
    cases = [('saudavel -> PASS', healthy, 'PASS'),
             ('worker zombie -> FAIL', zombie, 'FAIL'),
             ('webview falhou -> FAIL', webview, 'FAIL')]
    ok = True
    for nome, linhas, esperado in cases:
        rows = judge(linhas, '1')
        got = {'FAIL': 'FAIL', 'UNKNOWN': 'UNKNOWN'}.get(
            next((s for n, s, _ in rows if n.startswith('INT-1')), 'PASS'), 'PASS')
        # o veredicto global e o pior de todos
        states = [s for _n, s, _e in rows]
        got = 'FAIL' if 'FAIL' in states else ('UNKNOWN' if 'UNKNOWN' in states else 'PASS')
        good = got == esperado
        ok = ok and good
        print('  %-24s esperado=%-7s obtido=%-7s %s' % (nome, esperado, got,
                                                        'ok' if good else 'ERRADO'))
    print('SOTTO-DOCTOR NEG-ARM %s' % ('PASS' if ok else 'FAIL'))
    return 1 if ok else 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--log', default=LOG)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.neg_arm:
        return neg_arm()
    with open(args.log, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().splitlines()
    sess, pid = last_session(lines)
    rows = judge(sess, pid)
    if args.json:
        print(json.dumps({'pid': pid,
                          'items': [{'id': n, 'state': s, 'evidence': e}
                                    for n, s, e in rows]}, indent=2))
        return {'FAIL': 2, 'UNKNOWN': 3}.get(
            'FAIL' if any(s == 'FAIL' for _n, s, _e in rows)
            else ('UNKNOWN' if any(s == 'UNKNOWN' for _n, s, _e in rows) else 'PASS'), 0)
    return render(rows, pid)


if __name__ == '__main__':
    sys.exit(main())
