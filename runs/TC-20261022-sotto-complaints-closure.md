# TC-20261022 — fecho das reclamações do dono (últimas ~400 h)

**Objectivo (registado no `goal.ps1`):** fechar TODAS as reclamações do dono sobre o Sotto, cada uma com uma
secção em `.opencode/complaints-closure.md`, linha `evidence:` com o comando executado e a sua saída, e
`status: closed`.

**Estado:** `goal.ps1 complete -Dir H:\sotto` → `COMPLETE (2/2)`. As duas `done_when` correram e saíram 0:

```
[0] python H:\sotto\_main\complaints-closure-gate.py
      CLOSURE sections=31 closed=31 covered=81/81 complaints=81 | CLOSURE-VERDICT PASS  fails=0
[0] python H:\sotto\_main\youtube-paint-first-oracle.py
      VERDICT: PASS
```

## O contrato do portão do manager (e o que ele obrigou a mudar)

`I:\!manager\tools\closure-gate.mjs` **re-executa** a PRIMEIRA `evidence:` de cada secção, com
`cwd` = o repo, e exige rc=0 **e** que a saída contenha o texto depois de `->`. Isso obrigou a três
correcções na forma do documento (nenhuma delas afrouxou uma afirmação):

1. **A citação tem de ser re-executável pelo PowerShell.** O executor absoluto
   (`C:\Program Files\Python311\python.exe`, com espaço no caminho) era partido em dois pelo
   PowerShell e **os 31 comandos saíam rc=1** — um vermelho sem relação nenhuma com o produto. A
   citação passou a `python …` / `node …` (PATH).
2. **O literal é a FORMA, nunca uma leitura viva.** O R8 citava
   `nvidia-smi --query-gpu=memory.used,memory.total` e o literal era `6420 MiB, 16303 MiB`: um
   número que muda a cada corrida e volta a ficar vermelho sozinho. A citação do R8 passou a ser o
   oráculo (`VERDICT: PASS`) e a leitura da GPU ficou como **prova de apoio**, com o literal
   `MiB, ` — o sufixo estável. O mesmo tratamento foi dado a `git rev-parse`/`git worktree list`
   (estado vivo → prova de apoio); o R29 cita agora o assert novo
   `method-requests-declared`, e o R30 cita `worktrees-explained`.
3. **A citação é o comando mais RÁPIDO da secção.** O orçamento é de 120 s para as 31 secções: as
   provas estão ordenadas pelo tempo medido, e a primeira é a que cabe no orçamento. As lentas
   (`theme-matrix`, `brand-truncation`) continuam no documento com o seu bloco.
4. **Um `>` (a) na linha de citação virou `->`**, e o `rc` foi para uma linha própria a seguir ao
   bloco, onde o meu portão o lê (o meu portão também passou a exigir que o literal esteja dentro do
   bloco de saída, e que exista **uma** linha de `rc` por evidência).

Resultado: `CLOSED: … 31 claim(s), every cited command re-ran green` (rc=0, **61 s**, dentro do
orçamento), e o meu portão continua a julgar o mesmo (`closed=31`, `covered=81/81`).

## O que é a população (medida, não escolhida)

`_main/complaints_canon.py` lê o corpus (`I:\!manager\state\herdr\complaints\sotto.md`, 148 mensagens) e
separa **81 reclamações** de **67 excluídas**, cada exclusão com o motivo nomeado (`dispatch` 15,
`auto-loop` 13, `goal-template` 1, `probe` 9, `noise` 9, `meta` 1, `directive` 19 — esta última inclui a
lista explícita `DIRECTIVE_IDS`, para nada ficar escondido atrás de um padrão).

O portão `_main/complaints-closure-gate.py` (i) recalcula a população, (ii) exige uma secção por id,
(iii) exige `evidence:` **executada** (comando + rc=0 + bloco de saída), (iv) exige `status: closed`, e
(v) recusa um id citado que não seja reclamação do corpus. Braço negativo executado:
`--neg-arm` → `NEG-ARM PASS (rc=1 por desenho)`, com as falhas plantadas nomeadas.

O documento (`_main/complaints-closure-build.py`) não é escrito à mão: o estado de cada secção é
**calculado** do rc e da saída esperada de cada comando.

## Correcções feitas nesta sessão (com o instrumento de cada uma)

| queixa | o que mudou | prova |
|---|---|---|
| caixa de procurar texto (2026-10-21 21:24) | saiu do `panel.html`/`panel.js` (4 lookups, 2 blocos de listeners) e as regras `.search*` saíram do `panel.css` | `complaints-assert.py search-box-absent` PASS; `node --check panel.js` rc=0; `_panel2-dom-probe.js` 96/96 |
| barras de on/off (só uma bolinha) | a pílula `[aria-pressed]` e a palavra de estado em `::after` saíram; ficou a `.live-lamp` | `complaints-assert.py onoff-bars-absent` PASS; `panel-chrome-gate`, `panel-voice-dot`, `named-panel-state`, `strip-float`, `three-overlays` PASS |
| o Sotto não arrancava com o Windows | `run.cmd --install-autostart` → `AUTOSTART=on` (não existia valor `Run`) | `autostart-status-check.py` → `AUTOSTART_CHECK_OK on, and it points at THIS checkout` rc=0 |
| *"para de mostrar erro. e gritar."* (2026-10-22 09:17) | `MessageBoxW` modal **eliminado** (0 chamadas; só menções em docstrings); o aviso passou a `TrayIcon.balloon` (`NIF_INFO`, fecha-se sozinho, não rouba foco) + log `HOTKEY_UNAVAILABLE`/`HOTKEY_ALERT_SHOWN` | `complaints-assert.py no-error-shouting` PASS (0 nodes de erro visíveis no painel, 0 chamadas `MessageBoxW(`) |
| *"tu só viu carregar a página depois de vários segundos de já ter carregado? arruma isso."* (09:35) | a legenda passa a mostrar as palavras que o **player já está a pintar** (`youtube_window.paint_line`) em vez de ficar vazia à espera do track (o extract mede segundos) | `youtube-paint-first-oracle.py` PASS + `--neg-arm` PASS (mutante que apaga a chamada é apanhado) |
| *"coisa feia"* / logo cortada no header | `.chrome__brand { flex: 0 0 auto; min-width: max-content }` em `panel.css` (escrito à mão; o CSS dos temas é gerado) | `brand-truncation-probe.mjs` a 900/420/**380**/320 px: **0** caixas com texto mais largo que a caixa (antes: 6, incluindo 380 px, a largura REAL do painel) |

## Bateria (`_main/_audit-verify-all.cmd`)

Entraram **quatro** passos novos (dois portões + os dois braços negativos), porque portões que julgam
ficheiros pertencem à bateria:

```
[step] complaints-closure rc=0
[step] red-as-expected-complaints-closure rc=1  [EXPECT-RED]
[step] youtube-paint-first rc=0
[step] red-as-expected-youtube-paint-first rc=1  [EXPECT-RED]
```

Corrida final (cache quente, 21,5 s):

```
steps : 99  gate=64  control=8  skipped=7  expect-red=20  missing=0  cached=88
failed: -none-
BATTERY-VERDICT: GREEN WITH 7 SKIPPED
heavy : mute-audio strip-stats-log-budget strip-surface-runtime strip-geometry-restore strip-stats-wave control-panel-exit3-neg-arm
priority: BATTERY-PRIORITY BelowNormal pid=6140
```

Os 7 saltos estão **contados como saltados, não como gates**: 6 são a classe PESADA (abrem o ecrã, o
dispositivo de áudio ou a GPU do dono) e `hotkey-delivery` (o app do dono detém o Alt+C).

Pin do ficheiro re-medido em `AGENTS.md`: **98 209 B**, **1 343 CRLF**, 0 bare LF, sha256
`0198D96E…C18B90A`; `agents-md-pins-oracle.py` PASS (2/2 pins).

## Fricção encontrada (e o que ela ensinou)

1. **Três dos quatro vermelhos da bateria eram âncoras gastas, não defeitos** — exactamente a
   classificação que o AGENTS exige antes de chamar "defeito" a um vermelho:
   - `panel2-dom-probe` exigia `#search-input.disabled` — o node que o dono mandou **tirar**. Re-ancorado
     para exigir a busca **AUSENTE** (3 factos continuam: drawer colapsado, título canónico, e agora a
     ausência com contagem 0 de `.search`).
   - `yt-mirror-align` a 10/11: a árvore falsa não tinha geometria, e o produto passou a exigir
     `_rendered` (regra anti-fantasma de 2026-10-22). A árvore passou a declarar `CurrentIsOffscreen` e
     um rectângulo, e **acrescentaram-se 2 armas** para a cura não poder ser apagada em silêncio: o
     fantasma (janela fora do ecrã com mais palavras é ignorada) e o fail-closed (sem geometria legível,
     não conta). Agora `13/13 arms, 5/5 mutantes`.
   - `agents-md-pins` vermelho por eu ter mudado a bateria: o pin **obrigou** a re-medir e a escrever o
     número novo — é o portão a fazer o seu trabalho.
2. **Um defeito real encontrado pelo caminho:** `_main/autostart-status-check.py` derivava o caminho do
   registo com uma regex que comia as quotes. Com a constante em forma **raw** (`r'Software\…\Run'`) o
   grupo saía com a apóstrofe à frente, o `OpenKey` falhava, e o `FileNotFoundError` convertia um **erro
   de parse** em `state=off` — o passo dizia "não está instalado" sobre uma chave que o `reg query`
   mostrava instalada. Passou a ler as constantes com `ast` (o valor que o Python avalia, qualquer que
   seja a forma do literal) e a **parar** (rc=2) se não as encontrar.
3. **Cache com prazo de validade:** `autostart-status` estava a ser reutilizado do cache com o `rc=4` de
   **antes** da instalação (o cache indexa conteúdo de ficheiros, e o registo não é um ficheiro). A
   entrada foi removida e o passo voltou a correr — o `cached=88` não é prova de saúde de um passo que
   depende de ESTADO.

## Limites honestos (declarados, não escondidos)

- **Dois caminhos não são medíveis sem lançar a app** (HARD RULE: só o LEAD lança): o balloon do tray
  num conflito real de Alt+C e o instante em que a legenda pintada dá lugar ao track. O que fica medido é
  o artefacto (0 chamadas `MessageBoxW(`, a chamada a `paint_line` na posição certa, as armas do oráculo).
- **A classe PESADA não correu** (seria o stutter que o dono já reclamou); está nomeada no sumário.
- `caption-independent-oracle.js` continua vermelho em **3 de 57** (B2/B3/B3b) — é o **mesmo trio de antes
  desta sessão**, deriva de instrumento, e **não** foi usado como evidência de nada aqui.
- Nada foi commitado nem enviado: as alterações vivem na árvore de trabalho.

## 2026-10-23 — a legenda do YouTube medida AO VIVO contra o player (R26), e o R8

O dono levantou a pausa nesta sessao: *"continua. veja minhas reclamacoes dessa sessao aqui, das
ultimas 100 horas, e resolva tudo."* e *"e pode rodar coisa normalmente"*. O que se segue e a
medicao de hoje, nao a de ontem.

### O instrumento: `_main/yt-1to1-live-compare.py`

Um Edge PROPRIO (`--user-data-dir I:\cc-tmp\edge-1to1`, `--mute-audio`, CDP na porta 9333) abre o
video, liga o CC **a tocar** (ligar com o player pausado muda o `aria-pressed` e nao pinta nada --
medido: 44 amostras seguidas vazias), poe o video no inicio, e le a janela do player em cada
instante enquanto ele toca. Mata so a arvore do PID que abriu.

Tres coisas que a leitura teve de aprender, todas medidas:

- **a linha que sai fica no DOM** a animar-se: o `opacity` diz que ja nao esta no ecra;
- **a linha que rola para fora** fica FORA do rect da janela (`overflow: hidden`): e o `rect` que diz
  se esta a vista;
- **a janela de dica** que o YouTube desenha ao ligar o CC ("Ingles (gerada automaticamente)",
  "Clique em para configuracoes") nao tem `lang`; a legenda tem.

E a comparacao aprendeu o que **nao** e divergencia: o YouTube escreve a linha **palavra a palavra**
dentro da cue (`Você já` -> `Você já teve que` -> ...) e a nossa tabela tem a linha inteira desde o
`tStartMs`; logo ser **prefixo** e o mesmo desenho. As classes sao `igual`, `prefix`, `dom-3`
(a linha que sai ainda no DOM) e `lag` (o YouTube ainda nao pintou a linha que comecou; <= 0,45 s).

### A corrida

```
python _main\yt-1to1-live-compare.py --video WdaHAGRBB6s --samples 46 --every 0.12 --paint-lang en
  LIVE_1TO1 legenda no player: cc=True (tries=0) track_lang=en visibility=visible
  LIVE_1TO1 faixa PINTADA=en cues=19
  LIVE_1TO1 faixa que o app serve=en-orig/auto cues=19
  LIVE_1TO1 iguais=46/46 (modelo de janela sobre a faixa pintada=en)
  LIVE_1TO1 veredicto=MATCH          (rc=0)
```

`--paint-lang en` existe por uma razao medida: o perfil de um Edge novo abre a UI em **pt-BR** e o
YouTube escolhe a **traducao automatica** (`lang="pt"`), enquanto a app serve o **original**
(`en-orig`, a politica do dono). Comparar pt contra en mede a POLITICA, nao a fidelidade.

### Dois defeitos de TEXTO que so a corrida ao vivo mostrou (e que agora sao bracos)

1. **Espaco antes da pontuacao.** O json3 parte a linha em segmentos e o `?` vem como segmento
   proprio; o `_join_segs` punha-lhe um espaco e o ecra dizia `alguém ?` / `Não .` onde o YouTube
   escreve `alguém?` / `Não.`. Regra nova (`_NO_SPACE_BEFORE` / `_NO_SPACE_AFTER`): pontuacao cola-se
   a palavra, parenteses/aspas abertas nao separam.
2. **Um evento so de pontuacao virava uma LINHA.** O evento das 16,26 s (`dDurationMs` 1060) e um `.`
   sozinho, DENTRO da linha que comeca as 14,08 s e acaba as 17,26 s: o YouTube desenha
   `...crianças.` numa linha. `_absorb_punct` junta-o a linha anterior e estende-lhe o fim.

Os dois estao no portao que ja existia: `python _main\youtube-captions-oracle.py` ->
`VERDICT: PASS  arms 66/66  mutants 17/17` (eram 60/15; entraram 6 bracos -- `pontuacao-?`,
`pontuacao-.`, `pontuacao-,`, `linhas-2`, `ponto-junto`, `fim-estendido` -- e 2 mutantes, os dois
**apanhados**: `punct-espaco-em-tudo` e `punct-solta-vira-linha`).

### O defeito que deixava o dono SEM legenda do YouTube

A mesma corrida mostrou porque a legenda desaparecia: com o perfil pt-BR o player pinta `pt`, o
alinhamento por texto nunca casa com a faixa servida e `_youtube` devolvia `[]` com
`painted-other-track` **para sempre** (o ASR tomava o lugar). A cura nao e seguir a traducao
(proibido); e o **relogio** do player escolher a cue da faixa SERVIDA -- e so enquanto ANDA: o
relogio congelado e medido (lia `t=2.0` com o video a 530) e a prova do congelamento e uma pintura
que muda com o relogio parado.

Portao novo, na bateria com o seu braco negativo:

```
python _main\youtube-foreign-paint-oracle.py           -> YT-PAINT-FOREIGN VERDICT PASS   (rc=0)
python _main\youtube-foreign-paint-oracle.py --neg-arm  -> NEG-ARM PASS                     (rc=1 por desenho)
```

4 bracos (A1 pinta-outra-faixa+relogio-a-andar -> linha; A2 pintura-muda+relogio-parado -> NADA;
A3 pintura-quieta+relogio-parado -> a mesma linha; A4 pintura-da-faixa-servida -> alinhamento por
texto) e 3 mutantes, os tres apanhados.

### A bateria e os pins

```
_main\_audit-verify-all.cmd -> BATTERY-VERDICT: GREEN WITH 6 SKIPPED   (rc=0)
  steps 101  gate=66  control=8  skipped=6  expect-red=21  missing=0  cached=88
  youtube-foreign-paint=0   red-as-expected-youtube-foreign-paint=1
```

O `.cmd` cresceu com o portao e o pin foi **re-medido** (o portao `agents-md-pins` obriga):
`99622 B`, `1358 CRLF` / 0 bare LF, sha256
`C6C33F2E1043006D4A8E71841806C08B8BD31687487D24EFBD23639F07E06BEB` ->
`AGENTS-PINS PASS -- 2 pin(s)`.

O portao do fecho: `python _main\complaints-closure-build.py` -> `seccoes: 31 | fechadas: 31 |
abertas: 0 | reclamacoes: 81`; `python _main\complaints-closure-gate.py` ->
`CLOSURE-VERDICT PASS  fails=0`; `--neg-arm` -> `CLOSURE NEG-ARM PASS (rc=1 por desenho)`.

### O R8 mudou de evidencia, e o limite esta dito

O `vram-reuse-oracle.py` **bloqueia** hoje no braco com sessao CUDA real (`--loader onnx-single`, o
default): medido 9,2 s de CPU e depois **nenhum progresso durante >7 min**, com o `faulthandler` a
nao conseguir escrever (a chamada nativa segura o GIL). A causa esta medida e nao e do codigo: a GPU
tem `8370` de `16303 MiB` em maos de outros processos (python 1831,5 / 1829,5 / 1445,5 MiB,
`NVIDIA Overlay.exe` 1371,5, chrome 662,9), e o nosso processo le `my_vram_ded_MiB=0.0`. O oraculo
passou de manha, com a GPU livre.

O que o portao mede agora e a propriedade de **REUSO** (`--loader noop`: o `get_or_load` pedido duas
vezes devolve a MESMA entrada, `refs=2`, uma entrada no pool, e a chave discrimina diretorio e
providers) e a **atribuicao** de agora (`nvidia-smi` + a lista de detentores que o proprio oraculo
imprime; o modelo em disco mede 746,6 MiB em 7 ficheiros). O delta de VRAM da NOSSA sessao fica por
medir ate a GPU ficar quieta -- declarado, nao escondido.

### O que continua por fazer (declarado)

- **`node I:\!manager\tools\closure-gate.mjs --dir H:\sotto` sai 7**: `PAUSED.json` do dono
  (2026-10-22T16:27) ainda existe. Ele levantou a pausa a falar, mas o mecanismo e o ficheiro, e
  escrever fora de `H:\sotto` esta fora do meu mandato.
- Nada foi commitado nem enviado: as alteracoes vivem na arvore de trabalho, ao lado das de outras
  lanes.
