# TRES ORDENS: taskbar, cinzento, e APRENDER A PRINTAR -- mais o audit de UX

## O que ele disse, verbatim

  *"para de fazer essa porra de legenda no meio da tela ser a merda de um processo na minha
   task bar, e para de fazer ESSA PORRA SER CINZA E NAO TRANSPARENTE. E APRENDE A PRINTAR
   DIREITO ESSA MERDA"*

  *"e para de fazer essa merda aparecer na minha tela. ta atrapalhando. tira print com isso
   longe da coordenada da minha tela. tu ta me irritando"*

  *"jesus que coisa mais nojenta de feia. usa subagents pra fazer full audit do user
   experience por que ta me dando nojo"*

## 1. A taskbar e o cinzento sao O MESMO defeito

A janela PRINCIPAL resolve os dois em `_on_before_show`:

    set_ex_style(hwnd, add=WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, remove=WS_EX_APPWINDOW)

**`WS_EX_TOOLWINDOW` sem `WS_EX_APPWINDOW` e o que a tira da barra de tarefas.** E o
`TransparencyKey` do WinForms so e aplicado a uma janela **LAYERED**.

**A janela da legenda nao herdava NENHUM dos dois: eu criei-a e nunca lhe dei os estilos.**
Acrescentado ao `_on_caption_before_show`:

    cap_styles = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if not self.args.opaque: cap_styles |= WS_EX_LAYERED
    set_ex_style(cap_hwnd, add=cap_styles, remove=WS_EX_APPWINDOW)

**E o primeiro corte falhou, com o log a dize-lo:**

    CAPTION_WINDOW_STYLES_FAILED error=UnboundLocalError("cannot access local ...")

Com os nomes `hwnd`/`styles` o Python tratava-os como LOCAIS por haver outra atribuicao mais
abaixo no mesmo metodo. Renomeados para `cap_hwnd`/`cap_styles`, compila. **NAO VERIFICADO a
correr** -- o shell que esta de pe e anterior a esta mudanca.

## 2. APRENDER A PRINTAR -- e a minha tecnica estava errada

Eu capturava coordenadas do ecra (`CopyFromScreen(600,940,...)`) e ADIVINHAVA onde a janela
estava. Tres capturas seguidas apanharam um video do YouTube, a GUI do DSH e a barra de
tarefas -- **nunca a janela que eu queria.** E cada tentativa punha coisas na tela dele.

A tecnica certa, e sao duas partes:

  1. enumerar as janelas do PROCESSO do shell (`EnumWindows` + `GetWindowThreadProcessId`),
     que da o HWND exacto e o rect exacto -- sem adivinhar nada;
  2. `SetWindowPos(hwnd, -3000, -3000, ...)` ANTES de capturar, e `PrintWindow(hwnd, hdc, 2)`
     (`PW_RENDERFULLCONTENT`). **O `PrintWindow` renderiza a janela mesmo fora do ecra.**

Medido: com a janela a -3000,-3000, `off1.png` saiu 380x900 com `ok=True`, e
`janelas do Sotto AINDA visiveis: 0` -- **nada na tela dele.**

## 3. O que a captura fora do ecra mostrou -- e ele tem razao

`I:/cc-tmp/off1.png`. O dialogo *"Pause and unload?"* contem:

  * **uma BARRA DE SCROLL dentro do dialogo** -- a que ele mandou remover em [50532];
  * *"This build cannot pause yet. The panel has no bridge.pause() call, so the engines
    keep running and nothing will be unloaded."* -- **um dialogo que admite que nao faz nada;**
  * um botao DESACTIVADO com o rotulo *"Pause -- not available in this shell yet"* --
    **oferecer ao utilizador uma funcao que nao existe;**
  * *"This build cannot pause yet"* a vermelho -- **um erro sobre o qual ele nao pode agir;**
  * *"Warming up the teleprompter"* com texto a contraste quase nulo.

**"Nojenta de feia" e literal: scrollbar, moldura, botao morto e erro sem accao.**

## 4. Os subagentes do audit, criados com as regras dele

Tres, um por superficie: `ux-strip-bar`, `ux-dialogs`, `ux-side-panel`. **A primeira regra
que lhes dei foi a dele: nunca lancar, nunca matar, NUNCA mandar teclas nem trazer nada para a
tela** -- e para ver, so `PrintWindow` fora do ecra ou o Chromium headless.
