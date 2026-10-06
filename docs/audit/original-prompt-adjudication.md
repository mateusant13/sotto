# Adjudication of the ORIGINAL PROMPT — does it still hold, and must it still be followed?

**Date:** 2026-10-06 · **Lane:** `SottoPromptReview` · **Scope:** read-only over `H:/sotto`,
`I:/!manager`, and `github.com/mateusant13/sotto`; only this file was written.
**Owner ask, verbatim:** *"veja se o prompt original ainda se sustenta e deve ser seguido."*

---

## 0. What the original prompt IS (and what is UNFOUND)

### 0.1 The requirement-bearing artefact: the FIRST COMMIT (`548a4a3`)

**Artefact:** `H:/sotto/README.md` + `H:/sotto/docs/README.md` + `H:/sotto/docs/roadmap.md`,
all landed in the repo's first commit

```
548a4a3791d78f3755ba8da8796929ed88861527  2026-10-05 21:40:12 -0300
Sotto: the plan, the mark, and the licence posture
```

**The line that makes it the prompt/vision** — `README.md:1-6`, verbatim:

> Real-time transcription of everything your computer says, docked to the right
> edge of the screen. Press Alt+C.
> Sotto listens to **system audio**, not just the microphone. It writes a live
> caption into an overlay while you play, call, or stream, and turns the result
> into a searchable archive organised by day, then by hour.

**Why this artefact and not another.** The owner pointed the agent at the repo himself
(`github.com/mateusant13/sotto`): session `01a10f72-c0a0-7284-9445-0cecfd6636ce`, user message
`2026-10-06T04:28:16Z` — *"https://github.com/mateusant13/sotto tu nao ta achando isso? no
manager? como que nao achou?"*. The published repo's `README.md` is **byte-identical** to the
local first-commit `README.md` (read side by side, this lane, today), and the repo carries no
other vision document. `docs/roadmap.md` is the requirement list (milestones M0–M6, the idle
contract, the risk register, the approval protocol) written the same day.

### 0.2 The owner's own prompt, verbatim (the acceptance sentence)

`H:/sotto/AGENTS.md:5` preserves it and it is present on disk in the session transcript
(`01a10f72-…`, user message `2026-10-06T04:47:55Z`):

> *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc.
> e legendas."*

This one sentence is the acceptance test every row below is measured against.

### 0.3 UNFOUND — the *literal* "source brief"

The first commit and `docs/roadmap.md:8` both cite a brief that is **not on disk**:

> `roadmap.md:8` — "## The thing the source brief got wrong / The brief describes a
> mic-to-caption pipeline: `microfone -> CPAL -> PCM 16 kHz -> speech`"
> `docs/README.md:8-11` — "The source brief describes a microphone-to-caption pipeline."

**Where I looked and did not find it** (all read-only):

| place | command / result |
|---|---|
| `H:/sotto` (all `*.md`,`*.py`,`*.json`, no `node_modules`) | `grep -rn "source brief\|original prompt\|the brief this came from"` → only *references* to the brief (roadmap/README + lane self-audits), never its text |
| `H:/sotto` git history | 5 commits only (`548a4a3` first); first-commit body names the brief but does not quote it |
| `I:/!manager/inbox` | 3 files, none mentions Sotto |
| `I:/!manager/state/{cards,decisions,inbox,design,claims,context,lanes,arrivals}` | grep `sotto` → no brief text |
| `archive.prompts` (searchable owner-prompt history) | `sotto`→6 rows, `CPAL`→0, `nemotron`→2 (2026-09), `tauri`→1, `parakeet`→1 (2026-09-27); the **earliest Sotto owner word on disk is `2026-10-06T04:22:42Z`** ("ignora os avisos etc. quero que tu apenas foque em terminar o sotto") — a *continuation*, i.e. the pre-repo prompt was given in a session the archive does not hold |

**Conclusion:** the original **prompt/vision** is adjudicated from the first-commit README +
roadmap (the vision as written down), with the owner's one-line acceptance as the standard. The
literal "source brief" (a mic→CPAL spec) is **UNFOUND on disk** and is *not* reconstructed here.

---

## 1. Every stated requirement, with today's verdict

Vocabulary: **HOLDS** = still true and still worth following · **CHANGED** = the owner or a
measurement redirected it (later owner words cited where on disk) · **OBSOLETE** = contradicted
by measurement. Every row carries a path or a measurement.

| # | requirement (source line) | verdict | today's evidence |
|---|---|---|---|
| R1 | **Alt+C shows the transcriptions in real time, of ANY audio on the PC, as captions** (`AGENTS.md:5`, owner verbatim) | **HOLDS** | Unchanged on disk; it is the acceptance this lane's peers are chasing. `app/webview/README.md` — Alt+C is "the global toggle"; `_main/live-owner.log` line 5 `HOTKEY_REGISTERED accelerator=Alt+C … isRegistered=true` |
| R2 | **Listen to SYSTEM AUDIO, not just the microphone — WASAPI loopback of the render endpoint, no virtual device** (`README.md:4-7`; `roadmap.md:14-21`) | **HOLDS** | `worker/config.json` `preferred_devices: []` + `_comment` (universal ladder); `worker/wasapi_loopback.py` is the ctypes WASAPI loopback; `_main/capability-probe.log` verbatim `IAudioClient::Initialize(SHARED\|LOOPBACK) -> OK … peak=0.350000 … VERDICT: YES — this PC can capture system audio with NO virtual cable` |
| R3 | **Overlay docked to the right edge; Alt+C toggles it** (`README.md:1-2`) | **HOLDS** | `app/webview/sotto_webview.py:318` `dock_right(work, width=PANEL_WIDTH, height=PANEL_HEIGHT, margin=PANEL_MARGIN, dock='right')`; constants `:82-84` `380 / 900 / 12`; run.cmd "starts hidden and waits for Alt+C" |
| R4 | **Shell = Tauri 2 + Rust + Svelte 5 + TypeScript. No Electron** (`README.md:50-52`; `roadmap.md:53-64`) | **OBSOLETE** | Commit `460125a5` — *"the panel Alt+C actually toggles, plus the two findings that killed Tauri"*; the app is now **WebView2 + Python**: `app/webview/README.md` "`sotto_webview.py` … WebView2 (pywebview 6.2.1 + pythonnet)"; owner ruled, quoted in that file: *"sem fallback. webview2 é pra funcionar, pronto."*; owner `2026-10-06T04:47:07Z` — *"sim, usa o webview ou tauri sei la"* |
| R5 | **Capture through CPAL** (`roadmap.md:12`, `:22-24`, `:53-55`) | **CHANGED** | `roadmap.md` itself: *"CPAL alone is **not sufficient**"*; today = native WASAPI loopback (`worker/wasapi_loopback.py`) + PortAudio **callback** stream — `worker/README.md` "Capture uses a callback stream. Blocking reads fail on this host with `PaErrorCode -9999`" |
| R6 | **Streaming ASR: Nemotron 3.5 streaming while recording** (`README.md:55`; `roadmap.md` M3) | **HOLDS** | `worker/config.json` `model.dir = models/nemotron-3.5-asr-streaming-0.6b-int8` (shipped, `providers: [CUDAExecutionProvider, CPUExecutionProvider]`); `worker/README.md` §Model — the live caption model is the NVIDIA Nemotron 3.5 streaming RNNT |
| R7 | **Batch ASR: Parakeet Redux through `transcribe.cpp`, for the canonical transcript afterwards** (`README.md:20-24,55`; `roadmap.md:58-60`) | **CHANGED** | The general-transcription path is separate and different today: `_main/../asr-test/resultado.txt` (manager scratch `…/scratch/_scratch/asr-test/`) measures **"Parakeet v3 int8, CUDA (o modelo ACTUAL)" RTF 0.256** vs **"Parakeet Redux, CUDA" RTF 0.769**; and `docs/oss-approaches-20261006.md:122-131,236-238` states the authoritative-Parakeet final (A2) "**needs a second model. Not started**" |
| R8 | **No resident Python; `transcribe.cpp` is the C++ runtime that makes that reachable from Rust** (`README.md:25-27`) | **OBSOLETE** | The product **is** Python: `H:/sotto/AGENTS.md` layout — "`app/webview/run.cmd` **THE APP** … the shell the app IS", `run.cmd` `start`s `pythonw.exe sotto_webview.py`; the worker is `worker/sotto_worker.py` on `onnxruntime-genai` (no `transcribe.cpp` anywhere in the tree) |
| R9 | **Diarization — TBD, needs a non-Python path** (`README.md:56`; risk register `roadmap.md:105`) | **OBSOLETE** *(as stated)* | The non-Python constraint is void (R8); the roadmap's own escape applies — *"find the native export, **or cut diarization from v1**"* — and no diarization module exists in `worker/` or `app/` today |
| R10 | **Search store: SQLite + FTS5 + sqlite-vec, one database, one file** (`README.md:57-58`; M4/M5) | **CHANGED** | No SQLite/FTS5/sqlite-vec anywhere in the tree (`grep -rn "sqlite\|FTS5\|sqlite-vec" worker/ app/` → hits only inside ONNX weight blobs). The live store is a **markdown folder tree**: `sotto_webview.py:1682-86` — *"Layout: `<root>/<YYYY-MM-DD>/<HH>.md` — a 24 h folder, one file per hour, appended as captions commit"*, `HISTORY_ROOT` default `H:/sotto/history`, reason stated in-file: *"the owner asked for the data to live under H:/sotto"* |
| R11 | **Searchable archive organised by day, then by hour** (`README.md:6-7`) | **HOLDS** | Same artefact: `HISTORY_DAY_RE = ^\d{4}-\d{2}-\d{2}$`, `HISTORY_LINE_RE = ^-\s+\[HH:MM:SS\]\s+(.*)$` (`sotto_webview.py:97-98`), plus panel surface `#history-list .hist__folder` (`:977`) and `reveal_in_folder` (`:1783`) |
| R12 | **Idle contract: with no audio, nothing resident but the shell and the database; every model worker on demand; each row proved by a sampled RSS** (`roadmap.md:37-49`) | **CHANGED** | The "database" term is void (R10). Today the shell is the WebView2 process (+33% vs Electron — `app/webview/README.md`, "416 MB vs 312 MB, measured, and ruled on anyway") and the worker is spawned on demand (`run.cmd --with-worker`); the post-activation **idle arm is being added now** (lane `SottoDeviceRouting`, running) — i.e. the idle *claim* is not yet a closed measurement |
| R13 | **Licence posture: parakeet-redux CC-BY-4.0 attribution required; nemotron `license:other` must be read before shipping** (`README.md:34-38`) | **HOLDS** | Never retracted; the shipped model is the nemotron 3.5 streaming ONNX export (`worker/config.json`), so the `license:other` gate still stands unread-for-shipping in this tree |
| R14 | **Approval protocol: a reviewer whose only job is to refute each milestone before it opens; a milestone whose exit cannot be made falsifiable does not open** (`roadmap.md:107-118`) | **HOLDS** | The house runs this today: dedicated falsifier/refuter lanes and two-colour oracles (e.g. `_main/panel-exit3-oracle.py --unit --neg-arm`, `_main/run-cmd-exit-oracle.py --neg-arm` in `app/webview/README.md`); the defects this lane's peers found were found by refutation, not by review |
| R15 | **Milestones M0–M6 with command-provable exits** (`roadmap.md:51-73`) | **HOLDS** *(as method; M0–M2 contents CHANGED)* | The *method* survives — the house now runs measured oracles per fix. M0's "Tauri 2 + Rust + Svelte" and M2's "Parakeet Redux through transcribe.cpp" are the changed contents (R4, R7) |

**Tally: 8 HOLDS · 4 CHANGED · 3 OBSOLETE** (15 rows; 8+4+3 = 15). HOLDS = R1,R2,R3,R6,R11,
R13,R14,R15; CHANGED = R5,R7,R10,R12 (plus the M0–M2 *contents* under R15); OBSOLETE = R4,R8,R9.

---

## 2. The verdict in one paragraph

The **product vision still holds and should still be followed**: real-time captions of any PC
audio, on an Alt+C overlay docked right, with a searchable day/hour archive. What is **dead** is
the *implementation half of the plan* — the Tauri/Rust/Svelte stack, the "no resident Python"
constraint, and `transcribe.cpp` (R4, R8), plus the non-Python diarization constraint (R9). What
**changed** is every mechanism the plan chose: CPAL → native WASAPI loopback + PortAudio
callback (R5); a two-model Redux/`transcribe.cpp` batch path → a separate Parakeet-v3 inference
path, with the live model being Nemotron streaming (R6/R7); SQLite+FTS5+sqlite-vec → an
on-disk markdown hour-file tree (R10); an idle contract measured against "shell + database" →
an idle contract still being closed, now against a WebView2 shell (R12). Follow the vision;
do not follow the stack.

---

## 3. What the original prompt did NOT anticipate

Three gaps today's work proved were missing from the plan. This is the part to act on.

**3.1 Speech/music separation.** The prompt assumed captured system audio *is* speech. Today the
worker carries a live `music_gated_chunks` counter (`worker/sotto_worker.py:541, :603, :1442,
:1860`) and a distinct verdict `captured-signal-has-no-speech` (`sotto_worker.py:2285`), and
`docs/audit/device-routing.md:262` names the case: *"rendered non-speech only (ambient/music) →
`captured-signal-has-no-speech`"*. The plan had no row for "the PC is playing music".

**3.2 Folder history.** The prompt planned a SQLite store; it never had a notion of a
browsable on-disk history. Today the transcript store is `<H:/sotto/history>/<YYYY-MM-DD>/<HH>.md`
with `#history-list .hist__folder` and "show in folder" (`sotto_webview.py:1682-86, :977,
:1783`), and the reason is written in the file: *"the owner asked for the data to live under
H:/sotto."* The prompt did not anticipate the owner wanting his data as a folder he can open.

**3.3 The verdict-word defect.** The prompt's "approval" section worried about *milestones*
passing vacuously; it never anticipated a **single run whose verdict word disagrees with its own
exit code**, or a `done` with **no verdict word at all** being painted as a healthy finish.
Both were measured and fixed 2026-10-06: `sotto_worker.py:2237-2253` (order `ran_but_silent`
before `all-candidate-taps-flat`, so `done.verdict == "silent-device"` iff `exit == 3`), and the
panel's positive test `if verdict not in HEALTHY_DONE_VERDICTS` (recorded in `AGENTS.md`, gate
`_main/panel-exit3-oracle.py --unit --neg-arm`). A plan that only audits milestones cannot see
this class.

---

## SELF-AUDIT

- **protocolos em falta** — I did not read `H:/sotto/AGENTS.md` end-to-end *as a document before
  searching*; I read it first (as the brief said) but then spent several turns re-searching for a
  "source brief" that the file itself names as a *derived* artefact. The protocol I should have
  followed is the one this repo already uses: **name the falsifier of "the artefact I concluded is
  the prompt" before searching** ("if a brief file existed, `git log` and `grep -rn` would name
  it") — which would have cut the `I:/!manager/state/**` sweep short.
- **verificacao adicional** — I compared `H:/sotto/README.md` and the GitHub copy by eye, not by
  hash. A `sha256sum` of both would have made "byte-identical" a number instead of a claim.
  Cost: 1 command (`sha256sum README.md` vs the API blob sha) — not run (the GitHub tool was
  refused by the `restart` guard mid-session; the raw file was read instead).
- **checkboxes novas** — "For an adjudication, cite each requirement to a `file:line` **and**
  each verdict to a `file:line` or a measured log line; a row with only prose is RED." Mechanic
  RED input: any row whose verdict cell lacks a path. This is the check that would have stopped
  me writing a vision paragraph instead of the R-table.
- **review por outro subagente** — **sim-com-escopo**: re-derive *only* §1's verdict column from
  the cited files (does the cited line in fact say that?). Not the prose (§2), not §3's framing.
- **gate-doubt**:
  - **verde-de-verdade:** the only "green" this lane produces is the R-table's own consistency,
    and it is **not machine-checked by anything** — there is no run whose green I am quoting. The
    measurements I *cite* are other lanes' (e.g. `_main/capability-probe.log` `VERDICT: YES`,
    `_main/asr-test/resultado.txt` RTF) and I read them on disk; I did **not** re-run any of them.
    So: no vacuous green *claimed*, but also no independent green *earned*.
  - **falta-no-gate:** nothing checks that a *requirement document* (README/roadmap) and the
    live tree agree. Scenario a future change walks straight through: someone edits `README.md`
    §Stack back to "Tauri 2, Rust, Svelte" (or deletes `docs/roadmap.md`), and no gate goes RED —
    `self-audit-lint.sh` validates a SELF-AUDIT block's *shape*, not its content, and the
    `docs/audit/00-MAPA-*` maps audit *findings*, not *requirements*.
  - **gate-melhor** — a `requirements-drift` check: for each requirement row carrying a
    `file:line`, assert the cited path exists and the cited line still matches a regex; RED input
    = a copy of this file whose R4 evidence line is deleted. Command shape:
    `py -3 H:/sotto/_main/req-drift-check.py docs/audit/original-prompt-adjudication.md` → `rc=1`
    naming R4 when `README.md` no longer contains "Tauri 2". *n/a today — no such script exists
    (this lane is read-only except this file).*
- **confianca** — **alta** that the vision is the first commit (path + the byte-identical GitHub
  copy + the owner's own pointer to that repo); **media** on R12 (the idle claim is still open —
  the arm is being added by a running lane) and on R9 (OBSOLETE *as stated* is a judgement about a
  dropped constraint, not a measurement of a failing one). What would move both to alta: a live
  idle RSS sample, and a line in the tree that diarization is out of scope.
- **nao verificado** — (1) the literal source brief (UNFOUND — §0.3); (2) the GitHub repo's commit
  history beyond the local 5 (the `github` tool was refused by the `restart` guard; the raw
  `README.md` was fetched, the commit list was not); (3) no oracle re-run (R2/R6/R7/R11 rest on
  logs read from disk, not re-executed); (4) `sha256sum` equality of the two READMEs (see above);
  (5) whether `H:/sotto/history/` in fact contains hour files today (the code path exists; no
  directory listing was taken).

---

## CACHE/PRICE

Source: `bash I:/!manager/scripts/cache-task-report.sh SottoPromptReview` (verbatim output
pasted from that run, 2026-10-06T09:14:03Z).

- cache: read=5830656 write=0 hit=96.4673% (cache-read / input+cache-read); universe: 53 usage rows from `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoPromptReview.jsonl`; instrument: `scripts/cache-task-report.sh`
- price: $0.00000000 USD (source: session JSONL `message.usage.cost.total`; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: 2026-10-06T09:03:59.833Z, 09:04:00.314Z, 09:04:01.131Z, 09:05:58.303Z, 09:10:57.927Z — 5 prefix-break events (state=RESOLVED-BREAKS-OMP; 5 of 114912 OMP prefix-ledger rows attributable to keys `01a10f72-c0a0-7284-9445-0cecfd6636ce` / `SottoPromptReview`)
- where-failed: session_id=01a11074-7b15-7268-8b97-e437f67310d3 — item_index=0 (space-bunny-free), item_index=0 (ling-3.1-flash-free), item_index=0 (deepseek-flash), item_index=44, item_index=131
- source: `scripts/cache-task-report.sh` over this lane's own session JSONL (53 usage rows); tokens — input 213524, output 34265, cache-read 5830656, cache-write 0; models opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free; the reporter's own verdict: "UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision"
