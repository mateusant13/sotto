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
function drive(engineMod, seq, close) {
  const partial = [];
  const commits = [];
  const metas = [];
  const engine = engineMod.createEngine({
    source: 'proc:4242',
    // O CONTRATO E' STRING (unico call site: `onCommit(line, reason, meta)` com
    // `line` de `formulateTokens`, e o `panel.js` le `(text, reason, meta)`) --
    // medido 2026-11-09: a versao anterior deste driver fazia `c.map(...)` e
    // NUNCA commitava nada (os bracos A-D liam so' os provisorios, por isso
    // passavam com `commits` vazio). Um payload inesperado agora aparece no
    // proprio nome do braco em vez de virar uma lista vazia silenciosa.
    onCommit: (c, reason, meta) => {
      commits.push(typeof c === 'string' ? c : '<NAO-STRING:' + typeof c + '>');
      metas.push(meta || {});
    },
    onProvisional: (c, p) => partial.push([...c, ...p].map((x) => x.w).join(' ')),
    now: () => 0,
  });
  for (const [text, meta] of seq) engine.ingest(text, meta || {});
  // FECHAR A LINHA: sem isto um fragmento unico nunca COMMITA (o buffer espera a
  // proxima frase, o prazo ou o voto do worker). `flush` e' o fecho do painel;
  // `hold-timeout` e' o prazo que produz `provisional-draft`.
  if (close === 'flush' && typeof engine.flush === 'function') engine.flush('flush');
  if (close === 'hold-timeout' && typeof engine.expireHold === 'function') engine.expireHold();
  return { last: partial[partial.length - 1], partial, commits, metas };
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

  // E/F/G -- O QUE O FICHEIRO LEVA, na rota que e' ESCRITA (revisao 2026-11-09).
  // As duas lojas RECUSAM `provisional-draft` (`history_append` responde
  // `HISTORY_REFUSED reason=provisional-draft`), logo um `fileText` carimbado so'
  // nessa rota e' um campo que nunca chega ao disco -- foi assim que a cura M8
  // ficou INERTE. O braco E fecha a fala com voto do worker (`final:true`) e SEM
  // marca final (o caso em que `formulateTokens` INVENTA o ponto) e exige as duas
  // metades: o display continua com a marca, o ficheiro fica sem ela.
  const e = drive(engineMod, [['acabou a fala sem ponto', { final: true }]], 'flush');
  const eMeta = e.metas[e.metas.length - 1] || {};
  const eDisplay = String(e.commits[e.commits.length - 1] || '');
  add('E rota final sem marca: o ficheiro leva o texto CRU e o display a marca',
    eMeta.route === 'final' && eMeta.fileText === 'Acabou a fala sem ponto'
      && /[.!?\u2026]$/.test(eDisplay),
    JSON.stringify({ route: eMeta.route, fileText: eMeta.fileText, display: eDisplay }));

  const f = drive(engineMod, [['a fala ja tinha ponto.', { final: true }]], 'flush');
  const fMeta = f.metas[f.metas.length - 1] || {};
  add('F rota final que JA trazia a marca: nenhum fileText (byte-identico)',
    fMeta.route === 'final' && fMeta.fileText === undefined,
    JSON.stringify({ route: fMeta.route, fileText: fMeta.fileText }));

  const g = drive(engineMod, [['rascunho sem ponto', { final: false }]], 'hold-timeout');
  const gMeta = g.metas[g.metas.length - 1] || {};
  add('G rascunho: continua a carimbar o fileText (regra anterior intacta)',
    gMeta.route === 'provisional-draft' && gMeta.fileText === 'Rascunho sem ponto',
    JSON.stringify({ route: gMeta.route, fileText: gMeta.fileText }));

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
  let guardCaught = false;
  let guardGot = '';
  try {
    const res = arms(loadEngine(tmp));
    const a = res.find((r) => r.name.startsWith('A '));
    caught = !a.ok;
    got = a.got;
    // O SEGUNDO MUTANTE -- a GUARDA DE ROTA que a revisao de 2026-11-09 derrubou.
    // O braco E tem de cair: sem isso este oraculo julga o motor e nao a rota que
    // a LOJA escreve, que foi o buraco que deixou a cura inerte em producao.
    // A ANCORA E' O BLOCO DO `fileText`, nao o `BLOCK` do cumulative: o `BLOCK`
    // vive dentro de `ingest`, onde `route` nem existe (medido: o mutante
    // anterior morreu em `ReferenceError: route is not defined`, que e' um
    // SETUP ERROR e nao uma mutacao).
    const FE_BLOCK = "      {\n        const tail = String((all[all.length - 1] || {}).w || '');";
    const FE_MUT = "      if (route !== 'final') {\n        const tail = String((all[all.length - 1] || {}).w || '');";
    const tmp2 = path.join(HERE, '_route-guard-mutant-engine.js');
    if (!src.includes(FE_BLOCK)) {
      guardGot = 'ANCORA DO FILETEXT AUSENTE -- o braco nao pode julgar';
    } else {
      fs.writeFileSync(tmp2, src.replace(FE_BLOCK, FE_MUT), 'utf8');
      try {
        const gg = arms(loadEngine(tmp2));
        const ee = gg.find((r) => r.name.startsWith('E '));
        guardCaught = Boolean(ee) && !ee.ok;
        guardGot = ee ? ee.got : 'arm E ausente';
      } finally {
        try { fs.unlinkSync(tmp2); } catch (e2) { /* ja apagado */ }
      }
    }
  } finally {
    try { fs.unlinkSync(tmp); } catch (e) { /* ja' apagado */ }
  }
  console.log(`NEG-ARM mutant caught=${caught} A=${JSON.stringify(got)}`);
  console.log(`NEG-ARM guarda-de-rota caught=${guardCaught} E=${JSON.stringify(guardGot)}`);
  console.log(caught && guardCaught ? 'NEG-ARM: PASS' : 'NEG-ARM FAIL');
  // CONTRATO DA BATERIA: rc=1 = o mutante foi apanhado (o `:expectred` recusa
  // rc=0 com "the control did NOT go red"). Medido 2026-11-03: este braco saiu 0
  // na bateria com `NEG-ARM: PASS` escrito -- o oraculo dizia uma coisa e o codigo
  // de saida outra, e a bateria le' o codigo.
  return (caught && guardCaught) ? 1 : 0;
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
