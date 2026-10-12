'use strict';
/**
 * Sotto -- letter-swap-oracle.js
 *
 * The gate for app/panel/letter-swap.js. It runs the REAL module (no stub, no mirror) and
 * holds BOTH colours: the control must be GREEN and every mutant must go RED.
 *
 *   node _main/letter-swap-oracle.js            control GREEN, all arms
 *   node _main/letter-swap-oracle.js --neg-arm  + 4 mutants on COPIES, each RED-as-required
 *
 * WHAT IT MEASURES (the brief's fixed pairs, verbatim intent):
 *   "bom dia" -> "bom dia!"            = 1   (one letter inserted)
 *   "gato"    -> "pato"               = 1   (one letter replaced)
 *   "bom dia" -> "bom dia"            = 0   (identical: nothing animates)
 *   "o rato roeu" -> "o rato comeu"   = 2   (the shared 'o' does NOT animate)
 *   "vou falar" -> "eu vou falar"     = 3   (a word inserted)
 *   "bom dia" -> "boa noite"          = 5   (a whole phrase swapped: 3 replaced + 2 inserted)
 *
 * WHAT IT DOES NOT MEASURE: what the real WebView2 paints. jsdom proves the DOM contract
 * (which nodes exist, which are spans, which are text), not the pixels. No shell, no worker,
 * no app is launched by this file.
 */
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const req = createRequire('H:/sotto/_main/x.js');
const { JSDOM } = req('jsdom');

const PANEL = 'H:/sotto/app/panel/letter-swap.js';
const SRC = fs.readFileSync(PANEL, 'utf8');

let failures = 0;
let checks = 0;
function ok(name, cond, detail) {
  checks += 1;
  if (cond) console.log('PASS ' + name);
  else { failures += 1; console.log('FAIL ' + name + (detail === undefined ? '' : '  ' + detail)); }
}
function eq(name, got, want) {
  ok(name, JSON.stringify(got) === JSON.stringify(want),
    'got=' + JSON.stringify(got) + ' want=' + JSON.stringify(want));
}
function pad(s, n) { s = String(s); while (s.length < n) s += ' '; return s; }

/* ---------------- variant loader: the real source, in a fresh context ---------------- */
function loadVariant(source, window) {
  const sandbox = { module: { exports: {} }, console: console, setTimeout: setTimeout, clearTimeout: clearTimeout };
  if (window) sandbox.window = window;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: 'letter-swap.js' });
  return sandbox.module.exports;
}
function newDom(reduced) {
  const dom = new JSDOM('<!doctype html><html><head></head><body><div id="t"></div></body></html>');
  if (reduced) dom.window.matchMedia = function (q) { return { matches: /reduce/.test(q), media: String(q) }; };
  return dom;
}

/* ---------------- the brief's fixed pairs ---------------- */
const PAIRS = [
  ['bom dia', 'bom dia!', 1],
  ['gato', 'pato', 1],
  ['bom dia', 'bom dia', 0],
  ['o rato roeu', 'o rato comeu', 2],
  ['vou falar', 'eu vou falar', 3],
  ['bom dia', 'boa noite', 5],
  ['o gato viu o rato', 'o gato viu o gato', 1],
  ['o gato', 'o cão', 2]
];

const bytes = Buffer.byteLength(SRC, 'utf8');
const crlf = (SRC.match(/\r\n/g) || []).length;
const bareLf = (SRC.replace(/\r\n/g, '').match(/\n/g) || []).length;
const sha = crypto.createHash('sha256').update(SRC).digest('hex').toUpperCase();
console.log('--- letter-swap-oracle: impl=' + PANEL);
console.log('    bytes=' + bytes + '  CRLF=' + crlf + '  bareLF=' + bareLf + '  sha256=' + sha);
console.log('    lines=' + SRC.split('\n').length);
console.log('');

const LS = loadVariant(SRC, null);

/* ================= CONTROL ================= */
console.log('--- control: the real module ---');

for (const p of PAIRS) {
  eq('C1 fixed pair ' + JSON.stringify(p[0]) + ' -> ' + JSON.stringify(p[1]),
    LS.changedNew(p[0], p[1]).length, p[2]);
}
for (const p of PAIRS) {
  const d = LS.diff(p[0], p[1]);
  eq('C2 segments join to newText ' + JSON.stringify(p[0]) + ' -> ' + JSON.stringify(p[1]),
    d.segments.map(function (s) { return s.text; }).join(''), p[1]);
}
eq('C3a producerSwap redux/nemotron', LS.producerSwap({ producer: 'redux', prevProducer: 'nemotron' }), true);
eq('C3b producerSwap same producer', LS.producerSwap({ producer: 'redux', prevProducer: 'redux' }), false);
eq('C3c producerSwap missing prevProducer', LS.producerSwap({ producer: 'redux' }), false);
eq('C3d producerSwap missing both', LS.producerSwap({}), false);
eq('C3e producerSwap empty strings', LS.producerSwap({ producer: '', prevProducer: 'redux' }), false);
eq('C3f producerSwap whitespace-trimmed equal', LS.producerSwap({ producer: 'redux', prevProducer: ' redux ' }), false);

/* C4: a producer swap animates ONLY the changed letters */
const dom4 = newDom(false);
const el4 = dom4.window.document.getElementById('t');
const r4 = LS.apply(el4, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
eq('C4a animated == 1', r4.animated, 1);
eq('C4b changed == 1', r4.changed, 1);
eq('C4c text swapped', el4.textContent, 'bom dia!');
eq('C4d childNodes == 2', el4.childNodes.length, 2);
eq('C4e node0 is a text node', el4.childNodes[0].nodeType, 3);
eq('C4f node0 is the unchanged prefix', el4.childNodes[0].data, 'bom dia');
eq('C4g node1 is an element', el4.childNodes[1].nodeType, 1);
eq('C4h node1 carries the letter span class', el4.childNodes[1].className, 'letter-swap__ch--new');
eq('C4i node1 is the changed letter', el4.childNodes[1].textContent, '!');
eq('C4j data-swap-changed', el4.getAttribute('data-swap-changed'), '1');
eq('C4k data-swap-animated', el4.getAttribute('data-swap-animated'), '1');
eq('C4l root class set', el4.classList.contains('letter-swap--swapped'), true);
eq('C4m style element injected', dom4.window.document.getElementById('sotto-letter-swap-styles') !== null, true);

/* C5: the SAME producer swaps silently */
const dom5 = newDom(false);
const el5 = dom5.window.document.getElementById('t');
const r5 = LS.apply(el5, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'redux' });
eq('C5a animated == 0', r5.animated, 0);
eq('C5b text swapped', el5.textContent, 'bom dia!');
eq('C5c no spans painted', el5.querySelectorAll('span').length, 0);
eq('C5d one text node', el5.childNodes.length, 1);

/* C6: no producer named -> silent */
const dom6 = newDom(false);
const el6 = dom6.window.document.getElementById('t');
const r6 = LS.apply(el6, 'bom dia', 'bom dia!', {});
eq('C6a animated == 0', r6.animated, 0);
eq('C6b text swapped', el6.textContent, 'bom dia!');
eq('C6c no spans painted', el6.querySelectorAll('span').length, 0);

/* C7: prefers-reduced-motion -> silent */
const dom7 = newDom(true);
const el7 = dom7.window.document.getElementById('t');
const r7 = LS.apply(el7, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
eq('C7a animated == 0', r7.animated, 0);
eq('C7b text swapped', el7.textContent, 'bom dia!');
eq('C7c no spans painted', el7.querySelectorAll('span').length, 0);

/* C8: a foreign child (a search <mark>) -> silent, text still swapped, mark kept */
const dom8 = newDom(false);
const el8 = dom8.window.document.getElementById('t');
el8.textContent = 'bom dia';
const textNode8 = el8.firstChild;
const mark8 = dom8.window.document.createElement('mark');
mark8.textContent = 'XYZ';
el8.appendChild(mark8);
const r8 = LS.apply(el8, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
eq('C8a animated == 0', r8.animated, 0);
eq('C8b skipped == true', r8.skipped, true);
eq('C8c textUnchanged == true', r8.textUnchanged, true);
eq('C8d the text node is the SAME node', el8.firstChild === textNode8, true);
eq('C8e the text content is untouched', el8.textContent, 'bom diaXYZ');
eq('C8f the foreign mark survived', el8.querySelector('mark') !== null, true);

/* C9: identical text -> NO DOM write at all */
const dom9 = newDom(false);
const el9 = dom9.window.document.getElementById('t');
el9.textContent = 'bom dia';
const kidsBefore = el9.childNodes.length;
const r9 = LS.apply(el9, 'bom dia', 'bom dia', { producer: 'redux', prevProducer: 'nemotron' });
eq('C9a unchanged flag', r9.unchanged, true);
eq('C9b childNodes untouched', el9.childNodes.length, kidsBefore);
eq('C9c text untouched', el9.textContent, 'bom dia');

/* C10: finish() unwraps the spans back to plain text */
const unwrapped = LS.finish(el4);
eq('C10a one span unwrapped', unwrapped, 1);
eq('C10b one text node left', el4.childNodes.length, 1);
eq('C10c text is the new line', el4.textContent, 'bom dia!');
eq('C10d root class removed', el4.classList.contains('letter-swap--swapped'), false);

/* C11: the animation ceiling is honoured */
const dom11 = newDom(false);
const el11 = dom11.window.document.getElementById('t');
const r11 = LS.apply(el11, 'bom dia', 'boa noite', { producer: 'redux', prevProducer: 'nemotron', maxAnimated: 2 });
eq('C11a animated capped at 2', r11.animated, 2);
eq('C11b changed still 5', r11.changed, 5);
eq('C11c text swapped', el11.textContent, 'boa noite');

/* C12: the per-element memory makes the panel's call site one line */
const dom12 = newDom(false);
const el12 = dom12.window.document.getElementById('t');
LS.apply(el12, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
LS.finish(el12);
// an INSERTION with no explicit prevProducer must still animate: the element remembers 'redux'
const r12 = LS.apply(el12, 'bom dia!', 'bom dia.', { producer: 'nemotron' });
eq('C12a insertion animates via the remembered producer', r12.animated, 1);
eq('C12b text swapped', el12.textContent, 'bom dia.');
// a DELETION animates nothing (there is no letter to paint) -- the memory is not involved
const dom12c = newDom(false);
const el12c = dom12c.window.document.getElementById('t');
LS.apply(el12c, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
LS.finish(el12c);
const r12del = LS.apply(el12c, 'bom dia!', 'bom dia', { producer: 'nemotron' });
eq('C12c a deletion animates nothing', r12del.animated, 0);
eq('C12d text swapped back', el12c.textContent, 'bom dia');
// the same pair with the producer spelled out behaves identically (the memory is not a second gate)
const dom12b = newDom(false);
const el12b = dom12b.window.document.getElementById('t');
const r12b = LS.apply(el12b, 'bom dia!', 'bom dia.', { producer: 'nemotron', prevProducer: 'redux' });
eq('C12e explicit prevProducer agrees with the memory', r12b.animated, 1);

/* C13: the injected CSS touches no layout property */
const css = dom4.window.document.getElementById('sotto-letter-swap-styles').textContent;
ok('C13a declares opacity', /opacity/.test(css));
ok('C13b declares transform', /transform/.test(css));
ok('C13c declares no width', !/[^-]width/.test(css));
ok('C13d declares no margin', !/margin/.test(css));
ok('C13e declares no font-size', !/font-size/.test(css));
ok('C13f declares no position', !/position/.test(css));
ok('C13g honours prefers-reduced-motion', /prefers-reduced-motion/.test(css));

/* C14: the degraded path reports itself and still joins */
const d14 = LS.diff('a'.repeat(900), 'b'.repeat(900));
eq('C14a degraded flagged', d14.degraded, true);
eq('C14b join holds', d14.segments.map(function (s) { return s.text; }).join(''), 'b'.repeat(900));
eq('C14c every letter changed', d14.changedNew.length, 900);

/* C15: the shared-letter case paints 5 nodes, the shared 'o' as plain text */
const dom15 = newDom(false);
const el15 = dom15.window.document.getElementById('t');
const r15 = LS.apply(el15, 'o rato roeu', 'o rato comeu', { producer: 'redux', prevProducer: 'nemotron' });
eq('C15a animated == 2', r15.animated, 2);
eq('C15b childNodes == 5', el15.childNodes.length, 5);
eq('C15c node0 unchanged prefix', el15.childNodes[0].data, 'o rato ');
eq('C15d node1 changed span', el15.childNodes[1].className + '|' + el15.childNodes[1].textContent, 'letter-swap__ch--new|c');
eq('C15e node2 the shared o, plain text', el15.childNodes[2].nodeType + '|' + el15.childNodes[2].data, '3|o');
eq('C15f node3 changed span', el15.childNodes[3].className + '|' + el15.childNodes[3].textContent, 'letter-swap__ch--new|m');
eq('C15g node4 unchanged suffix', el15.childNodes[4].data, 'eu');

/* C16: the style element is injected once, not per swap */
const dom16 = newDom(false);
const el16 = dom16.window.document.getElementById('t');
LS.apply(el16, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'nemotron' });
LS.finish(el16);
LS.apply(el16, 'bom dia!', 'bom dia', { producer: 'redux', prevProducer: 'nemotron' });
eq('C16 exactly one style element', dom16.window.document.querySelectorAll('style#sotto-letter-swap-styles').length, 1);

console.log('');
console.log('CONTROL: ' + (checks - failures) + '/' + checks + ' checks passed' + (failures ? '  -- RED' : '  -- GREEN'));

/* ================= NEG-ARM ================= */
if (process.argv.indexOf('--neg-arm') !== -1) {
  console.log('');
  console.log('--- neg-arm: mutants on COPIES of the source; each must go RED ---');

  function pairArm(a, b, want) {
    return function (MLS) {
      const got = MLS.changedNew(a, b).length;
      return got === want ? 'stays GREEN (got ' + got + ', want ' + want + ')' : 'RED (got ' + got + ', want ' + want + ')';
    };
  }
  function domAnimatedArm(a, b, want) {
    return function (MLS) {
      const d = newDom(false);
      const e = d.window.document.getElementById('t');
      const r = MLS.apply(e, a, b, { producer: 'redux', prevProducer: 'nemotron' });
      return r.animated === want ? 'stays GREEN (animated ' + r.animated + ')' : 'RED (animated ' + r.animated + ', want ' + want + ')';
    };
  }
  function sameProducerArm() {
    return function (MLS) {
      const d = newDom(false);
      const e = d.window.document.getElementById('t');
      const r = MLS.apply(e, 'bom dia', 'bom dia!', { producer: 'redux', prevProducer: 'redux' });
      return r.animated === 0 ? 'stays GREEN (animated 0)' : 'RED (animated ' + r.animated + ', want 0)';
    };
  }
  function joinArm(a, b) {
    return function (MLS) {
      const d = MLS.diff(a, b);
      const joined = d.segments.map(function (s) { return s.text; }).join('');
      return joined === b ? 'stays GREEN (join ok)' : 'RED (join ' + JSON.stringify(joined) + ')';
    };
  }

  const MUTANTS = [
    { id: 'M1', name: 'animate EVERY letter (the brief\'s mutant)',
      find: '      if (seg.same) { frag.appendChild(doc.createTextNode(seg.text)); continue; }',
      replace: '      if (false) { frag.appendChild(doc.createTextNode(seg.text)); continue; }',
      arms: [domAnimatedArm('bom dia', 'bom dia!', 1)] },
    { id: 'M2', name: 'the 0-op split removed (unchanged letters inside a run are reordered)',
      find: '          if (inRun) { flushRun(); segments.push({ same: true, text: ops[i][1] }); inRun = true; }\r\n          else sameBuf += ops[i][1];',
      replace: '          // (0-op split removed by the mutant)\r\n          sameBuf += ops[i][1];',
      arms: [joinArm('o rato roeu', 'o rato comeu')] },
    { id: 'M3', name: 'the producer gate removed (everything is a swap)',
      find: 'var isSwap = producerSwap({ producer: producer, prevProducer: prevProducer });',
      replace: 'var isSwap = true;',
      arms: [sameProducerArm()] },
    { id: 'M4', name: 'the common-prefix segment dropped (the row loses its first words)',
      find: '      if (p > 0) segments.push({ same: true, text: newS.slice(0, p) });',
      replace: '      // (prefix segment removed by the mutant)',
      arms: [joinArm('o rato roeu', 'o rato comeu'), joinArm('bom dia', 'bom dia!')] }
  ];

  let mutantFailures = 0;
  for (const m of MUTANTS) {
    const hits = SRC.split(m.find).length - 1;
    ok(m.id + ' replacement hits exactly once', hits === 1, 'hits=' + hits);
    if (hits !== 1) { mutantFailures += 1; continue; }
    const mutantSrc = SRC.replace(m.find, m.replace);
    const MLS = loadVariant(mutantSrc, null);
    for (const arm of m.arms) {
      const verdict = arm(MLS);
      const red = /^RED/.test(verdict);
      ok(m.id + ' ' + m.name + ' -> ' + verdict, red);
      if (!red) mutantFailures += 1;
    }
  }

  /* the control must still be GREEN under the same arms */
  let controlRed = 0;
  for (const p of PAIRS) {
    if (LS.changedNew(p[0], p[1]).length !== p[2]) controlRed += 1;
  }
  ok('control stays GREEN on every fixed pair', controlRed === 0, 'red=' + controlRed);

  console.log('');
  console.log('NEG-ARM: ' + (MUTANTS.length - mutantFailures) + '/' + MUTANTS.length + ' mutant(s) RED-as-required'
    + (mutantFailures ? '  -- RED' : '  -- PASS') + '; control GREEN=' + (controlRed === 0));
  failures += mutantFailures + controlRed;
}

console.log('');
console.log('SUMMARY: ' + (checks - failures) + '/' + checks + ' check(s) passed; failed=' + failures);
console.log(failures === 0 ? 'VERDICT: PASS' : 'VERDICT: FAIL');
process.exit(failures === 0 ? 0 : 1);
