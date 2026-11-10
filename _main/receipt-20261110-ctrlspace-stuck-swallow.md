# RECIBO — o estado preso que engolia o `Ctrl+Space` para sempre (2026-11-10)

Card do dono: **"Ctrl+Space BUGADO: preciso de activate -> alt c -> alt c off/on para a legenda
funcionar"**. Medido nesta árvore; o comando está ao lado de cada número.

## 1. O defeito

`app/webview/space_swallow.py`, predicado puro `classify_event`:

```
if vk == target_vk and (mods_down & required_mods) == required_mods:
    return 'swallow', True, not key_down_swallowed
```

`key_down_swallowed` só devia estar `True` entre o `keydown` e o `keyup` **da mesma tecla**. Se o
hook é instalado a meio de uma pressão, ou o `keyup` se perde, o estado fica preso: `not
key_down_swallowed` passa a ser **sempre `False`**, cada pressão seguinte é **engolida e nunca
alterna**, e nada no log o diz — indistinguível de um hook morto. O `Ctrl+Space` some do Windows *e*
a legenda não muda, que é exactamente a borda que ele descreveu.

Evidência de que a tecla ficou muda sem rasto (`_main/scout-20261110-live-caption-stuck.md`, Q2, sobre
`_main/webview-run.log`, **187 339** linhas):

| linha | ocorrências |
|---|---|
| `HOTKEY_PRESSED role=live` (última: 21:16:08.483) | — |
| `HOTKEY_OBSERVER_ALIVE` | **0** |
| `SPACE_SWALLOW_*` a dizer que uma pressão foi engolida sem alternar | **0** (não existia) |

O hook estava instalado e armado (`swallow=true hook=true registered=true`) e não deixou uma linha
desde as 21:16.

## 2. A cura

Duas metades, as duas baratas:

1. **A TESTEMUNHA É O TEMPO, não o bit físico.** Medido: a primeira versão desta cura lia
   `GetAsyncKeyState` e exigia "tecla em cima" para desmentir o estado — mas **um `keydown` chega
   sempre com a tecla em baixo**, portanto essa leitura dava `False` **zero vezes** no instante que
   importa (o braço B2e apanhou-o). Agora o estado carrega o instante em que nasceu (`_swallowed_at`,
   relógio injectável) e um `keydown` com o estado de pé há mais de **`STUCK_HELD_S = 3.0 s`** sem
   `keyup` é uma pressão **nova**: alterna. Um auto-repeat real chega a cada ~30 ms, logo a repetição
   legítima continua a não alternar (B2b/B2f provam as duas metades).
2. **O silêncio acaba.** Uma pressão engolida sem alternar escreve `SPACE_SWALLOW_REPEAT` (contagens
   1/10/100 e cada 1000) e o reset escreve `SPACE_SWALLOW_STATE_RESET … resets=N
   why=key-up-was-lost-while-swallowing`. Uma tecla que engole e não alterna deixa de ser
   indistinguível de um hook morto.

## 3. Portão

`_main/ctrlspace-swallow-oracle.py` — o fio **REAL** (`LiveHotkeyThread`), o predicado **REAL** e um
`user32` gravador; nenhum hook é instalado e nenhuma tecla é injectada no sistema.

| arm | o que exige |
|---|---|
| B2 | `keydown` com Ctrl engolido e alterna **uma** vez |
| B2b | auto-repeat imediato: engolido, **não** alterna outra vez |
| B2c | o `keyup` da tecla engolida também sai, e fecha o estado |
| **B2e** | **estado preso (10 s sem `keyup`): a pressão nova ALTERNA e `state_resets` sobe** |
| B2f | a repetição seguinte, com a tecla em baixo, é auto-repeat de novo (o estado não fica a alternar para sempre) |
| B2d | um `WM_HOTKEY` atrasado não duplica a alternância |

Medido: `CTRLSPACE-SWALLOW VERDICT: PASS (21/21)` rc=0. O negativo ganhou o mutante
`sem-cura-do-estado-preso` (o ramo removido numa **cópia**) ao lado dos seis que já existiam.

Duas correcções de instrumento vieram com o braço: o `user32` gravador não modelava a **tecla
física** (devolvia `0` para tudo fora dos modificadores), e o `press_combo` passou a entregar o
`keydown` com a tecla em baixo e o `keyup` depois de a soltar — a mesma ordem que o Windows usa.

## 4. O que NÃO está curado por este recibo

- **A outra metade do card** — a legenda congelada no ecrã — tem causa **diferente** e não está
  fechada: o forense apontou `_caption_idle_hide` a desistir em silêncio com
  `_caption_window_shown` falso, mas a leitura do código mostra que `push_caption_to_window` **repõe**
  essa bandeira ao empurrar (é esta mesma lane que o leu em `sotto_webview.py:17728`), e o número que
  provaria o contrário não foi medido. Fica `[INFERENCE]`; não se cura uma hipótese.
- **`verified` continua impossível de uma lane.** A prova é o oráculo sobre o código que embarca, não
  uma corrida na tela dele: este recibo diz `fixed, NOT verified`. A próxima sessão dele tem de
  mostrar `SPACE_SWALLOW_STATE_RESET` (se o estado prender) e `HOTKEY_PRESSED role=live` a cada
  pressão.
