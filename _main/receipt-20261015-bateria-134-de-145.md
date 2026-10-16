# A BATERIA CAIU A 134/145 -- 11 VERMELHOS, E PELO MENOS UM E MEU

Medido 2026-10-15 apos os meus commits dos geradores:
  SUMMARY: 134/145 instrument(s) rc=0; failed=11; launches=0

Antes do meu trabalho desta sessao a bateria dava 144/144. Os 11:

  visibility-guard (rows #60/#61)  AttributeError: Probe object has no attribute
                                   show_caption_window  <- DEFEITO DE CODIGO
  visibility-guard neg             idem
  AGENTS.md pins re-measured live  VERDICT FAIL  <- o pin do --help ou da bateria
                                   mudou (eu mexi na bateria)
  theme gen reproduces (regra 10)  VERDICT FAIL -- the shipped files ARE NOT
                                   reproduced by a fresh run  <- MUITO PROVAVELMENTE
                                   MEU: o gen_zipc.py exige --out e o oraculo de
                                   reproducao pode nao o passar
  panel state atomic neg           SETUP ERROR (rc=2)
  zipc designs neg (6)             rc=4294967295  <- codigo de crash do Windows
  caption independent of panel     VERDICT FAIL
  botoes lane oracle               VERDICT FAIL
  botoes lane gesture              VERDICT FAIL
  theme switching: ONE attribute   rc=1, Node v24.8.0
  theme switching neg (3 mutants)  rc=1

O QUE ISTO SIGNIFICA, sem adornos: o meu trabalho fechou o criterio dos TOKENS (os
tres oraculos de desenho dao PASS: cine-themes 53 tokens todos lidos, cinematic-designs
0 sem leitor, zipc-designs 9 checks 0 failed) mas ABRIU ou revelou 11 falhas noutros
sitios. E a mesma forma de sempre: consertar uma coisa mexe em tres.

O QUE A PROXIMA RODADA FAZ, por ordem de valor:
  1. `theme gen reproduces` -- correr o oraculo sozinho e ver QUAL ficheiro nao e
     reproduzido e PORQUE. Se for o gen_zipc (--out), e um ajuste do oraculo, nao do
     gerador.
  2. `visibility-guard` -- o AttributeError e um metodo que mudou de nome; corrigir o
     probe ou o oraculo.
  3. `AGENTS.md pins` -- re-medir o pin e actualizar com o numero novo.
  4. Os cinco restantes, um a um.

NAO FECHO O GOAL. O criterio dele (0 tokens orfaos) esta cumprido; o portao que o
prova e que tem de ficar verde, e esta vermelho por onze razoes que eu ainda nao
atribui uma a uma.
