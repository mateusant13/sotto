# C18 — "a logo do sotto tá truncada ou tem algo por cima" (mecanismo, não corrigido)

**Estado:** mecanismo encontrado e medido em 2026-10-22 06:1x. **A cura é uma linha em
`app/panel/panel.css`, que está alterado por outra lane neste tree** — não foi aplicada, e por isso
C18 continua ABERTO. Este recibo existe para a cura não se perder à espera do ficheiro.

## O que o dono disse

> *"muitas vezes a logo do sotto tá truncada ou tem algo por cima"*

## O que está no produto (lido, com linha)

`app/panel/panel.html` — a marca é o **primeiro item de uma linha flex**, em todas as variantes de
chrome (`:212`, `:234`, `:239`, `:246`), seguida dos vizinhos que a podem tapar:

```
211  <div class="chrome chrome--bcast" data-chrome="head">
212    <span class="chrome__brand">sotto</span>
213    <span class="chrome__rec" aria-hidden="true"></span>
214    <span class="chrome__state"> ... REC / STBY ... </span>
217    <span class="chrome__chan">CH·01</span>
218    <span class="chrome__tc" data-chrome-tc>--:--:--:--</span>
219  </div>
```

`app/panel/panel.css` — as duas regras que se cruzam:

```
.chrome__brand   { font-size: 11px; font-weight: 600; letter-spacing: 0.2em;
                   text-transform: none; color: var(--text-muted); white-space: nowrap }
.chrome__brand, .wordmark { min-width: 32px }
```

E as que **não** existem, e é a ausência delas que faz o defeito:

* nenhum `flex: none` / `flex: 0 0 auto` na marca ⇒ é um item flex **encolhível**;
* nenhum `min-width: max-content` / `max-content` ⇒ o piso é `32px`, não a largura do texto;
* nenhum `overflow: hidden` na marca ⇒ o texto **não** é cortado com reticências, transborda a caixa;
* o `.chrome` é `display: flex; gap: 6px` ⇒ o vizinho seguinte começa **nos 32px**, e o fundo dele
  pinta por cima do texto que transbordou.

## A conta (limite inferior, sem render)

Com `font-size: 11px` e `letter-spacing: 0.2em` (= 2,2 px por caractere, aplicado a **todos** os cinco):

```
5 caracteres × 0,45em (o avanço mais estreito plausível) = 24,75 px
+ 5 × 2,2 px de tracking                                 = 11,00 px
                                                    total ≥ 35,75 px      > 32 px de piso
```

Num monoespaçado a 0,60em (o caso realista, e há `--font-mono`/`--mono` em jogo) dá
`5 × 6,6 + 11 = 44 px` ⇒ **12 px a mais do que a caixa**. Portanto: **em qualquer tipo de letra que não
seja o mais estreito que existe, o texto da marca é mais largo que o piso de `min-width`**, e o que
sobra é tapado pelo vizinho seguinte. É exactamente "truncada ou tem algo por cima".

Isto explica também porque é **intermitente** ("muitas vezes"): só acontece quando a linha do header
está sob pressão de largura — strip estreita, janela pequena, ou os vizinhos mais largos (`CH·01`,
`--:--:--:--`, `pág. 1`).

## A cura (uma linha, NÃO aplicada)

```css
.chrome__brand, .wordmark { min-width: max-content; flex: 0 0 auto }
```

A marca é a única coisa naquela linha que não pode encolher — os vizinhos podem (`.stripbar__word` já
usa `overflow: hidden; text-overflow: ellipsis`, que é o comportamento certo para uma palavra de
estado). `max-content` torna o piso igual ao texto; `flex: 0 0 auto` impede o encolhimento.

## Porque não está feita

`git status --short app/panel/panel.css` =

```
 M app/panel/panel.css
```

A lane que está a implementar o menu de 3 pontos e o selector de tradução tem esse ficheiro aberto.
Editar por cima era escrever no trabalho dela (regra do repo). O gate para esta cura deve ser escrito
**junto com a cura**, não antes: um gate vermelho no produto é uma armadilha para quem correr a bateria
a seguir.

## O que este recibo NÃO prova

* Não há render nesta medição. A conta é um **limite inferior** sobre as métricas declaradas; a largura
  real depende da face carregada. A prova visual exigiria `_main/_border-radius-probe.py` (Chromium
  headless por CDP) ou `--dump-dom` do WebView2 real — ambos lançamentos, e o dono estava a dormir.
* Não sei se o dono viu isto no **painel** ou na **strip**; o mesmo `.chrome__brand` serve os dois, e a
  strip é o sítio mais estreito, logo o mais provável.
