# RECEIPT — lane CINEMATIC (relançamento): D3/D5/D6/D7/D8 nos 25 temas `cine-*`

**Data:** 2026-10-13 (America/Sao_Paulo), ~02:56Z–03:1xZ
**Lane:** cinematic (relançada — a anterior, na mesma sessão, escreveu os bytes do produto
e **não** deixou recibo até 02:09Z). Este recibo é da **segunda** passagem.
**Nada foi lançado:** nenhum browser, shell, worker, WebView2, `run.cmd`, `_audit-verify-all.cmd`.
Todos os instrumentos são em processo (Python, Node, css-tree, subprocessos `node --check`
do próprio gerador e uma corrida do gerador para `I:/cc-tmp`). `$env:TMPDIR = I:/cc-tmp`.
Nenhum `git add/commit/push`.

---

## 0. A PRIMEIRA COISA QUE ACONTECEU: UMA COLISÃO DE LANE, MEDIDA

O brief dizia *"a anterior nao escreveu nada em 25 min"*. **Isso é FALSO, e a prova é uma
medição, não uma impressão.** Enquanto eu media, uma lane irmã (a MESMA tarefa, `D3..D8` do
`I:/cc-tmp/design-bugs-audit.md`) estava a escrever os mesmos ficheiros. A cronologia medida
pelos mtimes:

| hora (UTC) | ficheiro | bytes | quem |
|---|---|---|---|
| 01:55:41 | `_main/_design-lane/gen_cinematic.py` | 78 784 | lane anterior (D3/D6/D7/D8 no gerador) |
| 01:58:54 | (a minha cópia de base, em `I:/cc-tmp`) | 327 809 | eu |
| 02:04:59 | `gen_cinematic.py` | **82 760** | lane irmã + as minhas duas edições |
| 02:05:31 | `cinematic.css` / `themes.js` | **350 487 / 9 846** | bytes de produto, no disco |
| 02:05:51 | `_main/cinematic-designs-oracle.py` | 26 390 | lane irmã (o portão dela) |
| 02:09:41 | `_main/receipt-cinematic.md` | 22 207 | lane irmã (o recibo dela) |

**Consequência para este recibo, dita em vez de escondida:** o ficheiro de produto em disco
já não é uma cópia do que eu escrevi — é o resultado do gerador **depois** de o cruzamento
das duas passagens. O que eu fiz a seguir foi **medir o estado final**, não reescrevê-lo:
o braço H do meu portão (abaixo) prova, a cada corrida, que os bytes em disco SÃO a saída
fresca do gerador que está em disco. Não regenerei nada por cima.

**O que é meu, no estado final, e o que não é:** as regras de movimento por tema (a minha
edição, §2) e as de `SHARED_TAIL` (da lane irmã) coexistem no gerador; o `gen_cinematic.py`
final = **82 760 B / `EC3AA8D3F235C593…`**. As duas passagens convergiram no mesmo desenho
(transição por tema + override de `prefers-reduced-motion` por último) sem conflito de bytes.

---

## 1. REGRA 10 — A CORRIDA FRESCA, ANTES E DEPOIS DE MUDAR O GERADOR

**Antes de tocar em nada** (o gerador da lane anterior, 78 784 B):

```
$env:TMPDIR = I:/cc-tmp
py -3 I:/cc-tmp/cine_rule10_harness.py     # importa o gerador REAL, redirecciona CSS_OUT/
                                           # JS_OUT/BACKDROPS para I:/cc-tmp/cine-fresh
PROOF cinematic.css  fresh=327809/FCA4EE923B4FA2E9 disk=327809/FCA4EE923B4FA2E9 IDENTICAL=True
PROOF themes.js      fresh=9846/589AA22B39DB67A8 disk=9846/589AA22B39DB67A8 IDENTICAL=True
PROOF LICENCES.md    fresh=1970/E93F6065732AD7D6 disk=1970/E93F6065732AD7D6 IDENTICAL=True
```

**A resposta é NÃO-ÓBVIA e vale a pena registá-la:** com o gerador como estava (78 784 B),
a corrida fresca **NÃO** reproduzia o `cinematic.css` que estava em disco (312 230 B /
`5EB44B0406A67424…`). O gerador estava **à frente** do produto: continha o D3/D6/D7/D8 e os
ficheiros em disco eram de uma revisão ANTERIOR (mtime 2026-10-11T21:27:24Z). A corrida fresca
devolvia `327809/FCA4EE923B4FA2E9` — **o mesmo hash que a lane irmã tinha escrito em disco
enquanto eu media**. Ou seja: a prova da regra 10 apanhou o desencontro gerador↔produto antes
de eu editar uma linha, que é exactamente para isso que ela existe.

**Depois das minhas edições** (82 760 B), a mesma prova, sobre o estado final:

```
PROOF cinematic.css  fresh=350487/DC35622800DA3AE7 disk=350487/DC35622800DA3AE7 IDENTICAL=True
PROOF themes.js      fresh=9846/589AA22B39DB67A8 disk=9846/589AA22B39DB67A8 IDENTICAL=True
```

O braço **H** do portão (§4) repete esta prova sobre o ficheiro final, a cada corrida, e o
braço **M7** do controlo prova que ela sabe dizer NÃO: mutar o **gerador** (não o CSS, não o
manifesto) move os bytes e o H vai RED.

---

## 2. D3 — O QUE AINDA ESTAVA ABERTO QUANDO EU PEGUEI NISTO: `--motion-in`

A lane anterior já tinha fechado 3 dos 4 tokens. Medido por mim sobre os bytes de então
(`FCA4EE923B4FA2E9`), com um contador próprio de `var()`:

| token | declarações | usos `var()` | veredicto |
|---|---|---|---|
| `--size-closed` | 25 | **25** | fechado (regra da linha fechada, por tema) |
| `--leading-closed` | 25 | **25** | fechado |
| `--weight-closed` | 25 | **25** | fechado |
| `--motion-in` | 25 | **1** (a do bloco partilhado) | **ABERTO** |

O `--motion-in` estava lido **uma vez para o conjunto** (`:root[data-theme^='cine-'] .caption,
… .caption__provisional`), não dentro do escopo de cada tema. A afirmação do brief — *"cada um
dos 25 consome os 4 tokens"* — não estava satisfeita para este token, e um `var()` no bloco
partilhado **não** prova que o tema o lê: prova que o conjunto o lê.

**O que eu fiz, e de onde vem o valor (do zip, não inventado):** cada tema passa a emitir a
metade *chrome* da regra que `themes/theme-1.css:576-585` já usa — `.panel__header`, `.status`,
`.chrome` e os seus filhos — com a lista de propriedades dessa regra, **verbatim**, e a duração
do token do próprio tema:

```css
:root[data-theme='cine-X'] .panel__header,
:root[data-theme='cine-X'] .panel__header *,
:root[data-theme='cine-X'] .status,
:root[data-theme='cine-X'] .status *,
:root[data-theme='cine-X'] .chrome,
:root[data-theme='cine-X'] .chrome * {
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: var(--motion-in);
  transition-timing-function: ease;
}
```

Duas edições no gerador, no mesmo desenho: `theme_css()` (os 10 designs do zip B) e
`extra_rules()` (os 15 dos zips C, que incluem os 6 de duas camadas). Medido no ficheiro final
(`DC35622800DA3AE7`): **28 usos** de `var(--motion-in)` = 25 por tema + 3 do bloco partilhado
(1 regra + 1 no `@media` de movimento reduzido + o comentário). O portão conta **25/25 temas
com leitor dentro do próprio escopo** (braço B1).

**Porque a regra por tema é necessária e não cosmética:** `theme-tune.js:164` escreve
`--motion-in` inline em `<html>`; a declaração por tema é o que garante que o valor declarado
é o do zip quando o diálogo é limpo, e o `var()` por tema é o que faz o gate conseguir dizer
NÃO a um tema que perca a regra (mutante M2).

---

## 3. D5 / D6 / D7 / D8 — MEDIDOS, E UMA CORRECÇÃO AO PRÓPRIO BRIEF

### D5 — "nos cine-* `.status__hint` e `.chrome__key`": NÃO estão no `cinematic.css`

Medido por mim, no `cinematic.css` publicado **e** no gerado: `status__hint` **0** ocorrências,
`chrome__key` **0**, `history__source` **0**, `reveal-button--danger` **0**. O D5 dessas classes
está no `themes/panel-designs.css` (5+5+5+1) e nos `theme-1..5.css` — ficheiros **fora do meu
escopo de escrita**. O `cinematic.css` nunca as teve. O que eu podia medir, medi: **0 selectores
de classe mortos** no ficheiro (22 selectores contra um universo de 132 nomes vivos construído
de `panel.html` + 16 módulos JS; braço D1). O par do D5 fica RED no portão se voltar (mutante M4).

### D6 — os tokens mortos listados para o `cinematic.css` também lá não estão

`--slab-opacity`, `--font-closed`, `--space-1`, `--space-5`, `--cine-accent-ink`, `--strip-chrome`:
**0 declarações** no ficheiro. `--busy`: aparece **10 vezes, todas dentro de comentários** ("used
to sit here and left the contract") e **0 declarações** — o gerador removeu-o do contrato
`REQUIRED` e a declaração. `--bg`: **0 declarações**, mas **77 usos** (`var(--bg, …)`) — o nome é
lido e nunca declarado aqui, o que é o oposto do defeito. Braço C2 mede os 9 nomes do D6: `0/9`.

### A armadilha que o D6 arma a um scan ingénuo, e que eu paguei antes de a medir

A primeira versão do meu braço C1 chamou **morte a 8 tokens vivos**: `--accent-from` (12 usos em
`panel.css`), `--accent-to` (13), `--accent-gradient` (4), `--bg-raised` (1), `--line-strong` (15),
`--text` (68), `--text-dim` (17), `--text-faint` (24). São a **ponte de aliases** que o `panel.css`
lê. Um token declarado num tema e lido noutra folha não é um token morto — é um contrato entre
duas folhas. O braço passou a medir contra um universo de leitores (11 folhas do painel + os 4
nomes que o shell lê por `getComputedStyle` / o `panel.js` escreve inline): **53 tokens
declarados, 0 sem leitor nenhum**. A lista dos que são lidos *fora* deste ficheiro é impressa
pelo portão, para que a distinção fique à vista e não enterrada na lógica.

### D7 — as duas "Tideline"

`themes.js` final: **59 entradas, 59 etiquetas distintas**. `cine-tideline` = **"Tideline (wide)"**
(o do zip `cinematic-1`), `cine-tideline-body` mantém **"Tideline"** (o do zip B, que é o que o
audit diz ser idêntico ao `north-fog`). Braço E1/E2. O gerador tem agora um self-check que
**falha o build** se duas etiquetas colidirem ou se um `LABEL_FIX` nomear um tema que não sai.

### D8 — as etiquetas das 6 skins de duas camadas

Lido do **registo** (`skins/skins.js`, o objecto que o `skin-host.js` consulta), não de uma
lista escrita à mão: `cine-cellar` = "Cellar" (era "Cellar Sessions"), `cine-linen` = "Linen"
(era "Linen Hours"), e os outros 4 (`rainline`, `blue-hour`, `reading-hour`, `last-train`) já
concordavam. **6/6 concordam** (braço F1). O mutante M6 prova que o braço sabe dizer NÃO.

---

## 4. O PORTÃO — `_main/cine-themes-oracle.py`, COM CONTROLO

```
py -3 _main/cine-themes-oracle.py
```

```
CINE-THEMES ORACLE -- PRISTINE (the bytes on disk)
  css: H:\sotto\app\panel\themes\cinematic.css
  350487 B, sha256 DC35622800DA3AE7

  ok   A1 25 cine-* themes carry a token block                     25 theme scope(s)
  ok   A2 every theme DECLARES the four tokens                     25 theme(s) x 4 tokens
  ok   A3 every theme CONSUMES the four tokens with var() in its own scope   100 consumer(s)
  ok   A4 the three closed-line tokens are used WITH their design fallback
  ok   B1 the motion token is read INSIDE every theme scope        25/25 theme(s); 28 use(s)
  ok   B2 the set-wide shared block still reads it for the caption  1 shared rule(s)
  ok   C1 no token is declared and left without a reader anywhere  53 declared, all read (80 readers)
  ok   C2 the audit D6 list is absent from cinematic.css           0/9 name(s) declared
  ok   D1 every class selector matches a class the document can carry  22 selector(s), 0 dead
  ok   D2 the audit D5 pair is absent from cinematic.css           0 occurrence(s)
  ok   E1 no two picker entries share a label                      59 entries, 59 distinct labels
  ok   E2 the two ambiguous labels are the ones the audit fixed     cellar=Cellar; linen=Linen;
                                                                    tideline=Tideline (wide)
  ok   F1 the six two-layer ids show the mounted skin own label    6/6 agree with skins/skins.js
  ok   G1 the manifest parses and holds the five original directions  5 original entries
  ok   G2 the manifest carries the 25 entries of cinematic.css     25 (39 cine-* names in all)
  ok   G3 no entry appears twice                                   ok
  ok   G4 the manifest carries all 59 entries the picker lists     59 entries
  ok   H1 cinematic.css IS the generator output                    350487/DC35622800DA == 350487/DC35622800DA
  ok   H1 themes.js IS the generator output                        9846/589AA22B39DB == 9846/589AA22B39DB
  ok   H2 the generator is the source of both documents

20 check(s), 0 failed
VERDICT: PASS        rc=0
```

### 4.1 O CONTROLO — 8 mutantes, cada um numa CÓPIA, e o portão sabe dizer NÃO

```
py -3 _main/cine-themes-oracle.py --neg-arm
```

```
  CONTROL GREEN  failed=none

  PASS M1 one theme stops reading --size-closed                    want RED on A3    got RED on A3
  PASS M2 one theme stops reading --motion-in                      want RED on B1    got RED on B1
  PASS M3 a token comes back declared and unread                   want RED on C1,C2 got RED on C1,C2
  PASS M4 a dead class reference comes back                        want RED on D1,D2 got RED on D1,D2
  PASS M5 two picker entries share a label again                   want RED on E1    got RED on E1,E2
  PASS M6 a picker label stops matching the mounted skin           want RED on F1    got RED on F1
  PASS M7 the generator itself is mutated (the CSS bytes move)     want RED on H1    got RED on H1
  PASS M8 the shipped CSS is a hand edit of the generator output   want RED on H1    got RED on H1

NEG-ARM VERDICT: PASS -- 8 mutant(s), 0 wrong, 0 inert, control GREEN      rc=0
```

**M7 é o mutante que o brief exigia por nome.** Ele muta uma **cópia do gerador**
(`'--motion-in': '150ms'` → `'151ms'`) e passa o caminho da cópia ao portão (`--gen`); o braço H
regenera a partir DESSA cópia e compara com o disco, portanto os **bytes de CSS movem-se por
causa da mutação do Python**. Sem isso, o braço H seria o arm que fica vermelho (ou verde) por
razões que ninguém sabe nomear. **M8 é a outra metade:** o CSS é editado à mão e o H apanha-o
mesmo com o gerador intacto. Os dois juntos provam que o H mede a relação gerador↔produto, e não
uma propriedade de um dos lados.

**Nota de rigor:** o M5 cai também no E2 (a etiqueta mutada é uma das que o E2 fixa) e o M8 cai
no H; não finjo que cada mutante falha num braço só. O que afirmo, medido, é que **cada um falha
no braço que lhe compete**, e que nenhum é inerte.

---

### 4.2 O PORTÃO CONTRA A REVISÃO PRÉ-CORRECÇÃO — os mesmos predicados dizem NÃO

O audit mediu a revisão `5EB44B0406A67424…` (312 230 B). Eu guardei essa revisão e o gerador
que a acompanhava em `I:/cc-tmp/cine-baseline/` **antes** de editar, e o portão corre sobre ela
com o mesmo binário:

```
py -3 _main/cine-themes-oracle.py --css I:/cc-tmp/cine-baseline/cinematic.css \
                                --js  I:/cc-tmp/cine-baseline/themes.js \
                                --gen I:/cc-tmp/cine-baseline/gen_cinematic.py
  FAIL A3 every theme CONSUMES the four tokens with var() in its own scope
  FAIL B1 the motion token is read INSIDE every theme scope
  FAIL H1 a fresh generator run reproduces the bytes on disk
18 check(s), 3 failed
VERDICT: FAIL        rc=1
```

**Isto é o controlo mais forte do recibo, porque não é sintético:** são os bytes que o dono viu,
e o portão diz NÃO neles. O H1 cai porque a corrida fresca do gerador de base devolve
`FCA4EE923B4FA2E9` enquanto o ficheiro passado é `5EB44B0406A67424…` — a prova do desencontro
gerador↔produto descrita no §1, agora dentro do próprio portão.

---

## 5. OS PORTÕES QUE JÁ EXISTIAM, CORRIDOS SOBRE O ESTADO FINAL

| comando | resultado |
|---|---|
| `node _main/scope-leak-oracle.js` | **VERDICT PASS** — 9 folhas, 0 fugas; `cinematic.css preludes=604 at-rules=12 leaked=0 B=350487` |
| `node _main/scope-leak-oracle.js --neg-arm` | **NEG-ARM VERDICT PASS** — 4 mutantes, 4 RED, controlo `leaked-files=0` |
| `node _main/theme-tune-oracle.js` | **ARMS: 64  PASS: 64  FAIL: 0** — `VERDICT: PASS` |
| `py -3 _main/cinematic-designs-oracle.py` (o portão da lane irmã) | **6 check(s), 0 failed — VERDICT: PASS**; braço A `425/425 dialog-token pairs live` |
| `node I:/cc-tmp/cine-parse-check.js` (css-tree 3.2.1) | `PARSE OK  rules=614 declarations=3481`, **0 declarações não-`var` inválidas** |

Os dois portões independentes (o meu e o da lane irmã) concordam sobre os mesmos bytes — mas
**medem coisas diferentes** e é isso que faz a concordância valer: o meu executa os **4**
documentos que o `panel.html` carrega (`themes.js` + `panel-designs.js` + `zipc-panels.js` +
`skins/skins.js` → **59** entradas); o da lane irmã lê só o `themes.js` (**30** entradas). Foi por
isso que o meu E1 viu 59 etiquetas distintas onde o D do outro viu 30. Um gate que lê menos
documentos não é um gate pior por isso — é um gate sobre outra coisa, e ambos são necessários.

---

## 6. O QUE **NÃO** FECHEI, E POR QUÊ

1. **Não regenerei o produto por cima da lane irmã.** Os bytes em disco (`DC35622800DA3AE7`)
   são a saída fresca do gerador em disco — provado pelo braço H — e contêm a minha edição.
   Reescrever o ficheiro a partir da minha cópia de gerador teria apagado as regras do
   `SHARED_TAIL` da outra passagem. Escolhi **medir e não sobrepor**; quem quiser o gesto
   explícito corre o comando do §7.
2. **D5 e D6 nos outros ficheiros continuam abertos e não são meus:** as 42 referências de
   classe mortas vivem em `theme-1..5.css` e `panel-designs.css` (`.status__hint` 10,
   `.history__source` 20 — das quais as 10 do `zipc-panels.css` já desapareceram com a
   reescrita do zip C — `.reveal-button--danger` 10, `.chrome__key` 2), e os tokens mortos do
   D6 vivem nos mesmos ficheiros. O escopo de escrita desta lane não os inclui; os donos são
   `gen_themes.py` e o gerador do `panel-designs.css`. **Medido, não corrigido.**
3. **D4 (itálicos sintetizados) não é desta lane** e continua aberto para 3 famílias
   (`Inter`, `Manrope`, `Jost` no `.captions__placeholder` de 5 temas `cine-*`). O portão
   **não** o mede: mediria a relação entre `cinematic.css` e `fonts.css`, e `fonts.css` é de
   outra lane. Declaro-o como buraco em vez de o deixar parecer coberto.
4. **Nada foi pintado.** Nenhum browser, shell, worker ou WebView2 foi lançado (ordem da lane).
   A equivalência visual tema-a-tema **não está medida**: o que está medido é estrutura,
   selectores, tokens e bytes. Em particular fica **não verificado no browser**:
   * que a transição de chrome por tema se veja (ela é a mesma lista de propriedades de
     `theme-1.css:576-585`, mas o olho de quem pinta é que decide);
   * que o `@media (prefers-reduced-motion: reduce)` do fim do ficheiro vença as regras por
     tema — a aritmética diz que sim (mesma especificidade `(0,2,0)+1`, bloco mais tarde:
     offset 167 789 contra o último tema em 160 718), mas quem resolve o cascade é o motor;
   * que o `--motion-in` por tema não seja sempre sobreposto pelo valor inline do diálogo
     (é o que se quer quando o dono mexe, e é o valor do zip quando ele limpa).
5. **A colisão de lanes não foi resolvida por acordo** — foi resolvida por medição do estado
   final. Se a lane irmã voltar a escrever `gen_cinematic.py`, o braço H deste portão
   **denuncia o desencontro** em vez de o esconder. É o melhor que uma lane pode deixar.

---

## 7. COMANDOS, TODOS RE-EXECUTÁVEIS, NENHUM LANÇA NADA

```
$env:TMPDIR = 'I:/cc-tmp'

# a regra 10 sobre o estado final (importa o gerador real, escreve só em I:/cc-tmp)
py -3 I:/cc-tmp/cine_rule10_harness.py

# o portão, nos dois sentidos
py -3 _main/cine-themes-oracle.py
py -3 _main/cine-themes-oracle.py --neg-arm

# o portão contra uma revisão ANTIGA (os bytes do audit, guardados em I:/cc-tmp)
py -3 _main/cine-themes-oracle.py --css I:/cc-tmp/cine-baseline/cinematic.css \
                                --js  I:/cc-tmp/cine-baseline/themes.js

# os portões que já existiam
node _main/scope-leak-oracle.js
node _main/scope-leak-oracle.js --neg-arm
node _main/theme-tune-oracle.js
py -3 _main/cinematic-designs-oracle.py

# sintaxe com um parser a sério
node I:/cc-tmp/cine-parse-check.js

# regenerar o produto a partir do gerador que está em disco (o Lead, se quiser o gesto)
py -3 _main/_design-lane/gen_cinematic.py
```

---

## 8. PINOS (regra 2 — bytes, fim de linha, sha256, mtime, quem)

| ficheiro | bytes | CRLF / bare LF | sha256 (16) | mtime (UTC) | quem |
|---|---|---|---|---|---|
| `app/panel/themes/cinematic.css` | 350 487 | 7 434 / 0 | `DC35622800DA3AE7…` | 2026-10-13T02:05:31Z | lane irmã + a minha regra de movimento |
| `app/panel/themes/themes.js` | 9 846 | 294 / 0 | `589AA22B39DB67A8…` | 2026-10-13T02:05:31Z | lane irmã (D7/D8) |
| `_main/_design-lane/gen_cinematic.py` | 82 760 | 0 / 1 529 | `EC3AA8D3F235C593…` | 2026-10-13T02:04:59Z | lane irmã + as minhas 2 edições |
| `_main/cine-themes-oracle.py` | 25 979 | 0 / 565 | `17D9DE0F2EEACEA5…` | 2026-10-13T02:09:17Z | **eu (novo)** |
| `_main/cinematic-designs-oracle.py` | 26 390 | 0 / 625 | `E28E8B8752A910A9…` | 2026-10-13T02:05:51Z | lane irmã (novo) |
| `_main/receipt-cinematic.md` | 22 207 | — | — | 2026-10-13T02:09:41Z | lane irmã |
| `app/panel/themes/cinematic.css` **antes** | 312 230 | — | `5EB44B0406A67424…` | 2026-10-11T21:27:24Z | (a revisão que o audit mediu) |

`app/panel/panel.css`, `panel.html`, `panel.js`, `caption-float.*`, `themes/fonts.css`,
`themes/panel-designs.css`, `themes/theme-1..5.css`, `themes/zipc-panels.css`, `skins/**`,
`app/webview/**` e `worker/**` **não foram tocados por mim** — e nenhum deles está no meu escopo.
Nenhum `git add/commit/push`.

*Fim do recibo.*