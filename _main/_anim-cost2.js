/* Sotto — THE ANIMATION ATTRIBUTION PROBE (lane/goal-anim).
 *
 * WHY THIS EXISTS. `_main/_panel-anim-cost.js` answers "is the animated panel
 * more expensive than the still one" with one mean per arm. It cannot answer
 * "WHICH animation, on WHICH element, costs WHAT", and on this box its mean is
 * dominated by a single multi-second block, so a mean cannot separate the cost
 * of an effect from the cost of the first layout of a document carrying 430 KB
 * of CSS on a machine where `chrome --dump-dom data:text/html,<h1>` takes 100 s.
 *
 * WHAT THIS FILE ADDS, in the same served arm, on the same real panel bytes:
 *
 *   * PER-PUSH SAMPLES, not a mean: every `pushCaption` duration with its offset
 *     in the window, summarised to p50/p95/max. The window is opened AFTER a
 *     warm-up stream, and the warm-up is REPORTED rather than merged, so the
 *     start-up cost is visible as its own number instead of being averaged into
 *     the steady-state one (or silently discarded).
 *   * LONG-ANIMATION-FRAME `scripts[]`: each long frame's own attribution —
 *     invoker, source URL, function name, duration and
 *     `forcedStyleAndLayoutDuration`. That is the only place the browser names
 *     the code that paid for the frame, and it is what turns "the panel is slow"
 *     into "this line, this many ms".
 *   * A `getAnimations()` CENSUS: every active animation with its name, target,
 *     play state, iteration count and the CSS PROPERTIES it animates, plus how
 *     many provisional word spans are `inline-block` and how many carry an
 *     animation. One number per candidate, per element.
 *   * AN ABLATION SWITCH (`abl=`): one CSS rule set removed at run time through
 *     the CSSOM (a `deleteRule`/`style.removeProperty`, never a `<style>`
 *     element and never a `style=` attribute), so the SAME bytes can be measured
 *     with exactly one effect off. `none` is the control: an ablation whose
 *     number does not move against `none` is not a cost, whatever it looks like.
 *
 * The stream, the theme, the served page and the beacon transport are the ones
 * the shipped probe already uses. This file changes WHAT IS REPORTED, not what
 * is measured.
 *
 *   #mode=attrib&theme=theme-5&arm=on&abl=no-word-anim&port=NNNN
 */

(function () {
  'use strict';

  var params = {};
  String(location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
    var i = kv.indexOf('=');
    if (i > 0) params[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
  });

  var THEME = params.theme || 'theme-5';
  var ABLATION = params.abl || 'none';
  var PORT = params.port || '';
  var SECONDS = Number(params.seconds || 6);
  var RATE_HZ = Number(params.rate || 8);
  var WARMUP_MS = Number(params.warmup || 2500);

  /* ── the channels ───────────────────────────────────────────────────────── */
  var LOAF = { count: 0, duration: 0, blocking: 0, styleAndLayout: 0, max: 0,
    entries: [], supported: false };
  var frames = [];
  var lastFrame = null;
  /* Every push, tagged with the phase it landed in: `warm` before the window
   * opens, `window` inside it. Kept as the raw samples so the report can carry
   * BOTH the distribution (p50) and the outliers that a mean hides. */
  var pushes = [];
  var running = true;
  var measuring = false;
  var startedAt = 0;
  var bootAt = 0;
  var phase = 'boot';
  var census = null;
  var beacon = null;

  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        if (!measuring || e.startTime < startedAt) return;
        LOAF.count += 1;
        LOAF.duration += e.duration;
        LOAF.blocking += (e.blockingDuration || 0);
        if (e.styleAndLayoutStart) {
          LOAF.styleAndLayout += Math.max(0, e.startTime + e.duration - e.styleAndLayoutStart);
        }
        if (e.duration > LOAF.max) LOAF.max = e.duration;
        if (LOAF.entries.length < 40) {
          LOAF.entries.push({
            t: +(e.startTime - startedAt).toFixed(1),
            dur: +e.duration.toFixed(1),
            block: +(e.blockingDuration || 0).toFixed(1),
            render: e.renderStart ? +(e.startTime + e.duration - e.renderStart).toFixed(1) : null,
            /* THE ATTRIBUTION: which script, which module, and how much of the
             * frame it spent forcing style+layout. */
            scripts: (e.scripts || []).slice(0, 8).map(function (s) {
              return {
                f: s.sourceFunctionName || '',
                url: String(s.sourceURL || '').split('/').pop(),
                inv: s.invoker || '',
                dur: +s.duration.toFixed(1),
                fsl: +(s.forcedStyleAndLayoutDuration || 0).toFixed(1)
              };
            })
          });
        }
      });
    }).observe({ type: 'long-animation-frame', buffered: true });
    LOAF.supported = true;
  } catch (err) { /* the report says `loaf.supported:false` */ }

  function raf(t) {
    if (lastFrame !== null) frames.push({ t: t, d: t - lastFrame, phase: phase });
    lastFrame = t;
    if (running) requestAnimationFrame(raf);
  }

  /* ── THE ABLATIONS ────────────────────────────────────────────────────────
   * Each entry names ONE candidate. `decls` drops a declaration from every
   * matching rule (including rules nested in `@media`), `exact` drops the whole
   * declaration block of a rule whose selector is EXACTLY this text, `insert`
   * appends a rule to the last stylesheet (highest cascade priority).
   *
   * A `deleteRule`/`style.removeProperty` is a CSSOM write: `panel.html`'s
   * `style-src` governs `<style>` elements and `style=` ATTRIBUTES, not the
   * CSSOM, so every one of these lands on the real sheet and the measurement
   * stays inside one document. The applied count is reported (`abl.applied`) so
   * an ablation that matched NOTHING cannot be read as "this effect is free". */
  var ABLATIONS = {
    none: {},
    /* The per-word reveal itself, with the `inline-block` that comes with it —
     * the two halves measured apart below. */
    'no-word-anim': { decls: [{ sel: /\.caption__word/, prop: 'animation' }] },
    'no-word-inline': { decls: [{ sel: /\.caption__word/, prop: 'display' }] },
    'no-led-anim': { decls: [{ sel: /\.caption__led/, prop: 'animation' }] },
    'no-typing-anim': { decls: [{ sel: /\[data-typing\]/, prop: 'animation' }] },
    'no-caption-anim': { exact: '.caption' },
    'no-motion-everywhere': { decls: [
      { sel: /\.caption__word/, prop: 'animation' },
      { sel: /\.caption__led/, prop: 'animation' },
      { sel: /\.caption__mark/, prop: 'animation' },
      { sel: /\.chrome/, prop: 'animation' },
      { sel: /\.caption/, prop: 'animation' },
      { sel: /\.caption/, prop: 'transition' }
    ] },
    /* THE CANDIDATE FIX, MEASURED BEFORE IT IS WRITTEN. Every theme animates
     * EVERY provisional word span (`sotto-N-rise` / `-snap` / `-fog` with
     * `fill: both`), but a span's animation only ever STARTS when the span is
     * created — and `panel.js` creates it on the partial that makes it the
     * NEWEST word (`data-typing`). So the reveal is already a one-word event; the
     * other 38 spans are finished, filled animations that every later restyle
     * still has to re-apply. This rewrites the selector to say exactly what the
     * pixels already show: `[data-typing]`. */
    'newest-only': { resel: /(\.caption__word)(?!\[)/g, keepDisplay: true },
    /* The forced layout, isolated: `followNewestLine()` reads `scrollHeight`
     * inside every push, which forces a synchronous style+layout of the document
     * on the partial path. Returning a stale 0 makes the read a no-op — an UPPER
     * BOUND on what that read costs, not a fix (the box would stop following). */
    'no-scroll-read': { js: 'scrollHeight' },
    /* `fill: both` on a 100 ms reveal leaves a FINISHED animation applying its
     * end state on every word span for the rest of the line's life, and every
     * later restyle still walks it. In the four themes that animate the tail the
     * end state EQUALS the base state (nothing else sets `opacity`/`transform`/
     * `filter` on a word span), so dropping the fill should be invisible — this
     * measures whether it is also free. theme-3 has no word animation (it ramps
     * with `--w-op`), so it has nothing for this to touch. */
    'no-word-fill': { fill: /caption__word/ },
    /* The three things that animate FOREVER (the two LEDs and the caret) and the
     * one that animates briefly: asked for their own compositor layer, so the
     * main thread stops repainting them every frame. */
    promote: { insert: [
      '#caption-list .caption__word[data-typing], #caption-list .caption__mark,'
        + ' #caption-list .caption__led { will-change: opacity, transform; }'
    ] },
    /* The candidate FIX, measured before it is written: rows get their own
     * containment so a mutation inside one row cannot invalidate the box. */
    'contain-rows': { insert: [
      '#caption-list > .caption { contain: layout style paint; }',
      '#caption-list > .caption--provisional { contain: layout style paint; }'
    ] },
    /* The other half of the same idea: `will-change` on the two things that
     * animate, so the compositor owns them from the first frame. */
    'promote': { insert: [
      '.caption__word[data-typing], .caption--provisional .caption__provisional .caption__word'
        + ' { will-change: opacity, transform; }',
      '.caption--provisional .caption__led { will-change: opacity, transform; }'
    ] }
  };

  function eachRule(sheet, fn) {
    var rules;
    try { rules = sheet.cssRules; } catch (err) { return; }  // cross-origin: skip
    if (!rules) return;
    (function walk(list) {
      for (var i = 0; i < list.length; i += 1) {
        var r = list[i];
        fn(r);
        if (r.cssRules && r.cssRules.length) walk(r.cssRules);
      }
    }(rules));
  }

  function applyAblation(name) {
    var spec = ABLATIONS[name] || {};
    var out = { name: name, known: !!ABLATIONS[name], decls: 0, dropped: 0, inserted: 0 };
    var toDrop = [];
    if (spec.decls) {
      for (var s = 0; s < document.styleSheets.length; s += 1) {
        eachRule(document.styleSheets[s], function (rule) {
          if (!rule.selectorText || !rule.style) return;
          spec.decls.forEach(function (d) {
            if (!d.sel.test(rule.selectorText)) return;
            if (d.prop === 'transition' && !rule.style.transition && !rule.style.transitionProperty) return;
            if (rule.style.getPropertyValue(d.prop) === '' && !rule.style.getPropertyPriority(d.prop)) {
              /* `animation` may be spread over longhands in this sheet. */
              if (rule.style.animationName === '' && rule.style.transitionProperty === '' && d.prop !== 'display') return;
            }
            rule.style.removeProperty(d.prop);
            rule.style.removeProperty('-' + d.prop + '-name');
            rule.style.removeProperty('-' + d.prop + '-duration');
            rule.style.removeProperty('-' + d.prop + '-delay');
            rule.style.removeProperty('-' + d.prop + '-fill-mode');
            rule.style.removeProperty('-' + d.prop + '-iteration-count');
            out.decls += 1;
          });
        });
      }
    }
    if (spec.exact) {
      for (var q = 0; q < document.styleSheets.length; q += 1) {
        var sheet = document.styleSheets[q];
        var n = 0;
        try { n = sheet.cssRules ? sheet.cssRules.length : 0; } catch (err) { n = 0; }
        for (var i = n - 1; i >= 0; i -= 1) {
          var r = sheet.cssRules[i];
          if (r.selectorText && r.selectorText.trim() === spec.exact) {
            sheet.deleteRule(i);
            out.dropped += 1;
          }
        }
      }
    }
    if (spec.fill) {
      for (var f = 0; f < document.styleSheets.length; f += 1) {
        eachRule(document.styleSheets[f], function (rule) {
          if (!rule.selectorText || !rule.style) return;
          if (!spec.fill.test(rule.selectorText)) return;
          if (rule.style.animationName === '' && rule.style.getPropertyValue('animation') === '') return;
          rule.style.animationFillMode = 'none';
          out.decls += 1;
        });
      }
    }
    if (spec.resel) {
      /* `selectorText` is writable on a CSSStyleRule: the selector is rewritten in
       * place, no rule deleted, no sheet replaced. */
      for (var r2 = 0; r2 < document.styleSheets.length; r2 += 1) {
        eachRule(document.styleSheets[r2], function (rule) {
          if (!rule.selectorText || !rule.style) return;
          if (rule.selectorText.indexOf('.caption__word') < 0) return;
          /* THE BOX MODEL IS NOT PART OF THE CANDIDATE. The theme's word rule also
           * carries `display: inline-block`; rewriting THAT to `[data-typing]`
           * would take the tail's inline-block boxes away and confound the arm with
           * a reflow of the line -- the shipped fix leaves `display` alone. */
          if (spec.keepDisplay && rule.style && rule.style.display) return;
          var next = rule.selectorText.replace(spec.resel, '.caption__word[data-typing]');
          if (next === rule.selectorText) return;
          try { rule.selectorText = next; out.decls += 1; } catch (err) { /* read-only sheet */ }
        });
      }
    }
    if (spec.js === 'scrollHeight') {
      try {
        Object.defineProperty(Element.prototype, 'scrollHeight', {
          configurable: true,
          get: function () { return 0; }
        });
        out.inserted += 1;
      } catch (err) { /* reported by the count */ }
    }
    if (spec.insert) {
      var last = null;
      for (var k = document.styleSheets.length - 1; k >= 0; k -= 1) {
        try { if (document.styleSheets[k].cssRules) { last = document.styleSheets[k]; break; } } catch (err) { /* skip */ }
      }
      if (last) {
        spec.insert.forEach(function (text) {
          try { last.insertRule(text, last.cssRules.length); out.inserted += 1; } catch (err) { /* reported by the count */ }
        });
      }
    }
    return out;
  }

  /* ── THE CENSUS ───────────────────────────────────────────────────────────
   * One snapshot of what is actually animating, taken inside the window. Grouped
   * by animation name + the target's own descriptor, so "40 instances of
   * `sotto-5-snap` on `.caption__word`, 38 of them finished and still applying
   * a fill" is a readable fact rather than an inference. */
  function describe(el) {
    if (!el || el.nodeType !== 1) return String(el);
    var s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.className && typeof el.className === 'string') {
      s += '.' + el.className.trim().split(/\s+/).join('.');
    }
    return s;
  }

  function censusNow() {
    var anims = [];
    var byKey = {};
    var list;
    try { list = document.getAnimations(); } catch (err) { list = []; }
    list.forEach(function (a) {
      var target = a.effect && a.effect.target;
      var timing = a.effect && a.effect.getTiming ? a.effect.getTiming() : {};
      var props = {};
      try {
        (a.effect.getKeyframes ? a.effect.getKeyframes() : []).forEach(function (k) {
          Object.keys(k).forEach(function (p) {
            if (p !== 'offset' && p !== 'computedOffset' && p !== 'easing' && p !== 'composite') props[p] = 1;
          });
        });
      } catch (err) { /* a transition effect may refuse; the count still lands */ }
      var name = a.animationName || a.transitionProperty || a.constructor.name;
      var desc = describe(target);
      var key = name + ' @ ' + desc;
      if (!byKey[key]) byKey[key] = { name: name, target: desc, n: 0, states: {}, props: Object.keys(props), dur: timing.duration };
      byKey[key].n += 1;
      byKey[key].states[a.playState] = (byKey[key].states[a.playState] || 0) + 1;
      if (anims.length < 60) {
        anims.push({ name: name, target: desc, state: a.playState,
          t: Math.round(a.currentTime || 0), dur: timing.duration,
          iter: timing.iterations, props: Object.keys(props) });
      }
    });

    var words = document.querySelectorAll('.caption--provisional .caption__word');
    var inlineBlocks = 0;
    var animWords = 0;
    var promoted = 0;
    for (var i = 0; i < words.length; i += 1) {
      var cs = getComputedStyle(words[i]);
      if (cs.display === 'inline-block') inlineBlocks += 1;
      if (cs.animationName && cs.animationName !== 'none') animWords += 1;
      if (cs.willChange && cs.willChange !== 'auto') promoted += 1;
    }
    var rows = document.querySelectorAll('#caption-list > .caption');
    var rowAnims = 0;
    for (var j = 0; j < rows.length; j += 1) {
      if (getComputedStyle(rows[j]).animationName !== 'none') rowAnims += 1;
    }

    return {
      at: +(performance.now() - startedAt).toFixed(1),
      total: list.length,
      groups: Object.keys(byKey).map(function (k) { return byKey[k]; })
        .sort(function (a, b) { return b.n - a.n; }).slice(0, 20),
      instances: anims,
      dom: {
        rows: rows.length,
        wordSpans: words.length,
        wordsInlineBlock: inlineBlocks,
        wordsAnimated: animWords,
        wordsPromoted: promoted,
        rowsAnimated: rowAnims
      }
    };
  }

  function summarise(list) {
    if (!list.length) return null;
    var s = list.slice().sort(function (a, b) { return a - b; });
    var at = function (p) { return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
    var sum = 0;
    for (var i = 0; i < s.length; i += 1) sum += s[i];
    return { n: s.length, mean: +(sum / s.length).toFixed(2), p50: +at(0.5).toFixed(2),
      p95: +at(0.95).toFixed(2), max: +s[s.length - 1].toFixed(2),
      over8: s.filter(function (v) { return v > 8; }).length,
      over50: s.filter(function (v) { return v > 50; }).length };
  }

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  /* ── THE STREAM ───────────────────────────────────────────────────────────
   * The same shape the shipped probe drives: one growing line, one word at a
   * time, every 125 ms. `window.sotto.pushCaption` is WRAPPED so the duration of
   * each call is a sample of its own — the panel's path is synchronous all the
   * way to the forced layout inside it, so this number is the whole synchronous
   * cost of a partial, which is what the target ("push under 8 ms p50") names. */
  var WORDS = ('o som chega antes da imagem e a legenda nasce enquanto a frase ainda '
    + 'esta em formacao cada palavra provisoria carrega uma pequena duvida quando a '
    + 'frase fecha ela ganha peso e fica ninguem le uma legenda as pessoas apenas '
    + 'acompanham o painel escuta tudo mas nao interrompe nada').split(' ');

  var base = 0;
  var word = 0;

  function tick() {
    if (!running) return;
    if (word >= WORDS.length) { word = 0; base += 4; }
    word += 1;
    var text = WORDS.slice(0, word).join(' ');
    var t0 = performance.now();
    window.sotto.pushCaption(text, { start: base, end: base + word * 0.3, final: false });
    /* THE SAMPLE IS THE DURATION OF THE CALL, and its OFFSET is kept beside it:
     * a p50 says what the path costs, the offsets say WHEN the outliers landed
     * (which is how a start-up block is told apart from a per-partial one). */
    var ms = performance.now() - t0;
    if (measuring) {
      pushes.push([+(performance.now() - startedAt).toFixed(1), +ms.toFixed(2)]);
    } else {
      warm.push([+(t0 - bootAt).toFixed(1), +ms.toFixed(2)]);
    }
    setTimeout(tick, Math.round(1000 / RATE_HZ));
  }

  var warm = [];

  function durs(pairs) {
    return pairs.map(function (p) { return p[1]; });
  }

  /* A BEACON THAT CANNOT BE LOST. The first version wrapped nothing: a throw in
   * `censusNow()` (a transition effect that refuses `getKeyframes`, a font-set
   * walk) took the whole report with it and the arm printed NO BEACON — which
   * reads as "the panel is fine" or as "the harness is broken", never as the
   * truth. The census is now OPTIONAL and the payload is always sent. */
  var pageErrors = [];
  var sent = false;
  try {
    window.addEventListener('error', function (e) {
      pageErrors.push(String((e && e.message) || e));
    });
  } catch (err) { /* no window listener: the beacon below still carries the rest */ }

  function beaconOut(payload) {
    sent = true;
    if (pageErrors.length) payload.pageErrors = pageErrors.slice(0, 6);
    if (!PORT) return;
    /* HELD IN A MODULE-SCOPE VARIABLE ON PURPOSE: a local `Image` is collected
     * before the request is issued and the server never sees a byte (measured in
     * the shipped probe, 2026-10-31). `document.title` carries a second copy, so
     * an arm whose beacon was refused still leaves its payload in the log. */
    beacon = new Image();
    beacon.src = 'http://127.0.0.1:' + PORT + '/report?payload='
      + encodeURIComponent(JSON.stringify(payload));
    document.title = 'attrib ' + JSON.stringify(payload);
  }

  function report() {
    running = false;
    measuring = false;
    try { census = census || censusNow(); } catch (err) { census = { error: String(err) }; }
    var list = document.getElementById('caption-list');
    var framed = frames.filter(function (f) { return f.phase === 'window'; }).map(function (f) { return f.d; });
    var payload = {
      probe: 'anim-cost2',
      theme: THEME,
      ablation: applied,
      seconds: SECONDS,
      rateHz: RATE_HZ,
      warmupMs: WARMUP_MS,
      windowMs: +(performance.now() - startedAt).toFixed(1),
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      push: { window: summarise(durs(pushes)), warmup: summarise(durs(warm)),
        samples: pushes.slice(0, 96) },
      frame: summarise(framed),
      loaf: { supported: LOAF.supported, count: LOAF.count,
        duration: +LOAF.duration.toFixed(1), blocking: +LOAF.blocking.toFixed(1),
        styleAndLayout: +LOAF.styleAndLayout.toFixed(1), max: +LOAF.max.toFixed(1),
        entries: LOAF.entries },
      animations: census,
      /* ── THE FONT-SWAP CHANNEL ────────────────────────────────────────────
       * `fonts.css` declares 71 faces with `font-display: swap` over 13 bundled
       * `.woff2` files, and a swap RE-LAYS-OUT every line that uses the face. If
       * a forced layout inside a push lands on that moment it pays for the whole
       * document at once, which looks exactly like "the animation is slow". The
       * offsets of the font fetches and of `loadingdone` are reported so the
       * outlier can be MATCHED to a swap instead of blamed on an effect. */
      fonts: {
        faces: (function () {
          var n = { loaded: 0, loading: 0, error: 0, unloaded: 0 };
          document.fonts.forEach(function (f) { n[f.status] = (n[f.status] || 0) + 1; });
          return n;
        }()),
        done: fontEvents,
        fetches: (function () {
          var out = [];
          try {
            performance.getEntriesByType('resource').forEach(function (r) {
              if (!/\.woff2/.test(r.name)) return;
              if (r.startTime < startedAt - 4000) return;
              out.push({ f: r.name.split('/').pop(), start: +(r.startTime - startedAt).toFixed(0),
                end: +(r.responseEnd - startedAt).toFixed(0) });
            });
          } catch (err) { /* the channel is optional, the count above still lands */ }
          return out.slice(-16);
        }())
      },
      dom: {
        rows: list ? list.querySelectorAll('.caption').length : null,
        words: list ? list.querySelectorAll('.caption__word').length : null
      }
    };
    beaconOut(payload);
  }

  var fontEvents = [];
  try {
    document.fonts.addEventListener('loadingdone', function () {
      fontEvents.push(+performance.now().toFixed(0));
    });
  } catch (err) { /* no FontFaceSet: the fetch list still lands */ }

  var applied = { name: ABLATION, known: false, decls: 0, dropped: 0, inserted: 0 };

  function main() {
    bootAt = performance.now();
    setTheme(THEME);
    applied = applyAblation(ABLATION);
    /* The window opens after the warm-up stream has paid for the document's
     * first layout, its font loads and its first style recalc — all of which are
     * ONE-OFF costs that a per-push mean would otherwise smear across every
     * sample. They are not discarded: `push.warmup` carries them. */
    setTimeout(function () {
      requestAnimationFrame(raf);
      tick();
      /* A WATCHDOG BEACON. A lost report is indistinguishable from a panel with
       * nothing wrong, so if the normal path has not reported by the time its own
       * timers are spent (+8 s), the arm says so and carries the page's errors. */
      setTimeout(function () {
        if (sent) return;
        try { report(); } catch (err) {
          beaconOut({ probe: 'anim-cost2', watchdog: true, ablation: applied,
            error: String(err && err.stack ? err.stack : err) });
        }
      }, WARMUP_MS + SECONDS * 1000 + 8000);
      setTimeout(function () {
        startedAt = performance.now();
        measuring = true;
        phase = 'window';
        setTimeout(function () { census = censusNow(); }, 1200);
        setTimeout(report, SECONDS * 1000);
      }, WARMUP_MS);
    }, 400);
  }

  if (document.readyState === 'complete') setTimeout(main, 0);
  else window.addEventListener('load', function () { setTimeout(main, 0); });
}());
