# RECIBO - a CLASSE "terminal na cara do dono", medida e fechada onde e' desta arvore

Ordem que abriu o trabalho (DM do watcher, 2026-11-08): *"to vendo terminal dar pop up, DE NOVO, na
minha tela"* + *"essa frequencia do terminal, mesmo se fosse background, ta retardada"*. O dono ja'
tinha mandado (2026-11-07, verbatim): *"e' pra tua mensagem automatica mandar fazer full audit atras de
scripts q fazem esse comportamento, e pra arrumar de fix, de forma nuclear"*.

## 0. A linha acusada, verbatim do censo

```
culprit   = gh.exe(41080)
chain     = gh.exe(41080) <- bun.exe(38824) <- omp.exe(24236)
window    = class=CASCADIA_HOSTING_WINDOW_CLASS hwnd=0x1ac41ec
lifetime  = 0.36s
signal    = foreground=True popup=True
```

`omp.exe` sou eu (a sessao), `bun.exe` e' o runtime do kernel JS do harness. **Nao ha uma unica chamada a
`gh` em `H:/sotto`** -- medido:
`grep -rn -E "(^|[^a-z])gh( |\.exe)" --include=*.py --include=*.js --include=*.mjs --include=*.cmd _main app worker .git/hooks`
devolve **4 linhas, todas falsos positivos** (`gh` como variavel `gh`/`gh = w._vtbl(...)` em
`_main/_design-lane/survey3.py:38`, `survey6.py:43`, `_main/friendly-name-probe.py:65,81,86`). O
processo que pintou a janela e' do HARNESS, nao deste repo.

Isso nao fecha o trabalho: a DM pede a CLASSE, e a classe tem uma metade que e' desta arvore.

## 1. O CENSO COMPLETO -- e os tres defeitos do proprio instrumento

O censo existe desde 2026-11-04 (`_main/console-window-audit.py`, AST de **1248 ficheiros** `.py`,
`.js`, `.mjs`, `.cjs`, `.ts`). A DM obrigou a reler o instrumento, e ele estava errado em **tres**
sitios -- cada um deixava passar exactamente a classe que o dono ve:

| # | defeito do instrumento | o que ele deixava passar | cura (medida) |
|---|---|---|---|
| I1 | `guarded = ('windowsHide' in window) or ('detached: true' in window)` (`audit_js`) | **o caso desta DM**: `spawn('gh', [...], {detached: true})` era certificado como guardado. A DM diz, verbatim: *"`detached: true` is NOT a fix: it leaves the child console-less and the next spawn paints again"* | guarda = **so'** `windowsHide`. O `detached` continua a valer apenas na arm `USER-GESTURE` (o *reveal in folder*, que e' um clique do dono) |
| I2 | a janela de leitura era `segment[line-3 : line+12]` | uma chamada com o `startupinfo` correcto na linha 64 de uma chamada que comeca na 42 era publicada `WEAK-FLAG` -- **portao acusando quem esta' certo** | `ast.get_source_segment(src, node)`: o segmento EXACTO do no'. `WEAK-FLAG` caiu **6 -> 5** so' por isto |
| I3 | `CONSOLE_EXES` nao conhecia `gh`, `bun`, `deno` | `spawn('gh', ...)` sem guarda classificava-se `INHERITS` ("herda a consola do pai") -- **falso quando o pai nao tem consola**: o Windows aloca uma NOVA e o Windows Terminal (hospedeiro por omissao) pinta | `gh/gh.exe/bun/bun.exe/deno/deno.exe` entram na lista, com o pid e a janela que os incriminaram escritos ao lado |

O braco negativo do censo ganhou a arm da DM, **C4**:

```python
jweak   -> spawn('gh', ['pr','list'], { detached: true, stdio: 'ignore' })   # tem de ser NO-FLAG
jstrong -> spawn('gh', ['pr','list'], { windowsHide: true, stdio: 'ignore' }) # tem de passar
```

Medido depois:

```
NEG-ARM PASS -- C1(os.system)=True C2(bit sozinho RED)=True C2(baseline perdoa)=True
                C3(o par passa)=True C4(detached do JS nao esconde)=True
CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela
files=1248 counts={'SCRIPT': 461, 'USER-GESTURE': 2, 'GUARD-EXTERNAL': 4, 'STRING': 9}
```

`GUARD-EXTERNAL 4` sao os quatro sitios cujo `creationflags` vem de um parametro (verificados a mao,
2026-11-04). `STRING 9` sao programas dinamicos, que o censo nao julga por string -- declarado, nao
absolvido.

## 2. A DIVIDA CONGELADA FOI ZERADA -- 0 WEAK-FLAG

`_main/console-weakflag-baseline.json` congelava **9** sitios de 2026-11-04 com `creationflags` sem o
par. Uma divida congelada e' uma janela que ainda pode pintar, por isso ela foi paga, nao renovada:

| ficheiro:linha | programa | cura |
|---|---|---|
| `worker/_probe/boot-control.py:29` | `python` | `startupinfo=_SI` (o par) |
| `worker/_probe/boot-control.py:40` | `git show` | idem |
| `worker/_probe/boot-io.py:40` | `python` | idem |
| `_main/quarantine-index-collision-20260707/selftest.py:562` | `python -m index.selftest` | idem |
| `_main/quarantine-index-collision-20260707/selftest.py:689` | idem (arm D-writer) | idem |
| `_main/measure-readiness.py:42` | `electron` | ja' trazia o par; era o defeito I2 do censo |

`_SI` e' o par literal (`STARTUPINFO` + `STARTF_USESHOWWINDOW` + `wShowWindow=0`), escrito em cada
ficheiro: estes probes vivem fora de `app/`, onde mora o helper `no_console.py`. Os tres ficheiros
compilam (`py_compile` rc=0). O baseline passou a `sites: []` -- **qualquer** `WEAK-FLAG` novo falha o
passo a partir de agora.

## 3. ANTES / DEPOIS, com o instrumento da DM

`python -m watcher pops --minutes 90 --json` (a janela que contem a DM e o trabalho), medido as 18:0xZ:

| imagem | classe da janela | linhas | leitura |
|---|---|---|---|
| `chrome.exe` | `Chrome_WidgetWin_1` | 68 | o browser do dono (nao e' desta classe) |
| `windowsterminal.exe` | `CASCADIA_HOSTING_WINDOW_CLASS` | **38** | a classe da DM |
| `WindowsTerminal.exe` | idem | 5 | idem |
| `''` (vazio) | idem | 4 | idem |
| `explorer.exe` | `Xaml_WindowedPopupClass` | 19 | popup do shell do Windows |
| `cmd.exe` | `PseudoConsoleWindow` | 7 | consola ALOCADA (o proprio defeito) |
| `ffmpeg.exe` | `PseudoConsoleWindow` | 2 | idem |
| `gh.exe` | -- | **0** | a imagem da DM ja' nao apareceu na janela |

**47 janelas de terminal em 90 min.** As cadeias que o censo nomeia, verbatim:

```
cmd.exe(23472) <- svchost.exe <- services.exe <- wininit.exe
    cmd /c H:\sotto\_main\sotto-relaunch.cmd          (16:38:25)
ffmpeg.exe(53436) <- pythonw.exe(32284) <- node.exe(56560) <- bun.exe(27680)   (17:27:41)
cmd.exe(30628) <- explorer.exe(14016)                 (16:24:36 e 17:24:40)
```

O que isso prova, e o que NAO prova:

* **Nao prova** que a arvore esta' limpa no sentido da DM: as cadeias acima tem `bun.exe`/`node.exe`
  como pais -- o HARNESS e as lanes, nao codigo deste repo. O censo desta arvore diz 0 sitios, e um
  censo que devolve 0 sobre a arvore nao absolve quem a chama.
* **Prova** que a metade que e' desta arvore nao tem mais sitio conhecido que pinte: 1248 ficheiros,
  `WINDOW 0 / NO-FLAG 0 / WEAK-FLAG 0 / PARSE 0`.
* A cadeia `cmd /c sotto-relaunch.cmd` sob `svchost.exe` e' uma accao de TAREFA AGENDADA. Varridas as
  **487** tarefas desta maquina (`schtasks /query /xml`, uma por uma): **nenhuma** define hoje
  `sotto-relaunch.cmd`. As duas que existem para o Sotto sao `\Sotto` (`H:\sotto\app\webview\run.cmd`)
  e `\SottoRelaunch` (`pythonw.exe _main\sotto-relaunch.py --relaunch --tag task`) -- `pythonw` nao
  tem consola nenhuma. A linha das 16:38 e' **residual e nao reproduzivel**: fica declarada, nao
  explicada.

## 4. O QUE FICA FORA DE ALCANCE DAQUI

* `bun.exe`/`omp.exe` sao o harness. Nenhum ficheiro desta arvore decide o `windowsHide` deles.
  A cura dessa metade e' do harness (ou de quem larga a lane), e o que esta casa pode fazer -- e fez --
  e' **nao ser ela a largar**.
* `cmd.exe(30628) <- explorer.exe` sao consolas abertas pelo PROPRIO dono.
* O `sotto-relaunch.cmd` das 16:38: residual, sem tarefa que o defina hoje (declarado acima).

## 5. CUSTO E TECTO

Nada pesado foi largado para esta cura: o censo e' AST (18,6 s a quente), o braco negativo 12,5 s, os
tres ficheiros pagos compilam em milissegundos. Tecto declarado da corrida: **nenhum processo novo
persistente**; o unico job longo em voo e' a bateria que ja' estava a correr, e ela nao foi reiniciada
por esta cura.

## 6. VEREDICTO

`CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela` com a divida **zerada** e a arm **C4** a
provar que o `detached` do JS nao esconde. A metade do harness continua a pintar (47 janelas em 90 min)
e **nao** esta' curada por este commit -- dizer o contrario seria o verde que nao mede nada.
`verified` continua impossivel de uma lane: exige uma hora de silencio e a mao do dono.
