# Sotto — WIRE the route-stamp gate, and close its TEXT-ONLY gap

Lane: `SottoProbeWiring` · 2026-10-07 · alvo **`H:/sotto`** (nada foi escrito fora do repo).
Origem: `_main/route-stamp-gate-20261006.md` — essa lane landou `_main/route-stamp-gate.js` (GREEN
`8/8` rc=0; RED `7/8` rc=1, so' a `G3`) e deixou **dois buracos abertos de proposito**. Esta fecha os
dois. Nada do motor foi editado: a mutacao do painel vive numa COPY descartavel.

---

## 0. VEREDICTO

1. **WIRED.** Os TRES probes da classe estao agora invocados pelo
   `_main/_cura-oracle-suite.py` — `route-stamp-gate`, `historico-vs-redux-probe` e
   `panel-live-vs-history-probe` — cada um **GREEN** na propria suite
   (`SUITE: GREEN=3`, rc 0). Antes desta lane `grep -rn route-stamp-gate` so' devolvia as
   strings do proprio gate: **nenhum invocador existia**.
2. **TEXT-ONLY GAP FECHADO.** O gate ganhou a arm **`G4 PANEL CHOKE`**, que compara a guarda do
   `panel.js` por **FORMA normalizada** (comentarios removidos, espacos colapsados) em vez do
   `includes()` byte-a-byte de antes — e traz consigo o seu proprio vermelho: a MESMA check sobre uma
   COPY com `|| 'final'` restaurado e' RED, no MESMO comando. `GATE: PASS — 11/11` (rc 0) no ficheiro
   live; `GATE: RED — 10/11` (rc 1) com a copy, e **exactamente uma arm** vira RED: a `G4`.

O `panel.js` LIVE nunca foi aberto para escrita: `sha256` identico antes e depois
(`135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962`).

---

## 1. CHANGE 1 — WIRE os tres probes

### 1.1 O mecanismo, medido no codigo em frente

| onde | o que faz |
|---|---|
| `_main/_cura-oracle-suite.py:73` | corre cada oraculo com `subprocess.run([PY] + argv, cwd=REPO, ...)` |
| `_main/_cura-oracle-suite.py:56` | `VERDICT = {0:"GREEN", 1:"RED", 2:"UNRUNNABLE"}` |
| `_main/_cura-oracle-suite.py:83-85` | imprime `[VERDICT] name rc=... wall=...s` + as ultimas 6 linhas do stdout |

Os tres probes sao **binarios `node`**. A suite invoca `[PY] + argv`, logo cada linha atravessa para
o `node` por um wrapper `-c`, que **propaga o rc do node** — e os tres ja' usam a convencao que a
suite espera (0/1/2; docs nos proprios ficheiros: `historico-vs-redux-probe.js:38`,
`panel-live-vs-history-probe.js:32`). A forma foi MEDIDA na lane de origem
(`py -3 -c "…subprocess.call(['node','_main/route-stamp-gate.js'],cwd=r'H:/sotto')"` → rc 0,
receipt:301-320), nao suposta.

### 1.2 A mudanca — `_main/_cura-oracle-suite.py:51-66` (TRES linhas, o MESMO molde)

```python
    # ── the NODE probes ──────────────────────────────────────────────────────
    # A gate nobody runs is this house's most-repeated defect: the three `.js`
    # probes below were each RED-able and each invoked by NOBODY (`grep -rn`
    # found only their own strings). The suite runs `[PY] + argv` (see the
    # subprocess.run below) and maps rc 0/1/2 to GREEN/RED/UNRUNNABLE, so each
    # node probe is invoked THROUGH the interpreter, which propagates node's
    # exit code. `cwd=` is the repo root the suite already runs every oracle in.
    ("route-stamp-gate",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/route-stamp-gate.js'],cwd=r'H:/sotto'))"],
     120),
    ("historico-vs-redux-probe",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/historico-vs-redux-probe.js'],cwd=r'H:/sotto'))"],
     120),
    ("panel-live-vs-history-probe",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/panel-live-vs-history-probe.js'],cwd=r'H:/sotto'))"],
     120),
]
```

`route-stamp-gate` entrou **verbatim** como o brief o deu (`:58-60`); as duas sondas-irmas usaram o
**mesmo molde de uma linha** porque ele lhes assenta 1:1 (mesmo runtime, mesma convencao rc, mesmo
`cwd=REPO`). Nada mais da suite foi tocado.

### 1.3 O invocador EXISTE agora (a prova, com linha)

`_main/_cura-oracle-suite.py:58`, `:61`, `:64` — antes nao existia nenhum (`grep -rn route-stamp-gate`
so' devolvia `_main/route-stamp-gate.js:*`).

### 1.4 A SUITE corre e reporta GREEN (verbatim — a linha de cada linha, e o total)

```
$ cd H:/sotto && py -3 _main/_cura-oracle-suite.py --only route-stamp-gate,historico-vs-redux-probe,panel-live-vs-history-probe --out _main/_cura-oracle-suite-node-probes.json ; echo "SUITE rc=$?"
[     GREEN] route-stamp-gate                 rc=0 wall=0.5s
             |        real = false
             |        want = false
             | [PASS] CONTROL: the panel mutant bit the panel source exactly once (the check is not vacuous)
             |        real = {"panelChanged":true,"panelMatches":1}
             |        want = {"panelChanged":true,"panelMatches":1}
             | GATE: PASS — 11/11 arm(s) (live GREEN, and every arm RED on its own mutation)
[     GREEN] historico-vs-redux-probe         rc=0 wall=0.3s
             |        real = true
             |        want = true
             | [PASS] guard present — sotto_webview.py history_append declines a provisional-draft
             |        real = true
             |        want = true
             | RESULT: GREEN — the transcript carries only the worker-closed line
[     GREEN] panel-live-vs-history-probe      rc=0 wall=0.4s
             |        real = true
             |        want = true
             | [PASS] control: the two values DIFFER (the probe is not vacuous)
             |        real = true
             |        want = true
             | RESULT: GREEN — 9/9 arm(s)
SUITE: GREEN=3
receipt: _main/_cura-oracle-suite-node-probes.json
SUITE rc=0
```

`--only` foi usado com um `--out` PROPRIO (`_main/_cura-oracle-suite-node-probes.json`) para **nao
clobberar** o recibo da suite completa (`_main/_cura-oracle-suite.json`). O `route-stamp-gate` reporta
`rc=0` e verdict **GREEN**; as duas sondas-irmas tambem. A suite completa NAO foi corrida: os oraculos
`segment-rerun-probe`, `speech-gate-oracle` e `delivery-rate-oracle-wav` declaram timeouts de 420 s
cada e puxam CUDA/endpoints que esta lane nao tem razao para tocar — o brief pede a linha do row, e a
linha do row esta' acima.

---

## 2. CHANGE 2 — o gap TEXT-ONLY: a arm `G4 PANEL CHOKE`

### 2.1 O buraco, com `file:line` (nomeado pelo proprio receipt da lane de origem, SELF-AUDIT `falta-no-gate`)

O gate `8/8` original afirmava a guarda fail-closed do `panel.js` **so' por TEXTO**, com duas
comparacoes byte-a-byte (`_main/route-stamp-gate.js`, versao anterior, main()):

```js
const PANEL_FAIL_CLOSED = "if (route !== 'final') return;";
const PANEL_PERMISSIVE = "const route = (meta && meta.route) || 'final';";
```

Duas fraquezas MEDIDAS:

1. **Um `panel.js` que readquira `|| 'final'` de forma DIFERENTE** (espacos, quebra de linha, aspas)
   nao e' apanhado: o `includes()` procura a string exacta. Um `panel.js` que volta ao default
   permissivo por outra forma fica **GREEN** — o cenario que o receipt de origem nomeia.
2. **A comparacao byte-a-byte e' errada nos DOIS sentidos.** O proprio COMENTARIO da cura
   (`app/electron/panel.js:331-334`) escreve `(meta && meta.route) ||` e `'final'` em duas linhas de
   comentario. Um `includes("|| 'final'")` sobre o ficheiro CRU casaria o COMENTARIO — punha um painel
   fail-closed a RED. (A string exacta `const route = (meta && meta.route) || 'final';` nao aparece no
   comentario, por isso o codigo antigo passava; mas por sorte, nao por desenho.)

E, sobretudo, o antigo era um **SETUP ERROR rc 2** (`return 2`), nao uma arm: uma regressao desse tipo
nao acendia o gate — mandava a suite a `UNRUNNABLE`.

### 2.2 A mudanca — a guarda e' comparada por FORMA, e ganha o seu proprio vermelho

`_main/route-stamp-gate.js`:

| onde | o que faz |
|---|---|
| `:97-104` | novo surface `--panel <path>` (default `app/electron/panel.js`), como `--engine` ja' fazia |
| `:116-125` | `PANEL_TEST = "if (route !== 'final') return;"` e `PANEL_ASSIGN_RE = /const route = ([^;]*);/` |
| `:184-192` | `withPermissivePanel(src)`: a COPY com a ATRIBUICAO trocada pelo default pre-cura, **1 match exigido** |
| `:195-221` | `panelGuardVerdict(src)`: NORMALIZA (tira comentarios `//`, colapsa espacos) e exige **as duas metades** |
| `:306-334` | le o painel sob teste + o painel LIVE (fonte do controlo); `--emit-panel-mutant` escreve a copy |
| `:407-409` | a linha de banner passa a mostrar `choke(assignment=… test=… fail-closed=…)` |
| `:457-462` | a arm `G4` + os DOIS controlos |

O predicado, verbatim (`:212-221`):

```js
function panelGuardVerdict(src) {
  const n = src.split(/\r?\n/).map((l) => l.replace(/\/\/.*$/, '')).join('\n')
    .replace(/\s+/g, ' ').trim();
  const assigns = n.match(new RegExp(PANEL_ASSIGN_RE.source, 'g')) || [];
  const m = PANEL_ASSIGN_RE.exec(n);
  const assignment = assigns.length === 1 && m ? m[1] : null;
  const test = n.includes(PANEL_TEST);
  const failClosed = assigns.length === 1 && test && !/['"]final['"]/.test(assignment);
  return { assignment, test, failClosed };
}
```

**Fail-closed exige as duas metades:** o TESTE e' exactamente `if (route !== 'final') return;`, e a
ATRIBUICAO nao carrega o literal `'final'` (o que o receipt de origem pediu como "nao contenha
`|| 'final'`"; exigir o literal AUSENTE e' um pouco mais forte e apanha tambem `const route = 'final';`
— ver SELF-AUDIT `gate-melhor`). Uma guarda que **nao pode ser LIDA** (atribuicao ausente ou
ambigua) reporta `failClosed:false`: e' RED, nunca passe vacuo. A normalizacao e' o que impede o
COMENTARIO da cura de falso-vermelhar o painel.

### 2.3 GREEN — contra o painel LIVE (verbatim)

```
$ cd H:/sotto && node _main/route-stamp-gate.js ; echo rc=$?
…
panel     : app\electron\panel.js   choke(assignment="meta && meta.route" test=true fail-closed=true)
…
[PASS] G4 PANEL CHOKE: `panel.js recordHistory` is FAIL-CLOSED (guard normalised, not byte-matched)
       real = true
       want = true
[PASS] CONTROL: the SAME panel check on the pre-cure guard (`|| 'final'` restored) is RED — the named regression
       real = false
       want = false
[PASS] CONTROL: the panel mutant bit the panel source exactly once (the check is not vacuous)
       real = {"panelChanged":true,"panelMatches":1}
       want = {"panelChanged":true,"panelMatches":1}

GATE: PASS — 11/11 arm(s) (live GREEN, and every arm RED on its own mutation)
rc=0
```

(log completo: `_main/_route-stamp-gate-wiring-green.txt`.)

### 2.4 RED — a arm `G4` na COPY com `|| 'final'` restaurado (verbatim)

```
$ cd H:/sotto && node _main/route-stamp-gate.js --emit-panel-mutant _main/_panel-red-copy.js ; echo rc=$?
WROTE H:\sotto\_main\_panel-red-copy.js
  the panel `|| 'final'` pre-cure COPY (the live panel is untouched)
  run it RED:  node _main/route-stamp-gate.js --panel _main\_panel-red-copy.js
rc=0

$ diff app/electron/panel.js _main/_panel-red-copy.js ; echo "diff rc=$?"
335c335
<   const route = meta && meta.route;
---
>   const route = (meta && meta.route) || 'final'; /* GATE-MUTANT-PANEL: the pre-cure guard */
diff rc=1

$ node _main/route-stamp-gate.js --panel _main/_panel-red-copy.js ; echo rc=$?
panel     : _main\_panel-red-copy.js   choke(assignment="(meta && meta.route) || 'final'" test=true fail-closed=false)   === PANEL UNDER TEST: NOT the live file (app\electron\panel.js) — its arm is expected RED ===
…
[FAIL] G4 PANEL CHOKE: `panel.js recordHistory` is FAIL-CLOSED (guard normalised, not byte-matched)
       real = false
       want = true
[PASS] CONTROL: the SAME panel check on the pre-cure guard (`|| 'final'` restored) is RED — the named regression
       real = false
       want = false
[PASS] CONTROL: the panel mutant bit the panel source exactly once (the check is not vacuous)
       real = {"panelChanged":true,"panelMatches":1}
       want = {"panelChanged":true,"panelMatches":1}

GATE: RED — 10/11 arm(s)
rc=1
```

(log completo, 50 linhas: `_main/_route-stamp-gate-panel-red.txt`.) **A COPY difere do live em UMA
linha** (335 — a atribuicao). A COPY foi apagada depois da demo; o gate re-gera-a a qualquer altura com
`--emit-panel-mutant`, a partir do ficheiro live.

### 2.5 O emit RECUSA escrever sobre o painel live (o guarda do proprio gate)

```
$ node _main/route-stamp-gate.js --emit-panel-mutant app/electron/panel.js ; echo "refuse rc=$?"
SETUP ERROR: --emit-panel-mutant refuses to write over the live panel
refuse rc=2

$ sha256sum app/electron/panel.js       # depois da recusa: 135f9f6e… (IDENTICO)
135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962  app/electron/panel.js
```

### 2.6 O RED do MOTOR continua a funcionar (nao regredi a arm `G3`)

```
$ node _main/route-stamp-gate.js --emit-mutant _main/_route-stamp-red-copy.js >/dev/null 2>&1
$ node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js ; echo "engine-red rc=$?"
…
[FAIL] G3 THE ARM: a stream with NO `final` key writes NOTHING on disk
…
[PASS] G4 PANEL CHOKE: `panel.js recordHistory` is FAIL-CLOSED (guard normalised, not byte-matched)
…
GATE: RED — 10/11 arm(s)
engine-red rc=1
```

`G3` vira RED pelo mutante do motor e `G4` fica GREEN (o painel e' o live) — as duas arms sao
independentes, cada uma com o seu proprio mutante.

---

## 3. FICHEIROS TOCADOS E `sha256` (antes → depois)

| ficheiro | accao | sha256 ANTES | sha256 DEPOIS |
|---|---|---|---|
| `_main/route-stamp-gate.js` | **EDITADO** (surface `--panel`, arm `G4` + 2 controlos, guarda normalizada) | `d86a1b80d003cb4ba7097450a1e52e278b7b3a72eb54a9a6d94a485accae93ea` | `774f6c35e8ee762bd0348e2c5c3ba99bb55428033e16860b6365e76d0ce729c9` |
| `_main/_cura-oracle-suite.py` | **EDITADO** (3 linhas em `ORACLES`, `:51-66`) | `aeedb1dc59e766e0f34b073e8a9e02d5a95b1faa461db0cc2478df2a5d3e89e0` | `f16109b0ea10ef355352669d02fbfe7cd3fbbb669f49031d7ec47583e04c0c1f` |
| `app/electron/panel.js` | **NAO TOCADO** (so' lido; a mutacao vive na copy) | `135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962` | `135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962` |
| `app/electron/caption-formulation.js` | NAO TOCADO | `c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83` | `c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83` |
| `app/electron/history-store.js` | NAO TOCADO | `536160b3b11c62d2efeb2bf424bb9fcb9ded30d9b8802d0799c416f92d6979af` | `536160b3b11c62d2efeb2bf424bb9fcb9ded30d9b8802d0799c416f92d6979af` |
| `_main/_route-stream-long.jsonl` | NAO TOCADO | `3a54609d5d4db219204ac657a93b6d6b992cf4417e9cb17cb34febc9979e2af3` | `3a54609d5d4db219204ac657a93b6d6b992cf4417e9cb17cb34febc9979e2af3` |
| `_main/route-stamp-gate-wiring-20261006.md` | **NOVO** (este recibo) | — | nao tem auto-hash honesto (o proprio `write` muda o ficheiro) |
| `_main/_route-stamp-gate-wiring-green.txt` | NOVO (log da corrida verde) | — | ver §3.1 |
| `_main/_route-stamp-gate-panel-red.txt` | NOVO (log da corrida RED do painel) | — | ver §3.1 |
| `_main/_route-stamp-gate-engine-red.txt` | NOVO (log da corrida RED do motor) | — | ver §3.1 |
| `_main/_cura-oracle-suite-node-probes.json` | NOVO (recibo da suite, `--only` dos 3 node probes) | — | ver §3.1 |
| `_main/_panel-red-copy.js` | criado e **apagado** (demo do RED) | — | — |
| `_main/_route-stamp-red-copy.js` | criado e **apagado** (RED do motor) | — | — |
| `worker/**` | **NAO TOCADO** (non-goal) | — | — |

### 3.1 `sha256` dos artefactos de log (por `sha256sum` pelo leitor; abaixo medido)

O recibo nao se auto-hasheia; os logs abaixo foram hasheados depois de escritos:

```
$ sha256sum _main/_route-stamp-gate-wiring-green.txt _main/_route-stamp-gate-panel-red.txt _main/_route-stamp-gate-engine-red.txt _main/_cura-oracle-suite-node-probes.json
```

(ver §5 — a linha real esta' colada la'.)

---

## 4. VERIFICACAO DO FIM DE VOO (corrida UMA vez, rc reportado)

| comando | rc | nota |
|---|---|---|
| `node --check _main/route-stamp-gate.js` | **0** | sintaxe |
| `py -3 -m py_compile _main/_cura-oracle-suite.py` | **0** | sintaxe |
| `node _main/route-stamp-gate.js` | **0** | `GATE: PASS — 11/11` |
| `node _main/route-stamp-gate.js --panel _main/_panel-red-copy.js` | **1** | `GATE: RED — 10/11` — so' `G4` |
| `node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js` | **1** | `GATE: RED — 10/11` — so' `G3` |
| `node _main/route-stamp-gate.js --emit-panel-mutant app/electron/panel.js` | **2** | recusa escrever sobre o painel live |
| `py -3 _main/_cura-oracle-suite.py --only <os 3>` | **0** | `SUITE: GREEN=3` — os tres rows GREEN |
| `sha256sum app/electron/panel.js` (antes == depois) | — | identico `135f9f6e…` |

**Nenhuma janela foi aberta:** o gate e' leitura de ficheiros + `require` + escrita em
`history-verify/`; a suite corre `node` num subprocesso com `capture_output=True`. Nao arranca a app,
nao spawna `python.exe`/electron visivel, nao liga porto.

---

## 5. `sha256` DOS LOGS (medido, colado verbatim)

```
$ cd H:/sotto && sha256sum _main/_route-stamp-gate-wiring-green.txt _main/_route-stamp-gate-panel-red.txt _main/_route-stamp-gate-engine-red.txt _main/_cura-oracle-suite-node-probes.json
223c90394eb7909beb8b031d1b03e3eb328ca97a36e43b6811f93b1d50b5337f  _main/_route-stamp-gate-wiring-green.txt
2bca1764582753a947846d01aed0cf249357c6ee2be67c99bc11947ffba2d6b8  _main/_route-stamp-gate-panel-red.txt
881ab432811cd4c6aad252460fd71416d8d34336559d51b23608fac27523e4c2  _main/_route-stamp-gate-engine-red.txt
22b542b92845e804552a420b9639f6bd38ad48be934a22e3f088e5d49f4a9129  _main/_cura-oracle-suite-node-probes.json
```

---

## SELF-AUDIT

1. **protocolos em falta** — senti falta de um protocolo para **editar um ficheiro untracked que o
   brief diz ser de outra lane**. O brief resolveu-o a mao para `_main/route-stamp-gate.js` ("MAIN
   GRANTS YOU THE ONE-ROW EDIT ... and nothing else in that file") mas **nao** para os dois
   non-goals adjacentes que a task 1 me mandava wire: as tres linhas caem em
   `_main/_cura-oracle-suite.py`, que o receipt de origem (`:335-341`) nomeia como entregavel de OUTRA
   lane ("Esta lane landou `_main/_cura-oracle-suite.py`"). Resolvi-o pelo **minimo**: tres entradas
   `ORACLES` no molde exacto que a lane de origem mediu, zero reformatacao, zero toque no resto do
   ficheiro. Faria diferente: pedir no brief a posse EXPLICITA do ficheiro da suite quando a task 1
   pede "wire all three", em vez de a inferir da concessao de UMA row ao gate.
2. **verificacao adicional** — corri-a, e era barata: **(a)** o RED do MOTOR (§2.6) para provar que
   nao regredi a arm `G3` ao mexer no `main()`; **(b)** o **refuse-over-live** do
   `--emit-panel-mutant` (§2.5) — o guarda que impede a copy de clobberar o painel live — porque um
   `--panel` novo sem esse guarda seria uma escrita no ficheiro que o brief proibe; **(c)**
   `py -3 -m py_compile` na suite, porque a linha nova e' uma string Python que um erro de aspas
   deixaria sintacticamente valida mas funcionalmente morta (o wrapper `-c` so' rebentava em runtime).
   O que ficou por fazer e seria caro: correr a SUITE COMPLETA (3 oraculos a 420 s, CUDA/endpoint) —
   desproporcionado para a linha do row pedida.
3. **checkboxes novas** — (mecanico) **toda comparacao TEXTO-a-TEXTO de codigo-fonte normaliza
   ANTES de comparar** (tira comentarios, colapsa espacos) e o proprio gate carrega um CONTROL com o
   input permissivo restaurado. Aqui: `panelGuardVerdict` + a arm
   `CONTROL: the SAME panel check on the pre-cure guard (`|| 'final'` restored) is RED`. Um
   `includes()` cru e' errado nos DOIS sentidos (falso-GREEN por reformatacao, falso-RED por um
   comentario que cita o codigo pre-cura).
4. **review por outro subagente** — **sim-com-escopo**: um revisor independente que leia
   `_main/route-stamp-gate.js:184-221` + `:457-462` e responda (1) se `panelGuardVerdict` e' de facto
   RED-able so' pela regressao nomeada (`|| 'final'` restaurado) e nao por um artefacto de leitura, e
   (2) se a normalizacao por `//`-strip pode morder um `panel.js` legitimo (uma string com `//`, p.ex.
   uma URL, dentro da REGIAO da guarda). NAO precisa rever o motor nem a suite.
5. **gate-doubt**
   - **verde-de-verdade:** os verdes que corre — `GATE: PASS — 11/11` (rc 0), `SUITE: GREEN=3`
     (rc 0), `py_compile` rc 0, `node --check` rc 0. **O verde do `G4` NAO e' vacuo:** ele carrega,
     no MESMO comando, o CONTROL que o deixa RED sobre a copy pre-cura (`real=false want=false`) e o
     CONTROL que prova que a mutacao `bit` uma vez (`panelChanged:true, panelMatches:1`); o
     `GATE: RED — 10/11` da §2.4 mostra a `G4` a acender sozinha. O green da SUITE e' real mas
     **parcial**: os `--only` de 3 rows deixam os 14 oraculos antigos POR CORRER nesta sessao — nada
     prova que continuem verdes; o que mudou neles foi zero (nao os toquei), mas a suite completa nao
     foi corrida e isso fica dito, nao escondido.
   - **falta-no-gate:** o que o `G4` NAO verifica — **nao EXECUTA o `panel.js`** (DOM-bound, precisa da
     app, que nao se arranca). Ele afirma a FORMA da guarda no ficheiro; um painel que passe a guarda
     num wrapper (`function rec(m){ if (guard(m)) return; … }`) ou que MUTE a guarda sem mudar a
     atribuicao/teste fica GREEN. Segundo buraco mais estreito: a normalizacao tira `//` de toda a
     linha, logo uma URL `http://…` dentro da REGIAO capturada corromperia o texto normalizado (nao o
     caso hoje — a regiao da guarda e' `const route` + `if`, sem URL). Cenario que atravessa o
     primeiro: alguem troca `panel.js:336` por um helper `if (!isFinalRoute(route)) return;` e
     `isFinalRoute` devolve `true` para tudo — a `G4` fica RED (o TESTE ja' nao e' o exacto), o que e'
     o lado seguro; mas alguem que escreva `if (route !== 'final') return;` E um `|| 'final'` noutro
     ponto do caminho (o `store.append`) nao e' vista por esta arm — e' vista pela `G3`, na corrida do
     replay.
   - **gate-melhor:** o check mecanico que fecharia o `const route = 'final';` (que a regra
     do receipt — "nao contenha `|| 'final'`" — NAO apanharia) ja' esta' DENTRO desta mudanca: o
     predicado exige `!/['"]final['"]/.test(assignment)`, isto e', o literal `'final'` AUSENTE da
     atribuicao, o que e' mais forte que `|| 'final'` e nao introduz falso-RED no ficheiro live.
     Comando: `node _main/route-stamp-gate.js --panel <copy com `const route = 'final';`>` → deve dar
     `GATE: RED` com a `G4` a falhar. **Input que tem de o deixar RED: `const route = 'final';`**
     (nao medido nesta lane — a copy usada foi a do `|| 'final'`, que e' o input nomeado pelo brief;
     fica declarado, nao corrido).
6. **confianca** — **alta** no `G4` (as duas cores medidas no mesmo comando, a mutacao provada a
   morder uma vez, o ficheiro live com sha identico antes/depois, o emit recusando o live).
   **alta** no wiring: os tres rows correm por dentro da suite e reportam GREEN (rc 0) — o invocador
   existe hoje, nao amanha. **media** so' na generalidade: a suite COMPLETA nao foi corrida nesta
   sessao, logo os 14 oraculos antigos estao "nao tocados" e nao "re-provados".
7. **nao verificado** — (1) o `panel.js` EXECUTADO num DOM (non-goal: precisa da app); (2) a SUITE
   COMPLETA de ponta a ponta (14 oraculos antigos + 3 novos; so' os 3 novos foram corridos); (3) a
   variante `const route = 'final';` do SELF-AUDIT 5 (predicado cobre-a por desenho, mas nao foi
   corrida); (4) a generalidade dos `--only` da suite — um `--only` de 3 rows nao prova a suite inteira;
   (5) census de `history-verify/route-stamp-*` (roots descartaveis, recriados a cada corrida).

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh SottoProbeWiring` — saida VERBATIM:

```
## CACHE/PRICE
- task/agent: SottoProbeWiring
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoProbeWiring.jsonl
- cache: read=4596096 write=0 hit=96.8594% (cache-read / input+cache-read); universe: 38 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoProbeWiring.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=36 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over …
- when-failed: break_items=2; WHEN=2026-10-06T23:40:03.853000+00:00 | break_items=3; WHEN=2026-10-06T23:40:20.443000+00:00 | break_items=3; WHEN=2026-10-06T23:40:23.604000+00:00 | break_items=2; WHEN=2026-10-07T00:02:51.346000+00:00 | break_items=2; WHEN=2026-10-07T00:10:39.943000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 123957 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoProbeWiring']; window: 2026-10-06T23:40:03.853000+00:00..2026-10-07T00:10:39.943000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=mimo-v2.6-flash model=mimo-v2.6-flash item_index=1; turn_id=1791330003853 | session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791330020443 | session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791330023604 | session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=16; turn_id=1791331371346 | session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=26; turn_id=1791331839943 (state=RESOLVED-BREAKS-OMP; population: 5 of 123957 OMP prefix-ledger rows attr…
- report generated_at: 2026-10-07T00:20:18.976930+00:00
- usage rows: 38
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 149024
- output tokens: 30432
- cache-read tokens: 4596096
- cache-write tokens: 0
- hit ratio: 96.8594% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=36 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 38 of 38 matched usage rows
- prefix breaks: 12 (state=RESOLVED-BREAKS-OMP; population: 5 of 123957 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoProbeWiring']; window: 2026-10-06T23:40:03.853000+00:00..2026-10-07T00:10:39.943000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T23:40:03.853000+00:00; WHERE session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=mimo-v2.6-flash model=mimo-v2.6-flash item_index=1; turn_id=1791330003853
  - break_items=3; WHEN=2026-10-06T23:40:20.443000+00:00; WHERE session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791330020443
  - break_items=3; WHEN=2026-10-06T23:40:23.604000+00:00; WHERE session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791330023604
  - break_items=2; WHEN=2026-10-07T00:02:51.346000+00:00; WHERE session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=16; turn_id=1791331371346
  - break_items=2; WHEN=2026-10-07T00:10:39.943000+00:00; WHERE session_id=01a11394-5734-7377-b8e2-23a66bf29d25 provider=deepseek-flash model=deepseek-flash item_index=26; turn_id=1791331839943
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

**WHEN / WHERE failed (lido do bloco acima):** 5 prefix breaks nesta sessao — 23:40:03Z / 23:40:20Z /
23:40:23Z / 00:02:51Z / 00:10:39Z, `session_id=01a11394-5734-7377-b8e2-23a66bf29d25` em
mimo-v2.6-flash, cline-pass/stealth/pixel-canary e deepseek-flash, todos `state=RESOLVED-BREAKS-OMP`
(population 5 of 123957 rows — artefacto de fila/pacing do ledger de prefixos do OMP, nao uma quebra
do trabalho desta lane); `cache-write=0` e `hit=96.8594%` em 38 usage rows. `cost=$0.00000000` —
reportado pelo provider, com as taxas exactas por modelo **UNKNOWN** na mesma fonte.
