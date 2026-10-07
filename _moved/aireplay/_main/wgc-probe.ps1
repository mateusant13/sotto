# wgc-probe.ps1 -- API-surface check for Windows.Graphics.Capture on this host.
#
# READ-ONLY with respect to the machine: it instantiates NO capture session, records no
# screen, opens no audio device and creates no window. It only reflects the WinRT type
# surface that the shipped recorder would be built against.
#
# Run:  powershell.exe -NoProfile -ExecutionPolicy Bypass -File H:\aireplay\_main\wgc-probe.ps1
#
# HISTORY (2026-10-08): first written inline while researching 01-capture-encode; the
# behaviour below is what produced the MEASURED lines cited in
# docs/research/01-capture-encode.md and receipts/receipt-01-capture-encode.md.

$ErrorActionPreference = 'Continue'

function Show-Names($label, $type, $pattern) {
    try {
        $methods = $type.GetMethods() | ForEach-Object { $_.Name }
        $names = if ($pattern) { $methods | Where-Object { $_ -match $pattern } } else { $methods }
        $names = ($names | Sort-Object -Unique) -join ','
        Write-Output ("{0}: {1}" -f $label, $names)
    } catch {
        Write-Output ("{0}-FAIL: {1}" -f $label, $_.Exception.Message)
    }
}

# 1. Is capture supported at all on this device?
try {
    $session = [Windows.Graphics.Capture.GraphicsCaptureSession, Windows.Graphics.Capture, ContentType=WindowsRuntime]
    $isSupported = $session.GetMethod('IsSupported', [System.Reflection.BindingFlags]'Public,Static')
    Write-Output ("WGC-IsSupported = {0}" -f $isSupported.Invoke($null, @()))
} catch {
    Write-Output ("WGC-PROBE-FAIL: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
}

# 2. The frame pool: does the pool we need exist here (incl. the free-threaded variant)?
Show-Names 'FramePool' ([Windows.Graphics.Capture.Direct3D11CaptureFramePool, Windows.Graphics.Capture, ContentType=WindowsRuntime]) 'Create|Recreate|TryGetNextFrame'

# 3. The capture ITEM: TryCreateFromWindowId / TryCreateFromDisplayId are what let a
#    recorder pick a source PROGRAMMATICALLY, with no picker UI and no consent dialog.
Show-Names 'CaptureItem' ([Windows.Graphics.Capture.GraphicsCaptureItem, Windows.Graphics.Capture, ContentType=WindowsRuntime]) $null

# 4. Session knobs: the border question (see doc section 4d).
Show-Names 'SessionMembers' ([Windows.Graphics.Capture.GraphicsCaptureSession, Windows.Graphics.Capture, ContentType=WindowsRuntime]) 'Border|Cursor|IsSupported|StartCapture'

try {
    $kind = [Windows.Graphics.Capture.GraphicsCaptureAccessKind, Windows.Graphics.Capture, ContentType=WindowsRuntime]
    Write-Output ("AccessKind values: {0}" -f (([Enum]::GetNames($kind)) -join ','))
} catch {
    Write-Output ("AccessKind-FAIL: {0}" -f $_.Exception.Message)
}
