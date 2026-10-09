# Measure the real work area(s) the strip has to live in — no Python, no window.
#
# Why PowerShell: launching `python.exe` from a tool shell puts a visible console
# on the owner's screen (measured before, and the house census names it). This
# reads the same user32 data through Add-Type instead.
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public class SottoMon {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int left, top, right, bottom; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct MONITORINFOEX {
        public int cbSize;
        public RECT rcMonitor;
        public RECT rcWork;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szDevice;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int x, y; }

    public delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdc, ref RECT rect, IntPtr data);

    [DllImport("user32.dll")]
    public static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr clip, MonitorEnumProc proc, IntPtr data);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern bool GetMonitorInfoW(IntPtr hMonitor, ref MONITORINFOEX info);

    [DllImport("user32.dll")]
    public static extern IntPtr MonitorFromPoint(POINT pt, uint flags);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT pt);

    [DllImport("user32.dll")]
    public static extern int GetDpiForSystem();

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int index);
}
'@

$monitors = New-Object System.Collections.ArrayList
$proc = [SottoMon+MonitorEnumProc]{
    param($hMonitor, $hdc, [ref]$rect, $data)
    $mi = New-Object SottoMon+MONITORINFOEX
    $mi.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mi)
    if ([SottoMon]::GetMonitorInfoW($hMonitor, [ref]$mi)) {
        [void]$monitors.Add([pscustomobject]@{
            handle  = [int64]$hMonitor
            device  = $mi.szDevice
            primary = (($mi.dwFlags -band 1) -ne 0)
            monitor = "$($mi.rcMonitor.left),$($mi.rcMonitor.top) $($mi.rcMonitor.right - $mi.rcMonitor.left)x$($mi.rcMonitor.bottom - $mi.rcMonitor.top)"
            work    = "$($mi.rcWork.left),$($mi.rcWork.top) $($mi.rcWork.right - $mi.rcWork.left)x$($mi.rcWork.bottom - $mi.rcWork.top)"
        })
    }
    return $true
}
[void][SottoMon]::EnumDisplayMonitors([IntPtr]::Zero, [IntPtr]::Zero, $proc, [IntPtr]::Zero)

$dpi = [SottoMon]::GetDpiForSystem()
$pt = New-Object SottoMon+POINT
[void][SottoMon]::GetCursorPos([ref]$pt)
$nearest = [SottoMon]::MonitorFromPoint($pt, 2)   # MONITOR_DEFAULTTONEAREST
$primary = [SottoMon]::MonitorFromPoint((New-Object SottoMon+POINT), 1)

"DPI=$dpi scale=$([math]::Round($dpi / 96.0, 4))"
"monitors=$($monitors.Count)"
$monitors | ForEach-Object { "  hwnd=$($_.handle) device=$($_.device) primary=$($_.primary) monitor=[$($_.monitor)] work=[$($_.work)]" }
"cursor=($($pt.x),$($pt.y)) monitor_at_cursor=$([int64]$nearest)"
"primary_monitor=$([int64]$primary)"
"virtual_screen=$([SottoMon]::GetSystemMetrics(0))x$([SottoMon]::GetSystemMetrics(1))"

# The proposed strip numbers, computed here so the receipt carries them.
$mi = New-Object SottoMon+MONITORINFOEX
$mi.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mi)
[void][SottoMon]::GetMonitorInfoW($primary, [ref]$mi)
$w = $mi.rcWork.right - $mi.rcWork.left
$h = $mi.rcWork.bottom - $mi.rcWork.top
$width = [math]::Min(1040, [math]::Max(480, [int][math]::Round($w * 0.62)))
$height = 148
$x = $mi.rcWork.left + [int](($w - $width) / 2)
$y = $mi.rcWork.top + $h - $height - 48
"STRIP width=$width height=$height x=$x y=$y (work=$($w)x$($h)@($($mi.rcWork.left),$($mi.rcWork.top)))"
