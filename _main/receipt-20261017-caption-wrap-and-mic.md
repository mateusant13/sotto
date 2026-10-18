# RECIBO — legenda com quebra de linha, botão que esconde o painel, e o censo dos microfones (2026-10-17)

Quatro pedidos do dono nesta tarde. Três fecham aqui, um tem um truth que só ele
pode resolver. Tudo medido; nada afirmado sem número.

---

## 1. "a legenda ta do tamanho da tela" — quebrada como o YouTube

### A pesquisa (feita nesta sessão, online, como ele pediu)

O consenso de **Netflix, TED, BBC, Section508 e VEED**:

| regra | valor | fonte |
|---|---|---|
| caracteres por linha | ≤ 42 | Netflix (EN), TED (o ponto em que UMA linha vira DUAS), Section508 (45), VEED (42); BBC usa 37 por causa do teletexto de largura fixa |
| linhas no ecrã | **2** | todos os cinco: *"a third line covers the frame"* |
| onde quebrar | depois de pontuação, **antes de conjunção**, antes de preposição | Netflix |
| o que nunca separar | artigo do substantivo, preposição da sua frase, conjunção do que se segue, pronome do verbo, partes de um verbo | BBC |
| largura | **68% de um quadro 16:9** | BBC |
| velocidade de leitura | 15-20 caracteres/s | Netflix/TED/BBC/VEED |

### A regra que muda a implementação

O BBC, verbatim: *"num character count so aproxima a largura numa fonte
PROPORCIONAL"* — e a nossa **é** proporcional (Segoe UI). `lilly` é mais estreito
que `mummy`. Portanto **contar caracteres está errado aqui**, e o próprio BBC diz
que se queimam as legendas tu mesmo se usa uma **largura**, não uma contagem.

Duas consequências, e as duas estão escritas no código:

1. a medição é feita em **píxeis com a fonte real** (GDI+), nunca em caracteres;
2. os 42 caracteres são um **tecto de legibilidade**, não o mecanismo.

### Feito

`app/webview/caption_wrap.py` (novo) — a política de quebra. `MAX_LINES = 2`,
`WIDTH_FRACTION = 0.68`, e uma lista de palavras às quais uma linha pode começar
(conjunções e preposições, nas duas línguas — `lang_id` é `auto`).

`app/webview/caption_overlay.py` — **uma disposição, calculada uma vez**, que a
medição e o desenho partilham. Ter duas cópias de "quantas linhas" é como uma
legenda é medida com uma altura e desenhada com outra.

### O que o fraseado ficou, na fonte real

Medido com GDI+, Segoe UI Bold 34 px, área de trabalho 1920 px:

```
entrada (88 ch): 'e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc'
    linha 1     258 px  e eu quero que
    linha 2     547 px  o alt c mostre as transcricoes em
    (nao cabe, devolvido: 'tempo real, de qualquer audio do meu pc')

entrada (119 ch): 'quando eu estiver a falar e a outra pessoa estiver a falar ao mesmo tempo ...'
    linha 1     477 px  quando eu estiver a falar e a
    linha 2     504 px  outra pessoa estiver a falar ao
    (nao cabe, devolvido: 'mesmo tempo nao quero que o sistema misture as duas vozes')

entrada (65 ch, EN): 'the caption should break at a natural seam and never split a word'
    linha 1     492 px  the caption should break at a
    linha 2     600 px  natural seam and never split a word
```

Orçamento: **727 px**. O tecto dos 42 caracteres é o que aperta; os 68% dariam
1305 px. Linhas equilibradas (477/504) e quebras em costuras: *"falar e a" /
"outra pessoa"*, *"break at a" / "natural seam"*.

**O que não cabe volta como `overflow`.** Uma frase truncada sem sinal é pior do
que uma frase partida, e a terceira linha no ecrã é o que todas as guias proíbem.

### O oráculo

`_main/caption-wrap-oracle.py`: **32 braços GREEN**, `--neg-arm` **4/4 RED**.

### Cinco instrumentos errados, todos registados

Este foi o mais caro de construir e vale a pena escrever:

1. `StringFormat.MeasureTrailingSpaces` — não é membro de `StringFormat`.
2. `fmt.FormatFlags = StringFormat.GenericTypographic` — no pythonnet esse nome
   resolve para o **TIPO**; a atribuição levanta `TypeError`.
3. `StringFormatFlags.GenericTypographic` — não existe no enum do .NET.
4. `g.MeasureString(text, font, 10000, fmt)` — o terceiro argumento é um `SizeF`
   de área de layout; um `int` levanta "Parâmetro inválido" **só em algumas
   strings**, que é o pior modo de falhar que existe.
5. A minha teoria do **garbage collector** — prendi os objectos `Graphics`,
   `Bitmap` e `Font` à closure devolvida, achando que o collector os levava. Não
   os levava. A teoria óbvia parecia certa e estava errada; está escrito na
   ficha porque voltar a tentá-la custaria outra hora.

O que funciona: `g.MeasureString(text, font)`, a sobrecarga de 2 argumentos — que
é **o mesmo motor que desenha** (`GraphicsPath.AddString` + `FillPath`). Medir
com GDI e desenhar com GDI+ é assim se corta a última letra.

### E o instrumento verifica-se a si próprio

`20 W` e `20 i` têm de ficar longe um do outro: `measure` levanta se não
discriminar, porque uma medição que devolve o mesmo número para tudo concordaria
com **qualquer** orçamento, e um portão que não pode falhar não é um portão.

### Dois erros meus que os números apanharam

- O tecto era `measure('M' * 42)`. `M` é a letra mais larga do alfabeto, portanto
 _media a pior linha que ninguém vai ler_: **1419 px**, contra **727 px** de 42
  caracteres de texto a sério. Com o tecto errado o orçamento dava 1305 px e uma
  frase de 68 caracteres ficava **numa linha só** — a queixa do dono, de novo e
  com outro chapéu.
- `_seam_index` guardava `best = i` a cada correspondência e só devolvia no fim,
  o que mantinha a costura **mais cedo** e produzia isto numa frase de 119
  caracteres: linha 1 = `quando` (137 px), linha 2 = `eu estiver a` (199 px), e
  tudo o resto de volta. Três palavras numa linha, numa função cuja função é
  escolher onde partir.

E uma lição do braço negativo: **duas das quatro mutações não disparavam.** Não
era falha do portão — a fração dos 68% simplesmente não aperta num ecrã de
1920 px, porque o tecto dos 42 caracteres ganha. Em vez de afrouxar o braço,
cada mutação passou a levar a **sua própria largura de área de trabalho**, e a
mutação da fração é testada a 800 px, onde ela aperta de facto. Um portão que só
funciona numa geometria não é um portão.

---

## 2. "assim q eu ativar a legenda, esconda o painel"

`app/webview/sotto_webview.py`, `_set_live_enabled`. **A ordem importa e mede-se:**
`hide_panel` chama `_blank_caption_window`, que tira os píxeis. Se
`show_caption_window(True)` corresse primeiro, a própria chamada que ligava a
legenda ia-a apagar a seguir, e ela só voltaria com a primeira palavra — o que
não é visível para quem só diz *"acendi e não aparece nada"*. Esconder primeiro,
acender depois.

O botão continua acessível: `hide_panel` não escreve `data-caption-window`, logo
o interruptor fica ligado, e o **Alt+C** traz o painel e o botão de volta.

---

## 3. Defeito encontrado de passagem: o log está a ser enterrado

Não era o que ele pediu, mas estava a tornar **inutilizável o instrumento** de
que preciso para provar o resto. `_record` escrevia no ficheiro **toda** vez que
`reason is not None` — e `reason` também é `'panel-not-visible'`. Ou seja: **um
clique em qualquer sítio do ecrã, com o painel escondido, escrevia uma linha.**

```
73 420 linhas OUTSIDE_CLICK
crescimento medido: 3 185 B em 5 s = ~640 B/s = ~55 MB/dia
```

Isto é um ficheiro grande; pior, é um ficheiro onde vive a prova de que o botão
da legenda não abre nada (`LIVE_ENABLED`, `STRIP_HEIGHT`, `PANEL_SURFACE`).
Enterrar a evidência num ruído de 640 B/s para o painel já estar escondido não
tem razão de ser: *"o painel não estava à vista"* **não é uma decisão**, é a
ausência de uma. O log passou a registar decisões e a contar o resto, que viaja
na próxima linha real.

---

## 4. "faz pegar o meu mic tambem" — o censo está feito, a escada ainda não

### O que a máquina tem

`_main/device-names.py`, medido: **29 entradas**. A escada de captura
(`device_candidates` em `worker/sotto_worker.py`) oferece o rung C (nome
explícito), o rung P (um pid), o rung A (loopback WASAPI de cada endpoint de
render) e o rung B (entradas cujo **nome** casa com cable/virtual/stereo mix/
voicemeeter/…). **Nenhum desses alcança um microfone**, e a lista de nomes é feita
de cabos virtuais, não de microfones. A escada está correcta — é por isso que o
microfone precisa de uma rung nova e não de um nome novo.

### `_main/mic-census.py` — 2,5 s por dispositivo, com números

**Com sinal:**

| id | API | nome | peak | rms |
|---|---|---|---|---|
| **5** | **MME** | **Microphone (HyperX Quadcast)** | **0.3695** | 0.2292 |
| 41 | WASAPI | Microphone (HD Pro Webcam C920) | 0.1179 | 0.1002 |
| 40 | WASAPI | Microphone (HyperX Quadcast) | 0.0773 | 0.0793 |

**Sem sinal ou inacessível:**

| nome | o que aconteceu |
|---|---|
| Microfone (NVIDIA Broadcast) | silêncio digital (0.000031) em MME, DirectSound e WASAPI |
| Headset (soundcore Space Q45) | **não há driver instalado** (MME error 6) |
| tudo o que é WDM-KS | `Blocking API not supported yet` — limite do PortAudio, não do dispositivo |
| Microfone (HD Pro Webcam C920) em MME | `A device ID has been used that is out of range` |

**Duas leituras que mudam o desenho:**

- **MME funciona só no Quadcast; WASAPI funciona nos dois.** A rung do microfone
  tem de ser **WASAPI**, com MME como recurso — o mesmo caminho que o rung A já
  usa, e por isso sem driver novo.
- A entrada **por omissão do sistema é `VoiceMeeter Output`**, não um microfone.

### O que falta, e porquê não está feito

Falta a rung e a **mistura**: o dono disse *"também"*, ou seja o microfone **em
vez de** o áudio do sistema, ou **além** dele. A verdade medida é que **dois
microfones diferentes têm sinal ao mesmo tempo** (Quadcast e C920), o que
significa que a escolha não é óbvia e que uma rung cega escolheria mal.

**Preciso de uma resposta sua para não adivinhar:** qual microfone é o seu — o
**HyperX Quadcast** ou a **Webcam C920**? E o microfone entra **junto com** o
áudio do sistema, ou sozinho?

---

## 5. "pesquisa como separar audio de pessoas no discord e faça"

### A verdade, e é uma limitação da plataforma, não uma configuração

Pesquisado nesta sessão. **No Windows o Discord entrega as vozes de todas as
pessoas num único stream de saída.** A mixagem é feita **pelo emissor**, antes de
chegar a ti, e o sistema operativo nunca vê uma stream por participante. Não há
registo, chave nem cabo virtual que separe duas pessoas dentro desse stream.

O que existe, segundo a pesquisa:

| método | o que dá | onde corre |
|---|---|---|
| **Craig** (bot) | **um FLAC por participante**, sincronizado ao segundo | servidor, Discord |
| OBS 28+ *Application Audio Capture* | o Discord **todo** numa faixa | local |
| Audacity + VB-Cable | **duas faixas: eu e todos os outros** | local |
| **Diarização** (pyannote, NeMo) | quem falou quando, sobre a faixa misturada | local |

A pesquisa é explícita: *"Discord calls rarely give you that by default"* e a
classificação é *Best: faixas por orador de um bot; **Good: duas faixas (eu vs
todos os outros)**; Okay: uma faixa misturada*.

### O que já temos e serve a esse fim

- `worker/sotto_worker.py` tem **`ProcessLoopbackTap`** — captura por
  **processo** (`--target-pid` / `SOTTO_TARGET_PID`), já fechado em código. O
  Discord é `Discord.exe`: dá uma faixa só dele, separada do resto do sistema.
- **O microfone é a faixa "eu".** Com a rung do microfone, "eu vs todos os
  outros" deixa de ser uma nota de rodapé e passa a ser a arquitetura — e é
  exactamente o que o `mic-census.py` mediu.

### O que não posso prometer

Separar **cada pessoa** dentro do Discord sem bot no servidor **não é
implementável localmente**. A única via honesta é o **Craig**, que é uma conta
e uma configuração do lado do servidor, não código. Diarização local dá "falou /
não falou" com attributos, não com nomes.

---

## 6. "guarda os audios, vao ser processados continuamente por modelo melhor. o parakeet"

### O motor já existe — `worker/redux_live.py`

**MEDIDO, hoje:** `worker/redux_live.py` (73 641 B) É o **Parakeet Redux (TDT)**,
com o **mesmo contrato JSONL no stdout**, e liga-se com um argumento:

```
run.cmd --worker worker\redux_live.py
```

`--worker` é a opção do próprio shell (`sotto_webview.py:6686`), portanto ligar e
desligar o Parakeet **não muda um ficheiro fora desse**. Um duplo clique no
`run.cmd` é a posição OFF.

### O bloqueio é o pesos, e é uma correcção ao AGENTS.md

**MEDIDO, agora, com `node` sobre `H:\sotto\worker\models`:**

```
worker/models  ->  1 directório:  nemotron-3.5-asr-ptbr-onnx-int4
```

**Não existe `parakeet-redux-onnx-int4/`.** O `AGENTS.md` diz o contrário em dois
lugares — a correcção **#7** afirma que *"está de novo em disco"* com os bytes
exatos, e a tabela da secção 8 diz **9 directórios** *"incl. fp32, both parakeet
dirs, and two qwen* dirs"*. Hoje são **1**. Isto é precisamente a regra 1 do
próprio ficheiro: *"'a grep devolveu ZERO' é uma afirmação com prazo de validade.
Repete o grep antes de a repetires"*. **A afirmação está errada e o Parakeet
não está no disco.**

Sem os pesos, `redux_live.py` arranca e recusa-se a carregar — o que está escrito
no código dele (`REDUX_LIVE_REFUSED`), o que é o comportamento certo.

Falta: **(a)** gravar o áudio em disco, **(b)** trazer os pesos do Parakeet,
**(c)** ligar o motor. (a) não depende de nada e posso fazê-lo já.

---

## 7. Pins desta revisão

```
app/webview/caption_wrap.py         (novo)
app/webview/caption_overlay.py      (rebitado: layout único, 2 linhas)
app/webview/sotto_webview.py        (esconde o painel + fim do spam do log)
_main/caption-wrap-oracle.py        (novo, 32 braços + 4 mutações)
_main/mic-census.py                  (novo)
```