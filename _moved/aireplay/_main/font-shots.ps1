# font-shots.ps1 — capturas 1920×1080 das seis vistas de preview.html.
#
# Uso:
#   pwsh -File H:\aireplay\_main\font-shots.ps1 -Suffix ""            # -> preview-fontes-<vista>.png
#   pwsh -File H:\aireplay\_main\font-shots.ps1 -Suffix "antes" -Dir H:\aireplay\_main\_fontes-antes-instrumento
#
# Regras: headless (nunca janela), --user-data-dir próprio em TEMP, espera com
# timeout, e se o Chrome pendurar mata-se SÓ a árvore com este user-data-dir
# (caminho completo do artefacto — nunca uma palavra genérica).
param(
  [string]$Suffix = '',
  [string]$Dir = 'H:\aireplay\_main',
  [int]$BudgetMs = 16000,
  [string[]]$Views = @('compare','tele','bcast','mano','cine','inst')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Dir)) { New-Item -ItemType Directory -Path $Dir | Out-Null }
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'

foreach ($v in $Views) {
  $name = if ($Suffix) { "$Suffix-$v" } else { $v }
  $shot = Join-Path $Dir ("preview-fontes-$v.png")
  $udd  = Join-Path $env:TEMP ('fontes-shot-' + [guid]::NewGuid().ToString('N'))
  $ca = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
          '--hide-scrollbars','--window-size=1920,1080',"--user-data-dir=$udd",
          "--virtual-time-budget=$BudgetMs","--screenshot=$shot",
          "file:///H:/aireplay/docs/design/preview.html#$v")
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $p = Start-Process -FilePath $chrome -ArgumentList $ca -PassThru `
        -RedirectStandardOutput (Join-Path $env:TEMP "$name.out.txt") `
        -RedirectStandardError  (Join-Path $env:TEMP "$name.err.txt")
  $ok = $p.WaitForExit(90000)
  if (-not $ok) {
    $tree = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($udd) }
    foreach ($t in $tree) { Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Output ("HANG  {0,-8} (morto pelo udd, {1} proc)" -f $v, ($tree | Measure-Object).Count)
  }
  $sw.Stop()
  $len = if (Test-Path -LiteralPath $shot) { (Get-Item -LiteralPath $shot).Length } else { -1 }
  $sha = if ($len -gt 0) { (Get-FileHash -LiteralPath $shot -Algorithm SHA256).Hash.Substring(0,16) } else { '-' }
  # INVARIANT CULTURE, on purpose: this box runs pt-BR, whose number group separator is a
  # PERIOD, so `{4:N1}` would render 1024.5 as "1.024,5" - read as one second, meant as a
  # thousand.  `F1` under InvariantCulture prints "1024.5".  Same precedent as
  # all-gates.ps1:356.  Gate: _lane25-locale-number-gate.ps1
  $inv = [System.Globalization.CultureInfo]::InvariantCulture
  Write-Output ("SHOT  {0,-8} {1,9} B  {2}  rc={3} {4}s  {5}" -f $v, $len, $sha, $p.ExitCode, $sw.Elapsed.TotalSeconds.ToString('F1', $inv), $shot)
  if (Test-Path -LiteralPath $udd) {
    $full = (Resolve-Path -LiteralPath $udd).Path
    if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-shot-') {
      Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}
