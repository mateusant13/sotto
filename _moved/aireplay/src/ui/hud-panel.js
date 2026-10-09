/* THE HUD BINDER — the ONLY writer of the plate's DOM.
 *
 * It does three things and refuses to do a fourth:
 *   1. writes what `HudContract.renderPlate()` decided (never decides text),
 *   2. flips `data-mapped` ONLY from `show()` / `hide()`, the two functions
 *      that stand for SPEC §1.6 step 2 and step 3,
 *   3. reads back the computed geometry, which is what the gate asserts.
 *
 * IT DOES NOT INVENT A STATE, A NUMBER, OR A COLOUR. Every string on the plate
 * comes from `HudContract`, which is the same module the gate requires, so a
 * disagreement between the panel and the contract is impossible by
 * construction rather than by review.
 *
 * THE BRIDGE. The shell (`hud-shell.py`) is the only thing that calls
 * `SottoHudBridge.*`. There is no `window.pywebview` dependency in this file
 * and no event listener on `document` for a hotkey: the KEYS ARE NOT THE
 * PANEL'S. `docs/overlay-hotkey-contract.md` §4.2(5) — "The overlay key chain
 * and the replay key chain are SEPARATE chains" — and §1 — RegisterHotKey
 * reports PRESS ONLY. A keydown listener in the document would be a THIRD
 * path that answers a press the OS already routed, which is exactly the
 * double-fire `DEAL` §6.1 and §6.3 forbid. The panel is a READOUT.
 */
(function (global) {
  'use strict';

  var C = global.HudContract;
  if (!C) { throw new Error('hud-contract.js did not load — the panel has no contract to render from'); }

  var el = {};
  function byId(id) { return document.getElementById(id); }

  function bind() {
    el.body = document.body;
    el.plate = byId('plate');
    el.glyph = byId('glyph');
    el.line1 = byId('line1');
    el.line2 = byId('line2');
    el.line3 = byId('line3');
    el.timer = byId('timer');
    var missing = Object.keys(el).filter(function (k) { return !el[k]; });
    if (missing.length) {
      throw new Error('hud-panel.html is missing element(s): ' + missing.join(','));
    }
  }

  /* ONE WRITE. `renderPlate` returns the whole plate; this writes it and
   * nothing else computes anything. */
  function paint(plate) {
    el.body.setAttribute('data-state', plate.state);
    /* `data-glyph` is the NAME, not the colour: the colours live in CSS keyed
     * by this name (SPEC §1.3's alpha budget). A state that maps to an unknown
     * name therefore paints `transparent` and is caught by PASS-5's
     * distinctness assertion — it does not silently fall back to the idle
     * colour. */
    el.plate.setAttribute('data-glyph', plate.glyph_name);
    el.line1.textContent = plate.line1;
    el.line2.textContent = plate.line2;
    /* ALWAYS assigned, including to '' — a stale binding line left in the DOM
     * is the "HUD says armed when it is not" failure (SPEC §4.3). */
    el.line3.textContent = plate.line3;
    el.timer.textContent = plate.timer;
    return plate;
  }

  var SottoHud = {
    /* SPEC §1.6 step 2 — the ONLY mapping site, reachable only from a HUD
     * binding or `--show-hud`. There is no code path here that runs at load. */
    show: function () {
      el.body.setAttribute('data-mapped', '1');
      return true;
    },
    /* SPEC §1.6 step 3 — `hide()` and nothing else. */
    hide: function () {
      el.body.setAttribute('data-mapped', '0');
      return true;
    },
    toggle: function () {
      if (el.body.getAttribute('data-mapped') === '1') { return this.hide(); }
      return this.show();
    },
    is_mapped: function () {
      return el.body.getAttribute('data-mapped') === '1';
    },

    /* The one render entry point. `state_token` is an enum name (SPEC §3.1)
     * and `ctx` is the measured context — never a phrase. */
    render: function (state_token, ctx) {
      return paint(C.renderPlate(state_token, ctx || {}));
    },

    /* SPEC §5 `hud.anchor` — one attribute write, and `hidden` is a real
     * value of the enum rather than a boolean smuggled in beside it. */
    set_anchor: function (anchor) {
      if (C.ANCHORS.indexOf(anchor) < 0) {
        throw new Error('unknown hud.anchor ' + JSON.stringify(anchor) +
          ' — expected one of ' + C.ANCHORS.join('|'));
      }
      el.body.setAttribute('data-anchor', anchor);
      return anchor;
    },

    /* SPEC §5 — the DPI-scaled geometry, written ONCE at load from the shell's
     * monitor report. This file never calls a DPI API: SPEC §2.4 requires the
     * detector to be read-only and a script asking the OS for a scale factor
     * is the same class of move. */
    apply_geometry: function (dpi, display_w) {
      var r = document.documentElement.style;
      r.setProperty('--plate-max-w', C.plate_width_px(dpi, display_w) + 'px');
      r.setProperty('--plate-min-w', C.scale_px('plate_min_w_px', dpi) + 'px');
      r.setProperty('--corner-radius', C.scale_px('corner_radius_px', dpi) + 'px');
      r.setProperty('--glyph-px', C.scale_px('glyph_px', dpi) + 'px');
      r.setProperty('--inset-px', C.scale_px('inset_px', dpi) + 'px');
      r.setProperty('--font-primary', C.scale_px('font_px_primary', dpi) + 'px');
      r.setProperty('--font-secondary',
        Math.max(C.PARAMS.font_px_secondary_floor.value,
                 Math.round(C.PARAMS.font_px_secondary_ratio.value *
                            C.scale_px('font_px_primary', dpi))) + 'px');
      return { dpi: dpi, display_w: display_w,
               plate_max_w: C.plate_width_px(dpi, display_w) };
    },

    /* WHAT THE GATE READS. It reports the COMPUTED values, not the attributes
     * we set: a panel that set `data-mapped="1"` and still painted nothing
     * because a CSS rule won must not be able to pass. */
    probe: function () {
      var cs = getComputedStyle(el.plate);
      var rect = el.plate.getBoundingClientRect();
      return {
        state: el.body.getAttribute('data-state'),
        mapped: el.body.getAttribute('data-mapped'),
        anchor: el.body.getAttribute('data-anchor'),
        glyph_name: el.plate.getAttribute('data-glyph'),
        glyph_rgb: getComputedStyle(el.glyph).backgroundColor,
        plate_alpha_px: cs.backgroundColor,
        plate_visible: cs.visibility,
        plate_opacity: cs.opacity,
        plate_rect: { w: Math.round(rect.width), h: Math.round(rect.height),
                      x: Math.round(rect.x), y: Math.round(rect.y) },
        line1: el.line1.textContent,
        line2: el.line2.textContent,
        line3: el.line3.textContent,
        timer: el.timer.textContent,
        /* SPEC §1.1's ceiling, MEASURED off the live DOM rather than asserted
         * from the markup: count the rows that are painting text. */
        painted_lines: [el.line1, el.line2, el.line3].filter(function (n) {
          return n.textContent.length > 0 && n.offsetHeight > 0;
        }).length
      };
    }
  };

  /* THE BRIDGE — what `hud-shell.py` calls into. Present with a NO-OP default
   * so the document is inert if it is ever opened directly (and so opening it
   * directly paints nothing, which is the SPEC §1.6 rule again). */
  global.SottoHudBridge = global.SottoHudBridge || {
    set_state: function () {},
    set_bindings: function () {},
    show: function () {},
    hide: function () {},
    log: function () {}
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bind(); });
  } else {
    bind();
  }

  /* Modules load as classic scripts before this one; `testdrive` is the gate's
   * entry point and is the ONLY way to make the panel paint without a window,
   * which is what the headless arms use. It is a function, not a call — nothing
   * here paints at load. */
  global.SottoHud = SottoHud;

})(window);