/* Sotto — THE FIVE-DESIGN PROBE.
 *
 * WHAT IT IS FOR. "The theme applied" is not a claim about an attribute; it is a
 * claim about what the browser COMPUTED. `document.documentElement.dataset.theme`
 * changing proves the switcher wrote a string, nothing more — and the way this
 * goes wrong silently is that the stylesheet did not load, or the family was never
 * bundled and the panel painted `Segoe UI` under a theme that says `Barlow
 * Condensed`. So this file measures the LIVE document:
 *
 *   * per theme, the computed `font-family`, `font-size`, `font-weight`,
 *     `line-height`, `text-align`, `text-shadow`, `color` and `text-transform` of
 *     the FORMING line, of the NEWEST CLOSED line and of an OLDER SETTLED line,
 *     plus the accent actually painted;
 *   * per theme, the `--accent` token the theme declares on `:root`;
 *   * per theme, whether the direction's OWN family really loaded (`FontFace`
 *     status + `document.fonts.check(name)`), not merely whether it was named;
 *   * per theme, whether that theme's own stylesheet is PRESENT, PARSED and
 *     SCOPED to `:root[data-theme='theme-N']` with a rule that reaches
 *     `.caption__text`;
 *   * whether `localStorage` is usable from THIS document — the panel's
 *     persistence is a claim the owner asked about, and on a `file://` document
 *     Chromium refuses storage unless it was launched with
 *     `--allow-file-access-from-files`;
 *   * the `page-error` channel's own state, because that channel must stay wired.
 *
 * HOW IT GETS OUT, WITHOUT TOUCHING THE SHELL. `sotto_webview.py` is NOT edited
 * (the lane's brief forbids it) and it owns the `--dump-dom` probe, so the payload
 * cannot ride in that constant. Instead the measurement is written into the DOM as
 * ATTRIBUTES on a probe element — `data-theme-probe-count` /
 * `data-theme-probe-0..N`, one JSON document per theme — so a `--dump-dom` run of
 * the REAL app captures every value in the DOM it already dumps. A throw on the
 * `page-error` channel is the second copy, for the run where the DOM dump is not
 * parsed by hand.
 *
 * WHERE IT LOADS. Never in the shipped panel: `_main/_theme-probe-arm.py` writes a
 * COPY of `panel.html` into a temp directory, rewrites the asset URLs and appends
 * `<script src="_theme-probe.js">` to it. `app/panel/panel.html` does not mention
 * this file.
 *
 * ── TWO CORRECTIONS TO THE FIRST VERSION OF THIS FILE (2026-10-07) ───────────
 * 1. THE FIXTURE HAD TWO LINES WHERE THE PANEL HAS THREE, and the one it called
 *    "the closed line" was the WRONG one. `panel.js` marks only the FRESHEST
 *    settled row `.caption--latest` (line 444-446: the flag is moved off the
 *    previous owner and onto the row that just closed), so `.caption--latest` is
 *    *the line that was live a moment ago*, not the history column. Measuring it
 *    as "the history" made the probe demand that the freshest settled row look
 *    identical to one from ten minutes back. It now builds all three rows the real
 *    list holds, in the real order — `caption` (older, settled), `caption
 *    caption--latest` (just closed), `caption caption--provisional` (live, last
 *    child) — and states which claim belongs to which row.
 * 2. `getMatchedCSSRules` DOES NOT EXIST in this Chromium (checked: the string is
 *    absent from the dumped DOM), so that assertion returned null, the judge
 *    coerced it to `[]`, and EVERY theme failed a check that could never pass.
 *    The replacement reads the theme's own `CSSStyleSheet` out of
 *    `document.styleSheets` and asserts what the old check was reaching for:
 *    present, parsed, `:root[data-theme=…]`-scoped, and a rule that names
 *    `.caption__text`.
 *
 * THE HARNESS OPS (via `location.hash`, the affordance `surface.js` also uses):
 *   #theme-probe-op=measure            the default: measure all five and restore
 *   #theme-probe-op=set&theme-probe-theme=theme-3   choose a theme, then report
 *   #theme-probe-op=read               report the theme the document CAME UP in
 * The last two exist so PERSISTENCE is a measurement: load once with `set`, then
 * load a SECOND, independent document with `read` against the same profile
 * directory and require it to arrive already wearing what was stored.
 */
(function () {
  'use strict';

  var THEMES = [
    { name: 'theme-1', label: 'Teleprompter', accent: '#f2e9d8', family: 'Barlow Condensed', weight: 700, size: 30 },
    { name: 'theme-2', label: 'Broadcast', accent: '#ff6a55', family: 'IBM Plex Mono', weight: 600, size: 20 },
    { name: 'theme-3', label: 'Manuscrito', accent: '#a9c1d9', family: 'Newsreader', weight: 400, size: 23 },
    { name: 'theme-4', label: 'Cinema Card', accent: '#e4b363', family: 'Fraunces', weight: 400, size: 24 },
    { name: 'theme-5', label: 'Instrumento', accent: '#5fd3a7', family: 'Space Grotesk', weight: 700, size: 24 }
  ];

  var REPORT = {
    probe: 'sotto-theme-probe/2',
    href: String(location.href),
    readyState: String(document.readyState),
    rootThemeAttribute: String(document.documentElement.getAttribute('data-theme')),
    themes: [],
    errors: []
  };

  function hashParam(key) {
    var m = new RegExp('(?:^|[#&])' + key + '=([A-Za-z0-9_-]+)').exec(String(location.hash));
    return m ? m[1] : null;
  }

  /* `data-theme-probe-op` = 'measure' (default) keeps the real wiring. Anything
   * else removes every theme stylesheet from the document, so the SAME instrument
   * must go RED: the families go back to the system fallback, the rail disappears
   * and the accent reads the base panel's colour. An instrument that cannot say no
   * is not an instrument. */
  var op = hashParam('theme-probe-op') || 'measure';
  REPORT.op = op;

  function unlinkThemes() {
    var removed = [];
    var links = document.querySelectorAll('link[rel="stylesheet"]');
    for (var i = 0; i < links.length; i += 1) {
      var href = links[i].getAttribute('href') || '';
      if (href.indexOf('themes/theme-') >= 0 && href.indexOf('fonts.css') < 0) {
        removed.push(href);
        links[i].parentNode.removeChild(links[i]);
      }
    }
    return removed;
  }

  /* ── the theme's OWN stylesheet, read as the browser parsed it ─────────────
   * This is the honest replacement for the dead `getMatchedCSSRules` call: it
   * answers "is theme-N.css really in this document, really parsed, and does it
   * really carry a rule for the caption text, scoped to this theme". */
  function themeSheet(theme) {
    var out = {
      file: theme.name + '.css', found: false, rules: 0, rootScoped: 0,
      captionTextRules: 0, error: null
    };
    /* CSSOM SERIALISES ATTRIBUTE SELECTORS WITH DOUBLE QUOTES: the stylesheet
     * says `:root[data-theme='theme-1']` and `rule.selectorText` hands back
     * `:root[data-theme="theme-1"]`. Comparing the two literally reported
     * "theme-1.css carries no rule scoped to :root[data-theme='theme-1']" for a
     * rule that was right there — so the quotes come off BOTH sides first. */
    var rootSel = ':root[data-theme=' + theme.name + ']';
    var norm = function (s) { return String(s || '').replace(/["']/g, ''); };
    for (var i = 0; i < document.styleSheets.length; i += 1) {
      var s = document.styleSheets[i];
      var href = String(s.href || '');
      if (href.lastIndexOf('/' + theme.name + '.css') < 0) continue;
      out.found = true;
      var rules = null;
      try {
        rules = s.cssRules;
      } catch (e) {
        out.error = String(e && e.name) + ': ' + String(e && e.message).slice(0, 100);
        return out;
      }
      if (!rules) { out.error = 'no cssRules'; return out; }
      out.rules = rules.length;
      for (var r = 0; r < rules.length; r += 1) {
        var sel = norm(rules[r].selectorText);
        if (!sel || sel.indexOf(rootSel) < 0) continue;
        out.rootScoped += 1;
        if (sel.indexOf('.caption__text') >= 0) out.captionTextRules += 1;
      }
      return out;
    }
    return out;
  }

  /* ── is `localStorage` usable from THIS document? ─────────────────────────
   * The switcher swallows a throw on purpose (`readStore`/`writeStore` fall back
   * to an in-memory value), so a document that cannot persist looks exactly like
   * a document that can until the next launch. This canary is the difference. */
  function storeVerdict() {
    var v = { readable: false, writable: false, roundTrip: null, error: null };
    try {
      var k = 'sotto.probe.canary';
      window.localStorage.setItem(k, 'ok');
      v.writable = true;
      v.roundTrip = window.localStorage.getItem(k);
      window.localStorage.removeItem(k);
      v.readable = true;
    } catch (e) {
      v.error = String(e && e.name) + ': ' + String(e && e.message).slice(0, 140);
    }
    try {
      v.sottoThemeLast = window.SottoTheme ? String(window.SottoTheme.last()) : null;
      v.sottoThemeCurrent = window.SottoTheme ? String(window.SottoTheme.current()) : null;
      v.apiPresent = Boolean(window.SottoTheme);
    } catch (e2) {
      v.apiPresent = false;
    }
    return v;
  }

  function err(message) {
    REPORT.errors.push(String(message));
    try {
      throw new Error('SOTTO_THEME_PROBE ' + message);
    } catch (e) {
      /* The only way a page can push to the shell's `page-error` channel. */
      setTimeout(function () { throw e; }, 0);
    }
  }

  /* ── THE THREE ROWS THE REAL LIST HOLDS, IN THE REAL ORDER ────────────────
   * Built once, inserted into the real `#caption-list`, so every rule that
   * reaches them does so through the real cascade — including the `panel.css`
   * rules a theme has to out-specificity. */
  function settledLi(id, time, text) {
    var li = document.createElement('li');
    li.className = 'caption';
    li.id = id;
    var t = document.createElement('span');
    t.className = 'caption__time';
    t.textContent = time;
    var b = document.createElement('span');
    b.className = 'caption__text';
    b.textContent = text;
    li.appendChild(t);
    li.appendChild(b);
    return li;
  }

  function buildFixture() {
    var list = document.getElementById('caption-list');
    if (!list) return null;

    /* 1. an OLDER settled line — this is "the history" the design talks about */
    var history = settledLi('theme-probe-history', '10:23:58',
      'O som chega antes da imagem.');

    /* 2. the FRESHEST settled line — panel.js moves `.caption--latest` here */
    var latest = settledLi('theme-probe-latest', '10:24:04',
      'Quando a frase fecha, ela ganha peso — e fica.');
    latest.classList.add('caption--latest');

    /* 3. the LIVE line, last child, exactly as `renderProvisional` appends it */
    var forming = document.createElement('li');
    forming.className = 'caption caption--provisional';
    forming.id = 'theme-probe-forming';
    var t1 = document.createElement('span');
    t1.className = 'caption__time';
    t1.textContent = '10:24:01';
    var body1 = document.createElement('span');
    body1.className = 'caption__text';
    var confirmed = document.createElement('span');
    confirmed.className = 'caption__confirmed';
    confirmed.textContent = 'A legenda nasce enquanto a frase';
    var provisional = document.createElement('span');
    provisional.className = 'caption__provisional';
    provisional.textContent = ' ainda está em formação ·';
    body1.appendChild(confirmed);
    body1.appendChild(provisional);
    forming.appendChild(t1);
    forming.appendChild(body1);

    list.appendChild(history);
    list.appendChild(latest);
    list.appendChild(forming);
    list.hidden = false;
    var ph = document.getElementById('placeholder');
    if (ph) ph.hidden = true;
    return { history: history, latest: latest, forming: forming };
  }

  function read(el) {
    if (!el) return null;
    var cs = getComputedStyle(el);
    return {
      family: cs.fontFamily,
      size: cs.fontSize,
      weight: cs.fontWeight,
      style: cs.fontStyle,
      lineHeight: cs.lineHeight,
      letterSpacing: cs.letterSpacing,
      transform: cs.textTransform,
      textAlign: cs.textAlign,
      textShadow: cs.textShadow,
      color: cs.color,
      borderLeftColor: cs.borderLeftColor,
      borderLeftWidth: cs.borderLeftWidth,
      borderLeftStyle: cs.borderLeftStyle
    };
  }

  /* A RAIL IS ONLY A RAIL IF IT PAINTS. The first version of this probe tested
   * the two keywords alone and called a `0px solid` border "a rail kept" (four
   * themes failed a border that is invisible), and then — with the width fixed —
   * called `panel.css`'s `border-left: 2px solid transparent` on every `.caption`
   * a rail too. Three facts decide it and all three are read: the style keyword,
   * the WIDTH, and the ALPHA of the colour. A transparent 2 px border is a gutter,
   * not a mark. */
  function alphaOf(color) {
    var s = String(color || '');
    if (s === 'transparent') return 0;
    var m = /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)/.exec(s);
    if (!m) return 1;
    return m[4] === undefined ? 1 : parseFloat(m[4]);
  }

  function railVisible(box) {
    if (!box) return null;
    return box.borderLeftStyle !== 'none' &&
      parseFloat(box.borderLeftWidth) > 0 &&
      alphaOf(box.borderLeftColor) > 0.02;
  }

  function rgb(hex) {
    var h = hex.replace('#', '');
    return 'rgb(' + parseInt(h.slice(0, 2), 16) + ', ' +
      parseInt(h.slice(2, 4), 16) + ', ' +
      parseInt(h.slice(4, 6), 16) + ')';
  }

  function token(name) {
    return String(getComputedStyle(document.documentElement)
      .getPropertyValue(name) || '').trim();
  }

  /* WHICH WEIGHTS THE BUNDLE REALLY CARRIES FOR A FAMILY.
   *
   * This exists because of a defect that no other check here could see: theme 1
   * declares `--weight-closed: 400`, the bundle shipped ONLY Barlow Condensed 700,
   * and CSS font matching takes the nearest available face — so the settled
   * history painted the LIVE line's heavy strokes and the "history recedes" half
   * of the Teleprompter direction was silently carried by size and hue alone. A
   * `font-weight: 400` in `getComputedStyle` is the AUTHOR's number, not a face
   * that exists; `document.fonts` is where the faces are. */
  function facesFor(family) {
    var out = [];
    if (!document.fonts || !document.fonts.forEach) return out;
    try {
      document.fonts.forEach(function (f) {
        if (String(f.family || '').replace(/["']/g, '') === family) out.push(String(f.weight));
      });
    } catch (e) { /* reported by the empty list */ }
    return out;
  }

  function measure(theme, fx) {
    /* THE ELEMENT THAT CARRIES THE CAPTION IS `.caption__text`, not the `<li>`:
     * the `<li>` is the grid (time column + text column) and keeps panel.css's own
     * 15px for the gutter. Reading the `<li>` is the mistake this probe made
     * first — it reported every theme at `15px/400` while the themes were in fact
     * applying. */
    var textEl = fx.forming.querySelector('.caption__text');
    var forming = read(textEl);
    var history = read(fx.history.querySelector('.caption__text'));
    var latest = read(fx.latest.querySelector('.caption__text'));
    var historyBox = read(fx.history);
    var latestBox = read(fx.latest);
    var formingBox = read(fx.forming);
    var confirmed = read(fx.forming.querySelector('.caption__confirmed'));
    var provisional = read(fx.forming.querySelector('.caption__provisional'));

    var btn = document.getElementById('theme-button');
    var btnCS = btn ? getComputedStyle(btn) : null;
    var swatch = btn ? getComputedStyle(btn, '::after').backgroundColor : null;
    var wordmark = document.querySelector('.wordmark__name');
    var wordmarkColor = wordmark ? getComputedStyle(wordmark).color : null;
    var accentToken = token('--accent');

    return {
      name: theme.name,
      label: theme.label,
      directionAccent: theme.accent,
      directionAccentRgb: rgb(theme.accent),
      rootAttribute: String(document.documentElement.getAttribute('data-theme')),
      /* the token the THEME declares, and the token panel.css aliases it to */
      accentToken: accentToken,
      accentTokenIsDirection: accentToken.toLowerCase() === theme.accent.toLowerCase(),
      fontSansToken: token('--font-sans'),
      forming: forming,
      history: history,
      latest: latest,
      lineBox: formingBox,
      historyLineBox: historyBox,
      latestLineBox: latestBox,
      confirmed: confirmed,
      provisional: provisional,
      familyUnderTest: theme.family,
      familyResolved: forming.family.replace(/["']/g, '').split(',')[0].trim() === theme.family,
      familyQuotedInDeclaration: forming.family.indexOf('"' + theme.family + '"') >= 0,
      /* `.caption__text` computed values, per row, so the three claims the design
       * makes can be told apart: the live line SHINES, the freshest settled line
       * just closed, the history RECEDES. */
      liveShines: forming.textShadow !== 'none',
      liveShadowsDiffer: forming.textShadow !== history.textShadow,
      historyFlat: history.textShadow === 'none',
      liveRailVisible: railVisible(formingBox),
      historyRailVisible: railVisible(historyBox),
      latestRailVisible: railVisible(latestBox),
      liveAccentPainted: formingBox.borderLeftColor === rgb(theme.accent) && railVisible(formingBox),
      wordmarkColor: wordmarkColor,
      wordmarkPaintedAccent: wordmarkColor === rgb(theme.accent),
      liveTextIsAccent: forming.color === rgb(theme.accent),
      liveBiggerThanHistory: parseFloat(forming.size) > parseFloat(history.size),
      liveBiggerThanLatest: parseFloat(forming.size) > parseFloat(latest.size),
      leftAligned: forming.textAlign === 'left' || forming.textAlign === 'start' ||
        forming.textAlign === 'justify' || forming.textAlign === '-webkit-auto',
      sheet: themeSheet(theme),
      /* The weights the BUNDLE carries, and whether the two weights this theme
       * actually asks for are among them. `historyWeightCovered` is the assertion
       * that would have caught the Barlow-Condensed-400 gap. */
      bundleWeights: facesFor(theme.family),
      liveWeightCovered: facesFor(theme.family).indexOf(String(forming.weight)) >= 0,
      historyWeightCovered: facesFor(theme.family).indexOf(String(history.weight)) >= 0,
      faceKnown: document.fonts ? document.fonts.check('12px "' + theme.family + '"', 'Aãç') : null,
      /* A control NAME that does not exist. If this were ever true, the check above
       * would be answering about nothing. */
      faceKnownControl: document.fonts
        ? document.fonts.check('12px "Sotto No Such Family"', 'Aãç')
        : null,
      buttonLabel: btn ? (btn.querySelector('.theme-button__label') || {}).textContent : null,
      buttonSwatch: swatch,
      buttonSwatchIsAccent: swatch === rgb(theme.accent),
      paintButtonLabel: btnCS ? btnCS.color : null
    };
  }

  /* ── the non-measure ops: `set` and `read` ────────────────────────────────
   * They are what makes PERSISTENCE measurable. `set` chooses a theme through the
   * SHIPPED switcher (so `writeStore` is the shipped one), `read` reports what the
   * document came up wearing before anything touched it. */
  function runOp() {
    var chosen = hashParam('theme-probe-theme');
    REPORT.chosen = chosen;
    REPORT.themeAtLoad = String(document.documentElement.getAttribute('data-theme'));
    if (op === 'set') {
      REPORT.setReturned = window.SottoTheme ? String(window.SottoTheme.set(chosen)) : null;
      REPORT.themeAfterSet = String(document.documentElement.getAttribute('data-theme'));
    }
    REPORT.store = storeVerdict();
    finish();
  }

  /* ── the switch itself ────────────────────────────────────────────────────
   * Through the SHIPPED switcher when it is there, because that is the code the
   * owner's click runs and it is what repaints the button. A raw attribute write
   * was the first version's path and it left the button reading "Teleprompter"
   * under all five themes — the probe was measuring a document the switcher did
   * not know it was wearing. `persist: false` keeps the store clean, because the
   * persistence arms are the only ones allowed to write it. */
  function switchTo(name) {
    var via = 'attribute';
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
      via = 'SottoTheme.set';
    }
    document.documentElement.setAttribute('data-theme', name);
    return via;
  }

  function main() {
    if (op !== 'measure') { runOp(); return; }

    REPORT.sheets = (function () {
      var out = [];
      for (var i = 0; i < document.styleSheets.length; i += 1) {
        var s = document.styleSheets[i];
        var rules = null;
        try { rules = s.cssRules ? s.cssRules.length : 0; } catch (e) { rules = 'inaccessible'; }
        out.push({ href: String(s.href || '(inline)').replace(/^.*[\\/]/, ''), rules: rules });
      }
      return out;
    }());

    var links = document.querySelectorAll('link[rel="stylesheet"]');
    var seen = [];
    for (var i = 0; i < links.length; i += 1) {
      seen.push(String(links[i].getAttribute('href') || '').replace(/^.*[\\/]/, ''));
    }
    REPORT.stylesheetsLinked = seen;
    REPORT.fontsLinked = seen.indexOf('fonts.css') >= 0;
    REPORT.themeCountLinked = seen.filter(function (h) { return /^theme-\d\.css$/.test(h); }).length;
    REPORT.fontSourceWoff2 = 0;
    for (var f = 0; f < document.styleSheets.length; f += 1) {
      var sheet = document.styleSheets[f];
      var rules = null;
      try { rules = sheet.cssRules; } catch (e) { continue; }
      if (!rules) continue;
      for (var r = 0; r < rules.length; r += 1) {
        var rule = rules[r];
        if (rule.type === 5 || (rule.constructor && rule.constructor.name === 'CSSFontFaceRule')) {
          if (String(rule.cssText || '').indexOf('woff2') >= 0) REPORT.fontSourceWoff2 += 1;
        }
      }
    }

    /* The manifest the switcher reads, and the five labels in the owner's order. */
    REPORT.manifest = (function () {
      var m = window.SottoThemeManifest;
      if (!m) return null;
      return {
        fallback: m.fallback,
        names: m.themes.map(function (t) { return t.name; }),
        labels: m.themes.map(function (t) { return t.label; }),
        swatches: m.themes.map(function (t) { return t.swatch; })
      };
    }());

    /* The `page-error` channel is wired by the SHELL's injected bridge, not by
     * panel.html: if `window.sotto` exists it is the shell's bridge, and the
     * channel's own listener is what the shell installed. This page cannot read a
     * native listener, so what is asserted here is the panel-side half that IS
     * visible — the bridge object exists, so the shell's injector ran. */
    REPORT.pageErrorChannel = {
      bridgePresent: typeof window.sotto === 'object' && window.sotto !== null,
      bridgeMethods: (typeof window.sotto === 'object' && window.sotto !== null)
        ? ['pushCaption', 'onCaption'].filter(function (m) { return typeof window.sotto[m] === 'function'; })
        : []
    };

    REPORT.store = storeVerdict();

    var fx = buildFixture();
    if (!fx) { err('no #caption-list to measure'); return finish(); }

    var pending = [];
    THEMES.forEach(function (t) {
      if (document.fonts && document.fonts.load) {
        pending.push(document.fonts.load(t.weight + ' 20px "' + t.family + '"')
          .then(function (faces) { t._facesLoaded = faces.length; },
            function (e) { t._facesLoaded = 'error:' + String(e && e.name); }));
      }
    });

    var run = function () {
      /* `document.fonts.ready` resolves when the faces the document has ASKED for
       * are done — and a document that has asked for none resolves it at once, so
       * a run that silently skipped every font load would still be "ready". The
       * guard is a real timer as well, so the probe can never hang a dump. */
      var done = false;
      var go = function () {
        if (done) return;
        done = true;
        THEMES.forEach(function (t) {
          REPORT.switchPath = switchTo(t.name);
          var m = measure(t, fx);
          m.facesLoadedByApi = t._facesLoaded;
          REPORT.themes.push(m);
        });
        /* Leave the document wearing the theme it started in, and a KNOWN theme,
         * so the dumped DOM is comparable run to run. */
        switchTo(REPORT.rootThemeAttribute || 'theme-1');
        finish();
      };
      if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
        document.fonts.ready.then(go, go);
      }
      setTimeout(go, 1500);
    };

    Promise.all(pending).then(run, run);
  }

  function finish() {
    /* The DOM is the channel: attribute values are strings, and the dump
     * truncates nothing that fits in an element. One attribute per theme. */
    var host = document.createElement('div');
    host.id = 'theme-probe';
    host.setAttribute('data-theme-probe-count', String(REPORT.themes.length));
    host.setAttribute('data-theme-probe-summary', JSON.stringify({
      probe: REPORT.probe,
      op: REPORT.op,
      linked: REPORT.stylesheetsLinked,
      fontsLinked: REPORT.fontsLinked,
      themeCountLinked: REPORT.themeCountLinked,
      fontSourceWoff2: REPORT.fontSourceWoff2,
      rootThemeAttribute: REPORT.rootThemeAttribute,
      switchPath: REPORT.switchPath || null,
      themeAtLoad: REPORT.themeAtLoad || null,
      chosen: REPORT.chosen || null,
      setReturned: REPORT.setReturned || null,
      themeAfterSet: REPORT.themeAfterSet || null,
      store: REPORT.store || null,
      manifest: REPORT.manifest || null,
      pageErrorChannel: REPORT.pageErrorChannel || null,
      errors: REPORT.errors
    }));
    REPORT.themes.forEach(function (t, i) {
      host.setAttribute('data-theme-probe-' + i, JSON.stringify(t));
    });
    document.body.appendChild(host);

    /* The second copy, on the channel the shell already logs. One line per run,
     * and only the fields a reader needs to judge. */
    try {
      throw new Error('SOTTO_THEME_PROBE ' + JSON.stringify({
        probe: REPORT.probe,
        op: REPORT.op,
        themeAtLoad: REPORT.themeAtLoad || null,
        themeAfterSet: REPORT.themeAfterSet || null,
        store: REPORT.store || null,
        themes: REPORT.themes.map(function (t) {
          return [t.name, t.familyResolved, t.forming.family.split(',')[0],
            t.forming.size, t.forming.weight, t.forming.lineHeight, t.forming.textAlign,
            t.forming.textShadow, t.history.size, t.history.weight, t.history.textShadow,
            t.liveRailVisible, t.historyRailVisible, t.accentToken, t.faceKnown,
            t.facesLoadedByApi, t.bundleWeights, t.historyWeightCovered];
        }),
        errors: REPORT.errors
      }));
    } catch (e) {
      setTimeout(function () { throw e; }, 0);
    }
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(main, 0);
  } else {
    document.addEventListener('DOMContentLoaded', main);
  }
}());
