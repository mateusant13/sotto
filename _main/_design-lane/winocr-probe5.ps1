$ErrorActionPreference='Stop'
try {
  [void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
  $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
  Write-Output "OCR-OK"
  foreach ($l in $langs) { Write-Output ("  " + $l.LanguageTag + "  " + $l.DisplayName) }
} catch { Write-Output ("WINOCR-FAIL: " + $_.Exception.Message) }
