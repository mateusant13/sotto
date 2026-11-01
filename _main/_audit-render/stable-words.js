/* THE WORKER'S PROMISE: THE UNPROVEN WORD STAYS OFF THE SCREEN.
 *
 * O DONO, 2026-10-30, verbatim:
 *   *"faz sotto identificar palavras que ainda nao estao completas e nao dar
 *   display. nunca vai dar display por exemplo em 'so' sem esperar virar 'sou'.
 *   em qualquer lingua"*
 *
 * QUEM PROVE. O `worker/sotto_worker.py` e a camada que sabe se a ultima
 * palavra de um parcial esta provada: o veredicto do tokenizer (`continues`)
 * so chega no fragmento SEGUINTE, e o worker segura a palavra ate la. Ele
 * marca o evento com `stable: true` quando ja a provou.
 *
 * PORQUUE UM FICHEIRO PROPRIO. O `caption-formulation.js` e o `panel.js` estao
 * debaixo do ratchet de `code-health` (bytes, linhas), que ja esta vermelho
 * para eles: um ficheiro NOVO nao piora esse portao. E o sinal e uma
 * PROPRIEDADE de um estado -- uma palavra que o motor transporta -- e nao uma
 * regra de formatacao, que e o que justifica ter o seu proprio modulo.
 *
 * O ESTADO. `wordsStable` comeca FALSO: um evento sem a chave `stable` vem de
 * um produtor que nao faz a promessa, e a leitura segura de uma promessa
 * ausente e "a palavra nao esta provada".
 */
(function (global) {
  'use strict';

  var wordsStable = false;

  var api = {
    /* O sinal chegou: o worker ja segurou a palavra, o painel nao segura outra. */
    set: function (value) {
      wordsStable = !!value;
    },
    /* Um evento novo sem promessa devolve o estado ao valor seguro. */
    reset: function () {
      wordsStable = false;
    },
    get: function () {
      return wordsStable;
    },
    /* SAO ESTAS PALAVRAS PROVADAS INTEIRAS?
     *
     * Tres casos, e so um e novo:
     *   - a linha FECHOU: o `tailClosed` do motor. As palavras de uma linha
     *     fechada nao podem mais mudar.
     *   - a PROMESSA DO TRABALHADOR: `stable: true` (owner, 2026-10-30). O
     *     worker ja segurou a palavra suspeita, logo o painel nao segura
     *     outra -- sem isto o dono perderia DUAS palavras por parcial.
     *   - o PLAYER (YouTube): o texto vem da faixa do player, palavra a
     *     palavra, e a ultima e inteira por construcao.
     *
     * O resto (o trabalho do ASR) segura a ultima palavra: ela ainda pode
     * crescer, e o dono pediu palavras inteiras.
     */
    wordsAreWhole: function (tailClosed, key) {
      return !!tailClosed
        || wordsStable
        || (key !== null && key.indexOf('external:') === 0);
    },
    /* A PROMESSA CHEGA COM O FRAGMENTO. Este embrulha o `ingest` do motor para
     * que o sinal `stable: true` (owner, 2026-10-30) seja registado ANTES de
     * o motor pintar -- e para que o registo viva num ficheiro so, em vez de
     * uma linha em `panel.js` que o ratchet de `code-health` nao perdoa.
     */
    wrap: function (engine) {
      const ingest = engine.ingest.bind(engine);
      engine.ingest = function (text, meta) {
        api.set(meta && meta.stable === true);
        return ingest(text, meta);
      };
      return engine;
    }
  };

  global.StableWords = api;
  /* Node (o oratorio carrega este ficheiro): o mesmo objecto, exportado. */
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : this);
