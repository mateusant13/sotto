# 2026-11-24 — stutter card `dm-dab7ea056465d2fea48d`: o caminho tem nome, e ele já está demovido

Card do watcher (ordem do dono, verbatim): *"acabou de acontecer stutter. culpa de quem? é pra
sempre verificar o maior culpado do stutter"*. Culprit: `pythonw.exe(11608)` = a shell do Sotto,
carrier `python.exe(9364)` = o worker. **Confirmei a atribuição** (`cmdline` = 
`H:\sotto\app\webview\sotto_webview.py --log ... --ready-file ...`, criado 14:17:40, e
`worker/sotto_worker.py` como filho). A árvore é minha; o card é meu.

## 1. O caminho, `file:line`

`worker/sotto_worker.py:7636` — `load_mode = _enter_load_background_mode()` antes de
`StreamAsr(...)` (a construção das três `InferenceSession`), fechado por
`_end_load_window()` quando as sessões estão prontas. O peso lido é
`worker/models/nemotron-3.5-asr-ptbr-onnx-int4/encoder.onnx.data` = **690 089 984 B**
(o modelo vivo completo tem 760 MB; o `parakeet-redux` de 743 MB é o motor de fundo, não
entra nesta carga).

A janela de fundo é **CAPADA em `LOAD_BG_MAX_S = 0.75` s** (`worker/sotto_worker.py:6825`), e
o motivo está escrito no próprio ficheiro, medido em 2026-11-05: em
`PROCESS_MODE_BACKGROUND_BEGIN` a carga custa **19,3× de parede** (o `og.Model` passa de 2,64 s
para 9,04 s, e houve braço a 35,88 s) porque o modo baixa a CPU a IDLE e o I/O a VeryLow.
Passados 0,75 s o processo volta a `BELOW_NORMAL` — CPU demovida, **I/O normal**.

## 2. O que medi agora (mesmo instrumento, processo meu)

`GetPriorityClass` do worker, amostrado a 0,25 s durante a carga:

```
t=  0.0s class=0x000020 NORMAL
t=  0.3s class=0x004000 BELOW_NORMAL
t= 19.1s class=0x000020 NORMAL     (fim do run)
```

Ou seja: **a CPU está demovida desde os 0,3 s**, e a janela de I/O VeryLow existe só nos
primeiros 0,75 s. Não afirmo que a janela correu nesse intervalo: `GetPriorityClass` devolve a
classe, não o modo — o que este instrumento prova é a classe.

## 3. A aritmética do episódio

O watcher mediu `over_line = 83,7 s/h` acima da linha de 20 MB/s.
`83,7 × 20 MB/s ≈ 1,67 GB` ≈ **duas cargas frias** de 760 MB. E há **duas** linhas
`BRIDGE_SPAWNED` naquela hora: `13:38:43` (pid 56108) e `13:39:27` (pid 51584) — a primeira
carga foi o arranque da app, a segunda foi o **respawn causado pela cunha da tap** que esta lane
curou no commit `a19ca9666e` (`meter-blind-starved`).

Estado de HOJE, mesma árvore, 5 s de `io_counters`: worker `write=0,70 MB/s`, shell
`other=0,82 MB/s`; ficheiros escritos em 180 s: **4** (`webview-run.log` +1,4 KB/s,
`panel-state.json`, `panel-visibility.json`, `.steady-watcher.json`). A árvore está **~25×
abaixo** da linha de 20 MB/s.

## 4. Porque NÃO proponho subir o teto de 0,75 s

Seriam 8-14 s (ou 160 s, pelo 19,3× medido) de carga a IDLE para esconder 690 MB de leitura
uma vez por arranque — o próprio ficheiro documenta que essa troca foi rejeitada com números em
2026-11-05. A cura do episódio é **menos spawns**, e ela já está landada.

## 5. Duas hipóteses testadas e RECUSADAS (medidas, não supostas)

* **`panel-state.json` reescrito a cada segundo sem mudar** — FALSO: 9 amostras em 4 s com
  sha256 **idêntico** (`10ed65e820ce`), tamanho 6 807 B. O escritor publica um *heartbeat*
  (`sequence`/`writtenAt`, `durable=False` desde 2026-11-23) e é isso que dá idade ao ficheiro.
  Não há trabalho repetido a cortar.
* **`webview-run.log` sem rotação** — 37 MB e +1,4 KB/s = 5 MB/h, sem sinal de I/O. É limpeza
  de disco, não custo de stutter; não entra como cura de performance.

## 6. Custo declarado

Uma carga de modelo quente (o mesmo instrumento do §2), atrás de
`watcher run --cpu 40 --single --io very-low`: 1 processo, 3 threads, RSS ≤ 2,2 GiB,
leitura ≤ 1,7 GB, ≤ 45 s de parede. Nada mais correu em paralelo.
