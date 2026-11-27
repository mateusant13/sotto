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

## O que falta neste repo

`harness/angulos.tsv` nao existe aqui (nem em VOD.RIP). E' a matriz de angulos falsificadores que
gravador (122 L), codeintel (26 L), superharness (11 L) e !watcher (45 L) ja tem.

Placar dos 6 projetos: `H:/!gravador/revival/f6-frota.md`.
