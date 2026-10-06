"""WASAPI loopback capture -- rung (a) of Sotto's universal audio ladder.

WHY THIS EXISTS
---------------
`worker/config.json` used to name three devices that exist only on machines with
VB-Cable / VoiceMeeter installed. On an ordinary Windows PC none of them exist,
so the shipped product could not capture system audio anywhere else. sounddevice
(PortAudio) cannot help: PortAudio exposes no WASAPI loopback endpoint, which is
precisely why the config hardcoded a virtual cable.

WHAT WINDOWS ACTUALLY OFFERS (the vendor-documented, driver-free path)
---------------------------------------------------------------------
Capture "whatever the PC is playing" by opening the DEFAULT RENDER endpoint as a
loopback CAPTURE client:

  1. CoCreateInstance(CLSID_MMDeviceEnumerator) -> IMMDeviceEnumerator
  2. IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender, eConsole) -> IMMDevice
  3. IMMDevice::Activate(IID_IAudioClient) -> IAudioClient
  4. IAudioClient::GetMixFormat() -> the endpoint's MIX format
  5. IAudioClient::Initialize(AUDCLNT_SHAREMODE_SHARED,
                               AUDCLNT_STREAMFLAGS_LOOPBACK, ...)
       -- the stream MUST be initialized with the mix format. A loopback stream
          has no format negotiation, so asking for 16 kHz mono (what the ASR
          model wants) fails; the conversion is done here instead.
  6. IAudioClient::GetService(IID_IAudioCaptureClient) -> IAudioCaptureClient
  7. Start(), then poll GetNextPacketSize/GetBuffer/ReleaseBuffer.

Documentation this follows (Microsoft Learn; the pages are the authority, the
URLs are given so a reader can check them):
  * Core Audio / WASAPI loopback recording:
    https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording
  * IAudioClient::Initialize and AUDCLNT_STREAMFLAGS_LOOPBACK:
    https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudioclient-initialize
  * The default-endpoint enumeration used by step 2:
    https://learn.microsoft.com/windows/win32/coreaudio/device-roles
  * Windows 10 2004+ process-scoped loopback (NOT required by this rung, but the
    modern sibling of AUDCLNT_STREAMFLAGS_LOOPBACK):
    https://learn.microsoft.com/windows/win32/audio/process-loopback

Windows only feeds a loopback client while that endpoint is actually rendering,
so a loopback tap legitimately reads digital silence when nothing is playing.
That is why the caller must judge a tap on a measured peak over N blocks and
never on "it opened".

No third-party dependency: ctypes + the Windows DLLs already present.
"""

import ctypes
import sys
import threading
import time
from ctypes import wintypes

# ── Win32 / COM constants ─────────────────────────────────────────────────────
HRESULT = ctypes.c_long
CLSCTX_INPROC_SERVER = 1
COINIT_MULTITHREADED = 0
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106: already initialised, other mode
S_OK = 0            # CoInitializeEx: COM started here;            reference taken
S_FALSE = 1         # CoInitializeEx: COM already running here;    reference taken
# What a successful `_com_init()` leaves the caller OWING. They are kept apart
# because CoUninitialize is due for exactly one of them.
COM_REF_TAKEN = "taken"    # S_OK / S_FALSE: the caller must CoUninitialize
COM_ALREADY = "already"    # RPC_E_CHANGED_MODE: nothing was taken to give back

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002  # GetBuffer: this packet is SILENCE

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

E_RENDER = 0
E_CONSOLE = 0
E_MULTIMEDIA = 1

# REFERENCE_TIME units: 100 ns. 100 ms buffer, the documented fallback.
HNS_100MS = 1_000_000


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
    tail = [int(d[i : i + 2], 16) for i in (0, 2)]
    tail += [int(e[i : i + 2], 16) for i in (0, 2, 4, 6, 8, 10)]
    return GUID(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*tail))


CLSID_MMDeviceEnumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioClient = _guid("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioCaptureClient = _guid("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
IID_IPropertyStore = _guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")

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


# ── COM plumbing ──────────────────────────────────────────────────────────────
def _ole32():
    return ctypes.WinDLL("ole32", use_last_error=True)


# ── COM init: the vendor contract, not an assumption ──────────────────────────
# CoInitializeEx(NULL, COINIT_MULTITHREADED) has THREE documented outcomes, and a
# caller has to tell them apart because they differ in what it then OWES:
#   S_OK               (0) COM started here in the MTA;          A REFERENCE IS TAKEN
#   S_FALSE            (1) COM already running here in the MTA;  A REFERENCE IS TAKEN
#                          "The COM library is already initialized on this thread."
#                          Also a SUCCESS code.
#   RPC_E_CHANGED_MODE     already running here in ANOTHER apartment. The CALL
#                          fails and no reference is taken -- but COM IS
#                          initialised and usable on this thread.
# Everything else (E_FAIL, E_OUTOFMEMORY, E_UNEXPECTED, ...) is a real failure and
# nothing was taken. Microsoft Learn, CoInitializeEx (Return value + Remarks: "each
# successful call to CoInitialize or CoInitializeEx, including any call that returns
# S_FALSE, must be balanced by a corresponding call to CoUninitialize"):
#   https://learn.microsoft.com/windows/win32/api/combaseapi/nf-combaseapi-coinitializeex
#
# The gate used to be `if hr not in (0, RPC_E_CHANGED_MODE): raise`. It REFUSED
# S_FALSE -- a success code -- and never gave back the reference it took, so in a
# process where nothing had initialised COM first the SECOND call on that thread
# returned S_FALSE and raised. The ladder calls default_render_endpoint() twice on
# one thread before any stream exists (device_candidates() ->
# loopback_device_spec(), then WasapiLoopbackTap.__init__), so rung (a) -- WASAPI
# loopback of the default render endpoint, the only rung that needs no virtual
# cable -- could never open.
# MEASURED 2026-10-06 (`_main/flat-endpoint-ladder.py mta`, the branch where the
# thread was MTA before anything else touched it): candidate list WITHOUT the WASAPI
# rung, peak=0.000092, nonzero_blocks=0, worker rc=3 -- the numbers of
# `_main/_live_owner3.log:61`. Same run, post-fix: see `_main/flat-endpoint-AFTER-mta.out`.
def _com_init():
    """Start COM on this thread, or admit it is already running.

    Returns COM_REF_TAKEN when THIS call took a reference, which the caller MUST
    pair with `_com_uninit()`; COM_ALREADY when COM is already running here in
    another apartment and NOTHING was taken (calling CoUninitialize then would
    release someone else's reference, which is why the outcome is returned instead
    of collapsed into a bool). Raises WasapiError on a genuine failure.
    """
    hr = _ole32().CoInitializeEx(None, COINIT_MULTITHREADED)
    if hr in (S_OK, S_FALSE):
        return COM_REF_TAKEN
    if hr == RPC_E_CHANGED_MODE:
        # The thread is already an STA. That is a STATE, not a fault: COM is
        # initialised and the objects this module uses are free-threaded. MEASURED
        # 2026-10-06 on this box (`_main/flat-endpoint-BEFORE.out`): sounddevice/
        # PortAudio leaves the worker's main thread in an STA before rung (a) is
        # ever probed, every CoInitializeEx here then returns RPC_E_CHANGED_MODE,
        # and the loopback tap opens and carries speech (601 blocks,
        # peak=0.465224, 59 captions). Turning this into an error would DELETE
        # rung (a) on exactly such a host -- a regression, not a fix.
        return COM_ALREADY
    raise WasapiError("CoInitializeEx failed: %s" % _fmt(hr))


def _com_uninit():
    """Give back the reference `_com_init()` said it took. Never raises: the
    thread's COM is released on thread exit anyway, and losing the caller's real
    work over a bookkeeping error would be worse than the leak."""
    try:
        _ole32().CoUninitialize()
    except Exception:
        pass


def _vtbl(ptr, index, restype, *argtypes):
    table = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(table[index])


def _release(ptr):
    if ptr:
        try:
            _vtbl(ptr, 2, wintypes.ULONG)()
        except Exception:
            pass


def _fmt(hr):
    try:
        # WinError takes a SIGNED C int. Passing the unsigned form of an HRESULT
        # whose high bit is set (every failure HRESULT: E_FAIL 0x80004005, ...)
        # raised OverflowError, so the message the gate was trying to raise was
        # replaced by a bare Python error coming OUT of the error path itself.
        # Narrowing first is what makes "the negative HRESULTs stay errors"
        # observable as a WasapiError instead of a crash.
        raise ctypes.WinError(ctypes.c_int32(ctypes.c_uint32(hr).value).value)
    except OSError as exc:
        return "%s (0x%08X)" % (exc.strerror, hr & 0xFFFFFFFF)


class WasapiError(RuntimeError):
    pass


class LoopbackEndpoint:
    """Probe result for the default render endpoint (no stream started)."""

    def __init__(self, name, endpoint_id, rate, channels, bits, format_tag, block_align):
        self.name = name
        self.endpoint_id = endpoint_id
        self.rate = rate
        self.channels = channels
        self.bits = bits
        self.format_tag = format_tag  # resolved: PCM or IEEE float
        self.block_align = block_align

    def __repr__(self):
        return "<LoopbackEndpoint %r %d Hz %dch %dbit>" % (
            self.name,
            self.rate,
            self.channels,
            self.bits,
        )


def default_render_endpoint(role=E_CONSOLE):
    """Enumerate the default RENDER endpoint. Raises WasapiError with the HRESULT.

    This is steps 1-2-3-4 of the docstring and is deliberately free of any stream
    state, so it can be used both by the capability probe and by the live tap.

    COM is started for the duration of this call and, when THIS call is the one
    that took the reference, released again on every exit path -- including the
    exception paths, which is what `try/finally` is doing here. Each call is
    therefore balanced on its own, so a second call in the same thread is not
    paying for the first one's reference.
    """
    if sys.platform != "win32":
        raise WasapiError("WASAPI loopback is Windows-only")
    com = _com_init()
    try:
        return _enumerate_default_render_endpoint(role)
    finally:
        if com == COM_REF_TAKEN:
            _com_uninit()


def _enumerate_default_render_endpoint(role):
    """The body of `default_render_endpoint`, with COM already started."""
    ole32 = _ole32()
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = HRESULT
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    enum = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(CLSID_MMDeviceEnumerator),
        None,
        CLSCTX_INPROC_SERVER,
        ctypes.byref(IID_IMMDeviceEnumerator),
        ctypes.byref(enum),
    )
    if hr != 0 or not enum:
        raise WasapiError("MMDeviceEnumerator unavailable: %s" % _fmt(hr))

    dev = ctypes.c_void_p()
    # NOTE: (this, flow, role, ppEndpoint) -- omitting ppEndpoint corrupts the
    # stack; measured as "access violation reading 0xFFFFFFFFFFFFFFFF".
    get_default = _vtbl(
        enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
    )
    hr = get_default(enum, E_RENDER, role, ctypes.byref(dev))
    if hr != 0:
        hr = get_default(enum, E_RENDER, E_MULTIMEDIA, ctypes.byref(dev))
    if hr != 0 or not dev:
        _release(enum)
        raise WasapiError("no default render endpoint: %s" % _fmt(hr))

    # friendly name -- a failure report must name the endpoint
    name = None
    store = ctypes.c_void_p()
    activate = _vtbl(
        dev,
        3,
        HRESULT,
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    if activate(dev, ctypes.byref(IID_IPropertyStore), CLSCTX_INPROC_SERVER, None, ctypes.byref(store)) == 0:
        var = (ctypes.c_ubyte * 24)()
        get_value = _vtbl(
            store, 5, HRESULT, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(ctypes.c_ubyte)
        )
        if get_value(store, ctypes.byref(_PKEY_FRIENDLY), var) == 0:
            if ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0] == 0x001B:  # VT_LPWSTR
                name = ctypes.cast(
                    ctypes.cast(var, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.c_wchar_p
                ).value
        _release(store)

    get_id = _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))
    endpoint_id = None
    buf = ctypes.c_wchar_p()
    if get_id(dev, ctypes.byref(buf)) == 0:
        endpoint_id = buf.value
        ole32.CoTaskMemFree(buf)

    client = ctypes.c_void_p()
    hr = activate(dev, ctypes.byref(IID_IAudioClient), CLSCTX_INPROC_SERVER, None, ctypes.byref(client))
    if hr != 0:
        _release(dev)
        _release(enum)
        raise WasapiError("Activate(IAudioClient) failed: %s" % _fmt(hr))

    mix = ctypes.POINTER(WAVEFORMATEX)()
    get_mix = _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))
    hr = get_mix(client, ctypes.byref(mix))
    if hr != 0 or not mix:
        _release(client)
        _release(dev)
        _release(enum)
        raise WasapiError("GetMixFormat failed: %s" % _fmt(hr))

    wf = mix.contents
    tag = wf.wFormatTag
    if tag == WAVE_FORMAT_EXTENSIBLE and wf.cbSize >= 22:
        # offset 18 = wValidBitsPerSample, 20 = dwChannelMask, 24 = SubFormat GUID
        sub = ctypes.cast(ctypes.addressof(wf) + 24, ctypes.POINTER(GUID)).contents
        tag = sub.Data1 & 0xFFFF
    if tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
        _release(client)
        _release(dev)
        _release(enum)
        raise WasapiError("unsupported mix subformat 0x%04X" % tag)

    ep = LoopbackEndpoint(
        # Some drivers publish no PKEY_Device_FriendlyName (measured on this box:
        # the property store returns nothing). The endpoint ID still identifies
        # it exactly, and a failure report that says "unnamed" tells the owner
        # nothing he can act on.
        name=name or (endpoint_id or "<unnamed render endpoint>"),
        endpoint_id=endpoint_id,
        rate=int(wf.nSamplesPerSec),
        channels=int(wf.nChannels),
        bits=int(wf.wBitsPerSample),
        format_tag=tag,
        block_align=int(wf.nBlockAlign),
    )
    # the client is re-activated inside the tap; release the probe's handles
    _release(client)
    _release(dev)
    _release(enum)
    return ep


class WasapiLoopbackTap:
    """Live loopback capture with the same surface as the sounddevice tap.

    Delivers float32 MONO blocks at the endpoint's MIX rate (typically 48 kHz).
    The caller resamples to the model's 16 kHz -- that conversion cannot happen
    on the device, because a loopback stream must use the mix format.
    """

    def __init__(self, on_block, block_ms=100, role=E_CONSOLE):
        import numpy as np

        self.np = np
        self.on_block = on_block
        self.block_ms = block_ms
        self.ep = default_render_endpoint(role)
        self.rate = self.ep.rate
        self.native_rate = self.rate
        self.channels = self.ep.channels
        self.block = int(self.rate * block_ms / 1000)
        self._stop = threading.Event()
        self._thread = None
        self._com = None          # what `_start` owes COM, released by `close`
        self._client = None
        self._capture = None
        self._enum = None
        self._dev = None
        # Packets GetBuffer marked AUDCLNT_BUFFERFLAGS_SILENT. Counted, not dropped,
        # so "the endpoint is not rendering" is visible instead of being converted
        # into samples by accident.
        self.silent_packets = 0

    # -- name surface the worker's reporting uses ----------------------------
    @property
    def name(self):
        return "WASAPI loopback: %s" % self.ep.name

    @property
    def stream(self):
        """The worker closes taps with `t.stream.stop(); t.stream.close()`.

        Returning self keeps that call site working unchanged: `close()` is
        idempotent and already stops the pump, the client and the thread.
        """
        return self

    def start(self):
        """The worker opens taps with `tap.stream.start()`; same surface."""
        if self._thread is None:
            self._start()
        return self

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _start(self):
        # COM for the tap's LIFETIME. `default_render_endpoint()` in __init__
        # released its own reference when it returned (that is what makes each of
        # its calls balanced), so CoCreateInstance below would otherwise run on a
        # thread whose COM may already be closed. The reference is released by
        # `close()`.
        self._com = _com_init()
        try:
            self._open()
        except BaseException:
            # nothing was opened, so nothing owns the reference
            self._release_com()
            raise

    def _release_com(self):
        if self._com == COM_REF_TAKEN:
            _com_uninit()
        self._com = None

    def _open(self):
        ole32 = _ole32()
        enum = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_MMDeviceEnumerator),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IMMDeviceEnumerator),
            ctypes.byref(enum),
        )
        if hr != 0:
            raise WasapiError("MMDeviceEnumerator unavailable: %s" % _fmt(hr))
        self._enum = enum

        dev = ctypes.c_void_p()
        get_default = _vtbl(
            enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
        )
        hr = get_default(enum, E_RENDER, E_CONSOLE, ctypes.byref(dev))
        if hr != 0:
            hr = get_default(enum, E_RENDER, E_MULTIMEDIA, ctypes.byref(dev))
        if hr != 0:
            raise WasapiError("no default render endpoint: %s" % _fmt(hr))
        self._dev = dev

        activate = _vtbl(
            dev,
            3,
            HRESULT,
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )
        client = ctypes.c_void_p()
        hr = activate(dev, ctypes.byref(IID_IAudioClient), CLSCTX_INPROC_SERVER, None, ctypes.byref(client))
        if hr != 0:
            raise WasapiError("Activate(IAudioClient) failed: %s" % _fmt(hr))
        self._client = client

        mix = ctypes.POINTER(WAVEFORMATEX)()
        hr = _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))(
            client, ctypes.byref(mix)
        )
        if hr != 0 or not mix:
            raise WasapiError("GetMixFormat failed: %s" % _fmt(hr))

        init = _vtbl(
            client,
            3,
            HRESULT,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(WAVEFORMATEX),
            ctypes.c_void_p,
        )
        hr = init(client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 0, 0, mix, None)
        if hr != 0:
            hr = init(
                client,
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK,
                HNS_100MS,
                0,
                mix,
                None,
            )
        if hr != 0:
            raise WasapiError("Initialize(SHARED|LOOPBACK) failed: %s" % _fmt(hr))

        cap = ctypes.c_void_p()
        hr = _vtbl(client, 14, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
            client, ctypes.byref(IID_IAudioCaptureClient), ctypes.byref(cap)
        )
        if hr != 0:
            raise WasapiError("GetService(IAudioCaptureClient) failed: %s" % _fmt(hr))
        self._capture = cap

        hr = _vtbl(client, 10, HRESULT)(client)
        if hr != 0:
            raise WasapiError("IAudioClient::Start failed: %s" % _fmt(hr))

        self._thread = threading.Thread(target=self._pump, name="wasapi-loopback", daemon=True)
        self._thread.start()

    def _pump(self):
        np = self.np
        cap = self._capture
        block_align = self.ep.block_align
        channels = self.ep.channels
        float_fmt = self.ep.format_tag == WAVE_FORMAT_IEEE_FLOAT
        next_size = _vtbl(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))
        get_buffer = _vtbl(
            cap,
            3,
            HRESULT,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(ctypes.c_int64),
        )
        release = _vtbl(cap, 4, HRESULT, wintypes.DWORD)
        # POLL FASTER THAN THE DEVICE'S RING, or frames are dropped where no
        # counter of ours can see them.
        #
        # Measured 2026-10-06 (`_main/` audit): this endpoint grants
        # `GetBufferSize` = 1056 frames = **22 ms** at 48 kHz, and the previous
        # period (`block_ms/1000/4` = 25 ms) was SLOWER than that, so the ring
        # overflowed on every cycle. One knob, same process, same device,
        # same block: period 25 ms -> duty 0.815 (8.15 blocks/s); period 5 ms
        # -> duty 0.999 (9.99 blocks/s). `audio_s` now tracks wall clock.
        #
        # The period is derived from the RING, not from our own block size: our
        # block is 100 ms and says nothing about how fast the device must be
        # drained. `block_ms/20` = 5 ms at the shipped 100 ms setting.
        period = min(0.005, max(0.001, self.block_ms / 1000.0 / 20.0))
        buf = []
        acc = 0
        while not self._stop.is_set():
            n = wintypes.DWORD(0)
            if next_size(cap, ctypes.byref(n)) != 0:
                break
            if n.value == 0:
                time.sleep(period)
                continue
            data = ctypes.POINTER(ctypes.c_ubyte)()
            frames = wintypes.DWORD(0)
            flags = wintypes.DWORD(0)
            pos = ctypes.c_int64(0)
            if get_buffer(cap, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), ctypes.byref(pos)) != 0:
                break
            if frames.value:
                if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data:
                    # AUDCLNT_BUFFERFLAGS_SILENT says the endpoint is not rendering
                    # and the packet's BYTES ARE NOT VALID SAMPLES. The flags were
                    # read and thrown away, so the undefined contents of a silent
                    # packet were decoded as audio -- which is precisely the
                    # dead-endpoint signature the ladder reads as "this device hears
                    # something": MEASURED peak=0.000092 with nonzero_blocks>0.
                    # Microsoft Learn, IAudioCaptureClient::GetBuffer (flags):
                    #   https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-getbuffer
                    # The packet is ACCUMULATED AS ZEROS rather than skipped, so a
                    # silent endpoint keeps the run's block cadence and is reported
                    # as the silence it is (peak 0, no nonzero block) instead of
                    # vanishing from the counters or lying in them.
                    arr = np.zeros(frames.value, dtype=np.float32)
                    self.silent_packets += 1
                else:
                    raw = ctypes.string_at(data, frames.value * block_align)
                    if float_fmt:
                        arr = np.frombuffer(raw, dtype=np.float32)
                    else:
                        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if channels > 1:
                        arr = arr.reshape(-1, channels).mean(axis=1)
                buf.append(np.asarray(arr, dtype=np.float32))
                acc += arr.size
            release(cap, frames.value)
            # Emit EXACTLY block-size frames so downstream chunking is regular.
            while acc >= self.block:
                joined = np.concatenate(buf) if len(buf) > 1 else buf[0]
                head = joined[: self.block]
                rest = joined[self.block :]
                buf = [rest] if rest.size else []
                acc = rest.size
                self.on_block(np.ascontiguousarray(head, dtype=np.float32))

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._client is not None:
            try:
                _vtbl(self._client, 11, HRESULT)(self._client)  # Stop
            except Exception:
                pass
        for ref in (self._capture, self._client, self._dev, self._enum):
            _release(ref)
        self._capture = self._client = self._dev = self._enum = None
        self._release_com()


def loopback_device_spec(role=E_CONSOLE):
    """A device-shaped dict for the worker's candidate list (rung a).

    Returns None when the endpoint cannot be opened, so the ladder simply falls
    through to rung (b) on a machine that has no render endpoint at all.
    """
    try:
        ep = default_render_endpoint(role)
    except Exception:
        return None
    return {
        "name": "WASAPI loopback: %s" % ep.name,
        "index": None,
        "max_input_channels": ep.channels,
        "default_samplerate": ep.rate,
        "hostapi": None,
        "hostapi_name": "Windows WASAPI (loopback)",
        "wasapi_loopback": True,
        "endpoint_id": ep.endpoint_id,
        "rate": ep.rate,
        "channels": ep.channels,
        "bits": ep.bits,
    }
