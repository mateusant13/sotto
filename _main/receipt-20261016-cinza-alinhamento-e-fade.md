# TRES QUEIXAS: a caixa cinza, o alinhamento e a legenda que nao some

## 1. A CAIXA CINZA -- a causa era uma inversao minha

MEDIDO com o motor real (probe CDP, 900x170, sobre a caption.html):

    ANTES:  html.bg = rgba(0,0,0,0)   body.bg = rgba(0,0,0,0)   -> a pagina pintava NADA

E era isso o defeito. A janela da legenda e transparente por COR-CHAVE: TransparencyKey =
magenta + WS_EX_LAYERED (medido na janela viva: LAYERED key=0xFF00FF flags=1 ok=True). A
cor-chave remove pixels EXACTAMENTE magenta -- e mais nada.

A pagina pintava TRANSPARENTE, e o WebView2 compoe isso sobre o fundo OPACO dele. O que sobra
e esse fundo: o cinza que ele ve. A chave nunca o podia remover, porque cinza nao e magenta.

A cura e a pagina pintar a PROPRIA cor-chave, e entao tudo o que nao e texto sai da janela:

    caption.html        html, body { background: #ff00ff !important; }
    zip-overlay.css     html[data-caption-window], html[data-caption-window] body {
                          background: #ff00ff !important; }

MEDIDO DEPOIS:

    html.bg = rgb(255, 0, 255)    body.bg = rgb(255, 0, 255)   <- a cor da chave
    elementos que pintam: 4 -- HTML, BODY (magenta, chaveado), a LED verde e o meter verde

Nenhuma placa cinzenta em lado nenhum. O texto e a LED nao sao magenta, portanto ficam.

## 2. O ALINHAMENTO -- a segunda linha comeca a esquerda

A causa estava escrita no zip-overlay.css, com a nota THE COLUMN HANGS TO THE RIGHT, as the
zip sets it: text-align right !important em .caption-float__col, __line e __prev.

O dono disse o contrario, verbatim: a segunda linha comeca na direita da div ainda, nao e nem
na esquerda ou meio. MEDIDO antes: align.col/prev/line = right.
MEDIDO depois: align.col/prev/line = left, alignItems.col = flex-start.

As duas regras do .captions__list (o list do strip) FICAM a direita -- sao outro elemento.

## 3. A LEGENDA QUE NAO SOME -- nao havia temporizador nenhum

MEDIDO: push_caption_to_window mostrava a janela na PRIMEIRA legenda e nunca mais a escondia.
grep por setTimeout/setInterval/Timer no caminho da legenda: ZERO. A legenda ficava o tempo
inteiro porque nada a tirava.

Acrescentado ao shell:

    CAPTION_IDLE_HIDE_S = 6.0
    _arm_caption_idle_hide()   -- rearmado a CADA legenda empurrada
    _caption_idle_hide(seq)    -- esconde so se a sequencia nao avancou

A sequencia e o que impede um temporizador velho de esconder uma legenda nova. E o
show_caption_window(False) escreve data-caption-window=off, portanto o painel volta a mostrar
a legenda dele quando a janela some.

VALIDADO em processo (probe com subclasse real, sem lancar a app): PASS 4/4

    T1 idle esconde uma vez e escreve a marca off
    T2 re-armar cancela o anterior -- esconde UMA vez
    T3 um temporizador obsoleto (seq avancado) NAO esconde
    T4 sem janela mostrada nao mexe em nada

E o probe apanhou um erro MEU primeiro: a versao anterior usava um objeto que nao era
SottoShell, e self._caption_idle_hide nao resolvia (CAPTION_IDLE_ARM_FAILED). Era o probe que
estava errado, nao o codigo -- mas sem o corrigir eu teria concluido o contrario.

py_compile rc=0, 557 969 B.

## 4. ALT+C -- o que esta MEDIDO, e o que falta

  * O registo esta BEM: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true
    mod_norepeat=true -- cinco vezes no log, uma por arranque.
  * O ciclo AVANCA: as pressoes das 05:57:04 / 05:57:07 / 05:57:11 mostram PANEL_SHOWN
    mode=strip, mode=side e PANEL_HIDDEN -- HIDDEN -> STRIP -> SIDE -> HIDDEN, o contrato dele.
  * MAS o painel nao vem para a frente: PANEL_FOREGROUND_UNLOCK ok=false. O
    SetForegroundWindow e RECUSADO pelo Windows -- a shell nao e o processo em primeiro plano,
    e o Windows nao deixa um processo de fundo roubar o foco. O painel aparece atras da janela
    que ele esta a usar.
  * E a app NAO ESTA A CORRER AGORA: o censo de processos nao encontra nenhum
    sotto_webview.py. Sem shell, Alt+C nao pode fazer nada.

NAO MEDIDO / NAO FECHADO: o nome da janela que tem o foco, e se o painel fica realmente
visivel por cima do que ele usa. A cura provavel e o AttachThreadInput (ou
AllowSetForegroundWindow) antes do SetForegroundWindow -- NAO aplicada, porque mexe no caminho
de foco e eu nao a posso verificar sem lhe mostrar a janela.

## 5. OS BOTOES -- NAO MEDIDO

O subagente que ia medir a posicao dos botoes por tema terminou SEM relatorio. Fica nomeado
como o proximo trabalho: medir os rects de cada controle nos cinco temas e fixar a mesma
posicao literal. Nada foi afirmado sobre isso aqui.
