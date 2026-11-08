#!/usr/bin/env python
# NO-BUG: instrumento da lane HotkeySpam (2026-11-08) -- mede a RAJADA do Alt+C
# executando os corpos que correm no shell, com a janela INJECTADA. Nao abre
# janela, nao toca em ctypes, nao lanca o app vivo, nao escreve log de produto.
"""ORACLE: Alt+C spammado -- uma rajada custa UMA transicao, e nao uma por pressao.

A EVIDENCIA QUE ESTE INSTRUMENTO JULGA (`_main/webview-run.log`, a rajada do
dono 03:30:57.5Z..03:31:02.6Z):

    107 presses na vida; 17 com gap < 300 ms; minimo 0 ms.
    HOTKEY_TOGGLE -> STRIP_RECT_WIDTH -> WINDOW_GEOMETRY -> PANEL_SURFACE ->
    PAINT_ACK_ARM -> PANEL_CONTENT -> PAINT_ACK -> PANEL_SHOWN, por pressao,
    medidos 416-700 ms de um HOTKEY_TOGGLE ao seguinte.
    `WARN UI_THREAD_STALL begin-invoke not run in 0.25s fn=guarded_show`

O DEFEITO: cada pressao era um item de trabalho inteiro na fila do worker.
Cinco presses empilhavam ~3 s de resize de janela + troca de documento
WebView2, e o UI thread nao tinha vez.

A CURA: `_hotkey_dispatch('panels')` so' SOMA em `_panel_presses` (o token
continua a entrar na fila para guardar a ordem em relacao ao Ctrl+Space); o
worker, no primeiro token `panels`, DRENA o contador inteiro e caminha o ciclo
`hotkey_gesture.advance` N passos de uma vez, aplicando o estado final numa
unica transicao. Os tokens seguintes encontram 0 e sao um no-op declarado.

BRACOS (impressos no arranque):

  (A1) 6 presses em 50 ms -> UM drain coalescido (uma transicao decidida),
       nao 6; o muro de 6 transicoes (2400 ms com a transicao falsa de 400 ms)
       desaparece
  (A2) o estado resultante e' EXACTAMENTE o de `advance` caminhado a mao
  (A3) uma pressao sozinha transita no mesmo instante -- nao ha janela de
       debounce (o inicio da transicao e' << 400 ms depois do despacho)
  (A4) um token `live` ENTRE dois `panels` mantem a ordem, e os paineis
       colapsam na mesma transicao
  (A5) presses que somam o MESMO estado nao movem a janela (3 presses
       escondido -> ZERO transicoes), e a rajada seguinte volta a andar
  (A6) uma rajada REALISTA (5 presses em 320 ms, com a transicao a decorrer)
       custa no maximo 2 transicoes -- nao 5

A FILA E' A REAL (`queue.Queue`, o worker real, threads reais). O que o
instrumento FECHA e' so' a janela de entrega das presses de uma rajada: o
`BurstQueue.get` espera que a rajada inteira tenha entrado antes de o worker
ver o primeiro token -- e' o instante em que o fio do hotkey entregou as
presses de 50 ms e o worker ainda nao tinha vez. Sem esse portao o braco
mediria o escalonador do Windows, nao o codigo.

Uso:
    python _main/hotkey-spam-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/hotkey-spam-oracle.py --neg-arm  -> muta uma COPIA (FIFO de
        volta) e exige que (A1)/(A5) fiquem RED; imprime as contagens.
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SOTTO_ROOT") or HERE.parent).resolve()
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
GESTURE = ROOT / "app" / "webview" / "hotkey_gesture.py"
EXIT_PASS, EXIT_FAIL = 0, 1

#: A transicao que o dono mediu (416-700 ms). O instrumento usa o modelo de
#: 400 ms: e' o custo de um map/unmap de janela + `PANEL_SHOWN`, e e' o que
#: transforma uma rajada de 6 presses em 2,4 s no defeito reportado.
TRANSITION_S = 0.400

COALESCED = re.compile(
    r'HOTKEY_COALESCED presses=(\d+) from=(\S+) to=(\S+) '
    r'steps=(\d+) transitions=(\d+)')
SKIPPED = 'HOTKEY_COALESCED skipped=1'

rows: list[tuple[bool, str, str]] = []
LOG: list[str] = []

ARM_LIST = (
    "(A1) 6 presses em 50 ms -> UM drain coalescido, nao 6 transicoes",
    "(A2) estado resultante == hotkey_gesture.advance caminhado a mao",
    "(A3) pressao sozinha transita no mesmo instante (sem debounce)",
    "(A4) `live` entre dois `panels` mantem a ordem; paineis colapsam",
    "(A5) 3 presses escondido (mesmo estado) -> ZERO transicoes",
    "(A6) rajada realista de 5 presses em 320 ms -> no maximo 2 transicoes",
)


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


def log(message, *a, **k):  # o `log` do shell, capturado
    LOG.append(str(message))


def warn(message, *a, **k):
    LOG.append('WARN ' + str(message))


# ---------------------------------------------------------------------------
# Extracao do proprio ficheiro (o que corre, nao a minha transcricao)
# ---------------------------------------------------------------------------
def class_methods(source: str, cls_name: str, names) -> dict:
    tree = ast.parse(source)
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    out = {}
    for node in (cls.body if cls else []):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            out[node.name] = ast.get_source_segment(source, node) or ""
    return out


def load_module(name: str, path: Path):
    spec = _ilu.spec_from_file_location(name, str(path))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_dispatch(source: str, gesture):
    """Os corpos REAIS de despacho/worker/resolve, exec'd contra um `self` falso."""
    wanted = ("_hotkey_dispatch", "_hotkey_worker_loop", "_hotkey_resolve")
    bodies = class_methods(source, "SottoShell", wanted)
    if len(bodies) != len(wanted):
        return None
    namespace = {
        "log": log,
        "warn": warn,
        "threading": threading,
        "queue": queue,
        "window_visible": lambda hwnd: bool(SCREEN['visible']),
        "hotkey_numbers": lambda: gesture,
    }
    module = ast.Module(
        body=[ast.parse(bodies[name]).body[0] for name in wanted],
        type_ignores=[])
    exec(compile(module, "<sotto-shell-spam>", "exec"), namespace)
    return namespace


#: O que `window_visible` devolve. O fake show/hide escreve aqui; a funcao do
#: namespace le' daqui -- e' o mesmo caminho do shell real (medir a janela).
SCREEN = {'visible': False}


class BurstQueue(queue.Queue):
    """A fila do worker so' abre DEPOIS de a rajada inteira ter entrado.

    E' o caso que a coalescencia existe para resolver: o fio do hotkey
    entregou 6 presses em 50 ms e o worker ainda nao tinha vez. O produto nao
    tem portao nenhum -- quem fecha e' o instrumento, para medir o CODIGO em
    vez do escalonador da maquina.
    """

    def __init__(self):
        super().__init__()
        self.open = threading.Event()

    def get(self, block=True, timeout=None):
        self.open.wait(timeout=10.0)
        return super().get(block, timeout)


class Shell:
    """So' o que os tres metodos tocam. Nenhuma chamada Win32."""

    def __init__(self, methods, *, gated=False, visible=False, surface=''):
        self.hwnd = 4242
        self.visible = bool(visible)
        self.surface_applied = str(surface or '')
        self.visible_cache = self.visible
        self._caption_wanted = False
        self._caption_window_shown = False
        self.caption_overlay = None
        self._panel_presses = 0
        self._panel_press_lock = threading.Lock()
        self._hotkey_queue = BurstQueue() if gated else queue.Queue()
        self._hotkey_worker = None
        self.transitions: list[tuple[str, str, float]] = []
        self.starts: list[float] = []
        self.live_steps: list[bool] = []
        self.in_transition = False
        SCREEN['visible'] = bool(visible)
        for name in ("_hotkey_dispatch", "_hotkey_worker_loop", "_hotkey_resolve"):
            setattr(self, name, types.MethodType(methods[name], self))

    # -- o que o worker FAZ na janela: uma transicao do modelo de 400 ms ------
    def _transition(self, kind, surface):
        self.in_transition = True
        t0 = time.perf_counter()
        self.starts.append(t0)
        time.sleep(TRANSITION_S)
        if kind == 'show':
            self.visible = True
            self.surface_applied = str(surface)
            SCREEN['visible'] = True
        else:
            self.visible = False
            SCREEN['visible'] = False
        self.transitions.append((kind, str(surface), t0))
        self.in_transition = False
        return True

    def show_strip(self, reason):
        return self._transition('show', 'strip')

    def show_side(self, reason):
        return self._transition('show', 'panel')

    def hide_panel(self, reason):
        return self._transition('hide', self.surface_applied)

    def _set_live_enabled(self, payload):
        self.live_steps.append(bool(payload.get('on')))
        return 'enabled'

    # -- a leitura do instrumento -------------------------------------------
    def drain_lines(self):
        return [COALESCED.match(line) for line in LOG
                if line.startswith('HOTKEY_COALESCED presses=')]

    def drains(self):
        return [m for m in self.drain_lines() if m and int(m.group(1)) > 0]

    def skipped(self):
        return sum(1 for line in LOG if line.startswith(SKIPPED))

    def order(self):
        """`panels-applied`/`live`/`panels-skipped` na ordem em que sairam."""
        out = []
        for line in LOG:
            if line.startswith('HOTKEY_COALESCED presses='):
                out.append('panels-applied')
            elif line.startswith(SKIPPED):
                out.append('panels-skipped')
            elif line.startswith('HOTKEY_LIVE_STEP '):
                out.append('live')
        return out


def wait_idle(shell, timeout=8.0):
    """Espera o worker esvaziar a fila E sair da transicao (60 ms de calma)."""
    end = time.perf_counter() + timeout
    stable = 0
    while time.perf_counter() < end:
        if shell.in_transition or not shell._hotkey_queue.empty():
            stable = 0
        else:
            stable += 1
            if stable >= 3:
                return True
        time.sleep(0.02)
    return False


def burst(shell, presses, gap_s=0.002):
    """Entrega a rajada como o fio do hotkey a entrega: `dispatch` por pressao."""
    t0 = time.perf_counter()
    for _ in range(presses):
        shell._hotkey_dispatch('panels')
        if gap_s:
            time.sleep(gap_s)
    return (time.perf_counter() - t0) * 1000.0


# ---------------------------------------------------------------------------
# Veredicto
# ---------------------------------------------------------------------------
def verdict(name: str) -> int:
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print(f"FALHA: {label}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={total} pass={passed} fail={failed} "
          f"(rc={EXIT_PASS if not failed else EXIT_FAIL})")
    return EXIT_PASS if not failed else EXIT_FAIL


def run(shell_path: Path, label: str = 'AFTER') -> int:
    if not shell_path.exists():
        print(f"VERDICT: FAIL -- {shell_path} ausente")
        return EXIT_FAIL
    if label == 'AFTER':
        print("BRACOS JULGADOS:")
        for line in ARM_LIST:
            print(f"  {line}")
    rows.clear()
    LOG.clear()

    source = shell_path.read_text(encoding='utf-8')
    gesture = load_module("hotkey_gesture_spam", shell_path.parent / "hotkey_gesture.py")
    methods = build_dispatch(source, gesture)
    if not methods:
        print("VERDICT: FAIL -- nao consegui extrair despacho/worker/resolve")
        return EXIT_FAIL

    # -- (A1) 6 presses em 50 ms -> UM drain --------------------------------
    print("\nARM (A1) -- a rajada de 50 ms, com o worker ainda sem vez")
    LOG.clear()
    shell = Shell(methods, gated=True, visible=False, surface='')
    t_first = time.perf_counter()
    burst_ms = burst(shell, 6)
    shell._hotkey_queue.open.set()
    idle = wait_idle(shell)
    wall_ms = (time.perf_counter() - t_first) * 1000.0
    drains = shell.drains()
    fifo_ms = 6 * TRANSITION_S * 1000.0
    print(f"  MEDIDO {label}: burst_ms={burst_ms:.2f} wall_ms={wall_ms:.2f} "
          f"drains={len(drains)} skipped={shell.skipped()} "
          f"window_transitions={len(shell.transitions)} "
          f"fifo_wall_ms={fifo_ms:.0f}")
    add(idle, "(A1) o worker ficou ocioso (a rajada foi processada)")
    add(burst_ms < 50.0, "(A1) as 6 presses entraram em < 50 ms",
        f"burst_ms={burst_ms:.2f}")
    add(len(drains) == 1,
        "(A1) 6 presses -> UM drain coalescido (uma transicao decidida), nao 6",
        f"drains={len(drains)} presses={[m.group(1) for m in drains]}")
    add(shell.skipped() == 5,
        "(A1) os outros 5 tokens sao no-ops declarados (skipped=1)",
        f"skipped={shell.skipped()}")
    add(len(shell.transitions) <= 1,
        "(A1) a janela mexe no maximo uma vez (6 passos = estado inicial)",
        f"window_transitions={len(shell.transitions)}")
    add(wall_ms < fifo_ms / 2.0,
        "(A1) o muro da rajada caiu para menos de metade do FIFO",
        f"wall_ms={wall_ms:.1f} vs fifo_ms={fifo_ms:.0f}")

    # -- (A2) o estado final e' o de `advance` caminhado a mao --------------
    print("\nARM (A2) -- o estado aplicado e' o do ciclo caminhado N passos")
    LOG.clear()
    shell = Shell(methods, gated=True, visible=False, surface='')
    burst(shell, 4)
    shell._hotkey_queue.open.set()
    wait_idle(shell)
    expected = gesture.advance(False, '', 4)
    add((shell.visible, shell.surface_applied) == expected,
        "(A2) 4 presses escondido -> o mesmo (visible, surface) de advance()",
        f"shell={(shell.visible, shell.surface_applied)} "
        f"advance={expected}")

    # -- (A3) uma pressao sozinha nao espera janela nenhuma -----------------
    print("\nARM (A3) -- uma pressao sozinha transita AGORA (sem debounce)")
    LOG.clear()
    shell = Shell(methods, visible=False, surface='')
    t0 = time.perf_counter()
    dispatched = shell._hotkey_dispatch('panels')
    t_return = time.perf_counter()
    end = t_return + 2.0
    while not shell.starts and time.perf_counter() < end:
        time.sleep(0.001)
    start_ms = ((shell.starts[0] - t0) * 1000.0) if shell.starts else -1.0
    wait_idle(shell)
    total_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  MEDIDO {label}: dispatch_ms={(t_return - t0) * 1000.0:.2f} "
          f"transition_start_ms={start_ms:.2f} total_ms={total_ms:.2f}")
    add(dispatched is True, "(A3) o despacho aceitou a pressao")
    add(shell.starts and 0.0 <= start_ms < 150.0,
        "(A3) a transicao comeca no mesmo instante -- nada de janela de 400 ms",
        f"transition_start_ms={start_ms:.2f}")
    add(len(shell.transitions) == 1,
        "(A3) a pressao sozinha faz exactamente UMA transicao",
        f"transitions={len(shell.transitions)}")
    add(total_ms >= TRANSITION_S * 1000.0 * 0.9,
        "(A3) e o muro total e' o da transicao (400 ms), sem adiamento",
        f"total_ms={total_ms:.1f}")

    # -- (A4) `live` entre dois `panels` -------------------------------------
    print("\nARM (A4) -- Ctrl+Space no meio da rajada nao perde o lugar")
    LOG.clear()
    shell = Shell(methods, gated=True, visible=False, surface='')
    shell._hotkey_dispatch('panels')
    shell._hotkey_dispatch('live')
    shell._hotkey_dispatch('panels')
    shell._hotkey_queue.open.set()
    wait_idle(shell)
    order = shell.order()
    print(f"  MEDIDO {label}: order={order} "
          f"drains={[m.group(1) for m in shell.drains()]} "
          f"transitions={len(shell.transitions)}")
    add(order == ['panels-applied', 'live', 'panels-skipped'],
        "(A4) a ordem e' painel -> live -> painel (o token do meio conta)",
        str(order))
    add([m.group(1) for m in shell.drains()] == ['2'],
        "(A4) as duas presses de painel colapsam no primeiro token",
        str([m.group(1) for m in shell.drains()]))
    add(len(shell.transitions) == 1,
        "(A4) e a rajada de paineis custa UMA transicao",
        f"transitions={len(shell.transitions)}")

    # -- (A5) presses que somam o mesmo estado -------------------------------
    print("\nARM (A5) -- 3 presses escondido: a janela NAO se mexe")
    LOG.clear()
    shell = Shell(methods, gated=True, visible=False, surface='')
    burst(shell, 3)
    shell._hotkey_queue.open.set()
    wait_idle(shell)
    drains = shell.drains()
    print(f"  MEDIDO {label}: drains={len(drains)} "
          f"transitions={[(k, s) for k, s, _ in shell.transitions]}")
    add(len(drains) == 1 and drains[0].group(5) == '0',
        "(A5) um drain com transitions=0", f"lines={drains and drains[0].group(0)}")
    add(len(shell.transitions) == 0,
        "(A5) zero chamadas de show/hide -- o mesmo estado nao custa pixel",
        f"transitions={shell.transitions}")
    # ... e a tecla continua viva depois do no-op.
    shell._hotkey_dispatch('panels')
    wait_idle(shell)
    add(len(shell.transitions) == 1 and shell.visible,
        "(A5) a pressao seguinte volta a andar (1 pressao -> strip)",
        f"transitions={[(k, s) for k, s, _ in shell.transitions]}")

    # -- (A6) rajada realista: presses a chegar DURANTE a transicao ----------
    print("\nARM (A6) -- 5 presses em 320 ms (a transicao ja' a decorrer)")
    LOG.clear()
    shell = Shell(methods, visible=False, surface='')
    t_first = time.perf_counter()
    for index in range(5):
        if index:
            time.sleep(0.08)          # 80 ms entre presses, todas < 400 ms
        shell._hotkey_dispatch('panels')
    wait_idle(shell)
    wall_ms = (time.perf_counter() - t_first) * 1000.0
    fifo_ms = 5 * TRANSITION_S * 1000.0
    print(f"  MEDIDO {label}: wall_ms={wall_ms:.1f} "
          f"transitions={[(k, s) for k, s, _ in shell.transitions]} "
          f"drains={[m.group(1) for m in shell.drains()]} "
          f"fifo_wall_ms={fifo_ms:.0f}")
    add(len(shell.transitions) <= 2,
        "(A6) a rajada realista custa no maximo 2 transicoes, nao 5",
        f"transitions={len(shell.transitions)}")
    add(wall_ms < fifo_ms,
        "(A6) e o muro cai abaixo do FIFO",
        f"wall_ms={wall_ms:.1f} vs fifo_ms={fifo_ms:.0f}")

    return verdict("hotkey-spam")


# ---------------------------------------------------------------------------
# --neg-arm: muta uma COPIA para FIFO (uma transicao por pressao) e exige RED
# ---------------------------------------------------------------------------
MUTANT_OLD = """        with self._panel_press_lock:
            presses = int(self._panel_presses)
            self._panel_presses = 0"""
MUTANT_NEW = """        with self._panel_press_lock:
            presses = 1 if self._panel_presses else 0
            self._panel_presses = max(0, self._panel_presses - 1)"""


def neg_arm() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='hotkey-spam-neg-'))
    try:
        webview = tmp / "app" / "webview"
        webview.mkdir(parents=True)
        shutil.copy2(SHELL, webview / "sotto_webview.py")
        shutil.copy2(GESTURE, webview / "hotkey_gesture.py")
        target = webview / "sotto_webview.py"
        text = target.read_text(encoding='utf-8')
        if MUTANT_OLD not in text:
            print("NEG-ARM FAIL -- nao encontrei o dreno (o texto mudou)")
            return EXIT_FAIL
        target.write_text(text.replace(MUTANT_OLD, MUTANT_NEW, 1), encoding='utf-8')
        print("=== NEG-ARM: FIFO de volta (um passo por token), numa COPIA")
        rows.clear()
        rc = run(webview / "sotto_webview.py", label='NEG(FIFO)')
        failed = [label for ok, label, _ in rows if not ok]
        a1_red = any(label.startswith('(A1)') and '6 presses -> UM drain' in label
                     for label in failed)
        a5_red = any(label.startswith('(A5)') for label in failed)
        passed = len(rows) - len(failed)
        print(f"  NEG-ARM ARM COUNTS: arms={len(rows)} pass={passed} "
              f"fail={len(failed)} A1_red={a1_red} A5_red={a5_red} rc={rc}")
        if rc == EXIT_FAIL and a1_red and a5_red:
            print(f"NEG-ARM PASS -- RED as designed em A1 e A5 "
                  f"({len(failed)} arms RED no total)")
            return EXIT_PASS
        print("NEG-ARM FAIL -- o oraculo NAO ve a regressao FIFO")
        return EXIT_FAIL
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv) -> int:
    if "--neg-arm" in argv:
        return neg_arm()
    return run(SHELL)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
