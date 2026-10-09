# Recibo — a bateria vermelha, e o `skip-verdict-guard` que se acusava a si próprio

**Lane:** MEASUREMENT · **Data:** 2026-10-08 · **Sujeito:** `_main\_audit-verify-all.cmd`
(32 203 B, sha256 `EBF715E9E4CF75B2FF5E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C`)
**Instrumento novo:** `_main\_skip-verdict-guard.py` · **Bateria:** corrida limpa `13:39:04 → 13:42:42`

---

## 0. O par que decide (resposta curta)

```
steps    : 41   gate=30  control=9  skipped=1  expect-red=1  missing=0
BATTERY-VERDICT: GREEN WITH 1 SKIPPED - 1 step(s) did NOT verify this run and are NOT counted as gates:  hotkey-delivery
exit-code: 0
```

- **`steps :` aparece UMA única vez** (contagem medida: 1). Confirmado por dois lados:
  1 linha `steps :`, 1 banner `BATTERY SUMMARY`, 1 linha `BATTERY-VERDICT`, e **41 beacons `[step]`
  para 41 passos** — se o `cmd.exe` tivesse re-caminhado a cauda, os beacons seriam ~80.
- **`exit-code: 0`** e o processo devolveu **0** (`$LASTEXITCODE` do `cmd /c`).
- Nada falhou: `failed: -none-`.

O passo alvo, `skip-verdict-guard`, está **`rc=0`** — e não por ter sido desligado (ver §4).

---

## 1. O que o passo AFIRMA

O passo é um **`:record`** — um **gate**: o único `rc` que passa é **0**. O contrato dele, verbatim
do próprio `.cmd` (`:327-352`):

> Every step above wrote its log. An instrument that silently skips an arm and still exits 0 is a
> skip wearing a pass, and the difference is visible only in its log -- so this single sweep refuses
> the whole run if ANY step's log carries a skip verdict (`VERDICT: SKIPPED`) while that step is not
> declared skip-capable.

E o outro lado do contrato, o `:skipped` (`:412-428`), que é quem **declara** a excepção e é a única
fonte de `SKIPLOGS`:

> `* rc=0 AND the skip text(s) present -> SKIPPED: counted in `skipped=`, listed in the summary, and
> NEVER counted in `gate=`, because nothing was verified`
> `* rc=0 with NEITHER -> FAILURE. [...] an instrument that cannot say whether it verified or skipped
> must not be rounded up to a pass`

**A afirmação, em uma frase:** *depois que todo passo escreveu o seu log, UMA varredura reprova a
corrida inteira se qualquer log de PASSO carregar `VERDICT: SKIPPED` sem que o seu passo seja
declarado skip-capable.* O `SKIPLOGS` nasce `,` (`:91`) e recebe `hotkey-delivery.log` (`:236`).

**Isto é um gate, NÃO um `:expectred`.** Nada no contrato dele exige `rc=1`; ele exige `rc=0` e falha
a corrida quando encontra uma violação. A classificação **não foi tocada**.

---

## 2. O defeito: o instrumento lia o SEU PRÓPRIO transcrito

O passo era um `python -c` inline que varria `%OUT%\*.log` excluindo apenas o prefixo `_run-`.
Mas o **console da própria bateria** fica em `%OUT%` com o nome `_battery-run-<ts>.log` — e o
`:skipped` **ecoa o texto do skip no seu beacon**:

```
[step] hotkey-delivery rc=0  [SKIPPED] NOT VERIFIED: the instrument itself says this arm did not run, its own words being VERDICT: SKIPPED
```

Esse echo contém a agulha `VERDICT: SKIPPED` **verbatim**. O guarda então acusava o console de si
mesmo, nomeando `_battery-run-20261007-130942.log` e `_battery-run-20261007-131528.log`.

**Consequência, e é o que importa:** era um **falso positivo que é RED independentemente do
comportamento dos passos**, e **auto-perpetuante** — cada corrida escreve um novo console que
rearma a acusação. O `_run-` do prefixo antigo era uma forma mais estreita da mesma ideia, e
**não cobria o nome sob o qual o console é de facto guardado**.

**Não era um `:expectred` disfarçado, e não era o passo a fazer o trabalho dele.** Era o instrumento
a olhar para o sítio errado.

---

## 3. As duas cores, medidas com o instrumento NOVO

### VERDE — o directorio varrido a sério

```
python H:\sotto\_main\_skip-verdict-guard.py --dir "H:\sotto\_main\_audit-verify" --exclude ",hotkey-delivery.log,"
```
```
cadence : once, after every step has written its log
dir     : H:\sotto\_main\_audit-verify
needle  : VERDICT: SKIPPED
exclude : ['hotkey-delivery.log']
PASS ARM-C1 an UNDECLARED skip verdict is CAUGHT
PASS ARM-C2 the battery own run console is NOT read (the self-reference)
PASS ARM-C3 a DECLARED skip log is not a violation
PASS ARM-C4 a clean log is not a violation
PASS ARM-C5 the sweep really read the files (not a vacuous green)
SKIP-GUARD-CONTROL: PASS (5/5)
step logs READ : 64
NOT read (battery artifacts, "_" prefix) : 16
NOT read (declared skip-capable)         : 1
no skip verdict outside the declared skip step(s)
SKIP-GUARD-VERDICT: GREEN - 64 step log(s) read, no undeclared skip verdict, control RED where it must be
```
**rc = 0.** 64 logs de passo lidos, 16 artefactos `_`-prefixados (incluindo os dois
`_battery-run-*.log`) correctamente **não** lidos, e 1 log declarado como skip.

### VERMELHO — a fixture permanente

```
python H:\sotto\_main\_skip-verdict-guard.py --dir "H:\sotto\_main\_skip-guard-redcheck" --exclude ","
```
```
PASS ARM-C1 ... PASS ARM-C5
SKIP-GUARD-CONTROL: PASS (5/5)
step logs READ : 2
NOT read (battery artifacts, "_" prefix) : 1
NOT read (declared skip-capable)         : 0
SKIP-VERDICT IN THE LOG OF A STEP THAT IS NOT DECLARED SKIP-CAPABLE: bogus-step.log
SKIP-GUARD-VERDICT: RED - 1 undeclared skip verdict(s) in 2 step log(s)
```
**rc = 1.** A fixture `_main\_skip-guard-redcheck\` tem três ficheiros:
`bogus-step.log` (85 B — o passo que faz skip sem o declarar), **`_battery-run-fake.log` (76 B —
o MESMO texto, com prefixo `_`)** e `clean-step.log` (36 B). O veredicto nomeia **só** o
`bogus-step.log`: o console falso **não** foi lido. É essa a assimetria que prova que a regra nova
distingue um log de passo de um transcrito de corrida.

### Porque é que o verde não é vazio

As **cinco** armas de controlo correm em **toda** a invocação, e o instrumento sai **2** se alguma
se portar mal. `ARM-C1` injecta uma violação sintética e exige que seja apanhada; `ARM-C2` prova que
o console da bateria não é lido; `ARM-C5` prova que a varredura leu ficheiros a sério. **Um verde
por não olhar para nada é impossível: dá exit 2.**

---

## 4. O que foi mudado, e porquê

| # | artefacto | mudança | porquê |
|---|---|---|---|
| 1 | `_main\_skip-verdict-guard.py` | **NOVO instrumento** (só ASCII, `argparse`, `--dir`, `--exclude`, `--control-only`). Predicado: **um LOG DE PASSO é um `*.log` cujo basename NÃO começa por `_`** e não está em `--exclude`. 5 armas de controlo sempre ligadas. Saída: **0** limpo+controlo PASS, **1** skip não declarado, **2** controlo mal comportado | tira a decisão de dentro de um one-liner e dá-lhe um predicado declarado e um controlo não-vacuidade |
| 2 | `_main\_audit-verify-all.cmd` `:327-352` | o `python -c` inline → `python _main\_skip-verdict-guard.py --dir "%OUT%" --exclude "!SKIPLOGS!" > "%OUT%\_skip-guard.log" 2>&1`, com `call :record skip-verdict-guard MISSING` no ramo `else` | passa a haver um instrumento nomeado, com log próprio; instrumento ausente continua a ser FALHA |
| 3 | `_main\_audit-verify-all.cmd` cabeçalho + bloco REM | o texto do contrato passou a dizer **STEP** log, e 3 linhas REM novas documentam o defeito de auto-referência e a regra `_` | o próximo leitor não volta a estreitar o prefixo |
| 4 | `_main\_skip-guard-redcheck\` | **NOVO** fixture vermelho permanente | o vermelho fica reproduzível para sempre, sem depender do estado da árvore |

**O que NÃO foi mudado, deliberadamente:**

- **O `kind` do passo continua `:record`.** Não foi reclassificado para `:expectred` — o contrato dele
  nunca pediu `rc=1`.
- **O guarda nunca foi desligado, comentado, nem removido.** A cura preserva uma arma negativa a
  funcionar: o guarda é **a única coisa que torna "SKIP não é um passe" executável** neste repo.
- **A classificação de `hotkey-delivery` como `:skipped` não foi tocada.** É um skip **real,
  declarado e correctamente tratado** (o Alt+C está na mão do shell vivo do dono, pid 28428,
  `winerror=1409`).

**Duas verdades de skip que não se podem confundir:** (a) `hotkey-delivery.log` — skip real,
declarado; (b) `_battery-run-*.log` — o echo do console da bateria, que **não é o log de um passo**.

---

## 5. Impressão digital do `.cmd` — antes e depois

| momento | len | CRLF | bare LF | sha256 | mtime |
|---|---|---|---|---|---|
| **antes** da corrida | 32 203 | 538 | 0 | `EBF715E9E4CF75B2FF5E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C` | 2026-10-07 13:32:33 |
| **depois** da corrida | 32 203 | 538 | 0 | `EBF715E9E4CF75B2FF5E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C` | 2026-10-07 13:32:33 |

**A corrida está LIMPA: o sha256 não mudou durante a corrida — não houve edição concorrente.**
O ficheiro continua **100 % CRLF, 0 bare LF**. É por isso que a contagem de `steps :` igual a 1 é
significativa e não um artefacto de offset.

**Histórico de tamanho (a deriva é real, não reutilizar números antigos):**
`18 595 B` (o que o `AGENTS.md` ainda cita) → `31 071 B` (a revisão que a lane `strip` apanhou a mudar
a meio de uma corrida) → **`32 203 B`** hoje.

---

## 6. A bateria inteira, hoje — o log verbatim

Console: `_main\_battery-run-20261007-133904.log` (4 724 B), stderr `0 B`.
Resumo: `_main\_audit-verify\_battery-summary.txt`.

```
=============== BATTERY SUMMARY ===============
steps    : 41   gate=30  control=9  skipped=1  expect-red=1  missing=0
failed   : -none-
skipped  :  hotkey-delivery
BATTERY-VERDICT: GREEN WITH 1 SKIPPED - 1 step(s) did NOT verify this run and are NOT counted as gates:  hotkey-delivery
```

Os dois passos que eram vermelhos hoje de manhã:

```
[step] strip-geometry-restore rc=0
[step] skip-verdict-guard rc=0
```

**`strip-geometry-restore` — verificado como NÃO vazio.** O passo corre
`_main\_strip-restore-probe.py`, que **não imprime nada** (por isso `strip-restore.log` tem 0 B) e
escreve o veredicto em `_main\_strip-restore-probe.json`. Esse JSON foi reescrito **durante esta
corrida** (mtime `2026-10-07 13:42:04`, stamp `7736-1791391293`):

```
"verdict": "GREEN",  "failed": [],  "file_restored": true
in-bounds  : PANEL_GEOMETRY_RESTORED surface=strip rect=1040x148@(700,400) clamped=false   → ok
off-screen : PANEL_GEOMETRY_RESTORED surface=strip rect=1040x148@(880,884) clamped=true    → ok
             PANEL_GEOMETRY_CLAMPED  was=1040x148@(5000,5000) now=1040x148@(880,884) work=1920x1032@(0,0)
```

6/6 checks `ok`, `failed: []`, e as duas armas (in-bounds `clamped=false` / off-screen
`clamped=true`) a comportarem-se. **É o `rc=0` de um gate que olhou para alguma coisa.**

O `strip-geometry-restore=3` de hoje de manhã era a corrida com o app do dono, que reescreve
`_main/panel-visibility.json` **sem** a chave `geometry` a cada ~3 s. A lane `strip` corrigiu a sonda
(o seed é escrito logo a seguir a uma escrita dele) e ela dá **GREEN 6/6 sozinha** — confirmado aqui
**dentro da bateria**.

---

## 7. O que continua RED

**Nada falhou nesta corrida: `failed: -none-`, `exit-code: 0`.** Duas coisas que **não** são passes e
não devem ser lidas como tal:

1. **`hotkey-delivery` está SKIPPED** — declarado, `rc=0`, contado em `skipped=1` e **nunca** em
   `gate=`. Nada foi verificado nesse braço. O `BATTERY-VERDICT` di-lo em voz alta em vez de o
   arredondar para verde.
2. **`red-as-expected-historico-gate-off rc=1`** é um `:expectred` a **comportar-se**: `rc` é
   **exactamente 1** e o defeito foi nomeado. Não é uma falha; é o único passo que **deve** sair
   diferente de zero.

Nenhum RED residual atribuível a esta lane. O `steps : 41` de hoje contra o `steps : 29` citado no
`AGENTS.md` **não é contradição**: aquele é um número datado de uma revisão anterior, e as outras
lanes acrescentaram passos desde então.

---

## 8. `AGENTS.md` — as linhas acrescentadas (as únicas escritas fora de `_main\`)

O ficheiro é **100 % LF** e assim ficou: **76 323 B, 0 CRLF / 853 bare LF**, sha256
`0529104427D98861E432E555B9BD96FF5CBC7C1AF088F368204DDBEB560745B5`. Sempre com `edit`
(nunca `write`), que **preserva** os finais de linha.

1. **A segunda causa do duplo percurso** — o bullet da bateria ganhou o parágrafo
   *"AND CRLF IS NOT ENOUGH — A SECOND CAUSE, PROVEN 2026-10-08: A CONCURRENT EDIT OF THE FILE
   MID-RUN"*, com as duas armas do reprodutor (`_main\_cmd-offset-drift\subject.cmd`), o
   `28 947 → 31 071 B` da lane `strip`, a regra *"a run whose `.cmd` sha256 changes mid-run is DIRTY:
   say so and repeat it"*, o histórico de tamanhos e a nota `edit` preserva CRLF / `write` emite só LF.
2. **A armadilha do `pip` a ensombrar o namespace** — bullet novo, **verbatim da §6.1 de
   `_main\receipt-execution-providers.md`**, inserido depois do bullet "THE LIVE ENGINE IS HYBRID".
   **É aditivo, não contradiz nada que já lá estivesse.** O vizinho mais próximo é o bullet do
   `cublasLt64_13.dll` / WinError 126, e os dois modos de falha são **distintos** — lá o provider é
   *listado* e falha a inicializar; aqui **não é listado de todo** e o erro é `null`. O bullet novo
   di-lo explicitamente. Acrescentei também a regra das três perguntas: `get_available_providers()`
   = o que o **pacote** suporta; `InferenceSession.get_providers()` = o que a **sessão** usa; só o
   profiler do ORT diz o que **executa**.

> **Nota para quem lê:** o `AGENTS.md` já **excede o orçamento de 65 536 B** de instruções do
> workspace (76 323 → truncado a ~65 143). A cauda é truncada para os leitores — manter adições
> futuras curtas.

---

## 9. Armadilhas de ferramenta provadas hoje

- **`write` emite só LF.** Nunca usar no `.cmd` (as subrotinas são alcançadas por **offset de byte**;
  deriva de offsets → a lista de passos corre duas vezes). O `edit` **preserva** o que lá está.
- **O `-replace` do PowerShell não tem `Multiline` por omissão** — `^` casa só na posição 0. Uma
  "mutação" que é silenciosamente um no-op produz um resultado falso: **afirmar que a mutação mudou
  os bytes ANTES de ler o resultado** (aconteceu nesta sessão; a segunda tentativa, válida, provou o
  mecanismo: `919 → 964 B`, `'xit' não é reconhecido como um comando interno`, cauda re-corrida).
- **O `edit` exige um `read` prévio do alvo nesta sessão** — a primeira tentativa no `AGENTS.md` foi
  recusada, e passou depois do `read`.
- **O `read` não lê `hotkey-delivery.log`** (`invalid UTF-8`) — usar
  `[System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes(...))`.
- **Um caminho mal copiado parece um ficheiro desaparecido.** `strip-restore-probe.json` "não
  existia"; o nome real é **`_strip-restore-probe.json`**. Um `Get-Item` falhado não é prova de
  ausência — é prova de que o caminho está errado até se provar o contrário.

---

## 10. Reprodutibilidade

```
# o par que decide
cmd /c "H:\sotto\_main\_audit-verify-all.cmd > H:\sotto\_main\_battery-run-<ts>.log 2>&1"
type H:\sotto\_main\_audit-verify\_battery-summary.txt

# o guarda, as duas cores
python H:\sotto\_main\_skip-verdict-guard.py --dir "H:\sotto\_main\_audit-verify" --exclude ",hotkey-delivery.log,"   # rc 0
python H:\sotto\_main\_skip-verdict-guard.py --dir "H:\sotto\_main\_skip-guard-redcheck" --exclude ","                 # rc 1
```

**Limites, declarados:** a corrida foi feita com 5 outras lanes a editar a árvore. O `.cmd` **não**
mudou durante a corrida (sha256 idêntico antes/depois), por isso esta corrida é limpa — mas os logs
de passo de outras lanes podem ter mudado de conteúdo a meio. O que este recibo prova é o par
`BATTERY-VERDICT`/`exit-code` daquela janela de 13:39:04–13:42:42, com a contagem de `steps :`, e as
duas cores do guarda.
