#!/usr/bin/env python3
"""O PLANO DA BATERIA: todas as respostas do cache de uma corrida, num processo.

O DEFEITO QUE ISTO FECHA (MEDIDO, 2026-11-05)

A `.cmd` pergunta ao cache **um passo de cada vez**, com um `python` novo por
passo (`for /f ... in ('python _main\\_stepcache.py check ...')`, ~linha 2949).
Medido nesta maquina, seis invocacoes de um passo ja' cacheado:

    min 0,124 s   max 0,150 s por passo   ->  319 passos = 43,1 s

Numa corrida a QUENTE -- em que nada precisa de executar -- a bateria gastava
~43 s so' a criar interpretadores que leem o mesmo JSON e dizem `HIT`. O alvo da
casa e' 60 s: isso era 72 % do alvo gasto em dispensa.

O QUE ESTE FICHEIRO FAZ: le as declaracoes `call :step ...` do proprio `.cmd`,
carrega o estado UMA vez, responde a todos os passos NO MESMO PROCESSO e escreve
um plano que a `.cmd` le com `for /f` (uma leitura de ficheiro, zero processos
por passo).

O CONTRATO E' O DO CLI, NAO UM PARECIDO. `_stepcache.check()`, `elapsed_of()` e a
regra do modo rapido vivem em `_stepcache.py`; este ficheiro importa-os e
reproduz a MESMA arvore de decisao que o subcomando `check` imprime (`HIT` /
`MISS` / `SKIP-SLOW` + `rc=` + `elapsed=` + `threshold=`). O `--selftest`
compara as duas saidas, passo a passo.

A GRAMATICA DAS DECLARACOES tem UMA definicao na casa: `STEP_RE`, em
`_main/sotto-state-page.py` (e' ela que conta os declarados contra os registados
e recusa um passo declarado que nao corre). Este ficheiro importa-a -- dois
regexes para a mesma linha divergiriam em silencio.

PLANO (uma linha por passo, `|` separado -- nenhuma `deps` deste ficheiro tem `|`):

    <nome>|<HIT|MISS|SKIP-SLOW>|<rc|->|<elapsed|->|<threshold|->

Um passo cujo nome se repete mantem a PRIMEIRA ocorrencia, que e' a ordem em que
`call :step` chega.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CMD = os.path.join(HERE, "_audit-verify-all.cmd")
OUT_DIR = os.path.join(HERE, "_audit-verify")
DEFAULT_STATE = os.path.join(REPO, "_cache", "battery-steps.json")
DEFAULT_PLAN = os.path.join(REPO, "_cache", "battery-plan.txt")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_KNOWN_ENV = {
    "%ROOT%": REPO,
    "%OUT%": OUT_DIR,
    "%CACHE_STATE%": DEFAULT_STATE,
}


def _expand(text):
    """`%OUT%`/`%ROOT%`/`%CACHE_STATE%` -> caminho real; o resto fica literal.

    Um `%VAR%` desconhecido (ou um `!VAR!` de expansao atrasada) fica como esta':
    o dep nao resolve, o cache responde `dep-missing` e o passo CORRE. Errar para
    o lado de correr e' o unico lado seguro.
    """
    for key, value in _KNOWN_ENV.items():
        text = text.replace(key, value)
    return text


def declarations(cmd_path=CMD):
    """[(nome, expect_rc, always, deps, log)] na ordem em que o `.cmd` os declara."""
    page = _load("_sotto_state_page", os.path.join(HERE, "sotto-state-page.py"))
    rows = []
    seen = set()
    with io.open(cmd_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = page.STEP_RE.match(line)
            if not m:
                continue
            always, _heavy, name, expect, deps, log, _command = m.groups()
            if name in seen:
                continue
            seen.add(name)
            rows.append((name, int(expect), bool(always),
                         _expand(deps), _expand(log)))
    return rows


def _depends_on_state(deps, state_path):
    """Um dep que E' o ficheiro de estado -> o passo nao entra no plano."""
    target = os.path.normcase(os.path.abspath(state_path))
    for dep in deps.split(";"):
        dep = dep.strip()
        if not dep:
            continue
        if os.path.normcase(os.path.abspath(dep)) == target:
            return True
    return False


def answer(sc, name, expect, always, deps, log, state_path, fast, threshold):
    """(verdict, rc, elapsed, threshold_or_None) -- a MESMA arvore do CLI `check`."""
    hit, rc, _reason = sc.check(name, sc.split_deps(deps), expect_rc=expect,
                                log=log or None, always=always,
                                state_path=state_path)
    elapsed = sc.elapsed_of(name, state_path)
    elapsed_s = "" if elapsed is None else "%.3f" % elapsed
    if fast and elapsed is not None and elapsed > threshold:
        return "SKIP-SLOW", "-", elapsed_s, "%.3f" % threshold
    if hit:
        return "HIT", str(rc), elapsed_s, ""
    return "MISS", "-", elapsed_s, ""


def build(out_path=DEFAULT_PLAN, state_path=DEFAULT_STATE, cmd_path=CMD):
    sc = _load("_stepcache_plan", os.path.join(HERE, "_stepcache.py"))
    fast = sc.fast_mode()
    threshold = sc.fast_threshold_s()
    t0 = time.perf_counter()
    rows = []
    for name, expect, always, deps, log in declarations(cmd_path):
        if _depends_on_state(deps, state_path):
            # O ESTADO MUDA DURANTE A CORRIDA. A resposta a este passo tem de
            # ser dada no instante em que ele corre (o caminho por passo), nao
            # aqui: um plano que adivinha sobre um ficheiro que a propria corrida
            # reescreve e' a unica forma de este cache mentir.
            rows.append((name, "DEFER", "-", "", ""))
            continue
        verdict, rc, elapsed, thr = answer(sc, name, expect, always, deps,
                                           log, state_path, fast, threshold)
        rows.append((name, verdict, rc, elapsed, thr))
    tmp = out_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write("%s|%s|%s|%s|%s\n" % row)
    os.replace(tmp, out_path)
    hits = sum(1 for r in rows if r[1] == "HIT")
    defer = sum(1 for r in rows if r[1] == "DEFER")
    return {"steps": len(rows), "hits": hits, "defer": defer,
            "misses": len(rows) - hits - defer,
            "fast": fast, "threshold": threshold,
            "build_s": round(time.perf_counter() - t0, 3), "out": out_path}


# ── o selftest: o plano TEM de dar a MESMA resposta que o CLI ────────────────
def _selftest():
    import json
    import shutil
    import subprocess
    import tempfile

    sc = _load("_stepcache_selftest", os.path.join(HERE, "_stepcache.py"))
    page = _load("_sotto_state_page_st", os.path.join(HERE, "sotto-state-page.py"))
    problems = []

    # (A) A GRAMATICA E' A MESMA: o censo da pagina de estado e o plano nao
    # podem discordar sobre o conjunto de passos declarados.
    here = declarations()
    pages = []
    with io.open(CMD, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = page.STEP_RE.match(line)
            if m:
                pages.append(m.group(3))
    if sorted(set(pages)) != sorted(n for n, *_ in here):
        problems.append("gramatica: plano=%d nomes, state-page=%d nomes"
                        % (len(here), len(set(pages))))

    root = tempfile.mkdtemp(prefix="sotto-battery-plan-")
    try:
        # (B) AS RESPOSTAS: um estado sintetico com as quatro formas que existem
        # (HIT, `always`, LENTO e MISS por dep que mudou), respondido pelo plano
        # e pelo CLI, comparados um a um.
        state = os.path.join(root, "state.json")
        files = {}
        for name in ("a.py", "b.py"):
            files[name] = os.path.join(root, name)
            io.open(files[name], "w", encoding="utf-8").write("x = 1\n")
        logs = {}
        for step in ("passo-hit", "passo-always", "passo-lento", "passo-miss"):
            logs[step] = os.path.join(root, step + ".log")
            io.open(logs[step], "w", encoding="utf-8").write("VERDICT: PASS\n")
        cache = {"version": 1, "steps": {}}
        for step, deps, elapsed in (("passo-hit", [files["a.py"]], 0.5),
                                    ("passo-lento", [files["a.py"]], 5.0),
                                    ("passo-miss", [files["b.py"]], 0.2)):
            fp, missing = sc.fingerprint(deps)
            assert fp and not missing, (fp, missing)
            cache["steps"][step] = {
                "fingerprint": fp, "rc": 0, "exit_code": 0, "expect_rc": 0,
                "deps": deps, "log": logs[step],
                "log_sha256": sc.sha256_file(logs[step]), "elapsed_s": elapsed,
            }
        io.open(state, "w", encoding="utf-8").write(json.dumps(cache))
        # o dep do `passo-miss` muda DEPOIS de registado: tem de dar MISS
        io.open(files["b.py"], "w", encoding="utf-8").write("x = 2\n")

        cmd_file = os.path.join(root, "fake.cmd")
        with io.open(cmd_file, "w", encoding="utf-8", newline="\n") as fh:
            for step, deps, always in (
                    ("passo-hit", files["a.py"], ""),
                    ("passo-always", files["a.py"], "always "),
                    ("passo-lento", files["a.py"], ""),
                    ("passo-miss", files["b.py"], "")):
                fh.write('call :step %s%s 0 "%s" "%s" python x.py\n'
                         % (always, step, deps, logs[step]))

        def _cli(step, deps, always):
            cmd = [sys.executable, os.path.join(HERE, "_stepcache.py"), "check",
                   "--step", step, "--expect-rc", "0", "--deps", deps,
                   "--log", logs[step], "--state", state]
            if always:
                cmd.append("--always")
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            verdict = ("HIT" if "HIT" in out
                       else "SKIP-SLOW" if "SKIP-SLOW" in out else "MISS")
            rc = "-"
            for line in out.splitlines():
                if line.startswith("rc="):
                    rc = line[3:].strip() or "-"
            return verdict, rc

        def _compare(tag, fast):
            if fast:
                os.environ[sc.FAST_MODE_ENV] = "1"
                os.environ[sc.FAST_THRESHOLD_ENV] = "1"
            else:
                os.environ.pop(sc.FAST_MODE_ENV, None)
                os.environ.pop(sc.FAST_THRESHOLD_ENV, None)
            out = os.path.join(root, "plan-%s.txt" % tag)
            info = build(out, state, cmd_file)
            plan = {}
            for line in io.open(out, encoding="utf-8"):
                name, verdict, rc = line.rstrip("\n").split("|")[:3]
                plan[name] = (verdict, rc)
            for step, deps, always in (
                    ("passo-hit", files["a.py"], False),
                    ("passo-always", files["a.py"], True),
                    ("passo-lento", files["a.py"], False),
                    ("passo-miss", files["b.py"], False)):
                want = _cli(step, deps, always)
                got = plan.get(step)
                if got != want:
                    problems.append("%s %s: CLI=%r plano=%r"
                                    % (tag, step, want, got))
            os.environ.pop(sc.FAST_MODE_ENV, None)
            os.environ.pop(sc.FAST_THRESHOLD_ENV, None)
            return info

        off = _compare("normal", False)
        on = _compare("rapido", True)
        # O PLANO TEM DE DECIDIR: sem estes dois, um plano quebrado que responde
        # MISS a tudo passava o selftest.
        if off["hits"] != 2:
            problems.append("modo normal: hits=%d (esperado 2: hit e lento)"
                            % off["hits"])
        if on["hits"] != 1:
            problems.append("modo rapido: hits=%d (o lento vira SKIP-SLOW)"
                            % on["hits"])

        # (C) O NUMERO QUE JUSTIFICA ISTO, medido neste mesmo estado.
        t0 = time.perf_counter()
        for step, deps, always in (
                ("passo-hit", files["a.py"], False),
                ("passo-always", files["a.py"], True),
                ("passo-lento", files["a.py"], False),
                ("passo-miss", files["b.py"], False)):
            _cli(step, deps, always)
        per_step = (time.perf_counter() - t0) / 4.0
        print("por passo (CLI) : %.3f s  -> 319 passos = %.1f s"
              % (per_step, per_step * 319))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # (E) O MEMO DE BYTES NAO MENTE (medido 2026-11-05). O `sha256_file` do
    # `_stepcache` guarda o hash por (caminho, mtime, tamanho) e isso cortou o
    # `sotto-state-page.py --check` de 6,1 s para 3,2 s -- mas o preco declarado
    # e' que um ficheiro REESCRITO com o MESMO tamanho tem de dar outro hash, e
    # que a segunda leitura de um ficheiro PARADO nao volta a ler o disco.
    try:
        sc = _load("_stepcache_hasharm", os.path.join(HERE, "_stepcache.py"))
    except Exception as exc:                        # noqa: BLE001
        sc = None
        problems.append("memo de bytes: o _stepcache nao carrega (%s)" % exc)
    if sc is not None:
        import tempfile as _tf
        d = _tf.mkdtemp(prefix="sotto-hash-")
        try:
            f = os.path.join(d, "alvo.bin")
            with io.open(f, "wb") as fh:
                fh.write(b"AAAA")
            h1 = sc.sha256_file(f)
            memo_before = len(getattr(sc, "_HASH_CACHE", {}))
            h1b = sc.sha256_file(f)
            memo_after = len(getattr(sc, "_HASH_CACHE", {}))
            if h1 != h1b:
                problems.append("memo: a leitura repetida mudou o hash (%r/%r)"
                                % (h1, h1b))
            if memo_after != memo_before:
                problems.append("memo: a segunda leitura entrou no cache outra vez "
                                "(%d -> %d) -- o memo nao esta' a valer"
                                % (memo_before, memo_after))
            with io.open(f, "wb") as fh:
                fh.write(b"BBBB")           # MESMO tamanho, outro conteudo
            h2 = sc.sha256_file(f)
            if h2 == h1:
                problems.append("memo: reescrever o ficheiro devolveu o hash ANTIGO "
                                "-- o memo serve um resultado errado")
            print("memo de bytes   : repetido=sem-leitura reescrito=hash-novo "
                  "(%d entradas)" % memo_after)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # (D) A MEDICAO REAL, no ficheiro real: o plano inteiro de uma corrida.
    real = build(os.path.join(tempfile.gettempdir(), "sotto-plan-selftest.txt"))
    print("plano real      : %d passos em %.3f s (hits=%d misses=%d defer=%d)"
          % (real["steps"], real["build_s"], real["hits"], real["misses"],
             real["defer"]))
    if real["defer"] < 1:
        problems.append("plano real: defer=%d (nenhum passo depende do estado -- "
                        "a regra do DEFER nao esta' a ver nada)" % real["defer"])
    if real["steps"] < 200:
        problems.append("plano real: %d passos (a gramatica perdeu passos)"
                        % real["steps"])
    if problems:
        for p in problems:
            print("FAIL %s" % p)
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


# ── o braco negativo: as mutacoes que o selftest TEM de apanhar ──────────────
_NEG_MUTANTS = (
    ("hit-inventado",
     'if hit:\n        return "HIT", str(rc), elapsed_s, ""',
     'if True:\n        return "HIT", "0", elapsed_s, ""'),
    ("defer-apagado",
     '        if _depends_on_state(deps, state_path):',
     '        if False and _depends_on_state(deps, state_path):'),
    ("skip-slow-apagado",
     '    if fast and elapsed is not None and elapsed > threshold:',
     '    if False and fast and elapsed is not None and elapsed > threshold:'),
)


def _run_adjacent(text, tag):
    """Corre uma copia AO LADO do original e devolve `(rc, out)`.

    AO LADO, e nao num directorio temporario (medido 2026-11-05): o selftest
    resolve `CMD`, `DEFAULT_STATE` e as DEPS dos passos por caminhos relativos
    `HERE`/`REPO`, logo uma copia noutra arvore media `hits=0 misses=343
    defer=0` sobre ficheiros que nao existem la' -- o controle positivo da
    copia LIMPA caia e os tres mutantes eram "apanhados" por um
    `FileNotFoundError` em vez da sua arm. Ao lado, tudo o que o selftest le'
    e' o da arvore de verdade, e o unico byte diferente e' o mutante.
    """
    import subprocess
    copy = os.path.join(HERE, "_battery-plan.mutant-%s.py" % tag)
    try:
        io.open(copy, "w", encoding="utf-8", newline="\n").write(text)
        r = subprocess.run([sys.executable, copy, "--selftest"],
                           capture_output=True, text=True, cwd=REPO)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    finally:
        try:
            os.remove(copy)
        except OSError:
            pass


def neg_arm():
    """Cada mutacao numa COPIA ao lado; o selftest da copia TEM de cair.

    Devolve 1 quando as apanha (a convencao da casa: `--neg-arm` sai 1 ao
    apanhar, porque o passo declara `expect-rc=1`), 0 quando uma sobrevive.
    """
    import shutil

    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    caught = 0
    problems = []
    table_at = src.find("_NEG_MUTANTS = (")
    for tag, needle, replacement in _NEG_MUTANTS:
        # A ancora tem de estar no CODIGO, e nao so' na propria tabela de
        # mutantes (uma ancora que so' casa consigo mesma plantaria o mutante
        # dentro da tabela e nao mudaria comportamento nenhum).
        at = src.find(needle)
        if at < 0 or table_at < 0 or at > table_at:
            problems.append("%s: a ancora nao esta' no codigo (at=%d, tabela=%d)"
                            % (tag, at, table_at))
            continue
        rc, out = _run_adjacent(src.replace(needle, replacement, 1), tag)
        if "Traceback (most recent call last)" in out:
            problems.append("%s: a copia MORREU (excepcao, nao arm) -- "
                            "mutante nao julgado" % tag)
            continue
        fails = [l for l in out.splitlines() if l.startswith("FAIL ")]
        if rc != 0 and fails:
            caught += 1
            print("CAUGHT %-18s rc=%d %s" % (tag, rc, fails[:1]))
        elif rc != 0:
            problems.append("%s: rc=%d SEM linha FAIL -- nao se sabe o que caiu"
                            % (tag, rc))
        else:
            problems.append("%s: o selftest da copia PASSOU (mutante vivo)" % tag)

    # O CONTROLE POSITIVO: a mesma copia, SEM mutacao, tem de dar `VERDICT: PASS`.
    rc, out = _run_adjacent(src, "ctrl")
    if rc != 0 or "VERDICT: PASS" not in out:
        problems.append("controle: a copia LIMPA nao passou (rc=%d, traceback=%s)"
                        % (rc, "Traceback" in out))
    else:
        print("CONTROLE copia limpa: VERDICT PASS (rc=0)")

    if problems:
        for p in problems:
            print("NOT-CAUGHT %s" % p)
        print("NEG-ARM: FAIL -- %d/%d" % (caught, len(_NEG_MUTANTS)))
        return 0
    print("NEG-ARM: PASS -- %d mutantes, %d apanhados" % (len(_NEG_MUTANTS), caught))
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="_battery-plan.py", description="todas as respostas do cache, num processo")
    ap.add_argument("--cmd", default=CMD, help="the battery whose steps are declared")
    ap.add_argument("--out", default=DEFAULT_PLAN)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--neg-arm", action="store_true",
                    help="as mutacoes que o --selftest tem de apanhar (sai 1 ao apanhar)")
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    if args.selftest:
        return _selftest()
    info = build(args.out, args.state, args.cmd)
    sys.stdout.write("PLAN steps=%d hits=%d misses=%d defer=%d fast=%s build_s=%.3f out=%s\n"
                     % (info["steps"], info["hits"], info["misses"], info["defer"],
                        str(info["fast"]).lower(), info["build_s"], info["out"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
