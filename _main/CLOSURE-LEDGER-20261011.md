# CLOSURE LEDGER — every unfinished item named by the workspace docs, with its state

**Written 2026-10-11 by the Lead, from the files, not from memory.** The goal for this round
asked for an enumeration of EVERY unfinished item across the named sources and a measured
closure for each. This file is that enumeration: one row per item, grouped by area, with the
state the source itself states. It is GENERATED from the map strictly more than written by
hand — the map rows below are copied verbatim from
`docs/audit/00-MAPA-CONSOLIDADO.md`, whose own gate (
`bash I:/!manager/scripts/audit-map-gate.sh H:/sotto/docs/audit`) is GREEN at
**applied 124 / open 12 / in-flight 0** as this file is written, read from the gate itself.

## 1. The live product — 12 rows whose state cell reads OPEN

Each row below is an OPEN finding of the audit, with the map own location and state text.
Rows closed this session are NOT here; they are listed in section 5 with their instruments.

### docs/instruments (1)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| F10 | RTF > 1 na CPU: a app nao acompanha a fala em tempo real (`auditoria-completa-20261007.md:72`) | **OPEN** — a fonte transfere a decisao para o dono (:756-757: GPU, export com chunk menor, ou dizer que esta atrasado) |  |

### other (3)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| 18 | o `ready` do supervisor le um stream onde a app nunca escreve (o log vai para `--log`, nao para o PTY) | `launch-entry.md §3.4.2`, `spec.json` | **OPEN** |
| 19 | uma TERCEIRA causa do hang `STAGING_LOADED` reproduziu e nao esta nomeada | `launch-entry.md §4` | **OPEN** |
| G5 | o proprio pre-flight e um run pythonw sem stdout: o usage:/error: do argparse e descartado e o rc e o contrato inteiro (`launch-entry.md:119`) | **OPEN** — a fonte diz que e BY DESIGN (launch-entry.md:124-125); fica aberto enquanto o rc for o unico sinal |  |

### panel/rendering (3)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| 4 | painel aparece sozinho no ecra ≤63 ms em cada arranque | `edgechromium.py:348`, `sotto_webview.py:995` | **OPEN** |
| F1 | o painel mostra-se sozinho sem accao do dono (edgechromium.py:348 form.Show() sob transparent=True) (`window-visibility.md:186`) | **OPEN** — herdado da linha #4 (dois censos do mesmo instrumento discordam; o AGENTS.md marca o par NAO RECONCILIADO e a ordem do dono suspendeu o censo) |  |
| F9 | o campo de busca do painel nao pode receber teclado (`auditoria-completa-20261007.md:71`) | **OPEN** — a fonte transfere a decisao para o dono (:481, :762): hoje nao tem backend nem teclado e nao foi exercido |  |

### shell/window (1)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| F9 | 14 campos, 0 divergencias do webview-shell nao e reproduzivel (`doc-vs-code.md:29`) | **OPEN** — herdado da linha #52 |  |

### transcript/provenance (1)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| F2 | o HISTORY nao pode ser alimentado: nenhuma meta do motor live traz producer (`auditoria-completa-20261007.md:64`) | **OPEN** — o gate da fonte diz PRODUCER-VERDICT: no-producer-in-tree (:663) e o transcript foi fechado ao motor live por ordem do dono (:752); nota 2026-10-11: a arvore viva passou a carimbar producer (sotto_worker.py:3069/3567/3605) mas se a linha chega ao meta.producer que o gate canonico le continua NAO MEDIDO |  |

### worker/audio/ASR (3)

| id | finding (from the map) | where | state as filed |
|---|---|---|---|
| 62 | `subprocess.run(timeout=)` a volta do `electron.exe` multi-processo pode nao ser tecto [INFERENCE] | `_main/_run-hidden.py:24` | **OPEN** |
| F3 | o fallback de buffer de 100 ms e codigo morto (`audio-path.md:279`) | **OPEN** — herdado da linha #36 |  |
| F4 | subprocess.run(timeout=) a volta do electron.exe multi-processo pode nao ser tecto [INFERENCE] (`windows-landmines.md:317`) | **OPEN** — herdado da linha #62 |  |

## 2. What BLOCKS the open rows, by class

- **OWNER STOP ORDER (2026-10-11)** — `_moved/aireplay`-style items aside, this is the
  binding one for the live product: nothing may launch `sotto_webview.py`, `run.cmd`, the
  worker, or `_main/_audit-verify-all.cmd`. Everything that needs a real WebView2 paint, a
  real device or a full-shell run is UNMEASURABLE today: the T2 startup flash (row #4/#46,
  where the four census numbers still contradict each other), row #62 (measuring the electron
  tree ceiling means launching a binary the docs declare DEAD), and every row whose closure
  would be "painted correctly by the real WebView2".
- **NEEDS A REAL DEVICE / AUDIO** — the audio-path rows (#11, #13, #22, #23, #37) and any
  claim about what the owner hears: the routing law says a silent loopback is usually CORRECT
  behaviour, and the box has no audio routed into the cable while this is written.
- **PARKED TREE (`_moved/aireplay`)** — see section 3. Its own questions were ANSWERED on
  2026-10-10; what remains there is either owner-only or another tree work.
- **OWNER DECISION (recorded, not blocking)** — the `redux` literal producer tag: kept
  deliberately, with a one-edit rename path (`history-source.js:51`, `panel.js`,
  `REDUX_PRODUCER`, `redux_batch.py`, the oracle) plus migration, for the day the finisher is
  not the Redux package.

## 3. The parked tree — `_moved/aireplay`

**`_main/DEBT-LEDGER.md`** (390 lines) keeps five OPEN rows, all of them about the LANE
RUNTIME (wakes, cron, prune), not about the Sotto captioning product:

| id | item | state |
|---|---|---|
| D-IDLE-WAKE | a wake must reach an IDLE session within 3 minutes | OPEN — the owner actual requirement, NOT MEASURED there |
| D-D1 | minted `userMessageId` is 48 chars, the 20 most recent runtime rows are 55 | OPEN — shape proven wrong, causal role unproven |
| D-D5 | PRUNE is session-scoped, so an orphan row in a session with no runtime is permanent | OPEN — POP=4 rows, 0 with `expires_at` |
| D-D6 | `Runtime shutdown deadline exceeded after 60000ms` on every exec against a live session | OPEN — POP=1, a rate needs >=20 passes |
| D-D4 | no alarm when `now - max(cron_runs.created_at_ms) > 15 min` while an active cron exists | OPEN — the runtime cron is dead 26.5 h, POP=1 |

**`_main/TO-BE-ANSWERED-BY-OWNER.md``** — Q1..Q8 ALL ANSWERED in that file on 2026-10-10
(owner authorised "push and take all decisions"): push done; SPEC 06 stays written; no machine
change; clip clock keeps the measured order; duplicates decided by `content_key`; ring budget
priced from system RAM; the four plan files committed; the three gate-audit files committed
with `-f` and corrected by accretion. FOUR items remain open in its own final section:

| item | state |
|---|---|
| who set the label `S-1-16-4096` | OWNER-ONLY (the file says so explicitly: "teu, por medicao") |
| the L18 p95 probe reviewer verdict | IN FLIGHT in that tree, not measurable from here |
| lanes L5 and L6, and the wave-2 reviewers (L5, L6, L7, L18 by rule 4) | OTHER TREE WORK |
| the WGC has never captured a frame — F18.8 measures item CREATION, never a session | OTHER TREE WORK, and it needs a capture session |

**`_main/_lease-audit/TO-BE-ANSWERED-BY-OWNER.md`** — seven questions the synthetic store
could not decide. The owner instruction in force is *"toma todas as decisoes voce mesmo"*, so
they are DECIDED here rather than left open, each with the reason and the check it implies:

| q | decision (Lead, 2026-10-11) | why | what the instrument must now do |
|---|---|---|---|
| Q1 clips vs ASR windows may overlap | WINDOWS may overlap by up to `PAD_S` (0.10 s) each side; CLIPS may NOT overlap | the spec own words say recorded segments overlap; a clip IS the timeline interval, so overlapping clips would index the same time twice | keep C01 RED for clips; allow windows overlapping <= 0.20 s total |
| Q2 must two clips of a sequence be contiguous | NO contiguity rule | the clip boundary is the user keypress, which is arbitrary; the schema keeps the ASR window on `segment`, never on `video` | keep reporting the gap as INFO-GAP |
| Q3 is there a duration source beyond db and container for an imported file | NO rank above 4 | whatever an importer read is written INTO the db by the import, so the db IS the import own value | ranks 3 (db) and 4 (container) stand |
| Q4 is the moov `creation_time` usable | NO — never used for ordering | our own writer writes 0 literal (`mp4_writer.cpp:257/272/293`), so 0 and epoch-1904 must both read as UNKNOWN | keep the zero-field census |
| Q5 how does the index store a moved path | by `content_key` (whole-file sha256), never by path; two paths for one identity is NOT representable and stays so | `video.content_key` is UNIQUE and identity is the hash, measured: the second INSERT fails with IntegrityError | PATH MOVED = re-scan updating the row; a second path needs a schema change nobody asked for |
| Q6 ms tolerance on duration comparison | 1 ms for OUR OWN clips; `max(1 ms, 0.2% of duration)` for imported/container | our writer writes integer ms end to end, so exactness is free there; a container may truncate | label which rule each output used |
| Q7 do line citations hold on a drifted tree | no stable line numbers are promised: every citation carries the revision (sha256/date) | the tree diverged this week while lanes worked in it | print the file sha256 beside every line citation |

## 4. The goal final requirement — BLOCKED BY THE OWNER OWN ORDER, not by work

This round objective ends with "a clean, single-summary `_main/_audit-verify-all.cmd` run at
exit code 0". **That run cannot happen while the owner stop order stands.** The order is
recorded verbatim in the root `AGENTS.md`: *"para de abrir o sotto, ta travando meu pc quando
ele abre"*, and the same file names that battery explicitly as forbidden —
`_main_audit-verify-all.cmd` "lanca o shell dezenas de vezes". Launching it would be
disobedience dressed as rigour, and the owner is the one who has to live with the machine
it hangs.

What IS run at every commit instead, and is green at HEAD: the refactor-safe suite
(`node app/shadowplay/run-all.mjs`, 15 suites + `GATE 9 passed / 0 refused`, run by
`scripts/pre-commit` on every commit) plus the 25 in-process instruments listed in
section 5, none of which launches anything.

## 5. Closed THIS session, with the instrument that proves it

| item | closure | instrument |
|---|---|---|
| meter chain (the owner staircase) | worker emits the level stream | `_main/meter-chain-oracle.py` 55 checks + neg 66 |
| audio meter oracle RED | driver never forwarded the block period | `_main/audio-meter-oracle.py` 11 PASS + both neg modes |
| row #9 + F2 (flags discarded) | discontinuity counted in BOTH loops | `_main/audit-rows-tap-flags-ledger.py` 0 of 4 live |
| row #5 (blind census) | DETACHED_PROCESS dropped: 0 rows -> 14 rows | `_main/audit-rows-landmine-child-control.py` arm r5 |
| row #33 (stale OFFSCREEN comment) | sentence replaced by the real cure | `_main/audit-rows-byte-claims.py` arm r33 |
| row #34 (three oracles orphan a child) | tree-kill handler on all three | same instrument, arm r34 |
| row #35 (dead constant + unhandled wait) | handler added, constant removed | same instrument, arm r35 |
| rows #44/#47/#48/#54/#56/#57/#63/#49/#50/#51/#45 | docs corrected to the bytes | the row-specific oracles, all green |
| the 13 products diffs of the sweep section 6 | items 8, 9, 10 applied (comment, census, discontinuity) | receipts `receipt-20261011-audit-rows-sweep.md` addenda 1-4 |

## 6. Not measured, said plainly

- Nothing in this session launched the product, the worker or the shell. Every closure above
  is either a byte-level measurement or an in-process instrument.
- The T2 startup flash (rows #4/#46) remains UNMEASURED and its four numbers still
  contradict each other; the conflict is DECLARED in AGENTS.md rather than resolved.
- The meter wire has never crossed a real stdout pipe, and no bar has been painted from it.
- The discontinuity bit was counted against a scripted vtable; no real device has set it here.
- `_main/_probe/` is git-ignored (`.gitignore:60`), so the census fix lives on this box only.

