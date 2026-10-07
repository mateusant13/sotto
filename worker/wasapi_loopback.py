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
# IAudioMeterInformation::GetPeakValue on a DEVICE returns that device's own
# current peak -- the live answer to "which render endpoint is carrying audio
# right now", read without opening any stream (Microsoft Learn, IAudioMeterInformation).
IID_IAudioMeterInformation = _guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

# IMMDeviceEnumerator::EnumAudioEndpoints device state. Only ACTIVE endpoints can
# render, so only they are candidates for a loopback tap (Microsoft Learn,
# IMMDeviceEnumerator + DEVICE_STATE_*).
DEVICE_STATE_ACTIVE = 0x00000001

# IMMDevice::OpenPropertyStore access mode (Microsoft Learn). Pulled out because
# `_friendly_name` reaches the store through it, not through Activate().
STGM_READ = 0x00000000

# PROPVARIANT::vt for an LPWSTR. Measured on this box: the property store hands
# PKEY_Device_FriendlyName back with vt=0x001F
# (`_main/friendly-name-probe.out`). The previous body tested 0x001B, which is no
# PROPVARIANT type at all, so even a store that answered would have been refused.
VT_LPWSTR = 0x001F

# Where the union starts inside a PROPVARIANT: 8 bytes of header (VARTYPE plus
# three reserved words) on every supported ABI -- x86 and x64 both align the
# union on 8 for its ULONGLONG/double members. Reading the LPWSTR at offset 0
# instead returns the header bytes reinterpreted as a pointer (measured: an
# access violation, rc=5, `_main/friendly-name-probe.out`).
PROPVARIANT_UNION_OFFSET = 8

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


# ── one IMMDevice -> one LoopbackEndpoint ────────────────────────────────────
# `default_render_endpoint` and `list_render_endpoints` need the SAME three
# things from an IMMDevice (its friendly name, its endpoint id, its MIX format).
# They are shared here so a SECOND render endpoint cannot be described by a
# second, drifting copy of the mix-format parsing.
def _make_enumerator(ole32):
    """CoCreateInstance the MMDeviceEnumerator, with the argtypes set."""
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
    return enum


def _friendly_name(dev):
    """PKEY_Device_FriendlyName, or None when the device genuinely publishes none.

    THREE measured defects in the previous body, all on this box (2026-10-06,
    `_main/friendly-name-probe.out`); the later two only became observable once
    the first was fixed:

      * it reached the property store through `IMMDevice::Activate(
        IPropertyStore, CLSCTX_INPROC_SERVER, ...)`, which fails with
        E_NOINTERFACE (0x80004002) on ALL SIX active render endpoints. So the
        function returned None for every device and the ladder, the tap ledger
        and the panel named every endpoint by its raw GUID
        ("WASAPI loopback: {0.0.0.00000000}.{55395a4e-...}") instead of
        "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)". The property store is
        reached through `IMMDevice::OpenPropertyStore` (vtable index 4), which
        returns S_OK on the same six (Microsoft Learn, IMMDevice::OpenPropertyStore).
      * it read the LPWSTR out of OFFSET 0 of the PROPVARIANT. On x64 the 8-byte
        header (VARTYPE + three reserved words) is followed by the union at
        offset 8, so offset 0 reinterprets the header bytes as a pointer --
        measured: dereferencing it killed the probe with an access violation
        (rc=5). Offset 8 returns the name, vt=VT_LPWSTR (0x001F).
      * it tested vt against 0x001B, which is no PROPVARIANT type at all, so
        even a store that answered would have been refused. The measured vt of a
        friendly name is VT_LPWSTR = 0x001F.

    A device that really publishes nothing still gets None, and `_mix_spec` keeps
    its honest endpoint-id fallback rather than a fabricated name.
    """
    store = ctypes.c_void_p()
    open_store = _vtbl(dev, 4, HRESULT, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))
    if open_store(dev, STGM_READ, ctypes.byref(store)) != 0 or not store:
        return None
    name = None
    var = (ctypes.c_ubyte * 24)()
    got = False
    try:
        get_value = _vtbl(
            store, 5, HRESULT, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(ctypes.c_ubyte)
        )
        if get_value(store, ctypes.byref(_PKEY_FRIENDLY), var) == 0:
            got = True
            if ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0] == VT_LPWSTR:
                pw = ctypes.cast(
                    ctypes.addressof(var) + PROPVARIANT_UNION_OFFSET,
                    ctypes.POINTER(ctypes.c_void_p),
                )[0]
                if pw:
                    name = ctypes.cast(pw, ctypes.c_wchar_p).value
    finally:
        if got:
            # The store allocated the string; PropVariantClear owns freeing it.
            # Only after a successful GetValue: clearing an uninitialised
            # PROPVARIANT would free a pointer nobody set.
            ole32 = _ole32()
            ole32.PropVariantClear.argtypes = [ctypes.c_void_p]
            ole32.PropVariantClear.restype = HRESULT
            ole32.PropVariantClear(ctypes.byref(var))
        _release(store)
    return name


def _endpoint_id(dev, ole32):
    """The endpoint's own id string (IMMDevice::GetId), or None."""
    buf = ctypes.c_wchar_p()
    if _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(buf)) != 0:
        return None
    val = buf.value
    ole32.CoTaskMemFree(buf)
    return val


def _mix_spec(dev, ole32):
    """LoopbackEndpoint for ONE IMMDevice: name, id and MIX format.

    A loopback stream has no format negotiation, so this format is the one the
    tap MUST initialise with (Microsoft Learn, loopback recording).
    """
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
    try:
        mix = ctypes.POINTER(WAVEFORMATEX)()
        hr = _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))(
            client, ctypes.byref(mix)
        )
        if hr != 0 or not mix:
            raise WasapiError("GetMixFormat failed: %s" % _fmt(hr))
        wf = mix.contents
        tag = wf.wFormatTag
        if tag == WAVE_FORMAT_EXTENSIBLE and wf.cbSize >= 22:
            # offset 18 = wValidBitsPerSample, 20 = dwChannelMask, 24 = SubFormat GUID
            sub = ctypes.cast(ctypes.addressof(wf) + 24, ctypes.POINTER(GUID)).contents
            tag = sub.Data1 & 0xFFFF
        if tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
            raise WasapiError("unsupported mix subformat 0x%04X" % tag)
        endpoint_id = _endpoint_id(dev, ole32)
        return LoopbackEndpoint(
            # Some drivers publish no PKEY_Device_FriendlyName (measured on this
            # box: the property store returns nothing). The endpoint ID still
            # identifies it exactly, and a failure report that says "unnamed"
            # tells the owner nothing he can act on.
            name=_friendly_name(dev) or (endpoint_id or "<unnamed render endpoint>"),
            endpoint_id=endpoint_id,
            rate=int(wf.nSamplesPerSec),
            channels=int(wf.nChannels),
            bits=int(wf.wBitsPerSample),
            format_tag=tag,
            block_align=int(wf.nBlockAlign),
        )
    finally:
        # the client is re-activated inside the tap; release the probe's handle
        _release(client)


def _enumerate_default_render_endpoint(role):
    """The body of `default_render_endpoint`, with COM already started."""
    ole32 = _ole32()
    enum = _make_enumerator(ole32)
    try:
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
            raise WasapiError("no default render endpoint: %s" % _fmt(hr))
        try:
            return _mix_spec(dev, ole32)
        finally:
            _release(dev)
    finally:
        _release(enum)


def _device_by_id(enum, endpoint_id):
    """IMMDeviceEnumerator::GetDevice (vtable index 5) -> IMMDevice."""
    dev = ctypes.c_void_p()
    hr = _vtbl(enum, 5, HRESULT, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p))(
        enum, endpoint_id, ctypes.byref(dev)
    )
    if hr != 0 or not dev:
        raise WasapiError("GetDevice(%s) failed: %s" % (endpoint_id, _fmt(hr)))
    return dev


def _meter_peak(dev, seconds=0.15):
    """IAudioMeterInformation::GetPeakValue on the DEVICE, sampled for `seconds`.

    >0 means this endpoint is rendering RIGHT NOW. No stream is opened to read
    it, so it is safe to ask about every endpoint. None when the meter is
    unavailable (the caller must then not treat "no reading" as "no signal").
    """
    m = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(IID_IAudioMeterInformation),
                                              CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(m)) != 0 or not m:
        return None
    try:
        get_peak = _vtbl(m, 3, HRESULT, ctypes.POINTER(ctypes.c_float))
        best = 0.0
        t0 = time.time()
        while True:
            v = ctypes.c_float(0.0)
            if get_peak(m, ctypes.byref(v)) == 0:
                best = max(best, float(v.value))
            if time.time() - t0 >= seconds:
                break
            time.sleep(0.02)
        return best
    finally:
        _release(m)


def list_render_endpoints(role=E_CONSOLE, meter_ms=0.15):
    """EVERY ACTIVE render endpoint, each with its live meter peak.

    `IMMDeviceEnumerator::EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE)` is
    what defines ACTIVE (Microsoft Learn). The result is ORDERED BY SIGNAL
    (meter_peak descending; the DEFAULT endpoint breaks a tie), because the
    defect this exists to remove is a tap that opens a SILENT endpoint while the
    owner's audio renders on a different one.
    """
    if sys.platform != "win32":
        raise WasapiError("WASAPI loopback is Windows-only")
    com = _com_init()
    try:
        return _list_render_endpoints(role, meter_ms)
    finally:
        if com == COM_REF_TAKEN:
            _com_uninit()


def _list_render_endpoints(role, meter_ms):
    ole32 = _ole32()
    enum = _make_enumerator(ole32)
    out = []
    try:
        default_id = None
        dev_default = ctypes.c_void_p()
        get_default = _vtbl(
            enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
        )
        if get_default(enum, E_RENDER, role, ctypes.byref(dev_default)) == 0 and dev_default:
            default_id = _endpoint_id(dev_default, ole32)
            _release(dev_default)

        coll = ctypes.c_void_p()
        hr = _vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
            enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll)
        )
        if hr != 0 or not coll:
            raise WasapiError("EnumAudioEndpoints(eRender, ACTIVE) failed: %s" % _fmt(hr))
        try:
            count = wintypes.UINT(0)
            _vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
            for i in range(count.value):
                dev = ctypes.c_void_p()
                if _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(
                        coll, i, ctypes.byref(dev)) != 0 or not dev:
                    continue
                try:
                    ep = _mix_spec(dev, ole32)
                    out.append({
                        "endpoint_id": ep.endpoint_id,
                        "name": ep.name,
                        "rate": ep.rate,
                        "channels": ep.channels,
                        "bits": ep.bits,
                        "format_tag": ep.format_tag,
                        "block_align": ep.block_align,
                        "is_default": ep.endpoint_id is not None and ep.endpoint_id == default_id,
                        "meter_peak": _meter_peak(dev, meter_ms),
                    })
                except Exception:
                    # One endpoint that cannot be described must not hide the
                    # others: the ladder still needs the ones that can.
                    pass
                finally:
                    _release(dev)
        finally:
            _release(coll)
    finally:
        _release(enum)
    # ORDER IS THE CONTRACT: whoever is rendering now goes first.
    out.sort(key=lambda e: (-(e["meter_peak"] or 0.0), not e["is_default"]))
    return out


def live_render_peaks(meter_ms=0.12):
    """{endpoint_id: live meter peak} for every ACTIVE render endpoint, read NOW.

    The candidate list is ordered ONCE, when `device_candidates()` runs at
    process start, and that reading is what the ladder then walks. MEASURED on
    this box 2026-10-06: at that moment the owner was not rendering yet, every
    one of the six active render endpoints read `meter_peak=0.000000`, the sort
    could not discriminate, and the `not is_default` tie-break handed the FIRST
    tap window to `VoiceMeeter Input` -- the endpoint this box never renders to
    -- while the audio was on `CABLE Input` (id `{2f1295af-...}`). The ladder
    then burned a whole window before reaching the endpoint that was playing.

    This is the same question asked at the moment the answer matters, and it is
    deliberately cheaper than `list_render_endpoints`: no IAudioClient is
    activated and no mix format is parsed, because only the meter is wanted.
    Cost measured on this box: 6 endpoints at `meter_ms=0.12` = 0.76 s
    (`_main/ordem-dos-candidatos-probe.py`), against the 6.0 s tap window it
    replaces when it changes the choice.

    Returns {} -- never raises, never guesses -- when the platform or the
    enumeration fails; a caller that gets {} must keep the order it already has.
    """
    if sys.platform != "win32":
        return {}
    com = _com_init()
    try:
        ole32 = _ole32()
        enum = _make_enumerator(ole32)
        out = {}
        try:
            coll = ctypes.c_void_p()
            hr = _vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(ctypes.c_void_p))(
                enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll)
            )
            if hr != 0 or not coll:
                return {}
            try:
                count = wintypes.UINT(0)
                _vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
                for i in range(count.value):
                    dev = ctypes.c_void_p()
                    if _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(
                            coll, i, ctypes.byref(dev)) != 0 or not dev:
                        continue
                    try:
                        eid = _endpoint_id(dev, ole32)
                        if eid:
                            out[eid] = _meter_peak(dev, meter_ms)
                    finally:
                        _release(dev)
            finally:
                _release(coll)
        finally:
            _release(enum)
        return out
    except Exception:
        return {}
    finally:
        if com == COM_REF_TAKEN:
            _com_uninit()


def endpoint_spec(endpoint_id):
    """The LoopbackEndpoint for ONE endpoint id, or WasapiError."""
    if sys.platform != "win32":
        raise WasapiError("WASAPI loopback is Windows-only")
    com = _com_init()
    try:
        ole32 = _ole32()
        enum = _make_enumerator(ole32)
        try:
            dev = _device_by_id(enum, endpoint_id)
            try:
                return _mix_spec(dev, ole32)
            finally:
                _release(dev)
        finally:
            _release(enum)
    finally:
        if com == COM_REF_TAKEN:
            _com_uninit()


class WasapiLoopbackTap:
    """Live loopback capture with the same surface as the sounddevice tap.

    Delivers float32 MONO blocks at the endpoint's MIX rate (typically 48 kHz).
    The caller resamples to the model's 16 kHz -- that conversion cannot happen
    on the device, because a loopback stream must use the mix format.

    Contract: `stop()` is idempotent and, when it returns, `on_block` will never
    be called again (the pump thread is joined before returning), but the COM
    interfaces are still open. `close()` = `stop()` + release of every COM
    reference, also idempotent; `close()` alone is enough for a caller that
    never intends to reuse the tap.
    """

    def __init__(self, on_block, block_ms=100, role=E_CONSOLE, endpoint_id=None):
        import numpy as np

        self.np = np
        self.on_block = on_block
        # Held ONLY around the `on_block` call in `_pump`, so `stop()` can prove
        # the guarantee below: set `_stop`, join the pump, then acquire this lock
        # -- whoever gets it afterwards cannot be inside a callback, and the
        # joined thread will not start another one.
        self._cb_lock = threading.Lock()
        self.block_ms = block_ms
        self.role = role
        # WHICH endpoint this tap reads. None keeps the historical behaviour
        # (the DEFAULT render endpoint); an id opens THAT endpoint, which is what
        # lets the ladder settle on the endpoint that is actually RENDERING
        # instead of on a default that may be carrying nothing. MEASURED on this
        # box 2026-10-06: the owner's Chrome rendered to `CABLE Input` while the
        # default was `VoiceMeeter Input`, whose loopback read 0 blocks / peak 0.
        self.endpoint_id = endpoint_id
        self.ep = (default_render_endpoint(role) if endpoint_id is None
                   else endpoint_spec(endpoint_id))
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
        # Packets whose `pu64DevicePosition` did not continue the previous one,
        # i.e. frames the ring dropped instead of handing over. Read-only
        # diagnostic: it consumes the position out-parameter of GetBuffer, which
        # used to be an uninitialised 5th vtable slot (F16).
        self.position_gap_packets = 0

    # -- name surface the worker's reporting uses ----------------------------
    @property
    def name(self):
        return "WASAPI loopback: %s" % self.ep.name

    @property
    def stream(self):
        """The worker closes taps with `t.stream.stop(); t.stream.close()`.

        Returning self keeps that call site working unchanged: `stop()` is the
        real, idempotent stop (no callback after it returns) and `close()` is
        `stop()` plus the release of the COM interfaces.
        """
        return self

    def start(self):
        """The worker opens taps with `tap.stream.start()`; same surface."""
        if self._thread is None:
            self._start()
        return self

    def stop(self):
        """Stop delivering blocks. Idempotent; never releases interfaces.

        GUARANTEE: once this returns, `on_block` is NEVER called again. The
        pump is asked to stop (`_stop`), joined, and the callback lock is taken
        afterwards, so a callback that was already in flight has returned and
        the joined thread cannot start another one. This is the property the
        worker's tap ledger depends on: after `close_tap()` the abandoned
        endpoint must stop adding `blocks`/`block_samples`/`peak` to the run.

        F4 (`docs/audit/auditoria-completa-20261007.md`): the worker calls
        `t.stream.stop()` and this method did not exist, so the AttributeError
        was swallowed by `close_tap()` and `close()` -- the only path that set
        `_stop` -- was unreachable. The abandoned `_pump` kept feeding the run.

        Does NOT touch `_client`/`_capture`/`_dev`/`_enum`: `close()` is the
        releasing path. `IAudioClient::Stop` is called here too, so a caller
        that only stops (and reuses the object later) is not left with a
        capturing client; a failure there never masks the guarantee above.
        """
        self._stop.set()
        if self._thread is not None:
            # The pump sleeps at most `period` (<= 5 ms) per empty poll, so the
            # join is bounded by that, not by the device. The timeout is a safety
            # valve for a wedged COM call: if it fires, `_thread` is KEPT, so
            # `_thread is None` keeps meaning "the pump is gone" and `close()`
            # cannot release the interfaces underneath a live thread.
            self._thread.join(timeout=2.0)
            if not self._thread.is_alive():
                self._thread = None
        if self._client is not None:
            try:
                _vtbl(self._client, 11, HRESULT)(self._client)  # Stop
            except Exception:
                pass
        # Barrier: whoever holds `_cb_lock` is inside `on_block`; taking it here
        # means the callback that was in flight has returned. The pump, already
        # past its `_stop` test, cannot start another one.
        with self._cb_lock:
            pass
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
        enum = _make_enumerator(_ole32())
        self._enum = enum

        if self.endpoint_id:
            # The ladder picked THIS endpoint (it was the one rendering). Opening
            # the default instead would silently substitute the very endpoint
            # whose silence is the defect.
            dev = _device_by_id(enum, self.endpoint_id)
        else:
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
        # FIVE out-parameters. IAudioCaptureClient::GetBuffer is (this,
        # BYTE **ppData, UINT32 *pNumFramesToRead, DWORD *pdwFlags,
        # UINT64 *pu64DevicePosition, UINT64 *pu64QPCPosition); the earlier
        # declaration declared only FOUR, so the callee's 5th slot was
        # uninitialised stack that it may write 8 bytes through. The 5th
        # (`pu64QPCPosition`) is optional in the IDL, so it is passed as NULL
        # (None) -- an explicit null, not a missing argument. The device
        # position IS used: `position_gap_packets` below counts packets whose
        # position does not continue the previous one, i.e. frames the ring
        # dropped or that arrived out of order.
        get_buffer = _vtbl(
            cap,
            3,
            HRESULT,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_uint64),
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
        # The period is OUR poll interval, derived from our own block size --
        # NOT from the device's ring, and not from anything the endpoint
        # reports: our block is 100 ms, which says nothing about how fast the
        # device must be drained, and the previous `block_ms/1000/4` (25 ms)
        # was slower than the measured 22 ms grant. `block_ms/20` = 5 ms at the
        # shipped 100 ms setting, i.e. we poll ~4x faster than the ring fills,
        # which is what keeps duty at 0.999 instead of 0.815.
        period = min(0.005, max(0.001, self.block_ms / 1000.0 / 20.0))
        buf = []
        acc = 0
        prev_pos = None
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
            if get_buffer(cap, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), ctypes.byref(pos), None) != 0:
                break
            if frames.value:
                # `pos` is the device position of this packet's first frame,
                # wrapped to a SIGNED 64-bit carrier for the vtable. A packet
                # that does not continue the previous one means the ring lost
                # frames (or the endpoint rewound): counted, so a gap is a
                # visible number instead of ~0.1 s of audio spliced together.
                # WASAPI may mark a discontinuity with the same flag, but this
                # comparison does not depend on the flag being set.
                if prev_pos is not None and pos.value != prev_pos + frames.value:
                    self.position_gap_packets += 1
                prev_pos = pos.value
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
                # Held for the duration of the deliver only: `stop()` takes this
                # same lock AFTER joining the pump, which is what makes "no
                # `on_block` after `stop()` returns" a property of the object
                # rather than a hope about thread scheduling.
                #
                # AND THE `_stop` TEST IS REPEATED **INSIDE** THE LOCK, because the
                # lock alone is not enough and the adversary lane proved it
                # (`_main/_review-tapstop.py`, 2026-10-07): `_pump` tests `_stop`
                # once at the loop HEAD, so a thread already past that test but
                # wedged BEFORE this lock — exactly the case `stop()`'s bounded
                # `join(timeout=2.0)` exists for — could take the lock after
                # `stop()` returned and deliver ONE more block (measured: +0.70 s
                # after `stop()` returned, join timed out). With `stop()`'s own
                # barrier having come and gone, only a re-test here can close it:
                # if the stop flag is set by the time the lock is ours, this block
                # belongs to nobody and is dropped. The counter the ledger reads
                # stops with the tap, which is the whole point of F4.
                with self._cb_lock:
                    if self._stop.is_set():
                        return
                    self.on_block(np.ascontiguousarray(head, dtype=np.float32))

    def close(self):
        """`stop()` + release every COM reference. Idempotent.

        This is the path that gives the references back: COM init token,
        capture client, audio client, device and enumerator. `stop()` is safe to
        call again afterwards (the second `stop(); close()` pair is a no-op) and
        never touches the interfaces, so the release stays in ONE place.

        The second join is the only case where it is needed: if `stop()` timed
        out on a wedged pump, releasing the interfaces under a LIVE thread would
        be a use-after-free, so close waits (unbounded, once) for the pump to
        leave before releasing -- and after that it is provably gone, which is
        the same invariant `_thread is None` carries.
        """
        self.stop()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
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


def loopback_device_specs(role=E_CONSOLE):
    """Device-shaped dicts for EVERY ACTIVE render endpoint -- the ladder's rung (a).

    ORDERED BY WHO IS RENDERING NOW (live meter peak, descending). This is the
    cure for the measured defect: the previous rung (a) offered ONLY the DEFAULT
    render endpoint, so on this box the tap read `VoiceMeeter Input` (idle, peak
    0) while the owner's Chrome rendered to `CABLE Input` (peak 0.26) -- the app
    reported "no audio to transcribe" with the sound plainly playing.

    Every endpoint is kept, including the default: dropping it would break the
    historical driver-free path, and a silent endpoint costs one bounded tap
    window before the ladder moves on (the rotation loop already does that). An
    empty list means this machine has no usable render endpoint at all, and the
    ladder falls through to rung (b) exactly as before.
    """
    try:
        # 0.4 s per endpoint, not a single instantaneous read: the ordering must
        # ride out a brief digital-zero gap in the owner's audio (the moment
        # between two tracks is not "this endpoint is idle").
        eps = list_render_endpoints(role, meter_ms=0.4)
    except Exception:
        return []
    out = []
    for e in eps:
        peak = e.get("meter_peak")
        if e.get("is_default"):
            why = "WASAPI loopback of the DEFAULT render endpoint"
        else:
            why = "WASAPI loopback of an active render endpoint"
        if peak:
            why += " (rendering now, meter peak %.3f)" % peak
        out.append({
            "name": "WASAPI loopback: %s" % e["name"],
            "index": None,
            "max_input_channels": e["channels"],
            "default_samplerate": e["rate"],
            "hostapi": None,
            "hostapi_name": "Windows WASAPI (loopback)",
            "wasapi_loopback": True,
            "endpoint_id": e["endpoint_id"],
            "rate": e["rate"],
            "channels": e["channels"],
            "bits": e["bits"],
            "meter_peak": peak,
            "rung_why": why,
        })
    return out
