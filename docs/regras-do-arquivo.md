# Regras para manter este ficheiro verdadeiro

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


1. **"O grep deu ZERO" é uma afirmação com prazo de validade.** Re-correr antes de repetir, e colar os
   números de HOJE.
2. **Nomear a revisão ao citar uma linha.** As lanes editam `worker/sotto_worker.py`,
   `app/webview/sotto_webview.py` e `run.cmd` em paralelo. Dar tamanho, mtime e/ou sha256; tratar toda a
   `file:line` como HINT e re-grep antes de agir.
3. **Ausência precisa de instrumento, não de impressão.** Nomear o instrumento, a cadência e a contagem.
4. **Uma screenshot prova COR, não COORDENADAS.** O Edge headless desta máquina fixa o layout viewport em
   **492 px** em `--screenshot` E `--dump-dom`. Só `sotto_webview.py --dump-dom` (WebView2 real) responde
   "onde"; o seu key `controls` imprime `viewport_w` ao lado de cada número.
5. **O EOL do repo é REGRA, não desejo.** `.gitattributes` é **GERADO** por
   `_main/_make-gitattributes.py --write` a partir do estado medido (CRLF 712 / LF 1510 / MISTO 68 numa
   amostra de 2 296 ficheiros de texto) e verificado por `_main/_gitattributes-verify.py`. **Nunca editar
   à mão: regenerar e re-verificar.**
6. **Um portão que julga FICHEIROS entra na bateria; um portão que LANÇA fica fora e di-lo-á aqui.** Um
   portão novo nasce com o braço negativo **já executado** (`NEG-ARM PASS`, rc=1 por desenho). Um braço
   negativo que não está na bateria é um mutante a que ninguém volta a olhar.
7. **Um portão VERMELHO não é veredicto sobre o produto.** Classificar primeiro: âncora gasta (higiene) vs
   afirmação vermelha (defeito). O runner da segunda bateria separa arms negativos (rc 0/1 por desenho) de
   falhas reais (rc≥2 ou crash).
8. **Uma regra fora da população do instrumento não pode ser apanhada por ele.** O `render protection` do
   painel esteve MORTO no produto com todos os portões verdes, porque (i) o harness jsdom não carregava
   `zip-overlay.css` e (ii) o censo saltava selectores que mencionassem `data-caption-window` — a regra
   errada. A cura: o documento de legenda tem marcador próprio **`data-caption-doc="1"`**. Escrever o que
   o instrumento NÃO carrega e justificar cada selector que ele escusa.
