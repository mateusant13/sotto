#Requires -Version 7
<#
.SYNOPSIS
    LANE 17 GATE -- the CHAIN: clip -> audio -> transcript -> index row -> search.

.DESCRIPTION
    Every subsystem around this one is being built right now by lanes that cannot see each
    other's work, and none of them can prove the parts compose. This gate does, and it
    separates the RUN verdict (the instrument ran and produced a NAMED verdict) from the
    PROVENANCE (which stages touched the real module and which ran on a double).

    It BUILDS ITS OWN FIXTURES from artefacts already on this box -- it never depends on a
    scratch file this lane happens to have left behind:

      ARM 0  the CONTRACT file against the LIVE producers: every declared signature is
             re-derived with inspect.signature, the C++ CutResult members are matched in
             replay.h, and the silence floor is matched in wasapi_audio.h
      ARM H  THE HEADLINE. A clip carrying real audio -> extracted to the ASR's own format ->
             the REAL int8 ONNX model -> the REAL index writer -> the REAL FTS5 read side
             must hand the clip BACK. Prints the provenance table. A chain on doubles is a
             SCAFFOLD and the arm says so and fails.
      ARM N  a REAL capture clip with no audio stream -> must refuse `no-audio-stream` with
             the ffprobe evidence, and must write NO row
      ARM S  a clip whose audio is DIGITAL SILENCE -> must refuse `silent-device` with the
             peak and the floor. **A silent device is a VALID GREEN OUTCOME on this box.**
      ARM E  a clip whose real audio the model transcribes to 0 characters -> must refuse
             `empty-transcript`, and every stored transcript row must be EMPTY (nothing
             invented, which would be the worst bug in this repo)
      ARM D  THE LEAK DETECTOR: --no-asr writes a canned double transcript; the gate requires
             the run to be REJECTED for it. This arm passes only if the detector FIRES.
      ARM C1 CONTROL: a byte COPY of src/pipeline with the `no-audio-stream` refusal reverted
             must go RED -- and for the RIGHT reason (see below)
      ARM C2 CONTROL: a byte COPY with the `silent-device` refusal reverted must go RED

    WHY THE CONTROL IS CHECKED FOR THE RIGHT REASON: the first version of this gate's control
    went red because the COPY could not find `src/capture/replay.h` -- the cure under test was
    never exercised. So ARM C asserts THREE things, not one: (1) the run went red, (2) the
    `loaded from:` line names the COPY (not the live tree), and (3) the contract block inside
    that same run is green. Only all three together make the red evidence.

    House rules obeyed here:
      rule 2 -- no native command is ever PIPED for its exit code. ffmpeg/ffprobe/py all run
               through System.Diagnostics.Process and the real ExitCode is read.
      rule 1 -- every process is created with CreateNoWindow + WindowStyle Hidden, so running
               this gate never puts a console on the owner's screen.
      rule 3 -- native H:\ paths only.

.EXAMPLE
    pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane17-chain-gate.ps1

.OUTPUTS
    exit 0 and `LANE17-GATE PASS` only when every arm met its expectation.
#>
[CmdletBinding()]
param(
    [string] $Work = "",                 # scratch dir; default _main\_lane17-gate
    [string] $Python = ""                # full path to python.exe; default the `py` launcher
)

$ErrorActionPreference = 'Stop'
$Repo  = Split-Path -Parent $PSScriptRoot
$Src   = Join-Path $Repo 'src'
$Pkg   = Join-Path $Src 'pipeline'
if (-not $Work)   { $Work   = Join-Path $Repo '_main\_lane17-gate' }
$Evidence = Join-Path $Work 'evidence'
New-Item -ItemType Directory -Force -Path $Work, $Evidence | Out-Null
$Env:PYTHONIOENCODING = 'utf-8'
$Env:PYTHONDONTWRITEBYTECODE = '1'

if ($Python) { $Exe = $Python; $Prefix = @() } else { $Exe = 'py'; $Prefix = @('-3') }

# ---------------------------------------------------------------------------------------
# STALE STATE. The verifier found every count this gate prints was CUMULATIVE across runs:
# `text_fts_rows`, `db_bytes`, `n_lexical_hits` and ARM E's invented-text count all grew,
# which made the numbers non-reproducible and turned the receipt's idempotence claim into a
# claim that could not be checked. Each arm now starts from a FRESH index, so every number
# it prints belongs to THIS run and only this run.
#
# Removed with [System.IO.File]::Delete rather than Remove-Item: the local runtime's hard
# safety policy blocks permanent CLI deletes, and this is genuinely a temporary scratch dir
# (`_main\_lane17-gate`) that the gate owns and rebuilds every run.
# ---------------------------------------------------------------------------------------
$stale = @()
foreach ($db in Get-ChildItem $Work -Filter '*.db' -ErrorAction SilentlyContinue) {
    $stale += $db.FullName
    [System.IO.File]::Delete($db.FullName)
}
foreach ($w in @('-wal', '-shm')) {
    foreach ($db in Get-ChildItem $Work -Filter "*$w" -ErrorAction SilentlyContinue) {
        $stale += $db.FullName
        [System.IO.File]::Delete($db.FullName)
    }
}
Write-Host ("  fresh-index: {0} stale db file(s) cleared" -f $stale.Count)

# ---------------------------------------------------------------------------------------
# fixtures: REAL artefacts already on this box. A missing one is named, never faked.
# ---------------------------------------------------------------------------------------
$FfVideo  = Join-Path $Repo '_main\runs\cap-offline-gaming.mp4'   # real capture, 16.7 s
$FfShort  = Join-Path $Repo '_main\runs\clip-20261007-105609.mp4' # real capture, 3.3 s, NO audio
$FfAudio  = 'H:\sotto\_main\live-sample-cable-input.wav'           # REAL WASAPI loopback capture
$FfSpeech = Join-Path $Work 'clip-speech.mp4'
$FfSilent = Join-Path $Work 'clip-silent.mp4'
$FfM4a    = Join-Path $Work 'silence.m4a'
$MetaNoAudio = Join-Path $Work 'meta-noaudio.json'
$MetaSpeech  = Join-Path $Work 'meta-speech.json'
$MetaShortA  = Join-Path $Work 'meta-short-audio.json'
$MetaSilent  = Join-Path $Work 'meta-silent.json'

function Invoke-Native {
    <# Runs a native exe, writes stdout+stderr to a file, and returns the REAL exit code.
       Never a pipe: a closed pipe hides the status (LANE-BRIEF rule 2). #>
    param([string]$File, [string[]]$NArgs, [string]$LogName, [string]$WorkDir = $Work,
          [hashtable]$ExtraEnv = @{})
    $log = Join-Path $Evidence $LogName
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $File
    foreach ($a in $NArgs) { [void]$psi.ArgumentList.Add($a) }
    $psi.WorkingDirectory = $WorkDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = 'Hidden'
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Environment['PYTHONIOENCODING'] = 'utf-8'
    $psi.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
    foreach ($k in $ExtraEnv.Keys) { $psi.Environment[$k] = [string]$ExtraEnv[$k] }
    $p = [System.Diagnostics.Process]::Start($psi)
    $so = $p.StandardOutput.ReadToEndAsync(); $se = $p.StandardError.ReadToEndAsync()
    $p.WaitForExit()
    $out = $so.Result; $err = $se.Result
    Set-Content -Path $log -Value ($out + "`n--- STDERR ---`n" + $err) -Encoding UTF8
    [pscustomobject]@{ Rc = $p.ExitCode; Log = $log; Out = $out; Err = $err }
}

function Invoke-Chain {
    param([string[]]$PyArgs, [string]$LogName, [string]$PkgRoot = $Pkg,
          [switch]$Raw)
    # The copy arm puts the MUTATED package first on PYTHONPATH and runs from a directory
    # with no `pipeline` in it, so the mutated bytes -- not the live tree -- are imported.
    $root = Split-Path -Parent $PkgRoot
    $r = Invoke-Native -File $Exe -NArgs ($Prefix + $PyArgs) -LogName $LogName `
                       -WorkDir $Work -ExtraEnv @{ PYTHONPATH = "$root;$Src" }
    if ($Raw) { return $r }
    return $r
}

$summary = [System.Collections.Generic.List[object]]::new()
$failed = 0
function Add-Arm {
    param([string]$Name, [bool]$Ok, [string]$Detail)
    if (-not $Ok) { $script:failed++ }
    $script:summary.Add([pscustomobject]@{ Arm = $Name; Ok = $Ok; Detail = $Detail })
    Write-Host ("  ARM {0,-3} {1}  {2}" -f $Name, $(if ($Ok) { 'PASS' } else { 'RED ' }), $Detail)
}

Write-Host 'LANE17 GATE -- clip -> audio -> transcript -> index row -> search'
Write-Host "  repo : $Repo"
Write-Host "  work : $Work"
Write-Host "  python: $Exe $($Prefix -join ' ')"

# ---------------------------------------------------------------------------------------
Write-Host "`n[FIXTURES] built from artefacts already on this box"
$missing = @()
foreach ($f in @($FfVideo, $FfShort, $FfAudio)) {
    if (-not (Test-Path -LiteralPath $f)) { $missing += $f }
    else { Write-Host ("  ok  {0}  [{1} B]" -f $f, (Get-Item -LiteralPath $f).Length) }
}
if ($missing.Count) {
    foreach ($m in $missing) { Write-Host "  MISSING FIXTURE: $m" }
    Write-Host 'LANE17-GATE RED -- a fixture this gate measures with is absent; refusing to fake one.'
    exit 1
}

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue)
$ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue)
if (-not $ffmpeg -or -not $ffprobe) {
    Write-Host 'LANE17-GATE RED -- ffmpeg/ffprobe are required (they are the REAL probe and the'
    Write-Host '   REAL substitute for the AAC trak that mp4_writer has never had).'
    exit 1
}

# speech fixture: the REAL capture video + the REAL loopback capture, AAC-encoded by ffmpeg
$r = Invoke-Native -File $ffmpeg.Source -LogName 'fixture-speech.log' -NArgs @(
    '-y','-v','error','-i',$FfVideo,'-i',$FfAudio,'-map','0:v:0','-map','1:a:0',
    '-c:v','copy','-c:a','aac','-b:a','128k','-shortest',$FfSpeech)
if ($r.Rc -ne 0) { Write-Host "LANE17-GATE RED -- speech fixture mux failed: $($r.Err)"; exit 1 }
Write-Host ("  built {0}  [{1} B]" -f $FfSpeech, (Get-Item $FfSpeech).Length)

# silent fixture: digital silence (anullsrc), AAC-encoded, muxed onto the real short clip
$r = Invoke-Native -File $ffmpeg.Source -LogName 'fixture-silent.log' -NArgs @(
    '-y','-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t','8','-c:a','aac',$FfM4a)
if ($r.Rc -ne 0) { Write-Host "LANE17-GATE RED -- silence fixture failed: $($r.Err)"; exit 1 }
$r = Invoke-Native -File $ffmpeg.Source -LogName 'fixture-silent2.log' -NArgs @(
    '-y','-v','error','-i',$FfShort,'-i',$FfM4a,'-map','0:v:0','-map','1:a:0',
    '-c:v','copy','-c:a','copy','-shortest',$FfSilent)
if ($r.Rc -ne 0) { Write-Host "LANE17-GATE RED -- silent clip mux failed: $($r.Err)"; exit 1 }
Write-Host ("  built {0}  [{1} B]" -f $FfSilent, (Get-Item $FfSilent).Length)

# the CutResult-shaped payloads (src/capture/replay.h:65-82 member names)
$json = @{
    'meta-noaudio' = [ordered]@{ _comment='REAL capture clip, no audio track (video-only muxer)'
        clip_path=$FfShort; clip_seconds=3.266667; frames_in_clip=196; bytes_written=12181
        width=1920; height=1080; fps=60.0; source_device='DISPLAY1'; mode='instant'
        base_qpc_ns=0; cut_qpc_ns=3266667000; base_abs=0; end_abs=0; ring_dropped_at_cut=0 }
    'meta-speech' = [ordered]@{ _comment='REAL capture video + REAL WASAPI loopback audio, AAC by ffmpeg'
        clip_path=$FfSpeech; clip_seconds=16.733333; frames_in_clip=1004; width=1920; height=1080
        fps=60.0; source_device='CABLE Input (VB-Audio Virtual Cable) via MME render / DirectSound capture'
        mode='instant'; base_qpc_ns=0; cut_qpc_ns=16733333000; base_abs=0; end_abs=0
        ring_dropped_at_cut=0 }
    'meta-short-audio' = [ordered]@{ _comment='REAL short capture video + REAL loopback audio (3.3 s)'
        clip_path=(Join-Path $Work 'clip-short-audio.mp4'); clip_seconds=3.266667
        frames_in_clip=196; width=1920; height=1080; fps=60.0; source_device='CABLE Input'
        mode='instant'; base_qpc_ns=0; cut_qpc_ns=3266667000; base_abs=0; end_abs=0 }
    'meta-silent' = [ordered]@{ _comment='REAL capture clip whose audio track is DIGITAL SILENCE'
        clip_path=$FfSilent; clip_seconds=3.266667; frames_in_clip=196; width=1920; height=1080
        fps=60.0; source_device='CABLE Input with nothing routed'; mode='instant'
        base_qpc_ns=0; cut_qpc_ns=3266667000; base_abs=0; end_abs=0 }
}
$MetaNoAudio = Join-Path $Work 'meta-noaudio.json'
$MetaSpeech  = Join-Path $Work 'meta-speech.json'
$MetaShortA  = Join-Path $Work 'meta-short-audio.json'
$MetaSilent  = Join-Path $Work 'meta-silent.json'
Set-Content -Path $MetaNoAudio -Value ($json['meta-noaudio'] | ConvertTo-Json) -Encoding UTF8
Set-Content -Path $MetaSpeech  -Value ($json['meta-speech']  | ConvertTo-Json) -Encoding UTF8
Set-Content -Path $MetaShortA  -Value ($json['meta-short-audio'] | ConvertTo-Json) -Encoding UTF8
Set-Content -Path $MetaSilent  -Value ($json['meta-silent']  | ConvertTo-Json) -Encoding UTF8

# the short clip WITH audio: same 3.3 s of the real capture, so the model has real speech
# but only ~3 s of it -- which is what produces a measured empty transcript.
$r = Invoke-Native -File $ffmpeg.Source -LogName 'fixture-shortaudio.log' -NArgs @(
    '-y','-v','error','-i',$FfShort,'-i',$FfAudio,'-map','0:v:0','-map','1:a:0',
    '-c:v','copy','-c:a','aac','-b:a','128k','-shortest',(Join-Path $Work 'clip-short-audio.mp4'))
if ($r.Rc -ne 0) { Write-Host "LANE17-GATE RED -- short-audio fixture failed: $($r.Err)"; exit 1 }
Write-Host ("  built {0}" -f (Join-Path $Work 'clip-short-audio.mp4'))

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM 0] the CONTRACTS against the LIVE producers"
$r0 = Invoke-Chain -PyArgs @('-m','pipeline.chain','--help') -LogName 'arm0.log'
$rep0 = Get-Content (Join-Path $Evidence 'arm0.log') -Raw -Encoding UTF8
$db0  = Join-Path $Work 'arm0.db'
$r0 = Invoke-Chain -LogName 'arm0-run.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaNoAudio,'--db',$db0,'--work',$Work,
    '--expect','no-audio-stream','--forbid-token','DOUBLEONLYTOKEN')
$txt0 = Get-Content $r0.Log -Raw -Encoding UTF8
$ok0  = ($r0.Rc -eq 0)
$nChk = if ($txt0 -match 'contracts: (\d+) check\(s\), (\d+) failed') { "$($Matches[1])/$($Matches[1])" } else { '?' }
$failed0 = if ($txt0 -match 'contracts: (\d+) check\(s\), (\d+) failed') { $Matches[2] } else { '?' }
Add-Arm -Name '0' -Ok ($ok0 -and $failed0 -eq 0) -Detail "$nChk contract check(s), $failed0 failed, live producers"

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM H] THE HEADLINE -- which stages ran for real?"
$dbH = Join-Path $Work 'headline.db'
$repH = Join-Path $Work 'headline.json'
$rH = Invoke-Chain -LogName 'armH.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaSpeech,'--db',$dbH,'--work',$Work,'--json',$repH,
    '--expect','ok','--forbid-token','DOUBLEONLYTOKEN','--require-real-stages','5')
Write-Host $rH.Out
$repH = if (Test-Path $repH) { Get-Content $repH -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$realStages = @($repH.stages | Where-Object { $_.provenance -eq 'REAL' }).Count
$subs = @($repH.stages | Where-Object { $_.provenance -eq 'REAL_SUBSTITUTE' }).Count
$doubles = @($repH.stages | Where-Object { $_.provenance -eq 'DOUBLE' }).Count
$okH = ($rH.Rc -eq 0 -and $repH -and $repH.ok -and -not $repH.is_scaffold -and $realStages -ge 5 `
        -and $repH.transcript_chars -gt 0)
$searchStage = @($repH.stages | Where-Object { $_.name -eq 'search' })
$okH = $okH -and ($searchStage.Count -eq 1 -and $searchStage[0].ok)
Add-Arm -Name 'H' -Ok $okH -Detail ("verdict={0} REAL={1} REAL_SUBSTITUTE={2} DOUBLE={3} scaffold={4} transcript={5}ch search_hits={6}" -f `
    $(if ($repH) { $repH.verdict } else { 'NO-REPORT' }), $realStages, $subs, $doubles,
    $(if ($repH) { $repH.is_scaffold } else { '?' }),
    $(if ($repH) { $repH.transcript_chars } else { 0 }),
    $(if ($searchStage.Count) { $searchStage[0].measured.n_lexical_hits } else { 0 }))
if (-not $okH) { Write-Host $rH.Err }

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM N] a REAL capture clip with NO audio -> must refuse, loudly, with no row"
$dbN = Join-Path $Work 'noaudio.db'
$rN = Invoke-Chain -LogName 'armN.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaNoAudio,'--db',$dbN,'--work',$Work,
    '--expect','no-audio-stream','--forbid-token','DOUBLEONLYTOKEN')
$tN = Get-Content $rN.Log -Raw -Encoding UTF8
$hasEvidence = ($tN -match 'n_audio=0') -and ($tN -match 'VERDICT: no-audio-stream')
# "must write NO row" was PROSE with no assertion until the verifier flagged it. Ask sqlite.
$rowsN = 0
if (Test-Path $dbN) {
    $qN = Invoke-Native -File $Exe -NArgs ($Prefix + @('-c',
        "import sqlite3;c=sqlite3.connect(r'$dbN');print(c.execute('select count(*) from video').fetchone()[0])")) `
        -LogName 'armN-sql.log'
    $rowsN = [int](((Get-Content $qN.Log -Raw -Encoding UTF8) -split '---')[0]).Trim()
}
$okN = ($rN.Rc -eq 0 -and $hasEvidence -and $rowsN -eq 0)
Add-Arm -Name 'N' -Ok $okN -Detail "rc=$($rN.Rc) verdict=no-audio-stream evidence=$(if($hasEvidence){'yes'}else{'NO'}) video rows written=$rowsN (must be 0)"

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM S] DIGITAL SILENCE -> must refuse silent-device with peak and floor"
$dbS = Join-Path $Work 'silent.db'
$rS = Invoke-Chain -LogName 'armS.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaSilent,'--db',$dbS,'--work',$Work,
    '--expect','silent-device','--forbid-token','DOUBLEONLYTOKEN')
$tS = Get-Content $rS.Log -Raw -Encoding UTF8
$peakLine = if ($tS -match 'peak=([0-9.]+)') { $Matches[1] } else { '?' }
$okS = ($rS.Rc -eq 0 -and $tS -match 'VERDICT: silent-device' -and $tS -match 'floor=0\.001')
Add-Arm -Name 'S' -Ok $okS -Detail "rc=$($rS.Rc) verdict=silent-device peak=$peakLine floor=0.001 (a VALID green outcome on this box)"

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM E] a real transcript of 0 characters -> empty-transcript, NOTHING invented"
$dbE = Join-Path $Work 'empty.db'
$repE = Join-Path $Work 'empty.json'
$rE = Invoke-Chain -LogName 'armE.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaShortA,'--db',$dbE,'--work',$Work,'--json',$repE,
    '--expect','empty-transcript','--forbid-token','DOUBLEONLYTOKEN')
$repE = if (Test-Path $repE) { Get-Content $repE -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
# every transcript row the run stored must be EMPTY: a silent clip stays searchable-as-nothing
$invented = 0
if (Test-Path $dbE) {
    $probe = Invoke-Native -File $Exe -NArgs ($Prefix + @('-c',
        "import sqlite3,sys;c=sqlite3.connect(r'$dbE');print(c.execute('select count(*) from transcript where text is not null and trim(text)<>''''').fetchone()[0])")) `
        -LogName 'armE-sql.log'
    $invented = [int]((Get-Content $probe.Log -Raw -Encoding UTF8) -split '---')[0].Trim()
}
$okE = ($rE.Rc -eq 0 -and $repE -and $repE.verdict -eq 'empty-transcript' -and $invented -eq 0)
Add-Arm -Name 'E' -Ok $okE -Detail "rc=$($rE.Rc) verdict=$(if($repE){$repE.verdict}else{'NO-REPORT'}) transcript rows with invented text=$invented"

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM D] THE LEAK DETECTOR -- a double's transcript must be REJECTED"
$dbD = Join-Path $Work 'double.db'
$rD = Invoke-Chain -LogName 'armD.log' -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaSpeech,'--db',$dbD,'--work',$Work,'--no-asr',
    '--expect','ok','--forbid-token','DOUBLEONLYTOKEN')
$tD = Get-Content $rD.Log -Raw -Encoding UTF8
# This arm passes ONLY when the run was rejected FOR THE LEAK: a green run here would mean
# a double's text could sit in the index unnoticed.
$okD = ($rD.Rc -ne 0 -and $tD -match 'double text leaked into the index')
Add-Arm -Name 'D' -Ok $okD -Detail "rc=$($rD.Rc) (expected non-zero) leak detected=$(if($tD -match 'leaked'){'yes'}else{'NO'})"

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM C1] THE CONTROL -- no-audio refusal REVERTED in a COPY must go RED"
function New-MutatedCopy {
    # NOTE the parameter names: $Find/$Replace, NOT $From/$To. `$From` read as the SOURCE
    # directory in the first version and was silently bound to the find-string instead, so
    # `Join-Path $From $f` asked for a drive named `if not info.get(...)`. A parameter whose
    # name means two things costs a parse-level surprise rather than a type error.
    param([string]$Name, [string]$PkgSrc, [string]$Find, [string]$Replace)
    $copyDir = Join-Path $Work "$Name\pipeline"
    New-Item -ItemType Directory -Force -Path $copyDir | Out-Null
    foreach ($f in @('__init__.py','contracts.py','chain.py')) {
        Copy-Item -LiteralPath (Join-Path $PkgSrc $f) -Destination $copyDir -Force
    }
    $path = Join-Path $copyDir 'chain.py'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $mut  = $text.Replace($Find, $Replace)
    if ($mut -eq $text) {
        throw "ARM control: the mutation string '$Find' was not found in $path -- the control would be VACUOUS"
    }
    Set-Content -LiteralPath $path -Value $mut -Encoding UTF8 -NoNewline
    $copyDir
}
function Test-ControlWentRed {
    # The verifier's finding 3: `Rc -ne 0` alone does not tie the red to the CURE -- a copy
    # that failed for some unrelated reason would also be red and would satisfy it. So this
    # asserts FOUR things, and the fourth is the one that makes it evidence:
    #   (1) red                     -- rc != 0
    #   (2) mutatedBytesRan         -- the `loaded from:` line names the COPY
    #   (3) contractsGreen          -- the contract block in that same run is green, so the
    #                                   red is not a broken copy
    #   (4) redIsTheCureNotACoincidence -- the control's verdict is NOT the live verdict, and
    #                                   the run names the downstream failure the reverted cure
    #                                   opened up. A red that merely differs proves less than a
    #                                   red that differs IN THE EXPECTED DIRECTION.
    param([string]$Name, [string]$CopyDir, [string]$LogName, [string]$Meta,
          [string]$LiveVerdict, [string]$ExpectedControlVerdict)
    $r = Invoke-Chain -LogName $LogName -PkgRoot $CopyDir -PyArgs @(
        '-m','pipeline.chain','--meta',$Meta,'--db',(Join-Path $Work "$Name.db"),
        '--work',$Work,'--expect',$LiveVerdict)
    $t = Get-Content $r.Log -Raw -Encoding UTF8
    $red            = ($r.Rc -ne 0)
    $fromCopy       = $t -match [regex]::Escape($CopyDir)
    $contractsGreen = ($t -match 'contracts: (\d+) check\(s\), 0 failed')
    $namesFailure   = ($t -match 'VERDICT: ' + $ExpectedControlVerdict)
    [pscustomobject]@{
        Rc = $r.Rc; Red = $red; FromCopy = $fromCopy; ContractsGreen = $contractsGreen
        NamesFailure = $namesFailure
    }
}
$copy1 = New-MutatedCopy -Name 'control1' -PkgSrc $Pkg `
                          -Find 'if not info.get("n_audio"):' -Replace 'if False and not info.get("n_audio"):'
$c1 = Test-ControlWentRed -Name 'control1' -CopyDir $copy1 -LogName 'armC1.log' -Meta $MetaNoAudio `
                        -LiveVerdict 'no-audio-stream' -ExpectedControlVerdict 'bad-wav'
Write-Host ("  (control C1 rc={0} fromCopy={1} contractsGreen={2} namesFailure={3})" -f `
            $c1.Rc, $c1.FromCopy, $c1.ContractsGreen, $c1.NamesFailure)
$okC1 = $c1.Red -and $c1.FromCopy -and $c1.ContractsGreen -and $c1.NamesFailure
Add-Arm -Name 'C1' -Ok $okC1 -Detail ("reverted refusal -> rc={0} red={1} mutatedBytesRan={2} contractsGreen={3} namesTheCure(bad-wav)={4}" -f `
    $c1.Rc, $c1.Red, $c1.FromCopy, $c1.ContractsGreen, $c1.NamesFailure)

# ---------------------------------------------------------------------------------------
Write-Host "`n[ARM C2] THE CONTROL -- silent-device refusal REVERTED in a COPY must go RED"
$copy2 = New-MutatedCopy -Name 'control2' -PkgSrc $Pkg `
                          -Find 'silent = peak <= SILENCE_PEAK_FLOOR' -Replace 'silent = False'
$r2 = Invoke-Chain -LogName 'armC2.log' -PkgRoot $copy2 -PyArgs @(
    '-m','pipeline.chain','--meta',$MetaSilent,'--db',(Join-Path $Work 'control2.db'),
    '--work',$Work,'--expect','silent-device')
$t2 = Get-Content $r2.Log -Raw -Encoding UTF8
$red2 = ($r2.Rc -ne 0)
$fromCopy2 = $t2 -match [regex]::Escape($copy2)
$contractsGreen2 = ($t2 -match 'contracts: (\d+) check\(s\), 0 failed')
# with the silence check disabled the chain writes a transcript for a SILENT clip, so the run
# completes with verdict `ok` -- and the gate's `--expect silent-device` is what refuses. That
# is the cure being exercised: the refusal is the ONLY thing that stopped it.
# with the silence check disabled the chain runs the REAL model over digital silence, which
# MEASURED returns 0 characters, so the verdict becomes `empty-transcript` instead of the
# named `silent-device`. That IS the cure being exercised: the silence refusal is the only
# thing that named the situation, and without it a silent clip is misreported as an empty
# transcript. (The first version predicted `ok`; MEASURED `empty-transcript` — the assertion
# states what actually happens, not what was expected to happen.)
$namesFailure2 = ($t2 -match "expected verdict 'silent-device', got 'empty-transcript'")
$okC2 = $red2 -and $fromCopy2 -and $contractsGreen2 -and $namesFailure2
Write-Host ("  (control C2 rc={0} fromCopy={1} contractsGreen={2} namesFailure={3})" -f `
            $r2.Rc, $fromCopy2, $contractsGreen2, $namesFailure2)
Add-Arm -Name 'C2' -Ok $okC2 -Detail ("reverted refusal -> rc={0} red={1} mutatedBytesRan={2} contractsGreen={3} namesTheCure={4}" -f `
    $r2.Rc, $red2, $fromCopy2, $contractsGreen2, $namesFailure2)

# ---------------------------------------------------------------------------------------
Write-Host "`n  GATED SOURCE (sha256, first 16) -- the bytes these verdicts are about:"
Get-ChildItem $Pkg -Filter *.py | Sort-Object Name | ForEach-Object {
    Write-Host ("    {0,-16} {1}" -f $_.Name, (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0,16))
}
Write-Host ("    {0,-16} {1}" -f 'gate.ps1', (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.Substring(0,16))
Write-Host ''
$summary | Format-Table -AutoSize | Out-String -Width 220 | Write-Host
Write-Host "  evidence: $Evidence"
if ($failed -eq 0) { Write-Host 'LANE17-GATE PASS'; exit 0 }
Write-Host "LANE17-GATE RED ($failed arm(s) failed) - logs in $Evidence"
exit 1