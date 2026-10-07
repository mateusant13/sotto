# font-ab-experiment.ps1 — o controlo do conserto: com e sem as duas entradas de
# registo que apontam para as cópias STAT-corrigidas do Fraunces.
#
# Desenho: (1) ruído do instrumento (duas capturas do MESMO estado);
# (2) SEM o conserto -> 6 capturas + o diagnóstico da página;
# (3) COM o conserto -> o diagnóstico da página (as 6 capturas "depois" são as
#     do entregável, tiradas por font-shots.ps1 antes deste script).
# As entradas de registo voltam SEMPRE ao estado inicial (try/finally).
$ErrorActionPreference = 'Stop'
$k = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$N1 = 'Fraunces Fix (TrueType)'
$N2 = 'Fraunces Fix Italic (TrueType)'
$fx = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Variable-STATfix.ttf"
$fi = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Italic-Variable-STATfix.ttf"
$main = 'H:\aireplay\_main'

Write-Output "=== 1. ruído do instrumento (cine, MESMO estado, 2ª captura) ==="
& pwsh -NoProfile -File (Join-Path $main 'font-shots.ps1') -Dir (Join-Path $main '_fontes-ruido') -Views cine

try {
  Write-Output ""
  Write-Output "=== 2. SEM o conserto: remove as 2 entradas ==="
  Remove-ItemProperty -LiteralPath $k -Name $N1 -Force
  Remove-ItemProperty -LiteralPath $k -Name $N2 -Force
  foreach ($n in @($N1, $N2)) {
    $v = (Get-ItemProperty -LiteralPath $k).$n
    Write-Output ("  {0,-32} => {1}" -f $n, $(if ($null -eq $v) { '(ausente)' } else { $v }))
  }
  & pwsh -NoProfile -File (Join-Path $main 'font-shots.ps1') -Dir (Join-Path $main '_fontes-antes-instrumento')
  & pwsh -NoProfile -File (Join-Path $main 'font-measure.ps1') -Hash diag-compare -Name antesfix
}
finally {
  Write-Output ""
  Write-Output "=== 3. repõe o conserto (estado final) ==="
  New-ItemProperty -LiteralPath $k -Name $N1 -Value $fx -PropertyType String -Force | Out-Null
  New-ItemProperty -LiteralPath $k -Name $N2 -Value $fi -PropertyType String -Force | Out-Null
  foreach ($n in @($N1, $N2)) {
    Write-Output ("  {0,-32} => {1}" -f $n, (Get-ItemProperty -LiteralPath $k).$n)
  }
  & pwsh -NoProfile -File (Join-Path $main 'font-measure.ps1') -Hash diag-compare -Name depoisfix
}
