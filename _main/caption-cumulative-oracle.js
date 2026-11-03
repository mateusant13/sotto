#!/usr/bin/env node
/*
 * CAPTION-CUMULATIVE ORACLE -- o fragmento que E' A LINHA, mesmo sem relogio.
 *
 * O DEFEITO, medido no log VIVO do dono (2026-11-03, pid 18156, 11:45). O worker
 * publica o texto ACUMULADO da linha aberta (`LineFormer._event`, contrato
 * "o fragmento e' a LINHA"). Quando o `start` chega, `caption-formulation.js`
 * detecta a re-leitura (`start < lastAudioEnd`) e substitui. Quando o `start`
 * NAO chega -- que e' o caso do caminho em que ele nao foi publicado -- o
 * fragmento era CONCATENADO:
 *
 *   worker mandou:  'ig u a galera'
 *                   'ig u a galera do a esquerda'
 *                   'ig u a galera do a esquerda tava gravando.'
 *   o dono leu:     'Ig u a galera ig u a galera do a esquerda ig u a galera do
 *                    a esquerda tava gravando.'
 *
 * Medido nas duas direccoes no motor REAL: com `meta` de tempos a linha cresce
 * limpa (ja' era assim); sem `meta` ela duplicava. A cura e' de TEXTO -- o que
 * chegou comeca com o que ja' esta' escrito, logo e' a mesma linha.
 *
 *   node _main/caption-cumulative-oracle.js             # rc=0 verde, rc=1 vermelho
 *   node _main/caption-cumulative-oracle.js --neg-arm   # rc=0 so' se o mutante cai
 *
 * NAO abre janela, nao arranca worker, nao toca em dispositivo de audio: carrega
 * o modulo do painel e empurra eventos por ele.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const ENGINE = path.join(HERE, '..', 'app', 'panel', 'caption-formulation.js');

function loadEngine(src) {
  delete require.cache[require.resolve(src)];
  return require(src);
}

/** Empurra `seq` pelo motor e devolve os provisorios e os commits. */
function drive(engineMod, seq) {
  const partial = [];
  const commits = [];
  const engine = engineMod.createEngine({
    source: 'proc:4242',
    onCommit: (c) => commits.push(c.map((x) => x.w).join(' ')),
    onProvisional: (c, p) => partial.push([...c, ...p].map((x) => x.w).join(' ')),
    now: () => 0,
  });
  for (const [text, meta] of seq) engine.ingest(text, meta || {});
  return { last: partial[partial.length - 1], partial, commits };
}

const GROWTH = [
  ['ig u a galera', {}],
  ['ig u a galera do a esquerda', {}],
  ['ig u a galera do a esquerda tava gravando.', {}],
];
const GROWTH_TIMED = [
  ['ig u a galera', { start: 12.5, end: 13.0 }],
  ['ig u a galera do a esquerda', { start: 12.5, end: 13.5 }],
  ['ig u a galera do a esquerda tava gravando.', { start: 12.5, end: 14.0 }],
];
const GROWTH_WANT = 'ig u a galera do a esquerda tava gravando.';
const NEW_SENTENCE = [
  ['primeira frase', {}],
  ['segunda frase diferente', {}],
];

function arms(engineMod) {
  const out = [];
  const add = (name, ok, got) => out.push({ name, ok, got });

  const a = drive(engineMod, GROWTH);
  add('A sem `meta`: o fragmento cumulativo SUBSTITUI (nao concatena)',
    a.last === GROWTH_WANT, a.last);

  const b = drive(engineMod, GROWTH_TIMED);
  add('B com `meta`: continua a crescer limpo (sem regressao)',
    b.last === GROWTH_WANT, b.last);

  const c = drive(engineMod, NEW_SENTENCE);
  add('C uma frase NOVA ainda e\' acrescentada (a regra nao engole fala)',
    c.last === 'primeira frase segunda frase diferente', c.last);

  const d = drive(engineMod, [['a mesma linha', {}], ['a mesma linha', {}]]);
  add('D a repeticao EXACTA continua a nao duplicar (regra anterior intacta)',
    d.last === 'a mesma linha', d.last);

  return out;
}

const OPENING_LINE = '        opening = incoming;';
const BLOCK = [
  '      if (agreedPrefixLength(emittedWords, fragWords) === emittedWords.length) {',
  '        committed = [];',
  '        provisional = [];',
  '        prevWords = [];',
  '        lastAudioEnd = null;',
  OPENING_LINE,
  '      }',
].join('\n');

function negArm() {
  // O ficheiro do painel vive em CRLF; a ancora e' escrita com `\n`, logo a
  // comparacao corre sobre uma copia normalizada (o mutante escreve-se em LF).
  const src = fs.readFileSync(ENGINE, 'utf8').replace(/\r\n/g, '\n');
  if (!src.includes(BLOCK)) {
    console.log('NEG-ARM FAIL: o bloco da cura nao esta no motor (ancora)');
    return 1;
  }
  const tmp = path.join(HERE, '_cumulative-mutant-engine.js');
  fs.writeFileSync(tmp, src.replace(BLOCK, '      /* neg-arm: sem a cura */'), 'utf8');
  let caught = false;
  let got = '';
  try {
    const res = arms(loadEngine(tmp));
    const a = res.find((r) => r.name.startsWith('A '));
    caught = !a.ok;
    got = a.got;
  } finally {
    try { fs.unlinkSync(tmp); } catch (e) { /* ja' apagado */ }
  }
  console.log(`NEG-ARM mutant caught=${caught} A=${JSON.stringify(got)}`);
  console.log(caught ? 'NEG-ARM: PASS' : 'NEG-ARM FAIL');
  // CONTRATO DA BATERIA: rc=1 = o mutante foi apanhado (o `:expectred` recusa
  // rc=0 com "the control did NOT go red"). Medido 2026-11-03: este braco saiu 0
  // na bateria com `NEG-ARM: PASS` escrito -- o oraculo dizia uma coisa e o codigo
  // de saida outra, e a bateria le' o codigo.
  return caught ? 1 : 0;
}

function main() {
  if (process.argv.includes('--neg-arm')) return negArm();
  const res = arms(loadEngine(ENGINE));
  let bad = 0;
  for (const r of res) {
    console.log(`${r.ok ? 'PASS' : 'FAIL'} ${r.name}`);
    if (!r.ok) {
      console.log(`     real = ${JSON.stringify(r.got)}`);
      bad += 1;
    }
  }
  console.log(`VERDICT: ${bad ? 'RED' : 'GREEN'} (${res.length - bad}/${res.length})`);
  return bad ? 1 : 0;
}

process.exit(main());
