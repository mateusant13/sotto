# Receipt — panel row identity, key (source, start) (STEP 4) — 2026-10-11

Lane: panel row identity. Write scope was `app/panel/panel.js`, `app/panel/caption-formulation.js` and
two NEW files (`_main/panel-row-identity-oracle.js`, this receipt). No `.cmd` file was written.
Nothing was launched: no shell, no worker, no `run.cmd`, no WebView2, no paint/DOM probe — the owner's
stop order ("para de abrir o sotto, ta travando meu pc quando ele abre") is in force and every number
below comes from `node` reading bytes, from read-only `git`, or from an in-process `vm`/jsdom run.

**Revision 2 of this receipt.** Revision 1 (12442 B, sha256 `B2F6ADDF0B1F260CFC43A017168DC83C695B63D61E579AFAE53682FC61E379E4`,
mtime 2026-10-11T21:38:55.745Z) carried sections 0, 1, 3, 4 and 5 below and a FOUR-arm oracle with ONE
mutant. This revision keeps all of that evidence in substance and replaces section 2 with the SEVEN-arm
oracle and FOUR mutants, adds the two instrument facts found while extending it, and adds section 5 (open
gaps). Nothing in sections 0, 1 or 4 was retracted.

---

## 0. STOP-THE-LINE FINDING: panel.js WAS ALREADY BEING WRITTEN BY ANOTHER ACTOR

I did NOT write `app/panel/panel.js`. When I measured it to make the edit, another actor was writing it
in real time. Measured in-process (`node`, `statSync` + `crypto.createHash('sha256')` over the same
bytes):

    21:26:27Z  132 233 B  (the revision I first read this session)
    21:26:53Z  133 707 B  18971ce88406b48a...
    21:28:26Z  135 941 B  eaea29dd973c9abf...
    21:29:09Z  137 400 B  9582e2e5a4907289...
    21:33:58Z  137 352 B  a0be06942eea066a19e04677df52d200f858cbbc7b514c88193aee24224b3928
    21:34:51Z  137 352 B  a0be0694... (same)
    21:35:03Z  137 352 B  (same)
    21:35:15Z  137 352 B  (same)
    21:35:27Z  137 352 B  (same)  -> settled for 3 consecutive 12 s samples

The live bytes already carried STEP 4's shape before I wrote anything: a function
`rowIdentity(source, start)` with the doc comment "THE KEY OF A COMMITTED ROW: (source, start) (STEP 4)",
and `app/panel/caption-formulation.js` (mtime 2026-10-11T21:25:47Z, 40 333 B) had `commit()` stamping
`source: engineSource`. Two writers on one file clobber or mangle it, so I stopped: the brief's own
collision rule ("REPORT in receipt, do not edit") applies to the write target itself. The collision was
reported to the parent at 21:28Z by `send_message`.

Consequence, stated plainly: **this lane delivers the VERIFICATION half** (an oracle that can say NO, and
this receipt), not the edit. The edit that is in the tree was landed by that other actor; every claim
below about `panel.js` is measured on the pinned revision above and is a claim about THOSE bytes, not
about the actor. `git diff --numstat -- app/panel/panel.js app/panel/caption-formulation.js` (HEAD =
pre-change revision) reads `218 75 panel.js` and `34 4 caption-formulation.js`; HEAD was
126551 B / `68A599AACA62B3F3D4ABC7237541980A52AB756AD6A1A0D308399743E1AB7E2B` for the panel and
37472 B / `075B53664D980D15179FE02F79FFD42D04B5E6470DA25FB47226B60C10F4ECBF` for the engine.

## 1. THE EDIT SITES AS THEY STAND (pinned revision 137 352 B / a0be0694...)

BEFORE (measured by me in the 133 707 B revision, `panel.js:873` — the keying this STEP replaces; that
text is GONE from the pinned revision, `grep` → 0 hits):

    const existing = start === null ? null : committedByStart.get(start) || null;
    committedByStart.delete(start);
    committedByStart.set(start, line);

AFTER (anchors re-measured by exact-text scan on the pinned revision; line numbers are HINTS, re-grep
before trusting them):

    panel.js:326   function rowIdentity(source, start)
                     -> null when there is no start; the NUMBER start when there is no
                        source; otherwise String(source) + "\u0000" + start
    panel.js:371   const paintedWordsBySource = new Map()   (was one paintedWords object)
    panel.js:382   const provisionalRows = new Map()        (keyed by the same identity)
    panel.js:398   const engines = new Map()                (one engine per source)
    panel.js:640   function engineFor(source)               -> createEngine({ source: key })
    panel.js:700   function armHoldTimer()                  -> for (const engine of engines.values())
    panel.js:755   function renderProvisional(committed, provisional, source)
    panel.js:855   function retireProvisional(source)
    panel.js:884   const source = meta && typeof meta.source === 'string' && meta.source ? meta.source : null
    panel.js:896   function addCaption(text, reason, meta)
    panel.js:915   const identity = rowIdentity(source, start);
    panel.js:926   if (source !== null) line.dataset.source = source;   (no attribute with no source)
    panel.js:972   const trimmedKey = rowIdentity(trimmedSource, trimmedStart);  (trim loop)
    panel.js:2452  for (const engine of engines.values()) engine.flush('status-change');
    panel.js:2803  the CLEAR-removal COMMENT (comment only: "an engine's reset()",
                   "retireProvisional() (now per source)") — no functional line in that hunk
    caption-formulation.js:582-588
                   onCommit(line, reason, engineSource === null
                     ? (tag === null ? { route, start, routeSource }
                                     : { route, start, routeSource, producer: tag })
                     : (tag === null ? { route, start, routeSource, source: engineSource }
                                     : { route, start, routeSource, producer: tag, source: engineSource }));

The no-source branch is the SAME literal, same keys, same ORDER as before the change — that is what keeps
a no-source run byte-identical, and CHK-E below checks it by RUNNING the engine, not by reading it.
Ordering rule respected (it is the rule that killed the panel for a day, see AGENTS.md):
`engines`/`provisionalRows`/`rowIdentity` are declared ABOVE the module-init block that calls
`wireCaptions()`.

## 2. THE ORACLE — BOTH COLOURS IN ONE COMMAND

    node _main/panel-row-identity-oracle.js --neg-arm

It runs the REAL `panel.js`, `caption-formulation.js` and `history-source.js` bytes in ONE `vm` context
against a hand-rolled DOM (node builtins only — no jsdom, no npm, no browser, nothing launched), and
`node --check` on the panel first. `--neg-arm` then rebuilds the same bytes with ONE thing removed at a
time, IN MEMORY (no copy on disk, no fifth repo path), and runs the SAME checks.

The flush is the panel's own: a status payload with non-empty text reaches `wireStatus`, which calls
`engine.flush('status-change')` for EVERY engine. `bridge.onStats`/`getStats` are deliberately absent, so
`wireLevel()` takes its documented early return.

### 2.1 Shipped colours (arm "AS SHIPPED", same command)

    panel-row-identity-oracle — real panel.js bytes in a node vm, fake DOM
      panel.js   137352 B  sha256 a0be06942eea066a19e04677df52d200f858cbbc7b514c88193aee24224b3928
      panel.js   mtime 2026-10-11T21:33:58.762Z
      engine     40333 B  sha256 6eb5fb8af421fa26cdaeef4cf6f37d49f3d0d831b16c9a1c787a9b4816159072
      node --check app/panel/panel.js -> rc=0

    GREEN CHK-A  same start + DIFFERENT sources -> TWO rows with their own text
          committed rows=2 [proc:111@10, proc:222@10] texts="Alpha one."/"Beta one."
    GREEN CHK-B  the same line again -> ONE row, text replaced IN PLACE
          source="proc:111" rows@20=1 same-node=true text "Gamma one." -> "Corrected." revision=true
    GREEN CHK-C  no source, same start twice -> still ONE row (pre-existing contract)
          rows@30=1 data-source=null same-node=true text "Delta one." -> "Corrected."
    GREEN CHK-C2 no source at all -> NO data-source attribute anywhere in the box
          rows=1 rows-with-data-source=0 dataset keys of the row=["index","indexPadded","revision","start"] text="Corrected."
    GREEN CHK-D  a partial for source A never rewrites the live row of source B
          provisional rows after A=1 after A+B=2 after A-repaint=2 | A kept "epsilon alpha ▍" while B="epsilon beta ▍" | A repaint -> "epsilon alpha extended ▍", B untouched=true
    GREEN CHK-E  commit meta: no-source literal byte-identical, source added LAST
          no-source keys=route,start,routeSource obj={"route":"final","start":5,"routeSource":"worker-stamped"} | +source keys=route,start,routeSource,source | +producer keys=route,start,routeSource,producer | +both keys=route,start,routeSource,producer,source | empty/null/number/object/array source keys=route,start,routeSource / ... / route,start,routeSource | two engines stamped ["proc:111","proc:222"]
    GREEN CHK-F  the trim path keeps the index on the rows that are still there
          MAX=200 rows after 200=200 after the 201st=200 (A,0) still there=0 | (B,0) rewritten IN PLACE=true rows=200 text="LinhaB reescrita." | append rows=200 last="Nunca vista."

    AS-SHIPPED COLOURS: CHK-A=GREEN CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=GREEN CHK-E=GREEN CHK-F=GREEN

What each arm is the CONTRACT for, not the implementation:

* **CHK-A / CHK-D** — two sources at the same audio second are two rows, and a partial for one never
  rewrites the other's live row. These are the two claims the per-source keying exists for.
* **CHK-C / CHK-C2** — the NO-SOURCE path is unchanged: one row per start, and NO `data-source` attribute
  anywhere in the document. C2 builds its own panel because in the shared harness earlier arms have
  already put the attribute on the list.
* **CHK-E** — the engine's half: keys AND key ORDER, from the engine source of the arm, with no DOM.
  Fail-closed cases are driven (`''`, `null`, `42`, `{}`, `[]` all keep the three-key literal), and two
  engines with different sources are shown to stamp their own.
* **CHK-F** — 201 commits across two sources: the oldest row leaves the DOM and its identity leaves the
  index with it; re-committing a surviving row replaces it IN PLACE; a never-seen line appends and trims
  back to `MAX_CAPTIONS`.

### 2.2 Both colours in the SAME command — four mutants

    M1 one engine for every app            (panel) engineFor(source) -> key = null
       mutant bytes 137308 B  sha256 6de8a6e73c12295b15e25a177d3af64772b3200e210640e0c7a6aa6625b75f36
       COLOURS: CHK-A=RED CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=RED CHK-E=GREEN CHK-F=RED
       must be RED    CHK-A,CHK-D -> all RED
       must stay GREEN CHK-B,CHK-C,CHK-C2,CHK-E -> all GREEN
       selective: true

    M2 the row key ignores the source      (panel) rowIdentity(source, start) -> source = null
       mutant bytes 137386 B  sha256 0d989f76731afadfd110287c4e7113af74d4058f8158ae4eaef43e47d00c40d1
       COLOURS: CHK-A=RED CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=GREEN CHK-E=GREEN CHK-F=RED
       must be RED    CHK-A -> all RED
       must stay GREEN CHK-B,CHK-C,CHK-C2,CHK-D,CHK-E -> all GREEN
       selective: true

    M3 the source key moves out of LAST place   (engine) { route, start, source, routeSource }
       mutant bytes 40333 B  sha256 198b570e854e166a57f2939d0792338d95b5d04e9b96026e005c8924d189329c
       COLOURS: CHK-A=GREEN CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=GREEN CHK-E=RED CHK-F=GREEN
       must be RED    CHK-E -> all RED
       must stay GREEN CHK-A,CHK-B,CHK-C,CHK-C2,CHK-D -> all GREEN
       selective: true

    M4 the no-source literal gains a source key (engine) { route, start, routeSource, source: null }
       mutant bytes 40347 B  sha256 fd146eb3c292d45489aa568033da030fdb9de4c920d992276b5721c041be0073
       COLOURS: CHK-A=GREEN CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=GREEN CHK-E=RED CHK-F=GREEN
       must be RED    CHK-E -> all RED
       must stay GREEN CHK-A,CHK-B,CHK-C,CHK-C2,CHK-D -> all GREEN
       selective: true

    VERDICT: PASS      (rc=0)

Notes that make the colours readable:

* **M1** is the pre-STEP-4 shape (revision 1 of this receipt measured the same mutant at 137332 B /
  `aeca05c8f70ffdccadd660b6713d99a4c1f745d158cc6a7955e883b18a7bb403` — same mutation, one comment
  string shorter now). A and D go RED because two apps share one buffer; F goes RED because two apps with
  the same audio second collapse onto one row (200 commits land as 100 rows). B, C, C2 and E stay GREEN —
  a mutant that reddens everything proves nothing.
* **M2** isolates the ROW KEY: the buffers are still per source, so D stays GREEN, and only A and F (the
  two arms about two sources colliding on a ROW) go RED. Revision 1 had no M2; it was added because M1
  removes two things at once (the engine split and the row key) and could not say which arm belonged to
  which.
* **M3** and **M4** isolate the ENGINE's half and redden **E alone**; every panel arm stays GREEN, which is
  exactly right — the panel reads `meta.source` by NAME and never depended on key order. M3 is the same
  byte count as the shipped engine (40333 B): a key reorder, nothing else.
* CHK-E runs the engine source OF THE ARM (`loadEngine(engineSource)`), not the shipped file, so an
  engine mutant is really measured by it.

### 2.3 Instrument facts the reader must know (all found in this lane)

1. **The harness's `dataset` now MIRRORS into attributes, the way a browser does.** CHK-C2's claim is the
   ABSENCE of `data-source`, and `querySelectorAll('[data-source]')` reads attributes — a plain `{}` for
   `dataset` would have left the selector blind to every write and made the arm vacuous. The independent
   half of that arm is `Object.keys(row.dataset)` on the row itself, which does not depend on the
   mirroring.
2. **The extended oracle exposed a bug IN THE INSTRUMENT, not in the panel — and it is fixed.** The
   harness's `isConnected` compared a node's root against a module-global `DOC`. Adding CHK-C2 and CHK-F
   (each builds its OWN panel) repointed that global, so the shared harness's rows suddenly looked
   detached and **CHK-D went RED on the first extended run**, with `provisional rows after A-repaint=3`.
   The fix is "walks up to A document root" (`n.nodeType === 9`), after which the shipped panel is all
   GREEN. Recorded because a RED that was the instrument's would otherwise have been read as a panel
   defect — and because a two-panel harness is exactly what the next per-source arm will need.
3. **A case-sensitivity bug in the oracle's OWN text matching** (revision 1): the engine's `formulate()`
   capitalises a line ("alpha one" → "Alpha one."), so the first version had CHK-A/B/C RED in BOTH arms.
   The neg-arm's "must stay GREEN" requirement caught it before the receipt was written. Rule this
   teaches: a green that cannot turn red is worthless, and so is a red that cannot turn green.

## 3. SIZES AND sha256 (every number from the command shown)

    node -e "const fs=require('fs'),c=require('crypto');for(const f of process.argv.slice(1)){const b=fs.readFileSync(f);console.log(b.length+' B  sha256 '+c.createHash('sha256').update(b).digest('hex')+'  '+fs.statSync(f).mtime.toISOString()+'  '+f)}" app/panel/panel.js app/panel/caption-formulation.js _main/panel-row-identity-oracle.js

    app/panel/panel.js                            137 352 B  sha256 a0be06942eea066a19e04677df52d200f858cbbc7b514c88193aee24224b3928
    app/panel/caption-formulation.js               40 333 B  sha256 6eb5fb8af421fa26cdaeef4cf6f37d49f3d0d831b16c9a1c787a9b4816159072
    _main/panel-row-identity-oracle.js             32 509 B  sha256 4fee0e456503a5746fe20aaca9e4780d15d260d8680846104ebe62d83ff14349  (628 lines, mtime 2026-10-11T21:42:24.981Z)

The oracle was **22 679 B / `c3c38db24f44a621f03b80cedf5958642482fcc39cf4c7b3436e26594d82b369`** when
revision 1 of this receipt pinned it (4 arms, 1 mutant). It is now the 7-arm / 4-mutant file above.
This receipt's own bytes + sha256 are reported in the lane's message to the parent, measured after this
write. The oracle re-reads both live files at every run and prints their bytes + sha256 + mtime itself, so
a stale green cannot be mistaken for a fresh one.

## 4. COLLISIONS OUTSIDE MY WRITE SCOPE — REPORTED, NOT EDITED

1. `app/panel/panel.js` — a second writer was active in it (section 0). Not my edit.
2. `app/panel/caption-formulation.js` — changed by that same writer (`commit()` now stamps
   `source: engineSource`, :582-588). Reported, not touched by me.
3. `_main/redux-live-contract-oracle.js` — **MEASURED NOW: VERDICT FAIL, rc=1** (13663 B, sha256
   `6AEA2480A83D94CBFAF100D32455220678751FA97F427E28AE90EF431D53133A`). It fails on its own anchor
   guard, `A0/panel-anchors`: "panel.js no longer contains:
   [`committedByStart.get(start)`, `committedByStart.set(start, line)`,
   `dom.list.querySelector('.caption--provisional')`, `retireProvisional(); addCaption(...)`] — the model
   below is STALE and this oracle must not be trusted". Its control arms still pass
   (`CONTROL-VERDICT PASS armB(wrong start)-RED=true armC(shared start)-RED=true`) and 7 of its 8 shipped
   arms hold; the anchor guard is the thing that went red, which is the guard doing its job. Command:
   `node _main/redux-live-contract-oracle.js`.
4. `_main/_panel2-repeat-probe.js` — **MEASURED NOW: the real-panel arm is GREEN 4/4, rc=0** (17959 B,
   sha256 `AC6660D445D7C08B1AD78987EADAA859B0FDC64FE4CBAC5EBA7E24C17F4BA57D`; real `panel.html` + its real
   scripts under jsdom against a stub bridge, node builtins + jsdom only — verified before running, no
   `child_process`, no shell). Its NEGATIVE CONTROL can no longer be built:
   `node _main/_panel2-repeat-probe.js --revert` → "SETUP ERROR: the identity lookup anchor is not in
   panel.js — the control cannot be built.", rc=2. It fails LOUDLY, which is the right failure, but the
   probe's control half is dead until its anchor is re-pointed at `rowIdentity`. Neither file is in my
   write scope.

## 5. OPEN GAPS this receipt does NOT close

1. The panel can now separate two sources, but **nothing in the app produces two sources at once**: STEP 5
   (two workers in one shell) does not exist. The separation is provable in-process only.
2. `wireStatus()` flushes EVERY engine on EVERY non-empty status payload, and that flush is not
   attributed to a source: with two live sources, a status line from one app commits the other app's held
   buffer as well. The worker stamps caption events with `source`; it is NOT MEASURED here whether its
   STATUS payload carries one, so it is not claimed either way. Out of my write scope, left to the owner's
   next step.
3. `SottoSkin.live(...)` is ONE surface: with two sources painting, the skin shows whichever painted last.
   Out of my write scope, not changed.
4. The engine's hold timer is ONE timer that drives every engine (`for (const engine of engines.values())`
   then re-arms while any holds). Correct, but not per-source-scheduled: a source that stops producing is
   still driven by the shared timer.
5. CHK-F drives 201 commits through the fake DOM. It measures the panel's INDEX, not a browser's layout.
6. The CLEAR removal's consequence — the live box can only be emptied by the worker's own `final:true` line
   boundary — is unchanged by this lane and was not re-measured here.

## 6. NOT-MEASURED

- **Any behaviour of the real shell / WebView2 / a painted panel: NO launch was made** (owner's stop
  order). The oracle's DOM is a hand-rolled fake in `node` and the jsdom probe is a library model; neither
  proves a paint, and the browser's own `data-*` reflection and `isConnected` semantics are MODELLED,
  not observed.
- **End-to-end two-app separation (STEP 5: two workers in one shell) does not exist in this repo**, so
  "two apps in one panel" is UNMEASURED here; what is measured is two SOURCES driven through the panel's
  own bridge contract in one process.
- **No real device / `proc:` source ever reached the panel**: every source string in every arm is a literal
  written by the oracle. Whether a real worker's `proc:<pid>` / `device:<name>` / `file:<name>` values
  reach the panel in the shape the engine expects is UNMEASURED here (the worker side is gated separately
  by `_main/per-app-source-plumbing-oracle.py`).
- **Whether the worker's STATUS payload carries `source`** — not measured, and the panel's status flush is
  per-panel, not per-source (section 5.2).
- **`SottoSkin.live(...)` with two sources** — which surface wins, and whether it flickers, is not measured.
- **The panel's behaviour with a device name containing `:`, quotes or backslashes** is argued from the code
  (Map keys, never attribute selectors), not exercised with such a string.
- **Whether the other actor's edits to `panel.js`/`caption-formulation.js` are finished, committed, or
  intended as the final shape: NOT MEASURED by me.** The pin above is the revision that was stable for 3
  consecutive 12 s samples at 21:35Z and unchanged at 21:42Z; if the file moves again, re-run the oracle
  (it prints the sha256 it measured).
- **The trim loop with two sources at the same start** is now covered by CHK-F in-process (200 rows, two
  sources, trim + in-place rewrite + append); it is still NOT covered against a real browser.
- No measurement of the owner's real audio, no GPU/model load, no timing/RSS numbers.
