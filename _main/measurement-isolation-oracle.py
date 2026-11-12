#!/usr/bin/env python3
"""measurement-isolation-oracle -- uma MEDICAO escreve o estado do DONO?

O DEFEITO, medido por leitura em 2026-11-12 e fechado no mesmo dia. A pergunta
"esta largada e' a app ou uma medicao?" estava escrita DUAS vezes, e as duas
copias discordavam:

  * o LOCK (`main()`) pergunta `_measurement_flag(args)` e cai em
    `measurement_lock_name` -> `--probe-v2` toma `Local\\SottoShell.m.probe_v2`;
  * a ISOLACAO DO ESTADO (`isolated_state_path`) perguntava
    `args.mutex_name != DEFAULT_MUTEX_NAME`, e `--probe-v2` NAO toca em
    `--mutex-name`.

Logo uma largada `--probe-v2`/`--probe-stats`/`--exit-after`/`--dump-dom`/
`--selftest`/`--memory`/`--no-hotkey`/`--probe-outside-click`/`--probe-edit-mode`
tinha lock privado e escrevia `_main\\panel-state.json` e
`_main\\panel-visibility.json` por cima dos ficheiros da app VIVA do dono. O
segundo e' o que o worker OBEDECE (`PanelVisibilityReader`: `visible` decide
parque, `shed` decide o nivel), por isso o sintoma nao e' cosmetico: a sonda
publicava `visible=false` e o worker dele mudava de modo, e publicava um payload
sem `park`/`shed` e o nivel de shedding perdia-se.

O QUE ESTE ORACULO JULGA, seis arms, nenhuma larga a app e nenhuma abre janela:

  A1  app do dono         -> caminho byte-identico, zero flag no argv do worker
  A2  `--probe-v2`        -> os DOIS ficheiros isolados, e o sufixo e' o NOME QUE
                             O LOCK TOMA (as duas decisoes nao podem divergir)
  A3  `--mutex-name X`    -> o sufijo e' X (o caminho sancionado do POV)
  A4  as nove flags       -> TODAS isolam (a tabela e' uma so')
  A5  estrutural          -> `start_panel_visibility` passa o caminho ISOLADO ao
                             writer e o snapshot publica `writer.path`, nunca a
                             constante
  A6  vivo                -> executa o `start_panel_visibility` REAL contra um
                             diretorio temporario: uma escrita chega ao ficheiro
                             isolado e o ficheiro da APP NAO EXISTE

`--neg-arm` corre a MESMA populacao contra tres copias mutiladas da shell e cada
mutante tem de cair pela SUA arm (rc=1 quando apanha, que e' a convencao desta
casa: um negativo que devolve 0 ao apanhar e' um portao que nao pode falhar).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

STATE = os.path.join(ROOT, "_main", "panel-state.json")
VISIBILITY = os.path.join(ROOT, "_main", "panel-visibility.json")

#: As nove flags da familia. Lida AQUI de proposito: se a tabela da shell ganhar
#: uma decima, esta lista nao a conhece e a A4 diz isso em vez de a ignorar.
MEASUREMENT_ATTRS = (
    ("dump_dom", "--dump-dom"),
    ("selftest", "--selftest"),
    ("memory", "--memory"),
    ("no_hotkey", "--no-hotkey"),
    ("exit_after", "--exit-after"),
    ("probe_v2", "--probe-v2"),
    ("probe_stats", "--probe-stats"),
    ("probe_outside_click", "--probe-outside-click"),
    ("probe_edit_mode", "--probe-edit-mode"),
)

MUTANT_VISIBILITY_OFF = (
    "        path = self.isolated_state_path(PANEL_VISIBILITY_PATH)",
    "        path = PANEL_VISIBILITY_PATH",
)
MUTANT_PREDICATE_OLD = (
    "    if _measurement_flag(args):\n"
    "        return True\n"
    "    mutex = str(getattr(args, 'mutex_name', '') or '')\n"
    "    return bool(mutex) and mutex != DEFAULT_MUTEX_NAME",
    "    mutex = str(getattr(args, 'mutex_name', '') or '')\n"
    "    return bool(mutex) and mutex != DEFAULT_MUTEX_NAME",
)
MUTANT_ARGV_OFF = (
    "    isolated_visibility = isolated_state_file(PANEL_VISIBILITY_PATH, args)\n"
    "    if isolated_visibility != PANEL_VISIBILITY_PATH:\n"
    "        tail += ['--panel-visibility', isolated_visibility]\n",
    "",
)


def load_shell(path, name):
    # O ficheiro importa os IRMAOS (`hot_reload`, `panel_state`, ...) por nome,
    # e uma copia vive num diretorio temporario: sem o diretorio REAL da shell
    # no `sys.path` a copia morre em `ModuleNotFoundError` e o braco negativo
    # mede o veneno do proprio instrumento em vez do mutante. MEDIDO 2026-11-12:
    # os tres mutantes "nao apanhados" por `No module named 'hot_reload'`.
    for directory in (os.path.dirname(os.path.abspath(path)),
                      os.path.dirname(os.path.abspath(SHELL))):
        if directory not in sys.path:
            sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def app_args(mod, **extra):
    """A largada do DONO: nenhuma flag de medicao, mutex por omissao."""
    args = SimpleNamespace(mutex_name=mod.DEFAULT_MUTEX_NAME)
    for attr, _name in MEASUREMENT_ATTRS:
        setattr(args, attr, False)
    args.worker_threads = 0
    args.speakers = False
    for key, value in extra.items():
        setattr(args, key, value)
    return args


def probe_args(mod, **flags):
    args = app_args(mod)
    for attr in flags:
        setattr(args, attr, True)
    return args


def run_cases(mod):
    got = {}

    # -- A1: a app do dono nao muda de sitio, byte a byte ------------------
    owner = app_args(mod)
    got["a1_owner_not_measurement"] = mod.is_measurement_launch(owner) is False
    got["a1_state_untouched"] = (
        mod.isolated_state_file(STATE, owner) == STATE
        and mod.isolated_state_file(VISIBILITY, owner) == VISIBILITY)
    got["a1_worker_argv_clear"] = mod.worker_argv_tail(owner) == []

    # -- A2: uma flag de medicao isola os DOIS ficheiros ------------------
    probe = probe_args(mod, probe_v2=True)
    lock = mod.measurement_lock_name(probe)
    want_tag = re.sub(r"[^A-Za-z0-9_.-]", "_", lock)
    state_p = mod.isolated_state_file(STATE, probe)
    vis_p = mod.isolated_state_file(VISIBILITY, probe)
    argv = mod.worker_argv_tail(probe)
    got["a2_probe_is_measurement"] = mod.is_measurement_launch(probe) is True
    got["a2_state_isolated"] = state_p != STATE and state_p.endswith(want_tag + ".json")
    got["a2_visibility_isolated"] = vis_p != VISIBILITY and vis_p.endswith(want_tag + ".json")
    # O sufixo E' o nome do lock: a decisao do lock e a do estado sao a mesma.
    got["a2_tag_matches_lock"] = mod.measurement_state_tag(probe) == want_tag
    got["a2_worker_reads_the_same_file"] = (
        "--panel-visibility" in argv
        and argv[argv.index("--panel-visibility") + 1] == vis_p)

    # -- A3: `--mutex-name` explicito (o caminho sancionado do POV) --------
    named = app_args(mod, mutex_name="SottoPovSelftest")
    got["a3_named_mutex_isolates"] = (
        mod.measurement_state_tag(named) == "SottoPovSelftest"
        and mod.isolated_state_file(STATE, named).endswith(
            "panel-state.SottoPovSelftest.json"))

    # -- A4: as NOVE flags, uma por uma --------------------------------
    missed = []
    for attr, flag in MEASUREMENT_ATTRS:
        one = probe_args(mod, **{attr: True})
        if not (mod.is_measurement_launch(one)
                and mod.isolated_state_file(VISIBILITY, one) != VISIBILITY
                and "--panel-visibility" in mod.worker_argv_tail(one)):
            missed.append(flag)
    got["a4_all_flags_isolate"] = not missed
    got["a4_flags_missed"] = missed

    # -- A5: as duas metades ESTRUTURAIS do ficheiro que embarca ----------
    # LE-SE O FICHEIRO DO MODULO CARREGADO, nunca `SHELL`: no braco negativo o
    # modulo E' a copia mutilada, e ler a shell viva fazia esta arm aprovar o
    # mutante (medido 2026-11-12: M1 caia em tres arms e a A5 continuava True).
    source_path = getattr(mod, "__file__", SHELL)
    text = open(source_path, encoding="utf-8").read()
    tree = ast.parse(text)
    body = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "start_panel_visibility", "panel_visibility_snapshot",
                "worker_argv_tail"):
            body[node.name] = ast.get_source_segment(text, node) or ""
    start = body.get("start_panel_visibility", "")
    snap = body.get("panel_visibility_snapshot", "")
    got["a5_writer_gets_isolated_path"] = (
        "path = self.isolated_state_path(PANEL_VISIBILITY_PATH)" in start
        and "path=path," in start
        and "path=PANEL_VISIBILITY_PATH" not in start)
    got["a5_snapshot_names_the_writer"] = "'path': writer.path" in snap

    # -- A6: o caminho VIVO, com o metodo REAL e um diretorio temporario ---
    got.update(run_live(mod))
    return got


def run_live(mod):
    """Executa `start_panel_visibility` a serio contra um root temporario.

    O ficheiro e' DESCARTAVEL e nenhum dispositivo ou janela entra no caminho: o
    writer e' o real, `observe` devolve False (nao ha janela nesta corrida), e o
    que se mede e' ONDE a escrita aterra.
    """
    out = {"a6_isolated_file_written": False, "a6_live_file_untouched": False,
           "a6_snapshot_path_is_the_file": False, "a6_detail": ""}
    tmp = tempfile.mkdtemp(prefix="sotto-isolation-")
    saved = (mod.PANEL_VISIBILITY_PATH, mod.PANEL_VISIBILITY_INTERVAL_S)
    live = os.path.join(tmp, "panel-visibility.json")
    mod.PANEL_VISIBILITY_PATH = live
    mod.PANEL_VISIBILITY_INTERVAL_S = 3600.0   # so' a escrita EXPLICITA acontece
    try:
        probe = probe_args(mod, probe_v2=True)
        fake = SimpleNamespace(args=probe, panel_visibility=None)
        fake.observe_panel_visible = lambda: False
        fake.geometry_snapshot = lambda: {}
        fake.shedding_level = lambda: None
        fake.engine_park_reason = lambda: None
        for name in ("isolated_state_path", "start_panel_visibility",
                     "panel_visibility_snapshot"):
            setattr(fake, name, getattr(mod.SottoShell, name).__get__(fake))
        fake.start_panel_visibility()
        writer = fake.panel_visibility
        writer.write("oracle")
        deadline = time.time() + 5.0
        while time.time() < deadline and not os.path.exists(writer.path):
            time.sleep(0.02)
        snap = fake.panel_visibility_snapshot()
        out["a6_isolated_file_written"] = (
            writer.path != live and os.path.exists(writer.path))
        out["a6_live_file_untouched"] = not os.path.exists(live)
        out["a6_snapshot_path_is_the_file"] = (
            isinstance(snap, dict) and snap.get("path") == writer.path)
        out["a6_detail"] = "writer=%s live=%s exists=%s" % (
            os.path.basename(writer.path), os.path.basename(live),
            os.path.exists(live))
        writer.stop("oracle")
    except Exception as exc:                                    # noqa: BLE001
        out["a6_detail"] = "raised %r" % (exc,)
    finally:
        mod.PANEL_VISIBILITY_PATH, mod.PANEL_VISIBILITY_INTERVAL_S = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return out


ARMS = ("a1_owner_not_measurement", "a1_state_untouched", "a1_worker_argv_clear",
        "a2_probe_is_measurement", "a2_state_isolated", "a2_visibility_isolated",
        "a2_tag_matches_lock", "a2_worker_reads_the_same_file",
        "a3_named_mutex_isolates", "a4_all_flags_isolate",
        "a5_writer_gets_isolated_path", "a5_snapshot_names_the_writer",
        "a6_isolated_file_written", "a6_live_file_untouched",
        "a6_snapshot_path_is_the_file")


def judge(got):
    bad = [name for name in ARMS if not got.get(name)]
    return bad


def run_mutant(label, old, new, arms_that_must_fail):
    """Uma copia da shell com UMA mutilacao; devolve as arms que caíram."""
    text = open(SHELL, encoding="utf-8").read()
    if old not in text:
        return None, ["%s: anchor missing" % label]
    tmp = tempfile.mkdtemp(prefix="sotto-mutant-")
    path = os.path.join(tmp, "sotto_webview_mutant.py")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new, 1))
    try:
        mod = load_shell(path, "sotto_shell_mutant_" + re.sub(r"\W", "_", label))
        got = run_cases(mod)
        fell = [name for name in ARMS if not got.get(name)]
    except Exception as exc:                                    # noqa: BLE001
        fell = ["%s: raised %r" % (label, exc)]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    missing = [name for name in arms_that_must_fail if name not in fell]
    return fell, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("measurement-isolation-oracle -- a medicao escreve o estado do dono? (sem largar a app)")

    if parsed.neg_arm:
        cases = (
            ("M1-visibility-nao-isolada", MUTANT_VISIBILITY_OFF[0],
             MUTANT_VISIBILITY_OFF[1],
             ("a5_writer_gets_isolated_path", "a6_isolated_file_written",
              "a6_live_file_untouched")),
            ("M2-predicado-antigo", MUTANT_PREDICATE_OLD[0], MUTANT_PREDICATE_OLD[1],
             ("a2_probe_is_measurement", "a2_state_isolated",
              "a2_visibility_isolated", "a4_all_flags_isolate")),
            ("M3-argv-sem-a-flag", MUTANT_ARGV_OFF[0], MUTANT_ARGV_OFF[1],
             ("a2_worker_reads_the_same_file", "a4_all_flags_isolate")),
        )
        ok = 0
        for label, old, new, must in cases:
            fell, missing = run_mutant(label, old, new, must)
            caught = fell is not None and not missing
            ok += 1 if caught else 0
            say("  %-26s %s fallen=%s%s" % (
                label, "CAUGHT" if caught else "NOT-CAUGHT",
                ",".join(fell or []) or "-",
                "" if not missing else "  sem-cair=" + ",".join(missing)))
        say("")
        say("NEG-ARM: %s -- %d/%d mutantes apanhados" % (
            "PASS" if ok == len(cases) else "FAIL", ok, len(cases)))
        return 1 if ok == len(cases) else 0

    live = load_shell(SHELL, "sotto_shell_isolation")
    got = run_cases(live)
    for name in ARMS:
        say("  live  " + name.ljust(34) + str(got.get(name)))
    if got.get("a4_flags_missed"):
        say("  live  a4 flags sem isolacao             " + ",".join(got["a4_flags_missed"]))
    say("  live  a6 detail                          " + str(got.get("a6_detail")))
    bad = judge(got)
    say("")
    if bad:
        say("VERDICT: FAIL -- %d/%d arms" % (len(ARMS) - len(bad), len(ARMS)))
        for name in bad:
            say("  failed: " + name)
        return 1
    say("VERDICT: PASS -- %d/%d arms" % (len(ARMS), len(ARMS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
