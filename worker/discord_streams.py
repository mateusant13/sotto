#!/usr/bin/env python
"""discord_streams.py -- ONE transcript per Discord speaker, in parallel.

WHAT THE OWNER ASKED FOR (2026-11-24, verbatim):
    "sotto é pra conseguir distinguir cada voz/camada de audio e saber
     transcrever corretamente cada uma em paralelo. faz isso de algum jeito
     usando o que o discord proporciona ou entao com modelo que separa vozes."

WHY THE DISCORD SPLIT AND NOT A SEPARATION MODEL
------------------------------------------------
Discord's voice engine already knows who is who: the SFU sends one Opus
stream per participant, tagged with an audio SSRC, and the SPEAKING opcode
maps SSRC -> user id. `discord/src/receiver-core.js` decodes each of those
streams into its own 16 kHz mono PCM file under `<out>/<user_id>/`. That split
is EXACT: two people talking at the same time never touch the same bytes.

The alternative -- a separation model over the mixed call -- was measured on
this machine against the real 2026-11-16 Discord call
(`_main/bench/logs/moss-after.log`): MossFormer2_SS_16K over 60 s cost
**1335.107 s (RTF 22.25)** and produced **210 words in stream 0 and 2 words in
stream 1** against 211 words in the mix, i.e. it fed nearly the whole call to
one voice. It cannot run live on this box and it did not separate that 4-voice
mix. So the ingress here is the exact one Discord gives us for free.

WHAT THIS FILE IS (the missing half)
------------------------------------
The capture side exists; nothing transcribed it per speaker. This worker:
  * tails `<pcm-dir>/<user_id>/*.pcm` (any number of speakers, any number of
    rolled segment files per speaker),
  * segments each speaker INDEPENDENTLY (energy gate + line cap) with
    `redux_live.LiveSegmenter`, so one person pausing never closes another
    person's line,
  * decodes every speaker's utterances on ONE engine thread (the GPU is the
    shared resource; "parallel" is per-speaker state and per-speaker captions,
    not N copies of a 615 MB model),
  * writes the worker JSONL contract the shell already reads, one object per
    line on stdout, with the per-voice fields the panel already renders.

THE CLOCK (the part that is easy to get wrong)
----------------------------------------------
Discord sends NOTHING while a participant is silent, so a speaker's PCM is not
wall-clock-continuous: concatenating samples and dividing by 16 kHz drifts by
every pause, and after ten minutes the badge is minutes away from the voice.
Timestamps therefore come from the per-packet index the writer already emits
(`<segment>.jsonl`: one `packet` row with `t_ms` and `samples`), interpolated
inside a packet at 16 kHz. `start`/`end` land on ONE shared clock: the earliest
`started_at_ms` header in the tree, so two speakers' lines are comparable.

PER-VOICE SOURCE. Each caption carries `source="discord/voice:speaker-<n>"`
(the shape `app/panel/panel.js::voiceFromSource` reads) plus `speaker` and
`speakerId`. The panel paints one forming row and one hue per voice with no app
change; `--names` maps ids to display names when one is supplied.

RELATION TO THE EXISTING SPEAKER PATH (not a replacement)
---------------------------------------------------------
`worker/speaker_sidecar.py` labels a MIXED stream after the fact; this worker
does not use it and does not need it, because here the audio is already split.
`sotto_worker.py --speakers` still applies to the endpoint-mix path.

USAGE
-----
    python worker/discord_streams.py                       # tail discord/out
    python worker/discord_streams.py --pcm-dir D --names names.json
    python worker/discord_streams.py --once --quiet        # drain, then exit
    run.cmd --worker worker\\discord_streams.py            # captions in the panel

Only READS the tree; never opens an audio device, never touches the owner's
audio endpoints, never spawns a console window.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np                                                     # noqa: E402

import redux_live                                                      # noqa: E402

RATE = 16000
BYTES_PER_SAMPLE = 2
DEFAULT_PCM_DIR = os.path.join(REPO, "discord", "out")
PRODUCER = "redux"


def log(line):
    sys.stderr.write("discord-streams: %s\n" % line)
    sys.stderr.flush()


def emit(payload):
    """One JSON object, one line, flushed -- the shell's worker contract."""
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        os._exit(0)


def read_header(jsonl_path):
    """The `segment` header of one index file, or None if not written yet."""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("type") == "segment":
                    return row
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return None


class PacketIndex:
    """`<segment>.jsonl` read incrementally: sample offset -> wall clock ms.

    One anchor per packet is enough: packets are 20 ms of audio, and the wall
    time inside a packet is interpolated at 16 kHz. Anchors are appended as the
    index grows, so the reader never re-parses a growing file.
    """

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.header = None
        self.anchors = []      # [(sample_offset_in_file, t_ms)]

    def refresh(self):
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read()
        except OSError:
            return
        if not data:
            return
        consumed = data.rfind(b"\n") + 1
        if consumed <= 0:
            return                      # a half-written row; the next scan gets it
        self.offset += consumed
        cursor = self.anchors[-1][0] if self.anchors else 0
        for raw in data[:consumed].splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            kind = row.get("type")
            if kind == "segment" and self.header is None:
                self.header = row
            elif kind == "packet":
                samples = int(row.get("samples") or 0)
                t_ms = row.get("t_ms")
                if samples <= 0 or t_ms is None:
                    continue
                self.anchors.append((cursor, int(t_ms)))
                cursor += samples

    def wall_ms(self, sample_offset):
        """Wall clock for a sample offset inside this file."""
        if not self.anchors:
            start = None
            if self.header and self.header.get("started_at_ms") is not None:
                start = float(self.header["started_at_ms"])
            return start
        index = bisect.bisect_right(self.anchors, (sample_offset, float("inf"))) - 1
        if index < 0:
            return float(self.anchors[0][1])
        base_sample, base_ms = self.anchors[index]
        if index + 1 < len(self.anchors):
            next_sample, next_ms = self.anchors[index + 1]
            span = next_sample - base_sample
            if span > 0:
                return base_ms + (sample_offset - base_sample) * (next_ms - base_ms) / span
        return base_ms + (sample_offset - base_sample) * 1000.0 / RATE


class Segment:
    """One PCM file plus its index; `base` is its first sample on the speaker."""

    __slots__ = ("path", "index", "base", "span")

    def __init__(self, path, base):
        self.path = path
        self.index = PacketIndex(path[:-4] + ".jsonl")
        self.base = int(base)
        self.span = 0
        self.refresh()

    def refresh(self):
        self.index.refresh()
        try:
            self.span = max(self.span, os.path.getsize(self.path) // BYTES_PER_SAMPLE)
        except OSError:
            pass


class Speaker:
    """One Discord user id: its files, its sample clock, its open line."""

    __slots__ = ("user_id", "slot", "name", "segmenter", "epoch_ms", "files",
                 "current", "file_offset", "seg_base", "fed", "last_wall_ms",
                 "lines", "samples", "bytes", "partial_at")

    def __init__(self, user_id, slot, segmenter, epoch_ms):
        self.user_id = user_id
        self.slot = slot
        self.name = "speaker-%d" % slot
        self.segmenter = segmenter
        self.epoch_ms = epoch_ms
        self.files = []
        self.current = -1
        self.file_offset = 0
        self.seg_base = 0
        self.fed = 0
        self.last_wall_ms = None
        self.lines = 0
        self.samples = 0
        self.bytes = 0
        self.partial_at = 0.0

    @property
    def total_samples(self):
        return self.files[-1].base + self.files[-1].span if self.files else 0

    def wall_ms(self, sample):
        if not self.files:
            return float(self.epoch_ms)
        chosen = self.files[0]
        for segment in self.files:
            if sample >= segment.base:
                chosen = segment
            else:
                break
        local = min(max(0, sample - chosen.base), max(0, chosen.span - 1))
        wall = chosen.index.wall_ms(local)
        if wall is None:
            return float(self.epoch_ms) + sample * 1000.0 / RATE
        return wall

    def timeline_s(self, sample):
        return max(0.0, (self.wall_ms(sample) - self.epoch_ms) / 1000.0)

    def line_start_sample(self):
        """Global sample index where the open line began."""
        seg = self.segmenter
        if seg.seg_start is None:
            return self.fed
        return self.seg_base + int(round(float(seg.seg_start) * RATE))

    def line_end_sample(self):
        seg = self.segmenter
        return self.seg_base + int(round(float(seg.audio_s) * RATE))

    def restart_segmenter(self):
        self.segmenter = _SEGMENTER_FACTORY()
        self.seg_base = self.fed
        self.partial_at = 0.0


_SEGMENTER_FACTORY = None


class StreamQueue:
    """Bounded hand-off from the readers to the one decode thread.

    Bounded on purpose: with many speakers the engine is the bottleneck, and an
    unbounded queue would turn a slow GPU into an out-of-memory. A dropped
    PARTIAL hurts nothing (the next pass or the final replaces it); a dropped
    FINAL is counted and named, never silent.
    """

    def __init__(self, cap=256):
        self.q = queue.Queue(maxsize=int(cap))
        self.dropped_partials = 0
        self.dropped_finals = 0

    def put(self, job):
        try:
            self.q.put_nowait(job)
        except queue.Full:
            if job.final:
                self.dropped_finals += 1
                log("QUEUE_FULL dropped=final speaker=%s start=%.2f"
                    % (job.speaker, job.start))
            else:
                self.dropped_partials += 1

    def get(self, timeout=0.25):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


class Job:
    __slots__ = ("pcm", "start", "end", "final", "line_id", "speaker", "label",
                 "uid", "source")

    def __init__(self, pcm, start, end, final, line_id, speaker, label, uid, source):
        self.pcm = pcm
        self.start = start
        self.end = end
        self.final = final
        self.line_id = line_id
        self.speaker = speaker
        self.label = label
        self.uid = uid
        self.source = source


class Reader:
    """Discovery + per-speaker segmentation. Never decodes."""

    def __init__(self, pcm_dir, out, names=None, gap_s=0.4, block_s=0.2,
                 partial_s=2.0, window_s=None, min_window_s=None):
        self.pcm_dir = os.path.abspath(pcm_dir)
        self.out = out
        self.names = names or {}
        self.gap_s = float(gap_s)
        self.block_bytes = max(BYTES_PER_SAMPLE, int(block_s * RATE) * BYTES_PER_SAMPLE)
        self.partial_s = float(partial_s)
        self.window_s = float(window_s if window_s is not None
                              else redux_live.DEFAULT_WINDOW_S)
        self.min_window_s = float(min_window_s if min_window_s is not None
                                  else redux_live.DEFAULT_MIN_WINDOW_S)
        self.speakers = {}
        self.next_slot = 1
        self.epoch_ms = None
        self.blocks = 0
        self.bytes_read = 0

    # -- discovery -------------------------------------------------------
    def discover(self):
        try:
            entries = sorted(os.listdir(self.pcm_dir))
        except OSError:
            return 0
        added = 0
        for name in entries:
            path = os.path.join(self.pcm_dir, name)
            if not (name.isdigit() and os.path.isdir(path)) or name in self.speakers:
                continue
            speaker = Speaker(name, self.next_slot, _SEGMENTER_FACTORY(), None)
            speaker.name = self.names.get(name) or "speaker-%d" % self.next_slot
            self.speakers[name] = speaker
            self.next_slot += 1
            self._refresh_files(speaker)
            added += 1
        if added:
            self._settle_epoch()
        return added

    def _settle_epoch(self):
        earliest = None
        for speaker in self.speakers.values():
            for segment in speaker.files:
                header = read_header(segment.index.path)
                if header and header.get("started_at_ms") is not None:
                    started = int(header["started_at_ms"])
                    earliest = started if earliest is None else min(earliest, started)
        if earliest is None:
            return
        self.epoch_ms = earliest
        for speaker in self.speakers.values():
            speaker.epoch_ms = earliest

    def _refresh_files(self, speaker):
        directory = os.path.join(self.pcm_dir, speaker.user_id)
        try:
            names = sorted(n for n in os.listdir(directory) if n.endswith(".pcm"))
        except OSError:
            return 0
        known = {segment.path for segment in speaker.files}
        base = speaker.total_samples
        added = 0
        for name in names:
            path = os.path.join(directory, name)
            if path in known:
                continue
            speaker.files.append(Segment(path, base))
            base += speaker.files[-1].span
            added += 1
        if added and speaker.current < 0:
            speaker.current = 0
            speaker.file_offset = 0
            speaker.seg_base = 0
        return added

    # -- reading ---------------------------------------------------------
    def pump(self):
        """Read every complete block available, per speaker, once."""
        self.discover()
        for speaker in self.speakers.values():
            self._refresh_files(speaker)
        if self.epoch_ms is None:
            self._settle_epoch()
        if self.epoch_ms is None:
            return 0
        read_any = 0
        for speaker in self.speakers.values():
            speaker.epoch_ms = self.epoch_ms
            while speaker.current >= 0:
                segment = speaker.files[speaker.current]
                segment.refresh()
                if not segment.index.header:
                    break                       # the writer has not flushed it yet
                if self._read_block(speaker, segment):
                    read_any += 1
                    continue
                if speaker.current + 1 < len(speaker.files):
                    self._close_line(speaker)
                    speaker.current += 1
                    speaker.file_offset = 0
                    speaker.restart_segmenter()
                    continue
                break
            self._maybe_partial(speaker)
        return read_any

    def _read_block(self, speaker, segment):
        try:
            with open(segment.path, "rb") as fh:
                fh.seek(speaker.file_offset)
                data = fh.read(self.block_bytes)
        except OSError:
            return False
        usable = len(data) - (len(data) % BYTES_PER_SAMPLE)
        if usable <= 0:
            return False
        absolute = segment.base + speaker.file_offset // BYTES_PER_SAMPLE
        speaker.file_offset += usable
        self.bytes_read += usable
        speaker.bytes += usable
        self.blocks += 1
        samples = np.frombuffer(data[:usable], dtype="<i2").astype(np.float32) / 32768.0
        speaker.samples += samples.size

        wall_start = speaker.wall_ms(absolute)
        if (speaker.last_wall_ms is not None
                and wall_start - speaker.last_wall_ms > self.gap_s * 1000.0):
            # A pause that exists only on the wall clock (Discord sends no
            # packets while the user is silent) CLOSES the line: feeding the
            # concatenated bytes would join two utterances minutes apart.
            self._close_line(speaker)
            speaker.restart_segmenter()
        speaker.last_wall_ms = wall_start + samples.size * 1000.0 / RATE
        speaker.fed = max(speaker.fed, absolute + samples.size)
        speaker.segmenter.feed(samples)
        if speaker.segmenter.should_close(None):
            self._close_line(speaker)
            speaker.restart_segmenter()
        return True

    def _maybe_partial(self, speaker):
        seg = speaker.segmenter
        if seg.seg_start is None or seg.seg_samples == 0 or not seg.should_decode():
            return
        if seg.open_seconds - speaker.partial_at < self.partial_s:
            return
        speaker.partial_at = seg.open_seconds
        self._enqueue(speaker, final=False)

    def _close_line(self, speaker):
        seg = speaker.segmenter
        if seg.seg_start is None or seg.seg_samples == 0:
            return False
        self._enqueue(speaker, final=True)
        speaker.lines += 1
        return True

    def _enqueue(self, speaker, final):
        seg = speaker.segmenter
        pcm = np.concatenate(seg.seg) if len(seg.seg) > 1 else seg.seg[0].copy()
        start_sample = speaker.line_start_sample()
        end_sample = start_sample + pcm.size
        self.out.put(Job(
            pcm=pcm,
            start=speaker.timeline_s(start_sample),
            end=max(speaker.timeline_s(end_sample),
                    speaker.timeline_s(start_sample)),
            final=final,
            line_id=speaker.lines,
            speaker=speaker.user_id,
            label=speaker.name,
            uid=speaker.user_id,
            source="discord/voice:speaker-%d" % speaker.slot,
        ))

    def flush(self):
        for speaker in self.speakers.values():
            self._close_line(speaker)
            speaker.restart_segmenter()

    def stats(self):
        return "speakers=%d blocks=%d bytes=%d epoch_ms=%s" % (
            len(self.speakers), self.blocks, self.bytes_read, self.epoch_ms)


class Decoder:
    """One engine thread: transcribe every queued speaker job, emit captions."""

    def __init__(self, backend, worker, quiet=False):
        self.backend = backend
        self.worker = worker
        self.quiet = quiet
        self.stop = False
        self.decoded = 0
        self.finals = 0
        self.partials = 0
        self.errors = 0
        self.compute_s = []
        self.last_text = {}

    def run(self):
        while True:
            job = self.worker.get(0.25)
            if job is None:
                if self.stop and self.worker.q.unfinished_tasks == 0:
                    break
                continue
            try:
                started = time.perf_counter()
                text, _segments = self.backend.transcribe(job.pcm)
                elapsed = time.perf_counter() - started
            except Exception as exc:                        # noqa: BLE001
                self.errors += 1
                log("DECODE_FAILED speaker=%s start=%.2f %s: %s"
                    % (job.label, job.start, type(exc).__name__, exc))
                self.worker.q.task_done()
                continue
            self.worker.q.task_done()
            self.decoded += 1
            self.compute_s.append(elapsed)
            text = (text or "").strip()
            if not text:
                continue
            key = (job.speaker, job.line_id)
            if not job.final and self.last_text.get(key) == text:
                continue
            if len(self.last_text) > 512:
                self.last_text.clear()
            self.last_text[key] = text
            if job.final:
                self.finals += 1
            else:
                self.partials += 1
            emit({
                "type": "caption",
                "text": text,
                "start": round(job.start, 2),
                "end": round(job.end, 2),
                "final": bool(job.final),
                "producer": PRODUCER,
                "producerModel": self.backend.name,
                "route": "final" if job.final else "provisional-draft",
                "speaker": job.label,
                "speakerId": job.uid,
                "source": job.source,
                "audio_s": round(float(job.pcm.size) / RATE, 2),
            })
            if not self.quiet and job.final:
                log("CAPTION speaker=%s start=%.2f end=%.2f chars=%d"
                    % (job.label, job.start, job.end, len(text)))

    def stats_line(self):
        if not self.compute_s:
            return "decoded=0 finals=0"
        return ("decoded=%d finals=%d partials=%d errors=%d "
                "mean_compute_s=%.3f max_compute_s=%.3f"
                % (self.decoded, self.finals, self.partials, self.errors,
                   sum(self.compute_s) / len(self.compute_s), max(self.compute_s)))


def load_names(path):
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        log("names file unreadable (%s); ids will be shown as speaker-N" % exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if str(v).strip()}


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pcm-dir", default=DEFAULT_PCM_DIR,
                    help="Discord per-user PCM tree (default discord/out)")
    ap.add_argument("--names", default=None,
                    help="JSON {user_id: display name}; without it: speaker-N")
    ap.add_argument("--once", action="store_true",
                    help="read everything already on disk, flush open lines, exit")
    ap.add_argument("--quiet", action="store_true", help="no per-caption stderr line")
    ap.add_argument("--poll-s", type=float, default=0.20)
    ap.add_argument("--stats-s", type=float, default=10.0)
    ap.add_argument("--gap-s", type=float, default=0.4,
                    help="wall-clock silence that closes a speaker's line")
    ap.add_argument("--window-s", type=float, default=redux_live.DEFAULT_WINDOW_S)
    ap.add_argument("--min-window-s", type=float, default=redux_live.DEFAULT_MIN_WINDOW_S)
    ap.add_argument("--partial-s", type=float, default=2.0,
                    help="decode an open line every N s of new audio")
    ap.add_argument("--threads", type=int, default=2,
                    help="process-wide engine threads (see redux_live budget)")
    ap.add_argument("--engine", choices=("onnx", "ternary"), default="onnx")
    ap.add_argument("--onnx-dir", default=redux_live.DEFAULT_ONNX_DIR)
    ap.add_argument("--ternary-dir", default=redux_live.DEFAULT_TERNARY_DIR)
    ap.add_argument("--idle-exit-s", type=float, default=0.0,
                    help="in tail mode, exit after N s without new bytes (0 = never)")
    # ── the flags the shell hands EVERY worker (app/webview/sotto_webview.py
    # `worker_argv_tail` + `_spawn`). Accepted here because a rejected argv is a
    # worker that never starts; none of them changes this worker's source.
    ap.add_argument("--preload-only", action="store_true",
                    help="load the engine and wait for START_CAPTURE on stdin")
    ap.add_argument("--speakers", action="store_true",
                    help="uniform shell flag; this worker is per-speaker by construction")
    ap.add_argument("--panel-visibility", default=None,
                    help="uniform shell flag; the display switch belongs to the shell")
    return ap


def main(argv=None):
    global _SEGMENTER_FACTORY
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.pcm_dir):
        log("no capture tree at %s (run the Discord capture first)" % args.pcm_dir)
        return 2
    names = load_names(args.names)

    def segmenter_factory():
        return redux_live.LiveSegmenter(
            window_s=args.window_s, gap_s=args.gap_s,
            min_window_s=args.min_window_s)

    _SEGMENTER_FACTORY = segmenter_factory
    worker = StreamQueue()
    reader = Reader(args.pcm_dir, worker, names=names, gap_s=args.gap_s,
                    partial_s=args.partial_s, window_s=args.window_s,
                    min_window_s=args.min_window_s)
    backend = redux_live.load_backend(
        args.engine, args.onnx_dir, args.ternary_dir, args.threads, "cuda",
        log=log)
    log("engine=%s load_s=%.2f threads=%d tree=%s"
        % (backend.name, backend.load_s, args.threads,
           os.path.abspath(args.pcm_dir)))
    emit({"type": "status", "state": "model-loaded", "engine": backend.name,
          "stage": "discord-streams", "load_s": backend.load_s})
    if args.preload_only:
        # The shell preloads a worker and activates it with ONE line on stdin.
        # Emitting captions before that would paint a call the owner has not
        # asked to caption; loading the model early is the whole point.
        log("PRELOAD waiting for START_CAPTURE")
        while True:
            line = sys.stdin.readline()
            if not line:
                log("PRELOAD stdin closed; exiting without capturing")
                return 0
            if line.strip() == "START_CAPTURE":
                break

    decoder = Decoder(backend, worker, quiet=args.quiet)
    thread = threading.Thread(target=decoder.run, name="discord-decode", daemon=True)
    thread.start()
    next_stats = time.monotonic() + args.stats_s
    idle_since = None
    empty_pumps = 0
    try:
        while True:
            read = reader.pump()
            if read:
                idle_since = None
                empty_pumps = 0
            else:
                empty_pumps += 1
                if idle_since is None:
                    idle_since = time.monotonic()
            now = time.monotonic()
            if now >= next_stats:
                log("STATS %s %s queue=%d dropped_partials=%d dropped_finals=%d"
                    % (reader.stats(), decoder.stats_line(), worker.q.qsize(),
                       worker.dropped_partials, worker.dropped_finals))
                next_stats = now + args.stats_s
            if args.once and empty_pumps >= 2:
                break
            if (args.idle_exit_s and idle_since is not None
                    and now - idle_since >= args.idle_exit_s):
                log("IDLE_EXIT after %.1fs without new bytes" % args.idle_exit_s)
                break
            time.sleep(args.poll_s)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        reader.flush()
        deadline = time.monotonic() + 120.0
        while worker.q.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.05)
        decoder.stop = True
        thread.join(timeout=30)
        log("TOTAL %s %s dropped_partials=%d dropped_finals=%d"
            % (reader.stats(), decoder.stats_line(),
               worker.dropped_partials, worker.dropped_finals))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
