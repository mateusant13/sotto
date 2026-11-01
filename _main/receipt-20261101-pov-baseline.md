# Baseline POV — 2026-11-01 (o que o dono vê, medido de fora)

Instrumento: `_main/pov-selftest.py --run`. Ele arranca uma SEGUNDA instância com
`--mutex-name SottoPovSelftest`, tecla livre `Alt+Shift+F12` e o token `high` do dono
(`_main/launch-as-token.py`, fonte `explorer.exe`), e lê o que a app escreve. Não toca na instância
dele (pid 41492), não mostra nada na tela dele, não usa input sintético.

## O que já está certo, com número

|passo|medido|
|---|---|
|processo aceite → `UI_WATCHDOG_STARTED`|0,835 s|
|→ `PRELOAD_INSTALLED`|1,295 s|
|→ `STAGING_SEEN (bounce)`|1,317 s|
|→ `RECEIVER_READY` (painel pronto)|**2,761 s**|
|→ `PRELOAD_ACTIVE hasSotto=true methods=19`|2,774 s|
|→ `PANEL_STATE_WRITER`|2,792 s|

Arranque limpo = **2,8 s** até o painel estar pronto. A instância das 09:42 levou **74 s** no mesmo
passo com a máquina a correr 46 processos Python de outros projectos (codeintel, watcher, BrandOps):
o número grande era CONTENÇÃO, não a app.

## Defeitos medidos, cada um com o seu rasto

1. **`SELFTEST broken=expected two presses, saw 4`, rc=3.** O auto-teste do próprio repo falha na
   árvore de hoje. Medido no log de `_main/pov-selftest.py`:
   `arm=hold caption_flipped=true` · `arm=tap visible=true mode=strip` ·
   `arm=double visible=true mode=side` — ou seja as armas passam, mas o contador de toques soma 4
   onde esperava 2.
2. **O painel ROUBА o foco.** `PANEL_SHOWN ... show=SW_SHOW+FOREGROUND
   focus_stolen=intentional(hotkey)` e `SELFTEST focus_stolen_by_own_window=true
   after_pid=46144`. `show_strip`/`show_side` chamam `foreground_unlock()` — deliberado desde
   2026-10-09 para libertar o pointer-lock de um jogo, mas custa o foco de quem está a escrever em
   qualquer outro programa.
3. **Uma instância de medição escreve no estado da app viva.** `PANEL_STATE_WRITER
   path=H:\sotto\_main\panel-state.json` apareceu no log da instância de teste, com
   `--mutex-name` privado: o caminho do estado é global. Medido nesta sessão — depois do run, o
   `panel_state.py --read` do dono mostrava `producerPid=46144` (a instância de teste) e
   `freshness=STALE`.
4. **O log cresce sem tecto.** `_main/webview-run.log` = **45 464 263 B** hoje (o ficheiro tem
   linhas de 2026-10-29 em diante). Não há rotação: cada evento faz `append` e `flush`.
5. **O probe de DOM do painel estoura o orçamento.** `WARN exec_js TIMEOUT after 10.0s
   script='(() => { const title = ... document.qu…'` na instância das 09:51 — a leitura do DOM que
   alimenta `panel-state.json` não respondeu dentro de 10 s.

## O que NÃO está provado aqui

- Nada disto é sobre o `Alt+C` do dono com o teclado dele: o input sintético não é evidência
  (AGENTS.md), e uma lane não pode apertar a tecla dele. A prova do gesto é a do auto-teste, que
  percorre o MESMO `simulate_press` que o sistema operativo usa.
- `drift_ms` da legenda vs. o player não foi medido nesta nota; vive nos oráculos
  `youtube-sotto-drift` e `youtube-1to1`.

## Paridade dos dois produtores, vista num ecrã onde ele não está (2026-11-01 10:4x)

Instrumento: `_main/sim/youtube-caption-sim.html` (gerado por
`_main/sim/make-youtube-caption-sim.py`, que importa `youtube_reveal`/`word_fade`/`youtube_captions`
da app e amostra o MESMO `frame()` que a app desenha) aberto no Chromium headless — nenhuma janela
na tela dele. Frames lidos do painel de estado da própria página (t, linhas, a sair, alfa por linha).

|t|modo|linhas|a sair|linhas pintadas (alfa)|
|---|---|---|---|
|2,707 s|YouTube (payload)|3 (janela 2+1)|1|`Have you ever had to kill a man?` **185** · `>> No.` 255 · `>> Then` 255|
|2,580 s|ASR ao vivo (o mesmo motor)|2|0|`Have you ever had to kill a man?` 255 · `No.` 255|

O que isto prova e o que não prova. **Prova** que o motor é UM: a janela (2 + 1), a linha que sai
com alfa a descer, e a revelação palavra a palavra saem da mesma função nos dois produtores — a
única diferença visível é o `>> ` do payload, que é do YouTube e não nosso. **Não prova** que a
legenda ao vivo tem as mesmas palavras no mesmo instante: o ASR entrega `Then` quando o reconhece,
e nesse instante ainda não o tinha. Conteúdo é do produtor; a FORMA é do motor.

