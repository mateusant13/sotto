<#
    blind_run.ps1 -- drive _main/blind_corpus.txt into the aireplay-capture stdin channel.

    Feed order: every payload of the corpus is written to the child's stdin in corpus order, then
    stdin is closed.  Each payload is terminated per -Mode:
        lf         0x0A after every line   (the base measurement)
        crlf       0x0D 0x0A after every line
        nonewline  0x0A after every line EXCEPT the last one
    Deadlock note: the child writes about 5 KB total (one ~50 byte reply per input plus usage())
    while the input is about 140 KB.  The stdout pipe buffer is 64 KB and is never filled, so
    write-all-then-read-all cannot wedge.  Measured reply count is asserted, not assumed.

    Replies are the stdout lines that begin with '{'.  Everything else on stdout is the child's own
    log_line()/usage() text.

    Corpus payload dialect (see blind_corpus.txt):  \\  \"  \n  \r  \t  \xHH  <A*N>  \X -> \ and X
#>
[CmdletBinding()]
param(
    [string]$Exe     = 'I:\cc-tmp\blind_capture.exe',
    [string]$Corpus  = 'H:\sotto-wt\blind2\_main\blind_corpus.txt',
    [int]   $Runs    = 5,
    [string]$Mode    = 'lf',
    [string]$OutDir  = 'I:\cc-tmp'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Exe))    { throw "exe not found: $Exe" }
if (-not (Test-Path -LiteralPath $Corpus)) { throw "corpus not found: $Corpus" }
if ($Mode -notin @('lf','crlf','nonewline')) { throw "bad -Mode: $Mode" }

function Expand-Payload([string]$s) {
    if ($null -eq $s) { return [byte[]]@() }
    $sb = [System.Text.StringBuilder]::new()
    $i = 0
    while ($i -lt $s.Length) {
        $c = $s[$i]
        if ($c -eq '\' -and $i + 1 -lt $s.Length) {
            $n = $s[$i+1]
            switch ($n) {
                '\' { [void]$sb.Append('\') ; $i += 2; continue }
                '"' { [void]$sb.Append('"') ; $i += 2; continue }
                'n' { [void]$sb.Append("`n") ; $i += 2; continue }
                'r' { [void]$sb.Append("`r") ; $i += 2; continue }
                't' { [void]$sb.Append("`t") ; $i += 2; continue }
                'x' {
                    if ($i + 3 -ge $s.Length) { throw "truncated \x escape in payload" }
                    [void]$sb.Append([char][Convert]::ToInt32($s.Substring($i+2,2),16))
                    $i += 4; continue
                }
                'A' {
                    if ($i + 3 -ge $s.Length) { throw "truncated \x escape in payload" }
                    [void]$sb.Append([char][Convert]::ToInt32($s.Substring($i+2,2),16))
                    $i += 4; continue
                }
                default { [void]$sb.Append('\'); [void]$sb.Append($n); $i += 2; continue }
            }
        }
        # <A*N> filler
        if ($c -eq '<' -and ($i + 3) -lt $s.Length -and $s.Substring($i,3) -eq '<A*') {
            $close = $s.IndexOf('>', $i)
            if ($close -lt 0) { throw "unterminated <A*N> in payload" }
            $n = [int]$s.Substring($i+3, $close - ($i+3))
            for ($k = 0; $k -lt $n; $k++) { [void]$sb.Append('A') }
            $i = $close + 1; continue
        }
        [void]$sb.Append($c); $i++
    }
    # C-escape string -> raw bytes, latin1 style (one char == one byte for everything we emit)
    $out = [byte[]]::new($sb.Length)
    for ($k = 0; $k -lt $sb.Length; $k++) { $out[$k] = [byte][char]$sb[$k] }
    # unary comma: prevent PowerShell from enumerating the byte[] into the output stream.
    # Without it a multi-byte payload arrives as Object[] and an empty payload arrives as $null,
    # which makes Process.StandardInput.BaseStream.Write throw "Value cannot be null. (Parameter 'buffer')".
    return ,$out
}

# ---- read the corpus -------------------------------------------------------------------------
$cases = @()
foreach ($raw in [System.IO.File]::ReadAllLines($Corpus)) {
    $line = $raw.TrimEnd("`r")          # .gitignore/autocrlf: a checkout may add CRLF
    if ($line -eq '' -or $line.StartsWith('#')) { continue }
    $f = $line.Split('|')
    if ($f.Count -lt 4) { throw "bad corpus line: $line" }
    $cases += [pscustomobject]@{
        Id      = $f[0].Trim()
        Class   = $f[1].Trim()
        Expect  = $f[2].Trim()
        Payload = $f[3]
        Note    = if ($f.Count -gt 4) { $f[4].Trim() } else { '' }
        Bytes   = Expand-Payload $f[3]
    }
}
Write-Host ("corpus: {0} inputs from {1}" -f $cases.Count, $Corpus)

function HexOf([byte[]]$b, [int]$max = 32) {
    if ($b.Length -eq 0) { return '(empty)' }
    $n = [Math]::Min($max, $b.Length)
    $s = ($b[0..($n-1)] | ForEach-Object { $_.ToString('x2') }) -join ''
    if ($b.Length -gt $n) { $s += '..' + $b.Length + 'B' }
    return $s
}

function Classify([string]$reply) {
    if ($null -eq $reply -or $reply -eq '') { return 'NOREPLY' }
    if ($reply -match '"error":"line too long"') { return 'TOOLONG' }
    if ($reply -match '"ok":true')  { return 'TRUE' }
    if ($reply -match '"ok":false') { return 'FALSE' }
    return 'ODD'
}

# ---- one run --------------------------------------------------------------------------------
$allRuns = @()
for ($run = 1; $run -le $Runs; $run++) {
    $payload = [System.IO.MemoryStream]::new()
    for ($i = 0; $i -lt $cases.Count; $i++) {
        $b = $cases[$i].Bytes
        $payload.Write($b, 0, $b.Length)
        $last = ($i -eq $cases.Count - 1)
        switch ($Mode) {
            'crlf'      { $payload.Write([byte[]]@(0x0D,0x0A),0,2) }
            'nonewline' { if (-not $last) { $payload.WriteByte(0x0A) } }
            default     { $payload.WriteByte(0x0A) }
        }
    }
    $inBytes = $payload.ToArray()
    $payload.Dispose()

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $Exe
    $psi.UseShellExecute        = $false
    $psi.RedirectStandardInput  = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.WorkingDirectory       = (Split-Path -Parent $Exe)
    $psi.StandardOutputEncoding = [System.Text.Encoding]::Latin1
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::Latin1

    $p = [System.Diagnostics.Process]::new()
    $p.StartInfo = $psi
    [void]$p.Start()
    $p.StandardInput.BaseStream.Write($inBytes, 0, $inBytes.Length)
    $p.StandardInput.BaseStream.Flush()
    $p.StandardInput.BaseStream.Close()      # EOF: this is what releases the child's blocking ReadFile

    $stdoutTask = $p.StandardOutput.ReadToEndAsync()
    $stderrTask = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit(120000)) { $p.Kill($true); throw "child hung on run $run" }
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $exit   = $p.ExitCode
    $p.Dispose()

    $replies = @($stdout -split "`n" | ForEach-Object { $_.TrimEnd("`r") } |
                 Where-Object { $_ -like '{*' })

    $rows = @()
    $expectN = ($cases | Where-Object { $_.Expect -ne 'NOREPLY' }).Count
    for ($i = 0; $i -lt $cases.Count; $i++) {
        $got = if ($i -lt $replies.Count) { $replies[$i] } else { '' }
        $act = Classify $got
        $rows += [pscustomobject]@{
            Run    = $run
            Id     = $cases[$i].Id
            Class  = $cases[$i].Class
            Bytes  = HexOf $cases[$i].Bytes
            Len    = $cases[$i].Bytes.Length
            Expect = $cases[$i].Expect
            Actual = $act
            Verdict = if ($act -eq $cases[$i].Expect) { 'pass' } else { 'FAIL' }
            Raw    = $got
        }
    }
    Write-Host ("run {0}/{1}: exit={2} replies={3} expected={4} {5}B in, stdout={6}B" -f `
        $run, $Runs, $exit, $replies.Count, $expectN, $inBytes.Length, $stdout.Length)
    $allRuns += ,$rows
}

# ---- results --------------------------------------------------------------------------------
$flat = foreach ($r in $allRuns) { $r }
$tsv = Join-Path $OutDir "blind-$Mode-$Runs.tsv"
$flat | Select-Object Run,Id,Class,Len,Bytes,Expect,Actual,Verdict,Raw |
        Export-Csv -Delimiter "`t" -NoTypeInformation -Path $tsv
Write-Host "wrote $tsv"

Write-Host ''
Write-Host '=== per-input (run 1; verdict must be identical in every run) ==='
foreach ($r in $allRuns[0]) {
    $vs = ($allRuns | ForEach-Object { ($_ | Where-Object Id -eq $r.Id).Verdict }) -join ','
    $mark = if ($r.Verdict -eq 'pass') { ' ok  ' } else { ' FAIL ' }
    Write-Host ("{0} {1,-4} {2,-12} len={3,-6} expect={4,-8} actual={5,-8} {6} {7}" -f `
        $mark, $r.Id, $r.Class, $r.Len, $r.Expect, $r.Actual, ($vs -replace 'pass','.' -replace 'FAIL','X'), $r.Raw)
}

Write-Host ''
$divergent = 0
for ($i = 0; $i -lt $cases.Count; $i++) {
    $seen = @{}
    foreach ($r in $allRuns) { $k = $r[$i].Raw; if ($seen.ContainsKey($k)) { $seen[$k]++ } else { $seen[$k] = 1 } }
    if ($seen.Count -gt 1) {
        $divergent++
        Write-Host ("DIVERGENCE {0} ({1}): {2} distinct replies across {3} runs" -f `
            $cases[$i].Id, $cases[$i].Class, $seen.Count, $Runs)
        foreach ($k in $seen.Keys) { Write-Host ("    x{0}  {1}" -f $seen[$k], $(if($k -eq ''){'(none)'}else{$k})) }
    }
}
Write-Host ("divergence: {0} of {1} inputs differed across {2} runs (mode {3})" -f $divergent, $cases.Count, $Runs, $Mode)

$fails = $flat | Where-Object Verdict -eq 'FAIL'
Write-Host ("SUMMARY mode={0} runs={1} inputs={2} failing-inputs={3} total-fail-rows={4}" -f `
    $Mode, $Runs, $cases.Count, ($fails.Id | Sort-Object -Unique).Count, $fails.Count)
foreach ($g in ($fails | Group-Object Id)) {
    $one = $g.Group[0]
    Write-Host ("  FAIL {0} {1} expect={2} actual={3} bytes={4}" -f $g.Name, $one.Class, $one.Expect, $one.Actual, $one.Bytes)
}
if ($divergent -gt 0) { Write-Host '  NOTE: divergence present -- see above, do not average' }