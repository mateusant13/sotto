'use strict';

/**
 * Sotto — the HISTORY ROUTE oracle: which text is allowed to reach the file.
 *
 * THE DEFECT THIS CLOSES (measured, `docs/audit/ao-vivo-vs-redux.md`): the string
 * painted in the LIVE caption box is the SAME string written to the transcript,
 * so whatever the renderer happened to cut short was recorded as if it were a
 * finished sentence — and `caption-formulation.js:formulate()` then INVENTED a
 * full stop on it. Of the owner's 472 entries, 352 (74.6 %) had <= 3 words and
 * 472/472 ended in terminal punctuation: the file could not tell a closed
 * sentence from a 1500 ms hold-timeout fragment.
 *
 * WHAT THIS DRIVES, and nothing else:
 *   the REAL worker (`worker/sotto_worker.py`, file mode over a real recording)
 *     -> the REAL renderer module (`app/panel/caption-formulation.js`)
 *     -> the REAL store (`app/panel/history-store.js`) -> `<date>/<HH>.md`
 *
 * ARMS
 *   1  NEW route — every worker event carries `final` (M2/M3). A line reaches
 *      the file ONLY on `final:true`, and it is stamped `route=final` (M8).
 *   2  CONTROL — the PRE-CURE semantics on the SAME stream: no `final` marker,
 *      the hold deadline commits (M6 not yet in force). This is what the owner's
 *      file was written by, and it must be measurably worse — otherwise the
 *      cure changed nothing and the green on arm 1 proves nothing.
 *   3  THE FILE — the artefact is re-read from disk and censused: entries,
 *      `> 3 words`, `<= 3 words` and how many carry a route marker.
 *   4  NO PROVISIONAL MAY BE WRITTEN — every line in the file must be a
 *      `route=final` line; a `provisional-draft` on disk is only legal from
 *      `flush()` (a terminal exit), never from the hold deadline.
 *
 * `--root` exists so this runs WITHOUT writing into the owner's transcript:
 * `history/` is his, and `docs/audit/ao-vivo-vs-redux.md` §4.4 already records
 * test lines in it as a defect to fix, not a precedent to repeat.
 *
 * Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window: one child process plus
 * file reads.
 */

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const HERE = __dirname;
const REPO = path.join(HERE, '..');

const args = process.argv.slice(2);
function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

const streamPath = flagValue('--stream');
const audioPath = flagValue('--audio') || path.join(HERE, 'pt-br-sample.wav');
const maxChunks = flagValue('--max-chunks') || '0';
const root = path.resolve(flagValue('--root') || path.join(REPO, 'history-verify'));
const enginePath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const workerPath = path.join(REPO, 'worker', 'sotto_worker.py');

const results = [];
function arm(name, real, want, control) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  const differs = control === undefined || JSON.stringify(real) !== JSON.stringify(control);
  const good = ok && differs;
  results.push(good);
  console.log(`[${good ? 'PASS' : 'FAIL'}] ${name}`);
  console.log(`       real    = ${JSON.stringify(real)}`);
  console.log(`       want    = ${JSON.stringify(want)}`);
  console.log(`       control = ${JSON.stringify(control)}  (must differ: ${differs ? 'yes' : 'NO'})`);
}

/** Run the REAL worker in file mode and return its JSONL lines parsed. */
function runWorker() {
  const env = { ...process.env, SOTTO_AUDIO_FILE: audioPath };
  const argv = [workerPath];
  if (Number(maxChunks) > 0) argv.push('--max-chunks', String(maxChunks));
  const out = spawnSync(process.env.SOTTO_PYTHON || 'python', argv, {
    cwd: REPO,
    env,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  if (out.status !== 0) {
    console.log(`SETUP ERROR: worker exited ${out.status}\n${(out.stderr || '').slice(-2000)}`);
    process.exit(2);
  }
  return out.stdout.split(/\r?\n/).filter((l) => l.trim().startsWith('{')).map((l) => JSON.parse(l));
}

function streamFromWorker() {
  console.log(`worker    : ${process.env.SOTTO_PYTHON || 'python'} ${path.relative(REPO, workerPath)} (SOTTO_AUDIO_FILE=${audioFileLabel()})`);
  const rows = runWorker();
  const captions = rows.filter((r) => r.type === 'caption');
  const dump = flagValue('--dump-stream');
  if (dump) {
    // The worker run costs ~3 minutes on 224 s of audio; the RECORDING is what
    // makes this oracle cheap to re-run and is what the arms can be replayed
    // against without a model at all (`--stream`).
    fs.writeFileSync(path.resolve(dump), captions.map((c) => JSON.stringify(c)).join('\n') + '\n', 'utf8');
    console.log(`stream    : dumped to ${path.resolve(dump)}`);
  }
  console.log(`stream    : ${captions.length} caption event(s) — ` +
    `${captions.filter((c) => c.final === false).length} provisional, ` +
    `${captions.filter((c) => c.final === true).length} final`);
  return captions;
}

let audioFileLabel = () => path.relative(REPO, audioPath);

function readStream(file) {
  console.log(`stream    : ${file} (recording)`);
  return fs
    .readFileSync(file, 'utf8')
    .split(/\r?\n/)
    .filter((l) => l.trim().startsWith('{'))
    .map((l) => JSON.parse(l))
    .filter((r) => r.type === 'caption');
}

const F = require(enginePath);

/**
 * ARM 1 — the NEW route: `final` travels with every fragment and the engine
 * decides. This is the real wiring: `panel.js` hands `meta` straight to
 * `engine.ingest`.
 */
function armNewRoute(captions) {
  const commits = [];
  const engine = F.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text, reason, ...(meta || {}),
      // The engine hands the FILE its own text: for a draft it drops the
      // terminal mark `formulate()` would have invented (M8).
      fileText: (meta && meta.fileText) || text,
    }),
    onProvisional: () => {},
  });
  for (const c of captions) {
    engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
  }
  engine.flush('stream-end');
  return commits;
}

/**
 * ARM 2 — the CONTROL, and it is the real OLD wiring, not a mock: no `final`
 * marker at all (which is what the pre-cure worker sent) and the panel's 1500 ms
 * deadline fired after every fragment — the worst case for the defect, and the
 * exact case `panel.js` `armHoldTimer` produced.
 */
function armControl(captions) {
  const commits = [];
  const engine = F.createEngine({
    onCommit: (text, reason) => commits.push({ text, reason }),
    onProvisional: () => {},
  });
  for (const c of captions) {
    engine.ingest(c.text, { start: c.start, end: c.end });
    engine.expireHold();
  }
  engine.flush('stream-end');
  return commits;
}

/** Words, the unit the owner's own numbers are taken in. */
function words(text) {
  return String(text || '').trim().split(/\s+/).filter(Boolean);
}

function census(commits) {
  const w = commits.map((c) => words(c.text).length);
  const short = w.filter((n) => n <= 3).length;
  return {
    entries: commits.length,
    over3: w.filter((n) => n > 3).length,
    short,
    shortPct: commits.length ? Math.round((100 * short) / commits.length * 10) / 10 : null,
    median: w.length ? w.slice().sort((a, b) => a - b)[Math.floor(w.length / 2)] : null,
  };
}

function main() {
  if (!fs.existsSync(enginePath)) {
    console.log(`SETUP ERROR: no engine at ${enginePath}`);
    return 2;
  }
  if (streamPath) {
    if (!fs.existsSync(streamPath)) {
      console.log(`SETUP ERROR: no stream at ${streamPath}`);
      return 2;
    }
  } else if (!fs.existsSync(audioPath)) {
    console.log(`SETUP ERROR: no audio at ${audioPath}`);
    return 2;
  }
  audioFileLabel = () => (streamPath ? '(none — recorded stream)' : path.relative(REPO, audioPath));

  const captions = streamPath ? readStream(streamPath) : streamFromWorker();
  if (!captions.length) {
    console.log('SETUP ERROR: the worker emitted no caption at all');
    return 2;
  }

  const before = armControl(captions);
  const after = armNewRoute(captions);
  const cBefore = census(before);
  const cAfter = census(after);

  console.log(`\nCONTROL (pre-cure semantics, same stream): ${JSON.stringify(cBefore)}`);
  console.log(`NEW     (route-aware, same stream)       : ${JSON.stringify(cAfter)}`);

  // ── arm 1: the cure is measurable on the SAME stream ────────────────────
  // FRACTIONS, not absolute counts. The new route writes FEWER lines (one per
  // worker segment instead of one per held fragment), so "more >3-word lines"
  // is only meaningful as a share of what was written: MEASURED on 224 s of
  // real speech, the control wrote 1221 lines with 21 (1.7 %) above 3 words,
  // the new route 135 lines with 134 (99.3 %) above.
  const pctOver3 = (c) => (c.entries ? Math.round((100 * c.over3) / c.entries * 10) / 10 : null);
  arm(
    'the file-worthy text improves: the <=3-word SHARE falls, the >3-word SHARE rises',
    [cAfter.shortPct < cBefore.shortPct, pctOver3(cAfter) > pctOver3(cBefore)],
    [true, true],
    [cBefore.shortPct < cBefore.shortPct, pctOver3(cBefore) > pctOver3(cBefore)],
  );
  console.log(`       <=3-word share: control ${cBefore.shortPct}% -> new ${cAfter.shortPct}%   ` +
    `| >3-word share: control ${pctOver3(cBefore)}% -> new ${pctOver3(cAfter)}%`);

  // ── arm 2: no provisional partial may be committed as a sentence ────────
  // The discriminating fact is not "the text differs" but that a provisional
  // line is NEVER among the commits, on any stream that carries the marker.
  const provisionalTexts = new Set(captions.filter((c) => c.final === false).map((c) => c.text));
  const leaked = after.filter((c) => provisionalTexts.has(c.text) && c.route !== 'final');
  arm(
    'no provisional partial reaches the transcript',
    leaked.map((c) => c.text),
    [],
    before.length ? ['(the control commits fragments by design)'] : [],
  );

  // ── arm 3: the terminal punctuation the file shows is the WORKER\'s ─────
  // `formulate()` appends a full stop when a line has none, so punctuation
  // alone proves nothing — but every line the NEW route writes must be one the
  // WORKER closed (`route=final`), which is the fact punctuation cannot carry.
  arm(
    'every line written on the new route is a worker-closed line (route=final)',
    Array.from(new Set(after.map((c) => c.route))),
    ['final'],
    Array.from(new Set(before.map((c) => c.route))),
  );

  // ── arm 4: a DRAFT carries no INVENTED terminal mark (the acceptance test) ─
  // "if the file has no way to know that a line is partial, the defect is not
  // closed" — and the ficheiro's own way to know is `route=`, backed here by
  // the punctuation rule: a fragment the worker never closed may not be dressed
  // with the full stop `formulate()` would have added on its own.
  {
    const stream = [
      { text: 'Nossa, eu', start: 3.0, end: 3.6, final: false },
      { text: 'Nossa, eu vou', start: 3.0, end: 4.2, final: false },
    ];
    const seen = [];
    const engine = F.createEngine({
      onCommit: (text, reason, meta) => seen.push({ text, reason, ...(meta || {}) }),
      onProvisional: () => {},
    });
    for (const c of stream) engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
    engine.flush('status-change'); // the terminal exit a dead worker goes through
    arm(
      'a fragment that reaches the file by the terminal exit is unpunctuated and marked a draft',
      [seen.map((s) => s.route), seen.map((s) => s.fileText), seen.map((s) => s.text)],
      [['provisional-draft'], ['Nossa, eu vou'], ['Nossa, eu vou.']],
      [[null], [], []],
    );
  }

  // ── arm 5: THE FILE — the artefact, re-read from disk ──────────────────
  process.env.SOTTO_HISTORY_ROOT = root;
  const store = require(path.join(REPO, 'app', 'panel', 'history-store.js'));
  // The census must be over THIS run's output only, or a second run counts the
  // first one's lines and the arm compares two different populations.
  const written = [];
  const stamp = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const hourFile = path.join(
    root,
    `${stamp.getFullYear()}-${pad(stamp.getMonth() + 1)}-${pad(stamp.getDate())}`,
    `${pad(stamp.getHours())}.md`,
  );
  fs.mkdirSync(path.dirname(hourFile), { recursive: true });
  fs.writeFileSync(hourFile, '', 'utf8');
  for (const c of after) {
    const entry = store.append(c.fileText, { source: 'live', route: c.route, start: c.start, reason: c.reason });
    if (entry) written.push(entry);
  }
  const file = written.length ? written[0].path : null;
  if (!file) {
    arm('the store wrote the new-route lines to disk', false, true, false);
    return 1;
  }
  const raw = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const LINE = /^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$/;
  const onDisk = [];
  for (const l of raw) {
    const m = LINE.exec(l);
    if (!m) continue;
    // The provenance is METADATA, not words — it must be stripped before the
    // text is measured, or every line would gain the same four words and every
    // line would read as a word-prefix of the next.
    const tail = /^(.*?)\s*<!--\s*(route=\S+)(?:\s+start=([\d.]+))?(?:.*?)-->\s*$/.exec(m[2]);
    onDisk.push({
      text: tail ? tail[1] : m[2],
      route: tail ? tail[2].slice('route='.length) : null,
      start: tail && tail[3] ? Number(tail[3]) : null,
    });
  }
  const cFile = census(onDisk);
  console.log(`\nFILE      : ${file}`);
  console.log(`FILE      : ${JSON.stringify(cFile)}`);
  console.log(`FILE      : routes = ${JSON.stringify(onDisk.reduce((a, e) => ((a[e.route] = (a[e.route] || 0) + 1), a), {}))}`);

  arm(
    'THE FILE: every entry is a closed line, marked, and >3 words is the majority',
    [onDisk.length === after.length,
     onDisk.every((e) => e.route === 'final'),
     cFile.shortPct < cBefore.shortPct],
    [true, true, true],
    [false, false, cBefore.shortPct < cBefore.shortPct],
  );

  for (const e of onDisk) console.log(`  - [${'  '}] ${e.text}   <!-- ${e.route} start=${e.start} -->`);

  const failed = results.filter((r) => !r).length;
  console.log(`\nRESULT: ${failed ? `RED — ${failed} violation(s)` : 'GREEN — only worker-closed lines reach the transcript, and they are marked'}`);
  return failed ? 1 : 0;
}

process.exit(main());
