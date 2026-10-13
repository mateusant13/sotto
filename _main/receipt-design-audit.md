# RECEIPT — lane audit-designs (2026-10-12)

**Lane:** audit-designs — LEITURA APENAS. Nenhum CSS, JS, HTML, JSON ou gerador foi tocado.
**Relatório completo:** `I:/cc-tmp/design-bugs-audit.md` (26 968 B, 457 linhas).
**Escopo de escrita exercido:** `I:/cc-tmp/design-bugs-audit.md` e este recibo. **Mais nada.**
**Nada foi lançado.** Nenhum browser, shell, worker, WebView2, `run.cmd` ou `_audit-verify-all.cmd`.

---

## 0. AVISO — uma lane irmã moveu o painel vivo DURANTE esta auditoria

Medido por `mtime` no fim da lane: `app/panel/themes/fonts.css` mudou a **2026-10-13 00:15:03**
(66 → **70** `@font-face`), `app/panel/panel.html` a **00:18:41** (ganhou
`<link href="caption-float.css">`, e todas as linhas abaixo dele deslocaram-se **+5**), e
`app/panel/panel.js` a **00:14:09**. **Não fui eu** — o meu único `git status` é
``?? _main/receipt-design-audit.md``.

**Re-acção:** re-medi tudo o que toca esses 2 ficheiros e **corrigi o relatório**:

* folhas EAGER: **8 → 9** (entrou `caption-float.css`, 6 646 B, 137 linhas, `E67E0AD00961F850` —
  varrido por mim: **0 preludes fora de raiz**, não traz fuga nova);
* linhas do `panel.html`: 55-59 → **60-64**, 66 → **71**;
* **D4 perdeu uma metade: `Newsreader|300|normal` EXISTE agora** (`present=true`). Essa metade fica
  **FECHADA pela lane irmã**; os **3 itálicos** (`Inter`, `Manrope`, `Jost` a 400 italic) continuam
  **ABERTOS** e re-medidos contra o `fonts.css` de `9033B2371C6222B0`;
* **D1, D2, D3, D5–D10 não mudaram**: `cinematic.css` (`5EB44B0406A67424`),
  `zipc-panels.css` (`9E32F9160C38B855`), `themes.js` (`DEEDC0EFAB3ADD61`) e
  `panel-designs.css` (`FD231DC5B10B2564`) **não se moveram**. As 42 referências de classe mortas
  foram re-contadas no markup de AGORA: continuam 42.

**A lição, e é a regra 2 da `AGENTS.md`:** um `file:line` sem o `sha256` ao lado é uma afirmação com
prazo de validade. O relatório leva agora a tabela de revisões à cabeça.

---

## 1. O que medi, e com que instrumento

Instrumentos, todos em processo Node, nenhum abre GUI:

1. **Execução dos manifestos num `vm` sandbox** com um `window` falso, na MESMA ordem do `panel.html`
   (`themes.js` → `panel-designs.js` → `zipc-panels.js` → `skins.js`), para obter o array real que o
   picker lista. É a única forma de contar o que o dono vê sem abrir o painel.
2. **Parser de CSS próprio** (tokenizer que respeita comentários e strings e **preserva a contagem de
   linhas**), sobre os bytes em disco. Foi re-escrito a meio da lane: a primeira versão colapsava os
   comentários numa linha e **deslocava todos os números de linha**; os números deste relatório são
   da versão que preserva linhas (verificado: `raw lines == stripped lines` em theme-3.css 720/720,
   cinematic.css 6889/6889, panel.css 2964/2964).
3. **Universo de classes** = `class="…"` de `panel.html` ∪ `class=/className=` e
   `classList.add/toggle/remove` de 11 módulos JS. Sem esse universo um "classe morta" seria um
   falso positivo por construção.
4. **Scan de scope próprio**, com a mesma regra do `scope-leak-oracle.js`, para os 3 ficheiros que
   ele não varre.

---

## 2. Os números, e o comando de cada um

| medida | valor | comando / instrumento |
|---|---|---|
| designs no picker | **59** | execução dos 4 manifestos no `vm` |
| nomes duplicados no array | 0 | idem |
| etiquetas duplicadas | **1** ("Tideline" ×2) | idem |
| designs congelados (`SOTTO_SKINS.themes`) | **20** | idem |
| `has(id)` verdadeiro para os 20 skins | **20/20** | reimplementação literal de `skin-host.js:66-82` |
| folhas EAGER | **9** (era 8 quando comecei; entrou `caption-float.css`) | contagem de `<link>` em `panel.html` |
| **scope leak (portão existente)** | **9 folhas, 0 fugas, PASS, rc=0** | `node _main/scope-leak-oracle.js` |
| **controlo do portão** | **4 mutantes, 4 RED, controlo GREEN, rc=0** | `node _main/scope-leak-oracle.js --neg-arm` |
| **gap oracle + controlo** | **CONTROL ARM PASS (0 falhas), rc=0** | `node docs/design-intake/gap-oracle.mjs --self-check` |
| zipc: sequências de selectores distintas para 10 temas | **2** (grupo de 7 + grupo de 3) | parser de CSS |
| zipc: `repeating-linear-gradient` / `grid-cols` / `rounded-full` / `backdrop-filter` / `::after` | **0 / 0 / 0 / 0 / 0** | contagem sobre `zipc-panels.css` |
| zipc: `var()` no ficheiro inteiro | **0** | idem |
| zipc: tokens de afinação consumidos | **0/17** (outras famílias 16/17, 16/17, 13/17) | matriz de consumo `var()` |
| cinematic: `--size-closed` / `--leading-closed` / `--weight-closed` / `--motion-in` | **25 declarações cada, 0 usos cada** | parser de CSS |
| pedidos de fonte sem @font-face | **7 quando medi → 5 agora** (2 × Newsreader 300 FECHADOS pela lane irmã; restam Inter italic ×3, Manrope italic, Jost italic) | resolução por-tema do token `--font-*` contra os `@font-face` |
| famílias declaradas / ficheiros de fonte ausentes | **16 / 0** (faces: 66 → **70**) | `themes/fonts.css` |
| referências de classe mortas | **42** | universo de 140 nomes vs CSS de tema |
| `!important` (comentários removidos) | panel 2, theme-N 2 cada, panel-designs 10, cinematic 0, zipc 0, fonts 0, skin-layout 6, skin-shim 5, vendor 1 | contagem por ficheiro |
| temas que perdem para `panel.css` | **0** (especificidade + ordem de carga + 2 `!important` surface-scoped sem contenda) | cálculo de especificidade |

Números de `git grep` de controlo para as classes mortas (todos com 0 ocorrências no markup e no JS):
`status__hint` **10**, `history__source` **20**, `reveal-button--danger` **10**, `chrome__key` **2**.

---

## 3. A conclusão que o Lead deve levar

**D1 (GRAVE).** Os **10 painéis do 3.º zip** (`themes/zipc-panels.css`) são **2 esqueletos
recoloridos**, não 10 designs. Prova em 4 medições independentes: 2 sequências de selectores; 6 e 4
declarações de layout a diferir dentro de cada grupo; 0 ocorrências das marcas de identidade dos
designs do zip (página pautada do `Paper`, grelha do `Hairline`, avatares e vidro fosco do
`GlassCards`); e o esqueleto inteiro de `GlassCards` são 18 selectores sobre o DOM que o painel já
tem, sem um único elemento novo. É a queixa literal do dono.

**D2 (GRAVE).** Nos mesmos 10, o diálogo de afinação do dono é **inteiramente inerte**: o
`zipc-panels.css` tem **zero** `var()` e **0/17** dos tokens que o `theme-tune.js` escreve.

**D3 (GRAVE).** Nos **25 temas `cine-*`**, 4 tokens são declarados 25 vezes cada e nunca consumidos
(100 declarações sem leitor) — 4 controlos do diálogo mortos. Dono a decidir: `cinematic.css` ou
`theme-tune.js`.

**D4-D8:** 7 fontes sintetizadas, 42 selectores mortos, `150 declarações de token sem leitor, 2
etiquetas divergentes, "Tideline" duplicado.

**Dois falsos positivos que fechei com controlo, e que ficam registados para ninguém os reabrir:**
`cine-tideline-body` ≡ `cine-north-fog` é FIEL ao zip (`themes.ts:161-163` vs `:298-300` são
idênticos caractere a caractere); e o reveal `type` do zip B ESTÁ implementado (mecanismo global do
`panel.css:2358-2362`, com `--type-step: 0ms` a desligá-lo por tema).

**Um erro meu, corrigido a meio, que fica escrito:** a minha primeira leitura de `SOTTO_SKINS`
concluiu que `skin-host.js` estava partido (indexava um array por nome). **Estava errado** — eu
inspeccionei `SK.zips` em vez do topo do objecto; `SOTTO_SKINS.themes` é um objecto com 20 chaves e
`has(id)` é `true` para os 20. A conclusão foi retirada antes de entrar no relatório, e o que ficou
no relatório é a medição correcta.

---

## 4. O que NÃO consegui fechar, e por quê

1. **Nada foi lançado** — é a regra dura desta lane. Logo **não há nenhuma medição de pintura**. A
   equivalência visual design-a-design não está medida; o que está medido é estrutura, selectores,
   propriedades e tokens. Se o Lead quiser a metade visual, o comando exacto está no relatório §5.4:
   `app\webview\run.cmd --show`, com `--no-lazy` como braço de controlo.
2. **O eixo (b)/(c) do zip D não foi medido tema a tema** (20 temas). Medi o registo das 20 skins e o
   mapeamento nome→fragmento; o interior dos `.html` / `.css` de `skins/cinematic-2/` não foi
   interpretado quanto a identidade de desenho.
3. **Não re-executei os geradores.** Se a correcção for feita em `gen_themes.py` / `gen_cinematic.py`
   / `pack_skins.py`, é **obrigatório** provar primeiro que uma corrida fresca reproduz os bytes em
   disco (regra da `AGENTS.md` §10). Não o fiz porque re-executar geradores escreve ficheiros fora do
   meu escopo de escrita.
4. **O loader diferido não foi visto a correr.** Li a fiacção completa
   (`sotto_webview.py:3031-3045`, `:4268`, `:4286`, `:131-213`, `:3629-3645`, `:3528`) e ela
   fecha — mas ler a fiacção não é vê-la entregar `cinematic.css`.

---

## 5. Comandos desta lane (todos re-executáveis, nenhum lança nada)

```
$env:TMPDIR = I:/cc-tmp
node _main/scope-leak-oracle.js
node _main/scope-leak-oracle.js --neg-arm
node docs/design-intake/gap-oracle.mjs --self-check
node docs/design-intake/gap-oracle.mjs
git grep -n -- status__hint            -- app/panel/
git grep -n -- history__source         -- app/panel/
git grep -n -- reveal-button--danger   -- app/panel/
git grep -n -- chrome__key             -- app/panel/
```

**Nada foi commitado, nada foi adicionado ao índice, nenhum `git add -A` foi corrido.** O Lead faz o
commit.
