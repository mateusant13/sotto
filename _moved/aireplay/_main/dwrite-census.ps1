# dwrite-census.ps1 — pergunta ao DIRECTWRITE (o backend de fontes do Chromium
# no Windows) que famílias ele tem, e compara com o GDI.
#
# Porque é que isto existe: o Chromium no Windows NÃO enumera fontes por GDI,
# usa IDWriteFactory::GetSystemFontCollection + FindFamilyName (skia). Uma
# família que o GDI vê e o DirectWrite não é exactamente o defeito medido.
#
# Uso: pwsh -NoProfile -File H:\aireplay\_main\dwrite-census.ps1
$ErrorActionPreference = 'Stop'

$cs = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class DWriteCensus
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

    // IDWriteFontFamily deriva de IDWriteFontList: os slots da base vêm PRIMEIRO.
    [ComImport, Guid("da20d8ef-812a-4c43-9802-62ec4abd7add"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteFontFamily
    {
        [PreserveSig] int GetFontCollection(out IDWriteFontCollection c);   // IDWriteFontList
        [PreserveSig] uint GetFontCount();                                  // IDWriteFontList
        [PreserveSig] int GetFont(uint index, out IntPtr font);             // IDWriteFontList
        [PreserveSig] int GetFamilyNames(out IDWriteLocalizedStrings names);
        [PreserveSig] int GetFirstMatchingFont(int weight, int stretch, int style, out IntPtr font);
    }

    [ComImport, Guid("08256209-099a-4b34-b86d-c22b110e7771"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDWriteLocalizedStrings
    {
        [PreserveSig] uint GetCount();
        [PreserveSig] int FindLocaleName([MarshalAs(UnmanagedType.LPWStr)] string localeName,
                                         out uint index, out int exists);
        [PreserveSig] int GetLocaleNameLength(uint index, out uint length);
        [PreserveSig] int GetLocaleName(uint index, [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, uint size);
        [PreserveSig] int GetStringLength(uint index, out uint length);
        [PreserveSig] int GetString(uint index, [Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, uint size);
    }

    private static IDWriteFactory _factory;
    private static IDWriteFontCollection _coll;

    public static string Init()
    {
        Guid iid = new Guid("b859ee5a-d838-4b5b-a2e8-1adc7d93db48");
        IntPtr p;
        int hr = DWriteCreateFactory(0 /* SHARED */, ref iid, out p);
        if (hr != 0) return "DWriteCreateFactory hr=0x" + hr.ToString("X8");
        _factory = (IDWriteFactory)Marshal.GetObjectForIUnknown(p);
        hr = _factory.GetSystemFontCollection(out _coll, false);
        if (hr != 0) return "GetSystemFontCollection hr=0x" + hr.ToString("X8");
        return null;
    }

    public static uint FamilyCount() { return _coll.GetFontFamilyCount(); }

    private static string FamilyName(uint i)
    {
        IDWriteFontFamily fam;
        if (_coll.GetFontFamily(i, out fam) != 0) return null;
        IDWriteLocalizedStrings names;
        if (fam.GetFamilyNames(out names) != 0) return null;
        uint n = names.GetCount();
        if (n == 0) return null;
        uint len;
        if (names.GetStringLength(0, out len) != 0) return null;
        StringBuilder sb = new StringBuilder((int)len + 1);
        if (names.GetString(0, sb, len + 1) != 0) return null;
        return sb.ToString();
    }

    // Toda a lista, para se poder procurar por substring (GDI pode ter nomes
    // que o DirectWrite não tem e vice-versa).
    public static string[] AllNames()
    {
        uint n = _coll.GetFontFamilyCount();
        List<string> l = new List<string>((int)n);
        for (uint i = 0; i < n; i++)
        {
            string s = FamilyName(i);
            l.Add(s == null ? "(erro@" + i + ")" : s);
        }
        return l.ToArray();
    }

    // O caminho EXACTO que o skia/Chromium usa: FindFamilyName.
    public static string Find(string name)
    {
        uint idx; int exists;
        int hr = _coll.FindFamilyName(name, out idx, out exists);
        if (hr != 0) return "hr=0x" + hr.ToString("X8");
        if (exists == 0) return "AUSENTE";
        IDWriteFontFamily fam;
        if (_coll.GetFontFamily(idx, out fam) != 0) return "existe(index=" + idx + ") mas GetFontFamily falhou";
        return "PRESENTE index=" + idx + " faces=" + fam.GetFontCount();
    }
}
'@

Add-Type -TypeDefinition $cs -Language CSharp | Out-Null
$init = [DWriteCensus]::Init()
if ($init) { Write-Output "INIT FALHOU: $init"; exit 2 }

$all = [DWriteCensus]::AllNames()
Write-Output ("DIRECTWRITE  famílias no system font collection: {0}" -f $all.Count)

$targets = @('Newsreader', 'Newsreader 16pt', 'Fraunces', 'Space Grotesk', 'Space Grotesk Light',
             'Barlow Condensed', 'IBM Plex Mono', 'Georgia', 'Times New Roman')
Write-Output ""
Write-Output "FindFamilyName (o caminho que o Chromium/skia usa):"
foreach ($t in $targets) { Write-Output ("  {0,-20} -> {1}" -f $t, [DWriteCensus]::Find($t)) }

Write-Output ""
Write-Output "Famílias do DirectWrite que contêm Newsreader/Fraunces/Space Grotesk/Barlow/Plex:"
foreach ($n in $all) {
    if ($n -match 'Newsreader|Fraunces|Space Grotesk|Barlow|Plex') { Write-Output "  $n" }
}

# ---- controlo: o MESMO nome perguntado ao GDI --------------------------
Add-Type -AssemblyName System.Drawing
$gdi = New-Object System.Drawing.Text.InstalledFontCollection
$gdiNames = $gdi.Families | ForEach-Object { $_.Name }
Write-Output ""
Write-Output ("GDI (InstalledFontCollection)  famílias: {0}" -f $gdiNames.Count)
foreach ($t in $targets) {
    $hit = $gdiNames -contains $t
    Write-Output ("  {0,-20} -> {1}" -f $t, $(if ($hit) { 'PRESENTE' } else { 'AUSENTE' }))
}
Write-Output ""
Write-Output "Controlo negativo:"
Write-Output ("  {0,-20} -> DW {1} | GDI {2}" -f '__fonte-que-nao-existe__', [DWriteCensus]::Find('__fonte-que-nao-existe__'), $(if ($gdiNames -contains '__fonte-que-nao-existe__') { 'PRESENTE' } else { 'AUSENTE' }))
