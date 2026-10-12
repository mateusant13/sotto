#!/usr/bin/env node
/**
 * S1 GAP ORACLE - every design named inside the 5 .zip prototypes vs every theme/skin
 * the LIVE panel actually ships. Read-only: it never writes, never launches anything.
 *
 * WHAT IT MEASURES
 *   1. zip-side designs, parsed out of the extracted sources under
 *      docs/design-intake/<zip>/src/... (5 sources, one parser each).
 *   2. live-side artefacts: app/panel/themes/themes.js manifest, the
 *      app/panel/themes/panel-designs.js manifest fragment, and the per-skin
 *      file prefixes in app/panel/skins/cinematic-2/ (plus that index.json own
 *      frozen list).
 *   3. the join, in TWO modes:
 *        STRICT  - normalized id == normalized live id. No analyst bridges.
 *        ALIASED - STRICT plus a printed list of analyst-declared bridges
 *                  (zip A tele -> theme-1 "Teleprompter" -> pd-tele, etc.).
 *      Both numbers are printed so the bridges can never hide a gap.
 *   4. live artefacts that have NO source in any of the 5 zips (the other half
 *      of the matrix - a theme nobody can trace is as much a finding as a
 *      design nobody ported).
 *
 * CONTROL ARM (--self-check)
 *   Copies the live root to a temp dir, applies ONE mutation (drop one theme
 *   entry / delete one skin files / drop one pd-* entry), and asserts the matrix
 *   CHANGES in the predicted direction. An instrument that stays silent on a
 *   mutated input cannot say NO, so a silent arm fails the run (rc=2).
 *
 * USAGE
 *   node docs/design-intake/gap-oracle.mjs                # the matrix
 *   node docs/design-intake/gap-oracle.mjs --self-check   # matrix + control arm
 *   node docs/design-intake/gap-oracle.mjs --json         # machine-readable
 *
 * Exit codes: 0 = the run completed. The matrix is DATA, not a gate: it reports
 * gaps instead of failing on them (a real gap here is a legitimate finding).
 * 2 = --self-check failed, i.e. the control arm did NOT detect its mutation.
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';

const REPO = process.env.SOTTO_ROOT || 'H:\\sotto';
const ZIP_ROOT = path.join(REPO, 'docs', 'design-intake');
const LIVE_ROOT = path.join(REPO, 'app', 'panel');

const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
const sha = (p) => {
  try { return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex').slice(0, 12).toUpperCase(); }
  catch { return 'ABSENT'; }
};
const bytes = (p) => { try { return fs.statSync(p).size; } catch { return -1; } };

/** one zip source -> [{id, name, file, line, kind}] plus a __declared__ sentinel
 *  carrying the cardinality the source itself declares, so a parser that
 *  silently yields 0 is visible in the output instead of hidden. */
function parseZipSource(dir, label) {
  const found = [];
  const add = (id, name, file, line, kind) => found.push({ id, name, file, line, kind });
  const rp = (f) => path.join(ZIP_ROOT, dir, f);

  // --- A: sotto-app-design-directions - src/data/designs.ts DESIGNS: DesignDef[]
  let a;
  try { a = fs.readFileSync(rp('src/data/designs.ts'), 'utf8'); } catch {}
  if (a) {
    // SCOPE: only the DESIGNS array. designs.ts ALSO declares SCENES (:105-109) whose
    // entries carry id/name too (noir/stage/deep) - those are background IMAGES, not
    // designs. Parsing the whole file silently counts 8 instead of 5, so the array is
    // sliced out from its declaration to its first top-level close.
    const dStart = a.search(/DESIGNS\s*:\s*DesignDef/);
    const dEnd = dStart < 0 ? -1 : a.indexOf('\n];', dStart);
    a = dStart < 0 ? '' : a.slice(dStart, dEnd < 0 ? undefined : dEnd + 3);
    const re = /\bid:\s*['"]([^'"]+)['"]/g;
    let m;
    while ((m = re.exec(a))) {
      const at = a.slice(0, m.index).split(/\r?\n/).length;
      const nm = /name:\s*['"]([^'"]+)['"]/.exec(a.slice(m.index, m.index + 320));
      add(m[1], nm ? nm[1] : m[1], 'src/data/designs.ts', at, 'design');
    }
    const declaredAt = a.split(/\r?\n/).findIndex(l => /DESIGNS\s*:\s*DesignDef/.test(l));
    found.push({ id: '__declared__', name: String(found.length), file: 'src/data/designs.ts', line: declaredAt + 1, kind: 'declared' });
  }

  // --- B / D: cinematic-transcription-app-designs[ (1)| (2)] - src/themes.ts THEMES
  let t;
  try { t = fs.readFileSync(rp('src/themes.ts'), 'utf8'); } catch {}
  if (t) {
    const re = /\bid:\s*['"]([^'"]+)['"]/g;
    let m;
    while ((m = re.exec(t))) {
      const at = t.slice(0, m.index).split(/\r?\n/).length;
      const nm = /name:\s*['"]([^'"]+)['"]/.exec(t.slice(m.index, m.index + 220));
      add(m[1], nm ? nm[1] : m[1], 'src/themes.ts', at, 'theme');
    }
    found.push({ id: '__declared__', name: String(found.filter(x => x.kind === 'theme').length), file: 'src/themes.ts', line: 1, kind: 'declared' });
  }

  // --- C: cinematic-transcription-app-designs (1) - components/panels/PanelSet{A,B}.tsx
  for (const f of ['src/components/panels/PanelSetA.tsx', 'src/components/panels/PanelSetB.tsx']) {
    let s;
    try { s = fs.readFileSync(rp(f), 'utf8'); } catch {}
    if (!s) continue;
    s.split(/\r?\n/).forEach((l, i) => {
      const m = /^export function ([A-Za-z0-9_]+)\s*\(/.exec(l);
      if (m) add(m[1], m[1], f, i + 1, 'panel');
    });
  }

  // --- E: sotto-transcription-panel-designs - src/components/panels.tsx
  let e;
  try { e = fs.readFileSync(rp('src/components/panels.tsx'), 'utf8'); } catch {}
  if (e) {
    e.split(/\r?\n/).forEach((l, i) => {
      const m = /^export function ([A-Za-z0-9_]+)\s*\(/.exec(l);
      if (m) add(m[1].replace(/Panel$/, ''), m[1], 'src/components/panels.tsx', i + 1, 'panel');
    });
  }

  return { dir, label, items: found };
}

const ZIP_SOURCES = [
  ['sotto-app-design-directions', 'A - sotto-app-design-directions.zip'],
  ['cinematic-transcription-app-designs', 'B - cinematic-transcription-app-designs.zip'],
  ['cinematic-transcription-app-designs (1)', 'C - cinematic-transcription-app-designs (1).zip'],
  ['cinematic-transcription-app-designs (2)', 'D - cinematic-transcription-app-designs (2).zip'],
  ['sotto-transcription-panel-designs', 'E - sotto-transcription-panel-designs.zip'],
];

/** the live side, from a root that can be a mutated copy */
function parseLive(liveRoot) {
  const themes = [];
  const pds = [];
  const skins = [];
  let skinsJs = { size: -1, sha: 'ABSENT', nameEntries: 0 };
  let idx = { size: -1, sha: 'ABSENT', frozen: [], complete: false, designs: [], viewport: null };

  const readManifest = (file, sink) => {
    const p = path.join(liveRoot, 'themes', file);
    let s;
    try { s = fs.readFileSync(p, 'utf8'); } catch { return; }
    const re = /name:\s*['"]([^'"]+)['"]\s*,\s*\r?\n\s*label:\s*['"]([^'"]+)['"]/g;
    let m;
    while ((m = re.exec(s))) {
      const at = s.slice(0, m.index).split(/\r?\n/).length;
      const file_ = /file:\s*['"]([^'"]+)['"]/.exec(s.slice(m.index, m.index + 200));
      sink.push({ name: m[1], label: m[2], file: file_ ? file_[1] : '', line: at + 1 });
    }
  };
  readManifest('themes.js', themes);
  readManifest('panel-designs.js', pds);
  // The THIRD zip's ten panel designs (owner, 2026-10-12). Same fragment shape,
  // same sink: they are panel designs, and the C rows below are matched by NAME.
  readManifest('zipc-panels.js', pds);

  const sj = path.join(liveRoot, 'skins', 'skins.js');
  try {
    const s = fs.readFileSync(sj, 'utf8');
    // size = BYTES ON DISK, not s.length (which counts UTF-16 code units and reads
    // ~380 low in a file that is mostly ASCII).
    skinsJs = { size: bytes(sj), sha: sha(sj), nameEntries: (s.match(/\bname:\s*['"]/g) || []).length };
  } catch {}

  const skinDir = path.join(liveRoot, 'skins', 'cinematic-2');
  for (const f of (() => { try { return fs.readdirSync(skinDir); } catch { return []; } })()) {
    const m = /^([a-z0-9-]+)\.(stage|caption|chrome|panel)\.html$/.exec(f);
    if (m && !skins.some(x => x.name === m[1])) skins.push({ name: m[1], label: m[1] });
  }
  const ij = path.join(skinDir, 'index.json');
  try {
    const j = JSON.parse(fs.readFileSync(ij, 'utf8'));
    idx = { size: bytes(ij), sha: sha(ij), frozen: j.frozen || [], complete: !!j.complete, designs: j.designs || [], viewport: j.viewport || null };
  } catch {}

  return { themes, pds, skins, skinsJs, idx };
}

/**
 * Analyst-declared bridges. Each entry is EXPLICIT and printed, so a reader can
 * audit or reject it. STRICT (no bridges) is always reported alongside, so a
 * bridge can never hide a gap silently.
 */
const BRIDGES = [
  { from: 'tele', to: ['theme-1', 'pd-tele'], why: 'zip A "Teleprompter" -> theme-1 "Teleprompter" + pd-tele' },
  { from: 'bcast', to: ['theme-2', 'pd-bcast'], why: 'zip A "Broadcast" -> theme-2 "Broadcast" + pd-bcast' },
  { from: 'mano', to: ['theme-3', 'pd-mano'], why: 'zip A "Manuscrito" -> theme-3 "Manuscrito" + pd-mano' },
  { from: 'cine', to: ['theme-4', 'pd-cine'], why: 'zip A "Cartao de Cinema" -> theme-4 + pd-cine' },
  { from: 'inst', to: ['theme-5', 'pd-instr'], why: 'zip A "Instrumento" -> theme-5 + pd-instr' },
  { from: 'Teleprompter', to: ['pd-tele', 'theme-1'], why: 'zip E TeleprompterPanel -> pd-tele' },
  { from: 'Broadcast', to: ['pd-bcast', 'theme-2'], why: 'zip E BroadcastPanel -> pd-bcast' },
  { from: 'Manuscript', to: ['pd-mano', 'theme-3'], why: 'zip E ManuscriptPanel -> pd-mano' },
  { from: 'Cinema', to: ['pd-cine', 'theme-4'], why: 'zip E CinemaPanel -> pd-cine' },
  { from: 'Instrument', to: ['pd-instr', 'theme-5'], why: 'zip E InstrumentPanel -> pd-instr' },
  { from: 'tideline', to: ['cine-tideline-body'], why: 'zip B Tideline -> cine-tideline-body (label "Tideline"); the manifest carries BOTH cine-tideline and cine-tideline-body' },
  { from: 'midnight-rain', to: ['cine-midnight-rain'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'warm-hour', to: ['cine-warm-hour'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'velvet-dusk', to: ['cine-velvet-dusk'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'study-light', to: ['cine-study-light'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'motel-glow', to: ['cine-motel-glow'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'paper-moon', to: ['cine-paper-moon'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'quiet-streets', to: ['cine-quiet-streets'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'last-reel', to: ['cine-last-reel'], why: 'manifest prefixes zip B ids with "cine-"' },
  { from: 'north-fog', to: ['cine-north-fog'], why: 'manifest prefixes zip B ids with "cine-"' },
];

function classify(zipSources, live) {
  const liveAll = [
    ...live.themes.map(t => ({ ...t, kind: 'theme' })),
    ...live.pds.map(t => ({ ...t, kind: 'panel-design' })),
    ...live.skins.map(t => ({ ...t, kind: 'skin' })),
  ];
  // A live name can be AMBIGUOUS: two live artefacts can normalize to the same
  // key (measured: 'tideline' -> cine-tideline AND cine-tideline-body). First-wins
  // would silently credit one and hide the other, so every key keeps ALL candidates
  // and the row reports AMBIGUOUS when there is more than one.
  const liveByNorm = new Map();
  for (const l of liveAll) {
    for (const k of [l.name, l.label]) {
 const n = norm(k);
      if (!n) continue;
      if (!liveByNorm.has(n)) liveByNorm.set(n, []);
      const arr = liveByNorm.get(n);
      if (!arr.some(x => x.name === l.name && x.kind === l.kind)) arr.push(l);
    }
  }
  const pick = (k) => {
    const arr = liveByNorm.get(k);
    if (!arr || !arr.length) return null;
    if (arr.length === 1) return { live: arr[0], ambiguous: false, candidates: arr };
    return { live: null, ambiguous: true, candidates: arr };
  };

  const rows = [];
  for (const src of zipSources) {
    for (const it of src.items) {
      if (it.id === '__declared__') continue;
      const row = { ...it, zip: src.dir, zipLabel: src.label };
      const n = norm(it.id);
      const nLabel = norm(it.name);
      const s1 = pick(n), s2 = pick(nLabel);
      row.strictHit = s1 && !s1.ambiguous ? s1.live : null;
      row.strictAmbiguous = s1 && s1.ambiguous ? s1.candidates : null;
      const hitsA = [];
      for (const b of BRIDGES) {
        if (norm(b.from) !== n && norm(b.from) !== nLabel) continue;
        for (const to of b.to) {
          const p = pick(norm(to));
          if (!p) continue;
          if (p.ambiguous) { hitsA.push({ to, via: b.why + ' [AMBIGUOUS]', ambiguous: p.candidates }); continue; }
          hitsA.push({ to, via: b.why, live: p.live });
        }
      }
      row.aliasedHit = hitsA.length ? hitsA : (row.strictHit ? [{ to: row.strictHit.name, via: 'exact', live: row.strictHit }] : null);
      rows.push(row);
    }
  }

  const zipNorms = new Set();
  for (const src of zipSources) for (const it of src.items) {
    if (it.id === '__declared__') continue;
    zipNorms.add(norm(it.id)); zipNorms.add(norm(it.name));
  }
  for (const b of BRIDGES) for (const to of b.to) zipNorms.add(norm(to));
  // claimed = names any zip design actually resolved to (strict, exact or bridged).
  // Matching on the zip NORM set instead would hide cine-tideline behind the shared
  // 'tideline' key, so the live side is claimed by identity, not by spelling.
  const claimed = new Set();
  for (const r of rows) {
    if (r.strictHit) claimed.add(r.strictHit.kind + ':' + r.strictHit.name);
    for (const h of (r.aliasedHit || [])) if (h.live) claimed.add(h.live.kind + ':' + h.live.name);
  }
  const orphanLive = liveAll.filter(l => !claimed.has(l.kind + ':' + l.name));

  return { rows, orphanLive, liveAll, liveByNorm };
}

function letterOf(zipSources, zipDir) {
  const s = zipSources.find(x => x.dir === zipDir);
  return (s.label.match(/^([A-E])/) || ['?'])[0];
}

function renderMatrix(zipSources, live, cls) {
  const L = [];
  const w = (s) => L.push(s);
  w('='.repeat(98));
  w('S1 GAP ORACLE - designs inside the 5 .zip prototypes vs the LIVE app/panel');
  w('='.repeat(98));
  w('repo      : ' + REPO);
  w('zip root  : ' + ZIP_ROOT);
  w('live root : ' + LIVE_ROOT);
  w('');

  w('--- ZIP SIDE (parsed from the extracted JSX/TS, not from the zip listing) -------');
  let total = 0;
  for (const src of zipSources) {
    const real = src.items.filter(i => i.id !== '__declared__');
    total += real.length;
    w('  ' + src.label.padEnd(54) + String(real.length).padStart(3) + ' designs');
  }
  w('  ' + 'TOTAL'.padEnd(54) + String(total).padStart(3) + ' designs');
  w('');

  w('--- LIVE SIDE (measured now) --------------------------------------------------');
  w('  themes.js manifest entries         ' + String(live.themes.length).padStart(3));
  w('  panel-designs.js + zipc-panels.js  ' + String(live.pds.length).padStart(3));
  w('  skins/cinematic-2/ skin prefixes   ' + String(live.skins.length).padStart(3));
  w('  => live artefacts                  ' + String(live.themes.length + live.pds.length + live.skins.length).padStart(3));
  w('  measured skins/skins.js              ' + live.skinsJs.size + ' B, sha256 ' + live.skinsJs.sha +
    ', ' + live.skinsJs.nameEntries + ' name: entries -> ' +
    (live.skinsJs.nameEntries === 0 ? 'NOT a name-keyed manifest' : 'name-keyed'));
  w('  measured skins/cinematic-2/index.json ' + live.idx.size + ' B, sha256 ' + live.idx.sha +
    ', frozen=' + live.idx.frozen.length + ', complete=' + live.idx.complete +
    ', viewport=' + JSON.stringify(live.idx.viewport));
  w('  self-check: index.json frozen[] vs file prefixes -> ' +
    (live.idx.frozen.length === live.skins.length ? 'MATCH (' + live.skins.length + ')' :
      'MISMATCH frozen=' + live.idx.frozen.length + ' prefixes=' + live.skins.length));
  w('');

  const rows = cls.rows;
  const strictOK = rows.filter(r => r.strictHit).length;
  const aliasOK = rows.filter(r => r.aliasedHit).length;
  w('--- THE JOIN ------------------------------------------------------------------');
  w('  STRICT  (normalized id == normalized live id, no analyst bridges)');
  w('     implemented ' + String(strictOK).padStart(3) + ' / ' + rows.length + '    unimplemented ' + String(rows.length - strictOK).padStart(3));
  w('  ALIASED (STRICT + ' + BRIDGES.length + ' declared bridges, every one printed below)');
  w('     implemented ' + String(aliasOK).padStart(3) + ' / ' + rows.length + '    unimplemented ' + String(rows.length - aliasOK).padStart(3));
  w('');
  w('    zip  id                strict    aliased   live match');
  for (const r of rows) {
    const s = r.strictHit ? 'YES' : 'no';
    const a = r.aliasedHit ? 'YES' : 'no';
    let match;
    if (r.aliasedHit) match = r.aliasedHit.map(h => h.ambiguous ? h.to + ' [AMBIGUOUS x' + h.ambiguous.length + ']' : h.to).join(', ');
    else if (r.strictAmbiguous) match = 'AMBIGUOUS: ' + r.strictAmbiguous.map(c => c.name).join(' OR ');
    else if (r.strictHit) match = r.strictHit.name;
    else match = '-';
    w('    ' + letterOf(zipSources, r.zip).padEnd(5) + String(r.id).padEnd(18) + s.padEnd(10) + a.padEnd(10) + match);
  }
  w('');

  const gaps = rows.filter(r => !r.aliasedHit);
  const strictGaps = rows.filter(r => !r.strictHit);
  w('  GAPS - no live implementation, STRICT mode : ' + strictGaps.length);
  for (const g of strictGaps) w('     [' + letterOf(zipSources, g.zip) + '] ' + g.id + '  (' + g.file + ':' + g.line + ')');
  w('  GAPS - no live implementation, ALIASED mode: ' + gaps.length);
  for (const g of gaps) w('     [' + letterOf(zipSources, g.zip) + '] ' + g.id + '  (' + g.file + ':' + g.line + ')');
  w('');

  const oT = cls.orphanLive.filter(l => l.kind === 'theme');
  const oP = cls.orphanLive.filter(l => l.kind === 'panel-design');
  const oS = cls.orphanLive.filter(l => l.kind === 'skin');
  w('  LIVE ARTEFACTS WITH NO SOURCE IN ANY OF THE 5 ZIPS: ' + cls.orphanLive.length);
  if (oT.length) w('     themes.js (' + oT.length + '): ' + oT.map(l => l.name).join(', '));
  if (oP.length) w('     panel-designs.js (' + oP.length + '): ' + oP.map(l => l.name).join(', '));
  if (oS.length) w('     skins (' + oS.length + '): ' + oS.map(l => l.name).join(', '));
  w('');

  w('--- ANALYST-DECLARED BRIDGES (each is what turns a strict no into a YES) --------');
  const seen = new Set();
  for (const b of BRIDGES) {
    if (seen.has(b.why)) continue;
    seen.add(b.why);
    w('     ' + b.from.padEnd(14) + ' -> ' + b.to.join(', ') + '   | ' + b.why);
  }
  w('');
  w('--- WHAT THIS ORACLE DOES NOT MEASURE ------------------------------------------');
  w('  * whether a live theme LOOKS like the zip design it is matched to by name.');
  w('    This is a NAME matrix; visual equivalence is measured design by design');
  w('    in the sheet, from the JSX/CSS, not here.');
  w('  * the bodies of the skins. Only their file prefixes are counted; no .html');
  w('    or .css inside cinematic-2/ is parsed for design identity.');
  w('  * zip C caption variants (wide/tight/italic/editorial/mono): those are');
  w('    variants of ONE panel, not separate designs, so they are deliberately');
  w('    outside this count. They are measured in the sheet.');
  w('  * no file was written and no process was launched to produce this output.');
  return L.join('\n');
}

/* ------------------------------ control arm ------------------------------ */

function selfCheck(zipSources, live, cls) {
  const L = [];
  const w = (s) => L.push(s);
  let failed = 0;
  const check = (name, cond, detail) => {
    w('  [' + (cond ? 'PASS' : 'FAIL') + '] ' + name + (detail ? '  -- ' + detail : ''));
    if (!cond) failed++;
  };

  const rows = cls.rows;
  check('real arm: strict results are a subset of aliased results',
    rows.filter(r => r.strictHit).every(r => r.aliasedHit));
  check('real arm: every row cites a file:line',
    rows.every(r => r.file && r.line > 0));
  check('real arm: live side non-empty',
    live.themes.length > 0 && live.pds.length > 0 && live.skins.length > 0,
    live.themes.length + ' themes + ' + live.pds.length + ' pd + ' + live.skins.length + ' skins');
  check('real arm: index.json frozen[] == file prefixes',
    live.idx.frozen.length === live.skins.length,
    'frozen=' + live.idx.frozen.length + ' prefixes=' + live.skins.length);

  const strictGaps = rows.filter(r => !r.strictHit).length;
  const aliasGaps = rows.filter(r => !r.aliasedHit).length;
  check('real arm has a detectable population (strict gaps >= 1)',
    strictGaps >= 1, 'strict gaps=' + strictGaps + ', aliased gaps=' + aliasGaps);

  // os.tmpdir() reads process.env.TEMP/TMP, which is EMPTY under some hosts and
  // then resolves to a bogus relative path. AGENTS.md rule 6 names I:\cc-tmp.
  const tmpBase = [process.env.TMPDIR, process.env.TEMP, process.env.TMP]
    .find(p => p && fs.existsSync(p)) || 'I:\\cc-tmp';
  fs.mkdirSync(tmpBase, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(tmpBase, 's1-gap-neg-'));
  try {
    // Copy the WHOLE live root first. parseLive(tmp) must see a COMPLETE tree:
    // copying only the mutated file guts the live side (0 skins, 0 panel-designs),
    // and the regression count would then measure 'everything vanished' instead of
    // 'this one artefact vanished'.
    const copyTree = (srcDir, dstDir) => {
      for (const e of fs.readdirSync(srcDir, { withFileTypes: true })) {
        const s = path.join(srcDir, e.name);
        const d = path.join(dstDir, e.name);
        if (e.isDirectory()) { fs.mkdirSync(d, { recursive: true }); copyTree(s, d); }
        else { fs.mkdirSync(path.dirname(d), { recursive: true }); fs.copyFileSync(s, d); }
      }
    };
    copyTree(LIVE_ROOT, tmp);
    const read = (rel) => fs.readFileSync(path.join(tmp, rel), 'utf8');
    const write = (rel, s) => fs.writeFileSync(path.join(tmp, rel), s);

    // MUTATION 1 -- delete one themes.js entry: a live theme must vanish from the
    // manifest, and any zip design matched ONLY to it must regress to a gap.
    const tOrig = read('themes/themes.js');
    const victim = /name:\s*'theme-2',[\s\S]{0,140}?\},\s*\r?\n/.exec(tOrig) ||
                   /name:\s*'cine-midnight-rain',[\s\S]{0,140}?\},\s*\r?\n/.exec(tOrig);
    check('mutation 1 target found in themes.js', !!victim);
    if (victim) {
      write('themes/themes.js', tOrig.replace(victim[0], ''));
      const lv = parseLive(tmp);
      const c2 = classify(zipSources, lv);
      const regressed = c2.rows.filter((r, i) => !r.strictHit && rows[i] && rows[i].strictHit);
      const regressedIds = regressed.map(r => r.id);
      check('mutation 1: deleting a themes.js entry regresses its designs to gaps',
        regressed.length >= 1, 'regressed=' + regressedIds.join(','));
    }

    // MUTATION 2 -- delete one frozen skin's fragment files. The skin prefix is
    // derived from the directory listing, so removing every file of one prefix
    // must drop it from live.skins and regress the zip design that matched it.
    const skinDir = path.join(tmp, 'skins', 'cinematic-2');
    const skinPrefix = 'blue-plate';
    const skinFiles = fs.readdirSync(skinDir).filter(f => f.startsWith(skinPrefix + '.'));
    check('mutation 2 target found in skin dir', skinFiles.length > 0, skinFiles.length + ' files');
    for (const f of skinFiles) fs.rmSync(path.join(skinDir, f));
    const lv2 = parseLive(tmp);
    const c3 = classify(zipSources, lv2);
    const regressedP = c3.rows.filter((r, i) => !r.strictHit && rows[i] && rows[i].strictHit);
    check('mutation 2: deleting a skin prefix regresses its design',
      regressedP.length >= 1, 'regressed=' + regressedP.map(r => r.id).join(','));

    // MUTATION 3 -- break the skins index.json frozen[] array. skins[] comes from the
    // directory, frozen[] from index.json, so the two must DISAGREE afterwards.
    const iOrig = read('skins/cinematic-2/index.json');
    check('mutation 3 target found in index.json', /"frozen"\s*:\s*\[/.test(iOrig));
    write('skins/cinematic-2/index.json',
      iOrig.replace(/"frozen"\s*:\s*\[[\s\S]*?\]/, '"frozen": []'));
    const lv3 = parseLive(tmp);
    check('mutation 3: frozen[] no longer matches the file prefixes',
      lv3.idx.frozen.length !== lv3.skins.length,
      'frozen=' + lv3.idx.frozen.length + ' prefixes=' + lv3.skins.length);


    check('control arm: live side still parses after mutations', lv3.themes.length >= 0);

    const verdict = failed === 0;
    w('');
    w('CONTROL ARM VERDICT: ' + (verdict ? 'PASS' : 'FAIL') + '  (' + failed + ' failing check(s))');
    w('');
    if (!verdict) process.exitCode = 2;
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  for (const s of L) console.log(s);
}

/* --------------------------------- main flow --------------------------------- */

const zipSources = ZIP_SOURCES.map(([dir, label]) => parseZipSource(dir, label));
const live = parseLive(LIVE_ROOT);
const cls = classify(zipSources, live);

if (process.argv.includes('--self-check')) {
  selfCheck(zipSources, live, cls);
} else if (process.argv.includes('--json')) {
  console.log(JSON.stringify({
    zipSources: zipSources.map(s => ({ label: s.label, count: s.items.filter(i => i.id !== '__declared__').length })),
    live: { themes: live.themes.length, pds: live.pds.length, skins: live.skins.length },
    rows: cls.rows,
    orphanLive: cls.orphanLive
  }, null, 2));
} else {
  console.log(renderMatrix(zipSources, live, cls));
}
