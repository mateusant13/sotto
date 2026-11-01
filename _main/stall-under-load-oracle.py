"""O CARREGAR DO MODELO NAO ENGASGA O ECRA: nada trava a UI dentro da janela de carga.

A queixa do dono e' literal -- *"NUNCA TRAVAR O PC DO USUARIO OU STUTTER"* -- e a cura que
este oraculo julga nao e' "o worker e' leve": e' que a CARGA vive no PROCESSO do worker e o
shell continua a publicar. O que se mede, portanto, e' o shell DURANTE a janela em que o
worker esta' a carregar o modelo:

  * janela de carga = `BRIDGE_SPAWN` -> `BRIDGE_LOAD_MS` (o worker diz quanto levou), com o
    tecto de `--max-window-s` para uma janela cujo fim nunca chegou nao engolir a sessao;
  * prova de que o shell NAO travou = as suas publicacoes periodicas (`BRIDGE_STATS_PUSH`,
    `BRIDGE_METER`, `BRIDGE_CAPTION_SENT`) continuam a cair DENTRO da janela;
  * o defeito = qualquer `UI_THREAD_STALL` ou `exec_js TIMEOUT` dentro da janela. Medido
    2026-10-30: 93 `UI_THREAD_STALL` e 68 `exec_js TIMEOUT` em UMA janela de 50 s, com o
    Edge headless a desenhar 45 temas -- a carga e' o GATILHO, o congelamento e' do CODIGO.

Julga so' a SESSAO VIVA (a ultima `SHELL_STARTUP_STAGE`), pela mesma razao do
`paint-live-show-oracle.py`: um log com dias publica um numero que ja' nao descreve nada.
Sem janela de carga na sessao imprime `VERDICT: SKIPPED`; o passo da bateria e' skip-capable.

`--neg-arm` injecta um `UI_THREAD_STALL` dentro de uma janela sintetica e exige RED, e tem
um segundo braco: uma janela sem publicacao nenhuma tambem e' RED (o shell pode ter travado
sem dizer).
"""
# NO-BUG: instrumento da ordem "nada de stutter": as janelas de carga do modelo nao podem
# ter um unico UI_THREAD_STALL ou exec_js TIMEOUT dentro; julga a sessao viva, nao o produto
from __future__ import annotations

import argparse
import os
import re

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webview-run.log')
START = ('SHELL_STARTUP_STAGE', 'SHELL_START')
SPAWN = 'BRIDGE_SPAWN'
LOADED = 'BRIDGE_LOAD_MS'
STALL = ('UI_THREAD_STALL', 'exec_js TIMEOUT')
ALIVE = ('BRIDGE_STATS_PUSH', 'BRIDGE_METER', 'BRIDGE_CAPTION_SENT', 'BRIDGE_STATS_REPLY',
         'PANEL_SURFACE', 'STATUS_APPLIED')
TS = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})')


def _ts(line):
    m = TS.match(line)
    return m.group(1) if m else ''


def _epoch(stamp):
    import time
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return time.mktime(time.strptime(stamp, fmt))
        except ValueError:
            continue
    return None


def session(lines):
    for i in range(len(lines) - 1, -1, -1):
        if any(tag in lines[i] for tag in START):
            return lines[i:], _ts(lines[i])
    return [], ''


def windows(lines, max_window_s):
    """[(inicio, fim, publicacoes, estalos)] por janela de carga da sessao."""
    out = []
    open_at = None
    pubs = 0
    stalls = 0
    for ln in lines:
        if SPAWN in ln and open_at is None:
            open_at = _ts(ln)
            pubs = stalls = 0
            continue
        if open_at is None:
            continue
        if any(tag in ln for tag in ALIVE):
            pubs += 1
        if any(tag in ln for tag in STALL):
            stalls += 1
        if LOADED in ln:
            out.append((open_at, _ts(ln), pubs, stalls))
            open_at = None
    if open_at is not None:
        out.append((open_at, '?', pubs, stalls))
    # uma janela sem fim nao pode engolir a sessao: o tecto e' declarado, nao escondido
    capped = []
    for start, end, pubs, stalls in out:
        if end == '?':
            a = _epoch(start)
            if a is None:
                continue
            capped.append((start, 'sem-fim', pubs, stalls))
            continue
        a, b = _epoch(start), _epoch(end)
        if a is None or b is None or (b - a) > max_window_s:
            capped.append((start, end, pubs, stalls))
            continue
        capped.append((start, end, pubs, stalls))
    return capped


def judge(text, max_window_s=300.0):
    """-> (verdict, detail). Puro: so' o texto do log."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    sess, started = session(lines)
    if not sess:
        return 'SKIPPED', {'why': 'nenhum arranque de shell no log', 'started': '', 'windows': []}
    wins = windows(sess, max_window_s)
    fails = []
    for start, end, pubs, stalls in wins:
        if stalls:
            fails.append('janela %s -> %s tem %d estalo(s) de UI' % (start, end, stalls))
    # AUSENCIA DE PUBLICACAO NAO E' PROVA DE TRAVAMENTO, e o primeiro desenho deste oraculo
    # tratava-a como tal: medido na sessao viva, duas janelas de 23 s sem publicacao nenhuma
    # -- que e' o normal de um shell parado sem audio (o `BRIDGE_STATS_PUSH` e' de 30 em 30 s).
    # Um oraculo com esse braco publica vermelho por desenho. Fica INFORMACAO impressa.
    detail = {'started': started, 'windows': wins, 'fails': fails,
              'max_pubs': max((w[2] for w in wins), default=0),
              'quiet': [w for w in wins if not w[2]]}
    if fails:
        return 'RED', detail
    if not wins:
        return 'SKIPPED', dict(detail, why='nenhuma janela de carga na sessao viva (%s)'
                               % (started,))
    return 'GREEN', detail


def neg_arm(text, max_window_s=300.0):
    """Duas mutacoes de uma sessao sintetica LIMPA -- cada uma tem de ser apanhada."""
    base = ('2099-01-01 00:00:00.000 sotto: SHELL_STARTUP_STAGE stage=start\n'
            '2099-01-01 00:00:01.000 sotto: BRIDGE_SPAWN pid=1\n'
            '2099-01-01 00:00:02.000 sotto: BRIDGE_STATS_PUSH count=1\n'
            '2099-01-01 00:00:03.000 sotto: PANEL_SURFACE surface=panel\n'
            '2099-01-01 00:00:20.000 sotto: BRIDGE_LOAD_MS ms=18000\n')
    cases = (
        ('limpa', base, 'GREEN'),
        ('estalo-dentro-da-carga',
         base.replace('2099-01-01 00:00:03.000 sotto: PANEL_SURFACE surface=panel\n',
                      '2099-01-01 00:00:03.000 WARN UI_THREAD_STALL begin-invoke not run in 10 s\n'
                      '2099-01-01 00:00:03.500 sotto: PANEL_SURFACE surface=panel\n'),
         'RED'),
        # CONTROLE DE ESPECIFICIDADE: um estalo FORA da janela nao pode ser contado, senao o
        # oraculo morde qualquer coisa e o verde dele nao vale nada.
        ('estalo-fora-da-janela',
         base.replace('2099-01-01 00:00:20.000 sotto: BRIDGE_LOAD_MS ms=18000\n',
                      '2099-01-01 00:00:20.000 sotto: BRIDGE_LOAD_MS ms=18000\n'
                      '2099-01-01 00:00:25.000 WARN UI_THREAD_STALL begin-invoke not run\n'),
         'GREEN'),
    )
    bad = 0
    for label, sample, expect in cases:
        got, detail = judge(sample, max_window_s)
        ok = got == expect
        bad += 0 if ok else 1
        print('  %-28s -> %-8s %s  %s'
              % (label, got, 'as required' if ok else 'NOT-CAUGHT',
                 (detail.get('fails') or ['-'])[0][:88]))
    print('NEG-ARM cases=%d caught=%d' % (len(cases), len(cases) - bad))
    if bad:
        print('NEG-ARM FAIL')
        return 2
    print('NEG-ARM PASS')
    return 1   # convencao da casa: o braco negativo PASSOU sai rc=1 (passo expect-red)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--max-window-s', type=float, default=300.0)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm('', args.max_window_s)
    if not os.path.exists(args.log):
        print('STALL-UNDER-LOAD VERDICT: SKIPPED (sem log em %s)' % (args.log,))
        return 0
    text = open(args.log, encoding='utf-8', errors='replace').read()
    verdict, detail = judge(text, args.max_window_s)
    print('STALL-UNDER-LOAD sessao=%s janelas=%d publicacoes_max=%d'
          % (detail.get('started') or '-', len(detail.get('windows') or []),
             detail.get('max_pubs') or 0))
    for start, end, pubs, stalls in detail.get('windows') or []:
        print('  janela %s -> %-23s publicacoes=%-4d estalos=%d' % (start, end, pubs, stalls))
    for start, end, pubs, stalls in detail.get('quiet') or []:
        print('  nota: janela %s -> %s sem publicacao -- nao e prova de travamento: o '
              'shell parado nao escreve nada' % (start, end))
    for why in detail.get('fails') or []:
        print('  RED: %s' % (why,))
    if verdict == 'SKIPPED':
        print('STALL-UNDER-LOAD VERDICT: SKIPPED (%s)' % (detail.get('why') or '-',))
        return 0
    print('STALL-UNDER-LOAD VERDICT: %s' % (verdict,))
    return 0 if verdict == 'GREEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
