#!/usr/bin/env python
"""Known-answer gate for `worker/discord_streams.py` -- per-speaker transcription.

WHY THIS GATE EXISTS
--------------------
The owner asked for each voice in a Discord call to be transcribed on its own
stream. The capture side writes `<user>/<start_ms>.pcm`; the worker transcribes
each file tail separately. Two things can silently be wrong and both produce
plausible text:

  1. CROSSTALK -- two speakers' audio lands on one ASR input (a wiring bug), and
     the transcript is a soup of both languages that still "reads".
  2. CLOCK DRIFT -- Discord sends nothing while a user is silent, so a sample
     count divided by 16 kHz drifts by every pause. The caption then carries a
     timestamp minutes away from the voice it belongs to.

THE KNOWN ANSWER IS BUILT, NOT INFERRED
---------------------------------------
`_main/pt-br-sample.wav` and `_main/en-us-sample.wav` are the SAME announcement
in Portuguese and English (measured, the engine's own transcript of each):
    PT: "O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima
         segunda-feira. Os moradores precisam de um caminho alternativo..."
    EN: "The radio announced that the bridge over the river will be closed next
         Monday. Residents need an alternative route..."
Two different voices, same meaning, disjoint vocabularies -- so crosstalk is
detectable by WORD, not by a model's opinion.

The fixture is a real Discord tree:
  * speaker A = PT, split into TWO segment files with a 6.0 s WALL-CLOCK gap that
    exists only on the clock (no packets, exactly like a muted stretch),
  * speaker B = EN, starting 2.0 s after A's first packet,
  * one `packet` row per 20 ms with `t_ms`, the same index the writer emits.

Assertions: two speaker ids; A's text is Portuguese and has none of B's English
keywords (and vice versa); A's post-gap lines start at >= 13.5 s (7.5 s of audio
+ 6.0 s of silence), NOT contiguous at 7.5 s; B's first line starts near 2.0 s;
each speaker keeps ONE `discord/voice:speaker-N` source.

NEGATIVE ARM
------------
`--neg-arm` merges both speakers' audio under ONE user id (the split is lost).
The positive assertions must then FAIL. Per house convention the neg-arm returns
rc=1 when it catches the mutant, rc=0 when the mutant goes undetected.

Usage:
    python _main/discord-streams-oracle.py             # positive (rc=0 pass)
    python _main/discord-streams-oracle.py --neg-arm   # rc=1 when caught
    python _main/discord-streams-oracle.py --keep      # leave the fixture tree
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, "worker", "discord_streams.py")
PT_SAMPLE = os.path.join(HERE, "pt-br-sample.wav")
EN_SAMPLE = os.path.join(HERE, "en-us-sample.wav")

RATE = 16000
PACKET = 320                    # 20 ms at 16 kHz
EPOCH_MS = 1_700_000_000_000
GAP_MS = 6000
A_PART_S = 7.5
B_DELAY_MS = 2000
TMP_ROOT = r"I:/cc-tmp"

PT_WORDS = ("rádio", "ponte", "rio", "segunda", "moradores", "caminho", "trabalho")
EN_WORDS = ("bridge", "monday", "residents", "alternative", "route", "closed")


def load_16k(path):
    import librosa
    with wave.open(path) as handle:
        rate = handle.getframerate()
        data = np.frombuffer(handle.readframes(handle.getnframes()),
                             dtype=np.int16).astype(np.float32) / 32768.0
    return librosa.resample(data, orig_sr=rate, target_sr=RATE)


def write_stream(directory, user_id, parts):
    """parts = [(started_at_ms, np.int16 samples)] -> one file per part."""
    folder = os.path.join(directory, user_id)
    os.makedirs(folder, exist_ok=True)
    for started_ms, samples in parts:
        base = os.path.join(folder, "%d" % started_ms)
        with open(base + ".pcm", "wb") as pcm:
            pcm.write(samples.astype("<i2").tobytes())
        with open(base + ".jsonl", "w", encoding="utf-8") as index:
            index.write(json.dumps({
                "type": "segment", "user_id": user_id, "ssrc": 1,
                "started_at_ms": started_ms, "sample_rate": RATE,
                "channels": 1, "format": "s16le",
            }) + "\n")
            for seq, offset in enumerate(range(0, samples.size, PACKET)):
                chunk = samples[offset:offset + PACKET]
                index.write(json.dumps({
                    "type": "packet", "t_ms": started_ms + seq * 20, "seq": seq,
                    "user_id": user_id, "samples": int(chunk.size),
                    "pcm_bytes": int(chunk.size * 2),
                }) + "\n")
            index.write(json.dumps({
                "type": "close", "t_ms": started_ms + samples.size * 1000 // RATE,
                "duration_ms": samples.size * 1000 // RATE,
                "samples": int(samples.size), "pcm_bytes": int(samples.size * 2),
            }) + "\n")


def build_tree(directory, mutate=False):
    pt = (load_16k(PT_SAMPLE) * 32767.0).astype(np.int16)
    en = (load_16k(EN_SAMPLE) * 32767.0).astype(np.int16)
    split = int(A_PART_S * RATE)
    a1, a2 = pt[:split], pt[split:]
    a2_start = EPOCH_MS + GAP_MS + int(round(a1.size * 1000 / RATE))
    if mutate:
        # NEG-ARM: the split is lost -- both voices under one user id.
        write_stream(directory, "100", [(EPOCH_MS, a1), (a2_start, a2)])
        write_stream(directory, "100", [(EPOCH_MS + B_DELAY_MS, en)])
        return
    write_stream(directory, "100", [(EPOCH_MS, a1), (a2_start, a2)])
    write_stream(directory, "200", [(EPOCH_MS + B_DELAY_MS, en)])


def run_worker(directory):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hidden_launch", os.path.join(HERE, "hidden-launch.py"))
    hidden = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hidden)
    argv = [sys.executable, "-u", WORKER, "--pcm-dir", directory,
            "--once", "--quiet", "--threads", "2"]
    rc, out, err = hidden.run(argv, capture=True, timeout=900)
    events = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") == "caption":
            events.append(row)
    return rc, events, err


def group(events):
    speakers = {}
    for event in events:
        uid = str(event.get("speakerId"))
        item = speakers.setdefault(uid, {"source": event.get("source"),
                                         "label": event.get("speaker"),
                                         "texts": [], "starts": []})
        item["texts"].append(str(event.get("text") or ""))
        item["starts"].append(float(event.get("start") or 0.0))
        if event.get("source") != item["source"]:
            item["source_changed"] = True
    return speakers


def check(events):
    """Return (ok, [failure lines], facts)."""
    failures = []
    speakers = group(events)
    facts = {"speakers": {uid: {"label": item["label"], "source": item["source"],
                                "lines": len(item["texts"]),
                                "first_start": min(item["starts"]) if item["starts"] else None,
                                "last_start": max(item["starts"]) if item["starts"] else None,
                                "text": " ".join(item["texts"])}
                         for uid, item in speakers.items()}}
    if len(speakers) != 2:
        failures.append("expected 2 speaker ids, got %d: %r"
                        % (len(speakers), sorted(speakers)))
        return False, failures, facts

    def score(item, words):
        text = " ".join(item["texts"]).casefold()
        return sum(1 for word in words if word in text)

    ordered = sorted(speakers.values(),
                     key=lambda item: min(item["starts"]) if item["starts"] else 9e9)
    first, second = ordered[0], ordered[1]
    pt_item = first if score(first, PT_WORDS) >= score(second, PT_WORDS) else second
    en_item = second if pt_item is first else first

    if score(pt_item, PT_WORDS) < 3:
        failures.append("the Portuguese stream lost its own words: %r"
                        % " ".join(pt_item["texts"]))
    if score(pt_item, EN_WORDS) != 0:
        failures.append("CROSSTALK: the Portuguese stream contains English words: %r"
                        % " ".join(pt_item["texts"]))
    if score(en_item, EN_WORDS) < 2:
        failures.append("the English stream lost its own words: %r"
                        % " ".join(en_item["texts"]))
    if score(en_item, PT_WORDS) != 0:
        failures.append("CROSSTALK: the English stream contains Portuguese words: %r"
                        % " ".join(en_item["texts"]))

    if any(item.get("source_changed") for item in speakers.values()):
        failures.append("a speaker changed its per-voice source mid-call")
    sources = {item["source"] for item in speakers.values()}
    if len(sources) != 2 or any(not str(s).startswith("discord/voice:speaker-")
                                for s in sources):
        failures.append("per-voice sources are not two distinct discord/voice ids: %r"
                        % sorted(sources))

    gap_expected = A_PART_S + GAP_MS / 1000.0          # 13.5 s
    pt_starts = pt_item["starts"]
    if not any(start < A_PART_S - 0.5 for start in pt_starts):
        failures.append("no Portuguese line in the pre-gap segment (< %.1f s): %r"
                        % (A_PART_S, pt_starts))
    post_gap = [start for start in pt_starts if start >= A_PART_S]
    if not post_gap:
        failures.append("no Portuguese line after the gap: %r" % pt_starts)
    elif min(post_gap) < gap_expected - 0.4:
        failures.append(
            "CLOCK DRIFT: post-gap line starts at %.2f s; the wall clock says >= %.2f s"
            % (min(post_gap), gap_expected))
    first_en = min(en_item["starts"])
    if not (B_DELAY_MS / 1000.0 - 0.6 <= first_en <= B_DELAY_MS / 1000.0 + 4.0):
        failures.append("English first line starts at %.2f s, expected ~%.1f s"
                        % (first_en, B_DELAY_MS / 1000.0))
    facts["gap_expected_s"] = gap_expected
    facts["pt_post_gap_starts"] = sorted(post_gap)
    facts["en_first_start_s"] = first_en
    return not failures, failures, facts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    for sample in (PT_SAMPLE, EN_SAMPLE):
        if not os.path.isfile(sample):
            print("CANNOT-MEASURE: missing fixture %s" % sample)
            return 3
    os.makedirs(TMP_ROOT, exist_ok=True)
    tree = os.path.join(TMP_ROOT, "discord-streams-oracle-%d-%s"
                        % (os.getpid(), "neg" if args.neg_arm else "pos"))
    shutil.rmtree(tree, ignore_errors=True)
    os.makedirs(tree, exist_ok=True)
    try:
        build_tree(tree, mutate=args.neg_arm)
        rc, events, err = run_worker(tree)
        ok, failures, facts = check(events)
    finally:
        if not args.keep:
            shutil.rmtree(tree, ignore_errors=True)

    print("FACTS " + json.dumps(facts, ensure_ascii=False))
    if args.neg_arm:
        if not ok:
            print("NEG-ARM: PASS (the merged-speaker mutant was caught)")
            for line in failures:
                print("  caught-by: %s" % line)
            return 1
        print("NEG-ARM: FAIL (the merged-speaker mutant passed the assertions)")
        return 0

    if ok:
        print("PASS discord-streams: two voices, own words, own clock, own source")
        return 0
    print("FAIL discord-streams (worker rc=%d)" % rc)
    for line in failures:
        print("  " + line)
    tail = (err or "").strip().splitlines()[-6:]
    for line in tail:
        print("  worker: " + line)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
