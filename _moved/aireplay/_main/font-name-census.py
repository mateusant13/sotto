# font-name-census.py — censo das tabelas 'name'/'fvar'/'OS/2' dos ficheiros
# variáveis instalados por utilizador. Responde: que família é que cada
# ficheiro DIZ que é, com que eixos, e se o ficheiro se lê sem erro.
#
# Uso: py -3 H:\aireplay\_main\font-name-census.py
import os, sys, glob

from fontTools.ttLib import TTFont

FONTS = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "Fonts")
WANT = [
    "Newsreader-Variable.ttf", "Newsreader-Italic-Variable.ttf",
    "Fraunces-Variable.ttf", "Fraunces-Italic-Variable.ttf",
    "SpaceGrotesk-Variable.ttf",
    "BarlowCondensed-Bold.ttf", "IBMPlexMono-Bold.ttf", "IBMPlexMono-Italic.ttf",
]
IDS = {1: "family(1)", 2: "subfamily(2)", 3: "uid(3)", 4: "full(4)", 5: "version(5)",
       6: "ps(6)", 16: "typofamily(16)", 17: "typosub(17)", 21: "wws(21)", 22: "wws2(22)"}


def names(f):
    out = {}
    for rec in f["name"].names:
        if rec.nameID in IDS and rec.platformID == 3 and rec.langID == 0x409:
            out[rec.nameID] = rec.toUnicode()
    return out


def main():
    print("font-name-census  FONTS=%s" % FONTS)
    for w in WANT:
        p = os.path.join(FONTS, w)
        print("=" * 78)
        print("%s  %d B  exists=%s" % (w, os.path.getsize(p), os.path.exists(p)))
        try:
            f = TTFont(p, lazy=True, fontNumber=0)
        except Exception as e:
            print("  READ FAILED: %r" % (e,))
            continue
        n = names(f)
        for i in sorted(n):
            print("  %-16s %r" % (IDS[i], n[i]))
        missing = [IDS[i] for i in (1, 2, 16, 17) if i not in n]
        print("  name IDs ausentes: %s" % (missing or "nenhum"))
        if "fvar" in f:
            axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue, a.flags)
                    for a in f["fvar"].axes]
            print("  fvar axes (%d): %s" % (len(axes), axes))
            insts = f["fvar"].instances
            print("  fvar named instances: %d" % len(insts))
            for ins in insts[:12]:
                nm = ins.subfamilyNameID
                try:
                    nm = f["name"].getDebugName(ins.subfamilyNameID)
                except Exception:
                    pass
                print("      %-28s ps=%s coords=%s" % (nm, getattr(ins, "postscriptNameID", None),
                                                       ins.coordinates))
        else:
            print("  fvar: (não é variável)")
        os2 = f["OS/2"]
        head = f["head"]
        post = f["post"]
        print("  OS/2 fsSelection=0x%04x  usWeightClass=%d  usWidthClass=%d"
              % (os2.fsSelection, os2.usWeightClass, os2.usWidthClass))
        print("  head.macStyle=0x%04x  unitsPerEm=%d  post.italicAngle=%.2f  post.isFixedPitch=%d"
              % (head.macStyle, head.unitsPerEm, post.italicAngle, post.isFixedPitch))
        print("  tabelas: %s" % ",".join(sorted(f.keys())))
        f.close()


if __name__ == "__main__":
    main()
