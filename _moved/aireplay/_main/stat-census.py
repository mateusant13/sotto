# stat-census.py — censo da tabela STAT dos ficheiros variáveis instalados.
#
# Porque é que isto importa: o DirectWrite (o backend de fontes do Chromium no
# Windows) constrói o nome da FAMÍLIA a partir de ID16/ID1 + os valores de eixo
# da STAT que NÃO estejam marcados como "elidíveis". Um valor de eixo com
# Flags sem o bit ELIDABLE (0x0002) é colado ao nome da família — é assim que
# `Fraunces` se transforma em `Fraunces 9pt` e `Fraunces 9pt SuperSoft`.
#
# Uso: py -3 H:\aireplay\_main\stat-census.py
import os
from fontTools.ttLib import TTFont

FONTS = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "Fonts")
WANT = ["Newsreader-Variable.ttf", "Newsreader-Italic-Variable.ttf",
        "Fraunces-Variable.ttf", "Fraunces-Italic-Variable.ttf",
        "SpaceGrotesk-Variable.ttf"]

ELIDABLE = 0x0002
OLDER_SIBLING = 0x0001


def main():
    for w in WANT:
        p = os.path.join(FONTS, w)
        f = TTFont(p, lazy=True)
        print("=" * 78)
        print(w)
        try:
            st = f["STAT"].table
        except Exception as e:
            print("  sem STAT: %r" % (e,))
            f.close()
            continue
        print("  STAT version=%s  ElidedFallbackNameID=%s"
              % (getattr(st, "Version", "?"), getattr(st, "ElidedFallbackNameID", "?")))
        axes = []
        if getattr(st, "DesignAxisRecord", None):
            for a in st.DesignAxisRecord.Axis:
                axes.append((a.AxisTag, a.AxisNameID, a.AxisOrdering))
                print("  DesignAxis tag=%-5s nameID=%-4s order=%s  (%s)"
                      % (a.AxisTag, a.AxisNameID, a.AxisOrdering,
                         f["name"].getDebugName(a.AxisNameID)))
        if getattr(st, "AxisValueArray", None) and st.AxisValueArray:
            for i, av in enumerate(st.AxisValueArray.AxisValue):
                fmt = av.Format
                fl = av.Flags
                nm = f["name"].getDebugName(av.ValueNameID)
                extra = ""
                if fmt in (1, 3, 4):
                    extra = " axisIndex=%s value=%s" % (getattr(av, "AxisIndex", "?"),
                                                        getattr(av, "Value", "?"))
                    if fmt == 3:
                        extra += " linkedValue=%s" % getattr(av, "LinkedValue", "?")
                    if fmt == 4:
                        extra = " axisValueRecords=%s" % [
                            (r.AxisIndex, r.Value) for r in av.AxisValueRecord]
                elif fmt == 2:
                    extra = " nomimalValue=%s rangeMin=%s rangeMax=%s" % (
                        av.NominalValue, av.RangeMinValue, av.RangeMaxValue)
                print("  AxisValue[%d] fmt=%d flags=0x%04x %s elidable=%s olderSibling=%s  %r"
                      % (i, fmt, fl, extra, bool(fl & ELIDABLE), bool(fl & OLDER_SIBLING), nm))
        f.close()


if __name__ == "__main__":
    main()
