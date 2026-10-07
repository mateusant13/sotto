
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const list = document.getElementById('caption-list');
  const status = document.getElementById('status');
  const lines = list ? Array.from(list.children).map((li) => {
    const body = li.querySelector('.caption__text');
    return {
      text: body ? body.textContent : txt(li),
      provisional: li.classList.contains('caption--provisional'),
      latest: li.classList.contains('caption--latest'),
    };
  }) : null;
  const ph = document.getElementById('placeholder');
  const pt = document.querySelector('.captions__placeholder-title');
  const pb = document.querySelector('.captions__placeholder-body');
  return {
    url: location.href,
    live: {
      count: list ? list.childElementCount : -1,
      lines: lines,
      provisionalCount: lines
        ? lines.filter((line) => line.provisional).length : -1,
      hint: txt(document.getElementById('captions-hint')).trim(),
      hidden: list ? !!list.hidden : null,
      // THE FOLLOW, AS THREE NUMBERS. The owner's report was *"a transcricao nao
      // ta dando auto scroll no painel"* and no existing field could confirm or
      // refute it: `count` says how many lines exist, not whether the newest one
      // is on screen. `atBottom` is the exact predicate the panel's own follow
      // rule uses, read from the element that actually scrolls
      // (`#captions-body`, whose CSS is `overflow-y: auto`).
      scroll: (() => {
        const box = document.getElementById('captions-body');
        if (!box) return null;
        const scrollTop = box.scrollTop;
        const scrollHeight = box.scrollHeight;
        const clientHeight = box.clientHeight;
        return {
          top: scrollTop,
          height: scrollHeight,
          client: clientHeight,
          atBottom: (scrollHeight - scrollTop - clientHeight) < 48,
          overflowing: scrollHeight > clientHeight + 4,
        };
      })(),
    },
    status: {
      text: txt(document.getElementById('status-text')).trim(),
      kind: status
        ? (status.classList.contains('status--error') ? 'error'
          : status.classList.contains('status--live') ? 'live' : 'busy')
        : null,
    },
    placeholder: {
      hidden: ph ? !!ph.hidden : null,
      title: txt(pt).trim(),
      body: txt(pb).trim(),
    },
  };
})()
