(function () {
  'use strict';
  var THEME = '%(theme)s';
  var SURFACE = '%(surface)s';
  function settledLi(text, cls, time) {
    var li = document.createElement('li');
    li.className = cls;
    var t = document.createElement('span'); t.className = 'caption__time'; t.textContent = time;
    var b = document.createElement('span'); b.className = 'caption__text'; b.textContent = text;
    li.appendChild(t); li.appendChild(b);
    return li;
  }
  function go() {
    try { if (window.SottoTheme) { window.SottoTheme.set(THEME, { persist: false }); } } catch (e) {}
    try { document.documentElement.dataset.theme = THEME; } catch (e) {}
    try { document.body.dataset.surface = SURFACE; } catch (e) {}
    var list = document.getElementById('caption-list');
    if (list) {
      list.appendChild(settledLi('O som chega antes da imagem.', 'caption', '10:23:58'));
      list.appendChild(settledLi('Quando a frase fecha, ela ganha peso - e fica.', 'caption caption--latest', '10:24:04'));
      var forming = document.createElement('li');
      forming.className = 'caption caption--provisional';
      var t1 = document.createElement('span'); t1.className = 'caption__time'; t1.textContent = '10:24:01';
      var body1 = document.createElement('span'); body1.className = 'caption__text';
      var conf = document.createElement('span'); conf.className = 'caption__confirmed'; conf.textContent = 'A legenda nasce enquanto a frase';
      var prov = document.createElement('span'); prov.className = 'caption__provisional'; prov.textContent = ' ainda esta em formacao -';
      body1.appendChild(conf); body1.appendChild(prov);
      forming.appendChild(t1); forming.appendChild(body1);
      list.appendChild(forming);
      list.hidden = false;
      var ph = document.getElementById('placeholder'); if (ph) ph.hidden = true;
      var rail = document.getElementById('captions-body'); if (rail) rail.scrollTop = rail.scrollHeight;
    }
    var out = {
      inner: { w: window.innerWidth, h: window.innerHeight },
      dpr: window.devicePixelRatio,
      theme: document.documentElement.dataset.theme,
      surface: document.body.dataset.surface,
      els: []
    };
    var all = document.querySelectorAll('body *');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var tag = el.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'LINK' || tag === 'SVG' || tag === 'PATH') continue;
      var cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      var r = el.getBoundingClientRect();
      if (r.width < 0.5 && r.height < 0.5) continue;
      var txt = '';
      for (var j = 0; j < el.childNodes.length; j++) {
        if (el.childNodes[j].nodeType === 3) txt += el.childNodes[j].nodeValue;
      }
      txt = txt.replace(/\s+/g, ' ').trim();
      if (!txt && !el.id && !(el.className && el.className.toString().trim())) continue;
      if (!txt && cs.backgroundColor === 'rgba(0, 0, 0, 0)' && parseFloat(cs.borderTopWidth) === 0 && cs.backgroundImage === 'none') continue;
      out.els.push({
        tag: tag, id: el.id || '', cls: (el.className || '').toString().slice(0, 70),
        x: Math.round(r.x * 10) / 10, y: Math.round(r.y * 10) / 10,
        w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
        fs: cs.fontSize, fw: cs.fontWeight, color: cs.color,
        bg: cs.backgroundColor, bw: cs.borderTopWidth, pos: cs.position,
        txt: txt.slice(0, 48)
      });
    }
    var pre = document.createElement('pre');
    pre.id = 'rects-out';
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', function () { setTimeout(go, 300); }); }
  else { setTimeout(go, 300); }
})();
