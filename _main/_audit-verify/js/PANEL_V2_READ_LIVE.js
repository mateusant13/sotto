
(() => {
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  // O CAMPO SAIU (2026-10-30). A leitura continua a correr e a devolver a mesma
  // forma: `searchInputDisabled` passa a ser lido como "nao ha campo nenhum", que e'
  // o estado que o dono pediu -- e um `requestSubmit` de um formulario ausente
  // rebentava a sonda inteira (medido: `TypeError: input is null`).
  const input = document.getElementById('search-input');
  const form = document.getElementById('search-form');
  if (input && form) {
    input.value = '__STAMP__';
    form.requestSubmit();
  }
  return {
    live: {
      lines: qa('#caption-list .caption__text').map((e) => e.textContent),
      count: (document.getElementById('caption-list') || {}).childElementCount,
      placeholderHidden: !!(document.getElementById('placeholder') || {}).hidden,
      // The panel DISABLES the search input while no canonical producer exists
      // (nothing could match, and a search box that cannot work is a promise
      // with no backend). Read here so the transcript arm below can require the
      // honest state instead of inventing a hit.
      searchBoxAbsent: !document.getElementById('search-input'),
      searchInputDisabled: !!(document.getElementById('search-input') || {}).disabled,
    },
    feed: qa('#history-list .hist__text').map((e) => e.textContent),
    feedFolderButtons: qa('#history-list .hist__folder').length,
    rootLabel: txt(document.getElementById('history-root')).trim(),
    searched: true,
  };
})()
