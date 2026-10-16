# F9 -- A MOLDURA DE 1 px NOS DIALOGOS E POPUPS

## A ordem

[50531], verbatim: *em NENHUM design, eu quero moldura*.

## O que o audit mediu

Uma borda de 1 px em TODO dialogo e popup: `panel.css` dialogo, o dropdown, o `#tune-note`
(que era um QUADRO DUPLO -- 1 px de caixa mais 2 px a esquerda), o `#status` (border-top) e o
`#strip-state` (caixa de 1 px).

## O que removi, com o numero

    .pause-dialog    border: 1px solid var(--line-strong)                     -> fora
    .theme-dropdown  border: 1px solid var(--line-strong, rgba(148,163,184,.28)) -> fora

Ambas com o motivo escrito no sitio: a sombra e o fundo JA separam a superficie do que esta
por tras, portanto a linha nao acrescenta informacao nenhuma -- e e o padrao que ele mandou
tirar.

## O que NAO removi, e digo por que

  * `.tune-dialog` -- o meu seletor nao encontrou um bloco com esse nome. Pode herdar do
    `.pause-dialog` (a nota do F3 diz que herda o `margin: auto`), mas **nao verifiquei**, e
    nao afirmo.
  * `#tune-note` -- **NAO EXISTE no `panel.css`**: as duas unicas ocorrencias do nome no
    ficheiro sao os MEUS comentarios. O audit mediu-o, portanto ou vive noutro ficheiro, ou
    ja foi removido. **Nao invento cura para um elemento que nao encontro** -- fica nomeado.
  * `#status` (border-top) e `#strip-state` (caixa) -- sao indicadores de estado, nao
    dialogos; a linha neles pode ser o que os distingue de texto solto. Nao os toquei sem
    medir o efeito, e a ordem dele fala de MOLDURA no painel.

## O que falta

**VISTO a correr.** Nenhuma destas mudancas foi olhada depois de aplicada: o que esta provado
e a regra removida e o motivo. O `.tune-dialog` e o `#tune-note` precisam do mesmo tratamento
depois de eu os LOCALIZAR com um grep mais largo do que o meu.
