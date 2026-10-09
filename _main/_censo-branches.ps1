param()
$ErrorActionPreference = 'Continue'
$rows = @()
foreach ($r in (git for-each-ref --format='%(refname:short)|%(objectname:short)|%(committerdate:iso)' refs/heads/)) {
  $parts = $r -split '\|'
  $b = $parts[0]
  if ($b -eq 'main') { continue }
  $ahead = [int](git rev-list --count "main..$b" 2>$null)
  $behind = [int](git rev-list --count "$b..main" 2>$null)
  $rows += [pscustomobject]@{ Branch = $b; Ahead = $ahead; Behind = $behind; Date = $parts[2] }
}
Write-Output "branches (excl main): $($rows.Count)"
$withWork = @($rows | Where-Object { $_.Ahead -gt 0 })
$empty = @($rows | Where-Object { $_.Ahead -eq 0 })
Write-Output "com trabalho proprio (ahead>0): $($withWork.Count)"
Write-Output "sem trabalho proprio (ahead=0): $($empty.Count)"
Write-Output ""
Write-Output "=== TIPO x ESTADO ==="
$rows | ForEach-Object {
  $t = ($_.Branch -split '/')[0]
  $st = if ($_.Ahead -eq 0) { 'vazia' } else { 'com-trabalho' }
  "$t|$st"
} | Group-Object | Sort-Object Name | Format-Table Count, Name -AutoSize | Out-String
$rows | Export-Csv -NoTypeInformation -Path H:\sotto\_main\_branch-censo.csv -Encoding UTF8
Write-Output "=== 12 lanes com MAIS commits nao integrados ==="
$withWork | Sort-Object Ahead -Descending | Select-Object -First 12 | Format-Table Branch, Ahead, Behind, Date -AutoSize | Out-String
Write-Output "=== 8 mais ATRASADAS em relacao a main ==="
$rows | Sort-Object Behind -Descending | Select-Object -First 8 | Format-Table Branch, Ahead, Behind, Date -AutoSize | Out-String
