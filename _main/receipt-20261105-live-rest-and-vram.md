# Recibo — carga e memoria da instancia VIVA, com o codigo de hoje (2026-11-05, 19:0x)

Instrumentos: `_main/shell-thread-cpu.py <pid>` (Toolhelp32 + `GetThreadTimes` +
`GetThreadDescription`), `nvidia-smi`, `Get-Process`, e o proprio log da shell.
Tudo read-only; nenhum dispositivo de audio aberto, nada lancado na tela do dono.

## A INSTANCIA

    pid 20288  pythonw  (shell)   pid 31348  python  (worker)
    janela: 18:57:10 -> 19:0x, painel ESCONDIDO, legenda ao vivo DESLIGADA
            (`CAPTION_WANTED_RESTORED on=false`), YouTube a tocar
            (`YOUTUBE_TICK_MS ... vid='ea20SBGR8ao' rows=1 why='painted' hz=3.9`)

## CPU (o numero que o dono pediu)

| quem | janela | CPU de UM nucleo | maiores fios |
|---|---|---|---|
| shell (20288) | 8,1 s | **1,2 %** | `sotto-gaming-mode` 1,0 %, `yt-cdp-source` 0,2 % |
| shell (20288) | 30,1 s | **3,7 %** | `sotto-batch-executor` 1,7 %, `yt-cdp-source` 0,6 %, `sotto-hotkey-live-swallow` 0,2 %, `sotto-external-captions` 0,2 % |
| worker (31348) | 8,1 s | **2,5 %** | quatro fios sem nome (0,12 / 0,05 / 0,02 / 0,02 s) |

A janela de 8 s e a de 30 s nao concordam sobre QUEM e' o primeiro, e isso e' a
propria informacao: `sotto-gaming-mode` (8 s) e `sotto-batch-executor` (30 s) sao
dois tickers de 10 s que caem em janelas diferentes. Nenhum dos dois e' o laco da
legenda. A soma das duas janelas fica **entre 1,2 % e 3,7 %**, contra os 23,4 %
de um nucleo que a mesma maquina media no inicio da sessao com o video parado.

## MEMORIA

| processo | working set | privado |
|---|---|---|
| shell 20288 | 172 MB | **134 MB** |
| worker 31348 | 1 574 MB | **3 390 MB** |
| VRAM livre | — | 9 690 MiB de 16 303 |

`BRIDGE_RSS rss_mb=1091.5 private_mb=2883.9` e' a mesma grandeza lida pelo worker
nesta sessao, e ela e' **constante** em 2,5 min (2883.8 -> 2883.8): nao e' fuga.

## O GUARDA DE VRAM, medido na instancia viva (a cura de hoje)

    18:57:22  VRAM_GUARD_PARKING  free_mb=393  pid=31348  mode=engine-not-process
    18:59:10  VRAM_GUARD_RESUMING free_mb=13643 mode=engine-not-process showing=False

**UM parque e UMA retomada em ~13 min**, contra 21 parques e 6 retomadas no mesmo
dia com `resume_mb=2400`. A retomada aconteceu com `showing=False` (a cura E13: a
visibilidade decide o que recarregar, nunca se o pedido se levanta) e com
`resume_mb=3200` (a invariante E18: `RESUME = LOW + MODEL_VRAM`), ou seja a volta
deixou >= 1200 MB livres e o parque seguinte **nao** era garantido por conta.

## O QUE O PARQUE FAZ, LIDO NO CODIGO (nao medido)

`set_engine_park('vram')` -> `park` no `panel-visibility.json` ->
`EngineSwitch.park()` -> `shed = muito-alta` -> `mode='shed'` ->
`_release_engine('shed-muito-alta')` (worker/engine_switch.py:712-780). A
mensagem que o painel mostra diz "the transcription engines were unloaded to free
their VRAM".

## O QUE O PARQUE LARGA, LIDO NO CODIGO — e a correccao que ele pediu

`park='vram'` -> `shed='muito-alta'` -> `mode='shed'` -> `_release_engine()` ->
`ParakeetEngine.release()` (`worker/engine_policy.py:223`), que JA' publica a
medicao: `REDUX_ENGINE_RELEASED engine=.. reason=.. rss_before_mb=.. rss_after_mb=..`.
Foi um erro meu dizer que a medicao nao existia: ela existia, **mas nao chegava a
log nenhum** — o `_pump` do shell guarda as linhas de stderr do worker num anel de
40 (`stderr_tail`) e so' as despeja na cauda da MORTE. Ou seja:

- o painel diz ao dono *"the transcription engines were unloaded to free their VRAM"*;
- a unica prova disso vivia num buffer que se le' depois de o worker morrer;
- e o `REDUX_SHEDDING`/`REDUX_MODE` do interruptor idem.

**A CURA, landada agora** (`app/webview/sotto_webview.py`): `ENGINE_VISIBLE_TAGS`
(`REDUX_ENGINE_RELEASED`, `REDUX_ENGINE_RELEASE_FAILED`, `REDUX_ENGINE_LOAD`,
`REDUX_SHEDDING`) passa a sair no log do shell por `log_repeat(..., every_s=30)`,
DENTRO do bloco de stderr e antes do `continue` que o fecha (o mesmo `continue` que
ja' custou uma tarde ao `BRIDGE_ALIVE`). O oraculo `_main/death-cause-oracle.py`
ganhou as arms **F** (a linha chega ao log) e **G** (uma linha fora da lista NAO e'
encaminhada — o controlo que protege o ficheiro do dono), e o `--neg-arm` ganhou a
TERCEIRA mutacao: medido `A/E/F` RED, `NEG-ARM PASS`.

## O QUE AINDA NAO SEI (e nao afirmo)

- **O nemotron nao tem caminho de largada**: `grep -rn "def release" worker/*.py`
  devolve `engine_policy.py:223` (parakeet), `:271` (`RunnerEngine`, que devolve
  `False`) e mais nada para o motor ao vivo. Isso e' a regra do dono de 2026-11-04
  ("legenda ao vivo desligada nao e' modelo desligado"), nao um defeito — mas
  significa que a frase do painel, em `vram`, e' verdadeira so' para o parakeet.
- **O `private_mb` do worker (2883.8) nao mudou nos dois lados do parque desta
  sessao.** Com a linha nova, a proxima largada responde isto com dois numeros em
  vez de uma deducao. VRAM livre subiu 393 -> 13 643 MiB entre o parque e a
  retomada, e isso e' compativel com os apps DELE a fecharem: nao atribuo.
