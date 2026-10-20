#!/usr/bin/env node
/**
 * SCOPE-LEAK ORACLE -- every selector member of every theme stylesheet must be
 * rooted at a theme scope.
 *
 * WHY THIS FILE EXISTS (2026-10-11): the theme scope gate and the per-member
 * oracle both cover theme-{1..5}.css only, and panel-designs.css -- a generated
 * file that is the LAST stylesheet the panel loads -- carried the same defect
 * UNGUARDED: 22 unscoped selector members, one of which
 * (`.caption__mark{display:none}`) beat panel.css's own rule at the same
 * specificity and hid the forming line's tail marker in the shipped build
 * (panel.css:2278 says display:inline; panel-designs.css is loaded last).
 * A defect with no gate is a defect that comes back.
 *
 * WHAT IT IS NOT: it does not render and does not launch anything. It parses the
 * bytes, and it can say NO -- see --neg-arm.
 *
 * EXIT CODES: the normal run is 0 PASS / 1 FAIL. `--neg-arm` is 1 BY DESIGN when
 * it passes (the negative arm is SUPPOSED to find the leak), 0 when a mutant was
 * NOT caught, and 2 when an anchor is missing or ambiguous -- a decorative mutant
 * is worse than no mutant at all, so the oracle refuses to count it.
 *
 * Usage: node _main/scope-leak-oracle.js [--dir <dir>] [--neg-arm]
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const argv = process.argv.slice(2);
const argOf = (name, dflt) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : dflt;
};
const DIR = path.resolve(argOf('--dir', path.join(ROOT, 'app', 'panel', 'themes')));
const NEG = argv.includes('--neg-arm');

// The two theme-scope forms this repo writes:
//   :root[data-theme='theme-3']    (exact)
//   :root[data-theme^='cine-']     (prefix, one file per theme SET)
const SCOPE_RE = /^:root\[data-theme(?:[~^|*$])?=/;
// Keyframe steps are scoped by their @keyframes wrapper, not by a member prefix.
const STEP_RE = /^(\d+(?:\.\d+)?%|from|to)$/i;

/** Split a stylesheet into top-level block preludes; comments blanked, offsets kept. */
function preludes(css) {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
  const out = [];
  let start = 0;
  let depth = 0;
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === '{') {
      if (depth === 0) out.push({ text: src.slice(start, i), line: src.slice(0, start).split('\n').length });
      depth += 1;
    } else if (c === '}') {
      depth -= 1;
      if (depth === 0) start = i + 1;
    }
  }
  return out;
}

function scan(css) {
  const leaked = [];
  let count = 0;
  let atRules = 0;
  let stepLists = 0;
  for (const { text, line } of preludes(css)) {
    const prelude = text.replace(/\s+/g, ' ').trim();
    if (!prelude) continue;
    if (prelude.startsWith('@')) { atRules += 1; continue; }
    const members = prelude.split(',').map((m) => m.trim()).filter(Boolean);
    if (!members.length) continue;
    if (members.every((m) => STEP_RE.test(m))) { stepLists += 1; continue; }
    count += 1;
    for (const m of members) if (!SCOPE_RE.test(m)) leaked.push(m + '   [line ' + line + ']');
  }
  return { leaked, preludes: count, atRules, stepLists };
}

function scanFile(file) {
  const bytes = fs.readFileSync(file);
  const r = scan(bytes.toString('utf8'));
  return {
    name: path.basename(file),
    bytes: bytes.length,
    sha: crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase().slice(0, 16),
    ...r,
  };
}

function report(rows, label, dir) {
  console.log('SCOPE-LEAK ORACLE -- ' + label + '\n  dir: ' + dir);
  let bad = 0;
  for (const r of rows) {
    const ok = r.leaked.length === 0;
    if (!ok) bad += 1;
    console.log('  ' + (ok ? 'GREEN' : 'RED  ') + ' ' + r.name.padEnd(20) +
      ' preludes=' + String(r.preludes).padEnd(5) + ' at-rules=' + String(r.atRules).padEnd(4) +
      ' step-lists=' + String(r.stepLists).padEnd(4) + ' leaked=' + r.leaked.length +
      '  B=' + r.bytes + ' sha256[0:16]=' + r.sha);
    for (const m of r.leaked.slice(0, 6)) console.log('        LEAKED MEMBER: ' + m);
    if (r.leaked.length > 6) console.log('        ... and ' + (r.leaked.length - 6) + ' more');
  }
  return bad;
}

const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.css')).sort()
  .map((f) => path.join(DIR, f));
if (!files.length) {
  console.error('SETUP ERROR: no .css under ' + DIR);
  process.exit(2);
}
const rows = files.map(scanFile);

if (!NEG) {
  report(rows, 'PRISTINE (the shipped bytes)', DIR);
  const total = rows.reduce((n, r) => n + r.leaked.length, 0);
  console.log(total === 0
    ? '\nVERDICT: PASS -- ' + rows.length + ' stylesheet(s), every selector member rooted at a theme scope.'
    : '\nVERDICT: FAIL -- ' + total + ' unscoped selector member(s).');
  process.exit(total === 0 ? 0 : 1);
}

// ---- NEGATIVE ARM: the SAME scan, against copies that MUST come out RED ----
// House rule: TMPDIR is I:\cc-tmp on this box; G: fills and kills lanes with ENOSPC.
//
// THE MUTANTS ARE TEXTUAL, ON A UNIQUE ANCHOR, in a file this oracle judges.
// The anchor is declared as an EXACT string; before it is used the oracle COUNTS
// it in the file. An anchor that is missing (the stylesheet was regenerated and
// the oracle is now stale) or that appears more than once (the mutation would
// hit the wrong member) is DECORATIVE: it proves nothing, so the oracle refuses
// to count it, says so, and exits 2. A mutant that loads and changes nothing is
// reported as SURVIVED -- the gate is blind there -- and the arm fails.
const MUTANTS = [
  {
    file: 'theme-1.css',
    tag: 'M1 theme-1.css: the hover pair loses the scope of its second member',
    anchor: ":root[data-theme='theme-1'] .icon-button:hover,\r\n:root[data-theme='theme-1'] .strip-button:hover",
    replace: ":root[data-theme='theme-1'] .icon-button:hover,\r\n.strip-button:hover",
  },
  {
    file: 'theme-1.css',
    tag: 'M2 theme-1.css: the history note pair loses the scope of its second member',
    anchor: ":root[data-theme='theme-1'] .history__note,\r\n:root[data-theme='theme-1'] .history__count",
    replace: ":root[data-theme='theme-1'] .history__note,\r\n.history__count",
  },
  {
    file: 'panel-designs.css',
    tag: 'M3 panel-designs.css: the hover pair loses the scope of its second member',
    anchor: ":root[data-theme='pd-tele'] .icon-button:hover,\r\n:root[data-theme='pd-tele'] .strip-button:hover",
    replace: ":root[data-theme='pd-tele'] .icon-button:hover,\r\n.strip-button:hover",
  },
  {
    file: 'panel-designs.css',
    tag: 'M4 panel-designs.css: .caption__mark loses its scope (the rule that actually shipped)',
    anchor: ":root[data-theme='pd-tele'] .caption__time,\r\n:root[data-theme='pd-tele'] .caption__mark",
    replace: ":root[data-theme='pd-tele'] .caption__time,\r\n.caption__mark",
  },
];

const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-scope-neg-'));
const countOf = (hay, needle) => hay.split(needle).length - 1;
let wrong = 0;
let decorative = 0;
let caught = 0;
for (const m of MUTANTS) {
  const srcPath = path.join(DIR, m.file);
  if (!fs.existsSync(srcPath)) {
    console.log('  RED   mutant ' + m.tag.padEnd(48) + ' FILE MISSING -- DECORATIVE, not counted');
    decorative += 1;
    wrong += 1;
    continue;
  }
  const src = fs.readFileSync(srcPath, 'utf8');
  const hits = countOf(src, m.anchor);
  if (hits !== 1) {
    console.log('  RED   mutant ' + m.tag.padEnd(48) + ' ANCHOR ' + (hits === 0 ? 'MISSING' : 'AMBIGUOUS')
      + ' (' + hits + ' hit(s)) -- DECORATIVE, not counted');
    decorative += 1;
    wrong += 1;
    continue;
  }
  const text = src.replace(m.anchor, m.replace);
  if (text === src) {
    console.log('  RED   mutant ' + m.tag.padEnd(48) + ' ANCHOR applied to NOTHING -- DECORATIVE, not counted');
    decorative += 1;
    wrong += 1;
    continue;
  }
  const p = path.join(scratch, 'arm-' + m.tag.replace(/[^\w]+/g, '-') + '.css');
  fs.writeFileSync(p, text);
  const got = scanFile(p);
  const red = got.leaked.length > 0;
  if (red) caught += 1; else wrong += 1;
  console.log('  ' + (red ? 'PASS' : 'FAIL') + ' ' + m.tag.padEnd(48) +
    ' want=RED got=' + (red ? 'RED' : 'GREEN') +
    ' leaked=' + got.leaked.length + (red ? '  first=' + got.leaked[0].slice(0, 56) : ''));
  if (!red) console.log('        SURVIVED -- the gate is blind here');
}
// CONTROL: untouched copies of the same tree must stay GREEN.
const control = path.join(scratch, 'control');
fs.mkdirSync(control);
for (const f of files) fs.copyFileSync(f, path.join(control, path.basename(f)));
const ctrlBad = report(files.map((f) => scanFile(path.join(control, path.basename(f)))),
  'CONTROL (untouched copies)', control);
const ok = wrong === 0 && ctrlBad === 0;
console.log('\nNEG-ARM ' + (ok ? 'PASS' : 'FAIL') +
  ' -- ' + MUTANTS.length + ' mutant(s), ' + caught + ' caught, ' + wrong + ' wrong, ' +
  decorative + ' decorative, control leaked-files=' + ctrlBad);
fs.rmSync(scratch, { recursive: true, force: true });
console.log('scratch used and cleaned: ' + scratch + ' (TMPDIR honoured)');
// rc=1 BY DESIGN when the arm passes: the negative arm is SUPPOSED to find the
// leak, so "found it" is a non-zero exit. rc=0 means a mutant was NOT caught.
// rc=2 is a setup error: a decorative mutant could not be prepared at all.
process.exit(ok ? 1 : (decorative > 0 ? 2 : 0));
