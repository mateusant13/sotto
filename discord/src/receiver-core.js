// The receiving core shared by the live Discord path and the synthetic harness.
//
// Contract (both callers use it identically):
//   map.bind(ssrc, userId)              -> SSRC -> Discord user id
//   tap.ingest({ ssrc, opus, tMs })     -> one Opus packet, tagged with its SSRC
//
// The tap owns, per SPEAKER STREAM, one Opus decoder and one open file pair:
//   <out>/<user_id>/<epoch_ms>.pcm    raw PCM s16le, 16 kHz, mono, continuous
//   <out>/<user_id>/<epoch_ms>.jsonl  one row per packet + segment close
// A decoder is never created per packet and never duplicated per packet; the
// stats counter `decoders` proves how many were actually constructed.
import fs from 'node:fs';
import path from 'node:path';
// @discordjs/opus is CJS and exports its class on the module object only.
import OpusModule from '@discordjs/opus';

const { OpusEncoder } = OpusModule;

export const SAMPLE_RATE = 16000;
export const CHANNELS = 1;
export const BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * 2;

const USER_ID_RE = /^\d+$/;

/** SSRC -> user id, and back. Fed by the live receiver's ssrcMap events, or by
 * the harness directly. Rebinding the same pair is a no-op; rebinding an SSRC
 * to a new user (Discord does this after a reconnect) is logged and applied. */
export class SsrcMap {
  constructor(log = () => {}) {
    this.bySsrc = new Map();
    this.byUser = new Map();
    this.log = log;
  }

  /** @returns {boolean} true when the mapping changed (so the caller can log once) */
  bind(ssrc, userId, source = 'unknown') {
    const s = Number(ssrc);
    const u = String(userId);
    if (!Number.isInteger(s) || s <= 0) throw new TypeError(`invalid SSRC: ${ssrc}`);
    if (!USER_ID_RE.test(u)) throw new TypeError(`invalid user id: ${userId}`);
    const previous = this.bySsrc.get(s);
    if (previous === u) return false;
    this.bySsrc.set(s, u);
    this.byUser.set(u, s);
    this.log(`SSRC_MAP ssrc=${s} user=${u} source=${source} previous=${previous ?? 'none'}`);
    return true;
  }

  userIdFor(ssrc) {
    return this.bySsrc.get(Number(ssrc));
  }

  ssrcFor(userId) {
    return this.byUser.get(String(userId));
  }

  entries() {
    return [...this.bySsrc.entries()].map(([ssrc, userId]) => ({ ssrc, userId }));
  }
}

function openUnique(basePath) {
  for (let n = 0; n < 1000; n += 1) {
    const base = n === 0 ? basePath : `${basePath}-${n}`;
    try {
      return { base, fd: fs.openSync(`${base}.pcm`, 'wx') };
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;
    }
  }
  throw new Error(`cannot allocate a segment file for ${basePath}`);
}

/**
 * Per-speaker PCM tap.
 *
 * segmentMs > 0 rolls a new file every N ms; gapMs > 0 rolls when a speaker is
 * silent for N ms. Both default to 0: one continuous segment per speaker per run.
 */
export class PcmTap {
  constructor({ outDir, segmentMs = 0, gapMs = 0, log = () => {} }) {
    this.outDir = path.resolve(outDir);
    this.segmentMs = segmentMs;
    this.gapMs = gapMs;
    this.log = log;
    this.map = new SsrcMap(log);
    this.speakers = new Map();
    this.stats = { packets: 0, decoders: 0, bytes: 0, segments: 0, unknownSsrc: 0, decodeErrors: 0 };
  }

  _stateFor(ssrc) {
    const userId = this.map.userIdFor(ssrc);
    if (!userId) return null;
    let state = this.speakers.get(userId);
    if (!state) {
      state = {
        userId,
        ssrc: Number(ssrc),
        // ONE decoder for this speaker stream, reused for every packet.
        decoder: new OpusEncoder(SAMPLE_RATE, CHANNELS),
        segment: null,
        lastPacketMs: -Infinity,
      };
      this.stats.decoders += 1;
      this.speakers.set(userId, state);
      this.log(`SPEAKER_OPEN user=${userId} ssrc=${ssrc} decoder=opus/${SAMPLE_RATE}Hz/${CHANNELS}ch`);
    }
    return state;
  }

  _openSegment(state, tMs) {
    const stamp = Math.trunc(tMs);
    const dir = path.join(this.outDir, state.userId);
    fs.mkdirSync(dir, { recursive: true });
    const { base, fd } = openUnique(path.join(dir, String(stamp)));
    const indexFd = fs.openSync(`${base}.jsonl`, 'wx');
    fs.writeSync(
      indexFd,
      `${JSON.stringify({
        type: 'segment',
        user_id: state.userId,
        ssrc: state.ssrc,
        started_at_ms: stamp,
        sample_rate: SAMPLE_RATE,
        channels: CHANNELS,
        format: 's16le',
      })}\n`,
    );
    const segment = { base, fd, indexFd, startedAtMs: stamp, bytes: 0, samples: 0, packets: 0 };
    state.segment = segment;
    this.stats.segments += 1;
    this.log(`SEGMENT_OPEN user=${state.userId} ssrc=${state.ssrc} file=${path.relative(this.outDir, `${base}.pcm`)}`);
    return segment;
  }

  _closeSegment(state) {
    const segment = state.segment;
    if (!segment) return;
    fs.writeSync(
      segment.indexFd,
      `${JSON.stringify({
        type: 'close',
        t_ms: Date.now(),
        duration_ms: Math.round((segment.samples / SAMPLE_RATE) * 1000),
        pcm_bytes: segment.bytes,
        samples: segment.samples,
        packets: segment.packets,
      })}\n`,
    );
    fs.closeSync(segment.fd);
    fs.closeSync(segment.indexFd);
    this.log(
      `SEGMENT_CLOSE user=${state.userId} file=${path.relative(this.outDir, `${segment.base}.pcm`)} ` +
        `duration_ms=${Math.round((segment.samples / SAMPLE_RATE) * 1000)} packets=${segment.packets}`,
    );
    state.segment = null;
  }

  /**
   * Feed one Opus packet tagged with its SSRC.
   * @returns {{userId: string, pcmBytes: number, samples: number} | null}
   */
  ingest({ ssrc, opus, tMs = Date.now() }) {
    if (!opus || opus.length === 0) return null;
    const state = this._stateFor(ssrc);
    if (!state) {
      this.stats.unknownSsrc += 1;
      this.log(`PACKET_UNMAPPED ssrc=${ssrc} bytes=${opus.length}`);
      return null;
    }

    let pcm;
    try {
      pcm = state.decoder.decode(opus);
    } catch (err) {
      this.stats.decodeErrors += 1;
      this.log(`DECODE_ERROR user=${state.userId} ssrc=${ssrc} bytes=${opus.length} error=${err.message}`);
      return null;
    }
    if (!pcm || pcm.length === 0) return null;

    const now = Math.trunc(tMs);
    if (
      !state.segment ||
      (this.segmentMs > 0 && now - state.segment.startedAtMs >= this.segmentMs) ||
      (this.gapMs > 0 && now - state.lastPacketMs >= this.gapMs)
    ) {
      this._closeSegment(state);
      this._openSegment(state, now);
    }

    const segment = state.segment;
    fs.writeSync(segment.fd, pcm);
    const samples = pcm.length / 2;
    segment.bytes += pcm.length;
    segment.samples += samples;
    segment.packets += 1;
    state.lastPacketMs = now;

    fs.writeSync(
      segment.indexFd,
      `${JSON.stringify({
        type: 'packet',
        t_ms: now,
        seq: segment.packets - 1,
        ssrc: Number(ssrc),
        user_id: state.userId,
        opus_bytes: opus.length,
        pcm_bytes: pcm.length,
        samples,
      })}\n`,
    );

    this.stats.packets += 1;
    this.stats.bytes += pcm.length;
    return { userId: state.userId, pcmBytes: pcm.length, samples };
  }

  closeAll() {
    for (const state of this.speakers.values()) this._closeSegment(state);
  }
}
