# 11 — A SPEC-ALVO: o comportamento que eu escolho

Este ficheiro é o único deste directório que **não** descreve o que o código faz hoje. Ele descreve
o que eu decido que o Sotto **deve** fazer, jornada a jornada, e o número que fecha cada jornada.
`02` a `09` descrevem o presente; quando os dois discordam, o `10-DEFECTS.md` diz qual dos dois é o
defeito.

Toda a decisão aqui tem de caber em quatro coisas, ou não entra:

1. uma **ordem do dono** (verbatim, datada);
2. um **número** que a torna falsificável;
3. o **instrumento** que o mede — e ele tem de existir no repositório, não ser inventado aqui;
4. o que **não** se promete.

## 0. A promessa, em uma frase

**O dono ouve audio neste PC e vê o que está a ser dito, na tela, sem carregar em nada e sem esperar
por um modelo.** A legenda é o produto; tudo o resto — painéis, histórico, temas — serve essa
frase.

## 1. As jornadas

| # | jornada | quando | o que ele vê | o número que a fecha |
|---|---|---|---|---|
| J1 | abrir o app | duplo-clique, autostart, relançamento | a legenda ao vivo já ligada; o painel escondido | decisão `on=true` no arranque; primeira linha ≤ 3 000 ms depois do 1º áudio com modelo quente |
| J2 | assistir a um vídeo do YouTube | ele vê um vídeo no Chrome | a linha do player, na língua original ou na escolhida, sincronizada | `drift_ms` medido contra o player, |drift| ≤ 150 ms |
| J3 | uma call / áudio do sistema | Discord, jogo, qualquer app | as linhas do áudio daquela app | primeira linha ≤ 3 000 ms do primeiro bloco; deriva de áudio (`tap_ms`) ≤ 1 500 ms no pixel |
| J4 | voltar atrás no tempo | ele abre o histórico | o que foi dito, com a hora, a fonte e o contexto | linha existe no disco `history/<dia>/<hora>.md` e busca por palavra devolve a mesma linha |
| J5 | Alt+C | ele quer ver o painel | faixa de baixo → painel da direita → escondido, por pressão | despacho ≤ 50 ms e pintura ≤ 400 ms por passo |
| J6 | Ctrl+Space | ele quer calar a legenda | o display apaga; modelo, transcrição e histórico continuam | `LIVE_ENABLED on=false` sem parar o worker |
| J7 | o PC tropeça | stutter, altifalante trocado, Chrome fechado | a legenda não dessincroniza e não desaparece | `stutter-caption` (drift sob stutter ≤ 150 ms) e `device-ladder-cost` |
| J8 | ele acaba | desliga, reinicia | os ficheiros ficam coerentes e o próximo arranque não mente | `live-code-freshness` + `panel-state` da sessão nova |

## 2. Jornada a jornada: o que eu escolho, e porquê

### J1 — abrir o app liga a legenda

**Ordem do dono (2026-11-11, verbatim):** *"as soon as i open it, should start the subtitles in my
screen. the ctrl space."*

**Decisão.** O arranque decide por `SottoShell.caption_wanted_at_start` (pura): liga por omissão;
desliga numa corrida de medição (`MEASUREMENT_FLAGS`) ou numa largada de lane (`SOTTO_LANE_LAUNCH=1`),
porque nenhuma das duas pode pintar no ecrã dele. O ficheiro `_main/caption-wanted.json` continua a
ser escrito e lido, mas **não vence** o arranque: o desacordo vai para o log
(`CAPTION_WANTED_START_OVERRIDES`).

**Porque não a alternativa "obedecer ao ficheiro e mostrar um botão".** Medido: o ficheiro dizia
`{"on": false}` desde a sessão anterior, e a sessão anterior só o escrevia `false` quando ele
desligava com o HOLD — ou seja, obedecer-lhe transformava um desligar de uma vez num desligar para
sempre, e a única saída era ele premiar outra vez. Um interruptor que só abre por dentro de si mesmo
não é um interruptor.

**Número.** `CAPTION_WANTED_START on=true reason=default` no log de todo o arranque que não seja
medição; primeira pintura dentro do orçamento de `paint-live-show` (400 ms do pedido ao pixel) quando
o pedido já existe.

**Instrumento.** `_main/caption-wanted-default-oracle.py` (21 arms, `--neg-arm` 4/4) e
`_main/paint-live-show-oracle.py`.

**Não se promete:** que a primeira linha chegue depressa — o modelo carrega (ver D-04 em
`10-DEFECTS.md`); promete-se que a legenda está **ligada** e que o estado é escrito, não que o modelo
esteja quente.

### J2 — o YouTube como fonte externa

**Ordem do dono (2026-11-04):** *"tu pode usar meu youtube e meu navegador. só que dessa vez, no
background."* E a política de língua: en/pt-BR/es **não se traduzem entre si**; qualquer outra língua
vai para a língua escolhida (default `pt`), persistida em `_main/caption-settings.json`.

**Decisão.** A fonte é o DOM do player por CDP, não a árvore de acessibilidade, porque a árvore
devolve uma linha por minuto com a aba em segundo plano (medido 2026-11-03). O relógio é o do
player, interpolado com tolerância **do estado publicado** (PLAYING/PAUSED/ENDED), nunca com um tecto
redondo: um tecto redondo inventa uma parada que o player não declarou e custava 2,3 s de erro num
stutter de 3 s.

**Número.** `drift_sotto_ms` contra `drift_player_ms` com o oráculo `youtube-sotto-drift`, alvo
|drift| ≤ 150 ms; sob stutter, `stutter-caption` ≤ 150 ms.

**Instrumento.** `_main/youtube-1to1-oracle.py`, `_main/youtube-sotto-drift-oracle.py`,
`_main/stutter-caption-oracle.py`, `_main/youtube-cdp-source-oracle.py`.

**Não se promete:** ler uma legenda que o player não está a mostrar. Sem faixa, sem cue, sem linha —
e o log diz `no-captions`, que é uma medida e não um silêncio.

### J3 — o áudio do sistema

**Decisão.** O worker é o dono da captura: escada de dispositivos, tap por processo quando há
`--target-name`, journal quente para não pagar 43 s a abrir um rung que entrega zero. A shell não
lhe pode dizer "muda de dispositivo" (não há canal) — logo toda a política rápida vive no worker.

**Número.** Primeira linha ≤ 3 000 ms do primeiro bloco; `CAPTION_PAINT_LAG audio_ms` ≤ 1 500 ms no
pixel; abertura do primeiro dispositivo com sinal ≤ 1 s com o journal quente.

**Instrumento.** `_main/first-capture-fast-oracle.py`, `_main/device-ladder-cost-oracle.py`,
`_main/caption-lag-budget-oracle.py`.

**Não se promete** tempo real do nemotron: ele é o motor **local** e o atraso dele é medido, não
hipotético (regra 2 de 2026-11-04).

### J4 — o histórico

**Decisão.** Uma linha por frase fechada, com hora, fonte (`PC`/`YouTube`) e contexto (`ctx1=`), no
ficheiro `history/<dia>/<hora>.md`; a busca lê o mesmo ficheiro. As linhas **parciais** não entram
(elas são o que o olho vê, não o que se guarda). A retenção tem tecto declarado e o corte é contado.

**Número.** Toda linha admitida existe no ficheiro; busca por uma palavra da linha devolve essa
linha; exportar não perde nenhuma.

**Instrumento.** `_main/history-route-oracle.py` (duas populações: stream curto e longo),
`_main/history-write-oracle.py`, `_main/history-context-oracle.py`.

**Não se promete:** pontuação terminal inventada ao vivo. O `?` e o `!` não são inventados; o ponto
final vem da prosa e da pausa medida, e só na LEITURA do arquivo.

### J5 — os painéis

**Ordem do dono (2026-11-01 → 2026-11-05):** Alt+C alterna painéis, um passo por pressão, três casas
(escondido → baixo → direita → escondido), sem janela de espera.

**Decisão.** Cada `WM_HOTKEY` avança o ciclo uma vez; `MOD_NOREPEAT` garante um evento por pressão
física; a memória da última superfície faz `show/hide/show` alternar em vez de repetir.

**Número.** Despacho ≤ 50 ms (`HOTKEY_COALESCED`), pintura ≤ 400 ms (`PANEL_SHOWN wait_ms`), rajada
de 6 toques em <50 ms = **1** transição, não 6.

**Instrumento.** `_main/altc-gesture-oracle.py`, `_main/hotkey-spam-oracle.py`,
`_main/boot-interaction-oracle.py`.

### J6 — calar a legenda não é desligar o modelo

**Ordem do dono (2026-11-04, verbatim):** *"se a legenda ao vivo ta desativada, nao signiifca q o
modelo ta desativado. é o DISPLAY que ta desativado."*

**Decisão.** `LIVE_ENABLED on=false` corta **o display**. Nenhum caminho pode desligar worker, modelo
ou histórico a pretexto de a legenda estar desligada.

**Número.** `grep` do `_set_live_enabled` sem uma única chamada a `bridge.stop`/`stop_worker`, e o
worker vivo depois do toggle (`WORKER_ALIVE` a continuar).

**Instrumento.** `_main/caption-switch-race-oracle.py` (arm do interruptor),
`_main/caption-wanted-default-oracle.py` (A11).

### J7 — o PC tropeça, a legenda não

**Decisão.** A legenda não dessincroniza por um stutter **que o player não declarou**; o que o player
declara (pausa/fim) apaga os pixels. O áudio volta depois de um corte e a legenda volta com ele, ou o
defeito é **nomeado** (`NO_CAPTION_AFTER_AUDIO_BACK`).

**Número.** `stutter-caption` ≤ 150 ms; `CAPTURE_SIGNAL_BACK` dentro de 25 s sem legenda nova produz
a linha de defeito; `audio-back-detector` 11 arms.

**Instrumento.** `_main/stutter-caption-oracle.py`, `_main/audio-back-detector-oracle.py`,
`_main/yt-clock-static-oracle.py`.

### J8 — acabar bem

**Decisão.** Sair só por ele (ou por kill do gestor de tarefas): o `UI_WATCHDOG` recupera, não mata
a app. O estado que fica no disco é coerente e a sessão seguinte não é julgada com o código velho.

**Número.** `UI_WATCHDOG_RECOVER` em vez de `UI_WATCHDOG_EXIT` num hang sem assinatura;
`live-code-freshness-oracle --strict` a dizer `FRESH` para o processo que escreveu o log.

**Instrumento.** `_main/ui-watchdog-oracle.py`, `_main/live-code-freshness-oracle.py`,
`_main/dead-app-exit-oracle.py`.

## 3. Orçamentos globais (a tabela que fecha qualquer discussão)

| o quê | orçamento | dono do número |
|---|---|---|
| pintura do painel (pedido → pixel) | **400 ms** | `paint-live-show` |
| despacho do Alt+C | **50 ms** | `boot-interaction` |
| idade do áudio no pixel | **1 500 ms** | `caption-lag-budget` |
| drift contra o player | **150 ms** | `youtube-sotto-drift` / `stutter-caption` |
| primeira linha depois do 1º áudio | **3 000 ms** | `time-to-first-caption` |
| CPU da shell | **25 % de um núcleo**, um fio ≤ 15 % | `shell-thread-budget` |
| CPU da árvore (shell + worker) | **250 % de um núcleo** (mediana de 3 janelas) | `tree-cost` |
| passo da bateria | **240 s** de tecto, corrida a quente ~60 s | `step-deadline` / `battery-budget` |

Um orçamento sem dono não é um orçamento: cada linha acima nomeia o passo que a mede, e um passo
saltado **não** é um portão que passou.

## 4. Não-objectivos (o que eu recuso, com a razão)

| recusa | razão |
|---|---|
| dar nomes a vozes | ordem do dono: *"quem falava quando nao é importante... sendo que é só separar audio pra transcrever cada falante?"* |
| traduzir entre en/pt-BR/es | ordem do dono de 2026-11-04/2026-11-08; o código faz clamp, não honra |
| prometer tempo real do nemotron | ele é o motor local; o atraso é medido |
| trocar por `parakeet-ultra` | 7,02× o disco por ganho de qualidade não medido |
| `ARK-ASR-0.6B` | traduz em vez de transcrever, sem `pt` |
| pontuação de modelo multilingue | 2,4 GB + torch, com o `I:` a 4,8 % livre — recusado por medição |
| mutar o áudio do dono | `SOTTO_OWNER_AUDIO_OK` é dele, não de uma lane |
| abrir janelas na tela dele | nenhum script, nenhuma sonda, nenhum controlo |

## 5. O que "funciona" quer dizer (critério de aceitação, sem adjectivos)

Uma jornada está **fechada** quando as quatro condições valem ao mesmo tempo:

1. o comportamento foi observado **no processo do dono** (não num harness), com o pid e a hora;
2. o log carrega a linha que nomeia o desfecho (não só o sucesso — a linha que diria o defeito);
3. o instrumento que o mede está **num passo da bateria** com o seu `--neg-arm`;
4. a frescura foi verificada (`live-code-freshness`), porque um número medido num processo anterior
   ao código mede o código anterior.

Enquanto faltar (1), o estado é **`fixed, NOT verified`** — e é isso que fica escrito.
