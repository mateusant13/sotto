# RETRACCAO: o meu gate por-tema estava ERRADO, e os oraculos existentes tinham razao

Escrevi o `_main/token-orphans-per-theme.py` para medir tokens declarados num tema e
lidos pelas regras DESSE tema. O resultado foi absurdo: 25 de 25 temas com ~30 orfaos
cada, incluindo `--font`, `--text`, `--radius`, `--mono`, `--size-small`.

O ERRO: apliquei o criterio errado. Um tema DECLARA tokens; a folha base (panel.css) e
as outras folhas CONSOMEM-nos. Um token declarado num tema e lido FORA dele NAO e um
orfao -- e exactamente como o sistema de desenho funciona. O criterio correcto, e o que
os oraculos cine-themes C1 e cinematic-designs C ja usam, e: lido em QUALQUER sitio.

Pelo criterio correcto:
  --cine-scrim ....... lido 12 vezes  -> NAO e orfao
  --size-chrome ...... lido 0 vezes   -> ERA orfao, e foi curado (tem leitor no
                        .captions__hint)

Os 13 temas que declaram `--cine-scrim` sem o lerem nas SUAS regras sao divida real,
mas cosmetica: uma variavel sem leitor nao custa um pixel nem uma regra, custa bytes.
E a declaracao e UNIFORME -- o gerador emite-a para os 25 no mesmo bloco, e o dialogo
de ajuste do dono conhece-a. Torna-la condicional para 13 nao compra nada mensuravel.

DECISAO, com o numero que a justifica: FICA. 12 de 25 consomem-na, a declaracao e
uniforme, e o custo de a remover para 13 (gerador condicional, mais um ramo para
manter) e maior do que os bytes que poupa. O que NAO pode ficar e um token lido por
NINGUEM -- e esse, o --size-chrome, foi curado e esta gateado.

O instrumento errado foi APAGADO. Fica a licao, que e a mesma desta sessao toda: um
instrumento com o criterio errado nao mede menos -- mede outra coisa, e com confianca.
