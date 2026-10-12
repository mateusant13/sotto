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

  /* Ask the shell for the real bytes of one deferred URL. Fire-and-forget by
   * design: the caller adds the element anyway, and the element is what waits. */
  function ask(url) {
    if (ASKED[url]) return;
    ASKED[url] = true;
    log('ask', url);
    try {
      var s = window.sotto;
      if (s && typeof s.dispatch === 'function') {
        s.dispatch('lazy-asset', { url: String(url) });
        return;
      }
      if (window.pywebview && window.pywebview.api &&
          window.pywebview.api.dispatch) {
        window.pywebview.api.dispatch('lazy-asset', { url: String(url) });
      }
    } catch (err) {
      log('ask-failed', url + ' ' + (err && err.message ? err.message : err));
    }
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
    var step = inject('script', { src: 'skins/skins.js',
                                   'data-sotto-lazy': 'skin' });
    log('inject', 'skins/skins.js' + (step ? '' : ' FAILED'));
    if (!step) return;
    /* 812 KB of array literals executes synchronously on load, so by the time the
     * next line runs window.SOTTO_SKINS exists. */
    step.addEventListener('load', function () {
      var host = inject('script', { src: 'skin-host.js',
                                     'data-sotto-lazy': 'skin' });
      log('inject', 'skin-host.js' + (host ? '' : ' FAILED'));
      if (!host) return;
      host.addEventListener('load', function () {
        inject('link', { rel: 'stylesheet', href: 'skin-layout.css',
                         'data-sotto-lazy': 'skin' });
        log('inject', 'skin-layout.css');
      }, false);
    }, false);
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
        ask(url);
        inject('link', { rel: 'stylesheet', href: url,
                         'data-sotto-lazy': 'theme' });
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

