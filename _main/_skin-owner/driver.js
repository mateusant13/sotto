(() => {
  const out = {
    title: document.title,
    url: location.href,
    hash: location.hash,
    search: location.search,
    viewport: [innerWidth, innerHeight],
    styleSheets: document.styleSheets.length,
    rootChildren: [],
    varHosts: [],
    designControls: [],
    textSamples: [],
  };

  const root = document.getElementById('root') || document.body;

  function describe(el, depth) {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      cls: (el.className && String(el.className).slice(0, 160)) || null,
      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      pos: cs.position,
      bg: cs.backgroundColor,
      font: cs.fontFamily.slice(0, 60),
      kids: el.children.length,
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 90),
    };
  }

  for (const child of Array.from(root.children)) out.rootChildren.push(describe(child, 0));

  // Who carries the CSS variables?
  const all = root.querySelectorAll('*');
  for (const el of all) {
    const inline = el.getAttribute('style') || '';
    if (inline.indexOf('--') >= 0) {
      out.varHosts.push({
        tag: el.tagName.toLowerCase(),
        id: el.id || null,
        cls: (el.className && String(el.className).slice(0, 120)) || null,
        depth: (() => { let d = 0, n = el; while (n && n !== root) { d += 1; n = n.parentElement; } return d; })(),
        vars: inline.slice(0, 1200),
      });
      if (out.varHosts.length > 12) break;
    }
  }

  // Anything that looks like a design switch.
  const clickable = root.querySelectorAll('button,[role="button"],a,input,select');
  for (const el of clickable) {
    const label = (el.getAttribute('aria-label') || el.title || el.value || el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!label) continue;
    out.designControls.push({
      tag: el.tagName.toLowerCase(),
      selector: el.id ? '#' + el.id : null,
      cls: (el.className && String(el.className).slice(0, 140)) || null,
      label: label.slice(0, 60),
      rect: (() => { const r = el.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })(),
    });
    if (out.designControls.length > 60) break;
  }

  // The biggest text on screen, which is where a caption lives.
  const texts = [];
  for (const el of all) {
    if (el.children.length) continue;
    const t = (el.textContent || '').trim();
    if (t.length < 4) continue;
    const cs = getComputedStyle(el);
    texts.push({ text: t.slice(0, 70), size: parseFloat(cs.fontSize) || 0, tag: el.tagName.toLowerCase(), cls: (el.className && String(el.className).slice(0, 80)) || null });
  }
  texts.sort((a, b) => b.size - a.size);
  out.textSamples = texts.slice(0, 25);

  return out;
})()
