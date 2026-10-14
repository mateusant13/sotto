# RECIBO — AUDITORIA DE TRADE-OFFS · AREA **SHELL**

**Ficheiro:** `app/webview/sotto_webview.py` · **Data:** 2026-10-13 (sessão do subagente SHELL)
**Regra cumprida:** nada foi lançado. Nenhuma instância do shell/worker/app foi aberta. Só
medição estática (bytes, `node`, `git`) e instrumentos **em processo** (`import` do módulo +
chamada directa às funções). `$env:TMPDIR = I:/cc-tmp`. Nada no produto foi editado.

---

## 0. PIN DA REVISÃO MEDIDA (regra 2 de AGENTS.md)

| quê | valor | instrumento |
|---|---|---|
| bytes | **509 411** | `fs.statSync` |
| linhas | **9 881** | split \r?\n |
| CRLF / LF puro | **9 880 / 0** | contagem de \r\n vs \n (a propriedade CRLF do repo MANTÉM-SE) |
| sha256 | **`d89d33c54367dc0970b84369897be20f30708717c7b949797c21789009ee538e`** | `crypto.createHash` sobre os bytes |
| mtime | 2026-10-13 17:53:15 Z | — |
| HEAD | `ee1db85` "P0-1 PROVEN IN PRODUCTION, AND MY OWN COMMENT WAS FALSE" (2026-10-13 14:58:53 -03) | `git log -1` |
| `git status` do ficheiro | **limpo** (nenhuma entrada) | `git status --porcelain -- app/webview/sotto_webview.py` |

**Densidade dos marcadores.** O brief falava em "~27". Medido nesta revisão:
`deliberate` **11**, `on purpose` **14**, `ON PURPOSE` **1**, `intentional` **2**, `by design` **2**
→ **30 linhas**, 0.30 % de 9 881. Não é prova de nada; é a população que auditei.

**Artefacto de log medido:** `_main/webview-run.log` = **16 783 779 B**, **112 528** linhas `sotto:`,
cauda de 13:53:14 → 14:46:04, `LOG_ROTATED from=847 859 845 B kept=16 777 081 B cap=64 MB`.

---

## 1. O ACHADO CENTRAL — AINDA DENTRO DA MINHA AREA E **MEDIDO**

O loop JS↔Python foi fechado hoje em `panel.js:1913` (guarda na mudança real) e
`panel_state.py:78` (temp único + retry). **O brief pede para não repetir esse achado — e eu não
repito.** O que encontro é a metade que NINGUÉM fechou: **a shell não tem guarda alguma.**

### 1.1 `SottoShell.set_panel_surface` — **MELHORAR**

**Linha:** `app/webview/sotto_webview.py:6972` (`def set_panel_surface`), corpo `:6987-7029`.

**O que ela afirma:** "As duas metades são UMA acção de propósito. Mudar o atributo sozinho dá uma
coluna de 380×900 com CSS de strip; redimensionar sozinho dá uma janela de strip com CSS de
painel." (`:6981`)

**O que COMPRA:** coerência garantida entre documento e janela — num único caminho, o par
(`document surface`, `HWND rect`) nunca se dessincroniza. É a razão pela qual a entrada existe, e
é boa.

**O que CUSTA (medido, por aplicação):**

| passo | linha | custo |
|---|---|---|
| `refresh_strip_height` → `strip_height_from_css` | `6998` → `6859` | 1 `exec_js` **bloqueante** |
| `refresh_strip_width` → `strip_width_from_dom` | `6999` → `6908` | 1 `exec_js` **bloqueante** |
| `SottoSurfaces.set(...)` | `7003` | 1 `exec_js` **bloqueante** |
| `_strip_offset_from_page` (lê `localStorage`) | `7014` → `7047` | 1 `exec_js` **bloqueante**, **sem guarda** |
| `_apply_window_geometry` | `7020` | `SetWindowPos` + `log` + `_ui(_fit_client_area)` + `send_geometry` (= outro `exec_js`) |
| `log(PANEL_SURFACE)` | `7022` | 167 B |
| `publish_panel_visibility` | `7028` | 1 `write_atomic` |

**São 5 round trips JS bloqueantes + 1 `SetWindowPos` + 1 `_ui` (BeginInvoke com espera até 10 s,
`:4931`) + 1 escrita com `fsync` + 3 linhas de log (427 B) — por chamada.**

E `refresh_strip_height`/`refresh_strip_width` têm guarda **depois** do round trip
(`:7278` `if value == self.strip_height_css`, `:6949` `if value == self.strip_width_dom`): a
chamada JS é paga sempre, o resultado é descartado sempre.

**Medido na cauda do log:**

- **30 652** aplicações `PANEL_SURFACE`; razões: `strip-float-off` **30 647**, `hotkey` **5**.
  → **6 129 : 1** trabalho repetido vs. transição real.
- 30 649 `WINDOW_GEOMETRY`, 30 652 `panel client area forced`.
- **78,53 %** dos bytes do ficheiro são essas 3 linhas. Com as 17 890 falhas de escrita
  (`PANEL_VISIBILITY_WRITE_FAILED`, 19,62 %) são **98,15 %**. O resto do log — a app inteira,
  worker, captions, tray, autostart — é **1,85 %**.
- Ritmo: **30,7 aplicações/s** na janela 13:53:14→14:09:54 (999,4 s) → 427 B × 30,7/s =
  **13,1 kB/s = 45 MB/h** só destas três linhas.
- `WINDOW_GEOMETRY visible=` : `false` **30 363**, `true` 286 → o loop corria sobretudo com o
  painel **escondido**. `ok=true` em **100 %** das 30 649.

**VEREDICTO: MELHORAR.** A escolha de desenho é a melhor hoje (um caminho, coerente). O que está
errado é que ela é **incondicional**: a shell não pergunta "esta superfície/rect já é o que
tenho?". A guarda existe só do lado do `panel.js`.

**Mudança concreta.** Duas, ambas locais a `set_panel_surface` / `_apply_window_geometry`:

1. Em `set_panel_surface`, depois de `name = normalise_surface_name(surface)`, devolver `False`
   cedo quando `name == self.surface_applied` **e** o rect que `geometry_for(name)` devolve é
   igual ao rect actual (comparar `x/y/width/height`, que é o que `geometry_snapshot` estampa).
   Não escrever document surface, não mexer na janela, não publicar visibilidade, não escrever
   log — excepto uma linha de taxa (ver 3.2).
2. Em `_apply_window_geometry`, chamar `_fit_client_area` só quando a **dimensão** mudou.
   Medido: as 30 649 aplicações do loop tinham `window=380x40` **inalterado** — foram feitas
   30 652 re-fits de cliente para zero mudanças de tamanho. (`edit_drag_to:6402-6404` já tem
   exactamente esta guarda `moved`; copiar a forma.)

**Como se prova que não quebra nada.**

- Novo braço em `_main/strip-geometry-oracle.py` / `_main/panel-exit3-oracle.py`: uma surface
  aplicada DUAS vezes com o mesmo rect → a segunda não pode mexer na janela nem produzir
  `WINDOW_GEOMETRY`/`PANEL_SURFACE`; e uma surface **diferente** (strip↔panel) tem de continuar a
  produzir ambos, porque é aí que a coerência comprada pela escolha é observável.
- `--neg-arm`: remover a guarda numa cópia e confirmar que só o braço da repetição fica RED
  (a repetição volta) e que o braço da mudança real fica GREEN.
- Contra-prova de que a guarda não é vazia: contar `writes` de `PanelVisibilityWriter` numa
  corrida real — com a guarda tem de ser ~5 (`reason=hotkey`), não 30 652.
- `_main/_strip-surface-oracle.py` (que fixa a forma do payload) tem de continuar GREEN: a
  guarda não altera nenhum campo, só a frequência.

---

## 2. O QUE AINDA SE REGISTA DEMASIADO

### 2.1 O tecto do log só vale no ARRANQUE — **MELHORAR**

**Linha:** `_open_log` (`:659-697`) faz a rotação; `_log_writer` (`:713-739`) — o thread que É o
único dono do ficheiro durante a corrida — **nunca mede o tamanho**. Uma leitura de
`:726-732` confirma: o loop é `q.get()` → `fh.write` → `fh.flush()`, sem `tell()`/`fstat`.

**O que COMPRA:** arranque limpo. Um launch nunca herda 808 MB do anterior.

**O que CUSTA (medido):**

- `LOG_ROTATED from=847 859 845 B` = **808,6 MiB**. O tecto de 64 MB foi respeitado no arranque
  e **atravessado 12,6× durante a corrida**.
- Instrumento em processo (`I:/cc-tmp/logcap-probe.py`, módulo importado, nada lançado):
  pré-encho 1,04 MB, `SOTTO_LOG_CAP_MB=1`, chamo `_open_log` → **roda** (bom); depois **20 000**
  chamadas a `log()` pelo caminho real → ficheiro em **3 873 430 B (3,70 MB)** com tecto
  1 048 576 B → **`CAP EXCEEDED DURING THE RUN: true`**.
- Taxa honesta: a sessão que chegou aos 808,6 MiB terminou às 14:09:54 e
  `SHELL_EXIT … statsReplies=14647 meterPushes=145969` dá ~1,46×10⁴ s ≈ **4,05 h**
  (meter a 10 Hz = 14 597 s; replies a 1 Hz = 14 647 s — os dois contadores concordam).
  → **~200 MiB/h**, ou seja **~2,5× a baseline de 81 MB/h** do meu brief, não 36×:
  não sei a hora exacta de arranque (foi rodada fora pelo keep de 16 MB), portanto este número
  é um **limite inferior**.

**VEREDICTO: MELHORAR.** A decisão (guardar a cauda, apagar nada, falhar em silêncio se não
puder rodar) continua correcta. O que falta é o mesmo tecto dentro da corrida.

**Mudança concreta.** Em `_log_writer`, um contador de linhas e, a cada N (N = 1 024), um
`fh.flush(); size = fh.tell()`. Se `size > cap_mb*1024*1024`, escrever a linha
`sotto: LOG_ROTATED …` e truncar pela cabeça com o mesmo algoritmo de `_open_log` (seek a
`size - keep`, cortar na fronteira de linha). O `tell()` sobre um handle em modo `buffering=1`
não é uma syscall. Medido: um loop que escreve 20 000 linhas **com `fh.tell()` em cada linha**
levou 12,46 s em I: (≈0,62 ms/linha, dominado pelo stdout e pelo `print`), ou seja a verificação
não é o custo — e com N = 1 024 é 1 000× mais rara.

**Como se prova.** `_main/log-rotation-oracle.py` **já** importa o módulo e chama o
`_open_log` real, em processo, sem lançar nada. Acrescentar-lhe um braço: escrever N linhas por
`log()` e afirmar `os.path.getsize(TMP) <= cap + keep`. `--neg-arm`: retirar a verificação do
`_log_writer` numa cópia → o braço tem de ficar RED. O braço existente (rotação no arranque)
tem de ficar GREEN nos dois.

> **NÃO MEDIDO, e é a fronteira desta auditoria:** se a taxa de ~200 MiB/h ainda se verifica
> **depois** dos três commits de hoje (`panel.js a4aa779` 14:55:32, `sotto_webview.py`
> `b3fa5f0`/`68e9fa4`/`ee1db85` 14:51→14:58). O último launch dentro do log é **14:45:50**,
> **anterior** à guarda do `panel.js`. Medir exige correr a app — proibido. Escrevo que não
> consegui medir.

### 2.2 `_set_strip_offset`: a linha de log por movimento — **MELHORAR**

**Linha:** `:7138-7139` `log(f'STRIP_DRAG phase={phase} offset=… ')`, dentro de
`_set_strip_offset` (`:7073`).

**O que COMPRA:** um rasto de cada movimento do arrasto da strip.

**O que CUSTA (medido):** o commit `b3fa5f0` ("P0-4 SECOND FIX: `exec_js` was a synchronous round
trip on EVERY move -- now ONCE per drag") corrigiu o round trip (`:7131-7133`, enviado só no
primeiro movimento) mas **deixou a linha de log em cada movimento**. Na cauda do log
`STRIP_DRAG` = **277 linhas**; o próprio comentário de `:7120-7124` mede **277 movimentos em
1,86 s ≈ 149/s**. São 277 × 82 B ≈ 22,7 kB por arrasto — uma correcção a meio.

`edit_drag_to` (`:6379-6423`), o caminho gémeo, faz tudo bem: guarda `moved` (`:6402`), zero
`exec_js` no loop, re-fit **posted** (`:6418`), e **uma** linha de log no `end` (`:6420`).

**VEREDICTO: MELHORAR.** Registar `phase=end` (com `moves=`) e, quando muito, `phase=start`.
Nunca `phase=move`: 149 linhas por segundo para dizer que a janela se mexeu é o padrão exacto
que o brief pede para caçar. Acrescentar a mesma guarda `moved` de `edit_drag_to` antes do
`SetWindowPos`.

**Como se prova.** `_main/strip-drag-shell-oracle.py` existe e cobre o caminho. Braço novo:
um arrasto sintético (o mesmo que o commit `b3fa5f0` usou) → nº de linhas `STRIP_DRAG` == 2
(start/end), e `SetWindowPos` chamado só quando x/y mudou. `--neg-arm` (log por movimento
restaurado) → RED.

---

## 3. AS ESCRITAS: A CAUSA RAIZ MEDIDA (e não é a que o comentário diz)

### 3.1 `panel_state.write_atomic` — a colisão era **interna** — **MELHORAR (desenho)**

**O que o código afirma** (`app/webview/panel_state.py:78`, hoje): *"TWO writers touch this file
-- the shell's periodic writer and the worker"*. Ou seja: a colisão é atribuída ao worker.

**O que está MEDIDO.** Antes de hoje (`git show 1b21cf8:app/webview/panel_state.py:78`) o nome
temporário era **fixo**: `tmp = path + '.tmp'`. E `_main/panel-visibility.json` tem **dois
escritores dentro do MESMO processo**: o thread do `PanelVisibilityWriter` (`:3499-3505`,
cadência 3,0 s) e o caminho síncrono `publish_panel_visibility` (`:5213`), chamado de
`set_panel_surface`, `show_panel`, `hide_panel`, `edit_drag_to`, `_set_strip_offset`.

**Instrumento em processo** (`I:/cc-tmp/wa-sim.py`, nada lançado), 80 escritas, escritor
"fixed-tmp" vs o `write_atomic` actual:

| braço | escritores | leitor 10 Hz | escritas | falhas | taxa |
|---|---|---|---|---|---|
| `OLD fixed-tmp` | 1 | sim | 40 | 0 | 0,0 % |
| `NEW unique-tmp` | 1 | sim | 40 | 0 | 0,0 % |
| **`OLD fixed-tmp`** | **2** | **sim** | 80 | **79** | **98,8 %** |
| **`NEW unique-tmp`** | **2** | **sim** | 80 | 0 | 0,0 % |
| `OLD fixed-tmp` | 2 | **não** | 80 | **79** | **98,8 %** |
| `NEW unique-tmp` | 2 | não | 80 | 0 | 0,0 % |

→ **A falha reproduz-se sem nenhum leitor.** A causa é o nome temporário fixo entre os dois
escritores da própria shell. O worker não é necessário para a reproduzir.

**Consequência funcional, medida.** 17 890 falhas em 30 652 tentativas = **58,4 %**. E
`WINDOW_GEOMETRY visible=false` em 30 363 de 30 649 aplicações: com o painel **escondido**,
**58 % dos "estou escondido" perderam-se**. `ReduxHiddenSwitch`
(`worker/sotto_worker.py:3404`) falha **fechado para o streaming** quando o ficheiro está
velho/ilegível (`:3374`, `:3428-3430`) — ou seja: a LEI DA STACK do dono ("o ao vivo só
acontece quando o painel tá aberto") assenta num canal que, na era do loop, falhava mais de
metade das vezes. Isto não é um detalhe de desempenho; é uma funcionalidade que não disparava.

**E o NOVO risco que o retry introduz.** `write_atomic` (`:93-99`) tenta 6 vezes com
`time.sleep(0.02*(attempt+1))` = 0,02+0,04+0,06+0,08+0,10+0,12 = **0,32 s de sono**. Medido,
com o alvo aberto por outro processo: **482,3 ms** por escrita falhada. Ao ritmo do loop
(30,7 aplicações/s), se a guarda do `panel.js` fosse a única coisa entre a app e o loop, seriam
**14,8 s de sono por segundo**. O retry é correcto para a cadência de 3 s (1 200 escritas/h) e
**errado para o caminho de transição**, que é o caminho quente. **A nova correcção é um
amplificador de 15× de um acidente já medido.**

Verificado por leitura de `webview/util.py:335-336`: o pywebview corre cada chamada js_api num
**thread novo** (*"executed in a separate thread to prevent blocking the UI thread"*). Portanto
o sono de 0,32 s não bloqueia a UI directamente — mas a ~31 mensagens/s cria ~31 threads/s e
~155 `BeginInvoke` enfileirados/s.

**VEREDICTO: MELHORAR (desenho, não a mudança de hoje).** Dois passos, um feito e um aberto:

1. **FEITO hoje** (`68e9fa4`): temp único + retry. Provado acima: 98,8 % → 0 %.
2. **ABERTO:** um ficheiro, **um** escritor. A cadência do `PanelVisibilityWriter` já é um
   thread; `publish_panel_visibility` deve **colocar** a transição nesse thread (fila) em vez de
   escrever a partir do chamador. Ganha três coisas de uma vez: (a) zero colisão por
   construção; (b) **ordenação total** — com dois escritores, um `poll` que lê a janela a
   meio de uma transição pode cair *depois* da escrita da transição e sobrescrevê-la com um
   `visible` velho (*lost update*). Janela medível: escrita ≈ 5–9 ms contra cadência de 3 s →
   ~0,3 % por transição. **NÃO MEDIDO se alguma inversão aconteceu realmente** (não posso
   lançar); reporto a forma, não um caso; (c) o caminho quente deixa de conter o retry de
   0,32 s no thread do chamador.

**Como se prova.** `_main/panel-visibility-guard-oracle.py` já conduz os métodos reais com um
`self` falso, em processo. Braço novo: duas escritas quase simultâneas (transição + cadência)
com o mesmo `visible` → o ficheiro final tem de reflectir a **última por ordem de chegada**, não
uma ordem de thread; e o nº de escritas tem de ser exactamente o pedido. `--neg-arm` com os dois
escritores restaurados → RED. E um braço que afirme `writer.writes == número de
publish_panel_visibility + cadência`, para pegar a duplicação.

---

## 4. O MECANISMO DO FREEZE — UM CANDIDATO MEDIDO, OUTRO EXCLUÍDO

Isto interessa ao Lead porque orienta a próxima medição.

**EXCLUÍDO por medição (não por palpite):** em 112 528 linhas, `UI_THREAD_STALL` = **0**,
`exec_js TIMEOUT` = **0**, `POSTED_CALLABLE_FAILED` = **0**, `BRIDGE_METER_CALLBACK_FAILED` = **0**,
`emit_async failed` = **0**. O thread da UI **não** ficou parado pela métrica da própria shell.
Um candidato popular ao freeze ("a fila do WinForms afogou") não é apoiado por este artefacto.

**CONFIRMADO:** 30,7 `write_atomic`/s × média **9,363 ms** em H: (ver 5) = **290 ms de `fsync`
por segundo**, 58 % dela desperdiçada antes do `os.replace`; mais 45 MB/h de linhas de log de
três tokens; mais ~155 `ExecuteScriptAsync` enfileirados/s.

Custo de `write_atomic` nesta caixa, medido em processo sobre **H:** (40 escritas, temp único,
sem contenção): **p50 = 5,008 ms, média = 9,363 ms, p99 = 26,855 ms, máx = 26,855 ms** — o que
confirma o "8,42 ms/escrita" do comentário em vez de o repetir sem prova. Com um leitor a 20 Hz
(como o `switch.tick()` do worker, uma leitura por bloco de áudio, `sotto_worker.py:5288`):
média **60,6 ms, máx 181,0 ms** (6,5×), com `read_errors = 0` — o `os.replace` continua atómico,
logo não há ficheiro rasgado; o custo é de débito, não de correcção.

---

## 5. OS DELIBERATE QUE AUDITEI E QUE CONTINUAM A SER A MELHOR ESCOLHA

| # | linha | trade-off | o que COMPRA | o que CUSTA | VEREDICTO |
|---|---|---|---|---|---|
| 1 | `:3598-3607` | `SottoHost._shell` é **privado de propósito** ("pywebview walks every public attribute of the js_api") | evita a recursão ao objeto .NET medida como `maximum recursion depth exceeded` | nada — é a forma mais barata possível | **MANTER** — verificado por leitura de `webview/util.py:190-206`: `if name.startswith('_'): continue` (`:193-194`) **salta o atributo antes de o ler**. A prova não é o comentário, é a linha do pywebview |
| 2 | `:4119`, `:4200-4209`, `:9613` | transparência por omissão (`--opaque` desliga) + `WEBVIEW2_WINDOW_TO_VISUAL_DEFAULT = False` | overlay que flutua sobre o ecrã; `windowed` compõe **ESCURO** nesta caixa (medido, no próprio comentário de `:9633-9635`) | o `Show()` do pywebview em cada navegação (`edgechromium.py:348`) desfaz o `hidden=True` — fechado por `_gate_form_show` (`:4402`, chamado de `:4243`), 0/20 launches | **MANTER** — a decisão medida é a melhor hoje. Nota de manutenção: `transparency_hack` (`:1230-1310`) re-implementa uma chamada interna do pywebview (`edgechromium.py:348`) e tem de ser revista sempre que o pywebview muda |
| 3 | `:1425-1450` + `:1323` + `SW_SHOWNOACTIVATE` | não roubar foco; foco só no Alt+C do dono | a app nunca tira o cursor de onde o dono está a escrever | o caminho do Alt+C precisa de `foreground_unlock` (restore+show+SetForegroundWindow) — que é exactamente a excepção declarada | **MANTER** |
| 4 | `:1943-1969` | `CreateMutexW` falhar ⇒ **prosseguir** ("refusing to start because a lock could not be created would be worse than a rare double shell") | a app arranca sempre | uma shell dupla rara com hotkey morto | **MANTER** — assimétrico de propósito e do lado certo |
| 5 | `:1933-1936`, `:1989-2002` | nome derivado para medições, nunca o nome da app; lock **sempre** tomado | probes não são recusados pela app do dono (o que "brickou" o conjunto de instrumentos em 2026-10-07) e dois probes idênticos não empilham workers | mais nomes de mutex | **MANTER** |
| 6 | `:1838-1913`, `:2391-2621`, `:2084-2273` | hotkey / tray / click-watcher: **thread + GetMessageW, sem poll nem timer** | cada um é um laço de eventos; nada consome CPU parado | 3 threads e 1 janela message-only | **MANTER** — e é o **modelo** que `_apply_window_geometry` e `_set_strip_offset` deviam seguir |
| 7 | `:5179-5206`, `:312` | `PanelVisibilityWriter`: cadência 3,0 s + `geometry` aditiva no **mesmo** ficheiro | bate o coração de frescura que o worker usa (`staleAfterSeconds` = 9,0); evita um 2º ficheiro autoritativo | medido: p50 5,0 ms / média 9,4 ms por escrita em H:, 1 200/h = ~7,2 s/h | **MANTER** a cadência (é o que faz a detecção de fracção funcionar). **MELHORAR** o número de escritores — ver 3.1 |
| 8 | `:278` | `PANEL_STATE_INTERVAL_S = 2.0` | o painel como texto, sempre fresco | p50 9,4 ms em H:, 1 800/h | **MANTER** |
| 9 | `:559` | `SHELL_SHA256_AT_IMPORT = file_sha256(SHELL_PATH)` no import | o `code_state_log` sabe que código está a correr | **medido: 1 ms** para 509 411 B | **MANTER** — negligenciável, e agora com número em vez de impressão |
| 10 | `:7292` chamado de `:6166` | `code_state_log` calcula o sha dos dois ficheiros **por arranque de worker** | detecta shell/worker velhos | 509 KB + 291 KB de leitura ≈ 2 × 1 ms por restart | **MANTER** |
| 11 | `:3656-3706` | a tabela de despacho guarda **nomes**, não valores | uma entrada má custa só o seu `kind` | um `getattr` por mensagem | **MANTER** — o relato da entrada que matou todos os tipos é a razão |
| 12 | `:6505-6579`, `:6580-6590`, `:6614-6627`, `:6649-6729` | `stats()` uma forma para pull e push; log com orçamento (`STATS_LOG_INTERVAL_S`/`METER_LOG_INTERVAL_S` = 30 s); `emit_async` com **um** pendente por canal | o painel não pode receber duas imagens de uma medição; a fila do WinForms não cresce com o feed | `stats()` corre por amostra de meter (10 Hz) mesmo quando a página não consegue drenar | **MANTER** — os quatro relatos de "isto já foi um flood" têm números, e o oráculo `_main/emit-queue-bound-oracle.py` sabe dizer NÃO |
| 13 | `:824-842` | `wait_ready_file` faz poll a 0,1 s **limitado** | o wrapper detecta um hang | nenhum (um modo, uma vez) | **MANTER** |
| 14 | `:9239-9390` | `--check-args` / `--ready-file` / `--mutex-name` com `argparse.SUPPRESS` | o `--help` do `run.cmd` é byte-a-byte o de antes; a validação é do parser da shell, sem 2ª tabela | flags invisíveis | **MANTER** |
| 15 | `:674` | "swallowed on purpose -- a log that cannot be rotated must never stop the app" | arranque garantido | uma rotação falhada é silenciosa | **MANTER** |
| 16 | `:426`, `:8789` | `open-failed` / veredictos de erro excluídos de conjuntos "saudáveis" | a cor da morte do worker não é neutralizada | nenhum | **MANTER** |
| 17 | `:4649-4690` | o bounce por `stage.html`, decidido pelo **documento** e não por uma flag | um load reentrante converge para o painel em vez de depender de uma flag | uma navegação extra no arranque | **MANTER** — a razão medida (título `stage.html` e strip 100 % branca) sustenta-a |

---

## 6. RESUMO DE VEREDICTOS

| ficheiro:linha | veredicto | prioridade |
|---|---|---|
| `sotto_webview.py:6972` `set_panel_surface` sem guarda de idempotência | **MELHORAR** | **P0** — 81,7 % das linhas e 78,5 % dos bytes do log |
| `sotto_webview.py:7138` `STRIP_DRAG` por movimento (P0-4 feito a meio) | **MELHORAR** | **P0** |
| `sotto_webview.py:7140-7179` `_fit_client_area` sem guarda de dimensão | **MELHORAR** | P1 |
| `sotto_webview.py:713-739` tecto do log só no arranque | **MELHORAR** | **P0** |
| `sotto_webview.py:5213` 2º escritor síncrono de `panel-visibility.json` | **MELHORAR** | P1 (custo de 0,32 s de retry no caminho quente) |
| `sotto_webview.py:7030-7058` `_strip_offset_from_page` sem cache | **MELHORAR** | P2 (round trip por chamada, resultado igual) |
| os 17 deliberate auditados | **MANTER** | — |

### O que eu **não** consegui medir (e vale mais escrever do que adivinhar)

1. **Se o loop morreu.** Os três commits de hoje são posteriores ao último launch registado
   (14:45:50). Confirmar exige correr a app — proibido por ordem do dono. A guarda está só do
   lado do `panel.js`; a shell, medida agora, continua sem guarda.
2. **Se alguma inversão de escrita aconteceu** com os dois escritores de
   `panel-visibility.json`. A janela é ~0,3 % por transição; não observei nenhum caso.
3. **Qualquer coisa que precise do shell a correr**: o censo de flash a 25 ms nesta revisão, o
   `paint` real, o multi-monitor (`work_area` assume primário, e o próprio código declara-o não
   medido), e a profundidade real da fila do WinForms.
4. **O caminho de freeze completo.** Excluí a paragem da UI por medição; o que fica medido é
   disco + volume de log + threads. A atribuição final continua em aberto, como já estava.

---

## APÊNDICE — instrumentos que usei (todos em processo, nenhum lança a app)

| instrumento | onde | o que mede |
|---|---|---|
| `wa-bench.py` / `wa-bench2.py` | I:/cc-tmp (apagados) | custo de `write_atomic` em H: e I:, e sob leitor concorrente |
| `wa-sim.py` | I:/cc-tmp | fixed-tmp vs unique-tmp com 1 e 2 escritores, com e sem leitor |
| `logcap-probe.py` | I:/cc-tmp (apagado) | importa o shell real, chama `_open_log` + 20 000 `log()`, prova a ausência de tecto em corrida |
| `node` sobre os bytes | — | pin (bytes/linhas/CRLF/sha256) e censo do log |
| `git show 1b21cf8:…` | — | o nome temporário fixo antes da correcção de hoje |
| leitura de `webview/util.py:190-206`, `:335-336`, `edgechromium.py:102-104`, `:346-349` | site-packageswebview | por que `_shell` privado funciona, em que thread corre a js_api, e qual é a chamada `Show()` |
| leitura de `worker/sotto_worker.py:3326-3383`, `:3404-3430`, `:5288-5290` | — | o que o worker faz com o ficheiro, e a que cadência o lê |

Nenhum destes escreveu no produto. Os ficheiros de scratch de H: foram removidos e verificados
(`product-tree scratch leftovers: NONE`).


---

# ADENDA DE REVISÃO — O FICHEIRO MOVEU-SE ENQUANTO EU AUDITAVA (regra 2 de AGENTS.md)

**Medido no fim desta sessão, não no início.** `app/webview/sotto_webview.py`:

| | pin que usei durante toda a auditoria | pin no fim (agora) |
|---|---|---|
| bytes | 509 411 | **509 957** |
| linhas | 9 881 | **9 889** |
| mtime | 2026-10-13 17:53:15 Z | **2026-10-13 17:58:31 Z** |
| sha256 | `d89d33c54367dc09…` | **`9be0dfac9c3a32718b9e21f93862c7ec7376dade22febbfac85b54887e397de0`** |

A diferença são **+8 linhas / +546 bytes**, TODAS dentro de `_open_log` (`:659-705`): o Lead
corrigiu o comentário que afirmava que o resto do log era *"moved aside to <log>.1 rather than
discarded"* — agora diz a verdade (a cauda é escrita em `<log>.1` e depois `os.replace`d por cima
do log, **o conteúdo antigo desaparece**), e cita o mesmo número que eu medi:
`LOG_ROTATED from=847859845 B kept=16777081 B cap=64 MB`.

**Isto muda uma coisa no meu recibo e confirma outra:**

- **Confirma §2.1.** O comentário novo agora afirma, correctamente, *"THE OLD content is gone"* —
  ou seja, a rotação de 64 MB é um acontecimento **de arranque**, e uma corrida longa volta a
  crescer sem tecto. `_log_writer` (`:721-747`, lido agora) continua sem `tell()`/`fstat`
  (`:734-740` é `q.get()` → `fh.write` → `fh.flush()`). A recomendação mantém-se, não aplicada.
- **Confirma §2.2.** `log(f'STRIP_DRAG phase=…')` continua **em cada movimento**, agora em
  `:7146`, e `_strip_moved_sent` (`:7139-7143`) continua a proteger só o `exec_js`. A
  correcção a meio mantém-se.
- **Confirma §3.1.** Continua a haver dois escritores de `panel-visibility.json`
  (`PanelVisibilityWriter._loop` `:3507` e `publish_panel_visibility` `:5213`) e o retry
  continua em `panel_state.py:93-99`.

**Re-verifiquei TODAS as âncoras que cito contra a revisão de 9 889 linhas.** A tabela abaixo
substitui as linhas onde a numeração mudou. O que não está nesta tabela, verifiquei que é igual
nas duas revisões.

| o que cito | linha NOVA | linha que eu escrevi no corpo |
|---|---|---|
| `_log_writer` (sem tecto em corrida) | **721** | 713 |
| `set_panel_surface` | **6980** | 6980 ✓ |
| `PANEL_SURFACE` log | **7030** | 7022 |
| `refresh_strip_height` na surface | **7006** | 6998 |
| `refresh_strip_width` na surface | **7007** | 6999 |
| `_strip_offset_from_page()` na surface | **7022** | 7014 |
| def `_strip_offset_from_page` | **7038** | 7030 |
| `_apply_window_geometry` na surface | **7028** | 7020 |
| `publish_panel_visibility` na surface | **7036** | 7028 |
| def `_apply_window_geometry` | **7148** | 7140 |
| `WINDOW_GEOMETRY` log | **7169** | 7161 |
| def `_fit_client_area` | **4307** | 4299 |
| `client area forced` log | **4327** | 4319 |
| `_fit_client_area` no `_apply_window_geometry` | **7183** | 7175 |
| `send_geometry()` no `_apply_window_geometry` | **7186** | 7178 |
| `_set_strip_offset` | **7081** | 7073 |
| `_strip_moved_sent` (uma vez por arrasto) | **7139-7143** | 7131-7135 |
| `STRIP_DRAG` log por movimento | **7146** | 7138 |
| def `edit_drag_to` | 6379 | 6379 ✓ |
| guarda `moved` do `edit_drag_to` | 6402 | 6402 ✓ |
| `_post(_fit_client_area)` do `edit_drag_to` | 6418 | 6418 ✓ |
| `PANEL_EDIT_GEOMETRY_SAVED` | 6420 | 6420 ✓ |
| def `publish_panel_visibility` | 5213 | 5213 ✓ |
| `PanelVisibilityWriter._loop` | **3507** | 3499 |
| `PanelVisibilityWriter.write` | **3516** | 3508 |
| chamada `panel_state.write_atomic` | **3565** | 3557 |
| rate-limit `errors % 500` | **3576** | 3568 |
| `SottoHost._shell` privado | **3615** | 3607 |
| "THE TABLE HOLDS NAMES" | **3641** | 3633 |
| `_SINGLE_INSTANCE` / `def take_single_instance_lock` | **1944 / 1951** | 1936 / 1943 |
| `transparency_hack` | 1230 | 1230 ✓ |
| `foreground_unlock` | 1425 | 1425 ✓ |
| `_gate_form_show` def / chamada | **4410 / 4251** | 4402 / 4243 |
| `transparent=not self.args.opaque` | **4127** | 4119 |
| `reason=--opaque` | **4213** | 4205 |
| `SHELL_SHA256_AT_IMPORT` | 559 | 559 ✓ |
| `code_state_log` def / chamada | 7292 / 6166 | 7292 / 6166 ✓ |
| `stats` / `reply_stats` / `_stats_log_maybe` / `emit_async` | **6513 / 6588 / 6622 / 6657** | 6505 / 6580 / 6614 / 6649 |
| `STATS_LOG_INTERVAL_S` / `METER_LOG_INTERVAL_S` | **979 / 993** | 971 / 985 |
| `swallowed on purpose` | **682** | 674 |
| `PANEL_STATE_INTERVAL_S = 2.0` / `PANEL_VISIBILITY_INTERVAL_S = 3.0` | 278 / 312 | ✓ |
| `wait_ready_file` / `parse_args` / bounce por documento | 832 / 9239 / 4649 | ✓ |

**O Lead deve aplicar as correcções contra esta coluna NOVA, não contra as do corpo.** Nenhum
veredicto mudou: os sete `MELHORAR` continuam por aplicar, e os 17 `MANTER` continuam
correctos — os verifiquei um a um na revisão nova.
