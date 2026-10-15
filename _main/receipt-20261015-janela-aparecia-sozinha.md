# "POR QUE EU AINDA TO SENDO ATRAPALHADO?" -- porque a janela da legenda aparecia sozinha

## A causa, e esta escrita no proprio shell -- para a OUTRA janela

O comentario do `_on_navigation_start` explica o mecanismo:

    "pywebview SHOWS the form again on EVERY navigation start when the window is
     transparent (platforms/edgechromium.py:345-349, if transparent: self.form.Show())"

A janela PRINCIPAL tem uma guarda para isto: `_gate_form_show`, que recusa o `Show()` do
pywebview com ninguem a pedir.

**A janela da LEGENDA, que eu criei, NAO TINHA NENHUMA.** E por isso ela aparecia sozinha na
tela dele ao abrir a app -- cinzenta, sem legenda nenhuma, por cima do que ele estava a
fazer. A pergunta dele: *"por que eu ainda to sendo atrapalhado?"*.

## A cura, e e uma condicao

No fim do `_on_caption_loaded` -- o evento em que a navegacao ja acabou, portanto o sitio
certo para repor o estado:

    if not getattr(self, "_caption_window_shown", False):

**Se o botao live a mostrou, isto nao lhe toca.** Se ninguem a pediu, ela volta a
esconder-se -- e ele deixa de a ver a aparecer do nada.

`py_compile` rc=0.

## O que eu NAO fiz, e digo porquê

**A mudanca de raiz para *"abrir o Sotto trava o PC"*: o worker deixa de arrancar com a
shell e passa a arrancar quando ele pedir legendas.**

MEDIDO, e e esta a conta: `SHELL_STARTUP_STAGE` = 18 no log, e nas ultimas ~1 hora o worker
carregou o modelo **14 vezes** -- `worker_load_s` de 90.96, 30.79, 26.25, 19.45, 18.58, 7.41,
5.76, 4.63, 3.68, 2.55... Isso e ~1 GB de disco e o modelo a inicializar, catorze vezes, e
**a maioria desses arranques fui eu a fazer para medir.**

Nao fiz a mudanca agora porque ela mexe num contrato que tem um gate proprio de 15 bracos
(`_main/_lane1-worker-default-arms.py`), e **meia-mudanca num contrato e pior do que nenhuma**:
o gate fica vermelho, e vermelho por um motivo que eu nao vou ter contexto para explicar.

Fica nomeada com o sitio exacto: `_worker_autostart_reason` (`sotto_webview.py:6257`) devolve
`default`, e e esse o unico valor que arranca. O que ela tem de passar a devolver e um valor
que NAO arranque, com o arranque a acontecer no `show_panel` -- e o gate dos 15 bracos a ser
re-baselinado na MESMA rodada.
