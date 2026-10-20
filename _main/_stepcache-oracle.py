#!/usr/bin/env python3
"""ORACLE for the battery's own cache -- `_main/_stepcache.py`.

Owner, 2026-10-20, verbatim: *"faz cache e teste incremental/delta e etc pra tu
parar de re rodar tudo do zero TODA HORA"*. The engine that makes that possible
is `_main/_stepcache.py`; this file is the gate that says the engine is HONEST.

A cache that can lie is worse than no cache: a gate that reuses yesterday's log
after today's product changed is a battery that answers "GREEN" about code it
never looked at. So the claim this oracle pins is not "the cache is fast", it is
"the cache only says HIT when the CONTENT it fingerprinted is still the content
on disk, the rc it recorded is still a pass, and the log it points at is still
there, byte for byte".

ARMS (in its own temp dir; the REAL state and the REAL battery are never touched)
    a  conteudo inalterado            -> HIT
    b  conteudo alterado              -> MISS
    c  rc!=0 gravado                  -> MISS  (a failure is never reused as a pass)
    d  log apagado                    -> MISS
    e  log alterado                   -> MISS
    f  deps vazio                     -> MISS  (nothing to invalidate it)
    g  estado em disco corrompido     -> MISS, and NO crash
    h  a CLI responde HIT/MISS        -> the announced contract, byte for byte
    i  mtime sozinho                  -> HIT    (the fingerprint is CONTENT, not time)
    j  o conjunto de deps mudou       -> MISS
    k  expect-red (rc=1) gravado      -> HIT    (the battery's red-by-design steps)
    l  dep em falta                   -> MISS, and NO crash
    m  o estado real e a bateria real  -> untouched by this oracle

NEGATIVE ARM (executed, not decorative)
    Four BROKEN COPIES of the engine. Each copy is a TEXTUAL patch of a unique
    anchor; an anchor that is missing or ambiguous is DECORATIVE and the oracle
    refuses to count it. Each mutant is loaded and the SAME battery runs against
    it, and the mutant must go RED on ITS OWN claim:

      1. the fingerprint is ignored      -> b must go RED (changed content reused)
      2. the log is not checked at all   -> d AND e must go RED
      3. a recorded rc!=0 is accepted    -> c must go RED
      4. the log's sha256 is ignored     -> e must go RED (a swapped log reused)

Usage:
    python _main/_stepcache-oracle.py          # arms + mutants, rc=0 on PASS

It opens no window, no audio device, no network. Its temp dir is
`I:\\cc-tmp\\stepcache-test-<pid>\\` (never `_main\\_audit-verify`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_stepcache.py")
BATTERY = os.path.join(HERE, "_audit-verify-all.cmd")
REAL_STATE = os.path.join(os.path.dirname(HERE), "_cache", "battery-steps.json")

EXIT_PASS = 0
EXIT_FAIL = 1


# ── helpers ──────────────────────────────────────────────────────────────────

def load_engine(path: str, name: str):
    """Load an engine (or a MUTANT of one) from a path."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def sha256_file(path: str):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            h.update(fh.read())
        return h.hexdigest()
    except OSError:
        return None


def run_cli(engine_path: str, args, root: str, tag: str):
    """Run the engine's CLI. stdout/stderr go to FILES, never to a pipe: this
    sandbox denies CreatePipe (measured in `_main/_audit-embedded-js-check.py`)."""
    out = os.path.join(root, "%s.out" % tag)
    err = os.path.join(root, "%s.err" % tag)
    with open(out, "wb") as fo, open(err, "wb") as fe:
        proc = subprocess.run(
            [sys.executable, engine_path] + list(args),
            stdout=fo, stderr=fe,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc.returncode, read_text(out), read_text(err)


def workdir_root() -> str:
    base = os.environ.get("TMPDIR") or r"I:\cc-tmp"
    if not os.path.isdir(base):
        base = tempfile.gettempdir()
    path = os.path.join(base, "stepcache-test-%d" % os.getpid())
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    return path


class Fix:
    """A fixture: two deps and a log, on disk."""

    def __init__(self, root: str, name: str):
        self.dir = os.path.join(root, name)
        os.makedirs(self.dir, exist_ok=True)
        self.dep = os.path.join(self.dir, "dep.txt")
        self.dep2 = os.path.join(self.dir, "dep2.txt")
        self.log = os.path.join(self.dir, "step.log")
        self.write(self.dep, "A\n")
        self.write(self.dep2, "B\n")
        self.write(self.log, "log line 1\n")

    @staticmethod
    def write(path: str, text: str) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


# ── the battery that runs against the engine AND against every mutant ───────

def battery(engine, root: str, tag: str):
    """(rows, engine_path). The SAME battery for the real engine and for every
    mutant: the arms call the engine's own API, and arm (h) calls its CLI."""
    rows = []
    state = os.path.join(root, "state-%s.json" % tag)
    engine_path = getattr(engine, "__file__", ENGINE)

    def add(ok, name, detail=""):
        rows.append((bool(ok), name, detail))

    # (a) conteudo inalterado -> HIT
    fx = Fix(root, tag + "-a")
    deps = "%s;%s" % (fx.dep, fx.dep2)
    engine.record("s-a", deps, 0, log=fx.log, state_path=state)
    hit, rc, why = engine.check("s-a", deps, 0, log=fx.log, state_path=state)
    add(hit and rc == 0, "a conteudo inalterado -> HIT",
        "hit=%s rc=%s (%s)" % (hit, rc, why))

    # (b) conteudo alterado -> MISS
    Fix.write(fx.dep, "A ALTERADO\n")
    hit, rc, why = engine.check("s-a", deps, 0, log=fx.log, state_path=state)
    add((not hit) and rc is None, "b conteudo alterado -> MISS",
        "hit=%s (%s)" % (hit, why))

    # (c) rc!=0 gravado -> MISS
    engine.record("s-c", deps, 3, log=fx.log, state_path=state)
    hit, rc, why = engine.check("s-c", deps, 0, log=fx.log, state_path=state)
    add(not hit, "c rc!=0 gravado -> MISS", "hit=%s (%s)" % (hit, why))

    # (d) log apagado -> MISS
    fx_d = Fix(root, tag + "-d")
    deps_d = "%s;%s" % (fx_d.dep, fx_d.dep2)
    engine.record("s-d", deps_d, 0, log=fx_d.log, state_path=state)
    os.unlink(fx_d.log)
    hit, rc, why = engine.check("s-d", deps_d, 0, log=fx_d.log, state_path=state)
    add(not hit, "d log apagado -> MISS", "hit=%s (%s)" % (hit, why))

    # (e) log alterado -> MISS
    fx_e = Fix(root, tag + "-e")
    deps_e = "%s;%s" % (fx_e.dep, fx_e.dep2)
    engine.record("s-e", deps_e, 0, log=fx_e.log, state_path=state)
    Fix.write(fx_e.log, "log line 1 -- REPLACED\n")
    hit, rc, why = engine.check("s-e", deps_e, 0, log=fx_e.log, state_path=state)
    add(not hit, "e log alterado -> MISS", "hit=%s (%s)" % (hit, why))

    # (f) deps vazio -> MISS
    hit, rc, why = engine.check("s-f", "", 0, log=fx.log, state_path=state)
    add(not hit, "f deps vazio -> MISS", "hit=%s (%s)" % (hit, why))

    # (g) estado em disco corrompido -> MISS, sem crash
    state_g = os.path.join(root, "state-%s-corrupt.json" % tag)
    Fix.write(state_g, "{not json at all ][")
    hit, rc, why = engine.check("s-a", deps, 0, log=fx.log, state_path=state_g)
    add(not hit, "g estado corrompido -> MISS sem crash",
        "hit=%s (%s)" % (hit, why))

    # (h) a CLI responde HIT/MISS como anunciado
    cli_state = os.path.join(root, "state-%s-cli.json" % tag)
    fx_h = Fix(root, tag + "-h")
    deps_h = "%s;%s" % (fx_h.dep, fx_h.dep2)
    rc0, out0, err0 = run_cli(engine_path, [
        "record", "--step", "s-h", "--deps", deps_h, "--rc", "0",
        "--log", fx_h.log, "--state", cli_state], root, tag + "-h-rec")
    rc1, out1, err1 = run_cli(engine_path, [
        "check", "--step", "s-h", "--deps", deps_h, "--log", fx_h.log,
        "--state", cli_state], root, tag + "-h-hit")
    Fix.write(fx_h.dep, "A ALTERADO\n")
    rc2, out2, err2 = run_cli(engine_path, [
        "check", "--step", "s-h", "--deps", deps_h, "--log", fx_h.log,
        "--state", cli_state], root, tag + "-h-miss")
    cli_ok = (rc0 == 0 and rc1 == 0 and rc2 == 1
              and out1 == "HIT\nrc=0\n"
              and out2.startswith("MISS\nreason=")
              and out2.count("\n") == 2)
    add(cli_ok, "h a CLI responde HIT/MISS como anunciado",
        "record rc=%s | hit rc=%s out=%r | miss rc=%s out=%r"
        % (rc0, rc1, out1, rc2, out2.splitlines()[0] if out2 else ""))

    # (i) mtime sozinho -> HIT (o fingerprint e o CONTEUDO)
    fx_i = Fix(root, tag + "-i")
    deps_i = "%s;%s" % (fx_i.dep, fx_i.dep2)
    engine.record("s-i", deps_i, 0, log=fx_i.log, state_path=state)
    Fix.write(fx_i.dep, "A\n")           # the SAME bytes, a NEW mtime
    hit, rc, why = engine.check("s-i", deps_i, 0, log=fx_i.log, state_path=state)
    add(hit, "i mtime sozinho -> HIT (conteudo, nao mtime)",
        "hit=%s (%s)" % (hit, why))

    # (j) o conjunto de deps mudou -> MISS
    fx_j = Fix(root, tag + "-j")
    deps_j1 = fx_j.dep
    deps_j2 = "%s;%s" % (fx_j.dep, fx_j.dep2)
    engine.record("s-j", deps_j1, 0, log=fx_j.log, state_path=state)
    hit, rc, why = engine.check("s-j", deps_j2, 0, log=fx_j.log, state_path=state)
    add(not hit, "j o conjunto de deps mudou -> MISS",
        "hit=%s (%s)" % (hit, why))

    # (k) expect-red (rc=1) gravado -> HIT
    fx_k = Fix(root, tag + "-k")
    deps_k = "%s;%s" % (fx_k.dep, fx_k.dep2)
    engine.record("s-k", deps_k, 1, log=fx_k.log, state_path=state)
    hit1, rc1_, why1 = engine.check("s-k", deps_k, 1, log=fx_k.log, state_path=state)
    hit0, rc0_, why0 = engine.check("s-k", deps_k, 0, log=fx_k.log, state_path=state)
    add(hit1 and not hit0, "k expect-red rc=1 -> HIT (rc=0 nesse passo -> MISS)",
        "expect1 hit=%s | expect0 hit=%s (%s)" % (hit1, hit0, why0))

    # (l) dep em falta -> MISS, sem crash
    hit, rc, why = engine.check("s-l", "%s;%s" % (fx.dep,
                                                   os.path.join(root, "nao-existe.txt")),
                                0, log=fx.log, state_path=state)
    add(not hit, "l dep em falta -> MISS sem crash", "hit=%s (%s)" % (hit, why))

    return rows


# ── the mutants ─────────────────────────────────────────────────────────────

MUTANTS = [
    ("fingerprint-ignorado",
     ["b conteudo alterado -> MISS"],
     '    if entry.get("fingerprint") != fp:\n'
     '        return False, None, "fingerprint: the deps changed"',
     '    if False:\n'
     '        return False, None, "fingerprint: the deps changed"'),
    ("log-nunca-verificado",
     ["d log apagado -> MISS", "e log alterado -> MISS"],
     '    if not os.path.isfile(log_path):\n'
     '        return False\n'
     '    got = sha256_file(log_path)\n'
     '    return bool(want_sha) and bool(got) and got == want_sha',
     '    return True'),
    ("rc-nao-passe-aceito",
     ["c rc!=0 gravado -> MISS"],
     '    if recorded_rc != int(expect_rc):',
     '    if False:'),
    ("sha256-do-log-ignorado",
     ["e log alterado -> MISS"],
     '    return bool(want_sha) and bool(got) and got == want_sha',
     '    return bool(got)'),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass

    if not os.path.isfile(ENGINE):
        print("RED   engine missing: %s" % ENGINE)
        return EXIT_FAIL
    with open(ENGINE, "r", encoding="utf-8", newline="") as fh:
        source = fh.read()

    real_state_before = sha256_file(REAL_STATE)
    battery_before = sha256_file(BATTERY)

    root = workdir_root()
    started = time.monotonic()
    try:
        print("ARMS (the cache's own claims; state and battery are MINE)")
        engine = load_engine(ENGINE, "stepcache_live")
        rows = battery(engine, root, "live")
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        arms_green = sum(1 for ok, _, _ in rows if ok)
        arms_total = len(rows)
        print("\n  %d/%d" % (arms_green, arms_total))

        print("\nNEGATIVE ARM (broken copies of the engine must go RED)")
        caught = 0
        weak = 0
        for idx, (label, expected, old, new) in enumerate(MUTANTS):
            hits = source.count(old)
            if hits != 1:
                print("  RED   mutant %-28s ANCHOR %s -- oracle is stale"
                      % (label, "MISSING" if hits == 0 else "AMBIGUOUS"))
                weak += 1
                continue
            path = os.path.join(root, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_engine(path, "stepcache_mut_%d" % idx)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-28s DECORATIVO: nao carregou (%s)"
                      % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                mrows = battery(bad, root, "mut%d" % idx)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-28s a bateria rebentou (%s)"
                      % (label, type(exc).__name__))
                weak += 1
                continue
            reds = [name for ok, name, _ in mrows if not ok]
            missing = [e for e in expected if e not in reds]
            if not missing:
                print("  GREEN mutant %-28s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            elif not reds:
                print("  RED   mutant %-28s SURVIVED -- the gate is blind here"
                      % label)
            else:
                print("  RED   mutant %-28s caught by the WRONG claim (%s); "
                      "its own claim held: %s"
                      % (label, "; ".join(reds[:3]), "; ".join(missing)))
        total = len(MUTANTS)

        # (m) the REAL state and the REAL battery were not touched
        real_state_after = sha256_file(REAL_STATE)
        battery_after = sha256_file(BATTERY)
        untouched = (real_state_before == real_state_after
                     and battery_before == battery_after)
        print("\n  %s m o estado real e a bateria real nao foram tocados "
              "(state %s, battery %s)"
              % ("GREEN" if untouched else "RED  ",
                 "igual" if real_state_before == real_state_after else "MUDOU",
                 "igual" if battery_before == battery_after else "MUDOU"))
        arms_total += 1
        arms_green += 1 if untouched else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)

    took = time.monotonic() - started
    ok = (arms_green == arms_total and caught == total and weak == 0)
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d  (%.1fs)"
          % ("PASS" if ok else "FAIL", arms_green, arms_total, caught, total, took))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram nada."
              % weak)
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
