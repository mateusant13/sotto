"""Freeze today's audio ring into ONE benchmark corpus (owner's order, 2026-11-16).

WHAT IT PRODUCES (all inside this folder)
  mix.opus        stream-copy concat of every CLOSED ring segment of the day,
                  `-c:a copy`, no re-encode: the corpus as the ring wrote it.
  mix-16k.wav     ONE 16 kHz mono 16-bit decode of the same segments, in the
                  same order, at TRUE wall-clock speed (see THE RATE DEFECT).
  speech-60s.csv  speech fraction per 60 s of content time, ENERGY ONLY.
  manifest.json   per-segment facts + the exact commands + sha256 of every file.

THE RATE DEFECT THIS SCRIPT HAS TO UNDO (measured, not assumed)
  `audio_ring.AudioRing` declares `self.rate = 16000` (worker/audio_ring.py:116)
  and feeds those samples to `ffmpeg -f f32le -ar 16000` (:226). The ring is
  written from `on_block` (worker/sotto_worker.py:7580-7586), which is the tap
  callback -- and the loopback tap delivers the endpoint MIX rate, 48 kHz:
  "It delivers float32 mono at the endpoint's MIX rate (typically 48 kHz) ...
  `resample_to_16k` downstream does the 48k -> 16k step"
  (worker/sotto_worker.py:4440-4447). That resample really is downstream
  (`if native: block = resample_to_16k(block, rate)`, :7951), i.e. AFTER the
  ring already took a copy. So every ring sample is a 48 kHz sample labelled
  16 kHz: played at the declared rate the audio runs 3x slow, an octave and a
  half low.

  Measured on disk, independently of the code: every closed segment declares
  600.0065 s while its wall span (filename open time -> file mtime) is ~200 s.
  `rate_ratio_samples_per_wall_s` in the manifest is samples / wall_span_s and
  reads ~47000-48000; a correct 16 kHz ring would read ~16000.

  The undo is the SAME integer-ratio boxcar the worker uses for 48000 -> 16000
  (worker/sotto_worker.resample_to_16k): mean over exact 3-sample groups. No
  interpolation, no drift, no scipy.

ENERGY-ONLY SPEECH (no model, no sherpa, no GPU)
  20 ms frames on the true-time 16 kHz signal, RMS in dBFS, a frame counts as
  speech above GATE_DBFS. Bins are 60 s of CONTENT time. TWO criteria are
  reported so the number is not a single unreviewed threshold: a fixed
  -45 dBFS gate and an adaptive gate (10th percentile + 12 dB).

Usage (caged):
  PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 --io very-low \
    --single freeze-corpus --timeout 1800 -- python _main/bench/discord-call-20261116/freeze-corpus.py
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DAY = os.path.join(ROOT, 'history', 'audio', '2026-11-16')
DAY_DATE = os.path.basename(DAY)                      # AAAA-MM-DD

#: The ring's DECLARED rate (worker/audio_ring.py:116, and the `-ar 16000` it
#: hands ffmpeg at :226).
DECL_RATE = 16000
#: The rate the tap actually hands `on_block` (worker/sotto_worker.py:4440).
TRUE_RATE = 48000
RATIO = TRUE_RATE // DECL_RATE

FRAME_MS = 20
GATE_DBFS = -45.0
BIN_S = 60.0

OUT_OPUS = os.path.join(HERE, 'mix.opus')
OUT_WAV = os.path.join(HERE, 'mix-16k.wav')
OUT_MANIFEST = os.path.join(HERE, 'manifest.json')
OUT_CSV = os.path.join(HERE, 'speech-60s.csv')
#: Where ONE segment's declared-16 kHz PCM is staged (19 MB at a time, deleted
#: after each segment). TMPDIR is I:\cc-tmp on this box; H: is 99 % full.
TMP_PCM = os.path.join(os.environ.get('TMPDIR') or os.environ.get('TEMP') or HERE,
                       'sotto-corpus-seg.pcm')
#: DUTY CYCLE, declared before the run: sleep this fraction of the time the last
#: segment took. The cage bounds CPU and cannot bound a reader that never waits,
#: so the reader bounds itself.
PACE = 0.30


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(argv):
    r = subprocess.run(argv, capture_output=True)
    if r.returncode:
        raise SystemExit('command failed rc=%d: %r\n%s'
                         % (r.returncode, argv, r.stderr.decode('utf-8', 'replace')[:600]))
    return r.stdout


def probe_duration(path):
    out = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=nw=1:nk=1', path]).decode().strip()
    try:
        return float(out)
    except ValueError:
        return None



def snapshot(day_dir, quiet_s=3.0):
    """Every .opus whose size stopped changing, in filename (= open time) order."""
    names = sorted(n for n in os.listdir(day_dir) if n.endswith('.opus'))
    first = {}
    for n in names:
        try:
            first[n] = os.path.getsize(os.path.join(day_dir, n))
        except OSError:
            first[n] = -1
    time.sleep(quiet_s)
    out = []
    for n in names:
        p = os.path.join(day_dir, n)
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        if size <= 0 or size != first[n]:
            continue          # empty, or still being written by the live worker
        out.append(p)
    return out


def decode_argv(path, out):
    """ONE decode of ONE segment, 16-bit at the DECLARED rate, to `out`."""
    return ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1',
            '-i', path, '-map', '0:a:0', '-ac', '1', '-ar', str(DECL_RATE),
            '-f', 's16le', out]


def concat_opus(segments, out_path):
    lst = out_path + '.concat.txt'
    with open(lst, 'w', encoding='utf-8') as fh:
        for p in segments:
            fh.write("file '%s'\n" % p.replace('\\', '/'))
    argv = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '1',
            '-f', 'concat', '-safe', '0', '-i', lst,
            '-map', '0:a:0', '-c:a', 'copy', '-f', 'ogg', out_path]
    try:
        run(argv)
    finally:
        os.remove(lst)
    return argv



#: ONE 8 MB read. THE MEASURED REASON IT IS A FILE AND NOT A PIPE: reading a
#: pipe with a 1 MB `BufferedReader.read()` issues a syscall per whatever the
#: pipe happens to hold, measured on this box as 61 736 ops/s at 1 470 bytes per
#: operation (91.2 MB/s) -- a reader that never waits, which the cage can bound
#: in CPU but not in IO, and it stuttered the owner's live call. A regular file
#: read of 8 MB is one operation, and the file was just written so it is in the
#: page cache.
READ_BYTES = 8 << 20


class Channel(object):
    """Decode ONE segment to a temp file, then read it back in 8 MB blocks.

    One ffmpeg per segment, one process at a time (the caller is serial), and
    never two passes over the same bytes: this pass yields the true-time 16 kHz
    blocks and counts the declared samples at the same time.
    """

    def __init__(self, path, tmp_path):
        self.path = path
        self.tmp_path = tmp_path
        self.samples = 0
        self.rem = b''

    def decode_to_temp(self):
        # `-f s16le <file>`: ffmpeg writes the declared-16 kHz stream straight to
        # a regular file. 16-bit instead of float32 halves the bytes on disk; the
        # corpus WAV is 16-bit anyway, so nothing a benchmark can hear is lost.
        run(decode_argv(self.path, self.tmp_path))

    def blocks(self):
        with open(self.tmp_path, 'rb') as fh:
            while True:
                raw = fh.read(READ_BYTES)
                if not raw:
                    break
                if self.rem:
                    raw = self.rem + raw
                keep = len(raw) - (len(raw) % (2 * RATIO))     # whole 3-sample groups
                if not keep:
                    self.rem = raw
                    continue
                x = np.frombuffer(raw[:keep], dtype='<i2')
                self.rem = raw[keep:]
                self.samples += x.size
                mean = x.reshape(-1, RATIO).astype(np.int32).sum(axis=1)
                yield ((mean + 1) // RATIO).astype('<i2')      # boxcar, rounded
        self.rem = b''


def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    segments = snapshot(DAY)
    if not segments:
        raise SystemExit('no closed segments in %s' % DAY)
    if limit:
        segments = segments[:limit]        # dry run: first N closed segments only
    print('segments: %d' % len(segments))

    # ── 1. the corpus as written (stream copy) ────────────────────────────────
    concat_argv = concat_opus(segments, OUT_OPUS)
    mix_declared_s = probe_duration(OUT_OPUS)

    # ── 2. the true-time 16 kHz decode ────────────────────────────────────────
    per_seg = []
    frame_bytes = int(DECL_RATE * FRAME_MS / 1000)      # 20 ms at 16 kHz = 320
    written = 0

    with wave.open(OUT_WAV, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        for i, path in enumerate(segments, 1):
            name = os.path.basename(path)
            t_seg = time.time()
            ch = Channel(path, TMP_PCM)
            ch.decode_to_temp()
            carry = np.zeros(0, dtype=np.int16)
            seg_frames = 0
            seg_dbs = []
            for y in ch.blocks():
                if carry.size:
                    y = np.concatenate((carry, y))
                n = (y.size // frame_bytes) * frame_bytes
                if n:
                    f = y[:n].reshape(-1, frame_bytes).astype(np.float32) / 32768.0
                    rms = np.sqrt((f * f).mean(axis=1))
                    seg_dbs.append(20.0 * np.log10(np.maximum(rms, 1e-9)))
                    seg_frames += int(n // frame_bytes)
                    wav.writeframes(y[:n].astype('<i2').tobytes())
                    written += n
                carry = y[n:]
            try:
                os.remove(TMP_PCM)
            except OSError:
                pass
            declared_s = ch.samples / float(DECL_RATE)
            content_s = ch.samples / float(TRUE_RATE)
            st = os.stat(path)
            stt = name.split('.')[0]
            opened = _dt.datetime(2026, 11, 16, int(stt[0:2]), int(stt[2:4]), int(stt[4:6]))
            closed = _dt.datetime.fromtimestamp(st.st_mtime)
            span = (closed - opened).total_seconds()
            dbs = np.concatenate(seg_dbs) if seg_dbs else np.zeros(0)
            per_seg.append({
                'file': name,
                'bytes': st.st_size,
                'sha256_16': sha256(path)[:16],
                'opened': opened.strftime('%Y-%m-%dT%H:%M:%S'),
                'closed_mtime': closed.strftime('%Y-%m-%dT%H:%M:%S'),
                'wall_span_s': round(span, 1),
                'ffprobe_format_s': probe_duration(path),
                'decoded_s_at_declared_16k': round(declared_s, 3),
                'content_s_at_true_48k': round(content_s, 3),
                'rate_ratio_samples_per_wall_s': round(ch.samples / span, 0) if span else None,
                'hole_s_inside_segment': round(span - content_s, 1),
                'frames': seg_frames,
                'median_frame_dbfs': round(float(np.median(dbs)), 1) if dbs.size else None,
                'p10_dbfs': round(float(np.percentile(dbs, 10)), 1) if dbs.size else None,
                '_db': dbs,
            })
            took = time.time() - t_seg
            print('  [%2d/%2d] %s content=%7.1fs span=%7.1fs ratio=%6.0f took=%.1fs'
                  % (i, len(segments), name, content_s, span,
                     ch.samples / span if span else 0, took))
            if PACE and i < len(segments):
                time.sleep(PACE * took)

    # ── 3. 60 s energy bins over the WHOLE corpus, content time ───────────────
    all_db = (np.concatenate([s.pop('_db') for s in per_seg])
              if per_seg else np.zeros(0))
    p10 = float(np.percentile(all_db, 10)) if all_db.size else GATE_DBFS
    adaptive = max(GATE_DBFS, p10 + 12.0)
    per_bin = int(BIN_S * 1000 / FRAME_MS)
    rows = []
    for start in range(0, all_db.size, per_bin):
        chunk = all_db[start:start + per_bin]
        rows.append({
            'bin': len(rows),
            't0_s': len(rows) * BIN_S,
            'frames': int(chunk.size),
            'median_dbfs': round(float(np.median(chunk)), 1),
            'speech_frac_-45dBFS': round(float((chunk > GATE_DBFS).mean()), 3),
            'speech_frac_adaptive': round(float((chunk > adaptive).mean()), 3),
        })
    with open(OUT_CSV, 'w', encoding='utf-8') as fh:
        fh.write('bin,t0_s,frames,median_dbfs,speech_frac_-45dBFS,speech_frac_adaptive\n')
        for r in rows:
            fh.write('%d,%.0f,%d,%.1f,%.3f,%.3f\n' % (r['bin'], r['t0_s'], r['frames'],
                                                      r['median_dbfs'],
                                                      r['speech_frac_-45dBFS'],
                                                      r['speech_frac_adaptive']))

    # ── 4. gaps on the wall-clock timeline ────────────────────────────────────
    gaps = []
    prev_end = None
    for s in per_seg:
        opened = _dt.datetime.strptime(s['opened'], '%Y-%m-%dT%H:%M:%S')
        closed = _dt.datetime.strptime(s['closed_mtime'], '%Y-%m-%dT%H:%M:%S')
        if prev_end is not None:
            g = (opened - prev_end).total_seconds()
            if g > 0:
                gaps.append({'from': prev_end.strftime('%H:%M:%S'),
                             'to': opened.strftime('%H:%M:%S'), 'gap_s': round(g, 1)})
        prev_end = closed
    biggest = max(gaps, key=lambda g: g['gap_s']) if gaps else None
    holes = sorted(({'file': s['file'], 'hole_s': s['hole_s_inside_segment']}
                    for s in per_seg), key=lambda h: -h['hole_s'])[:5]

    total_content = sum(s['content_s_at_true_48k'] for s in per_seg)
    total_span = sum(s['wall_span_s'] for s in per_seg)
    manifest = {
        'corpus': 'discord-call-20261116',
        'built': _dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'owner_order': 'keep the current audio on disk as a benchmark corpus '
                       '(2026-11-16, live Discord call)',
        'source_dir': 'history/audio/2026-11-16',
        'snapshot_policy': 'every .opus with size > 0 whose size did not change over 3 s '
                           'at build time; the segment the live worker was still writing '
                           'is EXCLUDED',
        'rate_finding': {
            'ring_declared_rate_hz': DECL_RATE,
            'tap_rate_hz': TRUE_RATE,
            'speed_factor_applied_to_mix16k': RATIO,
            'verify': 'per-segment rate_ratio_samples_per_wall_s reads ~47000-48000; '
                      'a correct 16 kHz ring would read ~16000',
            'mechanism': 'worker/audio_ring.py:116 self.rate = 16000; '
                         'worker/sotto_worker.py:7580-7586 on_block() pushes the raw tap '
                         'block BEFORE worker/sotto_worker.py:7951 resample_to_16k runs',
        },
        'commands': {
            'mix_opus': ' '.join(concat_argv),
            'per_segment_decode': ' '.join(decode_argv('<segment.opus>', '<tmp.pcm>')),
            'mix_16k_wav': 'the per-segment decode above, then boxcar 3:1 '
                           '(declared-16k -> true-16k) and 16-bit PCM, one WAV',
            'decode_proof': 'ffmpeg -v error -i mix-16k.wav -f null -',
            'completeness_proof': 'ffprobe format=duration of mix.opus vs the sum of the '
                                 'per-segment decoded durations',
            'naive_decode_WRONG': 'ffmpeg -i mix.opus -ar 16000 out.wav   '
                                  '# 3x slow / 1.5 octaves low: do not benchmark on it',
        },
        'totals': {
            'segments': len(per_seg),
            'content_s': round(total_content, 1),
            'wall_span_s': round(total_span, 1),
            'wav_samples': int(written),
            'wav_s': round(written / 16000.0, 2),
            'mix_opus_declared_s': mix_declared_s,
            'largest_file_gap': biggest,
            'top_intra_segment_holes': holes,
        },
        'energy_only': {
            'frame_ms': FRAME_MS,
            'gate_dbfs_fixed': GATE_DBFS,
            'adaptive_gate_dbfs': round(adaptive, 1),
            'p10_dbfs': round(p10, 1),
            'speech_frac_whole_corpus_-45': round(float((all_db > GATE_DBFS).mean()), 3),
            'speech_frac_whole_corpus_adaptive': round(float((all_db > adaptive).mean()), 3),
            'bins_csv': 'speech-60s.csv',
            'bins': rows,
        },
        'files': {},
        'segments': per_seg,
    }
    for key, path in (('mix.opus', OUT_OPUS), ('mix-16k.wav', OUT_WAV),
                      ('speech-60s.csv', OUT_CSV)):
        manifest['files'][key] = {'bytes': os.path.getsize(path), 'sha256': sha256(path)}
    with open(OUT_MANIFEST, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write('\n')
    print(json.dumps({'segments': len(per_seg),
                      'content_s': round(total_content, 1),
                      'wav_s': round(written / 16000.0, 2),
                      'mix_declared_s': mix_declared_s,
                      'largest_gap': biggest,
                      'speech_-45': manifest['energy_only']['speech_frac_whole_corpus_-45'],
                      'adaptive_gate': round(adaptive, 1)}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
