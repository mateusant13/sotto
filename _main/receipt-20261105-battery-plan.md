# O plano da bateria — um processo responde por 341 passos

**Data:** 2026-11-05 · **Instrumento:** `_main/_battery-plan.py` (novo) ·
**Mutado:** `_main/_audit-verify-all.cmd` (`:step`, setup, subrotinas `:plan_load` / `:plan_lookup`, sumário)

## O defeito, medido

A `.cmd` perguntava ao cache **um passo de cada vez**, com um `python` novo por passo
(`for /f ... in ('python _main\_stepcache.py check ...')`). Medido nesta máquina, sobre um passo
**já cacheado**, seis invocações:

```
min 0,124 s   max 0,150 s por passo     ->  341 passos = 42,3 a 51,2 s
```

Numa corrida **a quente** — em que nada tem de executar — a bateria gastava dezenas de segundos a
criar interpretadores que leem **o mesmo** `_cache\battery-steps.json` e dizem `HIT`. O alvo da casa
é 60 s; isto era a maior parte dele em dispensa, não em prova.

## A cura

1. `_main/_battery-plan.py` lê as declarações `call :step ...` **do próprio `.cmd`** (a gramática tem
   uma só definição na casa: `STEP_RE`, de `_main/sotto-state-page.py`, importada — dois regexes para
   a mesma linha divergiriam em silêncio), carrega o estado **uma vez**, responde a todos os passos
   **no mesmo processo** e escreve `_main\_audit-verify\_battery-plan.txt`.
2. `:step` lê a resposta de uma variável (`:plan_lookup`); um passo **ausente** do plano cai no
   caminho por passo, que continua a ser a autoridade. Falta de resposta = MISS, **nunca** HIT.
3. `DEFER`: um passo cujas deps incluem o **próprio ficheiro de estado** (que esta corrida reescreve)
   não entra no plano — o loader deixa-o de fora e ele responde no instante em que corre. São 5 hoje.
4. `SOTTO_BATTERY_PLAN=0` devolve o caminho por passo. Um plano é uma cache de **decisões**, e uma
   decisão errada tem de ter para onde voltar.

## Medido

| | antes | depois |
|---|---|---|
| dispensa do cache (341 passos) | 42–51 s (341 spawns) | **1,84 s** (1 processo) |
| respostas | 341 spawns | 184 HIT · 152 MISS · 5 DEFER |

`--selftest` (PASS) compara o plano contra o CLI `check`, um a um, sobre as quatro formas que
existem — HIT, `always`, lento (fast mode) e MISS por dep alterado — nos dois modos, e exige que o
plano **decida** (`hits=2` normal, `hits=1` rápido). Um plano que respondesse MISS a tudo passaria
um teste que só comparasse "não crashou".

`--neg-arm` (PASS, sai 1): três mutações plantadas numa **cópia**, cada uma derrubada pela sua arm —

* `hit-inventado` — `if hit:` → `if True:`, um HIT fabricado;
* `defer-apagado` — a regra do DEFER desligada (o plano passaria a adivinhar sobre um ficheiro que a
  corrida reescreve);
* `skip-slow-apagado` — o modo rápido ignorado.

## Prova diferencial (a que conta)

Duas corridas na mesma árvore, `_main\_audit-verify\_plan-summary-off.txt` e `_plan-summary-on.txt`,
com `SOTTO_BATTERY_PLAN=0` e `=1`:

| | plano OFF | plano ON |
|---|---|---|
| parede | **850,0 s** | **765,9 s** |
| steps / gate / control / expect-red / skipped / missing | 343 / 179 / 8 / 137 / 19 / 0 | **igual** |
| falhas | `red-as-expected-youtube-cdp-slow` | **a mesma** |
| `cached=` | 175 | 187 |
| plano reconstruído no arranque | — | **sim** (idade do ficheiro ≈ 2 s no fim de uma corrida de 766 s) |

O ganho de 84 s inclui a vantagem de ordem (a segunda corrida executa menos: 187 passos cacheados
contra 175), por isso o número **que mede o mecanismo** é o outro, medido directamente: **341 spawns
a 0,124-0,150 s = 43 s** contra **um processo a 1,84 s**. O delta de parede é o que se vê de fora; o
mecanismo é o que se mede por dentro.

O mesmo veredicto nos dois lados é o que importa: **o plano não mudou nenhuma decisão** — mudou quem
as toma.

## Pin

`_main\_audit-verify-all.cmd` passou de **260779 B / 3196 CRLF** para **265171 B / 3267 CRLF**
(0 bare LF), sha256 `2E67B21B1F51D67293327D0EDC5155BFDCB2635841935D42E714FC372DA59870`. O pin do
`AGENTS.md` foi re-medido no mesmo commit (`_main/agents-md-pins-oracle.py` PASS).

Dois passos novos, ambos `always`: `battery-plan` (`--selftest`) e `red-as-expected-battery-plan`
(`--neg-arm`).

## De quebra: seis passos vermelhos apanhados por esta corrida

A corrida anterior (19:40–20:02) fechou **RED com 8 falhas**. Duas eram da minha própria autoria em
voo; as outras seis eram defeitos reais nos instrumentos, e cada uma tem a sua causa:

| passo | causa medida | cura |
|---|---|---|
| `historico-vs-redux-probe` | o regex exigia `HISTORY_REFUSED reason=provisional-draft` **numa linha** e a shell publica `where=history_append` no meio (o texto do log está partido em três linhas do fonte). O braço julgava FORMATACAO, não comportamento | regex julga a **ordem** (guarda → testemunha → `return None`) com folga; probe GREEN |
| `red-as-expected-worker-churn` | a âncora do mutante era `"PROGRESS['seq'] += 1\r\n"` e o worker está em **LF**: o mutante não se plantava e o `--neg-arm` morria em `AssertionError` em vez de julgar | âncora por regex `\r?\n`; rc=1 |
| `red-as-expected-punct-model` | o oráculo imprimia `NEG-ARM PASS` (sem dois-pontos) e o passo procura `NEG-ARM: PASS` | linha final no formato da casa; rc=1 |
| `red-as-expected-live-queue` | (1) o `finally` fazia `sys.path.remove(tmp)` mesmo quando o mutante nunca foi escrito → `ValueError` matava o passo inteiro e escondia os outros mutantes; (2) a âncora do mutante `if is_alive(pid):` ficou velha quando a guarda passou a `if pid is None or pid == keep or is_alive(pid):` | `remove` guardado por `if tmp in sys.path`; mutante tira a pergunta de liveness e mantém o resto — 50/50 arms, `NEG-ARM PASS`, rc=1 |
| `code-health` | `app/webview/youtube_cdp_source.py` cresceu (63492→63669 B, 1340→1342 linhas) com o backoff do CDP | crescimento **declarado** no baseline (o ratchet absorve o declarado) |
| `console-window-audit` | `_main/_battery-when-green.py` largava o gate com `creationflags` **só** (o flag "fraco"): invisível de um terminal, visível para o dono em `pythonw` | passa pelo `_main/hidden-launch.py` (a `CREATE_NO_WINDOW` **e** `STARTUPINFO`/`SW_HIDE`); `CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s)` |

A lição que se repete em quatro delas: **uma âncora de mutante e um texto de veredicto são
afirmações com prazo de validade** — o alvo muda, o oráculo continua a correr e a falar de si mesmo.
