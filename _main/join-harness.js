// Oracle for the caption pipeline.
//
// IT LOADS THE REAL MODULE. require('../app/panel/caption-formulation.js')
// — not a copy of it. The previous version of this file pasted a hand-copied
// transcription of the join functions out of panel.js, which is a gate that
// can go GREEN while the product is broken: the copy and the source drift
// silently and nothing notices. That risk is why the text decisions now live
// in a module this harness can actually import.
//
// Arms 1-6 are the ORIGINAL six, kept so the old regressions cannot come back.
// Arms 7-10 are new and cover what the formulation layer adds. Arm 11 (added
// 2026-10-11) pins the PROVISIONAL CALLBACK CONTRACT on both sides.
//
// THE SAME ARMS RUN AGAINST THE OLD CODE. --impl=<path> swaps in another module
// exposing the same interface, which is how the negative control is produced
// (_main/control/caption-formulation-pre.js). One arm list, two
// implementations, so "the new arms go red on the old code" is a measured run
// rather than an argument.
//
// ── RE-BASELINED 2026-10-11: THE PROVISIONAL CALLBACK'S SHIPPED SHAPE ────────
//
// This harness went RED — REAL JOIN-HARNESS: 6 FAILED — and the six were exactly
// the checks that read the PROVISIONAL line. The stale expectation was HERE, not
// in the module. The stub below used to be
//
//     onProvisional: (text) => { provisionalText = text; }
//
// which is the PRE-change renderer's convention ((text, isProvisional) — it
// survives in the old-module control, _main/control/caption-formulation-pre.js
// line 108), and it captured ONE argument and expected a joined STRING. The
// shipped engine calls, at app/panel/caption-formulation.js:737:
//
//     onProvisional(committed, provisional);      // TWO arrays of TOKEN objects
//
// and the one live caller it has is app/panel/panel.js:676:
//
//     onProvisional: (committed, provisional) => renderProvisional(committed, provisional, key),
//
// whose renderer derives its two word arrays with (panel.js:758-759):
//
//     Array.isArray(committed)   ? committed.map(t => t.w)   : []
//     Array.isArray(provisional) ? provisional.map(t => t.w) : []
//
// — a STRING first argument paints ZERO words on the row. So the token-array
// contract IS the shipped one, and the string expectation was this harness's own
// stale copy of the old convention. Note what the stale stub structurally COULD
// NOT see: after a re-read the whole line sits in 'provisional' and 'committed'
// is EMPTY (caption-formulation.js:622-632), so arm3 was shown one word of two,
// and arm1 eleven of twelve. The six failing checks were exactly the six that
// read this stub; every committed-path arm PASSED in the same run, which is the
// signature of a stale reader, not of a broken engine.
//
// The stub now reads what the panel reads, and ARM 11 PINS THE CONTRACT ON BOTH
// SIDES — the module's call site AND the caller's wiring, read from the bytes on
// disk — so the next drift is a NAMED FAIL instead of a stale green.
//
// --neg-arm reverts the contract in COPIES under %TEMP% and requires the gate to
// go RED, printing the failing check names. TWO mutants, one per side: M1 the
// module's call site back to the string form, M2 the caller's wiring back to the
// pre-change shape (a caller that stopped reading arrays would silently paint
// nothing while the module stayed correct — the module instrument cannot see
// that, which is why the caller's bytes are pinned too).

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const ROOT = path.join(__dirname, '..');
/** The shipped module and the shipped caller — the two halves of the contract. */
const REAL_IMPL = path.join(ROOT, 'app', 'panel', 'caption-formulation.js');
const REAL_PANEL = path.join(ROOT, 'app', 'panel', 'panel.js');

const flagValue = (name, fallback) => {
  const flag = process.argv.find((a) => a.startsWith('--' + name + '='));
  return path.resolve(flag ? flag.slice(name.length + 3) : fallback);
};
const IMPL = flagValue('impl', REAL_IMPL);
const PANEL = flagValue('panel', REAL_PANEL);
const NEG_ARM = process.argv.includes('--neg-arm');
const LABEL = path.basename(IMPL) === 'caption-formulation.js' ? 'REAL' : 'CONTROL';

const mod = require(IMPL);
const { createEngine, formulate, describeReadiness, SENTENCE_GAP_S, SENTENCE_MAX_CHARS, READY_SECONDS_MEASURED } = mod;

// ── THE SHIPPED CONTRACT, READ FROM THE BYTES ───────────────────────────────
// Never asserted from memory: the module's call site and the caller's wiring are
// both read here, exactly as they are on disk, and pinned by arm 11.
const IMPL_SRC = fs.readFileSync(IMPL, 'utf8');
const PANEL_SRC = fs.readFileSync(PANEL, 'utf8');
/** The call the shipped engine makes, character for character. */
const CONTRACT_CALL = 'onProvisional(committed, provisional);';
/** The PRE-change call, kept ONLY as the neg-arm's revert target. */
const OLD_CONTRACT_CALL = 'onProvisional(visibleText(), true);';
/** '<name>: (a, b) => <callee>(a, b, ...)' — the caller's own wiring line. */
const WIRING_RE = /onProvisional:\s*\(([^)]*)\)\s*=>\s*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)/;
/** The caller's coercion: without BOTH of these a non-array paints no words. */
const ARRAY_COERCIONS = ['Array.isArray(committed)', 'Array.isArray(provisional)'];
const wiring = WIRING_RE.exec(PANEL_SRC);
const wiringParams = wiring ? wiring[1].split(',').map((s) => s.trim()).filter(Boolean) : [];
const wiringArgs = wiring ? wiring[3].split(',').map((s) => s.trim()).filter(Boolean) : [];
const wiringCoercions = ARRAY_COERCIONS.filter((c) => PANEL_SRC.includes(c));

// A stubbed clock, advanced by the test rather than by real time, so the
// hold-timeout arm is deterministic instead of a race.
let NOW = 1000000;

/** Committed (final) lines, in the order the panel would render them. */
let committedLines = [];
/** The provisional text most recently pushed to the DOM. */
let provisionalText = '';
/** How many times the engine reported a provisional line. */
let provisionalCalls = 0;
/** The KINDS of the last call's arguments — the contract, observed. */
let lastProvisionalShape = null;
/** The last call's raw token arrays, for the per-token shape check. */
let lastProvisionalTokens = null;
/** Every call that did NOT hand the panel the two token arrays it consumes. */
let contractViolations = [];

/**
 * A fresh engine wired to the same two sinks panel.js uses.
 *
 * onProvisional READS WHAT THE PANEL READS. The two-array reading and the
 * Array.isArray coercion below are panel.js:758-759's own — copied, not
 * invented — because the claim this harness makes is "what the box would paint",
 * and a stub that accepted a string the panel would refuse to paint would turn a
 * broken renderer into a green gate.
 */
function freshEngine() {
  committedLines = [];
  provisionalText = '';
  provisionalCalls = 0;
  lastProvisionalShape = null;
  lastProvisionalTokens = null;
  contractViolations = [];
  return createEngine({
    onCommit: (text) => {
      committedLines.push(text);
    },
    onProvisional: (...args) => {
      provisionalCalls += 1;
      const committedArg = args[0];
      const provisionalArg = args[1];
      lastProvisionalShape = args.map((a) => (Array.isArray(a) ? 'array' : a === null ? 'null' : typeof a));
      lastProvisionalTokens = [committedArg, provisionalArg];
      // panel.js:758-759, character for character in behaviour: only ARRAYS of
      // tokens contribute words to the row.
      const confWords = Array.isArray(committedArg) ? committedArg.map((t) => t.w) : [];
      const provWords = Array.isArray(provisionalArg) ? provisionalArg.map((t) => t.w) : [];
      provisionalText = confWords.concat(provWords).join(' ');
      if (args.length !== 2 || !Array.isArray(committedArg) || !Array.isArray(provisionalArg)) {
        contractViolations.push(args.length + ' arg(s) [' + lastProvisionalShape.join(',') + ']');
      }
    },
    now: () => NOW,
  });
}

/**
 * Feed a fragment as the worker emits it: text plus its audio window.
 *
 * mod.advance is the test-only seam the pre-change control needs, because the
 * old engine read the wall clock itself instead of taking an injected 'now'. It
 * is optional, so the real engine is driven exactly as the panel drives it and
 * the control is driven on the same terms.
 */
function feed(engine, text, start, end, dtMs = 560) {
  NOW += dtMs;
  if (typeof mod.advance === 'function') mod.advance(dtMs);
  engine.ingest(text, { start, end });
}

/** Advance the stubbed clock without feeding anything (a silent stream). */
function tick(ms) {
  NOW += ms;
  if (typeof mod.advance === 'function') mod.advance(ms);
}

let fails = 0;
const failedNames = [];
function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) {
    fails += 1;
    failedNames.push(name);
  }
  console.log((ok ? 'PASS ' : 'FAIL ') + name + '  got=' + JSON.stringify(got) + (ok ? '' : ' want=' + JSON.stringify(want)));
}

// ── ARM 1: a burst of fragments becomes ONE line, not N lines ───────────────
// Measured cadence: one fragment per 0.56 s of audio, contiguous.
{
  const e = freshEngine();
  for (let i = 0; i < 12; i++) feed(e, 'w' + i, i * 0.56, (i + 1) * 0.56);
  check('arm1 nothing committed while the burst is open', committedLines, []);
  check('arm1 the whole burst is on screen as one line', provisionalText,
    'w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11');
  check('arm1 negative control: not 12 lines', committedLines.length !== 12, true);
  // ONE REPORT PER FRAGMENT is what keeps the live line moving (the word ramp and
  // the typing reveal are driven from it), so the count is pinned here rather
  // than left as an unread counter.
  check('arm1 the engine reported the line once per fragment', provisionalCalls, 12);
}

// ── ARM 2: a real pause in the AUDIO closes the sentence ────────────────────
// This is the arm the old 1200 ms WALL-CLOCK rule could not pass: the gap here
// is 11.20 s of audio but only ~1 s of wall clock between fragments.
{
  const e = freshEngine();
  feed(e, 'hello', 0.0, 0.56);
  feed(e, 'there', 0.56, 1.12);
  feed(e, 'again', 12.32, 12.88, 900);   // 11.20 s of audio silence
  check('arm2 the pause closed the first line', committedLines, ['Hello there.']);
  check('arm2 the next fragment starts the next line', provisionalText, 'again');
  e.flush();
  check('arm2 tail flushed', committedLines, ['Hello there.', 'Again.']);
}

// ── ARM 3: a gap SHORTER than a sentence does not split the line ────────────
// The negative half of arm 2, and the one that keeps the threshold honest:
// 2.80 s is the largest within-burst gap measured in the owner's run.
{
  const e = freshEngine();
  feed(e, 'this', 0.0, 0.56);
  feed(e, 'is', 3.36, 3.92);             // 2.80 s of audio silence
  check('arm3 a 2.80s gap did NOT close the line', committedLines, []);
  check('arm3 the words are still one line', provisionalText, 'this is');
}

// ── ARM 4: empties are ignored ──────────────────────────────────────────────
{
  const e = freshEngine();
  feed(e, '', 0.0, 0.56);
  feed(e, '   ', 0.56, 1.12);
  feed(e, 'real', 1.12, 1.68);
  e.flush();
  check('arm4 empties ignored', committedLines, ['Real.']);
}

// ── ARM 5: the hard cap still closes a run-on ───────────────────────────────
// Without this, a model that never pauses grows one line forever.
{
  const e = freshEngine();
  for (let i = 0; i < 40; i++) feed(e, 'abcdefghij', i * 0.56, (i + 1) * 0.56);
  check('arm5 the cap closed some lines', committedLines.length >= 2, true);
  check('arm5 no line exceeds the cap',
    committedLines.every((l) => l.length <= SENTENCE_MAX_CHARS + 1), true);
}

// ── ARM 6: the stream STOPS mid-sentence; the tail still lands ──────────────
// The original arm 6 regression, in the new world. There is no audio timestamp
// to reason about after the stop, so the wall-clock hold timeout is what must
// close it — otherwise the last words are stranded forever.
//
// Note what is NOT asserted here: "g" + "gen" + "s" is three separate word
// DELTAs from the worker, so the line is "G gen s." and not "G gens.". The
// engine joins with spaces and never splices fragments into one token; an
// earlier draft of this arm asserted that merge and was simply wrong.
{
  const e = freshEngine();
  feed(e, 'g', 0.0, 0.56);
  feed(e, 'gen', 0.56, 1.12);
  feed(e, 's', 1.12, 1.68);
  check('arm6 nothing committed while the tail is held', committedLines, []);
  tick(2000);                              // the stream went silent
  feed(e, '', 0, 0);                      // no further audio arrives
  e.flush();
  check('arm6 the stopped stream still landed its words', committedLines, ['G gen s.']);
}

// ── ARM 7 (NEW, acceptance i): a REVISED tail is rewritten, not duplicated ─
// The measured case from the owner's run: "cre" then "s" then "partici" then
// "s" re-read the same audio, and the old join rendered "cre s partici".
{
  const e = freshEngine();
  feed(e, 'going along', 0.0, 1.12);
  feed(e, 'slush', 1.12, 1.68);
  check('arm7 first reading is provisional', provisionalText, 'going along slush');
  // The model re-reads the SAME audio and revises its last word.
  feed(e, 'slush country', 1.12, 2.24);
  check('arm7 the revision did not duplicate the old words',
    provisionalText, 'going along slush country');
  check('arm7 no duplicated token', provisionalText.includes('slush slush'), false);
  // And revises it again, harder.
  feed(e, 'slushy country', 1.12, 2.24);
  check('arm7 the second revision replaced, not appended',
    provisionalText, 'going along slushy country');
  check('arm7 still no duplicate', provisionalText.includes('slushy slushy'), false);
  e.flush();
  check('arm7 exactly one committed line', committedLines.length, 1);
  check('arm7 the committed line has no garbage', committedLines[0], 'Going along slushy country.');
}

// ── ARM 8 (NEW, acceptance ii): a pause longer than the cadence closes it ───
// A gap far longer than the ~1 s wall cadence but SHORTER than arm 2's pause,
// to show the boundary is the AUDIO clock and not the wall clock.
{
  const e = freshEngine();
  feed(e, 'going along', 0.0, 1.12);
  feed(e, 'slush', 1.12, 1.68);
  const wallBefore = NOW;
  feed(e, 'country', 1.68 + SENTENCE_GAP_S + 0.1, 2.24 + SENTENCE_GAP_S + 0.1, 700);
  check('arm8 a >8s audio gap closed the line even at 700ms wall', committedLines,
    ['Going along slush.']);
  check('arm8 the wall gap really was under the old 1200ms rule', NOW - wallBefore < 1200, true);
  e.flush();
  check('arm8 the rest landed', committedLines, ['Going along slush.', 'Country.']);
}

// ── ARM 9 (NEW, acceptance iii): the punctuation/casing pass ────────────────
// The literal input from the brief.
{
  check('arm9 the brief sentence', formulate('going along slush country roadss'),
    'Going along slush country roadss.');
  check('arm9 it does not touch the interior',
    formulate('going along slush country roadss').replace('Going along slush country roadss.', ''), '');
  check('arm9 existing terminal punctuation is not doubled',
    formulate('this is a full sentence.'), 'This is a full sentence.');
  check('arm9 an interrogative opener gets a question mark',
    formulate('what is the cadence here'), 'What is the cadence here?');
  check('arm9 empty text stays empty', formulate('   '), '');
  check('arm9 casing applies through the engine too', formulate('élan'), 'Élan.');
}

// ── ARM 10 (NEW, acceptance c): one honest readiness state ──────────────────
{
  const warming = describeReadiness(0);
  check('arm10 at launch the state is warming', warming.state, 'warming');
  check('arm10 it states the measured seconds',
    warming.body.includes(READY_SECONDS_MEASURED + ' s'), true);
  const ready = describeReadiness(READY_SECONDS_MEASURED * 1000 + 1);
  check('arm10 past the measurement it is ready', ready.state, 'ready');
  check('arm10 there is no third state',
    [warming.state, ready.state].every((s) => s === 'warming' || s === 'ready'), true);
}

// ── ARM 11 (NEW 2026-10-11): THE PROVISIONAL CALLBACK'S SHIPPED CONTRACT ────
// The arm that would have caught the 6-FAILED drift instead of going stale. It
// asserts the callback's shape at RUNTIME, and it reads the contract out of the
// two files that define it: the module's call site and the caller's wiring.
// Either side drifting alone is a RED with a name.
{
  const e = freshEngine();
  feed(e, 'contract pin', 0.0, 0.56);
  const tokens = Array.isArray(lastProvisionalTokens[0]) && Array.isArray(lastProvisionalTokens[1])
    ? lastProvisionalTokens[0].concat(lastProvisionalTokens[1]) : [];
  check('arm11 the callback carries two token arrays', lastProvisionalShape, ['array', 'array']);
  check('arm11 the callback never left the array path', contractViolations, []);
  check('arm11 the callback union equals visible()', provisionalText, e.visible());
  check('arm11 every token carries w a b',
    tokens.length > 0 && tokens.every((t) => t && typeof t.w === 'string'
      && (t.a === null || typeof t.a === 'number') && (t.b === null || typeof t.b === 'number')), true);
  check('arm11 the module still calls onProvisional(committed, provisional)',
    IMPL_SRC.split(CONTRACT_CALL).length - 1, 1);
  check('arm11 the caller still passes both arrays to renderProvisional',
    [wiring !== null, wiringParams, wiringArgs.slice(0, 2), wiringParams.length === 2],
    [true, ['committed', 'provisional'], ['committed', 'provisional'], true]);
  check('arm11 the caller still paints only arrays', wiringCoercions, ARRAY_COERCIONS);
}

if (fails) console.log('FAILING CHECKS (' + fails + '): ' + failedNames.join(' | '));
console.log(
  LABEL + ' JOIN-HARNESS: ' +
  (fails === 0 ? 'PASS (11 arms)' : fails + ' FAILED') +
  '  impl=' + IMPL,
);

// ── NEG-ARM: THE GATE MUST BE ABLE TO SAY NO ────────────────────────────────
// Nothing above proves the gate can FAIL on the contract it now reads, so this
// reverts the contract in COPIES (never in the shipped files) and requires RED,
// with the failing check names printed. Both sides are reverted, one mutant
// each, because either can break the row alone: the module handing the panel a
// string, and the caller that stopped reading arrays.
function sha256(text) {
  return crypto.createHash('sha256').update(text).digest('hex').toUpperCase();
}

function writeMutant(dir, name, text) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, text);
  return { path: p, bytes: Buffer.byteLength(text), sha256: sha256(text) };
}

function runCase(implPath, panelPath) {
  const child = spawnSync(process.execPath, [__filename, '--impl=' + implPath, '--panel=' + panelPath], {
    cwd: ROOT,
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 64 * 1024 * 1024,
    env: Object.assign({}, process.env, { TMPDIR: process.env.TMPDIR || 'I:\\cc-tmp' }),
  });
  const out = String(child.stdout || '') + String(child.stderr || '');
  const m = /FAILING CHECKS \(\d+\): (.*)/.exec(out);
  const names = (m ? m[1] : '').split(' | ').map((s) => s.trim()).filter(Boolean);
  return { rc: child.status, out: out, names: names };
}

function reportCase(label, mutant, result, expect) {
  if (!mutant || !result) {
    console.log('  ' + label);
    console.log('    COPY NOT BUILT or not run — the shipped bytes it reverts were not found exactly once. OPEN, not green.');
    return false;
  }
  const missing = expect.filter((n) => result.names.indexOf(n) === -1);
  const extra = result.names.filter((n) => expect.indexOf(n) === -1);
  console.log('  ' + label);
  console.log('    copy   ' + mutant.path + '  ' + mutant.bytes + ' B  sha256=' + mutant.sha256);
  console.log('    child  rc=' + result.rc + '  failing=' + result.names.length +
    '  expected-named=' + (expect.length - missing.length) + '/' + expect.length);
  console.log('    child FAILING CHECKS: ' + (result.names.join(' | ') || '(none)'));
  if (missing.length) console.log('    MISSING RED NAMES: ' + missing.join(' | '));
  if (extra.length) console.log('    UNEXPECTED RED NAMES: ' + extra.join(' | '));
  return result.rc === 1 && missing.length === 0;
}

function runNegArm() {
  const tempRoot = process.env.TMPDIR || process.env.TEMP || 'I:\\cc-tmp';
  const dir = path.join(tempRoot, 'join-harness-neg-arm-' + process.pid);
  fs.mkdirSync(dir, { recursive: true });

  const implReal = fs.readFileSync(REAL_IMPL, 'utf8');
  const panelReal = fs.readFileSync(REAL_PANEL, 'utf8');
  const callHits = implReal.split(CONTRACT_CALL).length - 1;

  // M1 — the module's call site back to the PRE-change string convention.
  const m1 = callHits === 1
    ? writeMutant(dir, 'caption-formulation-call-reverted.js', implReal.split(CONTRACT_CALL).join(OLD_CONTRACT_CALL))
    : null;
  // M2 — the caller's wiring back to the pre-change shape: a string parameter
  // list, and a renderer that no longer coerces through Array.isArray.
  const wiringLine = 'onProvisional: (committed, provisional) => renderProvisional(committed, provisional, key),';
  const confLine = 'const confWords = Array.isArray(committed) ? committed.map(t => t.w) : [];';
  const provLine = 'const provWords = Array.isArray(provisional) ? provisional.map(t => t.w) : [];';
  const m2Hits = [wiringLine, confLine, provLine].map((s) => panelReal.split(s).length - 1);
  const m2 = m2Hits.every((n) => n === 1)
    ? writeMutant(dir, 'panel-caller-reverted.js', panelReal
      .split(wiringLine).join('onProvisional: (text, isProvisional) => renderProvisional(text, isProvisional, key),')
      .split(confLine).join("const confWords = String(committed == null ? '' : committed).trim().split(' ').filter(Boolean);")
      .split(provLine).join("const provWords = String(provisional == null ? '' : provisional).trim().split(' ').filter(Boolean);"))
    : null;

  const M1_EXPECT = [
    'arm1 the whole burst is on screen as one line',
    'arm2 the next fragment starts the next line',
    'arm3 the words are still one line',
    'arm7 first reading is provisional',
    'arm7 the revision did not duplicate the old words',
    'arm7 the second revision replaced, not appended',
    'arm11 the callback carries two token arrays',
    'arm11 the callback never left the array path',
    'arm11 the callback union equals visible()',
    'arm11 every token carries w a b',
    'arm11 the module still calls onProvisional(committed, provisional)',
  ];
  const M2_EXPECT = [
    'arm11 the caller still passes both arrays to renderProvisional',
    'arm11 the caller still paints only arrays',
  ];

  console.log('── NEG-ARM (contract reverted in COPIES under ' + tempRoot + ') ──');
  const control = runCase(REAL_IMPL, REAL_PANEL);
  console.log('  N0 control  real module + real caller  rc=' + control.rc +
    '  failing=' + control.names.length + '  (must be GREEN)');
  let ok = control.rc === 0 && control.names.length === 0;
  const verdicts = [];

  const r1 = m1 ? runCase(m1.path, REAL_PANEL) : null;
  const green1 = reportCase('M1 module call reverted to onProvisional(visibleText(), true)', m1, r1, M1_EXPECT);
  verdicts.push('M1=' + (green1 ? 'RED-as-required' : 'NOT-RED'));
  ok = ok && green1;

  const r2 = m2 ? runCase(REAL_IMPL, m2.path) : null;
  const green2 = reportCase('M2 caller wiring reverted to the string form', m2, r2, M2_EXPECT);
  verdicts.push('M2=' + (green2 ? 'RED-as-required' : 'NOT-RED'));
  ok = ok && green2;

  console.log('  NEG-ARM: ' + (ok ? 'PASS' : 'FAIL') + '  control-green=' + (control.rc === 0) + '  ' + verdicts.join('  '));
  return ok;
}

let negOk = true;
if (NEG_ARM) negOk = runNegArm();
process.exit(fails === 0 && negOk ? 0 : 1);
