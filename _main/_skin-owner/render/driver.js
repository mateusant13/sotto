/* Sotto — the SKIN render instrument's driver.
 *
 * It drives the REAL panel document (loaded from `app/panel/panel.html`) through
 * the panel's OWN bridge contract (`preload.js`) and asks one question per check.
 * Nothing is hard-coded per design: the design list comes from `window.SOTTO_SKINS`
 * and every expectation is relational, because a hard-coded design name is a second
 * copy of the mockup that drifts the day it is re-frozen.
 *
 * Run: see `main.js` in this directory. Exit code is the verdict.
 */
(async function () {
  const out = { checks: {}, observations: {}, errors: [], shoot: [], themes: [] };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  // NOT requestAnimationFrame: this instrument runs in a HIDDEN window, where the
  // compositor has no reason to run a frame at all — measured, the first run of
  // this harness hung on `await frames()` and had to be killed. A timer is the
  // only thing guaranteed to fire in a window nobody is looking at.
  const frames = () => sleep(30);
  const bridge = window.sotto;

  function check(name, ok, note) {
    out.checks[name] = !!ok;
    if (!ok && note !== undefined) out.observations[name] = note;
    return !!ok;
  }

  function skinOf(id) {
    return (window.SOTTO_SKINS && window.SOTTO_SKINS.themes && window.SOTTO_SKINS.themes[id]) || null;
  }

  const skinIds = Object.keys((window.SOTTO_SKINS && window.SOTTO_SKINS.themes) || {});

  // ---- 1. the manifest carries designs, and every design mounts ------------
  check('the_skin_manifest_carries_designs', skinIds.length > 0, 'themes=' + skinIds.length);
  out.observations.skinThemes = skinIds.length;

  const mounted = [];
  const mountFailures = [];
  for (const id of skinIds) {
    document.documentElement.dataset.theme = id;
    await frames();
    await sleep(40);
    const host = document.getElementById('skin');
    const root = host && host.shadowRoot;
    const stage = root && root.querySelector('.skin__stage');
    const caption = root && root.querySelector('.skin__caption');
    const panel = root && root.querySelector('.skin__panel');
    const ok = !!root && !!stage && !!caption && !!panel
      && document.body.getAttribute('data-skin') === '1';
    mounted.push({ id, ok, sheets: root ? root.styleSheets.length : 0 });
    if (!ok) mountFailures.push(id);
  }
  check('every_skin_theme_mounts', mountFailures.length === 0, JSON.stringify(mountFailures.slice(0, 6)));
  out.observations.mounted = mounted.length;
  out.themes = skinIds.slice();

  // ---- 2. the vendor's own stylesheet is adopted, not copied by hand -------
  document.documentElement.dataset.theme = skinIds[0] || 'theme-1';
  await frames();
  await sleep(120);
  const host = document.getElementById('skin');
  const shadow = host && host.shadowRoot;
  let cssRules = 0;
  let cssHref = '';
  let keyframesSeen = 0;
  if (shadow) {
    for (const sheet of Array.from(shadow.styleSheets)) {
      const href = sheet.href || '';
      if (href.indexOf('app.css') < 0) continue;
      cssHref = href;
      try {
        cssRules = sheet.cssRules.length;
        for (const rule of Array.from(sheet.cssRules)) {
          if (rule.type === CSSRule.KEYFRAMES_RULE) keyframesSeen += 1;
        }
      } catch (err) {
        out.errors.push('cssRules unreadable: ' + err.name);
      }
    }
  }
  check('the_mockups_own_stylesheet_is_adopted', cssRules > 50 && /app\.css$/.test(cssHref),
    'href=' + cssHref + ' rules=' + cssRules);
  check('the_mockups_keyframes_survive_the_shadow_boundary', keyframesSeen > 0,
    'keyframes=' + keyframesSeen);
  out.observations.cssRules = cssRules;
  out.observations.keyframes = keyframesSeen;

  // ---- 3. nothing remote: the panel has no network ------------------------
  let remote = [];
  for (const key of Object.keys(window.SOTTO_SKIN_HTML || {})) {
    const frag = window.SOTTO_SKIN_HTML[key];
    for (const kind of Object.keys(frag)) {
      const html = String(frag[kind] || '');
      if (html.indexOf('http://') >= 0 || html.indexOf('https://') >= 0) remote.push(key + '.' + kind);
    }
  }
  check('no_frozen_fragment_reaches_the_network', remote.length === 0, JSON.stringify(remote.slice(0, 6)));

  // ---- 4. our own box is out of the way while a skin is on ----------------
  const captionsStyle = getComputedStyle(document.querySelector('.captions'));
  const historyStyle = getComputedStyle(document.querySelector('.history'));
  check('our_own_caption_box_is_hidden_while_a_skin_is_on', captionsStyle.display === 'none',
    'display=' + captionsStyle.display);
  check('our_own_transcript_drawer_is_hidden_while_a_skin_is_on', historyStyle.display === 'none',
    'display=' + historyStyle.display);

  // ---- 5. our controls survive: they are the ONE thing that stays ---------
  const hide = document.getElementById('hide-button');
  const pause = document.getElementById('panel-pause-button');
  const status = document.getElementById('status');
  const rect = (el) => (el ? el.getBoundingClientRect() : { width: 0, height: 0 });
  const visible = (el) => {
    if (!el) return false;
    const r = rect(el);
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  check('the_hide_button_is_still_on_screen', visible(hide), JSON.stringify(rect(hide)));
  check('the_pause_button_is_still_on_screen', visible(pause), JSON.stringify(rect(pause)));
  check('the_status_line_is_still_on_screen', visible(status), JSON.stringify(rect(status)));

  // ---- 6. a live caption lands in the DESIGN'S own plate ------------------
  const design = 'cine-cellar';
  document.documentElement.dataset.theme = skinOf(design) ? design : skinIds[0];
  await frames();
  await sleep(80);
  // COUNT THE CALLS, so "the row is missing" can be told apart from "the panel never
  // committed a line" — the two have different owners and the first version of this
  // instrument could not tell them apart (rows=0 with our own list holding one row).
  const calls = { live: 0, line: 0 };
  const skinApi = window.SottoSkin;
  const live0 = skinApi.live;
  const line0 = skinApi.line;
  skinApi.live = function (payload) { calls.live += 1; return live0.call(this, payload); };
  skinApi.line = function (payload) { calls.line += 1; return line0.call(this, payload); };

  const liveWord = 'extraordinario';
  const committed = 'a linha confirmada com palavras suficientes para o motor aceitar';
  // The engine commits a word only once TWO consecutive hypotheses agree on it
  // (`caption-formulation.js`), so one push is not a line: the same growing text has
  // to arrive more than once, exactly as the worker's partials do.
  for (let i = 0; i < 4; i += 1) {
    bridge.pushCaption(committed, { start: 1, end: 4.5 + i, final: false, route: 'stream' });
    await sleep(420);
  }
  await sleep(200);
  bridge.pushCaption(committed + ' ' + liveWord, { start: 1, end: 6.2, final: false, route: 'stream' });
  await sleep(420);
  const shadow2 = document.getElementById('skin').shadowRoot;
  const wordHost = shadow2 && shadow2.querySelector('.skin__caption');
  const plateText = wordHost ? (wordHost.textContent || '').replace(/\s+/g, ' ').trim() : '';
  check('a_caption_word_lands_in_the_designs_own_plate', plateText.indexOf(liveWord) >= 0,
    'plate="' + plateText.slice(0, 160) + '" calls=' + JSON.stringify(calls));
  out.observations.plate = plateText.slice(0, 200);
  out.shoot.push('cine-cellar-live');

  // ---- 7. a closed line lands in the design's own history list -----------
  bridge.pushCaption(committed + ' ' + liveWord + ', e a linha fecha aqui.',
    { start: 1, end: 9, final: true, route: 'final' });
  await sleep(2200);
  const shadow3 = document.getElementById('skin').shadowRoot;
  const rows = shadow3 ? shadow3.querySelectorAll('[data-skin-line]') : [];
  const rowText = rows.length ? (rows[rows.length - 1].textContent || '').replace(/\s+/g, ' ').trim() : '';
  const slots = (window.SottoSkin && window.SottoSkin.slots()) || {};
  check('a_closed_line_lands_in_the_designs_own_row', rows.length > 0 && rowText.length > 0,
    'rows=' + rows.length + ' ourRows=' + document.querySelectorAll('#caption-list li').length
    + ' lineCalls=' + calls.line + ' liveCalls=' + calls.live
    + ' historyList=' + !!slots.historyList + ' template=' + !!slots.historyTemplate
    + ' last="' + rowText.slice(0, 80) + '"');
  out.observations.rows = rows.length;
  out.observations.ourRows = document.querySelectorAll('#caption-list li').length;
  out.observations.lineCalls = calls.line;
  out.observations.liveCalls = calls.live;
  out.observations.slotKeys = Object.keys(slots);
  out.shoot.push('cine-cellar-line');

  // ---- 8. the mockup's invented numbers are GONE, not translated ---------
  // "GONE" MEANS NOT PAINTED, not "no element anywhere holds the string": silencing
  // a filter chip hides the whole `<button>`, and the chip's own leaf keeps its text.
  // The first version of this check read `el.hidden` alone and reported five survivors
  // that were inside hidden buttons. Walk the ancestors and the computed style.
  const names = ['june', 'sofia', 'marlow', 'toma', 'reader', 'host', 'ines', 'alun', 'cleo', 'pia'];
  function rendered(el) {
    let node = el;
    while (node) {
      // The walk ends at the shadow root, which is NOT an Element:
      // `getComputedStyle` on it throws `parameter 1 is not of type
      // 'Element'` and aborts the whole instrument (measured 2026-10-08).
      // Only Elements have computed style; stop at the root first.
      if (node === shadow3) break;
      if (node.hidden) return false;
      if (node.nodeType === 1) {
        const cs = getComputedStyle(node);
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      }
      node = node.parentNode;
    }
    return true;
  }
  const invented = [];
  for (const el of Array.from(shadow3.querySelectorAll('*'))) {
    if (el.children.length) continue;
    const text = (el.textContent || '').trim();
    if (!text || !rendered(el)) continue;
    const low = text.toLowerCase();
    if (/^\d+%$/.test(text) || /^\d+\s*wpm$/i.test(text) || /^\d+\s*speakers?$/i.test(text)) invented.push(text);
    else if (names.indexOf(low) >= 0) invented.push(text);
  }
  check('the_mockups_invented_numbers_are_gone', invented.length === 0,
    JSON.stringify(invented.slice(0, 8)));
  out.observations.silenced = (window.SottoSkin && window.SottoSkin.slots() && window.SottoSkin.slots().silenced) || 0;

  // ---- 9. the design's brand slot wears OUR name -------------------------
  const brandWanted = 'sotto';
  const chromeText = (shadow3.querySelector('.skin__chrome') || { textContent: '' }).textContent || '';
  check('the_designs_brand_slot_says_sotto', chromeText.toLowerCase().indexOf(brandWanted) >= 0,
    'chrome="' + chromeText.replace(/\s+/g, ' ').trim().slice(0, 90) + '"');

  // ---- 10. a theme with NO skin keeps the panel it had -------------------
  document.documentElement.dataset.theme = 'theme-1';
  await frames();
  await sleep(120);
  const noSkin = !document.body.getAttribute('data-skin');
  const skinHidden = getComputedStyle(document.getElementById('skin')).display === 'none';
  const ownBoxBack = getComputedStyle(document.querySelector('.captions')).display !== 'none';
  check('a_theme_without_a_skin_keeps_the_old_panel', noSkin && skinHidden && ownBoxBack,
    JSON.stringify({ noSkin, skinHidden, ownBoxBack }));

  // ---- 11. the shots. A `capturePage` is a MAIN-process call, so the driver
  // returns a PLAN and `main.js` walks it: one theme per shot, each with its own
  // live line, because a screenshot taken after the walk shows only the last one
  // (measured: five shots, one design, all byte-identical).
  out.shootPlan = [];
  for (const id of skinIds) {
    out.shootPlan.push({
      name: id.replace(/[^a-z0-9-]/gi, ''),
      theme: id,
      first: 'a legenda ao vivo chega aqui palavra a palavra',
      second: 'e a linha fecha quando o motor decide.',
    });
  }
  return out;
}())
