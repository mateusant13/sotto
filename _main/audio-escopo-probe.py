"""AudioEscopo — WHICH render endpoint does the tap need to look at on this box?

Answers the owner's defect ("youtube a tocar e nada transcrito") with a number,
not a guess. Two facts are measured here:

  1. WHICH endpoint is rendering RIGHT NOW. `IAudioMeterInformation::GetPeakValue`
     on the DEVICE returns the device's current peak -- sampled for a few seconds
     while whoever is playing (the owner's YouTube, or this script's own fixture)
     renders. No stream is opened to read it.
  2. What a WASAPI LOOPBACK of EVERY active render endpoint contains at the same
     time. The worker's rung (a) opens loopback on the DEFAULT endpoint ONLY
     (`WasapiLoopbackTap.__init__` -> `default_render_endpoint()`); this measures
     what every OTHER endpoint would have delivered, under the SAME audio.

The decisive run is `--play <name-substring>`: it plays the fixture to the named
output while ALL loopback captures run, so the table says whether the DEFAULT
endpoint's loopback hears audio that the owner hears through the real speakers.

    pythonw.exe _main/audio-escopo-probe.py --seconds 6
    pythonw.exe _main/audio-escopo-probe.py --seconds 6 --play "Alto-falantes"
    pythonw.exe _main/audio-escopo-probe.py --seconds 6 --play "Realtek"

Read-only w.r.t. the worker: it uses worker/wasapi_loopback.py's own COM plumbing
and constants. It plays sound only when --play is given. Writes JSON + a human log
so it can run hidden under pythonw.exe (no console, no window).
"""
import ctypes
import io
import json
import os
import sys
import threading
import time
from ctypes import wintypes

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "worker"))
import wasapi_loopback as W  # noqa: E402

HRESULT = W.HRESULT
_vtbl = W._vtbl
GUID = W.GUID
IID_IAudioMeterInformation = W._guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
FLAG_SILENT = 0x2

# ── args ──────────────────────────────────────────────────────────────────────
def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

SECONDS = float(_arg("--seconds", "4"))
PLAY = _arg("--play", "")
PLAY_INDEX = _arg("--play-index", "")
OUT_JSON = _arg("--json", os.path.join(HERE, "audio-escopo.json"))
OUT_LOG = _arg("--log", os.path.join(HERE, "audio-escopo.log"))

log_f = io.open(OUT_LOG, "w", encoding="utf-8")


def p(*a):
    line = " ".join(str(x) for x in a)
    log_f.write(line + "\n")
    log_f.flush()


# ── COM ───────────────────────────────────────────────────────────────────────
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
ole32.CoInitializeEx(None, 0)  # MTA; this process owns it for its whole life

E_RENDER = 0
E_CONSOLE = 0
DEVICE_STATE_ACTIVE = 0x1


def _enumerator():
    enum = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(W.CLSID_MMDeviceEnumerator), None,
                                W.CLSCTX_INPROC_SERVER,
                                ctypes.byref(W.IID_IMMDeviceEnumerator), ctypes.byref(enum))
    if hr != 0:
        raise RuntimeError("MMDeviceEnumerator: %s" % W._fmt(hr))
    return enum


def dev_id(dev):
    b = ctypes.c_wchar_p()
    _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(b))
    v = b.value
    if b:
        ole32.CoTaskMemFree(b)
    return v


def friendly(dev):
    store = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(W.IID_IPropertyStore),
                                              W.CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(store)) != 0:
        return None
    var = (ctypes.c_ubyte * 24)()
    pk = W.PROPERTYKEY(W.PKEY_Device_FriendlyName, 14)
    ok = _vtbl(store, 5, HRESULT, ctypes.POINTER(W.PROPERTYKEY), ctypes.POINTER(ctypes.c_ubyte))(
        store, ctypes.byref(pk), var)
    name = None
    if ok == 0 and ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0] == 0x001B:
        name = ctypes.cast(ctypes.cast(var, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.c_wchar_p).value
    W._release(store)
    return name


def meter_peak(dev, seconds=1.5):
    """Sample IAudioMeterInformation::GetPeakValue on the DEVICE. This is the
    device's live peak: >0 means SOMETHING is rendering to it right now."""
    m = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(IID_IAudioMeterInformation),
                                              W.CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(m)) != 0:
        return None
    get_peak = _vtbl(m, 3, HRESULT, ctypes.POINTER(ctypes.c_float))
    best = 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        v = ctypes.c_float(0.0)
        if get_peak(m, ctypes.byref(v)) == 0:
            best = max(best, float(v.value))
        time.sleep(0.05)
    W._release(m)
    return best


class Capture(threading.Thread):
    """A loopback CAPTURE client on one endpoint, same call shape as the worker's
    tap: GetNextPacketSize -> GetBuffer -> (honour the SILENT flag) -> ReleaseBuffer.
    Reports frames and per-lane peaks."""

    def __init__(self, dev):
        super().__init__(daemon=True)
        self.dev = dev
        self.blocks = []          # 100 ms blocks (mono float32)
        self.rate = None
        self.channels = None
        self.format_tag = None
        self.silent_packets = 0
        self.frames = 0
        self.ok = False
        self.err = None
        self._halt = threading.Event()
        self._client = None
        self._capture = None

    def run(self):
        try:
            self._open_and_pump()
        except Exception as exc:  # reported, never hidden
            self.err = "%s: %s" % (type(exc).__name__, exc)

    def _open_and_pump(self):
        activate = _vtbl(self.dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD,
                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        client = ctypes.c_void_p()
        if activate(self.dev, ctypes.byref(W.IID_IAudioClient), W.CLSCTX_INPROC_SERVER,
                    None, ctypes.byref(client)) != 0:
            raise RuntimeError("Activate(IAudioClient) failed")
        self._client = client
        mix = ctypes.POINTER(W.WAVEFORMATEX)()
        if _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(W.WAVEFORMATEX)))(
                client, ctypes.byref(mix)) != 0 or not mix:
            raise RuntimeError("GetMixFormat failed")
        wf = mix.contents
        self.rate = int(wf.nSamplesPerSec)
        self.channels = int(wf.nChannels)
        align = int(wf.nBlockAlign)
        tag = wf.wFormatTag
        if tag == W.WAVE_FORMAT_EXTENSIBLE and wf.cbSize >= 22:
            sub = ctypes.cast(ctypes.addressof(wf) + 24, ctypes.POINTER(GUID)).contents
            tag = sub.Data1 & 0xFFFF
        self.format_tag = tag
        init = _vtbl(client, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.c_int64,
                     ctypes.c_int64, ctypes.POINTER(W.WAVEFORMATEX), ctypes.c_void_p)
        if init(client, 0, W.AUDCLNT_STREAMFLAGS_LOOPBACK, 0, 0, mix, None) != 0:
            if init(client, 0, W.AUDCLNT_STREAMFLAGS_LOOPBACK, W.HNS_100MS, 0, mix, None) != 0:
                raise RuntimeError("Initialize(LOOPBACK) failed")
        cap = ctypes.c_void_p()
        if _vtbl(client, 14, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
                client, ctypes.byref(W.IID_IAudioCaptureClient), ctypes.byref(cap)) != 0:
            raise RuntimeError("GetService(IAudioCaptureClient) failed")
        self._capture = cap
        if _vtbl(client, 10, HRESULT)(client) != 0:
            raise RuntimeError("IAudioClient::Start failed")
        self.ok = True

        block = int(self.rate * 0.1)
        next_size = _vtbl(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))
        get_buffer = _vtbl(cap, 3, HRESULT, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                           ctypes.POINTER(ctypes.c_int64))
        release = _vtbl(cap, 4, HRESULT, wintypes.DWORD)
        float_fmt = tag == W.WAVE_FORMAT_IEEE_FLOAT
        buf = []
        acc = 0
        while not self._halt.is_set():
            n = wintypes.DWORD(0)
            if next_size(cap, ctypes.byref(n)) != 0:
                break
            if n.value == 0:
                time.sleep(0.002)
                continue
            data = ctypes.POINTER(ctypes.c_ubyte)()
            frames = wintypes.DWORD(0)
            flags = wintypes.DWORD(0)
            pos = ctypes.c_int64(0)
            if get_buffer(cap, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags),
                          ctypes.byref(pos)) != 0:
                break
            if frames.value:
                self.frames += frames.value
                if flags.value & FLAG_SILENT or not data:
                    arr = np.zeros(frames.value, dtype=np.float32)
                    self.silent_packets += 1
                else:
                    raw = ctypes.string_at(data, frames.value * align)
                    if float_fmt:
                        arr = np.frombuffer(raw, dtype=np.float32)
                    else:
                        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if self.channels > 1:
                        arr = arr.reshape(-1, self.channels).mean(axis=1)
                buf.append(np.asarray(arr, dtype=np.float32))
                acc += arr.size
            release(cap, frames.value)
            while acc >= block:
                joined = np.concatenate(buf) if len(buf) > 1 else buf[0]
                head = joined[:block]
                rest = joined[block:]
                buf = [rest] if rest.size else []
                acc = rest.size
                self.blocks.append(np.ascontiguousarray(head, dtype=np.float32))

    def stop(self):
        self._halt.set()
        self.join(timeout=2.0)
        if self._client is not None:
            try:
                _vtbl(self._client, 11, HRESULT)(self._client)
            except Exception:
                pass
        for ref in (self._capture, self._client):
            W._release(ref)


def play_in_thread(target_substr, seconds):
    """Play worker/assets/sample1.flac to the FIRST output device whose name
    contains target_substr, in a background thread. Returns (thread, info-dict)."""
    import sounddevice as sd
    import soundfile as sf

    info = {"target": target_substr, "device": None, "index": None, "rate": None,
            "error": None, "seconds": seconds}
    pcm, sr = sf.read(r"H:\sotto\worker\assets\sample1.flac", dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    idx = None
    apis = sd.query_hostapis()
    _ = apis
    if PLAY_INDEX != "":
        idx = int(PLAY_INDEX)
    else:
        # prefer a WASAPI render device when the name matches several host APIs
        cands = [i for i, d in enumerate(sd.query_devices())
                 if d["max_output_channels"] > 0 and target_substr.lower() in d["name"].lower()]
        wasapi = [i for i in cands if "wasapi" in apis[sd.query_devices()[i]["hostapi"]]["name"].lower()]
        idx = (wasapi or cands or [None])[0]
    if idx is None:
        info["error"] = "no output device matching %r" % target_substr
        return None, info
    info["device"] = sd.query_devices(idx)["name"]
    info["index"] = idx
    info["src_rate"] = sr

    # Render at the DEVICE's own rate (WASAPI shared mode is happiest there) and
    # resample the fixture to it, so the render is the fixture and not a refusal.
    dev_rate = int(sd.query_devices(idx)["default_samplerate"])
    info["rate"] = dev_rate
    if sr != dev_rate:
        n = int(len(pcm) * dev_rate / sr)
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n),
                        np.arange(len(pcm)), pcm).astype(np.float32)

    pos = [0]
    written = [0]
    pcm_ext = np.concatenate([pcm, np.zeros(dev_rate, dtype=np.float32)])

    def cb(outdata, frames, time_info, status):
        need = frames
        out = []
        while need > 0:
            take = min(need, len(pcm_ext) - pos[0])
            out.append(pcm_ext[pos[0]:pos[0] + take])
            pos[0] += take
            need -= take
            if pos[0] >= len(pcm_ext):
                pos[0] = 0
        chunk = np.concatenate(out)
        outdata[:len(chunk), 0] = chunk
        if outdata.shape[1] > 1:
            outdata[:len(chunk), 1] = chunk
        outdata[len(chunk):] = 0
        written[0] += frames

    def run():
        try:
            info["open_ok"] = True
            with sd.OutputStream(device=idx, samplerate=dev_rate, channels=2,
                                 dtype="float32", callback=cb):
                time.sleep(seconds)
        except Exception as exc:
            info["open_ok"] = False
            info["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            info["frames_written"] = written[0]

    t = threading.Thread(target=run, daemon=True)
    return t, info


def summarize(cap):
    peak = rms = 0.0
    nonzero = 0
    for b in cap.blocks:
        m = float(np.abs(b).max()) if b.size else 0.0
        peak = max(peak, m)
        if m > 0.0:
            nonzero += 1
    if cap.blocks:
        x = np.concatenate(cap.blocks).astype("float64")
        rms = float(np.sqrt((x ** 2).mean()))
    return {
        "blocks": len(cap.blocks),
        "nonzero_blocks": nonzero,
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "frames": cap.frames,
        "silent_packets": cap.silent_packets,
        "opened": cap.ok,
        "error": cap.err,
        "rate": cap.rate,
        "channels": cap.channels,
        "format_tag": cap.format_tag,
    }


def main():
    enum = _enumerator()
    dev_default = ctypes.c_void_p()
    _vtbl(enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
        enum, E_RENDER, E_CONSOLE, ctypes.byref(dev_default))
    default_id = dev_id(dev_default)

    coll = ctypes.c_void_p()
    hr = _vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
        enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll))
    count = wintypes.UINT(0)
    _vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))

    endpoints = []
    for i in range(count.value):
        d = ctypes.c_void_p()
        _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(
            coll, i, ctypes.byref(d))
        endpoints.append({
            "index": i,
            "id": dev_id(d),
            "name": friendly(d),
            "is_default": dev_id(d) == default_id,
            "_dev": d,
        })

    p("=== AudioEscopo probe ===")
    p("timestamp:", time.strftime("%Y-%m-%dT%H:%M:%S"))
    p("active render endpoints:", count.value)
    p("DEFAULT (eConsole) render endpoint:", default_id)
    for e in endpoints:
        p("  [%s] %r  %s" % ("DEFAULT" if e["is_default"] else "       ", e["name"], e["id"]))
    p("EnumAudioEndpoints hr=%s" % hr)
    p("play target: %r  seconds=%.1f" % (PLAY, SECONDS))

    # 1) who is rendering RIGHT NOW (meter, no stream)
    p("")
    p("-- IAudioMeterInformation peak over 1.5 s (who is rendering right now) --")
    for e in endpoints:
        e["meter_peak"] = meter_peak(e["_dev"])
        p("  meter peak=%-9s %r" % (("%.6f" % e["meter_peak"]) if e["meter_peak"] is not None
                                    else "n/a", e["name"]))

    # 2) loopback capture on EVERY endpoint, all at once
    p("")
    p("-- WASAPI loopback capture on EVERY active render endpoint (%.1f s) --" % SECONDS)
    caps = {}
    for e in endpoints:
        c = Capture(e["_dev"])
        caps[e["id"]] = c
        c.start()
    time.sleep(0.4)

    play_thread = None
    play_info = None
    if PLAY or PLAY_INDEX != "":
        play_thread, play_info = play_in_thread(PLAY, SECONDS + 1.0)
        p("-- --play: rendering the fixture to %r (index %s) --" % (PLAY, PLAY_INDEX))
        if play_info.get("error"):
            p("   PLAY ERROR:", play_info["error"])
        else:
            p("   PLAY device=%r index=%s" % (play_info["device"], play_info["index"]))
        play_thread.start()
    else:
        p("-- no --play: measuring whatever is rendering now (owner's audio, if any) --")

    t0 = time.time()
    while time.time() - t0 < SECONDS:
        time.sleep(0.2)
    for c in caps.values():
        c.stop()
    if play_thread is not None:
        play_thread.join(timeout=3.0)
        p("   PLAY RESULT:", json.dumps(play_info, ensure_ascii=False))
        if not play_info.get("open_ok"):
            p("   !! PLAYER NEVER OPENED -- this arm is INVALID, not evidence")

    p("")
    p("-- RESULTS --")
    results = []
    for e in endpoints:
        s = summarize(caps[e["id"]])
        row = {
            "index": e["index"], "name": e["name"], "id": e["id"],
            "is_default": e["is_default"], "meter_peak": e["meter_peak"],
        }
        row.update(s)
        results.append(row)
        flag = "DEFAULT" if e["is_default"] else "       "
        if play_info and play_info.get("device") and e["name"] and \
                play_info["device"].lower()[:12] in e["name"].lower():
            flag += " PLAYED"
        p("  [%s] %r" % (flag, e["name"]))
        p("        blocks=%s nonzero_blocks=%s peak=%s rms=%s frames=%s silent_packets=%s opened=%s err=%s"
          % (s["blocks"], s["nonzero_blocks"], s["peak"], s["rms"], s["frames"],
             s["silent_packets"], s["opened"], s["error"]))

    out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": SECONDS,
        "play_target": PLAY,
        "play_index": PLAY_INDEX,
        "play_info": play_info,
        "default_id": default_id,
        "endpoint_count": count.value,
        "endpoints": results,
    }
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    p("")
    p("wrote", OUT_JSON)
    log_f.close()
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
