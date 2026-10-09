# Janela-censo: procura processos com janela visivel de python/powershell/node ligados a lanes
$procs = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^(python|pythonw|pwsh|powershell|node|cmd|conhost)\.exe$'
}
$rows = @()
foreach ($p in $procs) {
  $cmd = $p.CommandLine
  if (-not $cmd) { continue }
  $isSotto = ($cmd -match 'sotto|aireplay|_main|lane|oracle|probe|receipt')
  $pid_ = $p.ProcessId
  $w = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
  if ($w -and $w.MainWindowHandle -ne 0) {
    $rows += [pscustomobject]@{
      PID = $pid_; Name = $p.Name; Title = $w.MainWindowTitle
      Cmd = ($cmd.Substring(0, [Math]::Min(150, $cmd.Length)))
    }
  }
}
"POPULACAO = janelas visiveis entre $($procs.Count) processos candidatos"
if ($rows.Count -eq 0) { "NENHUMA janela visivel." }
else { $rows | Format-Table -AutoSize | Out-String -Width 220 }
