# Recibo — a legenda nativa quebra como o YouTube e nunca parte uma palavra (2026-10-21)

**O DONO, verbatim (2026-10-21):**
> *"voce nao ta fazendo a legenda parecendo com como o youtube da DISPLAY e quebra
> as linhas e etc. é pra tu fazer isso."*
> *"só palavras inteiras"* (o mesmo pedido, 2026-10-20, no bloco da legenda)

**A LEGENDA QUE O DONO VÊ É A NATIVA, NÃO O `caption.html`.** `sotto_webview.py:69`
define `CAPTION_HTML` e há **uma** ocorrência — a definição; o único
`webview.create_window` é o do painel (`:5805`); e `sotto_webview.py:5885` diz
verbatim: *"THE FLOATING CAPTION IS A NATIVE LAYERED WINDOW, NOT A WEBVIEW2"*.
Por isso o CSS de `app/panel/` **não chega ao ecrã** nesta via: quem desenha é
`app/webview/caption_overlay.py` + `app/webview/caption_wrap.py`.

---

## 1. O QUE MUDOU

**`app/webview/caption_wrap.py`** — o módulo ganhou o **passo de equilíbrio**:
`_greedy_end`, `_greedy_lines`, `_is_seam` e `_balance_last`. `wrap()` passa a
terminar em

```python
lines = _greedy_lines(words, measure, max_px)
lines = _balance_last(lines, words, measure, max_px)
```

`_balance_last` move a fronteira entre as **duas últimas linhas** (as duas que a
janela mostra) para a divisão que minimiza a diferença de largura, e obedece a
**duas regras duras**:

* uma linha **nunca** excede `max_px` (cada candidato é medido antes);
* **nenhuma palavra é nunca partida** (um candidato é um índice de palavra).

Um corte natural (`_is_seam`) ganha um empate próximo, e entre opções iguais
ganha o `m` maior — a linha 1 fica tão cheia quanto o equilíbrio permite.

## 2. O ANTES E O DEPOIS, MEDIDOS

**INSTRUMENTO:** `_main/caption-native-wrap-oracle.py` — **puro e em processo**.
Mede com a **função de medição do próprio produto** (`caption_overlay._measure`:
GDI+ `Graphics.MeasureString` sobre uma **bitmap de memória** — nenhuma janela,
nenhuma app, nenhum browser, nenhum áudio) no **tamanho do produto** (Segoe UI
Bold 34 px) e com o **orçamento do próprio produto** (`caption_wrap.budget_px`).
As linhas vêm do **próprio `_layout` do produto**, portanto mede-se o código que
vai correr, não uma transcrição dele.

| corpus | ANTES (sem o passo de equilíbrio) | DEPOIS |
|---|---|---|
| pior desequilíbrio | **0,382** (o exemplo do dono: *"e o que eu quero e que a legenda apareca aqui em baixo, igual o youtube faz"*) | **0,118** |
| linha mais larga que o orçamento | 0 | 0 |
| palavras perdidas/partidas | 0 | 0 |

O orçamento medido nesta máquina: **727,1 px** (68 % de uma área de 1920 px, com
o limite de 42 caracteres).

**O "0,382" É O EXEMPLO DO DONO, MEDIDO COM O CÓDIGO DE HOJE** — o exemplo que
ele próprio descreveu, medido com o mesmo instrumento antes e depois.

## 3. O QUE O PORTÃO PROVA (E O QUE ELE **NÃO** PROVA)

| arm | o que afirma | verde |
|---|---|---|
| ARM 1 | nenhuma linha excede o orçamento | GREEN (0 over) |
| ARM 2 | **as palavras que saíram da janela seguidas das palavras no ecrã são as palavras que entraram** — nada partido, nada perdido | GREEN (0 lost) |
| ARM 3 | as duas linhas estão equilibradas (≤ 0,25) | GREEN (worst = 0,118) |
| ARM 4 | uma palavra mais larga que a caixa é entregue **inteira**, não partida | GREEN |

**O CASO DA PALAVRA LONGA É UM COMPORTAMENTO DOCUMENTADO, NÃO UM DEFEITO** — e o
portão conta-o à parte: `_greedy_end` diz que uma palavra mais larga que a caixa
vai sozinha para a linha e é **clipped** pelo renderer, porque partir uma palavra
é proibido. Onde isso acontece o equilíbrio é **impossível** sem partir a
palavra, e por isso o ARM 3 mede só os casos onde o equilíbrio é possível.

**O BRAÇO NEGATIVO, EXECUTADO (não decorativo):** dois mutantes do módulo, cada
um numa **cópia** instalada como o módulo `caption_wrap` (que é o que o overlay
importa), e os mesmos arms contra eles:

| mutante | apanhado por |
|---|---|
| **M1** o passo de equilíbrio é removido | o **ARM 3** (balanço) |
| **M2** o espaço entre as palavras desaparece | o **ARM 2** (integridade das palavras) |

`python _main/caption-native-wrap-oracle.py --neg-arm` → **6/6 GREEN**, os dois
mutantes apanhados, o controlo verde.

## 4. PINS

| ficheiro | bytes | EOL | sha256 (16) |
|---|---|---|---|
| `app/webview/caption_wrap.py` | 20 049 | CRLF 0 / bareLF 417 | `3A996C4044B3DC76` |
| `app/webview/caption_overlay.py` | 45 100 | CRLF 0 / bareLF 653 | `42019370C4C6451A` |
| `_main/caption-native-wrap-oracle.py` | 10 993 | CRLF 0 / bareLF 252 | `1B7CBC35272925F3` |

(`app/webview/*.py` é **LF** por `.gitattributes`; o HEAD do `caption_wrap.py`
também era LF — **não houve regressão de EOL**.)

### 4.1 O `caption_overlay.py` TAMBÉM FOI MEXIDO (a "marca" do tema)

O overlay ganhou um **contrato de marca**: recebe os *tokens* do tema que o painel
mediu e pinta a legenda nativa com a **mesma** cara do painel. **NÃO HÁ REMETENTE**
(`app/panel/brand-bridge.js` não existe e o `panel.js` não emite `brand-tokens`),
portanto a via da marca está **inerte** — e o `_THEME_DEFAULT` reproduz o
comportamento antigo **exactamente** (Segoe UI, 34 px, `rgb(245,248,252)`, caneta
preta de 6 px), que é o que o portão mede. `py_compile` passa.

**O QUE NÃO FOI MEDIDO:** a via da marca (nenhum tema chega), e o desenho em si —
o portão mede **as linhas e as larguras**, não os pixels.

## 5. O QUE **NÃO** FOI MEDIDO

- **O que o ecrã mostra.** Isto mede as LINHAS e as LARGURAS com as métricas
  reais da fonte; não há fotografia do overlay (e uma foto desta máquina tem o
  limite de viewport de 492 px, que não responde a coordenadas).
- **A posição e o tamanho da janela da legenda** (o `caption_overlay` continua a
  por a sua conta).
- **O caminho do `caption.html`** (o documento de legenda, usado quando não há
  janela nativa): o CSS de lá foi arrumado por outra via e não é o que este
  portão mede.
