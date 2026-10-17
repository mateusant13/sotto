# RECEIPT — a legenda nativa em janela Win32 em camada (2026-10-17)

Lane: continuacao de uma sessao que morreu a meio do commit (OpenRouter 402).
Proprietario pediu: **commit e push**. Nada foi lancado.

Pinos medidos no inicio desta sessao (regra 2 do AGENTS.md — o nome a
revisao, porque as lanes mexem nestes ficheiros a toda a hora):

| ficheiro | bytes | sha256 (16) | notas |
|---|---|---|---|
| `app/webview/caption_overlay.py` | 17 207 | `C422664CAF026EFED` | 428 linhas, LF puro |
| `app/webview/sotto_webview.py` (antes) | 601 747 | — | 11 250 CRLF + 321 LF (misturado) |
| `app/webview/sotto_webview.py` (depois) | 588 705 | — | 11 198 CRLF + 139 LF |
| `_main/_design-lane/gen_themes.py` | 175 579 | — | 3 456 CRLF |

## 1. O que a overlay e

Uma janela Win32 nativa, nao uma segunda janela pywebview:

- `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE |
  WS_EX_TOPMOST` sobre `WS_POPUP`.
- Ligacoes `ctypes` completas (user32/gdi32/gdiplus).
- GDI+ desenha texto branco com contorno preto e o LED verde num DIB
  `Format32bppPArgb`.
- Composto com `UpdateLayeredWindow` + `AC_SRC_ALPHA` (alfa por pixel de
  verdade).
- **Thread propria com o seu proprio message pump.** A primeira tentativa corria
  na thread da UI e travou o WinForms: o pump da overlay precisa de `GetMessage`
  e nao pode pedir mensagens a uma thread que esta a fazer outra coisa.

## 2. Porque o WebView2 nao podia fazer isto

Nao e opiniao, e o upstream mediu:

- `MicrosoftEdge/WebView2Feedback#118` — um utilizador pôs `WS_EX_LAYERED` +
  `LWA_COLORKEY` no HWND que embute o WebView2 e o resultado foi literalmente
  *"That did not work"*.
- O pywebview documenta `transparent` como **nao suportado no Windows**.
- O commit anterior desta serie (`2a55916`) ja tinha chegado a esta conclusao e
  tinha tentado o caminho WebView2 (`DefaultBackgroundColor=Transparent`),
  medindo **0,56 % de branco** em vez de placa inteira. Per-pixel alpha nao e
  alcancavel por essa via.
- `Wails #6088`: chamadas layered/alpha partem a transparencia por pixel.

Logo: `UpdateLayeredWindow` nao e uma preferencia estetica, e o unico mecanismo
suportado.

## 3. O que foi medido nesta sessao

| o quê | como | resultado |
|---|---|---|
| `py_compile` dos 3 ficheiros Python | `python -m py_compile` | **rc=0** |
| `panel.js` | `node --check` | **rc=0** |
| gerador: proveniencia | `gen_themes.py --check` | `10 theme(s), 535 ledger row(s), 0 without provenance` |
| gerador: reprodutibilidade | run em copia (`I:\cc-tmp`), 3023 ficheiros de input | **6 de 7 ficheiros byte-for-byte** |
| gerador: a 7.ª saida | comparacao byte a byte | `theme-1.css` diferia em **4 bytes** |
| a origem dos 4 bytes | comparacao linha a linha | **MAO**: `.dialog-button` tinha `rgba(255,255,255,0.72)` em vez de `var(--text-secondary)` |
| gerador: depois de regenerar | comparacao byte a byte | **ALL_IDENTICAL** (7/7) |
| gerador: idempotencia | 2.ª execucao + sha256 | **0 ficheiros mudados** |
| fugas de scope | `node _main/scope-leak-oracle.js` | `VERDICT PASS`, 9 stylesheets, 0 sem scope |
| modelo em disco | `Get-ChildItem H:\sotto\worker\models -Directory` | 1 unico: `nemotron-3.5-asr-ptbr-onnx-int4` |
| pesos do modelo | listagem | 783 537 972 B; `encoder.onnx` 1 248 467 + `.data` 681 652 224, `decoder.onnx` 4 417 + `.data` 59 760 640, `joint.onnx` 1 796 + `.data` 37 822 592, `silero_vad.onnx` 2 327 524, `tokenizer.json` 642 525, `vocab.txt` 64 024 |
| os nomes batem com o worker | leitura | `sotto_worker.py:561-563` carrega `encoder.onnx`/`decoder.onnx`/`joint.onnx` — exactamente estes |
| codigo morto | `grep` em `app/` e `_main/` | `_on_caption_loaded`, `_on_caption_before_show`, `_caption_bgc_transparent`: **zero call sites** |
| suite + gate (pre-commit) | hook, 3 commits | suites **15/15**, gate **9/9** |

## 4. O codigo morto que saiu

`self.caption_window` e atribuido **uma unica vez** em `sotto_webview.py:4807`
como `None` e nunca mais e atribuido. Os tres metodos que o desreferenciavam
nao tinham nenhum chamador no repositorio inteiro:

- `_on_caption_loaded` (190 linhas)
- `_on_caption_before_show` (57 linhas)
- `_caption_bgc_transparent` (43 linhas)
- mais o `self.caption_window = None` orfao

**235 linhas fora.** Os `_main/_panel-*-mutant.py` que o `grep` tambem devolve
sao **copias independentes** do shell, nao chamadores — e a razao pela qual
`py_compile` do repo inteiro continuaria a passar sem estes metodos.

**Mantido:** `show_caption_window` — e viva, chamada de `:4482` (float on/off),
`:6417` (hide do painel) e `:8383` (botao live). Apagar esta seria partir o
controque que o dono pediu.

**Mantido, e digo porque:** `set_layered_color_key` (nivel de modulo, `:1500`) ja
nao tem nenhum caller tambem. Fica **fora do ambito** desta correcao — e uma
funcao de nivel de modulo, nao um dereferenciador de `caption_window`, e
removela nao foi medido por nada. A frase do docstring que nomeava os dois
metodos apagados foi corrigida, para o ficheiro nao ficar a dizer uma coisa
falsa.

## 5. Commits desta serie

| SHA | o quê |
|---|---|
| `20b1c88` | a overlay nativa + `external_subs.py` + o codigo morto removido |
| `071ec51` | `worker/config.json`: `model.dir` para o modelo que existe em disco |
| `53ec557` | regeneracao dos temas (gerador + 6 CSS) |
| `f24649c` | `panel.js`: strings de pausa em portugues |
| (este commit) | este recibo — o SHA e o commit que cria este ficheiro; nao se pode escrever dentro do ficheiro que ele mesmo cria |

Ramo: `chore/measurement-instruments-20261011-051354`. Os quatro commits
anteriores sao deste trabalho; `494a927` e `2a55916` ja estavam pushados e nao
foram tocados.

## 6. O que NAO foi verificado (e nao deve ser lido como verificado)

1. **A overlay nunca foi vista correr.** A ordem do dono proibe subagentes de
   abrir o shell, e o proprietario esta a usar a maquina. Aceitacao estatica
   apenas: compila, a logica esta lida, a thread existe. **Se esta corre mal ao
   vivo, nada aqui o contradiz.** O Lead tem de abrir e ver.
2. **`model.lang_id` continua `"auto"` (101)** — medido contra o modelo
   multilingue antigo. Este modelo e um fine-tune **monolingue** pt-BR e o
   README diz `lang_id` pt-BR = **12**. Se o embedding nao cobrir o slot 101,
   o decode pode colapsar. **Nao mexi**, porque mudar `lang_id` sem audio real
   seria inventar uma convencao de decode, que e o erro que o `docs/model-specs/`
   ja proibe. Precisa de um run com a amostra pt-BR.
3. **Os insumos do gerador nao estao versionados.**
   `_main/_design-lane/zips/` e git-ignored (84,2 MB, 3023 ficheiros). As folhas
   CSS sao "geradas" mas **nao sao reproduziveis a partir de um clone limpo**.
   O gerador e provadamente current; os arquivos de que ele le nao estao no
   repositorio.
4. **O `panel.js` ficou traduzido a meio** — `dom.pauseConfirmButton`
   (`:2436`) continua em ingles.
5. **15 recibos `?? _main/receipt-*` de outras lanes** (2026-10-10 a 2026-10-16:
   auditorias, UX, hot-path) ficaram por commit. Nenhum menciona a overlay.
   Sweepá-los para dentro de um commit de legenda seria atribuir a uma mudanca
   receipts que descrevem outras. Ficam para o Lead despachar.
6. **`set_layered_color_key`** sem caller (ver 4).

## 7. Nao foi feito, de proposito

- Nada foi **lancado**: nem `run.cmd`, nem `sotto_webview.py`, nem o worker.
- Nenhum processo foi **matado**.
- `app/shadowplay/state/gate/gate-log.txt` (+2520 linhas) e lixo de teste
  (`?? app/_base-*.test.txt`, `?? $null`, `?? .txt`, `?? %SystemDrive%/...`) nao
  foram commitados **nem apagados**.
- Nenhum CSS escrito a mao: a mao que existia foi desfeita pelo gerador.
- O resto do churn da arvore (`_moved/aireplay`, `history-verify`, dozens de
  `_main/_panel-*`) foi deixado exactamente como estava — nao e meu.