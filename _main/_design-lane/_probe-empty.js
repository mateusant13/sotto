(() => {
  try {
    if (window.SottoSkin && window.SottoSkin.active) {
      window.SottoSkin.lines([]);
      window.SottoSkin.live({ committed: [], provisional: [] });
      window.SottoSkin.status({ word: '', state: '' });
      window.SottoSkin.level(0);
      // Freeze out the audit fixture's late retries: this shot is the idle state.
      window.SottoSkin.lines = function () {};
      window.SottoSkin.live = function () {};
      window.SottoSkin.status = function () {};
    }
  } catch (e) {}
  const r = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      x: Math.round(b.x * 10) / 10, y: Math.round(b.y * 10) / 10,
      w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10,
      pos: cs.position, display: cs.display, overflow: cs.overflowY,
      bg: cs.backgroundColor, z: cs.zIndex,
    };
  };
  const host = document.getElementById('skin');
  const sr = host && host.shadowRoot;
  if (sr) {
    const freeze = document.createElement('style');
    freeze.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}';
    sr.appendChild(freeze);
  }
  const q = (s) => (sr ? sr.querySelector(s) : null);
  return {
    theme: document.documentElement.dataset.theme,
    surface: document.body.dataset.surface,
    win: [innerWidth, innerHeight],
    body: r(document.body),
    panel: r(document.querySelector('.panel')),
    skinHost: r(host),
    stage: r(q('.skin__stage')),
    col: r(q('.skin__col')),
    panelBox: r(q('.skin__panel')),
    aside: r(q('.skin__panel > *')),
    asideHeader: r(q('.skin__panel > * > *')),
    quiet: r(q('.quiet-scroll')),
    quietKids: q('.quiet-scroll') ? q('.quiet-scroll').children.length : null,
    rows: sr ? sr.querySelectorAll('[data-skin-line]').length : null,
    empty: r(q('[data-skin-empty]')),
    emptyText: q('[data-skin-empty]') ? q('[data-skin-empty]').textContent : null,
    caption: r(q('.skin__caption')),
    captionHidden: q('.skin__caption') ? q('.skin__caption').hidden : null,
    captionPlate: r(q('.skin__caption > *')),
    footer: r(q('[data-skin-footer]')),
    hideBtn: r(q('[data-skin-hide]')),
    header: r(document.querySelector('.panel__header')),
    controls: r(document.querySelector('.panel__controls')),
    themeBtn: r(document.querySelector('#theme-button')),
    status: r(document.querySelector('.status')),
    history: r(document.querySelector('.history')),
    captions: r(document.querySelector('.captions')),
    skinCss: Array.from(sr ? sr.querySelectorAll('link') : []).map((l) => l.getAttribute('href')),
  };
})()
