'use strict';

/**
 * Sotto — THE DAY/HOUR GALLERY: a time-range query and the bucketing under it.
 *
 * OWNER 2026-10-08, verbatim: *"na pesquisa dos transcript, tira o historico que
 * ja mostra sozinho. tem que ter apenas botoes pra navegar entre a 'galeria' de
 * dias/horas"*. Two things are being asked for, and they are different:
 *
 *   1. THE LIST MUST NOT POPULATE ITSELF. Opening the drawer used to append every
 *      entry `historyApi.tail()` returned, newest-first, so the owner scrolled a
 *      wall of lines to find an hour he already knew the name of. The gallery
 *      replaces the wall with NAVIGATION: the panel offers the days and the hours
 *      it actually holds, and a line is shown only after one is chosen.
 *   2. THE NAVIGATION IS BY TIME, not by text. The search box stays (it is a
 *      different question — "where did he say X"), but browsing is now a range
 *      (24 h, then 1 h) plus the buckets inside it.
 *
 * WHY THIS IS ITS OWN FILE, DOM-FREE, DUAL-EXPORTED. Exactly the reason
 * `history-source.js` and `caption-formulation.js` are: `panel.js` is DOM-bound and
 * cannot be executed outside a browser, so a claim about the BUCKETING (a
 * boundary hour lands in one bucket and not two; a day rolls over at local
 * midnight, not at UTC) could only ever be asserted by reading `panel.js`'s
 * source. Here an oracle `require`s THIS file and runs the real function. See
 * `_main/history-gallery-oracle.js`.
 *
 * THE ONE DECISION WORTH NAMING: an entry carries a DATE (`YYYY-MM-DD`) and a
 * TIME (`HH:MM:SS`) as SEPARATE strings — that is how `history-store.js` writes
 * them into `history/<day>/<hour>.md` — so a timestamp only exists once the two
 * are combined, and it must be combined in LOCAL time, because the folder name is
 * local. `new Date('2026-10-08T11:43:16')` is parsed as LOCAL by spec, but
 * `new Date('2026-10-08')` is parsed as UTC — which is why this file builds the
 * Date from its parts and never from a joined string. That bug is OBSERVABLE ON
 * THIS BOX and was measured: the box is `GMT-0300`, so the bare-date parse of
 * `2026-10-08` yields Wed Oct 07 21:00 local — the entry moves to the PREVIOUS
 * day's bucket, and the first three hours of every day go with it. The oracle's
 * `--neg-arm` injects exactly that parse and watches this file's arms go RED.
 */

/** The ranges, in the owner's order: 24 h first, then 1 h. */
const RANGES = [
  { id: '24h', label: '24 h', hours: 24 },
  { id: '1h', label: '1 h', hours: 1 },
];

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const TIME_RE = /^\d{2}:\d{2}(:\d{2})?$/;

function pad2(n) {
  return String(n).padStart(2, '0');
}

/** The entry's LOCAL timestamp as a `Date`, or `null` when it cannot be read.
 *
 * Built from PARTS on purpose — see the file docstring: joining the two strings
 * into one and handing that to `new Date` would make the parsing depend on the
 * shape (a bare date is UTC, a date+time is local), and a malformed entry would
 * silently become `Invalid Date` rather than `null`.
 */
function entryStamp(entry) {
  if (!entry || typeof entry !== 'object') return null;
  const date = String(entry.date == null ? '' : entry.date).trim();
  const time = String(entry.time == null ? '' : entry.time).trim();
  if (!DATE_RE.test(date) || !TIME_RE.test(time)) return null;
  const ymd = date.split('-').map(Number);
  const full = time.length === 5 ? `${time}:00` : time;
  const hms = full.split(':').map(Number);
  const dt = new Date(ymd[0], ymd[1] - 1, ymd[2], hms[0], hms[1], hms[2]);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

/** `YYYY-MM-DD` in LOCAL time, or `null`. The DAY bucket's key. */
function dayKey(entry) {
  const s = entryStamp(entry);
  if (!s) return null;
  return `${s.getFullYear()}-${pad2(s.getMonth() + 1)}-${pad2(s.getDate())}`;
}

/** `YYYY-MM-DD HH` in LOCAL time, or `null`. The HOUR bucket's key. */
function hourKey(entry) {
  const s = entryStamp(entry);
  if (!s) return null;
  return `${dayKey(entry)} ${pad2(s.getHours())}`;
}

/**
 * The gallery: newest day first, each with its own newest hour first.
 *
 * Entries whose stamp cannot be read are DROPPED and COUNTED (`skipped`) rather
 * than silently bucketed into "today" — an unreadable line is a fact about the
 * store, and a gallery that hides it would make the store look cleaner than it is.
 */
function buckets(entries) {
  const byDay = new Map();
  let skipped = 0;
  let total = 0;
  for (const entry of entries || []) {
    total += 1;
    const day = dayKey(entry);
    if (!day) { skipped += 1; continue; }
    const hour = hourKey(entry).slice(-2);
    let bucket = byDay.get(day);
    if (!bucket) {
      bucket = { day, count: 0, hours: new Map() };
      byDay.set(day, bucket);
    }
    bucket.count += 1;
    if (!bucket.hours.has(hour)) bucket.hours.set(hour, { day, hour, count: 0 });
    bucket.hours.get(hour).count += 1;
  }
  const days = [...byDay.values()]
    .sort((a, b) => (a.day < b.day ? 1 : -1))
    .map((d) => ({
      day: d.day,
      count: d.count,
      hours: [...d.hours.values()].sort((a, b) => (a.hour < b.hour ? 1 : -1)),
    }));
  return { days, total, skipped };
}

/** The range spec for an id, or the spec itself; `null` for an unknown id. */
function rangeOf(range) {
  if (range && typeof range === 'object') return range;
  const id = String(range == null ? '' : range).trim();
  return RANGES.find((r) => r.id === id) || null;
}

/**
 * True iff the entry falls inside the window of `hours` ENDING at `now`.
 *
 * A FUTURE entry (its stamp is after `now`) is refused: the window is "the last N
 * hours", and a line stamped in the future is a clock or store defect that must
 * not be presented as the most recent thing that happened.
 */
function inRange(entry, range, now) {
  const spec = rangeOf(range);
  if (!spec || spec.hours == null) return false;
  const stamp = entryStamp(entry);
  if (!stamp) return false;
  const at = now instanceof Date ? now : new Date();
  const age = at.getTime() - stamp.getTime();
  return age >= 0 && age <= spec.hours * 3600 * 1000;
}

/** The entries inside the range, newest first (the list the drawer paints). */
function select(entries, range, now) {
  const spec = rangeOf(range);
  const kept = (entries || []).filter((e) => inRange(e, spec, now));
  return kept.sort((a, b) => {
    const sa = entryStamp(a);
    const sb = entryStamp(b);
    if (!sa || !sb) return 0;
    return sb.getTime() - sa.getTime();
  });
}

/** The entries of ONE bucket (a day, or a day+hour), newest first. */
function pick(entries, day, hour) {
  const wantDay = String(day == null ? '' : day).trim();
  const wantHour = hour == null || hour === '' ? null : String(hour).trim();
  const kept = (entries || []).filter((e) => {
    if (dayKey(e) !== wantDay) return false;
    if (wantHour == null) return true;
    return hourKey(e).slice(-2) === wantHour;
  });
  return kept.sort((a, b) => {
    const sa = entryStamp(a);
    const sb = entryStamp(b);
    if (!sa || !sb) return 0;
    return sb.getTime() - sa.getTime();
  });
}

const SottoHistoryGallery = {
  RANGES,
  entryStamp,
  dayKey,
  hourKey,
  buckets,
  rangeOf,
  inRange,
  select,
  pick,
};

// Both surfaces, because this file is BOTH a `<script>` in the panel and a
// `require` in the oracle — the same dual export `history-source.js` carries, and
// for the same reason: exporting only under CommonJS left the renderer with
// nothing.
if (typeof module !== 'undefined' && module.exports) module.exports = SottoHistoryGallery;
if (typeof window !== 'undefined') window.SottoHistoryGallery = SottoHistoryGallery;
