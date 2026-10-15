# O DIALOGO NAO ABRE QUANDO O PAUSE NAO EXISTE -- e o raciocinio que eu estava a desfazer

## O que estava escrito no codigo, e era defensavel

`panel.js`, sobre o botao do pause:

    // Not `disabled`: the button job is to OPEN the dialog, and the dialog is
    // where the owner finds out what this shell can and cannot do. `aria-disabled`
    // is the honest announcement without making it unreachable.

**E um raciocinio honesto: e no dialogo que o dono descobre o que a shell faz.**

**E o dono rejeitou-o, com o print na mao:** *"jesus que coisa mais nojenta de feia"*.
**A palavra dele ganha.**

## O que ele via, e a conta

Um dialogo a perguntar *"Pause and unload?"* com:

  * um botao DESACTIVADO -- *"Pause -- not available in this shell yet"*;
  * uma linha vermelha -- *"This build cannot pause yet. The panel has no bridge.pause()
    to call, so the engines keep running and nothing will be unloaded."*;
  * e a barra de scroll que a altura desse texto obrigava a aparecer.

**Tres sintomas, uma causa: o dialogo existia para oferecer uma funcao que esta shell nao
tem.** `wired` e falso no WebView2 porque nao ha `bridge.pause()`.

**Oferecer uma funcao que nao existe e pior do que nao a oferecer** -- e a prova e que o
utilizador fica com um dialogo que lhe diz que perdeu o tempo a abri-lo.

## A correccao, e sao cinco linhas

Em `openPauseConfirm`, DEPOIS de `applyPauseAvailability()` -- que e quem sabe o estado:

    if (dom.pauseConfirmButton && dom.pauseConfirmButton.disabled) {

**Usa o `disabled` que o `applyPauseAvailability` acabou de pos, portanto nao fica uma
SEGUNDA copia da verdade sobre o que esta ligado** -- que e como os defeitos de hoje
comecaram todos.

Resultado: sem pause, **nao ha dialogo** -- e sem dialogo nao ha botao morto, nem linha
vermelha, nem barra de scroll. Os tres sintomas caem com a causa.

`node --check` rc=0.

## O que fica, e e o proximo passo honesto

Ao clicar, o painel escreve **uma linha no rodape** -- *"Pause is not available in this
build yet"*. **E melhor que um modal, mas ainda e um botao que nao faz o que diz.** O passo
seguinte e **ou implementar o `bridge.pause()` a serio, ou tirar o botao da barra.** Fica
nomeado; nao escolhi por ele.

## E os subagentes do audit de UX continuam a correr

Tres: `ux-strip-bar`, `ux-dialogs`, `ux-side-panel`. Nenhum lancou nada, nenhum pos nada na
tela dele -- e essa foi a PRIMEIRA regra que lhes dei.
