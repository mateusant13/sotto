# Sotto — `worker/sotto_worker.py` is GONE from the worktree: state of the facts, and what I did NOT do

Lane: `SottoWorkerGone` · 2026-10-06 · alvo **`H:/sotto`** (shared tree, `isolated: false` — measured:
9/9 lanes with `isolated: true` died at worktree creation with `Acesso negado. (os error 5)`).
Nothing was written outside `H:/sotto`; the ONLY file this lane created is this receipt.
**The Sotto app was NOT started** (it would put a window on the owner's screen). No ASR code touched.

---

## 0. VERDICT — STOP AT THE REPORT, and why

The deletion is **REAL, WORKTREE-ONLY, UNSTAGED, and it is NOT a commit**: the index still holds the
blob, no commit ever deleted the path, no branch/worktree/stash carries the deletion. **But I cannot
prove it is not another lane's live work — the evidence points the OTHER way**, so per the brief I did
**not** restore it:

1. **HEAD is NOT what was on disk.** `worker/__pycache__/sotto_worker.cpython-311.pyc` (an instrument
   that survives the deletion) records the source it was compiled from: **149856 B, mtime
   `2026-10-06 10:51:41`**. HEAD's blob is **127023 B**. So the deleted file was ~22 KB of
   *uncommitted* content that no commit contains.
2. **A lane's own copy of that live file is sitting in the tree**: `_main/_ordem-before/sotto_worker.py`,
   **128569 B, mtime 10:12:27**, blob `b139269d1cfeae64acae24b6bb6c8238196d9f0e` — i.e. the file was
   being **edited by lanes** and at least one lane made a backup of it. (`worker/_sotto_worker_agcinert.py`,
   128460 B @06:22, is a second variant, git-ignored at `.gitignore:74`.)
3. **`git checkout -- worker/sotto_worker.py` would itself destroy a lane's uncommitted work**: it
   restores the 06:59 content over a file the day's lanes had taken to 149856 B — exactly the act the
   brief forbids ("never revert another lane's uncommitted work").
4. **The delete does not predate every open lane.** The shell's own source documents the traffic:
   `app/webview/sotto_webview.py:2439` — *"with five lanes editing `worker/sotto_worker.py` all morning"* —
   and the app's hot-reload log records a **delete/create/modify churn on exactly that filename** while
   the app ran (§5). The delete landed at **17:42:05** (§2), i.e. mid-day, with lanes open and this tree
   in use.

Consequence: the file is forfeit as *content*, and restoring is a decision for the owner/main, not for
a lane. **My single recommendation is in §6.**

---

## 1. The four commands, VERBATIM

```
$ git status --porcelain -- worker/sotto_worker.py
 D worker/sotto_worker.py

$ git show HEAD:worker/sotto_worker.py | wc -c
127023

$ git log --diff-filter=D -- worker/sotto_worker.py
(no output — NO commit ever deleted this path)

$ git worktree list
H:/sotto                    11df66e [main]
H:/sotto-wt-FlatEndpoint    3e90f92 [feat/FlatEndpoint]
H:/sotto-wt-PanelGap        3e90f92 [feat/PanelGap]
H:/sotto-wt-TapRestartLoop  3e90f92 [feat/TapRestartLoop]

$ git stash list
(no output — no stash exists)
```

Supporting, same session:

```
$ git rev-parse HEAD:worker/sotto_worker.py :worker/sotto_worker.py
ed3171aaed2082282fb2f00459a79859cd782f5d
ed3171aaed2082282fb2f00459a79859cd782f5d          # HEAD blob == INDEX blob

$ git diff --cached --name-status
(empty — NOTHING is staged)

$ git diff --stat -- worker/sotto_worker.py
 worker/sotto_worker.py | 2580 ------------------------------------------------
 1 file changed, 2580 deletions(-)

$ git ls-files -d
worker/sotto_worker.py

$ git log --all --oneline -- worker/sotto_worker.py
5ffeefc durability: track the whole untracked production tree so `git clean` cannot take it
3e90f92 bridge: the panel stops saying "Waiting for audio" when it never had audio
```

Verbatim status letters: `" D worker/sotto_worker.py"` — column 1 (index) is a SPACE, column 2
(worktree) is `D`: **deleted in the WORKING TREE only, index untouched.**

```
$ git show HEAD:worker/sotto_worker.py | sha256sum
ffe3b62fce7660efd78ff450cb1f79a06f94577a77e1a661d4d67e3a8cb1c07c  -
$ ls -la worker/sotto_worker.py
ls: cannot access 'worker/sotto_worker.py': No such file or directory
```

---

## 2. State in HEAD, and the timestamp of the deletion

- **HEAD carries the file**: blob `ed3171aaed2082282fb2f00459a79859cd782f5d`, **127023 B**, sha256
  `ffe3b62fce7660efd78ff450cb1f79a06f94577a77e1a661d4d67e3a8cb1c07c`.
- It entered git **twice** in history: `3e90f92` (2026-10-06 00:06:07) added a **13913-B stub**, and
  `5ffeefc` (2026-10-06 06:59:06, *"durability: track the whole untracked production tree so `git clean`
  cannot take it"*) replaced it with today's real 127023-B file. `HEAD` is `11df66e` (07:02:59, docs only).
- **The three sibling worktrees all sit at `3e90f92`** and therefore carry the *stub*, 14281 B on disk —
  so no sibling worktree holds the deleted content, and none holds the deletion either.
- **Renamed? No.** No `??` copy of the name appears anywhere in the tree, and the only other files that
  look like the worker are pre-existing variants: `_main/_ordem-before/sotto_worker.py` (128569 B,
  10:12:27 — a lane's *before* snapshot, blob `b139269d…`) and `worker/_sotto_worker_agcinert.py`
  (128460 B, 06:22:30, git-ignored).
- **When it was deleted**: `stat` of the parent directory — `worker mtime=2026-10-06 17:42:05.129527400 -0300`
  — is the moment an entry was removed from `worker/` (no other file in `worker/` was created or removed
  then; the next-newest write there is `inspect_model.py` @17:04). Lower bound: the source was on disk at
  **17:31:27**, when `worker/__pycache__/sotto_worker.cpython-311.pyc` was written. So the delete is
  **~17:42 today, ~2 h 30 min before this receipt**, not a stale leftover of the morning.

**The file that was on disk was NOT HEAD's.** The `.pyc` header (PEP 552 timestamp block) is the instrument
that survives the deletion — read with `struct.unpack('<4sIII', open(pyc,'rb').read(16))`:

```
pyc magic   : a70d0d0a flags: 0
pyc src_mtime: 1791294701 2026-10-06 10:51:41
pyc src_size : 149856
```

i.e. `worker/sotto_worker.py` was last *replaced* at 10:51:41 with **149856 B**, and stayed that content
until it was removed at ~17:42. **Neither HEAD (127023 B) nor any copy on this box is that content.**

---

## 3. Is the deletion staged, or worktree-only?

**Worktree-only.** Three independent readings agree: `git status --porcelain` shows index=space/
worktree=`D`; `git diff --cached --name-status` is empty; `git rev-parse :worker/sotto_worker.py`
returns the same blob as HEAD. A native Windows `del`/`os.remove` — never `git rm`.

---

## 4. What the app does TODAY when started (reasoned from the spawn sites — **it was not started**)

Two things must be separated, and the brief's second cited line is not a spawn site:

- **`app/webview/sotto_webview.py:3704` is NOT a production spawn.** It lives inside `probe_reload()`
  (`:3676`, a worker-reload selftest) and only seeds `# seed\n` into a file inside `tempfile.mkdtemp()`.
  Nothing in `run.cmd` spawns a worker either (`run.cmd` starts only the shell; `--with-worker` is the
  bridge's flag, `run.cmd:7`).
- **The one production spawn is `WorkerBridge._spawn()` → `subprocess.Popen([self.command, self.worker_path])`
  at `app/webview/sotto_webview.py:2984`**, with `self.worker_path` = `--worker` (default
  `DEFAULT_WORKER_PATH`, `:3590` → `:64-66`, `worker/sotto_worker.py` — the shell passes no `--worker`),
  wired at `:2357` into `WorkerBridge(command=…, worker_path=…)` `:2782`.

Starting the app today therefore does **not** wait for a spawn error; it takes the explicit branch at
`:2941-2947`:

```python
if not os.path.exists(self.worker_path):
    self.log(f'BRIDGE_WORKER_MISSING path={self.worker_path}')
    self._bridge_status(
        f'Worker not found - {self.worker_path} does not exist', 'error',
        {'title': 'Worker not found',
         'body': 'The shell found no worker entrypoint at the path it was given.'},
        'missing')
    self._schedule_restart('missing')
    return
```

So the panel paints **`Worker not found - H:\sotto\worker\sotto_worker.py does not exist`** with
`state='error'` (an error colour, per the panel verdict law in `AGENTS.md`), and `_schedule_restart`
re-arms the same failing spawn in a loop. **No captions can ever arrive** — the app is a shell around a
worker that does not exist.

**And the panel the owner is looking at RIGHT NOW is the *other* face of the same hole**: the running
shell (pid 24756) still has the pre-deletion worker child **pid 36844** up (`tasklist /FI "PID eq 36844"`
→ `python.exe 36844`), spawned before the file vanished, so it is decoding *from code held in memory*.
`_main/panel-state.json` (written 20:08:00, `ageSeconds: 0.0`) still shows `childPid 36844`,
`capturing: true`, `spawns 7`, live captions in `_main/webview-run.log`. The bridge has **not yet
noticed**: `grep -c BRIDGE_WORKER_MISSING _main/webview-run.log` → **0**. The moment 36844 exits
(which it does constantly — `restarts=7`, `deaths=6`), the next `_spawn()` takes the missing branch
above and the live field dies with it.

---

## 5. The churn the app itself recorded on that filename

`_main/webview-run.log` (17341 lines, mtime 20:09:57), lines 13575-13595, verbatim:

```
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=1 debounce_ms=250
sotto: HOT_RELOAD_FLUSH kind=worker files=["sotto_worker.py"] events=1 debounce_ms=250
sotto: HOT_RELOAD_WORKER_QUEUED files=["sotto_worker.py"] debounce_ms=2000 min_interval_ms=180000
sotto: HOT_RELOAD_WORKER_DEFERRED files=["sotto_worker.py"] reason=capturing -- applies at the next boundary
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=2 events=1 debounce_ms=250
...
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=1 events=1 debounce_ms=250
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=2 debounce_ms=250
...
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=1 debounce_ms=250
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=2 debounce_ms=250
sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=2 events=3 debounce_ms=250
```

`action=3` (deleted) appears **three times**, interleaved with create/modify. The file was being deleted
and rewritten repeatedly in a live tree; `HOT_RELOAD_WORKER_DEFERRED reason=capturing` is why the running
child kept running old code. `app/webview/hot_reload.py` **never** deletes or writes the worker (its only
`os.replace` is at `:553`, on a CSS asset) — so the churn came from outside the app. No script in the repo
deletes the worker path either (`grep` for `os.remove|shutil.move|os.rename|os.replace` around
`sotto_worker` across `_main/*.py` → only unrelated log cleanups). **Who issued the delete is UNKNOWN
from this box**; the two candidate owners are a lane's mutant/restore harness and an operator/editor
action, and I refuse to name one.

---

## 6. The two candidate actions, with their costs — and my recommendation

**(A) `git checkout -- worker/sotto_worker.py`** — restores blob `ed3171aa` (127023 B, sha256
`ffe3b62f…`), index untouched, no staging needed.

- *Benefit*: the app stops being a shell around nothing; `BRIDGE_WORKER_MISSING` never fires.
- *Cost 1 (the one that decides it)*: **it silently reverts every uncommitted edit made to that file
  after 06:59** — the file on disk was 149856 B @10:51:41, HEAD is 127023 B. That is "reverting another
  lane's uncommitted work", the house rule this brief invokes. It is also a *content* rollback of an ASR
  worker the day's lanes were curing.
- *Cost 2*: the shell watches `worker/`; creating the file fires `HOT_RELOAD_EVENT` → `_QUEUED` →
  debounced/respawn (`min_interval_ms=180000`, deferred while capturing). The live child dies and is
  respawned on the older code, mid-stream, under the owner's feet. Not a window — but a visible stop in
  transcription.

**(B) Treat it as MOVED/LOST and restore the newest content that survives** — i.e.
`cp _main/_ordem-before/sotto_worker.py worker/sotto_worker.py` (128569 B, blob `b139269d…`,
`.gitignore` does not cover `_main/`).

- *Benefit*: spawns again, no window, index still shows ` D`.
- *Cost*: it is **not** the last content either (the last was 149856 B @10:51), it is *pre-`_ordem`* work
  by construction (the name says "before"), and it promotes an untracked probe artifact into a production
  path. It buys a running app at the price of a code version nobody has verified since 10:12.

**RECOMMENDATION (single): do NOT restore in this lane — hand it to the owner/main, and if and only if
they authorize a restore, do (B) first (`cp` the surviving 128569-B copy in, keeping the index's ` D`
intact for the diff) rather than (A), because (A) destroys post-06:59 lane work while (B) only produces
a stale-but-real worker — and before either, quarantine `_main/_ordem-before/sotto_worker.py` and stop
the running shell's next worker respawn (`BRIDGE_WORKER_MISSING`) being read as a new defect.**
If the owner wants the *content* recovered, the honest statement is: **no copy of the 149856-B version
exists on this box** — `find . -type f -size 149856c` (excluding `worker/models` and `node_modules`) is
**empty**; the only surviving trace of it is the compiled `.pyc` (5c6d5a5d…), which is not source.

---

## 7. What I did NOT do (deliberate)

- **Did not restore, move, or `git checkout` anything.** The worktree is exactly as found; the index is
  exactly as found.
- **Did not start the app** (no window on the owner's screen) and did not restart the running shell.
- **Did not touch any other lane's file** — `AGENTS.md`, `panel.js`, `caption-formulation.js`,
  `history-store.js`, `sotto_webview.py`, `worker/README.md`, `worker/wasapi_loopback.py` and all the
  untracked `_main/`/`worker/` artifacts are untouched; every command in this receipt is read-only
  (`git status/diff/log/rev-parse/ls-files`, `stat`, `find`, `grep`, `tasklist`, `struct.unpack` on a
  `.pyc`).
- **Did not delete an untracked file** — and explicitly did not touch `worker/_sotto_worker_agcinert.py`
  or `_main/_ordem-before/`.
- **Did not touch the ASR stack.**
- **Did not put a window on the owner's screen — and the house's own instrument corroborates it.** The
  window census (`I:/!manager/state/progress/window-census.log`, cadence 60 s) carries **no
  `ALERTA-JANELA` row for any pid of this lane**; its last two alarms are
  `ALERTA-JANELA ts=2026-10-06T13:24:22Z … nome=WhatsApp.Root` and
  `ALERTA-JANELA ts=2026-10-06T13:42:22Z … nome=pythonw … cmd="C:\Program Files\Python311\pythonw.exe" "H:\sotto\app\webview\sotto_webview.py" --log "H:\sotto\_main\webview-run.log" --with-worker`
  — the running app itself, ~10 h before this lane's commands. The only interpreter this lane ran was
  `python -` (import of `struct`, read-only `struct.unpack` over a `.pyc` header and over
  `_main/panel-state.json`); it allocates no window. This is a *supporting* observation, not the
  proof: the census samples every 60 s and cannot prove the absence of a short-lived window (AGENTS.md
  says so in terms). The primary reason no window appeared is that no UI entrypoint was ever invoked.


---

## 8. Honest limits

1. **The deleter is UNKNOWN.** I proved *what* was deleted (149856 B @10:51:41), *when* (~17:42:05), and
   that it was a plain filesystem delete — not *who*. The lane ledger I would have queried
   (`I:/!manager/state/fleet/lane-ledger.jsonl`) is not at that path, and I did not go hunting outside
   the repo for it.
2. **The 17:42:05 timestamp is directory-mtime evidence, not a filesystem journal.** An NTFS USN read
   would date it exactly and could name the deleting process; that instrument was not used (out of scope,
   and it needs elevation).
3. **The running app's worker child was NOT stopped or inspected beyond `tasklist`** — killing it is not
   mine to do and would have removed the owner's current captions.
4. **HEAD's worker is assumed runnable but was not run** (running it means a model load and, per house
   rule, no window risk is worth the confirmation here).

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoWorkerGone
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoWorkerGone.jsonl
- cache: read=1497600 write=0 hit=92.5991% (cache-read / input+cache-read); universe: 18 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoWorkerGone.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=17 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 18 of 18 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T23:06:53.598000+00:00 | break_items=3; WHEN=2026-10-06T23:08:53.100000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 123495 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoWorkerGone']; window: 2026-10-06T23:06:53.598000+00:00..2026-10-06T23:08:53.100000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11377-a89d-70c3-86fb-255b9f0c250c provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791328013598 | session_id=01a11377-a89d-70c3-86fb-255b9f0c250c provider=deepseek-flash model=deepseek-flash item_index=48; turn_id=1791328133100 (state=RESOLVED-BREAKS-OMP; population: 2 of 123495 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoWorkerGone']; window: 2026-10-06T23:06:53.598000+00:00..2026-10-06T23:08:53.100000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T23:10:47.399646+00:00
- usage rows: 18
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 119695
- output tokens: 26449
- cache-read tokens: 1497600
- cache-write tokens: 0
- hit ratio: 92.5991% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 4 (state=RESOLVED-BREAKS-OMP; population: 2 of 123495 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoWorkerGone']; window: 2026-10-06T23:06:53.598000+00:00..2026-10-06T23:08:53.100000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

## SELF-AUDIT

1. **protocolos em falta** — faltou-me um protocolo de **propriedade do `worker/sotto_worker.py`**: a
   casa proíbe reverts e proíbe apagar untracked, mas não há regra para *um ficheiro TRACKED apagado do
   worktree por outrem* — que é um terceiro caso (nem revert, nem untracked, nem commit). A decisão foi
   tomada por extensão da regra "não reverter trabalho alheio". O que faria diferente: abrir com "cujo é
   este ficheiro e quem o apagou", consultando o lane ledger ANTES de medir o conteúdo.
2. **verificacao adicional** — correi o instrumento que sobrevive à remoção: o cabeçalho PEP 552 do
   `.pyc` (§2). Sem ele ter-me-ia ficado a hipótese errada ("o ficheiro era o de HEAD") e a recomendação
   teria sido um `git checkout` destrutivo. Custo: uma leitura de 16 bytes. **Devia ser o PRIMEIRO passo
   desta classe de trabalho.**
3. **checkboxes novas** — (mecânico) *antes de propor restaurar um ficheiro tracked ausente, correr
   `python -c "import struct;d=open('<pyc>','rb').read(16);print(struct.unpack('<4sIII',d))"` e comparar
   `src_size`/`src_mtime` com `git cat-file -s HEAD:<path>`; se diferirem, a restauração é uma PERDA, não
   uma cura.* E: *aplica-se `stat -c %y` ao DIRETORIO pai para datar a remoção do entry quando o journal
   não está disponível.*
4. **review por outro subagente** — **sim-com-escopo**: um reviewer que leia §0/§6 e diga se a decisão de
   NÃO restaurar se sustenta com a prova do `.pyc` (149856 ≠ 127023) e se a minha escolha de (B) sobre (A)
   na recomendação é a certa. O que NÃO delegaria: a medição (é read-only e já está datada).
5. **gate-doubt**
   - **verde-de-verdade:** não corri gate nenhum neste trabalho; é read-only e o "verde" é a ausência de
     escrita. Não há corrida que possa ter passado vacuosa, **exceto** uma: `git status --porcelain --
     worker/sotto_worker.py` sozinho não prova *staged vs worktree*; precisou do par
     `git diff --cached --name-status` (vazio) + `git rev-parse :path` (== HEAD blob) para a coluna 1 ser
     lida como espaço e não como `D` de staged. Usei os três.
   - **falta-no-gate:** o gate de topo desta classe — `git status` — **não distingue "apagado por um
     commit" de "apagado do worktree" nem diz QUANDO**, e uma mudança futura atravessa isto trivialmente:
     uma lane que faça `os.remove(worker/sotto_worker.py)` para testar um mutante deixa o mesmo
     ` D` que um acidente do dono, e ninguém sabe a idade sem ir ao `.pyc`/journal. O `D` é
     ambíguo-por-construção.
   - **gate-melhor:** um check mecânico no pre-commit/pre-dispatch que, para cada ` D` no worktree,
     imprima `src_size` do `.pyc` da mesma base e compare com `git cat-file -s HEAD:<path>`; RED quando
     diferem (prova de que o ficheiro apagado continha trabalho não-commitado). Input que o deixa RED:
     `H:/sotto` **hoje** — 149856 vs 127023.
6. **confianca** — **alta** no estado medido (blob, staged-vs-worktree, histórico, worktrees, stash, idade
   ~17:42, conteúdo 149856 via `.pyc`) e **média** na atribuição ("quem apagou" é UNKNOWN, e é por isso
   que a recomendação não é executada aqui). Muda-a: o journal USN do volume H:.
7. **nao verificado** — (a) quem apagou e a hora exata ao segundo; (b) se o shell parado/em execução
   volta a spawnar hoje (não se tocou no processo 24756/36844); (c) se HEAD's worker ainda arranca (não
   se correu — non-goal); (d) o `--worker` explícito do `run.cmd` real em uso hoje (o default é o caminho
   ausente, mas não verifiquei o `.cmd` realmente invocado do lado do dono); (e) o lane ledger do
   manager (path não encontrado).
