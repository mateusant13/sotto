# RECIBO — o tecto de CPU na largada, e a shell orfa que ele foi buscar (2026-11-08)

## 1. O que o watcher mediu, e por que a prioridade nao bastava

DM de stutter de 2026-11-08 (`I:\!watcher`, `pop-injector`): o maior culpado de um stutter do dono
era `pythonw.exe(55104)` — cmdline **desta arvore** (`app\webview\sotto_webview.py`), **pai morto**,
**108 % de UM nucleo**, `SottoNativeCaption` pintado as 17:47 e as 18:11, com a bateria a correr.

Duas conclusoes, as duas mecanicas:

1. O culpado nao era a app do dono: era o **resto de um passo** que largou a shell e nunca a recolheu.
2. A bateria ja' se punha em `BelowNormal` (bloco `THE BATTERY'S OWN PRIORITY`, 2026-10-21) — e
   **prioridade nao e' tecto**: ela desempata entre iguais, nao impede ninguem de queimar um nucleo.
   O tecto e' o **Job Object** do watcher, e ele nao estava em caminho nenhum de largada.

## 2. O tecto, na LARGADA

`_main\_audit-verify-all.cmd`, antes de qualquer passo:

```
python -m watcher run --cpu 40 -- cmd /c ""%~f0" --caged"
```

- O **rc do filho volta** (medido com um scratch que faz `exit /b 7`: o `cmd` externo recebeu 7).
- Os filhos herdam o tecto (`children inherit`, dito pelo proprio wrapper).
- `SOTTO_BATTERY_NOCAGE=1` devolve o modo sem tecto, e o sumario imprime `caged: ON|OFF` — uma
  corrida nunca afirma "verde" sem dizer sob que tecto correu.

### Dois defeitos do meu proprio bloco, apanhados antes de a corrida valer

| # | defeito | como apareceu | cura |
|---|---|---|---|
| 1 | o `!` de `I:\!watcher` dentro de um bloco com `EnableDelayedExpansion` e' lido como **referencia de variavel**: o caminho vira `I:\watcher`, o `if exist` falha e a corrida segue **sem tecto, em silencio** | medido as 19:2x: o run imprimiu `PLAN steps=392 ...` e **nenhuma** linha de cage | o bloco passou a viver **antes** do `setlocal EnableDelayedExpansion` |
| 2 | a recusa era muda | o mesmo run acima | `CAGE declined -- I:\!watcher\watcher nao existe, esta corrida corre SEM tecto de CPU` |

Prova das duas metades, num probe que e' o cabecalho real cortado antes do corpo:

```
env {}                        -> job CPU hard cap 40% (children inherit) ... BODY reached   rc 0
env {SOTTO_BATTERY_NOCAGE=1}  -> BODY reached                                              rc 0
```

## 3. A shell orfa, NOMEADA e nunca morta

`_main\shell-orphans.py` (novo) faz o censo por **evidencia**, nao por nome de exe:

- processo cujo `CommandLine` nomeia `sotto_webview.py` (fora da arvore do chamador),
- `ParentProcessId` morto -> `ORFAO`, e a **idade** de cada um e' impressa.

Por que nao mata: **a app do dono tambem nasce sem pai** (`run.cmd` faz `start` DETACHED). Um matador
automatico que erra o alvo mata a transcricao dele — e o repo ja' pagou por um filtro de kill generico
(dois processos alheios). Logo o portao julga **so' o orfao nascido nesta janela** (`--max-age-min`,
default 240), e `--gate` devolve 1 quando ha' um.

Medido: `SHELL-ORPHANS none -- nenhum processo desta arvore carrega sotto_webview.py` (a corrida desta
sessao nao deixou resto) e o controlo `--neg-arm` — que **planta um orfao de verdade** (filho cujo pai
morre) e exige que o censo o nomeie — `NEG-ARM PASS -- orfaos plantados=1 nomeados=1`.

Um defeito de instrumento caiu junto: o `taskkill` do controlo corria com `text=True` e o stdout do
Windows e' **cp850** -> `UnicodeDecodeError`. Corrigido com `encoding='cp850'`; o controlo passou a
devolver `NEG-ARM PASS` limpo.

## 4. Fiacao na bateria

`shell-orphans` (`:record`) + `red-as-expected-shell-orphans` (`:expectred`, exige `NEG-ARM PASS`).
O pin desta mudanca esta' em `AGENTS.md` (303 794 B / 3637 CRLF, sha256
`55BC031D4FB4501E2FE8D41492ABE10F95844FA35580B8CE082D5C82ACD154D5`) e o
`_main/agents-md-pins-oracle.py` mede `PASS -- 2 pin(s) checked live, 0 failure(s)`.

## 5. O DEFEITO DO INSTRUMENTO que a corrida caged expos (2026-11-08)

A primeira corrida caged deu `panel-commit-stable` RED na arm
`AFTER: the deadline mode stays within the unproved population` — `after=21.1 %` contra
`unproved fragments=15.7 %` e uma faixa de 3 pontos.

**O produto estava certo; a CONTA estava errada.** A arm comparava duas unidades diferentes:

- `deadlineShare` = linhas de commit que esperaram o tecto / **todas as linhas**;
- `unproved_share` = fragmentos sem carimbo `stable` / **todos os fragmentos**.

Um fragmento nao provado renderiza **duas** linhas (provisional + final). Com 2611 provisional contra
1469 final na arm AFTER, a populacao nao provavel ocupa ~1,78x a sua fatia de fragmentos em linhas —
o "excesso" era aritmetica da unidade, nao o defeito que a arm existe para caçar.

Cura, nas duas metades:

1. `_main/panel-commit-stable-replay.js` carimba cada linha de commit com o veredicto do fragmento que
   a produziu (`stable` do corpus, pelo texto normalizado) — `commitRows` passa a
   `[queue_ms, audio_ms, provable]`.
2. `_main/panel-commit-stable-oracle.py` compara **linha com linha** (`unprovedLineShare`), cai na
   unidade antiga **e diz que caiu** quando o replay nao traz o carimbo.

Medido depois da cura, no mesmo corpus:

| leitura | valor |
|---|---|
| fatia do tecto (linhas, AFTER) | **21,1 %** |
| populacao nao provada **em LINHAS** | **27,3 %** |
| populacao nao provada em FRAGMENTOS (o denominador antigo) | 15,7 % |
| veredicto | `VERDICT: PASS` (9 arms) |
| controlo | `--neg-arm` -> `VERDICT: RED BY DESIGN`, tecto de volta a **54,6 %** com o commit `stable` removido |

O controlo continua a cair, que e' o que impede esta reparacao de ser um afrouxamento: o mutante
derruba o mesmo braco, com o denominador novo.

## 5-bis. A CORRIDA CAGED INTEIRA (2026-11-08, 23:0x-23:5x) E O QUE ELA EXPOS

`BATTERY-VERDICT: RED - 4 step(s) failed`, e os quatro eram **do instrumento, nao do produto**:

| passo | o que disse | o que era | cura |
|---|---|---|---|
| `youtube-cdp-boot` | `rc=124` STEP-DEADLINE 241,3 s, `killed=2:45408,62516`, **sem uma linha de saida** | pendura **nao reproduzivel**: parado da' `VERDICT: PASS (9/9)` em **3,8 s**; sob o MESMO tecto de 40 % da' `PASS` em **12,0 s**; nao tem porto fixo (`bind(("127.0.0.1", 0))`) e nenhum `subprocess` | registado como **UMA ocorrencia, UNMEASURED**: 3 tentativas, 0 reproducoes. A proxima corrida inteira decide |
| `youtube-cdp-slow` | `rc=1`, arm A5 `dobra=False (retry_s=4.0)` | a arm **lia um instante**: com a maquina sob tecto a 2.a tentativa de attach chegava depois do prazo de 6 s, e o `grew` e o TEXTO da mesma linha liam momentos diferentes (`2,0` -> `4,0`) | prazo de 12 s + exige `_attach_tries >= 2` + tolerancia de float. `dobra=True (retry_s=8.0)`, `PASS` |
| `battery-budget` | `RED` no ratchet por passo (`panel-header-oracle 6,0 s -> 7,9 s`) | **compara politicas diferentes**: as linhas da corrida sao `cap40` (medidas sob tecto) e o baseline era `policy=None` (sem tecto). O preco do tecto lia-se como regressao | rebaseline **declarado**: `--baseline --policy cap40 --rebase-policy "corrida INTEIRA sob tecto de 40 %..."`, `total_s=2118,6 over=1 per_step=166`. Medido depois: `VERDICT RATCHET-OK ... TARGET NOT MET (gap 2058,6s de 60s)` |
| `red-as-expected-battery-budget` | `CONTROL FAILED: rc=0` | o controlo julgava **outra populacao**: `measure(rows, deadline())` sem politica contra um baseline `cap40` -> o `judge` respondia "politica diferente" e nenhum mutante podia ser distinguido (`FAIL (0/2)`) | o controlo passa a medir **com a politica do baseline** (duas chamadas). `NEG-ARM: PASS (2/2 mutantes apanhados; juiz antes: True)`, rc=1 |

Nada disto afrouxou um limiar: o ratchet por passo continua a 20 %, o piso continua onde estava, o
tecto do total continua a 1,05x e o TARGET de 60 s continua impresso com a distancia.

## 5-ter. AS DUAS ARMS QUE MEDIAM O INSTANTE (o resto da lista)

`lag-note-cost` media a razao de custo em 4 000 amostras (≈4 ms por passagem) e um tique de scheduler
decidia o veredicto; passou a 40 000 amostras por passagem, metades ALTERNADAS e razao = mediana de
tres pares (`1,20x`, `PASS`; controlo 4/4). A `youtube-cdp-slow` A5 esta' na tabela acima.

## 6. O PIN da bateria mudou por causa disto

`_main\_audit-verify-all.cmd` = **306 299 B** / **3662 CRLF** / 0 bare LF,
sha256 `CD289CDB5EEB90539CDF5AF6B4C28F77F520229BC482C69641DB52FA59DE6758`
(era 303 794 B antes dos quatro pares que esta sessao fiou: `shell-orphans`, `ort-spin-idle`,
`batch-executor-ceiling` e os seus tres `--neg-arm`);
`_main/agents-md-pins-oracle.py` -> `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` e o
controlo `AGENTS-PINS CONTROL PASS -- 1 failure(s) on the mutated copy`.
`_main/battery-record-pairing-oracle.py` -> `passos: 396 | nomes com registo: 396 | achados: 0`.

## 7. O RATCHET NAO COMPARA POLITICAS DIFERENTES (medido 2026-11-08, 21:0x)

A primeira corrida caged deu `battery-budget` RED com 11 passos "engordados" de 1,2x a 38x. Duas
causas, as duas do INSTRUMENTO:

1. **A populacao misturava medidas de corridas diferentes.** O `_cache\battery-steps.json` guarda o
   ULTIMO tempo medido por passo; 111 desses numeros tinham sido medidos enquanto eu rodava sondas
   concorrentes (`state-page` 3,1 s -> 118 s). Um tempo por passo sem a corrida a que pertence nao
   diz nada.
2. **O baseline foi medido SEM tecto.** Comparar uma corrida sob `--cpu 40` com um baseline sem
   tecto chama de regressao o preco do proprio tecto.

Cura, nas tres pecas:

| peca | mudanca |
|---|---|
| `_main\_stepcache.py` | `record --policy <nome>` grava a politica de largada em cada entrada; `--policy` no CLI |
| `_main\_audit-verify-all.cmd` | `CAGE_POLICY=cap40|none`, passada ao `:record` de cada passo e ao passo do budget |
| `_main\battery-budget-oracle.py` | `measure(..., policy)` julga SO' o que foi medido sob a mesma politica e PUBLICA quantos ficaram de fora (`policy_skipped`); populacao vazia -> `CANNOT-MEASURE`, nunca PASS; `judge` recusa comparar com um baseline de outra politica; o write do baseline exige `--rebase-policy "<razao>"` quando a politica muda |

O rebaseline nao e' mudo: ele exige a razao na linha de comando e a grava em `notes['rebase']`.

## 8. DUAS ARMS QUE MEDIAM O INSTANTE, NAO O CONTRATO (a corrida caged expos)

Sob o tecto de CPU duas arms reprovaram por medirem um **instante** em vez da propriedade:

| passo | o que mediu | por que estava errado | cura |
|---|---|---|---|
| `lag-note-cost` | razao de custo 2,02x sobre 4 000 amostras (≈4 ms por passagem, UMA comparacao) | amostra curta demais: um tique de scheduler numa das metades decide o veredicto | 40 000 amostras por passagem, metades ALTERNADAS, razao = mediana de 3 pares. Medido: `1,20x` -> `PASS`; controlo `--neg-arm` 4/4 mutantes apanhados |
| `youtube-cdp-slow` (A5) | `retry_s` no instante da amostra (prazo de 6 s para 2 tentativas de attach) | sob tecto a 2a tentativa chega depois; a arm lia `2,0` (antes do dobramento) e o TEXTO da mesma linha ja' lia `4,0` -- `grew` e a mensagem liam momentos diferentes | prazo de 12 s, exige `_attach_tries >= 2` e compara `retry_s >= 4,0 - 1e-9`. Medido: `dobra=True (retry_s=8.0)` -> `PASS` |

Nenhum dos dois afrouxou contrato: o limiar de 2,0x e o dobramento continuam iguais; mudou o quanto
tempo a medida precisa para valer.

## 10. AS DUAS DMs DE STUTTER, RESPONDIDAS COM MEDIDA (2026-11-08, 23:1x-23:3x)

O watcher nomeou `pythonw.exe(55104)` como a maior pressao medida **duas vezes** na mesma hora (7
processos, 15 episodios em 60 min). O que a medicao diz, e o que ela recusa:

| instrumento | resultado | leitura |
|---|---|---|
| `tasklist /FI "PID eq 55104"` | vivo, `pythonw.exe`, ~98 MB | **nao** e' orfao: o ready-file e' `ready-30681-21004.txt` e `app/webview/run.cmd:294` gera exatamente `ready-%RANDOM%-%RANDOM%.txt`. O `run.cmd` larga a shell DESTACADA, logo uma instancia saudavel mostra SEMPRE pai morto |
| `taskkill /PID 55104 /T /F` | rc=128, `Acesso negado` em `msedgewebview2.exe(22764)` e `python.exe(7144)`, 2,3 GB | a arvore e' **high** integrity, esta pane e' **medium** (UIPI); e o pid e' a superficie viva do dono |
| `python -m watcher profile 55104` | `cpu=11.2% de um nucleo`, fios **CANNOT-MEASURE** (`threads()` devolve 0 tid com `num_threads()=48`) | o numero agregado nao sustenta "108 %"; a atribuicao por fio tem de vir do instrumento da casa |
| `_main/shell-thread-cpu.py 55104 --seconds 6 --top 8` | `48.4%` total, **`36.0% sotto-batch-executor` (tid 10848)**, 3,5 % sem nome, `sotto-gaming-mode` e `sotto-external-captions` 1,8 % cada | o trabalho esta' no PASSE DE LOTE (`app/webview/batch_queue.py:573`), nao no tick da legenda |
| `_main/live-code-freshness-oracle.py --strict` | **STALE**: pid 55104 arrancou 13:38:36, `processo sha256=1C4A7E1DAE1C` contra `disco FD56234EEB84` (101 ficheiros) | a instancia carrega codigo ANTERIOR ao de hoje; nenhuma cura escrita depois das 13:38 esta' dentro dela. STEP 0 do `docs/bug-hunt.md`: a primeira accao e' reiniciar, e reiniciar a app do dono e' accao dele |

**O que fica decidido:** nao se mata a app do dono, e nao se atribui a ela um numero que o instrumento
nao mediu. O `BatchExecutor` **nao** e' um laco girando: ele tem portao de carga (`allowed()` so' no
nivel `leve`) e a accao do shedding esta' desarmada de proposito (`SOTTO_LOAD_SHED_ACT=1`), porque
arma-la automaticamente num limiar nao calibrado desligaria a transcricao por causa de um build. O que
falta e' um **tecto declarado** naquele laco -- e' o que a lane despachada entrega, com o pid, o tid e
os 36 %/48,4 % como brief.

## 11. O QUE NAO ESTA' VERIFICADO


- O tecto de 40 % e' do **wrapper**; que a corrida inteira caiba no prazo habitual sob ele e' o que a
  corrida caged mede — o numero dela e' o veredicto, nao este paragrafo.
- `pythonw.exe(55104)` foi morto por `taskkill /T` nesta sessao; **quem** o largou (qual passo) nao
  esta' identificado — o censo nomeia o orfao, nao o autor.
