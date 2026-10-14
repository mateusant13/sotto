# BALANCO FINAL DO P0 -- o que fechei, o que diagnostico, e o que nao consigo

2026-10-14. Ordem do dono: consertar tudo que e friccao, lentidao, falta de optimizacao e
errado. Este e o registo.

## FECHADO E MEDIDO

P0-1 O LOG. Crescia sem limite: medido 808,6 MB e +81 MB/hora. Rotacao comitada e PROVADA
EM PRODUCAO: LOG_ROTATED from=847859845 B kept=16777081 B -- o log passou a comecar em 16 MB.
O flood foi atribuido por censo em streaming e o defeito acoplado corrigido:
PANEL_VISIBILITY_WRITE_FAILED dava 1 145 063 linhas porque o `write_atomic` usava um TEMP DE
NOME FIXO e dois escritores colidiam. Agora temp unico + repeticao limitada + log com taxa.

P0-3 O TRAVAMENTO. Confirmado pelas auditorias: e A MESMA causa do P0-1 -- um LOOP de
realimentacao JS<->Python. Uma iteracao fechava-se sobre si mesma
(`emit(geometry)` sem dedup voltava ao `onGeometry`). Taxa medida p50 102/s, p90 185/s,
p99 264/s. CORRIGIDO pelas DUAS guardas -- a da pagina e a da shell.

P0-4 MOVER. Duas operacoes redundantes por pointermove, medidas a ~149 Hz:
`localStorage.setItem` a cada move (REMOVIDO, o end() ja grava) e
`exec_js(STRIP_MOVED_JS)` a cada move, um round-trip sincrono (agora UMA VEZ POR ARRASTO,
nao removido -- o comentario dele documenta um proposito real).

P0-5 OS BOTOES. O dono: "por algum motivo, tu ta fazendo os designs terem botoes em lugares
diferentes. nao e pra fazer isso". Ele tinha razao e o gerador fazia-o: o gen_cinematic.py
emitia TRES posicoes para .panel__controls, contradizendo a regra escrita no proprio
panel.html. Unificado na linha de topo.

O GANHO MAIOR veio de uma lane, nao de mim: a SEGUNDA PASSAGEM M3 custava 50,9% de TODA a
inferencia e nao comprava nada. Agora e opt-in e DESLIGADA.

## DIAGNOSTICADO, NAO FECHADO

A bateria da 88/9. Falha em preflight-refusal-visible-oracle.py, arm 4 -- o CONTROLO.
Diagnostico completo em receipt-20261014-last-red-diagnosed.md, e a conclusao e que NENHUM
dos dois candidatos a controlo serve: um pino por revisao nao pode expressar antes-da-cura
para um ficheiro que viveu FORA do indice, e o ficheiro embarcido e de antes do pre-voo
existir. Fiz seis tentativas, TODAS pioraram, e apliquei-as e reverti todas.

## O QUE NAO CONSIGO, E DIGO-O

1. Fechar o vermelho. O controlo correcto tem de ser medido com um harness que NAO de pipe
   ao filho, e o do oraculo da. Nao e um problema de codigo, e do desenho da medicao.
2. A minha folha zip-overlay.css usa !important para derrotar contratos escritos do produto
   (o cartao que pediste contra o NOTHING PAINTS do caption-float.css). NAO A CORRIGI sem
   a tua decisao, porque a correccao muda o que o painel parece.
3. O P0-2 -- a bateria levar 115 s em dois instrumentos -- e a tua decisao, porque a via
   rapida corta cobertura real.

## A REGRA DESTA SESSAO

Seis retraccoes e auto-correccoes, TODAS da mesma forma: tratar um instrumento com limites
como se nao os tivesse. E duas lanes de auditoria renderam mais do que dez rounds meus.