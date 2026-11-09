# RECIBO — o ciclo carga/largada que se excita a si proprio (2026-11-09)

Tudo o que segue foi medido nesta arvore, hoje, com o comando ao lado. Onde digo `PASS`, o `rc`
esta' colado; onde digo `UNMEASURED`, digo-o por palavras.

## 1. A queixa e a medicao que ela obrigou

DM do watcher (`I:\!watcher\state\herdr-inbox\dm-00dbf74d817f8b2c3ddd.md`, stutter 50452):
`SUBTOTAL 50452 -> 2 04m/8/s`, `O D3 e top`, e o cabecalho do log do worker:

```
REDUX_ENGINE_LOAD 82   REDUX_ENGINE_RELEASE 70        (numa execucao)
REDUX_ENGINE_LOAD_MS 1900                              (1,9 GB lidos do disco por carga)
par mais apertado: carga 06:55:15,304 -> largada 06:55:46,571   = 31 s
```

A leitura da DM que este recibo aceita: **o ciclo regula mal porque se excita a si proprio** — o
nivel sobe enquanto a carga pesa, e cai quando ela acaba, e a carga seguinte (que o nivel pediu) e'
o que produz a proxima subida. Nao ha' nada de "estragado": ha' dois relogios que nao conversam.

## 2. A decisao (e o que foi RECUSADO)

* **A LARGADA NUNCA E' RECUSADA.** Primeira versao desta cura tinha um piso `MIN_LOADED_S = 120 s`
  em `release()` ("nao largar o que acabou de se carregar"). **Retirada antes de commitar**: um
  modelo que a pressao pediu para sair tem de sair, e um piso na largada e' exactamente a inversao
  que o dono proibe (a maquina e' o que nao pode sofrer). Largar devolve 460 MB e e' barato;
  **o que custa 1,9 s de disco e a rajada de CPU e' VOLTAR**.
* **O PISO E' NO LADO DA CARGA.** `ParakeetEngine.reload_floor_left()` conta os segundos que faltam
  para o motor poder voltar a carregar: `max(RELOAD_FLOOR_S, RELOAD_FLOOR_LOAD_FACTOR * load_s)`
  = `max(60 s, 10 x load_s)` — um motor cuja leitura custa 20 s espera 200 s.
* **O LOTE DO INTERVALO ESPERA; UMA CAUDA TENTA E DIZ QUE TENTOU.** `maybe_kick` passa
  `respect_memory_floor=True` e devolve `False` dentro do piso, com o audio na fila e o tick seguinte
  a tentar outra vez (`REDUX_BATCH_DEFERRED reason=reload-floor wait_s=.. held_s=..`). Uma cauda nao
  tem tick seguinte, logo tenta e escreve `REDUX_BATCH_RELOAD_FLOOR ... attempting=anyway` — uma
  recusa muda seria perda do ultimo minuto do dono.

## 3. O que mudou, por ficheiro

| ficheiro | mudanca |
|---|---|
| `worker/engine_policy.py` | `RELOAD_FLOOR_S = 60.0`, `RELOAD_FLOOR_LOAD_FACTOR = 10.0`; `ParakeetEngine.loaded_t`/`released_t`, `reload_floor_left()`, `release_age_s()`; `release()` regista o instante e **nunca recusa** |
| `worker/engine_switch.py` | `flush_pending` consulta `reload_floor_left()` do motor: deferivel (intervalo) ou "tenta e diz" (cauda) |
| `_main/redux-arm-weights-oracle.py` | ARMs **R1-R8** (o piso no motor e no lote) + mutante **M5** que remove o deferimento |
| `_main/load-shedding-oracle.py` | `_FakeEngine.reload_floor_left()` (0 por omissao: a arm 11 continua a medir o comportamento de antes) |

## 4. Verificacao — os tres comandos e os tres vereditos

```
python _main/redux-arm-weights-oracle.py
  GREEN ARM SUMMARY: 28/28 checks green; red=[]
  VERDICT: PASS                                        rc=0

python _main/redux-arm-weights-oracle.py --neg-arm
  MUTANT VERDICT M5-reload-floor-removed: ... missing=[] extra=[] -> OK
  MUTANT VERDICT M4-control-comment-only-must-move-nothing: expect_red=[] observed_red=[] -> OK
  VERDICT: PASS                                        rc=0

python _main/load-shedding-oracle.py
  LOAD-SHEDDING GREEN -- arms=240 pass=240 fail=0       rc=0
python _main/load-shedding-oracle.py --neg-arm
  NEG-ARM(largada-cpu) PASS ... NEG-ARM(largada-cega) PASS    rc=1
```

As arms novas, com os numeros delas:

| arm | medido |
|---|---|
| R1 piso zero antes de largar | `floor_left=0.0` |
| R2 a largada nunca e' recusada | `release=True releases=1 loaded=False` |
| R3 o piso comeca em 60 s | `floor_left=60.0` (`RELOAD_FLOOR_S=60.0`) |
| R4 o piso passa | `floor_left=0.0` aos 61 s |
| R5 o piso cresce com o custo da carga | `floor_left=200.0` para `load_s=20` (`factor=10.0`) |
| R6 o lote espera o piso | `kicked=False deferred=1`, linha `reason=reload-floor` |
| R7 uma cauda tenta e diz que tentou | linha `REDUX_BATCH_RELOAD_FLOOR ... attempting=anyway` |
| R8 sem piso o lote nao espera | `deferred=0`, nenhuma linha |

M5 (o deferimento arrancado com `if False:`) derruba **R6 e R7 e mais nada**; o mutante de controlo
(um comentario) nao move arm nenhuma — o instrumento nao avermelha por qualquer diff.

## 5. O QUE NAO ESTA' MEDIDO

* **A contagem de cargas depois da cura, na instancia do dono, e' UNMEASURED.** O worker vivo corre o
  codigo de antes de hoje; a cura e' do FICHEIRO. O numero que a fecha e'
  `grep -c REDUX_ENGINE_LOAD` no log dele por hora depois de um worker novo — e o worker novo e'
  arrancado pelo artefacto (matar o pid cujo `cmdline` contem `sotto_worker.py`; a shell respawna em
  ~1 s), nunca pela mao dele na app.
* **O efeito no stutter** so' se afirma com o instrumento do watcher e a mesma janela depois.
* O `ReleaseGate` da largada (commit/CPU) nao foi tocado por esta cura.

## 6. As outras duas regras da MESMA DM, e quem as cumpre

A DM propunha tres regras. A #2 e' a deste recibo. As outras duas **ja' estao no ficheiro**, no
`ReleaseGate` de `app/webview/load_shedding.py:696-753`, e a medicao de hoje diz por que o caso do
log do dono passa a ser recusado:

| regra da DM | mecanismo | numero |
|---|---|---|
| 1. nao largar o que o proximo passe precisa sem o `shed` PERSISTIR | `may_release` devolve `'memoria-sustentada-espera'` com `wait_s` no log | `RELEASE_PERSIST_S = 120.0` s |
| 3. preferir PAUSA a unload quando ha' commit | `commit < HIGH_PCT` -> `'cpu-apenas'`, o modelo FICA (o modo `shed` ja' pausou o lote) | `HIGH_PCT = 88.0`, `VERY_HIGH_PCT = 94.0` |

O par medido na DM -- `LOAD_ACTION_PUBLISHED ... commit=59.0% cpu=99.1%` seguido de
`REDUX_ENGINE_RELEASED` -- e' exactamente o caso `cpu-apenas`: **59,0 % < 88,0 %**, logo a largada
e' recusada e o log diz `REDUX_ENGINE_KEPT ... why=cpu-apenas`. Aquela largada aconteceu antes de a
guarda estar no caminho; com ela, o ciclo nao comeca (nao ha' largada) e, se houver largada por
memoria real, o piso da #2 impede a recarga imediata.

## 7. O que a DM pediu em `load()`

A DM apontava `worker/engine_policy.py:201-222` (`load()`) como o sitio do ciclo. Este recibo
**nao poe o piso dentro do `load()`**: um piso no `load()` recusaria a carga do caminho de STREAM
(`transcribe()` chama `load()`), ou seja calaria o motor ao vivo para poupar disco -- a inversao que
o dono proibe. O piso vive no unico chamador que existe para decidir cargas: o LOTE
(`flush_pending`), que e' quem pode esperar sem perder audio.

## 8. O REPLAY DO LOG DO DONO (2026-11-09, 12:0x) -- quantas das 82 cargas a cura corta

Instrumento: as duas funcoes que EMBARCAM (`load_shedding.ReleaseGate.may_release` e a aritmetica
`max(60 s, 10 x load_s)`), alimentadas com as linhas do proprio `_main/webview-run.log`
(65 340 820 B) e com o relogio real daquelas linhas. Nao e' simulacao de modelo: e' o predicado
publicado a julgar o passado medido.

```
LOAD_ACTION_PUBLISHED: 443   (leve 151, alta 208, muito-alta 84)
REDUX_ENGINE_RELEASED: 70    REDUX_ENGINE_LOAD: 80-82
```

**O ReleaseGate sobre as 84 publicacoes `muito-alta` do log:**

| razao | publicacoes | larga? |
|---|---|---|
| `cpu-apenas` (commit < 88 %) | **69** | NAO |
| `memoria-sustentada-espera` (commit >= 88 % ha' < 120 s) | 5 | NAO |
| `commit-ilegivel` (direccao segura, OOM) | 4 | sim |
| `memoria-sustentada` (>= 88 % por >= 120 s) | 3 | sim |
| `memoria-emergencia` (>= 94 %) | 3 | sim |
| **total** | **84** | **10 largam, 74 nao** |

Ou seja: das **70 largadas** que o log registou, **no maximo 10** teriam acontecido com a guarda no
caminho. As 69 em `cpu-apenas` sao exactamente o regime que a DM nomeia (`commit=59.0% cpu=99.1%`):
a pressao e' de CPU, o modelo nao e' o recurso escasso, e o modo `shed` ja' tinha pausado o lote.

**O piso da recarga sobre os pares release -> load do mesmo log:**

| piso | pares adiados |
|---|---|
| 60 s | **15 de 59** |
| (contraste) 120 s | 26 de 59 |

`load_s` no log: min 0,94 s, mediana 2,28 s, max 19,35 s — logo o piso efectivo e' 60 s na maioria
das cargas, e `max(60, 10 x 19,35) = 193,5 s` para a carga mais cara. O par mais apertado medido
(4,4 s) esta' entre os adiados.

**O que este replay NAO prova:** que a instancia viva pare de ciclar -- o worker em execucao corre o
codigo de antes de hoje. O que ele prova e' que, com estas duas guardas no caminho, o passado medido
nao se reproduz: 74 das 84 janelas severas nao largam nada, e 15 das recargas ficam a espera.
