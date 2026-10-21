(() => {
  const host = document.getElementById('skin');
  const sr = host && host.shadowRoot;
  const q = (s) => (sr ? sr.querySelector(s) : null);
  const input = q('.skin__panel input');
  const count = () => (sr ? sr.querySelectorAll('[data-skin-line]').length : -1);
  const empty = () => (q('[data-skin-empty]') ? q('[data-skin-empty]').textContent : null);
  const before = { rows: count(), empty: empty() };
  let match = null;
  let nomatch = null;
  if (input && window.SottoSkin) {
    input.value = 'microfone';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    match = { rows: count(), empty: empty() };
    input.value = 'zzzz-no-such-word';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    nomatch = { rows: count(), empty: empty() };
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return { theme: document.documentElement.dataset.theme, before, match, nomatch, restored: { rows: count(), empty: empty() } };
})()
