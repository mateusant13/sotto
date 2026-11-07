#!/usr/bin/env node
/* QUEM PEDE UM ARRASTO, E QUEM NAO PEDE -- o painel inteiro e' a pega.

 * NASCIDO DA ORDEM DO DONO (2026-11-06, verbatim): *"usa bem as skills, pra
 * implementar o fato de ser possivel mover qualquer painel pela tela. já que
 * agora ta extremamente bugado. a tentativa ta muito falha."*
 *
 * O QUE ESTAVA MEDIDO ANTES: `app/panel/strip-drag.js` armava o arrasto nativo
 * em DOIS sitios -- o `.stripbar` e o `.panel__header`. No painel isso e' uma
 * faixa de 56 px no topo de uma janela de 900 px: qualquer desenho que de' a essa
 * faixa outra altura (ou outra composicao) encolhe a area de pega com ela, e o
 * dono le' isso como "as vezes nao move". O CORPO do painel nao era pega nenhuma.
 *
 * Agora o painel inteiro pede o arrasto, e `isControl` (a lista que o strip ja'
 * usava) mais as LINHAS do transcrito e o scroller ficam de fora. Este oraculo e'
 * o que conta os dois lados dessa fronteira: para cada alvo, quantos
 * `beginWindowDrag` saem de UM pointerdown.
 *
 * AS ARMS: alvos que PEDEM (fundo do painel, header, wordmark, roda de controles
 * vazia) e alvos que NAO PEDEM (botao, linha do historico, lista do historico,
 * input de busca, dialogo). O `--neg-arm` apaga `.hist` da lista de exclusao numa
 * COPIA e exige que a arm da LINHA caia -- a fronteira tem de ser falsificavel,
 * senao o passo so' mede a si proprio.
 *
 * Uso:
 *   node _main/panel-drag-targets-oracle.js            # positivo
 *   node _main/panel-drag-targets-oracle.js --neg-arm  # mutante tem de cair
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const { JSDOM } = require("jsdom");

const REPO = path.resolve(__dirname, "..");
const SRC = path.join(REPO, "app/panel/strip-drag.js");

/* UMA PAGINA MINIMA COM A MESMA FORMA QUE A REAL. O `strip-drag.js` procura
 * `#strip-controls`, `#panel`, `.panel__header`; o resto existe para os alvos
 * poderem ser pressionados com o seu ancestral correto. */
const PAGE = `<!doctype html><html><body>
  <div id="strip-controls"><div class="grip"></div></div>
  <div id="panel">
    <div class="panel__header">
      <span class="wordmark">sotto</span>
      <div class="panel__controls">
        <button id="b-menu">menu</button>
        <span role="button" id="b-role">tema</span>
      </div>
    </div>
    <div class="captions"><div class="captions__body" id="caption-body"></div></div>
    <div class="history">
      <div class="history__bar">
        <button id="b-search" class="history__search-btn"></button>
        <input id="search" class="history__search">
      </div>
      <div class="history__body">
        <div class="history__list">
          <div class="hist" id="row"><span class="hist__time">12:00:01</span><span class="hist__text">banana pera manga</span></div>
        </div>
      </div>
    </div>
    <div class="dialog" id="dialog"><div class="theme-dropdown" id="dropdown"></div></div>
  </div>
</body></html>`;

function load(scriptPath) {
  const dom = new JSDOM(PAGE, { runScripts: "outside-only", pretendToBeVisual: true });
  const { window } = dom;
  const calls = [];
  window.sotto = {
    beginWindowDrag(surface) { calls.push(String(surface || "")); },
    setStripOffset() {},
  };
  window.eval(fs.readFileSync(scriptPath, "utf8"));
  return { window, calls };
}

function press(ctx, selector) {
  const el = ctx.window.document.querySelector(selector);
  if (!el) throw new Error(`alvo ausente na pagina: ${selector}`);
  ctx.calls.length = 0;
  const ev = new ctx.window.PointerEvent("pointerdown", {
    bubbles: true, cancelable: true, button: 0, pointerId: 1, isPrimary: true,
  });
  el.dispatchEvent(ev);
  return ctx.calls.length;
}

/* OS DOIS LADOS DA FRONTEIRA. `want` e' quantos `beginWindowDrag` o toque deve
 * pedir; um alvo que pede 2 tambem esta errado (dois lacos nativos aninhados). */
const ARMS = [
  { name: "PEDE painel(fundo)",       sel: "#panel", want: 1 },
  { name: "PEDE header",              sel: ".panel__header",         want: 1 },
  { name: "PEDE wordmark",            sel: ".wordmark",              want: 1 },
  { name: "PEDE roda de controles",   sel: ".panel__controls",       want: 1 },
  { name: "PEDE strip",               sel: "#strip-controls .grip",  want: 1 },
  { name: "NAO botao",                sel: "#b-menu",                want: 0 },
  { name: "NAO role=button",          sel: "#b-role",                want: 0 },
  { name: "NAO linha do historico",   sel: "#row",                   want: 0 },
  { name: "NAO texto da linha",       sel: "#row .hist__text",       want: 0 },
  { name: "NAO lista do historico",   sel: ".history__list",         want: 0 },
  { name: "NAO input de busca",       sel: "#search",                want: 0 },
  { name: "NAO dropdown de tema",     sel: "#dropdown",              want: 0 },
];

function judge(cases) {
  const bad = cases.filter((c) => c.got !== c.want);
  return { bad };
}

function positive() {
  const ctx = load(SRC);
  const cases = ARMS.map((a) => ({ name: a.name, want: a.want, got: press(ctx, a.sel) }));
  const { bad } = judge(cases);
  for (const c of cases) {
    console.log(`${c.got === c.want ? "ok  " : "FAIL"} ${c.name}: drags=${c.got} want=${c.want}`);
  }
  console.log(`VERDICT: ${bad.length ? "FAIL" : "PASS"} -- ${cases.length} arms, ${bad.length} divergentes`);
  return bad.length ? 1 : 0;
}

/* O MUTANTE: apaga `.hist` E `.history__list` da lista de exclusao. Se as duas
 * arms dos ROWS continuarem a dizer 0, a fronteira nao vem dali e este oraculo
 * nao mede o que diz medir. `.captions` e o resto da lista FICAM, para o mutante
 * nao virar "desliga tudo": uma mutacao que derruba tudo estaria a medir a pagina.
 */
function negArm() {
  const src = fs.readFileSync(SRC, "utf8");
  const marker = '.hist, .history__list, .history__body, .history__search, .history__bar, ';
  if (!src.includes(marker)) {
    console.log("NEG-ARM IMPOSSIVEL: a lista de exclusao nao tem a marca esperada");
    return 2;
  }
  const mutant = src.replace(marker, '.history__nothing, ');
  if (mutant === src) {
    console.log("NEG-ARM IMPOSSIVEL: a substituicao nao mudou o ficheiro");
    return 2;
  }
  const tmp = path.join(os.tmpdir(), `strip-drag-mutant-${process.pid}.js`);
  fs.writeFileSync(tmp, mutant);
  try {
    const ctx = load(tmp);
    const row = press(ctx, "#row");
    const list = press(ctx, ".history__list");
    const bg = press(ctx, "#panel");
    const caught = row === 1 && list === 1 && bg === 1;
    console.log(`mutante: linha=${row} (esperado 1) lista=${list} (esperado 1) fundo=${bg} (esperado 1)`);
    console.log(`NEG-ARM: ${caught ? "PASS" : "FAIL"} -- o mutante que apaga a exclusao dos rows ${caught ? "foi apanhado" : "NAO foi apanhado"}`);
    return caught ? 1 : 0;
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) { /* um temporario que fica nao muda o veredito */ }
  }
}

if (process.argv.includes("--neg-arm")) {
  process.exit(negArm());
}
process.exit(positive());
