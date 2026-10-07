'use strict';

/**
 * Sotto — PANEL STATE GUARD GATE: a predicate that reads a field the engine
 * never returns is a guard that cannot say yes.
 *
 * THE DEFECT CLASS THIS GATE EXISTS FOR (F6, `docs/audit/auditoria-completa-20261007.md`):
 * `app/panel/panel.js` re-arms its hold timer with
 *
 *     if (engine.state().provisionalRoute) armHoldTimer();
 *
 * and the engine's `state()` (`app/panel/caption-formulation.js`) returns
 * `{ committed, provisional, lastAudioEnd }`. `provisionalRoute` is NEVER
 * there, so the condition is permanently `undefined` -> falsy, the hold timer
 * is never re-armed while a provisional line is held, and the guard that was
 * supposed to keep a live provisional line alive silently does nothing. No
 * existing gate saw it because every gate that touches `panel.js` asserts the
 * TEXT of a source line; none executes the shape of the object the line reads.
 *
 * WHAT IT DOES, against the REAL modules, with no regex for the thing that
 * matters:
 *   1. EXTRACTS every `<expr>.state().<field>` read in `panel.js` — the direct
 *      chain, the `const st = engine.state(); st.<field>` shape, a destructuring
 *      `const { x } = engine.state()`, and the bracket form `state()['x']`.
 *      Reads are taken from the source with comments BLANKED, so a commented-out
 *      line is reported as context and never fails the gate.
 *   2. BUILDS the REAL engine (`caption-formulation.js createEngine`) and asks
 *      its REAL `state()` for its key set — before and after ingest, so a key
 *      that only appears mid-line is not mistaken for a missing one. The
 *      source-derived keys are printed beside it for a reader to compare.
 *   3. FAILS on any read that is not in that key set, naming file:line.
 *
 *   node _main/panel-state-guard-gate.js
 *   node _main/panel-state-guard-gate.js --panel <file>   (negative control:
 *        point it at a COPY of panel.js with the read changed)
 *
 * Exit codes: 0 every read resolves | 1 a read does not resolve (or the gate
 * would be vacuous: panel.js contains no `state()` read at all) | 2 setup error
 * (panel.js unreadable, or the engine does not expose `createEngine`/`state()`).
 * No window, no browser, no audio: file reads plus one real engine object.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');

const args = process.argv.slice(2);
function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

const panelPath = path.resolve(flagValue('--panel') || path.join(REPO, 'app', 'panel', 'panel.js'));
const enginePath = path.resolve(flagValue('--engine') || path.join(REPO, 'app', 'panel', 'caption-formulation.js'));

const rel = (p) => path.relative(REPO, p) || p;

/**
 * Blank CSS/JS comments, keeping every offset (and therefore every line number)
 * stable: a commented-out read is NOT a read, and the gate must not fail on one.
 * Strings, template literals and block comments are tracked; anything the
 * scanner cannot classify stays as code, which errs toward RED (a reported read
 * a human can inspect) and never toward a silent green.
 */
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

function lineOf(offset, src) {
  let line = 1;
  for (let i = 0; i < offset && i < src.length; i += 1) if (src[i] === '\n') line += 1;
  return line;
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const IDENT = '[A-Za-z_$][\\w$]*';
const RECEIVER = `${IDENT}(?:\\s*\\??\\s*\\.\\s*${IDENT})*`;

/**
 * Every read of a field of a `state()` result in `src`.
 * @returns {{field:string, line:number, expr:string, shape:string, site:string}[]}
 */
function readsOfState(src) {
  const blanked = blankComments(src, false);
  const hits = [];
  const seen = new Set();
  const push = (field, offset, expr, shape, site) => {
    const key = `${field}@${offset}`;
    if (seen.has(key)) return;
    seen.add(key);
    hits.push({ field, line: lineOf(offset, src), expr, shape, site });
  };

  // Scanned on the BLANKED source, so a commented-out read produces no match at
  // all rather than a false RED. Anything the scanner cannot classify stays as
  // code, which errs toward a reported read a human can inspect — never toward a
  // silent green.
  const pushMatch = (re, fieldIdx, exprIdx, shape, siteFn) => {
    let m;
    while ((m = re.exec(blanked)) !== null) {
      push(m[fieldIdx], m.index, exprIdx ? m[exprIdx] : '', shape, siteFn ? siteFn(m) : m[0]);
    }
  };

  // (1) direct: `engine.state().provisionalRoute` / `engine.state()?.f` / `x.state () . f`
  pushMatch(
    new RegExp(`(${RECEIVER})\\s*\\.\\s*state\\s*\\(\\s*\\)\\s*\\??\\s*\\.\\s*(${IDENT})`, 'g'),
    2, 1, 'direct', (m) => m[0].replace(/\s+/g, ' '),
  );
  // (1b) bracket: `engine.state()['provisionalRoute']`
  pushMatch(
    new RegExp(`(${RECEIVER})\\s*\\.\\s*state\\s*\\(\\s*\\)\\s*\\??\\s*\\[\\s*['"]([\\w$]+)['"]\\s*\\]`, 'g'),
    2, 1, 'bracket', (m) => m[0].replace(/\s+/g, ' '),
  );
  // (2) destructuring: `const { committed } = engine.state()` / `{ a: b }`
  {
    const re = new RegExp(`(?:const|let|var)\\s*\\{([^}]*)\\}\\s*=\\s*${RECEIVER}\\s*\\.\\s*state\\s*\\(\\s*\\)`, 'g');
    let m;
    while ((m = re.exec(blanked)) !== null) {
      for (const part of m[1].split(',')) {
        const name = part.split(/[:=]/)[0].trim();
        if (/^[A-Za-z_$][\w$]*$/.test(name)) push(name, m.index, m[1].trim(), 'destructured', m[0].replace(/\s+/g, ' '));
      }
    }
  }

  // (3) assigned to a local first: `const st = engine.state();` then `st.field`
  const aliases = [];
  {
    const re = new RegExp(
      `(${IDENT}(?:\\s*\\.\\s*${IDENT})*)\\s*=\\s*${RECEIVER}\\s*\\.\\s*state\\s*\\(\\s*\\)`,
      'g',
    );
    let m;
    while ((m = re.exec(blanked)) !== null) {
      const alias = m[1].replace(/\s+/g, '');
      // `this.st` / `a.b` are read back with the same dotted expression.
      const last = alias.split('.').pop();
      if (!/^[A-Za-z_$][\w$]*$/.test(last)) continue;
      aliases.push({ alias, line: lineOf(m.index, src), offset: m.index });
    }
  }
  for (const { alias, offset } of aliases) {
    const dotted = escapeRe(alias).replace(/\\\./g, '\\s*\\??\\s*\\.\\s*');
    const re = new RegExp(`(?<![\\w$.])${dotted}\\s*\\??\\s*\\.\\s*(${IDENT})`, 'g');
    let m;
    while ((m = re.exec(blanked)) !== null) {
      if (m.index < offset) continue; // only after the assignment is meaningful
      push(m[1], m.index, alias, 'via-local', `${alias}.${m[1]}`);
    }
    // bracket form on the local
    const reB = new RegExp(`${escapeRe(alias)}\\s*\\??\\s*\\[\\s*['"]([\\w$]+)['"]\\s*\\]`, 'g');
    while ((m = reB.exec(blanked)) !== null) {
      if (m.index < offset) continue;
      push(m[1], m.index, alias, 'via-local-bracket', `${alias}['${m[1]}']`);
    }
  }

  hits.sort((a, b) => a.line - b.line);
  return { reads: hits };
}

/** The key names of the object literal `state()` returns, read from the source. */
function sourceStateKeys(src) {
  const i = src.search(/state\s*:\s*\(\s*\)\s*=>\s*\(\s*\{/);
  if (i < 0) return null;
  const start = src.indexOf('{', src.indexOf('=>', i));
  let depth = 0;
  let end = -1;
  for (let k = start; k < src.length; k += 1) {
    if (src[k] === '{') depth += 1;
    else if (src[k] === '}') { depth -= 1; if (depth === 0) { end = k; break; } }
  }
  if (end < 0) return null;
  const body = blankComments(src.slice(start + 1, end), false);
  const keys = [];
  for (const raw of body.split(',')) {
    const part = raw.trim();
    if (!part) continue;
    const m = /^([A-Za-z_$][\w$]*)\s*:/.exec(part);
    if (m) { keys.push(m[1]); continue; }
    const m2 = /^([A-Za-z_$][\w$]*)$/.exec(part.replace(/\s+/g, ' ').trim());
    if (m2) keys.push(m2[1]);
  }
  return keys;
}

function main() {
  for (const p of [panelPath, enginePath]) {
    if (!fs.existsSync(p)) {
      console.log(`SETUP ERROR: ${rel(p)} is not readable`);
      return 2;
    }
  }

  const panelSrc = fs.readFileSync(panelPath, 'utf8');
  const engineSrc = fs.readFileSync(enginePath, 'utf8');
  const { reads } = readsOfState(panelSrc);

  delete require.cache[require.resolve(enginePath)];
  let engineMod;
  try {
    engineMod = require(enginePath);
  } catch (err) {
    console.log(`SETUP ERROR: cannot require ${rel(enginePath)}: ${err && err.message}`);
    return 2;
  }
  if (typeof engineMod.createEngine !== 'function') {
    console.log(`SETUP ERROR: createEngine absent in ${rel(enginePath)} — this gate needs the REAL engine to ask its REAL state()`);
    return 2;
  }
  const engine = engineMod.createEngine({ onCommit: () => {}, onProvisional: () => {} });
  if (!engine || typeof engine.state !== 'function') {
    console.log(`SETUP ERROR: the engine returned by ${rel(enginePath)} exposes no state() function`);
    return 2;
  }
  const keysBefore = Object.keys(engine.state() || {});
  // A field that only appears once a line is on screen must not look missing.
  try {
    engine.ingest('going along slush country roads', { start: 0, end: 2.24, final: false });
  } catch { /* the key set is what matters, not the ingest */ }
  const keysAfter = Object.keys(engine.state() || {});
  const keySet = new Set([...keysBefore, ...keysAfter]);
  const srcKeys = sourceStateKeys(engineSrc);

  console.log(`panel  : ${rel(panelPath)}`);
  console.log(`engine : ${rel(enginePath)}`);
  console.log(`\nreads on state() in the panel, with their sites:`);
  if (!reads.length) {
    console.log('  (none)');
  } else {
    for (const r of reads) {
      console.log(`  ${r.field}   <- ${rel(panelPath)}:${r.line}   shape=${r.shape}  via ${r.expr || '(direct)'}   site: ${r.site}`);
    }
  }
  console.log(`\nkeys the engine's REAL state() returns:`);
  console.log(`  before ingest : ${JSON.stringify(keysBefore)}`);
  console.log(`  after ingest  : ${JSON.stringify(keysAfter)}`);
  console.log(`  from the source literal : ${srcKeys === null ? '(state():=>{{…}} shape not recognised)' : JSON.stringify(srcKeys)}`);

  const arms = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    arms.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
    return ok;
  }

  console.log('');
  const bad = reads.filter((r) => !keySet.has(r.field));
  for (const r of reads) {
    arm(
      `every read resolves — state().${r.field} (${rel(panelPath)}:${r.line}, ${r.shape})`,
      keySet.has(r.field) ? 'resolves' : 'READS A FIELD THE ENGINE NEVER RETURNS',
      'resolves',
    );
  }
  arm(
    'the gate is NOT vacuous: panel.js contains at least one state() read',
    reads.length > 0 ? 'has reads' : 'NO state() READ AT ALL',
    'has reads',
  );
  arm(
    'the engine-side key set agrees with the source literal it is read from',
    srcKeys === null ? '(not comparable)' : (srcKeys.slice().sort().join(',') === [...keySet].sort().join(',') ? 'agree' : `DISAGREE src=${JSON.stringify(srcKeys)} runtime=${JSON.stringify([...keySet])}`),
    srcKeys === null ? '(not comparable)' : 'agree',
  );
  if (srcKeys === null) {
    // Not a failure by itself, but the source cross-check is the thing that
    // would catch a state() that builds its keys dynamically; say so.
    console.log('NOTE: the source literal of state() could not be parsed; only the runtime key set was checked.');
  }

  if (bad.length) {
    console.log(`\nthe panel reads ${bad.length} field(s) absent from the engine's state():`);
    for (const r of bad) console.log(`  ${rel(panelPath)}:${r.line}  state().${r.field}   (site: ${r.site})`);
    console.log('A predicate that reads a field the engine never returns can only ever be falsy — a guard that cannot say yes.');
  }

  const ok = arms.every(Boolean);
  console.log(`\nRESULT: ${ok ? 'GREEN' : 'RED'} — ${arms.filter(Boolean).length}/${arms.length} arm(s)`);
  return ok ? 0 : 1;
}

process.exit(main());
