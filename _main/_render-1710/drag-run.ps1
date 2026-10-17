param([Parameter(Mandatory=$true)][string]$Tree)
$ErrorActionPreference = 'Stop'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$page = Join-Path $Tree 'app\panel\drag-test.html'
$src  = 'H:\sotto\_main\_render-1710\drag-test.html'
Copy-Item $src $page -Force
$u = 'file:///' + ($page -replace '\\', '/')
$a = @('--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
       '--user-data-dir=H:\sotto\_main\_render-1710\edgeprof2',
       '--virtual-time-budget=4000', '--dump-dom', $u)
$d = & $edge @a 2>$null | Out-String
if ($d -match '(?s)DRAG-RESULTS(.*?)</pre>') { $matches[1] } else { 'NO RESULTS' }