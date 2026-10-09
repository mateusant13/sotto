"""_hl-auto-highlights-gate.py -- THE GATE for the auto-highlights detector.

Run:  py -3 _main/_hl-auto-highlights-gate.py > _main/_hl-auto-highlights-gate.log 2>&1
      read $LASTEXITCODE.  NEVER pipe a native command when the exit code matters.

================================================================================
WHY THIS GATE IS SHAPED LIKE THIS
================================================================================

`receipts/review-L15.md` S3 caught the previous highlights gate calling a
tautological arm its false-positive claim: "It is true by construction, for any
input... A gate that cannot go red is not a gate."  An arm that is green because
the code cannot produce anything else proves nothing.

So EVERY arm below has a MUTATION that must turn it red, and the mutation arms are
part of the gate's pass condition, not an optional extra.  If you delete a guard
and the output does not change, the gate FAILS and says which guard is inert --
which is exactly the class of defect the previous highlights design shipped twice.

THE ARMS
  ARM Q  quiet footage saves nothing      (the brief's bar: N minutes of quiet -> 0 clips)
  ARM B  sustained activity is not a moment (the arm the deleted spec had no answer to)
  ARM S  a genuine spike saves EXACTLY ONE clip, at the right second
  ARM M  the guards are load-bearing: each mutation must change an outcome

POPULATION AND WINDOW are printed at the top of every run.  Nothing below is
carried over from a previous run.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "index"))

import highlights as H  # noqa: E402  (path set above, deliberately)

SERIES_NPZ = REPO / "_main" / "_hl-frame-series.npz"
GRID_W, GRID_H, FPS = 64, 36, 10

#: The two real clips the spike arm is built from.  Both are quiet captures on
#: disk; their frames are decoded, an event is inserted, and the diff series is
#: recomputed from the resulting frames -- the detector sees exactly what it would
#: see on a real stream.
SPIKE_SRC = REPO / "_main" / "runs" / "cap-mux-1080p.mp4"
QUIET_SRC = REPO / "_main" / "logs" / "cap-nvenc-2160p60-run1.mp4"
#: A clip of the busy class (per-clip p50 = 0.1519), used by ARM S2.
BUSY_SRC = REPO / "_main" / "runs" / "clip-20261007-111303.mp4"

#: How close the reported peak has to be to the injected event.  0.5 s = 5 frames
#: at the 10 fps analysis rate.
PEAK_TOLERANCE_S = 0.5

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def load_series() -> tuple[list[str], list[np.ndarray]]:
    d = np.load(SERIES_NPZ, allow_pickle=True)
    return [str(x) for x in d["names"]], [np.asarray(x, dtype=float) for x in d["diff"]]


def decode_frames(path: Path, max_frames: int = 120) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
           "-vf", f"fps={FPS},scale={GRID_W}:{GRID_H},format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    fb = GRID_W * GRID_H
    n = min(len(r.stdout) // fb, max_frames)
    if n < 4:
        raise RuntimeError(f"{path}: only {n} frames decoded")
    return np.frombuffer(r.stdout[: n * fb], dtype=np.uint8).reshape(n, GRID_H, GRID_W)


def diff_of(frames: np.ndarray) -> np.ndarray:
    f = frames.astype(np.int16)
    return np.abs(np.diff(f, axis=0)).mean(axis=(1, 2)) / 255.0


def with_flash(frames: np.ndarray, at: int, length: int = 3) -> np.ndarray:
    """A full-frame flash inserted into REAL decoded frames.

    SYNTHETIC EVENT, real pixels everywhere else.  Labelled as such everywhere it
    is used.  It is not product evidence and it never counts as a recall number;
    its only job is to answer "can this detector see an impulse, and does it put
    the clip at the right second".
    """
    out = frames.copy()
    out[at: at + length] = 255
    return out


def evaluate_populations(series_quiet, series_busy, fps, cfg):
    """Run ARM Q and ARM B for ONE detector configuration. Returns both counts."""
    q = sum(len(H.detect_series(s, fps, cfg)) for _, s in series_quiet)
    b = sum(len(H.detect_series(s, fps, cfg)) for _, s in series_busy)
    return q, b


def main() -> int:
    neg_arm = "--neg-arm" in sys.argv[1:]
    print("=" * 78)
    print("GATE _hl-auto-highlights-gate   (auto-highlight detector)"
          + ("   [NEGATIVE CONTROL ARM]" if neg_arm else ""))
    print("=" * 78)

    sha = hashlib.sha256(SERIES_NPZ.read_bytes()).hexdigest()
    names, series = load_series()
    on_disk = sorted(p for ext in ("*.mp4", "*.mkv", "*.mov")
                     for p in (REPO / "_main").rglob(ext) if p.stat().st_size > 200_000)
    print(f"corpus cache = _main/_hl-frame-series.npz  sha256 {sha[:16]}...  "
          f"clips={len(names)}  video files on disk={len(on_disk)}")
    if len(names) != len(on_disk):
        print(f"  !! the cached corpus is STALE: {len(names)} cached vs {len(on_disk)} on "
              f"disk.  Re-run _main/_hl-frame-series-dump.py.  This run is NOT valid.")
        return 2

    # The quiet/busy split is taken from the probe's OWN statistic (per-clip p50),
    # never from the detector's output -- selecting the population with the thing
    # under test is how an arm becomes tautological.
    quiet = [(n, s) for n, s in zip(names, series) if float(np.percentile(s, 50)) < 0.05]
    busy = [(n, s) for n, s in zip(names, series) if float(np.percentile(s, 50)) >= 0.05]
    quiet_s = sum(len(s) for _, s in quiet) / FPS
    busy_s = sum(len(s) for _, s in busy) / FPS
    print(f"POPULATION = every *.mp4/*.mkv/*.mov > 200 KB under _main/, one decode each, "
          f"no sampling.  N = {len(names)} clips / {quiet_s + busy_s:.1f} s")
    print(f"WINDOW = one run, all files present on disk at run time; the clip cache is "
          f"re-hashed above and refused if stale")
    print(f"  quiet class (per-clip p50 < 0.05): N = {len(quiet)} clips / {quiet_s:.1f} s")
    print(f"  busy  class (per-clip p50 >= 0.05): N = {len(busy)} clips / {busy_s:.1f} s")
    print(f"ANALYSIS = {GRID_W}x{GRID_H} gray @ {FPS} fps, diff = mean|f[i]-f[i-1]|/255")
    print()
    cfg = H.HighlightConfig()
    print("SHIPPED CONFIGURATION")
    print(f"  abs_floor={cfg.abs_floor} (MEASURED)  rise_threshold={cfg.rise_threshold} "
          f"(DEFAULT, must exceed measured sustained ceiling {H.HIGH_RISE_CEILING_SUSTAINED})")
    print(f"  cooldown_s={cfg.cooldown_s} (DEFAULT)  lookback_s={cfg.lookback_s} "
          f"burst_max_s={cfg.burst_max_s} confirm_s={cfg.confirm_s} "
          f"recovery_ratio={cfg.recovery_ratio}")
    print(f"  pre_roll_s={cfg.pre_roll_s} post_roll_s={cfg.post_roll_s} "
          f"-> clip window {cfg.window_s:.1f} s")
    print()

    # ---------------------------------------------------------------- ARM Q
    print("ARM Q  -- quiet footage must save NOTHING")
    qfired, qdet = 0, None
    for n, s in quiet:
        qdet = H.HighlightDetector(cfg, FPS)
        for v in s:
            qdet.push(float(v))
        qdet.flush()
        qfired += len(qdet.fired)
    check("ARM Q: 0 highlights from the quiet population",
          qfired == 0,
          f"{len(quiet)} clips / {quiet_s:.1f} s of quiet footage -> {qfired} highlights "
          f"(expected 0)")
    if qdet:
        print(f"          last clip's refusal counters: {qdet.counters}")

    # ---------------------------------------------------------------- ARM B
    print()
    print("ARM B  -- sustained activity is NOT a moment")
    bfired, bdet = 0, None
    for n, s in busy:
        bdet = H.HighlightDetector(cfg, FPS)
        for v in s:
            bdet.push(float(v))
        bdet.flush()
        bfired += len(bdet.fired)
    check("ARM B: 0 highlights from the sustained-activity population",
          bfired == 0,
          f"{len(busy)} clips / {busy_s:.1f} s of footage that never stops changing -> "
          f"{bfired} highlights (expected 0)")
    if bdet:
        print(f"          last clip's refusal counters: {bdet.counters} "
              f"(rejected_sustained is the guard doing the work)")

    # ---------------------------------------------------------------- ARM S
    print()
    print("ARM S  -- a genuine spike must save EXACTLY ONE clip (SYNTHETIC event, "
          "real frames)")
    frames = decode_frames(SPIKE_SRC, max_frames=120)
    truth1 = 40
    truth2 = truth1 + 50            # 5.0 s later: INSIDE the 30 s cooldown
    spiked = with_flash(with_flash(frames, truth1), truth2)
    d_spike = diff_of(spiked)
    hits = H.detect_series(d_spike, FPS, cfg)
    n_spike_fired = len(hits)
    check("ARM S: exactly ONE highlight from a spike that occurs twice",
          n_spike_fired == 1,
          f"2 flashes at t={truth1/FPS:.1f}s and t={truth2/FPS:.1f}s, {cfg.cooldown_s:.0f}s "
          f"cooldown -> {n_spike_fired} highlight(s), expected exactly 1")
    if hits:
        h = hits[0]
        err = abs(h.t_peak_s - truth1 / FPS)
        check("ARM S: the highlight is at the FIRST flash, not the second",
              err <= PEAK_TOLERANCE_S and h.t_peak_s < truth2 / FPS,
              f"peak at t={h.t_peak_s:.2f}s, truth {truth1/FPS:.2f}s, error {err:.2f}s "
              f"(tolerance {PEAK_TOLERANCE_S}s)")
        print(f"          {h.reason}")

    # ---------------------------------------------------------------- ARM S2
    # The SAME event, over footage that is already moving.  This arm is the only
    # place `rise_threshold` is load-bearing, and it is the case that decided the
    # default: a threshold of 3.5 refuses it, and refusing it is refusing the
    # feature's own reason to exist (the kill happens DURING the action).
    print()
    print("ARM S2 -- the same spike, over footage that never stops moving")
    busy_frames = decode_frames(BUSY_SRC, max_frames=120)
    busy_base = diff_of(busy_frames)
    spiked_busy = with_flash(busy_frames.copy(), truth1)
    d_busy_spike = diff_of(spiked_busy)
    s2 = H.detect_series(d_busy_spike, FPS, cfg)
    check("ARM S2: exactly ONE highlight from a spike over busy footage",
          len(s2) == 1,
          f"1 flash at t={truth1/FPS:.1f}s over a busy clip (baseline p50 "
          f"{np.percentile(busy_base, 50):.4f}) -> {len(s2)} highlight(s), expected 1")
    if s2:
        check("ARM S2: the highlight is at the flash",
              abs(s2[0].t_peak_s - truth1 / FPS) <= PEAK_TOLERANCE_S,
              f"peak at t={s2[0].t_peak_s:.2f}s, truth {truth1/FPS:.2f}s, "
              f"rise {s2[0].rise:.2f}")

    # ---------------------------------------------------------------- ARM M
    print()
    print("ARM M  -- the guards must be LOAD-BEARING (this is what makes the gate a gate)")
    # Each mutation isolates ONE guard.  Varying a guard while another guard still
    # happens to dominate proves nothing about the one you varied -- that is the
    # trap this gate walked into on its own first run and reported as RED, and it
    # is why the mutating arms below OPEN the competing guard first.

    # M1 -- abs_floor.  Open the rise gate, or the rise refuses quiet first and the
    # floor looks inert for the wrong reason.
    open_rise = H.HighlightConfig.unchecked(rise_threshold=1.0)
    m1_keep = sum(len(H.detect_series(s, FPS, open_rise)) for _, s in quiet)
    m1_drop = sum(len(H.detect_series(s, FPS,
                                      H.HighlightConfig.unchecked(rise_threshold=1.0,
                                                                  abs_floor=0.0)))
                  for _, s in quiet)
    check("ARM M1: abs_floor is load-bearing for ARM Q",
          m1_keep == 0 and m1_drop > 0,
          f"with the rise gate open, quiet footage gives {m1_keep} highlights at "
          f"abs_floor={cfg.abs_floor} and {m1_drop} at abs_floor=0; if the two are "
          f"equal the floor is INERT and ARM Q proves nothing")

    # M2 -- burst_max_s, likewise isolated by opening the rise gate.
    m2_keep = sum(len(H.detect_series(s, FPS, open_rise)) for _, s in busy)
    m2_drop = sum(len(H.detect_series(s, FPS,
                                      H.HighlightConfig.unchecked(rise_threshold=1.0,
                                                                  burst_max_s=600.0)))
                  for _, s in busy)
    check("ARM M2: burst_max_s is load-bearing for ARM B",
          m2_drop > m2_keep,
          f"with the rise gate open, busy footage gives {m2_keep} highlights at "
          f"burst_max_s={cfg.burst_max_s} and {m2_drop} at 600 s; if they are equal the "
          f"burst guard is INERT and 'activity is not a moment' is unsupported")

    # M3 -- cooldown_s.
    m3 = replace(cfg, cooldown_s=0.0)
    m3_fired = len(H.detect_series(d_spike, FPS, m3))
    check("ARM M3: cooldown_s is load-bearing for ARM S",
          m3_fired > n_spike_fired,
          f"cooldown_s 0.0 on the same 2-flash input -> {m3_fired} highlights vs "
          f"{n_spike_fired} with the shipped cooldown; if these are equal the cooldown "
          f"is INERT")

    # M4 -- rise_threshold, tested ONLY where it is the binding guard (ARM S2's input).
    # 3.5 is the value this lane originally shipped.  The gate is what measured that
    # it REFUSES the flash, and moving the default to 3.25 is what fixed it; this
    # arm is the receipt for that decision and will go red if anyone raises it back.
    # 3.5 is ABOVE the measured sustained ceiling, so the constructor allows it --
    # __post_init__ guards the lower edge only, and that asymmetry is deliberate.
    m4 = replace(cfg, rise_threshold=3.5)
    m4_fired = len(H.detect_series(d_busy_spike, FPS, m4))
    check("ARM M4: rise_threshold is load-bearing on a spike over busy footage",
          m4_fired < len(s2),
          f"rise_threshold 3.5 -> {m4_fired} highlight(s) vs {len(s2)} at the shipped "
          f"{cfg.rise_threshold}; the default sits in a "
          f"{3.36 - H.HIGH_RISE_CEILING_SUSTAINED:.2f}-wide measured gap between the "
          f"sustained ceiling ({H.HIGH_RISE_CEILING_SUSTAINED}) and the rise of the "
          f"flash (3.36, N=1)")

    # ------------------------------------------------------- INERTNESS DISCLOSURE
    # Not an arm, a check on the SHIPPED configuration: a default that does nothing
    # on the whole measured population is a fact, and it is printed every run
    # instead of being discovered by the next reader.  This is the same shape as S2
    # of the deleted spec, where the entire rate came from MIN_GAP_S alone.
    sweep = {rt: sum(len(H.detect_series(s, FPS,
                                         H.HighlightConfig.unchecked(rise_threshold=rt)))
                     for _, s in busy) for rt in (2.0, 2.5, 3.0, 3.5)}
    inert = len(set(sweep.values())) == 1
    print()
    print(f"DISCLOSURE -- rise_threshold sweep over the busy population (shipped config "
          f"otherwise unchanged): {sweep}")
    print(f"  {'INERT' if inert else 'load-bearing'} on this population; the shipped "
          f"default's real work is done by abs_floor (quiet) and burst_max_s (busy). "
          f"See PROVENANCE['inertness_note'].")

    # ------------------------------------------------------- NEGATIVE CONTROL
    # THE arm that says the gate can fail.  Same assertions, same code path, a
    # detector with its guards reverted.  If ARM Q and ARM B stay GREEN against the
    # mutant, then this gate has been green for a reason that has nothing to do
    # with the guards -- which is precisely the S3 defect that killed the previous
    # highlights design.  Exits 3 (distinct from 1 = a real arm failed) because
    # "the gate cannot fail" is a different failure from "the detector is wrong".
    print()
    print("NEGATIVE CONTROL -- the SAME ARM Q / ARM B assertions, against a detector "
          "with its guards reverted")
    mutant = H.HighlightConfig.unchecked(abs_floor=0.0, burst_max_s=600.0,
                                         rise_threshold=1.0)
    m_q, m_b = evaluate_populations(quiet, busy, FPS, mutant)
    print(f"  mutant (abs_floor=0.0, burst_max_s=600 s, rise_threshold=1.0): "
          f"ARM Q would report {m_q} highlights (assertion is '== 0'), "
          f"ARM B would report {m_b} (assertion is '== 0')")
    if neg_arm:
        ok = (m_q > 0 and m_b > 0)
        print(f"  [{'PASS' if ok else 'FAIL'}] the gate is RED against the mutant: a gate "
              f"that cannot go red is not a gate")
        return 0 if ok else 3
    print("  (run with --neg-arm to make this an enforced exit-3 check)")

    # ---------------------------------------------------------------- verdict
    print()
    print("-" * 78)
    failed = [n for n, ok, _ in results if not ok]
    for n, ok, d in results:
        print(f"{'PASS' if ok else 'FAIL'}  {n}")
    print("-" * 78)
    if failed:
        print(f"VERDICT FAIL -- {len(failed)} arm(s) red: {', '.join(failed)}")
        return 1
    print(f"VERDICT PASS -- all {len(results)} arms green, including "
          f"{sum(1 for n, _, _ in results if n.startswith('ARM M'))} mutation arms that "
          f"prove the guards are load-bearing")
    print("NOT PROVEN BY THIS GATE: recall. There is no labelled gameplay corpus on this "
          "box (N = 0), so no number here is a precision/recall figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())