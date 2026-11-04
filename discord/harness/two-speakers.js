#!/usr/bin/env node
// Synthetic two-speaker harness: proves the RECEIVING core without a live call.
//
// It builds 16-bit PCM sines, encodes them to real Opus packets (48 kHz stereo,
// 20 ms frames), tags each packet with one of two distinct SSRCs, and feeds them
// through the SAME PcmTap the live Discord path uses. Then it reads the files
// back with an independent reader and computes duration, RMS and zero-crossing
// frequency from the BYTES ON DISK (not from the tap's own counters).
//
//   node harness/two-speakers.js            # expect PASS, rc=0
//   node harness/two-speakers.js --neg-arm  # collapse both SSRCs onto one user:
//                                           # the two-speaker assertion must fail
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import OpusScript from 'opusscript';
import { PcmTap, SAMPLE_RATE, BYTES_PER_SECOND } from '../src/receiver-core.js';

const NEG_ARM = process.argv.includes('--neg-arm');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_ROOT = path.resolve(HERE, '..', 'out', 'harness');
const FRAME_MS = 20;
const FRAMES_PER_CHANNEL = 960; // 20 ms at 48 kHz
const SPEAKERS = [
  { ssrc: 111111, userId: '900000000000000001', hz: 440, frames: 100, amp: 12000 },
  { ssrc: 222222, userId: '900000000000000002', hz: 660, frames: 125, amp: 9000 },
];

function log(line) {
  process.stdout.write(`${line}\n`);
}

function encodeSine(hz, amp) {
  const pcm = Buffer.alloc(FRAMES_PER_CHANNEL * 2 * 2); // stereo s16le
  for (let i = 0; i < FRAMES_PER_CHANNEL; i += 1) {
    const v = Math.round(Math.sin((2 * Math.PI * hz * i) / 48000) * amp);
    pcm.writeInt16LE(v, i * 4);
    pcm.writeInt16LE(v, i * 4 + 2);
  }
  return { pcm, encoder: new OpusScript(48000, 2, OpusScript.Application.AUDIO) };
}

function readPcmStats(file) {
  const buf = fs.readFileSync(file);
  const samples = new Int16Array(buf.buffer, buf.byteOffset, buf.length / 2);
  let sumSq = 0;
  let crossings = 0;
  let prev = 0;
  for (let i = 0; i < samples.length; i += 1) {
    const s = samples[i];
    sumSq += s * s;
    if (i > 0 && ((prev < 0 && s >= 0) || (prev >= 0 && s < 0))) crossings += 1;
    prev = s;
  }
  const durationMs = (samples.length / SAMPLE_RATE) * 1000;
  const rms = samples.length ? Math.sqrt(sumSq / samples.length) : 0;
  const freq = durationMs > 0 ? crossings / 2 / (durationMs / 1000) : 0;
  return { bytes: buf.length, samples: samples.length, durationMs, rms, freq };
}

function fail(lines, message) {
  log(lines.join('\n'));
  log(`HARNESS: FAIL ${message}`);
  process.exit(1);
}

fs.rmSync(OUT_ROOT, { recursive: true, force: true });
fs.mkdirSync(OUT_ROOT, { recursive: true });

const tap = new PcmTap({ outDir: OUT_ROOT, log });
const baseMs = Date.now();

// The mapping the live receiver learns from SPEAKING opcodes, done here directly.
tap.map.bind(SPEAKERS[0].ssrc, SPEAKERS[0].userId, 'harness');
if (NEG_ARM) {
  // Defect arm: both SSRCs resolve to ONE speaker. The two-file assertion must die.
  tap.map.bind(SPEAKERS[1].ssrc, SPEAKERS[0].userId, 'harness-neg-arm');
} else {
  tap.map.bind(SPEAKERS[1].ssrc, SPEAKERS[1].userId, 'harness');
}

const prepared = SPEAKERS.map((s) => {
  const { pcm, encoder } = encodeSine(s.hz, s.amp);
  const frames = [];
  for (let f = 0; f < s.frames; f += 1) {
    frames.push(encoder.encode(pcm, FRAMES_PER_CHANNEL));
  }
  return { ...s, opusFrames: frames, packetCount: frames.length };
});

// Interleave the two speakers frame by frame, exactly as the UDP socket does.
const totalFrames = Math.max(...prepared.map((s) => s.opusFrames.length));
for (let f = 0; f < totalFrames; f += 1) {
  for (const speaker of prepared) {
    if (f >= speaker.opusFrames.length) continue;
    const tMs = baseMs + f * FRAME_MS;
    tap.ingest({ ssrc: speaker.ssrc, opus: speaker.opusFrames[f], tMs });
  }
}
tap.closeAll();

const lines = [];
for (const entry of tap.map.entries()) {
  lines.push(`HARNESS map ssrc=${entry.ssrc} -> user=${entry.userId}`);
}
lines.push(
  `HARNESS stats packets=${tap.stats.packets} decoders_created=${tap.stats.decoders} ` +
    `segments=${tap.stats.segments} bytes=${tap.stats.bytes} unknown_ssrc=${tap.stats.unknownSsrc} ` +
    `decode_errors=${tap.stats.decodeErrors}`,
);

const expectedPackets = prepared.reduce((n, s) => n + s.packetCount, 0);
if (tap.stats.packets !== expectedPackets) fail(lines, `ingested ${tap.stats.packets}/${expectedPackets} packets`);
if (tap.stats.unknownSsrc !== 0) fail(lines, `unmapped SSRC packets: ${tap.stats.unknownSsrc}`);
if (tap.stats.decodeErrors !== 0) fail(lines, `decode errors: ${tap.stats.decodeErrors}`);

const filesByUser = new Map();
for (const userDir of fs.readdirSync(OUT_ROOT)) {
  const dir = path.join(OUT_ROOT, userDir);
  if (!fs.statSync(dir).isDirectory()) continue;
  filesByUser.set(
    userDir,
    fs.readdirSync(dir).filter((n) => n.endsWith('.pcm')).map((n) => path.join(dir, n)),
  );
}

if (!NEG_ARM) {
  if (filesByUser.size !== 2) fail(lines, `expected 2 speaker directories, got ${filesByUser.size}`);
  if (tap.stats.decoders !== 2) fail(lines, `expected one decoder per stream (2), got ${tap.stats.decoders}`);
}

const results = [];
for (const speaker of prepared) {
  const files = filesByUser.get(speaker.userId) ?? [];
  if (!NEG_ARM && files.length !== 1) fail(lines, `user ${speaker.userId} has ${files.length} pcm files, expected 1`);
  if (files.length === 0) continue;
  for (const file of files) {
    const st = readPcmStats(file);
    results.push({ speaker, file, st });
    lines.push(
      `HARNESS file=${path.relative(process.cwd(), file)} duration_ms=${st.durationMs.toFixed(2)} ` +
        `bytes=${st.bytes} samples=${st.samples} rms=${st.rms.toFixed(1)} zero_cross_hz=${st.freq.toFixed(1)}`,
    );
  }
}

if (NEG_ARM) {
  const collapsed = filesByUser.size === 1 && results.length === 1;
  log(lines.join('\n'));
  if (collapsed) {
    log('HARNESS neg-arm collapsed both SSRCs into one speaker directory as designed');
    log('NEG-ARM: PASS (the two-speaker assertion caught it)');
    process.exit(1);
  }
  log('NEG-ARM: FAIL (mutant was not caught)');
  process.exit(0);
}

for (const { speaker, st } of results) {
  const expectedMs = speaker.frames * FRAME_MS;
  if (Math.abs(st.durationMs - expectedMs) > 1) fail(lines, `${speaker.userId} duration ${st.durationMs} != ${expectedMs}`);
  if (st.bytes !== st.samples * 2) fail(lines, `${speaker.userId} odd byte count`);
  if (st.rms < 500) fail(lines, `${speaker.userId} RMS ${st.rms.toFixed(1)} below floor 500 (silent)`);
  if (Math.abs(st.freq - speaker.hz) / speaker.hz > 0.05) {
    fail(lines, `${speaker.userId} dominant ${st.freq.toFixed(1)} Hz != ${speaker.hz} Hz (cross-talk?)`);
  }
  if (st.bytes !== expectedMs * (BYTES_PER_SECOND / 1000)) {
    fail(lines, `${speaker.userId} byte count ${st.bytes} != ${expectedMs * (BYTES_PER_SECOND / 1000)}`);
  }
}

const rmsA = results.find((r) => r.speaker.ssrc === SPEAKERS[0].ssrc)?.st.rms ?? 0;
const rmsB = results.find((r) => r.speaker.ssrc === SPEAKERS[1].ssrc)?.st.rms ?? 0;
if (Math.abs(rmsA - rmsB) < 1) fail(lines, 'speakers are indistinguishable (identical RMS)');

log(lines.join('\n'));
log('HARNESS: PASS (2 speakers, 2 files, durations exact, RMS above floor, distinct tones)');
