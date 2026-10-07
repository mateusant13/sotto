
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const history = document.getElementById('history');
  const captions = document.getElementById('captions');
  const out = {
    url: location.href,
    shape: {
      history: !!history,
      live: !!captions,
      liveBox: !!document.getElementById('captions-body'),
      liveList: !!document.getElementById('caption-list'),
      // LIVE comes FIRST and the transcript drawer follows it (the live box is
      // the product and takes the space; see `panel.html`'s own comment on the
      // section order). This arm used to assert the OPPOSITE — `historyAboveLive`
      // — and the panel reorder of 2026-10-07 (F2/D1: a transcript that cannot
      // fill is collapsed UNDER the captions) would have made a stale arm RED
      // for the right change. `captions` precedes `history`, so history FOLLOWS.
      liveAboveHistory: !!(history && captions &&
        (captions.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING)),
    },
    buttons: {
      search: !!document.getElementById('search-button'),
      searchInput: !!document.getElementById('search-input'),
      reveal: !!document.getElementById('reveal-button'),
      revealLabel: txt(document.getElementById('reveal-button')).trim(),
    },
    historyApi: !!(window.sotto && window.sotto.history &&
      typeof window.sotto.history.tail === 'function' &&
      typeof window.sotto.history.search === 'function' &&
      typeof window.sotto.history.reveal === 'function'),
  };
  return out;
})()
