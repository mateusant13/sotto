#!/usr/bin/env node
/* SOTTO - the SHARED PANEL CONTRACT, measured on the real page in every theme.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The owner's 2026-11-09 contract is ONE composition for every selectable
 * design, not a fix in the themes somebody happened to open:
 *
 *   * the right/bottom panel uses the space it has (no bottom void),
 *   * the tools row (search + folder) stays ON SCREEN above the feed, and a
 *     feed shorter than the panel ends on the floor instead of leaving a void,
 *   * it scrolls but shows NO scrollbar,
 *   * settings sits immediately left of close,
 *   * search is a glyph that reveals the field on demand,
 *   * no demo circles around the stamp,
 *   * every screen caption -- Ctrl+Space included -- carries the design's own
 *     background, while the TEXT identity stays the design's own.
 *
 * `theme-caption-identity-oracle.py` already proves the two numbers INSIDE the
 * `HISTORY-LEGIBILITY` block of `panel-unified.css`; it parses a file. This
 * oracle is the other half: it opens `app/panel/panel.html` in a private,
 * headless browser (no owner screen, no owner profile, no synthetic Windows
 * input), enumerates the REAL picker manifest, switches to EVERY entry and reads
 * COMPUTED geometry, computed paint and real scrolling.
 *
 * WHAT IS AN ARM AND WHAT IS NOT
 * ------------------------------
 * Arms are relations, never fixed pixels: `menu.right + gap == hide.left`,
 * `hide.right == panelWidth - 14`, `status.top - history.bottom <= 26`,
 * `scrollbar-width == none` while `scrollTop` still moves, `PageDown` moves the
 * same box the wheel resolves, etc. The one place a
 * pixel appears is the row's own inset, read from the same theme.
 *
 * INVENTORY (the 45 vs 65 / skin question, answered from the manifests)
 * ---------------------------------------------------------------------
 * The picker is `SottoThemeManifest.themes` (themes.js + the two zip fragments
 * push into it): 59 entries. 45 of them are generated CSS themes
 * (`:root[data-theme='…']` in theme-1..5.css, cinematic.css, panel-designs.css,
 * zipc-panels.css) and 20 are frozen skins (`SOTTO_SKINS.themes`), 6 of which
 * are the SAME id -- so 45 + 20 - 6 = 59. Every picker entry must resolve to a
 * CSS block OR a skin fragment set, every CSS id must be selectable, and every
 * skin must be discoverable: a theme that exists and cannot be chosen, or is
 * chosen and has nothing to paint, is a FAIL that names the id.
 *
 * USAGE
 *   node _main/panel-themes-oracle.mjs [--json out.json] [--only id,id]
 *   node _main/panel-themes-oracle.mjs --neg-arm
 *
 * EXIT CODE: 0 = every arm passed; 1 = at least one failed.
 * `--neg-arm` copies `app/panel` to a temp dir, plants eight independent
 * mutations, and REQUIRES each to be caught (exit 1 with `NEG-ARM: PASS`);
 * an uncaught mutant exits 0 with `NEG-ARM: FAIL`.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..');
const argv = process.argv.slice(2);
function argOf(flag, fallback) {
  const i = argv.indexOf(flag);
  if (i < 0 || i + 1 >= argv.length) return fallback;
  return argv[i + 1];
}
const PANEL_DIR = path.resolve(argOf('--panel-dir', path.join(REPO, 'app', 'panel')));
const JSON_OUT = argOf('--json', '');
const ONLY = argOf('--only', '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const NEG = argv.includes('--neg-arm');

const ROWS = 60;
const ROW_INSET = 14; // the row's right inset, `panel-unified.css`

/* ══════════════════════════════════════════════════════════════════════════
   1. INVENTORY - read from the manifests the page itself reads
   ══════════════════════════════════════════════════════════════════════════ */

function loadManifests(dir) {
  const ctx = { console };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['themes/themes.js', 'themes/panel-designs.js',
    'themes/zipc-panels.js', 'skins/skins.js']) {
    const p = path.join(dir, f);
    if (!fs.existsSync(p)) return { error: `missing manifest ${f}` };
    try {
      vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, { filename: f });
    } catch (err) {
      return { error: `${f}: ${err.message}` };
    }
  }
  return {
    manifest: ctx.SottoThemeManifest || null,
    skins: ctx.SOTTO_SKINS || null,
    skinHtml: ctx.SOTTO_SKIN_HTML || null,
  };
}

/** Every `:root[data-theme='x']` block in every shipped stylesheet. */
function cssThemeIndex(dir) {
  const themesDir = path.join(dir, 'themes');
  const out = new Map(); // id -> Set(file)
  if (!fs.existsSync(themesDir)) return out;
  for (const file of fs.readdirSync(themesDir)) {
    if (!file.endsWith('.css')) continue;
    const rel = `themes/${file}`;
    const text = fs.readFileSync(path.join(themesDir, file), 'utf8');
    const re = /:root\[data-theme\s*=\s*['"]([^'"]+)['"]\]/g;
    let m;
    while ((m = re.exec(text))) {
      if (!out.has(m[1])) out.set(m[1], new Set());
      out.get(m[1]).add(rel);
    }
  }
  return out;
}

function inventory(dir) {
  const loaded = loadManifests(dir);
  if (loaded.error) return { ok: false, problems: [loaded.error], entries: [], counts: {} };
  const { manifest, skins, skinHtml } = loaded;
  const problems = [];
  if (!manifest || !Array.isArray(manifest.themes)) {
    return { ok: false, problems: ['SottoThemeManifest.themes missing'], entries: [], counts: {} };
  }
  const css = cssThemeIndex(dir);
  const picker = manifest.themes;
  const names = picker.map((e) => e.name);
  const seen = new Set();
  const fragmentFilesMissing = new Set();
  for (const name of names) {
    if (!name) problems.push('a picker entry has no `name`');
    else if (seen.has(name)) problems.push(`duplicate picker id: ${name}`);
    seen.add(name);
  }

  const entries = [];
  for (const entry of picker) {
    const name = entry.name;
    const file = entry.file || '';
    const fileOk = Boolean(file) && fs.existsSync(path.join(dir, file));
    const cssFiles = css.get(name) || new Set();
    const hasCss = fileOk && cssFiles.has(file);
    const skin = skins && skins.themes ? skins.themes[name] : null;
    let hasSkin = false;
    if (skin) {
      /* WHAT SHIPS IS `skins/skins.js`: `skin-host.js` reads the four fragments
       * from `SOTTO_SKIN_HTML` at mount time, never from the disk files. The
       * `.html` files beside it are the vendor source, so a missing one does not
       * break a design -- it is counted separately below, not treated as an
       * unloaded theme. A key that is not in the manifest IS an unloaded theme. */
      const frag = skinHtml && skinHtml[`${skin.zip}/${skin.design}`];
      const fragOk = frag && ['caption', 'chrome', 'panel', 'stage']
        .every((k) => typeof frag[k] === 'string' && frag[k].length > 0);
      hasSkin = Boolean(fragOk);
      if (!hasSkin) problems.push(`skin fragments missing from skins.js: ${name} (${skin.zip}/${skin.design})`);
      for (const k of ['caption', 'chrome', 'panel', 'stage']) {
        if (!fs.existsSync(path.join(dir, 'skins', skin.zip, `${skin.design}.${k}.html`))) {
          fragmentFilesMissing.add(`${skin.zip}/${skin.design}.${k}.html`);
        }
      }
    }
    /* A skin-only entry carries no `file` -- the design is the frozen mockup.
     * An entry that NAMES a stylesheet must have it; that is the difference
     * between "skin-backed on purpose" and "a path that rotted". */
    if (file && !fileOk) problems.push(`picker entry names a stylesheet that does not exist: ${name} -> ${file}`);
    if (!file && !hasSkin) problems.push(`picker entry names no stylesheet and has no skin: ${name}`);
    if (!hasCss && !hasSkin) problems.push(`picker entry has no design: ${name} (no :root block in ${file}, no skin)`);
    entries.push({ name, file, label: entry.label || '', css: hasCss, skin: hasSkin });
  }

  /* A DESIGN THAT PAINTS AND CANNOT BE CHOSEN IS INVISIBLE WORK. */
  for (const id of css.keys()) {
    if (!seen.has(id)) problems.push(`stylesheet defines an id the picker cannot select: ${id} (${[...css.get(id)].join(', ')})`);
  }
  for (const id of Object.keys((skins && skins.themes) || {})) {
    if (!seen.has(id)) problems.push(`skin exists and the picker cannot select it: ${id}`);
  }

  const cssIds = [...css.keys()].filter((id) => seen.has(id));
  const skinIds = Object.keys((skins && skins.themes) || {}).filter((id) => seen.has(id));
  const dual = cssIds.filter((id) => skinIds.includes(id));
  /* THE VENDOR WALLPAPERS ARE NOT SHIPPED, AND THAT IS MEASURED HERE RATHER
   * THAN DISCOVERED IN A SCREENSHOT. Every frozen stage fragment references
   * `img/<id>.jpg`; this tree has no `app/panel/img` at all, so the mockup's
   * photo backdrop is a flat colour. It does NOT touch the caption contract --
   * the caption bed is the design's `--cap-bg` colour, which is measured by the
   * `caption-plate` arm on every theme -- so it is reported as a count, not as a
   * failing arm, and never invented back. */
  const missingImages = new Set();
  const skinsRoot = path.join(dir, 'skins');
  if (fs.existsSync(skinsRoot)) {
    for (const zip of fs.readdirSync(skinsRoot)) {
      const zd = path.join(skinsRoot, zip);
      if (!fs.statSync(zd).isDirectory()) continue;
      for (const f of fs.readdirSync(zd)) {
        if (!f.endsWith('.stage.html')) continue;
        const text = fs.readFileSync(path.join(zd, f), 'utf8');
        const re = /img\/[\w.-]+\.(?:jpg|jpeg|png|webp)/g;
        let m;
        while ((m = re.exec(text))) {
          if (!fs.existsSync(path.join(dir, m[0]))) missingImages.add(m[0]);
        }
      }
    }
  }
  return {
    ok: problems.length === 0,
    problems,
    entries,
    missingImages: [...missingImages].sort(),
    fragmentFilesMissing: [...fragmentFilesMissing].sort(),
    counts: {
      picker: names.length,
      css: cssIds.length,
      skin: skinIds.length,
      dual: dual.length,
      skinOnly: skinIds.length - dual.length,
    },
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   2. THE PAGE - private context, headless, no owner profile
   ══════════════════════════════════════════════════════════════════════════ */

function at(msAgo, text) {
  const d = new Date(Date.now() - msAgo);
  const p = (n) => String(n).padStart(2, '0');
  return {
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
    text,
    path: null,
  };
}
const WORDS = 'banana pera manga uva abacaxi morango goiaba pitanga carambola jabuticaba caju';
const ENTRIES = Array.from({ length: ROWS }, (_, i) => at((ROWS - i) * 60000, `${WORDS} ${i + 1}`));

async function openPanel(browser, dir) {
  const ctx = await browser.newContext({ viewport: { width: 380, height: 900 } });
  await ctx.addInitScript((rows) => {
    const target = {
      setLiveEnabled(v) { return { liveEnabled: v }; },
      setTranslationTarget() {},
      getStats() { return { stats: { peak: 0.4, blocks: 128 } }; },
      onStats() { return () => {}; },
      onCaption() { return () => {}; },
      onStatus() { return () => {}; },
      setPanelSurface() {}, replyInfo() {}, setTheme() {},
      getTheme() { return document.documentElement.dataset.theme || 'theme-1'; },
      setPause() {}, pointerInteractive() {},
      externalCaptions() { return []; }, onExternalCaptions() { return () => {}; },
      /* The deferred-asset loader asks the shell for the real bytes; a resolved
       * promise is its "confirmed" signal. Nothing else in the stub needs it. */
      dispatch() { return Promise.resolve(); },
      history: {
        append() {},
        reveal() {},
        search() { return Promise.resolve({ hits: [] }); },
        tail() { return Promise.resolve({ entries: rows, root: 'H:/sotto/history' }); },
        root() { return Promise.resolve({ root: 'H:/sotto/history', canonicalProducer: 'test' }); },
      },
    };
    window.sotto = new Proxy(target, { get: (t, k) => (k in t ? t[k] : () => {}) });
    try { window.localStorage.setItem('sotto.theme', 'theme-1'); } catch (err) { void err; }
  }, ENTRIES);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('requestfailed', (r) => errors.push(`requestfailed ${r.url()} (${r.failure() && r.failure().errorText})`));
  await page.goto(pathToFileURL(path.join(dir, 'panel.html')).href, { waitUntil: 'load' });
  await page.waitForFunction(
    (n) => document.querySelectorAll('#history-list .hist').length >= n,
    ROWS,
    { timeout: 20000 },
  );
  await page.waitForFunction(() => Boolean(window.SottoBrand), null, { timeout: 5000 })
    .catch(() => {});
  /* THE DEFERRED DESIGN ASSETS ARE LOADED HERE, ON PURPOSE.
   *
   * In the app they arrive through the shell's `LazyAssetGate` (the page asks,
   * pywebview confirms, the element is injected). This oracle has no shell, and
   * the loader's own fallback waits 2 s per URL for a channel that will never
   * exist -- 40 themes x 2 s of nothing, in a gate that has to run in the
   * battery. The loader has its own coverage; what is measured HERE is the
   * composition of the designs, so the same four resources are injected in the
   * same documented order (`lazy-assets.js`: cinematic -> skins.js ->
   * skin-host.js -> skin-layout.css, then panel-designs). */
  const loads = await page.evaluate(async () => {
    const load = (tag, attrs) => new Promise((resolve) => {
      const el = document.createElement(tag);
      for (const k of Object.keys(attrs)) el.setAttribute(k, attrs[k]);
      el.onload = () => resolve(true);
      el.onerror = () => resolve(false);
      document.head.appendChild(el);
    });
    const out = {};
    out.cinematic = await load('link', { rel: 'stylesheet', href: 'themes/cinematic.css' });
    out.designs = await load('link', { rel: 'stylesheet', href: 'themes/panel-designs.css' });
    out.skins = await load('script', { src: 'skins/skins.js' });
    out.host = await load('script', { src: 'skin-host.js' });
    out.layout = await load('link', { rel: 'stylesheet', href: 'skin-layout.css' });
    return out;
  });
  /* A DEFERRED ASSET THAT DID NOT LOAD IS A FAILURE, NOT A NOTE. Measured before
   * this line existed: with `themes/cinematic.css` missing from the copy, the
   * page keeps the base theme, `data-theme` still reads back the attribute the
   * measure just wrote, and every relation arm (which the unified sheet satisfies
   * by itself) passed -- the gate was green on 10 themes that had not painted. */
  const failedLoads = Object.keys(loads).filter((k) => !loads[k]);
  if (failedLoads.length) {
    throw new Error(`deferred asset failed to load: ${failedLoads.join(',')} ${JSON.stringify(loads)}`);
  }
  await page.waitForTimeout(120);
  return { ctx, page, errors };
}

/* ══════════════════════════════════════════════════════════════════════════
   3. ONE THEME, MEASURED
   ══════════════════════════════════════════════════════════════════════════ */

async function measure(page, id, hasSkin) {
  await page.evaluate((theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    void document.body.offsetWidth;
  }, id);
  /* The skin mounts asynchronously (its host follows the attribute), and the
   * brand bridge paints on a 120 ms timer. Both are observed, never slept on
   * blindly: the arms read the state that is on screen. */
  await page.waitForFunction(({ theme, skin }) => {
    const on = document.body.getAttribute('data-skin-theme') || '';
    if (skin) return on === theme;
    return on !== theme;
  }, { theme: id, skin: hasSkin }, { timeout: 20000 }).catch(() => {});
  /* A SKIN THAT NEVER MOUNTED IS NOT A THEME THAT PASSED. The wait above swallows
   * its timeout, so the mount state is read back and becomes an arm of its own
   * (`skin-mounted`); without it a skin-only id silently measures the previous CSS
   * theme and every relation still holds. */
  const skinMounted = await page.evaluate(
    (skin) => !skin || (document.body.getAttribute('data-skin-theme') || '') === skin,
    hasSkin ? id : '',
  );
  await page.evaluate(() => { if (window.SottoBrand && window.SottoBrand.push) window.SottoBrand.push(); });
  await page.waitForTimeout(220);
  const data = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const box = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
    };
    const panel = q('.panel');
    const row = q('.panel__controls');
    const menu = q('#menu-button');
    const hide = q('#hide-button');
    const hist = q('.history');
    const histBody = q('.history__body');
    const histList = q('.history__list');
    const status = q('#status');
    const tools = q('.history__tools');
    const input = q('#history-search');
    const timeEl = q('#history-list .hist .hist__time');
    const histText = q('#history-list .hist .hist__text');
    const capText = q('#brand-probe .caption--provisional .caption__text');
    const col = q('#caption-float .caption-float__col');
    const cs = (el, pseudo) => (el ? window.getComputedStyle(el, pseudo || null) : null);
    const bodyStyle = cs(histBody);
    const listStyle = cs(histList);
    /* THE SCROLLER IS RESOLVED, NOT ASSUMED (measured 2026-11-09). The body was
     * the scroller until then, and the tools row lived INSIDE it -- so the feed's
     * pin to the newest line pushed the search glyph to `top=-3940px`, off screen.
     * The layout now scrolls the LIST and keeps the tools in a row that does not
     * scroll with the feed.
     * This resolves the element the product itself resolves
     * (`panel.js historyScroller`): nearest `overflow:auto|scroll` ancestor,
     * preferring the one whose content actually overflows. A gate that hard-codes
     * `.history__body` measures a box the wheel no longer moves. */
    const resolveScroller = () => {
      let nearest = null;
      for (let node = histList; node && node !== document.body && node !== document.documentElement;
        node = node.parentElement) {
        const y = cs(node).overflowY;
        if (y !== 'auto' && y !== 'scroll' && y !== 'overlay') continue;
        if (!nearest) nearest = node;
        if (node.scrollHeight > node.clientHeight + 1) return node;
      }
      return nearest;
    };
    const feed = resolveScroller();
    let scrollMoved = 0;
    let scrollable = false;
    if (feed) {
      const before = feed.scrollTop;
      scrollable = feed.scrollHeight > feed.clientHeight + 20;
      feed.scrollTop = 40;
      scrollMoved = feed.scrollTop;
      feed.scrollTop = before;
    }
    const order = row
      ? [...row.children]
        .filter((el) => el.getBoundingClientRect().width > 0)
        .map((el) => ({ id: el.id || el.className, left: el.getBoundingClientRect().left }))
        .sort((a, b) => a.left - b.left)
      : [];
    const cap = cs(capText);
    return {
      theme: document.documentElement.getAttribute('data-theme'),
      brand: document.documentElement.getAttribute('data-brand'),
      panel: box(panel),
      row: box(row),
      menu: box(menu),
      hide: box(hide),
      hist: box(hist),
      histBody: box(histBody),
      histListBox: box(histList),
      lastRowBox: histList && histList.lastElementChild ? box(histList.lastElementChild) : null,
      toolsBox: box(tools),
      status: box(status),
      menuInRow: Boolean(menu && row && menu.parentElement === row),
      paintedOrder: order,
      scrollbarWidth: bodyStyle ? bodyStyle.scrollbarWidth : '',
      webkitScrollbar: histBody ? cs(histBody, '::-webkit-scrollbar').width : '',
      overflowY: feed ? cs(feed).overflowY : '',
      scroller: feed ? (feed.id || String(feed.className || feed.tagName)) : 'none',
      listScrollbarWidth: listStyle ? listStyle.scrollbarWidth : '',
      listWebkitScrollbar: histList ? cs(histList, '::-webkit-scrollbar').width : '',
      scrollable,
      scrollMoved,
      voidGap: (status && hist) ? status.getBoundingClientRect().top - hist.getBoundingClientRect().bottom : null,
      statusBottomGap: (status && panel)
        ? panel.getBoundingClientRect().bottom - status.getBoundingClientRect().bottom : null,
      searchDisplay: input ? cs(input).display : 'absent',
      searchClass: Boolean(tools && tools.classList.contains('is-searching')),
      circles: {
        present: Boolean(timeEl),
        before: timeEl ? cs(timeEl, '::before').content : '',
        after: timeEl ? cs(timeEl, '::after').content : '',
        avatars: document.querySelectorAll('[data-skin-avatar]').length,
      },
      plate: col ? cs(col).backgroundColor : 'absent',
      plateVar: window.getComputedStyle(document.documentElement)
        .getPropertyValue('--brand-plate').trim(),
      /* THE DESIGN'S OWN BED, read from the same elements brand-bridge reads
       * (`readRow` on the probe's provisional row, `panelBase()` on main.panel,
       * `--bg-slab` on the root, plus the skins' `--cap-bg`). The plate arm
       * re-derives the expected colour from these, so "one generic plate" cannot
       * pass: a hard-coded bed would have to equal every theme's own mix. */
      bed: {
        rowBg: (() => {
          const probe = document.getElementById('brand-probe');
          const live = probe ? probe.querySelector('.caption--provisional') : null;
          return live ? cs(live).backgroundColor : 'absent';
        })(),
        panelBg: (() => {
          const el = document.querySelector('main.panel') || document.body;
          return el ? cs(el).backgroundColor : 'absent';
        })(),
        /* FROM `body`, exactly where brand-bridge reads it (a theme may declare
         * `--bg-slab` on the surface, not on the root), with the root as a
         * fallback so a design that declares it there still resolves. */
        slab: (window.getComputedStyle(document.body).getPropertyValue('--bg-slab')
          || window.getComputedStyle(document.documentElement).getPropertyValue('--bg-slab')).trim(),
        capBg: (window.getComputedStyle(document.body).getPropertyValue('--cap-bg')
          || window.getComputedStyle(document.documentElement).getPropertyValue('--cap-bg')).trim(),
        /* A SKIN'S BED LIVES INSIDE ITS SHADOW ROOT (`background: var(--cap-bg)` on
         * the fragment's own caption box), where `getComputedStyle(document.body)`
         * cannot see it. The colours the skin itself paints are collected here, so
         * the plate arm can still require the plate to be one of THAT design's
         * colours instead of any opaque rectangle. */
        skinDebug: (() => {
          const host = document.getElementById('skin');
          return {
            host: Boolean(host),
            hidden: host ? host.hidden : null,
            light: host ? host.querySelectorAll('*').length : -1,
            shadow: host && host.shadowRoot ? host.shadowRoot.querySelectorAll('*').length : -1,
            capEls: document.querySelectorAll('.skin__caption').length,
            bodySkin: document.body.getAttribute('data-skin-theme') || '',
          };
        })(),
        skinColors: (() => {
          /* THE SKIN'S OWN BEDS, wherever the host put them: `#skin` is a shadow
           * root in this build, but the same markup can mount in the light DOM, and
           * a walk that only looks in `shadowRoot` misses every skin that did.
           * Both are walked, and only inside the skin host -- the panel's own
           * background is not a caption bed. */
          const out = [];
          const collect = (scope) => {
            if (!scope) return;
            for (const node of scope.querySelectorAll('*')) {
              const bg = window.getComputedStyle(node).backgroundColor;
              if (bg && !/,\s*0\)$/.test(bg) && bg !== 'transparent') out.push(bg);
              if (out.length >= 400) return;
            }
          };
          const host = document.getElementById('skin');
          collect(host);
          if (host && host.shadowRoot) collect(host.shadowRoot);
          return out;
        })(),
      },
      capFace: cap ? {
        family: cap.fontFamily,
        size: cap.fontSize,
        weight: cap.fontWeight,
        transform: cap.textTransform,
        color: cap.color,
      } : null,
      histFont: histText ? parseFloat(cs(histText).fontSize) : null,
    };
  });

  /* SEARCH IS A GLYPH UNTIL ASKED (owner, 2026-11-07/09). Measured as a
   * transition: hidden -> a real click reveals and focuses it -> Escape hides it
   * and clears the query. A field that is merely "not visible" but still holds
   * focus would fail the focus half. */
  data.search = { before: data.searchDisplay };
  data.search.revealed = await page.evaluate(() => {
    const btn = document.getElementById('history-search-button');
    if (!btn) return { ok: false, why: 'no button' };
    btn.click();
    const tools = document.querySelector('.history__tools');
    const input = document.getElementById('history-search');
    const shown = Boolean(tools && tools.classList.contains('is-searching'));
    const style = input ? window.getComputedStyle(input) : null;
    const visible = Boolean(style && style.display !== 'none' && input.getBoundingClientRect().width > 0);
    const focused = document.activeElement === input;
    return { ok: shown && visible && focused, shown, visible, focused };
  });
  data.search.hidden = await page.evaluate(() => {
    const input = document.getElementById('history-search');
    if (input) {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    }
    const tools = document.querySelector('.history__tools');
    const closed = !(tools && tools.classList.contains('is-searching'));
    const style = input ? window.getComputedStyle(input) : null;
    return { ok: closed && Boolean(style && style.display === 'none'), closed };
  });

  /* THE KEYS SCROLL IT (owner contract 2026-11-09). With the bar hidden, the
   * keyboard is the affordance that says the box moves. Measured as a real
   * bubbling keydown on the transcript section, against the same scroller the
   * wheel owns -- and `Home` is measured too, so an arm cannot pass on a box that
   * only moves one way. */
  data.keys = await page.evaluate(() => {
    const section = document.getElementById('history');
    const list = document.querySelector('.history__list');
    if (!section || !list) return { ok: false, why: 'no section/list' };
    /* Same resolution as the product (`panel.js historyScroller`): the row list
     * first, then its nearest scrolling ancestor. Reading `.history__body`
     * directly would test a box the keyboard no longer moves after the tools row
     * was lifted out of the scroller. */
    const cs = (el) => window.getComputedStyle(el);
    let body = null;
    for (let node = list; node && node !== document.body && node !== document.documentElement;
      node = node.parentElement) {
      const y = cs(node).overflowY;
      if (y !== 'auto' && y !== 'scroll' && y !== 'overlay') continue;
      if (!body) body = node;
      if (node.scrollHeight > node.clientHeight + 1) { body = node; break; }
    }
    if (!body) return { ok: false, why: 'no scroller' };
    const max = body.scrollHeight - body.clientHeight;
    if (max <= 0) return { ok: false, why: `no travel max=${max}` };
    const send = (key) => section.dispatchEvent(
      new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
    body.scrollTop = 0;
    const start = body.scrollTop;
    const down = send('PageDown');
    const afterDown = body.scrollTop;
    const up = send('PageUp');
    const afterUp = body.scrollTop;
    body.scrollTop = 0;
    const end = send('End');
    const afterEnd = body.scrollTop;
    const home = send('Home');
    const afterHome = body.scrollTop;
    return {
      ok: afterDown > start && afterUp < afterDown && afterEnd > 0 && afterHome < afterEnd,
      start, afterDown, afterUp, afterEnd, afterHome,
      scroller: body.id || String(body.className || body.tagName),
      prevented: { down, up, end, home },
    };
  });
  /* A SHORT FEED IS WHERE THE VOID SHOWS (measured 2026-11-09). The full 60-row
   * feed fills the drawer whatever the row sizing does, so the void only appears
   * once the newest line would otherwise float above empty panel. The list is
   * trimmed to its last three rows and re-measured: the bottom edge of the newest
   * line must be the floor of the box (the owner: *"tira o vazio"*), which is what
   * `margin-top:auto` on the first row buys. This runs LAST, after every other
   * measurement has read the full feed. */
  data.short = await page.evaluate(() => {
    const list = document.querySelector('.history__list');
    if (!list) return { rows: 0, gap: null };
    const keep = 3;
    const rows = [...list.children];
    /* The trimmed rows are DETACHED, not deleted, and put back before this
     * evaluate returns: the page is shared by every CSS theme (a skin gets its own
     * page), so leaving three rows behind would make the next theme measure a feed
     * that cannot scroll. */
    const removed = rows.slice(0, Math.max(0, rows.length - keep));
    removed.forEach((node) => node.remove());
    list.scrollTop = list.scrollHeight;
    const lr = list.getBoundingClientRect();
    const last = list.lastElementChild ? list.lastElementChild.getBoundingClientRect() : null;
    const padBottom = parseFloat(window.getComputedStyle(list).paddingBottom || '0') || 0;
    const out = {
      rows: list.children.length,
      gap: last ? lr.bottom - padBottom - last.bottom : null,
      listHeight: lr.height,
      lastHeight: last ? last.height : null,
    };
    removed.forEach((node) => list.appendChild(node));
    list.scrollTop = list.scrollHeight;
    return out;
  });
  data.skinMounted = skinMounted;
  return data;
}

/* ══════════════════════════════════════════════════════════════════════════
   4. THE ARMS - relations, one verdict each
   ══════════════════════════════════════════════════════════════════════════ */

function parseRgb(text) {
  /* THE TOKENS ARE HEX (`--bg-slab: #060708`), and the computed values are
   * `rgb()`/`rgba()`. A parser that only read the second form made every design's
   * own bed invisible to the plate arm -- measured: `candidates=none` on 35 of 59
   * entries while the plate itself was correct. */
  const hex = /^#([0-9a-f]{3,8})$/i.exec(String(text || '').trim());
  if (hex) {
    const h = hex[1];
    const n = h.length;
    if (n === 3 || n === 4) {
      const v = h.split('').map((c) => parseInt(c + c, 16));
      return { r: v[0], g: v[1], b: v[2], a: n === 4 ? v[3] / 255 : 1 };
    }
    if (n === 6 || n === 8) {
      const v = [];
      for (let i = 0; i < n; i += 2) v.push(parseInt(h.slice(i, i + 2), 16));
      return { r: v[0], g: v[1], b: v[2], a: n === 8 ? v[3] / 255 : 1 };
    }
    return null;
  }
  const m = /rgba?\(([^)]+)\)/.exec(String(text || ''));
  if (!m) return null;
  const parts = m[1].split(/[,/\s]+/).filter(Boolean).map(Number);
  if (parts.length < 3 || parts.slice(0, 3).some((n) => Number.isNaN(n))) return null;
  return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
}

function judge(data, hasSkin) {
  const arms = [];
  const add = (name, ok, detail) => arms.push({ name, ok: Boolean(ok), detail });

  const near = (a, b, tol) => Math.abs(a - b) <= tol;
  const menu = data.menu;
  const hide = data.hide;
  const panel = data.panel;

  /* A1 - SETTINGS IMMEDIATELY LEFT OF CLOSE, inside the row. */
  const gap = (menu && hide) ? hide.left - menu.right : null;
  add('header-adjacent', menu && hide && data.menuInRow && gap >= -0.6 && gap <= 6.6,
    `menuInRow=${data.menuInRow} gap=${gap === null ? 'n/a' : gap.toFixed(1)}`);

  /* A2 - THE ROW IS RIGHT-ANCHORED in the panel, whatever the design. */
  add('row-right-anchored', hide && panel && near(hide.right, panel.right - ROW_INSET, 1.5),
    hide && panel ? `hide.right=${hide.right.toFixed(1)} want=${(panel.right - ROW_INSET).toFixed(1)}` : 'missing');

  /* A3 - NO VISIBLE SCROLLBAR, on both scrollers, both engines. */
  add('no-visible-scrollbar',
    data.scrollbarWidth === 'none' && data.webkitScrollbar === '0px'
    && data.listScrollbarWidth === 'none' && data.listWebkitScrollbar === '0px',
    `body=${data.scrollbarWidth}/${data.webkitScrollbar} list=${data.listScrollbarWidth}/${data.listWebkitScrollbar}`);

  /* A4 - AND IT STILL SCROLLS. `overflow: hidden` is STILL a scroll container
   * for a programmatic `scrollTop` (measured: setting `scrollTop = 40` moves a
   * hidden box), so the arm also reads the computed `overflow-y`: the box must be
   * `auto`/`scroll`, which is what makes the WHEEL work -- the wheel itself is
   * proved by `panel-history-wheel`, not by a synthetic event here. */
  add('scrollable',
    data.scrollable && data.scrollMoved > 0
    && (data.overflowY === 'auto' || data.overflowY === 'scroll'),
    `overflow=${data.scrollable} moved=${data.scrollMoved} overflow-y=${data.overflowY} scroller=${data.scroller}`);

  /* A5 - NO BOTTOM VOID: the feed ends where the status line begins, and the
   * status line sits at the panel's bottom edge. */
  add('no-bottom-void',
    data.voidGap !== null && data.voidGap <= 26 && data.voidGap >= -2
    && data.statusBottomGap !== null && data.statusBottomGap <= 18,
    `void=${data.voidGap === null ? 'n/a' : data.voidGap.toFixed(1)} statusGap=${data.statusBottomGap === null ? 'n/a' : data.statusBottomGap.toFixed(1)}`);

  /* A5-bis - THE TOOLS ROW IS ON SCREEN (measured 2026-11-09). With the drawer
   * itself as the scroller, the feed's pin to its newest line pushed the tools row
   * to `top=-3940px` on theme-1: the magnifier and the folder glyph were painted
   * above the viewport and no mouse could reach them, while `search-on-demand`
   * happily passed because `.click()` does not need an element to be visible. The
   * row must live inside the drawer's box and inside the window. */
  add('search-reachable',
    data.toolsBox !== null && data.hist !== null
    && data.toolsBox.top >= Math.max(0, data.hist.top) - 1
    && data.toolsBox.bottom <= data.hist.bottom + 1,
    data.toolsBox && data.hist
      ? `tools=${data.toolsBox.top.toFixed(1)}..${data.toolsBox.bottom.toFixed(1)} drawer=${data.hist.top.toFixed(1)}..${data.hist.bottom.toFixed(1)}`
      : 'missing');

  /* A5-ter - A SHORT FEED ENDS ON THE FLOOR. The newest line of a three-row feed
   * must sit at the bottom of the box: no empty panel under it. */
  add('short-feed-on-floor',
    data.short && data.short.rows > 0 && data.short.gap !== null
    && data.short.gap <= 8 && data.short.gap >= -2,
    data.short
      ? `rows=${data.short.rows} gapBelowNewest=${data.short.gap === null ? 'n/a' : data.short.gap.toFixed(1)}`
      : 'n/a');

  /* A6 - SEARCH ON DEMAND. */
  add('search-on-demand',
    data.search.before === 'none' && data.search.revealed.ok && data.search.hidden.ok,
    `before=${data.search.before} reveal=${JSON.stringify(data.search.revealed)} close=${JSON.stringify(data.search.hidden)}`);

  /* A7 - NO DEMO CIRCLES AROUND THE STAMP. The stamp must EXIST: an empty string
   * is what a selector that matched nothing returns, and "no circles on an element
   * that is not there" is the shape of a gate that cannot fail. */
  add('no-demo-circles',
    data.circles.present
    && (data.circles.before === 'none' || data.circles.before === 'normal')
    && (data.circles.after === 'none' || data.circles.after === 'normal')
    && data.circles.avatars === 0,
    `present=${data.circles.present} before=${data.circles.before} after=${data.circles.after} avatars=${data.circles.avatars}`);

  /* A8 - THE CAPTION CARRIES ITS DESIGN'S BED, AND THE BED IS THAT DESIGN'S OWN.
   *
   * The first half (opaque) is trivial: `withPlate` guarantees it. The second half
   * is the one the owner asked for -- "not one generic plate" -- so the expected
   * colour is RE-DERIVED here from the design's own tokens, exactly as
   * brand-bridge does it:
   *   1. a bed-strong row wash (alpha >= 0.5) IS the bed, composited over the
   *      panel base at max(alpha, 0.55);
   *   2. otherwise the design's `--bg-slab` becomes the bed, at clamp(alpha,
   *      0.72, 0.86) composited over the panel base;
   *   3. a skin that declares `--cap-bg` bed-strong is accepted as the bed too.
   * A plate that matches NONE of the design's own beds fails, so one hard-coded
   * plate shared by 59 entries cannot pass. */
  const bedOf = (data.bed || {});
  const plate = parseRgb(data.plate);
  const base = (() => {
    const p = parseRgb(bedOf.panelBg);
    return p && p.a > 0.5 ? [p.r, p.g, p.b] : [16, 11, 8];
  })();
  const composite = (c, a) => [0, 1, 2].map((i) => Math.round(
    [c.r, c.g, c.b][i] * a + base[i] * (1 - a)));
  const candidates = [];
  /* brand-bridge's own rule, replicated: any readable row wash (> 0.02) is
   * carried at max(alpha, 0.55) -- so a 9 % tint still yields a bed at 0.55. */
  const row = parseRgb(bedOf.rowBg);
  /* THE WASH ALPHA IS NOT STABLE BETWEEN PAINT AND READ (measured on `Timeline`:
   * `rgba(216,167,232,0.016)` at read time, `0.045` at paint time -- the probe row
   * animates). So the row is not re-composited at a fixed alpha; the plate is
   * required to LIE ON THE LINE between the wash and the panel base, and the alpha
   * that solves each channel must AGREE across channels. Measured margins: a
   * correct plate solves to 0.0446-0.0450 (spread 0.0004); a generic grey plate
   * solves to 0.020/0.058/0.054 (spread 0.038). */
  if (row) {
    const chans = [0, 1, 2]
      .map((i) => ({ row: [row.r, row.g, row.b][i], base: base[i], plate: plate ? [plate.r, plate.g, plate.b][i] : null }))
      .filter((c) => c.plate !== null && Math.abs(c.row - c.base) > 8)
      .map((c) => (c.plate - c.base) / (c.row - c.base));
    if (chans.length >= 2) {
      const spread = Math.max(...chans) - Math.min(...chans);
      const alpha = chans.reduce((a, b) => a + b, 0) / chans.length;
      candidates.push({ rgb: [0, 0, 0], a: 0, alpha, from: `row@${alpha.toFixed(3)}`, spread, solved: true });
    }
  }
  const slab = parseRgb(bedOf.slab);
  if (slab && slab.a > 0.02) {
    const a = Math.min(0.86, Math.max(0.72, slab.a));
    candidates.push({ rgb: composite(slab, a), a, from: 'slab' });
  }
  const capBg = parseRgb(bedOf.capBg);
  if (capBg && capBg.a >= 0.5) candidates.push({ rgb: [capBg.r, capBg.g, capBg.b], a: capBg.a, from: 'cap-bg' });
  /* Every colour the mounted skin paints is a legal bed for that skin: the
   * fragment's own `--cap-bg` is one of them, and a generic plate is not. */
  /* A SKIN'S BED IS COMPOSITED TOO (`skinTokens` reads the caption box's own
   * background and calls `effectiveBg` on it before the plate is painted), so the
   * candidate is the composite at the colour's own alpha with the opacity raised to
   * 0.55 -- the same two numbers as the row path. Measured on `Timeline`: a
   * `rgba(…,0.05)` tint whose plate is (25,18,18). */
  for (const colour of (bedOf.skinColors || [])) {
    const c = parseRgb(colour);
    if (c && c.a > 0.02) {
      candidates.push({ rgb: composite(c, c.a), a: Math.max(c.a, 0.55), from: 'skin', tol: 8 });
    }
  }
  const matched = plate ? candidates.find((c) => (c.solved
    /* THE OPACITY IS PART OF THE RELATION, not a free pass: the plate carries
     * `max(washAlpha, 0.55)`, so a plate whose opacity does not equal that is not
     * this design's bed -- a raw, un-composited wash solves to alpha 1 with spread 0
     * and would otherwise pass while the bed is the wrong colour. */
    ? c.spread <= 0.02 && near(Math.max(c.alpha, 0.55), plate.a, 0.06)
    : c.rgb.every((v, i) => near(v, [plate.r, plate.g, plate.b][i], c.tol || 3))
      && near(c.a, plate.a, 0.06))) : null;
  add('caption-plate', Boolean(plate) && plate.a >= 0.5 && Boolean(matched),
    `plate=${data.plate} alpha=${plate ? plate.a : 'n/a'} bed=${matched ? matched.from : 'NONE'}`
    + ` candidates=${candidates.map((c) => c.from + (c.solved ? '' : ':' + c.rgb.join('/') + '@' + c.a.toFixed(2))).join(' ') || 'none'}`
    + ` row=${bedOf.rowBg} panel=${bedOf.panelBg} slab=${bedOf.slab}`
    + ` skinColors=${(bedOf.skinColors || []).length} dbg=${JSON.stringify(bedOf.skinDebug)}${hasSkin ? ' (skin)' : ''}`);

  /* A9 - AND ITS TEXT IS STILL LEGIBLE at the theme's own size. */
  add('history-text-legible', data.histFont !== null && data.histFont >= 13.4,
    `histFont=${data.histFont}`);

  /* A10 - THE KEYS MOVE IT. Hiding the scrollbar removes the only thing that said
   * the box can move, so the keyboard has to: PageDown down, PageUp back, End to the
   * bottom, Home to the top -- all on the SAME scroller the wheel resolves. */
  add('keyboard-scroll', Boolean(data.keys && data.keys.ok),
    data.keys ? `down=${data.keys.afterDown} up=${data.keys.afterUp} end=${data.keys.afterEnd} home=${data.keys.afterHome}` : 'missing');

  /* A11 - A SKIN THAT DID NOT MOUNT IS NOT A THEME THAT PASSED. The mount wait
   * swallows its timeout; without this arm a skin-only id measures the previous
   * CSS theme and every relation above still holds. */
  add('skin-mounted', !hasSkin || Boolean(data.skinMounted),
    hasSkin ? `mounted=${data.skinMounted}` : 'n/a (css theme)');

  return arms;
}

/* ══════════════════════════════════════════════════════════════════════════
   5. THE RUN
   ══════════════════════════════════════════════════════════════════════════ */

async function run(dir, opts = {}) {
  const inv = inventory(dir);
  const report = { inventory: inv.counts, problems: inv.problems, themes: [], arms: {}, errors: [] };
  report.missingImages = inv.missingImages || [];
  report.fragmentFilesMissing = inv.fragmentFilesMissing || [];
  const only = Array.isArray(opts.only) && opts.only.length ? opts.only : ONLY;
  const entries = inv.entries.filter((e) => !only.length || only.includes(e.name));
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let session = null;
  try {
    session = await openPanel(browser, dir);
    /* THE LIVE ARRAYS, NOT A COPY (measured by review 2): `openPanel` returns the
     * array its page listeners keep pushing into, so a copy freezes the errors known
     * at open time and drops every one raised DURING `measure()` -- including a skin
     * fragment's own `<link href="skins/<zip>/app.css">` failing at mount, which is
     * exactly the "a design that never painted passed" hole this gate exists for. */
    const errorSets = [session.errors];
    const faces = new Set();
    const plates = new Set();
    let page = session.page;
    for (const entry of entries) {
      /* ONE PAGE PER SKIN. A frozen skin is MOUNT-ONCE in the app (its fragment is
       * injected into a shadow root and stays), so switching skins inside one page
       * measures a state the product never shows: measured on `Timeline`, alone it
       * read the skin's own bed and at position 59 it read the plate of the skin
       * before it. A fresh page per skin removes the question instead of widening
       * the arm's tolerance. */
      if (entry.skin) {
        await session.ctx.close();
        session = await openPanel(browser, dir);
        page = session.page;
        errorSets.push(session.errors);
      }
      const data = await measure(page, entry.name, entry.skin);
      const arms = judge(data, entry.skin);
      if (data.capFace) {
        faces.add([data.capFace.family, data.capFace.size, data.capFace.weight,
          data.capFace.transform].join('|'));
      }
      if (data.plate) plates.add(String(data.plate));
      /* THE PAYLOAD THE PAGE ACTUALLY POSTED, kept so the NATIVE consumer can be
       * judged against the same 59 designs instead of a re-derived guess. The
       * overlay never reads the DOM: `_brand_tokens` receives exactly this. */
      const brand = await page.evaluate(() => (window.SottoBrand && window.SottoBrand.last)
        ? window.SottoBrand.last() : null);
      report.themes.push({ id: entry.name, skin: entry.skin, css: entry.css, arms, brand });
      for (const arm of arms) {
        if (!report.arms[arm.name]) report.arms[arm.name] = { pass: 0, fail: 0, failures: [] };
        if (arm.ok) report.arms[arm.name].pass += 1;
        else {
          report.arms[arm.name].fail += 1;
          report.arms[arm.name].failures.push(`${entry.name}: ${arm.detail}`);
        }
      }
    }
    report.faces = faces.size;
    report.plates = plates.size;
    report.pageErrors = errorSets.flat();
  } finally {
    if (session) await session.ctx.close();
    await browser.close();
  }
  report.inventoryOk = inv.ok;
  /* THE FLOOR IS A FLOOR, NOT A TAUTOLOGY: with 59 entries the caption face floor
   * used to be `min(10, entries.length)`, so 49 of them could flatten to one
   * appearance and still pass. The floors are now stated for the real population
   * and fall back to the population size for an `--only` subset. */
  const floor = Math.min(entries.length, 10);
  report.distinctCaptionFaces = (report.faces || 0) >= Math.min(entries.length, Math.max(floor, 30));
  report.distinctPlates = (report.plates || 0) >= Math.min(entries.length, Math.max(floor, 20));
  return report;
}

function printReport(report) {
  const c = report.inventory || {};
  console.log(`THEMES picker=${c.picker} css=${c.css} skin=${c.skin} dual=${c.dual} skinOnly=${c.skinOnly}`);
  if (report.problems.length) {
    console.log(`INVENTORY PROBLEMS ${report.problems.length}`);
    for (const p of report.problems) console.log(`  - ${p}`);
  } else {
    console.log('INVENTORY OK -- every picker entry resolves to a CSS block or a skin, and nothing paints that cannot be chosen');
  }
  if (report.fragmentFilesMissing && report.fragmentFilesMissing.length) {
    console.log(`SKIN-SOURCE missing=${report.fragmentFilesMissing.length} -- vendor .html files absent; the SHIPPED fragments live in skins.js and were measured`);
  }
  if (report.missingImages && report.missingImages.length) {
    console.log(`SKIN-IMAGES missing=${report.missingImages.length} -- the frozen mockups' wallpaper files are not shipped (informational: the caption bed is the design's own --cap-bg colour and IS measured)`);
  }
  const names = Object.keys(report.arms);
  for (const name of names) {
    const arm = report.arms[name];
    console.log(`${arm.fail === 0 ? 'PASS' : 'FAIL'} ${name} pass=${arm.pass} fail=${arm.fail}`);
    for (const f of arm.failures.slice(0, 8)) console.log(`      ${f}`);
    if (arm.failures.length > 8) console.log(`      ... ${arm.failures.length - 8} more`);
  }
  console.log(`CAPTION-FACES distinct=${report.distinctCaptionFaces} (${report.faces || 0} computed tuples)`);
  console.log(`CAPTION-PLATES distinct=${report.distinctPlates} (${report.plates || 0} computed beds)`);
  if (report.pageErrors && report.pageErrors.length) {
    console.log(`PAGE-ERRORS ${report.pageErrors.length}`);
    for (const e of report.pageErrors.slice(0, 5)) console.log(`  ${e}`);
  }
  /* A PAGE ERROR IS A FAILURE -- EXCEPT THE ONE KNOWN, DOCUMENTED MISS: the 20
   * frozen mockups' wallpaper files are not shipped (`img/*.jpg`), which
   * `SKIN-IMAGES missing` already reports as informational. Anything else on the
   * page (a failed stylesheet, a thrown script) fails the gate, because a theme
   * whose sheet did not load is measured against the base theme and passes every
   * relation. */
  const wallpaper = /(img\/[\w.-]+\.(?:jpe?g|png|webp|avif))|(^Failed to load resource: net::ERR_FILE_NOT_FOUND$)/i;
  const fatal = (report.pageErrors || []).filter((e) => !wallpaper.test(String(e)));
  const failed = Object.values(report.arms).reduce((n, a) => n + a.fail, 0);
  const ok = report.inventoryOk && failed === 0 && report.distinctCaptionFaces
    && report.distinctPlates && fatal.length === 0;
  if (fatal.length) {
    console.log(`PAGE-ERRORS FATAL ${fatal.length}`);
    for (const e of fatal.slice(0, 5)) console.log(`  ${e}`);
  }
  console.log(`VERDICT: ${ok ? 'PASS' : 'FAIL'} -- themes=${report.themes.length} arms=${names.length} failed_arms=${failed} fatal_page_errors=${fatal.length}`);
  return ok;
}

/* ══════════════════════════════════════════════════════════════════════════
   6. NEGATIVE ARM - ten independent mutants, each must be caught
   ══════════════════════════════════════════════════════════════════════════ */

/* THE NEGATIVE ARM MEASURES A SAMPLE, AND THAT IS STATED.
 *
 * Every mutant below breaks a mechanism that is shared by all 59 entries: the
 * row's order, the scrollbar paint, the drawer's height, the plate fallback, the
 * stamp's pseudo-element. Running the mutant against all 59 would multiply the
 * neg-arm's cost by fifteen and prove the same relation fifteen more times, so
 * it runs against ONE representative of each design family -- a base theme, a
 * frozen skin, a zip panel-design and a zipc direction. The positive run above
 * is what covers the full inventory. */
const SHORT = ['theme-1', 'cine-adobe', 'pd-tele', 'GlassCards'];

const MUTANTS = [
  {
    name: 'M1 order: settings loses its slot next to close',
    file: 'panel-unified.css',
    find: 'html body[data-surface="panel"] #menu-button { order: 6 !important; }',
    replace: 'html body[data-surface="panel"] #menu-button { order: 0 !important; }',
    expect: 'header-adjacent',
  },
  {
    name: 'M2 scrollbar: the paint is put back',
    file: 'panel-unified.css',
    find: '  overflow: hidden !important;\n  scrollbar-width: none !important;',
    replace: '  overflow: hidden !important;\n  scrollbar-width: auto !important;',
    expect: 'no-visible-scrollbar',
  },
  {
    name: 'M3 scrolling: the list stops scrolling',
    file: 'panel-unified.css',
    find: '{ overflow-y: auto !important; margin: 0 !important;',
    replace: '{ overflow-y: hidden !important; margin: 0 !important;',
    expect: 'scrollable',
  },
  {
    name: 'M4 void: the drawer is capped at 34vh again',
    file: 'panel-unified.css',
    find: 'html body[data-surface="panel"] .history:not(.history--collapsed) {\n  max-height: none !important;',
    replace: 'html body[data-surface="panel"] .history:not(.history--collapsed) {\n  max-height: 34vh !important;',
    expect: 'no-bottom-void',
  },
  {
    name: 'M5 plate: the designed caption bed is disabled',
    file: 'brand-bridge.js',
    find: '    var strong = tokens.rowBgAlpha >= 0.5 && parseColour(tokens.rowBg);',
    replace: '    var strong = true;',
    expect: 'caption-plate',
  },
  {
    name: 'M6 circles: the demo box comes back on the stamp',
    file: 'panel-unified.css',
    find: 'html body[data-surface="panel"] .hist__time::before,\nhtml body[data-surface="panel"] .hist__time::after {\n  content: none !important;',
    replace: 'html body[data-surface="panel"] .hist__time::before,\nhtml body[data-surface="panel"] .hist__time::after {\n  content: "" !important;',
    expect: 'no-demo-circles',
  },
  {
    name: 'M7 inventory: a shipped skin loses its fragments',
    file: 'skins/skins.js',
    find: '"cinematic-2/adobe":',
    replace: '"cinematic-2/adobe-removed":',
    expect: 'inventory',
  },
  {
    /* THE MECHANISM ITSELF, not "the previous version of the file": the call is
     * removed from a COPY, so the mutant cannot rot when panel.js moves on. */
    name: 'M8 keys: the transcript loses its keyboard scroll',
    file: 'panel.js',
    find: 'wireHistoryKeys();\n',
    replace: '',
    expect: 'keyboard-scroll',
  },
  {
    /* The shipped defect of 2026-11-09, re-planted structurally: the drawer
     * becomes the scroller again and the list stops being one, so the tools row
     * travels with the feed and lands off screen. */
    name: 'M9 reach: the drawer goes back to being the scroller',
    file: 'panel-unified.css',
    find: 'html body[data-surface="panel"] .history__body,\nhtml body[data-surface="panel"] .history__list {\n  display: flex !important; flex-flow: column !important;\n  flex: 1 !important; min-height: 0 !important;\n  overflow: hidden !important;\n  scrollbar-width: none !important;\n}\nhtml body[data-surface="panel"] .history__list { overflow-y: auto !important;',
    replace: 'html body[data-surface="panel"] .history__body {\n  display: block !important;\n  flex: 1 !important; min-height: 0 !important;\n  overflow: auto !important;\n  scrollbar-width: none !important;\n}\nhtml body[data-surface="panel"] .history__list { overflow-y: visible !important;',
    expect: 'search-reachable',
  },
  {
    name: 'M10 floor: a short feed floats at the top again',
    file: 'panel-unified.css',
    find: 'html body[data-surface="panel"] .history__list > :first-child { margin-top: auto !important; }',
    replace: 'html body[data-surface="panel"] .history__list > :first-child { margin-top: 0 !important; }',
    expect: 'short-feed-on-floor',
  },
];

function plantMutant(dir, mutant) {
  const p = path.join(dir, mutant.file);
  const raw = fs.readFileSync(p, 'utf8');
  /* THE SHIPPED FILES ARE CRLF (measured: panel-unified.css 511 CRLF / 0 bare
   * LF), so an anchor written with `\n` matches nothing and the mutant would be
   * "not caught" for a reason that has nothing to do with the arm. The anchor is
   * compared on a normalised copy and the file is written back in its own style. */
  const crlf = raw.includes('\r\n');
  const text = crlf ? raw.replace(/\r\n/g, '\n') : raw;
  const at = text.indexOf(mutant.find);
  if (at < 0) return `anchor not found in ${mutant.file}`;
  const out = text.slice(0, at) + mutant.replace + text.slice(at + mutant.find.length);
  fs.writeFileSync(p, crlf ? out.replace(/\n/g, '\r\n') : out, 'utf8');
  return '';
}

async function negativeArm() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-themes-neg-'));
  const results = [];
  let caught = 0;
  try {
    for (const mutant of MUTANTS) {
      const copy = path.join(tmp, 'panel');
      fs.rmSync(copy, { recursive: true, force: true });
      fs.cpSync(PANEL_DIR, copy, { recursive: true });
      const plantError = plantMutant(copy, mutant);
      if (plantError) {
        results.push({ name: mutant.name, ok: false, why: plantError });
        continue;
      }
      const report = await run(copy, { only: SHORT });
      if (mutant.expect === 'inventory') {
        const ok = report.inventoryOk === false;
        results.push({ name: mutant.name, ok, why: ok ? 'inventory refused' : 'inventory accepted the mutant' });
        if (ok) caught += 1;
        continue;
      }
      const arm = report.arms[mutant.expect];
      const ok = Boolean(arm && arm.fail > 0);
      results.push({
        name: mutant.name,
        ok,
        why: arm ? `${mutant.expect} pass=${arm.pass} fail=${arm.fail}` : `${mutant.expect} not measured`,
      });
      if (ok) caught += 1;
    }
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  for (const r of results) console.log(`${r.ok ? 'CAUGHT' : 'NOT-CAUGHT'} ${r.name} -- ${r.why}`);
  const ok = caught === MUTANTS.length;
  console.log(`NEG-ARM: ${ok ? 'PASS' : 'FAIL'} -- ${caught}/${MUTANTS.length} mutants caught`);
  return ok ? 1 : 0;
}

/* ══════════════════════════════════════════════════════════════════════════
   7. MAIN
   ══════════════════════════════════════════════════════════════════════════ */

if (NEG) {
  process.exit(await negativeArm());
} else if (argv.includes('--tokens')) {
  /* DIAGNOSTIC, NOT AN ARM: the tokens the bridge actually posted for the ids in
   * `--only`, so a failing plate can be read at its source instead of guessed. */
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const session = await openPanel(browser, PANEL_DIR);
  for (const id of ONLY) {
    const entry = inventory(PANEL_DIR).entries.find((e) => e.name === id);
    const data = await measure(session.page, id, Boolean(entry && entry.skin));
    const tokens = await session.page.evaluate(() => {
      const t = window.SottoBrand && window.SottoBrand.last ? window.SottoBrand.last() : null;
      return t ? { theme: t.theme, rowBg: t.rowBg, rowBgAlpha: t.rowBgAlpha,
        slabColor: t.slabColor, panelBgColor: t.panelBgColor } : null;
    });
    console.log(`${id} plate=${data.plate} tokens=${JSON.stringify(tokens)}`);
  }
  await session.ctx.close();
  await browser.close();
  process.exit(0);
} else {
  const report = await run(PANEL_DIR);
  const ok = printReport(report);
  if (JSON_OUT) {
    fs.writeFileSync(path.resolve(JSON_OUT), JSON.stringify(report, null, 2), 'utf8');
    console.log(`JSON ${path.resolve(JSON_OUT)}`);
  }
  process.exit(ok ? 0 : 1);
}
