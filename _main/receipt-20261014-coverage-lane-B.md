# RECIBO — LANE B: as lacunas do SHELL, do LOG e do WORKER (B1..B6)

**Data:** 2026-10-15 ~00:00–01:0x -03:00. **Lane:** B (`_main/*`, `app/webview/*`, `worker/*`).
**Ordem:** o dono mandou *"cobre todo o restante"* — fechar as 18 lacunas que
`_main/cobertura-oracle.py` mediu. Este recibo fecha as SEIS do brief (B1..B6) e,
porque a bateria so fica verde quando nao falta nenhuma, mais a ULTIMA que resistia
(B7, `panel hide gate at startup` — shell, ficheiro desta lane).

**VERIFICACAO FINAL, os dois numeros que o brief exigiu:**

| comando | antes | depois |
|---|---|---|
| `py -3 _main/cobertura-oracle.py` | **18 [GAP] / 34 areas**, rc=1 | **0 [GAP] / 34 areas**, rc=0 — `VERDICT: PASS -- every mapped area has an instrument that RUNS` |
| `node _main/instruments-battery.mjs` | 127 linhas, rc=1 (a unica vermelha era o proprio `cobertura-oracle`) | **rc=0, `SUMMARY: 131/131 instrument(s) rc=0; failed=0`, `BATTERY-EXIT=0`** |

A primeira corrida da bateria desta lane deu `SUMMARY: 126/127 ... failed=1`, e a unica
linha vermelha era `rc=1 !!! cobertura: 34 areas` — ou seja **o proprio oraculo de
cobertura a dizer que ainda faltavam areas**, com as nove linhas desta lane todas a
`rc=0`. Duas lacunas resistiam, e nenhuma era das seis do brief:

* `JS<->Python surface loop guard` — fechada por **outra lane** durante esta sessao
  (`_main/surface-loop-oracle.py`, linha 106 da bateria). Nao a toquei: o que e meu
  nesta area e o CENSO do flood (B3), nao a guarda do `panel.js`.
* `panel hide gate at startup` — fechada por mim, e a seguir. Vive no shell
  (`app/webview/sotto_webview.py`), que E o ficheiro desta lane.

---

## Regra que governou tudo: nao lancar

Nenhum instrumento desta lane abre a app, o shell, o worker, o WebView2 ou um browser.
**O dono esta a usar a app AGORA** (medido nesta sessao: `pythonw.exe
H:\sotto\app\webview\sotto_webview...` pid 38388 desde 22:05 e `python.exe
H:\sotto\worker\sotto_worker.py` pid 38228 desde 22:36). Duas consequencias:

* tudo o que corre aqui e **em processo** (importa o ficheiro que embarca e chama as
  funcoes reais) ou **le bytes**;
* o unico instrumento que INVOCA o `run.cmd` (B1) corre **so os bracos que nao chegam
  ao caminho de lancamento**, e imprime a prova disso mesmo
  (`ARM-SELECT ... (LAUNCH-FREE: nothing below reaches the launch path)`,
  `leftovers=[]`, census com `0` amostras visiveis).

---

## B1 — wrapper pre-flight (run.cmd exit contract)

**Area no mapa:** token `run-cmd-exit`. **Onde viveu o defeito do rc 120:** no
**alvo do redirect da captura de recusa do PRE-FLIGHT**, dentro do proprio
`app/webview/run.cmd` — `2>%TEMP%\sotto-preflight-refusal.txt`. O ficheiro carrega
hoje a medicao e a cura, nas linhas 142–157:

* `run.cmd:145` — `2>G:\Temp\sotto-preflight-refusal.txt -> rc 120 e a app nao arranca`;
  o MESMO comando, o MESMO interpretador, com `2>I:\cc-tmp\rf.txt -> rc 2` e o texto do
  argparse presente;
* `run.cmd:147` — *rc 120 e o que o cmd responde quando nao consegue dar ao filho o
  redirect que lhe mandou dar*, logo uma maquina com `%TEMP%` cheio, read-only ou num
  drive que recusa a escrita ficava com um wrapper que **RECUSA UM ARRANQUE BOM** e nao
  diz nada accionavel. Palavras do dono citadas ali: *"%TEMP% e uma propriedade da
  maquina DELES, nao da nossa"*;
* `run.cmd:157` — a cura: `set "REFUSAL=%HERE%..\..\_main\sotto-preflight-refusal-%RANDOM%%RANDOM%.txt"`,
  ao lado do log que a recusa e recibo PARA.

**Instrumento:** `_main/run-cmd-exit-oracle.py` (JA EXISTIA, 55 679 B; **nao
reescrito** — ganhou duas coisas aditivas, ver abaixo). **Registado na bateria.**

**O que foi preciso acrescentar, e por que:** o oraculo corria os QUATRO bracos, e
dois deles (`start-logged`, `start-default`) **arrancam a app**; os `G1..G4` arrancam
copias dela. Registá-lo assim faria a bateria abrir a app do dono — exactamente o que
a regra F5 proibe e o que a propria bateria promete ("`launches=0`"). Uma lane irma
chegou a escrever essa objecao no ficheiro. A resolucao foi **aditiva e minima**:

1. `--arms <subset>` (default: os quatro, comportamento intacto) — permite correr
   **so** `argv,bogus,help`, os bracos que nao chegam ao lancamento;
2. `--temp-arm` — o controlo do defeito do rc 120, **estatico** (nao arranca processo
   nenhum): restaura `set "REFUSAL=%TEMP%\..."` numa COPIA e exige RED;
3. dois defeitos do proprio patch, apanhados a correr: o `ARM-RCS` indexava
   `results[n]` de um tuplo fixo e dava `KeyError` com um subconjunto; e a razao
   impressa dizia "all 4 arms green" com dois bracos.

**BRACO NEGATIVO (o da area):** `--arms bogus,help --no-gaps --neg-arm` constroi uma
COPIA da arvore cujo unico ficheiro diferente e o wrapper **pre-fix**
(`_main/run-cmd-prefix-20261006.cmd`, sha256 `B9C08FEC…`).

**Prova de que diz NAO** (verbatim, os numeros):

```
LIVE   --arms bogus,help --no-gaps                       rc=0
  ARM bogus         rc=2 want=2 ms=389 PASS      (5/5 checks ok, leftovers=[])
  ARM help          rc=0 want=0 ms=346 PASS      (5/5: 27/27 flags na usage, --check-args oculto)
  ARM temp-target   [ok] REFUSAL=%HERE%..\..\_main\sotto-preflight-refusal-%RANDOM%%RANDOM%.txt
  CENSUS 24 samples, 0 with a visible window
  ARM-VERDICT PASS  all 2 arm(s) green

NEG    --arms bogus,help --no-gaps --neg-arm              rc=0
  ARM bogus         rc=0 want=2 ms=348 FAIL
      [NO] rc == 2 :: rc=0
      [NO] the wrapper says so on its own console :: (no output)
      [NO] a receipt line is appended to the run log :: ''
  ARM help          rc=0 want=0 PASS              <-- fica VERDE: e um controlo, nao um colapso
  ARM-VERDICT PASS  arm1(bogus) RED-as-expected=True arms2-4-still-green=True failed=['bogus']
```

**BRACO NEGATIVO DO rc 120 (proprio, porque o pre-fix nao pode ser o controlo desta
cura — nao tem pre-flight nenhum):** `--temp-arm`, rc=0:

```
LIVE   [ok] the wrapper DEFINES the refusal capture :: REFUSAL=%HERE%..\..\_main\...
LIVE   [ok] the capture is NOT aimed at the system %TEMP% (rc 120, measured 2026-10-14)
LIVE   [ok] no 2>"%TEMP%..." redirect survives anywhere in the wrapper :: none
MUTANT [NO] the capture is NOT aimed at the system %TEMP% :: REFUSAL=%TEMP%\sotto-preflight-refusal.txt
TEMP-ARM: live green=True  mutant RED-as-expected=True
NEG-ARM PASS: the %TEMP% target is refused by the check, and the live wrapper is clean
```

**Linhas na bateria (3):** verde, neg-arm, e o controlo do rc 120.

---

## B2 — log rotation (847 MB -> 16 MB)

**Area:** token `log-rotation`. **O que prova a cura:** `receipt-20261014-p0-final-balance.md`
— em producao, `LOG_ROTATED from=847859845 B kept=16777081 B cap=64 MB`. **847 MB
passaram a 16 MB.** O `_open_log` (`sotto_webview.py:703`) roda acima de
`SOTTO_LOG_CAP_MB` (default **64 MB**) e guarda a cauda de `SOTTO_LOG_KEEP_MB`
(default **16 MB**). Re-medido hoje: `_main/webview-run.log` = **19.7 MB** — o tecto
esta a segurar em producao, nao so num ficheiro de rascunho.

**Instrumento:** `_main/log-rotation-oracle.py` — JA EXISTIA (1 363 B) e **nao sabia
dizer NAO**: nao tinha braco negativo e **nao tinha codigo de saida** (imprimia
`VERDICT: FAIL` e devolvia 0, logo uma linha na bateria nunca ficaria vermelha). Foi
estendido, mantendo a medicao original e acrescentando: o rc, a verificacao da
**fronteira de linha** (a versao antiga lia 80 bytes e perguntava por uma linha de 99 —
nunca podia ver um fragmento), o recibo `LOG_ROTATED`, o tecto, e os defaults do
codigo que embarca.

**Prova (live, rc=0, 8 checks):** `antes=3 000 000 B -> depois=1 048 559 B`; os
primeiros 100 B sao uma linha INTEIRA; recibo
`sotto: LOG_ROTATED from=3000000 B kept=1048500 B cap=1 MB`; defaults `64`/`16`
presentes na fonte; o log de producao (19.7 MB) abaixo do tecto.

**BRACO NEGATIVO:** copia do shell em `I:/cc-tmp` com o gatilho da rotacao desligado
(`if cap_mb > 0 and os.path.getsize(path) > cap_mb * 1024 * 1024:` -> `if False:`;
a string e unica no ficheiro, contagem 1). **Prova de que diz NAO** (rc=0):

```
FAIL a 3 MB file over a 1 MB cap IS rotated (the file shrinks) :: before=3000000 B after=3000000 B
FAIL the rotation leaves the app own receipt 'sotto: LOG_ROTATED' :: (nenhum)
FAIL the file is then BOUNDED by the cap it rotated under :: after=3000000 B cap_bound=1052672 B
NEG-ARM: RED as expected -- with the cure removed the log is NOT rotated
```

**Linha na bateria:** verde (ja estava) + `--neg-arm` (acrescentada por mim).

---

## B3 — log flood census (4,18 M linhas / 97 por cento)

**Area:** token `log-flood`. **O que o censo mediu** (`receipt-audit-p0-loop.md`,
`receipt-20261013-log-flood-census.md`): `_main/webview-run.log` = **808.6 MB /
5 627 892 linhas**, e QUATRO eventos eram **~786 MB — 97 por cento**:
`panel` 1 445 015 · `PANEL_SURFACE` 1 444 917 · `WINDOW_GEOMETRY` 1 444 916 ·
`PANEL_VISIBILITY_WRITE_FAILED` 1 145 063. Os tres primeiros diferem por **1** — a
assinatura de UM loop a emitir os tres por iteracao, medido a **p50 102/s, p99 264/s**.

**Instrumento:** `_main/log-flood-census.py` — JA EXISTIA (811 B) como **relator**:
imprimia a tabela e saia sempre 0 (`py -3 _main/log-flood-census.py --gate` devolvia
rc=0 sem sequer conhecer a flag). **Dei-lhe forma de gate**, com a decisao mais
importante declarada e medida:

* o veredicto e sobre uma **JANELA RECENTE** (`--window-hours`, default 12) e **nao**
  sobre o ficheiro inteiro — porque o rotador **guarda os ultimos 16 MB de proposito**,
  logo o arquivo do flood fica no ficheiro para sempre. Medido hoje: o ficheiro inteiro
  e **76.9 %** eventos do flood (top 21.5 %) enquanto as ultimas 12 h sao **0.7 %**.
  Um gate sobre o ficheiro inteiro acusaria o build de hoje do defeito de ontem e
  ficaria vermelho ate o ultimo byte retido envelhecer;
* RED quando UM evento passa `FLOOD_EVENT_PCT = 20 %` da janela ou os quatro passam
  `FLOOD_TOTAL_PCT = 50 %`. As barras vivem no espaco entre as duas medicoes
  (producao: 25.7 % / 97 %; vivo: 0.3 % / 0.7 %);
* `NO-DATA` (rc 0, dito em voz alta) quando a janela tem menos de 500 linhas **ou
  quando o log nao existe** — `_main/webview-run.log` e git-ignored (`*.log`,
  `.gitignore:14`), portanto um clone limpo nao tem nenhum, e um gate que alias
  respondesse RED seria uma mina para a proxima pessoa em vez de uma medicao.

**Prova (live, `--gate`, rc=0):** ficheiro 19.7 MB / 143 178 linhas; janela de 12 h =
29 917 linhas (`2026-10-14 13:59:08 -> 2026-10-15 00:37:58`), os quatro a **0.7 %**
(top 0.3 %, `PANEL_VISIBILITY_WRITE_FAILED` = **0**), minuto mais cheio 625 linhas;
ARQUIVO (historia) 76.9 %.

**BRACO NEGATIVO:** dois logs sinteticos escritos pelo proprio instrumento em
`I:/cc-tmp` (caminhos unicos por PID — duas lanes correm a bateria ao mesmo tempo,
medido hoje), nas **proporcoes de producao** a uma escala 1:257 e com o loop empacotado
a ~93 linhas/s para a assinatura de TAXA tambem estar la. **Prova de que diz NAO**
(rc=0):

```
FLOODED (the production signature)  lines=21313  top=26.4 %  four=100.0 %  -> RED
CLEAN (caption traffic)            lines=9210   top= 0.0 %  four=  0.0 %  -> GREEN
NEG-ARM: PASS -- the detector fires on the flood and stays quiet on caption traffic
```

Os DOIS sao precisos: um detector que dispara em tudo e tao inutil como um que nao
dispara em nada, e o braco CLEAN e o que prova que as barras nao sao um carimbo.

**Linhas na bateria (2):** `--gate` + `--neg-arm`. (A linha `--gate` ja tinha sido
escrita por outra lane **antes** de a flag existir — e por isso era um no-op que
passava; agora e um gate a serio.)

---

## B4 — emit queue bound (RISCO ABERTO CONHECIDO)

**Area:** token `emit-queue-bound`. **O risco, nas palavras em que foi registado:** a
correccao de `emit_async` tira o back-pressure do pump de legendas mas passaria a
enfileirar um callable por push (~43/s) **sem limite** no thread da UI — com um worker a
correr isso PODE saturar a fila do WinForms e travar a janela.

**Instrumento:** `_main/emit-queue-bound-oracle.py` (7 443 B) — **JA EXISTIA COMPLETO,
com os dois bracos**. Nao foi tocado: nao reescrever o que ja esta certo. Constroi o
shell com `object.__new__` (sem `__init__`, logo sem janela e sem locks) e substitui
so o que `emit_async` toca (`_post` e o core do WebView2).

**Prova (live, rc=0):** `VERDICT: PASS` — 100 pushes sem drain -> **1** callable;
1000 pushes concorrentes -> **1**; o script leva o payload MAIS NOVO (M99, nao M98);
2 canais -> 2 slots; um post DESCARTADO -> **3 de 3** pushes passam (o latch nao fica preso).

**BRACO NEGATIVO:** copia do shell com a guarda de coalescencia trocada por `pass`.
**Prova de que diz NAO** (rc=0):

```
NEG-ARM: RED as expected
   MUTANT: 100 undrained pushes posted 100 callable(s), expected 1
   MUTANT: 1000 concurrent pushes posted 1000 callable(s), expected 1
```

**Linha na bateria:** verde (ja estava) + `--neg-arm` (acrescentada por mim).

---

## B5 — queue_drops whitelist

**Area:** token `queue-drops`. **O defeito:** o worker imprime `queue_drops=` em CADA
`WORKER_STATS` e o `parse_worker_stats` guarda TODOS os tokens `key=value` — o shell
**ja tinha o numero** e a whitelist deitava-o fora. O chip "behind" do painel tinha um
ramo que **nunca pode disparar**: esperava por um campo que este ficheiro dropava.

**Instrumento:** `_main/queue-drops-whitelist-oracle.py` — JA EXISTIA (1 377 B, 3
casos) e ganhou: um 4.º caso (um valor que NAO e numero tambem fica AUSENTE, nunca 0) e
o braco negativo.

**Prova (live, rc=0):** 4/4 — `queue_drops=12` chega ao payload como `12.0`;
`queue_drops=0` fica `0.0`; ausente fica AUSENTE (nunca zero); `n/a` fica AUSENTE.
(`rate` continua FORA, e isso tambem esta pinado: a cura nao pode virar "whitelistar tudo".)

**BRACO NEGATIVO:** copia do shell com o tuplo sem `queue_drops`
(`for key in ('peak', 'blocks', 'queue_drops'):` -> `for key in ('peak', 'blocks'):`,
string unica). **Prova de que diz NAO** (rc=0):

```
FAIL queue_drops printed by the worker -> payload={'tag': 'stats', 'peak': 0.5, 'blocks': 7.0}
FAIL zero drops stays zero            -> payload={'tag': 'stats', 'peak': 0.5, 'blocks': 7.0}
ok   absent -> absent (not zero)      <-- os casos 3 e 4 ficam verdes: o controlo e preciso
ok   unparseable -> absent (not zero)
NEG-ARM: RED as expected -- ... (2 case(s) failed)
```

**Linha na bateria:** verde (ja estava) + `--neg-arm` (acrescentada por mim).

---

## B6 — second pass (M3) opt-in (a passagem que custava 50,9 por cento)

**Area:** token `second-pass`. **A decisao e o numero:** a segunda passagem M3 custava
**50.9 % de todo o tempo de inferencia** na corrida do proprio dono, para um texto que
diferia do ultimo parcial em 5 de 5 casos e nao era melhor. Fica DESLIGADA e
`SOTTO_SECOND_PASS=1` traz-la de volta.

**O risco desta area tem UM CARACTER de largura:** virar aquele default poe a passagem
— que custa metade da maquina — de volta LIGADA para toda a gente, em silencio.

**Instrumento:** `_main/second-pass-default-oracle.py` — JA EXISTIA (1 312 B, 6 casos
de ambiente) e ganhou: o braco negativo e **dois pins estruturais** (um interruptor que
ninguem consulta nao e uma cura).

**Prova (live, rc=0):** os 6 casos (omissao->DESLIGADO, `=1`->LIGADO, `=0`->DESLIGADO,
`=true`->LIGADO, `=vazio`->DESLIGADO, `=yes`->LIGADO) **+** os dois pins:
`_second_pass_enabled` e CONSULTADO no caminho vivo (2 ocorrencias: a definicao e
`if _second_pass_enabled():`) e o docstring ainda carrega o **50.9** que decidiu.

**BRACO NEGATIVO:** copia do worker em `I:/cc-tmp` com o default virado
(`os.environ.get("SOTTO_SECOND_PASS", "")` -> `"1"`, string unica). **Prova de que diz
NAO** (rc=0):

```
FAIL omissao -> DESLIGADO -> True      <-- a passagem volta a estar ON sem ninguem pedir
ok   =1 -> LIGADO / =0 -> DESLIGADO / =true -> LIGADO / =vazio -> DESLIGADO / =yes -> LIGADO
NEG-ARM: RED as expected -- with the default flipped the omission case reads LIGADO (1 case(s) failed)
```

**Linha na bateria:** verde (ja estava) + `--neg-arm` (acrescentada por mim).

---

## B7 (nao estava no brief, mas era a ultima lacuna) — panel hide gate at startup

**Area:** token `panel-hidden-at-startup`. **O defeito:** apagar UMA linha de
`_on_before_show` (`self._ui(self._subscribe_core_ready)`) deixava o `py_compile` a
rc=0, o shell a carregar bem, e **o painel na mesa do dono** — invisivel ao compilador,
as linhas de log que SAIRAM, e ao census de 60 s da casa. E o mesmo defeito que a
regra do AGENTS.md sobre o *flash* no arranque descreve.

**Instrumento:** `_main/panel-hidden-at-startup-oracle.py` — **JA EXISTIA** (40 301 B) e
**nao estava registado**. A razao registada numa nota de outra lane era "escreve e corre
copias do shell". **Medi antes de acreditar:** e *HEADLESS BY CONSTRUCTION* (nenhuma
janela, nenhum WebView2, nada do que o dono corre e tocado), escreve os mutantes num
`tempfile.TemporaryDirectory` e **importa-os** — importar uma copia nao e lancar nada, e
e exactamente o que os meus proprios bracos negativos fazem.

**Prova de que nao abre janela nenhuma** (census meu, a volta da corrida, com a app do
dono VIVA):

```
BEFORE: visible_windows=11  python_procs=15
  ... ORACLE GREEN failures=0   (rc=0, 1.4 s)
AFTER : visible_windows=11  python_procs=15
```

**Prova de que diz NAO** (verbatim do proprio oraculo — 144 decisoes de visibilidade,
6 cenarios x 3 timings de init x 8 repeticoes, 4 mutantes):

```
[PASS] ARMED-ONCE before_show fired twice -> guard subscribed once (handlers=2: 1 pywebview + 1 shell)
[PASS] MUTATION arm-line-deleted   expected=caught; delete the arming call from _on_before_show; wiring failures=2 -> the oracle catches it
[PASS] MUTATION guard-never-installed expected=caught; the guard exists but is never subscribed; wiring failures=3 -> the oracle catches it
[PASS] MUTATION pre-fix-shape      expected=caught; the exact pre-fix shell; wiring failures=2 -> the oracle catches it
[PASS] MUTATION ticket-repro       expected=immune; TICKET-55a4ab4b157bdd26bb9629c7's own repro -> visibility intact
ORACLE GREEN failures=0
```

**Linha na bateria:** `['_main/panel-hidden-at-startup-oracle.py', 'panel hide gate at startup (headless, 4 mutants)']`.

---

## A BATERIA

`node _main/instruments-battery.mjs` -> **rc=0**; a linha verbatim:

```
SUMMARY: 131/131 instrument(s) rc=0; failed=0; launches=0 (no shell, app or worker is opened --
the ONE run.cmd invocation in this list is its --help pre-flight, which argparse answers and exits;
measured 2026-10-12: 0 processes left)
BATTERY-EXIT=0
```

O ficheiro da bateria nao mudou entre o inicio e o fim da corrida: **15 422 B**, sha256
`187176C0B0244A8EADF5D04664960CF10850F816F0F94AC92C89D0B320B09C6E` — logo o 131/131 e
uma medicao desta revisao e nao de uma revisao a meio de outra lane.

As nove linhas desta lane (as verdes de B2/B4/B5/B6 ja existiam e passaram a correr os
instrumentos com a forma de gate; as outras sao minhas):

| area | linha | cor |
|---|---|---|
| B1 | `run-cmd-exit-oracle.py --arms bogus,help --no-gaps` | verde |
| B1 | `... --neg-arm` | RED (pre-fix) |
| B1 | `run-cmd-exit-oracle.py --temp-arm` | RED (rc 120) |
| B3 | `log-flood-census.py --gate` | verde |
| B3 | `log-flood-census.py --neg-arm` | RED + GREEN sinteticos |
| B2 | `log-rotation-oracle.py --neg-arm` | RED |
| B4 | `emit-queue-bound-oracle.py --neg-arm` | RED |
| B5 | `queue-drops-whitelist-oracle.py --neg-arm` | RED |
| B6 | `second-pass-default-oracle.py --neg-arm` | RED |
| B7 | `panel-hidden-at-startup-oracle.py` | verde (144 decisoes, 4 mutantes) |

---

## PINS (regra 2 do AGENTS.md: tamanho, mtime e/ou sha256)

| ficheiro | bytes | fim de linha | sha256 |
|---|---|---|---|
| `_main/run-cmd-exit-oracle.py` | 63 811 | 0 CRLF / 1261 bare LF | `60AC3D0EC317810400EE6692AB679C64B826954CE34561018A688034CF51884D` |
| `_main/log-rotation-oracle.py` | 10 750 | 0 / 237 | `0B9DC9E3521A47D3B981B9D3D24BFF0567462F0CFF1B4BE03B1BAC6F60290C82` |
| `_main/log-flood-census.py` | 13 594 | 0 / 292 | `FED6FDECA307E4061F4868A88742671125FCC5658DE0C8AD1EB3926D20B050A0` |
| `_main/emit-queue-bound-oracle.py` | 7 443 | 0 / 223 | `4855495866461F94E8331BA1E798121497143D8DBB7915757266B4A734945E3F` |
| `_main/queue-drops-whitelist-oracle.py` | 6 439 | 0 / 148 | `23204779F684FDD165DE50485A1467264C14E0FAB41DA80285FA54031E6ABA1B` |
| `_main/second-pass-default-oracle.py` | 6 821 | 0 / 154 | `A60F2F2F6B902169DE65D18BFD833B34ADD1A4A276F04273BB20DBCF521428A8` |
| `_main/instruments-battery.mjs` | 15 422 | 213 CRLF / 0 bare LF | `187176C0B0244A8EADF5D04664960CF10850F816F0F94AC92C89D0B320B09C6E` |
| `app/webview/sotto_webview.py` (NAO tocado) | 524 312 | 10 097 CRLF / 0 bare LF | `D888D0CBF1D658802D126D41045BC3013E7C08EA928957764A8122F60A0621E2` |
| `app/webview/run.cmd` (NAO tocado) | 13 250 | 227 CRLF / 0 bare LF | `683E9C7B742F5498A3BA18B3D91A3441931A7B686E077A75D4D17C7D5413A39B` |
| `worker/sotto_worker.py` (NAO tocado) | 335 778 | 6 344 CRLF / 0 bare LF | `A23217E552FEB8ADAEAA1FBED4E4498D63EBD26C999095278C18C9E3909BF0B4` |

**Nenhum ficheiro de produto foi editado nesta lane.** Os instrumentos leem o produto e
constroem mutantes em `I:/cc-tmp` (ou numa copia temporaria apagada num `finally`).

---

## O QUE NAO FIZ / NAO MEDI (F6: o que nao foi medido diz-se NAO MEDIDO)

1. **Nao lancei a app, o shell, o worker, o WebView2 nem um browser.** Nenhum braco
   prova o comportamento do WebView2 real; tudo o que esta acima e bytes, AST ou
   chamadas em processo ao ficheiro que embarca.
2. **NAO MEDIDO: se a fila do WinForms chega a crescer na app a serio.** O limite da
   fila esta provado (B4); a profundidade nunca foi instrumentada, logo a causa do
   freeze continua NAO ATRIBUIDA.
3. **NAO MEDIDO: a taxa viva do loop de superficies.** O censo mede o que esta no log;
   a assercao de taxa (p50 102/s) e do recibo da auditoria de 2026-10-13, nao re-medida
   aqui. O que medi hoje e a COMPOSICAO: o arquivo ainda e 76.9 % flood, a janela de
   12 h e 0.7 %.
4. **Nao fechei a lacuna do `panel.js`.** `JS<->Python surface loop guard` foi
   fechada por outra lane (`_main/surface-loop-oracle.py`) enquanto eu trabalhava; nao
   a toquei porque o que e meu nessa area e o CENSO do flood (B3), nao a guarda.
   **Nao MEDI o oraculo dela** — nao o corri, nao o li, e nao afirmo nada sobre ele
   alem do que o `cobertura-oracle` diz (a area tem uma linha que corre).
5. **Nao toquei em `app/shadowplay/`, nem em `_base-*/` ou `_logs-before/`.** Nada de
   `git add -A`; os ficheiros desta lane sao NOMEADOS (a lista esta nos pins).
6. **A bateria tem mais de uma lane a escrever no mesmo ficheiro em simultaneo**
   (medido: duas execucoes de `instruments-battery.mjs` vivas ao mesmo tempo, e o
   `instruments-battery.mjs` foi reescrito por outra lane enquanto eu trabalhava). Os
   pinos acima sao a fotografia no momento em que escrevi isto; quem repetir a
   verificacao deve re-medir antes de citar (regra 1 do AGENTS.md).
