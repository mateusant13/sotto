# dwrite-families.ps1 — lista COMPLETA das famílias do DirectWrite e do GDI,
# com as faces de cada família de interesse. Responde "que nomes é que o
# DirectWrite expõe para os ficheiros que instalámos?".
#
# Uso: pwsh -NoProfile -File H:\aireplay\_main\dwrite-families.ps1
$ErrorActionPreference = 'Stop'

$cs = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class DWFam
{
    [DllImport("dwrite.dll", PreserveSig = true)]
    private static extern int DWriteCreateFactory(uint factoryType, ref Guid iid, out IntPtr factory);

    [ComImport, Guid("b859ee5a-d838-4b5b-a2e8-1adc7d93db48"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteFactory
    {
        [PreserveSig] int GetSystemFontCollection(out IDWriteFontCollection collection,
                                                 [MarshalAs(UnmanagedType.Bool)] bool checkForUpdates);
    }

    [ComImport, Guid("a84cee02-3eea-4eee-a827-87c1a02a0fcc"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteFontCollection
    {
        [PreserveSig] uint GetFontFamilyCount();
        [PreserveSig] int GetFontFamily(uint index, out IDWriteFontFamily family);
        [PreserveSig] int FindFamilyName([MarshalAs(UnmanagedType.LPWStr)] string familyName,
                                         out uint index, out int exists);
        [PreserveSig] int GetFontFromFontFace(IntPtr fontFace, out IntPtr font);
    }

    [ComImport, Guid("da20d8ef-812a-4c43-9802-62ec4abd7add"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteFontFamily
    {
        [PreserveSig] int GetFontCollection(out IDWriteFontCollection c);
        [PreserveSig] uint GetFontCount();
        [PreserveSig] int GetFont(uint index, out IDWriteFont font);
        [PreserveSig] int GetFamilyNames(out IDWriteLocalizedStrings names);
        [PreserveSig] int GetFirstMatchingFont(int weight, int stretch, int style, out IDWriteFont font);
    }

    [ComImport, Guid("acd16696-8c14-4f5d-877e-fe3fc1d32737"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteFont
    {
        [PreserveSig] int GetFontFamily(out IDWriteFontFamily family);
        [PreserveSig] int GetWeight(out int weight);
        [PreserveSig] int GetStretch(out int stretch);
        [PreserveSig] int GetStyle(out int style);
        [PreserveSig] int IsSymbolFont();
        [PreserveSig] int GetFaceNames(out IDWriteLocalizedStrings names);
        [PreserveSig] int GetInformationalStrings(int informationalStringID, out IDWriteLocalizedStrings strings, out int exists);
    }

    [ComImport, Guid("08256209-099a-4b34-b86d-c22b110e7771"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteLocalizedStrings
    {
        [PreserveSig] uint GetCount();
        [PreserveSig] int FindLocaleName([MarshalAs(UnmanagedType.LPWStr)] string localeName, out uint index, out int exists);
        [PreserveSig] int GetLocaleNameLength(uint index, out uint length);
        [PreserveSig] int GetLocaleName(uint index, [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, uint size);
        [PreserveSig] int GetStringLength(uint index, out uint length);
        [PreserveSig] int GetString(uint index, [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, uint size);
    }

    private static IDWriteFontCollection _coll;

    public static string Init()
    {
        Guid iid = new Guid("b859ee5a-d838-4b5b-a2e8-1adc7d93db48");
        IntPtr p;
        int hr = DWriteCreateFactory(0, ref iid, out p);
        if (hr != 0) return "DWriteCreateFactory hr=0x" + hr.ToString("X8");
        IDWriteFactory f = (IDWriteFactory)Marshal.GetObjectForIUnknown(p);
        hr = f.GetSystemFontCollection(out _coll, false);
        if (hr != 0) return "GetSystemFontCollection hr=0x" + hr.ToString("X8");
        return null;
    }

    private static string First(IDWriteLocalizedStrings names)
    {
        uint n = names.GetCount();
        if (n == 0) return "(sem nomes)";
        uint len;
        if (names.GetStringLength(0, out len) != 0) return "(erro len)";
        StringBuilder sb = new StringBuilder((int)len + 1);
        if (names.GetString(0, sb, len + 1) != 0) return "(erro str)";
        return sb.ToString();
    }

    public static uint Count() { return _coll.GetFontFamilyCount(); }

    public static string FamilyAt(uint i)
    {
        IDWriteFontFamily fam;
        if (_coll.GetFontFamily(i, out fam) != 0) return "(erro)";
        IDWriteLocalizedStrings nm;
        if (fam.GetFamilyNames(out nm) != 0) return "(erro nomes)";
        return First(nm);
    }

    // família + cada face com o seu (peso, largura, estilo) e o nome da face
    public static string[] FacesAt(uint i)
    {
        IDWriteFontFamily fam;
        if (_coll.GetFontFamily(i, out fam) != 0) return new string[] { "(erro familia)" };
        List<string> l = new List<string>();
        uint n = fam.GetFontCount();
        for (uint j = 0; j < n; j++)
        {
            IDWriteFont fo;
            if (fam.GetFont(j, out fo) != 0) { l.Add("(erro face " + j + ")"); continue; }
            int w, s, st;
            fo.GetWeight(out w); fo.GetStretch(out s); fo.GetStyle(out st);
            IDWriteLocalizedStrings fn;
            string face = "?";
            if (fo.GetFaceNames(out fn) == 0) face = First(fn);
            string full = "";
            IDWriteLocalizedStrings ins; int ex;
            if (fo.GetInformationalStrings(2 /* FULL_NAME */, out ins, out ex) == 0 && ex != 0)
                full = " full=" + First(ins);
            l.Add("    face[" + j + "] wght=" + w + " stretch=" + s + " style=" + st +
                  " faceName=" + face + full);
        }
        return l.ToArray();
    }
}
'@

Add-Type -TypeDefinition $cs -Language CSharp | Out-Null
if ([DWFam]::Init()) { Write-Output "INIT FALHOU"; exit 2 }
$n = [DWFam]::Count()
Write-Output "DIRECTWRITE famílias=$n"

$dwNames = @()
for ($i = 0; $i -lt $n; $i++) { $dwNames += [DWFam]::FamilyAt([uint32]$i) }

Add-Type -AssemblyName System.Drawing
$gdi = New-Object System.Drawing.Text.InstalledFontCollection
$gdiNames = @($gdi.Families | ForEach-Object { $_.Name })

$dwNames | Sort-Object | Set-Content -LiteralPath 'H:\aireplay\_main\fonts-dw.txt' -Encoding utf8
$gdiNames | Sort-Object | Set-Content -LiteralPath 'H:\aireplay\_main\fonts-gdi.txt' -Encoding utf8

Write-Output ""
Write-Output "--- nomes do DirectWrite (todos, $n) ---"
$dwNames | Sort-Object | ForEach-Object { Write-Output "  $_" }
Write-Output ""
Write-Output "--- só no GDI (o que o GDI tem e o DirectWrite não) ---"
(Compare-Object -ReferenceObject $dwNames -DifferenceObject $gdiNames | Where-Object { $_.SideIndicator -eq '=>' }).InputObject | Sort-Object | ForEach-Object { Write-Output "  $_" }
Write-Output ""
Write-Output "--- só no DirectWrite ---"
(Compare-Object -ReferenceObject $dwNames -DifferenceObject $gdiNames | Where-Object { $_.SideIndicator -eq '<=' }).InputObject | Sort-Object | ForEach-Object { Write-Output "  $_" }

Write-Output ""
Write-Output "--- faces das famílias de interesse no DirectWrite ---"
for ($i = 0; $i -lt $n; $i++) {
    $nm = $dwNames[$i]
    if ($nm -match 'Newsreader|Fraunces|Space Grotesk|Barlow|Plex|Ubuntu') {
        Write-Output ("  [{0}] {1}" -f $i, $nm)
        [DWFam]::FacesAt([uint32]$i) | ForEach-Object { Write-Output $_ }
    }
}
