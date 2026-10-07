'use strict';
/**
 * ADVERSARIAL REVIEW — attack 5: did lane 2's changes introduce a regression?
 *
 * Real modules, no DOM, no browser. Asks the two questions a reviewer should:
 *   (a) does the engine's new `reset()` leave anything alive — specifically, can
 *       the CONTINUATION branch (`emittedStart`/`emittedEnd`/`emittedWords`,
 *       `caption-formulation.js`) swallow the next line after a Clear?
 *   (b) does `panel.js` still paint the LEGACY Electron status wire, which is a
 *       bare STRING and not `{text,kind}`?
 *
 *     cmd /c "node _main\_review-panel.js > _main\_review-panel.log 2>&1"
 */
const fs = require('node:fs');
const path = require('node:path');

const REPO = path.normalize(path.join(__dirname, '..'));
const enginePath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const panelPath = path.join(REPO, 'app', 'panel', 'panel.js');
const F = require(enginePath);

const say = (s) => console.log(s);
let fails = 0;
function check(name, real, want) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  if (!ok) fails += 1;
  say(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
  say(`       real = ${JSON.stringify(real)}`);
  say(`       want = ${JSON.stringify(want)}`);
}

function makeEngine() {
  const commits = [];
  const engine = F.createEngine({
    onCommit: (text, reason, meta) => commits.push({ text, reason, meta }),
    onProvisional: () => {},
  });
  return { engine, commits };
}

say('engine: ' + enginePath);
say('');
say('--- (a) reset() leaves nothing alive ---');
{
  const { engine, commits } = makeEngine();
  engine.ingest('o rato roeu', { start: 0, end: 1.2, final: false });
  const before = engine.state();
  check('state() is non-empty after an ingest',
    { committed: before.committed.length + before.provisional.length > 0 }, { committed: true });
  engine.reset();
  const after = engine.state();
  check('reset() empties committed and provisional',
    { c: after.committed, p: after.provisional, lastAudioEnd: after.lastAudioEnd },
    { c: [], p: [], lastAudioEnd: null });
  engine.ingest('o rato roeu', { start: 0, end: 1.2, final: false });
  engine.flush('after-reset');
  check('a line ingested AFTER reset() still commits (nothing swallowed)', commits.length, 1);
  check('and its text is the line itself, not empty', commits[0] && commits[0].text,
    'O rato roeu.');
}

say('');
say('--- (a2) THE SWALLOW TEST: reset() then the SAME line again ---');
{
  const { engine, commits } = makeEngine();
  engine.ingest('a prova dos nove', { start: 5, end: 6.4, final: true });
  engine.flush('first');
  check('the first pass commits once', commits.length, 1);
  engine.reset();                       // the Clear button
  engine.ingest('a prova dos nove', { start: 5, end: 6.4, final: true });
  engine.flush('second');
  check('the SAME line after reset() commits AGAIN (not treated as a re-cover)',
    commits.length, 2);
  check('the two commits are the same text',
    commits.map((c) => c.text), ['A prova dos nove.', 'A prova dos nove.']);
}

say('');
say('--- (a3) the route survives reset() (a cleared buffer must not inherit one) ---');
{
  const { engine, commits } = makeEngine();
  engine.ingest('linha fechada', { start: 0, end: 1, final: true });
  engine.flush('worker-closed');
  engine.reset();
  engine.ingest('linha nova', { start: 9, end: 10, final: false });
  engine.flush('status-change');
  check('the line after a reset is NOT stamped final by the cleared buffer',
    commits.map((c) => c.meta.route), ['final', 'provisional-draft']);
}

say('');
say('--- (b) the legacy status wire: a bare string from the Electron arm ---');
const panel = fs.readFileSync(panelPath, 'utf8');
const lines = panel.split(/\r?\n/);
const i = lines.findIndex((l) => /^function wireStatus\(\)/.test(l));
if (i < 0) { say('SETUP: wireStatus not found'); process.exit(2); }
let j = i;
while (j < lines.length && !(j > i && /^\}/.test(lines[j]))) j += 1;
const body = lines.slice(i, j + 1);
const code = body
  .map((l) => l.replace(/\/\/.*$/, ''))          // strip line comments: the F8
  .join('\n');                                    // comment QUOTES the old regex
say(`wireStatus region: panel.js:${i + 1}-${j + 1} (${body.length} lines, comments stripped below)`);
for (const l of body.slice(0, 8)) say('       ' + l.trim());
say('       ...');
const codeOnly = body.filter((l) => !/^\s*\/\//.test(l.trim()));
for (const l of codeOnly) if (l.trim()) say('   code| ' + l.trim());

const readsString = /typeof\s+payload\s*===\s*['"]string['"]/.test(code)
  || /typeof\s+payload\s*!==\s*['"]object['"]/.test(code)
  || /String\(\s*payload\s*\)/.test(code);
const proseRegex = /(stopped\|error\|dead\|no audio\|no working)/.test(code);
check('wireStatus does NOT classify by prose regex anywhere in its CODE (F8)',
  proseRegex, false);
check('wireStatus reads the event through the factored reader',
  /statusPayload\(payload\)/.test(code), true);

// Execute the two PURE readers, extracted from the live file by line span.
const start = lines.findIndex((l) => /^function statusPayload\(payload\)/.test(l));
const start2 = lines.findIndex((l) => /^function statusKind\(kind\)/.test(l));
if (start < 0 || start2 < 0) { say('SETUP: readers not found'); process.exit(2); }
let end2 = start2;
while (end2 < lines.length && !(end2 > start2 && /^\}/.test(lines[end2]))) end2 += 1;
const src = lines.slice(start, end2 + 1).join('\n');
const ns = {};
new Function('exports', src + '\nexports.statusPayload = statusPayload; exports.statusKind = statusKind;')(ns);
say(`executed readers from panel.js:${start + 1}-${end2 + 1}`);
check('legacy bare STRING (the Electron arm) -> text, no kind',
  ns.statusPayload('boom'), { text: 'boom', kind: null });
check('the app\'s {text,kind} -> both kept',
  ns.statusPayload({ text: 'x', kind: 'ERROR' }), { text: 'x', kind: 'error' });
check('a missing payload changes nothing',
  ns.statusPayload(undefined), { text: '', kind: null });
check('kind is read verbatim, never guessed',
  [ns.statusKind('error'), ns.statusKind('live'), ns.statusKind('busy'), ns.statusKind('')],
  ['error', 'live', '', '']);
check('an UNKNOWN kind is neutral, not an error',
  ns.statusKind('device-exhausted'), '');

say('');
say(`RESULT: ${fails === 0 ? 'GREEN' : 'RED'} — ${fails} failing check(s)`);
process.exit(fails === 0 ? 0 : 1);
