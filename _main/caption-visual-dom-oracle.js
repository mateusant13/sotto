'use strict';

/**
 * caption-visual-dom-oracle.js — A CAIXA DA LEGENDA MANDA a escolha.
 *
 * O QUE ELE RESPONDE, e que nenhum oraculo de FONTE responde: com o painel REAL
 * carregado (`app/panel/panel.html`, os `<script src>` dele proprios, executados
 * por ordem, e o `panel.js` que embarca), mudar "Fundo da legenda" ou
 * "Transparencia do fundo" chega a `bridge.setCaptionVisual` com o payload que o
 * shell espera: `plate` em `tight|normal` e `opacity` = 1 - transparencia/100.
 *
 * POR QUE ELE EXISTE. Dono, 2026-11-09, verbatim: *"the background in the
 * subtitles is too wide. should be more concise and less bloaty"* e, na mesma
 * rodada, a transparencia escolhivel. A maquinaria (modo `tight`, alfa so' da
 * placa, `caption_settings` com clamp e escrita atomica) ja' existia SEM UM
 * CHAMADOR -- e a classe que esta casa ja' pagou tres vezes. Um `_step` que so'
 * prova a matematica da placa deixa a caixa sem fiacao passar: por isso a
 * segunda metade do `caption-plate-oracle` (arm A8) le o fonte, e este le a
 * PAGINA. As duas metades falham por motivos diferentes.
 *
 * A ARM DO ARRANQUE E' A OUTRA METADE DA MESMA REGRA: uma sessao SEM escolha
 * guardada nao pode empurrar nada -- o shell ja' leu `caption-settings.json`
 * quando criou o overlay, e um push vazio poria a legenda no default do painel
 * por cima do ficheiro que o dono escreveu.
 *
 * O NEGATIVO (`--neg-arm`) muta o `panel.js` numa COPIA (nunca no fonte) e exige
 * que a arm NOMEADA caia. rc=1 = todos os mutantes apanhados; rc=0 = algum
 * mutante INERTE.
 *
 * ORIGEM COM STORAGE: o `file://` da' origem OPACA e o `localStorage` levanta --
 * medido aqui (a escolha guardada nunca chegava a ser lida e as duas arms do
 * arranque passavam a medir o default). O documento e' montado sobre
 * `https://sotto.local/`. Nada e' tocado no disco e nenhuma janela abre.
 *
 * Uso:
 *   node _main/caption-visual-dom-oracle.js
 *   node _main/caption-visual-dom-oracle.js --neg-arm
 */

const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const PANEL_HTML = path.resolve(__dirname, '..', 'app', 'panel', 'panel.html');
const PANEL_JS = path.resolve(__dirname, '..', 'app', 'panel', 'panel.js');

/** A pagina REAL, com o `panel.js` de disco (ou o mutado que o negativo passa). */
function boot(options) {
  const opts = options || {};
  const html = fs.readFileSync(PANEL_HTML, 'utf8');
  const dom = new JSDOM(html, {
    url: 'https://sotto.local/panel.html',
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const calls = [];
  const real = {
    setCaptionVisual: (o) => { calls.push(o); return Promise.resolve(o); },
    onStatus: () => {}, onCaption: () => {}, show: () => {}, hide: () => {},
    getStats: () => Promise.resolve({}),
    setPanelSurface: () => Promise.resolve(),
    setLiveEnabled: () => Promise.resolve({}),
    history: undefined,
  };
  // Um Proxy para o resto: o `panel.js` inteiro corre, e um metodo em falta nao
  // pode ser o motivo de a arm medir outra coisa.
  window.sotto = new Proxy(real, {
    get(target, key) {
      if (key in target) return target[key];
      return () => Promise.resolve({});
    },
  });
  for (const [key, value] of Object.entries(opts.storage || {})) {
    window.localStorage.setItem(key, value);
  }
  const errors = [];
  const sources = [];
  const re = /<script[^>]+src="([^"]+)"/g;
  let m;
  while ((m = re.exec(html))) sources.push(m[1]);
  for (const src of sources) {
    const file = path.resolve(path.dirname(PANEL_HTML), src);
    if (!fs.existsSync(file)) continue;
    let body = fs.readFileSync(file, 'utf8');
    if (opts.mutantJs && file === PANEL_JS) body = opts.mutantJs;
    try {
      window.eval(body);
    } catch (err) {
      errors.push(src + ': ' + (err && err.message));
    }
  }
  try {
    window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  } catch (err) {
    errors.push('DOMContentLoaded: ' + (err && err.message));
  }
  return { window, doc: window.document, calls, errors };
}

function alphaOf(call) {
  return call && typeof call.opacity === 'number' ? call.opacity : NaN;
}

/** As arms de uma pagina SEM escolha guardada: o arranque tem de ficar calado. */
function silentArms(page) {
  return {
    bootSilent: page.calls.length === 0,
    pageErrors: page.errors.length === 0,
  };
}

/** As arms, contra uma pagina ja' montada COM escolha guardada. */
function arms(page) {
  const doc = page.doc;
  const sel = doc.getElementById('caption-plate-select');
  const range = doc.getElementById('caption-opacity-range');
  const label = doc.getElementById('caption-opacity-value');
  const out = {};
  out.controls = Boolean(sel) && Boolean(range) && Boolean(label);
  out.pageErrors = page.errors.length === 0;

  // (1) arranque com escolha guardada: UMA chamada, com o valor guardado.
  const boot0 = page.calls.slice();
  out.bootPushCall = boot0;
  out.bootPush = boot0.length === 1 && boot0[0].plate === 'normal'
    && Math.abs(alphaOf(boot0[0]) - 0.7) < 1e-9;
  out.bootShows = Boolean(sel) && sel.value === 'normal';

  // (2) mudar a caixa: o payload novo, e o mesmo alfa.
  page.calls.length = 0;
  if (sel) {
    sel.value = 'tight';
    sel.dispatchEvent(new page.window.Event('change', { bubbles: true }));
  }
  out.changeSends = page.calls.length === 1 && page.calls[0].plate === 'tight'
    && Math.abs(alphaOf(page.calls[0]) - 0.7) < 1e-9;

  // (3) a transparencia: 70% -> alfa 0.30, e o rotulo acompanha o dedo.
  page.calls.length = 0;
  if (range) {
    range.value = '70';
    range.dispatchEvent(new page.window.Event('input', { bubbles: true }));
  }
  out.labelFollows = Boolean(label) && (label.textContent || '') === '70%';
  if (range) range.dispatchEvent(new page.window.Event('change', { bubbles: true }));
  out.opacitySends = page.calls.length === 1
    && Math.abs(alphaOf(page.calls[0]) - 0.3) < 1e-9;
  return out;
}

/* Cada mutante muda UMA ancora (que tem de existir uma vez) numa COPIA em
 * memoria -- o ficheiro do repo nunca e' reescrito. */
const MUTANTS = [
  {
    name: 'M1 a caixa muda e nada e enviado',
    anchor: "      sendCaptionLook(plate, transparency);",
    mutant: '      void 0;',
    arms: ['changeSends', 'opacitySends'],
  },
  {
    /* Medido numa pagina SEM escolha guardada: com escolha o `stored` ja' e'
     * verdadeiro e esta mutacao nao muda nada -- um mutante que nao pode falhar
     * nao e' evidencia. Foi assim que a primeira versao deste negativo deu
     * `INERTE`, e o conserto e' a arm, nao o mutante. */
    name: 'M2 o arranque empurra por cima do ficheiro',
    anchor: '    if (stored) sendCaptionLook(look.plate, look.transparency);',
    mutant: '    sendCaptionLook(look.plate, look.transparency);',
    storage: {},
    silent: true,
    arms: ['bootSilent'],
  },
  {
    name: 'M3 a transparencia invertida',
    anchor: '  const opacity = 1 - (transparency / 100);',
    mutant: '  const opacity = transparency / 100;',
    arms: ['bootPush', 'opacitySends'],
  },
];

function report(rows, title) {
  console.log(title);
  let bad = 0;
  for (const [name, ok, detail] of rows) {
    if (!ok) bad += 1;
    console.log('  ' + (ok ? 'GREEN' : 'RED  ') + ' ' + name
      + (detail ? '  ' + detail : ''));
  }
  return bad;
}

function positive() {
  const page = boot({
    storage: { 'sotto.captionPlate': 'normal', 'sotto.captionOpacity': '30' },
  });
  const result = arms(page);
  const bare = silentArms(boot({ storage: {} }));
  const rows = [
    ['os tres elementos existem', result.controls, ''],
    ['nenhum erro de pagina', result.pageErrors, page.errors.join('; ')],
    ['o select abre no valor guardado', result.bootShows, ''],
    ['arranque com escolha manda o payload', result.bootPush,
      JSON.stringify(result.bootPushCall)],
    ['arranque SEM escolha nao empurra nada', bare.bootSilent, ''],
    ['mudar a caixa manda a escolha nova', result.changeSends, ''],
    ['o rotulo segue o dedo', result.labelFollows, ''],
    ['transparencia 70% -> alfa 0.30', result.opacitySends, ''],
  ];
  const bad = report(rows, 'A CAIXA DE CONFIGURACOES, na pagina REAL:');
  console.log('');
  console.log('%d/%d GREEN', rows.length - bad, rows.length);
  return bad;
}

function negative() {
  const source = fs.readFileSync(PANEL_JS, 'utf8');
  const rows = [];
  let caught = 0;
  for (const mutant of MUTANTS) {
    const count = source.split(mutant.anchor).length - 1;
    if (count !== 1) {
      rows.push([mutant.name + ' NAO FOI CONSTRUIDO',
        false, 'a ancora ocorre ' + count + ' vez(es)']);
      continue;
    }
    const mutated = source.replace(mutant.anchor, mutant.mutant);
    // Um mutante que nao muda o texto e' um mutante que nao pode falhar.
    if (mutated === source) {
      rows.push([mutant.name + ' NAO FOI CONSTRUIDO', false, 'texto identico']);
      continue;
    }
    const page = boot({
      storage: mutant.storage !== undefined
        ? mutant.storage
        : { 'sotto.captionPlate': 'normal', 'sotto.captionOpacity': '30' },
      mutantJs: mutated,
    });
    const result = mutant.silent ? silentArms(page) : arms(page);
    const red = mutant.arms.filter((name) => !result[name]);
    const hit = red.length === mutant.arms.length;
    if (hit) caught += 1;
    rows.push([mutant.name, hit, red.length
      ? 'RED em ' + red.join(', ') : 'INERTE -- nenhuma arm nomeada caiu']);
  }
  report(rows, 'NEGATIVE ARM -- mutantes no painel, em COPIA:');
  console.log('');
  console.log('%d/%d mutantes apanhados', caught, MUTANTS.length);
  // rc=1 = apanhados (a convencao da casa: o negativo devolve 1 ao apanhar).
  return caught === MUTANTS.length ? 0 : 1;
}

const negArm = process.argv.includes('--neg-arm');
const failed = negArm ? negative() : positive();
console.log('VERDICT: ' + (failed
  ? (negArm ? 'NEG-ARM FAIL (mutante inerte)' : 'FAIL')
  : (negArm ? 'NEG-ARM PASS (mutantes apanhados)' : 'PASS')));
process.exit(negArm ? (failed ? 0 : 1) : (failed ? 1 : 0));
