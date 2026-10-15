#!/usr/bin/env node
/* SOTTO — LANE FONTS: the fidelity oracle.
 *
 * WHAT IT PROVES. Each arm is a SEPARATE claim so a green can never hide a red:
 *
 *   ARM A  every family the FIVE EXTRACTED DESIGN ZIPS name is (1) on disk in
 *          `app/panel/fonts/» and (2) declared by an `@font-face» in
 *          `app/panel/themes/fonts.css».
 *   ARM B  every `src:» URL of every `@font-face» resolves to a file that
 *          exists and every face carries `font-display: swap». A `.woff2» in
 *          `app/panel/fonts/» that no `@font-face» declares is reported as WARN,
 *          not RED: it is dead bytes, not a design that paints wrong.
 *   ARM C  every (family, weight, style) a GENERATED THEME asks for in a rule
 *          that sets `font-family» has an EXACT `@font-face». CSS font matching
 *          silently takes the NEAREST face, so a miss here is a design painting
 *          a weight the zip never asked for, with nothing on screen to say so.
 *   ARM D  for every theme scope, the LIVE CAPTION family (the zip's caption
 *          face) at the theme's own `--weight-caption» has an exact face, normal
 *          always, and ITALIC whenever the zips' own Google Fonts URLs request
 *          that italic weight for that family. Where no zip asks for the italic
 *          (Outfit, Jost, Manrope, Space Grotesk, Barlow Condensed, Inter...)
 *          the browser's synthesised oblique is what the design itself gets, so
 *          it is NOT a miss.
 *
 * THE CONTROL IS A NEG-ARM, NOT A COMMENT: `--neg-arm» copies the panel's
 * `themes/» + `fonts/» into a scratch tree, DELETES every `@font-face» of the
 * caption family the first theme scope names from the COPY, and re-runs C and D
 * against it. If the copy does not go RED the gate cannot say no and its green
 * is worthless.
 *
 * NO GUI, NO BROWSER, NO SHELL: bytes only. `$env:TMPDIR» is honoured.
 *
 * Run:  node _main/fonts-fidelity-oracle.mjs
 *       node _main/fonts-fidelity-oracle.mjs --neg-arm
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..');
const args = process.argv.slice(2);
const NEG = args.includes('--neg-arm');
const panelArg = args.indexOf('--panel');
let PANEL = path.resolve(panelArg >= 0 ? args[panelArg + 1] : path.join(REPO, 'app', 'panel'));
const INTAKE = path.join(REPO, 'docs', 'design-intake');

const SHEETS = ['themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
                'themes/theme-4.css', 'themes/theme-5.css', 'themes/cinematic.css',
                'themes/panel-designs.css'];

const say = (s) => { console.log(s); };
const read = (p) => fs.readFileSync(p, 'utf8');
const slug = (fam) => fam.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const primaryFamily = (stack) => {
  const m = String(stack).match(/"([^"]+)"/) || String(stack).match(/'([^']+)'/);
  return m ? m[1] : null;
};

/* ── the declaration side: fonts.css ───────────────────────────────────────── */
function parseFontsCss(root) {
  const file = path.join(root, 'themes', 'fonts.css');
  const text = read(file);
  const faces = [];
  for (const m of text.matchAll(/@font-face\s*\{([^}]*)\}/g)) {
    const b = m[1];
    const fam = (b.match(/font-family:\s*['"]([^'"]+)['"]/) || [])[1];
    const style = (b.match(/font-style:\s*([a-z]+)/) || [])[1] || 'normal';
    const weight = (b.match(/font-weight:\s*(\d+)/) || [])[1];
    const src = (b.match(/url\(([^)]+)\)/) || [])[1];
    const display = (b.match(/font-display:\s*([a-z]+)/) || [])[1] || null;
    faces.push({ fam, style, weight, src, display, file });
  }
  return faces;
}
const faceKey = (fam, weight, style) => fam + '|' + String(weight) + '|' + (style === 'italic' ? 'italic' : 'normal');
const faceIndex = (faces) => new Set(faces.map((f) => faceKey(f.fam, f.weight, f.style)));

/* ── the theme side: every generated stylesheet ────────────────────────────── */
function parseSheets(root) {
  const themes = new Map();
  for (const rel of SHEETS) {
    const file = path.join(root, rel);
    if (!fs.existsSync(file)) continue;
    const lines = read(file).split(/\r?\n/);
    let scope = null, body = null, bodyLine = 0;
    for (let i = 0; i < lines.length; i += 1) {
      const l = lines[i];
      if (body === null) {
        const m = l.match(/(:root\[data-theme[^\]]*\])([^{]*)\{\s*$/);
        if (m) { scope = m[1]; body = []; bodyLine = i + 1; }
        continue;
      }
      if (/^\}\s*$/.test(l)) {
        const idm = scope.match(/data-theme=['^]?([^'\]]*)['\]]?/);
        const id = idm ? idm[1] : scope;
        if (!themes.has(id)) themes.set(id, { id, toks: new Map(), rules: [] });
        const T = themes.get(id);
        for (const ln of body) {
          const t = ln.match(/^\s*(--[a-z0-9-]+):\s*(.+?);/);
          if (t) T.toks.set(t[1], t[2]);
        }
        const text = body.join('\n');
        const fam = (text.match(/font-family:\s*([^;]+);/) || [])[1];
        if (fam) {
          T.rules.push({
            sheet: rel, line: bodyLine, fam: fam.trim(),
            weight: (text.match(/font-weight:\s*([^;]+);/) || [])[1],
            style: (text.match(/font-style:\s*([^;]+);/) || [])[1],
          });
        }
        scope = null; body = null;
        continue;
      }
      body.push(l);
    }
  }
  return themes;
}
function makeResolver(themes) {
  const shared = themes.get('cine-') || { toks: new Map() };
  const lookup = (T, key) => {
    if (T.toks.has(key)) return T.toks.get(key);
    if (T.id.startsWith('cine-') && shared.toks.has(key)) return shared.toks.get(key);
    return null;
  };
  const resolve = (T, expr, depth = 0) => {
    if (expr == null || depth > 6) return null;
    const s = String(expr).trim();
    const m = s.match(/^var\((--[a-z0-9-]+)\s*(?:,\s*([\s\S]+))?\)$/);
    if (!m) return s;
    const hit = lookup(T, m[1]);
    if (hit != null) return resolve(T, hit, depth + 1);
    return m[2] != null ? resolve(T, m[2], depth + 1) : null;
  };
  return { resolve, lookup };
}

/* ── the zip side ──────────────────────────────────────────────────────────── */
/* ── which family does a STACK actually ask for? ─────────────────────────────
 * MEASURED DEFECT, 2026-10-14. \`primaryFamily\` takes the first QUOTED name of a
 * stack. That is right for a design's own stack ("Fraunces","Georgia",serif) and
 * WRONG for a generic one: Tailwind's default
 *
 *   --font-sans: ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji",...
 *   --font-mono: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",...
 *
 * quotes ONLY its fallbacks, so the first quoted name is an OPERATING-SYSTEM
 * face. ARM A then demanded we ship "Apple Color Emoji" (Apple's, proprietary,
 * unbundleable) and "Liberation Mono" (metric-compatible with Courier New, an OS
 * face) -- two REDs that were the ORACLE's defect, not the product's. Both stacks
 * are the built dist/index.html of a zip and name no design typeface at all.
 *
 * The rule below is the narrow one: walk the stack, skip generic CSS keywords and
 * OS-shipped faces, and return the FIRST entry that is left. A stack made only of
 * those asks for NOTHING and returns null. Every skip is PRINTED by ARM A, so a
 * family cannot be dropped silently, and the Google-Fonts requests are scanned
 * independently -- a real face named in a stack is still checked. */
const GENERIC_FAMILIES = new Set(['ui-sans-serif', 'ui-serif', 'ui-monospace',
  'ui-rounded', 'system-ui', '-apple-system', 'blinkmacsystemfont', 'sans-serif',
  'serif', 'monospace', 'cursive', 'fantasy', 'math', 'emoji', 'fangsong',
  'inherit', 'initial', 'unset', 'revert']);
/* Faces that ship with an OPERATING SYSTEM. None can be bundled and none can be
 * declared by an @font-face we own, so a stack that names only these asks for
 * nothing we could deliver. */
const SYSTEM_FACES = new Set(['apple color emoji', 'segoe ui emoji',
  'segoe ui symbol', 'noto color emoji', 'segoe ui', 'sfmono-regular', 'menlo',
  'monaco', 'consolas', 'liberation mono', 'courier new', 'courier',
  'avenir next', 'helvetica neue', 'helvetica', 'arial narrow', 'arial',
  'georgia', 'times new roman', 'times', 'verdana', 'tahoma', 'trebuchet ms',
  'lucida console', 'lucida sans unicode', 'cambria', 'calibri', 'candara',
  'constantia', 'corbel', 'impact', 'comic sans ms', 'palatino linotype',
  'book antiqua', 'franklin gothic medium', 'gabriola', 'ms gothic',
  'malgun gothic', 'microsoft yahei', 'yu gothic', 'meiryo', 'simsun',
  'nsimsun', 'batang', 'gulim', 'dotum', 'dejavu sans', 'dejavu serif',
  'dejavu sans mono']);

function stackEntries(stack) {
  return String(stack).split(',')
    .map((s) => s.trim().replace(/^["']|["']$/g, '').trim())
    .filter(Boolean);
}

/* Returns { family, skipped } -- \`skipped\` is every entry the rule passed over,
 * so the caller can print what it dropped instead of hiding the decision. */
function designFamily(stack) {
  const skipped = [];
  for (const e of stackEntries(stack)) {
    const k = e.toLowerCase();
    if (/^\d+$/.test(e) || e.startsWith('var(') || e.startsWith('--')) {
      skipped.push(e); continue;
    }
    if (GENERIC_FAMILIES.has(k) || SYSTEM_FACES.has(k)) { skipped.push(e); continue; }
    return { family: e, skipped: skipped };
  }
  return { family: null, skipped: skipped };
}

const skippedStacks = [];   // stacks that name no design face (ARM A prints them)
function zipSources() {
  const fams = new Map();          // family -> Set(source)
  const italic = new Map();        // family -> Set(weight) the zips ask for in italic
  if (!fs.existsSync(INTAKE)) return { fams, italic };
  const dirs = fs.readdirSync(INTAKE, { withFileTypes: true })
    .filter((e) => e.isDirectory()).map((e) => e.name);
  const add = (map, key, val) => {
    if (!map.has(key)) map.set(key, new Set());
    map.get(key).add(val);
  };
  for (const d of dirs) {
    const walk = (p, acc = []) => {
      for (const e of fs.readdirSync(p, { withFileTypes: true })) {
        const q = path.join(p, e.name);
        if (e.isDirectory()) walk(q, acc); else acc.push(q);
      }
      return acc;
    };
    for (const f of walk(path.join(INTAKE, d))) {
      if (/package-lock/.test(f) || !/\.(tsx?|css|html)$/.test(f)) continue;
      const text = read(f);
      /* 1. the Google Fonts request: family=NAME:ital,opsz,wght@0,9..144,300;1,9..144,300 */
      for (const m of text.matchAll(/family=([A-Za-z0-9+]+)(:[^"'&\s]*)?/g)) {
        const name = m[1].replace(/\+/g, ' ');
        add(fams, name, d + '/index.html');
        const spec = m[2] || '';
        const at = spec.indexOf('@');
        if (at < 0) continue;
        const axes = spec.slice(1, at).split(',');
        for (const tuple of spec.slice(at + 1).split(';')) {
          const parts = tuple.split(',');
          if (parts.length !== axes.length) continue;
          const obj = {};
          axes.forEach((a, i) => { obj[a] = parts[i]; });
          if (obj.ital !== '1') continue;
          const w = obj.wght || obj.opsz;
          if (!w) continue;
          const mm = String(w).match(/^(\d+)(?:\.\.(\d+))?$/);
          if (!mm) continue;
          const lo = +mm[1], hi = mm[2] ? +mm[2] : lo;
          for (let k = lo; k <= hi; k += 100) add(italic, name, String(k));
        }
      }
      /* 2. the @theme stacks the zips declare (--font-tele, --font-cinema, ...) */
      for (const m of text.matchAll(/--font-[a-z0-9-]+:\s*([^;]+);/g)) {
        const pick = designFamily(m[1]);
        if (pick.family) {
          add(fams, pick.family, d + '/' + path.basename(f) + ' (--font-*)');
        } else {
          /* A stack that names NO design face: printed, never silently dropped. */
          skippedStacks.push({ where: d + '/' + path.basename(f), stack: m[1].trim() });
        }
      }
    }
  }
  return { fams, italic };
}

/* ── the arms ──────────────────────────────────────────────────────────────── */
function armA(faces, zips) {
  const declared = new Set(faces.map((f) => f.fam));
  const onDisk = new Set(fs.readdirSync(path.join(PANEL, 'fonts'))
    .map((n) => (n.match(/^(.+?)-latin-/) || [])[1]).filter(Boolean));
  const bad = [];
  for (const [fam, where] of [...zips.fams].sort()) {
    const hasFile = onDisk.has(slug(fam));
    const hasFace = declared.has(fam);
    if (!hasFile || !hasFace) bad.push({ fam, hasFile, hasFace, where: [...where][0] });
  }
  say('ARM A  zip families=' + zips.fams.size + '  not-on-disk-or-not-declared=' + bad.length
      + '  stacks-naming-no-design-face=' + skippedStacks.length);
  for (const s of skippedStacks) {
    say('       skip ' + s.where + '  --font-* stack names only generic/OS faces: ' + s.stack.slice(0, 70));
  }
  for (const b of bad) say('       RED ' + b.fam + ' onDisk=' + b.hasFile + ' declared=' + b.hasFace + '  <- ' + b.where);
  return bad.length === 0;
}
function armB(faces) {
  const badSrc = [], warn = [], noDisplay = [];
  for (const f of faces) {
    if (!f.src) { badSrc.push(f.fam + ' (no src)'); continue; }
    if (!fs.existsSync(path.resolve(path.dirname(f.file), f.src))) badSrc.push(f.fam + ' ' + f.weight + ' -> ' + f.src);
    if (f.display !== 'swap') noDisplay.push(f.fam + ' ' + f.weight + ' font-display=' + f.display);
  }
  const declared = new Set(faces.map((f) => path.basename(f.src || '')));
  for (const n of fs.readdirSync(path.join(PANEL, 'fonts'))) {
    if (n.endsWith('.woff2') && !declared.has(n)) warn.push(n);
  }
  say('ARM B  @font-face=' + faces.length + '  broken-src=' + badSrc.length
      + '  not-swap=' + noDisplay.length + '  undeclared-files(WARN)=' + warn.length);
  for (const b of badSrc) say('       RED broken src ' + b);
  for (const b of noDisplay) say('       RED font-display ' + b);
  for (const b of warn) say('       WARN undeclared file ' + b + ' (' + fs.statSync(path.join(PANEL, 'fonts', b)).size + ' B, dead bytes: no @font-face declares it)');
  return badSrc.length === 0 && noDisplay.length === 0;
}
function armC(faces) {
  const themes = parseSheets(PANEL);
  const { resolve } = makeResolver(themes);
  const have = faceIndex(faces);
  const asked = new Map();
  for (const [, T] of themes) {
    for (const r of T.rules) {
      const fam = primaryFamily(resolve(T, r.fam) || r.fam);
      const w = resolve(T, r.weight);
      if (fam == null || w == null || !/^\d+$/.test(String(w))) continue;
      const style = String(resolve(T, r.style) || 'normal') === 'italic' ? 'italic' : 'normal';
      const k = faceKey(fam, w, style);
      if (!asked.has(k)) asked.set(k, { n: 0, themes: new Set() });
      asked.get(k).n += 1; asked.get(k).themes.add(T.id);
    }
  }
  const bad = [];
  for (const [k, e] of asked) if (!have.has(k)) bad.push(k + '  x' + e.n + ' rule(s) in [' + [...e.themes].join(',') + ']');
  bad.sort();
  say('ARM C  distinct (family|weight|style) asked by a rule=' + asked.size + '  with no exact @font-face=' + bad.length);
  for (const b of bad) say('       RED ' + b);
  return bad.length === 0;
}
function armD(faces, zips) {
  const themes = parseSheets(PANEL);
  const { resolve, lookup } = makeResolver(themes);
  const have = faceIndex(faces);
  const bad = [];
  let n = 0, italicProbes = 0, italicSkipped = 0;
  for (const [, T] of themes) {
    const sans = lookup(T, '--font-sans');
    if (!sans) continue;
    n += 1;
    const capRaw = lookup(T, '--font-caption') || 'var(--font-sans)';
    const cap = primaryFamily(String(capRaw).includes('--font-sans') ? sans : capRaw);
    const w = String(resolve(T, 'var(--weight-caption)') || '400');
    if (!have.has(faceKey(cap, w, 'normal'))) {
      bad.push(T.id + ' caption=' + cap + ' weight=' + w + ' normal (live/closed line) has no exact face');
    }
    const zipItalic = zips.italic.get(cap);
    if (!zipItalic || !zipItalic.has(w)) { italicSkipped += 1; continue; }
    italicProbes += 1;
    if (!have.has(faceKey(cap, w, 'italic'))) {
      bad.push(T.id + ' caption=' + cap + ' weight=' + w + ' italic (forming line, italic ASKED BY THE ZIP) has no exact face');
    }
  }
  say('ARM D  theme scopes=' + n + '  caption-face misses=' + bad.length
      + '  italic probes=' + italicProbes + '  italic skipped (no zip asks it)=' + italicSkipped);
  for (const b of bad) say('       RED ' + b);
  return bad.length === 0;
}

/* ── the run ───────────────────────────────────────────────────────────────── */
function scratchCopy() {
  const base = process.env.TMPDIR || process.env.TEMP || os.tmpdir();
  const dir = fs.mkdtempSync(path.join(base, 'sotto-fonts-neg-'));
  for (const sub of ['themes', 'fonts']) fs.cpSync(path.join(PANEL, sub), path.join(dir, sub), { recursive: true });
  return dir;
}

say('== SOTTO fonts fidelity oracle ==');
say('panel = ' + PANEL);
say('mode  = ' + (NEG ? 'NEG-ARM (defect injected in a COPY)' : 'shipped tree'));
const zips = zipSources();
const faces = parseFontsCss(PANEL);
const a = armA(faces, zips), b = armB(faces);
if (!NEG) {
  const c = armC(faces), d = armD(faces, zips);
  say('VERDICT: ' + ((a && b && c && d) ? 'PASS' : 'FAIL') + '  (A=' + a + ' B=' + b + ' C=' + c + ' D=' + d + ')');
  process.exit(a && b && c && d ? 0 : 1);
} else {
  const themes = parseSheets(PANEL);
  const { lookup } = makeResolver(themes);
  let victim = null, victimTheme = null;
  for (const [, T] of themes) {
    const sans = lookup(T, '--font-sans');
    if (!sans) continue;
    const capRaw = lookup(T, '--font-caption') || 'var(--font-sans)';
    const cap = primaryFamily(String(capRaw).includes('--font-sans') ? sans : capRaw);
    if (cap) { victim = cap; victimTheme = T.id; break; }
  }
  const dir = scratchCopy();
  const cssPath = path.join(dir, 'themes', 'fonts.css');
  const css = read(cssPath);
  const before = (css.match(/@font-face/g) || []).length;
  const re = new RegExp('@font-face\\s*\\{[^}]*font-family:\\s*[\'"]' + victim + '[\'"];[\\s\\S]*?\\}\\n?', 'g');
  const after = css.replace(re, '');
  fs.writeFileSync(cssPath, after, 'utf8');
  say('NEG-ARM injected: removed every @font-face of family "' + victim + '" (the caption face of ' + victimTheme + ') from the COPY');
  say('NEG-ARM copy faces ' + before + ' -> ' + (after.match(/@font-face/g) || []).length + '  (' + cssPath + ')');
  PANEL = dir;
  const faces2 = parseFontsCss(PANEL);
  const c2 = armC(faces2), d2 = armD(faces2, zips);
  const red = (!c2) || (!d2);
  say('NEG-ARM verdict: ' + (red ? 'RED as required' : 'GREEN — CONTROL IS INERT, the gate cannot say no'));
  say('VERDICT: ' + ((red && a && b) ? 'PASS' : 'FAIL') + '  (control GREEN=' + (a && b) + ', injected RED=' + red + ')');
  process.exit(red && a && b ? 0 : 1);
}
