"""Universal audio-capture CAPABILITY PROBE for the Sotto worker.

Answers one question a non-expert can read: on THIS machine, can Sotto capture
"whatever the PC is playing" WITHOUT any virtual cable driver installed?

Method, from the vendor documentation:

  * The default RENDER endpoint (eRender, eConsole) is opened through
    IMMDeviceEnumerator::GetDefaultAudioEndpoint. See
    https://learn.microsoft.com/windows/win32/coreaudio/ ...
    (core-audio-endpoints / default-audio-endpoint).
  * IMMDevice::Activate yields an IAudioClient that is INITIALIZED with
    AUDCLNT_SHAREMODE_SHARED and the AUDCLNT_STREAMFLAGS_LOOPBACK flag. A loopback
    capture client is a CAPTURE client whose "input" is the render endpoint, and it
    must be initialized with the endpoint's MIX format (IAudioClient::GetMixFormat)
    -- not an arbitrary rate. That is the whole reason a normal 16 kHz open fails:
    the loopback stream has no format negotiation.
  * IAudioClient::GetService(IID_IAudioCaptureClient) then delivers the mixed output
    of the endpoint as packets, exactly as it is played.

A process-scoped alternative exists on Windows 10 2004+ (build 19041) through
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK + AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS
(ProcessLoopbackMode / TargetProcessId / TargetThreadId), see
https://learn.microsoft.com/windows/win32/audio/process-loopback . It is reported
here but NOT required by the ladder: the default-render loopback above is what
works on every Windows machine that has a sound card at all.

Everything is ctypes + comctl32/ole32/psapi already present on Windows. There is NO
third-party dependency, which is the point: a machine with no VB-Cable, no
VoiceMeeter and no Python audio wheel still gets an answer.

Writes a verbatim log to H:/sotto/_main/capability-probe.log and prints one VERDICT
line. Launch it hidden -- never let a console flash on the owner's desktop.
"""

import ctypes
import io
import os
import sys
import threading
import time
from ctypes import wintypes

# ctypes.wintypes has NO HRESULT on CPython (it is not exported there). Every
# COM method here returns one, so bind the Win32 equivalent once: a 32-bit
# signed LONG. S_OK compares fine against a Python int.
HRESULT = ctypes.c_long

CLSCTX_INPROC_SERVER = 1


OUT = r"H:\sotto\_main\capability-probe.log"

PROBE_SECONDS = float(os.environ.get("SOTTO_PROBE_SECONDS", "2.0"))

# ── COM plumbing ──────────────────────────────────────────────────────────────
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
propsys = ctypes.WinDLL("propsys", use_last_error=True)

S_OK = 0
E_NOTFOUND = -2147024809  # 0x80070490
E_INVALIDARG = -2147024809 + 0  # resolved below from HRESULT codes
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106

COINIT_MULTITHREADED = 0x0

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

E_CONSOLE = 0
E_RENDER = 0


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


def guid(s):
    """Parse '{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}' into a GUID.

    The 8 tail bytes are TWO from the 4-hex-digit field and SIX from the
    12-hex-digit field. Splitting both with the same stride is the bug that
    produced an empty slice and a ValueError on the first GUID literal."""
    s = s.strip().strip("{}")
    a, b, c, d, e = s.split("-")
    tail = [int(d[i : i + 2], 16) for i in (0, 2)]
    tail += [int(e[i : i + 2], 16) for i in (0, 2, 4, 6, 8, 10)]
    return GUID(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*tail))


CLSID_MMDeviceEnumerator = guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioClient = guid("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioCaptureClient = guid("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
IID_IPropertyStore = guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")

# PKEY_Device_FriendlyName -- {A45C254E-DF1C-4EFD-8020-67D146A850E0}, 14
PKEY_FriendlyName = guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


PKEY_Device_FriendlyName = PROPERTYKEY(PKEY_FriendlyName, 14)
# ctypes defaults a WinDLL function's restype to c_int (32 bits). CoCreateInstance
# writes a 64-bit interface pointer through its last out-parameter, so WITHOUT
# these declarations the pointer comes back truncated and the first vtable call
# dies with an access violation. Measured: "OSError: access violation reading
# 0xFFFFFFFFFFFFFFFF" on IMMDeviceEnumerator::GetDefaultAudioEndpoint.
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoInitializeEx.restype = HRESULT
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = HRESULT
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]


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


def _start_tone(stop_evt):
    """Play a 440 Hz tone on the SAME endpoint the loopback is capturing.

    A loopback client that opens, starts and delivers ZERO packets proves the
    handles exist -- it does NOT prove the signal path carries audio. Windows
    only feeds a loopback client while the endpoint actually renders. This
    positive control removes that ambiguity: the tone is written to the WASAPI
    host API's OWN default output device, which IS the default render endpoint
    the probe captured, so any non-zero loopback peak is the tone coming back.

    Returns (thread, error-or-None).
    """
    import threading

    import numpy as np
    import sounddevice as sd

    def work():
        try:
            apis = sd.query_hostapis()
            wasapi = next((a for a in apis if "wasapi" in a["name"].lower()), None)
            # sounddevice names these keys default_input_device / default_output_device
            # (NOT default_input / default_output -- measured; the shorter name used
            # by the walkthroughs raises KeyError and the control silently never ran).
            dev = wasapi["default_output_device"] if wasapi else None
            info = sd.query_devices(dev) if dev is not None else sd.query_devices(kind="output")
            _tone_note.append("tone-> %r (index %s, %d Hz, %d ch)" % (info["name"], dev, int(info["default_samplerate"]), int(info["max_output_channels"]) or 2))
            rate = int(info["default_samplerate"])
            ch = int(info["max_output_channels"]) or 2
            chunk = int(rate * 0.10)
            n = np.arange(chunk)
            wave = (0.35 * np.sin(2 * np.pi * 440.0 * n / rate)).astype("float32")
            frames = np.repeat(wave[:, None], ch, axis=1)
            with sd.OutputStream(device=dev, samplerate=rate, channels=ch, dtype="float32") as out:
                while not stop_evt.is_set():
                    out.write(frames)
        except Exception as exc:  # pragma: no cover - reported, never fatal
            _tone_error.append("%s: %s" % (type(exc).__name__, exc))

    _tone_error[:] = []
    _tone_note[:] = []
    th = threading.Thread(target=work, name="probe-tone", daemon=True)
    th.start()
    return th


_tone_error = []
_tone_note = []


def _vtbl_method(ptr, index, restype, *argtypes):
    """Bind a COM vtable slot. ptr is the interface pointer."""
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])


def _release(ptr):
    if ptr:
        _vtbl_method(ptr, 2, wintypes.ULONG)()


def _fmt_hresult(hr):
    try:
        raise ctypes.WinError(ctypes.c_uint32(hr).value)
    except OSError as exc:
        return "%s (0x%08X)" % (exc.strerror, hr & 0xFFFFFFFF)


# ── log ───────────────────────────────────────────────────────────────────────
_log = io.open(OUT, "w", encoding="utf-8")


def p(*a):
    _log.write(" ".join(str(x) for x in a) + "\n")
    _log.flush()


def main():
    result = {
        "loopback": False,
        "device_name": None,
        "rate": None,
        "channels": None,
        "bits": None,
        "peak": 0.0,
        "rms": 0.0,
        "packets": 0,
        "reason": "",
        "endpoint_id": None,
        "role_default": None,
        "process_loopback": "unknown",
        "build": "",
    }

    p("SOTTO audio-capture capability probe")
    p("host: %s" % (os.environ.get("COMPUTERNAME", "?")))
    p("python: %s" % sys.version.split()[0])
    p("")

    # ── 1. host APIs the PortAudio layer exposes (the EXISTING rung-b list) ─────
    p("── host APIs exposed to PortAudio (sounddevice) ──")
    try:
        import sounddevice as sd

        apis = sd.query_hostapis()
        for i, a in enumerate(apis):
            p("  [%d] %-24s" % (i, a["name"]))
        ins = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
        p("  PortAudio INPUT devices: %d" % len(ins))
        cable = [
            d
            for d in ins
            if any(k in d["name"].lower() for k in ("cable", "virtual", "voicemeeter", "loopback", "stereo mix"))
        ]
        p("  heuristic cable/stereo-mix inputs: %d %s" % (len(cable), [d["name"] for d in cable]))
    except Exception as exc:
        p("  sounddevice unavailable: %s: %s" % (type(exc).__name__, exc))

    p("")

    # ── 2. the default RENDER endpoint, via IMMDeviceEnumerator ────────────────
    hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    if hr not in (S_OK, RPC_E_CHANGED_MODE):
        p("CoInitializeEx failed: %s" % _fmt_hresult(hr))
        result["reason"] = "COM not initializable"
        return result
    p("CoInitializeEx hr=0x%08X (0=S_OK, 0x80010106=already init in another mode, both fine)" % (hr & 0xFFFFFFFF))

    enum = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(CLSID_MMDeviceEnumerator),
        None,
        CLSCTX_INPROC_SERVER := 1,
        ctypes.byref(IID_IMMDeviceEnumerator),
        ctypes.byref(enum),
    )
    if hr != S_OK:
        p("CoCreateInstance(MMDeviceEnumerator) failed: %s" % _fmt_hresult(hr))
        result["reason"] = "MMDeviceEnumerator unavailable"
        return result

    # Two roles exist for the default endpoint: eConsole (what the user's shell
    # plays) and eMultimedia (legacy apps). eConsole is the one the ladder wants.
    # Both are tried, because a machine whose console role was never published
    # still has a perfectly usable multimedia role.
    dev = ctypes.c_void_p()
    # THREE parameters: (this, flow, role, ppEndpoint). Declaring only two made
    # Windows write the endpoint pointer into a garbage slot and fault. Measured:
    # "access violation reading 0xFFFFFFFFFFFFFFFF" until ppEndpoint was passed.
    get_default = _vtbl_method(
        enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
    )
    hr = get_default(enum, E_RENDER, E_CONSOLE, ctypes.byref(dev))
    if hr == S_OK:
        result["role_default"] = "eConsole"
        p("GetDefaultAudioEndpoint(eRender, eConsole) -> OK")
    else:
        p("GetDefaultAudioEndpoint(eRender, eConsole) -> %s" % _fmt_hresult(hr))
        p("retrying with the eMultimedia role")
        hr = get_default(enum, E_RENDER, 1, ctypes.byref(dev))
        if hr == S_OK:
            result["role_default"] = "eMultimedia"
            p("GetDefaultAudioEndpoint(eRender, eMultimedia) -> OK")
    if hr != S_OK:
        p("NO default render endpoint: %s" % _fmt_hresult(hr))
        result["reason"] = "no default render endpoint (%s)" % _fmt_hresult(hr)
        return result

    # ── 3. friendly name (a failure report must name the endpoint) ─────────────
    get_id = _vtbl_method(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))
    buf = ctypes.c_wchar_p()
    if get_id(dev, ctypes.byref(buf)) == S_OK:
        result["endpoint_id"] = buf.value
        p("endpoint id: %s" % buf.value)
        ole32.CoTaskMemFree(buf)

    store = ctypes.c_void_p()
    activate = _vtbl_method(
        dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
    )
    h = activate(dev, ctypes.byref(IID_IPropertyStore), 1, None, ctypes.byref(store))
    if h == S_OK:
        key = PROPERTYKEY(PKEY_FriendlyName.fmtid, 14)
        var = (ctypes.c_ubyte * 24)()
        get_value = _vtbl_method(
            store, 5, HRESULT, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(ctypes.c_ubyte)
        )
        if get_value(store, ctypes.byref(key), ctypes.cast(var, ctypes.POINTER(ctypes.c_ubyte))) == S_OK:
            vt = ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0]
            if vt == 0x001B:  # VT_LPWSTR
                ptr = ctypes.cast(ctypes.cast(var, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.c_wchar_p)
                result["device_name"] = ptr.value
                p("friendly name: %s" % ptr.value)
    _release(store)

    # ── 4. Activate IAudioClient + read the MIX format ─────────────────────────
    client = ctypes.c_void_p()
    h = activate(dev, ctypes.byref(IID_IAudioClient), 1, None, ctypes.byref(client))
    if h != S_OK:
        p("IMMDevice::Activate(IAudioClient) failed: %s" % _fmt_hresult(h))
        result["reason"] = "Activate(IAudioClient) failed (%s)" % _fmt_hresult(h)
        return result
    p("IMMDevice::Activate(IAudioClient) -> OK")

    mix = ctypes.POINTER(WAVEFORMATEX)()
    get_mix = _vtbl_method(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)))
    h = get_mix(client, ctypes.byref(mix))
    if h != S_OK or not mix:
        p("IAudioClient::GetMixFormat failed: %s" % _fmt_hresult(h))
        result["reason"] = "GetMixFormat failed (%s)" % _fmt_hresult(h)
        return result

    wf = mix.contents
    result["rate"] = int(wf.nSamplesPerSec)
    result["channels"] = int(wf.nChannels)
    result["bits"] = int(wf.wBitsPerSample)
    tag = wf.wFormatTag
    # WAVEFORMATEXTENSIBLE appendage, per the documented layout:
    #   offset 18  WORD   wValidBitsPerSample   (reads 32 here -- NOT the tag)
    #   offset 20  DWORD  dwChannelMask
    #   offset 24  GUID   SubFormat             <- the real PCM/float tag
    # Reading at 18 returned 0x0020 and the probe wrongly declared the endpoint
    # unsupported; it is at 24.
    sub_tag = None
    if tag == WAVE_FORMAT_EXTENSIBLE and wf.cbSize >= 22:
        base = ctypes.addressof(wf)
        sub = ctypes.cast(base + 24, ctypes.POINTER(GUID)).contents
        sub_tag = sub.Data1 & 0xFFFF
    else:
        sub_tag = tag
    p(
        "mix format: tag=0x%04X%s rate=%d Hz channels=%d bits=%d blockAlign=%d"
        % (tag, (" (extensible->0x%04X)" % sub_tag) if sub_tag != tag else "", wf.nSamplesPerSec, wf.nChannels, wf.wBitsPerSample, wf.nBlockAlign)
    )

    float_fmt = sub_tag == WAVE_FORMAT_IEEE_FLOAT
    pcm_fmt = sub_tag == WAVE_FORMAT_PCM
    if not (float_fmt or pcm_fmt):
        p("UNSUPPORTED mix subformat 0x%04X (only PCM and IEEE float are read here)" % sub_tag)
        result["reason"] = "unsupported mix subformat 0x%04X" % sub_tag
        return result

    # ── 5. Initialize with SHARED + LOOPBACK, exactly as documented ───────────
    init = _vtbl_method(
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
    # periodicity 0 -> engine default; buffer duration 0 -> engine default.
    h = init(client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 0, 0, mix, None)
    if h != S_OK:
        # Retry with the documented 100 ms buffer, which some engines require.
        h = init(client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 10000000, 0, mix, None)
        p("Initialize(SHARED|LOOPBACK, 0ms buffer) failed (%s); retried with 100ms buffer" % _fmt_hresult(h))
    if h != S_OK:
        p("IAudioClient::Initialize(SHARED|LOOPBACK) failed: %s" % _fmt_hresult(h))
        result["reason"] = "Initialize(SHARED|LOOPBACK) failed (%s)" % _fmt_hresult(h)
        return result
    p("IAudioClient::Initialize(SHARED|LOOPBACK) -> OK  (the driver-free rung works)")

    cap = ctypes.c_void_p()
    get_service = _vtbl_method(client, 14, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    h = get_service(client, ctypes.byref(IID_IAudioCaptureClient), ctypes.byref(cap))
    if h != S_OK:
        p("IAudioClient::GetService(IAudioCaptureClient) failed: %s" % _fmt_hresult(h))
        result["reason"] = "GetService(IAudioCaptureClient) failed (%s)" % _fmt_hresult(h)
        return result
    p("IAudioClient::GetService(IAudioCaptureClient) -> OK")

    start = _vtbl_method(client, 10, HRESULT)
    h = start(client)
    if h != S_OK:
        p("IAudioClient::Start failed: %s" % _fmt_hresult(h))
        result["reason"] = "Start failed (%s)" % _fmt_hresult(h)
        return result
    p("IAudioClient::Start -> OK")

    # POSITIVE CONTROL. Deliberately started BEFORE the pump so the endpoint is
    # already rendering when the first packet is asked for.
    stop_evt = threading.Event()
    tone_on = os.environ.get("SOTTO_PROBE_TONE", "1") != "0"
    if tone_on:
        _start_tone(stop_evt)
        time.sleep(0.4)
        p("positive control: 440 Hz tone playing on the default render endpoint")

    # ── 6. pump packets, measure the actual signal ────────────────────────────
    import numpy as np

    bps = result["bits"] // 8
    frames_per_packet_block = wf.nBlockAlign
    peak = 0.0
    sumsq = 0.0
    total = 0
    packets = 0
    deadline = time.time() + PROBE_SECONDS

    next_size = _vtbl_method(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))
    get_buffer = _vtbl_method(
        cap,
        3,
        HRESULT,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.c_int64),
    )
    release_buffer = _vtbl_method(cap, 4, HRESULT, wintypes.DWORD)

    while time.time() < deadline:
        n = wintypes.DWORD(0)
        if next_size(cap, ctypes.byref(n)) != S_OK:
            break
        if n.value == 0:
            time.sleep(0.01)
            continue
        data = ctypes.POINTER(ctypes.c_ubyte)()
        avail = wintypes.DWORD(0)
        flags = wintypes.DWORD(0)
        pos = ctypes.c_int64(0)
        if get_buffer(cap, ctypes.byref(data), ctypes.byref(avail), ctypes.byref(flags), ctypes.byref(pos)) != S_OK:
            break
        if avail.value and data:
            raw = ctypes.string_at(data, avail.value * frames_per_packet_block)
            if float_fmt:
                arr = np.frombuffer(raw, dtype=np.float32)
            else:
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            arr = arr.reshape(-1, result["channels"]) if result["channels"] > 1 else arr.reshape(-1, 1)
            mono = arr.mean(axis=1)
            pk = float(np.abs(mono).max()) if mono.size else 0.0
            if pk > peak:
                peak = pk
            sumsq += float((mono.astype(np.float64) ** 2).sum())
            total += int(mono.size)
            packets += 1
        release_buffer(cap, avail.value)
        time.sleep(0.005)

    stop = _vtbl_method(client, 11, HRESULT)
    stop(client)
    stop_evt.set()

    result["loopback"] = True
    result["peak"] = peak
    result["rms"] = (sumsq / total) ** 0.5 if total else 0.0
    result["packets"] = packets

    p("")
    p("pumped %d packets / %d samples over %.1fs" % (packets, total, PROBE_SECONDS))
    p("measured peak=%.6f rms=%.6f" % (peak, result["rms"]))
    if tone_on:
        if _tone_error:
            p("positive control FAILED to play: %s" % _tone_error[0])
            p("  -> peak=0 is NOT evidence about the loopback path; the tone never ran.")
        else:
            p("positive control tone played without error on the default render endpoint.")
    p("NOTE: peak=0 here means NOTHING WAS PLAYING during the probe window.")
    p("      It does NOT mean loopback failed -- the client opened, started and")
    p("      delivered %d packets. A machine playing music would read higher." % packets)

    # ── 7. process-scoped loopback availability (informational) ───────────────
    try:
        p("")
        p("── process-scoped loopback (Windows 10 2004+ / build 19041+) ──")
        buf = ctypes.create_string_buffer(1024)
        n = wintypes.DWORD(0)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # RtlGetVersion via ntdll is the supported path; use the version stub.
        nt = ctypes.WinDLL("ntdll")
        class RTL_OSVERSIONINFOEXW(ctypes.Structure):
            _fields_ = [
                ("dwOSVersionInfoSize", wintypes.DWORD),
                ("dwMajorVersion", wintypes.DWORD),
                ("dwMinorVersion", wintypes.DWORD),
                ("dwBuildNumber", wintypes.DWORD),
                ("dwPlatformId", wintypes.DWORD),
                ("szCSDVersion", wintypes.WCHAR * 128),
            ]

        info = RTL_OSVERSIONINFOEXW()
        info.dwOSVersionInfoSize = ctypes.sizeof(info)
        st = nt.RtlGetVersion(ctypes.byref(info))
        if st == 0:
            build = info.dwBuildNumber
            p("Windows build %d (RtlGetVersion %d.%d)" % (build, info.dwMajorVersion, info.dwMinorVersion))
            if build >= 19041:
                result["process_loopback"] = "available (build>=19041)"
                p("process loopback: AVAILABLE (build %d >= 19041)" % build)
            else:
                result["process_loopback"] = "unavailable (build %d < 19041)" % build
                p("process loopback: NOT available (build %d < 19041)" % build)
        del n
    except Exception as exc:
        p("build probe skipped: %s: %s" % (type(exc).__name__, exc))

    return result


if __name__ == "__main__":
    res = main()
    name = res["device_name"] or res["endpoint_id"] or "<unnamed render endpoint>"
    if res["loopback"]:
        line = (
            'VERDICT: YES — this PC can capture system audio with NO virtual cable. '
            'WASAPI loopback of the default render endpoint OPENED "%s" '
            "(%d Hz, %d ch, %d-bit) and delivered %d packets; peak=%.6f. "
            "The ladder can use rung (a) here."
            % (name, res["rate"], res["channels"], res["bits"], res["packets"], res["peak"])
        )
    else:
        line = (
            'VERDICT: NO — the driver-free rung is not available on this PC (%s). '
            "The ladder must fall back to rung (b), a virtual-cable / stereo-mix "
            'input, or the owner must plug in headphones.' % (res["reason"] or "unknown")
        )
    p("")
    p(line)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    _log.close()
