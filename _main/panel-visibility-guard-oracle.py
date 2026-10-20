#!/usr/bin/env python3
"""panel-visibility-guard-oracle -- is self.visible a CACHE or a LATCH?

AUDIT ROW #60, as filed: "_on_navigation_start early-returns on self.visible -> shown once, never
auto-hidden again". This oracle drives the REAL method with a fake self, in process, and asks the
question the row is really asking. The answer it measures is: self.visible is a MEASURED CACHE, not
a latch.

FOUR CASES, no launch:
  A. hidden + window mapped  -> `_on_navigation_start` must re-assert (sync AND posted) and the
     re-assert must actually HIDE the window;
  B. shown (visible=True)    -> it must NOT re-assert. That is the row reading a feature as a
     defect: while the owner has the panel on screen, a navigation must not take it away;
  C. the row cycle "shown once, then never again": shown -> the OWNER hides it (the real
     `hide_panel` re-measures the window, it does not assume) -> the next navigation RE-ASSERTS;
  D. the residual, named: visible=True STALE while the window is mapped -> the re-assert bails, so
     nothing hides. That is real, and it is why `toggle_panel` reads the window live and logs
     PANEL_VISIBILITY_CACHE_STALE, and why the navigation-time Show gate exists upstream.
  E. (added 2026-10-20) the contract of `hide_panel` AFTER the product changed on 2026-10-17:
     hiding the panel takes the CAPTION PIXELS away and leaves the owner's switch alone
     (`_blank_caption_window('panel-hidden')`, NOT `show_caption_window(False)`), because the
     caption is "a free overlay on my screen" and hiding a panel must not switch it off.

BOTH COLOURS. `--neg-arm` runs the same cases against a COPY of the shell with the guard in
`_reassert_hidden` removed: case D must FLIP (the mutant hides a panel the owner asked for) while
A, B, C and E stay put. A SECOND copy takes the caption-window blank out of `hide_panel` and case
E must FLIP; a THIRD cut strips the precision clause out of `run.cmd` and the promise check must
break. An arm that cannot tell the guard from the mechanism cannot report on it.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

#: Row #61: `run.cmd` used to promise a bare "start hidden". What is MEASURED is narrower, and
#: the file has to say which one it is -- so this phrase is both the promise and the marker this
#: oracle checks for, and its absence is what the neg-arm mutates away.
RUN_CMD = os.path.join(ROOT, "app", "webview", "run.cmd")
PRECISION = "not a promise about pixels"
#: The claim is the BEHAVIOUR (a hidden panel), not a literal phrase: what the row indicts is an
#: unqualified promise, so the check is "it says hidden AND it qualifies what was measured".
CLAIM = "hidden"

GUARD = "        if not hwnd or self.args.show or self.visible:"
GUARD_OFF = "        if not hwnd or self.args.show:"


#: The shell imports its SIBLING `hot_reload` (sotto_webview.py:54), so the directory the file
#: lives in has to be importable BEFORE exec_module -- the same thing the real launcher gets for
#: free by running from that directory.
def load_shell(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


#: Binds the REAL re-assert with the name the post records. A bare lambda would work as a call and
#: then record "<lambda>", so a check written against the name the product uses would fail for a
#: reason that has nothing to do with the product -- measured 2026-10-11, first run of this oracle:
#: cases A and C read False with the hide already recorded in both.
def bind_reassert(shell, probe):
    def _reassert_hidden():
        return shell._reassert_hidden(probe)
    return _reassert_hidden


class Probe:
    """The fake self: only what the driven methods actually touch."""

    def __init__(self, mod, shell, mapped, visible):
        self._shell = shell
        # `_on_navigation_start` and `_reassert_hidden` call EACH OTHER, so the fake self has to
        # carry the real re-assert (bound to itself) instead of a stub -- otherwise the arm would
        # measure its own stub, which proves nothing about the product.
        self._reassert_hidden = bind_reassert(shell, self)
        self.logs = []
        self.hides = []
        self.posts = []
        self.published = []
        self.caption_window_calls = []
        self.blank_caption_calls = []
        self.hwnd = 4242
        self.visible = visible
        self.args = SimpleNamespace(show=False)
        self.state = {"mapped": mapped}
        mod.window_visible = lambda hwnd: bool(self.state["mapped"]) if hwnd else False
        mod.hide_window = self._hide
        mod.log = self.logs.append

    def _hide(self, hwnd):
        self.hides.append(hwnd)
        self.state["mapped"] = False
        return True

    def _post(self, fn):
        self.posts.append(getattr(fn, "__name__", str(fn)))
        return True

    def publish_panel_visibility(self, reason):
        self.published.append(reason)

    def show_caption_window(self, on):
        """A JANELA DA LEGENDA, no stub.

        NOTA 2026-10-20: o `hide_panel` REAL JA NAO chama este metodo -- desde
        2026-10-17 ele chama `_blank_caption_window` (o stub de baixo). O stub
        fica porque e' o registo do mesmo interruptor, e porque um caminho que
        volte a LIGAR a legenda tem de ter onde registar a chamada.
        MEDIDO na bateria de 2026-10-16 (135/145, e este era UM DOS VERMELHOS):
        este stub foi acrescentado quando o oraculo morria com
        `AttributeError: 'Probe' object has no attribute 'show_caption_window'`.
        Registar a chamada e o que o oraculo precisa: o efeito e do shell, nao daqui."""
        self.caption_window_calls.append(on)
        return True

    def _blank_caption_window(self, reason):
        """A JANELA DA LEGENDA VAZIA, no stub -- o metodo que o `hide_panel` REAL chama.

        PRODUTO, 2026-10-17: ESCONDER O PAINEL JA NAO DESLIGA A LEGENDA. A frase do
        dono que a linha executava -- *"quando eu quero ou nao"* -- e' a do
        INTERRUPTOR, nao a do painel; a legenda e' *"um overlay, livre na minha
        tela"*, entao `hide_panel` tira os PIXELS (`_blank_caption_window`, que nao
        escreve `data-caption-window`) e nao toca no interruptor. No produto de
        hoje: `app/webview/sotto_webview.py:7726` `self._blank_caption_window
        ('panel-hidden')`, def em `:8597`.

        SEM ESTE STUB O ORACULO MORRE: `AttributeError: 'Probe' object has no
        attribute '_blank_caption_window'` -- medido na bateria de 2026-10-20. Era
        um CRASH do instrumento (que nao media nada), nao um vermelho de produto.
        O registo e' o mesmo do `show_caption_window`: o efeito e' do shell, nao
        daqui."""
        self.blank_caption_calls.append(reason)
        return True


def promise(text):
    """Row #61: is the launcher promise precise about what was MEASURED?"""
    return {
        "claims_start_hidden": CLAIM in text.lower(),
        "marks_precision": PRECISION in text,
        "cites_the_receipt": "receipt-20261007-panel-startup-flash" in text,
        "promise_precise": (CLAIM in text) and (PRECISION in text),
    }


def run_cases(mod):
    Shell = mod.SottoShell
    nav = lambda probe: Shell._on_navigation_start(probe, None, None)
    reassert = lambda probe: Shell._reassert_hidden(probe)
    hide = lambda probe, reason: Shell.hide_panel(probe, reason)

    # A -- hidden, window mapped.
    a = Probe(mod, Shell, mapped=True, visible=False)
    nav(a)
    case_a = {"posted": a.posts, "hides": a.hides,
              "reasserts_when_hidden": a.hides == [4242] and a.posts == ["_reassert_hidden"]}

    # B -- shown on purpose.
    b = Probe(mod, Shell, mapped=True, visible=True)
    nav(b)
    case_b = {"posted": b.posts, "hides": b.hides,
              "respected_when_shown": b.posts == [] and b.hides == []}

    # C -- the row cycle: shown, then the OWNER hides it, then a navigation arrives.
    c = Probe(mod, Shell, mapped=True, visible=True)
    nav(c)
    before = list(c.hides)
    hide(c, "audit-row60")
    visible_after_owner_hide = c.visible
    c.state["mapped"] = True          # a later navigation maps it again
    nav(c)
    case_c = {"visible_after_owner_hide": visible_after_owner_hide,
              "hides_before_cycle_leg": before,
              "hides_after_cycle_leg": c.hides,
              "reasserts_after_a_hide_cycle": (visible_after_owner_hide is False
                                               and len(c.hides) > len(before)
                                               and c.posts[-1:] == ["_reassert_hidden"])}

    # D -- the residual: a STALE visible=True while the window is mapped.
    d = Probe(mod, Shell, mapped=True, visible=True)
    reassert(d)
    case_d = {"hides": d.hides, "visible": d.visible,
              "stale_cache_residual": d.hides == []}

    # E -- ADDED 2026-10-20: the contract of `hide_panel` DEPOIS de 2026-10-17. O
    # produto trocou "esconder o painel desliga a legenda" por "esconder o painel
    # tira os PIXELS e deixa o interruptor do dono como esta" (o dono, verbatim:
    # *"ela e' livre na minha tela, um overlay"*). O `hide_panel` REAL chama
    # `self._blank_caption_window('panel-hidden')` (`app/webview/sotto_webview.py:7726`)
    # e NAO chama `show_caption_window(False)`. Sem este caso, o stub recem-acrescentado
    # era decoracao -- um mutante que tirasse a chamada passava despercebido, que e'
    # exactamente o que um portao nao pode ser.
    e = Probe(mod, Shell, mapped=True, visible=True)
    hide(e, "audit-row60")
    case_e = {"blank_caption_calls": e.blank_caption_calls,
              "caption_window_calls": e.caption_window_calls,
              "hides_the_pixels_not_the_switch":
                  (e.blank_caption_calls == ["panel-hidden"]
                   and e.caption_window_calls == [])}

    return {
        "case_a_hidden": case_a,
        "case_b_shown": case_b,
        "case_c_cycle": case_c,
        "case_d_stale_cache": case_d,
        "case_e_caption_window": case_e,
        "reasserts_when_hidden": case_a["reasserts_when_hidden"],
        "respected_when_shown": case_b["respected_when_shown"],
        "reasserts_after_a_hide_cycle": case_c["reasserts_after_a_hide_cycle"],
        "stale_cache_residual": case_d["stale_cache_residual"],
        "hides_the_pixels_not_the_switch": case_e["hides_the_pixels_not_the_switch"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-cmd", default=RUN_CMD)
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("panel-visibility-guard-oracle -- row #60: cache or latch? (no launch)")

    live = load_shell(SHELL, "sotto_shell_row60")
    got = run_cases(live)
    run_cmd_text = open(parsed.run_cmd, encoding="utf-8").read()
    got.update(promise(run_cmd_text))
    for key in ("reasserts_when_hidden", "respected_when_shown",
                "reasserts_after_a_hide_cycle", "stale_cache_residual",
                "hides_the_pixels_not_the_switch"):
        say("  live  " + key.ljust(36) + str(got[key]))
    for key in ("claims_start_hidden", "marks_precision", "cites_the_receipt",
                "promise_precise"):
        say("  live  " + key.ljust(36) + str(got[key]))

    if not parsed.neg_arm:
        refuted = got["reasserts_when_hidden"] and got["reasserts_after_a_hide_cycle"]
        say("")
        # DERIVED FROM THE RUN, never a fixed sentence: this line used to carry the refutation
        # text on BOTH branches, so a STANDS verdict printed the sentence of its opposite.
        say("VERDICT: " + ("ROW #60 REFUTED" if refuted else "ROW #60 STANDS") + " -- measured: "
            + "hidden-reasserts=" + str(got["reasserts_when_hidden"])
            + " after-owner-hide-reasserts=" + str(got["reasserts_after_a_hide_cycle"])
            + " shown-is-respected=" + str(got["respected_when_shown"])
            + " stale-cache-residual=" + str(got["stale_cache_residual"])
            + "; the residual is a STALE visible=True, corrected by toggle_panel live read and by"
            + " the navigation-time Show gate upstream.")
        say("VERDICT row #61: " + ("PRECISE" if got["promise_precise"] else "IMPRECISE")
            + " -- run.cmd claims_start_hidden=" + str(got["claims_start_hidden"])
            + " marks_precision=" + str(got["marks_precision"])
            + " cites_the_receipt=" + str(got["cites_the_receipt"]))
        say("VERDICT hide_panel (2026-10-17): "
            + ("BLANKS THE PIXELS, LEAVES THE SWITCH" if got["hides_the_pixels_not_the_switch"]
               else "DOES NOT BLANK THE PIXELS")
            + " -- hiding the panel calls _blank_caption_window('panel-hidden') and does NOT"
            + " call show_caption_window(False): measured "
            + "blank=" + str(got["case_e_caption_window"]["blank_caption_calls"])
            + " switch=" + str(got["case_e_caption_window"]["caption_window_calls"]))
        ok = (refuted and got["promise_precise"]
              and got["hides_the_pixels_not_the_switch"])
        say("VERDICT: " + ("BOTH ROWS CLOSED" if ok else "ONE OF THE TWO ROWS IS NOT CLOSED"))
        return 0 if ok else 1

    scratch = tempfile.mkdtemp(prefix="sotto-visneg-")
    text = open(SHELL, encoding="utf-8").read()
    if GUARD not in text:
        say("SETUP ERROR: the re-assert guard is not where this oracle documents it")
        return 2
    path = os.path.join(scratch, "sotto_webview_guard_off.py")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace(GUARD, GUARD_OFF, 1))
    mutant_mod = load_shell(path, "sotto_shell_row60_mutant")
    mut = run_cases(mutant_mod)
    for key in ("reasserts_when_hidden", "respected_when_shown",
                "reasserts_after_a_hide_cycle", "stale_cache_residual",
                "hides_the_pixels_not_the_switch"):
        say("  mut   " + key.ljust(36) + str(mut[key]))
    wrong = []
    if not got["stale_cache_residual"]:
        wrong.append("live case D did not bail (the residual is not what this says it is)")
    if mut["stale_cache_residual"]:
        wrong.append("mutant case D still bailed (removing the guard changed nothing)")
    for key in ("reasserts_when_hidden", "respected_when_shown",
                "reasserts_after_a_hide_cycle", "hides_the_pixels_not_the_switch"):
        if mut[key] != got[key]:
            wrong.append("mutant moved " + key + ", which this mutant must not touch")
    say("")
    # THIRD MUTANT, added 2026-10-20: the caption-window case E has to be able to say
    # NO. Without this copy, case E would be DECORATION -- a check that is green in the
    # live tree for a reason nobody could contradict. The cut takes the
    # `_blank_caption_window('panel-hidden')` call out of `hide_panel`, so the product
    # would go back to leaving the caption pixels up; case E MUST go RED.
    BLANK_CALL = "        self._blank_caption_window('panel-hidden')"
    if text.count(BLANK_CALL) != 1:
        say("SETUP ERROR: the hide_panel caption-window call is not where this oracle "
            "documents it")
        return 2
    blank_path = os.path.join(scratch, "sotto_webview_no_blank.py")
    with open(blank_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace(BLANK_CALL, "        pass  # oracle mutant: no blank", 1))
    blank_mod = load_shell(blank_path, "sotto_shell_row60_noblank")
    blank = run_cases(blank_mod)
    say("  mut   hides_the_pixels_not_the_switch " + str(blank["hides_the_pixels_not_the_switch"]))
    if blank["hides_the_pixels_not_the_switch"]:
        wrong.append("the hide_panel mutant still blanked the caption window"
                     " (case E cannot say NO -- it is decoration)")
    # SECOND MUTANT, different file: strip the precision clause out of run.cmd (row #61).
    run_text = open(parsed.run_cmd, encoding="utf-8").read()
    if PRECISION not in run_text:
        say("SETUP ERROR: the run.cmd precision clause is not where this oracle documents it")
        return 2
    run_mutant = os.path.join(scratch, "run-cmd-imprecise.cmd")
    with open(run_mutant, "w", encoding="utf-8", newline="") as handle:
        handle.write(run_text.replace(PRECISION, "the panel starts hidden"))
    mut_promise = promise(open(run_mutant, encoding="utf-8").read())
    say("  mut   run.cmd promise_precise     " + str(mut_promise["promise_precise"]))
    if mut_promise["promise_precise"]:
        wrong.append("run.cmd mutant still read precise (the check cannot see the clause)")
    say("")
    say("NEG-ARM: removing the re-assert guard must flip case D ALONE, stripping the run.cmd"
        " precision clause must break the promise check, and taking the caption-window"
        " blank out of hide_panel must flip case E; wrong: " + str(wrong))
    say("NEG-ARM " + ("PASS" if not wrong else "FAIL"))
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())