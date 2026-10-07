
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
    methods: ['pushCaption', 'setStatus', 'onCaption', 'onStatus', 'onGeometry',
              'hide', 'toggle', 'quit', 'setPointerInteractive', 'getInfo',
              'captionApplied', 'statusApplied', 'ready', 'clearApplied']
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
               className: s ? String(s.className) : null,
               error: !!(s && s.classList.contains('status--error')),
               live: !!(s && s.classList.contains('status--live')) };
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
