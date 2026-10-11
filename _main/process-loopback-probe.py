#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove or refute: can Windows WASAPI PROCESS LOOPBACK capture ONE process's audio?

WHY THIS FILE EXISTS
--------------------
Sotto's owner requirement is per-app audio separation ("capture ONE chosen process's
audio").  The endpoint loopback ladder in `worker/wasapi_loopback.py` is a
different API surface: it taps a RENDER ENDPOINT and therefore hears everything that
endpoint carries, whoever rendered it.  The only Windows API that scopes a capture to
a PROCESS is `ActivateAudioInterfaceAsync` against the virtual device
`VAD\Process_Loopback`, with an `AUDIOCLIENT_ACTIVATION_PARAMS` blob naming
a PID.  The tokens `ActivateAudioInterfaceAsync` / `PROCESS_LOOPBACK` /
`process_loopback` occur ZERO times in this repository, so nothing here had ever
opened it.

This file is the instrument.  It declares the whole COM surface by hand with
`ctypes` -- no comtypes, no pycaw, no sounddevice, no numpy: the stdlib only.
That is deliberate.  It is the same technique `worker/wasapi_loopback.py` already
uses for endpoint loopback (`_vtbl`, `_com_init`, GUID helpers), re-derived
for the process-loopback activation path, so "it works" here does not depend on a
package that might not be installed.

THE CONTRACT, AND WHERE IT CAME FROM
------------------------------------
Two shipped implementations of this API were read, and they AGREE:

  * Microsoft, Windows-classic-samples/Samples/ApplicationLoopback/cpp/LoopbackCapture.cpp
    (the reference sample):
        AUDIOCLIENT_ACTIVATION_PARAMS p = {};
        p.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
        p.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;
        p.ProcessLoopbackParams.TargetProcessId = processId;
        PROPVARIANT v = {};
        v.vt = VT_BLOB;
        v.blob.cbSize    = sizeof(p);          // 12, NOT 16
        v.blob.pBlobData = (BYTE*)&p;          // points STRAIGHT at the params
        ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
                                    __uuidof(IAudioClient), &v, this, &asyncOp);
  * the Rust `wasapi` crate 0.21.0 (`new_application_loopback_client`):
    identical, cbSize = size_of::<AUDIOCLIENT_ACTIVATION_PARAMS>(), pBlobData = &params.

A SECOND, WIDELY-COPIED VARIANT exists that wraps the params in a leading DWORD
({ DWORD cbSize; AUDIOCLIENT_ACTIVATION_PARAMS params; }, blob.cbSize = 16).  Both are
implemented here as ARMS and both HRESULTs are printed, because the difference is
exactly the kind of thing that gets argued about instead of measured.  ARM A
("direct") is the shipped contract above; ARM B ("wrapped") is the variant.

WHAT IT MEASURES -- THREE CONTROLS, ONE RUN
-------------------------------------------
A capture that returns packets proves nothing on its own: a stream can be opened on a
device that hears nothing and still deliver a full cadence of silence, which is the
exact false green this repository has already been burned by.  So:

  POSITIVE   a child process we spawn renders a 440 Hz tone into a NON-DEFAULT render
             endpoint; we capture its PID tree.  Requires packets > 0 AND peak > 0.05.
  NEGATIVE-A the SAME capture, at the SAME moment (the tone is still playing), aimed
             at a live process that renders nothing (`cmd /c timeout`).  Must be
             silent: zero packets, or a peak below the floor.  This is the arm that
             separates "per-process" from "per-endpoint": if the API were really
             tapping the endpoint, this arm would hear the tone too.
  NEGATIVE-B (informational) an invalid TargetProcessId (0, and 0xFFFFFFFE).  This arm
             was WRITTEN as a required control and then MEASURED to be an over-claim:
             pid 0 is REJECTED with E_INVALIDARG, but 0xFFFFFFFE is ACCEPTED and yields a
             live IAudioClient.  The API is therefore NOT fail-closed against arbitrary
             garbage pids -- and nothing in the shipped contract promises it is.  So this
             arm is REPORTED loudly as a DEVIATION and never decides the exit code; the
             control that carries the proof is NEGATIVE-A.  (Keeping the arm and its
             measurement is the point: the deviation is a fact about this build.)
  EXCLUDE    (informational) the same live renderer, mode
             PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE.  Expected silent: it
             proves the MODE field is honoured rather than ignored.

EXIT CODES (printed at the end, and documented here so a caller need not guess)
------------------------------------------------------------------------------
  0  positive control proved AND NEGATIVE-A behaved as required.  NEGATIVE-B is
     informational: a deviation there is printed as DEVIATION and still exits 0, because
     the claim under test -- "one chosen process's audio, and not another's" -- does not
     depend on pid-validation strictness (measured: pid 0 IS rejected, 0xFFFFFFFE is NOT)
  3  the plumbing works but the POSITIVE CONTROL WAS SILENT (a real possible outcome;
     it is reported, never hidden)
  2  a declared step failed (which one is printed, with its HRESULT)
  4  REFUSED: the only matching render endpoint is the system default output and
     SOTTO_ALLOW_AUDIBLE is not set.  Same convention as `_main/inject-all-probe.py`:
     this probe must never make the owner hear a test tone.

WHAT IT DOES *NOT* PROVE (read before quoting a green)
------------------------------------------------------
  * One PID and one endpoint on one machine on one build.  It does not prove behaviour
    for a process tree that renders through a different mechanism, nor for a
    protected/audiosrv-hosted session.
  * It does not prove the capture is sample-accurate, gapless, or correctly resampled
    -- only that real signal from the target PID arrives and that a non-rendering PID
    yields nothing.
  * EXCLUDE mode is reported, not required: other audio on the box would confound it,
    so it never decides the exit code.
  * NEGATIVE-B is reported, not required, for the same kind of reason: it measures an
    API-strictness property (does an invalid pid get refused?) that the shipped contract
    never promises.  Measured on this build it is only HALF true, and that half-truth is
    printed in the MEASURED block instead of being allowed to mask a proved result.
  * It does not prove that a CHILD of the target pid is excluded -- the mode exercised
    here is INCLUDE_TARGET_PROCESS_TREE, which is what the MS sample uses and what
    "capture this app" means.  A grandchild that renders into a different endpoint was
    not measured.

USAGE
-----
  python process-loopback-probe.py [--seconds 3.0] [--device "CABLE Input"]
                                   [--com mta|sta] [--json OUT] [--keep]
It spawns its render child with CREATE_NO_WINDOW, so no console appears.
"""

from __future__ import annotations

import argparse
import array
import ctypes
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

if sys.platform != "win32":  # pragma: no cover - this file is Windows-only by nature
    print("FATAL: process loopback is a Windows API")
    raise SystemExit(2)

HRESULT = ctypes.c_long

# -- HRESULTs named, so the printed numbers are readable ----------------------
S_OK = 0x00000000
E_NOINTERFACE = 0x80004002
E_INVALIDARG = 0x80070057
E_UNEXPECTED = 0x8000FFFF
RPC_E_CHANGED_MODE = 0x80010106

# -- activation contract -----------------------------------------------------
VT_BLOB = 65
VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = "VAD\\Process_Loopback"

AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0
PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE = 1

# -- WASAPI flags/ids used by both the capture and the render child -----------
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002
HNS_100MS = 1_000_000

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

E_RENDER = 0
E_CONSOLE = 0
DEVICE_STATE_ACTIVE = 0x00000001
STGM_READ = 0x00000000
CLSCTX_INPROC_SERVER = 0x00000001
COINIT_MULTITHREADED = 0x00000000
COINIT_APARTMENTTHREADED = 0x00000002
VT_LPWSTR = 0x001F
PROPVARIANT_UNION_OFFSET = 8

CREATE_NO_WINDOW = 0x08000000

# The floor the positive control must clear.  The tone is rendered at amplitude 0.4,
# so a working capture lands near 0.4 and a dead one near 0.0 -- the gap is three
# orders of magnitude and 0.05 is nowhere near either edge.  It is also the same
# order as the 0.000122 "nothing routed" ceiling this repo measured for a silent
# endpoint (AGENTS.md, `_main/listen-probe.py`), so the two vocabularies agree.
PEAK_FLOOR = 0.05


# -- GUID --------------------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __str__(self):
        return "{%08X-%04X-%04X-%s-%s}" % (
            self.Data1,
            self.Data2,
            self.Data3,
            "".join("%02X" % b for b in self.Data4[:2]),
            "".join("%02X" % b for b in self.Data4[2:]),
        )


def _guid(s):
    a, b, c, d, e = s.strip().strip("{}").split("-")
    tail = [int(d[i:i + 2], 16) for i in (0, 2)]
    tail += [int(e[i:i + 2], 16) for i in (0, 2, 4, 6, 8, 10)]
    return GUID(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*tail))


def _guid_from_raw(raw):
    """16 raw bytes -> the usual brace form (used to log a QueryInterface)."""
    if len(raw) < 16:
        return "<short>"
    d1 = int.from_bytes(raw[0:4], "little")
    d2 = int.from_bytes(raw[4:6], "little")
    d3 = int.from_bytes(raw[6:8], "little")
    rest = raw[8:16]
    return "{%08X-%04X-%04X-%s-%s}" % (
        d1, d2, d3, rest[:2].hex().upper(), rest[2:].hex().upper())


CLSID_MMDeviceEnumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioClient = _guid("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioCaptureClient = _guid("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
IID_IAudioRenderClient = _guid("{F294ACFC-3146-4483-A7BF-ADDCA7C260E2}")
IID_IUnknown = _guid("{00000000-0000-0000-C000-000000000046}")
# IActivateAudioInterfaceCompletionHandler -- the interface the caller must implement to
# receive the async activation result (mmdeviceapi.h).  The value below is the SDK's own,
# and it is ALSO the IID this host was MEASURED to request.  The first run of this probe
# declared {41D949AB-9862-444A-80F6-C261334DA5EB} (a guess, never confirmed from source);
# the handler's QueryInterface log then named {94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90} as the
# ONLY interface the audio stack asked for on the completion handler.  Refusing that QI is
# what made ActivateAudioInterfaceAsync answer E_ILLEGAL_METHOD_CALL (0x8000000E) instead
# of activating -- measured, twice, on both PROPVARIANT layouts.  The log is the authority
# and the constant now agrees with it.
IID_IActivateAudioInterfaceCompletionHandler = _guid("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")

PKEY_Device_FriendlyName = _guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


_PKEY_FRIENDLY = PROPERTYKEY(PKEY_Device_FriendlyName, 14)


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    # FLAT, and it has to STAY flat -- this was wrong when the file was first written,
    # and the bug was invisible until it made a control lie.
    #
    # The real layout is Format's SEVEN fields inline (18 bytes), then
    # wValidBitsPerSample at 18, dwChannelMask at 20, SubFormat at 24 -- 40 bytes.
    # Nesting a WAVEFORMATEX here is what a first draft does, and it is wrong TWICE
    # over: ctypes pads that nested struct to 20 (because nSamplesPerSec is a DWORD),
    # which pushes dwChannelMask to 24 and SubFormat to 28, and the whole thing comes
    # out 44 bytes.  Reading a driver's 40-byte WAVEFORMATEXTENSIBLE through such a
    # struct returns the FIRST FOUR BYTES OF SubFormat as dwChannelMask and the 4 bytes
    # PAST the struct as SubFormat.Data1 -- so a float32 endpoint reports as int32.
    # Measured consequence (run 2): the render arm believed int32 and wrote int32 PCM
    # into a float32 stream, where every sample re-reads as ~5e-8, i.e. DIGITAL
    # SILENCE, and the positive control read peak=0.000000 while the endpoint really
    # carried the tone.  The declared-ABI check below now fails hard on any drift.
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
        ("wValidBitsPerSample", wintypes.WORD),
        ("dwChannelMask", wintypes.DWORD),
        ("SubFormat", GUID),
    ]


class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [
        ("TargetProcessId", wintypes.DWORD),
        ("ProcessLoopbackMode", ctypes.c_int),
    ]


class _ACTIVATION_UNION(ctypes.Union):
    _fields_ = [("ProcessLoopbackParams", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)]


class AUDIOCLIENT_ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [("ActivationType", ctypes.c_int), ("u", _ACTIVATION_UNION)]


class BLOB(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.ULONG), ("pBlobData", ctypes.POINTER(ctypes.c_ubyte))]


class PROPVARIANT(ctypes.Structure):
    # VARTYPE + three reserved WORDs (8 bytes) then the union, which x64 aligns on 8
    # for its ULONGLONG members -- so blob lands at offset 8 and the whole thing is
    # 24 bytes.  Same reading `worker/wasapi_loopback.py` documents for the
    # LPWSTR case at PROPVARIANT_UNION_OFFSET.
    _fields_ = [
        ("vt", wintypes.WORD),
        ("wReserved1", wintypes.WORD),
        ("wReserved2", wintypes.WORD),
        ("wReserved3", wintypes.WORD),
        ("blob", BLOB),
    ]


def _hx(hr):
    """An HRESULT as unsigned hex, whatever carrier it came back in."""
    if hr is None:
        return "n/a"
    return "0x%08X" % (int(hr) & 0xFFFFFFFF)


def _fmt(hr):
    try:
        raise ctypes.WinError(ctypes.c_int32(ctypes.c_uint32(int(hr) & 0xFFFFFFFF).value).value)
    except OSError as exc:
        return "%s (%s)" % (exc.strerror, _hx(hr))


# -- COM plumbing: the same technique worker/wasapi_loopback.py uses ----------
def _ole32():
    return ctypes.WinDLL("ole32", use_last_error=True)


def _com_init(apartment="mta"):
    """CoInitializeEx, returning (hr, owed_reference).

    Three documented outcomes, and they differ in what the caller then owes:
      S_OK                COM started here;                 a reference IS taken
      S_FALSE             COM already running here;         a reference IS taken
      RPC_E_CHANGED_MODE  this thread is in the OTHER apartment; NOTHING is owed
    """
    ole32 = _ole32()
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = HRESULT
    flags = COINIT_MULTITHREADED if apartment == "mta" else COINIT_APARTMENTTHREADED
    hr = int(ole32.CoInitializeEx(None, flags)) & 0xFFFFFFFF
    if hr == RPC_E_CHANGED_MODE:
        return hr, False
    return hr, hr in (0x00000000, 0x00000001)


def _com_uninit():
    try:
        _ole32().CoUninitialize()
    except Exception:
        pass


def _vtbl(ptr, index, restype, *argtypes):
    """One COM method: read slot `index` out of the object's vtable.

    `WINFUNCTYPE` (stdcall) and NOT `CFUNCTYPE`: this is the ABI the
    shipped endpoint-loopback tap in this repo uses, and it is what the audio stack
    expects.
    """
    table = ctypes.cast(
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0],
        ctypes.POINTER(ctypes.c_void_p),
    )
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(table[index])


def _release(ptr):
    if ptr:
        try:
            _vtbl(ptr, 2, wintypes.ULONG)()
        except Exception:
            pass


def _ptr_value(holder):
    """The address a ctypes pointer VARIABLE holds (never the address of the var)."""
    try:
        return ctypes.cast(ctypes.pointer(holder), ctypes.POINTER(ctypes.c_void_p))[0]
    except Exception:
        return None


# -- ActivateAudioInterfaceAsync, resolved out of Mmdevapi.dll by hand --------
def resolve_activate_export(dll="Mmdevapi.dll"):
    """(module_base, proc_address, callable) for ActivateAudioInterfaceAsync.

    `ctypes.WinDLL('Mmdevapi.dll').GetProcAddress` raises AttributeError --
    GetProcAddress lives in kernel32, not in the target DLL -- so the module is loaded
    and the export is looked up through kernel32 explicitly.
    """
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
    k32.LoadLibraryW.restype = ctypes.c_void_p
    k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    k32.GetModuleHandleW.restype = ctypes.c_void_p
    k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    k32.GetProcAddress.restype = ctypes.c_void_p

    base = k32.LoadLibraryW(dll) or k32.GetModuleHandleW(dll)
    if not base:
        return None, None, None
    proc = k32.GetProcAddress(ctypes.c_void_p(base), b"ActivateAudioInterfaceAsync")
    if not proc:
        return base, None, None
    fn = ctypes.WINFUNCTYPE(
        HRESULT,
        wintypes.LPCWSTR,
        ctypes.POINTER(GUID),
        ctypes.POINTER(PROPVARIANT),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )(proc)
    return base, proc, fn


# -- the completion handler: a hand-rolled COM object ------------------------
# THE CLASSIC SILENT FAILURE this avoids: the WINFUNCTYPE wrappers must outlive the
# object.  If the vtable array (or the wrappers it holds) is garbage collected, the
# vtable slot becomes a dangling function pointer and activation either never completes
# or takes the process down.  Every handler is therefore registered in _HANDLERS for
# the life of the process.
_HANDLERS = {}

_IID_NAMES = {
    bytes(IID_IUnknown): "IUnknown",
    bytes(IID_IActivateAudioInterfaceCompletionHandler):
        "IActivateAudioInterfaceCompletionHandler",
}

# Accept a QueryInterface by RAW BYTES, never by the friendly name: the name is only a
# label, and a mis-declared GUID must not be what decides whether activation proceeds.
# (The first revision of this file decided by name, so the wrong constant above turned
# into E_NOINTERFACE on the one QI that mattered.)  A request outside this set is refused
# with E_NOINTERFACE and is STILL LOGGED with its decision, which is how it was caught.
_ACCEPT_IIDS = frozenset({
    bytes(IID_IUnknown),
    bytes(IID_IActivateAudioInterfaceCompletionHandler),
})


class CompletionHandler:
    """IActivateAudioInterfaceCompletionHandler (IUnknown + ActivateCompleted).

    The callback runs on an MTA thread owned by the audio stack, NOT on the thread that
    called ActivateAudioInterfaceAsync, so the result is published on the object and the
    caller polls `done` (a time.sleep loop definitely releases the GIL, so a
    ctypes callback can always get in).
    """

    def __init__(self, qi_log, name="handler"):
        self.name = name
        self.qi_log = qi_log
        self.done = False
        self.hr_get_activate_result = None
        self.hr_activate = E_UNEXPECTED
        self.punk = None
        self.error = None
        self.refs = 1
        self.completed_at = None
        self.extra_iids = {}  # raw 16 bytes -> name, learned from QueryInterface
        self._vt = None
        self._obj = None
        self.ptr = None
        self._build()

    def _build(self):
        QI_T = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        AR_T = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
        RL_T = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
        AC_T = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p)

        def qi(this, riid, ppv):
            try:
                raw = ctypes.string_at(riid, 16) if riid else b""
                brace = _guid_from_raw(raw)
                friendly = _IID_NAMES.get(raw) or self.extra_iids.get(raw)
                tag = "%s%s" % (brace, " " + friendly if friendly else "")
                if ppv:
                    ctypes.cast(ppv, ctypes.POINTER(ctypes.c_void_p))[0] = None
                if raw in _ACCEPT_IIDS:
                    self.refs += 1
                    ctypes.cast(ppv, ctypes.POINTER(ctypes.c_void_p))[0] = this
                    self.qi_log.append((self.name, "%s -> S_OK" % tag))
                    return S_OK
                self.qi_log.append((self.name, "%s -> E_NOINTERFACE" % tag))
                return E_NOINTERFACE
            except Exception as exc:  # never let an exception cross the ABI
                self.error = "QI: %r" % (exc,)
                return E_UNEXPECTED

        def addref(this):
            self.refs += 1
            return self.refs

        def release(this):
            self.refs -= 1
            return self.refs if self.refs > 0 else 0

        def activate_completed(this, operation):
            try:
                hr_result = HRESULT(E_UNEXPECTED)
                punk = ctypes.c_void_p(None)
                get_result = _vtbl(operation, 3, HRESULT, ctypes.POINTER(HRESULT),
                                   ctypes.POINTER(ctypes.c_void_p))
                call_hr = int(get_result(operation, ctypes.byref(hr_result), ctypes.byref(punk)))
                self.hr_get_activate_result = call_hr & 0xFFFFFFFF
                self.hr_activate = int(hr_result.value) & 0xFFFFFFFF
                if punk:
                    # Hold our own reference: the operation is released by the caller
                    # once this callback returns, and the IUnknown it handed us must
                    # outlive it.
                    held = ctypes.c_void_p()
                    hr_qi = int(_vtbl(punk, 0, HRESULT, ctypes.POINTER(GUID),
                                      ctypes.POINTER(ctypes.c_void_p))(
                        punk, ctypes.byref(IID_IUnknown), ctypes.byref(held)))
                    self.punk = held if (hr_qi == 0 and held) else punk
                self.completed_at = time.time()
            except Exception as exc:
                self.error = "ActivateCompleted: %r" % (exc,)
            finally:
                self.done = True
            return S_OK

        # Keep the FOUR callback objects themselves alive, not just their addresses:
        # ctypes.cast() to c_void_p copies the address and does NOT retain the thunk, so
        # a collected CFUNCTYPE leaves a dangling vtable slot -- the classic silent
        # failure this class exists to avoid.
        self._callbacks = (QI_T(qi), AR_T(addref), RL_T(release), AC_T(activate_completed))
        self._vt = (ctypes.c_void_p * 4)(
            ctypes.cast(self._callbacks[0], ctypes.c_void_p),
            ctypes.cast(self._callbacks[1], ctypes.c_void_p),
            ctypes.cast(self._callbacks[2], ctypes.c_void_p),
            ctypes.cast(self._callbacks[3], ctypes.c_void_p),
        )
        self._obj = (ctypes.c_void_p * 1)(ctypes.cast(self._vt, ctypes.c_void_p).value)
        self.ptr = ctypes.cast(self._obj, ctypes.c_void_p)
        _HANDLERS[id(self)] = self

    def wait(self, timeout_s):
        deadline = time.time() + timeout_s
        while not self.done and time.time() < deadline:
            time.sleep(0.02)
        return self.done


# -- the activation itself ---------------------------------------------------
def activate_process_loopback(activate_fn, pid, mode, layout, timeout_s=10.0, name="handler"):
    """Open a process-loopback IAudioClient for `pid`.

    Returns a dict; `client` is a c_void_p on success.  Every HRESULT is kept so
    the caller can print raw numbers instead of a boolean.
    """
    out = {
        "pid": pid, "mode": mode, "layout": layout, "name": name,
        "hr_call": None, "hr_activate": None, "hr_get_result": None,
        "client": None, "handler": None, "qi": [], "timeout": False, "error": None,
        "blob_cbSize": None,
    }
    params = AUDIOCLIENT_ACTIVATION_PARAMS()
    params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
    params.u.ProcessLoopbackParams.TargetProcessId = int(pid) & 0xFFFFFFFF
    params.u.ProcessLoopbackParams.ProcessLoopbackMode = int(mode)

    pv = PROPVARIANT()
    pv.vt = VT_BLOB

    # ARM A ("direct"): the shipped contract.  blob.cbSize is the size of the PARAMS
    # STRUCT ITSELF and pBlobData points straight at it.
    # ARM B ("wrapped"): the widely-copied variant that prefixes a DWORD cbSize and
    # reports the size of the wrapper.
    if layout == "direct":
        holder = params
        pv.blob.cbSize = ctypes.sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
    elif layout == "wrapped":
        class _Wrapped(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("params", AUDIOCLIENT_ACTIVATION_PARAMS)]

        holder = _Wrapped()
        holder.cbSize = ctypes.sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
        holder.params = params
        pv.blob.cbSize = ctypes.sizeof(_Wrapped)
    else:
        raise ValueError("unknown layout %r" % (layout,))

    out["blob_cbSize"] = int(pv.blob.cbSize)
    pv.blob.pBlobData = ctypes.cast(ctypes.byref(holder), ctypes.POINTER(ctypes.c_ubyte))

    handler = CompletionHandler(out["qi"], name=name)
    out["handler"] = handler

    op = ctypes.c_void_p(None)
    hr = int(activate_fn(
        VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
        ctypes.byref(IID_IAudioClient),
        ctypes.byref(pv),
        handler.ptr,
        ctypes.byref(op),
    ))
    out["hr_call"] = hr & 0xFFFFFFFF
    if out["hr_call"] != 0:
        out["error"] = "ActivateAudioInterfaceAsync: %s" % _fmt(out["hr_call"])
        if op:
            _release(op)
        return out

    if not handler.wait(timeout_s):
        out["timeout"] = True
        out["error"] = "ActivateCompleted never fired within %.1fs" % timeout_s
        if op:
            _release(op)
        return out

    out["hr_get_result"] = handler.hr_get_activate_result
    out["hr_activate"] = handler.hr_activate
    out["client"] = handler.punk
    if handler.error:
        out["error"] = handler.error
    if out["hr_activate"] != 0:
        out["error"] = "activation result: %s" % _fmt(out["hr_activate"])
    if op:
        _release(op)
    return out


def _release_client(act):
    if act and act.get("client"):
        _release(act["client"])
        act["client"] = None


# -- capture side ------------------------------------------------------------
def _wfx_kind(ptr):
    """(tag, channels, rate, bits, block_align, float_fmt, label) from a WAVEFORMATEX*."""
    wfx = ptr.contents
    tag = int(wfx.wFormatTag)
    bits = int(wfx.wBitsPerSample)
    real_tag = tag
    if tag == WAVE_FORMAT_EXTENSIBLE and int(wfx.cbSize) >= 22:
        # AUTHORITATIVE read: SubFormat sits at byte offset 24 of a real
        # WAVEFORMATEXTENSIBLE.  worker/wasapi_loopback.py reads it the same way
        # (addressof(wf) + 24), and that is the reading that agreed with the endpoint
        # when this file's struct did not.  Deliberately NOT via the struct field, so a
        # future alignment regression cannot silently mislabel the format again.
        raw = ctypes.string_at(ctypes.cast(ptr, ctypes.c_void_p).value + 24, 16)
        real_tag = int.from_bytes(raw[0:4], "little")
    float_fmt = real_tag == WAVE_FORMAT_IEEE_FLOAT
    label = "float32" if float_fmt else ("int16" if bits == 16 else "int%d" % bits)
    return {
        "tag": tag, "real_tag": real_tag, "channels": int(wfx.nChannels),
        "rate": int(wfx.nSamplesPerSec), "bits": bits,
        "block_align": int(wfx.nBlockAlign), "float_fmt": float_fmt, "label": label,
    }


def _make_wfx(rate, channels, bits, float_fmt):
    """A WAVEFORMATEX for a format we declare ourselves (the AUTOCONVERTPCM arms)."""
    w = WAVEFORMATEX()
    w.wFormatTag = WAVE_FORMAT_IEEE_FLOAT if float_fmt else WAVE_FORMAT_PCM
    w.nChannels = channels
    w.nSamplesPerSec = rate
    w.wBitsPerSample = bits
    w.nBlockAlign = channels * bits // 8
    w.nAvgBytesPerSec = rate * w.nBlockAlign
    w.cbSize = 0
    return w


def open_capture(client, log):
    """GetService(IAudioCaptureClient) behind an Initialize ladder; first win wins.

    The format question is NOT a detail on this virtual device: the Rust wasapi crate
    documents that GetMixFormat on an application-loopback client "just returns Not
    implemented", while the Microsoft sample sidesteps it entirely by declaring 16-bit
    PCM 44100 2ch + AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM.  So the ladder tries the
    endpoint's own mix format first and falls back to a declared format, printing EVERY
    HRESULT -- which arm wins is a fact about this build, not something to assume.
    """
    out = {"ok": False, "arms": [], "format": None, "buffer_frames": None,
           "capture": None, "client": client}

    init = _vtbl(client, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.c_int64,
                 ctypes.c_int64, ctypes.POINTER(WAVEFORMATEX), ctypes.c_void_p)
    get_mix = _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))

    mix = ctypes.POINTER(WAVEFORMATEX)()
    hr_mix = int(get_mix(client, ctypes.byref(mix)))
    out["hr_get_mix_format"] = hr_mix & 0xFFFFFFFF
    log("    GetMixFormat            -> %s" % _hx(hr_mix))

    declared = [
        ("declared float32 48000 2ch", _make_wfx(48000, 2, 32, True)),
        ("declared int16   44100 2ch", _make_wfx(44100, 2, 16, False)),
    ]

    autocvt = (AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM
               | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY)
    arms = []
    if hr_mix == 0 and mix:
        arms.append(("GetMixFormat + LOOPBACK", mix, AUDCLNT_STREAMFLAGS_LOOPBACK))
        arms.append(("GetMixFormat + LOOPBACK|AUTOCONVERTPCM", mix, autocvt))
    for label, wfx in declared:
        arms.append((label + " + LOOPBACK|AUTOCONVERTPCM",
                     ctypes.cast(ctypes.byref(wfx), ctypes.POINTER(WAVEFORMATEX)), autocvt))

    winner = None
    for label, fmt_ptr, flags in arms:
        for hns in (0, HNS_100MS):
            hr = int(init(client, AUDCLNT_SHAREMODE_SHARED, flags, hns, 0, fmt_ptr, None))
            out["arms"].append({"label": label, "hns": hns, "hr": hr & 0xFFFFFFFF})
            log("    Initialize %-42s hns=%-8d -> %s%s"
                % (label, hns, _hx(hr), "" if hr == 0 else "  " + _fmt(hr)))
            if hr == 0:
                winner = (label, fmt_ptr, flags, hns)
                break
        if winner:
            break

    if not winner:
        out["error"] = "every Initialize arm failed"
        return out

    out["format"] = _wfx_kind(winner[1])
    out["format"]["winning_arm"] = winner[0]
    out["format"]["flags"] = winner[2]
    out["format"]["hns"] = winner[3]
    log("    WINNER                  -> %s  [%d Hz, %d ch, %s, block_align=%d, flags=%s]"
        % (winner[0], out["format"]["rate"], out["format"]["channels"],
           out["format"]["label"], out["format"]["block_align"], _hx(winner[2])))

    buf = wintypes.UINT(0)
    hr = int(_vtbl(client, 4, HRESULT, ctypes.POINTER(wintypes.UINT))(client, ctypes.byref(buf)))
    log("    GetBufferSize           -> %s (%d frames)" % (_hx(hr), buf.value))
    out["buffer_frames"] = int(buf.value)

    cap = ctypes.c_void_p()
    hr = int(_vtbl(client, 14, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
        client, ctypes.byref(IID_IAudioCaptureClient), ctypes.byref(cap)))
    log("    GetService(Capture)     -> %s" % _hx(hr))
    if hr != 0 or not cap:
        out["error"] = "GetService(IAudioCaptureClient): %s" % _fmt(hr)
        return out
    out["capture"] = cap

    hr = int(_vtbl(client, 10, HRESULT)(client))
    log("    Start                   -> %s" % _hx(hr))
    if hr != 0:
        out["error"] = "IAudioClient::Start: %s" % _fmt(hr)
        return out

    out["ok"] = True
    return out


def measure_capture(cap, seconds, fmt, log, label=""):
    """Drain a capture client for `seconds` and return measured numbers.

    SILENT packets are accumulated AS ZEROS and counted, never skipped and never
    decoded: AUDCLNT_BUFFERFLAGS_SILENT means the packet's bytes are not valid samples,
    and reading them anyway is exactly how a dead endpoint gets reported as "it hears
    something" -- the defect `worker/wasapi_loopback.py` documents.
    """
    next_size = _vtbl(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))
    get_buffer = _vtbl(cap, 3, HRESULT, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                       ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                       ctypes.POINTER(ctypes.c_int64), ctypes.c_void_p)
    release_buffer = _vtbl(cap, 4, HRESULT, wintypes.DWORD)

    block_align = fmt["block_align"]
    float_fmt = fmt["float_fmt"]
    bits = fmt["bits"]

    t0 = time.time()
    deadline = t0 + seconds
    packets = frames = silent_packets = nonzero_packets = 0
    peak = 0.0
    sum_sq = 0.0
    n_samples = 0
    first_packet_at = None
    hr_error = None

    while time.time() < deadline:
        n = wintypes.DWORD(0)
        hr = int(next_size(cap, ctypes.byref(n)))
        if hr != 0:
            hr_error = hr & 0xFFFFFFFF
            break
        if n.value == 0:
            time.sleep(0.002)
            continue

        data = ctypes.POINTER(ctypes.c_ubyte)()
        got = wintypes.DWORD(0)
        flags = wintypes.DWORD(0)
        pos = ctypes.c_int64(0)
        hr = int(get_buffer(cap, ctypes.byref(data), ctypes.byref(got), ctypes.byref(flags),
                            ctypes.byref(pos), None))
        if hr != 0:
            hr_error = hr & 0xFFFFFFFF
            break

        if got.value:
            packets += 1
            frames += int(got.value)
            if first_packet_at is None:
                first_packet_at = time.time() - t0
            if (flags.value & AUDCLNT_BUFFERFLAGS_SILENT) or not data:
                silent_packets += 1
            else:
                raw = ctypes.string_at(data, int(got.value) * block_align)
                if float_fmt:
                    arr = array.array("f")
                elif bits == 16:
                    arr = array.array("h")
                elif bits == 32:
                    arr = array.array("i")
                else:
                    arr = array.array("h")
                try:
                    arr.frombytes(raw)
                except ValueError:
                    arr = array.array("f")
                    arr.frombytes(raw[: (len(raw) // 4) * 4])
                if len(arr):
                    scale = 1.0 if float_fmt else float(1 << (bits - 1))
                    p = max(abs(max(arr)), abs(min(arr))) / scale
                    if p > peak:
                        peak = p
                    if p > 0.0:
                        nonzero_packets += 1
                    sum_sq += sum((v / scale) ** 2 for v in arr)
                    n_samples += len(arr)
        release_buffer(cap, got.value)

    elapsed = time.time() - t0
    rms = math.sqrt(sum_sq / n_samples) if n_samples else 0.0
    out = {
        "label": label,
        "seconds": seconds,
        "elapsed_s": round(elapsed, 3),
        "packets": packets,
        "frames": frames,
        "silent_packets": silent_packets,
        "nonzero_packets": nonzero_packets,
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "first_packet_at_s": None if first_packet_at is None else round(first_packet_at, 4),
        "channels": fmt["channels"],
        "rate": fmt["rate"],
        "hr_error": None if hr_error is None else _hx(hr_error),
    }
    log("    %-22s packets=%-5d frames=%-8d peak=%.6f rms=%.6f silent=%-5d nonzero=%-5d first=%s"
        % (label or "measure", packets, frames, peak, rms, silent_packets, nonzero_packets,
           ("%.3fs" % first_packet_at) if first_packet_at is not None else "never"))
    return out


def close_capture(client, opened):
    if opened and opened.get("capture"):
        _release(opened["capture"])
        opened["capture"] = None
    if client:
        try:
            _vtbl(client, 11, HRESULT)(client)  # Stop
        except Exception:
            pass


# -- render endpoint enumeration (shared by the probe AND its render child) --
def _device_id(dev):
    """IMMDevice::GetId (vtable 5) -> str, CoTaskMemFree'd."""
    ole32 = _ole32()
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    sid = ctypes.c_wchar_p()
    hr = int(_vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(sid)))
    if hr != 0 or not sid.value:
        return None
    out = sid.value
    addr = _ptr_value(sid)
    if addr:
        ole32.CoTaskMemFree(ctypes.c_void_p(addr))
    return out


def _friendly_name(dev):
    """PKEY_Device_FriendlyName via IMMDevice::OpenPropertyStore (vtable 4).

    Not via IMMDevice::Activate(IPropertyStore): that path is documented in
    `worker/wasapi_loopback.py` to fail with E_NOINTERFACE on every active render
    endpoint on this box, which then names every device by its raw GUID.
    """
    store = ctypes.c_void_p()
    if int(_vtbl(dev, 4, HRESULT, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
            dev, STGM_READ, ctypes.byref(store))) != 0 or not store:
        return None
    name = None
    try:
        var = (ctypes.c_ubyte * 24)()
        if int(_vtbl(store, 5, HRESULT, ctypes.POINTER(PROPERTYKEY),
                     ctypes.POINTER(ctypes.c_ubyte))(
                store, ctypes.byref(_PKEY_FRIENDLY), var)) == 0:
            if ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0] == VT_LPWSTR:
                pw = ctypes.cast(ctypes.addressof(var) + PROPVARIANT_UNION_OFFSET,
                                 ctypes.POINTER(ctypes.c_void_p))[0]
                if pw:
                    name = ctypes.cast(pw, ctypes.c_wchar_p).value
    finally:
        _release(store)
    return name


def _enumerator():
    ole32 = _ole32()
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = HRESULT
    enum = ctypes.c_void_p()
    hr = int(ole32.CoCreateInstance(
        ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_INPROC_SERVER,
        ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enum)))
    if hr != 0 or not enum:
        raise RuntimeError("MMDeviceEnumerator unavailable: %s" % _fmt(hr))
    return enum


def default_render_device_id(enum):
    dev = ctypes.c_void_p()
    if int(_vtbl(enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD,
                 ctypes.POINTER(ctypes.c_void_p))(
            enum, E_RENDER, E_CONSOLE, ctypes.byref(dev))) != 0 or not dev:
        return None
    try:
        return _device_id(dev)
    finally:
        _release(dev)


def list_render_endpoints():
    """Every ACTIVE render endpoint: {index, name, endpoint_id, is_default}."""
    enum = _enumerator()
    out = []
    try:
        default_id = default_render_device_id(enum)
        coll = ctypes.c_void_p()
        hr = int(_vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(ctypes.c_void_p))(
            enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll)))
        if hr != 0 or not coll:
            raise RuntimeError("EnumAudioEndpoints(eRender, ACTIVE): %s" % _fmt(hr))
        try:
            count = wintypes.UINT(0)
            _vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
            for i in range(count.value):
                dev = ctypes.c_void_p()
                if int(_vtbl(coll, 4, HRESULT, wintypes.UINT,
                             ctypes.POINTER(ctypes.c_void_p))(
                        coll, i, ctypes.byref(dev))) != 0 or not dev:
                    continue
                try:
                    eid = _device_id(dev)
                    out.append({
                        "index": i,
                        "name": _friendly_name(dev),
                        "endpoint_id": eid,
                        "is_default": bool(eid and default_id and eid == default_id),
                    })
                finally:
                    _release(dev)
        finally:
            _release(coll)
    finally:
        _release(enum)
    return out


# -- the render child: a real, separate process that really renders audio ----
def render_child_main(args):
    """Render a continuous sine until the stop file appears.

    This runs as its OWN process because the whole point is a PID: a tone rendered from
    inside the probe would make the probe's own tree the target and there would be
    nothing left to distinguish.
    """
    report_path = args.report
    log_lines = []
    state = {
        "pid": os.getpid(), "state": "starting", "device": args.device,
        "freq": args.freq, "amp": args.amp, "frames_written": 0,
        "seconds_rendered": 0.0, "log": log_lines, "error": None,
    }

    def flush(state_name):
        state["state"] = state_name
        tmp = report_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1)
        os.replace(tmp, report_path)

    def log(msg):
        log_lines.append("%.3f %s" % (time.time(), msg))

    try:
        com_hr, _owed = _com_init(args.com)
        log("CoInitializeEx(%s) -> %s" % (args.com, _hx(com_hr)))
        endpoints = list_render_endpoints()
        log("render endpoints: %d" % len(endpoints))
        for ep in endpoints:
            log("  [%d] %s default=%s" % (ep["index"], ep["name"], ep["is_default"]))

        needle = (args.device or "").lower()
        matches = [ep for ep in endpoints if needle and needle in (ep["name"] or "").lower()]
        if not matches:
            state["error"] = ("no ACTIVE render endpoint matches %r; saw: %s"
                              % (args.device, [ep["name"] for ep in endpoints]))
            flush("error")
            return 2

        # Prefer a NON-default endpoint: rendering into the system default is what the
        # owner hears, and `_main/inject-all-probe.py` already established the
        # refusal convention (exit 4) plus SOTTO_ALLOW_AUDIBLE as the opt-in.
        chosen = next((ep for ep in matches if not ep["is_default"]), None)
        if chosen is None:
            if os.environ.get("SOTTO_ALLOW_AUDIBLE") != "1":
                state["error"] = ("the only match for %r is the SYSTEM DEFAULT output (%s); "
                                  "refusing to play a test tone at the owner. "
                                  "Set SOTTO_ALLOW_AUDIBLE=1 to override."
                                  % (args.device, matches[0]["name"]))
                flush("refused")
                return 4
            chosen = matches[0]

        state["endpoint"] = chosen["name"]
        state["endpoint_id"] = chosen["endpoint_id"]
        state["endpoint_is_default"] = chosen["is_default"]
        state["endpoint_index"] = chosen["index"]
        log("chosen endpoint: %s (default=%s)" % (chosen["name"], chosen["is_default"]))

        enum = _enumerator()
        dev = ctypes.c_void_p()
        try:
            # IMMDeviceEnumerator::GetDevice (vtable 5) by endpoint id -- the same
            # device the census just described, not a second, drifting lookup.
            hr = int(_vtbl(enum, 5, HRESULT, wintypes.LPCWSTR,
                           ctypes.POINTER(ctypes.c_void_p))(
                enum, chosen["endpoint_id"], ctypes.byref(dev)))
            log("GetDevice -> %s" % _hx(hr))
            if hr != 0 or not dev:
                state["error"] = "GetDevice: %s" % _fmt(hr)
                flush("error")
                return 2

            client = ctypes.c_void_p()
            hr = int(_vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD,
                           ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
                dev, ctypes.byref(IID_IAudioClient), CLSCTX_INPROC_SERVER, None,
                ctypes.byref(client)))
            log("Activate(IAudioClient) -> %s" % _hx(hr))
            if hr != 0 or not client:
                state["error"] = "Activate(IAudioClient): %s" % _fmt(hr)
                flush("error")
                return 2
            try:
                mix = ctypes.POINTER(WAVEFORMATEX)()
                hr = int(_vtbl(client, 8, HRESULT,
                               ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))(
                    client, ctypes.byref(mix)))
                log("GetMixFormat -> %s" % _hx(hr))
                if hr != 0 or not mix:
                    state["error"] = "GetMixFormat: %s" % _fmt(hr)
                    flush("error")
                    return 2
                fmt = _wfx_kind(mix)
                state["rate"] = fmt["rate"]
                state["channels"] = fmt["channels"]
                state["bits"] = fmt["bits"]
                state["sample_kind"] = fmt["label"]
                log("mix format: %d Hz %d ch %s (block_align=%d)"
                    % (fmt["rate"], fmt["channels"], fmt["label"], fmt["block_align"]))
                if fmt["bits"] not in (16, 32):
                    state["error"] = "unsupported mix format: %s" % fmt
                    flush("error")
                    return 2

                hr = int(_vtbl(client, 3, HRESULT, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_int64, ctypes.c_int64,
                               ctypes.POINTER(WAVEFORMATEX), ctypes.c_void_p)(
                    client, AUDCLNT_SHAREMODE_SHARED, 0, HNS_100MS, 0, mix, None))
                log("Initialize(SHARED) -> %s" % _hx(hr))
                if hr != 0:
                    state["error"] = "Initialize(SHARED): %s" % _fmt(hr)
                    flush("error")
                    return 2

                bufsize = wintypes.UINT(0)
                _vtbl(client, 4, HRESULT, ctypes.POINTER(wintypes.UINT))(
                    client, ctypes.byref(bufsize))
                get_padding = _vtbl(client, 6, HRESULT, ctypes.POINTER(wintypes.UINT))
                render = ctypes.c_void_p()
                hr = int(_vtbl(client, 14, HRESULT, ctypes.POINTER(GUID),
                               ctypes.POINTER(ctypes.c_void_p))(
                    client, ctypes.byref(IID_IAudioRenderClient), ctypes.byref(render)))
                log("GetService(Render) -> %s" % _hx(hr))
                if hr != 0 or not render:
                    state["error"] = "GetService(IAudioRenderClient): %s" % _fmt(hr)
                    flush("error")
                    return 2

                get_buffer = _vtbl(render, 3, HRESULT, wintypes.UINT,
                                   ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)))
                release_buffer = _vtbl(render, 4, HRESULT, wintypes.UINT, wintypes.DWORD)

                rate = fmt["rate"]
                channels = fmt["channels"]
                bits = fmt["bits"]
                float_fmt = fmt["float_fmt"]
                scale = 1.0 if float_fmt else float((1 << (bits - 1)) - 1)
                step = 2.0 * math.pi * float(args.freq) / float(rate)
                amp = float(args.amp)
                phase = [0.0]

                def fill(frames_wanted):
                    """Fill exactly `frames_wanted` frames of sine and release them."""
                    p = ctypes.POINTER(ctypes.c_ubyte)()
                    hr2 = int(get_buffer(render, frames_wanted, ctypes.byref(p)))
                    if hr2 != 0 or not p:
                        return hr2 & 0xFFFFFFFF
                    ph = phase[0]
                    if float_fmt:
                        out = array.array("f")
                        for _f in range(frames_wanted):
                            s = math.sin(ph) * amp
                            ph += step
                            for _c in range(channels):
                                out.append(s)
                        ctypes.memmove(p, out.tobytes(), len(out) * 4)
                    elif bits == 16:
                        out = array.array("h")
                        for _f in range(frames_wanted):
                            v = int(round(math.sin(ph) * amp * scale))
                            ph += step
                            for _c in range(channels):
                                out.append(v)
                        ctypes.memmove(p, out.tobytes(), len(out) * 2)
                    else:
                        out = array.array("i")
                        for _f in range(frames_wanted):
                            v = int(round(math.sin(ph) * amp * scale))
                            ph += step
                            for _c in range(channels):
                                out.append(v)
                        ctypes.memmove(p, out.tobytes(), len(out) * 4)
                    phase[0] = ph
                    return int(release_buffer(render, frames_wanted, 0)) & 0xFFFFFFFF

                # Pre-roll the whole ring, THEN Start: the documented shared-mode
                # pattern, and it means the first capture packet already has signal
                # instead of a hole.
                hr = fill(int(bufsize.value))
                log("prefill %d frames -> %s" % (bufsize.value, _hx(hr)))
                if hr != 0:
                    state["error"] = "render prefill: %s" % _fmt(hr)
                    flush("error")
                    return 2
                state["frames_written"] = int(bufsize.value)

                hr = int(_vtbl(client, 10, HRESULT)(client))
                log("Start -> %s" % _hx(hr))
                if hr != 0:
                    state["error"] = "IAudioClient::Start: %s" % _fmt(hr)
                    flush("error")
                    return 2

                flush("rendering")

                chunk = max(1, rate // 100)  # 10 ms
                started = time.time()
                deadline = started + float(args.max_seconds)
                stop_reason = "max-seconds"
                while time.time() < deadline:
                    if args.stop_file and os.path.exists(args.stop_file):
                        stop_reason = "stop-file"
                        break
                    pad = wintypes.UINT(0)
                    if int(get_padding(client, ctypes.byref(pad))) != 0:
                        stop_reason = "GetCurrentPadding failed"
                        break
                    avail = int(bufsize.value) - int(pad.value)
                    if avail < chunk:
                        time.sleep(0.004)
                        continue
                    n = min(chunk, avail)
                    hr = fill(n)
                    if hr != 0:
                        stop_reason = "fill %s" % _hx(hr)
                        break
                    state["frames_written"] += n

                state["seconds_rendered"] = round(time.time() - started, 3)
                state["stop_reason"] = stop_reason
                time.sleep(0.35)  # let the ring drain so the tail is really rendered
                hr = int(_vtbl(client, 11, HRESULT)(client))
                log("Stop -> %s" % _hx(hr))
                flush("done")
                return 0
            finally:
                _release(client)
        finally:
            _release(enum)
            _release(dev)
    except Exception as exc:  # pragma: no cover - the report IS the diagnostic
        import traceback
        state["error"] = "%r" % (exc,)
        log_lines.append(traceback.format_exc())
        try:
            flush("error")
        except Exception:
            pass
        return 2


# -- the probe battery -------------------------------------------------------
class Probe:
    def __init__(self, args):
        self.args = args
        self.lines = []
        self.activate_fn = None
        self.results = {"controls": {}, "env": {}}

    def log(self, msg=""):
        self.lines.append(msg)
        print(msg, flush=True)

    def run(self):
        args = self.args
        self.log("=" * 78)
        self.log("PROCESS-LOOPBACK PROBE -- WASAPI per-process capture via")
        self.log("  ActivateAudioInterfaceAsync(VAD\\Process_Loopback)")
        self.log("=" * 78)
        self.log("python      : %s" % sys.version.replace("\n", " "))
        self.log("pid         : %d" % os.getpid())
        self.log("seconds     : %s   device substring: %r   com: %s"
                 % (args.seconds, args.device, args.com))

        # ---- declared structure sizes: the layout claim, checked on this build
        sz_params = ctypes.sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
        sz_plp = ctypes.sizeof(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)
        sz_pv = ctypes.sizeof(PROPVARIANT)
        off_blob = PROPVARIANT.blob.offset
        sz_wfx = ctypes.sizeof(WAVEFORMATEX)
        sz_wfx_ext = ctypes.sizeof(WAVEFORMATEXTENSIBLE)
        off_mask = WAVEFORMATEXTENSIBLE.dwChannelMask.offset
        off_sub = WAVEFORMATEXTENSIBLE.SubFormat.offset
        self.log("")
        self.log("-- declared ABI -------------------------------------------------------")
        self.log("sizeof(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS) = %d  (expect 8)" % sz_plp)
        self.log("sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)       = %d  (expect 12)" % sz_params)
        self.log("sizeof(PROPVARIANT)                         = %d  (expect 24)" % sz_pv)
        self.log("PROPVARIANT.blob offset                     = %d  (expect 8)" % off_blob)
        # The format struct is a GATE, not a footnote: a 44-byte WAVEFORMATEXTENSIBLE
        # misreads a float32 endpoint as int32, and the render arm then writes int32 PCM
        # into a float stream -- ~5e-8 per sample, i.e. a silent positive control that
        # looks like a capture failure.  That is exactly what run 2 measured.
        self.log("sizeof(WAVEFORMATEX)                        = %d  (expect 20)" % sz_wfx)
        self.log("sizeof(WAVEFORMATEXTENSIBLE)                = %d  (expect 40)" % sz_wfx_ext)
        self.log("WAVEFORMATEXTENSIBLE.dwChannelMask offset   = %d  (expect 20)" % off_mask)
        self.log("WAVEFORMATEXTENSIBLE.SubFormat offset       = %d  (expect 24)" % off_sub)
        self.results["env"]["sizes"] = {
            "process_loopback_params": sz_plp, "activation_params": sz_params,
            "propvariant": sz_pv, "blob_offset": off_blob,
            "waveformatex": sz_wfx, "waveformatextensible": sz_wfx_ext,
            "dwchannelmask_offset": off_mask, "subformat_offset": off_sub,
        }
        if sz_wfx_ext != 40 or off_sub != 24 or off_mask != 20:
            self.log("STEP FAILED: WAVEFORMATEXTENSIBLE is %d bytes with SubFormat at %d"
                     % (sz_wfx_ext, off_sub))
            self.log("  (the real struct is 40 bytes with SubFormat at 24; anything else")
            self.log("   misreads the endpoint's subformat and silently breaks the tone)")
            return 2
        if sz_params != 12 or off_blob != 8:
            self.log("STEP FAILED: the declared structures do not match the ABI that the")
            self.log("  shipped Microsoft sample and the Rust wasapi crate both describe.")
            return 2

        # ---- export resolution
        base, proc, activate_fn = resolve_activate_export()
        self.log("")
        self.log("-- ActivateAudioInterfaceAsync ----------------------------------------")
        self.log("Mmdevapi.dll module base    = %s" % ("0x%X" % base if base else "NOT LOADED"))
        self.log("ActivateAudioInterfaceAsync = %s" % ("0x%X" % proc if proc else "NOT FOUND"))
        self.results["env"]["module_base"] = None if not base else "0x%X" % base
        self.results["env"]["proc_address"] = None if not proc else "0x%X" % proc
        if not proc:
            self.log("STEP FAILED: the export does not exist in this DLL.")
            return 2
        self.activate_fn = activate_fn

        # ---- COM
        com_hr, owed = _com_init(args.com)
        self.log("CoInitializeEx(%s) -> %s  (reference_owed=%s)"
                 % (args.com, _hx(com_hr), owed))
        self.results["env"]["coinitializeex"] = _hx(com_hr)
        if com_hr == RPC_E_CHANGED_MODE:
            self.log("NOTE: this thread was already in the other apartment; continuing.")

        try:
            return self._battery()
        finally:
            if owed:
                _com_uninit()

    # -- one capture arm, end to end ------------------------------------------
    def _arm(self, label, pid, mode, layout, seconds, note=""):
        self.log("")
        self.log("-- ARM %s --" % label)
        self.log("   target pid=%d mode=%s layout=%s%s"
                 % (pid, "INCLUDE_TREE"
                    if mode == PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE
                    else "EXCLUDE_TREE", layout, (" " + note) if note else ""))
        act = activate_process_loopback(self.activate_fn, pid, mode, layout, name=label)
        self.log("   ActivateAudioInterfaceAsync -> %s" % _hx(act["hr_call"]))
        if act["qi"]:
            self.log("   QueryInterface seen         -> %s"
                     % ", ".join(n for _w, n in act["qi"]))
        if act["hr_call"] != 0:
            self.log("   FAILED: %s" % _fmt(act["hr_call"]))
            return {"ok": False, "act": act, "measure": None, "hr": act["hr_call"],
                    "why": "ActivateAudioInterfaceAsync"}
        if act["timeout"]:
            self.log("   FAILED: ActivateCompleted never fired")
            return {"ok": False, "act": act, "measure": None, "hr": None, "why": "timeout"}
        self.log("   GetActivateResult           -> %s" % _hx(act["hr_get_result"]))
        self.log("   activation result (HRESULT) -> %s%s"
                 % (_hx(act["hr_activate"]),
                    "" if act["hr_activate"] == 0 else "  " + _fmt(act["hr_activate"])))
        if act["hr_activate"] != 0 or not act["client"]:
            if act.get("error"):
                self.log("   %s" % act["error"])
            return {"ok": False, "act": act, "measure": None, "hr": act["hr_activate"],
                    "why": "activation result"}

        self.log("   IAudioClient obtained       -> True")
        opened = open_capture(act["client"], self.log)
        if not opened["ok"]:
            self.log("   FAILED: %s" % opened.get("error"))
            close_capture(act["client"], opened)
            _release_client(act)
            return {"ok": False, "act": act, "measure": None, "open": opened,
                    "hr": act["hr_activate"], "why": "Initialize/GetService"}

        measured = measure_capture(opened["capture"], seconds, opened["format"],
                                   self.log, label=label)
        close_capture(act["client"], opened)
        _release_client(act)
        self.log("   released")
        return {"ok": True, "act": act, "open": opened, "measure": measured, "hr": 0,
                "why": None}

    def _battery(self):
        args = self.args

        # ---- render endpoint census (context: which endpoint will carry the tone)
        self.log("")
        self.log("-- render endpoint census --------------------------------------------")
        try:
            endpoints = list_render_endpoints()
        except Exception as exc:
            self.log("STEP FAILED: %s" % (exc,))
            return 2
        for ep in endpoints:
            self.log("   [%2d] %-52s default=%s" % (ep["index"], ep["name"], ep["is_default"]))
        self.results["env"]["render_endpoints"] = endpoints
        if not endpoints:
            self.log("STEP FAILED: no ACTIVE render endpoint.")
            return 2
        needle = (args.device or "").lower()
        matches = [ep for ep in endpoints if needle and needle in (ep["name"] or "").lower()]
        if not matches:
            self.log("STEP FAILED: no render endpoint matches %r (see the census above)."
                     % args.device)
            return 2
        non_default = [ep for ep in matches if not ep["is_default"]]
        if not non_default and os.environ.get("SOTTO_ALLOW_AUDIBLE") != "1":
            self.log("REFUSED: the only match for %r is the SYSTEM DEFAULT output (%s)."
                     % (args.device, matches[0]["name"]))
            self.log("  This probe must not make the owner hear a test tone.")
            self.log("  Set SOTTO_ALLOW_AUDIBLE=1 to override.")
            return 4

        # ---- layout arms: which PROPVARIANT blob layout does this build accept?
        # Run against our OWN pid while nothing is rendering: cheap, and it is also a
        # first data point (a non-rendering target should be silent).
        self.log("")
        self.log("-- LAYOUT ARMS (target = this probe's own pid, nothing rendering) ----")
        layout_results = {}
        for layout in ("direct", "wrapped"):
            act = activate_process_loopback(
                self.activate_fn, os.getpid(),
                PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE, layout,
                name="layout-" + layout)
            ok = (act["hr_call"] == 0 and not act["timeout"]
                  and act["hr_activate"] == 0 and bool(act["client"]))
            layout_results[layout] = {
                "hr_call": _hx(act["hr_call"]),
                "hr_activate": _hx(act["hr_activate"]),
                "ok": bool(ok),
                "blob_cbSize": act["blob_cbSize"],
                "qi": [n for _w, n in act["qi"]],
            }
            self.log("   layout=%-8s blob.cbSize=%-3d hr_call=%s hr_activate=%s -> %s"
                     % (layout, act["blob_cbSize"], _hx(act["hr_call"]),
                        _hx(act["hr_activate"]), "ACCEPTED" if ok else "REFUSED"))
            if act["qi"]:
                self.log("       QueryInterface: %s" % ", ".join(n for _w, n in act["qi"]))
            if not ok:
                if act["hr_call"] != 0:
                    self.log("       %s" % _fmt(act["hr_call"]))
                elif act["hr_activate"] != 0:
                    self.log("       %s" % _fmt(act["hr_activate"]))
                elif act["timeout"]:
                    self.log("       ActivateCompleted never fired")
            _release_client(act)
        self.results["layout_arms"] = layout_results

        winning = next((l for l in ("direct", "wrapped") if layout_results[l]["ok"]), None)
        if not winning:
            self.log("")
            self.log("STEP FAILED: NEITHER layout activated a process-loopback IAudioClient.")
            self.log("  The API surface is reachable but this build refused both blobs.")
            return 2
        self.log("")
        self.log("   WINNING LAYOUT: %s" % winning)
        self.results["winning_layout"] = winning

        # ---- negative control B: invalid PIDs must be REJECTED
        self.log("")
        self.log("-- NEGATIVE CONTROL B (informational): does an invalid pid FAIL? -------")
        negb = []
        for bad_pid in (0, 0xFFFFFFFE):
            act = activate_process_loopback(
                self.activate_fn, bad_pid,
                PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE, winning,
                name="negB-%d" % bad_pid)
            rejected = not (act["hr_call"] == 0 and not act["timeout"]
                            and act["hr_activate"] == 0 and bool(act["client"]))
            negb.append({"pid": bad_pid, "hr_call": _hx(act["hr_call"]),
                         "hr_activate": _hx(act["hr_activate"]),
                         "rejected": bool(rejected), "timeout": bool(act["timeout"])})
            self.log("   pid=0x%08X  hr_call=%s  hr_activate=%s  -> %s"
                     % (bad_pid, _hx(act["hr_call"]), _hx(act["hr_activate"]),
                        "REJECTED (as required)" if rejected else "ACCEPTED (unexpected)"))
            if act["hr_call"] != 0:
                self.log("       %s" % _fmt(act["hr_call"]))
            elif act["hr_activate"] != 0:
                self.log("       %s" % _fmt(act["hr_activate"]))
            elif act["timeout"]:
                self.log("       ActivateCompleted never fired")
            _release_client(act)
        negb_ok = all(r["rejected"] for r in negb)
        self.results["controls"]["negative_b"] = negb
        self.results["controls"]["negative_b_ok"] = bool(negb_ok)
        if not negb_ok:
            self.log("   DEVIATION (informational, does NOT decide the exit code): this build")
            self.log("   ACCEPTED an invalid process id, so the API is not fail-closed against")
            self.log("   garbage pids. The discriminating control is NEGATIVE-A.")

        # ---- spawn the render child
        self.log("")
        self.log("-- RENDER CHILD --------------------------------------------------------")
        workdir = tempfile.mkdtemp(prefix="plp-", dir=(os.environ.get("TMPDIR") or None))
        report_path = os.path.join(workdir, "render-report.json")
        stop_path = os.path.join(workdir, "stop")
        child_log = os.path.join(workdir, "render-child.log")
        cmd = [
            sys.executable, os.path.abspath(__file__), "--render-child",
            "--device", args.device, "--freq", str(args.freq), "--amp", str(args.amp),
            "--report", report_path, "--stop-file", stop_path,
            "--max-seconds", str(max(30.0, args.seconds + 25.0)), "--com", args.com,
        ]
        self.log("   workdir: %s" % workdir)
        self.log("   cmd    : %s" % " ".join('"%s"' % c if " " in c else c for c in cmd))
        self.results["env"]["workdir"] = workdir
        child = None
        try:
            with open(child_log, "w", encoding="utf-8") as logfh:
                child = subprocess.Popen(
                    cmd, stdout=logfh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW, cwd=workdir)
            self.log("   spawned pid=%d (CREATE_NO_WINDOW, so no console appears)"
                     % child.pid)
            self.results["env"]["child_pid"] = child.pid

            state = None
            deadline = time.time() + 20.0
            while time.time() < deadline:
                if os.path.exists(report_path):
                    try:
                        with open(report_path, "r", encoding="utf-8") as fh:
                            state = json.load(fh)
                    except Exception:
                        state = None
                    if state and state.get("state") in ("rendering", "done", "error",
                                                        "refused"):
                        break
                if child.poll() is not None:
                    break
                time.sleep(0.05)

            if not state or state.get("state") not in ("rendering", "done"):
                self.log("STEP FAILED: the render child never reached 'rendering'.")
                self.log("   child rc=%s" % child.poll())
                if state:
                    self.log("   report: %s" % json.dumps(
                        {k: v for k, v in state.items() if k != "log"}))
                for line in self._tail(child_log):
                    self.log("   child| " + line)
                if child.poll() is None:
                    self._stop_child(child, stop_path)
                return 2

            self.log("   child state=%s pid=%s endpoint=%r default=%s rate=%s ch=%s %s"
                     % (state.get("state"), state.get("pid"), state.get("endpoint"),
                        state.get("endpoint_is_default"), state.get("rate"),
                        state.get("channels"), state.get("sample_kind")))
            if state.get("state") == "done":
                self.log("   NOTE: the child had ALREADY finished rendering before the")
                self.log("   first arm started; frames_written=%s"
                         % state.get("frames_written"))
            self.results["env"]["child_report_start"] = {
                k: v for k, v in state.items() if k != "log"}

            # ---- POSITIVE CONTROL
            pos = self._arm("POSITIVE (target = render child tree)", child.pid,
                            PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE, winning,
                            args.seconds,
                            note="[the tone is playing on %r]" % state.get("endpoint"))
            self.results["controls"]["positive"] = self._summary(pos)

            # ---- NEGATIVE CONTROL A: a live process that renders nothing, while the
            # tone is STILL playing. This is the arm that separates per-process from
            # per-endpoint.
            self.log("")
            self.log("-- NEGATIVE CONTROL A: a live, non-rendering process, tone still up -")
            quiet = subprocess.Popen(
                ["cmd.exe", "/c", "timeout", "/t", "20", "/nobreak"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            self.log("   quiet pid=%d (cmd /c timeout /t 20) -- renders nothing" % quiet.pid)
            try:
                nega = self._arm("NEGATIVE-A (target = non-rendering cmd)", quiet.pid,
                                 PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE,
                                 winning, min(2.0, args.seconds),
                                 note="[tone still playing on %r]" % state.get("endpoint"))
            finally:
                try:
                    quiet.kill()
                except Exception:
                    pass
            self.results["controls"]["negative_a"] = self._summary(nega)

            # ---- EXCLUDE mode (informational, never decides the exit code)
            if not args.no_exclude_arm:
                excl = self._arm("EXCLUDE (target = render child, mode=EXCLUDE)",
                                 child.pid,
                                 PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE,
                                 winning, min(2.0, args.seconds),
                                 note="[informational: expected silent]")
                self.results["controls"]["exclude"] = self._summary(excl)

            # ---- collect the child
            self._stop_child(child, stop_path)
            final = None
            if os.path.exists(report_path):
                try:
                    with open(report_path, "r", encoding="utf-8") as fh:
                        final = json.load(fh)
                except Exception:
                    final = None
            if final:
                self.log("")
                self.log("-- render child, final ------------------------------------------------")
                self.log("   state=%s frames_written=%s seconds_rendered=%s stop_reason=%s"
                         % (final.get("state"), final.get("frames_written"),
                            final.get("seconds_rendered"), final.get("stop_reason")))
                self.results["env"]["child_report_final"] = {
                    k: v for k, v in final.items() if k != "log"}
                self.results["env"]["child_log"] = final.get("log")

            return self._verdict()
        finally:
            if child is not None and child.poll() is None:
                self._stop_child(child, stop_path)
            if not args.keep:
                shutil.rmtree(workdir, ignore_errors=True)

    def _stop_child(self, child, stop_path):
        try:
            with open(stop_path, "w", encoding="utf-8") as fh:
                fh.write("stop\n")
        except Exception:
            pass
        try:
            child.wait(timeout=10)
        except Exception:
            try:
                child.kill()
            except Exception:
                pass

    @staticmethod
    def _tail(path, n=25):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return [l.rstrip() for l in fh.readlines()[-n:]]
        except Exception:
            return []

    @staticmethod
    def _summary(arm):
        if not arm:
            return {"ok": False, "why": "skipped"}
        return {"ok": bool(arm.get("ok")), "why": arm.get("why"),
                "hr": None if arm.get("hr") is None else _hx(arm["hr"]),
                "measure": arm.get("measure")}

    def _verdict(self):
        c = self.results["controls"]
        pos = c.get("positive") or {}
        nega = c.get("negative_a") or {}
        negb_ok = bool(c.get("negative_b_ok"))
        pm = pos.get("measure") or {}
        nm = nega.get("measure") or {}
        pos_packets = pm.get("packets")
        pos_peak = pm.get("peak")
        pos_ok = bool(pos.get("ok")) and (pos_packets or 0) > 0 and (pos_peak or 0.0) > PEAK_FLOOR
        nega_silent = bool(nega.get("ok")) and (
            (nm.get("packets") or 0) == 0 or (nm.get("peak") or 0.0) <= PEAK_FLOOR)

        self.log("")
        self.log("=" * 78)
        self.log("MEASURED")
        self.log("  POSITIVE  ok=%-5s packets=%-5s frames=%-8s peak=%-9s rms=%-9s silent_pkts=%s"
                 % (pos.get("ok"), pos_packets, pm.get("frames"), pos_peak, pm.get("rms"),
                    pm.get("silent_packets")))
        self.log("  NEG-A     ok=%-5s packets=%-5s frames=%-8s peak=%-9s rms=%-9s silent_pkts=%s"
                 % (nega.get("ok"), nm.get("packets"), nm.get("frames"), nm.get("peak"),
                    nm.get("rms"), nm.get("silent_packets")))
        ex_arm = c.get("exclude") or {}
        ex = ex_arm.get("measure") or {}
        if ex:
            self.log("  EXCLUDE   ok=%-5s packets=%-5s peak=%-9s (informational)"
                     % (ex_arm.get("ok"), ex.get("packets"), ex.get("peak")))
        self.log("  NEG-B     %s  (informational)"
                 % ("all invalid pids REJECTED"
                    if negb_ok else "DEVIATION: an invalid pid was ACCEPTED"))
        self.log("  thresholds: positive needs packets>0 AND peak>%.2f; negative-a needs"
                 " packets==0 OR peak<=%.2f" % (PEAK_FLOOR, PEAK_FLOOR))
        self.log("")

        if pos_ok and nega_silent:
            self.log("VERDICT: PROCESS LOOPBACK PROVEN -- one process's audio captured by pid,")
            self.log("  with the same capture silent for a non-rendering pid at the same moment.")
            self.log("  deciding numbers: positive peak=%.6f packets=%d; negative-a peak=%.6f packets=%d"
                     % (pos_peak or 0.0, pos_packets or 0, nm.get("peak") or 0.0,
                        nm.get("packets") or 0))
            if not negb_ok:
                self.log("  DEVIATION (informational, does not change this verdict): an invalid")
                self.log("  TargetProcessId (0xFFFFFFFE) was ACCEPTED; pid 0 WAS rejected. The API")
                self.log("  is not fail-closed against garbage pids; NEGATIVE-A carries the proof.")
            self.log("EXIT: 0")
            return 0
        if pos.get("ok") and not pos_ok:
            self.log("VERDICT: PLUMBING-ONLY -- POSITIVE CONTROL SILENT.")
            self.log("  The activation, the IAudioClient, GetService and the pump all")
            self.log("  succeeded (%d packet(s), peak=%s) but no signal from the render"
                     % (pos_packets or 0, pos_peak))
            self.log("  child arrived. This is a REAL outcome and is NOT hidden.")
            if not nega_silent:
                self.log("  negative-a ALSO was not silent (peak=%s packets=%s)"
                         % (nm.get("peak"), nm.get("packets")))
            self.log("EXIT: 3")
            return 3
        self.log("VERDICT: STEP FAILED -- the positive arm did not complete.")
        self.log("  step: %s   hr=%s" % (pos.get("why"), pos.get("hr")))
        self.log("EXIT: 2")
        return 2


# -- entry point -------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        description="Prove or refute WASAPI PROCESS LOOPBACK (per-process capture) with "
                    "a hand-declared ctypes COM surface.")
    p.add_argument("--seconds", type=float, default=3.0,
                   help="capture window per arm (default 3.0)")
    p.add_argument("--device", default="CABLE Input",
                   help="render endpoint substring for the tone (default 'CABLE Input'). "
                        "The system default output is REFUSED unless SOTTO_ALLOW_AUDIBLE=1.")
    p.add_argument("--freq", type=float, default=440.0, help="tone frequency (default 440)")
    p.add_argument("--amp", type=float, default=0.4, help="tone amplitude (default 0.4)")
    p.add_argument("--com", choices=("mta", "sta"), default="mta",
                   help="apartment for CoInitializeEx (default mta)")
    p.add_argument("--json", default=None, help="also write the measured result as JSON")
    p.add_argument("--keep", action="store_true", help="keep the temp workdir")
    p.add_argument("--no-exclude-arm", action="store_true",
                   help="skip the informational EXCLUDE-mode arm")
    # internal: the child re-enters this same file
    p.add_argument("--render-child", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--report", default=None, help=argparse.SUPPRESS)
    p.add_argument("--stop-file", default=None, help=argparse.SUPPRESS)
    p.add_argument("--max-seconds", type=float, default=60.0, help=argparse.SUPPRESS)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.render_child:
        if not args.report:
            print("--render-child needs --report")
            return 2
        return render_child_main(args)

    probe = Probe(args)
    try:
        rc = probe.run()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    if args.json:
        try:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({"exit": rc, "results": probe.results}, fh, indent=1)
            print("\n(json written to %s)" % args.json)
        except Exception as exc:
            print("could not write --json: %r" % (exc,))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
