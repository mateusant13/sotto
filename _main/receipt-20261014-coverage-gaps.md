# AS 18 LACUNAS DE COBERTURA -- o trabalho concreto que a regra F1 pede

Medido por `py -3 _main/cobertura-oracle.py` em 2026-10-14: **34 areas mapeadas,
16 cobertas** por um instrumento que CORRE na bateria, **18 sem porta nenhuma.**

O commit `b2d0f92` tem o titulo errado (diz 13) porque a primeira leitura do output estava
truncada; este ficheiro e a lista completa e medida.

Cada linha abaixo e uma area que pode ser mudada HOJE sem nada para a apanhar. Nao sao
desculpas -- sao o backlog que a regra F1 cria.

| area | o que la vive |
|---|---|
| JS<->Python surface loop guard | a guarda que fechou o loop do PC travado (medido p99 264/s) |
| buttons lane (size e visibilidade) | os botoes pequenos e visiveis que o dono pediu |
| caption line fidelity | a legenda tem de ser a linha que o worker fechou |
| caption overlay independence | a legenda nao pode depender do painel |
| emit queue bound | a fila de legendas sem limite -- RISCO ABERTO CONHECIDO |
| fonts fidelity | as fontes do .zip |
| hotkey / Alt+C cycle | o Alt+C que estava com codigo morto (panel_mode) |
| log flood census | o censo do flood de 4,18 M linhas / 97 por cento |
| log rotation | a rotacao que provou 847 MB -> 16 MB |
| panel hide gate at startup | o gate que impede o painel de aparecer sozinho |
| panel state write (atomic) | o temp fixo que dava 1 145 063 falhas de escrita |
| queue_drops whitelist | a whitelist que estava a filtrar queue_drops |
| second pass (M3) opt-in | a segunda passagem que custava 50,9 por cento |
| theme chrome (footer labels) | o historico/em curso que o dono mandou tirar |
| theme switching | trocar de tema |
| themes: design fidelity (zip) | cada tema igual ao .zip |
| themes: light census | nenhum tema branco |
| wrapper pre-flight (run.cmd exit) | o contrato de saida do run.cmd -- onde viveu o rc 120 |

## Como fechar cada uma

Tres passos, e o terceiro e o que fez a diferenca nesta sessao:

1. escrever o oraculo da area (ou apontar o que ja existe);
2. por-lhe um BRACO NEGATIVO -- um mutante que o faca ficar RED, senao ele nao
   distingue a cura da ausencia de teste;
3. por a linha na `instruments-battery.mjs` para que CORRA.

Um oraculo que existe mas nao esta na bateria e decorativo, e o cobertura-oracle
diz exactly isso.
