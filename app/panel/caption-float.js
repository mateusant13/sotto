/* caption-float.js — the FLOATED caption: the zip's CaptionStage, translated to this panel.
 *
 * owner, 2026-10-12, verbatim: *"e ele tem um botao de linhar a legenda, que liga ela NA
 * TELA, igual um overlay, EXATAMENTE IGUAL os .zip fazem."*
 *
 * WHAT THIS MODULE OWNS. The overlay's CONTENT and nothing else. It is a sibling of
 * `.panel` in the document (the owner's rule: nothing on top of the current panel, nothing
 * in the panel's div), it is painted only while the strip surface holds
 * `data-float="on"`, and it has NO BACKGROUND EVER — the lead receipt's own note on the
 * zip's caption tailwind classes.
 *
 * WHAT IT DOES NOT OWN. The button is `panel.js`'s (`#strip-float-button`), the window
 * height is the shell's (`--strip-height`, re-read on every `setPanelSurface('strip')`),
 * and the visibility is one attribute. This module only keeps the three nodes in sync with
 * the same caption state the panel already holds, so the two surfaces can never disagree.
 *
 * DEFERRED, like `letter-swap.js`: it is not on the first-paint path. It registers itself
 * and nothing else, so a caption that lands before it executes is still painted by
 * `panel.js` and is picked up the moment this module runs. */
(function () {
  'use strict';

  var line = null;
  var prev = null;
  var meter = null;
  var meterFill = null;
  var credits = null;
  var current = null;
  var previous = null;
  var listening = false;

  function nodes() {
    if (line) return true;
    var host = document.getElementById('caption-float');
    if (!host) return false;
    line = document.getElementById('caption-float-line');
    prev = document.getElementById('caption-float-prev');
    meter = document.getElementById('caption-float-meter');
    meterFill = document.getElementById('caption-float-meter-fill');
    credits = document.getElementById('caption-float-credits');
    return !!(line && prev && meter && meterFill && credits);
  }

  /**
   * Push one caption. `panel.js` calls this from its own caption choke points, so the
   * overlay shows exactly what the panel shows — same text, same producer, same instant.
   * The previous line is kept one back, which is what makes the live line read as LIVE.
   */
  function push(text, meta) {
    if (!nodes()) return;
    var value = typeof text === 'string' ? text : '';
    if (value && value !== current) {
      previous = current;
      current = value;
    }
    line.textContent = value;
    prev.textContent = previous || '';
    // The credits are only rewritten when a meta ARRIVES. A provisional push carries
    // no producer, and erasing the line on every partial would make the overlay
    // flicker between the speaker's name and nothing.
    if (meta && typeof meta === 'object') {
      var who = [];
      if (meta.producer) who.push(String(meta.producer));
      if (meta.source) who.push(String(meta.source));
      credits.textContent = who.length ? who.join(' · ') : '';
    }
  }

  /** The listening meter. `panel.js` feeds it the same smoothed level its own bars use. */
  function setMeter(level) {
    if (!nodes() || !meterFill) return;
    var v = Number(level);
    if (!Number.isFinite(v)) v = 0;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    meterFill.style.transform = 'scaleX(' + v.toFixed(4) + ')';
    if (listening) meter.classList.add('is-on');
  }

  /** Whether the meter is on at all — the zip shows it only while audio is arriving. */
  function setListening(on) {
    if (!nodes() || !meter) return;
    listening = !!on;
    meter.classList.toggle('is-on', listening);
  }

  function state() {
    return {
      on: !!document.body && document.body.getAttribute('data-float') === 'on',
      text: current,
      prev: previous,
      listening: listening
    };
  }

  window.SottoCaptionFloat = {
    push: push,
    setMeter: setMeter,
    setListening: setListening,
    state: state
  };
})();
