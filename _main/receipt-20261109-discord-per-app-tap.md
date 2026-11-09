# RECIBO — o áudio do Discord, identificado por PROGRAMA (2026-11-09)

Ordem do dono, verbatim: *"to em call no discord agora. identifica corretamente o audio saindo do
discord. faz o tempo real funcionar"*.

Este recibo cobre a metade **identificar**: o tap por processo já existia e não tinha como sobreviver
ao reinício do programa, porque só aceitava um PID. A metade **tempo real** está noutra lane
(fusão stream/refinado) e não é afirmada aqui.

## 1. O que já existia, e foi medido a funcionar (nesta máquina, hoje)

`worker/sotto_worker.py` já implementa **WASAPI process loopback**
(`AUDIOCLIENT_ACTIVATION_PARAMS`, modo `INCLUDE_TARGET_PROCESS_TREE`) e aceita `--target-pid` /
`SOTTO_TARGET_PID`. Medido, com o `Discord.exe` vivo:

```
PLP_TARGET pid=24484 state=alive desc='Discord.exe' mode=0
PLP_GET_MIX_FORMAT hr=E_NOTIMPL (a resposta medida neste dispositivo)
PLP_INITIALIZE declared float32 48000 2ch + LOOPBACK|AUTOCONVERTPCM -> hr=0
PLP_GET_BUFFER_SIZE frames=480 ; PLP_START hr=0
PLP_OPEN_OK pid=24484 rate=48000 channels=2 block=4800
blocks=39 silent=0 pump_exited=False hr=0   (4 s)
```

E a árvore do Discord, lida agora: **6 processos** `Discord.exe`, todos filhos da raiz **22992**
excepto ela. O maior pid é **24484** — e **não** é a raiz.

## 2. O que faltava, e por que um pid não serve

Um pid é um **número**. Ele morre no instante em que o dono reinicia o Discord, e nesse instante a
escada fica sem alvo — sem erro, sem aviso, apenas nenhum rung `p`. O que o dono nomeia é o
**programa**. Além disso, o pid certo não é "o mais gordo": o modo include-tree captura a árvore do
pid dado, logo um pid do MEIO deixa de fora os irmãos que renderizam áudio.

## 3. A cura

`worker/process_target.py` (novo) — puro o suficiente para ser julgado sem abrir processo:

* `match(rows, name)` — igualdade do basename normalizado, **nunca substring** (um filtro por
  palavra casaria `Discord.exe` com `DiscordCanary.exe`);
* `pick_root(rows, name)` — a **raiz** da árvore (o processo do nome cujo pai não tem o mesmo nome);
  empate → o maior pid, que no Windows é o mais recente;
* `resolve_again(name, current, rows)` — mantém o pid vivo, **re-resolve** quando ele morreu, e
  devolve `None` quando não há nenhum processo do nome (nunca cai no mix do endpoint em silêncio).

Fiação em `worker/sotto_worker.py`: `--target-name` / `SOTTO_TARGET_NAME` / `audio.target_name`
(três fontes, a primeira que existir ganha; `--target-pid` continua a ganhar de todas, porque um pid
explícito é o dono a apontar o dedo). Resolve no arranque (recusa cedo, com `stage=target-name`,
quando o programa não está a correr) e **re-resolve na rotação** (`TARGET_NAME_REBOUND` /
`TARGET_NAME_MISSING` no log).

## 4. Verificação corrida (o comando e o veredicto, não um adjectivo)

| o quê | comando | resultado |
|---|---|---|
| as decisões | `python _main/process-target-oracle.py` | `PROCESS-TARGET VERDICT: PASS (14/14)` rc=0 |
| os mutantes | `python _main/process-target-oracle.py --neg-arm` | `NEG-ARM: 3/3 mutantes apanhados` rc=**1** |
| a captura da RAIZ | `ProcessLoopbackTap(pid=22992)` 4 s | `blocks=39 silent=0 pump_exited=False hr=0`, `winner='declared float32 48000 2ch + LOOPBACK\|AUTOCONVERTPCM'` |
| a escada | `process_loopback_candidate(22992)` | rung `p`, `target_pid=22992` (arm A9) |
| a bateria | `process-target` + `red-as-expected-process-target` | ligados; `battery-wiring` PASS 7/7, `battery-record-pairing` PASS, `battery-class` PASS |
| o pin | `python _main/agents-md-pins-oracle.py` | `325645 B / 3821 CRLF`, `AGENTS-PINS PASS` |

Os mutantes que o negativo apanha são o defeito real, cada um pela sua arm: comparação por
substring (A1), raiz = maior pid (A3), pid morto sem rebind (A7).

## 5. O que NÃO está medido

* **O áudio de uma CALL real.** Na janela da medição o Discord estava a renderizar **silêncio**
  (`peak=0.0`, `rms=0.0`, `silent_packets=0`, 39 blocos chegaram): a captura está aberta e a
  entregar, mas não havia voz para julgar. Provar "a voz do call sai em `target-name`" exige uma
  call activa — é a mão dele, não uma lane.
* **A separação contra o mix.** Provar que o tap por processo EXCLUI música/jogo exige tocar áudio
  numa lane, o que a lei do áudio do dono proíbe. Declarado `CANNOT-MEASURE` em lane, pelo motivo.
* **O caminho de produção**: a shell não passa `SOTTO_TARGET_NAME` por si. Ligar isso é uma decisão
  de política (um Discord sem call entrega silêncio, e um vídeo de YouTube deixaria de ser ouvido),
  por isso a chave existe e não é default.
