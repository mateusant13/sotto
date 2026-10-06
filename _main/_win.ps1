
Get-CimInstance Win32_Process -Filter "ProcessId=7976" | Select-Object ProcessId,Name,CommandLine | Format-List
