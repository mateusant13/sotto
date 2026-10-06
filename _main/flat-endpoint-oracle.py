"""RED/GREEN control for "the endpoint comes out FLAT" in worker/wasapi_loopback.py.

TWO defects, ONE class: the tap is allowed to report signal that is not there, and
the ladder then either dies or lies. Both are asserted here against the vendor
contract, not against the code's assumption.

DEFECT 1 -- the COM init gate (wasapi_loopback.py:187-189, pre-fix)
    CoInitializeEx returns S_FALSE (1) when COM is ALREADY running on this thread in
    the SAME apartment. That is a SUCCESS code ("the COM library is already
    initialized on this thread") and, per the same page, "each successful call ...
    including any call that returns S_FALSE, must be balanced by a corresponding
    call to CoUninitialize". The pre-fix gate was

        if hr not in (0, RPC_E_CHANGED_MODE):
            raise WasapiError("CoInitializeEx failed: %s" % _fmt(hr))

    so it refused 1 and never released a reference. The ladder calls
    default_render_endpoint() TWICE in one process on one thread before a stream
    exists (device_candidates() -> loopback_device_spec(), then
    WasapiLoopbackTap.__init__) and the reference from the first call is never
    given back, so the second call returns S_FALSE and rung (a) -- WASAPI loopback
    of the default render endpoint, the only rung that needs no virtual cable --
    can never open. The ladder then spends its window on PortAudio pseudodevices
    that carry digital silence and exits. Measured, verbatim, in
    _main/_live_owner3.log:61:
        BRIDGE_EXIT pid=13752 rc=1 ... nonzero_blocks=0 peak=0.000092
    Microsoft Learn, CoInitializeEx return value / Remarks:
      https://learn.microsoft.com/windows/win32/api/combaseapi/nf-combaseapi-coinitializeex
      https://learn.microsoft.com/windows/win32/api/combaseapi/nf-combaseapi-couninitialize

DEFECT 2 -- GetBuffer's flags byte (wasapi_loopback.py:487-500, pre-fix)
    IAudioCaptureClient::GetBuffer returns a flags DWORD; AUDCLNT_BUFFERFLAGS_SILENT
    (0x2) means "this packet is silence and the buffer contents are NOT valid
    samples". The pre-fix pump read the flags into a local and dropped it, then
    decoded the packet anyway, so the undefined bytes of a silent packet were
    counted as audio: a non-rendering endpoint reports peak ~1e-4 and
    nonzero_blocks > 0 instead of 0.
    Microsoft Learn, IAudioCaptureClient::GetBuffer (flags parameter):
      https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-getbuffer

HOW EACH ARM IS DRIVEN
  * Arms 1-4 REPLACE the module's `_ole32()` with a scripted stub whose
    CoInitializeEx returns one chosen HRESULT and whose CoCreateInstance raises a
    sentinel, so the enumeration path stops at the stub by construction and no
    endpoint is touched. The stub counts CoInitializeEx / CoUninitialize, which is
    how the balance assertion is made.
  * Arms 5-6 use the REAL ole32: two CoInitializeEx in one thread, and an STA->MTA
    mismatch. Arm 5 wraps `_ole32()` with a counting proxy that delegates to the
    real DLL, so the REAL API is what runs and is what is counted. Arm 6 asserts
    against the value the real API returns (printed), not against a constant.
    Neither arm opens a stream.
  * Arms 7-8 run the REAL `_pump()` against a scripted COM vtable: a block of
    memory whose first slot points at an array of stdcall function pointers, which
    is exactly what `_vtbl()` dereferences. The packet payload is 0x38C00000
    float32 repeated, i.e. **9.155e-05** per sample -- the measured dead-endpoint
    peak (`peak=0.000092`), so arm 7 is tied to the number in the evidence and not
    to an invented one. No device, no stream: the pump is handed packets directly.
  * Arm 8 is the CONTROL for arm 7: the SAME bytes with the SILENT bit clear must
    be DELIVERED. Without it, "zero everything" would pass arm 7.
  * Arm 4 is the CONTROL for arms 1-3: a genuine failure HRESULT must still be
    refused, so "never raise" cannot pass the gate arms.

Run:  py -3 _main/flat-endpoint-oracle.py               # both subjects, one command
      py -3 _main/flat-endpoint-oracle.py --with-tap    # adds the live rung-(a)
                                                        # open (opens a real
                                                        # loopback stream ~0.3 s)
Exit code 0 only when the LIVE file is GREEN on every arm AND the frozen pre-fix
copy is RED on at least one -- a green you cannot turn red is not green.
"""

import ctypes
import hashlib
import importlib.util
import os
import sys
import threading
from ctypes import POINTER, wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIVE = os.path.join(ROOT, "worker", "wasapi_loopback.py")
MUTANT = os.path.join(HERE, "_flat-endpoint-mutant-wasapi_loopback.py")
# The pre-fix source this oracle was built against. If the frozen copy stops
# matching, the RED arm would be testing the wrong subject and the pair would be
# worthless, so the run is REFUSED instead.
MUTANT_SHA256 = "2A2F8021D1E92FEF2CA20E6BCF8B6167B452965D7752C88598ACFE6A454A753F"

COINIT_MULTITHREADED = 0x0
COINIT_APARTMENTTHREADED = 0x2
S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106
E_UNEXPECTED = -2147467259        # 0x8000FFFF, a documented hard failure
E_FAIL_FOR_PUMP = -2147467259

AUDCLNT_BUFFERFLAGS_SILENT = 0x2

# 0x38C00000 as little-endian bytes = float32 1.5 * 2**-14 = 9.155e-05, the
# measured peak of a DEAD endpoint (`peak=0.000092`). Used as the *garbage* that
# a SILENT-flagged packet carries, so arm 7 proves the code was counting exactly
# the magnitude the evidence reports.
GARBAGE = b"\x00\x00\xc0\x38"
GARBAGE_PEAK = 9.1552734375e-05


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def load(path, name):
    """Import a module from an explicit path so the mutant is never shadowed by
    the copy already in sys.modules."""
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def real_ole32():
    return ctypes.WinDLL("ole32", use_last_error=True)


# ── arms 1-4: the init gate, against a scripted ole32 ────────────────────────
class StopHere(Exception):
    """Sentinel: the init gate passed and execution reached the device path."""


class _Fn(object):
    """The module assigns `.argtypes`/`.restype` on the DLL functions it calls, so
    the stub's attributes must carry them too."""

    def __init__(self, fn):
        self._fn = fn
        self.argtypes = None
        self.restype = None

    def __call__(self, *a):
        return self._fn(*a)


class StubOle32(object):
    def __init__(self, init_hr):
        self._hr = init_hr
        self.init_calls = 0
        self.uninit_calls = 0
        self.device_calls = 0
        self.CoInitializeEx = _Fn(self._co_init_ex)
        self.CoUninitialize = _Fn(self._uninit)
        self.CoCreateInstance = _Fn(self._co_create)
        self.CoTaskMemFree = _Fn(lambda p: None)

    def _co_init_ex(self, *a):
        self.init_calls += 1
        return self._hr

    def _uninit(self):
        self.uninit_calls += 1
        return 0

    def _co_create(self, *a):
        self.device_calls += 1
        raise StopHere("stub: reached CoCreateInstance")


def gate_arm(name, mod, init_hr, expect):
    """expect: 'proceed'        -> gate passes, a reference was taken and released;
               'proceed-no-ref' -> gate passes, NOTHING was taken, so NOTHING may
                                   be released (this is RPC_E_CHANGED_MODE: COM is
                                   initialised in another apartment. Calling
                                   CoUninitialize here would release somebody
                                   else's reference);
               'raise'          -> WasapiError must come out of the gate itself."""
    stub = StubOle32(init_hr)
    orig = mod._ole32
    mod._ole32 = lambda: stub
    got, detail = "NO-RAISE", ""
    try:
        mod.default_render_endpoint()
    except StopHere:
        got = "proceed"
    except mod.WasapiError as exc:
        got, detail = "raise", str(exc)[:100]
    except BaseException as exc:  # a crash is not a verdict
        got, detail = "CRASH", "%s: %s" % (type(exc).__name__, exc)
    finally:
        mod._ole32 = orig
    took_ref = init_hr in (S_OK, S_FALSE)
    if expect == "proceed":
        # StopHere unwound out of the function, so the cleanup path had to run
        balance_ok = took_ref and stub.uninit_calls == 1
    elif expect == "proceed-no-ref":
        balance_ok = (not took_ref) and stub.uninit_calls == 0
    else:
        balance_ok = stub.uninit_calls == 0
    device_ok = stub.device_calls == (0 if expect == "raise" else 1)
    ok = (got == "proceed" if expect.startswith("proceed") else got == "raise") \
        and balance_ok and device_ok
    print(
        "  %-30s hr=0x%08X expect=%-15s got=%-8s %s  refs{init=%d uninit=%d "
        "device=%d}%s"
        % (name, init_hr & 0xFFFFFFFF, expect, got, "OK" if ok else "RED",
           stub.init_calls, stub.uninit_calls, stub.device_calls,
           "" if not detail else "  -- " + detail)
    )
    return {"arm": name, "ok": ok, "got": got, "detail": detail}


def gate_arms(mod):
    return [
        gate_arm("s-false-is-success", mod, S_FALSE, "proceed"),
        gate_arm("s-ok-is-success-and-balanced", mod, S_OK, "proceed"),
        # RPC_E_CHANGED_MODE: COM is already running here in another apartment.
        # The call "fails" and takes no reference, but COM IS initialised -- and
        # MEASURED on this box that is the state the WORKER's ladder thread is in
        # (sounddevice/PortAudio gets there first: _main/flat-endpoint-BEFORE.out,
        # 601 blocks / peak 0.465224 / 59 captions THROUGH rung (a)). Treating this
        # as fatal would delete rung (a) on exactly such a host.
        gate_arm("changed-mode-usable-no-ref", mod, RPC_E_CHANGED_MODE, "proceed-no-ref"),
        gate_arm("genuine-failure-refused", mod, E_UNEXPECTED, "raise"),
    ]


# ── arm 5: the REAL API, two calls in one thread ─────────────────────────────
class CountingOle32(object):
    """Delegates every call to the REAL ole32 and counts the two bookkeeping
    entry points. Nothing is stubbed: the DLL that runs is the DLL that ships."""

    def __init__(self):
        self._real = real_ole32()
        self.inits = 0
        self.uninits = 0

    def CoInitializeEx(self, *a):
        self.inits += 1
        return self._real.CoInitializeEx(*a)

    def CoUninitialize(self):
        self.uninits += 1
        return self._real.CoUninitialize()

    def __getattr__(self, k):
        return getattr(self._real, k)


def arm_real_two_calls(mod):
    """The ladder's exact sequence, on the REAL API: two
    default_render_endpoint() calls on one thread must BOTH return an endpoint,
    and every reference taken must be given back."""
    box = {}

    def run():
        counter = CountingOle32()
        orig = mod._ole32
        mod._ole32 = lambda: counter
        try:
            first = mod.default_render_endpoint()
            box["first"] = ("rate=%d ch=%d" % (first.rate, first.channels), "")
            try:
                second = mod.default_render_endpoint()
                box["second"] = ("rate=%d ch=%d" % (second.rate, second.channels), "")
            except BaseException as exc:
                box["second"] = ("", "%s: %s" % (type(exc).__name__, exc))
        except BaseException as exc:
            box["first"] = ("", "%s: %s" % (type(exc).__name__, exc))
            box["second"] = ("", "not reached")
        finally:
            mod._ole32 = orig
            box["inits"] = counter.inits
            box["uninits"] = counter.uninits

    th = threading.Thread(target=run)
    th.start()
    th.join()
    ok = (
        box["first"][0] != "" and box["second"][0] != ""
        and box["inits"] == box["uninits"] == 2
    )
    print(
        "  %-30s first=%s second=%s refs{init=%d uninit=%d} %s"
        % (
            "real-two-calls-one-thread",
            box["first"][0] or "RAISED " + box["first"][1],
            box["second"][0] or ("RAISED " + box["second"][1]),
            box["inits"], box["uninits"], "OK" if ok else "RED",
        )
    )
    return {"arm": "real-two-calls-one-thread", "ok": ok,
            "got": "%s/%s" % (box["first"][0], box["second"][0]), "detail": ""}


def arm_real_sta_mismatch(mod):
    """The REAL API in the state that produces RPC_E_CHANGED_MODE: make this
    thread an STA, then ask the module for the MTA. The module must still ENUMERATE
    (COM is initialised -- in the other apartment) and must NOT call CoUninitialize,
    because the failed call took no reference. The raw HRESULT the API returns is
    printed, so the arm rests on a measurement rather than on a constant."""
    box = {}

    def run():
        counter = CountingOle32()
        orig = mod._ole32
        mod._ole32 = lambda: counter
        try:
            h_sta = counter.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
            box["h_sta"] = h_sta
            got, detail = "PROCEEDED", ""
            if h_sta == S_OK:
                box["raw"] = counter.CoInitializeEx(None, COINIT_MULTITHREADED)
                try:
                    ep = mod.default_render_endpoint()
                    box["ep"] = "%d Hz %dch" % (ep.rate, ep.channels)
                except BaseException as exc:
                    got, detail = "RAISED", "%s: %s" % (type(exc).__name__, exc)
            else:
                got, detail = "SETUP-FAILED", "STA CoInitializeEx -> 0x%08X" % (h_sta & 0xFFFFFFFF)
            box["got"], box["detail"] = got, detail
        finally:
            mod._ole32 = orig
            # balance the ONE successful init this arm itself made; done on the raw
            # DLL so it is not attributed to the module
            counter._real.CoUninitialize()
            box["uninits_by_module"] = counter.uninits

    th = threading.Thread(target=run)
    th.start()
    th.join()
    ok = (
        box.get("got") == "PROCEEDED"
        and box.get("raw") == RPC_E_CHANGED_MODE
        and box.get("uninits_by_module") == 0
    )
    print(
        "  %-30s raw sta->mta=0x%08X module=%s ep=%s module_CoUninit=%s %s%s"
        % (
            "real-sta-mismatch-usable",
            box.get("raw", 0) & 0xFFFFFFFF,
            box.get("got"),
            box.get("ep", "-"),
            box.get("uninits_by_module"),
            "OK" if ok else "RED",
            "  -- " + box["detail"] if box.get("detail") else "",
        )
    )
    return {"arm": "real-sta-mismatch-usable", "ok": ok,
            "got": box.get("got"), "detail": box.get("detail", "")}


# ── arms 7-8: the REAL pump, against a scripted COM vtable ───────────────────
class ScriptedCapture(object):
    """An IAudioCaptureClient-shaped object built the way ctypes sees one: a cell
    holding a pointer to an array of stdcall function pointers. `_vtbl(ptr, i)`
    reads the cell, then the i-th slot, and calls it as a COM method."""

    def __init__(self, packets, block_align, channels):
        self.packets = packets        # list of (frames, flags, payload_bytes)
        self.block_align = block_align
        self.channels = channels
        self.i = 0
        self.pos = 0
        self.released = 0
        self.calls = 0
        self.next_calls = 0
        protos = {}
        protos[5] = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, POINTER(wintypes.DWORD))
        protos[3] = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p,
            POINTER(POINTER(ctypes.c_ubyte)), POINTER(wintypes.DWORD),
            POINTER(wintypes.DWORD), POINTER(ctypes.c_int64))
        protos[4] = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.DWORD)
        fns = {5: self._next_size, 3: self._get_buffer, 4: self._release}
        self._vtable = (ctypes.c_void_p * 16)()
        self._keep = []
        for idx, proto in protos.items():
            cb = proto(fns[idx])
            self._keep.append(cb)
            self._vtable[idx] = ctypes.cast(cb, ctypes.c_void_p).value
        self._cell = (ctypes.c_void_p * 1)()
        self._cell[0] = ctypes.cast(self._vtable, ctypes.c_void_p).value
        # per-packet payload buffers, kept alive for the whole run
        self._bufs = [(ctypes.c_ubyte * len(p[2])).from_buffer_copy(p[2])
                      for p in self.packets]

    @property
    def handle(self):
        return ctypes.cast(self._cell, ctypes.c_void_p)

    def _next_size(self, this, pn):
        self.next_calls += 1
        if self.next_calls > 10000:      # a pump that never ends must not hang the oracle
            raise RuntimeError("scripted capture client: pump did not terminate")
        if self.i >= len(self.packets):
            # The real API returns S_OK with 0 frames while the endpoint is idle,
            # and the pump polls on that. A scripted client that has no more
            # packets ends the stream the honest way instead: a failure HRESULT,
            # which is what the pump's `break` is for. Returning 0 here would
            # loop forever.
            return E_FAIL_FOR_PUMP
        pn[0] = self.packets[self.i][0]
        return 0

    def _get_buffer(self, this, ppdata, pframes, pflags, ppos):
        if self.i >= len(self.packets):
            return E_FAIL_FOR_PUMP          # ends the pump loop, as the API would
        frames, flags, _payload = self.packets[self.i]
        pframes[0] = frames
        pflags[0] = flags
        ppos[0] = self.pos
        ppdata[0] = ctypes.cast(self._bufs[self.i], POINTER(ctypes.c_ubyte))
        self.pos += frames
        self.i += 1
        self.calls += 1
        return 0

    def _release(self, this, frames):
        self.released += 1
        return 0


class _FakeEndpoint(object):
    """Only the fields the pump reads off self.ep."""

    def __init__(self, rate, channels, block_align, format_tag):
        self.rate = rate
        self.channels = channels
        self.block_align = block_align
        self.format_tag = format_tag
        self.name = "scripted endpoint (no device opened)"
        self.endpoint_id = None
        self.bits = 32


def pump_arm(name, mod, flags, expect_peak, frames=480, packets=3, block_ms=10):
    """Run the REAL _pump against a scripted capture client.

    expect_peak == 0.0    : the packet is SILENT and must contribute no signal.
    expect_peak > 0       : the packet is real data and must be DELIVERED at full
                            magnitude -- the control that makes the first case mean
                            something."""
    np = mod.np if hasattr(mod, "np") else __import__("numpy")
    rate, channels = 48000, 2
    block_align = channels * 4
    payload = GARBAGE * (frames * channels)      # frames*ch * 4 bytes
    cap = ScriptedCapture([(frames, flags, payload)] * packets, block_align, channels)
    out = []
    tap = mod.WasapiLoopbackTap.__new__(mod.WasapiLoopbackTap)
    tap.np = __import__("numpy")
    tap.on_block = lambda b: out.append(b.copy())
    tap.block_ms = block_ms
    tap.rate = tap.native_rate = rate
    tap.channels = channels
    tap.block = int(rate * block_ms / 1000)
    tap._stop = threading.Event()
    tap._thread = None
    tap._client = None
    tap._capture = cap.handle
    tap._enum = None
    tap._dev = None
    tap.ep = _FakeEndpoint(rate, channels, block_align, mod.WAVE_FORMAT_IEEE_FLOAT)
    tap.silent_packets = 0                       # read back below; not decoration
    tap._pump()                                  # returns when get_buffer fails

    peak = max((float(abs(b).max()) for b in out), default=-1.0)
    n_silent = getattr(tap, "silent_packets", 0)
    if expect_peak == 0.0:
        ok = peak == 0.0 and len(out) == packets and n_silent == packets
        want = "peak==0 and %d blocks and silent_packets==%d" % (packets, packets)
    else:
        ok = abs(peak - GARBAGE_PEAK) < 1e-9 and len(out) == packets and n_silent == 0
        want = "peak==%.6g and %d blocks and silent_packets==0" % (GARBAGE_PEAK, packets)
    print(
        "  %-30s flags=0x%X blocks=%d/%-2d peak=%.9f silent_packets=%d  want %s  %s"
        % (name, flags, len(out), packets, peak, n_silent, want, "OK" if ok else "RED")
    )
    return {"arm": name, "ok": ok, "got": "peak=%.9f blocks=%d" % (peak, len(out)),
            "detail": ""}


def pump_arms(mod):
    return [
        pump_arm("silent-flag-is-silence", mod, AUDCLNT_BUFFERFLAGS_SILENT, 0.0),
        pump_arm("unsilenced-packet-kept", mod, 0x0, GARBAGE_PEAK),
    ]


def arm_live_tap(mod):
    """OPT-IN (--with-tap): the sequence the ladder actually runs -- probe the
    endpoint, then construct and start the tap on the SAME thread. Opens a real
    loopback stream for ~0.3 s and closes it. This is the arm that says "rung (a)
    can open at all", which is the thing the defect took away."""
    got, detail = "NO-RAISE", ""
    blocks = []
    tap = None
    try:
        spec = mod.loopback_device_spec()
        got = "spec=%s" % ("None" if spec is None else "ok")
        tap = mod.WasapiLoopbackTap(lambda b: blocks.append(b), block_ms=100)
        tap.start()
        import time
        time.sleep(0.3)
    except BaseException as exc:
        got, detail = "CRASH", "%s: %s" % (type(exc).__name__, exc)
    finally:
        if tap is not None:
            try:
                tap.close()
            except Exception:
                pass
    ok = got == "spec=ok"
    print("  %-30s %s  blocks_in_300ms=%d %s%s"
          % ("live-tap-opens", got, len(blocks), "OK" if ok else "RED",
             "  -- " + detail if detail else ""))
    return {"arm": "live-tap-opens", "ok": ok, "got": got, "detail": detail}


def run(path, name, with_tap):
    print("=" * 78)
    print("SUBJECT: %s" % path)
    print("         sha256 %s" % sha256(path))
    print("=" * 78)
    mod = load(path, name)
    results = gate_arms(mod)
    results.append(arm_real_two_calls(mod))
    results.append(arm_real_sta_mismatch(mod))
    results.extend(pump_arms(mod))
    if with_tap:
        results.append(arm_live_tap(mod))
    failed = [r["arm"] for r in results if not r["ok"]]
    print("  -> %s  (%d arms, %d failed%s)"
          % ("PASS" if not failed else "FAIL", len(results), len(failed),
             ", failed=" + ",".join(failed) if failed else ""))
    return failed


def main():
    with_tap = "--with-tap" in sys.argv
    print("flat-endpoint-oracle  root=%s" % ROOT)
    print("  arm 5/6 use the REAL ole32; arms 1-4/7-8 touch no device.")
    if with_tap:
        print("  --with-tap: arm 9 opens a real loopback stream for ~0.3 s.")
    print()
    if not os.path.exists(MUTANT):
        print("VERDICT FAIL  no frozen pre-fix copy at %s" % MUTANT)
        return 1
    if sha256(MUTANT) != MUTANT_SHA256:
        print("VERDICT FAIL  frozen pre-fix copy has drifted: %s != %s"
              % (sha256(MUTANT), MUTANT_SHA256))
        return 1
    if sha256(LIVE) == MUTANT_SHA256:
        print("NOTE: the live file still IS the pre-fix source -- both subjects "
              "must read RED until the fix lands.")
    live_failed = run(LIVE, "wasapi_loopback_live", with_tap)
    print()
    print("### CONTROL ARM -- the frozen pre-fix copy must be RED ###")
    print()
    mut_failed = run(MUTANT, "wasapi_loopback_prefix", with_tap)
    print()
    print("=" * 78)
    print("LIVE   : %s%s" % ("PASS" if not live_failed else "FAIL",
                             "" if not live_failed else " failed=" + ",".join(live_failed)))
    print("CONTROL: %s%s" % ("RED as required" if mut_failed else "GREEN -- the "
                             "control cannot fail, so it proves nothing",
                             "" if mut_failed else " failed=[]"))
    good = (not live_failed) and bool(mut_failed)
    print("VERDICT %s" % ("PASS" if good else "FAIL"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
