$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
Write-Output ("ENGINE: " + $engine.RecognizerLanguage.LanguageTag)
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function AwaitOp($op) {
  $t = $asTask.MakeGenericMethod($op.GetType().GenericTypeArguments[0]).Invoke($null, @($op))
  $t.Wait(-1) | Out-Null
  return $t.Result
}
$src = "H:\sotto\docs\design\incoming\design-3.png"
$img = [System.Drawing.Image]::FromFile($src)
$W = $img.Width; $H = $img.Height
$scale = 2.0; $bandH = 300; $overlap = 40; $y = 0
$out = New-Object System.Text.StringBuilder
while ($y -lt $H) {
  $bh = [Math]::Min($bandH, $H - $y)
  $bmp = New-Object System.Drawing.Bitmap([int]($W*$scale)), ([int]($bh*$scale))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($img, (New-Object System.Drawing.Rectangle(0,0,[int]($W*$scale),[int]($bh*$scale))), (New-Object System.Drawing.Rectangle(0,$y,$W,$bh)), [System.Drawing.GraphicsUnit]::Pixel)
  $g.Dispose()
  $ms = New-Object System.IO.MemoryStream
  $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  $bytes = $ms.ToArray(); $ms.Dispose()
  $ras = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  $dw = New-Object Windows.Storage.Streams.DataWriter($ras)
  $dw.WriteBytes($bytes)
  $st = $dw.StoreAsync(); $st.AsTask().Wait(-1) | Out-Null
  $fl = $dw.FlushAsync(); $fl.AsTask().Wait(-1) | Out-Null
  $ras.Seek(0)
  $op = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)
  $dec = AwaitOp $op
  $op2 = $dec.GetSoftwareBitmapAsync(); $sb = AwaitOp $op2
  $op3 = $engine.RecognizeAsync($sb); $res = AwaitOp $op3
  foreach ($ln in $res.Lines) {
    $mn = 99999
    foreach ($wd in $ln.Words) { $mn = [Math]::Min($mn, $wd.BoundingRect.Top) }
    [void]$out.AppendLine(("y={0,4}  {1}" -f [int]($y + $mn/$scale), $ln.Text))
  }
  $ras.Dispose(); $sb.Dispose()
  if ($bh -lt $bandH) { break }
  $y += ($bandH - $overlap)
}
$img.Dispose()
$out.ToString() | Set-Content -Path 'H:\sotto\_main\_design-lane\ocr-3.txt' -Encoding UTF8
Write-Output "OK"
