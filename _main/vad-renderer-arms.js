/**
 * Does VAD-on FEED the renderer a turn boundary, or merely gate chunks?
 *
 * Feeds the two REAL worker caption streams (the same audio, 6.0 s of digital
 * silence in the middle, use_vad off vs on) through the REAL formulation
 * engine, and prints the lines it commits plus the REASON for each. Nothing
 * here is a model: `caption-formulation.js` is the module panel.js loads.
 *
 * usage: node _main/vad-renderer-arms.js
 */
const fs = require('fs');
const path = require('path');

const mod = require(path.join(__dirname, '..', 'app', 'electron', 'caption-formulation.js'));
const { createEngine, SENTENCE_GAP_S } = mod;

function captions(tag) {
  return fs
    .readFileSync(path.join(__dirname, `vad-arm-${tag}.jsonl`), 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => JSON.parse(l))
    .filter((r) => r.type === 'caption');
}

function run(tag) {
  const lines = [];
  let now = 1000000;
  const engine = createEngine({
    onCommit: (text, reason) => lines.push({ text, reason }),
    onProvisional: () => {},
    now: () => now,
  });
  const caps = captions(tag);
  let prevEnd = null;
  let maxGap = 0;
  for (const c of caps) {
    now += 560;
    if (prevEnd !== null) maxGap = Math.max(maxGap, c.start - prevEnd);
    engine.ingest(c.text, { start: c.start, end: c.end });
    prevEnd = c.end;
  }
  // Close the stream the way a run ending does: the hold timeout.
  now += mod.COMMIT_MAX_HOLD_MS + 1000;
  engine.ingest('', { start: null, end: null });
  return { lines, caps: caps.length, maxGap };
}

console.log(`SENTENCE_GAP_S = ${SENTENCE_GAP_S} (a caption closing the line needs an AUDIO gap this big)`);
for (const tag of ['gap-off', 'gap-on']) {
  const r = run(tag);
  console.log(`\n=== ${tag}: ${r.caps} captions, largest observed audio gap ${r.maxGap.toFixed(2)}s ===`);
  for (const l of r.lines) console.log(`   [${l.reason}] ${JSON.stringify(l.text)}`);
  const gapBoundaries = r.lines.filter((l) => String(l.reason).startsWith('audio-gap')).length;
  console.log(`   lines committed ${r.lines.length}; closed by an AUDIO GAP: ${gapBoundaries}`);
}
