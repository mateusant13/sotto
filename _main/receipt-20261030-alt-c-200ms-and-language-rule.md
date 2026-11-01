# Recibo — 2026-10-30 — a regra da língua (en/pt/es nunca traduzem) e o Alt+C a 200 ms

**As ordens, verbatim.**

1. *"regra nunca que pode ser quebrada: legendas nao traduzem entre ingles pt br e espanhol.
   só outras linguas, todas pro ingles."*
2. *"a porra do alt c, bota 200ms."*
3. *"tu vai achar essa sessao que estamos, procurar tudo que eu falei sobre o alt c nas
   ultimas 24 horas, e implementar."*

---

## 1. A REGRA DA LÍNGUA

### O que está no código

`app/webview/youtube_captions.py`:

| símbolo | valor / comportamento |
|---|---|
| `TARGET_LANG` | `'en'` — o único destino de tradução que existe |
| `UNTRANSLATED_LANGS` | `('en', 'pt', 'es')` — nenhuma destas é traduzida em direcção nenhuma |
| `_target_langs(orig)` | devolve **um** elemento para as três (`(base,)`, sem fallback) e `('en', orig)` para todas as outras |

Um `(orig, 'en')` para um vídeo espanhol era **a política de 2026-10-21** e é exactamente o
que a ordem de hoje proíbe — por isso a lista tem um elemento só. Um vídeo espanhol sem
faixa espanhola **não serve legenda nenhuma** (a transcrição ao vivo do próprio áudio fica a
resposta); não recebe a inglesa nem a portuguesa.

### O BURACO QUE ESTAVA ABERTO: o menu de tradução

`TARGET_OVERRIDE` (o selector do menu de 3 pontos, pedido do dono em 2026-10-21, quando a
política **permitia** traduzir entre as três) passava à frente da política. Com a regra a ser
absoluta, esse caminho era o único sítio onde ela ainda podia ser quebrada à mão — por
exemplo: escolher `pt` num vídeo chinês (tradução para português, proibida) ou `en` num
vídeo português (tradução entre as três, proibida).

**Fechado em `_target_langs`**: a escolha continua a ser registada (`TRANSLATION_TARGET` no
log), mas o resultado é sempre o da regra. O menu continua a funcionar; o que não faz é
transportar a tradução proibida para o ecrã.

### Medido

```
python _main/youtube-captions-oracle.py            -> VERDICT: PASS  arms 62/62  mutants 16/16
python _main/youtube-captions-oracle.py --neg-arm  -> NEG-ARM PASS  mutants 16/16  (rc=1 por desenho)
```

Braços que medem a regra (não comentários):

```
a48  um video em PORTUGUES serve a legenda em PORTUGUES, nunca em ingles
a54  um video ESPANHOL sem faixa em espanhol NAO e' traduzido (nem para ingles nem para pt)
a55  um video ESPANHOL sem faixa nenhuma da None (nunca a de portugues)
a56  um video PORTUGUES com so' faixa INGLESA nao serve nada (PT->EN e' proibida)
a57  um video INGLES com so' faixa PORTUGUESA nao serve nada (EN->PT e' proibida)
a58  EN, PT e ES nunca se traduzem ENTRE SI (varrendo as tres)
a59  uma escolha no menu NAO quebra a regra (3 origens x 4 escolhas)          <- NOVO
a60  qualquer outra lingua vai SEMPRE para INGLES, escolha ou nao            <- NOVO
```

Mutantes que provam que os braços têm dentes — os dois novos e os dois que já existiam para
os conjuntos:

```
the-untouched-set-loses-portuguese   caught by a48, a56, a58
the-untouched-set-loses-spanish      caught by a47, a54, a58
the-explicit-pick-wins-over-the-rule caught by a59, a60                      <- NOVO
```

`a59`/`a60` só viraram gate porque o mutante `the-explicit-pick-wins-over-the-rule` volta a
pôr a escolha à frente da regra e os dois ficam vermelhos. Um braço que nenhum mutante
derruba não mede nada.

### Docs

`docs/politica-youtube.md` ganhou a secção **A REGRA ABSOLUTA**, com a tabela das três
línguas, o mecanismo do `clamp` e os números do portão. O texto de 2026-10-21 (espanhol →
`es,en`) ficou marcado como substituído — a regra antiga é a que hoje é proibida, e deixá-la
legível sem marca era a segunda verdade que este repo já pagou caro.

---

## 2. O ALT+C A 200 ms

`app/webview/hotkey_gesture.HOTKEY_HOLD_MS = 200.0`, e o número está em **três** sítios que
concordam, medidos:

| sítio | valor medido |
|---|---|
| `hotkey_gesture.HOTKEY_HOLD_MS` (fábrica) | `200.0` |
| `hotkey_settings.HOTKEY_HOLD_MS_CHOICES` (o que o painel da direita oferece) | `(200, 300, 400, 500, 700, 900, 1200)` |
| `_main/hotkey-settings.json` (o ficheiro vivo) | `{"holdMs": 200}` |

**O risco está escrito, não escondido** (no docstring de `hotkey_gesture.py` e em
`docs/hotkey-gestos.md`): com 200 ms, as pressões de **204, 438 e 468 ms** lidas do log dele
caem em HOLD — um toque acima de ~0,2 s comuta a legenda em vez de mostrar o painel. Foi ele
que escolheu o número; a lista do dropdown mantém 300/400/500/700/900/1200 para voltar atrás
num clique.

---

## 3. TUDO O QUE ELE DISSE DO ALT+C NAS ÚLTIMAS 24 H, E ONDE ESTÁ

Fonte: `archive.search("alt c")` / `("alt+c")` sobre todos os projectos, filtrado a
`H:\sotto` e às últimas 24 h — **11 prompts**, sessão `01a185b5-fb64`. Re-corrido a
2026-10-30 12:0x, a mesma janela: **14 hits em todos os projectos, 12 nas últimas 24 h,
11 deles em `H:\sotto`** (o 12.º é outra app). A primeira passagem deste recibo tinha
publicado 12 linhas e deixado **três** de fora (`07:29:54`, `07:30:24`, `09:33:47`, as
linhas 13-15); estão aqui agora, cada uma com o instrumento que a mede — *"o grep deu
ZERO" e uma afirmação com prazo de validade: re-corre-se antes de repetir*. Cada linha traz o
instrumento que a mede hoje.

| # | o que ele disse (verbatim) | onde está | medido por |
|---|---|---|---|
| 1 | *"1 tap = painel de baixo, 2 taps = painel da direita"* (`05:10`) | `hotkey_gesture.resolve_taps` + `SottoShell._hotkey_resolve` | `altc-gesture` arm "1 toque -> strip" / "2 toques -> side" |
| 2 | *"faz uma config disso pra eu escolher os milisegundos, no painel da direita"* (`05:10`) | `hotkey_settings.py` + `#hotkey-hold-select` em `panel.html`/`panel.js` | `altc-gesture` arms "o valor de fábrica está na lista que o painel oferece" e "pedir exactamente esse valor não é aproximado para outro" |
| 3 | *"a legenda ao vivo desativada, é pra desativar apenas o display. o historico ainda escuta, o modelo ainda funciona"* (`05:10`) | `hotkey_hold` → `_set_live_enabled` só | `altc-gesture` arms "_set_live_enabled NÃO nomeia worker / history" |
| 4 | *"POR QUE APERTAR ALT C DE NOVO NAO FECHA O PAINEL ATUAL?"* (`07:38`) | `_hotkey_resolve`: mesmo painel no ecrã → `hide_panel('hotkey-toggle')` | arm "toque com a faixa no ecrã -> `hide_panel('hotkey-toggle')`" |
| 5 | *"assim que o alt c é segurado suficiente, da display ou tira display da legenda. nao é pra esperar o release"* (`07:39`) | `HotkeyThread._tick` entrega ao cruzar o limiar (`HOTKEY_HOLD_FIRED`) | arm "o log prova que a tecla estava em baixo no disparo" |
| 6 | *"tem um delay DO CARALHO pra aparecer os painels"* (`07:42`) | o 1.º toque mostra no instante; a janela de 400 ms só PROMOVE | arm "o primeiro toque mostra o painel SEM esperar a janela" |
| 7 | *"apertar alt c e nao deixar alt c ir embora (manter apertado) deve mexer normalmente nos comandos"* (`07:43`) | `_on_press`/`_tick` sem `while`/`for` (pump devolve em microssegundos) | arms "_on_press/_tick não têm While nem For" |
| 8 | *"EU TO APERTANDO ALT C E TA LIGANDO E DESLIGANDO A LEGENDA"* (`07:29`) | o limiar saiu de 500 ms; hoje 200 ms **por ordem dele** | arm "2000 ms fechados por new-press -> TOQUE"; ver §2 para o risco aceite |
| 9 | *"varias implementacoes diferentes e tao conflitando entre si?"* (`07:08`) | um só número: `hotkey_gesture`; o shell lê por `hotkey_numbers()` | arms "o shell lê os números por hotkey_numbers() e não os redefine" / "o shell NÃO tem uma segunda cópia" |
| 10 | *"desliga o nemotron por carga… desliga parakeet também se a carga for muito alta"* (`05:10`) | `load_shedding` | passo `load-shedding` da bateria (26 arms) |
| 11 | *"essse AUTO CLICKER TA ESQUISITO… EM OUTROS APPS O SHIFT C NAO FUNCIONA"* (`09:40`) | fora do Sotto (o AutoClicker dele); o "acesso negado" é o `launch-as-token` | passo `launch-as-token --selftest` + `red-as-expected-launch-as-token` |
| 12 | *"meu autoclicker (op auto clicker 4.1) parou de funcionar … nao clica em nada fora da janela dele"* (`07:10`) | já medido em `_main/receipt-20261030-altc-acesso-clicker-fone.md` §3: a hipótese de integridade está **refutada** (o clique corre `high`, `S-1-16-12288`) e o binário usa `SendInput`/`mouse_event`, que são injecção global | `python _main/input-path-oracle.py` → **PASS: nenhum hook global existe** (inclui o mutante "aparece um segundo hook, o do teclado"); a parte do overlay comer o clique fica **por medir** — censo de hoje (6 `pythonw`, 3 janelas, 0 do Sotto visíveis) não tem janela para medir sem a pôr no ecrã dele |
| 13 | *"ME FALA QUE PORRA DE MECANISMO TA FALTANDO PRA TU CONSERTAR OQ EU FALO?"* (`07:29:54`) | resposta medida, nunca uma desculpa: faltava (a) a **duração** do gesto -- sem `GetAsyncKeyState` só existia o instante da pressão; (b) o **canal** para a acção sair da thread do hotkey; (c) um **rasto** (`HOTKEY_PRESSED`/`RELEASED`/`HOLD_FIRED`) para a mão dele ser lida em vez de adivinhada | `altc-gesture` arms da fronteira, do disparo no tick e do `show_caption_window`; o log vivo com `held_ms` |
| 14 | *"O QUE TA FALTANDO PRA TU ENTENDER 100% DA IMPLEMENTACAO E FAZER ELA? DESCOBRE POR QUE TU FALHOU NESSA PORRA E ME SUGERE ALGO PRA TU NUNCA MAIS FAZER MERDA"* (`07:30:24`) | o mecanismo é o **oráculo que executa o código vivo** (`altc-gesture`, 90 arms, extrai `_set_live_enabled` e `_on_press`/`_tick` do ficheiro) mais o **pin de um sítio só** (`hotkey_gesture`), nascido de ele ter dito *"varias implementacoes diferentes e tao conflitando"* | `python _main/altc-gesture-oracle.py` -> 90/90; braços "o shell lê os números por `hotkey_numbers()`" e "o shell NÃO tem uma segunda cópia" |
| 15 | *"faz full audit. tu vai me explicar exatamente a logica inteira, sem sobrar nada, sem faltar caminho … e tu vai me falar se tem algum erro"* (`09:33:47`) | `docs/hotkey-altc-full-audit.md` -- o caminho inteiro (10 saltos), a prioridade dos seis casos, os sete erros que eram erros com o número que os provou, e os **cinco que continuam** | esse documento, com a tabela de verificação (`altc-gesture` 90/90 + os quatro passos da bateria) |

O contrato da doc foi reescrito: `docs/hotkey-gestos.md` dizia `HOTKEY_HOLD_MS = 900` e
"1 toque = painel de baixo" sem o fechar. Hoje diz **200 ms**, o **fechar no mesmo painel** e
o **disparo ao cruzar o limiar**.

```
python _main/altc-gesture-oracle.py           -> ALTC-GESTURE GREEN -- arms=90 pass=90 fail=0
python _main/altc-gesture-oracle.py --neg-arm -> NEG-ARM PASS
```

---

## 4. O RATCHET DE CÓDIGO (a razão escrita, como a lei do ficheiro exige)

`app/webview/youtube_captions.py`: **95 117 B → 95 302 B** (+185, **+0 linhas**). O
crescimento é o comentário que documenta o `clamp` do menu e a razão de a lista ter um
elemento só; a duplicação de ramo que sobrou da edição foi apagada na mesma passagem.
`_main/code-health-baseline.json` re-medido para esse ficheiro, só a métrica `bytes`.

```
python _main/code-health-oracle.py           -> CODE-HEALTH VERDICT PASS  (piorém: 0 métrica(s))
python _main/code-health-oracle.py --neg-arm -> NEG-ARM PASS  (3 de 3 mutantes apanhados)
```

---

## 5. SELF-AUDIT — o que este recibo NÃO prova

1. **Nenhum olho humano viu o menu de tradução.** O `clamp` foi medido por função pura
   (`_target_langs`) e por `track_from_info` com fixtures — não pelo clique real no menu
   dentro da app. A app não foi aberta (regra `SOTTO_NEVER_ON_OWNER_SCREEN`).
2. **O `200 ms` não foi re-medido no teclado dele.** É um número escolhido por ele, não um
   número derivado das pressões. Ficou escrito o que ele custa (§2) em vez de o esconder.
3. **`a59`/`a60` são novos e o mutante que os prova também.** Um braço novo que só corre
   contra o módulo carregado não prova o caminho do shell: o shell só chama
   `set_target_language`, e essa chamada não foi executada num processo real nesta revisão.
4. **A política não foi medida num vídeo real do YouTube** — a rede não foi usada. Quem prova
   a escolha da faixa são os fixtures do oráculo, não a tabela do yt-dlp de hoje.
