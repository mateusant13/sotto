# RECEIPT — lane CINEMATIC: os 25 temas `cine-*` — tokens mortos, selectores mortos e etiquetas erradas

**Data:** 2026-10-13 (America/Sao_Paulo)
**Lane:** cinematic (D3, D5, D6, D7, D8 do relatório `I:/cc-tmp/design-bugs-audit.md`)
**Nada foi lançado.** Nenhum browser, shell, worker, WebView2, `run.cmd` ou `_audit-verify-all.cmd`.
Todos os instrumentos são em processo (Python, Node, css-tree); o único subprocesso é o
`node --check` que o PRÓPRIO gerador corre sobre o manifesto que escreveu, e uma corrida do
gerador para um directório TEMP (braço E do portão).

**Escopo de escrita exercido — exactamente 4 ficheiros + este recibo:**

| ficheiro | antes | agora |
|---|---|---|
| `app/panel/themes/cinematic.css` | 312 230 B / `5EB44B0406A67424…` | **350 487 B / `DC35622800DA3AE7…`** (7 434 CRLF / 0 bare LF) |
| `app/panel/themes/themes.js` | 9 854 B / `DEEDC0EFAB3ADD61…` | **9 846 B / `589AA22B39DB67A8…`** (294 CRLF / 0 bare LF) |
| `_main/_design-lane/gen_cinematic.py` | 67 043 B / `0DC0C2381309A720…` | **82 760 B / `EC3AA8D3F235C593…`** |
| `_main/cinematic-designs-oracle.py` | não existia | **26 390 B / `E28E8B8752A910A9…`** (novo — o portão) |
| `_main/receipt-cinematic.md` | não existia | este ficheiro |

`app/panel/panel.css`, `panel.html`, `panel.js`, `caption-float.js`, `caption-float.css`,
`themes/zipc-panels.css`, `themes/fonts.css`, `themes/panel-designs.css`, `themes/theme-1..5.css`,
`skins/**`, `app/webview/**` e `worker/**` **não foram tocados por mim**. O
`app/panel/themes/backdrops/LICENCES.md` também não: a corrida de regeneração redireccionou
`BACKDROPS` para `I:/cc-tmp`, e o ficheiro mantém 1 970 B / `E93F6065732AD7D6…` / mtime
2026-10-11T21:27:24Z. Nenhum `git add/commit/push`. `$env:TMPDIR = I:/cc-tmp` em todos os comandos.

---

## 0. REGRA 10 — A CORRIDA FRESCA REPRODUZIU OS BYTES EM DISCO **ANTES** DE EU EDITAR

O gerador é `gen_cinematic.py` (o cabeçalho do CSS não nomeia o gerador; o ficheiro Python
nomeia-se a si próprio na linha 70 e é o único que escreve `cinematic.css` e `themes.js`).

    copy _main/_design-lane/gen_cinematic.py -> I:/cc-tmp/gen-cinematic-copy.py
      sha256 origem == sha256 cópia == 0DC0C2381309A720B87F65A389DF8BB9A6DC563755279BE9E440CCB9DB4DE122
    py -3 I:/cc-tmp/run-gen-fresh.py        # a CÓPIA, com 5 constantes de caminho redireccionadas
      fresh-cinematic.css  312230 B  sha256 5EB44B0406A674240FBFACE41EB4548D2750924A5655A0B9DF0FA79117E21AFD
      cinematic.css        312230 B  sha256 5EB44B0406A674240FBFACE41EB4548D2750924A5655A0B9DF0FA79117E21AFD  IDÊNTICOS
      fresh-themes.js        9854 B  sha256 DEEDC0EFAB3ADD61555F644B07B0C30A74D96D556D14651E505A0FC70D953293
      themes.js              9854 B  sha256 DEEDC0EFAB3ADD61555F644B07B0C30A74D96D556D14651E505A0FC70D953293  IDÊNTICOS
      rc=0, e os mtimes de `cinematic.css`/`themes.js` ficaram 2026-10-11T21:27:24Z (o repo não foi escrito)

O driver redirecciona **cinco caminhos** (`HERE`, `SOURCE`, `C2_SOURCE`, `CSS_OUT`, `JS_OUT`,
`BACKDROPS`) porque a cópia vive em `I:/cc-tmp` e não tem lá o `zips/` nem os dois módulos de
dados. Caminho não é lógica: os bytes do gerador que correram são os da cópia, sha256 igual ao do
repo. **Só depois disto editei o gerador.** O braço E do portão repete esta prova sobre o ficheiro
final, a cada corrida.

---

## 1. D3 — OS QUATRO CONTROLOS MORTOS PASSAM A VIVOS NOS 25 (100/100, e o diálogo inteiro 425/425)

**Medido antes, com o meu parser sobre os bytes publicados (`5EB44B04…`):** os quatro tokens
`--size-closed`, `--leading-closed`, `--weight-closed`, `--motion-in` estavam declarados
**25 vezes cada** e lidos por **0** regras — o portão novo dizia `0/100`. O diálogo de afinação
inteiro estava em `13/17` nos dez temas base (o número da auditoria) e em `12/17` nos seis do
`cinematic-2`.

**Agora, no ficheiro em disco (`DC356228…`):** `100/100` pares dos quatro tokens, e
**`425/425` pares do diálogo inteiro** (17 tokens × 25 temas) — braço A do portão, que lê os 17
tokens do PRÓPRIO `theme-tune.js` e resolve a ponte de aliases (`--font: var(--font-sans)`) por
onde o `panel.css` lê o valor do tema.

### 1.1 De onde vem cada valor — do zip, nunca inventado

| família | linha fechada no zip | size | leading | weight | motion |
|---|---|---|---|---|---|
| `cinematic` (10) | a **ghost line** — `LiveCaption.tsx:114-125`: `text-[13px] leading-snug text-[var(--caption-ink)]` + `ghostClassName` = `"font-body font-light"` (`themes.ts:25`, nenhum dos 10 designs o sobrepõe) | **13px** (o `md:text-[14.5px]` exige ≥768 px; a nossa coluna é 380) | **1.375** (Tailwind `leading-snug`, confirmado na doc; o zip traz `tailwindcss 4.1.17`) | **300** (`font-light`) | **150ms** — este zip **não** declara transição de cor na legenda; fica o valor do repo |
| `cinematic-1` (9) | a **previous line** — `CaptionStage.tsx:81-98`: `fontSize: clamp(13px, 1.14vw, round(size*0.66))`, `lineHeight: 1.45`, `fontWeight: c.weight` | `max(13px, calc(var(--size-caption) * 0.66))` (a resolução que o próprio módulo extra já usava; o termo `vw` é morto a 380 px) | **1.45** | `var(--weight-caption)` (o zip usa `c.weight`) | **320ms** (`StreamText.tsx:40`: `transition: opacity 320ms ease`) |
| `cinematic-2` (6) | a **previous line do `stack`** — `LiveCaptions.tsx:371-383`: `fontSize: calc(size * 0.66)`, sem leading nem weight próprios (herda) | `max(13px, calc(var(--size-caption) * 0.66))` | `var(--leading-caption)` | `var(--weight-caption)` | **300ms** (`LiveCaptions.tsx:436-437`: `color .3s ease, filter .3s ease`) |

**Onde são consumidos:** nos dez base, a regra da linha fechada
`:root[data-theme='X'] .caption:not(.caption--latest) .caption__text` passou a
`font-size: var(--size-closed, …); line-height: var(--leading-closed, …); font-weight: var(--weight-closed, …)`.
Nos quinze extras, o gerador emite a MESMA leitura depois do bloco do módulo (mesma especificidade,
emitida depois, portanto ganha) — o ficheiro de dados de outra lane não foi tocado.
O `--motion-in` é lido por UMA regra do bloco partilhado do conjunto para a legenda
(`.caption/.caption__text/.caption__confirmed/.caption__provisional`, a lista de propriedades do
`theme-1.css:219`) e, nos extras, também pelas regras de chrome que outra lane acrescentou (ver §6).

### 1.2 O delta visual, medido (linha fechada dos dez base)

| tema | `--size-caption` (clamp) | 0.72×floor (antes) | agora | weight antes→agora | leading antes→agora |
|---|---|---|---|---|---|
| cine-midnight-rain | clamp(20px,2.7vw,31px) | 14.4px | 13px | 300→300 | 1.45→1.375 |
| cine-warm-hour | clamp(21px,2.8vw,33px) | 15.1px | 13px | 400→300 | 1.4→1.375 |
| cine-velvet-dusk | clamp(19px,2.5vw,29px) | 13.7px | 13px | 400→300 | 1.5→1.375 |
| cine-study-light | clamp(16px,2.1vw,24px) | 11.5px | 13px | 400→300 | 1.6→1.375 |
| cine-tideline-body | clamp(20px,2.6vw,30px) | 14.4px | 13px | 300→300 | 1.45→1.375 |
| cine-north-fog | clamp(20px,2.6vw,30px) | 14.4px | 13px | 300→300 | 1.45→1.375 |
| cine-motel-glow | clamp(22px,3vw,35px) | 15.8px | 13px | 500→300 | 1.38→1.375 |
| cine-paper-moon | clamp(14px,1.8vw,20px) | 10.1px | 13px | 500→300 | 1.7→1.375 |
| cine-quiet-streets | clamp(18px,2.3vw,27px) | 13.0px | 13px | 400→300 | 1.5→1.375 |
| cine-last-reel | clamp(21px,2.8vw,32px) | 15.1px | 13px | 500→300 | 1.4→1.375 |

Nos quinze extras o valor pintado **não muda** (o size é a mesma expressão; leading/weight são os
do próprio tema); muda só o `--motion-in` declarado (150ms → 320/300ms). A opacidade `0.72` das
linhas antigas **não** foi tocada — é decisão do painel (DECISION 2), e está dita no cabeçalho.

### 1.3 A decisão que ficou por explicar, e fica

O zip da ghost line também declara uma **entrada** (`ghostIn 0.7s ease both`, `index.css:166-177`).
**Não** a liguei ao `--motion-in`: o campo do diálogo tem máximo **400 ms** (`theme-tune.js:164`),
e um token de 700 ms ali seria um controlo que mente sobre si próprio — o defeito que o
`theme-tune.js` existe para impedir. O `--motion-in` é a transição de cor/superfície, o sentido
que tem em todas as outras famílias; a entrada da linha é a `caption-in 220ms` que o
`panel.css:1155` já dá a `.caption`. Se o Lead quiser a entrada do zip animada, é outra mudança
(e outro dono do token).

---

## 2. D5 — MEDIDO: A FATIA DOS `cine-*` É **VAZIA**, e a atribuição do brief está errada

O brief diz que "nos cine-* a fatia é `.status__hint` e `.chrome__key`". **Isso não se confirma:**

* `.status__hint`, `.chrome__key`, `.history__source` e `.reveal-button--danger` ocorrem **0 vezes**
  em `cinematic.css` (contagem literal sobre os bytes, e o parser de selectores concorda);
* as 12 ocorrências de `status__hint`/`chrome__key` no painel estão em `theme-1..5.css:326`,
  `theme-5.css:648` e `panel-designs.css:311,1012,1769,2483,3191,3513` — **a própria tabela D5 da
  auditoria não lista `cinematic.css` em nenhuma linha**;
* o portão mede **909 referências de classe** no ficheiro, contra um universo de **139 nomes**
  construído de `panel.html` + 16 módulos JS (`class=`, `className=`, `classList.add/toggle/remove`):
  **0 mortas**.

Consequência: nos `cine-*` não havia nada a remover nem a ligar. Os 42 selectores mortos da
auditoria vivem em `theme-1..5.css` e `panel-designs.css` (fora do meu escopo de escrita; as 10
`.history__source` do `zipc-panels.css` foram fechadas pela lane irmã). O braço B fica no portão
com o mutante M2 (`.chrome__key` injectado numa cópia → VERMELHO).

---

## 3. D6 — OITO NOMES SAÍRAM DO CONTRATO, CADA UM COM A MEDIÇÃO

Um token declarado sem leitor é peso morto. Medi **todos** os 53 tokens declarados no ficheiro
final contra `app/panel/**` (CSS, JS, HTML, skins, caption-float) **e** `sotto_webview.py`:
`var(--t)` e `getComputedStyle`. Sete nomes da lista da auditoria tinham **0 leitores em todo o
painel**, e o meu próprio scan acrescentou um oitavo que a auditoria não nomeou:

| nome | leitores antes | decisão | porquê |
|---|---|---|---|
| `--slab-opacity` | 0 | **sai** | o `--panel` do zip já traz o seu próprio alfa; o `theme-tune.js:41-45` regista-o como deliberadamente não-controlo |
| `--busy` | 0 | **sai** | não existe estado `busy` no painel: o `panel.js` só alterna `status--live`/`status--error` |
| `--font-closed` | 0 | **sai** | o `cine_extra_c1.py:183` declara a fonte do PAINEL, e a previous line do zip pinta `scene.captionFont` (`CaptionStage.tsx:85`): dar-lhe leitor pintaria uma fonte que o design nunca usa |
| `--space-1`, `--space-5` | 0 | **saem** | o `panel.css` só lê `--space-2` e `--space-3` |
| `--space-4` | 0 no cine; 1 no `panel-designs.css` | **sai** | **não estava na lista da auditoria** — o único leitor é de outra família |
| `--bg` | 0 | **sai** | os outros dez aliases têm leitores; este não |
| `--cine-accent-ink` | 0 | **sai** | o zip usa o `--accent-ink` como texto sobre uma linha de histórico cheia de accent, elemento que o nosso painel não tem |
| `--strip-chrome` | 1 (`panel.css:1482`) | **não tocado** | ficheiro fora do meu escopo de escrita |

O contrato passou de 59 para 52 tokens por tema; o gerador, o auto-check e o portão (braço C)
recusam qualquer regressão: **53 tokens declarados, 0 sem leitor, 0 dos removidos ainda declarado**.
Controlo M3.

**Resíduo medido e NÃO fechado:** `--ok`, `--error` e `--idle` são declarados no
`cinematic.css` e **não têm leitor dentro dele** (o `panel.css` não os lê; quem os lê são
`theme-1.css`/`panel-designs.css`, e essas regras são scoped aos temas deles). A auditoria
não os listou porque o método dela conta um token vivo se QUALQUER ficheiro o consumir. Não os
removi: são o trio de SIGNIFICADO do produto, o `panel.css` não os declara no `:root`, e removê-los
deixaria os temas cine com os tokens por definir. Fica dito, com o número.

---

## 4. D7/D8 — AS ETIQUETAS: 30/30 ÚNICAS, 6/6 IGUAIS À SKIN

| id | antes | agora | porquê |
|---|---|---|---|
| `cine-tideline` | "Tideline" (duplicado) | **"Tideline (wide)"** | o `cine-tideline-body` é a Tideline do **zip B** (o próprio `gap-oracle.mjs` faz esse join: `tideline -> cine-tideline-body` e diz "zip B Tideline -> cine-tideline-body"); o id só leva o sufixo para os separar, e o outro é o design do `cinematic-1`, variante `wide`, agrupado com o Midnight Café — a etiqueta diz qual é qual |
| `cine-cellar` | "Cellar Sessions" | **"Cellar"** | a skin congelada `skins.js` chama-lhe `"Cellar"`, e é a skin que monta |
| `cine-linen` | "Linen Hours" | **"Linen"** | idem, `"Linen"` |

Medido no manifesto final: **30 entradas, 30 nomes distintos, 30 etiquetas distintas** (era 29), e
dos 6 ids que existem AO MESMO TEMPO no picker e numa skin congelada, **6/6 concordam** (era 4/6).
O gerador ganhou um auto-check que FALHA o build se `LABEL_FIX` nomear um tema que não embarca ou
se duas entradas partilharem etiqueta. Controlos M4 (duplicado) e M5 (skin divergente).

### 4.1 Um QUINTO controlo morto, que a auditoria não nomeou e o meu scan apanhou

`--caption-upper` (o campo "Maiúsculas" do diálogo) estava **morto nos 6 temas do `cinematic-2`**:
o `cine_extra_c2.py:422` escreve `text-transform: none` como LITERAL, e o módulo nunca lê o
token. A auditoria contou-o vivo porque QUALQUER ficheiro o consome (os dez base e o `cinematic-1`
consomem-no). Medido, com os quatro de D3 já fechados: o diálogo estava em **419/425** pares;
**um quinto controlo morto em 6 temas**.
O gerador passou a emitir, para cada extra, `text-transform: var(--caption-upper, <valor do design>)` —
o valor pintado não muda (o declarado é o do design) e o botão passa a mover a legenda. É o que
leva o braço A de **419/425** a **425/425**.

---

## 5. O PORTÃO, COM CONTROLO — `_main/cinematic-designs-oracle.py`

Nada é lançado. 6 braços, todos sobre os bytes em disco (o E corre o gerador para um TEMP).

    py -3 _main/cinematic-designs-oracle.py

    CINEMATIC-DESIGNS ORACLE -- PRISTINE (the bytes on disk)
      file:    H:\sotto\app\panel\themes\cinematic.css
               350487 B, sha256 DC35622800DA3AE7

      ok    A 100/100 D3 pairs live; 425/425 dialog-token pairs live (17 tokens x 25 themes)
      ok    B 909 class reference(s) against a 139-name universe from 17 file(s); 0 dead
      ok    C 53 token(s) declared; 0 with NO reader anywhere; 0 of the removed names still declared
      ok    D 30 entries, 30 distinct names, 30 distinct labels; 6 shared with a frozen skin, 0 label mismatch(es)
      ok    F 94 pinned value(s) match the zip, family by family
      ok    E css dc35622800da3ae7, manifest 589aa22b39db67a8 == a fresh run

    6 check(s), 0 failed
    VERDICT: PASS

**O CONTROL OBRIGA CADA BRAÇO A SABER DIZER NÃO — e cada mutante corre o MESMO predicado contra
uma CÓPIA** (a lição do brief: mutar um módulo JS não muda bytes de CSS; por isso o braço D recebe
um `--themes` e o neg-arm aponta-o para a cópia mutada):

    py -3 _main/cinematic-designs-oracle.py --neg-arm

    NEG-ARM -- each defect injected into a COPY, the SAME predicate re-run
      CONTROL GREEN  failed=none

      PASS M1 one theme stops consuming --size-closed (the D3 defect)   want RED on A   got RED on A
      PASS M2 a selector that matches no node (the D5 defect)           want RED on B   got RED on B
      PASS M3 a token declared with no reader (the D6 defect)           want RED on C   got RED on C
      PASS M4 two picker entries share a label (the D7 defect)          want RED on D   got RED on D
      PASS M5 picker label != the mounted skin (the D8 defect)          want RED on D   got RED on D
      PASS M6 a hand edit (rule 10: not the generator output)           want RED on E   got RED on A,F,E

    NEG-ARM VERDICT: PASS -- 6 mutant(s), 0 wrong, 0 inert, control GREEN

**Um erro do próprio portão, apanhado pelo controlo e corrigido — fica escrito:** o M3 (declarar
`--busy` numa linha) ficou VERDE na primeira versão, porque o braço C lia as declarações com
`^\s*--token:` e o mutante escreve `sel { --busy: x; }` na MESMA linha do selector. O braço C
passou a ler as declarações dos CORPOS das regras já parseadas; o M3 ficou VERMELHO. Um portão que
não sabe dizer NÃO ao defeito que ele próprio persegue não é um portão.

### 5.1 Os outros portões, re-corridos

| comando | resultado |
|---|---|
| `node _main/scope-leak-oracle.js` | **PASS** — 9 folhas, 0 fugas; `cinematic.css preludes=604 at-rules=12 leaked=0 B=350487 DC35622800DA3AE7` |
| `node _main/scope-leak-oracle.js --neg-arm` | **PASS** — 4 mutantes RED, controlo GREEN |
| `node _main/theme-tune-oracle.js` | **PASS** — 64 checks, 0 falhas (lê `theme-1..5.css`/`panel.css`; não foi afectado) |
| `node docs/design-intake/gap-oracle.mjs` | rc=0; o join de nomes continua a dizer `tideline -> cine-tideline-body` |
| css-tree (`H:/sotto/node_modules/css-tree`) | `csstree.parse` OK: 629 regras, 3 496 declarações, **0 propriedades desconhecidas**, **0 valores inválidos** (726 `var()` que o lexer não resolve), **7 434 CRLF / 0 bare LF** |

---

## 6. AVISO DE CONCORRÊNCIA — OUTRA LANE ESCREVEU O MESMO GERADOR ENQUANTO EU TRABALHAVA

Medido por `mtime`/`sha256`: às **2026-10-13T02:01:52Z** o `gen_cinematic.py` mudou sem ser
por mim (80 720 B, `261261DD267D1963…`). A alteração é a **metade chrome** do mesmo D3: regras
por tema `.panel__header, .panel__header *, .status, .status *, .chrome, .chrome *` com
`transition-duration: var(--motion-in)` — a lista de propriedades de `theme-1.css:576-585` —
emitidas tanto no `theme_css` como no `extra_rules`, e o comentário delas refere o meu bloco
partilhado.

**Não reverti.** Integrei-a, regenerei, e o portão cobre o ficheiro COMBINADO (o braço A vê o
`--motion-in` consumido duas vezes por tema, e o braço E confirma que os bytes em disco são a
corrida fresca do gerador combinado). Acrescentei ainda o que faltava para a promessa ficar
inteira: um bloco final (`SHARED_TAIL`) com o `@media (prefers-reduced-motion: reduce)` que
zera as transições **também no chrome** — sem ele, o chrome transitionava sob reduced-motion
enquanto a legenda não, e a lista de selectores de `theme-1.css:593-602` cobre os dois.

**Risco declarado:** se aquela lane voltar a editar o gerador, o braço E fica VERMELHO na próxima
corrida (é exactamente para isso que ele existe). Pin de agora: 82 760 B / `EC3AA8D3F235C593…` /
mtime 2026-10-13T02:04:59Z.

---

## 7. O QUE **NÃO** FECHEI, E POR QUÊ

1. **Nenhuma medição de pintura.** A regra dura da lane proíbe lançar o browser/app/shell. Tudo o
   que afirmo sobre o que o dono VÊ é derivado de: parse de bytes (o meu), css-tree (sintaxe),
   aritmética de especificidade e o universo de classes do markup real. **A equivalência visual
   tema-a-tema com o zip continua NÃO MEDIDA.** O comando exacto, para o Lead:
   `cmd /c app\webview\run.cmd --show` (e escolher os temas no picker).
2. **`--ok`/`--error`/`--idle`** declarados no `cinematic.css` sem leitor dentro dele —
   medido, explicado em §3, deixado em pé de propósito.
3. **`--strip-chrome`** (1 declaração em `panel.css`, 1 leitor lá) — ficheiro fora do escopo.
4. **Os 42 selectores mortos de D5** em `theme-1..5.css`/`panel-designs.css` — fora do escopo;
   nos `cine-*` a fatia é zero (§2).
5. **D4** (os 3 itálicos sintetizados em `Inter`/`Manrope`/`Jost`) — dono é `themes/fonts.css`.
6. **A entrada da ghost line (0.7 s)** não foi ligada a `--motion-in` (§1.3): 700 ms não cabe no
   intervalo 0–400 do diálogo. Decisão registada, reversível numa linha do `CLOSED`.
7. **A escolha de 13 px para TODAS as linhas antigas dos dez base** é um juízo de desenho: o zip
   só mostra UMA ghost line. Está medida a delta (§1.2) e o valor vive numa linha do gerador.
8. **O valor de `--motion-in` nos dez base (150 ms)** é o valor do repo, não do zip — esse zip não
   declara transição de cor na legenda. Dito na tabela de §1.1.

---

## 8. COMANDOS, TODOS RE-EXECUTÁVEIS, NENHUM LANÇA NADA

    $env:TMPDIR = 'I:/cc-tmp'

    # a prova da regra 10, nos dois sentidos (o braço E faz isto sozinho)
    py -3 _main/cinematic-designs-oracle.py            # 6 checks, VERDICT PASS
    py -3 _main/cinematic-designs-oracle.py --neg-arm  # 6 mutantes, controlo GREEN

    # regenerar o produto (o Lead, se quiser)
    py -3 I:/cc-tmp/regen-product.py                   # BACKDROPS redireccionado; escreve os 2 ficheiros

    # os portões que já existiam
    node _main/scope-leak-oracle.js
    node _main/scope-leak-oracle.js --neg-arm
    node _main/theme-tune-oracle.js
    node I:/cc-tmp/cine-css-parse-check.js             # css-tree sobre o ficheiro publicado

## 9. PINOS (regra 2 — tamanho, fim de linha, sha256, mtime)

| ficheiro | bytes | CRLF / bare LF | sha256 | mtime (UTC) |
|---|---|---|---|---|
| `app/panel/themes/cinematic.css` | 350 487 | 7 434 / 0 | `DC35622800DA3AE7F2B7AB531B720307BD7666ED6933005860F227E6C386C5B3` | 2026-10-13T02:05:31Z |
| `app/panel/themes/themes.js` | 9 846 | 294 / 0 | `589AA22B39DB67A8E9F22EBF780A8F611F140B65CB92E3F13C2E556187EF5798` | 2026-10-13T02:05:31Z |
| `_main/_design-lane/gen_cinematic.py` | 82 760 | (py, LF) | `EC3AA8D3F235C593EC34A965BF069FACD19970C43BC95F975C29A67D603EF907` | 2026-10-13T02:04:59Z |
| `_main/cinematic-designs-oracle.py` | 26 390 | (py, LF) | `E28E8B8752A910A963E1B190D98B4D4D77734DBCAEFF428AA31A7B79DD79FD73` | 2026-10-13T02:05:51Z |
| `cinematic.css` **antes** | 312 230 | 6 888 / 0 | `5EB44B0406A674240FBFACE41EB4548D2750924A5655A0B9DF0FA79117E21AFD` | 2026-10-11T21:27:24Z |
| `themes.js` **antes** | 9 854 | 294 / 0 | `DEEDC0EFAB3ADD61555F644B07B0C30A74D96D556D14651E505A0FC70D953293` | 2026-10-11T21:27:24Z |
| `gen_cinematic.py` **antes** | 67 043 | (py) | `0DC0C2381309A720B87F65A389DF8BB9A6DC563755279BE9E440CCB9DB4DE122` | 2026-10-11T21:27:23Z |
| `themes/backdrops/LICENCES.md` | 1 970 | 21 / 0 | `E93F6065732AD7D6CEE940593ABB20C6205ACA7857DCE67E081AD3809E00A76B` | 2026-10-11T21:27:24Z (não movido) |

*Fim do recibo.*
