# The panel's status is a REPAIR CONTROL — receipt

Owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei que, ao
clicar, deve fazer a pipeline inteira ser revivida, se nao tiver funcionando"*.

One click on the panel's status — the footer (`#status`) or the strip's own state
(`#strip-state`) — kills the worker, drops every latch that could outlive it, and
spawns a fresh one. It is **unconditional**: no health test stands between the
owner and the repair, because a button that answers "you do not need this" is a
button that argues with the man looking at the screen. The price is one model load
and it is stated in the element's own `title` BEFORE he clicks.

## Files changed

| file | what | lines |
|---|---|---|
| `app/webview/sotto_webview.py` | the injected bridge gains `revive(reason)` | `2298-2307` |
| | `BRIDGE_PROBE.methods` gains `'revive'` (17 → **18**, seen live) | `2481` |
| | the ONE page→host router gains the `'revive'` kind | `2889` |
| | `SottoHost._revive` — carries the request, decides nothing | `2909-2916` |
| | `_revive_lock` / `_revive_thread` (the in-flight guard) | `3066-3067` |
| | `--probe-revive SECONDS` (a measurement flag, suppressed from `--help`) | `7709` |
| | …its suppression (`measurement-flag(--probe-revive)`) and its arming | `5801`, `3806-3815` |
| | `run_revive_probe` — presses the REAL `#status` in the REAL page | `6115-6152` |
| | `START_REASONS` gains `'revive'` (without it the click is a silent decline) | `5815` |
| | `SottoShell.revive_worker` — the guard, the immediate paint, the thread | `5994-6037` |
| | `SottoShell._do_revive` — reload-policy stop, latch clear, kill, respawn | `6039-6092` |
| `app/panel/panel.js` | `REVIVE_HINT` / `REVIVE_TITLE` / `reviveInFlight` (above the init block) | `222-227` |
| | `wireRevive();` in the init block | `470` |
| | the strip's hover sentence keeps the hint (it rewrites its own title) | `1663` |
| | `paintReviveSentence` / `reviveSupported` / `revivePipeline` / `wireRevive` | `1773-1870` |
| | **`let transcriptExpanded` MOVED above the init block** (a real TDZ fix, below) | `213` |
| `_main/revive-pipeline-oracle.py` | the oracle, all arms + both controls | new |
| `_main/revive-panel-render-test/{main.js,driver.js,preload.js}` | the Chromium arm over the REAL `panel.html` | new |

Measured revisions: shell `26DDD3BB7A3F1682` (411 140 B), panel.js `860F3D08677E0DF1`
(117 517 B). Transcripts: `_main/_revive-oracle-transcript.txt`,
`_main/_revive-oracle-negarm.txt`.

## Re-run, both colours

```
py -3 _main/revive-pipeline-oracle.py            # four arms   -> VERDICT: PASS, rc 0
py -3 _main/revive-pipeline-oracle.py --neg-arm  # two controls -> VERDICT: PASS, rc 0
py -3 _main/revive-pipeline-oracle.py --panel-only   # the Chromium arm alone
py -3 _main/revive-pipeline-oracle.py --live-only    # the real page + a real worker
```

## ARM P / P2 — the real document, in Chromium

The page is `app/panel/panel.html` itself, rebuilt into the instrument's directory
with its relative assets pointed back at `app/panel/`, and the REAL `panel.js`
loaded — so the listener under test is the shipped one. The fake bridge lives in
`preload.js` and runs before any page script.

`ARM P: GREEN` — the footer AND the strip report `role=button`, `tabindex=0`,
`cursor:pointer`, the title states the cost; the shell's own
`{text, kind:'error'}` payload is pushed in first (the sticky death is on screen:
`status--error`, `"Worker stopped (exit 3) - silent-device"`), then ONE click:

```
one_click_calls_revive_once      true    calls[0] === 'panel-status'
the_repair_is_announced          true    "Restarting the pipeline…"
the_announcement_is_on_screen    true    not clipped AND non-empty
the_repair_is_not_painted_as_an_error true  no status--error, no status--live
the_death_is_gone_from_the_footer true   not /exit 3/
the_strip_says_it_too            true    #strip-word === 'Restarting'
a_second_click_does_not_stack    true    still exactly 1 call
the_second_click_says_already    true
enter_on_the_strip_revives       true    (phase 2, a fresh document)
```

`ARM P2: GREEN` — with `bridge.revive` absent, nothing is called and the footer
says, word for word: **"This shell cannot restart the pipeline (no
bridge.revive())"** — the honesty rule `wirePause` already follows. Zero page
errors in both arms.

## ARM S — the shell's own revive, in process

The real `revive_worker`/`_do_revive` against fake collaborators, with the old
bridge's `stop` held for 0.5 s so a double click lands in the window:
`REVIVE_REQUESTED reason="panel-status" had_bridge=true pid=4242`; the old child
stopped with `reason=revive`; `REVIVE_CLEARED pending_error=…` and the `no_audio`
verdict dropped; `start_worker` called with **exactly** `['revive']`; the
hot-reload policy stopped FIRST; the second call returned `False` and logged
`REVIVE_REFUSED reason=already-in-flight` without spawning; `REVIVE_DONE
started=true pid=5150 spawns=1`; the in-flight flag released.

## ARM L — the LIVE shell, a real worker, the real page pressing the real element

```
sotto: REVIVE_PROBE_ARMED s=22.0
sotto: REVIVE_REQUESTED reason="panel-status" had_bridge=true pid=2860
sotto: REVIVE_PROBE {"hasRevive":true,"offscreen":false,"ok":true,"pressed":"status",
       "statusError":false,"text":"Restarting the pipeline\u2026",
       "title":"Restart the pipeline \u2014 reloads the live engine",
       "wired":{"footer":"button|0|pointer","strip":"button|0|pointer"}}
sotto: WORKER_AUTOSTART=started reason=revive
sotto: REVIVE_DONE started=true pid=22476 spawns=1
```

**The pid changed: 2860 → 22476**, the respawn used `reason=revive`, and the
`reason="panel-status"` on the request is what proves the revive came from the
PANEL's click and not from Python. Later runs: 41996 → 9736, 44856 → 11800,
16016 → 37772, each with the same shape and each `ARM L: GREEN`.

**No caption flowed after the revive, and that is measured, not omitted:** nothing
was playing (`captions_after_the_revive: 0`). The brief names the fallback for
exactly this case and it is what the arm asserts — the fresh
`WORKER_AUTOSTART=started reason=revive` plus the new child's own statuses
(`statuses=3` on its exit, and the page's receipts
`STATUS_APPLIED text="boot"` / `PLACEHOLDER_APPLIED title="Ready — speak and the
line flows"`).

## The two real defects this lane found

1. **A panel-killing TDZ in `panel.js`, shipped, and latent by luck.**
   `wireHistory()` (init) → `loadHistory` → `renderFeed` → `applyTranscriptMode` →
   `isTranscriptExpanded`, which READS `transcriptExpanded` — declared 370 lines
   BELOW, at `:824`. With the real shell the tail arrives asynchronously, so the
   read lands after the module has finished evaluating and the panel works; the
   moment that path is SYNCHRONOUS (a shell with no `bridge.history` — the panel's
   own "no transcript writer yet" case) the init block dies with `Cannot access
   'transcriptExpanded' before initialization` and NOTHING after it runs: no
   `wireStatus`, no caption subscription, a panel frozen on its placeholder. My
   instrument reproduced it on its FIRST run on the real document; the fake bridge
   lacked `history` and that was enough. Fixed by moving the declaration above the
   init block (AGENTS.md: "anything the init block can touch is declared above
   it"), which is also why the arms now run with **zero** page errors.
2. **A blank footer, mine.** `setStatus(text, 'busy')` does not merely HIDE the
   sentence — it writes an EMPTY STRING (`textContent = paintsText ? text : ''`),
   because only an error paints its words. A `paintReviveSentence` that only
   removed the clip class therefore painted NOTHING: the owner would have clicked
   the dead status and watched the footer go blank. ARM P caught it (`the_repair_
   is_announced=false` while the weaker "not clipped" check passed), the sentence
   is now written explicitly, and that weak check was strengthened to demand
   non-empty text so it can never pass over a blank footer again.

## Controls — `--neg-arm`, one line each, built from TODAY

```
CONTROL-1 panel minus `wireRevive();` -> RED on 3 check(s)
  the_footer_is_wired=False  the_strip_is_wired=False  one_click_calls_revive_once=False
CONTROL-2 shell minus its dispatch entry -> probe_clicked=True unknown_kind=True revived=False
both controls RED as expected
VERDICT: PASS
```

CONTROL-2 is the discriminating one: the probe still pressed the element
(`probe_clicked=True`, so the control is not measuring a dead page), the shell
refused the kind (`BRIDGE_UNKNOWN_KIND kind='revive'`) and did NOT revive.

## Disclosed

- **The live arm runs its OWN hidden shell, not the owner's running instance.**
  Killing the worker of the app he is using would interrupt his live captions for
  the length of a model load, so the owner's app was STOPPED for the measurement
  (freeing the WASAPI endpoint, which two workers cannot share) and RESTARTED
  afterwards — shell **28756**, worker **50368**, `PRELOAD_ACTIVE methods=18`,
  panel hidden, 0 `PAGE_ERROR`. `--no-hotkey` keeps a measurement run from
  answering his Alt+C.
- **`--probe-revive` is a real measurement flag** (suppressed from `--help`,
  suppressed in `_worker_autostart_reason` so it never pays a model load by
  accident). It is the only product surface added, and it exists because there is
  no other way to press the page's own element from outside: this shell has no
  eval-from-outside channel.
- **One run returned `REVIVE_PROBE null` with no cause and has NOT been
  attributed.** `exec_js` reports only the call, so a throw inside the page's own
  click listener vanished. The probe now wraps itself in `try/catch` and returns
  `{ok:false, threw, stack}`, so a recurrence names its own cause instead of
  looking like a timer that never fired. Four subsequent runs are green; the
  panel.js under test was being rewritten by ANOTHER LANE during that window
  (three hash changes observed in my run), which is the likely but unproven
  cause.
- **Another lane edited `panel.js` while this lane worked** (112 843 → 117 517 B
  in three steps). My code survived every time and all arms are green on the
  revision above, but the ownership boundary was crossed by someone else.
