#!/usr/bin/env python
"""Seeds H:/sotto/revival/sim.jsonl with the attempts this repo actually ran.

Every row is a measurement that exists in the repo (oracle, receipt, log line);
nothing here is invented to fill the ledger. Failed attempts are PRESERVED, because
that is the point of the memory: the next lane must not re-walk them.

Run once: python _main/sim-seed.py
"""
from __future__ import annotations

import subprocess
import sys

S = r"C:\Users\Administrador\.agents\skills\project-revival\scripts\sim_memory.py"
MODEL = "deepseek-v4.1-flash"
REPO = "."


def record(cause, hypothesis, action, rationale, predict, benchmark, observed, passed, unresolved=None, commit=None):
    argv = [sys.executable, S, "--repo", REPO, "record", "--cause", cause,
            "--hypothesis", hypothesis, "--action", action, "--rationale", rationale,
            "--predict", predict, "--benchmark", benchmark, "--model", MODEL,
            "--observed", observed, "--passed" if passed else "--failed"]
    if unresolved:
        argv += ["--unresolved", unresolved]
    if commit:
        argv += ["--commit", commit]
    r = subprocess.run(argv, capture_output=True, text=True, cwd=r"H:\sotto")
    ok = r.returncode == 0 and '"ok": true' in (r.stdout or "")
    print(("OK  " if ok else "FAIL"), cause, (r.stdout or r.stderr).strip()[:120])
    return ok


PASSED = [
    dict(cause="captions-froze-on-a-pause-the-clock-disproved",
         hypothesis="The screen was blanked on a STALE 5.9 s photo while the player was moving, and yt_source_paused stayed armed, so unpausing never repainted.",
         action="Single owner youtube_clock.pause_proven(clock_static, clock_moving, photo_fresh) with measured movement winning, DOM_FRESH_S=1.2 from the snapshot's own stamp, YOUTUBE_PAUSE_STALE_PHOTO named per episode, and no path arming yt_source_paused without pause_proven.",
         rationale="One rule, one owner: two witnesses that disagree cannot both be right, and a photo older than the freshness threshold is not a witness at all.",
         predict="Contradicted pause episodes 0 on the owner's log; a real pause still blanks (arm19/arm20 stay green).",
         benchmark="_main/yt-pause-disagreement-oracle.py --log _main/webview-run.log; _main/youtube-monotonic-oracle.py",
         observed="episodes=2 contradicted=0 CLEAN rc 0 on his log (18 contradicted before the fix, 1 in his session); arm19-static-pause-still-blanks and arm20-cached-snapshot-is-not-a-second-measure green."),
    dict(cause="uia-caption-read-blocked-the-4hz-loop",
         hypothesis="One accessibility-tree read of 16437 ms had no per-stage budget, so it blocked the 4 Hz loop and collapsed it to 0.5 Hz.",
         action="app/webview/yt_read_budget.py: UIA_BUDGET_MS=350, HOLD_SCALE=3.0, HOLD_MIN_S=2.0; a read over budget buys a named hold and serves the last words instead of blocking again.",
         rationale="A stage has a budget and a typed refusal, never a clock that hides where it stalled.",
         predict="Simulated cadence with his numbers rises from 0.067 Hz to about 2.95 Hz; the episode prints YOUTUBE_UIA_SLOW_BUDGET instead of freezing silently.",
         benchmark="_main/yt-read-budget-oracle.py (battery pair yt-read-budget + red-as-expected-yt-read-budget)",
         observed="0.067 Hz -> 2.95 Hz in the simulated cadence; pair green in battery #19."),
    dict(cause="metric-red-arm-that-exits-zero",
         hypothesis="subsystem.feature_map_gate_ms declared `--gate --selftest` as its red arm; that exits 0, so benchmark_history --verify-red reported FALSE-GREEN and the gate could never fail that way.",
         action="_main/feature-map-neg-arm.py builds a temp repo with features/INDEX.md and no features.json, runs the canonical gate, and exits 1 only when the refusal names the missing map.",
         rationale="An arm that cannot fail the other way is a false green; the red arm must be a command that goes red.",
         predict="benchmark run --verify-red stops printing FALSE-GREEN and feature_map_gate_ms returns PASS with red_ok true.",
         benchmark="I:/!watcher/scripts/benchmark_history.py run --repo . --gate --verify-red",
         observed="NEG-ARM PASS rc 1; run --verify-red failures [] and subsystem.feature_map_gate_ms PASS 1344.18 ms."),
    dict(cause="clr-spawn-crash-turned-a-paint-metric-red",
         hypothesis="The GDI+ host died before any sample with 0xE0434352 (STATUS_CLR_EXCEPTION), so a spawn crash was scored as a product regression.",
         action="_main/yt-paint-metric.py retries that exit code ONCE, prints PAINT-METRIC retry=1 reason=clr-spawn-exception, and passes an honest FAIL/CANNOT-MEASURE through untouched.",
         rationale="Retrying a proven spawn crash is not retrying a verdict; the value is still measured once.",
         predict="1-of-4 caged failures become 0 without changing the measured 12.133 ms.",
         benchmark="_main/yt-paint-metric.py caged; benchmark_history run --verify-red",
         observed="VERDICT PASS 12.133 ms standalone and caged; the following gated run was 5/5 PASS."),
    dict(cause="mutation-harness-reparsed-the-monolith-per-mutation",
         hypothesis="nemotron-preload-oracle spent 6.75 s of 11.68 s in ast.get_source_segment, which re-splits the 1.5 MB shell on every call.",
         action="Swapped 12 sites to _main/_astcache.segment (cached line partition per source) and replaced a racing loaded=bridge.loaded arm with a bounded 5 s barrier on the contract fact.",
         rationale="Parse once per (file, content); an arm that reads a producer between two ticks measures the scheduler.",
         predict="Positive path about 6.9 s / 5.39 s CPU -> about 4.1 s / 3.0 s, neg-arm 60.8 s -> about 20 s with 17/17 mutants still caught.",
         benchmark="_main/nemotron-preload-oracle.py and --neg-arm, caged",
         observed="6.9 s/5.39 s CPU -> 4.1 s/3.00 s; neg-arm 60.8 s/51.44 s -> 20.5 s/17.28 s, 17/17 caught (rc 1). Commit d66c7e2."),
    dict(cause="benchmark-noise-floor-lived-in-a-fork",
         hypothesis="The 60 s min_delta existed only in the skill-tree copy of benchmark_history.py (0 `effective_floor` occurrences); the canonical script never needed it.",
         action="REVIVAL=I:/!watcher/scripts for benchmark gate/selftest and REVIVAL_SKILLS=skill scripts for feature_map_sync/loop_friction_audit; COMMANDS.md and VALIDATION.md repointed.",
         rationale="A number that exists only in a fork is not mine to defend; one variable would have silently turned four gates into MISSING.",
         predict="Canonical gate runs in about 23 s with rc 0 and the selftest in about 5 s; no gate becomes MISSING.",
         benchmark="I:/!watcher/scripts/benchmark_history.py run --repo . --label battery --gate; --selftest",
         observed="selftest {selftest PASS, arms 5} in 5.0 s; gate rc 0 in 22.9 s caged; all four gates proven running. Commit 7e50232."),
    dict(cause="js-spawn-sites-with-no-timeout",
         hypothesis="41 execFileSync/spawnSync call sites passed no timeout, so a hung child could outlive its budget and hang the caller.",
         action="Single index insertion of `timeout: 30000,` per call in 21 files plus two hoisted `-e` literals so the call fits the detector window; fail-fast pair wired into the battery.",
         rationale="Nothing may silently hang; the detector's own window is part of the contract, so the source was made detectable rather than the detector loosened.",
         predict="fail_fast_audit scan --gate 41 -> 0 findings; node --check green on all 21; every previously-green selftest still green.",
         benchmark="fail_fast_audit.py scan --repo . --gate; node --check; app/shadowplay/run-all.mjs",
         observed="0 findings; 21/21 node --check; 15/15 shadowplay suites and parse-gate 9/9 PASS. Commits 509594d, 96c678e. The 3 dispatch-guard reds are pre-existing and need the uninstalled plugin."),
    dict(cause="arm-raced-the-status-pump",
         hypothesis="`loaded=bridge.loaded` read the bridge between the state publish and the load publish, so the ready-before-open arm failed 1 in 3 under cProfile.",
         action="Bounded 5 s barrier on bridge.loaded with a named failure `bridge never reported loaded after frontend-ready`; deadline still fails.",
         rationale="An arm that observes a producer between two ticks measures the scheduler, not the product.",
         predict="The arm is green in repeated runs under cProfile, and the named failure fires when the barrier is not met.",
         benchmark="_main/nemotron-preload-oracle.py under cProfile, repeated",
         observed="Arm green in repeated runs; the named failure fires when the barrier is not met."),
]

FAILED = [
    dict(cause="cosine-threshold-for-speaker-slot-identity",
         hypothesis="Per-segment embeddings with a cosine threshold would keep one slot per voice across sparse speech.",
         action="Built _main/_slot-cosine-distribution.py over 120 s of the owner's multi-voice call and measured same-voice vs different-voice cosine distributions.",
         rationale="A name must never be wrong, so the threshold had to separate the populations before any code shipped.",
         predict="A threshold exists that separates the two populations.",
         benchmark="_main/_slot-cosine-distribution.py on the 2026-11-24 call",
         observed="same voice min +0.655 vs different voices max +0.743: the interval is EMPTY, so no cosine threshold separates them with this model on this audio. No threshold was added; the cost is an extra colour during sparse speech, never a wrong name.",
         unresolved="Slot identity during sparse speech stays unsolved; the dashboard may paint one colour too many for one person."),
    dict(cause="source-separation-model-for-per-voice-streams",
         hypothesis="A separation model would give one clean stream per voice for transcription.",
         action="Ran MossFormer2_SS_16K over 60 s of the same real call.",
         rationale="Per-voice transcription was the owner's order; separation was the candidate route.",
         predict="Two streams, each transcribing its own speaker, at a usable RTF.",
         benchmark="_main/bench/logs/moss-after.log",
         observed="1335.107 s for 60 s of audio (RTF 22.25); 210 words in stream 0 and 2 in stream 1 against 211 in the mix. Refuted on cost and on output.",
         unresolved="Per-voice separation needs a different mechanism; the sidecar + bridge route delivers voice:speaker-N today."),
    dict(cause="rewriter-that-glued-battery-step-lines",
         hypothesis="A census rewriter could convert red-as-expected step pairs into one step without touching behaviour.",
         action="_main/_red-arm-census.py --apply on _main/_audit-verify-all.cmd.",
         rationale="143.9 s versus 45.8 s looked like duplicated proof.",
         predict="Same gates, less time.",
         benchmark="_main/battery-launch.py --verify plus byte/CRLF diff of the .cmd",
         observed="It saved nothing (the step IS the invocation) and corrupted the file: lines glued with no CRLF and `--neg-arm --neg-armcall :expectred`; 448841 B/5111 CRLF instead of 448809/5115. Reverted with git checkout; --apply now refuses rc 2 CENSO-APPLY REFUSED.",
         unresolved="Battery wall time must come from not repeating work (per-step registry, content cache), not from deleting steps."),
    dict(cause="span-rewrite-codemod-for-js-timeouts",
         hypothesis="A generic span rewrite could insert timeout options into 21 JS call sites.",
         action="Two codemod attempts that rewrote the call span.",
         rationale="Hand-editing 41 sites is error-prone.",
         predict="41 sites fixed mechanically.",
         benchmark="node --check on all 21 files plus a diff against git show HEAD:<file>",
         observed="The first destroyed call arguments in every file; the second duplicated file tails. Both reverted with git checkout --. Replaced by a single index insertion at the options object, which passed node --check 21/21.",
         unresolved="No generic span rewriter is trusted in this repo without a shape diff against HEAD."),
    dict(cause="live-paint-cadence-without-the-owner-session",
         hypothesis="Paint cadence and reveal clock can be judged from a lane launch.",
         action="Launched the shell with SOTTO_LANE_LAUNCH=1 on port 9340 and tried to judge paint cadence.",
         rationale="The owner's freeze was a paint symptom.",
         predict="Paint cadence measurable without his screen.",
         benchmark="_main/keepalive.py lane launch plus _main/product-soak-oracle.py",
         observed="CAPTION_WANTED_START on=false reason=lane: with _caption_wanted false there are no cues and no CAPTION_PAINT_SURFACE, so cadence and the reveal clock cannot be judged. YouTube playback also returns LOGIN_REQUIRED (readyState 0) in a signed-out profile.",
         unresolved="Painting requires the strip on his screen (his word in that session); the lane covers attach, snapshot, pause/seek/clock and the read envelope only."),
]


def existing_causes() -> set[str]:
    """Idempotent: a cause already in the ledger is never re-recorded as round 1."""
    r = subprocess.run([sys.executable, S, "--repo", REPO, "show", "--json"],
                       capture_output=True, text=True, cwd=r"H:\sotto")
    try:
        import json
        doc = json.loads(r.stdout)
    except Exception:
        return set()
    return {e.get("root_cause_id") for e in doc.get("entries", [])}


def main() -> int:
    bad = 0
    have = existing_causes()
    for e in PASSED:
        if e["cause"] in have:
            print("SKIP", e["cause"], "(already in the ledger)")
            continue
        bad += not record(passed=True, **e)
    for e in FAILED:
        if e["cause"] in have:
            print("SKIP", e["cause"], "(already in the ledger)")
            continue
        u = e.pop("unresolved", None)
        bad += not record(passed=False, unresolved=u, **e)
    print("entries with a refusal:", bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
