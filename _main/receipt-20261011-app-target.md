# Receipt — STEP 5: the worker's PER-APP tap is now REACHABLE FROM THE APP (opt-in, ONE target)

**Date:** 2026-10-11 (America/Sao_Paulo) · **Lane:** subagent of `session-b4dd3d3d-3632-4b10-b337-5fbe44d33595`
**Owner's requirement this serves, verbatim:** *"audios de diferentes apps tem que ser separados e processados separadamente"*
**Owner's stop order in force, verbatim:** *"para de abrir o sotto, ta travando meu pc quando ele abre."* —
**nothing in this lane launched the app, the shell, the worker, `run.cmd` or `_main\_audit-verify-all.cmd`.**
Every instrument below is in-process (a python module imported, a kernel snapshot read with ctypes). No window was
created and no visible console was left: every python call went through Node `spawnSync` with `windowsHide: true`
(`CREATE_NO_WINDOW`).

---

## 1. What was wrong

The worker has been able to tap **ONE** process tree since 2026-10-11 —
`worker/sotto_worker.py:3894` (`--target-pid`, `type=str`) / `:4321` (`SOTTO_TARGET_PID` fallback), the
`p` rung at `:1044-1046`, `ProcessLoopbackTap` with `INCLUDE_TARGET_PROCESS_TREE`, and `source` = `proc:<pid>`
on every caption — but the **app could not ask for it**:

```
$ grep -n target_pid app/webview/sotto_webview.py     # BEFORE this lane
(no output — ZERO matches)
```

A capability that exists in the worker and is unreachable from the app is the same defect class as a factored rule
nothing calls. This lane adds the reachable path, opt-in, and — the part that matters — makes an **unresolvable**
target REFUSE instead of silently falling back to the endpoint mix (which would transcribe EVERY app while the
owner believes he is reading one).

## 2. The three artefacts

| file | before | after |
|---|---|---|
| `app/webview/sotto_webview.py` | **429 463 B**, sha256 `0660B991D81729E673BB1BC599E3D57E60EF382A4BE9FBAAB679E9C19C4C5E21`, 2026-10-11T21:20:13.183Z | **439 498 B**, sha256 `E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F`, 2026-10-11T21:37:29.904Z, 8 663 CRLF / 0 bare LF |
| `_main/app-target-oracle.py` | absent | **26 957 B**, sha256 `F7B3E9C65965235DBCF25D9C67A8439ADB2C59B3B8E25995B1A924F5A1B1D125`, 620 lines, LF (4 of 5 sibling `_main` oracles are LF too) |
| `_main/receipt-20261011-app-target.md` | absent | this file — its own size/sha256 are reported in the lane's final message (a file cannot contain its own hash) |

The shell delta is **+10 035 B**, all of it the six sites below. The shell was **already** ` M` in git when this lane
started (other lanes); the pin above is what this lane measured before its first write, so the delta is attributable.

```
$ git status --porcelain -- app/webview/sotto_webview.py _main/app-target-oracle.py worker/sotto_worker.py app/panel app/webview/run.cmd
 M app/panel/caption-formulation.js      <- NOT this lane
 M app/panel/panel.js                    <- NOT this lane
 M app/webview/sotto_webview.py          <- this lane (on top of pre-existing lane edits)
?? _main/app-target-oracle.py            <- this lane
$ git diff --stat -- worker/sotto_worker.py app/panel app/webview/run.cmd
 app/panel/caption-formulation.js |  38 ++++-
 app/panel/panel.js               | 293 +++++++++++++++++++++++++++++----------
```

**`worker/sotto_worker.py` shows NO diff: this lane did not touch the worker.** Neither `run.cmd` nor
`_main\_audit-verify-all.cmd` nor `app/panel/` was written to (the panel entries above are other lanes', pre-existing).

## 3. The six sites, before → after

Each "before" block below is the **literal the edit matched**, and the tool refuses a literal that is absent or
appears more than once — so every pair is exact by construction, not by memory.

### Site 1 — `WorkerBridge.__init__`: the parameter and its store

```python
# BEFORE
    def __init__(self, command, worker_path, device=None,
                 capture_mode=DEFAULT_CAPTURE_MODE, log=log,
                 on_caption=None, on_status=None, on_stats=None,
                 on_meter=None,
                 silence_ms=WORKER_SILENCE_MS,
                 backoff_base=1000, backoff_max=30000):
        ...
        self.capture_mode = capture_mode

# AFTER
    def __init__(self, command, worker_path, device=None,
                 capture_mode=DEFAULT_CAPTURE_MODE, log=log,
                 on_caption=None, on_status=None, on_stats=None,
                 on_meter=None,
                 silence_ms=WORKER_SILENCE_MS,
                 backoff_base=1000, backoff_max=30000,
                 target_pid=None):
        ...
        self.capture_mode = capture_mode
        #: THE PER-APP TAP, opt-in: the pid of the ONE app whose process tree the
        #: worker must tap, or None for the endpoint mix (the behaviour every run
        #: had before this parameter existed). It travels to the child in the
        #: ENVIRONMENT -- `_child_env` is the whole contract, and it is where
        #: the "absent means byte-identical env" promise is kept. The worker owns
        #: the refusal for a pid that is not alive (sotto_worker.py,
        #: `_plp_pid_state`); this shell only resolves NAMES (see
        #: `resolve_app_target`).
        self.target_pid = target_pid
```

Appending a keyword parameter is safe for every existing caller: **every sibling oracle that builds a
`WorkerBridge` passes keyword arguments only** — five files, seven sites (`benign-status-arm-oracle.py:41`,
`no-audio-latch-oracle.py:100`, `panel-exit3-oracle.py:279/388/570`, `restart-30s-oracle.py:147`,
`tap-restart-loop-oracle.py:139`) — and two of those gates (`panel-exit3-oracle.py --unit`,
`no-audio-latch-oracle.py`'s sibling `revive-pipeline-oracle.py --shell-only`) were re-run GREEN against this
revision (§4.5), which is the empirical half of the same claim.

### Site 2 — the child env is FACTORED into `_child_env()` (new method, before `_spawn`)

```python
    def _child_env(self):
        """The child's WHOLE environment contract, in one place.

        Factored out of `_spawn` so it is assertable WITHOUT spawning
        anything (`_main/app-target-oracle.py` builds bridges in-process and
        compares the dicts -- the same reason `_worker_autostart_reason` was
        factored out of `_on_loaded`). The device and the capture mode already
        travelled this way; the per-app target joins them HERE, and ONLY when it
        was asked for: a bridge built without `target_pid` produces the
        byte-identical environment it produced before the parameter existed.
        """
        env = dict(os.environ)
        env['SOTTO_CAPTURE_MODE'] = self.capture_mode
        if self.device is not None:
            env['SOTTO_AUDIO_DEVICE'] = self.device
        #: OPT-IN: `SOTTO_TARGET_PID` appears ONLY when a target was resolved.
        #: The worker reads it as the per-app tap (sotto_worker.py,
        #: `--target-pid` / `SOTTO_TARGET_PID`); absent, its candidate ladder
        #: is the endpoint mix, unchanged.
        if self.target_pid is not None:
            env['SOTTO_TARGET_PID'] = str(self.target_pid)
        return env
```

### Site 3 — `_spawn` uses it, and NOTHING else in `_spawn` changed

```python
# BEFORE (the whole env contract, inline)
        env = dict(os.environ)
        env['SOTTO_CAPTURE_MODE'] = self.capture_mode
        if self.device is not None:
            env['SOTTO_AUDIO_DEVICE'] = self.device

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) \

# AFTER
        # The WHOLE env contract lives in `_child_env`, so it can be asserted
        # without spawning anything (see its docstring). Nothing else in this
        # method was touched when the per-app target was added.
        env = self._child_env()

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) \
```

The pid travels in the **environment**, never in argv — `_spawn` still builds `[self.command, self.worker_path]`
with no extra argument, which is the same channel `SOTTO_CAPTURE_MODE` and `SOTTO_AUDIO_DEVICE` already use, and
the same channel the worker reads at `sotto_worker.py:4321`.

### Site 4 — the resolver and the precedence helper (new module section, before the CLI banner)

```python
def resolve_app_target(value):
    """`--app-target` -> the pid to tap, plus every pid the rule considered.
    ...
      * `value` is all digits and > 0 -> `(that pid, [that pid])`. The pid
        is ACCEPTED as given: whether it is still alive is the WORKER's refusal
        to make (sotto_worker.py, `_plp_pid_state` -> `state="error"
        stage="target-pid"`), not this shell's ...
      * anything else is an IMAGE NAME, matched case-insensitively against
        `szExeFile` over the LIVE process table.
      * TREE-ROOT RULE: of the matches, only those whose PARENT is not itself a
        match survive. That is what makes `--app-target chrome.exe` mean the
        BROWSER process: the tap is opened with INCLUDE_TARGET_PROCESS_TREE, so
        the renderers' audio arrives with it, while aiming at a renderer pid
        alone would tap one renderer's share and miss the rest. `candidates`
        is the sorted root list, and the LOWEST pid is chosen when several
        roots remain.
      * no match -> `(None, [])`. The caller must REFUSE loudly ...
    """
    raw = str(value if value is not None else '').strip()
    if raw == '':
        return None, []
    if raw.isdigit():
        pid = int(raw)
        if pid > 0:
            return pid, [pid]
        return None, []
    wanted = raw.casefold()
    matches = [(pid, parent) for pid, parent, exe in _process_table()
               if str(exe).casefold() == wanted]
    if not matches:
        return None, []
    matched_pids = {pid for pid, _parent in matches}
    roots = sorted(pid for pid, parent in matches if parent not in matched_pids)
    if not roots:
        roots = sorted(matched_pids)
    return roots[0], roots


def app_target_request(args, env=None):
    """The requested per-app tap and WHERE it came from: flag > env > none. ..."""
    raw = getattr(args, 'app_target', None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), 'flag'
    env = os.environ if env is None else env
    raw = str(env.get('SOTTO_APP_TARGET') or '').strip()
    if raw:
        return raw, 'env'
    return None, None
```

The table is read with the ctypes walk this module **already had** for the memory report — `_process_table()`
(`CreateToolhelp32Snapshot` / `Process32FirstW` / `Process32NextW`, `PROCESSENTRY32W` with `c_size_t` for
`th32DefaultHeapID`), reused rather than re-implemented. **No WMI, no subprocess, no psutil, no new handle
lifetime.** The name-based branch is what makes the feature usable at all: pids change on every app restart.

### Site 5 — the CLI flag (right after `--capture`)

```python
    parser.add_argument('--app-target', default=None, metavar='PID|IMAGE',
                        help='tap ONE app instead of the endpoint mix: a pid or '
                             'an image name (e.g. chrome.exe). A NAME is resolved '
                             "to the app's TREE ROOT -- the per-app tap follows "
                             'the whole process tree, so a renderer pid alone is '
                             'the wrong thing to aim at. An unresolvable target '
                             'starts NO worker (the endpoint mix would transcribe '
                             'every app instead of the one you named). '
                             'SOTTO_APP_TARGET also sets it; the flag wins. '
                             'WITHOUT it the worker taps the endpoint mix, '
                             'exactly as today')
```

`--app-target` is **NOT** in the measurement-flag suppression set of `_worker_autostart_reason`: it names a
TARGET, not a measurement. `--dump-dom --app-target X` therefore still suppresses the worker by `--dump-dom`
(ARM h). `run.cmd` needs no change: it passes `%*` through untouched (`run.cmd:166`, `:172`) and its
`--check-args` pre-flight uses the shell's own parser (`:126`), which now accepts the flag.

### Site 6 — `start_worker`: resolve once, and REFUSE when the name matches nothing

```python
# BEFORE
        if self.bridge is not None:
            return False
        self.bridge = WorkerBridge(
            ...
            on_meter=self.on_worker_meter,
        )

# AFTER
        if self.bridge is not None:
            return False
        # ── THE PER-APP TAP, OPT-IN -- AND AN UNRESOLVED TARGET REFUSES ──────
        # ... (an unresolved name must NOT fall back to the endpoint mix: that
        # would transcribe EVERY app while the owner believes he is reading one)
        target_pid = None
        target_value, target_source = app_target_request(self.args)
        if target_value is not None:
            log(f'APP_TARGET value={json.dumps(target_value)} '
                f'source={target_source}')
            target_pid, candidates = resolve_app_target(target_value)
            if target_pid is None:
                log(f'APP_TARGET_UNRESOLVED value={json.dumps(target_value)} '
                    f'reason=no-process')
                self.apply_panel_state(
                    f'App target not found - {target_value}', 'error',
                    {'title': 'App target not found',
                     'body': f'No running process matches {target_value!r}, so '
                             'the per-app tap has nothing to aim at. No worker '
                             'was started: the endpoint mix would transcribe '
                             'every app instead of the one you named.'})
                log('WORKER_AUTOSTART=declined reason=app-target-unresolved '
                    'by=start_worker')
                return False
            log(f'APP_TARGET_RESOLVED value={json.dumps(target_value)} '
                f'chose={target_pid} candidates='
                + ','.join(str(pid) for pid in candidates))
        self.bridge = WorkerBridge(
            ...
            on_meter=self.on_worker_meter,
            target_pid=target_pid,
        )
```

The refusal reuses the two existing shapes instead of inventing a third: the `WORKER_AUTOSTART=declined reason=…`
line every other refusal logs, and the paint call the missing-worker case makes —
`self.apply_panel_state(text, 'error', info)` (`sotto_webview.py:4141`, from `_worker_off_message` at `:4138`).
`target_pid=` is passed at the **ONE** `WorkerBridge` construction site; there is still exactly one bridge.

## 4. Instruments, with the real output

### 4.1 `py -3 -m py_compile app/webview/sotto_webview.py` → **rc = 0**, no stdout, no stderr

### 4.2 ACTUAL IMPORT of the shell module (not just a parse) + the two functions called

`py_compile` cannot catch a module-level `NameError` — that defect class already shipped once in the worker
(`import ctypes` local to `_pmc()`, so `import sotto_worker` died while `py_compile` passed). So the shell is
imported for real, in-process:

```
$ py -3 -c "...spec_from_file_location('sotto_shell_import_check', ...sotto_webview.py); exec_module(m)..."
IMPORT OK
has resolve_app_target: True
has app_target_request: True
digits: (4242, [4242])
zero: (None, [])
nope: (None, [])
own image: python.exe
own: (3632, [3632, 11992, 16840, 21736, 37748])
no target has key: False
target env: 4242
rc=0
```

Read the last four lines together: a bridge with **no** target does not have the key at all, and the same bridge
with `target_pid=4242` carries `SOTTO_TARGET_PID=4242`.

### 4.3 The new oracle — `py -3 _main/app-target-oracle.py` → **rc = 0**

```
app-target-oracle -- the per-app tap, reachable and opt-in
shell      : H:\sotto\app\webview\sotto_webview.py
bytes      : 439498
sha256     : E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F
launches   : NOTHING (no shell, no window, no worker, no device)

== LIVE shell -- every arm must be GREEN
  ARM a  [GREEN]  digits -> pid, junk -> None
  ARM b  [GREEN]  live image name -> TREE ROOT
      note: live same-image tree available: chrome.exe x33
  ARM c  [GREEN]  impossible name -> None
  ARM d  [GREEN]  target_pid reaches the child env
  ARM e  [GREEN]  no target -> no SOTTO_TARGET_PID
  ARM f  [GREEN]  flag > env > none
  ARM g  [GREEN]  unresolved REFUSES to start a worker
  ARM h  [GREEN]  not in the suppression set
  ARM i  [GREEN]  CLI contract

mutants    : G:\Temp\sotto-app-target-oracle-wqp7nf_8
  m1-env-line-removed: 1 literal replacement, 101 B -> 0 B, line endings preserved ('\r\n')
  m2-tree-root-removed: 1 literal replacement, 82 B -> 53 B, line endings preserved ('\r\n')
  sotto_webview_m1-env-line-removed.py  439397 B  sha256 FBB9B46FA2B206031C6D9D9B0410BD935D6BCDC6AB9DDB4F05E4FA897CE703B3
  sotto_webview_m2-tree-root-removed.py  439469 B  sha256 C35C8CA8953294600033B4B570CCB20C01DCF869C3E3EAE9907AE7A1C71553F7

== M1 env line removed -- exactly ONE arm must be RED
  ARM a GREEN | ARM b GREEN | ARM c GREEN | ARM d [RED ] | ARM e..i GREEN
      FAIL: SOTTO_TARGET_PID=None (wanted "4242")
      FAIL: the target travels WITH the device, both in the same env
      FAIL: a string pid is written as given

== M2 tree-root rule removed -- exactly ONE arm must be RED
  ARM b [RED ] (a, c..i GREEN)
      FAIL: python.exe: candidate 12076 is a tree ROOT (parent 16840 is 'python.exe')
      FAIL: python.exe: candidate 25108 is a tree ROOT (parent 11992 is 'python.exe')
      FAIL: chrome.exe: candidate 3928 is a tree ROOT (parent 8424 is 'chrome.exe')   [+33 more]
      FAIL: injected: chose the lowest ROOT 100, got 90
      FAIL: injected: candidates are the roots [100, 500], got [90, 100, 200, 500]

VERDICT: PASS  live=GREEN(9/9)  M1 env line removed=RED-as-expected(['d'])  M2 tree-root rule removed=RED-as-expected(['b'])
```

Both mutants are made from **today's shell**, byte-exact apart from one literal replacement
(439 498 − 439 397 = 101 B = the anchor with CRLF; 439 498 − 439 469 = 29 B), written to `%TEMP%`, never to
`_main/` — this lane's write scope is exactly three repo paths. The anchors are re-encoded to the file's OWN
line ending before they are counted, so a mutant cannot differ by line endings too.

### 4.4 `py -3 _main/app-target-oracle.py --neg-arm` → **rc = 0**

The mutant half alone, same two colours:

```
VERDICT: PASS  M1 env line removed=RED-as-expected(['d'])  M2 tree-root rule removed=RED-as-expected(['b'])
```

### 4.5 The existing gates still say what they said (all **rc = 0**)

| gate | command | last line |
|---|---|---|
| lock hardening | `py -3 _main/_lock-hardening-unit.py` | `UNIT-VERDICT: PASS (6/6)` |
| revive pipeline (shell half) | `py -3 _main/revive-pipeline-oracle.py --shell-only` | `VERDICT: PASS` (ARM S: GREEN; shell sha256 prefix `e5b4ade733bc3562` — the post-edit shell, so the gate ran against THIS revision) |
| panel exit-3 (in-process) | `py -3 _main/panel-exit3-oracle.py --unit` | JSON `"verdict": "PASS"`, `"failures": []` |
| worker-start wiring | `py -3 _main/_audit-worker-start-wiring.py` | `WIRING-VERDICT: GREEN` |

The wiring gate re-read the edited `start_worker` body by regex and still finds the guard **before** the
`WorkerBridge(` construction (it reports the match offset, not a line number) and the call site's argument to be
the rule's output — i.e. the new resolution block sits after the guard and did not disturb the pair that gate
exists to protect.

### 4.6 The chain to the worker, re-verified by grep (not by memory)

```
$ grep -n "SOTTO_TARGET_PID|target_pid" worker/sotto_worker.py
 952: def device_candidates(cfg_audio=None, wanted=None, target_pid=None):
1044: if target_pid:
1045:     offer(process_loopback_candidate(target_pid, _plp_proc_desc(target_pid)), "p",
1046:           "explicit target pid: one app's tree, not the endpoint mix")
3894: ap.add_argument("--target-pid", default=None, type=str, ...)
4321: _target_raw = args.target_pid if args.target_pid is not None else os.environ.get("SOTTO_TARGET_PID")
4333: _target_state = _plp_pid_state(target_pid)
4335:     emit(type="status", state="error", stage="target-pid", ...)
```

So the environment key this shell now writes is exactly the key the worker reads (`:4321`), and the worker — not
the shell — owns the liveness refusal (`:4333-4336`). The shell accepts a pid it cannot verify on purpose: it
never opens the process.

## 5. What this does NOT prove — NOT MEASURED

1. **No real per-app tap was opened.** Nothing in this lane ran the worker, so "the worker opens a process
   loopback for the pid this shell resolved and captions arrive tagged `proc:<pid>`" is **NOT MEASURED here** —
   that is the worker lane's instrument (`_main/per-app-source-plumbing-oracle.py`), and only a real launch
   under a lifted stop order can close it.
2. **No window, no panel, no DOM.** The refusal's paint is asserted as the CALL
   (`apply_panel_state(text, 'error', info)`, exactly the missing-worker path) and its `kind == 'error'`;
   **whether the panel's DOM received it is NOT MEASURED** — that needs the app, which the owner's order forbids.
3. **TWO apps at once is impossible by construction, and was not attempted.** There is ONE `SottoShell.bridge`
   and ONE worker; `--app-target` takes ONE value. "audios de diferentes apps separados" is satisfied one app at
   a time per run; two simultaneous taps would need a second bridge and are out of this STEP's scope.
4. **The TREE-ROOT choice was measured against the live table of THIS box at THIS instant** (chrome.exe x33,
   python.exe x5, plus the injected table). A different box, or the same box at another moment, may have other
   roots; the rule's own behaviour is pinned by the injected table, which is deterministic.
5. **`run.cmd --app-target X` was not executed** (it would launch the app). The passthrough is static
   (`run.cmd:166/172` pass `%*`; `:126` pre-flights with the shell's own parser, which ARM i proves accepts the
   flag).
6. **The pid-accepting branch was not tested against a live process the worker would actually tap** — ARM a
   proves the arithmetic and the shape, ARM g proves the pid reaches the bridge; the worker's open is unmeasured.
7. **The receipt's own sha256 is not in this file** (impossible); it is in the lane's final message.

## 6. Behaviour change when the flag is ABSENT: none, and it is asserted

ARM e builds a bridge exactly as every existing caller does and compares `_child_env()` to
`dict(os.environ) + SOTTO_CAPTURE_MODE` — **dict equality**, not a spot check — and asserts
`'SOTTO_TARGET_PID' not in env` (absent, not empty). With a device, the only difference is the
`SOTTO_AUDIO_DEVICE` key that was already there. ARM h proves `--app-target` is not in the suppression set.
So: no flag and no `SOTTO_APP_TARGET` → the same environment, the same candidate ladder, the same everything.
