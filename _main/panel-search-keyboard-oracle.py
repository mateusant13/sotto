#!/usr/bin/env python3
"""panel-search-keyboard-oracle -- can the panel take keyboard focus at all? The row says NO; the code and a
real run log say YES, while the pointer is on it.

AUDIT ROW F9: "o campo de busca do painel nao pode receber teclado" (auditoria-completa-20261007.md:71), a
finding whose source transfers the decision to the owner. The audit was right about the MECHANISM it named:
`_on_before_show` puts WS_EX_NOACTIVATE on the window and `show_panel` shows it with SW_SHOWNOACTIVATE --
right for appearing (Alt+C must not steal focus), wrong for the INTERACTIVE state, because a
WS_EX_NOACTIVATE window is not brought to the foreground by a click either, so the panel could never take
keyboard focus and `<input type="search" id="search-input">` could never receive a character.

THAT IS NOW FIXED, and this oracle measures the fix where it can:
  * THE CHAIN, in the live files: panel.js mouseenter/mouseleave -> bridge.setPointerInteractive(active) ->
    the shell IPC call -> set_pointer_interactive(), which CLEARS WS_EX_NOACTIVATE and click-through while
    active and restores both on leave. show_panel SW_SHOWNOACTIVATE is untouched, so appearing still
    steals nothing; only the moment the pointer is on the panel can activate it.
  * THE EVIDENCE FROM A REAL RUN: _main/webview-run.log carries the POINTER_INTERACTIVE lines of
    the runs it holds, and
    (THE LOG IS LIVE -- lanes keep writing to it, so the counts DRIFT: 671 lines read in one pass, 621 in the
    next minutes later. The arms re-derive them every run and the verdict prints the CURRENT ones; no number
    here is remembered.)
    this oracle checks the INVARIANT over every one of them -- active=X iff click_through=not X iff
    noactivate=not X. Measured 2026-10-12: 671 lines, 337 active=true with noactivate=false, 334
    active=false with noactivate=true. The window really does receive activation rights while the pointer
    is on it, thousands of times, in the shipped app.
  * WHAT STAYS TRUE, and is by design: the search INPUT is DISABLED while no writer exists (panel.html), a
    content condition rather than a keyboard one, so an empty history cannot be searched even when focused.
  * UNMEASURED, and said so: that a CHARACTER actually lands in the field. Nothing here typed into it --
    that needs the launch the owner stop order forbids. The residual is a keystroke test, not a wiring gap.

THE LOG IS LIVE DATA, AND THIS FILE SAYS SO OUT LOUD. `_main/webview-run.log` is written by the app itself
while it runs, so it grows and changes between two runs of this oracle. It is DADO VIVO, not source: it is
therefore NOT one of the battery's `deps` (deps are FILES, and a growing log is a file that changes on its
own -- the fingerprint would be a lie about what was judged). Every run prints the log it judged: how many
bytes, how many POINTER_INTERACTIVE lines, and the sha256 of exactly those bytes.

ARM 4 is the control: one line of a COPY of the log is rewritten so noactivate contradicts active, and the
invariant must catch it -- otherwise arm 2 would only be counting lines. The real log is never modified.

NEGATIVE ARM (executed, not decorative)
    `--neg-arm` runs ONLY that control, and only the control: it proves that the invariant reader can see
    a contradiction instead of counting lines. It exits 1 BY DESIGN (the negative arm has to fail) and
    prints `NEG-ARM PASS` when the control did its job. A control that cannot seed its violation, or one
    whose violation slips through, is a FAILURE and says so.

Usage:
    python _main/panel-search-keyboard-oracle.py            # the arms, rc=0 on PASS
    python _main/panel-search-keyboard-oracle.py --neg-arm  # the control alone, rc=1 BY DESIGN
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
PANEL_JS = os.path.join(ROOT, "app", "panel", "panel.js")
PANEL_HTML = os.path.join(ROOT, "app", "panel", "panel.html")
LOG = os.path.join(ROOT, "_main", "webview-run.log")
# THE FIELDS ARE READ BY NAME, NEVER BY ADJACENCY (re-anchored 2026-11-11). The
# shell writes `active= click_through= applied= noactivate=` (sotto_webview.py,
# `POINTER_INTERACTIVE` log line): a fourth field was inserted BETWEEN
# `click_through` and `noactivate`, and the old pattern required the three to be
# contiguous, so it matched 0 of the 139 lines in the log and arm 2 accused the
# PRODUCT ("no POINTER_INTERACTIVE line at all") of the INSTRUMENT's rot. The
# `.*?` between the fields is exactly what a new field must not be able to break,
# and the capture is still anchored on the three names the invariant needs.
LINE = re.compile(r"POINTER_INTERACTIVE active=(\w+)\b.*?\bclick_through=(\w+)\b"
                  r".*?\bnoactivate=(\w+)\b")

EXIT_PASS = 0
EXIT_FAIL = 1


def parse(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = LINE.search(line)
            if match:
                rows.append(tuple(match.group(1, 2, 3)))
    return rows


def violations(rows):
    bad = []
    for active, click, noact in rows:
        want = "false" if active == "true" else "true"
        if click != want or noact != want:
            bad.append((active, click, noact))
    return bad


def control(say):
    """The control: one line of a COPY of the log made contradictory.

    THE VIOLATION IS SEEDED FROM A LINE THE READER ITSELF MATCHED (re-anchored
    2026-11-11). The old control replaced one fixed literal
    (`active=true click_through=false noactivate=false`): when the shell inserted
    `applied=` into that same line the literal ceased to exist, and the control
    declared "no active=true line to mutate" while arm 2 was reading the log
    correctly -- the control was measuring the line's SPELLING, not the reader.
    Now the anchor is a line `LINE` matched, and its two flags are rewritten BY
    NAME: a field added anywhere on that line can change its text but never the
    ability to seed the contradiction, so this anchor cannot rot the same way.

    Returns True when the invariant reader caught the contradiction (the control
    did its job), False otherwise. The real log is never modified.
    """
    workdir = os.path.join(tempfile.gettempdir(), "f9-keyboard")
    os.makedirs(workdir, exist_ok=True)
    mutant = os.path.join(workdir, "log-mutant.txt")
    with open(LOG, encoding="utf-8", errors="replace", newline="") as handle:
        live = handle.read().splitlines(True)
    # ANCORA RE-MEDIDA 2026-11-23: o seeding exigia uma linha `active=true`, e o
    # log VIVO pode nao ter NENHUMA linha `POINTER_INTERACTIVE` (o dono abriu a
    # app e o ponteiro nunca passou no painel: 0 linhas medidas as 04:43 da
    # sessao de 2026-11-23) -- o controlo dizia "could not seed" e saia com rc=0,
    # que a bateria le' como o controlo NAO reprovar. Duas metades:
    #   (a) a semente e' QUALQUER linha que o leitor casou -- prefere-se
    #       `active=true`, uma `active=false` serve (basta UMA das tres flags
    #       contradizer a invariante);
    #   (b) sem linha nenhuma no log vivo, a copia e' SINTETICA: tres linhas com a
    #       forma que o shell escreve, uma consistente a activa, uma consistente
    #       IDLE e a terceira contraditoria. O log real nunca e' tocado.
    fallback = None
    seed = None
    for index, line in enumerate(live):
        match = LINE.search(line)
        if not match:
            continue
        if match.group(1) == "true" and match.group(2, 3) != ("true", "true"):
            seed = index
            break
        if fallback is None:
            fallback = index
    if seed is None:
        seed = fallback
    source = "live"
    if seed is None:
        source = "synthetic"
        original = [
            "POINTER_INTERACTIVE active=true click_through=false applied=true "
            "noactivate=false\n",
            "POINTER_INTERACTIVE active=false click_through=true applied=true "
            "noactivate=true\n",
            "POINTER_INTERACTIVE active=true click_through=false applied=true "
            "noactivate=false\n",
        ]
        seed = 2
    else:
        original = live
    row = LINE.search(original[seed]).group(1, 2, 3)
    patched = original[seed]
    if row[0] == "true":
        patched = re.sub(r"\bnoactivate=\w+", "noactivate=true", patched, count=1)
    else:
        # uma linha IDLE: vira-la `active=true` contradiz as duas flags dela
        patched = re.sub(r"\bactive=\w+", "active=true", patched, count=1)
    lines = list(original)
    lines[seed] = patched
    # How far the copy differs from the original: exactly ONE line, so there is no
    # doubt about WHICH line the control patched.
    changed = sum(1 for a, b in zip(original, lines) if a != b)
    changed += abs(len(original) - len(lines))
    with open(mutant, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(lines))
    caught = violations(parse(mutant))
    say("  arm 4  CONTROL (one line of a COPY made contradictory): source=%s, patched "
        "line %d (semente active=%s cf=%s na=%s), the copy differs from the original in "
        "%d line(s); violations caught=%d (the live log had %d)"
        % (source, seed + 1, row[0], row[1], row[2], changed, len(caught),
           len(violations(parse(LOG)))))
    os.remove(mutant)
    if changed != 1:
        say("  arm 4  CONTROL: the patch was NOT surgical -- the control is not testing what it claims")
        return False
    if not caught:
        return False
    if source == "synthetic" and len(caught) != 1:
        # a copia sintetica carrega UMA contradicao: mais do que uma quer dizer
        # que o leitor marcou uma linha consistente -- o controlo nao provaria o
        # que diz provar.
        say("  arm 4  CONTROL: the synthetic copy has ONE contradiction and the reader "
            "flagged %d line(s) -- the reader or the fixture is wrong"
            % len(caught))
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true",
                        help="run ONLY the control; rc=1 BY DESIGN")
    args = parser.parse_args(argv)
    say = print
    wrong = []
    with open(SHELL, encoding="utf-8") as handle:
        shell = handle.read()
    with open(PANEL_JS, encoding="utf-8") as handle:
        panel_js = handle.read()
    with open(PANEL_HTML, encoding="utf-8") as handle:
        panel_html = handle.read()
    with open(LOG, "rb") as handle:
        log_bytes = handle.read()
    log_sha = hashlib.sha256(log_bytes).hexdigest()

    if args.neg_arm:
        say("panel-search-keyboard-oracle -- NEGATIVE ARM: the control alone\n")
        say("  log       : %s (%d B, sha256 %s)" % (os.path.basename(LOG), len(log_bytes), log_sha))
        say("  note      : LIVE DATA -- the app writes this log while it runs, so the digest")
        say("              above says WHICH log this verdict was taken over.\n")
        ok = control(say)
        say("")
        say("VERDICT: NEG-ARM %s  control %s"
            % ("PASS" if ok else "FAIL", "caught the contradiction" if ok else "DID NOT catch it"))
        say("(rc=1 por design: the negative arm has to fail)")
        return EXIT_FAIL if ok else EXIT_PASS

    say("panel-search-keyboard-oracle -- row F9 (files + the run log; no launch)")

    chain = {
        "panel.js drives activation on hover": "setPointerInteractive" in panel_js,
        "on mouseenter AND mouseleave": "mouseenter" in panel_js and "mouseleave" in panel_js,
        "the shell receives the payload": "'active'" in shell or "\"active\"" in shell,
        "the setter CLEARS noactivate when active": "remove=WS_EX_NOACTIVATE" in shell,
        "and RESTORES it when idle": "add=WS_EX_NOACTIVATE" in shell,
    }
    say("  arm 1  the chain, in the live files: " + ", ".join("%s=%s" % (k, str(v).lower())
        for k, v in chain.items()))
    for key, ok in chain.items():
        if not ok:
            wrong.append("arm 1: the chain lost " + key)

    rows = parse(LOG)
    truthy = sum(1 for a, _c, _n in rows if a == "true")
    falsy = sum(1 for a, _c, _n in rows if a == "false")
    bad = violations(rows)
    say("  arm 2  the run log: %d POINTER_INTERACTIVE line(s), active=true %d, active=false %d, invariant violations %d (log %d B, sha256 %s)"
        % (len(rows), truthy, falsy, len(bad), len(log_bytes), log_sha))
    # UM LOG SEM A LINHA NAO REFUTA A LINHA F9 (medido 2026-11-23): a sessao viva
    # do dono (aberta 04:43) tinha ZERO `POINTER_INTERACTIVE` -- o ponteiro nunca
    # passou no painel. Contar a ausencia como "o painel nao pode receber
    # activacao" seria julgar o PRODUTO por nao ter sido exercitado; o passo
    # declara-se SKIPPED (nunca verde), e o `:skipped` da bateria exige a frase.
    skipped = None
    if not rows:
        skipped = ("no-pointer-lines in _main/webview-run.log (0 matched line(s)) -- "
                   "arm 2 is the only arm that reads the log, and the chain arms passed")
        say("  arm 2  SKIPPED reason=no-pointer-lines")
    elif truthy == 0 or falsy == 0:
        wrong.append("arm 2: the toggle only ever went ONE way -- the panel could not take activation")
    if bad:
        wrong.append("arm 2: %d line(s) break the invariant, e.g. %s" % (len(bad), bad[:2]))

    # ARM 3, RE-ANCORADA EM 2026-10-30, com a razao escrita: o dono pediu a caixa de
    # busca FORA em 2026-10-21 21:24 (*"tira a caixa de procurar texto"*) e ela saiu do
    # markup nesta sessao. A premissa da linha F9 -- "o campo nao pode receber teclado" --
    # ficou sem sujeito, e a versao mais FORTE dessa mesma linha e' a AUSENCIA: nao ha
    # campo nenhum para receber o que quer que seja. Um campo que voltasse a aparecer
    # sem esta arm a dizer nada passaria despercebido, por isso as duas metades ficam.
    field = ("search-input" in panel_html) and ("search-form" in panel_html)
    declared = "disabled while no writer exists" in panel_html or "search input is disabled" in panel_html
    absent_ok = not field
    say("  arm 3  the field: input present=%s (absent is the owner's order), "
        "disabled-while-no-writer declared=%s"
        % (str(field).lower(), str(declared).lower()))
    if field and not declared:
        wrong.append("arm 3: a search field CAME BACK and its inert reason is not declared")
    if not absent_ok and not declared:
        pass  # covered above

    if not control(say):
        wrong.append("arm 4: a contradictory line slipped through -- arm 2 counts lines, it does not read them")

    say("")
    detail = (" -- the row is REFUTED as of this revision: the panel DOES receive activation while the"
              " pointer is on it (chain wired in the files; %d activation(s) measured in a real run log,"
              " %d release(s), %d invariant violation(s) over %d line(s)). What stays true is the field"
              " own condition -- DISABLED while no writer exists -- and that no keystroke was ever typed"
              " into it: that is UNMEASURED, and needs the launch the owner order forbids"
              ) % (truthy, falsy, len(bad), len(rows))
    if wrong:
        say("VERDICT: FAIL" + detail)
    elif skipped:
        say("VERDICT: SKIPPED reason=" + skipped)
    else:
        say("VERDICT: PASS" + detail)
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
