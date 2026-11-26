# Os 21 passos `heavy` da bateria: o que substitui cada um, e o que não tem substituto

Medido 2026-11-26 sobre `_main/_audit-verify-all.cmd` (445 321 B): **21** `call :step heavy`,
contados por `grep -c '^ *call :step .*heavy'`. Eles não correm sem `SOTTO_BATTERY_HEAVY=1`
porque abrem a tela, o dispositivo de áudio ou a GPU do dono — e uma lane não faz isso. Esta é
a classificação honesta de cada um em três classes, com o substituto que já existe, o que falta
construir, ou a razão pela qual ele é irredutível.

## Classe A — a metade provável já existe fora da tela

| passo | o que ele mede | substituto |
|---|---|---|
| `panel-paint-first-measure` | primeiro quadro do painel (custou 328 ms medidos) | `_main/panel-hidden-at-startup-oracle.py` mede a decisão de mostrar sem abrir; a **pintura** passa a ser coberta por `headless_paint` |
| `strip-surface-runtime` | a superfície da faixa | `_main/overlay-ink-oracle.py` lê os píxeis reais do bitmap do `_layout` fora do ecrã |
| `strip-stats-log-budget` | orçamento de linhas do log do strip | idem, pela contagem de frames do destino headless |
| `strip-stats-wave` | a forma da onda na faixa | idem |
| `strip-geometry-restore` | o rect da faixa no monitor do cursor | `_main/multi-monitor-oracle.py` julga `select_display_for_point` e o clamp da work area **sem** janela (6 braços) |
| `control-panel-exit3-neg-arm` | o braço negativo do painel de controlo | o par negativo corre sem abrir: é mutação de expectativa |
| `shell-relaunch` + `red-as-expected-shell-relaunch` | relançamento da shell | `SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py` já arranca escondido; o que falta é o braço de **relançamento** na lane |

**Regra que fica:** um passo `heavy` cuja metade julgada é *decisão*, *geometria* ou *píxeis de um
bitmap* tem substituto headless. Ele sai da classe `heavy` no mesmo commit em que o substituto prova
estar verde, e o passo original fica como `crosscheck` declarado com o custo medido — nunca os dois
como portões do mesmo invariante (lei dos testes, propriedade 3).

## Classe B — precisa de um dispositivo de áudio, e o dispositivo é dele

| passo | por que não corre | via honesta |
|---|---|---|
| `mute-audio` | escreve num endpoint | recusa sem `SOTTO_OWNER_AUDIO_OK=1`; `--status-all` é leitura livre |
| `device-silence` + `red-as-expected-device-silence` | renderiza para `CABLE Input` e o VoiceMeeter encaminha para hardware | a metade de **lógica** corre com `sounddevice` falso (é o que `_main/capture-share-oracle.py` faz); a metade de **device** fica `CANNOT-MEASURE` |
| `speaker-watch` + `red-as-expected-speaker-watch` | abre o dispositivo real (`--allow-heavy`) | idem: o dublê cobre o contrato, o device não |
| `parakeet-ultra` | carrega o modelo e mede disco/VRAM | precisa de GPU; roda caged com autorização explícita do dono |

**O que já foi feito desta classe:** `_main/speaker-sidecar-oracle.py` (142/142 + 21/21 mutantes)
julga a mistura de microfone, o ganho constante do loopback, o resto de áudio carregado e o silêncio
digital **sem abrir um dispositivo** — 15 braços de `mic_battery` com taps falsos.

## Classe C — irredutível sem a superfície do dono

| passo | por que |
|---|---|
| `altc-first-caption` | mede o gesto a produzir a primeira legenda **na tela**; o gesto sintético é proibido (`keybd_event`/`SendInput` mede o Windows, não o Sotto) |
| `power-recovery-live` | depende do estado de energia da máquina dele |
| `concurrent-workers`, `devlab-crosstalk` | dois workers reais com a app dele aberta; medem o produto sob carga real, não um contrato |

Estes três/quatro continuam **SKIPPED** e nomeados no sumário. Não é um verde: é um buraco com
nome, e a única cura é a palavra dele naquela sessão.

## O que isto muda na prática

- Hoje: `GREEN WITH 25 SKIPPED`, 21 deles `heavy`. Depois da classe A migrar: **~14 SKIPPED**.
- O número que **não** desce: os da classe B e C. Um passo que abre o dispositivo dele continua a
  ser decisão dele, e a página do produto deve dizer isso com o nome, não com um "skip".

## Como re-medir (o censo é um comando)

```
grep -c '^ *call :step .*heavy' _main/_audit-verify-all.cmd
grep -aE "BATTERY-VERDICT|skipped=" _main/_audit-verify/_battery-run-*.log | tail -3
```

O primeiro número é a população; o segundo é o que ela custou na última corrida. Uma mudança de
classe que não muda o segundo número não aconteceu.
