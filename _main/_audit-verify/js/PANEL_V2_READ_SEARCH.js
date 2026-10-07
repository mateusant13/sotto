
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  return {
    search: {
      hits: qa('#history-list .hist').length,
      texts: qa('#history-list .hist__text').map((e) => e.textContent),
      marked: !!q('#history-list mark'),
      note: txt(document.getElementById('history-status')).trim(),
      folderButtons: qa('#history-list .hist__folder').length,
    },
  };
})()
