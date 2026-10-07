# check-default-adapter.ps1 -- which DXGI adapter does DEFAULT D3D11 device creation land on?
#
# Read-only: creates a D3D11 device, asks it which adapter it is, releases it. No capture,
# no screen recorded, no audio device, no window.
#
# WHY THIS EXISTS (2026-10-08): the first draft of docs/research/01-capture-encode.md claimed
# "the default D3D11 adapter must never be assumed to be the NVIDIA one", illustrated with
# `D3D11CreateDevice(NULL, HARDWARE, ...)` returning feature level 0xB000 "for either adapter".
# 0xB000 is D3D_FEATURE_LEVEL_11_0 -- it says NOTHING about vendor. This script measures the
# thing that actually matters (which adapter the NULL-adapter path selects) instead of
# inferring it from a feature level.
#
# Run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File H:\aireplay\_main\check-default-adapter.ps1

$ErrorActionPreference = 'Continue'

$sig = @'
using System;
using System.Runtime.InteropServices;

public static class Ad {
    public delegate int EnumAdapters1Delegate(IntPtr self, uint index, out IntPtr ppAdapter);
    public delegate int GetDesc1Delegate(IntPtr self, IntPtr pDesc);
    public delegate int QIDelegate(IntPtr self, ref Guid riid, out IntPtr ppv);
    public delegate int GetAdapterDelegate(IntPtr self, out IntPtr pAdapter);

    [DllImport("d3d11.dll")]
    public static extern int D3D11CreateDevice(IntPtr pAdapter, int DriverType, IntPtr Software,
        uint Flags, IntPtr pFeatureLevels, uint FeatureLevels, uint SDKVersion,
        out IntPtr ppDevice, out uint pFeatureLevel, out IntPtr ppImmediateContext);

    [DllImport("dxgi.dll")]
    public static extern int CreateDXGIFactory1(ref Guid riid, out IntPtr ppFactory);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct DXGI_ADAPTER_DESC1 {
        public uint VendorId, DeviceId, SubSysId, Revision;
        public UIntPtr DedicatedVideoMemory, DedicatedSystemMemory, SharedSystemMemory;
        public long LuidLow; public int LuidHigh; public uint Flags;
    }
}
'@
Add-Type -TypeDefinition $sig -Language CSharp

function Read-AdapterIdentity([IntPtr]$adapter) {
    if ($adapter -eq [IntPtr]::Zero) { return $null }
    $vt = [Runtime.InteropServices.Marshal]::ReadIntPtr($adapter)
    # IDXGIAdapter1 vtable: 0 QI .. 9 CheckInterfaceSupport, 10 GetDesc1
    $getDesc1 = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer(
        [Runtime.InteropServices.Marshal]::ReadIntPtr($vt, 10 * [IntPtr]::Size),
        [Ad+GetDesc1Delegate])
    # DXGI_ADAPTER_DESC1 layout: 128 wchar Description, then 4 uints, 3 size_t, LUID, uint
    $buf = [Runtime.InteropServices.Marshal]::AllocHGlobal(1024)
    try {
        $hr = $getDesc1.Invoke($adapter, $buf)
        if ($hr -ne 0) { return [pscustomobject]@{ error = ('GetDesc1 hr=0x{0:X8}' -f $hr) } }
        $bytes = New-Object byte[] 1024
        [Runtime.InteropServices.Marshal]::Copy($buf, $bytes, 0, 1024)
        $w = [Text.Encoding]::Unicode.GetString($bytes, 0, 256)
        $z = $w.IndexOf([char]0)
        $name = if ($z -ge 0) { $w.Substring(0, $z) } else { $w }
        $vendor = [Runtime.InteropServices.Marshal]::ReadInt32($buf, 256)
        $device = [Runtime.InteropServices.Marshal]::ReadInt32($buf, 260)
        return [pscustomobject]@{ name = $name; vendor = ('0x{0:X4}' -f $vendor); device_id = ('0x{0:X4}' -f $device) }
    } finally {
        [Runtime.InteropServices.Marshal]::FreeHGlobal($buf)
    }
}

Write-Output '--- adapters enumerated by DXGI ---'
$iidFactory = [Guid]'770aae78-f26f-4dba-a829-253c83d1b387'
$fac = [IntPtr]::Zero
$hr = [Ad]::CreateDXGIFactory1([ref]$iidFactory, [ref]$fac)
if ($hr -ne 0) { Write-Output ('CreateDXGIFactory1 hr=0x{0:X8}' -f $hr); exit 1 }
$fvt = [Runtime.InteropServices.Marshal]::ReadIntPtr($fac)
$enum = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer(
    [Runtime.InteropServices.Marshal]::ReadIntPtr($fvt, 12 * [IntPtr]::Size),
    [Ad+EnumAdapters1Delegate])
for ($i = 0; $i -lt 8; $i++) {
    $ad = [IntPtr]::Zero
    if ($enum.Invoke($fac, [uint32]$i, [ref]$ad) -ne 0) { break }
    $id = Read-AdapterIdentity $ad
    Write-Output ("  index {0}: {1}  vendor={2} device_id={3}" -f $i, $id.name, $id.vendor, $id.device_id)
}

# The actual question: default (NULL adapter, D3D_DRIVER_TYPE_HARDWARE) -> which adapter?
$dev = [IntPtr]::Zero; $ctx = [IntPtr]::Zero; $feat = [uint32]0
$hr = [Ad]::D3D11CreateDevice([IntPtr]::Zero, 1, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, 7,
                              [ref]$dev, [ref]$feat, [ref]$ctx)
Write-Output ("`nD3D11CreateDevice(NULL, D3D_DRIVER_TYPE_HARDWARE) hr=0x{0:X8} feature_level=0x{1:X}" -f $hr, $feat)

if ($hr -eq 0 -and $dev -ne [IntPtr]::Zero) {
    $dvt = [Runtime.InteropServices.Marshal]::ReadIntPtr($dev)
    $qi = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer(
        [Runtime.InteropServices.Marshal]::ReadIntPtr($dvt), [Ad+QIDelegate])
    $iidDev = [Guid]'54ec77fa-1377-44e6-8c32-88fd5f44c84c'   # IDXGIDevice
    $dxgiDev = [IntPtr]::Zero
    $hr2 = $qi.Invoke($dev, [ref]$iidDev, [ref]$dxgiDev)
    if ($hr2 -eq 0 -and $dxgiDev -ne [IntPtr]::Zero) {
        $dvt2 = [Runtime.InteropServices.Marshal]::ReadIntPtr($dxgiDev)
        # IDXGIDevice vtable: 0 QI,1 AddRef,2 Release,3 SetPrivateData,4 SetPrivateDataInterface,
        # 5 GetPrivateData, 6 GetParent, 7 GetAdapter
        $getAdapter = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer(
            [Runtime.InteropServices.Marshal]::ReadIntPtr($dvt2, 7 * [IntPtr]::Size),
            [Ad+GetAdapterDelegate])
        $adp = [IntPtr]::Zero
        $hr3 = $getAdapter.Invoke($dxgiDev, [ref]$adp)
        if ($hr3 -eq 0 -and $adp -ne [IntPtr]::Zero) {
            $id = Read-AdapterIdentity $adp
            Write-Output ("DEFAULT-ADAPTER -> '{0}' vendor={1} device_id={2}" -f $id.name, $id.vendor, $id.device_id)
        } else {
            Write-Output ("GetAdapter failed hr=0x{0:X8}" -f $hr3)
        }
    } else {
        Write-Output ("IDXGIDevice QI failed hr=0x{0:X8}" -f $hr2)
    }
}
