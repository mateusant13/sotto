# AS QUATRO AUDITORIAS DE TRADE-OFF — e o conflito que a MINHA folha introduz

2026-10-13. Quatro lanes, uma por area (`shell`, `panel.js`, `panel.css`, `worker`),
recibos em `_main/receipt-tradeoff-*.md`. Nenhuma editou o produto.

## O que e MEU e esta errado: o `zip-overlay.css` usa `!important` e derrota contratos escritos

A auditoria do `panel.css` mediu o padrao. As 59 cabecas `body[data-surface="strip"]` e todas as
defesas de ID estao cotadas contra OS TEMAS (`:root[data-theme] .class`, (0,3,0)), e contra esse
concorrente estao aritmeticamente correctas. Os sobrepositores REAIS sao folhas IRMAS com
`!important`, carregadas DEPOIS do `panel.css`: `zip-overlay.css` 51, `skin-layout.css` 10,
`panel-designs.css` 10, `caption-float.css` 2. `!important` vence qualquer regra de autor
nao-`!important` independentemente da especificidade -- logo nenhuma dessas 59 cabecas compete.

E a folha com MAIS `!important` e a que EU escrevi hoje. Vitimas medidas:

* `zip-overlay.css:249-255` transforma a barra de 4 px num ponto verde redondo de 6 px.
* `zip-overlay.css:321-328` poe um cartao com borda e preenchimento em `.caption-float__stage`,
  derrotando a lista NOTHING PAINTS in every state do `caption-float.css` e os comentarios do
  `panel.css`: NO BACKGROUND EVER (:2923-2926) e the bar IS the body (:2950-2954) -- no unico
  estado em que o overlay pinta.
* `zip-overlay.css:151` vence o par de cores LIVE ao nivel de ID (:2022-2026, :2042-2049), cujo
  comentario (:2001-2003) promete que nenhum tema pode restaurar o vermelho antigo -- verdade
  dos temas, falso da folha irma que eu embarquei.

ISSO NAO E UM DESENHO DIFERENTE: e a minha folha a mentir sobre o produto. Os quatro passos de
desenho que apliquei hoje escoram-se em `!important` e cada um apaga uma promessa escrita.

## E uma vitima que NAO e minha

`caption-float.css:102-105` (height:0;margin:0, (1,1,0)) apaga `panel.css:3089-3111` -- o medidor
mais `.is-on` mais `meter-fill`, OITO declaracoes inertes, e o comentario :3086-3088
(CSS owns the shape) e FALSO.

## O que as quatro dizem, e o que nenhuma pode dizer

CONCORDAM que o loop esta fechado pelas DUAS guardas (a da pagina, verificada mecanicamente no
Node: 100 chamadas com o mesmo nome dao 0 applySurface, uma troca real da 2; e a da shell, que
apliquei hoje). NENHUMA pode dizer se o loop morreu: a cauda que usaram e PRE-fix, e confirmar
exige UM lancamento, que e do Lead.

* WORKER (23 944 B): a segunda passagem M3 custava 50,9% de TODA a inferencia e nao comprava
  nada -> OPT-IN e DESLIGADA (aplicado). O custo por chunk fora do modelo e 163,8 us = 0,6% ->
  MANTER tudo; a optimizacao obvia poupa 0,28 s em 4 h e mexe nos digitos do rms. 13 deliberate,
  11 MANTER com prova.
* PANEL.JS (26 261 B): dos dois polls de 1 Hz SO UM EXISTE -- o relogio nunca arma
  (`data-chrome-clock` tem 2 ocorrencias em TODA a app/panel, ambas dentro do panel.js, e o IIFE
  retorna antes do setInterval). O que corre e o pull de stats a 1,007 respostas/s contra 145 969
  pushes de medidor -- 1% do trafego. Veredicto MELHORAR (auto-desarmante), porque repinta a
  escadaria do WORKER_STATS a 1 Hz em vez de 10 Hz: amplifica o defeito reportado pelo dono.
* PANEL.CSS (39 145 B): ~1 309 B / ~45 linhas (2,6 KB com comentarios) de `panel.css` nao podem
  corresponder a nenhum elemento carregado -- 7 regras mortas (:2890-2906, :2603-2610,
  :1502-1510, :1495-1500, :1475-1477 duplicada de :2915-2917, :2560-2577, :1863-1963).

## O que eu NAO corrigi, e digo-o antes que perguntes

O `zip-overlay.css` com `!important` continua comitado e continua a derrotar contratos escritos.
A correccao certa NAO e apagar o cartao: ePARAR DE USAR `!important` e deixar o produto decidir --
e isso pode mudar o que o painel parece. E UMA DECISAO DO DONO: o cartao do zip D foi o que ele
pediu, e o `caption-float.css` diz que nada pode pintar.

ONDE E QUE O CARTAO ACABA E O CONTRATO COMECA e uma pergunta que so ele pode responder.
