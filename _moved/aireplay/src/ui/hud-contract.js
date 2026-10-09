/* THE HUD CONTRACT — DOM-FREE, and it is ONE file for the panel AND the gate.
 *
 * WHY DOM-FREE (the same reason `H:\sotto\app\panel\caption-formulation.js`,
 * `history-source.js` and `surface.js` are DOM-free): the gate must be able to
 * `require()` this and assert the bindings against `docs/overlay-hotkey-contract.md`
 * and `specs/05-overlay-hud.md` WITHOUT launching a window, and the panel must
 * read the same table so there is no second copy to drift. A fact that lives in
 * two files is a fact that will disagree.
 *
 * EVERY NUMBER HERE IS COPIED FROM A NAMED SOURCE AND THE SOURCE IS NAMED.
 * Nothing in this file is our invention unless it carries `(⚙ ours)`.
 *
 *   SPEC   = `H:\sotto\_moved\aireplay\specs\05-overlay-hud.md`
 *   DEAL   = `H:\sotto\_moved\aireplay\docs\overlay-hotkey-contract.md`
 *
 * WHAT IS **NOT** HERE, ON PURPOSE:
 *   - the native layered-window HUD of SPEC §1.2-§1.6. That is a C++
 *     `hud.h` inside the capture process (`SPEC` §7) and `src/capture/**` is
 *     ANOTHER LANE'S FILES (lane brief rule 5). What is here is the SURFACE:
 *     the plate the user reads, and the shell that refuses to map it.
 *   - any claim that a key works in-game. `DEAL` §4.5 and `SPEC` §4.5 both say
 *     that is `NOT MEASURED`; no game has been run on this host.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) { module.exports = api; }
  root.HudContract = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /* ======================================================================
   * §1 — THE STATES. SPEC §3.1, eleven of them, and the rule that decides
   * the naming: **the HUD's word and the log's word are the same string**.
   * `token` IS the enum name, verbatim; nothing paraphrases it. That rule
   * exists because this repo already paid for a run whose verdict
   * disagreed with the state it emitted in the same run (`H:\sotto\AGENTS.md`
   * verdict-order bullet, `worker/runs/exit3-armB-worker.jsonl`).
   * ==================================================================== */

  /* Glyph colours are SPEC §1.3's alpha budget, verbatim (ARGB premultiplied).
   * `recording` red and `error` red-orange are DELIBERATELY different values:
   * SPEC §1.3 — "deliberately distinct from the recording red so a failure
   * never reads as 'recording'". A HUD that cannot tell you it failed is the
   * defect SPEC was written for. */
  var GLYPH = {
    saving:   0xfff0b43c, /* SPEC §1.3 amber — transient, not failure */
    armed:    0xff56be78, /* SPEC §1.3 green  — ready, not doing anything */
    recording:0xffe24a4a, /* SPEC §1.3 red    — the only saturated pixel */
    error:    0xffe0553a, /* SPEC §1.3 red-orange, distinct from recording */
    none:     0x00000000  /* HIDDEN paints no glyph at all (SPEC §3.1) */
  };

  var PLATE = 0x0c0c10;      /* SPEC §1.3 */
  var PLATE_ALPHA = 204;     /* SPEC §1.3 — 80 % */
  var OUTLINE_ALPHA = 64;    /* SPEC §1.3 — 25 % */

  var STATES = [
    /* token,        glyph,      alpha, meaning, source */
    ['HIDDEN',                'none',       0, 'window exists unmapped; nothing published', 'SPEC §3.1'],
    ['ARMING',                'saving',     PLATE_ALPHA, 'a HUD binding fired; capture self-test has not returned', 'SPEC §3.1'],
    ['IDLE',                  'armed',      PLATE_ALPHA, 'armed, recording nothing, ring filling', 'SPEC §3.1'],
    ['RECORDING',             'recording',  PLATE_ALPHA, 'manual record running', 'SPEC §3.1'],
    ['SAVING',                'saving',     PLATE_ALPHA, 'the cut/write is running', 'SPEC §3.1'],
    ['HIDDEN_EXCLUSIVE',      'error',      0, 'exclusive fullscreen: window unmapped, tray+toast carry it', 'SPEC §3.1'],
    ['ERROR_SILENT_DEVICE',   'error',      PLATE_ALPHA, 'device opened and delivered digital silence', 'SPEC §3.1/§3.3'],
    ['ERROR_DEVICE_EXHAUSTED','error',      PLATE_ALPHA, 'every candidate capture source refused or flat', 'SPEC §3.1/§3.3'],
    ['ERROR_CORRUPT_ROW',     'error',      PLATE_ALPHA, 'a queue/IPC record arrived malformed and was rejected', 'SPEC §3.1/§3.3'],
    ['ERROR_ENCODER_REFUSED', 'error',      PLATE_ALPHA, 'no encoder initialised, so the hotkey was never armed', 'SPEC §3.1/§3.3'],
    ['ERROR_PROTECTED',       'error',      PLATE_ALPHA, 'protected content blocks capture', 'SPEC §3.1/§2.6']
  ];

  /* token -> {glyph, alpha, meaning, source}. Fails LOUD rather than silently
   * defaulting: an unknown state that quietly painted the idle glyph is exactly
   * the `PASS-5` RED arm (SPEC §6: "a build where HIDDEN_EXCLUSIVE paints the
   * idle glyph ⇒ the distinctness assertion fails"). */
  function state(token) {
    for (var i = 0; i < STATES.length; i++) {
      if (STATES[i][0] === token) {
        return {
          token: token,
          glyph: GLYPH[STATES[i][1]],
          glyph_name: STATES[i][1],
          plate_alpha: STATES[i][2],
          meaning: STATES[i][3],
          source: STATES[i][4]
        };
      }
    }
    throw new Error('unknown HudState token ' + JSON.stringify(token) +
      ' — the log token must string-equal an enum name (SPEC §3.1)');
  }

  function tokens() { return STATES.map(function (s) { return s[0]; }); }

  function is_error(t) { return t.indexOf('ERROR_') === 0; }

  /* ======================================================================
   * §2 — THE BINDINGS. Two SEPARATE chains, and `DEAL` §4.2(5) is the rule
   * that keeps them apart: "The overlay key chain and the replay key chain
   * are SEPARATE chains. A taken replay key must never change which overlay
   * key is live, and vice versa."
   * ==================================================================== */

  /* Win32 virtual-key codes. Only the ones this panel names, so the file is
   * readable; `mods` is the Win32 mask WITHOUT MOD_NOREPEAT (0x4000) because
   * `DEAL` §2.1 says the trigger ORs it in itself. */
  var VK = {
    F7: 0x76, F9: 0x78, F10: 0x79, F11: 0x7A, F12: 0x7B,
    Z: 0x5A, S: 0x53, R: 0x52, C: 0x43,
    SNAPSHOT: 0x2C /* VK_SNAPSHOT == PrintScreen */
  };
  var MOD = { ALT: 0x0001, CONTROL: 0x0002, SHIFT: 0x0004, NOREPEAT: 0x4000, WIN: 0x0008 };

  /* --- 2a. THE HUD CHAIN — SPEC §4.2, ten bindings, verbatim ------------
   * SPEC §8: "If a binding table and `src/capture/trigger.cpp` ever disagree,
   * THE CODE IS WRONG, not this table — the table is the contract."
   * `semantic` is `press` for every row and that is load-bearing, not lazy:
   * `DEAL` §3.3 forbids building a hold or a release on `RegisterHotKey`,
   * because §1 of `DEAL` measured that the API reports PRESS ONLY. */
  var HUD_BINDINGS = [
    /* `dup_of` names the ladder rung this row DELIBERATELY mirrors.
     *
     * THIS IS A REPORTED CONTRADICTION, NOT A DEFECT, and it is load-bearing
     * enough to be a field rather than a comment. SPEC §4.2 rows H1-H6 name
     * `trigger.cpp:69`, `:68`, `:70`, `:71`, `:72`, `:73` as the rungs they
     * match, and H2's own rationale is "a duplicate so a machine that owns
     * `Alt+F9` still has one free". So SPEC §4.2 and DEAL §2.1 DELIBERATELY
     * share 5 `vk`+`mods` pairs.
     *
     * DEAL §6.3 says "Duplicate bindings must be refused at arm time". Read
     * across the two documents that rule would refuse 5 of SPEC's own rows,
     * which cannot be the intent. THE RESOLUTION THIS FILE TAKES, stated so a
     * reviewer can disagree with it by name:
     *   - §6.3's refusal applies WITHIN one arm (one trigger's own ladder),
     *     because that is the only place a double-fire happens.
     *   - a HUD row and a ladder rung are the SAME physical key on purpose:
     *     one press, one cut, two subscribers of the same event.
     *   - therefore the invariant worth asserting is NOT "no overlap" but
     *     "every overlap is DECLARED". An undeclared collision is the defect
     *     `DEAL` §6.3 is really about, and that is what the gate checks.
     * DEAL §2.4's "No collision with §2.1" claim is about the OVERLAY chain
     * (`Alt+C`) only, and that one IS enforced as a hard zero below. */
    ['H1',  VK.F9,      MOD.ALT,                  'Alt+F9',     'press', 30, 'save last 30 s', 'Alt+F9'],
    ['H2',  VK.F9,      MOD.CONTROL,              'Ctrl+F9',    'press', 30, 'save last 30 s', null],
    ['H3',  VK.F10,     MOD.ALT,                  'Alt+F10',    'press', 30, 'save last 30 s', 'Alt+F10'],
    ['H4',  VK.F11,     MOD.ALT,                  'Alt+F11',    'press', 60, 'save last 60 s', 'Alt+F11'],
    ['H5',  VK.F12,     MOD.CONTROL,              'Ctrl+F12',   'press', 60, 'save last 60 s', 'Ctrl+F12'],
    ['H6',  VK.SNAPSHOT, 0,                       'PrintScreen','press', 10, 'save last 10 s', 'PrintScreen'],
    ['H7',  VK.F10,     MOD.CONTROL,              'Ctrl+F10',   'press', null, 'toggle manual record', null],
    ['H8',  VK.Z,       MOD.ALT,                  'Alt+Z',      'press', null, 'toggle HUD', null],
    ['H9',  VK.S,       MOD.ALT,                  'Alt+S',      'press', null, 'cycle HUD anchor', null],
    ['H10', VK.F7,      MOD.ALT,                  'Alt+F7',     'press', null, 'refuse forced borderless', null]
  ].map(function (r) {
    return {
      id: r[0], vk: r[1], mods: r[2], name: r[3], semantic: r[4],
      window_s: r[5], action: r[6], dup_of: r[7],
      source: 'SPEC §4.2 row ' + r[0],
      /* SPEC §4.3: exactly three outcomes and none of them is silent —
       * `registered` | `pinned` (taken by another process, poll still works)
       * | `invisible` (UAC secure desktop — the ONLY case the HUD is allowed
       * to say the key does not work, and it says why). */
      status: 'registered'
    };
  });

  /* --- 2b. THE SOTTO OVERLAY CHAIN — DEAL §2.4, verbatim ----------------
   * These are the KEYS OF THE PANEL ITSELF (Alt+C toggles this window). They
   * are not HUD keys and they are not in `trigger.cpp`. They are declared here
   * so the panel can SHOW which one is live, per DEAL §4.2(6): "If every key
   * in a chain is taken, say so LOUDLY, once." */
  var OVERLAY_BINDINGS = [
    ['Alt+C',        VK.C, MOD.ALT],
    ['Alt+Shift+C',  VK.C, MOD.ALT | MOD.SHIFT],
    ['Ctrl+Alt+C',   VK.C, MOD.ALT | MOD.CONTROL],
    ['Ctrl+Shift+C', VK.C, MOD.SHIFT | MOD.CONTROL]
  ].map(function (r) {
    return {
      name: r[0], vk: r[1], mods: r[2],
      semantic: 'press',
      action: 'toggle the caption panel',
      source: 'DEAL §2.4',
      status: 'registered'
    };
  });

  /* --- 2c. THE REPLAY LADDER — DEAL §2.1, carried ONLY to prove DISJOINT --
   * The panel never registers these and never fires on them. They are here
   * for exactly one assertion, which the gate makes: no `vk`+`mods` pair is
   * in two chains (DEAL §6.3 — "a future edit that adds Ctrl+Alt+R to the
   * overlay chain must not silently double-fire").
   * ORDER IS DEAL §2.1's, NOT trigger.cpp's: DEAL §2.2 deliberately puts F12
   * LAST because MS Learn reserves it for the debugger at all times, and
   * DEAL §2.3 demotes PrintScreen because it is OS-owned. DEAL §2.2 says if
   * F12 stays at position 1 "that is a decision to record, not a detail". */
  var REPLAY_LADDER = [
    ['Ctrl+Alt+R',   VK.R, MOD.CONTROL | MOD.ALT, 30],
    ['Alt+F11',      VK.F11, MOD.ALT, 60],
    ['Ctrl+F12',     VK.F12, MOD.CONTROL, 60],
    ['F11',          VK.F11, 0, 30],
    ['F10',          VK.F10, 0, 30],
    ['Alt+F10',      VK.F10, MOD.ALT, 30],
    ['Alt+F9',       VK.F9,  MOD.ALT, 30],
    ['PrintScreen',  VK.SNAPSHOT, 0, 10],
    ['F12',          VK.F12, 0, 30]
  ].map(function (r) {
    return { name: r[0], vk: r[1], mods: r[2], window_s: r[3], source: 'DEAL §2.1' };
  });

  /* `HotkeyBinding::operator==` (`trigger.h:79`) compares exactly `vk` and
   * `mods` — DEAL §6.3. So the collision predicate is the same pair. */
  function collisions(a, b) {
    var out = [];
    for (var i = 0; i < a.length; i++) {
      for (var j = 0; j < b.length; j++) {
        if (a[i].vk === b[j].vk && a[i].mods === b[j].mods) {
          out.push(a[i].name + ' <-> ' + b[j].name);
        }
      }
    }
    return out;
  }

  /* SPEC §4.3 line 3, rendered. NEVER a bare list of names: a binding that
   * silently degraded is the exact defect SPEC §4.3 calls out. */
  function binding_line(bindings) {
    return bindings.map(function (b) {
      return b.name + ' ' + (b.status === 'registered' ? 'live'
                          : b.status === 'pinned'      ? 'taken by another app'
                          : b.status === 'invisible'   ? 'unreachable (UAC secure desktop)'
                          : 'unknown(' + b.status + ')');
    }).join(' · ');
  }

  /* ======================================================================
   * §3 — THE PARAMETERS. SPEC §5, every row this surface actually uses.
   * An unused key is a deleted key in this repo, so this is not "all of §5":
   * it is the subset the DOM surface reads, and `used_params` says which.
   * ==================================================================== */

  var PARAMS = {
    plate_max_w_px:  { value: 480, kind: 'dpi', min: 240, source: 'SPEC §5' },
    plate_min_w_px:  { value: 240, kind: 'dpi', min: 240, source: 'SPEC §5' },
    corner_radius_px:{ value: 8,   kind: 'dpi', min: 8,   source: 'SPEC §5' },
    glyph_px:        { value: 12,  kind: 'dpi', min: 12,  source: 'SPEC §5' },
    inset_px:        { value: 24,  kind: 'dpi', min: 24,  source: 'SPEC §5' },
    font_px_primary: { value: 13,  kind: 'dpi', min: 12,  max: 22, source: 'SPEC §5' },
    font_px_secondary_ratio: { value: 0.82, kind: 'ratio', min: 0.82, source: 'SPEC §5 (ratio, not a second constant)' },
    font_px_secondary_floor: { value: 11, kind: 'px', min: 11, source: 'SPEC §5' },
    fade_in_ms:      { value: 120,  kind: 'ms', min: 120, source: 'SPEC §5' },
    fade_out_ms:     { value: 250,  kind: 'ms', min: 250, source: 'SPEC §5' },
    success_hold_ms: { value: 2000, kind: 'ms', min: 2000, source: 'SPEC §5' },
    ring_seconds_decimals: { value: 1, kind: 'decimal', min: 1, source: 'SPEC §5' }
  };

  function used_params() { return Object.keys(PARAMS).sort(); }

  /* SPEC §5's DPI rule, verbatim: "The HUD is sized in DPI, never in pixels."
   * Clamped, not scaled, and `dpi` comes from the SHELL's own monitor report —
   * this file never calls a DPI API (SPEC §2.4: the detector must be read-only). */
  function scale_px(name, dpi) {
    var p = PARAMS[name];
    if (!p) { throw new Error('unknown hud parameter ' + name); }
    if (p.kind !== 'dpi') { return p.value; }
    var v = Math.round(p.value * (dpi / 96));
    if (p.max != null && v > p.max) { v = p.max; }   /* SPEC §5: clamp 22 */
    if (p.min != null && v < p.min) { v = p.min; }
    return v;
  }

  /* The plate's max width is ALSO capped at <= 25 % of the display width —
   * SPEC §5, closed decision: "no combination of DPI and resolution can
   * produce a plate that owns the screen". */
  function plate_width_px(dpi, display_w) {
    var w = scale_px('plate_max_w_px', dpi);
    var cap = Math.round(display_w * 0.25);
    return Math.max(scale_px('plate_min_w_px', dpi), Math.min(w, cap));
  }

  /* ======================================================================
   * §4 — THE RENDER. One pure function: state + context -> the plate.
   *
   * THIS IS THE ONLY PLACE TEXT IS COMPOSED, and it is DOM-FREE on purpose so
   * the gate can walk all eleven states with no window on the owner's screen
   * and compare what it PAINTS. `renderPlate` returns the exact three strings
   * and the exact colours; the DOM binder below only writes them.
   *
   * SPEC §1.1 is the ceiling: THREE lines is the maximum, plus one glyph and
   * one right-aligned timer. "A fourth line is a design failure, not a
   * feature." `renderPlate` therefore cannot emit four, and the gate asserts
   * the count.
   * ==================================================================== */

  function fmt_timer(seconds) {
    if (seconds == null || !isFinite(seconds) || seconds < 0) { return ''; }
    var s = Math.floor(seconds % 60);
    var m = Math.floor(seconds / 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  /* SPEC §5 `ring_seconds_displayed: 1` — "one decimal — '119.4 s left' is
   * useful, '119.4165 s' is a log line". */
  function fmt_ring(seconds) {
    if (seconds == null || !isFinite(seconds)) { return '—'; }
    return seconds.toFixed(PARAMS.ring_seconds_decimals.value);
  }

  /* SPEC §3.3 — each error carries the one number or string that lets the
   * owner act on it. "An error line with no actionable datum is decoration."
   * The numbers come from the CALLER's measurement; this never invents one. */
  function error_line_2(t, ctx) {
    ctx = ctx || {};
    switch (t) {
      case 'ERROR_SILENT_DEVICE':
        /* SPEC §3.3: "peak 9.2e-05 < floor 0.002 — nothing is routed into it".
         * If the measurement is missing we say SO, we do not print a zero that
         * looks measured. */
        if (ctx.peak == null || ctx.peak_floor == null) {
          return 'digital silence below the floor (peak not measured) — ' +
                 'nothing is routed into the device';
        }
        return 'peak ' + ctx.peak + ' < floor ' + ctx.peak_floor +
               ' — nothing is routed into it';
      case 'ERROR_DEVICE_EXHAUSTED':
        return ctx.reason || 'every candidate capture source was refused or flat';
      case 'ERROR_CORRUPT_ROW':
        /* SPEC §3.3: non-fatal, and the HUD must SAY it is non-fatal. */
        return (ctx.rejected == null ? 1 : ctx.rejected) +
               ' record rejected (malformed) — recording unaffected';
      case 'ERROR_ENCODER_REFUSED':
        return (ctx.encoder_status || 'no encoder') +
               (ctx.encoder_error ? ' — ' + ctx.encoder_error : '');
      case 'ERROR_PROTECTED':
        return 'protected content blocks capture' +
               (ctx.window_class ? ' — could not read ' + ctx.window_class : '');
      default:
        return ctx.reason || 'unknown failure';
    }
  }

  function renderPlate(token, ctx) {
    ctx = ctx || {};
    var s = state(token);
    var line2 = '', line3 = '', timer = '';

    switch (token) {
      case 'HIDDEN':
        /* SPEC §1.6: "There is no 'warm-up' paint, no 'armed' paint, no
         * 1-frame paint at start-up." Nothing to compose — the plate is not
         * published at all. Returning the empty strings IS the render. */
        break;

      case 'HIDDEN_EXCLUSIVE':
        /* SPEC §2.3(2): the window is NOT mapped, so the plate is never seen.
         * The text exists for the tray tooltip and the one toast, which are
         * the channels that do not need the display. */
        line2 = ctx.reason || 'exclusive fullscreen detected — HUD unmapped';
        break;

      case 'ARMING':
        line2 = ctx.reason || 'capture self-test running';
        break;

      case 'IDLE':
        line2 = ctx.reason ||
          ('armed · ' + (ctx.codec || 'H.264') +
           (ctx.bitrate_mbps ? ' · ' + ctx.bitrate_mbps + ' Mbps' : '') +
           (ctx.ring_mb ? ' · ring ' + ctx.ring_mb + ' MB' : ''));
        break;

      case 'RECORDING':
        /* SPEC §1.1's sketch: line 1 is the state, line 2 the mode/bitrate/
         * ring line, and the timer is right-aligned. */
        line2 = ctx.reason ||
          ((ctx.mode || 'gaming') +
           (ctx.resolution ? ' ' + ctx.resolution : '') +
           (ctx.fps ? ctx.fps : '') +
           (ctx.ring_s ? ' · ring ' + fmt_ring(ctx.ring_s) + ' s left' : '') +
           (ctx.bitrate_mbps ? ' · ' + ctx.bitrate_mbps + ' Mbps' : ''));
        timer = fmt_timer(ctx.elapsed_s);
        break;

      case 'SAVING':
        line2 = ctx.reason || 'writing clip…';
        timer = fmt_timer(ctx.elapsed_s);   /* SPEC §3.2: the timer FREEZES */
        break;

      default: /* every ERROR_* */
        line2 = error_line_2(token, ctx);
        break;
    }

    /* SPEC §4.3: line 3 is the binding line whenever the state is not
     * RECORDING (RECORDING spends line 3 on the mode line instead). */
    if (token !== 'RECORDING' && token !== 'HIDDEN' && ctx.bindings) {
      line3 = typeof ctx.bindings === 'string' ? ctx.bindings
                                               : binding_line(ctx.bindings);
    }

    /* SPEC §3.2 SAVING -> IDLE passes through a transient success line
     * (`saved clip_0644.mp4 · 12.4 s · 71 MB`) for `success_hold_ms`. */
    if (ctx.success_line) { line2 = ctx.success_line; }

    return {
      state: token,
      glyph: s.glyph,
      glyph_name: s.glyph_name,
      plate_alpha: s.plate_alpha,
      line1: token,          /* SPEC §3.4 rule 2: the enum name is FIRST */
      line2: line2,
      line3: line3,
      timer: timer,
      /* SPEC §1.1: three lines is the ceiling. Exported as a COUNT so the
       * gate can assert it rather than trust this comment. */
      line_count: (line2 ? 1 : 0) + (line3 ? 1 : 0) + 1,
      is_error: is_error(token)
    };
  }

  /* SPEC §4.4(2): "`Alt+Z` is never re-bound to a different combination behind
   * the user's back." The anchor cycle is the ONLY thing Alt+S moves. */
  var ANCHORS = ['top-left', 'top-right', 'hidden'];

  return {
    GLYPH: GLYPH, PLATE: PLATE, PLATE_ALPHA: PLATE_ALPHA,
    OUTLINE_ALPHA: OUTLINE_ALPHA,
    STATES: STATES, state: state, tokens: tokens, is_error: is_error,
    VK: VK, MOD: MOD,
    HUD_BINDINGS: HUD_BINDINGS,
    OVERLAY_BINDINGS: OVERLAY_BINDINGS,
    REPLAY_LADDER: REPLAY_LADDER,
    collisions: collisions, binding_line: binding_line,
    PARAMS: PARAMS, used_params: used_params, scale_px: scale_px,
    plate_width_px: plate_width_px,
    fmt_timer: fmt_timer, fmt_ring: fmt_ring,
    renderPlate: renderPlate, error_line_2: error_line_2,
    ANCHORS: ANCHORS
  };
});