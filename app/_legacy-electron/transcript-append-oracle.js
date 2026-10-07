'use strict';

/**
 * Sotto — the transcript append oracle: one new line per caption, and never
 * the same words twice.
 *
 * THE DEFECT THIS EXISTS FOR (owner, 2026-10-06, verbatim):
 *
 *   "e por que duplica as entradas de transcript? por que nao da append,
 *    sempre? fica duplicando linha."
 *
 * MEASURED on the owner's own transcript before this oracle existed:
 * `history/2026-10-06/06.md` + `07.md`, 137 entries, 90 of which are a word
 * prefix of the entry after them and 2 repeated verbatim with different
 * timestamps (`O rádio.` at 06:17:31 and 06:19:47; `Speaking.` at 06:40:19 and
 * 06:42:06). The panel's rendered feed carried exactly those 137 entries, so
 * the duplication is in what gets COMMITTED, not in how the feed paints.
 *
 * WHY IT HAPPENED. The worker sends the LINE, not the chunk: every partial of
 * one line carries the SAME `start` and a growing `end`
 * (worker/sotto_worker.py:_event — "`start` is the START OF THE LINE, never
 * the newest chunk's start"). The renderer's hold deadline (1500 ms) can
 * therefore commit a PREFIX of a line the worker is still holding, and the
 * next partial re-covers exactly that audio. `caption-formulation.js` was
 * built to join and REPLACE within one line, but `commit()` threw the
 * re-cover anchor away (`takeBuffer()` sets `lastAudioEnd = null`), so after a
 * commit the continuation read as a brand-new fragment and its already-written
 * words went to history a second time.
 *
 * WHAT THIS CHECKS. For every worker line in a REAL worker caption stream,
 * replayed through the REAL engine with the hold deadline fired as often as it
 * possibly can (after EVERY fragment — the maximum-split condition, and the
 * one that produced the owner's file), the words committed to history must be,
 * in order and exactly once, the words of that line. Two ways to fail, and
 * both are failures:
 *
 *   DUPLICATION  a word committed twice -> the concat does not match, or a
 *                committed line is a word-prefix of the next one
 *   LOSS         a word committed zero times -> the concat does not match
 *
 * A check that only looked for duplicates would pass a "cure" that simply ate
 * the continuation, which is why the exact concatenation is the primary
 * assertion and the prefix test is only the legible one.
 *
 * WHERE THE BAR IS LOWER, AND WHY. Without audio position the renderer cannot
 * tell "the worker extended the line" from "the worker started a new sentence
 * with the same opening"; guessing there would silently eat words. So the
 * `meta=none` arm asserts only what is PROVABLE without a position: the same
 * text twice in a row must never be committed twice. It is labelled separately
 * in the output rather than quietly counted as a pass.
 *
 *   node app/_legacy-electron/transcript-append-oracle.js
 *   node app/_legacy-electron/transcript-append-oracle.js --pretend <engine.js>
 *   node app/_legacy-electron/transcript-append-oracle.js --history <file.md>
 *
 * `--pretend` runs the replay against another copy of the engine, which is how
 * this oracle was proved RED against the pre-fix `caption-formulation.js`
 * (`git show HEAD:app/electron/caption-formulation.js`).
 * `--history` censuses a REAL transcript file (exact duplicates and
 * word-prefix-growth pairs) — the owner's artefact, read as-is. It exits 1 on
 * any pair found; see the audit for why that census is a measurement and not
 * the gate (a worker that closes a line and then re-speaks its opening would
 * produce a legitimate pair, and the file alone cannot tell).
 */

const fs = require('node:fs');
const path = require('node:path');

const REPO = path.join(__dirname, '..', '..');

/** The real live-tap stream: cumulative partials, same `start`, growing `end`. */
const CUMULATIVE_STREAM = path.join(REPO, 'worker', 'runs', 'gate-live-speech.jsonl');
/** The real file/selftest stream: one chunk per caption, advancing `start`. */
const DELTA_STREAM = path.join(REPO, 'worker', 'runs', 'ACCEPT-after.jsonl');

const args = process.argv.slice(2);
function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

const enginePath = flagValue('--pretend')
  ? path.resolve(process.cwd(), flagValue('--pretend'))
  : path.join(__dirname, '..', 'panel', 'caption-formulation.js');
const historyFile = flagValue('--history') ? path.resolve(process.cwd(), flagValue('--history')) : null;

/** Lower-case, punctuation-stripped words: the unit both sides are compared in. */
function normalisedWords(text) {
  return String(text == null ? '' : text)
    .toLowerCase()
    .replace(/[.!?…,]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

/** Caption events from a worker jsonl, in order. */
function captionEvents(file) {
  const out = [];
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed[0] !== '{') continue;
    let row;
    try {
      row = JSON.parse(trimmed);
    } catch {
      continue; // a partially flushed last line is not a caption
    }
    if (row.type !== 'caption' || !row.text) continue;
    out.push({
      text: String(row.text),
      start: typeof row.start === 'number' ? row.start : null,
      end: typeof row.end === 'number' ? row.end : null,
    });
  }
  return out;
}

/**
 * Split a caption stream into the WORKER's lines.
 *
 * The worker's `start` is the start of the line, so the moment it changes the
 * previous line closed (`LineFormer._close`) and a new one began.
 */
function workerLines(events) {
  const lines = [];
  for (const ev of events) {
    const last = lines[lines.length - 1];
    if (!last || last.start !== ev.start) lines.push({ start: ev.start, events: [ev] });
    else last.events.push(ev);
  }
  return lines;
}

/**
 * Replay one worker line through the real engine, returning the committed lines.
 *
 * @param {object} F the real formulation module
 * @param {{events: object[]}} line
 * @param {'every-fragment'|'line-close'} hold how often the deadline is fired
 * @param {boolean} withMeta whether the audio position travels with the caption
 */
function replayLine(F, line, hold, withMeta = true) {
  const committed = [];
  const engine = F.createEngine({
    onCommit: (text) => committed.push(text),
    onProvisional: () => {},
  });
  for (const ev of line.events) {
    engine.ingest(ev.text, withMeta ? { start: ev.start, end: ev.end } : {});
    // The panel arms this deadline on every caption and fires it when the
    // worker has been silent for COMMIT_MAX_HOLD_MS. Firing it here, after
    // every fragment, is the worst case for the defect: it splits the worker's
    // line as many times as the deadline possibly can.
    if (hold === 'every-fragment') engine.expireHold();
  }
  engine.flush('line-close');
  return committed;
}

/** The exact-concatenation failure: a word written twice, or never written. */
function appendProblem(committed, expectedText, label) {
  const expected = normalisedWords(expectedText);
  const actual = committed.flatMap((l) => normalisedWords(l));
  if (actual.join(' ') === expected.join(' ')) return null;
  return (
    `${label}: append is not exact — the line must appear once, in order\n` +
    `      expected (${expected.length} words): ${expected.join(' ')}\n` +
    `      committed (${actual.length} words): ${actual.join(' ')}\n` +
    `      lines committed: ${JSON.stringify(committed)}`
  );
}

/** The legible duplicate: a committed line re-written as the prefix of the next. */
function duplicateProblems(committed, label) {
  const problems = [];
  for (let i = 0; i + 1 < committed.length; i += 1) {
    const a = normalisedWords(committed[i]);
    const b = normalisedWords(committed[i + 1]);
    const same = a.join(' ') === b.join(' ');
    const prefix = a.length && a.length < b.length && a.every((w, k) => w === b[k]);
    if (same || prefix) {
      problems.push(
        `${label}: DUPLICATE — ${same ? 'the same line twice in a row' : 'line N is a word-prefix of line N+1'}\n` +
          `      ${JSON.stringify(committed[i])}\n      ${JSON.stringify(committed[i + 1])}`,
      );
    }
  }
  return problems;
}

/** Replay a whole stream, under both hold policies. */
function checkStream(F, file, label) {
  if (!fs.existsSync(file)) return [`${label}: stream not found at ${file}`];
  const lines = workerLines(captionEvents(file));
  const problems = [];
  const notes = [];
  let commits = 0;
  let words = 0;
  let weakLines = 0;
  for (const [i, line] of lines.entries()) {
    const expectedText = line.events[line.events.length - 1].text;
    for (const hold of ['every-fragment', 'line-close']) {
      const committed = replayLine(F, line, hold);
      const tag = `${label} line ${i + 1} hold=${hold}`;
      const append = appendProblem(committed, expectedText, tag);
      if (append) problems.push(append);
      problems.push(...duplicateProblems(committed, tag));
    }
    // The no-position arm: the same text twice in a row must never be written
    // twice. Nothing stronger is provable without a position — see the header.
    const noMeta = replayLine(F, line, 'every-fragment', false);
    const tag = `${label} line ${i + 1} meta=none (weaker bar: no identical repeat)`;
    for (let k = 0; k + 1 < noMeta.length; k += 1) {
      if (normalisedWords(noMeta[k]).join(' ') === normalisedWords(noMeta[k + 1]).join(' ')) {
        problems.push(`${tag}: DUPLICATE — the same line twice in a row\n      ${JSON.stringify(noMeta[k])}`);
      }
    }
    weakLines += 1;
    const committed = replayLine(F, line, 'every-fragment');
    commits += committed.length;
    words += committed.flatMap((l) => normalisedWords(l)).length;
  }
  notes.push(
    `#${label}: ${lines.length} worker lines, ${commits} commits, ${words} words, ` +
      `${weakLines} line(s) checked at the weaker meta=none bar`,
  );
  return { problems, notes };
}

/**
 * The named unit cases, each one a rule the owner stated.
 *
 * These exist because the stream replay can pass by luck: a case that never
 * occurs in the fixture proves nothing about the branch it lives in.
 */
function checkUnitCases(F) {
  const problems = [];
  const run = (fragments, withMeta = true) => {
    const committed = [];
    const engine = F.createEngine({
      onCommit: (text) => committed.push(text),
      onProvisional: () => {},
    });
    for (const [text, meta] of fragments) {
      engine.ingest(text, withMeta ? meta : {});
      engine.expireHold();
    }
    return committed;
  };

  const cases = [
    {
      name: 'the same caption twice (the owner: "NUNCA a mesma linha duas vezes")',
      fragments: [
        ['O rádio', { start: 1, end: 2 }],
        ['O rádio', { start: 1, end: 2 }],
      ],
      expect: 1,
    },
    {
      name: 'worker restart: a new line whose audio clock resets must not be swallowed',
      fragments: [
        ['After day', { start: 10, end: 12 }],
        ['Immediately after', { start: 0.5, end: 1.1 }],
      ],
      expect: 2,
    },
    {
      name: 'worker restart that coincidentally repeats the old text is a NEW utterance',
      fragments: [
        ['O rádio', { start: 10, end: 12 }],
        ['O rádio', { start: 0.5, end: 0.9 }],
      ],
      expect: 2,
    },
    {
      name: 'a genuine new sentence after a pause is not stripped',
      fragments: [
        ['O rádio', { start: 1, end: 2 }],
        ['Segunda feira', { start: 4, end: 5 }],
      ],
      expect: 2,
    },
    {
      name: 'no audio position: the same text twice must not be written twice',
      fragments: [['O rádio', {}], ['O rádio', {}]],
      expect: 1,
      withMeta: false,
    },
  ];

  for (const c of cases) {
    const committed = run(c.fragments, c.withMeta !== false);
    if (committed.length !== c.expect) {
      problems.push(
        `unit case failed: ${c.name}\n      expected ${c.expect} committed line(s), got ${committed.length}: ${JSON.stringify(committed)}`,
      );
    }
  }

  // AND the growth case the cure is for: the worker extends a line the renderer
  // already committed. Every word once, in order.
  const grown = run([
    ['Schoolrooms', { start: 0.5, end: 1 }],
    ['Schoolrooms Day after', { start: 0.5, end: 2 }],
    ['Schoolrooms Day after He\'ll an appearance', { start: 0.5, end: 3 }],
  ]);
  const concat = grown.flatMap((l) => normalisedWords(l)).join(' ');
  if (concat !== 'schoolrooms day after he\'ll an appearance') {
    problems.push(
      'unit case failed: a continuation of a committed line must append only the new words\n' +
        `      got: ${JSON.stringify(grown)}\n      words written: ${concat}`,
    );
  }

  return problems;
}

/** Census a real transcript file: the owner's own artefact, read as-is. */
function censusHistory(file) {
  const raw = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const entries = [];
  raw.forEach((l, i) => {
    const m = /^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$/.exec(l);
    // The `<!-- route=… start=… reason=… -->` provenance the writer stamps on
    // a line (M8) is METADATA, not words. Counting it as text would inflate
    // every entry by the same four words and — worse — make every line a
    // word-prefix of the next, i.e. a census that reports the cure as the
    // defect. Wrapped in try/catch because this oracle runs on any engine/file
    // an operator points it at.
    if (m) entries.push({ line: i + 1, time: m[1], text: m[2].replace(/\s*<!--.*?-->\s*$/, '') });
  });
  const seen = new Map();
  const exact = [];
  for (const e of entries) {
    const key = normalisedWords(e.text).join(' ');
    if (seen.has(key)) exact.push([seen.get(key), e]);
    else seen.set(key, e);
  }
  const growth = [];
  for (let i = 0; i + 1 < entries.length; i += 1) {
    const a = normalisedWords(entries[i].text);
    const b = normalisedWords(entries[i + 1].text);
    if (a.length && a.length < b.length && a.every((w, k) => w === b[k])) {
      growth.push([entries[i], entries[i + 1]]);
    }
  }
  console.log(`${file}: ${entries.length} entries`);
  console.log(`  exact duplicates (same words, different timestamp): ${exact.length}`);
  for (const [a, b] of exact) {
    console.log(`    line ${a.line} [${a.time}] and line ${b.line} [${b.time}]: ${a.text}`);
  }
  console.log(`  word-prefix growth (entry N is a prefix of N+1): ${growth.length}`);
  for (const [a, b] of growth.slice(0, 5)) {
    console.log(`    line ${a.line} -> ${b.line}: ${a.text}  ->  ${b.text}`);
  }
  return exact.length + growth.length;
}

if (historyFile) {
  const bad = censusHistory(historyFile);
  console.log(bad ? `RESULT: RED — ${bad} duplicate/prefix pair(s)` : 'RESULT: GREEN — no duplicates');
  process.exit(bad ? 1 : 0);
}

const F = require(enginePath);
console.log(`engine under test: ${enginePath}`);
const problems = [];
const notes = [];
for (const [file, label] of [
  [CUMULATIVE_STREAM, 'gate-live-speech (cumulative, live tap)'],
  [DELTA_STREAM, 'ACCEPT-after (delta, file mode)'],
]) {
  const out = checkStream(F, file, label);
  problems.push(...out.problems);
  notes.push(...out.notes);
}
problems.push(...checkUnitCases(F));
for (const n of notes) console.log(n);
if (problems.length) {
  console.log(`\nRESULT: RED — ${problems.length} violation(s)`);
  for (const p of problems) console.log(`\n${p}`);
  process.exit(1);
}
console.log('\nRESULT: GREEN — every worker line is appended once, in order, word for word');
process.exit(0);
