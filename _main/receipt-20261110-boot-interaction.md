# RECIBO — a fluidez medida DO ARRANQUE, e o que ela ja' diz (dono, 2026-11-10)

Ordem do dono, verbatim: *"a performance e o measure de TUDO tem que comecar a partir do momento
que o app abre. como um usuario. se eu abro o app, e ja tento abrir o painel alt c, e ele demora 2
segundos, E HORRIVEL."*

## 1. O instrumento: `_main/boot-interaction-oracle.py` (novo)

Le a **ultima sessao** do log vivo (`SHELL_STARTUP_STAGE stage=pre-lock` e' a ancora) e reporta uma
linha por interaccao basica, com o instante no arranque (`boot+ms`) e o custo dela em ms.

**PORQUE DOIS ELOS.** O log nao carrega um id na linha `PANEL_SHOWN`, logo um emparelhamento
posicional atribui a pintura de uma pressao a tecla de outra e inventa o numero. O elo que NAO e'
ambiguo e' o `HOTKEY_COALESCED ... transitions=1`, que o proprio codigo emite imediatamente antes de
chamar `show_strip`/`show_side` e que carrega `from=`/`to=`. Portanto:

| elo | linhas | o que mede |
|---|---|---|
| DESPACHO | `HOTKEY_PRESSED role=panels` -> `HOTKEY_COALESCED transitions=1` | a tecla chegar ao laco que decide |
| PINTURA | `HOTKEY_COALESCED transitions=1` -> `PANEL_SHOWN` | a janela aparecer no ecra |

Orcamentos declarados: **400 ms** para os dois elos do Alt+C e para o Ctrl+Space (e' o mesmo prazo que
`paint-live-show` ja' exige, nao se inventa uma regua nova), **200 ms** para o menu da bandeja,
**15 000 ms** para a primeira legenda (a carga do modelo, informativa: nao e' promessa de fluidez).

Uma interaccao sem par no log fica **UNMEASURED** e **impede** o verde; um log sem sessao diz
`SKIPPED` (rc=3). Nada medido nunca se apresenta como rapido.

## 2. O que ele mede na sessao DELE de hoje (pid 13072, arranque 09:33:51.565)

```
interacao                       boot+ms         ms orcamento  veredicto
alt-c 1o: despacho                21484        5.0      400  PASS  to=visible/strip presses=1
alt-c 1o: pintura                 21489     3142.0      400  FAIL  content_ack=false wait_ms=500.0
alt-c pior total                  24835     5241.0      400  FAIL  despacho 2215 + pintura 3026
ctrl+space primeiro toggle        20076      212.0      400  PASS  on=false
bandeja: pior menu_ms                 -     5063.0      200  FAIL  n=13 ok=0 em 13
arranque -> 1a legenda                -     1856.0    15000  PASS
VERDICT: FAIL -- medidas=6 falhas=3 nao-medidas=0
```

Tres factos que isto separa, e que nenhum instrumento anterior separava:

1. **A TECLA E' INSTANTANEA; A JANELA NAO.** O despacho custou **5 ms**; a pintura custou **3 142 ms**.
   Todo o atraso que ele sente esta' no caminho do `show`, nao no hook nem no laco do gesto.
2. **O PIOR CASO DE HOJE FOI 5,2 s** (despacho 2 215 + pintura 3 026), mais do que os 2 s que ele
   chamou horriveis -- e ele nao os viu como um erro porque nao havia linha nenhuma a dizer o total.
3. **A BANDEJA NUNCA FICA EM PRIMEIRO PLANO**: 13 `TRAY_MENU_FOREGROUND`, **13 com `ok=0`**, com
   `err=1446` (ERROR_TIMEOUT) e um `menu_ms=5063`. O menu que ele chamou de travado esta' medido.

E o que JA' esta' bom, para nao se afirmar o contrario: o Ctrl+Space comuta em **212 ms** e a primeira
legenda pinta **1 856 ms** depois do arranque (a carga do modelo, dentro do orcamento informativo).

## 3. O controle

`--neg-arm` monta **seis logs sinteticos** e exige o veredicto de cada um: uma sessao dentro dos
orcamentos tem de dar PASS; Alt+C a 2 000 ms, Ctrl+Space a 900 ms, bandeja a 800 ms e primeira
legenda a 40 s tem de dar FAIL **cada um pelo seu braco**; e um log sem sessao tem de dar SKIPPED.
Medido: `NEG-ARM: PASS -- 6/6 casos`, rc=1. Sem navegador, sem janela, sem audio.

Passos da bateria: `boot-interaction` (`always`, skip-capable) + `red-as-expected-boot-interaction`
(`:expectred`, rc=1 + `NEG-ARM: PASS`). `battery-record-pairing` mediu **459 passos e 459 nomes com
registo, 0 achados**; `battery-class` PASS; `battery-wiring` PASS (187 ligados).

## 4. O que NAO esta' medido / nao esta' corrigido

* **A correccao dos 3,1 s / 5,2 s NAO foi feita aqui.** Este recibo entrega o instrumento e o numero;
  o `content_ack=false` com `wait_ms=500` diz que a espera declarada e' de meio segundo, logo o resto
  do tempo esta' FORA daquela espera (o map/`transparency_hack`/ack da pagina). O cartao da cura
  fica aberto com estes numeros.
* **O `err=1446` da bandeja** tem cura propria (`SetForegroundWindow` recusado: o mesmo classe do
  menu que ele chamou de travado em 2026-11-04).
* Uma corrida *da propria app* continua a ser dele: este instrumento le o que a app dele escreveu, e
  nao abre nada.
