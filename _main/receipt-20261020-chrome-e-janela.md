# Sotto receipt — o chrome da página e a janela errada (2026-10-20)

Owner, 2026-10-20, verbatim:

> "eu ja mandei tu resolver o negocio de que por algum motivo texto de outras
> coisas que nao sao o transcript do video do youtube fica vazando pro nosso app"

Duas correcções em `app/webview/external_subs.py`, um portão novo em
`_main/`, e o passo registado na bateria. As medições de campo (a árvore UIA
da janela do dono, os 20 textos, o censo das 19 janelas) são o **ground truth
do briefing**; eu não as repeti — o meu portão prova as mesmas claims sobre
fixtures sintéticas, sem abrir nada.

---

## 1. O furo A — o leitor lia a PÁGINA, não o VÍDEO

`_player_rect` respondia "o maior elemento da janela", e numa página do
YouTube essa resposta é a PÁGINA.

| o quê | medido (janela real do dono, Chrome, hwnd 1710572) |
|---|---|
| janela | `(-8, -8, 1928, 1040)` |
| `player_rect` antigo | `(0, 121, 1905, 4107)` — área 7 593 330; o `y=4107` está **abaixo** do fundo da janela (1040): a árvore carrega o documento inteiro, scrolado |
| banda antiga | `121 + (4107-121)*0.62` = **2592.32** → dentro dos COMENTÁRIOS |
| elemento real do vídeo (mesma árvore) | `class="html5-video-player ytp-trans"`, `name="Player de video do YouTube"`, rect `(16, 189, 1354, 942)`, área 1 007 514 |
| banda correcta | `189 + (942-189)*0.62` = **655.86 .. 942** → onde o YouTube PINTA a legenda |

**A correcção** é uma função nova, `_video_player_rect(uia, root, window_rect)`:
prefere o elemento de vídeo real e só cai na heurística antiga quando não há
elemento de vídeo (Stremio, outro player).

* O sinal é a **CLASS NAME** (`html5-video-player`), **não** o `name`: o `name`
  é a tradução da interface ("Player de video do YouTube" em pt-BR) e muda com
  a língua; a classe é a marcação do player.
* O maior elemento com essa classe ganha (um mini-player na mesma página não
  rouba a banda).
* O elemento tem de estar **dentro** da janela (vídeo scrolado para fora não
  está a ser visto) e ter pelo menos 40x40 px.
* `caption_lines` passou a enumerar a árvore **uma vez** (o `FindAll` era
  feito duas vezes: uma para o rect, outra para a banda).

**O que a geometria compra**, medido no portão (mesmos números, duas
execuções — a banda antiga e a banda nova, sobre a MESMA árvore):

| | banda antiga (página) | banda nova (vídeo) |
|---|---|---|
| rect | `(0, 121, 1905, 4107)` | `(16, 189, 1354, 942)` |
| `band_top` | 2592.32 | **655.86** |
| linhas de chrome que viraram **candidatas** | **5 de 6** | **0 de 6** |
| linhas de chrome que chegaram à **saída** (3 polls) | **4** | **0** |
| linhas da **legenda real** na saída | **0** | **2** |

Das 6 linhas de chrome medidas, **5 sobrevivem a todas as regras de
vocabulário** do módulo (são frases normais: um comentário, um título de
recomendado, um handle, uma badge) — só a geometria as pode tirar. A sexta
("há 8 dias") já é apanhada pelo `_AGO_ONLY`; está no fixture para provar que
os dois mecanismos não lutam.

---

## 2. O furo B — uma janela que não é player foi adoptada como player

O Explorador de Arquivos do dono chamava-se
`kicktwitchyoutube_instagram - Explorador de Arquivos`: **"youtube" era o
nome de uma pasta**. O teste era só o título, e o censo das 19 janelas
visíveis tinha **exactamente 1 falso positivo** — esse.

Consequência medida: ao adoptar essa janela, o leitor lia a lista de
ficheiros como legenda e o **video id nunca vinha**
(`edit_values` → `['_tools', <datas>, 'Pasta de arquivos', 'cookie-extension']`),
logo a app perdia a legenda REAL do YouTube.

**A correcção** é a função nova `_window_is_player(title, proc, url)`,
usada por `player_source` **e** por `find_player_window`:

1. a **URL** (`youtube.com/watch?v=` / `youtu.be/`) é prova e conta sempre,
   qualquer que seja o processo;
2. o **título** só conta se a janela for um **BROWSER**
   (`_is_browser`: chrome / msedge / firefox) — o título de um player é o
   título de uma ABAS, e uma aba só existe num browser;
3. **Stremio** continua reconhecido pelo **PROCESSO** (`stremio.exe`), que é
   a prova real dele.

`find_player_window` devolve agora o primeiro **PLAYER** (ordem de z), e não o
primeiro título com "youtube": o Explorador deixou de ser candidato, e o
navegador dele é devolvido mesmo estando enumerado depois.

---

## 3. O portão novo

`_main/external-subs-geometry-window-oracle.py` — **13/13 arms, 6/6 mutantes
RED, 0 decorativos**, `VERDICT: PASS`, rc=0.
`--neg-arm` sai com **rc=1 por desenho** (como o `youtube-captions-oracle.py`).

Corre num **processo próprio**: não abre janela, não abre browser, não
renderiza áudio, não toca na app. O scratch é um `mkdtemp` sob
`$TMPDIR` (`I:\cc-tmp`) apagado no fim; o `--state <ficheiro>` grava o
recibo da corrida (veredicto, contagens, sha256 do módulo).

| arm | o que prova |
|---|---|
| a1 | com o rect da página **e** o elemento de vídeo presentes, `player_rect` = `(16, 189, 1354, 942)` |
| a2 | `band_top` = 655.86 (vídeo), e **não** 2592.32 (página) |
| a3 | a legenda real **é lida** (`>> So the Akali`) |
| a4 | o chrome da página **não** chega à caixa |
| b1/b2/b3 | **sem** elemento de vídeo, a heurística antiga ainda vale: rect `(0, 121, 1905, 4107)`, banda 2592.32, e uma linha nessa banda ainda é lida |
| c1 | `player_source` com título "youtube" e proc `explorer.exe` → `''` (a falsa positiva fechada) |
| d1 | a janela real do dono (chrome.exe) → `external:youtube` (o caso medido continua) |
| e1 | proc `explorer.exe` mas URL `youtube.com/watch?v=...` → `external:youtube` (a URL é prova mais forte que o título) |
| f1/f2 | `find_player_window` devolve a janela do **browser** (0x2222) e **nada** (0) quando o único candidato é o Explorador |
| g1 | a janela real ainda devolve o **video id** `cUeZMUGCxrw` |

### O braço negativo — EXECUTADO, não escrito

Seis cópias quebradas do motor, cada uma um patch textual de uma âncora
**única** (uma âncora em falta ou ambígua é decorativa e o portão recusa-a):

| mutante | apanhado por |
|---|---|
| `the-page-is-used-instead-of-the-video` | a1, a2, a3 |
| `the-video-rect-is-ignored` | a1, a2 |
| `the-smallest-video-element-wins` | a1, a2, a3 |
| `a-youtube-title-in-a-non-browser-is-a-player` | c1, f1, f2 |
| `the-url-only-counts-when-the-title-matches-too` | e1 |
| `find-player-window-accepts-any-youtube-title` | f1, f2 |

---

## 4. A bateria

Passo novo `external-subs-geometry-window`, na secção dos portões de
`external_subs` (a seguir ao `external-caption-chrome-census`), no formato
`:step`/`:record` que o ficheiro usa hoje.

Corrida real (2026-10-20, depois da minha mudança, **com** as alterações
não-commitadas da outra lane já no ficheiro):

```
steps 51  gate 39  control 10  skipped 1  expect-red 1  missing 0  failed 0
BATTERY-VERDICT: GREEN WITH 1 SKIPPED - hotkey-delivery (o próprio instrumento
diz VERDICT: SKIPPED; é o kind declarado, não uma falha)
exit-code: 0
```

O `skipped=1` é o `hotkey-delivery`, whose instrument declares the skip; o
baseline de antes (48 passos / 37 gates / 10 controlos / 0 falhas) difere
porque a outra lane introduziu 2 passos (`stepcache-oracle`,
`skip-verdict-guard`) no mesmo ficheiro. O meu passo é **um** dos 51 e
saiu a 0 (na primeira corrida correu a sério; na segunda, com os ficheiros
inalterados, veio do cache da outra lane).

**CONCORRÊNCIA — o que aconteceu, exactamente.** A outra lane estava a
re-escrever `_main/_audit-verify-all.cmd` ao mesmo tempo. Timeline:

1. Eu inseri o passo (por bytes, CRLF preservado): 50 621 B, sha `0152EC…`.
2. A outra lane reescreveu o ficheiro **e o meu passo ficou lá** (eles
   partiram da working tree): 51 832 B, sha `7CACF6…`.
3. A minha reinserção (por não ter seen a cópia) duplicou o bloco; **removi
   a duplica** por bytes e o ficheiro voltou a ser **byte a byte** o da outra
   lane: 51 832 B, sha `7CACF6…`, **1 cópia** do passo, 765 CRLF / 0 bare LF.

**A bateria NÃO está no meu commit**: o ficheiro carrega o trabalho não
commitado da outra lane (242 inserções / 103 remoções) e commitar um
ficheiro partilhado em andamento levaria o trabalho deles dentro do meu
commit. O passo está **no working tree**, pronto a ser commitado por quem
fechar a bateria.

---

## 5. O que NÃO foi medido

* **Não reabri a app, o browser nem o worker** (regra). Logo: o número de
  linhas de chrome que deixa de entrar **na app do dono** não é medido — é
  medido no leitor, sobre fixtures.
* **Não censerei a árvore UIA viva do dono.** A classe
  `html5-video-player`, os rects, os 20 textos e o censo das 19 janelas são o
  **ground truth do briefing**; o meu portão usa-os como fixtures, não os
  re-mediu.
* **Não medi o caso do YouTube SEM vídeo na página** (home, search, playlist):
  aí não há elemento `html5-video-player` e vale a heurística antiga — está
  provado no arm b, mas o comportamento na app real não foi medido.
* **Não medi o efeito no caminho da faixa real** (`youtube_captions.py`): não
  foi tocado.
* **O leitor de página, na app, só é consultado para players que NÃO são
  YouTube** (para uma janela do YouTube a shell usa a faixa real do próprio
  YouTube). Os 20 textos do briefing são do **leitor** (todos PENDING, nenhum
  confirmado), e é no leitor que a correcção foi feita.

## 6. Limitações

1. **A correcção geométrica depende da classe `html5-video-player`.** É a
   marcação do YouTube e pode mudar. Onde não há elemento de vídeo, vale a
   heurística antiga (arms b1-b3). O `name` do elemento não é usado de
   propósito: é a tradução da interface e muda com a língua.
2. **A lista de browsers é uma whitelist** (`chrome`, `msedge`, `firefox`).
   Um YouTube no Brave/Vivaldi/Opera deixa de ser reconhecido pelo título, e
   a URL só é lida da barra de endereço para um browser dessa lista — logo
   essa janela **não é adoptada**. Antes era (pelo título). É uma troca
   consciente: preferi não adoptar uma janela a adopter a errada, mas é uma
   limitação real.
3. **"stremio" no título de um não-browser deixou de ser prova** (era a mesma
   classe de falso positivo: um ficheiro `stremio.mkv` no Explorador). O
   **processo** Stremio continua a ser prova, e o arm de fallback prova que
   o Stremio não parte.
4. **`find_player_window` não tem barra de endereço para ler**: com duas
   janelas do YouTube abertas ganha a de cima, e ele não distingue a home do
   vídeo.
5. O leitor passa a devolver **o rect do vídeo**, o que muda a banda de
   leitura em qualquer player HTML5 (não só YouTube).

## 7. Ficheiros

| ficheiro | bytes | sha256 (medido) |
|---|---|---|
| `app/webview/external_subs.py` | 35 117 | `8CF7F45802066ECB3EE261190BEAD6941BF05D8CC078016347DDCF98FC7343F1` |
| `_main/external-subs-geometry-window-oracle.py` | 24 714 | `AB1F3EF90CF46C963A6D64E0C8B21564D0940C15267D3CE6DA63B7B51DC54A22` |
| `_main/receipt-20261020-chrome-e-janela.md` | (este) | — |
| `_main/_audit-verify-all.cmd` (working tree, **não commitado**) | 51 832 | `7CACF6AEC37867CA8B4E73007B99B329DA1A8FD75D69D509FFEDB741794C06E3` (765 CRLF / 0 bare LF) |

`app/webview/external_subs.py` e o portão são **LF**; a bateria é **CRLF
puro** (editada por bytes, para não partir a lista de passos).
