# RECEIPT — freeze hunt, 2026-10-12 (lane: freeze-hunt)

**Owner's words:** "alguma coisa do sotto, faz meu pc dar uma travada muito forte a cada
alguns segundos. entenda o q é e arruam pra sempre. faz full hunt desse bug, trace,
audit com fix, etc."

**This receipt is MEASUREMENT ONLY.** No product code was written, edited or deleted.
Nothing under "worker/", "app/", "_main/instruments-battery.mjs" or "AGENTS.md" was
touched. The app, the shell and the worker were never launched, killed or restarted by
this lane. Every instrument runs on "pythonw.exe" (no console window) and writes only
under "_main/".

**Window of the measurements in this file:** 2026-10-12 13:41 – 14:39 -03:00.
All wall-clock times are -03:00.

---

## 1. VERDICT IN ONE PARAGRAPH

**The tap rotation is NOT the freeze.** It runs at **1.33 events/min (one every ~45 s)**,
and in the most recent 34-minute window it did not fire at all — so it cannot be something
that happens "a cada alguns segundos". In a 150 s window containing **149 measured
machine pauses, not one coincided with a tap-stall line**. **The thing that actually fires
"every few seconds" is the WH_MOUSE_LL click hook: 11.8/min, one every 5.1 s**, and each
firing does a synchronous "print(flush=True)" plus a log write + flush *inside the hook
proc*. **The machine does measurably pause — up to 57 ms, 3–15 times per minute — and that
survives gc.disable(), so it is the machine's and not the instrument's artifact.** But this
lane could not prove that the hook (or anything else in Sotto) *causes* a freeze the owner
would call "muito forte": the largest pauses measured with a clean instrument were
**57 ms**, and the 100–743 ms pauses seen in earlier windows came from instrument runs
that allocated hundreds of MB and are **not reliable**. **The single biggest machine cost
found is a worker death-restart loop: 8 "BRIDGE_EXIT" + 6 "BRIDGE_RESTART" in the last
1500 log lines, each death costing a full ~1 GB model load.** That loop is **not a Sotto
bug** — it is the hot-reload watcher restarting the worker every time a lane edits
"worker/sotto_worker.py", which happened at 13:50:51 and again at 14:17:38.

---

## 2. THE TAP — RATE, INTERVAL, DEVICE, AND WHY IT STOPS

### 2.1 Rate, measured three independent ways

| instrument | window | tap-stall events | rate | mean interval |
|---|---|---|---|---|
| "_main/tap-stall-rate-probe.py --secs 90" | 90 s @ ~13:42 | 2 | **1.33/min** | 45 s |
| "_main/tap-stall-rate-probe.py --secs 180" | 180 s @ ~13:5x | 4 | **1.33/min** | 45 s |
| clock-derived, whole 39388 era (2004 s) | 33.4 min @ 12:34–13:47 | 44 | **1.31/min** | ~30 s median |

The third row derives time from the "evidence_age_s" field that travels inside every
"BRIDGE_SILENT_BENIGN" line — the only monotonic clock in a log that carries **no
per-line timestamp** (registered deficiency). Inter-arrival gaps, in seconds:
"5, 597, 6, 21, 126, 917, 13, 40, 49, 40, 26, 40, 71, 128, 57, 43, 132, 43, 18, 30,
21, 52, 21, 329, 5, 74, 36, 25, 23, 337, 14, 16, 17, 60, 49, 16, 16, 16, 16, 16, 16,
16, 38" — i.e. a burst of ~16 s gaps, a few 5–6 s gaps, and long silences up to 15 min.
3 gaps <= 10 s, 15 <= 20 s, 29 <= 45 s, 9 > 60 s.

**And it stops:** in the last 1500 log lines (14:05:18 -> 14:39:23, 34.1 min) the count of
"tap-stall" lines is **0**. Device rotation continued without it: "device-rotated" 97
times in that same window = **2.85/min (every 21 s)**.

### 2.2 The device, and why the tap stops

Tap endpoints seen rotating, in order of appearance in the log:

1. "WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)" — the device named in
   the last "TAP_STALLED" the panel still holds in its stderr tail.
2. "WASAPI loopback: Speakers (NVIDIA Broadcast)"
3. "CABLE Output (VB-Audio Virtual Cable)" — the device the live worker holds **right now**.
4. "VoiceMeeter Output (VB-Audio Vo... [MME]" — the device named in every "SILENT-DEVICE".
5. Historically: "Entrada (Realtek HD Audio Line input)", "Fones de ouvido (soundcore Space Q45)".

**Why the tap stops — measured, not inferred:** the tap delivers **digital silence**.

* "BRIDGE_SILENT_BENIGN ... because=\"device-rotated reason=flat peak=0.0 floor=0.002\""
* "SILENT-DEVICE VoiceMeeter Output (VB-Audio Vo [MME] peak=9.2e-05 < floor=0.002 over
  60 blocks (2/10 opened candidates silent, captions=0)"
* "TAP_STALLED device='WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'
  stalled_s=60.0 blocks=0 captions=962 reopens=34"

"peak=0.0" against a floor of "0.002" means the loopback carries nothing. That is the
**routing law already written in AGENTS.md**: with nothing rendered into a virtual cable
every loopback reads silence, and "a live run that reads silence is usually CORRECT
BEHAVIOUR, not a regression". The worker is doing its job; the owner's audio is not
reaching the cable it is tapping. **The fix for a silent tap is a routing change in
VoiceMeeter / Windows Sound settings, not a code change.**

### 2.3 The most recent JSONL (task step 2)

"worker/runs/gate-live-silence.jsonl", **4845 B, mtime 2026-10-06 06:16:19 — six days
stale**. 12 events: 3 boot, 1 model-loading, 1 model-loaded, 1 gate, 1 device,
2 capture-started, **1 "device-rotated" (reason="flat", "WASAPI loopback:
{0.0.0.00000000}.{55395a4e-...}" -> "VoiceMeeter Output (VB-Audio Vo", "peak=0",
"window_s=6", attempt 1 of 5)**, 1 silent-device, 1 done.
**"per-app-tap-lost" = 0. "tap-stalled" = 0.**

**Redirect the task's assumption:** *no JSONL has been written anywhere under H:/sotto
in the last 48 h* (measured by walking every "*.jsonl"). The live worker's stdout is a
pipe and is never written to disk, so the live run is observable **only** through
"_main/webview-run.log" and "_main/panel-state.json".

---

## 3. IS THE FREEZE THE TAP ROTATION? — **REFUTED, TWICE**

**(a) The cadence does not match.** "A cada alguns segundos" means a few seconds. The tap
rotation is measured at **1.33/min (45 s)** in the windows where it fires, and **0/min** in
the most recent 34-minute window. That is 3–13x slower than the complaint, and sometimes
absent entirely.

**(b) Direct attribution, measured.** "_main/freeze-correlate.py" ran a tight timer loop for
150.9 s while watching the log grow at 10 Hz, then printed the log lines written **during**
each pause and in the 2 s **before** it. Result:

* **149 pauses > 20 ms, 5 > 100 ms, MAX 123.7 ms.**
* **Zero of them landed on a "device-rotated (tap-stalled)" line.** Not one. This is the
  refutation the tap hypothesis needed, and it is an instrument result, not an impression.
* 146 of the 149 pauses wrote **nothing at all** to the shell's log during the pause.
* **3 pauses coincided exactly with the log growing by 109 B, and that 109 B is one
  "OUTSIDE_CLICK source=hook" line** — i.e. the pause straddled the click hook's log write.

---

## 4. THE MACHINE PAUSE — MEASURED, AND CONTROLLED

"gc-control-probe" exists because a tight Python loop can manufacture its own pauses:
it appends millions of floats (a gen-2 collection costs 20–120 ms, exactly the size of the
pauses being measured) and can exhaust RAM and swap — which is what made two earlier runs
take 200–280 s of wall time to finish 60–150 s of probe time. The control therefore holds
**O(1) memory** (no list, just a max and six counters) and runs the same loop **twice in
one process**: 60 s with the collector at its defaults, then 60 s with gc.disable().

| half | iterations | rate | MAX gap | >20 ms | >50 ms | >100 ms |
|---|---|---|---|---|---|---|
| gc **enabled** | 183 664 502 / 60.0 s | 3.06 M/s | **57.098 ms** | 15 | 3 | 0 |
| gc **disabled** | 188 666 560 / 60.0 s | 3.14 M/s | **48.065 ms** | 6 | 0 | 0 |

**VERDICT (printed by the instrument): "pauses SURVIVE gc.disable() -> they are the
machine's."** So the earlier "the box freezes" readings were not the collector's.

**The honest ceiling this lane can claim: the machine pauses by up to ~57 ms, 3–15 times
per minute.** The 100–743 ms pauses recorded in the three earlier (list-allocating) runs
are **UNRELIABLE and are not claimed**. A 57 ms pause is perceptible — a 60 fps frame is
16.7 ms — but it is **not** a "travada muito forte", and this instrument runs on one
core of a 20-core box, so it **cannot see** a GPU/driver stall, a DPC storm, or a
single-core spin that does not deschedule it. **A strong freeze can be happening and this
instrument would report 57 ms.** That limit is stated so the receipt is not read as proof
that the box is healthy.

### 4.1 The shell's own heartbeat

"panel-state.json" is rewritten every "PANEL_STATE_INTERVAL_S = 2.0" s by the shell, so
its mtime is a box-wide heartbeat written by a process that does nothing else.
"_main/panel-stall-probe.py" sampled it at 200 ms for 45.1 s: **22 writes, gaps 2.01 –
2.07 s, MAX 2.07 s, zero gaps > 5 s.** The shell's writer never stalled.

---

## 5. WHAT *DOES* MATCH "A CADA ALGUNS SEGUNDOS"

Measured, last 1500 log lines (14:05:18 -> 14:39:23, 34.1 min), rate recomputed from the
"evidence_age_s" clock:

| event | count | rate | interval | matches "a few seconds"? |
|---|---|---|---|---|
| **"OUTSIDE_CLICK source=hook"** | **403** | **11.82/min** | **5.1 s** | **YES** |
| "device-rotated" (any reason) | 97 | 2.85/min | 21 s | borderline |
| "BRIDGE_SILENT_BENIGN" | 22 | 0.65/min | 92 s | no |
| "CAPTION_APPLIED" | 62 | 1.82/min | 33 s | no |
| "tap-stall" | **0** | 0/min | — | no |
| "WARN exec_js TIMEOUT" | **0** | 0/min | — | no |
| "BRIDGE_EXIT" / "BRIDGE_RESTART" / "HOT_RELOAD_WORKER_RESTART" | 8 / 6 / 6 | — | — | see §6 |

**The click hook is the only Sotto event whose measured cadence matches the complaint.**
"app/webview/sotto_webview.py" "_on_mouse" (:1996-2016) is a "WH_MOUSE_LL" proc
filtered to "WM_LBUTTONDOWN/RBUTTONDOWN/MBUTTONDOWN/XBUTTONDOWN", and it calls
"self._consider()" -> "_record()" -> "log()" **inside the hook proc**. "log()"
(:599-610) does "print(..., flush=True)" **and** "_LOG_FILE.write" + "flush" under
"_LOG_LOCK". So every click on the box costs a synchronous flush from inside a
low-level input hook, 11.8 times a minute. **Not measured: how long one of those
invocations actually blocks.** That is the gap.

---

## 6. THE NEW FINDING — A WORKER DEATH-RESTART LOOP (not a product bug)

**The parent's input said "0 x BRIDGE_RESTART / BRIDGE_EXIT / HOT_RELOAD_WORKER_RESTART in
the last 1500 lines". Re-measured at 14:04, that is no longer true:**

"BRIDGE_EXIT" **8**, "BRIDGE_RESTART" **6**, "HOT_RELOAD_WORKER_RESTART" **6** in the
last 1500 lines. The churn began between the parent's 13:0x measurement and 14:04.

Timeline from the log (wall times derived by chaining each worker's own "evidence_age_s"
anchors to the parent's anchor "pid 39388 spawned 12:34:46"):

| line | event |
|---|---|
| 104762 | "BRIDGE_EXIT pid=39388 rc=1" after **age 4361 s**, captions 1886, audio_s 1455 s |
| 104763 | "BRIDGE_SPAWNED pid=29536" |
| 104958 | "BRIDGE_EXIT pid=29536 rc=1", captions 22, audio_s 150 s, rss **2326 MB** |
| 105137 | "BRIDGE_EXIT pid=17724 rc=1", captions 37, audio_s 133 s, rss **1815 MB** |
| 105233 | "BRIDGE_EXIT pid=40128 rc=3", captions 0, audio_s 16.8 s, rss **1709 MB** |
| 105314 / 105380 / 105523 | three more "rc=3", audio_s 11–17 s, rss **1706–1710 MB** |
| 105432 | "BRIDGE_EXIT pid=17864 rc=1", audio_s 7.3 s |
| 105549 | "BRIDGE_SPAWNED pid=40032" |

**Every death costs a full worker cycle with a ~1 GB model load** ("rss_mb" 1706–1710 at
each death), plus a WASAPI tap open and a CUDA/ORT session init. Seven of them in ~2.5 min
is a large, repeated machine load — the only thing found here big enough to be called a
*travada*.

**What triggers it:** "HOT_RELOAD_WORKER_RESTART files=[\"sotto_worker.py\"]" and
"files=[\"model_vram_pool.py\", \"vram_residency.py\"]". A lane is editing the worker while
the owner uses the box:

* "worker/sotto_worker.py" — **326 681 B, mtime 2026-10-12 14:17:38** (325 485 B at
  13:50:51; it is being edited repeatedly)
* "worker/model_vram_pool.py" — 16 351 B, mtime 13:51:56 -03:00
* "worker/vram_residency.py" — 15 903 B, same mtime

**Verdict:** the loop is a **consequence of concurrent lane edits + the hot-reload
watcher**, not a defect in the shipped worker. It stopped being continuous — at 14:09 the
live worker (pid 40032) had been up 10 min with "peak=0.64" — and then **started again**:
"sotto_worker.py" was edited at 14:17:38 and worker pid 18516 started at 14:17:42.

### 6.1 Crash reasons the log actually carries (all-time counts of stderr_tail lines)

| message | n |
|---|---|
| "WasapiError: Initialize(SHARED\|LOOPBACK) failed: <no description> (0x8889000A)" | **18** |
| "ModuleNotFoundError: No module named 'onnxruntime'" | **14** |
| "IndentationError: unexpected indent" | **10** |
| "File \"…/sotto_worker.py\", line 1307, in choose_providers" | 7 |
| "SILENT-DEVICE VoiceMeeter Output (VB-Audio Vo [MME] …" | 30+ |

**0x8889000A = AUDCLNT_E_DEVICE_INVALIDATED** — the endpoint was reconfigured or
removed while the capture client was open. That is the WASAPI side of the same story as
§2.2: the audio graph on this box is being rebuilt under the worker.

---

## 7. STATE OF THE LIVE RUN AT 14:09:51 -03:00 (last direct read)

* shell pid **33248** ("pythonw.exe … sotto_webview.py", started 12:13:22, 43 MB)
* worker pid **40032** ("python.exe … sotto_worker.py", started 13:59:28, 489 MB, 244 s CPU)
* "worker.state = \"capture-started\"", "restarts=6 spawns=6 deaths=5"
* "workerStats" stderr tail: "peak=0.641724", "blocks=5699", "nonzero_blocks=2247"
  — **loud, healthy audio is flowing**
* tap device: "CABLE Output (VB-Audio Virtual Cable)"
* **"namedState = \"no-audio\""** — while the worker reports "peak=0.64".

**"namedState=no-audio" is a stale latch**, not a live reading: it is derived from
"noAudioEvidenceAgeS", which was ~3006 s old at the same instant the worker was
transcribing. The panel is displaying a state the worker left behind minutes ago. That is
a real UI defect worth its own receipt, but it is not the freeze.

---

## 8. WHAT IS **NOT** PROVEN — do not read any of these as established

1. **That anything in Sotto causes the owner's freeze.** The attribution run shows the
   pauses do not coincide with tap rotation; 3 of 149 coincide with a click-hook write;
   146 coincide with nothing the shell logs. That is not a causal result.
2. **The size of the freeze.** The clean instrument caps at **57 ms**. The 100–743 ms
   figures came from runs that allocated hundreds of MB and are **discarded as
   unreliable**. Nothing here measures a "travada muito forte".
3. **The duration of one click-hook invocation.** Never measured. §5 establishes the
   cadence (5.1 s) and the fact that the write happens inside the hook proc; it does not
   establish that the hook blocks for milliseconds.
4. **GPU state.** "nvidia-smi" was found at "C:\Windows\System32\nvidia-smi.exe" but
   fails with "Failed to initialize NVML: Unknown Error". **UNMEASURED.**
5. **What "python.exe run.py" (pid 37616, 826 MB, 28.6% of a core, started 12:41:43,
   parent "node.exe scripts/dev-all.mjs") is.** Not investigated — outside this lane's
   brief. It is a dev server, not Sotto.
6. **Whether the freeze is still occurring.** The windows disagree: the clean 14:34 run
   saw max 57 ms; earlier runs saw more, but those are confounded.
7. **Why "reruns=124"** in the worker's final stats, or what "reopens=37 -> 38" per
   minute means for the owner. Counted, not explained.
8. **The worker's "rc=1" deaths print no traceback** into the "stderr_tail" the shell
   keeps (the tails hold only "WORKER_STATS" ticks), so their cause is **not identified**.

---

## 9. RECOMMENDATIONS (no code written — measurement lane)

1. **Measure the hook, not the log.** The one gap in this hunt is the per-invocation cost
   of "_on_mouse" -> "log()" inside the "WH_MOUSE_LL" proc. An instrument that times
   "log()" itself (monotonic clock around the write, from a synthetic click) would turn
   §5's cadence into a duration. That is the measurement most likely to confirm or kill
   the only hypothesis that matches the complaint's cadence.
2. **Move the log write out of the hook proc.** If (1) shows a multi-millisecond block, the
   fix is to enqueue and let a writer thread flush — the hook proc should do no I/O. This
   is the one candidate change this hunt actually supports, and it is a change, so it is
   the Lead's call, not this lane's.
3. **Gate hot-reload on worker edits while the owner is at the box.** §6's loop is the only
   large machine cost found, and it is driven by lane edits. If a lane must edit
   "worker/sotto_worker.py" during the owner's session, restarting the worker costs a
   ~1 GB model load each time.
4. **Fix the stale "namedState=no-audio" latch** — separate receipt.
5. **Do not chase the tap rotation as the freeze.** It is measured at 1.33/min and 0/min,
   and 149 measured pauses never coincided with it. A silent tap is a routing problem the
   owner fixes in VoiceMeeter, per the routing law in AGENTS.md.

---

## 10. INSTRUMENTS CREATED (all new, all under "_main/", all "pythonw.exe", no console)

| file | what it measures |
|---|---|
| "_main/tap-stall-rate-probe.py" | samples "_main/webview-run.log" by byte offset every --interval s for --secs; counts "tap-stall", "ladder-flat", "benign", "execjs", "outside", "caption", "restart", "exit", "stats-push"; prints per-sample rows + a summary JSON. **Exit 0 even with 0 events.** |
| "_main/tap-stall-rate-180.json" | its output: 180 s @ 2 s cadence -> "tap-stall 4 (1.33/min, mean 45 s)", "outside 25 (8.33/min, mean 7.2 s)", "execjs 0", "restart 0", "exit 0" |
| "_main/panel-stall-probe.py" | samples "_main/panel-state.json" mtime at 200 ms; the gap histogram is the box-wide stall detector |
| "_main/freeze-jitter-probe.py" | tight timer loop + per-pause log attribution (byte offsets before/after each pause) |
| "_main/freeze-correlate.py" | 10 Hz offset->time map + tight loop; prints the log lines written **during** each pause and in the 2 s before it |
| "_main/gc-control-probe.py" | **the control**: O(1) memory, same loop twice in one process, gc on then gc off |

Raw captures kept: "_main/_jitter2.log", "_main/_panelstall.log",
"_main/_corr2.log" (empty — that launch never ran), "_main/tap-stall-rate-180.json".
Scratch ".ps1" process-census files: "_main/_freeze-*.ps1".

**House rules honoured:** nothing under "worker/", "app/", "_main/instruments-battery.mjs"
or "AGENTS.md" was written; no process was launched or killed by this lane; no console
window was created ("pythonw.exe" throughout; PowerShell only from ".ps1" files); no
"AGENTS.md" or context file was grepped; "H:/" paths only; the kill filter rule was
moot (nothing killed).
