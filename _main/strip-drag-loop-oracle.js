#!/usr/bin/env node
/* ARRASTO: O LACO, PROVADO POR MODELO. Onda 18, 2026-10-15.
 *
 * O defeito medido no log do dono: STRIP_DRAG correu 1 498 vezes e a janela saltava entre
 * dois pontos (to=(801,804) e to=(795,812)) com o base fixo. A correcao trocou
 * `event.clientX` por `event.screenX`. Isto prova que a troca E a correcao, sem precisar
 * de um rato fisico:
 *
 *   clientX e relativo ao VIEWPORT DA JANELA. O shell move a JANELA. Mover a janela muda o
 *   `clientX` do ponteiro parado, portanto o delta que a pagina calcula deixa de medir o
 *   que o DONO mexeu -- e a janela alcanca um ponto fixo onde deixa de seguir o rato.
 *
 * O modelo: o ponteiro anda 10 px por passo no ECRA; a janela e movida para o offset que a
 * pagina pede. Mede-se o DESLOCAMENTO TOTAL da janela contra o do ponteiro. */

function run(useScreen, steps, stepPx) {
  let winX = 0;            // onde a janela esta
  const startOx = 0;       // o offset guardado QUANDO O ARRASTO COMECOU
  const pointerStart = 0;
  // o que a pagina grava no `pointerdown`
  const startPx = useScreen ? pointerStart : pointerStart - winX;
  const trace = [];
  for (let i = 1; i <= steps; i++) {
    const pointer = pointerStart + i * stepPx;              // posicao NO ECRA
    const eventPx = useScreen ? pointer : pointer - winX;    // clientX = ecra - janela
    const dx = eventPx - startPx;
    // O CODIGO REAL: `live = start.ox + dx` -- FRESCO a cada passo, nunca acumulado.
    // Era aqui que o meu primeiro modelo estava errado, e a diferenca decide tudo.
    const live = startOx + dx;
    winX = live;                                             // o shell move a janela
    trace.push(winX);
  }
  return { winX, pointer: pointerStart + steps * stepPx, trace };
}

const STEPS = 20, STEP = 10;
const want = STEPS * STEP;   // 200 px: o que o dono mexeu

const client = run(false, STEPS, STEP);
const screen = run(true, STEPS, STEP);

console.log("ARRASTO -- MODELO DO LACO (" + STEPS + " passos de " + STEP + " px)");
console.log("  ponteiro andou ................ " + want + " px");
console.log("  clientX -> janela andou ....... " + client.winX + " px   (" + Math.round(client.winX / want * 100) + "% do rato)");
console.log("  screenX -> janela andou ....... " + screen.winX + " px   (" + Math.round(screen.winX / want * 100) + "% do rato)");
console.log("");
console.log("  primeiros passos com clientX: " + client.trace.slice(0, 5).join(", "));
console.log("  primeiros passos com screenX: " + screen.trace.slice(0, 5).join(", "));
console.log("");

let bad = 0;
function chk(name, ok, detail) {
  if (!ok) bad += 1;
  console.log("  " + (ok ? "ok  " : "FAIL") + "  " + name.padEnd(52) + " " + detail);
}
chk("A  screenX: a janela segue o rato ate ao fim",
    screen.winX === want, "andou " + screen.winX + " de " + want + " px");
chk("B  clientX: a janela anda METADE do que o rato andou",
    client.winX === want / 2, "andou " + client.winX + " de " + want + " px -- " + Math.round(client.winX / want * 100) + "% do rato");
chk("C  clientX: o rasto REPETE cada valor (o engasgo que ele sentiu)",
    client.trace[0] === client.trace[1] && client.trace[2] === client.trace[3],
    "rasto=" + client.trace.slice(0, 6).join(","));
chk("D  screenX: cada passo acrescenta os " + STEP + " px todos",
    screen.trace[1] - screen.trace[0] === STEP, "passo=" + (screen.trace[1] - screen.trace[0]));
chk("E  screenX: o rasto NAO repete nenhum valor",
    screen.trace.every((v, k) => k === 0 || v > screen.trace[k - 1]),
    "rasto=" + screen.trace.slice(0, 6).join(","));

console.log("");
console.log(bad === 0 ? "VERDICT: PASS -- screenX e a correcao, e clientX reproduz o defeito"
                      : "VERDICT: FAIL -- " + bad + " check(s)");
process.exit(bad === 0 ? 0 : 1);