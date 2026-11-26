# Recibo 2026-11-26 — o comportamento do player gravado e reproduzido offline

Ordem do dono que abriu este trabalho, verbatim:

> *"por que EU tenho que mandar tu fazer uma snapshot do youtube pra pegar o comportamento exato e
> reproduzir offline? por que nenhuma das skills te ajuda a ver as coisas por essa visao?"*

E a pergunta que veio depois:

> *"this dm might be a error. if this was caused by one of your subagents, the dm should go to them.
> or if this was you, to you. check"*

## 1. A DM nao era erro — a atribuicao estava certa, e o mecanismo foi REFUTADO

Os pids que a DM nomeia (`ctrlspace-swallow`, `process-target`) sao passos da bateria que **este
assento** larga: o log da corrida mostra `[step] ctrlspace-swallow rc=0` e `[step] process-target
rc=0`, e o runner e' `pythonw step-deadline.py -- <oraculo>`. **Nenhum subagente corre a bateria.**
A atribuicao "esta lane" estava certa, logo a DM voltou para ca', nao para um subagente.

O mecanismo, porem, nao: os dois oraculos nomeados contem **0** ocorrencias de `subprocess` — nao
largam filho nenhum. E a forma EXACTA da bateria, reproduzida com o proprio instrumento, deu
`child pid=36856 hwnd=0 visible=0`; `pythonw` + flags de omissao → `hwnd=0`; pai de consola + flags
de omissao → `hwnd=9110450 visible=0`. Uma janela **invisivel** nao e' a janela que o dono ve.

Resposta em `I:/cc-tmp/dm-reply-console.md`; a DM fechou como `answered`.

## 2. O par que responde a pergunta dele

|peca|o que faz|medido 2026-11-26|
|---|---|---|
|`_main/yt-snapshot-capture.py`|grava o player, nao o log: `currentTime`, `paused`, `readyState`, `rate`, segmento visivel, linhas da janela, a cada 50 ms, com dois carimbos, mais o guiao `play/pause/seek` com o instante do pedido|`dQw4w9WgXcQ` → 466 amostras, `readyState=4` em 99,4 %, pausa real de 4 s (6,18 s imovel), **recuo real 11,16 → 0,00**|
|`_main/yt-capture-replay-oracle.py`|replaia o fixture num relogio simulado pelo **codigo do produto** (`pause_proven`, `SeekWitness`, `advance`, `decide`) e julga sete perguntas|`VERDICT: PASS` rc 0; `--neg-arm 6/6` rc 1|

### Os bracos

|braco|o que afirma|resultado|
|---|---|---|
|a|um video a ANDAR nunca e' provado em pausa|PASS — 10 amostras em movimento, 0 erradas|
|b|uma pausa a serio continua a apagar|PASS — 2 pausas longas, 1 delas desmentida pelo relogio e excluida|
|c|um recuo gravado e' um seek NOMEADO uma vez|PASS — 1 salto gravado, 1 seek `was=11.157506 now=0.0`|
|d|o instante servido nao recua sem testemunha|PASS — 0 recuos sem testemunha, 4 seeks testemunhados|
|e|o fixture teve media|PASS — 475/478 com `rs>0` (0,994); os 3 `rs=0` estao a rodear o seek|
|f|as constantes do espelho concordam com a shell|PASS — `CLOCK_STATIC_PAUSE_S=2.0`, `CLOCK_MOVING_MIN_RATE=0.05`, `DOM_FRESH_S=1.2`|
|g|a cue pintada|`CANNOT-MEASURE why=no-caption-segment`|

### O que custou a honestidade — e este e' o achado metodologico

A primeira corrida do `--neg-arm` deu **1/5**. Quatro mutantes nao derrubavam nada, porque o fixture
GRAVADO nao contem as epocas que os discriminam: o video nao se moveu enquanto a bandeira dizia
pausa, nao houve foto velha, e o unico recuo foi um seek a serio. Um braco assim e' um **verde falso**.

Tres epocas medidas do log do dono entraram num fixture DERIVADO que carrega a origem em cada amostra:

- **E1** a foto velha de **5,9 s** (`YOUTUBE_SNAPSHOT_STALE age_ms=5891`, 02:38:08.713);
- **E2** a bandeira `paused=True` com `YOUTUBE_PAUSE_DISAGREED clock_rate=0.58` (02:38:01, pid 57008);
- **E3** um recuo de 1,0 s, **abaixo** de `SEEK_BACK_S=2.0` — nao e' seek e nao pode mover o chao.

Dois bracos foram **apagados** por nao poderem falhar (a pausa desmentida nunca pode ser provada:
`pause_proven` recusa por construcao quando o relogio anda), e viraram **cobertura contada**. E os
mutantes foram re-apontados ao defeito historico inteiro: espelho estatico **cego** + `pause_proven`
a aceitar so' a bandeira. Resultado: **6/6**.

## 3. O que NAO se mede, dito

- **O texto da cue nao e' obtenivel sem sessao.** MEDIDO nesta maquina, perfil de lane limpo:
  3 videos, **26 faixas**, todas `200` com **0 bytes**. Um video TOCA (`readyState=4`,
  `currentTime` a avancar); as faixas nao servem bytes. Logo o braco (g) e' um HOLE nomeado, e um
  fixture sem cue nunca vira PASS.
- **A frescura da foto** nao se deduz de uma linha do tempo: o `stamp` nasce no momento da leitura.
  O dono dela e' `_main/yt-pause-disagreement-oracle.py`.
- **A pausa/seek do dono na instalacao DELE** continua `fixed, NOT verified`: os pids 53752/73436
  carregam codigo anterior aos commits.

## 4. Bateria: tres pares novos, e o portao que os exigiu

`battery-wiring` recusou **dois oraculos orfaos** (`yt-headless-paint-oracle.py`,
`yt-lane-session-oracle.py`) antes de os passos existirem — `fail=1`, e o nome de cada um. Depois:

|par|classe|medido|
|---|---|---|
|`yt-capture-replay` + `red-as-expected-...`|normal (le' fixtures, nao larga browser)|PASS rc 0 / `NEG-ARM: PASS` rc 1|
|`yt-headless-paint` + `red-as-expected-...`|normal (fora do ecra, `windows_opened=0`, 109 bitmaps)|PASS rc 0 / 5/5 rc 1|
|`yt-lane-session` + `red-as-expected-...`|**heavy** (larga um Chrome real)|PASS rc 0 / 3/3 rc 1|

`battery-launch.py --verify`: **PASS** nos cinco portoes (pins, wiring, pairing, class,
undefined-names).

### O braco de rede do `yt-lane-session` estava a medir a politica do YouTube de ontem

Ele exigia `rc=3` ("signed-out recusa"). MEDIDO, o mesmo video TOCA num perfil de lane — `rc=0`
duas vezes, em duas formas diferentes. O braco foi refeito para recusar um **OK sem prova de
playback** (e apanhou exactamente isso: `readyState=4` com `delta_ms=0`), aceitar uma recusa
NOMEADA nos dois sentidos, e degradar falha de rede a **HOLE declarado** em vez de vermelho.
Uma corrida depois: `PASS played readyState=4 delta_ms=796`.

## 5. Pin re-medido

```
_main\_audit-verify-all.cmd = 448809 B, 5115 CRLF / 0 bare LF,
sha256 EF7ED87D24B7EF7739560AA50532E745A774C8E5126B4C340ABE7F82A9124518
```

`agents-md-pins-oracle.py`: `AGENTS-PINS PASS -- 2 pin(s)`.

## 6. A regra que ficou escrita

`AGENTS.md` §"O COMPORTAMENTO DO PLAYER GRAVA-SE EM BYTES E REPRODUZ-SE OFFLINE (medido
2026-11-26)" — o par, os bracos, as epocas derivadas com origem, o que nao se mede, e o portao.

## 7. O que fica aberto

1. As conversoes do censo de `red-as-expected` (`--apply` em curso; 8 passos, **217 s** medidos).
2. Um cookie jar sem dono que torne a metade das cues verde (`--cookies` ja' existe no instrumento).
3. A corrida da bateria que prova o tempo de parede mais curto.
