#!/usr/bin/env node
'use strict';

/**
 * LIBRARY for the theme structural assertion. Both arms use THIS file:
 * `assert-themes.js` runs it over the real five files and prints the verdict;
 * `assert-themes-neg.js` runs it over mutant copies and requires RED.
 *
 * The three claims, checked with a tokenizer (comments and strings skipped),
 * never with a grep:
 *
 *   1. EVERY selector — every top-level selector, including each member of a
 *      comma-separated list — is scoped to `:root[data-theme='theme-N']`, and N
 *      is the file's OWN number. A selector scoped to another theme is a
 *      collision; an unscoped selector leaks into all five at once.
 *   2. NO `@import`, no `url(...)`, no `http(s)://`. The panel's CSP is
 *      `default-src 'none'; style-src 'self'`, and the panel runs on `file://`.
 *   3. the `var(--x)` tokens a file CONSUMES are declared in that same file, so
 *      a missing token cannot silently inherit from another theme.
 */

const fs = require('fs');
const path = require('path');

const DEFAULT_DIR = path.join(__dirname, '..', '..', 'app', 'panel', 'themes');

/** Strip comments and strings so the scanner only ever sees real CSS. */
function clean(text) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('/*', i)) {
      const j = text.indexOf('*/', i + 2);
      i = j < 0 ? text.length : j + 2;
      continue;
    }
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      let j = i + 1;
      while (j < text.length && text[j] !== ch) {
        if (text[j] === '\\') j += 1;
        j += 1;
      }
      out += text.slice(i, j + 1);
      i = j + 1;
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

/** Every selector of every rule, at every nesting depth. */
function selectors(text) {
  const found = [];
  let depth = 0;
  let prelude = '';
  for (const ch of text) {
    if (ch === '{') {
      const sel = prelude.trim();
      if (sel && !sel.startsWith('@')) {
        sel.split(',').forEach((one) => {
          const t = one.trim().replace(/\s+/g, ' ');
          if (t) found.push(t);
        });
      }
      depth += 1;
      prelude = '';
      continue;
    }
    if (ch === '}') {
      depth -= 1;
      prelude = '';
      continue;
    }
    if (depth < 2) prelude += ch;
  }
  return found;
}

function analyse(dir, files) {
  const report = [];
  for (const file of files) {
    const n = file.match(/theme-(\d)/)[1];
    const raw = fs.readFileSync(path.join(dir, file), 'utf8');
    const body = clean(raw);
    const sels = selectors(body);

    const unscoped = sels.filter((s) => !s.startsWith(':root[data-theme='));
    const foreign = sels
      .filter((s) => s.startsWith(':root[data-theme='))
      .filter((s) => s.slice(0, s.indexOf(']') + 1) !== `:root[data-theme='theme-${n}']`);

    const atImport = /@import/i.test(body);
    const urlFn = /url\s*\(/i.test(body);
    const remote = /(https?:)?\/\//i.test(body);

    const used = new Set([...body.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)].map((m) => m[1]));
    const declared = new Set([...body.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1]));
    const undeclared = [...used].filter((v) => !declared.has(v));

    const problems = [];
    if (unscoped.length) problems.push(`${unscoped.length} unscoped selector(s): ${unscoped.slice(0, 3).join(' | ')}`);
    if (foreign.length) problems.push(`${foreign.length} selector(s) scoped to ANOTHER theme: ${foreign.slice(0, 2).join(' | ')}`);
    if (atImport) problems.push('@import present');
    if (urlFn) problems.push('url() present');
    if (remote) problems.push('remote URL present');
    if (undeclared.length) problems.push(`undeclared token(s): ${undeclared.join(', ')}`);

    report.push({
      file,
      selectors: sels.length,
      scoped: sels.length - unscoped.length,
      foreign: foreign.length,
      atImport,
      urlFn,
      remote,
      tokensUsed: used.size,
      tokensUndeclared: undeclared,
      verdict: problems.length ? 'RED' : 'GREEN',
      problems,
    });
  }
  return report;
}

module.exports = { analyse, clean, selectors, DEFAULT_DIR };
