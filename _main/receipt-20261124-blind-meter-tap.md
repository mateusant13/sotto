# 2026-11-24 — "não tá legendando nada": o medidor é cego no cabo virtual e a tap esperava para sempre

Ordem do dono, verbatim: *"grava o audio do meu chrome. por que o modelo nao ta
funcionando? to vendo uma live e nao ta legendando nada"* e *"grava pra fazer benchmark
depois/teste enquanto ao vivo tu arruma"*.

## 1. O corpus (pedido dele, medido)

`I:/sotto-tmp/ep-tap-rec.py --match "CABLE Input" --out I:/sotto-tmp/owner-chrome-live/cable-130431 --seconds 900`

```
13:04:33 OPEN rate=48000 block_ms=100
13:04:38 WIN 13:04:38 audio_s=5.0    blocks=+50   peak=0.1461
13:05:28 WIN 13:05:28 audio_s=54.4   blocks=+544  peak=0.1221
13:19:31 WIN 13:19:31 audio_s=819.7  blocks=+8197 peak=0.0000
13:19:33 CLOSED audio_s=821.7
```

821,7 s de audio real a 48 kHz, 16-bit, mono (≈ 79 MB), com `.log` por segundo e `.json`
de fecho. O `peak=0.0000` da ultima linha é a cauda silenciosa do fim da janela, não
perda de audio.

## 2. O defeito, e as duas testemunhas no mesmo minuto

`IAudioMeterInformation` lê **0,0000** nos cinco endpoints de render desta máquina
(`CABLE Input`, `VoiceMeeter Input`, `soundcore Space Q45`, `NVIDIA HDMI`, `HyperX
Quadcast`) — inclusive quando o cabo virtual está a transportar som. Medido lado a lado:

| instrumento | leitura no MESMO minuto (2026-11-24) |
|---|---|
| censo do medidor (`list_render_endpoints(meter_ms=0.2)`) | `peak=0.0000` em todos |
| loopback de endpoint independente no `CABLE Input` | `+544 blocos / 5 s`, `peak=0.1221` |
| worker do produto (pid 47460) | `blocks=2.0`, `peak=0.0`, `rows=0` |

A cadeia que isso produzia no produto:

1. `WORKER_COST ... rows=11 rows_since_tick=0 chunks_since_tick=0 audio_s_since_tick=0.000`
   congelado das 13:03:11 às 13:05:21 com o Chrome a tocar no cabo;
2. `BRIDGE_STATS_PUSH payload={"tag":"meter","peak":0.0,"blocks":2.0}` a cada 30 s;
3. `first_block_decided`/`dead_first_block_plan` com todos os medidores a zero →
   `TAP_QUIET_DESKTOP ... keep-the-tap`, e o `silent_desktop_hold` a dobrar a janela
   até `TAP_SILENT_DESKTOP_MAX_S` = 60 s;
4. `tap_stall_reason(...)` via `tap_census_verdict` = `quiet` → `"endpoint-idle"` →
   `progress("idle-wait"); stop.wait(0.1)` **para sempre**. A tap nunca reabria e a
   escada nunca descia até o endpoint que estava a renderizar.

Terceira reprodução, já com o `worker/config.json` a fixar o endpoint certo:
pid 59448 abriu `CABLE Input` às 13:18:09 (`LADDER_TRY attempt=1/10 ... ms=63
result=opened`), pintou legenda às 13:18:13 e 13:18:14 (`CAPTION_APPLIED text="Gente."
kind=final`), e às 13:20:25 o próprio produto escreveu
`TAP_DELIVERY_STALLED endpoint='WASAPI loopback: CABLE Input (Virtual Cable)'
stalled_s=33.6 action=client-starved` e **rotou para outro endpoint** — `WORKER_COST
rows=3 ... chunks_since_tick=0` daí até ao fim da sessão.

## 3. A cura (código)

`worker/sotto_worker.py`:

* `tap_stall_reason(..., run_blocks=None, window_blocks=None)` ganha o veredito
  **`meter-blind-starved`**: censo `quiet` (todos os medidores a zero) + a CORRIDA já
  entregou bloco + a JANELA não entregou nenhum ⇒ o cliente está travado, reabrir. A
  testemunha é o BLOCO, que o medidor não tem como falsificar. Um desktop realmente
  calado tem `run_blocks == 0` e continua a esperar — é o que preserva a cura de
  2026-11-02 (12 clientes WASAPI em 3 min).
* o laço passa as duas testemunhas:
  `run_blocks=counters.get("blocks", 0)` e `window_blocks=device_blocks["value"]`
  (este último é zerado em cada abertura, logo "0" quer dizer *este cliente nunca
  entregou*).
* a reabertura continua limitada por `reopens < TAP_REOPEN_MAX` e pela mesma escada de
  dispositivos, agora alimentada por uma testemunha que o medidor não envenena.

`_main/tap-delivery-stall-oracle.py` ganha A2.5–A2.8 (as quatro formas de decisão),
A5.7/A5.8 (a fiação no laço que embarca) e o mutante **M4** (o medidor cego volta a
responder "espera" — o defeito exato do dono).

## 4. Prova

```
python _main/tap-delivery-stall-oracle.py            -> TAP-DELIVERY VERDICT: PASS -- 27/27
python _main/tap-delivery-stall-oracle.py --neg-arm    -> NEG-ARM: PASS -- 4/4
```

Oraculos vizinhos que executam as mesmas funções, todos verdes depois da mudança:
`device-ladder-cost` 17/17, `first-capture-fast` arms=11 fail=0, `tap-first-block` 6/6,
`tap-silent-desktop` PASS, `tap-stall-policy` PASS, `tap-stall-watchdog` GREEN,
`worker-park` 18/18. `boot-interaction` = `SKIPPED reason=stale-process` (não é verde;
o processo que escreveu o log é anterior ao código).

**UNMEASURED:** a legenda a voltar num worker já curado nesta sessão — a shell do dono
congelou às 13:21:29 (ver §5) e nenhum worker novo subiu. A próxima abertura mede.

## 5. O red que esta lane não consegue pagar: a shell congelou

Medido, todos no mesmo instante:

* `_main/webview-run.log` para em `13:21:29.599` (36 862 637 B) e não volta a crescer;
  `_main/panel-state.json` e `_main/panel-visibility.json` param no mesmo segundo;
* nenhuma linha `BRIDGE_EXIT` do worker 59448, e **nenhum** `sotto_worker.py` vivo
  depois do kill — a shell não recolheu nem respawnou: as threads que logam pararam
  juntas;
* `shell-thread-cpu.py 37988 --seconds 5` → `0.0% de um nucleo`, `CANNOT-MEASURE`
  (a soma dos fios não fecha): processo parado, não ocupado;
* `taskkill /F /PID 37988` → `Acesso negado` (pane `medium`, app `high`);
* `python _main/sotto-relaunch.py --relaunch` → token emprestado executou
  `taskkill`, `rc=[(37988, 0), ...]`, e aos 15 s e aos 60 s o pid continuava vivo:
  **`ABORTA: a instancia antiga nao morreu; nao lanco nada`**;
* censo de janelas: **zero** janelas `Sotto`/`WebView*` na sessão — não há app na tela
  dele, só o processo-corpse a deter `Local\SottoShell`, e por isso qualquer arranque
  novo morre no mutex.

Um `TerminateProcess` que devolve 0 e não mata significa espera em kernel; nada que
esta lane faça a partir de uma pane `medium` a resolve. **A cura exige que o dono
termine o processo/faça reboot** — e é por isso que este red está escrito aqui, com o
número de cada medição, em vez de escondido.

## 6. Correção de rota aplicada

`worker/config.json` fica modificado **localmente** (`audio.device = "CABLE Input
(VB-Audio Virtual Cable)"`) para o próximo arranque do dono abrir o endpoint que
transporta o som; **não vai para commit** — é alavanca desta máquina, não default de
produto. `git status` mostra apenas `worker/sotto_worker.py`,
`_main/tap-delivery-stall-oracle.py` e esse ficheiro local.

## 7. O segundo red, e ele é o que apaga a legenda agora: a sessão ORT/CUDA congela

Depois do arranque novo (`sotto-relaunch.py --relaunch`, 13:38:23, pid 50268, code_id
`2D092F4CE7DE`), dois workers nasceram e nenhum legendou:

| pid | nascido | o que mediu |
|---|---|---|
| 56108 | 13:38:43 | `BRIDGE_LOAD_MS ms=9656` e depois **zero** blocos; morto pelo cão de guarda de silêncio às 13:39:26 (`killed=True`, `captions=0`) |
| 51584 | 13:39:27 | `WORKER_GPU_POLICY ... asr_request=CUDAExecutionProvider` às 13:40:00; a partir daí **0,0 s de CPU, 0 bytes lidos, RSS 707 MB imóvel por 4 min** (19 fios) |

Reporte reproduzido fora do produto, num processo desta lane com o MESMO binário e o MESMO
áudio (`python worker/sotto_worker.py --threads 2 --device "CABLE Input" --max-seconds 90`),
com `py-spy dump` a apanhar a pilha às 14 s:

```
Thread 18900 (active+gil): "MainThread"
    _create_inference_session (onnxruntime\capi\onnxruntime_inference_collection.py:789)
    __init__ (onnxruntime\capi\onnxruntime_inference_collection.py:683)
    open_graph (sotto_worker.py:1771)
    _asr_open_once (sotto_worker.py:1777)
    open_asr_sessions (sotto_worker.py:1894)
```

Amostragem de 10 em 10 s do mesmo processo: `rss_mb` 34 → 579 → 1476 → 1549 → **1549,2 →
1549,8 → 1550,3**, `read_mb` **71,7 nas três últimas**, `cpu_s` +0,1 por intervalo (o fio do
audio-ring, não o ORT). Ou seja: a criação da sessão CUDA **para** a meio, com 9,9 GiB livres
na GPU (`nvidia-smi`: 6083 MiB usados de 16303, 20 % de utilização) e o áudio a chegar.

O áudio estava lá, medido no mesmo minuto com a mesma API: loopback independente no
`CABLE Input` às 13:42:50 → `+51 blocos em 5,1 s, peak=0.2014`.

E a queda para CPU não existe como saída: `--providers CPUExecutionProvider` é recusado pelo
próprio motor — `RuntimeError: Nemotron requires CUDAExecutionProvider exclusively`
(medido, 3,5 s, `peak_rss_mb=288.5`).

**Conclusão:** o defeito que apaga a legenda hoje não é tap, não é dispositivo e não é o
modelo — é o processo a congelar dentro de `InferenceSession` com o provider CUDA, a mesma
classe de congelamento que já tinha matado a shell às 13:21:29 (0,0 % de CPU, log e ficheiros
de estado parados no mesmo segundo, `TerminateProcess` pendente). Nenhuma dessas duas classe
se resolve de dentro de uma pane `medium`: exige reiniciar a máquina (ou o driver de vídeo) —
e é por isso que este red fica escrito aqui com os números, em vez de escondido num commit.
