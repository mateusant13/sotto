"""RED/GREEN control for the CoInitializeEx contract in worker/wasapi_loopback.py.

Ticket TICKET-140ba250c2f890e1e8bbf62d (repo ticket 140ba250c2f890e1e8bbf62d):
`default_render_endpoint()` refused S_FALSE (1), which is a SUCCESS code, so the
second call in the same thread raised WasapiError.

The contract under test is the one the vendor states, not the one the code
assumed -- CoInitializeEx, Return value + Remarks:
  S_OK                0x00000000  COM started on this thread.  reference taken.
  S_FALSE             0x00000001  COM ALREADY running on this thread in the SAME
                                  apartment.  A SUCCESS code.  reference taken.
  RPC_E_CHANGED_MODE  0x80010106  COM running here in a DIFFERENT apartment --
                                  "the call fails and returns RPC_E_CHANGED_MODE".
                                  NO reference taken.
  "each successful call to CoInitialize or CoInitializeEx, including any call
   that returns S_FALSE, must be balanced by a corresponding call to
   CoUninitialize."

THIS ORACLE NEVER TOUCHES AN AUDIO DEVICE.
  * Arms 1-4 replace the module's `_ole32()` with a stub whose CoInitializeEx
    returns a scripted HRESULT and whose CoCreateInstance RAISES a sentinel, so
    the enumeration/activation path is unreachable by construction -- the stub
    counts the attempt and stops there.  No endpoint is enumerated, no stream is
    initialised.
  * Arms 5-6 call the REAL CoInitializeEx/CoUninitialize only.  Both are pure
    apartment bookkeeping; neither opens, queries or configures an endpoint.
  * There is no arm anywhere in this file that calls the real CoCreateInstance.

Run:  py -3 _main/wasapi-com-init-oracle.py           both colours, one command
      py -3 _main/wasapi-com-init-oracle.py --neg-arm only the pre-fix copy
"""

import ctypes
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIVE = os.path.join(ROOT, "worker", "wasapi_loopback.py")
BEFORE = os.path.join(HERE, "_wasapi-com-before.LATEST.txt")

COINIT_MULTITHREADED = 0x0
COINIT_APARTMENTTHREADED = 0x2
S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106
E_UNEXPECTED = -2147418113  # 0x8000FFFF, one of the documented failures

COINIT = COINIT_APARTMENTTHREADED


def _p(msg=""):
    print(msg)


def load(path, name):
    """Import a module from an explicit path, so the mutant is never shadowed by
    an already-imported `wasapi_loopback` in sys.modules."""
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class StopHere(Exception):
    """Sentinel: the init gate passed and we reached the device path."""


class _Fn(object):
    """ctypes function pointers accept `.argtypes`/`.restype`; a bound method
    does not. The module assigns both, so the stub must too."""

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
        self.CoUninitialize = _Fn(lambda: self._uninit())
        self.CoCreateInstance = _Fn(self._co_create)
        self.CoTaskMemFree = _Fn(lambda p: None)

    def _co_init_ex(self, *a):
        self.init_calls += 1
        return self._hr

    def _uninit(self):
        self.uninit_calls += 1
        return 0

    def _co_create(self, *a):
        # Stops BEFORE any endpoint work. Counting it proves the arms reached
        # the gate and the arm never went past it.
        self.device_calls += 1
        raise StopHere("stub: reached CoCreateInstance")


def stub_arm(name, mod, init_hr, expect, took_ref):
    """Run default_render_endpoint() against a scripted ole32.

    expect: "proceed"  -> the init gate must pass; we then stop at the stub.
            "raise"    -> WasapiError must come out of the init gate itself.
    took_ref: whether the vendor contract says THIS outcome took a COM reference
              that the caller is then OBLIGED to give back. It is asserted
              separately from `expect`, because the two are different questions:
              an outcome can be admissible AND still owe a reference.
    """
    stub = StubOle32(init_hr)
    real_ole32 = mod._ole32
    mod._ole32 = lambda: stub
    verdict = None
    detail = ""
    try:
        mod.default_render_endpoint()
        verdict = "NO-RAISE"
        detail = "default_render_endpoint() returned without raising"
    except StopHere:
        verdict = "proceed"
    except mod.WasapiError as exc:
        verdict = "raise"
        detail = str(exc)[:90]
    except BaseException as exc:  # a crash is not a verdict
        verdict = "CRASH"
        detail = "%s: %s" % (type(exc).__name__, exc)
    finally:
        mod._ole32 = real_ole32

    ok = verdict == expect
    # A reference is owed for S_OK/S_FALSE only. RPC_E_CHANGED_MODE took NOTHING,
    # so calling CoUninitialize there would release a reference this module never
    # took -- i.e. it would tear down another component's apartment.
    if took_ref:
        # the call must give back exactly one reference, including on the
        # exception path (here: the stub's StopHere inside the enumeration body)
        bal_ok = stub.uninit_calls == 1
    else:
        bal_ok = stub.uninit_calls == 0
    bal = "init=%d uninit=%d" % (stub.init_calls, stub.uninit_calls)
    ok = ok and bal_ok and stub.device_calls == (1 if expect == "proceed" else 0)

    _p(
        "  %-28s hr=0x%08X expect=%-8s got=%-8s %s  balance[%s] %-9s owes-ref=%s%s"
        % (
            name,
            init_hr & 0xFFFFFFFF,
            expect,
            verdict,
            "OK" if ok else "RED",
            bal,
            "balanced" if bal_ok else "UNBALANCED",
            "yes" if took_ref else "no",
            ("  -- " + detail) if detail else "",
        )
    )
    return {"arm": name, "ok": ok, "got": verdict, "detail": detail,
            "init": stub.init_calls, "uninit": stub.uninit_calls,
            "device_calls": stub.device_calls}


def real_ole32():
    dll = ctypes.WinDLL("ole32", use_last_error=True)
    dll.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    dll.CoInitializeEx.restype = ctypes.c_long
    dll.CoUninitialize.argtypes = []
    dll.CoUninitialize.restype = None
    return dll


def arms_stubbed(mod):
    """`owe` encodes what the VENDOR contract says each outcome owes, not what
    the code happens to do.

    RPC_E_CHANGED_MODE is admissible here and OWES NOTHING: the call failed, so
    no reference was taken, and CoUninitialize would release a reference this
    module never took. It is a STATE, not a fault -- see the note on
    `real-mismatch-keeps-working`.
    """
    return [
        stub_arm("s-false-is-success", mod, S_FALSE, "proceed", True),
        stub_arm("s-ok-is-success", mod, S_OK, "proceed", True),
        stub_arm("changed-mode-no-ref", mod, RPC_E_CHANGED_MODE, "proceed", False),
        stub_arm("genuine-failure-raises", mod, E_UNEXPECTED, "raise", False),
    ]


def arm_real_second_call(_mod):
    """Ground truth from the REAL API: a second CoInitializeEx in the same
    apartment returns S_FALSE. No endpoint is touched."""
    ole32 = real_ole32()
    h1 = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    h2 = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    ole32.CoUninitialize()  # one per successful call -- h2 returned S_FALSE
    ole32.CoUninitialize()
    ok = (h1 == S_OK) and (h2 == S_FALSE)
    _p("  %-28s real API hr1=0x%08X hr2=0x%08X  expect hr1=S_OK hr2=S_FALSE  %s"
       % ("real-second-call-is-sfalse", h1 & 0xFFFFFFFF, h2 & 0xFFFFFFFF,
          "OK" if ok else "RED"))
    return {"arm": "real-second-call-is-sfalse", "ok": ok,
            "got": "hr2=0x%08X" % (h2 & 0xFFFFFFFF), "detail": "",
            "init": 2, "uninit": 2, "device_calls": 0}


def arm_real_mismatch(mod):
    """Real-API arm, in an apartment that really is a different one.

    MEASURED 2026-10-06, clean process, no pre-init by this oracle:
    `import sounddevice; sd.query_devices()` leaves the MAIN THREAD in an STA
    (53 devices enumerated), after which a WASAPI-style MTA request returns
    RPC_E_CHANGED_MODE. So this is not a hypothetical branch on this box -- it is
    the branch a natural worker run takes before rung (a) is ever probed.

    Therefore the module MUST NOT refuse here: refusing deletes the only rung
    that needs no virtual cable. What it must do instead is distinguish the
    outcome from success, and -- the part a boolean collapses -- NOT give back a
    reference it never took.

    No endpoint is touched: only CoInitializeEx/CoUninitialize are called.
    """
    if not hasattr(mod, "_com_init"):
        _p("  %-28s SKIPPED -- module has no _com_init() (pre-fix shape)"
           % "real-mismatch-owes-nothing")
        return {"arm": "real-mismatch-owes-nothing", "ok": True, "got": "SKIPPED",
                "detail": "no _com_init on this build", "init": 0, "uninit": 0,
                "device_calls": 0}
    ole32 = real_ole32()
    h_sta = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    got = "SETUP-FAILED"
    detail = ""
    if h_sta != S_OK:
        detail = "STA init returned 0x%08X" % (h_sta & 0xFFFFFFFF)
    else:
        raw = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        detail = "raw api in an STA -> 0x%08X" % (raw & 0xFFFFFFFF)
        try:
            outcome = mod._com_init()
        except mod.WasapiError as exc:
            got = "REFUSED"
            detail += "; module refused: %s" % str(exc)[:80]
        except BaseException as exc:
            got = "CRASH"
            detail += "; %s: %s" % (type(exc).__name__, exc)
        else:
            got = "admitted:%s" % outcome
        finally:
            # exactly ONE successful init happened here (the STA one); the
            # MTA request failed and owes no reference, so one uninit is due.
            ole32.CoUninitialize()

    # admitted AND explicitly marked as owing nothing
    ok = got.startswith("admitted:") and got != "admitted:taken"
    _p("  %-28s real API in an STA -> %-18s %s"
       % ("real-mismatch-owes-nothing", got, "OK" if ok else "RED"))
    _p("  %-28s %s" % ("", detail[:120]))
    return {"arm": "real-mismatch-owes-nothing", "ok": ok, "got": got,
            "detail": detail, "init": 1, "uninit": 1, "device_calls": 0}


def run(path, name):
    _p("=" * 78)
    _p("SUBJECT: %s" % path)
    _p("=" * 78)
    mod = load(path, name)
    results = arms_stubbed(mod)
    results.append(arm_real_second_call(mod))
    results.append(arm_real_mismatch(mod))
    failed = [r["arm"] for r in results if not r["ok"]]
    _p("  -> %s  (%d arms, %d failed%s)"
       % ("PASS" if not failed else "FAIL", len(results), len(failed),
          ", failed=" + ",".join(failed) if failed else ""))
    return failed


def main():
    neg = "--neg-arm" in sys.argv
    _p("wasapi-com-init-oracle  ticket=140ba250c2f890e1e8bbf62d  "
       "root=%s" % ROOT)
    _p("NO AUDIO DEVICE IS OPENED BY ANY ARM (see module docstring).")
    _p()

    if neg:
        _p("### NEGATIVE ARM -- the pre-fix copy must stay RED ###")
        _p()
        if not os.path.exists(BEFORE):
            _p("VERDICT FAIL  no before-copy recorded at %s" % BEFORE)
            return 1
        before = open(BEFORE).read().split()[0]
        failed = run(before, "wasapi_loopback_before")
        if not failed:
            _p("VERDICT FAIL  the pre-fix copy went GREEN -- the control cannot "
               "fail, so it proves nothing")
            return 1
        _p()
        _p("VERDICT PASS  (negative arm) pre-fix copy is RED on %d arm(s): %s"
           % (len(failed), ",".join(failed)))
        return 0

    live_failed = run(LIVE, "wasapi_loopback_live")
    _p()
    _p("=" * 78)
    neg_failed = None
    if os.path.exists(BEFORE):
        before = open(BEFORE).read().split()[0]
        _p("### NEGATIVE ARM -- the pre-fix copy must be RED ###")
        _p()
        neg_failed = run(before, "wasapi_loopback_before")
    else:
        _p("(no before-copy recorded at %s -- negative arm skipped)" % BEFORE)
    _p()
    _p("LIVE   : %s" % ("PASS" if not live_failed else
                        "FAIL failed=" + ",".join(live_failed)))
    _p("NEGARM : %s" % ("PASS (pre-fix copy RED on %d arm(s))"
                        % len(neg_failed) if neg_failed else "FAIL"))
    good = (not live_failed) and bool(neg_failed)
    _p()
    _p("VERDICT %s" % ("PASS" if good else "FAIL"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())