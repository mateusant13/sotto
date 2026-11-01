# Recibo — a bateria nunca mais trava/atrapalha o dono (2026-10-22)

## A ordem do dono, verbatim

Sessão **`ses_ea36ec6efffeE7E32m9COGhkxL`** ("Estado das legendas e renderer nativo"), 2026-10-21,
lida da base de sessões do OpenCode (`C:\Users\Administrador\.local\share\opencode\opencode.db`,
modo leitura):

| hora | o dono escreveu |
|---|---|
| 01:00:18 | *"e teus testes demoram muito e sao pesados. implementa caching e incremental test e etc."* |
| 17:22:24 | *"tu ta fazendo algo que faz meu pc travar/stutter? ou é outro processo?"* |
| 17:25:44 | *"essa porra dessa bateria ai deve ta mal otimizada ou burra entao. arruma. e faz cache/incremental test"* |
| 17:39:14 | *"entendo por que a bateria trava e da stutter. é por que o start do que quer que seja, da stutter no meu computador"* |
| 2026-10-22 | *"e tu vai garantir que minha reclamação nunca mais aconteça"* |

## O que causa o stutter (medido, não suposto)

- **Arrancar QUALQUER processo** custa ao dono **53-127 ms** de stutter nesta máquina (os discos
  estão a 0,4-20 % livres: um arranque é uma leitura de disco na fila que ele está a usar).
- **Arrancar a app** custa muito mais: `_main/_strip-stats-log-probe.py` escreveu a medição —
  **63,6 s depois "a caixa estava saturada (VRAM 100 %, 38 `msedgewebview2.exe`)"**.
- Logo o número que importa é **QUANTOS ARRANQUES**, não o tempo de parede.

Mas a frase antiga — *"os passos mais lentos são os que lançam a app"* — era **exacta demais**:
lendo as **origens** (`subprocess.Popen`), só **SEIS** passos tocam o mundo do dono.
`tap-open-timeout` (33,6 s) e `strip-surface-oracle` (19,9 s) estão entre os mais lentos e **não
arrancam nada** (um dorme num deadline, o outro só lê ficheiros).

## A GARANTIA — quatro partes

1. **A CLASSE `heavy`.** Um passo que abre o ecrã, o dispositivo de áudio ou a GPU do dono está
   declarado `heavy` no `.cmd`: **não corre** sem `SOTTO_BATTERY_HEAVY=1`; quando não corre é
   contado em `skipped=`, **nomeado** no sumário (`heavy:`) e **nunca** em `gate=`. Um passo
   pesado **em cache** é grátis (não arranca nada) e mantém o seu gate. O opt-in é o **VALOR**
   `"1"`, não a existência da variável.
2. **A BATERIA PÕE-SE `BelowNormal`.** O `cmd.exe` da bateria — e, por herança de `CreateProcess`,
   todos os seus filhos, incluindo a app que um passo pesado arranque — perde a prioridade para o
   primeiro plano do dono. O sumário diz o que aconteceu: `priority: BATTERY-PRIORITY BelowNormal
   pid=…`.
3. **O PORTÃO** `_main/battery-heavy-gate.py` (na bateria, com o braço negativo
   `red-as-expected-battery-heavy-gate`):
   - **C1** corre as **etiquetas REAIS da bateria** (extraídas verbatim do `.cmd`) sobre um passo
     **falso** que escreve um ficheiro-marcador, três vezes: por omissão o marcador **não** existe
     e o passo é **SKIPPED**; com `=0` **também não** existe; com `=1` **existe** e é **gate**.
   - **C2** as duas declarações concordam: cada passo `heavy` usa um instrumento com o marcador
     `BATTERY-HEAVY: <kind>` e cada instrumento marcado pertence a um passo `heavy`.
   - **C3** o **piso**: os seis nomes medidos estão lá, com o tipo de mundo que cada um abre.
   - **Neg-arm EXECUTADO: 5/5 mutantes apanhados** (rc=1 por desenho).
4. **O CENSO** `_main/_battery-start-census.py` (**lança ⇒ fica FORA da bateria**): traça os eventos
   do kernel `Win32_ProcessStartTrace`, que **não perdem** um python de 100 ms (uma sondagem de
   250 ms perderia), e conta **só a árvore de processos da bateria**.

## As medições de hoje

```
python _main\battery-heavy-gate.py            -> PASS, rc=0
python _main\battery-heavy-gate.py --neg-arm  -> 5/5 apanhados, rc=1 por desenho
cmd /c "_main\_audit-verify-all.cmd"          -> BATTERY-VERDICT: GREEN ... rc=0
   steps 95, gate=64, control=9, skipped=4, expect-red=18, missing=0, cached=84
   heavy    : mute-audio strip-stats-log-budget strip-surface-runtime strip-stats-wave
   priority : BATTERY-PRIORITY BelowNormal pid=4236
python _main\_battery-start-census.py         -> bateria rc=0, 20,0 s
   174 arranques NA ÁRVORE da bateria
     0 deles do MUNDO DO DONO  (msedgewebview2.exe / pythonw.exe / sotto_worker.py)
   717 arranques na máquina FORA da árvore -- nunca contados
python _main\_battery-start-census.py --neg-arm -> NEG-ARM PASS (viu pythonw.exe x1)
python _main\agents-md-pins-oracle.py         -> AGENTS-PINS PASS (2 pins, 0 falhas)
```

**0** é a resposta à garantia: uma corrida default da bateria **não arranca a app, nem o WebView2,
nem toca no dispositivo de áudio do dono** — e o censo **provou que sabe ver a diferença** (o braço
negativo arranca `pythonw.exe`, o nome que o kernel dá ao shell da app, e o censo conta-o).

## Dois defeitos que os próprios instrumentos apanharam

1. **A primeira versão da bateria lia a *existência* da variável** (`if not defined
   SOTTO_BATTERY_HEAVY`), não o seu valor. Foi **o censo que o apanhou**: ele põe `SOTTO_BATTERY_HEAVY=0`
   e a bateria correu os seis pesados — a corrida do censo gastou 373,9 s e teve
   `strip-surface-runtime rc=3`. A linha passou a `if not "%SOTTO_BATTERY_HEAVY%"=="1"`, a linha
   `heavymode:` do sumário pela mesma razão, e o mutante **M5** existe para isso não voltar.
2. **O censo estava a contar a máquina inteira** (10 417 arranques: servidores MCP do OpenCode,
   apps do dono). Passou a traçar `ProcessID` **e** `ParentProcessID` e a percorrer a árvore a
   partir do pid da bateria; o que não se consegue atribuir é reportado em `unattributed` e nunca
   contado. Dois sub-defeitos do próprio censo, apanhados pelo braço negativo: `Start-Process`
   junta o `-ArgumentList` com espaços e a regra de aspas do `/c` estraga comandos com várias
   partes aspadas (rc=1 em 0,1 s; curado com `ProcessStartInfo.Arguments` cru) e a subscrição do
   WMI **não está viva** quando `Register-WmiEvent` retorna (uma corrida de 0,1 s deu **zero**
   eventos; curado com 1,5 s de espera antes de arrancar o comando).

## Um vermelho latente que o modo rápido escondia

`red-as-expected-lang-id-oracle` estava a ser **fast-skipped** (e um passo saltado não é um portão
que passou). Quando correu: **rc=2** — a cópia-mutante de `worker/lang_prompt.py` é escrita fora do
repo, logo o `REPO` derivado do `__file__` aponta para o temporário e
`REPO/docs/model-specs/original/fp16/languages.json` não está lá (o export int4 não traz
`languages.json`) ⇒ o mutante "não chegou a correr". Corrigido em `_main/lang-id-oracle.py`:
**2/2 mutantes apanhados**.

## O que está DECLARADO e NÃO está medido

- O modo pesado (`SOTTO_BATTERY_HEAVY=1`) **não foi corrido na máquina do dono** — seria
  exactamente o stutter que se quer evitar. O seu custo já está medido no repo (62 s, 42 s, 34 s,
  29 s, 26 s por passo, mais os 38 processos do WebView2).
- O compositor das bordas (o desktop visto através dos cantos) precisa de relançar a app: só o LEAD
  o pode fazer e o dono está a usá-la.

## Ficheiros

- `_main/_audit-verify-all.cmd` — classe `heavy`, `:step_heavyskip`, opt-in pelo valor, bloco da
  prioridade, sumário (`heavy:`, `priority:`, `heavymode:`).
- `_main/battery-heavy-gate.py` — o portão (C1/C2/C3 + 5 mutantes).
- `_main/_battery-start-census.py` — o censo (traço do kernel, árvore da bateria, `--neg-arm`).
- `_main/lang-id-oracle.py` — a correcção das raízes do mutante.
- AGENTS.md — §4-bis (as quatro partes) e o pin do `.cmd` re-medido.

## Pin do `.cmd` (medido 2026-10-22 03:05)

`_main\_audit-verify-all.cmd` = **95614 B**, **1314 CRLF** / 0 bare LF,
sha256 `89E3BF852F4797BBD4723DB312EAB24F30EA258B010790B05252B9B3BC77BC9C`.
