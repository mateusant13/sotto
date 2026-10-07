# font-crop-diff.ps1 — compara duas PNG pixel a pixel, opcionalmente numa
# região, e diz ONDE é que diferem (caixa + grelha 12×8). Também grava os
# recortes, para se poder olhar para eles.
#
# Uso:
#   pwsh -File font-crop-diff.ps1 -A x.png -B y.png
#   pwsh -File font-crop-diff.ps1 -A x.png -B y.png -X 0 -Y 0 -W 1920 -H 150 -CropA a.png -CropB b.png
param(
  [Parameter(Mandatory=$true)][string]$A,
  [Parameter(Mandatory=$true)][string]$B,
  [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0,
  [int]$Thresh = 10,
  [string]$CropA = '', [string]$CropB = '', [string]$DiffOut = ''
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$ia = [System.Drawing.Image]::FromFile($A)
$ib = [System.Drawing.Image]::FromFile($B)
if ($W -le 0) { $W = [Math]::Min($ia.Width, $ib.Width) }
if ($H -le 0) { $H = [Math]::Min($ia.Height, $ib.Height) }
$W = [Math]::Min($W, [Math]::Min($ia.Width, $ib.Width) - $X)
$H = [Math]::Min($H, [Math]::Min($ia.Height, $ib.Height) - $Y)

$ba = New-Object System.Drawing.Bitmap $ia
$bb = New-Object System.Drawing.Bitmap $ib
# ATENÇÃO: $X/$Y são nomes de parâmetro e PowerShell é insensível a maiúsculas —
# os ciclos abaixo usam $px/$py para não os destruírem. Guarda-se o rectângulo.
$X0 = $X; $Y0 = $Y; $W0 = $W; $H0 = $H
$rect = New-Object System.Drawing.Rectangle $X, $Y, $W, $H
$ca = $ba.Clone($rect, $ba.PixelFormat)
$cb = $bb.Clone($rect, $bb.PixelFormat)
if ($CropA) { $ca.Save($CropA, [System.Drawing.Imaging.ImageFormat]::Png) }
if ($CropB) { $cb.Save($CropB, [System.Drawing.Imaging.ImageFormat]::Png) }

$diff = $null
if ($DiffOut) { $diff = New-Object System.Drawing.Bitmap $W, $H }

$count = 0; $minX = [int]::MaxValue; $minY = [int]::MaxValue; $maxX = -1; $maxY = -1
$grid = New-Object 'int[,]' 12, 8
for ($py = 0; $py -lt $H; $py++) {
  for ($px = 0; $px -lt $W; $px++) {
    $pa = $ca.GetPixel($px, $py); $pb = $cb.GetPixel($px, $py)
    $d = [Math]::Max([Math]::Abs($pa.R - $pb.R),
         [Math]::Max([Math]::Abs($pa.G - $pb.G), [Math]::Abs($pa.B - $pb.B)))
    if ($d -gt $Thresh) {
      $count++
      if ($px -lt $minX) { $minX = $px }; if ($px -gt $maxX) { $maxX = $px }
      if ($py -lt $minY) { $minY = $py }; if ($py -gt $maxY) { $maxY = $py }
      $grid[[Math]::Min(11, [int]($px * 12 / $W)), [Math]::Min(7, [int]($py * 8 / $H))]++
    }
    if ($diff) { $diff.SetPixel($px, $py, $(if ($d -gt $Thresh) { [System.Drawing.Color]::FromArgb(255,255,0,0) } else { [System.Drawing.Color]::FromArgb(255,20,22,26) })) }
  }
}
if ($diff) { $diff.Save($DiffOut, [System.Drawing.Imaging.ImageFormat]::Png); $diff.Dispose() }

Write-Output ("A={0}  {1}x{2}" -f (Split-Path -Leaf $A), $ia.Width, $ia.Height)
Write-Output ("B={0}  {1}x{2}" -f (Split-Path -Leaf $B), $ib.Width, $ib.Height)
Write-Output ("regiao: x={0} y={1} {2}x{3}  limiar>{4}" -f $X0, $Y0, $W0, $H0, $Thresh)
Write-Output ("pixeis diferentes: {0} de {1} ({2:N3}%)" -f $count, ($W * $H), (100.0 * $count / ($W * $H)))
if ($count -gt 0) { Write-Output ("caixa da diferenca: x {0}..{1}  y {2}..{3}" -f $minX, $maxX, $minY, $maxY) }
Write-Output "grelha 12x8 (contagem por celula):"
for ($gy = 0; $gy -lt 8; $gy++) {
  $row = @()
  for ($gx = 0; $gx -lt 12; $gx++) { $row += ("{0,7}" -f $grid[$gx, $gy]) }
  Write-Output ("  " + ($row -join ''))
}
$ca.Dispose(); $cb.Dispose(); $ba.Dispose(); $bb.Dispose(); $ia.Dispose(); $ib.Dispose()
