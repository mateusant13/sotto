/* Sotto — THE REVEAL TIMELINE (lane/goal-anim), the evidence arm.
 *
 * WHY THIS FILE EXISTS. A perf fix that changes what the owner sees is not a
 * fix. The candidate change (the word reveal belongs to the NEWEST word only)
 * is argued to be pixel-identical, and an argument is not evidence — so this
 * arm RECORDS THE FRAMES: after the same controlled pushes, on every
 * `requestAnimationFrame` the provisional line is on screen, it samples the
 * computed `opacity` / `transform` / `filter` / `display` of every word span and
 * the box's scroll state, and beacons the sequence.
 *
 * THE COMPARISON is then a diff of two runs of the SAME script against the same
 * panel with one line of CSS changed (`SOTTO_PANEL_DIR` picks which): either the
 * timelines are identical frame by frame, or the first divergence is printed
 * with its frame index, its opacity and its scroll offset. "Looks the same" is
 * not accepted here; the numbers are.
 *
 * THE STREAM IS THE SAME SHAPE AS THE COST PROBE'S, just with a fixed script:
 * eight closed lines (so the box really scrolls), then one forming line grown a
 * word at a time at 120 ms — the cadence that arrives faster than theme-5's
 * 100 ms reveal, i.e. the WORST case for the change under test.
 */

(function () {
  'use strict';

  var params = {};
  String(location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
    var i = kv.indexOf('=');
    if (i > 0) params[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
  });
  var THEME = params.theme || 'theme-5';
  var PORT = params.port || '';
  var LABEL = params.side || 'run';
  var RATE = Number(params.rate || 8);
  var SAMPLES = Number(params.samples || 60);
  var PAUSE = Number(params.pause || 120);

  var timeline = [];
  var beacon = null;

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  function push(text, meta) {
    window.sotto.pushCaption(text, meta);
  }

  function r2(v) { return Math.round(v * 100) / 100; }

  /** One frame of the provisional line, as four comparable strings + geometry. */
  /** The newest word's animation, in milliseconds after the partial was pushed.
   * `startTime - pushAt` is the question this answers: a reveal that starts late
   * is a different look, and the frame cadence of a run hides it. */
  var pushAt = 0;

  function animBasis(span) {
    if (!span || !span.getAnimations) return '';
    return span.getAnimations().map(function (a) {
      var st = a.startTime === null || a.startTime === undefined
        ? 'pending' : Math.round(a.startTime - pushAt);
      var cur = a.currentTime === null || a.currentTime === undefined
        ? '?' : Math.round(a.currentTime);
      return (a.animationName || 'anim') + '@' + st + '+' + cur;
    }).join(',');
  }

  function sample() {
    var body = document.getElementById('captions-body');
    var row = document.querySelector('#caption-list > .caption--provisional');
    var words = row ? row.querySelectorAll('.caption__word') : [];
    var ops = [];
    var tf = [];
    var fl = [];
    var disp = [];
    for (var i = 0; i < words.length; i += 1) {
      var cs = getComputedStyle(words[i]);
      ops.push(r2(parseFloat(cs.opacity)));
      /* THE RAW VALUES, not a present/absent flag: a FINISHED `fill: both`
       * animation still reports `matrix(1, 0, 0, 1, 0, 0)` where the base state
       * reports `none`, and those two paint identically. A flag would call that a
       * visual difference; the string lets the diff say the same thing the pixels
       * say. */
      tf.push(cs.transform);
      fl.push(cs.filter);
      disp.push(cs.display === 'inline-block' ? 'b' : 'i');
    }
    var rect = row ? row.getBoundingClientRect() : null;
    var bodyRect = body ? body.getBoundingClientRect() : null;
    return {
      ops: ops.join(','),
      tf: tf.join('|'),   // a matrix carries commas of its own
      fl: fl.join('|'),
      disp: disp.join(''),
      scroll: body ? [Math.round(body.scrollTop), Math.round(body.scrollHeight),
        Math.round(body.clientHeight)] : null,
      /* The row's position INSIDE the scroll box, so a layout shift and a scroll
       * change cannot be confused with one another. */
      rowTop: rect && bodyRect ? Math.round(rect.top - bodyRect.top) : null,
      rowH: rect ? Math.round(rect.height) : null,
      typing: row && row.querySelector('.caption__word[data-typing]')
        ? row.querySelectorAll('.caption__word').length - 1 : -1,
      anims: animBasis(words[words.length - 1])
    };
  }

  function run() {
    /* THE HISTORY, so the box overflows and the follow has to work. */
    for (var k = 0; k < 8; k += 1) {
      push('a legenda numero ' + k + ' fecha e vai para o historico do painel agora',
        { start: k, end: k + 1, final: true });
    }
    requestAnimationFrame(function () {
      var line = 'o som chega antes da imagem';
      var steps = [4, 8, 13, 20, 30, line.length];
      var n = 0;
      /* EIGHT FRAMES PER PARTIAL, NOT a second of frames after the last one. The
       * reveal the owner asked for lasts 100 ms and lives INSIDE a push, so the
       * timeline has to be sampled where the animation is: the frames that follow
       * each partial. `step` and `t` are the alignment keys of the before/after
       * diff. */
      function grow() {
        if (n >= steps.length) { report(); return; }
        pushAt = performance.now();
        push(line.slice(0, steps[n]), { start: 100, end: 100 + n, final: false });
        var t0 = performance.now();
        var got = 0;
        (function framesOfStep() {
          var f = sample();
          f.step = n;
          f.text = line.slice(0, steps[n]).length;
          f.t = Math.round(performance.now() - t0);
          timeline.push(f);
          got += 1;
          if (got < 8) { requestAnimationFrame(framesOfStep); return; }
          n += 1;
          setTimeout(grow, 30);
        }());
      }
      grow();
    });
  }

  function report() {
    var payload = {
      probe: 'anim-visual',
      label: LABEL,
      theme: THEME,
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      pauseMs: PAUSE,
      frames: timeline
    };
    beacon = new Image();
    beacon.src = 'http://127.0.0.1:' + PORT + '/report?payload='
      + encodeURIComponent(JSON.stringify(payload));
    document.title = 'visual ' + LABEL + ' frames=' + timeline.length;
  }

  function main() {
    setTheme(THEME);
    /* Fonts settle first: a swap mid-timeline would show up as a geometry change
     * that has nothing to do with the change under test. */
    setTimeout(run, 1400);
  }

  if (document.readyState === 'complete') setTimeout(main, 0);
  else window.addEventListener('load', function () { setTimeout(main, 0); });
}());
