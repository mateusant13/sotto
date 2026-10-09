/* Sotto — the oracle for the per-theme TEMPLATE layer (`app/panel/theme-tune.js`).
 *
 * Run:  node _main/theme-tune-oracle.js            → PASS/FAIL, exit 0/1
 *       node _main/theme-tune-oracle.js --neg-arm  → also proves the LIVENESS
 *                                                    gate can go RED
 *
 * WHAT THIS FILE IS FOR. The tuning layer's whole risk is not a crash — it is a
 * control that WORKS (it stores a value, it repaints its own readout) and changes
 * nothing on screen, because the variable it writes is read by no rule. This repo
 * has already paid for that class of defect once (`docs/audit/config-inert-fixed.md`),
 * and three tokens in the shipped themes are exactly that trap today:
 * `--slab-opacity` and `--text-confirmed` are declared by all five theme files and
 * consumed by none, and `--font-caption`/`--font-closed` are declared as
 * `var(--font-sans)` and consumed by none. So the strongest arm here is ARM 7: for
 * EVERY token the module can write, `var(--token)` must appear in the panel's own
 * CSS. It reads the real files from disk; it is not a copy of the field list.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PANEL = path.join(ROOT, 'app', 'panel');
const tune = require(path.join(PANEL, 'theme-tune.js'));

const results = [];
let failures = 0;

function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: detail === undefined ? '' : String(detail) });
  if (!ok) failures += 1;
}

function eq(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  check(name, a === e, a === e ? a : `got ${a}, want ${e}`);
}

/* ── ARM 1: colour parsing ─────────────────────────────────────────────────── */
eq('hexToRgb 6-digit', tune.hexToRgb('#F2E9D8'), { r: 242, g: 233, b: 216 });
eq('hexToRgb 3-digit expands', tune.hexToRgb('#fff'), { r: 255, g: 255, b: 255 });
eq('hexToRgb rejects a name', tune.hexToRgb('red'), null);
eq('hexToRgb rejects rgb()', tune.hexToRgb('rgb(1,2,3)'), null);
eq('hexToRgb rejects 8-digit', tune.hexToRgb('#11223344'), null);
eq('rgbaOf keeps the hue', tune.rgbaOf('#FF6A55', 0.16), 'rgba(255, 106, 85, 0.16)');
eq('rgbaOf clamps alpha', tune.rgbaOf('#000000', 5), 'rgba(0, 0, 0, 1)');
eq('rgbaOf rejects a non-colour', tune.rgbaOf('nope', 0.5), null);

/* ── ARM 2: reading the alpha a THEME chose ────────────────────────────────── */
/* The design's own opacity has to survive an accent change, so it is read from
 * the computed value rather than invented here. */
eq('alphaOfComputed reads rgba', tune.alphaOfComputed('rgba(242, 233, 216, 0.12)'), 0.12);
eq('alphaOfComputed reads rgb as opaque', tune.alphaOfComputed('rgb(1, 2, 3)'), 1);
eq('alphaOfComputed refuses a hex', tune.alphaOfComputed('#F2E9D8'), null);
eq('alphaOfComputed refuses garbage', tune.alphaOfComputed('none'), null);

/* ── ARM 3: one field, normalised ──────────────────────────────────────────── */
const sizeCaption = tune.field('sizeCaption');
const accent = tune.field('accent');
const weightCaption = tune.field('weightCaption');
const typeStep = tune.field('typeStep');
const fontSans = tune.field('fontSans');

eq('length: a good value passes', tune.normalizeField(sizeCaption, 34), 34);
eq('length: over the max is clamped', tune.normalizeField(sizeCaption, 999), 64);
eq('length: under the min is clamped', tune.normalizeField(sizeCaption, -10), 12);
eq('length: a unit is tolerated', tune.normalizeField(sizeCaption, '34px'), 34);
eq('length: text is refused (no override)', tune.normalizeField(sizeCaption, 'big'), undefined);
eq('select: a known weight passes', tune.normalizeField(weightCaption, '700'), '700');
eq('select: an unknown weight is refused', tune.normalizeField(weightCaption, '850'), undefined);
eq('select: a number is coerced to its option', tune.normalizeField(weightCaption, 600), '600');
eq('color: a hex is lowercased', tune.normalizeField(accent, '#FF6A55'), '#ff6a55');
eq('color: nonsense is refused', tune.normalizeField(accent, 'chartreuse'), undefined);
eq('length: zero is a real value, not "unset"', tune.normalizeField(typeStep, 0), 0);
eq('font: a bundled stack canonicalises',
  tune.normalizeField(fontSans, '"ibm plex mono",  "cascadia mono", consolas, ui-monospace, monospace'),
  '"IBM Plex Mono", "Cascadia Mono", Consolas, ui-monospace, monospace');
eq('font: an unbundled family is refused',
  tune.normalizeField(fontSans, '"Comic Sans MS", cursive'), undefined);

/* Float noise must not reach the stylesheet. */
eq('number: the step decides the precision',
  tune.normalizeField(tune.field('trackingCaption'), 0.0064), 0.006);
eq('number: a stray decimal is rounded to the step',
  tune.normalizeField(tune.field('leadingCaption'), 1.0633), 1.06);

/* ── ARM 4: the settings map — one theme cannot leak into another ──────────── */
const map = tune.normalizeSettings({
  'theme-1': { sizeCaption: 34, accent: '#FF0000' },
  'theme-2': { sizeCaption: 20, captionUpper: 'none' },
  'theme-9': { sizeCaption: 99 },          // not a theme
  'theme-3': { nopeNotAField: 1 },         // no valid field → whole entry goes
  'theme-4': 'not an object',
  'theme-5': [1, 2, 3],
});
eq('map: only the five known themes survive', Object.keys(map).sort(), ['theme-1', 'theme-2']);
eq('map: theme-1 keeps its own edits', map['theme-1'], { sizeCaption: 34, accent: '#ff0000' });
eq('map: theme-2 keeps its own edits', map['theme-2'], { sizeCaption: 20, captionUpper: 'none' });
check('map: an empty theme is not stored as an empty object', !('theme-3' in map));

/* ── ARM 5: an unreadable store is "no edits yet", never a throw ───────────── */
eq('parse: malformed JSON degrades to {}', tune.parseSettings('{not json'), {});
eq('parse: an array is not a settings map', tune.parseSettings('[1,2,3]'), {});
eq('parse: null is not a settings map', tune.parseSettings('null'), {});
eq('parse: unknown keys are dropped',
  Object.keys(tune.parseSettings('{"theme-1":{"bogus":1},"x":{"sizeCaption":12}}')).length, 0);
eq('round trip', tune.parseSettings(tune.serializeSettings(map)), map);

/* ── ARM 6: the declarations a theme produces ──────────────────────────────── */
const decls = tune.declarationsFor(
  { sizeCaption: 34, accent: '#ff0000', typeStep: 0 },
  { alphaOf: (token) => (token === '--accent-soft' ? 0.12 : null) }
);
const asMap = {};
for (const [token, value] of decls) asMap[token] = value;

eq('decl: the length carries its unit', asMap['--size-caption'], '34px');
eq('decl: the accent is written', asMap['--accent'], '#ff0000');
/* THE SWATCH MUST FOLLOW THE ACCENT. `themes/themes.js` says a swatch that
 * drifts from its theme makes the button lie about the theme it offers; the
 * theme files write `--theme-swatch` as a LITERAL hex, so changing `--accent`
 * without this would leave the dot painting the old colour. */
eq('decl: the picker swatch follows the accent, solid', asMap['--theme-swatch'], '#ff0000');
eq('decl: the accent halo keeps the theme\'s own alpha', asMap['--accent-soft'], 'rgba(255, 0, 0, 0.12)');
eq('decl: the hairlines are re-tinted', asMap['--line'], 'rgba(255, 0, 0, 0.18)');
eq('decl: the strong hairline is re-tinted', asMap['--line-strong'], 'rgba(255, 0, 0, 0.4)');
eq('decl: 0ms is written, not dropped', asMap['--type-step'], '0ms');
check('decl: an untouched knob is not written at all', !('--size-closed' in asMap));
check('decl: a number field carries no unit', !String(tune.declarationsFor({ leadingCaption: 1.06 })[0][1]).includes('px'));

/* ── ARM 7: THE LIVENESS GATE — every knob moves something ──────────────────
 * Reads the shipped CSS from disk. A token that no rule consumes is a control
 * that takes a click and paints nothing. */
const cssFiles = [
  path.join(PANEL, 'panel.css'),
  path.join(PANEL, 'themes', 'fonts.css'),
  ...[1, 2, 3, 4, 5].map((n) => path.join(PANEL, 'themes', `theme-${n}.css`)),
];
let css = '';
const cssPresent = [];
for (const file of cssFiles) {
  if (!fs.existsSync(file)) continue;
  cssPresent.push(path.basename(file));
  css += '\n' + fs.readFileSync(file, 'utf8');
}
check('liveness: the shipped CSS was found', cssPresent.length >= 6, cssPresent.join(','));

function tokenIsConsumed(token) {
  /* `var(--token)` — the only way a custom property reaches a declaration. */
  return css.includes(`var(${token})`) || css.includes(`var(${token},`);
}

const tokens = tune.allTokens();
check('liveness: the module exposes tokens to check', tokens.length >= 10, `${tokens.length} tokens`);
const unconsumed = tokens.filter((t) => !tokenIsConsumed(t));
check('liveness: EVERY knob is consumed by shipped CSS', unconsumed.length === 0,
  unconsumed.length ? `dead knobs: ${unconsumed.join(', ')}` : `${tokens.length} knobs all consumed in ${cssPresent.length} files`);

/* No token may be offered twice: two rows writing one variable would make one of
 * them silently win, and the pair would fight on every paint. */
const dupes = tokens.filter((t, i) => tokens.indexOf(t) !== i);
check('liveness: no token is written by two knobs', dupes.length === 0, dupes.join(', '));

/* THE KNOWN-INERT TOKENS MUST NOT BE OFFERED. This is the positive statement of
 * the same rule, with the three names this repo measured as declared-and-unread. */
const INERT = ['--slab-opacity', '--text-confirmed', '--font-caption', '--font-closed'];
const offeredInert = INERT.filter((t) => tokens.indexOf(t) >= 0);
check('liveness: the measured-inert tokens are not offered', offeredInert.length === 0,
  offeredInert.join(', '));
for (const t of INERT) {
  /* They are declared in the themes — that is WHY they are the trap. */
  check(`liveness: ${t} really is declared in a theme (so it is a trap, not a typo)`,
    css.includes(`${t}:`), '');
  check(`liveness: ${t} is declared and NOT consumed (the reason it is refused)`,
    !tokenIsConsumed(t), tokenIsConsumed(t) ? `${t} IS consumed — revisit the exclusion` : 'declared, read by nothing');
}

/* ── ARM 8: the wiring in the document ──────────────────────────────────────
 * The module is useless if the document does not load it in the right order:
 * after the manifest + switcher (it reads the manifest and follows `data-theme`)
 * and before panel.js. */
const html = fs.readFileSync(path.join(PANEL, 'panel.html'), 'utf8');
const iManifest = html.indexOf('src="themes/themes.js"');
const iSwitcher = html.indexOf('src="theme-switcher.js"');
const iTune = html.indexOf('src="theme-tune.js"');
const iPanel = html.indexOf('src="panel.js"');
check('wiring: all four scripts are linked',
  [iManifest, iSwitcher, iTune, iPanel].every((i) => i >= 0),
  `manifest=${iManifest} switcher=${iSwitcher} tune=${iTune} panel=${iPanel}`);
check('wiring: theme-tune loads AFTER the switcher', iTune > iSwitcher);
check('wiring: theme-tune loads BEFORE panel.js', iTune > 0 && iTune < iPanel);

const src = fs.readFileSync(path.join(PANEL, 'theme-tune.js'), 'utf8');
/* The dialog must NOT be a child of `.panel`: the slab clips its own overflow
 * (`panel.css .panel { overflow: hidden }`), which is the documented reason
 * `#pause-dialog` is a sibling of `.panel` too. */
check('wiring: the dialog is appended to <body>, outside the clipping slab',
  src.includes('doc.body.append(dialog)') && !src.includes(".querySelector('.panel').append"));
/* HIDE STAYS LAST: the gear is inserted BEFORE the pause button, so it can never
 * become the rightmost control the owner ruled against. */
check('wiring: the gear is inserted before the pause button, so Hide stays rightmost',
  src.includes("host.insertBefore(btn, pause)"));
check('wiring: the CSS for the dialog exists',
  css.includes('.tune-body') && css.includes('.tune-row__reset') && css.includes('.tune-dialog'));

/* ── ARM 9 (--neg-arm): the liveness gate can go RED ────────────────────────
 * A gate that cannot fail is not a gate. The subject is the token this lane
 * caught by hand: it is declared by all five themes and read by none, so the
 * SAME predicate that passes every offered knob must reject it. */
if (process.argv.indexOf('--neg-arm') >= 0) {
  const bogus = '--slab-opacity';
  const consumed = tokenIsConsumed(bogus);
  check('neg-arm: the gate REJECTS a declared-but-unread token', consumed === false,
    consumed ? 'the gate would have passed --slab-opacity: it is vacuous' : 'rejected as expected');
  /* And a token that IS consumed must pass it, or the gate is just always-false. */
  check('neg-arm: the gate ACCEPTS a consumed token', tokenIsConsumed('--size-caption') === true);
}

/* ── report ───────────────────────────────────────────────────────────────── */
const pad = results.reduce((m, r) => Math.max(m, r.name.length), 0);
for (const r of results) {
  console.log(`${r.ok ? 'ok  ' : 'FAIL'}  ${r.name.padEnd(pad)}  ${r.detail}`);
}
console.log('');
console.log(`ARMS: ${results.length}  PASS: ${results.length - failures}  FAIL: ${failures}`);
console.log(failures === 0 ? 'VERDICT: PASS' : 'VERDICT: FAIL');
process.exit(failures === 0 ? 0 : 1);
