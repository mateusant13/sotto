#!/usr/bin/env node
'use strict';

/**
 * Oracle for `app/panel/history-gallery.js` — the day/hour gallery.
 *
 * WHY THIS EXISTS: the owner asked for browsing by TIME (*"apenas botoes pra
 * navegar entre a 'galeria' de dias/horas"*), and every claim that follows from
 * that is a claim about a FUNCTION — which hour a line lands in, where a day
 * rolls over, what "the last 24 h" excludes. Those are executable, so they are
 * executed against the SHIPPED file rather than regexed out of `panel.js`.
 *
 * THE NEGATIVE ARM IS THE POINT. Arm 1 asserts that a stamp is built in LOCAL
 * time; the trap it exists for is that `new Date('2026-10-08')` is parsed as UTC
 * while `new Date('2026-10-08T00:30:00')` is parsed as LOCAL. `--neg-arm`
 * re-installs exactly that UTC-shaped `entryStamp` and requires arm 1 to go RED
 * while the others stay green. An oracle that cannot say NO is worth nothing.
 *
 * Usage: node _main/history-gallery-oracle.js [--neg-arm]
 */

const path = require('node:path');

const SRC = path.join(__dirname, '..', 'app', 'panel', 'history-gallery.js');
const gallery = require(SRC);

const NEG = process.argv.includes('--neg-arm');

const results = [];
function arm(name, fn) {
  try {
    const problems = fn() || [];
    results.push({ name, ok: problems.length === 0, problems });
  } catch (err) {
    results.push({ name, ok: false, problems: [`threw: ${err && err.message}`] });
  }
}
function eq(got, want, what) {
  const g = JSON.stringify(got);
  const w = JSON.stringify(want);
  return g === w ? null : `${what}: got ${g}, want ${w}`;
}

// ── THE NEGATIVE ARM's subject: the UTC-shaped stamp, and ONLY it ────────────
// The defect is the BARE-DATE parse. `new Date('2026-10-08')` is UTC midnight
// while `new Date('2026-10-08T00:30:00')` is LOCAL, so an implementation that
// reaches for the date alone puts every line of a day at 21:00 of the PREVIOUS
// day on this box (measured: GMT-0300, `offsetMinutes = 180`).
//
// FIRST ATTEMPT WAS A NO-OP, and the reason is worth keeping: the broken version
// was written as `new Date(date + 'T' + time)` — which is the LOCAL-parsing form,
// i.e. the CORRECT one — so the control could not move and the oracle reported
// `red=[]` while claiming to have one. A control written from the same intuition
// as the code under test proves nothing.
let stampImpl = gallery.entryStamp;
if (NEG) {
  stampImpl = function bareDateEntryStamp(entry) {
    if (!entry || typeof entry !== 'object') return null;
    const dt = new Date(String(entry.date == null ? '' : entry.date).trim());
    return Number.isNaN(dt.getTime()) ? null : dt;
  };
}
const dayKey = (e) => {
  const s = stampImpl(e);
  if (!s) return null;
  const p = (n) => String(n).padStart(2, '0');
  return `${s.getFullYear()}-${p(s.getMonth() + 1)}-${p(s.getDate())}`;
};

const at = (date, time, text) => ({ date, time, text: text || 'x', hour: time.slice(0, 2) });
const NOW = new Date(2026, 9, 8, 12, 0, 0); // 2026-10-08 12:00 LOCAL

// ── 1. LOCAL, not UTC: the first half-hour of a day is that day's ───────────
arm('a stamp is built in LOCAL time (the UTC-parsing trap)', () => {
  const out = [];
  const midnight = at('2026-10-08', '00:30:00');
  out.push(eq(dayKey(midnight), '2026-10-08', 'the 00:30 line\'s day bucket'));
  out.push(eq(dayKey(at('2026-10-08', '23:59:59')), '2026-10-08', 'the 23:59 line\'s day bucket'));
  // And the SHIPPED function must agree with the local reference above.
  out.push(eq(gallery.dayKey(midnight), '2026-10-08', 'shipped dayKey on the 00:30 line'));
  out.push(eq(gallery.hourKey(midnight), '2026-10-08 00', 'shipped hourKey on the 00:30 line'));
  return out.filter(Boolean);
});

// ── 2. THE RANGE: 24 h inclusive, +1 s out, a future line out ───────────────
arm('inRange is the window ENDING at now, inclusive at its edge', () => {
  const out = [];
  const r24 = gallery.rangeOf('24h');
  const edge = new Date(NOW.getTime() - 24 * 3600 * 1000);
  const inside = at('2026-10-07', '12:00:01');
  const outside = at('2026-10-07', '11:59:59');
  const future = at('2026-10-08', '12:00:01');
  out.push(eq(gallery.inRange(inside, r24, NOW), true, '23 h 59 m 59 s ago is INSIDE 24 h'));
  out.push(eq(gallery.inRange(outside, r24, NOW), false, '24 h 00 m 01 s ago is OUTSIDE 24 h'));
  out.push(eq(gallery.inRange(future, r24, NOW), false, 'a FUTURE line is OUTSIDE the window'));
  // The 1 h range, same shape.
  const r1 = gallery.rangeOf('1h');
  out.push(eq(gallery.inRange(at('2026-10-08', '11:30:00'), r1, NOW), true, '30 min ago is inside 1 h'));
  out.push(eq(gallery.inRange(at('2026-10-08', '10:30:00'), r1, NOW), false, '90 min ago is outside 1 h'));
  // An unknown id must not silently become "everything".
  out.push(eq(gallery.rangeOf('nope'), null, 'an unknown range id is null'));
  out.push(eq(gallery.inRange(inside, 'nope', NOW), false, 'an unknown range matches NOTHING'));
  // Sanity on the edge constant itself (so the arm cannot pass vacuously).
  out.push(eq(edge.getHours(), 12, 'the edge is at 12:00 local'));
  return out.filter(Boolean);
});

// ── 3. BUCKETING: counts, and the owner's order (newest first) ──────────────
arm('buckets groups by day and hour, newest first, and counts', () => {
  const out = [];
  const entries = [
    at('2026-10-07', '09:00:00'), at('2026-10-07', '09:30:00'), at('2026-10-07', '21:00:00'),
    at('2026-10-08', '11:00:00'), at('2026-10-08', '11:43:16'), at('2026-10-08', '11:44:00'),
    at('2026-10-08', '12:00:00'),
  ];
  const b = gallery.buckets(entries);
  out.push(eq(b.total, 7, 'total entries seen'));
  out.push(eq(b.skipped, 0, 'nothing skipped'));
  out.push(eq(b.days.map((d) => d.day), ['2026-10-08', '2026-10-07'], 'days newest first'));
  out.push(eq(b.days.map((d) => d.count), [4, 3], 'per-day counts'));
  out.push(eq(b.days[0].hours.map((h) => h.hour), ['12', '11'], 'hours newest first'));
  out.push(eq(b.days[0].hours.map((h) => h.count), [1, 3], 'per-hour counts'));
  out.push(eq(b.days[1].hours.map((h) => h.hour), ['21', '09'], 'the older day\'s hours'));
  out.push(eq(b.days[1].hours.map((h) => h.count), [1, 2], 'the older day\'s counts'));
  return out.filter(Boolean);
});

// ── 4. AN UNREADABLE LINE IS COUNTED, NEVER BUCKETED INTO "today" ───────────
arm('an unreadable entry is skipped and counted, not bucketed', () => {
  const out = [];
  const b = gallery.buckets([
    at('2026-10-08', '11:00:00'),
    { date: 'garbage', time: '11:00:00' },
    { date: '2026-10-08', time: 'nope' },
    { date: '', time: '' },
    null,
    { text: 'no stamp at all' },
  ]);
  out.push(eq(b.total, 6, 'total seen (including the unreadable ones)'));
  out.push(eq(b.skipped, 5, 'the five unreadable entries are counted'));
  out.push(eq(b.days.length, 1, 'only ONE day exists'));
  out.push(eq(b.days[0].count, 1, 'and it holds exactly the readable line'));
  out.push(eq(gallery.entryStamp({ date: '2026-10-08', time: '11:00' }), gallery.entryStamp(at('2026-10-08', '11:00:00')), 'HH:MM and HH:MM:SS agree'));
  return out.filter(Boolean);
});

// ── 5. select / pick: the list the drawer actually paints ───────────────────
arm('select keeps the range newest-first; pick isolates one bucket', () => {
  const out = [];
  const entries = [
    at('2026-10-06', '09:00:00', 'old'),
    at('2026-10-08', '09:00:00', 'a'),
    at('2026-10-08', '11:00:00', 'b'),
    at('2026-10-08', '11:30:00', 'c'),
  ];
  const sel = gallery.select(entries, '24h', NOW);
  out.push(eq(sel.map((e) => e.text), ['c', 'b', 'a'], '24 h keeps today\'s three, newest first'));
  const hour = gallery.pick(entries, '2026-10-08', '11');
  out.push(eq(hour.map((e) => e.text), ['c', 'b'], 'the 11 h bucket holds exactly two'));
  const day = gallery.pick(entries, '2026-10-08');
  out.push(eq(day.map((e) => e.text), ['c', 'b', 'a'], 'the day bucket holds three'));
  out.push(eq(gallery.pick(entries, '2026-10-08', '09').map((e) => e.text), ['a'], 'the 09 h bucket holds one'));
  return out.filter(Boolean);
});

// ── 6. THE OWNER'S ORDER: 24 h first, then 1 h ──────────────────────────────
arm('the ranges are offered 24 h first, then 1 h', () => {
  const out = [];
  out.push(eq(gallery.RANGES.map((r) => r.id), ['24h', '1h'], 'range order'));
  out.push(eq(gallery.RANGES.map((r) => r.label), ['24 h', '1 h'], 'range labels'));
  out.push(eq(gallery.RANGES.map((r) => r.hours), [24, 1], 'range widths'));
  return out.filter(Boolean);
});

// ── Report ──────────────────────────────────────────────────────────────────
const failed = results.filter((r) => !r.ok);
const redNames = failed.map((r) => r.name);
const offsetMin = new Date(2026, 9, 8, 12, 0, 0).getTimezoneOffset();
// THE CONTROL IS ONLY OBSERVABLE OFF UTC: when the box's offset is 0, local time
// and UTC time are the same instant, so a local/UTC mix-up cannot move any
// assertion — and an oracle that claimed otherwise would be lying about its own
// reach. This is stated, not hidden.
const tzObservable = offsetMin !== 0;
const LOCAL_ARM = 'a stamp is built in LOCAL time (the UTC-parsing trap)';
// The arms that do NOT consume the injected stamp: they must stay GREEN, which is
// what shows the control was SCOPED (it moved the stamp's consumers and nothing
// else) rather than having taken the module down.
const INDEPENDENT_ARMS = [
  'inRange is the window ENDING at now, inclusive at its edge',
  'the ranges are offered 24 h first, then 1 h',
];
let controlsOk;
if (NEG) {
  const localRed = redNames.includes(LOCAL_ARM);
  const scoped = INDEPENDENT_ARMS.every((n) => !redNames.includes(n));
  controlsOk = localRed && scoped && tzObservable;
} else {
  controlsOk = failed.length === 0;
}

for (const r of results) {
  const mark = r.ok ? 'PASS' : 'FAIL';
  console.log(`[${mark}] ${r.name}`);
  for (const p of r.problems) console.log(`       ${p}`);
}
console.log('');
if (NEG) {
  console.log(`TZ: offsetMinutes=${offsetMin} observable=${tzObservable}`);
  console.log(`NEG-ARM: red=${JSON.stringify(redNames)}`);
  console.log(`NEG-ARM: local-arm-red=${redNames.includes(LOCAL_ARM)} independent-arms-green=${INDEPENDENT_ARMS.every((n) => !redNames.includes(n))}`);
  console.log(`NEG-ARM-VERDICT: ${controlsOk ? 'PASS' : 'FAIL'} — the bare-date stamp moved the LOCAL arm and left the stamp-independent arms alone`);
} else {
  console.log(`RESULT: ${failed.length === 0 ? 'GREEN' : 'RED'} — ${results.length - failed.length}/${results.length} arm(s)`);
}
process.exit(controlsOk ? 0 : 1);
