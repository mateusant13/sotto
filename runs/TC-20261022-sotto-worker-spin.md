# TC-20261022 — o worker busy-spin e o "sem backoff no respawn"

Queixa do dono, verbatim: *"worker busy-spin (1.3-1.8 cores) with no backoff on respawn"*.

**Resumo numa linha:** o backoff existia e a **paragem** também existia — mas a paragem estava
escrita num sítio que **nunca corre**. Corrigido e provado; o número de CPU (1.3-1.8 core) fica por
medir porque exige o worker a correr e o PC foi reiniciado (ver §5).

---

## 1. O que o log dele mostra (medido, não inferido)

`_main/webview-run.log`, 2026-10-22 04:04 → 04:25, uma morte no-audio a cada ~85 s:

```
04:04:02 BRIDGE_DEATH rc=3 deaths=1 kind=no-audio
04:04:02 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=15000  restart=0
04:05:46 BRIDGE_DEATH rc=3 deaths=2 kind=no-audio
04:05:46 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=30000  restart=0
04:07:52 BRIDGE_DEATH rc=3 deaths=3 kind=no-audio
04:07:52 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=60000  restart=0
04:10:21 BRIDGE_DEATH rc=3 deaths=4 kind=no-audio
04:10:21 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=120000 restart=0
04:14:48 BRIDGE_DEATH rc=3 deaths=5 kind=no-audio
04:14:48 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=240000 restart=0
04:20:18 BRIDGE_DEATH rc=3 deaths=6 kind=no-audio
04:20:18 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=300000 restart=0
```

O `restart=0` em todas as linhas é o que faz o log **parecer** "sem backoff": o campo imprime
`self.restarts` — o contador da **outra** escada (falhas reais), que fica a 0 na escada no-audio. O
contador que interessa (`no_audio_restarts`) nunca é impresso. O campo é honesto e enganador ao mesmo
tempo.

O que ele **não** mostra, e devia: `BRIDGE_RESTART_SUPPRESSED`. Zero ocorrências em 41 MB de log,
embora `no_audio_restart_cap=3` (`sotto_webview.py:11919`) mande parar à terceira morte seguida.

## 2. A causa (lida ao byte, não deduzida)

`_schedule_restart`, medido com `len(line) - len(line.lstrip())`:

```
12998  indent= 8  if self.stopped:
12999  indent=12      return
13000  indent= 8  # The two ladders. ...
13004  indent=12  # O TECTO. ...
13008  indent=12  if self.no_audio_restarts >= self.no_audio_restart_cap:
13021  indent=16      return
13022  indent= 8  if no_audio:            <-- a escada que SEMPRE corria
```

Um `if` a 12 espaços, imediatamente a seguir a um `return` a 12, **é o corpo do `if self.stopped:` a
8**. Portanto o tecto estava:

1. **aninhado em "a shell está a parar"** — o único estado em que ninguém precisa dele; e
2. **atrás de um `return`**, logo inalcançável em qualquer estado.

`ast.parse` aceita-o sem uma palavra: código morto depois de `return` é Python legal. É por isso que
nenhum portão o apanhou — os portões existentes procuram a **string** `BRIDGE_RESTART_SUPPRESSED`, e a
string está lá. Procurar uma string não é perguntar se ela pode ser executada.

## 3. A correcção

Desindentado 4 espaços (o bloco passou para indent 8, atrás do `if self.stopped: ... return`):

```
app/webview/sotto_webview.py   bytes 739 351 -> 739 279  (-72)
EOL: CRLF=14109 bareLF=0  antes  ->  CRLF=14109 bareLF=0  depois
```

## 4. A prova — `_main/worker-respawn-ceiling-oracle.py`

O instrumento **não lança a app, não carrega modelo e não abre dispositivo**: extrai
`_schedule_restart` do ficheiro real com `ast`, liga-o a um stub e conduz `cap + 3` mortes no-audio.
Três afirmações:

* **C1 ESTRUTURAL** — o tecto não pode estar dentro de um bloco guardado por `self.stopped` nem
  depois de um `return` no mesmo bloco. É a que **diz porquê**.
* **C2 COMPORTAMENTAL** — `cap + 3` mortes produzem exactamente `cap` respawns e depois supressão.
* **C3 ESCADA LIMITADA** — todo o atraso ≤ `no_audio_backoff_max` e uma supressão não arma timer.

**Antes da correcção (o ficheiro como estava):**

```
FAIL C1 ... it is nested inside `if self.stopped:` ... | an unconditional `return` on line 12999 precedes it
FAIL C2 6 consecutive no-audio deaths produced 6 respawn(s) and ZERO suppression:
        [15.0, 30.0, 60.0, 120.0, 240.0, 300.0] -- cap=3 was never reached
ok   C3 every scheduled delay <= 300000 ms
VERDICT: FAIL   (rc=1)
```

Repare que os atrasos do oráculo são **exactamente** os do log dele — `15, 30, 60, 120, 240, 300`. O
oráculo reproduz a máquina dele sem lhe tocar.

**Depois:**

```
ok C1 the ceiling is reachable: no `self.stopped` guard above it, no `return` before it
ok C2 6 deaths -> exactly 3 respawn(s) [15.0, 30.0, 60.0], then SUPPRESSED
ok C3 every scheduled delay <= 300000 ms
VERDICT: PASS   (rc=0)
```

**Braço negativo** (`--neg-arm`) — repõe o defeito original (bloco de volta sob `if self.stopped:`):

```
CONTROL ... VERDICT: PASS
M1 the shipped defect restored ... VERDICT: FAIL  (C1 and C2 red)
NEG-ARM VERDICT: PASS -- control GREEN, mutant RED   (rc=0)
```

Registado na segunda bateria (`_main/instruments-battery.mjs`), com os dois passos; `node --check`
rc=0 e o ficheiro mantém **CRLF=355 / bareLF=0**.

## 5. O que fica por medir (declarado, não esquecido)

* **Os 1.3-1.8 core.** O PC foi reiniciado e o Sotto não está a correr (procura por
  `python/pythonw` com `sotto_worker.py` na linha de comando: **nenhum**). Medir o spin exige lançar a
  app — que é do LEAD e é passo pesado. O que a correcção garante é o **tecto do custo**: no máximo
  **três** vidas de worker (15 + 30 + 60 s de espera), em vez das seis e a subir que o log mostra.
* **O custo de cada vida** já está medido: `BRIDGE_LOAD_MS` 4 266-11 375 ms e 8 rotações até
  `ROTATION_CEILING` (`MAX_ROTATIONS_WITHOUT_SIGNAL = 8`). Com o tecto a funcionar, o custo deixa de
  ser ilimitado.
* **A recuperação é manual por desenho:** depois da supressão, o painel diz *"Confere a rotagem
  (VoiceMeeter / som do Windows) e aperta Alt+C"*. Isso não é um bug — é a decisão certa: recarregar
  1 GB de modelo não arranja uma rotagem.

## 6. Uma correcção de log proposta (não feita)

`BRIDGE_RESTART ... restart={self.restarts}` imprime o contador da escada errada, e foi isso que fez a
queixa parecer "sem backoff". O honesto é imprimir também `no_audio_restarts=`, que é o número que
governa a escada no-audio. Não o fiz nesta passagem porque há receios de consumidores do formato;
antes de mexer, procurar quem faz parse da linha.

## O CPU: quanto, de quem, e o que o multiplicava (2026-10-22, 06:0x)

O dono descreveu o worker a **1,3-1,8 núcleos**. Medi-o com o instrumento do próprio repo, sobre um
ficheiro que já estava em disco (nada lançado agora):

```
python _main\sotto-perf-log.py --report _main\perf\sotto-perf-20261022-032626.jsonl
  records      : 49 (18 sys samples, 18 family samples, 4280 slips)
  CPU used (process time, whole run): 35.0 s (shell+worker+its webviews)
  worker   peak n=1    104.3 % cpu      1271 MB rss
  webview  peak n=7     30.6 % cpu       361 MB rss
  shell    peak n=1     19.6 % cpu       161 MB rss
  p50 0.7 ms   p90 8.3   p99 27.5   MAX 103.2
  slips > 50 ms : 4   > 100 ms : 1   > 250 ms : 0
```

**Leitura:** a média da família é **0,29 núcleos** (35,0 s de CPU em 120 s). A **soma dos picos** por papel
é **1,55 núcleos** (104,3 + 30,6 + 19,6), que é exactamente a faixa que o dono sentiu — e acontece nos
**carregamentos do modelo**, não num laço. E naquela janela a máquina não estava a engasgar por nossa
causa: 4 slips acima de 50 ms em 4280 amostras, máximo 103,2 ms.

**O que MULTIPLICAVA o custo** era a escada de respawn: com o tecto inalcançavel, cada morte do worker
recarregava 1,2-1,3 GB de pesos ao serviço de zero legendas (medido no log: 24,75 s + 16,2 s de load numa
janela em que o dispositivo estava plano). Fechado: `6 deaths -> exactly 3 respawn(s) [15.0, 30.0, 60.0],
then SUPPRESSED`.

**O que NÃO é verdade, e fica dito:** não há laço sem escape no worker nem no shell — censo AST,
`_main/worker-busy-loop-oracle.py`: os três `while True:` têm `return`/`queue.get`/`sleep`. O oráculo
declara no cabeçalho que não mede CPU e que não vê dentro de uma extensão C.
