# A LISTA COMPLETA -- tudo o que o dono mandou arrumar, dos 65 prompts da sessao

Ordem dele, verbatim: *"vai ver o historico de todos os meus prompts do workspace sotto,
dentro do dsh/deepseek harness, e veja tudo que eu ja falei que tu tem que arrumar sobre
isso"*. Fonte: `I:/cc-tmp/meus-prompts.txt` (65 prompts, extraidos do transcript da
sessao, 189 MB descomprimidos).

## 1. [860]
Diferentes templates, mas o BOTAO de trocar template fica no MESMO lugar; dropdown com PREVIEW ao passar o rato; todos os templates MUITO perto dos .zip -- INCLUINDO as legendas ao vivo no BAIXO e no MEIO da tela; o painel de baixo SEM transcript/historico (so o da direita); o painel de baixo pequeno e minimalista; as legendas na tela como overlay iguais aos .zip
**Estado: ABERTO: a janela propria esta feita e provada em sonda; o dropdown com preview NAO existe**

## 2. [13770]
Cada tema dos .zip com o design IGUAL, so muda a POSICAO dos botoes; um "revamp" a serio, nao uma skin por cima nem recolor
**Estado: PARCIAL: os geradores leem os zips; falta a comparacao visual tema a tema**

## 3. [24395]
Cada tema implementado, NAO por cima do nosso painel nem na mesma div; "traduzido" pro tamanho atual com os botoes atuais, o resto IGUAL; o painel de baixo NAO mostra legenda; menor ainda, mais estreito, do tamanho dos botoes; os botoes mais CLAROS; um botao que liga a legenda NA TELA como overlay EXATAMENTE como os .zip; o Sotto nao carrega tudo de uma vez, so o essencial; nemotron 3.5 ao vivo + parakeet redux por cima; animacao por LETRA TROCADA; separacao de speakers de call; dropdown com preview sem travar e super otimizado; investigar se o Sotto causa stutter no arranque
**Estado: VARIOS ABERTOS: o painel de baixo, a animacao por letra, a separacao de speakers, o dropdown**

## 4. [30564]
Achar laco/fuga/travamento e arrumar; o bug do Alt+C (uma cor solida, uma div inteira); TRES overlays: (1) painel de baixo (2) a legenda independente, na tela, SEM FUNDO, SEM NADA, extremamente clean, com algo que lhe de corpo tipo uma barra a esquerda (3) o painel da direita com TODOS os botoes; o painel de baixo so o bare minimum; SO o painel da direita mostra historico
**Estado: PARCIAL: os 3 overlays existem; a legenda sem fundo esta feita e provada**

## 5. [32218]
O painel MINIMO; a legenda INDEPENDENTE do painel, nao acoplada; nao ver div com cor solida mas INVISIVEL; as FONTES ORIGINAIS do .zip; o painel de baixo MOVIVEL pra cima/baixo/lados; TIRAR o botao da direita de mostrar legenda; o botao da legenda ao vivo deve ser o "live" e CLARO quando esta e quando nao; o X introduzido em lugar aleatorio e ESTUPIDO -- poe na DIREITA dos botoes; voltar na sessao e ver os prompts de imitar o .zip; VARIOS DESIGNS BUGADOS; Alt+C 2x nao abre o painel da direita; implementar TUDO
**Estado: ABERTO: o arrasto (ele diz que esta completamente travado AGORA); as fontes**

## 6. [32264]
A troca de design/tema NAO pode rolar pra cima -- sempre mostrando o bottom do historico
**Estado: a confirmar**

## 7. [37122] e [37134]
Ver print de como e CADA .zip (cada demo) e aplicar daquele jeito ao nosso caso; o painel tem dimensoes de PAINEL, nao de um app quadrado nem da tela inteira
**Estado: ABERTO: so o theme-1 foi comparado por numeros**

## 8. [37242]
Entendeu como eu quero as legendas na tela? NAO acopladas a painel algum. A legenda ao vivo. Como OVERLAY. E o jeito que ela aparece quando eu quero ou nao?
**Estado: FEITO em caminho: janela propria, provada em sonda com screenshot**

## 9. [38444]
Quando o Sotto abre ou fecha o PC trava; tu esta fazendo os designs terem botoes em lugares DIFERENTES -- nao e pra fazer isso; o painel de baixo e o da direita NOJENTOS de performance e de mover; o painel de baixo COMPLETAMENTE FEIO; a seta mostra a legenda e como ela deve FICAR NA TELA, com o design PROPRIO dela, pra CADA DEMO DE CADA .ZIP
**Estado: PARCIAL: os botoes na mesma posicao foram unificados num gerador**

## 10. [41856]
Alt+C nao aperta direito em diversos casos; abrir/fechar o Sotto trava o PC; o Sotto reclama de coisa nao carregada com erro VERMELHO; TIRAR "em curso" e "historico" das barras; TIRAR o botao de "transcript"; os botoes simples e pequenos porem VISIVEIS O SUFICIENTE; NAO ter tema branco
**Estado: FEITO: em curso/historico fora, transcript fora (visto com olhos), o tecto do reinicio ataca o travamento**

## 11. [42215]
Duplo Alt+C deve aparecer o SEGUNDO painel; o primeiro painel ta BRANCO; porque fechar o Sotto ainda trava o sistema
**Estado: ABERTO em parte: o tecto do reinicio e a cura do travamento**

## 12. [42241]
Porque a partir do rainline os designs sao uma MERDA? Tira print e ve as imagens. E para de dar worker error
**Estado: o tecto do reinicio ataca o worker error**

## 13. [42268]
Compara as prints das demos dos .zip com as prints do implementado; imitar MAIS os .zip; cada design IGUAL ao zip, so os botoes no mesmo lugar; NAO ter MOLDURA no painel (so se a demo tiver); TIRAR esse padrao de design de todos -- nao e pra ter padrao, o padrao e os botoes no mesmo lugar
**Estado: FEITO em parte: moldura removida na ultima folha; falta a comparacao tema a tema**

## 14. [44219]
Porque copiaste coisas SEM SENTIDO das demos? Porque tem "personagens falando" num dos designs? Arruma. E tu esta botando designs POR CIMA do painel e fica duas coisas SOBREPOSTAS como um glitch
**Estado: ABERTO**

## 15. [50531]
Em NENHUM design: moldura, botao por cima da LOGO, ou posicao DIFERENTE em pixel de outro design
**Estado: FEITO em parte: moldura; o botao por cima da logo NAO foi tocado**

## 16. [50532]
E tambem nao quero que apareca a BARRA DE SCROLL
**Estado: FEITO: scrollbar escondida nos dois motores**

## 17. [AGORA]
"a porra de arrastar a janela e completamente travado"
**Estado: ABERTO, e e o proximo**

## O ARRASTO -- o que eu ja vi no codigo, sem ter medido ainda

  * Entra-se SO pela bandeja (`Edit caption position`), nunca por atalho nem por chrome
    no painel (`set_edit_mode`, L6558).
  * `EDIT_DRAG_MIN_INTERVAL_MS = 50` -- no MAXIMO 20 amostras por segundo. Ja e choppy.
  * O movimento e um `SetWindowPos(..., SWP_NOSIZE|SWP_NOACTIVATE)` a cada amostra.
  * **`edit_drag_to` DESISTE em silencio por tres razoes:** (a) `not self.edit_mode`;
    (b) `width <= 0 or height <= 0` no `self.geometry`; (c) o clamp a `work_area()`;
    e o `grab` vem de `self.edit_grab or (0, 0)`.
  * Nenhuma dessas desistencias escreve no log. **E por isso que "esta travado" nao
    deixa rasto: o caminho falha calado.** E o primeiro defeito a corrigir -- medir
    antes de mexer.
