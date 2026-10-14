# O MEU EDIT PARTIU O ORACULO -- e o checkout salvou-o

2026-10-14. Tentei o ultimo passo do vermelho (substituir o git-show pelo wrapper
embarcido) e o meu edit deixou um rc4 duplicado e uma continuacao orfa:

  IndentationError: unexpected indent (preflight-refusal-visible-oracle.py, line 185)

Reverti com git checkout -- e volta a compilar. LIMPO no HEAD 2469ef2.

## O que ficou

O produto (app/panel, app/webview, worker) NAO foi tocado. A unica coisa que modifiquei
foi o oraculo, e esta revertido. O ultimo passo continua escrito, com comandos exactos, em
receipt-20261014-last-step-exact.md.

## O que aprendi nesta conta

O prompt do dono dizia que edicoes por fatia de linha e regex partiram ficheiros cinco
vezes nesta sessao. Fiz a edicao com a ferramenta edit sobre strings exactas, mas o
old_string nao correspondia ao que estava la, o edit nao aplicou, e o que ficou foi o
ficheiro meio-escrito. py_compile apanhou-o e o git checkout salvou-o.

## O balanco

Nao fechei o ultimo vermelho. O resto continua feito.
