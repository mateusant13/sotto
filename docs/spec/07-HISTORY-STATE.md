# 07 — HISTÓRICO E ESTADO: tudo o que fica escrito em disco

Este documento responde a uma pergunta só: **o que é que o Sotto em `HEAD` escreve em disco, com que forma, e quem é que o lê?** Não descreve o que devia ser escrito, nem o que foi prometido numa ordem antiga. Cada frase leva etiqueta: `[CODE]` com `ficheiro:linha` (a linha foi lida), `[MEASURED]` com o comando, a saída e a data, ou `[INFERENCE]` com o raciocínio à vista. O que não se conseguiu ler ou medir fica em `[UNKNOWN]` e volta na última secção.

O `HEAD` medido é `b01611830d58dd225272e9f1b2031d4123edecd9`, de `2026-11-11T23:29:24-03:00` `[MEASURED]` (comando `git log -1 --format='%H %cI'`, executado em 2026-11-11).

## 1. O mapa do que fica no disco

| o que fica escrito | quem escreve | quem lê | nota |
|---|---|---|---|
| `history/<AAAA-MM-DD>/<HH>.md` | a shell (`SottoShell.history_append`) `[CODE]` `app/webview/sotto_webview.py:15688` | a própria shell (`_history_entries`) e, por ela, o painel `[CODE]` `app/webview/sotto_webview.py:15935` | uma linha por legenda fechada; a pasta é o dia local e o ficheiro é a hora local `[CODE]` `app/webview/sotto_webview.py:15386` |
| `history/audio/<AAAA-MM-DD>/<HHMMSS>.<kbps>k.opus` | o worker (`AudioRing`) `[CODE]` `worker/audio_ring.py:102` | instrumentos de replay/benchmark `[CODE]` `_main/audio-replay.py:262` | Ogg Opus, 16 kHz mono `[CODE]` `worker/audio_ring.py:24` |
| `history/audio/index.jsonl` | `AudioRing._close_segment` `[CODE]` `worker/audio_ring.py:281` | `read_index` e o replay `[CODE]` `worker/audio_ring.py:440` | uma linha por segmento FECHADO `[CODE]` `worker/audio_ring.py:286` |
| `history/audio/lines.jsonl` | `append_line_anchor` `[CODE]` `worker/audio_ring.py:419` | ferramentas de corte por frase `[CODE]` `worker/audio_ring.py:27` | âncora `t0`/`t1` de parede por legenda `[CODE]` `worker/audio_ring.py:433` |
| `<TMPDIR>/sotto-batch-queue/<id>.json` + `<id>.f32` | `BatchQueue` `[CODE]` `app/webview/batch_queue.py:202` | `BatchExecutor` e o próprio arranque seguinte `[CODE]` `app/webview/batch_queue.py:237` | fila em disco do áudio sem transcrição `[CODE]` `app/webview/batch_queue.py:1` |
| `<TMPDIR>/sotto-batch-queue/adopted.json` | `BatchQueue.adopt_dead_spools` `[CODE]` `app/webview/batch_queue.py:493` | a mesma adopção, na leitura seguinte `[CODE]` `app/webview/batch_queue.py:495` | impede adoptar o mesmo ficheiro duas vezes `[CODE]` `app/webview/batch_queue.py:487` |
| `_main/panel-visibility.json` | `PanelVisibilityWriter` `[CODE]` `app/webview/sotto_webview.py:11546` | worker (`PanelVisibilityReader`) e instrumentos `[CODE]` `worker/engine_switch.py:478` | `visible` é medido (`IsWindowVisible`), nunca intenção `[CODE]` `app/webview/sotto_webview.py:11554` |
| `_main/panel-state.json` | `PanelStateWriter` `[CODE]` `app/webview/panel_state.py:118` | `panel_state.py --read`, sondas e oráculos `[CODE]` `app/webview/panel_state.py:42` | o painel como TEXTO, com idade calculada pelo leitor `[CODE]` `app/webview/panel_state.py:34` |
| `_main/caption-settings.json` | `caption_settings.save` `[CODE]` `app/webview/caption_settings.py:62` | `youtube_captions` no import `[CODE]` `app/webview/youtube_captions.py:609` e `caption_overlay` no import `[CODE]` `app/webview/caption_overlay.py:523` | língua-alvo e aspecto da legenda `[CODE]` `app/webview/caption_settings.py:1` |
| `_main/caption-wanted.json` | `_caption_wanted_store` `[CODE]` `app/webview/sotto_webview.py:21576` | o arranque, só para o registo `[CODE]` `app/webview/sotto_webview.py:21554` | já NÃO decide o arranque `[CODE]` `app/webview/sotto_webview.py:21508` |
| `_main/caption-drag-offset.json` | `caption_drag.save_offset` `[CODE]` `app/webview/caption_drag.py:285` | `caption_overlay` ao criar a janela `[CODE]` `app/webview/caption_overlay.py:620` | `{"x": int, "y": int}` `[CODE]` `app/webview/caption_drag.py:299` |
| `_main/hotkey-settings.json` | `hotkey_settings.set_panels_enabled` `[CODE]` `app/webview/hotkey_settings.py:148` | a shell (`accelerators`, `panels_enabled`) `[CODE]` `app/webview/sotto_webview.py:10372` | teclas e o interruptor do Alt+C `[CODE]` `app/webview/hotkey_settings.py:1` |
| `_main/shell-relaunch.json` | `Relauncher` `[CODE]` `app/webview/shell_relaunch.py:89` | o mesmo vigia, para contar o tecto `[CODE]` `app/webview/shell_relaunch.py:138` | `{"relaunches": [epoch, …]}` `[CODE]` `app/webview/shell_relaunch.py:126` |
| `_main/shell-relaunch.log` | `Relauncher.record` `[CODE]` `app/webview/shell_relaunch.py:173` | humano e instrumentos `[INFERENCE]` (não há leitor em código) | escrito e sincronizado antes de qualquer `os._exit` `[CODE]` `app/webview/shell_relaunch.py:155` |
| `_main/diar-watch.json` | o sidecar de falantes `[CODE]` `worker/speaker_sidecar.py:633` | `watch_payload_if_fresh` `[CODE]` `worker/speaker_bridge.py:186` | payload da Fase A; a chave é `multivoice` `[CODE]` `worker/speaker_bridge.py:191` |
| `_main/webview-run.log` | shell, `run.cmd` e worker `[CODE]` `app/webview/run.cmd:308` | todos | é o recibo vivo `[CODE]` `docs/spec/01-ARCHITECTURE.md:138` |
| `_main/webview-worker-tracebacks.log` | o WORKER (`_death_trace`) `[CODE]` `worker/sotto_worker.py:9411` | instrumentos | tecto 256 KB; ao passar, guarda a metade final `[CODE]` `worker/sotto_worker.py:9433` |

`[INFERENCE]` O desenho é sempre o mesmo: a shell escreve o estado e o worker **lê o ficheiro**, porque não existe canal de comando para o worker (`stdin` é `DEVNULL`, `docs/spec/01-ARCHITECTURE.md:96`). O ficheiro é a interface; por isso cada um tem um formato congelado e um leitor que recusa uma forma que não conhece.

### 1.1 O que existe hoje no disco (medido, não herdado)

`[MEASURED]` 2026-11-11, na raiz `H:/sotto`:

```
$ find history -maxdepth 2 -name '*.md' | wc -l                      -> 24
$ find history -maxdepth 1 -mindepth 1 -type d ! -name audio | wc -l -> 5
$ cat history/*/*.md | wc -l                                         -> 1315
$ find history/audio -name '*.opus' | wc -l                          -> 56
$ du -sb history/audio | cut -f1                                     -> 74588119
$ wc -l history/audio/index.jsonl history/audio/lines.jsonl          -> 53, 7
```

`[INFERENCE]` Os 56 `.opus` contra 53 linhas de `index.jsonl` não são uma contradição demonstrável sem abrir os ficheiros: o índice só recebe um registo quando o segmento FECHA (`worker/audio_ring.py:281`), e um segmento aberto não tem linha. Fica como número medido, não como explicação.

## 2. A linha do histórico

Uma linha gravada tem esta forma, lida do arquivo real:

`[MEASURED]` 2026-11-11, comando `tail -3 history/2026-11-11/18.md`:

```
- [18:04:51] É tipo <!-- ctx1=v:chrome.exe|t:%2899%2B%29%20SrDogg%20-%20Twitch%20-%20Google%20Chrome|u:https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DSmA0cV9_vco route=final producer=redux via=pc start=1269.16 src=worker-stamped reason=hold-timeout -->
```

O escritor monta `- [{HH:MM:SS}] {corpo}{proveniência}\n` `[CODE]` `app/webview/sotto_webview.py:15808`, e a proveniência é um comentário HTML ` <!-- … -->` `[CODE]` `app/webview/sotto_webview.py:15450`. Um leitor de Markdown mostra a frase e nada mais; qualquer leitor do FICHEIRO a retira antes de tratar o resto como texto `[CODE]` `app/webview/sotto_webview.py:15966`.

| chave | valores que o escritor aceita | o que responde | evidência |
|---|---|---|---|
| `ctx1=` | o corpo de `history_context.encode` | de onde veio o som e o que estava à frente | `[CODE]` `app/webview/sotto_webview.py:15418` |
| `route=` | `final`, `provisional-draft`, `batch` | que estrada fechou a linha | `[CODE]` `app/webview/sotto_webview.py:870` |
| `producer=` | `redux`, `live` | que motor fechou a linha | `[CODE]` `app/webview/sotto_webview.py:901` |
| `via=` | `pc`, `youtube`, `external` | de que ÁUDIO veio (o que os dois filtros leem) | `[CODE]` `app/webview/sotto_webview.py:913` |
| `start=` | número com 2 casas | a identidade da linha no relógio de áudio do worker | `[CODE]` `app/webview/sotto_webview.py:15435` |
| `src=` | `worker-stamped`, `worker-stamped-producer`, `panel-deadline`, `fallback` | que ramo decidiu a rota | `[CODE]` `app/webview/sotto_webview.py:892` |
| `reason=` | texto livre, sem `ctx1=` | a regra que disparou no instante da escrita | `[CODE]` `app/webview/sotto_webview.py:15446` |

Um valor fora destas listas **não é escrito**: `_history_provenance` devolve `''` quando a rota não está em `HISTORY_ROUTES`, e omite cada chave cujo valor não pertence ao conjunto `[CODE]` `app/webview/sotto_webview.py:15410`. Sem rota, a linha é escrita sem comentário nenhum — um marcador que ninguém sabe interpretar é pior do que nenhum `[CODE]` `app/webview/sotto_webview.py:867`. O `reason` é limpo de qualquer `ctx1=` antes de ser escrito `[CODE]` `app/webview/sotto_webview.py:15446`, e o token é escrito PRIMEIRO, imediatamente a seguir a `<!--`, para o leitor ancorado ao início não poder ser enganado por um `ctx1=` dentro do texto livre `[CODE]` `app/webview/sotto_webview.py:15419`.

## 3. O `ctx1=`: o contexto de proveniência

O código vive em `app/webview/history_context.py` e responde, nas palavras do módulo, a *"where did this audio come from and what was I looking at when it was said?"* `[CODE]` `app/webview/history_context.py:3`. São cinco campos opcionais, por esta ordem `[CODE]` `app/webview/history_context.py:39`:

| campo | letra | limite | de onde vem |
|---|---|---|---|
| `sourceApp` | `a` | 64 | o alvo do tap por aplicação (`app_target_request`) `[CODE]` `app/webview/sotto_webview.py:15505` |
| `audioSource` | `s` | 96 | o `meta.source` do evento do worker `[CODE]` `app/webview/history_context.py:296` |
| `viewingApp` | `v` | 64 | a janela em primeiro plano, lida por `GetForegroundWindow` `[CODE]` `app/webview/history_context.py:250` |
| `viewingTitle` | `t` | 120 | o título dessa janela `[CODE]` `app/webview/history_context.py:269` |
| `viewingUrl` | `u` | 300 | só quando o chamador a entrega; query, fragment e userinfo saem `[CODE]` `app/webview/history_context.py:75` |

Os limites estão em `MAX_LEN` `[CODE]` `app/webview/history_context.py:45`, e o corpo inteiro tem tecto de 512 caracteres `[CODE]` `app/webview/history_context.py:49`. O que transborda é **cortado**, não apagado: um título CJK de 120 caracteres são 1 080 caracteres codificados sem o tecto, e apagar o campo levaria a origem do áudio com ele `[CODE]` `app/webview/history_context.py:46`. O corte é por caracteres inteiros, nunca dentro de um escape percentual `[CODE]` `app/webview/history_context.py:149`.

- **Codificação.** Pares `letra:valor` unidos por `|`, com o valor percent-encoded por `quote(value, safe='')` `[CODE]` `app/webview/history_context.py:144`. O marcador é `ctx1=<corpo>` `[CODE]` `app/webview/history_context.py:51`.
- **Leitura.** `token_in` procura o token ancorado ao início do comentário, não em qualquer sítio da linha `[CODE]` `app/webview/history_context.py:187`.
- **URL.** Só `http`/`https`; o `netloc` perde o userinfo e baixa a caixa; o path é percent-encoded com o conjunto do parser WHATWG; a query só sobrevive quando o host é do YouTube e `v=` casa `[A-Za-z0-9_-]{6,20}` `[CODE]` `app/webview/history_context.py:93`. A barra final de um host nu é removida `[CODE]` `app/webview/history_context.py:107`.
- **Texto.** Um caracter de controlo é uma QUEBRA de palavra, não algo a apagar: `page\n2` não pode virar `page2` `[CODE]` `app/webview/history_context.py:65`.

### 3.1 Quando é capturado (e por que não é no commit)

A captura é feita na **chegada do evento**, não quando a linha é gravada `[CODE]` `app/webview/history_context.py:12`. `note_history_context` é chamado pelos dois caminhos de emissão enquanto o evento ainda é fresco, com a chave `start=` do worker `[CODE]` `app/webview/sotto_webview.py:15559`, e guarda um anel de 24 entradas `[CODE]` `app/webview/sotto_webview.py:15587`.

| regra | o que impede | evidência |
|---|---|---|
| anel + tolerância 0,05 s no `start=` | uma linha herdada de outra fala | `[CODE]` `app/webview/sotto_webview.py:15609` |
| último snapshot só se `|start − last_start| ≤ 8,0 s` | uma janela de outro momento | `[CODE]` `app/webview/sotto_webview.py:15627` |
| mudança de sessão limpa o anel | um reinício do worker recomça o relógio em zero e herdaria a janela antiga | `[CODE]` `app/webview/sotto_webview.py:15552` |
| leitura de foreground com TTL de 0,5 s | uma rajada de finais a abrir `USER32` por linha | `[CODE]` `app/webview/history_context.py:54` |

O contexto explícito do chamador ganha **campo a campo**; o anel só preenche o que o chamador omitiu, e nesse caminho não há leitura de foreground no commit `[CODE]` `app/webview/sotto_webview.py:15730`. `nothing here starts a process, opens a window, reads pixels or takes input` `[CODE]` `app/webview/history_context.py:25`.

## 4. A regra de fusão (`history_merge`)

O histórico guarda a LINHA, não o fluxo: a mesma linha a crescer reescreve a última gravada, uma cópia idêntica não entra, e só uma linha nova acrescenta `[CODE]` `app/webview/sotto_webview.py:934`. A janela é de 3,0 s `[CODE]` `app/webview/sotto_webview.py:931`.

As três identidades, por ordem de força `[CODE]` `app/webview/sotto_webview.py:942`:

1. O `start=` do worker é a identidade da linha: dois registos com o mesmo `start` (tolerância 0,05 s) são a mesma linha, mesmo que o texto tenha encolhido `[CODE]` `app/webview/sotto_webview.py:971`.
2. Um `start` diferente é uma linha diferente, mesmo com texto idêntico — uma repetição real entra `[CODE]` `app/webview/sotto_webview.py:1000`.
3. Sem `start`, o prefixo nos dois sentidos dentro da janela; texto idêntico sem identidade só é duplicado dentro da janela `[CODE]` `app/webview/sotto_webview.py:1022`.

| situação | decisão | evidência |
|---|---|---|
| texto igual + `start` distinto | `append` | `[CODE]` `app/webview/sotto_webview.py:1000` |
| texto igual + `audioSource` diferente | `append` | `[CODE]` `app/webview/sotto_webview.py:1002` |
| texto igual + `via` diferente | `append` | `[CODE]` `app/webview/sotto_webview.py:1004` |
| texto igual, sem start, pausa > 3 s | `append` | `[CODE]` `app/webview/sotto_webview.py:1008` |
| a leitura ENCOLHEU e é a mesma linha | `skip`, com `HISTORY_SHRINK_KEPT` | `[CODE]` `app/webview/sotto_webview.py:1044` |
| mesmo `start`, cresceu, mesma `via` | `replace` | `[CODE]` `app/webview/sotto_webview.py:1048` |
| cresceu, mas `start` distinto | `append` | `[CODE]` `app/webview/sotto_webview.py:1057` |
| cresceu, sem start, pausa ≤ 3 s | `replace`; fora da janela, `append` | `[CODE]` `app/webview/sotto_webview.py:1060` |

O `_merge_key` compara sem a pontuação final, porque `... going for.` e `... going for there.` são a mesma frase a crescer `[CODE]` `app/webview/sotto_webview.py:1160`.

### 4.1 `replace_at`: a segunda passagem no lugar da primeira

Quando o `history_merge` diz `append` e a linha nova traz um `start=`, a shell relê o ficheiro à procura de uma linha JÁ gravada com esse `start` (`_history_find_start`, tolerância 0,05 s) `[CODE]` `app/webview/sotto_webview.py:15634`. Se a encontrar, reescreve-a onde ela está em vez de acrescentar outra `[CODE]` `app/webview/sotto_webview.py:15757`.

- Uma linha do lote (`producer=redux`) **não é sobrescrita** pelo ao vivo: o lote fica, e o registo diz `HISTORY_FUSED_KEPT producer=redux start=… why=batch-wins` `[CODE]` `app/webview/sotto_webview.py:15759`.
- `via` diferente nunca funde: o `start` do YouTube é `time.monotonic()` e o do worker é o relógio de áudio, dois espaços de números que podem coincidir `[CODE]` `app/webview/sotto_webview.py:15646`.
- Sem `start=` não se reescreve nada: sem identidade, a resposta é "não sei" `[CODE]` `app/webview/sotto_webview.py:15756`.

Quando a acção é `replace`, o contexto da linha anterior é preservado e o novo ganha campo a campo, para uma linha que cresce nunca perder a origem `[CODE]` `app/webview/sotto_webview.py:15766`.

As etiquetas de log desta secção são `HISTORY_APPEND`, `HISTORY_LINE_MERGED`, `HISTORY_FUSED`, `HISTORY_DUPLICATE_SKIPPED`, `HISTORY_SHRINK_KEPT`, `HISTORY_FUSED_KEPT` `[CODE]` `app/webview/sotto_webview.py:15847`. `[MEASURED]` 2026-11-11: `grep -c "HISTORY_APPEND\|HISTORY_FUSED\|HISTORY_DUPLICATE_SKIPPED" _main/webview-run.log` → `1224` (número agregado das três etiquetas no log vivo, não uma contagem de linhas do histórico).

## 5. Que linhas são admitidas — e a recusa exata

Há **dois** portões, e eles não dizem a mesma coisa `[CODE]` `app/panel/history-source.js:130` e `[CODE]` `app/webview/sotto_webview.py:15699`.

### 5.1 O portão do painel: a rota

A decisão única está em `app/panel/history-source.js`, função `historyDecision` `[CODE]` `app/panel/history-source.js:130`. O predicado, ao pé da letra:

| `meta.route` | `meta.producer` | decisão | motivo da recusa | evidência |
|---|---|---|---|---|
| `final` | qualquer | entra como `final` | — | `[CODE]` `app/panel/history-source.js:132` |
| `provisional-draft` | qualquer | recusa | `provisional-draft` | `[CODE]` `app/panel/history-source.js:136` |
| outra rota não vazia | qualquer | recusa | `unknown-route` | `[CODE]` `app/panel/history-source.js:133` |
| ausente/vazia | `redux` | entra como `batch` | — | `[CODE]` `app/panel/history-source.js:139` |
| ausente/vazia | `live` ou ausente | recusa | `no-route-no-producer` | `[CODE]` `app/panel/history-source.js:140` | O produtor deixou de ser o portão em 2026-11-05: é proveniência, escrita na linha como `producer=`, para um leitor distinguir uma linha Parakeet de uma linha de streaming sem a segunda desaparecer `[CODE]` `app/panel/history-source.js:118`.

A recusa não é silenciosa: `reportHistoryRefusal` conta por assinatura e envia a primeira ocorrência e cada 50.ª `[CODE]` `app/panel/panel.js:2379`, e a shell escreve `HISTORY_REFUSED where=… reason=… route=… final=… producer=… src=… n=… total=…` `[CODE]` `app/webview/sotto_webview.py:12398`.

### 5.2 O portão do arquivo: a shell

`history_append` recusa **apenas** duas coisas: corpo vazio `[CODE]` `app/webview/sotto_webview.py:15691` e `route == 'provisional-draft'`, que responde `None` e escreve `HISTORY_REFUSED where=history_append reason=provisional-draft …` `[CODE]` `app/webview/sotto_webview.py:15699`. Qualquer outra chamada directa com um corpo não vazio e uma rota diferente — ou sem rota nenhuma — é escrita.

`[INFERENCE]` É por isso que os dois portões têm de existir: o painel é o único chamador de produção (`_history_append`, `app/webview/sotto_webview.py:12355`, chamado a partir de `recordHistory`, `app/panel/panel.js:2249`), mas a shell não confia nisso e repete a invariante mais forte que ela própria pode provar.

### 5.3 O terceiro filtro: a leitura

Na leitura, `_history_entries` aplica mais duas regras que **não alteram o disco** `[CODE]` `app/webview/sotto_webview.py:15971`:

- colapsa corridas de repetição (`text_normalize.collapse_runs`) `[CODE]` `app/webview/sotto_webview.py:15971` e descarta a linha inteira quando é só preenchimento (`is_filler_line`) `[CODE]` `app/webview/sotto_webview.py:15972`, com a justificação medida no comentário: 121 das 1 302 linhas do arquivo do dono, 9,3 %, eram `Mmm` `[CODE]` `app/webview/sotto_webview.py:15967`. `[INFERENCE]` A linha continua no ficheiro e continua a contar para `wc -l`; o que ela não faz é aparecer na cauda, na busca ou na exportação.

## 6. Retenção: a janela e a poda

`HISTORY_RETENTION_H` é `4320` horas, ou 180 dias, com `SOTTO_HISTORY_RETENTION_H` a sobrepor `[CODE]` `app/webview/sotto_webview.py:835`. A docstring diz porquê: a janela de 48 h de 2026-11-06 foi substituída pelo recall de meses em 2026-11-09 `[CODE]` `app/webview/sotto_webview.py:829`.

A poda corre na **primeira escrita de cada hora**, não num ficheiro de relógio nem num processo à parte `[CODE]` `app/webview/sotto_webview.py:15896`. O algoritmo é:

1. listar as pastas de dia que casam `^\d{4}-\d{2}-\d{2}$` `[CODE]` `app/webview/sotto_webview.py:15902`;
2. comparar o NOME da pasta com a data de corte (strings `YYYY-MM-DD`, ordem lexicográfica = ordem de calendário) e saltar as que são `>= oldest` `[CODE]` `app/webview/sotto_webview.py:15908`;
3. apagar os `.md` dessa pasta `[CODE]` `app/webview/sotto_webview.py:15916` e só depois `os.rmdir` — a pasta só desaparece se ficar vazia `[CODE]` `app/webview/sotto_webview.py:15920`;
4. se algo foi removido, escrever `HISTORY_PRUNE removed=… keep_h=… oldest=…` `[CODE]` `app/webview/sotto_webview.py:15924`.

`[INFERENCE]` A poda é por DIA, não por hora: uma pasta de dia mais nova que a data de corte fica inteira, mesmo que a hora seja anterior ao instante de corte. O painel usa o mesmo número para filtrar a cauda já lida, sem uma segunda leitura do disco `[CODE]` `app/panel/panel.js:77`.

**Não existe um corte de 60 dias em `HEAD`.** `[MEASURED]` 2026-11-11: `grep -n "4320" app/webview/sotto_webview.py app/panel/panel.js app/panel/history-store.js` → `sotto_webview.py:835 … or 4320)`, `panel.js:73 … passou a 4320 h (180 dias)`, `panel.js:77 … = 4320;`, `history-store.js:41 … || 4320;`; `grep -n "2160\|60 day"` nos mesmos três ficheiros → sem saída (`rc=1`). A tarefa que pediu este documento dizia "60 dias"; o código diz 180, e este documento descreve o código.

## 7. Ler, procurar e exportar

### 7.1 A cauda

`_history_entries` devolve um fluxo do mais NOVO para o mais ANTIGO, invertendo a ordem dos ficheiros e a ordem das linhas dentro de cada ficheiro `[CODE]` `app/webview/sotto_webview.py:15935`. Cada entrada leva `date`, `hour`, `time`, `text`, `path`, `context` e `via` `[CODE]` `app/webview/sotto_webview.py:15975`.

O texto que sai daqui não é o texto cru: `close_line` acrescenta o ponto final quando a prosa e a pausa o provam, e devolve a string intacta quando não há evidência `[CODE]` `app/webview/prose_punct.py:94`. A pausa é a diferença entre o fim desta linha e o fim da seguinte, um teto do silêncio que inclui a latência de escrita `[CODE]` `app/webview/sotto_webview.py:15956`.

`history_tail(limit=400)` corta as N mais novas e volta a inverter para o mais antigo primeiro `[CODE]` `app/webview/sotto_webview.py:15991`. O painel pede `HISTORY_LOAD = 400` no arranque e guarda no máximo `MAX_HISTORY = 500` entradas `[CODE]` `app/panel/panel.js:65`.

### 7.2 A busca (`history_search`)

São três camadas, por esta ordem, e a ordem é o produto `[CODE]` `app/webview/sotto_webview.py:12424`:

| camada | regra | o que encontra | evidência |
|---|---|---|---|
| 0 literal | a query dobrada é substring do texto dobrado | a frase exata, com acentos dobrados (`maçã` ← `maca`) | `[CODE]` `app/webview/sotto_webview.py:1323` |
| 1 fonética | TODAS as palavras da query têm um Soundex igual em alguma palavra da entrada | a palavra que ele queria dizer | `[CODE]` `app/webview/sotto_webview.py:1331` |
| 2 fuzzy | cada palavra da query está a uma distância de edição limitada de alguma palavra | gralhas, uma letra a mais ou a menos | `[CODE]` `app/webview/sotto_webview.py:1340` |

O orçamento de edição é `ceil(0.34 × len)`, limitado a 2 e a zero para palavras com menos de 4 letras `[CODE]` `app/webview/sotto_webview.py:1208`. A distância é por PALAVRA, nunca sobre a frase inteira `[CODE]` `app/webview/sotto_webview.py:1334`.

Cada camada tem o seu tecto, e não são iguais: `SEARCH_LAYER_CAPS = (1.0, 0.25, 0.05)` com um piso `(1, 8, 4)` `[CODE]` `app/webview/sotto_webview.py:12428`. Com `limit=200` isso dá 200 literais, 50 fonéticas e 10 fuzzy. `[INFERENCE]` O tecto separado existe porque a camada fonética devolve 172 candidatos para `maca` num arquivo de 2 077 linhas — o comentário mede-o e explica que `mais`/`faca`/`massa` são todos `M200` `[CODE]` `app/webview/sotto_webview.py:12418`.

Se a query não casar o texto, a busca tenta o CONTEXTO da linha (app, título, origem do áudio), com as mesmas três camadas `[CODE]` `app/webview/sotto_webview.py:16039`. Cada hit leva `match` = `literal`, `phonetic` ou `fuzzy`, para o painel poder dizer PORQUE casou `[CODE]` `app/webview/sotto_webview.py:16054`.

### 7.3 A exportação

`history_export(fmt, limit)` produz texto compacto, do mais antigo para o mais novo, com o contexto depois da frase `[CODE]` `app/webview/sotto_webview.py:16062`. `fmt` é `txt` (por omissão) ou `md`; um `fmt` desconhecido cai em `txt`; `limit` é preso a `[1, 5000]` `[CODE]` `app/webview/sotto_webview.py:16083`. Cada linha é `[AAAA-MM-DD HH:MM:SS] texto` seguida, quando existe, de ` · view=… · audio=… · source=… · url=…` `[CODE]` `app/webview/sotto_webview.py:16113`.

`history_export_file` deriva do mesmo corpo — nunca de um segundo arquivo — e escreve `history/sotto-transcript-<AAAAMMDD-HHMMSS>.txt` (ou `.md`) `[CODE]` `app/webview/sotto_webview.py:16131`. Uma exportação vazia não cria ficheiro `[CODE]` `app/webview/sotto_webview.py:16128`; uma falha de escrita é uma recusa nomeada com `HISTORY_EXPORT_FAILED` `[CODE]` `app/webview/sotto_webview.py:16138`, e o sucesso escreve `HISTORY_EXPORT path=… entries=… format=…` `[CODE]` `app/webview/sotto_webview.py:16142`.

`reveal_in_folder` abre o Explorer com `CREATE_NO_WINDOW` e recusa qualquer caminho fora da raiz do histórico, comparando com `normcase` e mantendo a caixa original para o comando e o log `[CODE]` `app/webview/sotto_webview.py:16155`. Um caminho ausente não abre nada e escreve `REVEAL_MISSING` `[CODE]` `app/webview/sotto_webview.py:16178`; um caminho fora da raiz escreve `REVEAL_REFUSED reason=outside-history-root` `[CODE]` `app/webview/sotto_webview.py:16171`.

## 8. Áudio em disco

### 8.1 O anel de 12 horas (`history/audio/`)

O worker mantém o áudio INTEIRO das últimas 12 horas, para replay e benchmark `[CODE]` `worker/audio_ring.py:1`. O desenho é por SEGMENTOS de 10 minutos — 72 ficheiros para 12 h `[INFERENCE]` (600 s × 72 = 43 200 s = 12 h) — e não um ficheiro por bloco, porque escrever um ficheiro por bloco é a classe de defeito que o repositório já pagou `[CODE]` `worker/audio_ring.py:8`.

| parâmetro | valor | evidência |
|---|---|---|
| horas guardadas | 12,0 (`SOTTO_AUDIO_RING_HOURS`) | `[CODE]` `worker/audio_ring.py:42` |
| bitrate | 24 kbps (`SOTTO_AUDIO_RING_KBPS`) | `[CODE]` `worker/audio_ring.py:43` |
| duração do segmento | 600 s | `[CODE]` `worker/audio_ring.py:44` |
| tecto da fila | 120 s de áudio; o que transborda é CONTADO em `dropped_s` | `[CODE]` `worker/audio_ring.py:49` |
| tecto em MB | 600 MB; o mais velho sai primeiro | `[CODE]` `worker/audio_ring.py:50` |
| ligado por omissão | sim, `SOTTO_AUDIO_RING` só desliga com `0`/`no`/`false`/vazio | `[CODE]` `worker/audio_ring.py:114` |
| desligado em | `--selftest` e `--audio` (replay de ficheiro) | `[CODE]` `worker/sotto_worker.py:6775` |

O escritor nunca bloqueia o fio do áudio: `push` copia o bloco e faz `put_nowait`; se a fila estourar, perde o bloco e conta os segundos `[CODE]` `worker/audio_ring.py:208`. O `_prune` apaga por idade e depois por MB `[CODE]` `worker/audio_ring.py:388`, e **nunca** apaga o segmento aberto — o `mtime` dele fica parado enquanto não chega áudio `[CODE]` `worker/audio_ring.py:373`.

Cada segmento fechado ganha uma linha em `index.jsonl` com `file`, `t0`, `t1`, `samples`, `rate`, `kbps` e `bytes` `[CODE]` `worker/audio_ring.py:286`. Cada legenda fechada ganha uma linha em `lines.jsonl` com `t0`, `t1`, `text` e, quando existe, `source` `[CODE]` `worker/sotto_worker.py:5436`.

### 8.2 O áudio que ficou sem transcrição

São dois sítios diferentes, e o documento não os confunde:

**O spool do worker** (`worker/live_queue.py`, `PendingAudio`) guarda o áudio capturado enquanto nenhum motor está carregado: fica em RAM até 120 s `[CODE]` `worker/live_queue.py:56` e transborda para `sotto-pending-audio-<pid>` como `float32` cru, na ordem, e **não há caminho que deite um bloco fora** `[CODE]` `worker/live_queue.py:251`; `dropped` existe para o oráculo exigir zero `[CODE]` `worker/live_queue.py:309`. **A fila em disco da shell** (`batch_queue.py`) adopta os spools de workers que já não existem `[CODE]` `app/webview/batch_queue.py:477` e transcreve-os com prioridade baixa, só no nível `leve` `[CODE]` `app/webview/batch_queue.py:713` (secção 9).

`[INFERENCE]` O rótulo da tarefa — "áudio guardado sem transcrição (`history/audio/`)" — descreve o anel da secção 8.1, que guarda TODO o áudio e não só o não transcrito. O áudio sem transcrição, no sentido estrito, vive no spool do worker e na fila de lote, não em `history/audio/`. Ver `## Lacunas`.

## 9. A fila de lote: contrato em disco

`BatchQueue` é uma fila em disco; o disco é o estado, e não há índice em RAM que um restart perca `[CODE]` `app/webview/batch_queue.py:202`. O directório resolve por `SOTTO_BATCH_QUEUE_DIR`, depois `TMPDIR/sotto-batch-queue`, depois `I:\cc-tmp/sotto-batch-queue`, depois o temp do sistema `[CODE]` `app/webview/batch_queue.py:132`.

O manifesto é `<id>.json` e o áudio `<id>.f32`; o `id` é `<epoch ms>-<pid>-<seq>` e é ordenável, para a ordem de chegada sobreviver a um restart `[CODE]` `app/webview/batch_queue.py:331`. O manifesto tem `id`, `created`, `rate`, `samples`, `seconds`, `source`, `state`, `attempts` e `retry_at` `[CODE]` `app/webview/batch_queue.py:360`.

| estado | significado | transição | evidência |
|---|---|---|---|
| `queued` | à espera | `claim` → `inflight` | `[CODE]` `app/webview/batch_queue.py:301` |
| `inflight` | um filho a correr | no arranque, volta a `queued` e conta `recovered` | `[CODE]` `app/webview/batch_queue.py:281` |
| `done` | transcrito; o `.f32` é apagado | — | `[CODE]` `app/webview/batch_queue.py:424` |
| `failed` | 3 tentativas falhadas; guarda o erro (até 2 000 caracteres) | — | `[CODE]` `app/webview/batch_queue.py:443` |

Regras que se pagam sozinhas:

- **O payload vai primeiro, o manifesto depois.** Um crash entre os dois deixa payload sem manifesto, que não é fila, em vez de um manifesto a apontar para áudio inexistente `[CODE]` `app/webview/batch_queue.py:339`.
- **Escrita atómica** por `.tmp` + `os.replace`, com `fsync` `[CODE]` `app/webview/batch_queue.py:179`.
- **Um bloco com menos de 4 bytes ou comprimento não múltiplo de 4 é recusado** como `BATCH_QUEUE_ENQUEUE_REFUSED reason=payload-not-float32` `[CODE]` `app/webview/batch_queue.py:346`.
- **3 tentativas** e depois `failed` `[CODE]` `app/webview/batch_queue.py:76`, com 60 s entre tentativas `[CODE]` `app/webview/batch_queue.py:80`; **`DONE_KEEP = 200`** faz sair do directório os `done` mais antigos `[CODE]` `app/webview/batch_queue.py:84`.

### 9.1 `adopted.json`: a memória da adopção

`adopt_dead_spools` varre directórios `sotto-pending-audio-<pid>`, e só adopta quando o pid **não está vivo** — um worker vivo ainda vai transcrever aquele áudio, e copiá-lo agora duplicaria a frase `[CODE]` `app/webview/batch_queue.py:477`. Um ficheiro só é adoptado se tiver pelo menos 2 s `[CODE]` `app/webview/batch_queue.py:72`, e a chave `(caminho, tamanho, mtime)` fica em `adopted.json` para a segunda leitura não duplicar o mesmo ficheiro `[CODE]` `app/webview/batch_queue.py:487`. A cópia não apaga a origem: o spool pertence ao worker, e o `sweep_spool_dir` dele limpa-o no arranque seguinte `[CODE]` `app/webview/batch_queue.py:485`. A adopção escreve `BATCH_QUEUE_ADOPTED files=… roots=… pending_s=…` `[CODE]` `app/webview/batch_queue.py:532`.

### 9.2 Quem corre o lote, e a que preço

O `BatchExecutor` corre o Parakeet em modo lote, num filho `BELOW_NORMAL`, **sem abrir dispositivo de áudio nenhum** `[CODE]` `app/webview/batch_queue.py:30`. Só o nível `leve` o deixa correr `[CODE]` `app/webview/batch_queue.py:713`; se a carga subir, mata o filho, devolve o bloco à fila e escreve `BATCH_EXEC_YIELDED … o bloco volta a fila` `[CODE]` `app/webview/batch_queue.py:771`.

O orçamento de CPU é 12 % de um núcleo e o período deriva do custo medido: `idle = custo × (1 − 0,12) / 0,12`, com o log `BATCH_CPU_BUDGET used_ms=… budget=… rate=… idle_ms=…` `[CODE]` `app/webview/batch_queue.py:837`. O filho leva `OMP_NUM_THREADS` e as irmãs BLAS a 2 `[CODE]` `app/webview/batch_queue.py:119`.

A fila é armada por `load_shedding.open_action`, que constrói `BatchQueue` e `open_executor` `[CODE]` `app/webview/load_shedding.py:1261`. `[INFERENCE]` O executor é construído mesmo quando a acção de shedding está desarmada, porque a construção está fora do `if armed` `[CODE]` `app/webview/load_shedding.py:1253`.

### 9.3 Uma carga do motor por LOTE, não por bloco

O driver do lote é um PROCESSO por bloco e, antes de decodificar, ele carrega o Parakeet ONNX
int4 inteiro — ~1,9 GB de páginas de um `mmap`, lidas em operações de ~4 MB `[CODE]`
`app/webview/batch_queue.py:1109`. Enquanto um bloco por filho foi a regra, cada bloco pagava essa
leitura: com cinco blocos pendentes são cinco cargas do mesmo modelo, para transcrever áudio que já
está no disco.

`[MEASURED]` O watcher mediu exactamente essa forma no dono, em 2026-11-12 05:0x:
`python.exe(53836)` = `io 162.4 MB/s (40 ops/s, 4060 KB/op)`, `cmdline = … batch_queue.py
--transcribe …\1794459181885-57128-0001.f32 --rate 16000 --window-s 15.0 --json`, durante um
episódio de stutter — **40 × 4 060 KB/s** é o perfil de uma carga de modelo, não de uma decodificação
de 15 s de áudio. O mesmo directório de spool tinha seis payloads da mesma shell com ids separados
por 5,5 s `[MEASURED]` `ls -l I:/cc-tmp/sotto-batch-queue` (2026-11-12): seis blocos, seis cargas.

O contrato passou a ser: **um filho serve até `MAX_BLOCKS_PER_CHILD = 8` blocos com UMA carga do
motor** `[CODE]` `app/webview/batch_queue.py:134`. O executor pede os blocos com `next_entries`
`[CODE]` `app/webview/batch_queue.py:321`, monta um comando só com N payloads e N ids `[CODE]`
`app/webview/batch_queue.py:746`, e o driver carrega o backend uma vez e responde **um `result` por
`id`** `[CODE]` `app/webview/batch_queue.py:1222`. O executor só marca `done` o bloco cujo resultado
chegou; sem resultado ele nomeia o defeito (`no-result`) em vez de dar o áudio por transcrito
`[CODE]` `app/webview/batch_queue.py:872`.

O tecto de 8 não é gosto: o `BATCH_CPU_BUDGET` é uma **média** sobre o que o laço serve, e o `yield`
por carga alta tem de ter onde cortar entre um bloco e o seguinte — oito blocos de 15 s são 2 min de
áudio por carga, e o custo de uma carga fica amortizado em oito `[INFERENCE]`.

`[MEASURED]` Portão: `batch-queue-drain-oracle` arm `one-load-per-batch` mede um `step()` com oito
blocos e exige **um** spawn com oito payloads e oito ids, com os oito `done`, e o CONTROL força o
tecto a 1 e exige **oito** spawns — senão o braço estaria a medir o desenho antigo. Medido:
`spawns=1 payloads=8 ids=8 done=8 state=done tecto=8 control_spawns=8`, `VERDICT: PASS (6/6 arms)`.

## 10. Cada ficheiro de estado e o seu contrato

| ficheiro | forma | escritor | leitor | falha |
|---|---|---|---|---|
| `caption-settings.json` | `{"target_lang": "pt", "opacity": 1.0, "plate": "tight"}` | `caption_settings.save` (tmp + `os.replace`) `[CODE]` `app/webview/caption_settings.py:62` | `youtube_captions` no import `[CODE]` `app/webview/youtube_captions.py:609`; `caption_overlay` no import `[CODE]` `app/webview/caption_overlay.py:523` | ausente/partido cai em `pt`/1.0/`tight` `[CODE]` `app/webview/caption_settings.py:40`; `opacity` é preso a `[0,30, 1,0]` e um `plate` fora de `tight|normal` cai em `tight` `[CODE]` `app/webview/caption_settings.py:59` |
| `caption-wanted.json` | `{"on": bool, "at": ISO-8601}` | `_caption_wanted_store`, tmp + `os.replace` `[CODE]` `app/webview/sotto_webview.py:21576` | o arranque lê-o para o log, **não** para decidir `[CODE]` `app/webview/sotto_webview.py:21560` | ausente é o normal; a decisão é pura e ignora o `on` gravado `[CODE]` `app/webview/sotto_webview.py:21526` |
| `caption-drag-offset.json` | `{"x": int, "y": int}` | `save_offset` no fim de um arrasto com movimento `[CODE]` `app/webview/caption_drag.py:285` | `load_offset` ao criar a janela `[CODE]` `app/webview/caption_overlay.py:620` | qualquer erro devolve `(0, 0)` `[CODE]` `app/webview/caption_drag.py:274` |
| `hotkey-settings.json` | `{"panels": str, "live": str, "panels_enabled": bool}` | `write` / `set_panels_enabled`, via `panel_state.write_atomic` `[CODE]` `app/webview/hotkey_settings.py:99` | `accelerators()['live']` `[CODE]` `app/webview/sotto_webview.py:10372` e `panels_enabled()` `[CODE]` `app/webview/sotto_webview.py:26206` | JSON partido cai nas teclas de fábrica `[CODE]` `app/webview/hotkey_settings.py:55`; `panels_enabled` só é `False` se o ficheiro disser literalmente `false` `[CODE]` `app/webview/hotkey_settings.py:145` |
| `panel-visibility.json` | schema `sotto.panel-visibility/1`: `visible`, `since_ms`, `age_ms`, `pid`, `reason`, `transitions`, `writtenAt`, `writtenAtEpoch`, `staleAfterSeconds`, mais `shed` `[CODE]` `app/webview/sotto_webview.py:11775`, `park` `[CODE]` `app/webview/sotto_webview.py:11785` e `geometry` `[CODE]` `app/webview/sotto_webview.py:11800` (campos base em `[CODE]` `app/webview/sotto_webview.py:11746`) | `PanelVisibilityWriter`, no fio `sotto-panel-visibility` `[CODE]` `app/webview/sotto_webview.py:11644` | worker `PanelVisibilityReader` `[CODE]` `worker/engine_switch.py:478`; `engine_parked_now` `[CODE]` `worker/sotto_worker.py:1175` | o leitor falha para `visible=true`: ficheiro ausente, ilegível, forma desconhecida ou `visible` não-bool tudo vale "continuar a transcrever" `[CODE]` `worker/engine_switch.py:486` |
| `panel-state.json` | schema `sotto.panel-state/1` + `writtenAt`, `writtenAtEpoch`, `ageSeconds` (idade NA escrita), `staleAfterSeconds`, `producerPid` `[CODE]` `app/webview/panel_state.py:59` | `PanelStateWriter` a cada 2,0 s `[CODE]` `app/webview/sotto_webview.py:366` | `panel_state.py --read`, sondas, oráculos `[CODE]` `app/webview/panel_state.py:42` | a idade autoritativa é calculada pelo LEITOR: um produtor morto não pode actualizar um número dentro do ficheiro que parou de escrever `[CODE]` `app/webview/panel_state.py:34` |
| `shell-relaunch.json` | `{"relaunches": [epoch, …]}` `[CODE]` `app/webview/shell_relaunch.py:126` | `Relauncher` `[CODE]` `app/webview/shell_relaunch.py:252` | `within_cap` `[CODE]` `app/webview/shell_relaunch.py:138` | tecto de 3 relançamentos por hora `[CODE]` `app/webview/shell_relaunch.py:69`; a recusa fala uma vez por minuto, não a cada sonda `[CODE]` `app/webview/shell_relaunch.py:80` |
| `diar-watch.json` | payload da Fase A com a chave `multivoice` `[CODE]` `worker/speaker_bridge.py:191` | `speaker_sidecar` `[CODE]` `worker/speaker_sidecar.py:633` | `speaker_bridge.watch_payload_if_fresh` `[CODE]` `worker/speaker_bridge.py:194` | ausente, vazio, a meio de escrita, JSON inválido, velho demais ou grande demais → `None`, que significa "nada mudou" `[CODE]` `worker/speaker_bridge.py:199` |

### 10.1 O arranque da legenda não obedece ao ficheiro

`caption_wanted_at_start` é pura e devolve `(on, reason)` `[CODE]` `app/webview/sotto_webview.py:21508`:

1. `SOTTO_CAPTION_WANTED_DEFAULT=0|1` ganha a tudo `[CODE]` `app/webview/sotto_webview.py:21539`; uma largada de lane (`SOTTO_LANE_LAUNCH=1`) desliga `[CODE]` `app/webview/sotto_webview.py:21547`.
2. Uma flag de medição (`--dump-dom`, `--selftest`, `--memory`, `--no-hotkey`, `--exit-after`, `--probe-*`) desliga `[CODE]` `app/webview/sotto_webview.py:21550`; caso contrário liga, com razão `default` `[CODE]` `app/webview/sotto_webview.py:21552`.

O `stored=false` continua a ser lido e o desacordo fica no log: `CAPTION_WANTED_START_OVERRIDES stored=false -- o arranque liga a legenda` `[CODE]` `app/webview/sotto_webview.py:21570`. `[MEASURED]` 2026-11-11, o ficheiro vivo: `cat _main/caption-wanted.json` → `{"on": false, "at": "2026-11-11T17:41:48"}` — ou seja, em `HEAD` este ficheiro está a contradizer o arranque e é o log que o diz.

### 10.2 O `panels` do `hotkey-settings.json` não é lido

`[MEASURED]` 2026-11-11: `grep -rn "hotkey_settings.write\|hotkey_config().write" app/` → sem saída; `grep -rn "settings.write" _main/altc-gesture-oracle.py` → linhas `797`, `802` e `807`, as três de um oráculo. A tecla dos PAINÉIS que a shell registra vem de `--hotkey` (fábrica `Alt+C`) `[CODE]` `app/webview/sotto_webview.py:25495`, e o que a shell lê do ficheiro é `accelerators()['live']` `[CODE]` `app/webview/sotto_webview.py:10372` e `panels_enabled()` `[CODE]` `app/webview/sotto_webview.py:26206`. `[INFERENCE]` A chave `panels` é, em `HEAD`, um campo escrito pela API do módulo e por nenhum caminho de produto.

### 10.3 O isolamento por mutex

Uma corrida de medição com `--mutex-name` escreve `panel-state.<mutex>.json`, não o ficheiro do dono `[CODE]` `app/webview/sotto_webview.py:15342`. O motivo é medido: uma instância de medição já publicou `PANEL_STATE_WRITER path=H:\sotto\_main\panel-state.json` com o seu próprio pid, no mesmo ficheiro que a app do dono usa `[CODE]` `app/webview/sotto_webview.py:15323`. O caminho por omissão, com o mutex de produção, é devolvido byte a byte sem alteração `[CODE]` `app/webview/sotto_webview.py:15339`.

## 11. O comportamento do histórico no painel

### 11.1 O contrato da API

O objecto `window.sotto.history` expõe `append`, `tail`, `search`, `root`, `export`, `exportFile` e `reveal` `[CODE]` `app/webview/sotto_webview.py:10995`. Os pedidos viajam com um `id` e a resposta volta por `window.__sotto_history(id, payload)` `[CODE]` `app/webview/sotto_webview.py:10768`. `[INFERENCE]` `historyCall` não tem prazo: a `Promise` só resolve quando a shell responder `[CODE]` `app/webview/sotto_webview.py:10774`, e um handler que nunca responda deixa-a pendente — ver `## Lacunas`.

`history.root()` devolve `{'root': <caminho>, 'canonicalProducer': 'the closed caption line (live or batch)'}` `[CODE]` `app/webview/sotto_webview.py:15384`. `[INFERENCE]` O `canonicalProducer` deixou de ser um booleano de "há escritor?" desde 2026-11-05; é uma frase, e o painel só testa se é uma string não vazia `[CODE]` `app/panel/panel.js:2094`.

### 11.2 Os dois filtros de origem

O painel tem dois botões, `#history-filter-pc` e `#history-filter-youtube`, no grupo `aria-label="Transcript source"` `[CODE]` `app/panel/panel.html:611`. O estado nasce com os dois ligados `[CODE]` `app/panel/panel.js:287`.

- `viaOf(entry)` lê `entry.via`; `youtube` e `external` contam como o botão do YouTube e tudo o resto é `pc` `[CODE]` `app/panel/panel.js:2466`; `viaVisible(entry)` devolve `viaFilter[viaOf(entry)] !== false` `[CODE]` `app/panel/panel.js:2473`.
- `toggleViaFilter` desliga/liga o botão carregado e, **se desligar o último**, volta a ligar o outro `[CODE]` `app/panel/panel.js:2499`. É a única regra que a UI impõe sozinha: nunca os dois desligados.
- Com um filtro desligado, a cauda é RECONSTRUÍDA (`renderFeed`), e não remendada, porque a linha que pertence ao fim pode ser outra `[CODE]` `app/panel/panel.js:2431`.

### 11.3 A roda e a caixa que rola

O contentor que rola é descoberto, não assumido: `historyScroller()` sobe do `#history-list` até ao primeiro antepassado cujo `overflow-y` seja `auto|scroll|overlay` e cujo conteúdo transborde; o mais próximo fica como recurso `[CODE]` `app/panel/panel.js:1785`.

- **Roda:** um estalido isolado move 1:1; estalidos dentro de 220 ms crescem o passo em 0,75× por estalido, com tecto de 6× `[CODE]` `app/panel/panel.js:1817`. O passo de um evento nunca excede 75 % da altura visível `[CODE]` `app/panel/panel.js:1820`. `deltaMode` é respeitado: linha = 16 px `[CODE]` `app/panel/panel.js:1824`.
- **`preventDefault` só quando a caixa se move**, para o fim do percurso não ser comido `[CODE]` `app/panel/panel.js:1855`.
- **Botão do meio e teclado:** sobre o histórico, o botão do meio transforma o painel numa superfície de arrasto e consome a pressão para o WebView2 não abrir o widget de autoscroll `[CODE]` `app/panel/panel.js:1875`; setas, PageUp/PageDown, Home/End movem a mesma caixa, com `HISTORY_KEY_STEP = 48` `[CODE]` `app/panel/panel.js:1901`.
- **Seguir a novidade:** por omissão segue; o scroll do dono é a única coisa que o pára, e voltar ao fundo (a menos de 48 px) retoma `[CODE]` `app/panel/panel.js:1743`. Depois de uma mudança de tema o fundo é re-fixado, nunca o topo `[CODE]` `app/panel/panel.js:1964`.

### 11.4 O carimbo e a cor

O carimbo mostra só `HH:MM:SS` `[CODE]` `app/panel/panel.js:4118`; o dia viaja no `title` da linha `[CODE]` `app/panel/panel.js:2624`. A regra de cor, que é relacional e não um gosto:

- a cor é `color-mix(in srgb, var(--time-past) 25%, var(--text-primary))` com opacidade `var(--hist-time-opacity, 0.78)` `[CODE]` `app/panel/panel-unified.css:224`;
- a mistura existe porque o `--time-past` de vários temas é branco a 25 %, e aplicar 0,72 por cima disso dava **1,69:1** no pior desenho medido — abaixo de 3:1 `[CODE]` `app/panel/panel-unified.css:207`;
- a base declara 10 px e `--text-faint` `[CODE]` `app/panel/panel.css:957`; a camada de legibilidade sobe para 11,5 px `[CODE]` `app/panel/panel-unified.css:312` e a coluna de 46 px `[CODE]` `app/panel/panel-unified.css:184` passa a 60 px `[CODE]` `app/panel/panel-unified.css:272`, porque `HH:MM:SS` a 11,5 px em IBM Plex Mono não cabe em 46 px `[CODE]` `app/panel/panel-unified.css:266`;
- `tabular-nums` é forçado `[CODE]` `app/panel/panel-unified.css:228`, e as decorações `::before`/`::after` do carimbo são desligadas `[CODE]` `app/panel/panel-unified.css:337`.

## Lacunas

- `[UNKNOWN]` **O corte de 60 dias não existe.** A tarefa pedia "o clip at 60 days"; o código em `HEAD` usa 180 dias/4320 h em três FICHEIROS (`app/webview/sotto_webview.py:835`, `app/panel/panel.js:77`, `app/panel/history-store.js:41`). Fechar: confirmar com o dono se 60 dias é uma decisão nova (que exigiria mudar o código) ou um lapso da tarefa; o `history-store.js` que repete o número não é servido pelo `panel.html` `[CODE]` `app/panel/panel.html:1254`.
- `[UNKNOWN]` **`history/audio/` guarda todo o áudio, não só o não transcrito.** O anel de 12 h é ligado por omissão `[CODE]` `worker/audio_ring.py:114` e recebe cada bloco do tap `[CODE]` `worker/audio_ring.py:189`. O áudio "sem transcrição" vive no `PendingAudio` do worker e na fila de lote. Fechar: ler `docs/` do dono sobre a ordem de 2026-11-11, ou perguntar qual dos dois ele chamou "áudio que ficou sem transcrição".
- `[UNKNOWN]` **O que acontece a uma `Promise` de `historyCall` sem resposta.** `historyCall` não tem prazo (`app/webview/sotto_webview.py:10774`) e não foi possível medir um handler que não responda sem abrir a app. Fechar: um oráculo que injete um handler mudo e observe `window.sotto.history.tail`.
- `[UNKNOWN]` **Se o painel chega a escrever a tecla dos painéis.** `[MEASURED]` 2026-11-11: `grep -rn "hotkey_settings.write\|hotkey_config().write" app/` → sem saída; a chave `panels` existe no ficheiro `[CODE]` `app/webview/hotkey_settings.py:99` e não alimenta o registo. Fechar: procurar no menu da bandeja e no painel um caminho `set-hotkey` que não esteja em `app/` (por exemplo um recurso JS carregado dinamicamente) ou confirmar a ausência com o dono.
- `[MEASURED]` **A reescrita da cauda deixou de poder truncar a hora (D-35, 2026-11-15).**
  `action == 'replace'` e `replace_at` liam o ficheiro inteiro e reescreviam-no com
  `open(path, 'w')`, que TRUNCA o alvo antes do primeiro byte: um crash, um `ENOSPC` ou um kill entre
  o truncate e o flush deixava a hora VAZIA, e `history/` é a única cópia das palavras. Agora os dois
  caminhos passam por `rewrite_lines_atomic` `[CODE]` `app/webview/sotto_webview.py:851`: temp irmão
  com pid e tid no nome, `flush` + `os.fsync`, e só então `os.replace` (com retry breve no
  `PermissionError` do Windows, porque `_history_entries` abre o alvo em cada refrescamento do
  painel). A população medida é 33 ficheiros da hora, 272 746 B, o maior 34 058 B — a reescrita é de
  milissegundos. As quatro arms e os dois mutantes vivem em `_main/history-write-oracle.py`
  (`VERDICT: PASS (10/10)`, `--neg-arm` rc=1). O que continua `[UNKNOWN]`: a FREQUÊNCIA com que uma
  reescrita acontece numa sessão real do dono — o `HISTORY_FUSED` conta as fusões, não as faltas de
  energia, e um crash a meio não se reproduz sem a app na tela dele.
- `[UNKNOWN]` **A poda do anel em MB nunca foi exercitada nesta campanha.** Os 600 MB e a ordem "mais velho primeiro" foram lidos (`worker/audio_ring.py:50` e `worker/audio_ring.py:388`), não observados. Fechar: `python _main/audio-ring-oracle.py` (oráculo do próprio módulo) numa árvore temporária.
- `[UNKNOWN]` **O `summary.json` não tem chamador de produção.** `[MEASURED]` 2026-11-11: `grep -rln "qwen_summary" app/ worker/` devolve só `app/webview/hot_reload.py` (um comentário em `:58`) e `worker/qwen_summary.py` (ele próprio). Fechar: procurar um agendador em `_main/` ou confirmar que é uma ferramenta manual.
