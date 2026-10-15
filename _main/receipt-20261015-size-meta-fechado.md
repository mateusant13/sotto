# O --size-meta FECHOU: cada pd-* pinta o chrome no tamanho do SEU zip

O dono pediu ha muito: os temas dos .zip com o desenho IGUAL, so os botoes variam. O
base-themes-oracle media um sintoma disso: o token --size-meta, que existe para o
tamanho do texto de chrome, era DECLARADO por todos os dez desenhos e LIDO por
nenhum. Dez desenhos com o mesmo esqueleto e o mesmo tamanho de chrome.

MEDIDO NA ZIP, nao no extract: o membro src/components/panels.tsx (11 995 B, sha256
36917491...) e byte-identico a copia que o gerador leia, e la cada desenho manda o seu
tamanho: pd-tele 11px (linha 31), pd-bcast 9.5px (:158), pd-mano 10px (:182),
pd-cine 13px (:253), pd-instr 10px (:340).

A DIFICULDADE, e a solucao: o bloco CHROME e PARTILHADO pelas duas lanes, e editar o
literal la reescreveria theme-1..5.css -- o que as ordens proibem. A troca corre no
TEXTO EMITIDO dos desenhos pd-* apenas, com uma tabela de pares-ancora exactos que
FALHA O BUILD se uma ancora nao ocorrer exactamente uma vez. E ela apanhou o primeiro
corte: ancoras de duas linhas escritas com CRLF nunca casam, porque o Python normaliza
as mudancas de linha do fonte.

O DIFF E EXACTAMENTE O PRETENDIDO: 8 declaracoes em panel-designs.css, todas
font-size: <literal> -> var(--size-meta). Linhas 3721->3721, +95 B, 3720 CRLF / 0 LF
nu. theme-1..5.css e panel-designs.js: BYTE-IDENTICOS (provado por sha256; so os
mtimes mexeram porque o gerador nao tem interruptor por ficheiro).

VISIVEL, e vale a pena nomear porque e o que o dono vai ver:
  pd-mano 12.5px -> 10px   (a linha de rascunho encolhe)
  pd-cine 11px -> 13px     (marca e estado crescem)
  pd-instr 9/11/9 -> 10px  (tres linhas, uma medida)
  pd-tele 10px -> 11px
  ARM B passou de "declarado 10 vezes com 0 leitores" a "2 vezes" -- as duas que
  sobram sao da lane A (theme-1 e theme-5), e estao certas em ficar.

GATES, todos nos bytes finais:
  base-themes-oracle ........... PASS (ARM D verde)
  base-themes-oracle --neg-arm . CONTROL PASS (M1-M5)
  scope-leak-oracle ............ PASS, 9 folhas, 0 fugas
  zipc-designs-oracle .......... PASS, 9 checks
  gen_themes.py --check ........ rc=0, 535 linhas de registo, 0 sem proveniencia
  instruments-battery .......... 144/144 rc=0, failed=0, launches=0

NAO MEDIDO, e dito: nada foi pintado ao vivo. Todos os valores acima sao valores
COMPUTADOS de tokens declarados. Nada foi lancado, e os movimentos de 1 a 2,5 px
sao para o olho do dono, nao para este recibo.

E uma prosa FALSA que fica, fora do meu alcance: o base-themes-oracle (linhas 83-89)
ainda diz que o --size-meta e lido por nenhum e culpa o bloco CHROME partilhado. O
gate passa, mas o texto mente. Tentei corrigi-la e PARTI O FICHHEIRO (string sem
fecho); reverti e ficou como estava. Registado aqui para nao se perder.
