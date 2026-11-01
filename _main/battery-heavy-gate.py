"""GATE: the battery must never open the owner's world unless he asks for it.

THE OWNER, verbatim (2026-10-21, session `ses_ea36ec6efffeE7E32m9COGhkxL`,
"Estado das legendas e renderer nativo" -- the session with the Sotto messages):

    01:00:18  "e teus testes demoram muito e sao pesados. implementa caching e
              incremental test e etc."
    17:22:24  "tu ta fazendo algo que faz meu pc travar/stutter? ou é outro
              processo?"
    17:25:44  "essa porra dessa bateria ai deve ta mal otimizada ou burra entao.
              arruma. e faz cache/incremental test"
    17:39:14  "entendo por que a bateria trava e da stutter. é por que o start do
              que quer que seja, da stutter no meu computador."

WHAT THE MEASUREMENTS SAY (2026-10-21, this machine):

  * Starting ANY process costs the owner a 53-127 ms stutter. The disks are at
    0.4-20% free, so a start is a disk read and the disk queue is the owner's
    foreground.
  * Starting the app shell costs MUCH more than that: `_main/_strip-stats-log-probe.py`
    wrote down the measurement -- 63.6 s later "the box was saturated (VRAM 100 %,
    38 `msedgewebview2.exe`)". The WebView2 runtime is 38 processes and a
    saturated GPU.
  * The battery's own slow steps are the ones that start the app: measured
    `strip-stats-log-budget` 61.96 s, `strip-surface-runtime` 41.98 s,
    `tap-open-timeout` 33.78 s, `strip-geometry-restore` 29.01 s,
    `strip-stats-wave` 26.19 s, `strip-surface-oracle` 21.06 s.

  READ THE SOURCES, NOT THE NAMES. Two of those six (`tap-open-timeout`,
  `strip-surface-oracle`) start NOTHING: the first waits on a deadline
  (`time.sleep`), the second parses files. The ones that really open the owner's
  world were found by reading the spawn sites:

      _main/_strip-surface-probe.py:205    Popen([PYW, SHELL, ...])       app window
      _main/_strip-stats-log-probe.py:200  Popen([PYW, shell, ...])       app window
      _main/_strip-restore-probe.py:171    Popen(cmd)                    app window
      _main/_strip-stats-probe.py:173      Popen([PYW, SHELL, ...])       app window
      _main/panel-exit3-oracle.py:166      Popen([sys.executable, SHELL]) app (windowless)
                                            + `--device CABLE_OUT`       the audio device
      _main/mute-audio-oracle.py:215       set_volume() on the device    the audio device

  NOT heavy, and the reasons matter: `autostart-status` starts the shell with
  `--autostart-status` (it prints and exits -- no window); `hotkey-delivery`
  runs a READ-ONLY PowerShell query ("this probe must never touch the owner's
  app", its own words); the hotkey oracles instantiate the shell class with
  `object.__new__` and never create a window.

THE MECHANISM THIS GATE GUARDS (in `_main/_audit-verify-all.cmd`):

  * A step may carry the class `heavy`: `call :step heavy <name> ...`.
  * A heavy step does NOT run unless `SOTTO_BATTERY_HEAVY=1` is set. When it
    does not run it is counted in `skipped=`, NAMED in the summary under
    `heavy:`, and NEVER counted in `gate=`.
  * A CACHED heavy step is free (it starts no process) and keeps its gate.
  * The battery puts ITSELF below normal priority, so the owner's foreground
    work wins the CPU and the disk queue.

THE THREE CLAIMS. Each one is a fact about the PRODUCT, not about the text.

  C1  THE MECHANISM WORKS. Proved by RUNNING the battery's OWN labels (extracted
      verbatim from `_main/_audit-verify-all.cmd`) over a FAKE heavy step whose
      command writes a marker file, three times over: by default the marker must
      NOT exist and the step must be counted as SKIPPED (never as a gate); with
      `SOTTO_BATTERY_HEAVY=0` the marker must ALSO not exist (the opt-in is the
      VALUE "1", not the mere existence of the variable -- a caller asking for
      OFF must get OFF); with `SOTTO_BATTERY_HEAVY=1` the marker MUST exist.
      Reading the code is not proof; running it is.

  C2  THE TWO DECLARATIONS AGREE. Every step declared `heavy` in the battery
      uses an instrument that carries the `BATTERY-HEAVY:` marker, and every
      instrument that carries the marker is used by a step declared `heavy`.
      The marker lives in the instrument, next to the truth (the spawn), and the
      class lives in the battery, next to the step. A new instrument that opens
      the owner's world MUST carry the marker -- that is the review rule, and
      this gate is what makes it stick.

  C3  THE FLOOR. The heavy set is not empty, and it holds the six steps the
      source-reading found, with the kind of world each one opens. A gate whose
      claim can be satisfied by deleting a line is decoration; the floor is
      what stops that.

HEADLESS BY CONSTRUCTION: it launches no app, no browser, no audio device and
no worker. The only process it starts is a `cmd.exe` running the battery's own
labels over a fake step.

    python _main\\battery-heavy-gate.py            -> rc 0 PASS / rc 1 FAIL
    python _main\\battery-heavy-gate.py --neg-arm  -> rc 1 BY DESIGN
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD_PATH = os.path.join(ROOT, "_main", "_audit-verify-all.cmd")

CREATE_NO_WINDOW = 0x08000000

# The kind of world each known heavy step opens. The floor.
HEAVY_FLOOR = {
    "strip-surface-runtime": "app-window",
    "strip-stats-log-budget": "app-window",
    "strip-geometry-restore": "app-window",
    "strip-stats-wave": "app-window",
    "control-panel-exit3-neg-arm": "audio-device",
    "mute-audio": "audio-device",
    # 2026-10-30: o passo que mede o GESTO do dono. Nao abre janela, nao abre
    # dispositivo e nao carrega modelo -- depende da MAO do dono (uma pressao de
    # Alt+C numa sessao viva), e sem ela o instrumento responde NO-MEASURE.
    "altc-first-caption": "owner-hand",
    # 2026-10-30: o auto-relancamento do shell LARGA a app (o passo estava
    # `always` e o log da app ganhou dois `SHELL_STARTUP_STAGE` num run).
    "shell-relaunch": "app-window",
    "red-as-expected-shell-relaunch": "app-window",
}

#: `owner-hand` (2026-10-30): a medicao que so' EXISTE depois de um gesto do dono.
#: Nao e' "sem classe": e' uma classe propria, porque nenhuma bandeira de ambiente a
#: pode produzir -- e um verde inventado seria pior do que um passo que nao corre.
HEAVY_KINDS = ("app-window", "audio-device", "model", "owner-hand")

# The marker is a COMMENT AT THE START OF A LINE. Anchored on purpose: this
# file's own docstring talks about the marker, and a marker that matches prose
# makes the gate read its own documentation as a declaration (measured
# 2026-10-22: the first version did exactly that and the battery went RED on
# itself).
MARKER_RE = re.compile(
    r"^[ \t]*(?:#|//|--|REM[ \t]+)?[ \t]*BATTERY-HEAVY:[ \t]*([a-z\-]+)",
    re.M)

STEP_CALL_RE = re.compile(r"^\s*call\s+:step\s+(.*)$")
STEP_ARGS_RE = re.compile(
    r'^([A-Za-z0-9_.\-]+)\s+(\d)\s+"([^"]*)"\s+"([^"]*)"\s+(.*)$')
INSTRUMENT_RE = re.compile(r"_main[\\/][A-Za-z0-9_.\-]+")


# ---------------------------------------------------------------------------
# THE PARSER: the battery's own step lines.
# ---------------------------------------------------------------------------

def parse_steps(cmd_text: str):
    """-> [(name, always, heavy, deps, log, command, instrument)]."""
    steps = []
    for line in cmd_text.splitlines():
        m = STEP_CALL_RE.match(line)
        if not m:
            continue
        rest = m.group(1)
        always = heavy = False
        while True:
            low = rest.lower()
            if low.startswith("always "):
                always, rest = True, rest[7:]
                continue
            if low.startswith("heavy "):
                heavy, rest = True, rest[6:]
                continue
            break
        m2 = STEP_ARGS_RE.match(rest)
        if not m2:
            continue
        name, expect, deps, log, command = m2.groups()
        files = INSTRUMENT_RE.findall(command)
        instrument = files[0].replace("\\", "/") if files else None
        steps.append((name, always, heavy, deps, log, command.strip(), instrument))
    return steps


def heavy_steps(cmd_text: str):
    return {s[0]: s for s in parse_steps(cmd_text) if s[2]}


def marker_kind(instrument_text: str):
    kinds = [k for k in MARKER_RE.findall(instrument_text or "")]
    return kinds[0] if kinds else None


# ---------------------------------------------------------------------------
# C1 -- THE MECHANISM, proved by RUNNING the battery's own labels.
# ---------------------------------------------------------------------------

def label_region(cmd_text: str) -> str:
    """The battery's label block, verbatim: from `:step` to the end."""
    lines = cmd_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == ":step":
            start = i
            break
    if start is None:
        raise RuntimeError("the battery has no `:step` label")
    return "\r\n".join(lines[start:]) + "\r\n"


HARNESS_HEADER = """@echo off
setlocal EnableDelayedExpansion
cd /d "{root}"
set "ROOT={root}\\"
set "OUT={tmp}\\"
set "CACHE_STATE={tmp}\\state.json"
set "N=0"
set "GATES=0"
set "CTRLS=0"
set "SKIPN=0"
set "REDS=0"
set "MISSINGN=0"
set "BAD=0"
set "CACHEDN=0"
set "HEAVYN=0"
set "HEAVYLIST="
set "STEPLIST="
set "FAILED="
set "CONTROLLIST="
set "SKIPLIST="
set "SKIPLOGS=,"
"""

HARNESS_BODY = """call :step heavy fake-heavy 0 "{deps}" "{log}" python -c "import pathlib,sys;pathlib.Path(sys.argv[1]).write_text('RAN')" "{marker}"
call :record fake-heavy !STEP_RC!
echo HARNESS N=!N! GATES=!GATES! SKIPN=!SKIPN! HEAVYN=!HEAVYN! BAD=!BAD! STEPLIST=!STEPLIST!
exit /b 0
"""


def _harness_cmd(tmp: str) -> str:
    return os.path.join(tmp, "heavy-harness.cmd")


def _run_harness(cmd_text: str, tmp: str, heavy_env) -> dict:
    """Run the battery's own labels over a fake heavy step. -> what happened.

    `heavy_env` is the VALUE the caller puts in SOTTO_BATTERY_HEAVY: None (the
    variable is not there at all), "0" (there, and OFF) or "1" (there, and ON).
    The "0" case is not academic: MEASURED 2026-10-22, the first version of the
    battery's check was `if not defined SOTTO_BATTERY_HEAVY`, so a caller that
    set the variable to "0" (the start census did) RAN every heavy step.
    """
    deps = os.path.join(tmp, "deps.txt")
    log = os.path.join(tmp, "fake.log")
    marker = os.path.join(tmp, "marker.txt")
    with open(deps, "w", encoding="utf-8") as fh:
        fh.write("a dependency that never changes\n")
    for path in (log, marker):
        if os.path.exists(path):
            os.remove(path)

    harness = _harness_cmd(tmp)
    body = HARNESS_HEADER.format(root=ROOT, tmp=tmp.replace("\\", "/"))
    body += HARNESS_BODY.format(deps=deps, log=log, marker=marker)
    body += label_region(cmd_text)
    with open(harness, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)

    env = dict(os.environ)
    env.pop("SOTTO_BATTERY_HEAVY", None)
    if heavy_env is not None:
        env["SOTTO_BATTERY_HEAVY"] = heavy_env
    proc = subprocess.run(
        ["cmd", "/c", harness],
        capture_output=True, text=True, timeout=180, cwd=ROOT, env=env,
        creationflags=CREATE_NO_WINDOW,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    counters = {}
    for line in out.splitlines():
        if line.startswith("HARNESS "):
            for token in line.split()[1:]:
                if "=" in token:
                    key, _, val = token.partition("=")
                    counters[key] = val
    log_text = ""
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            log_text = fh.read()
    return {
        "ran": os.path.exists(marker),
        "log": log_text,
        "out": out,
        "counters": counters,
        "rc": proc.returncode,
    }


def check_mechanism(cmd_text: str, tmp: str):
    """C1. -> list of failure strings."""
    failures = []
    default = _run_harness(cmd_text, tmp, heavy_env=None)
    off = _run_harness(cmd_text, tmp, heavy_env="0")
    optin = _run_harness(cmd_text, tmp, heavy_env="1")

    # BY DEFAULT the heavy step must NOT run.
    if default["ran"]:
        failures.append(
            "C1 the heavy step RAN by default: the battery opened the owner's "
            "world without being asked (SOTTO_BATTERY_HEAVY was not set)")
    # ...and SOTTO_BATTERY_HEAVY=0 must mean OFF, not "on because it exists".
    if off["ran"]:
        failures.append(
            "C1 the heavy step RAN with SOTTO_BATTERY_HEAVY=0: the opt-in is "
            "read as the EXISTENCE of the variable instead of its VALUE, so a "
            "caller asking for OFF gets the owner's world opened")
    # ...and it must be counted as SKIPPED, never as a gate.
    gates = default["counters"].get("GATES")
    skipn = default["counters"].get("SKIPN")
    heavyn = default["counters"].get("HEAVYN")
    if gates != "0":
        failures.append(
            "C1 the heavy step was counted as %s GATE(S) when it did not run "
            "(GATES=%s): a step that did not verify is never a gate"
            % (gates, gates))
    if skipn != "1":
        failures.append(
            "C1 the heavy step was not counted as SKIPPED (SKIPN=%s, want 1): "
            "the summary would hide that the step did not run" % skipn)
    if heavyn != "1":
        failures.append(
            "C1 the heavy step was not counted in the HEAVY class (HEAVYN=%s, "
            "want 1): the summary must name it" % heavyn)
    if "BATTERY-HEAVY-SKIP" not in default["log"]:
        failures.append(
            "C1 the heavy step's log does not carry the BATTERY-HEAVY-SKIP "
            "marker: a reader of the log cannot tell that the step did not run")
    if "SKIPPED: heavy class" not in default["out"]:
        failures.append(
            "C1 the beacon does not say the step was SKIPPED as heavy: the "
            "owner reads the console, not the label")

    # WITH THE OPT-IN it must run.
    if not optin["ran"]:
        failures.append(
            "C1 with SOTTO_BATTERY_HEAVY=1 the heavy step did NOT run: the "
            "opt-in is broken and the heavy steps can never be verified")
    if optin["counters"].get("GATES") != "1":
        failures.append(
            "C1 with SOTTO_BATTERY_HEAVY=1 the heavy step was not counted as a "
            "gate (GATES=%s, want 1)"
            % optin["counters"].get("GATES"))
    return failures


# ---------------------------------------------------------------------------
# C2 + C3 -- THE DECLARATIONS.
# ---------------------------------------------------------------------------

def check_declarations(cmd_text: str, instrument_texts):
    """C2 and C3. -> list of failure strings."""
    failures = []
    heavy = heavy_steps(cmd_text)
    steps = parse_steps(cmd_text)

    # C2a: a heavy step's instrument must declare itself.
    for name, info in sorted(heavy.items()):
        inst = info[6]
        if not inst:
            failures.append("C2 the heavy step `%s` has no instrument" % name)
            continue
        text = instrument_texts.get(inst)
        if text is None:
            failures.append(
                "C2 the heavy step `%s` uses `%s`, which does not exist" %
                (name, inst))
            continue
        kind = marker_kind(text)
        if kind is None:
            failures.append(
                "C2 the heavy step `%s` uses `%s`, which does not carry the "
                "BATTERY-HEAVY: marker -- the instrument that opens the owner's "
                "world must say so where the truth is" % (name, inst))
        elif kind not in HEAVY_KINDS:
            failures.append(
                "C2 the instrument `%s` declares the kind `%s`, which is not "
                "one of %s" % (inst, kind, ", ".join(HEAVY_KINDS)))

    # C2b: an instrument that declares itself must be used by a heavy step.
    used_by_heavy = {}
    for name, info in heavy.items():
        if info[6]:
            used_by_heavy.setdefault(info[6], []).append(name)
    for inst, text in sorted(instrument_texts.items()):
        kind = marker_kind(text)
        if kind is None:
            continue
        if inst not in used_by_heavy:
            failures.append(
                "C2 the instrument `%s` declares itself HEAVY (%s) but no step "
                "that uses it is declared heavy in the battery: the "
                "declaration and the class disagree" % (inst, kind))
    for inst in sorted(used_by_heavy):
        if inst not in instrument_texts:
            failures.append("C2 the instrument `%s` does not exist" % inst)

    # C3: the floor.
    for name, kind in sorted(HEAVY_FLOOR.items()):
        if name not in heavy:
            failures.append(
                "C3 the step `%s` is missing from the HEAVY class: it opens "
                "the owner's %s (read from the source, 2026-10-21) and a "
                "battery that runs it opens the owner's world without being "
                "asked" % (name, kind))
            continue
        inst = heavy[name][6]
        text = instrument_texts.get(inst or "", "")
        got = marker_kind(text or "")
        if got != kind:
            failures.append(
                "C3 the step `%s` opens the owner's %s but its instrument `%s` "
                "declares `%s`" % (name, kind, inst, got))
    if not heavy:
        failures.append(
            "C3 the HEAVY class is EMPTY: a battery with no heavy class opens "
            "the owner's world on every run")
    return failures


# ---------------------------------------------------------------------------
# THE MUTANTS: five real defects, each one a copy with ONE change.
# ---------------------------------------------------------------------------

def _mutate_cmd_remove_heavy_check(cmd_text: str) -> str:
    """THE MECHANISM GONE: the heavy step runs like any other."""
    out, n = re.subn(
        r'if "!S_HEAVY!"=="1" if not "%SOTTO_BATTERY_HEAVY%"=="1" if not "!S_HIT!"=="1" goto step_heavyskip',
        "REM the heavy check was removed",
        cmd_text, count=1)
    if n == 0:
        raise RuntimeError("the mutant did not find the heavy check")
    return out


def _mutate_cmd_existence_not_value(cmd_text: str) -> str:
    """THE OPT-IN READ AS EXISTENCE: `SOTTO_BATTERY_HEAVY=0` turns it ON.

    This is not a hypothetical: it is the FIRST version of the battery's check
    (`if not defined SOTTO_BATTERY_HEAVY`), and MEASURED 2026-10-22 it made the
    start census -- which sets the variable to "0" -- run every heavy step and
    start the owner's app. The gate's C1 must be able to fail on it.
    """
    out, n = re.subn(
        r'if not "%SOTTO_BATTERY_HEAVY%"=="1"',
        "if not defined SOTTO_BATTERY_HEAVY",
        cmd_text, count=1)
    if n == 0:
        raise RuntimeError("the mutant did not find the heavy opt-in check")
    return out


def _mutate_cmd_remove_class(cmd_text: str) -> str:
    """THE DECLARATION GONE: a heavy step is no longer declared heavy."""
    out, n = re.subn(r"call :step heavy strip-surface-runtime ",
                     "call :step strip-surface-runtime ", cmd_text, count=1)
    if n == 0:
        raise RuntimeError("the mutant did not find the heavy declaration")
    return out


def _mutate_cmd_gate_counts(cmd_text: str) -> str:
    """THE SKIP COUNTED AS A GATE: the heavy skip lands in `gate=`."""
    out, n = re.subn(
        r"(set /a N\+=1\r?\nset /a SKIPN\+=1\r?\nif defined STEP_HEAVYSKIP \()",
        r"\1\r\n  set /a GATES+=1",
        cmd_text, count=1)
    if n == 0:
        raise RuntimeError("the mutant did not find the fastskip block")
    return out


def _mutate_instrument_remove_marker(text: str) -> str:
    """THE MARKER GONE: the instrument that opens the world stops saying so."""
    out, n = re.subn(
        r"^[ \t]*(?:#|//|--|REM[ \t]+)?[ \t]*BATTERY-HEAVY:[ \t]*[a-z\-]+[^\n]*\n",
        "", text, count=1, flags=re.M)
    if n == 0:
        raise RuntimeError("the mutant did not find the BATTERY-HEAVY marker")
    return out


MUTANTS = [
    ("M1 the heavy check is gone from the battery (the heavy step runs like "
     "any other)", "cmd", _mutate_cmd_remove_heavy_check, "C1"),
    ("M2 a step that opens the owner's world is no longer declared heavy",
     "cmd", _mutate_cmd_remove_class, "C2"),
    ("M3 the heavy skip is counted as a GATE (a step that did not run is "
     "rounded up to a pass)", "cmd", _mutate_cmd_gate_counts, "C1"),
    ("M4 the instrument that opens the owner's world stops declaring it",
     "instrument", _mutate_instrument_remove_marker, "C2"),
    ("M5 the heavy opt-in is read as the EXISTENCE of SOTTO_BATTERY_HEAVY "
     "instead of its VALUE, so a caller that asks for OFF (``=0``) gets the "
     "owner's world opened", "cmd", _mutate_cmd_existence_not_value, "C1"),
]


# ---------------------------------------------------------------------------
# THE RUNNERS.
# ---------------------------------------------------------------------------

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def collect_instrument_texts(cmd_text: str):
    texts = {}
    for name, always, heavy, deps, log, command, instrument in parse_steps(cmd_text):
        if not instrument:
            continue
        if instrument in texts:
            continue
        path = os.path.join(ROOT, instrument.replace("/", os.sep))
        texts[instrument] = read_text(path) if os.path.exists(path) else None
    return texts


def run_gate() -> int:
    cmd_text = read_text(CMD_PATH)
    texts = collect_instrument_texts(cmd_text)
    tmp = tempfile.mkdtemp(prefix="battery-heavy-gate-", dir=_tmpdir())
    try:
        failures = []
        failures += check_mechanism(cmd_text, tmp)
        failures += check_declarations(cmd_text, texts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    heavy = sorted(heavy_steps(cmd_text))
    print("BATTERY-HEAVY GATE -- the battery must not open the owner's world "
          "unless he asks")
    print("  battery: %s" % CMD_PATH)
    print("  heavy   : %d step(s) declared heavy: %s"
          % (len(heavy), ", ".join(heavy) if heavy else "-none-"))
    if failures:
        print("FAIL")
        for f in failures:
            print("  ** %s" % f)
        return 1
    print("PASS")
    print("  C1 the mechanism: a heavy step does NOT run by default and does NOT "
          "run with SOTTO_BATTERY_HEAVY=0 (the opt-in is the value \"1\", not the "
          "existence of the variable), and is counted as SKIPPED, never as a "
          "gate; with SOTTO_BATTERY_HEAVY=1 it runs and IS a gate")
    print("  C2 the declarations agree: every heavy step's instrument carries "
          "the BATTERY-HEAVY: marker and every marked instrument belongs to a "
          "heavy step")
    print("  C3 the floor: the %d known steps that open the owner's screen or "
          "his audio device are all declared heavy" % len(HEAVY_FLOOR))
    return 0


def run_neg_arm() -> int:
    cmd_text = read_text(CMD_PATH)
    texts = collect_instrument_texts(cmd_text)
    print("BATTERY-HEAVY GATE -- NEGATIVE ARM (%d mutants, each a broken copy)"
          % len(MUTANTS))
    print("  battery: %s" % CMD_PATH)
    caught = 0
    for name, target, mutate, claim in MUTANTS:
        broken_cmd = cmd_text
        broken_texts = dict(texts)
        try:
            if target == "cmd":
                broken_cmd = mutate(cmd_text)
            else:
                # the instrument that carries the marker of a HEAVY step
                heavy = heavy_steps(cmd_text)
                inst = None
                for step, info in sorted(heavy.items()):
                    if info[6] and marker_kind(texts.get(info[6]) or ""):
                        inst = info[6]
                        break
                if not inst:
                    raise RuntimeError("no instrument carries the marker")
                broken_texts[inst] = mutate(texts[inst])
        except Exception as exc:  # a mutant that could not be built proves nothing
            print("  ** %s -- THE MUTANT COULD NOT BE BUILT: %s" % (name, exc))
            continue
        tmp = tempfile.mkdtemp(prefix="battery-heavy-neg-", dir=_tmpdir())
        try:
            failures = []
            failures += check_mechanism(broken_cmd, tmp)
            failures += check_declarations(broken_cmd, broken_texts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if failures:
            caught += 1
            print("  PASS (caught) %s" % name)
            print("        -> %s" % failures[0])
        else:
            print("  ** NOT CAUGHT %s -- the gate is blind to this defect"
                  % name)
    print("NEG-ARM: %d/%d mutant(s) caught" % (caught, len(MUTANTS)))
    if caught == len(MUTANTS):
        print("NEG-ARM PASS: %d mutant(s), every one caught" % len(MUTANTS))
        print("VERDICT: FAIL (rc=1 BY DESIGN -- the negative arm is a control)")
        return 1
    print("NEG-ARM FAIL: %d mutant(s) slipped through" % (len(MUTANTS) - caught))
    print("VERDICT: FAIL")
    return 1


def _tmpdir() -> str:
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    os.makedirs(base, exist_ok=True)
    return base


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--neg-arm" in argv:
        return run_neg_arm()
    return run_gate()


if __name__ == "__main__":
    sys.exit(main())
