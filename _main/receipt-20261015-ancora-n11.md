# A ANCORA DO MUTANTE N11 FOI MOVIDA, E OS 11 MUTANTES VAO A VERMELHO

O ultimo vermelho da bateria era o three-overlays-oracle: `SETUP ERROR: mutant anchor
absent in panel.html` -- o mutante N11 (que prova que o D5 ainda discrimina) usava como
ancora o `<span class="history__label">` que eu removi quando o dono mandou tirar o
botao de transcript.

A CURA: mover a ancora para `.history__path` -- o botao da pasta, que ainda existe no
markup e continua a ser um CONTROLO da gaveta, que e a mesma classe de ancora. O que o
mutante prova nao mudou: se o botao do transcript reaparecer no markup, o D5 tem de
ficar vermelho.

MEDIDO:
  a vivo .............. VERDICT PASS
  braco negativo ...... N11 the transcript button comes back -> D5 RED
                        NEG-ARM VERDICT: PASS -- every mutant went RED

E os 11 mutantes, nao so o N11: N1 a transparencia volta, N2 o overlay ganha fundo,
N3 a history deixa de estar escondida na barra, N4 o botao da transparencia volta,
N5 a barra encolhe, e os restantes. Todos RED.

O que esta feito, e o que falta:
  FEITO   os 5 vermelhos que a minha remocao do rotulo causou, um a um:
          zipc-designs (verde), cine-themes (verde), cinematic-designs (verde),
          o orfao --size-chrome (tem leitor), o three-overlays (ancora movida).
  FALTA   correr a BATERIA INTEIRA e confirmar 0 vermelhos -- que e a prova de que
          os cinco fecharam juntos e nao um as custas dos outros.
