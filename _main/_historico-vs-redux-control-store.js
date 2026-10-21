'use strict';

/**
 * Sotto — the transcript history store, for the Electron arm.
 *
 * This is the Node twin of the store in `app/webview/sotto_webview.py`
 * (`SottoShell.history_*`). Both write the SAME layout, so the panel is one
 * artefact with two hosts and the on-disk data is portable between them:
 *
 *   <root>/<YYYY-MM-DD>/<HH>.md      one 24 h folder, one file per hour
 *   - [HH:MM:SS] the caption text    one line per committed caption
 *
 * The root is the repo's own `history/` (H:/sotto/history) unless
 * SOTTO_HISTORY_ROOT overrides it. The panel never learns this convention: it
 * is handed the entry, path included, so the layout lives in exactly two
 * places — here and there — and the two must agree.
 *
 * No dependency: `node:fs` and `node:child_process` only, both already loaded
 * by the shell. There is no index and no database — a search reads the hour
 * files, which is bounded by construction (24 files a day) and is why this is
 * the cheap option the brief asked for.
 */

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

/** `<repo>/history`, unless the operator overrode it. */
const ROOT = path.normalize(
  process.env.SOTTO_HISTORY_ROOT || path.join(__dirname, '..', '..', 'history'),
);

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const LINE_RE = /^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$/;
/**
 * The provenance the WRITER stamps on the end of a line (M8). It is an HTML
 * comment, so a Markdown reader shows the sentence and nothing else, and every
 * reader of the FILE strips it before treating the rest as text.
 */
const TAIL_RE = /\s*<!--.*?-->\s*$/;
/** The routes `provenance` is allowed to write: outside this, nothing is written. */
const ROUTES = ['final', 'provisional-draft'];
/**
 * The route SOURCES `provenance` may write as `src=`: WHICH branch decided the
 * route. `'fallback'` is the one the de-landing produced SILENTLY — a line that
 * reached the transcript ONLY because `caption-formulation.js routeFor`'s
 * else-half manufactured it when the worker stamped no route at all (P1
 * `4fb5b25380cbc8269977e22e`; see `_main/silent-fallback-probe.js`). Outside
 * this list nothing is written: an uninterpretable marker is worse than none.
 *
 * `'worker-stamped-producer'` is the SAME route decided by a DIFFERENT fact:
 * `caption-formulation.js routeSourceFor` returns it for a line that DECLARES
 * a producer while no worker `final` vote decided the route. It was declared
 * there (`:501`) and missing here until 2026-10-11, so such a line would have
 * been written with no `src=` marker at all — the provenance thinner than the
 * decision that produced it. (`panel.js recordHistory`'s `route !== 'final'`
 * guard is what kept it latent: a producer-stamped line with no worker vote is
 * usually not a `final` route.)
 */
const ROUTE_SOURCES = ['worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback'];

function pad2(n) {
  return String(n).padStart(2, '0');
}

function nowParts(date = new Date()) {
  return {
    date: `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`,
    hour: pad2(date.getHours()),
    time: `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`,
  };
}

function pathFor(date) {
  const parts = nowParts(date);
  return path.join(ROOT, parts.date, `${parts.hour}.md`);
}

/**
 * The `<!-- route=… start=… reason=… -->` suffix for one line (M8) — the Node
 * twin of `_history_provenance` in app/webview/sotto_webview.py, so both arms
 * write the same shape.
 *
 * WHY IT EXISTS: `formulate()` appends terminal punctuation to every line the
 * renderer commits, so a fragment the panel abandoned after 1500 ms and a
 * sentence the worker actually closed were byte-identical here. `start` is the
 * worker's own line identity (`worker/sotto_worker.py:_event`), and `reason` is
 * the rule that fired at the instant of the write.
 *
 * It goes ON the line and NOT into `entry.text`: the feed and the search show
 * the sentence, the file carries the provenance.
 */
function provenance(meta) {
  if (!meta || typeof meta !== 'object') return '';
  const route = String(meta.route || '').trim();
  if (!ROUTES.includes(route)) return '';
  const parts = [`route=${route}`];
  if (typeof meta.start === 'number' && Number.isFinite(meta.start)) {
    parts.push(`start=${meta.start.toFixed(2)}`);
  }
  // WHICH branch decided the route (M9). Written AFTER `start=` so every
  // existing `route=… start=…` reader (`history-route-oracle.js`,
  // `historico-vs-redux-probe.js`, `route-stamp-gate.js`) keeps its capture.
  const src = String(meta.routeSource || '').trim();
  if (ROUTE_SOURCES.includes(src)) parts.push(`src=${src}`);
  const reason = String(meta.reason || '').replace(/\s+/g, ' ').trim();
  if (reason) parts.push(`reason=${reason}`);
  return ` <!-- ${parts.join(' ')} -->`;
}

/** One committed caption → one line in the hour file. Returns the entry. */
function append(text, meta) {
  const body = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
  if (!body) return null;
  // HISTORICO-VS-REDUX GUARD — OWNER 2026-10-06: the transcript carries ONLY a
  // line the WORKER closed (`route=final`). The panel already declines a
  // `provisional-draft` (panel.js `recordHistory`); this is the same invariant
  // at the store, so no other caller can put the LIVE caption in the
  // transcript. See docs/audit/historico-vs-redux.md.

  const now = new Date();
  const { date, hour, time } = nowParts(now);
  const file = path.join(ROOT, date, `${hour}.md`);
  const entry = { date, hour, time, text: body, path: file };
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.appendFileSync(file, `- [${time}] ${body}${provenance(meta)}\n`, 'utf8');
  } catch (err) {
    console.error(`sotto: HISTORY_APPEND_FAILED path=${file} error=${err && err.message}`);
    return null;
  }
  return entry;
}

/** Every hour file under the root, OLDEST first: [{date, hour, path}]. */
function files() {
  let days = [];
  try {
    days = fs
      .readdirSync(ROOT)
      .filter((name) => DAY_RE.test(name))
      .sort();
  } catch {
    return [];
  }
  const out = [];
  for (const day of days) {
    const folder = path.join(ROOT, day);
    let hours = [];
    try {
      hours = fs.readdirSync(folder).filter((name) => name.endsWith('.md')).sort();
    } catch {
      continue;
    }
    for (const name of hours) out.push({ date: day, hour: name.slice(0, -3), path: path.join(folder, name) });
  }
  return out;
}

function read(file) {
  try {
    return fs.readFileSync(file, 'utf8').split(/\r?\n/);
  } catch (err) {
    console.error(`sotto: HISTORY_READ_FAILED path=${file} error=${err && err.message}`);
    return [];
  }
}

/** NEWEST-first entry stream: reverse file order AND line order. */
function* entries() {
  const all = files();
  for (let i = all.length - 1; i >= 0; i -= 1) {
    const { date, hour, path: file } = all[i];
    const lines = read(file);
    for (let j = lines.length - 1; j >= 0; j -= 1) {
      const match = LINE_RE.exec(lines[j]);
      if (match) {
        // The provenance comment is the FILE's, not the feed's: strip it so
        // search and the feed still see the sentence (M8 — see `provenance`).
        yield { date, hour, time: match[1], text: match[2].replace(TAIL_RE, '').trim(), path: file };
      }
    }
  }
}

function tail(limit = 400) {
  const want = Math.max(1, Number(limit) || 400);
  const out = [];
  for (const entry of entries()) {
    out.push(entry);
    if (out.length >= want) break;
  }
  out.reverse(); // oldest-first, for the feed
  return { entries: out, root: ROOT };
}

// ═══════════════════════════════════════════════════════════════════════════
// SEARCH — the JS twin of `history_search` in app/webview/sotto_webview.py.
//
// THIS FILE IS NOT ON THE SHIPPED PAGE. Measured 2026-10-11: `panel.html` loads
// ELEVEN scripts and this is not one of them; the live path is
// `panel.js:2842 runSearch()` -> `history-search` -> the Python twin. Only the
// oracles read this file (`historico-vs-redux-probe.js`, `history-route-oracle.js`,
// `live-vs-history-source-oracle.js`, `history-producer-gate.js`,
// `canonical-producer-oracle.py`).
//
// IT IS STILL FIXED, AND THE REASON IS THE REASON THE PYTHON TWIN WAS: an oracle
// that asserts on the live search and another that asserts on this one would
// disagree, and whichever one runs second looks broken. Two implementations of one
// contract are only worth having if they agree by construction. The three layers,
// the per-word edit budget, the all-words rule and the per-layer caps below are the
// same decisions, with the same numbers, as the Python side — `search-oracle.py`
// is the gate on the Python half and reads it out of the shell by `ast`.
// ═══════════════════════════════════════════════════════════════════════════

const FUZZ_RATIO = 0.34;
const FUZZY_MIN_WORD = 4;
const MAX_EDITS = 2;
const LAYER_CAPS = [1.0, 0.25, 0.05];
const LAYER_MIN = [1, 8, 4];
const LAYER_NAME = ['literal', 'phonetic', 'fuzzy'];

const SOUNDEX = (() => {
  const map = {};
  'bfpv'.split('').forEach((c) => { map[c] = '1'; });
  'cgjkqsxz'.split('').forEach((c) => { map[c] = '2'; });
  'dt'.split('').forEach((c) => { map[c] = '3'; });
  'l'.split('').forEach((c) => { map[c] = '4'; });
  'mn'.split('').forEach((c) => { map[c] = '5'; });
  'r'.split('').forEach((c) => { map[c] = '6'; });
  return map;
})();

/** Lowercase and strip diacritics: `Maçã`/`MACA`/`maçá` all fold to `maca`. */
function fold(text) {
  return String(text == null ? '' : text)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

/** A 4-character sound key, or '' when the word carries no letters. */
function soundex(word) {
  const letters = fold(word).replace(/[^a-z]/g, '');
  if (!letters) return '';
  let previous = SOUNDEX[letters[0]] || '';
  let codes = '';
  for (const ch of letters.slice(1)) {
    const code = SOUNDEX[ch] || '';
    if (code && code !== previous) codes += code;
    if (ch !== 'h' && ch !== 'w') previous = code;
  }
  return (letters[0].toUpperCase() + codes + '000').slice(0, 4);
}

/** Edit budget for `word`: ceil(ratio x len), capped, and 0 for short words. */
function editBudget(word) {
  if (word.length < FUZZY_MIN_WORD) return 0;
  return Math.min(MAX_EDITS, Math.ceil(FUZZ_RATIO * word.length));
}

/** Edit distance, or null once it is known to exceed `cap`. */
function boundedLevenshtein(a, b, cap) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > cap) return null;
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current.push(Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost));
    }
    // The early exit reads the row MINIMUM, not its label: the Python twin had
    // `row_min = i` and gave up on the third row, killing the layer on long words.
    if (Math.min.apply(null, current) > cap) return null;
    previous = current;
  }
  return previous[previous.length - 1] <= cap ? previous[previous.length - 1] : null;
}

/** 0 literal, 1 phonetic, 2 fuzzy, -1 no match. All-words after layer 0. */
function matchRank(text, foldedQuery, queryWords) {
  const foldedText = fold(text);
  if (!foldedQuery) return -1;
  if (foldedText.indexOf(foldedQuery) !== -1) return 0;
  const words = foldedText.split(/\s+/).filter(Boolean);
  if (!words.length) return -1;
  const entryKeys = new Set(words.map(soundex));
  if (queryWords.every((w) => soundex(w) && entryKeys.has(soundex(w)))) return 1;
  for (const qw of queryWords) {
    const budget = editBudget(qw);
    if (budget <= 0) {
      if (words.indexOf(qw) === -1) return -1;
      continue;
    }
    if (!words.some((w) => boundedLevenshtein(qw, w, budget) !== null)) return -1;
  }
  return 2;
}

function search(query, limit = 200) {
  const foldedQuery = fold(query).trim();
  const queryWords = foldedQuery ? foldedQuery.split(/\s+/) : [];
  const want = Math.max(1, Number(limit) || 200);
  const caps = LAYER_CAPS.map((frac, i) => Math.max(LAYER_MIN[i], Math.floor(want * frac)));
  const buckets = [[], [], []];
  if (queryWords.length) {
    for (const entry of entries()) {
      const rank = matchRank(entry.text, foldedQuery, queryWords);
      if (rank < 0) continue;
      if (buckets[rank].length < caps[rank]) {
        buckets[rank].push(Object.assign({}, entry, { match: LAYER_NAME[rank] }));
      }
      if (buckets.every((b, i) => b.length >= caps[i])) break;
    }
  }
  return { query, hits: buckets[0].concat(buckets[1], buckets[2]), root: ROOT };
}

function root() {
  return { root: ROOT };
}

/**
 * Open the OS file manager at the entry's FILE, or at the root.
 *
 * `explorer /select,"<file>"` for a file, `explorer "<dir>"` for a folder.
 * `windowsHide: true` and `detached: true` so no console window is created and
 * the shell does not wait on it — a helper that flashes a console is the exact
 * defect this house refuses. A path outside the root is REFUSED.
 */
function reveal(targetPath) {
  const raw = String(targetPath == null ? '' : targetPath).trim().replace(/^"|"$/g, '');
  let target;
  if (raw) {
    target = path.resolve(raw);
    const rootResolved = path.resolve(ROOT);
    const within =
      target === rootResolved ||
      target.toLowerCase().startsWith(rootResolved.toLowerCase() + path.sep);
    if (!within) {
      console.error(`sotto: REVEAL_REFUSED path=${raw} reason=outside-history-root`);
      return false;
    }
  } else {
    target = path.resolve(ROOT);
  }
  if (!fs.existsSync(target)) {
    console.error(`sotto: REVEAL_MISSING path=${target}`);
    return false;
  }
  const isFile = fs.statSync(target).isFile();
  const args = isFile ? [`/select,${target}`] : [target];
  try {
    const child = spawn('explorer', args, { detached: true, stdio: 'ignore', windowsHide: true });
    child.unref();
  } catch (err) {
    console.error(`sotto: REVEAL_FAILED path=${target} error=${err && err.message}`);
    return false;
  }
  return true;
}

module.exports = { ROOT, append, tail, search, root, reveal };
