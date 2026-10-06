Get-CimInstance Win32_Process -Filter "ProcessId=3312" | Select-Object -ExpandProperty CommandLine
