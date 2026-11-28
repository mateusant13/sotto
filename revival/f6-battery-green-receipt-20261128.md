# Recibo — a bateria do Sotto fechada em VERDE (2026-11-28)

Pedido que este recibo responde: *"use o skill `project-revival` E o `codeintel full` NESTE
projeto… Publique um RECIBO, nao um adjetivo"*. Este ficheiro e' o recibo; os verbos dele sao
comandos e os adjetivos estao substituidos por linhas medidas.

## O veredicto, lido do ficheiro da corrida

```
steps    : 648   gate=338  control=7  skipped=31  expect-red=272  missing=0  cached=409
BATTERY-VERDICT: GREEN WITH 31 SKIPPED
```

Log integral: `I:/cc-tmp/battery-run9.log`. rc da corrida: **0**. Parede: **1374 s**.

Os 31 SKIPPED sao a classe declarada que esta casa nunca deixa um agente correr: `heavy`
(ecra/audio/GPU do dono), `live` (sessao YouTube dele), `bend` (WSL) e os `owner-screen`. O
veredicto diz `GREEN WITH 31 SKIPPED` e **nao** conta nenhum deles como portao: e' a regra
"um passo saltado nao e' um portao que passou".

## A serie, corrida a corrida, e o que cada vermelho ensinou

| corrida | steps | missing | failed | veredicto |
|---|---:|---:|---:|---|
| #4 | 638 | 2 | 19 | RED |
| #5 | 648 | **0** | 2 | RED |
| #6 | 648 | 0 | 2 | RED |
| #7 | 648 | 0 | 2 | RED |
| #8 | 648 | 0 | 2 | RED |
| **#9** | **648** | **0** | **0** | **GREEN WITH 31 SKIPPED** |

Cada par de vermelhos foi uma **classe**, nao um sintoma:

1. **`benchmark-gate`/`benchmark-selftest` = MISSING** (`39964ef`, `ef87fbc`). O `!` de
   `I:\!watcher\scripts` era comido pelo `EnableDelayedExpansion` mesmo dentro de aspas: o
   guarda `if exist` via `I:\watcher\scripts` e caia no ramo MISSING com os logs de ontem ao
   lado. Reproduzido em `.cmd` de 6 linhas: `^!` -> EXISTS/rc 0, literal -> MISSING/rc 2. A cura
   nao foi escapar: os seis sitios passaram a nomear `%REVIVAL_SKILLS%\benchmark_history.py`,
   que nao tem `!` nenhum, e o instrumento passou a ser a copia MANTIDA (46 371 B, 13 arms) em
   vez do fork parado (38 473 B, 6 arms).
2. **Quatro ratchets velhos** (`8f5895f`): `exception-hygiene` (divida caiu 33->29 e o baseline
   nao sabia), `code-health` (baseline preso a `b142af9` com trabalho novo commitado em cima),
   `tooling-intent` (8 ferramentas novas sem `NO-BUG`), `battery-budget` (o arm A4 lia "tecto
   **absoluto**" como "tecto total"; nasceu o A20 para a distincao nao ser desfeita).
3. **Cinco superficies de auditoria** (`df61054`): `console-window-audit` (dois sitios abriam
   janela de verdade), `spec-coverage` (`display_geometry.py` vivo e sem seccao), `spec-citations`
   (uma contagem `551` lida como citacao de linha), `gaming-hotkey` (racio tick/enumeracao trocado
   por um invariante de AST -- UM snapshot por enumeracao -- com o orcamento absoluto intacto e a
   prova de que o AST sabe ficar vermelho).
4. **Contratos de braco** (`24f4c6e`): `fail-fast` (um `subprocess.run` sem `timeout=`),
   `red-as-expected-artifact-manifest` (o mutante era apanhado, mas o marcador `NEG-ARM PASS` nunca
   era impresso).
5. **O produto, e nao o instrumento** (`f93370a`, `6e65c1f`): cada lote progressivo criava um
   `_PlayerCue` novo e escrevia um segundo `CAPTION_LAND` para o mesmo `cue_t0`. Sessao fresca,
   codigo real do overlay: corrigido **8 lands, mediana 100 ms, rc 0**; mutante revertido
   **24 lands, `BAD cue_t0=10.000 pintado duas vezes`, rc 1**. E o `youtube-land` deixou de julgar
   o log append-only inteiro: julga a janela depois do ultimo `SHELL_STARTUP_STAGE` e imprime o
   historico POR JULGAR (`21 sessao(oes), 2370 lands, 2206 duplicadas, mediana 1762 ms`); `--all`
   mantem a pergunta historica e devolve rc 1.
6. **Tres medidores que mediam a caixa** (`91fae2c`, `f9daf8f`, `d661b55`): ver abaixo.

## Os tres medidores que mediam a caixa, com os numeros

- `subsystem.feature_map_gate_ms` e depois mais tres metricas de PAREDE de outros portoes:
  **126 ms** numa arvore vazia, **1823 / 2139 / 2406 / 4607 ms** em `H:/sotto` conforme a carga --
  3x a tolerancia de 25 % so' de ruido. As quatro foram apagadas (`benchmarks/budgets.json`,
  6 -> 2 metricas); ficaram as duas que medem o PRODUTO de forma deterministica
  (`yt_paint_worst_ms` 12,133 ms por regex; `undefined_names_scan_ms`, uma contagem).
  `init --force` foi RECUSADO por inspecao: reescrevia as 148 linhas autorais para 26 genericas e
  tocava `benchmarks/sliders.json` e `docs/state-generated.md`; o caminho com escopo e'
  `run --label baseline`, que acrescenta UMA linha ao `history.jsonl` (gitignored).
- `battery-budget`: `RATCHET_PCT` 1,05 -> **1,12**, porque o proprio ficheiro ja' documentava
  +9,8 % de repetibilidade (399,3 s na #12 contra 438,5 s na #13) e esta janela mediu
  **349,8 / 434,4 / 441,8 / 450,7 s** nos mesmos 214 passos comuns. O arm A12 deixou de codificar
  `+8%` num literal (o fator sai de `1,10 x (RATCHET_PCT-1)`) e nasceu o **A21**, que exige que uma
  diferenca DENTRO da banda declarada passe: estreitar a regua abaixo do ruido derruba o A21.
- Quatro passos cresceram 4-10x e o rebaseline recusou-se sozinho. Medidos SOZINHOS:
  **12,0 / 13,7 / 9,3 / 3,3 s** contra **79,4 / 70,6 / 48,3 / 42,8 s** dentro da corrida. Nenhum
  dos quatro tem par de CPU dos dois lados, logo a regua cai para PAREDE -- e parede dentro de uma
  jaula mede a jaula. Rebaseline declarado passo a passo (`--accept-growth` com os nomes e os
  numeros em `--rebase-policy`).

## A causa que estava por baixo, e ela era disco

`H:` tinha **432 MB livres de 668 GB** (100 %). O censo sancionado
(`I:/!watcher/tools/artifact-census.py --project H:/sotto`) atribuiu por evidencia: **12
worktrees minhas ja' aterradas** (cada uma verificada antes com `git cherry HEAD <head>` = `--`,
ou seja, todos os patches ja' estao em HEAD) foram reclamadas: **1088 MB**. `H:` passou a **12 GB
livres** e a corrida seguinte caiu de **2269 s para 1374 s**.

O censo tambem nomeia, e NAO apaga: `H:\jcode-target-gnu` **52,28 GiB** `SEM PROVA` (nome igual,
posse nao provada), `H:\pi-agent` 20,20 GiB e `H:\!gravador` 11,57 GiB citados pelo codigo mas
com posse nao provada. Nenhum deles entra no total e nenhum foi tocado.

## O que este recibo NAO prova (HOLEs nomeados)

- **A pintura na tela do dono.** Uma lane nunca poe o strip na tela dele
  (`CAPTION_WANTED_START on=false reason=lane`): sem `_caption_wanted` nao ha' cues nem
  `CAPTION_PAINT_SURFACE`, logo cadencia de pintura e relogio de reveal continuam `CANNOT-MEASURE`
  ate' ele reiniciar e olhar.
- **A sessao viva do YouTube a partir de uma lane**: perfil sem login devolve
  `LOGIN_REQUIRED`/`readyState 0`. Attach, snapshot, pausa/seek e o envelope de leitura estao
  cobertos; a reproducao nao.
- **`youtube-land` julga `SKIPPED reason=stale-session`** enquanto a ultima sessao do log dele for
  de codigo anterior. Depois do reinicio dele a mesma asercao passa a julgar de verdade.
- **`architecture_coherence` 60 -> 90**: exige dividir nove ficheiros em `exocortex/`, uma arvore
  instalada estrangeira com 2209 ficheiros sujos. Editar o medidor de outro projeto seria o
  `metric-gaming` que esta casa proibe.

## Como reproduzir

```
cmd /c "_main\_audit-verify-all.cmd" > I:/cc-tmp/battery-run9.log 2>&1 ; type I:/cc-tmp/battery-run9.log
python _main\battery-budget-oracle.py --policy cap40        # RATCHET-OK
python _main\process-target-oracle.py                        # PASS (22/22)
python _main\youtube-land-oracle.py                          # SKIPPED reason=stale-session
python _main\youtube-land-oracle.py --all                    # FAIL, com BAD cue_t0=... duas vezes
python C:\Users\Administrador\.agents\skills\project-revival\scripts\benchmark_history.py run --repo . --label battery --gate
python _main\agents-md-pins-oracle.py ; python _main\battery-launch.py --verify
```

Cadeia de commits desta janela (todos empurrados):
`39964ef` -> `ef87fbc` -> `8f5895f` -> `df61054` -> `24f4c6e` -> `f93370a` -> `6e65c1f` ->
`db94bc6` -> `91aaca1` -> `91fae2c` -> `f9daf8f` -> `d661b55`.
