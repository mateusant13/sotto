#!/usr/bin/env python3
"""THE STEP CACHE OF THE BATTERY -- one step, one fingerprint, one honest answer.

WHY THIS EXISTS (owner, 2026-10-20, verbatim: *"faz cache e teste incremental/delta
e etc pra tu parar de re rodar tudo do zero TODA HORA"*).

`_main/_audit-verify-all.cmd` runs EVERY gate from scratch on EVERY invocation, even
when not one byte of the product changed. This module is the layer that lets the
battery re-run ONLY what moved: a step is identified by the CONTENT of the files it
judges, not by their timestamps.

THE FINGERPRINT
---------------
    fingerprint(deps) = sha256 over, for every dep, sorted by path:
        <path>\0<sha256 of the file's BYTES>\n

CONTENT, never mtime: a `touch` must NOT invalidate a step (the bytes are the
same), and a rewrite with the SAME bytes must not either. Changing the CONTENT of
any dep changes the fingerprint, and therefore the step runs again.

THE HONESTY RULE (this is the whole point; a cache that can lie is worse than no
cache)
------------------------------------------------------------------------------
A step is a HIT only when ALL of these hold:

    (a) the fingerprint of the deps TODAY equals the one recorded;
    (b) the recorded rc is the rc this step is SUPPOSED to produce
        (0 for a gate/control/skipped, 1 for an expect-red step);
    (c) the log file the step produced still EXISTS and its sha256 is the one
        that was recorded.

If ANY of them fails -> MISS, and the step runs again. A failure is NEVER reused
as if it were a pass: (b) is what makes a red step red on the next run too.

The deps list may never be empty: a step with no deps has nothing to invalidate
it, so it can never be trusted -> MISS.

THE STATE
---------
    H:\sotto\_cache\battery-steps.json

one JSON object, one entry per step: the fingerprint, the rc, the exit code, the
timestamp, the log path and the log's sha256. The file is written atomically
(temp file + os.replace) so a crash mid-write cannot leave a half state behind.
A CORRUPT state file is not a crash: it is a MISS for every step.

CLI
---
    python _main/_stepcache.py check  --step NAME --deps "a;b" [--log L]
                                      [--expect-rc N] [--state FILE] [--always]
    python _main/_stepcache.py record --step NAME --deps "a;b" --rc N --log L
                                      [--state FILE]
    python _main/_stepcache.py status [--state FILE]

`check` prints EXACTLY two lines, so the .cmd can read them with `for /f`:

    HIT            rc=0
    MISS           reason=<why>

and exits 0 on HIT, 1 on MISS. `deps` is a `;`-separated list of paths,
resolved against the repo root when they are relative.

THIS MODULE OPENS NOTHING: no window, no audio device, no network. It reads
files and writes one JSON file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_STATE = os.path.join(REPO, "_cache", "battery-steps.json")

STATE_VERSION = 1
_CHUNK = 1 << 20
_HASH_NO_CACHE = bool(os.environ.get("SOTTO_HASH_NO_CACHE"))


# ── the primitives ───────────────────────────────────────────────────────────

# O CACHE DE BYTES POR PROCESSO (medido 2026-11-05). `sotto-state-page.py`
# chama `fingerprint` 650 vezes num `--check` e 991 ficheiros eram re-lidos e
# re-hasheados -- 3,57 s em `read` DOS MESMOS BYTES, e o `--neg-arm` faz nove
# dessas leituras (102,8 s). O hash de um ficheiro e' uma funcao PURA do
# conteudo, e a chave carrega `st_mtime_ns` + `st_size`: um ficheiro reescrito
# dentro do mesmo nanossegundo com o MESMO tamanho devolveria o hash antigo --
# e' o unico preco, e nenhum passo desta casa reescreve uma dependencia dessa
# forma a meio de um processo. `SOTTO_HASH_NO_CACHE=1` desliga-o.
_HASH_CACHE = {}
# A JANELA RACICAMENTE LIMPA (medido 2026-11-05, e foi a propria arm que o
# achou): dois `write` seguidos no mesmo ficheiro, com o MESMO tamanho, cabem
# no mesmo `st_mtime_ns` do NTFS -- e o memo devolvia o hash do conteudo antigo.
# Medido: `FAIL memo: reescrever o ficheiro devolveu o hash ANTIGO`. So' um
# ficheiro que ja' esta' PARADO ha' mais de 2 s entra no memo; um ficheiro que
# alguem acabou de escrever nunca e' cacheado.
_HASH_STABLE_S = 2.0


def sha256_file(path: str) -> str:
    """sha256 of a file's BYTES. Missing file -> None (never an exception)."""
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    except (OSError, ValueError):
        key = None
    stable = False
    if key is not None:
        try:
            stable = (time.time() - st.st_mtime) > _HASH_STABLE_S
        except (OSError, ValueError):
            stable = False
    if key is not None and stable and not _HASH_NO_CACHE:
        cached = _HASH_CACHE.get(key)
        if cached is not None:
            return cached
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            while True:
                block = fh.read(_CHUNK)
                if not block:
                    break
                h.update(block)
        digest = h.hexdigest()
    except (OSError, ValueError):
        return None
    if key is not None and stable and not _HASH_NO_CACHE:
        _HASH_CACHE[key] = digest
    return digest


def log_intact(log_path: str, want_sha: str) -> bool:
    """The log the step produced must still be THERE and still be the SAME BYTES.

    Two questions, both answered here and nowhere else: does the file exist,
    and is it the file that was recorded? A step whose log was deleted, or
    replaced by another run's log, has NOT been proven -- it must run again.
    """
    if not os.path.isfile(log_path):
        return False
    got = sha256_file(log_path)
    return bool(want_sha) and bool(got) and got == want_sha


def resolve(dep: str) -> str:
    """A dep is relative to the REPO ROOT (never to the cwd)."""
    if os.path.isabs(dep):
        return os.path.normpath(dep)
    return os.path.normpath(os.path.join(REPO, dep))


def _key_for(dep: str, path: str) -> str:
    """The fingerprint key of a dep: its path RELATIVE to the repo when it lives
    there (so the repo can move without invalidating everything), else absolute."""
    try:
        rel = os.path.relpath(path, REPO)
    except ValueError:                                           # pragma: no cover
        return os.path.normcase(path)
    if rel.startswith(".."):
        return os.path.normcase(path)
    return os.path.normcase(rel.replace("\\", "/"))


def split_deps(raw) -> list:
    """`a;b;c` -> [a, b, c]. Accepts a list too (the oracle passes one), and
    splits EVERY item on `;`, so `--deps "a;b"` and `--deps a b` are the same."""
    if raw is None:
        return []
    items = list(raw) if isinstance(raw, (list, tuple)) else [str(raw)]
    out = []
    for item in items:
        for part in str(item).split(";"):
            part = part.strip()
            if part:
                out.append(part)
    return out


def fingerprint(deps) -> tuple:
    """(hex, missing). `missing` is the list of deps that are not there.

    A missing dep has NO fingerprint: the step cannot be trusted, so the caller
    must treat it as a MISS.
    """
    items = split_deps(deps)
    if not items:
        return None, []
    digest = hashlib.sha256()
    missing = []
    pairs = []
    for dep in items:
        path = resolve(dep)
        if not os.path.isfile(path):
            missing.append(dep)
            continue
        pairs.append((_key_for(dep, path), dep, path))
    for key, _dep, path in sorted(pairs):
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        digest.update((sha256_file(path) or "?").encode("ascii"))
        digest.update(b"\n")
    if missing:
        return None, missing
    return digest.hexdigest(), []


# ── the state on disk ────────────────────────────────────────────────────────

def load_state(path: str = DEFAULT_STATE):
    """(state, error). A CORRUPT file is an empty state plus an error string --
    it is never an exception: a broken cache must not break the battery."""
    empty = {"version": STATE_VERSION, "steps": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return empty, None
    except (OSError, ValueError) as exc:
        return empty, "state-unreadable: %s: %s" % (type(exc).__name__, exc)
    if not isinstance(data, dict) or not isinstance(data.get("steps"), dict):
        return empty, "state-malformed: no 'steps' object"
    return data, None


def save_state(state, path: str = DEFAULT_STATE) -> bool:
    """Atomic write. The directory is created if it is not there."""
    directory = os.path.dirname(path)
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = path + ".tmp-%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        sys.stderr.write("stepcache: cannot write %s: %s\n" % (path, exc))
        try:
            os.unlink(path + ".tmp-%d" % os.getpid())
        except OSError:
            pass
        return False


# ── the two verbs ────────────────────────────────────────────────────────────

def check(step: str, deps, expect_rc: int = 0, log=None, always: bool = False,
          state_path: str = DEFAULT_STATE) -> tuple:
    """(hit, rc, reason). The HONESTY RULE lives here and nowhere else."""
    if always:
        # Never cached -- its truth is OUTSIDE the files (the registry, the
        # machine's own state). It still gets a TIMESTAMP in the state, which
        # is what the fast mode reads to decide it is too slow to run.
        return False, None, "always: this step is never cached"
    items = split_deps(deps)
    if not items:
        return False, None, "no-deps: a step with no deps can never be trusted"
    state, err = load_state(state_path)
    if err:
        return False, None, err
    entry = (state.get("steps") or {}).get(step)
    if not isinstance(entry, dict):
        return False, None, "no-entry: this step was never recorded"
    fp, missing = fingerprint(items)
    if fp is None:
        return False, None, "dep-missing: %s" % ", ".join(missing)
    if entry.get("fingerprint") != fp:
        return False, None, "fingerprint: the deps changed"
    try:
        recorded_rc = int(entry.get("rc"))
    except (TypeError, ValueError):
        return False, None, "rc-unreadable: the recorded rc is not a number"
    if recorded_rc != int(expect_rc):
        return False, None, ("rc-not-pass: recorded rc=%s, this step must "
                             "produce rc=%s" % (recorded_rc, expect_rc))
    log_path = entry.get("log")
    if not log_path:
        return False, None, "no-log: the recorded step produced no log"
    log_path = resolve(log_path)
    if log is not None:
        wanted = resolve(log)
        if os.path.normcase(wanted) != os.path.normcase(log_path):
            return False, None, "log-path: the step now logs somewhere else"
    if not log_intact(log_path, entry.get("log_sha256")):
        return False, None, "log-missing-or-changed: %s" % log_path
    return True, recorded_rc, "ok"

def record(step: str, deps, rc: int, log=None, expect_rc: int = 0,
           state_path: str = DEFAULT_STATE, t0=None) -> tuple:
    """(ok, reason). Records the step AS IT RAN. A step whose deps are missing
    is NOT recorded: there would be nothing to invalidate it later.

    `t0` is the MARKER FILE the battery writes right before the step runs; the
    elapsed time is read from its mtime. A marker is a file write, not a
    process: the battery starts a Python process for every step already, and
    one more per step would be a tax on every run to serve one mode.
    """
    items = split_deps(deps)
    if not items:
        return False, "no-deps: refusing to record a step with no deps"
    fp, missing = fingerprint(items)
    if fp is None:
        return False, "dep-missing: %s" % ", ".join(missing)
    state, err = load_state(state_path)
    if err:
        # a corrupt state is repaired by writing a fresh one -- but the step is
        # still recorded, so the run that just happened is not thrown away.
        state = {"version": STATE_VERSION, "steps": {}}
    log_path = resolve(log) if log else ""
    log_sha = sha256_file(log_path) if log_path else None
    entry = {
        "fingerprint": fp,
        "rc": int(rc),
        "exit_code": int(rc),
        "expect_rc": int(expect_rc),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "deps": items,
        "log": log_path,
        "log_sha256": log_sha,
    }
    elapsed = elapsed_since(t0)
    if elapsed is not None:
        entry["elapsed_s"] = round(elapsed, 3)
    state.setdefault("steps", {})[step] = entry
    state["version"] = STATE_VERSION
    if not save_state(state, state_path):
        return False, "state-not-written: %s" % state_path
    return True, "ok"


# ── the CLI ──────────────────────────────────────────────────────────────────

def _deps_arg(value):
    """`--deps "a;b"` and `--deps a b` are the same list of files."""
    return split_deps(value)


# ── THE TIMING, AND THE FAST MODE (owner, 2026-10-21) ────────────────────────
#: THE OWNER, verbatim: *"a bateria deve ser rapida"* / *"e teus testes demoram
#: muito e sao pesados. implementa caching e incremental test e etc."*
#:
#: THE CACHE AND THE INCREMENTAL PART WERE ALREADY THERE (a HIT reuses a step
#: whose judged CONTENT did not change -- 79 of 89 steps in the run of
#: 2026-10-21). What was MISSING is the other half: **nobody could say which
#: step was slow**, because nothing measured the time. So:
#:
#:   * every step records how long it took (`elapsed_s`), and the summary
#:     prints the slowest ones -- the table is the answer to "what is heavy";
#:   * `SOTTO_BATTERY_FAST=1` SKIPS the steps that were slower than the
#:     threshold in the last run, and the summary says which ones it skipped
#:     and how long they had taken. A skipped step is NOT a gate that passed.
#:
#: The threshold is in the environment because the owner knows his machine and
#: the battery does not.
FAST_MODE_ENV = "SOTTO_BATTERY_FAST"
FAST_THRESHOLD_ENV = "SOTTO_BATTERY_FAST_S"
FAST_THRESHOLD_DEFAULT_S = 20.0


def fast_mode() -> bool:
    """Is the FAST MODE on? (the owner's env var, the only switch)."""
    return str(os.environ.get(FAST_MODE_ENV) or "").strip().lower() in (
        "1", "true", "yes", "on")


def fast_threshold_s() -> float:
    """How slow is too slow for the fast mode (seconds)."""
    raw = str(os.environ.get(FAST_THRESHOLD_ENV) or "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return FAST_THRESHOLD_DEFAULT_S
    return value if value > 0 else FAST_THRESHOLD_DEFAULT_S


def elapsed_since(t0) -> float | None:
    """Seconds since the marker file `t0` was written, or None."""
    if not t0:
        return None
    try:
        return max(0.0, time.time() - os.path.getmtime(str(t0)))
    except OSError:
        return None


def elapsed_of(step: str, state_path: str = DEFAULT_STATE):
    """The duration recorded for `step` in the last run that ran it, or None."""
    state, err = load_state(state_path)
    if err:
        return None
    entry = (state.get("steps") or {}).get(step)
    if not isinstance(entry, dict):
        return None
    try:
        return float(entry.get("elapsed_s"))
    except (TypeError, ValueError):
        return None


def slowest(state_path: str = DEFAULT_STATE, top: int = 10):
    """[(step, seconds), ...] -- the slowest steps of the last run, worst first.

    Only the steps that RAN have a duration; a step reused from the cache
    carries the duration of the run that produced its log, which is the number
    that matters ("this step is heavy even when it is cached").
    """
    state, err = load_state(state_path)
    if err:
        return []
    rows = []
    for name, entry in (state.get("steps") or {}).items():
        if not isinstance(entry, dict):
            continue
        try:
            seconds = float(entry.get("elapsed_s"))
        except (TypeError, ValueError):
            continue
        rows.append((name, seconds))
    rows.sort(key=lambda row: (-row[1], row[0]))
    return rows[:max(1, int(top))]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="_stepcache.py",
        description="the per-step cache of the Sotto verification battery")
    sub = parser.add_subparsers(dest="verb")

    def add_state(p):
        p.add_argument("--state", default=DEFAULT_STATE,
                       help="the state file (default: %s)" % DEFAULT_STATE)

    p_check = sub.add_parser("check", help="is this step already proven?")
    add_state(p_check)
    p_check.add_argument("--step", required=True)
    p_check.add_argument("--deps", nargs="+", default=[],
                         help="the files this step judges: --deps a;b OR --deps a b")
    p_check.add_argument("--log", default=None)
    p_check.add_argument("--expect-rc", type=int, default=0)
    p_check.add_argument("--always", action="store_true",
                         help="never cached (a step whose truth is outside the files)")

    p_rec = sub.add_parser("record", help="record a step that just ran")
    add_state(p_rec)
    p_rec.add_argument("--step", required=True)
    p_rec.add_argument("--deps", nargs="+", default=[],
                       help="the files this step judges: --deps a;b OR --deps a b")
    p_rec.add_argument("--rc", type=int, required=True)
    p_rec.add_argument("--log", default=None)
    p_rec.add_argument("--expect-rc", type=int, default=0,
                       help="the rc this step is supposed to produce (kept for "
                            "the reader; the check compares against it)")
    # THE MARKER FILE (2026-10-21). `record` reads the elapsed time from the
    # mtime of the marker the battery writes right before the step runs. The
    # flag was MISSING here and the CLI's `record` died with
    # `AttributeError: 'Namespace' object has no attribute 't0'` -- which is
    # why the cache's own oracle arm (h) went RED: the arm that says "the CLI
    # answers HIT/MISS as announced" was asking a CLI that could not record.
    p_rec.add_argument("--t0", default=None,
                       help="the marker file whose mtime is the step's start")

    p_status = sub.add_parser("status", help="what the cache knows")
    add_state(p_status)
    p_status.add_argument("--step", default=None)

    p_slow = sub.add_parser("slowest",
                             help="the slowest steps of the last run")
    add_state(p_slow)
    p_slow.add_argument("--top", type=int, default=10)

    args = parser.parse_args(argv)
    if args.verb is None:
        parser.print_help()
        return 2

    if args.verb == "check":
        hit, rc, reason = check(args.step, _deps_arg(args.deps),
                                expect_rc=args.expect_rc, log=args.log,
                                always=args.always, state_path=args.state)
        elapsed = elapsed_of(args.step, args.state)
        # THE FAST MODE. A step that was SLOWER than the threshold in the last
        # run is skipped -- and the answer says so, with the number, so the
        # battery's summary can name it instead of quietly dropping it.
        if fast_mode() and elapsed is not None and elapsed > fast_threshold_s():
            sys.stdout.write("SKIP-SLOW\nelapsed=%.3f\nthreshold=%.3f\n"
                             % (elapsed, fast_threshold_s()))
            return 2
        if hit:
            sys.stdout.write("HIT\nrc=%s\nelapsed=%s\n"
                             % (rc, "" if elapsed is None else "%.3f" % elapsed))
            return 0
        sys.stdout.write("MISS\nreason=%s\nelapsed=%s\n"
                         % (reason, "" if elapsed is None else "%.3f" % elapsed))
        return 1

    if args.verb == "slowest":
        rows = slowest(args.state, args.top)
        for name, seconds in rows:
            sys.stdout.write("%-44s %8.2f s\n" % (name, seconds))
        return 0

    if args.verb == "record":
        ok, reason = record(args.step, _deps_arg(args.deps), args.rc,
                            log=args.log, expect_rc=args.expect_rc,
                            state_path=args.state, t0=args.t0)
        if ok:
            sys.stdout.write("RECORDED %s rc=%s\n" % (args.step, args.rc))
            return 0
        sys.stdout.write("RECORD-FAILED %s reason=%s\n" % (args.step, reason))
        sys.stderr.write("stepcache: %s: %s\n" % (args.step, reason))
        return 1

    state, err = load_state(args.state)
    if err:
        print("STATE UNREADABLE: %s" % err)
    steps = state.get("steps") or {}
    if args.step:
        entry = steps.get(args.step)
        if not entry:
            print("%-40s (not recorded)" % args.step)
            return 1
        rows = [(args.step, entry)]
    else:
        rows = sorted(steps.items())
    for name, entry in rows:
        print("%-40s rc=%-3s log=%s" % (name, entry.get("rc"),
                                        os.path.basename(entry.get("log") or "-")))
        print("    fingerprint : %s" % (entry.get("fingerprint") or "-"))
        print("    deps        : %s" % ", ".join(entry.get("deps") or []))
        print("    log sha256  : %s" % (entry.get("log_sha256") or "-"))
        print("    timestamp   : %s" % (entry.get("timestamp") or "-"))
    print("steps in the state: %d" % len(steps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
