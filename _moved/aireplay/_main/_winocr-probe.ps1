# _winocr-probe.ps1 - MEASURE Windows.Media.Ocr (the Windows built-in OCR engine)
# Runs under Windows PowerShell 5.1 (WinRT projection is available there).
# No downloads, no window, no screen capture: it reads the synthetic PNGs in
# H:\aireplay\_main\ocr-frames\ that ocr_frames.py generated.
$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}

[void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Storage.StorageFile,Windows.Foundation,ContentType=WindowsRuntime]

Write-Output "== ENGINE =="
foreach ($l in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
  Write-Output ("AVAILABLE " + $l.LanguageTag + " | " + $l.DisplayName)
}
$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($eng -eq $null) { Write-Output "USER-PROFILE ENGINE NULL (no OCR language installed for the user)"; }
else { Write-Output ("USER-PROFILE ENGINE " + $eng.RecognizerLanguage.LanguageTag) }

$engPt = $null
try {
  $lang = New-Object Windows.Globalization.Language "pt-BR"
  $engPt = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
} catch { Write-Output ("TRYCREATEFROMLANGUAGE ERR " + $_.Exception.Message) }
if ($engPt -eq $null) { Write-Output "pt-BR ENGINE NULL" } else { Write-Output ("pt-BR ENGINE " + $engPt.RecognizerLanguage.LanguageTag) }

# does an en-US engine exist? (asked for deliberately, likely absent)
$engEn = $null
try {
  $langEn = New-Object Windows.Globalization.Language "en-US"
  $engEn = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langEn)
} catch { Write-Output ("EN ERR " + $_.Exception.Message) }
if ($engEn -eq $null) { Write-Output "en-US ENGINE NULL" } else { Write-Output ("en-US ENGINE " + $engEn.RecognizerLanguage.LanguageTag) }

Write-Output ("MAXDIMENSION " + [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)

foreach ($engineKind in @("pt-BR")) {
  $engine = $engPt
  if ($engine -eq $null) { continue }
  Write-Output ("== ARM engine=" + $engineKind + " ==")
  foreach ($item in (Get-ChildItem "H:\aireplay\_main\ocr-frames\*.png" | Sort-Object Name)) {
    Write-Output ("--- FRAME " + $item.Name)
    try {
      $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($item.FullName)) ([Windows.Storage.StorageFile])
      $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
      $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
      $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
      Write-Output ("DIM " + $bitmap.PixelWidth + "x" + $bitmap.PixelHeight)
      $sw = [System.Diagnostics.Stopwatch]::StartNew()
      $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
      $sw.Stop()
      Write-Output ("MS " + $sw.ElapsedMilliseconds)
      $n = 0
      foreach ($line in $res.Lines) {
        $n++
        $ws = @()
        foreach ($w in $line.Words) { $ws += $w.Text }
        Write-Output ("LINE " + $n + " | " + $line.Text + " | words=" + $ws.Count)
      }
      Write-Output ("NLINES " + $n)
      $stream.Dispose()
    } catch {
      Write-Output ("FRAME ERROR " + $_.Exception.Message)
    }
  }
}
Write-Output "== DONE =="
