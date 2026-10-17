#!/usr/bin/env node
/**
 * TdzReachOracle -- THE CLASS, not the one instance.
 *
 * WHY THIS EXISTS (measured, not guessed). `app/panel/panel.js` declared
 * `const CAPTION_WINDOW_ATTR` at :2217 and the top-level init block at :629
 * called a function that reads it. The real WebView2 said so, in the shell's
 * own log, on the run that was live when this was written:
 *
 *   2026-10-17 16:00:40 WARN PAGE_ERROR text="Uncaught ReferenceError: Cannot
 *   access 'CAPTION_WINDOW_ATTR' before initialization" at=panel.js:2221:48
 *   stack="... at captionOverlayIsUp (panel.js:2221:48) at
 *   watchCaptionWindowState (panel.js:2254:20) at panel.js:629:3"
 *
 * THREE WRONG INSTRUMENTS WERE TRIED FIRST. All three are why the docstring
 * is long. Do not repeat them.
 *
 *   1. A one-hop grep for the constant in the init block. It returned ZERO and
 *      that zero was FALSE: line 629 never spells `CAPTION_WINDOW_ATTR`. The
 *      reference is two calls deep.
 *   2. A transitive scanner that compared each constant's declaration line with
 *      the line where the REFERENCE TEXT sits. Also GREEN, also false: the dead
 *      zone is about the order statements are EVALUATED, not the order words
 *      appear. `watchCaptionWindowState` is CALLED from :629, above both 2217
 *      and 2221, so 2217 < 2221 proves nothing.
 *   3. The transitive scanner fixed for (2), which then reported TWO hits and so
 *      was also wrong, in the other direction: it counted `holdTimer` (:757),
 *      reached from `wireCaptions` -> `bridge.onCaption(cb)`. That is a CALLBACK
 *      registered during init and fired later, long after evaluation finished,
 *      so `holdTimer` is long initialised. Reachable is not executed-during-init.
 *
 * So the oracle keeps the call graph and separates the two edges:
 *   DIRECT   -- a reference reached without crossing a nested function boundary.
 *               It runs inside the init burst, so it is a real TDZ risk.
 *   DEFERRED -- reached across a nested function (`cb`, arrow, observer,
 *               timeout). It runs later. Reported, never judged.
 *
 * The runtime is still the authority: `_page_error` in
 * `app/webview/sotto_webview.py` logs every uncaught page throw as
 * `WARN PAGE_ERROR text=... at=file:line:col stack=...`, and the startup order
 * means a DIRECT hit stops evaluation and HIDES every later one. Fix the top
 * DIRECT hit, restart, read the log, repeat. That loop is what cured this file.
 *
 * SCOPE, STATED SO NOBODY OVER-TRUSTS IT. Lexical scanning, not a parser. It
 * reaches only top-level `function` declarations and only by name, so a call
 * through a member expression (`wire.x()`), anything behind `eval`, and a
 * variable holding a function are all invisible to it. It REPORTS names it
 * could not resolve rather than calling them clean, so the blind spot shows up
 * in the output instead of hiding in a GREEN.
 *
 * EXIT  0 no DIRECT hit   1 at least one DIRECT hit   2 cannot read the file
 *
 * USAGE
 *   node _main/tdz-reach-oracle.js app/panel/panel.js 612 635
 *   node _main/tdz-reach-oracle.js --selftest
 *        Runs the oracle over fixtures that carry a known answer in each
 *        direction -- one real TDZ, one callback that only LOOKS like one,
 *        one clean file -- and refuses to pass unless it gets all three right.
 *        An oracle that has never said "yes" is not an oracle; an oracle that
 *        cannot say "yes" for the right reason is worse.
 */
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const KEYWORDS = new Set(['if', 'else', 'for', 'while', 'do', 'switch', 'case',
  'return', 'const', 'let', 'var', 'function', 'class', 'new', 'typeof',
  'instanceof', 'this', 'null', 'undefined', 'true', 'false', 'in', 'of',
  'try', 'catch', 'finally', 'throw', 'delete', 'void', 'await', 'async',
  'yield', 'break', 'continue', 'default', 'export', 'import', 'static',
  'get', 'set', 'extends', 'super', 'with', 'debugger', 'from']);

function scan(file) {
  let src;
  try {
    src = readFileSync(file, 'utf8');
  } catch (err) {
    return { error: `CANNOT_READ ${file} ${err.message}` };
  }
  const lines = src.split(/\r\n|\n|\r/);

  /* Block comments are stripped across the WHOLE source first, with the line
   * count preserved, because a comment opening on one line and closing on the
   * next is invisible to a per-line strip -- and the doc block above a constant
   * spells that constant's own name, so a per-line strip reads every doc comment
   * as a reference to it. */
  const clean = src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/gm, (m, p1) => p1 + ' '.repeat(Math.max(0, m.length - p1.length)))
    .split(/\r\n|\n|\r/);

  const stringsOff = (text) => text
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/`(?:\\.|[^`\\])*`/g, '``');

  // --- top-level bindings, by brace balance -------------------------------
  const declLine = new Map();
  const funcs = new Map();
  let depth = 0, pending = null;
  lines.forEach((text, i) => {
    const n = i + 1;
    if (!/^\s/.test(text) && depth === 0) {
      const c = /^(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*(?:=|;|,)/.exec(text);
      if (c) declLine.set(c[1], n);
      const f = /^function\s+([A-Za-z_$][\w$]*)\s*\(/.exec(text);
      /* A function body on ONE line (`function f() { return x; }`) never closes
       * on a later line, so a "close it when the next `}` line appears" machine
       * leaves `pending` open and the NEXT top-level function overwrites it --
       * silently losing the first. Close on the brace balance instead: the
       * function ends the line depth returns to where it started. */
      if (f) pending = { name: f[1], line: n, from: n, to: n, startDepth: depth, sawBrace: false };
    }
    if (pending) {
      if (/\{/.test(text)) { pending.sawBrace = true; pending.to = n; }
    }
    for (const ch of text) {
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
    }
    if (depth < 0) depth = 0;
    if (pending && pending.sawBrace && depth <= pending.startDepth) {
      funcs.set(pending.name, pending);
      pending = null;
    }
  });

  /* DIRECT vs DEFERRED lines, per top-level function. A line is DEFERRED when it
   * sits inside a NESTED function inside the top-level one -- that is the body of
   * a callback the init hands out, which the engine runs later, outside the init
   * burst. Brace counting alone is not enough, because object literals and
   * blocks open braces too, so a nested-function open is only credited when the
   * line actually spells one. */
  const deferred = new Map();   // fnName -> Set(line)
  for (const [name, f] of funcs) {
    const set = new Set();
    let d = 0, nested = null;
    for (let n = f.from; n <= f.to && n <= lines.length; n++) {
      const text = lines[n - 1];
      if (n > f.from && /\bfunction\b|\(/.test(text) && /\{/.test(text)) nested = d;
      const opens = (text.match(/\{/g) || []).length;
      const closes = (text.match(/\}/g) || []).length;
      if (nested !== null) set.add(n);
      d += opens - closes;
      if (nested !== null && d <= nested) nested = null;
    }
    deferred.set(name, set);
  }

  const ident = /[A-Za-z_$][\w$]*/g;
  const refsOn = (n) => {
    const out = [];
    if (n < 1 || n > clean.length) return out;
    const s = stringsOff(clean[n - 1]);
    let m; ident.lastIndex = 0;
    while ((m = ident.exec(s)) !== null) if (!KEYWORDS.has(m[0])) out.push(m[0]);
    return out;
  };

  /* Identifiers sitting in CALL-ARGUMENT position. `host.on(cb)` hands `cb` to
   * someone else, so `cb` runs when the host runs it, not during the init burst --
   * and the per-line nested-function rule cannot see that, because in a one-line
   * `function init() { host.on(cb); }` there is no separate line for the callback.
   * Only BARE identifiers count, and only ones that are top-level FUNCTIONS: a bare
   * identifier argument that is a `const` is a value read at that line, which is a
   * direct read and must stay judged. Getting that distinction wrong in either
   * direction hides a real bug, so it is spelled out rather than assumed. */
  function argFnRefsOn(n) {
    const out = new Set();
    const s = stringsOff(clean[n - 1] || '');
    const call = /[A-Za-z_$][\w$]*\s*\(/g;
    let m;
    while ((m = call.exec(s)) !== null) {
      let i = m.index + m[0].length, depth = 1, buf = '', parts = [];
      while (i < s.length) {
        const c = s[i];
        if (c === '(') { depth++; buf += c; }
        else if (c === ')') { depth--; if (depth === 0) break; buf += c; }
        else if (c === ',' && depth === 1) { parts.push(buf); buf = ''; }
        else buf += c;
        i++;
      }
      parts.push(buf);
      for (const part of parts) {
        const t = part.trim();
        if (/^[A-Za-z_$][\w$]*$/.test(t) && funcs.has(t)) out.add(t);
      }
    }
    return out;
  }

  // --- transitive closure, carrying the edge kind -------------------------
  const direct = new Map();     // name -> line that reached it DIRECTLY
  const deferredHit = new Map();// name -> line that reached it via a callback
  const unresolved = new Set();
  const queue = [];
  const seed = (name, line, kind) => {
    if (kind === 'direct') { if (!direct.has(name)) { direct.set(name, line); queue.push([name, line, 'direct']); } }
    else if (!direct.has(name) && !deferredHit.has(name)) { deferredHit.set(name, line); queue.push([name, line, 'deferred']); }
  };
  for (let n = initFrom_; n <= initTo_; n++) {
    for (const name of refsOn(n)) seed(name, n, 'direct');
  }

  const seenFn = new Map();     // fnName -> weakest kind it was already walked with
  const rank = (k) => (k === 'direct' ? 1 : 0);
  while (queue.length) {
    const [name, atLine, kind] = queue.pop();
    const fn = funcs.get(name);
    /* `!seenFn.has(name)` is load-bearing and was missing for a while: `rank('deferred')`
     * is 0 and the default is also 0, so `rank(kind) > rank(seenFn.get(name) ?? 'deferred')`
     * read `0 > 0` and NEVER opened a function reached through a callback. The symptom
     * was that deferred names silently vanished from the report instead of being
     * reported as deferred, which reads exactly like "there was nothing there". */
    if (fn && (!seenFn.has(name) || rank(kind) > rank(seenFn.get(name)))) {
      /* Rewalk when a function turns out to be reachable more directly than the
       * first path that found it. Without this, whichever path the stack happened
       * to pop first decides the answer for good -- which is how a function whose
       * ONLY caller is a callback can be walked as if the init burst ran it. */
      seenFn.set(name, kind);
      const late = deferred.get(name) || new Set();
      for (let n = fn.from; n <= fn.to; n++) {
        /* THE EDGE KIND PROPAGATES, and getting this wrong is the third version of
         * the same mistake. `armHoldTimer` reads `holdTimer` on its own second line,
         * with nothing nested in between, so a per-line rule calls that DIRECT. But
         * the only caller of `armHoldTimer` is the callback inside
         * `bridge.onCaption(cb)`, so the FUNCTION does not run during the init burst
         * at all -- it runs when a caption arrives. Whether a read is in the dead
         * zone is decided by WHEN the enclosing function runs, not by where the
         * word sits inside it. So a function reached through a callback hands
         * DEFERRED down everything it touches, all the way down. */
        const edge = kind === 'deferred' || late.has(n) ? 'deferred' : 'direct';
        /* The handover names are EXCLUDED from the direct seeding rather than
         * seeded as deferred afterwards. `seed` keeps the first -- strongest --
         * edge it is given, so seeding `cb` as direct from `refsOn` first and as
         * deferred second silently keeps the wrong one. Order of two calls cannot
         * carry that decision; the exclusion can. */
        const asArg = argFnRefsOn(n);
        for (const inner of refsOn(n)) {
          if (asArg.has(inner)) continue;
          seed(inner, n, edge);
        }
        for (const arg of asArg) seed(arg, n, 'deferred');
      }
      continue;
    }
    if (!fn && !declLine.has(name)) unresolved.add(name);
  }

  // --- the verdict --------------------------------------------------------
  const hits = [], deferredOnly = [];
  for (const [name, dline] of declLine) {
    if (dline <= initFrom_ && dline <= initTo_) continue;   // set before init ran
    if (direct.has(name)) {
      if (dline > initFrom_) hits.push({ name, declaredAt: dline, via: direct.get(name) });
    } else if (deferredHit.has(name) && dline > initFrom_) {
      deferredOnly.push({ name, declaredAt: dline, via: deferredHit.get(name) });
    }
  }
  hits.sort((a, b) => a.via - b.via);
  deferredOnly.sort((a, b) => a.via - b.via);
  return {
    bytes: Buffer.byteLength(src), lines: lines.length,
    decls: declLine.size, funcs: funcs.size, reached: seenFn.size,
    unresolved, hits, deferredOnly,
  };
}

let initFrom_ = 0, initTo_ = 0;

// ---------------------------------------------------------------------------
// selftest: three fixtures, three known answers
// ---------------------------------------------------------------------------
function selftest() {
  const dir = mkdtempSync(join(tmpdir(), 'tdz-'));
  const w = (n, body) => { const p = join(dir, n); writeFileSync(p, body, 'utf8'); return p; };

  // A: a real TDZ -- init calls down into a function that reads a later const.
  const a = w('a.js', [
    'init();',                                   // 1  <- init burst
    'function helper() { return LATE; }',        // 2
    'function init() { helper(); }',              // 3
    'const LATE = 1;',                           // 4
    'init();',                                   // 5  (fine: LATE is set by now)
  ].join('\n'));
  /* B is the fixture that cost three wrong instruments, so it is the one that
   * matters: the read of `TIMER` sits on the callback's OWN line with nothing
   * nested around it -- a per-line rule calls it direct -- and the callback is
   * reached only through `host.on(cb)`, which is a deferred edge. Correct answer
   * is NO hit and YES in the deferred list. Two ways this fixture was wrong
   * before it was right, and both are worth keeping in the file:
   *   1. the expectation said `['TIMER']` while the label said "must NOT be a
   *      hit", so it passed for the wrong reason;
   *   2. the burst was 1..2, and line 2 IS the definition of `init`, so `cb` was
   *      seeded direct straight out of the burst and no rule downstream could
   *      ever rescue it. A fixture whose own input is wrong teaches nothing. */
  const b = w('b.js', [
    'init();',                                        // 1  <- init burst
    'function init() { host.on(cb); }',               // 2  deferred edge
    'function cb() { return TIMER; }',                // 3  the read, own line
    'let TIMER = null;',                              // 4  declared after the burst
    'function host() {}',
  ].join('\n'));
  // C: clean -- every binding is initialised before the init burst uses it.
  const c = w('c.js', [
    'const EARLY = 1;',                            // 1
    'init();',                                    // 2
    'function init() { return use(EARLY); }',     // 3
    'function use(x) { return x; }',              // 4
  ].join('\n'));

  const cases = [
    ['A real TDZ (LATE)', a, 1, 1, ['LATE'], []],
    ['B callback (TIMER) - must NOT be a hit', b, 1, 1, [], ['TIMER']],
    ['C clean', c, 2, 2, [], []],
  ];
  let bad = 0;
  console.log('TdzReachOracle selftest');
  console.log('');
  for (const [label, path, from, to, expectHits, expectDeferred] of cases) {
    initFrom_ = from; initTo_ = to;
    const r = scan(path);
    const got = r.hits.map((h) => h.name).sort();
    const gotLate = r.deferredOnly.map((d) => d.name).sort();
    const want = expectHits.slice().sort();
    const wantLate = expectDeferred.slice().sort();
    const ok = JSON.stringify(got) === JSON.stringify(want)
      && JSON.stringify(gotLate) === JSON.stringify(wantLate);
    if (!ok) bad++;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`);
    console.log(`        hits=[${got}] expected=[${want}]`);
    console.log(`        deferred=[${gotLate}] expected=[${wantLate}]`);
  }
  console.log('');
  console.log(bad ? `SELFTEST: RED (${bad} wrong)` : 'SELFTEST: GREEN (3/3)');
  return bad ? 1 : 0;
}

// ---------------------------------------------------------------------------
const argv = process.argv.slice(2);
if (argv[0] === '--selftest') process.exit(selftest());

if (argv.length < 3) {
  console.error('usage: tdz-reach-oracle.js <file> <initFrom> <initTo> | --selftest');
  process.exit(2);
}
const file = resolve(argv[0]);
initFrom_ = Number(argv[1]);
initTo_ = Number(argv[2]);

const r = scan(file);
if (r.error) { console.error(r.error); process.exit(2); }

console.log(`file            ${file}`);
console.log(`bytes           ${r.bytes}`);
console.log(`init burst      ${initFrom_}..${initTo_}`);
console.log(`top-level const/let   ${r.decls}`);
console.log(`top-level functions  ${r.funcs}`);
console.log(`functions reached    ${r.reached}  (transitive fixpoint)`);
console.log(`unresolved names     ${r.unresolved.size}  (referenced, not a top-level binding -- the blind spot)`);
if (r.unresolved.size) console.log(`   ${[...r.unresolved].sort().slice(0, 10).join(' ')}`);
console.log('');
console.log(`TDZ DIRECT   (runs inside the init burst): ${r.hits.length}`);
for (const h of r.hits) {
  console.log(`  ${h.name}  declared:${h.declaredAt}  reached at:${h.via}  => ReferenceError at load`);
}
console.log(`DEFERRED     (behind a callback, runs later -- reported, NOT judged): ${r.deferredOnly.length}`);
for (const d of r.deferredOnly) {
  console.log(`  ${d.name}  declared:${d.declaredAt}  reached at:${d.via}`);
}
console.log('');
console.log(`VERDICT: ${r.hits.length ? 'RED' : 'GREEN'}`);
console.log(`The runtime is the authority: grep the shell log for WARN PAGE_ERROR after a restart.`);
process.exit(r.hits.length ? 1 : 0);