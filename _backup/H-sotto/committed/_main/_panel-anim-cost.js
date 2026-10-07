/* Sotto ÔÇö THE ANIMATION-COST PROBE.
 *
 * WHAT IT IS FOR. The owner's condition, verbatim from this lane's brief: the
 * live box is REWRITTEN ON EVERY PARTIAL, so any animation added to it has to be
 * `opacity`/`transform`/`filter` ÔÇö never a property that forces a relayout ÔÇö and
 * the cost has to be MEASURED with the animation on and off. *"O dono acabou de
 * levar com stutter causado por n├│s: um painel que engasga ├® uma entrega
 * falhada."*
 *
 * So this file runs the REAL panel (`panel.js`, `panel.css`, the real theme
 * files) against the audit stub bridge, drives a realistic caption stream into
 * it on REAL wall-clock timers, and reports four independent things:
 *
 *   * FRAME TIMING ÔÇö every `requestAnimationFrame` delta over the window, so the
 *     report carries p50/p95/max and not just a mean;
 *   * LONG ANIMATION FRAMES (`PerformanceObserver`, `long-animation-frame`) ÔÇö
 *     `duration`, `blockingDuration`, and `styleAndLayout` derived as
 *     `startTime + duration - styleAndLayoutStart`, which is the frame's own
 *     style+layout share. THIS IS THE "count of layouts" the brief asks for, in
 *     the only form a page can read: the compositor/layout time each long frame
 *     spent, summed. A frame that only composites adds nothing to it;
 *   * THE PANEL'S OWN MAIN-THREAD COST ÔÇö `performance.now()` around every
 *     `pushCaption`, summed and maxed, which is the synchronous work the partial
 *     path costs whatever the compositor does;
 *   * THE DOM SHAPE ÔÇö how many rows and how many word spans are on screen, so
 *     the numbers can be attributed to a real caption load.
 *
 * THE ARMS (chosen by `location.hash`, and each one a different browser launch):
 *   #mode=cost&theme=theme-5&arm=on        the theme's animations running
 *   #mode=cost&theme=theme-5&arm=reduced   the box's own setting (animations off)
 *   #mode=cost&theme=theme-5&arm=relayout  THE CONTROL: the same animations,
 *                                          re-declared on `width` so every frame
 *                                          forces a relayout. An instrument that
 *                                          cannot see that difference cannot
 *                                          certify the compositor-only ones.
 *
 * HOW IT GETS OUT. Not through `--dump-dom`: this arm runs on REAL time (virtual
 * time would make every frame delta a fiction), so there is no moment at which a
 * dump would be taken. The result is therefore BEACONED to a local HTTP server
 * the arm script starts on 127.0.0.1 ÔÇö an `Image()` GET with the summary in the
 * query string, which needs no CORS and works from a `file://` document. The arm
 * copy's CSP is widened for exactly that (`img-src ... http://127.0.0.1:*`), and
 * that widening is stated in the receipt because it is a difference between the
 * copy and the shipped panel.
 */

(function () {
  'use strict';

  var params = {};
  String(location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
    var i = kv.indexOf('=');
    if (i > 0) params[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
  });

  var THEME = params.theme || 'theme-5';
  var ARM = params.arm || 'on';
  var PORT = params.port || '';
  var SECONDS = Number(params.seconds || 6);
  var RATE_HZ = Number(params.rate || 8);

  var LOAF = { count: 0, duration: 0, blocking: 0, styleAndLayout: 0, render: 0, max: 0 };
  var LONGTASK = { count: 0, duration: 0 };
  var frames = [];
  var lastFrame = null;
  var pushMs = { count: 0, total: 0, max: 0 };
  var running = true;
  /** Held here so the beacon request outlives `report()`. See the note there. */
  var beacon = null;

  /* ÔöÇÔöÇ the two observers, before anything is driven ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ */
  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        LOAF.count += 1;
        LOAF.duration += e.duration;
        LOAF.blocking += (e.blockingDuration || 0);
        if (e.styleAndLayoutStart) {
          LOAF.styleAndLayout += Math.max(0, e.startTime + e.duration - e.styleAndLayoutStart);
        }
        if (e.renderStart) {
          LOAF.render += Math.max(0, e.startTime + e.duration - e.renderStart);
        }
        if (e.duration > LOAF.max) LOAF.max = e.duration;
      });
    }).observe({ type: 'long-animation-frame', buffered: true });
  } catch (e) { /* the report says `loafSupported:false` instead */ }

  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        LONGTASK.count += 1;
        LONGTASK.duration += e.duration;
      });
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) { /* ditto */ }

  function raf(t) {
    if (lastFrame !== null) frames.push(t - lastFrame);
    lastFrame = t;
    if (running) requestAnimationFrame(raf);
  }

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  /* ÔöÇÔöÇ THE RELAYOUT CONTROL ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
   * The SAME two elements the theme animates, with the SAME cadence, but on a
   * property that changes their box. If the instrument cannot tell this apart
   * from the compositor-only version, its green on the real arms means nothing. */
  function installRelayoutControl() {
    var css = document.createElement('style');
    css.textContent = '@keyframes cost-relayout{'
      + 'from{width:2px}to{width:16px}}'
      + '.caption--provisional .caption__led,.chrome__meter i{'
      + 'animation:cost-relayout .4s linear infinite !important}';
    document.head.appendChild(css);
  }

  /* ÔöÇÔöÇ THE STREAM ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
   * Real wall-clock timers, one growing line per ~1.5 s, so the engine's own
   * hold deadline commits and retires rows the way it does in the app. The
   * WORDS grow one at a time, which is what makes the word spans churn. */
  var WORDS = ('o som chega antes da imagem e a legenda nasce enquanto a frase ainda '
    + 'esta em formacao cada palavra provisoria carrega uma pequena duvida quando a '
    + 'frase fecha ela ganha peso e fica ninguem le uma legenda as pessoas apenas '
    + 'acompanham o painel escuta tudo mas nao interrompe nada').split(' ');

  var base = 0;
  var word = 0;
  var startedAt = 0;

  function tick() {
    if (!running) return;
    if (word >= WORDS.length) { word = 0; base += 4; }
    word += 1;
    var text = WORDS.slice(0, word).join(' ');
    var t0 = performance.now();
    window.sotto.pushCaption(text, { start: base, end: base + word * 0.3, final: false });
    var dt = performance.now() - t0;
    pushMs.count += 1;
    pushMs.total += dt;
    if (dt > pushMs.max) pushMs.max = dt;
    setTimeout(tick, Math.round(1000 / RATE_HZ));
  }

  function summarise(list) {
    if (!list.length) return null;
    var s = list.slice().sort(function (a, b) { return a - b; });
    var at = function (p) { return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
    var sum = s.reduce(function (a, b) { return a + b; }, 0);
    return {
      n: s.length,
      mean: +(sum / s.length).toFixed(2),
      p50: +at(0.5).toFixed(2),
      p95: +at(0.95).toFixed(2),
      max: +s[s.length - 1].toFixed(2),
      over33: s.filter(function (v) { return v > 33.4; }).length,
      over50: s.filter(function (v) { return v > 50; }).length
    };
  }

  function report() {
    running = false;
    var list = document.getElementById('caption-list');
    var payload = {
      theme: THEME,
      arm: ARM,
      seconds: SECONDS,
      rateHz: RATE_HZ,
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      loafSupported: LOAF.count > 0,
      loaf: {
        count: LOAF.count,
        duration: +LOAF.duration.toFixed(2),
        blocking: +LOAF.blocking.toFixed(2),
        styleAndLayout: +LOAF.styleAndLayout.toFixed(2),
        render: +LOAF.render.toFixed(2),
        max: +LOAF.max.toFixed(2)
      },
      longtask: { count: LONGTASK.count, duration: +LONGTASK.duration.toFixed(2) },
      frame: summarise(frames),
      push: {
        count: pushMs.count,
        total: +pushMs.total.toFixed(2),
        mean: +(pushMs.total / Math.max(1, pushMs.count)).toFixed(3),
        max: +pushMs.max.toFixed(3)
      },
      dom: {
        rows: list ? list.querySelectorAll('.caption').length : null,
        words: list ? list.querySelectorAll('.caption__word').length : null,
        led: list ? list.querySelectorAll('.caption__led').length : null
      },
      animations: (function () {
        var led = document.querySelector('.caption--provisional .caption__led');
        var bar = document.querySelector('.chrome__meter i');
        var wordSpan = document.querySelector('.caption__word');
        return {
          led: led ? getComputedStyle(led).animationName : null,
          meter: bar ? getComputedStyle(bar).animationName : null,
          wordTransition: wordSpan ? getComputedStyle(wordSpan).transitionProperty : null
        };
      }())
    };
    var url = 'http://127.0.0.1:' + PORT + '/report?payload='
      + encodeURIComponent(JSON.stringify(payload));
    /* THE IMAGE IS HELD IN A MODULE-SCOPE VARIABLE ON PURPOSE. The first version
     * built it as a local inside this function and it was collected before the
     * request was ever issued ÔÇö the payload was correct in `document.title` and
     * the server never saw a byte. Measured, twice. */
    beacon = new Image();
    beacon.src = url;
    /* A second copy through `document.title`, so a run whose beacon was refused
     * is still visible in the arm's own log rather than silently lost. */
    document.title = 'cost ' + JSON.stringify(payload);
  }

  function main() {
    setTheme(THEME);
    if (ARM === 'relayout') installRelayoutControl();
    /* Let the first paint and the font loads settle before the window opens, so
     * the frame numbers are about the caption path and not about start-up. */
    setTimeout(function () {
      startedAt = performance.now();
      requestAnimationFrame(raf);
      tick();
      setTimeout(report, SECONDS * 1000);
    }, 600);
  }

  if (document.readyState === 'complete') setTimeout(main, 0);
  else window.addEventListener('load', function () { setTimeout(main, 0); });
}());
