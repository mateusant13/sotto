'use strict';

/**
 * Sotto M0 — the panel renderer.
 *
 * It owns the DOM and nothing else. Captions arrive through the preload bridge
 * (`window.sotto.onCaption`) and each applied line is acknowledged back to the
 * main process, which is what makes the receiver provable from stdout: an
 * applied caption is a line in `run.log`, not an assumption.
 *
 * In M0 the caption area stays empty and shows the placeholder. Audio capture
 * is a later milestone; the API it will call is already wired and exercised.
 */

/** Cap on rendered lines, matching MAX_CAPTIONS in main.js. */
const MAX_CAPTIONS = 200;

const dom = {
  panel: document.getElementById('panel'),
  captions: document.getElementById('captions'),
  placeholder: document.getElementById('placeholder'),
  list: document.getElementById('caption-list'),
  status: document.getElementById('status'),
  statusText: document.getElementById('status-text'),
  hideButton: document.getElementById('hide-button'),
  clearButton: document.getElementById('clear-button'),
};

const bridge = window.sotto;

/** No bridge means no captions can ever arrive; say so instead of looking idle. */
if (!bridge) {
  dom.status.classList.add('status--error');
  dom.statusText.textContent = 'Preload bridge missing — captions are impossible';
  dom.placeholder.querySelector('.captions__placeholder-title').textContent = 'Panel not wired';
  dom.placeholder.querySelector('.captions__placeholder-body').textContent =
    'window.sotto is undefined. The preload script did not run, so no caption can reach this panel.';
} else {
  wireCaptions();
  wireStatus();
  wireControls();
  announceReady();
}

// ---------------------------------------------------------------------------

function wireCaptions() {
  bridge.onCaption(({ text }) => {
    addCaption(String(text || '').trim());
  });
}

/** Render one caption line and acknowledge it. */
function addCaption(text) {
  if (!text) return false;

  dom.placeholder.hidden = true;
  dom.list.hidden = false;

  const line = document.createElement('li');
  line.className = 'caption';

  const time = document.createElement('span');
  time.className = 'caption__time';
  time.textContent = new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const body = document.createElement('span');
  body.className = 'caption__text';
  body.textContent = text;

  line.append(time, body);
  dom.list.append(line);

  // Mark the newest line, drop the highlight from the previous one.
  const previous = dom.list.querySelector('.caption--latest');
  if (previous) previous.classList.remove('caption--latest');
  line.classList.add('caption--latest');

  while (dom.list.childElementCount > MAX_CAPTIONS) {
    dom.list.removeChild(dom.list.firstElementChild);
  }

  // Follow the newest line, but only when already near the bottom: yanking the
  // view away from someone reading back is worse than a stale scroll.
  const { scrollTop, scrollHeight, clientHeight } = dom.captions;
  const nearBottom = scrollHeight - scrollTop - clientHeight < 48;
  if (nearBottom) dom.captions.scrollTop = scrollHeight;

  bridge.captionApplied(text);
  setStatus('Receiving captions', 'live');
  return true;
}

function wireStatus() {
  bridge.onStatus((text) => {
    setStatus(String(text || ''), '');
  });

  bridge.onGeometry((geometry) => {
    // The renderer is told the real slab size so CSS can match the window
    // instead of guessing, which is how a panel ends up misaligned on a
    // different monitor.
    if (geometry && geometry.width) {
      document.documentElement.style.setProperty('--panel-width', `${geometry.width}px`);
    }
  });
}

/** @param {'live'|'error'|''} state */
function setStatus(text, state) {
  if (!text) return;
  dom.statusText.textContent = text;
  dom.status.classList.toggle('status--live', state === 'live');
  dom.status.classList.toggle('status--error', state === 'error');
  bridge.statusApplied(text);
}

function wireControls() {
  // Click-through is on for the transparent margin; turn it off while the
  // pointer is over the slab so these two buttons are actually clickable.
  const setInteractive = (active) => bridge.setPointerInteractive(active);
  dom.panel.addEventListener('mouseenter', () => setInteractive(true));
  dom.panel.addEventListener('mouseleave', () => setInteractive(false));

  dom.hideButton.addEventListener('click', () => bridge.hide());
  dom.clearButton.addEventListener('click', () => {
    dom.list.replaceChildren();
    dom.list.hidden = true;
    dom.placeholder.hidden = false;
    bridge.clearApplied(0);
    setStatus('Cleared', '');
  });
}

/** Tell main the page is painted and what it is showing. */
function announceReady() {
  const placeholder = dom.placeholder.textContent.replace(/\s+/g, ' ').trim();
  bridge.ready({
    captions: dom.list.childElementCount,
    placeholder,
    hasBridge: true,
  });
}