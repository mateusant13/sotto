# RECIBO -- o arranque e o parque (2026-11-11)

O card do dono, verbatim: *"a performance e o measure de TUDO tem que comecar a partir do momento que
o app abre. como um usuario. se eu abro o app, e ja tento abrir o painel alt c, e ele demora 2
segundos, E HORRIVEL"* e *"arranque: demora DEMAIS a responder a keybindings/qualquer coisa"*.

Tudo o que segue foi MEDIDO nesta arvore, hoje. Onde um numero de log aparece, ele tem hora e pid.

## 1. O que o arranque custava, e onde

Sessao do dono, pid 21400, `_main/webview-run.log`:

```
00:48:42.483  worker nasce
00:48:49.444  BRIDGE_LOAD_MS ms=6969          modelo: 6,5 s -- NAO e' o problema
00:48:55.836  LADDER_TRY 1/11 CABLE Input  result=opened
00:48:55.878  BRIDGE_METER peak=0.0458        o endpoint ESTA' a tocar
00:49:03.396  device-rotated (flat)           abandonou o que tocava
00:49:17.0xx  VoiceMeeter mudo, Fones recusado, Headset hands-free mudo
00:49:19.788  worker-parked (silent-device)
00:49:40.065  LADDER_TRY 1/11 CABLE Input  outra vez
00:49:41.295  primeira legenda                59 016 ms depois do arranque
```

Duas pernas, as duas curadas:

* **A ESCADA ABANDONAVA O ENDPOINT QUE RENDERIZA** (`600e190`). `silent_desktop_hold` perguntava ao
  censo "alguem toca na maquina?" e, com QUALQUER endpoint acima do piso, respondia "rotaciona" --
  sem perguntar se o endpoint a tocar era O DESTA TAP. Agora recebe `own_peak` (o pico do proprio
  endpoint no MESMO censo): a tocar aqui -> a tap fica e a janela dobra; mudo aqui e outro a tocar ->
  rotaciona como sempre; sem leitura -> nunca e' "sem sinal". Instrumento:
  `_main/first-capture-fast-oracle.py` **GREEN arms=11 fail=0**, `--neg-arm` **5/5**.
* **O PARQUE DORMIA O BACKOFF INTEIRO COM AUDIO A SAIR** (`b5b1783`). O `park_session` espera em
  `stop.wait()` de 15 s dobrando ate' 300 s, e nada perguntava ao medidor. Agora `park_meter_wake` le'
  o `IAudioMeterInformation` (leitura, nenhum cliente WASAPI) a cada `PARK_BEAT_S` e devolve
  `why='signal'`; `{}` ilegivel NUNCA acorda (ausencia de medida nao e' sinal). Piso do parque 0,01
  contra 0,002 da tap, porque um residuo de 0,003 nao e' uma legenda a nascer.
  Instrumento: `_main/worker-park-oracle.py` **GREEN 18/18** (P16 `why=signal wall_s=0.01
  meter_reads=3`, P17 `why=limited`), `--neg-arm` **rc=1** com 5 arms RED.

## 2. Dois instrumentos que condenavam o trabalho normal

* **A ARM QUE PENDURAVA** (`b5b1783`). O P16 conduz o `park_session` de uma COPIA mutada; com a guarda
  arrancada nenhuma leitura acorda o parque, o laco volta ao backoff para sempre e a arm ficou
  **7 minutos** presa (medido: pid 41048, `py-spy dump` -> `Stop.wait` -> `_wait` da copia negativa).
  Saiu por `kill`. Agora carrega o mesmo `should_end` do P17 (2 s) e o `why='limited'` e' o FAIL dela:
  um braco cujo unico desfecho possivel e' "o mutante nao acorda" nao pode esperar o relogio inteiro.
  Prova: `P18 {"mutant_P16_arm_ok": false, "mutant_wall_s": 2.0}`.
* **O `boot-interaction` SOMAVA PERNAS QUE NAO SAO A MESMA** (`b5b1783`). Duas correcoes:
  - `menu_ms` da bandeja media `time.monotonic()` antes e depois do `TrackPopupMenu`, que BLOQUEIA
    ate' o menu fechar: os **672 ms** da sessao sao o tempo com o menu ABERTO, ou seja a mao dele. A
    familia virou duas linhas -- `bandeja: menu aberto (ms)` INFORMATIVO e `bandeja: primeiro plano ok`
    como PORTAO (a fracao de menus com `ok=0`; o `SetForegroundWindow` cru era recusado 13 de 13
    antes do `AttachThreadInput`).
  - a primeira legenda virou TRES medidas, as tres com o numero na mesma tabela: `arranque -> 1a
    legenda` **59 016 ms** (PORTAO -- e' o que ele sente), `1a legenda: idade do AUDIO` **74 ms**
    (PORTAO -- a perna que e' NOSSA) e `escada aberta -> 1a legenda` **1 278 ms** (informativo).
    Medido: `--neg-arm` **8/8** (o G2 novo exige que 800 ms de menu aberto PASSEM; o R3 novo exige FAIL
    no `ok=0`) e `PAINT-ARM: PASS -- red=FAIL green=PASS mutacao=FAIL`.
  - **STALE NAO E' VEREDITO.** O oraculo passou a perguntar ao `live-code-freshness-oracle.py` se o
    PROCESSO que escreveu o log carregou o codigo do disco; com `STALE` o RED vira
    `BOOT-INTERACTION SKIPPED reason=stale-process` e cada linha reprovada sai como `STALE-EVIDENCE`.
    E' o mesmo contrato do `paint-live-show` (`demote_stale`), importado PELO CAMINHO porque o
    ficheiro tem HIFEN.

## 3. O que NAO esta' verificado

* **O numero do card nao mudou num processo vivo.** A sessao medida (00:48:42) precede as duas curas:
  o `live-code-freshness-oracle.py --strict` diz `worker/sotto_worker.py MUDOU DEPOIS DO ARRANQUE` e
  `O QUE O DONO CARREGA NAO E ESTE CODIGO`. Logo: **fixed, NOT verified** -- `UNMEASURED` ate' ele
  fechar e abrir a app; a proxima sessao do log e' que publica o numero.
* A prova de que o `own_peak` acerta no endpoint certo e' de FUNCAO (censo falso, nenhum dispositivo
  aberto). Abrir dispositivo de audio e' a tela dele: `MUST NOT`.

## 4. Portoes tocados

| portao | comando | resultado |
|---|---|---|
| parque | `python _main/worker-park-oracle.py --cpu-window 4` | `VERDICT: GREEN (18/18)` em 8,6 s |
| parque negativo | `python _main/worker-park-oracle.py --neg-arm` | `NEG-ARM: PASS`, rc=**1**, 5 arms RED |
| arranque/interacao | `python _main/boot-interaction-oracle.py` | `SKIPPED reason=stale-process` (o FAIL de 59 s fica impresso como `STALE-EVIDENCE`) |
| arranque negativo | `python _main/boot-interaction-oracle.py --neg-arm` | `NEG-ARM: PASS -- 8/8` |
| pin do `.cmd` | `python _main/agents-md-pins-oracle.py` | `AGENTS-PINS PASS -- 2 pin(s)` em 353 312 B |
| higiene | `python _main/undefined-names-oracle.py` | `GREEN -- 19 ficheiros` |
| ratchet | `python _main/code-health-oracle.py` | `PASS` depois de absorver +3 130 B / +60 linhas |
