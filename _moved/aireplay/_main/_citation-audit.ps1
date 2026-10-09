param([string]$OutFile = "H:\sotto\_moved\aireplay\_main\_citation-audit.txt")
# CITATION-AUDIT: re-open EVERY url cited in research/*.md and assert the exact quoted
# claim is present in the fetched page. A citation that does not assert is a defect.
# Usage: pwsh -NoProfile -File _main\_citation-audit.ps1
$ErrorActionPreference = 'Continue'
$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'

$cases = @(
  @{ id='N1'; url='https://www.nvidia.com/en-us/software/nvidia-app/';                 needle='DVR-style Instant Replay' }
  @{ id='N1b'; url='https://www.nvidia.com/en-us/software/nvidia-app/';               needle='last 30 seconds' }
  @{ id='N1c'; url='https://www.nvidia.com/en-us/software/nvidia-app/';               needle='8K HDR at 30 fps' }
  @{ id='N1d'; url='https://www.nvidia.com/en-us/software/nvidia-app/';               needle='noise and room echo removal' }
  @{ id='N1e'; url='https://www.nvidia.com/en-us/software/nvidia-app/';               needle='clutch kills' }
  @{ id='N2'; url='https://web.archive.org/web/20260110141314/https://nvidia.custhelp.com/app/answers/detail/a_id/4811'; needle='Save last [user defined] mins/seconds recorded' }
  @{ id='N2b'; url='https://web.archive.org/web/20260110141314/https://nvidia.custhelp.com/app/answers/detail/a_id/4811'; needle='Toggle Instant Replay on/off' }
  @{ id='N2c'; url='https://web.archive.org/web/20260110141314/https://nvidia.custhelp.com/app/answers/detail/a_id/4811'; needle='Ctrl+Shift+0' }
  @{ id='N3'; url='https://web.archive.org/web/20250814145634/https://nvidia.custhelp.com/app/answers/detail/a_id/5084/~/nvidia-app-in-game-performance-and-latency-overlay'; needle='Alt+Shift+R' }
  @{ id='N3b'; url='https://web.archive.org/web/20250814145634/https://nvidia.custhelp.com/app/answers/detail/a_id/5084/~/nvidia-app-in-game-performance-and-latency-overlay'; needle='Alt+R to toggle the statistics overlay' }
  @{ id='N4'; url='https://web.archive.org/web/20220521021516/https://nvidia.custhelp.com/app/answers/detail/a_id/4813'; needle='automatically capture key moments, clutch kills, and match-winning plays' }
  @{ id='N5'; url='https://web.archive.org/web/20251101185332/https://nvidia.custhelp.com/app/answers/detail/a_id/4814'; needle='encoded in H.264 and saved as MP4 files' }
  @{ id='N6'; url='https://web.archive.org/web/20220119113109/https://nvidia.custhelp.com/app/answers/detail/a_id/3328'; needle='black bars are added' }
  @{ id='M1'; url='https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model'; needle='bypass desktop composition entirely' }
  @{ id='M1b'; url='https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model'; needle='Instead of using the DWM swapchain to display on the screen, the application swapchain is used' }
  # NEEDLE NOTE (learned from the FIRST run, which reported L1 FAIL): stripping tags from
  # ffmpeg.org/legal.html collapses "GNU Lesser General Public License" to "LesserGeneral",
  # so the full phrase is not a stable needle. Assert the tag-safe tail instead.
  @{ id='L1'; url='https://ffmpeg.org/legal.html'; needle='LGPL) version 2.1 or later' }
  @{ id='L1b'; url='https://ffmpeg.org/legal.html'; needle='If those parts get used the GPL applies to all of FFmpeg' }
  @{ id='G1'; url='https://api.github.com/repos/tauri-apps/global-hotkey'; needle='"spdx_id": "Apache-2.0"' }
  @{ id='G2'; url='https://api.github.com/repos/obsproject/obs-studio'; needle='"spdx_id": "GPL-2.0"' }
  @{ id='G3'; url='https://api.github.com/repos/microsoft/windows-rs'; needle='"spdx_id": "Apache-2.0"' }
  @{ id='C1'; url='https://crates.io/api/v1/crates/global-hotkey'; needle='"max_version":"0.8.0"' }
  @{ id='C2'; url='https://crates.io/api/v1/crates/windows'; needle='"max_version":"0.62.2"' }
  @{ id='X1'; url='https://api.github.com/repos/obsproject/graphicscapture'; needle='Not Found' }
  @{ id='X2'; url='https://crates.io/api/v1/crates/transparency'; needle='crate' }  # expect it NOT to contain "crate"
  @{ id='X3'; url='https://api.github.com/repos/onlyon64/transparency'; needle='Not Found' }
)

$lines = @("CITATION-AUDIT  run $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')", "")
$pass = 0; $fail = 0
foreach ($c in $cases) {
  $h = & curl.exe -sL --max-time 90 -A $ua -H "User-Agent: $ua" $c.url 2>$null
  $s = ($h -join '') -replace '<[^>]+>', ' ' -replace '\s+', ' '
  $found = $s.Contains($c.needle)
  # X2 is an inverted case: it must NOT resolve to a crate
  if ($c.id -eq 'X2') {
    $isMissing = ($s -match '"errors"' -or $s -notmatch '"crate"')
    $ok = $isMissing
    $lines += ("{0,-5} {1,-6} {2}" -f $c.id, $(if($ok){'PASS'}else{'FAIL'}), "INVERTED: crates.io/transparency must NOT exist")
  } else {
    $ok = $found
    $lines += ("{0,-5} {1,-6} bytes={2,-8} needle='{3}'" -f $c.id, $(if($ok){'PASS'}else{'FAIL'}), $s.Length, $c.needle)
  }
  if ($ok) { $pass++ } else { $fail++; $lines += ("        URL: " + $c.url) }
  Start-Sleep -Seconds 2
}
$lines += ""
$lines += ("CASES={0}  PASS={1}  FAIL={2}" -f $cases.Count, $pass, $fail)
$lines += ("VERDICT " + $(if ($fail -eq 0) { 'PASS - every citation asserts its claim' } else { "FAIL - $fail citation(s) do not assert" }))
$lines | Set-Content -Path $OutFile -Encoding UTF8
$lines | ForEach-Object { $_ }
