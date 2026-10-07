# font-lag-probe.ps1 — quanto tempo / quantos processos até uma alteração do
# registo de fontes do utilizador ficar visível a um processo NOVO?
#
# Mede a sério porque este atraso contamina qualquer A/B: uma captura tirada
# logo a seguir a mexer no registo pode mostrar o estado ANTERIOR.
#
# O instrumento é a sonda de largura do espécime (mesmo algoritmo da página):
# imprime RESOLVE / AUSENTE para "Fraunces". Fonte única da verdade: o DOM.
$ErrorActionPreference = 'Stop'
$k = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$N1 = 'Fraunces Fix (TrueType)'
$N2 = 'Fraunces Fix Italic (TrueType)'
$fx = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Variable-STATfix.ttf"
$fi = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Italic-Variable-STATfix.ttf"
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'

function VerdictoFr([string]$tag) {
  $udd = Join-Path $env:TEMP ('fontes-lag-' + [guid]::NewGuid().ToString('N'))
  $o   = Join-Path $env:TEMP 'lag.html'
  $ca = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
          "--user-data-dir=$udd",'--virtual-time-budget=1500','--dump-dom',
          'file:///H:/aireplay/_main/font-fraunces-specimen.html')
  $sw = [Diagnostics.Stopwatch]::StartNew()
  Start-Process -FilePath $chrome -ArgumentList $ca -RedirectStandardOutput $o `
    -RedirectStandardError (Join-Path $env:TEMP 'lag.err') -Wait | Out-Null
  $sw.Stop()
  $t = [System.IO.File]::ReadAllText($o)
  $m = [regex]::Match($t, 'Fraunces normal 300=([0-9.]+) \(([^)]*)\)')
  $res = if ($m.Success) { $m.Groups[2].Value } else { 'sem leitura' }
  $line = "  {0,-22} t={1,5:N1}s  Fraunces normal300={2}  -> {3}" -f $tag, $sw.Elapsed.TotalSeconds, $m.Groups[1].Value, $res
  Write-Output $line
  if (Test-Path -LiteralPath $udd) {
    $full = (Resolve-Path -LiteralPath $udd).Path
    if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-lag-') {
      Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  return $res
}

$t0 = Get-Date
Write-Output "estado inicial: $((Get-ItemProperty -LiteralPath $k).$N1)"
Write-Output "=== A. estado actual (conserto LIGADO), 3 processos novos ==="
1..3 | ForEach-Object { VerdictoFr "ligado #$_" | Out-Null }

Write-Output "=== B. REMOVE as 2 entradas: 3 processos seguidos + espera 6s + 2 processos ==="
Remove-ItemProperty -LiteralPath $k -Name $N1 -Force
Remove-ItemProperty -LiteralPath $k -Name $N2 -Force
$b = @()
1..3 | ForEach-Object { $b += (VerdictoFr "removido #$_") }
Start-Sleep -Seconds 6
$b += (VerdictoFr "removido +6s #4")
$b += (VerdictoFr "removido +6s #5")
Write-Output ("  -> ainda viam PRESENTE: {0} de 5" -f (($b | Where-Object { $_ -match 'RESOLVE' }) | Measure-Object).Count)

Write-Output "=== C. REPÕE as 2 entradas: 3 processos seguidos + espera 6s + 2 processos ==="
New-ItemProperty -LiteralPath $k -Name $N1 -Value $fx -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $k -Name $N2 -Value $fi -PropertyType String -Force | Out-Null
$c = @()
1..3 | ForEach-Object { $c += (VerdictoFr "reposto #$_") }
Start-Sleep -Seconds 6
$c += (VerdictoFr "reposto +6s #4")
$c += (VerdictoFr "reposto +6s #5")
Write-Output ("  -> ainda viam AUSENTE: {0} de 5" -f (($c | Where-Object { $_ -match 'AUSENTE' }) | Measure-Object).Count)
Write-Output ("tempo total: {0:N0}s   estado final: {1}" -f ((Get-Date) - $t0).TotalSeconds, (Get-ItemProperty -LiteralPath $k).$N1)
