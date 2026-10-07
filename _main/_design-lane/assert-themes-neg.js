#!/usr/bin/env node
'use strict';

/**
 * NEGATIVE CONTROL for the theme structural assertion.
 *
 * `assert-themes.js` prints GREEN. A gate that has never said no is not
 * evidence, so this arm builds MUTANT COPIES of the real theme files in a temp
 * directory — each with ONE deliberate violation — and requires the assertion to
 * go RED and to NAME THE RIGHT REASON. The five real files are never written to.
 *
 * Usage: node _main/_design-lane/assert-themes-neg.js
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const lib = require('./theme-assert-lib');

const SRC = lib.DEFAULT_DIR;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-themes-neg-'));
const runner = path.join(__dirname, 'assert-themes.js');
const FILES = ['theme-1.css', 'theme-2.css', 'theme-3.css', 'theme-4.css', 'theme-5.css'];

const MUTANTS = [
  {
    name: 'unscoped-selector',
    file: 'theme-1.css',
    apply: (t) => t + '\n.caption--provisional {\n  color: red;\n}\n',
    expect: 'unscoped selector',
  },
  {
    name: 'foreign-theme-scope',
    file: 'theme-2.css',
    apply: (t) => t + "\n:root[data-theme='theme-4'] .caption__text {\n  color: red;\n}\n",
    expect: 'ANOTHER theme',
  },
  {
    name: 'at-import',
    file: 'theme-3.css',
    apply: (t) => t + '\n@import "theme-1.css";\n',
    expect: '@import',
  },
  {
    name: 'remote-url',
    file: 'theme-4.css',
    apply: (t) => t + "\n:root[data-theme='theme-4'] .panel {\n  background-image: url(https://example.invalid/x.png);\n}\n",
    expect: 'url()',
  },
  {
    name: 'undeclared-token',
    file: 'theme-5.css',
    apply: (t) => t.replace(/^\s*--text-muted:.*$/m, ''),
    expect: 'undeclared token',
  },
];

function copyAll(dir) {
  for (const f of FILES) fs.copyFileSync(path.join(SRC, f), path.join(dir, f));
}

function run(dir) {
  try {
    const out = execFileSync(process.execPath, [runner, '--dir', dir], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
    });
    return { code: 0, out };
  } catch (err) {
    return { code: err.status === undefined ? -1 : err.status, out: `${err.stdout || ''}${err.stderr || ''}` };
  }
}

const results = [];
let failed = 0;

// ARM 0 — the control: an untouched copy stays GREEN.
const pristine = fs.mkdtempSync(path.join(tmp, 'pristine-'));
copyAll(pristine);
const p = run(pristine);
const arm0 = p.code === 0 && /VERDICT PASS/.test(p.out);
if (!arm0) failed += 1;
results.push(['pristine-copy', 'GREEN', arm0 ? 'GREEN' : 'RED', arm0 ? 'ok' : p.out.trim().split('\n').slice(-1)[0]]);

// ARMS 1..N — every mutant must go RED for its own reason.
for (const m of MUTANTS) {
  const dir = fs.mkdtempSync(path.join(tmp, `mut-${m.name}-`));
  copyAll(dir);
  const target = path.join(dir, m.file);
  fs.writeFileSync(target, m.apply(fs.readFileSync(target, 'utf8')));
  const r = run(dir);
  const named = r.out.includes(m.expect) && r.out.includes(m.file);
  const held = r.code !== 0 && named;
  if (!held) failed += 1;
  results.push([
    m.name,
    `RED naming "${m.expect}" in ${m.file}`,
    held ? 'RED' : (r.code === 0 ? 'GREEN (missed)' : 'RED, wrong reason'),
    held ? 'ok' : r.out.trim().split('\n').filter((l) => l.trim()).slice(-2).join(' | '),
  ]);
}

console.log('NEGATIVE CONTROL for the theme structural assertion\n');
for (const [name, want, got, note] of results) {
  const ok = got === 'GREEN' && name === 'pristine-copy' ? true : got === 'RED';
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(21)} want=${want.padEnd(40)} got=${got.padEnd(18)} ${note}`);
}
console.log('');
console.log(failed === 0
  ? `NEG-ARM VERDICT PASS — the untouched copy stayed GREEN and all ${MUTANTS.length} mutants went RED, each naming its own violation and file.`
  : `NEG-ARM VERDICT FAIL — ${failed} arm(s) did not behave.`);

fs.rmSync(tmp, { recursive: true, force: true });
process.exit(failed === 0 ? 0 : 1);
