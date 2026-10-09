$all = Get-Content H:\sotto\_main\webview-run.log
$all | Select-String "BRIDGE_(DEATH|EXIT|SILENT|SPAWNED|RESTART|CAPTION)" | Select-Object -Last 10 | ForEach-Object { $_.Line }
$c1 = @($all | Select-String "BRIDGE_SPAWNED").Count
$c2 = @($all | Select-String "BRIDGE_DEATH").Count
$c3 = @($all | Select-String "BRIDGE_RESTART").Count
Write-Output ("COUNTS SPAWNED={0} DEATH={1} RESTART={2}" -f $c1, $c2, $c3)
