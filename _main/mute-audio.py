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
    parser.add_argument("--no-wait", action="store_true",
                       help="with --mute: leave the mute in place and exit")
    parser.add_argument("--state-path", default=None,
                       help="where the saved volume lives (default: _main/)")
    parser.add_argument("--role", default="console", choices=list(ROLE_NAMES),
                        help="which default-output role to mute")
    parser.add_argument("--reason", default="", help="why it is muted")
    args = parser.parse_args(argv)

    path = args.state_path or default_state_path()
    backend = PycawBackend(role=args.role)

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
