# font-specimen-shots.ps1 — captura o espécime (texto fixo, sem animação) COM e
# SEM as duas entradas do conserto. Mesmo instrumento, mesmo texto: a diferença
# de pixéis é atribuível à fonte, ao contrário das capturas da página, que é
# animada.
$ErrorActionPreference = 'Stop'
$k = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$N1 = 'Fraunces Fix (TrueType)'
$N2 = 'Fraunces Fix Italic (TrueType)'
$fx = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Variable-STATfix.ttf"
$fi = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Italic-Variable-STATfix.ttf"
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$url = 'file:///H:/aireplay/_main/font-fraunces-specimen.html'

function Shot([string]$out) {
  $udd = Join-Path $env:TEMP ('fontes-spec-' + [guid]::NewGuid().ToString('N'))
  $ca = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
          '--hide-scrollbars','--window-size=1400,560',"--user-data-dir=$udd",
          '--virtual-time-budget=2500',"--screenshot=$out",$url)
  $p = Start-Process -FilePath $chrome -ArgumentList $ca -PassThru `
        -RedirectStandardOutput (Join-Path $env:TEMP 'spec.out') `
        -RedirectStandardError  (Join-Path $env:TEMP 'spec.err')
  if (-not $p.WaitForExit(60000)) {
    Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
      Where-Object { $_.CommandLine -and $_.CommandLine.Contains($udd) } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Output "  HANG em $out"
  }
  if (Test-Path -LiteralPath $udd) {
    $full = (Resolve-Path -LiteralPath $udd).Path
    if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-spec-') {
      Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  Write-Output ("  {0}  {1} B" -f $out, (Get-Item -LiteralPath $out).Length)
}

Write-Output "=== COM o conserto ==="
Shot 'H:\aireplay\_main\font-fraunces-specimen-depois.png'
try {
  Write-Output "=== SEM o conserto (entradas removidas) ==="
  Remove-ItemProperty -LiteralPath $k -Name $N1 -Force
  Remove-ItemProperty -LiteralPath $k -Name $N2 -Force
  Shot 'H:\aireplay\_main\font-fraunces-specimen-antes.png'
}
finally {
  New-ItemProperty -LiteralPath $k -Name $N1 -Value $fx -PropertyType String -Force | Out-Null
  New-ItemProperty -LiteralPath $k -Name $N2 -Value $fi -PropertyType String -Force | Out-Null
  Write-Output "=== conserto reposto ==="
  Shot 'H:\aireplay\_main\font-fraunces-specimen-depois2.png'
}
