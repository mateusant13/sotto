#!/usr/bin/env python
"""GATE: um passo que LARGA a app nao pode correr na classe `always`.

O DEFEITO MEDIDO (2026-10-30). A reconstrucao da bateria depois do truncamento
declarou todos os passos novos como `always`; dois deles -- `shell-relaunch` e o
seu braco negativo -- exercitam o auto-relancamento, e o log da app prova o
resultado:

    12:07:05.460 SHELL_STARTUP_STAGE pid=8992   stage=pre-lock panel=true
    12:09:12.101 SHELL_STARTUP_STAGE pid=33300  stage=pre-lock panel=true

Duas instancias nascidas nos dois minutos em que a bateria correu, cada uma com
o `PANEL_GEOMETRY_RESTORED` a seguir. A lei do dono e' `SOTTO_NEVER_ON_OWNER_SCREEN`
(AGENTS.md): nenhuma lane lanca a app de modo a que ela apareca no ecra dele. Um
passo que mexe no relancamento pertence a classe `heavy`, que NAO corre sem
`SOTTO_BATTERY_HEAVY=1`.

O QUE ESTE ORACULO EXIGE
  * lê as linhas `call :step <classe> <nome> ... <comando>` da `.cmd`;
  * se o COMANDO nomeia um modulo que larga a app, a classe TEM de ser `heavy`;
  * a lista de modulos e' explicita e pequena: o que se prova e' o que se nomeia.

ARM 1  todo o passo `always` cujo comando nomeia um largador -- ZERO permitido.
ARM 2  a lista de largadores casa com os ficheiros que existem no repo.
ARM 3  o proprio `shell-relaunch` (e o seu braco negativo) estao declarados `heavy`.

NEG-ARM (`--neg-arm`): a MESMA verificacao sobre uma copia da `.cmd` em que um
passo `heavy` foi rebaixado a `always` -- tem de ficar VERMELHO.

Exit: 0 verde, 1 vermelho, 2 erro de setup.
"""
# NO-BUG: portao das CLASSES de passo da bateria: recusa um passo `always` cujo comando nomeie um largador da app (o que ja' exercitou o auto-relancamento por acidente)
from __future__ import annotations

import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
CMD = os.path.join(HERE, "_audit-verify-all.cmd")

#: Os commandos que podem LARGAR a app (ou largar um filho que a substitui).
#: Nomeados um a um: uma lista por padrao (`*probe*`) punha a classe errada em
#: passos que so' leem.
LAUNCHERS = (
    "shell-relaunch-oracle.py",     # exercita o relancamento (selftest + mutantes)
    "shell_relaunch.py",
    "app\\webview\\sotto_webview.py",
    "_strip-surface-probe.py",
    "_strip-restore-probe.py",
    "_strip-stats-probe.py",
    "_strip-stats-log-probe.py",
    "panel-exit3-oracle.py",        # braco `--with-worker` sobe worker + shell
    "sotto-relaunch.py",
    # `launch-as-token.py` NAO esta' aqui: ele empresta o token de uma instancia
    # que JA' existe e larga um filho proprio, mas nunca sobe a app.
)

#: Os subcomandos do `_main\devlab\lab.py` que LEVANTAM o worker de ASR: os
#: quatro `run_worker_once(` de la' largam `worker\sotto_worker.py`, que carrega
#: ~1,8 GiB de modelo e ocupa a GPU. MEDIDO 2026-11-15: `concurrent-workers` (S4)
#: e `devlab-crosstalk` (S6) estavam declarados `heavy` no COMENTARIO e no README
#: e registados sem a palavra -- cada corrida pagava dois carregamentos (~3 min
#: de parede, 3 300 MiB) que o dono nao pediu. A classe `heavy` do `:step` nao e'
#: so' "abre a tela": e' qualquer coisa que o dono SENTE, e carregar o modelo
#: duas vezes e' exatamente isso.
#: `captions` e `chaos` NAO estao aqui de proposito: eles abrem um Chrome
#: headless sobre uma pagina de fixture e nunca tocam no modelo (medidos 3,1 s e
#: 2,0 s a quente, contra ~90 s por worker).
MODEL_SUBCMDS = ("concurrent", "crosstalk", "strips", "feed", "score")


def model_loaders(text):
    """[(nome, subcomando)] dos passos que levantam o modelo SEM `heavy`."""
    bad = []
    for cls, name, cmd in steps(text):
        if "heavy" in cls:
            continue
        low = cmd.replace("/", "\\").lower()
        if "devlab\\lab.py" not in low:
            continue
        partes = low.split("devlab\\lab.py", 1)[1].split()
        if partes and partes[0] in MODEL_SUBCMDS:
            bad.append((name, partes[0]))
    return bad


RESULTS = []


def arm(name, real, want):
    ok = real == want
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}")
    if not ok:
        print(f"       real = {real!r}\n       want = {want!r}")


def steps(text):
    """[(classe, nome, comando)] de todas as linhas `call :step ...`.

    A FORMA real da linha e' `call :step [always] [heavy] <nome> <rc> "<deps>"
    "<log>" <comando>`: a classe pode ter DUAS palavras. O comando e' o que vem
    DEPOIS da ultima aspa -- as deps de um gate tambem nomeiam largadores, e ler
    a linha inteira acusava o `battery-heavy-gate` de largar a app por ela os
    LISTAR.
    """
    mods = {"always", "heavy", "fast", "skip-capable", "light"}
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*call :step\w*\s+(.*)$", line)
        if not m:
            continue
        body = m.group(1).strip()
        cls = []
        resto = body
        while True:
            head = resto.split(" ", 1)[0]
            if head in mods:
                cls.append(head)
                resto = resto.split(" ", 1)[1] if " " in resto else ""
                continue
            break
        name = resto.split(" ", 1)[0] if resto else ""
        cmd = body.split('"')[-1].strip() if '"' in body else ""
        out.append((cls, name, cmd))
    return out


def offenders(text):
    bad = []
    for cls, name, cmd in steps(text):
        if "heavy" in cls:
            continue
        if "py_compile" in cmd:          # compilar nao abre janela nenhuma
            continue
        low = cmd.replace("/", "\\").lower()
        for launch in LAUNCHERS:
            if launch.lower() in low:
                bad.append((name, launch, cmd))
                break
    return bad


def main() -> int:
    neg = "--neg-arm" in sys.argv[1:]
    if not os.path.exists(CMD):
        print("SETUP: a bateria nao existe")
        return 2
    text = io.open(CMD, encoding="utf-8", errors="replace").read()

    if not neg:
        bad = offenders(text)
        arm("nenhum passo `always` corre um largador da app", bad, [])
        faltam = [l for l in LAUNCHERS
                  if os.path.sep in l and not os.path.exists(os.path.join(REPO, l))]
        arm("cada largador nomeado existe no repo", faltam, [])
        rel = [(c, n) for c, n, cmd in steps(text)
               if "shell-relaunch-oracle.py" in cmd]
        arm("o relancamento (e o seu negativo) estao declarados `heavy`",
            [("heavy" in c) for c, _ in rel], [True] * len(rel) if rel else [])
        arm("nenhum passo carrega o modelo sem `heavy` (o modelo custa ~1,8 GiB x2)",
            model_loaders(text), [])
        fail = RESULTS.count(False)
        print(f"\nBATTERY-CLASS VERDICT {'PASS' if fail == 0 else 'RED'} "
              f"-- arms={len(RESULTS)} fail={fail}")
        return 0 if fail == 0 else 1

    # ── o braco negativo: um `heavy` rebaixado a `always` tem de ser apanhado ──
    linhas = text.split("\n")
    alvo = None
    for i, line in enumerate(linhas):
        if re.match(r"\s*call :step .*heavy.* shell-relaunch ", line):
            alvo = i
            linhas[i] = line.replace("heavy ", "", 1)
            break
    if alvo is None:
        print("SETUP: nao encontrei o passo heavy do relancamento para mutar")
        return 2
    tmp = tempfile.mkdtemp(prefix="battery-class-")
    p = os.path.join(tmp, "battery.cmd")
    io.open(p, "w", encoding="utf-8").write("\n".join(linhas))
    mut = offenders(io.open(p, encoding="utf-8").read())
    ok = len(mut) >= 1 and mut[0][0] == "shell-relaunch"
    print(("[PASS] neg-arm: o mutante (heavy -> always) foi apanhado e nomeado\n"
           if ok else
           "[FAIL] neg-arm: o mutante sobreviveu -- o gate nao mede a classe\n"))

    # ── o SEGUNDO eixo: um carregador de modelo rebaixado tem de ser apanhado ──
    # O braco acima muta o passo do RELANCAMENTO, e a lista dele sao LARGADORES.
    # Esta arm prova o eixo que faltava -- um passo do devlab que carrega o
    # modelo -- porque um unico mutante so' exercita a lista que ele nomeia, e
    # foi exatamente por isso que `concurrent-workers` passou meses sem classe.
    linhas2 = text.split("\n")
    alvo2 = None
    for i, line in enumerate(linhas2):
        if re.match(r"\s*call :step heavy (concurrent-workers|devlab-crosstalk) ", line):
            alvo2 = i
            linhas2[i] = line.replace("heavy ", "", 1)
            break
    if alvo2 is None:
        print("SETUP: nao encontrei um passo heavy do devlab para mutar")
        return 2
    p2 = os.path.join(tmp, "battery2.cmd")
    io.open(p2, "w", encoding="utf-8").write("\n".join(linhas2))
    mut2 = model_loaders(io.open(p2, encoding="utf-8").read())
    ok2 = len(mut2) == 1 and mut2[0][1] in ("concurrent", "crosstalk")
    print(("[PASS] neg-arm2: o carregador de modelo rebaixado foi apanhado e nomeado %r\n"
           % (mut2[0][0],)) if ok2 else
          "[FAIL] neg-arm2: o mutante do modelo sobreviveu -- o eixo nao e' medido\n")

    print("BATTERY-CLASS NEG-ARM PASS -- RED as designed" if (ok and ok2)
          else "BATTERY-CLASS NEG-ARM FAIL")
    # rc=1 POR DESENHO no braco negativo (ver stale-display-oracle.py).
    return 1 if (ok and ok2) else 2


if __name__ == "__main__":
    sys.exit(main())
