param([Parameter(Mandatory=$true)][string]$Url, [string]$OutFile)
# Fetch a page (incl. web.archive.org) and reduce it to the visible article TEXT.
# Usage: pwsh -File _main\_fetch-nv.ps1 -Url "<url>" -OutFile "<file>"
$ErrorActionPreference = 'Stop'
$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
$html = & curl.exe -sL --max-time 90 -A $ua $Url
$rc = $LASTEXITCODE
if ($rc -ne 0) { Write-Output "CURL_RC=$rc"; exit $rc }
$s = ($html -join "`n")
# drop <script>...</script>, <style>...</style>, and any base64 data: URIs (they are enormous)
$s = [regex]::Replace($s, '(?is)<script.*?</script>', ' ')
$s = [regex]::Replace($s, '(?is)<style.*?</style>', ' ')
$s = [regex]::Replace($s, '(?is)url\(&quot;data:image/[\s\S]*?&quot;\)', ' ')
$s = [regex]::Replace($s, '(?is)background-image:\s*url\([^)]*\)', ' ')
$s = [regex]::Replace($s, '(?is)<!--.*?-->', ' ')
# keep the block structure readable
$s = [regex]::Replace($s, '(?i)</(p|div|li|tr|h1|h2|h3|h4|br)>', "`n")
$s = [regex]::Replace($s, '(?i)<br\s*/?>', "`n")
$s = [regex]::Replace($s, '(?s)<[^>]+>', ' ')
$s = [System.Net.WebUtility]::HtmlDecode($s)
$lines = $s -split "`n" | ForEach-Object { ($_ -replace '\s+', ' ').Trim() } | Where-Object { $_ -ne '' }
$out = ($lines -join "`n")
Set-Content -Path $OutFile -Value $out -Encoding UTF8
Write-Output ("WROTE {0} chars={1} lines={2}" -f $OutFile, $out.Length, $lines.Count)