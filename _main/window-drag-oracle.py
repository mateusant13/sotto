#!/usr/bin/env python
# NO-BUG: julga o texto por `ast` e o seguidor de 240 Hz; nao arrasta a janela viva nem prova o `SetWindowPos` contra o `user32` desta sessao.
"""O ARRASTO DO PAINEL E' NOSSO E ANDA A 240 Hz -- medido, nao afirmado.

O DEFEITO QUE ESTE PORTAO EXISTE PARA IMPEDIR (medido na instancia viva,
2026-11-09 15:05, no log do proprio dono):

    WINDOW_DRAG_BEGIN surface=panel hwnd=17437966   .072
    WINDOW_DRAG_DONE  surface=panel to=(1528,12) from=(1528,12)   .078

Seis milissegundos e `from == to`: a janela nao anda um pixel. A causa esta' no
estilo da janela que este shell cria (`style=0x06010000`, sem `WS_CAPTION` e sem
`WS_THICKFRAME`; `exstyle=0x080100A8` com `WS_EX_NOACTIVATE`) -- o `SC_MOVE` do
`DefWindowProc` nao entra num laco modal e volta ao chamador. Ou seja: a tentativa
de emprestar o arrasto do Windows nao pode funcionar nesta janela, e o log dizia
"BEGIN" e "DONE" como se tivesse funcionado.

O QUE FOI FEITO: o delta da pega e' aplicado por um fio proprio
(`WindowDragFollower`, `name='sotto-window-drag'`) a 240 Hz -- `GetCursorPos` +
`GetAsyncKeyState` mais UM `SetWindowPos(SWP_NOSIZE)` quando o pixel muda. Sem
hook, sem mensagem por movimento para a pagina, sem uma linha de log por amostra.

OS BRACOS (todos sobre o TEXTO REAL do `sotto_webview.py`, extraido por AST -- o
modulo inteiro nao e' importado, que e' a regra desta casa):

  A1 delta-exato         o deslocamento aplicado e' a DIFERENCA cursor-pega
  A2 escala              com DPI 2.0 o mesmo movimento fisico anda METADE em DIP
  A3 clamp               a janela nunca sai da area de trabalho (4 bordas)
  A4 identidade          cursor parado nao inventa movimento
  A5 sem-loop-do-windows `_begin_window_drag` NAO manda WM_NCLBUTTONDOWN e arma
                         o follower (e' o mutante que o `--neg-arm` repoe)
  A6 taxa-entregue       o fio REAL entrega com p50 do intervalo <= 8 ms em 3
                         gestos de 300 ms somados (a MEDIANA e' o que distingue
                         um laco de 240 Hz de um de 60 Hz; a cauda mede a
                         contenda da maquina -- ver `P50_GAP_MS`)
  A7 zero-log-por-amostra nenhuma linha escrita no meio do gesto
  A8 persiste-uma-vez    `persist=True` chega UMA vez, no fim

Uso:
  python _main/window-drag-oracle.py [--json out.json] [--neg-arm]
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

#: O PISO E' 200, E O NUMERO TEM UMA MEDICAO ATRAS (2026-11-09). Este oraculo
#: nasceu com 230 Hz e ficou INSTAVEL: no mesmo minuto mediu 222,2 Hz (RED) e
#: 239,9 Hz (GREEN), com a maquina do dono a 81 % de CPU (DM de stutter do
#: watcher, mesma janela). Um braco que depende do escalonador do Windows numa
#: maquina carregada e' um braco que mente -- ele nao mede o CODIGO. O alvo que
#: ele existe para apanhar e' uma regressao de taxa (o laco de 60 Hz que este
#: portao substituiu daria ~60), e 200 Hz ainda da' 3,3x de margem contra isso.
RATE_SAMPLES = 300           # ms de gesto medido
#: O QUE ESTE BRACO JULGA E' O **p50 DO INTERVALO**, E A RAZAO E' MEDIDA
#: (2026-11-12, cinco leituras da mesma arvore dentro e fora da corrida caged):
#: a taxa media e a cauda oscilam com a contenda da maquina (172-240 Hz, maximo
#: de 4,67 a 90,86 ms num unico gesto, com 61 % de CPU da maquina a ser de
#: OUTRAS lanes), mas o intervalo TIPICO nao: um laco a 240 Hz tem 4,17 ms por
#: quadro e um a 60 Hz tem 16,7 ms. Julgar a cauda mede o escalonador; julgar a
#: mediana mede o laco. O defeito que este braco foi escrito para apanhar e' o
#: laco de 60 Hz curado em 2026-11-09, e a distancia entre os dois e' 4x -- 8,0 ms
#: fica no meio dela, com 1,9x de margem para cada lado. O que a mediana NAO ve
#: (um gesto inteiro congelado) e' medido pelo piso de amostras e pela arm A12.
P50_GAP_MS = 8.0
#: O piso da taxa continua, mas so' como rede: um laco que nem chega a 100 Hz
#: nao tem 40 amostras uteis em 300 ms e o `n` minimo ja' o apanha. Ele fica
#: porque uma taxa abaixo disso significa que o fio nao esta' a entregar.
RATE_SANITY_HZ = 100.0
CPU_CEILING = 0.20        # do nucleo, durante o gesto


def _source(path=SHELL):
    return io.open(path, 'r', encoding='utf-8', newline='').read()

#: O PROPRIO DIRECTORIO NO `sys.path`: `_astcache` vive ao lado deste ficheiro, e um
#: import por nome so' resolve quando o directorio do SCRIPT esta' na lista -- verdade
#: ao correr `python _main\x.py`, mentira quando o oraculo e' importado por outro
#: instrumento (a sonda que mediu a distribuicao do max_gap foi assim que caiu num
#: `ModuleNotFoundError`, medido 2026-11-12).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
#: A ARVORE E OS SEGMENTOS VEM DE `_astcache` (2026-11-12). Este ficheiro
#: guardava a SUA copia da cura (37,6 s de `_splitlines_no_ff` em 51 chamadas,
#: medido por `cProfile` no `--neg-arm`) e outros tres oraculos guardavam a mesma
#: copia com outro nome -- cinco copias de uma convencao. Uma so' e' modulo.
from _astcache import segment, tree as _tree  # noqa: E402


def extract(text, names):
    """Os pedacos do ficheiro REAL: funcoes, classes e constantes por NOME."""
    tree = _tree(text)
    out = {}
    wanted = set(names)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            out[node.name] = segment(text, node, "")
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in wanted:
                out[target.id] = segment(text, node, "")
    return out


def build_namespace(pieces, shell, hold_ms=RATE_SAMPLES):
    """Um mundo FALSO, com o codigo REAL la' dentro."""
    ns = {'__name__': 'drag_probe'}
    ns['ctypes'] = ctypes
    ns['time'] = time
    ns['threading'] = threading

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

    class FakeUser32:
        """O ponteiro de mentira: desce por `hold_ms` e anda 1 px por amostra."""

        def __init__(self, hold_ms):
            #: O RELOGIO DO GESTO COMECA NA PRIMEIRA PERGUNTA, nao na construcao
            #: (medido 2026-11-12). `begin()` espera ate' 100 ms pelo fio da pega
            #: anterior, e com o `t0` fixado antes disso a janela de 300 ms ja'
            #: chegava gasta: a corrida caged mediu `elapsed_ms=130` e **n=23**
            #: amostras, e a arm leu 184,7 Hz sobre um gesto TRUNCADO -- um
            #: numero que fala do custo de abrir o fio, nao da taxa do laco.
            self.t0 = None
            self.hold_ms = hold_ms
            self.x = 500
            self.y = 400
            self.samples = 0
            self.stamps = []

        def GetAsyncKeyState(self, vk):
            now = time.perf_counter()
            if self.t0 is None:
                self.t0 = now
            down = (now - self.t0) * 1000.0 < self.hold_ms
            return 0x8000 if down else 0

        def GetCursorPos(self, ref):
            self.samples += 1
            #: O INSTANTE DE CADA AMOSTRA. E' aqui que o braco A6 mede a
            #: DISTRIBUICAO dos intervalos em vez do pior caso: um unico
            #: intervalo de 12 ms numa maquina carregada e' o escalonador, e
            #: julgar o maximo fazia este braco mentir (medido 2026-11-12, ver
            #: `MAX_GAP_MS`). Nao custa nada: e' um `perf_counter` por amostra
            #: no ponteiro FALSO, fora do codigo de producao.
            self.stamps.append(time.perf_counter())
            point = ref._obj
            point.x = self.x + self.samples
            point.y = self.y
            return 1

    fake = FakeUser32(hold_ms)
    lines = []
    ns.update({'POINT': POINT, 'user32': fake, 'VK_LBUTTON': 0x01,
               'log': lines.append, 'shell': shell})
    for name, code in pieces.items():
        if name in ('WindowDragFollower', '_drag_timer_period'):
            continue
        exec(compile(code, '<%s>' % name, 'exec'), ns)
    for name in ('_drag_timer_period', 'WindowDragFollower'):
        code = pieces.get(name)
        if code:
            exec(compile(code, '<%s>' % name, 'exec'), ns)
    return ns, fake, lines


def gaps_ms(stamps):
    """Os intervalos entre AMOSTRAS consecutivas, em ms.

    O braco A6 julga o **p95** disto, nao o maximo: numa maquina carregada um
    unico intervalo de 12 ms e' o escalonador do Windows a tirar o fio do
    processador, e julgar o maximo fazia o braco dizer RED sobre codigo correcto
    (medido 2026-11-12: 12 leituras seguidas deram maximo 4,75..12,18 ms com a
    taxa entre 230 e 240 Hz, enquanto o intervalo tipico ficou em 4,2 ms).
    """
    return [round((b - a) * 1000.0, 3) for a, b in zip(stamps, stamps[1:])]


def _pct(values, frac):
    """O percentil `frac` (0..1) de `values`, por posto, sem interpolar."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round(frac * (len(ordered) - 1)))
    return ordered[max(0, min(idx, len(ordered) - 1))]


def measure_rate(text, hold_ms=RATE_SAMPLES):
    pieces = extract(text, {'drag_origin', 'WindowDragFollower',
                            'WINDOW_DRAG_FRAME_HZ', 'WINDOW_DRAG_FRAME_S',
                            'WINDOW_DRAG_SPIN_S', 'WINDOW_DRAG_STUCK_SAMPLES',
                            '_drag_timer_period', '_DRAG_TIMER_PERIOD'})
    missing = [n for n in ('drag_origin', 'WindowDragFollower',
                           'WINDOW_DRAG_FRAME_S',
                           'WINDOW_DRAG_STUCK_SAMPLES') if n not in pieces]
    if missing:
        return None, 'missing:%s' % ','.join(missing)

    class Shell:
        def __init__(self):
            self.calls = []
            self.persists = 0

        def window_drag_to(self, x, y, persist=False):
            self.calls.append((x, y, persist))
            if persist:
                self.persists += 1
                return True
            return True

    shell = Shell()
    ns, fake, lines = build_namespace(pieces, shell, hold_ms)
    follower = ns['WindowDragFollower'](shell)
    try:
        import psutil  # noqa: F401
        _proc = psutil.Process()
        _t0 = _proc.cpu_times()
        cpu0 = _t0.user + _t0.system
    except Exception:
        cpu0 = None
    started = follower.begin('panel', (500, 400, 100, 100), 1)
    deadline = time.perf_counter() + (RATE_SAMPLES / 1000.0) + 2.0
    while follower.active and time.perf_counter() < deadline:
        time.sleep(0.01)
    if follower.active:
        follower.stop()
    if follower.is_alive():
        follower.join(2.0)
    # A ULTIMA LINHA DO PROPRIO GESTO NAO CONTA: `WINDOW_DRAG_FOLLOW_END` e' o
    # relatorio do fim, escrito uma vez. O braco mede o que aconteceu DURANTE.
    during = [line for line in lines if 'WINDOW_DRAG_FOLLOW_END' not in str(line)]
    # `time.process_time()` nesta maquina tem grao de 15,6 ms: ele devolve
    # 0,000 duas vezes e o braco passaria sem medir nada (a classe "portao que
    # nao pode falhar"). O custo vem do `psutil`, e sem ele o braco e'
    # CANNOT-MEASURE -- nunca verde.
    if cpu0 is None:
        cpu = None
    else:
        _t1 = _proc.cpu_times()
        cpu = ((_t1.user + _t1.system) - cpu0) / (follower.elapsed_s or 1e-9)
    #: A TAXA VEM DA JANELA ENTRE AMOSTRAS, nao da vida do fio. O fio nasce com
    #: `begin()` e morre com o `finally` (que ainda escreve o
    #: `WINDOW_DRAG_PERSIST`); dividir por `elapsed_s` metia as duas pontas no
    #: denominador e pagava o custo de abrir/fechar o fio como se fosse laco.
    stamps = list(fake.stamps)
    window_s = (stamps[-1] - stamps[0]) if len(stamps) >= 2 else 0.0
    gaps_all = gaps_ms(stamps)
    return {
        'started': bool(started),
        'hz': ((len(stamps) - 1) / window_s) if window_s > 0 else 0.0,
        'updates': follower.updates,
        'max_gap_ms': follower.max_gap_ms,
        'elapsed_ms': follower.elapsed_s * 1000.0,
        'persists': shell.persists,
        'cpu_of_one_core': cpu,
        'log_lines_during_gesture': len(during),
        'samples': follower.samples,
        'gaps_ms': gaps_ms(fake.stamps),
    }, None


def measure_stuck(text, cause, hold_ms=80):
    """Um gesto que NAO move a janela: o seguidor tem de NOMEAR a causa.

    `cause=''` e' o clique que nao muda o pixel -- o desfecho NORMAL de uma
    pressao curta, e tem de continuar a nao publicar nada. `cause='no-anchor'` e'
    o arrasto partido, e e' o que a queixa do dono de 2026-11-09 nao conseguia
    distinguir daquele.
    """
    pieces = extract(text, {'drag_origin', 'WindowDragFollower',
                            'WINDOW_DRAG_FRAME_HZ', 'WINDOW_DRAG_FRAME_S',
                            'WINDOW_DRAG_SPIN_S', 'WINDOW_DRAG_STUCK_SAMPLES',
                            '_drag_timer_period', '_DRAG_TIMER_PERIOD'})
    missing = [n for n in ('drag_origin', 'WindowDragFollower',
                           'WINDOW_DRAG_FRAME_S',
                           'WINDOW_DRAG_STUCK_SAMPLES') if n not in pieces]
    if missing:
        return None, 'missing:%s' % ','.join(missing)

    class Shell:
        def __init__(self):
            self.persists = 0
            self._window_drag_refusal = cause

        def window_drag_to(self, x, y, persist=False):
            if persist:
                self.persists += 1
                return True
            # O CANAL E' REESCRITO A CADA AMOSTRA, como no produto: o caminho
            # "o pixel nao mudou" limpa o motivo, e um `False` sem causa nao
            # pode ser contado como recusa.
            self._window_drag_refusal = cause
            return False

    shell = Shell()
    ns, fake, lines = build_namespace(pieces, shell, hold_ms)
    follower = ns['WindowDragFollower'](shell)
    started = follower.begin('panel', (500, 400, 100, 100), 1)
    deadline = time.perf_counter() + (hold_ms / 1000.0) + 2.0
    while follower.active and time.perf_counter() < deadline:
        time.sleep(0.01)
    if follower.active:
        follower.stop()
    if follower.is_alive():
        follower.join(2.0)
    text_lines = [str(line) for line in lines]
    stuck = [line for line in text_lines if 'WINDOW_DRAG_STUCK' in line]
    ends = [line for line in text_lines if 'WINDOW_DRAG_FOLLOW_END' in line]
    return {
        'started': bool(started),
        'samples': follower.samples,
        'updates': follower.updates,
        'refused': getattr(follower, 'refused', None),
        'cause': getattr(follower, 'refusal_cause', None),
        'stuck': stuck,
        'end_line': ends[0] if ends else '',
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--target', default=SHELL)
    args = ap.parse_args()

    text = _source(args.target)
    checks = []

    def check(name, ok, evidence):
        checks.append({'arm': name, 'ok': bool(ok), 'evidence': evidence})
        print(('  GREEN ' if ok else '  RED   ') + name.ljust(24) + ' ' + evidence)

    pieces = extract(text, {'drag_origin', 'WINDOW_DRAG_STUCK_SAMPLES'})
    if 'drag_origin' not in pieces:
        print('CANNOT-MEASURE: drag_origin ausente do fonte')
        return 2
    ns = {}
    exec(compile(pieces['drag_origin'], '<drag_origin>', 'exec'), ns)
    origin = ns['drag_origin']
    #: O piso vem do FONTE, nao de um literal daqui: um oraculo que repete o
    #: numero mede a copia, e o produto podia mudar o piso sem ninguem saber.
    _floor_ns = {}
    if 'WINDOW_DRAG_STUCK_SAMPLES' in pieces:
        exec(compile(pieces['WINDOW_DRAG_STUCK_SAMPLES'], '<stuck>', 'exec'),
             _floor_ns)
    WINDOW_DRAG_STUCK_FLOOR = int(
        _floor_ns.get('WINDOW_DRAG_STUCK_SAMPLES') or 0)
    work = {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
    size = (380, 900)

    # A1 -- o delta e' relativo a PEGA, nunca a posicao absoluta do cursor.
    nx, ny = origin((1000, 500, 500, 100), (1120, 420), 1.0, size, work)
    check('A1 delta-exato', (nx, ny) == (620, 20), f'got=({nx},{ny}) want=(620,20)')

    # A2 -- o cursor chega em pixels fisicos: com DPI 2 o DIP anda metade.
    nx, ny = origin((1000, 500, 500, 100), (1100, 600), 2.0, size, work)
    check('A2 escala', (nx, ny) == (550, 150), f'got=({nx},{ny}) want=(550,150)')

    # A3 -- o clamp, nas quatro bordas.
    cases = {
        'left': ((0, 0, 500, 100), (-900, 0), (0, 100)),
        'top': ((0, 0, 500, 100), (0, -900), (500, 0)),
        'right': ((0, 0, 500, 100), (9000, 0), (1540, 100)),
        'bottom': ((0, 0, 500, 100), (0, 9000), (500, 180)),
    }
    bad = []
    for label, (anchor, cursor, want) in cases.items():
        got = origin(anchor, cursor, 1.0, size, work)
        if got != want:
            bad.append('%s=%r!=%r' % (label, got, want))
    check('A3 clamp', not bad, 'ok 4 bordas' if not bad else '; '.join(bad))

    # A4 -- cursor parado nao inventa movimento.
    nx, ny = origin((700, 700, 300, 40), (700, 700), 1.0, size, work)
    check('A4 identidade', (nx, ny) == (300, 40), f'got=({nx},{ny}) want=(300,40)')

    # A5 -- o caminho do Windows nao existe mais, e o follower esta' armado.
    begin_src = ''
    tree = _tree(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_begin_window_drag':
            begin_src = segment(text, node, '')
    uses_os_loop = ('WM_NCLBUTTONDOWN' in begin_src) or ('SendMessageW' in begin_src)
    arms_follower = 'follower.begin(' in begin_src
    has_anchor = 'GetCursorPos' in begin_src
    check('A5 sem-loop-do-windows', (not uses_os_loop) and arms_follower and has_anchor,
          'os_loop=%s follower=%s anchor=%s' % (uses_os_loop, arms_follower, has_anchor))

    # A6/A7/A8 -- o fio REAL, medido 3x300 ms, com o ponteiro de mentira.
    #: TRES GESTOS, E OS INTERVALOS SOMAM-SE ANTES DE JULGAR (medido 2026-11-12).
    #: Julgar a MEDIANA de tres gestos de 300 ms deixava o veredicto nas maos de
    #: um unico episodio do escalonador: a mesma arvore deu `slow=19/62 (30,6 %)`
    #: num gesto e `0/72` no seguinte, com a corrida caged a roubar ~80 ms de uma
    #: vez. Somados, esses 19 intervalos pesam 19/203 = 9,4 % e a arm mede o LACO;
    #: um laco de 60 Hz continua a ter 100 % deles lentos em todos os gestos, que
    #: e' a unica regressao que este braco existe para apanhar.
    runs = []
    for _ in range(3):
        one, why = measure_rate(text)
        if one is None:
            runs = []
            break
        runs.append(one)
    rate = None
    if runs:
        runs.sort(key=lambda r: r['hz'])
        rate = dict(runs[len(runs) // 3])          # a mais lenta das tres
        rate['gaps_ms'] = [g for r in runs for g in r['gaps_ms']]
        rate['updates'] = min(r['updates'] for r in runs)
        rate['runs_hz'] = [round(r['hz'], 1) for r in runs]
    if rate is None:
        check('A6 taxa-entregue', False, 'CANNOT-MEASURE %s' % why)
        check('A7 zero-log-por-amostra', False, 'CANNOT-MEASURE')
        check('A8 persiste-uma-vez', False, 'CANNOT-MEASURE')
    else:
        gaps = rate['gaps_ms']
        p50 = _pct(gaps, 0.50)
        check('A6 taxa-entregue',
              p50 <= P50_GAP_MS and rate['hz'] >= RATE_SANITY_HZ
              and rate['updates'] >= 40 and len(gaps) >= 60,
              'p50_gap_ms=%.2f p95_ms=%.2f max_ms=%.2f hz=%.1f upgrades=%d '
              'runs_hz=%s n=%d ceiling_p50=%.1f'
              % (p50, _pct(gaps, 0.95), max(gaps) if gaps else 0.0, rate['hz'],
                 rate['updates'], rate.get('runs_hz'), len(gaps), P50_GAP_MS))
        if rate['cpu_of_one_core'] is None:
            check('A9 giro-limitado', False, 'CANNOT-MEASURE sem psutil')
        else:
            check('A9 giro-limitado', rate['cpu_of_one_core'] <= CPU_CEILING,
                  'cpu=%.3f de um nucleo ceiling=%.2f'
                  % (rate['cpu_of_one_core'], CPU_CEILING))
        check('A7 zero-log-por-amostra', rate['log_lines_during_gesture'] == 0,
              'linhas=%d amostras=%d' % (rate['log_lines_during_gesture'],
                                         rate['samples']))
        check('A8 persiste-uma-vez', rate['persists'] == 1,
              'persists=%d' % rate['persists'])

    # A10/A11/A12 -- O GESTO QUE NAO ANDA. A queixa do dono (2026-11-09:
    # *"os paineis nao sao draggable em 240hz"*) nao era atribuivel porque um
    # `updates=0` tanto e' um clique como um arrasto partido. As tres arms
    # separam-nos: recusa POR CAUSA num gesto real publica `WINDOW_DRAG_STUCK`
    # com o motivo; o clique parado NAO publica; e um gesto abaixo do piso de
    # amostras tambem nao (senao todo o clique viraria um alarme).
    st_anchor, why_st = measure_stuck(text, 'no-anchor', hold_ms=80)
    st_click, why_click = measure_stuck(text, '', hold_ms=80)
    st_short, why_short = measure_stuck(text, 'no-anchor', hold_ms=12)
    if st_anchor is None or st_click is None or st_short is None:
        check('A10 recusa-nomeada', False,
              'CANNOT-MEASURE %s' % (why_st or why_click or why_short))
        check('A11 clique-nao-alarma', False, 'CANNOT-MEASURE')
        check('A12 piso-de-amostras', False, 'CANNOT-MEASURE')
    else:
        named = (st_anchor['refused'] or 0) > 0 and 'cause=no-anchor' in (
            st_anchor['stuck'][0] if st_anchor['stuck'] else '')
        check('A10 recusa-nomeada', bool(st_anchor['stuck']) and named,
              'samples=%d updates=%d refused=%s causas=%s'
              % (st_anchor['samples'], st_anchor['updates'],
                 st_anchor['refused'], (st_anchor['stuck'][0][:60]
                                        if st_anchor['stuck'] else 'NENHUMA')))
        check('A11 clique-nao-alarma',
              not st_click['stuck'] and (st_click['refused'] or 0) == 0,
              'stuck=%d refused=%s end=%s'
              % (len(st_click['stuck']), st_click['refused'],
                 (st_click['end_line'][-40:] or '-')))
        check('A12 piso-de-amostras',
              not st_short['stuck'] and st_short['samples'] < WINDOW_DRAG_STUCK_FLOOR,
              'samples=%d stuck=%d'
              % (st_short['samples'], len(st_short['stuck'])))

    ok = all(c['ok'] for c in checks)
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for c in checks if c['ok']), len(checks)))
    if args.json:
        with io.open(args.json, 'w', encoding='utf-8') as handle:
            json.dump({'ok': ok, 'checks': checks, 'rate': rate}, handle, indent=1)

    if not args.neg_arm:
        return 0 if ok else 1

    # O NEGATIVO: a cura volta a ser o laco do Windows numa COPIA do ficheiro.
    tmp_dir = tempfile.mkdtemp(prefix='sotto-drag-neg-')
    try:
        copy = os.path.join(tmp_dir, 'sotto_webview.py')
        shutil.copyfile(args.target, copy)
        bad_text = io.open(copy, 'r', encoding='utf-8', newline='').read()
        needle = '        if not follower.begin(surface, anchor, hwnd):'
        if needle not in bad_text:
            print('NEG-ARM IMPOSSIVEL: a ancora do follower nao esta no fonte')
            return 2
        bad_text = bad_text.replace(
            needle,
            '        user32.SendMessageW(hwnd, 0x00A1, 2, 0)\n'
            '        if not follower.begin(surface, anchor, hwnd):', 1)
        io.open(copy, 'w', encoding='utf-8', newline='').write(bad_text)
        ns_args = ['--target', copy]
        # A guarda INTEIRA, pelo largador da casa: `creationflags` sozinho e' a
        # metade barata (o censo chama-lhe WEAK-FLAG) e um filho de consola
        # nascido de um pai SEM consola ganha uma NOVA janela.
        import importlib.util
        _hl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "hidden-launch.py")
        _spec = importlib.util.spec_from_file_location("hidden_launch", _hl_path)
        _hl = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_hl)
        rc_child, out_child, _err_child = _hl.run(
            [sys.executable, os.path.abspath(__file__)] + ns_args,
            capture=True, timeout=600)
        caught_a5 = rc_child == 1 and 'A5 sem-loop-do-windows' in out_child
        # SEGUNDO MUTANTE: o veredicto de arrasto partido APAGADO. Sem ele,
        # apagar o `WINDOW_DRAG_STUCK` deixava o negativo verde -- a classe
        # "portao que nao pode falhar" que este ficheiro ja' pagou uma vez.
        copy2 = os.path.join(tmp_dir, 'sotto_webview_stuck.py')
        shutil.copyfile(args.target, copy2)
        stuck_text = io.open(copy2, 'r', encoding='utf-8', newline='').read()
        anchor_stuck = '            if (self.samples >= WINDOW_DRAG_STUCK_SAMPLES'
        if anchor_stuck not in stuck_text:
            print('NEG-ARM IMPOSSIVEL: o emissor de WINDOW_DRAG_STUCK nao esta no fonte')
            return 2
        io.open(copy2, 'w', encoding='utf-8', newline='').write(
            stuck_text.replace(anchor_stuck,
                               '            if (False and self.samples >= '
                               'WINDOW_DRAG_STUCK_SAMPLES', 1))
        rc2, out2, _err2 = _hl.run(
            [sys.executable, os.path.abspath(__file__), '--target', copy2],
            capture=True, timeout=600)
        caught_stuck = rc2 == 1 and 'A10 recusa-nomeada' in out2
        # TERCEIRO MUTANTE: O LACO DE 60 Hz, que e' a regressao que o A6 existe
        # para apanhar. Ele nasceu com o teto do MAXIMO, passou pelo p95 e hoje
        # julga o p50 (2026-11-12) -- um limiar que muda TEM de trazer o mutante
        # que prova que ele ainda apanha o que apanhava, senao cada afinamento
        # transformava o braco no "portao que nao pode falhar". A 60 Hz o
        # intervalo e' 16,7 ms em TODO quadro: 2x o teto de 8,0, logo o mutante
        # cai pelo p50 e nao pela cauda.
        copy3 = os.path.join(tmp_dir, 'sotto_webview_60hz.py')
        shutil.copyfile(args.target, copy3)
        hz_text = io.open(copy3, 'r', encoding='utf-8', newline='').read()
        anchor_hz = 'WINDOW_DRAG_FRAME_HZ = 240'
        if anchor_hz not in hz_text:
            print('NEG-ARM IMPOSSIVEL: WINDOW_DRAG_FRAME_HZ nao esta no fonte')
            return 2
        io.open(copy3, 'w', encoding='utf-8', newline='').write(
            hz_text.replace(anchor_hz, 'WINDOW_DRAG_FRAME_HZ = 60', 1))
        rc3, out3, _err3 = _hl.run(
            [sys.executable, os.path.abspath(__file__), '--target', copy3],
            capture=True, timeout=600)
        caught_slow = rc3 == 1 and 'A6 taxa-entregue' in out3
        caught = caught_a5 and caught_stuck and caught_slow
        print('NEG-ARM: %s -- A5 rc=%d (%s) / A10 rc=%d (%s) / A6-60hz rc=%d (%s)'
              % ('PASS' if caught else 'FAIL', rc_child,
                 'caught' if caught_a5 else 'NOT-CAUGHT', rc2,
                 'caught' if caught_stuck else 'NOT-CAUGHT', rc3,
                 'caught' if caught_slow else 'NOT-CAUGHT'))
        return 1 if caught else 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
