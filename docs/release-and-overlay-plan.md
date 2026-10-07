# Release + overlay — especificação (pedida pelo dono, 2026-10-07)

Escrito para ser executado mais tarde, sem depender da memória desta sessão. Onde digo **MEDIDO** é
porque foi medido nesta máquina; onde digo **A DECIDIR** é porque precisa da tua escolha; o resto é
plano.

## 1. Instalador `.exe` — o mais leve que conseguirmos

**O que pesa, medido:** os modelos. `nemotron int8` 1.020 MB, `int4` 756 MB, `fp16` 1.247 MB,
`fp32` 2.479 MB; `parakeet-redux-ternary` 171 MB. O Python + pywebview + pythonnet + kestrel são
algumas centenas de MB. **O WebView2 já existe no Windows 11** (o runtime Evergreen está cá — o app
corre nele).

Consequências para "o mais leve":
- **Não empacotar os pesos no instalador.** O `.exe` instala o app e descarrega os modelos na
  primeira utilização, com `hf download` e verificação de sha256 (é o que já faço hoje à mão).
  Assim o instalador fica na casa das **dezenas de MB**, e o disco cresce só quando o dono aceita.
- **Nunca PyInstaller `--onefile`**: ele descompacta tudo para `%TEMP%` no arranque (arranque lento e
  o disco a dobrar). Se for para empacotar, é `--onedir`.
- **Inno Setup** (leve, script em texto, aceita instalar por utilizador sem admin) é a escolha
  natural; NSIS/WiX são alternativas. O instalador tem de: criar atalho no **Menu Iniciar** (é o que
  torna o app **pesquisável no Windows**, tecla Windows → escrever "Sotto" → abrir), atalho opcional
  no Desktop, entrada de **autostart** (o `HKCU\...\Run` que já existe e está verificado),
  e desinstalador.
- **WebView2**: o instalador deve *verificar* o runtime e, se faltar, apontar para o bootstrapper da
  Microsoft em vez de o embutir.

## 2. System tray, e sair só por lá ou pelo Task Manager

- Ícone no tray com menu: **Mostrar painel / Esconder / Legenda ao vivo on-off / Sumir/ Sair**.
- **O painel perde o botão Quit.** Hoje existe um `Quit` no cabeçalho (foi o F7); a regra nova é que
  **sair só pelo tray ou pelo Task Manager**. Isso muda o painel: o `Quit` sai, ou passa a "esconder".
- `Alt+C` continua a ser o controlo principal; o tray é a segunda porta.

## 3. "Um finalizar finaliza ele inteiro de verdade" — e aqui há uma decisão tua

**O estado de hoje, medido:** o task manager mostra **dois** processos — a shell
(`pythonw.exe` + `sotto_webview.py`) e o worker (`python.exe` + `sotto_worker.py`), que é um **filho**
dela. Matar a shell **não** garante matar o worker (ele fica órfão e continua a capturar áudio).

Duas maneiras de cumprir o que pediste, com custos diferentes:

| opção | como | o que ganhas | o que perdes |
|---|---|---|---|
| **(a) Job Object** *(recomendada)* | a shell cria o worker dentro de um **Windows Job Object** com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` | matar a shell (ou o job) **mata a árvore toda**, garantido pelo kernel, e nenhum filho sobrevive; um Task Manager → "End task" na shell limpa tudo | o Task Manager continua a mostrar 2 linhas (a shell *é* a raiz) |
| **(b) Um só processo** | o worker passa a **thread** dentro da shell (sem processo filho) | uma única linha no Task Manager, literalmente o que pediste | **perde-se o isolamento de crash**: hoje um crash do runtime nativo (ORT/kestrel) mata só o worker e a shell reinicia-o em 2 s; em thread, uma falha nativa leva a app inteira atrás — com um modelo de 1,7 GB e kernels nativos, isto não é teórico |

**A DECIDIR por ti:** (a) ou (b). O meu voto é **(a)** — dá-te a garantia que pediste ("um finalizar
finaliza ele inteiro de verdade") sem trocar isolamento de crash por cosmética de Task Manager. Se
preferires (b) literalmente, é implementável, mas o reinício automático do worker que hoje salva a
app de uma morte de dispositivo deixa de existir.

## 4. Tamanho da fonte das transcrições

- Um controlo **+ / −** para o tamanho das legendas, **nas duas superfícies**: no overlay (o de baixo)
  e no painel da direita. O valor é **um só**, partilhado — mudar num sítio muda no outro.
- Implementação: uma custom property CSS (por exemplo `--escala-legenda`, aplicada ao
  `--size-caption`) no nó raiz, persistida entre arranques. Escala por passos (ex.: 0,85 / 1 / 1,15 /
  1,35 / 1,6), com limites, e nunca a ponto de a linha caber mal — o painel tem 380 px de largura.
- Precisa de **atalho de teclado** também (o dono está a ver vídeo, não a apontar o rato): sugerido
  `Alt+Shift+=` / `Alt+Shift+-` com o painel aberto.
- Acessibilidade: o aumento de fonte tem de continuar AA contra a placa em todos os temas.

## 5. O overlay: triângulo invertido, quase transparente, a subir de baixo

O que pediste, em palavras tuas: *"o overlay tem que parecer um triangulo invertido, quase ou todo
transparente, igual aqueles apps que ao apertar pra falar, surge de baixo da tela uma pequena
animacao com um pequeno design simples e minimalista."*

- **Ancorado no fundo do ecrã**, centrado horizontalmente, **triângulo invertido** (base larga em
  cima, ponta em baixo) — a forma lê-se como "algo a subir da borda".
- **Quase ou totalmente transparente**: o que se vê é o conteúdo (legendas/estado), não um painel.
- **Animação de subida** ao ser chamado: uma subida curta com fade, ~180–250 ms, ease-out; e
  `prefers-reduced-motion` desliga-a.
- **Técnica recomendada (evita a armadilha):** a janela nativa **não** se move por frame. Ela é
  criada com o tamanho final, encostada ao fundo, transparente e *click-through*; a subida é feita
  **dentro do DOM** (`transform: translateY`) sobre um fundo transparente. Mover/redimensionar a
  janela nativa a 60 fps com WebView2 é o caminho curto para flicker.
- **Alvos e foco:** continua a nunca roubar o foco; continua *click-through* até o rato entrar.
- **Forma vs retângulo:** a janela é retangular (o Windows não faz janelas triangulares), mas o
  **conteúdo** desenha o triângulo e o resto é transparente e não-clicável. `--opaque` desliga a
  transparência se em algum momento for preciso diagnosticar.

## 6. O que isto obriga a mudar no que já existe

- `app/electron/panel.js` / `panel.html`: sai o `Quit` (ou passa a "esconder"), entra o **+ / −** de
  fonte, e o overlay é uma **terceira superfície** (strip de baixo, triângulo) ao lado da faixa e do
  painel.
- `app/webview/sotto_webview.py`: **Job Object** para o worker (secção 3), janela do overlay com
  âncora no fundo, e o **tray** (ícone + menu + sair).
- `app/webview/run.cmd`: inalterado na semântica; o instalador chama o `pythonw.exe` do Python
  embutido, nunca o `run.cmd` (é consola — ver a regra da casa).

## 7. Notas de honestidade

- Nada disto foi executado ainda: é especificação. As duas exceções são os factos MEDIDOS citados
  (tamanhos dos modelos, a árvore de processos de hoje, o autostart já instalado, o WebView2 presente).
- O **empacotamento de Python + pythonnet + pywebview** é a parte com mais risco de surpresa
  (é um app .NET + CPython: convém testar num Windows limpo antes de prometer instalador).
- O overlay triangular precisa de uma decisão de dono que não é técnica: **quanto do ecrã** pode
  ocupar em altura, e se aparece sobre tudo. **Sobre jogos: DECIDIDO — pode aparecer por cima de
  jogos, mas tem de ser uma configuração DESATIVADA por omissão** (palavras do dono: *"pode aparecer
  por cima de jogos, mas tem que ser uma configuracao desativada por default"*). Técnica: aparecer
  sobre fullscreen exclusivo obriga a topmost + (em alguns casos) hook de apresentação; com o
  default desligado, o caso difícil não é o caminho normal e pode ser afinado depois.
