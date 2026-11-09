#!/usr/bin/env python
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
  A6 taxa-entregue       o fio REAL entrega >= 200 Hz por 300 ms, com o maior
                         intervalo entre amostras <= 12 ms
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
RATE_FLOOR_HZ = 200.0
RATE_SAMPLES = 300           # ms de gesto medido
MAX_GAP_MS = 12.0
CPU_CEILING = 0.20        # do nucleo, durante o gesto


def _source(path=SHELL):
    return io.open(path, 'r', encoding='utf-8', newline='').read()


def extract(text, names):
    """Os pedacos do ficheiro REAL: funcoes, classes e constantes por NOME."""
    tree = ast.parse(text)
    out = {}
    wanted = set(names)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            out[node.name] = ast.get_source_segment(text, node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in wanted:
                out[target.id] = ast.get_source_segment(text, node)
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
            self.t0 = time.perf_counter()
            self.hold_ms = hold_ms
            self.x = 500
            self.y = 400
            self.samples = 0

        def GetAsyncKeyState(self, vk):
            down = (time.perf_counter() - self.t0) * 1000.0 < self.hold_ms
            return 0x8000 if down else 0

        def GetCursorPos(self, ref):
            self.samples += 1
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


def measure_rate(text, hold_ms=RATE_SAMPLES):
    pieces = extract(text, {'drag_origin', 'WindowDragFollower',
                            'WINDOW_DRAG_FRAME_HZ', 'WINDOW_DRAG_FRAME_S',
                            'WINDOW_DRAG_SPIN_S',
                            '_drag_timer_period', '_DRAG_TIMER_PERIOD'})
    missing = [n for n in ('drag_origin', 'WindowDragFollower',
                           'WINDOW_DRAG_FRAME_S') if n not in pieces]
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
    fake.t0 = time.perf_counter()      # a janela do botao comeca AGORA
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
    return {
        'started': bool(started),
        'hz': (follower.updates / follower.elapsed_s) if follower.elapsed_s else 0.0,
        'updates': follower.updates,
        'max_gap_ms': follower.max_gap_ms,
        'elapsed_ms': follower.elapsed_s * 1000.0,
        'persists': shell.persists,
        'cpu_of_one_core': cpu,
        'log_lines_during_gesture': len(during),
        'samples': follower.samples,
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

    pieces = extract(text, {'drag_origin'})
    if 'drag_origin' not in pieces:
        print('CANNOT-MEASURE: drag_origin ausente do fonte')
        return 2
    ns = {}
    exec(compile(pieces['drag_origin'], '<drag_origin>', 'exec'), ns)
    origin = ns['drag_origin']
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
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_begin_window_drag':
            begin_src = ast.get_source_segment(text, node) or ''
    uses_os_loop = ('WM_NCLBUTTONDOWN' in begin_src) or ('SendMessageW' in begin_src)
    arms_follower = 'follower.begin(' in begin_src
    has_anchor = 'GetCursorPos' in begin_src
    check('A5 sem-loop-do-windows', (not uses_os_loop) and arms_follower and has_anchor,
          'os_loop=%s follower=%s anchor=%s' % (uses_os_loop, arms_follower, has_anchor))

    # A6/A7/A8 -- o fio REAL, medido por 300 ms, com o ponteiro de mentira.
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
        rate = runs[len(runs) // 2]
        rate['runs_hz'] = [round(r['hz'], 1) for r in runs]
    if rate is None:
        check('A6 taxa-entregue', False, 'CANNOT-MEASURE %s' % why)
        check('A7 zero-log-por-amostra', False, 'CANNOT-MEASURE')
        check('A8 persiste-uma-vez', False, 'CANNOT-MEASURE')
    else:
        check('A6 taxa-entregue',
              rate['hz'] >= RATE_FLOOR_HZ and rate['max_gap_ms'] <= MAX_GAP_MS
              and rate['updates'] >= 40,
              'hz=%.1f upgrades=%d max_gap_ms=%.2f elapsed_ms=%.0f floor=%.0f'
              % (rate['hz'], rate['updates'], rate['max_gap_ms'],
                 rate['elapsed_ms'], RATE_FLOOR_HZ))
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
        import subprocess
        flags = 0x08000000 if os.name == 'nt' else 0   # CREATE_NO_WINDOW
        proc = subprocess.run([sys.executable, os.path.abspath(__file__)] + ns_args,
                              capture_output=True, text=True, creationflags=flags)
        caught = proc.returncode == 1 and 'A5 sem-loop-do-windows' in proc.stdout
        print('NEG-ARM: %s -- rc=%d' % ('PASS' if caught else 'FAIL', proc.returncode))
        return 1 if caught else 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
