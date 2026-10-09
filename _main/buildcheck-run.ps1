<#
    buildcheck-run.ps1 -- compile gate for the Sotto/ArbV8 merged tree.

    Contract:
      * exit code of THIS script mirrors the compiler rc (0 = compiles, non-zero = does not).
      * The compiler rc is captured by REDIRECTING to a log file and reading $LASTEXITCODE.
        It is NEVER captured by piping to Select-Object -First N: a truncated pipe closes
        early, the native process dies with a broken-pipe status, and a real compile
        failure is reported as a fake success. That is the exact bug this gate exists to kill.
      * -SourceSet recipe = the exact file list in src/capture/build.cmd:12
        -SourceSet all    = every *.cpp under src/capture (catches files that were merged
                             into src/ but never added to build.cmd, i.e. silent no-build)
      * No -j flag: this mingw g++ 15.2.0 build rejects -j and -j2 outright
        (measured: "unrecognized command-line option '-j'"). Compilation is therefore
        single-threaded, which satisfies the <=2 threads measurement cap.

    Usage:
      pwsh -File _main/buildcheck-run.ps1 -RepoRoot <worktree> -Label head -SourceSet all
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$Label,
    [ValidateSet('recipe', 'all')][string]$SourceSet = 'all',
    [string]$LogDir = $env:TMPDIR
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($LogDir)) { $LogDir = 'I:\cc-tmp' }

$gxx = 'H:\msys64\mingw64\bin\g++.exe'
if (-not (Test-Path $gxx)) {
    Write-Output "FATAL: compiler not found at $gxx"
    exit 900
}

$src = Join-Path $RepoRoot '_moved\aireplay\src\capture'
if (-not (Test-Path $src)) {
    Write-Output "FATAL: source dir not found: $src"
    exit 901
}

# build.cmd:12 file list, verbatim.
$recipe = @(
    'main.cpp', 'common.cpp', 'd3d11_ctx.cpp', 'nv12_convert.cpp', 'wgc_capture.cpp',
    'nvenc_encoder.cpp', 'ring_buffer.cpp', 'mp4_writer.cpp', 'selftest.cpp',
    'test_window.cpp', 'replay.cpp'
)

if ($SourceSet -eq 'recipe') {
    $files = $recipe | ForEach-Object { Join-Path $src $_ }
    $missing = $files | Where-Object { -not (Test-Path $_) }
    if ($missing) {
        Write-Output "FATAL: recipe lists missing file(s): $($missing -join ', ')"
        exit 902
    }
} else {
    $files = (Get-ChildItem $src -Filter *.cpp -File | Sort-Object Name | ForEach-Object { $_.FullName })
}
if (-not $files -or $files.Count -eq 0) {
    Write-Output "FATAL: no source files resolved for SourceSet=$SourceSet"
    exit 903
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$outDir = Join-Path $LogDir "bc-$Label"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$exe = Join-Path $outDir 'aireplay-capture.exe'
$log = Join-Path $outDir "compile-$Label.log"

# build.cmd:12 link set. -lavrt/-luuid/-lole32/-loleaut32 plus the D3D/Win32 set already
# present in the recipe. There is NO -lwasapi in this mingw -- do not add it.
$libs = @('-ld3d11', '-ldxgi', '-lavrt', '-luuid', '-lole32', '-loleaut32',
    '-lruntimeobject', '-lwindowsapp', '-lpsapi', '-lgdi32', '-luser32')

$argList = @(
    '-std=c++17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter',
    '-I', $src, '-I', (Join-Path $src 'third_party')
) + $files + @('-o', $exe) + $libs

Write-Output "=== buildcheck label=$Label sourceSet=$SourceSet files=$($files.Count) ==="

$sw = [System.Diagnostics.Stopwatch]::StartNew()
# Redirect to file. Do NOT pipe.
& $gxx @argList *> $log
$rc = $LASTEXITCODE
$sw.Stop()

$lines = @()
if (Test-Path $log) { $lines = Get-Content $log }

$errLines = @($lines | Where-Object { $_ -match '(?i)\berror\b' })
$firstError = $null
foreach ($l in $errLines) { if ($l -match '(?i)\berror\b') { $firstError = $l; break } }

Write-Output "RC=$rc"
Write-Output "ELAPSED_MS=$($sw.ElapsedMilliseconds)"
Write-Output "ERROR_LINES=$($errLines.Count)"
Write-Output "LOG=$log"
if ($firstError) { Write-Output "FIRST_ERROR=$firstError" }
if ($rc -eq 0 -and (Test-Path $exe)) {
    Write-Output "EXE_BYTES=$((Get-Item $exe).Length)"
}
if ($rc -ne 0) {
    Write-Output '--- first 40 log lines ---'
    $lines | Select-Object -First 40 | ForEach-Object { Write-Output $_ }
}

# Machine-readable sidecar so results can be aggregated without re-running the compiler.
$side = [ordered]@{
    label      = $Label
    sourceSet  = $SourceSet
    rc         = $rc
    elapsedMs  = $sw.ElapsedMilliseconds
    fileCount  = $files.Count
    errorCount = $errLines.Count
    firstError = $firstError
    log        = $log
    utc        = (Get-Date).ToUniversalTime().ToString('o')
}
$side | ConvertTo-Json -Compress | Out-File -Encoding utf8 (Join-Path $outDir "result-$Label.json")

exit $rc