"""Oracle for worker/punctuation_prosody.py.

Modes
  --measure   frame features on the fixture WAVs -> gap histogram + band clustering
  (default)   >=12 behaviour arms against the real module, rc=0 on success
  --neg-arm   mutate a COPY of the module and demand rc=1 + "NEG-ARM: PASS"

Pure numpy on fixture WAVs. No model load, no app, no audio device.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

HOP_MS = 20.0
WIN_MS = 25.0
TARGET_SR = 16000  # worker clock: chunk_samples 8960 @16k = 560 ms
F0_MIN, F0_MAX = 60.0, 400.0
PAUSE_FLOOR_MS = 80.0


# ---------------------------------------------------------------- wav decode


def read_wav(path):
    """Minimal RIFF reader: PCM 8/16/32 + IEEE float 32. Returns (float64 mono, sr)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file: %s" % path)
    pos = 12
    fmt = None
    data = None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = int.from_bytes(raw[pos + 4:pos + 8], "little")
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError("missing fmt/data chunk: %s" % path)
    tag = int.from_bytes(fmt[0:2], "little")
    channels = int.from_bytes(fmt[2:4], "little")
    sr = int.from_bytes(fmt[4:8], "little")
    bits = int.from_bytes(fmt[14:16], "little")
    if tag == 0xFFFE and len(fmt) >= 26:  # WAVE_FORMAT_EXTENSIBLE
        tag = int.from_bytes(fmt[24:26], "little")
    if tag == 1 and bits == 16:
        x = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768.0
    elif tag == 1 and bits == 32:
        x = np.frombuffer(data, dtype="<i4").astype(np.float64) / 2147483648.0
    elif tag == 1 and bits == 8:
        x = (np.frombuffer(data, dtype="u1").astype(np.float64) - 128.0) / 128.0
    elif tag == 3 and bits == 32:
        x = np.frombuffer(data, dtype="<f4").astype(np.float64)
    elif tag == 3 and bits == 64:
        x = np.frombuffer(data, dtype="<f8").astype(np.float64)
    else:
        raise ValueError("unsupported wav encoding tag=%d bits=%d" % (tag, bits))
    if channels > 1:
        x = x[: (len(x) // channels) * channels].reshape(-1, channels).mean(axis=1)
    return x, sr


def resample(x, sr_in, sr_out=TARGET_SR):
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / float(sr_in)))
    src = np.arange(len(x), dtype=np.float64)
    dst = np.arange(n_out, dtype=np.float64) * (sr_in / float(sr_out))
    return np.interp(dst, src, x)


# ---------------------------------------------------------------- features


def frame_features(x, sr):
    """hop 20 ms / win 25 ms -> dict of arrays: t, rms, rms_db, zcr, f0, voiced."""
    hop = int(round(sr * HOP_MS / 1000.0))
    win = int(round(sr * WIN_MS / 1000.0))
    if len(x) < win:
        return None
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    fr = x[idx]                                    # (n, win)
    rms = np.sqrt(np.mean(fr * fr, axis=1))
    peak = float(np.max(np.abs(x))) or 1.0
    rmsn = rms / peak
    zcr = np.mean(np.abs(np.diff(np.signbit(fr).astype(np.int8), axis=1)), axis=1)
    t = (hop * np.arange(n) + win / 2.0) / sr

    # noise floor: median of the quietest 10 % of frames (min is a single sample).
    q = np.sort(rmsn)
    floor = float(np.median(q[: max(1, len(q) // 10)]))
    gate = max(floor * 3.0, 0.02)  # 0.02 * peak == 0.02 in normalised units

    f0 = np.zeros(n)
    voiced = np.zeros(n, dtype=bool)
    min_lag = max(1, int(sr / F0_MAX))
    max_lag = int(sr / F0_MIN)
    if max_lag + 2 < win:
        w = np.hanning(win)
        spec = np.fft.rfft(fr * w, n=2 * win, axis=1)
        ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :win]
        ac0 = ac[:, :1].copy()
        ac0[ac0 <= 0] = 1e-12
        acn = ac / ac0
        for i in range(n):
            if rmsn[i] < gate:
                continue
            seg = acn[i, min_lag:max_lag + 1]
            k = int(np.argmax(seg))
            if seg[k] < 0.30:  # aperiodic / unvoiced
                continue
            lag = min_lag + k
            # parabolic refinement around the peak
            if 0 < k < len(seg) - 1:
                a, b, c = seg[k - 1], seg[k], seg[k + 1]
                den = a - 2 * b + c
                d = 0.5 * (a - c) / den if den != 0 else 0.0
                if abs(d) <= 1.0:
                    lag = lag + d
            f0[i] = sr / lag
            voiced[i] = True
    return {
        "t": t, "rms": rmsn, "rms_db": 20.0 * np.log10(np.maximum(rmsn, 1e-9)),
        "zcr": zcr, "f0": f0, "voiced": voiced,
        "gate": gate, "floor": floor, "peak": peak, "hop": hop, "sr": sr,
    }


def gaps_from(feats):
    """Runs below gate lasting >= PAUSE_FLOOR_MS. Returns list of dicts."""
    hop_ms = HOP_MS
    below = feats["rms"] < feats["gate"]
    out = []
    i, n = 0, len(below)
    while i < n:
        if below[i]:
            j = i
            while j + 1 < n and below[j + 1]:
                j += 1
            ms = (j - i + 1) * hop_ms
            if ms >= PAUSE_FLOOR_MS:
                t0 = feats["t"][i] - WIN_MS / 2000.0
                t1 = feats["t"][j] + WIN_MS / 2000.0
                out.append({"start": t0, "end": t1, "ms": ms, "i0": i, "i1": j})
            i = j + 1
        else:
            i += 1
    return out


def _slope(xs, ys):
    if len(xs) < 2:
        return None
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    xs = xs - xs.mean()
    den = float(np.sum(xs * xs))
    if den <= 0:
        return None
    return float(np.sum(xs * (ys - ys.mean())) / den)


def pre_gap_shape(feats, gap, pre_ms=150.0):
    """Slopes over the pre_ms window ending at the gap start.

    Frames that are already below the gate are excluded: including them makes
    every slope a measurement of the silence ramp, not of the speech.
    """
    t0 = gap["start"] - pre_ms / 1000.0
    t1 = gap["start"]
    sel = (feats["t"] >= t0) & (feats["t"] < t1) & (feats["rms"] >= feats["gate"])
    n_sel = int(np.sum(sel))
    if n_sel < 2:
        return {"f0_slope": None, "rms_slope": None, "f0_delta_st": None,
                "pre_frames": n_sel}
    tt = feats["t"][sel]
    # F0 in semitones re 100 Hz, voiced frames only; >=5 frames or the fit is noise.
    v = sel & feats["voiced"] & (feats["f0"] > 0)
    f0_slope = None
    f0_delta = None
    nv = int(np.sum(v))
    if nv >= 5:
        st = 12.0 * np.log2(feats["f0"][v] / 100.0)
        s = _slope(feats["t"][v], st)
        f0_slope = None if s is None else s
        k = max(1, nv // 3)
        f0_delta = float(np.median(st[-k:]) - np.median(st[:k]))
    rs = _slope(tt, feats["rms_db"][sel])
    return {"f0_slope": f0_slope, "rms_slope": rs, "f0_delta_st": f0_delta,
            "pre_frames": n_sel}


def label_slope(v, dead=0.5):
    if v is None:
        return "unknown"
    if v > dead:
        return "rising"
    if v < -dead:
        return "falling"
    return "flat"


def band(ms):
    if ms < 250.0:
        return "short"
    if ms < 600.0:
        return "clause"
    return "sentence"


FIXTURES = [
    ("_main/pt-br-sample.wav", None),
    ("_main/fixtures/stack-compare/unified-tts/ptbr-tts-01.wav", "ptbr-tts-01"),
    ("_main/fixtures/stack-compare/unified-tts/ptbr-tts-02.wav", "ptbr-tts-02"),
    ("_main/fixtures/stack-compare/unified-tts/ptbr-tts-03.wav", "ptbr-tts-03"),
    ("_main/fixtures/stack-compare/unified-tts/enus-tts-01.wav", "enus-tts-01"),
    ("_main/fixtures/stack-compare/unified-tts/enus-tts-02.wav", "enus-tts-02"),
    ("_main/live-sample-cable-input.wav", None),
]


def load_refs():
    p = os.path.join(HERE, "fixtures", "stack-compare", "unified-tts", "reference.json")
    with open(p, "r", encoding="utf-8") as fh:
        return {c["id"]: c for c in json.load(fh)["clips"]}


def _pos_fraction(gap, edge):
    """Where the gap sits inside the speech span, 0..1 (word-time proxy)."""
    span0 = edge["lead_ms"] / 1000.0
    span1 = edge["dur_s"] - edge["tail_ms"] / 1000.0
    if span1 <= span0:
        return 0.0
    return (gap["start"] - span0) / (span1 - span0)


def edge_silence(feats, dur_s):
    """Leading / trailing silence in ms, measured on the same gate."""
    above = np.nonzero(feats["rms"] >= feats["gate"])[0]
    if len(above) == 0:
        return {"lead_ms": dur_s * 1000.0, "tail_ms": dur_s * 1000.0, "dur_s": dur_s}
    half_win = WIN_MS / 2000.0
    lead = float(feats["t"][above[0]] - half_win) * 1000.0
    tail = (dur_s - float(feats["t"][above[-1]] + half_win)) * 1000.0
    return {"lead_ms": max(0.0, lead), "tail_ms": max(0.0, tail), "dur_s": dur_s}


def measure(argv):
    refs = load_refs()
    total = 0
    all_gaps = []
    edges_of = {}
    print("%-26s %6s %6s %5s %5s %6s %6s %s" % (
        "file", "dur_s", "gate", "n", "speech", "lead", "tail", "gaps_ms"))
    for rel, rid in FIXTURES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print("%-26s MISSING" % rel)
            continue
        x, sr = read_wav(path)
        x = resample(x, sr)
        f = frame_features(x, TARGET_SR)
        gs = gaps_from(f)
        edges_of[rel] = edge_silence(f, len(x) / TARGET_SR)
        # drop leading/trailing silence: only gaps flanked by speech matter
        inner = [g for g in gs if g["start"] > 0.05 and g["end"] < len(x) / TARGET_SR - 0.05]
        total += len(inner)
        for g in inner:
            sh = pre_gap_shape(f, g)
            g = dict(g)
            g.update(sh)
            g["band"] = band(g["ms"])
            g["f0_label"] = label_slope(sh["f0_delta_st"])
            g["rms_label"] = label_slope(sh["rms_slope"], 0.0)
            g["file"] = rel
            g["rid"] = rid
            all_gaps.append(g)
        print("%-26s %6.2f %6.3f %5d %5.2f %6.0f %6.0f %s" % (
            rel.replace("_main/", "").replace("fixtures/stack-compare/unified-tts/", ""),
            len(x) / TARGET_SR, f["gate"], len(inner), float(np.mean(f["voiced"])),
            edges_of[rel]["lead_ms"], edges_of[rel]["tail_ms"],
            " ".join("%.0f" % g["ms"] for g in inner)))

    print("\n--- gap histogram (all fixtures, inner gaps) ---")
    edges = [80, 120, 160, 200, 250, 300, 400, 500, 600, 800, 1000, 1500, 3000]
    for lo, hi in zip(edges, edges[1:]):
        n = sum(1 for g in all_gaps if lo <= g["ms"] < hi)
        print("  %4d-%4d ms : %2d %s" % (lo, hi, n, "#" * n))
    print("  total inner gaps: %d" % total)

    print("\n--- per gap: t, ms, band, pre-gap f0 delta (st), f0 slope (st/s), rms slope (dB/s) ---")
    for g in all_gaps:
        print("  %-14s %6.2fs %6.0f ms %-8s f0=% -6s %-7s rms=% -6s %-7s" % (
            os.path.basename(g["file"])[:14], g["start"], g["ms"], g["band"],
            ("%.2f" % g["f0_delta_st"]) if g["f0_delta_st"] is not None else "n/a",
            g["f0_label"],
            ("%.1f" % g["rms_slope"]) if g["rms_slope"] is not None else "n/a",
            g["rms_label"]))

    print("\n--- clustering vs authored reference text ---")
    by_file = {}
    for g in all_gaps:
        by_file.setdefault(g["file"], []).append(g)
    # pt-br-sample has no authored punctuation, but ASR-TRUTH.md section C shows
    # the phrase break the model itself heard: "segunda-feira. Os moradores".
    extra_split = {"_main/pt-br-sample.wav": " os moradores"}
    radio_text = None
    try:
        with open(os.path.join(HERE, "fixtures", "stack-compare", "reference.json"),
                  "r", encoding="utf-8") as fh:
            radio_text = json.load(fh)["clips"][0]["reference"]
    except Exception:
        pass
    table = {b: {"comma": 0, "period": 0, "none": 0} for b in ("short", "clause", "sentence")}
    comma_recall = {}
    marks_out = {}
    for rel, rid in FIXTURES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        if rid is not None:
            raw = refs[rid]["reference_raw"]
            n_comma, n_period = raw.count(","), raw.count(".")
        elif rel in extra_split and radio_text:
            raw = radio_text
            n_comma, n_period = 0, 1  # the period is the one ASR-TRUTH documents
        else:
            continue
        marks = []
        acc = 0
        for ch in raw:
            if ch in ",.?!;:":
                marks.append((ch, acc))
            elif not ch.isspace():
                acc += 1
        if rel in extra_split:
            head = raw.split(extra_split[rel])[0]
            marks.append((".", sum(1 for ch in head if not ch.isspace())))
        total_letters = float(max(1, acc))
        # a period at the very end is the trailing silence, measured on its own
        frac = {(ch, pos / total_letters) for ch, pos in marks
                if pos / total_letters < 0.98}

        gs = by_file.get(rel, [])
        marks_out.setdefault(rel, []).extend(sorted(frac, key=lambda m: m[1]))
        clause_hits = 0
        for g in gs:
            fr = _pos_fraction(g, edges_of[rel])
            near = {(ch, p) for ch, p in frac if abs(fr - p) <= 0.10}
            kind = ("comma" if any(ch == "," for ch, _ in near) else
                    "period" if any(ch in ".!?" for ch, _ in near) else "none")
            table[g["band"]][kind] += 1
            if kind == "comma" and g["band"] == "clause":
                clause_hits += 1
        comma_recall[rid or rel] = (clause_hits, n_comma)
        print("  %-12s ref: %d comma, %d period | measured: %d short, %d clause, %d sentence"
              % (rid or os.path.basename(rel), n_comma, n_period,
                 sum(1 for g in gs if g["band"] == "short"),
                 sum(1 for g in gs if g["band"] == "clause"),
                 sum(1 for g in gs if g["band"] == "sentence")))

    print("\n  band        n  at-comma-pos  at-period-pos  no mark near")
    for b in ("short", "clause", "sentence"):
        t = table[b]
        print("  %-9s %3d  %11d  %13d  %12d"
              % (b, t["comma"] + t["period"] + t["none"], t["comma"], t["period"], t["none"]))

    hit = sum(v[0] for v in comma_recall.values())
    total = sum(v[1] for v in comma_recall.values())
    print("\n  COMMA RECALL: %d of %d authored commas produced a 250-600 ms gap"
          " (%s)" % (hit, total, ", ".join("%s %d/%d" % (k, v[0], v[1])
                                           for k, v in comma_recall.items())))
    print("  CLAUSE PRECISION: %d of %d clause-band gaps sit at a comma position"
          % (table["clause"]["comma"],
             table["clause"]["comma"] + table["clause"]["period"] + table["clause"]["none"]))
    print("\n  SENTENCE PRECISION: %d of %d sentence-band gaps sit at a period position"
          % (table["sentence"]["period"],
             table["sentence"]["comma"] + table["sentence"]["period"] + table["sentence"]["none"]))

    print("\n  per authored mark -> is there a gap of the RIGHT band within +-0.10 of its"
          " expected time fraction?")
    print("  %-16s %-5s %7s %11s %8s %12s  %s"
          % ("file", "mark", "expect", "band-gap ms", "delta", "nearest-any", "verdict"))
    ok_c = n_c = ok_p = n_p = 0
    for rel, _ in FIXTURES:
        gs = by_file.get(rel, [])
        if not gs:
            continue
        for ch, p in marks_out.get(rel, []):
            want = "clause" if ch == "," else "sentence"
            cand = [g for g in gs
                    if g["band"] == want and abs(_pos_fraction(g, edges_of[rel]) - p) <= 0.10]
            anyg = min(gs, key=lambda g: abs(_pos_fraction(g, edges_of[rel]) - p))
            hit = bool(cand)
            g = cand[0] if hit else None
            if ch == ",":
                n_c += 1
                ok_c += hit
            else:
                n_p += 1
                ok_p += hit
            print("  %-16s %-5s %7.3f %11s %8s %12.0f  %s"
                  % (os.path.basename(rel)[:16], ch, p,
                     ("%.0f" % g["ms"]) if g else "none",
                     ("%+.3f" % (_pos_fraction(g, edges_of[rel]) - p)) if g else "-",
                     anyg["ms"], "hit" if hit else "MISS"))
    print("  -> commas with a 250-600 ms gap at their position: %d/%d ;"
          " periods with a >=600 ms gap: %d/%d" % (ok_c, n_c, ok_p, n_p))

    print("\n  SENTENCE BAND >=600 ms per file:")
    for rel, rid in FIXTURES:
        e = edges_of.get(rel)
        if e is None:
            continue
        sents = [g for g in by_file.get(rel, []) if g["band"] == "sentence"]
        print("    %-26s inner: %-24s trailing silence %.0f ms"
              % (os.path.basename(rel), [int(g["ms"]) for g in sents], e["tail_ms"]))

    print("\n--- slope vs band ---")
    for b in ("short", "clause", "sentence"):
        sub = [g for g in all_gaps if g["band"] == b]
        clean = [g for g in sub if "live-sample" not in g["file"]]
        rise = sum(1 for g in clean if g["f0_label"] == "rising")
        fall = sum(1 for g in clean if g["f0_label"] == "falling")
        flat = sum(1 for g in clean if g["f0_label"] == "flat")
        unk = sum(1 for g in clean if g["f0_label"] == "unknown")
        erise = sum(1 for g in clean if g["rms_label"] == "rising")
        efall = sum(1 for g in clean if g["rms_label"] == "falling")
        eflat = sum(1 for g in clean if g["rms_label"] == "flat")
        eunk = sum(1 for g in clean if g["rms_label"] == "unknown")
        print("  %-8s clean n=%2d | f0 rising=%2d falling=%2d flat=%2d unknown=%2d"
              " | rms rising=%d falling=%2d flat=%d unknown=%d"
              % (b, len(clean), rise, fall, flat, unk, erise, efall, eflat, eunk))


# ---------------------------------------------------------------- arms

MODULE_REL = os.path.join("worker", "punctuation_prosody.py")

# The two live strings the panel actually carried (given by the owner's brief).
LIVE_A = "What's, crazy is, that Astro at the."
LIVE_B = "What's, crazy is, that Astro at the highest thinking budget also."

# Measured on _main/pt-br-sample.wav: one 1100 ms inner gap, at the sentence
# boundary after "segunda-feira" (13 of 25 words = 52 % into the clip).
RADIO = ("radio anunciou que a ponte sobre o rio vai ser interditada na proxima "
         "segunda feira os moradores precisam de um caminho alternativo para "
         "chegar ao trabalho")
RADIO_GAPS = [90] * 14 + [1100] + [90] * 10   # boundary 14 == after "feira"

# Measured on ptbr-tts-01.wav: the 360 ms clause gap sits at the authored comma
# after "sexta-feira".
TTS01 = "a reuniao de amanha foi adiada para sexta feira porque o diretor"
TTS01_GAPS = [90] * 8 + [360] + [90] * 2


def _arm(name, got, want):
    return (name, got == want, "got %r want %r" % (got, want))


def arms(mod):
    """Every arm is (name, ok, detail). Buys nothing from the network or devices."""
    n = mod.normalise
    out = []

    # -- identity: no audio evidence, no invention -------------------------
    out.append(_arm("identity_no_pauses_live", n(LIVE_A, []), LIVE_A))
    out.append(_arm("identity_none_pauses_live", n(LIVE_A, None), LIVE_A))
    out.append(_arm("identity_no_pauses_live_b", n(LIVE_B, []), LIVE_B))
    out.append(_arm("identity_empty_text", n("", [{"ms": 5000}]), ""))
    out.append(_arm("identity_pauses_shorter_than_text",
                    n("a, b c, d", [{"ms": 60}]), "a b c, d"))

    # -- drop: unproven commas only, and only below the floor ---------------
    out.append(_arm("drop_junk_commas_live_a",
                    n(LIVE_A, [{"ms": 60}, {"ms": 90}, {"ms": 40},
                               {"ms": 70}, {"ms": 60}, {"ms": 50}]),
                    "What's crazy is that Astro at the."))
    out.append(_arm("drop_junk_commas_live_b",
                    n(LIVE_B, [{"ms": 55}] * 8),
                    "What's crazy is that Astro at the highest thinking budget also."))
    out.append(_arm("drop_floor_is_inclusive",
                    n("a, b, c", [{"ms": 199}, {"ms": 201}]), "a b, c"))
    out.append(_arm("keep_question_mark",
                    n("Really? yes", [{"ms": 40}]), "Really? yes"))
    out.append(_arm("keep_period_drop_comma",
                    n("Done, next. ok", [{"ms": 40}, {"ms": 300}]), "Done next. ok"))

    # -- add: measured bands ------------------------------------------------
    out.append(_arm("add_comma_at_measured_360ms", n(TTS01, TTS01_GAPS),
                    "a reuniao de amanha foi adiada para sexta feira, porque o diretor"))
    out.append(_arm("add_period_at_measured_1100ms", n(RADIO, RADIO_GAPS),
                    RADIO.replace("segunda feira os", "segunda feira. os")))
    out.append(_arm("band_edges_249_250_599_600",
                    n("a b c d e", [{"ms": 249}, {"ms": 250},
                                    {"ms": 599}, {"ms": 600}]),
                    "a b, c, d. e"))
    out.append(_arm("no_add_below_clause_floor",
                    n("a b", [{"ms": 249}]), "a b"))
    out.append(_arm("no_double_marks",
                    n("a, b c", [{"ms": 700}, {"ms": 90}]), "a, b c"))
    out.append(_arm("no_mark_before_existing_mark",
                    n("a , b", [{"ms": 700}]), "a , b"))
    out.append(_arm("numeric_pause_entries", n("a b", [350]), "a, b"))
    out.append(_arm("unknown_pause_entry_is_identity",
                    n("a, b", [{"f0_slope": 4.0}]), "a, b"))
    out.append(_arm("non_list_pauses_is_identity",
                    n("a, b", {"0": {"ms": 700}}), "a, b"))
    out.append(_arm("mark_goes_inside_closing_quote",
                    n('ele disse "pronto" agora',
                      [{"ms": 90}, {"ms": 90}, {"ms": 700}]),
                    'ele disse "pronto." agora'))
    out.append(_arm("comma_dropped_inside_quote",
                    n('"Sim," ele disse',
                      [{"ms": 60}, {"ms": 90}]),
                    '"Sim" ele disse'))

    # -- trailing boundary --------------------------------------------------
    out.append(_arm("trailing_period_from_silence",
                    n("the end", [{"ms": 90}, {"ms": 800}]), "the end."))
    out.append(_arm("trailing_never_doubles",
                    n("the end.", [{"ms": 90}, {"ms": 800}]), "the end."))
    out.append(_arm("trailing_needs_its_own_entry",
                    n("the end", [{"ms": 90}]), "the end"))

    # -- f0 is carried but must not invent '?' ------------------------------
    out.append(_arm("f0_rising_does_not_make_question",
                    n("a b", [{"ms": 800, "f0_slope": 9.0, "rms_slope": -4.0}]),
                    "a. b"))

    # -- stability ----------------------------------------------------------
    once = n(RADIO, RADIO_GAPS)
    out.append(_arm("idempotent", n(once, RADIO_GAPS), once))
    out.append(_arm("whitespace_preserved",
                    n("a  b,  c\nd", []), "a  b,  c\nd"))
    out.append(_arm("whitespace_preserved_on_edit",
                    n("a  b,  c", [{"ms": 90}, {"ms": 50}]), "a  b  c"))
    out.append(_arm("standalone_mark_dropped_no_double_space",
                    n("a , b", [{"ms": 90}, {"ms": 50}]), "a b"))
    return out


def load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_fixtures():
    """Drift guard: the gap numbers the receipt quotes must still come out of the
    feature pipeline. Nothing else in the oracle touches frame_features/gaps_from,
    so without this a change there would leave every arm green."""
    path = os.path.join(ROOT, "_main/fixtures/stack-compare/unified-tts/ptbr-tts-01.wav")
    x, sr = read_wav(path)
    dur = len(x) / float(sr)
    f = frame_features(resample(x, sr), TARGET_SR)
    got = [int(g["ms"]) for g in gaps_from(f)
           if g["start"] > 0.05 and g["end"] < dur - 0.05]
    want = [100, 80, 80, 100, 180, 360, 80, 120]
    return ("measured_gaps_ptbr_tts_01", got == want, "got %r want %r" % (got, want))


def run_all(verbose=True):
    mod = load_module(os.path.join(ROOT, MODULE_REL), "punct_prosody_under_test")
    results = arms(mod) + [check_fixtures()]
    bad = [r for r in results if not r[1]]
    if verbose:
        for name, ok, detail in results:
            print("%-38s %s%s" % (name, "PASS" if ok else "FAIL",
                                  "" if ok else "  " + detail))
        print("\n%d arms, %d pass, %d fail" % (len(results), len(results) - len(bad), len(bad)))
    return 0 if not bad else 1


MUTATIONS = [
    ("drop_floor_zero", "DROP_FLOOR_MS = 200.0", "DROP_FLOOR_MS = 0.0"),
    ("clause_floor_zero", "CLAUSE_MIN_MS = 250.0", "CLAUSE_MIN_MS = 0.0"),
    ("sentence_floor_250", "SENTENCE_MIN_MS = 600.0", "SENTENCE_MIN_MS = 250.0"),
]


def neg_arm():
    """Mutate a COPY of the module; every mutation must fail at least one arm."""
    src_path = os.path.join(ROOT, MODULE_REL)
    with open(src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    bad = 0
    for name, old, new in MUTATIONS:
        if old not in src:
            print("%-38s BROKEN  mutation target not found: %r" % (name, old))
            bad += 1
            continue
        mutated = src.replace(old, new, 1)
        assert mutated != src
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "punct_mutant.py")
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(mutated)
            try:
                mod = load_module(dst, "punct_mutant_" + name)
            except Exception as exc:  # a mutant that does not import is not a red arm
                print("%-38s BROKEN  mutant import failed: %s" % (name, exc))
                bad += 1
                continue
        res = arms(mod)
        failed = [r for r in res if not r[1]]
        caught = bool(failed)
        print("%-38s %s  %d/%d arms red%s" % (
            name, "RED as required" if caught else "SURVIVED", len(failed), len(res),
            ("  first: " + failed[0][0]) if failed else ""))
        if not caught:
            bad += 1
    if bad:
        print("\nNEG-ARM: FAIL  %d mutation(s) did not turn the oracle red" % bad)
        return 0
    print("\nNEG-ARM: PASS")
    return 1


def main(argv):
    if "--measure" in argv:
        measure(argv)
        return 0
    if "--neg-arm" in argv:
        return neg_arm()
    return run_all()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
