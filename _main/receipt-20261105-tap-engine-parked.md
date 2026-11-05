# O motor largado pela shell nao e' um dispositivo culpado — 112 rotacoes viram UMA tap

Medido em 2026-11-05, na instancia VIVA do dono (shell pid 52504, arranque 18:04:52),
com o commit `d1edc17` a entrar no worker atraves do RESPAWN que a shell faz — o worker
corre o ficheiro do disco, logo nao foi preciso relancar a app.

## ANTES

| facto | valor |
|---|---|
| `device-rotated` no run (18:05..18:33) | **112**, quase todas `reason=flat`, uma a cada ~15 s |
| `VRAM_GUARD_PARKING` | `free_mb=669`, `free_mb=1176`, `free_mb=1141` — o motor esta' LARGADO |
| `ENGINE_PARK reason=vram` | 18:13:44 (publicado no `panel-state.json`, chave `park`) |
| audio presente durante o parque | `noAudioEvidence peak=0.317144` contra `floor=0.002` — ha' sinal |
| `CAPTION_IN` no run | 6, o ultimo as 18:09:01 — sem motor nao ha' legenda possivel |
| morte do worker antigo | 18:33:34 `BRIDGE_DEATH rc=4294967295 kind=error last="tap-dead-endpoint"` |

O instrumento dizia a verdade e ninguem a lia: a janela da tap chama-se "plana", o
`window_ended` pergunta ao medidor de silencio, ninguem toca em nada, e a escada ROTACIONA
— reabrindo um cliente WASAPI por rotacao no motor de audio que o dono partilha.

## A CURA

`worker/sotto_worker.py::window_ended` ganha `engine_parked=`: com o `park` que a shell
publica, a tap FICA ABERTA e a janela dobra `15,2 -> 30,4 -> 60` s (tecto
`TAP_SILENT_DESKTOP_MAX_S`), com UMA linha. Fechar e sondar perderia audio, que e'
exactamente o que o parque nao pode custar. O leitor `engine_parked_now` obedece ao
`staleAfterSeconds` do payload — o parque de uma shell morta nao segura a tap.

## DEPOIS (medido, nao inferido)

```
2026-11-05 18:33:52.075 sotto: STATUS_APPLIED text="tap-engine-parked"
```

| facto | valor |
|---|---|
| `device-rotated` depois da linha | **0** (232 linhas de log, ~100 s) |
| `TAP_DEAD_ENDPOINT` / `TAP_STALLED` depois | 0 / 0 |
| worker vivo depois | 13 `BRIDGE_ALIVE`, `phase=window` |
| `park` lido do ficheiro que os DOIS lados usam | `_main/panel-visibility.json`, `park='vram'`, escrito 2 s antes da leitura |

O caminho foi conferido nas duas pontas e nao por suposicao: `worker/sotto_worker.py:5994`
declara `--panel-visibility` (default `REDUX_VISIBILITY_DEFAULT`) e
`app/webview/sotto_webview.py:758` escreve `REPO_ROOT/_main/panel-visibility.json`. O
ficheiro tem hoje `park='vram'`, `writtenAtEpoch` e `staleAfterSeconds` — exactamente as
tres chaves que `engine_parked_now` le.

Nota de campo: `_main/panel-state.json` (a sonda de estado) e' OUTRO ficheiro e nao tem
`park` no topo — quem julgar o parque por ele ve `None` e conclui o contrario do verdadeiro.

## PROVA DO DETECTOR (fora da instancia viva)

`_main/worker-park-oracle.py`, 14/14 GREEN:

- **P12** — `window_ended` REAL com `engine_parked='vram'` devolve `[15.2, 30.4, 60.0, 60.0]`
  e escreve UM `tap-engine-parked`;
- **P13** — o MESMO `window_ended`, mesma janela plana, sem parque, devolve `None`
  (a escada anda): a arm mede o PARQUE, nao a funcao;
- **P14** — o mutante que desarma a guarda (`if parked:` -> `if False:`) numa COPIA do
  worker faz P12 RED. A prova do detector vive DENTRO do passo (precedente
  `dead-app-exit`, `caption-dup-repro`), entao a bateria nao ganha linhas.
- `--neg-arm` (parque revertido) rc=1; `--neg-arm-tap` rc=1.

## O QUE ISTO NAO PROVA

O limite da janela de 60 s nao foi exercitado na instancia viva (o parque durou ~90 s
depois da cura). O caminho que FECHA a espera quando o parque levanta e' o `now >= window_end`
normal, e a arm P13 e' o unico controlo de que ele ainda rotaciona quando deve.
