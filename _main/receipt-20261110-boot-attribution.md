# RECIBO — o arranque e a retoma passam a ter número (dono, 2026-11-10)

Tudo o que segue foi medido nesta árvore hoje. Onde o `PASS` aparece, o comando está ao lado e
foi corrido nesta sessão.

## 1. O card e o buraco

Card do dono: *"arranque: demora DEMAIS a responder a keybindings/qualquer coisa -- tornar
extremo"*. Medido no log DELE (`_main/webview-run.log`, worker pid 52792):

| relógio | linha |
|---|---|
| 21:22:33.014 | `BRIDGE_LOAD_MS` / worker com o modelo carregado |
| 21:22:50 | `STATUS_APPLIED text=device` |
| 21:22:56.047 | `capture-started` |

**23 s sem UMA linha** entre o modelo e a captura. `WORKER_BOOT_PROF` já publica `numpy_import`,
`ort_import`, `og_import`, `cuda_dirs`, `probe`, as três sessões, `og_model` e `first_decode` — o
que faltava era o custo de **abrir cada candidato da escada**, e quantas voltas a espera de
`DEVICE_IN_USE` gastou.

## 2. `LADDER_TRY` — uma linha por rung, com milissegundos

`worker/sotto_worker.py:ladder_try_line` (função **pura**) monta a linha; o laço da escada a
escreve em `err(...)` uma vez por candidato:

```
LADDER_TRY attempt=2/9 device='VoiceMeeter Input' api='wasapi' ms=1743 retries=1 result=opened
```

`result` ∈ `opened` | `refused` | `stopped`. O `ms` é medido de `_t_try`, carimbado **antes** do
laço de retry — senão somaria três esperas de 1,5 s ao valor da abertura.

Puro de propósito: um portão que precisa de ABRIR um dispositivo para provar que escreve uma linha
não tem controlo, e o áudio do dono é `MUST NOT` (regra de 2026-11-02).

## 3. `audio_back_step` — "o audio voltou e nada acontece", medido

Residual do card fechado por medição: o worker publicava `TAP_IDLE`/`TAP_STALLED` quando o áudio
**sumia** e `WORKER_RESUMED` quando o parque acabava. Nenhuma das duas responde à pergunta dele:
**os blocos voltaram e a legenda não?** O par (blocos a subir, `captions` parado) não era lido por
linha nenhuma — um worker saudável a transcrever silêncio e um worker partido eram a mesma linha.

Duas linhas, e a segunda dá nome ao defeito:

```
CAPTURE_SIGNAL_BACK gap_s=12 blocks=120 captions=4
NO_CAPTION_AFTER_AUDIO_BACK grace_s=25 blocks_delta=280 captions=4
```

- a lacuna é `gap_s >= TAP_STALL_S` — o **mesmo** limiar que `tap_stall_reason`/`TAP_STALLED` já
  usam, não um segundo número para a mesma pergunta (a arm A9 é **estrutural**: um `in src` casava
  com o próprio comentário que cita o limiar, e o mutante M3 passava por isso — medido no
  `--neg-arm`);
- a graça é `AUDIO_BACK_GRACE_S = 25 s`; se a legenda avançou, o estado morre em SILÊNCIO (o
  instrumento não fala no caso normal);
- a linha do defeito sai **uma vez**.

## 4. O portão de cada instrumento, e o negativo

| portão | positivo | negativo |
|---|---|---|
| `_main/ladder-try-instrument-oracle.py` | `VERDICT: PASS -- 12 arm(s), 0 failure(s)` rc=0 | `NEG-ARM: PASS -- 4/4 mutantes apanhados` rc=1 |
| `_main/audio-back-detector-oracle.py` | `VERDICT: PASS -- 11 arm(s), 0 failure(s)` rc=0 | `NEG-ARM: PASS -- 4/4 mutantes apanhados` rc=1 |

Os dois pares estão na bateria com `:expectred` (exige rc=1 **e** a frase `NEG-ARM: PASS` no log).
`battery-wiring` PASS `ligados=185 sem_passo=108 populacao=293`; `battery-record-pairing`
454 passos / 454 nomes / 0 achados; `battery-class` PASS arms=3.

## 5. O portão que recusou o commit (classe do `keyframe-shape`)

Duas corridas da bateria, sete minutos de distância, **o mesmo código**: 10:49:22 os 9 probes PASS;
10:56:37 `keyframe-shape-probe.mjs FAILED exit 1:` com a saída **vazia**, e o pre-commit recusou.

Não era o produto. O probe captura a **tela real** (`source: "desktop"`); um desktop parado dá
`longestUniqueRun` < 30, e `contentSufficientToCoverClock` recusa por desenho — o probe reprovava
um produto correto pelo único motivo que ele próprio mede e imprime na linha acima. E o
`parse-gate` pinava `CONTENT_SUFFICIENT: true`: dois portões dependentes da tela do dono.

Cura (três partes, §commits):
1. o probe deriva `REFUSAL_CLASS` (`still-desktop` | `unexplained` | `none`) e
   `REFUSAL_UNDERSTOOD`; a recusa explicada pelo próprio run sai **rc 0**, a recusa com conteúdo
   suficiente continua **rc 1**;
2. `process.exitCode` no lugar de `process.exit()` — com stdout num cano o `exit` descartava o que
   não foi escrito, e foi por isso que o gate ficou com `exit 1:` e zero bytes de evidência;
3. o pin do `parse-gate` passa a ser `REFUSAL_UNDERSTOOD` (independente do ecrã); `FIRST_IDR_SEC 0`
   fica, porque a primeira imagem tem de ser IDR em qualquer ecrã.

Medido depois: `keyframe-shape-probe.mjs PASS exit 0, all 10 receipt keys printed, and 2
truth-valued key(s) compared`; `parse-gate` `RESULT 9 passed, 0 refused`.

## 6. Pins

* `_main\_audit-verify-all.cmd` = **346458 B**, **4031 CRLF** / 0 bare LF,
  sha256 `D2B9E1DFE0BC252D3740A80DC0ECD641BA5D0DDB526A73A06B18FA124B13FCE1`
  (`agents-md-pins-oracle` PASS, 2 pins lidos ao vivo).
* `code-health` absorve a metrica declarada de `worker/sotto_worker.py`
  (`--update --allow-dirty`, 94 ficheiros).

## 7. O que NÃO está verificado

* **A janela viva dele.** O `LADDER_TRY` e as duas linhas do `audio_back_step` só aparecem com
  áudio a correr; a app não foi aberta por esta lane (a tela dele não é banco de ensaio). `fixed,
  NOT verified`: o que falta é o log do próximo arranque dele, e a linha nomeia o que procurar.
* O custo de 23 s continua **não atribuído**: o instrumento existe, o dono do número vem do
  primeiro arranque que o escrever. Nenhuma cura foi proposta antes dessa leitura — a regra da
  casa é medir primeiro, e um "arranque mais rápido" sem a linha ao lado seria um número sem dono.
