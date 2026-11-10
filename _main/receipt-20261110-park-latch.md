# RECIBO — o latch que um `return` gastava (parque do motor, 2026-11-10)

Card do dono: **"PC em silêncio: Ctrl+Space NÃO desaparece, legenda congelada para sempre; áudio
volta e nada acontece"**. Tudo abaixo foi medido nesta árvore e no log dele; o comando está ao lado
de cada número.

## 1. O defeito, no código e no disco

`app/webview/sotto_webview.py:on_external_captions_released` — a sequência de HEAD:

```
self._external_parked = False          # o latch é CONSUMIDO
if self._paused:                       return False
if not (self.visible or self._caption_window_shown): return False
...
if self.engine_park_reason() == 'captions':
    self.set_engine_park(None)         # <- nunca alcançado nos dois casos acima
```

O release é de **borda** (o watcher do player avisa **uma vez**). Um `return` nas duas guardas
gastava a única oportunidade: a chamada seguinte morria em `if not self._external_parked: return
False`. O pedido de parque ficava escrito para sempre.

Medido no estado em disco da sessão dele (`panel-visibility.json`, último write **21:36:12**):
`"park": "captions"` com `"visible": false`, reimpresso a cada 3 s, e `staleAfterSeconds=9.0`
**nunca** a expirar — o ficheiro nunca ficava velho porque o worker o reescrevia.

Contagem no log da sessão (`_main/webview-run.log`, 187 339 linhas):

| evento | ocorrências |
|---|---|
| `ENGINE_PARK reason=` | **16** |
| `EXTERNAL_CAPTIONS_ENGINE_RESUMED` | **1** |

O worker, com o ficheiro a dizer `captions`, segura a tap por **624 s** de cada vez
(12+24+48+60×9; o ciclo anterior do mesmo log mediu **625,8 s**), e o motor nunca volta. As palavras
dele: *"a legenda congela e nunca volta"* · *"o áudio volta e nada acontece"*.

## 2. A cura

O parque é do **MOTOR**, não da janela. A pausa e a visibilidade desligam o **DISPLAY** (regra 3 do
`AGENTS.md`: *"legenda ao vivo desativada não significa que o modelo está desativado"*), nunca o
pedido de parque — limpar o pedido é **uma escrita num ficheiro, custo zero**.

- O latch é consumido **depois** das guardas que sobrevivem (`exiting`), e o pedido `captions` é
  limpo **independentemente** de `_paused`/visibilidade.
- Só o motivo `captions` sai daqui: o parque por **VRAM** tem outro dono e continua de pé.
- A linha passou a nomear o estado que decidiu: `EXTERNAL_CAPTIONS_ENGINE_RESUMED reason=player-stopped
  mode=engine-not-process paused=… visible=…`.

## 3. A cura RECUSADA, e por quê

O forense (`_main/scout-20261110-live-caption-stuck.md`, Q7) propôs que o ramo do parque do worker
perguntasse ao medidor vivo (`_live_render_peaks`) se algum endpoint voltou a tocar e terminasse o
*hold*. **O contrato que ele citou (`worker/sotto_worker.py:2180`, "qualquer endpoint acima do piso →
`None`") é o do `silent_desktop_hold` — o caminho da máquina CALADA, não o do parque.** Com o player
a fornecer legenda o áudio **está** a tocar: a guarda terminaria o hold em todas as janelas e a
escada voltaria a abrir um cliente WASAPI por janela — o defeito de **46 rotações em 11 minutos** que
o hold existe para curar. Aplicado e **revertido** no mesmo turno (`git checkout -- worker/sotto_worker.py`);
o número de que ele precisava é o do §1, e esse estava do lado da shell.

## 4. Portão

`_main/external-resume-latch-oracle.py` — executa a **função real**, extraída por `ast` do ficheiro
que embarca, sobre um shell falso:

| arm | o que exige |
|---|---|
| A1 | release com painel **e** overlay escondidos → parque limpo (o caso do dono) |
| A2 | release com `_paused` → parque limpo (regra 3) |
| A3 | sem pedido pendente → `False`, **zero** escritas |
| A4 | parque de **VRAM** não é libertado por um release de legendas |
| A5 | shell a sair → `False`, zero escritas, **latch intacto**, linha `…RESUME_SKIPPED` |
| A6 | o espelho da pausa é limpo em **todos** os caminhos |
| A7 | a linha de sucesso nomeia `paused=` e `visible=` |

Medido: `LATCH-ORACLE VERDICT: PASS (7/7)` rc=0. Negativo cirúrgico (as duas guardas de HEAD
repostas **na função extraída**, nunca "o ficheiro de HEAD", que apodrece no dia em que a cura é
cometida): `NEG-ARM: PASS -- mutante apanhado por 3 arm(s)` rc=1.

Na bateria: `external-resume-latch` + `red-as-expected-external-resume-latch`
(`battery-wiring` PASS `ligados=182 sem_passo=108 populacao=290`;
`battery-record-pairing` 448 passos / 448 nomes / 0 achados).

## 5. O portão que já estava vermelho, e que este trabalho reparou

`_main/external-resume-oracle.py` (o dono do invariante até hoje) morria desde 2026-11-09 com
`AttributeError: 'Stub' object has no attribute '_clear_yt_source_mirrors'` — o `Stub` não
acompanhou a cura do espelho da pausa. Os braços E3/E4/E5/E8/E9 dele fixavam exactamente as guardas
que esta cura remove, então eles **saíram** (um invariante, um portão dono: o release pertence ao
oráculo novo) junto com os três mutantes cuja âncora deixou de existir. Ficou com o **parque**, a
**retomada por VRAM** e a **graça do guarda**:

```
bracos: 14 verdes, 0 vermelhos          EXTERNAL-RESUME VERDICT PASS        rc=0
NEG-ARM 7 of 7 mutant(s) caught         NEG-ARM PASS                        rc=1
```

## 6. O que NÃO está verificado

- **`verified` continua impossível de uma lane**: a prova é o oráculo sobre a função real, não uma
  corrida da app na tela dele. O que este recibo afirma é `fixed, NOT verified` — a próxima sessão
  dele tem de mostrar `EXTERNAL_CAPTIONS_ENGINE_RESUMED` a seguir a um release com o painel
  escondido, e o `panel-visibility.json` a deixar de dizer `"park": "captions"`.
- Se o `_external_parked` desta sessão chegou a `False` antes do fim: `[INFERENCE]` (não há log desse
  campo; a armadilha de código é certa, a ocorrência é inferida da contagem 16:1 do §1).
- O endpoint aberto às 21:33:42.456 e o routing físico do áudio (`peak` ficou `0.0`, silêncio
  digital): fora do escopo deste card — o forense deixou-os como `[INFERENCE]`.
