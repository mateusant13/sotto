/* Sotto — strip-minimal verification driver.
 *
 * Loads the REAL `app/panel/panel.html` (via main.js in this directory, same
 * hidden-window pattern as `_main/_skin-owner/render/main.js`) and answers one
 * question per check with COMPUTED style, not markup:
 *
 *   the strip (`body[data-surface="strip"]`) is MINIMAL — the theme picker and
 *   the tune dialog stay hidden even when FORCED OPEN, while the strip's own
 *   controls stay visible; back on `panel` both popups work again.
 *
 * Forcing both open is the point: `.theme-picker` and `#tune-dialog` are
 * created by JS on `document.body`, OUTSIDE the `.panel__header`/`.history`
 * subtrees the old strip rules hide. A test that only reads the markup would
 * pass on the leak. `hidden === false` + `open === true` with
 * `display === 'none'` is the rule working against a popup that wants paint.
 */
(async function () {
  var out = { checks: {}, obs: {}, errors: [] };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  function disp(el) {
    if (!el) return 'MISSING';
    try { return getComputedStyle(el).display; } catch (e) { return 'ERR:' + String(e && e.message); }
  }
  function check(name, ok, note) {
    out.checks[name] = !!ok;
    if (!ok && note !== undefined) out.obs[name] = note;
    return !!ok;
  }
  try {
    // -- 0. the new rules exist in the PARSED stylesheet --------------------
    var pickerRule = null;
    var tuneRule = null;
    for (var si = 0; si < document.styleSheets.length; si += 1) {
      var sheet = document.styleSheets[si];
      var rules = null;
      try { rules = sheet.cssRules; } catch (e) { continue; }
      if (!rules) continue;
      for (var ri = 0; ri < rules.length; ri += 1) {
        var r = rules[ri];
        if (!r.selectorText || !r.style) continue;
        if (r.selectorText.indexOf('data-surface') < 0 || r.selectorText.indexOf('strip') < 0) continue;
        if (r.selectorText.indexOf('.theme-picker') >= 0) {
          pickerRule = { sel: r.selectorText, display: r.style.getPropertyValue('display'), prio: r.style.getPropertyPriority('display') };
        }
        if (r.selectorText.indexOf('#tune-dialog') >= 0) {
          tuneRule = { sel: r.selectorText, display: r.style.getPropertyValue('display'), prio: r.style.getPropertyPriority('display') };
        }
      }
    }
    out.obs.pickerRule = pickerRule;
    out.obs.tuneRule = tuneRule;
    check('rule_picker_strip_none_important',
      !!pickerRule && pickerRule.display === 'none' && pickerRule.prio === 'important',
      JSON.stringify(pickerRule));
    check('rule_tune_strip_none_important',
      !!tuneRule && tuneRule.display === 'none' && tuneRule.prio === 'important',
      JSON.stringify(tuneRule));

    // -- 1. onto the strip surface ------------------------------------------
    var surf = window.SottoSurfaces ? window.SottoSurfaces.set('strip') : 'NO-API';
    await sleep(150);
    out.obs.surface = surf;
    check('surface_is_strip', surf === 'strip' && document.body.dataset.surface === 'strip', String(surf));

    // -- 2. force the picker OPEN on the strip -------------------------------
    // Keyboard Enter on the strip's own theme button: the same gesture that
    // opens the picker on the panel (clicks only cycle by owner contract).
    var stripTheme = document.getElementById('strip-theme-button');
    out.obs.stripThemeButtonDisplay = disp(stripTheme);
    if (stripTheme) {
      stripTheme.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    }
    await sleep(150);
    var picker = document.querySelector('.theme-picker');
    out.obs.pickerExists = !!picker;
    out.obs.pickerHiddenAttr = picker ? !!picker.hidden : null;
    out.obs.pickerDisplayOnStrip = disp(picker);
    check('picker_exists_after_open', !!picker, 'no .theme-picker in DOM');
    check('picker_open_but_hidden_on_strip',
      !!picker && picker.hidden === false && disp(picker) === 'none',
      'hidden=' + (picker && picker.hidden) + ' display=' + disp(picker));

    // -- 3. force the tune dialog OPEN on the strip --------------------------
    var tuneOpened = false;
    var tuneErr = null;
    if (window.SottoThemeTune && typeof window.SottoThemeTune.open === 'function') {
      try { window.SottoThemeTune.open(); tuneOpened = true; }
      catch (e) { tuneErr = String(e && e.message); }
    } else {
      tuneErr = 'NO-API';
    }
    await sleep(150);
    var tune = document.getElementById('tune-dialog');
    out.obs.tuneOpenAttempt = tuneOpened;
    out.obs.tuneOpenError = tuneErr;
    out.obs.tuneExists = !!tune;
    out.obs.tuneOpenAttr = tune ? !!tune.open : null;
    out.obs.tuneDisplayOnStrip = disp(tune);
    check('tune_open_but_hidden_on_strip',
      !!tune && !!tune.open && disp(tune) === 'none',
      'open=' + (tune && tune.open) + ' display=' + disp(tune));
    if (tune && tune.open) { try { tune.close(); } catch (e) { /* measured state kept */ } }

    // -- 4. the strip's own controls stay visible -----------------------------
    var bar = document.getElementById('strip-controls');
    var live = document.getElementById('strip-live-button');
    var pause = document.getElementById('strip-pause-button');
    var open = document.getElementById('strip-open-button');
    var state = document.getElementById('strip-state');
    out.obs.stripbarDisplay = disp(bar);
    out.obs.stripLiveDisplay = disp(live);
    out.obs.stripPauseDisplay = disp(pause);
    out.obs.stripOpenDisplay = disp(open);
    out.obs.stripStateDisplay = disp(state);
    check('strip_controls_visible',
      disp(bar) !== 'none' && disp(live) !== 'none' && disp(pause) !== 'none' &&
      disp(open) !== 'none' && disp(stripTheme) !== 'none' && disp(state) !== 'none',
      JSON.stringify({ bar: disp(bar), live: disp(live), pause: disp(pause), open: disp(open), theme: disp(stripTheme), state: disp(state) }));

    // -- 5. the static hides still hold on the strip --------------------------
    var header = document.querySelector('.panel__header');
    var history = document.querySelector('.history');
    var skin = document.getElementById('skin');
    out.obs.headerDisplay = disp(header);
    out.obs.historyDisplay = disp(history);
    out.obs.skinDisplay = disp(skin);
    check('static_hides_hold_on_strip',
      disp(header) === 'none' && disp(history) === 'none' && disp(skin) === 'none',
      JSON.stringify({ header: disp(header), history: disp(history), skin: disp(skin) }));

    // -- 6. back on panel: both popups usable again (no regression) -----------
    var back = window.SottoSurfaces ? window.SottoSurfaces.set('panel') : 'NO-API';
    await sleep(150);
    out.obs.surfaceBack = back;
    if (picker) picker.hidden = true; // closed precondition: the strip step left it open, and Enter TOGGLES
    await sleep(50);
    var panelTheme = document.getElementById('theme-button');
    // OBS, not theory: is the panel button really there, and did Enter land on it?
    out.obs.panelThemeButtonExists = !!panelTheme;
    out.obs.panelThemeButtonDisplay = disp(panelTheme);
    out.obs.panelThemeButtonParent = panelTheme && panelTheme.parentElement
      ? (panelTheme.parentElement.className || panelTheme.parentElement.tagName) : null;
    out.obs.activeBefore = document.activeElement
      ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) : null;
    if (panelTheme) {
      panelTheme.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    }
    await sleep(150);
    out.obs.pickerDisplayOnPanel = disp(picker);
    out.obs.pickerHiddenOnPanel = picker ? !!picker.hidden : null;
    out.obs.activeAfter = document.activeElement
      ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) : null;
    check('picker_usable_on_panel', disp(picker) !== 'none', disp(picker));
    if (picker) picker.hidden = true;
    if (window.SottoThemeTune && typeof window.SottoThemeTune.open === 'function') {
      try { window.SottoThemeTune.open(); } catch (e) { /* recorded below */ }
    }
    await sleep(150);
    out.obs.tuneDisplayOnPanel = disp(tune);
    out.obs.tuneOpenOnPanel = tune ? !!tune.open : null;
    check('tune_usable_on_panel',
      !!tune && !!tune.open && disp(tune) !== 'none',
      'open=' + (tune && tune.open) + ' display=' + disp(tune));
    if (tune && tune.open) { try { tune.close(); } catch (e) { /* measured state kept */ } }
  } catch (e) {
    out.errors.push('driver-throw: ' + String((e && e.stack) || e));
  }
  return out;
})();
