"""Oracle de `_main/dm-triage.py` -- a FERRAMENTA que julga os DMs do watcher.

Nasceu de um defeito medido na propria ferramenta (2026-11-26): o DM
`dm-81956dec` chegou com a forma

    STUTTER (owner): python.exe(72760) is the top measured pressure, signals:
    tick-gap, not-scheduled -- CANNOT-MEASURE this tree's rate ...

e a ferramenta respondeu `DM-TRIAGE CANNOT-MEASURE why=unparsed-section`. A
recusa estava HONESTA (ela nao inventou uma taxa), mas era inutil: a DM nao tem
numero nenhum a julgar -- o watcher declara que a leitura e' uma POSICAO NA FILA
de um tick travado -- e o que ela afirma e' IDENTIDADE e CADEIA, que sao
verificaveis. Hoje ela responde `why=no-rate-in-claim` com a identidade
resolvida, e um pid morto sai `UNKNOWN`, nunca `MISATTRIBUTED` (um pid morto nao
e' um pid alheio).

Os arms, e o que cada um RECUSA:

  a  `unmeasured`      forma real do dm-81956dec -> rc 0, `why=no-rate-in-claim`,
                       `metric=identity`, `alive=no`, `verdict-chain=UNKNOWN`
  b  `dead-pid`        taxa numerica com pid morto -> rc 3, `why=dead-pid`
  c  `unparsed`        assunto sem classe -> rc 3, `why=unparsed-section`
  d  `window`          `--window 0` -> rc 3, `why=... window-must-be-positive`
  e  `facts-only`      imprime factos e NAO amostra (rc 0, sem `status=`)
  f  `owner-screen`    o modulo nao chama nada que pinte a tela dele

`--neg-arm` muta o MODULO (nao a expectativa) em tres sitios e exige que o arm
correspondente fique vermelho; um mutante que nao derrube o seu arm e' um
`MISSED` e o oraculo devolve rc 0 -- o codigo de "o portao e' cego".

Uso: python _main/dm-triage-oracle.py [--neg-arm]
rc 0 = PASS (todos os arms), rc 1 = FAIL, rc 3 = CANNOT-MEASURE.
"""
# NO-BUG: a ferramenta de triagem de DMs nao tinha oraculo nem linha na bateria; o
# defeito medido (dm-81956dec) foi a propria recusa `why=unparsed-section` e nao
# ha' id de ledger para ele -- a cura e' este par de arms.
from __future__ import annotations

import argparse
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "dm-triage.py"
PY = sys.executable or "python"

# A forma REAL, byte a byte, do DM que expos o defeito (dm-81956decf09eec356bb0).
UNMEASURED = """---
id: dm-{dm}
from: watcher
subject: STUTTER (owner): python.exe({pid}) is the top measured pressure, signals: tick-gap, not-scheduled \u2014 CANNOT-MEASURE this tree's rate: the governor's tick was stalled (tick-gap, not-scheduled), so the sampled number is a queue position, not the culprit's CPU
status: new
schema: 1
---

## question

Owner order, verbatim: "acabou de acontecer stutter. culpa de quem?"

culprit   = python.exe({pid})
attribution = tick-gap
cwd       = H:\\sotto
cmdline   = python _main\\gaming-hotkey-oracle.py --neg-arm
chain     = python.exe({pid}) <- pythonw.exe(100360) <- cmd.exe(51060) <- python.exe(52096) <- cmd.exe(92652)
ceiling   = watcher run --cpu 40 --io very-low by python.exe(52096) \u2014 kernel Job Object
"""

NUMERIC_DEAD = """---
id: dm-{dm}
from: watcher
subject: STUTTER (owner): python.exe({pid}) is the top measured pressure, cpu 42 % of one core over a 5 s window
status: new
schema: 1
---

## question

culprit   = python.exe({pid})
chain     = python.exe({pid}) <- cmd.exe(51060)
ceiling   = watcher run --cpu 40 --io very-low
"""

GARBAGE = """---
id: dm-{dm}
from: watcher
subject: hello there, just checking in.
status: new
schema: 1
---

## question

no numbers, no culprit.
"""


# A LARGADA E' A DA CASA: `hidden-launch` poe CREATE_NO_WINDOW **e** o
# `startupinfo` com STARTF_USESHOWWINDOW/SW_HIDE. So' `creationflags` e' o
# WEAK-FLAG que o `console-window-audit` recusa (medido 2026-11-26: dois sitios
# deste ficheiro derrubaram o passo), porque herda a consola do pai.
_LAUNCH = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "hidden-launch.py"))


def dead_pid() -> int:
    """Um pid que EXISTIU e morreu -- a morte e' o facto, nao um chute."""
    proc = _LAUNCH["popen"]([PY, "-c", "raise SystemExit(0)"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait(timeout=60)
    return proc.pid


def run_tool(tool: Path, dm: Path, extra: list[str], root: str) -> tuple[int, str, str]:
    proc = _LAUNCH["popen"]([PY, str(tool), str(dm), "--root", root] + extra,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=120)
    return proc.returncode, out, err


def arm(name: str, tool: Path, dm: Path, extra: list[str], rc: int,
        markers: tuple[str, ...], absent: tuple[str, ...], root: str) -> tuple[bool, str]:
    got, out, err = run_tool(tool, dm, extra, root)
    blob = out + err
    if got != rc:
        return False, f"rc={got} want={rc} out={blob.strip()[:200]!r}"
    for m in markers:
        if m not in blob:
            return False, f"missing {m!r} in {blob.strip()[:200]!r}"
    for a in absent:
        if a in blob:
            return False, f"forbidden {a!r} present in {blob.strip()[:200]!r}"
    return True, "ok"


def build_fixtures(tmp: Path) -> dict[str, Path]:
    d = dead_pid()
    out = {}
    for key, text in (("unmeasured", UNMEASURED), ("numeric_dead", NUMERIC_DEAD),
                      ("garbage", GARBAGE)):
        p = tmp / f"{key}.md"
        p.write_text(text.format(dm=key, pid=d), encoding="utf-8")
        out[key] = p
    out["pid"] = d  # type: ignore[assignment]
    return out


ARMS = (
    # nome, fixture, extra, rc, markers, absent
    ("a-unmeasured-dm-carries-no-rate",
     "unmeasured", [], 0,
     ("why=no-rate-in-claim", "metric=identity", "alive=no", "verdict-chain=UNKNOWN"),
     ("verdict-chain=MISATTRIBUTED", "unparsed-section")),
    ("b-a-numeric-rate-with-a-dead-pid-refuses",
     "numeric_dead", [], 3, ("why=dead-pid",), ()),
    ("c-an-unclassifiable-subject-refuses",
     "garbage", [], 3, ("why=unparsed-section", "text='hello there, just checking in.'"), ()),
    ("d-a-zero-window-refuses",
     "unmeasured", ["--window", "0"], 3, ("window-must-be-positive",), ()),
    ("e-facts-only-never-samples",
     "unmeasured", ["--facts-only"], 0,
     ("verdict-chain=", "DM-TRIAGE dm="), ("status=OK", "why=no-rate-in-claim")),
)


def owner_screen() -> tuple[bool, str]:
    """Nenhuma chamada que pinte a tela do dono -- medido no FONTE, nao na prosa."""
    src = TOOL.read_text(encoding="utf-8", errors="replace")
    bad = [m for m in ("webbrowser.open", "os.startfile", "tkinter", "MessageBoxW",
                       "ShellExecute", "window.open(") if m in src]
    if bad:
        return False, f"chamadas que pintam a tela: {bad}"
    return True, "ok"


MUTANTS = (
    # nome, substituicao, arm que TEM de ficar vermelho
    ("a-dm-that-declares-cannot-measure-becomes-a-cpu-class",
     ('        if "cannot-measure" in s:\n            return "STUTTER-unmeasured"\n', ''),
     "a-unmeasured-dm-carries-no-rate"),
    ("a-dead-culprit-is-called-misattributed",
     ('        verdict = "UNKNOWN" if not live else "MISATTRIBUTED"',
      '        verdict = "MISATTRIBUTED"'),
     "a-unmeasured-dm-carries-no-rate"),
    ("a-zero-window-is-accepted",
     ('    if args.window <= 0:', '    if False:'),
     "d-a-zero-window-refuses"),
)


def neg_arm(tmp: Path, fx: dict) -> int:
    src = TOOL.read_text(encoding="utf-8")
    caught = missed = 0
    for name, (old, new), target in MUTANTS:
        if old not in src:
            print(f"NEG-ARM MISSED {name}: sinal ausente no fonte")
            missed += 1
            continue
        mutant = tmp / "mutant_dm-triage.py"
        mutant.write_text(src.replace(old, new, 1), encoding="utf-8")
        want = next(a for a in ARMS if a[0] == target)
        _n, _fx, extra, rc, markers, absent = want
        ok, why = arm(target, mutant, fx[_fx], extra, rc, markers, absent, str(HERE.parent))
        if ok:
            print(f"NEG-ARM MISSED {name}: o arm {target} continuou verde ({why})")
            missed += 1
        else:
            print(f"NEG-ARM caught {name} -> {target}: {why[:110]}")
            caught += 1
    print(f"NEG-ARM: {'PASS' if missed == 0 else 'FAIL'} -- {caught} caught, {missed} missed "
          f"of {len(MUTANTS)}")
    return 1 if missed == 0 else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true",
                    help="muta o MODULO e exige que cada arm fique vermelho")
    args = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="dm-triage-oracle-"))
    try:
        fx = build_fixtures(tmp)
        if args.neg_arm:
            return neg_arm(tmp, fx)
        passed = failed = 0
        for name, key, extra, want_rc, markers, absent in ARMS:
            ok, why = arm(name, TOOL, fx[key], extra, want_rc, markers, absent, str(HERE.parent))
            print(f"ARM {name}: {'PASS' if ok else 'FAIL'} -- {why}")
            passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        ok, why = owner_screen()
        print(f"ARM f-owner-screen: {'PASS' if ok else 'FAIL'} -- {why}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"VERDICT: {'PASS' if failed == 0 else 'FAIL'} -- {passed} arms PASS, {failed} FAIL")
        return 0 if failed == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
