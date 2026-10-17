param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string]$Tag,
  [string]$Hash = ''
)
$ErrorActionPreference = 'Stop'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$panel = Join-Path $Root 'app\panel\panel.html'
$url = 'file:///' + ($panel -replace '\\', '/')
$a = @('--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
       '--disable-extensions', '--hide-scrollbars', '--force-device-scale-factor=1',
       '--user-data-dir=H:\sotto\_main\_render-1710\edgeprof', '--window-size=380,900',
       '--virtual-time-budget=6000', '--dump-dom', ($url + $Hash))
$d = & $edge @a 2>$null | Out-String
if ($d -match '(?s)PROBE-OUT">(.*?)</pre>') {
  $j = $matches[1] | ConvertFrom-Json
  "== $Tag =="
  "theme            : $($j.theme)"
  "panel box-shadow : $($j.panel.boxShadow)"
  "panel radius     : $($j.panel.borderRadius)"
  "html radius      : $($j.html.borderRadius)   html bg: $($j.html.background)"
  "grip rect        : $($j.grip.rect)"
  "grip background  : $($j.gripBg)"
} else {
  "== $Tag == PROBE-OUT missing"
}