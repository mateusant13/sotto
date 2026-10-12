"""The idle-tap freeze patch, as DATA, plus a COPY-ONLY applier.

WHY A SCRIPT AND NOT AN EDIT: the owner's order for this emergency is that ONLY
the Lead writes worker/sotto_worker.py, and hot_reload.py restarts the worker on
every save of it. So the patch is delivered as exact before/after text and this
applier writes a COPY, never the product file. It refuses an output under worker/
or an output that already exists, so it cannot silently overwrite another lane's file.

Usage:
    python _main/_tap-idle-patch.py --src worker/sotto_worker.py --out _main/_tmp-worker-patched.py

Every edit is an EXACT string match with a count expectation, so a moved worker
revision fails loudly instead of patching the wrong line.
"""
import argparse
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "worker", "sotto_worker.py")

EDIT1_OLD = """                        if device_blocks["value"] != stall_blocks:
                            # Still delivering: this tap IS the run.
                            stall_blocks = device_blocks["value"]
                            stall_since = now
                            stall_backoff = TAP_STALL_S
                        elif now - stall_since >= stall_backoff:
"""

EDIT1_NEW = """                        # STEP ONE -- is this a stall WORTH a rotation, or merely an
                        # idle endpoint? device_blocks frozen is READINESS, not a
                        # death sentence: it says only that no block arrived. An
                        # endpoint that nothing renders into LEGITIMATELY delivers no
                        # packet at all -- measured on this box, 5 of 6 active render
                        # endpoints return n=0
                        # (docs/audit/blank-frames-root-cause.md:154) -- and the pump
                        # polls that nothing every 5 ms while staying ALIVE
                        # (worker/wasapi_loopback.py:982-984), never setting
                        # pump_exited. MEASURED LIVE in the freezing run
                        # (_main/webview-run.log L93666):
                        #     TAP_STALLED ... stalled_s=60.0 blocks=0 reopens=32
                        #     pump_exited=False silent_packets=0 gap_packets=0
                        # -- a tap that was ALIVE and reading ZERO packets was rotated
                        # 33 times anyway, each rotation restarting an endpoint's audio
                        # stream. That is the "travada muito forte a cada alguns
                        # segundos" the owner reported. Rotating an idle endpoint cannot
                        # conjure audio into it, and the next rung is equally idle (2 of
                        # 9 and 2 of 10 ladder candidates silent, the same device every
                        # time), so the rotation buys nothing and costs a WASAPI
                        # Initialize.
                        stall_worth_rotating = (
                            # (1) the pump BROKE on an HRESULT. The only two writers of
                            # pump_exited are worker/wasapi_loopback.py:978
                            # (GetNextPacketSize) and :992 (GetBuffer) -- the one state
                            # that is dead BY EVIDENCE rather than by silence.
                            bool(getattr(getattr(tap, "stream", tap),
                                         "pump_exited", False))
                            # (2) the counter froze AFTER DELIVERING. That is the real
                            # frozen tap this 2026-10-11 watchdog targets:
                            # device_blocks froze at 59 after 5.6 s of audio
                            # (_main/receipt-20261011-altc-frozen-tap.md D3) -- an
                            # engine that stopped MID-STREAM, not an endpoint that never
                            # had anything in it. The two look identical to the block
                            # counter and are told apart ONLY here.
                            or device_blocks["value"] > 0
                            # (3) OR the run has been truly idle a long time, so
                            # re-scanning ONCE is worth it: the audio may simply have
                            # MOVED. 90 s of real silence before the first rotation
                            # replaces the 32-reopen loop with at most one reopen per
                            # stall_backoff -- one per 60 s once the backoff has
                            # doubled -- instead of one per 4-22 s.
                        )
                        if device_blocks["value"] != stall_blocks:
                            # Still delivering: this tap IS the run. stall_since is
                            # the no-block clock and is renewed here. The BACKOFF is
                            # deliberately NOT renewed: assigning
                            # stall_backoff = TAP_STALL_S on this path is what erased
                            # the exponential growth on every delivered block and held
                            # the measured re-open cadence at 4-22 s while reopens
                            # climbed to 32 (the 2026-10-12 log above).
                            stall_blocks = device_blocks["value"]
                            stall_since = now
                        elif (now - stall_since >= stall_backoff
                              and stall_worth_rotating):
"""

EDIT2_OLD = """                            emit(type="status", state="device-rotated", reason="tap-stalled",
                                 to=target["name"], device=dev["name"],
                                 stalled_s=round(stalled_s, 1), blocks=device_blocks["value"],
                                 captions=counters["captions"])
"""

EDIT2_NEW = """                            # The word must name WHY, because it is what the owner reads:
                            # the bridge builds the footer from this reason (_readable,
                            # app/webview/sotto_webview.py:7920-7928) and separately caches the
                            # LAST reason=flat (app/webview/sotto_webview.py:8019-8022),
                            # stamping it with evidence_age_s=3092.1 while the live statuses
                            # all said tap-stalled -- the panel and the log were describing
                            # DIFFERENT rotations.
                            stall_kind = ("pump-dead"
                                          if not device_blocks["value"]
                                          and getattr(inner, "pump_exited", False)
                                          else "tap-frozen"
                                          if device_blocks["value"]
                                          else "tap-idle")
                            emit(type="status", state="device-rotated", reason="tap-stalled",
                                 to=target["name"], device=dev["name"],
                                 stalled_s=round(stalled_s, 1), blocks=device_blocks["value"],
                                 captions=counters["captions"], stall_kind=stall_kind)
"""

EDIT3_OLD = """            rotations += 1
"""

EDIT3_NEW = """            rotations += 1
            # -- THE LADDER'S OWN BACKOFF (added 2026-10-12) -------------------------
            # A flat rotation used to be IMMEDIATE: close one tap, open the next,
            # serve out its window, rotate again. With nothing routed into any
            # candidate -- the measured normal on this box, where every loopback reads
            # digital silence -- the whole ladder is burned at one endpoint per
            # tap_window and the run dies device-exhausted, which the shell then
            # restarts on its own 2 s/8 s/16 s/30 s backoff
            # (app/webview/sotto_webview.py:8147). Measured in one owner run: 2 146
            # reason=flat rotations, 56 device-exhausted, 444 BRIDGE_RESTART.
            # Each rotation is an IAudioClient::Initialize on a new endpoint, so the
            # ladder is the OTHER half of the owner's freeze. 1 s, doubling to 8 s per
            # rotation, so a machine with nothing to capture stops paying for it
            # every few seconds. stop.wait (never time.sleep) so stop and
            # --max-seconds still answer at once.
            stop.wait(float(min(8.0, 2.0 ** (rotations - 1))))
"""

EDITS = [
    ("E1+E2 the liveness gate and the backoff-reset bug", EDIT1_OLD, EDIT1_NEW, 1),
    ("E3 the rotation names its kind", EDIT2_OLD, EDIT2_NEW, 1),
    ("E4 the ladder's own backoff", EDIT3_OLD, EDIT3_NEW, 1),
]


def apply(text):
    notes = []
    for label, old, new, count in EDITS:
        found = text.count(old)
        if found != count:
            print("FAIL %s: expected %d exact match(es), found %d" % (label, count, found))
            print("--- the first 240 bytes this edit expected ---")
            print(repr(old[:240]))
            sys.exit(1)
        notes.append("%s at byte-offset %d" % (label, text.find(old)))
        text = text.replace(old, new)
    return text, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=LIVE)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)
    if os.path.abspath(ROOT) != os.path.dirname(os.path.dirname(src)):
        print("FAIL --src is not inside this repo: %s" % src)
        return 2
    if not src.endswith(os.path.join("worker", "sotto_worker.py")):
        print("FAIL --src must be worker/sotto_worker.py, not another worker file")
        return 2
    if os.sep + "worker" + os.sep in (os.sep + out.replace("/", os.sep)):
        print("FAIL --out must NOT be under worker/ (only the Lead writes there)")
        return 2
    if os.path.exists(out):
        print("FAIL --out already exists, refusing to overwrite: %s" % out)
        return 2

    # The worker is CRLF with 0 bare LF (a pinned property). Measure that on
    # the RAW bytes, then read with universal newlines so the edit strings are
    # plain LF, and write back with newline="\r\n" so the copy keeps the property.
    with open(src, "rb") as fh:
        raw = fh.read()
    bare_lf = raw.count(b"\n") - raw.count(b"\r\n")
    print("  source: %d bytes, bare LF = %d (must be 0), CRLF = %d" % (
        len(raw), bare_lf, raw.count(b"\r\n")))
    if bare_lf:
        print("FAIL --src does not have the pinned CRLF property; refusing")
        return 2

    with open(src, "r", encoding="utf-8", errors="surrogateescape",
              newline=None) as fh:
        text = fh.read()
    text, notes = apply(text)

    shutil.copyfile(src, out)                 # prove we read it first
    with open(out, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)

    with open(out, "rb") as fh:
        data = fh.read()
    print("patched copy written: %s" % out)
    for n in notes:
        print("  " + n)
    print("  bytes %d, sha256 %s, bare LF = %d (must be 0)" % (
        len(data), hashlib.sha256(data).hexdigest(),
        data.count(b"\n") - data.count(b"\r\n")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
