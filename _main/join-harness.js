// Oracle for the caption pipeline.
//
// IT LOADS THE REAL MODULE. `require('../app/panel/caption-formulation.js')`
// — not a copy of it. The previous version of this file pasted a hand-copied
// transcription of the join functions out of `panel.js`, which is a gate that
// can go GREEN while the product is broken: the copy and the source drift
// silently and nothing notices. That risk is why the text decisions now live
// in a module this harness can actually import.
//
// Arms 1-6 are the ORIGINAL six, kept so the old regressions cannot come back.
// Arms 7-10 are new and cover what the formulation layer adds.
//
// THE SAME ARMS RUN AGAINST THE OLD CODE. `--impl=<path>` swaps in another
// module exposing the same interface, which is how the negative control is
// produced (`_main/control/caption-formulation-pre.js`). One arm list, two
// implementations, so "the new arms go red on the old code" is a measured
// run rather than an argument.

'use strict';

const path = require('node:path');

const IMPL = (() => {
  const flag = process.argv.find((a) => a.startsWith('--impl='));
  return path.resolve(flag ? flag.slice('--impl='.length) : path.join(__dirname, '..', 'app', 'panel', 'caption-formulation.js'));
})();
const LABEL = path.basename(IMPL) === 'caption-formulation.js' ? 'REAL' : 'CONTROL';

const mod = require(IMPL);
const { createEngine, formulate, describeReadiness, SENTENCE_GAP_S, SENTENCE_MAX_CHARS, READY_SECONDS_MEASURED } = mod;

// A stubbed clock, advanced by the test rather than by real time, so the
// hold-timeout arm is deterministic instead of a race.
let NOW = 1000000;

/** Committed (final) lines, in the order the panel would render them. */
let committedLines = [];
/** The provisional text most recently pushed to the DOM. */
let provisionalText = '';

/**
 * A fresh engine wired to the same two sinks panel.js uses.
 * @param {{start?:number,end?:number}} [meta]
 */
function freshEngine() {
  committedLines = [];
  provisionalText = '';
  return createEngine({
    onCommit: (text) => {
      committedLines.push(text);
    },
    onProvisional: (text) => {
      provisionalText = text;
    },
    now: () => NOW,
  });
}

/**
 * Feed a fragment as the worker emits it: text plus its audio window.
 *
 * `mod.advance` is the test-only seam the pre-change control needs, because
 * the old engine read the wall clock itself instead of taking an injected
 * `now`. It is optional, so the real engine is driven exactly as the panel
 * drives it and the control is driven on the same terms.
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
function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
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
// The original arm 6 regression, in the new world. There is no audio
// timestamp to reason about after the stop, so the wall-clock hold timeout is
// what must close it — otherwise the last words are stranded forever.
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
    warming.body.includes(`${READY_SECONDS_MEASURED} s`), true);
  const ready = describeReadiness(READY_SECONDS_MEASURED * 1000 + 1);
  check('arm10 past the measurement it is ready', ready.state, 'ready');
  check('arm10 there is no third state',
    [warming.state, ready.state].every((s) => s === 'warming' || s === 'ready'), true);
}

console.log(
  `${LABEL} JOIN-HARNESS: ` +
  (fails === 0 ? 'PASS (10 arms)' : `${fails} FAILED`) +
  `  impl=${IMPL}`,
);
process.exit(fails === 0 ? 0 : 1);
