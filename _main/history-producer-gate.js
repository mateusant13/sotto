'use strict';

/**
 * Sotto — HISTORY PRODUCER GATE: can the transcript EVER fill?
 *
 * THE QUESTION NO GATE ASKS, and the reason this file exists.
 * `_main/live-vs-history-source-oracle.js` reports GREEN, and one of its arms
 * says "the canonical path is OPEN, not a fake that can never fill". That arm is
 * built by the ORACLE ITSELF: it copies every commit and INJECTS
 * `producer:'redux'` (`live-vs-history-source-oracle.js:219`,
 * `writeHistory(commits, shipped, source.CANONICAL_PRODUCER, …)`). So the oracle
 * proves the PREDICATE can accept a tagged line; it can say nothing about
 * whether anything in the tree ever TAGS one. Measured today: nothing does. The
 * transcript is therefore structurally incapable of filling, and every gate in
 * the repo is green about it.
 *
 * ── WHAT THIS GATE ASSERTS, RESTATED 2026-10-08 (and why it had to be) ───────
 * The first version replayed ONE stream — the LIVE worker's shape, which carries
 * no producer — and then compared `P = the meta carries a producer` against
 * `S = some non-test source stamps one`. The worker has since started stamping
 * `producer:"redux"` on its BATCH lines while the LIVE streaming shape correctly
 * carries NONE, so that single stream can only ever read `P = false`: the gate was
 * comparing a fact about ONE shape against a fact about the whole TREE, and it had
 * become structurally incapable of being satisfied. Measured RED:
 *   PRODUCER-VERDICT: inconsistent — a non-test source stamps a producer but the
 *   ENGINE meta carries none  (worker/redux_batch.py:17,189,202;
 *   worker/sotto_worker.py:2375,2413)
 *
 * The asymmetry is not a bug — it is the OWNER'S LAW, and
 * `_main/_redux-producer-path.js` proves both directions on the real engine:
 * *"o historico nao e' pra ser NUNCA o historico do live nvidia"*. So the gate now
 * replays BOTH shapes and asserts the asymmetry as three invariants. A producer is
 * forwarded IFF the fragment carried one:
 *
 *   P1 (the batch path)  fragments carrying `producer:'redux'`  -> every commit's
 *                        meta carries it, the predicate ACCEPTS it, and the line
 *                        REACHES THE DISK. This is the arm the old gate could not
 *                        express, and it is why `D > 0` is now really measured
 *                        instead of being asserted about a run that never stamped.
 *   P2 (the live path)   fragments carrying none (the live streaming shape) ->
 *                        no meta carries a producer, the predicate REFUSES it, and
 *                        NOTHING reaches the disk. Without this arm ARM P1 only
 *                        shows "the store accepts things"; with it, P1 shows the
 *                        STAMP is what decides.
 *   P3 (the conflict)    fragments of ONE line declaring DIFFERENT producers ->
 *                        the engine forwards NOTHING (it refuses to pick a winner,
 *                        `committedProducer` in caption-formulation.js), the
 *                        predicate refuses, and nothing reaches the disk.
 *
 * VERDICT — every invariant is checked, and every one of them can fail on its own:
 *   CONSISTENT (exit 0) when P1 && P2 && P3. The engine forwards the tag exactly
 *   when the fragments carried one, so the transcript can fill from the batch pass
 *   and can never fill from the live engine. `S` (the tree scan, ARM B) is printed
 *   with the file:line of every stamper and is a PRECONDITION of P1 rather than a
 *   fact checked beside it: P1 cannot pass unless a real source stamps `redux`,
 *   because the gate does not stamp anything itself. That is the property that
 *   makes this gate non-vacuous and it is worth stating plainly:
 *
 *     **IF NOTHING IN THE TREE STAMPS A PRODUCER, P1 FAILS AND THIS GATE IS RED.**
 *
 *   So the "the feed is structurally empty" state is a RED here, not a green
 *   labelled `no-producer-in-tree` — a gate that can only say yes is worse than
 *   none, and this gate previously had a name for emptiness that read like a pass.
 *   INCONSISTENT (exit 1) otherwise, with the failing invariant named.
 *
 *   node _main/history-producer-gate.js
 *   node _main/history-producer-gate.js --control-stamp-nvidia
 *       NEGATIVE CONTROL, both colours in ONE command: points the gate at a COPY
 *       of `caption-formulation.js` whose `onCommit` meta carries
 *       `producer:'nvidia'` — a REAL, PLACEABLE producer tag that is not the
 *       canonical one. The engine forwards it, and the predicate must refuse every
 *       line, so arms P1 and P3 flip to false and the gate must go RED. Exits 0
 *       only when the control really went RED. The copy
 *       (`_main/_lane6-engine-mutant.js`) is deleted before exit.
 *
 * Exit codes: 0 consistent (or the control arm behaved as expected) | 1
 * inconsistent | 2 setup error. No window, no browser, no audio: file reads,
 * one real engine, one real store under throwaway roots that are deleted.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');

const args = process.argv.slice(2);
const CONTROL_STAMP = args.includes('--control-stamp-nvidia');
/**
 * `--engine <path>` — run the SAME assertions against another copy of the engine.
 *
 * This exists so the gate is falsifiable from the outside: the two failure modes
 * it claims to catch (a tag that is DROPPED before the commit, a tag that is
 * INVENTED for a line that never declared one) are both one-line mutants of
 * `caption-formulation.js`, and a gate that ships a control for only one of them
 * has not shown it can say no to the other. The path is announced in the output,
 * never assumed. The real engine remains the default.
 */
function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}
const ENGINE_OVERRIDE = flagValue('--engine');

const sourcePath = path.join(REPO, 'app', 'panel', 'history-source.js');
const engineRealPath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const storePath = path.join(REPO, 'app', 'panel', 'history-store.js');
const oraclePath = path.join(HERE, 'live-vs-history-source-oracle.js');
const MUTANT_PATH = path.join(HERE, '_lane6-engine-mutant.js');
/** One root per replayed stream: a shared root would let one arm's lines be
 *  counted as another's, which is exactly the confusion P2/P3 exist to prevent. */
const throwRoot = (tag) => path.join(HERE, `_lane6-history-throwaway-${tag}`);

const rel = (p) => path.relative(REPO, p) || p;

/** The word the worker stamps on its batch lines, and the ONLY one the transcript takes. */
const CANONICAL_PRODUCER = 'redux';

/**
 * WORKER-SHAPED stream, LIVE SHAPE. Every partial is CUMULATIVE and carries the
 * LINE's own `start` with a growing `end` (worker/sotto_worker.py `_event`:
 * "`start` is the START OF THE LINE, never the newest chunk's start"),
 * `final:false` while the worker is still holding the line and `final:true` on the
 * line it CLOSED. This is the shape the panel actually sees; it is not read from a
 * recorded file so that the gate cannot inherit the recorded file's own curation.
 *
 * It carries NO producer on purpose: the live streaming engine never declares one,
 * and `app/panel/caption-formulation.js` must therefore commit with no producer at
 * all (ARM P2). A gate that only fed the batch shape would prove the feed opens
 * while proving nothing about the flow the owner actually runs.
 */
const WORKER_STREAM = [
  { text: 'going along', start: 0.0, end: 0.56, final: false },
  { text: 'going along slush', start: 0.0, end: 1.12, final: false },
  { text: 'going along slush country', start: 0.0, end: 1.68, final: false },
  { text: 'going along slush country roads', start: 0.0, end: 2.24, final: true },
];

/**
 * THE BATCH WORKER'S OWN META — the stream the old gate was missing, and the
 * reason it could not see the cure.
 *
 * `worker/redux_batch.py:189,202` (and the streaming worker's batch switch,
 * `worker/sotto_worker.py:2375,2413`) emit `producer:'redux'` on the lines the
 * canonical pass produces. AGE 2026-10-08: the engine used to hand `onCommit` a
 * NEW object of three literal keys — `{ route, start, routeSource }` — so that
 * stamp died one step before `history-source.js`, the guard that needs it, and the
 * feed took zero lines. MEASURED before the change by `_main/_redux-producer-path.js`:
 * ARM B 0 of 1 accepted, keys exactly `[route, start, routeSource]`, while its
 * injected control (ARM C) accepted 1.
 */
const BATCH_STREAM = [
  { text: 'O rádio anunciou que a ponte', start: 0.0, end: 2.5, producer: 'redux', final: false },
  { text: 'O rádio anunciou que a ponte sobre o rio', start: 0.0, end: 5.0, producer: 'redux', final: false },
  {
    text: 'O rádio anunciou que a ponte sobre o rio vai ser interditada.',
    start: 0.0, end: 7.92, producer: 'redux', final: true,
  },
];

/**
 * P3 — the FAIL-CLOSED case: fragments of ONE line that declare different
 * producers. The engine must forward NOTHING (`committedProducer()` returns null,
 * so the commit meta carries no `producer` key at all and the predicate refuses
 * the line). A gate that never fed this stream could not tell "the engine forwards
 * what the worker stamped" from "the engine forwards whatever it last saw".
 */
const CONFLICT_STREAM = [
  { text: 'linha de origem discutida', start: 12.0, end: 13.4, producer: 'redux', final: false },
  { text: 'linha de origem discutida e mais', start: 12.0, end: 14.8, producer: 'live', final: true },
];

const LINE_RE = /^-\s+\[\d{2}:\d{2}:\d{2}\]\s+/;

function blankComments(src, isPy) {
  const out = src.split('');
  let i = 0;
  let quote = null;
  let block = false;
  while (i < src.length) {
    const c = src[i];
    const d = src[i + 1];
    if (block) {
      if (c === '*' && d === '/') { out[i] = ' '; out[i + 1] = ' '; i += 2; block = false; continue; }
      if (c !== '\n') out[i] = ' ';
      i += 1;
      continue;
    }
    if (quote) {
      if (c === '\\') { i += 2; continue; }
      if (c === quote) quote = null;
      i += 1;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { quote = c; i += 1; continue; }
    if (c === '/' && d === '*') { out[i] = ' '; out[i + 1] = ' '; block = true; i += 2; continue; }
    if (c === '/' && d === '/') { while (i < src.length && src[i] !== '\n') { out[i] = ' '; i += 1; } continue; }
    if (isPy && c === '#') { while (i < src.length && src[i] !== '\n') { out[i] = ' '; i += 1; } continue; }
    i += 1;
  }
  return out.join('');
}

/** Replay `events` through the REAL engine; one record per `onCommit`. */
function replay(events, engineMod) {
  const commits = [];
  const engine = engineMod.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text,
      reason,
      meta: meta && typeof meta === 'object' ? { ...meta } : meta === undefined ? null : meta,
    }),
    onProvisional: () => {},
  });
  for (const c of events) {
    // `producer` is spread ONLY when the event names one. A literal
    // `producer: undefined` is not the live shape: the engine reads any string
    // in the field (even an empty one) as "this fragment DECLARED a producer"
    // (`rememberProducer` → `bufferSawProducer = true`), which would make ARM P2
    // an arm about an empty string instead of about the LIVE streaming shape —
    // the one thing it exists to measure.
    const meta = { start: c.start, end: c.end, final: c.final };
    if (c.producer !== undefined) meta.producer = c.producer;
    engine.ingest(c.text, meta);
  }
  // panel.js `wireStatus` flush — the last thing that closes a line.
  engine.flush('stream-end');
  return commits;
}

const SCAN_DIRS = ['app', 'worker', 'scripts'];
const SCAN_EXT = new Set(['.js', '.mjs', '.cjs', '.py', '.html']);
const SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'build', 'runs']);
/** The predicate module: it names the tag, it does not stamp one. */
const ALLOWED = new Set([path.join(REPO, 'app', 'panel', 'history-source.js')]);
/** An oracle/probe/harness is TEST source: it may build a tagged fixture. */
const TEST_RE = /(oracle|probe|test|spec|harness|gate|fixture|copy|mutant)/i;
/** `producer:` / `"producer":` / `producer =` — an assignment, not a read. */
const STAMP_RE = /["']?producer["']?\s*[:=](?!=)/;

function walk(dir, out) {
  let names = [];
  try { names = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of names) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      walk(full, out);
    } else if (SCAN_EXT.has(path.extname(e.name).toLowerCase())) {
      out.push(full);
    }
  }
  return out;
}

/** ARM B: every `producer` assignment in the tree, classified. */
function scanProducers() {
  const hits = [];
  const files = [];
  for (const d of SCAN_DIRS) walk(path.join(REPO, d), files);
  for (const file of files) {
    const cls = ALLOWED.has(file) ? 'allowed-predicate' : TEST_RE.test(path.basename(file)) ? 'test' : 'live';
    const raw = fs.readFileSync(file, 'utf8').split(/\r?\n/);
    const blanked = blankComments(raw.join('\n'), file.endsWith('.py')).split(/\n/);
    for (let i = 0; i < blanked.length; i += 1) {
      const m = STAMP_RE.exec(blanked[i]);
      if (!m) continue;
      hits.push({ file, line: i + 1, cls, text: raw[i].trim(), at: m.index, code: m.index });
    }
  }
  return { hits, filesScanned: files.length };
}

function countDiskLines(root) {
  let lines = 0;
  const files = [];
  if (!fs.existsSync(root)) return { lines, files };
  for (const day of fs.readdirSync(root)) {
    const folder = path.join(root, day);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const name of fs.readdirSync(folder)) {
      if (!name.endsWith('.md')) continue;
      const body = fs.readFileSync(path.join(folder, name), 'utf8').split(/\r?\n/);
      for (const l of body) if (LINE_RE.test(l)) lines += 1;
      files.push(path.join(folder, name));
    }
  }
  return { lines, files };
}

/**
 * Build the `producer:'nvidia'` mutant of the REAL engine (the negative control).
 *
 * THE ANCHOR IS `committedProducer`, NOT THE `onCommit` CALL, and that is a fix
 * with a measured cause. This control used to regex the LITERAL call
 * (`onCommit(line, reason, { … })`) and append `producer: 'nvidia'`. AGE
 * 2026-10-08: the engine no longer writes that literal — it decides the tag first
 * and passes a TERNARY:
 *   `onCommit(line, reason, tag === null ? { route, start, routeSource }
 *                                        : { route, start, routeSource, producer: tag })`
 * so the old regex still matched its prefix, replaced it, and produced a file
 * whose ONLY change was a producer on the `tag === null` branch. Measured:
 * `node _main\\history-producer-gate.js --control-stamp-nvidia` exited 2 with
 * `SETUP ERROR: … the anchor "onCommit(line, reason, { … })" … is not there`.
 * A control that cannot build its mutant cannot report on anything.
 *
 * Overriding the SOURCE OF THE TAG instead pins the property under test in ONE
 * act: "the engine declares this producer whatever the fragments said". `nvidia`
 * is chosen deliberately — it is a REAL, PLACEABLE producer tag that is not the
 * canonical one, so the mutant exercises the guard's refuse path rather than the
 * engine's no-tag path (`tag === null`). A control that merely made `tag` null
 * would prove the store refuses an ABSENT tag; this one proves it refuses a
 * WRONG one, which is the stronger claim and the one the open risk in AGENTS.md
 * (a non-Redux batch engine silently claiming `redux`) actually names.
 */
const CONTROL_TAG = 'nvidia';

function makeControlEngine() {
  const src = fs.readFileSync(engineRealPath, 'utf8');
  // The anchor is END-DELIMITED by the byte that actually follows the function in
  // the source (`\n\n  /**`, verified 2026-10-08: `function committedProducer` occurs
  // exactly once in the file, at column 2, and the next line after its closing brace
  // is blank then a two-space-indented JSDoc). Three earlier attempts are worth
  // recording, because every one of them failed in a way that could have been silent:
  //   * `…[\s\S]*?\n\}` stopped at the INNER closing brace of
  //     `if (…) return null;` — the same indentation depth — and swallowed the next
  //     18 430 bytes. The mutant came out 17 157 B against a 35 525 B original and
  //     `require`d as an EMPTY namespace, so this control died with
  //     `TypeError: Cannot read properties of undefined (reading 'ingest')` instead
  //     of reporting a verdict.
  //   * `…\n  \}\n(?=\n  \/\*\*)` then failed to match at all, because the blank
  //     line after the brace sits between `\n  \}` and the JSDoc.
  //   * Both forms used a bare `\n`, and `app/panel/caption-formulation.js` is a
  //     CRLF file — every `\n` in the pattern needed `\r?\n`. Dumped verbatim:
  //     `…return bufferProducer;\r\n  }\r\n\r\n  /**…`.
  // Hence `\r?\n` throughout, plus a SHAPE-INDEPENDENT backstop below
  // (`grewDelta`): whatever the regex does, a mutant of the wrong LENGTH CLASS is
  // refused rather than run.
  const m = /function committedProducer\(\)\s*\{[\s\S]*?\r?\n  \}\r?\n(?=\r?\n[\s\S]{0,4}\/\*\*)/.exec(src);
  if (!m) {
    console.log(`SETUP ERROR: the control arm needs the \`function committedProducer() { … }\` definition in ${rel(engineRealPath)} to override; it is not there.`);
    return null;
  }
  const anchor = m[0];
  if (anchor.length > 800) {
    console.log(`SETUP ERROR: the control arm's anchor matched ${anchor.length} bytes of ${rel(engineRealPath)} — it is over-matching, so the mutant would be a mutilated module. Re-anchor it (the function is 4 lines) before trusting any control verdict.`);
    return null;
  }
  const mutant = `function committedProducer() {\n    return ${JSON.stringify(CONTROL_TAG)}; // CONTROL: a placeable, NON-canonical tag\n  }\n`;
  const out = src.replace(anchor, mutant);
  const grewDelta = Buffer.byteLength(out, 'utf8') - Buffer.byteLength(src, 'utf8');
  if (Math.abs(grewDelta) > 500) {
    console.log(`SETUP ERROR: replacing that anchor changed the engine by ${grewDelta} byte(s) — a one-function change is tens of bytes, so the anchor is over-matching and the mutant would be a different module, not a control.`);
    return null;
  }
  fs.writeFileSync(MUTANT_PATH, out, 'utf8');
  console.log(`control  : ${rel(MUTANT_PATH)} — a COPY of ${rel(engineRealPath)} with ONE function replaced`);
  console.log(`           ${anchor.trim().split('\n')[0]} … (${anchor.trim().split('\n').length} line(s), ${anchor.length} byte(s))`);
  console.log(`           -> return ${JSON.stringify(CONTROL_TAG)};   (a real tag, not the canonical one; file delta ${grewDelta >= 0 ? '+' : ''}${grewDelta} byte(s))`);
  return MUTANT_PATH;
}

/**
 * ONE stream, driven through the REAL engine, then the REAL predicate, then the
 * REAL store. Returns everything the invariants need, so each invariant is a
 * statement about MEASURED output and none of them re-runs the pipeline.
 */
function driveStream(events, tag, engineMod, source, store) {
  const root = throwRoot(tag);
  fs.rmSync(root, { recursive: true, force: true });
  const priorRoot = process.env.SOTTO_HISTORY_ROOT;
  process.env.SOTTO_HISTORY_ROOT = root;

  const commits = replay(events, engineMod);
  const priorCwd = process.cwd();
  let rows;
  try {
    // The store resolves its root at call time; require() it AFTER the env var is
    // set so this stream cannot write into another stream's tree.
    delete require.cache[require.resolve(storePath)];
    const freshStore = require(storePath);
    rows = commits.map((c) => {
      const carriesProducer = !!(c.meta && typeof c.meta === 'object'
        && Object.prototype.hasOwnProperty.call(c.meta, 'producer'));
      const value = carriesProducer ? c.meta.producer : null;
      const accepted = source.isCanonicalLine(c.meta);
      let appended = null;
      if (accepted) {
        const entry = freshStore.append(c.text, c.meta);
        appended = entry ? rel(entry.path) : '(refused)';
      }
      return { carriesProducer, value, accepted, appended, text: c.text, meta: c.meta };
    });
  } finally {
    process.chdir(priorCwd);
  }
  const disk = countDiskLines(root);
  if (priorRoot === undefined) delete process.env.SOTTO_HISTORY_ROOT;
  else process.env.SOTTO_HISTORY_ROOT = priorRoot;
  fs.rmSync(root, { recursive: true, force: true });
  return { commits, rows, disk, accepted: rows.filter((r) => r.accepted).length };
}

function main() {
  for (const p of [sourcePath, engineRealPath, storePath]) {
    if (!fs.existsSync(p)) {
      console.log(`SETUP ERROR: missing ${rel(p)}`);
      return 2;
    }
  }

  let enginePath = engineRealPath;
  if (CONTROL_STAMP) {
    const mutant = makeControlEngine();
    if (!mutant) return 2;
    enginePath = mutant;
  } else if (ENGINE_OVERRIDE) {
    enginePath = path.resolve(ENGINE_OVERRIDE);
    if (!fs.existsSync(enginePath)) {
      console.log(`SETUP ERROR: --engine ${ENGINE_OVERRIDE} does not exist`);
      return 2;
    }
    console.log(`engine override: ${rel(enginePath)} (--engine; NOT the shipped engine)`);
  }

  // ------------------------------------------------------------------ ARM A
  delete require.cache[require.resolve(enginePath)];
  let engineMod;
  try {
    engineMod = require(enginePath);
  } catch (err) {
    console.log(`SETUP ERROR: cannot require ${rel(enginePath)}: ${err && err.message}`);
    return 2;
  }
  if (typeof engineMod.createEngine !== 'function') {
    console.log(`SETUP ERROR: createEngine absent in ${rel(enginePath)} — ARM A cannot run the REAL engine, and a gate that cannot run the engine must not report on it.`);
    return 2;
  }

  const store = require(storePath);
  const source = require(sourcePath);
  if (typeof store.append !== 'function') {
    console.log(`SETUP ERROR: append absent in ${rel(storePath)} — ARM C cannot reach the REAL store.`);
    return 2;
  }
  if (typeof source.isCanonicalLine !== 'function') {
    console.log(`SETUP ERROR: isCanonicalLine absent in ${rel(sourcePath)} — ARM C cannot ask the REAL predicate.`);
    return 2;
  }

  console.log(`engine : ${rel(enginePath)}`);
  console.log(`guard  : ${rel(sourcePath)}  (CANONICAL_PRODUCER = ${JSON.stringify(source.CANONICAL_PRODUCER)}, agrees with this gate: ${source.CANONICAL_PRODUCER === CANONICAL_PRODUCER})`);
  console.log(`store  : ${rel(storePath)}  (SOTTO_HISTORY_ROOT = one throwaway root per stream, deleted before exit)`);

  const batch = driveStream(BATCH_STREAM, 'batch', engineMod, source, store);
  const live = driveStream(WORKER_STREAM, 'live', engineMod, source, store);
  const conflict = driveStream(CONFLICT_STREAM, 'conflict', engineMod, source, store);

  const show = (label, res, note) => {
    console.log(`\n--- ${label} ---`);
    console.log(`  stream: ${note}`);
    console.log(`  commits from the REAL engine : ${res.commits.length}`);
    if (!res.commits.length) {
      console.log(`  !! THE ENGINE COMMITTED NOTHING. The strategy this gate is written against has moved;`);
      console.log(`     do not read a green from a run in which the engine produced no evidence either way.`);
    }
    for (const r of res.rows) {
      console.log(`  meta = ${JSON.stringify(r.meta)}`);
      console.log(`    producer key present=${r.carriesProducer} value=${JSON.stringify(r.value)}  isCanonicalLine=${r.accepted}`
        + (r.appended ? `  appended=${r.appended}` : ''));
    }
    console.log(`  accepted by the predicate     : ${res.accepted}`);
    console.log(`  lines on disk                 : ${res.disk.lines}  ${JSON.stringify(res.disk.files.map(rel))}`);
  };

  show('ARM P1: the BATCH shape (fragments carry producer:\'redux\')', batch,
    `${BATCH_STREAM.length} event(s), every one stamped producer=${JSON.stringify(CANONICAL_PRODUCER)}`);
  show('ARM P2: the LIVE shape (no fragment carries a producer) — the control', live,
    `${WORKER_STREAM.length} event(s), ${WORKER_STREAM.filter((e) => e.final === false).length} partial(s) final:false, then the closed line final:true, then flush('stream-end')`);
  show('ARM P3: ONE line whose fragments declare DIFFERENT producers (fail-closed)', conflict,
    `${CONFLICT_STREAM.length} event(s), producers ${JSON.stringify(CONFLICT_STREAM.map((e) => e.producer))}`);

  // ------------------------------------------------------------------ ARM B
  const scan = scanProducers();
  const live_hits = scan.hits.filter((h) => h.cls === 'live');
  console.log(`\n--- ARM B: who in the tree stamps a producer? (scanned ${scan.filesScanned} file(s) in ${SCAN_DIRS.map((d) => `${d}/`).join(', ')}) ---`);
  if (!scan.hits.length) {
    console.log('  no `producer:` / `producer =` assignment anywhere in app/, worker/, scripts/');
  } else {
    for (const h of scan.hits) {
      console.log(`  ${rel(h.file)}:${h.line}  [${h.cls}]  ${h.text}`);
    }
  }
  console.log(`  live (non-test, non-allowed) stamps : ${live_hits.length}`);
  console.log('  NOTE: this scan is CONTEXT, not a measured invariant — P1 below fails on its own if');
  console.log('        what it forwards is not the canonical tag, whether or not a source was found here.');

  // ------------------------------------------------------------- the invariants
  const all = (rows, f) => rows.length > 0 && rows.every(f);
  const producersSeen = (rows) => JSON.stringify([...new Set(rows.filter((r) => r.carriesProducer).map((r) => r.value))]);

  const p1_forwarded = all(batch.rows, (r) => r.carriesProducer && r.value === CANONICAL_PRODUCER);
  const p1_sawCanonical = batch.rows.some((r) => r.carriesProducer && r.value === CANONICAL_PRODUCER);
  const p1_accepted = batch.rows.length > 0 && batch.accepted === batch.rows.length;
  const p1_disk = batch.disk.lines > 0 && batch.disk.lines === batch.accepted;
  const P1 = p1_forwarded && p1_accepted && p1_disk;

  const p2_none = all(live.rows, (r) => !r.carriesProducer);
  const p2_refused = live.rows.length > 0 && live.accepted === 0;
  const p2_disk = live.disk.lines === 0;
  const P2 = p2_none && p2_refused && p2_disk;

  const p3_none = all(conflict.rows, (r) => !r.carriesProducer);
  const p3_refused = conflict.rows.length > 0 && conflict.accepted === 0;
  const p3_disk = conflict.disk.lines === 0;
  const P3 = p3_none && p3_refused && p3_disk;

  const S = live_hits.length > 0;

  console.log('\n--- the invariants ---');
  console.log(`  P1 the BATCH tag is forwarded, accepted and reaches the disk`);
  console.log(`       every commit carries producer=${JSON.stringify(CANONICAL_PRODUCER)} : ${p1_forwarded}`);
  console.log(`       every commit accepted by the predicate        : ${p1_accepted}  (${batch.accepted}/${batch.rows.length})`);
  console.log(`       disk lines > 0 and equal to the accepted      : ${p1_disk}  (${batch.disk.lines} line(s))`);
  console.log(`     => P1 : ${P1}`);
  console.log(`  P2 the LIVE shape carries NO producer and cannot reach the disk`);
  console.log(`       NO commit carries a producer key              : ${p2_none}`);
  console.log(`       NOTHING accepted by the predicate             : ${p2_refused}  (${live.accepted}/${live.rows.length})`);
  console.log(`       disk lines == 0                               : ${p2_disk}  (${live.disk.lines} line(s))`);
  console.log(`     => P2 : ${P2}`);
  console.log(`  P3 a CONFLICTED line is refused at the engine, not at the store`);
  console.log(`       NO commit carries a producer key              : ${p3_none}`);
  console.log(`       NOTHING accepted by the predicate             : ${p3_refused}  (${conflict.accepted}/${conflict.rows.length})`);
  console.log(`       disk lines == 0                               : ${p3_disk}  (${conflict.disk.lines} line(s))`);
  console.log(`     => P3 : ${P3}`);
  console.log(`  S  (a live source stamps a producer — context)  : ${S}   (${live_hits.length} hit(s))`);
  if (!S) {
    console.log('     !! NO SOURCE IN THE TREE STAMPS A PRODUCER, so the transcript cannot fill. P1 is not');
    console.log('        satisfied by this gate stamping anything itself: it replays what the ENGINE does');
    console.log('        with a stream it is handed, and it never invents a tag.');
  }

  const reasons = [];
  if (!p1_forwarded && !p1_sawCanonical) {
    reasons.push(`the BATCH stream declares producer=${JSON.stringify(CANONICAL_PRODUCER)} on every fragment, but the engine's commit meta does not carry it — the tag is being DROPPED before the guard that needs it, which is the exact defect _main/_redux-producer-path.js ARM B measured before the fix`);
  }
  if (!p1_forwarded && p1_sawCanonical) {
    reasons.push(`the engine forwarded a producer on the batch stream but its value is not the canonical one (producers seen: ${producersSeen(batch.rows)}; the guard admits only ${JSON.stringify(CANONICAL_PRODUCER)}) — a tag that reaches the guard and is not the one it admits`);
  }
  if (p1_forwarded && !p1_accepted) {
    reasons.push(`${batch.rows.length - batch.accepted} of ${batch.rows.length} forwarded line(s) were still refused by the predicate, yet the meta really does carry ${JSON.stringify(CANONICAL_PRODUCER)} — the guard and the engine disagree about the tag`);
  }
  if (p1_forwarded && p1_accepted && !p1_disk) {
    reasons.push(`the predicate accepted ${batch.accepted} line(s) but ${batch.disk.lines} reached the transcript: the store is refusing what the guard accepted, so the feed is closed one step LATER than the guard`);
  }
  if (!p2_none) {
    reasons.push(`${live.rows.filter((r) => r.carriesProducer).length} of ${live.rows.length} LIVE commit(s) CARRIED a producer (values ${producersSeen(live.rows)}) although no fragment declared one — the engine is inventing a tag, which is the asymmetry the owner's law forbids`);
  }
  if (p2_none && !p2_refused) {
    reasons.push(`${live.accepted} LIVE line(s) were accepted by the guard — the two fields are ONE source again, which is the owner-reported defect`);
  }
  if (p2_none && p2_refused && !p2_disk) {
    reasons.push(`${live.disk.lines} LIVE line(s) reached the transcript while the guard refused them`);
  }
  if (!p3_none) {
    reasons.push(`fragments of ONE line declared DIFFERENT producers (${JSON.stringify(CONFLICT_STREAM.map((e) => e.producer))}) and the engine forwarded ${producersSeen(conflict.rows)} anyway: it PICKED a winner instead of failing closed`);
  }
  if (p3_none && !p3_refused) {
    reasons.push(`a conflicted line was ACCEPTED (${conflict.accepted}/${conflict.rows.length}) — a line whose provenance is contradictory must never reach the canonical transcript`);
  }
  if (p3_none && p3_refused && !p3_disk) {
    reasons.push(`${conflict.disk.lines} conflicted line(s) reached the transcript`);
  }
  if (batch.rows.length === 0 || live.rows.length === 0 || conflict.rows.length === 0) {
    reasons.push(`at least one stream committed NOTHING (batch=${batch.rows.length}, live=${live.rows.length}, conflict=${conflict.rows.length}) — the engine contract this gate is written against has moved, and a gate must not read a green from a run that produced no evidence`);
  }

  const consistent = reasons.length === 0;
  if (consistent) {
    console.log('\nPRODUCER-VERDICT: producer-wired-through');
    console.log('  A producer is stamped IN THE TREE, the engine forwards it IFF the fragments carried it,');
    console.log(`  and the lines it stamps reach the transcript (ARM P1: ${batch.accepted}/${batch.rows.length} accepted, ${batch.disk.lines} on disk) while the`);
    console.log(`  LIVE shape is refused (ARM P2: ${live.accepted}/${live.rows.length} accepted, ${live.disk.lines} on disk) and a conflicted line is refused at the`);
    console.log('  engine (ARM P3). The canonical path is genuinely open AND the asymmetry holds:');
    console.log('  the history is not, and cannot become, the live engine\'s history.');
  } else {
    console.log('\nINCONSISTENT STATE — the tree and the transcript disagree:');
    for (const r of reasons) console.log(`  * ${r}`);
  }

  // Context only: what the sibling oracle does, so a reader can see why it can be
  // green while this gate reports a closed path. No effect on the verdict.
  if (fs.existsSync(oraclePath)) {
    const oracleSrc = fs.readFileSync(oraclePath, 'utf8');
    const injects = /writeHistory\(commits,\s*shipped,\s*source\.CANONICAL_PRODUCER/.test(oracleSrc);
    const warn = /tagged = producer \? commits\.map/.test(oracleSrc);
    console.log(`\nINFO  : ${rel(oraclePath)} — injects a producer itself: writeHistory(commits, shipped, source.CANONICAL_PRODUCER, …)=${injects}, copies-commits-and-stamps=${warn}`);
  }

  let rc = consistent ? 0 : 1;
  if (CONTROL_STAMP) {
    const wentRed = !consistent;
    console.log(`\nCONTROL-ARM (stamp producer:'nvidia' on the ONCOMMIT META of a COPY, leave the tree alone)`);
    console.log(`  verdict real = ${consistent ? 'GREEN' : 'RED'}`);
    console.log(`  verdict want = RED`);
    console.log(`  CONTROL ${wentRed ? 'PASS' : 'FAIL'} — ${wentRed ? 'the gate catches a producer tag that is forwarded but is not the canonical one, so no line it stamps may reach the transcript' : 'THE GATE STAYED GREEN ON A FORWARDED NON-CANONICAL PRODUCER'}`);
    rc = wentRed ? 0 : 1;
  }

  if (CONTROL_STAMP) fs.rmSync(MUTANT_PATH, { force: true });
  for (const tag of ['batch', 'live', 'conflict']) fs.rmSync(throwRoot(tag), { recursive: true, force: true });

  console.log(`\nRESULT: ${consistent ? 'GREEN' : 'RED'} — PRODUCER-VERDICT: ${consistent ? 'producer-wired-through' : 'inconsistent'}`);
  return rc;
}

let rc = 1;
try {
  rc = main();
} catch (err) {
  console.log(`SETUP ERROR: ${err && err.stack ? err.stack : err}`);
  try { fs.rmSync(MUTANT_PATH, { force: true }); } catch { /* ignore */ }
  for (const tag of ['batch', 'live', 'conflict']) {
    try { fs.rmSync(throwRoot(tag), { recursive: true, force: true }); } catch { /* ignore */ }
  }
  rc = 2;
}
process.exit(rc);
