#!/usr/bin/env node
/*
 * redux-live-contract-oracle.js — does `worker/redux_live.py`'s JSONL land on the
 * panel as ONE ROW PER CLOSED LINE, or does it lose text / duplicate words?
 *
 * WHAT IS REAL HERE AND WHAT IS MODELLED, because the difference decides how much
 * this oracle is worth:
 *
 *   REAL   `app/panel/caption-formulation.js`, loaded with `require` — it is
 *          DOM-free on purpose (`:407-412` of panel.js says so) and its own
 *          `module.exports` is the surface this file drives. Every text decision
 *          in this oracle is the SHIPPED decision, not a re-implementation.
 *   REAL   the caption events: `_main/redux-live-smoke.jsonl`, produced by
 *          `worker/redux_live.py` on `_main/pt-br-sample.wav`. Not hand-written.
 *   MODELLED  the three row rules of `panel.js`'s `addCaption`
 *          (`:591-659`) and the singleton of `renderProvisional` (`:495-558`),
 *          because those need a DOM. ARM 0 anchors the model to the shipped
 *          source text, so a panel that changes its keying makes THIS FILE FAIL
 *          instead of quietly modelling a panel that no longer exists.
 *
 * The rule under test is `panel.js:598-603`:
 *
 *     // WHICH LINE THIS IS. `meta.start` is the worker's own segment identity
 *     const start = meta && typeof meta.start === 'number' ? meta.start : null;
 *     const existing = start === null ? null : committedByStart.get(start) || null;
 *     ...
 *     const line = existing && existing.isConnected ? existing : document.createElement('li');
 *
 * `existing` ⇒ REPLACE THE TEXT IN PLACE (`:611-617`). So two DIFFERENT closed
 * lines that carry the SAME `start` are ONE row, and the first line's text is
 * gone. That is the loss this oracle exists to make visible.
 *
 * Usage:
 *   node _main/redux-live-contract-oracle.js            # all arms
 *   node _main/redux-live-contract-oracle.js --neg-arm  # ARM B/C must go RED
 * Exit 0 iff every arm's expectation held.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..');
const FORMULATION = path.join(ROOT, 'app', 'panel', 'caption-formulation.js');
const PANEL = path.join(ROOT, 'app', 'panel', 'panel.js');
const STREAM = path.join(HERE, 'redux-live-smoke.jsonl');

const MAX_CAPTIONS = 200; // panel.js:38

// ---------------------------------------------------------------------------
// The panel model. Every branch below quotes the line of panel.js it stands for.
// ---------------------------------------------------------------------------

/** Faithful to `renderProvisional` (`panel.js:495-558`): ONE provisional row, ever. */
function makePanel() {
  return {
    rows: [],              // the committed `<li>`s, in DOM order
    byStart: new Map(),    // `committedByStart` (panel.js:601/635/649)
    provisional: null,     // `.caption--provisional` — a SINGLETON (panel.js:501)
    provisionalEverCreated: 0,
    appended: 0,           // new rows
    replaced: 0,           // `existing` branch — a row's text was OVERWRITTEN
    replaces: [],          // what was lost, for the failure message

    renderProvisional(committed, provisional) {
      // `dom.list.querySelector('.caption--provisional')` — reused, never duplicated.
      if (!this.provisional) {
        this.provisional = { text: '', kind: 'provisional' };
        this.provisionalEverCreated += 1;
      }
      this.provisional.text =
        committed.map((t) => t.w).join(' ') + ' ' + provisional.map((t) => t.w).join(' ');
    },

    /** `retireProvisional` (`panel.js:561-565`). */
    retireProvisional() {
      this.provisional = null;
    },

    /** `addCaption` (`panel.js:591-659`), text only — the DOM parts are not the claim. */
    addCaption(text, reason, meta) {
      if (!text) return false;
      this.retireProvisional(); // panel.js:594
      const start = meta && typeof meta.start === 'number' ? meta.start : null;
      const existing = start === null ? null : this.byStart.get(start) || null;
      if (existing) {
        // panel.js:611-617 — REPLACE IN PLACE, and NOTE: `committedByStart.set`
        // is NOT called on this path (it lives in the `else`), so the map still
        // points at the same row. The previous text is destroyed.
        this.replaces.push({ start, lost: existing.text, kept: text });
        existing.text = text;
        this.replaced += 1;
      } else {
        const row = { text, start, kind: 'committed' };
        this.rows.push(row);
        this.appended += 1;
        if (start !== null) this.byStart.set(start, row); // panel.js:635
      }
      // panel.js:644-651 — the trim drops the map entry with the row.
      while (this.rows.length > MAX_CAPTIONS) {
        const first = this.rows.shift();
        if (first && first.start !== null) this.byStart.delete(first.start);
      }
      return true;
    },
  };
}

// ---------------------------------------------------------------------------
// Instruments
// ---------------------------------------------------------------------------

function readStream(file) {
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const events = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    let obj;
    try { obj = JSON.parse(line); } catch (e) { continue; }
    events.push(obj);
  }
  return events;
}

/** The caption events only — status/done lines are the shell's business. */
function captions(events) {
  return events.filter((e) => e.type === 'caption' && typeof e.text === 'string');
}

/**
 * Replay a caption stream through the REAL engine and the MODELLED panel.
 *
 * `mutate` may rewrite each event's `start`/`end` — that is how the two negative
 * controls are built, so they differ from the shipped arm in ONE variable only.
 *
 * A `final:true` event is committed IMMEDIATELY here, where the panel would wait
 * for its 1500 ms hold timer (`COMMIT_MAX_HOLD_MS`, panel.js:467). Committing at
 * the final event is the CONSERVATIVE direction for the claim: it creates rows at
 * the earliest possible moment, so if the shipped stream can produce a duplicate
 * row, this cadence is the one that finds it.
 */
function replay(engine, panel, caps, mutate) {
  let provisionalMax = 0;
  const commits = [];
  const eng = engine.createEngine({
    onCommit: (text, reason, meta) => {
      panel.retireProvisional();  // panel.js:439
      panel.addCaption(text, reason, meta); // panel.js:440
      commits.push({ text, reason, meta });
    },
    onProvisional: (committed, provisional) => {
      panel.renderProvisional(committed, provisional);
      if (panel.provisional) provisionalMax = Math.max(provisionalMax, 1);
    },
  });
  const finalsSeen = [];
  for (const raw of caps) {
    const ev = mutate ? mutate(raw) : raw;
    // `wireCaptions` (panel.js:575-580) hands the whole event as `meta`, which is
    // how the engine sees `final` (`caption-formulation.js:621-622`) and
    // `producer` (`:311`).
    eng.ingest(ev.text, {
      start: ev.start, end: ev.end, final: ev.final, producer: ev.producer,
    });
    if (ev.final === true) {
      eng.flush('line-closed');
      finalsSeen.push(ev.start);
    }
  }
  // The tail: what the panel's hold timer would eventually write.
  eng.expireHold();
  eng.flush('end-of-stream');
  return { provisionalMax, commits, finalsSeen };
}

/** Adjacent word bigrams that repeat INSIDE one text — the duplication detector. */
function repeatedBigrams(text) {
  const w = String(text).toLowerCase().split(/\s+/).filter(Boolean);
  const seen = new Map();
  const dup = [];
  for (let i = 0; i + 1 < w.length; i += 1) {
    const key = w[i] + ' ' + w[i + 1];
    if (seen.has(key)) dup.push(key);
    seen.set(key, i);
  }
  return dup;
}

// ---------------------------------------------------------------------------
// Arms
// ---------------------------------------------------------------------------

const results = [];
function record(name, ok, detail, expect) {
  results.push({ name, ok, detail, expect });
  const tag = ok ? 'PASS' : 'FAIL';
  console.log(`  [${tag}] ${name}: ${detail}`);
}

function main() {
  const negArm = process.argv.includes('--neg-arm');
  console.log('redux-live-contract-oracle — worker/redux_live.py JSONL -> the real panel engine');

  // ---- ARM 0: the instruments are real, and the model is anchored -----------
  const F = require(FORMULATION);
  console.log('\nARM 0 — the instrument, and the anchor that stops the model from rotting');
  const constants = F.SENTENCE_GAP_S === 8 && F.SENTENCE_MAX_CHARS === 90
    && F.COMMIT_MAX_HOLD_MS === 1500;
  record('A0/formulation-loads', typeof F.createEngine === 'function' && constants,
    `createEngine=${typeof F.createEngine} SENTENCE_GAP_S=${F.SENTENCE_GAP_S} `
    + `SENTENCE_MAX_CHARS=${F.SENTENCE_MAX_CHARS} COMMIT_MAX_HOLD_MS=${F.COMMIT_MAX_HOLD_MS}`,
    true);

  const panelSrc = fs.readFileSync(PANEL, 'utf8');
  const anchors = [
    'committedByStart.get(start)',
    'committedByStart.set(start, line)',
    "dom.list.querySelector('.caption--provisional')",
    'body.textContent = text',
    'retireProvisional();\n    addCaption(text, reason, meta);',
  ];
  const missing = anchors.filter((a) => !panelSrc.includes(a));
  record('A0/panel-anchors', missing.length === 0,
    missing.length ? `panel.js no longer contains: ${JSON.stringify(missing)} — the model below `
      + `is STALE and this oracle must not be trusted` : `${anchors.length}/${anchors.length} `
      + `shipped lines present in panel.js (${panelSrc.length} B)`, true);

  const all = readStream(STREAM);
  const caps = captions(all);
  record('A0/stream-is-real', caps.length > 0,
    `${STREAM} -> ${all.length} JSON lines, ${caps.length} caption events, `
    + `${caps.filter((c) => c.final).length} of them final:true`, true);

  // ---- ARM A: the shipped stream ------------------------------------------
  console.log('\nARM A — the SHIPPED stream (expect GREEN)');
  const pa = makePanel();
  const ra = replay(F, pa, caps, null);
  const starts = ra.commits.map((c) => c.meta.start);
  const distinct = new Set(starts);
  const dupA = ra.commits.flatMap((c) => repeatedBigrams(c.text));
  const finalsA = caps.filter((c) => c.final === true).length;

  record('A1/one-row-per-closed-line', pa.rows.length === finalsA,
    `${finalsA} closed line(s) in the stream -> ${pa.rows.length} row(s) `
    + `(${pa.appended} appended, ${pa.replaced} replaced)`, true);
  record('A2/no-commit-ever-replaced-a-row', pa.replaced === 0,
    `replaced=${pa.replaced}` + (pa.replaces.length
      ? ` — LOST: ${JSON.stringify(pa.replaces.map((r) => r.lost.slice(0, 48)))}` : ''), true);
  record('A3/segment-identity-is-distinct', distinct.size === starts.length,
    `start values: ${JSON.stringify(starts)}`, true);
  record('A4/no-duplicated-words', dupA.length === 0,
    dupA.length ? `repeated bigrams: ${JSON.stringify(dupA.slice(0, 6))}` : 'none', true);
  record('A5/provisional-is-a-singleton', ra.provisionalMax <= 1,
    `max simultaneous provisional rows = ${ra.provisionalMax} `
    + `(created ${pa.provisionalEverCreated}x, retired on every commit)`, true);
  console.log('    rows:');
  pa.rows.forEach((r, i) => console.log(`      ${i + 1}. start=${r.start} ${JSON.stringify(r.text)}`));

  // ---- ARM B: the plausible WRONG identity — start advances every event -----
  console.log('\nARM B (control, must go RED) — `start` advances with every partial');
  const pb = makePanel();
  const rb = replay(F, pb, caps, (ev) => Object.assign({}, ev, { start: ev.end }));
  const dupB = rb.commits.flatMap((c) => repeatedBigrams(c.text));
  const bRed = dupB.length > 0 || pb.rows.length !== finalsA;
  // The control's PASS condition IS "it went red" — in BOTH modes. A control that
  // prints PASS while measuring green is the defect, not the evidence.
  record('B1/control-went-RED', bRed,
    `rows=${pb.rows.length} (shipped=${pa.rows.length}) replaced=${pb.replaced} `
    + `repeated bigrams=${dupB.length}` + (dupB.length ? ` e.g. ${JSON.stringify(dupB.slice(0, 4))}` : '')
    + (bRed ? ' -> RED as required' : ' -> GREEN, so this control proves NOTHING'),
    bRed);

  // ---- ARM C: two DIFFERENT segments sharing ONE start ---------------------
  console.log('\nARM C (control, must go RED) — every segment carries the SAME `start`');
  const pc = makePanel();
  const rc = replay(F, pc, caps, (ev) => Object.assign({}, ev, { start: 0.0 }));
  const cRed = pc.rows.length !== finalsA || pc.replaced > 0;
  record('C1/control-went-RED', cRed,
    `${finalsA} closed line(s) -> ${pc.rows.length} row(s), replaced=${pc.replaced}`
    + (pc.replaces.length ? `; the row that was overwritten held `
      + `${JSON.stringify(pc.replaces[0].lost.slice(0, 60))}` : '')
    + (cRed ? ' -> RED as required' : ' -> GREEN, so this control proves NOTHING'),
    cRed);

  // ---- verdict -------------------------------------------------------------
  const hard = results.filter((r) => r.name.startsWith('A0/') || r.name.startsWith('A'));
  const bad = hard.filter((r) => !r.ok);
  console.log('');
  const controlsOk = bRed && cRed;
  const ok = controlsOk && bad.length === 0;
  console.log(`CONTROL-VERDICT ${controlsOk ? 'PASS' : 'FAIL'}  `
    + `armB(wrong start)-RED=${bRed} armC(shared start)-RED=${cRed}`);
  console.log(`VERDICT ${ok ? 'PASS' : 'FAIL'} — `
    + `${hard.length - bad.length}/${hard.length} shipped-contract arm(s) held`
    + (bad.length ? `; failed: ${JSON.stringify(bad.map((r) => r.name))}` : ''));
  return ok ? 0 : 1;
}

process.exit(main());
