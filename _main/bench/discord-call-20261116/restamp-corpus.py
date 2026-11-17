# -*- coding: utf-8 -*-
"""RE-STAMP the corpus manifest against the files that ARE on disk.

## Why this exists

`manifest.json` was written at 2026-11-16T22:18:55, and the two artefacts it
describes were written AFTER it: `mix.opus` at 22:22, `mix-16k.wav` at 22:24:32
and `speech-60s.csv` at 22:21.  The manifest therefore describes a state that
never existed, and the drift is not cosmetic:

    manifest says  mix-16k.wav  432 534 444 B / 216 267 200 frames / 13 516.7 s
    disk has       mix-16k.wav  358 400 044 B / 179 200 000 frames / 11 200.0 s
    deficit                                          2 316.7 s of content time

`13 516.7 - 11 200.0 = 2 316.7`, i.e. the WAV on disk is missing one hole's
worth of audio that the segment list still counts.  Any benchmark that reads
`totals.content_s` and then decodes `mix-16k.wav` measures two different
populations, which is the class this house pays for every time.  The deficit is
REPORTED here, never smoothed away: this script adopts the bytes on disk and
records the gap between them and the segment sum.

## What it does, and what it refuses to do

* Re-derives, by measurement, every number it writes: sha256 + size per file,
  WAV header (channels/rate/width/frames), and the 60 s energy bins using the
  SAME arithmetic as `freeze-corpus.py` (320-sample frames, `20*log10(max(rms,
  1e-9))`, gate -45 dBFS, adaptive = max(gate, p10+12), 3 000 frames per bin).
* Patches `manifest.json` in place: `files`, `totals.wav_*`,
  `energy_only.bins`/aggregates, and a `restamp` block naming what moved.
* Does NOT rebuild audio, does NOT touch the ring, does NOT decode with ffmpeg
  (it only reads the WAV that exists), and does NOT delete the segment list.

Run: `python _main/bench/discord-call-20261116/restamp-corpus.py [--check]`
`--check` measures and prints without writing (a falsifier for the diff).
"""
from __future__ import print_function

import hashlib
import json
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, 'manifest.json')
CSV = os.path.join(HERE, 'speech-60s.csv')
WAV = os.path.join(HERE, 'mix-16k.wav')
MIX_OPUS = os.path.join(HERE, 'mix.opus')

FRAME_MS = 20          # same as freeze-corpus.py:68
GATE_DBFS = -45.0      # same as freeze-corpus.py:69
BIN_S = 60.0           # same as freeze-corpus.py:70
READ_FRAMES = 1 << 20  # 1 MiB of int16 = 32.8 s at 16 kHz, one read per block


def file_facts(path):
    h = hashlib.sha256()
    n = 0
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(4 << 20)
            if not b:
                break
            n += len(b)
            h.update(b)
    return {'bytes': n, 'sha256': h.hexdigest()}


def frame_dbs(path, rate):
    """Yield per-frame dBFS and the frame count, reading the WAV in blocks.

    Same arithmetic as the builder: int16 -> float32/32768 -> rms per 320-sample
    frame -> 20*log10(max(rms,1e-9)).  Blocks are aligned to whole frames so no
    sample is dropped or counted twice.
    """
    fb = int(rate * FRAME_MS / 1000)
    with wave.open(path, 'rb') as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SystemExit('unexpected WAV shape: ch=%d width=%d'
                             % (w.getnchannels(), w.getsampwidth()))
        rate_hz = w.getframerate()
        frames_total = w.getnframes()
        carry = np.zeros(0, dtype='<i2')
        out = []
        while True:
            raw = w.readframes(READ_FRAMES)
            if not raw:
                break
            y = np.frombuffer(raw, dtype='<i2')
            if carry.size:
                y = np.concatenate((carry, y))
            n = (y.size // fb) * fb
            if n:
                f = y[:n].reshape(-1, fb).astype(np.float32) / 32768.0
                out.append(20.0 * np.log10(np.maximum(np.sqrt((f * f).mean(axis=1)), 1e-9)))
            carry = y[n:]
        dbs = np.concatenate(out) if out else np.zeros(0)
    return rate_hz, frames_total, dbs


def bins_from(dbs, per_bin):
    rows = []
    for start in range(0, dbs.size, per_bin):
        chunk = dbs[start:start + per_bin]
        rows.append({'bin': len(rows), 't0_s': len(rows) * BIN_S, 'frames': int(chunk.size),
                     'median_dbfs': round(float(np.median(chunk)), 1),
                     'speech_frac_-45dBFS': round(float((chunk > GATE_DBFS).mean()), 3)})
    return rows


def main():
    check = '--check' in os.sys.argv
    man = json.load(open(MANIFEST, encoding='utf-8'))
    before = dict(man.get('files') or {})
    rate, frames_total, dbs = frame_dbs(WAV, 16000)
    wav_s = frames_total / float(rate)
    per_bin = int(BIN_S * 1000 / FRAME_MS)
    rows = bins_from(dbs, per_bin)
    p10 = float(np.percentile(dbs, 10)) if dbs.size else GATE_DBFS
    adaptive = max(GATE_DBFS, p10 + 12.0)
    for r in rows:
        chunk = dbs[r['bin'] * per_bin:r['bin'] * per_bin + r['frames']]
        r['speech_frac_adaptive'] = round(float((chunk > adaptive).mean()), 3)

    facts_wav, facts_opus = file_facts(WAV), file_facts(MIX_OPUS)
    content_s = float(man['totals']['content_s'])
    deficit = round(content_s - wav_s, 1)

    print('mix-16k.wav  %d B  sha256 %s' % (facts_wav['bytes'], facts_wav['sha256'][:16]))
    print('  rate=%d frames=%d  duration=%.1f s  bins=%d frames_per_bin=%d'
          % (rate, frames_total, wav_s, len(rows), per_bin))
    print('mix.opus     %d B  sha256 %s' % (facts_opus['bytes'], facts_opus['sha256'][:16]))
    print('segments     content_s=%.1f  ->  wav_s=%.1f   DEFICIT=%.1f s'
          % (content_s, wav_s, deficit))
    print('p10_dbfs=%.1f adaptive=%.1f speech_frac=%.3f'
          % (p10, adaptive, float((dbs > GATE_DBFS).mean())))

    if check:
        print('CHECK-ONLY: nothing written')
        return 0

    with open(CSV, 'w', encoding='utf-8', newline='') as fh:
        fh.write('bin,t0_s,frames,median_dbfs,speech_frac_-45dBFS,speech_frac_adaptive\n')
        for r in rows:
            fh.write('%d,%.0f,%d,%.1f,%.3f,%.3f\n'
                     % (r['bin'], r['t0_s'], r['frames'], r['median_dbfs'],
                        r['speech_frac_-45dBFS'], r['speech_frac_adaptive']))
    facts_csv = file_facts(CSV)

    man['files'] = {'mix.opus': facts_opus, 'mix-16k.wav': facts_wav,
                    'speech-60s.csv': facts_csv}
    man['totals']['wav_samples'] = int(frames_total)
    man['totals']['wav_s'] = round(wav_s, 1)
    man['totals']['wav_deficit_vs_segments_s'] = deficit
    man['energy_only'].update({
        'bins_csv': 'speech-60s.csv',
        'p10_dbfs': round(p10, 1),
        'adaptive_gate_dbfs': round(adaptive, 1),
        'speech_frac_whole_corpus_-45': round(float((dbs > GATE_DBFS).mean()), 3),
        'speech_frac_whole_corpus_adaptive': round(float((dbs > adaptive).mean()), 3),
        'bins': rows,
    })
    # IDEMPOTENT BY CONSTRUCTION: the first run's `before` is the lie the file
    # actually carried, and a later run must not overwrite that record with its
    # own predecessor (which is this script's output).  Every other field is a
    # constant re-derived the same way each time, so re-running is a
    # byte-identical no-op -- which is what makes the stamp verifiable.
    prev = man.setdefault('restamp', {})
    prev['utc'] = 'measured 2026-11-17 (restamp-corpus.py)'
    prev['why'] = ('manifest.json was written 2026-11-16T22:18:55, BEFORE mix.opus (22:22), '
                   'speech-60s.csv (22:21) and mix-16k.wav (22:24:32) were (re)written, so it '
                   'described a state that never existed')
    prev.setdefault('before', dict(before))
    prev['deficit_s'] = deficit
    prev['deficit_note'] = (
        'the WAV on disk holds %.1f s of content while the segment list sums %.1f s; the '
        'benchmark audio is SHORTER than the corpus it names, and that gap is published '
        'rather than smoothed' % (wav_s, content_s))
    prev['benchmark_entry_point'] = (
        'mix.opus + `commands.per_segment_decode` (one decode per segment, then the 3:1 '
        'boxcar) is the faithful path: every segment in `segments[]` was measured that way. '
        'Do NOT treat mix-16k.wav as "the corpus" until the %.1f s deficit is explained -- '
        'its provenance after the 22:24:32 rewrite is UNPROVEN.' % deficit)
    tmp = MANIFEST + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, MANIFEST)
    print('WROTE %s (%d B) and %s (%d B)'
          % (os.path.basename(MANIFEST), os.path.getsize(MANIFEST),
             os.path.basename(CSV), os.path.getsize(CSV)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
