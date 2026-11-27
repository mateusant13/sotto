#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-11-04 -- o Ctrl+Space em gaming
# (nao dava nada) e fora dele, e a deteccao de "gaming" que ele pediu. Mede o
# codigo que corre: o observador REAL, o caminho REAL do toggle e o detector REAL.
"""ORACLE: Ctrl+Space em gaming, o nao-roubo de foco, e a deteccao de jogo.

ORDEM DO DONO, verbatim (2026-11-04):

    *"e em gaming: control espaço nao da display na legenda. nao faz nada. nem on
    nem off. fora de gaming: control espaço nao ativa o espaço em apps. detecta
    'gaming' parecido com o que meu projeto !watcher do disco i faz."*

O QUE ESTE ORACULO MEDE (e o que ele NAO mede: tecla fisica -- um `keybd_event`
mede o Windows, nao a app, e este repo proibe-o):

  (a) uma pressao DENTRO do modo jogo e' vista e LIGA a legenda -- pelo
      observador real (`PassiveHotkeyThread.run`, do ficheiro) e pela decisao real
      (`_hotkey_resolve` -> `_set_live_enabled` -> `show_caption_window` ->
      `NativeCaptionOverlay.show`), com o detector em GAMING;
  (b) uma segunda pressao DESLIGA-a (on, off);
  (c) o toggle NAO rouba o primeiro plano: `SetForegroundWindow`/`SetActiveWindow`/
      `SetFocus`/`AttachThreadInput` = 0 chamadas, `ShowWindow` so' com
      `SW_SHOWNOACTIVATE`/`SW_HIDE`, `SetWindowPos` sempre com `SWP_NOACTIVATE` --
      medido nas funcoes REAIS, com o `user32` por tras de um gravador;
  (d) o toggle NAO chama nenhuma API que COMA teclas: `RegisterHotKey`,
      `SetWindowsHookEx`, `keybd_event`, `SendInput`, `BlockInput` = 0; a UNICA
      leitura de teclado do observador e' `GetAsyncKeyState` (passiva);
  (e) `is_gaming()` e' True com um processo de jogo nomeado e False com um
      processo comum -- e o detector REAL (`EnumProcesses`) nesta maquina nao
      inventa um jogo a partir do `python.exe`;
  (f) o DWELL mantem `is_gaming()` True pelos ticks configurados depois da ultima
      vista (o `game_dwell_ticks` do `!watcher`) e cai exactamente no tick
      seguinte;
  (g) o tick do detector custa menos do que o orcamento declarado
      (`gaming_mode.TICK_BUDGET_MS`) -- medido, com uma enumeracao por tick;
  (h) o observador sobrevive a um processo a queimar a maquina (um laco Python
      que segura o GIL, o analogo de um jogo a comer o CPU): a pressao que cai
      INTEIRA dentro da volta perdida continua a ser vista, e o `max_gap_ms` que
      o laco publica e' lido de volta.

COMO. `ast` extrai do FICHEIRO QUE VAI CORRER os corpos de `_hotkey_resolve`,
`_set_live_enabled`, `show_caption_window`, `show` (do overlay) e a classe
`PassiveHotkeyThread`; eles correm contra um shell falso, um `user32`-GRAVADOR e
uma sequencia de teclas injectada. Nenhuma janela e' aberta, nenhum ctypes de
input e' tocado, nada e' posto no ecra do dono.

Uso:
    python _main/gaming-hotkey-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/gaming-hotkey-oracle.py --neg-arm  -> muta uma COPIA e exige RED
    SOTTO_ROOT=<arvore> ...                         -> julga outra arvore
"""
from __future__ import annotations

import ast
import builtins
import ctypes
import importlib.util as _ilu
import json
import os
import re
import shutil
import sys
import symtable
import tempfile
import threading
import time
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SOTTO_ROOT") or HERE.parent).resolve()
WEBVIEW = ROOT / "app" / "webview"
SHELL = WEBVIEW / "sotto_webview.py"
GESTURE = WEBVIEW / "hotkey_gesture.py"
OVERLAY = WEBVIEW / "caption_overlay.py"
GAMING = WEBVIEW / "gaming_mode.py"
EXIT_PASS, EXIT_FAIL = 0, 1

#: As APIs que COMEM a tecla ao resto do sistema. Uma so' chamada no caminho e'
#: o defeito: `RegisterHotKey` toma a combinacao, um hook low-level mata-a em
#: todas as janelas, e `keybd_event`/`SendInput`/`BlockInput` injectam/substituem.
KEY_EATING = ('RegisterHotKey', 'SetWindowsHookExW', 'SetWindowsHookExA',
              'keybd_event', 'SendInput', 'BlockInput')

#: As APIs que MOVEM o primeiro plano. Nenhuma pode ser chamada num toggle.
FOCUS_TAKING = ('SetForegroundWindow', 'SetActiveWindow', 'SetFocus',
                'BringWindowToTop', 'AttachThreadInput', 'SetWindowLongW',
                'SetWindowLongPtrW')

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOACTIVATE = 0x0010

rows: list[tuple[bool, str, str]] = []

ARM_LIST = (
    "(a) pressao em GAMING: vista e LIGA a legenda",
    "(b) pressao seguinte DESLIGA-a (on, off)",
    "(c) o toggle NAO rouba o primeiro plano (flags medidas, nao lidas)",
    "(d) o toggle NAO chama API que come teclas (0 chamadas)",
    "(e) is_gaming() True para jogo nomeado, False para processo comum",
    "(f) o dwell do watcher mantem is_gaming() True N ticks e cai depois",
    "(g) o tick do detector custa menos que o orcamento declarado",
    "(h) pressao inteira dentro de uma volta perdida (laco a segurar o GIL): vista",
)


def add(ok, name, detail=""):
    if not isinstance(detail, str):
        detail = str(detail)
    rows.append((bool(ok), name, detail))
    print("  %s %s%s" % ('GREEN' if ok else 'RED  ', name,
                         ("  " + detail) if detail else ""))
    return bool(ok)


def wait_until(cond, timeout=2.0, step=0.005):
    """Espera ate' `cond()` ser verdade, com prazo. Devolve o que `cond` deu.

    O DETERMINISMO DE UM BRACO NAO PODE SER UM `sleep` (MEDIDO 2026-11-04): num
    braco de pressao, parar 100 ms depois de soltar a leitura e' uma aposta em
    que o fio foi servido nesse intervalo -- e numa maquina a correr tres lanes
    a aposta perde, exactamente as vezes que ensinam a repetir o portao. Quem
    espera um EVENTO espera pelo evento.
    """
    limit = time.monotonic() + float(timeout)
    while True:
        if cond():
            return True
        if time.monotonic() >= limit:
            return False
        time.sleep(step)


def load_module(name, path):
    spec = _ilu.spec_from_file_location(name, str(path))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

#: O PROPRIO DIRECTORIO NO `sys.path`: `_astcache` vive ao lado deste ficheiro, e um
#: import por nome so' resolve quando o directorio do SCRIPT esta' na lista -- verdade
#: ao correr `python _main\x.py`, mentira quando o oraculo e' importado por outro
#: instrumento (a sonda que mediu a distribuicao do max_gap foi assim que caiu num
#: `ModuleNotFoundError`, medido 2026-11-12).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
#: A ARVORE VEM DE `_astcache` (2026-11-12). Este ficheiro tinha a SUA copia da
#: cura (**24,9 s em `builtins.compile`** e 95 `ast.parse` num `--neg-arm` de
#: 57 s, medido por `cProfile`) -- a quarta copia da mesma convencao na arvore.
from _astcache import tree as _tree  # noqa: E402


def _class_node(source, cls_name):
    tree = _tree(source)
    return next((n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == cls_name), None)


def class_methods(source, cls_name, names):
    cls = _class_node(source, cls_name)
    if cls is None:
        return {}
    out = {}
    # `ast.get_source_segment` re-parte a fonte INTEIRA por chamada: medido com cProfile
    # aqui, 2,5 s em 6 chamadas, e 57,3 s para as 214 funcoes de `SottoShell` (2026-11-11).
    # A tabela de linhas e' uma so' para o ficheiro todo e a fatia e' aritmetica. O
    # contrato e' o do original com `padded=False`: a PRIMEIRA linha comeca na coluna do
    # nome e a ultima corta na coluna final -- nao e' um `dedent` (a indentacao das
    # linhas do meio fica como esta', e e' isso que faz o `ast.parse` do fragmento valer).
    lines = source.splitlines(keepends=True)
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            lineno = node.lineno - 1
            end_lineno = (getattr(node, 'end_lineno', None) or node.lineno) - 1
            col = node.col_offset
            end_col = getattr(node, 'end_col_offset', None)
            if end_col is None:
                out[node.name] = ast.get_source_segment(source, node) or ""
            elif lineno == end_lineno:
                out[node.name] = lines[lineno][col:end_col]
            else:
                out[node.name] = (lines[lineno][col:] + ''.join(lines[lineno + 1:end_lineno])
                                  + lines[end_lineno][:end_col])
    return out


def method_names(source, cls_name):
    cls = _class_node(source, cls_name)
    return {n.name for n in (cls.body if cls else []) if isinstance(n, ast.FunctionDef)}


def names_used(fragment, name):
    """O NOME aparece no CODIGO (nao no comentario)? -- `ast`, nao regex."""
    try:
        tree = ast.parse(fragment)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
        if isinstance(node, ast.Name) and node.id == name:
            return True
    return False


def user32_names(fragment):
    """Os nomes lidos de `user32` num fragmento (`user32.X`, `_user32.X`)."""
    tree = ast.parse(fragment)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in ('user32', '_user32'):
                out.add(node.attr)
    return out


def kernel32_names(fragment):
    """Os nomes lidos de `kernel32` num fragmento (`kernel32.X`, `_kernel32.X`)."""
    tree = ast.parse(fragment)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in ('kernel32', '_kernel32'):
                out.add(node.attr)
    return out


def api_names(fragment):
    """TODO nome usado ou chamado no CODIGO (comentario e docstring nao contam)."""
    tree = ast.parse(fragment)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Name):
            out.add(node.id)
    return out


# ---------------------------------------------------------------------------
# O `user32`-GRAVADOR: mede o EFEITO (quais chamadas, com que flags), nao o texto
# ---------------------------------------------------------------------------
class RecordingUser32(object):
    """Registra (nome, args) de cada chamada; NAO chama o Windows.

    Nao chamar e' a escolha segura: `ShowWindow`/`SetWindowPos` com um hwnd falso
    nao tem efeito util, e um instrumento que pode mexer numa janela e' um
    instrumento que pode mostrar uma janela no ecra do dono.
    """

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args))
            return 1
        return record

    def names(self):
        return [name for name, _ in self.calls]

    def of(self, name):
        return [args for n, args in self.calls if n == name]

    def reset(self):
        self.calls.clear()


# ---------------------------------------------------------------------------
# O FIO DO OBSERVADOR, do ficheiro, com o teclado injectado
# ---------------------------------------------------------------------------
class FakeWindows(object):
    """O ESTADO das teclas, com a semantica do `GetAsyncKeyState`.

    `press(vk)` põe o bit 0 (a borda) -- que o Windows guarda ate' alguem o ler,
    e que e' exactamente a cura do toque perdido. `hold(vk, True)` põe o 0x8000.

    `schedule(t, press=True, vk=..., hold_s=...)` agenda um evento no RELOGIO DE
    PAREDE. E' assim que a maquina de estados imita o Windows: o SO recebe a
    tecla sem precisar do GIL deste processo, logo a pressao pode acontecer
    DENTRO de uma volta em que a thread principal nao corre (o caso medido,
    `max_gap_ms=29266`). Os eventos sao aplicados na primeira leitura que os
    alcanca -- que e' o que o bit 0 faz de verdade.
    """

    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.down = {}
        self.edge = {}
        self.pending = []
        #: A LEITURA PRESA (2026-11-04). `gate` ABERTO (posto) == as leituras
        #: passam; FECHADO == a `state()` seguinte FICA presa e avisa em
        #: `gate_entered`. E' o que torna a "volta tardia" DETERMINISTICA: a
        #: ordem (ler / carregar na tecla / soltar) deixa de ser uma corrida de
        #: relogio de parede e passa a ser um handshake.
        #:
        #: O SENTIDO E' "ABERTO", e nao "fechado", por MEDICAO (2026-11-04): com
        #: `gate.post()` a dizer "bloqueia", um `clear()` que chegasse entre o
        #: `set()` de `gate_entered` e o `wait()` PERDIA o aviso e o observador
        #: ficava preso para sempre (`loops=5 depois=5`, medido). `is_set()` em
        #: laco nao perde nada.
        self.gate = None
        self.gate_entered = None

    def press(self, vk, hold_s=0.0):
        self.edge[int(vk)] = True
        if hold_s:
            self.down[int(vk)] = True

    def release(self, vk):
        self.down.pop(int(vk), None)

    def schedule(self, at, vk, hold_s=0.0):
        """Agenda uma pressao em `at` (relogio de parede) que dura `hold_s`."""
        self.pending.append((float(at), int(vk), float(hold_s)))

    def _apply(self, now):
        keep = []
        for at, vk, hold_s in self.pending:
            if at > now:
                keep.append((at, vk, hold_s))
                continue
            self.edge[vk] = True
            # O `down` so' e' verdadeiro enquanto a tecla esta' fisicamente em
            # baixo: um evento de 30 ms ja' acabou quando a leitura chega.
            if hold_s and at + hold_s > now:
                self.down[vk] = True
        self.pending = keep

    def state(self, vk):
        vk = int(vk)
        # A VOLTA PRESA, encenada sem relogio: quem le' fica aqui' ate' o
        # oraculo ter posto a pressao inteira -- e so' o bit 0 a pode salvar.
        if self.gate is not None and not self.gate.is_set():
            if self.gate_entered is not None:
                self.gate_entered.set()
            while not self.gate.is_set():
                self.gate.wait(0.05)
        self._apply(self.clock())
        bits = 0
        if self.down.get(vk):
            bits |= 0x8000
        if self.edge.pop(vk, False):
            bits |= 0x0001
        return bits


def class_consts(source, cls, names):
    """O valor LITERAL das constantes da CLASSE, lido do ficheiro vivo.

    MEDIDO 2026-11-15: `show_caption_window` le' `self.CAPTION_REPLAY_MAX_S`, que
    e' atributo de CLASSE (`sotto_webview.py:18935`) e nao nome de modulo -- o
    `module_consts` nao o alcanca, o `self` do duplo nao o tem, e o corpo morria
    em `AttributeError` dentro do `except` de `_set_live_enabled`, publicando
    `LIVE_ENABLED_FAILED` e nenhuma janela. O defeito era do ARNES. O valor vem
    do PROPRIO ficheiro: reencenar o numero aqui media a copia, nao o produto.
    """
    wanted = set(names)
    out = {}
    for node in _tree(source).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if (isinstance(target, ast.Name)
                                and target.id in wanted):
                            try:
                                out[target.id] = ast.literal_eval(item.value)
                            except (ValueError, SyntaxError):
                                continue
                elif (isinstance(item, ast.AnnAssign)
                      and isinstance(item.target, ast.Name)
                      and item.target.id in wanted):
                    try:
                        out[item.target.id] = ast.literal_eval(item.value)
                    except (ValueError, SyntaxError):
                        continue
    return out


def module_consts(source):
    """As constantes de MODULO do ficheiro -- o chao de qualquer namespace extraido.

    MEDIDO 2026-11-11: a cura de 2026-11-10 que deu UM so' relogio ao show
    (`SHOW_BUDGET_S = SHOW_BUDGET_MS / 1000.0`) pos uma constante DERIVADA no
    caminho de `_hotkey_resolve`. O arnes injectava so' as costuras que conhecia
    e o corpo extraido morria com `NameError` -- julgando o arnes em vez do
    produto. O valor e' lido do PROPRIO ficheiro (literais e derivadas); o que
    for injectado por cima continua a ganhar.
    """
    out = {}
    try:
        tree = _tree(source)
    except SyntaxError:
        return out
    assigns = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if names:
            assigns.append((names, node))
    for names, node in assigns:
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError, TypeError):
            continue
        for name in names:
            out[name] = value
    # SEGUNDA PASSAGEM: o que nao e' literal mas e' INOFENSIVO de avaliar
    # (`SHOW_BUDGET_MS / 1000.0`) corre numa COPIA do namespace, com as
    # constantes ja' pescadas la' dentro -- sem isso o lado direito da
    # atribuicao tambem falta.
    for names, node in assigns:
        if all(name in out for name in names):
            continue
        env = dict(out)
        env.update({"os": os, "sys": os.sys, "time": time,
                    "__builtins__": __builtins__})
        try:
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         "<consts>", "exec"), env)
        except Exception:                                        # noqa: BLE001
            continue
        for name in names:
            if name in env:
                out[name] = env[name]
    return out


def unresolved_globals(module, namespace):
    """Os nomes de MODULO que os corpos extraidos LEEM e o namespace nao tem.

    MEDIDO 2026-11-11: um nome de modulo em falta dava `NameError` a meio do
    braco -- e, onde havia um `except` pelo meio, dava ZERO (o oraculo acusava o
    produto). Este portao de `symtable`, sobre o modulo que vai ser exec'd,
    nomeia a costura em falta antes de correr o corpo.
    """
    table = symtable.symtable(ast.unparse(module), "<extract>", "exec")
    have = set(namespace) | set(dir(builtins))
    for node in module.body:            # o proprio modulo define nomes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            have.add(node.name)
        elif isinstance(node, ast.Assign):
            have.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            have.add(node.target.id)
    need = set()
    for child in table.get_children():
        for symbol in child.get_symbols():
            if symbol.is_global():
                need.add(symbol.get_name())
    return sorted(name for name in need if name not in have)


def build_observer(source, gesture, log_fn, windows):
    """A classe `PassiveHotkeyThread` do FICHEIRO, sem ctypes real e sem a tecla dele."""
    node = _class_node(source, 'PassiveHotkeyThread')
    if node is None:
        return None
    kernel = type('K', (), {
        'GetCurrentThreadId': staticmethod(lambda: 4242),
        'SetThreadPriority': staticmethod(lambda *a: 1),
        'GetCurrentThread': staticmethod(lambda: -2),
    })()
    user = type('U', (), {
        'GetAsyncKeyState': staticmethod(windows.state),
    })()
    namespace = {
        'threading': threading,
        'time': time,
        'kernel32': kernel,
        'user32': user,
        '_HOTKEY_TRACE': False,
        'hotkey_numbers': lambda: gesture,
        'parse_accelerator': gesture.parse_accelerator,
        'log': log_fn,
        '__builtins__': __builtins__,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 '<passive-hotkey>', 'exec'), namespace)
    return namespace['PassiveHotkeyThread']


class FakeLog(object):
    def __init__(self):
        self.lines = []
        self._lock = threading.Lock()

    def __call__(self, message, *a, **k):
        with self._lock:
            self.lines.append(str(message))

    def has(self, needle):
        return any(needle in line for line in self.lines)

    def presses(self):
        return [line for line in self.lines if 'HOTKEY_PRESSED role=live' in line]


# ---------------------------------------------------------------------------
# O CAMINHO REAL DO TOGGLE: `_hotkey_resolve` -> `_set_live_enabled`
#   -> `show_caption_window` -> `NativeCaptionOverlay.show`
# ---------------------------------------------------------------------------
def build_toggle(source, overlay_source, recorder, log_fn):
    """Os QUATRO corpos reais, ligados, com o `user32` por tras do gravador."""
    shell_bodies = class_methods(source, 'SottoShell',
                                 ('_hotkey_resolve', '_set_live_enabled',
                                  'show_caption_window'))
    overlay_bodies = class_methods(overlay_source, 'NativeCaptionOverlay',
                                   ('show',))
    if len(shell_bodies) != 3 or len(overlay_bodies) != 1:
        return None
    overlay_ns = {
        '_user32': recorder,
        'HWND_TOPMOST': -1,
        'SWP_NOMOVE': 0x0002,
        'SWP_NOSIZE': 0x0001,
        'SWP_NOACTIVATE': SWP_NOACTIVATE,
        'SWP_SHOWWINDOW': 0x0040,
        'SW_SHOWNOACTIVATE': SW_SHOWNOACTIVATE,
        'SW_HIDE': SW_HIDE,
        'log': log_fn,
        'ctypes': ctypes,
        '__builtins__': __builtins__,
    }
    ov_body = overlay_bodies['show'].replace(
        'def show(self, on=True):', 'def show(self, on=True):', 1)
    exec(compile(ast.Module(body=[ast.parse(ov_body).body[0]], type_ignores=[]),
                 '<overlay-show>', 'exec'), overlay_ns)
    OverlayClass = overlay_ns['show']

    class OverlayDouble(object):
        """A janela do overlay e' FALSA; o `show` e' o do ficheiro."""

        def __init__(self):
            self.hwnd = 987654
            self.text = "legenda de prova"
            self.previous = ""
            self._blank = False
            self.visible = False
            self._geom_logged = True
            self.lock = threading.RLock()
            self.shown = []
            # O `show` REAL LE' DOIS ATRIBUTOS QUE O `__init__` DO FICHEIRO POE
            # (medido 2026-11-15: `caption_overlay.py:541` e `:569`). O `show`
            # de 2026-11-14 (o painel manda no Z) passou a chamar o provedor
            # `z_below` e a escrever a falha em `self.log` -- um duplo sem os
            # dois pagava `AttributeError` DENTRO do `try`, o `show` levantava
            # e a arm lia `shown=[]`. O defeito era do ARNES: a janela nao
            # aparecia porque o fake nao era a classe que ele dizia ser.
            self.log = log_fn
            self.z_below = None

        def _update(self):
            return True

        def show(self, on=True):
            ok = OverlayClass(self, on)
            self.shown.append(bool(on))
            return ok

        def set_work_area(self, *a, **k):
            return True

    overlay = OverlayDouble()

    # O CHAO DE CONSTANTES DO FICHEIRO (2026-11-11): a cura de 2026-11-10
    # (`SHOW_BUDGET_S`, *"um so' relogio"* do show) fez `_hotkey_resolve` ler
    # nomes de modulo. Aqui o braco so' empurra a tecla `live`, que sai antes do
    # orcamento -- mas a costura em falta e' a mesma, e um `panels` futuro morria
    # com `NameError` em vez de ser medido.
    ns = module_consts(source)
    ns.update({
        'hotkey_numbers': lambda: _GESTURE[0],
        'window_visible': lambda hwnd: False,
        'log': log_fn,
        'ctypes': ctypes,
        '__builtins__': __builtins__,
    })
    # O QUE `_set_live_enabled` LE' E O ARNES NAO DAVA (2026-11-11): `json` e
    # `time` no caminho do replay, e `_caption_replay_allowed` (funcao de MODULO,
    # extraida do ficheiro como o `hotkey-live-toggle` ja' fazia). Sem eles o
    # `except` do proprio `_set_live_enabled` engolia um `NameError` e este braco
    # passava a medir um interruptor que tinha falhado por dentro.
    helpers = [node for node in _tree(source).body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == '_caption_replay_allowed']
    if not helpers:
        log_fn('EXTRACAO_INCOMPLETA falta _caption_replay_allowed')
        return None
    ns.update({'json': json, 'time': time})
    module = ast.Module(
        body=helpers + [ast.parse(shell_bodies[n]).body[0]
                        for n in ('_hotkey_resolve', '_set_live_enabled',
                                  'show_caption_window')],
        type_ignores=[])
    missing = unresolved_globals(module, ns)
    if missing:
        log_fn(f'EXTRACAO_INCOMPLETA nomes_de_modulo_em_falta={missing}')
        return None
    exec(compile(module, '<sotto-toggle>', 'exec'), ns)
    resolve, set_live, show_window = (ns['_hotkey_resolve'], ns['_set_live_enabled'],
                                      ns['show_caption_window'])

    class ShellDouble(object):
        """So' o que os tres metodos tocam. Nenhuma janela, nenhum teclado."""

        def __init__(self):
            self.hwnd = 4242
            self.visible = False
            self.surface_applied = 'strip'
            self._caption_wanted = False
            self._caption_window_shown = False
            self.caption_overlay = overlay
            self.work_area = lambda: {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
            self.display = {'scaleFactor': 1.0}
            self.live_calls = []
            # AS CONSTANTES DE CLASSE SAEM DO FICHEIRO VIVO (medido 2026-11-15):
            # `show_caption_window` le' `self.CAPTION_REPLAY_MAX_S`; sem ela o
            # corpo morria em `AttributeError` dentro do `except` e o braco
            # julgava o arnes. So' a que os corpos leem -- um mapa cheio de
            # numeros copiados aqui seria a copia a passar pelo produto.
            for _name, _value in class_consts(
                    source, 'SottoShell', ('CAPTION_REPLAY_MAX_S',)).items():
                setattr(self, _name, _value)
            # OS TRES SLOTS DE ESTADO DA LEGENDA SAO DO PRODUTO (medido
            # 2026-11-15, mesma rodada): `_set_live_enabled` chama
            # `_caption_status_start()` / `_caption_status_stop()` /
            # `_caption_off_ack()` -- o aviso de "model-loading" do Ctrl+Space de
            # 2026-11-11. Um duplo sem eles pagava `AttributeError` dentro do
            # `except`, e o unico sinal era `LIVE_ENABLED_FAILED` no log: a
            # decisao (`live_calls`) continuava certa e a arm nova era a unica
            # que via a falha. Gravados, porque um fake mudo deixaria a cura de
            # 2026-11-11 sem prova e o braco mediria o arnes.
            self.caption_status = []

        def _post(self, fn):
            return fn()

        def _caption_status_start(self):
            self.caption_status.append('start')

        def _caption_status_stop(self):
            self.caption_status.append('stop')

        def _caption_off_ack(self):
            self.caption_status.append('off-ack')

        def exec_js_post(self, script):
            return True

        def _caption_wanted_store(self, on):
            return True

        def _hotkey_resolve(self, kind):
            return resolve(self, kind)

        def _set_live_enabled(self, payload):
            return set_live(self, payload)

        def show_caption_window(self, on):
            return show_window(self, on)

        def show_strip(self, reason):
            self.visible = True
            self.surface_applied = 'strip'
            return 'strip'

        def show_side(self, reason):
            self.visible = True
            self.surface_applied = 'panel'
            return 'panel'

        def hide_panel(self, reason):
            self.visible = False
            return True

    shell = ShellDouble()
    orig_set_live = shell._set_live_enabled

    def _tracked(payload):
        shell.live_calls.append(bool((payload or {}).get('on')))
        return orig_set_live(payload)

    shell._set_live_enabled = _tracked
    return shell, overlay


_GESTURE = [None]


# ---------------------------------------------------------------------------
# A CORRIDA
# ---------------------------------------------------------------------------
def process_names_primitive(source):
    """UM snapshot por enumeracao, NENHUM handle por pid -- lido do AST, sem relogio.

    O racio tick/enumeracao NAO e' um invariante do produto: e' uma afirmacao
    sobre a CARGA da maquina (medido 2026-11-27: 1,53 com 586 processos, contra
    0,77 com 669 noutra corrida desta casa, sem regressao nenhuma). O que o
    produto GARANTE e' mecanico: `_process_names` chama UM
    `CreateToolhelp32Snapshot` e nao abre um handle por pid. E' isso que este
    braco julga; o tempo continua a sair no detalhe dos outros bracos,
    REPORTADO e nao julgado.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, "AST de gaming_mode.py: %s" % exc
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == '_process_names'), None)
    if fn is None:
        return False, "def _process_names ausente de gaming_mode.py"
    calls = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.append(node.func.id)
    snapshots = [c for c in calls if c == 'CreateToolhelp32Snapshot']
    per_pid = [c for c in calls
               if c in ('OpenProcess', 'EnumProcesses',
                        'QueryFullProcessImageNameW', 'OpenThread')]
    ok = len(snapshots) == 1 and not per_pid
    return ok, ("CreateToolhelp32Snapshot=%d APIs-por-pid=%s"
                % (len(snapshots), ",".join(sorted(set(per_pid))) or "nenhuma"))


def run(shell_path, gesture_path, overlay_path, gaming_path):
    for path in (shell_path, gesture_path, overlay_path, gaming_path):
        if not path.exists():
            print("VERDICT: FAIL -- %s ausente" % path)
            return EXIT_FAIL
    print("BRACOS JULGADOS:")
    for line in ARM_LIST:
        print("  %s" % line)
    rows.clear()

    gesture = load_module('hotkey_gesture_probe', gesture_path)
    _GESTURE[0] = gesture
    gaming = load_module('gaming_mode_probe', gaming_path)
    source = shell_path.read_text(encoding='utf-8')
    overlay_source = overlay_path.read_text(encoding='utf-8')
    log = FakeLog()
    recorder = RecordingUser32()

    # -- ARM 0: o detector e' READ-ONLY (o dono pediu para DETECTAR) -----------
    print("\nARM 0 -- o detector NAO age: nenhuma API de input/suspensao no ficheiro")
    gaming_src = gaming_path.read_text(encoding='utf-8')
    gaming_api = user32_names(gaming_src)
    gaming_code = api_names(gaming_src)
    add(gaming_api == {'GetForegroundWindow', 'GetWindowThreadProcessId'},
        "gaming_mode.py so' le' a janela em primeiro plano",
        str(sorted(gaming_api)))
    add(not (gaming_code & set(KEY_EATING)),
        "gaming_mode.py nao tem nenhuma API que coma teclas (nenhum hook)",
        str(sorted(gaming_code & set(KEY_EATING))) or "0")
    add(not (gaming_code & {'SuspendThread', 'TerminateProcess', 'SetPriorityClass',
                            'SetThreadPriority'}),
        "gaming_mode.py nao mexe no agendamento nem mata nada",
        str(sorted(gaming_code & {'SuspendThread', 'TerminateProcess',
                                  'SetPriorityClass', 'SetThreadPriority'})) or "0")
    add(gaming.TICK_S == 2.0, "o tick e' de 2 s", str(gaming.TICK_S))
    add(gaming.GAME_DWELL_TICKS == 10,
        "o dwell de fabrica e' o do watcher (models.py:433 game_dwell_ticks=10)",
        str(gaming.GAME_DWELL_TICKS))
    add(gaming.TICK_BUDGET_MS > 0, "o orcamento do tick esta' declarado",
        "%s ms" % gaming.TICK_BUDGET_MS)
    add(not hasattr(gaming, 'apply') and not hasattr(gaming, 'suspend'),
        "o modulo nao expoe nenhuma accao (so' is_gaming())")

    # -- ARM (e): a regra do watcher ------------------------------------------
    print("\nARM (e) -- is_gaming(): jogo nomeado vs processo comum")
    det = gaming.GamingDetector(log=log, read_names=lambda: ['explorer.exe',
                                                             'eldenring.exe'],
                                read_foreground=lambda: 0,
                                read_foreground_name=lambda pid: '')
    det.tick()
    add(det.is_gaming() is True, "eldenring.exe -> is_gaming() True",
        det.snapshot()['game'])
    add(log.has('GAMING_MODE on=true game="eldenring.exe"'),
        "UMA linha de transicao publicada", [l for l in log.lines
                                             if l.startswith('GAMING_MODE')][-1:]
        if log.has('GAMING_MODE') else '')
    log2 = FakeLog()
    det_plain = gaming.GamingDetector(
        log=log2, read_names=lambda: ['explorer.exe', 'python.exe', 'chrome.exe'],
        read_foreground=lambda: 0, read_foreground_name=lambda pid: '')
    det_plain.tick()
    add(det_plain.is_gaming() is False,
        "explorer/python/chrome -> is_gaming() False", det_plain.snapshot()['why'])
    add(not log2.has('GAMING_MODE on=true'),
        "nenhuma transicao para gaming com processos comuns")
    # A FAMILIA DO CLIENTE: 3 ticks seguidos em primeiro plano (games.py).
    log3 = FakeLog()
    fg = {'name': 'leagueclient.exe'}
    det_c = gaming.GamingDetector(
        log=log3, read_names=lambda: ['explorer.exe', 'leagueclient.exe'],
        read_foreground=lambda: 777,
        read_foreground_name=lambda pid: fg['name'])
    det_c.tick()
    add(det_c.is_gaming() is False,
        "cliente do League com 1 tick de foco NAO e' partida (streak=3)", "1 tick")
    det_c.tick()
    det_c.tick()
    add(det_c.is_gaming() is True,
        "cliente do League com 3 ticks seguidos em foco E' partida",
        "streak=%d" % det_c._streak)
    # O SHIPPING DESCONHECIDO sem CPU medida nao e' jogo (a diferenca declarada).
    add(gaming.is_game_process_detailed('random-win64-shipping.exe')[0] is False,
        "*-Win64-Shipping.exe desconhecido sem CPU medida NAO e' jogo")
    add(gaming.is_game_process_detailed('random-win64-shipping.exe',
                                        cpu_pct_of_machine=5.0)[0] is True,
        "o mesmo Shipping com 5 %% da maquina E' jogo (regra do watcher)")
    # A MAQUINA DE VERDADE: o detector real nao INVENTA um jogo.
    # MEDIDO 2026-11-11: a arm exigia `is_gaming() is False` -- ou seja o dono
    # nao podia estar a jogar no momento em que a bateria corre. Com o `Deadlock`
    # aberto ela reprovou (`hits=[GameHit(name='deadlock.exe', in_match=True)]`),
    # um oraculo a julgar a secretaria do dono em vez do classificador. O que se
    # prova agora e' o que de facto se quer: TODO `hit` sai de um processo que a
    # enumeracao REAL leu (nada e' inventado) e o veredicto concorda com os hits.
    real = gaming.GamingDetector(log=FakeLog())
    real.tick()
    names_lc = {str(n).lower() for n in real.last_names}
    invented = [h for h in real.last_hits if str(h.name).lower() not in names_lc]
    add(not invented and (real.is_gaming() is bool(real.last_hits)),
        "o detector REAL nao inventa jogo: todo hit esta' na enumeracao",
        "names=%d hits=%s invented=%s" % (len(real.last_names), real.last_hits,
                                          invented))
    add(len(real.last_names) > 5, "a enumeracao real leu processos",
        "%d nomes" % len(real.last_names))

    # -- ARM (f): o dwell -----------------------------------------------------
    print("\nARM (f) -- o dwell do watcher: N ticks depois da ultima vista")
    log4 = FakeLog()
    present = {'on': True}
    seen = {'on': True}
    det_d = gaming.GamingDetector(
        log=log4, dwell_ticks=gaming.GAME_DWELL_TICKS,
        read_names=lambda: ['explorer.exe'] + (['eldenring.exe'] if present['on'] else []),
        read_foreground=lambda: 0, read_foreground_name=lambda pid: '')
    det_d.tick()                     # tick 1: a vista real
    present['on'] = False
    held = []
    for _ in range(gaming.GAME_DWELL_TICKS):
        held.append(det_d.tick())    # ticks 2..11
    after = det_d.tick()             # tick 12
    add(all(held), "a vista desaparece e is_gaming() fica True nos %d ticks seguintes"
        % gaming.GAME_DWELL_TICKS, str(held))
    add(after is False, "e cai exactamente no tick seguinte (nao fica preso para sempre)",
        "tick=%d why=%s" % (det_d.ticks, det_d.why()))
    add(log4.has('GAMING_MODE on=false'),
        "a saida tambem tem a sua linha", [l for l in log4.lines
                                           if 'on=false' in l][-1:])
    add(sum(1 for l in log4.lines if l.startswith('GAMING_MODE')) == 2,
        "duas linhas no total (uma por TRANSICAO, nao uma por tick)",
        str([l for l in log4.lines if l.startswith('GAMING_MODE')]))
    log5 = FakeLog()
    det_z = gaming.GamingDetector(log=log5, dwell_ticks=0,
                                  read_names=lambda: ['eldenring.exe'],
                                  read_foreground=lambda: 0,
                                  read_foreground_name=lambda pid: '')
    det_z.tick()
    present['on'] = False
    det_z._read_names = lambda: ['explorer.exe']
    det_z.tick()
    add(det_z.is_gaming() is False,
        "dwell=0 desliga a histerese (o numero e' configuravel, nao magico)")

    # -- ARM (g): o custo do tick ---------------------------------------------
    print("\nARM (g) -- o custo do tick do detector, medido contra o PISO da mesma corrida")
    # O QUE ESTAVA ERRADO (MEDIDO 2026-11-04): este braco julgava o PIOR de 5
    # amostras contra 50 ms de relogio de parede. Numa maquina a correr tres
    # lanes, o escalonador estica uma amostra e o braco fica VERMELHO sem uma
    # linha de regressao -- medido: 2 de 10 corridas com `worst=51.24 ms` e
    # `worst=56.72 ms`, e as mesmas corridas verdes minutos depois. Um portao
    # que fica vermelho por CARGA ensina a todos a repeti-lo.
    #
    # O RACIO tick/enumeracao NAO E' INVARIANTE (MEDIDO 2026-11-27, n_proc=586):
    # tick_min=20,71 ms, enum_min=13,52 ms, racio=1,53 -- 0,03 acima do tecto
    # 1,5 sem nenhuma regressao. A mesma casa mediu 0,77 com 669 processos
    # (tick 91,14 / enum 119,13) e 0,86/1,03/1,04 em tres corridas ao lado:
    # o minimo de 9 amostras apanha escalonamento, nao custo intrinseco.
    # O que o produto GARANTE e' mecanico e nao depende da maquina: UM snapshot
    # por enumeracao, nenhum handle por pid (`gaming_mode.py:52-56`). E' isso
    # que a arm abaixo julga, pelo AST do ficheiro; o tempo e' REPORTADO.
    counts = {'n': 0}
    _real_names = gaming._process_names

    def counted_names():
        counts['n'] += 1
        return _real_names()

    det_b = gaming.GamingDetector(log=FakeLog(), read_names=counted_names)

    def _pair():
        """(tick_min, enum_min) de UMA rodada: o piso e o tick lado a lado.

        O PISO TEM DE LEVAR TANTAS AMOSTRAS COMO O TICK (2026-11-05). Com 5
        enumeracoes contra 9 ticks, o minimo do tick era o minimo de mais
        amostras -- e no dia carregado o racio saiu 1,82 (tick_min=23,22 contra
        enum_min=12,75) sem regressao nenhuma: tres corridas ao lado deram 0,86,
        1,03 e 1,04. Uma rodada a mais e' barata (14 ms cada) e o que a arm
        julga e' o custo INTRINSECO, que por definicao e' o melhor par.
        """
        floor = []
        for _ in range(9):
            t0 = time.perf_counter()
            _real_names()
            floor.append((time.perf_counter() - t0) * 1000.0)
        counts['n'] = 0
        timings = []
        for _ in range(9):
            t0 = time.perf_counter()
            det_b.tick()
            timings.append((time.perf_counter() - t0) * 1000.0)
        return (min(timings), min(floor), statistics.median(timings),
                max(timings))

    tick_min, enum_ms, tick_med, worst = _pair()
    for _ in range(2):
        if tick_min <= enum_ms * 1.5 and tick_min < gaming.TICK_BUDGET_MS:
            break
        _t, _e, _m, _w = _pair()
        if _e > 0 and (_t / _e) < (tick_min / max(enum_ms, 0.001)):
            tick_min, enum_ms, tick_med, worst = _t, _e, _m, _w

    add(counts['n'] == 9, "uma enumeracao por tick (contada na costura)",
        "read_names=%d para 9 ticks" % counts['n'])
    ok_prim, prim_detail = process_names_primitive(gaming_src)
    add(ok_prim, "UM snapshot por enumeracao, nenhum handle por pid", prim_detail)
    print("  REPORTADO (nao julgado): tick_min=%.2f ms enum_min=%.2f ms racio=%.2f "
          "n_proc=%d -- carga da maquina, nao regressao"
          % (tick_min, enum_ms, tick_min / max(enum_ms, 0.001), len(det_b.last_names)))
    # O ORCAMENTO ABSOLUTO E' UMA AFIRMACAO SOBRE A MAQUINA, nao sobre o produto --
    # e nesta caixa ele foi medido do lado errado. MEDIDO 2026-11-08 na corrida
    # `steps=385`: `tick_min=91,14 ms` contra `budget=50,0 ms`, com
    # `enum_min=119,13 ms` para UMA enumeracao nua de 669 processos, racio **0,77**.
    # Ou seja: o tick custou MENOS do que a enumeracao que ele tem de fazer, e o
    # braco vermelho so' falava da carga. A forma load-invariant e' a DISJUNCAO:
    # cabe no orcamento (maquina quieta) OU nao se distingue de uma enumeracao nua
    # (o piso e' da plataforma). Uma regressao de verdade derruba as DUAS metades.
    add(tick_min < gaming.TICK_BUDGET_MS or tick_min <= enum_ms * 1.5,
        "o custo intrinseco cabe no orcamento OU e' o de UMA enumeracao nua",
        "tick_min=%.2f ms budget=%.1f ms enum_min=%.2f ms | median=%.2f worst=%.2f "
        "(a espera do escalonador, REPORTADA e nao julgada)"
        % (tick_min, gaming.TICK_BUDGET_MS, enum_ms, tick_med, worst))
    add(tick_min < gaming.TICK_S * 1000.0 / 10.0,
        "e gasta menos de um decimo de um tick (antes do orcamento)",
        "tick_min=%.2f ms de %.0f ms" % (tick_min, gaming.TICK_S * 1000.0))

    # -- o caminho do toggle, do ficheiro -------------------------------------
    print("\nARM (c)/(d) -- o toggle REAL nao rouba foco e nao come teclas")
    built = build_toggle(source, overlay_source, recorder, log)
    if built is None:
        add(False, "os quatro corpos do toggle foram extraidos do ficheiro")
        return verdict("GAMING-HOTKEY")
    shell, overlay = built
    add(True, "os quatro corpos do toggle foram extraidos do ficheiro",
        "_hotkey_resolve, _set_live_enabled, show_caption_window, overlay.show")
    recorder.reset()
    foreground_before = 'notepad.exe'
    shell._hotkey_resolve('live')
    calls_after_one = list(recorder.calls)
    recorder.reset()
    shell._hotkey_resolve('live')
    calls_after_two = list(recorder.calls)
    names1 = [n for n, _ in calls_after_one]
    names2 = [n for n, _ in calls_after_two]
    add(shell.live_calls == [True, False],
        "duas pressoes -> on, off (a decisao real)", str(shell.live_calls))
    add(overlay.shown == [True, False],
        "a janela do overlay foi mostrada e escondida, por essa ordem",
        str(overlay.shown))
    # A JANELA NAO APARECE POR ACIDENTE (medido 2026-11-15): o `show` real de
    # 2026-11-14 le' `self.z_below` e escreve a falha em `self.log`, e
    # `show_caption_window` le' `self.CAPTION_REPLAY_MAX_S` -- tres nomes que o
    # `__init__` do ficheiro poe e o duplo nao tinha. O sintoma nao era um braco
    # vermelho gritante: era `CAPTION_WINDOW_SHOW_FAILED AttributeError` DENTRO do
    # `except` do produto, a arm a ler `shown=[]` e o log a dizer `LIVE_ENABLED_FAILED`.
    # Um arnes que engole a excepcao do produto transforma uma falha de FIACAO num
    # braco mudo, por isso a prova e' negativa: nenhuma linha de falha no log.
    _fail_lines = [line for line in log.lines
                   if 'CAPTION_WINDOW_SHOW_FAILED' in line
                   or 'LIVE_ENABLED_FAILED' in line]
    add(not _fail_lines,
        "o caminho do toggle correu sem excepcao engolida (nenhuma linha de FALHA)",
        str(_fail_lines[:2]) or '0 linhas de falha')
    add(not (set(names1) | set(names2)) & set(FOCUS_TAKING),
        "NENHUMA API de primeiro plano foi chamada",
        str(sorted((set(names1) | set(names2)) & set(FOCUS_TAKING))) or "0 chamadas")
    show_args = [args[1] for args in recorder.of('ShowWindow')
                 if len(args) > 1]
    add(all(int(cmd) in (SW_HIDE, SW_SHOWNOACTIVATE) for cmd in show_args),
        "ShowWindow so' com SW_HIDE/SW_SHOWNOACTIVATE (nunca SW_SHOW/SW_RESTORE)",
        str(show_args))
    pos_args = recorder.of('SetWindowPos')
    add(all(int(args[-1]) & SWP_NOACTIVATE for args in pos_args if len(args) == 7),
        "todo SetWindowPos leva SWP_NOACTIVATE", "n=%d" % len(pos_args))
    eaten = sorted((set(names1) | set(names2)) & set(KEY_EATING))
    add(not eaten, "NENHUMA API que come teclas foi chamada",
        str(eaten) or "0 chamadas")
    add(foreground_before == 'notepad.exe',
        "o primeiro plano do cenario nao mudou (nada aqui pode move-lo)")

    # -- o observador: a unica leitura e' GetAsyncKeyState ---------------------
    obs_bodies = class_methods(source, 'PassiveHotkeyThread', ('run',))
    add(bool(obs_bodies), "o corpo do observador foi extraido do ficheiro")
    obs_user = user32_names(obs_bodies.get('run', ''))
    add(obs_user == {'GetAsyncKeyState'},
        "o observador so' LE' o teclado (GetAsyncKeyState), e nada mais de user32",
        str(sorted(obs_user)))
    add(not (obs_user & set(KEY_EATING)),
        "o observador nao tem nenhuma API que coma teclas",
        str(sorted(obs_user & set(KEY_EATING))) or "0")
    add(not names_used(obs_bodies.get('run', ''), 'GetForegroundWindow'),
        "a pressao NAO depende da janela em primeiro plano (jogo fullscreen incluido)")
    resolve_body = class_methods(source, 'SottoShell', ('_hotkey_resolve',)).get(
        '_hotkey_resolve', '')
    add(not names_used(resolve_body, 'GetForegroundWindow')
        and not names_used(resolve_body, 'is_gaming'),
        "a decisao do toggle nao pergunta quem esta' em primeiro plano nem o modo jogo")

    # -- ARM (a)/(b): a pressao DENTRO do modo jogo ---------------------------
    print("\nARM (a)/(b) -- pressao em GAMING: vista, e liga/desliga")
    windows = FakeWindows()
    cls = build_observer(source, gesture, log, windows)
    if cls is None:
        add(False, "a classe do observador foi construida do ficheiro")
        return verdict("GAMING-HOTKEY")
    add(True, "a classe do observador foi construida do ficheiro")
    # O shell do toggle ja' comutou duas vezes no braco (c)/(d); as contagens
    # deste braco comecam do zero -- senao o vermelho seria do irmao, nao daqui.
    shell.live_calls.clear()
    overlay.shown.clear()
    game_state = gaming.GamingDetector(
        log=FakeLog(), read_names=lambda: ['eldenring.exe'],
        read_foreground=lambda: 0, read_foreground_name=lambda pid: '')
    game_state.tick()
    add(game_state.is_gaming() is True, "o cenario esta' em GAMING (pre-condicao)")
    log.lines.clear()
    press_records = []

    def on_press():
        press_records.append(game_state.is_gaming())
        shell._hotkey_resolve('live')

    observer = cls('Ctrl+Space', on_press, log_fn=log, role='live',
                   poll_s=0.005, key_state=windows.state)
    observer.start()
    observer.wait_ready(2.0)
    time.sleep(0.05)
    windows.press(0x11)                    # Ctrl em baixo
    windows.press(0x20, hold_s=0.05)       # Space
    time.sleep(0.10)
    windows.release(0x20)
    windows.release(0x11)
    time.sleep(0.10)
    windows.press(0x11)
    windows.press(0x20, hold_s=0.05)
    time.sleep(0.10)
    windows.release(0x20)
    windows.release(0x11)
    time.sleep(0.10)
    observer.stop()
    observer.join(2.0)
    add(len(log.presses()) == 2,
        "duas pressoes em GAMING -> DUAS linhas HOTKEY_PRESSED role=live",
        str(log.presses()))
    add(shell.live_calls == [True, False],
        "e o interruptor alterna ON e OFF", str(shell.live_calls))
    add(press_records == [True, True],
        "as duas pressoes foram entregues COM o detector em GAMING", str(press_records))

    # -- ARM (h): a volta perdida ---------------------------------------------
    print("\nARM (h) -- a volta perdida: a pressao INTEIRA dentro de uma leitura presa")
    windows2 = FakeWindows()
    log6 = FakeLog()
    presses6 = []
    cls2 = build_observer(source, gesture, log6, windows2)
    obs2 = cls2('Ctrl+Space', lambda: presses6.append(time.monotonic()),
                log_fn=log6, role='live', poll_s=0.025, key_state=windows2.state)
    obs2.start()
    obs2.wait_ready(2.0)
    time.sleep(0.06)
    # O DETERMINISMO E' UM HANDSHAKE, NAO UM `sleep` (MEDIDO 2026-11-04). A versao
    # anterior punha um fio `hog` a comer o GIL e dois `sleep` de 30/150 ms: uma
    # LOTERIA. Um fio Python larga o GIL de 5 em 5 ms, por isso o `hog` so' as
    # vezes apanhava a pressao la' dentro, e a maquina carregada mudava a ordem.
    # Aqui: fecha-se a LEITURA, espera-se que o observador esteja PRESO dentro
    # dela (o evento `gate_entered`), poem-se a pressao com as teclas JA'
    # soltas -- so' o bit 0 -- e abre-se. A ordem deixa de ser corrida.
    windows2.gate = threading.Event()
    windows2.gate_entered = threading.Event()
    windows2.gate.clear()          # FECHADO: a proxima leitura fica presa
    entered6 = windows2.gate_entered.wait(2.0)
    windows2.press(0x11)
    windows2.press(0x20)
    windows2.gate.set()            # ABERTO: o observador le' a borda guardada
    wait_until(lambda: bool(presses6), 2.0)
    loops_at_gate = obs2.loops
    wait_until(lambda: obs2.loops > loops_at_gate, 2.0)
    obs2.stop()
    obs2.join(2.0)
    beats = [l for l in log6.lines if 'HOTKEY_OBSERVER_ALIVE' in l]
    gap = int(round(float(getattr(obs2, '_wake_gap', 0.0)) * 1000.0))
    for line in beats:
        match = re.search(r'max_gap_ms=(\d+)', line)
        if match:
            gap = max(gap, int(match.group(1)))
    add(entered6, "o observador estava PRESO na leitura quando a tecla foi carregada",
        "gate_entered=%s" % entered6)
    add(len(presses6) == 1,
        "a pressao que caiu inteira na volta perdida FOI vista (uma, e so' uma)",
        "presses=%d" % len(presses6))
    add(obs2.loops > loops_at_gate, "e o observador voltou a girar depois da volta presa",
        "loops=%d depois=%d max_gap_ms=%d" % (loops_at_gate, obs2.loops, gap))
    add(any('via=latched' in line for line in log6.presses()),
        "a entrega veio do BIT 0 (via=latched) -- as teclas ja' estavam soltas",
        str(log6.presses()))
    add(log6.has('HOTKEY_PRESSED role=live count=1'),
        "a linha da pressao tem o count=1 (a entrega e' a do ficheiro)")

    # -- ARM (h2): o GIL TOMADO, o caso MEDIDO (`max_gap_ms=29266`) -----------
    print("\nARM (h2) -- o GIL tomado por uma chamada C (o caso medido: UIA 29 s)")
    windows3 = FakeWindows()
    log7 = FakeLog()
    presses7 = []
    cls3 = build_observer(source, gesture, log7, windows3)
    obs3 = cls3('Ctrl+Space', lambda: presses7.append(True), log_fn=log7,
                role='live', poll_s=0.025, key_state=windows3.state)
    obs3.start()
    obs3.wait_ready(2.0)
    time.sleep(0.06)
    # A PRESSAO E' POSTA ENQUANTO A LEITURA ESTA' PRESA, e o `hold_the_gil` a
    # seguir torna a volta REALMENTE longa (o `max_gap_ms` que o log do dono
    # publicou). A versao anterior agendava a pressao em `t_now + 0.10 s` e
    # entrava no GIL a seguir: se o fio principal fosse despejado por 100 ms
    # antes de chegar ao GIL, a tecla era lida ao vivo (`via=state`) e o braco
    # ficava vermelho por CARGA. Agora a ordem e' imposta, nao corrida.
    windows3.gate = threading.Event()
    windows3.gate_entered = threading.Event()
    windows3.gate.clear()          # FECHADO: a leitura fica presa durante o GIL
    entered7 = windows3.gate_entered.wait(2.0)
    windows3.press(0x11)
    windows3.press(0x20)

    # O TAMANHO DO RETROCESSO E' CALIBRADO, NAO ESCOLHIDO A OLHO (medido 2026-11-12).
    # `(a+)+$` explode como 2^n: nesta maquina, UMA chamada custa 2,3 ms com 16 `a`,
    # 35,7 ms com 20, **480,6 ms com 23** e **3 773,5 ms com 26**. A versao anterior
    # usava 26 e um prazo de 0,45 s, logo cada chamada isolada segurava o GIL por
    # ~3,8 s -- oito vezes o prazo -- e o `while` so' podia sair depois dela: 5
    # mutantes x 3,8 s = ~19 s de pura espera dentro dos 53,1 s deste passo. Com 20
    # `a` uma chamada custa **36-46 ms** (duas series medidas), 10-13x abaixo do
    # prazo de 0,45 s, entao o excesso fica limitado a UMA chamada curta: o braco
    # mede o MESMO fenomeno (GIL tomado por codigo C que nao larga) sem pagar 3,8 s
    # por tentativa. Medido depois: passo de 53,1 s -> 34,8 s, 5/5 mutantes.
    HOLD_BACKTRACK_A = 20          # 36-46 ms por chamada, medido
    def hold_the_gil(seconds):
        """Uma chamada C que NAO larga o GIL -- o que a UIA fazia (medido 29 s).

        `sre` corre em C sem largar o GIL, e esta expressao tem retrocesso
        catastrofico. E' uma pausa MEDIDA, nao um `sleep` (um `sleep` larga o GIL
        e nao reproduz nada). O tamanho fica em `HOLD_BACKTRACK_A` para que o
        EXCESSO do prazo seja uma chamada curta e nao uma de 3,8 s.
        """
        pattern = re.compile(r'(a+)+$')
        probe = 'a' * HOLD_BACKTRACK_A + 'b'
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            pattern.match(probe)

    # O DONO NAO ESPERA ATRAS DE UM TESTE (medido 2026-11-26, DM do watcher).
    # O watcher apanhou `python.exe(72760)` = este oraculo (`--neg-arm`) como a
    # maior pressao do episodio, com sinais `tick-gap, not-scheduled`: o
    # governador estava a ser escalonado atras dele. O `hold_the_gil` abaixo e'
    # um ciclo em C que NAO larga o GIL por 0,45 s -- de proposito, e' o
    # fenomeno que o braco reproduz. A PRIORIDADE nao muda esse braco (o GIL e'
    # interno ao processo: a thread observadora continua travada), logo baixar a
    # classe do PROCESSO aqui e' a cura certa -- o dono deixa de esperar e o arm
    # mede o mesmo `max_gap_ms`.
    print('ARM (h) prioridade do processo: %s' % _lower_me())
    hold_the_gil(0.45)
    windows3.gate.set()
    wait_until(lambda: bool(presses7), 2.0)
    # A VOLTA SO' E' MEDIDA NO INICIO DA SEGUINTE: parar o observador no instante
    # em que a pressao entra deixaria `max_gap_ms` a zero e o braco media um
    # numero que nunca foi calculado (medido: gap=0 com o press entregue).
    loops3 = obs3.loops
    wait_until(lambda: obs3.loops > loops3, 2.0)
    obs3.stop()
    obs3.join(2.0)
    gap3 = int(round(float(getattr(obs3, '_wake_gap', 0.0)) * 1000.0))
    for line in log7.lines:
        match = re.search(r'max_gap_ms=(\d+)', line)
        if match:
            gap3 = max(gap3, int(match.group(1)))
    add(entered7, "a leitura estava presa quando o GIL foi tomado",
        "gate_entered=%s" % entered7)
    add(len(presses7) == 1,
        "a pressao que caiu DENTRO do GIL tomado foi vista (uma, e so' uma)",
        "presses=%d" % len(presses7))
    add(gap3 >= 400, "a volta ficou presa como no log do dono",
        "max_gap_ms=%d (o log dele mediu 203..29266)" % gap3)
    add(any('via=latched' in line for line in log7.presses()),
        "a entrega veio do BIT 0 (via=latched) -- a borda que o Windows guardou",
        str(log7.presses()))

    # -- ARM (i): a prioridade PEDIDA e' a APLICADA (medida no Windows) -------
    print("\nARM (i) -- a prioridade do observador: pedida e LIDA DE VOLTA")
    result = {}

    def _probe_priority():
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.GetCurrentThread.restype = ctypes.c_void_p
        k.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
        k.GetThreadPriority.argtypes = [ctypes.c_void_p]
        k.GetThreadPriority.restype = ctypes.c_int
        before = int(k.GetThreadPriority(k.GetCurrentThread()))
        ok = bool(k.SetThreadPriority(k.GetCurrentThread(),
                                      int(gesture.OBSERVER_PRIORITY)))
        after = int(k.GetThreadPriority(k.GetCurrentThread()))
        result.update(before=before, ok=ok, after=after)

    probe = threading.Thread(target=_probe_priority, daemon=True)
    probe.start()
    probe.join(5.0)
    add(bool(result.get('ok')) is True,
        "SetThreadPriority aceita o numero do hotkey_gesture",
        "ok=%s" % result.get('ok'))
    add(int(result.get('after', 0)) == int(gesture.OBSERVER_PRIORITY),
        "e o Windows LE' DE VOLTA a prioridade pedida (efeito, nao intencao)",
        "before=%s after=%s" % (result.get('before'), result.get('after')))
    add(int(gesture.OBSERVER_PRIORITY) == 1,
        "o valor e' ABOVE_NORMAL (1), nao TIME_CRITICAL (15)",
        str(gesture.OBSERVER_PRIORITY))

    return verdict("GAMING-HOTKEY")


def verdict(name):
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print("FALHA: %s%s" % (label, ("  -- " + detail) if detail else ""))
    print("\n%s %s -- arms=%d pass=%d fail=%d (rc=%d)"
          % (name, 'GREEN' if not failed else 'VERMELHO', total, passed, failed,
             EXIT_PASS if not failed else EXIT_FAIL))
    return EXIT_PASS if not failed else EXIT_FAIL


# ---------------------------------------------------------------------------
# --neg-arm: muta uma COPIA, quatro vezes, e cada mutante tem de dar RED
# ---------------------------------------------------------------------------
#: MUTANTE 1 -- o toggle ROUBA o primeiro plano: `SW_SHOWNOACTIVATE` vira
#: `SW_SHOW` e entra um `SetForegroundWindow` na janela da legenda.
OVERLAY_STEAL_PATCH = (
    "                _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)",
    "                _user32.SetForegroundWindow(self.hwnd)\n"
    "                _user32.ShowWindow(self.hwnd, 5)",
)

#: MUTANTE 2 -- o DWELL apagado: a vista vale um tick so'.
GAMING_DWELL_PATCH = (
    "        gaming = bool(raw or (\n"
    "            self.dwell_ticks > 0 and self._seen_tick is not None\n"
    "            and (self.ticks - self._seen_tick) <= self.dwell_ticks))",
    "        gaming = bool(raw)",
)

#: MUTANTE 3 -- o `in_match` ignorado: a regra do watcher perde a metade
#: "um nome conhecido E' uma partida".
GAMING_INMATCH_PATCH = (
    "    if is_game_name(name, extra_names):\n        return True, True",
    "    if is_game_name(name, extra_names):\n        return True, False",
)

#: MUTANTE 5 -- o TICK BLOQUEIA: uma chamada de 200 ms entra no laco do detector
#: (o defeito que o braco do ORCAMENTO existe para apanhar -- um travamento por
#: tick, nao uma contagem). MEDIDO sem ele: o braco do orcamento nao tinha nenhum
#: controlo, e um braco sem controlo e' um verde que nao mede.
GAMING_TICK_BLOCKS_PATCH = (
    "        names = list(self._read_names())",
    "        _block = __import__('time').sleep(0.2)\n"
    "        names = list(self._read_names())",
)

#: MUTANTE 4 -- o observador AFAMADO: a volta passa a 1 s e o bit 0 (a borda) e'
#: deixado de fora, que e' o observador de antes de 2026-11-04 com o laco preso.
SHELL_STARVE_PATCHES = (
    ("            if mods_ready and (fresh or (down and not held)):",
     "            if mods_ready and down and not held:"),
    ("            self._stop_requested.wait(self.poll_s)",
     "            self._stop_requested.wait(max(1.0, self.poll_s))"),
)


def _copy_tree(tmp):
    webview = tmp / "app" / "webview"
    webview.mkdir(parents=True)
    for name in ("sotto_webview.py", "hotkey_gesture.py", "hotkey_settings.py",
                 "caption_overlay.py", "gaming_mode.py", "win32_types.py",
                 "capture_exclusion.py"):
        src = WEBVIEW / name
        if src.exists():
            shutil.copy2(src, webview / name)
    return webview


#: MUTANTE 6 -- a excepcao ENGOLIDA pelo `except` do produto (a classe medida em
#: 2026-11-15): um nome que o `show_caption_window` le' e nao existe produz
#: `CAPTION_WINDOW_SHOW_FAILED`/`LIVE_ENABLED_FAILED` e `shown=[]`, e a arm que
#: julga isso e' a que impede o arnes de voltar a medir-se a si proprio.
SHOW_ATTR_MISSING_PATCH = (
    "            if on:\n"
    "                self._caption_window_shown = True",
    "            if on:\n"
    "                self._caption_window_shown = self._NAME_THAT_DOES_NOT_EXIST",
)


def _patch_file(path, patch, note):
    text = path.read_text(encoding='utf-8')
    if patch[0] not in text:
        return None
    path.write_text(text.replace(patch[0], patch[1], 1), encoding='utf-8')
    return note


def _mutate_overlay_steal(webview):
    return _patch_file(webview / "caption_overlay.py", OVERLAY_STEAL_PATCH,
                       "o toggle rouba o primeiro plano (SetForegroundWindow + SW_SHOW)")


def _mutate_gaming_dwell(webview):
    return _patch_file(webview / "gaming_mode.py", GAMING_DWELL_PATCH,
                       "o dwell apagado (a vista vale um tick)")


def _mutate_gaming_tick_blocks(webview):
    return _patch_file(webview / "gaming_mode.py", GAMING_TICK_BLOCKS_PATCH,
                       "o tick bloqueia 200 ms por volta (o orcamento estourado)")


def _mutate_gaming_inmatch(webview):
    return _patch_file(webview / "gaming_mode.py", GAMING_INMATCH_PATCH,
                       "o in_match ignorado (um jogo nomeado deixa de ser partida)")


def _mutate_show_attr_missing(webview):
    return _patch_file(webview / "sotto_webview.py", SHOW_ATTR_MISSING_PATCH,
                       "o show le' um atributo que nao existe (a excepcao engolida)")


def _mutate_shell_starve(webview):
    path = webview / "sotto_webview.py"
    text = path.read_text(encoding='utf-8')
    for old, new in SHELL_STARVE_PATCHES:
        if old not in text:
            return None
        text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')
    return "o observador faminto: volta de 1 s e sem a borda do bit 0"


MUTANTS = (("foreground-stolen-on-toggle", _mutate_overlay_steal),
           ("dwell-removed", _mutate_gaming_dwell),
           ("in-match-ignored", _mutate_gaming_inmatch),
           ("observer-poll-starved", _mutate_shell_starve),
           ("tick-blocks-200ms", _mutate_gaming_tick_blocks),
           ("show-exception-swallowed", _mutate_show_attr_missing))

_NEG_MUTANTS = len(MUTANTS)


def _lower_me(class_hex=0x00004000):
    """Poe ESTE processo em BELOW_NORMAL -- e LE' DE VOLTA o valor aplicado.

    Um teste que queima CPU de proposito (um ciclo em C que nao larga o GIL) nao
    tem o direito de competir com o dono. MEDIDO 2026-11-26: o watcher nomeou
    este oraculo como a maior pressao de um episodio de stutter, com o governador
    a apanhar `tick-gap` a escalona-lo. A classe de prioridade nao toca no braco
    (o GIL e' interno), mas tira este processo da frente do dono.
    Devolve a classe LIDA DE VOLTA (`GetPriorityClass`), nunca o pedido.
    """
    try:
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        k32.GetPriorityClass.restype = ctypes.c_uint32
        handle = k32.GetCurrentProcess()
        k32.SetPriorityClass(handle, class_hex)
        return int(k32.GetPriorityClass(handle))
    except Exception:  # noqa: BLE001 -- a prioridade nunca derruba um braco
        return 0


def neg_arm():
    """Muta uma COPIA, uma vez por mutante. Cada um tem de derrubar O SEU braco.

    A prova e' o rc: um mutante que o oraculo NAO ve' e' um oraculo que nao mede
    aquele comportamento. rc=1 (a casa conta o vermelho como sucesso) e
    `NEG-ARM` na ultima linha quando todos sao apanhados.

    A CONTAGEM E' DERIVADA DA TABELA (medido 2026-11-15): o texto dizia "as cinco
    regressoes" com SEIS registadas -- o mesmo defeito de prosa que ja' custou
    pins desatualizados nesta casa. Uma frase que conta mutantes a mao mente no
    dia em que se acrescenta o seguinte.
    """
    failures = 0
    for name, mutate in MUTANTS:
        tmp = Path(tempfile.mkdtemp(prefix="gaming-neg-"))
        try:
            webview = _copy_tree(tmp)
            note = mutate(webview)
            if note is None:
                print("NEG-ARM: nao consegui mutar %s (o texto mudou)" % name)
                failures += 1
                continue
            print("\n=== NEG-ARM %s: %s" % (name, note))
            rc = run(webview / "sotto_webview.py", webview / "hotkey_gesture.py",
                     webview / "caption_overlay.py", webview / "gaming_mode.py")
            if rc == EXIT_FAIL:
                print("NEG-ARM %s PASS -- RED as designed" % name)
            else:
                print("NEG-ARM %s FAIL -- o oraculo NAO ve a regressao" % name)
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print("\nNEG-ARM FAIL -- o oraculo nao ve a regressao")
        return EXIT_PASS
    print("\nNEG-ARM PASS -- RED as designed: as %d regressoes derrubam o oraculo"
          % _NEG_MUTANTS)
    return EXIT_FAIL


def main(argv):
    if "--neg-arm" in argv:
        return neg_arm()
    return run(SHELL, GESTURE, OVERLAY, GAMING)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
