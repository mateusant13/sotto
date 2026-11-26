# Receipt — os dois últimos vermelhos, o rato do code-health e a medição de io (2026-11-26)

Tree que a bateria julgou: `c570d5e` (último commit de código antes da corrida).
Corrida: `_main/_audit-verify/_battery-run-20261126-140341.log`, **596 passos, 1 080 s,
`BATTERY-VERDICT: GREEN WITH 25 SKIPPED`, 0 FAILED**.

## 1. `code-health rc=2` — o rato julgava um ficheiro PARTIDO

A base `_main/code-health-baseline.json` tinha sido gravada em `c69f692` a partir de
`worker/speaker_sidecar.py` **sem** a linha `DEFAULT_WINDOW_S = 10.0`, que o meu próprio trim de
comentário apagou em `c2e30ecc`. O `34e31e9` repôs a constante (era a causa do `NameError` que
matava `speaker-sidecar-gpu-policy`, `capture-share` e `stutter-caption`); na corrida seguinte o
rato viu **+24 B / +1 linha** e chamou-lhe regressão.

- Diff da base: exactamente duas linhas, `bytes` 96 681 → 96 705 e `lines` 1 991 → 1 992.
- `--update` mediu sobre conteúdo **commitado** (`--update` recusa uma entrada que mudaria a partir de
  ficheiro não commitado): `106 ficheiro(s)`.
- Depois: `CODE-HEALTH VERDICT PASS`, `piorem: 0 métrica(s)`; `--neg-arm 5/5`.
- Commit `b142af90`.

## 2. `nemotron-preload rc=1` — dois braços mediam o escalonador, não a supressão

Medido: **10/12 dentro da jaula**, **12/12 sozinho** minutos depois, na MESMA árvore. O texto da
falha era o mesmo nos dois braços: `MISSING: activation leaked stale hidden status before child
response` e `MISSING: ready-before-open status did not clear on activation`.

**Mecanismo (lido, não adivinhado).** `WorkerBridge` **não** guarda estados de um filho escondido
para os reproduzir na ativação: cada linha é decidida quando chega —
`app/webview/sotto_webview.py:25966-25967` calcula `preload_hidden`, `:26163-26166` descarta,
`:26168` entrega a `_status`, que chama `on_status` de forma síncrona (`:25286-25305`). A bomba é
um leitor único (`_pump`, `:25688-25701` → `_consume` `:25894`, ramo de estado `:25958`) e ela
publica `bridge.state` em `:25962` **antes** de decidir em `:26163`. Os dois `if status_events:`
olhavam precisamente para esse intervalo: não mediam a supressão, mediam quando o fio do filho
chegou.

**Forma nova (três peças, cada uma com a razão no código):**

| braço antigo | forma | fica vermelho por |
|---|---|---|
| vazio antes da ativação | **apagado** — estritamente subsumido pela contagem final (um vazamento vira evento a mais depois da barreira, e há um só leitor) | a contagem `!= expected_status_count` |
| vazio depois de `request_capture` | **projeção pura** `caption_status_for(ready_state) is not None` | o dicionário local, sem fio nenhum |
| contagem final | dreno limitado a **2,0 s** + juízo por **NOME** contra `hidden_names` | um nome que só pode aparecer se a supressão quebrou |

**Controlo negativo (mutando a EXPECTATIVA, não o produto):**

```
=== expectativa de vazamento invertida ===
real WorkerBridge fake-child=10/12
VERDICT: FAIL
  MISSING: activation leaked stale hidden status ['capture-started']
rc=1
=== projeção invertida ===
real WorkerBridge fake-child=11/12
VERDICT: FAIL
  MISSING: ready-before-open status did not clear on activation
rc=1
=== revertido ===
real WorkerBridge fake-child=12/12
VERDICT: PASS -- preload activation and hidden panel routing are enforced
rc=0
```

Cinco corridas seguidas: `5/5 PASS`, `12/12` em cada. `--neg-arm`: `NEG-ARM: PASS -- 17/17`.
O braço `--neg-arm` do próprio oráculo continua a apanhar os mutantes de ciclo de vida.
Commit `c570d5e` (levou também os dois `.txt` de output colado que estavam versionados na raiz).

A lei que sobra disto ficou em `AGENTS.md` (§ *UM BRACO QUE LE UMA LISTA ENTRE DOIS PASSOS DO
PRODUTOR NAO E' UM BRACO*), commit `e33634e`: `AGENTS-PINS PASS -- 2 pin(s)`, `claims-date PASS
checks=4 fail=0`, `console-window-audit PASS 0 sítios`.

## 3. O io que o watcher mediu — identidade, tecto e mecanismo

DM `dm-62a363448a9b46ef11c4` (relief `stutter-relief`): `cmd.exe(32908)`, **22,8 MB/s a 42 301
ops/s**, `io 63 586,8 MB/s` no sujeito, mas só **1,76 MB/s em TODOS os volumes**.

- **Identidade:** minha. `cmd.exe(32908)` é o wrapper `--caged` da bateria que eu largei
  (`cmd.exe(103372)` → `python -m watcher run --cpu 40 --io very-low` →
  `cmd /c _main\_audit-verify-all.cmd --caged`), cwd `H:\sotto`, árvore de 8 processos.
- **Tecto declarado, do próprio log da corrida:** `job CPU hard cap 40% (children inherit)`,
  `io priority VeryLow (readback=0)`. É **um** job, **um** passo de cada vez — não há workers a afinar.
- **Re-medido (psutil, diferencial de 5 s sobre a árvore):** acumulado de vida
  **1 354,9 MB lidos**, janela **21,78 MB/s a 41 753 ops/s** = **521 bytes por operação**. Bate com
  o instrumento do watcher e confirma a classe: leituras pequenas de page-cache/pipes, com
  `C: 0,20 MB/s` e `0,64 ms/op` no volume.
- **A atribuição por processo DENTRO da árvore não serve:** um `cmd.exe` não faz 42 mil leituras por
  segundo; ele é o host de terminal dos filhos, logo a linha por-pid nomeia o transporte.
- **Mecanismo:** a bateria são 596 linhas `call :step`; cada corrida arranca um `pythonw` por passo
  (`step-deadline.py`), o comando do passo (outro interpretador que importa site-packages) e um
  `_stepcache.py record`. Medido nesta árvore: **0,07 s por `record`** (5 records = 0,34 s), logo o
  registo custa ~24 s na corrida inteira — não é ele o custo. O custo é o **arranque de
  interpretador × 348 passos que correram** (596 − 248 em cache).
- **O que já corta:** o plano (`_battery-plan.py`) responde HIT a partir de uma variável, sem
  arrancar interpretador (`:plan_lookup`, `_audit-verify-all.cmd:4722`), e a cache é por CONTEÚDO.
- **O que ficou por fazer, nomeado:** um runner persistente que mantenha **um** interpretador e
  despache os oráculos dentro dele. É uma reescrita do runner com braço vermelho próprio; não entrou
  numa resposta, e a estimativa (arranque ≈ 0,3 s × 348 ≈ 104 s de 1 080) é uma **inferência**, não
  uma medição.

Resposta enviada: `I:\!watcher\state\herdr-inbox\dm-eeafd9f60f7f20bdd8e5.md`; DM original fechada
`answered`.

## O que este recibo NÃO prova

`fixed, NOT verified` para tudo o que só corre no arranque dele: o tecto do diarizador
(`42b7420f`) e as correções do congelamento. As metades não medidas estão declaradas em
`docs/por-medir.md` (diarizador pós-arranque, cadência de pintura com o painel aberto, YouTube a
tocar de um perfil de lane).
