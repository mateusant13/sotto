#!/usr/bin/env python
"""ORACLE: THE MUTE -- SILENT BY CONSTRUCTION, AND IT COMES BACK EXACTLY.

The owner's order, 2026-10-19, verbatim:
    "se tu vai usar audio padrao pra testar qualquer coisa, muta. nao quero
     ficar ouvindo."

Until now the protection was a REFUSAL: a probe that wanted the default
endpoint walked away with rc=4 ("AUDIBLE-DEVICE") unless SOTTO_ALLOW_AUDIBLE=1
was set. This gate covers the other door -- the MUTE (`_main/mute-audio.py`),
which lets the test run while the owner's speakers stay at 0.

A mute that is only "usually right" is worse than no mute at all, because the
owner cannot tell the difference between "the test was silent" and "the test
never ran". So the arms below measure the four things that can go wrong:

    the mute does not happen      the volume is not 0 afterwards
    the mute is half done         the device is left at 0 with no way back
    the restore is wrong          it comes back as 50%, or as the system
                                  default, or as nothing at all
    the restore is lost           the saved volume disappears on a failure

MEASURED ON THIS BOX (2026-10-19), and the reason the arms are written the
way they are:
  * the default RENDER endpoint is "VoiceMeeter Input (VB-Audio VoiceMeeter
    VAIO)" -- role eConsole and eMultimedia resolve to the SAME device;
    eCommunications resolves to a DIFFERENT one, so the role matters;
  * the master volume is a SCALAR in 0..1 (`SetMasterVolumeLevel` is
    DECIBELS, and +50 dB is an invalid parameter on this endpoint);
  * a scalar round trip is FLOAT32-QUANTIZED: set 0.37 and the device reads
    back 0.3700000047683716. The volume that comes back MUST be the volume
    that was READ -- so the arms compare against the value read AFTER the
    write, never against the value written.

THE NEGATIVE ARM breaks the mute eight ways. The one the owner cares about
most is `unmute-restores-the-literal-50-not-the-saved-value`: a restore
that puts a fixed 50 instead of the value it found looks perfectly healthy
and leaves the owner with the wrong volume for the rest of the day.

RUN
    python _main/mute-audio-oracle.py            # arms + mutants, rc=0 on PASS
    python _main/mute-audio-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = r"H:\sotto"
MAIN_DIR = os.path.join(REPO, "_main")
MODULE_PATH = os.path.join(MAIN_DIR, "mute-audio.py")

EXIT_PASS, EXIT_FAIL = 0, 1
# The owner's screen must never show a console window. Same flags the repo
# uses elsewhere: CREATE_NO_WINDOW | DETACHED_PROCESS.
NO_WINDOW = 0x08000000 | 0x00000008

AUDIO_LIBS = ("sounddevice", "numpy", "pyaudio", "winsound", "wave",
              "simpleaudio", "sherpa_onnx", "onnxruntime")


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeBackend:
    """A device that does exactly what we TELL it to -- including wrongly.

    `fail_set_on` raises (the endpoint blew up); `silent_fail_on` accepts the
    write and does NOT apply it (the mute that did not happen). The second
    one is the dangerous one: nothing raises, nothing prints, and the owner's
    speakers stay at full volume.
    """

    def __init__(self, default="A", volumes=None, fail_set_on=None,
                 silent_fail_on=None):
        self.volumes = dict(volumes or {"A": 0.75, "B": 0.9})
        self.default = default
        self.fail_set_on = fail_set_on
        self.silent_fail_on = silent_fail_on

    def default_endpoint(self):
        return (self.default, "Fake " + self.default)

    def get_volume(self, device_id):
        return float(self.volumes[device_id])

    def set_volume(self, device_id, scalar):
        scalar = float(scalar)
        if self.fail_set_on is not None and scalar == self.fail_set_on:
            raise RuntimeError("COMError simulado: o dispositivo rebentou")
        if self.silent_fail_on is not None and scalar == self.silent_fail_on:
            return  # a write that does NOT take effect
        self.volumes[device_id] = scalar


def battery(mod, mod_path: str, workdir: str, source: str) -> list:
    out = []

    def attempt(name, fn):
        """An exception is a RED with a reason -- never a crash of the run."""
        try:
            ok, detail = fn()
        except Exception as exc:                                # noqa: BLE001
            ok, detail = False, "REBENTOU com %s: %s" % (type(exc).__name__, exc)
        out.append((bool(ok), name, detail))
        return bool(ok)

    states = []

    def state_path(tag: str) -> str:
        path = os.path.join(workdir, "state-%s.json" % tag)
        states.append(path)
        return path

    # ------------------------------------------------------------------
    # THE REAL ENDPOINT. The owner's volume goes back to what it was in
    # the `finally`, whatever happens above.
    # ------------------------------------------------------------------
    backend = mod.PycawBackend()
    device_id, device_name = backend.default_endpoint()
    original = backend.get_volume(device_id)
    # A test value that is NOT the system default: "it came back to the
    # default" has to be distinguishable from "it came back to my value".
    test_value = 0.37 if abs(original - 0.37) > 1e-6 else 0.63

    try:
        def a1():
            return (bool(device_id) and bool(device_name),
                    "%s | %s" % (device_name, device_id))
        attempt("o endpoint default de render resolve", a1)

        def a2():
            st = state_path("a2")
            res = mod.mute_default_output("oracle", backend=backend, state_path=st)
            now = backend.get_volume(device_id)
            mod.unmute_default_output(backend=backend, state_path=st)
            return (res.get("state") == "muted" and now == 0.0,
                    "state=%r volume_durante_o_mute=%r" % (res.get("state"), now))
        attempt("mute põe o volume a 0", a2)

        def a3():
            st = state_path("a3")
            backend.set_volume(device_id, test_value)
            saved = backend.get_volume(device_id)     # what the device READS
            mod.mute_default_output("oracle", backend=backend, state_path=st)
            mod.unmute_default_output(backend=backend, state_path=st)
            back = backend.get_volume(device_id)
            return (back == saved,
                    "guardado=%r restaurado=%r igual=%s" % (saved, back, back == saved))
        attempt("unmute restaura EXACTAMENTE o valor guardado", a3)

        def a4():
            st = state_path("a4")
            backend.set_volume(device_id, test_value)
            saved = backend.get_volume(device_id)
            mod.mute_default_output("oracle", backend=backend, state_path=st)
            mod.unmute_default_output(backend=backend, state_path=st)
            back = backend.get_volume(device_id)
            return (back == saved and back != original,
                    "guardado=%r restaurado=%r default_do_sistema=%r" % (saved, back, original))
        attempt("unmute restaura o MEU valor, nao o default do sistema", a4)

        def a5():
            st = state_path("a5")
            backend.set_volume(device_id, test_value)
            saved = backend.get_volume(device_id)
            mod.mute_default_output("oracle", backend=backend, state_path=st)
            second = mod.mute_default_output("oracle-2", backend=backend, state_path=st)
            mod.unmute_default_output(backend=backend, state_path=st)
            back = backend.get_volume(device_id)
            return (back == saved and second.get("already_muted") is True,
                    "guardado=%r restaurado=%r already_muted=%r"
                    % (saved, back, second.get("already_muted")))
        attempt("duas chamadas de mute nao se anulam", a5)

        def a6():
            st = state_path("a6")
            before = backend.get_volume(device_id)
            res = mod.unmute_default_output(backend=backend, state_path=st)
            after = backend.get_volume(device_id)
            return (res.get("state") == "not-muted" and res.get("restored") is False
                    and after == before and not os.path.exists(st),
                    "antes=%r depois=%r state=%r" % (before, after, res.get("state")))
        attempt("unmute sem mute previo e inofensivo", a6)

        def a7():
            st = state_path("a7")
            backend.set_volume(device_id, test_value)
            mod.mute_default_output("oracle", backend=backend, state_path=st)
            during = os.path.exists(st)
            mod.unmute_default_output(backend=backend, state_path=st)
            after = os.path.exists(st)
            return (during and not after,
                    "existe_durante_o_mute=%s existe_depois_do_unmute=%s"
                    % (during, after))
        attempt("o estado do mute desaparece depois do unmute", a7)

        def a8():
            st = state_path("cli")
            backend.set_volume(device_id, test_value)
            saved = backend.get_volume(device_id)
            env = dict(os.environ)
            env["SOTTO_MUTE_STATE"] = st
            run = lambda *a: subprocess.run(
                [sys.executable, mod_path] + list(a),
                capture_output=True, text=True, env=env, timeout=60,
                creationflags=NO_WINDOW)
            p1 = run("--mute", "--no-wait", "--state-path", st, "--reason", "oracle")
            muted = backend.get_volume(device_id)
            p2 = run("--status", "--state-path", st)
            p3 = run("--unmute", "--state-path", st)
            back = backend.get_volume(device_id)
            return (p1.returncode == 0 and p2.returncode == 0 and p3.returncode == 0
                    and muted == 0.0 and back == saved and not os.path.exists(st),
                    "rc=%d/%d/%d volume_durante=%r restaurado=%r guardado=%r"
                    % (p1.returncode, p2.returncode, p3.returncode, muted, back, saved))
        attempt("a CLI --mute/--status/--unmute faz o ciclo completo", a8)

        def a9():
            st = state_path("cli-status")
            env = dict(os.environ)
            env["SOTTO_MUTE_STATE"] = st
            p = subprocess.run(
                [sys.executable, mod_path, "--status", "--state-path", st],
                capture_output=True, text=True, env=env, timeout=60,
                creationflags=NO_WINDOW)
            try:
                payload = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:                                   # noqa: BLE001
                return False, "stdout=%r rc=%d" % (p.stdout[:200], p.returncode)
            return (p.returncode == 0 and payload.get("device_name") == device_name
                    and isinstance(payload.get("volume"), float),
                    "rc=%d device=%r volume=%r"
                    % (p.returncode, payload.get("device_name"), payload.get("volume")))
        attempt("a CLI --status mostra o default output e o volume", a9)

        def a19():
            # The `--mute` that WAITS must put the volume back when it is
            # interrupted (Ctrl+C). The OS-level keypress is not simulated
            # here -- the KeyboardInterrupt itself is injected, which is the
            # branch this code owns.
            import contextlib
            import io
            import unittest.mock as mock
            st = state_path("cli-ctrlc")
            backend.set_volume(device_id, test_value)
            saved = backend.get_volume(device_id)
            buf = io.StringIO()
            with mock.patch.object(mod.time, "sleep", side_effect=KeyboardInterrupt):
                with contextlib.redirect_stdout(buf):
                    rc = mod._cli(["--mute", "--state-path", st, "--reason", "oracle"])
            back = backend.get_volume(device_id)
            return (rc == 0 and back == saved and not os.path.exists(st),
                    "rc=%r restaurado=%r guardado=%r" % (rc, back, saved))
        attempt("o --mute que espera volta a por o volume quando e interrompido", a19)
    finally:
        for path in states:
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            backend.set_volume(device_id, original)
        except Exception:                                       # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # THE FAKE DEVICE: the failure modes, deterministically.
    # ------------------------------------------------------------------
    def a10():
        # RELATIVE to the module's own directory: the property is "the state
        # file lives next to the code that writes it". (An absolute "_main"
        # check would go RED for every mutant -- they live in a temp dir --
        # and a mutant "caught" by an unrelated check is a decorative
        # mutant. The absolute check for the REAL module is in main().)
        return (os.path.dirname(os.path.abspath(mod.DEFAULT_STATE_PATH))
                == os.path.dirname(os.path.abspath(mod_path)),
                "estado por omissao: %s | modulo em %s"
                % (mod.DEFAULT_STATE_PATH,
                   os.path.dirname(os.path.abspath(mod_path))))
    attempt("o estado por omissao vive NO DIRECTORIO DO MODULO (nada e escrito fora)", a10)

    def a11():
        fb = FakeBackend(default="A", volumes={"A": 0.75}, silent_fail_on=0.0)
        st = state_path("a11")
        raised = None
        try:
            mod.mute_default_output("oracle", backend=fb, state_path=st)
        except mod.MuteError as exc:
            raised = exc
        return (raised is not None,
                "levantou: %s" % raised if raised
                else "SILENCIOU: devolveu um mute que nao muteou")
    attempt("se o mute nao pega, o erro e explicito", a11)

    def a12():
        fb = FakeBackend(default="A", volumes={"A": 0.75}, silent_fail_on=0.0)
        st = state_path("a12")
        try:
            mod.mute_default_output("oracle", backend=fb, state_path=st)
        except mod.MuteError:
            pass
        return (fb.volumes["A"] == 0.75 and not os.path.exists(st),
                "volume=%r (esperado 0.75) estado=%s"
                % (fb.volumes["A"], os.path.exists(st)))
    attempt("se o mute nao pega, o volume fica como estava e nao ha estado", a12)

    def a13():
        fb = FakeBackend(default="A", volumes={"A": 0.75}, fail_set_on=0.0)
        st = state_path("a13")
        raised = None
        try:
            mod.mute_default_output("oracle", backend=fb, state_path=st)
        except mod.MuteError as exc:
            raised = exc
        return (raised is not None,
                "levantou: %s" % raised if raised
                else "SILENCIOU: o dispositivo rebentou e o mute seguiu")
    attempt("se o dispositivo rebenta a meio do mute, o erro e explicito", a13)

    def a14():
        fb = FakeBackend(default="A", volumes={"A": 0.75}, fail_set_on=0.0)
        st = state_path("a14")
        try:
            mod.mute_default_output("oracle", backend=fb, state_path=st)
        except mod.MuteError:
            pass
        return (fb.volumes["A"] == 0.75 and not os.path.exists(st),
                "volume=%r (esperado 0.75) estado=%s"
                % (fb.volumes["A"], os.path.exists(st)))
    attempt("se o dispositivo rebenta, nada fica a meio", a14)

    def a15():
        fb = FakeBackend(default="A", volumes={"A": 0.37}, fail_set_on=0.37)
        st = state_path("a15")
        mod.mute_default_output("oracle", backend=fb, state_path=st)
        raised = None
        try:
            mod.unmute_default_output(backend=fb, state_path=st)
        except mod.MuteError as exc:
            raised = exc
        survived = os.path.exists(st)
        good = FakeBackend(default="A", volumes=fb.volumes)
        res = mod.unmute_default_output(backend=good, state_path=st)
        return (raised is not None and survived and res.get("restored") is True
                and good.volumes["A"] == 0.37 and not os.path.exists(st),
                "levantou=%s estado_sobreviveu=%s segunda_tentativa=%r"
                % (raised is not None, survived, good.volumes["A"]))
    attempt("se o restore falhar, o estado SOBREVIVE e a segunda tentativa restaura", a15)

    def a16():
        fb = FakeBackend(default="A", volumes={"A": 0.6, "B": 0.9})
        st = state_path("a16")
        mod.mute_default_output("oracle", backend=fb, state_path=st)
        fb.default = "B"
        mod.unmute_default_output(backend=fb, state_path=st)
        return (fb.volumes["A"] == 0.6 and fb.volumes["B"] == 0.9,
                "device_mudado=%r device_novo=%r" % (fb.volumes["A"], fb.volumes["B"]))
    attempt("se o default mudou, o unmute restaura o device mudado e nao toca no novo", a16)

    def a17():
        fb = FakeBackend(default="A", volumes={"A": 0.6, "B": 0.9})
        st = state_path("a17")
        mod.mute_default_output("oracle", backend=fb, state_path=st)
        fb.default = "B"
        res = mod.mute_default_output("oracle-2", backend=fb, state_path=st)
        return (fb.volumes["A"] == 0.6 and fb.volumes["B"] == 0.0
                and res.get("restored_another_device_first") is not None,
                "device_mudado=%r device_novo=%r restaurou_o_antigo=%r"
                % (fb.volumes["A"], fb.volumes["B"],
                   res.get("restored_another_device_first")))
    attempt("um mute noutro device restaura PRIMEIRO o device antigo", a17)

    def a18():
        folder = os.path.join(workdir, "writes")
        os.makedirs(folder, exist_ok=True)
        st = os.path.join(folder, "state.json")
        fb = FakeBackend(default="A")
        mod.mute_default_output("oracle", backend=fb, state_path=st)
        during = sorted(os.listdir(folder))
        mod.unmute_default_output(backend=fb, state_path=st)
        after = sorted(os.listdir(folder))
        return (during == ["state.json"] and after == [],
                "durante=%r depois=%r" % (during, after))
    attempt("o mute escreve SO o ficheiro de estado e apaga-o no unmute", a18)

    imported = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    heavy = sorted(imported & set(AUDIO_LIBS))
    attempt("o modulo nao importa nenhuma biblioteca de audio (nao renderiza nada)",
            lambda: (not heavy and "sounddevice" not in source,
                     "imports=%r" % heavy))
    return out


# The anchors are exact strings of `_main/mute-audio.py`. A mutant whose
# anchor is missing is DECORATIVE -- it proves nothing -- so the oracle
# refuses to count it.
#
# The restore inside `unmute_default_output`, with enough context to be
# UNIQUE: `_try_restore` has the same two lines, and an anchor that matches
# twice would mutate the wrong place.
UNMUTE_RESTORE = ("    try:\n        backend.set_volume(device_id, saved)\n"
                   "    except Exception as exc:\n"
                   "        raise MuteError(\"nao consegui restaurar")

MUTANTS = [
    # THE MUTE THAT DOES NOT MUTE.
    ("mute-does-not-zero-the-volume",
     "        backend.set_volume(device_id, 0.0)",
     "        backend.set_volume(device_id, saved)"),
    # THE MUTE THAT SWALLOWS THE FAILURE: the endpoint blew up, the mute
    # "worked", the owner's speakers stayed at full volume.
    ("mute-swallows-the-failure",
     "    except Exception as exc:\n"
     "        raise MuteError(\"nao consegui mutar %s: %s: %s\"\n"
     "                        % (device_name, type(exc).__name__, exc))",
     "    except Exception as exc:\n"
     "        return {\"state\": \"mute-failed\", \"error\": str(exc),\n"
     "                \"device_id\": device_id, \"device_name\": device_name,\n"
     "                \"volume_now\": backend.get_volume(device_id),\n"
     "                \"saved_scalar\": saved, \"state_path\": path}"),
    # THE SECOND MUTE THAT OVERWRITES THE FIRST: unmute would restore 0.
    ("second-mute-overwrites-the-saved-value",
     "    if prior and prior.get(\"device_id\") == device_id and "
     "prior.get(\"saved_scalar\") is not None:",
     "    if False:"),
    # THE UNMUTE THAT TOUCHES THE VOLUME WITH NOTHING TO UNDO.
    ("unmute-without-mute-touches-the-volume",
     "        device_id, device_name = backend.default_endpoint()\n"
     "        return {\n"
     "            \"state\": \"not-muted\",",
     "        device_id, device_name = backend.default_endpoint()\n"
     "        backend.set_volume(device_id, 0.0)\n"
     "        return {\n"
     "            \"state\": \"not-muted\","),
    # THE RESTORE THAT PUTS 50% INSTEAD OF THE VALUE IT FOUND. 0.5 is the
    # scalar form of "50" -- the raw-level API on this endpoint is DECIBELS.
    ("unmute-restores-50-percent-not-the-saved-value",
     UNMUTE_RESTORE,
     "    try:\n        backend.set_volume(device_id, 0.5)\n"
     "    except Exception as exc:\n"
     "        raise MuteError(\"nao consegui restaurar"),
    # THE RESTORE THAT PUTS THE LITERAL 50 -- off the 0..1 scale. On this
    # endpoint that is an invalid parameter; on another one it is a wrong
    # volume. Both are RED.
    ("unmute-restores-the-literal-50-not-the-saved-value",
     UNMUTE_RESTORE,
     "    try:\n        backend.set_volume(device_id, 50.0)\n"
     "    except Exception as exc:\n"
     "        raise MuteError(\"nao consegui restaurar"),
    # THE RESTORE THAT PUTS BACK THE SYSTEM DEFAULT. The owner gets the
    # volume he had yesterday, not the one he had a minute ago.
    ("unmute-restores-the-system-default-not-the-saved-value",
     UNMUTE_RESTORE,
     "    try:\n        backend.set_volume(device_id, 1.0)\n"
     "    except Exception as exc:\n"
     "        raise MuteError(\"nao consegui restaurar"),
    # THE RESTORE THAT LOSES THE SAVED VOLUME: the state is deleted BEFORE
    # the volume is put back, so a failed restore is unrecoverable.
    ("unmute-deletes-the-state-before-restoring",
     UNMUTE_RESTORE,
     "    _clear_state(path)\n    try:\n        backend.set_volume(device_id, saved)\n"
     "    except Exception as exc:\n"
     "        raise MuteError(\"nao consegui restaurar"),
]


def main() -> int:
    neg_only = "--neg-arm" in sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass
    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8", newline="") as fh:
        source = fh.read()

    arms_total = arms_green = 0
    if not neg_only:
        print("ARMS (the real mute, on the real default output)")
        workdir = tempfile.mkdtemp(prefix="mute-oracle-")
        try:
            mod = load_module(MODULE_PATH, "mute_audio_live")
            rows = battery(mod, MODULE_PATH, workdir, source)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        # The REAL module only: the shipped file must keep its state inside
        # `_main/`. (The battery checks the relative property -- the state
        # lives next to the code -- because an absolute check would go RED
        # for every mutant, which lives in a temp dir, and a mutant caught
        # by an unrelated check is a decorative mutant.)
        rows.append((
            os.path.dirname(os.path.abspath(mod.DEFAULT_STATE_PATH))
            == os.path.abspath(MAIN_DIR),
            "o estado por omissao do modulo REAL vive em _main/",
            mod.DEFAULT_STATE_PATH))
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        arms_green = sum(1 for ok, _, _ in rows if ok)
        arms_total = len(rows)
        print("\n  %d/%d" % (arms_green, arms_total))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    caught = 0
    weak = 0
    workdir = tempfile.mkdtemp(prefix="mute-oracle-mut-")
    try:
        for idx, (label, old, new) in enumerate(MUTANTS):
            hits = source.count(old)
            if hits != 1:
                print("  RED   mutant %-48s ANCHOR %s -- oracle is stale"
                      % (label, "MISSING" if hits == 0 else "AMBIGUOUS"))
                weak += 1
                continue
            path = os.path.join(workdir, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, "mute_audio_mut_%d" % idx)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-48s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            sub = tempfile.mkdtemp(prefix="mute-oracle-mut-run-")
            try:
                res = battery(bad, path, sub, source.replace(old, new, 1))
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-48s a bateria rebentou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            finally:
                shutil.rmtree(sub, ignore_errors=True)
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-48s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-48s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    total = len(MUTANTS)
    if neg_only:
        # rc=1 BY DESIGN: the negative arm reproves on purpose.
        print("\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo REPROVA de proposito)" % ("PASS" if caught == total else "FAIL",
                                                  caught, total))
        return EXIT_FAIL

    ok = (arms_green == arms_total and caught == total and weak == 0)
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", arms_green, arms_total, caught, total))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram "
              "nada." % weak)
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
