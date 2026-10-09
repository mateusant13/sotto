/* Sotto — PER-THEME TEMPLATE EDITING.
 *
 * The owner's request, verbatim (2026-10-08):
 *
 *   "quero que os temas sejam templates. e quero modificar coisas de cada
 *    templete de um jeito facil, pelo painel. tipo trocar a fonte, entre
 *    outras coisas q tu achar bom tambem"
 *
 * So a theme stops being a fixed design and becomes a TEMPLATE the owner can
 * adjust from inside the panel, and every adjustment belongs to ONE theme:
 * changing the caption size on Teleprompter must not touch Broadcast.
 *
 * ── THE MECHANISM: INLINE CUSTOM PROPERTIES ON <html> ─────────────────────────
 * An edit is written with
 *
 *     document.documentElement.style.setProperty('--size-caption', '34px')
 *
 * and undone with `removeProperty`, which restores whatever the theme's own
 * stylesheet declares — no copy of the theme is kept anywhere, so the
 * generator-owned `themes/theme-N.css` files are never edited by this module
 * (they stay regenerable) and this layer cannot drift from them.
 *
 * WHY INLINE AND NOT A GENERATED `<style>` ELEMENT, both reasons load-bearing:
 *   1. PRECEDENCE. The five theme files scope every rule to
 *      `:root[data-theme='theme-N']`, and their token blocks are at specificity
 *      (0,1,0). An inline custom property on `<html>` outranks EVERY author
 *      rule regardless of specificity, so this layer never has to win an
 *      argument with a theme file — it simply is later by construction.
 *   2. CSP. `panel.html` ships `style-src 'self'`, which governs markup and
 *      stylesheet loads; `setProperty` is a CSSOM mutation. The mechanism does
 *      not depend on how the CSP treats a script-created `<style>`, which is
 *      the kind of reading that changes between Chromium versions.
 *
 * ── EVERY KNOB IS PROVEN LIVE, AND THAT IS THE POINT ──────────────────────────
 * A control that writes a variable nothing reads is worse than no control: it
 * takes a click, shows a change in its own readout, and paints nothing. This
 * repo has already paid for that lesson (`docs/audit/config-inert-fixed.md`).
 * So the shipped token list is not "everything a theme declares" — it is only
 * the tokens a shipped rule actually CONSUMES, and `_main/theme-tune-oracle.js`
 * gates it: for every token below, `var(--token)` must appear in the panel's
 * own CSS, or the oracle goes RED. Three tokens the themes declare are
 * therefore ABSENT on purpose, with the measurement in the oracle:
 *   * `--slab-opacity`  — declared 0.96–0.99 in all five themes, read by
 *     nothing: the slab's own background bakes the percentage into
 *     `color-mix(... 97% ...)` at generation time. Editing it would do nothing.
 *   * `--text-confirmed` — declared by all five themes, consumed by no rule
 *     (a confirmed line is painted with `--text-secondary`, see
 *     `themes/theme-1.css:226-231`).
 *   * `--font-caption` / `--font-closed` — declared as `var(--font-sans)` by
 *     all five, consumed by no rule; the caption family comes from
 *     `--font-sans` directly (`themes/theme-1.css:217`). `--font-sans` is the
 *     knob that moves, and it moves BOTH tiers, which is the truth.
 *
 * ── THE DEFAULTS ARE READ, NEVER COPIED ───────────────────────────────────────
 * "Restore this theme" has to mean the value `gen_themes.py` wrote, not a second
 * copy of it living in this file. So the baseline for a knob is obtained by
 * REMOVING the inline property and reading the theme's own computed value
 * (`baseline()`); nothing here hard-codes `30px` or `#F2E9D8`. That is also why
 * a theme can be regenerated with new numbers and every stored edit still means
 * what it meant, and every untouched knob still follows the new design.
 *
 * ── PERSISTENCE IS DEFENSIVE, LIKE `theme-switcher.js` ────────────────────────
 * `localStorage` can throw over `file://` in WebView2, so every access is
 * wrapped and falls back to memory: the edits work for the session either way.
 */
(function (root) {
  'use strict';

  var STORE_KEY = 'sotto.theme.tune';

  /* ── THE FONTS THE PANEL ACTUALLY BUNDLES ────────────────────────────────────
   * `themes/fonts.css` ships all SIXTEEN families the design zips name — the owner
   * asked for every one of them, verbatim (2026-10-08): *"eu gostei de todas as
   * fontes, entao inclua toda as fontes"* — so the picker offers sixteen and
   * nothing that is not on this box. The panel is a `file://` document with no
   * network (`font-src 'self'`), so offering a family that is not bundled would let
   * the owner pick a font and silently get a fallback, which is the defect this
   * list exists to prevent.
   *
   * The stacks are spelled the way the theme files spell them, so the `select` can
   * show the theme's OWN value as the selected option instead of "other". */
  var FONT_SYSTEM_SANS = '-apple-system, "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif';
  var FONT_SYSTEM_MONO = '"Cascadia Mono", ui-monospace, Consolas, monospace';
  var UI_FALLBACK = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif';
  var SERIF_FALLBACK = 'Georgia, "Times New Roman", serif';
  var MONO_FALLBACK = '"Cascadia Mono", Consolas, ui-monospace, monospace';
  var FONT_OPTIONS = [
    /* THE FIVE ORIGINAL DIRECTIONS KEEP THEIR OWN STACKS, VERBATIM. `themes/theme-N.css`
     * declares these exact strings, and an option is matched by comparing the stack
     * whitespace- and case-insensitively — so shortening one here would make the
     * `select` stop recognising the theme's own value and offer it as a separate
     * "Do tema" option. The five lines below are copied from the generated files on
     * purpose and `_main/theme-tune-oracle.js` is what keeps them honest. */
    { value: '"Barlow Condensed", "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif', label: 'Barlow Condensed — teleprompter' },
    { value: '"IBM Plex Mono", "Cascadia Mono", Consolas, ui-monospace, monospace', label: 'IBM Plex Mono — broadcast' },
    { value: '"Newsreader", "Segoe UI Variable Text", "Segoe UI", Georgia, serif', label: 'Newsreader — manuscrito' },
    { value: '"Fraunces", "Segoe UI Variable Text", "Segoe UI", Georgia, serif', label: 'Fraunces — cinema card' },
    { value: '"Space Grotesk", "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif', label: 'Space Grotesk — instrumento' },
    // the families the `cinematic` template set brought in
    { value: '"Inter", ' + UI_FALLBACK, label: 'Inter — neutra de interface' },
    { value: '"Instrument Sans", ' + UI_FALLBACK, label: 'Instrument Sans — sóbria' },
    { value: '"Jost", ' + UI_FALLBACK, label: 'Jost — geométrica leve' },
    { value: '"Manrope", ' + UI_FALLBACK, label: 'Manrope — arredondada' },
    { value: '"Outfit", ' + UI_FALLBACK, label: 'Outfit — geométrica macia' },
    { value: '"Bricolage Grotesque", ' + UI_FALLBACK, label: 'Bricolage Grotesque — editorial' },
    { value: '"Instrument Serif", ' + SERIF_FALLBACK, label: 'Instrument Serif — serifa de título' },
    { value: '"Cormorant Garamond", ' + SERIF_FALLBACK, label: 'Cormorant Garamond — serifa fina' },
    { value: '"Lora", ' + SERIF_FALLBACK, label: 'Lora — serifa de leitura' },
    { value: '"DM Mono", ' + MONO_FALLBACK, label: 'DM Mono — mono leve' },
    { value: '"JetBrains Mono", ' + MONO_FALLBACK, label: 'JetBrains Mono — mono de código' },
    // and the two stacks that are already on the machine
    { value: FONT_SYSTEM_SANS, label: 'Sistema (sem serifa)' },
    { value: FONT_SYSTEM_MONO, label: 'Mono do sistema' }
  ];

  var WEIGHT_OPTIONS = [
    { value: '300', label: '300 — fina' },
    { value: '400', label: '400 — normal' },
    { value: '500', label: '500 — média' },
    { value: '600', label: '600 — semi' },
    { value: '700', label: '700 — negrito' },
    { value: '800', label: '800 — pesada' }
  ];

  var CASE_OPTIONS = [
    { value: 'none', label: 'como está' },
    { value: 'uppercase', label: 'MAIÚSCULAS' },
    { value: 'lowercase', label: 'minúsculas' },
    { value: 'capitalize', label: 'Cada Palavra' }
  ];

  /* ── THE KNOBS ───────────────────────────────────────────────────────────────
   * `token` is the variable this field writes. `alphaKeys` lists the extra
   * tokens the field must also write BECAUSE they are literal colours in the
   * theme files that would otherwise keep the OLD hue — a changed accent that
   * leaves the theme button's own swatch dot painting the previous accent is a
   * control that lies about itself, which is exactly what `themes/themes.js`
   * says must never happen. The alpha of each is READ from the theme
   * (`alphaOfComputed`) so the designer's own opacity is preserved instead of a
   * number invented here; the fallbacks are only for an unparseable value. */
  var FIELDS = [
    { id: 'fontSans', token: '--font-sans', kind: 'font', label: 'Fonte do tema' },
    { id: 'sizeCaption', token: '--size-caption', kind: 'length', unit: 'px', min: 12, max: 64, step: 1, label: 'Tamanho — legenda ao vivo' },
    { id: 'leadingCaption', token: '--leading-caption', kind: 'number', unit: '', min: 0.9, max: 2.2, step: 0.01, label: 'Altura da linha — ao vivo' },
    { id: 'weightCaption', token: '--weight-caption', kind: 'select', options: WEIGHT_OPTIONS, label: 'Peso — ao vivo' },
    { id: 'trackingCaption', token: '--tracking-caption', kind: 'number', unit: 'em', min: -0.02, max: 0.2, step: 0.002, label: 'Espaço entre letras — ao vivo' },
    { id: 'captionUpper', token: '--caption-upper', kind: 'select', options: CASE_OPTIONS, label: 'Maiúsculas' },
    { id: 'sizeClosed', token: '--size-closed', kind: 'length', unit: 'px', min: 10, max: 40, step: 1, label: 'Tamanho — linha fechada' },
    { id: 'leadingClosed', token: '--leading-closed', kind: 'number', unit: '', min: 0.9, max: 2.2, step: 0.01, label: 'Altura da linha — fechada' },
    { id: 'weightClosed', token: '--weight-closed', kind: 'select', options: WEIGHT_OPTIONS, label: 'Peso — linha fechada' },
    {
      id: 'accent',
      token: '--accent',
      kind: 'color',
      label: 'Cor de destaque',
      colorKeys: ['--accent-soft', '--theme-swatch', '--line', '--line-strong'],
      colorAlpha: { '--accent-soft': 0.14, '--line': 0.18, '--line-strong': 0.40 }
    },
    { id: 'textClosed', token: '--text-secondary', kind: 'color', label: 'Cor — texto confirmado' },
    { id: 'textProvisional', token: '--text-provisional', kind: 'color', label: 'Cor — texto provisório' },
    { id: 'bgSlab', token: '--bg-slab', kind: 'color', label: 'Fundo do painel' },
    { id: 'bgSlabStrong', token: '--bg-slab-strong', kind: 'color', label: 'Fundo do painel (topo)' },
    { id: 'radius', token: '--radius-lg', kind: 'length', unit: 'px', min: 0, max: 28, step: 1, label: 'Cantos do painel' },
    { id: 'motionIn', token: '--motion-in', kind: 'length', unit: 'ms', min: 0, max: 400, step: 10, label: 'Duração das transições' },
    {
      id: 'typeStep',
      token: '--type-step',
      kind: 'length',
      unit: 'ms',
      min: 0,
      max: 200,
      step: 5,
      label: 'Digitação letra a letra (0 = desligada)',
      /* The reveal's own documented off switch (`panel.css:1768-1776`). */
      zeroMeansOff: true
    }
  ];

  var FIELDS_BY_ID = {};
  var FIELDS_BY_TOKEN = {};
  for (var fi = 0; fi < FIELDS.length; fi += 1) {
    FIELDS_BY_ID[FIELDS[fi].id] = FIELDS[fi];
    FIELDS_BY_TOKEN[FIELDS[fi].token] = FIELDS[fi];
  }

  /* Every token this module can ever write, including a colour field's
   * companions. Used by `clear()` and by the oracle's liveness gate. */
  function allTokens() {
    var out = [];
    for (var i = 0; i < FIELDS.length; i += 1) {
      out.push(FIELDS[i].token);
      var extra = FIELDS[i].colorKeys;
      if (extra) for (var j = 0; j < extra.length; j += 1) out.push(extra[j]);
    }
    return out;
  }

  /* ── COLOUR ────────────────────────────────────────────────────────────────── */
  function hexToRgb(hex) {
    if (typeof hex !== 'string') return null;
    var s = hex.trim().toLowerCase();
    if (s.charAt(0) !== '#') return null;
    var body = s.slice(1);
    if (body.length === 3) {
      if (!/^[0-9a-f]{3}$/.test(body)) return null;
      return {
        r: parseInt(body.charAt(0) + body.charAt(0), 16),
        g: parseInt(body.charAt(1) + body.charAt(1), 16),
        b: parseInt(body.charAt(2) + body.charAt(2), 16)
      };
    }
    if (body.length === 6) {
      if (!/^[0-9a-f]{6}$/.test(body)) return null;
      return {
        r: parseInt(body.slice(0, 2), 16),
        g: parseInt(body.slice(2, 4), 16),
        b: parseInt(body.slice(4, 6), 16)
      };
    }
    return null;
  }

  function rgbaOf(hex, alpha) {
    var rgb = hexToRgb(hex);
    if (!rgb) return null;
    var a = typeof alpha === 'number' && isFinite(alpha) ? Math.min(1, Math.max(0, alpha)) : 1;
    return 'rgba(' + rgb.r + ', ' + rgb.g + ', ' + rgb.b + ', ' + trimNumber(a, 3) + ')';
  }

  /* `rgba(242, 233, 216, 0.12)` or `rgb(242, 233, 216)` → 0.12 / 1. Returns null
   * when the sheet's own alpha cannot be read, so the caller uses its fallback. */
  function alphaOfComputed(value) {
    if (typeof value !== 'string') return null;
    var m = /^rgba?\(([^)]+)\)$/i.exec(value.trim());
    if (!m) return null;
    var parts = m[1].split(/[\s,/]+/).filter(function (p) { return p !== ''; });
    if (parts.length < 3) return null;
    if (parts.length === 3) return 1;
    var a = parseFloat(parts[3]);
    return isFinite(a) ? Math.min(1, Math.max(0, a)) : null;
  }

  /* ── NUMBERS ───────────────────────────────────────────────────────────────── */
  function decimalsFor(step) {
    if (typeof step !== 'number' || step >= 1) return 0;
    var s = String(step);
    var dot = s.indexOf('.');
    return dot < 0 ? 0 : s.length - dot - 1;
  }

  /* Trim float noise without inventing digits: 0.006000000001 → "0.006". */
  function trimNumber(n, decimals) {
    if (typeof n !== 'number' || !isFinite(n)) return '';
    var d = typeof decimals === 'number' ? decimals : 3;
    var fixed = n.toFixed(Math.min(8, Math.max(0, d)));
    if (fixed.indexOf('.') >= 0) fixed = fixed.replace(/0+$/, '').replace(/\.$/, '');
    return fixed;
  }

  function clampRound(value, min, max, step, decimals) {
    var n = Number(value);
    if (!isFinite(n)) return null;
    if (typeof min === 'number' && n < min) n = min;
    if (typeof max === 'number' && n > max) n = max;
    if (typeof step === 'number' && step > 0) {
      var steps = Math.round((n - (typeof min === 'number' ? min : 0)) / step);
      n = (typeof min === 'number' ? min : 0) + steps * step;
      /* Rounding back to the step's own precision is what stops `0.30000000004`
       * reaching the stylesheet. */
      n = Number(n.toFixed(Math.min(8, Math.max(0, typeof decimals === 'number' ? decimals : 3))));
    }
    if (typeof min === 'number' && n < min) n = min;
    if (typeof max === 'number' && n > max) n = max;
    return n;
  }

  /* ── NORMALISATION: ONE FIELD ────────────────────────────────────────────────
   * Returns the STORED form (number / string) or `undefined` when the value is
   * not usable. `undefined` is not an error path to paper over: it means "do not
   * override this token", i.e. the theme's own value is used, which is the only
   * honest outcome of an unusable edit. */
  function normalizeField(field, value) {
    if (!field || value === undefined || value === null) return undefined;

    if (field.kind === 'color') {
      var hex = hexToRgb(typeof value === 'string' ? value : '');
      if (!hex) return undefined;
      return hexToHex(hex);
    }

    if (field.kind === 'select') {
      var v = String(value);
      for (var i = 0; i < field.options.length; i += 1) {
        if (field.options[i].value === v) return v;
      }
      return undefined;
    }

    if (field.kind === 'font') {
      /* MATCHED BY ITS PRIMARY FAMILY, not by the whole stack. The themes spell
       * their fallbacks differently on purpose (`theme-1` ends `Inter, system-ui`,
       * a template theme ends `system-ui, sans-serif`), and an option is a choice of
       * FACE — so comparing the full string would show "Do tema" for a theme whose
       * face is on this list and is the same face. The primary family is the part
       * that decides what is painted. */
      var canonical = matchOption(field, value);
      if (canonical) return canonical;
      return undefined;
    }

    if (field.kind === 'length' || field.kind === 'number') {
      /* A bare string like "34px" is accepted and its number taken, because a
       * stored value from an older revision may carry the unit. */
      var raw = typeof value === 'string' ? value.trim() : value;
      var n = parseFloat(raw);
      if (!isFinite(n)) return undefined;
      return clampRound(n, field.min, field.max, field.step, decimalsFor(field.step));
    }

    return undefined;
  }

  function hexToHex(rgb) {
    function h(n) { var s = n.toString(16).toLowerCase(); return s.length === 1 ? '0' + s : s; }
    return '#' + h(rgb.r) + h(rgb.g) + h(rgb.b);
  }

  function normalizeSpace(s) {
    return String(s).replace(/\s+/g, ' ').trim().toLowerCase();
  }

  /* ── THE CSS VALUE FOR ONE FIELD, GIVEN ITS STORED FORM ─────────────────────── */
  function cssValueFor(field, value) {
    if (!field || value === undefined || value === null) return null;
    if (field.kind === 'color') return typeof value === 'string' ? value : null;
    if (field.kind === 'select' || field.kind === 'font') return String(value);
    if (field.kind === 'length' || field.kind === 'number') {
      var n = Number(value);
      if (!isFinite(n)) return null;
      return trimNumber(n, decimalsFor(field.step)) + (field.unit || '');
    }
    return null;
  }

  /* ── THE DECLARATIONS A THEME'S SETTINGS PRODUCE ─────────────────────────────
   * `opts.alphaOf(token)` returns the alpha the theme's OWN stylesheet used for a
   * colour-companion token, so a changed accent keeps the design's own opacity.
   * Returns an array of `[token, value]` pairs, and the ONLY writer of tokens in
   * this module — the DOM layer applies this list verbatim. */
  function declarationsFor(settings, opts) {
    var out = [];
    if (!settings || typeof settings !== 'object') return out;
    var alphaOf = (opts && typeof opts.alphaOf === 'function') ? opts.alphaOf : null;

    for (var i = 0; i < FIELDS.length; i += 1) {
      var field = FIELDS[i];
      if (!Object.prototype.hasOwnProperty.call(settings, field.id)) continue;
      var value = settings[field.id];
      var css = cssValueFor(field, value);
      if (css === null) continue;
      out.push([field.token, css]);

      if (field.kind === 'color' && field.colorKeys) {
        for (var j = 0; j < field.colorKeys.length; j += 1) {
          var key = field.colorKeys[j];
          var fallback = field.colorAlpha && typeof field.colorAlpha[key] === 'number'
            ? field.colorAlpha[key] : 1;
          var alpha = null;
          if (alphaOf) {
            var read = alphaOf(key);
            if (typeof read === 'number' && isFinite(read)) alpha = read;
          }
          if (alpha === null) alpha = fallback;
          var derived = rgbaOf(css, alpha);
          /* `--theme-swatch` is painted as a solid dot; an rgba with a low alpha
           * would make the theme button look washed out, so it keeps the hue and
           * takes full opacity. */
          if (key === '--theme-swatch') derived = css;
          if (derived) out.push([key, derived]);
        }
      }
    }
    return out;
  }

  /* ── THE SETTINGS MAP: { 'theme-N': { fieldId: value } } ───────────────────── */
  function knownThemeNames(names) {
    if (names && names.length) return names;
    var manifest = root && root.SottoThemeManifest;
    if (manifest && manifest.themes && manifest.themes.length) {
      return manifest.themes.map(function (t) { return t.name; });
    }
    return ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5'];
  }

  function isKnownTheme(name, names) {
    var list = knownThemeNames(names);
    for (var i = 0; i < list.length; i += 1) if (list[i] === name) return true;
    return false;
  }

  function normalizeSettings(raw, names) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    var out = {};
    for (var themeName in raw) {
      if (!Object.prototype.hasOwnProperty.call(raw, themeName)) continue;
      if (!isKnownTheme(themeName, names)) continue;
      var entry = raw[themeName];
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
      var clean = {};
      for (var id in entry) {
        if (!Object.prototype.hasOwnProperty.call(entry, id)) continue;
        var field = FIELDS_BY_ID[id];
        if (!field) continue;
        var value = normalizeField(field, entry[id]);
        if (value === undefined) continue;
        clean[id] = value;
      }
      if (Object.keys(clean).length) out[themeName] = clean;
    }
    return out;
  }

  function parseSettings(json, names) {
    if (typeof json !== 'string' || !json) return {};
    var raw;
    try {
      raw = JSON.parse(json);
    } catch (err) {
      /* A corrupt store is not a crash: it is "no edits yet". */
      return {};
    }
    return normalizeSettings(raw, names);
  }

  function serializeSettings(map) {
    return JSON.stringify(map || {});
  }

  /* ── THE DOM LAYER ───────────────────────────────────────────────────────────
   * Everything above is DOM-free so `_main/theme-tune-oracle.js` can gate it in
   * Node; everything below only exists when there is a document. */
  var api = {
    FIELDS: FIELDS,
    FONT_OPTIONS: FONT_OPTIONS,
    STORE_KEY: STORE_KEY,
    allTokens: allTokens,
    hexToRgb: hexToRgb,
    rgbaOf: rgbaOf,
    alphaOfComputed: alphaOfComputed,
    normalizeField: normalizeField,
    normalizeSettings: normalizeSettings,
    parseSettings: parseSettings,
    serializeSettings: serializeSettings,
    cssValueFor: cssValueFor,
    declarationsFor: declarationsFor,
    field: function (id) { return FIELDS_BY_ID[id] || null; },
    fieldByToken: function (token) { return FIELDS_BY_TOKEN[token] || null; }
  };

  if (!root || !root.document) {
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    return;
  }

  var doc = root.document;
  var memoryStore = null;
  var settings = {};
  var appliedTheme = null;
  /* The alpha each colour-companion token has in the CURRENT theme, read from
   * the live computed style so an accent edit keeps the design's opacity. */
  var alphaCache = {};
  var dialog = null;
  var rows = {};
  var button = null;

  function themeElement() {
    return doc.documentElement || null;
  }

  function currentTheme() {
    var el = themeElement();
    var manifest = root.SottoThemeManifest;
    var fallback = (manifest && manifest.fallback) || 'theme-1';
    return (el && el.dataset && el.dataset.theme) || fallback;
  }

  function themeLabel(name) {
    var manifest = root.SottoThemeManifest;
    if (manifest && typeof manifest.byName === 'function') {
      var t = manifest.byName(name);
      if (t) return t.label;
    }
    return String(name);
  }

  function readStore() {
    try {
      var v = root.localStorage.getItem(STORE_KEY);
      return typeof v === 'string' ? v : null;
    } catch (err) {
      return memoryStore;
    }
  }

  function writeStore(json) {
    memoryStore = json;
    try {
      root.localStorage.setItem(STORE_KEY, json);
    } catch (err) {
      /* Silent by design: the edit still took effect in this document. */
    }
  }

  function load() {
    settings = parseSettings(readStore());
    return settings;
  }

  function persist() {
    writeStore(serializeSettings(settings));
  }

  function settingsFor(name) {
    return settings[name] || {};
  }

  function readAlpha(token) {
    var el = themeElement();
    if (!el || !root.getComputedStyle) return null;
    var value = root.getComputedStyle(el).getPropertyValue(token);
    return api.alphaOfComputed(value);
  }

  /* The theme's OWN value for a token: drop our declaration and read what the
   * stylesheet then resolves to. This is the only source of a default here. */
  function baselineFor(token) {
    var el = themeElement();
    if (!el || !el.style) return '';
    var had = el.style.getPropertyValue(token);
    el.style.removeProperty(token);
    var value = root.getComputedStyle
      ? root.getComputedStyle(el).getPropertyValue(token).trim()
      : '';
    if (had !== '') el.style.setProperty(token, had);
    return value;
  }

  function baseline() {
    var out = {};
    for (var i = 0; i < FIELDS.length; i += 1) {
      out[FIELDS[i].id] = baselineFor(FIELDS[i].token);
    }
    return out;
  }

  /* Write ONE theme's edits onto <html>. Every token is written or removed on
   * every pass so a value that was just deleted cannot linger. */
  function apply(name) {
    var themeName = name || currentTheme();
    var el = themeElement();
    if (!el || !el.style) return themeName;

    /* ORDER MATTERS, AND IT IS THE WHOLE REASON THIS IS ONE PASS:
     * (1) every token this module can write is removed FIRST, so what follows
     *     reads the THEME's own values and not the previous theme's edits — the
     *     live case is a theme switch, where the old theme's inline colours are
     *     still on <html> at the moment the new theme's stylesheet starts to
     *     apply. Reading first would carry the old theme's opacity into the new
     *     one's accent.
     * (2) the alpha of each colour companion is read from that clean state.
     * (3) the new declarations are written. Nothing is observed between the
     *     steps: this is synchronous, so no frame paints the in-between. */
    var tokens = allTokens();
    for (var t = 0; t < tokens.length; t += 1) el.style.removeProperty(tokens[t]);

    alphaCache = {};
    for (var i = 0; i < FIELDS.length; i += 1) {
      var field = FIELDS[i];
      if (field.colorKeys) {
        for (var c = 0; c < field.colorKeys.length; c += 1) {
          var a = readAlpha(field.colorKeys[c]);
          if (typeof a === 'number') alphaCache[field.colorKeys[c]] = a;
        }
      }
    }

    var decls = declarationsFor(settingsFor(themeName), {
      alphaOf: function (token) {
        return Object.prototype.hasOwnProperty.call(alphaCache, token) ? alphaCache[token] : null;
      }
    });
    for (var d = 0; d < decls.length; d += 1) {
      el.style.setProperty(decls[d][0], decls[d][1]);
    }

    appliedTheme = themeName;
    return themeName;
  }

  function hasEdits(name) {
    return Object.keys(settingsFor(name || currentTheme())).length > 0;
  }

  function setField(id, value) {
    var field = FIELDS_BY_ID[id];
    if (!field) return false;
    var name = currentTheme();
    var clean = normalizeField(field, value);
    var entry = settings[name] || {};
    if (clean === undefined) delete entry[id];
    else entry[id] = clean;
    if (Object.keys(entry).length) settings[name] = entry;
    else delete settings[name];
    persist();
    apply(name);
    return true;
  }

  function resetField(id) {
    var name = currentTheme();
    var entry = settings[name];
    if (!entry) return false;
    delete entry[id];
    if (Object.keys(entry).length) settings[name] = entry;
    else delete settings[name];
    persist();
    apply(name);
    return true;
  }

  function resetTheme() {
    var name = currentTheme();
    delete settings[name];
    persist();
    apply(name);
    return true;
  }

  /* ── THE DIALOG ──────────────────────────────────────────────────────────────
   * Built once, from `FIELDS`, and appended to `body` OUTSIDE `.panel` — the slab
   * clips its own overflow (`panel.css .panel { overflow: hidden }`), so a modal
   * inside it would be clipped, which is the same reason `#pause-dialog` is a
   * sibling of `.panel`. It wears the pause dialog's own classes for the shell,
   * so it cannot drift from it visually. */
  function el(tag, className, text) {
    var node = doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function buildRow(field, base) {
    var row = el('div', 'tune-row');
    row.dataset.field = field.id;

    var head = el('div', 'tune-row__head');
    var label = el('span', 'tune-row__label', field.label);
    var value = el('span', 'tune-row__value', '');
    head.append(label, value);

    var control;
    if (field.kind === 'color') {
      control = el('input', 'tune-row__color');
      control.type = 'color';
      control.setAttribute('aria-label', field.label);
    } else if (field.kind === 'select' || field.kind === 'font') {
      control = el('select', 'tune-row__select');
      control.setAttribute('aria-label', field.label);
      var options = field.kind === 'font' ? FONT_OPTIONS : field.options;
      for (var i = 0; i < options.length; i += 1) {
        var opt = el('option', null, options[i].label);
        opt.value = options[i].value;
        control.append(opt);
      }
      /* The theme's own family may be a stack this list does not carry. It is
       * offered as its own option instead of being shown as a different one: a
       * select that displays the wrong font is a control that lies. */
      if (field.kind === 'font' && base && !matchOption(field, base)) {
        var own = el('option', null, 'Do tema');
        own.value = base;
        control.prepend(own);
      }
    } else {
      control = el('input', 'tune-row__range');
      control.type = 'range';
      control.min = String(field.min);
      control.max = String(field.max);
      control.step = String(field.step);
      control.setAttribute('aria-label', field.label);
    }

    var reset = el('button', 'tune-row__reset', '↺');
    reset.type = 'button';
    reset.title = 'Voltar ao valor do tema';
    reset.setAttribute('aria-label', 'Restaurar ' + field.label);

    control.addEventListener('input', function () {
      setField(field.id, control.value);
      syncRow(field);
    });
    control.addEventListener('change', function () {
      setField(field.id, control.value);
      syncRow(field);
    });
    reset.addEventListener('click', function () {
      resetField(field.id);
      syncRow(field);
    });

    row.append(head, control, reset);
    rows[field.id] = { row: row, head: head, control: control, value: value, reset: reset, field: field, base: base };
    return row;
  }

  /* Paint one row from the live truth: the stored value if there is one, the
   * theme's own value otherwise. `data-changed` is what makes "what did I edit"
   * visible without reading every control. */
  function syncRow(field) {
    var entry = rows[field.id];
    if (!entry) return;
    var name = currentTheme();
    var stored = settingsFor(name)[field.id];
    var base = entry.base;
    var changed = stored !== undefined;

    if (field.kind === 'color') {
      var hex = changed ? stored : toHex(base);
      entry.control.value = hex || '#000000';
      entry.value.textContent = changed ? String(stored).toUpperCase() : 'do tema';
    } else if (field.kind === 'select' || field.kind === 'font') {
      /* A `select` matches by EXACT string, and a computed custom property is
       * whitespace-normalised by the engine. So the theme's value is mapped to
       * the canonical option value before it is assigned: without this the
       * control would silently fall back to its FIRST option and show a font
       * the theme is not using. */
      entry.control.value = changed ? String(stored) : (matchOption(field, base) || base);
      entry.value.textContent = changed ? labelForOption(field, stored) : 'do tema';
    } else {
      var n = changed ? Number(stored) : parseFloat(base);
      if (isFinite(n)) entry.control.value = String(n);
      entry.value.textContent = changed
        ? (trimNumber(n, decimalsFor(field.step)) + (field.unit || ''))
        : 'do tema';
    }

    entry.row.dataset.changed = changed ? 'true' : 'false';
  }

  /* The canonical option value whose PRIMARY FAMILY equals `value`'s, or null.
   * Comparison is whitespace/case-insensitive and quote-insensitive so a theme's
   * own spelling still matches the option that carries that face. */
  function primaryFamily(value) {
    return normalizeSpace(String(value).split(',')[0]).replace(/["']/g, '').trim();
  }

  function matchOption(field, value) {
    var options = field.kind === 'font' ? FONT_OPTIONS : (field.options || []);
    var want = field.kind === 'font' ? primaryFamily(value) : normalizeSpace(value);
    for (var i = 0; i < options.length; i += 1) {
      var got = field.kind === 'font' ? primaryFamily(options[i].value) : normalizeSpace(options[i].value);
      if (got === want) return options[i].value;
    }
    return null;
  }

  function labelForOption(field, value) {
    var options = field.kind === 'font' ? FONT_OPTIONS : field.options;
    for (var i = 0; i < options.length; i += 1) {
      if (options[i].value === value) return options[i].label;
    }
    return String(value);
  }

  /* A computed colour can arrive as `rgb(242, 233, 216)` or as `#f2e9d8`
   * depending on how the custom property was written; `<input type=color>` only
   * accepts `#rrggbb`, so both forms are converted here. */
  function toHex(value) {
    if (typeof value !== 'string') return null;
    var v = value.trim();
    if (v.charAt(0) === '#') {
      var rgb = api.hexToRgb(v);
      return rgb ? hexToHex(rgb) : null;
    }
    var m = /^rgba?\(([^)]+)\)$/i.exec(v);
    if (!m) return null;
    var parts = m[1].split(/[\s,/]+/).filter(function (p) { return p !== ''; });
    if (parts.length < 3) return null;
    var n = parts.slice(0, 3).map(function (p) { return parseInt(p, 10); });
    if (n.some(function (x) { return !isFinite(x); })) return null;
    return hexToHex({ r: n[0], g: n[1], b: n[2] });
  }

  function syncAll() {
    var name = currentTheme();
    var base = baseline();
    for (var i = 0; i < FIELDS.length; i += 1) {
      var entry = rows[FIELDS[i].id];
      if (!entry) continue;
      entry.base = base[FIELDS[i].id];
      syncRow(FIELDS[i]);
    }
    if (dialog) {
      var title = doc.getElementById('tune-theme-name');
      if (title) title.textContent = themeLabel(name);
      var note = doc.getElementById('tune-note');
      if (note) {
        var count = Object.keys(settingsFor(name)).length;
        note.textContent = count
          ? count + (count === 1 ? ' ajuste só neste tema' : ' ajustes só neste tema')
          : 'Nada ajustado ainda neste tema.';
      }
    }
  }

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = el('dialog', 'pause-dialog tune-dialog');
    dialog.id = 'tune-dialog';
    dialog.setAttribute('aria-labelledby', 'tune-dialog-title');

    var title = el('h2', 'pause-dialog__title', 'Personalizar tema');
    title.id = 'tune-dialog-title';

    var body = el('p', 'pause-dialog__body');
    var nameStrong = el('strong', null, '');
    nameStrong.id = 'tune-theme-name';
    body.append(
      doc.createTextNode('Os ajustes valem só para '),
      nameStrong,
      doc.createTextNode('. Cada tema guarda os seus.')
    );

    var note = el('p', 'pause-dialog__honest', '');
    note.id = 'tune-note';

    var list = el('div', 'tune-body');
    list.id = 'tune-body';
    var base = baseline();
    for (var i = 0; i < FIELDS.length; i += 1) {
      if (FIELDS[i].kind === 'color' || FIELDS[i].kind === 'select' || FIELDS[i].kind === 'font') {
        list.append(buildRow(FIELDS[i], base[FIELDS[i].id]));
      }
    }
    for (var j = 0; j < FIELDS.length; j += 1) {
      if (FIELDS[j].kind === 'length' || FIELDS[j].kind === 'number') {
        list.append(buildRow(FIELDS[j], base[FIELDS[j].id]));
      }
    }

    var buttons = el('div', 'pause-dialog__buttons');
    var reset = el('button', 'dialog-button dialog-button--danger', 'Restaurar este tema');
    reset.type = 'button';
    reset.id = 'tune-reset-button';
    var close = el('button', 'dialog-button', 'Fechar');
    close.type = 'button';
    close.id = 'tune-close-button';

    reset.addEventListener('click', function () {
      resetTheme();
      syncAll();
    });
    close.addEventListener('click', function () {
      if (typeof dialog.close === 'function') dialog.close();
    });

    buttons.append(reset, close);
    dialog.append(title, body, note, list, buttons);
    doc.body.append(dialog);
    return dialog;
  }

  function openDialog() {
    ensureDialog();
    syncAll();
    if (typeof dialog.showModal === 'function') {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute('open', 'open');
    }
  }

  /* ── THE ENTRY POINT ─────────────────────────────────────────────────────────
   * A `.icon-button` in `.panel__controls`, INSERTED BEFORE THE PAUSE BUTTON so
   * the header keeps the owner's own left-to-right ruling (theme, tune, pause,
   * hide) and HIDE STAYS LAST/RIGHTMOST, which `panel.html:265-288` makes
   * load-bearing: the cluster is right-anchored in all five themes, so the last
   * child is the rightmost control. `panel.js` never re-parents the controls, so
   * one `insertBefore` here is enough and nothing has to be re-wired. */
  function ensureButton() {
    var existing = doc.getElementById('tune-button');
    if (existing) { button = existing; return button; }
    var host = doc.querySelector('.panel__controls');
    if (!host) return null;

    var btn = el('button', 'icon-button tune-button');
    btn.type = 'button';
    btn.id = 'tune-button';
    btn.title = 'Personalizar este tema';
    btn.setAttribute('aria-label', 'Personalizar este tema');
    btn.setAttribute('aria-haspopup', 'dialog');

    var svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    var path = doc.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M2.5 4.5h2.2M8.3 4.5h5.2M2.5 8h5.2M11.3 8h2.2M2.5 11.5h1.1M7.2 11.5h6.3');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('stroke-linecap', 'round');
    svg.append(path);
    var dots = [[6.5, 4.5], [9.9, 8], [5.8, 11.5]];
    for (var i = 0; i < dots.length; i += 1) {
      var c = doc.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx', String(dots[i][0]));
      c.setAttribute('cy', String(dots[i][1]));
      c.setAttribute('r', '1.7');
      c.setAttribute('fill', 'none');
      c.setAttribute('stroke', 'currentColor');
      c.setAttribute('stroke-width', '1.5');
      svg.append(c);
    }
    btn.append(svg);
    btn.addEventListener('click', openDialog);

    var pause = doc.getElementById('panel-pause-button');
    if (pause && pause.parentNode === host) host.insertBefore(btn, pause);
    else host.prepend(btn);

    button = btn;
    return button;
  }

  function boot() {
    load();
    apply();
    ensureButton();

    /* A theme switch is a `data-theme` write on <html> (`theme-switcher.js`), and
     * this module has to follow it: the edits belong to the theme, so switching
     * away must REMOVE them and switching back must restore them. Observing the
     * attribute means the two modules never call each other and neither owns the
     * other's order. */
    if (root.MutationObserver) {
      var observer = new root.MutationObserver(function () {
        if (appliedTheme !== currentTheme()) {
          apply();
          if (dialog && dialog.open) syncAll();
        }
      });
      observer.observe(themeElement(), { attributes: true, attributeFilter: ['data-theme'] });
    }

    /* A store written by another document (a second panel window) is picked up
     * on focus, so two windows cannot disagree forever. Cheap: one read. */
    root.addEventListener('focus', function () {
      var before = serializeSettings(settings);
      load();
      if (serializeSettings(settings) !== before) {
        apply();
        if (dialog && dialog.open) syncAll();
      }
    });
  }

  api.apply = apply;
  api.open = openDialog;
  api.settings = function (name) { return settingsFor(name || currentTheme()); };
  api.hasEdits = hasEdits;
  api.set = setField;
  api.resetField = resetField;
  api.resetTheme = resetTheme;
  api.baseline = baseline;
  api.currentTheme = currentTheme;
  api.reload = function () { load(); apply(); };

  root.SottoThemeTune = api;

  var start = function () {
    try {
      boot();
    } catch (err) {
      /* A tuning layer must never take the panel down with it: the captions are
       * the product and this module only decorates them. The page-error hook in
       * the shell's bridge would still report a throw, so silence here is not
       * concealment — but a missing gear is better than a frozen transcript. */
      if (root.console && root.console.warn) root.console.warn('theme-tune: ' + (err && err.message));
    }
  };

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start);
  else start();

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : null));
