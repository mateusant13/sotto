#!/usr/bin/env python
"""MUTE THE OWNER'S DEFAULT OUTPUT -- one place, callable by everyone.

Owner, 2026-10-19, verbatim:
    "se tu vai usar audio padrao pra testar qualquer coisa, muta. nao quero
     ficar ouvindo."

THE PROBLEM THIS SOLVES
-----------------------
Until now the protection was a REFUSAL. A probe that wanted to render audio
on the system default endpoint walked away with rc=4 ("AUDIBLE-DEVICE")
unless SOTTO_ALLOW_AUDIBLE=1 was set -- see `_main/inject-all-probe.py`
and `_main/_audio-tone-inject.py`. A refusal is safe, but it is a dead end:
the measurement does not happen, and whoever needed it has to invent a
workaround (or ask the owner to listen to a tone).

What the owner asked for is the OTHER door: a MUTE. The test runs, the audio
goes to the default endpoint, and the owner hears NOTHING. The rule lives
here, in one module, instead of being re-invented per probe.

MEASURED ON THIS BOX (2026-10-19, pycaw + the Windows audio engine):
  * the default RENDER endpoint is
    "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)" -- role eConsole AND role
    eMultimedia both resolve to
    {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0};
  * role eCommunications resolves to a DIFFERENT device
    ("Headset (soundcore Space Q45 Hands-Free)"), so the ROLE MATTERS. This
    tool uses eConsole -- what Windows' Sound settings shows -- by default;
  * the master volume is a SCALAR in 0..1. `SetMasterVolumeLevel` takes
    DECIBELS, not a 0..100 scale, and +50 dB is an invalid parameter on this
    endpoint (COMError -2147024809);
  * a scalar round trip is FLOAT32-QUANTIZED: set 0.37 and the device reads
    back 0.3700000047683716. So the value that is RESTORED must be the value
    that was READ -- never the value that was SET, and never a "default".

THE RULE: read the master volume of the default output, put it at 0, and put
BACK THAT NUMBER when you are done. If the mute cannot be done, say so
loudly -- never leave it half done.

USAGE
  python _main/mute-audio.py --status
  python _main/mute-audio.py --mute            # waits; Ctrl+C restores
  python _main/mute-audio.py --mute --no-wait  # leaves the mute in place
  python _main/mute-audio.py --unmute

Run it with pythonw.exe (or CREATE_NO_WINDOW) if you do not want a console
window on the owner's screen.

The state file lives in `_main/mute-audio-state.json` (already ignored by
.gitignore via `_main/*-state.json`) and NOTHING is written outside `_main/`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILENAME = "mute-audio-state.json"
DEFAULT_STATE_PATH = os.path.join(HERE, STATE_FILENAME)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
# A WRITE TO THE OWNER'S AUDIO IS A REFUSAL, NOT A HABIT (owner order,
# 2026-11-02: *"nunca mais roda nada que vai mutar meu audio ou resetar ele e
# fazer mutar"*). Reading (`--status`, `--status-all`) is free; every path that
# WRITES a volume/mute needs this flag in the environment, and the refusal is a
# distinct exit code so a battery step can never mistake it for a pass.
EXIT_OWNER_AUDIO = 9
OWNER_AUDIO_ENV = "SOTTO_OWNER_AUDIO_OK"
# THE JOURNAL: a kill can skip every `finally`, so the mute protocol's state file
# is not enough on its own (measured 2026-11-02: a battery killed mid-arm left two
# endpoints at 0.0 with no saved value anywhere). Before ANY write, the value read
# is appended here; `--repair` puts every journalled endpoint back and clears it.
JOURNAL_FILENAME = "audio-journal.json"
DEFAULT_JOURNAL_PATH = os.path.join(HERE, JOURNAL_FILENAME)

ROLE_NAMES = ("console", "multimedia", "communications")


class MuteError(RuntimeError):
    """A mute/unmute that did NOT happen. Never swallowed, never faked."""


# --------------------------------------------------------------------------
# the real endpoint
# --------------------------------------------------------------------------
class PycawBackend:
    """The system's default RENDER device -- the owner's speakers.

    pycaw is imported INSIDE the methods: importing it at module level would
    drag COM into every process that merely imports this file.
    """

    def __init__(self, role: str = "console"):
        if role not in ROLE_NAMES:
            raise MuteError("papel de audio desconhecido: %r" % role)
        self.role = role

    # -- plumbing ---------------------------------------------------------
    def _enumerator(self):
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetDeviceEnumerator()

    def _role_value(self) -> int:
        from pycaw.constants import ERole
        return getattr(ERole, "e" + self.role.capitalize()).value

    def _device(self, device_id: str):
        dev = self._enumerator().GetDevice(device_id)
        if dev is None:
            raise MuteError("o dispositivo %s nao existe (ou foi removido)" % device_id)
        return dev

    def _volume_iface(self, device_id: str):
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume
        iface = self._device(device_id).Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        # QueryInterface, NOT ctypes.cast. A cast builds a SECOND wrapper
        # around the same COM identity and both release it at exit -- the
        # access violation comtypes prints on shutdown ("reading
        # 0xFFFFFFFFFFFFFFFF"). The QueryInterface carries its OWN reference,
        # so there is exactly one owner and the shutdown is silent.
        return iface.QueryInterface(IAudioEndpointVolume)

    # -- the protocol -----------------------------------------------------
    def default_endpoint(self):
        """(device_id, friendly_name) of the default RENDER endpoint."""
        from pycaw.constants import EDataFlow
        from pycaw.pycaw import AudioUtilities
        dev = self._enumerator().GetDefaultAudioEndpoint(
            EDataFlow.eRender.value, self._role_value())
        if dev is None:
            raise MuteError("nao ha endpoint de render por omissao para o papel %r"
                            % self.role)
        info = AudioUtilities.CreateDevice(dev)
        name = getattr(info, "FriendlyName", None) or str(info.id)
        return str(info.id), str(name)

    def get_volume(self, device_id: str) -> float:
        """The master volume SCALAR (0..1), as the device reports it."""
        return float(self._volume_iface(device_id).GetMasterVolumeLevelScalar())

    def set_volume(self, device_id: str, scalar: float) -> None:
        """Set the master volume SCALAR (0..1)."""
        self._volume_iface(device_id).SetMasterVolumeLevelScalar(
            float(scalar), None)


# --------------------------------------------------------------------------
# the state file
# --------------------------------------------------------------------------
def default_state_path() -> str:
    """Where the saved volume lives. NEVER outside `_main/` by default."""
    return os.environ.get("SOTTO_MUTE_STATE") or DEFAULT_STATE_PATH


def _read_state(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_state(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _clear_state(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _try_restore(backend, device_id: str, saved: float) -> bool:
    try:
        backend.set_volume(device_id, saved)
    except Exception:
        return False
    return True


# --------------------------------------------------------------------------
# the owner's audio is not a test bench
# --------------------------------------------------------------------------
def owner_audio_allowed() -> bool:
    """Is a WRITE to an endpoint sanctioned right now?"""
    return str(os.environ.get(OWNER_AUDIO_ENV) or "").strip() == "1"


def refusal(op: str) -> dict:
    """The one shape every writer returns when the flag is missing."""
    return {
        "state": "refused-owner-audio",
        "op": op,
        "why": "recusa: audio do dono",
        "fix": f"ponha {OWNER_AUDIO_ENV}=1 SO se o dono pediu (ordem 2026-11-02)",
    }


# --------------------------------------------------------------------------
# the journal -- the last line of defence when a process is KILLED
# --------------------------------------------------------------------------
def journal_path() -> str:
    return os.environ.get("SOTTO_AUDIO_JOURNAL") or DEFAULT_JOURNAL_PATH


def _journal_read(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    rows = data.get("writes") if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else []


def _journal_write(path: str, rows: list) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"writes": rows}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def journal_record(device_id: str, device_name: str, prior: float, why: str) -> None:
    """Append the value ABOUT TO BE OVERWRITTEN, before the write happens.

    Write-before-write is the whole point: a `TerminateProcess` between the two
    lines leaves the journal on disk, which is what `--repair` reads. Recording
    after the write would lose exactly the case that cost the owner his audio.
    """
    path = journal_path()
    rows = _journal_read(path)
    rows.append(
        {
            "device_id": device_id,
            "device_name": device_name,
            "prior_scalar": float(prior),
            "why": why,
            "at": time.time(),
            "pid": os.getpid(),
        }
    )
    _journal_write(path, rows[-200:])


def repair(journal: str | None = None) -> dict:
    """Put every journalled endpoint back to the value recorded BEFORE the write."""
    path = journal or journal_path()
    rows = _journal_read(path)
    backend = PycawBackend(role="console")
    done, failed = [], []
    for row in reversed(rows):
        did = row.get("device_id")
        prior = row.get("prior_scalar")
        if not did or prior is None:
            continue
        try:
            backend.set_volume(did, float(prior))
            done.append({"device": row.get("device_name") or did, "restored_to": float(prior)})
        except Exception as exc:                       # noqa: BLE001 - reported, not hidden
            failed.append({"device": row.get("device_name") or did,
                           "error": f"{type(exc).__name__}: {exc}"})
    if done and not failed:
        _journal_write(path, [])
    return {"state": "repaired", "restored": done, "failed": failed,
            "journal": path, "cleared": bool(done and not failed)}


# --------------------------------------------------------------------------
# the library
# --------------------------------------------------------------------------
def mute_default_output(reason: str = "", backend=None, state_path=None) -> dict:
    """Put the default output at 0. Remember the volume to put back.

    Raises MuteError if the mute did not take effect -- and, in that case,
    leaves the volume where it was. Never a half mute.
    """
    backend = backend or PycawBackend()
    path = state_path or default_state_path()
    device_id, device_name = backend.default_endpoint()

    prior = _read_state(path)

    # A mute left behind on ANOTHER device (the default output changed while
    # we were away) is restored FIRST. We never leave a device at 0 without a
    # way back to its own volume.
    restored_first = None
    if prior and prior.get("device_id") and prior.get("device_id") != device_id:
        restored_first = _restore_from(backend, prior)
        prior = None

    if prior and prior.get("device_id") == device_id and prior.get("saved_scalar") is not None:
        # Already muted by us: KEEP the first saved volume. A second mute must
        # not overwrite it with 0 -- that would unmute to silence.
        saved = float(prior["saved_scalar"])
        already = True
    else:
        saved = backend.get_volume(device_id)
        already = False

    # THE MUTE. Set it to 0, then READ IT BACK: a write that does not take
    # effect is a mute that did not happen.
    # JOURNAL FIRST: if this process is killed between the two lines below, the
    # value that was here is on disk and `--repair` can put it back.
    try:
        journal_record(device_id, device_name, saved, reason or "mute")
    except Exception:
        pass
    try:
        backend.set_volume(device_id, 0.0)
    except Exception as exc:
        raise MuteError("nao consegui mutar %s: %s: %s"
                        % (device_name, type(exc).__name__, exc))
    actual = backend.get_volume(device_id)
    if actual != 0.0:
        _try_restore(backend, device_id, saved)
        raise MuteError("o mute nao pegou: o volume de %s ficou em %r (esperado 0.0)"
                        % (device_name, actual))

    if already:
        record = dict(prior)
        record["reason"] = reason or record.get("reason", "")
    else:
        record = {
            "device_id": device_id,
            "device_name": device_name,
            "saved_scalar": saved,
            "reason": reason,
            "at": time.time(),
        }
        # The state is written AFTER the volume is really at 0. If the write
        # fails we roll the volume back: a mute nobody can undo is worse than
        # no mute at all.
        try:
            _write_state(path, record)
        except Exception as exc:
            _try_restore(backend, device_id, saved)
            raise MuteError("mutei %s mas nao consegui guardar o volume anterior "
                            "(%s) -- voltei-o a %r" % (device_name, exc, saved))

    return {
        "state": "muted",
        "already_muted": already,
        "device_id": device_id,
        "device_name": device_name,
        "volume_now": actual,
        "saved_scalar": saved,
        "restored_another_device_first": restored_first,
        "state_path": path,
    }


def _restore_from(backend, prior: dict):
    device_id = prior.get("device_id")
    saved = prior.get("saved_scalar")
    if not device_id or saved is None:
        return None
    backend.set_volume(device_id, float(saved))
    return {"device_id": device_id, "saved_scalar": float(saved)}


def unmute_default_output(backend=None, state_path=None) -> dict:
    """Put back EXACTLY the volume that was saved. A no-op if nothing to undo.

    Raises MuteError if the restore did not take effect; the state file is
    kept in that case, so the restore can be retried.
    """
    backend = backend or PycawBackend()
    path = state_path or default_state_path()
    prior = _read_state(path)

    if not prior or prior.get("saved_scalar") is None:
        # Nothing of ours to undo. Do NOT touch the owner's volume.
        device_id, device_name = backend.default_endpoint()
        return {
            "state": "not-muted",
            "restored": False,
            "device_id": device_id,
            "device_name": device_name,
            "volume_now": backend.get_volume(device_id),
            "state_path": path,
        }

    device_id = str(prior.get("device_id"))
    saved = float(prior["saved_scalar"])

    try:
        backend.set_volume(device_id, saved)
    except Exception as exc:
        raise MuteError("nao consegui restaurar o volume de %s: %s: %s "
                        "(o estado ficou guardado, para repetir)"
                        % (device_id, type(exc).__name__, exc))
    actual = backend.get_volume(device_id)
    if actual != saved:
        raise MuteError("pedi %r mas o dispositivo le %r -- o estado ficou "
                        "guardado, para repetir" % (saved, actual))

    # Only now is the state worthless -- the volume is back.
    _clear_state(path)
    return {
        "state": "unmuted",
        "restored": True,
        "device_id": device_id,
        "device_name": prior.get("device_name"),
        "volume_now": actual,
        "saved_scalar": saved,
        "state_path": path,
    }


def status(backend=None, state_path=None) -> dict:
    """What the default output is, how loud it is, and whether WE muted it."""
    backend = backend or PycawBackend()
    path = state_path or default_state_path()
    device_id, device_name = backend.default_endpoint()
    prior = _read_state(path)
    return {
        "state": "muted" if prior else "unmuted",
        "muted": bool(prior),
        "device_id": device_id,
        "device_name": device_name,
        "volume": backend.get_volume(device_id),
        "saved_scalar": (prior or {}).get("saved_scalar"),
        "reason": (prior or {}).get("reason"),
        "state_path": path,
    }


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------
def _emit(payload: dict) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def list_endpoints() -> list[dict]:
    """Every audio endpoint with its mute and volume. Never raises for one device.
    """
    rows = []
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        from ctypes import POINTER, cast
    except Exception as exc:                                   # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"}]
    for dev in AudioUtilities.GetAllDevices():
        name = getattr(dev, "FriendlyName", "?")
        row = {"name": name}
        try:
            vol = cast(dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                       POINTER(IAudioEndpointVolume))
            row["muted"] = bool(vol.GetMute())
            row["scalar"] = round(float(vol.GetMasterVolumeLevelScalar()), 3)
        except Exception as exc:                               # noqa: BLE001
            row["inactive"] = type(exc).__name__
        rows.append(row)
    return rows


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mute-audio.py",
        description="Mute the system default output (the owner's speakers).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mute", action="store_true",
                       help="mute the default output and wait for Ctrl+C")
    group.add_argument("--unmute", action="store_true",
                       help="restore the volume saved by --mute")
    group.add_argument("--status", action="store_true",
                       help="print the default output and its volume")
    group.add_argument("--status-all", action="store_true",
                       help="print EVERY endpoint and its mute/volume -- the read-only census that shows what --mute does NOT cover")
    parser.add_argument("--no-wait", action="store_true",
                       help="with --mute: leave the mute in place and exit")
    parser.add_argument("--state-path", default=None,
                       help="where the saved volume lives (default: _main/)")
    parser.add_argument("--role", default="console", choices=list(ROLE_NAMES),
                        help="which default-output role to mute")
    parser.add_argument("--reason", default="", help="why it is muted")
    parser.add_argument("--repair", action="store_true",
                        help="put back EVERY endpoint recorded in the journal (write; needs the owner flag)")
    parser.add_argument("--journal-status", action="store_true",
                        help="print the journal -- read-only")
    args = parser.parse_args(argv)

    path = args.state_path or default_state_path()
    if getattr(args, "journal_status", False):
        _emit({"state": "journal", "journal": journal_path(),
               "writes": _journal_read(journal_path())})
        return EXIT_OK
    # EVERY WRITE BELOW IS THE OWNER'S AUDIO. Refuse without his flag, and say
    # why in the shape every reader already parses.
    if (args.mute or args.unmute or getattr(args, "repair", False)) and not owner_audio_allowed():
        _emit(refusal("mute" if args.mute else "unmute" if args.unmute else "repair"))
        return EXIT_OWNER_AUDIO
    if getattr(args, "repair", False):
        _emit(repair())
        return EXIT_OK
    backend = PycawBackend(role=args.role)

    if getattr(args, "status_all", False):
        # READ-ONLY, AND IT EXISTS BECAUSE OF A MEASURED FAILURE (2026-11-02).
        # `--mute` mutes ONE endpoint: the default OUTPUT role. The owner heard a
        # test render anyway, because the render went into `CABLE Input (VB-Audio
        # Virtual Cable)` and VoiceMeeter forwards that to a hardware out that is
        # NOT the default. Muting the default proved nothing about what he hears;
        # the census proves it per endpoint, and a step that renders audio must
        # name the endpoint it renders into and show it muted HERE.
        _emit({"state": "status-all", "endpoints": list_endpoints()})
        return EXIT_OK
    if args.mute:
        try:
            result = mute_default_output(args.reason, backend=backend,
                                         state_path=path)
        except MuteError as exc:
            _emit({"state": "mute-failed", "error": str(exc)})
            return EXIT_FAIL
        _emit(result)
        if args.no_wait:
            return EXIT_OK
        try:
            while True:
                time.sleep(2.0)
                _emit(status(backend=backend, state_path=path))
        except KeyboardInterrupt:
            pass
        try:
            _emit(unmute_default_output(backend=backend, state_path=path))
        except MuteError as exc:
            _emit({"state": "unmute-failed", "error": str(exc)})
            return EXIT_FAIL
        return EXIT_OK

    if args.unmute:
        try:
            _emit(unmute_default_output(backend=backend, state_path=path))
        except MuteError as exc:
            _emit({"state": "unmute-failed", "error": str(exc)})
            return EXIT_FAIL
        return EXIT_OK

    try:
        _emit(status(backend=backend, state_path=path))
    except MuteError as exc:
        _emit({"state": "status-failed", "error": str(exc)})
        return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(_cli())
