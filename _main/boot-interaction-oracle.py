"""A FLUIDEZ MEDE-SE DO ARRANQUE, E DA PRIMEIRA INTERACCao -- ordem do dono, 2026-11-10.

Verbatim: *"a performance e o measure de TUDO tem que comecar a partir do momento que
o app abre. como um usuario. se eu abro o app, e ja tento abrir o painel alt c, e ele
demora 2 segundos, E HORRIVEL."*

TODOS os instrumentos de custo desta casa mediam DEPOIS de a app estar quente: um
`paint-cost` de 0,063 ms p95, um `shell-thread-budget` de 8 % de um nucleo, um
`PANEL_SHOWN wait_ms=406` de uma sessao com o painel ja montado. Nenhum respondia a
pergunta que ele fez, porque nenhum estava ancorado no ARRANQUE: um instrumento que
comeca no arranque ve o que o caminho FRIO custa, e o frio e' o que ele encontra
quando duplo-clica o icone.

O QUE ESTE LE. O log da shell (`_main/webview-run.log`), a ULTIMA sessao dele (a
ultima `SHELL_STARTUP_STAGE`), e nada mais: quem arranca a app e' ele.

| linha | o que da' | orcamento |
|---|---|---|
| `HOTKEY_PRESSED role=panels` -> `PANEL_SHOWN` | Alt+C: tecla -> janela na tela | `SHOW_BUDGET_MS` = 400 |
| `HOTKEY_PRESSED role=live` -> `LIVE_ENABLED` | Ctrl+Space: tecla -> legenda on/off | `LIVE_BUDGET_MS` = 400 |
| `TRAY_MENU_FOREGROUND ok=` | bandeja: a fracao de menus SEM primeiro plano | `0 %` (qualquer `ok=0`) |
| `TRAY_MENU_FOREGROUND menu_ms=` | tempo com o menu ABERTO -- e' a mao dele | informativo |
| `CAPTION_OVERLAY_LAG`/`CAPTION_PAINT` | arranque -> primeira legenda pintada | `FIRST_CAPTION_BUDGET_MS` = 15000 |
| `SHELL_STARTUP_STAGE` -> a primeira das de cima | arranque -> a primeira interacao DELE | informativo |

PORQUE OS ORCAMENTOS SAO ESTES. 400 ms e' o prazo que a casa ja' exige da pintura
(`paint-live-show`: `wait_ms<=400`); nao se inventa um numero novo para a mesma
sensacao. Os 15 s da primeira legenda sao a carga do modelo (medida 8,9 s a quente,
43 s a frio) e NAO sao uma promessa de fluidez: sao o numero contra o qual o motor
quente tem de ser julgado, e aparecem aqui para nao ficarem escondidos.

AS LINHAS QUE NAO EXISTEM NAO SAO UM PASSE. Uma interacao sem par no log fica
`UNMEASURED` na tabela e IMPEDE o veredicto verde enquanto for interacao que ele faz
(Alt+C, Ctrl+Space, bandeja): um instrumento que trata "nada medido" como "rapido" e'
o que esta casa pagou caro (`shell-thread-budget` sem shell viva devolvia verde).

  python _main/boot-interaction-oracle.py            # le o log vivo
  python _main/boot-interaction-oracle.py --log X    # outro log
  python _main/boot-interaction-oracle.py --neg-arm  # dois logs FALSOS, um verde e um vermelho
  python _main/boot-interaction-oracle.py --paint-arm # os dois FICHEIROS de forma: o log do dono
                                                      # (pintura 3 142 ms) tem de ser RED, o log
                                                      # curado (`PANEL_SHOW_COST`) tem de ser GREEN,
                                                      # e a mutacao da cura tem de voltar a RED
  python _main/boot-interaction-oracle.py --json

Veredicto: rc=0 PASS / rc=1 FAIL / rc=3 SKIPPED (sem sessao no log). O `--neg-arm`
devolve **1 quando apanha** (a convencao desta casa: um controlo que nao pode falhar
nao e' um controlo). O `--paint-arm` segue a mesma convencao: devolve 1 quando PEGA.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, 'webview-run.log')

#: Orcamentos -- ver o docstring: 400 ms e' o prazo que `paint-live-show` ja' exige.
SHOW_BUDGET_MS = 400.0
LIVE_BUDGET_MS = 400.0
MENU_BUDGET_MS = 200.0
FIRST_CAPTION_BUDGET_MS = 15000.0
#: A perna que a APP responde: a idade do audio da primeira legenda. E' o MESMO
#: orcamento que o `CAPTION_PAINT_LAG` ja' publica em cada legenda
#: (`budget_ms=1500` no log dele), porque e' a mesma promessa -- nao duas.
AUDIO_AGE_BUDGET_MS = 1500.0
#: Informativo (nao julga): da ultima escada ABERTA ate' a primeira pintura.
TAP_TO_CAPTION_BUDGET_MS = 15000.0

STAMP = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})')


def _t(line):
    m = STAMP.match(line)
    if not m:
        return None
    hh, mm, ss = m.group(1)[11:].split(':')
    return int(m.group(1)[11:13]) * 3600 + int(mm) * 60 + float(ss)


def _num(line, key):
    m = re.search(r'\b%s=(-?[\d.]+)' % re.escape(key), line)
    return float(m.group(1)) if m else None


def _field(line, key):
    m = re.search(r'\b%s=(\S+)' % re.escape(key), line)
    return m.group(1) if m else None


def session_lines(lines):
    """As linhas da ULTIMA sessao: a ultima `SHELL_STARTUP_STAGE` e' o arranque dela.

    Um log rotacionado guarda varias sessoes; medir desde a primeira seria medir
    outro dia. Nenhum arranque no log -> [] (e o veredicto e' SKIPPED, nunca PASS).
    """
    start = None
    for i, line in enumerate(lines):
        if 'SHELL_STARTUP_STAGE' in line and 'stage=pre-lock' in line:
            start = i
    return lines[start:] if start is not None else []


def _chain(seg):
    """(tecla, despacho, pintura) de cada Alt+C -- tres elos, cada um medivel.

    A RAZAO DE SER TRES E NAO UM: o log nao tem (ainda) um id na linha
    `PANEL_SHOWN`, portanto um emparelhamento posicional atribui a pintura de uma
    pressao a tecla de outra e inventa um numero. O elo que NAO e' ambiguo e' o
    `HOTKEY_COALESCED ... transitions=1`, que o proprio codigo emite imediatamente
    antes de chamar `show_strip`/`show_side`, e que carrega `from=`/`to=`. Logo:
    tecla -> coalesced e' o DESPACHO, coalesced -> shown e' a PINTURA, e a soma e'
    o que o dono sente. Medido na sessao de 2026-11-10 09:34: os 3,1 s do primeiro
    Alt+C estavam TODOS na pintura (despacho 5 ms).

    Um coalesced com `transitions=0` nao pinta nada e nao entra na cadeia.
    """
    out, pending_press, pending_step = [], None, None
    for line in seg:
        if 'HOTKEY_PRESSED' in line and 'role=panels' in line:
            if pending_press is None:
                pending_press = line
            continue
        if 'HOTKEY_COALESCED' in line and 'transitions=1' in line:
            if pending_step is not None:          # nunca foi pintado
                out.append((pending_press, pending_step, None))
                pending_press = None
            pending_step = line
            continue
        if 'PANEL_SHOWN' in line and pending_step is not None:
            out.append((pending_press, pending_step, line))
            pending_press, pending_step = None, None
    if pending_step is not None:
        out.append((pending_press, pending_step, None))
    return out


def measure(lines, log_name=''):
    seg = session_lines(lines)
    rows = []
    if not seg:
        return {'ok': False, 'why': 'no-session', 'rows': [], 'log': log_name}

    t0 = _t(seg[0])
    if t0 is None:
        return {'ok': False, 'why': 'no-timestamp', 'rows': [], 'log': log_name}

    def add(family, boot_ms, value_ms, budget, note='', kind='gate'):
        """`kind='info'` nao e' um portao: o numero e' publicado e nao julga.

        Existe por UMA razao medida (2026-11-11): "arranque -> 1a legenda" inclui
        o tempo em que o dono ainda nao tinha audio a sair, e esse tempo nao e'
        nosso. Quem julga a app e' a perna que comeca quando a ESCADA ABRE num
        endpoint -- e' essa que tem orcamento.
        """
        if value_ms is None:
            # INFO SEM LEITURA NAO E' UM BURACO NO PORTAO: a linha existe para
            # PUBLICAR, e um fixture que modela so o Alt+C nao tem o que ela le.
            verdict = 'INFO' if kind == 'info' else 'UNMEASURED'
        elif kind == 'info':
            verdict = 'INFO'
        else:
            verdict = 'PASS' if value_ms <= budget else 'FAIL'
        rows.append({'family': family, 'boot_ms': None if boot_ms is None else round(boot_ms, 1),
                     'value_ms': None if value_ms is None else round(value_ms, 1),
                     'budget_ms': budget, 'note': note, 'kind': kind,
                     'verdict': verdict})

    # Alt+C -> painel na tela, em dois elos: DESPACHO (tecla->coalesced) e
    # PINTURA (coalesced->shown). O primeiro par e' o que ele sente ao abrir a app.
    chain = _chain(seg)
    if chain:
        press, step, shown = chain[0]
        dispatch = (_t(step) - _t(press)) * 1000.0 if press else None
        paint = (_t(shown) - _t(step)) * 1000.0 if shown else None
        add('alt-c 1o: despacho', (_t(press) - t0) * 1000.0 if press else None,
            dispatch, SHOW_BUDGET_MS, 'to=%s presses=%s'
            % (_field(step, 'to'), _field(step, 'presses')))
        add('alt-c 1o: pintura', (_t(step) - t0) * 1000.0, paint, SHOW_BUDGET_MS,
            'content_ack=%s wait_ms=%s'
            % (_field(shown, 'content_ack'), _field(shown, 'wait_ms')) if shown
            else 'coalesced sem PANEL_SHOWN depois')
        totals = [((_t(s) - _t(p)) * 1000.0, i) for i, (p, st, s) in enumerate(chain)
                  if p is not None and s is not None]
        if totals:
            worst, idx = max(totals)
            p, st, s = chain[idx]
            add('alt-c pior total', (_t(p) - t0) * 1000.0, worst, SHOW_BUDGET_MS,
                'cadeia #%d, despacho %.0f + pintura %.0f'
                % (idx + 1, (_t(st) - _t(p)) * 1000.0, (_t(s) - _t(st)) * 1000.0))
        else:
            add('alt-c pior total', None, None, SHOW_BUDGET_MS, 'nenhuma cadeia completa')
    else:
        add('alt-c 1o: despacho', None, None, SHOW_BUDGET_MS,
            'nenhuma pressao com transitions=1 no log')
        add('alt-c 1o: pintura', None, None, SHOW_BUDGET_MS, 'idem')

    # Ctrl+Space -> LIVE_ENABLED on/off.
    live_press, live_done = None, None
    for line in seg:
        if 'HOTKEY_PRESSED' in line and 'role=live' in line and live_press is None:
            live_press = line
        elif live_press is not None and 'LIVE_ENABLED' in line:
            live_done = line
            break
    if live_press is not None and live_done is not None:
        add('ctrl+space primeiro toggle', (_t(live_press) - t0) * 1000.0,
            (_t(live_done) - _t(live_press)) * 1000.0, LIVE_BUDGET_MS,
            'on=%s' % (_field(live_done, 'on') or '-'))
    else:
        add('ctrl+space primeiro toggle', None, None, LIVE_BUDGET_MS, 'nenhum par no log')

    # A BANDEJA, EM DUAS METADES -- porque o `menu_ms` NAO E' A NOSSA (medido
    # 2026-11-11). Ele mede `time.monotonic()` antes e depois do
    # `TrackPopupMenu`, que BLOQUEIA ate' o menu fechar: os 672 ms da sessao dele
    # sao o tempo com o menu ABERTO, ou seja o tempo que ELE levou a escolher.
    # Um portao sobre isso condena a mao do dono (e o `n=1` de uma sessao em que
    # ele abriu o menu uma vez media um clique, nao uma interface).
    tray = [l for l in seg if 'TRAY_MENU_FOREGROUND' in l]
    if tray:
        menus = [m for m in (_num(l, 'menu_ms') for l in tray) if m is not None]
        add('bandeja: menu aberto (ms)', None, max(menus) if menus else None,
            MENU_BUDGET_MS, 'n=%d -- tempo com o menu aberto (dele, nao da app)'
            % len(tray), kind='info')
        bad = sum(1 for l in tray if 'ok=0' in l)
        # A PERNA QUE E' DA APP: o menu precisa de primeiro plano para nao comer
        # o clique de fora, e o `SetForegroundWindow` cru era recusado 13 de 13
        # nesta maquina antes do `AttachThreadInput` (`_take_menu_foreground`).
        add('bandeja: primeiro plano ok', None, 100.0 * bad / len(tray), 0.0,
            'n=%d falhas=%d (ok=0 no TRAY_MENU_FOREGROUND)' % (len(tray), bad))
    else:
        add('bandeja: primeiro plano ok', None, None, 0.0, 'sem TRAY_MENU_FOREGROUND')

    # Arranque -> primeira legenda pintada (o modelo, nao uma promessa de fluidez).
    first = None
    for line in seg:
        if ('CAPTION_PAINT ' in line or 'CAPTION_OVERLAY_LAG' in line):
            first = line
            break
    # A PERNA QUE E' NOSSA: da ULTIMA escada ABERTA antes da pintura ate' a
    # pintura. O numero de cima inclui o tempo em que o dono ainda nao tinha
    # audio a sair, e esse tempo nao e' do Sotto -- medido 2026-11-11 (pid 21400):
    # arranque -> 1a legenda = 59,0 s, e a escada abriu o endpoint que entregou
    # as 00:49:40.065, com a legenda 1,28 s depois. Um portao que julga a soma
    # condena o trabalho normal e ensina a nao o ler.
    tap_to_caption = None
    tap_note = 'sem escada ABERTA no log'
    if first is not None:
        for line in seg:
            if line is first:
                break
            if 'LADDER_TRY' in line and 'result=opened' in line:
                tap_to_caption = (_t(first) - _t(line)) * 1000.0
                tap_note = 'device=%s' % (_field(line, 'device') or '-')
    if first is not None:
        add('escada aberta -> 1a legenda', None, tap_to_caption,
            TAP_TO_CAPTION_BUDGET_MS, tap_note, kind='info')
        add('arranque -> 1a legenda', None, (_t(first) - t0) * 1000.0,
            FIRST_CAPTION_BUDGET_MS, ''
            if 'CAPTION_PAINT' in first else 'age_ms=%.0f' % (_num(first, 'age_ms') or 0),
            # E' UM PORTAO: 40 s ate' a primeira legenda e' o que o dono sente, e
            # a perna do audio nao o desculpa -- no arranque de 2026-11-11 havia
            # audio no endpoint aberto as 00:48:55.878 e a legenda saiu as
            # 00:49:41.295 (o defeito que `silent_desktop_hold(own_peak=...)` cura).
            )
        # O UNICO NUMERO DESTA FAMILIA QUE E' DA APP: a idade do AUDIO da
        # primeira legenda. `audio_ms=74` no arranque de 2026-11-11 significa que
        # a app legendou 74 ms depois de o som existir; o resto dos 59 s foi o
        # dono ainda a nao tocar nada. Sem esta perna, o portao condenava o
        # trabalho normal pela espera do audio -- a classe que esta casa ja'
        # pagou no `pin que ninguem re-mede`.
        first_audio = None
        for line in seg:
            if 'CAPTION_APPLIED' in line or 'CAPTION_PAINT_LAG' in line:
                first_audio = _num(line, 'audio_ms')
                if first_audio is None:
                    first_audio = _num(line, 'tap_age_ms')
                if first_audio is not None:
                    break
        add('1a legenda: idade do AUDIO', None, first_audio, AUDIO_AGE_BUDGET_MS,
            'CAPTION_APPLIED audio_ms / CAPTION_PAINT_LAG tap_age_ms',
            # O campo so' existe a partir de 2026-11-10; um fixture anterior nao
            # tem o que julgar, e julga-lo seria o portao a inventar um numero.
            kind='gate' if first_audio is not None else 'info')
    else:
        add('arranque -> 1a legenda', None, None, FIRST_CAPTION_BUDGET_MS, 'sem pintura no log')

    measured = [r for r in rows if r['value_ms'] is not None]
    fails = [r for r in measured if r['verdict'] == 'FAIL']
    unmeasured = [r for r in rows if r['verdict'] == 'UNMEASURED']
    return {'ok': not fails and not unmeasured, 'why': 'measured', 'rows': rows,
            'log': log_name, 't0': seg[0][:23],
            'measured': len(measured), 'fails': len(fails), 'unmeasured': len(unmeasured)}


def render(res, out=sys.stdout):
    if res.get('why') == 'no-session':
        print('BOOT-INTERACTION SKIPPED reason=no-session log=%s' % (res['log'],), file=out)
        print(' (um log sem `SHELL_STARTUP_STAGE stage=pre-lock` nao foi aberto nesta'
              ' arvore: nada medido, nada afirmado)', file=out)
        return 3
    if res.get('why') == 'no-timestamp':
        print('BOOT-INTERACTION SKIPPED reason=no-timestamp log=%s' % (res['log'],), file=out)
        return 3
    print('BOOT-INTERACTION log=%s sessao=%s' % (res['log'], res['t0']), file=out)
    print('%-28s %10s %10s %8s  %s'
          % ('interacao', 'boot+ms', 'ms', 'orcamento', 'veredicto / nota'), file=out)
    for r in res['rows']:
        print('%-28s %10s %10s %8.0f  %s%s'
              % (r['family'],
                 '-' if r['boot_ms'] is None else '%.0f' % r['boot_ms'],
                 '-' if r['value_ms'] is None else '%.1f' % r['value_ms'],
                 r['budget_ms'], r['verdict'],
                 ('  ' + r['note']) if r['note'] else ''), file=out)
    v = 'PASS' if res['ok'] else 'FAIL'
    print('VERDICT: %s -- medidas=%d falhas=%d nao-medidas=%d'
          % (v, res['measured'], res['fails'], res['unmeasured']), file=out)
    return 0 if res['ok'] else 1


# ── o controle: dois logs FALSOS, um verde e um vermelho ────────────────────
def _synthetic(show_ms, live_ms, menu_ms, caption_ms, menu_ok=1):
    """Um log com a FORMA que a shell escreve -- e um unico numero mudado por braco."""
    base = '2026-11-10 10:00:00.000'
    h, m, s = 10, 0, 0.0

    def at(ms):
        nonlocal s
        s = ms / 1000.0
        mm = int(s // 60)
        ss = s - mm * 60
        return '2026-11-10 10:%02d:%06.3f' % (mm, ss)

    L = ['2026-11-10 10:00:00.000 sotto: shell=webview2 pywebview=6.2.1 '
         'python=3.11.8 pid=999',
         '2026-11-10 10:00:00.003 sotto: SHELL_STARTUP_STAGE pid=999 stage=pre-lock'
         ' python=x panel=true',
         '%s sotto: HOTKEY_PRESSED role=panels count=1 accelerator=Alt+C thread=1'
         % at(1000.0),
         '%s sotto: HOTKEY_COALESCED presses=1 from=hidden/- to=visible/strip'
         ' steps=1 transitions=1' % at(1000.0 + 5.0),
         '%s sotto: PANEL_SHOWN reason=hotkey-cycle-strip mode=strip content_ack=true'
         ' wait_ms=1.0' % at(1000.0 + show_ms),
         '%s sotto: HOTKEY_PRESSED role=live count=1 source=hook accelerator=Ctrl+Space'
         ' thread=2' % at(2000.0),
         '%s sotto: LIVE_ENABLED on=true' % at(2000.0 + live_ms),
         '%s sotto: TRAY_MENU_FOREGROUND ok=%d err=0 menu_ms=%d'
         % (at(3000.0), menu_ok, menu_ms),
         '%s sotto: CAPTION_PAINT instant=true text="oi"' % at(caption_ms)]
    return L


# ── o braco da PINTURA: dois LOGS EM FICHEIRO, um por forma conhecida ───────
# O `_synthetic` acima prova a ARITMETICA do oraculo. Estes dois provam a FORMA
# que a shell escreve: `_main/fixtures/boot-interaction-altc-paint-slow.log` e'
# a sessao do dono de 2026-11-10 09:33:51 (Alt+C: despacho 5 ms, pintura
# 3 142 ms, `content_ack=false wait_ms=500`), e
# `_main/fixtures/boot-interaction-altc-paint-fast.log` e' a forma CURADA: um
# orcamento so' (`PANEL_SHOW_COST` com as cinco parcelas + `total_ms`) e a
# pintura dentro dos 400 ms. O braco falha se o oraculo deixar passar um log de
# forma lenta, e falha tambem se o log curado nao publicar a linha de custo --
# um log sem `PANEL_SHOW_COST` e' o log ANTIGO, e um oraculo que o aceita nao
# mede o que foi curado.
FIXTURES = os.path.join(HERE, 'fixtures')
PAINT_RED = os.path.join(FIXTURES, 'boot-interaction-altc-paint-slow.log')
PAINT_GREEN = os.path.join(FIXTURES, 'boot-interaction-altc-paint-fast.log')
PAINT_FAMILY = 'alt-c 1o: pintura'


def _load_fixture(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read().splitlines()


def _row(res, family):
    for r in res.get('rows') or []:
        if r['family'] == family:
            return r
    return None


def _stamp(secs):
    """`secs` segundos desde 00:00 -> 'YYYY-MM-DD HH:MM:SS.mmm' (o formato do log)."""
    secs = max(0.0, secs)
    hh = int(secs // 3600)
    mm = int((secs - hh * 3600) // 60)
    ss = secs - hh * 3600 - mm * 60
    return '2026-11-10 %02d:%02d:%06.3f' % (hh, mm, ss)


def _uncure(lines):
    """A MUTACAO DO CONSERTO: o log curado com a cura DESFEITA.

    Duas coisas que o conserto escreve e o defeito nao: a linha de custo
    (`PANEL_SHOW_COST`, um orcamento so' com as parcelas medidas) e a pintura
    dentro do orcamento. A mutacao apaga a primeira e empurra o `PANEL_SHOWN`
    3 142 ms para a frente do `HOTKEY_COALESCED` -- exactamente o numero do log
    do dono. Se o braco RED nao pegar ISTO, ele nao pega o defeito.
    """
    seq = [l for l in lines if 'HOTKEY_COALESCED' in l and 'transitions=1' in l]
    t_step = _t(seq[0]) if seq else 0.0
    out = []
    for line in lines:
        if 'PANEL_SHOW_COST' in line:
            continue
        if 'PANEL_SHOWN' in line:
            out.append(_stamp(t_step + 3.142) + line[23:])
            continue
        out.append(line)
    return out


def paint_arm(verbose=True):
    """O braco da pintura: LENTO tem de dar FAIL, CURADO tem de dar PASS.

    Devolve 1 (o braco PEGOU -- que e' o "PASS" do `--neg-arm` desta casa) ou 0.
    """
    cases = []
    reason = {}
    if not os.path.exists(PAINT_RED) or not os.path.exists(PAINT_GREEN):
        if verbose:
            print('paint-arm: FAIL -- fixture ausente (%s / %s)'
                  % (PAINT_RED, PAINT_GREEN))
        return 0
    for name, path in (('RED', PAINT_RED), ('GREEN', PAINT_GREEN)):
        lines = _load_fixture(path)
        res = measure(lines, log_name=path)
        row = _row(res, PAINT_FAMILY)
        rc = (3 if res.get('why') in ('no-session', 'no-timestamp')
              else (0 if res['ok'] else 1))
        cases.append({'name': name, 'path': path, 'res': res, 'row': row,
                      'rc': rc, 'lines': lines})
        if verbose:
            print('paint-arm %s fixture=%s rc=%d verdict=%s %s=%.1f budget=%.0f'
                  % (name, os.path.basename(path), rc,
                     'PASS' if res['ok'] else 'FAIL', PAINT_FAMILY,
                     (row or {}).get('value_ms') or -1.0, SHOW_BUDGET_MS))
    red, green = cases
    ok = True

    # 1) O LOG DO DONO, na forma em que ele o escreveu, tem de ser RED.
    if not (red['rc'] == 1 and red['row'] and red['row']['verdict'] == 'FAIL'
            and (red['row']['value_ms'] or 0.0) > SHOW_BUDGET_MS):
        ok = False
        reason['red'] = 'o log lento nao saiu FAIL na pintura (rc=%d, %s)'
    # 2) A forma curada tem de ser GREEN, e o log curado tem de PUBLICAR o custo.
    if not (green['rc'] == 0 and green['row']
            and green['row']['verdict'] == 'PASS'):
        ok = False
        reason['green'] = 'o log curado nao saiu PASS na pintura (rc=%d)' % green['rc']
    cost = [l for l in green['lines'] if 'PANEL_SHOW_COST' in l]
    if not cost:
        ok = False
        reason['cost'] = 'o log curado nao publica PANEL_SHOW_COST (forma antiga)'
    else:
        total = _num(cost[-1], 'total_ms')
        parts = [_num(cost[-1], k) for k in
                 ('surf_ms', 'arm_ms', 'gate_ms', 'map_ms', 'ack_ms')]
        if total is None or any(p is None for p in parts):
            ok = False
            reason['cost'] = 'PANEL_SHOW_COST sem total_ms ou sem as cinco parcelas'
        elif total > SHOW_BUDGET_MS:
            ok = False
            reason['cost'] = ('PANEL_SHOW_COST total_ms=%.1f > %.0f'
                              % (total, SHOW_BUDGET_MS))
        elif abs(sum(parts) - total) > 1.0:
            ok = False
            reason['cost'] = ('PANEL_SHOW_COST soma das parcelas=%.1f != total_ms=%.1f'
                              % (sum(parts), total))
    # 3) A MUTACAO: o log curado com a cura desfeita tem de voltar a RED.
    mut = measure(_uncure(green['lines']), log_name='mutacao-do-consero')
    mrow = _row(mut, PAINT_FAMILY)
    mrc = (3 if mut.get('why') in ('no-session', 'no-timestamp')
           else (0 if mut['ok'] else 1))
    if verbose:
        print('paint-arm MUTACAO fixture=mutacao-do-consero rc=%d verdict=%s %s=%.1f'
              % (mrc, 'PASS' if mut['ok'] else 'FAIL', PAINT_FAMILY,
                 (mrow or {}).get('value_ms') or -1.0))
    if not (mrc == 1 and mrow and mrow['verdict'] == 'FAIL'):
        ok = False
        reason['mutation'] = 'a mutacao da cura NAO foi apanhada (rc=%d)' % mrc
    if verbose:
        for k, v in reason.items():
            print('paint-arm REASON %s: %s' % (k, v))
        print('PAINT-ARM: %s -- red=FAIL green=PASS mutacao=FAIL'
              % ('PASS' if ok else 'FAIL'))
    return 1 if ok else 0


def neg_arm():
    """Verde com numeros dentro do orcamento, vermelho com 2000 ms -- cada um pelo SEU braco."""
    cases = [
        ('G a sessao rapida tem de dar PASS', _synthetic(120.0, 90.0, 40, 4000.0), 0),
        ('R1 Alt+C a 2000 ms tem de dar FAIL', _synthetic(2000.0, 90.0, 40, 4000.0), 1),
        ('R2 Ctrl+Space a 900 ms tem de dar FAIL', _synthetic(120.0, 900.0, 40, 4000.0), 1),
        # O `menu_ms` a 800 ms e' INFO (o tempo dele com o menu aberto): passa.
        ('G2 bandeja com o menu aberto 800 ms tem de dar PASS',
         _synthetic(120.0, 90.0, 800, 4000.0), 0),
        # A perna da APP: o menu sem primeiro plano falha.
        ('R3 bandeja sem primeiro plano (ok=0) tem de dar FAIL',
         _synthetic(120.0, 90.0, 40, 4000.0, menu_ok=0), 1),
        ('R4 primeira legenda a 40 s tem de dar FAIL', _synthetic(120.0, 90.0, 40, 40000.0), 1),
        ('R5 um log sem sessao tem de dar SKIPPED (rc=3)',
         ['2026-11-10 10:00:00.000 sotto: nada'], 3),
    ]
    caught = 0
    for name, lines, want in cases:
        res = measure(lines, log_name='sintetico')
        rc = (3 if res.get('why') in ('no-session', 'no-timestamp')
              else (0 if res['ok'] else 1))
        good = rc == want
        caught += good
        print('%s %s (rc=%d, esperado %d)' % ('PASS' if good else 'FAIL', name, rc, want))
    # R6: os dois ficheiros de FORMA (o log do dono e o log curado) mais a
    # mutacao da cura -- ver `paint_arm`. O `--neg-arm` desta casa devolve 1
    # quando PEGA, portanto o caso `... 1` e' o desejado.
    pgood = paint_arm(verbose=True) == 1
    print('%s R6 pintura dos ficheiros de forma tem de pegar red+mutacao (rc=%d,'
          ' esperado 1)' % ('PASS' if pgood else 'FAIL', 1 if pgood else 0))
    caught += pgood
    cases_n = len(cases) + 1
    if caught == cases_n:
        print('NEG-ARM: PASS -- %d/%d casos' % (caught, cases_n))
        return 1
    print('NEG-ARM: FAIL -- %d/%d casos' % (caught, cases_n))
    return 0


PAINT_LIVE = os.path.join(HERE, 'paint-live-show-oracle.py')


def _fresh_helpers():
    """`demote_stale`/`live_process_verdict` PELO CAMINHO, nao por nome.

    O ficheiro chama-se `paint-live-show-oracle.py` (HIFEN): um `import` por
    nome nao o alcanca, e uma segunda copia destas duas funcoes seria a segunda
    convencao da casa para a mesma pergunta. Devolve `(None, None)` quando o
    ficheiro nao esta' ao lado -- o veredicto entao fica o que a medicao deu.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_paint_live', PAINT_LIVE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.demote_stale, mod.live_process_verdict
    except Exception:                      # noqa: BLE001
        return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--paint-arm', action='store_true',
                    help='o braco da PINTURA contra os dois ficheiros de forma '
                         '(_main/fixtures/boot-interaction-altc-paint-{slow,fast}.log);'
                         ' devolve 1 quando PEGA o log lento e a mutacao da cura')
    a = ap.parse_args(argv)
    if a.neg_arm:
        return neg_arm()
    if a.paint_arm:
        return paint_arm(verbose=True)
    if not os.path.exists(a.log):
        print('BOOT-INTERACTION SKIPPED reason=no-log path=%s' % (a.log,))
        return 3
    with open(a.log, encoding='utf-8', errors='replace') as fh:
        # 4 MiB bastam: a ultima sessao de uma app que ele abriu cabe lá, e ler
        # 21 MB para achar a cauda e' o mesmo desperdicio que a casa ja' mediu.
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - 4 * 1024 * 1024))
        lines = fh.read().splitlines()
    res = measure(lines, log_name=a.log)
    if not res['ok']:
        demote, fresh_of = _fresh_helpers()
        if demote is not None:
            fresh, why = fresh_of(a.log)
            if demote('RED', fresh) == 'SKIPPED':
                # A EVIDENCIA NAO SE APAGA -- cada linha continua impressa com o
                # carimbo do processo que a produziu. O que muda e' o veredicto:
                # um numero medido num processo que carregou OUTRO codigo mede o
                # codigo velho (medido 2026-11-11: a sessao de 00:48:42 precede a
                # cura `600e190` do endpoint que renderiza, e o boot->legenda de
                # 59 s e' exactamente o defeito que ela cura).
                if not a.json:
                    render(res)
                    for r in res['rows']:
                        if r['verdict'] in ('FAIL', 'UNMEASURED'):
                            print('STALE-EVIDENCE %-28s %s ms orcamento %s  %s'
                                  % (r['family'],
                                     '-' if r['value_ms'] is None else '%.1f' % r['value_ms'],
                                     r['budget_ms'], r['note']))
                print('BOOT-INTERACTION SKIPPED reason=stale-process live=%s'
                      % (why,))
                return 3
    if a.json:
        print(json.dumps(res, indent=2))
        return 0 if res.get('ok') else (3 if res.get('why') in ('no-session', 'no-timestamp') else 1)
    return render(res)


if __name__ == '__main__':
    sys.exit(main())
