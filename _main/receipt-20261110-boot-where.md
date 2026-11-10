# RECIBO - ONDE o arranque da pagina gasta o tempo (medido, 2026-11-10)

## 1. O instrumento

`_main/_cache/page-boot-where.mjs` (descartavel, Playwright + `msedge --headless`, o mesmo motor
que o `panel-themes-oracle.mjs` usa nesta casa): abre o `app/panel/panel.html` REAL, instala o
`BOOT_PROFILE_JS` REAL do shell por `addInitScript` (antes do primeiro script da pagina) e le os
marcos. Sem janela, sem audio, sem largar a app.

Duas armadilhas cairam na primeira tentativa, e ficam escritas:

* `page.evaluate(profiler)` **depois** do `load` mede outra coisa: o `early` saiu a 233/511/729 ms e
  a fase `load` nao existia (o evento ja tinha passado). Tem de ser `addInitScript`.
* `chrome.exe --headless=new --dump-dom` **nao devolve** nesta maquina (rc=124 em 120 s, DOM vazio)
  e o `agent-browser open` ficou pendurado no mesmo ficheiro. O caminho que funciona e' o Playwright
  com `channel: 'msedge'`, que este repo ja' usa.

## 2. Onde o tempo esta' (8 corridas, `file://`, duas armas)

| marco | valor medido |
|---|---|
| `early -> panel-js` | **59, 62, 73, 78, 179, 263, 340, **671** ms |
| `panel-js -> wired` (fiacao) | **4, 5, 6, 7** ms |
| `wired -> paint1/paint2` | 1-3 ms |
| `paint -> theme:<nome>` (montagem do tema) | **20-112** ms |
| `theme -> dom` | 8-10 ms |
| `dom -> load` | 1-3 ms |

As tres leituras que isto autoriza, e uma que NAO autoriza:

1. **A fiacao da pagina nao e' o bloco: 4-7 ms.** Nenhuma cura do lado da fiacao compra nada.
2. **A montagem do tema custa 20-112 ms** (uma escrita de `data-theme` + `paintAll` sobre dois
   botoes); e' a maior parcela NOMEADA depois da fiacao.
3. **O bloco e' ANTES da primeira linha do `panel.js`** -- e e' ele que varia de 59 a 671 ms para o
   MESMO ficheiro, na mesma maquina, na mesma sessao de browser. Nao e' a pagina que ficou mais
   lenta: e' a maquina. Isto reproduz, em especie, o que o log do dono mediu (`firstPaint` 356 ms em
   2026-11-09 21:22 e 1040 ms em 2026-11-10 09:34).
4. **NAO autoriza** dizer QUAL script e' o bloco. O `slowest`/`resources` do payload continuam vazios
   sobre `file://` (medido: `resources=0`, `slowest=[]`, mesmo com `longtask_supported=true`), e o
   `http://` de medicao contamina o numero com a fila do servidor (um `caption-formulation.js` de
   65 KB aparece a 1 728 ms). Atribuicao por ficheiro continua **UNMEASURED**.

## 3. A cura que foi tentada e REVERTIDA -- e por que isso e' o resultado

Os tres manifestos de tema (`themes.js` 9 846 B + `panel-designs.js` 2 998 B + `zipc-panels.js`
3 162 B = **16 006 B**) eram os unicos scripts da metade bloqueante que ninguem consome antes do
`theme-switcher.js` (que ja' e' `defer`): `panel.js` nao le' `SottoThemeManifest` nem
`ThemeSwitcher` em sitio nenhum (medido: `grep` = 0). Passaram a `defer` e o A/B foi corrido
**intercalado no mesmo browser**, com a pagina BEFORE ao lado (`_boot-before.html`, os tres sem
`defer`):

| par | A (com `defer`) | B (sem `defer`) |
|---|---|---|
| 1-2 | panel-js@78, dom@114 | panel-js@73, dom@100 |
| 3-4 | panel-js@340, dom@411 | panel-js@263, dom@314 |
| 5-6 | panel-js@671, dom@781 | panel-js@669, dom@760 |

As duas metades ficam a 1-50 ms uma da outra enquanto a MESMA metade anda 600 ms entre corridas:
**16 KB a menos no caminho bloqueante nao se mede nesta maquina, e uma mudanca sem ganho medido e'
peso morto.** A pagina foi revertida (`git checkout app/panel/panel.html`) e o achado fica: o bloco
nao sao esses scripts.

## 4. A proxima cura, DESENHADA e NAO aterrada (com a razao)

O maior script da metade bloqueante e' `caption-formulation.js` (**64 858 B**), ao lado do proprio
`panel.js` (**233 918 B**). Adiar o motor para `defer` corta o maior pedaco movel -- mas **nao e'
seguro hoje**, e o que o impede esta' medido no fonte:

* `panel.js:4258` chama `window.SottoFormulation.describeReadiness(...)` **no handler `onStatus`**
  (`wireStatus`, `panel.js:4178`), que corre no arranque, quando a shell empurra o estado;
* `engineFor` (`panel.js:1125`) chama `window.SottoFormulation.createEngine` na PRIMEIRA legenda, e
  o `onCaption` e' registado durante o `panel.js` -- ou seja antes de um script `defer` executar.

Aterrar isto exige duas metades: guarda no `describeReadiness` (`F && F.describeReadiness`) e uma
fila para a primeira legenda que chegue antes do motor, mais uma corrida VIVA da app (legendas a
fluir) para provar que nenhuma das duas metades parte. A corrida viva e' a tela do dono.

## 5. O QUE ESTA' MEDIDO E O QUE NAO ESTA'

* Medido: fiacao 4-7 ms; tema 20-112 ms; o bloco antes do `panel.js` varia 59-671 ms na mesma
  pagina; `file://` nao da Resource Timing (`resources=0`); `--dump-dom` do chrome nao volta.
* NAO medido: qual ficheiro dentro do bloco; a pagina com a ponte REAL (a da sonda e' falsa, entao
  a fiacao mede a fiacao, nao o custo de chamar a shell).
* A resposta definitiva do bloco continua a ser a linha `PANEL_BOOT_PROFILE` da sessao dele, agora
  com marcos (`7e8a18e`).
