# 00 — A PROMESSA

Este ficheiro é o contrato do produto, escrito nas palavras do dono e conferido contra o que o
código faz hoje. Não é um plano: é a lista do que foi prometido, e ao lado de cada linha o **estado
medido** dessa promessa, com o instrumento que o mede.

A regra: uma promessa sem instrumento não é uma promessa, é uma intenção. Onde o instrumento não
existe, a linha diz `[UNKNOWN]` e o que falta para a medir.

## 1. A promessa, por palavras dele

| # | verbatim | data |
|---|---|---|
| P1 | *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc. e legendas."* | 2026-10 (a frase de abertura do produto) |
| P2 | *"as soon as i open it, should start the subtitles in my screen. the ctrl space."* | 2026-11-11 |
| P3 | *"se a legenda ao vivo ta desativada, nao signiifca q o modelo ta desativado. é o DISPLAY que ta desativado."* | 2026-11-04 |
| P4 | *"nao e pra traduzir entre ingles pt br e espanhol. nesses 3, é lingua original que da display."* | 2026-11-04 |
| P5 | *"mas pra traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é pt br."* | 2026-11-08 |
| P6 | *"apertar alt c super rapido deixa o app travando pra caralho. deixa completamente fluido."* | 2026-11-08 |
| P7 | *"sotto closed by itself. maybe crashed? not sure. should close only because of me, or hard kill from task manager."* | 2026-11-09 |
| P8 | *"to em call no discord agora. identifica corretamente o audio saindo do discord"* | 2026-11-09 |
| P9 | *"quem falava quando nao é importante... sendo que é só separar audio pra transcrever cada falante?"* | 2026-10 |
| P10 | *"nao faz nenhum script existente ou novo abrir coisa na minha tela tipo pop up"* | 2026-11-04 |

## 2. O estado de cada promessa, hoje

O estado tem três valores apenas: **cumprida** (observada no processo dele e medida), **cumprida no
código** (o instrumento prova a função, o processo dele ainda não a corre), **aberta**.

| # | promessa | estado | instrumento | a evidência |
|---|---|---|---|---|
| P1 | Alt+C mostra a transcrição ao vivo | **cumprida no código** | `altc-gesture-oracle`, `paint-live-show-oracle` | despacho do Alt+C medido em 5 ms e pintura em 3 142 ms na sessão de 2026-11-10 — a pintura **não** cabe no orçamento de 400 ms, e é por isso que ela tem passo próprio (`boot-interaction`) |
| P2 | abrir a app liga a legenda | **cumprida no código, NÃO verificada** | `caption-wanted-default-oracle` (21 arms, neg 4/4) | `10-DEFECTS.md` §D-02: o ficheiro dizia `{"on": false}` e vencia o arranque. O processo dele corre código anterior (`live-code-freshness` = `STALE`) |
| P3 | calar a legenda não desliga o modelo | **cumprida no código** | `caption-switch-race-oracle`, `caption-wanted-default` A11 | `LIVE_ENABLED on=false` corta o display; o worker e o histórico continuam |
| P4 | en/pt/es na língua original | **cumprida no código** | `youtube-captions-oracle` (66 arms) | `UNTRANSLATED_LANGS = ('en','pt','es')`; um `pick` que fosse traduzir é clampado |
| P5 | o resto vai para a língua escolhida | **cumprida no código** | `youtube-captions-oracle` | `_target_langs('ja')` devolve `('pt','ja')`; a escolha é persistida em `_main/caption-settings.json` |
| P6 | Alt+C em rajada não trava | **cumprida no código** | `hotkey-spam-oracle` (19 arms) | 6 toques em <50 ms = 18,5 ms de despacho e **1** transição, contra 2 461,5 ms e 6 na fila antiga |
| P7 | fecha só por ele | **cumprida no código** | `ui-watchdog-oracle` (9 arms) | um hang sem assinatura passou de `UI_WATCHDOG_EXIT` para `UI_WATCHDOG_RECOVER` |
| P8 | o áudio do Discord certo | **cumprida, com um braço UNMEASURED** | `process-target-oracle` (14 arms) | 39 blocos entregues com a raiz da árvore aberta; **UNMEASURED** o áudio de uma call real — na janela medida ele não estava a renderizar som (`peak=0.0`) |
| P9 | separar falantes para transcrever cada um | **aberta** | `fusion-oracle`, `fusion-wire-oracle` | a fusão stream/refinado existe e está ligada; a separação por falante **não** está medida |
| P10 | nada abre na tela dele | **cumprida no código** | `owner-screen-gate` (987 ficheiros, 0 achados), `console-window-audit` (AST) | `--neg-arm` rc=1 nos dois |

## 3. O que a promessa NÃO inclui

Estas são as recusas que o dono fez, e que nenhuma sessão futura pode reintroduzir como "melhoria":

- **Nomes de vozes.** A cadeia de falantes serve para separar áudio, não para dizer quem falou.
- **Tempo real do nemotron.** Ele é o motor **local**; o atraso dele é medido, não prometido. A
  legenda que acompanha o áudio é a do YouTube; sem ela, a do motor local com o atraso que tiver.
- **Tradução entre en/pt-BR/es.** Em qualquer direcção.
- **Abrir janelas, diálogos ou o browser na tela dele.** Nenhum script, nenhum instrumento.
- **Mutar ou reiniciar o áudio dele.** Um instrumento escreve num endpoint só com
  `SOTTO_OWNER_AUDIO_OK=1`, e a bandeira é dele.

## 4. O critério de aceitação

Uma promessa passa de **cumprida no código** a **cumprida** quando as quatro coisas valem juntas:

1. observada **no processo do dono**, com `pid` e hora;
2. o log carrega a linha que nomeia o desfecho — e também a que nomearia o defeito;
3. o instrumento está num passo da bateria, com o seu `--neg-arm` verde;
4. `live-code-freshness --strict` diz `FRESH` para o processo que escreveu a linha.

Enquanto faltar (1), o estado escrito é **`cumprida no código, NÃO verificada`** — e é isso que este
directório escreve, sem eufemismo.
