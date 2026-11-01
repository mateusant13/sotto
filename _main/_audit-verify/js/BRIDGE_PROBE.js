
(() => {
  const missing = document.body.textContent.indexOf('Preload bridge missing') >= 0;
  return {
    hasSotto: typeof window.sotto === 'object' && window.sotto !== null,
    // Which document is this, really? A probe that reports "the bridge is
    // there" while measuring a page with no `#panel` in it is a probe lying by
    // omission, so the document's own identity travels with the verdict.
    url: location.href,
    title: document.title,
    readyState: document.readyState,
    hasPanelElement: !!document.getElementById('panel'),
    // `setStripOffset` is in the list because the page's drag probes for it with
    // `typeof bridge.setStripOffset === 'function'` and SILENTLY skips the shell
    // half when it is absent (panel.html:1126). A probe that does not name the
    // method cannot report it missing, so the count is the live receipt.
    methods: ['pushCaption', 'setStatus', 'onCaption', 'onExternalCaption', 'onStatus', 'onGeometry',
              'hide', 'toggle', 'quit', 'setPointerInteractive', 'getInfo',
              'captionApplied', 'statusApplied', 'ready', 'clearApplied',
              'setStripOffset', 'beginWindowDrag', 'setLiveEnabled', 'pause']
              .filter((m) => typeof window.sotto[m] === 'function'),
    hotkey: window.sotto ? window.sotto.HOTKEY : null,
    platform: window.sotto ? window.sotto.platform : null,
    panelSaidBridgeMissing: missing,
    statusText: (document.getElementById('status-text') || {}).textContent || '',

    // WHAT THE PANEL SHOWS, not what the shell intended to send it. The
    // `statusText` above is the footer line; the two class flags are how the
    // panel paints severity (`status--error` is the red one), and the
    // placeholder block is the headline the owner reads before any caption
    // exists. A dump that carries only the text cannot tell "the panel showed
    // a dead worker" from "the panel showed the word `done` in a neutral
    // colour", which is a distinction this shell has already been wrong about.
    status: (() => {
      const s = document.getElementById('status');
      return { text: (document.getElementById('status-text') || {}).textContent || '',
               // THE WORKER'S OWN CAUSE (owner, 2026-10-21). The panel shows only
               // `ready` / `not ready`; the cause moved into the 3-dot menu
               // (`#panel-menu-cause`, mirrored on `documentElement.dataset.workerCause`).
               // A dump that reads only `text` above can no longer see the device,
               // so the cause is published HERE too.
               cause: (document.getElementById('panel-menu-cause') || {}).textContent
                      || (document.documentElement.dataset ? document.documentElement.dataset.workerCause : '')
                      || '',
               className: s ? String(s.className) : null,
               error: !!(s && s.classList.contains('status--error')),
               live: !!(s && s.classList.contains('status--live')),
               noAudio: !!(s && s.classList.contains('status--noaudio')) };
    })(),
    placeholder: (() => {
      const ph = document.getElementById('placeholder');
      const t = document.querySelector('.captions__placeholder-title');
      const b = document.querySelector('.captions__placeholder-body');
      return { hidden: ph ? !!ph.hidden : null,
               warming: !!(ph && ph.classList.contains('captions__placeholder--warming')),
               title: (t || {}).textContent || '',
               body: (b || {}).textContent || '' };
    })(),
    captions: (() => {
      const l = document.getElementById('caption-list');
      return { count: l ? l.childElementCount : -1, hidden: l ? !!l.hidden : null };
    })()
  };
})()
