# gate_run.ps1 -- real-execution verification of the FIXED scale gate.
#
# What the self-test (_main/scale_gate_selftest.py, 9/9 arms incl. R0_old_logic)
# cannot do: run the shipped probe against a real store.py / search.py and read
# a real exit code.  That is this script's only job.
#
# Run A: the probe, UNMODIFIED, on its own 16 ms budget.  Expect RESULT: PASS, rc 0.
# Run B: the SAME probe and the SAME measurement path, but with the budget
#        threshold driven to a deliberately impossible value.  Expect
#        RESULT: FAIL and a NON-ZERO rc.  If run B ever returns rc 0, the gate
#        is still broken and that is the headline finding.
# Run C (-Big): the full n=211200 population, opt-in, because it is slow.
#
# EXIT-CODE DISCIPLINE (the bug that bit this host before): stdout+stderr go to
# a FILE with `> file 2>&1` and the rc is read from $LASTEXITCODE afterwards.
# Never pipe to Select-Object -First N -- a closed pipe turns a failing exit into
# a fake success.
#
# THREADS: the probe itself sets OMP/OPENBLAS/MKL/NUMEXPR to 2 before numpy is
# imported and calls store.set_thread_budget(2).  This script does not add any.
#
# Usage:  pwsh -File _main/gate_run.ps1 [-Big]

$ErrorActionPreference='Continue'
$env:TMPDIR='I:\cc-tmp'
$env:PYTHONIOENCODING='utf-8'

$wt='H:\sotto-wt\gateverify'
$probe=Join-Path $wt '_moved\aireplay\_main\slice_scale_probe.py'
$outdir=Join-Path $wt '_main'
$big=($args -contains '-Big')

# ---------------------------------------------------------------------------
# Run A -- the compliant run, 16 ms budget, probe untouched.
# ---------------------------------------------------------------------------
$a_out=Join-Path $outdir 'gate_run_A_20000.txt'
python $probe 20000 100 4096 > $a_out 2>&1
$a_rc=$LASTEXITCODE

# ---------------------------------------------------------------------------
# Run B -- impossible budget.  The probe's argv is POSITIONAL ONLY:
#     probe.py [N] [n_queries] [chunk]
# There is NO --budget-ms flag; BUDGET_MS is a module constant (line 47).  So
# the threshold is lowered from OUTSIDE, at import time, by this runner -- the
# probe file on disk is not edited, and every measured number comes from the
# same real code path as run A.  Both gate clauses are re-pointed: BUDGET_MS is
# read as a module global inside latency_stats() at call time, while gate()'s
# p95_max default was bound at def time, so __defaults__ is rebound too.
# ---------------------------------------------------------------------------
$b_drv=Join-Path $env:TMPDIR 'gate_impossible_budget.py'
$b_out=Join-Path $outdir 'gate_run_B_impossible.txt'
$py=@'
import importlib.util, pathlib, sys

probe_path = sys.argv[1]
budget_ms = float(sys.argv[2])
rest = sys.argv[3:]

spec = importlib.util.spec_from_file_location("slice_scale_probe", probe_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

probe.BUDGET_MS = budget_ms
probe.P95_MAX_MS = budget_ms
probe.gate.__defaults__ = (probe.gate.__defaults__[0], budget_ms)

sys.exit(probe.main(["slice_scale_probe"] + rest))
'@
Set-Content -Path $b_drv -Value $py -Encoding utf8
python $b_drv $probe 0.0001 20000 100 4096 > $b_out 2>&1
$b_rc=$LASTEXITCODE
Remove-Item $b_drv -Force -ErrorAction SilentlyContinue

Write-Output "=== gate_run.ps1 real exit codes ==="
Write-Output ("RUN_A compliant  n=20000 rc=$a_rc  out=$a_out")
Write-Output ("RUN_B impossible budget=0.0001ms rc=$b_rc  out=$b_out")

# ---------------------------------------------------------------------------
# Run C -- full population, opt-in only.
# ---------------------------------------------------------------------------
if ($big) {
    $c_out=Join-Path $outdir 'gate_run_C_211200.txt'
    python $probe 211200 100 4096 > $c_out 2>&1
    $c_rc=$LASTEXITCODE
    Write-Output ("RUN_C full      n=211200 rc=$c_rc  out=$c_out")
} else {
    Write-Output "RUN_C full      n=211200 UNRUN (pass -Big to include)"
}