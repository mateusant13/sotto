(() => {
  try {
    if (window.SottoSkin && window.SottoSkin.active) {
      window.SottoSkin.lines([]);
      window.SottoSkin.live({ committed: [], provisional: [] });
      window.SottoSkin.lines = function () {};
      window.SottoSkin.live = function () {};
    }
  } catch (e) {}
  const host = document.getElementById('skin');
  const sr = host && host.shadowRoot;
  const q = (s) => (sr ? sr.querySelector(s) : null);
  const list = q('.quiet-scroll > div');
  const kids = [];
  const sc = q('.quiet-scroll');
  if (sc) {
    for (const c of sc.children) {
      const cs = getComputedStyle(c);
      kids.push({ tag: c.tagName, cls: c.className, hidden: c.hidden, disp: cs.display,
                  text: (c.textContent || '').trim().slice(0, 80), h: c.getBoundingClientRect().height });
    }
  }
  return {
    theme: document.documentElement.dataset.theme,
    headerHTML: q('.skin__panel > * > *') ? q('.skin__panel > * > *').innerHTML.slice(0, 1800) : null,
    scrollerHTML: sc ? sc.innerHTML.slice(0, 3000) : null,
    scrollerKids: kids,
    listHidden: list ? list.hidden : null,
    emptyHidden: q('[data-skin-empty]') ? q('[data-skin-empty]').hidden : null,
  };
})()
