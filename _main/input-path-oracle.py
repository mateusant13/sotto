#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# BLOCKS: BUG-20261023-01
"""INPUT-PATH ORACLE -- o rato do dono NAO passa pelo Sotto. Nunca.

O DEFEITO MEDIDO (2026-10-23, no log do proprio dono, `_main/webview-run.log`):

    19:46:42.825  PANEL_VISIBILITY_ON_SCREEN visible=false ... panel_shown=false
    19:46:41.606  OUTSIDE_CLICK_HOOK installed=true ... type=WH_MOUSE_LL

ASSIM: 22 ms depois de a app nascer, com o painel NUNCA mostrado, o Sotto
instalou um hook global de rato. Um `WH_MOUSE_LL` poe TODOS os eventos do rato
(1000 por segundo num rato de 1000 Hz) a passar pelo callback PYTHON da thread
que o instalou, antes de chegarem a qualquer outra coisa. O cursor soluça; o
resto do sistema -- que nao espera por esse callback -- fica bom. E sob
Ctrl+Alt+Del o Windows NAO entrega hooks de utilizador (o secure desktop nao os
chama), por isso o cursor fica bom la dentro e volta a travar ao sair.

As palavras do dono, verbatim:
    *"MEU MOUSE TA TRAVANDO DEMAIS. O RESTO DO SISTEMA NAO"*
    *"MEU MOUSE VOLTA AO NORMAL QUANDO EU ENTRO NO CONTROL ALT DEL, MAS VOLTA A
      TRAVAR DEPOIS Q EU SAIO"*
    *"sotto e pra usuarios ate com pc fraco, isso e inadmissivel"*

A PRIMEIRA VERSAO deste portao julgava o MEIO-FIO: exigia que o hook so fosse
instalado sob `_wants_hook` e liberto no `stop`. Isso era um gate a proteger um
mecanismo que nao devia existir. A 2026-10-30 o dono cortou o no', verbatim:
*"se esses hooks sao burros ou desnecessarios, remove. nao mantem nada q tu ta
achando q e pior"*. O hook foi REMOVIDO do shell e substituido por um tick de
`SetTimer` que so' corre com o painel visivel (`OutsideClickWatcher`).

POR ISSO O INVARIANTE AGORA E' A AUSENCIA, nao a disciplina do mecanismo:

  C1  nao existe UM UNICO `SetWindowsHookEx` no shell (AST: qualquer variante),
      nem a constante `WH_*_LL`, nem a struct `MSLLHOOKSTRUCT`. Um hook que
      ninguem instala e' a unica forma de o rato do dono ser sempre dele.
  C2  a regra: `_wants_poll` == `armed or edit_mode`.
  C3  `hide_panel` desarma o watcher (o tick sai com o painel).
  C4  o timer NUNCA e' pedido fora de `_restart_timer`, e `_restart_timer` pede
      `KillTimer` primeiro e desiste quando `_wants_poll()` e' falso.
  C5  o comportamento da CLASSE REAL: nasce sem tick, segue as duas flags, e um
      `_poll`/`_poll_drag` a correr nao lanca nem fecha nada.
  C6  o RITMO e' o que o estado pede: 25 ms a arrastar, 100 ms a vigiar.
  C7  `stop` mata o timer (um timer vivo numa thread morta e' um tick que nunca
      chega).
  C8  as PROPRIEDADES pedem o ritmo: nao ha caminho que mude o estado sem
      re-armar o tick.
  C9  mostrar arma e esconder desarma, e SO' no watcher (um segundo escritor e'
      um invocador a mais).
  C10 o tick nao fecha o painel por si: a decisao continua a passar por
      `_consider`, que e' a unica funcao com as guardas (a sair, edit mode, nao
      armado, painel nao visivel, dentro do rect, janela nossa).

Cada braco tem de apanhar um mutante (ver `MUTANTS`), e o `--neg-arm` constroi o
mutante 0 e obriga-o a ficar VERMELHO -- rc=1 POR DESENHO.

    python _main/input-path-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main/input-path-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca processo nenhum, NAO instala hook nenhum, NAO cria janela: julga
FICHEIROS e o estado de um objecto. Pode entrar na bateria.
"""
import argparse
import ast
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL_DIR = os.path.join(REPO, "app", "webview")
SHELL = os.path.join(SHELL_DIR, "sotto_webview.py")
MUTANT_PREFIX = "_inputpath-neg-"

#: Nomes que so' existem para instalar um hook global. `SetWindowsHookEx` cobre
#: `...ExA`/`...ExW`: qualquer um deles e' o mesmo mecanismo.
HOOK_CALLS = ("SetWindowsHookEx", "SetWindowsHookExA", "SetWindowsHookExW",
              "UnhookWindowsHookEx", "CallNextHookEx")


def crlf(text):
    """A shell e CRLF-pura: o texto que a parte tem de ser CRLF tambem."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _class(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _func_in(src_lines, parent, name):
    """O texto-fonte de um metodo, do `def` ate a ultima linha do seu corpo."""
    for node in ast.walk(parent) if parent is not None else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = node.lineno
            end = max([getattr(n, "lineno", start) for n in ast.walk(node)] or [start])
            return "\n".join(src_lines[start - 1:end])
    return ""


def _func_anywhere(src_lines, tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = node.lineno
            end = max([getattr(n, "lineno", start) for n in ast.walk(node)] or [start])
            return "\n".join(src_lines[start - 1:end])
    return ""


def load_module(path, name):
    # A shell importa `hot_reload`, `youtube_captions`, ... que vivem ao lado
    # dela: sem este caminho, importar a shell de fora rebenta com ModuleNotFound.
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class StubShell:
    """O minimo que o watcher toca: nenhuma janela, nenhum shell real.

    `hwnd = 0` de proposito: e' o mesmo "nao ha janela" que o `_poll` tem de
    aguentar, e o `_consider` recusa-se a fechar por `panel-not-visible`.
    """

    hwnd = 0
    edit_grab = None
    visible = False

    def __init__(self):
        import threading
        self.exiting = threading.Event()
        self.hidden = []

    def hide_panel(self, reason):
        self.hidden.append(reason)
        return True

    def edit_drag_to(self, x, y, persist=False):
        return True


def _func_node(parent, name):
    """O NODE do metodo, para se poder contar CHAMADAS (nao texto)."""
    for node in ast.walk(parent) if parent is not None else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls(node, name):
    """Quantas vezes `name(...)` e CHAMADO dentro de `node`."""
    if node is None:
        return -1
    return sum(1 for n in ast.walk(node)
               if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == name)


def _hook_sites(tree):
    """(chamadas, nomes, structs): tudo o que ainda cheira a hook global."""
    calls = sorted({getattr(n.func, "attr", "") for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") in HOOK_CALLS})
    names = sorted({t.id for n in ast.walk(tree)
                    if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)
                    and t.id.startswith("WH_") and t.id.endswith("_LL")})
    structs = sorted({n.name for n in ast.walk(tree)
                      if isinstance(n, ast.ClassDef)
                      and ("HOOKSTRUCT" in n.name or n.name.startswith("MSLL"))})
    return calls, names, structs


def arms(mod, source_text):
    """Todas as verificacoes. (`mod` pode ser a shell REAL ou uma copia mutante.)"""
    results = []
    src_lines = source_text.replace("\r\n", "\n").split("\n")
    tree = ast.parse(source_text)
    watcher = _class(tree, "OutsideClickWatcher")
    if watcher is None:
        return [("C0 a classe OutsideClickWatcher existe", False, "ausente")]

    run = _func_in(src_lines, watcher, "run")
    restart = _func_in(src_lines, watcher, "_restart_timer")
    wants = _func_in(src_lines, watcher, "_wants_poll")
    hide = _func_anywhere(src_lines, tree, "hide_panel")
    show = _func_anywhere(src_lines, tree, "show_panel")

    # ── C1: A AUSENCIA ─────────────────────────────────────────────────────
    calls, names, structs = _hook_sites(tree)
    results.append(("C1 nenhum hook global existe no shell (chamada, constante "
                    "ou struct)",
                    not calls and not names and not structs,
                    {"calls": calls, "wh_names": names, "structs": structs}))

    # ── C2: a regra ────────────────────────────────────────────────────────
    ok_c2 = "return bool(self._armed or self._edit_mode)" in wants
    results.append(("C2 `_wants_poll` == armed or edit_mode", ok_c2, wants.strip()))

    # ── C3: esconder desarma ───────────────────────────────────────────────
    ok_c3 = "click_watcher.armed = False" in hide
    results.append(("C3 `hide_panel` desarma o watcher", ok_c3, hide[-400:]))

    # ── C4: o timer pede-se num sitio so', e com guarda ────────────────────
    set_timer_everywhere = sum(1 for n in ast.walk(watcher)
                               if isinstance(n, ast.Call)
                               and getattr(n.func, "attr", "") == "SetTimer")
    set_timer_here = _calls(_func_node(watcher, "_restart_timer"), "SetTimer")
    ok_c4 = (set_timer_everywhere == 1 and set_timer_here == 1
             and "_wants_poll()" in restart
             and "KillTimer" in restart
             and _calls(_func_node(watcher, "run"), "SetTimer") == 0)
    results.append(("C4 o timer so' e' pedido em `_restart_timer`, com guarda",
                    ok_c4, {"set_timer_total": set_timer_everywhere,
                            "set_timer_in_restart": set_timer_here,
                            "guard": "_wants_poll()" in restart,
                            "run_pede_timer": _calls(_func_node(watcher, "run"),
                                                     "SetTimer")}))

    # ── C5: a classe real, sem thread e sem janela ─────────────────────────
    cls = getattr(mod, "OutsideClickWatcher")
    shell = StubShell()
    w = cls(shell)
    steps = [
        ("nasce sem tick", w._wants_poll() is False),
        ("armed=True pede o tick", (setattr(w, "armed", True) or w._wants_poll()) is True),
        ("armed=False larga o tick", (setattr(w, "armed", False) or w._wants_poll()) is False),
        ("edit_mode=True pede o tick",
         (setattr(w, "edit_mode", True) or w._wants_poll()) is True),
        ("edit_mode=False larga o tick",
         (setattr(w, "edit_mode", False) or w._wants_poll()) is False),
        ("um tick desarmado nao lanca", _noraise(w._poll) is True),
        ("um tick desarmado nao fecha", (w._poll() or not shell.hidden) is True),
        ("um tick de arrasto nao lanca", _noraise(w._poll_drag) is True),
    ]
    bad = [name for name, ok in steps if not ok]
    results.append(("C5 a classe real segue as duas flags e um tick sobrando e' inerte",
                    not bad, bad))

    # ── C6: o ritmo ────────────────────────────────────────────────────────
    w2 = cls(StubShell())
    ritmo_visivel = w2._interval_ms()
    w2.edit_mode = True
    ritmo_arrasto = w2._interval_ms()
    w2.edit_mode = False
    ok_c6 = (ritmo_arrasto == mod.POLL_MS_DRAG
             and ritmo_visivel == mod.POLL_MS_VISIBLE
             and ritmo_arrasto < ritmo_visivel)
    results.append(("C6 a arrastar 25 ms, a vigiar 100 ms", ok_c6,
                    {"visivel": ritmo_visivel, "arrasto": ritmo_arrasto,
                     "POLL_MS_VISIBLE": mod.POLL_MS_VISIBLE,
                     "POLL_MS_DRAG": mod.POLL_MS_DRAG}))

    # ── C7: `stop` mata o timer ────────────────────────────────────────────
    stop_node = _func_node(watcher, "stop")
    ok_c7 = _calls(stop_node, "KillTimer") >= 1
    results.append(("C7 `stop` mata o timer", ok_c7,
                    {"killtimer": _calls(stop_node, "KillTimer")}))

    # ── C8: as propriedades pedem o ritmo ──────────────────────────────────
    setters = [n for n in ast.walk(watcher)
               if isinstance(n, ast.FunctionDef)
               and any(isinstance(d, ast.Attribute) and d.attr == "setter"
                       for d in n.decorator_list)]
    setter_names = sorted(n.name for n in setters)
    ok_c8 = ({"armed", "edit_mode"} <= set(setter_names)
             and all(_calls(n, "_apply_timer") >= 1 for n in setters))
    results.append(("C8 as propriedades pedem o ritmo", ok_c8,
                    {"setters": setter_names,
                     "without_timer": [n.name for n in setters
                                       if not _calls(n, "_apply_timer")]}))

    # ── C9: mostrar/esconder passam pelo watcher ───────────────────────────
    ok_c9 = ("click_watcher.armed = True" in show
             and "click_watcher.armed = False" in hide)
    results.append(("C9 mostrar arma e esconder desarma, no watcher", ok_c9,
                    {"show": "click_watcher.armed = True" in show,
                     "hide": "click_watcher.armed = False" in hide}))

    # ── C10: a decisao continua a ser a de `_consider` ─────────────────────
    poll_node = _func_node(watcher, "_poll")
    ok_c10 = (_calls(poll_node, "hide_panel") == 0
              and _calls(poll_node, "_consider") >= 1
              and "click-outside" not in _func_in(src_lines, watcher, "_poll"))
    results.append(("C10 o tick nao fecha por si: a decisao passa por `_consider`",
                    ok_c10,
                    {"hide_panel_no_tick": _calls(poll_node, "hide_panel"),
                     "_consider_no_tick": _calls(poll_node, "_consider")}))
    return results


def _noraise(fn):
    """Executa `fn()` e diz se NAO lancou. Um tick que lanca mata o vigilante."""
    try:
        fn()
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# os mutantes: cada um tem de deixar o portao VERMELHO
# ---------------------------------------------------------------------------
_GUARD = """        if not self._wants_poll():
            self._last_fg = None
            return False
"""
MUTANTS = [
    (
        "hook-volta",
        "o hook global volta ao caminho vivo (C1)",
        _GUARD + """        user32.SetTimer(None, _POLL_TIMER_ID, int(self._interval_ms()), None)""",
        """        user32.SetWindowsHookExW(14, None, None, 0)
        user32.SetTimer(None, _POLL_TIMER_ID, int(self._interval_ms()), None)""",
    ),
    (
        "regra-sempre",
        "a regra deixa de olhar as flags (C2, C5)",
        """        return bool(self._armed or self._edit_mode)""",
        """        return True""",
    ),
    (
        "esconder-nao-desarma",
        "esconder o painel deixa o tick vivo (C3, C9)",
        """        if self.click_watcher is not None:
            self.click_watcher.armed = False""",
        """        if self.click_watcher is not None:
            pass""",
    ),
    (
        "timer-sempre",
        "o tick arranca mesmo sem nada para vigiar (C4)",
        _GUARD,
        """        if False:
            self._last_fg = None
            return False
""",
    ),
    (
        "stop-nao-mata",
        "o encerramento deixa o timer vivo numa thread morta (C7)",
        """        if self.thread_id:
            try:
                user32.KillTimer(None, _POLL_TIMER_ID)""",
        """        if self.thread_id:
            try:
                pass""",
    ),
    (
        "edit-mode-sem-ritmo",
        "sair do edit mode muda o estado e NAO re-arma o tick (C8)",
        """    @edit_mode.setter
    def edit_mode(self, value):
        self._edit_mode = bool(value)
        self._apply_timer()""",
        """    @edit_mode.setter
    def edit_mode(self, value):
        self._edit_mode = bool(value)""",
    ),
    (
        "ritmo-unico",
        "o arrasto perde o ritmo proprio: 100 ms a arrastar (C6)",
        """        return POLL_MS_DRAG if self._edit_mode else POLL_MS_VISIBLE""",
        """        return POLL_MS_VISIBLE""",
    ),
    (
        "tick-fecha-direto",
        "o tick fecha o painel por si, sem as guardas de `_consider` (C10)",
        """            self._consider(int(point.x), int(point.y), WM_LBUTTONDOWN,
                           source='foreground')""",
        """            self._consider(int(point.x), int(point.y), WM_LBUTTONDOWN,
                           source='foreground')
            self.shell.hide_panel('click-outside')""",
    ),
    (
        "show-nao-arma",
        "mostrar o painel deixa de armar o watcher: o clique fora nao fecha (C9)",
        """            self.click_watcher.armed = True""",
        """            pass""",
    ),
    (
        "hook-de-teclado",
        "aparece um segundo tipo de hook global, o do teclado (C1)",
        """HC_ACTION = 0""",
        """HC_ACTION = 0
WH_KEYBOARD_LL = 13""",
    ),
]


def build_mutant(text, name, old, new):
    old, new = crlf(old), crlf(new)
    count = text.count(old)
    if count != 1:
        raise RuntimeError("%s: a ancora casou %d vezes (esperado 1)" % (name, count))
    path = os.path.join(SHELL_DIR, "%s%s.py" % (MUTANT_PREFIX, name))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new, 1))
    return path


def clean_mutants():
    if not os.path.isdir(SHELL_DIR):
        return
    for name in os.listdir(SHELL_DIR):
        if name.startswith(MUTANT_PREFIX) and name.endswith(".py"):
            try:
                os.remove(os.path.join(SHELL_DIR, name))
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true",
                    help="aponta o portao a uma copia partida: tem de sair rc=1")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    clean_mutants()
    text = _read(SHELL)

    if args.neg_arm:
        try:
            name, _why, old, new = MUTANTS[0]
            path = build_mutant(text, name, old, new)
            try:
                mmod = load_module(path, "_inputpath_neg_only")
                caught = [r for r in arms(mmod, _read(path)) if not r[1]]
            except Exception as exc:  # noqa: BLE001 -- ilegal tambem e apanhado
                caught = [("import", False, repr(exc))]
            if caught:
                print("NEG-ARM PASS -- a copia partida foi apanhada:")
                for label, _ok, got in caught:
                    print("   [RED] %s" % label)
                return 1
            print("NEG-ARM FAIL -- a copia partida ficou verde")
            return 0
        finally:
            clean_mutants()

    failures = []
    print("shell: %s (%d bytes)" % (SHELL, os.path.getsize(SHELL)))
    mod = load_module(SHELL, "_inputpath_shell")
    for label, ok, got in arms(mod, text):
        print("%s %s" % ("GREEN" if ok else "RED  ", label))
        if not ok:
            print("      got=%r" % (got,))
            failures.append(label)

    for name, why, old, new in MUTANTS:
        try:
            path = build_mutant(text, name, old, new)
        except RuntimeError as exc:
            print("RED   mutante %s nao pode ser construido: %s" % (name, exc))
            failures.append(name)
            continue
        try:
            mmod = load_module(path, "_inputpath_neg_%s" % name.replace("-", "_"))
            caught = [r for r in arms(mmod, _read(path)) if not r[1]]
        except Exception as exc:  # noqa: BLE001 -- um mutante ilegal tambem e apanhado
            caught = [("import", False, repr(exc))]
        if caught:
            print("GREEN mutante %s apanhado (%s)" % (name, why))
        else:
            print("RED   mutante %s NAO foi apanhado (%s)" % (name, why))
            failures.append(name)
    clean_mutants()

    if failures:
        print("INPUT-PATH VERDICT FAIL (%d)" % len(failures))
        return 2
    print("INPUT-PATH VERDICT PASS -- nenhum hook global existe: o rato do dono "
          "nao passa pelo Sotto nem com o painel aberto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
