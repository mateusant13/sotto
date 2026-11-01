#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-11-01 -- as duas hotkeys do Sotto
# (Alt+C = um passo do ciclo dos paineis, Ctrl+Space = a legenda ao vivo) medidas
# no codigo que corre. Nao corrige defeito nenhum: impede que o contrato volte a
# ser contado por janelas de toques ou por duracao de segurada.
"""ORACLE: AS DUAS HOTKEYS -- Alt+C alterna os paineis, Ctrl+Space a legenda.

ORDEM DO DONO, verbatim (2026-11-01):

    *"modifica a legenda ao vivo hotkey. bota o padrao como control espaco. e os
    painels deixa alt c. faz os paineis alternarem mesmo se eu deixar alt
    apertado o tempo inteiro e spammando c. alterna entre show e hide."*

O CONTRATO ANTERIOR (2026-10-30) decidia por TEMPO: 1 toque contra 2 toques
dentro de 400 ms, e uma segurada >= 200 ms como legenda ao vivo. Media a duracao
com `GetAsyncKeyState` em cada volta de um pump de 10 ms. Com o Alt fisicamente
em baixo e o C martelado, as duas coisas partiam o gesto ao meio -- e nao ha
nada disso que ele tenha pedido.

OS BRACOS (a lista e' impressa no arranque, e cada um diz o que julga):

  (a) 10 pressoes de Alt+C -> EXACTAMENTE 10 mudancas de visibilidade, com os
      shows a alternar strip,panel,strip,panel,strip;
  (b) duas pressoes separadas por 10 s de relogio -> DUAS mudancas;
  (c) uma pressao com 300 ms de relogio -> UMA mudanca, e NENHUM toggle de legenda;
  (d) Ctrl+Space -> a legenda comuta uma vez por pressao, e nao toca em painel;
  (e) o braco VERMELHO: reinstalar o adiamento de 400 ms (ou o limiar de HOLD)
      tem de derrubar o oraculo -- corrido, com o resultado mostrado.

COMO. Os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e
`_on_press` sao EXTRAIDOS DO FICHEIRO QUE VAI CORRER com `ast` e exec'd contra um
shell falso, um relogio-ESPIAO (qualquer leitura de tempo reprova o braco) e um
`threading`-espiao (um Timer significa adiamento). Nenhuma janela e' aberta,
nenhum ctypes e' tocado, nada e' posto no ecra do dono.

Uso:
    python _main/altc-gesture-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/altc-gesture-oracle.py --neg-arm  -> muta uma COPIA e exige RED
    SOTTO_ROOT=<arvore> ...                       -> julga outra arvore
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import json
import os
import re
import shutil
import tempfile
import textwrap
import time as real_time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SOTTO_ROOT") or HERE.parent).resolve()
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
GESTURE = ROOT / "app" / "webview" / "hotkey_gesture.py"
SETTINGS = ROOT / "app" / "webview" / "hotkey_settings.py"
LIVE_FILE = ROOT / "_main" / "hotkey-settings.json"
EXIT_PASS, EXIT_FAIL = 0, 1

rows: list[tuple[bool, str, str]] = []

ARM_LIST = (
    "(a) 10 pressoes de Alt+C -> 10 mudancas, shows strip,panel,strip,panel,strip",
    "(b) duas pressoes a 10 s -> duas mudancas",
    "(c) uma pressao com 300 ms -> uma mudanca (e nenhuma legenda)",
    "(d) Ctrl+Space comuta a legenda uma vez por pressao",
    "(e) --neg-arm: adiamento de 400 ms / limiar de HOLD reinstalados -> RED",
)


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


def load_module(name: str, path: Path):
    spec = _ilu.spec_from_file_location(name, str(path))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Extracao do proprio ficheiro (o que corre, e nao a minha transcricao)
# ---------------------------------------------------------------------------
def class_methods(source: str, cls_name: str, names) -> dict:
    """`{nome: fonte}` dos metodos pedidos, lidos do ficheiro com `ast`."""
    tree = ast.parse(source)
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    if cls is None:
        return {}
    out = {}
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            out[node.name] = ast.get_source_segment(source, node) or ""
    return out


def class_names(source: str, cls_name: str) -> set:
    tree = ast.parse(source)
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    return {n.name for n in (cls.body if cls else []) if isinstance(n, ast.FunctionDef)}


def code_only(source: str, cls_name: str, name: str) -> str:
    """O corpo de um metodo SEM a docstring -- o que ele FAZ, nao o que diz."""
    tree = ast.parse(source)
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    for node in (cls.body if cls else []):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:] or [ast.Pass()]
            clone = ast.FunctionDef(name=name, args=node.args, body=body,
                                    decorator_list=[], returns=None,
                                    type_params=[], lineno=1, col_offset=0)
            return ast.unparse(ast.fix_missing_locations(clone))
    return ""


def def_body(source: str, name: str) -> str:
    """O corpo imediato de uma funcao de modulo (sem docstring)."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:] or [ast.Pass()]
            return "\n".join(ast.unparse(n) for n in body)
    return ""


# ---------------------------------------------------------------------------
# Espioes: tempo lido e trabalho adiado sao REPROVADOS, nao apenas comentados
# ---------------------------------------------------------------------------
class SpyTime:
    """Qualquer leitura de relogio fica registada -- o gesto nao pode ler tempo."""

    def __init__(self):
        self.now = 1000.0
        self.reads: list[str] = []

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        self.reads.append(name)
        if name == 'monotonic':
            return lambda: self.now
        if name == 'perf_counter':
            return lambda: self.now
        return lambda *a, **k: None


class SpyThreading:
    """Um `Timer` aqui e' um ADIAMENTO, e o braco (a) tem de o ver."""

    class Event:
        def __init__(self):
            self.flag = False

        def set(self):
            self.flag = True

        def is_set(self):
            return self.flag

        def wait(self, timeout=None):
            return self.flag

    def __init__(self):
        self.timers: list = []
        self.threads: list = []

    def Timer(self, delay, fn):  # noqa: N802 -- nome do stdlib, de proposito
        self.timers.append((float(delay), fn))
        return type('T', (), {'daemon': False, 'start': lambda s: None,
                              'cancel': lambda s: None})()

    def Thread(self, target=None, **kwargs):  # noqa: N802
        self.threads.append(target)
        return type('T', (), {'daemon': False,
                              'start': lambda s: target and target(),
                              'is_alive': lambda s: False})()


class FakeLog:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, message, *a, **k):
        self.lines.append(str(message))

    def has(self, needle):
        return any(needle in line for line in self.lines)


#: O que `window_visible` devolve. O shell falso escreve aqui, e a funcao do
#: namespace le' daqui -- e' o mesmo caminho do shell real (medir a janela).
SCREEN = {'visible': False}


def build_shell(source: str, gesture):
    """Os metodos do shell, exec'd contra um `self` falso."""
    wanted = ("hotkey_pressed", "hotkey_live", "_hotkey_resolve")
    bodies = class_methods(source, "SottoShell", wanted)
    if len(bodies) != len(wanted):
        return None
    spies = {'time': SpyTime(), 'threading': SpyThreading(), 'log': FakeLog()}
    namespace = {
        "time": spies['time'],
        "threading": spies['threading'],
        "log": spies['log'],
        "hotkey_numbers": lambda: gesture,
        "window_visible": lambda hwnd: bool(SCREEN['visible']),
        "_spies": spies,
    }
    module = ast.Module(body=[ast.parse(bodies[name]).body[0] for name in wanted],
                        type_ignores=[])
    exec(compile(module, "<sotto-shell-hotkey>", "exec"), namespace)
    return namespace


class FakeShell:
    """So' o que os tres metodos tocam. Nenhuma chamada Win32.

    `hide_panel` NAO limpa `surface_applied`, de proposito: o ciclo de
    `hotkey_gesture.next_surface` depende dessa memoria para alternar o show
    seguinte, e o shell real tambem nao a limpa (braco estrutural separado).
    """

    def __init__(self, ns, visible=False, surface='panel', caption=False):
        self.hwnd = 4242
        self.visible = bool(visible)
        self.surface_applied = surface
        self._caption_wanted = bool(caption)
        self.events: list[tuple] = []
        self.live_calls: list[bool] = []
        SCREEN['visible'] = bool(visible)
        # O DESPACHO. Em producao `hotkey_pressed` poem o passo numa FILA e um
        # worker executa; a fila e' stdlib e nao tem regra nenhuma dentro (o braco
        # estrutural prova que ele so' poem), por isso aqui liga-se DIRECTO -- o
        # que se mede e' a decisao e o INSTANTE dela.
        self._hotkey_dispatch = lambda kind: ns['_hotkey_resolve'](self, kind)

    def _shown(self, surface):
        self.visible = True
        self.surface_applied = surface
        SCREEN['visible'] = True
        self.events.append(('show', surface))

    def show_strip(self, reason):
        self._shown('strip')
        return 'strip'

    def show_side(self, reason):
        self._shown('panel')
        return 'panel'

    def hide_panel(self, reason):
        self.visible = False
        SCREEN['visible'] = False
        self.events.append(('hide', self.surface_applied))
        return True

    def _set_live_enabled(self, payload):
        on = bool(payload.get('on'))
        self.live_calls.append(on)
        self._caption_wanted = on
        return 'enabled'


def visibility_changes(events):
    return len(events)


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


def run(gesture_path: Path, shell_path: Path, settings_path: Path,
        live_file: Path) -> int:
    for path in (gesture_path, shell_path, settings_path):
        if not path.exists():
            print(f"VERDICT: FAIL -- {path} ausente")
            return EXIT_FAIL
    print("BRACOS JULGADOS:")
    for line in ARM_LIST:
        print(f"  {line}")
    # CADA CORRIDA COMEÇA COM A LISTA VAZIA. Sem isto o `--neg-arm` somava as
    # linhas do primeiro mutante ao veredicto do segundo, e o segundo aparecia
    # vermelho por culpa do irmao -- evidencia falsa nos dois sentidos.
    rows.clear()

    gesture = load_module("hotkey_gesture_probe", gesture_path)
    if str(gesture_path.parent) not in os.sys.path:
        os.sys.path.insert(0, str(gesture_path.parent))
    settings = load_module("hotkey_settings_probe", settings_path)
    source = shell_path.read_text(encoding="utf-8")
    shell_methods = class_names(source, "SottoShell")
    thread_methods = class_names(source, "HotkeyThread")

    # -- ARM 1 -----------------------------------------------------------------
    print("\nARM 1 -- o contrato APOSENTADO saiu do codigo (nao so' do comentario)")
    add({"hotkey_pressed", "hotkey_live", "_hotkey_resolve"} <= shell_methods,
        "o shell tem hotkey_pressed, hotkey_live e _hotkey_resolve",
        str(sorted(n for n in ("hotkey_pressed", "hotkey_live", "_hotkey_resolve")
                   if n in shell_methods)))
    for dead in ("hotkey_hold", "_hotkey_forget", "_get_hotkey_hold",
                 "_set_hotkey_hold"):
        add(dead not in shell_methods, f"o shell JA' NAO tem {dead}")
    for dead in ("_tick", "_finish_measure", "_deliver_hold", "_threshold",
                 "_alt_is_down"):
        add(dead not in thread_methods, f"o HotkeyThread JA' NAO tem {dead}")
    add("_on_press" in thread_methods and "stop" in thread_methods,
        "o HotkeyThread ainda tem _on_press e stop")
    for gone in ("HOTKEY_HOLD_MS", "HOTKEY_TAP_WINDOW_MS", "HOLD_CEILING_MS"):
        add(not hasattr(gesture, gone), f"hotkey_gesture JA' NAO define {gone}")
    for gone in ("is_hold", "resolve_taps", "surface_for"):
        add(not hasattr(gesture, gone), f"hotkey_gesture JA' NAO tem {gone}")
    for gone in ("hold_ms", "clamp_hold_ms", "HOTKEY_HOLD_MS_CHOICES"):
        add(not hasattr(settings, gone), f"hotkey_settings JA' NAO tem {gone}")
    assigned = re.findall(
        r"^(HOTKEY_HOLD_MS|HOTKEY_TAP_WINDOW_MS|HOLD_CEILING_MS|"
        r"HOTKEY_LIVE_FALLBACKS|hotkey_threshold|VK_MENU)\s*=", source, re.M)
    add(not assigned, "o shell nao DEFINE nenhuma constante/limiar do contrato antigo",
        str(assigned) or "nenhuma atribuicao")
    add("def hotkey_threshold" not in source, "hotkey_threshold foi REMOVIDO")
    stray_state = re.findall(
        r"self\.(_hotkey_tap_count|_hotkey_tap_token|_hotkey_last_tap|"
        r"_measuring|_hold_fired|fake_hold_ms)\s*=", source)
    add(not stray_state, "o shell nao guarda estado de toques/medicao",
        str(sorted(set(stray_state))) or "nenhum")
    def names_used(fragment: str, name: str) -> bool:
        """O NOME aparece no CODIGO? (docstring e comentario nao contam.)"""
        try:
            fragment_tree = ast.parse(textwrap.dedent(fragment))
        except SyntaxError:
            return True
        for node in ast.walk(fragment_tree):
            if isinstance(node, ast.Attribute) and node.attr == name:
                return True
            if isinstance(node, ast.Name) and node.id == name:
                return True
        return False

    thread_src = next((ast.get_source_segment(source, n) or "")
                      for n in ast.walk(ast.parse(source))
                      if isinstance(n, ast.ClassDef) and n.name == "HotkeyThread")
    hotkey_methods = class_methods(
        source, "SottoShell", ("hotkey_pressed", "hotkey_live", "_hotkey_resolve"))
    reads_keyboard = [name for name, body in hotkey_methods.items()
                      if names_used(body, "GetAsyncKeyState")]
    add(not names_used(thread_src, "GetAsyncKeyState") and not reads_keyboard,
        "NINGUEM le' o teclado no caminho da hotkey (GetAsyncKeyState saiu de la)",
        str(reads_keyboard) or "nenhum leitor")

    # -- ARM 2 -----------------------------------------------------------------
    print("\nARM 2 -- as duas teclas: um so' dono, e ele e' gesto puro")
    add(gesture.PANELS_ACCELERATOR == "Alt+C",
        "a tecla dos paineis e' Alt+C", gesture.PANELS_ACCELERATOR)
    add(gesture.LIVE_ACCELERATOR == "Ctrl+Space",
        "a tecla da legenda ao vivo e' Ctrl+Space", gesture.LIVE_ACCELERATOR)
    add(gesture.parse_accelerator("Alt+C") == (('alt',), ord('C')),
        "Alt+C -> (('alt',), ord('C'))", str(gesture.parse_accelerator("Alt+C")))
    add(gesture.parse_accelerator("Ctrl+Space") == (('ctrl',), 0x20),
        "Ctrl+Space -> (('ctrl',), 0x20) -- o VK da barra de espaco",
        str(gesture.parse_accelerator("Ctrl+Space")))
    add(gesture.normalise_accelerator("control+space") == "Ctrl+Space",
        "o texto canonico e' Ctrl+Space", gesture.normalise_accelerator("control+space"))
    try:
        gesture.parse_accelerator("Space")
        bare = True
    except ValueError:
        bare = False
    add(bare is False, "uma tecla sem modificador e' RECUSADA (escreveria na app do dono)")
    add(settings.DEFAULTS == {"panels": gesture.PANELS_ACCELERATOR,
                              "live": gesture.LIVE_ACCELERATOR},
        "a fabrica das duas teclas vem de hotkey_gesture (uma vez)",
        str(settings.DEFAULTS))
    add("def hotkey_numbers()" in source and "hotkey_gesture" in source,
        "o shell le' as teclas por hotkey_numbers()")
    parse_body = def_body(source, "parse_accelerator")
    add("hotkey_numbers" in parse_body and "'F1'" not in parse_body,
        "parse_accelerator do shell DELEGA no gesto (sem segunda tabela de teclas)",
        parse_body.splitlines()[-1:] or "")
    arm_body = def_body(source, "arm_hotkey")
    add("accelerators" in arm_body and "'live'" in arm_body,
        "arm_hotkey arma a legenda com a tecla do FICHEIRO do dono")

    # -- ARM 3 -----------------------------------------------------------------
    print("\nARM 3 -- a regra pura: um passo por pressao, sem relogio")
    add(gesture.next_surface(False, "panel") == "strip",
        "escondido (ultimo show: painel) -> faixa de BAIXO",
        str(gesture.next_surface(False, "panel")))
    add(gesture.next_surface(True, "strip") is None,
        "faixa de baixo no ecra -> ESCONDE", str(gesture.next_surface(True, "strip")))
    add(gesture.next_surface(False, "strip") == "panel",
        "escondido (ultimo show: faixa) -> painel da DIREITA",
        str(gesture.next_surface(False, "strip")))
    add(gesture.next_surface(True, "panel") is None,
        "painel da direita no ecra -> ESCONDE", str(gesture.next_surface(True, "panel")))
    add(gesture.next_surface.__code__.co_argcount == 2,
        "a regra so' olha para a JANELA (visible, surface) -- nenhum tempo",
        str(gesture.next_surface.__code__.co_varnames[:2]))
    visible, surface = False, "panel"
    seq = []
    for _ in range(10):
        nxt = gesture.next_surface(visible, surface)
        seq.append(nxt or "hide")
        if nxt is None:
            visible = False
        else:
            visible, surface = True, nxt
    add(seq == ["strip", "hide", "panel", "hide", "strip", "hide", "panel", "hide",
                "strip", "hide"],
        "10 pressoes na regra pura: 10 mudancas, shows strip,panel,strip,panel,strip",
        str(seq))

    # -- ARM 4 -----------------------------------------------------------------
    print("\nARM 4 -- o shell EXECUTADO: estados, nao intencoes")
    ns = build_shell(source, gesture)
    if ns is None:
        add(False, "hotkey_pressed/hotkey_live/_hotkey_resolve extraidos do ficheiro")
        return verdict("ALTC-GESTURE")
    add(True, "hotkey_pressed/hotkey_live/_hotkey_resolve extraidos do ficheiro")
    spies = ns['_spies']

    # (a) DEZ pressoes -> DEZ mudancas.
    host = FakeShell(ns, visible=False, surface='panel')
    t0 = real_time.perf_counter()
    for _ in range(10):
        ns['hotkey_pressed'](host)
    elapsed_ms = (real_time.perf_counter() - t0) * 1000.0
    events = host.events
    shows = [surface for kind, surface in events if kind == 'show']
    add(visibility_changes(events) == 10,
        "(a) 10 pressoes -> EXACTAMENTE 10 mudancas de visibilidade", str(events))
    add(shows == ["strip", "panel", "strip", "panel", "strip"],
        "(a) os shows alternam strip,panel,strip,panel,strip", str(shows))
    add([kind for kind, _ in events] == ["show", "hide"] * 5,
        "(a) cada pressao muda o ecra (show,hide,show,hide,...)",
        str([kind for kind, _ in events]))
    add(host.live_calls == [], "(a) nenhuma das 10 pressoes de Alt+C mexe na legenda",
        str(host.live_calls))
    add(spies['time'].reads == [],
        "(a) o caminho da pressao NAO LE' RELOGIO nenhum",
        str(spies['time'].reads) or "zero leituras")
    add(spies['threading'].timers == [],
        "(a) nenhum Timer armado: nao ha adiamento nenhum",
        str(spies['threading'].timers) or "zero timers")
    per_press = elapsed_ms / 10.0
    add(per_press < 50.0,
        "(a) pressao -> mudanca de estado MEDIDA no processo",
        f"{elapsed_ms:.3f} ms / 10 pressoes = {per_press:.3f} ms por pressao")

    # (b) duas pressoes separadas por 10 s de relogio: DUAS mudancas.
    host = FakeShell(ns, visible=False, surface='panel')
    ns['hotkey_pressed'](host)
    spies['time'].now += 10.0           # o dono demora 10 s a carregar outra vez
    ns['hotkey_pressed'](host)
    add(visibility_changes(host.events) == 2,
        "(b) duas pressoes a 10 s -> DUAS mudancas (nao e' um gesto duplo)",
        str(host.events))
    add(spies['time'].reads == [],
        "(b) os 10 s nao mudam nada porque o codigo nao os le'",
        str(spies['time'].reads) or "zero leituras")

    # (c) uma pressao com 300 ms de relogio: UMA mudanca, nenhuma legenda.
    host = FakeShell(ns, visible=False, surface='panel')
    ns['hotkey_pressed'](host)
    spies['time'].now += 0.3            # a tecla ficou 300 ms em baixo
    for delay, fn in list(spies['threading'].timers):
        fn()                            # se algum timer existisse, disparava aqui
    add(visibility_changes(host.events) == 1,
        "(c) uma pressao de 300 ms -> UMA mudanca (nao e' um HOLD)", str(host.events))
    add(host.live_calls == [],
        "(c) os 300 ms NAO comutam a legenda", str(host.live_calls))
    add("_tick" not in thread_methods and not re.search(
            r"self\._measuring\s*=", source),
        "(c) nao existe onde 300 ms signifiquem alguma coisa (_tick/_measuring fora)")

    # (d) Ctrl+Space: a legenda comuta uma vez por pressao, e nao toca em painel.
    host = FakeShell(ns, visible=False, surface='panel', caption=False)
    ns['hotkey_live'](host)
    ns['hotkey_live'](host)
    add(host.live_calls == [True, False],
        "(d) Ctrl+Space: liga, desliga -- uma vez por pressao", str(host.live_calls))
    add(host.events == [], "(d) Ctrl+Space NAO toca nos paineis", str(host.events))

    # O ciclo continua a ler o que a JANELA mede.
    resolve_code = code_only(source, "SottoShell", "_hotkey_resolve")
    add("window_visible" in resolve_code,
        "o passo dos paineis mede a JANELA (window_visible), nao uma cache")
    add("surface_applied" in resolve_code,
        "o passo dos paineis le' a superficie aplicada (a memoria do ciclo)")
    hide_code = code_only(source, "SottoShell", "hide_panel")
    add("surface_applied" not in hide_code,
        "hide_panel NAO limpa surface_applied (e' o que faz o show seguinte alternar)")

    # -- ARM 5 -----------------------------------------------------------------
    print("\nARM 5 -- a thread: UM WM_HOTKEY = UM passo, e o pump nao trabalha")
    press_src = class_methods(source, "HotkeyThread", ("_on_press",)).get("_on_press", "")
    add(bool(press_src), "_on_press extraido do ficheiro")
    if press_src:
        class FakeThread:
            def __init__(self):
                self.pressed = 0
                self.role = 'panels'
                self.accelerator = 'Alt+C'
                self.thread_id = 4242
                self.lines = []
                self.calls = 0

            def log_fn(self, message):
                self.lines.append(str(message))

            def on_hotkey(self):
                self.calls += 1

        thread = FakeThread()
        lns = {}
        exec(compile(ast.Module(body=[ast.parse(press_src).body[0]], type_ignores=[]),
                     "<on-press>", "exec"), lns)
        lns["_on_press"](thread)
        lns["_on_press"](thread)
        add(thread.calls == 2,
            "duas entregas -> dois callbacks (nem mais, nem menos)", str(thread.calls))
        add(any("HOTKEY_PRESSED" in line and "role=panels" in line
                and "count=2" in line for line in thread.lines),
            "o log conta a entrega com papel e tecla", str(thread.lines[-1:]))
        body = code_only(source, "HotkeyThread", "_on_press")
        add("while" not in body and "for " not in body and "sleep" not in body
            and "time." not in body,
            "_on_press nao tem laco, nao dorme e nao le' relogio")
    run_code = code_only(source, "HotkeyThread", "run")
    add("RegisterHotKey" in run_code and "MOD_NOREPEAT" in run_code,
        "run regista com MOD_NOREPEAT (um WM_HOTKEY por pressao)")
    add("WaitMessage" in run_code and "sleep" not in run_code,
        "ocioso dorme em WaitMessage (sem sonda periodica)", "sleep=" +
        str("sleep" in run_code))
    add("UnregisterHotKey" in run_code,
        "o unregister corre no thread que registou (antes nao desligava nada)")
    stop_code = code_only(source, "HotkeyThread", "stop")
    add("WM_APP" in stop_code and "PostThreadMessageW" in stop_code,
        "stop ACORDA o WaitMessage com WM_APP")

    # -- ARM 6 -----------------------------------------------------------------
    print("\nARM 6 -- o ficheiro do dono (persistencia, com recusa explicita)")
    live_file_ok = live_file.exists()
    add(live_file_ok, f"{live_file.name} existe", str(live_file))
    if live_file_ok:
        payload = json.loads(live_file.read_text(encoding="utf-8"))
        add(payload.get("live") == gesture.LIVE_ACCELERATOR,
            "o ficheiro vivo diz Ctrl+Space", str(payload))
        add(payload.get("panels") == gesture.PANELS_ACCELERATOR,
            "o ficheiro vivo diz Alt+C", str(payload))
    tmp_dir = Path(tempfile.mkdtemp(prefix="altc-cfg-"))
    tmp_file = tmp_dir / "hotkey-settings.json"
    try:
        add(settings.accelerators(tmp_file) == settings.DEFAULTS,
            "sem ficheiro as teclas sao as de FABRICA", str(settings.accelerators(tmp_file)))
        written = settings.write({"live": "ctrl+space"}, tmp_file)
        add(written.get("ok") is True and written.get("live") == "Ctrl+Space",
            "a escolha grava-se (e normaliza)", str(written))
        add(settings.accelerators(tmp_file)["live"] == "Ctrl+Space",
            "a escolha le'-se de volta", str(settings.accelerators(tmp_file)))
        refused = settings.write({"live": "Nope+Zzz"}, tmp_file)
        add(refused.get("ok") is False, "uma tecla invalida e' RECUSADA", str(refused))
        add(settings.accelerators(tmp_file)["live"] == "Ctrl+Space",
            "a recusa NAO apaga a escolha anterior",
            str(settings.accelerators(tmp_file)))
        add(settings.write({"panels": "alt+c"}, tmp_file).get("ok") is True,
            "a tecla dos paineis tambem grava (a ordem e' uma so')")
        tmp_file.write_text("{ nao e' json", encoding="utf-8")
        add(settings.accelerators(tmp_file) == settings.DEFAULTS,
            "um ficheiro estragado volta a FABRICA (a app nao fica sem tecla)",
            str(settings.accelerators(tmp_file)))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # -- ARM 7 -----------------------------------------------------------------
    print("\nARM 7 -- a legenda desligada e' so' DISPLAY (executado da fonte)")
    live_src = class_methods(source, "SottoShell", ("_set_live_enabled",)).get(
        "_set_live_enabled", "")
    add(bool(live_src), "_set_live_enabled extraido do ficheiro")
    if live_src:
        lns = {"log": FakeLog()}
        exec(compile(ast.Module(body=[ast.parse(live_src).body[0]], type_ignores=[]),
                     "<set-live>", "exec"), lns)

        class WatchedShell:
            ALLOWED = {"_caption_wanted", "show_caption_window"}

            def __init__(self):
                object.__setattr__(self, "touched", [])
                object.__setattr__(self, "_caption_wanted", True)

            def __getattr__(self, name):
                if name in WatchedShell.ALLOWED:
                    object.__setattr__(self, name, lambda *a, **k: None)
                    return object.__getattribute__(self, name)
                self.touched.append(name)
                return lambda *a, **k: None

            def show_caption_window(self, on):
                self.touched.append(f"show_caption_window({on})")
                return None

        watched = WatchedShell()
        lns["_set_live_enabled"](watched, {"on": False})
        add(watched.touched == ["show_caption_window(False)"],
            "desligar a legenda toca SO' na janela da legenda", str(watched.touched))
        add(watched._caption_wanted is False, "a flag `_caption_wanted` fica em False")
        live_code = code_only(source, "SottoShell", "_set_live_enabled")
        for forbidden in ("_pause_shell", "_reload_worker", "_restart_worker",
                          "hide_panel", "show_panel", "worker", "history"):
            add(forbidden not in live_code, f"_set_live_enabled NAO nomeia {forbidden}")

    return verdict("ALTC-GESTURE")


# ---------------------------------------------------------------------------
# O BRACO VERMELHO
# ---------------------------------------------------------------------------
SHELL_DEFER_PATCH = (
    "        return self._hotkey_dispatch('panels')",
    "        t = threading.Timer(0.4, lambda: self._hotkey_dispatch('panels'))\n"
    "        t.daemon = True\n"
    "        t.start()\n"
    "        return None",
)


def _copy_tree(tmp: Path) -> Path:
    webview = tmp / "app" / "webview"
    webview.mkdir(parents=True)
    for name in ("hotkey_gesture.py", "hotkey_settings.py", "sotto_webview.py",
                 "panel_state.py"):
        shutil.copy2(ROOT / "app" / "webview" / name, webview / name)
    (tmp / "_main").mkdir()
    shutil.copy2(LIVE_FILE, tmp / "_main" / LIVE_FILE.name)
    return webview


def neg_arm() -> int:
    """Muta uma COPIA e exige RED -- duas regressoes, uma de cada lado.

    MUTANTE 1: o ADIAMENTO de 400 ms volta a `hotkey_pressed` (o gesto que o dono
    mandou tirar em 2026-10-30: *"tem um delay DO CARALHO pra aparecer os
    painels"*). MUTANTE 2: o LIMIAR de HOLD volta ao modulo do gesto (a duracao
    da segurada volta a decidir, que e' o que ele mandou tirar hoje).
    """
    failures = 0
    for name, mutate in (("defer-400ms", _mutate_shell_defer),
                         ("hold-threshold", _mutate_gesture_hold)):
        tmp = Path(tempfile.mkdtemp(prefix="altc-neg-"))
        try:
            webview = _copy_tree(tmp)
            note = mutate(webview)
            if note is None:
                print(f"NEG-ARM: nao consegui mutar {name} (o texto mudou)")
                failures += 1
                continue
            print(f"\n=== NEG-ARM {name}: {note}")
            rc = run(webview / "hotkey_gesture.py", webview / "sotto_webview.py",
                     webview / "hotkey_settings.py",
                     tmp / "_main" / LIVE_FILE.name)
            if rc == EXIT_FAIL:
                print(f"NEG-ARM {name} PASS -- RED as designed")
            else:
                print(f"NEG-ARM {name} FAIL -- o oraculo NAO ve a regressao")
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print("\nNEG-ARM FAIL -- o oraculo nao ve a regressao")
        return EXIT_PASS
    print("\nNEG-ARM PASS -- RED as designed: as duas regressoes derrubam o oraculo")
    return EXIT_FAIL


def _mutate_shell_defer(webview: Path):
    target = webview / "sotto_webview.py"
    text = target.read_text(encoding="utf-8")
    if SHELL_DEFER_PATCH[0] not in text:
        return None
    target.write_text(text.replace(*SHELL_DEFER_PATCH), encoding="utf-8")
    return "adiamento de 400 ms reinstalado em hotkey_pressed"


def _mutate_gesture_hold(webview: Path):
    target = webview / "hotkey_gesture.py"
    text = target.read_text(encoding="utf-8")
    marker = "#: A tecla dos PAINEIS."
    if marker not in text:
        return None
    text = text.replace(
        marker,
        "HOTKEY_HOLD_MS = 200.0\n\n\ndef is_hold(held_ms, hold_ms=HOTKEY_HOLD_MS):\n"
        "    return held_ms is not None and float(held_ms) >= float(hold_ms)\n\n\n"
        + marker, 1)
    target.write_text(text, encoding="utf-8")
    return "limiar de HOLD reinstalado no modulo do gesto"


def main(argv) -> int:
    if "--neg-arm" in argv:
        return neg_arm()
    return run(GESTURE, SHELL, SETTINGS, LIVE_FILE)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
