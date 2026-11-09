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
const { normalizeContext, encodeContext, decodeContext, contextTokenIn } =
  require('./history-context-store');

/** `<repo>/history`, unless the operator overrode it. */
const ROOT = path.normalize(
  process.env.SOTTO_HISTORY_ROOT || path.join(__dirname, '..', '..', 'history'),
);

/**
 * HOW LONG THE TRANSCRIPT SURVIVES ON DISK -- the twin of `HISTORY_RETENTION_H`
 * in `app/webview/sotto_webview.py`. Six months (180 days): the owner asked on
 * 2026-11-09 for months-later recall, which supersedes the older 48 h window.
 * `SOTTO_HISTORY_RETENTION_H` overrides it for a probe or a shorter store.
 */
const RETENTION_H = Number(process.env.SOTTO_HISTORY_RETENTION_H) || 4320;
/** The hour stamp of the last prune, so a burst of appends lists one directory. */
let _prunedStamp = '';

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
/**
 * The producers this writer may stamp as `producer=` (2026-11-05). The twin of
 * `HISTORY_PRODUCERS` in `app/webview/sotto_webview.py`, and the same rule as
 * `ROUTE_SOURCES`: outside this list nothing is written.
 */
const PRODUCERS = ['redux', 'live'];

// THE `ctx1=` TOKEN CODEC LIVES IN `history-context-store.js` (one format, two
// hosts): bounded fields, WHATWG-identical percent-encoding and URL bytes, and
// the trimmed-overflow rule. This file owns the layout, merge and retention.

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
function provenance(meta, contextToken = '') {
  if (!meta || typeof meta !== 'object') return '';
  const route = String(meta.route || '').trim();
  if (!ROUTES.includes(route)) return '';
  // The token goes FIRST, before the free-text reason (D2): the reader can
  // then take the first candidate without parsing a reason.
  const parts = [];
  if (contextToken) parts.push(`ctx1=${contextToken}`);
  parts.push(`route=${route}`);
  // WHO closed the line (2026-11-05) — the twin of `HISTORY_PRODUCERS` in
  // `app/webview/sotto_webview.py`. Both writers must say the same thing, or a
  // line's provenance would depend on which one wrote it.
  const producer = String(meta.producer || '').trim();
  if (PRODUCERS.includes(producer)) parts.push(`producer=${producer}`);
  if (typeof meta.start === 'number' && Number.isFinite(meta.start)) {
    parts.push(`start=${meta.start.toFixed(2)}`);
  }
  // WHICH branch decided the route (M9). Written AFTER `start=` so every
  // existing `route=… start=…` reader (`history-route-oracle.js`,
  // `historico-vs-redux-probe.js`, `route-stamp-gate.js`) keeps its capture.
  const src = String(meta.routeSource || '').trim();
  if (ROUTE_SOURCES.includes(src)) parts.push(`src=${src}`);
  // A reason is free text; `ctx1=` belongs to the token vocabulary and an
  // unscrubbed reason could end the comment with a spoofed token (D2).
  const reason = String(meta.reason || '')
    .replace(/\bctx1=\S*/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (reason) parts.push(`reason=${reason}`);
  return ` <!-- ${parts.join(' ')} -->`;
}

function mergeKey(text) {
  return String(text == null ? '' : text).replace(/[\s.!?…,;:]+$/u, '');
}

/** The last non-empty line of an hour file, parsed for the merge decision. */
function lastLine(file) {
  let lines = [];
  try {
    lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  } catch {
    return null;
  }
  let raw = '';
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    if (lines[i].trim()) { raw = lines[i]; break; }
  }
  if (!raw) return null;
  const match = /^-\s+\[(\d{2}):(\d{2}):(\d{2})\]\s+(.*)$/.exec(raw);
  const body = (match ? match[4] : raw).replace(TAIL_RE, '').trim();
  const startMatch = /\bstart=(-?\d+(?:\.\d+)?)/.exec(raw);
  const context = contextTokenIn(raw);
  return {
    body,
    timeS: match ? Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]) : null,
    start: startMatch ? Number(startMatch[1]) : null,
    audio: String(context.audioSource || ''),
    context,
  };
}

/**
 * The Node twin of `history_merge` in `app/webview/sotto_webview.py`:
 * `'skip'`, `'replace'` or `'append'`. The identity rules are the SAME, and the
 * defect they fix is the same: a plain text equality check ran first and
 * swallowed a legitimate later identical utterance.
 */
function mergeDecision(last, body, nowS, start, audio, windowS = 3) {
  if (!last) return 'append';
  body = String(body == null ? '' : body);
  // The Python twin refuses an empty body BEFORE any identity test. Without
  // this the two hosts disagree on an empty line carrying a distinct `start`
  // (Python `skip`, Node `append` through the shrink branch) -- measured
  // 2026-11-09.
  if (!body.trim()) return 'skip';
  const prev = String(last.body || '');
  const hasStart = typeof last.start === 'number' && Number.isFinite(last.start);
  const newHasStart = typeof start === 'number' && Number.isFinite(start);
  const sameStart = hasStart && newHasStart && Math.abs(last.start - start) <= 0.05;
  const distinctStart = hasStart && newHasStart && Math.abs(last.start - start) > 0.05;
  const lastAudio = String(last.audio || '').trim();
  const newAudio = String(audio || '').trim();
  const audioDiffers = Boolean(lastAudio && newAudio && lastAudio !== newAudio);
  const gap = () => (nowS == null || last.timeS == null ? null : Math.abs(nowS - last.timeS));
  if (prev === body) {
    if (distinctStart) return 'append';
    if (audioDiffers && !sameStart) return 'append';
    if (!sameStart) {
      const g = gap();
      if (g != null && g > windowS) return 'append';
    }
    return 'skip';
  }
  if (!prev) return 'append';
  const grew = mergeKey(body).startsWith(mergeKey(prev))
    || mergeKey(prev).startsWith(mergeKey(body));
  const shrank = mergeKey(prev).startsWith(mergeKey(body))
    && !mergeKey(body).startsWith(mergeKey(prev));
  const g = gap();
  const sameLine = sameStart || (!hasStart && !newHasStart && g != null && g <= windowS);
  if (shrank && sameLine) return 'skip';
  if (sameStart && grew) return 'replace';
  if (!grew) return 'append';
  // A different segment identity is a different line even when its text starts
  // with the previous one (same class as the equality defect, 2026-11-09).
  if (distinctStart) return 'append';
  if (g == null) return 'append';
  return g <= windowS ? 'replace' : 'append';
}

/**
 * DELETE DAY FOLDERS OLDER THAN THE RETENTION WINDOW -- the twin of
 * `_history_prune` in `app/webview/sotto_webview.py`.
 *
 * The Node store had NO retention: `history/` grew one folder per day and
 * nothing ever removed one, so "six months" was a promise the panel kept and
 * the disk did not. Cheapest honest shape (the same one the shell chose): on
 * the FIRST append of each hour, list the day folders (a handful of names),
 * drop those whose date is older than the window, and remove a folder only when
 * it is empty afterwards. One `readdirSync` per hour is not a measurement
 * anyone can notice; a background sweeper would be a process to own.
 *
 * `force` skips the hour memo so an oracle can exercise it twice in one hour.
 */
function prune(force = false) {
  const partsNow = nowParts();
  const stamp = `${partsNow.date}T${partsNow.hour}`;
  if (!force && _prunedStamp === stamp) return;
  _prunedStamp = stamp;
  const cutoff = new Date(Date.now() - RETENTION_H * 3600 * 1000);
  const oldest = nowParts(cutoff).date;
  let days = [];
  try {
    days = fs.readdirSync(ROOT).filter((name) => DAY_RE.test(name)).sort();
  } catch {
    return;
  }
  let removed = 0;
  for (const day of days) {
    if (day >= oldest) continue;
    const folder = path.join(ROOT, day);
    try {
      for (const name of fs.readdirSync(folder).sort()) {
        if (!name.endsWith('.md')) continue;
        try {
          fs.unlinkSync(path.join(folder, name));
          removed += 1;
        } catch {
          // an hour file another writer holds is skipped, like the shell twin
        }
      }
      fs.rmdirSync(folder);
    } catch {
      // a folder still holding something else (or already gone) is left alone
    }
  }
  if (removed) {
    // One line per hour at most, and only when something was removed: the
    // prune is a guarantee, not a heartbeat in the log.
    console.error(`sotto: HISTORY_PRUNE removed=${removed} keep_h=${RETENTION_H} oldest=${oldest}`);
  }
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
  if (String((meta && meta.route) || '').trim() === 'provisional-draft') return null;
  prune();
  const now = new Date();
  const { date, hour, time } = nowParts(now);
  const file = path.join(ROOT, date, `${hour}.md`);
  const nowS = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
  const context = normalizeContext(meta && meta.context);
  const start = typeof (meta && meta.start) === 'number' && Number.isFinite(meta.start)
    ? meta.start : null;
  const action = mergeDecision(lastLine(file), body, nowS, start,
    String(context.audioSource || ''));
  const entry = { date, hour, time, text: body, path: file, action, context };
  if (action === 'skip') return entry;
  const line = `- [${time}] ${body}${provenance(meta, encodeContext(context))}\n`;
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (action === 'replace') {
      const rows = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter((row) => row.trim());
      rows.pop(); // the line being rewritten
      rows.push(line.trimEnd());
      fs.writeFileSync(file, `${rows.join('\n')}\n`, 'utf8');
    } else {
      fs.appendFileSync(file, line, 'utf8');
    }
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
        yield {
          date,
          hour,
          time: match[1],
          text: match[2].replace(TAIL_RE, '').trim(),
          path: file,
          // The compact context on THIS line; a pre-2026-11-09 line is `{}`.
          context: contextTokenIn(lines[j]),
        };
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
      const contextText = Object.values(entry.context || {}).join(' ').toLowerCase();
      if (entry.text.toLowerCase().includes(needle)
          || (contextText && contextText.includes(needle))) {
        hits.push(entry);
        if (hits.length >= want) break;
      }
    }
  }
  return { query, hits, root: ROOT };
}

/** Compact text export, oldest-first — the Node twin of `history_export`. */
function exportBody(format = 'txt', limit = 400) {
  const fmt = String(format == null ? 'txt' : format).trim().toLowerCase() === 'md' ? 'md' : 'txt';
  const want = Math.min(Math.max(1, Number(limit) || 400), 5000);
  const out = [];
  for (const entry of entries()) {
    out.push(entry);
    if (out.length >= want) break;
  }
  out.reverse();
  const lines = out.map((entry) => {
    const ctx = entry.context || {};
    const bits = [];
    if (ctx.viewingApp || ctx.viewingTitle) {
      const view = [ctx.viewingApp, ctx.viewingTitle ? `"${ctx.viewingTitle}"` : '']
        .filter(Boolean).join(' ');
      bits.push(`view=${view}`);
    }
    if (ctx.audioSource) bits.push(`audio=${ctx.audioSource}`);
    if (ctx.sourceApp) bits.push(`source=${ctx.sourceApp}`);
    if (ctx.viewingUrl) bits.push(`url=${ctx.viewingUrl}`);
    const label = bits.length ? ` · ${bits.join(' · ')}` : '';
    return `${fmt === 'md' ? '- ' : ''}[${entry.date} ${entry.time}] ${entry.text}${label}`;
  });
  return { format: fmt, text: lines.join('\n'), entries: lines.length, root: ROOT };
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

module.exports = {
  ROOT,
  RETENTION_H,
  append,
  tail,
  search,
  root,
  reveal,
  export: exportBody,
  normalizeContext,
  encodeContext,
  decodeContext,
  mergeDecision,
  prune,
};
