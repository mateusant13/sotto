# List every process whose command line names the SOTTO ARTIFACT (never the bare
# word `sotto`), with pid and start time. Read-only: nothing is killed here.
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'sotto_webview\.py|sotto_worker\.py|_strip-surface-probe' } |
    Select-Object ProcessId, Name, CreationDate,
        @{n = 'cmd'; e = { $_.CommandLine.Substring(0, [Math]::Min(160, $_.CommandLine.Length)) } } |
    Format-List
