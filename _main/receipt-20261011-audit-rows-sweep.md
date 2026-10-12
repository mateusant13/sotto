# Receipt — audit register sweep: 21 OPEN rows read against the live bytes

**Lane:** register sweep (delegated). **Date:** 2026-10-11, 19:4x–20:2x -03:00.
**Subject:** `docs/audit/00-MAPA-CONSOLIDADO.md` rows that were **OPEN** and are decidable by
bytes, parse, or IN-PROCESS execution. **Nothing was launched.**

## 0. Order compliance (owner order of 2026-10-11: "para de abrir o sotto")

Every instrument in this sweep is one of: read bytes, `json.loads`, `re`, `ast`, `importlib` a
module and drive its own objects, or spawn a **short-lived file-reader** child with
`creationflags=0x08000000` (CREATE_NO_WINDOW) and `windowsHide`. **No `run.cmd`, no
`sotto_webview.py` process, no worker, no WebView2, no electron, no device, no
`_audit-verify-all.cmd`.** The process census at the end of this sweep found **no process whose
command line names any file written by this lane** (see §7). `TMPDIR=I:\cc-tmp` for every child.

## 1. Pins (the revision each measurement was taken against)

| file | bytes | sha256 (first 24) | mtime (2026-10-11) |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 440 186 | `4295AEABED6727721A125C2C` | 19:42:49 -03:00 |
| `worker/sotto_worker.py` | 304 762 | `771ACA94AB3E3B3AD37498CA` | 20:09:27 -03:00 |
| `worker/wasapi_loopback.py` | 51 215 | `09C65E941D75738417F0E209` | 2026-10-06 |
| `worker/config.json` | 5 882 | `6B788A9EE7BEFB3F814E55F6` | 2026-10-07 18:19:25 |
| `AGENTS.md` | 89 861 | `DA85A6F9762EB4F35B50C902` | 20:09:27 -03:00 |
| `docs/audit/00-MAPA-CONSOLIDADO.md` | 41 612 | `3F74BCB2B4B72A6742BA5282` | 20:15:14 -03:00 |
| `app/panel/panel.js` | 138 379 | `A14C0A96E69F759E2584BA0D` | 19:53:57 -03:00 |
| `app/_legacy-electron/worker-bridge.js` | 34 756 | `2F42BFC7BE5911A7364A30AC` | 2026-10-06 |
| `_main/model-spec-oracle.py` | 4 912 | `E93792084CF3D083E96C0B58` | 20:13:02 -03:00 |
| `_main/_oss_oracle.py` | 5 927 | `F44AB1C8FA8CA51C8889A634` | 20:14:48 -03:00 |
| `_main/runcmd-entry-report.json` | 14 521 | `5BC972D391A51F78ED146F49` | 2026-10-06 07:47:26 |

**Three subjects moved while this sweep ran** (rule 2 of "Keeping THIS file true"): the worker
(291 873 B → 304 762 B), the register (36 541 B at first read → 41 612 B), and BOTH oracles
(`model-spec-oracle.py` rewritten at 20:13:02 and `_oss_oracle.py` at 20:14:18 **and again** at
20:14:48). Where a number below is older than the pin in this table it says so.

## 2. The five instruments (new; all under `_main/`)

| instrument | bytes | sha256 (first 16) | mtime | runtime | VERDICT |
|---|---|---|---|---|---|
| `_main/audit-rows-bridge-decisions.py` | 21 347 | `E3187E38BB956F91` | 19:59:51 | 0.9 s | **PASS** live=8/8 (7 defects present, 1 refuted), 8/8 mutants flipped |
| `_main/audit-rows-tap-flags-ledger.py` | 15 895 | `856618BF074BE052` | 20:01:28 | 0.4 s | **PASS** 1 of 4 defect claims present, 4/4 mutants flipped |
| `_main/audit-rows-landmine-child-control.py` | 24 536 | `C97560FE6C2F752E` | 20:08:58 | 13.3 s | **PASS** 4/4 landmines reproduced, 4/4 mutants flipped |
| `_main/audit-rows-negative-arm-falsifiability.py` | 17 118 | `E31DBA8781DE1D26` | 20:15:45 | 1.0 s | **PASS** both oracles driven + blinded, receipt mutant flipped |
| `_main/audit-rows-byte-claims.py` | 13 327 | `CDDC9D4ADF2B9701` | 20:13:05 | 0.1 s | **PASS** 4 rows, 4/4 mutants flipped |

Run them with (all five exit 0 on PASS, 1 on FAIL, 2 on a dead anchor — never silently):

    py -3 _main/audit-rows-bridge-decisions.py
    py -3 _main/audit-rows-tap-flags-ledger.py
    py -3 _main/audit-rows-landmine-child-control.py
    py -3 _main/audit-rows-negative-arm-falsifiability.py
    py -3 _main/audit-rows-byte-claims.py

Full raw output of the five final runs: `I:\cc-tmp\audit-rows-sweep\*.log` (bridge-decisions
26 068 B, tap-flags-ledger 14 679 B, landmine-child-control 22 408 B, negative-arm-falsifiability
12 169 B, byte-claims 13 819 B). Every arm prints `DEFECT-PRESENT` / `DEFECT-REFUTED` (or
`defect=… expected=…`) and each mutant section must flip **only** the arm it targets.

**Every arm can say NO.** Nine mutants were built as COPIES under `%TEMP%`: 8 in instrument 1
(`m11-falsifier-off`, `m12-empty-caption-refused`, `m13-start-reports-child`,
`m15-restart-timer-cancelled`, `m38-payload-carries-tag`, `m41-unknown-type-silent`,
`m42-stop-emits-status`, `m43-restart-takes-lock`), 4 in instrument 2, 4 in instrument 3, 2+1 in
instrument 4 and 4 in instrument 5. Each replacement anchors on ONE literal asserted to occur
exactly once; a dead anchor makes the instrument **exit 2**, not pass.

## 3. Rows settled (21)

| row | verdict | one line |
|---|---|---|
| 5 | CONFIRMED | the census channel is 0 B with rc 0 under the file's own flags |
| 9A | **REFUTED** | SILENT IS examined: `silent_packets: 4`, delivered peak 0.0 |
| 9B | CONFIRMED | a `DATA_DISCONTINUITY` run is byte/peak-identical to the clean control, counters identical |
| 9C | **REFUTED** | the loss IS counted: `position_gap_packets: 3` on a position jump |
| 11 | CONFIRMED | the falsifier rewrites a REAL worker error to "Capture not started" |
| 12 | CONFIRMED | an empty caption counts as proof-of-life and lifts the death banner |
| 13 | CONFIRMED | `start()` returns True with `child_is_none: true` and 0 spawns |
| 15 | CONFIRMED | two restart timers pending, the first never cancelled |
| 33 | CONFIRMED | `:3552` still claims the flash is handled by an OFFSCREEN creation that does not exist |
| 34 | CONFIRMED | `wait(timeout=)` with no handler leaves the grandchild alive |
| 35 | CONFIRMED | `run-live-hidden.py` `:44` unhandled + `DETACHED_PROCESS` `:25` dead |
| 38 | CONFIRMED | the stats payload is `{peak, blocks}` — no `tag`, so a tick is indistinguishable from the total |
| 39 | **REFUTED** | `np.concatenate` is NOT called on every emit: 0 calls with one pending array |
| 41 | **REFUTED** | a typeless line is dropped but **logged** (`BRIDGE_UNKNOWN type=None`), not silent |
| 42 | CONFIRMED | `stop()` emits 0 statuses |
| 43 | CONFIRMED | `_restart` → `_spawn` with `restart_path_locked: false` |
| 46 | CONFIRMED (doc) | both contradictory flash sentences are still in `AGENTS.md` (`:578` and `:627`); the flash itself is NOT MEASURED |
| 48 | **CLOSED** | `STATE_MAP` declared at `worker-bridge.js:114`, lookup `:223`; `AGENTS.md:526` now cites `:114` |
| 54 | CONFIRMED (numbers stale) | `config.json` = 5 top-level keys, 17 leaves, 11 non-comment leaves — not 13, not 8 |
| 56 | **CLOSED IN CODE** (20:13Z) and verified here | new `--neg-arm` PASSES and FAILS when blinded |
| 57 | **CLOSED IN CODE** (20:14Z) — but the new arm has a measured defect | its control line is a label, not a measurement |
| 58 | CONFIRMED | the report has only the `caption` key; the refusal is measured in-process |
| 62 | mechanism CONFIRMED / instantiation NOT MEASURED | a 2-level tree survives the timeout; `taskkill /F /T` cures it |

## 4. Row by row — the row's own words, then the measurement

### #11 — "o falsificador de 'no audio' reescreve um erro REAL do worker"
`sotto_webview.py:7161` (`FALSE_AUDIO_ABSENT_RE`) runs BEFORE the worker's text reaches the panel.
Fed the worker's own real error string (`state=error stage=selftest detail="no audio at …"`):

    {"worker_said": "state=error stage=selftest detail=\"no audio at ...\"", "kind_emitted": "busy",
     "text_emitted": "Capture not started - the worker has not opened the audio device", "rewritten": true}

**CONFIRMED.** The panel is told *nothing was opened* when the worker said *a device WAS opened and
heard nothing* — a different fact with a different owner action. Mutant `m11-falsifier-off` (the
branch deleted) → this arm alone flips to REFUTED.

### #12 — "uma legenda VAZIA conta como prova de vida e limpa o aviso de morte"
`sotto_webview.py:7460`: `text = message.get('text')` — only `None` is refused, `''` passes.

    {"caption_text": "''", "captions_counter": 1, "malformed_counter": 0, "death_lifted": true, "lift_logged": true}

**CONFIRMED.** An empty caption clears a device-death banner. Mutant `m12-empty-caption-refused`
(`if not text:`) → flips.

### #13 — "`start()` devolve true sem worker nenhum"
Semantics are decided by the documented launch, so the ORACLE is "does the DOCUMENTED launch
transcribe?" (this lane's reading of the register row is stated in the instrument header).

    {"start_returned": true, "child_is_none": true, "spawns": 0, "state": "missing",
     "restart_scheduled": true, "returns_true_with_no_worker": true}

**CONFIRMED.** `start()` is a request, not a result, and it does not distinguish "spawning" from
"the worker path does not exist". Mutant `m13-start-reports-child` → flips.

### #15 — "`_schedule_restart` sobrescreve o timer sem cancelar o anterior"
`sotto_webview.py:7779` builds a new `threading.Timer` and assigns it to `self._restart_timer`.

    {"first_is_second": false, "first_still_alive": true, "second_alive": true,
     "restart_log_lines": ["BRIDGE_RESTART", "BRIDGE_RESTART"], "timers_pending": 2, "overwrites_without_cancel": true}

**CONFIRMED.** Two live timers can call `_restart` for one bridge. Mutant
`m15-restart-timer-cancelled` (`if self._restart_timer: cancel()`) → flips.

### #38 — "um tick de meio de corrida pode ser lido como o total da corrida"
`sotto_webview.py:5878` copies ONLY `('peak', 'blocks')` out of `last_worker_stats`.

    {"stored_tag": "final", "tick_payload": {"peak": 0.1, "blocks": 42.0},
     "final_payload": {"peak": 0.4, "blocks": 99.0}, "payload_has_tag": false,
     "payloads_differ": true, "tick_indistinguishable_from_total": true}

**CONFIRMED on the shell side**: the mid-run tick and the run total produce the SAME SHAPE, so the
panel (which reads only `fields.peak`/`fields.blocks`, `app/panel/panel.js:2640-2648`) cannot tell
them apart. **NOT MEASURED: whether a `tag=tick` line ever reaches the shell at all** — a sibling
lane owns the meter chain and has already recorded that the worker never emits
`{"type":"meter"}` (see §7). Mutant `m38-payload-carries-tag` → flips.

### #39 — "`_pump` copia o acumulador com `np.concatenate` a cada emit"
`worker/wasapi_loopback.py:1024` is `joined = np.concatenate(buf) if len(buf) > 1 else buf[0]`.
Driving the real `_pump` against a scripted `IAudioCaptureClient` vtable, with `np.concatenate`
counted through a proxy:

    one_pending_array     : emits 4, blocks [250,250,250,250], concatenate_calls 0,   concatenate_elements 0
    several_pending_arrays: emits 4, blocks [250,250,250,250], concatenate_calls 4,   concatenate_elements 1100
    copies_even_with_one_pending: false        copies_per_emit_multi: 1.0

**REFUTED as worded.** With one pending array (the steady state) it copies NOTHING; with several it
copies once per emit. The row's cost claim is real only in the multi-array case. Mutants in
instrument 2 → each flips its own arm.

### #9 — three claims about the tap's flag handling (one row, three verdicts)
`AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002` (`:68`); counters `silent_packets` (`:733`),
`position_gap_packets` (`:738`).

    A "SILENT is never examined"      -> emits 2, peak_per_block [0.0, 0.0], silent_packets 4,
                                         silent_flag_ignored: false       => REFUTED
    B "DATA_DISCONTINUITY is never examined" -> discontinuity vs control: audio_identical true,
                                         counters_identical true, discontinuity_invisible: true  => CONFIRMED
    C "the loss has no counter"       -> position jump with flags 0: position_gap_packets 3,
                                         loss_uncounted: false            => REFUTED

**One claim survives**: `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY` (0x1) is not examined — a run with
the bit set is **byte- and peak-identical** to the clean control and every counter matches. This is
the only arm in the whole sweep where the honest answer is "the defect is still there".

### #5 — "`console-census.py:106` passa `CREATE_NO_WINDOW|DETACHED_PROCESS` → canal de 0 bytes, rc 0, logo `python_pids()` fica cego"
Reproduced with harmless children (a child that prints 83 rows, this box, this run):

    channel_live_flags      : {"flags": "0x8000008", "rc": 0, "stdout_bytes": 0,   "rows": 0}
    channel_create_no_window: {"flags": "0x8000000", "rc": 0, "stdout_bytes": 2448, "rows": 17}
    m5-census-flags-fixed__console-census.py  4987 B  sha256 1FEEC7815711C846

**CONFIRMED.** `DETACHED_PROCESS` is the poison: with it the child gets no console and no pipe
data, and the caller sees rc 0 with an empty channel — an absence that cannot be distinguished from
"no processes". The mutant (the flag removed) makes the SAME channel return rows. **The row's own
anchor `:106` was NOT re-checked by launching the census** (it is a probe that spawns children); the
mechanism was reproduced with the same flag word instead.

### #34 / #35 — `wait(timeout=)` with no handler, and a dead constant
Two-level tree, timeout 2 s:

    timeout_no_handler    : timeout_expired true, direct_child_alive_after_timeout false,
                            grandchild_alive_after_timeout true   (handler: none)
    timeout_with_tree_kill: timeout_expired true, direct_child_alive_after_timeout false,
                            grandchild_alive_after_timeout false  (handler: taskkill /F /T)

**BOTH CONFIRMED.** `Popen.wait(timeout=)`/`subprocess.run(timeout=)` kill only the direct child;
the descendants survive, still holding whatever they hold. A `try/except TimeoutExpired: taskkill
/F /T` cures it in the same measurement. Mutants `m34-tree-kill-on-timeout` and
`m35-constant-removed-handler-added` → each flips its own arm.

### #62 — "`subprocess.run(timeout=)` à volta do `electron.exe` multi-processo pode não ser tecto [INFERENCE]"
**The MECHANISM is now MEASURED** (see #34 above: a 2-level tree survives a `subprocess.run`
timeout; `taskkill /F /T` cures it). **The electron INSTANTIATION is NOT MEASURED**: launching
`electron.exe`/the shell is forbidden by the standing order, and `AGENTS.md` correction §2 declares
that binary DEAD. The mutant `m62-electron-tree-kill` (the fix applied to `_main/_run-hidden.py`)
flips the arm, so the reading is live, not a label.

### #33 — "comentários obsoletos/contraditórios sobre a cura OFFSCREEN"
`sotto_webview.py` mentions OFFSCREEN at `:1010, :3522, :3552, :4031, :4853, :4854` — **all six are
comments/prose; there is NO executable use** (regex for an assignment or a call: 0 hits), and
`:1010` says the cure "was REMOVED 2026-10-06". `:3552` still reads:

    startup flash is handled by the OFFSCREEN creation position below.

**CONFIRMED.** The sentence points at a creation position that does not exist anywhere in the file.
Mutant `shell_no_stale_comment` → flips.

### #54 — "AGENTS/README listam 5 chaves do config; o ficheiro tem 13 (hoje 8)"
    top_level_keys          : [_comment_use_denoise, audio, model, output, use_denoise]  -> 5
    leaf_count_all          : 17
    leaf_count_non_comment  : 11   (audio.device, audio.preferred_devices, audio.block_ms,
                                    model.dir, model.lang_id, model.use_vad, model.providers,
                                    output.min_chars, output.partial, output.done_text_max_chars,
                                    use_denoise)
    row_says_13_or_8        : true

**CONFIRMED as a stale-number row; the row's two numbers are both wrong.** The file has **5** top-level
keys and **17** leaves (**11** excluding the `_comment_*` leaves). The register's own `row 54` in the
`AGENTS.md` Layout table already carries the corrected census (5 / 11), so the ROW is what is stale.
`worker/README.md:184-185` is blank + `## Audio` today — the row's second anchor does not hold
either. Mutant `config-13-keys` → flips.

### #48 — "`AGENTS.md` cita `worker-bridge.js:133` como STATE_MAP"
    state_map_declared_line : [114]
    state_map_lookup_line   : [223]
    agents_cite_line        : 526   ->  "carried (worker-bridge.js:**114**, where the table is DECLARED;
                                        :223 is the lookup -- this sentence cited :133 until 2026-10-11 …"

**CLOSED by another lane and re-measured here.** `AGENTS.md` now names `:114` as the declaration and
`:223` as the lookup, which is exactly what the file contains. Mutant `agents_old_citation` (the
citation reverted in a COPY) turns the arm's reading back to the defect, so the arm is not a rubber
stamp.

### #46 — "`AGENTS.md` contradiz-se sobre o painel no arranque"
    claim_zero_of_41_line : 578    ("arm P 0 of 41 samples at a 200 ms cadence")
    claim_visible_7s_line : 627    ("THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s")
    contradiction_present : true

**CONFIRMED as a DOC fact, and only as a doc fact.** Both sentences are still in the file. **Which one
is true is NOT MEASURED** — both numbers come from instruments that launch the shell
(`panel-startup-visibility-oracle.py`, `panel-startup-flash-census.py`), which the owner's order
forbids. Mutant `agents_one_claim_removed` → flips.

### #56 — "`model-spec-oracle` não tem braço negativo (detector de drift, não oráculo)"
**CLOSED IN CODE at 20:13:02 by another lane** (`_main/model-spec-oracle.py` 4 912 B), and verified
here by driving the new arm on a sandbox copy whose sha256 equals the live file's:

    plain_rc 0        | neg_arm_rc 0
    NEG-ARM M[chunk_samples=1234] : MISMATCH (RED as required)
    NEG-ARM M[blank_id=1]         : MISMATCH (RED as required)
    NEG-ARM control (live files)  : OK (green, as required)     VERDICT: NEG-ARM PASS
    blinded copy (comparison forced to a constant True):
    NEG-ARM M[blank_id=1] : OK -- THE ORACLE CANNOT SAY NO      VERDICT: NEG-ARM FAIL

**The closure is real**: the same arm driven against a blinded copy of its own oracle returns FAIL,
so the new `--neg-arm` detects the very blindness the row complained about. Mutant
`m56-oracle-cannot-say-no` → the arm's reading flips.

### #57 — "`_oss_oracle` não tem braço negativo"
**CLOSED IN CODE at 20:14:48 (its second rewrite in 30 s) — with a defect in the new arm.**
Driven on a sandbox copy (sha256 equal to the live file):

    plain_rc 0   PASS C1 / PASS C2 / PASS C3 / PASS C4   ORACLE GREEN (doc still true)
    neg_arm_rc 0 PASS NEG M1..M4 (each failing set is exactly its target)  NEG-ARM PASS

Then the SAME arm in-process with `checks()` replaced by a stub that answers **all-False for the live
tree** and exactly-one-False for the four mutant trees:

    stub_live_probed      : false
    stub_control_line     : PASS NEG control: the live tree is GREEN in this same process
    neg_arm_calls_checks_on_repo : false      (no call site passes REPO)
    control_line_unmeasured : true

**The control line is a LABEL, not a measurement.** `_main/_oss_oracle.py:92` prints
`all(results)` — the four MUTANT comparisons — under a sentence that claims the LIVE tree was checked
"in this same process". The stub proves the live tree is never consulted: it prints PASS while every
live check is False. A repaired copy (the line computing `all(checks(REPO, …))`) prints FAIL under
the same stub, which is what makes this a measurement rather than an opinion. See §5.

### #58 — "o braço `bogus` do `runcmd-entry-driver.py` não tem recibo"
    report_keys            : ["caption"]            (14 521 B, sha256 5BC972D391A51F78)
    driver_bogus_line      : 441   ("def arm_bogus(oracle, seconds: float = 8.0)")
    shell_parse_bogus_flag : SystemExit(2)
    shell_parse_check_args_only : returned args
    check_args_in_help     : false                  (argparse.SUPPRESS holds)

**CONFIRMED.** The driver HAS the arm (`:441`) but the report on disk carries a single key,
`caption` — the bogus arm was never recorded. What I could measure without launching `run.cmd`: the
shell's OWN parser refuses `--bogus-flag` with **SystemExit(2)** and accepts `--check-args` alone,
which is the pre-flight contract the wrapper relies on. **The wrapper leg (cmd → pre-flight →
`exit /b rc`) and the receipt itself are NOT MEASURED** — both require running `run.cmd`, which the
standing order names explicitly. Mutant: a report copy with a `bogus` key → the reading flips.

## 5. NEW item found (not in the register)

**`_main/_oss_oracle.py:92` — the new negative arm's control line is not measured.**

    print(('PASS ' if all(results) else 'FAIL ') + 'NEG control: the live tree is GREEN in this same process')

`results` holds the four MUTANT comparisons; nothing in `neg_arm()` ever calls `checks(REPO)`
(verified in-process with a stub that records whether it was asked about the live tree:
`stub_live_probed: false`). Consequence: if the live tree goes RED tomorrow, this line can still
print PASS and a reader will take it as "the control was green". This is exactly the failure mode the
register already named for `live-vs-history-source-oracle.js` ("a gate that supplies the thing it
then finds cannot say no"). Reported to the Lead; **not fixed here** (instrument scope).

## 6. Product fixes NOT written (exact location + proposed diff, for the Lead)

None of these was written by this lane. Line numbers are the pinned revisions in §1.

1. `app/webview/sotto_webview.py:7161-7164` (row #11) — do not rewrite a real worker error:

       elif FALSE_AUDIO_ABSENT_RE.search(value):
           self.log(f'BRIDGE_STATUS_FALSIFIED text={json.dumps(value)}')
           value = CAPTURE_NOT_STARTED
           kind = 'busy'
       ->
       elif FALSE_AUDIO_ABSENT_RE.search(value) and self.captions == 0:
           ...            # only claim "not started" while NO caption has ever arrived

2. `app/webview/sotto_webview.py:7461` (row #12) — refuse an empty caption:

       if text is None:
       ->  if not text:                       # '' is not proof of life

3. `app/webview/sotto_webview.py:7190` (row #13) — report the spawn, not the request:

       self._spawn()
       return True
       ->  return self._spawn() is not None   # or keep True and re-word the log line

4. `app/webview/sotto_webview.py:7781` (row #15) — cancel before overwriting:

       self._restart_timer = timer
       ->  if self._restart_timer is not None:
               self._restart_timer.cancel()
           self._restart_timer = timer

5. `app/webview/sotto_webview.py:5878` (row #38) — carry the tag (or refuse a non-final payload):

       for key in ('peak', 'blocks'):
       ->  for key in ('peak', 'blocks', 'tag'):

6. `app/webview/sotto_webview.py:7334-7335` (row #42) — a stop that says so:

       self.log(f'BRIDGE_STOP reason={reason} pid=none')
       return False
       ->  self._status(..., 'busy', ...) before returning      # symmetric with start()

7. `app/webview/sotto_webview.py:7788` (row #43) — take the lock on the restart path too:

       self.state = 'restarting'
       self._spawn()
       ->  with self._lock:
               if self.stopped or self.child is not None:
                   return
               self.state = 'restarting'
               self._spawn()

8. `app/webview/sotto_webview.py:3552` (row #33) — delete the stale sentence (the cure it points at
   was removed; `:1010`, `:4031` and `:4853` already say so).

9. `worker/wasapi_loopback.py` (row #9B) — the ONE live defect of this sweep: a packet with
   `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY` (0x1) is not examined. Proposed: count it next to
   `position_gap_packets` and (optionally) treat it as a stream restart, the way the position gap is
   already treated. **Decision belongs to the Lead** — the audio team's ledger may have a reason.

10. `_main/_probe/console-census.py:106` (row #5) — drop `| 0x00000008` (DETACHED_PROCESS) and
    keep `CREATE_NO_WINDOW` (0x08000000) alone; measured: rows 0 → 17 on the same channel.

11. `_main/device-silence-oracle.py:71`, `_main/panel-exit3-oracle.py:173`,
    `_main/panel-startup-visibility-oracle.py:386`, `_main/run-live-hidden.py:44` (rows #34/#35) —
    wrap each `wait(timeout=)`/`run(timeout=)` in `except subprocess.TimeoutExpired:` and kill the
    TREE (`taskkill /F /T /PID <child>`), then re-raise or record; delete the dead
    `DETACHED_PROCESS` constant at `_main/run-live-hidden.py:25`.

12. `_main/_oss_oracle.py:92` (NEW, §5) — make the control a measurement:

        print(('PASS ' if all(results) else 'FAIL ') + 'NEG control: ...')
        ->  print(('PASS ' if all(checks(REPO, lambda *a: None).values()) else 'FAIL ') + 'NEG control: ...')

13. `worker/README.md` + `AGENTS.md` (row #54) — state the measured census (5 top-level keys,
    17 leaves, 11 non-comment leaves) and stop calling the six named settings "the keys".

## 7. NOT MEASURED (with the exact reason)

- **#4 / the T2 startup flash.** Needs N ≥ 20 launches of the shell with the 25 ms census
  (`_main/panel-startup-flash-census.py`). **Forbidden by the owner's order.** The number that would
  settle #46 lives behind the same launch.
- **#46's "which number is true"** (0/41 vs 18/20 vs 141/262). Same reason. Only the doc fact is
  measured.
- **#47 — fp16 1230 MiB vs 1246.9 MiB.** Not re-measurable: only ONE export exists on disk,
  `worker/models/nemotron-3.5-asr-streaming-0.6b-int8` (1 070 642 977 B / 33 files). No fp16 weights,
  and RSS needs a model load (a launch).
- **#40 — separator-sensitive state-name sets** (`sotto_webview.py:112-126` vs the JS arm's
  normalization). NOT MEASURED: it needs the panel's own classifier executed under jsdom and compared
  to the Python sets; no instrument was built in this sweep. Named here so the gap is explicit.
- **#38's other half — does a `tag=tick` line ever reach the shell?** A sibling lane owns the meter
  chain and has recorded that the worker emits no `{"type":"meter"}` line today
  (`_main/receipt-20261011-meter-chain-gap.md`). This sweep measured only the SHELL's loss of the tag.
- **#58's receipt and the `run.cmd` leg.** Needs `cmd /c run.cmd --bogus-flag`; `run.cmd` is named
  in the standing order. The refusal was measured in-process instead (SystemExit(2)).
- **#62's electron instantiation.** `electron.exe`/shell launch forbidden; `AGENTS.md` §2 declares
  that binary DEAD. The mechanism (a tree surviving a `subprocess.run` timeout) IS measured.
- **Anything about what the real WebView2 PAINTS.** No shell was launched, so every DOM/paint claim in
  this receipt is about the Python/JS objects, never about pixels.
- **Row #5's own file, `_main/_probe/console-census.py`.** Not executed (it spawns children); the
  flag mechanism was reproduced on the same channel with harmless children.

**Sanity check performed at the end of the sweep** (real command, real output):

    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File I:\cc-tmp\lane-sweep-census.ps1
    ->  no process (other than this census) names an audit-rows- file
    ->  python/pythonw processes on this box right now: 15

(the 15 belong to other lanes; a FIRST version of this census matched its own script name — the
self-match was excluded by pid, and the raw output above is from the corrected run). And
`git status --porcelain` for this lane's six files shows **six `??` entries and zero ` M `**:

    ?? _main/audit-rows-bridge-decisions.py            ?? _main/audit-rows-negative-arm-falsifiability.py
    ?? _main/audit-rows-byte-claims.py                 ?? _main/audit-rows-tap-flags-ledger.py
    ?? _main/audit-rows-landmine-child-control.py      ?? _main/receipt-20261011-audit-rows-sweep.md

61 other `_main/` files show ` M ` repo-wide — **none of them is this lane's** (they belong to the
other lanes editing `_main/_audit-verify/`, `_main/_redux-gate-mutants/` etc.).

**This receipt's own bytes/sha256/mtime** are reported in the lane's final message: a file cannot
contain the hash of the bytes that would contain it.

## 8. What this receipt does NOT claim

- It does not claim any row is *APPLIED*: the register is the Lead's to edit, and the register moved
  twice while this sweep ran (36 541 B → 41 612 B).
- It does not claim a fix: §6 lists diffs **not written**.
- It does not claim the two rewritten oracles are sound beyond the arms driven here: `#56`'s arm was
  driven and blinded; `#57`'s arm was driven and its control line was PROVEN to be a label.
- It does not claim "no window appeared" anywhere: no window-producing code was run at all.


---

## ADDENDUM 2 — 2026-10-11 (Lead): the ONE live defect of this sweep is FIXED

**#9B is closed in PRODUCT code, not only measured.** `worker/wasapi_loopback.py` now declares
`AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY = 0x00000001` beside `..._SILENT`, carries a
`discontinuity_packets` counter and increments it in the packet loop; the SECOND loop that copies
that pump (`worker/sotto_worker.py`, the process-loopback tap) got the same three things, and the
`TAP_STALLED` ledger line now ends with `disco_packets=`. The packet's samples are still USED --
a one-off discontinuity is exactly what a glitch sounds like, and silencing it would delete audio
the owner asked for -- so this changes the LEDGER, not the audio.

Both colours, on THIS instrument, whose harness had to be repaired for it first:

- The harness built the tap with `__new__` (no `__init__`) and seeded only the two counters it
  knew, so the new increment was an `AttributeError` INSIDE the pump thread -- which killed the
  thread and turned ALL FOUR arms into crashed-pump readings, not measurements. It now seeds
  `tap.discontinuity_packets`, reports it in the counters dict, and `arm_r9b`'s `same_counters`
  includes it: without that, the comparison could not see the very fix it exists to measure.
- The m9b mutant is INVERTED: it used to SIMULATE the fix; it now REMOVES the counter and
  reproduces the pre-2026-10-11 state. `EXPECT['r9b']` flipped from
  `{'live': True, 'mutant': False}` to `{'live': False, 'mutant': True}`.
- Measured, three consecutive runs, identical: `VERDICT: PASS  live: 0 of 4 defect claims present
  -- every one refuted on the live bytes; 4/4 mutants flipped exactly their own arm`, rc=0.
  The closing sentence is now COMPUTED from the readings: the old one asserted "1 of 4 ... (the
  discontinuity bit)" as a fixed string and went stale the moment the bit began to be examined.
  `--neg-arm` skips the live block, so its verdict now says "live NOT probed in this mode ...
  no live set is claimed" instead of printing a set it never measured.

**Row #9 is therefore APPLIED and `F2` (inherited from it) with it:** all three of its claims are
false on the live bytes -- SILENT IS examined, the loss HAS a counter, and DATA_DISCONTINUITY is
examined now, with a mutant proving the counter is load-bearing.

**NOT MEASURED, unchanged:** nothing was launched; the counter was driven by a SCRIPTED vtable, so
no real device has yet set the bit on this box. The fix is measured against the instrument's
scripted discontinuity, not against a live glitch.


---

## ADDENDUM 3 — 2026-10-11 (Lead): the two instruments that pinned the two fixes were re-baselined

Fixing rows #33 and #5 made THIS sweep's own instruments exit 2 (dead anchor) and then exit 1
(labels holding the pre-fix live values). Both were re-baselined the same way the tap instrument
was: the live expectation follows the fix, and the MUTANT is INVERTED so it reproduces the defect
instead of simulating the cure. A gate that needs the defect present to build its own control is a
gate that pins the defect.

- `_main/audit-rows-byte-claims.py` -- row #33. The setup required the stale sentence to exist
  (to delete it in a copy); the live shell no longer has it, so the mutant now RESTORES it, anchored
  on the corrected comment line. `EXPECT_LIVE['r33'] True -> False`, the restore mutant expects
  the defect, and the three blocks that do not mutate the shell now carry the LIVE value for r33.
  `VERDICT: PASS  live: 2 of 4 rows still defective on the live bytes (r54, r46); 4/4 mutants
  flipped the reading they are aimed at`, rc=0.
- `_main/audit-rows-landmine-child-control.py` -- row #5. `m5-census-flags-fixed` becomes
  `m5-census-broken-flags` and puts `| 0x00000008` BACK; `LIVE_DEFECT` is now one named table
  (r5 False, r34/r35/r62 True) used by BOTH the live block and the else-branch of every mutant
  block, which is what the old hard-coded `True` in that else-branch got wrong the moment one arm
  flipped. `VERDICT: PASS  live: 3 of 4 landmines still reproduced on this box (r34, r35, r62); the
  rest are FIXED; 4/4 mutants flipped their own arm(s)`, rc=0.

**Both closing sentences are now COMPUTED from the readings**, not asserted as fixed strings: the
landmine one said "4/4 landmines reproduced ... the census channel is 0 B with rc 0" -- true when it
was written, FALSE the moment the census was fixed -- and the byte-claims one said "three rows read
on the live bytes". Each now names the arms that are still defective, and each says "live NOT
probed in this mode" when `--neg-arm` skips the live block instead of printing a set it never
measured. **This is the third and fourth instance of the same defect class in one session** (a
verdict sentence that cannot change when the facts do); it is worth treating as the house rule:
a PASS line must be derived from the run it closes.


---

## ADDENDUM 4 — 2026-10-11 (Lead): rows #34 and #35 are FIXED in the files, not just measured

This sweep filed them against OUR OWN instruments and launchers, and the sweep was right: the
landmine instrument's live arms reproduced a real orphan ("the orphan survives the timeout").
Fixed, all four sites, with the handler the instrument's own mutants had prescribed:

- `_main/device-silence-oracle.py`, `_main/panel-exit3-oracle.py`,
  `_main/panel-startup-visibility-oracle.py` (row #34): `try/except subprocess.TimeoutExpired` ->
  `taskkill /F /T /PID <pid>` -> re-raise. `/T` kills the tree; the target is a PID, never a NAME,
  so no kill filter can reach an unrelated process.
- `_main/run-live-hidden.py` (row #35): the same handler on its `wait(timeout=300)`, and the dead
  `DETACHED_PROCESS = 0x00000008` is REMOVED — nothing read it, and a detached child is exactly
  the orphan no ceiling can reach.

**Measured after the fix:** `py -3 _main/audit-rows-landmine-child-control.py` ->
`VERDICT: PASS  live: 1 of 4 landmines still reproduced on this box (r62); the rest are FIXED; 4/4
mutants flipped their own arm(s)`, rc=0. `py_compile` rc=0 on all four files.

**Three things this closure had to repair in the measuring instrument itself, all recorded rather
than hidden:**

1. `arm_r34` derived the defect with `all(...)` over the three files. That quantifier stops being
   able to say NO the moment ONE file is fixed, and it is the wrong claim anyway: ONE unhandled site
   can orphan a child. `any_wait_site_unhandled` now carries the claim (`all` is kept and printed).
2. The `m34`/`m35` mutants were INVERTED (they used to ADD the handler, i.e. simulate the cure);
   they now REMOVE it and restore the dead constant, so both colours still exist.
3. `arm_r35`'s detector was `text.count('DETACHED_PROCESS') == 1` — a count of MENTIONS. The
   comment that documents the removal makes that count 1, so the arm would have read the
   documentation as if it were the constant. It now requires a DEFINITION
   (`^[ \t]*DETACHED_PROCESS[ \t]*=`). A detector defeated by its own explanatory comment is the
   same defect class as a PASS line that cannot go stale.

**What is left live in that instrument is r62 alone**, and it is blocked by the owner's order rather
than by work: measuring it means launching electron.exe or the shell, the binary is declared DEAD,
and the row's own text calls the claim an INFERENCE. Registered as BLOCKED-BY-OWNER-ORDER.


---

## ADDENDUM 5 — 2026-10-11 (Lead): items 1-7 of section 6 are PAID, seven rows closed

The seven product diffs this sweep proposed were applied in `app/webview/sotto_webview.py`, each
verified by `_main/audit-rows-bridge-decisions.py`, whose live block now reads
`0 of 8 defects present on the live shell -- every one refuted by the bytes; 8/8 mutants flipped
exactly their own arm`, rc=0. Rows #11, #12, #13, #15, #38, #41, #42, #43 are APPLIED; the map went
from applied 65 / open 74 to **73 / 66**, gate GREEN.

**Three of the sweep's own proposals needed correcting before they could be applied, and each
correction is a measurement, not a preference:**

1. **Item 3 (row #13): `return self._spawn() is not None` would ALWAYS be False.** `_spawn()`
   falls out with `None` on every path — it never returned the child. Applied instead:
   `_spawn()` returns `self.child` on the success path (its two failure paths still return
   `None`), and `start()` reads that. A fix written as proposed would have turned every start into
   a reported failure.
2. **Item 5 (row #38): the tag the row is about is the WORKER'S OWN.** The payload already had the
   worker's `tag=tick|final` available in `fields` and dropped it; naming the source
   (`'stats'`) would not have told a tick from a total. Applied: the payload carries
   `fields['tag']`, with `'stats'` as the fallback for a line that declares none, and `'meter'`
   on the meter branch — and arm r38 now measures BOTH branches.
3. **Item 1 (row #11): the fix narrows the falsifier, it does not delete it.** The guard is
   `and self.captions == 0`, so the ARM had to grow a second case (the same real error AFTER a
   caption) or it could not tell the fix from the old behaviour. `DEFECT_KEY['r11']` moved to
   `rewrites_after_caption`; the first case is still measured and printed, because firing while no
   caption has ever arrived is correct.

**The measuring instrument was re-baselined, not loosened:** all seven mutants were INVERTED (they
used to simulate the cure; they now remove it), `EXPECT` flipped to `{'live': False, 'mutant': True}`
for the seven, and the closing PASS line is now COMPUTED from the live readings — the fixed string
said "7 defects present, 1 refuted" and would have gone stale the moment the rows were paid. That is
the fifth instance of this defect class in this session; `--neg-arm` says "live NOT probed in this
mode" instead of printing a set it never measured.

**NOT MEASURED, unchanged:** nothing was launched. The arms drive the shell IN PROCESS (they import
it from a file), so these closes are behavioural but not painted: no WebView2 window has shown any of
them, and the owner's stop order is why.


---

## ADDENDUM 6 — 2026-10-11 (Lead): row #40 closed -- the shell now speaks the JS twin's rule

The row's gap was named here as "NOT MEASURED: it needs the panel's own classifier executed under
jsdom and compared to the Python sets; no instrument was built in this sweep". The instrument turned
out to need no jsdom at all, because the question is narrower than that:

- **What the JS twin actually does is measured from its bytes, not assumed:**
  `app/_legacy-electron/worker-bridge.js:691` reads `String(message.type || '').toLowerCase()`
  and branches on that; and there is **no separator replacement anywhere in the file**
  (`replace(/[-_]` is absent). So the JS rule is CASE, and only case. The row's "separator-sensitive"
  wording describes the same defect class, but the twin does not normalise separators — inventing
  that rule on the Python side would have created a second vocabulary.
- **What the shell did:** `kind = message.get('type')` compared RAW, so the SAME line was a
  caption to the JS arm and a `malformed` drop here. Now:
  `kind = str(message.get('type') or '').lower()`.
- **Measured, both colours:** `_main/audit-rows-bridge-decisions.py` gained **arm r40** (it feeds
  `{"type": "Caption"}` and `{"type": "STATUS"}` and REQUIRES the caption to land, while checking
  that the twin still carries its `toLowerCase()` and still has no separator rule). The instrument
  now has NINE arms:
  `VERDICT: PASS  live: 0 of 9 defects present on the live shell -- every one refuted by the bytes;
  9/9 mutants flipped exactly their own arm`, rc=0, and `--neg-arm` says live was not probed.
  The mutant `m40-case-normalisation-removed` compares raw again and flips its own arm.
- The closing PASS line COMPUTED "0 of 9" the first time it ran with nine arms — which is the whole
  point of making it computed one round earlier: the stale sentence it replaced said "8/8".

Map: applied 73 -> 74, open 66 -> 65, gate GREEN. **NOT MEASURED: nothing was launched**; the arm
imports the shell in process, so this is the parser's behaviour, not a painted panel.
