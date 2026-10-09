/* Sotto — the RENDER runner for the per-theme template layer.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe \
 *       _main/theme-tune-render-test/main.js
 *
 * A real Chromium, a HIDDEN window (`show: false`, never shown), the REAL
 * stylesheets of the panel and the REAL `theme-tune.js`. It answers the one
 * question the Node oracle cannot: does an edit actually change what the engine
 * PAINTS, and does it stay inside the theme it was made on?
 *
 * EVERY CHECK IS RELATIONAL, on purpose. The theme's own numbers (30px, 20px,
 * #F2E9D8) are READ from the theme at runtime and compared with what the same
 * element reports after an edit — no expected value is hard-coded here, because a
 * hard-coded one is a second copy of the design that drifts the day
 * `gen_themes.py` moves, and then this instrument lies.
 *
 * The claims, one per line of output:
 *   cascade       an edit raises `--size-caption` on <html> AND the caption's own
 *                 computed `font-size` moves with it (inline beats the theme's
 *                 `:root[data-theme]` rule).
 *   isolation     switching to another theme drops the first theme's edit and the
 *                 element reports the OTHER theme's own value.
 *   memory        switching back restores the first theme's edit.
 *   baseline-read "restore this theme" returns the value the THEME declares, which
 *                 is the value read before the edit — so the baseline is read, not
 *                 copied.
 *   colour        an accent edit moves `--accent`, the picker swatch
 *                 (`--theme-swatch`) and the halo (`--accent-soft`) together, and
 *                 the halo keeps the theme's OWN alpha.
 *   off-switch    `--type-step: 0ms` reaches the stylesheet (the reveal's
 *                 documented off switch), rather than being treated as "unset".
 *   wiring        the gear exists inside `.panel__controls`, sits BEFORE the pause
 *                 button, HIDE IS STILL LAST, and the dialog is outside `.panel`
 *                 (the slab clips its own overflow).
 *   no-throw      no window error was raised while all of that happened.
 */
'use strict';

const path = require('path');
const { app, BrowserWindow } = require('electron');

const PAGE = path.join(__dirname, 'page.html');

/* Runs INSIDE the page. Returns raw observations plus the relational checks. */
const DRIVER = `(async () => {
  const tick = (ms) => new Promise((r) => setTimeout(r, ms === undefined ? 40 : ms));
  const out = { errors: [], observations: {}, checks: {} };
  window.addEventListener('error', (e) => out.errors.push(String(e.message)));
  window.addEventListener('unhandledrejection', (e) => out.errors.push('rejection: ' + String(e.reason)));

  const root = document.documentElement;
  const token = (name) => getComputedStyle(root).getPropertyValue(name).trim();
  const capPx = () => getComputedStyle(document.getElementById('probe-caption')).fontSize;
  const tuned = window.SottoThemeTune;
  const switcher = window.SottoTheme;
  if (!tuned || !switcher) {
    out.checks.api_present = false;
    return out;
  }
  out.checks.api_present = true;
  await tick();

  // ── baseline, READ from the theme ───────────────────────────────────────────
  const base0 = { token: token('--size-caption'), px: capPx() };
  out.observations.baseline = base0;

  // ── wiring ─────────────────────────────────────────────────────────────────
  const gear = document.getElementById('tune-button');
  const controls = document.querySelector('.panel__controls');
  out.observations.gearId = gear ? gear.id : null;
  out.checks.gear_in_controls = !!(gear && controls && gear.parentElement === controls);
  out.checks.gear_before_pause = !!(gear && gear.nextElementSibling
    && gear.nextElementSibling.id === 'panel-pause-button');
  out.checks.hide_is_last = !!(controls && controls.lastElementChild
    && controls.lastElementChild.id === 'hide-button');

  tuned.open();
  await tick(30);
  const dialog = document.getElementById('tune-dialog');
  const panel = document.getElementById('panel');
  out.observations.tuneRows = dialog ? dialog.querySelectorAll('.tune-row').length : 0;
  out.checks.dialog_exists = !!dialog;
  out.checks.dialog_outside_panel = !!(dialog && panel && !panel.contains(dialog));
  out.checks.dialog_open = !!(dialog && dialog.open);
  const closeBtn = document.getElementById('tune-close-button');
  if (closeBtn) closeBtn.click();
  await tick(20);
  out.checks.dialog_closes = !(dialog && dialog.open);

  // ── CASCADE: the edit reaches the painted caption ───────────────────────────
  tuned.set('sizeCaption', 41);
  await tick();
  const edited = { token: token('--size-caption'), px: capPx(),
                   inline: root.style.getPropertyValue('--size-caption') };
  out.observations.edited = edited;
  out.checks.edit_lands_on_html = edited.inline === '41px';
  out.checks.cascade_moves_the_paint = edited.px === '41px';
  out.checks.token_and_paint_agree = edited.token === '41px' && edited.px === '41px';

  // ── ISOLATION: the other theme does not inherit the edit ───────────────────
  switcher.set('theme-2');
  await tick();
  const other = { theme: root.dataset.theme, token: token('--size-caption'), px: capPx() };
  out.observations.otherTheme = other;
  out.checks.switched = other.theme === 'theme-2';
  out.checks.isolation = other.token !== '41px' && other.px !== '41px';
  out.checks.other_theme_owns_the_value = other.token === other.px;
  out.checks.no_inline_on_the_other_theme = root.style.getPropertyValue('--size-caption') === '';

  // ── MEMORY: coming back restores this theme's edit ─────────────────────────
  switcher.set('theme-1');
  await tick();
  const back = { theme: root.dataset.theme, token: token('--size-caption'), px: capPx() };
  out.observations.backAgain = back;
  out.checks.memory = back.token === '41px' && back.px === '41px';

  // ── BASELINE READ: restore returns what the THEME declares ─────────────────
  tuned.resetTheme();
  await tick();
  const after = { token: token('--size-caption'), px: capPx(),
                  inline: root.style.getPropertyValue('--size-caption') };
  out.observations.afterReset = after;
  out.checks.reset_returns_the_theme_value = after.token === base0.token && after.px === base0.px;
  out.checks.reset_clears_the_inline = after.inline === '';

  // ── COLOUR: accent, swatch and halo move TOGETHER, alpha preserved ─────────
  const alphaOf = (v) => {
    const m = /rgba\\(([^)]+)\\)/.exec(v || '');
    if (!m) return null;
    const p = m[1].split(/[\\s,]+/).filter(Boolean);
    return p.length === 4 ? parseFloat(p[3]) : null;
  };
  const halo0 = token('--accent-soft');
  tuned.set('accent', '#ff0000');
  await tick();
  const acc = { accent: token('--accent'), swatch: token('--theme-swatch'),
                halo: token('--accent-soft'), line: token('--line') };
  out.observations.accent = acc;
  out.checks.accent_written = acc.accent === '#ff0000';
  out.checks.swatch_follows_the_accent = acc.swatch === '#ff0000';
  out.checks.halo_follows_the_accent = /^rgba\\(255,\\s*0,\\s*0,/.test(acc.halo);
  out.checks.halo_keeps_the_theme_alpha = alphaOf(acc.halo) === alphaOf(halo0);
  out.checks.hairline_follows_the_accent = /^rgba\\(255,\\s*0,\\s*0,/.test(acc.line);

  // ── OFF SWITCH: 0ms is a value, not an absence ─────────────────────────────
  tuned.set('typeStep', 0);
  await tick();
  out.observations.typeStep = token('--type-step');
  out.checks.zero_is_written = out.observations.typeStep === '0ms';

  tuned.resetTheme();
  await tick();
  out.observations.finalToken = token('--size-caption');
  out.checks.final_is_the_theme_value = out.observations.finalToken === base0.token;

  // ── PERSISTENCE: what the store holds, read back through the module ─────────
  out.observations.store = (() => { try { return localStorage.getItem('sotto.theme.tune'); }
                                     catch (e) { return 'THREW:' + e.name; } })();
  out.checks.store_is_json_or_unavailable =
    out.observations.store === null || out.observations.store === 'THREW:SecurityError'
    || typeof out.observations.store === 'string';
  return out;
})()`;

app.disableHardwareAcceleration();

/* Runs INSIDE the page, AFTER the first driver. Where the first driver proves the
 * tuner's cascade on ONE theme, this one sweeps EVERY theme the manifest declares.
 * It exists because the theme set is now generated, and the failure mode of a
 * generated set is not a crash: it is a theme that forgot a token and therefore
 * inherits another design's colour, or a bundle that failed to load so that all
 * themes quietly fall back to `panel.css`'s `:root` defaults. Both look like "a
 * theme I don't like" rather than a bug, and neither is visible in a screenshot.
 *
 * It also drives the TWO CLICKS THE OWNER ASKED FOR through the real listeners —
 * dispatch, not `api.next()` — because the contract is about the buttons. */
const DRIVER_SWEEP = `(async () => {
  const tick = (ms) => new Promise((r) => setTimeout(r, ms === undefined ? 20 : ms));
  const out = { errors: [], observations: {}, checks: {} };
  window.addEventListener('error', (e) => out.errors.push(String(e.message)));
  window.addEventListener('unhandledrejection', (e) => out.errors.push('rejection: ' + String(e.reason)));

  const root = document.documentElement;
  const tok = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const sw = window.SottoTheme;
  const man = window.SottoThemeManifest;
  if (!sw || !man) { out.checks.api_present = false; return out; }
  out.checks.api_present = true;

  const REQUIRED = ['--bg-slab','--bg-slab-strong','--text-primary','--text-secondary',
    '--text-muted','--accent','--accent-soft','--theme-swatch','--line','--line-strong',
    '--radius-sm','--radius-md','--radius-lg','--space-1','--space-2','--space-3',
    '--font-sans','--font-mono','--size-caption','--leading-caption','--weight-caption',
    '--tracking-caption','--caption-upper','--motion-in','--ok','--busy','--error','--idle'];
  const ALIASES = ['--bg','--bg-raised','--text','--text-dim','--text-faint','--radius',
    '--font','--mono','--accent-from','--accent-to'];

  const themes = man.themes || [];
  out.observations.themeCount = themes.length;
  out.checks.manifest_has_the_template_set = themes.length > 5;

  const rows = [];
  const missingByTheme = {};
  const swatchMismatch = [];
  const sizeBad = [];
  const bgValues = new Set();
  for (const t of themes) {
    sw.set(t.name, { persist: false });
    await tick(18);
    const missing = REQUIRED.filter((n) => tok(n) === '')
      .concat(ALIASES.filter((n) => tok(n) === ''));
    if (missing.length) missingByTheme[t.name] = missing;
    const accent = tok('--accent').toLowerCase().replace(/\\s+/g, '');
    const swatch = String(t.swatch || '').toLowerCase().replace(/\\s+/g, '');
    if (/^#[0-9a-f]{3,8}$/.test(accent) && /^#[0-9a-f]{3,8}$/.test(swatch) && accent !== swatch) {
      swatchMismatch.push({ theme: t.name, accent, swatch });
    }
    const size = parseFloat(tok('--size-caption'));
    if (!isFinite(size) || size < 10 || size > 90) {
      sizeBad.push({ theme: t.name, size: tok('--size-caption') });
    }
    bgValues.add(tok('--bg-slab').toLowerCase());
    if (root.dataset.theme !== t.name) out.observations.themeWriteFailed = t.name;
    rows.push({ name: t.name, group: t.group || null, variant: t.variant || null,
                accent: accent, size: tok('--size-caption'),
                font: tok('--font-sans').split(',')[0] });
  }
  out.observations.rows = rows;
  out.checks.every_theme_declares_every_token = Object.keys(missingByTheme).length === 0;
  out.observations.missingByTheme = missingByTheme;
  out.checks.swatch_matches_accent = swatchMismatch.length === 0;
  out.observations.swatchMismatch = swatchMismatch;
  out.checks.caption_size_is_sane = sizeBad.length === 0;
  out.observations.sizeBad = sizeBad;
  out.observations.distinctBackgrounds = bgValues.size;
  /* If the bundle had not loaded, every theme would fall back to ONE value from
   * panel.css's :root. Requiring real variety is what catches a 404. */
  out.checks.themes_are_not_all_the_same =
    bgValues.size >= Math.ceil(themes.length * 0.8);

  /* ── THE OWNER'S TWO CLICKS, through the real listeners ──────────────────── */
  const btn = document.getElementById('theme-button') || document.querySelector('[data-theme-button]');
  out.checks.theme_button_exists = !!btn;
  sw.set(themes[0].name, { persist: false });
  await tick(15);
  if (btn) {
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    await tick(15);
    out.observations.afterLeftClick = root.dataset.theme;
    out.checks.left_click_advances = root.dataset.theme === themes[1].name;
    btn.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
    await tick(15);
    out.observations.afterRightClick = root.dataset.theme;
    out.checks.right_click_goes_back = root.dataset.theme === themes[0].name;
    sw.set(themes[0].name, { persist: false });
    await tick(10);
    btn.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
    await tick(15);
    out.checks.right_click_wraps_to_the_last = root.dataset.theme === themes[themes.length - 1].name;
  }
  out.checks.previous_api_walks_back = (() => {
    sw.set(themes[1].name, { persist: false });
    return sw.previous() === themes[0].name;
  })();

  /* ── the picker: opened by the KEYBOARD path (right-click is taken now) ──── */
  if (btn) {
    btn.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
  }
  await tick(30);
  const picker = document.querySelector('.theme-picker');
  const options = document.querySelectorAll('.theme-picker__option');
  const variantBadges = document.querySelectorAll('.theme-picker__variant');
  const headings = document.querySelectorAll('.theme-picker__group');
  const wantVariants = themes.filter((t) => t.variant).length;
  /* ONE HEADING PER GROUP — counted by DISTINCT 'group', not by 'groupLabel', because
   * the generator writes the label only on the first member and a group whose members
   * drifted apart would then be counted as one heading while the picker drew two.
   * (No backticks in this comment: it lives INSIDE a template literal, and a stray
   * backtick closes the driver. That mistake has cost two runs already.) */
  const wantHeadings = new Set(themes.filter((t) => t.group).map((t) => t.group)).size;
  out.observations.picker = { options: options.length, variantBadges: variantBadges.length,
                              headings: headings.length, wantVariants: wantVariants,
                              wantHeadings: wantHeadings,
                              maxHeight: picker ? getComputedStyle(picker).maxHeight : null };
  out.checks.picker_opens_on_the_keyboard = !!picker && picker.hidden === false;
  out.checks.picker_lists_every_theme = options.length === themes.length;
  /* '> 0' IS PART OF THE CHECK, not decoration. With only the five original
   * themes both counts are 0, and '0 === 0' would report a green for a feature
   * that rendered NOTHING — a gate that supplies the thing it then finds. The
   * owner asked for A/B/C variants to exist; a run that finds none has not
   * verified them, so it must not pass. */
  out.checks.picker_shows_every_variant_badge = wantVariants > 0
    && variantBadges.length === wantVariants;
  out.checks.picker_shows_every_group_heading = wantHeadings > 0
    && headings.length === wantHeadings;
  /* With the whole set in one list, an unscrolled picker runs off a 900 px window
   * and its tail cannot be clicked. */
  out.checks.picker_is_scroll_capped = !!picker
    && getComputedStyle(picker).maxHeight !== 'none'
    && getComputedStyle(picker).overflowY === 'auto';
  return out;
})()`;

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    width: 380,
    height: 900,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  try {
    await win.loadFile(PAGE);
    const result = await win.webContents.executeJavaScript(DRIVER, true);
    const sweep = await win.webContents.executeJavaScript(DRIVER_SWEEP, true);
    const checks = Object.assign({}, result.checks, sweep.checks);
    const errors = [].concat(result.errors || [], sweep.errors || []);
    const failed = Object.keys(checks).filter((k) => checks[k] !== true);
    const ok = failed.length === 0 && errors.length === 0 && result.ok !== false;
    console.log('RESULT ' + JSON.stringify({
      ok, failed, errors,
      checks,
      tuner: result.observations,
      sweep: sweep.observations,
      observedBackgrounds: sweep.observedBackgrounds,
    }, null, 2));
    console.log(ok ? 'VERDICT: PASS' : 'VERDICT: FAIL');
    app.exit(ok ? 0 : 1);
  } catch (err) {
    console.log('RESULT ' + JSON.stringify({ ok: false, error: String(err && err.stack || err) }));
    console.log('VERDICT: FAIL');
    app.exit(1);
  }
});

app.on('window-all-closed', () => app.exit(1));
