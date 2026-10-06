# flat-endpoint receipt — lane SottoFlatEndpoint (2026-10-06)

Ticket 140ba250c2f890e1e8bbf62d. Target `H:/sotto/worker/wasapi_loopback.py`
(27856 B, sha256 `10A1E611A9D701AC222AAEE1DD98FA3952FA8E423805FBBC4BBCB701ADA68F6D`).
`sotto_worker.py` NOT changed. Nothing under `app/` touched.

## Acceptance, each item with its measurement

| acceptance item | result |
|---|---|
| `py -3 -m py_compile worker/wasapi_loopback.py` rc=0 | rc=0, re-run against the final sha |
| NEW oracle RED with old code, GREEN with new, control pair printed | `_main/flat-endpoint-oracle.py`: LIVE sha `10A1E611` PASS 8/8 (9/9 with `--with-tap`); CONTROL = frozen pre-fix copy sha `2A2F8021` RED on 5 arms; exit 0 only when LIVE is green AND the control is red |
| report `docs/audit/flat-endpoint.md` with changed lines, BEFORE and AFTER, proof that `nonzero_blocks` left 0 | written, 23113 B; `_main/flat-endpoint.diff` = 8 hunks / +141 / -12; §2 BEFORE/AFTER; `self-audit-lint.sh` rc=0 |
| no "fixed" without the peak/nonzero measurement | BEFORE `nonzero_blocks=0 peak=0.000092 rc=3`; AFTER `nonzero_blocks=451 peak=0.465224 captions=42 rc=0`, same command, same audio, same window |

## BEFORE / AFTER (defect branch, real audio, `flat-endpoint-ladder.py mta`)

BEFORE (`_main/flat-endpoint-BEFORE-mta.err`):
`WORKER_STATS tag=final blocks=100 ... nonzero_blocks=0 peak=0.000092 rms=0.00002146 ... captions=0 ... audio_s=8.96`, rc=3,
candidate list WITHOUT the WASAPI rung, `verdict=silent-device device_outcome=all-flat`.
This reproduces `_main/_live_owner3.log:61` digit for digit.

AFTER (`_main/flat-endpoint-AFTER-mta.err`):
`WORKER_STATS tag=final blocks=451 ... nonzero_blocks=451 peak=0.465224 rms=0.05580778 ... captions=42 ... audio_s=44.80`, rc=0,
`tap_ledger[0] rung="a" rung_why="WASAPI loopback of the default render endpoint" settled=true captions=42`,
`proved_alive=true proved_reason=caption rotations=0`, captions are the fixture's own words.

Regression check (natural branch, both arms rc=0, still rung (a)):
BEFORE-natural `nonzero_blocks=601 peak=0.465224 captions=59`; AFTER-natural `nonzero_blocks=451 peak=0.465224 captions=43`.

## Oracle

LIVE: `s-false-is-success` OK (proceed, init=1 uninit=1 device=1); `s-ok-is-success-and-balanced` OK;
`changed-mode-usable-no-ref` OK (proceed, uninit=0) [CONTROL]; `genuine-failure-refused` OK (raise
`CoInitializeEx failed: Erro não especificado (0x80004005)`); `real-two-calls-one-thread` OK (both return,
init=2 uninit=2); `real-sta-mismatch-usable` OK (raw sta->mta=0x80010106, module proceeds,
CoUninitialize=0) [CONTROL]; `silent-flag-is-silence` OK (peak=0.000000000, silent_packets=3);
`unsilenced-packet-kept` OK (peak=0.000091553) [CONTROL]; `live-tap-opens` OK [opt-in].

MUTANT (frozen pre-fix, sha 2A2F8021) RED on 5: s-false-is-success (raise 0x00000001),
s-ok-is-success-and-balanced (uninit=0), genuine-failure-refused (CRASH OverflowError),
real-two-calls-one-thread (2nd RAISED), silent-flag-is-silence (peak=0.000091553), live-tap-opens (WasapiError).
Both CONTROL arms are green on BOTH subjects, so the red arms fail for the right reason.

## Refuted prediction (recorded, not buried)

Prediction: making `RPC_E_CHANGED_MODE` fatal (the literal reading of "keep the negative HRESULTs as
errors", and the sibling oracle's `changed-mode-raises` arm) would re-create the flat endpoint.
REFUTED by `_main/flat-endpoint-control-changedmode.py`: rung (a) IS removed from the candidate list
(measured), but the ladder still carried the audio through `CABLE Output` and emitted 24 captions
(`nonzero_blocks=343 peak=0.40097 rc=0`). What survives is only "changed-mode fatal removes rung (a)".
Decision: `RPC_E_CHANGED_MODE` stays a STATE (`COM_ALREADY`, no reference taken, so no CoUninitialize),
and every other negative HRESULT stays an error (arm `genuine-failure-refused`).

## Self-audit

protocolos em falta — (1) peer coordination via `write agent://<id>` is refused in this build
("no delegation seam"); I only learned it by trying to warn the sibling lane that wrote
`_main/wasapi-com-init-oracle.py` that one of its arms demands a regression — the finding had to be
buried in the report. Next time: verify the coordination channel BEFORE measuring a defect another
lane is already instrumenting. (2) I started running the worker BEFORE freezing the pre-fix source as
an oracle artifact; the freeze happened in time by luck, not by protocol. Next time: freeze the
pre-fix source first and write its sha into the oracle.

verificacao adicional — the cheapest confidence-raising check I did NOT run is a SECOND run of each
live A/B arm (§2 is one run per arm, a pair and not a distribution, and §6 shows the owner's routing
changes between runs). Cost: ~2 min per arm plus ~30 s model load, with audio playing.

checkboxes novas — (a) freeze the pre-fix source and have the oracle REFUSE to run if the frozen hash
drifts (implemented as `MUTANT_SHA256`); (b) every red oracle arm must ship a CONTROL that is green on
BOTH subjects, or "never raise" / "zero everything" can pass vacuously; (c) any arm that drives a real
loop against a scripted vtable must have an iteration cap — my own first `_next_size` returned 0 and
the real pump polls on that, hanging the oracle until I capped it at 10000.

review por outro subagente — sim-com-escopo: (1) try to turn the oracle's CONTROL green (by changing
the frozen copy or `MUTANT_SHA256`) to prove the red is real; (2) read §6 and look for a measurement
that sustains keeping `RPC_E_CHANGED_MODE` non-fatal on a host with NO virtual cable — the only claim
here sustained by the module's design rather than by measurement; (3) review `_pump` line by line, since
arms 7/8 use 480-frame blocks and the SILENT|DATA_DISCONTINUITY interaction is untested.

gate-doubt
- verde-de-verdade: the oracle's `VERDICT PASS` is real and could not pass vacuously — the CONTROL
  line in the SAME command run prints a DIFFERENT subject (sha 2A2F8021) RED on 5 arms; there is no
  stale artifact (`load()` pops sys.modules by explicit path) and no hand-supplied flag. The weakest
  green is the live A/B: same device and same audio, but sequentially and with the module imported
  inside the worker process, so there is no isolation between the arms, only sequence. `py_compile`
  rc=0 is green by construction and proves no behaviour.
- falta-no-gate: `silent_packets > 0` in a LIVE run (only the scripted arm proves it) and
  SILENT + DATA_DISCONTINUITY (0x1|0x2) in the same packet. A future change that crosses the hole:
  someone drops `block_ms` to 20 ms on an idle desktop — most packets become SILENT-flagged and the
  block cadence then comes only from the silence branch; no gate in this repo compares `blocks`
  against `silent_packets` in a real run.
- gate-melhor: `py -3 _main/flat-endpoint-oracle.py` goes RED if the SILENT branch is deleted from
  `_pump` (input: `worker/wasapi_loopback.py` without `flags.value & AUDCLNT_BUFFERFLAGS_SILENT`) —
  measured on the frozen copy, `silent-flag-is-silence` RED with peak=0.000091553. The mechanical
  check that is MISSING is live silence: `--with-tap` does not verify it (it opens 0.3 s with the PC
  possibly playing). It would close with a `live-idle-is-silent` arm: with NOTHING playing, require
  `silent_packets > 0` AND `peak == 0.0`, RED if `peak > 0`. Not written: it needs proof the machine
  is actually idle, which I cannot establish from this session without an endpoint-level silence probe.

confianca — ALTA on defect 1 (the card's numbers reproduced digit for digit, mechanism measured three
independent ways, red/green printed for two subjects); MEDIA on defect 2 (wrong against the contract
and proven deterministically, live firing UNPROVEN); BAIXA on the §6 design claim (sustained by the
module's docstring, not by a measurement on a host without a virtual cable).

nao verificado — (1) live firing of `AUDCLNT_BUFFERFLAGS_SILENT` (`_main/bfrc_flags.out`: 0/800);
(2) behaviour on a host with no virtual cable installed (none exists here); (3) SILENT|DATA_DISCONTINUITY
in one packet; (4) a second run of each live A/B arm; (5) `silent_packets > 0` in a real worker run;
(6) the `app/` path (panel/shell) — out of scope by instruction; (7) repo lint/formatter over the
changed file — `py_compile` only (no lint config found for `worker/`).

## CACHE/PRICE (verbatim from `bash I:/!manager/scripts/cache-task-report.sh SottoFlatEndpoint`)

- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoFlatEndpoint.jsonl
- cache: read=13016204 write=0 hit=98.0269% (cache-read / input+cache-read); 75 usage rows; instrument scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported; exact per-model rates UNKNOWN — not recorded in this source)
- model + route: opencode-go-3/deepseek-flash (68 calls), opencode-zen/space-bunny-free (7 calls)
- usage rows: 75; input 261995; output 97845; cache-read 13016204; cache-write 0
- WHEN failed: 09:34:52.486Z break_items=8 | 09:36:47.001Z break_items=2 | 09:41:43.666Z break_items=3 (state=RESOLVED-BREAKS-OMP; 3 of 115934 OMP prefix-ledger rows)
- WHERE failed: session_id=01a11090-a596-74a9-bbe1-afcfcd16d7ec provider=deepseek-flash model=deepseek-flash item_index=0 turn_id=1791279292486 | item_index=68 turn_id=1791279407001 | item_index=129 turn_id=1791279703666
- verdict: UNKNOWN — no task-level acceptance verdict is stored; the ratio is descriptive, not a prefix-stability decision

## SELO DO DONO — resposta (nao tenho a ferramenta de dispatch; nomeio em vez de tentar)

- Sede `agents/SottoFlatEndpoint.md` ausente: o resolver (`hooks/live/selo-do-dono.ts`,
  `caminhoAssento`) le `C:/Users/Administrador/.omp/agent/agents/SottoFlatEndpoint.md`, i.e. FORA da
  arvore que o meu dispatch me autoriza (`H:/sotto`). Escrever essa linha de `tools:` e' uma chamada
  unica, e o DONO dela e' o store de agentes / quem despacha o assento — nao uma lane com restricao de
  caminho. Fica nomeado, nao tentado.
- Governadores VERMELHOS e seus donos (todos do lado do Manager, nenhum e' meu):
  `theorist-always-on` -> Task Scheduler / `scripts/theorist-always-on-scheduled.cmd`;
  `ManagerSessionRestart` -> Task Scheduler / `scripts/restart-session.cmd` -> `restart-session.ps1 -Visible`;
  `theorist-delta-guard` -> Task Scheduler / `scripts/theorist-delta-guard-scheduled.cmd` -> `theorist-delta-guard.ps1`.
  A cura exige um SINAL NOVO na linha CITADA (`sinalNovo(antes, depois)`), que eu nao posso produzir de
  dentro de H:/sotto: nao ha' produtor sob o meu alcance.

## Tickets

- `dfced8c15b4f7144c209bd0b` (experience, P3): `write agent://<id>` refused — no delegation seam.
- `2051631332c989dda4e1d42f` (friction, P3): `worker/wasapi_loopback.py` untracked by git, so `git diff`
  is silently empty for it and every lane freezes its own pre-fix copy by hand.
- `d3310d3f6693c0a3eb29e460` (experience, P3): `deliverables` resolves relative paths against the session
  cwd and prints a bare ABSENT for files that exist under the work root.
