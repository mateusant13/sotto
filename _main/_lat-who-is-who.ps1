# _main/_lat-who-is-who.ps1 -- identity census for the latency answer.
# AGENTS.md: Get-CimInstance Win32_Process returns EMPTY inline; it must run from a .ps1 FILE.
# Read-only. Names no process for killing. Answers ONE question: which live process is
# the Sotto worker (sotto_worker.py) and which is the Sotto shell (sotto_webview.py),
# and what is each one's start time relative to the file each one is running.

$ErrorActionPreference = 'Continue'

$rows = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Select-Object ProcessId, Name, CreationDate, @{n='WS_MB';e={
        try { [math]::Round((Get-Process -Id $_.ProcessId -ErrorAction Stop).WorkingSet64/1MB,1) }
        catch { $null }
    }}, CommandLine

"pid     name       start                ws_mb  role        script"
"------  ---------  -------------------  -----  ----------  ------------------------------------------"

foreach ($r in ($rows | Sort-Object CreationDate)) {
    $cl = [string]$r.CommandLine
    $role = 'other'
    $script = ''
    if ($cl -match 'sotto_worker\.py')      { $role = 'WORKER'; $script = 'sotto_worker.py' }
    elseif ($cl -match 'sotto_webview\.py') { $role = 'SHELL';  $script = 'sotto_webview.py' }
    elseif ($cl -match 'BrandOps')          { $role = 'brandops'; $script = 'BrandOps backend' }
    elseif ($cl -match 'dsh|deepseek')      { $role = 'harness'; $script = 'dsh harness' }
    else {
        # keep the first recognisable script-ish token, so an unknown row is still identifiable
        $m = [regex]::Match($cl, '[A-Za-z]:\\[^"]*?\.py')
        if ($m.Success) { $script = $m.Value }
        else { $script = ($cl.Substring(0, [Math]::Min(70, $cl.Length))) }
    }
    $start = if ($r.CreationDate) { ([datetime]$r.CreationDate).ToString('yyyy-MM-dd HH:mm:ss') } else { '?' }
    '{0,-6}  {1,-9}  {2}  {3,5}  {4,-10}  {5}' -f $r.ProcessId, $r.Name, $start, $r.WS_MB, $role, $script
}

""
"--- the two scripts on disk, for the start-time comparison ---"
foreach ($f in @('H:\sotto\worker\sotto_worker.py', 'H:\sotto\app\webview\sotto_webview.py')) {
    $i = Get-Item $f
    '{0,-46} {1,9} B  mtime {2}' -f $i.FullName, $i.Length, $i.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
}
