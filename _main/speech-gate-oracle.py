"""Speech/music gate oracle (lane SottoSpeechSeparation).

A regression check for the ONE decision the gate makes: is a 560 ms chunk
speech? It exercises `sotto_worker.SpeechMusicGate` directly -- no model, no
audio device, ~1 second -- so it is cheap enough to run on every change to the
gate, and it FAILS on the plausible breakage (threshold moved, feature swapped,
hangover removed).

  python speech-gate-oracle.py            # exit 0 = PASS, 1 = FAIL
  python speech-gate-oracle.py --json     # machine-readable

RED input (the negative control) is the captured drone from 2026-10-06; the
GREEN inputs are the four speech fixtures in the repo. If the drone capture is
absent, the drone arm falls back to a synthesized 60 Hz tone so the oracle still
has a negative -- and says which it used.
"""
import argparse
import io
import re
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))
import sotto_worker as W  # noqa: E402

SR, CHUNK = 16000, 8960

SPEECH = [
    os.path.join(ROOT, "worker", "assets", "sample1.flac"),
    os.path.join(ROOT, "worker", "assets", "sample2.flac"),
    os.path.join(HERE, "pt-br-sample.wav"),
    os.path.join(HERE, "en-us-sample.wav"),
]
DRONE = os.path.join(HERE, "bfrc_live_capture2.wav")

# THE TWO POPULATIONS THE ORACLE NEVER COVERED (added 2026-11-15).
# Every speech fixture above is a clean STUDIO recording, so all four came back
# `kept_frac=1.0` while the shipped gate was deleting 72 % of a real broadcast
# and the product was losing 55 % of its transcript (`_main/devlab/lab.py score`,
# receipt `_main/receipt-20261115-speech-gate-broadcast.md`).
#   * BROADCAST is the owner's own 90 s cable capture: a real video, music bed
#     included, the exact class the product meets.
#   * MUSIC_BED is the diarization lane's real bed-only mix. It is the negative
#     arm that a constant-amplitude drone can never be, because it has the
#     percussive envelope the drone lacks and can therefore actually fail.
BROADCAST = os.path.join(HERE, "live-sample-cable-input-90s.wav")
MUSIC_BED = os.path.join(HERE, "diar-mix", "mix-bedonly.wav")


def to_16k(x, sr):
    if sr == SR:
        return x.astype(np.float32)
    n = int(round(len(x) * SR / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def load(path):
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return to_16k(x, sr)


def synth_drone(secs=8.0):
    t = np.arange(int(secs * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * 60 * t) + 0.15 * np.sin(2 * np.pi * 120 * t)
            + 0.07 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)


def gate_chunks(x):
    g = W.SpeechMusicGate()
    n = len(x) // CHUNK
    kept = [g.is_speech(x[i * CHUNK:(i + 1) * CHUNK]) for i in range(n)]
    return n, sum(kept), n - sum(kept)


NEG_CASES = {
    # name -> (what it plants, which problem it must produce)
    "gate-default-on": ("the shipping default flipped back to ON",
                        "the gate default is not OFF"),
    "broadcast-bar-removed": ("the broadcast bar downgraded to a publish",
                              "broadcast: kept only"),
}


def _neg_arm():
    """Plant each defect in a COPY and require THIS oracle to go RED.

    A control that cannot fail is not a control. Each case mutates the real
    sources the oracle reads -- `sotto_worker.py` for the default,
    `GATE_DB_RANGE_MIN` for the broadcast bar -- never a hand-built verdict.
    """
    import shutil, subprocess, tempfile
    here = HERE
    caught = 0
    for name, (_what, needle) in sorted(NEG_CASES.items()):
        tmp = tempfile.mkdtemp(prefix="sgneg-")
        try:
            root = os.path.join(tmp, "tree")
            shutil.copytree(os.path.join(ROOT, "worker"),
                            os.path.join(root, "worker"),
                            ignore=shutil.ignore_patterns("models", "__pycache__"))
            os.makedirs(os.path.join(root, "_main"), exist_ok=True)
            for fn in ("live-sample-cable-input-90s.wav", "en-us-sample.wav",
                       "pt-br-sample.wav"):
                src = os.path.join(here, fn)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(root, "_main", fn))
            shutil.copy2(os.path.abspath(__file__),
                         os.path.join(root, "_main", "speech-gate-oracle.py"))
            if name == "gate-default-on":
                wp = os.path.join(root, "worker", "sotto_worker.py")
                src = io.open(wp, encoding="utf-8").read()
                src = src.replace("    if _gate_env is None:\n        gate_enabled = False",
                                  "    if _gate_env is None:\n        gate_enabled = True", 1)
                io.open(wp, "w", encoding="utf-8", newline="").write(src)
                mutated = os.path.join(root, "worker", "sotto_worker.py")
            else:
                # Raise the threshold so the broadcast bar bites. The class the
                # worker ACTUALLY uses lives in `sotto_worker.py` -- the first
                # version of this mutant edited `_prefix_audioflag.py`, which is
                # a DIFFERENT copy of the same class, so the process under test
                # never changed and the arm reported NOT-CAUGHT on a real defect.
                # TWO mutations, because the bar is DORMANT while the gate
                # ships off: someone re-enables it AND retunes it to a number
                # that looks tuned (20 dB still keeps all four studio fixtures
                # at 0.87+). That is the defect this arm exists to refuse -- a
                # re-enabled gate that quietly eats a third of real broadcast.
                fp = os.path.join(root, "worker", "sotto_worker.py")
                src = io.open(fp, encoding="utf-8").read()
                new_src = re.sub(r"^GATE_DB_RANGE_MIN = [0-9.]+",
                                 "GATE_DB_RANGE_MIN = 20.0", src, flags=re.M)
                new_src = new_src.replace("    if _gate_env is None:\n        gate_enabled = False",
                                          "    if _gate_env is None:\n        gate_enabled = True", 1)
                assert new_src != src, "the mutant did not land in sotto_worker.py"
                io.open(fp, "w", encoding="utf-8", newline="").write(new_src)
                mutated = fp
            r = subprocess.run([sys.executable,
                                os.path.join(root, "_main", "speech-gate-oracle.py")],
                               capture_output=True, text=True, timeout=600)
            out = (r.stdout or "") + (r.stderr or "")
            hit = needle in out
            print("  %-24s rc=%d %s" % (name, r.returncode,
                                        "CAUGHT" if (r.returncode == 1 and hit)
                                        else "NOT-CAUGHT"))
            if r.returncode == 1 and hit:
                caught += 1
            else:
                print("    output tail:", out.strip().splitlines()[-3:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("NEG-ARM: %s -- %d/%d planted defects caught" %
          ("PASS" if caught == len(NEG_CASES) else "FAIL", caught, len(NEG_CASES)))
    return 1 if caught == len(NEG_CASES) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--neg-arm", action="store_true",
                    help="plant the defects the oracle exists to catch and require the RED")
    args = ap.parse_args()

    if args.neg_arm:
        return _neg_arm()

    problems = []
    rows = []

    # THE SHIPPING DEFAULT. The gate cost 55 % of the transcript as a product
    # default, so the default is OFF and this arm keeps it that way. Read
    # STRUCTURALLY, not by substring: the first version tested `"is" in
    # ast.dump(...)` and the dump spells the operator `Is()`, so the arm read
    # False on correct code -- an instrument that accuses a correct site.
    # The SOURCE is read rather than the behaviour, because importing the
    # worker's main() would open an audio device.
    import ast
    _wpath = os.path.join(ROOT, "worker", "sotto_worker.py")
    worker_src = open(_wpath, encoding="utf-8").read()
    default_off = None          # None = the shape was not found (CANNOT-MEASURE)
    for node in ast.walk(ast.parse(worker_src)):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        names = {n.id for n in ast.walk(test) if isinstance(n, ast.Name)}
        if ("_gate_env" not in names
                or not any(isinstance(o, ast.Is) for o in
                           (test.ops if isinstance(test, ast.Compare) else []))
                or not any(isinstance(c, ast.Constant) and c.value is None
                           for c in (test.comparators if isinstance(test, ast.Compare) else []))):
            continue
        # `if _gate_env is None:` -- what does the branch assign?
        for stmt in node.body:
            if (isinstance(stmt, ast.Assign)
                    and any(getattr(t, "id", "") == "gate_enabled" for t in stmt.targets)
                    and isinstance(stmt.value, ast.Constant)):
                default_off = (stmt.value.value is False)
    rows.append(dict(arm="default", src="sotto_worker.py", chunks=1, kept=0, gated=0,
                     gate_default_off=default_off))



    # NEGATIVE: the gate must withhold every chunk of a stationary drone.
    drone_src = DRONE if os.path.exists(DRONE) else "synth:60Hz"
    drone = load(DRONE) if os.path.exists(DRONE) else synth_drone()
    n, kept, gated = gate_chunks(drone)
    rows.append(dict(arm="drone", src=drone_src, chunks=n, kept=kept, gated=gated))
    if n == 0:
        problems.append("drone arm had no chunks")
    elif gated != n:
        problems.append(f"drone arm kept {kept}/{n} chunks; every one must be gated")

    # POSITIVE: the gate must KEEP the speech fixtures (allowing for genuine
    # pauses inside a clip, which are correctly gated). The bar is a majority
    # kept AND at least one caption-worthy run -- a gate that gated speech would
    # fail here, which is the regression this exists to catch.
    for p in SPEECH:
        if not os.path.exists(p):
            problems.append(f"missing speech fixture {p}")
            continue
        x = load(p)
        n, kept, gated = gate_chunks(x)
        frac = kept / n if n else 0.0
        rows.append(dict(arm="speech", src=os.path.basename(p), chunks=n, kept=kept, gated=gated,
                         kept_frac=round(frac, 3)))
        if frac < 0.5:
            problems.append(f"{os.path.basename(p)}: kept only {kept}/{n} ({frac:.2f}) -- gate ate speech")

    # BROADCAST: the gate must keep the majority of a real broadcast window.
    # This is the arm that would have caught the shipped defect; it is a
    # MAJORITY bar because real broadcast audio has genuine pauses.
    if os.path.exists(BROADCAST):
        x = load(BROADCAST)
        n, kept, gated = gate_chunks(x)
        frac = kept / n if n else 0.0
        rows.append(dict(arm="broadcast", src=os.path.basename(BROADCAST), chunks=n,
                         kept=kept, gated=gated, kept_frac=round(frac, 3)))
        # BINDING ONLY IF THE GATE SHIPS. While the default is OFF the mechanism
        # is dormant and this arm publishes the number; the moment somebody
        # turns it back on, the bar binds and this defect cannot ship twice.
        if frac < 0.5:
            msg = (f"broadcast: kept only {kept}/{n} ({frac:.2f}) -- the gate is eating "
                   f"real speech, which is the 2026-11-15 defect")
            if not default_off:
                problems.append(msg)
            else:
                rows[-1]["dormant"] = msg
    else:
        rows.append(dict(arm="broadcast", src="MISSING", chunks=0, kept=0, gated=0))

    # MUSIC BED: the honest negative arm. This arm is EXPECTED TO FAIL at the
    # current 18 dB threshold -- on real audio the gate cannot separate music
    # from speech at any threshold that also keeps speech (measured: 0.97/0.80
    # music vs 0.88/0.81 broadcast at 6-8 dB). So it does not gate the verdict;
    # it publishes the number, which is what makes "the mechanism does not work"
    # a measurement instead of an opinion.
    if os.path.exists(MUSIC_BED):
        x = load(MUSIC_BED)
        n, kept, gated = gate_chunks(x)
        frac = kept / n if n else 0.0
        rows.append(dict(arm="music", src=os.path.basename(MUSIC_BED), chunks=n,
                         kept=kept, gated=gated, kept_frac=round(frac, 3),
                         informative="a real music bed kept at this rate means the "
                                     "sub-frame dB span is not a music/speech discriminator"))

    if default_off is None:
        problems.append("CANNOT-MEASURE: could not find `if _gate_env is None:` assigning "
                        "gate_enabled in worker/sotto_worker.py -- an instrument that cannot "
                        "read the default cannot certify it")
    elif default_off is False:
        problems.append("the gate default is not OFF -- it cost 55 % of the transcript "
                        "as a product default (receipt 2026-11-15-speech-gate-broadcast)")

    ok = not problems
    out = dict(ok=ok, thresholds=dict(db_range_min=W.GATE_DB_RANGE_MIN,
                                      rms_floor=W.GATE_RMS_FLOOR, hold_chunks=W.GATE_HOLD_CHUNKS),
               rows=rows, problems=problems)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("speech-gate oracle")
        print(f"  thresholds: dbrange>={W.GATE_DB_RANGE_MIN} rms>={W.GATE_RMS_FLOOR} hold={W.GATE_HOLD_CHUNKS}")
        for r in rows:
            extra = f" kept_frac={r['kept_frac']}" if "kept_frac" in r else ""
            if r.get("gate_default_off") is not None:
                extra = f" default_off={r['gate_default_off']}"
            print(f"  {r['arm']:6} {r['src']:28} chunks={r['chunks']:3} kept={r['kept']:3} "
                  f"gated={r['gated']:3}{extra}")
        print("  VERDICT:", "PASS" if ok else "FAIL")
        for p in problems:
            print("   -", p)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
