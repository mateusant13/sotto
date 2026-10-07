#!/usr/bin/env node
'use strict';

/**
 * STRUCTURAL ASSERTION for the five Sotto theme files.
 *
 * Five stylesheets load into ONE document and must not collide, so the claims
 * below are checked against the real generated files. The logic lives in
 * `theme-assert-lib.js` so `assert-themes-neg.js` can hold it to mutant copies.
 *
 * Usage:
 *   node _main/_design-lane/assert-themes.js
 *   node _main/_design-lane/assert-themes.js --dir <other dir>
 */

const path = require('path');
const lib = require('./theme-assert-lib');

const argDir = process.argv.indexOf('--dir');
const dir = argDir > -1 ? process.argv[argDir + 1] : lib.DEFAULT_DIR;
const files = [1, 2, 3, 4, 5].map((n) => `theme-${n}.css`);

console.log(`dir: ${path.resolve(dir)}`);
const report = lib.analyse(dir, files);

let failures = 0;
for (const r of report) {
  if (r.verdict === 'RED') failures += 1;
  console.log(
    `${r.verdict}  ${r.file}  selectors=${r.selectors} scoped=${r.scoped} ` +
    `foreign=${r.foreign} @import=${r.atImport} url()=${r.urlFn} remote=${r.remote} ` +
    `tokens=${r.tokensUsed} undeclared=${r.tokensUndeclared.length}`
  );
  r.problems.forEach((p) => console.log(`        ${p}`));
}

console.log(
  failures === 0
    ? 'VERDICT PASS — all five theme files are scoped to their own theme, load no remote content, and declare every token they use.'
    : `VERDICT FAIL — ${failures} file(s) violated the contract.`
);
process.exit(failures === 0 ? 0 : 1);
