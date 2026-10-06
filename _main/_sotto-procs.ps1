Get-CimInstance Win32_Process -Filter "name='pythonw.exe' or name='python.exe'" |
  Where-Object { $_.CommandLine -like '*sotto*' } |
  ForEach-Object { "{0}|{1}|{2}|{3}" -f $_.ProcessId, $_.Name, $_.CreationDate.ToString('HH:mm:ss'), $_.CommandLine }
