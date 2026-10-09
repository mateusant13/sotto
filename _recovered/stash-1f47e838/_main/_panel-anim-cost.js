/* Sotto — THE ANIMATION-COST PROBE.
 *
 * WHAT IT IS FOR. The owner's condition, verbatim from this lane's brief: the
 * live box is REWRITTEN ON EVERY PARTIAL, so any animation added to it has to be
 * `opacity`/`transform`/`filter` — never a property that forces a relayout — and
 * the cost has to be MEASURED with the animation on and off. *"O dono acabou de
 * levar com stutter causado por nós: um painel que engasga é uma entrega
 * falhada."*
 *
 * So this file runs the REAL panel (`panel.js`, `panel.css`, the real theme
 * files) against the audit stub bridge, drives a realistic caption stream into
 * it on REAL wall-clock timers, and reports four independent things:
 *
 *   * FRAME TIMING — every `requestAnimationFrame` delta over the window, so the
 *     report carries p50/p95/max and not just a mean;
 *   * LONG ANIMATION FRAMES (`PerformanceObserver`, `long-animation-frame`) —
 *     `duration`, `blockingDuration`, and `styleAndLayout` derived as
 *     `startTime + duration - styleAndLayoutStart`, which is the frame's own
 *     style+layout share. THIS IS THE "count of layouts" the brief asks for, in
 *     the only form a page can read: the compositor/layout time each long frame
 *     spent, summed. A frame that only composites adds nothing to it;
 *   * THE PANEL'S OWN MAIN-THREAD COST — `performance.now()` around every
 *     `pushCaption`, summed and maxed, which is the synchronous work the partial
 *     path costs whatever the compositor does;
 *   * THE DOM SHAPE — how many rows and how many word spans are on screen, so
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
 * the arm script starts on 127.0.0.1 — an `Image()` GET with the summary in the
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

  var LOAF = { count: 0, duration: 0, blocking: 0, styleAndLayout: 0, render: 0, max: 0,
    seen: 0, dropped: 0 };
  var LONGTASK = { count: 0, duration: 0, seen: 0, dropped: 0 };
  var frames = [];
  var lastFrame = null;
  var pushMs = { count: 0, total: 0, max: 0 };
  /* ── THE FORCED-LAYOUT CHANNEL ────────────────────────────────────────────
   * `loaf.styleAndLayout` is the frame's OWN style+layout share, and a frame
   * that only composites contributes nothing to it — which is exactly why it
   * cannot, on its own, prove that a compositor-only animation stayed off the
   * layout path: "0 ms of style+layout" and "the observer never fired" look
   * identical from the report. This channel closes that: every frame the probe
   * READS a layout property (`.caption--provisional .caption__led`'s
   * `offsetWidth` and the list's `scrollHeight`), which forces a synchronous
   * layout IF one is pending. On the compositor-only arms the read is a cache
   * hit; on the `relayout` arm the width animation has just dirtied layout, so
   * the same read pays for it. That difference is the control's whole job. */
  var forced = { count: 0, total: 0, max: 0, skipped: 0 };
  /* ── THE CONTROL'S OWN COUNTERS ───────────────────────────────────────────
   * A control that never installed itself is a failure this file already made
   * once (see `installRelayoutControl`). The report carries the WRITES, not the
   * intent, so "the control was vacuous" is readable from the payload instead of
   * being inferred from a verdict that came out green. */
  var relayoutControl = false;
  var controlEl = null;
  var control = { writes: 0, skipped: 0 };
  /* Whether the OBSERVER was installed, which is a different question from
   * whether any entry landed in the window — the old report conflated the two
   * (`loafSupported: LOAF.count > 0`) and so reported "unsupported" whenever a
   * run happened to see no long frame at all. */
  var loafObserver = false;
  var longtaskObserver = false;
  /** True only between `startedAt` and `report()`. */
  var measuring = false;
  var running = true;
  /** Held here so the beacon request outlives `report()`. See the note there. */
  var beacon = null;

  /* ── the two observers, before anything is driven ───────────────────────── */
  /* ── THE WINDOW FILTER, AND WHY IT IS THE FIRST DEFECT ───────────────────
   * `observe({buffered: true})` replays EVERY entry the browser retained since
   * the document started — model load, font load, first paint — and the first
   * version summed all of it into the window's numbers. The receipt for that
   * run read "one long-animation-frame entry in the whole window" while the
   * count it printed had come from start-up. An entry counts only if it STARTED
   * at or after `startedAt`, and everything else is COUNTED AS DROPPED rather
   * than silently discarded, so the report can say how much it threw away. */
  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        LOAF.seen += 1;
        if (!measuring || e.startTime < startedAt) { LOAF.dropped += 1; return; }
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
    loafObserver = true;
  } catch (e) { /* the report says `loafObserver:false` instead */ }

  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        LONGTASK.seen += 1;
        if (!measuring || e.startTime < startedAt) { LONGTASK.dropped += 1; return; }
        LONGTASK.count += 1;
        LONGTASK.duration += e.duration;
      });
    }).observe({ type: 'longtask', buffered: true });
    longtaskObserver = true;
  } catch (e) { /* ditto */ }

  function raf(t) {
    if (lastFrame !== null) frames.push(t - lastFrame);
    lastFrame = t;
    /* THE CONTROL DIRTIES LAYOUT FIRST, so the read below has something to pay
     * for. On every other arm nothing wrote, and the read is a cache hit. */
    if (relayoutControl) controlStep();
    /* THE READ THAT MAKES THE CHANNEL REAL. Guarded so a missing node is
     * counted (`skipped`) instead of throwing inside the frame callback and
     * stopping the whole measurement. */
    var led = document.querySelector('.caption--provisional .caption__led');
    var list = document.getElementById('caption-list');
    if (led || list) {
      var t0 = performance.now();
      if (led) { void led.offsetWidth; }
      if (list) { void list.scrollHeight; }
      var dt = performance.now() - t0;
      forced.count += 1;
      forced.total += dt;
      if (dt > forced.max) forced.max = dt;
    } else {
      forced.skipped += 1;
    }
    if (running) requestAnimationFrame(raf);
  }

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  /* ── THE RELAYOUT CONTROL ────────────────────────────────────────────────
   * The SAME element the theme animates, with the SAME cadence, but on a
   * property that changes its box: `width`, written once per frame from THIS
   * frame callback. If the instrument cannot tell this apart from the
   * compositor-only animation, its green on the real arms means nothing.
   *
   * WHY IT IS A CSSOM WRITE AND NOT A `@keyframes` RULE — measured, and this is
   * this instrument's SECOND defect. The first version appended a <style>
   * element carrying `animation:cost-relayout … !important`, and
   * `app/panel/panel.html:22-25` declares `style-src 'self'` — so the element
   * was REFUSED and the keyframes never existed. The relayout arm's computed
   * `animationName` therefore stayed the THEME's own (`sotto-5-led-live` on
   * theme-5, `none` on theme-2), i.e. that arm differed from `on` only by noise
   * and its "control went red" would have proved nothing. A CSSOM write
   * (`el.style.width = …`) is NOT governed by `style-src` and lands whatever the
   * CSP says. `control.writes` in the report is the proof that it ran. */
  function controlStep() {
    if (!controlEl || !controlEl.isConnected) {
      controlEl = document.querySelector('.caption--provisional .caption__led');
    }
    if (!controlEl) { control.skipped += 1; return; }
    /* 2 → 9 px and back: a real box change on a real element, every frame. */
    var px = 2 + (control.writes % 8);
    controlEl.style.width = px + 'px';
    control.writes += 1;
  }

  function installRelayoutControl() {
    relayoutControl = true;
  }

  /* ── THE STREAM ──────────────────────────────────────────────────────────
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
    measuring = false;
    var list = document.getElementById('caption-list');
    var payload = {
      theme: THEME,
      arm: ARM,
      seconds: SECONDS,
      rateHz: RATE_HZ,
      /* The MEASURED window, not the requested one: the arm compares the two. */
      windowMs: +(performance.now() - startedAt).toFixed(1),
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      loafObserver: loafObserver,
      longtaskObserver: longtaskObserver,
      loaf: {
        count: LOAF.count,
        seen: LOAF.seen,
        dropped: LOAF.dropped,
        duration: +LOAF.duration.toFixed(2),
        blocking: +LOAF.blocking.toFixed(2),
        styleAndLayout: +LOAF.styleAndLayout.toFixed(2),
        render: +LOAF.render.toFixed(2),
        max: +LOAF.max.toFixed(2)
      },
      longtask: {
        count: LONGTASK.count,
        seen: LONGTASK.seen,
        dropped: LONGTASK.dropped,
        duration: +LONGTASK.duration.toFixed(2)
      },
      /* ms spent forcing a synchronous layout from the frame callback. */
      forcedLayout: {
        count: forced.count,
        skipped: forced.skipped,
        total: +forced.total.toFixed(2),
        mean: +(forced.total / Math.max(1, forced.count)).toFixed(3),
        max: +forced.max.toFixed(3)
      },
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
     * request was ever issued — the payload was correct in `document.title` and
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
      /* The window OPENS here: from now on an observer entry counts. Anything
       * already buffered stays counted as dropped. */
      measuring = true;
      requestAnimationFrame(raf);
      tick();
      setTimeout(report, SECONDS * 1000);
    }, 600);
  }

  if (document.readyState === 'complete') setTimeout(main, 0);
  else window.addEventListener('load', function () { setTimeout(main, 0); });
}());
