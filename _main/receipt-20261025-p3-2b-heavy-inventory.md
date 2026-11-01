# Recibo - P3.2-b: os seis passos pesados, inventariados, e o subconjunto headless recusado pelo portao

Anchored section: `## P3.2-heavy`.

## P3.2-heavy

O recibo do P3.2 diz `skipped=6`: seis passos da classe `heavy` ficaram **NOT RUN** na corrida de
2026-10-25 08:0x-08:34, porque o opt-in nao chegou com o valor `"1"` (`set VAR=1 && ...` entrega
`"1 "`, medido). Um passo saltado nao e um portao que passou, e por isso o verde da bateria **nao** se
declara. Este ficheiro inventaria os seis, escolhe o subconjunto que pode correr sem o ecra do dono, e
registra a recusa do portao de performance.

### 1. Os seis, um por um, e o que cada um FAZ (lido do codigo, nao do nome)

| passo | comando na `.cmd` | o que spawna | classificado |
|---|---|---|---|
| `mute-audio` | `python _main\mute-audio-oracle.py` | mexe no **dispositivo de audio** do dono (`mute-audio.py`) | **interactivo com o dono** |
| `strip-surface-runtime` | `python _main\_strip-surface-probe.py` | `sotto_webview` com `CREATE_NO_WINDOW`, sem `--show` (`--no-hotkey --no-hot-reload --no-worker`) | headless |
| `strip-stats-log-budget` | `python _main\_strip-stats-log-probe.py` | o mesmo shell, com `--with-worker` e um worker STANDIN | headless |
| `strip-geometry-restore` | `python _main\_strip-restore-probe.py` | o shell, `--exit-after 8`, e **escreve o ficheiro de geometria** do dono | headless, mexe em estado do dono |
| `strip-stats-wave` | `python _main\_strip-stats-probe.py` | o shell, `--probe-stats` le o DOM, `--show` **nao** e passado | headless |
| `control-panel-exit3-neg-arm` | `python _main\panel-exit3-oracle.py --unit --neg-arm` | ARM 0 only; o proprio ficheiro diz "no audio needed" e `unit_only` curto-circuita o spawn | headless |

A classe `heavy` destes cinco **nao** vem de mostrarem janelas: vem de subirem o WebView2 (medido em
2026-10-21: 38 `msedgewebview2.exe`, VRAM saturada). O texto generico do `skipped` diz "opens the
owner's screen, his audio device or his GPU", e para `mute-audio` a primeira e a segunda sao literais.

### 2. As guardas, medidas antes de decidir (2026-10-25, depois das 08:5x)

```
python _main\lane-screen-gate.py
  braco 1 synthetic-input green | braco 2 lane-launcher-visible green | braco 3 agents-rule green
  VERDICT: PASS  (baseline congelado: 13 ficheiros com input sintetico, 2 harnesses com --show -- NAO cresceu)
```

O `--show` nao e passado por nenhum dos cinco, e o gate que julga isso passa. O que faltava era a
trava de instancia unica, porque uma instancia viva faz a largada seguinte morrer em silencio:

```
OpenMutexW('Local\SottoShell')  -> FREE
OpenMutexW('Global\SottoShell') -> FREE
_main\panel-state.json          -> 2805 B, mtime 2026-10-24 00:11 (velho, nao ha shell vivo a escreve-lo)
```

Nota: `Get-Process msedgewebview2` conta **19** processos vivos, e isso **nao** prova um shell do
Sotto -- o mutex livre e o `panel-state.json` parado provam o contrario. O numero sozinho ja foi lido
como "a app esta a correr" noutra ocasião; a identidade mede-se pelo mutex e pelo registo, nunca pela
contagem.

### 3. O portao de performance RECUSOU o lease, e o passo nao se largou

```
python tools\performance-gate.py status   -> performance-gate: AMBER (commit-only, avail=28.3%)
python tools\performance-gate.py acquire --kind heavy --owner sotto-lane-p32-heavy5 --ttl 1800
  refused heavy lease ... state=amber
  - heavy-requires-green
```

`unknown` nao e `green` e `amber` tambem nao. O subconjunto nao correu. **Nao ha verde nenhum a
declarar daqui**, e os seis continuam NOT RUN.

A segunda tentativa, depois do trabalho nao-pesado deste turno, recusou com a razao medida e nao so o
estado:

```
refused heavy lease owner=sotto-lane-p32-heavy5 state=amber
  - heavy-requires-green
  - commit-pct=86.2 >= amber 80.0
```

Ou seja: a pressao de commit da maquina (86,2 %, contra o limiar amber de 80 %) e o que recusa, e nao
um lease esquecido nem um portao avariado. Duas tentativas, duas recusas, a segunda com o numero --
nao se tenta uma terceira: uma recusa e um resultado, e insistir nela e o mesmo erro que fazer polling.

### 4. O comando exacto que fica pronto (a primeira janela GREEN corre isto, por esta ordem)

```
python tools\performance-gate.py acquire --kind heavy --owner sotto-lane-p32-heavy5 --ttl 1800
python tools\performance-gate.py validate --id <id> --kind heavy --owner sotto-lane-p32-heavy5

python _main\_strip-surface-probe.py        > G:\Temp\opencode\heavy-surface.log 2>&1
python _main\_strip-stats-log-probe.py      > G:\Temp\opencode\heavy-statslog.log 2>&1
python _main\_strip-restore-probe.py        > G:\Temp\opencode\heavy-restore.log 2>&1
python _main\_strip-stats-probe.py          > G:\Temp\opencode\heavy-statswave.log 2>&1
python _main\panel-exit3-oracle.py --unit --neg-arm > G:\Temp\opencode\heavy-exit3neg.log 2>&1

python tools\performance-gate.py release --id <id> --owner sotto-lane-p32-heavy5
```

Entre cada um: `OpenMutexW('Local\SottoShell')` tem de voltar **FREE** (nenhuma instancia partida a
deter o nome). E `_main\panel-state.json` foi copiado para
`G:\Temp\opencode\panel-state-before-heavy.json` antes de tudo, para o `strip-geometry-restore` -- que
escreve o ficheiro de geometria do dono -- poder ser revertido byte a byte.

### 5. O que fica deliberadamente de fora

* `mute-audio`: mexe no **dispositivo de audio do dono**. Nao e uma questao de lease: e a regra do
  ecra/audio dele. Corre quando ele disser, ou quando o `mute-audio-oracle` correr como parte de uma
  janela que ele autorizou. A alternativa (o oraculo) ja tem 21 bracos e 8 mutantes provados; o que
  falta e a corrida, nao o instrumento.

### 6. Limites

1. Nenhum dos cinco correu: este recibo prova a **classificacao** e a **recusa**, nao a saude dos
   passos.
2. `strip-geometry-restore` escreve estado do dono mesmo quando passa -- o snapshot acima e o unico
   caminho de volta, e vive num ficheiro temporario.
3. O `lane-screen-gate` prova que estes instrumentos nao passam `--show`; nao prova o que o WebView2
   pinta por dentro.
