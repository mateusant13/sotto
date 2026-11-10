# RECIBO — o fundo da legenda: APERTADO, e uma caixa que o escolhe (dono, 2026-11-09/10)

Duas ordens do dono, verbatim, na mesma rodada:

> *"the background in the subtitles is too wide. should be more concise and less bloaty"*

> e, sobre a transparência: uma escolha dele, nas configurações do painel.

Tudo o que segue foi medido NESTA árvore, hoje. Onde há um número, o comando está ao lado.

## 1. Onde cada pedido aterrou

| # | pedido | onde aterrou | instrumento | veredicto |
|---|---|---|---|---|
| 1 | fundo mais apertado | `app/webview/overlay_paint.py` (modo `tight`: a placa acompanha a TINTA, não a caixa) + `caption_settings.py` (`plate` em `tight`/`normal`, default `tight`) | `_main/caption-plate-oracle.py` A1–A5, A9 | `9/9 GREEN`, `VERDICT: PASS` |
| 2 | transparência escolhível | `caption_settings.py` (`opacity`, clamp `[0.3, 1.0]`, escrita atómica) + `caption_overlay.set_visual` | A6 (defaults), A7 (ausente/corrompido/clamp/teto) | `9/9 GREEN` |
| 3 | a CAIXA que escolhe | `app/panel/panel.html` (`caption-plate-select`, `caption-opacity-range`, `caption-opacity-value`), `panel.js` (`sendCaptionLook`) | `_main/caption-visual-dom-oracle.js` (**novo**, este turno) | `8/8 GREEN`, `--neg-arm 3/3` |
| 4 | a fiação de ponta a ponta | `sotto_webview.py`: import de `caption_settings`, `bridge.setCaptionVisual` → `set_visual`, persistência | `caption-plate-oracle` A8 (lê o fonte) + o DOM novo (lê a PÁGINA) | `A8 GREEN`, `VERDICT: PASS` |

## 2. O número que o dono pediu, medido

`caption-plate-oracle` A1, nesta medição (a mesma caixa, os dois modos):

| modo | 1 linha | 2 linhas |
|---|---|---|
| `normal` | 249 × 71 | 310 × 122 |
| `tight` | **205 × 60** | **266 × 111** |

−44 px de largura e −11 px de altura nos dois casos, com a TINTA intacta (A5: a placa cai de 200
para 80 amostras e o branco da letra continua `(255,255,255,255)`). A3 mede que o texto não anda:
o ponto de pintura é o mesmo antes e depois.

## 3. O buraco que o par novo fecha

`caption-plate` julga a MATEMÁTICA da placa; a arm A8 dele lê o FONTE do `panel.js`. **Nenhum dos
dois podia falhar pelo defeito que esta casa já pagou três vezes**: um controlo que pinta na caixa e
não manda nada ao shell. `_main/caption-visual-dom-oracle.js` monta o `app/panel/panel.html`
VERDADEIRO — os `<script src>` dele próprios, executados por ordem, e o `panel.js` que embarca — num
jsdom com **origem que tem storage**, e exige:

1. os três elementos existem;
2. nenhum erro de página;
3. o `select` abre no valor guardado;
4. arranque COM escolha guardada → **uma** chamada a `bridge.setCaptionVisual` com
   `{plate:'normal', opacity:0.7}` para `sotto.captionOpacity='30'`;
5. arranque SEM escolha → **zero** chamadas (o shell já leu `caption-settings.json` quando criou o
   overlay; um push vazio põe o painel por cima do ficheiro que o dono escreveu);
6. mudar a caixa → a escolha nova, com o mesmo alfa;
7. o rótulo segue o dedo (`70%`);
8. transparência 70 % → `opacity 0.30`.

O `--neg-arm` muta o `panel.js` numa **cópia em memória** (o ficheiro do repo nunca é reescrito) e
mede 3/3: **M1** a caixa mudar sem enviar; **M2** o arranque empurrar por cima do ficheiro; **M3** a
transparência invertida. O **M2 obrigou a uma arm própria** — na página COM storage o `stored` já é
verdadeiro e o mutante ficava INERTE (medido: `NEG-ARM FAIL`, 2/3 na primeira versão); o conserto foi
a arm (uma página sem storage), não o mutante.

### 3-bis. Dois defeitos de INSTRUMENTO medidos no caminho, os dois corrigidos

* **`file://` dá origem OPACA e o `localStorage` levanta.** A primeira versão montava o documento
  sobre `file:///…/panel.html`; o `setItem` do harness e o `getItem` do `panel.js` caíam os dois num
  `catch` mudo, e as duas arms do arranque mediam o **default** chamando-lhe "o valor guardado". O
  documento passou a ser montado sobre `https://sotto.local/`; medido, a diferença é `2/9` → `9/9`.
* **`PAGE_STEPS` era código morto em `panel-deps-oracle.py`.** A tabela VIVA é `READS`, e a
  constante só aparecia na docstring. Uma entrada nova escrita em `PAGE_STEPS` não seria julgada por
  ninguém — o oráculo imprimiu `0` ocorrências do passo novo e `18/18` mesmo assim. A constante foi
  **apagada** e o par novo entrou em `READS` com `__PAGE__` (os 25 assets do `panel.html` na lista de
  dependências, senão o `_stepcache` reimprime um PASS sobre outro ficheiro). Medido depois:
  `panel-deps-oracle` **24/24**, `--neg-arm PASS`.

## 4. Bateria

O par novo entrou na `_main\_audit-verify-all.cmd` no mesmo commit:
`caption-visual-dom` (`:step` 0 + `:record`) e `red-as-expected-caption-visual-dom`
(`:expectred` 1, frase `NEG-ARM PASS`). Medidos nesta árvore, depois de escrever:

```
battery-record-pairing-oracle.py   passos: 437 | nomes com registo: 437 | achados: 0   PASS
panel-deps-oracle.py               VERDICT: PASS -- 24/24 arm(s)   (--neg-arm: PASS)
agents-md-pins-oracle.py           AGENTS-PINS PASS -- 2 pin(s) checked live
```

O pin do `.cmd` foi **re-medido**: **336877 B**, **3928 CRLF** / 0 bare LF,
sha256 `93566EC9…163D1D`. Ele inclui passos que outras lanes acrescentaram ao mesmo ficheiro
depois do pin anterior — o número é o VIVO, não a soma da minha mudança.

Custo do par novo: **~3,6 s** (positivo 1,9 s + negativo 4,7 s em duas invocações), a classe
`always`-style não é usada — o passo é cacheável e as dependências governam a cache.

## 5. O QUE NÃO ESTÁ VERIFICADO, e por quê

* **Nada disto foi visto na TELA do dono.** A prova é jsdom + oráculos; `verified` exige uma corrida
  real da app, pela mão dele. O veredicto honesto é **`fixed, NOT verified`**.
* A caixa em si (posição, tipografia, o popover) não tem prova de PIXEL: o jsdom não tem motor de
  layout. O que está provado é o CONTRATO (payload, valores, silêncio do arranque) e a presença dos
  controlos no `panel.html` que embarca.
* `caption-plate` A4 mede o limite de 17,1 px contra a fonte real, mas o `tight` em 2 linhas dá
  `14/13` palavras contra `35/36` do `normal` — uma diferença de UMA palavra na amostra. É a
  geometria da placa, não um bug do texto (A3 mostra os pontos de pintura iguais), e fica registado
  como diferença conhecida em vez de silêncio.
