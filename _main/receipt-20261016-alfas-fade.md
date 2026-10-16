# F5/F6: DUAS ALFAS A MULTIPLICAR -- e uma regra duplicada

## O que o audit mediu

    linha anterior:  cor 0,36 x opacity 0,42  = 0,15 efetivo   (contraste p50 1,07 sobre branco)
    creditos:        cor 0,52 x opacity 0,55  = 0,29 efetivo   (contraste p50 1,04)

Duas alfas no MESMO elemento multiplicam -- nao somam. O resultado era texto praticamente
invisivel, e o audit chamou-lhe o defeito de legibilidade mais grave da legenda.

## O estado em que encontrei

  * `panel.css` JA tinha passado a cor para `rgba(232, 238, 246, 1.0)` -- portanto a
    MULTIPLICACAO ja nao acontecia. O que sobrava era UMA alfa: 0,42 e 0,55.
  * MAS a regra do `prev` estava DUPLICADA no `zip-overlay.css`: dois blocos
    `body[data-float="on"] .caption-float__prev` com o mesmo `opacity: 0.42 !important`
    (um deles tambem punha a fonte serifada). Regra repetida e divida: quem editar uma
    acha que mudou o comportamento e a outra ganha.

## A cura

  * o bloco duplicado SAIU, com a nota a dizer porque;
  * a alfa unica do `prev`: 0,42 -> 0,62
  * a alfa unica dos creditos: 0,55 -> 0,72

O valor sobe porque a ordem do dono [41856] e *visiveis o suficiente pro usuario*, e 0,42
sobre video e o que o audit mediu a 1,07 de contraste -- um borrao. 0,62 mantem a linha
anterior claramente mais quieta que a viva (1,0) sem a apagar.

MEDIDO no ficheiro depois da mudanca: `opacity: 0.42` aparece UMA vez e so em prosa (o meu
comentario); as regras ficam `opacity: 0.62` e `opacity: 0.72`, uma cada.

## O que NAO esta medido

O CONTRASTE depois da mudanca. O audit mediu-o por pixeis (render com e sem texto, diferenca
de luminancia); eu nao repeti essa medida. O que esta provado e a causa (duas alfas), a
duplicacao removida, e que agora ha uma so alfa com valor mais alto. **A re-medicao do
contraste e a prova que falta.**
