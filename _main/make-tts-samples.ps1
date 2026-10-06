# Plant a SYMMETRIC pt-BR + en-US pair with the SAPI voices this box actually has
# (measured: 'Microsoft Maria Desktop' pt-BR, 'Microsoft Zira Desktop' en-US), so
# the language prompt can be tested against audio whose language is KNOWN.
# Text avoids accents on purpose: Windows PowerShell 5.1 reads a BOM-less .ps1 as
# ANSI, so an accented literal would be mangled before SAPI ever saw it.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$jobs = @(
  @{ voice = 'Microsoft Maria Desktop'; text = 'O radio anunciou que a ponte sobre o rio vai ser interditada na proxima segunda feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.'; out = 'H:\sotto\_main\pt-br-sample.wav' },
  @{ voice = 'Microsoft Zira Desktop';  text = 'The radio announced that the bridge over the river will be closed next Monday. Residents need an alternative route to get to work.'; out = 'H:\sotto\_main\en-us-sample.wav' }
)

foreach ($j in $jobs) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice($j.voice)
  $s.Rate = -1
  $s.SetOutputToWaveFile($j.out)
  $s.Speak($j.text)
  $s.Dispose()
  $len = (Get-Item $j.out).Length
  Write-Output ("made {0} ({1} bytes) voice={2}" -f $j.out, $len, $j.voice)
}
