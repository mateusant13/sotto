# Briefing do dono — 2026-10-12 04:2x -03:00 (verbatim) + mapa de atribuições

A ordem de parada de 2026-10-11 está **LEVANTADA** por esta mensagem: *"faz o sotto abrir, agora ele ta
fechado."* O Sotto ESTÁ aberto (Lead, pid 8588 + worker filho). Ainda assim: **só o Lead lança a app/worker**;
subagentes NÃO lançam (a app é uma instância única e o dono está a usá-la).

## O pedido, verbatim

> faz o sotto abrir, agora ele ta fechado. e garante pra mim o seguinte: cada tema/template/design, de cada
> versao de painel, de cada .zip, é implementado. e eu nao quero que seja por cima do nosso painel atual, ou
> na mesma div do painel, etc. eu quero que tudo seja "traduzido" pro tamanho atual, e com os botoes atuais.
> o resto, tem que ser igual. e o painel de baixo, ta errado. ele nao deve mostrar legenda de jeito nenhum.
> ele deve ser menor ainda, mais estreito, do tamanho dos botoes. os botoes tem que ser mais claros. e ele tem
> um botao de linhar a legenda, que liga ela NA TELA, igual um overlay, EXATAMENTE IGUAL os .zip fazem. é
> mostrado na TELA. como se nao houvesse painel pra legenda, como ela tivesse solta. mas isso, é pq tem q ser
> igual aos paineis. o sotto nao deve carregar tudo de uma vez, apenas o essencial. o sotto tem que usar o
> nemotron 3.5 pra falas ao vivo, e o parakeet redux por cima de qualquer coisa ao vivo falada, por que ele
> tem melhor qualidade. quando a troca de legenda no historico acontecer por causa desses dois, faz uma
> animacao por LETRA TROCADA e inserida. pesquisa online se da pra separar os audios de cada speaker de uma
> call do discord por alguma tecnica, ou se precisamos de um modelo pra fazer isso pela gente, e se a gente ja
> tem esse modelo. se nao tiver, instala. e faz o menu dropdown de escolher temas do sotto, onde passar o
> mouse em qualquer um ja mostra o preview sem travamento e super otimizado. e acho que é o sotto que causa um
> stutter quando inicia no meu pc, acho. investiga apenas se ELE faz isso, se nao faz, ignora. despacha varias
> coisas pra subagents, que tu ta fazendo agora, e desse prompt

## Decomposição em 7 frentes (uma por subagente; escopos de escrita DISJUNTOS)

| # | entrega | escopo de escrita (só isto) |
|---|---|---|
| S1 | inventário dos .zip + folha de tradução por design | `docs/design-intake/**` (novo) |
| S2 | painel de baixo: sem legenda, mais estreito, botões claros + botão que solta a legenda NA TELA | `app/panel/panel.html`, `app/panel/panel.css`, `app/panel/panel.js`, `app/panel/caption-float.js` (novo) |
| S3 | nemotron ao vivo + parakeet redux por cima de tudo o que é falado ao vivo | `worker/sotto_worker.py`, `worker/redux_live.py`, `worker/config.json` |
| S4 | animação por LETRA trocada/inserida na troca de legenda do histórico | `app/panel/letter-swap.js` (novo), `app/panel/caption-formulation.js` |
| S5 | pesquisa: separar áudio por speaker de uma call do Discord (e instalar modelo se faltar) | `docs/research/speaker-separation.md`, `_main/_venv-diar/**` |
| S6 | dropdown de temas com preview no hover, optimizado | `app/panel/theme-switcher.js`, `app/panel/theme-tune.js`, `app/panel/themes/**` |
| S7 | carregamento só do essencial + diagnóstico do stutter no arranque | `app/webview/sotto_webview.py`, `app/panel/lazy-assets.js` (novo) |

Regras duras para todos: (1) não lançar a app/shell/worker — pedir ao Lead; (2) `$env:TMPDIR="I:\cc-tmp"`;
(3) nunca deixar janela de consola visível; (4) ficheiros do painel são CRLF ou LF — MEDIR antes de reescrever;
(5) nenhum gate verde sem braço de controlo que saiba dizer NÃO; (6) cada entrega termina com um recibo em
`_main/receipt-20261012-<frente>.md` com os números medidos e o que NÃO ficou medido; (7) não tocar em
ficheiros fora do escopo — se precisar de uma linha noutro ficheiro, escreva o pedido no recibo.
## CONTEXTO MEDIDO PELO LEAD (2026-10-12 04:35, a app ESTÁ ABERTA — ler antes de trabalhar)

* **A app está aberta e é INSTÂNCIA ÚNICA**: shell `pythonw.exe sotto_webview.py` pid **8588**, worker
  `python.exe` pid **22172**. Ninguém além do Lead lança, mata ou reinicia. Se precisares de um arranque para
  medir, escreve no teu recibo o comando exato e o que ele prova — o Lead executa e devolve os números.
* **O "painel de baixo" é a STRIP**, medida no log da shell:
  `PANEL_GEOMETRY_RESTORED surface=strip rect=1040x100@(440,920) writtenAt=2026-10-12T04:32:12-03:00 clamped=false`.
  O dono quer: sem texto de legenda nenhum, mais estreito, da ALTURA DOS BOTÕES, botões mais claros.
* **Ordem real do arranque** (de `_main/webview-run.log`, sessão a começar na linha 91910; o log NÃO tem
  timestamp por linha): `SINGLE_INSTANCE already_running=false` -> `HOT_RELOAD_WATCH panel` + `worker` (2
  watchers, debounce 250 ms) -> `PRELOAD_INSTALLED` -> `STAGING_SEEN` -> `STAGING_LOADED` -> `RECEIVER_READY`
  -> `BRIDGE_STATS_REPLY payload={"tag":"stats"}` -> `PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C`.
* **Footprint agora** (re-medido pelo Lead, janela de 19 s a cadência de 1 s, ps: TotalProcessorTime):
  worker **2479 MB** RSS (máx 2481), shell **114 MB**, 2 processos WebView2 filhos.
  **CORRIGIDO — o "96.78 s de CPU" que aqui estava era o meu bug de unidades:** `Get-Process.CPU`
  devolve um `TimeSpan` no pwsh 7 e o `-f` imprimiu-o como texto; a medida certa é
  `.TotalProcessorTime.TotalSeconds`: shell **0,63 s / 19 s** (3,3% de um core), worker **0,47 s / 19 s**
  (2,5%) com o áudio PARADO (`CAPTION_APPLIED` contado 1/s, **0** no janela; quando há áudio dá ~30/s).
  O AGENTS.md cita int8 RSS ~1192 MB: o medido já não bate, e isso é uma medição a fazer, não uma conclusão.
* **Sem janelas visíveis**: `mainWindowHandle=0` para os dois pids (nenhuma consola órfã na tela do dono).
* **Payload de stats vazio = `{"tag":"stats"}`** (não `{}`): não escrevas guardas que assumam `{}`.
* A shell expõe **14 métodos** ao painel. Precisar de um método novo no shell = fora do teu escopo nesta
  ronda: entrega a assinatura exata no recibo.

---

# ACTUALIZAÇÃO DO LEAD — 2026-10-12 05:30 -03:00 (ronda 1 de 7)

**Estado dos oráculos nesta hora — todos corridos pelo Lead, não aceito a palavra da frente:**

| frente | instrumento | resultado (corrido pelo Lead) |
|---|---|---|
| S1 | `node docs/design-intake/gap-oracle.mjs` | **não corre**: `SyntaxError: Illegal return statement` na **:272** (24 391 B / 490 linhas às 05:24). Às 05:06 estava truncado no EOF (:429). O resumo "142/0" não é auto-verificado |
| S6 | `node _main/theme-preview-oracle.js` | **VERDICT: FAIL** (25,8 KB): ARM8 "the deferral is counted" (got false), ARM8 "exactly one apply at the commit" (got 0, want 1), ARM9 "the warm path ran in an idle slice" (fonts=0 images=0 ms=0) |
| S4 | `node _main/letter-swap-oracle.js` | **VERDICT: FAIL** 76/78: `C8b text swapped got="x" want="bom dia!"` e `C12a second swap animates without a prevProducer got=0 want=1` |
| S7 | `node --check app/panel/lazy-assets.js` | **parse ok** (12,5 KB, 05:21) |

**O que mudou no chão destas frentes (medido pelo Lead):**

1. **MossFormer2 instalado** — `_main/diar-models/mossformer2/last_best_checkpoint.pt`, **670 353 271 B**,
   sha256 `00A3A48B...` == o `oid` do ponteiro LFS do servidor (verificado duas vezes: em trânsito e no
   lugar), licença **apache-2.0**. Pedido ao S5 cumprido. `torch 2.7.0+cu128` existe no Python do sistema
   mas **nunca o executei** e o código de inferência (ClearerVoice-Studio) não está instalado → **UNMEASURED**.
2. **`_main/diar-models/` é agora git-ignorado** (como `worker/models/` e `history/`) — pesos locais, nunca
   no repositório.
3. **Os 5 ficheiros `_main/_audio-*` que estavam apagados foram repostos em disco** (`git checkout --`);
   não os trates como ausentes, e nada foi perdido.
4. **Os 12 mutantes `_main/_redux-gate-mutants/*.py` re-baselados foram verificados pelo gate que os
   consome** (`VERDICT: PASS`, rc=0) e comitados (`79bd753`) — não são lixo, não os apagues nem os
   revertas.
5. **Dois commits já no remoto:** `1f43b3b` (recibo da ronda 1 + S5 + MossFormer2) e `79bd753`
   (mutantes). `HEAD == origin/feat/build-verify-1`.

**Ainda bloqueado (o Lead não mata a app do dono):** os braços do arranque do S7 (`--no-worker` /
`SOTTO_NO_WORKER=1` vs completo) e a bateria 77/77 — a app do dono detém `SINGLE_INSTANCE`
(`Local\SottoShell`, pid do shell **8588**, worker **22172**).
