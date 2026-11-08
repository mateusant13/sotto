'use strict';

/**
 * _panel-history-measure.js — what the TRANSCRIPT ROW really computes to.
 *
 * `_panel2-dom-probe.js` injects ONLY `panel.css`, so it measures the base sheet
 * and not the cascade a human sees. This script loads EVERY stylesheet
 * `panel.html` links, in document order, plus the per-theme file the switch
 * would append, and prints `getComputedStyle` for the transcript row and its
 * parts.
 *
 *   node _main/_panel-history-measure.js                     # every theme, AFTER
 *   node _main/_panel-history-measure.js --state=before      # same, pre-fix
 *   node _main/_panel-history-measure.js theme-1 pd-bcast
 *
 * `--state=before` removes the block between HISTORY-LEGIBILITY-BEGIN/END from
 * `panel-unified.css` before injecting it, so the before/after pair comes from
 * the same document and the same cascade order -- not from a remembered number.
 *
 * jsdom has no layout engine and no `var()`/`calc()` resolution: the raw
 * computed value is printed (`raw:`) and then resolved here from the document's
 * own custom properties (`resolved:`), so `calc(13.5px * var(--caption-scale))`
 * reads as `13.5px` at the default dial. `color-mix()` is left as a token
 * expression -- jsdom drops it, a browser does not -- which is stated, not
 * papered over.
 */

const fs = require('node:fs');
const path = require('node:path');

const REPO = path.join(__dirname, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const { JSDOM } = require('jsdom');

const STATE = (process.argv.find((a) => a.startsWith('--state=')) || '--state=after').slice(8);
const BASE_SHEETS = [
  'themes/fonts.css',
  'panel.css',
  'caption-float.css',
  'themes/theme-1.css',
  'themes/theme-2.css',
  'themes/theme-3.css',
  'themes/theme-4.css',
  'themes/theme-5.css',
  'themes/zipc-panels.css',
  'button-contract.css',
  'panel-unified.css',
];

const THEME_FILE = {};
for (const manifest of ['themes.js', 'panel-designs.js']) {
  const src = fs.readFileSync(path.join(PANEL, 'themes', manifest), 'utf8');
  for (const m of src.matchAll(/name:\s*'([^']+)'[\s\S]{0,200}?file:\s*'([^']+)'/g)) {
    THEME_FILE[m[1]] = m[2];
  }
}

function sheetText(file) {
  let css = fs.readFileSync(path.join(PANEL, file), 'utf8');
  if (STATE === 'before') {
    css = css.replace(/\/\* HISTORY-LEGIBILITY-BEGIN[\s\S]*?HISTORY-LEGIBILITY-END \*\//g, '');
  }
  return `/* ${file} */\n` + css;
}

function build(theme) {
  const html = fs.readFileSync(path.join(PANEL, 'panel.html'), 'utf8');
  const dom = new JSDOM(html, {
    url: new URL('file://' + path.join(PANEL, 'panel.html')).href,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const doc = window.document;
  for (const link of Array.from(doc.querySelectorAll('link[rel="stylesheet"]'))) link.remove();

  const files = BASE_SHEETS.slice();
  const extra = THEME_FILE[theme];
  if (extra && !files.includes(extra)) files.push(extra);

  const style = doc.createElement('style');
  style.textContent = files.map(sheetText).join('\n');
  doc.head.prepend(style);

  doc.documentElement.setAttribute('data-theme', theme);
  doc.body.setAttribute('data-surface', 'panel');
  const history = doc.getElementById('history');
  if (history) history.classList.remove('history--collapsed');

  const list = doc.getElementById('history-list');
  list.replaceChildren();
  const samples = [
    ['[00:12:03]', 'Então a gente vai ver o que acontece com o max, que é o dois, três, mas.'],
    ['[00:12:09]', 'Run to like max two max, three, but running max.'],
    ['[00:12:15]', 'A segunda linha é o mesmo texto numa frase mais longa, para ver a quebra e o ritmo vertical da lista.'],
  ];
  for (const [stamp, text] of samples) {
    const li = doc.createElement('li');
    li.className = 'hist';
    li.setAttribute('data-history-row', '1');
    const time = doc.createElement('span');
    time.className = 'hist__time';
    time.textContent = stamp;
    const body = doc.createElement('span');
    body.className = 'hist__text';
    body.textContent = text;
    const folder = doc.createElement('button');
    folder.type = 'button';
    folder.className = 'hist__folder';
    folder.setAttribute('aria-label', 'Show in folder');
    folder.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 4.2a1 1 0 0 1 1-1h3.1l1.3 1.4h5.6a1 1 0 0 1 1 1v6.2a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1z"/></svg>';
    li.append(time, body, folder);
    list.append(li);
  }
  return { window, doc };
}

// ── resolve `var()` and the simple `calc()` forms this cascade uses ─────────
function tokenMap(window, doc) {
  const css = Array.from(doc.querySelectorAll('style')).map((s) => s.textContent).join('\n');
  const names = new Set();
  for (const m of css.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) names.add(m[1]);
  const root = window.getComputedStyle(doc.documentElement);
  const map = {};
  for (const n of names) {
    const v = root.getPropertyValue(n).trim();
    if (v) map[n] = v;
  }
  return map;
}

function resolve(value, map, depth = 0) {
  if (!value || depth > 12) return value;
  let out = value;
  out = out.replace(/var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)/g,
    (whole, name, fallback) => {
      if (map[name] !== undefined) return map[name];
      return fallback !== undefined ? fallback.trim() : whole;
    });
  if (out !== value) return resolve(out, map, depth + 1);
  const calc = out.match(/^calc\((.+)\)$/);
  if (calc) {
    let expr = calc[1].trim();
    // only `Npx * N` / `Npx / N` is used by this cascade
    const mul = expr.match(/^(-?[\d.]+)px\s*([*/])\s*(-?[\d.]+)$/);
    if (mul) {
      const n = mul[2] === '*' ? Number(mul[1]) * Number(mul[3]) : Number(mul[1]) / Number(mul[3]);
      return `${Number(n.toFixed(3))}px`;
    }
  }
  return out;
}

const PROPS = {
  '.hist': ['font-family', 'font-size', 'line-height', 'grid-template-columns', 'gap', 'padding-top', 'padding-bottom', 'padding-left', 'margin-top', 'color'],
  '.hist__time': ['font-family', 'font-size', 'line-height', 'color', 'opacity', 'font-variant-numeric'],
  '.hist__text': ['font-family', 'font-size', 'line-height', 'color', 'overflow-wrap'],
  '.hist__folder': ['width', 'height', 'padding'],
};

function report(theme) {
  const { window, doc } = build(theme);
  const map = tokenMap(window, doc);
  console.log(`\n## ${theme}  (${THEME_FILE[theme] || 'base only'})  state=${STATE}`);
  for (const [sel, props] of Object.entries(PROPS)) {
    const el = doc.querySelector(sel);
    const cs = window.getComputedStyle(el);
    const raw = props.map((p) => `${p}=${cs.getPropertyValue(p)}`).join(' | ');
    const res = props.map((p) => `${p}=${resolve(cs.getPropertyValue(p), map)}`).join(' | ');
    console.log(`  ${sel}`);
    console.log(`    raw:      ${raw}`);
    console.log(`    resolved: ${res}`);
  }
  const list = doc.getElementById('history-list');
  const listCs = window.getComputedStyle(list);
  console.log('  .history__list');
  console.log(`    raw:      display=${listCs.getPropertyValue('display')} | gap=${listCs.getPropertyValue('gap')} | padding-top=${listCs.getPropertyValue('padding-top')}`);
  const second = doc.querySelectorAll('.hist')[1];
  const secondCs = second ? window.getComputedStyle(second) : null;
  console.log(`    separation between rows (2nd .hist margin-top): ${secondCs ? secondCs.getPropertyValue('margin-top') : 'n/a'}`);
  const root = window.getComputedStyle(doc.documentElement);
  console.log(`  tokens: --caption-scale=${root.getPropertyValue('--caption-scale') || '(unset)'} --font=${resolve(root.getPropertyValue('--font'), map)} --size-small=${resolve(root.getPropertyValue('--size-small'), map) || '(unset)'}`);
}

const requested = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const themes = requested.length ? requested : ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5', 'cine-midnight-rain', 'pd-bcast'];
for (const t of themes) {
  try { report(t); } catch (err) { console.log(`\n## ${t}\n  ERROR ${err.stack}`); }
}
