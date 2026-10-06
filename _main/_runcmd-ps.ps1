param([string]$Needle = 'sotto_webview')
# A process-list filter MUST run from a .ps1 FILE with Get-CimInstance:
# measured on this box, the inline `-Command` form returns EMPTY stdout.
# ($Needle is a REGEX matched against the command line.)
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match $Needle } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine |
    Format-List
