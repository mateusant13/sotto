<#
  font-measure.ps1 — corre o Chrome headless sobre a PRÓPRIA página
  (docs/design/preview.html#<hash>), guarda o DOM, tira <script>/<style>,
  tira as tags e escreve o texto do diagnóstico (typobar + #selfcheck) num .txt.

  Uso:
    pwsh -File H:\aireplay\_main\font-measure.ps1 -Hash diag-compare -BudgetMs 16000
    pwsh -File H:\aireplay\_main\font-measure.ps1 -Hash tele -Name tele -BudgetMs 16000 -Shot

  Regras da casa respeitadas: headless (nunca janela visível), --user-data-dir
  próprio em TEMP (não toca no perfil do dono), -LiteralPath em todos os
  ficheiros, e o user-data-dir é verificado ANTES de ser apagado.
#>
param(
  [Parameter(Mandatory=$true)][string]$Hash,
  [string]$Name = '',
  [int]$BudgetMs = 16000,
  [switch]$Shot
)
$ErrorActionPreference = 'Stop'

$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$main   = 'H:\aireplay\_main'
$root   = 'H:\aireplay'
if (-not $Name) { $Name = $Hash }

$udd = Join-Path $env:TEMP ('fontes-udd-' + [guid]::NewGuid().ToString('N'))
$url = 'file:///H:/aireplay/docs/design/preview.html#' + $Hash

$dom = Join-Path $main ("font-dom-$Name.html")
$err = Join-Path $main ("font-dom-$Name.err.txt")
$txt = Join-Path $main ("font-diag-$Name.txt")

$cargs = @(
  '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--disable-extensions','--disable-background-networking','--disable-sync',
  '--allow-file-access-from-files',
  '--window-size=1920,1080',
  "--user-data-dir=$udd",
  "--virtual-time-budget=$BudgetMs"
)
$shotPath = $null
if ($Shot) {
  $shotPath = Join-Path $main ("preview-fontes-$Name.png")
  $cargs += "--screenshot=$shotPath"
}
$cargs += @('--dump-dom', $url)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
# Chrome é um binário de subsistema GUI: com `& exe` o PowerShell NÃO espera por
# ele, fecha o descritor do stdout e o dump sai com 0 bytes (medido). Obrigatório
# Start-Process -Wait, que espera e gere os descritores.
$proc = Start-Process -FilePath $chrome -ArgumentList $cargs `
        -RedirectStandardOutput $dom -RedirectStandardError $err -Wait -PassThru
$rc = $proc.ExitCode
$sw.Stop()

$rawLen = 0
for ($i = 0; $i -lt 40; $i++) {
  try { $rawLen = (Get-Item -LiteralPath $dom).Length; break }
  catch { Start-Sleep -Milliseconds 250 }
}
if ($rawLen -eq 0) { throw "dom vazio/inalcançável: $dom" }

# ---- limpeza: fora <script>/<style>, fora tags, decodifica entidades ----
$t = [System.IO.File]::ReadAllText($dom)
$t = [regex]::Replace($t, '(?s)<script\b.*?</script>', ' ')
$t = [regex]::Replace($t, '(?s)<style\b.*?</style>', ' ')
$t = [regex]::Replace($t, '(?s)<!--.*?-->', ' ')
$t = [regex]::Replace($t, '<[^>]*>', ' ')
$t = [System.Net.WebUtility]::HtmlDecode($t)
$t = [regex]::Replace($t, '[ \t]+', ' ')
$lines = $t -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }

$out = New-Object System.Collections.Generic.List[string]
$out.Add("# font-measure  hash=$Hash name=$Name budget=${BudgetMs}ms rc=$rc bytes=$rawLen elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,1))s")
$out.Add("# url=$url")

# linhas de família: as do #diag ("<vista>: painel ... fonte declarada X (instalada|AUSENTE...)")
foreach ($l in $lines) { if ($l -match 'fonte declarada') { $out.Add('FAM | ' + $l) } }
# barra de tipografia
foreach ($l in $lines) { if ($l -match 'Teleprompter' -or $l -match 'controlo do detector') { $out.Add('TYPO | ' + $l) } }
# veredicto
foreach ($l in $lines) { if ($l -match 'DIAG · vista' -or $l -match 'auto-teste') { $out.Add('VERD | ' + $l) } }

$out -join "`n" | Set-Content -LiteralPath $txt -Encoding utf8

# ---- limpa o user-data-dir (verificado) ----
if (Test-Path -LiteralPath $udd) {
  $full = (Resolve-Path -LiteralPath $udd).Path
  if ($full.StartsWith($env:TEMP, [System.StringComparison]::OrdinalIgnoreCase) -and $full -match 'fontes-udd-') {
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
  } else { Write-Output "NAO APAGUEI (fora do TEMP): $full" }
}

Write-Output ($out -join "`n")
if ($shotPath) { Write-Output ("SHOT | {0} {1} B" -f $shotPath, (Get-Item -LiteralPath $shotPath).Length) }
