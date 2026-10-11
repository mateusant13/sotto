#!/usr/bin/env node
'use strict';

/**
 * THEME-SCOPE ORACLE -- does the theme contract hold PER MEMBER of a selector
 * list, and does the instrument SAY NO when it does not?
 *
 * WHAT IT CLAIMS, and why it is not a second copy of the gate: the gate asks
 * "is every selector scoped?". This oracle asks the question the 2026-10-11
 * defect actually turned on -- whether THE SCOPE IS APPLIED PER MEMBER OF A
 * SELECTOR LIST or only once per SOURCE LINE. The old emit() prefixed the LINE,
 * so the group the templates write as
 *
 *     {S} .panel__header, {S} .panel__header *, {S} .status, {S} .status *,
 *     {S} .chrome, {S} .chrome *
 *
 * came out with ONE scope and five bare members, which then leaked into every
 * other theme's document (measured 2026-10-11: 4 unscoped selectors in each of
 * the five generated files). So the oracle checks:
 *
 *   A. every member of every selector list carries THIS FILE'S OWN scope;
 *   B. the six selectors that used to leak are still ONE rule of SIX members,
 *      in order -- the fix re-scopes the list, it does not fragment it into six
 *      rules, and a fragmented list is a different cascade;
 *   C. the pre-fix emission SHAPE is absent from every prelude: the old
 *      generator separated members with a comma and SPACES, the fix separates
 *      them with a comma and a LINE BREAK, so 'comma + spaces + a selector'
 *      inside a prelude is proof the defect is back even if a count still
 *      looked right;
 *   T. every var(--x) a file CONSUMES is DECLARED in that same file (the token
 *      half of the same defect).
 *
 * IN-PROCESS, NO LAUNCH, NO WRITES. The oracle is text arithmetic over the
 * shipped bytes; the negative arm mutates an IN-MEMORY copy, so the shipped
 * files are read-only to it and the run re-hashes them at the end to prove it.
 * Nothing is spawned: not the app, not the shell, not the worker, not python.
 *
 * Usage:
 *   node _main/theme-scope-oracle.js              pristine arm only
 *   node _main/theme-scope-oracle.js --neg-arm    pristine + mutants, BOTH colours
 *
 * rc: 0 = every arm behaved; 1 = the subject is RED or a mutant failed to go RED.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ARG_DIR = process.argv.indexOf('--dir');
const DIR = ARG_DIR > -1 ? process.argv[ARG_DIR + 1] : path.join(__dirname, '..', 'app', 'panel', 'themes');
const FILES = [1, 2, 3, 4, 5].map((n) => ({ n, file: 'theme-' + n + '.css' }));
const NEG_ARM = process.argv.includes('--neg-arm');

/** The six selectors the 2026-10-11 defect leaked, in the order the template writes them. */
const LEAKED = ['.panel__header', '.panel__header *', '.status', '.status *', '.chrome', '.chrome *'];

const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');

/** Comments out, everything else kept -- the same tokenizer the gate uses, so a
 *  token named in PROSE is never mistaken for a declaration. */
function stripComments(text) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('/*', i)) {
      const j = text.indexOf('*/', i + 2);
      i = j < 0 ? text.length : j + 2;
      continue;
    }
    out += text[i];
    i += 1;
  }
  return out;
}

/** Split on sep at depth 0 and outside quotes: ':is(a, b)' and '[x="a,b"]' stay whole. */
function splitTop(text, sep) {
  const parts = [];
  let cur = '';
  let depth = 0;
  let quote = null;
  for (const ch of text) {
    if (quote) { cur += ch; if (ch === quote) quote = null; continue; }
    if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
    if (ch === '(') depth += 1;
    else if (ch === ')') depth -= 1;
    if (ch === sep && depth === 0) { parts.push(cur); cur = ''; continue; }
    cur += ch;
  }
  parts.push(cur);
  return parts;
}

/** Every RULE at every nesting depth, with its members split. A keyframe step is not a rule. */
function rules(css) {
  const text = stripComments(css);
  const found = [];
  let depth = 0;
  let prelude = '';
  let keyframes = 0;
  for (const ch of text) {
    if (ch === '{') {
      const sel = prelude.trim();
      if (sel && !sel.startsWith('@')) {
        if (!keyframes) {
          found.push({
            raw: sel,
            members: splitTop(sel, ',').map((m) => m.trim().replace(/\s+/g, ' ')).filter(Boolean),
            depth,
          });
        }
      } else if (/^@[-\w]*keyframes/i.test(sel)) {
        keyframes = depth + 1;
      }
      depth += 1;
      prelude = '';
      continue;
    }
    if (ch === '}') {
      depth -= 1;
      if (keyframes && depth < keyframes) keyframes = 0;
      prelude = '';
      continue;
    }
    if (depth < 2) prelude += ch;
  }
  return found;
}

function tokens(css) {
  const text = stripComments(css);
  const used = new Set([...text.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)].map((m) => m[1]));
  const declared = new Set([...text.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1]));
  return { used: [...used].sort(), declared: [...declared].sort() };
}

/** C, the pre-fix emission SHAPE: inside a PRELUDE, a comma then spaces then a selector. */
function packedPrelude(rs) {
  return rs.filter((r) => /,[ \t]+[^\s]/.test(r.raw)).map((r) => r.raw.replace(/\s+/g, ' ').slice(0, 90));
}

/** Analyse ONE file's text. n is the theme number the file must be scoped to. */
function analyse(css, n) {
  const scope = ":root[data-theme='theme-" + n + "']";
  const reasons = [];
  const rs = rules(css);

  const all = rs.flatMap((r) => r.members);
  const unscoped = all.filter((m) => !m.startsWith(scope));
  const foreign = all.filter((m) => m.startsWith(':root[data-theme=') && !m.startsWith(scope));

  if (unscoped.length) reasons.push('A: ' + unscoped.length + ' member(s) NOT scoped to theme-' + n + ': ' + unscoped.slice(0, 4).join(' | '));
  if (foreign.length) reasons.push('A: ' + foreign.length + ' member(s) scoped to ANOTHER theme: ' + foreign.slice(0, 2).join(' | '));

  const defect = rs.filter((r) => r.members.some((m) => m.endsWith('.panel__header *')));
  let defectMembers = [];
  if (defect.length !== 1) {
    reasons.push('B: expected exactly ONE rule to carry the group that used to leak (.panel__header *), found ' + defect.length);
  } else {
    defectMembers = defect[0].members.map((m) => (m.startsWith(scope) ? m.slice(scope.length).trim() : m));
    if (defect[0].members.length !== LEAKED.length) {
      reasons.push('B: that group has ' + defect[0].members.length + ' members, not ' + LEAKED.length + ' -- it was fragmented or rebuilt');
    } else if (defectMembers.join(' | ') !== LEAKED.join(' | ')) {
      reasons.push('B: that group is no longer the six the defect leaked: ' + defectMembers.join(' | '));
    }
  }

  const packed = packedPrelude(rs);
  if (packed.length) reasons.push('C: ' + packed.length + ' prelude(s) PACK members onto one line (comma + spaces), the pre-fix emission shape: ' + packed.slice(0, 2).join(' || '));

  const tok = tokens(css);
  const undeclared = tok.used.filter((t) => !tok.declared.includes(t));
  if (undeclared.length) reasons.push('T: consumed and declared nowhere in this file: ' + undeclared.join(', '));

  return {
    verdict: reasons.length ? 'RED' : 'GREEN',
    reasons: reasons,
    members: all.length,
    membersScoped: all.length - unscoped.length,
    groups: rs.filter((r) => r.members.length > 1).length,
    defectMembers: defectMembers,
    tokensUsed: tok.used.length,
    undeclared: undeclared,
  };
}

function readAll() {
  const out = [];
  for (const f of FILES) {
    const p = path.join(DIR, f.file);
    const buf = fs.readFileSync(p);
    out.push({ n: f.n, file: f.file, text: buf.toString('utf8'), sha: sha256(buf) });
  }
  return out;
}

/* ----------------------------- THE MUTANTS ---------------------------------
 * Each takes the shipped TEXT and returns a mutated copy. The copy is a STRING:
 * nothing on disk is touched.
 */

/** The group the defect mangled, as it appears in the file, and its members. */
function defectGroup(text, n) {
  const scope = ":root[data-theme='theme-" + n + "']";
  const g = rules(text).filter((r) => r.members.some((m) => m.endsWith('.panel__header *')));
  if (g.length !== 1) return null;
  const NL = text.indexOf('\r\n') >= 0 ? '\r\n' : '\n';
  return { scope: scope, group: g[0], from: g[0].members.join(',' + NL), NL: NL };
}

/** Rebuild the group the way the pre-fix generator emitted it: only the FIRST
 *  member of each source LINE keeps the scope. Same members, same one rule. */
function revertScoping(text, n) {
  const d = defectGroup(text, n);
  if (!d) return { text: text, changed: 0 };
  const bare = d.group.members.map((m) => (m.startsWith(d.scope) ? m.slice(d.scope.length).trim() : m));
  const half = Math.ceil(bare.length / 2);
  const lines = [
    d.scope + ' ' + bare.slice(0, half).join(',  '),
    d.scope + ' ' + bare.slice(half).join(',  '),
  ];
  const idx = text.indexOf(d.from);
  if (idx < 0) return { text: text, changed: 0 };
  return { text: text.slice(0, idx) + lines.join(',' + d.NL) + text.slice(idx + d.from.length), changed: bare.length - 2 };
}

/** Re-scope every member of that group to ANOTHER theme. */
function foreignScope(text, n) {
  const d = defectGroup(text, n);
  if (!d) return { text: text, changed: 0 };
  const other = ":root[data-theme='theme-" + (n === 4 ? 5 : 4) + "']";
  const to = d.group.members.map((m) => other + m.slice(d.scope.length)).join(',' + d.NL);
  const idx = text.indexOf(d.from);
  if (idx < 0) return { text: text, changed: 0 };
  return { text: text.slice(0, idx) + to + text.slice(idx + d.from.length), changed: d.group.members.length };
}

/** Drop the appended token-resolution block (defect 2 restored). */
function revertTokens(text) {
  const at = text.indexOf('/* -- TOKENS THIS THEME CONSUMES AND DOES NOT OWN');
  if (at < 0) return { text: text, changed: 0 };
  return { text: text.slice(0, at), changed: text.slice(at).split('\n').filter(Boolean).length };
}

/** Drop ONE declaration line from the token block, leaving any other in place.
 *  The line must END IN A SEMICOLON: the block's own COMMENT also names both
 *  tokens in prose, and a mutant that deleted the prose would prove nothing. */
function dropDecl(text, token) {
  const re = new RegExp('^[ \\t]*' + token + ': [^\\r\\n]*;\\r?$', 'm');
  if (!re.test(text)) return { text: text, changed: 0 };
  return { text: text.replace(re, ''), changed: 1 };
}

/* --------------------------------- MAIN ----------------------------------- */

const shipped = readAll();
const before = shipped.map((s) => s.sha);

console.log('THEME-SCOPE ORACLE -- per-member scoping and token resolution');
console.log('dir: ' + DIR);
console.log('');

let pristineBad = 0;
let defectShown = null;
console.log('ARM 1  PRISTINE (the shipped bytes)');
for (const s of shipped) {
  const r = analyse(s.text, s.n);
  if (r.verdict !== 'GREEN') pristineBad += 1;
  console.log('  ' + r.verdict.padEnd(5) + ' ' + s.file.padEnd(14)
    + ' members=' + String(r.members).padStart(3)
    + ' scoped=' + String(r.membersScoped).padStart(3)
    + ' multi-member-groups=' + String(r.groups).padStart(2)
    + ' tokens=' + r.tokensUsed
    + ' undeclared=' + r.undeclared.length
    + ' sha256[0:16]=' + s.sha.slice(0, 16));
  r.reasons.forEach((x) => console.log('        ' + x));
}
defectShown = analyse(shipped[0].text, shipped[0].n).defectMembers;
console.log('  the group the defect leaked, as re-scoped by the fix (' + defectShown.length + ' members, ONE rule):');
defectShown.forEach((m) => console.log('    ' + m));

if (!NEG_ARM) {
  const pass = pristineBad === 0;
  console.log('');
  console.log(pass
    ? 'VERDICT PASS -- every member of every selector list is scoped to its own theme, the leaked group is intact, no prelude packs members onto one line, and every consumed token is declared.'
    : 'VERDICT FAIL -- ' + pristineBad + ' file(s) did not hold the contract.');
  process.exit(pass ? 0 : 1);
}

/* ---- ARM 2: every mutant must go RED, naming its OWN reason. --------------- */
const MUT = [
  { name: 'revert-scoping theme-1',         n: 1, file: 'theme-1.css', mutate: revertScoping, names: 'NOT scoped to theme-1' },
  { name: 'revert-scoping theme-5',         n: 5, file: 'theme-5.css', mutate: revertScoping, names: 'NOT scoped to theme-5' },
  { name: 'revert-token-block theme-3',     n: 3, file: 'theme-3.css', mutate: revertTokens,  names: '--font-serif' },
  { name: 'drop-only---font-serif theme-3', n: 3, file: 'theme-3.css', mutate: (t) => dropDecl(t, '--font-serif'), names: '--font-serif' },
  { name: 'drop-only---w-op theme-3',       n: 3, file: 'theme-3.css', mutate: (t) => dropDecl(t, '--w-op'),       names: '--w-op' },
  { name: 'foreign-scope theme-2',          n: 2, file: 'theme-2.css', mutate: foreignScope,  names: 'ANOTHER theme' },
];

console.log('');
console.log('ARM 2  MUTANTS (each is an IN-MEMORY copy; the shipped files are never written)');
let mutantsBad = 0;
for (const m of MUT) {
  const base = shipped.find((s) => s.file === m.file);
  const src = base.text;
  const out = m.mutate(src, m.n);
  const r = analyse(out.text, m.n);
  const named = r.reasons.some((x) => x.includes(m.names));
  const wentRed = r.verdict === 'RED' && named;
  if (!wentRed) mutantsBad += 1;
  const lineDelta = out.text === src ? 0 : Math.abs(out.text.split('\n').length - src.split('\n').length);
  console.log('  ' + (wentRed ? 'PASS' : 'FAIL') + '  ' + m.name.padEnd(32)
    + ' want=RED naming "' + m.names + '"'
    + '  got=' + r.verdict + (named ? '' : ' (wrong reason)')
    + '  touched~' + out.changed + ' lineDelta=' + lineDelta);
  if (!wentRed) r.reasons.forEach((x) => console.log('        ' + x));
}

const after = shipped.map((s) => sha256(fs.readFileSync(path.join(DIR, s.file))));
const untouched = before.every((h, i) => h === after[i]);
console.log('');
console.log('  shipped files unchanged by this run: ' + (untouched ? 'yes (all 5 sha256 identical before/after)' : 'NO -- A FILE MOVED'));

const pass = pristineBad === 0 && mutantsBad === 0 && untouched;
console.log('');
console.log(pass
  ? 'VERDICT PASS -- pristine GREEN and all ' + MUT.length + ' mutant(s) RED, each naming its own violation.'
  : 'VERDICT FAIL -- pristine failures=' + pristineBad + ', mutants that did not go RED=' + mutantsBad + (untouched ? '' : ', a shipped file was modified') + '.');
process.exit(pass ? 0 : 1);
