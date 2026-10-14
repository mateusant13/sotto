# O ULTIMO PASSO, ESCRITO PARA SER MECANICO

2026-10-14. O controlo do arm 4 do preflight-refusal-visible-oracle.py precisa de duas coisas:

1. SEM PIPE. Ja feito e medido: com run_wrapper(..., pipe=False) o braco deu rc=2 e
   caller text=0 B. Isso refutou a minha propria nota anterior, que dizia que nenhum
   controlo podia ficar cego sob este harness -- o texto vinha do pipe.

2. SEM RECIBO NO LOG. Falta. O ficheiro embarcido de 2026-10-06 tambem carrega o
   run-cmd-log-append.py, e o braco leu log delta=+52 B com o delta a nomear a flag. O
   oraculo trata um recibo nomeado como prova de que o controlo ja tem a cura.

## O passo exacto

a. Reaplicar o pipe=False no run_wrapper (esta no receipt-20261014-control-got-blind.md,
   mas eu reverti o oraculo ao HEAD quando o deixei a meio).

b. O controlo nao pode chamar o run-cmd-log-append.py. Como o ficheiro de 2026-10-06 o
   chama, ou se acrescenta um ramo ao oraculo que retire essa linha, ou se escreve o
   controlo a mao uma vez e se guarda embarcido, com apenas o --check-args sem
   redireccionamento e o exit /b do rc.

c. Correr py -3 _main/preflight-refusal-visible-oracle.py e esperar VERDICT PASS.

d. So depois disso a bateria deve dar 89/89, e so entao os quatro fixes de P0 ficam
   cobertos por bateria verde.

## O que nao afirmo

Nao o acabei. A bateria continua 88/9.
