/* Sotto — the DRIVER for the revive instrument. Read from disk by main.js and
 * evaluated in the page, which is why it can use any quoting it likes (a driver
 * embedded in a JS template literal once closed itself on a stray backtick).
 *
 * It measures the owner's repair control in the REAL document, through the REAL
 * listener `panel.js` installed:
 *
 *   phase 1 (default)
 *     wiring     the footer AND the strip are role=button, tabindex=0,
 *                cursor:pointer, and the title states the cost.
 *     the death  the shell's own `{text, kind:'error'}` payload is pushed in,
 *                so the panel is showing a sticky worker death to begin with.
 *     one click  clicking the footer calls `bridge.revive` EXACTLY once, names
 *                itself, announces the repair in a sentence that is ON SCREEN,
 *                and does NOT paint it as an error.
 *     no stack   a second click (footer and strip) adds no second call.
 *   phase 2 (after a reload, so the in-flight guard is fresh)
 *     keyboard   Enter on the strip revives.
 *   absent       with no `bridge.revive` at all: nothing is called and the panel
 *                SAYS it cannot — the honesty rule `wirePause` already follows.
 */
(async () => {
  const tick = (ms) => new Promise((r) => setTimeout(r, ms === undefined ? 30 : ms));
  const out = { observations: {}, checks: {}, errors: [] };
  window.addEventListener('error', (e) => out.errors.push(String(e.message)));
  window.addEventListener('unhandledrejection', (e) => out.errors.push('rejection: ' + String(e.reason)));
  // Errors raised while the DOCUMENT WAS PARSING (an init-time throw in
  // panel.js) were caught by the preload's own listener, because this one did
  // not exist yet.
  out.errors = out.errors.concat(window.__reviveProbeErrors || []);
  out.observations.diag = typeof window.__reviveProbeDiag === 'function'
    ? window.__reviveProbeDiag() : null;
  out.observations.statusTextAtStart = (document.getElementById('status-text') || {}).textContent;

  const phase = window.__reviveProbePhase || 1;
  const calls = window.__reviveProbe || { revive: [], statusApplied: [] };
  const hasRevive = typeof (window.sotto && window.sotto.revive) === 'function';
  const status = document.getElementById('status');
  const strip = document.getElementById('strip-state');
  const text = document.getElementById('status-text');
  const stripWord = document.getElementById('strip-word');

  out.observations.elements = {
    status: !!status, strip: !!strip, statusText: !!text, stripWord: !!stripWord,
    hasRevive: hasRevive, phase: phase,
  };
  if (!status || !strip || !text) {
    out.checks.the_panel_markup_is_present = false;
    return out;
  }
  out.checks.the_panel_markup_is_present = true;

  const wired = (el) => ({
    role: el.getAttribute('role'), tab: el.getAttribute('tabindex'),
    cursor: el.style.cursor, title: el.title,
  });
  out.observations.wired = { status: wired(status), strip: wired(strip) };
  out.checks.the_footer_is_wired = wired(status).role === 'button'
    && wired(status).tab === '0' && wired(status).cursor === 'pointer';
  out.checks.the_strip_is_wired = wired(strip).role === 'button'
    && wired(strip).tab === '0' && wired(strip).cursor === 'pointer';
  out.checks.the_title_states_the_cost = /restart the pipeline/i.test(status.title || '')
    && /reload/i.test(status.title || '');

  if (!hasRevive) {
    // ── THE HONESTY ARM ─────────────────────────────────────────────────────
    out.checks.a_shell_without_revive_says_so = /not in this shell/i.test(status.title || '');
    status.click();
    await tick(20);
    out.observations.absent = {
      calls: calls.revive.length, text: text.textContent,
      offscreen: text.classList.contains('status__text--offscreen'),
    };
    out.checks.absent_revive_calls_nothing = calls.revive.length === 0;
    out.checks.absent_revive_says_so = /cannot restart the pipeline/i.test(text.textContent || '');
    return out;
  }

  if (phase === 2) {
    // ── THE STRIP'S KEYBOARD, on a fresh page ───────────────────────────────
    strip.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter', bubbles: true, cancelable: true,
    }));
    await tick(20);
    out.observations.stripEnter = { calls: calls.revive.slice(), text: text.textContent };
    out.checks.enter_on_the_strip_revives = calls.revive.length === 1;
    return out;
  }

  // ── THE STICKY DEATH FIRST, or there is nothing to take off the screen ────
  if (typeof calls.statusCb !== 'function') {
    out.checks.the_panel_subscribed_to_status = false;
    return out;
  }
  out.checks.the_panel_subscribed_to_status = true;
  calls.statusCb({ text: 'Worker stopped (exit 3) - silent-device', kind: 'error' });
  await tick(20);
  out.observations.errorState = {
    text: text.textContent,
    offscreen: text.classList.contains('status__text--offscreen'),
    error: status.classList.contains('status--error'),
  };
  out.checks.the_death_is_on_screen = status.classList.contains('status--error')
    && /exit 3/.test(text.textContent || '');

  // ── ONE CLICK ON THE FOOTER, through the real listener ────────────────────
  status.click();
  await tick(20);
  out.observations.afterClick = {
    calls: calls.revive.slice(), text: text.textContent,
    offscreen: text.classList.contains('status__text--offscreen'),
    error: status.classList.contains('status--error'),
    live: status.classList.contains('status--live'),
    stripWord: stripWord ? stripWord.textContent : null,
  };
  out.checks.one_click_calls_revive_once = calls.revive.length === 1;
  out.checks.the_click_names_itself = calls.revive[0] === 'panel-status';
  out.checks.the_repair_is_announced = /restarting the pipeline/i.test(text.textContent || '');
  // AN EMPTY SENTENCE IS NOT ON SCREEN, and the class alone cannot say that:
  // `setStatus` writes '' for a non-error state, so a check that only read the
  // clip class passed over a BLANK footer (this instrument caught exactly that).
  out.checks.the_announcement_is_on_screen =
    !text.classList.contains('status__text--offscreen')
    && (text.textContent || '').trim().length > 0;
  out.checks.the_repair_is_not_painted_as_an_error =
    !status.classList.contains('status--error') && !status.classList.contains('status--live');
  out.checks.the_death_is_gone_from_the_footer = !/exit 3/.test(text.textContent || '');
  out.checks.the_strip_says_it_too = /restarting/i.test(stripWord ? stripWord.textContent : '');

  // ── A SECOND CLICK MUST NOT STACK A SECOND RESPAWN ────────────────────────
  status.click();
  strip.click();
  await tick(20);
  out.observations.afterSecond = { calls: calls.revive.slice(), text: text.textContent };
  out.checks.a_second_click_does_not_stack = calls.revive.length === 1;
  out.checks.the_second_click_says_already = /already restarting/i.test(text.textContent || '');
  return out;
})()
