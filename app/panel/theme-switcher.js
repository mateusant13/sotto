/* Sotto — theme switcher.
 *
 * ONE DEPENDENCY-FREE MODULE. It reads the manifest (`themes/themes.js`, loaded
 * BEFORE this file), owns the choice, and switches a theme by writing ONE
 * attribute:
 *
 *     document.documentElement.dataset.theme = 'theme-3'
 *
 * That is the whole mechanism. All five stylesheets are linked at once, every
 * rule in each of them is scoped to `:root[data-theme='theme-N']`, so a switch
 * is one attribute write: no reload, no parse, no network, no flicker, and no
 * per-theme JavaScript. CSS owns an optional <=180 ms colour transition and
 * honours `prefers-reduced-motion`; this module never animates anything.
 *
 * ── IT DOES NOT TOUCH THE CAPTION, STATUS OR HISTORY LOGIC ───────────────────
 * It reads no caption, writes no caption, adds no listener to the live box, and
 * changes no element that carries text. The only element it CREATES is its OWN
 * picker button, and only in the header's control cluster (`.panel__controls`),
 * never inside `.captions`, `.history` or `.status`. If a host page already
 * provides a `#theme-button`, this module BINDS to it instead of creating one.
 *
 * ── TWO MOUNT POINTS, ONE CHOICE (2026-10-08) ────────────────────────────────
 * `.panel__header` is `display:none` on the STRIP surface, so a theme control
 * that exists only inside it is UNREACHABLE the moment the shell opens the
 * strip — the owner would have no way to change the theme there. The strip's
 * control row therefore carries its own `[data-theme-button]` in the markup, and
 * this module wires and paints EVERY element carrying that attribute (plus
 * `#theme-button`). The header button is still the one it creates when the host
 * page has none; the strip button is the host page's. One `paintAll()` keeps
 * them showing the same theme, so they cannot drift.
 *
 * ── PERSISTENCE IS DEFENSIVE ON PURPOSE ─────────────────────────────────────
 * `localStorage` is not guaranteed over `file://` in WebView2: touching it can
 * throw (`SecurityError` / `QuotaExceededError`) or silently be per-document
 * opaque storage. So every access goes through `readStore`/`writeStore`, which
 * swallow a throw and fall back to an in-memory default. The choice works for
 * the session either way; persistence is a bonus, never a precondition.
 */
(function (root) {
  'use strict';

  var STORE_KEY = 'sotto.theme';

  /* The manifest is a sibling script. The inline copy is the fallback for the
   * case where it is missing (a host that only linked this file): it keeps the
   * switcher functional rather than leaving the panel with no theme at all. The
   * labels and swatches are the five design directions' own — the same table as
   * `themes/themes.js`, which is what `<html data-theme>` and the five
   * `themes/theme-N.css` files are keyed to. */
  var MANIFEST = (root && root.SottoThemeManifest) || null;
  var THEMES = (MANIFEST && MANIFEST.themes) || [
    { name: 'theme-1', label: 'Teleprompter', file: 'themes/theme-1.css', swatch: '#f2e9d8' },
    { name: 'theme-2', label: 'Broadcast', file: 'themes/theme-2.css', swatch: '#ff6a55' },
    { name: 'theme-3', label: 'Manuscrito', file: 'themes/theme-3.css', swatch: '#a9c1d9' },
    { name: 'theme-4', label: 'Cinema Card', file: 'themes/theme-4.css', swatch: '#e4b363' },
    { name: 'theme-5', label: 'Instrumento', file: 'themes/theme-5.css', swatch: '#5fd3a7' }
  ];
  var FALLBACK = (MANIFEST && MANIFEST.fallback) || THEMES[0].name;

  var memoryStore = null;

  function readStore() {
    try {
      var v = root.localStorage.getItem(STORE_KEY);
      return typeof v === 'string' ? v : null;
    } catch (err) {
      /* file:// in WebView2, a privacy mode, or a host policy: not an error,
       * just no storage. The in-memory value below is the fallback. */
      return memoryStore;
    }
  }

  function writeStore(name) {
    memoryStore = name;
    /* COUNTED: this is the ONLY place the module persists, and the oracle reads
     * `stat.storeWrites` to prove that hovering never reaches it. */
    stat.storeWrites += 1;
    try {
      root.localStorage.setItem(STORE_KEY, name);
    } catch (err) {
      /* Deliberately silent: the choice still took effect in this document. */
    }
  }

  function known(name) {
    if (!name) return null;
    for (var i = 0; i < THEMES.length; i += 1) {
      if (THEMES[i].name === name) return THEMES[i];
    }
    return null;
  }

  function themeElement() {
    if (root.document && root.document.documentElement) return root.document.documentElement;
    return null;
  }

  function currentTheme() {
    var el = themeElement();
    return (el && el.dataset && el.dataset.theme) || FALLBACK;
  }

  function labelOf(name) {
    var t = known(name);
    return t ? t.label : String(name);
  }

  /* ── the picker ─────────────────────────────────────────────────────────────
   * A button that CYCLES, and a picker dialog that JUMPS. Cycling is the whole
   * interaction the owner asked for ("no painel, vai ter botao de mudar o
   * tema"): one click, next design, instantly. The picker exists because five
   * clicks to reach the one you want is not a control, it is a puzzle — and it
   * is the only reason this module creates a second element.
   */
  var picker = null;

  /* ── the chevron dropdown (RIGHT PANEL, re-anchored 2026-10-12) ────────────
   *
   * ANCHOR — WHICH ELEMENT, AND WHY. The trigger lives in the RIGHT panel's own
   * control cluster, `.panel__controls` (panel.css:281), as `#theme-chevron`: the
   * cluster that already carries the font dial, Pause and Hide, and the place
   * the owner sent every control — *"o terceiro panel, e o da direita. onde deve
   * ter todos os botoes."* It is the ONLY element in the document that opens the
   * list, and the panel surface is the only surface that offers it.
   *
   * WHY IT LEFT THE STRIP (2026-10-12). The first cut anchored on
   * `#strip-theme-chevron`, which was then the only theme control reachable
   * while the strip was the surface in play. The panel lane then shipped the
   * owner's layout (commit `fae207a`): *"o painel de baixo, deve conter apenas o
   * bare minimum"*. The strip keeps ONE theme control — `#strip-theme-button,
   * which cycles next/previous on click and which `panel.html` ships, not this
   * module — and the list moved with the rest of the buttons. Two things hold
   * that in place, because a markup line on its own cannot:
   *   1. THIS MODULE no longer builds a strip chevron. The block that used to
   *      sit at the foot of `ensureChevrons` was deleted in the re-anchor, and
   *      `registerChevron` REFUSES a chevron the strip bar ships. The gate that
   *      pins both halves is `_main/theme-preview-oracle.js` ARM 11/12.
   *   2. `panel.css` hides the trigger AND the list on the strip surface —
   *      `body[data-surface="strip"] #strip-theme-chevron { display: none }` and
   *      `body[data-surface="strip"] .theme-dropdown { display: none
   *      !important }` — so a strip-bar chevron is inert and invisible, and a
   *      dropdown left open does not follow the shell onto the short surface.
   * A chevron the markup ships INSIDE `.panel__controls` is used as-is when the
   * module would otherwise create its own.
   *
   * The dropdown ITSELF (`#theme-dropdown`) is created here and appended to
   * `document.body`, NOT nested in either control: `.panel` has `overflow:
   * hidden` (panel.css:181), so a nested popup is clipped by the panel's own
   * rounded box. Body-level + `position:absolute` + the `z-index:40` the base
   * stylesheet already gives it (panel.css:352) is what lets the list escape the
   * panel. That list's own chrome — `.theme-chevron`, `.theme-dropdown*` — is
   * written in `panel.css`, which `panel.html` links EAGERLY (panel.html:49) and
   * which is NOT one of the assets `lazy-assets.js` gates behind the shell's
   * ask, so the trigger paints and the list opens whether or not the running
   * theme's own stylesheet has arrived yet.
   *
   * Same persist contract as the picker, plus LIVE PREVIEW: hovering (or
   * focusing) an option paints it instantly WITHOUT persisting
   * (`api.set(name, { persist:false })`), clicking (or Enter/Space) COMMITS it
   * through the same `api.set(name)` persist path the cycle button uses, and
   * leaving the dropdown or pressing Escape REVERTS to the committed theme
   * (`api.set(committed, { persist:false })` — the store still holds it, so no
   * write is needed). There is ONE dropdown, and with the strip bare the panel
   * chevron is its only door.
   */
  var chevrons = [];
  var activeChevron = null;
  var dropdown = null;
  var committedTheme = null;
  var previewTheme = null;
  var dropdownOpen = false;

  function ensurePicker(doc) {
    if (picker) return picker;
    picker = doc.createElement('div');
    picker.className = 'theme-picker';
    picker.hidden = true;
    picker.setAttribute('role', 'dialog');
    picker.setAttribute('aria-label', 'Choose a theme');

    var list = doc.createElement('div');
    list.className = 'theme-picker__list';
    list.setAttribute('role', 'group');

    /* THE LIST IS GROUPED AND BADGED (owner, 2026-10-08). He asked for the
     * near-duplicate designs to be shippable as alternatives for A/B/C testing —
     * *"pros que sao bem parecidos, faça outra alternativa, a b c testing"* — and
     * a flat list of thirty names makes two variants of ONE design look like two
     * unrelated themes. So the manifest's `group` becomes a heading and its
     * `variant` becomes the badge, which is what lets him find the pair he wants
     * to compare. Nothing here decides anything: it renders what the manifest
     * says, so a variant that is mislabelled is a manifest bug and not a UI one. */
    var lastGroup = null;
    THEMES.forEach(function (theme) {
      var group = theme.group || null;
      if (group && group !== lastGroup) {
        var head = doc.createElement('div');
        head.className = 'theme-picker__group';
        head.textContent = theme.groupLabel || group;
        list.append(head);
      }
      lastGroup = group;

      var b = doc.createElement('button');
      b.type = 'button';
      b.className = 'theme-picker__option';
      b.dataset.themeChoice = theme.name;
      b.style.setProperty('--theme-swatch', theme.swatch);

      var chip = doc.createElement('span');
      chip.className = 'theme-picker__swatch';
      chip.setAttribute('aria-hidden', 'true');
      b.append(chip);

      var label = doc.createElement('span');
      label.className = 'theme-picker__label';
      label.textContent = theme.label;
      b.append(label);

      if (theme.variant) {
        var badge = doc.createElement('span');
        badge.className = 'theme-picker__variant';
        badge.textContent = theme.variant;
        badge.title = 'Variante ' + theme.variant + ' deste design';
        b.append(badge);
      }

      b.addEventListener('click', function () {
        api.set(theme.name);
        closePicker();
      });
      list.append(b);
    });

    picker.append(list);
    doc.body.append(picker);
    return picker;
  }

  function closePicker() {
    if (picker) picker.hidden = true;
    buttons(root.document).forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  }

  function openPicker() {
    var doc = root.document;
    ensurePicker(doc);
    picker.hidden = false;
    buttons(doc).forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    var first = picker.querySelector('.theme-picker__option[aria-current="true"]')
      || picker.querySelector('.theme-picker__option');
    if (first) {
      first.focus();
      /* With the full set in the list, the current theme can be well below the
       * fold, and a picker that opens on somebody else's theme reads as "my
       * choice was lost". `scrollIntoView` with `block:'nearest'` scrolls only
       * when it has to, so the common case does not move at all. */
      if (typeof first.scrollIntoView === 'function') {
        first.scrollIntoView({ block: 'nearest' });
      }
    }
  }

  function syncPicker() {
    if (!picker) return;
    var name = currentTheme();
    var opts = picker.querySelectorAll('.theme-picker__option');
    for (var i = 0; i < opts.length; i += 1) {
      var on = opts[i].dataset.themeChoice === name;
      if (on) opts[i].setAttribute('aria-current', 'true');
      else opts[i].removeAttribute('aria-current');
    }
  }

  /* The committed theme is the store's answer, not the attribute's: while a
   * preview is painted the attribute wears the preview and the store still
   * holds the commit. */
  function committed() {
    var stored = readStore();
    return known(stored) ? stored : currentTheme();
  }

  function syncDropdown() {
    if (!dropdown) return;
    var name = previewTheme || currentTheme();
    var opts = dropdown.querySelectorAll('.theme-dropdown__option');
    for (var i = 0; i < opts.length; i += 1) {
      var on = opts[i].dataset.themeChoice === name;
      if (on) opts[i].setAttribute('aria-current', 'true');
      else opts[i].removeAttribute('aria-current');
    }
  }

  /* ── HOVER PREVIEW: COALESCED TO ONE ATTRIBUTE WRITE PER FRAME (2026-10-12) ──
   * THE COST OF A PREVIEW IS ONE ATTRIBUTE WRITE AND NOTHING ELSE. A theme
   * switch is `html[data-theme]` moving from one name to another, and the style
   * engine matching the rules it already has against the new name on the next
   * frame. NO preview may therefore create a stylesheet, fetch a font, decode an
   * image, write the store or call the shell: rooting a sweep of the list costs N
   * recalculations instead of N parses.
   *
   * NUMBER, WITH ITS DATE AND ITS REVISION (this file's own rule 2). The sentence
   * that used to stand here — "the eight theme stylesheets the document links
   * are 601 922 B / 3 149 rule blocks, so the CSS is ALL parsed at load" — is
   * STALE twice over and was corrected 2026-10-12. (1) The count: measured
   * 2026-10-12 over the EIGHT `<link>`s the document actually carries
   * (panel.html:48-66) — themes/fonts.css 27 971, panel.css 109 361,
   * themes/theme-{1..5}.css 26 952 / 27 169 / 27 302 / 26 235 / 27 437 and
   * themes/zipc-panels.css 35 875 — the eager load is 308 302 B over 1 179 rule
   * blocks, not 601 922 B / 3 149. (2) The premise: themes/cinematic.css
   * (312 230 B) and themes/panel-designs.css (128 716 B) are NOT linked any
   * more. Since S7's `lazy-assets.js` they are gated behind the shell's ask
   * and arrive only for a `cine-*` / `pd-*` theme, so "all parsed at load" now
   * holds for the five `theme-N` directions and the ten `zipc` panel designs and
   * NOT for the rest of the manifest. What survives the correction is the claim
   * that matters: the preview itself never parses anything. A theme stylesheet
   * that has not arrived is ASKED for, off this path, by `lazy-assets.js`'s
   * MutationObserver on `data-theme` (`settle()` → `loadFor()`), so a preview can
   * at worst warm the same bytes a commit would have fetched anyway.
   *
   * What this scheduler buys, in the units the jank is actually made of:
   *   * LATEST WINS. Ten `mouseenter`s inside one frame collapse into ONE apply,
   *     the one the pointer is actually resting on. The old code applied every
   *     one of them, so a fast sweep of the list paid ten full theme switches.
   *   * ONE FORCED RECALCULATION PER FRAME AT MOST. `pendingPreview` latches
   *     until the frame callback runs; a second event in the same frame only
   *     overwrites the name.
   *   * ZERO WORK ON THE REST OF THE PANEL. `previewing` suppresses the tuning
   *     layer's MutationObserver (see `previewWindowOpen`), whose `apply()`
   *     would otherwise remove 33 custom properties and issue four
   *     `getComputedStyle` reads PER HOVERED OPTION — a style invalidation plus
   *     four forced recalculations per event, which is the jank this lane was
   *     opened for.
   *   * THE FIRST HOVER IS WARM. `warm()` (on dropdown open, in an idle slice)
   *     asks for the fonts each theme asks for and decodes each theme's backdrop
   *     ONCE, so the preview frame never waits on a font or an image.
   *
   * COALESCING IS INVISIBLE TO THE ORACLE BY CONSTRUCTION: `stats()` reports
   * events, applies and the frame that applied them, so "10 hovers cost 1
   * apply" is a NUMBER and not a claim about smoothness. */
  var previewing = false;
  var pendingPreview = null;
  var rafHandle = null;
  var stat = {
    hoverEvents: 0, focusEvents: 0, applies: 0, reverts: 0, commits: 0,
    frames: 0, lastFrameApplies: 0, lastFlushMs: 0, totalFlushMs: 0,
    flushSamples: [], storeWrites: 0, shellCalls: 0,
    warmFonts: 0, warmImages: 0, warmMs: 0, coalescedDrops: 0
  };

  function now() {
    return (root.performance && root.performance.now) ? root.performance.now() : Date.now();
  }

  function statsLine() {
    return 'hovers=' + stat.hoverEvents + ' applies=' + stat.applies +
      ' frames=' + stat.frames + ' coalesced=' + stat.hoverEvents +
      '->' + stat.applies + ' storeWrites=' + stat.storeWrites +
      ' shellCalls=' + stat.shellCalls;
  }

  /* The preview runs INSIDE a documented window: from the first hover to the
   * revert/commit. While it is open the tuning layer defers, because its work is
   * per-theme state (the inline custom properties) and the commit/revert that
   * ends the window re-applies it exactly once. */
  function previewWindowOpen() {
    return previewing;
  }
  /* Warm EVERY theme once, off the critical path: the caption font each theme
   * names, and the backdrop each theme paints. Neither can be warmed by a
   * "preview" that is already late — the point is that the first hover does not
   * pay for them. */
  function warmFonts() {
    var fonts = (MANIFEST && MANIFEST.warmFonts) || null;
    var done = 0;
    if (!root.document || !root.document.fonts || typeof root.document.fonts.load !== 'function') return 0;
    if (fonts && fonts.length) {
      for (var i = 0; i < fonts.length; i += 1) {
        try { root.document.fonts.load(fonts[i], 'Aa'); done += 1; } catch (err) { /* not fatal */ }
      }
      return done;
    }
    /* No declared list: ask for the families the manifest's theme names imply by
     * reading the CSS the document already has. Bounded to one pass. */
    for (var t = 0; t < THEMES.length; t += 1) {
      var label = THEMES[t].label;
      if (!label) continue;
      try { root.document.fonts.load('16px "' + String(label).split(' ')[0] + '"', 'Aa'); done += 1; } catch (err) { /* not fatal */ }
    }
    return done;
  }

  function warmImages() {
    if (!root.document || !root.Image) return 0;
    var files = {};
    for (var i = 0; i < THEMES.length; i += 1) {
      var bd = THEMES[i].backdrop;
      if (bd) files[bd] = true;
    }
    var names = [];
    for (var k in files) if (Object.prototype.hasOwnProperty.call(files, k)) names.push(files[k]);
    for (var n = 0; n < names.length; n += 1) {
      try { var img = new root.Image(); img.decoding = 'async'; img.src = names[n]; } catch (err) { /* not fatal */ }
    }
    return names.length;
  }

  function warm() {
    var t0 = now();
    stat.warmFonts = warmFonts();
    stat.warmImages = warmImages();
    stat.warmMs = now() - t0;
    return { fonts: stat.warmFonts, images: stat.warmImages, ms: stat.warmMs };
  }

  function scheduleWarm() {
    if (typeof root.requestIdleCallback === 'function') {
      root.requestIdleCallback(function () { warm(); }, { timeout: 600 });
    } else {
      root.setTimeout(warm, 0);
    }
  }

  function inFrame() {
    return typeof root.requestAnimationFrame === 'function';
  }

  function flushPreview() {
    rafHandle = null;
    pendingPreview = null;
    stat.frames += 1;
    if (!previewTheme) { stat.lastFrameApplies = 0; return; }
    var t0 = now();
    api.set(previewTheme, { persist: false });
    var ms = now() - t0;
    stat.applies += 1;
    stat.lastFrameApplies = 1;
    stat.lastFlushMs = ms;
    stat.totalFlushMs += ms;
    if (stat.flushSamples.length < 512) stat.flushSamples.push(ms);
  }

  /* Hover/focus = instant preview, no persistence: the owner sees the theme
   * before he decides to keep it. The claim to paint is stored NOW and painted
   * in the frame — an event that lands while a frame is already pending only
   * replaces the name. */
  function preview(name) {
    if (!known(name)) return;
    if (previewTheme === name) return;
    stat.hoverEvents += 1;
    previewTheme = name;
    if (inFrame()) {
      if (rafHandle !== null) { stat.coalescedDrops = (stat.coalescedDrops || 0) + 1; return; }
      rafHandle = root.requestAnimationFrame(flushPreview);
    } else {
      /* No rAF (an old host): apply immediately — correctness first. */
      flushPreview();
    }
  }

  /* Click/Enter = commit through the SAME persist path the cycle button and
   * the picker use: one attribute write plus the store write inside `set`.
   *
   * ORDER IS LOAD-BEARING: the end of the preview window is published BEFORE the
   * commit write (so the tuning layer applies the theme it is switching TO and
   * not the previewed one), the commit write itself is ONE call, and the tuning
   * layer is re-applied once afterwards. The store write inside that call is the
   * ONLY store write the whole interaction makes. */
  function commit(name) {
    if (!known(name)) return;
    if (rafHandle !== null && typeof root.cancelAnimationFrame === 'function') {
      root.cancelAnimationFrame(rafHandle);
      rafHandle = null;
    }
    pendingPreview = null;
    previewing = false;
    previewTheme = null;
    committedTheme = api.set(name);
    stat.commits += 1;
    applyTune(committedTheme);
    closeDropdown();
  }

  /* The tuning layer is re-applied exactly ONCE per commit and ONCE per revert,
   * by name, so it never has to guess the theme it is applying. Absent module
   * (the oracle, the strip before it loads) = nothing to do.
   *
   * The ORDER is the whole trick: `previewing` is cleared BEFORE the commit
   * write, so by the time this runs the tuning layer's own `previewOpen()`
   * answers FALSE and it applies the theme we are switching TO — not the one
   * that was being previewed. Its MutationObserver then sees the write, finds
   * `appliedTheme` already equal to the settled theme, and does nothing. */
  function applyTune(name) {
    var tune = root.SottoThemeTune;
    if (!tune || typeof tune.apply !== 'function') return false;
    if (previewWindowOpen()) return false;
    try { tune.apply(name); } catch (err) { return false; }
    return true;
  }

  /* Leaving the dropdown or pressing Escape = revert to the committed theme.
   * The store still holds it, so the revert is `persist:false` — no write,
   * just the attribute back where it was. */
  function revertPreview() {
    var wasPreviewing = previewing || previewTheme !== null;
    if (rafHandle !== null && typeof root.cancelAnimationFrame === 'function') {
      root.cancelAnimationFrame(rafHandle);
      rafHandle = null;
    }
    pendingPreview = null;
    previewTheme = null;
    previewing = false;
    if (!wasPreviewing) return;
    /* ONE attribute write back to the commit. The store still holds it, so this
     * is the only preview write that is NOT the theme just previewed, and it is
     * not a persist: the choice the owner made is untouched by the preview. */
    api.set(committedTheme || FALLBACK, { persist: false });
    stat.reverts += 1;
    syncDropdown();
    applyTune(committedTheme || FALLBACK);
  }

  function openDropdown() {
    var doc = root.document;
    if (!doc) return;
    ensureDropdown(doc);
    closePicker();
    committedTheme = committed();
    previewTheme = null;
    dropdown.hidden = false;
    dropdownOpen = true;
    previewing = true;
    setChevronsExpanded(true);
    paintChevrons();
    syncDropdown();
    /* Warm the fonts and backdrops ONCE, in an idle slice: the first hover must
     * not be the first time the browser sees either. The idle scheduler is the
     * part that keeps it off the open path. */
    scheduleWarm();
    var first = dropdown.querySelector('.theme-dropdown__option[aria-current="true"]')
      || dropdown.querySelector('.theme-dropdown__option');
    if (first) first.focus();
  }

  function closeDropdown(revert) {
    if (rafHandle !== null && typeof root.cancelAnimationFrame === 'function') {
      root.cancelAnimationFrame(rafHandle);
      rafHandle = null;
    }
    pendingPreview = null;
    if (revert !== false) revertPreview();
    if (dropdown) dropdown.hidden = true;
    dropdownOpen = false;
    setChevronsExpanded(false);
    paintChevrons();
  }

  function toggleDropdown() {
    if (dropdownOpen && dropdown && !dropdown.hidden) closeDropdown(true);
    else openDropdown();
  }

  /* The chevrons: their own compact buttons next to each theme button — the
   * header's and the strip's — so the owner can cycle WITHOUT opening anything
   * and list WITHOUT cycling. The host page may ship them in markup
   * (`#strip-theme-chevron`), the module creates the header's when the harness
   * has none, and this code creates either one when it is missing. The BASE
   * `panel.css` order rules, not this insert, decide the final arrangement. */
  function paintChevrons() {
    if (!chevrons.length) return;
    var name = currentTheme();
    var theme = known(name);
    chevrons.forEach(function (c) {
      c.title = 'Theme list: ' + labelOf(name) + ' — open for all five, hover previews';
      c.setAttribute('aria-label', c.title);
      if (theme) c.style.setProperty('--theme-swatch', theme.swatch);
    });
  }

  /* The dropdown is shared, so every chevron reports the same expanded state. */
  function setChevronsExpanded(open) {
    chevrons.forEach(function (c) { c.setAttribute('aria-expanded', open ? 'true' : 'false'); });
  }

  function inAnyChevron(target) {
    for (var i = 0; i < chevrons.length; i += 1) {
      if (chevrons[i].contains(target)) return true;
    }
    return false;
  }

  /* ── BARE MINIMUM ON THE STRIP ──────────────────────────────────────────────
   * The strip surface is the owner's short bar (panel.html:590: transcript
   * drawer, header and footer are all `display:none` there), so it must never
   * grow a second door into the theme list. The test is ANCESTRY, not the
   * `data-surface` attribute: the attribute says which surface is ON SCREEN
   * right now, and a popup the panel opened can outlive a switch. The strip
   * bar is `.stripbar` (panel.html:610), and everything the strip carries lives
   * inside it — including a `#strip-theme-chevron` a future markup line might
   * ship there. */
  function inStripBar(el) {
    var n = el;
    while (n) {
      if (n.className && String(n.className).split(/\s+/).indexOf('stripbar') >= 0) return true;
      n = n.parentNode;
    }
    return false;
  }

  /* The one question `registerChevron` asks. A chevron in the RIGHT panel's
   * control cluster (`.panel__controls`, which is inside `.panel__header`) is
   * eligible; a chevron in the strip bar is NOT, so it never becomes a trigger
   * and never gets a click or keydown listener. */
  function isPanelChevron(el) {
    if (!el) return false;
    return !inStripBar(el);
  }

  function registerChevron(btn) {
    if (!btn || chevrons.indexOf(btn) >= 0) return btn;
    /* REFUSED, NOT HIDDEN: a strip-bar chevron keeps whatever it already is and
     * gets nothing from this module. It cannot open the dropdown, so the strip
     * stays bare even if a markup line ships one; `panel.css` keeps it
     * invisible. */
    if (!isPanelChevron(btn)) return null;
    chevrons.push(btn);
    if (!btn.dataset.wired) {
      btn.dataset.wired = 'true';
      wireChevron(btn);
    }
    return btn;
  }

  function makeChevron(doc, id, className) {
    var btn = doc.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.id = id;
    btn.dataset.themeChevron = 'true';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'theme-dropdown');
    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = doc.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    var path = doc.createElementNS(svgNS, 'path');
    path.setAttribute('d', 'M4 6.5L8 10.5L12 6.5');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
    btn.appendChild(svg);
    return btn;
  }

  function ensureChevrons(doc) {
    /* Every chevron the host page ships, in the RIGHT panel's cluster. A
     * `#strip-theme-chevron` the strip bar might ship is FOUND here and then
     * refused by `registerChevron`, so no listener is attached to it. */
    var found = doc.querySelectorAll('#theme-chevron, #strip-theme-chevron, [data-theme-chevron]');
    for (var i = 0; i < found.length; i += 1) registerChevron(found[i]);

    /* The panel's: created only when the host page has none. THIS IS THE ONLY
     * TRIGGER THE MODULE BUILDS. */
    if (!doc.getElementById('theme-chevron')) {
      var host = doc.querySelector('.panel__controls');
      if (host) {
        var hbtn = makeChevron(doc, 'theme-chevron', 'icon-button theme-chevron');
        var anchor = doc.getElementById('theme-button');
        if (anchor && anchor.parentNode === host && anchor.nextSibling) host.insertBefore(hbtn, anchor.nextSibling);
        else if (anchor && anchor.parentNode === host) host.appendChild(hbtn);
        else host.insertBefore(hbtn, host.firstChild);
        registerChevron(hbtn);
      }
    }

    /* ── THE STRIP HAS NO CHEVRON, AND THAT IS THE RE-ANCHOR ──────────────────
     * A block that built `#strip-theme-chevron` next to `#strip-theme-button`
     * and registered it used to sit exactly here. It was DELETED on 2026-10-12
     * (lane S6-R) when the dropdown moved to the right panel: the owner's order
     * is *"o painel de baixo, deve conter apenas o bare minimum"*, and the strip
     * already has its one theme control, `#strip-theme-button`, which CYCLES.
     * Nothing here re-creates the node — the earlier revision did, which is why
     * `panel.css` had to hide a node this module kept putting back. A lane that
     * restores a strip chevron goes RED on `_main/theme-preview-oracle.js`
     * ARM 11.7 and neg-arm M4. */

    paintChevrons();
    return chevrons;
  }

  function wireChevron(btn) {
    btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      activeChevron = btn;
      toggleDropdown();
    });
    btn.addEventListener('keydown', function (ev) {
      activeChevron = btn;
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp' || ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        if (dropdownOpen && dropdown && !dropdown.hidden) {
          var first = dropdown.querySelector('.theme-dropdown__option[aria-current="true"]')
            || dropdown.querySelector('.theme-dropdown__option');
          if (first) first.focus();
        } else {
          openDropdown();
        }
      } else if (ev.key === 'Escape') {
        closeDropdown(true);
      }
    });
  }

  function ensureDropdown(doc) {
    if (dropdown && dropdown.isConnected) return dropdown;
    var existing = doc.getElementById('theme-dropdown');
    if (existing) {
      dropdown = existing;
      syncDropdown();
      return dropdown;
    }
    var box = doc.createElement('div');
    box.className = 'theme-dropdown';
    box.id = 'theme-dropdown';
    box.hidden = true;
    box.setAttribute('role', 'listbox');
    box.setAttribute('aria-label', 'Choose a theme — hover previews, click keeps');
    /* ALL THE THEMES, IN TWO COLUMNS.
     *
     * IT WAS FIVE PLUS A DOOR, AND THE DOOR WAS NEVER BUILT: this function used
     * `list` without declaring it (it was a local of `ensurePicker`), so the
     * first chevron click threw `ReferenceError: list is not defined` and the
     * dropdown never existed at all. MEASURED 2026-10-17 in a real Chromium
     * against the shipped page: `#theme-chevron.click()` -> zero
     * `#theme-dropdown`, one console error. That is the owner's "o dropdown que
     * mostra todos os designs/temas nao funciona".
     *
     * The list below is ALL 45, rendered in a two-column grid by
     * `button-contract.css` so every design is reachable without a scrollbar. */
    var list = doc.createElement('div');
    list.className = 'theme-dropdown__list';
    list.setAttribute('role', 'group');
    THEMES.forEach(function (theme) {
      var b = doc.createElement('button');
      b.type = 'button';
      b.className = 'theme-dropdown__option';
      b.dataset.themeChoice = theme.name;
      b.setAttribute('role', 'option');
      b.style.setProperty('--theme-swatch', theme.swatch);
      b.textContent = theme.label;
      var chip = doc.createElement('span');
      chip.className = 'theme-dropdown__swatch';
      chip.setAttribute('aria-hidden', 'true');
      b.insertBefore(chip, b.firstChild);
      /* HOVER = preview: `mouseenter` paints instantly, `click` commits. */
      b.addEventListener('mouseenter', function () { preview(theme.name); });
      b.addEventListener('focus', function () { stat.focusEvents += 1; preview(theme.name); });
      b.addEventListener('click', function (ev) {
        ev.stopPropagation();
        commit(theme.name);
      });
      b.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          ev.stopPropagation();
          commit(theme.name);
        } else if (ev.key === 'Escape') {
          ev.preventDefault();
          ev.stopPropagation();
          closeDropdown(true);
          if (activeChevron) activeChevron.focus();
        } else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
          ev.preventDefault();
          ev.stopPropagation();
          var opts = dropdown.querySelectorAll('.theme-dropdown__option');
          var at = -1;
          for (var i = 0; i < opts.length; i += 1) {
            if (opts[i] === b) { at = i; break; }
          }
          var next = ev.key === 'ArrowDown'
            ? opts[(at + 1) % opts.length]
            : opts[(at - 1 + opts.length) % opts.length];
          if (next) next.focus();
        }
      });
      list.append(b);
    });
    box.append(list);
    /* Mouse-away = revert: leaving the whole box gives back the commit. */
    box.addEventListener('mouseleave', function () { closeDropdown(true); });
    doc.body.append(box);
    dropdown = box;
    return dropdown;
  }

  function paintButton(btn) {
    if (!btn) return;
    var name = currentTheme();
    var theme = known(name);
    btn.dataset.themeCurrent = name;
    btn.title = 'Theme: ' + labelOf(name) + ' — click for the next one, right-click for every theme';
    btn.setAttribute('aria-label', btn.title);
    if (theme) btn.style.setProperty('--theme-swatch', theme.swatch);
    var label = btn.querySelector('.theme-button__label');
    if (label) label.textContent = labelOf(name);
  }

  /* ── EVERY MOUNT POINT, ONE PAINT ───────────────────────────────────────────
   * The theme control exists in TWO places on purpose: the header's cluster
   * (`.panel__controls`, where the module creates `#theme-button` if the host
   * page has none) and the STRIP's control row (`#strip-theme-button`, markup,
   * because `.panel__header` is `display:none` on that surface and a button
   * inside it is unreachable). Both carry `data-theme-button`; this is the one
   * list, so a third mount point is a markup line and nothing else, and the two
   * can never show different themes. */
  function buttons(doc) {
    if (!doc || !doc.querySelectorAll) return [];
    var out = [];
    var seen = [];
    var push = function (el) { if (el && seen.indexOf(el) < 0) { seen.push(el); out.push(el); } };
    var nodes = doc.querySelectorAll('[data-theme-button]');
    for (var i = 0; i < nodes.length; i += 1) push(nodes[i]);
    push(doc.getElementById('theme-button'));
    return out;
  }

  function paintAll(doc) {
    buttons(doc).forEach(paintButton);
  }

  function wireButton(btn) {
    if (!btn) return;
    /* THE TWO CLICKS ARE THE OWNER'S, verbatim (2026-10-08): *"clique esquerdo
     * avança, direito retrocede nos temas"*. So the right button now walks
     * BACKWARDS, which is a change of contract: it used to OPEN THE PICKER. The
     * picker did not lose its home — it moved to the keyboard (ArrowDown /
     * ArrowUp / Enter), where it already was — and the reason that is the right
     * trade is the owner's OTHER request: walking the flat manifest order means
     * the A/B/C variants of one design sit next to each other, so one click each
     * way flips between them, which is the comparison he asked to be able to do. */
    btn.addEventListener('click', function () {
      api.next();
    });
    btn.addEventListener('contextmenu', function (ev) {
      ev.preventDefault();
      api.previous();
    });
    btn.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp' || ev.key === 'Enter') {
        ev.preventDefault();
        if (picker && !picker.hidden) closePicker();
        else openPicker();
        return;
      }
      if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        api.next();
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        api.previous();
      }
    });
    paintButton(btn);
  }

  /* The button the MODULE owns, used only when the host page has none. It is
   * inserted into the header's control cluster — `.panel__controls` — which is
   * where the panel's other controls live, so the tab order stays where the eye
   * already is. Nothing else in the document is moved, wrapped or renamed. */
  function ensureButton(doc) {
    var existing = doc.getElementById('theme-button');
    if (existing) return existing;

    var host = doc.querySelector('.panel__controls') || doc.querySelector('.panel__header');
    if (!host) return null;

    var btn = doc.createElement('button');
    btn.type = 'button';
    btn.className = 'icon-button theme-button';
    btn.id = 'theme-button';
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');

    var label = doc.createElement('span');
    label.className = 'theme-button__label';
    btn.append(label);

    host.prepend(btn);
    return btn;
  }

  /* list() — the five themes, in order, as the manifest declares them. */
  var api = {
    list: function () {
      return THEMES.map(function (t) {
        return {
          name: t.name, label: t.label, swatch: t.swatch,
          group: t.group || null, variant: t.variant || null
        };
      });
    },

    /* current() — what the document is wearing RIGHT NOW, read from the DOM and
     * not from a cached variable, so a hand-set attribute is never contradicted. */
    current: function () {
      return currentTheme();
    },

    /* set(name) — the switch itself: ONE attribute write. An unknown name is
     * refused and the current theme is returned instead of a half-applied one. */
    set: function (name, opts) {
      var el = themeElement();
      if (!el) return FALLBACK;
      var theme = known(name);
      if (!theme) return currentTheme();

      /* ONE attribute write. No stylesheet is created, fetched or replaced here:
       * the theme rules the document already has are matched against the new
       * name by the style engine on the next frame. That single write IS the
       * whole cost of a preview. */
      el.dataset.theme = theme.name;
      if (!opts || opts.persist !== false) writeStore(theme.name);

      syncPicker();
      syncDropdown();
      paintAll(root.document);
      paintChevrons();
      return theme.name;
    },

    /* previewWindowOpen() — TRUE while a hover preview is live, i.e. between the
     * first hover and the commit/revert that ends it. THE TUNING LAYER ASKS THIS
     * (app/panel/theme-tune.js): its MutationObserver reacts to the SAME
     * `data-theme` write, so without the question it would re-apply the owner's
     * per-theme colour edits on every hover — 33 custom-property removals and
     * four forced `getComputedStyle` reads per option, measured in the receipt. */
    previewWindowOpen: function () {
      return previewWindowOpen();
    },

    /* triggers() — the elements this module WIRED as dropdown doors, in wire
     * order. Exposed so a gate can assert WHERE the control lives instead of
     * re-implementing the registration rules: the list must contain the RIGHT
     * panel's chevron and NOTHING in the strip bar. Not part of the owner's
     * path. */
    triggers: function () {
      return chevrons.slice();
    },

    /* closeDropdown — exposed so an ORACLE can end a preview it started, and so a
     * caller that opened the dropdown without committing can put the panel back.
     * Not part of the owner's path; the buttons own that. */
    closeDropdown: function () {
      closeDropdown(true);
    },

    /* stats() — the numbers behind the claim, exposed for the oracle and for the
     * dev console. A preview budget is a NUMBER here, never a feeling. */
    stats: function () {
      return {
        themes: THEMES.length,
        hoverEvents: stat.hoverEvents,
        focusEvents: stat.focusEvents,
        applies: stat.applies,
        commits: stat.commits,
        reverts: stat.reverts,
        frames: stat.frames,
        coalescedDrops: stat.coalescedDrops,
        storeWrites: stat.storeWrites,
        shellCalls: stat.shellCalls,
        warmFonts: stat.warmFonts,
        warmImages: stat.warmImages,
        warmMs: stat.warmMs,
        flushMs: stat.flushSamples.slice(),
        previewWindowOpen: previewWindowOpen()
      };
    },

    /* next() — cycle, in manifest order, wrapping. */
    next: function () {
      var name = currentTheme();
      for (var i = 0; i < THEMES.length; i += 1) {
        if (THEMES[i].name === name) return api.set(THEMES[(i + 1) % THEMES.length].name);
      }
      return api.set(FALLBACK);
    },

    /* previous() — the SAME walk, one step back, on the owner's right button
     * (2026-10-08). Wrapping is deliberate: the ends of the list are not a wall,
     * they are the ends of a ring, so a wrong click costs one more click instead
     * of a trip to the picker. */
    previous: function () {
      var name = currentTheme();
      for (var i = 0; i < THEMES.length; i += 1) {
        if (THEMES[i].name === name) {
          return api.set(THEMES[(i - 1 + THEMES.length) % THEMES.length].name);
        }
      }
      return api.set(FALLBACK);
    },

    /* group(name) — the A/B/C family a theme belongs to, or null. Exposed because
     * "which designs are variants of one another" is a claim the picker renders
     * and an oracle should be able to check without reading the buttons. */
    group: function (name) {
      var t = known(name || currentTheme());
      return t && t.group ? t.group : null;
    },

    /** variant(name) — 'A' | 'B' | 'C' | null. */
    variant: function (name) {
      var t = known(name || currentTheme());
      return t && t.variant ? t.variant : null;
    },

    /* mount() — idempotent. Wires the header button (the host's or our own),
     * the chevron + dropdown, and the picker, then re-applies the stored
     * choice. Called once at load and again if the harness injects a button
     * later; a second call must not duplicate a listener or a picker, which
     * is what `wired` guards. */
    mount: function () {
      var doc = root.document;
      if (!doc || !doc.body) return false;
      var btn = ensureButton(doc);
      var all = buttons(doc);
      all.forEach(function (b) {
        if (b.dataset.wired) return;
        b.dataset.wired = 'true';
        wireButton(b);
      });
      ensureChevrons(doc);
      ensureDropdown(doc);
      syncPicker();
      syncDropdown();
      return Boolean(btn) || all.length > 0;
    },

    /* last() — the stored choice, or null. Exposed because "which theme comes
     * back after a restart" is a claim that has to be checkable. */
    last: function () {
      return readStore();
    }
  };

  if (root) {
    root.SottoTheme = api;

    if (root.document) {
      var apply = function () {
        /* The stored choice is applied BEFORE first paint (`script-src 'self'`
         * scripts in <head> run before the body exists), so the panel never
         * paints one theme and then flips to another. */
        var stored = readStore();
        api.set(known(stored) ? stored : FALLBACK, { persist: false });

        var boot = function () {
          api.mount();
          /* Dismissing the picker AND the dropdown: a click outside them,
           * Escape, or focus leaving the header. No caption element is ever a
           * target of these listeners. A dropdown cancel REVERTS the preview
           * (`closeDropdown(true)`); a commit already closed it. */
          root.document.addEventListener('click', function (ev) {
            if (dropdownOpen && dropdown && !dropdown.hidden) {
              if (dropdown.contains(ev.target)) return;
              if (inAnyChevron(ev.target)) return;
              closeDropdown(true);
            }
            if (!picker || picker.hidden) return;
            if (picker.contains(ev.target)) return;
            var b = root.document.getElementById('theme-button');
            if (b && b.contains(ev.target)) return;
            closePicker();
          });
          root.document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') {
              if (dropdownOpen) closeDropdown(true);
              closePicker();
            }
          });
          root.document.addEventListener('focusin', function (ev) {
            if (!dropdownOpen || !dropdown || dropdown.hidden) return;
            if (dropdown.contains(ev.target)) return;
            if (inAnyChevron(ev.target)) return;
            var t = ev.target;
            if (t && t.classList && t.classList.contains('theme-dropdown__option')) return;
            closeDropdown(true);
          });
        };

        if (root.document.readyState === 'loading') {
          root.document.addEventListener('DOMContentLoaded', boot);
        } else {
          boot();
        }
      };
      apply();
    }
  }

  /* Usable from Node for `node --check` and for a unit oracle. */
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : null));
