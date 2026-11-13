#!/usr/bin/env python
# NO-BUG: instrumento do PRAZO do ack de desligar (2026-11-12); nao corrige o
# produto, julga-o. Nada aqui abre janela, browser, audio nem input.
"""O "legenda ao vivo: desligada" SAI AO MEIO SEGUNDO -- e so' entao.

O DONO, verbatim: *"'legenda ao vivo: desligada' deve aparecer por meio segundo
apenas, e sumir."*

MEDIDO no log dele (pid 46056), antes desta correcao:

    19:29:59.928  CAPTION_STATUS_SHOWN reason=off ms=4 text="legenda ao vivo: desligada"
    19:30:05.9    <- nenhuma linha de retirada; o texto saiu ~6 s depois, pelo
                     temporizador de SILENCIO (`CAPTION_IDLE_HIDE_S = 6.0`)

A CAUSA, e o que NAO se fez: o ack era apagado por `_arm_caption_idle_hide`,
o mesmo temporizador que esconde uma LEGENDA verdadeira (`push_caption_to_window`
arma-o nas duas vias, player e ASR). Encolher `CAPTION_IDLE_HIDE_S` para 0,5 s
teria apagado a linha do player meio segundo depois de o player parar de a
mudar -- o oposto do 1:1 que ele pediu na mesma sessao. O ack ganhou prazo
proprio (`CAPTION_STATUS_HIDE_S = 0.5`, `_arm_caption_status_hide`).

O QUE ESTE ORACULO JULGA (4 arms, com o codigo REAL extraido por `ast`):

  A1 meio-segundo      -- `CAPTION_STATUS_HIDE_S` = 0,5 e MENOR que o do silencio.
  A2 nem-antes         -- a 0,30 s o texto AINDA esta' no ecra e o overlay esta'
                          visivel; a 0,90 s ja' saiu, e o log traz o numero
                          (`CAPTION_STATUS_HIDDEN after_s=0.5 ms=..`).
  A3 o-silencio-intacto-- o MESMO temporizador que apaga o ack NAO e' o que a
                          fala arma: com `_caption_status_reason` vazio (uma
                          legenda verdadeira no ecra) o disparo do ack nao
                          apaga nada.
  A4 uma-vez-por-episodio-- duas retiradas seguidas nao escrevem duas linhas
                          (um log que grita duas vezes pela mesma coisa nao e'
                          um instrumento).

`--neg-arm` muta uma COPIA do shell no disco: poe `CAPTION_STATUS_HIDE_S = 6.0`
(o valor antigo) e exige que A1 fique RED; e poe `_caption_status_hide` a
apagar sem olhar a razao e exige que A3 fique RED. rc=1 = todos apanhados
(`NEG-ARM: PASS -- k/k`), rc=0 = algum mutante INERTE.

    python _main\\caption-status-hide-oracle.py
    python _main\\caption-status-hide-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(APP, "sotto_webview.py")

if APP not in sys.path:
    sys.path.insert(0, APP)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _astcache import tree as _tree_of  # noqa: E402

#: O prazo que o dono pediu, e a folga do instrumento (relogio de parede de um
#: `threading.Timer` nesta maquina: medido 0-4 ms de atraso no disparo).
ACK_S = 0.5
EARLY_S = 0.30          # antes disto o texto TEM de estar no ecra
LATE_S = 0.90           # depois disto TEM de ter saido
TOL_MS = 250            # o `ms=` do log contra o prazo nominal

CLASS_METHODS = (
    "_arm_caption_status_hide",
    "_caption_status_hide",
    "_caption_off_ack",
    "_arm_caption_idle_hide",
    "_caption_idle_disarm",
)


def read_source(path=None):
    with io.open(path or SHELL, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _klass(src, where="<shell>"):
    tree = _tree_of(src, where)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SottoShell":
            return node
    raise SystemExit("EXTRACT-FAIL: SottoShell not found in %s" % where)


def extract(src, where="<shell>"):
    klass = _klass(src, where)
    methods = {}
    consts = []
    for item in klass.body:
        if isinstance(item, ast.FunctionDef):
            methods[item.name] = item
        elif isinstance(item, ast.Assign):
            names = [t.id for t in item.targets if isinstance(t, ast.Name)]
            if "CAPTION_STATUS_HIDE_S" in names or "CAPTION_IDLE_HIDE_S" in names:
                consts.append(item)
    missing = [m for m in CLASS_METHODS if m not in methods]
    if missing:
        raise SystemExit("EXTRACT-FAIL: missing %s in %s" % (missing, where))
    return methods, consts


def _literal_consts(tree):
    """As constantes de MODULO que o corpo compilado le', e so' as literais.

    O `_caption_off_ack` arrasta nomes do modulo (`UI_MARSHAL_TIMEOUT_S` e
    companhia) que nao sao regra nenhuma: sao numeros. Compilar so' as duas
    constantes da classe dava `NameError` -- medido, 0/4 arms. Ficam as
    atribuicoes cujo lado direito e' LITERAL: uma que chame `ctypes.WinDLL`
    faria o oraculo carregar Win32 para julgar um prazo.
    """
    out = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names:
            continue
        try:
            ast.literal_eval(node.value)
        except (ValueError, SyntaxError, TypeError):
            continue
        out.append(node)
    return out


_LOG = []


def build(src, where="<shell>", log=None):
    """A classe minima: so' os metodos e as constantes que o caminho conduz."""
    methods, consts = extract(src, where)
    tree = _tree_of(src, where)
    body = consts + [methods[name] for name in CLASS_METHODS]
    klass = ast.ClassDef(name="SottoShell", bases=[], keywords=[], body=body,
                         decorator_list=[], type_params=[])
    module = ast.Module(body=_literal_consts(tree) + [klass], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"time": time, "threading": __import__("threading"),
          "log": (log if log is not None
                  else (lambda msg, *_a, **_k: _LOG.append(str(msg)))),
          "json": __import__("json")}
    exec(compile(module, where, "exec"), ns)  # noqa: S102 -- codigo do repo
    return ns


class Overlay:
    """A janela do overlay: so' o que o caminho do ack toca."""

    def __init__(self):
        self.visible = False
        self.text = ""
        self.calls = []

    def set_work_area(self, *_a, **_k):
        return True

    def set_text(self, text, previous="", instant=False, **_k):
        self.text = str(text or "")
        self.calls.append(("set_text", self.text, bool(instant)))

    def show(self, on):
        self.visible = bool(on)
        self.calls.append(("show", self.visible))
        return True

    def hide(self):
        self.text = ""
        self.calls.append(("hide",))

    def wait_calls(self, n, timeout=1.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if len(self.calls) >= n:
                return True
            time.sleep(0.005)
        return len(self.calls) >= n


def make(src, where="<shell>"):
    ns = build(src, where)
    shell = ns["SottoShell"]()
    return shell, ns


class _Shell:
    """O caminho REAL do ack, com as costuras de ambiente ligadas a mao.

    As costuras sao de AMBIENTE (a fila do `_post`, o overlay, o log), nao da
    regra: `_post` corre ja', que e' o que a fila de pintura faz, e o log fica
    numa lista para as arms lerem o NUMERO que a producao escreve.
    """

    def __init__(self, src, where="<shell>"):
        self.lines = []
        self.ns = build(src, where,
                        log=lambda msg, *_a, **_k: self.lines.append(str(msg)))
        base = self.ns["SottoShell"]
        self.ov = Overlay()
        self.lines = []
        shell = self

        class Harness(base):          # type: ignore[misc,valid-type]
            def __init__(inner):
                inner.caption_overlay = shell.ov
                inner._caption_wanted = True
                inner._caption_window_shown = False
                inner._caption_status_reason = ""
                inner._caption_status_queued_for = ""
                inner._caption_status_episode_at = 0.0
                inner._caption_pending = None
                inner._caption_pending_status = False
                # `display` E' UM CAMPO, nao um metodo: na producao e' um dict
                # (`(self.display or {}).get('scaleFactor')`). Como metodo, o
                # `.get` caia em `CAPTION_STATUS_OFF_PAINT_FAILED` -- medido.
                inner.display = {"scaleFactor": 1.0}

            def _post(inner, fn):
                fn()
                return True

            def work_area(inner):
                return {"x": 0, "y": 0, "width": 1920, "height": 1080}

        self.shell = Harness()

    def log_lines(self):
        return list(self.lines)


def _patch_log(shell):
    """O `log` do modulo vai para a lista da arm (e' o unico observador)."""
    mod = sys.modules.get("sotto_webview")
    if mod is None:
        return None
    prev = getattr(mod, "log", None)
    mod.log = lambda msg, *a, **k: shell.lines.append(str(msg))
    return prev


# -- as arms ----------------------------------------------------------------

def arm_a1(src):
    """O prazo do ack e' 0,5 s e NAO e' o prazo do silencio."""
    ns = build(src)
    klass = ns["SottoShell"]
    ack = float(getattr(klass, "CAPTION_STATUS_HIDE_S"))
    idle = float(getattr(klass, "CAPTION_IDLE_HIDE_S"))
    ok = abs(ack - ACK_S) < 1e-6 and ack < idle
    return ok, "status_hide_s=%.2f idle_hide_s=%.2f" % (ack, idle)


def arm_a2(src):
    """A 0,30 s o texto AINDA la'; a 0,90 s ja' saiu -- e o `ms=` e' o medido."""
    h = _Shell(src)
    sh = h.shell
    t0 = time.monotonic()
    sh._caption_off_ack()
    if not h.ov.wait_calls(1, 0.3):
        return False, "nada pintado"
    while time.monotonic() - t0 < EARLY_S:
        time.sleep(0.005)
    early_visible = bool(h.ov.visible) and "desligada" in h.ov.text
    while time.monotonic() - t0 < LATE_S:
        if not h.ov.visible:
            break
        time.sleep(0.005)
    late_hidden = not h.ov.visible
    hidden = [l for l in h.lines if l.startswith("CAPTION_STATUS_HIDDEN ")]
    fields = dict(re.findall(r"(\w+)=(\S+)", hidden[0])) if hidden else {}
    ms = int(fields.get("ms", "-1")) if fields.get("ms", "").lstrip("-").isdigit() else -1
    ok = bool(early_visible and late_hidden and len(hidden) == 1
              and abs(ms - int(ACK_S * 1000)) <= TOL_MS)
    return ok, ("early_visible=%s late_hidden=%s lines=%d ms=%s"
                % (early_visible, late_hidden, len(hidden), ms))


def arm_a3(src):
    """Uma LEGENDA no ecra nao e' apagada pelo disparo do ack."""
    h = _Shell(src)
    sh = h.shell
    # Uma legenda verdadeira: o texto esta' la' mas a razao de estado esta' vazia.
    sh._caption_status_reason = ""
    sh._caption_window_shown = True
    h.ov.set_text("the ceiling.", "", True)
    h.ov.show(True)
    sh._caption_status_hide(int(getattr(sh, "_caption_status_hide_seq", 0) or 0), 0.0)
    kept = bool(h.ov.visible) and h.ov.text == "the ceiling."
    # E o ack VERDADEIRO, com a razao dele, apaga mesmo.
    h2 = _Shell(src)
    h2.shell._caption_off_ack()
    h2.ov.wait_calls(1, 0.3)
    h2.shell._caption_status_hide(
        int(getattr(h2.shell, "_caption_status_hide_seq", 0) or 0), 0.0)
    gone = not h2.ov.visible
    ok = bool(kept and gone)
    return ok, "legend_kept=%s ack_removed=%s" % (kept, gone)


def arm_a4(src):
    """Duas retiradas seguidas nao escrevem duas linhas (um episodio, uma linha)."""
    h = _Shell(src)
    sh = h.shell
    sh._caption_off_ack()
    h.ov.wait_calls(1, 0.3)
    seq = int(getattr(sh, "_caption_status_hide_seq", 0) or 0)
    sh._caption_status_hide(seq, time.time())
    sh._caption_status_hide(seq, time.time())
    lines = [l for l in h.lines if l.startswith("CAPTION_STATUS_HIDDEN ")]
    ok = len(lines) == 1
    return ok, "lines=%d" % len(lines)


ARMS = (
    ("A1 meio-segundo", arm_a1),
    ("A2 nem-antes", arm_a2),
    ("A3 o-silencio-intacto", arm_a3),
    ("A4 uma-vez-por-episodio", arm_a4),
)


# -- os mutantes ------------------------------------------------------------

def _mutants(src):
    """(nome, arm, texto mutado) -- cada um tem de deixar a SUA arm RED."""
    ack_old = "    CAPTION_STATUS_HIDE_S = 0.5"
    if ack_old not in src:
        raise SystemExit("MUTATION-FAIL: `CAPTION_STATUS_HIDE_S = 0.5` not found")
    yield ("M1 ack=6.0 (o valor antigo)", "A1 meio-segundo",
           src.replace(ack_old, "    CAPTION_STATUS_HIDE_S = 6.0", 1))
    guard = """            if str(getattr(self, '_caption_status_reason', '') or '') != 'off':
                return
"""
    if guard not in src:
        raise SystemExit("MUTATION-FAIL: the reason guard was not found")
    yield ("M2 sem-guarda-da-razao", "A3 o-silencio-intacto",
           src.replace(guard, "", 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true")
    ap.add_argument("--source", default=None)
    args = ap.parse_args(argv)

    src = read_source(args.source)
    if args.neg_arm:
        caught = 0
        total = 0
        fails = []
        for name, arm_name, mutated in _mutants(src):
            total += 1
            hit = False
            for label, fn in ARMS:
                if label != arm_name:
                    continue
                try:
                    ok, detail = fn(mutated)
                except Exception as exc:      # noqa: BLE001 -- mutante que parte conta
                    ok, detail = False, "raised %r" % (exc,)
                hit = not ok
                print("%s %s  antes=OK depois=%s %s"
                      % ("CAUGHT" if hit else "MISSED", name,
                         "RED" if hit else "still GREEN", detail))
            if hit:
                caught += 1
            else:
                fails.append(name)
        if caught == total:
            print("NEG-ARM: PASS -- %d/%d" % (caught, total))
            return 1
        print("NEG-ARM: FAIL -- %d/%d  inertes=%s" % (caught, total, fails))
        return 0

    good = 0
    for label, fn in ARMS:
        try:
            ok, detail = fn(src)
        except Exception as exc:              # noqa: BLE001
            ok, detail = False, "raised %r" % (exc,)
        print("%s %-24s %s" % ("PASS" if ok else "FAIL", label, detail))
        if ok:
            good += 1
    total = len(ARMS)
    print("\nVERDICT: %s (%d/%d)" % ("PASS" if good == total else "FAIL", good, total))
    return 0 if good == total else 1


if __name__ == "__main__":
    sys.exit(main())
