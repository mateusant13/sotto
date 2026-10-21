# Recibo — o gesto do Alt+C à velocidade humana (2026-10-21)

**O DONO, verbatim (2026-10-21):**
> *"alt c nao ta funcionando direito pra abrir o painel e etc. um alt c: ativa ou
> desativa legenda ao vivo. dois: abre o painel de baixo. tres: abre o painel da
> direita. to resumindo mas deve ter regras pra melhor ux disso. pode implementar
> uma versao melhor se tu achar algo melhor"*

**O GESTO JÁ EXISTIA** (contrato do dono de 2026-10-18) e continua o mesmo:
**1** pressão → legenda ao vivo on/off · **2** → painel de baixo (`show_strip`) ·
**3** → painel da direita (`show_side`). O que faltava era a **VELOCIDADE**.

---

## 1. O DEFEITO, MEDIDO NO APP DO DONO A CORRER

**INSTRUMENTO:** `WM_HOTKEY` **reais** posto na fila da thread do hotkey do shell
vivo (a técnica de `_main/_audit-hotkey-delivery.py`), lidos do **log da própria
app** (`_main/webview-run.log`). Nenhuma tecla foi simulada, nenhuma janela
aberta, o processo do dono foi o que respondeu. O script de medição é
`G:\Temp\opencode\gesture-measure.py` (fora do repo: é um instrumento de uma
sessão, não uma peça do produto).

**ANTES (2026-10-21 01:0x, shell com `HOTKEY_DOUBLE_MS = 250`):**

| gesto | o que disparou |
|---|---|
| 1 pressão | legenda off — **certo** |
| 2 pressões, 120 ms | legenda descartada + `PANEL_SHOWN mode=strip` — **certo** |
| **2 pressões, 400 ms** | **legenda on, legenda off → NADA ACONTECEU** |
| 2 pressões, 700 ms | legenda on, legenda off → NADA ACONTECEU |
| 3 pressões, 120 ms | legenda descartada + `PANEL_SHOWN mode=side` — **certo** |
| **3 pressões, 400 ms** | **legenda on/off/on → a acção ERRADA** |

**A CAUSA:** `HOTKEY_DOUBLE_MS = 250` governava **DUAS** coisas — o quanto uma
pressão **espera** pela legenda **e** o quanto uma pressão ainda conta como o
**mesmo gesto**. Um duplo-clique humano mede **300-500 ms**: fora dos 250, as
duas pressões eram **dois gestos**, a legenda ligava e desligava e o **painel
nunca abria**.

## 2. A CORRECÇÃO

**DOIS RELÓGIOS, UM NÚMERO DE HUMANO.**

| constante | valor | o que é |
|---|---|---|
| `HOTKEY_CAPTION_DEFER_MS` | **250** (inalterado) | quanto uma pressão **sozinha** espera pela legenda |
| `HOTKEY_GESTURE_MS` | **700** (novo) | quanto uma pressão ainda pertence ao **mesmo gesto** |

700 ms é um número **humano**: um duplo-clique deliberado mede 300-500 ms, logo
700 reconhece-o sem engolir a pressão deliberada seguinte.

**E A LEGENDA É DESFEITA** quando o gesto se revela um painel — a regra do dono,
verbatim: *"caso double alt c, a legenda nao habilita"*. Como o atraso da
legenda (250) é **mais curto** que a janela do gesto (700), a primeira pressão de
um duplo **humano** já pode ter ligado a legenda quando a segunda chega; por
isso `_undo_gesture_caption()` a **restaura ao estado anterior**, guardado por
`_caption_gesture_id` (um gesto antigo nunca desfaz a legenda de um gesto novo) e
`_caption_restore`.

**FICHEIROS:** `app/webview/sotto_webview.py` (constantes em `:1441-1442`,
`hotkey_pressed` em `:7789`, `_undo_gesture_caption` em `:7923`).

## 3. DEPOIS, MEDIDO NO APP DO DONO A CORRER (shell novo, pid 19624)

| gesto | o que disparou | veredicto |
|---|---|---|
| 1 pressão | `caption=true` | **certo** |
| 2 pressões, 120 ms | legenda descartada + `PANEL_SHOWN:strip` | **certo** |
| **2 pressões, 400 ms** | **`caption=false` + `PANEL_SHOWN:strip`** | **O QUE FALTAVA** |
| 2 pressões, 700 ms | `caption=false, caption=true` | fronteira da janela (700) |
| 3 pressões, 120 ms | legenda descartada + `PANEL_SHOWN:side` | **certo** |
| **3 pressões, 400 ms** | **`caption=false` + `PANEL_SHOWN:side`** | **O QUE FALTAVA** |

**O LOG DA APP, LINHA A LINHA (o duplo humano):**
```
01:21:08.004 sotto: HOTKEY_SINGLE caption_on=false after_ms=250
01:21:08.150 sotto: HOTKEY_CAPTION_UNDONE caption_on=true reason=gesture-is-a-panel
01:21:08.855 sotto: HOTKEY_DOUBLE panel=strip after_ms=700
01:21:08.921 sotto: PANEL_SHOWN reason=hotkey-double mode=strip visible=true
```

**O TRIPLO HUMANO:**
```
01:21:12.952 sotto: HOTKEY_SINGLE caption_on=false after_ms=250
01:21:13.094 sotto: HOTKEY_CAPTION_UNDONE caption_on=true reason=gesture-is-a-panel
01:21:13.565 sotto: PANEL_SHOWN reason=hotkey-triple mode=side visible=true
```

O `HOTKEY_CAPTION_UNDONE` **restaura o estado anterior** (`caption_on=true` = o
que estava antes do gesto) — a legenda fica **desligada** por um duplo, como o
dono mandou.

## 4. OS PORTÕES (todos verdes, e todos com o braço negativo)

| portão | comando | resultado |
|---|---|---|
| gesto | `python _main/hotkey-gesture-oracle.py` | **14/14 GREEN** |
| ciclo | `python _main/hotkey-cycle-oracle.py` | **VERDICT: PASS** |
| triplo | `python _main/hotkey-triple-oracle.py` | **30/30 GREEN, 9/9 mutantes apanhados** |

**O que cada um mede, depois de re-ancorado (2026-10-21):** o `gesture` extrai
`_hotkey_single` e `hotkey_pressed` do ficheiro **vivo** com `ast` e executa-os;
o `cycle` prova a **JANELA** comportamentalmente (120 ms = um gesto, **400 ms = um
gesto**, 900 ms = dois); o `triplo` tem os braços `double_fast`, `double_human`,
`double_wide`, `triple_fast`, `triple_human`, `quad_fast`, `lone_then_double` e
**9 mutantes** (M1 limiar do triplo, M2 o triplo pinta a faixa, M3 a legenda
pendente não é retirada, M4 o duplo volta a ser imediato, M5 o gesto nunca fecha,
M6 a janela é por gesto e não por pressão, M7 a janela do gesto volta a ser o
atraso da legenda, M8 a legenda não é desfeita, M9 o desfazer ignora o id do
gesto) — **todos apanhados**.

**TRÊS ÂNCORAS GASTAS QUE FOI PRECISO RE-ANCORAR** (não afrouxar): o `gesture` lia
`HOTKEY_DOUBLE_MS` (que deixou de existir) e injectava-o no espaço de nomes; o
`cycle` lia a mesma constante e esperava **400 ms = dois gestos** (que era
exatamente o defeito); o `triple` tinha um mutante cuja âncora deixava uma linha
indentada pendurada e **partia o próprio portão** com `IndentationError`.

## 5. PINS

| ficheiro | bytes | EOL | sha256 (16) |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 728 566 | CRLF 13 891 / bareLF 0 | `D82FDB0C84C9EAEA` |
| `_main/hotkey-gesture-oracle.py` | 6 182 | CRLF 0 / bareLF 153 | `8B489CD520179480` |
| `_main/hotkey-cycle-oracle.py` | 30 404 | CRLF 0 / bareLF 724 | `12D19A709E0593E7` |
| `_main/hotkey-triple-oracle.py` | 18 725 | CRLF 0 / bareLF 460 | `8FC2379304C0FAB5` |
| `_main/receipt-20261021-hotkey-gesture.md` | 6 951 | CRLF 0 / bareLF 137 | `D2A87001463636B4` |

## 6. O QUE **NÃO** FOI MEDIDO

- **O painel e a legenda ao vivo em simultâneo, com o owner a ver**: o gesto foi
  medido pelo log da app, que é a mesma evidência que o dono vê, mas **nada foi
  fotografado** (e uma foto desta máquina tem o limite do viewport de 492 px).
- **O comportamento com OUTRO programa a possuir o Alt+C** (a cadeia de fallback):
  o `hotkey-delivery` da bateria foi **SKIPPED** nesta corrida porque o app do
  dono detém o Alt+C — o instrumento diz isso alto, como deve.
- **A reacção a um duplo-clique ainda mais lento** (700 ms é a fronteira; acima
  dela são dois gestos, por desenho).
