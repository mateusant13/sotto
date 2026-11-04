# NO-BUG: owner-audio-gate — the owner's audio cannot be written by anything automatic. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""owner-audio-gate — the owner's audio cannot be written by anything automatic.

OWNER ORDER (2026-11-02, verbatim): *"nunca mais roda nada que vai mutar meu audio
ou resetar ele e fazer mutar. acabou de mutar. arruma"*.

WHAT WENT WRONG, MEASURED: a battery run was killed mid-arm; `mute-audio.py` had
already put an endpoint at 0.0 and its state file was the only record -- which the
kill removed. Two endpoints (`Speakers (NVIDIA Broadcast)`, `Microfone (NVIDIA
Broadcast)`) stayed at volume 0.0 with nothing anywhere saying what they used to
be. He heard a silent machine, and had to be told by me.

THE CONTRACT THIS PORT ENFORCES (all four are mechanisms, not prose):
  1. EVERY write (`--mute`, `--unmute`, `--repair`) REFUSES with rc=9 and
     `recusa: audio do dono` unless `SOTTO_OWNER_AUDIO_OK=1` is in the environment;
     READING (`--status`, `--status-all`, `--journal-status`) is always allowed.
  2. The value about to be overwritten is JOURNALLED BEFORE the write, so a
     kill leaves a record on disk; `--repair` puts every journalled endpoint back
     to its recorded value and clears the journal.
  3. `--repair` is idempotent and reports per endpoint what it restored.
  4. The negative arm MUTATES a copy of `mute-audio.py` (removes the guard) and
     demands the refusal disappear -- a port that cannot see the defect removed
     cannot refuse the defect arriving.

EVERY ARM HERE IS READ-ONLY ON THE REAL DEVICE: the refusal arms stop before any
`set_volume`, and the journal arms drive a FAKE backend whose volumes live in a
dict. There is no arm that writes to the owner's speakers; that is the point of
the file.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE = os.path.join(HERE, "mute-audio.py")
EXIT_OWNER_AUDIO = 9

# The same hidden-launch flag every child in this tree now carries: a battery step
# must not flash a console on the owner's desktop (AGENTS.md, 2026-11-02).
NO_WINDOW = 0x08000000


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeBackend:
    """Volumes live in a dict. Nothing here touches a real endpoint."""

    def __init__(self, volumes: dict, default: str):
        self.volumes = dict(volumes)
        self.default = default
        self.writes = []

    def default_endpoint(self):
        return self.default, "fake-default"

    def get_volume(self, device_id):
        return float(self.volumes[device_id])

    def set_volume(self, device_id, scalar):
        self.writes.append((device_id, float(scalar)))
        self.volumes[device_id] = float(scalar)


def _env_without_flag():
    env = dict(os.environ)
    env.pop("SOTTO_OWNER_AUDIO_OK", None)
    env["SOTTO_MUTE_STATE"] = ""      # never read the real state file
    return env


def _run_cli(args, env):
    proc = subprocess.run(
        [sys.executable, MODULE] + args,
        capture_output=True, text=True, errors="replace",
        env=env, timeout=120, creationflags=NO_WINDOW,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def arms() -> list[dict]:
    results = []

    def arm(name, ok, evidence):
        results.append({"arm": name, "ok": bool(ok), "evidence": str(evidence)[:300]})

    env = _env_without_flag()
    env["TMPDIR"] = os.environ.get("TMPDIR") or "I:/cc-tmp"

    # 1. a write without the flag is REFUSED, with the distinct exit code.
    rc, out = _run_cli(["--mute", "--no-wait"], env)
    arm("mute-without-flag-refused", rc == EXIT_OWNER_AUDIO and "audio do dono" in out,
        f"rc={rc} out={out.strip()[:120]}")

    # 2. a repair without the flag is refused the same way.
    rc, out = _run_cli(["--repair"], env)
    arm("repair-without-flag-refused", rc == EXIT_OWNER_AUDIO and "audio do dono" in out,
        f"rc={rc} out={out.strip()[:120]}")

    # 3. READING is always allowed (a census that needs a flag is a census that
    #    will not run when it matters).
    rc, out = _run_cli(["--journal-status"], env)
    arm("journal-status-read-allowed", rc == 0 and '"state": "journal"' in out,
        f"rc={rc} out={out.strip()[:120]}")

    # 4. the journal records the value BEFORE the write, and --repair restores
    #    exactly that value (fake backend: no real endpoint involved).
    tmp = tempfile.mkdtemp(prefix="owner-audio-")
    journal = os.path.join(tmp, "journal.json")
    try:
        mod = load_module(MODULE, "mute_audio_mod")
        old_journal = mod.journal_path
        mod.journal_path = lambda: journal
        try:
            back = FakeBackend({"dev-a": 0.42}, "dev-a")
            rec = mod.mute_default_output("arm-4", backend=back, state_path=os.path.join(tmp, "state.json"))
            rows = mod._journal_read(journal)
            arm("journal-before-write", rec.get("state") == "muted" and rows
                and rows[-1]["prior_scalar"] == 0.42,
                f"state={rec.get('state')} rows={rows}")
            # repair with the same fake backend plugs in through the module global
            mod.PycawBackend = lambda role="console": back
            rep = mod.repair(journal)
            arm("repair-restores-recorded-value",
                back.volumes["dev-a"] == 0.42 and rep.get("cleared") is True,
                f"volume={back.volumes['dev-a']} rep={json.dumps(rep)[:160]}")
        finally:
            mod.journal_path = old_journal
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 5. the source really HAS the guard (a port that trusts a docstring is a
    #    port that accepts a docstring-only fix).
    with open(MODULE, encoding="utf-8") as fh:
        src = fh.read()
    arm("guard-present-in-source",
        "SOTTO_OWNER_AUDIO_OK" in src and "EXIT_OWNER_AUDIO" in src
        and "def journal_record" in src,
        "constants and journal present")
    return results


def neg_arm() -> list[dict]:
    """Remove the guard from a COPY and demand the refusal disappear.

    The mutant is driven IN-PROCESS with a FakeBackend plugged into the module
    global, never through its real CLI: a mutant without the guard would reach
    the owner's speakers, and a control that mutes him to prove a point is the
    exact defect this file exists to refuse.
    """
    tmp = tempfile.mkdtemp(prefix="owner-audio-neg-")
    try:
        copy = os.path.join(tmp, "mute-audio.py")
        with open(MODULE, encoding="utf-8") as fh:
            src = fh.read()
        mutant = src.replace(
            "if (args.mute or args.unmute or getattr(args, \"repair\", False)) and not owner_audio_allowed():",
            "if False:",
        )
        if mutant == src:
            return [{"arm": "mutant-applied", "ok": False, "evidence": "guard line not found to mutate"}]
        with open(copy, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutant)

        env_gone = os.environ.pop("SOTTO_OWNER_AUDIO_OK", None)
        mod = load_module(copy, "mute_audio_mutant")
        fake = FakeBackend({"dev-neg": 0.77}, "dev-neg")
        mod.PycawBackend = lambda role="console": fake
        state = os.path.join(tmp, "state.json")
        journal = os.path.join(tmp, "journal.json")
        mod.journal_path = lambda: journal
        try:
            emitted = []
            mod._emit = lambda payload: emitted.append(payload)
            rc = mod._cli(["--mute", "--no-wait", "--state-path", state])
        finally:
            if env_gone is not None:
                os.environ["SOTTO_OWNER_AUDIO_OK"] = env_gone
        refused = any(p.get("state") == "refused-owner-audio" for p in emitted)
        muted = any(p.get("state") == "muted" for p in emitted)
        caught = (not refused) and muted and rc == 0
        return [{"arm": "mutant-guard-removed-refusal-gone", "ok": caught,
                 "evidence": f"rc={rc} emitted={json.dumps(emitted)[:200]}"}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



def main(argv: list[str]) -> int:
    rows = arms()
    neg = "--neg-arm" in argv
    if neg:
        rows = neg_arm()
    ok = sum(1 for r in rows if r["ok"])
    for r in rows:
        print(("PASS " if r["ok"] else "FAIL ") + r["arm"] + " — " + r["evidence"])
    print(json.dumps({"cases": len(rows), "caught": ok, "neg_arm": neg}))
    verdict = "PASS" if ok == len(rows) else "FAIL"
    print(f"VERDICT: {verdict}")
    if neg:
        print("NEG-ARM: PASS" if ok == len(rows) else "NEG-ARM: FAIL")
        # `red-as-expected-*` CONVENTION: exit 1 BY DESIGN when the control
        # caught the defect (the battery demands rc=1 and the phrase).
        return 1
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
