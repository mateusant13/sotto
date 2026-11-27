# Recibo F6 — `codeintel full` sobre o sotto

Medido em 2026-11-27 pela lane `lane-gravador`, com o instalador
`H:/codeintel-worktrees/triad-milestones-20261105`.

## Comando e resultado

```
cd H:/codeintel-worktrees/triad-milestones-20261105
py -3 -m codeintel full "H:/sotto" --scope _main/_libs --json > G:/Temp/f6-sotto.json
rc=2
```

```
verdict            cannot-measure
findings           58
population_counts  {scope: 58, outside-scope: 0, scratch: 0}
cannot_measure     1
detectors_completed 18        detectors_pending []
```

## O escopo teve de ser reduzido, e isso e' medicao

`--scope _main` tem **3043 `.py`** e estourou o prazo declarado de 400 s:

```
rc=124   (timeout, nenhum JSON produzido)
```

`_main/_libs` (175 `.py`) e' o maior subdiretorio que mede dentro do teto. Isto nao e' preferencia:
e' o limite de tempo do instrumento neste repo, publicado junto do numero.

## Por que o veredicto e' `cannot-measure` com 58 achados

Um detector recusando rebaixa o documento inteiro:

```json
{"detector": "wired_read",
 "reason": "RuntimeError importing codeintel.wired_read: codeintel.wired_read population is
            175 files (cap 8); refuse instead of reporting a prefix scan as complete"}
```

O `wired_read` tem populacao propria limitada a **8 arquivos**. Recusar em vez de publicar varredura
parcial e' correto; o efeito e' que o veredicto unico deixa de distinguir "os outros 17 detectores
acharam 58 coisas" de "nada foi medido". Os 58 achados estao no JSON.

## O que faltava neste repo -- e o que foi fechado depois desta medicao

Esta medicao e' de `19:48`; a matriz foi fechada no mesmo dia, com o numero medido:

- `harness/angulos.tsv` **existe** desde 2026-11-27 e e' um HARDLINK de `harness/angles.tsv` (mesmo
  inode, sha256 `118fc576c1d5bd32` nos dois nomes): o censo da frota le' `angulos.tsv`, o gerador do
  AGENTS.md e as skills leem `angles.tsv`, e uma copia derivaria. 33 linhas de dados + 5 `HOLE:`
  declarados.
- `scripts/revival_gate.py` passou a ser o entrypoint em codigo: positivo `REVIVAL GATE PASS` rc 0,
  `--neg-arm` rc 1 com 4/4 mutantes apanhados. Recibo:
  `_main/receipt-20261127-f6-revival-gate-and-codeintel.md`.
- A afirmacao "`--scope _main` estourou 400 s" desta folha continua valida e NAO foi refeita; a outra
  fatia medida foi `--scope worker --max-population-files 4000` (populacao 319, 17/18 detectores,
  82,27 s, rc 2).

Placar dos 6 projetos: `H:/!gravador/revival/f6-frota.md`.
