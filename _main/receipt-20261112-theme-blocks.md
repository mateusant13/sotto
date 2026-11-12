# RECIBO — os cinco ficheiros de tema que só existiam por nome (2026-11-12)

Medido nesta árvore hoje, com a máquina quieta. Onde diz `PASS`, o comando está ao lado e foi
corrido nesta sessão.

## 1. O defeito

`_main/spec-coverage-oracle.py` publicava `nome_apenas=5`: cinco ficheiros de produto apareciam na
especificação **só pelo nome do basename**, sem bloco próprio. São eles a camada que mais muda na
tela do dono e a única que ele pediu inteira (as 16 famílias de tipos e os 15 painéis dos três zips).

```
$ python _main/spec-coverage-oracle.py
  NOME-APENAS  app/panel/themes/fonts.css
  NOME-APENAS  app/panel/themes/panel-designs.css
  NOME-APENAS  app/panel/themes/panel-designs.js
  NOME-APENAS  app/panel/themes/zipc-panels.css
  NOME-APENAS  app/panel/themes/zipc-panels.js
SPEC-COVERAGE docs=16 ausentes=0 nome_apenas=5 classes_sem_seccao=0
SPEC-COVERAGE VERDICT: PASS          <- o portão aceita nome-apenas; a dívida é de cobertura, não de código
```

## 2. O que foi escrito

Cinco blocos em `docs/spec/13-MODULES.md`, no formato da casa (o que faz / quem o chama / o que
escreve-lê / quando falha / evidência), cada afirmação com a linha que a prova:

| ficheiro | o que o bloco fixa | linha que prova |
|---|---|---|
| `fonts.css` | 70 `@font-face`, 16 famílias, `latin` + `font-display: swap`, 1 345 304 B de `.woff2` para as 70 faces | `fonts.css:27`, `:29`, `panel.html:48` |
| `panel-designs.css` | 5 painéis `pd-*`, adiados pelo `lazy-assets` (`NEEDS['pd-']`), cluster de controlos em `:649`/`:2947` | `lazy-assets.js:83`, `panel.html:1269` |
| `panel-designs.js` | manifesto-fragmento de 5 entradas, `push` com guarda, `groupLabel` lido pelo switcher | `panel-designs.js:33`, `:74`, `theme-switcher.js:199` |
| `zipc-panels.css` | 10 painéis, no `<head>`, construídos só do DOM existente; o defeito que fecha (10 recolorações de 1 esqueleto) e o controlo `--profile legacy` byte a byte | `zipc-panels.css:67`, `:2200`, `panel.html:71` |
| `zipc-panels.js` | manifesto-fragmento de 10 entradas, `push` com `Array.isArray`, ordem dos três manifestos | `zipc-panels.js:91`, `:101`, `panel.html:1271` |

## 3. Duas dívidas medidas ao escrever (e uma correção no bloco agregado)

1. **O agregado dizia `71 @font-face`.** Medido por `ast`-equivalente (`re` sobre os blocos): são
   **70** faces e **71** ficheiros `.woff2` em `app/panel/fonts/`. O 71.º é
   `ibm-plex-mono-latin-700-normal.woff2`, sem `@font-face` nenhuma — peso morto de uma face.
   O texto agregado foi corrigido com os dois números e o nome do ficheiro.
2. **`fonts/LICENSE-NOTES.md` não existe.** O cabeçalho do `fonts.css` manda lê-lo para as licenças
   (as 16 famílias são SIL OFL 1.1, que exige atribuição); medido: não está em `app/panel/fonts/`
   nem em `_main/_design-lane/`. Fica escrito no bloco como dívida, não como facto resolvido.

## 4. Portões re-corridos depois das edições

```
$ python _main/spec-coverage-oracle.py
SPEC-COVERAGE docs=16 ausentes=0 nome_apenas=0 classes_sem_seccao=0
SPEC-COVERAGE VERDICT: PASS

$ python _main/spec-coverage-oracle.py --neg-arm
NEG-ARM fantasma       CAUGHT  (app/webview/_modulo-que-ninguem-escreveu.py)
NEG-ARM classe-sem-doc CAUGHT  (app/panel/skins/)
SPEC-COVERAGE NEG-ARM PASS

$ python _main/spec-citations-oracle.py
SPEC-CITATIONS: docs=16 citacoes=1477 sem_ficheiro=0 fora_de_alcance=0 index_ausente=0 fora_da_tabela=0
SPEC-CITATIONS VERDICT: PASS
```

A primeira volta do `spec-citations` deu **FAIL** com uma citação minha sem caminho
(`fonts.css:15`, que o oráculo lê como ficheiro inexistente no repo): corrigida para
`[CODE] app/panel/themes/fonts.css:15` — o defeito era do texto novo, e o portão apanhou-o na hora.

## 5. Números da especificação, re-medidos hoje (não citados)

| o quê | número | como |
|---|---|---|
| documentos | 15 (+ `README.md`) | `glob docs/spec/*.md` |
| linhas | **5 385** | `len(t.splitlines())` por ficheiro |
| `[CODE]` | **1 360** | `re.findall(r'\[([A-Z]+)\]', t)` |
| `[MEASURED]` | **173** | idem |
| `[INFERENCE]` | **62** | idem |
| `[UNKNOWN]` | **68** | idem |
| citações resolvidas | **1 477** em 16 documentos, 0 sem ficheiro | `spec-citations-oracle.py` |

`docs/spec/STATUS.md` foi atualizado com estes números e com a linha de citações; os dois que já
estavam certos (`spec-scale`, `battery-wiring`, `battery-record-pairing`, `battery-budget`) foram
re-corridos e conferem.

## 6. O que NÃO está verificado

* Nenhum destes cinco blocos descreve pixel observado: a afirmação sobre o que o olho vê continua a
  exigir página renderizada, e o instrumento que a mede é o `panel-themes-oracle.mjs`, que não corre
  nesta rodada.
* O `.woff2` órfão e o `LICENSE-NOTES.md` ausente ficam **medidos e escritos**; nenhum dos dois foi
  corrigido — apagar um ficheiro de fonte e escrever um ficheiro de licença são decisões do dono, não
  desta lane.
