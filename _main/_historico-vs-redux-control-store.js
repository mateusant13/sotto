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
 */
const ROUTE_SOURCES = ['worker-stamped', 'panel-deadline', 'fallback'];

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

function search(query, limit = 200) {
  const needle = String(query == null ? '' : query).trim().toLowerCase();
  const want = Math.max(1, Number(limit) || 200);
  const hits = [];
  if (needle) {
    for (const entry of entries()) {
      if (entry.text.toLowerCase().includes(needle)) {
        hits.push(entry);
        if (hits.length >= want) break;
      }
    }
  }
  return { query, hits, root: ROOT };
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
