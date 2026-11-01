# RECIBO — `lane-screen-gate` e a lei `SOTTO_NEVER_ON_OWNER_SCREEN`

**Data:** 2026-10-24 (madrugada; a ordem é de 2026-10-23, 23:2x)
**Estado:** `fixed`. **NÃO** `verified` — ver a última secção.

## A ordem, verbatim

> *"para de abrir essa merda na minha tela. tu vai resolver no teu ambiente ai sem encher o meu saco"*

E, depois de eu lhe mostrar que a app tem seams próprios (`--show`, `panel_state.py --read`):

> *"entao nunca mais faz isso. faz gates ou agents.md"*

## O que aconteceu, sem embelezar

1. A app foi lançada com `--show` e o painel ficou no ecrã dele enquanto ele trabalhava —
   `PANEL_VISIBILITY_ON_SCREEN visible=true` no log, às 23:22:38.
2. Antes disso, `_main/press-alt-c.py` disparou `keybd_event` quatro vezes como "teste". Os quatro
   `err=0` provam que o **Windows** aceitou as teclas; as **zero** linhas no log do Sotto provam que
   o **Sotto nunca as viu**. O instrumento media o sistema operativo, não a app.
3. Nada no repo impedia a repetição. É esse buraco que este recibo fecha.

## O instrumento

`_main/lane-screen-gate.py` — julga ficheiros, **lança nada**. Três braços:

| braço | fica vermelho quando |
|---|---|
| `synthetic-input` | um instrumento de nível 1 de `_main` **acrescenta** `keybd_event` / `SendInput` / `mouse_event` / `SendKeys` / `BlockInput` |
| `lane-launcher-visible` | um harness de lane (`keepalive*`, `*lane*`, `launch*`, `press*`) pede `--show` |
| `agents-rule` | `AGENTS.md` deixa de conter o marcador `SOTTO_NEVER_ON_OWNER_SCREEN` |

O detector lê **código**, não comentários (`code_lines`). A razão é medida: a primeira versão contava
comentários e punha vermelho o `keepalive.py` — o único ficheiro que **cumpria** a lei, por a
documentar. Quem documenta a regra não pode ser tratado como quem a quebra.

## A dívida antiga, congelada

`_main/lane-screen-baseline.json`: **13** instrumentos com input sintético e **2** harnesses com
`--show`, com a contagem de cada um. Não é perdão, é contagem: um ficheiro fora da lista, ou uma
contagem que cresça, fica vermelho. Apagá-los seria reescrever a história para o portão ficar bonito.

## O braço negativo (a prova de que o detector detecta)

```
control (limpo)                     -> VERDE
M1 keybd_event novo                 -> VERMELHO
M2 harness com --show               -> VERMELHO
M3 marcador apagado do AGENTS.md    -> VERMELHO
M4 ficheiro do baseline a CRESCER   -> VERMELHO
NEG-ARM PASS: 4 mutantes, todos apanhados     (rc=1 POR DESENHO)
```

## Ligação à bateria

`_main\_audit-verify-all.cmd`, logo a seguir ao `border-radius-gate`:

```
call :step lane-screen-gate 0 ...                  -> rc=0  BATTERY-VERDICT PASS
call :step red-as-expected-lane-screen-gate 1 ...  -> rc=1  NEG-ARM PASS
```

## Pin do `.cmd`, re-medido (a lei do arquivo)

| | antes | depois |
|---|---|---|
| bytes | 108675 | **110748** |
| CRLF | 1464 | **1491** |
| bare LF | 0 | **0** |
| sha256 | `9A3925DF…2E08` | **`71B6A090909995C12EF4AC0D3EAB65F9AC61E60A0C4A5E70A17A756F5B384559`** |

`AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.

## Limpeza das minhas próprias violações

- `_main/press-alt-c.py` e `_main/altc-press.log` — **apagados**;
- tarefa `Sotto_PressAltC` — **eliminada**;
- `_main/keepalive.py` — já não pede `--show`; arranca a app **escondida** (o estado em que ela
  escreve `panel-state.json` e o log) e recusa sem `SOTTO_LANE_LAUNCH=1`, escrevendo porquê;
- app **fechada**, `janelas do Sotto visiveis = 0`.

## O que NÃO está verificado

- **A corrida completa da bateria, feita em 2026-10-24** (`SOTTO_BATTERY_FAST=1`, `heavy` OFF):
  **`BATTERY-VERDICT: RED - 6 step(s) failed`**, exit 1. O portão novo **passou dentro dela**:
  `lane-screen-gate rc=0` e `red-as-expected-lane-screen-gate rc=1 [EXPECT-RED] the defect was found
  and named`.
- As 6 falhas, com dono atribuído — três depois de a primeira ser corrigida:

| passo | dono | estado |
|---|---|---|
| `panel-flash-contradiction` + controlo | **MEU** (o corte de `AGENTS.md` 748→205 de 2026-10-21 apagou a nota da contradição) | **corrigido nesta sessão**: `VERDICT: PASS`, neg-arm `flipped=['gate','visible']` |
| `exception-hygiene` | **OUTRA LANE** — `worker/sotto_worker.py` `git diff` = **+139/−2**, `except` 7→8, total 40→41 | vermelho por desenho do ratchet; **não toquei** |
| `code-health` | **MEU** em `app/webview/sotto_webview.py` **e** outra lane no worker | vermelho por desenho do ratchet; **não subi a linha de base** |

### O `code-health` e a troca que eu escolhi (2026-10-24)

| indicador | início da sessão | agora |
|---|---|---|
| bytes (`sotto_webview.py`) | 767283 (+8604) | **767928 (+9249)** |
| linhas | 14592 (+168) | **14604 (+180)** |
| `except_pass` | 23 (+1) | **22 — de volta à base** |
| métricas pioradas | 9 | **8** |

Três mudanças, todas com prova:

1. **A regra do B5 saiu do ficheiro grande** para `youtube_window.collapse_growth` (onde já vive
   `live_lines`), com os casos medidos no docstring — `−953 B / −19 linhas`. `youtube-window-oracle`
   **PASS 12/12**; casos do dono: `["O radio","O radio Segunda"] -> ['O radio Segunda']`,
   `["What?",">> What?"] -> ['What?', '>> What?']`, `["fine.","fine."] -> ['fine.']`.
2. **Dois `except: pass` meus passaram a dizer o que falhou** (`MOUSE_HOOK_UNHOOK_FAILED`,
   `UI_WATCHDOG_FLUSH_FAILED`) — engolir erro no desmonte do hook ou no flush do watchdog é o que o
   `exception-hygiene` existe para travar. `except_pass` volta à base: 22.
3. **A duplicação do B5, curada no sítio onde fica GRAVADA**: `history_append` recusa uma linha igual
   à última (`HISTORY_DUPLICATE_SKIPPED`) e a comparação tira a hora e a proveniência
   (`_history_last_body`). Prova, com um duplo e um ficheiro real:

   | sequência | resultado |
   |---|---|
   | 1.ª escrita | entrou |
   | a MESMA linha logo a seguir | **RECUSADA** |
   | frase diferente | entrou |
   | a mesma, depois de outra | entrou (não é censura, é repetição imediata) |
   | vazia / `provisional-draft` | recusadas (a invariante de 2026-10-06 continua) |
   | linhas no ficheiro | **3 de 3 esperadas** |

   Oráculos vizinhos verdes: `transcript-append-oracle` **rc=0**, `live-vs-history-source` **rc=0**,
   `history-producer-gate` **rc=0**, `ui-watchdog-oracle` **rc=0**.

**A troca, dita em voz alta:** a cura da duplicação **acrescenta** ~1300 B / 12 linhas ao ficheiro
ratcheado. Escolhi a queixa do dono em vez do indicador — o contrário seria ficar verde por não
corrigir. O resto não é redutível sem decisão dele: o cabeçalho do oráculo diz que `--update` é "só
com o dono de acordo", e mexer nele absorveria também o crescimento **de outra lane**
(`worker/sotto_worker.py`, +1142 B). Dois donos numa linha de base é como se perde a conta.
| `strip-hot-reload` | ninguém — `_main/_strip-reload-probe.py` corre a mão com **rc=0** | `rc=3` dentro da bateria (carga: 936 processos) — **não estabilizado**, fica declarado |

- **`verified` continua impossível de uma lane**: sem verificador independente, o ledger imprime
  `FIXED, NOT VERIFIED`.
