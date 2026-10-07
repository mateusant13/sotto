// throwaway: apply the remaining async rewrites to the probe
const fs = require('fs');
const p = '_main/_panel2-dom-probe.js';
let s = fs.readFileSync(p, 'utf8');

// An async IIFE used as an arm value must be awaited.
s = s.split('\n').reduce((out, line, i, all) => {
  const trimmed = line.trim();
  if (trimmed.startsWith('((async () => {')) {
    out.push(line.replace('((async () => {', 'await (async () => {'));
    return out;
  }
  if (/^\s*\}\)\(\),?\s*(.*)$/.test(line) && out.length && out.some((l) => l.includes('await (async () => {'))) {
    // `})(), 'x');` — leave as is; awaiting is what matters, the call shape is fine
    return out.concat([line]);
  }
  return out.concat([line]);
}, []).join('\n');

// `})(), 'want')` after an awaited IIFE is fine: `await (async()=>{...})(), 'want'`
// — but a bare comma makes the arm receive the comma expression. Normalise the
// three sites by hand below instead.
fs.writeFileSync(p, s, 'utf8');
console.log('done');
