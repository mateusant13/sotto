/* Sotto - the deferred-asset loader.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * app/panel/panel.html loads its whole design system up front, before the first
 * caption exists: five theme stylesheets, the cinematic and panel-designs
 * stylesheets, the 812 978-byte skin manifest (skins/skins.js) and
 * skin-host.js. On file:// every one of those bytes is read from disk and
 * parsed/compiled on the critical path of the first frame.
 *
 * This module makes those five resources an EMPTY body until the panel actually
 * needs them, and fetches the real bytes in dependency order when it does. It is
 * injected by the shell's preload (AddScriptToExecuteOnDocumentCreatedAsync), i.e.
 * BEFORE any page script - the only position that can both see the document's own
 * data-theme write from theme-switcher.js and pre-empt the panel's first paint.
 *
 * WHAT IS DEFERRED, AND WHY EACH IS SAFE TO DEFER (scopes measured on disk)
 * ----------------------------------------------------------------------
 *   themes/cinematic.css    312 230 B  every rule is scoped to
 *                                     :root[data-theme^='cine-'] (or an exact cine
 *                                     name). A base theme paints without it.
 *   themes/panel-designs.css 128 716 B  every rule is scoped to
 *                                     :root[data-theme='pd-*'] - five selectors,
 *                                     five themes.
 *   skins/skins.js           812 978 B  window.SOTTO_SKINS - read ONCE at parse
 *                                     time by skin-host.js. Deferring it is only
 *                                     safe if skin-host.js is deferred too, so the
 *                                     pair is deferred together.
 *   skin-host.js        22 712 B  mounts the frozen vendor designs in a
 *                                     shadow root. panel.js guards every call
 *                                     behind window.SottoSkin && .active.
 *   skin-layout.css           11 210 B  its rules are gated on body[data-skin],
 *                                     a state only skin-host.js sets.
 *
 * THE ORDERING CONTRACT (measured, not assumed)
 * --------------------------------------------
 *   1. skins/skins.js must LOAD AND EXECUTE before skin-host.js PARSES.
 *      skin-host.js does 'var MANIFEST = window.SOTTO_SKINS || null' at parse
 *      time and never re-reads it, so a skin manifest that arrives later is
 *      invisible to an already-running skin-host. Hence this order, never the
 *      reverse.
 *   2. skin-layout.css must be in the document before skin-host.js mounts,
 *      because it is what hides the panel's own DOM while a skin is up.
 *   3. cinematic.css / panel-designs.css constrain nothing else.
 *
 * WHY THE THEME IS READ FROM THE DOCUMENT AND NOT GUESSED
 * -------------------------------------------------------
 * The panel's own switcher resolves its startup theme as
 *   localStorage.getItem('sotto.theme')
 *     || document.documentElement.getAttribute('data-theme')
 *     || SottoThemeManifest.fallback
 * (theme-switcher.js readStore/currentTheme). The document's own
 * <html data-theme="theme-1"> is only the FALLBACK: the WebView2 user-data-dir
 * is persistent, so a theme the owner chose in an earlier session can be the
 * theme of this one. Guessing 'theme-1' here would break the first paint of
 * every session that starts on a cine or pd theme.
 *
 * FAILURE MODE, STATED PLAINLY
 * ----------------------------
 * The shell serves an empty 200 for a deferred URL unless the page has asked for
 * the real bytes. If the ask never lands, the panel renders the base theme with
 * no skin - the same picture as today with skins.js absent. There is no silent
 * retry loop: on a fast local scheme, a self-retrying fetch is how a diagnostic
 * becomes a hang.
 */

(function () {
  'use strict';

  /* The one table: which theme shape needs which deferred assets. Keys are a
   * prefix test on the theme id, so a new theme shape following the same
   * convention is covered without a code change. */
  var NEEDS = {
    /* The five owner themes need nothing deferred: themes/theme-{1..5}.css are
     * render-blocking stylesheets in <head>, needed by the first paint for any
     * of the five. */
    'theme-': [],
    /* 25 themes -> themes/cinematic.css + the skin pair + the layout that hides
     * the stock panel while the skin is up. */
    'cine-': ['themes/cinematic.css', 'skins/skins.js', 'skin-host.js',
              'skin-layout.css'],
    /* The second design zip's five themes -> themes/panel-designs.css only.
     * They reuse the stock panel DOM, so no skin pair is involved. */
    'pd-': ['themes/panel-designs.css']
  };

  var ASKED = {};
  /* url -> the callbacks waiting for the shell to CONFIRM the ask. An element
   * injected before that confirmation is answered with the gate's EMPTY 200 and
   * the real bytes are never fetched (see `ask` for the measured 10-55 ms). */
  var WAITING = {};
  /* url -> how many 50 ms turns this ask has waited for pywebview's api, which
   * is the only channel whose promise resolves AFTER Python's dispatch() has
   * run. After 2 s this falls back to the shell's fire-and-forget channel. */
  var WAITED = {};
  var LOG = [];

  function log(kind, detail) {
    LOG.push({ kind: kind, detail: detail, at: Date.now() });
    try {
      if (window.console && window.console.debug) {
        window.console.debug('sotto-lazy: ' + kind + ' ' + detail);
      }
    } catch (err) { /* a closed console must never break the loader */ }
  }

  /* Same resolution order as theme-switcher.js: the store, then the document's
   * own attribute, then the manifest's declared fallback. All three are read
   * defensively - a SecurityError from localStorage over file:// is a normal
   * outcome here, not an error to report. */
  /* SAME resolution order as theme-switcher.js, verbatim:
   *   localStorage.getItem('sotto.theme')
   *     || document.documentElement.getAttribute('data-theme')
   *     || SottoThemeManifest.fallback
   *     || 'theme-1'
   * The preload runs BEFORE any page script, so the document attribute is still
   * the static <html data-theme="theme-1"> fallback at this point. Reading it
   * first would miss a theme the owner stored in an earlier session. */
  function currentTheme() {
    try {
      var stored = window.localStorage.getItem('sotto.theme');
      if (typeof stored === 'string' && stored) return stored;
    } catch (err) { /* per-document opaque storage, or refused */ }
    try {
      var el = document.documentElement;
      var fromDom = el && el.getAttribute ? el.getAttribute('data-theme') : null;
      if (fromDom) return fromDom;
    } catch (err) { /* no documentElement yet: the preload runs very early */ }
    try {
      var man = window.SottoThemeManifest;
      if (man && man.fallback) return man.fallback;
    } catch (err) { /* manifest not parsed yet */ }
    return 'theme-1';
  }

  function needsFor(theme) {
    var keys = Object.keys(NEEDS);
    for (var i = 0; i < keys.length; i += 1) {
      if (theme.indexOf(keys[i]) === 0) return NEEDS[keys[i]];
    }
    return [];
  }

  /* Ask the shell for the real bytes of one deferred URL, and run `done` ONLY
   * once the shell has CONFIRMED it.
   *
   * WHY THE CALLBACK EXISTS, AND IT IS MEASURED. The shell's gate answers a
   * request for a URL the page has not asked for with an EMPTY 200, and the
   * ask travels as a MESSAGE while the <link>/<script> element the caller
   * injects is requested IMMEDIATELY. MEASURED 2026-10-13 on a `cine-cellar`
   * arm, after the shell's dispatch map was repaired and the asks DID arrive:
   *     PANEL_LAZY_EMPTY  url=themes/cinematic.css   50.476
   *     PANEL_LAZY_EMPTY  url=skins/skins.js         50.485
   *     PANEL_LAZY_EMPTY  url=skin-host.js           50.494
   *     PANEL_LAZY_EMPTY  url=skin-layout.css        50.521
   *     PANEL_LAZY_ALLOW  url=themes/cinematic.css   50.531   <- 55 ms late
   *     PANEL_LAZY_ALLOW  url=skins/skins.js         50.531
   *     PANEL_LAZY_ALLOW  url=skin-host.js           50.531
   *     PANEL_LAZY_ALLOW  url=skin-layout.css        50.531
   * and the page's own readback in the same run: `cinRules=0` (the 350 KB
   * cinematic sheet carried ZERO rules), `SOTTO_SKINS=undefined`,
   * `window.SottoSkin=undefined`. So the ask ARRIVED and the gate OPENED, and
   * the owner's five assets still loaded EMPTY -- the request had already been
   * answered. The ordering, not the channel, was the remaining defect.
   *
   * THE ONE ASK THAT CAN BE AWAITED is pywebview's own api: `api.dispatch`
   * resolves its promise when Python's `SottoHost.dispatch` RETURNS, i.e.
   * strictly after `LazyAssetGate.allow()` has run. When that api is not there
   * yet, this waits for it (50 ms turns, up to 2 s) instead of racing it, and
   * then falls back to the shell's fire-and-forget `window.sotto.dispatch`.
   * Every path ends in `done`, so an inject can never be skipped entirely.
   */
  function ask(url, done) {
    var finish = (typeof done === 'function') ? done : function () {};
    if (ASKED[url]) {
      /* A second ask for a URL already in flight must NOT inject now: that is
       * the same race. Queue behind the confirmation instead. */
      if (WAITING[url]) { WAITING[url].push(finish); } else { finish(); }
      return;
    }
    var s = window.sotto;
    var api = window.pywebview && window.pywebview.api;
    var canAwait = !!(api && typeof api.dispatch === 'function');
    var hasSotto = !!(s && typeof s.dispatch === 'function');
    if (!canAwait && !hasSotto) {
      setTimeout(function () { ask(url, done); }, 100);
      return;
    }
    if (!canAwait) {
      WAITED[url] = (WAITED[url] || 0) + 1;
      if (WAITED[url] <= 40) {
        setTimeout(function () { ask(url, done); }, 50);
        return;
      }
    }
    ASKED[url] = true;
    WAITING[url] = [finish];
    log('ask', url);
    var settled = false;
    var settle = function () {
      if (settled) return;
      settled = true;
      var list = WAITING[url] || [];
      delete WAITING[url];
      for (var i = 0; i < list.length; i += 1) {
        try { list[i](); } catch (err) { log('ask-callback-failed', url); }
      }
    };
    if (canAwait) {
      /* A SHELL THAT NEVER ANSWERS MUST NOT LEAVE THE INJECT UNRUN: the
       * timeout is the floor under this, and the worst case it buys is
       * today's behaviour (the element is injected and may be answered
       * empty), never a page that waits forever. */
      setTimeout(settle, 1500);
      try {
        Promise.resolve(api.dispatch(JSON.stringify({
          kind: 'lazy-asset', payload: { url: String(url) }
        }))).then(settle, function (err) {
          log('ask-failed', url + ' ' + (err && err.message ? err.message : err));
          settle();
        });
        return;
      } catch (err) {
        log('ask-failed', url + ' ' + (err && err.message ? err.message : err));
      }
    }
    try {
      if (hasSotto) { s.dispatch('lazy-asset', { url: String(url) }); }
    } catch (err) {
      log('ask-failed', url + ' ' + (err && err.message ? err.message : err));
    }
    settle();
  }

  /* Inject one element. tag is 'link' or 'script'. Attributes go through the
   * DOM API, never innerHTML: a table value is not markup. */
  function inject(tag, attrs) {
    var el;
    try { el = document.createElement(tag); }
    catch (err) { log('inject-failed', tag); return null; }
    var names = Object.keys(attrs);
    for (var i = 0; i < names.length; i += 1) {
      try { el.setAttribute(names[i], attrs[names[i]]); }
      catch (err) { /* an unwritable attribute is not fatal for the rest */ }
    }
    /* Scripts that must run in order and links that must block painting both
     * belong in <head>. document.write only works during parse and we are
     * usually past it. */
    var host = (document.head || document.documentElement || document.body);
    if (host && host.appendChild) {
      try { host.appendChild(el); }
      catch (err) {
        log('append-failed', tag + ' ' + (err && err.message ? err.message : err));
      }
    }
    return el;
  }

  /* The skin pair, in the ORDER THE CONTRACT REQUIRES:
   *   skins.js       -> sets window.SOTTO_SKINS
   *   skin-host.js   -> reads it at parse time and mounts
   *   skin-layout.css-> hides the stock panel while the skin is up */
  function loadSkinPair() {
    /* ASK BEFORE INJECT, for all three. The shell's gate answers an un-asked
     * deferred URL with an EMPTY body, so an inject without an ask gives a
     * script that parses to nothing: window.SOTTO_SKINS stays undefined and
     * skin-host.js mounts nothing while cinematic.css DOES arrive, i.e. a cine
     * theme half-applied. Measured: the first revision of this file asked only
     * for the theme stylesheet and shipped exactly that half. */
    ask('skins/skins.js', function () {
      /* THE DOM IS THE LATCH, and it is checked INSIDE the confirmation: a
       * second settle() that arrives while this ask is in flight must not
       * inject a second copy, and must not inject before the shell allowed it. */
      if (hasSkinScript()) return;
      var step = inject('script', { src: 'skins/skins.js',
                                     'data-sotto-lazy': 'skin' });
      log('inject', 'skins/skins.js' + (step ? '' : ' FAILED'));
      if (!step) return;
      /* 812 KB of array literals executes synchronously on load, so by the time the
       * next line runs window.SOTTO_SKINS exists. */
      step.addEventListener('load', function () {
        ask('skin-host.js', function () {
          var host = inject('script', { src: 'skin-host.js',
                                         'data-sotto-lazy': 'skin' });
          log('inject', 'skin-host.js' + (host ? '' : ' FAILED'));
          if (!host) return;
          host.addEventListener('load', function () {
            ask('skin-layout.css', function () {
              inject('link', { rel: 'stylesheet', href: 'skin-layout.css',
                               'data-sotto-lazy': 'skin' });
              log('inject', 'skin-layout.css');
            });
          }, false);
        });
      }, false);
    });
  }

  function hasThemeSheet(url) {
    return !!document.querySelector('link[data-sotto-lazy="theme"]'
      + '[href$="' + url + '"]');
  }

  function hasSkinScript() {
    return !!document.querySelector('script[data-sotto-lazy="skin"]');
  }

  /* Idempotent by construction: an element already in the document is never
   * injected twice, and a URL already asked for is never asked again. Both the
   * MutationObserver and the public reload() path go through here, so a theme
   * switch that fires twice cannot append a second 812 KB manifest. */
  function loadFor(theme) {
    var list = needsFor(theme);
    if (!list.length) return false;
    var changed = false;
    for (var i = 0; i < list.length; i += 1) {
      var url = list[i];
      if (url === 'skins/skins.js') {
        if (!hasSkinScript()) { loadSkinPair(); changed = true; }
        continue;
      }
      /* skin-host.js and skin-layout.css ride inside loadSkinPair's load
       * callbacks, in the order the contract requires. */
      if (url === 'skin-host.js' || url === 'skin-layout.css') continue;
      if (!hasThemeSheet(url)) {
        /* THE URL IS BOUND PER ITERATION, AND THAT IS NOT COSMETIC. `var url`
         * is function-scoped, and this callback now runs AFTER the ask has been
         * confirmed -- by which time the loop has advanced. MEASURED
         * 2026-10-13 on the first revision of this callback: `cine-cellar`
         * injects its theme sheet from the LAST list value, so the document
         * got a `link` for skin-layout.css 2 ms after the ask (answered EMPTY
         * at 53.284, before its own allow at 53.318) and cinematic.css was
         * NEVER injected at all (`cinRules=-2`). An IIFE pins the value. */
        (function (href) {
          ask(href, function () {
            if (hasThemeSheet(href)) return;
            inject('link', { rel: 'stylesheet', href: href,
                             'data-sotto-lazy': 'theme' });
            log('inject', href);
          });
        })(url);
        changed = true;
      }
    }
    if (changed) log('load', theme + ' -> ' + list.join(', '));
    return changed;
  }

  /* The whole decision, re-run on every data-theme mutation. */
  function settle() {
    var theme = currentTheme();
    var list = needsFor(theme);
    if (!list.length) { log('settle', theme + ' base (nothing deferred)'); return; }
    var changed = loadFor(theme);
    log('settle', theme + (changed ? ' armed' : ' already armed'));
  }

  function boot() {
    settle();
    /* The same latch skin-host.js uses: one attribute write from the switcher
     * is the whole interface, so observing it covers every path into a new theme
     * - button, dropdown, keyboard, preview-commit and a theme restored from the
     * store on the next launch. */
    if (window.MutationObserver && document.documentElement) {
      try {
        new MutationObserver(function () { settle(); })
          .observe(document.documentElement,
                   { attributes: true, attributeFilter: ['data-theme'] });
      } catch (err) { /* no observer means no late switch */ }
    }
    window.SottoLazy = {
      assets: function () { return ['themes/cinematic.css',
        'themes/panel-designs.css', 'skins/skins.js', 'skin-host.js',
        'skin-layout.css']; },
      needs: needsFor,
      reload: function (theme) { return loadFor(theme || currentTheme()); },
      log: function () { return LOG.slice(); }
    };
    log('boot', 'observer=' + !!(window.MutationObserver));
  }

  /* The preload can run before <html> exists. Settling then is a no-op, so wait
   * for the document rather than guessing a readystate. */
  if (document.documentElement) { boot(); }
  else if (document.addEventListener) {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else { boot(); }
})();

