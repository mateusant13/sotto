# font-final-run.ps1 — a corrida final, com o ESTADO VERIFICADO antes de cada
# conjunto de capturas.
#
# Porque é que isto existe: mediu-se que uma alteração ao registo de fontes do
# utilizador NÃO é visível aos 2 primeiros processos novos (font-lag-probe).
# Sem verificar o estado, uma captura "antes" pode mostrar o estado "depois".
#
# O verificador é a sonda de largura do espécime — o mesmo algoritmo da página.
$ErrorActionPreference = 'Stop'
$k = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$N1 = 'Fraunces Fix (TrueType)'
$N2 = 'Fraunces Fix Italic (TrueType)'
$fx = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Variable-STATfix.ttf"
$fi = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\Fraunces-Italic-Variable-STATfix.ttf"
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$main = 'H:\aireplay\_main'

function SondaFr {
  $udd = Join-Path $env:TEMP ('fontes-vf-' + [guid]::NewGuid().ToString('N'))
  $o = Join-Path $env:TEMP 'vf.html'
  $ca = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
          "--user-data-dir=$udd",'--virtual-time-budget=1500','--dump-dom',
          'file:///H:/aireplay/_main/font-fraunces-specimen.html')
  Start-Process -FilePath $chrome -ArgumentList $ca -RedirectStandardOutput $o `
    -RedirectStandardError (Join-Path $env:TEMP 'vf.err') -Wait | Out-Null
  $t = [System.IO.File]::ReadAllText($o)
  $m = [regex]::Match($t, 'Fraunces normal 300=([0-9.]+) \(([^)]*)\)')
  if (Test-Path -LiteralPath $udd) {
    $full = (Resolve-Path -LiteralPath $udd).Path
    if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-vf-') {
      Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  if ($m.Success) { return $m.Groups[2].Value } else { return 'sem leitura' }
}

# espera até o instrumento reportar o estado pedido (RESOLVE = conserto activo)
function EsperaEstado([string]$quero) {
  for ($i = 1; $i -le 8; $i++) {
    $v = SondaFr
    Write-Host ("    sondagem #{0}: Fraunces -> {1}" -f $i, $v)
    if ($v -match $quero) { return $v }
    Start-Sleep -Seconds 2
  }
  throw "estado '$quero' nunca apareceu depois de 8 sondagens"
}

function Shot([string]$url, [string]$out, [int]$w = 1920, [int]$h = 1080, [int]$budget = 16000) {
  $udd = Join-Path $env:TEMP ('fontes-fs-' + [guid]::NewGuid().ToString('N'))
  $ca = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
          '--hide-scrollbars',"--window-size=$w,$h","--user-data-dir=$udd",
          "--virtual-time-budget=$budget","--screenshot=$out",$url)
  $p = Start-Process -FilePath $chrome -ArgumentList $ca -PassThru `
        -RedirectStandardOutput (Join-Path $env:TEMP 'fs.out') `
        -RedirectStandardError (Join-Path $env:TEMP 'fs.err')
  if (-not $p.WaitForExit(90000)) {
    Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
      Where-Object { $_.CommandLine -and $_.CommandLine.Contains($udd) } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "    HANG"
  }
  if (Test-Path -LiteralPath $udd) {
    $full = (Resolve-Path -LiteralPath $udd).Path
    if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-fs-') {
      Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  Write-Host ("    {0}  {1} B" -f (Split-Path -Leaf $out), (Get-Item -LiteralPath $out).Length)
}

# ---------------------------------------------------------------- estado LIGADO
Write-Host "=== 1. garante o conserto LIGADO ==="
New-ItemProperty -LiteralPath $k -Name $N1 -Value $fx -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $k -Name $N2 -Value $fi -PropertyType String -Force | Out-Null
EsperaEstado 'RESOLVE' | Out-Null

Write-Host "=== 2. capturas do ENTREGÁVEL (conserto LIGADO, 1920x1080) ==="
foreach ($v in @('compare','tele','bcast','mano','cine','inst')) {
  Shot "file:///H:/aireplay/docs/design/preview.html#$v" (Join-Path $main "preview-fontes-$v.png")
}
Write-Host "=== 3. diagnóstico da página (LIGADO) + espécime ==="
& pwsh -NoProfile -File (Join-Path $main 'font-measure.ps1') -Hash diag-compare -Name depoisfix | Out-Null
Shot 'file:///H:/aireplay/_main/font-fraunces-specimen.html' (Join-Path $main 'font-fraunces-specimen-depois.png') 1400 560 2500

# --------------------------------------------------------------- estado DESLIGADO
Write-Host "=== 4. desliga o conserto e ESPERA que o instrumento o veja ==="
Remove-ItemProperty -LiteralPath $k -Name $N1 -Force
Remove-ItemProperty -LiteralPath $k -Name $N2 -Force
EsperaEstado 'AUSENTE' | Out-Null
Write-Host "=== 5. capturas 'antes' (mesmo instrumento, estado verificado) ==="
$antesDir = Join-Path $main '_fontes-antes-instrumento'
if (-not (Test-Path -LiteralPath $antesDir)) { New-Item -ItemType Directory -Path $antesDir | Out-Null }
foreach ($v in @('compare','tele','bcast','mano','cine','inst')) {
  Shot "file:///H:/aireplay/docs/design/preview.html#$v" (Join-Path $antesDir "preview-fontes-$v.png")
}
& pwsh -NoProfile -File (Join-Path $main 'font-measure.ps1') -Hash diag-compare -Name antesfix | Out-Null
Shot 'file:///H:/aireplay/_main/font-fraunces-specimen.html' (Join-Path $main 'font-fraunces-specimen-antes.png') 1400 560 2500

# ------------------------------------------------------------------ repõe e fecha
Write-Host "=== 6. repõe o conserto e confirma ==="
New-ItemProperty -LiteralPath $k -Name $N1 -Value $fx -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $k -Name $N2 -Value $fi -PropertyType String -Force | Out-Null
EsperaEstado 'RESOLVE' | Out-Null
Shot 'file:///H:/aireplay/_main/font-fraunces-specimen.html' (Join-Path $main 'font-fraunces-specimen-depois2.png') 1400 560 2500
Write-Host "=== fim. estado: $((Get-ItemProperty -LiteralPath $k).$N1) ==="
