# Receipt — the UI emit queue is bounded (2026-10-11)

## The risk this closes, in the words it was recorded with

`AGENTS.md` (the stop-order block) carried it as an OPEN risk the owner's order made unmeasurable:

> a correcção de `emit_async` (`_ui` → `_post`, commit `6908177`) tira o back-pressure do pump de
> legendas, mas passa a enfileirar um callable por push (~43/s) **sem limite** no thread da UI; com um
> worker a correr isso PODE saturar a fila do WinForms e travar a janela. NÃO VERIFICADO ... primeiro
> coalescer (um post pendente por canal), depois medir com UM lançamento autorizado.

The first half of that instruction is done here; the second half still needs the launch.

## The change

`emit_async` now keeps **one pending post per channel**:

* a push that arrives while another is still queued **replaces the queued payload** and returns
  without posting a second callable;
* the posted callable **pops at RUN time**, so N pushes collapse into the ONE script carrying the
  NEWEST payload;
* the licence is the method's own contract, already written down: every payload is a WHOLE state and
  the panel is a pure function of the last one it saw (both producers — `on_worker_stats` and
  `on_worker_meter` — send `self.stats()`, one shape);
* `_post` now **returns True when the callable was queued and False when it was dropped** (no form
  yet), and `emit_async` **releases the slot** on a drop or on a raise. Without that, the first push
  before the form exists would latch forever and the stats channel would go permanently silent — a
  worse failure than the queue this bound exists to fix.

The three other `_post` callers (`_measure_startup_visibility`, `_reassert_hidden`,
`_fit_client_area`) ignore the return value, so the new answer changes nothing for them.

## The instrument — in process, launches nothing

`py -3 _main/emit-queue-bound-oracle.py` imports the shell, builds it with `object.__new__` (no
`__init__`, so no window and no locks) and stubs the only two things `emit_async` touches: `_post`
and the WebView2 core. It asserts:

| # | check | measured |
|---|---|---|
| 1 | 100 pushes while the UI has not drained | **1** posted callable |
| 2 | draining that callable | **1** script, carrying **M99** (newest), not M98 |
| 3 | the latch releases after a drain | the next push posts |
| 4 | two channels | **2** pending posts (independent slots) |
| 5 | 1000 concurrent pushes from 4 threads | **1** posted callable |
| 6 | a DROPPED post (form not up yet) | **3 of 3** pushes post — the latch does not stick |

* **LIVE: `VERDICT: PASS`, rc=0.**
* **`--neg-arm`** — the same six checks against a copy of the shell with the coalescing guard turned
  into `pass`: **RED as expected** on #1 and #5 (`100 undrained pushes posted 100 callable(s)`,
  `1000 concurrent pushes posted 1000 callable(s)`), rc=0. So the oracle can say NO. The mutant is
  written beside the shell (it imports `hot_reload` from its own directory) and deleted in a
  `finally`.

## Pins

| artefact | bytes | sha256 |
|---|---|---|
| `app/webview/sotto_webview.py` (after) | **427 185** | **`F2AB162913CC9DFC…`** (16-hex; full hash below) |
| `_main/emit-queue-bound-oracle.py` | 7 443 | `4855495866461F94…` |
| before this change (the revive revision `7f2708b`) | 424 688 | `c28cea4add837a67…` |

Endings after the edit: **8 440 CRLF / 0 bare LF** (unchanged discipline: every added line is CRLF).
`py -3 -m py_compile app/webview/sotto_webview.py` → rc=0.

## What is NOT measured

1. **Whether this prevents a freeze in the real app.** No launch is permitted under the owner's
   standing order, so the end-to-end effect is UNMEASURED. What is measured is the queue bound itself.
2. **Whether the queue ever actually grew in the owner's runs.** The queue depth was never
   instrumented, so the freeze's cause is still unattributed; this removes one candidate mechanism
   rather than proving it was the one.
3. **The caption path.** `emit_async` is used ONLY by the stats/meter feed (two call sites, both
   `kind='stats'`); captions go through the blocking `emit`. Coalescing therefore cannot drop a
   caption — but that separation is verified by reading the call sites, not by a run.
