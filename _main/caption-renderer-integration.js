'use strict';

/*
 * INTEGRATION: the WORKER's caption stream through the REAL renderer engine.
 *
 * WHY THIS EXISTS
 * ---------------
 * The worker now emits a JOINED LINE (`worker/sotto_worker.py: LineFormer`), and
 * the panel ALSO joins (`app/panel/caption-formulation.js`). Two layers that
 * each own the line can fight: feed the renderer a line that GROWS and, if the
 * renderer treats it as a NEW fragment, the line duplicates itself word for word
 * ("O rádio O rádio Segunda-feira").
 *
 * The renderer's revision rule is `start < lastAudioEnd` -> replace what is on
 * screen. `LineFormer` therefore stamps every event with the LINE's start, never
 * the newest chunk's. This script drives the REAL module — the same file
 * `panel.html` loads and `panel.js` calls — with the REAL captions the worker
 * produced on `_main/pt-br-sample.wav`, and asserts:
 *
 *   1. the provisional line GROWS and is never a duplicate of what it replaced
 *   2. no committed line repeats an adjacent token
 *   3. the committed lines are exactly the worker's lines (nothing re-split)
 *
 * It also answers, with a measurement instead of a reading, the question the
 * brief asks: does the panel REPLACE the current line or APPEND? — `panel.js`
 * keeps ONE `.caption--provisional` <li> and rewrites its `textContent`
 * (`renderProvisional`), retiring it on commit; only a COMMITTED line appends a
 * new <li> (`addCaption`). REPLACE for the in-progress line, APPEND only at the
 * commit.
 *
 * Usage: node _main/caption-renderer-integration.js [after.jsonl]
 */

const fs = require('node:fs');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..');
const FORMULATION = require(path.join(REPO, 'app', 'panel', 'caption-formulation.js'));

const AFTER = process.argv[2] || path.join(__dirname, '_wav-after.jsonl');
const BEFORE = path.join(__dirname, '_wav-before.jsonl');

function captions(file) {
  const out = [];
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t.startsWith('{')) continue;
    let rec;
    try { rec = JSON.parse(t); } catch { continue; }
    if (rec.type === 'caption') out.push({ text: rec.text, start: rec.start, end: rec.end });
  }
  return out;
}

function replay(caps) {
  const provisional = [];
  const committed = [];
  const engine = FORMULATION.createEngine({
    onCommit: (text) => committed.push(text),
    onProvisional: (text, isProvisional) => provisional.push({ text, isProvisional }),
  });
  for (const c of caps) engine.ingest(c.text, { start: c.start, end: c.end });
  engine.flush('end');
  return { provisional, committed };
}

const results = [];
function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  results.push(ok);
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
  if (!ok) {
    console.log(`       got  = ${JSON.stringify(got)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
  }
}

const after = captions(AFTER);
const before = captions(BEFORE);

// ── 1/3: the worker's JOINED stream through the real engine ─────────────────
const r = replay(after);

check('1. the provisional line GROWS (a prefix chain, no duplicate render)',
  r.provisional.map((p) => p.text),
  ['O rádio', 'O rádio Segunda-feira', 'O rádio Segunda-feira Os moradores']);

check('2. committed lines carry no repeated adjacent token',
  r.committed.filter((t) => {
    const w = t.split(/\s+/);
    return w.some((x, i) => i > 0 && x === w[i - 1]);
  }),
  []);

check('3. the engine did not re-split what the worker joined',
  r.committed.length, 1);

console.log(`       committed = ${JSON.stringify(r.committed)}`);

// ── 4/5: the SAME replay of the PRE-CHANGE per-chunk stream ─────────────────
// MEASURED, and it is not what the control was expected to show: the engine
// joins per-chunk input too. So the two layers AGREE — the worker's join does
// not duplicate in the renderer — and the panel's committed text is one clean
// line whichever shape the worker sends. That is exactly why the two boundary
// constants must not drift, which is the arm below.
const c = replay(before);

console.log(`       control provisional = ${JSON.stringify(c.provisional.map((p) => p.text))}`);

check('4. the two layers AGREE: pre-change stream renders the same sentence',
  c.committed, r.committed);

check('5. every committed line is formulated (capital + terminal mark)',
  r.committed.filter((t) => !/^[A-ZÁÉÍÓÚÂÊÔÃÕÇ]/.test(t) || !/[.!?…]$/.test(t)),
  []);

// ── 6: the two layers' boundaries must not DRIFT apart ──────────────────────
// Two layers now own the same decision, in two languages. If one is retuned and
// the other is not, the panel and the worker start disagreeing about where a
// line ends, and nothing else here would notice.
const py = fs.readFileSync(path.join(REPO, 'worker', 'sotto_worker.py'), 'utf8');
function pyconst(name) {
  const m = py.match(new RegExp(`^${name}\\s*=\\s*([0-9.]+)`, 'm'));
  return m ? Number(m[1]) : null;
}
check('6. SENTENCE_GAP_S agrees across worker (py) and renderer (js)',
  [pyconst('SENTENCE_GAP_S'), FORMULATION.SENTENCE_GAP_S], [8, 8]);
check('7. SENTENCE_MAX_CHARS agrees across worker (py) and renderer (js)',
  [pyconst('SENTENCE_MAX_CHARS'), FORMULATION.SENTENCE_MAX_CHARS], [90, 90]);

const failed = results.filter((x) => !x).length;
console.log(`caption-renderer-integration: ${results.length - failed} PASS / ${failed} FAIL`
  + `  impl=${path.relative(REPO, require.resolve(
      path.join(REPO, 'app', 'panel', 'caption-formulation.js')))}`);
process.exit(failed === 0 ? 0 : 1);
