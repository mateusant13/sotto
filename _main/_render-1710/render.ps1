param(
  [Parameter(Mandatory=$true)][string]$Url,
  [Parameter(Mandatory=$true)][string]$Out,
  [int]$Width = 380,
  [int]$Height = 900
)
$ErrorActionPreference = 'Stop'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if (-not (Test-Path $edge)) { throw "edge not found: $edge" }
$prof = Join-Path 'H:\sotto\_main\_render-1710' ('edgeprof-' + [IO.Path]::GetRandomFileName())
if (Test-Path $Out) { Remove-Item -LiteralPath $Out -Force }
$args = @(
  '--headless=new',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-extensions',
  '--hide-scrollbars',
  '--force-device-scale-factor=1',
  "--user-data-dir=$prof",
  "--window-size=$Width,$Height",
  '--virtual-time-budget=6000',
  "--screenshot=$Out",
  $Url
)
$p = Start-Process -FilePath $edge -ArgumentList $args -WindowStyle Hidden -PassThru -Wait
if (Test-Path $prof) { Remove-Item -Recurse -Force -LiteralPath $prof -ErrorAction SilentlyContinue }
if (-not (Test-Path $Out)) { throw "screenshot not produced (exit $($p.ExitCode))" }
$i = Get-Item $Out
"rendered $($i.FullName) $($i.Length) B"