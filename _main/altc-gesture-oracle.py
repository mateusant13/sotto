#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-10-30 -- o gesto do Alt+C
# (1 toque = painel de baixo, 2 toques = da direita, HOLD = legenda) medido no
# codigo que corre; nao corrige nenhum defeito, impede que o contrato volte a
# ser contado por presses em vez de medido por duracao.
"""ORACLE: O GESTO DO ALT+C -- 1 toque = painel de baixo, 2 = da direita, HOLD = legenda.

ORDEM DO DONO, verbatim (2026-10-30):

    *"1 tap = painel de baixo, 2 taps = painel da direita,
      HOLD = legenda ao vivo on/off"*

A QUEIXA QUE ISTO FECHA, verbatim (2026-10-30): *"o alt c nao ta dando display em
qualquer painel"*. O contrato anterior (2026-10-18) dava a UM toque a legenda e
so' um SEGUNDO toque dentro de 700 ms subia o primeiro painel -- por isso um
toque isolado **nunca** mostrava painel nenhum, e um Alt+C segurado caia em
"triplo" e mostrava o painel errado.

O QUE E' VERIFICADO, E COMO. Os corpos de `hotkey_pressed`, `_hotkey_resolve`,
`hotkey_hold`, `HotkeyThread._on_press` e `HotkeyThread.measure_hold` sao
EXTRAIDOS DO FICHEIRO QUE VAI CORRER com `ast` e exec'd, contra um shell falso e
um relogio falso. Nenhuma janela e' aberta, nenhum ctypes e' tocado, nada e'
posto no ecra do dono. Um oraculo que reescrevesse a logica mediria a
transcricao, nao o produto.

O NUMERO DO GESTO TEM UM SO' DONO: `app/webview/hotkey_gesture.py`. Se alguem o
voltar a escrever em `sotto_webview.py` -- a segunda verdade que este repo ja
pagou uma vez -- a arm 2 fica vermelha.

Uso:
    python _main/altc-gesture-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/altc-gesture-oracle.py --neg-arm  -> muta uma COPIA e exige RED
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("SOTTO_ROOT") or r"H:\sotto").resolve()
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
GESTURE = ROOT / "app" / "webview" / "hotkey_gesture.py"
EXIT_PASS, EXIT_FAIL = 0, 1

rows: list[tuple[bool, str, str]] = []


#: As DURACOES medidas na mao do dono (2026-10-30, 21 pressoes, `held_ms` lidos
#: pelo `HotkeyThread`). O limiar do HOLD tem de cair no vazio entre as duas:
#:   93 110 187 204 438 468 [ele quer o painel] | 531 578 641 || 1187 ... 3047 [legenda]
_TAP_LENTO_MS = 641.0
_SEGURA_RAPIDA_MS = 1187.0


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


def load_gesture(path: Path):
    spec = _ilu.spec_from_file_location("hotkey_gesture_probe", str(path))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def js_code(text: str) -> str:
    """O JavaScript SEM comentarios -- o que corre, nao o que explica.

    Ingénuo de proposito: tira os blocos `/* */` e as linhas que COMECAM por
    `//`. Nao tenta perceber strings, porque a unica pergunta que se lhe faz e'
    "este ficheiro tem uma COPIA da lista de escolhas", e uma string com
    `//` num URL nao pode fabricar uma lista de numeros.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("//"))


def class_methods(source: str, cls_name: str, names) -> dict:
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


# ---------------------------------------------------------------------------
# Um relogio e um Timer que se controlam (nada de `sleep` num oraculo).
# ---------------------------------------------------------------------------
class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance_ms(self, ms):
        self.now += float(ms) / 1000.0


class FakeTimer:
    """O que `hotkey_pressed` usa de `threading.Timer`: agenda um callback."""

    pending: list = []

    def __init__(self, delay_s, fn):
        self.delay_s = float(delay_s)
        self.fn = fn
        self.daemon = False
        FakeTimer.pending.append(self)

    def start(self):
        return None

    def cancel(self):
        if self in FakeTimer.pending:
            FakeTimer.pending.remove(self)


class FakeThreading:
    Timer = FakeTimer


class FakeLog:
    def __init__(self):
        self.lines = []

    def __call__(self, message, *a, **k):
        self.lines.append(str(message))

    def has(self, needle):
        return any(needle in line for line in self.lines)


def build_shell(source: str, gesture):
    """Os metodos do shell, exec'd contra um `self` falso."""
    # `_hotkey_forget` entrou a 2026-10-30: com a accao a ser imediata, o Timer
    # deixou de adiar o painel e passou a REARMAR a contagem. O corpo tem de vir
    # do ficheiro que corre -- um `lambda` aqui mediria a minha copia.
    bodies = class_methods(source, "SottoShell",
                           ("hotkey_pressed", "_hotkey_resolve", "hotkey_hold",
                            "_hotkey_forget"))
    if len(bodies) != 4:
        return None
    clock = FakeClock()
    namespace = {
        "time": clock,
        "threading": FakeThreading,
        "log": FakeLog(),
        "hotkey_numbers": lambda: gesture,
    }
    module = ast.Module(body=[ast.parse(b).body[0] for b in bodies.values()],
                        type_ignores=[])
    exec(compile(module, "<sotto-shell-hotkey>", "exec"), namespace)
    # Os metodos ficam no namespace do exec; o `self` falso tem de os ver pelo
    # nome que o Timer usa (`self._hotkey_resolve`).
    namespace["_bind"] = (namespace["hotkey_pressed"],
                          namespace["_hotkey_resolve"],
                          namespace["hotkey_hold"],
                          namespace["_hotkey_forget"])
    return namespace


class FakeShell:
    """So' o que os tres metodos tocam. Nenhuma chamada Win32."""

    def __init__(self, caption_on=False, bound=None, visible=False, surface=None):
        self.shown = []
        self.live_calls = []
        self.hidden = []
        # O QUE O WINDOW VESTE. `_hotkey_resolve` decide o toggle por isto e nao
        # por uma intencao; sem estes dois campos o braco do toggle nao tinha
        # como descrever um painel ja' no ecra.
        self.visible = bool(visible)
        self.surface_applied = surface or ("strip" if visible else "")
        self._caption_wanted = bool(caption_on)
        # O DESPACHO. Em producao `hotkey_pressed` poem o token numa FILA e um
        # worker executa; a fila e' stdlib e nao tem regra nenhuma dentro, por
        # isso o oraculo liga o despacho DIRECTO -- o que se mede aqui e' a
        # decisao e o INSTANTE dela, nao o `queue.Queue`.
        if bound is not None:
            self._hotkey_resolve = lambda token: bound[1](self, token)
            self._hotkey_dispatch = lambda token: bound[1](self, token)
            self._hotkey_forget = lambda token: bound[3](self, token)

    def show_strip(self, reason):
        self.shown.append(("strip", reason))
        self.visible = True
        self.surface_applied = "strip"
        return "strip"

    def show_side(self, reason):
        self.shown.append(("side", reason))
        self.visible = True
        self.surface_applied = "side"
        return "side"

    def hide_panel(self, reason):
        self.hidden.append(reason)
        self.shown = [row for row in self.shown]
        self.visible = False
        self.surface_applied = ""
        return True

    def _set_live_enabled(self, payload):
        self.live_calls.append(dict(payload))
        self._caption_wanted = bool(payload.get("on"))
        return "enabled"


def drive(ns, shell, taps, gap_ms):
    """Toca `taps` vezes separadas por `gap_ms`, e fecha o gesto."""
    clock = ns["time"]
    for i in range(taps):
        if i:
            clock.advance_ms(gap_ms)
        ns["hotkey_pressed"](shell)
    # o ultimo toque fecha `window` ms depois
    clock.advance_ms(ns["hotkey_numbers"]().HOTKEY_TAP_WINDOW_MS + 1)
    fired = list(FakeTimer.pending)
    FakeTimer.pending.clear()
    for timer in fired:
        timer.fn()
    return fired


def build_thread(source: str, gesture):
    """`_on_press` + `measure_hold` + `_deliver_hold`, exec'd sobre uma classe falsa.

    `_deliver_hold` entrou na lista a 2026-10-30, no mesmo dia em que o HOLD
    passou a disparar ao CRUZAR o limiar (ordem do dono: *"assim que o alt c é
    segurado suficiente, da display ou tira display da legenda. nao é pra
    esperar o release da tecla"*). O `_on_press` deixou de chamar o callback
    directamente -- passou a chamar `_deliver_hold`, que marca `_hold_fired`
    antes de o entregar. Sem este metodo aqui, o braco falhava com
    `HOTKEY_HANDLER_FAILED` e lia `holds=0 taps=0`: o extractor tinha ficado
    para tras do codigo, que e' a forma mais barata de um oraculo mentir.
    """
    bodies = class_methods(
        source, "HotkeyThread",
        ("_on_press", "_tick", "_finish_measure", "_deliver_hold", "_threshold"))
    if len(bodies) != 5:
        return None
    # O LIMIAR EM VIGOR e' mutavel de proposito: e' o que o dono escolhe no
    # painel da direita, e a arm que prova que a thread o respeita tem de poder
    # muda-lo sem reiniciar nada.
    box = {"hold_ms": float(gesture.HOTKEY_HOLD_MS)}
    namespace = {
        "time": FakeClock(),
        "log": FakeLog(),
        "hotkey_numbers": lambda: gesture,
        "hotkey_threshold": lambda: box["hold_ms"],
        "_thresholdbox": box,
    }
    module = ast.Module(body=[ast.parse(b).body[0] for b in bodies.values()],
                        type_ignores=[])
    exec(compile(module, "<sotto-hotkey-thread>", "exec"), namespace)
    namespace["_bind"] = (namespace["_on_press"], namespace["_tick"],
                          namespace["_finish_measure"], namespace["_deliver_hold"],
                          namespace["_threshold"])
    return namespace


class FakeHotkeyThread:
    def __init__(self):
        self.pressed = 0
        self.thread_id = 4242
        self.fake_hold_ms = None
        self.taps = 0
        self.holds = 0
        self._hold_fired = False
        # A medicao vive no pump (`_tick`), por isso o falso precisa dos dois
        # campos de estado que `hotkey_pressed` inicializa no shell real.
        self._measuring = False
        self._hold_started = 0.0
        self.lines = []

    def log_fn(self, message):
        self.lines.append(str(message))

    def on_hotkey(self):
        self.taps += 1

    def on_hold(self):
        self.holds += 1

    #: A tecla, como um teclado real: liga-se e desliga-se pelo braco.
    down = False

    def _alt_is_down(self):
        return bool(self.down)

    def measure_hold(self):  # substituido pelo corpo real quando ha namespace
        return 0.0


def verdict(name: str) -> int:
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print(f"FALHA: {label}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={total} pass={passed} fail={failed} (rc={EXIT_PASS if not failed else EXIT_FAIL})")
    return EXIT_PASS if not failed else EXIT_FAIL


def run(gesture_path: Path, shell_path: Path) -> int:
    for path in (gesture_path, shell_path):
        if not path.exists():
            print(f"VERDICT: FAIL -- {path} ausente")
            return EXIT_FAIL
    gesture = load_gesture(gesture_path)
    # `hotkey_settings` AO LADO do gesto (2026-10-30): o numero de fabrica e a
    # lista que o painel oferece tem de ser lidos do MESMO sitio que a app le',
    # senao um braco aqui pode concordar com um ficheiro que o shell ignora.
    if str(gesture_path.parent) not in sys.path:
        sys.path.insert(0, str(gesture_path.parent))
    import hotkey_settings
    source = shell_path.read_text(encoding="utf-8")

    # -- estrutura ---------------------------------------------------------
    print("ARM 1 -- estrutura: a maquina dos dois relogios NAO voltou")
    tree = ast.parse(source)
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == "SottoShell"), None)
    names = {n.name for n in (cls.body if cls else []) if isinstance(n, ast.FunctionDef)}
    add("hotkey_pressed" in names and "hotkey_hold" in names,
        "o shell tem hotkey_pressed E hotkey_hold")
    for dead in ("_hotkey_single", "_hotkey_double", "_undo_gesture_caption"):
        add(dead not in names, f"{dead} (o contrato de 2026-10-18) foi REMOVIDO")
    # Atribuicao e nao substring: os nomes aparecem nos comentarios que explicam
    # porque sairam, e um oraculo que se deixa enganar por um comentario nao ve
    # codigo nenhum.
    live_assign = re.findall(
        r"^(HOTKEY_CAPTION_DEFER_MS|HOTKEY_GESTURE_MS)\s*=", source, re.M)
    add(not live_assign,
        "o shell ja' nao DEFINE HOTKEY_CAPTION_DEFER_MS nem HOTKEY_GESTURE_MS",
        str(live_assign) or "nenhuma atribuicao")

    # -- um so' dono para os numeros --------------------------------------
    print("\nARM 2 -- o numero do gesto vive em hotkey_gesture.py e em mais lado nenhum")
    # O NUMERO DE FABRICA NAO SE RE-PINA (2026-10-30, SEGUNDA VEZ NO MESMO DIA).
    # Este braco exigia `HOTKEY_HOLD_MS == 500`, e 500 era o defeito: medido na
    # mao do dono (21 pressoes), 531/578/641 ms viravam HOLD e comutavam a
    # legenda quando ele queria o painel. O vazio entre o toque mais lento (641)
    # e a segura mais rapida (1187) e' onde o limiar tem de viver; o valor passou
    # a 900. O que este braco guarda agora e' a PROPRIEDADE, nao o numero:
    # o limiar tem de estar ACIMA do toque mais lento medido e ABAIXO da segura
    # mais rapida medida. Um re-pin de 500 para 900 (ou de 900 para o que venha)
    # passaria a esconder exactamente o erro que ele apanhou.
    # 2026-10-30, TERCEIRA vez no mesmo dia: o dono ESCOLHEU o numero, por ordem
    # directa -- *"a porra do alt c, bota 200ms"*. Uma escolha dele SUBSTITUI a
    # medicao: o vazio 641..1187 deixou de ser a regra, e exigir esse vazio era
    # re-pinar contra o dono. O que continua a valer, e por isso e' o que estes
    # bracos guardam: (a) o numero vive NUM sitio e a lista do painel concorda com
    # ele; (b) pedir exactamente esse valor nao e' aproximado para outro; (c) a
    # CONSEQUENCIA esta' medida -- com 200 ms o toque mais lento que ele deu
    # (641 ms) PASSA a ser HOLD.
    add(gesture.HOTKEY_HOLD_MS in hotkey_settings.HOTKEY_HOLD_MS_CHOICES,
        "o valor de fabrica esta' na lista que o painel oferece",
        f"{gesture.HOTKEY_HOLD_MS} em {hotkey_settings.HOTKEY_HOLD_MS_CHOICES}")
    add(hotkey_settings.clamp_hold_ms(gesture.HOTKEY_HOLD_MS) == gesture.HOTKEY_HOLD_MS,
        "pedir exactamente esse valor nao e' aproximado para outro",
        f"clamp={hotkey_settings.clamp_hold_ms(gesture.HOTKEY_HOLD_MS)}")
    add(gesture.is_hold(_TAP_LENTO_MS) is True,
        "com o limiar ESCOLHIDO o toque mais lento medido dele ja' e' HOLD",
        "hold=%.0f toque_lento=%.0f" % (gesture.HOTKEY_HOLD_MS, _TAP_LENTO_MS))
    add(gesture.HOTKEY_TAP_WINDOW_MS == 400.0, "HOTKEY_TAP_WINDOW_MS = 400",
        f"{gesture.HOTKEY_TAP_WINDOW_MS}")
    add(gesture.HOLD_CEILING_MS >= gesture.HOTKEY_HOLD_MS,
        "o tecto da medicao nao e' menor que o limiar do HOLD",
        f"ceiling={gesture.HOLD_CEILING_MS} hold={gesture.HOTKEY_HOLD_MS}")
    helper = "def hotkey_numbers()" in source and "hotkey_gesture" in source
    add(helper, "o shell le os numeros por hotkey_numbers() e nao os redefine")
    add(not any(f"HOTKEY_HOLD_MS = {int(gesture.HOTKEY_HOLD_MS)}" in source
                for _ in [0]),
        "o shell NAO tem uma segunda copia de HOTKEY_HOLD_MS")

    # -- a regra pura ------------------------------------------------------
    print("\nARM 3 -- a regra pura")
    add(gesture.resolve_taps(1) == "strip", "1 toque -> strip")
    add(gesture.resolve_taps(2) == "side", "2 toques -> side")
    add(gesture.resolve_taps(3) == "side", "3 toques -> side (sem quarto estado inventado)")
    # RE-ANCORADO 2026-10-30 (a ordem de 200 ms): o braco guarda a FRONTEIRA, nao
    # um gosto -- abaixo do numero em vigor e' toque, a partir dele e' HOLD.
    add(gesture.is_hold(gesture.HOTKEY_HOLD_MS - 1) is False,
        "abaixo do limiar em vigor e' TOQUE", f"{gesture.HOTKEY_HOLD_MS - 1} ms")
    add(gesture.is_hold(gesture.HOTKEY_HOLD_MS) is True,
        "exactamente no limiar ja' e' HOLD", f"{gesture.HOTKEY_HOLD_MS} ms")
    add(gesture.is_hold(_TAP_LENTO_MS) is True,
        "o toque mais lento MEDIDO (641 ms) cai acima do limiar escolhido",
        f"{_TAP_LENTO_MS} ms")
    add(gesture.is_hold(_SEGURA_RAPIDA_MS) is True,
        "a segura mais rapida MEDIDA e' HOLD", f"{_SEGURA_RAPIDA_MS} ms")
    add(gesture.is_hold(gesture.HOTKEY_HOLD_MS) is True,
        "o proprio limiar ja' e' HOLD (a comparacao e' >=, nao >)",
        f"{gesture.HOTKEY_HOLD_MS}")
    add(gesture.is_hold(None) is False, "duracao desconhecida NAO vira HOLD")

    # -- o CICLO dos paineis (ordem do dono, 2026-10-30) -------------------
    print("\nARM 3-bis -- o ciclo nada -> primeiro -> segundo -> nada")
    add(gesture.next_surface(False, "") == "strip",
        "nada no ecra -> painel de BAIXO", str(gesture.next_surface(False, "")))
    add(gesture.next_surface(True, "strip") == "panel",
        "painel de baixo -> painel da DIREITA", str(gesture.next_surface(True, "strip")))
    add(gesture.next_surface(True, "panel") is None,
        "painel da direita -> FECHA (None)", str(gesture.next_surface(True, "panel")))
    # Superficie DESCONHECIDA com a janela visivel avanca para o FECHO: adivinhar
    # "painel de baixo" ali deixaria o dono a olhar para o mesmo painel com a
    # tecla a nao fazer nada, que e' a queixa que este ciclo veio resolver.
    add(gesture.next_surface(True, "") is None,
        "janela visivel com superficie desconhecida -> FECHA",
        str(gesture.next_surface(True, "")))
    add(len({gesture.next_surface(False, ""), gesture.next_surface(True, "strip"),
             gesture.next_surface(True, "panel")}) == 3,
        "os tres estados do ciclo sao DISTINTOS (nao ha dois iguais)")
    # A regra tem de ser a UNICA fonte: o `resolve_taps` antigo devolve
    # 'side' para 2+ e nao conhece o fecho; se o resolver do shell voltasse a
    # chama-lo, o ciclo acima nao seria usado por ninguem.
    src_resolver = source[source.find("def _hotkey_resolve"):] if "_hotkey_resolve" in source else ""
    src_resolver = src_resolver[:src_resolver.find("\n    def ", 10)] if src_resolver else ""
    add("next_surface" in src_resolver and "resolve_taps" not in src_resolver,
        "o resolver do shell chama next_surface e JA' NAO chama resolve_taps",
        f"next_surface={'next_surface' in src_resolver} "
        f"resolve_taps={'resolve_taps' in src_resolver}")

    # -- o despacho do shell ----------------------------------------------
    print("\nARM 4 -- o despacho, executado do proprio ficheiro")
    ns = build_shell(source, gesture)
    if ns is None:
        add(False, "os tres metodos do shell foram extraidos")
        return verdict("ALTC-GESTURE")
    add(True, "os tres metodos do shell foram extraidos")

    # 4.1 -- UM toque mostra o painel de BAIXO e nao toca na legenda.
    shell = FakeShell(bound=ns['_bind'])
    FakeTimer.pending.clear()
    drive(ns, shell, taps=1, gap_ms=0)
    # CONTRATO DE 2026-10-30 (ordem do dono, verbatim: *"alt segurado e c
    # multiplas vezes devem continuar mostrando os paineis e alternando entra
    # mostrar nada, mostrar o primeiro, mostrar o segundo"*): cada pressao
    # AVANCA um estado do ciclo. A razxao mudou com a regra (`hotkey-cycle-*`).
    add(shell.shown == [("strip", "hotkey-cycle-strip")],
        "UM toque (nada no ecra) -> painel de baixo", str(shell.shown))
    add(shell.live_calls == [], "UM toque NAO mexe na legenda", str(shell.live_calls))

    # 4.2 -- DOIS toques dentro da janela: UM painel so', o da DIREITA.
    shell = FakeShell(bound=ns['_bind'])
    FakeTimer.pending.clear()
    drive(ns, shell, taps=2, gap_ms=120)
    # CONTRATO NOVO (ordem do dono, 2026-10-30: *"tem um delay DO CARALHO pra
    # aparecer os painels ao apertar alt c"*). O PRIMEIRO toque age no acto, e o
    # segundo PROMOVE a mesma janela. A faixa por 120 ms e' o preco; antes o
    # preco era 400 ms de nada e o painel so' no fim. Re-pinar `[("side", ...)]`
    # aqui voltaria a exigir o adiamento que ele mandou tirar.
    # DOIS toques = DOIS passos do ciclo: nada -> baixo -> direita. Coincide com
    # o contrato antigo (2 toques = direita) por construcao, nao por sorte.
    add(shell.shown == [("strip", "hotkey-cycle-strip"), ("side", "hotkey-cycle-side")],
        "DOIS toques -> baixo e depois direita (dois passos do ciclo)", str(shell.shown))
    add(shell.live_calls == [], "DOIS toques NAO mexem na legenda", str(shell.live_calls))

    # 4.3 -- DOIS toques FORA da janela sao dois gestos: dois paineis de baixo.
    shell = FakeShell(bound=ns['_bind'])
    FakeTimer.pending.clear()
    for press in range(2):
        ns["hotkey_pressed"](shell)
        ns["time"].advance_ms(gesture.HOTKEY_TAP_WINDOW_MS + 50)
        for timer in list(FakeTimer.pending):
            FakeTimer.pending.remove(timer)
            timer.fn()
    # CONTRATO NOVO: o SEGUNDO gesto de um toque encontra a faixa no ecra, e um
    # toque no MESMO painel FECHA (queixa de 2026-10-30). Antes este braco exigia
    # dois `show_strip`; isso so' passava porque nada fechava nunca.
    # FORA da janela continua a ser dois gestos, mas o ciclo nao reinicia: o
    # segundo encontra a faixa no ecra e avanca para a DIREITA. Fechar no segundo
    # toque era o contrato antigo ("o mesmo painel fecha") e contradizia o de
    # hoje: com ele, `nada -> baixo -> nada -> baixo` e o painel da direita so'
    # aparecia por acidente.
    add(shell.shown == [("strip", "hotkey-cycle-strip"), ("side", "hotkey-cycle-side")]
        and shell.hidden == [], "dois toques separados: baixo e depois direita",
        f"shown={shell.shown} hidden={shell.hidden}")

    # 4.3-bis -- O TOQUE NAO ESPERA NADA. Medido 2026-10-30 no log do dono:
    # pressao -> `PANEL_SHOWN` = 460 ms, dos quais 8 ms de trabalho real; o resto
    # era `HOTKEY_TAP_WINDOW_MS`. Este braco exige que a accao ja' tenha
    # acontecido SAINDO de `hotkey_pressed`, sem avançar o relogio e sem correr
    # um unico Timer: e' a unica forma de provar que o adiamento morreu.
    shell = FakeShell(bound=ns['_bind'])
    FakeTimer.pending.clear()
    ns["hotkey_pressed"](shell)
    add(shell.shown == [("strip", "hotkey-cycle-strip")],
        "o primeiro toque mostra o painel SEM esperar a janela", str(shell.shown))
    add(len(FakeTimer.pending) >= 1,
        "a janela continua a ser REARMADA por um timer (para a contagem nao somar)")
    for timer in list(FakeTimer.pending):
        FakeTimer.pending.remove(timer)
        timer.fn()
    fresh = FakeShell(bound=ns['_bind'])
    ns["hotkey_pressed"](fresh)
    # Se o `_hotkey_forget` nao tivesse corrido, a contagem seria 2 e este toque
    # abriria o painel da DIREITA. A faixa e' portanto a prova do rearme.
    # O `fresh` nasce SEM estado de ecra (o fake nao herda o `surface_applied` do
    # anterior), logo o ciclo parte de NADA e o passo e' a faixa. O caso "a faixa
    # ja' esta' e o passo e' a direita" tem o seu proprio braco em 4.5.
    add(fresh.shown == [("strip", "hotkey-cycle-strip")],
        "passada a janela, o toque seguinte e' OUTRO gesto que comeca do NADA",
        str(fresh.shown))

    # 4.4 -- HOLD: a legenda liga, e NENHUM painel aparece.
    shell = FakeShell(caption_on=False, bound=ns['_bind'])
    FakeTimer.pending.clear()
    ns["hotkey_hold"](shell)
    add(shell.live_calls == [{"on": True}], "HOLD liga a legenda", str(shell.live_calls))
    add(shell.shown == [], "HOLD NAO mostra painel nenhum", str(shell.shown))
    ns["hotkey_hold"](shell)
    add(shell.live_calls[-1] == {"on": False}, "HOLD outra vez desliga a legenda",
        str(shell.live_calls))

    # 4.5 -- ALT+C DE NOVO FECHA (queixa dele, verbatim: *"POR QUE APERTAR ALT C
    # DE NOVO NAO FECHA O PAINEL ATUAL?"*). O mesmo painel no ecra -> esconde.
    shell = FakeShell(bound=ns['_bind'], visible=True, surface='strip')
    FakeTimer.pending.clear()
    drive(ns, shell, taps=1, gap_ms=0)
    add(shell.hidden == [] and shell.shown == [("side", "hotkey-cycle-side")],
        "toque com a faixa no ecra -> proximo passo: painel da DIREITA",
        f"hidden={shell.hidden} shown={shell.shown}")

    # 4.6 -- ... mas o painel da DIREITA pedido por um toque TROCA para a faixa
    # em vez de fechar: fechar e reabrir seria um piscar que ele nao pediu.
    shell = FakeShell(bound=ns['_bind'], visible=True, surface='side')
    FakeTimer.pending.clear()
    drive(ns, shell, taps=1, gap_ms=0)
    add(shell.hidden == ['hotkey-toggle'] and shell.shown == [],
        "toque com o painel da DIREITA no ecra -> fecha (o ciclo volta a NADA)",
        f"hidden={shell.hidden} shown={shell.shown}")

    # -- o thread da hotkey ------------------------------------------------
    print("\nARM 5 -- o thread: a DURACAO decide o gesto (nao o contador de presses)")
    tns = build_thread(source, gesture)
    if tns is None:
        add(False, "_on_press, _tick e _finish_measure extraidos")
        return verdict("ALTC-GESTURE")
    add(True, "_on_press, _tick e _finish_measure extraidos")

    def bound(thread):
        thread._tick = lambda: tns["_tick"](thread)
        thread._finish_measure = lambda held, reason='release': tns[
            "_finish_measure"](thread, held, reason)
        thread._deliver_hold = lambda: tns["_deliver_hold"](thread)
        thread._threshold = lambda: tns["_threshold"](thread)
        return thread

    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 900.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (1, 0), "900 ms -> on_hold e nao on_hotkey",
        f"holds={thread.holds} taps={thread.taps}")
    add(any("held_ms=900" in line for line in thread.lines),
        "o log carrega held_ms (auditavel no log do dono)", str(thread.lines[-1:]))

    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 0.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (0, 1), "0 ms -> on_hotkey e nao on_hold",
        f"holds={thread.holds} taps={thread.taps}")

    # RE-ANCORADO 2026-10-30: com 200 ms em vigor, 499 ms e' HOLD e nao toque. O
    # braco mede a MESMA propriedade (o seam entrega o gesto pelo numero em vigor)
    # e passa a testar os dois lados da fronteira nova.
    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 199.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (0, 1), "199 ms e' um TOQUE (abaixo dos 200)",
        f"holds={thread.holds} taps={thread.taps}")

    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 499.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (1, 0),
        "499 ms e' HOLD ao limiar escolhido, nao toque",
        f"holds={thread.holds} taps={thread.taps}")

    # -- 2026-10-30: um HOLD NAO ENG OLE a pressao SEGUINTE -------------------
    # Ordem do dono, verbatim: *"alt segurado e c multiplas vezes devem continuar
    # mostrando os paineis"*. O `_hold_fired` que sobrava de um HOLD entregue tem
    # de ser limpo na pressao seguinte, senao a segunda pressao cai no `return`
    # do `_finish_measure` e o dono carrega em Alt+C sem nada acontecer.
    print("\nARM 5-ter -- a pressao a seguir a um HOLD continua a contar")
    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 499.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    thread.fake_hold_ms = 0.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (1, 1),
        "HOLD e depois um toque -> um de cada (a pressao nao foi engolida)",
        f"holds={thread.holds} taps={thread.taps}")

    # -- 2026-10-30: um `new-press` NAO pode inventar um HOLD --------------
    # Medido no log do dono: quatro toques seguidos, e o release perdido de um deles
    # fazia o intervalo PRESS-AO-PRESS (1,2 s) passar por uma segurada -- a legenda
    # comutava sozinha. O HOLD so' o `_tick` pode entregar, ao cruzar o limiar.
    print("\nARM 5-quater -- o release perdido conta como TOQUE, nunca como HOLD")
    thread = bound(FakeHotkeyThread())
    tns["_finish_measure"].__get__(thread, FakeHotkeyThread)(2000.0, 'new-press')
    add((thread.holds, thread.taps) == (0, 1),
        "2000 ms fechados por new-press -> TOQUE (o HOLD so' nasce no tick)",
        f"holds={thread.holds} taps={thread.taps}")
    add(any('HOTKEY_SWALLOWED_HOLD' in line for line in thread.lines),
        "o caso fica escrito no log (nao se perde em silencio)",
        str(thread.lines[-1:]))
    thread = bound(FakeHotkeyThread())
    tns["_finish_measure"].__get__(thread, FakeHotkeyThread)(2000.0, 'release')
    add((thread.holds, thread.taps) == (1, 0),
        "2000 ms fechados por release -> HOLD (o caminho legitimo continua)",
        f"holds={thread.holds} taps={thread.taps}")

    # -- 2026-10-30: o gesto acaba quando QUALQUER tecla sobe ---------------
    print("\nARM 5-quinquies -- a medicao le' o Alt E a tecla do hotkey")
    body = tns['source'] if 'source' in tns else None
    text = None
    import ast as _ast, inspect as _inspect
    try:
        tree = _ast.parse(open(os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'),
                               encoding='utf-8').read())
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef) and node.name == '_alt_is_down':
                text = _ast.get_source_segment(
                    open(os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'),
                         encoding='utf-8').read(), node)
    except Exception as exc:
        add(False, "o corpo de `_alt_is_down` foi lido", repr(exc))
    if text:
        add('VK_MENU' in text and 'self.vk' in text,
            "`_alt_is_down` exige as DUAS teclas (ler so' o Alt deixava um toque virar HOLD)",
            text.splitlines()[-4:])

    # -- ORDEM DO DONO (2026-10-30): o HOLD dispara AO CRUZAR o limiar ------
    # Palavras dele, verbatim: *"assim que o alt c é segurado suficiente, da
    # display ou tira display da legenda. nao é pra esperar o release da tecla"*.
    print("\nARM 5-bis -- o HOLD entrega no LIMIAR, com a tecla AINDA em baixo")
    clock = tns["time"]
    box = tns["_thresholdbox"]
    box["hold_ms"] = 300.0
    thread = bound(FakeHotkeyThread())
    thread.down = True
    clock.now = 1000.0
    tns["_on_press"](thread)
    add((thread.holds, thread.taps) == (0, 0),
        "a pressao so' ABRE a medicao -- nao entrega nada", f"holds={thread.holds}")
    clock.advance_ms(290)
    tns["_tick"](thread)
    add(thread.holds == 0, "290 ms < 300 ms: ainda nada", f"holds={thread.holds}")
    clock.advance_ms(20)
    tns["_tick"](thread)
    add(thread.holds == 1 and thread.taps == 0,
        "310 ms >= 300 ms: o HOLD disparou SEM release",
        f"holds={thread.holds} taps={thread.taps}")
    add(any("key_still_down=true" in line for line in thread.lines),
        "o log prova que a tecla estava em baixo no disparo", str(thread.lines[-2:]))
    # ... e o RELEASE que vem depois NAO e' um segundo gesto.
    thread.down = False
    clock.advance_ms(10)
    tns["_tick"](thread)
    add(thread.taps == 0,
        "o release DEPOIS do hold nao vira toque (o mesmo Alt+C nao e' legenda E painel)",
        f"taps={thread.taps}")
    add(any("reason=release" in line for line in thread.lines),
        "o release fica registado com a duracao", str(thread.lines[-1:]))

    # -- ORDEM DO DONO (2026-10-30): segurar NAO bloqueia os comandos ------
    # Palavras dele, verbatim: *"eu apertar alt c e nao deixar alt c ir embora
    # (manter apertado) deve mexer normalmente nos comandos, inves de impedir
    # proximos comandos"*. A medicao antiga vivia dentro de `_on_press`, num
    # `while` que prendia o pump ate' 5 s: nenhum `WM_HOTKEY` novo era entregue
    # nesse tempo. ESTRUTURA e nao comportamento: nenhum dos corpos pode ter um
    # laco, nem dormir.
    print("\nARM 5-ter -- a medicao nao tem laco nenhum (o pump nunca fica preso)")
    for name in ("_on_press", "_tick", "_finish_measure"):
        body = class_methods(source, "HotkeyThread", (name,)).get(name) or ""
        tree_b = ast.parse(body).body[0]
        loops = [n for n in ast.walk(tree_b) if isinstance(n, (ast.While, ast.For))]
        add(not loops, name + " nao tem 'While' nem 'For' (um laco aqui prende o pump)")
        calls = [n.func.id for n in ast.walk(tree_b)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        add("sleep" not in calls, f"{name} nao dorme")

    # -- o limiar configuravel (F2) ----------------------------------------
    print("\nARM 6 -- o limiar do HOLD e' do DONO, e a thread respeita-o")
    box = tns["_thresholdbox"]
    box["hold_ms"] = 700.0
    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 600.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (0, 1),
        "limiar 700 ms: 600 ms ainda e' TOQUE", f"holds={thread.holds} taps={thread.taps}")
    box["hold_ms"] = 300.0
    thread = bound(FakeHotkeyThread())
    thread.fake_hold_ms = 600.0
    tns["_on_press"].__get__(thread, FakeHotkeyThread)()
    add((thread.holds, thread.taps) == (1, 0),
        "limiar 300 ms: os MESMOS 600 ms ja' sao HOLD", f"holds={thread.holds} taps={thread.taps}")

    # A escolha tem de SOBREVIVER a um restart: vive em disco, nao em memoria.
    settings_path = ROOT / "app" / "webview" / "hotkey_settings.py"
    add(settings_path.exists(), "hotkey_settings.py existe (o limiar vive em disco)")
    if settings_path.exists():
        spec = _ilu.spec_from_file_location(
            "hotkey_settings_probe", str(settings_path))
        sys.path.insert(0, str(ROOT / "app" / "webview"))
        settings = _ilu.module_from_spec(spec)
        spec.loader.exec_module(settings)
        tmp_file = Path(tempfile.mkdtemp(prefix="altc-cfg-")) / "hotkey-settings.json"
        add(settings.hold_ms(tmp_file) == float(gesture.HOTKEY_HOLD_MS),
            "sem ficheiro o limiar e' o de FABRICA", f"{settings.hold_ms(tmp_file)}")
        add(settings.write({"holdMs": 900}, tmp_file).get("ok") is True,
            "a escolha grava-se")
        add(settings.hold_ms(tmp_file) == 900.0,
            "a escolha le'-se de volta", f"{settings.hold_ms(tmp_file)}")
        add(settings.write({"holdMs": "lixo"}, tmp_file).get("ok") is False,
            "um valor que nao e' numero e' RECUSADO")
        add(settings.hold_ms(tmp_file) == 900.0,
            "a recusa NAO apaga a escolha anterior", f"{settings.hold_ms(tmp_file)}")
        add(settings.clamp_hold_ms(620) == 700,
            "620 ms cai na escolha mais proxima", f"{settings.clamp_hold_ms(620)}")
        add(settings.clamp_hold_ms(None) is None, "None nao vira escolha")
        tmp_file.write_text("{ nao e' json", encoding="utf-8")
        add(settings.hold_ms(tmp_file) == float(gesture.HOTKEY_HOLD_MS),
            "um ficheiro estragado volta a FABRICA (o Alt+C nao fica surdo)",
            f"{settings.hold_ms(tmp_file)}")
        shutil.rmtree(tmp_file.parent, ignore_errors=True)

    # A pagina pergunta a LISTA e nao a inventa.
    add("_get_hotkey_hold" in names and "_set_hotkey_hold" in names,
        "o shell expoe get/set do limiar ao painel")
    add("'setHotkeyHold'" in source and "'getHotkeyHold'" in source,
        "as duas entradas estao na tabela da API do pywebview")
    page = js_code((ROOT / "app" / "panel" / "panel.js").read_text(encoding="utf-8"))
    add("bridge.getHotkeyHold" in page,
        "panel.js PERGUNTA a lista ao shell (nao tem copia de HOTKEY_HOLD_MS_CHOICES)")
    add("HOTKEY_HOLD_MS_CHOICES" not in page,
        "panel.js nao carrega a lista de escolhas")

    # -- a legenda e SO' DISPLAY -------------------------------------------
    print("\nARM 6 -- a legenda desligada e' so' DISPLAY (ordem do dono)")
    # CODIGO e nao texto: a docstring de `hotkey_hold` NOMEIA `_pause_shell` so'
    # para dizer que nao lhe toca, e um oraculo que leia comentarios castiga quem
    # documenta a regra.
    hold_src = code_only(source, "SottoShell", "hotkey_hold")
    for forbidden in ("_pause_shell", "_resume_shell", "reload", "restart",
                      "show_strip", "show_side", "show_panel", "hide_panel"):
        add(forbidden not in hold_src,
            f"hotkey_hold NAO chama {forbidden} (nao descarrega motor nem mexe em painel)")

    # -- F3: desligar a legenda e' SO' DISPLAY, provado a CORRER ------------
    print("\nARM 7 -- `_set_live_enabled` executado: a UNICA saida e' a janela")
    live_src = class_methods(source, "SottoShell", ("_set_live_enabled",)).get(
        "_set_live_enabled", "")
    # A varredura dos nomes proibidos le' CODIGO: a docstring desta funcao conta
    # a historia do `hide_panel` que saiu, e castigar essa historia seria castigar
    # a unica prova de porque a linha nao esta' la'.
    live_code = code_only(source, "SottoShell", "_set_live_enabled")
    add(bool(live_src), "_set_live_enabled extraido do ficheiro")
    if live_src:
        lns = {"log": FakeLog()}
        exec(compile(ast.Module(body=[ast.parse(live_src).body[0]], type_ignores=[]),
                     "<set-live>", "exec"), lns)

        class WatchedShell:
            """Qualquer atributo tocado fora da lista e' registado e REPROVADO."""

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
        for forbidden in ("_pause_shell", "_reload_worker", "_restart_worker",
                          "hide_panel", "show_panel", "worker", "history"):
            add(forbidden not in live_code,
                f"_set_live_enabled NAO nomeia {forbidden}")

    return verdict("ALTC-GESTURE")


def neg_arm() -> int:
    """Muta uma COPIA do gesto e exige que o oraculo fique VERMELHO.

    A mutacao e' a REGRESSAO que o dono reportou: `resolve_taps` a devolver
    sempre `'strip'`, ou seja, DOIS toques a darem o painel de baixo -- o
    painel da direita nunca aparece.
    """
    tmp = Path(tempfile.mkdtemp(prefix="altc-neg-"))
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True)
        shutil.copy2(GESTURE, copy / "hotkey_gesture.py")
        shutil.copy2(SHELL, copy / "sotto_webview.py")
        # O UTFIMO QUE LE' O NUMERO (2026-10-30): sem esta copia o braco 2 importa
        # o `hotkey_settings` da ARVORE VIVA e mede outro ficheiro que nao o mutado.
        shutil.copy2(GESTURE.parent / "hotkey_settings.py", copy / "hotkey_settings.py")
        target = copy / "hotkey_gesture.py"
        text = target.read_text(encoding="utf-8")
        mutant = text.replace("return 'side' if n >= 2 else 'strip'",
                              "return 'strip'")
        if mutant == text:
            print("NEG-ARM: nao consegui mutar o alvo (o texto mudou)")
            return EXIT_FAIL
        target.write_text(mutant, encoding="utf-8")
        print("NEG-ARM: resolve_taps sempre 'strip' (o painel da direita nunca aparece)")
        rc = run(copy / "hotkey_gesture.py", copy / "sotto_webview.py")
        # O `:expectred` da bateria exige rc != 0 no passo negativo e a string
        # `NEG-ARM PASS` no log -- as duas coisas. Devolver 0 aqui fez o passo
        # `red-as-expected-altc-gesture` ficar VERMELHO na primeira corrida
        # (medido 2026-10-30, bateria `steps=148`), por o oraculo certo estar a
        # dizer o resultado pelo codigo errado.
        if rc == EXIT_FAIL:
            print("\nNEG-ARM PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM FAIL -- o oraculo NAO ve a regressao")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv) -> int:
    if "--neg-arm" in argv:
        return neg_arm()
    return run(GESTURE, SHELL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
