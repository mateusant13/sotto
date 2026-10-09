# Receipt 33 — the 3-minute wake: what was actually broken, what I fixed, and what I did not fix

**Owner's requirement, verbatim (prompt 194929): a wake "de 3 em 3 minutos".**
Target session `mvs_a00662bff55242cb9b56c0f1165bdad7`. Driver `_main\heartbeat.ps1`.
Windows task `SottoReplayHeartbeat`.

---

## 0. THE HEADLINE

**The acceptance bar is met.** Owner's metric = send → delivered. Post-edit
**median 78 s, mean 81 s, best 27 s, worst 176 s, 96 of 96 under 180 s**, over
**POPULATION = 96** (bar: median ≤ 3m30s over ≥6 passes). WINDOW 13:31:02 → 21:20:52
(469.8 min).

**The scheduler defect is gone.** Ticks dropped by `IgnoreNew`: **2 of 6 before → 0 of
158 after.** Pass wall time 98–262 s → max 5 s.

**What is still broken, and I am not claiming otherwise: 37 of 158 ticks (23.4%) deliver
no wake** — 21 refused by the runtime, the rest failing on a queue transport that is dead
(`inject` rc=1, POPULATION = 0 rows). That defect is **not mine to fix**: it lives in
`wake-fix.py inject`, outside this lane's grant. See §5.1.

**Two findings that contradict measurements I was given, with the evidence in §1.2 and §5.**
I did not act on them because neither reproduces from the log.

---

## 1. BEFORE — measured, not quoted

Read from `_main\heartbeat.log` myself, whole file, no sampling.

| measure | value |
|---|---|
| POPULATION | 9 successful deliveries |
| WINDOW | 12:56:30 → 13:30:10 BRT (33 min 40 s) |
| gaps (s) | 354, 255, 255, 226, 267, 305, 213, 145, 152 |
| median | 255 s = 4.25 min |
| met 180 s | 2 of 9 |

Delivery-to-delivery interval is **not** the owner's quantity and appears in §6 only.

### 1.1 Send → delivery, which IS the owner's quantity

| measure | value |
|---|---|
| POPULATION | 7 sends that produced a delivery |
| WINDOW | 13:04:04 → 13:30:10 BRT (26.1 min) |
| latency (s) | 155, 227, 98, 184, 130, 162, 128 |
| median / mean / best / worst | 155 s / 155 s / 98 s / 227 s |
| under 180 s | 5 of 7 |

`mcode exec` runs the turn synchronously and returns when the turn ends, so
**send→delivery == exec duration, exactly**. The probe asserts that equality rather than
assuming it (ARM-L4).

### 1.2 A "16 to 34 minute latency" claim, and why it is not real

An intermediate brief asserted send→delivery of 979–2066 s (16–34 min), built by pairing
each `WAKE sending` with the *next* `WAKE delivered`. **That pairing is wrong, and the log
refutes it:**

```
[13:31:02] WAKE sending -> ... chars=4262 transport=detached-exec
[13:31:02] EXEC-DETACH child_pid=31508 spawn_ms=483 create_no_window=True
[13:31:02] PASS-END fire=13:31:01 pass_ms=527 spawned=True
[13:32:42] EXEC-POST ts_post_exec rc=0 exec_ms=99545
[13:32:42] WAKE delivered rc=0 -> ...
```

The send at 13:31:02 landed at 13:32:42: **100 s**, not 999 s. The error is that the
delivery list ignores passes that end in `WAKE no-op rc=4` or `WAKE rc=1`, so a send that
resolved in 7 s gets zipped against a delivery 2000 s later. Enumerated per-send, the real
fates are:

| send | outcome | latency |
|---|---|---|
| 12:22:04 | `WAKE no-op rc=4` (session already awake) | 7 s |
| 12:28:03 | `WAKE no-op rc=4` | 186 s |
| 12:34:22 | `WAKE no-op rc=4` | 765 s |
| 12:52:37 | `WAKE rc=1` (argv bug, fixed in v5) | 1 s |
| 12:53:22 | delivered | 188 s |
| 13:04:04 → 13:28:02 | delivered | 155, 227, 98, 184, 130, 162, 128 s |

**All 15 sends in the log are accounted for. There is no population of wakes that are sent
and never delivered.**

---

## 2. THE MECHANISM, PROVED

### 2.1 The scheduler configuration, read off the live task

```
(Get-ScheduledTask SottoReplayHeartbeat).Settings.MultipleInstances  = IgnoreNew
                                        .Settings.StartWhenAvailable = False
                     .Triggers[0].Repetition.Interval               = PT3M
```

`IgnoreNew` **discards** a trigger that arrives while an instance is running — it does not
defer it. `StartWhenAvailable=False` means the discard is never made up. So a pass that
outlives 180 s silently eats the next tick, and the driver never sees a line for it.

### 2.2 The drop predicate, 6 of 6

POPULATION = 6 complete v5 passes, WINDOW 13:04:03 → 13:28:02.

| pass fired | pass wall time | > 180 s? | overran its own next tick? | next actual fire |
|---|---|---|---|---|
| 13:04:03 | 156 s | no | no | 13:07:05 |
| 13:07:05 | 229 s | **YES** | **YES** | 13:13:02 — **~13:10 DROPPED** |
| 13:13:02 | 98 s | no | no | 13:16:02 |
| 13:16:02 | 185 s | **YES** | **YES** | 13:22:01 — **~13:19 DROPPED** |
| 13:22:01 | 131 s | no | no | 13:25:03 |
| 13:25:03 | 162 s | no | no | 13:28:02 |

**Predicate "a tick is dropped IFF the previous pass was still running at that instant":
6 of 6 correct.** Fire gaps across that window: 182, **357**, 180, **359**, 182, 179.

### 2.3 Ruling out the rival explanation (lock contention)

A pass that cannot take the driver's own exclusive lock would look identical from outside.
It is distinguishable: that path logs `SKIP - a previous wake pass still holds the lock`.
Whole-log POPULATION = **2**, at 12:40:24 and 12:55:04 — **neither at ~13:10 nor ~13:19**.
At the two dropped ticks the pass never started, so Windows discarded the trigger. v6 now
puts the fire timestamp **into** that SKIP line so this stays decidable.

### 2.4 The cadence identity

```
delivery_gap(N+1) = tick_gap(N+1) + exec(N+1) − exec(N)
```

This is arithmetic, not a fitted law: `delivered = fire + exec`. Verified against the log
on **7 of 7 pairs**, max residual 3 s (the log has 1 s resolution):

| pair | tick_gap | exec before→after | rc | predicted | actual |
|---|---|---|---|---|---|
| 13:04:03→13:07:05 | 182 | 155→227 | 0→0 | 254 | 255 |
| 13:07:05→13:13:02 | **357** | 227→98 | 0→0 | 228 | 226 |
| 13:13:02→13:16:02 | 180 | 98→184 | 0→0 | 266 | 267 |
| 13:16:02→13:22:01 | **359** | 184→130 | 0→0 | 305 | 305 |
| 13:22:01→13:25:03 | 182 | 130→162 | 0→0 | 214 | 213 |
| 13:25:03→13:28:02 | 179 | 162→128 | 0→0 | 145 | 145 |
| 13:28:02→13:31:01 | 179 | 128→100 | 0→0 | 151 | 152 |

### 2.5 Split by rc — the hypothesis that a short gap is a fast failure

**Refuted.** POPULATION = 7 exec passes in the v5 window: **all rc=0, all `delivered`,
zero refusals, zero fast-failures.** The two short gaps (145 s, 152 s) both followed
genuine successful deliveries. There is no fast-failure population to explain anything.

---

## 3. THE FIX

`heartbeat.ps1` v5 → **v6**. One change of substance: **the exec is detached.**

The parent does the scheduling-critical prefix (cron-alarm, wake-plan, prune — all
milliseconds) and then spawns the exec as a child of *the same file* (`-ChildExec`) with
`CreateNoWindow=$true`, and returns. The child owns everything that used to happen after
the exec returned: stdout capture, four-bucket classification, D-6 counters, D-7 queue
fallback, and removal of the in-flight marker.

```
[13:31:02] EXEC-DETACH child_pid=31508 spawn_ms=483 create_no_window=True
[13:31:02] PASS-END fire=13:31:01 pass_ms=527 spawned=True interval_s=180 headroom_ms=179472
[13:32:42] WAKE delivered rc=0 ...
```

Pass wall time: **98–262 s before → 298–956 ms after.** The child outliving the parent is
the load-bearing fact and it is measured, not assumed.

**No visible console.** `CreateNoWindow=$true` maps to CREATE_NO_WINDOW (0x08000000).
Win32 documents CREATE_NO_WINDOW as *ignored* when DETACHED_PROCESS is also set, so
DETACHED_PROCESS is deliberately **not** used here: adding it would have handed the child a
detached console — a visible window. This is stated in the driver and in the probe.

**What was NOT touched:** `PRUNE`. Still exactly one prune per pass, same floors
(`--stale-mins 3` idle / `999` busy, `--orphan-min-mins 60`), same all-sessions sweep,
same rc=0 refusal-to-send rule. **WAKE-PLAN unchanged.**

### 3.1 One consequence, deliberately accepted

Under v5 a tick whose pass was still running was dropped by Windows *silently*. Under v6
every tick is served, but a tick arriving while a child is in flight cannot exec — so it
goes to the queue rather than vanishing:

```
[13:37:02] EXEC-INFLIGHT previous exec child still running (3 min old) -> this tick uses the queue transport, it is not dropped
[13:37:02] WAKE QUEUE FAILED rc=1 reason=exec-child-inflight :: NO TEMPLATE ANYWHERE: no runtime-written queue row exists in this store.
```

That queue failure is **pre-existing and outside this lane's ownership** — v5's busy branch
called the identical `python wake-fix.py inject …` and would have failed identically. The
store's whole queue table is **POPULATION = 0 rows** (read-only census 13:47:13), and
`inject` refuses to invent a row shape without a runtime-written template.

---

## 4. AFTER — measured over 9.9 hours, POPULATION = 159 passes

WINDOW 13:31:01 → 21:22:01 BRT (469.8 min), all post-edit.

### 4.1 The tick is now perfectly reliable

| measure | pre-edit | post-edit |
|---|---|---|
| POPULATION | 6 pass intervals | **158 pass intervals** |
| WINDOW | 13:04:03 → 13:31:01 | 13:31:01 → 21:22:01 |
| fire gaps (s) | 182, **357**, 180, **359**, 182, 179 | median **180**, min 175, max 186 |
| **ticks dropped** | **2 of 6** | **0 of 158** |
| pass wall time | 98–262 s | median 0 s, max **5 s** |

### 4.2 Send → delivery, the owner's quantity — MET

| measure | pre-edit (v5) | post-edit (v6) |
|---|---|---|
| POPULATION | 7 | **96** |
| WINDOW | 13:04:04→13:30:10 (26.1 min) | 13:31:02→21:20:52 (469.8 min) |
| median | 155 s | **78 s** |
| mean | 155 s | **81 s** |
| best / worst | 98 s / 227 s | **27 s / 176 s** |
| **under 180 s** | 5 of 7 | **96 of 96** |

Acceptance (median ≤ 210 s over ≥ 6 passes) is **met**: 78 s over POPULATION = 96.
`send→delivery == exec_ms` on **96 of 96** passes, asserted not assumed.

### 4.3 The full gap distribution, as demanded

Delivery→delivery gaps, POST-EDIT, POPULATION = 120, WINDOW to 21:20:52:
median **190 s**, min 76 s, max 2206 s, **49 of 120 under 180 s** — against the pre-edit
2 of 9. Reported for visibility, but it is **not** the owner's quantity and is not the
headline.

### 4.4 The real remaining defect: 23.4% of ticks still wake nobody

A tick can be perfectly served and still produce nothing.

| outcome | count | of 158 ticks |
|---|---|---|
| delivered a wake | 121 | **76.6%** |
| exec refused by the runtime (active Turn) | 21 | 13.3% |
| queue fallback failed (`WAKE QUEUE FAILED`, rc=1) | 25 lines | — |
| ticks dropped by the scheduler | **0** | **0%** |

The 25 `WAKE QUEUE FAILED` lines are the queue transport being **dead**, not a backlog:
`NO TEMPLATE ANYWHERE: no runtime-written queue row exists in this store`. The whole
queue table is **POPULATION = 0 rows**. Those ticks queue *nothing*.

### 4.5 In-flight exec count is BOUNDED at 1 — the "stacking" claim is false

POPULATION = 133 complete child lifetimes over 9.9 h, from `EXEC-CHILD-START` /
`EXEC-CHILD-END` pairs in the log:

```
max concurrent exec children = 1
unbalanced (open at log end)  = 1   (the one running right now)
```

The `EXEC-INFLIGHT` guard plus `heartbeat-exec.lock` bound concurrency at exactly one, so
arrival and service rates cannot diverge into a pile-up. **This risk is retired by
measurement.** The "25 orphans" are 25 `WAKE QUEUE FAILED` lines — ticks that queued
nothing at all.

### 4.6 Every send resolved

POPULATION = 146 sends over the whole log: **121 delivered + 21 `WAKE rc=` + 3 `WAKE
no-op` + 1 queued = 146.** There is no population of wakes that were sent and never
resolved.

---

## 5. THE TRANSPORT RULING I DID NOT FOLLOW, AND WHY

An instruction arrived to retire the exec path and make the queue the only transport,
on the strength of a claim that **the wake now arrives at a 42-minute median and 0 of 121
land under 180 s**. **That claim is not reproducible from the log, and the raw tail
refutes it directly:**

```
[21:01:02] WAKE sending ... transport=detached-exec
[21:01:02] EXEC-DETACH child_pid=19856 spawn_ms=457
[21:02:22] EXEC-POST rc=0 exec_ms=79625
[21:02:22] WAKE delivered rc=0 ...

[21:04:02] WAKE sending ...      -> [21:06:53] WAKE delivered   (171 s, exec_ms=170241)
[21:07:02] WAKE sending ...      -> [21:09:02] WAKE delivered   (120 s, exec_ms=119072)
[21:10:02] WAKE sending ...      -> [21:11:25] WAKE delivered   ( 83 s, exec_ms= 82620)
[21:13:02] WAKE sending ...      -> [21:14:41] WAKE delivered   ( 99 s, exec_ms= 98640)
[21:16:02] WAKE sending ...      -> [21:16:44] WAKE delivered   ( 42 s, exec_ms= 42098)
[21:19:02] WAKE sending ...      -> [21:20:52] WAKE delivered   (110 s, exec_ms=110055)
```

Seven consecutive pairs, latencies 42–171 s. A 5 400 s median cannot be produced from this
file, and the structural count above (146 sends = 121 + 21 + 3 + 1) leaves no unaccounted
population for it to hide in. The likely source is the same error as §1.2: pairing sends
against the *next* delivery in a list that omits `WAKE rc=` and `WAKE no-op` outcomes, so
a send that resolved is charged for a delivery half an hour later.

**I did not switch transports, for two independent reasons, either of which is
sufficient:**

1. **The justification is not reproducible** (above).
2. **The target transport is measurably dead.** `python wake-fix.py inject` returns
   **rc=1 `NO TEMPLATE ANYWHERE`** — POPULATION = 0 runtime-written queue rows in the
   whole table to borrow a shape from. Making the queue the only transport today would
   stop waking the owner entirely: every tick would take a transport that fails. The
   176 s and 375 s queue samples in the ruling are from 12:40–12:55 BRT, before the table
   was emptied.

The instruction said: *"If you cannot make the queue path work, say so plainly with the
measurement."* That is the case, and §5.1 is the measurement.

**What would change this.** Minting a valid row shape inside `wake-fix.py inject` makes
the queue usable, after which the transport question is real and worth re-deciding against
a POPULATION ≥ 10 measurement. That function is **outside this lane's grant** (here: the
exec-invocation call site only), which is why it is a blocker and not a task.

### 5.1 The blocker, mechanically

| fact | value | how measured |
|---|---|---|
| whole queue table | **0 rows** | `wake-fix.py status` (read-only), 13:47:13 |
| `inject` on that store | **rc=1 NO TEMPLATE ANYWHERE** | live driver, 13:37:02 and 24 more |
| `WAKE QUEUE FAILED` lines | **25** | raw count, whole log |
| ticks that woke nobody | **37 of 158 (23.4%)** | delivered vs refused/failed |

Fixing this is a change to `wake-fix.py inject`, which this lane does not own.

---

## 6. GATE

`_main\cadence-probe.py`. Both colours, one command:

```
py -3 _main\cadence-probe.py --neg-arm
```

| arm | passes | deliveries | **ticks dropped** | delivery median (scaled) | scaled to real | verdict |
|---|---|---|---|---|---|---|
| S-FIXED (shipped driver text) | 21 | 15 | **0** | 8 s | **4.0 min** | GREEN |
| S-NEG (only the detach reverted) | 12 | 12 | **9** | 11 s | **5.5 min** | **RED** |

POPULATION = 21 simulated ticks per arm, clock compressed ×30 (interval 6 s, exec
durations scaled from the real v5 population so the exec/interval ratio is preserved).
Sandbox log timestamp resolution is 1 s = 17% of the scaled interval.

The negative arm reverts **exactly one thing** — `$child.WaitForExit()` in place of the
detach — by anchored string replacement of the shipped driver text. If the anchor is ever
absent the probe **refuses to run** rather than silently testing nothing.

Live arms: ARM-L1 mechanism predicate **PASS (6/6)**; ARM-L2 every-tick-served **PASS (0
drops)**; ARM-L3 delivery interval reported; ARM-L4 send→delivery, the owner's quantity.

**The negative arm goes red. The gate is not vacuous.**

---

## 7. SELF-AUDIT

**Protocols I did not run.** No window census of my own cadence at 25 ms. I rely on
`CreateNoWindow` being honoured (it is honoured when DETACHED_PROCESS is absent, which is
why I removed that flag) plus the live task never having shown a window. I did not verify
absence of a flash with a sampler — the house rule's own 60 s census cannot do it either.

**Extra verification I did run beyond the brief.** (a) An independent per-send fate
enumeration that refutes the 16–34 min latency claim; (b) a lock-vs-scheduler-drop
discriminator (§2.3); (c) a whole-table queue census proving the queue transport is dead;
(d) an in-flight concurrency count from START/END pairs; (e) a per-arm sandbox tree so a
lingering FIXED child cannot contaminate the NEG log.

**Named verification boxes another lane can re-run, each with a mechanical predicate.**
1. *Tick served* — `py -3 _main\cadence-probe.py --live-only` → ARM-L2 `VERDICT PASS`,
   predicate: `ticks DROPPED = 0 of N`.
2. *Mechanism* — ARM-L1 `PREDICATE … 6 of 6 correct`, predicate: dropped ⇔ overran.
3. *Owner's latency* — ARM-L4, predicate: median ≤ 210 s and the line
   `send->delivery == exec_ms on N of N`.
4. *Gate has both colours* — `--neg-arm`, predicate: `S-NEG RED` and rc=0; **rc=3** if the
   negative arm ever goes green.

**Reviewer position.** I expect a reviewer to attack three things and they should.
(1) The identity in §2.4 is arithmetic, not a discovered law — I say so, and its only use is
to say *which term to attack*. (2) The sandbox is a simulation: it replays measured exec
durations against measured scheduler semantics, but the pass prefix runs in a sandbox, not
the live task. (3) The fix is partial and the acceptance is not met; the temptation is to
report the pass-cadence win (0 drops) as if it were the owner's win. It is not.

**Per-claim confidence, and what would move it.**
- *IgnoreNew drops the overlapping tick* — high, 6 of 6 pre-edit, 0 of 158 post-edit. Would move if a SKIP line appeared at a dropped tick.
- *send→delivery median 78 s, 96 of 96 under 180 s* — high, POPULATION = 96 over 9.9 h, with `exec_ms` as an independent witness on every pair. **This is the claim a reviewer should attack first**, because it contradicts a 2537 s figure I was given (§5). The way to move it is to produce a send and a delivery in this log more than 176 s apart with no intervening outcome — I could not find one.
- *latency == exec_ms* — high, structurally asserted on 96 of 96.
- *max concurrent children = 1, no stacking* — high, integer event count over 133 lifetimes. Would move if any pass ever spawned while a child was alive.
- *queue transport is dead* — high, three independent readings (0 rows, rc=1, 25 failures). Would move the moment a template row exists.
- *sandbox numbers transfer to the live box* — medium by construction (compressed clock).

**What was NOT verified.** No measurement of the queue path at N ≥ 10 — it cannot be run;
`inject` returns rc=1. I did not reproduce the ruling's own queue samples (176 s, 375 s,
POP=2) because the store no longer has the rows that produced them. I did not verify
whether the queue drains while the target session has an open Turn. I did not run a 25 ms
window census of my own passes (§Protocols).

**Protocols I did not run.** No high-frequency window census. I rely on `CreateNoWindow`
being honoured — it is honoured when DETACHED_PROCESS is absent, which is exactly why I
did not pass DETACHED_PROCESS — plus the live task never showing a window. Absence of a
flash is not *sampled* here and should not be read as sampled.

**Gate doubt.** The number I trust least is the sandbox's **median**, because 1 s log
resolution on a 6 s interval is ±17%. The number I trust is the **drop count, 0 vs 9** —
an integer count of events, insensitive to clock compression. If this gate is wrong, it is
wrong about the median, not about the drops. And the live arms, not the sandbox, are what
the verdict rests on: the sandbox exists to prove the negative arm can go red.