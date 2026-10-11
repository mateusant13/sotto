#!/usr/bin/env node
/*
 * redux-live-contract-oracle.js - does `worker/redux_live.py`'s JSONL land on the
 * panel as ONE ROW PER CLOSED LINE, or does it lose text / duplicate words?
 *
 * WHAT IS REAL HERE AND WHAT IS MODELLED, because the difference decides how much
 * this oracle is worth:
 *
 *   REAL   `app/panel/caption-formulation.js`, loaded with `require` - it is
 *          DOM-free on purpose and its own `module.exports` is the surface this
 *          file drives. Every text decision in this oracle is the SHIPPED
 *          decision, not a re-implementation.
 *   REAL   the caption events: `_main/redux-live-smoke.jsonl`, produced by
 *          `worker/redux_live.py` on `_main/pt-br-sample.wav`. Not hand-written.
 *   MODELLED  the row rules of `panel.js`'s `addCaption` and the per-source open
 *          row of `renderProvisional`, because those need a DOM. ARM 0 anchors the
 *          model to the shipped source text, so a panel that changes its keying
 *          makes THIS FILE FAIL instead of quietly modelling a panel that no
 *          longer exists.
 *
 * REPAIRED 2026-10-11 (STEP 4). The model below used to key a row by `start`
 * ALONE, which is what panel.js did until this session:
 *
 *     const existing = start === null ? null : committedByStart.get(start) || null;
 *
 * The shipped rule is now `rowIdentity(source, start)` (`panel.js:326`):
 *
 *     if (start === null || start === undefined) return null;
 *     return source === null || source === undefined ? start
 *                                                 : String(source) + "\u0000" + start;
 *
 * so a run with NO source behaves key for key as it always did (this stream has no
 * `source`: its keys are model/type/text/start/end/final/producer), while two
 * DIFFERENT sources that share one second of audio are now two rows instead of one
 * overwritten row. The open row is also PER SOURCE now (`provisionalRows`,
 * `panel.js:382`). ARM D measures exactly that, and `--neg-arm` restores the
 * pre-STEP-4 keying to prove ARM D can say NO. Before this repair the `--neg-arm`
 * flag was parsed and never used - an inert flag on a file that also could not run
 * at all, because its ARM 0 anchors had gone dead.
 *
 * Usage:
 *   node _main/redux-live-contract-oracle.js            # all arms; ARM D GREEN
 *   node _main/redux-live-contract-oracle.js --neg-arm  # ARM B/C RED, and ARM D
 *                                                       # RED under the OLD keying
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

const MAX_CAPTIONS = 200; // panel.js:42

// ---------------------------------------------------------------------------
// The panel model. Every branch below quotes the line of panel.js it stands for.
// ---------------------------------------------------------------------------

/**
 * `opts.legacyKeying` restores the PRE-STEP-4 rule (`start` alone) - that is the
 * negative arm for ARM D, and the ONLY difference between the two modes.
 */
function makePanel(opts) {
  const legacyKeying = !!(opts && opts.legacyKeying);
  return {
    rows: [],                 // the committed `<li>`s, in DOM order
    byKey: new Map(),         // `committedByStart`, keyed by `rowIdentity`
    provisionals: new Map(),  // `provisionalRows` - ONE OPEN ROW PER SOURCE
    appended: 0,              // new rows
    replaced: 0,              // `existing` branch - a row's text was OVERWRITTEN
    replaces: [],             // what was lost, for the failure message
    provisionalMax: 0,        // max simultaneous open rows
    provisionalEverCreated: 0,
    legacyKeying,

    /** `engineFor`'s key (`panel.js:641`) and `renderProvisional`'s (`:756`). */
    keyOf(source) {
      return source === null || source === undefined ? null : String(source);
    },

    /** `rowIdentity` (`panel.js:326-329`), verbatim - including the legacy arm. */
    rowIdentity(source, start) {
      if (start === null || start === undefined) return null;
      if (legacyKeying) return start; // PRE-STEP-4: `committedByStart.get(start)`
      return source === null || source === undefined
        ? start
        : String(source) + "\u0000" + start;
    },

    /**
     * `renderProvisional` (`panel.js:755-777`): the open row for THIS source, found
     * through `provisionalRows`, never through an attribute selector. Two sources
     * form two sentences at the same time; one source never has two open rows.
     */
    renderProvisional(committed, provisional, source) {
      const key = this.keyOf(source);
      let line = this.provisionals.get(key) || null;
      if (!line) {
        line = { text: '', kind: 'provisional', source: key };
        this.provisionals.set(key, line);
        this.provisionalEverCreated += 1;
      }
      line.text =
        committed.map((t) => t.w).join(' ') + ' ' + provisional.map((t) => t.w).join(' ');
      this.provisionalMax = Math.max(this.provisionalMax, this.provisionals.size);
      return line;
    },

    /** `retireProvisional(source)` (`panel.js:855-862`) - only THIS source's row. */
    retireProvisional(source) {
      this.provisionals.delete(this.keyOf(source));
    },

    /** `addCaption` (`panel.js:896-975`), text only - the DOM parts are not the claim. */
    addCaption(text, reason, meta) {
      if (!text) return false;
      const source = meta && typeof meta.source === 'string' && meta.source
        ? meta.source : null;
      this.retireProvisional(source); // panel.js:910
      const start = meta && typeof meta.start === 'number' ? meta.start : null;
      const identity = this.rowIdentity(source, start);
      const existing = identity === null ? null : this.byKey.get(identity) || null;
      if (existing) {
        // panel.js:938-947 - REPLACE IN PLACE. The previous text is destroyed.
        this.replaces.push({ identity, lost: existing.text, kept: text });
        existing.text = text;
        this.replaced += 1;
      } else {
        const row = { text, start, source, identity, kind: 'committed' };
        this.rows.push(row);
        this.appended += 1;
        if (identity !== null) this.byKey.set(identity, row); // panel.js:950
      }
      // panel.js:962-974 - the trim drops the TRIMMED ROW'S OWN key, read back off
      // the row, never the key of the line being appended (which may be another
      // source's).
      while (this.rows.length > MAX_CAPTIONS) {
        const first = this.rows.shift();
        if (first && first.identity !== null) this.byKey.delete(first.identity);
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

/** The caption events only - status/done lines are the shell's business. */
function captions(events) {
  return events.filter((e) => e.type === 'caption' && typeof e.text === 'string');
}

/**
 * Replay a caption stream through the REAL engines and the MODELLED panel.
 *
 * ONE ENGINE PER SOURCE, mirroring `engineFor(source)` (`panel.js:640-680`): the
 * engine holds single-stream buffer state, so two sources in one engine interleave
 * into one garbled sentence. `source` is passed to `createEngine` because that is
 * where `caption-formulation.js:284` reads it and where the commit's `meta.source`
 * is stamped (`:582-588`).
 *
 * `mutate` may rewrite each event's `start`/`source` - that is how the controls are
 * built, so they differ from the shipped arm in ONE variable only.
 *
 * A `final:true` event is committed IMMEDIATELY here, where the panel would wait for
 * its 1500 ms hold timer (`COMMIT_MAX_HOLD_MS`). Committing at the final event is
 * the CONSERVATIVE direction for the claim: it creates rows at the earliest possible
 * moment, so if the shipped stream can produce a duplicate row, this cadence finds it.
 */
function replay(engine, panel, caps, mutate) {
  const enginesByKey = new Map();
  const commits = [];
  let provisionalMax = 0;

  function engineFor(source) {
    const key = source === null || source === undefined ? null : String(source);
    const cached = enginesByKey.get(key);
    if (cached) return cached;
    const eng = engine.createEngine({
      source: key, // caption-formulation.js:284 -> meta.source on every commit
      onCommit: (text, reason, meta) => {
        panel.retireProvisional(key);          // panel.js:673
        panel.addCaption(text, reason, meta);  // panel.js:674
        commits.push({ text, reason, meta, engineKey: key });
      },
      onProvisional: (committed, provisional) => {
        panel.renderProvisional(committed, provisional, key); // panel.js:676
        provisionalMax = Math.max(provisionalMax, panel.provisionals.size);
      },
    });
    enginesByKey.set(key, eng);
    return eng;
  }

  const finalsSeen = [];
  for (const raw of caps) {
    const ev = mutate ? mutate(raw) : raw;
    // `wireCaptions` hands the whole event as `meta`, which is how the engine sees
    // `final` (`caption-formulation.js:621-622`) and `producer` (`:311`).
    const src = typeof ev.source === 'string' && ev.source ? ev.source : null;
    const eng = engineFor(src);
    eng.ingest(ev.text, {
      start: ev.start, end: ev.end, final: ev.final, producer: ev.producer,
    });
    if (ev.final === true) {
      eng.flush('line-closed');
      finalsSeen.push(ev.start);
    }
  }
  // The tail: what the panel's hold timer would eventually write, per engine.
  for (const eng of enginesByKey.values()) {
    eng.expireHold();
    eng.flush('end-of-stream');
  }
  return { provisionalMax, commits, finalsSeen, engineCount: enginesByKey.size };
}

/** Adjacent word bigrams that repeat INSIDE one text - the duplication detector. */
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
  console.log('redux-live-contract-oracle - worker/redux_live.py JSONL -> the real panel engine');
  if (negArm) console.log('MODE --neg-arm: the model keys by `start` ALONE (the PRE-STEP-4 panel).');

  // ---- ARM 0: the instruments are real, and the model is anchored -----------
  const F = require(FORMULATION);
  console.log('\nARM 0 - the instrument, and the anchor that stops the model from rotting');
  const constants = F.SENTENCE_GAP_S === 8 && F.SENTENCE_MAX_CHARS === 90
    && F.COMMIT_MAX_HOLD_MS === 1500;
  record('A0/formulation-loads', typeof F.createEngine === 'function' && constants,
    `createEngine=${typeof F.createEngine} SENTENCE_GAP_S=${F.SENTENCE_GAP_S} `
    + `SENTENCE_MAX_CHARS=${F.SENTENCE_MAX_CHARS} COMMIT_MAX_HOLD_MS=${F.COMMIT_MAX_HOLD_MS}`,
    true);

  const panelSrc = fs.readFileSync(PANEL, 'utf8');
  const anchors = [
    'function rowIdentity(source, start)',
    'function engineFor(source)',
    'const provisionalRows = new Map()',
    'const engines = new Map()',
    'function renderProvisional(committed, provisional, source)',
    'function retireProvisional(source)',
    'if (source !== null) line.dataset.source = source;',
    'const trimmedSource = first && first.dataset && first.dataset.source',
  ];
  const missing = anchors.filter((a) => !panelSrc.includes(a));
  record('A0/panel-anchors', missing.length === 0,
    missing.length ? `panel.js no longer contains: ${JSON.stringify(missing)} - the model below `
      + `is STALE and this oracle must not be trusted` : `${anchors.length}/${anchors.length} `
      + `shipped lines present in panel.js (${Buffer.byteLength(panelSrc, 'utf8')} B)`, true);

  const all = readStream(STREAM);
  const caps = captions(all);
  const srcs = new Set(caps.map((c) => c.source).filter((s) => typeof s === 'string'));
  record('A0/stream-is-real', caps.length > 0,
    `${STREAM} -> ${all.length} JSON lines, ${caps.length} caption events, `
    + `${caps.filter((c) => c.final).length} of them final:true, `
    + `${srcs.size} distinct 'source' value(s)`, true);

  // ---- ARM A: the shipped stream ------------------------------------------
  console.log('\nARM A - the SHIPPED stream (expect GREEN)');
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
      ? ` - LOST: ${JSON.stringify(pa.replaces.map((r) => r.lost.slice(0, 48)))}` : ''), true);
  record('A3/segment-identity-is-distinct', distinct.size === starts.length,
    `start values: ${JSON.stringify(starts)}`, true);
  record('A4/no-duplicated-words', dupA.length === 0,
    dupA.length ? `repeated bigrams: ${JSON.stringify(dupA.slice(0, 6))}` : 'none', true);
  record('A5/provisional-is-a-singleton', ra.provisionalMax <= 1,
    `max simultaneous provisional rows = ${ra.provisionalMax} `
    + `(created ${pa.provisionalEverCreated}x, retired on every commit; ${ra.engineCount} engine(s))`,
    true);
  console.log('    rows:');
  pa.rows.forEach((r, i) => console.log(`      ${i + 1}. start=${r.start} ${JSON.stringify(r.text)}`));

  // ---- ARM B: the plausible WRONG identity - start advances every event -----
  console.log('\nARM B (control, must go RED) - `start` advances with every partial');
  const pb = makePanel();
  const rb = replay(F, pb, caps, (ev) => Object.assign({}, ev, { start: ev.end }));
  const dupB = rb.commits.flatMap((c) => repeatedBigrams(c.text));
  const bRed = dupB.length > 0 || pb.rows.length !== finalsA;
  // The control's PASS condition IS "it went red" - in BOTH modes. A control that
  // prints PASS while measuring green is the defect, not the evidence.
  record('B1/control-went-RED', bRed,
    `rows=${pb.rows.length} (shipped=${pa.rows.length}) replaced=${pb.replaced} `
    + `repeated bigrams=${dupB.length}` + (dupB.length ? ` e.g. ${JSON.stringify(dupB.slice(0, 4))}` : '')
    + (bRed ? ' -> RED as required' : ' -> GREEN, so this control proves NOTHING'),
    bRed);

  // ---- ARM C: two DIFFERENT segments sharing ONE start, NO source ----------
  console.log('\nARM C (control, must go RED) - every segment carries the SAME `start`');
  const pc = makePanel();
  const rc = replay(F, pc, caps, (ev) => Object.assign({}, ev, { start: 0.0 }));
  const cRed = pc.rows.length !== finalsA || pc.replaced > 0;
  record('C1/control-went-RED', cRed,
    `${finalsA} closed line(s) -> ${pc.rows.length} row(s), replaced=${pc.replaced}`
    + (pc.replaces.length ? `; the row that was overwritten held `
      + `${JSON.stringify(pc.replaces[0].lost.slice(0, 60))}` : '')
    + (cRed ? ' -> RED as required' : ' -> GREEN, so this control proves NOTHING'),
    cRed);
  console.log('    NOTE: with NO source the key is the NUMBER `start`, so this collapse is');
  console.log('    still the shipped behaviour - and correct, because nothing distinguishes');
  console.log('    the two segments. ARM D is the case that changed in STEP 4.');

  // ---- ARM D: SAME start, DIFFERENT sources (the STEP 4 contract) ----------
  const dLabel = negArm ? 'D1/legacy-keying-went-RED' : 'D1/one-row-per-source-at-the-same-start';
  console.log('\nARM D - three segments sharing ONE `start`, each with its OWN source'
    + (negArm ? ' (expect RED under the legacy keying)' : ' (expect GREEN)'));
  const pd = makePanel({ legacyKeying: negArm });
  const rd = replay(F, pd, caps, (ev) => Object.assign({}, ev, {
    start: 0.0, source: 'proc:' + ev.start,
  }));
  const dSources = new Set(rd.commits.map((c) => c.meta.source));
  const dGreen = dSources.size > 1 && pd.rows.length === dSources.size && pd.replaced === 0;
  const dRed = !dGreen;
  const dOk = negArm ? dRed : dGreen;
  record(dLabel, dOk,
    `${rd.commits.length} commit(s) over ${dSources.size} source(s) at start=0.0 -> `
    + `${pd.rows.length} row(s), replaced=${pd.replaced}, `
    + `${rd.engineCount} engine(s), sources=${JSON.stringify([...dSources])}`
    + (negArm ? (dRed ? ' -> RED as required' : ' -> GREEN, so this control proves NOTHING')
              : (dGreen ? ' -> GREEN as required' : ' -> RED: a source was overwritten')),
    dOk);

  // ---- verdict -------------------------------------------------------------
  const hard = results.filter((r) => r.name.startsWith('A0/') || r.name.startsWith('A'));
  const bad = hard.filter((r) => !r.ok);
  console.log('');
  const controlsOk = bRed && cRed && dOk;
  const ok = controlsOk && bad.length === 0;
  console.log(`CONTROL-VERDICT ${controlsOk ? 'PASS' : 'FAIL'}  `
    + `armB(wrong start)-RED=${bRed} armC(shared start)-RED=${cRed} `
    + `armD(${negArm ? 'legacy keying' : 'per source'})-${negArm ? 'RED' : 'GREEN'}=${dOk}`);
  console.log(`VERDICT ${ok ? 'PASS' : 'FAIL'} - `
    + `${hard.length - bad.length}/${hard.length} shipped-contract arm(s) held`
    + (bad.length ? `; failed: ${JSON.stringify(bad.map((r) => r.name))}` : ''));
  return ok ? 0 : 1;
}

process.exit(main());
