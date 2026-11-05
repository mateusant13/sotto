#!/usr/bin/env python
# NO-BUG: instrumento da linha de aceitacao do Alt+C (ordem do dono, 2026-10-30): mede a ACCAO do gesto (`LIVE_ENABLED`/`PANEL_SHOWN`) contra 1500 ms; nao corrige o produto
"""ALT+C -> A ACCAO DO INTERRUPTOR: a linha de 1,5 s, medida em vez de afirmada.

A LINHA DE ACEITACAO E' *A ACCAO*, NAO A CLAUSULA. A queixa do dono foi *"alt c nao
ta dando display em qualquer painel"*: o que tem de acontecer depressa e' o que a
tecla **faz**. A ordem de 2026-11-01 e' verbatim *"faz os paineis alternarem mesmo
se eu deixar alt apertado o tempo inteiro e spammando c. alterna entre show e
hide"*, e a legenda ao vivo mudou de tecla: *"bota o padrao como control espaco"*.
Por isso cada pressao de Alt+C deixa `HOTKEY_TOGGLE step=show|hide` e cada pressao
de Ctrl+Space deixa `HOTKEY_LIVE_STEP` -- e' isso que este instrumento emparelha.

O PARAQUEDAS DE HOJE: DUAS TECLAS. `HOTKEY_PRESSED` agora traz `role=panels|live`.
Sem ler o papel, uma pressao de Ctrl+Space emparelhava com o `PANEL_SHOWN` de um
Alt+C que veio dois segundos depois e publicava 2 000 ms de latencia de um gesto
que nao foi medido -- o orcamento e' o mesmo, o gesto nao. As linhas antigas (sem
`role=`) continuam a ser lidas pelo caminho antigo, porque um log velho nao pode
virar lixo.

ESTE FICHEIRO MEDIA A COISA ERRADA. Ate' 2026-10-30 emparelhava uma pressao com a
pintura seguinte e chamava-lhe "primeira legenda", e o numero que saiu foi
**57 105 ms** contra um orcamento de 1 500 ms. Medido hoje, o defeito e' do
INSTRUMENTO e nao da app:

  * `HOTKEY_PRESSED count=1` aparece **29** vezes (de 539 pressoes no total);
    `CAPTION_PAINT`
    aparece **1** vez, a `2026-10-30 01:13:41.864`.
  * A ultima pressao que o ficheiro escolhia era de **2026-10-15 01:12:44**, e a
    pintura que ele lhe colava era de **2026-10-30** -- quinze dias e um arranque
    de shell pelo meio. A sessao so' terminava na proxima `count=1`, e uma
    sessao nao termina numa pressao: termina num `SHELL_STARTUP_STAGE`.
  * Na sessao REAL (2026-10-30, pid 33288): pressao `01:12:44.759` ->
    `LIVE_ENABLED on=true` `01:12:45.023` = **264 ms**. A pintura de `01:13:41.864`
    vem **54 s** depois de o worker arrancar (`WORKER_AUTOSTART=started`
    `01:12:47.978`) -- e' o carregamento do modelo e a primeira linha de audio,
    nao a resposta ao gesto.

O QUE ESTE ORACULO PASSA A MEDIR, e sao duas perguntas diferentes:

  1. **A ACCAO (portao, orcamento 1 500 ms).** Pressao `count=1` -> a primeira
     `LIVE_ENABLED` (ou `PANEL_SHOWN`) **na mesma sessao de shell**. E' o que o
     dono ve como "o alt c nao responde".
  2. **O CARREGAMENTO (informado, NAO e' portao).** `WORKER_AUTOSTART=started` ->
     a primeira `CAPTION_PAINT`. Isto e' o custo de um motor frio, e um portao
     aqui castigaria a app por carregar um modelo. O numero fica escrito para
     ninguem ter de o adivinhar.

SEM MEDICAO NAO E' UM VEREDITO: sem pressao, sem accao, ou sem uma sessao de
shell para as separar, sai 2 e diz o que falta. Um passo saltado nunca conta como
portao que passou.

**E O PASSO NAO ESPERA PELO GESTO DE NINGUEM**: sem `--log` ele CORRE a medicao
(`_main/pov-selftest.py --run`, tag privada) e julga o log que ESSA medicao
escreveu. Ate' 2026-11-01 ele lia `_main/webview-run.log` -- o ficheiro da
instancia do dono, que atravessa dias -- e respondia `NO-MEASURE` sempre que o
build no disco era mais novo do que a ultima sessao: um portao cujo estado de
repouso era "nao medido".

    python _main\\altc-first-caption-oracle.py                  # MEDE agora e julga
    python _main\\altc-first-caption-oracle.py --all            # todas as sessoes da medicao
    python _main\\altc-first-caption-oracle.py --budget-ms 1500 # o orcamento do dono
    python _main\\altc-first-caption-oracle.py --log <ficheiro> # julga um log ja' escrito
    python _main\\altc-first-caption-oracle.py --neg-arm        # rc=1 POR DESENHO

Exit: 0 dentro do orcamento, 1 fora do orcamento, 2 medicao ausente.
"""
# BATTERY-HEAVY: app-window -- este instrumento LARGA a app (segunda instancia,
# mutex privada, teclas livres, token `high`; nunca na tela do dono) para medir o
# gesto no build que esta' no disco. A classe pesada da bateria so' corre com
# `SOTTO_BATTERY_HEAVY=1`.

# NO-BUG: instrumento da linha de aceitacao Alt+C -> a ACCAO do Alt+C <= 1,5 s.
# A primeira versao media pressao -> pintura de TEXTO e emparelhava atraves de um
# arranque de shell (2026-10-15 -> 2026-10-30), dando 57 105 ms contra uma app que
# responde em 264 ms. As duas perguntas estao agora separadas.
from __future__ import annotations

import argparse
import datetime
import io
import os
import importlib.util
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUDGET_MS = 1500.0

STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})")
SHELL_START = re.compile(r"SHELL_STARTUP_STAGE pid=(\d+)")
PRESS = re.compile(r"HOTKEY_PRESSED(?: role=([\w-]+))? count=(\d+)")
TOGGLE = re.compile(r"HOTKEY_TOGGLE step=(\w+) surface=(\S+)")
LIVE_STEP = re.compile(r"HOTKEY_LIVE_STEP caption_on=(\w+)")
LIVE = re.compile(r"LIVE_ENABLED on=(\w+)")
PANEL = re.compile(r"PANEL_SHOWN reason=(\S+)")
WORKER = re.compile(r"WORKER_AUTOSTART=started")
PAINT = re.compile(r"CAPTION_PAINT instant=(\w+) hwnd=(\d+)")
# O BUILD DE CADA SESSao. O shell publica `SHELL_CODE_ID sha256=...` no arranque
# (2026-10-30). Sem ele, uma sessao de um build ANTIGO e' julgada como se fosse o
# codigo de hoje: medido 2026-10-30, o ultimo passo de bateria acusou 19030 ms
# contra 1500 ms com uma sessao de 11:26 enquanto o disco tinha mudado desde entao.
CODE = re.compile(r"SHELL_CODE_ID sha256=([0-9A-Fa-f]+)")


def parse_stamp(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f")
    except (TypeError, ValueError):
        return None


def read_events(path):
    """[(instante, tipo, detalhe)] -- so as linhas que interessam, em ordem de ficheiro."""
    out = []
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = STAMP.match(line)
            if not m:
                continue
            when = parse_stamp(m.group(1))
            if when is None:
                continue
            start = SHELL_START.search(line)
            if start:
                out.append((when, "shell", {"pid": start.group(1)}))
                continue
            press = PRESS.search(line)
            if press:
                out.append((when, "press", {"count": int(press.group(2)),
                                            "role": press.group(1) or ""}))
                continue
            toggle = TOGGLE.search(line)
            if toggle:
                out.append((when, "toggle", {"step": toggle.group(1),
                                             "surface": toggle.group(2)}))
                continue
            live_step = LIVE_STEP.search(line)
            if live_step:
                out.append((when, "live_step",
                            {"on": live_step.group(1) == "true"}))
                continue
            live = LIVE.search(line)
            if live:
                out.append((when, "live", {"on": live.group(1) == "true"}))
                continue
            panel = PANEL.search(line)
            if panel:
                out.append((when, "panel", {"reason": panel.group(1)}))
                continue
            if WORKER.search(line):
                out.append((when, "worker", {}))
                continue
            code = CODE.search(line)
            if code:
                out.append((when, "code", {"sha": code.group(1)}))
                continue
            paint = PAINT.search(line)
            if paint:
                out.append((when, "paint",
                            {"instant": paint.group(1) == "true",
                             "hwnd": paint.group(2)}))
    return out


def sessions(events):
    """Uma sessao por `SHELL_STARTUP_STAGE`, com o que aconteceu dentro dela.

    A SESSAO E' DO SHELL, E NAO DA PRESSAO. Era este o defeito de 2026-10-30: uma
    sessao comecava numa pressao `count=1` e acabava noutra `count=1`, por isso
    uma sessao sem segunda pressao comia o resto do ficheiro -- quinze dias -- e
    a primeira pintura de OUTRO arranque era colada a uma pressao antiga. Um log
    que atravessa varios arranques nao tem sessoes delimitadas por presses.
    """
    out = []
    for when, kind, detail in events:
        if kind == "shell":
            out.append({"pid": detail["pid"], "start": when, "presses": [],
                        "live": [], "panels": [], "workers": [], "paints": [],
                        "toggles": [], "live_steps": [], "code": None})
            continue
        if not out:
            # Antes do primeiro `SHELL_STARTUP_STAGE` (log rotado ou antigo): nao
            # se sabe a que arranque pertence, por isso nao se mede com ele.
            continue
        current = out[-1]
        if kind == "press" and detail["count"] == 1:
            current["presses"].append({"when": when,
                                       "role": detail.get("role") or ""})
        elif kind == "toggle":
            current["toggles"].append(when)
        elif kind == "live_step":
            current["live_steps"].append(when)
        elif kind == "live":
            current["live"].append(when)
        elif kind == "panel":
            current["panels"].append(when)
        elif kind == "code":
            # o primeiro id depois do arranque e' o do build que esta sessao corre
            if current.get("code") is None:
                current["code"] = detail["sha"]
        elif kind == "worker":
            current["workers"].append(when)
        elif kind == "paint":
            current["paints"].append(when)
    return [s for s in out if s["presses"]]


def disk_code_id():
    """O `sha256=` do codigo que esta' no DISCO agora, lido do proprio shell.

    A MESMA fonte que o shell usa no arranque (`code_identity()`), e a mesma que
    `_main/live-code-freshness-oracle.py` compara. Sem isto, um numero medido numa
    sessao de um build antigo seria publicado como se fosse o de hoje.
    """
    shell_dir = os.path.join(os.path.dirname(HERE), "app", "webview")
    shell = os.path.join(shell_dir, "sotto_webview.py")
    if not os.path.isfile(shell):
        return None
    if shell_dir not in sys.path:
        sys.path.insert(0, shell_dir)
    try:
        spec = importlib.util.spec_from_file_location("_altc_shell", shell)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_altc_shell"] = mod
        spec.loader.exec_module(mod)      # NAO arranca nada: `main()` so' corre em __main__
        ident = mod.code_identity() or ""
        return ident.split("sha256=", 1)[1].split()[0] if "sha256=" in ident else None
    except Exception:                     # noqa: BLE001
        return None


def first_after(stamps, when):
    for stamp in stamps:
        if stamp > when:
            return stamp
    return None


def press_when(press):
    """A pressao e' um instante (os casos do `--neg-arm`) ou `{when, role}` (o log)."""
    return press["when"] if isinstance(press, dict) else press


def first_press_per_role(session):
    """A PRIMEIRA pressao de CADA tecla -- duas teclas, duas perguntas.

    Antes de 2026-11-01 havia uma tecla e a resposta era uma. Agora um log traz
    `role=panels` e `role=live`, e medir so' a primeira do ficheiro deixava a
    outra sem veredicto (uma sessao em que ele so' tocou no Ctrl+Space depois de
    um Alt+C nunca era julgada na legenda). Linhas antigas, sem `role=`, sao um
    grupo so' -- o que era antes.
    """
    out, seen = [], set()
    for press in session["presses"]:
        role = (press.get("role") or "") if isinstance(press, dict) else ""
        if role in seen:
            continue
        seen.add(role)
        out.append(press)
    return out


def measure_one(session, press):
    """A accao que ESSA pressao causou, escolhida pelo PAPEL da tecla.

    Cada tecla tem a sua accao desde 2026-11-01: um Alt+C deixa `HOTKEY_TOGGLE` +
    `PANEL_SHOWN`/`PANEL_HIDDEN`, e um Ctrl+Space deixa `HOTKEY_LIVE_STEP` +
    `LIVE_ENABLED`. Uma pressao de uma tecla emparelhada com a accao da OUTRA nao
    e' uma medicao: e' a latencia de dois gestos somada.
    """
    when_press = press_when(press)
    role = (press.get("role") or "") if isinstance(press, dict) else ""
    # O PAPEL E' LIDO PELA FAMILIA, nao por igualdade: uma medicao que arma as
    # threads do proprio selftest publica `role=panels-probe`/`live-probe`
    # (`selftest_instrument.run_selftest`), e exigir a palavra exacta deixava a
    # pressao sem accao -- ausencia de medicao inventada pelo parser.
    if role.startswith("panels"):
        allowed = ("PANEL_SHOWN", "HOTKEY_TOGGLE")
    elif role.startswith("live"):
        allowed = ("LIVE_ENABLED", "HOTKEY_LIVE_STEP")
    else:
        # Log anterior ao `role=`: nao se sabe que tecla foi, por isso vale
        # qualquer accao -- o que valia antes desta versao. Nao se inventa papel.
        allowed = ("LIVE_ENABLED", "PANEL_SHOWN", "HOTKEY_TOGGLE",
                   "HOTKEY_LIVE_STEP")
    sources = {"LIVE_ENABLED": session.get("live") or [],
               "PANEL_SHOWN": session.get("panels") or [],
               "HOTKEY_TOGGLE": session.get("toggles") or [],
               "HOTKEY_LIVE_STEP": session.get("live_steps") or []}
    candidates = [(stamp, name) for name in allowed
                  for stamp in (first_after(sources[name], when_press),) if stamp]
    if not candidates:
        return (None, None, "NO-ACTION: a pressao esta no log e nenhuma accao "
                            "(%s) veio depois dela, na MESMA sessao de shell -- nao "
                            "ha gesto para medir" % "/".join(allowed))
    when, name = min(candidates)
    delta_ms = (when - when_press).total_seconds() * 1000.0
    if delta_ms <= 0:
        return (None, name, "NO-MEASURE: a accao nao e posterior a pressao (delta=%.0f ms)"
                            % delta_ms)
    return (delta_ms, name, "%s %s -> %s %s | delta=%.0f ms%s"
            % ("press", when_press.strftime("%H:%M:%S.%f")[:-3],
               name, when.strftime("%H:%M:%S.%f")[:-3][:12], delta_ms,
               (" role=%s" % role) if role else ""))


def measure(session):
    """(delta_ms | None, accao, nota) -- a PIOR das duas teclas, e nunca uma omissao verde.

    Uma sessao com as duas teclas tem duas respostas; o veredicto e' o maior
    delta (a tecla mais lenta), e se UMA delas nao tiver accao o resultado e'
    `None`: um passo que nao se mediu nao conta como portao que passou.
    """
    results = [measure_one(session, press)
               for press in first_press_per_role(session)]
    if not results:
        return (None, None, "NO-ACTION: a sessao nao tem pressao para medir")
    if any(delta is None for delta, _n, _m in results):
        first_none = next(r for r in results if r[0] is None)
        return first_none
    worst = max(results, key=lambda r: r[0])
    if len(results) > 1:
        extras = "; ".join(r[2] for r in results)
        return (worst[0], worst[1], "%s | as duas teclas: %s" % (worst[2], extras))
    return worst


def load_cost(session):
    """`WORKER_AUTOSTART=started` -> primeira pintura. INFORMACAO, nunca portao."""
    worker = session["workers"][0] if session["workers"] else None
    paint = first_after(session["paints"], worker) if worker else None
    if not worker or not paint:
        return None
    return (paint - worker).total_seconds() * 1000.0


def report(session, budget_ms):
    delta, name, nota = measure(session)
    if delta is None:
        return (None, nota)
    cost = load_cost(session)
    extra = (" | carga_do_motor=%.0f ms (informacao, NAO e' portao)" % cost) if cost else ""
    return (delta <= budget_ms,
            "%s | orcamento=%.0f ms%s" % (nota, budget_ms, extra))


def neg_arm(budget_ms):
    """O aritmetico tem de recusar o que esta fora e aceitar o que esta dentro."""
    base = datetime.datetime(2026, 10, 30, 1, 0, 0, 0)
    casos = [
        ("dentro", 300, True),
        ("fora", 1700, False),
        ("no limite", int(budget_ms), True),
        ("fora do limite", int(budget_ms) + 1, False),
    ]
    ok = True
    for nome, delta, esperado in casos:
        sessao = {"presses": [base],
                  "live": [base + datetime.timedelta(milliseconds=delta)],
                  "panels": [], "workers": [], "paints": []}
        dentro, _nota = report(sessao, budget_ms)
        bom = (dentro is esperado)
        ok = ok and bom
        print("MUTATION %-18s %s  esperado=%s obtido=%s"
              % (nome, "NEG-ARM PASS" if bom else "NEG-ARM FAIL",
                 str(esperado).lower(), str(dentro).lower()))

    # SEM ACCAO E' AUSENCIA DE MEDICAO, nunca verde
    dentro, _n = report({"presses": [base], "live": [], "panels": [],
                         "workers": [], "paints": []}, budget_ms)
    bom = dentro is None
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=None obtido=%s"
          % ("sem accao", "NEG-ARM PASS" if bom else "NEG-ARM FAIL", str(dentro).lower()))

    # A ACCAO MAIS CEDE VERDADEIRA ganha: `PANEL_SHOWN` antes de `LIVE_ENABLED`
    sessao = {"presses": [base],
              "live": [base + datetime.timedelta(milliseconds=900)],
              "panels": [base + datetime.timedelta(milliseconds=120)],
              "workers": [], "paints": []}
    dentro, nota = report(sessao, budget_ms)
    bom = dentro is True and "PANEL_SHOWN" in nota
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=PANEL_SHOWN obtido=%s"
          % ("a accao mais cedo", "NEG-ARM PASS" if bom else "NEG-ARM FAIL", nota.split("|")[0]))

    # A FRONTEIRA QUE ORIGINOU TUDO: uma sessao de shell NAO come a seguinte.
    # Uma pressao no arranque A e a accao no arranque B nao sao uma medicao.
    ev = [(base, "shell", {"pid": "1"}),
          (base + datetime.timedelta(seconds=1), "press", {"count": 1}),
          (base + datetime.timedelta(days=15), "shell", {"pid": "2"}),
          (base + datetime.timedelta(days=15, seconds=2), "live", {"on": True})]
    sessoes = sessions(ev)
    bom = len(sessoes) == 1 and sessoes[0]["live"] == []
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=accao-de-outro-arranque-recusada"
          % ("fronteira do shell",
             "NEG-ARM PASS" if bom else "NEG-ARM FAIL"))

    # CADA TECLA EMPARELA COM A SUA ACCAO (2026-11-01: duas teclas, dois gestos).
    # Uma pressao de Ctrl+Space creditada com o `HOTKEY_TOGGLE` de um Alt+C era a
    # latencia de dois gestos com o nome de um -- e o `role=` e' o que os separa.
    sessao = {"presses": [{"when": base, "role": "live"}],
              "live": [], "panels": [], "workers": [], "paints": [],
              "toggles": [base + datetime.timedelta(milliseconds=90)],
              "live_steps": []}
    dentro, nota = report(sessao, budget_ms)
    bom = dentro is None and "NO-ACTION" in nota
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=NO-ACTION (accao da OUTRA tecla recusada)"
          % ("papel errado", "NEG-ARM PASS" if bom else "NEG-ARM FAIL"))

    sessao = {"presses": [{"when": base, "role": "panels"}],
              "live": [], "panels": [], "workers": [], "paints": [],
              "toggles": [base + datetime.timedelta(milliseconds=90)],
              "live_steps": []}
    dentro, nota = report(sessao, budget_ms)
    bom = dentro is True and "HOTKEY_TOGGLE" in nota
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=HOTKEY_TOGGLE obtido=%s"
          % ("papel certo", "NEG-ARM PASS" if bom else "NEG-ARM FAIL",
             nota.split("|")[0]))

    # DUAS TECLAS NA MESMA SESSAO: o veredicto e' a PIOR (a tecla mais lenta), e
    # uma tecla sem accao NAO e' um verde -- e' ausencia de medicao.
    sessao = {"presses": [{"when": base, "role": "panels"},
                          {"when": base + datetime.timedelta(seconds=1),
                           "role": "live"}],
              "live": [base + datetime.timedelta(milliseconds=1400)],
              "panels": [], "workers": [], "paints": [],
              "toggles": [base + datetime.timedelta(milliseconds=60)],
              "live_steps": [base + datetime.timedelta(milliseconds=1400)]}
    dentro, nota = report(sessao, budget_ms)
    bom = dentro is True and "role=live" in nota
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=pior-das-duas(1400ms) obtido=%s"
          % ("duas teclas", "NEG-ARM PASS" if bom else "NEG-ARM FAIL",
             nota.split("|")[0]))

    sessao = {"presses": [{"when": base, "role": "panels"},
                          {"when": base + datetime.timedelta(seconds=1),
                           "role": "live"}],
              "live": [], "panels": [], "workers": [], "paints": [],
              "toggles": [base + datetime.timedelta(milliseconds=60)],
              "live_steps": []}
    dentro, nota = report(sessao, budget_ms)
    bom = dentro is None and "role=live" not in nota
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=None (a tecla sem accao nao passa)"
          % ("tecla muda", "NEG-ARM PASS" if bom else "NEG-ARM FAIL"))

    # delta NEGATIVO nunca e' verde, mesmo chegando ao `measure` emparelhado
    dentro, _n = report({"presses": [base],
                         "live": [base - datetime.timedelta(milliseconds=900)],
                         "panels": [], "workers": [], "paints": []}, budget_ms)
    bom = dentro is None
    ok = ok and bom
    print("MUTATION %-18s %s  esperado=None obtido=%s"
          % ("delta negativo", "NEG-ARM PASS" if bom else "NEG-ARM FAIL", str(dentro).lower()))

    print("NEG-ARM %s cases=%d" % ("PASS" if ok else "FAIL", len(casos) + 8))
    return 1


def drive(tag=None):
    """CORRE a medicao agora, no build que esta' no disco, e devolve o log DELE.

    PORQUE E' QUE O PASSO SE MEDE A SI MESMO (medido 2026-11-01). O passo lia
    `_main/webview-run.log` -- o ficheiro que a instancia do DONO escreve e que
    atravessa dias e dezenas de arranques. Numa bateria a seguir a uma mudanca de
    codigo ele respondia `MEDICAO AUSENTE: nenhuma sessao com pressao nasceu do
    build que esta' no disco` (rc=2): nao havia nada a medir, e o passo ficava
    vermelho a espera de um gesto que ninguem fez. Um `NO-MEASURE` nao pode ser o
    estado de repouso de um portao.

    `_main/pov-selftest.py --run` (o instrumento do dono, 2026-11-01) arranca uma
    SEGUNDA instancia com mutex privada, teclas livres e o token de um processo
    `high`, e o proprio selftest entrega Alt+C e Ctrl+Space pelo caminho real
    (`simulate_press` -> `WM_HOTKEY` -> `HOTKEY_PRESSED`). E' essa a medicao que
    este oraculo julga: o mesmo log traz `SHELL_STARTUP_STAGE`, `SHELL_CODE_ID` e
    as accoes.

    A TAG E' PRIVADA por run (`altc-first-caption-<pid>`), porque a tag separa
    log, runner E mutex: duas medicoes com a mesma tag matam uma a outra.
    """
    tag = tag or os.environ.get("SOTTO_POV_TAG") or "altc-first-caption-%d" % os.getpid()
    tmp = os.environ.get("SOTTO_TMP") or r"I:\cc-tmp"
    log = os.path.join(tmp, "pov-selftest-%s.log" % tag)
    driver = os.path.join(HERE, "pov-selftest.py")
    print("a medir: python _main/pov-selftest.py --run (tag=%s)" % tag)
    env = dict(os.environ, SOTTO_POV_TAG=tag)
    try:
        proc = subprocess.run([sys.executable, driver, "--run"], env=env,
                              capture_output=True, text=True, timeout=420, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except Exception as exc:                                    # noqa: BLE001
        print("MEDICAO AUSENTE: o motor da medicao nao correu: %r" % (exc,))
        return log
    tail = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()][-6:]
    print("motor rc=%d" % proc.returncode)
    for ln in tail:
        print("  " + ln[:160])
    if proc.returncode != 0:
        print("  stderr: %s" % (proc.stderr or "").strip()[-400:])
    if not os.path.isfile(log):
        print("MEDICAO AUSENTE: o motor nao escreveu %s" % log)
    return log


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Alt+C -> a accao do Alt+C: o delta medido")
    ap.add_argument("--log", default=None,
                    help="julga ESTE log; sem ele o passo MEDE agora (ver `drive`)")
    ap.add_argument("--budget-ms", type=float, default=DEFAULT_BUDGET_MS)
    ap.add_argument("--all", action="store_true", help="todas as sessoes, nao so a ultima")
    ap.add_argument("--neg-arm", action="store_true", help="muta o aritmetico; rc=1 POR DESENHO")
    ap.add_argument("--write", default=None)
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if args.neg_arm:
        return neg_arm(args.budget_ms)

    # SEM `--log` O PASSO NAO LE UM FICHEIRO QUE OUTRA SESSAO DEIXOU: mede agora.
    if args.log is None:
        args.log = drive()
    if not os.path.isfile(args.log):
        print("MEDICAO AUSENTE: log nao existe: %s" % args.log)
        print("ALTC-FIRST-CAPTION VERDICT NO-MEASURE (rc=2) -- ausencia de medicao nao e veredicto")
        return 2

    events = read_events(args.log)
    sessoes = sessions(events)
    linhas = ["log              : %s" % args.log,
              "arranques        : %d" % sum(1 for e in events if e[1] == "shell"),
              "sessoes c/ pressao: %d" % len(sessoes),
              "pressoes count=1 : %d (no ficheiro inteiro)" % sum(
                  1 for e in events if e[1] == "press" and e[2]["count"] == 1),
              "pinturas         : %d (no ficheiro inteiro)" % sum(
                  1 for e in events if e[1] == "paint"),
              "orcamento        : %.0f ms" % args.budget_ms,
              ""]
    if not sessoes:
        linhas.append("MEDICAO AUSENTE: nenhuma `HOTKEY_PRESSED count=1` DENTRO de uma "
                      "sessao de shell -- nao houve gesto para medir")
        text = "\n".join(linhas)
        print(text)
        if args.write:
            io.open(args.write, "w", encoding="utf-8", newline="").write(text + "\n")
        print("ALTC-FIRST-CAPTION VERDICT NO-MEASURE (rc=2)")
        return 2

    # UMA SESSAO DE UM BUILD ANTIGO NAO E' MEDICAO DO CODIGO DE HOJE.
    # MEDIDO 2026-10-30: o passo publicava 19030 ms (sessao de 11:26, build
    # sha256=696B1DA7E14B) enquanto o disco ja' corria outro id, e o numero foi
    # lido como se fosse da arvore actual. A sessao cujo build NAO e' o do disco
    # nao da' veredicto: diz NO-MEASURE e nomeia os dois ids.
    disco = disk_code_id()
    # Uma sessao SEM `SHELL_CODE_ID` no log e' de um build anterior a 2026-10-30:
    # nao se sabe que codigo correu, por isso nao e' evidencia de nada.
    sessoes = [x for x in sessoes if disco is None or x.get("code") == disco]
    if not sessoes:
        linhas.append("MEDICAO AUSENTE: nenhuma sessao com pressao nasceu do build "
                      "que esta' no disco (disco sha256=%s)" % (disco or "?"))
        text = "\n".join(linhas)
        print(text)
        if args.write:
            io.open(args.write, "w", encoding="utf-8", newline="").write(text + "\n")
        print("ALTC-FIRST-CAPTION VERDICT NO-MEASURE (rc=2)")
        return 2

    escolhidas = sessoes if args.all else sessoes[-1:]
    vereditos = []
    for n, sessao in enumerate(escolhidas, 1):
        dentro, nota = report(sessao, args.budget_ms)
        vereditos.append(dentro)
        linhas.append("sessao %d (pid %s): %s  %s"
                      % (n, sessao.get("pid", "?"),
                         "GREEN" if dentro else ("RED" if dentro is False else "NO-MEASURE"),
                         nota))
    text = "\n".join(linhas)
    print(text)
    if args.write:
        io.open(args.write, "w", encoding="utf-8", newline="").write(text + "\n")

    if any(v is None for v in vereditos):
        print("ALTC-FIRST-CAPTION VERDICT NO-MEASURE (rc=2)")
        return 2
    bad = [v for v in vereditos if v is False]
    print("SUMMARY sessoes=%d fora_do_orcamento=%d" % (len(vereditos), len(bad)))
    print("ALTC-FIRST-CAPTION VERDICT %s" % ("RED" if bad else "GREEN"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
