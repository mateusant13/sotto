# Recibo — o censo do disco do Sotto e o que foi removido (2026-11-01)

Ordem do dono, verbatim: *"entenda todo espaço em disco que o sotto consome e remove tudo que e inutil."*

Instrumento de cada linha abaixo (tudo medido nesta maquina, hoje): `du -sh`, `git count-objects -vH`,
`git lfs prune --dry-run`, `git worktree list`, `git verify-pack -v`, `df -h`.

## O que o Sotto ocupava, medido (H:\sotto = 16 GB no inicio)

|onde|tamanho|o que era|
|---|---|---|
|`.git/objects`|4,7 GB|um unico pack de 5 008 029 958 B|
|`.git/lfs`|3,4 GB|11 objectos LFS, **0 ficheiros LFS no checkout** (`git lfs ls-files` = 0)|
|`_main`|3,5 GB|venvs, modelos de diarizacao, sondas, 218 snapshots de mutantes|
|`_moved`|2,6 GB|a arvore `aireplay` — rastreada (928 ficheiros), morta para o produto|
|`app`|820 MB|o produto|
|`node_modules`|401 MB|dependencias (git-ignored, em uso)|
|`docs`|199 MB|189 MB eram RENDERS de design|
|`.codeintel`|167 MB|indice (regeneravel, em uso)|

## O que foi removido (medido antes e depois)

|alvo|antes|depois|porque e' inutil|comando|
|---|---|---|---|---|
|`.git/lfs`|3,4 GB|4,4 KB|nenhum ficheiro LFS no checkout; os 11 objectos sao de refs antigas|`git lfs prune`|
|`docs/design-audit-20261021`|95 MB|0|renders de design, `git-ignored` **de proposito** (o `.gitignore` diz: "reproducible from the sources next to them")|`rm -rf`|
|`docs/design-intake/demos` + `rendered`|89 MB|0|idem|`rm -rf`|
|`_main/_gaps-g1-after-*` (218 directorias)|254 MB|0|snapshots de mutante (copias de `_main`+`app`); o git ja guarda a historia|`rm -rf`|
|11 worktrees dormentes|649 MB|0|0 ficheiros tocados nos ultimos 3 dias, `dirty=0`; **branch e commits ficam** no repo|`git worktree remove`|
|`_main/_epvenvs`|1,9 GB|0|venvs `python -m venv` + pip (`onnxruntime`); reconstruiveis pela linha registada em `_main/receipt-execution-providers.md:191`|`rm -rf`|
|`_main/_venv-diar`|12 MB|0|idem|`rm -rf`|
|`_main/_skin-lane/shots`|16 MB|0|screenshots de uma lane de design, nao rastreados|`rm -rf`|

**Total devolvido: ~6,4 GB.**

Worktrees removidas (branch preservada): `ArbV9`, `clipasr`, `cut4`, `engproc`, `fixcut`, `ParseFix`,
`ReplyFix`, `specs57`, `stripctl`, `stripsh`, `wgcunb`. **Mantidas** por terem trabalho nao commitado:
`ArbV8` (dirty=11, 4 commits acima de `origin/main`), `audioclip`, `AuthFix`, `StdinV9` — e a
`I:/wt/CutVerbI2`, que vive fora desta raiz.

## O que NAO foi removido, e a razao medida

- **`_moved/aireplay` — 2,0 GB, rastreado (928 ficheiros).** O produto nao o usa: `git grep` sobre
  `app/` e `worker/` devolve 0 linhas (ja' medido em `_main/PARITY-GAP.md`). O que impede a remocao nao
  e' uso, e' **um portao**: `_main/channel-class-site-oracle.py` pina linhas DENTRO dessa arvore
  (`src/pipeline/share_export.py:119`, `share_gate.py:123`, `share_gate.py:661`). Apagar a arvore deixa
  esse oraculo vermelho sem que nada de vivo tenha mudado. **Decisao pendente do dono**: aposentar o
  oraculo (e o passo dele na bateria) para libertar 2,0 GB, ou manter a arvore como referencia citada.
- **`.git/objects` — 4,7 GB num so pack.** `git verify-pack` mede cinco blobs de **1179 / 922 / 658 /
  639 / 514 MB** na historia. Nenhum `gc` os remove: so' uma reescrita de historia (`filter-repo`) os
  tira, e isso muda **todos** os SHAs, invalida as worktrees e exige force-push numa branch
  rastreada. Nao se fez. O `git gc --prune=now` foi corrido para largar o que era inalcancavel.
- **`_main/diar-models` — 764 MB.** Pesos da diarizacao, fluxo VIVO do repo (separacao de falantes).
  *"ausente do worktree nunca e' prova de ausencia"* — e aqui e' o contrario: estao presentes e usados.
- **`_main/_redux-long` 232 MB, `_main/_render-1710` 70 MB, `_main/_design-lane/zips` 85 MB,
  `_main/design`** — material de sonda e renders de design. Ficam: e' conteudo do repo (os zips e o
  `_render-1710` estao ate' rastreados) e nao ha prova de que sejam regeneraveis sem custo.
- **`.codeintel` 167 MB** — indice derivado, usado pelo consultgpt; regeneravel mas em uso.
- **`_main/webview-run.log` 45 MB** — log da instancia VIVA. Ha rotacao no shell
  (`sotto_webview.py:1224`); nao se toca num ficheiro aberto por outro processo.

## Espaco livre medido no fim do censo

`H:` 58 GB · `I:` 60 GB (99 % usado, a maquina do dono esta' degradada — ver AGENTS.md) · `G:` 38 GB.
