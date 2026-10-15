# REGRAS FIXAS DO SOTTO -- o que fazer, o que NAO fazer, e donde vem cada regra

Estabelecido pelo dono 2026-10-14, verbatim: novas regras pra seguir: saber o que fazer.
saber o que nao fazer. ter oraculo. ter uma suite de testes com forma de confirmar os
resultados. recria tudo pra cada coisa do sotto, e pro futuro.

Tudo abaixo foi MEDIDO nesta sessao. Nenhuma regra aqui e bom gosto.

---

## 1. SABER O QUE NAO FAZER

### N1. Nunca tratar um instrumento limitado como se nao tivesse limites
Medido: a sonda de pintura escreve em _paint-{tag}.log, NAO no log de producao; eu afirmei
o contrario e estava errado. Um git ls-files vazio nao prova ausencia de ficheiro. Um
ENOENT prova que o CAMINHO esta errado, nao que o artefacto nao existe.

### N2. Nunca editar por fatia de linha ou regex quando ha strings exactas
Medido: parti preflight-refusal-visible-oracle.py com um edit cujo old_string nao
correspondia -- deixou um rc4 duplicado e IndentationError. O py_compile apanhou e o
git checkout salvou. Duas edicoes pequenas batem uma grande.

### N3. Nunca dizer que a rota e do lado do utilizador
O dono, verbatim: nao e pra escolher um ou outro. esse programa vai ser usado por
milhares de pessoas. entao faz direito. O estado por defeito de quase todos os
utilizadores e NAO TER NADA ENCAMINHADO. Um programa que trata isso como falha do
utilizador e um programa partido para o seu caso de uso principal.

### N4. Nunca prometer que viste uma imagem
O modelo step-5-preview-free nao tem entrada de imagem -- verificado pelo erro da
propria ferramenta. Dizer que vejo os prints sem poder ve-los e a mesma mentira de N1.

### N5. Nunca deixar um vermelho sem atribuir
A bateria ficou 88/9 tres vezes: falta de 5 flags suprimidas no HIDDEN_FLAGS, um
controlo que ja trazia a cura, e um redirecto para a TEMP do sistema que dava rc 120.
Em TODOS os casos a causa estava no MEU instrumento ou no MEU caminho, nao no produto.

### N6. Nunca criar um padrao de desenho
O dono, verbatim: tira esse padrao de design de todos. nao e pra ter padrao. o padrao
e os botoes no mesmo lugar. Acrescentei uma moldura uniforme a 30 temas na mesma
rodada em que ele pediu botoes visiveis. Visibilidade vem do PREENCHIMENTO, nao de uma
aresta igual em tudo.

---

## 2. SABER O QUE FAZER

### F1. Cada area do Sotto tem um oraculo, e ele corre na bateria
Medido: a area do pre-voo do wrapper ficou sem porta durante meses, e o defeito da TEMP
(rc 120, arranque recusado) viveu la ate esta sessao. O cobertura-oracle corre na
bateria e falha quando uma area nao tem instrumento.

### F2. Cada correccao tem uma prova no processo, nao so uma leitura
Medido: a correccao do Alt+C foi provada instanciando a classe real, e o defeito antigo
foi REPRODUZIDO como controlo negativo. Um fix sem controlo negativo nao distingue a
cura da ausencia do teste.

### F3. Confirmar pelo comportamento, nunca pela variavel que suspeitei
Medido: suspeitei da TEMP cheia; a verdade eram dois redirectos para drives diferentes
dando rc 120 e rc 2. So a reproducao minima isolou.

### F4. O contrato de um defeito antigo fica, muda-se so o PRECO
Medido: a decisao de 2026-10-06 (uma morte nunca parece aquecimento) ficou INTACTA; o
que mudou foi a escada de tempo da morte sem audio. Desfazer uma decisao medida para
resolver um sintoma e como os dois defeitos desta sessao nasceram.

### F5. Nada e lancado sem ordem do dono
O app e dele e esta em uso. So o Lead lanca, relanca ou mata. Um instrumento que precisa
de lancar pede o comando exacto no recibo e o Lead executa.

### F6. Um recibo sem numero nao e um recibo
Cada afirmacao carrega o comando e o numero. O que nao foi medido diz-se NAO MEDIDO.

---

## 3. O GATE

    node _main/instruments-battery.mjs      # 89 instrumentos, tem de dar 89/89 rc=0

O oraculo de cobertura (cobertura-oracle.py) corre dentro dela: se uma area do Sotto
ficar sem instrumento, a bateria fica vermelha. E assim que recria tudo pra cada coisa
deixa de ser uma intencao e passa a ser uma porta.

## 4. PARA O FUTURO

Uma area nova no produto entra com TRES coisas no mesmo commit: a regra (fazer/nao
fazer), o oraculo que a gate, e a linha na bateria. Um commit que acrescente area sem
gate e um commit que a proxima pessoa vai ter de descobrir as avessas.
