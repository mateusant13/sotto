# RECEBIMENTO -- lane BASE-TEMAS: D5 (os 42 selectores mortos), D6 (tokens sem leitor) e D4 (os italicos sintetizados)

**Data:** 2026-10-13 (America/Sao_Paulo)
**Lane:** base-temas (D4, D5, D6 do relatorio `I:/cc-tmp/design-bugs-audit.md`, nos ficheiros de `gen_themes.py` e no D4 do `gen_cinematic.py`)
**Nada foi lancado.** Nenhum browser, shell, worker, WebView2, `run.cmd` ou `_audit-verify-all.cmd`. Os unicos subprocessos sao (a) as copias dos geradores, com as saidas redireccionadas para `I:/cc-tmp`, e (b) o `node --check` que o proprio `gen_cinematic.py` corre sobre o manifesto que escreveu. `$env:TMPDIR = I:/cc-tmp` em todos os comandos. Nenhum `git add/commit/push`.

## Escopo de escrita exercido -- 11 ficheiros (9 editados + 2 novos), e mais nenhum

| ficheiro | antes | agora |
|---|---|---|
| `app/panel/themes/theme-1.css` | 26 952 B / `B259A5F3894CEC06...` | **28 973 B / `BBD3D7FA94EFCA6F...`** (721 CRLF / 0 bare LF) |
| `app/panel/themes/theme-2.css` | 27 169 B / `1FB154C049F19836...` | **29 191 B / `CF69B09DF46AAAD2...`** (755 / 0) |
| `app/panel/themes/theme-3.css` | 27 302 B / `B8CE0CED74E57286...` | **29 341 B / `DCBD6B10B311893C...`** (734 / 0) |
| `app/panel/themes/theme-4.css` | 26 235 B / `DD99FFD544DCFA46...` | **28 274 B / `6BB9A5BBC801592C...`** (715 / 0) |
| `app/panel/themes/theme-5.css` | 27 437 B / `BA6C8755B5526373...` | **29 297 B / `697F811B0CC10925...`** (785 / 0) |
| `app/panel/themes/panel-designs.css` | 128 716 B / `FD231DC5B10B2564...` | **139 610 B / `32592C7661014F95...`** (3 771 / 0) |
| `app/panel/themes/cinematic.css` | 350 487 B / `DC35622800DA3AE7...` | **350 326 B / `9B0A50DAF0874AAE...`** (7 427 / 0) |
| `_main/_design-lane/gen_themes.py` | 160 153 B / `0F9A3B190452DB8E...` | **164 970 B / `E088712A5354986B...`** (3 312 CRLF / 0 bare LF) |
| `_main/_design-lane/gen_cinematic.py` | 82 760 B / `EC3AA8D3F235C593...` | **84 158 B / `A09208F95B9F3BBF...`** |
| `_main/base-themes-oracle.py` | nao existia | **29 805 B / `A1EAB4FB94DA24F1...`** (novo -- o portao) |
| `_main/receipt-base-themes.md` | nao existia | este ficheiro |

`_main/_design-lane/build_fonts.py` foi LIDO e CORRIDO (regra 10) mas **nao editado**: 11 916 B / `0AA1F76289DE3E92...`, mtime intacto.

**Nao tocados, e medidos no fim** (sha256 inalterado, mtime anterior a esta lane): `panel.css` `C2002FC75D49E773`, `panel.html` `2A065214AC0571B3`, `panel.js` `CBDCB50FEF6A8B95`, `caption-float.js` `0C6896BFD849FCE4`, `caption-float.css` `E67E0AD00961F850`, `themes/panel-designs.js` `68B5907DC1E12CCE`, `themes/themes.js` `589AA22B39DB67A8`, `themes/fonts.css` `9033B2371C6222B0`, `themes/zipc-panels.css` `CB08DCA3AF1C4F22`, `theme-tune.js` `C61E082186BF0E49`, `skins/**`, `app/webview/**`, `worker/**`.

---

## 0. REGRA 10 PRIMEIRO -- e a corrida fresca NAO reproduzia o `cinematic.css` ate eu semear os inputs

Instrumento: `I:/cc-tmp/rule10-base.py` (depois absorvido pelo ARM D do portao). Cada gerador e copiado para `I:/cc-tmp`, o sha256 da copia e comparado com o do repo, e **a copia e que corre** -- com `__file__` a apontar para o ficheiro do repo, para que os caminhos de ENTRADA (`zips/`, modulos irmaos) resolvam normalmente e so as constantes de SAIDA sejam redireccionadas. Caminho nao e logica.

```
COPY gen-themes-copy.py     repo=160153/0F9A3B190452DB8E copy=160153/0F9A3B190452DB8E EQUAL=True
PROOF theme-1.css                  fresh=26952/B259A5F3894CEC06 disk=26952/B259A5F3894CEC06 IDENTICAL=True
PROOF theme-2.css                  fresh=27169/1FB154C049F19836 disk=27169/1FB154C049F19836 IDENTICAL=True
PROOF theme-3.css                  fresh=27302/B8CE0CED74E57286 disk=27302/B8CE0CED74E57286 IDENTICAL=True
PROOF theme-4.css                  fresh=26235/DD99FFD544DCFA46 disk=26235/DD99FFD544DCFA46 IDENTICAL=True
PROOF theme-5.css                  fresh=27437/BA6C8755B5526373 disk=27437/BA6C8755B5526373 IDENTICAL=True
PROOF panel-designs.css            fresh=128716/FD231DC5B10B2564 disk=128716/FD231DC5B10B2564 IDENTICAL=True
PROOF panel-designs.js             fresh=2998/68B5907DC1E12CCE disk=2998/68B5907DC1E12CCE IDENTICAL=True
PROOF cinematic.css                fresh=350487/DC35622800DA3AE7 disk=350487/DC35622800DA3AE7 IDENTICAL=True
PROOF themes.js                    fresh=9846/589AA22B39DB67A8 disk=9846/589AA22B39DB67A8 IDENTICAL=True
PROOF fonts.css                    fresh=29571/9033B2371C6222B0 disk=29571/9033B2371C6222B0 IDENTICAL=True
```

**Dois achados do instrumento, e ambos importam a quem repetir isto:**

1. **`gen_cinematic.py` le os ficheiros que substitui.** `manifest(rows)` abre o `themes.js` EM DISCO para capturar as cinco entradas originais (`gen_cinematic.py:966-996`), por isso a corrida fresca tem de comecar com o `themes.js` publicado copiado para o scratch -- sem isso morre com `FileNotFoundError`.
2. **`fetch_backdrop()` trata uma foto ja empacotada como INPUT** (`gen_cinematic.py:1042`: existe e > 8192 B -> devolve ` (bundled photo)`). Com o directório de backdrops VAZIO, a corrida **DESCARREGA**: medido na minha primeira passagem, o `curl.exe` trouxe 9 das 10 fotos (172 948 B, 131 536 B, ...) e o `north-fog` falhou o teste de magia JPEG, o que sozinho moveu o `cinematic.css` para `350742/E7C91667B9E07706` -- **255 B a mais, e a nota do tema passou de `(bundled photo)` para `(no photo could be bundled: gradient of the palette)`**. Com o directório semeado a partir de `app/panel/themes/backdrops/`, a corrida e determinista e **sem rede**: `350487/DC35622800DA3AE7`, identico. O ARM D do portao semeia sempre.

**Antes de editar uma linha**, a prova acima estava completa: os 7 ficheiros de produto eram reproduzidos byte a byte pelo gerador em disco. So depois editei.

**Residuo medido no mesmo braco, e PRE-EXISTENTE:** `app/panel/fonts/` tem **1 ficheiro a mais** do que o gerador produz -- `ibm-plex-mono-latin-700-normal.woff2` (14 956 B), que nenhum `@font-face` de `fonts.css` declara. O `build_fonts.py` de hoje so empacota IBM Plex Mono 400/500/600 (+400 italic). Nao apaguei nada (fora do meu escopo); o `_main/fonts-fidelity-oracle.mjs` confirma-o por outro caminho: `WARN undeclared file ibm-plex-mono-latin-700-normal.woff2 (14956 B, dead bytes: no @font-face declares it)`.

---

## 1. D5 -- as 42 referencias: 32 fechadas aqui, 10 ja fechadas pela lane irma, 0 em toda a CSS do painel

**Universo medido pelo portao, em tempo de execucao:** **134 classes** = os `class=` estaticos de `panel.html` (87 tokens) unidos as classes atribuidas pelos **12** modulos que o documento carrega (`<script src>`: caption-formulation, history-source, history-gallery, surface, themes/themes.js, themes/panel-designs.js, themes/zipc-panels.js, theme-switcher, theme-tune, panel.js, letter-swap.js, caption-float.js). A auditoria contou 11 modulos; hoje sao 12 (o `letter-swap.js` entrou).

| classe | refs na auditoria | onde | decisao, com a medicao |
|---|---|---|---|
| `.status__hint` | 10 | `theme-1..5.css:326` + `panel-designs.css` x5 | **SAI** -- 0 tokens de classe em `panel.html`, 0 nos 12 modulos, 0 nos 105 ficheiros de skin, 0 nos cinco zips. O bloco onde vivia dizia `the footer, where Alt+C is announced`: o dono tirou essa dica do painel (`panel.html:935`) e o `<kbd>` foi com ela. |
| `.history__source` | 20 (10 meus + 10 zipc) | `theme-1..5.css:341`, `panel-designs.css` x5, `zipc-panels.css` x10 | **SAI** -- mesma medicao. Nenhuma linha de historico de nenhum zip imprime etiqueta de fonte (as linhas do mockup levam texto, hora e uma confianca que o painel recusa inventar). Os dois membros vivos do grupo (`.history__note` = `panel.html:490`/`:538`, `.history__count` = `:478`) ficam. **Os 10 de `zipc-panels.css` ja tinham saido** (medido agora: 0 nesse ficheiro). |
| `.reveal-button--danger` | 10 | `theme-1..5.css:382` + `panel-designs.css` x5 | **SAI** -- `reveal-button` existe (`panel.html:520`) mas nenhum modulo lhe da um estado `--danger`; quem o tem e o `.dialog-button--danger` (markup estatico) e o `.icon-button--danger` (o JS). O membro vivo conserva a regra. |
| `.chrome__key` | 2 | `theme-5.css:648`, `panel-designs.css:3513` | **SAI** -- era a placa `ALT+C` do cabecalho do Instrumento. As 12 classes `chrome__*` que o painel carrega sao `brand, chan, dot, draft, led, meter, off, on, page, rec, state, tc`. Os `<Kbd>` dos zips estao no RODAPE DA LANDING PAGE (`App.tsx:76-86`), nunca dentro de um painel. |

**A 43.ª referencia morta, do MESMO instrumento, e que eu fechei tambem:** `{S} kbd` (uma regra de elemento, nao de classe, por isso nao entra nas 42). Medido: **0** elementos `<kbd>` em todo o `app/panel` -- a unica ocorrencia e a palavra dentro do comentario de `panel.html:935`. A regra pintava o mesmo aviso que o dono mandou sair; foi com as outras.

**Total medido agora, em toda a CSS debaixo de `app/panel/`: 0 ocorrencias das 4 classes.** `node _main/scope-leak-oracle.js` -> `VERDICT PASS -- 9 stylesheet(s)`, e cada membro por virgula continua com o seu scope (a regra do `emit()` que uma lane irma corrigiu nao foi tocada).

**Controlo (ARM A do portao):** `--neg-arm` reinsere `{S} .status__hint` na copia do gerador e regenera -> `M1 ... RED as required on ['A(10)']` (10 seletores mortos, um por design). O mesmo mutante NAO move o ARM B nem o C: a arm mede a RELACAO, nao um hash.

---

## 2. D6 -- o censo completo (o da auditoria + 4 que ela nao contou) e o que fiz com cada um

**Instrumento:** censo com SCOPE -- para cada declaracao, os leitores contados sao os `var()` do PROPRIO ficheiro, os das folhas de base que se aplicam sob o scope do tema (`panel.css`, `caption-float.css`, `skin-layout.css`, `skins/*.css`) e as mencoes no JS do painel / no shell, **com comentarios removidos** (o `theme-tune.js` fala de varios destes tokens em prosa, e um scan que nao os remova inventa leitores). Um scan global em vez de por scope da o resultado errado para `--font-caption`, `--text-confirmed` e `--size-meta`, que sao LIDOS no `cinematic.css` mas em SCOPES IRMAOS (`:root[data-theme='cine-*']`), nunca no scope de um `theme-N`.

| token | declaracoes nos meus 6 ficheiros | leitores | decisao | porque |
|---|---|---|---|---|
| `--slab-opacity` | 10 | 0 | **REMOVIDO** | o alfa e consumido no BUILD, duas vezes: por `over_black()` (a cor do zip composta sobre o palco preto) e pelo `color-mix(... N% ...)` que a skin escreve. Nao ha regra que o possa ler; o valor continua no ledger (`--trace`). |
| `--busy` | 10 | 0 | **REMOVIDO** | a cor do zip por detras (`--color-amberlite` / `--color-amberx`) e a PALAVRA MAIS FRESCA, papel que o `--text-provisional` ja cumpre (declarado e lido). Nao existe estado `busy` no vocabulario do painel (idle / live / error). |
| `--font-caption` | 10 | 0 | **REMOVIDO** | e sempre `var(--font-sans)` (o `t.put` e literal) e a regra da legenda nomeia `var(--font-sans)` directamente. Dois nomes para um valor e nenhum leitor. |
| `--font-closed` | 10 | 0 | **REMOVIDO** | idem, e nenhum zip da uma face diferente a linha fechada (as linhas fechadas sao a linha viva um tamanho abaixo). |
| `--space-1` | 10 | 0 | **REMOVIDO** | a escala do zip e a do Tailwind (dinamica); nos so declaramos 5 passos, e os dois extremos nao eram lidos por ninguem. |
| `--space-5` | 10 | 0 | **REMOVIDO** | idem. |
| `--bg` | 10 | 0 | **REMOVIDO** | alias do `--bg-slab`; os OUTROS 10 aliases do mesmo bloco sao lidos (`--bg-raised`, `--text`, `--text-dim`, `--text-faint`, `--radius`, `--font`, `--mono`, `--accent-from`, `--accent-to`, `--accent-gradient`) e o `panel.css:24` declara o seu proprio `--bg`. |
| `--text-confirmed` | 10 | **10 (novos)** | **GANHOU LEITOR** | a regra que pinta a tinta confirmada dentro da linha em formacao (`{B} .caption--provisional .caption__text`) escrevia o LITERAL; medido nos 10 designs, o literal E o valor do token (theme-1 `rgba(242, 233, 216, 0.82)`, theme-2 `rgba(255, 255, 255, 0.9)`, theme-3/4 `#EAE5D9`, theme-5 `#FFFFFF`, pd-tele `rgba(255, 255, 255, 0.6)`, ...). Passou a `color: var(--text-confirmed)`: **mesma cor, uma fonte em vez de duas**. |
| `--size-meta` | 10 | 0 | **NAO FECHADO -- declarado** | ver abaixo. |
| `--space-4` | 5 (so `theme-1..5`) | 0 neles / **1** no `panel-designs` | **NAO FECHADO -- declarado** | o bloco de tokens e PARTILHADO pelas duas lanes; o `pd-cine` le-o (`padding-left: var(--space-4)`, do `pl-4` do proprio zip). Removê-lo partia o unico design que o le. |

**Os 4 tokens que a auditoria NAO contou** e que o mesmo instrumento apanhou: `--font-caption` (10), `--text-confirmed` (10), `--size-meta` (10) e `--space-4` (5). O proprio `theme-tune.js:41-52` documenta os tres primeiros como inertes -- o que a auditoria leu como "so um comentario" era, na verdade, a justificacao escrita do dialogo de afinacao.

### 2.1 `--size-meta`: porque NAO o fechei (numeros, nao opiniao)

E o valor do zip para o tier meta de cada design, e a unica regra que o poderia ler e o bloco CHROME, que e **partilhado** pelas duas lanes e cujos `font-size` sao literais POR FAMILIA DE CHROME. Medido, tema a tema:

| tema (lane A) | `--size-meta` | literal do CHROME | tema (lane B) | `--size-meta` | literal do CHROME |
|---|---|---|---|---|---|
| theme-1 | 10px | 10px | pd-tele | **11px** | 10px |
| theme-2 | 9px | 9px | pd-bcast | **9.5px** | 9px |
| theme-3 | 11px | 11px | pd-mano | **10px** | 11px |
| theme-4 | 12px | 12px | pd-cine | **13px** | 12px |
| theme-5 | 9px | 9px | pd-instr | **10px** | 9px |

Ou seja: fazer a regra ler `var(--size-meta)` NAO e um refactor neutro -- **muda o tamanho pintado de 5 dos 10 designs** (os da lane B). Que tamanho cada chrome pinta e uma decisao de DESENHO, nao de higiene; o token fica como a pega da correccao e a decisao fica REPORTADA. Isto e, de longe, o achado mais interessante deste D6: **os cinco designs do 2.º zip pintam o seu chrome no tamanho do design do 1.º zip da mesma familia**.

### 2.2 A CONSEQUENCIA, dita em vez de escondida: `theme-tune.js` e o seu orgao ficaram desactualizados

O dialogo de afinacao recusa oferecer estes tokens PORQUE estao declarados e ninguem os le -- e o `_main/theme-tune-oracle.js` **PINAVA** esse estado (ARM 8, lista `INERT = ['--slab-opacity', '--text-confirmed', '--font-caption', '--font-closed']`). Depois do meu fecho, esse orgao fica com **4 arms VERMELHOS** (medido: `ARMS: 64 PASS: 60 FAIL: 4`, `VERDICT: FAIL`):

```
FAIL liveness: --slab-opacity really is declared in a theme (so it is a trap, not a typo)
FAIL liveness: --text-confirmed is declared and NOT consumed (the reason it is refused)   --text-confirmed IS consumed -- revisit the exclusion
FAIL liveness: --font-caption really is declared in a theme (so it is a trap, not a typo)
FAIL liveness: --font-closed really is declared in a theme (so it is a trap, not a typo)
```

**Nao os corrigi porque `app/panel/theme-tune.js` e `_main/theme-tune-oracle.js` estao FORA do meu escopo de escrita.** Quem os tem de re-baselinar: (1) o paragrafo `app/panel/theme-tune.js:41-52` (as 3 bullets `--slab-opacity` / `--text-confirmed` / `--font-caption`+`--font-closed` descrevem declaracoes que ja nao existem; a razao pela qual o dialogo os recusa desapareceu com elas) e (2) o ARM 8 do orgao (a lista `INERT` fica vazia, e o ARM 9 usa `--slab-opacity` como token bogus). O proprio orgao pede isso na mensagem que imprime: `revisit the exclusion`.

### 2.3 Os dois tokens que a auditoria mandou so REPORTAR

* `--strip-chrome` (1 declaracao, `panel.css:73`, 0 leitores em CSS, 0 em JS, 0 no shell): **fora do meu escopo** (`panel.css`). Reportado, nao tocado.
* `--cine-accent-ink` (10 na auditoria): **ja nao existe** -- medido agora, 0 ocorrencias em `cinematic.css` e 0 em `gen_cinematic.py`. Fechado pela lane irma do cinematic; nao o contei como meu.

**Controlo (ARM B do portao):** `--neg-arm` volta a declarar `--busy` na copia do gerador e regenera -> `M2 ... RED as required on ['B(10)']` (10 declaracoes mortas, uma por design).

---

## 3. D4 -- os italicos: 30 pedidos, 10 sintetizados, e a causa NAO e o zip

**A auditoria mediu 5 (Inter x3, Manrope x1, Jost x1). O instrumento certo mede 10.** O resolvedor tem de seguir a cadeia `--font-caption` -> `--font-sans` dentro do SCOPE do tema; a auditoria parou no primeiro salto e por isso nao viu os 5 temas cuja familia e o **Outfit**.

```
PEDIDOS DE ITALICO SEM FACE EMPACOTADA (o browser sintetiza o obliquo) -- 10
cine-midnight-rain@249   PLACEHOLDER fam=Outfit
cine-velvet-dusk@698    PLACEHOLDER fam=Outfit
cine-tideline-body@1141 PLACEHOLDER fam=Outfit
cine-quiet-streets@1807 PLACEHOLDER fam=Outfit
cine-north-fog@2256     PLACEHOLDER fam=Outfit
cine-rainglass@2894     PLACEHOLDER fam=Inter
cine-fieldnotes@3565    PLACEHOLDER fam=Inter
cine-rainline@5567      PLACEHOLDER fam=Manrope
cine-last-train@6997    PLACEHOLDER fam=Jost
cine-blue-hour@7315     PLACEHOLDER fam=Inter
```

**Os 10 sao `.captions__placeholder` -- o NOSSO estado vazio.** E o gerador escrevia a linha **incondicionalmente**, para os 25 temas (`gen_cinematic.py:880`), enquanto o italico da LEGENDA, tres linhas acima, e lido do ZIP (`t['italic'] = 'italic' in caption_class`, `:456`, a partir de `themes.ts`). Nenhum zip desenha um placeholder: o italico ali e invencao nossa.

**Ficheiros reais no @fontsource (medidos, nao inventados):**

| familia | ficheiros `*italic*` no pacote | `latin-400-italic.woff2`? |
|---|---|---|
| Inter | 126 de 252 | **existe** |
| Jost | 54 de 108 | **existe** |
| Manrope | **0** de 84 | nao existe |
| Outfit | **0** de 96 | nao existe |

**Decisao: (b), com precisao -- o placeholder passa a ECOAR a resposta do design em vez de a inventar.** O italico do placeholder passa a ser condicional ao italico que o proprio zip declara na legenda:

```python
    a('%s .captions__placeholder {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-caption);')
    if toks['__italic']:
        a('  font-style: italic;')
    a('  opacity: 0.55;')
    a('}')
```

Porque esta e a forma certa e nao a remocao cega: onde o zip italiza a legenda (warm-hour, motel-glow, last-reel, dustlight, rooftop) o placeholder CONTINUA italico -- e essas familias sao Fraunces e Lora, **ambas empacotadas com italicos reais** -- e em todos os outros 20 temas ele fica direito. Nao se empacota um ficheiro para satisfazer um pedido que ninguem fez (isso seria criar peso morto novo), e nao se pede uma face que nao existe.

**Fechado:** 7 dos 25 temas perderam a linha (`midnight-rain`, `velvet-dusk`, `study-light`, `tideline-body`, `paper-moon`, `quiet-streets`, `north-fog`), o que inclui **os 5 do Outfit** -- o `cinematic.css` foi de 350 487 para 350 326 B (161 B, exactamente as 7 linhas CRLF). Os 3 temas com legenda italica do SHIP ficaram intactos, e o `themes.js` saiu byte a byte igual (`589AA22B39DB67A8`).

### 3.1 O LIMITE REAL, e onde ele esta

**Restam 5 pedidos sintetizados, e NAO estao no meu escopo de escrita.** Os 15 temas `extra` (cafe, tideline, rainglass, fieldnotes, dustlight, rooftop, analog, shelves, ember, rainline, blue-hour, cellar, linen, reading-hour, last-train) recebem o CSS de dois modulos de dados que **tambem escrevem o italico incondicionalmente**:

```
_main/_design-lane/cine_extra_c1.py:455   w('  font-style: italic;')   (dentro de '@S@ .captions__placeholder {')
_main/_design-lane/cine_extra_c2.py:465   w('  font-style: italic;')   (idem)
```

Os 5 restantes sao `cine-rainglass`, `cine-fieldnotes`, `cine-blue-hour` (Inter), `cine-rainline` (Manrope) e `cine-last-train` (Jost). **A correccao e a mesma linha, condicionada ao `italic` do design, em cada um desses dois ficheiros** -- que nao posso tocar. O ARM C do portao imprime-os como `OPEN`, com o `file:line` que os emite, a cada corrida.

**E o limite do proprio pacote, dito sem o esconder:** o **Outfit e o Manrope nao tem NENHUM italico** no @fontsource (0 ficheiros). Se algum dia um zip PEDIR italico nessas familias, nao ha ficheiro real para empacotar -- seria preciso outro desenho ou outra familia, e isso e uma decisao do dono, nao um defeito a esconder com um obliquo sintetizado.

**Controlo (ARM C do portao):** `--neg-arm` restaura a linha incondicional na copia do gerador e regenera -> `M3 ... RED as required on ['C(30)']`.

---

## 4. GATE -- `_main/base-themes-oracle.py` (novo), com controlo que muta o GERADOR e REGENERA

```
$env:TMPDIR='I:/cc-tmp'; py -3 _main/base-themes-oracle.py --neg-arm
== BASE-THEMES ORACLE ==
ARM A (D5) -- class universe: 134 class(es) from panel.html + 12 module(s)
    GREEN every class selector matches a class the live document can carry
    GREEN .status__hint: 0 selector(s) in the six files
    GREEN .history__source: 0 selector(s) in the six files
    GREEN .reveal-button--danger: 0 selector(s) in the six files
    GREEN .chrome__key: 0 selector(s) in the six files
ARM B (D6) -- 528 declared token(s) checked against 160 reader site(s)
    GREEN no undeclared dead token in the six files
    OPEN  --size-meta ... (declarado, com os numeros da seccao 2.1)
    OPEN  --space-4 ... (declarado)
ARM C (D4) -- 16 bundled famil(ies); 11 rule(s) with font-style: italic resolved
    GREEN every italic request of theme-1..5 / panel-designs / the 10 SHIP cinematic themes has a real bundled face
    GREEN placeholder italic only where the zip italicises the caption
    OPEN  5 italic request(s) and 13 placeholder-echo(es) remain, ALL in themes emitted by the two extras modules (cine_extra_c1.py:455, cine_extra_c2.py:465)
ARM D (RULE 10) -- a fresh run of each generator from a sha256-verified copy
    GREEN theme-1..5.css, panel-designs.css, cinematic.css, fonts.css all reproduced byte-for-byte
VERDICT: PASS

== CONTROL: the same predicates against MUTATED GENERATOR COPIES ==
M1 D5 -- a dead class selector re-inserted               -> RED as required on ['A(10)']
M2 D6 -- a dead token re-declared                        -> RED as required on ['B(10)']
M3 D4 -- the unconditional placeholder italic restored   -> RED as required on ['C(30)']
M4 INERT -- a comment added (must stay GREEN on A/B/C)   -> GREEN (inert, as required)
M5 RULE 10 -- a generator mutation that moves the bytes  -> RED as required on D (theme-1.css,...,panel-designs.css)
CONTROL VERDICT: PASS
```

**A forma do controlo e a que o brief pediu, e e a mais forte:** cada mutante e uma COPIA do GERADOR em `I:/cc-tmp` (o `__file__` continua a apontar para o repo, para as ENTRADAS resolverem), **regenerada para um scratch**, e o MESMO predicado corre contra a SAIDA do mutante. O M4 e o que prova que os arms medem a RELACAO e nao um hash: um comentario a mais no gerador muda TODOS os bytes e deixa A/B/C verdes. O M5 prova o inverso no ARM D: uma mutacao de um valor (`--radius-sm: {radius_sm} /*moved*/`) quebra a reproducao dos SEIS ficheiros.

**Um erro do proprio portao, apanhado e corrigido aqui:** a primeira versao do ARM C construia o conjunto dos temas do SHIP sem aplicar o `RENAME` do gerador (`tideline` -> `tideline-body`), e por isso acusava o EXTRA `cine-tideline` de ser um tema do SHIP -- um falso RED. O portao le agora o `SHIP` **e** o `RENAME` do gerador (medicao, nao lista fixa). Segundo erro, tambem corrigido: o ARM C corria sobre a populacao ERRADA nos mutantes (o `cinematic.css` publicado, em vez do gerado), o que fazia o mutante INERTE aparecer vermelho.

**Portoes vizinhos re-corridos depois das minhas edicoes** (nenhum lancado, todos em processo):

| portao | resultado |
|---|---|
| `node _main/scope-leak-oracle.js` | **PASS** -- 9 folhas, 0 membros sem scope |
| `node _main/fonts-fidelity-oracle.mjs` | **PASS** (A/B/C/D) -- e confirma o orfao do IBM Plex Mono 700 |
| `py -3 _main/cine-themes-oracle.py` | **PASS** |
| `py -3 _main/cinematic-designs-oracle.py` | **PASS** |
| `py -3 _main/zipc-designs-oracle.py` | **PASS** |
| `node _main/theme-tune-oracle.js` | **FAIL 4/64** -- ver 2.2: PINAVA o defeito que eu fechei, e o re-baseline esta fora do meu escopo |

---

## 5. O QUE NAO FECHEI (e o que isto custa)

1. **`theme-tune.js:41-52` + o ARM 8 do `theme-tune-oracle.js`** -- ficaram obsoletos com o meu fecho (4 arms vermelhos). Fora do meu escopo; a correccao esta descrita em 2.2.
2. **5 pedidos de italico** nos 15 temas `extra` (`cine_extra_c1.py:455`, `cine_extra_c2.py:465`) -- fora do meu escopo; a correccao e a mesma linha condicional.
3. **`--size-meta`** (10 declaracoes mortas) e **`--space-4`** (5, so na lane A) -- declarados no portao como `OPEN`, com os numeros que explicam porque nao os toquei.
4. **`--strip-chrome`** (`panel.css:73`) -- a auditoria mandou so reportar. Reportado.
5. **`app/panel/fonts/ibm-plex-mono-latin-700-normal.woff2`** -- orfao pre-existente (14 956 B que nenhum `@font-face` declara). Reportado; nao apagado (fora do escopo).
6. **NADA disto foi visto a pintar.** Nenhum browser foi lancado (regra da lane): as afirmacoes sao sobre BYTES e sobre a RELACAO gerador->bytes. A prova de que o obliquo sintetizado desapareceu do ecra exigiria um render, e nao o fiz.
7. **Nao medi o que o dono ve.** As mudancas de D6 sao, por construcao, sem efeito visual (uma declaracao que ninguem le nao pode mudar nada) e a de D4 tira uma linha que o browser so podia satisfazer fabricando uma face; mas isso e um argumento, nao uma medicao de pixeis.

## 6. Pins (2026-10-13, para o proximo a mexer)

| ficheiro | bytes | sha256 |
|---|---|---|
| `app/panel/themes/theme-1.css` | 28 973 | `BBD3D7FA94EFCA6F26B6A7EAEE35D2FE4075836ACC812B76082EF9642C0C099A` |
| `app/panel/themes/theme-2.css` | 29 191 | `CF69B09DF46AAAD2E84E34B5EA4174D5324DBE8E8D932B06336AC8F3A492E745` |
| `app/panel/themes/theme-3.css` | 29 341 | `DCBD6B10B311893C719C28D451861E9DC3A459E5CC6AB3CC72F7CC990D1E2A71` |
| `app/panel/themes/theme-4.css` | 28 274 | `6BB9A5BBC801592CCA6992BA5334BCFFB8C9B7CA61FA63737C5C63AE6E196232` |
| `app/panel/themes/theme-5.css` | 29 297 | `697F811B0CC109257A2D16A81A7F5C6B6934FFFDE5819B02F61BCB1C72C4E77C` |
| `app/panel/themes/panel-designs.css` | 139 610 | `32592C7661014F95C20D53BE2D73B10FA57BFA47AF1A10F48C09AA5639182400` |
| `app/panel/themes/cinematic.css` | 350 326 | `9B0A50DAF0874AAEAAF5FA5539902628C2C02306EAD00B1B3D8CC250AB380E41` |
| `_main/_design-lane/gen_themes.py` | 164 970 | `E088712A5354986B3BC4EC8E5E1188FD00C04D8D35191013DC6A5EE8A211DAEC` |
| `_main/_design-lane/gen_cinematic.py` | 84 158 | `A09208F95B9F3BBF35ADF7061D495CD516A711274B02B03932E9737EC6C8B91A` |
| `_main/base-themes-oracle.py` | 29 805 | `A1EAB4FB94DA24F1A800778B57394DEC52A1E7F2778C16099DC7AC4FA6D49CB3` |

**Estado do `gen_cinematic.py` ANTES do meu gesto (o aviso do brief pedia-o):** 82 760 B / `EC3AA8D3F235C593EC34A965BF069FACD19970C43BC95F975C29A67D603EF907`, mtime 2026-10-13T02:04:59Z; `cinematic.css` 350 487 B / `DC35622800DA3AE7F2B7AB531B720307BD7666ED6933005860F227E6C386C5B3`, mtime 2026-10-13T02:05:31Z. **Os bytes de produto NAO se moveram sozinhos durante esta lane** (o mtime do `cinematic.css` ficou em 02:05:31Z ate eu o escrever as 02:36:28Z), e a regra 10 provou que o gerador e o produto estavam em sincronia antes de eu editar. O unico movimento de bytes que eu nao causei foi o do meu proprio primeiro ensaio de regra 10 (o download de backdrops, §0) -- que escreveu apenas em `I:/cc-tmp`.

